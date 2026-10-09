"""D-160 quota enforcement against real PostgreSQL: the service, the two writing routes and the usage read.

Skips unless `ORENA_TEST_POSTGRES_URL` names a THROWAWAY database (the fixture upgrades it to head, like
`tests/test_orena_quota_persistence_postgres.py`). CI has no PostgreSQL service, so these run locally.

The app itself runs on its SQLite test backend for essays; only the quota runtime (repository, incarnations,
subscription -> plan) is pointed at PostgreSQL, with a counting fake provider, so "the provider is not called"
is asserted, not inferred.
"""
from __future__ import annotations

import concurrent.futures
import os
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")
pytest.importorskip("fastapi")
from fastapi import HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from writing_coach.persistence.ids import stable_uuid  # noqa: E402
from writing_coach.persistence.incarnation_repository import PostgresIncarnationRepository  # noqa: E402
from writing_coach.persistence.product_repository import PostgresProductRepository  # noqa: E402
from writing_coach.persistence.quota_repository import PostgresQuotaRepository  # noqa: E402
from writing_coach.product import catalog, quota  # noqa: E402
from writing_coach.product.catalog import configure_plan_store  # noqa: E402
from writing_coach.product.service import ProductService  # noqa: E402

URL = os.getenv("ORENA_TEST_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")

TEXT = ("Hi Anna, I want to telling you about my last week. I go to the Da Nang office for a meeting with a "
        "customer and I dont finished the report.")


@pytest.fixture(scope="module")
def engine():
    from alembic import command
    from writing_coach.persistence.runtime import _runtime_alembic_config

    cfg = _runtime_alembic_config()
    cfg.set_main_option("sqlalchemy.url", URL.replace("%", "%%"))
    command.upgrade(cfg, "head")
    engine = create_engine(URL, future=True, pool_size=20, max_overflow=5)
    yield engine
    engine.dispose()


class Clock:
    def __init__(self, now=None):
        self.now = now

    def __call__(self):
        return self.now or datetime.now(UTC)


@pytest.fixture()
def account(engine, monkeypatch):
    """A fresh account (users row) metered by the service; the request context is pinned to it."""
    key = f"quota-gate-{uuid.uuid4()}"
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO users (id, user_key, email, name, picture, role, created_at) "
                 "VALUES (:id, :key, '', '', '', 'user', :now)"),
            {"id": stable_uuid("user", key), "key": key, "now": datetime.now(UTC)},
        )
    monkeypatch.setattr(quota, "current_user_key", lambda: key)
    monkeypatch.delenv(quota.FLAG, raising=False)
    previous = quota.runtime()
    configure_plan_store(None)
    yield key
    configure_plan_store(None)
    quota.configure_quota(**{f: getattr(previous, f) for f in
                             ("repository", "incarnations", "plan_for", "settings", "reason", "env", "clock")})


def wire(engine, *, clock=None):
    """The production wiring, pointed at the throwaway database."""
    clock = clock or Clock()
    products = PostgresProductRepository(engine)
    service = ProductService(products)
    repository = PostgresQuotaRepository(engine, clock=clock)
    quota.configure_quota(
        repository=repository, incarnations=PostgresIncarnationRepository(engine), plan_for=service.plan_for_user,
        settings=None, env={quota.FLAG: "on", quota.METERS_FLAG: "writing.review"}, clock=clock,
    )
    service.usage = quota.usage_for
    return repository, service, products


def bucket_of(engine, key):
    incarnation = PostgresIncarnationRepository(engine).resolve(str(stable_uuid("user", key)))
    if incarnation is None:
        return None
    return PostgresQuotaRepository(engine).latest_buckets(incarnation, ["writing.review"]).get("writing.review")


def spend(n, *, prefix="spend"):
    for index in range(n):
        with quota.admit("writing.review", request_digest=f"{prefix}-{index}") as ticket:
            ticket.dispatch("p")
            ticket.settle(1)


# ------------------------------------------------------------------ rooms --

