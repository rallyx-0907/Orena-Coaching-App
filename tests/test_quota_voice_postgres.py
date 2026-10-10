"""D-169 live voice charged by duration, against real PostgreSQL: each chunk reserved and settled whole at its token, the
renewal chain, no refund for an early end, concurrent sessions on one allowance, and the read-only check.

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
    assert all(state != "reserved" for state, _units in states(engine, bucket))


def test_a_chunk_is_reserved_dispatched_and_settled_whole_at_its_token(engine, account):
    wire_messages(engine)
    spend(5)
    voice = Voice()
    answer = voice.open()
    assert answer.status_code == 200 and answer.json()["max_seconds"] == 120
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (7, 0), "two messages, charged at once; nothing is held"
    assert ("settled", 2) in states(engine, bucket)
    voice.clock.t += 108
    renewed = voice.extend(answer, 1)
    assert renewed.status_code == 200 and renewed.json()["chunk"] == 1
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (9, 0)
    again = voice.extend(answer, 1)
    assert again.json() == renewed.json() and bucket_of(engine, account)["consumed"] == 9, "a repeat is free"


def test_ending_early_refunds_nothing_and_stops_renewals(engine, account):
    wire_messages(engine)
    voice = Voice()
    answer = voice.open()
    assert voice.end(answer).status_code == 200
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (2, 0)
    assert voice.extend(answer, 1).status_code == 404
    assert bucket_of(engine, account)["consumed"] == 2


def test_the_chunk_is_the_remaining_messages_on_the_real_store(engine, account):
    wire_messages(engine)
    spend(19)
    voice = Voice()
    answer = voice.open()
    assert answer.status_code == 200 and answer.json()["max_seconds"] == 60 and voice.token_life() == 60
    assert voice.open().status_code == 429, "the last message is gone"
    assert bucket_of(engine, account)["consumed"] == 20
    renewal = voice.extend(answer, 1)
    assert renewal.status_code == 429 and renewal.json()["detail"]["category"] == "quota_exhausted"


def test_open_end_over_and_over_never_beats_the_allowance(engine, account):
    wire_messages(engine)
    voice = Voice()
    lives = []
    for _round in range(30):
        answer = voice.open()
        if answer.status_code != 200:
            break
        lives.append(answer.json()["max_seconds"])
        voice.end(answer)
    assert sum(lives) == 20 * 60 and voice.minted == len(lives)
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (20, 0)


def test_six_concurrent_sessions_on_three_messages_hold_exactly_three(engine, account):
    wire_messages(engine)
    spend(17)
    voice = Voice()
    barrier = threading.Barrier(6)

    def one(_n):
        barrier.wait(timeout=15)
        return voice.open()

    with concurrent.futures.ThreadPoolExecutor(6) as pool:
        answers = list(pool.map(one, range(6)))
    assert sorted(a.status_code for a in answers) == [200, 200, 429, 429, 429, 429]
    assert sorted(a.json()["max_seconds"] for a in answers if a.status_code == 200) == [60, 120]
    assert voice.minted == 2
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (20, 0)


def test_concurrent_renewals_of_one_chunk_charge_once(engine, account):
    wire_messages(engine)
    voice = Voice()
    answer = voice.open()
    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        results = list(pool.map(lambda _n: voice.extend(answer, 1), range(4)))
    assert [r.status_code for r in results] == [200] * 4
    assert len({r.json()["connect"]["ephemeral_token"] for r in results}) == 1
    assert voice.minted == 2
    assert bucket_of(engine, account)["consumed"] == 4


def test_the_same_key_sent_concurrently_is_one_session(engine, account):
    wire_messages(engine)
    voice = Voice()
    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        answers = list(pool.map(lambda _n: voice.open(key="open-1"), range(4)))
    codes = sorted(a.status_code for a in answers)
    assert codes.count(200) == 1 and all(code in (200, 409) for code in codes), codes
    assert voice.minted == 1
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (2, 0)


def test_a_refused_token_leaves_nothing_charged(engine, account):
    wire_messages(engine)
    voice = Voice(Post(status=500))
    assert voice.open().status_code == 503
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (0, 0)
    assert ("settled", 0) in states(engine, bucket)


def test_the_reconciler_has_nothing_to_settle_for_a_vanished_session(engine, account):
    repository, _service = wire_messages(engine)
    voice = Voice()
    assert voice.open().status_code == 200  # then the worker dies: nothing ends the session
    done = quota.reconcile_once(repository, now=datetime.now(UTC) + timedelta(minutes=16))
    assert done == {"settled": 0, "released": 0}, "every chunk was settled when its token was minted"
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (2, 0)


def test_check_available_is_a_pure_read_on_the_real_store(engine, account):
    wire_messages(engine)
    spend(19)
    quota.check_available("orena.message")
    assert bucket_of(engine, account)["consumed"] == 19
    spend(1)
    with pytest.raises(Exception) as refused:
        quota.check_available("orena.message")
    assert refused.value.status_code == 429
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (20, 0)


def test_plan_and_usage_read_what_voice_has_charged(engine, account):
    _repository, service = wire_messages(engine)
    voice = Voice()
    answer = voice.open()
    state = service.account_state(account)["features"]["orena.message"]
    assert state["usage_state"] == "known" and state["used"] == 2 and state["remaining"] == 18
    voice.extend(answer, 1)
    state = service.account_state(account)["features"]["orena.message"]
    assert state["used"] == 4 and state["remaining"] == 16
