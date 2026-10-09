"""A normal, non-admin Google user on product-like staging is a learner, not a blocked reviewer.

Regression for the P1 where orena.chillpickle.org (APP_ENV=staging, Google sign-in on) showed a signed-in
user "This experience is available in the internal review environment." with an Account button that led to
the retired /account (404). Two causes: the client gated the whole learner UI on `is_admin` (static/orena/
main.js), and the notice linked to a route the server no longer has. The server never gated learners; these
tests pin that, keep Admin authorization separate, and keep /account retired.
"""
from __future__ import annotations

import asyncio
import base64
import json
import re
import time
from pathlib import Path

import httpx
from itsdangerous import TimestampSigner

import app as app_module
import auth_support
from writing_coach.core import deployment

ROOT = Path(__file__).resolve().parents[1]
LEARNER = {"google_sub": "staging-learner", "email": "learner@example.com", "name": "Linh", "role": "user"}


class _AnHourAgo(TimestampSigner):
    def get_timestamp(self) -> int:
        return int(time.time()) - 3600


def _cookie(**values: str) -> str:
    encoded = base64.b64encode(json.dumps(values).encode("utf-8"))
    return _AnHourAgo(auth_support.SESSION_SECRET or "local-single-user-mode").sign(encoded).decode("utf-8")


def _staging(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setattr(auth_support, "AUTH_ENABLED", True)
    monkeypatch.setattr(auth_support, "APP_ENV", "staging")
    monkeypatch.setattr(auth_support, "LOCAL_ADMIN_ALLOWED", False)
    monkeypatch.setattr(auth_support, "auth_user", lambda sub: LEARNER if sub == LEARNER["google_sub"] else None)
    monkeypatch.setattr(auth_support, "ensure_user_db", lambda: None)


def _get(path: str, signed_in: bool = True) -> httpx.Response:
    async def run():
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            if signed_in:
                client.cookies.set("writing_coach_session", _cookie(user_sub=LEARNER["google_sub"], language="en"))
            return await client.get(path)

    return asyncio.run(run())


def test_staging_is_a_public_environment() -> None:
    assert deployment.is_public_environment("staging")


def test_me_and_bootstrap_describe_a_plain_learner_without_any_review_flag(monkeypatch) -> None:
    _staging(monkeypatch)
    me = _get("/api/me")
    assert me.status_code == 200
    body = me.json()
    assert body["authenticated"] is True and body["role"] == "user" and body["is_admin"] is False
    assert not [key for key in body if "review" in key or "limited" in key or "internal" in key]

    boot = _get("/api/session/bootstrap")
    assert boot.status_code == 200
    payload = boot.json()
    assert payload["user"] == {"role": "user", "is_admin": False}
    assert payload["authenticated"] is True
    # The entry rule reads `language.stored`: a new account has none (-> Onboarding), nothing else gates it.
    assert "stored" in payload["language"]
    assert not [key for key in payload if "review" in key or "limited" in key or "internal" in key]


def test_learner_routes_are_allowed_for_a_non_admin_on_staging(monkeypatch) -> None:
    _staging(monkeypatch)
    for path in ("/api/me", "/api/session/bootstrap", "/api/learner-profile", "/api/account-settings"):
        response = _get(path)
        assert response.status_code not in (401, 403), (path, response.status_code)


def test_admin_authorization_stays_separate_on_staging(monkeypatch) -> None:
    _staging(monkeypatch)
    for path in ("/api/admin/ai/config", "/api/admin/console/overview"):
        assert _get(path).status_code == 403, path
        assert _get(path, signed_in=False).status_code == 401, path


def test_the_learner_shell_is_served_at_root_and_account_stays_retired(monkeypatch) -> None:
    _staging(monkeypatch)
    root = _get("/", signed_in=False)
    assert root.status_code == 200
    assert _get("/account").status_code == 404
    assert _get("/account", signed_in=False).status_code in (301, 302, 307, 401, 404)
    assert not any(getattr(route, "path", "") == "/account" for route in app_module.app.routes)


def test_the_client_has_no_review_only_gate_and_no_account_link() -> None:
    main = (ROOT / "static/orena/main.js").read_text(encoding="utf-8")
    assert not re.search(r"if \(!learner\.isAdmin\) \{", main)  # no blanket non-admin gate
    assert "isAdmin && isAdminHash" in main  # only an admin address is role-gated
    copy = (ROOT / "static/orena/copy/shell.js").read_text(encoding="utf-8")
    assert "internal review" not in copy.lower() and "limited:" not in copy
    for path in (ROOT / "static/orena").rglob("*"):
        if path.suffix not in {".js", ".css", ".html"} or "vendor" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"""href=["']/account["']""", text), path
