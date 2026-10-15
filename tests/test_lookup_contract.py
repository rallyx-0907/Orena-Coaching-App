"""The word-tap contract: deterministic, lexical language by script, bounded latency, honest AI accounting."""

from __future__ import annotations

import time
from typing import Any

import pytest

import app as app_module
from writing_coach import media_interaction, word_detail
from writing_coach.core.http_security import rate_group
from writing_coach.reading_derived import DerivedCache
from writing_coach.reading_lookup import ReadingLookupService, lexical_language
from writing_coach.reading_translation import ReadingTranslationService


@pytest.fixture(autouse=True)
def _one_learner(monkeypatch):
    """PR-MON-7D1: a learner's cached answers live in their account incarnation's scope; these tests are one
    learner's, with one incarnation."""
    from writing_coach import reading_cache_scope

    monkeypatch.setattr(reading_cache_scope, "_incarnation_of", lambda _user_key: "inc-one-learner")


class _Engine:
    model_version = "x-1"

    def __init__(self, engine_id: str = "local_marian", meaning: str = "nghĩa", delay: float = 0.0) -> None:
        self.engine_id = engine_id
        self.meaning = meaning
        self.delay = delay
        self.calls: list[tuple[str, str]] = []

    def translate_batch(self, source_language, target_language, segments):
        self.calls.append((source_language, target_language))
        if self.delay:
            time.sleep(self.delay)
        return {s.segment_id: self.meaning for s in segments}


class _Catalogue:
    def __init__(self, entries: dict | None = None) -> None:
        self.entries = entries or {}
        self.asked: list[tuple[str, str]] = []

    def find_entry(self, language_code, normalized_term):
        self.asked.append((language_code, normalized_term))
        return self.entries.get((language_code, normalized_term))


_DEF = {"definitions": [{"part_of_speech": "noun", "definition": "a hot drink"}], "phonetic": "/ˈkɒfi/"}


@pytest.fixture
def ai_calls(monkeypatch):
    calls: list[str] = []

    def spy(capability_key, **_k):
        calls.append(capability_key)
        return {"context_meaning": "ở đây", "why_here": "vì sao", "summary": "tóm tắt", "natural_translation": "x",
                "structure": [], "vocabulary": []}

    monkeypatch.setattr(media_interaction, "_run_structured", spy)
    monkeypatch.setattr(media_interaction, "current_language_code", lambda: "en")
    monkeypatch.setattr(word_detail, "_saved_terms", None)
    monkeypatch.setattr(word_detail, "_cache", DerivedCache())
    monkeypatch.setattr(word_detail, "_lookup", None)
    return calls


def _in(text, context, source, **over):
    base = {"text": text, "context": context, "source_language": source, "target_language": "vi", "depth": "sheet"}
    return word_detail.WordDetailIn(**{**base, **over})


# 3 / 4: the server default and the explicit asks ---------------------------------------------------------------

def test_sheet_without_a_contextual_flag_is_deterministic(ai_calls):
    body = word_detail.word_detail(_in("lamp", "The lamp ran out.", "en"))
    assert ai_calls == [] and body["contextStatus"] == "skipped"


def test_sheet_with_an_explicit_contextual_ask_is_ai_once_then_cached(ai_calls):
    first = word_detail.word_detail(_in("lamp", "The lamp ran out.", "en", contextual=True))
    word_detail.word_detail(_in("lamp", "The lamp ran out.", "en", contextual=True))
    assert first["contextStatus"] == "ready" and ai_calls == ["learner_dictionary"]


def test_deep_word_full_depth_is_still_ai_backed(ai_calls):
    word_detail.word_detail(_in("lamp", "The lamp ran out.", "en", depth="full"))
    assert ai_calls == ["learner_dictionary"]
    word_detail.word_detail(_in("lamp", "The lamp ran out.", "en", depth="full", contextual=False))
    assert ai_calls == ["learner_dictionary"]  # an explicit false is honoured


# 2 / 3: the lexical language, by script ------------------------------------------------------------------------

@pytest.mark.parametrize("selection,fallback,expected", [
    ("坚持", "en", "zh"), ("coffee", "zh", "en"), ("AI技术", "en", "zh"), ("Wi-Fi密码", "en", "zh"),
    ("Wi-Fi", "zh", "en"), ("café", "zh", "en"), ("123", "en", ""), ("123", "zh", ""), ("привет", "en", ""), ("한국어", "en", ""), ("ひらがな", "zh", ""),
])
def test_lexical_language_rule(selection, fallback, expected):
    assert lexical_language(selection, fallback) == expected


def test_a_han_word_in_english_text_goes_the_whole_chinese_path(ai_calls):
    catalogue = _Catalogue()
    engine = _Engine(meaning="kiên trì")
    english_asked: list[str] = []
    service = ReadingLookupService(catalogue, lambda w: english_asked.append(w), ReadingTranslationService(engine, cache=DerivedCache()))
    word_detail._lookup = service.lookup
    try:
        body = word_detail.word_detail(_in("坚持", "I admire her 坚持 a lot.", "en"))
    finally:
        word_detail._lookup = None
    assert catalogue.asked and all(lang == "zh" for lang, _ in catalogue.asked)
    assert english_asked == [] and engine.calls == [("zh", "vi")]  # the cache key is zh-sourced
    assert body["script"] == "hanzi" and body["ipa"] is None
    assert body["originalDefinition"]["source"] == "cc-cedict" and body["contextMeaning"] == "kiên trì"
    assert ai_calls == []


