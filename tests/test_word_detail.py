"""The Quick Sheet contracts (D-066): WordDetail and SentenceSheet.

The shapes come from the pinned canonical baseline, so a change to either has to
happen there first. These tests hold the backend to those files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException

from writing_coach import media_interaction, word_detail

CONTRACTS = Path(__file__).resolve().parents[1] / "docs" / "design" / "canonical-ui" / "data-contracts"


def contract(name: str) -> dict[str, Any]:
    return json.loads((CONTRACTS / f"{name}.json").read_text(encoding="utf-8"))


def assert_covers(template: Any, value: Any, path: str = "$") -> None:
    """Every key the canonical contract names is present, at every depth."""
    if isinstance(template, dict):
        assert isinstance(value, dict), f"{path} should be an object"
        for key, inner in template.items():
            if key.startswith("_"):
                continue
            assert key in value, f"{path}.{key} is missing from the response"
            assert_covers(inner, value[key], f"{path}.{key}")
    elif isinstance(template, list) and template and isinstance(template[0], dict) and value:
        assert_covers(template[0], value[0], f"{path}[0]")


class FakeLookup:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def to_dict(self) -> dict[str, Any]:
        return self.payload


EN_LOOKUP = {
    "base_form": "",
    "part_of_speech": "verb",
    "pronunciation": "/ˈslʊkət/",
    "audio_url": "https://audio.example/slukket.mp3",
    "meanings": [{"text": "put out", "source": "catalog"}],
    "definitions": [],
}

EXPLANATION = {
    "summary": "went dark, as if someone had put them out",
    "natural_translation": "Each window went dark.",
    "grammar_notes": ["A participle used as an adverbial.", "Weak verb, group one."],
    "vocabulary": [
        {"fragment": "slukket", "meaning": "put out", "pos": "verb", "pronunciation": ""},
        {"fragment": "forsvant", "meaning": "vanished", "pos": "verb", "pronunciation": ""},
    ],
    "usage_note": "Used of lights and fires.",
    "judgement": "natural",
    "judgement_reason": "The participle keeps the sentence short and cold.",
    "register": "neutral",
    "examples": [{"text": "Hun slukket lyset.", "note": ""}, {"text": "Brannen ble slukket.", "note": ""}],
    "counter_examples": [],
    "follow_ups": ["Why not slokket?"],
    "core_idea": "To make a light or a flame stop.",
    "mental_model": "A hand closing over a candle.",
    "common_mistake": "Reading it as the main verb.",
    "contrast": [{"term": "skru av", "note": "switch a device off"}],
    "structure": [
        {"chunk": "Ett etter ett", "role": "adverbial"},
        {"chunk": "forsvant", "role": "verb"},
        {"chunk": "vinduene", "role": "subject"},
    ],
}


def test_every_judgement_has_exactly_one_canonical_verdict() -> None:
    assert set(word_detail.USAGE_VERDICTS) == set(media_interaction.USAGE_JUDGEMENTS)
    assert len(set(word_detail.USAGE_VERDICTS.values())) == len(media_interaction.USAGE_JUDGEMENTS)
    documented = set(contract("WordDetail")["usageVerdict"].replace(" | null", "").split(" | "))
    assert set(word_detail.USAGE_VERDICTS.values()) == documented


def test_word_detail_matches_the_canonical_contract() -> None:
    detail = word_detail.project_word_detail(
        selection="slukket",
        context="Ett etter ett forsvant vinduene, slukket som om noen hadde gjort det.",
        language="en",
        lookup=EN_LOOKUP,
        explanation=EXPLANATION,
        saved=False,
    )
    assert_covers(contract("WordDetail"), detail)
    assert detail["headword"] == "slukket"
    assert detail["script"] == "latin"
    assert detail["ipa"] == "/ˈslʊkət/" and detail["pinyin"] is None
    assert detail["partOfSpeech"] == "verb"
    assert detail["contextMeaning"] == EXPLANATION["summary"]
    assert detail["meaningSource"] == "context"
    assert detail["usageVerdict"] == "natural"
    deeper = detail["deeper"]
    assert deeper["coreIdea"] == "To make a light or a flame stop."
    assert deeper["whyHere"].startswith("The participle")
    assert deeper["grammarNote"].splitlines() == EXPLANATION["grammar_notes"]
    assert deeper["contrast"] == [{"term": "skru av", "note": "switch a device off"}]
    # The word itself is not one of its own related expressions.
    assert [item["term"] for item in deeper["relatedExpressions"]] == ["forsvant"]
    # Nothing the server does not hold is invented.
    assert deeper["sources"] == [] and deeper["learnerSentences"] == []


def test_chinese_reading_is_pinyin_and_never_an_invented_ipa() -> None:
    detail = word_detail.project_word_detail(
        selection="把",
        context="她走过去，把窗户打开了。",
        language="zh",
        lookup={"pronunciation": "bǎ", "part_of_speech": "adposition", "meanings": [{"text": "hold"}]},
        explanation=None,
        saved=True,
    )
    assert detail["script"] == "hanzi"
    assert detail["pinyin"] == "bǎ" and detail["ipa"] is None
    assert detail["saved"] is True


def test_without_the_explanation_the_sheet_answers_from_the_dictionary_and_says_so() -> None:
    detail = word_detail.project_word_detail(
        selection="slukket", context="slukket", language="en", lookup=EN_LOOKUP, explanation=None, saved=False
    )
    assert detail["contextMeaning"] == "put out"
    assert detail["meaningSource"] == "dictionary"
    assert detail["usageVerdict"] is None
    assert detail["deeper"]["coreIdea"] == ""


def test_with_nothing_at_all_there_is_no_meaning_to_show() -> None:
    detail = word_detail.project_word_detail(
        selection="zzz", context="zzz", language="en", lookup=None, explanation=None, saved=False
    )
    assert detail["meaningSource"] == "none" and detail["contextMeaning"] == ""


def test_sentence_sheet_matches_the_canonical_contract() -> None:
    sheet = word_detail.project_sentence_sheet(
        sentence="Ett etter ett forsvant vinduene.", explanation=EXPLANATION, saved_terms={"forsvant"}
    )
    assert_covers(contract("SentenceSheet"), sheet)
    assert sheet["translation"] == "Each window went dark."
    assert [part["role"] for part in sheet["structure"]] == ["adverbial", "verb", "subject"]
    assert {item["term"]: item["saved"] for item in sheet["vocabulary"]} == {"slukket": False, "forsvant": True}


def test_structure_keeps_only_literal_ordered_chunks_with_a_known_role() -> None:
    source = "Ett etter ett forsvant vinduene"
    kept = media_interaction._structure(
        [
            {"chunk": "Ett etter ett", "role": "adverbial"},
            {"chunk": "paraphrase", "role": "verb"},  # not in the sentence
            {"chunk": "vinduene", "role": "object"},  # not one of the four roles
            {"chunk": "forsvant", "role": "VERB"},  # kept, role folded
            {"chunk": "Ett", "role": "subject"},  # out of order: it was already passed
        ],
        source,
    )
    assert kept == [
        {"chunk": "Ett etter ett", "role": "adverbial"},
        {"chunk": "forsvant", "role": "verb"},
    ]


def _configure(monkeypatch, lookup: dict[str, Any] | Exception, saved: set[str] | None = None) -> None:
    def do_lookup(*_args: Any) -> FakeLookup:
        if isinstance(lookup, Exception):
            raise lookup
        return FakeLookup(lookup)

    monkeypatch.setattr(word_detail, "_lookup", do_lookup)
    monkeypatch.setattr(word_detail, "_saved_terms", lambda: saved or set())
    monkeypatch.setattr(media_interaction, "current_language_code", lambda: "en")


def _request(**over: Any) -> word_detail.WordDetailIn:
    body = {
        "text": "slukket",
        "context": "Ett etter ett forsvant vinduene, slukket som om noen hadde gjort det.",
        "source_language": "en",
        "target_language": "vi",
    }
    return word_detail.WordDetailIn(**{**body, **over})


def test_endpoint_returns_the_contract_and_marks_a_saved_word(monkeypatch) -> None:
    _configure(monkeypatch, EN_LOOKUP, saved={"Slukket"})
    monkeypatch.setattr(media_interaction, "_run_structured", lambda *a, **k: dict(EXPLANATION))

    body = word_detail.word_detail(_request())

    assert body["available"] is True and body["claim"] == "word_detail"
    assert_covers(contract("WordDetail"), body)
    assert body["saved"] is True
    assert body["usageVerdict"] == "natural"


def test_endpoint_survives_the_provider_being_down(monkeypatch) -> None:
    _configure(monkeypatch, EN_LOOKUP)

    def down(*_a: Any, **_k: Any) -> dict[str, Any]:
        raise HTTPException(503, "unavailable")

    monkeypatch.setattr(media_interaction, "_run_structured", down)

    body = word_detail.word_detail(_request())

    assert body["available"] is True
    assert body["meaningSource"] == "dictionary"
    assert body["usageVerdict"] is None


def test_endpoint_is_unavailable_only_when_neither_path_answers(monkeypatch) -> None:
    _configure(monkeypatch, RuntimeError("dictionary is down"))
    monkeypatch.setattr(
        media_interaction, "_run_structured", lambda *a, **k: (_ for _ in ()).throw(HTTPException(503, "x"))
    )

    body = word_detail.word_detail(_request())

    assert body["available"] is False and body["claim"] == "word_detail_unavailable"


def test_endpoint_refuses_text_that_is_not_in_the_visible_context(monkeypatch) -> None:
    _configure(monkeypatch, EN_LOOKUP)
    with pytest.raises(HTTPException) as caught:
        word_detail.word_detail(_request(text="elsewhere"))
    assert caught.value.status_code == 422


def test_sentence_endpoint_drops_a_structure_that_does_not_match_the_sentence(monkeypatch) -> None:
    _configure(monkeypatch, EN_LOOKUP, saved={"forsvant"})
    explanation = {**EXPLANATION, "structure": [{"chunk": "made up", "role": "verb"}]}
    monkeypatch.setattr(media_interaction, "_run_structured", lambda *a, **k: explanation)

    body = word_detail.sentence_sheet(
        word_detail.SentenceSheetIn(
            text="Ett etter ett forsvant vinduene.", source_language="en", target_language="vi"
        )
    )

    assert body["available"] is True and body["claim"] == "sentence_sheet"
    assert body["structure"] == []
    assert next(item for item in body["vocabulary"] if item["term"] == "forsvant")["saved"] is True
