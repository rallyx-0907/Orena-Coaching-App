"""AI cost per account (AC-2; human decision 2026-10-04; proposals/AI_COST_PER_ACCOUNT.md).

Every priced provider call made inside a signed-in learner's request is recorded once more, beside the anonymous
`ai.operation` telemetry, as a row of `ai_cost_records`: the account, the feature, provider and model, the
estimated cost and the units - never what the learner wrote or said. It is the one record for the Admin cost page
(totals by default, per account for an administrator) and for per-plan quota.

Kept 13 months, then deleted automatically: the write path starts a sweep at most once a day per process, off the
request thread, in bounded batches through a repository method that deletes cost records and nothing else.

Before the table exists (migration 20261005_0026, applied per runtime by the operator), or on any database error,
writing pauses for five minutes and then tries again; nothing a learner does ever fails because of it. A row that could
not be written is never dropped silently (review of #487): it is kept in a bounded in-process queue, retried before the
next write, counted in that learner's per-learner cost cap meanwhile (`pending_usd`, ai/learner_cost.py), and the
failure is logged as an ALERT. Rows past the queue's bound are counted and alerted, never silently lost. An
administrator's connection test and configuration checks are not an account's spend and are not recorded.

Unlike the agent.turn sweep, this one has no off switch: automatic deletion at 13 months is the human's decision
for this record (2026-10-04), and it starts as soon as the table exists.
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from writing_coach import policies

RETENTION_DAYS = policies.default("ai_costs.retention_days")  # 13 months; the effective period is `ai_costs.retention_days`
SWEEP_INTERVAL = timedelta(days=1)
RETRY_AFTER = timedelta(minutes=5)
# Calls made for the operator, not the account in whose request they ran.
_NOT_SPEND = frozenset({"operator_test", "configuration"})
SWEEP_BATCH = 5000
MAX_PENDING = 5000   # rows kept for a retry while the table cannot be written
MAX_BATCHES = 20
# Request contexts that are not a signed-in account: nothing is recorded for them.
_NOT_AN_ACCOUNT = frozenset({"", "legacy", "local-admin", "local"})

_log = logging.getLogger(__name__)


class AccountCostRecorder:
    def __init__(self, repository: Any, *, now: Callable[[], datetime] = lambda: datetime.now(UTC),
                 run: Callable[[Callable[[], None]], None] | None = None,
                 days: int | Callable[[], int] = RETENTION_DAYS) -> None:
        self._repository = repository
        self._days = days
        self._now = now
        self._run = run or (lambda work: threading.Thread(target=work, name="ai-cost-retention", daemon=True).start())
        self._lock = threading.Lock()
        self._paused_until: datetime | None = None
        self._last_sweep: datetime | None = None
        self._pending: deque[tuple[str, dict[str, Any], datetime]] = deque()
        self.dropped = 0   # rows lost past MAX_PENDING (alerted)

    def record(self, user_key: str, event: dict[str, Any]) -> bool:
        """Record one telemetry event for this account, if it was a provider call that answered."""

        # A success, or any request actually sent (PR-MON-6 §8): a failed call that was sent may have cost money;
        # its cost state (unknown / unpriced / partial) makes its operation incomplete, never USD 0. A rung skipped
        # before sending is not a billable attempt and is never a cost row.
        billable = event.get("outcome") == "success" or event.get("billable_attempt") is True
        if user_key in _NOT_AN_ACCOUNT or not billable or not event.get("provider"):
            return False
        if event.get("origin") in _NOT_SPEND:
            return False
        writer = getattr(self._repository, "record_ai_cost", None)
        if not callable(writer):
            return False
        if self._paused_until is not None and self._now() < self._paused_until:
            self._keep(user_key, event)
            return False
        if not self._flush(writer):
            self._keep(user_key, event)
            return False
        try:
            written = bool(writer(user_key, event))
        except Exception as error:  # noqa: BLE001 - the table may not exist yet; a learner never pays for it
            self._failed(error)
            self._keep(user_key, event)
            return False
        self._paused_until = None
        self.maybe_sweep()
        return written

    def _failed(self, error: BaseException) -> None:
        _log.error("ALERT AI cost per account not written (%s); the row is kept and retried in %s, and it still counts "
                   "in the learner's cost cap", type(error).__name__, RETRY_AFTER)
        self._paused_until = self._now() + RETRY_AFTER

    def _keep(self, user_key: str, event: dict[str, Any]) -> None:
        with self._lock:
            if len(self._pending) >= MAX_PENDING:
                self._pending.popleft()
                self.dropped += 1
                _log.error("ALERT AI cost rows lost: the retry queue is full (%d dropped so far)", self.dropped)
            self._pending.append((user_key, dict(event), self._now()))

    def _flush(self, writer: Callable[[str, dict[str, Any]], Any]) -> bool:
        """Write the kept rows, oldest first; False (and paused again) at the first that still fails."""
        while True:
            with self._lock:
                if not self._pending:
                    return True
                user_key, event, _at = self._pending[0]
            try:
                writer(user_key, event)
            except Exception as error:  # noqa: BLE001
                self._failed(error)
                return False
            with self._lock:
                if self._pending and self._pending[0][1] is event:
                    self._pending.popleft()

    def pending_usd(self, user_key: str, since: datetime) -> float:
        """The cost of this account's rows not written yet, since `since` (counted in its per-learner cap)."""
        with self._lock:
            rows = [event for key, event, at in self._pending if key == user_key and at >= since]
        total = 0.0
        for event in rows:
            cost = event.get("cost") if isinstance(event.get("cost"), dict) else {}
            amount = cost.get("amount")
            if isinstance(amount, (int, float)) and amount > 0:
                total += float(amount)
        return total

    def maybe_sweep(self) -> None:
        now = self._now()
        with self._lock:
            if self._last_sweep is not None and now - self._last_sweep < SWEEP_INTERVAL:
                return
            self._last_sweep = now  # claimed before it runs: once a day, even when it fails
        days = self._days() if callable(self._days) else self._days
        self._run(lambda: self.sweep(now - timedelta(days=days), days))

    def sweep(self, before: datetime, days: int | None = None) -> int | None:
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
            _log.info("AI cost records: %d older than %d days removed", removed, days if days is not None else RETENTION_DAYS)
        return removed


_recorder: AccountCostRecorder | None = None


def install(repository: Any) -> None:
    global _recorder
    _recorder = (AccountCostRecorder(repository, days=lambda: policies.value("ai_costs.retention_days"))
                 if repository is not None else None)


def pending_usd(user_key: str, since: datetime) -> float:
    """Rows of this account not written to `ai_cost_records` yet (ai/learner_cost.py adds them to the learner total)."""
    return _recorder.pending_usd(user_key, since) if _recorder is not None else 0.0


def record_for_current_account(event: dict[str, Any]) -> None:
    """Called with each sanitized telemetry event; the account is the request's own (never an argument)."""

    if _recorder is None:
        return
    from writing_coach.billing.funding_context import attribution
    from writing_coach.core.request_context import current_user_key

    # PR-MON-6 §8: the learner operation (or the system reason) this call was made for, so its cost is aggregated per
    # operation. A call with neither is unattributed: counted and reported, never folded into a meter.
    operation_id, meter = attribution()
    if operation_id is not None:
        event = {**event, "funding_operation_id": operation_id, "funding_meter": meter}
    _recorder.record(current_user_key(), event)
