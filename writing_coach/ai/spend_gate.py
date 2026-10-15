"""The daily spend gate of a capability's paid pool entries (AI Cost Router, D-195 amendment 2026-10-14).

    paid_refused(capability, cap_policy) -> bool

True means "do not ask a paid model now". It is True when the cap policy is unreadable, zero or empty, when today's
(UTC) spend of this one capability in the shared AI ledger has reached the cap, and when the ledger cannot be read:
it fails closed. The free pool is never gated. The verdict is cached for a few seconds by `DailySpendGuard`, so the
cap is soft by a few calls in flight, exactly like the Orena daily cap.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime

from writing_coach import policies
from writing_coach.agent.budget import DailySpendGuard

_log = logging.getLogger(__name__)

_lock = threading.Lock()
_guards: dict[str, tuple[float, DailySpendGuard]] = {}


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
    capability's reviewed backup, PR-MON-7); otherwise the capability's whole paid spend (word translation)."""
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
