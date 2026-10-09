"""Learner feedback is kept at most 24 months, enforced by a periodic job (D-159, review of #113).

The sweep runs on a clock rather than on traffic. A daemon thread started with the app sweeps once at start and
then every `SWEEP_INTERVAL_SECONDS`, whether or not anyone sends feedback. Each sweep removes reviews older than
24 months, and orphans of a deleted account row, in bounded batches through
`delete_feedback_before()`. That method deletes only `learner.feedback` rows. Deleting is idempotent, so several
processes sweeping at once only repeat work. A failing sweep is logged and tried again at the next tick.

Deletion is a destructive lifecycle job, so the schedule starts only when `FEEDBACK_RETENTION_SWEEP` is on
(`feedback.retention_enabled`). Off, nothing is deleted.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from writing_coach.feedback import FEEDBACK_RETENTION_DAYS

SWEEP_INTERVAL_SECONDS = 24 * 3600
SWEEP_BATCH = 1000
MAX_BATCHES = 50  # a larger backlog goes over the next ticks

_log = logging.getLogger(__name__)


def sweep_once(delete_before: Callable[[datetime, int], int], *, now: datetime | None = None,
               days: int = FEEDBACK_RETENTION_DAYS) -> int:
    """One sweep: reviews older than `days`, in bounded batches. Returns how many rows went."""
    cutoff = (now or datetime.now(UTC)) - timedelta(days=days)
    removed = 0
    for _ in range(MAX_BATCHES):
        gone = int(delete_before(cutoff, SWEEP_BATCH) or 0)
        removed += gone
        if gone < SWEEP_BATCH:
            break
    return removed


class FeedbackRetentionSchedule:
    """Sweeps at start and then every `interval` seconds until `stop()`, on its own daemon thread."""

    def __init__(self, delete_before: Callable[[datetime, int], int], *,
                 interval: float = SWEEP_INTERVAL_SECONDS) -> None:
        self._delete_before = delete_before
        self._interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.sweeps = 0

    def tick(self) -> int | None:
        try:
            removed = sweep_once(self._delete_before)
        except Exception:
            _log.warning("learner feedback retention sweep failed; retried at the next tick", exc_info=True)
            return None
        finally:
            self.sweeps += 1
        if removed:
            _log.info("learner feedback: %d reviews past %d days removed", removed, FEEDBACK_RETENTION_DAYS)
        return removed

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.tick()
            self._stop.wait(self._interval)

    def start(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, name="feedback-retention", daemon=True)
            self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)
