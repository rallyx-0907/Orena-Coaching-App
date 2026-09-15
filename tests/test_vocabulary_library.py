"""Task B: the static curated Vocabulary Library catalog.

Covers the English/Chinese seed collections, cross-language aggregation,
load-time denormalization, the word-to-collection index, structural validation
failures, and card-projection compatibility with
`vocabulary_card_from_catalog_entry` (Task A).
"""

from __future__ import annotations

from copy import deepcopy

import pytest

from writing_coach.vocabulary_cards import vocabulary_card_from_catalog_entry
from writing_coach.vocabulary_library import (
    VocabularyCatalogInvalid,
    _build_catalog,
    _build_learner_catalog,
    all_vocabulary_entries,
    collection_ids_for_word,
    get_vocabulary_collection,
    get_vocabulary_source_collection,
    list_vocabulary_collections,
    list_vocabulary_source_collections,
    normalize_vocabulary_word,
    validate_vocabulary_collections,
)


def _valid_collection(**overrides: object) -> dict[str, object]:
    collection = {
        "id": "sample-collection",
        "language_code": "en",
        "framework": "cefr-internal",
        "level": "A1",
        "topic": None,
        "title": "Sample Collection",
        "provenance": {"origin": "curated", "note": "Test fixture."},
        "entries": [
            {
                "word": "sample",
                "definition": "an example used for illustration",
                "support_translations": {"vi": "mẫu"},
                "level": "A1",
                "topic": "everyday",
            }
        ],
    }
    collection.update(overrides)
    return collection


# --- Collection presence and metadata --------------------------------------


def test_library_does_not_publish_incomplete_english_seed_packs() -> None:
    summaries = list_vocabulary_collections("en")
    assert summaries == []
    assert get_vocabulary_collection("cefr-b2") is None


def test_library_does_not_publish_incomplete_chinese_seed_packs() -> None:
    summaries = list_vocabulary_collections("zh")
    assert summaries == []
    assert get_vocabulary_collection("hsk-1") is None


def test_source_catalog_keeps_seed_coverage_outside_the_public_library() -> None:
    english = list_vocabulary_source_collections("en")
    chinese = list_vocabulary_source_collections("zh")
    assert {summary["id"] for summary in english} == {
        "toeic-600-essential",
        "common-3000",
        "cefr-b2",
        "cefr-c1",
        "cefr-c2",
    }
    assert {summary["id"] for summary in chinese} == {
        "hsk-1",
        "hsk-2",
        "hsk-3",
        "hsk-4",
        "hsk-5",
        "hsk-6",
        "hsk-7-9",
    }
    assert get_vocabulary_source_collection("toeic-600-essential")["catalog_status"] == "seed"


def test_published_pack_folds_internal_level_extensions_without_new_tile() -> None:
    parent = _valid_collection(
        id="common-3000",
        title="3000 Common Words",
        catalog_status="published",
        entries=[
            {
                "word": "common",
                "definition": "shared by many people",
                "support_translations": {"vi": "phổ biến"},
                "level": "A1",
            }
        ],
    )
    extension = _valid_collection(
        id="cefr-b2",
        title="Common Words B2 extension",
        parent_collection_id="common-3000",
        catalog_status="internal",
        entries=[
            {
                "word": "substantial",
                "definition": "large in amount or importance",
                "support_translations": {"vi": "đáng kể"},
                "level": "B2",
            }
        ],
    )

    learner_catalog = _build_learner_catalog(_build_catalog([parent, extension]))

    assert set(learner_catalog) == {"common-3000"}
    assert learner_catalog["common-3000"]["levels"] == ["A1", "B2"]
    assert learner_catalog["common-3000"]["level_range"] == "A1–B2"
    assert [entry["word"] for entry in learner_catalog["common-3000"]["entries"]] == [
        "common",
        "substantial",
    ]


