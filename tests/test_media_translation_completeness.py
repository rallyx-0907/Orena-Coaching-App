"""Video PR-A: line translation completes within a bounded continuation, and a partial one says why.

Root cause the trial hit (24/47, 24/69, 48/113, 0/130): each provider batch is 24 lines; the first provider failure
(a rate limit in practice) ended the whole run, the reason was dropped into a log warning, and nothing ever asked for
the missing lines again. Nothing here reaches a network: providers are fakes.
"""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest
import requests

from tests.test_media_import_pipeline_reasons import _Ledger, _world
from tests.test_media_translation_groq import FakeResponse, install, segments
from writing_coach import media_translation as mt
from writing_coach.admin_content import media_outcome
from writing_coach.media_learning import (
    MediaLearningAsset, MediaLearningObject, MediaProcessingState, MediaTranscript,
)
from writing_coach.media_meaning import TranslatedLines, resolve_segment_meanings
from writing_coach.media_spend import SpendCapReached


# -- the provider says why it failed -----------------------------------------------------------------------------

def _groq() -> mt.GroqTranslationProvider:
    return mt.GroqTranslationProvider("key", model="m")


@pytest.mark.parametrize("status,headers,reason,retry", [
    (429, {"retry-after": "7"}, "rate_limited", 7.0),
    (429, {"x-ratelimit-reset-tokens": "2m3.5s"}, "rate_limited", 123.5),
    (429, {}, "rate_limited", 0.0),
    (500, {}, "provider_error", 0.0),
    (401, {}, "provider_auth", 0.0),
])
def test_groq_failures_carry_a_stable_reason(monkeypatch, status, headers, reason, retry):
    install(monkeypatch, FakeResponse({}, status=status, headers=headers))
    with pytest.raises(mt.TranslationProviderError) as raised:
        _groq().translate_batch("en", "vi", segments("One."))
    assert raised.value.reason == reason and raised.value.retry_after == retry


@pytest.mark.parametrize("status", [429, 401, 403])
def test_refused_groq_calls_still_reach_the_quota_telemetry(monkeypatch, status):
    from writing_coach.ai import audio_telemetry

    seen = []
    monkeypatch.setattr(audio_telemetry, "record_token_operation", lambda *a, **k: seen.append((a, k)))
    install(monkeypatch, FakeResponse({}, status=status))
    with pytest.raises(mt.TranslationProviderError):
        _groq().translate_batch("en", "vi", segments("One."))
    assert len(seen) == 1 and seen[0][1]["outcome"] == "failure" and seen[0][0] == ("media_translation",)


def test_a_timeout_is_its_own_reason(monkeypatch):
    def boom(*_a, **_k):
        raise requests.Timeout("slow")

    monkeypatch.setattr(mt.requests, "post", boom)
    with pytest.raises(mt.TranslationProviderError) as raised:
        _groq().translate_batch("en", "vi", segments("One."))
    assert raised.value.reason == "provider_timeout"


# -- the service reports the reason of the batch that failed ------------------------------------------------------

class _Flaky:
    engine_id = "fake"
    model_version = "1"

    def __init__(self, plan):
        self.plan = list(plan)  # per call: None = succeed, or an exception
        self.calls = 0

    def translate_batch(self, source, target, batch):
        self.calls += 1
        step = self.plan.pop(0) if self.plan else None
        if step is not None:
            raise step
        return {item.segment_id: f"vi:{item.original_text}" for item in batch}


def _media(count: int):
    items = segments(*[f"Line {i}." for i in range(count)])
    asset = MediaLearningAsset("a1", "https://example.invalid/v", "test", "external-video", "T", "en",
                               MediaProcessingState.READY, count * 2000, True, False)
    return MediaLearningObject(asset=asset, transcript=MediaTranscript("a1", "en", items))


def test_service_result_names_the_failure():
    limited = mt.TranslationProviderError("x", reason="rate_limited", retry_after=4.0)
    service = mt.MediaTranslationService(_Flaky([limited]))
    result = service.translate(_media(2), "vi")
    assert result.status is mt.MediaTranslationStatus.UNAVAILABLE
    assert result.reason == "rate_limited" and result.retry_after == 4.0


# -- resolve_segment_meanings passes the translator's reason through ----------------------------------------------

class _Cache:
    def __init__(self):
        self.rows = {}

    def get_media_translation(self, key):
        return self.rows.get(key)

    def put_media_translation(self, key, text, provenance, stamp):
        self.rows[key] = {"translated_text": text}


def test_outcome_carries_reason_and_keeps_the_lines_that_exist():
    items = segments("A.", "B.", "C.")

    def translate(missing, target):
        return TranslatedLines({items[0].segment_id: "a"}, reason="rate_limited", retry_after=3.0)

    outcome = resolve_segment_meanings(asset_id="a1", segments=items, support_language="vi", source_language="en",
                                       cache=_Cache(), translate=translate)
    assert outcome.status == "partial" and len(outcome.meanings) == 1
    assert outcome.reason == "rate_limited" and outcome.retry_after == 3.0


