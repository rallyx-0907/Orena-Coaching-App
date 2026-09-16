from __future__ import annotations

import asyncio
import json
from dataclasses import replace

import httpx

import app as app_module


SOURCE = (
    "English|Vietnamese|IPA|POS|Definition|Example\n"
    "abandon|bỏ, từ bỏ|/əˈbændən/|verb|to leave completely|They abandoned the plan.\n"
    "学习|học, học tập|xuéxí|verb|to study|我每天学习。\n"
).encode()


def _request(method: str, path: str, **kwargs) -> httpx.Response:
    async def exercise() -> httpx.Response:
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(exercise())


def test_admin_preview_and_import_are_real_vertical_slice(tmp_path, monkeypatch) -> None:
    # The app's SQLite vocabulary adapter is an isolated test backend.  Keep
    # the source id unique so this remains independent from other route tests.
    monkeypatch.setenv("VOCABULARY_DB", str(tmp_path / "vocabulary.db"))
    # The process runtime was built before monkeypatching, so use a fresh
    # adapter only for this test; production PostgreSQL is still fail-closed.
    from writing_coach.persistence.vocabulary_repository import sqlite_vocabulary_repository

    repository = sqlite_vocabulary_repository(tmp_path / "vocabulary.db")
    repository.initialize()
    runtime = replace(app_module._persistence_runtime, vocabulary_repository=repository)
    monkeypatch.setattr(app_module, "_persistence_runtime", runtime)
    app_module.configure_becoming_library_content(repository)

    preview = _request(
        "POST",
        "/api/admin/vocabulary/preview",
        files=[("files", ("batch.csv", SOURCE, "text/csv"))],
    )
    assert preview.status_code == 200
    preview_item = preview.json()["items"][0]
    assert preview_item["detected_mapping"]["term"] == "English"
    assert preview_item["detected_mapping"]["short_meaning"] == "Vietnamese"
    assert preview_item["detected_mapping"]["reading"] is None

    mapping = dict(preview_item["detected_mapping"])
    imported = _request(
        "POST",
        "/api/admin/vocabulary/import",
        data={
            "metadata": json.dumps(
                {
                    "title": "Imported Starter Pack",
                    "language_code": "en",
                    "framework": "internal",
                    "level": "A1–B1",
                    "meaning_language": "vi",
                    "collection_id": "test-imported-starter-pack",
                    "rights_status": "internal_curated",
                    "completeness": "complete",
                    "publish": True,
                    "publication_attested": True,
                }
            ),
            "mappings": json.dumps({"batch.csv": mapping}),
        },
        files=[("files", ("batch.csv", SOURCE, "text/csv"))],
    )
    assert imported.status_code == 200, imported.text
    result = imported.json()["items"][0]
    assert result["status"] == "imported"
    assert result["imported"] == 2

    collections = _request(
        "GET", "/api/vocabulary/library/collections?language_code=en"
    )
    assert collections.status_code == 200
    assert collections.json()["items"][0]["id"] == "test-imported-starter-pack"

    detail = _request(
        "GET", "/api/vocabulary/library/collections/test-imported-starter-pack?limit=10"
    )
    assert detail.status_code == 200
    items = detail.json()["items"]
    abandon = next(item for item in items if item["headword"] == "abandon")
    assert abandon["pronunciation"] == "/əˈbændən/"
    assert {meaning["language"] for meaning in abandon["meanings"]} == {"vi", "en"}
    assert abandon["examples"][0]["text"] == "They abandoned the plan."


def test_admin_import_reports_schema_boundary_instead_of_writing_a_workaround(monkeypatch) -> None:
    class UnavailableRepository:
        def available(self):
            return False

        def initialize(self):
            return None

    runtime = replace(
        app_module._persistence_runtime,
        vocabulary_repository=UnavailableRepository(),
    )
    monkeypatch.setattr(app_module, "_persistence_runtime", runtime)
    response = _request(
        "POST",
        "/api/admin/vocabulary/import",
        data={"metadata": json.dumps({"title": "Blocked", "language_code": "en"})},
        files=[("files", ("blocked.txt", b"term\n", "text/plain"))],
    )
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["category"] == "vocabulary_schema_unavailable"
    assert "migrations" not in response.text


