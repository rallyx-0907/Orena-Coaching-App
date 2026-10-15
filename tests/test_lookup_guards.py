"""English-dictionary eligibility guard, and the translation cache read before the paid-provider block."""

from __future__ import annotations

import time

import pytest

import app as app_module
from writing_coach.reading_derived import DerivedCache
from writing_coach.reading_lookup import ReadingLookupService
from writing_coach.reading_translation import ReadingTranslationService


@pytest.fixture(autouse=True)
def _one_learner(monkeypatch):
    """PR-MON-7D1: a learner's cached answers live in their account incarnation's scope; these tests are one
    learner's, with one incarnation."""
    from writing_coach import reading_cache_scope

    monkeypatch.setattr(reading_cache_scope, "_incarnation_of", lambda _user_key: "inc-one-learner")


class _Cache:
    def __init__(self) -> None:
        self.rows: dict = {}

    def get_dictionary(self, key):
        return None

    def put_dictionary(self, key, payload, fetched_at):
        return None


class _Http:
    def __init__(self, ok: bool = False) -> None:
        self.urls: list[str] = []
        self.ok = ok

    def get(self, url, **_k):
        self.urls.append(url)
        outer = self

        class _R:
            ok = outer.ok

            def json(self):
                return [{"word": "x", "phonetic": "", "phonetics": [], "meanings": [
                    {"partOfSpeech": "noun", "definitions": [{"definition": "a thing"}]}]}]

        return _R()


@pytest.fixture
def http(monkeypatch):
    fake = _Http(ok=True)
    monkeypatch.setattr(app_module, "requests", fake)
    monkeypatch.setattr(app_module, "_learning_cache", _Cache())
    monkeypatch.setattr(app_module, "is_chinese", lambda: False)
    ai = []
    monkeypatch.setattr(app_module, "dictionary_ai_fallback", lambda w: ai.append(w) or {"word": w, "definitions": []})
    fake.ai = ai
    return fake


@pytest.mark.parametrize("word", ["坚持", "日本語", "привет", "عربى", "한국어", "123", "坚持 on"])
def test_non_latin_selection_never_reaches_the_english_dictionary(http, word):
    started = time.perf_counter()
    result = app_module._reading_english_dictionary(word)
    assert http.urls == [] and http.ai == []
    assert result in ({"phonetic": ""}, None)
    assert time.perf_counter() - started < 0.5


@pytest.mark.parametrize("word", ["café", "don't", "don’t", "well-being", "résumé", "naïve", "ice cream", "o'clock"])
def test_english_plausible_selection_still_reaches_the_dictionary(http, word):
    result = app_module._reading_english_dictionary(word)
    assert len(http.urls) == 1
    assert result["definitions"]


def test_every_caller_is_guarded_not_only_reading(http):
    # The explicit GET /api/dictionary path shares lookup_dictionary: no network for a Han selection there either.
    app_module.lookup_dictionary("坚持", language="en")
    assert http.urls == []


class _Engine:
    model_version = "x-1"

    def __init__(self, engine_id: str, meaning: str = "kiên trì") -> None:
        self.engine_id = engine_id
        self.meaning = meaning
        self.calls = 0

    def translate_batch(self, source_language, target_language, segments):
        self.calls += 1
        return {s.segment_id: self.meaning for s in segments}


class _Store:
    def __init__(self) -> None:
        self.rows: dict = {}

    def get_many(self, kind, target_language, keys):
        return {k: self.rows[(kind, target_language, k)] for k in keys if (kind, target_language, k) in self.rows}

    def put_many(self, kind, target_language, source_language, rows, *, provider, model):
        for key, payload in rows:
            self.rows[(kind, target_language, key)] = payload


def _lookup(engine, cache_store):
    translation = ReadingTranslationService(engine, cache=cache_store)
    service = ReadingLookupService(None, lambda w: {"definitions": [{"part_of_speech": "noun", "definition": "a pot"}]}, translation)
    return translation, service.lookup("kettle", "A kettle.", "en", "vi").to_dict()


@pytest.mark.parametrize("engine_id", ["ai", "groq"])
def test_paid_engine_with_a_cache_hit_returns_the_cached_meaning_without_a_provider_call(engine_id):
    store = DerivedCache()
    local = _Engine("local_marian", "ấm đun nước")
    _lookup(local, store)  # a local Marian answer is created and cached
    assert local.calls == 1
    paid = _Engine(engine_id, "never")
    _t, result = _lookup(paid, store)
    assert result["meanings"] == [{"text": "ấm đun nước", "source": "machine_translation"}]
    assert paid.calls == 0


@pytest.mark.parametrize("engine_id", ["ai", "groq"])
def test_paid_engine_with_a_cache_miss_falls_back_to_the_raw_definition(engine_id):
    paid = _Engine(engine_id, "never")
    _t, result = _lookup(paid, DerivedCache())
    assert paid.calls == 0 and result["meanings"] == []
    assert result["definitions"][0]["definition"] == "a pot"


def test_local_marian_with_a_miss_is_still_called_and_cached():
    local = _Engine("local_marian", "ấm đun nước")
    store = DerivedCache()
    _t, result = _lookup(local, store)
    assert local.calls == 1 and result["meanings"][0]["text"] == "ấm đun nước"
    _lookup(local, store)
    assert local.calls == 1  # second tap is a cache hit
