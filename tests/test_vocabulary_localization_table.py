"""The (sense, support language) localization table behind the read path (D-124, 0025)."""

from __future__ import annotations

import json

from sqlalchemy import text

from writing_coach.persistence.vocabulary_repository import sqlite_vocabulary_repository
from writing_coach.vocabulary_localization import (
    ChineseDictionarySource,
    PivotTranslationSource,
    materialize_localizations,
)
from writing_coach.vocabulary_source_import import (
    detect_vocabulary_mapping,
    normalize_vocabulary_rows,
    parse_vocabulary_source,
)

ADMISSION = {
    "review_status": "approved",
    "publication_attested": True,
    "rights_status": "internal_curated",
    "completeness": "complete",
    "attested_by": "test-admin",
}


def _repository(tmp_path):
    repository = sqlite_vocabulary_repository(tmp_path / "vocabulary.db")
    repository.initialize()
    return repository


def _import(repository, collection_id: str, csv: str, *, publish: bool, meaning_language: str = "en") -> None:
    source = parse_vocabulary_source(f"{collection_id}.csv", csv.encode("utf-8"))
    normalized = normalize_vocabulary_rows(
        source,
        mapping=detect_vocabulary_mapping(source).mapping,
        language_code="zh",
        meaning_language=meaning_language,
    )
    repository.import_source(
        collection={
            "id": collection_id,
            "language_code": "zh",
            "title": collection_id,
            "catalog_status": "pending_review",
            "provenance": {"origin": "imported"},
        },
        source=normalized,
        records=normalized["records"],
        mapping={},
    )
    if publish:
        repository.finalize_collection_publication(collection_id, admission=ADMISSION)


def _meanings(repository, collection_id: str, term: str, *, status="published") -> list[dict]:
    collection = repository.get_collection(collection_id, status=status)
    entry = next(item for item in collection["entries"] if item["term"] == term)
    return [{k: m[k] for k in ("language", "text")} for m in entry["short_meanings"]]


def test_a_published_snapshot_still_gains_a_new_support_language(tmp_path) -> None:
    repository = _repository(tmp_path)
    _import(repository, "published-a", "word,meaning\n松树,pine\n", publish=True)
    # The same sense imported into a second list while the first is published:
    # that membership shows a frozen content snapshot (published_entry_immutable).
    _import(repository, "pending-b", "word,meaning,example\n松树,pine,山上有松树。\n", publish=False)
    with repository.engine.connect() as connection:
        snapshot = connection.execute(
            text("SELECT metadata FROM vocabulary_collection_memberships WHERE collection_id = 'pending-b'")
        ).scalar()
    assert "content_snapshot" in str(snapshot)

    entry_id = repository.get_collection("published-a")["entries"][0]["id"]
    counts = repository.store_localizations(
        [{"entry_id": entry_id, "support_language": "vi", "gloss": "cây thông", "source": "test-data",
          "source_version": "1", "method": "dictionary"}]
    )
    assert counts == {"inserted": 1, "selected": 1, "existing": 0}

    # Entry row, then snapshot, then the additive merge of selected rows (review P1-1).
    assert _meanings(repository, "published-a", "松树") == [
        {"language": "en", "text": "pine"}, {"language": "vi", "text": "cây thông"},
    ]
    assert _meanings(repository, "pending-b", "松树", status=None) == [
        {"language": "en", "text": "pine"}, {"language": "vi", "text": "cây thông"},
    ]
    # Neither the sense row nor the snapshot was mutated.
    with repository.engine.connect() as connection:
        stored = connection.execute(text("SELECT short_meanings FROM vocabulary_entries")).scalar()
        frozen = connection.execute(
            text("SELECT metadata FROM vocabulary_collection_memberships WHERE collection_id = 'pending-b'")
        ).scalar()
    stored, frozen = (json.loads(value) if isinstance(value, str) else value for value in (stored, frozen))
    assert all(item["language"] != "vi" for item in stored)
    assert all(item["language"] != "vi" for item in frozen["content_snapshot"]["short_meanings"])
    assert frozen["content_snapshot"]["examples"][0]["text"] == "山上有松树。"


def test_a_language_the_projection_already_has_is_not_replaced(tmp_path) -> None:
    repository = _repository(tmp_path)
    _import(repository, "own-vi", "word,meaning\n松树,cây thông non\n", publish=True, meaning_language="vi")
    entry_id = repository.get_collection("own-vi")["entries"][0]["id"]
    repository.store_localizations(
        [{"entry_id": entry_id, "support_language": "vi", "gloss": "thông", "source": "x", "source_version": "1", "method": "dictionary"}]
    )
    assert _meanings(repository, "own-vi", "松树") == [{"language": "vi", "text": "cây thông non"}]


def test_one_selected_gloss_per_sense_and_language_and_later_sources_do_not_displace_it(tmp_path) -> None:
    repository = _repository(tmp_path)
    _import(repository, "a", "word\n松树\n", publish=True)
    entry_id = repository.get_collection("a")["entries"][0]["id"]
    first = {"entry_id": entry_id, "support_language": "vi", "gloss": "cây thông", "source": "open-data", "source_version": "1", "method": "dictionary"}
    second = {**first, "gloss": "thông", "source": "api-fallback", "method": "pivot_translation"}
    assert repository.store_localizations([first]) == {"inserted": 1, "selected": 1, "existing": 0}
    assert repository.store_localizations([second, first]) == {"inserted": 1, "selected": 0, "existing": 1}
    assert _meanings(repository, "a", "松树") == [{"language": "vi", "text": "cây thông"}]


def test_materialization_reaches_a_published_collection_from_registered_sources(tmp_path) -> None:
    repository = _repository(tmp_path)
    _import(repository, "forest", "word\n松树\n竹林\n", publish=True)

    def marian(source, target, batch):
        return {key: {"pine; pine tree": "cây thông", "bamboo forest": "rừng tre"}[text] for key, text in batch}

    sources = [
        ChineseDictionarySource(),
        PivotTranslationSource(marian, engine="local_marian", model_version="opus-mt-v1", pairs=[("zh", "vi")]),
    ]
    reports = materialize_localizations(repository, "zh", sources, collection_id="forest")
    assert {row["language"]: row["added"] for row in reports} == {
        "en": {"cc-cedict": 2}, "vi": {"local_marian": 2},
    }
    assert _meanings(repository, "forest", "竹林") == [
        {"language": "en", "text": "bamboo forest"}, {"language": "vi", "text": "rừng tre"},
    ]
    # Re-running finds nothing missing: localization is materialized once.
    assert materialize_localizations(repository, "zh", sources, collection_id="forest") == []
    # The lookup path (find_entry) and the saved-word resolver see the same localizations.
    found = repository.find_entry("zh", "松树")
    assert found["support_translations"]["vi"] == "cây thông"
    assert any(m["language"] == "vi" for m in repository.list_entries_for_language("zh")[0]["short_meanings"])


def test_without_the_table_the_read_path_is_unchanged(tmp_path) -> None:
    repository = _repository(tmp_path)
    _import(repository, "plain", "word,meaning\n松树,pine\n", publish=True)
    with repository.engine.begin() as connection:
        connection.execute(text("DROP TABLE vocabulary_sense_localizations"))
    repository._localizations_present = None
    assert repository.localizations_available() is False
    assert _meanings(repository, "plain", "松树") == [{"language": "en", "text": "pine"}]
