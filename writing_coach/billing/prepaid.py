"""Prepaid periods for a domestic gateway, where every payment is a one-off.

A paid order buys one period. Periods are additive: each paid order extends access from the later of its
payment time and the current end, so a late or out-of-order webhook can never shorten access or lose a paid
period. The new end is
`max(now, current end) + period`, computed under the account's lock (persistence/billing_repository.py), and a
refund is a replay of the remaining orders, so the end of access is always derived from the orders themselves.

Months are calendar months, clamped to the last day (31 Jan + 1 month = 28/29 Feb), in UTC; server time decides.
"""

from __future__ import annotations

import calendar
from datetime import UTC, datetime
from typing import Literal

Period = Literal["month", "year"]


def add_period(start: datetime, period: Period, count: int = 1) -> datetime:
    if start.tzinfo is None:
        raise ValueError("a period starts at an aware UTC time")
    if count < 1:
        raise ValueError("a period count is positive")
    start = start.astimezone(UTC)  # the database answers in its session zone; the calendar is UTC's
    months = count * (12 if period == "year" else 1)
    month_index = start.month - 1 + months
    year, month = start.year + month_index // 12, month_index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return start.replace(year=year, month=month, day=day)


def extended_until(current_end: datetime | None, now: datetime, period: Period) -> datetime:
    """The end of access after one more paid period: from now when access has lapsed, from its end otherwise."""

    base = now if current_end is None or current_end <= now else current_end
    return add_period(base, period)

