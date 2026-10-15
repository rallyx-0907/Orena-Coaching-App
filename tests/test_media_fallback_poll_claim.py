"""The provider poll is claimed atomically, so repeated polling cannot spend twice.

The defect these lock down: the registry held a lock, but `poll()` fetched the
mutable record and then mutated it *outside* that lock, and called the provider
without claiming the right to do so. Two concurrent `/import/status` requests for
one job could therefore both call Supadata - duplicating paid quota - and race
each other's state writes.

Supadata charges per request, so "one provider call in flight per job" is a cost
contract, not only a correctness one. A browser polling once a second for a
90-second import must cost one job, not ninety.
"""

from __future__ import annotations

import dataclasses
import threading

import pytest

from writing_coach.media_fallback import (
    COMPLETED,
    DEFAULT_PROVIDER_START_WORKERS,
    FAILED,
    MAX_PROVIDER_START_WORKERS,
    POLL_IN_FLIGHT,
    PROVIDER_START_WORKERS_ENV,
    PROVIDER_STARTING,
    MediaFallbackJobRegistry,
    MediaFallbackJobSnapshot,
    SupadataMediaFallbackService,
    resolve_start_workers,
)
from writing_coach.media_providers.supadata import (
    SupadataTranscriptJob,
    SupadataTranscriptJobResult,
)

from tests.test_media_fallback import (
    InlineExecutor,
    base_acquisition,
    completed_transcript,
)

OWNER = "learner-1"
LANGUAGE = "en"


class CountingPollClient:
    """Counts provider polls, and can hold each one open on a barrier.

    `hold` lets a test keep a poll genuinely in flight while another caller asks
    for status - the only way to observe the race the fix is about.
    """

    def __init__(self, result, *, hold: threading.Event | None = None) -> None:
        self.result = result
        self.hold = hold
        self.poll_calls: list[tuple[str, str]] = []
        self.entered = threading.Event()
        self.concurrent = 0
        self.max_concurrent = 0
        self._lock = threading.Lock()

    def start(self, source_url: str, preferred_language: str, *, mode: str):
        return SupadataTranscriptJob(job_id="provider-job-1")

    def poll(self, job_id: str, preferred_language: str):
        with self._lock:
            self.poll_calls.append((job_id, preferred_language))
            self.concurrent += 1
            self.max_concurrent = max(self.max_concurrent, self.concurrent)
        self.entered.set()
        try:
            if self.hold is not None:
                self.hold.wait(timeout=5)
            return self.result() if callable(self.result) else self.result
        finally:
            with self._lock:
                self.concurrent -= 1


def service(client, registry: MediaFallbackJobRegistry | None = None):
    return SupadataMediaFallbackService(
        client,
        registry=registry or MediaFallbackJobRegistry(),
        executor=InlineExecutor(),
    )


def started_job(client) -> tuple[SupadataMediaFallbackService, str]:
    """A job whose provider id is already attached, ready to be polled."""

    engine = service(client)
    result = engine.start(
        base_acquisition(),
        owner_key=OWNER,
        learning_language=LANGUAGE,
        target_language="ja",
    )
    return engine, result.job_id


def poll(engine, job_id):
    return engine.poll(job_id, owner_key=OWNER, learning_language=LANGUAGE)


def run_concurrently(fn, count: int) -> list:
    """Fire `count` callers at once and collect their results in order."""

    results: list = [None] * count
    ready = threading.Barrier(count)

    def worker(index: int) -> None:
        ready.wait(timeout=5)
        try:
            results[index] = fn()
        except Exception as exc:  # recorded, then asserted on by the caller
            results[index] = exc

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert not any(t.is_alive() for t in threads), "a status request never returned"
    return results


