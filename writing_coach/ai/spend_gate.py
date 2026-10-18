"""The daily spend gate of a capability's paid pool entries (AI Cost Router, D-195 amendment 2026-10-14).

    paid_refused(capability, cap_policy) -> bool

True means "do not ask a paid model now". It is True when the cap policy is unreadable, zero or empty, when today's
(UTC) spend of this one capability in the shared AI ledger has reached the cap, and when the ledger cannot be read:
it fails closed. The free pool is never gated. The verdict is cached for a few seconds by `DailySpendGuard`, so the
cap is soft by a few calls in flight, exactly like the Orena daily cap.
"""

from __future__ import annotations

import logging
import math
import threading
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from writing_coach import policies
from writing_coach.agent.budget import DailySpendGuard

_log = logging.getLogger(__name__)

_lock = threading.Lock()
_guards: dict[str, tuple[float, DailySpendGuard]] = {}


CEILING_ENV = "AI_DAILY_SPEND_CEILING_USD"
WARN_ENV = "AI_DAILY_SPEND_WARN_RATIO"
DEFAULT_WARN_RATIO = 0.8

# The system-wide daily ceiling (owner, 2026-10-18: $5 a day on :8000, a warning at 80%, AI locked until the next UTC
# midnight once reached): today's spend across the WHOLE shared AI ledger, every capability. Installed by app.py from
# the environment; unset, there is no ceiling and nothing here changes.
_ceiling: DailySpendGuard | None = None


def ceiling_from_env(environ: Mapping[str, str]) -> float | None:
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


def configure_ceiling(cap_usd: float | None, *, read: Callable[[datetime], tuple[float, int]] | None,
                      warn_ratio: float = DEFAULT_WARN_RATIO, **guard: Any) -> None:  # fmt: skip
    """Install the system ceiling (`read`: the whole ledger's spend since a moment). A ceiling with nothing to read
    refuses every paid call: it fails closed."""

    global _ceiling
    if cap_usd is None:
        _ceiling = None
        return
    reader = read if read is not None else _unreadable
    _ceiling = DailySpendGuard(cap_usd=cap_usd, read=reader, warn_ratio=warn_ratio, label="system", **guard)


def _unreadable(since: datetime) -> tuple[float, int]:
    raise RuntimeError("no AI ledger to read the system ceiling from")


def ceiling_usd() -> float | None:
    return _ceiling.cap_usd if _ceiling is not None else None


def ceiling_reached() -> bool:
    """True when today's whole-system AI spend has reached the ceiling (or cannot be read): no paid call now."""

    return _ceiling is not None and _ceiling() is not None


def ceiling_status() -> dict[str, Any]:
    if _ceiling is None:
        return {"ceiling_usd": None}
    status = _ceiling.status()
    return {"ceiling_usd": status.pop("cap_usd"), **status}


def reset() -> None:
    with _lock:
        _guards.clear()


def _reader(capability: str, provider: str | None = None, model: str | None = None):
    def read(since: datetime) -> tuple[float, int]:
        from writing_coach.ai.platform import _installed_platform_repository

        repository = _installed_platform_repository()
        if provider is None:
            return repository.ai_spend_since_for_capability(capability, since)
        # PR-MON-7: one rung's own spend (the reviewed paid backup), not the capability's total.
        return repository.ai_spend_since_for_capability(capability, since, provider=provider, model=model)

    return read


def paid_refused(capability: str, cap_policy: str, *, provider: str | None = None, model: str | None = None) -> bool:
    """`provider`/`model` given: the cap measures that one (provider, model)'s spend for this capability (a routed
    capability's reviewed backup, PR-MON-7); otherwise the capability's whole paid spend (word translation). The
    system ceiling refuses every paid entry once reached, whatever the capability's own cap."""
    if ceiling_reached():
        return True
    try:
        cap = policies.value_strict(cap_policy)
        cap = float(cap) if cap is not None else 0.0
    except Exception:  # noqa: BLE001 - an unreadable cap is not "no cap" for a paid call
        _log.warning("word spend cap policy unreadable; paid entries skipped", exc_info=True)
        return True
    if not cap > 0:
        return True
    key = capability if provider is None else f"{capability}|{provider}|{model}"
    with _lock:
        held = _guards.get(key)
        if held is None or held[0] != cap:
            held = _guards[key] = (cap, DailySpendGuard(cap_usd=cap, read=_reader(capability, provider, model)))
    return held[1]() is not None
