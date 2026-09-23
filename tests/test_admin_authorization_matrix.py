"""Every admin route the app serves, called as nobody, as a learner and as an administrator.

The routes are read from the application itself, so a new admin route cannot
be added without being placed in this matrix. Each is called through the real
session middleware and the real admin guard, with a body the route would
accept, so it is the guard - not request validation - that turns a learner
away. An anonymous caller is stopped before any route runs; a learner is
refused by the route; an administrator reaches the route and gets what it was
designed to answer on the hermetic test backend.
"""
from __future__ import annotations

import asyncio
import base64
import inspect
import json

import httpx
import pytest
from itsdangerous import TimestampSigner

import app as app_module
import auth_support
from writing_coach import media_library_api, reading_library_api
from writing_coach.ai import platform

LEARNER = {"google_sub": "matrix-learner", "email": "learner@example.com", "name": "Learner", "role": "user"}
ADMIN = {"google_sub": "matrix-admin", "email": "admin@example.com", "name": "Admin", "role": "admin"}
ACCOUNTS = {user["google_sub"]: user for user in (LEARNER, ADMIN)}

BOOK = "9d0c5b2e-4a3c-4d1e-9a52-7a7b9b1d2c3e"
ARTICLE = "5b8d2c1a-7e34-4f0b-9c6d-1a2b3c4d5e6f"
TARGET = "7c9e4a2b-1d58-4b6f-8e0a-2b3c4d5e6f70"
ACCOUNT = "3f1d2c4b-5a69-4e7f-8a9b-0c1d2e3f4a5b"
UNREADABLE_MEDIA_URL = "ftp://media.example/clip.mp3"  # refused before any network use
CSV = ("files", ("words.csv", b"term,meaning\nagenda,plan\n", "text/csv"))
EPUB = ("files", ("book.epub", b"not an epub", "application/epub+zip"))
MEDIA_FILE = ("file", ("clip.wav", b"not media at all", "audio/wav"))
ROUTE = {"enabled": True, "provider": "no-such-provider", "model": "m"}

