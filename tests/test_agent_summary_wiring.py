"""The app's two hooks for the rolling-summary telemetry (agent/summary.py): the price and the stored record."""

from __future__ import annotations

from types import SimpleNamespace

import app as app_module


def test_the_price_names_the_provider_and_model_and_estimates_the_cost(monkeypatch):
    import writing_coach.ai.platform as platform

    monkeypatch.setattr(platform, "active_selection", lambda: (SimpleNamespace(id="gemini"), "gemini-3.5-flash-lite"))
    priced = app_module._price_agent_summary(1000, 100)
    assert (priced["provider"], priced["model"]) == ("gemini", "gemini-3.5-flash-lite")
    assert priced["cost"]["state"] in {"estimated", "unpriced"}


def test_the_record_is_stored_as_an_agent_summary_event_for_the_learner(monkeypatch):
    seen = []
    repo = SimpleNamespace(record_admin_event=lambda *a, **k: seen.append((a, k)))
    monkeypatch.setattr(app_module, "_persistence_runtime", SimpleNamespace(platform_repository=repo))
    app_module._record_agent_summary("learner-1", {"trace_id": "t1", "outcome": "success"})
    (args, kwargs), = seen
    assert args == ("agent.summary",) and kwargs["actor"] == "learner-1" and kwargs["entity_id"] == "t1"
    assert kwargs["payload"] == {"trace_id": "t1", "outcome": "success"}