class HeldPollRound:
    """Keeps one provider poll open until every other caller has been answered.

    Without this the fake provider returns instantly, each caller claims and
    releases in turn, and the test proves nothing about concurrency. Holding the
    first poll open makes the overlap real and the assertion deterministic: no
    timing window, no sleep.
    """

    def __init__(self, callers: int) -> None:
        self.callers = callers
        self.release = threading.Event()
        self._done = 0
        self._lock = threading.Lock()

    def finished(self) -> None:
        with self._lock:
            self._done += 1
            if self._done >= self.callers - 1:
                # Everyone who was going to be turned away has been.
                self.release.set()


def run_held_round(engine, job_id, client, callers: int) -> list:
    round_state = HeldPollRound(callers)
    client.hold = round_state.release

    def call():
        try:
            return poll(engine, job_id)
        finally:
            round_state.finished()

    results = run_concurrently(call, callers)
    client.hold = None
    return results


# --- 1 and 6: concurrent and repeated polling make one provider call ---------

def test_concurrent_status_requests_make_exactly_one_provider_poll() -> None:
    client = CountingPollClient(SupadataTranscriptJobResult(status="processing"))
    engine, job_id = started_job(client)

    results = run_concurrently(lambda: poll(engine, job_id), 2)
    assert client.max_concurrent <= 1, "two provider polls were in flight at once"

    # And with the provider call genuinely held open, the overlap is guaranteed:
    # twelve simultaneous readers buy exactly one poll.
    client.poll_calls.clear()
    results = run_held_round(engine, job_id, client, 12)

    assert len(client.poll_calls) == 1, "twelve concurrent readers must not buy twelve polls"
    assert client.max_concurrent <= 1
    assert {getattr(r, "status", r) for r in results} == {"processing"}
    # Eleven of them were told the truth: a poll is already in flight.
    states = [getattr(r, "provider_state", None) for r in results]
    assert states.count(POLL_IN_FLIGHT) == 11


def test_repeated_browser_polling_cannot_multiply_paid_provider_calls() -> None:
    """A poll loop costs one provider call per round, not one per request."""

    client = CountingPollClient(SupadataTranscriptJobResult(status="processing"))
    engine, job_id = started_job(client)

    for _ in range(5):
        run_held_round(engine, job_id, client, 8)

    # 40 status requests across 5 overlapping rounds: 5 provider calls, not 40.
    assert len(client.poll_calls) == 5
    assert client.max_concurrent <= 1


# --- 2: a second caller while a poll is in flight ----------------------------

def test_second_caller_during_an_in_flight_poll_gets_processing_and_spends_nothing() -> None:
    release = threading.Event()
    client = CountingPollClient(
        SupadataTranscriptJobResult(status="processing"), hold=release)
    engine, job_id = started_job(client)

    first: list = []
    holder = threading.Thread(target=lambda: first.append(poll(engine, job_id)))
    holder.start()
    assert client.entered.wait(timeout=5), "the first poll never reached the provider"

    # The provider call is genuinely open right now.
    second = poll(engine, job_id)
    assert second.status == "processing"
    assert second.provider_state == POLL_IN_FLIGHT, "the claim must be reported honestly"
    assert second.job_id == job_id
    assert len(client.poll_calls) == 1, "the second caller must not contact the provider"

    release.set()
    holder.join(timeout=5)
    assert first and first[0].status == "processing"
    assert len(client.poll_calls) == 1


def test_the_claim_is_released_so_a_later_poll_still_works() -> None:
    client = CountingPollClient(SupadataTranscriptJobResult(status="processing"))
    engine, job_id = started_job(client)

    poll(engine, job_id)
    poll(engine, job_id)
    assert len(client.poll_calls) == 2, "a released claim must be re-claimable"


def test_an_exception_inside_the_provider_poll_still_releases_the_claim() -> None:
    """A claim leaked on an unmodelled error would wedge the job forever."""

    class Exploding(CountingPollClient):
        def poll(self, job_id, preferred_language):
            super().poll(job_id, preferred_language)
            raise RuntimeError("provider client blew up")

    client = Exploding(None)
    engine, job_id = started_job(client)

    with pytest.raises(RuntimeError):
        poll(engine, job_id)
    # Not stuck: the next caller may claim again rather than seeing a permanent
    # phantom in-flight poll.
    with pytest.raises(RuntimeError):
        poll(engine, job_id)
    assert len(client.poll_calls) == 2


