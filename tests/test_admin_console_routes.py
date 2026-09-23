"""HTTP boundary of the Platform Admin control center.

The console is mounted on its own small app here with a fake guard and a real
SQLite schema, so each rule is checked at the boundary an operator's browser
actually crosses: who may call it, what leaves the server, and what is recorded.
"""
import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from writing_coach import admin_console_api as console
from writing_coach import reading_library_api
from writing_coach.media_library_store import FileMediaLibraryStore, MediaLibraryEntry
from writing_coach.persistence.admin_repository import AdminConsoleRepository
from writing_coach.persistence.models import AuditLog, Base, Essay, User, UserLanguageProfile, VocabularyCollection

NOW = datetime.now(UTC)
ADMIN = {"google_sub": "sub-admin", "email": "admin@example.com", "role": "admin"}


def guard(request):
    if request.headers.get("x-test-admin") != "1":
        raise HTTPException(403, "Platform administrator access required")
    return ADMIN


class PlatformRepo:
    def list_capability_configs(self):
        return []

    def get_capability_config(self, _key):
        return None

    def get_ai_selection(self):
        return None

    def get_provider_credential(self, _provider):
        return None

    def list_ai_operation_events(self, _limit=100):
        return []


class VocabularyRepo:
    def __init__(self):
        self.published = []

    def available(self):
        return True

    def finalize_collection_publication(self, collection_id, *, admission):
        if admission.get("rights_status") not in {"public_domain", "licensed", "creator_authorized", "internal_curated"}:
            raise ValueError("A vocabulary collection needs an approved rights/completeness admission.")
        self.published.append((collection_id, dict(admission)))
        return {"id": collection_id, "catalog_status": "published"}

    def list_entries(self, collection_id, *, search="", level="", limit=100, offset=0):
        return ([{"term": "agenda", "readings": [], "pronunciations": [{"text": "/əˈdʒendə/"}],
                  "short_meanings": [{"language": "vi", "text": "chương trình"}], "level": "B1", "part_of_speech": "noun"}], 1)


class ReadingRepo:
    def __init__(self):
        self.archived = []

    def archive_book(self, book_id):
        self.archived.append(book_id)
        return True


@pytest.fixture()
def setup(tmp_path):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    learner = uuid.uuid4()
    with Session(engine) as session, session.begin():
        session.add(User(id=uuid.uuid4(), user_key="sub-admin", email="admin@example.com", name="Admin", role="admin",
                         created_at=NOW - timedelta(days=100)))
        session.add(User(id=learner, user_key="sub-learner", email="learner.one@example.com", name="Learner One",
                         role="user", created_at=NOW - timedelta(days=2)))
        session.add(UserLanguageProfile(id=uuid.uuid4(), user_id=learner, language_code="zh", created_at=NOW, updated_at=NOW))
        session.add(Essay(id=uuid.uuid4(), user_id=learner, language_code="zh", legacy_id=1,
                          created_at=NOW - timedelta(hours=1), text="PRIVATE-ESSAY-TEXT"))
        session.add(VocabularyCollection(id="hsk1", language_code="zh", title="HSK 1", framework="HSK", level="HSK1",
                                         catalog_status="pending_review", origin="imported", provenance={},
                                         created_at=NOW, updated_at=NOW))
    store = FileMediaLibraryStore(tmp_path / "media")
    store.upsert(MediaLibraryEntry(
        media_id="youtube-abcdefghijk", media_type="video", provider="youtube", provider_media_id="abcdefghijk",
        canonical_url="https://www.youtube.com/watch?v=abcdefghijk",
        playback={"provider": "youtube", "kind": "embed", "url": "https://www.youtube-nocookie.com/embed/abcdefghijk"},
        title="Station announcements", thumbnail={"kind": "none", "ref": ""}, duration_ms=42000, language="zh", level="",
        creator="", source={"provider": "youtube", "type": "admin-import", "provenance_url": "https://www.youtube.com/watch?v=abcdefghijk",
                            "license": "x", "review_status": "checked", "imported_by": "admin@example.com"},
        library="shared", created_at=(NOW - timedelta(days=1)).isoformat(), lesson=None,
    ))
    vocabulary, reading = VocabularyRepo(), ReadingRepo()
    console.configure_admin_console(
        admin_guard=guard,
        backend="postgresql",
        repository=AdminConsoleRepository(engine),
        platform_repository=PlatformRepo(),
        vocabulary_repository=vocabulary,
        media_store=store,
        reading_repository=reading,
        runtime_services={"media_translation": {"engine": "local_marian", "model": "opus-mt-v1", "configured": True}},
        runtime_facts=lambda: {"schema": {"state": "ready", "current": "20260916_0009", "expected": "20260916_0009"},
                               "account_backbone": "active"},
        app_version="test",
    )
    app = FastAPI()
    app.include_router(console.router)
    yield {"app": app, "engine": engine, "learner": learner, "vocabulary": vocabulary, "reading": reading, "store": store}
    console.configure_admin_console(admin_guard=None)


