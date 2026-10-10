"""D-16T live voice charged by duration against `orena.message`, hermetic (CI, SQLite).

A voice session is a chain of short vendor tokens (chunks). Each chunk is admitted before its token exists, charged whole
when it is minted, and a learner who ends early gets nothing back, because the server cannot see the vendor socket.

The quota store is the in-memory TEST DOUBLE of `tests/test_quota_gate.py` and the vendor is a fake token minter (`Post`),
so "no token was minted" is asserted, not inferred: the session route, the real `VoiceService` and the real quota gate
run end to end. The same behaviour against real PostgreSQL is proved in `tests/test_quota_voice_postgres.py`.
"""
from __future__ import annotations

import concurrent.futures
import dataclasses
import threading
from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip("fastapi")

from test_agent_voice_session import Clock, Post, _body, _service  # noqa: E402
from test_quota_gate import FakeQuotaRepository, MemorySettings, enforced_runtime  # noqa: E402
from test_quota_orena_message import Rig, _isolated, spend, totals  # noqa: E402,F401  (fixture)

from writing_coach.agent.voice_session import (  # noqa: E402
    RENEW_LEAD_SECONDS,
    SESSION_SECONDS,
    VOICE_CHUNK_UNITS,
    VOICE_MIN_CHUNK_SECONDS,
)
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
    """The real routes and service, a fake vendor and a controlled clock."""

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

    def extend(self, answer, chunk, *, resumption=None, user="learner-1"):
        body = {"voice_session_id": answer.json()["voice_session_id"], "chunk": chunk}
        if resumption is not None:
            body["resumption"] = resumption
        return self.rig.client.post("/api/agent/voice/extend", json=body, headers={"x-test-user": user})

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

    def setup_sent(self, index=-1):
        return self.post.calls[index][2]["bidiGenerateContentSetup"]


def catalogue_with(*, seconds, limit=20):
    """The default catalogue with a Free-plan voice conversion (and message limit)."""
    plans = [plan.as_dict() for plan in (FREE, PLUS, PRO)]
    for row in plans:
        for key in ("name", "description", "price_label", "rank"):
            row.pop(key)
        if row["id"] == "free":
            row["entitlements"] = [{"key": "orena.message", "enabled": True, "limit": limit,
                                    "params": {"voice_seconds_per_message": seconds}}]
    configure_plan_store(MemorySettings({catalog.PLAN_SETTING_KEY: {
        "value": {"version": 2, "plans": plans}, "updated_at": "2026-10-09T10:00:00+00:00", "updated_by": "admin"}}))


def test_the_chunk_constants_are_what_the_decision_says():
    assert (VOICE_CHUNK_UNITS, VOICE_MIN_CHUNK_SECONDS, SESSION_SECONDS, RENEW_LEAD_SECONDS) == (2, 60, 900, 12)


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


def test_the_first_chunk_is_reserved_dispatched_minted_and_settled_whole():
    repository = enforced_runtime(env=ENV)
    voice = Voice()
    answer = voice.open()
    assert answer.status_code == 200
    body = answer.json()
    assert body["max_seconds"] == 120 == voice.token_life(), "two messages of voice: the token lives that long"
    assert (body["chunk"], body["session_max_seconds"], body["last"]) == (0, 900, False)
    assert body["renew_in"] == 120 - RENEW_LEAD_SECONDS
    assert body["connect"]["expires_at"].endswith("Z")
    assert totals(repository) == (2, 0), "charged whole when the token exists; nothing stays reserved"
    order = [c for c in repository.calls if c in ("reserve", "dispatch", "settle:2")]
    assert order == ["reserve", "dispatch", "settle:2"], "dispatched immediately before the mint, settled at once after"


def test_the_chunk_is_what_the_remaining_messages_buy():
    repository = enforced_runtime(env=ENV)
    spend(19)  # Free: 20 a day, 1 left
    voice = Voice()
    body = voice.open().json()
    assert body["max_seconds"] == 60 and voice.token_life() == 60
    assert totals(repository) == (20, 0)
    assert voice.open().status_code == 429, "and then the day is spent"
    assert voice.minted == 1


