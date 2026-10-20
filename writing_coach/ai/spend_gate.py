"""The daily spend gate of a capability's paid pool entries (AI Cost Router, D-195 amendment 2026-10-14), per learner since
D-251, and the system's daily AI spend MONITOR.

    paid_refused(capability, cap_policy) -> bool

True means "do not ask a paid model now". It is True when the cap policy is unreadable, zero or empty, when today's
(UTC) spend of this one capability has reached the cap, and when the ledger cannot be read: it fails closed. Since D-251
(owner, 2026-10-21: no app-wide cap, only a cap per learner by plan) the spend counted is the REQUEST'S OWN LEARNER's,
from the per-account ledger (`ai_cost_records`), so one learner reaching a capability's cap never stops another. Work
with no signed-in account (a background job) is measured over the whole capability, as before - it is not a learner.
The free pool is never gated. The verdict is cached for a few seconds by `DailySpendGuard`, so the cap is soft by a few
calls in flight.

The system monitor (`AI_DAILY_SPEND_CEILING_USD`, Admin's `ai.daily_spend_ceiling_usd`, warning at
`ai.daily_spend_warn_ratio`) adds up today's spend across the whole shared AI ledger, exactly as the old ceiling did, and
ALERTS: a warning line at the ratio, a high-severity line at the threshold, the provider health signal
(ai/health_signal.py, the :8000 health.log) and Admin's overview banner. It NEVER refuses a request (D-251 supersedes
PRE-502 R2's fail-closed ceiling). `observe()` is the tick every paid path calls; it cannot raise.
"""

from __future__ import annotations

import logging
import math
import threading
from collections import OrderedDict
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from writing_coach import policies
from writing_coach.ai.base import AIProviderUnavailable
from writing_coach.agent.budget import DailySpendGuard

_log = logging.getLogger(__name__)

_lock = threading.Lock()
_guards: OrderedDict[str, tuple[float, DailySpendGuard]] = OrderedDict()
MAX_GUARDS = 8192   # one per (learner, capability) in use today; the oldest are dropped past this


CEILING_ENV = "AI_DAILY_SPEND_CEILING_USD"
WARN_ENV = "AI_DAILY_SPEND_WARN_RATIO"
DEFAULT_WARN_RATIO = 0.8
CEILING_REASON = "system_ceiling"


class SpendCeilingReached(AIProviderUnavailable):
    """Never raised since D-251 (the system figure is a monitor). Kept only because agent/api.py still names it; the
    Intelligence lane removes that handler."""

    code = CEILING_REASON

    def __init__(self) -> None:
        super().__init__("The daily AI budget is used up; AI is paused until the next UTC midnight.")


def ceiling_from_env(environ: Mapping[str, str]) -> float | None:
    """The monitor's alert threshold in USD a day (the variable kept its old name, so :8000's environment still reads)."""
    raw = str(environ.get(CEILING_ENV, "")).strip()
    if not raw:
        return None
    value = float(raw)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{CEILING_ENV} must be a non-negative number of USD")
    return value


def warn_ratio_from_env(environ: Mapping[str, str]) -> float:
    raw = str(environ.get(WARN_ENV, "")).strip()
    if not raw:
        return DEFAULT_WARN_RATIO
    value = float(raw)
    if not (math.isfinite(value) and 0 < value <= 1):
        raise ValueError(f"{WARN_ENV} must be a share of the ceiling, above 0 and at most 1")
    return value


CEILING_POLICY = "ai.daily_spend_ceiling_usd"
WARN_POLICY = "ai.daily_spend_warn_ratio"
_ceiling_lock = threading.Lock()
# (threshold now, warn ratio now, ledger reader, guard options); None: no monitor was installed.
_ceiling_source: tuple[Callable[[], float | None], Callable[[], float], Callable[[datetime], tuple[float, int]],
                       dict[str, Any]] | None = None
_ceiling: DailySpendGuard | None = None
_ceiling_key: tuple[float, float] | None = None
_alerted_day: str | None = None


def live_ceiling() -> float | None:
    """The alert threshold now: the lower of AI_DAILY_SPEND_CEILING_USD and Admin's `ai.daily_spend_ceiling_usd`."""
    return policies.value(CEILING_POLICY)


def live_warn_ratio() -> float:
    return float(policies.value(WARN_POLICY))


def configure_ceiling(cap_usd: float | None | Callable[[], float | None], *,
                      read: Callable[[datetime], tuple[float, int]] | None,
                      warn_ratio: float | Callable[[], float] = DEFAULT_WARN_RATIO, **guard: Any) -> None:  # fmt: skip
    """Install the system monitor (`read`: the whole ledger's spend since a moment). `cap_usd` and `warn_ratio` are a
    number, or a callable read at each check (app.py: `live_ceiling`, `live_warn_ratio`)."""

    global _ceiling, _ceiling_source, _ceiling_key, _alerted_day
    cap = cap_usd if callable(cap_usd) else (lambda fixed=cap_usd: fixed)
    warn = warn_ratio if callable(warn_ratio) else (lambda fixed=warn_ratio: fixed)
    with _ceiling_lock:
        _ceiling_source = (cap, warn, read if read is not None else _unreadable, dict(guard))
        _ceiling, _ceiling_key, _alerted_day = None, None, None
    _current_ceiling()


