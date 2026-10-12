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
from writing_coach.persistence.models import (
    VocabularyCollectionMembership,
    VocabularyEntry,
    VocabularySenseLocalization,
)
from writing_coach.persistence.vocabulary_repository import (
    SQLAlchemyVocabularyRepository,
    sqlite_vocabulary_repository,
)
from writing_coach.vocabulary_cards import vocabulary_card_from_catalog_entry
from writing_coach.vocabulary_source_import import (
    detect_vocabulary_mapping,
    normalize_vocabulary_rows,
    parse_vocabulary_source,
)

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
    """A copy of a sample under a fresh id and a fresh word.

    The entry's identity is (language, term, part of speech), so PostgreSQL runs,
    which share one database, need their own word to never meet each other's rows.
    """

    changed = copy.deepcopy(record)
    token = uuid.uuid4()
    prefix, _slug = changed["id"].split(":", 1)
    changed["id"] = f"{prefix}:t{token.hex[:10]}"
    if changed["lang"] == "en":
        changed["headword"] = "resilient" + "".join(chr(97 + int(c, 16) % 26) for c in token.hex[:8])
    else:
        chars = [chr(0x4E00 + (token.int >> shift) % 0x5000) for shift in (0, 20)]
        changed["headword"] = "".join(chars)
        for char, hanzi in zip(changed["zh"]["chars"], chars, strict=True):
            char["hanzi"] = hanzi
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


# --- the same lexical entry: identity is (language, term, part of speech), never the authored id --------------


def csv_rows(text: str, language: str = "en"):
    parsed = parse_vocabulary_source("legacy.csv", text.encode("utf-8"))
    mapping = detect_vocabulary_mapping(parsed).mapping
    return normalize_vocabulary_rows(parsed, mapping=mapping, language_code=language, meaning_language="vi")


def import_legacy(repo, text: str, *, published: bool = False):
    normalized = csv_rows(text)
    target = collection("en", status="published" if published else "pending_review")
    repo.import_source(collection=target, source=normalized, records=normalized["records"], mapping={},
                       imported_by="test")  # fmt: skip
    return target, normalized


def entries_for(repo, language, normalized_term):
    with Session(repo.engine) as session:
        return list(session.scalars(select(VocabularyEntry).where(
            VocabularyEntry.language_code == language, VocabularyEntry.normalized_term == normalized_term)))  # fmt: skip


def test_an_authored_row_for_a_word_a_csv_already_stored_is_that_entry_not_a_second_one(repository):
    record = unique(sample("en_resilient"))
    word = record["headword"]
    _target, legacy = import_legacy(repository, f"English|Vietnamese|POS\n{word}|bền bỉ|adjective\n")
    legacy_identity = legacy["records"][0]["identity_key"]
    assert legacy_identity.endswith("|bền bỉ")  # the CSV path's sense is the meaning fingerprint

    normalized = authored([record], "en")
    lookup = repository.classify_authored_records("en", normalized["records"])[0]
    assert lookup["status"] == "duplicate"
    assert lookup["entry_id"] == str(entry_row(repository, legacy_identity).id)

    skipped = run(repository, collection("en"), normalized)
    assert (skipped["imported"], skipped["duplicates"]) == (0, 1)
    overwritten = run(repository, collection("en"), normalized, duplicates="overwrite")
    assert overwritten["updated"] == 1
    stored = entries_for(repository, "en", word.casefold())
    assert len(stored) == 1, "the importer never adds a second entry for the same word and part of speech"
    assert stored[0].identity_key == legacy_identity
    assert stored[0].short_meanings[0]["text"] == "kiên cường; có khả năng phục hồi nhanh"
    assert stored[0].provenance["source_id"] == record["id"]


def test_a_stored_entry_with_no_part_of_speech_is_the_same_entry(repository):
    record = unique(sample("en_resilient"))
    import_legacy(repository, f"English|Vietnamese\n{record['headword']}|bền bỉ\n")
    lookup = repository.classify_authored_records("en", authored([record], "en")["records"])[0]
    assert lookup["status"] == "duplicate"


def test_two_stored_entries_for_the_word_and_part_of_speech_refuse_the_row(repository):
    record = unique(sample("en_resilient"))
    word = record["headword"]
    import_legacy(repository, f"English|Vietnamese|POS\n{word}|bền bỉ|adjective\n")
    import_legacy(repository, f"English|Vietnamese|POS\n{word}|đàn hồi|adjective\n")
    normalized = authored([record], "en")
    lookup = repository.classify_authored_records("en", normalized["records"])[0]
    assert lookup["status"] == "ambiguous_conflict"
    result = run(repository, collection("en"), normalized, duplicates="overwrite")
    assert (result["imported"], result["updated"], result["conflicts"]) == (0, 0, 1)
    assert result["rows"][0]["conflict"] == "ambiguous_conflict"
    assert len(entries_for(repository, "en", word.casefold())) == 2


