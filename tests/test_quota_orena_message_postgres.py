"""D-163 `orena.message` enforcement against real PostgreSQL: the agent text turn, the text discussion turn and the
Plan & usage read.

Skips unless `ORENA_TEST_POSTGRES_URL` names a THROWAWAY database (the fixture upgrades it to head, like
`tests/test_quota_gate_postgres.py`, whose fixtures it reuses). CI has no PostgreSQL service, so these run locally.
The model is the deterministic fake, so "exactly one provider call" is counted, not inferred.
"""
# Fixtures imported from sibling test modules are used by name as arguments.
# ruff: noqa: F811
from __future__ import annotations

import concurrent.futures
import os
import threading
from datetime import UTC, datetime

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("fastapi")
from sqlalchemy import text  # noqa: E402

from test_quota_gate_postgres import Clock, account, engine  # noqa: E402,F401  (fixtures)
from test_quota_orena_message import Rig, _isolated, _run, ask, discussion, names  # noqa: E402,F401
from test_text_discussion import _answering, _CountingMeter, _FakeRepository  # noqa: E402,F401

from writing_coach.agent.errors import ProviderUnavailable  # noqa: E402
from writing_coach.agent.fake_provider import reply  # noqa: E402
from writing_coach.persistence.ids import stable_uuid  # noqa: E402
from writing_coach.persistence.incarnation_repository import PostgresIncarnationRepository  # noqa: E402
from writing_coach.persistence.product_repository import PostgresProductRepository  # noqa: E402
from writing_coach.persistence.quota_repository import PostgresQuotaRepository  # noqa: E402
from writing_coach.product import quota  # noqa: E402
from writing_coach.product.service import ProductService  # noqa: E402

URL = os.getenv("ORENA_TEST_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")
METER = "orena.message"


def wire_messages(engine, *, clock=None):
    """The production wiring pointed at the throwaway database, enforcing `orena.message`."""
    clock = clock or Clock()
    service = ProductService(PostgresProductRepository(engine))
    repository = PostgresQuotaRepository(engine, clock=clock)
    quota.configure_quota(
        repository=repository, incarnations=PostgresIncarnationRepository(engine), plan_for=service.plan_for_user,
        settings=None, env={quota.FLAG: "on", quota.METERS_FLAG: METER}, clock=clock,
    )
    service.usage = quota.usage_for
    return repository, service


def spend(n, *, prefix="spend"):
    for index in range(n):
        with quota.admit(METER, request_digest=f"{prefix}-{index}") as ticket:
            ticket.dispatch("p")
            ticket.settle(1)


def bucket_of(engine, key):
    incarnation = PostgresIncarnationRepository(engine).resolve(str(stable_uuid("user", key)))
    if incarnation is None:
        return None
    return PostgresQuotaRepository(engine).latest_buckets(incarnation, [METER]).get(METER)


def states(engine, bucket):
    with engine.connect() as connection:
        return sorted(connection.execute(
            text("SELECT state, actual_units FROM commerce_quota_reservations WHERE bucket_id = :b"),
            {"b": bucket["id"]}).all())


def test_five_concurrent_turns_on_the_last_message_call_the_provider_exactly_once(engine, account):
    wire_messages(engine)
    spend(19)  # Free: 20 a day, 1 left
    rig = Rig([reply("Màn này giữ các từ bạn đã lưu.")] * 5)
    barrier = threading.Barrier(5)

    def one(n):
        barrier.wait(timeout=10)
        return rig.turn(key=f"send-{n}")

    with concurrent.futures.ThreadPoolExecutor(5) as pool:
        answers = list(pool.map(one, range(5)))
    assert sorted(a.status_code for a in answers) == [200, 429, 429, 429, 429]
    assert len(rig.provider.requests) == 1, "exactly one provider call"
    for answer in answers:
        if answer.status_code == 429:
            detail = answer.json()["detail"]
            assert detail["category"] == "quota_exhausted"
            assert detail["context"]["used"] == detail["context"]["limit"] == 20
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (20, 0)


def test_the_same_key_retried_concurrently_is_one_call_and_one_charge(engine, account):
    wire_messages(engine)
    rig = Rig([reply("Màn này giữ các từ bạn đã lưu.")] * 3)
    with concurrent.futures.ThreadPoolExecutor(3) as pool:
        answers = list(pool.map(lambda _n: rig.turn(key="send-1"), range(3)))
    codes = sorted(a.status_code for a in answers)
    assert codes.count(200) == 1 and all(code in (200, 409) for code in codes)
    assert len(rig.provider.requests) == 1
    assert bucket_of(engine, account)["consumed"] == 1


