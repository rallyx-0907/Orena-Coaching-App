"""D-16T live voice charged by duration, against real PostgreSQL: the reservation, the cap, the settlement at the end,
the abandoned session, and concurrent sessions on one allowance.

Skips unless `ORENA_TEST_POSTGRES_URL` names a THROWAWAY database (the fixtures of `tests/test_quota_gate_postgres.py`
upgrade it to head). CI has no PostgreSQL service, so these run locally. The vendor is a fake token minter, so "no
token was minted" is counted, not inferred.
"""
# Fixtures imported from sibling test modules are used by name as arguments.
# ruff: noqa: F811
from __future__ import annotations

import concurrent.futures
import os
import threading
from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("fastapi")

from test_agent_voice_session import Post  # noqa: E402
from test_quota_gate_postgres import Clock, account, engine  # noqa: E402,F401  (fixtures)
from test_quota_orena_message import _isolated  # noqa: E402,F401  (fixture)
from test_quota_orena_message_postgres import bucket_of, spend, states, wire_messages  # noqa: E402
from test_quota_voice import Voice  # noqa: E402

from writing_coach.product import quota  # noqa: E402

URL = os.getenv("ORENA_TEST_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")


def test_a_spent_day_is_a_429_with_no_token_and_no_reservation(engine, account):
    wire_messages(engine)
    spend(20)
    voice = Voice()
    answer = voice.open()
    assert answer.status_code == 429
    detail = answer.json()["detail"]
    assert detail["category"] == "quota_exhausted" and detail["context"]["used"] == detail["context"]["limit"] == 20
    assert voice.minted == 0
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (20, 0)
    assert states(engine, bucket).count(("reserved", None)) == 0


def test_the_session_holds_what_it_may_use_and_settles_what_it_used(engine, account):
    wire_messages(engine)
    spend(5)
    voice = Voice()
    answer = voice.open()
    assert answer.status_code == 200 and answer.json()["max_seconds"] == 900
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (5, 15)
    assert ("dispatched", None) in states(engine, bucket), "dispatched right before the token was minted"
    voice.clock.t += 150  # two and a half minutes: three messages, a started one counts whole
    assert voice.end(answer).json()["seconds"] == 150.0
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (8, 0), "3 charged, the other 12 released"
    assert ("settled", 3) in states(engine, bucket)


def test_the_cap_is_the_remaining_messages_on_the_real_store(engine, account):
    wire_messages(engine)
    spend(19)
    voice = Voice()
    answer = voice.open()
    assert answer.status_code == 200 and answer.json()["max_seconds"] == 60 and voice.token_life() == 60
    assert voice.open().status_code == 429, "the last message is held by the open session"
    voice.clock.t += 20
    voice.end(answer)
    assert bucket_of(engine, account)["consumed"] == 20


def test_six_concurrent_sessions_never_hold_more_than_the_day(engine, account):
    wire_messages(engine)
    voice = Voice()
    barrier = threading.Barrier(6)

    def one(_n):
        barrier.wait(timeout=15)
        return voice.open()

    with concurrent.futures.ThreadPoolExecutor(6) as pool:
        answers = list(pool.map(one, range(6)))
    assert sorted(a.status_code for a in answers) == [200, 200, 429, 429, 429, 429]
    assert sorted(a.json()["max_seconds"] for a in answers if a.status_code == 200) == [300, 900]
    assert voice.minted == 2
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (0, 20)
    for answer in answers:
        if answer.status_code == 200:
            voice.clock.t += 1
            voice.end(answer)
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (2, 0), "each ended after a second: one message each"


def test_the_same_key_sent_concurrently_is_one_session(engine, account):
    wire_messages(engine)
    voice = Voice()
    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        answers = list(pool.map(lambda _n: voice.open(key="open-1"), range(4)))
    codes = sorted(a.status_code for a in answers)
    assert codes.count(200) == 1 and all(code in (200, 409) for code in codes), codes
    assert voice.minted == 1
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (0, 15)


def test_a_refused_token_leaves_nothing_reserved(engine, account):
    wire_messages(engine)
    voice = Voice(Post(status=500))
    assert voice.open().status_code == 503
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (0, 0)
    assert ("settled", 0) in states(engine, bucket)


def test_the_reconciler_settles_an_abandoned_session_at_its_reservation(engine, account):
    repository, _service = wire_messages(engine)
    voice = Voice()
    assert voice.open().status_code == 200  # then the worker dies: nothing ends the session
    assert bucket_of(engine, account)["reserved"] == 15
    assert quota.reconcile_once(repository, now=datetime.now(UTC) + timedelta(minutes=1)) == {"settled": 0, "released": 0}
    done = quota.reconcile_once(repository, now=datetime.now(UTC) + timedelta(minutes=16))
    assert done["settled"] >= 1
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (15, 0)


def test_a_session_nobody_ended_is_settled_by_the_next_sweep_on_the_real_store(engine, account):
    wire_messages(engine)
    voice = Voice()
    lost = voice.open()
    assert lost.json()["max_seconds"] == 900
    voice.clock.t += 901
    voice.service._bill_expired()  # the process is alive: its next voice call sweeps what outlived its token
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (15, 0)


def test_plan_and_usage_read_what_voice_holds(engine, account):
    _repository, service = wire_messages(engine)
    voice = Voice()
    answer = voice.open()
    state = service.account_state(account)["features"]["orena.message"]
    assert state["usage_state"] == "known" and state["used"] == 15 and state["remaining"] == 5
    voice.clock.t += 61
    voice.end(answer)
    state = service.account_state(account)["features"]["orena.message"]
    assert state["used"] == 2 and state["remaining"] == 18