def test_total_failure_keeps_the_reason_too():
    items = segments("A.")
    outcome = resolve_segment_meanings(asset_id="a1", segments=items, support_language="vi", source_language="en",
                                       cache=_Cache(), translate=lambda m, t: TranslatedLines({}, reason="provider_error"))
    assert outcome.status == "unavailable" and outcome.reason == "provider_error"


# -- the shared translator batches, keeps finished batches and names the stop -------------------------------------

def _translator(monkeypatch, provider, count):
    from writing_coach import listening_api

    service = mt.MediaTranslationService(provider)
    monkeypatch.setattr(listening_api, "media_translation_service", lambda: service)
    media = _media(count)
    return listening_api._curated_translator(media), media.transcript.segments


def test_translator_keeps_finished_batches_when_a_later_one_is_limited(monkeypatch):
    limited = mt.TranslationProviderError("x", reason="rate_limited", retry_after=2.0)
    translate, items = _translator(monkeypatch, _Flaky([None, limited]), 47)
    got = translate(items, "vi")
    assert len(got) == 24 and got.reason == "rate_limited" and got.retry_after == 2.0


def test_translator_takes_a_long_transcript_in_windows_instead_of_giving_up(monkeypatch):
    translate, items = _translator(monkeypatch, _Flaky([]), 24 * mt.MAX_TRANSLATION_BATCHES + 30)
    first = translate(items, "vi")
    assert len(first) == 24 * mt.MAX_TRANSLATION_BATCHES and first.reason == ""
    rest = translate([item for item in items if item.segment_id not in first], "vi")
    assert len(first) + len(rest) == len(items)


# -- the pipeline continues the missing lines, boundedly, and records why it stopped ------------------------------

def _meanings_script(world_total, steps):
    """A fake `meanings` whose k-th call reports (done, reason); done only grows, as the persisted cache makes it."""
    calls = []

    def meanings(entry, target):
        done, reason, retry = steps[min(len(calls), len(steps) - 1)]
        calls.append(done)
        status = "ready" if done >= world_total else "partial"
        return SimpleNamespace(status=status, meanings=[object()] * done, provider_calls=1,
                               reason=reason, retry_after=retry)

    return meanings, calls


def _slept(pipeline):
    waits = []
    pipeline._sleep = waits.append
    return waits