# --- 3 and 4: the terminal transitions are atomic ----------------------------

def test_completed_transition_is_atomic_under_concurrency() -> None:
    """Completion is all-or-nothing, however the callers interleave.

    The first wave overlaps the claimed provider poll on purpose: a caller that
    arrives while the poll is in flight is correctly told "processing" (that is
    the cost contract, covered above), so asserting "ready" for an *unordered*
    wave is a timing assumption, not a property of the code (issue #217). The
    poll is therefore held open until every other caller has been turned away,
    which makes the interleaving deterministic. Once it completes, a second
    concurrent wave must see exactly the finished job.
    """

    client = CountingPollClient(
        SupadataTranscriptJobResult(status="completed", transcript=completed_transcript()))
    engine, job_id = started_job(client)

    first_wave = run_held_round(engine, job_id, client, 10)

    assert len(client.poll_calls) == 1
    ready = [r for r in first_wave if r.status == "ready"]
    turned_away = [r for r in first_wave if r.status != "ready"]
    assert len(ready) == 1, "exactly one caller owns the completing poll"
    assert {r.status for r in turned_away} == {"processing"}
    assert {r.provider_state for r in turned_away} == {POLL_IN_FLIGHT}
    # Nobody who was turned away carries a half-written result.
    assert all(r.acquisition.media_object.transcript is None
               or not r.acquisition.media_object.transcript.segments
               for r in turned_away)

    # Now the job is finished: every concurrent caller sees the same finished
    # job - nobody sees a half-written state, and nobody pays again.
    results = run_concurrently(lambda: poll(engine, job_id), 10)

    assert len(client.poll_calls) == 1
    assert {r.status for r in results} == {"ready"}
    assert {r.provider_state for r in results} == {COMPLETED}
    transcripts = {
        len(r.acquisition.media_object.transcript.segments) for r in results
    }
    assert len(transcripts) == 1 and transcripts != {0}
    assert all(r.acquisition.media_object.asset.transcript_available for r in results)

    # And a later poll is served from the record without paying again.
    again = poll(engine, job_id)
    assert again.status == "ready"
    assert len(client.poll_calls) == 1


def test_failed_transition_is_atomic_under_concurrency() -> None:
    client = CountingPollClient(SupadataTranscriptJobResult(status="failed"))
    engine, job_id = started_job(client)

    results = run_concurrently(lambda: poll(engine, job_id), 10)

    assert len(client.poll_calls) == 1
    assert {r.status for r in results} == {"failed"}
    assert {r.failure_kind for r in results} == {"provider_failure"}

    again = poll(engine, job_id)
    assert again.status == "failed"
    assert len(client.poll_calls) == 1, "a settled failure must not be re-polled"


# --- 5: status polling racing the background provider-start ------------------

def test_status_polling_during_provider_start_never_polls_an_empty_provider_id() -> None:
    """The job exists before the provider names it; that gap must not be polled."""

    attach = threading.Event()
    started = threading.Event()

    class SlowStartClient(CountingPollClient):
        def start(self, source_url, preferred_language, *, mode):
            started.set()
            assert attach.wait(timeout=5)
            return SupadataTranscriptJob(job_id="provider-job-1")

    client = SlowStartClient(SupadataTranscriptJobResult(status="processing"))
    registry = MediaFallbackJobRegistry()
    # A real bounded pool here, not the inline double: the race only exists when
    # the start genuinely runs beside the status requests.
    engine = SupadataMediaFallbackService(client, registry=registry)

    result = engine.start(
        base_acquisition(),
        owner_key=OWNER,
        learning_language=LANGUAGE,
        target_language="ja",
    )
    job_id = result.job_id
    assert result.provider_state == PROVIDER_STARTING
    assert started.wait(timeout=5)

    # Hammer status while the provider has not answered yet.
    during = run_concurrently(lambda: poll(engine, job_id), 8)
    assert {r.status for r in during} == {"processing"}
    assert {r.provider_state for r in during} == {PROVIDER_STARTING}
    assert client.poll_calls == [], "no provider poll may happen before the job id exists"

    attach.set()
    for _ in range(200):
        if registry.get(job_id, owner_key=OWNER, learning_language=LANGUAGE).provider_job_id:
            break
        threading.Event().wait(0.01)

    after = poll(engine, job_id)
    assert after.status == "processing"
    assert [call[0] for call in client.poll_calls] == ["provider-job-1"]
    assert all(call[0] for call in client.poll_calls), "an empty provider id was polled"