def test_a_latin_word_in_chinese_text_goes_the_english_path(ai_calls):
    catalogue = _Catalogue()
    engine = _Engine(meaning="cà phê")
    english_asked: list[str] = []
    service = ReadingLookupService(catalogue, lambda w: english_asked.append(w) or _DEF, ReadingTranslationService(engine, cache=DerivedCache()))
    word_detail._lookup = service.lookup
    try:
        body = word_detail.word_detail(_in("coffee", "我喜欢喝 coffee 。", "zh"))
    finally:
        word_detail._lookup = None
    assert catalogue.asked and all(lang == "en" for lang, _ in catalogue.asked)
    assert english_asked == ["coffee"] and engine.calls == [("en", "vi")]
    assert body["script"] == "latin" and body["pinyin"] is None and body["ipa"] == "/ˈkɒfi/"
    assert body["originalDefinition"] == {"text": "a hot drink", "language": "en", "source": "dictionary"}
    assert ai_calls == []


def test_a_mixed_selection_is_chinese(ai_calls):
    catalogue = _Catalogue()
    service = ReadingLookupService(catalogue, lambda w: pytest.fail("no English dictionary for a mixed selection"),
                                   ReadingTranslationService(_Engine(), cache=DerivedCache()))
    result = service.lookup("AI技术", "我们研究 AI技术 的发展。", "zh", "vi")
    assert result.source_language == "zh" and all(lang == "zh" for lang, _ in catalogue.asked)


# 5: a meaning in hand is not held up by the network ------------------------------------------------------------

def test_a_catalogue_meaning_does_not_wait_for_the_external_dictionary():
    catalogue = _Catalogue({("en", "coffee"): {"term": "coffee", "short_meanings": [{"language": "vi", "text": "cà phê"}]}})
    service = ReadingLookupService(
        catalogue, lambda w: pytest.fail("the network dictionary must not be asked"), ReadingTranslationService(_Engine(), cache=DerivedCache()),
        lambda w: _DEF,
    )
    started = time.perf_counter()
    result = service.lookup("coffee", "I drink coffee.", "en", "vi").to_dict()
    assert time.perf_counter() - started < 0.5
    assert result["meanings"] == [{"text": "cà phê", "source": "collection"}]
    assert result["definitions"][0]["definition"] == "a hot drink" and result["pronunciation"] == "/ˈkɒfi/"


# 7: bounded latency --------------------------------------------------------------------------------------------

def test_a_hung_local_translator_does_not_hold_the_tap():
    engine = _Engine(delay=0.8)
    service = ReadingLookupService(None, lambda w: _DEF, ReadingTranslationService(engine, cache=DerivedCache()), budget_seconds=0.4)
    started = time.perf_counter()
    result = service.lookup("coffee", "I drink coffee.", "en", "vi").to_dict()
    assert time.perf_counter() - started < 1.5
    assert result["meanings"] == [] and result["definitions"][0]["definition"] == "a hot drink"  # the raw definition


def test_a_hung_dictionary_falls_back_within_its_timeout(monkeypatch):
    seen: dict[str, Any] = {}

    class _Hang:
        def get(self, url, **kwargs):
            seen["timeout"] = kwargs.get("timeout")
            time.sleep(0.05)
            raise app_module.requests.Timeout("slow")

    monkeypatch.setattr(app_module, "requests", _Hang())
    monkeypatch.setattr(app_module, "_learning_cache", type("C", (), {"get_dictionary": lambda s, k: None, "put_dictionary": lambda *a: None})())
    monkeypatch.setattr(app_module, "is_chinese", lambda: False)
    app_module._NO_ENTRY_UNTIL.clear()
    assert app_module._reading_english_dictionary("zzyzx") == {"phonetic": ""}
    assert seen["timeout"] == app_module._TAP_DICTIONARY_TIMEOUT <= 2
    # the legacy endpoint keeps its own 8 s
    with pytest.raises(Exception):  # noqa: B017 - its AI fallback is unavailable here; only the timeout matters
        app_module.lookup_dictionary("zzyzx", language="en", allow_ai=True)
    assert seen["timeout"] == 8


def test_a_miss_is_remembered_so_the_second_tap_is_instant(monkeypatch):
    urls: list[str] = []

    class _Miss:
        def get(self, url, **_k):
            urls.append(url)
            raise app_module.requests.Timeout("slow")

    monkeypatch.setattr(app_module, "requests", _Miss())
    monkeypatch.setattr(app_module, "_learning_cache", type("C", (), {"get_dictionary": lambda s, k: None, "put_dictionary": lambda *a: None})())
    monkeypatch.setattr(app_module, "is_chinese", lambda: False)
    app_module._NO_ENTRY_UNTIL.clear()
    app_module._reading_english_dictionary("qwxz")
    app_module._reading_english_dictionary("qwxz")
    assert len(urls) == 1


# 9: accounting -------------------------------------------------------------------------------------------------

def test_word_detail_counts_itself_and_only_when_it_asks_for_ai(ai_calls, monkeypatch):
    assert rate_group("POST", "/api/dictionary/word-detail") is None
    assert rate_group("POST", "/api/dictionary/sentence-sheet")[0] == "dictionary_ai"  # the rest stays counted
    counted: list[str] = []
    monkeypatch.setattr(word_detail, "_admit_ai", lambda request: counted.append("n"))
    request = object()
    word_detail.word_detail_route(_in("lamp", "The lamp ran out.", "en"), request)
    word_detail.word_detail_route(_in("lamp", "The lamp ran out.", "en", contextual=False), request)
    assert counted == []
    word_detail.word_detail_route(_in("lamp", "The lamp ran out.", "en", contextual=True), request)
    word_detail.word_detail_route(_in("lamp", "The lamp ran out.", "en", depth="full"), request)
    word_detail.word_detail_route(_in("lamp", "The lamp ran out.", "en", question="why?"), request)
    assert counted == ["n", "n", "n"]
