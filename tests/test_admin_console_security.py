"""Security gate for the console's own boundary (`/api/admin/console`).

A change must come from the console's page, every privileged action leaves a
complete audit row, a retried or doubled request cannot make a second copy of
what it already made, and the summaries read each fact once.
"""
from __future__ import annotations

import asyncio
import uuid

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.test_admin_console_routes import ADMIN, call, setup  # noqa: F401 - `setup` is a fixture
from writing_coach import admin_console_api as console
from writing_coach import media_library_api, reading_library_api
from writing_coach.media_library_store import MediaLibraryEntry
from writing_coach.persistence.models import AuditLog, User

BOOK = "9d0c5b2e-4a3c-4d1e-9a52-7a7b9b1d2c3e"
PUBLISH = {"rights_status": "licensed", "completeness": "complete", "attested": True}


def _upload_entry(media_id: str) -> MediaLibraryEntry:
    return MediaLibraryEntry(
        media_id=media_id, media_type="audio", provider="upload", provider_media_id=media_id.removeprefix("upload-"),
        canonical_url="", playback={"provider": "orena", "kind": "audio", "url": f"/api/media/files/media/{media_id}/o.wav"},
        title="Tone", thumbnail={"kind": "none", "ref": ""}, duration_ms=2000, language="en", level="", creator="",
        source={"provider": "upload", "type": "upload", "provenance_url": "", "license": "", "review_status": "",
                "imported_by": "admin@example.com"},
        library="shared", created_at="2026-09-18T00:00:00+00:00", lesson=None,
    )


@pytest.fixture()
def fakes(setup, monkeypatch):  # noqa: F811 - pytest fixture reuse
    """Importers that store what they are given, so outcomes are observable."""
    uploads: list[str] = []

    async def admin_upload(request, file, language):
        rows = []
        for item in file:
            await asyncio.sleep(0.05)  # long enough for a second request to overlap
            media_id = f"upload-{uuid.uuid4().hex}"
            setup["store"].upsert(_upload_entry(media_id))
            uploads.append(media_id)
            rows.append({"url": item.filename, "status": "ok", "detail": "Imported.", "media_id": media_id, "lesson_id": ""})
        return {"items": rows, "summary": {"total": len(rows), "ok": len(rows), "error": 0}}

    def admin_import(request, payload):
        return {"items": [{"url": item.url, "status": "ok", "detail": "Imported.",
                           "media_id": "youtube-abcdefghijk", "lesson_id": ""} for item in payload.items],
                "summary": {}}

    async def import_books(request, files, learning_language):
        return {"results": [{"filename": upload.filename, "status": "ok", "book_id": BOOK, "title": "T",
                             "chapter_count": 1} for upload in files]}

    monkeypatch.setattr(media_library_api, "admin_upload", admin_upload)
    monkeypatch.setattr(media_library_api, "admin_import", admin_import)
    monkeypatch.setattr(reading_library_api, "import_books", import_books)
    return {"uploads": uploads}


MUTATIONS = [
    ("POST", f"/api/admin/console/content/book/{BOOK}/archive", {}),
    ("POST", "/api/admin/console/content/vocabulary/hsk1/publish", {"json": PUBLISH}),
    ("POST", "/api/admin/console/content/media/youtube-abcdefghijk/reprocess", {}),
    ("POST", "/api/admin/console/imports/books",
     {"files": [("files", ("a.epub", b"x", "application/epub+zip"))], "data": {"learning_language": "en"}}),
    ("POST", "/api/admin/console/imports/media", {"json": {"language": "en", "items": [{"url": "https://www.youtube.com/watch?v=abcdefghijk"}]}}),
    ("POST", "/api/admin/console/imports/media-upload",
     {"files": [("file", ("tone.wav", b"RIFF-tone", "audio/wav"))], "data": {"language": "en"}}),
]


@pytest.mark.parametrize("method, path, body", MUTATIONS)
def test_a_change_must_come_from_the_console_page(setup, fakes, method, path, body):  # noqa: F811
    for origin in (None, "https://attacker.example", "http://testserver.attacker.example"):
        refused = call(setup["app"], method, path, origin=origin, **body)
        assert refused.status_code == 403, (path, origin)
        assert refused.json()["detail"]["category"].startswith("admin_origin"), (path, origin)
    assert setup["reading"].archived == [] and setup["vocabulary"].published == [] and fakes["uploads"] == []
    accepted = call(setup["app"], method, path, **body)
    assert accepted.status_code == 200, (path, accepted.text)


def _audit_rows(engine):
    with Session(engine) as session:
        return [
            {"action": row.action, "entity_type": row.entity_type, "entity_id": row.entity_id,
             "payload": dict(row.payload), "user_id": row.user_id, "created_at": row.created_at}
            for row in session.scalars(select(AuditLog).order_by(AuditLog.created_at)).all()
        ]