def call(app, method, path, admin=True, origin="http://testserver", **kwargs):
    """One request as the console page makes it: a browser attaches Origin to
    every request that changes something, and the console requires it."""
    headers = {"x-test-admin": "1"} if admin else {}
    if origin and method.upper() != "GET":
        headers["origin"] = origin
    headers.update(kwargs.pop("headers", None) or {})

    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, headers=headers, **kwargs)
    return asyncio.run(run())


READ_ROUTES = ["/overview", "/users/summary", "/users", "/content", "/imports/history", "/runtime"]


def test_every_console_route_requires_an_administrator(setup):
    for path in READ_ROUTES:
        assert call(setup["app"], "GET", f"/api/admin/console{path}", admin=False).status_code == 403, path
    assert call(setup["app"], "POST", "/api/admin/console/content/book/x/archive", admin=False).status_code == 403


def test_overview_reports_stored_facts_and_never_learner_text(setup):
    response = call(setup["app"], "GET", "/api/admin/console/overview")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["accounts"]["total"] == 2
    assert body["accounts"]["new_7d"] == 1
    assert len(body["accounts"]["registrations"]) == 30
    assert body["activity"]["active_7d"] == 1
    assert body["activity"]["new_7d"] == 1
    assert body["activity"]["returning_7d"] == 0
    assert {row["domain"]: row["events"] for row in body["activity"]["domains"]}["writing"] == 1
    assert body["languages"]["profiles"] == [{"language": "zh", "learners": 1}]
    assert body["content"]["media"]["transcript_missing"] == 1
    assert body["content"]["vocabulary"]["draft"] == 1
    kinds = [item["kind"] for item in body["attention"]]
    assert "transcript_missing" in kinds and "content_waiting" in kinds
    assert body["ai"]["runtime_mode"] in {"legacy", "capability"}
    # Provider display names come from the provider registry, not the browser.
    assert body["ai"]["provider_names"]["ollama"] == "Ollama"
    assert "PRIVATE-ESSAY-TEXT" not in response.text
    assert "learner.one@example.com" not in response.text


def test_users_are_listed_with_masked_identity_and_every_read_is_audited(setup):
    listed = call(setup["app"], "GET", "/api/admin/console/users?q=learner")
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    assert body["items"][0]["email_masked"] == "le•••@example.com"
    assert "learner.one@example.com" not in listed.text

    detail = call(setup["app"], "GET", f"/api/admin/console/users/{setup['learner']}")
    assert detail.status_code == 200
    assert detail.json()["email"] == "learner.one@example.com"
    assert "PRIVATE-ESSAY-TEXT" not in detail.text
    assert call(setup["app"], "GET", f"/api/admin/console/users/{uuid.uuid4()}").status_code == 404

    with Session(setup["engine"]) as session:
        actions = [row.action for row in session.query(AuditLog).order_by(AuditLog.created_at).all()]
        view = session.query(AuditLog).filter(AuditLog.action == "admin.account.view").one()
        listing = session.query(AuditLog).filter(AuditLog.action == "admin.accounts.list").one()
    assert actions[:2] == ["admin.accounts.list", "admin.account.view"]
    assert view.entity_id == str(setup["learner"])
    # The search text may be an address; the record keeps only that a search ran.
    assert listing.payload["filters"]["query"] is True
    assert "learner" not in repr(listing.payload)


def test_users_summary_reports_retention_as_insufficient_on_a_small_sample(setup):
    body = call(setup["app"], "GET", "/api/admin/console/users/summary").json()
    assert [window["days"] for window in body["retention"]] == [1, 7, 30]
    assert all(window["state"] == "insufficient" and window["rate_percent"] is None for window in body["retention"])
    assert body["level"] == {"state": "not_recorded"}
    assert body["segments_30d"] == {"active": 1, "new": 1, "returning": 0}


