from __future__ import annotations

from writing_coach.vocabulary_source_import import (
    canonical_vocabulary_identity,
    detect_vocabulary_mapping,
    normalize_vocabulary_rows,
    parse_vocabulary_source,
    stable_collection_id,
)


def test_csv_detection_and_normalization_preserve_source_layers() -> None:
    source = parse_vocabulary_source(
        "toeic.csv",
        b"English|Vietnamese|IPA|POS|Definition|Example\n"
        b"allocate|phan bo|/\xce\x98/|verb|give for a purpose|Allocate funds carefully.\n",
    )
    detected = detect_vocabulary_mapping(source)
    assert detected.mapping["term"] == "English"
    assert detected.mapping["short_meaning"] == "Vietnamese"
    assert detected.mapping["pronunciation"] == "IPA"
    assert detected.mapping["part_of_speech"] == "POS"
    assert detected.mapping["detailed_definition"] == "Definition"

    normalized = normalize_vocabulary_rows(
        source,
        mapping=detected.mapping,
        language_code="en",
        meaning_language="vi",
        collection_framework="TOEIC",
        collection_level="B1",
    )
    record = normalized["records"][0]
    assert record["term"] == "allocate"
    assert record["short_meanings"] == [
        {"language": "vi", "text": "phan bo", "origin": "source"}
    ]
    assert record["detailed_definitions"] == [
        {"language": "en", "text": "give for a purpose", "origin": "source"}
    ]
    assert record["examples"][0]["origin"] == "source"
    assert record["content_origins"]["short_meanings"] == "source"
    assert record["content_origins"]["detailed_definitions"] == "source"


def test_json_and_txt_sources_accept_different_shapes() -> None:
    json_source = parse_vocabulary_source(
        "words.json",
        b'{"entries":[{"headword":"abandon","gloss":"leave","pinyin":""}]}',
    )
    json_mapping = detect_vocabulary_mapping(json_source).mapping
    assert json_mapping["term"] == "headword"
    assert json_mapping["short_meaning"] == "gloss"

    txt_source = parse_vocabulary_source("hsk.txt", "学习\n复习\n".encode())
    assert txt_source.headers == ("term",)
    assert [row["term"] for row in txt_source.rows] == ["学习", "复习"]


def test_identity_is_language_and_sense_aware() -> None:
    assert canonical_vocabulary_identity(language_code="en", term="Lead") == canonical_vocabulary_identity(language_code="en", term="lead")
    assert canonical_vocabulary_identity(language_code="en", term="resume") != canonical_vocabulary_identity(language_code="en", term="résumé")
    assert canonical_vocabulary_identity(language_code="zh", term="学习") != canonical_vocabulary_identity(language_code="zh", term="學習")
    assert canonical_vocabulary_identity(language_code="en", term="lead", part_of_speech="noun", sense_key="metal") != canonical_vocabulary_identity(language_code="en", term="lead", part_of_speech="verb", sense_key="guide")
    assert stable_collection_id("HSK 1", "zh", "HSK").startswith("zh-hsk-hsk-1")


def test_duplicate_rows_are_reported_without_fabricating_missing_fields() -> None:
    source = parse_vocabulary_source(
        "minimal.csv",
        b"word,translation\nresume,continue\nresume,continue\n",
    )
    normalized = normalize_vocabulary_rows(
        source,
        mapping={"term": "word", "short_meaning": "translation"},
        language_code="en",
        meaning_language="en",
    )
    assert len(normalized["records"]) == 1
    assert normalized["skipped"][0]["reason"] == "duplicate identity in source"
    record = normalized["records"][0]
    assert record["detailed_definitions"] == []
    assert record["pronunciations"] == []
    assert record["examples"] == []


def test_row_target_language_must_match_the_collection_language() -> None:
    source = parse_vocabulary_source(
        "mixed.csv",
        b"word,target_language\nhello,en\n\xe5\xad\xa6\xe4\xb9\xa0,zh\ninvalid,not a language\n",
    )
    normalized = normalize_vocabulary_rows(
        source,
        mapping={"term": "word", "target_language": "target_language"},
        language_code="en",
        meaning_language="vi",
    )
    assert [record["term"] for record in normalized["records"]] == ["hello"]
    assert len(normalized["skipped"]) == 2
    assert "does not match collection language" in normalized["skipped"][0]["reason"]
    assert "valid language code" in normalized["skipped"][1]["reason"]


def test_invalid_target_language_does_not_hide_a_later_valid_duplicate() -> None:
    source = parse_vocabulary_source(
        "ordered.csv",
        b"word,target_language\nhello,not-a-language\nhello,en\n",
    )
    normalized = normalize_vocabulary_rows(
        source,
        mapping={"term": "word", "target_language": "target_language"},
        language_code="en",
        meaning_language="vi",
    )

    assert [record["term"] for record in normalized["records"]] == ["hello"]
    assert normalized["skipped"][0]["reason"].endswith("is not a valid language code")
