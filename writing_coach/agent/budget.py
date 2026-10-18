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
from typing import Any
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
    # A warning once per UTC day when today's spend reaches this share of the cap (owner, 2026-10-18: 80%); None: none.
    warn_ratio: float | None = None
    label: str = "agent"  # in the log lines: "agent" or "system"
    _cached: tuple[float, float | None] | None = field(default=None, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _warned_day: datetime | None = field(default=None, init=False)
    _reached_day: datetime | None = field(default=None, init=False)
    _last: tuple[float, datetime] | None = field(default=None, init=False)  # (spent, resets_at) of the last read

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
                self._last = (spent, midnight + timedelta(days=1))
                if verdict is not None:
                    if self._reached_day != midnight:  # once a day, not at every 5-second refresh while locked
                        self._reached_day = midnight
                        _log.warning("%s daily spend cap reached: %.4f of %.2f USD", self.label, spent, self.cap_usd)
                elif (self.warn_ratio is not None and spent >= self.warn_ratio * self.cap_usd
                      and self._warned_day != midnight):  # fmt: skip
                    self._warned_day = midnight
                    _log.warning("%s daily spend near cap: %.4f of %.2f USD (%.0f%%)", self.label, spent, self.cap_usd,
                                 100 * spent / self.cap_usd if self.cap_usd else 100.0)  # fmt: skip
            except Exception:  # the ledger cannot be read: fail closed
                _log.warning("%s daily spend ledger unreadable; refused", self.label, exc_info=True)
                self._last = None  # no stale spend shown beside the refusal
                verdict = until_reset
            self._cached = (self.monotonic(), verdict)
            return verdict

    def status(self) -> dict[str, Any]:
        """Today's spend against the cap, for an administrator: read through the same 5-second cache."""

        verdict = self()
        spent, resets = self._last if self._last is not None else (None, None)
        warned = self._warned_day is not None and resets is not None and self._warned_day == resets - timedelta(days=1)
        return {"cap_usd": self.cap_usd, "spent_usd": None if spent is None else round(spent, 4),
                "ratio": None if spent is None or not self.cap_usd else round(spent / self.cap_usd, 4),
                "warned": warned or verdict is not None, "reached": verdict is not None, "readable": spent is not None,
                "resets_at": resets.isoformat() if resets else None}  # fmt: skip


class LiveSpendGuard:
    """The daily cap, read at each check (Platform Admin, D-172): `cap()` is the cap now, None for "no cap". A change of
    cap starts a fresh guard, so the 5-second verdict cache never answers for the old number; with no cap a turn is
    always allowed, exactly as when the guard did not exist."""

    def __init__(self, cap: Callable[[], float | None], read: SpendReader | None, *,
                 ceiling: Callable[[], float | None] | None = None, **guard: Any) -> None:  # fmt: skip
        """`ceiling`: the system-wide guard (ai/spend_gate.py `ceiling_wait`), checked first - a turn stops once the
        whole system's daily spend is reached, whatever this cap is."""
        self._cap = cap
        self._read = read
        self._ceiling = ceiling
        self._guard = guard
        self._current: tuple[float, DailySpendGuard] | None = None
        self._lock = threading.Lock()

    def __call__(self) -> float | None:
        refused = self.check()
        return refused[0] if refused is not None else None

    def check(self) -> tuple[float, str] | None:
        """(seconds until it resets, which limit refused: "system" or "agent"), or None when a turn may run."""

        if self._ceiling is not None:
            wait = self._ceiling()
            if wait is not None:
                return wait, "system"
        wait = self._own()
        return (wait, "agent") if wait is not None else None

    def _own(self) -> float | None:
        try:
            cap = self._cap()
        except Exception:  # noqa: BLE001 - an unreadable cap setting is not "no cap" for a guard that exists
            _log.warning("agent daily spend cap unreadable; turns refused", exc_info=True)
            return 3600.0
        if cap is None:
            return None
        if self._read is None:  # a cap with no ledger to read refuses every turn: it fails closed
            return 3600.0
        with self._lock:
            if self._current is None or self._current[0] != cap:
                self._current = (cap, DailySpendGuard(cap_usd=cap, read=self._read, **self._guard))
            guard = self._current[1]
        return guard()

    def status(self) -> dict[str, Any]:
        """The agent cap now and today's spend against it, for an administrator; {"cap_usd": None} with no cap."""

        try:
            cap = self._cap()
        except Exception:  # noqa: BLE001 - shown as what it does: turns are refused
            return {"cap_usd": None, "reached": True, "error": "cap_unreadable"}
        if cap is None:
            return {"cap_usd": None}
        if self._read is None:
            return {"cap_usd": cap, "reached": True, "error": "no_ledger"}
        self()  # refresh the guard for this cap
        with self._lock:
            guard = self._current[1] if self._current is not None and self._current[0] == cap else None
        return guard.status() if guard is not None else {"cap_usd": cap, "reached": True, "error": "no_guard"}