@pytest.fixture()
def rooms(monkeypatch, tmp_path):
    import app as app_module
    from writing_coach.persistence.learning_repository import SQLiteLearningRepository

    client = TestClient(app_module.app)
    client.__enter__()
    repository = SQLiteLearningRepository(lambda: tmp_path / "writing.db")
    repository.initialize()
    monkeypatch.setattr(app_module, "_learning_repository", repository)
    calls: list[str] = []
    lock = threading.Lock()

    def evaluator(payload):
        with lock:
            calls.append("evaluate")
        time.sleep(0.2)  # long enough for concurrent requests to overlap
        return {"grammar": 50.0, "vocabulary": 55.0, "coherence": 60.0, "task_achievement": 58.0, "naturalness": 52.0,
                "cefr_estimate": "B1", "summary_vi": "ok", "strengths_vi": [], "strength_evidence": [],
                "priorities_vi": [], "errors": [], "schema_version": "writing-evaluation-v2"}

    def improver(payload):
        with lock:
            calls.append("improve")
        time.sleep(0.2)
        return {"corrected_text": payload.text}

    monkeypatch.setattr(app_module, "evaluate_with_ai", evaluator)
    monkeypatch.setattr(app_module, "improve_with_ai", improver)
    monkeypatch.setattr(app_module, "ALLOW_FALLBACK", False)
    monkeypatch.setattr(app_module, "get_learner_profile", lambda *a, **k: {"support_language": "vi"})
    app_module._review_in_flight.clear()
    try:
        yield client, calls, app_module
    finally:
        client.__exit__(None, None, None)


def _evaluate(client, text, **headers):
    return client.post("/api/evaluate", json={"prompt": "Email", "text": text, "learning_language": "en"}, headers=headers)


def test_five_concurrent_reviews_on_the_last_unit_call_the_provider_once(engine, account, rooms):
    client, calls, _ = rooms
    wire(engine)
    spend(1)  # Free: 2 a month, 1 left
    texts = [f"{TEXT} Variant number {n} of this piece." for n in range(5)]
    with concurrent.futures.ThreadPoolExecutor(5) as pool:
        answers = list(pool.map(lambda t: _evaluate(client, t), texts))
    statuses = sorted(answer.status_code for answer in answers)
    assert statuses == [200, 429, 429, 429, 429]
    assert calls == ["evaluate"], "exactly one provider call"
    for answer in answers:
        if answer.status_code == 429:
            context = answer.json()["detail"]["context"]
            assert answer.json()["detail"]["category"] == "quota_exhausted"
            assert context["used"] == context["limit"] == 2
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (2, 0)


def test_the_same_idempotency_key_retried_concurrently_is_one_call_and_one_charge(engine, account, rooms):
    client, calls, _ = rooms
    wire(engine)
    body = {"text": TEXT, "mode": "polish"}
    with concurrent.futures.ThreadPoolExecutor(3) as pool:
        answers = list(pool.map(lambda _n: client.post("/api/improve", json=body, headers={"Idempotency-Key": "press-1"}),
                                range(3)))
    codes = sorted(answer.status_code for answer in answers)
    assert codes.count(200) == 1 and all(code in (200, 409) for code in codes)
    assert calls == ["improve"]
    assert bucket_of(engine, account)["consumed"] == 1
    again = client.post("/api/improve", json=body, headers={"Idempotency-Key": "press-1"})
    assert again.status_code == 409 and again.json()["detail"]["category"] == "operation_finished"
    assert bucket_of(engine, account)["consumed"] == 1, "a retried key is never charged twice"


def test_an_identical_stored_review_is_free(engine, account, rooms):
    client, calls, _ = rooms
    wire(engine)
    assert _evaluate(client, TEXT).status_code == 200
    reused = _evaluate(client, TEXT)
    assert reused.status_code == 200 and reused.json()["reused"] is True
    assert calls == ["evaluate"]
    assert bucket_of(engine, account)["consumed"] == 1


def test_a_provider_error_and_the_fallback_settle_zero(engine, account, rooms, monkeypatch):
    client, calls, app_module = rooms
    wire(engine)
    from writing_coach.ai.base import AIProviderError

    def failing(payload):
        calls.append("evaluate")
        raise AIProviderError("bad")

    monkeypatch.setattr(app_module, "evaluate_with_ai", failing)
    assert _evaluate(client, TEXT).status_code == 502
    monkeypatch.setattr(app_module, "ALLOW_FALLBACK", True)
    assert _evaluate(client, TEXT + " Second.").status_code == 200
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (0, 0)
    with engine.connect() as connection:
        states = connection.execute(
            text("SELECT state, actual_units FROM commerce_quota_reservations WHERE bucket_id = :b"), {"b": bucket["id"]}
        ).all()
    assert sorted(states) == [("settled", 0), ("settled", 0)]


def test_improve_exhausted_is_429_not_502(engine, account, rooms):
    client, calls, _ = rooms
    wire(engine)
    spend(2)
    answer = client.post("/api/improve", json={"text": TEXT, "mode": "polish"})
    assert answer.status_code == 429 and answer.json()["detail"]["category"] == "quota_exhausted"
    assert int(answer.headers["Retry-After"]) > 0
    assert calls == []