# (method, path template) -> (concrete path, request body, statuses an administrator may get)
MATRIX = {
    ("GET", "/api/admin/ai/catalog"): ("/api/admin/ai/catalog", {}, {200}),
    ("GET", "/api/admin/ai/config"): ("/api/admin/ai/config", {}, {200}),
    ("PUT", "/api/admin/ai/config"): ("/api/admin/ai/config", {"json": {"provider": "no-such", "model": "m"}}, {400}),
    ("PUT", "/api/admin/ai/config/{capability_key}"): ("/api/admin/ai/config/learner_dictionary", {"json": ROUTE}, {400}),
    ("GET", "/api/admin/ai/credentials"): ("/api/admin/ai/credentials", {}, {200}),
    ("DELETE", "/api/admin/ai/credentials/{provider_id}"): ("/api/admin/ai/credentials/groq", {}, {404}),
    ("PUT", "/api/admin/ai/credentials/{provider_id}"): (
        "/api/admin/ai/credentials/groq", {"json": {"api_key": "sk-matrix", "models": ["m"], "default_model": "m"}}, {404}),
    ("POST", "/api/admin/ai/credentials/{provider_id}/test"): (
        "/api/admin/ai/credentials/groq/test", {"json": {"api_key": "sk-matrix"}}, {404}),
    ("GET", "/api/admin/ai/operations"): ("/api/admin/ai/operations", {}, {200}),
    ("POST", "/api/admin/ai/test"): ("/api/admin/ai/test", {"json": {"provider": "no-such", "model": "m"}}, {400}),
    ("POST", "/api/admin/ai/test/{capability_key}"): ("/api/admin/ai/test/learner_dictionary", {}, {404, 409}),
    ("GET", "/api/admin/console/overview"): ("/api/admin/console/overview", {}, {200}),
    ("GET", "/api/admin/console/users/summary"): ("/api/admin/console/users/summary", {}, {200}),
    ("GET", "/api/admin/console/users"): ("/api/admin/console/users", {}, {200}),
    ("GET", "/api/admin/console/users/{user_id}"): (f"/api/admin/console/users/{ACCOUNT}", {}, {404, 503}),
    ("GET", "/api/admin/console/content"): ("/api/admin/console/content", {}, {200}),
    ("GET", "/api/admin/console/content/{kind}/{content_id}"): (f"/api/admin/console/content/book/{BOOK}", {}, {404}),
    ("GET", "/api/admin/console/imports/history"): ("/api/admin/console/imports/history", {}, {200}),
    ("GET", "/api/admin/console/runtime"): ("/api/admin/console/runtime", {}, {200}),
    ("POST", "/api/admin/console/content/book/{book_id}/archive"): (
        f"/api/admin/console/content/book/{BOOK}/archive", {}, {404, 503}),
    ("POST", "/api/admin/console/content/vocabulary/{collection_id}/publish"): (
        "/api/admin/console/content/vocabulary/hsk1/publish",
        {"json": {"rights_status": "licensed", "completeness": "complete", "attested": True}}, {422, 503}),
    ("POST", "/api/admin/console/content/media/{media_id}/reprocess"): (
        "/api/admin/console/content/media/youtube-abcdefghijk/reprocess", {}, {404}),
    ("POST", "/api/admin/console/imports/books"): (
        "/api/admin/console/imports/books", {"files": [EPUB], "data": {"learning_language": "en"}}, {200, 503}),
    ("POST", "/api/admin/console/imports/media"): (
        "/api/admin/console/imports/media", {"json": {"language": "en", "items": [{"url": UNREADABLE_MEDIA_URL}]}}, {200, 503}),
    ("POST", "/api/admin/console/imports/media-upload"): (
        "/api/admin/console/imports/media-upload", {"files": [MEDIA_FILE], "data": {"language": "en"}}, {200, 503}),
    ("POST", "/api/admin/vocabulary/preview"): ("/api/admin/vocabulary/preview", {"files": [CSV]}, {200}),
    # The route's own validation answers after the guard, so the matrix writes nothing.
    ("POST", "/api/admin/vocabulary/import"): (
        "/api/admin/vocabulary/import", {"files": [CSV], "data": {"metadata": json.dumps({"language_code": "en"})}}, {422}),
    ("POST", "/api/media/admin/preview"): (
        "/api/media/admin/preview", {"json": {"urls": [UNREADABLE_MEDIA_URL], "language": "en"}}, {200, 503}),
    ("POST", "/api/media/admin/import"): (
        "/api/media/admin/import", {"json": {"language": "en", "items": [{"url": UNREADABLE_MEDIA_URL}]}}, {200, 503}),
    ("POST", "/api/media/admin/upload"): ("/api/media/admin/upload", {"files": [MEDIA_FILE], "data": {"language": "en"}}, {200, 503}),
    ("GET", "/api/media/admin/library"): ("/api/media/admin/library", {}, {200, 503}),
    ("GET", "/api/product/admin/account"): ("/api/product/admin/account", {}, {200}),
    ("GET", "/api/admin/readiness-summary"): ("/api/admin/readiness-summary", {}, {200}),
    ("GET", "/api/admin/product-activity"): ("/api/admin/product-activity", {}, {200}),
    # Admin-only although their paths do not say so.
    ("POST", "/api/reading/library/import"): (
        "/api/reading/library/import", {"files": [EPUB], "data": {"learning_language": "en"}}, {503}),
    ("POST", "/api/reading/library/books/{book_id}/archive"): (f"/api/reading/library/books/{BOOK}/archive", {}, {503}),
    # Reading Content Engine. The runtime this suite builds is SQLite, so the
    # engine is unconfigured and answers 503 - which is the point: the guard
    # still runs first, so anonymous is 401 and a learner is 403 before the
    # engine ever reports that it is inactive.
    ("GET", "/api/admin/reading/sources"): ("/api/admin/reading/sources", {}, {200, 503}),
    ("POST", "/api/admin/reading/sources"): (
        "/api/admin/reading/sources",
        {"json": {"slug": "matrix-source", "name": "Matrix", "source_type": "rss", "languages": ["en"]}},
        {201, 503},
    ),
    ("POST", "/api/admin/reading/sources/{source_id}"): (
        f"/api/admin/reading/sources/{ARTICLE}", {"json": {"state": "paused"}}, {404, 503}),
    ("GET", "/api/admin/reading/queue"): ("/api/admin/reading/queue", {}, {200, 503}),
    ("GET", "/api/admin/reading/jobs"): ("/api/admin/reading/jobs", {}, {200, 503}),
    ("POST", "/api/admin/reading/jobs"): (
        "/api/admin/reading/jobs", {"data": {"kind": "text", "text": "A pasted paragraph."}}, {202, 422, 503}),
    ("GET", "/api/admin/reading/jobs/{job_id}"): (f"/api/admin/reading/jobs/{ARTICLE}", {}, {404, 503}),
    ("POST", "/api/admin/reading/jobs/{job_id}/retry"): (
        f"/api/admin/reading/jobs/{ARTICLE}/retry", {}, {409, 503}),
    ("GET", "/api/admin/reading/articles/{article_id}"): (
        f"/api/admin/reading/articles/{ARTICLE}", {}, {404, 503}),
    ("POST", "/api/admin/reading/articles/{article_id}"): (
        f"/api/admin/reading/articles/{ARTICLE}", {"json": {"topic": "environment"}}, {404, 503}),
    ("POST", "/api/admin/reading/articles/{article_id}/status"): (
        f"/api/admin/reading/articles/{ARTICLE}/status", {"json": {"status": "published"}}, {404, 503}),
    ("POST", "/api/admin/reading/articles/{article_id}/targets"): (
        f"/api/admin/reading/articles/{ARTICLE}/targets", {"json": {"text": "higher ground"}}, {404, 503}),
    ("POST", "/api/admin/reading/articles/{article_id}/targets/{target_id}"): (
        f"/api/admin/reading/articles/{ARTICLE}/targets/{TARGET}", {"json": {"approved": True}}, {404, 503}),
    ("GET", "/api/admin/reading/operations"): ("/api/admin/reading/operations", {}, {200, 503}),
}
ADMIN_ONLY_WITHOUT_ADMIN_IN_PATH = {
    ("POST", "/api/reading/library/import"),
    ("POST", "/api/reading/library/books/{book_id}/archive"),
}


