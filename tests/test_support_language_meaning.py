"""The basic Quick Sheet meaning is in the learner's support language, from local sources only (0 paid AI)."""

from __future__ import annotations

from typing import Any

import pytest

from writing_coach import media_interaction, word_detail
from writing_coach.reading_derived import DerivedCache
from writing_coach.reading_lookup import ReadingLookupService
from writing_coach.reading_translation import ReadingTranslationService


class _Engine:
    model_version = "x-1"

    def __init__(self, engine_id: str = "local_marian", meaning: str = "") -> None:
        self.engine_id = engine_id
        self.meaning = meaning
        self.calls = 0

    def translate_batch(self, source_language, target_language, segments):
        self.calls += 1
        return {s.segment_id: self.meaning for s in segments}


class _Catalogue:
    def __init__(self, entries: dict) -> None:
        self.entries = entries

    def find_entry(self, language_code, normalized_term):
        return self.entries.get((language_code, normalized_term))


class _Store:
    def get_many(self, kind, target_language, keys):
        return {}

    def put_many(self, *a, **k):
        return None


@pytest.fixture
def ai_spy(monkeypatch):
    calls: list[str] = []

    def spy(*_a, **_k):
        calls.append("ai")
        raise AssertionError("no AI/paid provider for a basic lookup")

    monkeypatch.setattr(media_interaction, "_run_structured", spy)
    monkeypatch.setattr(media_interaction, "current_language_code", lambda: "en")
    monkeypatch.setattr(word_detail, "_saved_terms", None)
    monkeypatch.setattr(word_detail, "_cache", DerivedCache(_Store()))
    return calls


def _detail(service: ReadingLookupService, text: str, context: str, source: str) -> dict[str, Any]:
    word_detail._lookup = service.lookup
    try:
        return word_detail.word_detail(
            word_detail.WordDetailIn(
                text=text, context=context, source_language=source, target_language="vi", depth="sheet", contextual=False
            )
        )
    finally:
        word_detail._lookup = None


_EN_DEF = "able to recover quickly from difficult conditions"
_EN_DICT = lambda word: {"definitions": [{"part_of_speech": "adjective", "definition": _EN_DEF}], "phonetic": ""}  # noqa: E731


def test_catalogue_localization_is_the_meaning_and_the_english_definition_is_kept(ai_spy):
    catalogue = _Catalogue({("en", "resilient"): {"term": "resilient", "short_meanings": [{"language": "vi", "text": "kiên cường"}]}})
    engine = _Engine()
    service = ReadingLookupService(catalogue, _EN_DICT, ReadingTranslationService(engine))
    body = _detail(service, "resilient", "She is resilient.", "en")
    assert body["contextMeaning"] == "kiên cường" and body["meaningSource"] == "dictionary"
    assert body["meaningLanguage"] == "vi"
    assert body["originalDefinition"] == {"text": _EN_DEF, "language": "en", "source": "dictionary"}
    assert ai_spy == [] and engine.calls == 0


def test_local_translation_engine_supplies_the_support_meaning(ai_spy):
    engine = _Engine("local_marian", "kiên cường; có khả năng phục hồi nhanh")
    service = ReadingLookupService(None, _EN_DICT, ReadingTranslationService(engine))
    body = _detail(service, "resilient", "She is resilient.", "en")
    assert body["contextMeaning"] == "kiên cường; có khả năng phục hồi nhanh"
    assert body["originalDefinition"]["text"] == _EN_DEF
    assert ai_spy == []


@pytest.mark.parametrize("engine_id", ["ai", "groq"])
def test_a_paid_translation_engine_is_never_used_for_a_basic_tap(ai_spy, engine_id):
    engine = _Engine(engine_id, "should not be used")
    service = ReadingLookupService(None, _EN_DICT, ReadingTranslationService(engine))
    body = _detail(service, "resilient", "She is resilient.", "en")
    assert engine.calls == 0 and ai_spy == []
    # No local translation: the raw dictionary definition is the graceful fallback, labelled English.
    assert body["contextMeaning"] == _EN_DEF and body["meaningLanguage"] == "en"
    assert body["originalDefinition"] is None  # nothing to repeat


def test_chinese_cedict_keeps_the_original_and_never_calls_ai(ai_spy):
    engine = _Engine("local_marian", "kiên trì; kiên định; duy trì")
    service = ReadingLookupService(None, lambda w: None, ReadingTranslationService(engine))
    body = _detail(service, "坚持", "我们要坚持下去。", "zh")
    assert body["contextMeaning"] == "kiên trì; kiên định; duy trì" and body["meaningLanguage"] == "vi"
    original = body["originalDefinition"]
    assert original["source"] == "cc-cedict" and original["language"] == "en" and original["text"]
    assert ai_spy == []


def test_chinese_without_a_local_translation_falls_back_to_cedict_english(ai_spy):
    service = ReadingLookupService(None, lambda w: None, ReadingTranslationService(_Engine("local_marian", "")))
    body = _detail(service, "坚持", "我们要坚持下去。", "zh")
    assert body["contextMeaning"] and body["meaningLanguage"] == "en" and body["meaningSource"] == "dictionary"
    assert ai_spy == []