def test_store_down_is_503_and_the_provider_is_not_called(engine, account, rooms):
    client, calls, _ = rooms
    dead = create_engine("postgresql+psycopg://nobody:nothing@127.0.0.1:1/none", future=True,
                         connect_args={"connect_timeout": 2})
    quota.configure_quota(repository=PostgresQuotaRepository(dead), incarnations=PostgresIncarnationRepository(dead),
                          plan_for=ProductService(PostgresProductRepository(engine)).plan_for_user,
                          env={quota.FLAG: "on", quota.METERS_FLAG: "writing.review"})
    answer = _evaluate(client, TEXT)
    assert answer.status_code == 503 and answer.json()["detail"]["category"] == "quota_unavailable"
    assert calls == []
    dead.dispose()


def test_a_catalogue_store_error_is_503_not_the_defaults(engine, account, rooms):
    client, calls, _ = rooms
    wire(engine)

    class Broken:
        def get_setting(self, key):
            raise RuntimeError("down")

    configure_plan_store(Broken())
    answer = _evaluate(client, TEXT)
    assert answer.status_code == 503 and answer.json()["detail"]["context"]["reason"] == "catalogue"
    assert calls == []


# ---------------------------------------------------------------- service --

def test_usage_survives_a_restart(engine, account):
    wire(engine)
    spend(2)
    fresh = create_engine(URL, future=True)
    try:
        wire(fresh)  # a new process: new engine, new repository, nothing in memory
        with pytest.raises(HTTPException) as refused:
            spend(1, prefix="after-restart")
        assert refused.value.status_code == 429
        assert quota.usage_for(account, catalog.FREE)["writing.review"]["used"] == 2
    finally:
        fresh.dispose()


def test_the_month_boundary_resets_and_an_inflight_op_settles_into_its_month(engine, account):
    clock = Clock(datetime(2026, 10, 31, 23, 59, 0, tzinfo=UTC))
    wire(engine, clock=clock)
    with quota.request_facts(timezone="UTC"):
        spend(1)
        inflight = quota.admit("writing.review", request_digest="inflight")
        ticket = inflight.__enter__()
        ticket.dispatch("slow provider")
        with pytest.raises(HTTPException) as refused:
            spend(1, prefix="october")
        assert refused.value.status_code == 429
        assert refused.value.detail["context"]["resets_at"] == "2026-11-01T00:00:00Z"
        clock.now = datetime(2026, 11, 1, 0, 0, 0, tzinfo=UTC)
        spend(1, prefix="november")
        ticket.settle(1)
        inflight.__exit__(None, None, None)
    incarnation = PostgresIncarnationRepository(engine).resolve(str(stable_uuid("user", account)))
    with engine.connect() as connection:
        rows = dict(connection.execute(
            text("SELECT window_id, consumed FROM commerce_quota_buckets WHERE incarnation_id = :i AND meter = 'writing.review'"),
            {"i": incarnation}).all())
    assert rows == {"M:2026-10@UTC": 2, "M:2026-11@UTC": 1}, "the in-flight October review is charged to October"


def test_the_learners_timezone_decides_the_window(engine, account):
    clock = Clock(datetime(2026, 10, 31, 17, 30, tzinfo=UTC))  # 00:30 on Nov 1 in Ho Chi Minh City
    wire(engine, clock=clock)
    with quota.request_facts(timezone="Asia/Ho_Chi_Minh"):
        spend(1)
    bucket = bucket_of(engine, account)
    assert bucket["window_id"] == "M:2026-11@Asia/Ho_Chi_Minh"
    assert bucket["window_start"] == datetime(2026, 10, 31, 17, 0, tzinfo=UTC)
    with quota.request_facts(timezone="America/Los_Angeles"):
        spend(1, prefix="moved")
    assert bucket_of(engine, account)["window_id"] == "M:2026-11@Asia/Ho_Chi_Minh", "a zone change never reopens a window"


def test_free_to_plus_keeps_usage_and_raises_the_limit_and_back_to_free_refuses(engine, account):
    _repository, service, products = wire(engine)
    spend(2)
    with pytest.raises(HTTPException):
        spend(1, prefix="free-3")
    user_id = str(stable_uuid("user", account))
    products.apply_membership(user_id, plan="plus")
    spend(1, prefix="plus-3")
    assert quota.usage_for(account, service.plan_for_user(account))["writing.review"]["used"] == 3
    state = service.account_state(account)["features"]["writing.review"]
    assert (state["used"], state["limit"], state["remaining"]) == (3, 10, 7)
    products.apply_membership(user_id, plan=None)
    with pytest.raises(HTTPException) as refused:
        spend(1, prefix="free-again")
    assert refused.value.status_code == 429
    assert refused.value.detail["context"]["used"] == 3 and refused.value.detail["context"]["limit"] == 2
    bucket = bucket_of(engine, account)
    assert bucket["unit_limit"] == 3, "the stored row never breaks its CHECK after a downgrade"


