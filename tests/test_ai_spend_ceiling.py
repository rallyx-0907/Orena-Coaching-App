"""The system-wide daily AI spend ceiling (owner, 2026-10-18: $5 a day on :8000, a warning at 80%, AI locked until the
next UTC midnight once reached). It reads the whole shared AI ledger, every capability, as the agent cap does."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pytest

from writing_coach.agent.budget import DailySpendGuard, LiveSpendGuard
from writing_coach.ai import spend_gate

NOW = datetime(2026, 10, 18, 21, 0, tzinfo=UTC)


class Ledger:
    def __init__(self, usd=0.0, unpriced=0, fail=False):
        self.usd, self.unpriced, self.fail = usd, unpriced, fail

    def __call__(self, since):
        if self.fail:
            raise RuntimeError("ledger down")
        return self.usd, self.unpriced


@pytest.fixture(autouse=True)
def clean():
    spend_gate.configure_ceiling(None, read=None)
    spend_gate.reset()
    yield
    spend_gate.configure_ceiling(None, read=None)
    spend_gate.reset()


def ceiling(cap, ledger, ratio=0.8):
    spend_gate.configure_ceiling(cap, read=ledger, warn_ratio=ratio, now=lambda: NOW, monotonic=iter(range(0, 10**6, 10)).__next__)


def test_the_settings_parse_and_refuse_to_guess():
    assert spend_gate.ceiling_from_env({}) is None and spend_gate.ceiling_from_env({"AI_DAILY_SPEND_CEILING_USD": " "}) is None
    assert spend_gate.ceiling_from_env({"AI_DAILY_SPEND_CEILING_USD": "5"}) == 5.0
    assert spend_gate.warn_ratio_from_env({}) == 0.8
    for bad in ("-1", "nan", "five"):
        with pytest.raises(ValueError):
            spend_gate.ceiling_from_env({"AI_DAILY_SPEND_CEILING_USD": bad})
    for bad in ("0", "1.5", "x"):
        with pytest.raises(ValueError):
            spend_gate.warn_ratio_from_env({"AI_DAILY_SPEND_WARN_RATIO": bad})


def test_without_a_ceiling_nothing_is_refused():
    assert spend_gate.ceiling_reached() is False
    assert spend_gate.ceiling_status() == {"ceiling_usd": None}


def test_below_the_warning_nothing_happens_and_at_80_percent_it_warns_once_a_day(caplog):
    ledger = Ledger(usd=3.9)
    ceiling(5.0, ledger)
    with caplog.at_level(logging.WARNING):
        assert spend_gate.ceiling_reached() is False
        assert not [r for r in caplog.records if "near" in r.getMessage()]
        ledger.usd = 4.0
        assert spend_gate.ceiling_reached() is False
        assert spend_gate.ceiling_reached() is False
    near = [r for r in caplog.records if "near" in r.getMessage()]
    assert len(near) == 1 and "4.0000 of 5.00" in near[0].getMessage()
    status = spend_gate.ceiling_status()
    assert status["ceiling_usd"] == 5.0 and status["spent_usd"] == 4.0 and status["warned"] is True
    assert status["reached"] is False and status["resets_at"] == "2026-10-19T00:00:00+00:00"


def test_at_the_ceiling_every_paid_entry_is_refused_until_midnight():
    ceiling(5.0, Ledger(usd=5.0))
    assert spend_gate.ceiling_reached() is True
    assert spend_gate.ceiling_status()["reached"] is True
    # a capability's own cap would allow the call; the system ceiling refuses it
    assert spend_gate.paid_refused("word_translation", "word_translation.daily_spend_cap_usd") is True


def test_an_unreadable_ledger_fails_closed_and_unpriced_calls_count():
    ceiling(5.0, Ledger(fail=True))
    assert spend_gate.ceiling_reached() is True
    spend_gate.reset()
    ceiling(0.05, Ledger(usd=0.0, unpriced=5))  # 5 x the 0.01 USD allowance
    assert spend_gate.ceiling_reached() is True


def test_the_agent_stops_at_the_system_ceiling_even_below_its_own_cap():
    ceiling(5.0, Ledger(usd=5.0))
    agent = LiveSpendGuard(lambda: 50.0, Ledger(usd=5.0), ceiling=spend_gate.ceiling_check)
    assert agent() is not None  # its own $50 is far off; the system's $5 is reached
    assert LiveSpendGuard(lambda: None, None, ceiling=spend_gate.ceiling_check)() is not None


def test_the_lock_lifts_at_utc_midnight_and_the_warning_comes_again_the_next_day(caplog):
    clock = [NOW]
    ticks = iter(range(0, 10**7, 10))
    ledger = Ledger(usd=4.5)
    guard = DailySpendGuard(cap_usd=5.0, read=ledger, now=lambda: clock[0], monotonic=ticks.__next__, warn_ratio=0.8,
                            label="system")
    with caplog.at_level(logging.WARNING):
        assert guard() is None
        ledger.usd = 5.0
        assert guard() is not None and guard() is not None  # locked; "reached" is logged once, not every check
        clock[0] = NOW.replace(day=19, hour=0, minute=1)
        ledger.usd = 4.2  # today's ledger
        assert guard() is None
    lines = [r.getMessage() for r in caplog.records]
    assert len([m for m in lines if "near cap" in m]) == 2 and len([m for m in lines if "cap reached" in m]) == 1


def test_the_admin_status_never_shows_a_stale_or_missing_cap():
    ledger = Ledger(usd=0.5)
    cap = [1.0]
    agent = LiveSpendGuard(lambda: cap[0], ledger)
    assert agent.status()["cap_usd"] == 1.0 and agent.status()["reached"] is False
    cap[0] = None  # switched off: no old cap shown
    assert agent.status() == {"cap_usd": None}
    unreadable = LiveSpendGuard(lambda: (_ for _ in ()).throw(ValueError("bad")), ledger)
    assert unreadable() is not None and unreadable.status()["reached"] is True
    no_ledger = LiveSpendGuard(lambda: 1.0, None)
    assert no_ledger.status() == {"cap_usd": 1.0, "reached": True, "error": "no_ledger"}
    ceiling(5.0, Ledger(usd=1.0))
    assert spend_gate.ceiling_status()["spent_usd"] == 1.0
    spend_gate.configure_ceiling(5.0, read=Ledger(fail=True))
    status = spend_gate.ceiling_status()
    assert status["reached"] is True and status["spent_usd"] is None and status["readable"] is False


def test_the_guard_warns_once_per_day_with_its_label(caplog):
    clock = [NOW]
    ticks = iter(range(0, 10**6, 10))
    guard = DailySpendGuard(cap_usd=1.0, read=Ledger(usd=0.85), now=lambda: clock[0], monotonic=ticks.__next__,
                            warn_ratio=0.8, label="agent")
    with caplog.at_level(logging.WARNING):
        guard()
        guard()
    assert len([r for r in caplog.records if "agent daily spend near cap" in r.getMessage()]) == 1


def test_the_admin_view_is_admin_only_and_reports_both_limits(monkeypatch):
    from fastapi.testclient import TestClient

    import app as app_module

    ceiling(5.0, Ledger(usd=4.2))
    client = TestClient(app_module.app)
    monkeypatch.setattr(app_module, "require_admin", lambda request: {"role": "admin"})
    body = client.get("/api/admin/ai-spend").json()
    assert body["system"]["ceiling_usd"] == 5.0 and body["system"]["spent_usd"] == 4.2 and body["system"]["warned"]
    assert "agent" in body

    def refuse(request):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="admin_required")

    monkeypatch.setattr(app_module, "require_admin", refuse)
    assert client.get("/api/admin/ai-spend").status_code == 403


def test_check_says_which_limit_refused_and_whether_it_is_a_fault():
    """Review of #304, P2-5: the real LiveSpendGuard.check, not a stub."""
    read_cap = []

    def cap():
        read_cap.append(1)
        return 1.0

    ceiling(5.0, Ledger(usd=5.0))
    reached = LiveSpendGuard(cap, Ledger(usd=0.0), ceiling=spend_gate.ceiling_check)
    wait, scope, fault = reached.check()
    assert scope == "system" and fault is False and wait > 0 and read_cap == []  # the agent cap is not even read
    assert reached() == wait
    spend_gate.configure_ceiling(None, read=None)
    assert LiveSpendGuard(lambda: 1.0, Ledger(usd=1.0)).check()[1:] == ("agent", False)
    assert LiveSpendGuard(lambda: 1.0, Ledger(usd=0.1)).check() is None
    unreadable = LiveSpendGuard(lambda: (_ for _ in ()).throw(ValueError("bad")), Ledger())
    assert unreadable.check() == (3600.0, "agent", True)
    assert LiveSpendGuard(lambda: 1.0, Ledger(fail=True)).check()[1:] == ("agent", True)
    spend_gate.configure_ceiling(5.0, read=Ledger(fail=True))
    assert LiveSpendGuard(lambda: None, None, ceiling=spend_gate.ceiling_check).check()[1:] == ("system", True)
