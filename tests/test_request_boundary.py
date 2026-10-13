"""Signed-out local-admin is a property of the real request boundary, not of configuration (issue #137).

These tests drive real ASGI requests with a chosen peer address through the production middleware and guard, so a
change that decides locality from Host, Origin, forwarding headers or PUBLIC_BASE_URL fails here. The failure mode
that escaped the 2026-10-04 review - config-local read as request-local - has its own regression below."""

from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi import Depends, FastAPI
from starlette.middleware.sessions import SessionMiddleware

import auth_support
from writing_coach.core import request_boundary
from writing_coach.core.request_context import USER_KEY_CTX

LAN_PEER = "192.168.1.20"
GATEWAY = "172.29.0.1"
OTHER_CONTAINER = "172.29.0.5"
# /proc/net/route of a container on a bridge whose gateway is 172.29.0.1 (little-endian hex 01001DAC).
ROUTE_TABLE = (
    "Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT\n"
    "eth0\t00000000\t01001DAC\t0003\t0\t0\t0\t00000000\t0\t0\t0\n"
    "eth0\t00001DAC\t00000000\t0001\t0\t0\t0\t0000FFFF\t0\t0\t0\n"
)


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_support.router)

    @app.get("/api/admin-probe")
    def admin_probe(admin: dict = Depends(auth_support.require_admin)):
        return {"who": admin["google_sub"]}

    @app.get("/api/learner-probe")
    def learner_probe():
        return {"scope": USER_KEY_CTX.get()}

    @app.get("/api/health")
    def health():
        return {"ok": True}

    app.add_middleware(auth_support.UserIsolationMiddleware)
    app.add_middleware(SessionMiddleware, secret_key="t" * 40)
    return app


