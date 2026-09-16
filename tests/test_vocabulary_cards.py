from __future__ import annotations

from writing_coach.vocabulary_cards import (
    vocabulary_card_from_catalog_entry,
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
