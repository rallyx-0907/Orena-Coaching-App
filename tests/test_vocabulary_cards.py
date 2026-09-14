from __future__ import annotations

import pytest

from writing_coach.vocabulary_cards import (
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