def test_admin_import_keeps_unattested_collection_out_of_learner_catalog(monkeypatch, tmp_path) -> None:
    from writing_coach.persistence.vocabulary_repository import sqlite_vocabulary_repository

    repository = sqlite_vocabulary_repository(tmp_path / "pending.db")
    repository.initialize()
    monkeypatch.setattr(
        app_module,
        "_persistence_runtime",
        replace(app_module._persistence_runtime, vocabulary_repository=repository),
    )
    response = _request(
        "POST",
        "/api/admin/vocabulary/import",
        data={
            "metadata": json.dumps(
                {"title": "Pending Pack", "language_code": "en", "collection_id": "pending-pack"}
            ),
            "mappings": json.dumps({"words.txt": {"term": "term"}}),
        },
        files=[("files", ("words.txt", b"hello\n", "text/plain"))],
    )
    assert response.status_code == 200, response.text
    assert response.json()["collection"]["catalog_status"] == "pending_review"
    assert repository.list_collections("en") == []


def test_admin_import_rejects_publish_without_verified_admission(monkeypatch, tmp_path) -> None:
    from writing_coach.persistence.vocabulary_repository import sqlite_vocabulary_repository

    repository = sqlite_vocabulary_repository(tmp_path / "admission.db")
    repository.initialize()
    monkeypatch.setattr(
        app_module,
        "_persistence_runtime",
        replace(app_module._persistence_runtime, vocabulary_repository=repository),
    )
    response = _request(
        "POST",
        "/api/admin/vocabulary/import",
        data={
            "metadata": json.dumps(
                {
                    "title": "Unverified Pack",
                    "language_code": "en",
                    "collection_id": "unverified-pack",
                    "publish": True,
                    "publication_attested": True,
                    "completeness": "complete",
                }
            ),
        },
        files=[("files", ("words.txt", b"hello\n", "text/plain"))],
    )
    assert response.status_code == 422
    assert response.json()["detail"]["category"] == "vocabulary_rights_required"


def test_batch_import_keeps_a_bad_source_isolated(monkeypatch, tmp_path) -> None:
    from writing_coach.persistence.vocabulary_repository import sqlite_vocabulary_repository

    repository = sqlite_vocabulary_repository(tmp_path / "batch.db")
    repository.initialize()
    monkeypatch.setattr(
        app_module,
        "_persistence_runtime",
        replace(app_module._persistence_runtime, vocabulary_repository=repository),
    )
    app_module.configure_becoming_library_content(repository)
    mapping = {
        "good.csv": {
            "term": "English",
            "short_meaning": "Vietnamese",
            "pronunciation": "IPA",
        }
    }
    response = _request(
        "POST",
        "/api/admin/vocabulary/import",
        data={
            "metadata": json.dumps(
                {
                    "title": "Batch Isolated",
                    "language_code": "en",
                    "collection_id": "test-batch-isolated",
                    "rights_status": "internal_curated",
                    "completeness": "complete",
                    "publish": True,
                    "publication_attested": True,
                }
            ),
            "mappings": json.dumps(mapping),
        },
        files=[
            ("files", ("good.csv", b"English|Vietnamese|IPA\nhello|xin chao|/h/\n", "text/csv")),
            ("files", ("bad.csv", b"\xff\xfe", "text/csv")),
        ],
    )
    assert response.status_code == 200
    results = {item["filename"]: item for item in response.json()["items"]}
    assert results["good.csv"]["status"] == "imported"
    assert results["bad.csv"]["status"] == "failed"
    assert results["bad.csv"]["source_import_id"]
    assert repository.list_collections("en")[0]["item_count"] == 1
