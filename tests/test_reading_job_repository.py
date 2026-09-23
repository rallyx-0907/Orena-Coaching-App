"""The durable queue: a restart loses nothing, and no job runs twice.

The registry this replaces (`media_fallback.py`) keeps jobs in a process
dictionary, so a container restart drops every pending import silently. These
tests hold the properties that make a table better than that dictionary:
work survives the process, a claim is exclusive, a crashed worker's job comes
back, a job that keeps killing its worker eventually fails instead of cycling,
and the same submission never becomes two jobs.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine, select  # noqa: E402

from writing_coach.persistence.models import Base, ReadingIngestionJob  # noqa: E402
from writing_coach.persistence.reading_job_repository import (  # noqa: E402
    MAX_JOB_PAGE,
    ReadingJobRepository,
)

SOURCE = uuid.UUID("0a52e5d0-0000-4000-8000-000000000001")


@pytest.fixture()
def repository(tmp_path):
    """A real file-backed SQLite database: a new engine can reopen it, which
    is how "a restart loses nothing" is proved rather than asserted."""
    url = f"sqlite+pysqlite:///{tmp_path / 'jobs.db'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            ReadingIngestionJob.__table__.metadata.tables["reading_sources"].insert(),
            {
                "id": SOURCE, "slug": "orena-manual", "name": "Manual paste",
                "source_type": "manual", "state": "active", "languages": ["en", "zh"],
                "topic_hints": [], "polling_policy": {}, "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            },
        )
    repository = ReadingJobRepository(engine)
    repository.url = url  # the test reopens this to simulate a restart
    return repository


def _enqueue(repository, *, request_hash="hash-1", text="The river rose overnight."):
    return repository.enqueue(
        source_id=str(SOURCE),
        job_type="ingest_text",
        input_json={"kind": "text", "text": text},
        request_hash=request_hash,
        submitted_by="admin@example.com",
    )


# ---- durability -------------------------------------------------------------

def test_a_queued_job_survives_the_process_that_created_it(repository):
    job = _enqueue(repository)
    reopened = ReadingJobRepository(create_engine(repository.url))
    restored = reopened.get_job(job["id"])
    assert restored["status"] == "queued"
    assert restored["input_json"]["text"] == "The river rose overnight."


def test_a_job_claimed_before_a_crash_is_still_there_afterwards(repository):
    job = _enqueue(repository)
    repository.claim("worker-1")
    reopened = ReadingJobRepository(create_engine(repository.url))
    assert reopened.get_job(job["id"])["status"] == "running"


# ---- idempotency ------------------------------------------------------------

def test_the_same_submission_twice_is_one_job(repository):
    first = _enqueue(repository)
    second = _enqueue(repository)
    assert second["duplicate"] is True
    assert second["id"] == first["id"]


def test_a_text_whose_job_failed_can_be_submitted_again(repository):
    first = _enqueue(repository)
    repository.claim("worker-1")
    repository.fail(first["id"], worker_id="worker-1", code="fetch_failed", message="upstream refused", retry_in=None)
    second = _enqueue(repository)
    assert second["duplicate"] is False and second["id"] != first["id"]


def test_admin_retry_makes_a_new_job_and_leaves_the_failure_readable(repository):
    first = _enqueue(repository)
    repository.claim("worker-1")
    repository.fail(first["id"], worker_id="worker-1", code="fetch_failed", message="upstream refused", retry_in=None)
    retried = repository.retry(first["id"], actor="admin@example.com")
    assert retried["id"] != first["id"] and retried["status"] == "queued"
    failed = repository.get_job(first["id"])
    assert failed["status"] == "failed" and failed["last_error_code"] == "fetch_failed"


# ---- claiming ---------------------------------------------------------------

def test_a_claim_takes_the_oldest_due_job_and_only_once(repository):
    first = _enqueue(repository, request_hash="a", text="first")
    second = _enqueue(repository, request_hash="b", text="second")
    assert repository.claim("worker-1")["id"] == first["id"]
    assert repository.claim("worker-2")["id"] == second["id"]
    assert repository.claim("worker-3") is None


def test_the_claim_stamps_the_worker_the_attempt_and_the_heartbeat(repository):
    _enqueue(repository)
    claimed = repository.claim("worker-1")
    assert claimed["claimed_by"] == "worker-1"
    assert claimed["attempt"] == 1
    assert claimed["status"] == "running" and claimed["stage"] == "fetching"
    assert claimed["heartbeat_at"] is not None and claimed["started_at"] is not None


def test_a_job_waiting_for_its_backoff_is_not_claimed_yet(repository):
    job = _enqueue(repository)
    repository.claim("worker-1")
    repository.fail(job["id"], worker_id="worker-1", code="fetch_failed", message="timeout", retry_in=timedelta(minutes=5))
    assert repository.claim("worker-2") is None
    assert repository.claim("worker-2", now=datetime.now(UTC) + timedelta(minutes=6))["id"] == job["id"]


# ---- crash recovery ---------------------------------------------------------

def test_a_stranded_job_comes_back_after_its_heartbeat_goes_quiet(repository):
    job = _enqueue(repository)
    repository.claim("worker-1")
    later = datetime.now(UTC) + timedelta(minutes=10)
    assert repository.reap_stale(timedelta(minutes=5), now=later) == 1
    recovered = repository.get_job(job["id"])
    assert recovered["status"] == "queued" and recovered["claimed_by"] == ""
    assert recovered["last_error_code"] == "worker_lost"


def test_a_live_worker_keeps_its_job_by_reporting_in(repository):
    job = _enqueue(repository)
    repository.claim("worker-1")
    later = datetime.now(UTC) + timedelta(minutes=10)
    repository.heartbeat(job["id"], "worker-1", now=later)
    assert repository.reap_stale(timedelta(minutes=5), now=later) == 0
    assert repository.get_job(job["id"])["status"] == "running"


def test_a_late_worker_cannot_finish_a_job_that_was_taken_from_it(repository):
    """The zombie-worker sequence, deterministic and single-threaded.

    A worker that stalls past the stale window loses its job to the reaper and
    to whoever claims it next. If it then wakes and reports, that report must
    not land: it would finish, fail or re-queue a job another worker is in the
    middle of, and overwrite the result with a stale one.
    """
    job = _enqueue(repository)
    moment = datetime.now(UTC)
    late = repository.claim("worker-a", now=moment)
    repository.reap_stale(timedelta(minutes=5), now=moment + timedelta(minutes=10))
    fresh = repository.claim("worker-b", now=moment + timedelta(minutes=11))
    assert fresh["id"] == late["id"] and fresh["claimed_by"] == "worker-b"

    assert repository.complete(job["id"], worker_id="worker-a", result_kind="article_created") is False
    assert repository.fail(job["id"], worker_id="worker-a", code="boom", message="", retry_in=None) is False
    assert repository.advance_stage(job["id"], "analyzing", worker_id="worker-a") is False

    still_running = repository.get_job(job["id"])
    assert still_running["status"] == "running" and still_running["claimed_by"] == "worker-b"
    assert repository.complete(job["id"], worker_id="worker-b", result_kind="article_created") is True
    assert repository.get_job(job["id"])["status"] == "completed"


def test_the_reaper_leaves_a_job_whose_worker_reported_in_after_the_read(repository):
    """The reaper's write carries its own predicate, so a heartbeat that lands
    between deciding and writing keeps the job with its worker."""
    job = _enqueue(repository)
    moment = datetime.now(UTC)
    repository.claim("worker-a", now=moment)
    repository.heartbeat(job["id"], "worker-a", now=moment + timedelta(minutes=9))
    assert repository.reap_stale(timedelta(minutes=5), now=moment + timedelta(minutes=10)) == 0
    assert repository.get_job(job["id"])["claimed_by"] == "worker-a"


def test_a_queued_job_with_no_attempts_left_is_swept_rather_than_left_pending(repository):
    """The claim refuses a job with no attempts left, so nothing else would
    ever look at it again: it would sit in Imports forever as pending work
    that cannot run. The sweep is what closes that loop."""
    job = _enqueue(repository)
    with repository.engine.begin() as connection:
        connection.execute(
            ReadingIngestionJob.__table__.update()
            .where(ReadingIngestionJob.id == uuid.UUID(job["id"]))
            .values(attempt=3, max_attempts=3)
        )
    assert repository.claim("worker-1") is None
    assert repository.reap_stale(timedelta(minutes=5)) == 1
    swept = repository.get_job(job["id"])
    assert swept["status"] == "failed" and swept["last_error_code"] == "attempts_exhausted"


def test_a_job_that_keeps_killing_its_worker_fails_instead_of_cycling(repository):
    job = _enqueue(repository)
    moment = datetime.now(UTC)
    for _ in range(3):
        assert repository.claim("worker-1", now=moment) is not None
        moment += timedelta(minutes=10)
        repository.reap_stale(timedelta(minutes=5), now=moment)
    assert repository.get_job(job["id"])["status"] == "failed"
    assert repository.claim("worker-1", now=moment + timedelta(hours=1)) is None


# ---- results and listing ----------------------------------------------------

def test_a_completed_job_records_what_it_produced(repository):
    job = _enqueue(repository)
    repository.claim("worker-1")
    repository.complete(job["id"], worker_id="worker-1", result_kind="article_created", article_id=None, source_item_id=None)
    done = repository.get_job(job["id"])
    assert done["status"] == "completed" and done["stage"] == "done"
    assert done["result_kind"] == "article_created" and done["finished_at"] is not None


def test_a_duplicate_is_a_completed_job_not_a_failure(repository):
    job = _enqueue(repository)
    repository.claim("worker-1")
    repository.complete(job["id"], worker_id="worker-1", result_kind="duplicate", article_id=None, source_item_id=None)
    assert repository.get_job(job["id"])["status"] == "completed"


def test_the_admin_list_is_paginated_newest_first_and_bounded(repository):
    for index in range(5):
        _enqueue(repository, request_hash=f"h{index}", text=f"text {index}")
    page = repository.list_jobs(limit=2)
    assert len(page["items"]) == 2 and page["next_cursor"]
    second = repository.list_jobs(limit=2, cursor=page["next_cursor"])
    assert len(second["items"]) == 2
    assert {item["id"] for item in page["items"]} & {item["id"] for item in second["items"]} == set()
    assert len(repository.list_jobs(limit=10_000)["items"]) <= MAX_JOB_PAGE


def test_the_job_list_carries_no_submitted_payload(repository):
    _enqueue(repository, text="a body an admin pasted")
    item = repository.list_jobs(limit=1)["items"][0]
    assert "input_json" not in item
    assert set(item) >= {"id", "status", "stage", "job_type", "attempt", "created_at"}


def test_failing_without_a_retry_ends_the_job_and_frees_the_hash(repository):
    job = _enqueue(repository)
    repository.claim("worker-1")
    repository.fail(job["id"], worker_id="worker-1", code="unsafe_url", message="private address", retry_in=None)
    failed = repository.get_job(job["id"])
    assert failed["status"] == "failed" and failed["finished_at"] is not None
    with repository.engine.connect() as connection:
        live = connection.execute(
            select(ReadingIngestionJob.id).where(
                ReadingIngestionJob.status.in_(("queued", "running"))
            )
        ).all()
    assert live == []


# ---- who is doing the work --------------------------------------------------

def test_the_registry_names_every_worker_holding_work(repository):
    _enqueue(repository, request_hash="h-a", text="one")
    _enqueue(repository, request_hash="h-b", text="two")
    repository.claim("worker-a")
    repository.claim("worker-b")
    workers = repository.workers(stale_after=timedelta(minutes=5))
    assert {entry["worker_id"] for entry in workers} == {"worker-a", "worker-b"}
    assert all(entry["running"] == 1 and entry["state"] == "working" for entry in workers)
    assert all(entry["last_seen_at"] for entry in workers)


def test_a_worker_that_stopped_reporting_is_stale_not_absent(repository):
    _enqueue(repository)
    started = datetime(2026, 9, 23, 8, 0, tzinfo=UTC)
    repository.claim("worker-gone", now=started)
    workers = repository.workers(
        stale_after=timedelta(minutes=5), now=started + timedelta(minutes=9)
    )
    assert [(entry["worker_id"], entry["state"]) for entry in workers] == [
        ("worker-gone", "stale")
    ]
    assert workers[0]["heartbeat_age_seconds"] >= 540
    assert workers[0]["running"] == 1


def test_a_worker_that_finished_is_idle_rather_than_missing(repository):
    job = _enqueue(repository)
    moment = datetime(2026, 9, 23, 8, 0, tzinfo=UTC)
    repository.claim("worker-a", now=moment)
    repository.complete(
        job["id"], worker_id="worker-a", result_kind="article",
        article_id=None, source_item_id=None, now=moment,
    )
    workers = repository.workers(
        stale_after=timedelta(minutes=5), now=moment + timedelta(minutes=1)
    )
    assert [(entry["worker_id"], entry["state"], entry["running"]) for entry in workers] == [
        ("worker-a", "idle", 0)
    ]


def test_a_worker_nobody_has_heard_from_leaves_the_registry(repository):
    job = _enqueue(repository)
    moment = datetime(2026, 9, 23, 8, 0, tzinfo=UTC)
    repository.claim("worker-a", now=moment)
    repository.complete(
        job["id"], worker_id="worker-a", result_kind="article",
        article_id=None, source_item_id=None, now=moment,
    )
    assert repository.workers(
        stale_after=timedelta(minutes=5), now=moment + timedelta(hours=2)
    ) == []


def test_the_registry_puts_the_stale_worker_first(repository):
    _enqueue(repository, request_hash="h-a", text="one")
    _enqueue(repository, request_hash="h-b", text="two")
    started = datetime(2026, 9, 23, 8, 0, tzinfo=UTC)
    repository.claim("worker-stalled", now=started)
    repository.claim("worker-fine", now=started + timedelta(minutes=9))
    workers = repository.workers(
        stale_after=timedelta(minutes=5), now=started + timedelta(minutes=9)
    )
    assert [entry["worker_id"] for entry in workers] == ["worker-stalled", "worker-fine"]
