"""Unsupported scripts are unavailable at once; the local translator on the tap path is bounded."""

from __future__ import annotations

import time

import pytest

from writing_coach import media_interaction, media_translation, reading_lookup, word_detail
from writing_coach.media_translation import TranslationProviderError
from writing_coach.reading_derived import DerivedCache
from writing_coach.reading_lookup import ReadingLookupService
from writing_coach.reading_translation import ReadingTranslationService

_DEF = {"definitions": [{"part_of_speech": "noun", "definition": "a hot drink"}], "phonetic": ""}


@pytest.fixture(autouse=True)
def _one_learner(monkeypatch):
    """PR-MON-7D1: a learner's cached answers live in their account incarnation's scope; these tests are one
    learner's, with one incarnation."""
    from writing_coach import reading_cache_scope

    monkeypatch.setattr(reading_cache_scope, "_incarnation_of", lambda _user_key: "inc-one-learner")


class _Engine:
    engine_id = "local_marian"
    model_version = "x-1"
    accepts_timeout = True

    def __init__(self, delay: float = 0.0) -> None:
        self.delay = delay
        self.timeouts: list[float | None] = []

    def translate_batch(self, source_language, target_language, segments, *, timeout=None):
        self.timeouts.append(timeout)
        time.sleep(self.delay)
        return {s.segment_id: "nghĩa" for s in segments}


class _Catalogue:
    def __init__(self) -> None:
        self.asked: list = []

    def find_entry(self, language_code, normalized_term):
        self.asked.append((language_code, normalized_term))
        return None


@pytest.fixture(autouse=True)
def _clean():
    reading_lookup._mt_failed.clear()
    yield
    reading_lookup._mt_failed.clear()


@pytest.fixture
def ai_calls(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(media_interaction, "_run_structured", lambda *a, **k: calls.append("ai"))
    monkeypatch.setattr(media_interaction, "current_language_code", lambda: "en")
    monkeypatch.setattr(word_detail, "_saved_terms", None)
    monkeypatch.setattr(word_detail, "_cache", DerivedCache())
    return calls


@pytest.mark.parametrize("surrounding", ["en", "zh"])
@pytest.mark.parametrize("selection", ["привет", "한국어", "ひらがな", "カタカナ", "عربى", "12345"])
def test_an_unsupported_script_is_unavailable_at_once_and_calls_nothing(monkeypatch, ai_calls, surrounding, selection):
    catalogue = _Catalogue()
    engine = _Engine(delay=3.0)
    asked: list[str] = []
    service = ReadingLookupService(
        catalogue, lambda w: asked.append(w) or _DEF, ReadingTranslationService(engine, cache=DerivedCache()),
        lambda w: asked.append(w) or _DEF, budget_seconds=2.0,
    )
    monkeypatch.setattr(word_detail, "_lookup", service.lookup)
    started = time.perf_counter()
    body = word_detail.word_detail(word_detail.WordDetailIn(
        text=selection, context=f"x {selection} y", source_language=surrounding, target_language="vi", depth="sheet"))
    assert time.perf_counter() - started < 0.5
    assert asked == [] and engine.timeouts == [] and catalogue.asked == [] and ai_calls == []
    assert body["available"] is False and body["meaningSource"] == "none" and body["contextMeaning"] == ""


def test_the_lookup_path_passes_a_short_timeout_to_the_translator_call_itself():
    engine = _Engine(delay=0.05)
    service = ReadingLookupService(None, lambda w: _DEF, ReadingTranslationService(engine, cache=DerivedCache()), budget_seconds=1.0)
    service.lookup("espresso", "I drink espresso.", "en", "vi")
    assert engine.timeouts == [reading_lookup._MT_CALL_TIMEOUT] and reading_lookup._MT_CALL_TIMEOUT <= 2


def test_the_real_adapter_uses_the_lookup_timeout_and_keeps_its_own_default(monkeypatch):
    seen: list[float] = []

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"translations": [{"segment_id": "selection", "translated_meaning": "cà phê"}]}

    monkeypatch.setattr(media_translation.requests, "post", lambda url, json, timeout: seen.append(timeout) or _Resp())
    provider = media_translation.LocalHttpTranslationProvider("http://x")
    segments = [type("S", (), {"segment_id": "selection", "original_text": "coffee"})()]
    provider.translate_batch("en", "vi", segments, timeout=1.5)
    provider.translate_batch("en", "vi", segments)
    assert seen == [1.5, 90.0]


def test_repeated_misses_on_a_hung_translator_never_queue_more_than_the_bound():
    engine = _Engine(delay=1.5)
    service = ReadingLookupService(None, lambda w: _DEF, ReadingTranslationService(engine, cache=DerivedCache()), budget_seconds=0.05)
    started = time.perf_counter()
    for index in range(20):
        result = service.lookup(f"word{index}", f"I say word{index}.", "en", "vi").to_dict()
        assert result["meanings"] == [] and result["definitions"]  # the raw definition, every time
    assert time.perf_counter() - started < 20 * 0.3  # each tap within its budget
    assert len(engine.timeouts) <= reading_lookup._MT_SLOTS  # the rest were skipped at once, none queued
    assert len(reading_lookup._mt_inflight) <= reading_lookup._MT_SLOTS
    deadline = time.monotonic() + 5
    while reading_lookup._mt_inflight and time.monotonic() < deadline:
        time.sleep(0.05)  # let the bounded jobs finish so later tests start clean


def test_the_same_word_is_joined_and_a_failure_is_remembered():
    engine = _Engine(delay=0.3)
    service = ReadingLookupService(None, lambda w: _DEF, ReadingTranslationService(engine, cache=DerivedCache()), budget_seconds=0.1)
    for _ in range(3):
        service.lookup("kettle", "A kettle.", "en", "vi")
    assert len(engine.timeouts) == 1  # in flight: joined, not repeated

    class _Down(_Engine):
        def translate_batch(self, *a, **k):
            self.timeouts.append(None)
            raise TranslationProviderError("down")

    down = _Down()
    service = ReadingLookupService(None, lambda w: _DEF, ReadingTranslationService(down, cache=DerivedCache()), budget_seconds=1.0)
    service.lookup("teapot", "A teapot.", "en", "vi")
    time.sleep(0.1)
    service.lookup("teapot", "A teapot.", "en", "vi")
    assert len(down.timeouts) == 1  # the failure is remembered briefly
