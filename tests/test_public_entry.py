"""The public entry: `/` is the Landing for a visitor who is not signed in (sign-in on), the learner shell
for everyone else; `/landing`, `/terms`, `/privacy` and `/account-deletion` are public pages. Nothing under /api opens."""

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
            return {p: await c.get(p) for p in ("/landing", "/terms", "/privacy", "/account-deletion", "/terms?lang=en", "/privacy?lang=zh", "/account-deletion?lang=en")}

    r = _run(go())
    for path, res in r.items():
        assert res.status_code == 200, path
        assert "text/html" in res.headers["content-type"], path
    assert LANDING_MARKER in r["/landing"].text
    # Vietnamese by default, English for ?lang=en, and English for ?lang=zh (there is no Chinese text).
    assert '<html lang="vi">' in r["/terms"].text and "Điều khoản dịch vụ" in r["/terms"].text
    assert '<html lang="en">' in r["/terms?lang=en"].text and "Terms of Service" in r["/terms?lang=en"].text
    assert "Chính sách quyền riêng tư" in r["/privacy"].text
    assert '<html lang="en">' in r["/privacy?lang=zh"].text and "Privacy Policy" in r["/privacy?lang=zh"].text
    assert "Xoá tài khoản" in r["/account-deletion"].text and "Delete account" in r["/account-deletion?lang=en"].text
    for path, res in r.items():
        if path != "/landing":
            # The legal pages are static: the text is in the response and no runtime or script file is loaded.
            assert "<h2" in res.text and "support.js" not in res.text and "<x-dc" not in res.text, path
            assert "<script src" not in res.text, path
    for res in r.values():
        assert "Orena Donate.dc.html" not in res.text, "Donate is out of scope"
        assert ".dc.html" not in res.text.replace("data-dc-script", ""), "no prototype-file link survives"
        assert "fonts.googleapis.com" not in res.text and "fonts.gstatic.com" not in res.text, "fonts are self-hosted"


def test_public_pages_in_local_mode(monkeypatch):
    monkeypatch.setattr(auth_support, "AUTH_ENABLED", False)

    async def go():
        async with _client() as c:
            return [await c.get(p) for p in ("/landing", "/terms", "/privacy", "/account-deletion")]

    assert [r.status_code for r in _run(go())] == [200, 200, 200, 200]


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


async def _fetch(path):
    async with _client() as c:
        return await c.get(path)


def _get(path):
    return _fetch(path)


def test_account_deletion_page_is_public_uncached_and_says_how(monkeypatch):
    # Google Play's deletion URL: reachable signed out, never cached, and it names the real request channel.
    monkeypatch.setattr(auth_support, "AUTH_ENABLED", True)

    async def go():
        async with _client() as c:
            return await c.get("/account-deletion")

    res = _run(go())
    assert res.status_code == 200 and "text/html" in res.headers["content-type"]
    assert res.headers["cache-control"] == "no-store, max-age=0"
    assert "orena.support@chillpickle.org" in res.text
    assert "30 ngày" in res.text
    en = _run(_get("/account-deletion?lang=en"))
    assert "30 days" in en.text and "orena.support@chillpickle.org" in en.text
    assert "/account-deletion" in auth_support.PUBLIC_PAGE_PATHS


def test_fonts_are_served_from_this_origin_and_the_shell_does_not_call_google(monkeypatch):
    monkeypatch.setattr(auth_support, "AUTH_ENABLED", False)

    async def go():
        async with _client() as c:
            shell = await c.get("/?app=1")
            css = await c.get("/orena-assets/fonts/fonts.css")
            face = await c.get("/orena-assets/fonts/outfit-normal-latin.woff2")
            return shell, css, face

    shell, css, face = _run(go())
    assert "fonts.googleapis.com" not in shell.text and "fonts.gstatic.com" not in shell.text
    assert "/orena-assets/fonts/fonts.css" in shell.text
    assert css.status_code == 200 and "font-family:'Outfit'" in css.text and "https://" not in css.text
    assert face.status_code == 200 and face.content[:4] == b"wOF2"
    assert "max-age=604800" in face.headers["cache-control"]