def test_the_usage_read_equals_the_bucket_after_each_step(engine, account):
    _repository, service, _products = wire(engine)
    for step in range(3):
        if step:
            spend(1, prefix=f"step-{step}")
        state = service.account_state(account)["features"]["writing.review"]
        bucket = bucket_of(engine, account)
        used = 0 if bucket is None else bucket["consumed"] + bucket["reserved"]
        assert state["usage_state"] == "known"
        assert state["used"] == used == step
        assert state["limit"] == 2
        assert state["resets_at"] is not None
        if bucket is not None:
            assert state["resets_at"] == bucket["window_end"].astimezone(UTC).isoformat().replace("+00:00", "Z")


def test_the_reconciler_charges_abandoned_dispatched_work(engine, account):
    from writing_coach.persistence.quota_repository import BucketWindow

    an_hour_ago = datetime.now(UTC) - timedelta(hours=1)
    past = PostgresQuotaRepository(engine, clock=lambda: an_hour_ago)
    incarnation = PostgresIncarnationRepository(engine).ensure_active(str(stable_uuid("user", account)))
    window = quota.window_for("month", now=an_hour_ago, zone_name="UTC", previous=None)
    operation = f"q1:abandoned-{uuid.uuid4()}"
    # What a request that died between dispatch and settle leaves behind.
    past.reserve(incarnation_id=incarnation, meter="writing.review", operation_id=operation, requested_units=1,
                 window=BucketWindow(window.window_id, window.start, window.end, "cdefault:free", 2),
                 limit_policy="current")
    past.dispatch(operation_id=operation, dispatch_ref="provider")
    done = quota.reconcile_once(PostgresQuotaRepository(engine), limit=100000)
    assert done["settled"] >= 1
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (1, 0), "charged what was reserved (ABANDONED_SETTLES)"
    assert PostgresQuotaRepository(engine).get_reservation(operation)["outcome_ref"] == "reconciled:abandoned"


# ------------------------------------- review of #116, P1-1: one window per (account, meter) under races --

ZONES = ["UTC", "Asia/Tokyo", "America/Los_Angeles", "Europe/Paris", "Asia/Ho_Chi_Minh",
         "Australia/Sydney", "America/New_York", "Asia/Kolkata", "Pacific/Auckland", "America/Sao_Paulo"]


def _race(zones, *, barrier_in_read=False, monkeypatch=None):
    """Every zone admits one review at the same moment; returns how many were admitted."""
    if barrier_in_read:
        barrier = threading.Barrier(len(zones))
        real_latest = PostgresQuotaRepository.latest_buckets

        def slow_latest(self, inc, meters):
            out = real_latest(self, inc, meters)
            try:
                barrier.wait(timeout=5)
            except threading.BrokenBarrierError:
                pass  # retries after a superseded window read again; only the first read is synchronised
            return out

        monkeypatch.setattr(PostgresQuotaRepository, "latest_buckets", slow_latest)
    start = threading.Barrier(len(zones))

    def one(zone):
        start.wait(timeout=10)
        with quota.request_facts(timezone=zone):
            try:
                with quota.admit("writing.review", request_digest=f"text-{zone}") as ticket:
                    ticket.dispatch("p")
                    ticket.settle(1)
            except HTTPException as error:
                assert error.status_code == 429, error.detail
                return 0
        return 1

    with concurrent.futures.ThreadPoolExecutor(len(zones)) as pool:
        admitted = sum(pool.map(one, zones))
    if barrier_in_read:
        monkeypatch.setattr(PostgresQuotaRepository, "latest_buckets", real_latest)
    return admitted


def _open_buckets(engine, key, now):
    incarnation = PostgresIncarnationRepository(engine).resolve(str(stable_uuid("user", key)))
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT window_id, consumed, reserved FROM commerce_quota_buckets WHERE incarnation_id = :i "
                 "AND meter = 'writing.review' AND window_start <= :now AND :now < window_end"),
            {"i": incarnation, "now": now}).all()


def test_reviewer_repro_concurrent_first_use_in_distinct_zones(engine, account, monkeypatch):
    """The reviewer's reproduction (10 of 10 admitted on a Free plan of 2 before the fix)."""
    wire(engine)
    PostgresIncarnationRepository(engine).ensure_active(str(stable_uuid("user", account)))
    assert _race(ZONES, barrier_in_read=True, monkeypatch=monkeypatch) <= 2
    open_now = _open_buckets(engine, account, datetime.now(UTC))
    assert len(open_now) == 1, open_now
    assert open_now[0][1] + open_now[0][2] <= 2