def _current_ceiling() -> DailySpendGuard | None:
    global _ceiling, _ceiling_key
    source = _ceiling_source
    if source is None:
        return None
    cap_now, warn_now, reader, options = source
    try:
        cap = cap_now()
    except Exception:  # noqa: BLE001 - keep the last monitor rather than drop it
        _log.warning("system spend monitor threshold unreadable; keeping the last one", exc_info=True)
        return _ceiling
    if cap is None:
        with _ceiling_lock:
            _ceiling, _ceiling_key = None, None
        return None
    try:
        ratio = float(warn_now())
    except Exception:  # noqa: BLE001
        ratio = DEFAULT_WARN_RATIO
    key = (float(cap), ratio)
    with _ceiling_lock:
        if _ceiling is None or _ceiling_key != key:
            _ceiling = DailySpendGuard(cap_usd=key[0], read=reader, warn_ratio=key[1], label="system", **options)
            _ceiling_key = key
        return _ceiling


def _unreadable(since: datetime) -> tuple[float, int]:
    raise RuntimeError("no AI ledger to read the system spend from")


def ceiling_usd() -> float | None:
    guard = _current_ceiling()
    return guard.cap_usd if guard is not None else None


def observe() -> None:
    """Tick the system monitor (every paid path calls it before sending). It logs the warning at the ratio and a
    high-severity alert once a UTC day at the threshold. It never refuses and never raises."""
    global _alerted_day
    try:
        guard = _current_ceiling()
        if guard is None:
            return
        reached = guard.refusal()
        if reached is None or reached[1]:   # below the threshold, or the ledger could not be read (not a reached day)
            return
        status = guard.status()
        day = str(status.get("resets_at") or "")
        if day and day != _alerted_day:
            _alerted_day = day
            _log.error("ALERT system daily AI spend reached the alert threshold: %.4f of %.2f USD (monitor only; no "
                       "learner is refused, per-learner caps apply, D-251)", float(status.get("spent_usd") or 0.0),
                       float(status.get("cap_usd") or 0.0))
    except Exception:  # noqa: BLE001 - a monitor never costs a learner a request
        _log.warning("system spend monitor failed", exc_info=True)


def ceiling_check() -> None:
    """The agent guard's former `ceiling=` hook: monitor-only since D-251 (ticks, never refuses)."""
    observe()
    return None


def ceiling_status() -> dict[str, Any]:
    """Today's whole-system spend against the alert threshold, for Admin and the health signal. `reached` means the
    threshold is reached (alert, severity high); nothing is paused. `monitor_only` says so to every reader."""
    guard = _current_ceiling()
    if guard is None:
        return {"ceiling_usd": None, "monitor_only": True}
    observe()
    status = guard.status()
    readable = bool(status.get("readable"))
    reached = bool(status.get("reached")) and readable   # a ledger that cannot be read is unknown, not an alert
    warned = bool(status.get("warned")) and readable
    return {"ceiling_usd": status.pop("cap_usd"), **status, "reached": reached, "warned": warned,
            "severity": "high" if reached else "medium" if warned else None, "monitor_only": True}


def reset() -> None:
    with _lock:
        _guards.clear()


def _reader(capability: str, provider: str | None = None, model: str | None = None, account: str | None = None):
    def read(since: datetime) -> tuple[float, int]:
        from writing_coach.ai.platform import _installed_platform_repository

        repository = _installed_platform_repository()
        if account is not None:
            # D-251: this learner's own spend of this capability (and of one rung, when given) from `ai_cost_records`.
            return repository.ai_spend_since_for_account(account, since, capability=capability, provider=provider,
                                                         model=model)
        if provider is None:
            return repository.ai_spend_since_for_capability(capability, since)
        # PR-MON-7: one rung's own spend (the reviewed paid backup), not the capability's total.
        return repository.ai_spend_since_for_capability(capability, since, provider=provider, model=model)

    return read


def paid_refused(capability: str, cap_policy: str, *, provider: str | None = None, model: str | None = None) -> bool:
    """`provider`/`model` given: the cap measures that one (provider, model)'s spend for this capability (a routed
    capability's reviewed backup, PR-MON-7); otherwise the capability's whole paid spend (word translation). Inside a
    learner's request it is that learner's own spend (D-251); the system monitor never refuses here."""
    from writing_coach.ai.learner_cost import current_account

    observe()
    try:
        cap = policies.value_strict(cap_policy)
        cap = float(cap) if cap is not None else 0.0
    except Exception:  # noqa: BLE001 - an unreadable cap is not "no cap" for a paid call
        _log.warning("paid spend cap policy unreadable; paid entries skipped", exc_info=True)
        return True
    if not cap > 0:
        return True
    account = current_account()
    key = "|".join((account or "*", capability, provider or "", model or ""))
    with _lock:
        held = _guards.get(key)
        if held is None or held[0] != cap:
            held = _guards[key] = (cap, DailySpendGuard(cap_usd=cap, read=_reader(capability, provider, model, account),
                                                        label=f"{capability} ({'learner' if account else 'system'})"))
        _guards.move_to_end(key)
        while len(_guards) > MAX_GUARDS:
            _guards.popitem(last=False)
    return held[1]() is not None
