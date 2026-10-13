"""Billing grace policy: how long a recoverable billing state keeps its paid entitlement (D-MON-011).

Billing v1 (human, 2026-10-13): a Polar subscription in `past_due` (Polar `past_due` / `unpaid`) keeps its paid plan
for **2 days**, counted from the moment its paid period ended (the subscription's `paid_through`, which the Polar
adapter records as `past_due_at`, else the unpaid cycle's start, for a past-due event - `writing_coach/billing/polar`).
After that it reads as Free until Polar reports it active again (payment recovered) or ended (retries exhausted).
No other provider or state has grace: payOS is prepaid and never past due, and `paused` / `pending` / `unknown`
have no approved policy (ORENA_COMMERCE_ARCHITECTURE.md §3: missing policy blocks paid admissions).

The resolver (`writing_coach.product.entitlement.resolve`) takes a `GracePolicy` as an input and knows no number;
this module is where the number lives. The environment pins it (`BILLING_PAST_DUE_GRACE_HOURS`, 0..336); otherwise
the human's 48 hours apply. A value that is not a whole number in range is ignored and logged, and the approved
default applies - a typo never removes or extends a paying learner's grace silently past the human's value.
Making it an Admin-edited policy (`writing_coach/policies.py`, D-172) needs the Admin page's EN/VI/ZH copy, owned by
the UI lane; it is a recorded follow-up, not part of PR-MON-1.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta

_log = logging.getLogger(__name__)

ENV = "BILLING_PAST_DUE_GRACE_HOURS"
DEFAULT_PAST_DUE_HOURS = 48          # human, 2026-10-13: "Polar past_due có grace period 2 ngày cho Billing v1"
MAX_PAST_DUE_HOURS = 14 * 24         # Polar's own longest benefit grace option
GRACE_PROVIDERS = frozenset({"polar"})


@dataclass(frozen=True)
class GracePolicy:
    """`windows`: provider -> {billing state -> how long after `paid_through` it still grants}."""

    windows: Mapping[str, Mapping[str, timedelta]] = field(default_factory=dict)

    def window(self, provider: str, state: str) -> timedelta | None:
        """The grace for this provider's state, or None when it has none."""
        found = self.windows.get(provider, {}).get(state)
        return found if found and found > timedelta(0) else None


NO_GRACE = GracePolicy()


def past_due_hours(env: Mapping[str, str] | None = None) -> int:
    raw = (env if env is not None else os.environ).get(ENV)
    if raw is None or not str(raw).strip():
        return DEFAULT_PAST_DUE_HOURS
    try:
        hours = int(str(raw).strip())
    except ValueError:
        hours = -1
    if not 0 <= hours <= MAX_PAST_DUE_HOURS:
        _log.warning("%s=%r is not a whole number of hours in 0..%d; using %d", ENV, raw, MAX_PAST_DUE_HOURS,
                     DEFAULT_PAST_DUE_HOURS)
        return DEFAULT_PAST_DUE_HOURS
    return hours


def current(env: Mapping[str, str] | None = None) -> GracePolicy:
    """The grace policy in force now (read when a plan is resolved, so an environment change applies on restart)."""
    window = timedelta(hours=past_due_hours(env))
    return GracePolicy({provider: {"past_due": window} for provider in GRACE_PROVIDERS})
