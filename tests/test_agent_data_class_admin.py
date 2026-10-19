"""The owner records each AI provider's learner-data class in Admin (G8, #264). The record is a platform setting read
at each use, so a class set there applies to the next turn with no restart; while none is saved, or it cannot be read,
the environment record (`AGENT_PROVIDER_DATA_CLASSES`) stays authoritative. Nothing is guessed: a provider not listed
is `none`."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from writing_coach.agent.data_class import DataClass, LiveProviderDataClasses, ProviderDataClasses

ENV = ProviderDataClasses.parse("gemini=learning_profile")


def test_with_no_admin_record_the_environment_record_stands():
    live = LiveProviderDataClasses(ENV, lambda: None)
    assert live.of("gemini", "gemini-3.5-flash-lite") is DataClass.LEARNING_PROFILE
    assert live.of("openai") is DataClass.NONE
    assert live.current()[1] == "environment"


def test_an_admin_record_applies_at_the_next_use_and_replaces_the_environment():
    stored = {"value": None}
    live = LiveProviderDataClasses(ENV, lambda: stored["value"])
    stored["value"] = {"classes": {"openai": "full_memory", "gemini:gemini-3.5-flash-lite": "none"}}
    assert live.of("openai") is DataClass.FULL_MEMORY
    assert live.of("gemini", "gemini-3.5-flash-lite") is DataClass.NONE
    assert live.of("gemini", "other") is DataClass.NONE  # not listed in the Admin record: none, not the env's class
    assert live.cleared("openai", None, DataClass.LEARNING_PROFILE)
    assert live.current()[1] == "admin"


def test_an_unreadable_record_keeps_the_last_good_one_and_never_guesses():
    state = {"value": {"classes": {"openai": "learning_profile"}}}

    def stored():
        if state["value"] == "boom":
            raise RuntimeError("store down")
        return state["value"]

    live = LiveProviderDataClasses(ENV, stored)
    assert live.of("openai") is DataClass.LEARNING_PROFILE
    state["value"] = "boom"
    assert live.of("openai") is DataClass.LEARNING_PROFILE  # the last record read well
    state["value"] = {"classes": {"openai": "everything"}}
    assert live.of("openai") is DataClass.LEARNING_PROFILE
    assert LiveProviderDataClasses(ENV, lambda: {"classes": {"x": 1}}).current() == (ENV, "environment")


@pytest.mark.parametrize("entries", [{"": "none"}, {":m": "none"}, {"a:": "none"}, {"a:b:c": "none"},
                                     {"a,b": "none"}, {"a": "secret"}, {"a": 2}, ["a"]])
def test_a_malformed_record_does_not_parse(entries):
    with pytest.raises(ValueError):
        ProviderDataClasses.from_mapping(entries)


@pytest.fixture()
def rig(monkeypatch):
    import app as app_module
    from writing_coach import admin_console_api

    settings: dict[str, dict] = {}
    repository = app_module._persistence_runtime.platform_repository
    monkeypatch.setattr(repository, "get_setting", lambda key: settings.get(key))
    monkeypatch.setattr(repository, "set_setting",
                        lambda key, value, **kw: settings.__setitem__(key, {"value": value}) or settings[key])
    audits = []
    monkeypatch.setattr(app_module, "require_admin", lambda request: {"google_sub": "admin-1", "role": "admin"})
    monkeypatch.setattr(admin_console_api, "_audit", lambda admin, action, **kw: audits.append((action, kw)))
    monkeypatch.setattr(admin_console_api, "_same_origin", lambda request: None)
    yield TestClient(app_module.app), settings, audits, app_module


def test_admin_shows_the_record_its_source_and_what_each_class_sends(rig):
    client, _settings, _audits, _ = rig
    view = client.get("/api/admin/agent/data-classes").json()
    assert view["source"] == "environment" and view["default"] == "none"
    assert "gemini" in view["providers"]
    assert [c["class"] for c in view["choices"]] == ["none", "learning_profile", "full_memory"]


def test_the_owner_saves_a_record_audited_and_the_agent_reads_it_next(rig):
    client, settings, audits, app_module = rig
    answer = client.put("/api/admin/agent/data-classes", json={"classes": {"gemini": "full_memory"}})
    assert answer.status_code == 200, answer.text
    assert answer.json()["source"] == "admin" and answer.json()["classes"] == {"gemini": "full_memory"}
    assert app_module._AGENT_DATA_CLASSES.of("gemini", "any") is DataClass.FULL_MEMORY
    action, record = audits[-1]
    assert action == "admin.agent_data_classes" and record["required"] is True
    assert record["payload"]["to"] == {"gemini": "full_memory"}


@pytest.mark.parametrize("classes,code", [({"gemini": "everything"}, "data_class_invalid"),
                                          ({"no-such-provider": "none"}, "data_class_unknown_provider")])
def test_a_bad_record_is_refused_and_nothing_is_saved(rig, classes, code):
    client, settings, audits, _ = rig
    answer = client.put("/api/admin/agent/data-classes", json={"classes": classes})
    assert answer.status_code == 422 and code in answer.text
    assert settings == {} and audits == []
