"""The Reading engine's durable queue - `reading_ingestion_jobs`.

Schema: `migrations/proposed/20260924_0015_reading_content_engine.py` -
reviewed (round 1 `CHANGES REQUIRED`, revised, re-review pending), not yet
applied to any runtime. See
`docs/project/READING_CONTENT_ENGINE_SCHEMA_REVIEW_REQUEST.md`.

Why a table and not a dictionary: the registry this replaces
(`writing_coach/media_fallback.py`) holds jobs in process memory, so a
container restart drops every pending import with no trace. A table survives
the process, and every property below follows from that one decision.

Claiming is one `UPDATE` whose target comes from a locking subquery - never a
read followed by a later write. PostgreSQL renders `FOR UPDATE SKIP LOCKED`,
so two workers never take the same row and a hung job never blocks the ones
behind it; SQLite drops the locking clause, and the repeated
`status = 'queued'` in the outer `WHERE` is the whole of the exclusion there.

`attempt` is consumed by the *claim*, not by the failure: a worker that dies
before it can report anything has still used one of its chances, which is what
stops a job that reliably kills its worker from cycling forever. The claim
therefore also refuses a job that has no attempts left, so the database's
`attempt <= max_attempts` bound is never the thing that reports the exhaustion.

**A worker can lose a job it is still working on.** If it stalls past the
stale window, the reaper returns the job and someone else claims it. Every
mutating path therefore carries `_owned_by(job, worker)` - still running, still
this worker's - so a late report lands nowhere instead of finishing, failing or
re-queueing a job another worker is in the middle of. That is the difference
between a queue and a shared mutable row.
"""
from __future__ import annotations

import base64
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import case, select, update
from sqlalchemy.engine import Engine

from writing_coach.persistence.models import ReadingIngestionJob

DEFAULT_JOB_PAGE = 25
MAX_JOB_PAGE = 100
DEFAULT_MAX_ATTEMPTS = 3
# The claim's own stage. A worker names the later ones as it goes.
FIRST_STAGE = "fetching"
LIVE_STATUSES = ("queued", "running")


class InvalidCursor(ValueError):
    """A `cursor` value that does not decode to this query's own shape."""


def _now(value: datetime | None) -> datetime:
    return value or datetime.now(UTC)


def _lookup_uuid(value: Any) -> uuid.UUID | None:
    """The id of a job that could exist, or None for a string that never can."""
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def _aware(value: Any) -> datetime | None:
    """SQLite hands back naive datetimes; the runtime is timestamptz.

    Normalizing here rather than at every call site keeps comparisons honest
    on both backends - a naive value read back and compared against an aware
    `now()` would raise, which is exactly the kind of failure that only shows
    up in the hermetic suite.
    """
    if not isinstance(value, datetime):
        return None
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)


def _iso(value: Any) -> str | None:
    moment = _aware(value)
    return moment.isoformat() if moment else None


def _encode_cursor(created_at: datetime, job_id: str) -> str:
    payload = json.dumps({"created_at": created_at.isoformat(), "id": job_id}).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii")


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")))
        return datetime.fromisoformat(payload["created_at"]), str(payload["id"])
    except Exception as exc:  # noqa: BLE001 - any malformed cursor is the same outcome
        raise InvalidCursor(cursor) from exc


def _job(row: Any) -> dict[str, Any]:
    """One job, in full. The admin list uses `_job_summary` instead."""
    return {
        "id": str(row.id),
        "job_type": row.job_type,
        "source_id": str(row.source_id),
        "input_json": dict(row.input_json or {}),
        "input_asset_key": row.input_asset_key,
        "request_hash": row.request_hash,
        "status": row.status,
        "stage": row.stage,
        "attempt": row.attempt,
        "max_attempts": row.max_attempts,
        "last_error": row.last_error,
        "last_error_code": row.last_error_code,
        "next_retry_at": _iso(row.next_retry_at),
        "heartbeat_at": _iso(row.heartbeat_at),
        "claimed_by": row.claimed_by,
        "result_kind": row.result_kind,
        "result_article_id": str(row.result_article_id) if row.result_article_id else None,
        "result_source_item_id": (
            str(row.result_source_item_id) if row.result_source_item_id else None
        ),
        "submitted_by": row.submitted_by,
        "created_at": _iso(row.created_at),
        "started_at": _iso(row.started_at),
        "finished_at": _iso(row.finished_at),
    }