def test_reviewer_repro_without_an_injected_delay(engine, monkeypatch):
    results = []
    for _round in range(5):
        key = f"quota-race-{uuid.uuid4()}"
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO users (id, user_key, email, name, picture, role, created_at) "
                     "VALUES (:id, :key, '', '', '', 'user', :now)"),
                {"id": stable_uuid("user", key), "key": key, "now": datetime.now(UTC)})
        monkeypatch.setattr(quota, "current_user_key", lambda key=key: key)
        configure_plan_store(None)
        wire(engine)
        results.append(_race(ZONES))
        assert len(_open_buckets(engine, key, datetime.now(UTC))) == 1
    assert max(results) <= 2, results


def test_concurrent_distinct_zones_at_a_closed_window_transition(engine, account, monkeypatch):
    clock = Clock(datetime(2026, 10, 15, 12, 0, tzinfo=UTC))
    wire(engine, clock=clock)
    with quota.request_facts(timezone="UTC"):
        spend(2)  # October is used up
    clock.now = datetime(2026, 11, 1, 0, 0, 30, tzinfo=UTC)  # October (UTC) has just closed
    assert _race(ZONES, barrier_in_read=True, monkeypatch=monkeypatch) <= 2
    open_now = _open_buckets(engine, account, clock.now)
    assert len(open_now) == 1, open_now
    assert open_now[0][1] + open_now[0][2] <= 2


def test_a_window_another_bucket_covers_is_superseded_and_writes_nothing(engine, account):
    from writing_coach.persistence.quota_repository import BucketWindow

    repository, _service, _products = wire(engine)
    incarnation = PostgresIncarnationRepository(engine).ensure_active(str(stable_uuid("user", account)))
    now = datetime.now(UTC)
    utc = quota.window_for("month", now=now, zone_name="UTC", previous=None)
    tokyo = quota.window_for("month", now=now, zone_name="Asia/Tokyo", previous=None)
    first = repository.reserve(incarnation_id=incarnation, meter="writing.review", operation_id=f"q1:a-{uuid.uuid4()}",
                               requested_units=1, limit_policy="current",
                               window=BucketWindow(utc.window_id, utc.start, utc.end, "p", 2))
    assert first["status"] == "admit"
    second = repository.reserve(incarnation_id=incarnation, meter="writing.review", operation_id=f"q1:b-{uuid.uuid4()}",
                                requested_units=1, limit_policy="current",
                                window=BucketWindow(tokyo.window_id, tokyo.start, tokyo.end, "p", 2))
    assert second == {"status": "window_superseded"}
    assert repository.get_bucket(incarnation, "writing.review", tokyo.window_id) is None


def test_the_reconciler_settles_first_and_a_late_live_settle_writes_nothing(engine, account):
    """Current mode: a request outlives RECONCILE_AFTER, the reconciler charges it, then the request finishes."""
    from writing_coach.persistence.quota_repository import BucketWindow

    an_hour_ago = datetime.now(UTC) - timedelta(hours=1)
    past = PostgresQuotaRepository(engine, clock=lambda: an_hour_ago)
    incarnation = PostgresIncarnationRepository(engine).ensure_active(str(stable_uuid("user", account)))
    window = quota.window_for("month", now=an_hour_ago, zone_name="UTC", previous=None)
    operation = f"q1:slow-{uuid.uuid4()}"
    past.reserve(incarnation_id=incarnation, meter="writing.review", operation_id=operation, requested_units=1,
                 window=BucketWindow(window.window_id, window.start, window.end, "cdefault:free", 2),
                 limit_policy="current")
    past.dispatch(operation_id=operation, dispatch_ref="provider")
    live = quota.Ticket(PostgresQuotaRepository(engine), operation, 1, {})
    live.dispatched = True
    assert quota.reconcile_once(PostgresQuotaRepository(engine), limit=100000)["settled"] >= 1
    before = bucket_of(engine, account)
    late = PostgresQuotaRepository(engine).settle(operation_id=operation, actual_units=1, outcome_ref="essay:1")
    assert late["status"] == "payload_conflict"
    live.settle(1, "essay:1")  # the live ticket's own settle: logged, never raised, nothing written
    after = bucket_of(engine, account)
    assert (after["consumed"], after["reserved"]) == (before["consumed"], before["reserved"]) == (1, 0)
