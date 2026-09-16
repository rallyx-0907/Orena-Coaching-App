from __future__ import annotations

from writing_coach.persistence.vocabulary_repository import sqlite_vocabulary_repository
from writing_coach.vocabulary_source_import import (
    detect_vocabulary_mapping,
    normalize_vocabulary_rows,
    parse_vocabulary_source,
)


def _source(filename: str, text: str):
    parsed = parse_vocabulary_source(filename, text.encode("utf-8"))
    detected = detect_vocabulary_mapping(parsed)
    normalized = normalize_vocabulary_rows(
        parsed,
        mapping=detected.mapping,
        language_code="en",
        meaning_language="vi",
        collection_framework="TOEIC",
        collection_level="B1",
    )
    return parsed, detected, normalized


def test_sqlite_content_repository_persists_membership_and_replays_duplicates(tmp_path) -> None:
    repository = sqlite_vocabulary_repository(tmp_path / "vocabulary.db")
    assert repository.available() is False
    repository.initialize()
    assert repository.available() is True
    parsed, detected, normalized = _source(
        "toeic.csv",
        "English|Vietnamese|IPA|Definition|Example\n"
        "allocate|phân bổ|/ˈæləkeɪt/|give for a purpose|Allocate funds carefully.\n"
        "abandon|bỏ, từ bỏ|||\n",
    )
    collection = {
        "id": "en-toeic-essential",
        "title": "600 TOEIC Essential",
        "language_code": "en",
        "framework": "TOEIC",
        "level": "B1",
        "catalog_status": "published",
        "origin": "imported",
        "provenance": {
            "publisher": "test",
            "admission": {
                "review_status": "approved",
                "publication_attested": True,
                "attested_by": "test-admin",
                "rights_status": "internal_curated",
                "completeness": "complete",
            },
        },
    }
    first = repository.import_source(
        collection=collection,
        source=normalized,
        records=normalized["records"],
        mapping=detected.mapping,
        imported_by="test-admin",
    )
    assert first["status"] == "imported"
    assert first["imported"] == 2
    assert first["duplicates"] == 0

    summaries = repository.list_collections("en")
    assert summaries[0]["id"] == "en-toeic-essential"
    assert summaries[0]["item_count"] == 2
    assert summaries[0]["level_range"] == "B1"

    detail = repository.get_collection("en-toeic-essential", limit=1)
    assert detail is not None
    assert detail["pagination"] == {"limit": 1, "offset": 0, "total": 2, "has_more": True}
    assert detail["entries"][0]["short_meanings"][0]["language"] == "vi"
    assert detail["entries"][0]["pronunciations"][0]["text"] == "/ˈæləkeɪt/"
    assert detail["entries"][0]["detailed_definitions"][0]["origin"] == "source"

    second = repository.import_source(
        collection=collection,
        source=normalized,
        records=normalized["records"],
        mapping=detected.mapping,
        imported_by="test-admin",
    )
    assert second["status"] == "skipped"
    assert second["imported"] == 0
    assert second["duplicates"] == 2
    assert second["skipped"] == 2

    found = repository.find_entry("en", "allocate")
    assert found is not None
    assert found["term"] == "allocate"
    assert found["support_translations"] == {"vi": "phân bổ"}


def test_one_entry_can_belong_to_two_collections_without_copying_lexical_content(tmp_path) -> None:
    repository = sqlite_vocabulary_repository(tmp_path / "vocabulary.db")
    repository.initialize()
    _, detected, normalized = _source("one.csv", "word,meaning\nlead,dẫn dắt\n")
    base = {
        "language_code": "en",
        "framework": "internal",
        "level": "B1",
        "catalog_status": "published",
        "origin": "imported",
        "provenance": {
            "admission": {
                "review_status": "approved",
                "publication_attested": True,
                "attested_by": "test-admin",
                "rights_status": "internal_curated",
                "completeness": "complete",
            }
        },
    }
    for collection_id, title in (("pack-a", "Pack A"), ("pack-b", "Pack B")):
        repository.import_source(
            collection={**base, "id": collection_id, "title": title},
            source=normalized,
            records=normalized["records"],
            mapping=detected.mapping,
        )
    assert len(repository.list_entries_for_language("en")) == 1
    assert repository.list_collections("en")[0]["item_count"] == 1
    assert repository.list_collections("en")[1]["item_count"] == 1


