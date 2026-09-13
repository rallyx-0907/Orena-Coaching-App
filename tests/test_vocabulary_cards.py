from __future__ import annotations

from writing_coach.vocabulary_cards import vocabulary_card_from_saved_word


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