def test_list_vocabulary_collections_sorted_by_framework_then_level_then_title() -> None:
    summaries = list_vocabulary_source_collections("zh")
    keys = [(summary["framework"], summary["level"], summary["title"]) for summary in summaries]
    assert keys == sorted(keys)


def test_unknown_language_returns_empty_list() -> None:
    assert list_vocabulary_collections("fr") == []


# --- get_vocabulary_collection: denormalization -----------------------------


def test_get_toeic_collection_entries_carry_denormalized_metadata() -> None:
    collection = get_vocabulary_source_collection("toeic-600-essential")
    assert collection is not None
    assert collection["id"] == "toeic-600-essential"
    entries = collection["entries"]
    assert len(entries) >= 30
    for entry in entries:
        assert entry["language_code"] == "en"
        assert entry["framework"] == "toeic"
        assert entry["collection_id"] == "toeic-600-essential"
        assert entry["origin"] == "curated"
        assert entry["support_translations"]


def test_get_hsk1_collection_entries_carry_denormalized_metadata() -> None:
    collection = get_vocabulary_source_collection("hsk-1")
    assert collection is not None
    entries = collection["entries"]
    assert len(entries) >= 30
    for entry in entries:
        assert entry["language_code"] == "zh"
        assert entry["framework"] == "hsk"
        assert entry["collection_id"] == "hsk-1"
        assert entry["origin"] == "curated"
        assert entry["support_translations"]


def test_get_vocabulary_collection_unknown_id_returns_none() -> None:
    assert get_vocabulary_collection("no-such-collection") is None


# --- all_vocabulary_entries: language filtering -----------------------------


def test_all_vocabulary_entries_covers_every_english_collection() -> None:
    entries = all_vocabulary_entries("en")
    collection_ids = {entry["collection_id"] for entry in entries}
    assert collection_ids == {
        "toeic-600-essential",
        "common-3000",
        "cefr-b2",
        "cefr-c1",
        "cefr-c2",
    }
    assert all(entry["language_code"] == "en" for entry in entries)


def test_all_vocabulary_entries_covers_every_chinese_collection() -> None:
    entries = all_vocabulary_entries("zh")
    collection_ids = {entry["collection_id"] for entry in entries}
    assert collection_ids == {"hsk-1", "hsk-2", "hsk-3", "hsk-4", "hsk-5", "hsk-6", "hsk-7-9"}
    assert all(entry["language_code"] == "zh" for entry in entries)


def test_all_vocabulary_entries_unknown_language_is_empty() -> None:
    assert all_vocabulary_entries("de") == []


# --- collection_ids_for_word: load-time index -------------------------------


def test_collection_ids_for_word_finds_known_hsk1_word() -> None:
    assert collection_ids_for_word("zh", "你好") == ["hsk-1"]


def test_collection_ids_for_word_normalizes_before_lookup() -> None:
    assert collection_ids_for_word("en", "  Client ") == ["toeic-600-essential"]


def test_collection_ids_for_word_returns_empty_for_unknown_word() -> None:
    assert collection_ids_for_word("zh", "some-word-not-in-any-seed") == []


def test_collection_ids_for_word_does_not_cross_languages() -> None:
    assert collection_ids_for_word("en", "你好") == []


# --- normalize_vocabulary_word ----------------------------------------------


def test_normalize_vocabulary_word_strips_and_casefolds() -> None:
    assert normalize_vocabulary_word("  Client ") == "client"
    assert normalize_vocabulary_word("你好") == "你好"
    assert normalize_vocabulary_word(None) == ""


# --- validate_vocabulary_collections: acceptance ----------------------------


def test_validate_accepts_the_current_english_catalog() -> None:
    from writing_coach.languages.english.vocabulary_collections import (
        VOCABULARY_COLLECTIONS as ENGLISH_COLLECTIONS,
    )

    assert validate_vocabulary_collections(ENGLISH_COLLECTIONS) is None