def test_the_free_turns_write_nothing_and_a_spent_day_still_greets(engine, account):
    wire_messages(engine)
    spend(20)
    rig = Rig([reply("Chào bạn, hôm nay ôn vài từ nhé.")])
    for _refresh in range(5):  # refresh and reconnect: a new session each, all 200, one model greeting in all
        assert rig.turn(trigger="open", surface="orena.home").status_code == 200
    assert rig.turn("Bạn là ai?").status_code == 200
    assert rig.turn().status_code == 429
    assert len(rig.provider.requests) == 1, "only the greeting asked a model"
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (20, 0)


def test_a_failed_provider_settles_zero_and_a_leaver_settles_one(engine, account):
    wire_messages(engine)
    failing = Rig([(ProviderUnavailable("down"),)])
    assert names(failing.turn())[-1] == "error"
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (0, 0)
    assert states(engine, bucket) == [("settled", 0)]
    leaver = Rig([reply("Màn này giữ các từ bạn đã lưu và cho biết từ nào đến hạn ôn.")])
    stream = _run(leaver)
    for event in stream:
        if event.name == "segment_delta":
            break
    stream.close()  # the client disconnected mid-answer
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (1, 0)
    assert states(engine, bucket) == [("settled", 0), ("settled", 1)]
    early = Rig([reply("x")])
    stream = _run(early)
    next(stream)
    stream.close()  # the client left before the model ran
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (1, 0)
    assert states(engine, bucket) == [("settled", 0), ("settled", 0), ("settled", 1)]


def test_the_day_is_the_learners_local_day(engine, account):
    clock = Clock(datetime(2026, 10, 9, 16, 59, 0, tzinfo=UTC))  # 23:59 on Oct 9 in Ho Chi Minh City (UTC+7)
    wire_messages(engine, clock=clock)
    rig = Rig([reply("Màn này giữ các từ bạn đã lưu.")] * 3)
    local = {"X-Orena-Timezone": "Asia/Ho_Chi_Minh"}
    with quota.request_facts(timezone="Asia/Ho_Chi_Minh"):
        spend(20)
    spent = rig.turn(headers=local)
    assert spent.status_code == 429
    context = spent.json()["detail"]["context"]
    assert context["window"] == "day" and context["resets_at"] == "2026-10-09T17:00:00Z", \
        "midnight in the learner's zone, not UTC midnight"
    clock.now = datetime(2026, 10, 9, 17, 0, 1, tzinfo=UTC)  # 00:00:01 on Oct 10 locally; still Oct 9 in UTC
    assert rig.turn(headers=local).status_code == 200
    buckets = bucket_of(engine, account)
    assert buckets["window_id"] == "D:2026-10-10@Asia/Ho_Chi_Minh" and buckets["consumed"] == 1


def test_the_plan_and_usage_read_equals_the_bucket(engine, account):
    _repository, service = wire_messages(engine)
    rig = Rig([reply("Màn này giữ các từ bạn đã lưu.")] * 2)
    for step in range(2):
        if step:
            assert rig.turn(key=f"k{step}").status_code == 200
        state = service.account_state(account)["features"][METER]
        bucket = bucket_of(engine, account)
        used = 0 if bucket is None else bucket["consumed"] + bucket["reserved"]
        assert state["usage_state"] == "known"
        assert (state["used"], state["limit"], state["remaining"]) == (used, 20, 20 - used) == (step, 20, 20 - step)
        assert state["resets_at"] is not None
    assert bucket_of(engine, account)["window_id"].startswith("D:")


def test_voice_is_refused_with_the_real_store_and_mints_nothing(engine, account):
    from test_quota_orena_message import StubVoice

    wire_messages(engine)
    voice = StubVoice()
    rig = Rig([], voice=voice)
    answer = rig.client.post("/api/agent/voice/session", json={})
    assert answer.status_code == 503 and answer.json()["detail"]["category"] == "quota_voice_not_metered"
    assert voice.opened == 0
    assert bucket_of(engine, account) is None


def test_a_discussion_turn_is_one_message_on_the_real_store(engine, account, discussion):
    build, _store, calls = discussion
    wire_messages(engine)
    client = build()
    assert ask(client, request_id="r1").status_code == 200
    assert ask(client, request_id="r1").json()["reused"] is True
    assert calls == [1]
    assert bucket_of(engine, account)["consumed"] == 1
    spend(19, prefix="rest")
    refused = ask(client, request_id="r2")
    assert refused.status_code == 429 and refused.json()["detail"]["context"]["feature"] == METER
    assert calls == [1]


def test_free_to_plus_raises_the_daily_limit_and_keeps_usage(engine, account):
    _repository, service = wire_messages(engine)
    products = PostgresProductRepository(engine)
    spend(20)
    with pytest.raises(Exception) as refused:
        spend(1, prefix="more")
    assert refused.value.status_code == 429
    products.apply_membership(str(stable_uuid("user", account)), plan="plus")
    spend(1, prefix="plus-21")
    state = service.account_state(account)["features"][METER]
    assert (state["used"], state["limit"]) == (21, 200)
