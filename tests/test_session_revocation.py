"""Sign-out ends the session on the server, not only in the browser."""

import asyncio
import base64
import json
import time

import httpx
from itsdangerous import TimestampSigner

import app as app_module
import auth_support


def _cookie(**values) -> str:
    encoded = base64.b64encode(json.dumps(values).encode("utf-8"))
    return TimestampSigner(auth_support.SESSION_SECRET or "local-single-user-mode").sign(encoded).decode("utf-8")


def _signed_in(monkeypatch):
    monkeypatch.setattr(auth_support, "AUTH_ENABLED", True)
    monkeypatch.setattr(auth_support, "auth_user", lambda sub: {"google_sub": sub, "role": "user"})
    monkeypatch.setattr(auth_support, "ensure_user_db", lambda: None)


def _run(coro):
    return asyncio.run(coro)


def _client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app_module.app), base_url="http://testserver")


def test_old_cookie_is_refused_after_logout_for_reads_and_writes(monkeypatch):
    _signed_in(monkeypatch)
    sub = f"revoke-{time.time_ns()}"
    old = _cookie(user_sub=sub, iat_ms=auth_support._now_ms())

    async def exercise():
        async with _client() as client:
            client.cookies.set("writing_coach_session", old)
            before = await client.get("/api/session/bootstrap")
            out = await client.post("/auth/logout")
        async with _client() as replay:  # a copy of the cookie the browser held before signing out
            replay.cookies.set("writing_coach_session", old)
            read = await replay.get("/api/session/bootstrap")
            write = await replay.post("/api/essays", json={})
        return before, out, read, write

    before, out, read, write = _run(exercise())
    assert before.status_code == 200
    assert out.status_code == 200
    assert read.status_code == 401
    assert write.status_code == 401


def test_cookie_without_issue_time_is_refused_after_logout(monkeypatch):
    _signed_in(monkeypatch)
    sub = f"legacy-{time.time_ns()}"
    old = _cookie(user_sub=sub)

    async def exercise():
        async with _client() as client:
            client.cookies.set("writing_coach_session", old)
            before = await client.get("/api/session/bootstrap")
            await client.post("/auth/logout")
        async with _client() as replay:
            replay.cookies.set("writing_coach_session", old)
            return before, await replay.get("/api/session/bootstrap")

    before, after = _run(exercise())
    assert (before.status_code, after.status_code) == (200, 401)


def test_fresh_sign_in_after_logout_works_and_other_users_are_unaffected(monkeypatch):
    _signed_in(monkeypatch)
    stamp = time.time_ns()
    sub, other = f"a-{stamp}", f"b-{stamp}"
    old = _cookie(user_sub=sub, iat_ms=auth_support._now_ms())
    bystander = _cookie(user_sub=other, iat_ms=auth_support._now_ms())

    async def exercise():
        async with _client() as client:
            client.cookies.set("writing_coach_session", old)
            await client.post("/auth/logout")
        time.sleep(0.01)
        fresh = _cookie(user_sub=sub, iat_ms=auth_support._now_ms())
        async with _client() as client:
            client.cookies.set("writing_coach_session", fresh)
            signed_in = await client.get("/api/session/bootstrap")
        async with _client() as client:
            client.cookies.set("writing_coach_session", bystander)
            unaffected = await client.get("/api/session/bootstrap")
        return signed_in, unaffected

    signed_in, unaffected = _run(exercise())
    assert signed_in.status_code == 200
    assert unaffected.status_code == 200


def test_native_exchange_cookie_is_revoked_by_logout(monkeypatch):
    _signed_in(monkeypatch)
    sub = f"native-{time.time_ns()}"
    cookie = auth_support._native_session_cookie(sub)

    async def exercise():
        async with _client() as client:
            first = await client.get("/api/session/bootstrap", headers={"Cookie": f"writing_coach_session={cookie}"})
            await client.post("/auth/logout", headers={"Cookie": f"writing_coach_session={cookie}"})
            second = await client.get("/api/session/bootstrap", headers={"Cookie": f"writing_coach_session={cookie}"})
        return first, second

    first, second = _run(exercise())
    assert (first.status_code, second.status_code) == (200, 401)


def test_an_unreadable_revocation_record_refuses_the_request(monkeypatch):
    _signed_in(monkeypatch)

    class Broken:
        def get_setting(self, key):
            raise OSError("down")

    monkeypatch.setattr(auth_support, "_session_revocation_store", Broken())

    async def exercise():
        async with _client() as client:
            client.cookies.set("writing_coach_session", _cookie(user_sub="u", iat_ms=auth_support._now_ms()))
            return await client.get("/api/session/bootstrap")

    assert _run(exercise()).status_code == 503


def test_one_keyed_read_per_request(monkeypatch):
    _signed_in(monkeypatch)
    calls = []
    real = auth_support._session_revocation_store

    class Counting:
        def get_setting(self, key):
            calls.append(key)
            return real.get_setting(key)

    monkeypatch.setattr(auth_support, "_session_revocation_store", Counting())

    async def exercise():
        async with _client() as client:
            client.cookies.set("writing_coach_session", _cookie(user_sub="count", iat_ms=auth_support._now_ms()))
            return await client.get("/api/session/bootstrap")

    assert _run(exercise()).status_code == 200
    assert len(calls) == 1
