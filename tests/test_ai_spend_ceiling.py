"""The system's daily AI spend MONITOR (D-251, owner 2026-10-21: "không có trần chung cho app, chỉ có trần cho từng người
dùng theo gói"). It still reads the whole shared AI ledger, warns at the ratio and raises a high-severity alert at the
threshold - in the log, the provider health signal and Admin - but it never refuses a learner's request. It replaced the
2026-10-18 ceiling that paused paid AI for every learner until UTC midnight."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pytest

from writing_coach.agent.budget import DailySpendGuard, LiveSpendGuard
from writing_coach.ai import health_signal, spend_gate

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


def monitor(cap, ledger, ratio=0.8):
    spend_gate.configure_ceiling(cap, read=ledger, warn_ratio=ratio, now=lambda: NOW,
                                 monotonic=iter(range(0, 10**6, 10)).__next__)


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


def test_without_a_threshold_there_is_nothing_to_report():
    spend_gate.observe()
    assert spend_gate.ceiling_status() == {"ceiling_usd": None, "monitor_only": True}


def test_below_the_warning_nothing_happens_and_at_80_percent_it_warns_once_a_day(caplog):
    ledger = Ledger(usd=3.9)
    monitor(5.0, ledger)
    with caplog.at_level(logging.WARNING):
        spend_gate.observe()
        assert not [r for r in caplog.records if "near" in r.getMessage()]
        ledger.usd = 4.0
        spend_gate.observe()
        spend_gate.observe()
    near = [r for r in caplog.records if "near" in r.getMessage()]
    assert len(near) == 1 and "4.0000 of 5.00" in near[0].getMessage()
    status = spend_gate.ceiling_status()
    assert status["ceiling_usd"] == 5.0 and status["spent_usd"] == 4.0 and status["warned"] is True
    assert status["reached"] is False and status["severity"] == "medium" and status["monitor_only"] is True


def test_the_monitor_alerts_at_the_threshold_without_refusing_anything(caplog):
    """D-251: at the threshold a high-severity alert, once a UTC day; no paid call, agent turn or capability is refused."""
    monitor(5.0, Ledger(usd=5.0))
    with caplog.at_level(logging.WARNING):
        spend_gate.observe()
        spend_gate.observe()
    alerts = [r for r in caplog.records if r.getMessage().startswith("ALERT system daily AI spend")]
    assert len(alerts) == 1 and alerts[0].levelno == logging.ERROR and "no learner is refused" in alerts[0].getMessage()
    status = spend_gate.ceiling_status()
    assert status["reached"] is True and status["severity"] == "high" and status["monitor_only"] is True
    assert spend_gate.ceiling_check() is None   # the agent guard's hook only ticks
    agent = LiveSpendGuard(lambda: None, None, ceiling=spend_gate.ceiling_check)
    assert agent() is None and agent.check() is None   # no agent cap: the system figure stops no turn
    assert not hasattr(spend_gate, "ceiling_reached") and not hasattr(spend_gate, "require_below_ceiling")


def test_an_unreadable_ledger_is_not_an_alert_and_refuses_nothing():
    monitor(5.0, Ledger(fail=True))
    spend_gate.observe()
    status = spend_gate.ceiling_status()
    assert status["reached"] is False and status["readable"] is False and status["severity"] is None


def test_unpriced_calls_count_toward_the_alert():
    monitor(0.05, Ledger(usd=0.0, unpriced=5))  # 5 x the 0.01 USD allowance
    assert spend_gate.ceiling_status()["reached"] is True


def test_the_health_signal_carries_the_spend_monitor_as_a_high_severity_alert():
    """#452's health.log line: the report is an alert of severity high at the threshold, a medium note at the warning."""

    class Repository:
        def __init__(self, usd):
            self.usd = usd

        def list_ai_operation_events(self, limit):
            return []

        def ai_spend_since(self, since):
            return self.usd, 0

    values = {"ai.daily_spend_ceiling_usd": 2.0, "ai.daily_spend_warn_ratio": 0.8}
    reached = health_signal.spend_monitor(Repository(2.1), now=NOW, reader=values.__getitem__)
    assert reached["severity"] == "high" and reached["spent_usd"] == 2.1 and reached["threshold_usd"] == 2.0
    near = health_signal.spend_monitor(Repository(1.7), now=NOW, reader=values.__getitem__)
    assert near["severity"] == "medium"
    calm = health_signal.spend_monitor(Repository(0.1), now=NOW, reader=values.__getitem__)
    assert calm["severity"] is None
    report = health_signal._with_spend(health_signal.provider_health([], now=NOW), reached)
    assert report["status"] == "alert" and report["severity"] == "high" and report["alerts"] == []
    line = health_signal.health_line(report)
    assert line.startswith("status=alert severity=high") and "spend=reached(high)" in line
    assert "no learner is refused" in line
    none = health_signal.spend_monitor(Repository(9.0), now=NOW, reader={"ai.daily_spend_ceiling_usd": None,
                                                                          "ai.daily_spend_warn_ratio": 0.8}.__getitem__)
    assert none["severity"] is None and none["threshold_usd"] is None


def test_the_guard_lifts_at_utc_midnight_and_the_warning_comes_again_the_next_day(caplog):
    clock = [NOW]
    ticks = iter(range(0, 10**7, 10))
    ledger = Ledger(usd=4.5)
    guard = DailySpendGuard(cap_usd=5.0, read=ledger, now=lambda: clock[0], monotonic=ticks.__next__, warn_ratio=0.8,
                            label="system")
    with caplog.at_level(logging.WARNING):
        assert guard() is None
        ledger.usd = 5.0
        assert guard() is not None and guard() is not None  # "reached" is logged once, not every check
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
    monitor(5.0, Ledger(usd=1.0))
    assert spend_gate.ceiling_status()["spent_usd"] == 1.0


def test_the_admin_view_is_admin_only_and_reports_the_monitor(monkeypatch):
    from fastapi.testclient import TestClient

    import app as app_module

    monitor(5.0, Ledger(usd=4.2))
    client = TestClient(app_module.app)
    monkeypatch.setattr(app_module, "require_admin", lambda request: {"role": "admin"})
    body = client.get("/api/admin/ai-spend").json()
    assert body["system"]["ceiling_usd"] == 5.0 and body["system"]["spent_usd"] == 4.2 and body["system"]["warned"]
    assert body["system"]["monitor_only"] is True and "agent" in body

    def refuse(request):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="admin_required")

    monkeypatch.setattr(app_module, "require_admin", refuse)
    assert client.get("/api/admin/ai-spend").status_code == 403