def _job_summary(row: Any) -> dict[str, Any]:
    """What Admin -> Imports renders: state, never the submitted payload.

    The payload can be a whole pasted article; a list of twenty-five jobs must
    not carry twenty-five article bodies to draw twenty-five rows (SS46.2).
    """
    return {
        "id": str(row.id),
        "job_type": row.job_type,
        "status": row.status,
        "stage": row.stage,
        "attempt": row.attempt,
        "max_attempts": row.max_attempts,
        "last_error_code": row.last_error_code,
        "result_kind": row.result_kind,
        "result_article_id": str(row.result_article_id) if row.result_article_id else None,
        "submitted_by": row.submitted_by,
        "created_at": _iso(row.created_at),
        "finished_at": _iso(row.finished_at),
    }


class ReadingJobRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    # ---- submission ------------------------------------------------------
    def enqueue(
        self,
        *,
        source_id: str,
        job_type: str,
        input_json: dict[str, Any],
        request_hash: str,
        submitted_by: str,
        input_asset_key: str = "",
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Queue one submission, or hand back the live job that already is it.

        The `request_hash` unique index (live submissions only) is the actual
        guarantee; this pre-check only avoids the round trip for the common
        double-click. A text whose earlier job failed is not live, so it can
        be submitted again - that is the difference between "idempotent" and
        "never again".
        """
        moment = _now(now)
        with self.engine.begin() as connection:
            existing = connection.execute(
                select(ReadingIngestionJob).where(
                    ReadingIngestionJob.request_hash == request_hash,
                    ReadingIngestionJob.status.in_(LIVE_STATUSES),
                )
            ).first()
            if existing is not None:
                return {**_job(existing), "duplicate": True}
            job_id = uuid.uuid4()
            connection.execute(
                ReadingIngestionJob.__table__.insert(),
                {
                    "id": job_id,
                    "job_type": job_type,
                    "source_id": uuid.UUID(str(source_id)),
                    "input_json": dict(input_json or {}),
                    "input_asset_key": input_asset_key,
                    "request_hash": request_hash,
                    "status": "queued",
                    "stage": "queued",
                    "attempt": 0,
                    "max_attempts": max(1, int(max_attempts)),
                    "last_error": "",
                    "last_error_code": "",
                    "next_retry_at": moment,
                    "heartbeat_at": moment,
                    "claimed_by": "",
                    "result_kind": "",
                    "submitted_by": submitted_by,
                    "created_at": moment,
                },
            )
            row = connection.execute(
                select(ReadingIngestionJob).where(ReadingIngestionJob.id == job_id)
            ).first()
        return {**_job(row), "duplicate": False}

    def retry(self, job_id: str, *, actor: str, now: datetime | None = None) -> dict[str, Any] | None:
        """Re-submit a finished job's input as a **new** job.

        The failed row keeps its error, its attempts and its timestamps -
        mutating it back to `queued` would erase the only record of what went
        wrong, which is what an admin looking at Imports is there to read.
        """
        source = self.get_job(job_id)
        if source is None or source["status"] in LIVE_STATUSES:
            return None
        return self.enqueue(
            source_id=source["source_id"],
            job_type=source["job_type"],
            input_json=source["input_json"],
            request_hash=source["request_hash"],
            submitted_by=actor,
            input_asset_key=source["input_asset_key"],
            max_attempts=source["max_attempts"],
            now=now,
        )

    # ---- the worker ------------------------------------------------------
    def claim(self, worker_id: str, *, now: datetime | None = None) -> dict[str, Any] | None:
        """Take the oldest due job, exclusively, or return None.

        One statement, which is what the schema proposal claims for it: the
        `UPDATE` selects its own target through a locking subquery, so there is
        no window between deciding and writing. PostgreSQL renders
        `FOR UPDATE SKIP LOCKED`, so two workers never take the same row and a
        locked row never blocks the queue; SQLite drops the locking clause and
        the repeated `status = 'queued'` in the outer `WHERE` is the whole of
        the exclusion there, which is enough for a single-writer hermetic
        suite.

        `attempt < max_attempts` belongs in the predicate because the claim is
        what increments `attempt`: without it the last retry would violate
        `ck_reading_job_attempt_bound` instead of failing cleanly.
        """
        moment = _now(now)
        candidate = (
            select(ReadingIngestionJob.id)
            .where(
                ReadingIngestionJob.status == "queued",
                ReadingIngestionJob.next_retry_at <= moment,
                ReadingIngestionJob.attempt < ReadingIngestionJob.max_attempts,
            )
            .order_by(ReadingIngestionJob.created_at, ReadingIngestionJob.id)
            .limit(1)
            .with_for_update(skip_locked=True)
            .scalar_subquery()
        )
        with self.engine.begin() as connection:
            claimed = connection.execute(
                update(ReadingIngestionJob)
                .where(
                    ReadingIngestionJob.status == "queued",
                    ReadingIngestionJob.id == candidate,
                )
                .values(
                    status="running",
                    stage=FIRST_STAGE,
                    attempt=ReadingIngestionJob.attempt + 1,
                    claimed_by=worker_id,
                    started_at=moment,
                    heartbeat_at=moment,
                )
                .returning(ReadingIngestionJob.id)
            ).first()
            if claimed is None:
                return None
            row = connection.execute(
                select(ReadingIngestionJob).where(ReadingIngestionJob.id == claimed[0])
            ).first()
        return _job(row)

    def _owned_by(self, job_id: str, worker_id: str):
        """`this job, still running, still this worker's`.

        Every mutating path uses it, because a worker can lose a job it is
        still working on: the reaper hands a stalled worker's job to someone
        else, and the original's late report must then land nowhere.
        """
        return (
            (ReadingIngestionJob.id == uuid.UUID(str(job_id)))
            & (ReadingIngestionJob.status == "running")
            & (ReadingIngestionJob.claimed_by == worker_id)
        )

    def heartbeat(self, job_id: str, worker_id: str, *, now: datetime | None = None) -> bool:
        """"I am still working on this." Returns whether the job was still ours."""
        with self.engine.begin() as connection:
            updated = connection.execute(
                update(ReadingIngestionJob)
                .where(self._owned_by(job_id, worker_id))
                .values(heartbeat_at=_now(now))
            ).rowcount
        return bool(updated)

    def advance_stage(
        self, job_id: str, stage: str, *, worker_id: str, now: datetime | None = None
    ) -> bool:
        """Name the stage this worker has reached, if the job is still its own."""
        with self.engine.begin() as connection:
            updated = connection.execute(
                update(ReadingIngestionJob)
                .where(self._owned_by(job_id, worker_id))
                .values(stage=stage, heartbeat_at=_now(now))
            ).rowcount
        return bool(updated)

    def complete(
        self,
        job_id: str,
        *,
        worker_id: str,
        result_kind: str,
        article_id: str | None = None,
        source_item_id: str | None = None,
        now: datetime | None = None,
    ) -> bool:
        """A finished job, including the `duplicate` outcome.

        A duplicate is a *completed* job: the engine did exactly what it was
        asked and found the content already present. Reporting it as a failure
        would put a red row in Imports for a correct outcome.

        Returns whether the write landed. It does not when the job is no longer
        this worker's - a worker that stalled past the stale window has had its
        job reaped and re-claimed, and its late report would otherwise finish a
        job another worker is in the middle of and overwrite the result with a
        stale one.
        """
        with self.engine.begin() as connection:
            updated = connection.execute(
                update(ReadingIngestionJob)
                .where(self._owned_by(job_id, worker_id))
                .values(
                    status="completed",
                    stage="done",
                    result_kind=result_kind,
                    result_article_id=uuid.UUID(str(article_id)) if article_id else None,
                    result_source_item_id=(
                        uuid.UUID(str(source_item_id)) if source_item_id else None
                    ),
                    finished_at=_now(now),
                    heartbeat_at=_now(now),
                )
            ).rowcount
        return bool(updated)

    def fail(
        self,
        job_id: str,
        *,
        worker_id: str,
        code: str,
        message: str,
        retry_in: timedelta | None,
        now: datetime | None = None,
    ) -> bool:
        """Record why a job stopped, and whether it will come back.

        `retry_in=None` means this failure is not worth retrying (a private
        address, an unsupported file type): the job ends `failed` immediately
        rather than burning its remaining attempts on the same refusal.

        Guarded like `complete()`: a late worker's failure must not re-queue a
        job that already belongs to someone else.
        """
        moment = _now(now)
        with self.engine.begin() as connection:
            row = connection.execute(
                select(ReadingIngestionJob.attempt, ReadingIngestionJob.max_attempts).where(
                    self._owned_by(job_id, worker_id)
                )
            ).first()
            if row is None:
                return False
            exhausted = retry_in is None or row.attempt >= row.max_attempts
            updated = connection.execute(
                update(ReadingIngestionJob)
                .where(self._owned_by(job_id, worker_id))
                .values(
                    status="failed" if exhausted else "queued",
                    stage="done" if exhausted else "queued",
                    claimed_by="",
                    last_error_code=code,
                    last_error=message[:2000],
                    next_retry_at=moment if exhausted else moment + retry_in,
                    finished_at=moment if exhausted else None,
                    heartbeat_at=moment,
                )
            ).rowcount
        return bool(updated)

    def reap_stale(self, stale_after: timedelta, *, now: datetime | None = None) -> int:
        """Return work whose worker stopped reporting in, and sweep dead ends.

        `heartbeat_at` is NOT NULL and set by the claim itself, so there is no
        window in which a running job has no heartbeat for this predicate to
        miss. The attempt was already consumed at claim time; a job with none
        left fails here instead of returning to the queue.

        The second sweep exists because the claim refuses a job with no
        attempts left: without it such a job is invisible to the claim, to the
        stale check and to everything else, and sits in Admin -> Imports
        forever as pending work that can never run.
        """
        moment = _now(now)
        cutoff = moment - stale_after
        exhausted = ReadingIngestionJob.attempt >= ReadingIngestionJob.max_attempts
        with self.engine.begin() as connection:
            swept = connection.execute(
                update(ReadingIngestionJob)
                .where(
                    ReadingIngestionJob.status == "queued",
                    ReadingIngestionJob.attempt >= ReadingIngestionJob.max_attempts,
                )
                .values(
                    status="failed",
                    stage="done",
                    claimed_by="",
                    last_error_code="attempts_exhausted",
                    last_error="this job had no attempts left and could never be claimed",
                    finished_at=moment,
                    heartbeat_at=moment,
                )
            ).rowcount
            # One set-based statement, exactly as the migration docstring
            # specifies it, so the guard travels with the write: a heartbeat
            # landing between a read and a write cannot be overtaken, because
            # there is no read.
            stranded = connection.execute(
                update(ReadingIngestionJob)
                .where(
                    ReadingIngestionJob.status == "running",
                    ReadingIngestionJob.heartbeat_at < cutoff,
                )
                .values(
                    status=case((exhausted, "failed"), else_="queued"),
                    stage=case((exhausted, "done"), else_="queued"),
                    claimed_by="",
                    last_error_code="worker_lost",
                    last_error="the worker holding this job stopped reporting in",
                    next_retry_at=moment,
                    finished_at=case((exhausted, moment), else_=None),
                    heartbeat_at=moment,
                )
            ).rowcount
        return int(stranded) + int(swept)

    # ---- reads -----------------------------------------------------------
    def get_job(self, job_id: str) -> dict[str, Any] | None:
        if _lookup_uuid(job_id) is None:
            return None
        with self.engine.connect() as connection:
            row = connection.execute(
                select(ReadingIngestionJob).where(ReadingIngestionJob.id == uuid.UUID(str(job_id)))
            ).first()
        return _job(row) if row else None

    def list_jobs(
        self,
        *,
        status: str | None = None,
        cursor: str | None = None,
        limit: int = DEFAULT_JOB_PAGE,
    ) -> dict[str, Any]:
        """Newest first, keyset-paginated, bounded, and without the payload."""
        bounded = max(1, min(int(limit), MAX_JOB_PAGE))
        query = select(ReadingIngestionJob)
        if status:
            query = query.where(ReadingIngestionJob.status == status)
        if cursor:
            after_created_at, after_id = _decode_cursor(cursor)
            query = query.where(
                sa_tuple_before(after_created_at, uuid.UUID(after_id)),
            )
        query = query.order_by(
            ReadingIngestionJob.created_at.desc(), ReadingIngestionJob.id.desc()
        ).limit(bounded + 1)
        with self.engine.connect() as connection:
            rows = connection.execute(query).all()
        page = rows[: bounded]
        next_cursor = None
        if len(rows) > bounded and page:
            last = page[-1]
            next_cursor = _encode_cursor(_aware(last.created_at), str(last.id))
        return {"items": [_job_summary(row) for row in page], "next_cursor": next_cursor}

    def workers(
        self, *, stale_after: timedelta, now: datetime | None = None
    ) -> list[dict[str, Any]]:
        """Who is doing the work, from the claims themselves.

        There is no worker registry table, and adding one is a schema decision
        this lane may not make. What the queue already knows is enough for the
        question Operations actually asks: `claimed_by` says whose a job is and
        `heartbeat_at` says when that worker last reported, so grouping the
        claims gives identity, liveness and how much each worker is holding.

        Three states, because an operator does three different things about
        them:

        * **working** - holding a job and reporting in. Nothing to do.
        * **stale** - holding a job and silent past the reaper's window. The
          job will come back to the queue; the worker may be gone.
        * **idle** - holding nothing, but heard from recently. Alive and free.

        A worker that finished long ago is not listed: it is not evidence of
        anything current. One that is idle and has never taken a job is
        invisible here, which is the honest limit of counting claims rather
        than keeping a registry - Operations says so rather than implying the
        list is every process that exists.
        """
        from sqlalchemy import func

        moment = _now(now)
        running = func.sum(
            case((ReadingIngestionJob.status == "running", 1), else_=0)
        ).label("running")
        last_seen = func.max(ReadingIngestionJob.heartbeat_at).label("last_seen")
        query = (
            select(ReadingIngestionJob.claimed_by, running, last_seen)
            .where(
                ReadingIngestionJob.claimed_by.is_not(None),
                ReadingIngestionJob.claimed_by != "",
            )
            .group_by(ReadingIngestionJob.claimed_by)
        )
        with self.engine.connect() as connection:
            rows = connection.execute(query).all()

        order = {"stale": 0, "working": 1, "idle": 2}
        entries: list[dict[str, Any]] = []
        for row in rows:
            seen = _aware(row.last_seen)
            age = int((moment - seen).total_seconds()) if seen else None
            held = int(row.running or 0)
            stale = age is None or age > stale_after.total_seconds()
            if held:
                state = "stale" if stale else "working"
            elif stale:
                continue  # gone, not idle: nothing current to report
            else:
                state = "idle"
            entries.append(
                {
                    "worker_id": row.claimed_by,
                    "running": held,
                    "last_seen_at": _iso(seen),
                    "heartbeat_age_seconds": age,
                    "state": state,
                }
            )
        entries.sort(key=lambda entry: (order[entry["state"]], entry["worker_id"]))
        return entries

    def counts_by_status(self) -> dict[str, int]:
        """Queue depth for Admin -> Operations, computed in the database."""
        from sqlalchemy import func

        with self.engine.connect() as connection:
            rows = connection.execute(
                select(ReadingIngestionJob.status, func.count()).group_by(
                    ReadingIngestionJob.status
                )
            ).all()
        return {status: int(total) for status, total in rows}


def sa_tuple_before(created_at: datetime, job_id: uuid.UUID):
    """`(created_at, id) < (?, ?)` written portably.

    A row comparison is one index bound on PostgreSQL; SQLite has no row
    comparison, so the same condition is spelled out. Both mean "strictly
    older than the row the cursor names", which is what keeps a page boundary
    stable when two jobs share a timestamp.
    """
    return (ReadingIngestionJob.created_at < created_at) | (
        (ReadingIngestionJob.created_at == created_at) & (ReadingIngestionJob.id < job_id)
    )
