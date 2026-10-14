"""A word tap is deterministic: it never reaches the `learner_dictionary` AI capability.

D-192 (2026-10-14) refined "never AI": the only AI a tap can reach is the `word_translation` capability, only after
every deterministic layer missed, only when it is enabled (it ships disabled), and with the word only. These tests
therefore keep spying on every other AI entry and prove a disabled `word_translation` makes no call at all.

The contextual meaning ("Why here?") is the learner's explicit request, answered by the same endpoint with
`contextual` true and cached; every plain lookup path (Reading, Quick Sheet, Listening) asks with it false.
"""

from __future__ import annotations

from typing import Any

import pytest

import app as app_module
from writing_coach import media_interaction, word_detail
from writing_coach.reading_derived import DerivedCache


class _NoCache:
    def __init__(self) -> None:
        self.rows: dict[str, Any] = {}

    def get_dictionary(self, key: str):
        return self.rows.get(key)

    def put_dictionary(self, key: str, payload: dict, fetched_at: str) -> None:
        import json

        self.rows[key] = {"fetched_at": fetched_at, "payload_json": json.dumps(payload)}


@pytest.fixture
def ai_spy(monkeypatch):
    calls: list[str] = []

    def spy(name):
        def _fn(*args, **kwargs):
            calls.append(name)
            raise AssertionError(f"{name} must not be reached by a plain lookup")

        return _fn

    monkeypatch.setattr(app_module, "dictionary_ai_fallback", spy("dictionary_ai_fallback"))
    monkeypatch.setattr(app_module, "chinese_dictionary_ai", spy("chinese_dictionary_ai"))
    monkeypatch.setattr(app_module, "generate_structured", spy("generate_structured"))
    monkeypatch.setattr(media_interaction, "_run_structured", spy("_run_structured"))
    monkeypatch.setattr(app_module, "_learning_cache", _NoCache())
    return calls


class _Down:
    def get(self, *_a, **_k):
        raise app_module.requests.ConnectionError("dictionaryapi.dev is down")


class _Miss:
    ok = False

    def json(self):
        return {}


@pytest.mark.parametrize("failure", ["down", "miss"])
@pytest.mark.parametrize("chinese_setting", [False, True])
def test_reading_english_dictionary_miss_or_failure_never_reaches_ai(monkeypatch, ai_spy, failure, chinese_setting):
    fake = _Down() if failure == "down" else type("R", (), {"get": lambda self, *a, **k: _Miss()})()
    monkeypatch.setattr(app_module, "requests", fake)
    monkeypatch.setattr(app_module, "is_chinese", lambda: chinese_setting)
    result = app_module._reading_english_dictionary("zzyzx")
    assert ai_spy == []
    # The deterministic "no entry" answer (or None when the word is refused outright): never an error, never AI.
    assert result in ({"phonetic": ""}, None)


def test_reading_english_dictionary_hit_is_still_served_and_cached(monkeypatch, ai_spy):
    body = [{"word": "lamp", "phonetic": "/læmp/", "phonetics": [], "meanings": [
        {"partOfSpeech": "noun", "definitions": [{"definition": "a device that gives light"}]}]}]

    class _Hit:
        ok = True

        def json(self):
            return body

    monkeypatch.setattr(app_module, "requests", type("R", (), {"get": lambda self, *a, **k: _Hit()})())
    first = app_module._reading_english_dictionary("lamp")
    assert first["definitions"][0]["definition"] == "a device that gives light"
    monkeypatch.setattr(app_module, "requests", _Down())
    assert app_module._reading_english_dictionary("lamp")["cached"] is True  # cached: no second fetch
    assert ai_spy == []


def test_explicit_dictionary_endpoint_keeps_its_ai_fallback(monkeypatch):
    # The learner-facing GET /api/dictionary (allow_ai default) is unchanged: AI fallback stays intentional there.
    monkeypatch.setattr(app_module, "requests", _Down())
    monkeypatch.setattr(app_module, "_learning_cache", _NoCache())
    monkeypatch.setattr(app_module, "is_chinese", lambda: False)
    monkeypatch.setattr(app_module, "dictionary_ai_fallback", lambda word: {"word": word, "definitions": []})
    assert app_module.lookup_dictionary("zzyzx")["word"] == "zzyzx"


@pytest.fixture
def sheet_env(monkeypatch):
    monkeypatch.setattr(media_interaction, "current_language_code", lambda: "en")
    monkeypatch.setattr(word_detail, "_saved_terms", None)

    class _Store:
        rows: dict = {}

        def get(self, *a, **k):
            return None

        def put(self, *a, **k):
            return None

    monkeypatch.setattr(word_detail, "_cache", DerivedCache(_Store()))
    return None


def _body(**over: Any) -> word_detail.WordDetailIn:
    base = {"text": "ran out", "context": "The lamp ran out of oil.", "source_language": "en",
            "target_language": "vi", "depth": "sheet"}  # fmt: skip
    return word_detail.WordDetailIn(**{**base, **over})


@pytest.mark.parametrize("source,text,context", [
    ("en", "lamp", "The lamp ran out of oil."),
    ("zh", "你好", "你好，世界。"),
])
def test_deterministic_word_detail_makes_zero_ai_calls(monkeypatch, ai_spy, sheet_env, source, text, context):
    monkeypatch.setattr(word_detail, "_lookup", None)
    body = word_detail.word_detail(_body(text=text, context=context, source_language=source, contextual=False))
    assert ai_spy == []
    assert body["contextStatus"] == "skipped" and body["retryable"] is False


def test_deterministic_word_detail_with_the_real_lookup_and_dictionary_down(monkeypatch, ai_spy, sheet_env):
    monkeypatch.setattr(app_module, "requests", _Down())
    monkeypatch.setattr(app_module, "is_chinese", lambda: False)
    monkeypatch.setattr(word_detail, "_lookup", app_module._reading_lookup_service.lookup)
    body = word_detail.word_detail(_body(text="lamp", context="The lamp ran out of oil.", contextual=False))
    assert ai_spy == [] and body["contextStatus"] == "skipped"


def test_explicit_contextual_ask_still_reaches_the_capability_once_and_is_cached(monkeypatch, sheet_env):
    monkeypatch.setattr(word_detail, "_lookup", None)
    calls: list[str] = []

    class _Mem:
        def __init__(self):
            self.rows: dict = {}

        def get(self, key, *a, **k):
            return self.rows.get(key)

        def put(self, key, value, *a, **k):
            self.rows[key] = value

    def structured(capability_key, *, messages, schema, max_output_tokens):
        calls.append(capability_key)
        return {"context_meaning": "ran out", "why_here": "The lamp stopped."}

    monkeypatch.setattr(media_interaction, "_run_structured", structured)
    first = word_detail.word_detail(_body(contextual=True))  # contextual defaults true: the explicit "Why here?"
    second = word_detail.word_detail(_body(contextual=True))
    assert first["meaningSource"] == "context" and first["contextStatus"] == "ready"
    assert second["contextMeaning"] == "ran out"
    assert calls == ["learner_dictionary"]  # the second ask was a cache hit
