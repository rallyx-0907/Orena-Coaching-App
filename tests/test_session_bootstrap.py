"""ASGI contract tests for the compact authenticated session bootstrap."""

import asyncio
import base64
import hashlib
import json

import httpx
from itsdangerous import TimestampSigner

import app as app_module
import auth_support


def _session_cookie(**values: str) -> str:
    encoded = base64.b64encode(json.dumps(values).encode("utf-8"))
    return TimestampSigner(auth_support.SESSION_SECRET or "local-single-user-mode").sign(encoded).decode("utf-8")


def test_bootstrap_is_authenticated_versioned_compact_and_language_scoped(monkeypatch):
    monkeypatch.setattr(auth_support, "AUTH_ENABLED", True)
    monkeypatch.setattr(auth_support, "auth_user", lambda sub: {"google_sub": sub, "role": "user"})
    monkeypatch.setattr(auth_support, "ensure_user_db", lambda: None)

    async def exercise():
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            responses = []
            for language in ("en", "zh"):
                client.cookies.set("writing_coach_session", _session_cookie(user_sub="user-1", language=language))
                responses.append(await client.get("/api/session/bootstrap"))
            return responses

    responses = asyncio.run(exercise())
    assert [response.status_code for response in responses] == [200, 200]
    for response, language in zip(responses, ("en", "zh")):
        payload = response.json()
        assert payload["version"] == "orena.session-bootstrap.v1"
        assert payload["authenticated"] is True
        assert payload["mode"] == "google"
        assert payload["user"] == {"role": "user", "is_admin": False}
        assert payload["language"]["active"] == language
        assert {item["code"] for item in payload["language"]["options"]} == {"en", "zh"}
        assert set(payload) == {"version", "authenticated", "mode", "user", "language", "consent"}
        assert response.headers["cache-control"] == "no-store"
        assert all(secret not in repr(payload) for secret in ("user-1", "@", "essay", "text"))


def test_bootstrap_rejects_missing_and_expired_sessions_without_identity(monkeypatch):
    monkeypatch.setattr(auth_support, "AUTH_ENABLED", True)
    monkeypatch.setattr(auth_support, "auth_user", lambda _sub: None)

    async def exercise():
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            missing = await client.get("/api/session/bootstrap")
            client.cookies.set("writing_coach_session", "expired-or-invalid")
            expired = await client.get("/api/session/bootstrap")
            client.cookies.set(
                "writing_coach_session",
                _session_cookie(user_sub="unknown-user", language="en"),
            )
            unknown = await client.get("/api/session/bootstrap")
            return missing, expired, unknown

    responses = asyncio.run(exercise())
    assert [response.status_code for response in responses] == [401, 401, 401]
    for response in responses:
        assert response.json() == {"detail": "Authentication required"}
        assert all(secret not in response.text for secret in ("user-1", "email", "role", "language"))


def test_bootstrap_accepts_native_style_session_cookie_header(monkeypatch):
    """The native client attaches the existing signed session as a Cookie header."""
    monkeypatch.setattr(auth_support, "AUTH_ENABLED", True)
    monkeypatch.setattr(auth_support, "auth_user", lambda sub: {"google_sub": sub, "role": "user"})
    monkeypatch.setattr(auth_support, "ensure_user_db", lambda: None)

    async def exercise():
        cookie = _session_cookie(user_sub="native-user", language="zh")
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(
                "/api/session/bootstrap",
                headers={"Cookie": f"writing_coach_session={cookie}"},
            )

    response = asyncio.run(exercise())
    assert response.status_code == 200
    payload = response.json()
    assert payload["authenticated"] is True
    assert payload["language"]["active"] == "zh"
    assert payload["user"] == {"role": "user", "is_admin": False}


def test_native_handoff_exchange_issues_cookie_accepted_by_bootstrap(monkeypatch):
    monkeypatch.setattr(auth_support, "AUTH_ENABLED", True)
    monkeypatch.setattr(auth_support, "auth_user", lambda sub: {"google_sub": sub, "role": "user"})
    monkeypatch.setattr(auth_support, "ensure_user_db", lambda: None)

    async def exercise():
        verifier = "native-verifier"
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        assert any(char.isupper() for char in challenge)
        assert any(char.islower() for char in challenge)
        handoff = auth_support.issue_native_handoff("native-user", challenge)
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            exchange = await client.post(
                "/api/auth/native/exchange",
                json={"code": handoff, "code_verifier": verifier},
            )
            cookie = exchange.json()["session_cookie"]
            bootstrap = await client.get(
                "/api/session/bootstrap",
                headers={"Cookie": f"writing_coach_session={cookie}"},
            )
            replay = await client.post("/api/auth/native/exchange", json={"code": handoff})
            return exchange, bootstrap, replay

    exchange, bootstrap, replay = asyncio.run(exercise())
    assert exchange.status_code == 200
    assert exchange.json()["version"] == "orena.native-session.v1"
    assert exchange.headers["cache-control"] == "no-store"
    assert bootstrap.status_code == 200
    assert bootstrap.json()["authenticated"] is True
    assert replay.status_code == 401


def test_native_handoff_requires_the_bound_verifier_and_logout_endpoint_is_best_effort(monkeypatch):
    monkeypatch.setattr(auth_support, "AUTH_ENABLED", True)
    monkeypatch.setattr(auth_support, "auth_user", lambda sub: {"google_sub": sub, "role": "user"})
    monkeypatch.setattr(auth_support, "ensure_user_db", lambda: None)

    async def exchange(client, verifier_payload):
        verifier = "bound-verifier"
        handoff = auth_support.issue_native_handoff(
            "native-user",
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode(),
        )
        payload = {"code": handoff, **verifier_payload}
        return await client.post("/api/auth/native/exchange", json=payload)

    async def exercise():
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            missing = await exchange(client, {})
            wrong = await exchange(client, {"code_verifier": "wrong-verifier"})
            valid = await exchange(client, {"code_verifier": "bound-verifier"})
            cookie = valid.json()["session_cookie"]
            logout = await client.post(
                "/auth/logout",
                headers={"Cookie": f"writing_coach_session={cookie}"},
            )
            return missing, wrong, valid, logout

    missing, wrong, valid, logout = asyncio.run(exercise())
    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert valid.status_code == 200
    assert logout.status_code == 200
