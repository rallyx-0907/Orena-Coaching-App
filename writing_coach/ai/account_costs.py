"""AI cost per account (AC-2; human decision 2026-10-04; proposals/AI_COST_PER_ACCOUNT.md).

Every priced provider call made inside a signed-in learner's request is recorded once more, beside the anonymous
`ai.operation` telemetry, as a row of `ai_cost_records`: the account, the feature, provider and model, the
estimated cost and the units - never what the learner wrote or said. It is the one record for the Admin cost page
(totals by default, per account for an administrator) and for per-plan quota.

Kept 13 months, then deleted automatically: the write path starts a sweep at most once a day per process, off the
request thread, in bounded batches through a repository method that deletes cost records and nothing else.

Before the table exists (the migration is a proposal until the human authorizes it), or on any database error,
recording pauses for five minutes and then tries again; nothing a learner does ever fails because of it. An
administrator's connection test and configuration checks are not an account's spend and are not recorded.

Unlike the agent.turn sweep, this one has no off switch: automatic deletion at 13 months is the human's decision
for this record (2026-10-04), and it starts as soon as the table exists.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

RETENTION_DAYS = 396  # 13 months
SWEEP_INTERVAL = timedelta(days=1)
RETRY_AFTER = timedelta(minutes=5)
# Calls made for the operator, not the account in whose request they ran.
_NOT_SPEND = frozenset({"operator_test", "configuration"})
SWEEP_BATCH = 5000
MAX_BATCHES = 20
# Request contexts that are not a signed-in account: nothing is recorded for them.
_NOT_AN_ACCOUNT = frozenset({"", "legacy", "local-admin", "local"})

_log = logging.getLogger(__name__)


class AccountCostRecorder:
    def __init__(self, repository: Any, *, now: Callable[[], datetime] = lambda: datetime.now(UTC),
                 run: Callable[[Callable[[], None]], None] | None = None) -> None:
        self._repository = repository
        self._now = now
        self._run = run or (lambda work: threading.Thread(target=work, name="ai-cost-retention", daemon=True).start())
        self._lock = threading.Lock()
        self._paused_until: datetime | None = None
        self._last_sweep: datetime | None = None

    def record(self, user_key: str, event: dict[str, Any]) -> bool:
        """Record one telemetry event for this account, if it was a provider call that answered."""

        if user_key in _NOT_AN_ACCOUNT or event.get("outcome") != "success" or not event.get("provider"):
            return False
        if event.get("origin") in _NOT_SPEND:
            return False
        if self._paused_until is not None and self._now() < self._paused_until:
            return False
        writer = getattr(self._repository, "record_ai_cost", None)
        if not callable(writer):
            return False
        try:
            written = bool(writer(user_key, event))
        except Exception as error:  # noqa: BLE001 - the table may not exist yet; a learner never pays for it
            _log.warning("AI cost per account not recorded (%s); retrying in %s", type(error).__name__, RETRY_AFTER)
            self._paused_until = self._now() + RETRY_AFTER
            return False
        self._paused_until = None
        self.maybe_sweep()
        return written

    def maybe_sweep(self) -> None:
        now = self._now()
        with self._lock:
            if self._last_sweep is not None and now - self._last_sweep < SWEEP_INTERVAL:
                return
            self._last_sweep = now  # claimed before it runs: once a day, even when it fails
        self._run(lambda: self.sweep(now - timedelta(days=RETENTION_DAYS)))

    def sweep(self, before: datetime) -> int | None:
        delete = getattr(self._repository, "delete_ai_costs_before", None)
        if not callable(delete):
            return 0
        removed = 0
        try:
            for _ in range(MAX_BATCHES):
                gone = int(delete(before, limit=SWEEP_BATCH))
                removed += gone
                if gone < SWEEP_BATCH:
                    break
        except Exception:  # noqa: BLE001 - tried again the next day
            _log.warning("AI cost retention sweep failed after %d rows", removed, exc_info=True)
            return None
        if removed:
            _log.info("AI cost records: %d older than %d days removed", removed, RETENTION_DAYS)
        return removed


_recorder: AccountCostRecorder | None = None


def install(repository: Any) -> None:
    global _recorder
    _recorder = AccountCostRecorder(repository) if repository is not None else None


def record_for_current_account(event: dict[str, Any]) -> None:
    """Called with each sanitized telemetry event; the account is the request's own (never an argument)."""

    if _recorder is None:
        return
    from writing_coach.core.request_context import current_user_key

    _recorder.record(current_user_key(), event)
