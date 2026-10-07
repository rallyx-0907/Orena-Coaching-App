"""Signing in to the new learner UI (/next): the shell is public, every /api route is not, and the
return target after Google sign-in or sign-out is a strict same-origin allowlist (no open redirect).

Google is never contacted: the OAuth flow object and the ID-token check are replaced."""

import asyncio
import base64
import json
from types import SimpleNamespace

import httpx
import pytest
from itsdangerous import TimestampSigner

import app as app_module
import auth_support

REJECTED = [
    "https://evil.example/next",
    "http://evil.example",
    "//evil.example/next",
    "/next//evil.example",
    "/\\evil.example",
    "/next\\evil",
    "\\next",
    "/nextevil",
    "/nex",
    "next",
    "/",
    "/login",
    "/api/me",
    "/next\r\nSet-Cookie: x=1",
    "/next\nLocation: https://evil.example",
    "/next ",
    " /next",
    "/next\t",
    "/next\x00",
    "/next/../..//evil.example",
    "javascript:alert(1)",
    "/next#//evil.example",
    "/next?u=https://evil.example",
    "/next/" + "a" * 600,
    "",
    None,
    123,
]

ACCEPTED = ["/next", "/next/", "/next#/today", "/next#/welcome?step=languages", "/next?x=1#/today", "/next#/"]


@pytest.mark.parametrize("value", REJECTED)
def test_every_rejected_form_falls_back(value):
    assert auth_support.safe_next_target(value) == "/next"
    assert auth_support.safe_next_target(value, default="/") == "/"


@pytest.mark.parametrize("value", ACCEPTED)
def test_accepted_forms_pass_through_unchanged(value):
    assert auth_support.safe_next_target(value) == value


class _FakeFlow:
    """Stands in for google_auth_oauthlib's Flow: no network, a fixed state/verifier."""

    code_verifier = "verifier-for-tests"
    seen: dict = {}

    def __init__(self):
        self.credentials = SimpleNamespace(id_token="raw-id-token")

    def authorization_url(self, **kwargs):
        _FakeFlow.seen = kwargs
        return f"https://accounts.example/auth?state={kwargs['state']}", kwargs["state"]

    def fetch_token(self, code):
        assert code == "the-code"


def _signed_in_setup(monkeypatch, nonce_echo=True):
    monkeypatch.setattr(auth_support, "AUTH_ENABLED", True)
    monkeypatch.setattr(auth_support, "GOOGLE_CLIENT_ID", "client-id-for-tests")
    monkeypatch.setattr(auth_support, "google_flow", lambda code_verifier=None: _FakeFlow())
    monkeypatch.setattr(auth_support, "auth_user", lambda sub: {"google_sub": sub, "role": "user"})
    monkeypatch.setattr(auth_support, "ensure_user_db", lambda: None)
    monkeypatch.setattr(auth_support, "upsert_auth_user", lambda info: {"google_sub": "sub-1", "email": "a@example.com"})
    monkeypatch.setattr(auth_support, "maybe_claim_legacy_data", lambda email, sub: False)

    def verify(token, request, audience):
        return {"email_verified": True, "nonce": _FakeFlow.seen.get("nonce") if nonce_echo else "forged", "sub": "sub-1"}

    monkeypatch.setattr(auth_support.google_id_token, "verify_oauth2_token", verify)


def _client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app_module.app), base_url="http://testserver")


async def _sign_in(client, next_param):
    params = {} if next_param is None else {"next": next_param}
    start = await client.get("/auth/google", params=params)
    assert start.status_code == 302
    state = _FakeFlow.seen["state"]
    return await client.get("/auth/google/callback", params={"state": state, "code": "the-code"})


def _run(coro):
    return asyncio.run(coro)


# ---- middleware ----------------------------------------------------------------------------------


def test_signed_out_the_new_ui_shell_is_reachable_and_the_api_is_not(monkeypatch):
    monkeypatch.setattr(auth_support, "AUTH_ENABLED", True)

    async def exercise():
        async with _client() as client:
            return {
                "shell": await client.get("/next"),
                "asset": await client.get("/orena-assets/main.js"),
                "brand": await client.get("/orena-brand/logo/orena-mark.svg"),
                "languages": await client.get("/api/platform/languages"),
                "me": await client.get("/api/me"),
                "bootstrap": await client.get("/api/session/bootstrap"),
                "profile": await client.get("/api/learner-profile"),
                "old_ui": await client.get("/"),
                "next_lookalike": await client.get("/nextevil"),
                "next_sub_path": await client.get("/next/anything"),
            }

    r = _run(exercise())
    assert r["shell"].status_code == 200
    assert "text/html" in r["shell"].headers["content-type"]
    assert r["asset"].status_code == 200
    assert r["brand"].status_code in (200, 404) and r["brand"].status_code != 302
    assert r["languages"].status_code == 200
    for name in ("me", "bootstrap", "profile"):
        assert r[name].status_code == 401, name
    # The old UI is still behind the sign-in page, and only /next exactly is public.
    assert r["old_ui"].status_code == 302 and r["old_ui"].headers["location"] == "/login"
    assert r["next_lookalike"].status_code == 302
    assert r["next_sub_path"].status_code == 302


def test_auth_disabled_serves_everything_as_before(monkeypatch):
    monkeypatch.setattr(auth_support, "AUTH_ENABLED", False)

    async def exercise():
        async with _client() as client:
            return await client.get("/next"), await client.get("/api/me"), await client.get("/login")

    shell, me, login = _run(exercise())
    assert shell.status_code == 200
    assert me.status_code == 200 and me.json()["mode"] == "local"
    assert login.status_code == 302 and login.headers["location"] == "/"


# ---- sign-in -------------------------------------------------------------------------------------


