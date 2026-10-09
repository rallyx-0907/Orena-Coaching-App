"""D-16Z `pronunciation.audio` enforcement against real PostgreSQL: concurrent takes on the last seconds, restart
persistence, the month boundary in the learner's timezone, the Plan & usage read, and the reconciler.

Skips unless `ORENA_TEST_POSTGRES_URL` names a THROWAWAY database (the fixture upgrades it to head, like
`tests/test_quota_gate_postgres.py`, whose fixtures it reuses). CI has no PostgreSQL service, so these run locally.
The provider is the real Azure adapter over a fake HTTP session and a fake decoder, so "the provider was not called"
and "exactly this many seconds were sent" are counted, not inferred.
"""
# Fixtures imported from sibling test modules are used by name as arguments.
# ruff: noqa: F811
from __future__ import annotations

import concurrent.futures
import os
import threading
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("fastapi")
from sqlalchemy import text  # noqa: E402

from test_quota_gate_postgres import Clock, account, engine  # noqa: E402,F401  (fixtures)
from test_quota_pronunciation import (  # noqa: E402
    SCORED,
    AzureSession,
    _isolated,  # noqa: F401  (autouse fixture)
    assess,
    azure,
    build_client,
    take,
)

from writing_coach import speech_api  # noqa: E402
from writing_coach.persistence.ids import stable_uuid  # noqa: E402
from writing_coach.persistence.incarnation_repository import PostgresIncarnationRepository  # noqa: E402
from writing_coach.persistence.product_repository import PostgresProductRepository  # noqa: E402
from writing_coach.persistence.quota_repository import PostgresQuotaRepository  # noqa: E402
from writing_coach.product import quota  # noqa: E402
from writing_coach.product.service import ProductService  # noqa: E402

URL = os.getenv("ORENA_TEST_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")
METER = "pronunciation.audio"
LIMIT = 300  # Free: 5 minutes, stored in seconds


class SlowSession(AzureSession):
    """Long enough for concurrent requests to overlap, and a count of what really reached 'Azure'."""

    def post(self, url: str, **kwargs: Any):
        time.sleep(0.05)
        return super().post(url, **kwargs)


def wire(engine, *, clock=None):
    """The production wiring pointed at the throwaway database, enforcing `pronunciation.audio`."""
    clock = clock or Clock()
    service = ProductService(PostgresProductRepository(engine))
    repository = PostgresQuotaRepository(engine, clock=clock)
    quota.configure_quota(
        repository=repository, incarnations=PostgresIncarnationRepository(engine), plan_for=service.plan_for_user,
        settings=None, env={quota.FLAG: "on", quota.METERS_FLAG: METER}, clock=clock,
    )
    service.usage = quota.usage_for
    return repository, service


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


def spend(seconds, *, prefix="spend"):
    with quota.admit(METER, units=seconds, request_digest=prefix) as ticket:
        ticket.dispatch("p")
        ticket.settle(seconds)


def test_twenty_concurrent_takes_never_overspend_the_allowance(engine, account):
    wire(engine)
    session = SlowSession()
    speech_api.configure_speech_pronunciation(azure(session))
    client = build_client()
    barrier = threading.Barrier(20)

    def one(n):
        barrier.wait(timeout=20)
        return assess(client, take(20.0, str(n)), key=f"take-{n}")

    with concurrent.futures.ThreadPoolExecutor(20) as pool:
        answers = list(pool.map(one, range(20)))
    codes = sorted(a.status_code for a in answers)
    assert codes == [200] * 15 + [429] * 5, "300 s allow exactly fifteen 20 s takes"
    assert session.posts == 15, "the paid provider was called for the admitted takes only"
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"], bucket["unit_limit"]) == (LIMIT, 0, LIMIT)
    settled = states(engine, bucket)
    assert sum(units for _state, units in settled) <= LIMIT and len(settled) == 15
    for answer in answers:
        if answer.status_code == 429:
            context = answer.json()["detail"]["context"]
            assert (context["used"], context["limit"], context["unit"]) == (LIMIT, LIMIT, "second")


