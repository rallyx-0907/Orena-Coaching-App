"""A long transcript finishes translating by a bounded, deferred continuation (D-211, PROPOSED).

Trial evidence: VOA (78 lines) ended `failed 0/78` and then `partial 24/78`, both `rate_limited`. The key's allowance is
8000 tokens a minute (docs/ORENA_AI_COST_REDUCTION_PLAN.md) and one 24-line request reserves about 2.8k of it, so two or
three requests a minute fit; the rest has to wait for the window, not be abandoned. Providers here are fakes; nothing
reaches a network."""
from __future__ import annotations

import logging
from dataclasses import replace
from types import SimpleNamespace

import pytest

from tests.test_media_import_pipeline_reasons import _Ledger, _world
from tests.test_media_translation_groq import FakeResponse, install, segments
from writing_coach import media_translation as mt
from writing_coach import media_transcript_pipeline as mtp
from writing_coach.admin_content import media_outcome
from writing_coach.media_spend import SpendCapReached


def _setup(tmp_path, monkeypatch, *, lines, per_call, retry_after=30.0, never=False):
    """A held item and a provider that adds `per_call` lines per call, then is rate limited until the next call."""
    monkeypatch.setenv("MEDIA_PRETRANSLATE_LANGUAGES", "vi")
    monkeypatch.setenv("MEDIA_PIPELINE_INLINE", "1")
    state = {"done": 0, "calls": 0}

    def meanings(entry, target):
        state["calls"] += 1
        if not never:
            state["done"] = min(lines, state["done"] + per_call)
        done = state["done"]
        if done >= lines:
            return SimpleNamespace(status="ready", meanings=[object()] * done, provider_calls=1, reason="", retry_after=0.0)
        return SimpleNamespace(status="partial", meanings=[object()] * done, provider_calls=1,
                               reason="rate_limited", retry_after=retry_after)

    store, entry, pipeline = _world(tmp_path, lines=lines, meanings=meanings)
    held = store.update_if_present(entry.media_id, lambda e: replace(
        e, processing={"state": "held", "stage": "ready", "reason": "rights_unknown", "batch_id": "b1", "attempts": 1}))
    scheduled: list[tuple[float, object]] = []
    now = [1_000_000.0]
    pipeline._schedule = lambda delay, callback: scheduled.append((delay, callback))
    pipeline._clock = lambda: now[0]
    pipeline._sleep = lambda _s: None
    return store, held, pipeline, scheduled, now, state


def _first_run(store, entry, pipeline):
    """What `_run` does after the lesson is stored: translate, then maybe defer, then restore the item's own state."""
    stop: dict = {}
    outcome, counts = pipeline._translate(store, entry, "b1", False, stop=stop)
    outcome = pipeline._defer_translation(store, entry, outcome, stop)
    pipeline._write_processing(store, entry, state="held", stage="ready", translation=outcome, translation_counts=counts)
    return outcome, counts


def _drain(scheduled, now, limit=50):
    """Fire the due timers one by one, the clock moving to each."""
    fired = 0
    while scheduled and fired < limit:
        delay, callback = scheduled.pop(0)
        now[0] += delay
        callback()
        fired += 1
    return fired


def test_a_rate_limited_rest_is_deferred_with_the_providers_wait_and_the_item_stays_held(tmp_path, monkeypatch):
    store, entry, pipeline, scheduled, now, _state = _setup(tmp_path, monkeypatch, lines=20, per_call=1, retry_after=40.0)
    outcome, counts = _first_run(store, entry, pipeline)
    # The in-job rounds stop when their own wait budget is spent, not when the transcript is done.
    assert outcome == "deferred" and 0 < counts["vi"]["done"] < 20 and counts["vi"]["total"] == 20
    stored = store.get(entry.media_id).processing
    assert stored["state"] == "held" and stored["reason"] == "rights_unknown"  # the item itself is untouched
    assert stored["translation"] == "deferred" and stored["translation_reason"] == "rate_limited"
    record = stored["translation_continuation"]
    assert record["attempt"] == 1 and record["max_attempts"] == mtp.CONTINUATION_MAX_ATTEMPTS
    assert [delay for delay, _ in scheduled] == [40.0]  # the provider's own Retry-After
    shown = media_outcome(store.get(entry.media_id))["translation"]
    assert shown["state"] == "deferred" and shown["continuation"]["attempt"] == 1 and "next_at" in shown["continuation"]


def test_a_long_transcript_finishes_across_continuations_and_stays_held(tmp_path, monkeypatch):
    store, entry, pipeline, scheduled, now, state = _setup(tmp_path, monkeypatch, lines=78, per_call=8)
    assert _first_run(store, entry, pipeline)[0] == "deferred"
    assert _drain(scheduled, now) >= 1
    stored = store.get(entry.media_id).processing
    assert state["done"] == 78
    assert stored["translation"] == "ready" and stored["translation_counts"] == {"vi": {"done": 78, "total": 78}}
    assert stored["translation_reason"] == "" and stored["translation_continuation"] == {}
    assert stored["state"] == "held" and stored["reason"] == "rights_unknown"
    assert scheduled == []


