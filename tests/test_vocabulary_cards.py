from __future__ import annotations

import pytest
import writing_coach.becoming_library as becoming_library

from writing_coach.vocabulary_cards import (
    vocabulary_card_from_catalog_entry,
    VocabularyCardError,
    validate_vocabulary_card,

    vocabulary_card_from_saved_word,
)


def test_card_keeps_saved_word_identity_and_distinct_meanings() -> None:
    card = vocabulary_card_from_saved_word(
        {
            "word": "take off",
            "normalized_word": "take off",
            "language_code": "en",
            "phonetic": "/teɪk ɒf/",
            "part_of_speech": "phrasal verb",
            "definition": "to leave the ground",
            "translation_vi": "cất cánh",
            "source_kind": "reading",
            "source_fragment": "The plane will take off soon.",
            "source_essay_id": None,
        }
    )

    assert card["identity"] == {"language": "en", "normalized": "take off"}
    assert card["headword"] == "take off"
    assert card["pronunciation"] == "/teɪk ɒf/"
    assert card["meanings"] == [
        {"language": "en", "text": "to leave the ground"},
        {"language": "vi", "text": "cất cánh"},
    ]
    assert card["source_encounters"] == [
        {"kind": "reading", "fragment": "The plane will take off soon."}
    ]


def test_card_does_not_invent_empty_fields_or_orthography() -> None:
    card = vocabulary_card_from_saved_word(
        {
            "word": "curious",
            "normalized_word": "curious",
            "language_code": "en",
            "definition": "wanting to know more",
        }
    )

    assert card["meanings"] == [{"language": "en", "text": "wanting to know more"}]
    assert "pronunciation" not in card
    assert "part_of_speech" not in card
    assert card["examples"] == []
    assert card["collocations"] == []
    assert card["source_encounters"] == []
    assert "orthography" not in card


def test_card_accepts_verified_chinese_orthography_without_relabeling_it() -> None:
    orthography = {
        "script": "han",
        "characters": [
            {"character": "学", "stroke_count": 8, "stroke_paths": ["M0 0"] * 8}
        ],
        "source": "make-me-a-hanzi",
        "source_version": "hanzi-writer-data-2.0.1",
    }
    card = vocabulary_card_from_saved_word(
        {
            "word": "学习",
            "normalized_word": "学习",
            "language_code": "zh",
            "phonetic": "xuéxí",
            "definition": "to study",
        },
        orthography=orthography,
    )

    assert card["orthography"] == orthography
    assert card["identity"]["language"] == "zh"


def test_catalog_entry_card_carries_every_support_translation_in_stable_order() -> None:
    entry = {
        "word": "你好",
        "language_code": "zh",
        "phonetic": "nǐ hǎo",
        "part_of_speech": "phrase",
        "definition": "hello",
        "support_translations": {"vi": "xin chào", "en": "hello"},
        "level": "HSK1",
        "framework": "hsk",
        "topic": "greetings",
    }

    card = vocabulary_card_from_catalog_entry(entry)

    assert card["identity"] == {"language": "zh", "normalized": "你好"}
    assert card["headword"] == "你好"
    assert card["pronunciation"] == "nǐ hǎo"
    assert card["part_of_speech"] == "phrase"
    assert card["meanings"] == [
        {"language": "zh", "text": "hello"},
        {"language": "vi", "text": "xin chào"},
        {"language": "en", "text": "hello"},
    ]
    assert card["level"] == "HSK1"
    assert card["framework"] == "hsk"
    assert card["topic"] == "greetings"


def test_catalog_entry_card_preserves_natural_examples() -> None:
    entry = {
        "word": "invoice",
        "language_code": "en",
        "phonetic": "/ˈɪnvɔɪs/",
        "part_of_speech": "noun",
        "definition": "a document listing goods or services provided and the amount owed",
        "support_translations": {"vi": "hóa đơn"},
        "examples": [
            {
                "language": "en",
                "text": "Please send the invoice before Friday.",
            }
        ],
    }

    card = vocabulary_card_from_catalog_entry(entry)

    assert card["examples"] == [
        {
            "language": "en",
            "text": "Please send the invoice before Friday.",
        }
    ]


def test_imported_english_and_chinese_cards_preserve_source_orthography_and_layers() -> None:
    english = vocabulary_card_from_catalog_entry(
        {
            "term": "allocate",
            "language_code": "en",
            "normalized_term": "allocate",
            "short_meanings": [
                {"language": "vi", "text": "phân bổ", "origin": "source"}
            ],
            "detailed_definitions": [
                {"language": "en", "text": "give for a purpose", "origin": "source"}
            ],
            "pronunciations": [
                {"text": "/ˈæləkeɪt/", "origin": "source"}
            ],
            "examples": [
                {"language": "en", "text": "Allocate funds carefully."}
            ],
        }
    )
    chinese_orthography = {
        "script": "han",
        "characters": [{"character": "学习", "stroke_count": 16}],
        "source": "source-file",
    }
    chinese = vocabulary_card_from_catalog_entry(
        {
            "term": "学习",
            "language_code": "zh",
            "normalized_term": "学习",
            "readings": [{"text": "xuéxí", "origin": "source"}],
            "short_meanings": [
                {"language": "vi", "text": "học, học tập", "origin": "source"}
            ],
            "orthography": chinese_orthography,
        }
    )

    assert english["short_meanings"] == [{"language": "vi", "text": "phân bổ"}]
    assert english["detailed_definitions"] == [
        {"language": "en", "text": "give for a purpose"}
    ]
    assert english["examples"] == [
        {"language": "en", "text": "Allocate funds carefully."}
    ]
    assert chinese["pronunciation"] == "xuéxí"
    assert chinese["orthography"] == chinese_orthography