def test_collection_search_and_pagination_are_applied_before_fetching_rows(tmp_path) -> None:
    repository = sqlite_vocabulary_repository(tmp_path / "paged.db")
    repository.initialize()
    _, detected, normalized = _source(
        "paged.csv",
        "word,meaning\n"
        "alpha,first\n"
        "beta,second\n"
        "gamma,third\n",
    )
    repository.import_source(
        collection={
            "id": "paged-pack",
            "title": "Paged Pack",
            "language_code": "en",
            "framework": "internal",
            "level": "A1",
            "catalog_status": "published",
            "origin": "imported",
            "provenance": {
                "admission": {
                    "review_status": "approved",
                    "publication_attested": True,
                    "attested_by": "test-admin",
                    "rights_status": "internal_curated",
                    "completeness": "complete",
                }
            },
        },
        source=normalized,
        records=normalized["records"],
        mapping=detected.mapping,
    )

    detail = repository.get_collection("paged-pack", search="gamma", limit=1, offset=0)
    assert detail is not None
    assert detail["pagination"] == {"limit": 1, "offset": 0, "total": 1, "has_more": False}
    assert [entry["term"] for entry in detail["entries"]] == ["gamma"]


def test_published_admission_and_provenance_survive_pending_reimport(tmp_path) -> None:
    repository = sqlite_vocabulary_repository(tmp_path / "immutable-provenance.db")
    repository.initialize()
    _, detected, normalized = _source("first.csv", "word,meaning\nhello,greeting\n")
    approved = {
        "review_status": "approved",
        "publication_attested": True,
        "attested_by": "original-reviewer",
        "rights_status": "internal_curated",
        "completeness": "complete",
    }
    repository.import_source(
        collection={
            "id": "immutable-pack",
            "title": "Immutable Pack",
            "language_code": "en",
            "catalog_status": "published",
            "origin": "imported",
            "provenance": {"publisher": "original", "admission": approved},
        },
        source=normalized,
        records=normalized["records"],
        mapping=detected.mapping,
        imported_by="original-reviewer",
    )

    repository.import_source(
        collection={
            "id": "immutable-pack",
            "title": "Immutable Pack",
            "language_code": "en",
            "catalog_status": "pending_review",
            "origin": "imported",
            "provenance": {
                "publisher": "untrusted-reimport",
                "admission": {
                    "review_status": "pending_review",
                    "publication_attested": False,
                    "rights_status": "unknown",
                    "completeness": "partial",
                },
            },
        },
        source={**normalized, "filename": "second.csv"},
        records=normalized["records"],
        mapping=detected.mapping,
        imported_by="untrusted-reimport",
    )

    summary = repository.list_collections("en")[0]
    assert summary["catalog_status"] == "published"
    assert summary["provenance"]["publisher"] == "original"
    assert summary["provenance"]["admission"] == approved


def test_repository_rejects_caller_supplied_identity_mismatch(tmp_path) -> None:
    repository = sqlite_vocabulary_repository(tmp_path / "identity-ingress.db")
    repository.initialize()
    _, detected, normalized = _source("identity.csv", "word,meaning\nhello,greeting\n")
    record = {**normalized["records"][0], "identity_key": "en|tampered|||"}
    try:
        repository.import_source(
            collection={
                "id": "identity-pack",
                "title": "Identity Pack",
                "language_code": "en",
                "catalog_status": "pending_review",
                "origin": "imported",
                "provenance": {},
            },
            source=normalized,
            records=[record],
            mapping=detected.mapping,
        )
    except ValueError as exc:
        assert "identity key" in str(exc)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("tampered identity was accepted")


def test_failed_source_receipt_is_persisted_without_lexical_content(tmp_path) -> None:
    repository = sqlite_vocabulary_repository(tmp_path / "failed-receipt.db")
    repository.initialize()
    receipt = repository.record_source_failure(
        collection_id=None,
        filename="broken.csv",
        source_format="csv",
        content_hash="abc123",
        mapping={"term": "missing"},
        failure_reason="The source was not UTF-8 encoded.",
        imported_by="test-admin",
    )
    assert receipt["status"] == "failed"
    assert receipt["source_import_id"]
    assert receipt["failure_reason"] == "The source was not UTF-8 encoded."