def test_the_number_of_attempts_is_bounded_and_the_end_is_honest(tmp_path, monkeypatch):
    store, entry, pipeline, scheduled, now, state = _setup(tmp_path, monkeypatch, lines=10, per_call=0, retry_after=25.0, never=True)
    assert _first_run(store, entry, pipeline)[0] == "deferred"
    fired = _drain(scheduled, now)
    assert fired == mtp.CONTINUATION_MAX_ATTEMPTS
    stored = store.get(entry.media_id).processing
    assert stored["translation"] == "failed" and stored["translation_reason"] == "rate_limited"
    assert stored["translation_continuation"] == {} and stored["state"] == "held"
    assert scheduled == []


def test_the_total_time_budget_ends_the_continuation(tmp_path, monkeypatch):
    monkeypatch.setattr(mtp, "CONTINUATION_BUDGET_SECONDS", 700.0)
    store, entry, pipeline, scheduled, now, _state = _setup(tmp_path, monkeypatch, lines=10, per_call=0, retry_after=200.0, never=True)
    assert _first_run(store, entry, pipeline)[0] == "deferred"
    # 200 s waits inside a 700 s budget: three runs fit (at 200, 400, 600 s), a fourth wait would end at 800 s.
    fired = _drain(scheduled, now)
    assert fired == 3 and fired < mtp.CONTINUATION_MAX_ATTEMPTS
    stored = store.get(entry.media_id).processing
    assert stored["translation"] == "failed" and stored["translation_continuation"] == {}


def test_a_wait_longer_than_one_window_is_not_scheduled_at_all(tmp_path, monkeypatch):
    # A daily allowance asks for hours: promising a continuation inside the budget would be false.
    store, entry, pipeline, scheduled, now, _state = _setup(
        tmp_path, monkeypatch, lines=10, per_call=1, retry_after=mtp.CONTINUATION_MAX_DELAY + 1)
    outcome, counts = _first_run(store, entry, pipeline)
    assert outcome == "partial" and scheduled == []
    stored = store.get(entry.media_id).processing
    # Not dropped silently (D-214 P2-3): the item stays held and partial, the reason says why no continuation, the ask is kept.
    assert stored["translation_reason"] == "rate_limited_long_wait" and not stored.get("translation_continuation")
    assert stored["translation_retry_after"] == mtp.CONTINUATION_MAX_DELAY + 1
    assert stored["state"] == "held" and stored["translation"] == "partial"


def test_an_unknown_wait_uses_one_window_and_a_short_one_is_raised_to_the_floor(tmp_path, monkeypatch):
    store, entry, pipeline, scheduled, now, _state = _setup(tmp_path, monkeypatch, lines=10, per_call=1, retry_after=0.0)
    _first_run(store, entry, pipeline)
    assert [d for d, _ in scheduled] == [mtp.CONTINUATION_DEFAULT_DELAY]
    store2, entry2, pipeline2, scheduled2, _now2, _s2 = _setup(tmp_path / "b", monkeypatch, lines=10, per_call=1, retry_after=2.0)
    _first_run(store2, entry2, pipeline2)
    assert [d for d, _ in scheduled2] == [mtp.CONTINUATION_MIN_DELAY]


def test_a_continuation_checks_the_spend_cap_and_ends_with_that_reason(tmp_path, monkeypatch):
    store, entry, pipeline, scheduled, now, _state = _setup(tmp_path, monkeypatch, lines=20, per_call=1)
    assert _first_run(store, entry, pipeline)[0] == "deferred"

    class Capped(_Ledger):
        def check(self, *_a, **_k):
            raise SpendCapReached("spend_cap_batch_ai", limit=1.0, spent=1.0, scope="batch")

    pipeline._ledger = Capped()
    _drain(scheduled, now)
    stored = store.get(entry.media_id).processing
    assert stored["translation"] == "spend_cap" and stored["translation_reason"] == "spend_cap"
    assert stored["translation_continuation"] == {} and scheduled == []
    assert stored["state"] == "held"


def test_a_terminal_failure_in_a_continuation_is_not_asked_again(tmp_path, monkeypatch):
    store, entry, pipeline, scheduled, now, _state = _setup(tmp_path, monkeypatch, lines=20, per_call=1)
    assert _first_run(store, entry, pipeline)[0] == "deferred"
    pipeline._meanings = lambda e, t: SimpleNamespace(status="partial", meanings=[object()] * 5, provider_calls=1,
                                                      reason="provider_auth", retry_after=0.0)
    _drain(scheduled, now)
    stored = store.get(entry.media_id).processing
    assert stored["translation"] == "partial" and stored["translation_reason"] == "provider_auth"
    assert stored["translation_continuation"] == {} and scheduled == []