def test_an_admin_changed_conversion_is_honoured_with_a_floor_of_a_minute_and_a_ceiling_of_the_session():
    repository = enforced_runtime(env=ENV)
    catalogue_with(seconds=30)  # two messages of voice are 60 s
    assert Voice().open().json()["max_seconds"] == 60
    assert totals(repository) == (2, 0)

    configure_plan_store(None)
    catalogue_with(seconds=10)  # 20 s would be too short for a token: the floor is a minute, which is six messages
    voice = Voice()
    assert voice.open(user="learner-8").json()["max_seconds"] == 60
    assert totals(repository) == (2 + 6, 0)

    configure_plan_store(None)
    catalogue_with(seconds=3600)  # a message is an hour: one message already buys the whole session
    again = Voice()
    body = again.open(user="learner-9").json()
    assert body["max_seconds"] == 900 and body["last"] is True and body["renew_in"] is None
    assert totals(repository) == (2 + 6 + 1, 0)


def test_the_unlimited_branch_gives_a_whole_chunk(monkeypatch):
    enforced_runtime(env=ENV)
    original = quota._entitlement
    monkeypatch.setattr(quota, "_entitlement", lambda plan, meter: dataclasses.replace(original(plan, meter), limit=None))
    assert Voice().open().json()["max_seconds"] == 120


# ----------------------------------------------------------------------------------------------- the chain --

def test_a_renewal_mints_the_next_chunk_charges_it_and_carries_the_conversation_on():
    repository = enforced_runtime(env=ENV)
    voice = Voice()
    opened = voice.open()
    voice.clock.t += 100
    renewed = voice.extend(opened, 1, resumption="h-abc_123")
    assert renewed.status_code == 200
    body = renewed.json()
    assert (body["chunk"], body["max_seconds"], body["last"]) == (1, 120, False)
    assert body["voice_session_id"] == opened.json()["voice_session_id"]
    assert body["connect"]["ephemeral_token"] and body["connect"]["setup"] == {"setup": {"model": "models/gemini-3.8-live"}}
    assert totals(repository) == (4, 0), "the second chunk was charged when it was minted"
    assert voice.setup_sent(0)["sessionResumption"] == {}, "the first token asks the vendor for resumption handles"
    assert voice.setup_sent(1)["sessionResumption"] == {"handle": "h-abc_123"}, "the handle is locked into the new token"
    assert voice.setup_sent(1)["systemInstruction"] == voice.setup_sent(0)["systemInstruction"]
    assert [call[2]["bidiGenerateContentSetup"]["model"] for call in voice.post.calls] == ["models/gemini-3.8-live"] * 2


def test_a_handle_that_is_not_a_handle_is_not_put_into_the_setup():
    enforced_runtime(env=ENV)
    voice = Voice()
    opened = voice.open()
    for index, junk in enumerate(['x" , "model": "y', "a b", "", "é" * 5, "h" * 3000], start=1):
        assert voice.extend(opened, index, resumption=junk).status_code == 200
        assert voice.setup_sent()["sessionResumption"] == {}, f"{junk[:20]!r} must not reach the locked setup"


def test_a_repeated_renewal_returns_the_same_token_and_charges_nothing():
    repository = enforced_runtime(env=ENV)
    voice = Voice()
    opened = voice.open()
    first = voice.extend(opened, 1)
    again = voice.extend(opened, 1)
    assert first.status_code == again.status_code == 200 and first.json() == again.json()
    assert voice.minted == 2 and totals(repository) == (4, 0)


