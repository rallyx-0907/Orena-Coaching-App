"""The scoped machine credential for vocabulary ingestion (writing_coach/service_auth.py, issue #145).

What must hold, and is tested here:

- the token is scoped to POST /api/admin/vocabulary/preview and /import and nothing else: every other admin route,
  every learner route and every other method answers a token holder exactly as it answers nobody (401);
- a missing, wrong or revoked token is refused, and a wrong token never falls back to a session;
- nothing configured means the feature is off;
- the server keeps only a hash; it is compared by digest, in constant time;
- the session administrator is unchanged (an admin cookie still works, a learner cookie is still refused);
- authored vocabulary imported with the token still lands pending review, as an admin import does.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import inspect
import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

import app as app_module
import auth_support
from tests.test_admin_authorization_matrix import ACCOUNTS, ADMIN, LEARNER, _cookie
from writing_coach import media_library_api, reading_library_api, service_auth
from writing_coach.ai import platform

TOKEN = "unit-test-token-0123456789-abcdefghijklmnopqrstuvwxyz"
OTHER_TOKEN = "another-test-token-9876543210-zyxwvutsrqponmlkjihgfedcba"
PREVIEW = "/api/admin/vocabulary/preview"
IMPORT = "/api/admin/vocabulary/import"
SAMPLE = (Path(__file__).resolve().parents[1] / "docs" / "vocab" / "samples" / "en_resilient.json").read_bytes()


PUBLIC_API = {"/api/health", "/api/readiness", "/api/platform/languages", "/api/auth/native/exchange"}
PUBLIC_API_PREFIXES = ("/api/billing/webhooks/",)


def digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- the pure module


def test_configured_hashes_reads_only_well_formed_digests() -> None:
    good, other = digest(TOKEN), digest(OTHER_TOKEN)
    assert service_auth.configured_hashes({}) == ()
    assert service_auth.configured_hashes({service_auth.ENV_NAME: ""}) == ()
    assert service_auth.configured_hashes({service_auth.ENV_NAME: good}) == (good,)
    assert service_auth.configured_hashes({service_auth.ENV_NAME: f"{good}, {other.upper()}\n"}) == (good, other)
    # the raw token, a short value and a non-hex value are not digests: ignored, so a mistake fails closed
    assert service_auth.configured_hashes({service_auth.ENV_NAME: TOKEN}) == ()
    assert service_auth.configured_hashes({service_auth.ENV_NAME: "abc123"}) == ()
    assert service_auth.configured_hashes({service_auth.ENV_NAME: "g" * 64}) == ()


def test_token_matches_by_digest_for_any_configured_hash() -> None:
    hashes = (digest(TOKEN), digest(OTHER_TOKEN))
    assert service_auth.token_matches(TOKEN, hashes)
    assert service_auth.token_matches(OTHER_TOKEN, hashes)  # rotation: both are accepted while both are configured
    assert not service_auth.token_matches(TOKEN + "x", hashes)
    assert not service_auth.token_matches("", hashes)
    assert not service_auth.token_matches(TOKEN, ())
    assert not service_auth.token_matches(digest(TOKEN), hashes), "the hash itself is not the credential"


def test_the_comparison_is_constant_time_and_compares_every_hash() -> None:
    source = inspect.getsource(service_auth.token_matches)
    assert "hmac.compare_digest" in source and "return matched" in source
    assert "==" not in source, "a digest must never be compared with =="
    assert hmac.compare_digest(digest(TOKEN), digest(TOKEN))


def test_bearer_token_parsing() -> None:
    assert service_auth.bearer_token({"authorization": f"Bearer {TOKEN}"}) == TOKEN
    assert service_auth.bearer_token({"authorization": f"bearer   {TOKEN} "}) == TOKEN
    assert service_auth.bearer_token({"authorization": f"Basic {TOKEN}"}) == ""
    assert service_auth.bearer_token({"authorization": "Bearer "}) == ""
    assert service_auth.bearer_token({}) == ""


def test_scope_is_exactly_two_post_routes_with_a_bearer_header() -> None:
    bearer = {"authorization": f"Bearer {TOKEN}"}
    assert service_auth.VOCABULARY_INGEST_PATHS == {PREVIEW, IMPORT}
    for path in (PREVIEW, IMPORT):
        assert service_auth.is_vocabulary_ingest_request("POST", path, bearer)
        assert not service_auth.is_vocabulary_ingest_request("GET", path, bearer)
        assert not service_auth.is_vocabulary_ingest_request("POST", path, {})
        assert not service_auth.is_vocabulary_ingest_request("POST", path + "/", bearer)
    for path in ("/api/admin/ai/config", "/api/admin/console/overview", "/api/me", "/api/admin/vocabulary/preview2"):
        assert not service_auth.is_vocabulary_ingest_request("POST", path, bearer)


def test_a_service_request_runs_under_a_key_of_its_own_never_the_legacy_scope() -> None:
    assert service_auth.SERVICE_USER_KEY not in {"", "legacy"}
    source = inspect.getsource(auth_support.UserIsolationMiddleware._serve_vocabulary_ingest)
    assert "_user_key.set(service_auth.SERVICE_USER_KEY)" in source and "ensure_user_db" not in source


def test_the_module_logs_and_prints_nothing() -> None:
    source = inspect.getsource(service_auth)
    assert "logging" not in source and "print(" not in source and "logger" not in source


# ---------------------------------------------------------------- through the real app (sign-in on)


@pytest.fixture
def secured(monkeypatch):
    """The app with Google sign-in on and two known accounts - the same set-up as the admin authorization matrix."""
    monkeypatch.setattr(auth_support, "AUTH_ENABLED", True)
    monkeypatch.setattr(auth_support, "auth_user", lambda sub: ACCOUNTS.get(sub))
    monkeypatch.setattr(auth_support, "ensure_user_db", lambda: None)
    monkeypatch.setattr(platform, "_admin_guard", auth_support.require_admin)
    monkeypatch.setattr(media_library_api, "_admin_guard", auth_support.require_admin)
    monkeypatch.setattr(reading_library_api, "_admin_guard", auth_support.require_admin)
    app_module.configure_admin_console_from_runtime()
    monkeypatch.setattr(platform, "providers", lambda: {})
    return app_module.app


@pytest.fixture
def repository(tmp_path, monkeypatch):
    from writing_coach.persistence.vocabulary_repository import sqlite_vocabulary_repository

    repo = sqlite_vocabulary_repository(tmp_path / "vocabulary.db")
    repo.initialize()
    monkeypatch.setattr(app_module, "_persistence_runtime", replace(app_module._persistence_runtime, vocabulary_repository=repo))
    app_module.configure_becoming_library_content(repo)
    return repo


@pytest.fixture
def token_on(monkeypatch):
    monkeypatch.setenv(service_auth.ENV_NAME, digest(TOKEN))


def call(app, method: str, path: str, *, token: str | None = None, who: dict | None = None, **kwargs) -> httpx.Response:
    headers = dict(kwargs.pop("headers", {}))
    if token is not None:
        headers["authorization"] = f"Bearer {token}"
    if who is not None:
        headers["cookie"] = f"writing_coach_session={_cookie(who['google_sub'])}"

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            return await client.request(method, path, headers=headers, **kwargs)

    return asyncio.run(run())


def sample_file(name: str = "en_resilient.json"):
    return [("files", (name, SAMPLE, "application/json"))]


def import_data() -> dict:
    return {
        "metadata": json.dumps({
            "title": "ingest", "language_code": "en", "collection_id": "t-ingest",
            "rights_status": "unknown", "completeness": "partial",
        }),
        "duplicates": "skip",
    }


def test_a_valid_token_previews_and_imports_pending_review(secured, repository, token_on) -> None:
    preview = call(secured, "POST", PREVIEW, token=TOKEN, files=sample_file())
    assert preview.status_code == 200, preview.text
    row = preview.json()["items"][0]["authored"]["rows"][0]
    assert row["outcome"] == "ready" and row["existing"] == "new"

    imported = call(secured, "POST", IMPORT, token=TOKEN, files=sample_file(), data=import_data())
    assert imported.status_code == 200, imported.text
    body = imported.json()
    assert body["collection"]["catalog_status"] == "pending_review"
    assert body["items"][0]["imported"] == 1 and body["items"][0]["failed"] == 0
    assert repository.get_collection("t-ingest", limit=5) is None, "a token import is never visible to learners"
    stored = repository.get_collection("t-ingest", limit=5, status=None)
    assert stored["catalog_status"] == "pending_review" and len(stored["entries"]) == 1


def test_a_published_token_import_is_impossible(secured, repository, token_on) -> None:
    data = import_data()
    data["metadata"] = json.dumps({**json.loads(data["metadata"]), "publish": True, "publication_attested": True,
                                   "rights_status": "licensed", "completeness": "complete"})
    imported = call(secured, "POST", IMPORT, token=TOKEN, files=sample_file(), data=data)
    assert imported.status_code == 200, imported.text
    assert imported.json()["collection"]["catalog_status"] == "pending_review", "authored entries never publish at import (D-178)"


@pytest.mark.parametrize("path", [PREVIEW, IMPORT])
def test_missing_wrong_and_unconfigured_tokens_are_refused(secured, repository, monkeypatch, path) -> None:
    extra = {"data": import_data()} if path == IMPORT else {}
    # nothing configured: the feature is off, whatever a client sends
    monkeypatch.delenv(service_auth.ENV_NAME, raising=False)
    off = call(secured, "POST", path, token=TOKEN, files=sample_file(), **extra)
    assert off.status_code == 401 and off.json() == {"detail": "Invalid service token"}
    monkeypatch.setenv(service_auth.ENV_NAME, digest(TOKEN))
    # no credential at all: exactly the answer nobody gets today
    anonymous = call(secured, "POST", path, files=sample_file(), **extra)
    assert anonymous.status_code == 401 and anonymous.json() == {"detail": "Authentication required"}
    # a wrong token is refused outright and never falls back to a session
    wrong = call(secured, "POST", path, token=OTHER_TOKEN, files=sample_file(), **extra)
    assert wrong.status_code == 401 and wrong.json() == {"detail": "Invalid service token"}
    wrong_with_admin_session = call(secured, "POST", path, token=OTHER_TOKEN, who=ADMIN, files=sample_file(), **extra)
    assert wrong_with_admin_session.status_code == 401
    # the digest is not the credential
    assert call(secured, "POST", path, token=digest(TOKEN), files=sample_file(), **extra).status_code == 401


def test_revoking_a_token_takes_effect_at_the_next_request(secured, repository, monkeypatch) -> None:
    monkeypatch.setenv(service_auth.ENV_NAME, f"{digest(TOKEN)},{digest(OTHER_TOKEN)}")
    assert call(secured, "POST", PREVIEW, token=TOKEN, files=sample_file()).status_code == 200
    assert call(secured, "POST", PREVIEW, token=OTHER_TOKEN, files=sample_file()).status_code == 200
    monkeypatch.setenv(service_auth.ENV_NAME, digest(OTHER_TOKEN))  # the first token is revoked
    assert call(secured, "POST", PREVIEW, token=TOKEN, files=sample_file()).status_code == 401
    assert call(secured, "POST", PREVIEW, token=OTHER_TOKEN, files=sample_file()).status_code == 200


def test_the_token_reaches_no_other_route_and_no_other_method(secured, repository, token_on) -> None:
    paths = secured.openapi()["paths"]
    checked = 0
    for template, operations in sorted(paths.items()):
        for method in operations:
            method = method.upper()
            if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                continue
            if method == "POST" and template in service_auth.VOCABULARY_INGEST_PATHS:
                continue
            path = template
            while "{" in path:
                start = path.index("{")
                path = path[:start] + "x" + path[path.index("}") + 1:]
            if not path.startswith("/api/") or path in PUBLIC_API or path.startswith(PUBLIC_API_PREFIXES):
                continue
            headers = {"origin": "http://testserver"} if method != "GET" else {}
            response = call(secured, method, path, token=TOKEN, headers=headers)
            assert response.status_code == 401, (method, template, response.status_code, "a token holder is signed in nowhere")
            checked += 1
    assert checked > 50
    # the other vocabulary admin methods on the same paths are not the scoped operation either
    assert call(secured, "GET", PREVIEW, token=TOKEN).status_code in {401, 405}


def test_the_token_is_no_substitute_for_a_session_on_the_admin_console(secured, token_on) -> None:
    for path in ("/api/admin/console/overview", "/api/admin/ai/config", "/api/admin/ai/credentials", "/api/me"):
        response = call(secured, "GET", path, token=TOKEN)
        assert response.status_code == 401, (path, response.status_code)


def test_session_admin_is_unchanged(secured, repository, monkeypatch) -> None:
    monkeypatch.delenv(service_auth.ENV_NAME, raising=False)  # with no token configured at all
    assert call(secured, "POST", PREVIEW, who=ADMIN, files=sample_file(), headers={"origin": "http://testserver"}).status_code == 200
    learner = call(secured, "POST", PREVIEW, who=LEARNER, files=sample_file(), headers={"origin": "http://testserver"})
    assert learner.status_code == 403 and "Platform administrator" in learner.text
    anonymous = call(secured, "POST", PREVIEW, files=sample_file(), headers={"origin": "http://testserver"})
    assert anonymous.status_code == 401 and anonymous.json() == {"detail": "Authentication required"}
    imported = call(secured, "POST", IMPORT, who=ADMIN, files=sample_file(), data=import_data(), headers={"origin": "http://testserver"})
    assert imported.status_code == 200 and imported.json()["collection"]["catalog_status"] == "pending_review"


def test_a_learner_session_with_a_token_header_is_still_a_learner(secured, repository, token_on) -> None:
    # A valid token on a request makes it the service request, whatever cookie rides along; the cookie grants nothing here.
    response = call(secured, "POST", "/api/admin/ai/config", token=TOKEN, who=LEARNER, headers={"origin": "http://testserver"})
    assert response.status_code in {403, 405, 422}
    assert call(secured, "GET", "/api/admin/ai/config", token=TOKEN, who=LEARNER).status_code == 403


def test_the_routes_ask_the_scoped_guard_and_the_guard_falls_back_to_the_admin_session() -> None:
    assert "require_vocabulary_ingest(request)" in inspect.getsource(app_module.admin_vocabulary_source_preview)
    assert "require_vocabulary_ingest(request)" in inspect.getsource(app_module.admin_vocabulary_source_import)
    assert "return require_admin(request)" in inspect.getsource(auth_support.require_vocabulary_ingest)
    # no other route in the app uses the scoped guard
    source = inspect.getsource(app_module)
    assert source.count("require_vocabulary_ingest(request)") == 2