# --- the service can no longer write job state directly ----------------------

def test_the_registry_hands_out_snapshots_not_writable_records() -> None:
    """REGISTRY_MUTATION_UNDER_LOCK: state changes only through guarded methods."""

    registry = MediaFallbackJobRegistry()
    created = registry.create(
        owner_key=OWNER,
        learning_language=LANGUAGE,
        target_language="ja",
        acquisition=base_acquisition(),
        include_translation=True,
    )
    assert isinstance(created, MediaFallbackJobSnapshot)
    fetched = registry.get(
        created.public_job_id, owner_key=OWNER, learning_language=LANGUAGE)
    assert isinstance(fetched, MediaFallbackJobSnapshot)

    # Frozen: the service layer cannot reach in and set state at all.
    with pytest.raises(dataclasses.FrozenInstanceError):
        fetched.state = FAILED  # type: ignore[misc]

    # And the source proves the poll path no longer mutates a record directly.
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] /
              "writing_coach/media_fallback.py").read_text(encoding="utf-8")
    service_source = source[source.index("class SupadataMediaFallbackService"):]
    for forbidden in ("record.state =", "record.failure_kind =",
                      "record.completed_acquisition ="):
        assert forbidden not in service_source, f"{forbidden} escapes the registry lock"


def test_ownership_is_still_enforced_on_the_claim_path() -> None:
    client = CountingPollClient(SupadataTranscriptJobResult(status="processing"))
    engine, job_id = started_job(client)

    with pytest.raises(KeyError):
        engine.poll(job_id, owner_key="someone-else", learning_language=LANGUAGE)
    with pytest.raises(KeyError):
        engine.poll(job_id, owner_key=OWNER, learning_language="zh")
    assert client.poll_calls == [], "a rejected caller must not reach the provider"


# --- P2: bounded worker configuration ----------------------------------------

def test_worker_configuration_is_bounded_and_never_crashes_startup() -> None:
    assert resolve_start_workers(env={}) == DEFAULT_PROVIDER_START_WORKERS
    assert resolve_start_workers(env={PROVIDER_START_WORKERS_ENV: "8"}) == 8
    assert resolve_start_workers(env={PROVIDER_START_WORKERS_ENV: " 2 "}) == 2

    # An operator typo falls back rather than raising ValueError during startup.
    for bad in ("0", "-4", "abc", "", "   ", "4.5", str(MAX_PROVIDER_START_WORKERS + 1)):
        assert resolve_start_workers(
            env={PROVIDER_START_WORKERS_ENV: bad}
        ) == DEFAULT_PROVIDER_START_WORKERS, bad
    assert resolve_start_workers(True) == DEFAULT_PROVIDER_START_WORKERS
    assert resolve_start_workers(MAX_PROVIDER_START_WORKERS) == MAX_PROVIDER_START_WORKERS

    # Constructing the service with a bad value must not raise.
    import os
    previous = os.environ.get(PROVIDER_START_WORKERS_ENV)
    os.environ[PROVIDER_START_WORKERS_ENV] = "not-a-number"
    try:
        engine = SupadataMediaFallbackService(CountingPollClient(None))
        assert engine is not None
    finally:
        if previous is None:
            os.environ.pop(PROVIDER_START_WORKERS_ENV, None)
        else:
            os.environ[PROVIDER_START_WORKERS_ENV] = previous