def test_pipeline_continues_until_every_line_has_a_meaning(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_PRETRANSLATE_LANGUAGES", "vi")
    meanings, calls = _meanings_script(5, [(2, "rate_limited", 4.0), (5, "", 0.0)])
    store, entry, pipeline = _world(tmp_path, lines=5, meanings=meanings)
    waits = _slept(pipeline)
    assert pipeline._translate(store, entry, "b1", False) == ("ready", {"vi": {"done": 5, "total": 5}})
    assert calls == [2, 5] and waits == [4.0]
    assert store.get(entry.media_id).processing.get("translation_reason", "") == ""


def test_pipeline_gives_up_after_a_bounded_number_of_rounds_and_records_why(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_PRETRANSLATE_LANGUAGES", "vi")
    meanings, calls = _meanings_script(5, [(2, "rate_limited", 1.0)])
    store, entry, pipeline = _world(tmp_path, lines=5, meanings=meanings)
    waits = _slept(pipeline)
    outcome = pipeline._translate(store, entry, "b1", False)
    assert outcome == ("partial", {"vi": {"done": 2, "total": 5}})
    from writing_coach.media_transcript_pipeline import TRANSLATION_MAX_ROUNDS

    assert len(calls) == TRANSLATION_MAX_ROUNDS and len(waits) == TRANSLATION_MAX_ROUNDS - 1
    stored = store.get(entry.media_id)
    assert stored.processing["translation_reason"] == "rate_limited"
    assert media_outcome(stored)["translation"]["reason"] == "rate_limited"


def test_a_wait_is_capped_and_the_total_wait_is_bounded(tmp_path, monkeypatch):
    from writing_coach.media_transcript_pipeline import TRANSLATION_MAX_TOTAL_WAIT, TRANSLATION_MAX_WAIT

    monkeypatch.setenv("MEDIA_PRETRANSLATE_LANGUAGES", "vi")
    meanings, _calls = _meanings_script(5, [(1, "rate_limited", TRANSLATION_MAX_WAIT - 10)])
    store, entry, pipeline = _world(tmp_path, lines=5, meanings=meanings)
    waits = _slept(pipeline)
    pipeline._translate(store, entry, "b1", False)
    assert waits and max(waits) <= TRANSLATION_MAX_WAIT and sum(waits) <= TRANSLATION_MAX_TOTAL_WAIT


def test_a_retry_after_longer_than_one_wait_stops_with_rate_limited_instead_of_sleeping_into_it(tmp_path, monkeypatch):
    from writing_coach.media_transcript_pipeline import TRANSLATION_MAX_WAIT

    monkeypatch.setenv("MEDIA_PRETRANSLATE_LANGUAGES", "vi")
    meanings, calls = _meanings_script(5, [(1, "rate_limited", TRANSLATION_MAX_WAIT + 1)])
    store, entry, pipeline = _world(tmp_path, lines=5, meanings=meanings)
    waits = _slept(pipeline)
    assert pipeline._translate(store, entry, "b1", False) == ("partial", {"vi": {"done": 1, "total": 5}})
    assert len(calls) == 1 and waits == []
    assert store.get(entry.media_id).processing["translation_reason"] == "rate_limited"


def test_a_partial_that_does_not_grow_and_names_no_reason_stops_at_once(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_PRETRANSLATE_LANGUAGES", "vi")
    meanings, calls = _meanings_script(5, [(2, "", 0.0)])
    store, entry, pipeline = _world(tmp_path, lines=5, meanings=meanings)
    waits = _slept(pipeline)
    assert pipeline._translate(store, entry, "b1", False) == ("partial", {"vi": {"done": 2, "total": 5}})
    # Round 1 grew 0 -> 2 and continues; round 2 returned the same 2 with no reason, so it stops: 2 calls, not 5.
    assert len(calls) == 2 and waits == []
    assert store.get(entry.media_id).processing["translation_reason"] == "provider_error"


def test_a_terminal_reason_is_not_retried(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_PRETRANSLATE_LANGUAGES", "vi")
    meanings, calls = _meanings_script(5, [(0, "provider_auth", 0.0)])
    store, entry, pipeline = _world(tmp_path, lines=5, meanings=meanings)
    waits = _slept(pipeline)
    assert pipeline._translate(store, entry, "b1", False) == ("failed", {"vi": {"done": 0, "total": 5}})
    assert len(calls) == 1 and waits == []
    assert store.get(entry.media_id).processing["translation_reason"] == "provider_auth"


def test_an_exception_from_the_provider_path_is_a_provider_error_not_a_swallowed_warning(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_PRETRANSLATE_LANGUAGES", "vi")

    def down(entry, target):
        raise RuntimeError("provider down")

    store, entry, pipeline = _world(tmp_path, lines=5, meanings=down)
    _slept(pipeline)
    assert pipeline._translate(store, entry, "b1", False)[0] == "failed"
    assert store.get(entry.media_id).processing["translation_reason"] == "provider_error"


def test_spend_cap_mid_continuation_ends_partial_with_that_reason(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_PRETRANSLATE_LANGUAGES", "vi")
    meanings, calls = _meanings_script(5, [(2, "rate_limited", 0.0)])
    store, entry, pipeline = _world(tmp_path, lines=5, meanings=meanings)
    _slept(pipeline)
    checks = {"n": 0}

    class Capped(_Ledger):
        def check(self, *_a, **_k):
            checks["n"] += 1
            if checks["n"] > 1:
                raise SpendCapReached("spend_cap_batch_ai", limit=1.0, spent=1.0, scope="batch")

    pipeline._ledger = Capped()
    outcome = pipeline._translate(store, entry, "b1", False)
    assert outcome[0] == "partial" and len(calls) == 1
    assert store.get(entry.media_id).processing["translation_reason"] == "spend_cap"


def test_first_round_spend_cap_is_unchanged_and_names_its_reason(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_PRETRANSLATE_LANGUAGES", "vi")
    meanings, calls = _meanings_script(5, [(5, "", 0.0)])
    store, entry, pipeline = _world(tmp_path, lines=5, meanings=meanings)

    class Capped(_Ledger):
        def check(self, *_a, **_k):
            raise SpendCapReached("spend_cap_batch_ai", limit=1.0, spent=1.0, scope="batch")

    pipeline._ledger = Capped()
    assert pipeline._translate(store, entry, "b1", False)[0] == "spend_cap" and calls == []
    assert store.get(entry.media_id).processing["translation_reason"] == "spend_cap"


# -- the admin record shows the reason beside the counts ------------------------------------------------------------

def test_failed_item_with_stored_lines_keeps_its_reason_in_the_outcome(tmp_path):
    from tests.test_media_lifecycle import _entry

    entry = replace(_entry(), processing={"state": "failed", "reason": "language_mismatch", "translation": "partial",
                                          "translation_counts": {"vi": {"done": 3, "total": 5}},
                                          "translation_reason": "rate_limited"})
    outcome = media_outcome(entry)
    assert outcome["state"] == "failed" and outcome["reason"] == "language_mismatch"
    assert outcome["translation"] == {"state": "partial", "reason": "rate_limited", "counts": {"vi": {"done": 3, "total": 5}}}