def test_a_chunk_out_of_order_is_a_409_and_charges_nothing():
    repository = enforced_runtime(env=ENV)
    voice = Voice()
    opened = voice.open()
    for wrong in (0, 2, 5, -1, "1", None):
        refused = voice.extend(opened, wrong)
        assert refused.status_code == 409 and refused.json()["detail"]["category"] == "voice_chunk_mismatch", wrong
    assert voice.minted == 1 and totals(repository) == (2, 0)


def test_no_message_left_refuses_the_renewal_with_the_limit_and_keeps_the_session():
    repository = enforced_runtime(env=ENV)
    spend(17)
    voice = Voice()
    opened = voice.open()  # 2 of the 3 left
    assert opened.json()["max_seconds"] == 120
    assert voice.extend(opened, 1).json()["max_seconds"] == 60, "the last message: a shorter chunk"
    refused = voice.extend(opened, 2)
    assert refused.status_code == 429 and refused.json()["detail"]["category"] == "quota_exhausted"
    assert voice.minted == 2 and totals(repository) == (20, 0)
    # a failed attempt does not use the index up
    assert voice.extend(opened, 2).status_code == 429


def test_the_session_is_at_most_fifteen_minutes_in_all_its_chunks():
    repository = enforced_runtime(env=ENV)
    voice = Voice()
    opened = voice.open()
    lives = [opened.json()["max_seconds"]]
    index = 1
    while True:
        answer = voice.extend(opened, index)
        if answer.status_code != 200:
            break
        lives.append(answer.json()["max_seconds"])
        if answer.json()["last"]:
            index += 1
            break
        index += 1
    assert lives == [120] * 7 + [60], "seven chunks of two minutes, then the last 60 s of the 900"
    assert sum(lives) == 900
    over = voice.extend(opened, index)
    assert over.status_code == 409 and over.json()["detail"]["category"] == "voice_session_over"
    assert totals(repository) == (15, 0)


def test_a_failed_mint_on_a_renewal_charges_nothing_and_may_be_asked_again():
    repository = enforced_runtime(env=ENV)
    voice = Voice()
    opened = voice.open()
    voice.post.status = 500
    refused = voice.extend(opened, 1)
    assert refused.status_code == 503 and refused.json()["detail"] == "voice_unavailable"
    assert totals(repository) == (2, 0)
    voice.post.status = 200
    assert voice.extend(opened, 1).status_code == 200
    assert totals(repository) == (4, 0)


def test_a_session_nobody_renews_just_ends_when_its_token_does():
    repository = enforced_runtime(env=ENV)
    voice = Voice()
    opened = voice.open()
    sid = opened.json()["voice_session_id"]
    voice.clock.t += 121  # the token is dead
    tool = voice.rig.client.post("/api/agent/voice/tool", json={"voice_session_id": sid, "utterance": "u1", "calls": []},
                                 headers={"x-test-user": "learner-1"})
    assert tool.status_code == 404, "its tools are gone with its token"
    assert voice.extend(opened, 1).status_code == 404
    voice.open(user="learner-2")  # the next open sweeps it; nothing is owed and nothing is refunded
    assert sid not in voice.service.sessions._sessions
    assert totals(repository) == (4, 0)


def test_a_renewal_keeps_the_tools_alive_past_the_first_token():
    enforced_runtime(env=ENV)
    voice = Voice()
    opened = voice.open()
    sid = opened.json()["voice_session_id"]
    voice.clock.t += 108
    assert voice.extend(opened, 1).status_code == 200
    voice.clock.t += 100  # 208 s: past the first token (120 s), inside the second (108 + 120)
    tool = voice.rig.client.post("/api/agent/voice/tool", json={"voice_session_id": sid, "utterance": "u1", "calls": []},
                                 headers={"x-test-user": "learner-1"})
    assert tool.status_code == 200


# ------------------------------------------------------------------------------------------- ending early --

