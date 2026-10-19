"""A daily cap on each learner's voice minutes with Orena (Hermes for the owner, 2026-10-19): one Pro learner talking all
day would otherwise use the whole system's $5 AI budget (COST_PRE402_403). The `orena.voice` limit is seconds per UTC day,
15 minutes for Plus and Pro by the code's defaults (an administrator edits it in the plan catalogue). The minutes used are
the voice seconds the server already records per learner (`agent.voice_seconds` usage events), so the cap holds whether
or not usage limits are enforced. At the cap: 429 `quota_exhausted` with `feature: "orena.voice"` - this learner only;
nothing locks the system. Every token minted is clamped to the seconds left today, and its seconds are counted when it
is minted, metered or not, so an open session is seen by the next check."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from tests.test_agent_api import client  # noqa: F401 - the agent router's test client fixture
from writing_coach.product import plan_features, quota
from writing_coach.product.catalog import FREE, PLUS, PRO

NOW = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)


@pytest.fixture()
def voice_day(monkeypatch):
    state = {"plan": PLUS, "used": 0}
    monkeypatch.setattr(quota.runtime(), "plan_for", lambda user_key, strict=True: state["plan"])
    plan_features.configure(daily_usage=lambda user_key, feature: state["used"] if feature == plan_features.VOICE_USAGE
                            else 0, clock=lambda: NOW)  # fmt: skip
    yield state
    plan_features.configure(daily_usage=None)


def test_the_catalogue_gives_plus_and_pro_fifteen_minutes_a_day():
    voice = [p.entitlement_map()["orena.voice"] for p in (FREE, PLUS, PRO)]
    assert [v.enabled for v in voice] == [False, True, True]
    assert [v.limit for v in voice[1:]] == [900, 900] and voice[1].window == "day"


def test_under_the_cap_voice_opens_and_at_the_cap_this_learner_is_told(voice_day):
    voice_day["used"] = 899
    plan_features.require_voice_time("u1")
    voice_day["used"] = 900
    with pytest.raises(HTTPException) as refused:
        plan_features.require_voice_time("u1")
    assert refused.value.status_code == 429 and refused.value.headers["Retry-After"] == str(15 * 3600)
    detail = refused.value.detail
    assert detail["category"] == "quota_exhausted" and detail["retryable"] is False
    context = detail["context"]
    assert (context["feature"], context["used"], context["limit"], context["window"]) == ("orena.voice", 900, 900, "day")
    assert context["display_unit"] == "minute" and context["scale"] == 60 and context["resets_at"] == "2026-10-20T00:00:00Z"
    assert "upgrade" not in context  # Plus and Pro have the same minutes: no plans offer here


def test_a_plan_without_voice_is_still_403_first(voice_day):
    voice_day["plan"] = FREE
    with pytest.raises(HTTPException) as refused:
        plan_features.require_voice_time("u1")
    assert refused.value.status_code == 403


def test_usage_that_cannot_be_read_fails_closed(voice_day, monkeypatch):
    def broken(user_key, feature):
        raise RuntimeError("store down")

    plan_features.configure(daily_usage=broken, clock=lambda: NOW)
    with pytest.raises(HTTPException) as refused:
        plan_features.require_voice_time("u1")
    assert refused.value.status_code == 503


def test_without_a_usage_store_the_minutes_are_not_capped(voice_day):
    plan_features.configure(daily_usage=None)
    plan_features.require_voice_time("u1")  # a bare server: the plan rule still holds, minutes are not counted


@pytest.mark.parametrize("path", ["/api/agent/voice/session", "/api/agent/voice/extend"])
def test_both_voice_routes_refuse_at_the_cap_before_any_token(client, voice_day, path):  # noqa: F811
    from tests.test_agent_api import _Voice, enable
    from writing_coach.agent import api as agent_api

    enable([])
    voice = _Voice()
    agent_api._runtime.voice = voice
    voice_day["used"] = 900
    refused = client.post(path, json={"contract_version": 10})
    assert refused.status_code == 429 and refused.json()["detail"]["context"]["feature"] == "orena.voice"
    assert voice.calls == []


def test_a_placeholder_limit_saved_under_d236_reads_as_the_default(voice_day, monkeypatch):
    """Review of #325, P1-2: an editor that saved `orena.voice` as on/off stored limit 1 - never one second a day."""
    from dataclasses import replace

    from writing_coach.product.catalog import Entitlement

    stored = replace(PLUS, entitlements=tuple(
        Entitlement("orena.voice", enabled=True, limit=1) if e.key == "orena.voice" else e for e in PLUS.entitlements))
    voice_day["plan"] = stored
    monkeypatch.setattr(plan_features, "current_catalog", lambda strict=True: ({"plus": stored}, "r1"))
    voice_day["used"] = 600
    plan_features.require_voice_time("u1")
    assert plan_features.voice_seconds_left("u1") == 300


def test_every_token_is_clamped_to_the_minutes_left_and_unmetered_seconds_count_at_mint(voice_day):
    """Review of #325, P1-1: with messages not enforced a session is one token for the whole session - it must be
    clamped to what is left today and counted when it is minted, so a second session cannot pass the cap."""
    from tests.test_agent_voice_session import LEARNER, _body, _service

    recorded = []
    service = _service()
    service.runtime.meter = lambda user, feature, amount, request_id: recorded.append((feature, amount))
    voice_day["used"] = 900 - 240  # four minutes left today

    answer = service.open(_body(), LEARNER)
    assert answer["max_seconds"] <= 240
    assert recorded == [("agent.voice_seconds", answer["max_seconds"])]