def test_every_privileged_console_action_names_actor_target_time_and_outcome(setup, fakes):  # noqa: F811
    app, engine = setup["app"], setup["engine"]
    assert call(app, "GET", "/api/admin/console/users").status_code == 200
    assert call(app, "GET", f"/api/admin/console/users/{setup['learner']}").status_code == 200
    for method, path, body in MUTATIONS:
        assert call(app, method, path, **body).status_code == 200, path
    with Session(engine) as session:
        admin_id = session.scalar(select(User.id).where(User.user_key == ADMIN["google_sub"]))
    rows = _audit_rows(engine)
    expected = {
        ("admin.accounts.list", "account"), ("admin.account.view", "account"),
        ("admin.content.archive", "book"), ("admin.content.publish", "vocabulary_collection"),
        ("admin.content.reprocess", "media"), ("admin.import", "book"), ("admin.import", "media"),
    }
    assert expected <= {(row["action"], row["entity_type"]) for row in rows}
    for row in rows:
        assert row["user_id"] == admin_id, row["action"]
        assert row["created_at"] is not None
        if row["action"] != "admin.accounts.list":
            assert row["entity_id"], row["action"]
        if row["action"].startswith("admin.content."):
            assert row["payload"]["outcome"] == "ok", row
        if row["action"] == "admin.import":
            assert row["payload"]["status"] in {"ok", "error", "duplicate"}, row
    view = next(row for row in rows if row["action"] == "admin.account.view")
    assert view["entity_id"] == str(setup["learner"])
    assert "learner.one@example.com" not in repr(rows), "the audit row names the account, not its address"


def test_a_retried_archive_answers_as_done_without_a_second_change(setup, monkeypatch):  # noqa: F811
    archived = {"done": False}

    def archive_once(book_id):
        first = not archived["done"]
        archived["done"] = True
        return first

    monkeypatch.setattr(setup["reading"], "archive_book", archive_once)
    monkeypatch.setattr(console._state.repository, "get_book", lambda book_id: {"id": book_id, "status": "archived"})
    first = call(setup["app"], "POST", f"/api/admin/console/content/book/{BOOK}/archive")
    retry = call(setup["app"], "POST", f"/api/admin/console/content/book/{BOOK}/archive")
    assert first.json() == {"archived": True, "id": BOOK}
    assert retry.status_code == 200 and retry.json() == {"archived": True, "id": BOOK, "unchanged": True}
    outcomes = [row["payload"]["outcome"] for row in _audit_rows(setup["engine"]) if row["action"] == "admin.content.archive"]
    assert outcomes == ["ok", "unchanged"]


def test_a_book_that_was_never_there_is_still_not_found(setup, monkeypatch):  # noqa: F811
    monkeypatch.setattr(setup["reading"], "archive_book", lambda book_id: False)
    monkeypatch.setattr(console._state.repository, "get_book", lambda book_id: None)
    assert call(setup["app"], "POST", f"/api/admin/console/content/book/{BOOK}/archive").status_code == 404


def _upload(client_call, body: bytes, name: str = "tone.wav"):
    return client_call("POST", "/api/admin/console/imports/media-upload",
                       files=[("file", (name, body, "audio/wav"))], data={"language": "en"})


def test_the_same_file_uploaded_twice_is_one_library_item(setup, fakes):  # noqa: F811
    first = _upload(lambda *a, **k: call(setup["app"], *a, **k), b"RIFF-same-bytes")
    again = _upload(lambda *a, **k: call(setup["app"], *a, **k), b"RIFF-same-bytes", name="renamed.wav")
    other = _upload(lambda *a, **k: call(setup["app"], *a, **k), b"RIFF-other-bytes")
    (stored,) = first.json()["items"]
    (duplicate,) = again.json()["items"]
    assert stored["status"] == "ok"
    assert duplicate["status"] == "duplicate" and duplicate["media_id"] == stored["media_id"]
    assert other.json()["items"][0]["status"] == "ok"
    assert len(fakes["uploads"]) == 2, "the repeated file was not imported a second time"
    history = call(setup["app"], "GET", "/api/admin/console/imports/history?kind=media").json()
    assert sorted(row["status"] for row in history["items"] if row["origin"] == "receipt") == ["duplicate", "published", "published"]


def test_a_file_whose_first_copy_is_gone_can_be_imported_again(setup, fakes):  # noqa: F811
    first = _upload(lambda *a, **k: call(setup["app"], *a, **k), b"RIFF-come-back").json()["items"][0]
    setup["store"].delete(first["media_id"])
    again = _upload(lambda *a, **k: call(setup["app"], *a, **k), b"RIFF-come-back").json()["items"][0]
    assert again["status"] == "ok" and again["media_id"] != first["media_id"]


def test_two_identical_uploads_at_the_same_moment_store_one_item(setup, fakes):  # noqa: F811
    async def both():
        transport = httpx.ASGITransport(app=setup["app"])
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            headers = {"x-test-admin": "1", "origin": "http://testserver"}

            def send():
                return client.post("/api/admin/console/imports/media-upload", headers=headers,
                                   files=[("file", ("tone.wav", b"RIFF-race", "audio/wav"))], data={"language": "en"})

            return await asyncio.gather(send(), send())

    responses = asyncio.run(both())
    statuses = sorted(response.json()["items"][0]["status"] for response in responses)
    assert statuses == ["duplicate", "ok"]
    assert len(fakes["uploads"]) == 1


def test_the_users_summary_reads_first_activity_once(setup, monkeypatch):  # noqa: F811
    repository = console._state.repository
    calls = {"count": 0}
    original = repository.first_activity_by_user

    def counted():
        calls["count"] += 1
        return original()

    monkeypatch.setattr(repository, "first_activity_by_user", counted)
    assert call(setup["app"], "GET", "/api/admin/console/users/summary").status_code == 200
    assert calls["count"] == 1
