"""PRE-502 R1/R2 (#369): what the published Privacy Policy and the cost policy promise must be in force on a public
runtime. A system daily AI spend ceiling (AI_DAILY_SPEND_CEILING_USD); the retention sweeps behind the periods the
policy states (Orena Memory 180 days, agent activity 90 days, feedback 24 months). Production refuses to start without
a ceiling; every public runtime logs each unmet promise as an ERROR at start and shows it in Admin's readiness."""

from __future__ import annotations

import logging

import pytest

from writing_coach.core.published_promises import enforce_at_start, unmet_promises

ON = {"feedback.retention_sweep": True, "agent.turn_retention_sweep": True}
KEPT = {"AI_DAILY_SPEND_CEILING_USD": "5", "AGENT_MEMORY_HMAC_KEYS": "v1:" + "k" * 40,
        "AGENT_MEMORY_RETENTION_SWEEP": "on", "AGENT_ENABLED": "true"}


def policy(values):
    return lambda key: values[key]


def test_everything_in_force_means_no_unmet_promise():
    assert unmet_promises(KEPT, policy(ON)) == []


def test_a_zero_ceiling_is_a_ceiling():
    """$0 refuses every paid call: stricter, not missing."""
    assert unmet_promises({**KEPT, "AI_DAILY_SPEND_CEILING_USD": "0"}, policy(ON)) == []


@pytest.mark.parametrize("change,code", [
    ({"AI_DAILY_SPEND_CEILING_USD": ""}, "spend_ceiling_unset"),
    ({"AI_DAILY_SPEND_CEILING_USD": "lots"}, "spend_ceiling_unset"),
    ({"AGENT_MEMORY_RETENTION_SWEEP": "off"}, "memory_retention_sweep_off"),
    ({"AGENT_MEMORY_RETENTION_SWEEP": ""}, "memory_retention_sweep_off"),
])
def test_each_unmet_environment_promise_is_named(change, code):
    assert [p.code for p in unmet_promises({**KEPT, **change}, policy(ON))] == [code]


@pytest.mark.parametrize("key,code", [("feedback.retention_sweep", "feedback_retention_sweep_off"),
                                      ("agent.turn_retention_sweep", "agent_turn_retention_sweep_off")])
def test_each_unmet_admin_sweep_is_named(key, code):
    assert [p.code for p in unmet_promises(KEPT, policy({**ON, key: False}))] == [code]


def test_a_promise_about_data_the_runtime_does_not_keep_is_not_unmet():
    """No memory keys: Orena Memory keeps nothing here. Agent off: no agent.turn row is written."""
    values = {"AI_DAILY_SPEND_CEILING_USD": "5"}
    assert unmet_promises(values, policy({**ON, "agent.turn_retention_sweep": False})) == []


def test_a_policy_that_cannot_be_read_counts_as_off():
    def broken(key):
        raise RuntimeError("store down")

    assert {p.code for p in unmet_promises(KEPT, broken)} == {"feedback_retention_sweep_off",
                                                              "agent_turn_retention_sweep_off"}


def test_production_refuses_to_start_without_a_ceiling_and_logs_every_unmet_promise(caplog):
    values = {**KEPT, "APP_ENV": "production", "AI_DAILY_SPEND_CEILING_USD": "", "AGENT_MEMORY_RETENTION_SWEEP": "off"}
    with caplog.at_level(logging.ERROR), pytest.raises(RuntimeError, match="AI_DAILY_SPEND_CEILING_USD"):
        enforce_at_start(values, policy(ON))
    assert "memory_retention_sweep_off" in caplog.text and "spend_ceiling_unset" in caplog.text


def test_staging_starts_but_logs_each_unmet_promise_as_an_error(caplog):
    values = {**KEPT, "APP_ENV": "staging", "AI_DAILY_SPEND_CEILING_USD": ""}
    with caplog.at_level(logging.ERROR):
        problems = enforce_at_start(values, policy({**ON, "feedback.retention_sweep": False}))
    assert {p.code for p in problems} == {"spend_ceiling_unset", "feedback_retention_sweep_off"}
    assert caplog.text.count("ERROR") >= 2 or len([r for r in caplog.records if r.levelno == logging.ERROR]) == 2


def test_development_says_nothing(caplog):
    with caplog.at_level(logging.ERROR):
        assert enforce_at_start({"APP_ENV": "development"}, policy({k: False for k in ON})) == []
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_admin_readiness_lists_the_unmet_promises_by_name(monkeypatch):
    from fastapi.testclient import TestClient

    import app as app_module

    monkeypatch.setattr(app_module, "require_admin", lambda request: {"google_sub": "admin-1", "role": "admin"})
    monkeypatch.delenv("AI_DAILY_SPEND_CEILING_USD", raising=False)
    summary = TestClient(app_module.app).get("/api/admin/readiness-summary").json()
    codes = [p["code"] for p in summary["unmet_promises"]]
    assert "spend_ceiling_unset" in codes and "feedback_retention_sweep_off" in codes
    assert all(set(p) == {"code", "message"} for p in summary["unmet_promises"])