@pytest.fixture()
def signed_out_dev(monkeypatch):
    """An auth-disabled development runtime whose configuration allows a local administrator."""
    for name in (
        request_boundary.TRUST_DOCKER_PUBLISHED_PORT_ENV,
        request_boundary.PUBLISHED_BIND_HOST_ENV,
        "ALLOW_LOCAL_ADMIN",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")
    monkeypatch.setattr(auth_support, "AUTH_ENABLED", False)
    monkeypatch.setattr(auth_support, "LOCAL_ADMIN_ALLOWED", True)
    monkeypatch.setattr(request_boundary, "_read_route_table", lambda: ROUTE_TABLE)
    return monkeypatch


def _get(path: str, peer: object = "127.0.0.1", headers: dict[str, str] | None = None) -> httpx.Response:
    async def run():
        client_address = (peer, 51234) if peer is not None else None
        transport = httpx.ASGITransport(app=_app(), client=client_address)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(path, headers=headers or {})

    return asyncio.run(run())


def _declare_loopback_publish(monkeypatch, host: str = "127.0.0.1") -> None:
    monkeypatch.setenv(request_boundary.TRUST_DOCKER_PUBLISHED_PORT_ENV, "1")
    monkeypatch.setenv(request_boundary.PUBLISHED_BIND_HOST_ENV, host)


# ---- the real request boundary ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("peer", ["127.0.0.1", "127.0.0.2", "::1", "::ffff:127.0.0.1"])
def test_loopback_client_keeps_the_signed_out_local_admin(signed_out_dev, peer):
    assert _get("/api/admin-probe", peer).json() == {"who": "local-admin"}
    assert _get("/api/learner-probe", peer).json() == {"scope": "legacy"}
    assert _get("/api/me", peer).json()["is_admin"] is True


@pytest.mark.parametrize("peer", [LAN_PEER, "10.0.0.7", "8.8.8.8", "2001:db8::1", OTHER_CONTAINER, "testclient", None])
def test_remote_client_is_denied_admin_and_the_shared_learner_scope(signed_out_dev, peer):
    assert _get("/api/admin-probe", peer).status_code == 403
    assert _get("/api/learner-probe", peer).status_code == 403
    assert _get("/api/me", peer).status_code == 403
    assert _get("/api/health", peer).status_code == 200, "a public page stays public"


@pytest.mark.parametrize(
    "headers",
    [
        {"Host": "localhost:8000"},
        {"Host": "127.0.0.1"},
        {"Origin": "http://localhost:8000"},
        {"Referer": "http://127.0.0.1:8000/"},
        {"Host": "localhost", "Origin": "http://localhost:8000"},
    ],
)
def test_a_remote_request_cannot_claim_to_be_local_by_host_or_origin(signed_out_dev, headers):
    assert _get("/api/admin-probe", LAN_PEER, headers).status_code == 403
    assert _get("/api/learner-probe", LAN_PEER, headers).status_code == 403


@pytest.mark.parametrize(
    "headers",
    [
        {"X-Forwarded-For": "127.0.0.1"},
        {"Forwarded": "for=127.0.0.1"},
        {"X-Real-IP": "127.0.0.1"},
        {"CF-Connecting-IP": "127.0.0.1"},
    ],
)
def test_forwarding_headers_never_grant_locality_and_a_forwarded_request_is_not_local(signed_out_dev, headers):
    assert _get("/api/admin-probe", LAN_PEER, headers).status_code == 403
    # A loopback hop (a tunnel agent or reverse proxy on this machine) that says it forwarded is not the developer.
    assert _get("/api/admin-probe", "127.0.0.1", headers).status_code == 403
    assert _get("/api/learner-probe", "127.0.0.1", headers).status_code == 403


def test_config_local_does_not_imply_request_local(signed_out_dev):
    """The escaped failure mode: PUBLIC_BASE_URL says localhost, the config function says yes, the caller is remote."""
    assert auth_support._local_admin_allowed({"PUBLIC_BASE_URL": "http://localhost:8000"}) is True
    assert auth_support._local_admin_allowed({}) is True
    assert auth_support.LOCAL_ADMIN_ALLOWED is True
    assert _get("/api/admin-probe", LAN_PEER).status_code == 403
    # ALLOW_LOCAL_ADMIN relaxes the address check of the configuration only; the peer still decides.
    signed_out_dev.setenv("ALLOW_LOCAL_ADMIN", "1")
    assert _get("/api/admin-probe", LAN_PEER).status_code == 403


def test_configuration_can_only_restrict_a_loopback_request(signed_out_dev):
    signed_out_dev.setattr(auth_support, "LOCAL_ADMIN_ALLOWED", False)
    assert _get("/api/admin-probe", "127.0.0.1").status_code == 503
    assert _get("/api/me", "127.0.0.1").json()["is_admin"] is False


def test_a_public_runtime_has_no_signed_out_developer_even_on_loopback(signed_out_dev):
    signed_out_dev.setenv("APP_ENV", "staging")
    assert _get("/api/learner-probe", "127.0.0.1").status_code == 403
    assert request_boundary.request_is_local("127.0.0.1", {}, {"APP_ENV": "production"}) is False


# ---- Docker's published port ----------------------------------------------------------------------------------------


def test_the_docker_gateway_is_the_developer_only_with_a_loopback_publish_and_the_trust_flag(signed_out_dev):
    assert _get("/api/admin-probe", GATEWAY).status_code == 403, "denied until the operator declares a loopback publish"
    _declare_loopback_publish(signed_out_dev)
    assert _get("/api/admin-probe", GATEWAY).json() == {"who": "local-admin"}
    assert _get("/api/learner-probe", GATEWAY).json() == {"scope": "legacy"}


@pytest.mark.parametrize("bind", ["0.0.0.0", "192.168.1.5", "", "::"])
def test_a_lan_publish_voids_the_gateway_trust(signed_out_dev, bind):
    _declare_loopback_publish(signed_out_dev, bind)
    assert _get("/api/admin-probe", GATEWAY).status_code == 403


def test_the_trust_names_the_gateway_alone(signed_out_dev):
    _declare_loopback_publish(signed_out_dev)
    assert _get("/api/admin-probe", OTHER_CONTAINER).status_code == 403
    assert _get("/api/admin-probe", LAN_PEER).status_code == 403
    assert _get("/api/admin-probe", GATEWAY, {"X-Forwarded-For": GATEWAY}).status_code == 403


def test_without_a_known_gateway_the_trust_fails_closed(signed_out_dev):
    _declare_loopback_publish(signed_out_dev)
    signed_out_dev.setattr(request_boundary, "_read_route_table", lambda: "")
    assert _get("/api/admin-probe", GATEWAY).status_code == 403


# ---- the policy function ---------------------------------------------------------------------------------------------


def test_default_gateway_is_read_from_the_lowest_metric_default_route():
    assert request_boundary.default_gateway(ROUTE_TABLE) == GATEWAY
    two = ROUTE_TABLE + "eth1\t00000000\t0100000A\t0003\t0\t0\t100\t00000000\t0\t0\t0\n"
    assert request_boundary.default_gateway(two) == GATEWAY
    assert request_boundary.default_gateway("Iface\n") is None
    assert request_boundary.default_gateway("Iface\neth0\t00000000\t00000000\t0001\t0\t0\t0\t0\n") is None


@pytest.mark.parametrize(
    ("peer", "headers", "environ", "local"),
    [
        ("127.0.0.1", {}, {}, True),
        ("::1", {}, {}, True),
        ("localhost", {}, {}, False),
        ("", {}, {}, False),
        (None, {}, {}, False),
        (LAN_PEER, {"host": "localhost"}, {"PUBLIC_BASE_URL": "http://localhost:8000"}, False),
        (LAN_PEER, {}, {"ALLOW_LOCAL_ADMIN": "1"}, False),
        ("127.0.0.1", {"X-Forwarded-For": "8.8.8.8"}, {}, False),
        (GATEWAY, {}, {}, False),
        (GATEWAY, {}, {"ORENA_TRUST_DOCKER_PUBLISHED_PORT": "1"}, False),
        (GATEWAY, {}, {"ORENA_PUBLISHED_BIND_HOST": "127.0.0.1"}, False),
        (GATEWAY, {}, {"ORENA_TRUST_DOCKER_PUBLISHED_PORT": "1", "ORENA_PUBLISHED_BIND_HOST": "127.0.0.1"}, True),
        (GATEWAY, {}, {"ORENA_TRUST_DOCKER_PUBLISHED_PORT": "1", "ORENA_PUBLISHED_BIND_HOST": "0.0.0.0"}, False),
    ],
)
def test_request_is_local_policy(peer, headers, environ, local):
    assert request_boundary.request_is_local(peer, headers, environ, route_table=ROUTE_TABLE) is local


def test_the_peer_comes_from_the_connection_scope_only():
    assert request_boundary.peer_host({"client": ("10.1.2.3", 80)}) == "10.1.2.3"
    assert request_boundary.peer_host({"client": None}) is None
    assert request_boundary.peer_host({}) is None


# ---- extended forwarding headers, diagnostics ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "header",
    ["Via", "X-Client-IP", "Client-IP", "X-Cluster-Client-IP", "X-Forwarded", "Forwarded-For", "X-Original-Forwarded-For",
     "Fastly-Client-IP", "X-Envoy-External-Address", "X-Forwarded-Server", "True-Client-IP"],
)
def test_more_proxy_headers_revoke_locality(signed_out_dev, header):
    assert _get("/api/admin-probe", "127.0.0.1", {header: "1.1.1.1"}).status_code == 403
    assert request_boundary.request_is_local("127.0.0.1", {header: "x"}, {}) is False


