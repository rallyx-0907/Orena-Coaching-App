"""D-16T live voice charged by duration against `orena.message`, hermetic (CI, SQLite).

The quota store is the in-memory TEST DOUBLE of `tests/test_quota_gate.py` and the vendor is a fake token minter
(`Post`), so "no token was minted" is asserted, not inferred: the session route, the real `VoiceService` and the real
quota gate run end to end. The same behaviour against real PostgreSQL is proved in `tests/test_quota_voice_postgres.py`.
"""
from __future__ import annotations

import concurrent.futures
import dataclasses
import threading
from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip("fastapi")

from test_agent_voice_session import Clock, Post, _body, _service  # noqa: E402
from test_quota_gate import MemorySettings, enforced_runtime  # noqa: E402
from test_quota_orena_message import Rig, _isolated, spend, totals  # noqa: E402,F401  (fixture)

from writing_coach.agent.voice_session import SESSION_SECONDS  # noqa: E402
from writing_coach.ai.live_voice import GeminiLiveTokens  # noqa: E402
from writing_coach.core.request_context import USER_KEY_CTX  # noqa: E402
from writing_coach.product import catalog, quota  # noqa: E402
from writing_coach.product.catalog import FREE, PLUS, PRO, configure_plan_store  # noqa: E402

ENV = {quota.FLAG: "on", quota.METERS_FLAG: "orena.message"}
NOW = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)
URL = "/api/agent/voice/session"


def session_body(**extra):
    return {**_body(target="en"), **extra}


