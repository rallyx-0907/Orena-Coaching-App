"""Imported rows gain dictionary readings from vendored data, never from a model."""

from __future__ import annotations

import pytest

from writing_coach.vocabulary_dictionary import complete_from_dictionary
from writing_coach.vocabulary_source_import import (
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


def test_a_bare_chinese_headword_gains_its_pinyin_and_nothing_else() -> None:
    records = _records("word\n松树\n学习\n", "zh")
    completed, summary = complete_from_dictionary(records, "zh")

    pine = completed[0]
    assert pine["readings"] == [{"text": "sōng shù", "kind": "reading", "origin": "dictionary"}]
    assert pine["short_meanings"] == []  # meanings are localizations, not dictionary completion
    assert pine["content_origins"]["readings"] == "dictionary"
    assert pine["provenance"]["dictionary"]["source"] == "cc-cedict"
    assert pine["provenance"]["dictionary"]["license"] == "CC BY-SA 4.0"
    assert summary == {"source": "CC-CEDICT", "readings": 2, "not_found": 0}


def test_the_source_reading_wins_and_identity_is_untouched() -> None:
    records = _records("word,pinyin\n松树,sōngshù\n", "zh")
    completed, summary = complete_from_dictionary(records, "zh")

    assert completed[0]["identity_key"] == records[0]["identity_key"]
    assert completed[0]["readings"] == records[0]["readings"]
    assert summary["readings"] == 0


def test_a_word_the_dictionary_lacks_is_reported_not_invented() -> None:
    completed, summary = complete_from_dictionary(_records("word\n奥瑞纳㐀\n", "zh"), "zh")

    assert completed[0]["readings"] == []
    assert summary["not_found"] == 1


@pytest.mark.parametrize("language", ["en", "fr"])
def test_a_language_without_vendored_data_is_returned_unchanged(language: str) -> None:
    records = _records("word\nbasket\n", language)
    completed, summary = complete_from_dictionary(records, language)

    assert completed == records
    assert summary["source"] == ""
