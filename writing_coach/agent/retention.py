"""agent.turn telemetry is kept 90 days, and swept automatically (human direction 2026-10-04).

Each turn writes one `agent.turn` row to `audit_logs` (agent/timeline.py), linked to the learner's account. They
are kept for 90 days. The sweep needs no scheduler: the write path itself starts it, at most once a day per
process, off the request thread, and removes older rows in bounded batches through a repository method that can
delete `agent.turn` rows and nothing else. Deleting is idempotent, so several processes sweeping at once only
repeat work. A failing sweep is logged and tried again the next day; it never costs a learner a turn.

It is off by default (human direction 2026-10-04): automatic deletion is a destructive lifecycle change, so it
runs only once `AGENT_TURN_RETENTION_SWEEP` is switched on, after its independent review has passed. Off, nothing
is ever deleted and the rows simply stay.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta

TURN_RETENTION_DAYS = 90
SWEEP_INTERVAL_SECONDS = 24 * 3600
SWEEP_BATCH = 5000

SWEEP_SWITCH = "AGENT_TURN_RETENTION_SWEEP"
_ON = frozenset({"1", "true", "on", "yes"})
_OFF = frozenset({"", "0", "false", "off", "no"})

_log = logging.getLogger(__name__)


def sweep_enabled(env: Mapping[str, str]) -> bool:
    """True only when `AGENT_TURN_RETENTION_SWEEP` is switched on; unset is off. An unclear value refuses to start
    rather than guess whether deleting was meant."""

    value = str(env.get(SWEEP_SWITCH, "")).strip().casefold()
    if value in _ON:
        return True
    if value in _OFF:
        return False
    raise ValueError(f"{SWEEP_SWITCH} must be one of {sorted(_ON | _OFF - {''})}")


def _in_background(work: Callable[[], None]) -> None:
    threading.Thread(target=work, name="agent-turn-retention", daemon=True).start()


class TurnTelemetryRetention:
    """`maybe_sweep()` after each agent.turn write; a sweep runs when the last one began a day ago or more."""

    MAX_BATCHES = 20  # one sweep removes at most this many batches; a larger backlog goes over the next days

    def __init__(
        self,
        delete_before: Callable[[datetime, int], int],
        *,
        days: int = TURN_RETENTION_DAYS,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        run: Callable[[Callable[[], None]], None] = _in_background,
    ) -> None:
        self._delete_before = delete_before
        self._days = days
        self._now = now
        self._run = run
        self._lock = threading.Lock()
        self._last: datetime | None = None
        self._removed: int | None = None

    def maybe_sweep(self) -> int | None:
        """Start a sweep if one is due. With an inline runner it returns how many rows went (None on failure)."""

        now = self._now()
        with self._lock:
            if self._last is not None and now - self._last < timedelta(seconds=SWEEP_INTERVAL_SECONDS):
                return None
            self._last = now  # claimed before it runs: one sweep a day, even when it fails
        self._removed = None
        self._run(lambda: self._sweep(now - timedelta(days=self._days)))
        return self._removed

    def _sweep(self, before: datetime) -> None:
        removed = 0
        try:
            for _ in range(self.MAX_BATCHES):
                gone = self._delete_before(before, SWEEP_BATCH)
                removed += gone
                if gone < SWEEP_BATCH:
                    break
        except Exception:
            _log.warning("agent turn telemetry sweep failed after %d rows", removed, exc_info=True)
            return
        self._removed = removed
        if removed:
            _log.info("agent turn telemetry: %d rows older than %d days removed", removed, self._days)