class Voice:
    """The real route and service, a fake vendor and a controlled clock."""

    def __init__(self, post=None, *, billed=None):
        self.clock = Clock()
        self.post = post or Post()
        self.billed = billed if billed is not None else []
        self.service = _service(self.post, clock=self.clock, billed=self.billed)
        self.service.now = lambda: NOW
        self.rig = Rig([], voice=self.service)

    def open(self, *, key=None, user="learner-1", **extra):
        headers = {"x-test-user": user, **({"Idempotency-Key": key} if key else {})}
        return self.rig.client.post(URL, json=session_body(**extra), headers=headers)

    def end(self, answer, *, user="learner-1"):
        return self.rig.client.post("/api/agent/voice/end", json={"voice_session_id": answer.json()["voice_session_id"]},
                                    headers={"x-test-user": user})

    @property
    def minted(self):
        return len(self.post.calls)

    def token_life(self, index=-1):
        sent = self.post.calls[index][2]
        expires = datetime.strptime(sent["expireTime"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        return int((expires - NOW).total_seconds())


def catalogue_with(**free_voice):
    """The default catalogue with a Free-plan voice conversion (and optionally a Free message limit)."""
    plans = [plan.as_dict() for plan in (FREE, PLUS, PRO)]
    for row in plans:
        for key in ("name", "description", "price_label", "rank"):
            row.pop(key)
        if row["id"] == "free":
            row["entitlements"] = [
                {"key": "orena.message", "enabled": True, "limit": free_voice.get("limit", 20),
                 "params": {"voice_seconds_per_message": free_voice["seconds"]}},
            ]
    configure_plan_store(MemorySettings({catalog.PLAN_SETTING_KEY: {
        "value": {"version": 2, "plans": plans}, "updated_at": "2026-10-09T10:00:00+00:00", "updated_by": "admin"}}))


# ----------------------------------------------------------------------------------------------- admission --

def test_a_spent_day_is_a_429_and_no_token_is_minted():
    repository = enforced_runtime(env=ENV)
    spend(20)
    voice = Voice()
    answer = voice.open()
    assert answer.status_code == 429
    detail = answer.json()["detail"]
    assert detail["category"] == "quota_exhausted" and detail["retryable"] is False
    assert detail["context"]["feature"] == "orena.message" and detail["context"]["used"] == detail["context"]["limit"] == 20
    assert detail["context"]["resets_at"] and int(answer.headers["Retry-After"]) >= 1
    assert voice.minted == 0, "the vendor was never asked for a token"
    assert totals(repository) == (20, 0), "nothing was reserved"
    assert voice.service.sessions._sessions == {}


def test_the_session_reserves_what_it_may_use_and_the_token_lives_that_long():
    repository = enforced_runtime(env=ENV)
    voice = Voice()
    answer = voice.open()
    assert answer.status_code == 200
    body = answer.json()
    assert body["max_seconds"] == SESSION_SECONDS == 900, "a whole day left: the session cap itself"
    assert voice.token_life() == 900
    assert totals(repository) == (0, 15), "900 s at 60 s a message: 15 messages held"
    assert [c for c in repository.calls if c == "dispatch"] == ["dispatch"], "dispatched right before the mint"


def test_the_cap_is_what_the_remaining_messages_buy():
    repository = enforced_runtime(env=ENV)
    spend(18)  # Free: 20 a day, 2 left
    voice = Voice()
    body = voice.open().json()
    assert body["max_seconds"] == 120 and voice.token_life() == 120
    assert totals(repository) == (18, 2)
    # one message left: sixty seconds
    other = Voice()
    spend(1, user="learner-2")
    spend(18, user="learner-2")
    one_left = other.open(user="learner-2").json()
    assert one_left["max_seconds"] == 60 and other.token_life() == 60


def test_an_admin_changed_conversion_is_honoured():
    repository = enforced_runtime(env=ENV)
    catalogue_with(seconds=30)  # one message per 30 s: 900 s would be 30 messages, the day has 20
    voice = Voice()
    body = voice.open().json()
    assert body["max_seconds"] == 600 and voice.token_life() == 600, "20 messages x 30 s"
    assert totals(repository) == (0, 20)

    configure_plan_store(None)
    catalogue_with(seconds=3600)  # a message is an hour: one message already buys the whole cap
    again = Voice()
    assert again.open(user="learner-9").json()["max_seconds"] == 900
    assert totals(repository) == (0, 21)


# --------------------------------------------------------------------------------------------- settlement --

def test_ending_settles_the_seconds_it_lasted_and_releases_the_rest():
    repository = enforced_runtime(env=ENV)
    voice = Voice()
    answer = voice.open()
    voice.clock.t += 61  # a started second message counts as whole
    ended = voice.end(answer)
    assert ended.status_code == 200 and ended.json()["seconds"] == 61.0
    assert totals(repository) == (2, 0), "2 messages charged, the other 13 are free again"
    assert "settle:2" in repository.calls
    assert voice.billed[0][1]["audio_seconds"] == 61.0, "the vendor ledger gets the wall-clock seconds"


def test_a_short_session_costs_one_message_and_exact_minutes_cost_exactly_that():
    repository = enforced_runtime(env=ENV)
    voice = Voice()
    first = voice.open()
    voice.clock.t += 5
    voice.end(first)
    assert totals(repository) == (1, 0)
    second = voice.open()
    voice.clock.t += 180
    voice.end(second)
    assert totals(repository) == (4, 0), "180 s is 3 messages, not 4"


def test_a_session_that_runs_to_its_cap_is_charged_the_cap_never_more():
    repository = enforced_runtime(env=ENV)
    spend(17)  # 3 left: 180 s
    voice = Voice()
    answer = voice.open()
    assert answer.json()["max_seconds"] == 180
    voice.clock.t += 5000  # the learner's client never ended it on time
    ended = voice.end(answer)
    assert ended.json()["seconds"] == 180.0
    assert totals(repository) == (20, 0)


def test_ending_twice_charges_once():
    repository = enforced_runtime(env=ENV)
    voice = Voice()
    answer = voice.open()
    voice.clock.t += 30
    assert voice.end(answer).status_code == 200
    assert voice.end(answer).status_code == 404, "the session is over"
    assert totals(repository) == (1, 0)
    assert [c for c in repository.calls if c.startswith("settle")] == ["settle:1"]


def test_a_session_nobody_ended_is_settled_at_its_reservation_when_the_process_next_sweeps():
    repository = enforced_runtime(env=ENV)
    spend(10)  # 10 left: a 600 s session
    voice = Voice()
    lost = voice.open()
    assert lost.status_code == 200 and lost.json()["max_seconds"] == 600
    assert totals(repository) == (10, 10), "10 reserved: the day is full"
    voice.clock.t += 600 + 1  # the token is dead; the client vanished without ending it
    other = voice.open(user="learner-2")  # the worker's next open sweeps the expired session
    assert other.status_code == 200
    assert lost.json()["voice_session_id"] not in voice.service.sessions._sessions
    assert totals(repository) == (20, 15), "learner-1: 10 + the 10 reserved, settled; learner-2: 15 reserved"
    assert voice.billed[0][1]["audio_seconds"] == 600.0, "the ledger gets the token's life, never more"


def test_the_reconciler_is_the_backstop_when_the_process_is_gone():
    repository = enforced_runtime(env=ENV)
    voice = Voice()
    voice.open()  # 15 reserved and dispatched; then the process dies: nobody ever settles it
    assert totals(repository) == (0, 15)
    done = quota.reconcile_once(repository, now=datetime.now(UTC) + timedelta(minutes=16))
    assert done == {"settled": 1, "released": 0}
    assert totals(repository) == (15, 0), "settled at the reserved amount (ABANDONED_SETTLES)"


def test_a_vendor_that_refuses_the_token_costs_the_learner_nothing():
    repository = enforced_runtime(env=ENV)
    voice = Voice(Post(status=500))
    answer = voice.open()
    assert answer.status_code == 503 and answer.json()["detail"] == "voice_unavailable"
    assert totals(repository) == (0, 0), "settled 0: the reservation is not kept"
    assert "settle:0" in repository.calls


def test_a_missing_key_costs_the_learner_nothing_either():
    repository = enforced_runtime(env=ENV)
    voice = Voice()
    voice.service.tokens = GeminiLiveTokens(key=lambda: "", post=voice.post)
    assert voice.open().status_code == 503
    assert totals(repository) == (0, 0)


# -------------------------------------------------------------------------------------------- concurrency --

def test_concurrent_sessions_cannot_spend_more_than_the_allowance():
    repository = enforced_runtime(env=ENV)
    voice = Voice()
    barrier = threading.Barrier(6)

    def one(_n):
        barrier.wait(timeout=10)
        return voice.open()

    with concurrent.futures.ThreadPoolExecutor(6) as pool:
        answers = list(pool.map(one, range(6)))
    granted = [a for a in answers if a.status_code == 200]
    refused = [a for a in answers if a.status_code == 429]
    assert len(granted) + len(refused) == 6, [a.status_code for a in answers]
    seconds = sorted(a.json()["max_seconds"] for a in granted)
    assert sum(seconds) <= 20 * 60, "the day's 20 messages are never exceeded"
    assert seconds == [300, 900], "one session got its 15 messages, the next what was left (5)"
    assert voice.minted == 2, "tokens exist only for what was admitted"
    assert totals(repository) == (0, 20)


def test_the_same_key_sent_twice_is_one_session_and_one_reservation():
    repository = enforced_runtime(env=ENV)
    voice = Voice()
    first = voice.open(key="open-1")
    again = voice.open(key="open-1")
    assert first.status_code == 200
    assert again.status_code == 409 and again.json()["detail"]["category"] == "operation_in_progress"
    assert voice.minted == 1 and totals(repository) == (0, 15)
    voice.clock.t += 10
    voice.end(first)
    done = voice.open(key="open-1")
    assert done.status_code == 409 and done.json()["detail"]["category"] == "operation_finished"
    assert voice.minted == 1 and totals(repository) == (1, 0)


# -------------------------------------------------------------------------------------------- fail closed --

def test_an_unreadable_store_answers_503_and_mints_nothing():
    quota.configure_quota(env=ENV, reason="no_store")  # enforcement on, no quota store
    voice = Voice()
    answer = voice.open()
    assert answer.status_code == 503 and answer.json()["detail"]["category"] == "quota_unavailable"
    assert voice.minted == 0


def test_an_unreadable_switch_answers_503_and_mints_nothing():
    quota.configure_quota(settings=MemorySettings(fail=True), env={}, reason="no_postgresql")
    voice = Voice()
    answer = voice.open()
    assert answer.status_code == 503 and answer.json()["detail"]["category"] == "quota_unavailable"
    assert voice.minted == 0


def test_an_unreadable_catalogue_answers_503_and_mints_nothing():
    enforced_runtime(env=ENV)
    configure_plan_store(MemorySettings(fail=True))
    voice = Voice()
    answer = voice.open()
    assert answer.status_code == 503 and answer.json()["detail"]["category"] == "quota_unavailable"
    assert voice.minted == 0


# ------------------------------------------------------------------------------------------- switched off --

def test_voice_is_unchanged_when_messages_are_not_enforced():
    repository = enforced_runtime(env={quota.FLAG: "off"})
    voice = Voice()
    answer = voice.open()
    assert answer.status_code == 200 and answer.json()["max_seconds"] == 900 and voice.token_life() == 900
    voice.clock.t += 61
    assert voice.end(answer).json()["seconds"] == 61.0
    assert repository.calls == [] and repository.buckets == {}, "no read and no bucket: exactly the old path"
    assert voice.billed[0][1]["audio_seconds"] == 61.0


def test_a_meter_that_is_not_listed_is_not_charged():
    repository = enforced_runtime(env={quota.FLAG: "on", quota.METERS_FLAG: "writing.review"})
    voice = Voice()
    assert voice.open().json()["max_seconds"] == 900
    assert repository.calls == []


def test_the_other_voice_routes_are_unchanged_by_the_quota():
    repository = enforced_runtime(env=ENV)
    voice = Voice()
    answer = voice.open()
    sid = answer.json()["voice_session_id"]
    calls_before = list(repository.calls)
    tool = voice.rig.client.post("/api/agent/voice/tool", json={"voice_session_id": sid, "utterance": "u1", "calls": []},
                                 headers={"x-test-user": "learner-1"})
    turn = voice.rig.client.post("/api/agent/voice/turn", json={"voice_session_id": sid, "utterance": "u1"},
                                 headers={"x-test-user": "learner-1", "Idempotency-Key": "ignored"})
    assert tool.status_code == 200 and turn.status_code == 200
    assert repository.calls == calls_before, "no quota read on the other routes"


# ----------------------------------------------------------------------------------------------- the unit --

def test_units_for_rounds_up_and_never_exceeds_the_reservation():
    enforced_runtime(env=ENV)
    reset = USER_KEY_CTX.set("learner-1")
    try:
        ticket = quota.begin_voice("orena.message", max_seconds=900, request_digest="unit")
    finally:
        USER_KEY_CTX.reset(reset)
    assert (ticket.units, ticket.max_seconds, ticket.seconds_per_unit) == (15, 900, 60)
    assert [ticket.units_for(s) for s in (0, -3, 0.2, 60, 60.1, 119, 121, 900, 5000)] == [0, 0, 1, 1, 2, 2, 3, 15, 15]
    assert quota.NULL_TICKET.units_for(100) == 0 and quota.NULL_TICKET.max_seconds is None


def test_a_zero_second_session_is_not_a_thing():
    enforced_runtime(env=ENV)
    with pytest.raises(ValueError):
        quota.begin_voice("orena.message", max_seconds=0)


def test_a_conversion_that_is_not_a_positive_whole_number_is_unavailable_not_free():
    from fastapi import HTTPException

    entitlement = catalog.plan_by_id("free").entitlement_map()["orena.message"]
    for broken in (0, -5, True, "60", None):
        with pytest.raises(HTTPException) as refused:
            quota.seconds_per_unit(dataclasses.replace(entitlement, params={"voice_seconds_per_message": broken}))
        assert refused.value.status_code == 503
    assert quota.seconds_per_unit(entitlement) == 60
