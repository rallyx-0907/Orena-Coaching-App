"""Imported rows are completed from vendored dictionary data, never from a model."""

from __future__ import annotations

import pytest

from writing_coach.vocabulary_dictionary import complete_from_dictionary
from writing_coach.vocabulary_source_import import (
    canonical_vocabulary_identity,
    detect_vocabulary_mapping,
    normalize_vocabulary_rows,
    parse_vocabulary_source,
)


def _records(csv: str, language: str, meaning_language: str = "") -> list[dict]:
    source = parse_vocabulary_source("list.csv", csv.encode("utf-8"))
    mapping = detect_vocabulary_mapping(source).mapping
    return normalize_vocabulary_rows(
        source, mapping=mapping, language_code=language, meaning_language=meaning_language
    )["records"]


def test_a_bare_chinese_headword_gains_pinyin_and_an_english_dictionary_meaning() -> None:
    records = _records("word\n松树\n学习\n", "zh")
    completed, summary = complete_from_dictionary(records, "zh")

    pine = completed[0]
    assert pine["readings"] == [{"text": "sōng shù", "kind": "reading", "origin": "dictionary"}]
    assert pine["short_meanings"] == [{"language": "en", "text": "pine; pine tree", "origin": "dictionary"}]
    assert pine["content_origins"]["short_meanings"] == "dictionary"
    assert pine["provenance"]["dictionary"]["source"] == "cc-cedict"
    assert pine["provenance"]["dictionary"]["license"] == "CC BY-SA 4.0"
    assert summary == {"source": "CC-CEDICT", "readings": 2, "meanings": 2, "not_found": 0}


def test_the_source_always_wins_and_identity_is_untouched() -> None:
    records = _records("word,pinyin,meaning\n松树,sōngshù,cây thông\n", "zh", meaning_language="vi")
    before = records[0]["identity_key"]
    completed, _ = complete_from_dictionary(records, "zh")

    row = completed[0]
    assert row["identity_key"] == before == canonical_vocabulary_identity(
        language_code="zh", term="松树", part_of_speech="", sense_key="cây thông"
    )
    assert row["readings"] == records[0]["readings"]  # the source reading is kept
    assert row["short_meanings"][0] == {"language": "vi", "text": "cây thông", "origin": "source"}
    assert row["short_meanings"][1]["origin"] == "dictionary"
    assert records[0]["short_meanings"] == [{"language": "vi", "text": "cây thông", "origin": "source"}]


def test_a_meaning_in_an_unstated_language_is_not_second_guessed() -> None:
    records = _records("word,meaning\n松树,pine\n", "zh")
    completed, summary = complete_from_dictionary(records, "zh")

    assert [item["text"] for item in completed[0]["short_meanings"]] == ["pine"]
    assert summary["meanings"] == 0
    assert summary["readings"] == 1


def test_an_existing_english_meaning_is_not_duplicated() -> None:
    records = _records("word,meaning\n松树,pine tree\n", "zh", meaning_language="en")
    completed, summary = complete_from_dictionary(records, "zh")

    assert completed[0]["short_meanings"] == records[0]["short_meanings"]
    assert summary["meanings"] == 0


def test_a_word_the_dictionary_lacks_is_reported_not_invented() -> None:
    records = _records("word\n奥瑞纳㐀\n", "zh")
    completed, summary = complete_from_dictionary(records, "zh")

    assert completed[0]["short_meanings"] == []
    assert summary["not_found"] == 1


@pytest.mark.parametrize("language", ["en", "fr"])
def test_a_language_without_vendored_data_is_returned_unchanged(language: str) -> None:
    records = _records("word\nbasket\n", language)
    completed, summary = complete_from_dictionary(records, language)

    assert completed == records
    assert summary["source"] == ""


def test_completion_never_reaches_an_ai_capability(monkeypatch) -> None:
    from writing_coach.ai import platform as ai_platform

    def boom(*args, **kwargs):
        raise AssertionError("dictionary completion must not call a model")

    monkeypatch.setattr(ai_platform, "generate_structured", boom)
    completed, _ = complete_from_dictionary(_records("word\n市场\n", "zh"), "zh")
    assert completed[0]["short_meanings"][0]["text"].startswith("marketplace")