@pytest.mark.parametrize("target", ACCEPTED)
def test_callback_returns_to_an_allowed_next_target(monkeypatch, target):
    _signed_in_setup(monkeypatch)

    async def exercise():
        async with _client() as client:
            done = await _sign_in(client, target)
            bootstrap = await client.get("/api/session/bootstrap")
            return done, bootstrap

    done, bootstrap = _run(exercise())
    assert done.status_code == 302
    assert done.headers["location"] == target
    assert bootstrap.status_code == 200, "the session is signed in after the callback"


def test_callback_without_next_keeps_the_old_default(monkeypatch):
    _signed_in_setup(monkeypatch)
    done = _run(_run_with(None))
    assert done.status_code == 302 and done.headers["location"] == "/"


async def _run_with(target):
    async with _client() as client:
        return await _sign_in(client, target)


@pytest.mark.parametrize("target", [v for v in REJECTED if isinstance(v, str) and v and "\r" not in v and "\n" not in v and "\x00" not in v])
def test_callback_never_follows_a_rejected_target(monkeypatch, target):
    _signed_in_setup(monkeypatch)
    done = _run(_run_with(target))
    assert done.status_code == 302
    assert done.headers["location"] == "/next", "a next that was given and refused lands on /next, never elsewhere"


def test_a_later_sign_in_without_next_does_not_inherit_an_earlier_target(monkeypatch):
    _signed_in_setup(monkeypatch)

    async def exercise():
        async with _client() as client:
            await client.get("/auth/google", params={"next": "/next#/today"})
            await client.get("/auth/google")  # abandoned first attempt, then a plain one
            state = _FakeFlow.seen["state"]
            return await client.get("/auth/google/callback", params={"state": state, "code": "the-code"})

    done = _run(exercise())
    assert done.headers["location"] == "/"


def test_the_oauth_protections_are_unchanged(monkeypatch):
    _signed_in_setup(monkeypatch)

    async def exercise():
        async with _client() as client:
            start = await client.get("/auth/google", params={"next": "/next"})
            wrong_state = await client.get("/auth/google/callback", params={"state": "forged", "code": "the-code"})
            return start, wrong_state

    start, wrong_state = _run(exercise())
    assert _FakeFlow.seen["state"] and _FakeFlow.seen["nonce"], "state and nonce are still generated"
    assert _FakeFlow.seen["prompt"] == "select_account"
    assert wrong_state.status_code == 400

    _signed_in_setup(monkeypatch, nonce_echo=False)

    async def forged_nonce():
        async with _client() as client:
            return await _sign_in(client, "/next")

    assert _run(forged_nonce()).status_code == 400

    async def no_session():
        async with _client() as client:
            return await client.get("/auth/google/callback", params={"state": "x", "code": "the-code"})

    assert _run(no_session()).status_code == 400


def test_a_callback_query_cannot_choose_the_destination(monkeypatch):
    _signed_in_setup(monkeypatch)

    async def exercise():
        async with _client() as client:
            await client.get("/auth/google", params={"next": "/next#/today"})
            state = _FakeFlow.seen["state"]
            return await client.get(
                "/auth/google/callback",
                params={"state": state, "code": "the-code", "next": "https://evil.example"},
            )

    assert _run(exercise()).headers["location"] == "/next#/today"


def test_the_native_handoff_still_wins_over_next(monkeypatch):
    _signed_in_setup(monkeypatch)
    import hashlib

    challenge = base64.urlsafe_b64encode(hashlib.sha256(b"v").digest()).rstrip(b"=").decode()

    async def exercise():
        async with _client() as client:
            await client.get(
                "/auth/google",
                params={"next": "/next", "native_redirect_uri": "orena://auth/callback", "native_code_challenge": challenge},
            )
            state = _FakeFlow.seen["state"]
            return await client.get("/auth/google/callback", params={"state": state, "code": "the-code"})

    done = _run(exercise())
    assert done.headers["location"].startswith("orena://auth/callback?code=")


# ---- sign-out ------------------------------------------------------------------------------------


def _session_cookie(**values):
    encoded = base64.b64encode(json.dumps(values).encode("utf-8"))
    return TimestampSigner(auth_support.SESSION_SECRET or "local-single-user-mode").sign(encoded).decode("utf-8")


def test_logout_clears_the_session_and_names_a_validated_target(monkeypatch):
    monkeypatch.setattr(auth_support, "AUTH_ENABLED", True)
    monkeypatch.setattr(auth_support, "auth_user", lambda sub: {"google_sub": sub, "role": "user"})
    monkeypatch.setattr(auth_support, "ensure_user_db", lambda: None)

    async def exercise():
        results = []
        for params in ({}, {"next": "/next"}, {"next": "/next#/welcome"}, {"next": "https://evil.example"}, {"next": "//evil.example"}, {"next": "/next\\x"}):
            async with _client() as client:
                client.cookies.set("writing_coach_session", _session_cookie(user_sub="user-1"))
                before = await client.get("/api/me")
                out = await client.post("/auth/logout", params=params)
                # The jar keys the cookie by domain, so the deletion header is read directly.
                cleared = "1970" in out.headers.get("set-cookie", "")
                results.append((params, before.status_code, out, cleared))
        return results

    results = _run(exercise())
    for params, before, out, after in results:
        assert before == 200 and out.status_code == 200 and after is True, params
    bodies = [out.json() for _, _, out, _ in results]
    assert bodies[0] == {"ok": True}, "no next: the response is what it always was"
    assert bodies[1] == {"ok": True, "next": "/next"}
    assert bodies[2] == {"ok": True, "next": "/next#/welcome"}
    assert [b["next"] for b in bodies[3:]] == ["/next", "/next", "/next"]