def test_content_library_lists_all_three_domains_with_counts_and_filters(setup):
    body = call(setup["app"], "GET", "/api/admin/console/content").json()
    assert body["sources"]["book"] == "unavailable"
    assert body["counts"]["vocabulary"] == 1
    assert body["counts"]["media"] >= 1
    media = call(setup["app"], "GET", "/api/admin/console/content?kind=media&status=issues").json()
    assert [item["id"] for item in media["items"]] == ["youtube-abcdefghijk"]
    # A published item offers the two ways off the shelf; neither destroys it.
    assert media["items"][0]["actions"] == ["preview", "reprocess", "unpublish", "archive"]
    vocabulary = call(setup["app"], "GET", "/api/admin/console/content?kind=vocabulary").json()
    assert vocabulary["items"][0]["actions"] == ["preview", "publish"]


def test_content_preview_returns_domain_detail(setup):
    media = call(setup["app"], "GET", "/api/admin/console/content/media/youtube-abcdefghijk").json()
    assert media["record"]["title"] == "Station announcements"
    assert media["transcript"] == {"segment_count": 0, "segments": []}
    assert media["learner_link"] == "#/encounter?id=media%3Ayoutube-abcdefghijk&intent=follow"
    vocabulary = call(setup["app"], "GET", "/api/admin/console/content/vocabulary/hsk1").json()
    assert vocabulary["entries"][0]["term"] == "agenda"
    assert vocabulary["entries"][0]["meaning"] == "chương trình"
    assert call(setup["app"], "GET", "/api/admin/console/content/media/nope").status_code == 404


def test_media_can_be_taken_back_and_put_out_again(setup):
    """The lifecycle an operator actually needs, and no destruction in it."""
    path = "/api/admin/console/content/media/youtube-abcdefghijk/status"
    store = setup["store"]
    off = call(setup["app"], "POST", path, json={"status": "unpublished"})
    assert off.status_code == 200 and off.json()["record"]["status"] == "unpublished"
    assert "republish" in off.json()["record"]["actions"]
    # Gone from what a learner may browse, entirely present for an operator.
    assert store.list(language="zh") == []
    assert [item.media_id for item in store.list(language="zh", status=None)] == ["youtube-abcdefghijk"]
    kept = store.get("youtube-abcdefghijk")
    assert kept.source["provenance_url"] and kept.canonical_url

    listed = call(setup["app"], "GET", "/api/admin/console/content?kind=media").json()
    assert [item["status"] for item in listed["items"] if item["id"] == "youtube-abcdefghijk"] == ["unpublished"]

    back = call(setup["app"], "POST", path, json={"status": "published"})
    assert back.status_code == 200 and back.json()["record"]["status"] == "published"
    assert [item.media_id for item in store.list(language="zh")] == ["youtube-abcdefghijk"]

    assert call(setup["app"], "POST", path, json={"status": "deleted"}).status_code == 422
    assert call(setup["app"], "POST",
                "/api/admin/console/content/media/nope/status", json={"status": "archived"}).status_code == 404


def test_publish_requires_an_attested_admission_and_is_audited(setup):
    refused = call(setup["app"], "POST", "/api/admin/console/content/vocabulary/hsk1/publish",
                   json={"rights_status": "licensed", "completeness": "complete", "attested": False})
    assert refused.status_code == 422
    rejected = call(setup["app"], "POST", "/api/admin/console/content/vocabulary/hsk1/publish",
                    json={"rights_status": "", "completeness": "complete", "attested": True})
    assert rejected.status_code == 422
    published = call(setup["app"], "POST", "/api/admin/console/content/vocabulary/hsk1/publish",
                     json={"rights_status": "licensed", "completeness": "complete", "attested": True})
    assert published.status_code == 200
    collection_id, admission = setup["vocabulary"].published[0]
    assert collection_id == "hsk1"
    assert admission["attested_by"] == "sub-admin"
    assert admission["review_status"] == "approved"
    with Session(setup["engine"]) as session:
        assert session.query(AuditLog).filter(AuditLog.action == "admin.content.publish").count() == 1


def test_archive_goes_through_the_reading_library_contract(setup):
    response = call(setup["app"], "POST", "/api/admin/console/content/book/9d0c5b2e-4a3c-4d1e-9a52-7a7b9b1d2c3e/archive")
    assert response.status_code == 200
    assert setup["reading"].archived == ["9d0c5b2e-4a3c-4d1e-9a52-7a7b9b1d2c3e"]


