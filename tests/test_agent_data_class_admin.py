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


def test_an_unreadable_record_fails_closed_and_never_raises_a_class():
    """#357 review P1: the environment says gemini=learning_profile; the owner saved gemini=none in Admin. A read that
    fails - first read of a fresh worker, or after the owner lowered it - must not hand the higher class back."""
    state = {"value": {"classes": {"gemini": "none"}}}

    def stored():
        if state["value"] == "boom":
            raise RuntimeError("store down")
        return state["value"]

    live = LiveProviderDataClasses(ENV, stored)
    assert live.of("gemini") is DataClass.NONE
    state["value"] = "boom"
    assert live.of("gemini") is DataClass.NONE and live.current()[1] == "unavailable"  # not the env's learning_profile
    state["value"] = {"classes": {"gemini": "everything"}}
    assert live.of("gemini") is DataClass.NONE
    fresh = LiveProviderDataClasses(ENV, lambda: (_ for _ in ()).throw(RuntimeError("down")))
    assert fresh.of("gemini") is DataClass.NONE
    state["value"] = {"classes": {"gemini": "full_memory"}}
    lowered = LiveProviderDataClasses(ENV, stored)
    assert lowered.of("gemini") is DataClass.FULL_MEMORY
    state["value"] = "boom"  # the owner may have lowered it since: an earlier read is not the record in force
    assert lowered.of("gemini") is DataClass.NONE


def test_a_turn_uses_one_snapshot_of_the_record():
    reads = []
    live = LiveProviderDataClasses(ENV, lambda: reads.append(1) or {"classes": {"gemini": "full_memory"}})
    snapshot = live.snapshot()
    assert snapshot.of("gemini") is DataClass.FULL_MEMORY and snapshot.cleared("gemini", None, DataClass.FULL_MEMORY)
    assert len(reads) == 1


def test_a_model_id_may_carry_a_colon():
    record = ProviderDataClasses.from_mapping({"ollama:llama3:8b": "learning_profile"})
    assert record.of("ollama", "llama3:8b") is DataClass.LEARNING_PROFILE and record.of("ollama") is DataClass.NONE


@pytest.mark.parametrize("entries", [{"": "none"}, {":m": "none"}, {"a:": "none"},
                                     {"a,b": "none"}, {"a": "secret"}, {"a": 2}, ["a"]])
def test_a_malformed_record_does_not_parse(entries):
    with pytest.raises(ValueError):
        ProviderDataClasses.from_mapping(entries)


@pytest.fixture()
def rig(monkeypatch):
    import app as app_module
    from writing_coach import admin_console_api

    from writing_coach.persistence.platform_repository import SettingConflict

    settings: dict[str, dict] = {}
    audits = []
    versions = iter(f"2026-10-19T12:00:0{n}+00:00" for n in range(10))

    def set_setting(key, value, *, updated_by="", expected_updated_at=..., audit=None):
        current = settings.get(key)
        if expected_updated_at is not ... and (current["updated_at"] if current else None) != expected_updated_at:
            raise SettingConflict(key)
        settings[key] = {"value": value, "updated_at": next(versions), "updated_by": updated_by}
        audits.append((audit["action"], audit))  # written with the change, in one transaction (PostgreSQL)
        return settings[key]

    repository = app_module._persistence_runtime.platform_repository
    monkeypatch.setattr(repository, "get_setting", lambda key: settings.get(key))
    monkeypatch.setattr(repository, "set_setting", set_setting)
    monkeypatch.setattr(app_module, "require_admin", lambda request: {"google_sub": "admin-1", "role": "admin"})
    monkeypatch.setattr(admin_console_api, "_same_origin", lambda request: None)
    yield TestClient(app_module.app, headers={"Origin": "http://testserver"}), settings, audits, app_module


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
    assert action == "admin.agent_data_classes" and record["actor"] == "admin-1"
    assert record["payload"]["to"] == {"gemini": "full_memory"} and record["payload"]["from_source"] == "environment"


def test_a_save_over_a_newer_record_is_refused(rig):
    client, settings, audits, _ = rig
    first = client.put("/api/admin/agent/data-classes", json={"classes": {"gemini": "learning_profile"}}).json()
    stale = client.put("/api/admin/agent/data-classes", json={"classes": {"gemini": "full_memory"}})  # read nothing
    assert stale.status_code == 409 and "data_class_conflict" in stale.text
    assert settings["agent.provider_data_classes"]["value"] == {"classes": {"gemini": "learning_profile"}}
    again = client.put("/api/admin/agent/data-classes",
                       json={"classes": {"gemini": "none"}, "expected_updated_at": first["updated_at"]})
    assert again.status_code == 200 and again.json()["classes"] == {"gemini": "none"} and len(audits) == 2


@pytest.mark.parametrize("classes,code", [({"gemini": "everything"}, "data_class_invalid"),
                                          ({"no-such-provider": "none"}, "data_class_unknown_provider")])
def test_a_bad_record_is_refused_and_nothing_is_saved(rig, classes, code):
    client, settings, audits, _ = rig
    answer = client.put("/api/admin/agent/data-classes", json={"classes": classes})
    assert answer.status_code == 422 and code in answer.text
    assert settings == {} and audits == []