def test_ending_at_once_still_costs_the_chunk_and_refunds_nothing():
    repository = enforced_runtime(env=ENV)
    voice = Voice()
    opened = voice.open()
    ended = voice.end(opened)  # no time passed at all
    assert ended.status_code == 200 and ended.json()["seconds"] == 0.0
    assert totals(repository) == (2, 0), "a session costs at least the message its token was minted for"
    assert voice.extend(opened, 1).status_code == 404, "ending stops further chunks"
    assert voice.minted == 1


def test_open_end_over_and_over_cannot_hold_more_vendor_time_than_the_day_pays_for():
    """The review's probe: ending a session early and opening another used to put 9,900 s of Live time on 12 messages."""
    repository = enforced_runtime(env=ENV)
    voice = Voice()
    lives = []
    for _round in range(40):
        answer = voice.open()
        if answer.status_code != 200:
            assert answer.status_code == 429
            break
        lives.append(answer.json()["max_seconds"])
        voice.clock.t += 1
        voice.end(answer)
    assert sum(lives) == 20 * 60, "every second of token life was paid for in messages: 20 messages x 60 s"
    assert totals(repository) == (20, 0)


def test_ending_twice_charges_nothing_more():
    repository = enforced_runtime(env=ENV)
    voice = Voice()
    opened = voice.open()
    voice.clock.t += 30
    assert voice.end(opened).status_code == 200
    assert voice.end(opened).status_code == 404
    assert totals(repository) == (2, 0)
    assert [c for c in repository.calls if c.startswith("settle")] == ["settle:2"]


def test_the_vendor_ledger_gets_each_chunk_at_the_seconds_its_token_lives():
    enforced_runtime(env=ENV)
    voice = Voice()
    opened = voice.open()
    voice.extend(opened, 1)
    voice.clock.t += 5
    voice.end(opened)
    assert [kwargs["audio_seconds"] for _args, kwargs in voice.billed] == [120.0, 120.0], "an early end changes nothing"
    assert all(args == ("agent_voice",) for args, _kwargs in voice.billed)


def test_a_vendor_that_refuses_the_token_costs_the_learner_nothing():
    repository = enforced_runtime(env=ENV)
    voice = Voice(Post(status=500))
    answer = voice.open()
    assert answer.status_code == 503 and answer.json()["detail"] == "voice_unavailable"
    assert totals(repository) == (0, 0), "settled 0: nothing is kept"
    assert "settle:0" in repository.calls
    assert voice.billed == []


def test_a_missing_key_costs_the_learner_nothing_either():
    repository = enforced_runtime(env=ENV)
    voice = Voice()
    voice.service.tokens = GeminiLiveTokens(key=lambda: "", post=voice.post)
    assert voice.open().status_code == 503
    assert totals(repository) == (0, 0)


# -------------------------------------------------------------------------------------------- concurrency --

def test_concurrent_sessions_cannot_spend_more_than_the_allowance():
    repository = enforced_runtime(env=ENV)
    spend(17)  # 3 messages left
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
    assert sorted(a.json()["max_seconds"] for a in granted) == [60, 120], "the second got what was left"
    assert voice.minted == 2, "tokens exist only for what was admitted"
    assert totals(repository) == (20, 0)


def test_the_same_key_sent_twice_is_one_session_and_one_charge():
    repository = enforced_runtime(env=ENV)
    voice = Voice()
    first = voice.open(key="open-1")
    again = voice.open(key="open-1")
    assert first.status_code == 200
    assert again.status_code == 409 and again.json()["detail"]["category"] == "operation_finished"
    assert voice.minted == 1 and totals(repository) == (2, 0)


def test_six_lost_races_are_a_429_not_a_503():
    """The cause is exhaustion, so the learner is told so: a fake store that always loses the race to somebody else."""

    class AlwaysBeaten(FakeQuotaRepository):
        def reserve(self, **kwargs):
            self.calls.append("reserve")
            return {"status": "exhausted", "limit": 20, "consumed": 19, "reserved": 1}

    repository = enforced_runtime(env=ENV, repository=AlwaysBeaten())
    spend_user = USER_KEY_CTX.set("learner-1")
    try:
        with pytest.raises(Exception) as caught:
            quota.begin_voice("orena.message", max_seconds=900, chunk_units=2, min_chunk_seconds=60, request_digest="x")
    finally:
        USER_KEY_CTX.reset(spend_user)
    assert caught.value.status_code == 429 and caught.value.detail["category"] == "quota_exhausted"
    assert repository.calls.count("reserve") == quota.VOICE_RETRIES


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


