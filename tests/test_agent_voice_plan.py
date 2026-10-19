"""Voice chat with Orena is for Plus and Pro only; Free chats in text (owner, 2026-10-19, via Hermes). The plan's
`orena.voice` entitlement: Free off, Plus and Pro on by the code's defaults (an administrator may change them in the plan
catalogue). Checked on the server, before any limit or token: `POST /api/agent/voice/session` and `/voice/extend` answer
403 `feature_not_in_plan` (context.feature "orena.voice"); `GET /api/agent/voice/voices` says `entitled` so the client
shows the upgrade sheet before the tap. Speaking practice is not touched."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from writing_coach.product import plan_features, quota
from tests.test_agent_api import client  # noqa: F401 - the agent router's test client fixture
from writing_coach.product.catalog import FREE, PLUS, PRO, METERS


@pytest.fixture()
def plan(monkeypatch):
    chosen = {"plan": FREE}

    def plan_for(user_key, strict=True):
        if chosen["plan"] is None:
            raise RuntimeError("subscription store down")
        return chosen["plan"]

    monkeypatch.setattr(quota.runtime(), "plan_for", plan_for)
    return chosen


def test_the_catalogue_gives_voice_to_plus_and_pro_only():
    assert "orena.voice" in METERS
    assert [p.entitlement_map()["orena.voice"].enabled for p in (FREE, PLUS, PRO)] == [False, True, True]


@pytest.mark.parametrize(("chosen", "entitled"), [(FREE, False), (PLUS, True), (PRO, True)])
def test_the_plan_decides(plan, chosen, entitled):
    plan["plan"] = chosen
    assert plan_features.entitled("u1", plan_features.VOICE) is entitled
    if entitled:
        plan_features.require("u1", plan_features.VOICE)
    else:
        with pytest.raises(HTTPException) as refused:
            plan_features.require("u1", plan_features.VOICE)
        detail = refused.value.detail
        assert refused.value.status_code == 403 and detail["category"] == "feature_not_in_plan"
        assert detail["retryable"] is False and detail["context"]["feature"] == "orena.voice"
        assert detail["context"]["plan"] == "free" and detail["context"]["upgrade"]


def test_a_plan_that_cannot_be_read_fails_closed(plan):
    plan["plan"] = None
    with pytest.raises(HTTPException) as refused:
        plan_features.require("u1", plan_features.VOICE)
    assert refused.value.status_code == 503 and refused.value.detail["category"] == "quota_unavailable"
    assert plan_features.entitled("u1", plan_features.VOICE) is False


def test_a_server_without_a_plan_system_lets_voice_through(monkeypatch):
    monkeypatch.setattr(quota.runtime(), "plan_for", None)
    assert plan_features.entitled("u1", plan_features.VOICE) is True
    plan_features.require("u1", plan_features.VOICE)


# --- the routes -------------------------------------------------------------------------------------------------


@pytest.fixture()
def api(plan, client):
    from tests.test_agent_api import _Voice, enable
    from writing_coach.agent import api as agent_api

    enable([])
    voice = _Voice()
    agent_api._runtime.voice = voice
    yield client, voice, plan
    agent_api.configure_agent(None)


@pytest.mark.parametrize("path", ["/api/agent/voice/session", "/api/agent/voice/extend"])
def test_free_is_refused_voice_before_any_token_and_paid_plans_are_not(api, path):
    client, voice, plan = api
    refused = client.post(path, json={"contract_version": 10})
    assert refused.status_code == 403 and refused.json()["detail"]["context"]["feature"] == "orena.voice"
    assert voice.calls == []
    plan["plan"] = PLUS
    assert client.post(path, json={"contract_version": 10}).status_code != 403


def test_the_voice_list_says_whether_the_plan_has_voice(api):
    client, _voice, plan = api
    assert client.get("/api/agent/voice/voices").json()["entitled"] is False
    plan["plan"] = PRO
    assert client.get("/api/agent/voice/voices").json()["entitled"] is True
