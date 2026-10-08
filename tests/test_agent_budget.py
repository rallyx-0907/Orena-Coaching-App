"""The staging daily spend cap: shared ledger, fail closed, the contract's 429."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from writing_coach.agent.budget import UNPRICED_ALLOWANCE_USD, DailySpendGuard, cap_from_env

NOON = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)


def guard(usd, unpriced=0, *, cap=1.0, fail=False):
    seen = []

    def read(since):
        seen.append(since)
        if fail:
            raise RuntimeError("ledger down")
        return usd, unpriced

    return DailySpendGuard(cap_usd=cap, read=read, now=lambda: NOON), seen


def test_under_the_cap_a_turn_runs_and_the_day_starts_at_utc_midnight():
    g, seen = guard(0.40)
    assert g() is None
    assert seen == [datetime(2026, 10, 4, tzinfo=UTC)]


def test_at_the_cap_the_turn_waits_until_the_next_utc_midnight():
    g, _ = guard(1.00)
    assert g() == 12 * 3600


def test_an_unpriced_call_counts_against_the_cap_never_as_zero():
    g, _ = guard(1.0 - UNPRICED_ALLOWANCE_USD, unpriced=1)
    assert g() is not None


def test_an_unreadable_ledger_fails_closed():
    g, _ = guard(0, fail=True)
    assert g() is not None


def test_the_cap_is_off_unless_set_and_refuses_nonsense():
    assert cap_from_env({}) is None
    assert cap_from_env({"AGENT_DAILY_SPEND_CAP_USD": "1"}) == 1.0
    with pytest.raises(ValueError):
        cap_from_env({"AGENT_DAILY_SPEND_CAP_USD": "-1"})
