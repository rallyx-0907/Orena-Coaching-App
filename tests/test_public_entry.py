"""The public entry: `/` is the Landing for a visitor who is not signed in (sign-in on), the learner shell
for everyone else; `/landing`, `/terms` and `/privacy` are public pages. Nothing under /api opens."""

import asyncio

import httpx
from itsdangerous import TimestampSigner
import base64
import json

import app as app_module
import auth_support

LANDING_MARKER = 'data-screen-label="Landing"'
SHELL_MARKER = "/orena-assets/main.js"


def _client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app_module.app), base_url="http://testserver")


def _run(coro):
    return asyncio.run(coro)


def _session_cookie(**values):
    payload = base64.b64encode(json.dumps(values).encode("utf-8"))
    return TimestampSigner(auth_support.SESSION_SECRET or "local-single-user-mode").sign(payload).decode("utf-8")


def test_anonymous_root_is_the_landing_when_sign_in_is_on(monkeypatch):
    monkeypatch.setattr(auth_support, "AUTH_ENABLED", True)

    async def go():
        async with _client() as c:
            return await c.get("/"), await c.get("/?app=1")

    root, shell = _run(go())
    assert root.status_code == 200 and LANDING_MARKER in root.text and SHELL_MARKER not in root.text
    assert root.headers["cache-control"] == "no-store, max-age=0"
    assert shell.status_code == 200 and SHELL_MARKER in shell.text and LANDING_MARKER not in shell.text


def test_signed_in_root_is_the_shell(monkeypatch):
    monkeypatch.setattr(auth_support, "AUTH_ENABLED", True)
    monkeypatch.setattr(auth_support, "ensure_user_db", lambda: None)

    async def go():
        async with _client() as c:
            c.cookies.set("writing_coach_session", _session_cookie(user_sub="sub-1"))
            return await c.get("/")

    root = _run(go())
    assert root.status_code == 200 and SHELL_MARKER in root.text and LANDING_MARKER not in root.text
    assert root.headers["cache-control"] == "no-store, max-age=0"


def test_local_mode_root_is_the_shell(monkeypatch):
    monkeypatch.setattr(auth_support, "AUTH_ENABLED", False)

    async def go():
        async with _client() as c:
            return await c.get("/")

    root = _run(go())
    assert root.status_code == 200 and SHELL_MARKER in root.text and LANDING_MARKER not in root.text


def test_public_pages_need_no_session(monkeypatch):
    monkeypatch.setattr(auth_support, "AUTH_ENABLED", True)

    async def go():
        async with _client() as c:
            return {p: await c.get(p) for p in ("/landing", "/terms", "/privacy", "/terms?lang=en", "/privacy?lang=zh")}

    r = _run(go())
    for path, res in r.items():
        assert res.status_code == 200, path
        assert "text/html" in res.headers["content-type"], path
    assert LANDING_MARKER in r["/landing"].text
    assert "Điều khoản dịch vụ" in r["/terms"].text and "Terms of Service" in r["/terms"].text
    assert "Chính sách quyền riêng tư" in r["/privacy"].text
    for res in r.values():
        assert "Orena Donate.dc.html" not in res.text, "Donate is out of scope"
        assert ".dc.html" not in res.text.replace("data-dc-script", ""), "no prototype-file link survives"


def test_public_pages_in_local_mode(monkeypatch):
    monkeypatch.setattr(auth_support, "AUTH_ENABLED", False)

    async def go():
        async with _client() as c:
            return [await c.get(p) for p in ("/landing", "/terms", "/privacy")]

    assert [r.status_code for r in _run(go())] == [200, 200, 200]


def test_the_api_and_admin_stay_closed_to_a_visitor(monkeypatch):
    monkeypatch.setattr(auth_support, "AUTH_ENABLED", True)

    async def go():
        async with _client() as c:
            return {
                "profile": await c.get("/api/learner-profile"),
                "me": await c.get("/api/me"),
                "admin": await c.get("/api/admin/ai/config"),
            }

    r = _run(go())
    assert r["profile"].status_code == 401
    assert r["me"].status_code == 401
    assert r["admin"].status_code in (401, 403)


def test_login_leads_to_the_shell_without_a_loop(monkeypatch):
    monkeypatch.setattr(auth_support, "AUTH_ENABLED", True)

    async def go():
        async with _client() as c:
            login = await c.get("/login")
            target = login.headers["location"]
            landed = await c.get(target.split("#")[0])
            return login, target, landed

    login, target, landed = _run(go())
    assert login.status_code == 302 and target == "/?app=1#/welcome"
    assert landed.status_code == 200 and SHELL_MARKER in landed.text, "the redirect target is the shell, not the Landing"


def test_landing_buttons_point_where_the_visitor_can_continue():
    text = (app_module.ROOT / "templates" / "orena" / "public" / "landing.html").read_text(encoding="utf-8")
    assert 'href="/?app=1#/welcome"' in text and 'href="/privacy?lang=en"' in text and 'href="/terms?lang=en"' in text
    assert "Onboarding.dc.html" not in text