def test_five_concurrent_takes_on_the_last_seconds_spend_exactly_one(engine, account):
    wire(engine)
    spend(LIMIT - 10)
    session = SlowSession()
    speech_api.configure_speech_pronunciation(azure(session))
    client = build_client()
    barrier = threading.Barrier(5)

    def one(n):
        barrier.wait(timeout=20)
        return assess(client, take(5.5, str(n)), key=f"last-{n}")

    with concurrent.futures.ThreadPoolExecutor(5) as pool:
        answers = list(pool.map(one, range(5)))
    assert sorted(a.status_code for a in answers) == [200, 429, 429, 429, 429]
    assert session.posts == 1
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (LIMIT - 10 + 6, 0)


def test_the_same_take_sent_concurrently_is_one_provider_call_and_one_charge(engine, account):
    wire(engine)
    session = SlowSession()
    speech_api.configure_speech_pronunciation(azure(session))
    client = build_client()
    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        answers = list(pool.map(lambda _n: assess(client, take(7.4), key="one-take"), range(4)))
    codes = sorted(a.status_code for a in answers)
    assert codes.count(200) == 1 and all(code in (200, 409) for code in codes)
    assert session.posts == 1
    assert bucket_of(engine, account)["consumed"] == 8


def test_charged_seconds_survive_a_restart_and_the_next_take_adds_to_them(engine, account):
    wire(engine)
    session = AzureSession()
    speech_api.configure_speech_pronunciation(azure(session))
    assert assess(build_client(), take(7.4), key="before").status_code == 200
    assert bucket_of(engine, account)["consumed"] == 8
    _repository, service = wire(engine)  # a new process: new repository, new runtime, same database
    assert service.account_state(account)["features"][METER]["used"] == 8, "the usage read survives the restart"
    assert assess(build_client(), take(3.0, "after"), key="after").status_code == 200
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (11, 0)
    assert states(engine, bucket) == [("settled", 3), ("settled", 8)]


def test_failures_and_unusable_results_charge_nothing_and_a_new_key_may_try_again(engine, account):
    wire(engine)
    session = AzureSession(500, {"error": "boom"})
    speech_api.configure_speech_pronunciation(azure(session))
    client = build_client()
    assert assess(client, take(9.0), key="attempt-1").status_code == 502
    session.status, session.payload = 200, {"NBest": []}  # Azure answers and bills 9 s, the result is unusable
    assert assess(client, take(9.0), key="attempt-2").status_code == 502
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (0, 0)
    assert states(engine, bucket) == [("settled", 0), ("settled", 0)]
    session.payload = SCORED
    assert assess(client, take(9.0), key="attempt-3").status_code == 200
    again = assess(client, take(9.0), key="attempt-3")
    assert again.status_code == 409 and again.json()["detail"]["category"] == "operation_finished"
    assert bucket_of(engine, account)["consumed"] == 9 and session.posts == 3


def test_a_silent_take_is_charged_the_seconds_azure_processed(engine, account):
    wire(engine)
    silent = {"NBest": [{"PronScore": 0, "AccuracyScore": 0, "FluencyScore": 0, "CompletenessScore": 0,
                         "Words": [{"Word": "good", "AccuracyScore": 0, "ErrorType": "Omission"}]}]}
    speech_api.configure_speech_pronunciation(azure(AzureSession(200, silent)))
    assert assess(build_client(), take(3.2)).status_code == 422
    assert bucket_of(engine, account)["consumed"] == 4