def test_book_imports_record_a_receipt_per_file_including_failures(setup, monkeypatch):
    async def fake_import(request, files, learning_language):
        return {"results": [
            {"filename": "good.epub", "status": "ok", "book_id": "b-1", "title": "Good", "chapter_count": 3},
            {"filename": "bad.epub", "status": "error", "category": "malformed_epub"},
        ]}

    monkeypatch.setattr(reading_library_api, "import_books", fake_import)
    response = call(setup["app"], "POST", "/api/admin/console/imports/books",
                    files=[("files", ("good.epub", b"x", "application/epub+zip"))], data={"learning_language": "en"})
    assert response.status_code == 200
    assert [row["status"] for row in response.json()["results"]] == ["ok", "error"]
    # Where a failure happened is decided once, on the server, for the live
    # queue and the history alike.
    assert response.json()["results"][1]["stage"] == "parse"
    assert "stage" not in response.json()["results"][0]
    history = call(setup["app"], "GET", "/api/admin/console/imports/history?kind=book").json()
    by_source = {row["source"]: row for row in history["items"]}
    assert by_source["bad.epub"]["status"] == "failed"
    assert by_source["bad.epub"]["error"]["stage"] == "parse"
    assert by_source["good.epub"]["status"] == "published"
    assert history["summary"]["failed"] >= 1


def test_media_imports_answer_with_the_transcript_that_was_stored(setup, monkeypatch):
    from writing_coach import media_library_api

    setup["store"].upsert(MediaLibraryEntry(
        media_id="youtube-zzzzzzzzzzz", media_type="video", provider="youtube", provider_media_id="zzzzzzzzzzz",
        canonical_url="https://www.youtube.com/watch?v=zzzzzzzzzzz",
        playback={"provider": "youtube", "kind": "embed", "url": "https://www.youtube-nocookie.com/embed/zzzzzzzzzzz"},
        title="Harbour walk", thumbnail={"kind": "none", "ref": ""}, duration_ms=30000, language="en", level="",
        creator="", source={"provider": "youtube", "type": "admin-import", "provenance_url": "https://www.youtube.com/watch?v=zzzzzzzzzzz",
                            "license": "x", "review_status": "checked", "imported_by": "admin@example.com"},
        library="shared", created_at=NOW.isoformat(),
        lesson={"lesson_id": "youtube-zzzzzzzzzzz", "payload": {"transcript": {"segments": [{"text": "a"}, {"text": "b"}]}}},
    ))

    def fake_import(request, payload):
        return {"items": [
            {"url": "https://www.youtube.com/watch?v=zzzzzzzzzzz", "status": "ok", "detail": "Imported.",
             "media_id": "youtube-zzzzzzzzzzz", "lesson_id": ""},
            {"url": "https://example.com/page.html", "status": "error", "detail": "This address is not a supported media file."},
        ], "summary": {"total": 2, "ok": 1, "error": 1}}

    monkeypatch.setattr(media_library_api, "admin_import", fake_import)
    response = call(setup["app"], "POST", "/api/admin/console/imports/media", json={
        "language": "en", "items": [{"url": "https://www.youtube.com/watch?v=zzzzzzzzzzz"}, {"url": "https://example.com/page.html"}],
    })
    assert response.status_code == 200
    stored, failed = response.json()["items"]
    # A provider preview cannot count a transcript it has not fetched; the
    # import answers with what was actually stored.
    assert stored["has_transcript"] is True and stored["segment_count"] == 2
    assert "segment_count" not in failed
    history = call(setup["app"], "GET", "/api/admin/console/imports/history?kind=media").json()
    by_source = {row["source"]: row for row in history["items"]}
    assert by_source["https://www.youtube.com/watch?v=zzzzzzzzzzz"]["result"]["transcript"] == "available"
    assert by_source["https://example.com/page.html"]["status"] == "failed"


def test_runtime_reports_configuration_state_without_secret_values(setup, monkeypatch):
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setenv("AI_PROVIDER_SECRETS_KEY", key)
    body = call(setup["app"], "GET", "/api/admin/console/runtime")
    assert body.status_code == 200
    data = body.json()
    assert data["persistence_backend"] == "postgresql"
    assert data["ai"]["credential_store"] == "configured"
    assert data["services"][0]["id"] == "media_translation"
    assert data["billing"] == "not_active"
    assert data["ai"]["legacy_selection"]["source"] == "default"
    assert data["ai"]["legacy_selection"]["effective"]["provider"] == "ollama"
    assert data["ai"]["activation"] == "human_gated"
    # The console explains a health state with the control plane's own rule.
    from writing_coach.ai import control_plane
    assert data["ai"]["health_rules"] == {
        "degraded_latency_ms": control_plane._DEGRADED_LATENCY_MS,
        "degraded_failure_rate_percent": control_plane._DEGRADED_FAILURE_RATE_PERCENT,
    }
    assert key not in body.text
    monkeypatch.setenv("AI_PROVIDER_SECRETS_KEY", "not-a-fernet-key")
    invalid = call(setup["app"], "GET", "/api/admin/console/runtime")
    assert invalid.json()["ai"]["credential_store"] == "invalid"
    assert "not-a-fernet-key" not in invalid.text