def test_the_boot_line_names_the_trust_state_and_no_secret():
    off = request_boundary.trust_state_line({}, route_table=ROUTE_TABLE)
    assert "trust off" in off and GATEWAY in off and "(undeclared)" in off
    on = request_boundary.trust_state_line(
        {"ORENA_TRUST_DOCKER_PUBLISHED_PORT": "1", "ORENA_PUBLISHED_BIND_HOST": "127.0.0.1", "SESSION_SECRET": "s3cret"},
        route_table=ROUTE_TABLE,
    )
    assert "trust on" in on and "127.0.0.1" in on and "s3cret" not in on


def test_a_denied_peer_is_logged_once_by_address_only(signed_out_dev, caplog):
    request_boundary._LOGGED_DENIED.clear()
    with caplog.at_level("WARNING", logger="orena.request_boundary"):
        _get("/api/admin-probe", LAN_PEER, {"Authorization": "Bearer hunter2"})
        _get("/api/learner-probe", LAN_PEER)
    lines = [r.getMessage() for r in caplog.records if LAN_PEER in r.getMessage()]
    assert len(lines) == 1
    assert "hunter2" not in caplog.text


def test_a_gateway_peer_refused_for_missing_trust_says_what_to_set(signed_out_dev, caplog):
    request_boundary._LOGGED_DENIED.clear()
    with caplog.at_level("WARNING", logger="orena.request_boundary"):
        _get("/api/admin-probe", GATEWAY)
    assert "ORENA_TRUST_DOCKER_PUBLISHED_PORT=1" in caplog.text