def test_the_month_is_the_learners_local_month(engine, account):
    clock = Clock(datetime(2026, 10, 31, 16, 59, 0, tzinfo=UTC))  # 23:59 on Oct 31 in Ho Chi Minh City (UTC+7)
    wire(engine, clock=clock)
    session = AzureSession()
    speech_api.configure_speech_pronunciation(azure(session))
    client = build_client()
    local = {"X-Orena-Timezone": "Asia/Ho_Chi_Minh"}
    with quota.request_facts(timezone="Asia/Ho_Chi_Minh"):
        spend(LIMIT)
    spent = assess(client, take(3.0), headers=local)
    assert spent.status_code == 429
    context = spent.json()["detail"]["context"]
    assert context["window"] == "month" and context["resets_at"] == "2026-10-31T17:00:00Z", \
        "the first of the month at midnight in the learner's zone, not UTC"
    assert session.posts == 0
    clock.now = datetime(2026, 10, 31, 17, 0, 1, tzinfo=UTC)  # 00:00:01 on Nov 1 locally; still Oct 31 in UTC
    assert assess(client, take(3.0, "november"), headers=local).status_code == 200
    bucket = bucket_of(engine, account)
    assert bucket["window_id"] == "M:2026-11@Asia/Ho_Chi_Minh" and bucket["consumed"] == 3


def test_the_plan_and_usage_read_equals_the_bucket_after_each_take(engine, account):
    _repository, service = wire(engine)
    speech_api.configure_speech_pronunciation(azure(AzureSession()))
    client = build_client()
    for step, seconds in enumerate((None, 7.4, 52.0)):
        if seconds is not None:
            assert assess(client, take(seconds, str(step)), key=f"read-{step}").status_code == 200
        state = service.account_state(account)["features"][METER]
        bucket = bucket_of(engine, account)
        used = 0 if bucket is None else bucket["consumed"] + bucket["reserved"]
        assert state["usage_state"] == "known"
        assert (state["used"], state["limit"], state["remaining"]) == (used, LIMIT, LIMIT - used)
        assert (state["unit"], state["display_unit"], state["scale"]) == ("second", "minute", 60)
        assert state["resets_at"] is not None
    assert state["used"] == 60  # 8 + 52 whole seconds; the screen shows 1 minute of 5
    assert bucket_of(engine, account)["window_id"].startswith("M:")


def test_free_to_plus_raises_the_limit_and_keeps_the_seconds_used(engine, account):
    _repository, service = wire(engine)
    products = PostgresProductRepository(engine)
    spend(LIMIT)
    session = AzureSession()
    speech_api.configure_speech_pronunciation(azure(session))
    client = build_client()
    assert assess(client, take(3.0)).status_code == 429 and session.posts == 0
    products.apply_membership(str(stable_uuid("user", account)), plan="plus")
    assert assess(client, take(3.0, "plus")).status_code == 200
    state = service.account_state(account)["features"][METER]
    assert (state["used"], state["limit"]) == (LIMIT + 3, 1800)


def test_the_store_down_is_503_and_the_provider_is_not_called(engine, account):
    repository, _service = wire(engine)

    def down(**_kwargs):
        raise RuntimeError("database unavailable")

    repository.reserve = down  # type: ignore[method-assign]
    session = AzureSession()
    speech_api.configure_speech_pronunciation(azure(session))
    answer = assess(build_client(), take(3.0))
    assert answer.status_code == 503 and answer.json()["detail"]["category"] == "quota_unavailable"
    assert session.posts == 0


def test_the_reconciler_charges_a_take_abandoned_after_dispatch(engine, account):
    an_hour_ago = datetime.now(UTC) - timedelta(hours=1)
    wire(engine, clock=Clock(an_hour_ago))
    ticket = quota.begin(METER, units=8, request_digest="abandoned")
    ticket.dispatch("pronunciation")  # the process died with the paid request in flight
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (0, 8)
    done = quota.reconcile_once(PostgresQuotaRepository(engine), limit=100000)
    assert done["settled"] >= 1
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (8, 0), "charged at the admitted seconds (D-161 point 10)"