def test_validate_accepts_the_current_chinese_catalog() -> None:
    from writing_coach.languages.chinese.vocabulary_collections import (
        VOCABULARY_COLLECTIONS as CHINESE_COLLECTIONS,
    )

    assert validate_vocabulary_collections(CHINESE_COLLECTIONS) is None


def test_validate_accepts_a_well_formed_fixture() -> None:
    assert validate_vocabulary_collections([_valid_collection()]) is None


# --- validate_vocabulary_collections: rejections ----------------------------


def test_validate_rejects_duplicate_collection_ids() -> None:
    collections = [_valid_collection(), _valid_collection()]
    with pytest.raises(VocabularyCatalogInvalid):
        validate_vocabulary_collections(collections)


def test_validate_rejects_empty_entries() -> None:
    collection = _valid_collection(entries=[])
    with pytest.raises(VocabularyCatalogInvalid):
        validate_vocabulary_collections([collection])


def test_validate_rejects_missing_required_collection_field() -> None:
    collection = _valid_collection()
    del collection["title"]
    with pytest.raises(VocabularyCatalogInvalid):
        validate_vocabulary_collections([collection])


def test_validate_rejects_non_string_framework() -> None:
    collection = _valid_collection(framework=123)
    with pytest.raises(VocabularyCatalogInvalid):
        validate_vocabulary_collections([collection])


def test_validate_rejects_empty_level() -> None:
    collection = _valid_collection(level="   ")
    with pytest.raises(VocabularyCatalogInvalid):
        validate_vocabulary_collections([collection])


def test_validate_rejects_duplicate_words_within_one_collection() -> None:
    collection = _valid_collection()
    collection["entries"] = [
        deepcopy(collection["entries"][0]),
        deepcopy(collection["entries"][0]),
    ]
    with pytest.raises(VocabularyCatalogInvalid):
        validate_vocabulary_collections([collection])


def test_validate_rejects_missing_support_translations() -> None:
    collection = _valid_collection()
    del collection["entries"][0]["support_translations"]
    with pytest.raises(VocabularyCatalogInvalid):
        validate_vocabulary_collections([collection])


def test_validate_rejects_non_mapping_support_translations() -> None:
    collection = _valid_collection()
    collection["entries"][0]["support_translations"] = "vi: mau"
    with pytest.raises(VocabularyCatalogInvalid):
        validate_vocabulary_collections([collection])


def test_validate_rejects_non_mapping_collection() -> None:
    with pytest.raises(VocabularyCatalogInvalid):
        validate_vocabulary_collections(["not-a-mapping"])


# --- Card-projection compatibility ------------------------------------------


@pytest.mark.parametrize("language_code", ["en", "zh"])
def test_every_catalog_entry_round_trips_through_card_projection(language_code: str) -> None:
    entries = all_vocabulary_entries(language_code)
    assert entries
    for entry in entries:
        card = vocabulary_card_from_catalog_entry(entry)
        assert card["headword"] == entry["word"]
        assert card["identity"]["language"] == language_code
        assert card["meanings"]


@pytest.mark.parametrize("language_code", ["en", "zh"])
def test_seed_catalog_supports_pronunciation_and_context_examples(language_code: str) -> None:
    entries = all_vocabulary_entries(language_code)
    assert entries
    for entry in entries:
        assert entry["phonetic"]
        assert entry["examples"]
        assert entry["examples"][0]["language"] == language_code
        assert entry["examples"][0]["text"]


def test_seed_catalog_covers_the_requested_english_level_range() -> None:
    levels = {entry["level"] for entry in all_vocabulary_entries("en")}
    assert {"A1", "A2", "B1", "B2", "C1", "C2"} <= levels


def test_seed_catalog_covers_the_requested_hsk_level_range() -> None:
    levels = {entry["level"] for entry in all_vocabulary_entries("zh")}
    assert {"HSK1", "HSK2", "HSK3", "HSK4", "HSK5", "HSK6", "HSK7-9"} <= levels