def test_a_renewal_that_cannot_read_the_limit_is_a_503_and_charges_nothing():
    repository = enforced_runtime(env=ENV)
    voice = Voice()
    opened = voice.open()
    configure_plan_store(MemorySettings(fail=True))
    refused = voice.extend(opened, 1)
    assert refused.status_code == 503 and refused.json()["detail"]["category"] == "quota_unavailable"
    assert voice.minted == 1 and totals(repository) == (2, 0)


# ------------------------------------------------------------------------------------------- switched off --

def test_voice_is_unchanged_when_messages_are_not_enforced():
    repository = enforced_runtime(env={quota.FLAG: "off"})
    voice = Voice()
    answer = voice.open()
    body = answer.json()
    assert answer.status_code == 200 and body["max_seconds"] == 900 == voice.token_life()
    assert (body["last"], body["renew_in"], body["chunk"]) == (True, None, 0), "one token for the whole session"
    voice.clock.t += 61
    assert voice.end(answer).json()["seconds"] == 61.0
    assert repository.calls == [] and repository.buckets == {}, "no read and no bucket: exactly the old path"
    (_args, kwargs), = voice.billed
    assert kwargs["audio_seconds"] == 61.0, "the ledger gets the wall-clock seconds at the end, as it always did"
    assert "sessionResumption" not in voice.setup_sent(), "what is sent to the vendor is what it always was"


def test_an_unmetered_session_nobody_ended_is_billed_at_its_cap_by_the_next_sweep():
    enforced_runtime(env={quota.FLAG: "off"})
    voice = Voice()
    voice.open()
    assert voice.billed == [], "nothing is recorded at the mint on the unmetered path"
    voice.clock.t += SESSION_SECONDS + 300
    voice.open(user="learner-2")
    assert [kwargs["audio_seconds"] for _args, kwargs in voice.billed] == [float(SESSION_SECONDS)]


def test_a_meter_that_is_not_listed_sends_the_vendor_the_old_setup():
    enforced_runtime(env={quota.FLAG: "on", quota.METERS_FLAG: "writing.review"})
    voice = Voice()
    voice.open()
    assert "sessionResumption" not in voice.setup_sent() and voice.billed == []


def test_resumption_is_asked_for_only_by_a_chunked_session_and_the_switch_takes_it_out():
    enforced_runtime(env=ENV)
    voice = Voice()
    opened = voice.open()
    assert voice.setup_sent()["sessionResumption"] == {}
    voice.extend(opened, 1, resumption="h-1")
    assert voice.setup_sent()["sessionResumption"] == {"handle": "h-1"}
    off = Voice()
    off.service.resumption = False  # AGENT_VOICE_RESUMPTION=false: the vendor refused it at connect
    opened = off.open()
    off.extend(opened, 1, resumption="h-1")
    assert all("sessionResumption" not in call[2]["bidiGenerateContentSetup"] for call in off.post.calls)
    assert off.post.calls[0][2]["bidiGenerateContentSetup"]["systemInstruction"], "the rest of the setup is the same"


def test_the_resumption_switch_reads_the_environment_given_to_it():
    from writing_coach.agent.api import voice_resumption

    assert voice_resumption({}) is True
    for value in ("false", "0", "OFF", "no"):
        assert voice_resumption({"AGENT_VOICE_RESUMPTION": value}) is False
    assert voice_resumption({"AGENT_VOICE_RESUMPTION": "true"}) is True


