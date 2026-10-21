"""The Gate 1 live re-run script (D1; scripts/gate1_live_check.py): a dry run by default, refused before any call when
the account is unknown or the day's AI ceiling is near, and the four checks run as the account when asked to."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gate1_live_check.py"


@pytest.fixture()
def script(monkeypatch):
    monkeypatch.setitem(sys.modules, "app", types.SimpleNamespace())  # the script imports the app; not here
    spec = importlib.util.spec_from_file_location("gate1_live_check", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "_account", lambda app, email: {"user_key": "sub-1", "role": "user"})
    monkeypatch.setattr(module, "_spend", lambda: {"ceiling_usd": 2.0, "spent_usd": 0.4, "reached": False})
    monkeypatch.setattr(module, "_learner_cap", lambda user_key: {"state": "ok", "plan": "plus", "cap_usd": 0.1,
                                                                   "spent_usd": 0.0, "fault": False})
    return module


def _run(script, capsys, *args):
    code = script.main(["--email", "tester@example.com", "--language", "en", *args])
    return code, json.loads(capsys.readouterr().out)


def test_the_default_is_a_dry_run_that_calls_nothing(script, capsys, monkeypatch):
    called = []
    for name in ("_chat", "_why_here", "_review", "_listening_meaning"):
        monkeypatch.setattr(script, name, lambda *a, _n=name: called.append(_n))
    code, report = _run(script, capsys)
    assert code == 0 and report["execute"] is False and called == []
    assert report["account"] == "te***@example.com"  # never the email in full
    assert report["f1_learner_cap_readable"] is True and len(report["would_run"]) == 4


def test_an_unknown_account_is_refused(script, capsys, monkeypatch):
    monkeypatch.setattr(script, "_account", lambda app, email: None)
    code, report = _run(script, capsys, "--execute")
    assert code == 2 and report["refused"] == "no such account"


def test_the_system_total_is_a_monitor_and_never_refuses_the_run(script, capsys, monkeypatch):
    """D-251: no app-wide cap - a system total past its old ceiling refuses nothing."""
    monkeypatch.setattr(script, "_spend", lambda: {"ceiling_usd": 2.0, "spent_usd": 2.5, "reached": True})
    code, report = _run(script, capsys)
    assert code == 0 and "refused" not in report


def test_an_account_at_its_plans_ceiling_is_refused_before_any_call(script, capsys, monkeypatch):
    monkeypatch.setattr(script, "_learner_cap", lambda user_key: {"state": "refuse", "plan": "free", "cap_usd": 0.02,
                                                                   "spent_usd": 0.03, "fault": False})
    code, report = _run(script, capsys, "--execute")
    assert code == 2 and "plan's daily AI ceiling" in report["refused"]


def test_an_unreadable_learner_cap_is_reported(script, capsys, monkeypatch):
    monkeypatch.setattr(script, "_learner_cap", lambda user_key: {"state": "degrade", "plan": "plus", "cap_usd": 0.1,
                                                                   "spent_usd": None, "fault": True})
    assert _run(script, capsys)[1]["f1_learner_cap_readable"] is False


def test_execute_runs_the_four_checks_as_the_account_and_reports_the_run_spend(script, capsys, monkeypatch):
    from writing_coach.core.request_context import current_user_key

    seen = []

    def check(name):
        def run(*args):
            seen.append((name, current_user_key()))
            return True, {}
        return run

    for name in ("_chat", "_why_here", "_review", "_listening_meaning"):
        monkeypatch.setattr(script, name, check(name))
    spends = iter([{"ceiling_usd": 2.0, "spent_usd": 0.4, "reached": False},
                   {"ceiling_usd": 2.0, "spent_usd": 0.4071, "reached": False}])
    monkeypatch.setattr(script, "_spend", lambda: next(spends))
    code, report = _run(script, capsys, "--execute", "--actor", "hermes-supervisor (on behalf of Calis)")
    assert code == 0 and [item["check"] for item in report["results"]] == [
        "chat_turn", "why_here", "writing_review", "listening_meaning"]
    assert all(user == "sub-1" for _name, user in seen)  # every check ran as the test account
    assert report["run_spend_usd"] == 0.0071 and report["actor"] == "hermes-supervisor (on behalf of Calis)"


def test_a_failing_check_is_recorded_and_the_run_goes_on(script, capsys, monkeypatch):
    def broken(*args):
        raise RuntimeError("provider down")

    monkeypatch.setattr(script, "_chat", broken)
    for name in ("_why_here", "_review", "_listening_meaning"):
        monkeypatch.setattr(script, name, lambda *a: (True, {}))
    code, report = _run(script, capsys, "--execute")
    assert code == 1
    assert report["results"][0] == {"check": "chat_turn", "ok": False, "ms": report["results"][0]["ms"],
                                    "error": "RuntimeError", "status": None, "category": None}
    assert [item["ok"] for item in report["results"][1:]] == [True, True, True]