def test_another_part_of_speech_is_a_distinct_entry_and_retrieval_is_ordered_not_by_chance(repository):
    """A real homonym (another part of speech) is a new, distinguishable entry; `find_entry` answers by
    identity order, so the answer does not depend on which entry was inserted first."""

    record = unique(sample("en_resilient"))
    word = record["headword"]
    noun = copy.deepcopy(record)
    noun["id"] = record["id"] + "-n"
    noun["pos"] = [{"code": "noun"}]
    # Insert the noun first: insertion order must not decide the answer.
    first = collection("en")
    run(repository, first, authored([noun], "en"))
    run(repository, first, authored([record], "en"))
    repository.finalize_collection_publication(first["id"], admission=ADMISSION)
    identities = sorted(entry.identity_key for entry in entries_for(repository, "en", word.casefold()))
    assert identities == [f"en|{word.casefold()}|adjective|", f"en|{word.casefold()}|noun|"]
    assert repository.find_entry("en", word.casefold())["identity_key"] == identities[0]
    search = repository.search_entries("en", word, limit=5)
    assert [item["identity_key"] for item in search] == identities


# --- an overwrite never leaves a localization of the old content showing --------------------------------------


def add_localization(repo, entry_id, *, language, gloss, source, method, selected):
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    with Session(repo.engine) as session, session.begin():
        session.add(VocabularySenseLocalization(
            id=uuid.uuid4(), entry_id=entry_id, support_language=language, gloss=gloss, source=source,
            source_version="test", method=method, selected=selected, selection_reason="", validation={},
            created_at=now, updated_at=now,
        ))  # fmt: skip


def localizations_of(repo, entry_id):
    with Session(repo.engine) as session:
        return {row.source: row for row in session.scalars(select(VocabularySenseLocalization).where(
            VocabularySenseLocalization.entry_id == entry_id))}  # fmt: skip


def test_an_overwrite_retires_localizations_of_the_old_content(repository):
    record = unique(sample("en_resilient"))
    target = collection("en")
    first = authored([record], "en")
    run(repository, target, first)
    entry = entry_row(repository, first["records"][0]["identity_key"])
    # Derived from the old meaning (a pivot), in a language the content does not carry: it would show.
    add_localization(repository, entry.id, language="zh", gloss="有韧性的", source="pivot-test",
                     method="pivot_translation", selected=True)  # fmt: skip
    # Written by a person, in another language the content does not carry.
    add_localization(repository, entry.id, language="fr", gloss="résilient", source="editor",
                     method="curated", selected=True)  # fmt: skip
    before = repository.get_collection(target["id"], status=None)["entries"][0]
    assert {"zh", "fr"} <= {m["language"] for m in before["short_meanings"]}

    edited = copy.deepcopy(record)
    edited["meanings"][0]["vi"] = "bền bỉ"
    result = run(repository, target, authored([edited], "en"), duplicates="overwrite")
    assert result["updated"] == 1
    assert result["localizations_retired"] == {"deleted": 1, "unselected": 1}

    rows = localizations_of(repository, entry.id)
    assert "pivot-test" not in rows  # derived: deleted, to be derived again from the new content
    curated = rows["editor"]  # written by a person: kept, but no longer shown
    assert curated.selected is False
    assert "overwritten" in curated.selection_reason and curated.validation["stale"]["reason"]
    after = repository.get_collection(target["id"], status=None)["entries"][0]
    languages = {m["language"] for m in after["short_meanings"]}
    assert "zh" not in languages and "fr" not in languages
    assert after["short_meanings"][0]["text"] == "bền bỉ"
    # The import's localization pass will ask for this sense again.
    candidates = repository.localization_candidates("en", "zh", collection_id=target["id"])
    assert str(entry.id) in {str(candidate["entry_id"]) for candidate in candidates}


def test_skip_leaves_localizations_alone(repository):
    record = unique(sample("en_resilient"))
    target = collection("en")
    first = authored([record], "en")
    run(repository, target, first)
    entry = entry_row(repository, first["records"][0]["identity_key"])
    add_localization(repository, entry.id, language="zh", gloss="有韧性的", source="pivot-test",
                     method="pivot_translation", selected=True)  # fmt: skip
    run(repository, collection("en"), authored([record], "en"), duplicates="skip")
    assert localizations_of(repository, entry.id)["pivot-test"].selected is True