def test_saved_library_projection_prefers_imported_orthography(monkeypatch) -> None:
    source_orthography = {
        "script": "han",
        "characters": [{"character": "学习", "stroke_count": 16}],
        "source": "imported-source",
    }
    monkeypatch.setattr(becoming_library, "current_language_code", lambda: "zh")
    monkeypatch.setattr(
        becoming_library,
        "_catalog_entry_for",
        # _row_to_item now hands the lookup a resolver it decided once for the
        # whole list, so the stub takes it too.
        lambda word, resolve=None: {"orthography": source_orthography},
    )
    monkeypatch.setattr(
        becoming_library,
        "orthography_for_word",
        lambda word, language: {"source": "fallback-adapter"},
    )

    item = becoming_library._row_to_item(
        {
            "word": "学习",
            "phonetic": "xuéxí",
            "part_of_speech": "verb",
            "definition": "to study",
            "translation_vi": "học",
            "added_at": "",
            "source_essay_id": None,
            "source_fragment": "",
            "source_kind": "collection",
            "focus_note": "",
            "review_stage": 0,
            "successful_recalls": 0,
            "lapse_count": 0,
            "last_reviewed_at": "",
            "next_review_at": "",
        }
    )

    assert item["orthography"] == source_orthography


def test_catalog_entry_card_has_no_memory_or_source_encounters() -> None:
    entry = {
        "word": "curious",
        "language_code": "en",
        "definition": "wanting to know more",
        "support_translations": {"vi": "tò mò"},
    }

    card = vocabulary_card_from_catalog_entry(entry)

    assert "memory" not in card
    assert "source_encounters" not in card


def test_catalog_entry_card_does_not_invent_optional_fields() -> None:
    entry = {
        "word": "curious",
        "language_code": "en",
        "definition": "wanting to know more",
        "support_translations": {},
    }

    card = vocabulary_card_from_catalog_entry(entry)

    assert card["meanings"] == [{"language": "en", "text": "wanting to know more"}]
    assert "pronunciation" not in card
    assert "part_of_speech" not in card
    assert "level" not in card
    assert "framework" not in card
    assert "topic" not in card
    assert "orthography" not in card


def test_imported_card_keeps_short_meaning_separate_from_detailed_definition() -> None:
    card = vocabulary_card_from_catalog_entry(
        {
            "term": "abandon",
            "language_code": "en",
            "normalized_term": "abandon",
            "short_meanings": [
                {"language": "vi", "text": "bỏ, từ bỏ", "origin": "source"}
            ],
            "detailed_definitions": [
                {
                    "language": "en",
                    "text": "to leave someone or something completely",
                    "origin": "source",
                }
            ],
            "pronunciations": [
                {"text": "/əˈbændən/", "origin": "source"}
            ],
        }
    )

    assert card["headword"] == "abandon"
    assert card["pronunciation"] == "/əˈbændən/"
    assert card["short_meanings"] == [{"language": "vi", "text": "bỏ, từ bỏ"}]
    assert card["detailed_definitions"] == [
        {"language": "en", "text": "to leave someone or something completely"}
    ]
    assert {item["text"] for item in card["meanings"]} == {
        "bỏ, từ bỏ",
        "to leave someone or something completely",
    }
def test_card_preserves_rich_one_to_many_content_and_horizontal_understanding_refs() -> None:
    card = vocabulary_card_from_saved_word(
        {"word": "学习", "normalized_word": "学习", "language_code": "zh"},
        enrichments={
            "meanings": [
                {
                    "sense_id": "study",
                    "language": "en",
                    "text": "to study",
                    "contexts": ["我学习中文。"],
                },
                {
                    "sense_id": "learn",
                    "language": "en",
                    "text": "to learn",
                    "contexts": ["学习经验"],
                },
            ],
            "examples": [{
                "text": "我学习中文。",
                "source": {"kind": "reading", "id": "r1"},
            }],
            "understanding_refs": [{
                "id": "u1",
                "kind": "linguistic_explanation",
                "context": "我学习中文。",
            }],
            "explanation_artifacts": [{
                "kind": "mental_model",
                "text": "A deliberate learning image.",
            }],
        },
    )

    validate_vocabulary_card(card)
    assert len(card["meanings"]) == 2
    assert card["meanings"][0]["contexts"] == ["我学习中文。"]
    assert card["understanding_refs"][0]["kind"] == "linguistic_explanation"
    assert card["explanation_artifacts"][0]["kind"] == "mental_model"


def test_card_rejects_unprovenanced_verified_etymology_but_allows_other_optional_artifacts() -> None:
    card = vocabulary_card_from_saved_word(
        {"word": "学", "language_code": "zh"},
        enrichments={"explanation_artifacts": [
            {"kind": "mnemonic", "text": "A memory aid."},
            {"kind": "verified_etymology", "text": "A historical claim."},
        ]},
    )

    with pytest.raises(VocabularyCardError, match="trusted provenance"):
        validate_vocabulary_card(card)
