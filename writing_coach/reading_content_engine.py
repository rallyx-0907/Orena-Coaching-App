"""One pipeline: submission -> job -> snapshot -> candidate an admin reviews.

This is the module that makes the adapters, the deterministic processor and
the two repositories one engine rather than three parts. Everything a manual
paste goes through, a fetched URL and a future RSS item go through too - the
only difference is which adapter produced the `NormalizedSourceItem`.

Two boundaries this file exists to keep:

- **Nothing heavy happens in the admin's request.** `submit()` validates, mints
  a job and returns; the fetching, parsing and analysis happen in a worker
  process. An admin whose upstream is slow waits for a job id, not for a page.
- **Nothing here publishes.** The engine's terminal state is a candidate in
  `needs_review`. Making an article learner-visible is an admin's act, through
  the repository, recorded with their name on it.

Failure has two kinds and they are not treated alike. A refusal that will
never succeed - a private address, an unsupported file type, an empty
document - fails the job immediately rather than burning three attempts on the
same answer. A transient failure - an upstream timeout, a connection reset -
comes back with an exponential backoff.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from writing_coach.persistence.reading_content_repository import (
    MAX_TARGETS,
    ReadingContentRepository,
    TargetInput,
)
from writing_coach.persistence.reading_job_repository import ReadingJobRepository
from writing_coach.reading_processing import (
    analyze_article,
    quality_issues,
    suggest_targets,
)
from writing_coach.reading_source_import import (
    DirectUrlAdapter,
    FileAdapter,
    ManualTextAdapter,
    NormalizedSourceItem,
    ReadingSourceError,
    SubmittedInput,
    request_digest,
)

_logger = logging.getLogger(__name__)

# Which submission kind reaches which built-in source and which adapter.
JOB_TYPES = {"text": "ingest_text", "url": "ingest_url", "file": "ingest_file"}
SOURCE_FOR_KIND = {"text": "manual", "url": "direct_url", "file": "file"}

# Refusals that are facts about the input, not about the moment. Retrying one
# of these produces the same answer, so the job fails on the first attempt.
PERMANENT_ERRORS = frozenset(
    {
        "unsafe_url",
        "unsupported_content_type",
        "unsupported_file_type",
        "unsupported_input",
        "undecodable_source",
        "empty_source",
        "source_too_large",
    }
)
RETRY_BACKOFF = (timedelta(minutes=1), timedelta(minutes=5), timedelta(minutes=30))


def _backoff(attempt: int) -> timedelta:
    return RETRY_BACKOFF[min(max(attempt, 1) - 1, len(RETRY_BACKOFF) - 1)]


class ReadingContentEngine:
    def __init__(
        self,
        *,
        content: ReadingContentRepository,
        jobs: ReadingJobRepository,
        audit: Callable[..., None] | None = None,
    ) -> None:
        self.content = content
        self.jobs = jobs
        # Injectable so a test can supply a fetcher without a network, and so
        # a future RSS adapter is a registration rather than a branch here.
        self.adapters: dict[str, Callable[[], Any]] = {
            "text": ManualTextAdapter,
            "url": DirectUrlAdapter,
            "file": FileAdapter,
        }
        self._audit = audit

    # ---- submission ------------------------------------------------------
    def submit(
        self,
        submitted: SubmittedInput,
        *,
        actor: str,
        input_asset_key: str = "",
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Validate, queue, return. No fetching, no parsing, no AI.

        The only work done here is what an admin must be told about
        immediately: that the kind of input is supported at all. Everything
        else is the worker's, because an admin should not hold a request open
        while an upstream server decides whether to answer.
        """
        kind = (submitted.kind or "").strip().casefold()
        if kind not in JOB_TYPES:
            raise ReadingSourceError("unsupported_input", "This kind of source is not supported.")
        source_id = self.content.built_in_source_id(SOURCE_FOR_KIND[kind])
        job = self.jobs.enqueue(
            source_id=source_id,
            job_type=JOB_TYPES[kind],
            input_json=self._job_input(submitted),
            request_hash=request_digest(submitted, source_id=source_id),
            submitted_by=actor,
            input_asset_key=input_asset_key,
            now=now,
        )
        self._record_audit(
            actor=actor,
            action="admin.reading.submit",
            entity_id=job["id"],
            payload={"kind": kind, "duplicate": job["duplicate"], "job_type": JOB_TYPES[kind]},
        )
        return job

    def _job_input(self, submitted: SubmittedInput) -> dict[str, Any]:
        """The submission as the worker will rebuild it.

        A file's bytes are *not* in here - they go to the asset store and the
        job carries the key, because a row is not a place to keep an upload
        (SS46.10).
        """
        return {
            "kind": submitted.kind,
            "text": submitted.text,
            "url": submitted.url,
            "filename": submitted.filename,
            "title": submitted.title,
            "author": submitted.author,
            "language": submitted.language,
            "published_at": submitted.published_at,
            "source_name": submitted.source_name,
            "rights": dict(submitted.rights or {}),
        }

    # ---- processing ------------------------------------------------------
    def process(
        self,
        job: dict[str, Any] | None,
        *,
        payload: bytes = b"",
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        """Take one claimed job from submission to candidate.

        Returns what happened, so a worker can log it without re-reading the
        row: `article_created`, `duplicate`, or a failure dict. Never raises
        for an input problem - a job that fails is a recorded failure an admin
        can read, not an exception that disappears into a log.
        """
        if not job:
            return None
        job_id = job["id"]
        # The worker that claimed this job is the only one allowed to report on
        # it. Every stage boundary re-asserts that and *stops* when the answer
        # is no: the job writes would land nowhere anyway, but the content
        # writes would not - a zombie worker reaching the supersede path would
        # change which snapshot is current on behalf of a job it no longer
        # owns. Checking here costs one round trip and a wasted fetch; not
        # checking costs a corrupted currency flag.
        worker_id = job.get("claimed_by", "")
        lost = {"job_id": job_id, "result_kind": "job_lost"}
        submitted = self._rebuild(job, payload=payload)
        try:
            adapter = self.adapters[submitted.kind]()
            raw = adapter.fetch(submitted)
            if not self.jobs.advance_stage(job_id, "normalizing", worker_id=worker_id, now=now):
                return lost
            item = adapter.normalize(raw)
            # The last check before anything is written to the content tables.
            if not self.jobs.advance_stage(job_id, "deduplicating", worker_id=worker_id, now=now):
                return lost
            snapshot = self.content.record_source_item(
                source_id=job["source_id"],
                source_native_id=item.source_native_id,
                canonical_url=item.canonical_url,
                title=item.title,
                author=item.author,
                published_at=item.published_at,
                language=item.language,
                body=item.body,
                content_hash=item.content_hash,
                metadata=item.metadata,
                rights=item.rights,
                now=now,
            )
            existing = self.content.article_for_source_item(snapshot["id"])
            if existing is not None:
                # Idempotent by construction: these bytes already produced a
                # candidate - including one an admin rejected, which is how a
                # rejection keeps rejecting.
                self.jobs.complete(
                    job_id,
                    worker_id=worker_id,
                    result_kind="duplicate",
                    article_id=existing["id"],
                    source_item_id=snapshot["id"],
                    now=now,
                )
                return {
                    "job_id": job_id,
                    "result_kind": "duplicate",
                    "article_id": existing["id"],
                    "source_item_id": snapshot["id"],
                }
            if not self.jobs.advance_stage(job_id, "analyzing", worker_id=worker_id, now=now):
                return lost
            article = self._build_candidate(item, snapshot, now=now)
            self.jobs.complete(
                job_id,
                worker_id=worker_id,
                result_kind="article_created",
                article_id=article["id"],
                source_item_id=snapshot["id"],
                now=now,
            )
            return {
                "job_id": job_id,
                "result_kind": "article_created",
                "article_id": article["id"],
                "source_item_id": snapshot["id"],
            }
        except ReadingSourceError as refusal:
            return self._fail(job, code=refusal.code, message=refusal.message, now=now)
        except Exception as exc:  # noqa: BLE001 - a lost job is worse than a recorded one
            _logger.exception("reading engine: job %s failed unexpectedly", job_id)
            return self._fail(job, code="internal_error", message=str(exc), now=now)

    def _rebuild(self, job: dict[str, Any], *, payload: bytes) -> SubmittedInput:
        stored = dict(job.get("input_json") or {})
        return SubmittedInput(
            kind=stored.get("kind", ""),
            text=stored.get("text", ""),
            url=stored.get("url", ""),
            filename=stored.get("filename", ""),
            payload=payload,
            title=stored.get("title", ""),
            author=stored.get("author", ""),
            language=stored.get("language", ""),
            published_at=stored.get("published_at", ""),
            source_name=stored.get("source_name", ""),
            rights=dict(stored.get("rights") or {}),
        )

    def _build_candidate(
        self, item: NormalizedSourceItem, snapshot: dict[str, Any], *, now: datetime | None
    ) -> dict[str, Any]:
        """Measure, suggest, and hand the result to review - never to a learner.

        The quality issues are attached rather than acted on: "this text is
        shorter than an article" and "this is not the language it claims" are
        facts a reviewer needs, not grounds for the machine to throw a
        submission away that an admin deliberately made.
        """
        language = item.language or "en"
        analysis = analyze_article(item.body, language)
        issues = quality_issues(item.body, language)
        suggestions = suggest_targets(item.body, language, limit=MAX_TARGETS)
        excerpt = " ".join(item.body.split())[:280]
        return self.content.create_article(
            source_item_id=snapshot["id"],
            title=item.title or excerpt[:80],
            body=item.body,
            excerpt=excerpt,
            language=language,
            topic="",
            estimated_level=analysis.estimated_level,
            estimated_confidence=analysis.confidence,
            word_count=analysis.word_count,
            reading_time_seconds=analysis.reading_time_seconds,
            analysis={
                "sentence_count": analysis.sentence_count,
                "average_sentence_length": analysis.average_sentence_length,
                "distinct_word_ratio": analysis.distinct_word_ratio,
                "long_word_ratio": analysis.long_word_ratio,
                "level_confidence": analysis.confidence,
                "quality_issues": issues,
                "detected_language": item.metadata.get("detected_language", ""),
                "rights_known": item.metadata.get("rights_known", False),
            },
            targets=[
                TargetInput(
                    text=suggestion.text,
                    canonical_form=suggestion.canonical_form,
                    target_type=suggestion.target_type,
                    context=suggestion.context,
                    estimated_level=suggestion.estimated_level,
                    rank=suggestion.rank,
                )
                for suggestion in suggestions
            ],
            now=now,
        )

    def _fail(
        self, job: dict[str, Any], *, code: str, message: str, now: datetime | None
    ) -> dict[str, Any]:
        permanent = code in PERMANENT_ERRORS
        self.jobs.fail(
            job["id"],
            worker_id=job.get("claimed_by", ""),
            code=code,
            message=message,
            retry_in=None if permanent else _backoff(int(job.get("attempt", 1))),
            now=now,
        )
        return {
            "job_id": job["id"],
            "result_kind": "failed",
            "error_code": code,
            "permanent": permanent,
        }

    def _record_audit(self, **kwargs: Any) -> None:
        if self._audit is None:
            return
        try:
            self._audit(**kwargs)
        except Exception:  # noqa: BLE001 - an audit failure must not lose the work
            _logger.warning("reading engine: audit write failed", exc_info=True)

    # ---- operations ------------------------------------------------------
    def queue_health(self) -> dict[str, Any]:
        """What Admin -> Operations shows: depth by state, computed in the
        database rather than by counting rows in Python."""
        counts = self.jobs.counts_by_status()
        return {
            "queued": counts.get("queued", 0),
            "running": counts.get("running", 0),
            "failed": counts.get("failed", 0),
            "completed": counts.get("completed", 0),
            "checked_at": (now := datetime.now(UTC)).isoformat(),
            "worker_stale_after_seconds": int(DEFAULT_STALE_AFTER.total_seconds()),
            "as_of": now.isoformat(),
        }


DEFAULT_STALE_AFTER = timedelta(minutes=5)