def test_a_rerun_of_the_item_wins_over_a_pending_continuation(tmp_path, monkeypatch):
    store, entry, pipeline, scheduled, now, state = _setup(tmp_path, monkeypatch, lines=20, per_call=1)
    assert _first_run(store, entry, pipeline)[0] == "deferred"
    calls = state["calls"]
    store.update_if_present(entry.media_id, lambda e: replace(e, processing={**e.processing, "state": "queued"}))
    delay, callback = scheduled.pop(0)
    now[0] += delay
    callback()
    assert state["calls"] == calls  # nothing ran; it looks again after one minimum wait
    assert [d for d, _ in scheduled] == [mtp.CONTINUATION_MIN_DELAY]


def test_a_stale_timer_does_nothing_before_next_at(tmp_path, monkeypatch):
    store, entry, pipeline, scheduled, now, state = _setup(tmp_path, monkeypatch, lines=20, per_call=1, retry_after=40.0)
    assert _first_run(store, entry, pipeline)[0] == "deferred"
    calls = state["calls"]
    _delay, callback = scheduled.pop(0)
    now[0] += 5.0  # long before the 40 s are up
    callback()
    assert state["calls"] == calls and scheduled == []
    now[0] += 40.0
    callback()  # the same callback, now due, does run
    assert state["calls"] > calls


def test_an_archived_item_gets_no_provider_call(tmp_path, monkeypatch):
    store, entry, pipeline, scheduled, now, state = _setup(tmp_path, monkeypatch, lines=20, per_call=1)
    assert _first_run(store, entry, pipeline)[0] == "deferred"
    calls = state["calls"]
    store.update_if_present(entry.media_id, lambda e: replace(e, status="archived"))
    _drain(scheduled, now)
    assert state["calls"] == calls


def test_an_item_archived_between_rounds_stops_the_attempt_before_the_next_call(tmp_path, monkeypatch):
    store, entry, pipeline, scheduled, now, state = _setup(tmp_path, monkeypatch, lines=40, per_call=1)
    assert _first_run(store, entry, pipeline)[0] == "deferred"
    calls = state["calls"]

    def meanings(e, target):
        state["calls"] += 1
        state["done"] += 1
        # Progress with no stated reason: the attempt would go straight on to a second round.
        store.update_if_present(entry.media_id, lambda fresh: replace(fresh, status="archived"))
        return SimpleNamespace(status="partial", meanings=[object()] * state["done"], provider_calls=1, reason="", retry_after=0.0)

    pipeline._meanings = meanings
    _drain(scheduled, now)
    assert state["calls"] == calls + 1


def test_a_restart_arms_the_pending_continuation_again(tmp_path, monkeypatch):
    store, entry, pipeline, scheduled, now, _state = _setup(tmp_path, monkeypatch, lines=20, per_call=1, retry_after=50.0)
    assert _first_run(store, entry, pipeline)[0] == "deferred"
    scheduled.clear()
    now[0] += 20.0  # 30 s of the 50 s wait remain when the process comes back
    pipeline.recover(store, None)
    assert [round(d) for d, _ in scheduled] == [30]


def test_item_state_and_other_fields_are_untouched_by_a_continuation(tmp_path, monkeypatch):
    store, entry, pipeline, scheduled, now, _state = _setup(tmp_path, monkeypatch, lines=12, per_call=2)
    before = store.get(entry.media_id)
    assert _first_run(store, entry, pipeline)[0] == "deferred"
    _drain(scheduled, now)
    after = store.get(entry.media_id)
    assert after.status == before.status and after.lesson == before.lesson
    assert after.processing["state"] == "held" and after.processing["stage"] == "ready"


def test_a_429_is_logged_with_the_quota_headers_and_no_credential(monkeypatch, caplog):
    headers = {"retry-after": "9", "x-ratelimit-remaining-tokens": "120", "x-ratelimit-reset-tokens": "9s",
               "x-ratelimit-remaining-requests": "800", "authorization": "Bearer secret-value"}
    install(monkeypatch, FakeResponse({}, status=429, headers=headers))
    with caplog.at_level(logging.WARNING, logger="writing_coach.media_translation"):
        with pytest.raises(mt.TranslationProviderError):
            mt.GroqTranslationProvider("secret-key", model="m").translate_batch("en", "vi", segments("One."))
    text = " ".join(record.getMessage() for record in caplog.records)
    assert "x-ratelimit-remaining-tokens" in text and "x-ratelimit-reset-tokens" in text
    assert "secret" not in text
