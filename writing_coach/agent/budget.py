"""The staging daily spend cap (dogfood phase, human direction 2026-10-04: 1 USD a day, :8021 only).

Every priced provider call - the agent's rounds and every other learner capability -
is recorded with its estimated cost in the AI operation telemetry (`ai.operation`).
Before a turn starts, the guard adds up today's (UTC) spend from that one shared
ledger. At or over the cap the turn is refused with the contract's own 429 and a
Retry-After that ends at the next UTC midnight; the cap is never raised here.

It fails closed: a ledger that cannot be read refuses the turn, and a provider call
recorded without a price counts as UNPRICED_ALLOWANCE_USD each rather than as zero.
Off unless AGENT_DAILY_SPEND_CAP_USD is set - this is a staging guard, not the
per-account quota a public launch needs, and it is not billing.

Not in the ledger yet (reported as a gap): speech recognition and pronunciation
scoring, which record no cost today.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

_log = logging.getLogger(__name__)

CAP_ENV = "AGENT_DAILY_SPEND_CAP_USD"
UNPRICED_ALLOWANCE_USD = 0.01
CACHE_SECONDS = 5.0  # a soft cap: turns admitted inside one window, and rounds in flight, may overshoot it

SpendReader = Callable[[datetime], tuple[float, int]]  # since -> (estimated USD, unpriced provider calls)


def cap_from_env(environ: Mapping[str, str]) -> float | None:
    """The cap from the environment the app passes (the agent package reads no environment itself)."""

    raw = environ.get(CAP_ENV, "").strip()
    if not raw:
        return None
    value = float(raw)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{CAP_ENV} must be a non-negative number")
    return value


@dataclass
class DailySpendGuard:
    cap_usd: float
    read: SpendReader
    now: Callable[[], datetime] = lambda: datetime.now(UTC)
    monotonic: Callable[[], float] = time.monotonic
    _cached: tuple[float, float | None] | None = field(default=None, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def __call__(self) -> float | None:
        """Seconds until the cap resets when today's spend is at or over it; None when a turn may run."""

        with self._lock:
            if self._cached is not None and self.monotonic() - self._cached[0] < CACHE_SECONDS:
                return self._cached[1]
            moment = self.now()
            midnight = datetime(moment.year, moment.month, moment.day, tzinfo=UTC)
            until_reset = max(1.0, (midnight + timedelta(days=1) - moment).total_seconds())
            try:
                usd, unpriced = self.read(midnight)
                spent = float(usd) + unpriced * UNPRICED_ALLOWANCE_USD
                verdict = until_reset if spent >= self.cap_usd else None
                if verdict is not None:
                    _log.warning("agent daily spend cap reached: %.4f of %.2f USD", spent, self.cap_usd)
            except Exception:  # the ledger cannot be read: fail closed
                _log.warning("agent daily spend ledger unreadable; turns refused", exc_info=True)
                verdict = until_reset
            self._cached = (self.monotonic(), verdict)
            return verdict
