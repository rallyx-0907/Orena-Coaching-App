"""A cap on each learner's voice minutes with Orena (Hermes for the owner, 2026-10-19): one Pro learner talking all
day would otherwise use the whole system's $5 AI budget (COST_PRE402_403). The `orena.voice` limit is seconds per month
since D-248 (MV2-6a; it was per UTC day under D-237): Plus 6000 s (about 100 minutes), Pro 18000 s by the code's defaults
(an administrator edits it in the plan catalogue); the seconds are counted over the meter's window (#478). The minutes used are
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
from writing_coach.product.catalog import FREE, METERS, PLUS, PRO, Meter

NOW = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)
LIMIT = PLUS.entitlement_map()["orena.voice"].limit  # 6000 s by the code's defaults (D-248)


def configure(usage, clock=lambda: NOW):
    """Both readers (#478), so the meter's window - a day or a month - is counted whichever it is."""
    plan_features.configure(daily_usage=usage, monthly_usage=usage, clock=clock)


@pytest.fixture()
def voice_day(monkeypatch):
    state = {"plan": PLUS, "used": 0}
    monkeypatch.setattr(quota.runtime(), "plan_for", lambda user_key, strict=True: state["plan"])
    configure(lambda user_key, feature: state["used"] if feature == plan_features.VOICE_USAGE else 0)
    yield state
    configure(None)


def test_the_catalogue_gives_plus_100_and_pro_300_minutes_a_month():
    """D-248 (MV2-6a): a monthly window; Plus 6000 s, Pro 18000 s; Free stays off."""
    voice = [p.entitlement_map()["orena.voice"] for p in (FREE, PLUS, PRO)]
    assert [v.enabled for v in voice] == [False, True, True]
    assert [v.limit for v in voice[1:]] == [6000, 18000]
    assert all(v.window == "month" for v in voice)
    meter = voice[1].meter
    assert (meter.window, meter.unit, meter.display_unit, meter.scale) == ("month", "second", "minute", 60)


def test_under_the_cap_voice_opens_and_at_the_cap_this_learner_is_told(voice_day):
    voice_day["used"] = LIMIT - 1
    plan_features.require_voice_time("u1")
    voice_day["used"] = LIMIT
    with pytest.raises(HTTPException) as refused:
        plan_features.require_voice_time("u1")
    first = datetime(2026, 11, 1, tzinfo=UTC)
    assert refused.value.status_code == 429 and refused.value.headers["Retry-After"] == str(int((first - NOW).total_seconds()))
    detail = refused.value.detail
    assert detail["category"] == "quota_exhausted" and detail["retryable"] is False
    context = detail["context"]
    # The window is the catalogue's (month since D-248), never a fixed day.
    assert (context["feature"], context["used"], context["limit"], context["window"]) == ("orena.voice", LIMIT, LIMIT, "month")
    assert context["display_unit"] == "minute" and context["scale"] == 60 and context["resets_at"] == "2026-11-01T00:00:00Z"
    assert "upgrade" not in context  # no plans offer here (D-237)


def _refused_at_the_cap(voice_day):
    voice_day["used"] = LIMIT
    with pytest.raises(HTTPException) as refused:
        plan_features.require_voice_time("u1")
    return refused.value


def test_a_daily_voice_window_resets_at_the_next_utc_midnight(voice_day, monkeypatch):
    """The day case, exactly: a voice meter with window `day` resets at the next UTC midnight (15 h after NOW)."""
    monkeypatch.setitem(METERS, "orena.voice", Meter("orena.voice", "day", "second", "minute", scale=60))
    refused = _refused_at_the_cap(voice_day)
    assert refused.headers["Retry-After"] == str(15 * 3600)
    assert (refused.detail["context"]["window"], refused.detail["context"]["resets_at"]) == ("day", "2026-10-20T00:00:00Z")
    voice_day["used"] = 660
    assert plan_features.voice_allowance("u1")["resets_at"] == "2026-10-20T00:00:00Z"


def test_the_monthly_voice_window_resets_on_the_first_of_next_month(voice_day):
    """The month case, exactly: D-248's monthly meter resets at 00:00 UTC on the 1st of the next month."""
    refused = _refused_at_the_cap(voice_day)
    first = datetime(2026, 11, 1, tzinfo=UTC)
    assert refused.headers["Retry-After"] == str(int((first - NOW).total_seconds()))
    assert (refused.detail["context"]["window"], refused.detail["context"]["resets_at"]) == ("month", "2026-11-01T00:00:00Z")
    voice_day["used"] = 660
    assert plan_features.voice_allowance("u1")["resets_at"] == "2026-11-01T00:00:00Z"


def test_a_plan_without_voice_is_still_403_first(voice_day):
    voice_day["plan"] = FREE
    with pytest.raises(HTTPException) as refused:
        plan_features.require_voice_time("u1")
    assert refused.value.status_code == 403


def test_usage_that_cannot_be_read_fails_closed(voice_day, monkeypatch):
    def broken(user_key, feature):
        raise RuntimeError("store down")

    configure(broken)
    with pytest.raises(HTTPException) as refused:
        plan_features.require_voice_time("u1")
    assert refused.value.status_code == 503


def test_without_a_usage_store_the_minutes_are_not_capped(voice_day):
    configure(None)
    plan_features.require_voice_time("u1")  # a bare server: the plan rule still holds, minutes are not counted


@pytest.mark.parametrize("path", ["/api/agent/voice/session", "/api/agent/voice/extend"])
def test_both_voice_routes_refuse_at_the_cap_before_any_token(client, voice_day, path):  # noqa: F811
    from tests.test_agent_api import _Voice, enable
    from writing_coach.agent import api as agent_api

    enable([])
    voice = _Voice()
    agent_api._runtime.voice = voice
    voice_day["used"] = LIMIT
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
    assert plan_features.voice_seconds_left("u1") == LIMIT - 600


def test_every_token_is_clamped_to_the_minutes_left_and_unmetered_seconds_count_at_mint(voice_day):
    """Review of #325, P1-1: with messages not enforced a session is one token for the whole session - it must be
    clamped to what is left today and counted when it is minted, so a second session cannot pass the cap."""
    from tests.test_agent_voice_session import LEARNER, _body, _service

    recorded = []
    service = _service()
    service.runtime.meter = lambda user, feature, amount, request_id: recorded.append((feature, amount))
    voice_day["used"] = LIMIT - 240  # four minutes left

    answer = service.open(_body(), LEARNER)
    assert answer["max_seconds"] <= 240
    assert answer["last"] is True  # today's minutes end with this token: no renewal to be refused
    assert answer["day_limit_reached"] is True  # and the client may say so when this chunk ends
    assert recorded == [("agent.voice_seconds", answer["max_seconds"])]


def test_a_chunk_that_does_not_end_the_day_says_so(voice_day, monkeypatch):
    from tests.test_agent_voice_session import LEARNER, _body, _service

    service = _service()
    monkeypatch.setattr(plan_features, "voice_seconds_left", lambda user_key: 5000)  # more left than one token
    answer = service.open(_body(), LEARNER)
    assert answer["day_limit_reached"] is False


def test_a_token_that_uses_exactly_the_seconds_left_ends_the_day(voice_day, monkeypatch):
    """The boundary: left == the token's seconds - today's minutes end with this token."""
    from tests.test_agent_voice_session import LEARNER, _body, _service

    service = _service()
    monkeypatch.setattr(plan_features, "voice_seconds_left", lambda user_key: 900)  # the whole 900 s session token
    answer = service.open(_body(), LEARNER)
    assert answer["max_seconds"] == 900 and answer["day_limit_reached"] is True


# --- the voice energy bar (Monetisation v2): today's minutes, read before a session -------------------------------


def test_the_allowance_reports_todays_minutes_used_and_left(voice_day):
    voice_day["used"] = 660
    allowance = plan_features.voice_allowance("u1")
    assert allowance == {
        "feature": "orena.voice", "entitled": True, "limit": LIMIT, "used": 660, "left": LIMIT - 660, "unit": "second",
        "display_unit": "minute", "scale": 60, "window": "month", "resets_at": "2026-11-01T00:00:00Z", "plan": "plus"}


def test_the_allowance_never_reports_more_used_than_the_limit(voice_day):
    voice_day["used"] = LIMIT + 300  # a token minted past a lowered limit
    allowance = plan_features.voice_allowance("u1")
    assert (allowance["used"], allowance["left"]) == (LIMIT, 0)


def test_a_plan_without_voice_has_no_minutes_and_is_not_a_refusal(voice_day):
    voice_day["plan"] = FREE
    allowance = plan_features.voice_allowance("u1")
    assert (allowance["entitled"], allowance["limit"], allowance["left"]) == (False, 0, 0)


def test_uncapped_voice_says_so_with_no_numbers(voice_day):
    configure(None)
    allowance = plan_features.voice_allowance("u1")
    assert allowance["entitled"] is True and allowance["limit"] is None and allowance["left"] is None


def test_an_unreadable_allowance_fails_closed(voice_day):
    def broken(user_key, feature):
        raise RuntimeError("store down")

    configure(broken)
    with pytest.raises(HTTPException) as refused:
        plan_features.voice_allowance("u1")
    assert refused.value.status_code == 503


def test_the_allowance_route_reads_without_minting_or_charging(client, voice_day):  # noqa: F811
    from tests.test_agent_api import _Voice, enable
    from writing_coach.agent import api as agent_api

    enable([])
    voice = _Voice()
    agent_api._runtime.voice = voice
    voice_day["used"] = 300
    answer = client.get("/api/agent/voice/allowance")
    assert answer.status_code == 200 and answer.json()["left"] == LIMIT - 300
    assert answer.headers["Cache-Control"] == "no-store"
    assert voice.calls == []


def test_the_allowance_route_is_absent_without_voice(client, voice_day):  # noqa: F811
    from tests.test_agent_api import enable
    from writing_coach.agent import api as agent_api

    enable([])
    agent_api._runtime.voice = None
    assert client.get("/api/agent/voice/allowance").status_code == 404


# --- a monthly voice window (MV2-6a: about 100 minutes a month on Plus, 300 on Pro) --------------------------------


@pytest.fixture()
def voice_month(monkeypatch):
    """The meter moved to a month window, as the UI lane's catalogue change does; the limits are a month's seconds."""
    from dataclasses import replace

    from writing_coach.product.catalog import METERS, Entitlement, Meter

    monkeypatch.setitem(METERS, plan_features.VOICE, Meter("orena.voice", "month", "second", "minute", scale=60))
    plus = replace(PLUS, entitlements=tuple(
        Entitlement("orena.voice", enabled=True, limit=6000) if e.key == "orena.voice" else e for e in PLUS.entitlements))
    state = {"plan": plus, "day": 0, "month": 0}
    monkeypatch.setattr(quota.runtime(), "plan_for", lambda user_key, strict=True: state["plan"])
    monkeypatch.setattr(plan_features, "current_catalog", lambda strict=True: ({"plus": plus}, "r1"))
    plan_features.configure(daily_usage=lambda user_key, feature: state["day"],
                            monthly_usage=lambda user_key, feature: state["month"], clock=lambda: NOW)  # fmt: skip
    yield state
    plan_features.configure(daily_usage=None)


def test_a_monthly_window_counts_the_month_and_resets_on_the_first(voice_month):
    voice_month["day"], voice_month["month"] = 60, 5400  # one minute today, ninety this month
    allowance = plan_features.voice_allowance("u1")
    assert (allowance["window"], allowance["limit"], allowance["used"], allowance["left"]) == ("month", 6000, 5400, 600)
    assert allowance["resets_at"] == "2026-11-01T00:00:00Z"
    assert plan_features.voice_seconds_left("u1") == 600


def test_at_the_monthly_cap_the_refusal_says_the_month(voice_month):
    voice_month["month"] = 6000
    with pytest.raises(HTTPException) as refused:
        plan_features.require_voice_time("u1")
    context = refused.value.detail["context"]
    assert (context["window"], context["used"], context["resets_at"]) == ("month", 6000, "2026-11-01T00:00:00Z")


def test_a_monthly_window_without_a_monthly_reader_is_not_counted_as_a_day(voice_month):
    plan_features.configure(daily_usage=lambda user_key, feature: 6000, monthly_usage=None, clock=lambda: NOW)
    assert plan_features.voice_seconds_left("u1") is None  # never a day's total read as the month's


def test_december_resets_in_january():
    assert plan_features._period_end(datetime(2026, 12, 31, 23, 0, tzinfo=UTC), "month") == datetime(2027, 1, 1,
                                                                                                       tzinfo=UTC)
    assert plan_features._period_end(datetime(2026, 10, 19, 9, 0, tzinfo=UTC), "day") == datetime(2026, 10, 20,
                                                                                                   tzinfo=UTC)
