"""The Reading engine's worker - an execution path, never a request path.

Run as its own process (`python -m writing_coach.reading_worker`) or, in the
sandbox, beside the application in the same container. Either way it is off
the learner request path: a learner's page load never waits for a fetch, an
HTML extraction or a model call, because none of those happen where learners
are served.

Concurrency is `READING_WORKER_CONCURRENCY` and defaults to **1**. More
workers are not automatically better - each one competes for the same database
and the same upstream politeness budget - so the default is the small machine,
and raising it is a measured decision rather than an assumption.

The loop is deliberately dull: reap what a dead worker was holding, claim one
job, process it, repeat. Everything that makes that safe (the exclusive claim,
the heartbeat, the bounded attempts) lives in the repository, where the
database can enforce it.
"""
from __future__ import annotations

import logging
import os
import signal
import time
from datetime import datetime, timedelta
from typing import Any

from writing_coach.persistence.reading_job_repository import ReadingJobRepository
from writing_coach.reading_content_engine import ReadingContentEngine

_logger = logging.getLogger(__name__)

DEFAULT_STALE_AFTER = timedelta(minutes=5)
DEFAULT_IDLE_SLEEP_SECONDS = 2.0
MAX_CONCURRENCY = 8


def configured_concurrency() -> int:
    """`READING_WORKER_CONCURRENCY`, bounded, defaulting to one.

    Anything unparseable, zero or negative means one: a misconfigured
    environment should make the worker cautious, never absent and never
    unbounded.
    """
    raw = os.getenv("READING_WORKER_CONCURRENCY", "").strip()
    try:
        value = int(raw)
    except ValueError:
        return 1
    return max(1, min(value, MAX_CONCURRENCY))


class ReadingWorker:
    def __init__(
        self,
        *,
        engine: ReadingContentEngine,
        jobs: ReadingJobRepository,
        worker_id: str,
        stale_after: timedelta = DEFAULT_STALE_AFTER,
        asset_reader: Any = None,
    ) -> None:
        self.engine = engine
        self.jobs = jobs
        self.worker_id = worker_id
        self.stale_after = stale_after
        # How a file job's bytes are fetched back. Injected so the worker does
        # not have to know whether the asset store is a filesystem or an
        # object store.
        self._asset_reader = asset_reader
        self._running = True

    def run_once(self, *, now: datetime | None = None) -> dict[str, Any] | None:
        """Recover, claim, process. Returns what happened, or None if idle."""
        self.jobs.reap_stale(self.stale_after, now=now)
        job = self.jobs.claim(self.worker_id, now=now)
        if job is None:
            return None
        payload = self._payload_for(job)
        return self.engine.process(job, payload=payload, now=now)

    def _payload_for(self, job: dict[str, Any]) -> bytes:
        key = job.get("input_asset_key") or ""
        if not key or self._asset_reader is None:
            return b""
        try:
            return self._asset_reader(key)
        except Exception:  # noqa: BLE001 - reported as a job failure, not a crash
            _logger.warning("reading worker: could not read upload %s", key, exc_info=True)
            return b""

    def stop(self) -> None:
        self._running = False

    def run_forever(self, *, idle_sleep: float = DEFAULT_IDLE_SLEEP_SECONDS) -> None:
        """Process until asked to stop. A sleep only when there is nothing to do.

        No job is lost by stopping here: whatever is in flight keeps its
        heartbeat until this process exits, and the next worker's reaper
        returns it. That is the whole reason the queue is a table.
        """
        while self._running:
            try:
                outcome = self.run_once()
            except Exception:  # noqa: BLE001 - the loop outlives one bad job
                _logger.exception("reading worker: iteration failed")
                outcome = None
            if outcome is None:
                time.sleep(idle_sleep)


def main() -> int:  # pragma: no cover - process entry point
    """Stand up one worker per configured concurrency slot, in threads.

    Threads rather than processes because the work is I/O bound (fetching,
    database round trips) and because one process is easier to supervise in a
    compose file. Each thread claims its own jobs; the database, not this
    code, is what stops two of them taking the same one.
    """
    import threading

    from writing_coach.persistence.reading_content_repository import ReadingContentRepository
    from writing_coach.persistence.runtime import runtime_engine

    logging.basicConfig(level=logging.INFO)
    database = runtime_engine()
    if database is None:
        _logger.error("reading worker: no runtime database is configured")
        return 1
    jobs = ReadingJobRepository(database)
    engine = ReadingContentEngine(
        content=ReadingContentRepository(database), jobs=jobs
    )
    workers = [
        ReadingWorker(engine=engine, jobs=jobs, worker_id=f"{os.getpid()}-{index}")
        for index in range(configured_concurrency())
    ]

    def shutdown(signum, frame):  # noqa: ANN001, ARG001
        _logger.info("reading worker: shutting down")
        for worker in workers:
            worker.stop()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    threads = [threading.Thread(target=worker.run_forever, daemon=False) for worker in workers]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return 0


if __name__ == "__main__":  # pragma: no cover - process entry point
    raise SystemExit(main())
