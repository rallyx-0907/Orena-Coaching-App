"""The `word_translation` seam is admitted through a gate, not a queue (D-195, reviewer conditions).

Saturation is a miss, one call per word, a call that never started is cancelled when the tap's wait ends, a word whose
call raised is cooled down, and the log names the exception type only, once a minute.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from writing_coach import reading_lookup
from writing_coach.reading_derived import DerivedCache
from writing_coach.reading_lookup import ReadingLookupService
from writing_coach.reading_translation import ReadingTranslationService

SENTENCE = "The lamp ran out of oil."


class _Engine:
    engine_id = "ai"
    model_version = "x"


@pytest.fixture(autouse=True)
def clean_gate(monkeypatch):
    clock = {"now": 5000.0}
    monkeypatch.setattr(reading_lookup, "_seam_clock", lambda: clock["now"])
    monkeypatch.setattr(reading_lookup, "_seam_pool", ThreadPoolExecutor(max_workers=2))
    monkeypatch.setattr(reading_lookup, "_seam_slots", threading.BoundedSemaphore(2))
    monkeypatch.setattr(reading_lookup, "_seam_inflight", {})
    monkeypatch.setattr(reading_lookup, "_seam_failed", {})
    monkeypatch.setattr(reading_lookup, "_last_logged", {})
    # These tests exercise the gate with tiny budgets; the real floor is pinned by its own test below.
    monkeypatch.setattr(reading_lookup, "SEAM_MIN_WAIT_SECONDS", 0.25)
    yield clock


def _lookup(seam, text="lamp", budget=0.3):
    service = ReadingLookupService(
        None, lambda _w: {"phonetic": ""}, ReadingTranslationService(_Engine(), cache=DerivedCache()),
        budget_seconds=budget, word_translation=seam,
    )
    return service.lookup(text, SENTENCE, "en", "vi").to_dict()["meanings"]


def test_a_saturated_gate_is_a_miss_at_once_and_the_seam_is_not_called(clean_gate) -> None:
    release = threading.Event()
    started: list[str] = []

    def blocking(text, *_rest):
        started.append(text)
        release.wait(5)
        return "x"

    results: list = []
    threads = [threading.Thread(target=lambda w=w: results.append(_lookup(blocking, w, budget=1.0))) for w in ("lamp", "book")]
    for thread in threads:
        thread.start()
    for _ in range(100):
        if len(started) == 2:
            break
        time.sleep(0.02)
    assert len(started) == 2  # both slots are in use
    begun = time.monotonic()
    assert _lookup(blocking, "door") == []  # a third word: no slot, a miss
    assert time.monotonic() - begun < 0.2 and sorted(started) == ["book", "lamp"]
    release.set()
    for thread in threads:
        thread.join(5)


def test_a_word_already_running_is_joined_not_called_twice() -> None:
    release, entered = threading.Event(), threading.Event()
    calls: list[str] = []

    def blocking(text, *_rest):
        calls.append(text)
        entered.set()
        release.wait(5)
        return "đèn"

    out: list = []
    first = threading.Thread(target=lambda: out.append(_lookup(blocking, budget=2.0)))
    first.start()
    assert entered.wait(5)
    second = threading.Thread(target=lambda: out.append(_lookup(blocking, "lamp", budget=2.0)))
    second.start()
    time.sleep(0.2)
    release.set()
    first.join(5)
    second.join(5)
    assert calls == ["lamp"]
    assert out == [[{"text": "đèn", "source": "word_translation"}]] * 2


def test_work_that_never_started_is_cancelled_when_the_wait_ends(monkeypatch) -> None:
    """One worker, two slots: the second call queues behind the first, times out, and must never run late."""

    monkeypatch.setattr(reading_lookup, "_seam_pool", ThreadPoolExecutor(max_workers=1))
    release, entered = threading.Event(), threading.Event()
    ran: list[str] = []

    def seam(text, *_rest):
        ran.append(text)
        entered.set()
        release.wait(5)
        return "x"

    holder = threading.Thread(target=lambda: _lookup(seam, "lamp", budget=2.0))
    holder.start()
    assert entered.wait(5)
    assert _lookup(seam, "book", budget=0.3) == []  # queued, not started, waited 0.3 s
    release.set()
    holder.join(5)
    time.sleep(0.2)
    assert ran == ["lamp"]  # "book" was cancelled: it never ran
    assert reading_lookup._seam_inflight == {}  # and its gate was given back


def test_the_gate_is_given_back_after_every_outcome() -> None:
    assert _lookup(lambda *_a: "đèn")[0]["text"] == "đèn"
    assert _lookup(lambda *_a: None, "book") == []
    for _ in range(5):  # more calls than slots, one after another
        _lookup(lambda *_a: "x", "door")
    assert reading_lookup._seam_slots.acquire(blocking=False) and reading_lookup._seam_slots.acquire(blocking=False)


def test_a_word_whose_call_raised_is_cooled_down_then_asked_again(clean_gate) -> None:
    calls: list[str] = []

    def failing(text, *_rest):
        calls.append(text)
        raise RuntimeError("provider says: the word was lamp")

    assert _lookup(failing) == []
    time.sleep(0.1)  # the done-callback records the failure
    assert _lookup(failing) == []
    assert calls == ["lamp"]  # cooling down: not called again
    assert _lookup(failing, "book") == [] and calls == ["lamp", "book"]  # another word is unaffected
    clean_gate["now"] += reading_lookup._SEAM_FAILURE_SECONDS + 1
    assert _lookup(failing) == []
    assert calls == ["lamp", "book", "lamp"]


def test_failures_are_logged_by_exception_type_only_and_at_most_once_a_minute(clean_gate, caplog) -> None:
    def failing(text, *_rest):
        raise RuntimeError(f"echoed learner text: {text} / {SENTENCE}")

    with caplog.at_level(logging.WARNING, logger="orena.lookup"):
        _lookup(failing, "lamp")
        _lookup(failing, "book")
        _lookup(failing, "door")
    logged = "\n".join(record.getMessage() + (record.exc_text or "") for record in caplog.records)
    assert "RuntimeError" in logged and "word_translation" in logged
    for leaked in ("lamp", "book", "door", "echoed learner text", "ran out"):
        assert leaked not in logged
    assert all(record.exc_info is None for record in caplog.records)
    assert len([r for r in caplog.records if "failed" in r.getMessage()]) == 1  # throttled
    clean_gate["now"] += 61
    with caplog.at_level(logging.WARNING, logger="orena.lookup"):
        _lookup(failing, "pen")
    assert len([r for r in caplog.records if "failed" in r.getMessage()]) == 2


def test_the_request_context_reaches_the_seam() -> None:
    from writing_coach.core.request_context import USER_KEY_CTX, current_user_key

    seen: list[str] = []
    token = USER_KEY_CTX.set("account-7")
    try:
        _lookup(lambda *_a: seen.append(current_user_key()) or "đèn")
    finally:
        USER_KEY_CTX.reset(token)
    assert seen == ["account-7"]


def test_the_seam_always_gets_its_floor_of_the_tap_budget(monkeypatch) -> None:
    """The deterministic layers before the seam may have used the whole 2.0 s budget; a free model answers in 0.7-1.7 s,
    so the seam keeps at least SEAM_MIN_WAIT_SECONDS (D-200 amendment) instead of a quarter second."""

    monkeypatch.setattr(reading_lookup, "SEAM_MIN_WAIT_SECONDS", 1.8)
    assert reading_lookup.SEAM_MIN_WAIT_SECONDS >= 1.8

    def slow(text, *_rest):
        time.sleep(0.6)
        return "cái đèn"

    # The budget is already spent (0.05 s): the old code waited 0.25 s and missed; the floor waits for the answer.
    assert _lookup(slow, budget=0.05) == [{"text": "cái đèn", "source": "word_translation"}]