def test_an_unmetered_session_has_nothing_to_extend():
    enforced_runtime(env={quota.FLAG: "off"})
    voice = Voice()
    opened = voice.open()
    over = voice.extend(opened, 1)
    assert over.status_code == 409 and over.json()["detail"]["category"] == "voice_session_over"


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


# --------------------------------------------------------------------------------- the read-only check --

def test_check_available_reads_and_reserves_nothing():
    repository = enforced_runtime(env=ENV)
    reset = USER_KEY_CTX.set("learner-1")
    try:
        quota.check_available("orena.message")  # a fresh day: fine
        spend(19)
        before = list(repository.calls)
        quota.check_available("orena.message")  # one left: fine
        assert [c for c in repository.calls[len(before):]] == ["latest_buckets"], "a read, no reserve, no write"
        spend(1)
        with pytest.raises(Exception) as caught:
            quota.check_available("orena.message")
        assert caught.value.status_code == 429 and caught.value.detail["context"]["used"] == 20
        assert totals(repository) == (20, 0)
    finally:
        USER_KEY_CTX.reset(reset)


def test_check_available_is_nothing_when_not_enforced_and_503_when_unreadable():
    repository = enforced_runtime(env={quota.FLAG: "off"})
    quota.check_available("orena.message")
    assert repository.calls == []
    quota.configure_quota(env=ENV, reason="no_store")
    with pytest.raises(Exception) as caught:
        quota.check_available("orena.message")
    assert caught.value.status_code == 503


# ----------------------------------------------------------------------------------------------- the unit --

def test_a_chunk_ticket_says_what_it_buys():
    enforced_runtime(env=ENV)
    reset = USER_KEY_CTX.set("learner-1")
    try:
        ticket = quota.begin_voice("orena.message", max_seconds=900, chunk_units=2, min_chunk_seconds=60, request_digest="u")
        late = quota.begin_voice("orena.message", max_seconds=60, chunk_units=2, min_chunk_seconds=60, request_digest="v")
    finally:
        USER_KEY_CTX.reset(reset)
    assert (ticket.units, ticket.max_seconds, ticket.seconds_per_unit) == (2, 120, 60)
    assert (late.units, late.max_seconds) == (1, 60), "the last 60 s of a session cost one message"
    assert quota.NULL_TICKET.max_seconds is None and quota.NULL_TICKET.units == 0


def test_a_chunk_of_nothing_is_not_a_thing():
    enforced_runtime(env=ENV)
    with pytest.raises(ValueError):
        quota.begin_voice("orena.message", max_seconds=0, chunk_units=2)
    with pytest.raises(ValueError):
        quota.begin_voice("orena.message", max_seconds=60, chunk_units=0)


def test_a_conversion_that_is_not_a_positive_whole_number_is_unavailable_not_free():
    from fastapi import HTTPException

    entitlement = catalog.plan_by_id("free").entitlement_map()["orena.message"]
    for broken in (0, -5, True, "60", None):
        with pytest.raises(HTTPException) as refused:
            quota.seconds_per_unit(dataclasses.replace(entitlement, params={"voice_seconds_per_message": broken}))
        assert refused.value.status_code == 503
    assert quota.seconds_per_unit(entitlement) == 60


def test_refuse_unmetered_stays_a_generic_helper():
    """Voice no longer calls it; the media-import slice still does."""
    enforced_runtime(env=ENV)
    with pytest.raises(Exception) as caught:
        quota.refuse_unmetered("orena.message", category="quota_x_not_metered", message="no")
    assert caught.value.status_code == 503 and caught.value.detail["category"] == "quota_x_not_metered"
    enforced_runtime(env={quota.FLAG: "off"})
    quota.refuse_unmetered("orena.message", category="quota_x_not_metered", message="no")


def test_the_renewal_lead_leaves_the_client_time_to_reconnect():
    assert timedelta(seconds=RENEW_LEAD_SECONDS) < timedelta(seconds=VOICE_MIN_CHUNK_SECONDS) / 2