def test_runtime_services_describe_engines_without_credentials():
    class Groq:
        engine_id, model_version, configured, _api_key = "groq", "openai/gpt-oss-120b", True, "SECRET-KEY"

    class Keyless:
        engine_id, model_version, configured = "groq", "openai/gpt-oss-120b", False

    class Local:
        engine_id, model_version = "local_marian", "opus-mt-v1"

    class Asr:
        provider_id, model, _api_key = "groq", "whisper-large-v3-turbo", "SECRET-ASR"

    class Demo:
        provider_id = "demo-synthetic"

    services = console.describe_runtime_services(
        media_translation=("groq", Groq()), reading_translation=("local", Local()),
        speech_recognition=Asr(), pronunciation=Demo(), transcript_fallback="none",
    )
    assert services == {
        "media_translation": {"provider": "groq", "engine": "groq", "model": "openai/gpt-oss-120b", "state": "configured"},
        "reading_translation": {"provider": "local", "engine": "local_marian", "model": "opus-mt-v1", "state": "selected"},
        "speech_recognition": {"provider": "groq", "engine": "groq", "model": "whisper-large-v3-turbo", "state": "configured"},
        "pronunciation": {"provider": "demo-synthetic", "engine": "demo-synthetic", "model": "", "state": "demo"},
        "transcript_fallback": {"provider": "none", "engine": "none", "model": "", "state": "not_configured"},
    }
    assert "SECRET" not in repr(services)
    other = console.describe_runtime_services(
        media_translation=("groq", Keyless()), reading_translation=("local", Local()),
        speech_recognition=None, pronunciation=None, transcript_fallback="supadata",
    )
    assert other["media_translation"]["state"] == "not_configured"
    assert other["speech_recognition"] == {"provider": "", "engine": "", "model": "", "state": "not_configured"}
    assert other["transcript_fallback"]["state"] == "configured"


def test_schema_facts_without_an_engine_is_not_applicable():
    assert console.schema_facts(None) == {"state": "not_applicable", "current": None, "expected": None}


def test_the_application_mounts_the_console_and_answers_honestly_on_the_test_backend():
    import app as app_module

    # The standalone fixture above reconfigures the module; use the app's own wiring.
    app_module.configure_admin_console_from_runtime()
    # Included routers are not flattened into app.routes by this FastAPI, so the
    # mount is proven the way a browser would see it: the routes answer.
    for path in ("/api/admin/console/users", "/api/admin/console/content", "/api/admin/console/imports/history",
                 "/api/admin/console/users/summary"):
        assert call(app_module.app, "GET", path).status_code == 200, path
    assert call(app_module.app, "POST", "/api/admin/console/imports/books").status_code == 422
    assert call(app_module.app, "POST", "/api/admin/console/content/vocabulary/x/publish", json={}).status_code == 422
    overview = call(app_module.app, "GET", "/api/admin/console/overview")
    runtime = call(app_module.app, "GET", "/api/admin/console/runtime")
    assert overview.status_code == 200
    body = overview.json()
    # CI runs on the SQLite test backend, which holds no authoritative learner data.
    assert body["accounts"] == {"available": False}
    assert body["ai"]["capabilities"]["total"] >= 1
    assert runtime.json()["persistence_backend"] == app_module._persistence_runtime.backend


def test_console_reports_unavailable_instead_of_failing_without_postgresql(setup):
    console.configure_admin_console(admin_guard=guard, backend="sqlite", repository=None,
                                    platform_repository=PlatformRepo(), vocabulary_repository=None,
                                    media_store=None, reading_repository=None)
    overview = call(setup["app"], "GET", "/api/admin/console/overview").json()
    assert overview["accounts"] == {"available": False}
    assert overview["activity"] == {"available": False}
    users = call(setup["app"], "GET", "/api/admin/console/users").json()
    assert users == {"available": False, "items": [], "total": 0}
    kinds = [item["kind"] for item in overview["attention"]]
    assert "persistence_not_authoritative" in kinds