def _cookie(user_sub: str) -> str:
    encoded = base64.b64encode(json.dumps({"user_sub": user_sub}).encode("utf-8"))
    return TimestampSigner(auth_support.SESSION_SECRET or "local-single-user-mode").sign(encoded).decode("utf-8")


@pytest.fixture()
def secured(monkeypatch):
    """The app with Google sign-in on, two known accounts and the real guard."""
    monkeypatch.setattr(auth_support, "AUTH_ENABLED", True)
    monkeypatch.setattr(auth_support, "auth_user", lambda sub: ACCOUNTS.get(sub))
    monkeypatch.setattr(auth_support, "ensure_user_db", lambda: None)
    # Other suites install fakes into these module seams; put back the app's own.
    monkeypatch.setattr(platform, "_admin_guard", auth_support.require_admin)
    monkeypatch.setattr(media_library_api, "_admin_guard", auth_support.require_admin)
    monkeypatch.setattr(reading_library_api, "_admin_guard", auth_support.require_admin)
    app_module.configure_admin_console_from_runtime()
    # No provider is contacted: the provider-backed rows answer from an empty registry.
    monkeypatch.setattr(platform, "providers", lambda: {})
    return app_module.app


def _admin_routes() -> set[tuple[str, str]]:
    paths = app_module.app.openapi()["paths"]
    found = {(method.upper(), path) for path, operations in paths.items() for method in operations if "/admin" in path}
    return found | ADMIN_ONLY_WITHOUT_ADMIN_IN_PATH


def _request(app, method: str, path: str, body: dict, who: dict | None) -> httpx.Response:
    headers = {"origin": "http://testserver"} if method != "GET" else {}
    if who is not None:
        headers["cookie"] = f"writing_coach_session={_cookie(who['google_sub'])}"

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            return await client.request(method, path, headers=headers, **body)

    return asyncio.run(run())


def test_the_matrix_covers_every_admin_route_the_app_serves():
    routes = _admin_routes()
    assert routes == set(MATRIX), f"unclassified: {sorted(routes - set(MATRIX))}; stale: {sorted(set(MATRIX) - routes)}"
    assert len(routes) == 50


@pytest.mark.parametrize("route", sorted(MATRIX), ids=lambda route: f"{route[0]} {route[1]}")
def test_nobody_is_stopped_before_the_route(secured, route):
    path, body, _admin_statuses = MATRIX[route]
    response = _request(secured, route[0], path, body, None)
    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


@pytest.mark.parametrize("route", sorted(MATRIX), ids=lambda route: f"{route[0]} {route[1]}")
def test_a_learner_is_refused_by_the_route(secured, route):
    path, body, _admin_statuses = MATRIX[route]
    response = _request(secured, route[0], path, body, LEARNER)
    assert response.status_code == 403, response.text
    assert set(response.json()) == {"detail"}
    assert "Platform administrator" in json.dumps(response.json())


@pytest.mark.parametrize("route", sorted(MATRIX), ids=lambda route: f"{route[0]} {route[1]}")
def test_an_administrator_reaches_what_the_route_was_built_to_answer(secured, route):
    path, body, admin_statuses = MATRIX[route]
    response = _request(secured, route[0], path, body, ADMIN)
    assert response.status_code in admin_statuses, (route, response.status_code, response.text[:300])
    assert "sk-matrix" not in response.text


def test_every_admin_seam_is_wired_to_the_one_guard():
    source = inspect.getsource(app_module)
    assert "install_platform_ai(app, require_admin)" in source
    assert source.count("admin_guard=require_admin") >= 3  # media library, reading library, console
    assert "require_admin(request)" in inspect.getsource(app_module.admin_readiness_summary)
    assert "require_admin(request)" in inspect.getsource(app_module.admin_vocabulary_source_preview)
    assert "require_admin(request)" in inspect.getsource(app_module.admin_vocabulary_source_import)
