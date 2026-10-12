"""Authored entries through the existing repository import, on SQLite and (when set) PostgreSQL (D-17V).

The duplicate rule: an authored entry that is already stored is skipped (the
default) or overwritten only while it belongs to no published set. One that is
in a published set is refused as a conflict - nothing is overwritten, no
membership snapshot is written, nothing is unpublished.
"""

from __future__ import annotations

import copy
import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from writing_coach import vocabulary_entry_format as fmt
from writing_coach.persistence.models import VocabularyCollectionMembership, VocabularyEntry
from writing_coach.persistence.vocabulary_repository import (
    SQLAlchemyVocabularyRepository,
    sqlite_vocabulary_repository,
)
from writing_coach.vocabulary_cards import vocabulary_card_from_catalog_entry
from writing_coach.vocabulary_source_import import parse_vocabulary_source

SAMPLES = Path(__file__).resolve().parents[1] / "docs" / "vocab" / "samples"
ADMISSION = {
    "review_status": "approved",
    "publication_attested": True,
    "attested_by": "test-admin",
    "rights_status": "internal_curated",
    "completeness": "complete",
}


def sample(name: str) -> dict:
    return json.loads((SAMPLES / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture(params=["sqlite", "postgres"])
def repository(request, tmp_path):
    if request.param == "sqlite":
        repo = sqlite_vocabulary_repository(tmp_path / "vocabulary.db")
        repo.initialize()
        return repo
    engine = request.getfixturevalue("pg_engine")
    repo = SQLAlchemyVocabularyRepository(engine)
    assert repo.available()
    return repo


def unique(record: dict) -> dict:
    """A copy of a sample under a fresh id, so PostgreSQL runs never meet each other's rows."""

    changed = copy.deepcopy(record)
    prefix, _slug = changed["id"].split(":", 1)
    changed["id"] = f"{prefix}:t{uuid.uuid4().hex[:10]}"
    return changed


def authored(rows, language):
    raw = json.dumps(rows, ensure_ascii=False).encode("utf-8")
    return fmt.normalize_authored_entries(parse_vocabulary_source("entries.json", raw), language_code=language)


def collection(language: str, *, status: str = "pending_review") -> dict:
    ident = f"t-{language}-{uuid.uuid4().hex[:10]}"
    provenance = {"admission": dict(ADMISSION)} if status == "published" else {}
    return {"id": ident, "title": ident, "language_code": language, "catalog_status": status,
            "origin": "imported", "provenance": provenance}  # fmt: skip


def run(repo, target, normalized, duplicates="skip"):
    return repo.import_source(collection=target, source=normalized, records=normalized["records"], mapping={},
                              imported_by="test", duplicates=duplicates)  # fmt: skip


def entry_row(repo, identity_key):
    with Session(repo.engine) as session:
        return session.scalar(select(VocabularyEntry).where(VocabularyEntry.identity_key == identity_key))


def memberships(repo, collection_id):
    with Session(repo.engine) as session:
        return list(session.scalars(select(VocabularyCollectionMembership).where(
            VocabularyCollectionMembership.collection_id == collection_id)))  # fmt: skip


def test_both_samples_import_into_existing_tables_and_project_as_cards(repository):
    for name, language in (("en_resilient", "en"), ("zh_senlin", "zh")):
        normalized = authored([unique(sample(name))], language)
        target = collection(language)
        result = run(repository, target, normalized)
        assert (result["imported"], result["conflicts"], result["updated"]) == (1, 0, 0)
        record = normalized["records"][0]
        stored = entry_row(repository, record["identity_key"])
        assert stored is not None and stored.usage_notes == record["usage_notes"]
        assert stored.examples == record["examples"] and stored.orthography == record["orthography"]
        detail = repository.get_collection(target["id"], limit=10, status=None)
        assert detail["catalog_status"] == "pending_review"
        card = vocabulary_card_from_catalog_entry(detail["entries"][0])
        assert card["examples"][0]["highlight"] == record["examples"][0]["highlight"]
        if language == "zh":
            assert card["examples"][0]["reading_highlight"] == {"match": "sēnlín"}
            assert card["classifiers"][0]["text"] == "片"
        else:
            assert [item["text"] for item in card["collocations"]][:1] == ["highly resilient"]
            assert card["explanation_artifacts"][0]["kind"] == "mnemonic"


def test_a_duplicate_in_an_unpublished_set_is_skipped_by_default_and_overwritten_on_request(repository):
    record = unique(sample("en_resilient"))
    first = authored([record], "en")
    target = collection("en")
    run(repository, target, first)
    edited = copy.deepcopy(record)
    edited["meanings"][0]["vi"] = "bền bỉ"
    second = authored([edited], "en")
    identity = second["records"][0]["identity_key"]

    assert repository.classify_authored_records("en", second["records"])[0]["status"] == "duplicate"
    skipped = run(repository, collection("en"), second)
    assert (skipped["imported"], skipped["duplicates"], skipped["updated"]) == (0, 1, 0)
    assert entry_row(repository, identity).short_meanings[0]["text"] == "kiên cường; có khả năng phục hồi nhanh"

    other = collection("en")
    overwritten = run(repository, other, second, duplicates="overwrite")
    assert (overwritten["updated"], overwritten["conflicts"]) == (1, 0)
    assert entry_row(repository, identity).short_meanings[0]["text"] == "bền bỉ"
    assert len(memberships(repository, other["id"])) == 1


def test_a_duplicate_of_a_published_entry_is_a_conflict_and_changes_nothing(repository):
    record = unique(sample("zh_senlin"))
    first = authored([record], "zh")
    published = collection("zh")
    run(repository, published, first)
    repository.finalize_collection_publication(published["id"], admission=ADMISSION)
    identity = first["records"][0]["identity_key"]
    before = entry_row(repository, identity)

    edited = copy.deepcopy(record)
    edited["meanings"][0]["vi"] = "rừng già"
    second = authored([edited], "zh")
    lookup = repository.classify_authored_records("zh", second["records"])[0]
    assert lookup["status"] == "published_conflict"
    assert lookup["published_collections"] == [published["id"]]

    pending = collection("zh")
    for policy in ("skip", "overwrite"):
        result = run(repository, pending, second, duplicates=policy)
        assert (result["imported"], result["updated"], result["conflicts"]) == (0, 0, 1)
        assert result["rows"][0]["conflict"] == "published_conflict"
    after = entry_row(repository, identity)
    assert after.short_meanings == before.short_meanings
    # No membership in the new set, so no snapshot either.
    assert memberships(repository, pending["id"]) == []
    assert repository.get_collection(published["id"], limit=5)["catalog_status"] == "published"


def test_a_published_target_set_refuses_authored_entries(repository):
    record = unique(sample("en_resilient"))
    target = collection("en")
    run(repository, target, authored([record], "en"))
    repository.finalize_collection_publication(target["id"], admission=ADMISSION)
    fresh = authored([unique(sample("en_resilient"))], "en")
    with pytest.raises(ValueError, match="published"):
        run(repository, {**target, "catalog_status": "pending_review"}, fresh)


def test_the_same_id_under_another_part_of_speech_is_refused_not_guessed(repository):
    record = unique(sample("en_resilient"))
    run(repository, collection("en"), authored([record], "en"))
    changed = copy.deepcopy(record)
    changed["pos"] = [{"code": "noun"}]
    second = authored([changed], "en")
    assert repository.classify_authored_records("en", second["records"])[0]["status"] == "identity_conflict"
    result = run(repository, collection("en"), second, duplicates="overwrite")
    assert (result["imported"], result["conflicts"]) == (0, 1)


def test_the_legacy_merge_path_is_unchanged_when_no_policy_is_given(repository):
    """`duplicates=None` (every non-authored source) still merges into an existing unpublished entry."""

    record = unique(sample("en_resilient"))
    normalized = authored([record], "en")
    run(repository, collection("en"), normalized)
    result = repository.import_source(collection=collection("en"), source=normalized,
                                      records=normalized["records"], mapping={}, imported_by="test")  # fmt: skip
    assert "conflicts" not in result
    assert result["duplicates"] == 1 and result["imported"] == 1
