"""D-16S `media.import` enforcement against real PostgreSQL: concurrent imports on the last minutes, restart
persistence (a reservation settled by its operation id after the process died), the month boundary in the learner's
timezone, the Plan & usage read, the reconciler's scope by meter, and duplicates/failures in the real tables.

Skips unless `ORENA_TEST_POSTGRES_URL` names a THROWAWAY database (the fixture upgrades it to head, like
`tests/test_quota_gate_postgres.py`, whose fixtures it reuses). CI has no PostgreSQL service, so these run locally.
The routes, importer and pipeline are the production code over the scripted audio layer and ASR provider of
`tests/test_quota_media_import.py`, so "the provider was not called" and "this many seconds were reserved" are counted.
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

from test_quota_gate_postgres import Clock, account, engine  # noqa: E402,F401  (fixtures)
from test_quota_media_import import (  # noqa: E402
    METER,
    World,
    _isolated,  # noqa: F401  (autouse fixture)
    media,
    video_url,
)

from writing_coach import media_quota  # noqa: E402
from writing_coach.persistence.ids import stable_uuid  # noqa: E402
from writing_coach.persistence.incarnation_repository import PostgresIncarnationRepository  # noqa: E402
from writing_coach.persistence.product_repository import PostgresProductRepository  # noqa: E402
from writing_coach.persistence.quota_repository import PostgresQuotaRepository  # noqa: E402
from writing_coach.product import quota  # noqa: E402
from writing_coach.product.service import ProductService  # noqa: E402

URL = os.getenv("ORENA_TEST_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")
LIMIT = 900  # Free: 15 minutes, stored in seconds


def wire(engine, *, clock=None, meters=METER):
    """The production wiring pointed at the throwaway database, enforcing `media.import`."""
    clock = clock or Clock()
    service = ProductService(PostgresProductRepository(engine))
    repository = PostgresQuotaRepository(engine, clock=clock)
    quota.configure_quota(
        repository=repository, incarnations=PostgresIncarnationRepository(engine), plan_for=service.plan_for_user,
        settings=None, env={quota.FLAG: "on", quota.METERS_FLAG: meters}, clock=clock,
    )
    service.usage = quota.usage_for
    return repository, service


def bucket_of(engine, key, meter=METER):
    incarnation = PostgresIncarnationRepository(engine).resolve(str(stable_uuid("user", key)))
    if incarnation is None:
        return None
    return PostgresQuotaRepository(engine).latest_buckets(incarnation, [meter]).get(meter)


def spend(seconds, *, prefix="spend"):
    with quota.admit(METER, units=seconds, request_digest=prefix) as ticket:
        ticket.dispatch("p")
        ticket.settle(seconds)


def idle_pool(world, monkeypatch):
    """A process that queues the job and dies before it runs."""
    monkeypatch.setattr(world.pipeline, "_pool", type("Idle", (), {"submit": lambda *_a, **_k: None})())
    monkeypatch.delenv("MEDIA_PIPELINE_INLINE")


def test_twenty_concurrent_imports_never_overspend_the_allowance(engine, account, tmp_path, monkeypatch):
    world = World(tmp_path, monkeypatch)
    wire(engine)
    barrier = threading.Barrier(20)

    def one(n):
        barrier.wait(timeout=20)
        return world.upload(media(60, tag=f"file-{n}"), user=account)

    with concurrent.futures.ThreadPoolExecutor(20) as pool:
        answers = list(pool.map(one, range(20)))
    assert sorted(a.status_code for a in answers) == [200] * 15 + [429] * 5, "900 s allow exactly fifteen 60 s files"
    assert world.asr.calls == 15, "the paid provider heard the admitted imports only"
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"], bucket["unit_limit"]) == (LIMIT, 0, LIMIT)
    for answer in answers:
        if answer.status_code == 429:
            context = answer.json()["detail"]["context"]
            assert (context["used"], context["limit"], context["unit"]) == (LIMIT, LIMIT, "second")
    assert len(world.entries()) == 15 and len(world.stored_files()) == 15, "a refused file stores nothing"


def test_five_concurrent_imports_on_the_last_minutes_admit_exactly_one(engine, account, tmp_path, monkeypatch):
    world = World(tmp_path, monkeypatch)
    wire(engine)
    spend(LIMIT - 100)
    barrier = threading.Barrier(5)

    def one(n):
        barrier.wait(timeout=20)
        return world.upload(media(60, tag=f"last-{n}"), user=account)

    with concurrent.futures.ThreadPoolExecutor(5) as pool:
        answers = list(pool.map(one, range(5)))
    assert sorted(a.status_code for a in answers) == [200, 429, 429, 429, 429]
    assert world.asr.calls == 1
    assert bucket_of(engine, account)["consumed"] == LIMIT - 100 + 60


def test_the_same_file_sent_concurrently_is_one_import_and_one_charge(engine, account, tmp_path, monkeypatch):
    world = World(tmp_path, monkeypatch)
    wire(engine)
    barrier = threading.Barrier(4)

    def one(_n):
        barrier.wait(timeout=20)
        return world.upload(media(60, tag="same"), user=account)

    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        answers = list(pool.map(one, range(4)))
    assert [a.status_code for a in answers] == [200] * 4 and len({a.json()["media_id"] for a in answers}) == 1
    assert world.asr.calls == 1 and bucket_of(engine, account)["consumed"] == 60


def test_a_reservation_survives_a_restart_and_is_settled_by_its_operation_id(engine, account, tmp_path, monkeypatch):
    world = World(tmp_path, monkeypatch)
    wire(engine)
    idle_pool(world, monkeypatch)
    assert world.upload(media(120, 118.5), user=account).status_code == 200
    (entry,) = world.entries()
    operation = entry.source[media_quota.SOURCE_OP]
    repository = PostgresQuotaRepository(engine)
    assert repository.get_reservation(operation)["state"] == "reserved"
    assert (bucket_of(engine, account)["consumed"], bucket_of(engine, account)["reserved"]) == (0, 120)
    # The process died. A new one: new repository, new runtime, new pipeline, the same database and the same index.
    wire(engine)
    monkeypatch.setenv("MEDIA_PIPELINE_INLINE", "1")
    assert world.new_pipeline().recover(world.store, world.assets) == 1
    reservation = repository.get_reservation(operation)
    assert (reservation["state"], reservation["actual_units"], reservation["outcome_ref"]) == (
        "settled", 119, "completed:generated_asr")
    assert (bucket_of(engine, account)["consumed"], bucket_of(engine, account)["reserved"]) == (119, 0)
    assert world.new_pipeline().recover(world.store, world.assets) == 0
    assert bucket_of(engine, account)["consumed"] == 119, "recovering again charges nothing more"


def test_a_settlement_that_could_not_be_written_is_written_by_the_next_restart(engine, account, tmp_path, monkeypatch):
    world = World(tmp_path, monkeypatch)
    repository, _service = wire(engine)
    real_settle = repository.settle

    def down(**_kwargs):
        raise RuntimeError("database unavailable")

    repository.settle = down  # type: ignore[method-assign]
    assert world.upload(media(60), user=account).status_code == 200
    (entry,) = world.entries()
    operation = entry.source[media_quota.SOURCE_OP]
    assert PostgresQuotaRepository(engine).get_reservation(operation)["state"] == "dispatched"
    assert bucket_of(engine, account)["reserved"] == 60
    repository.settle = real_settle  # type: ignore[method-assign]
    world.new_pipeline().recover(world.store, world.assets)
    assert PostgresQuotaRepository(engine).get_reservation(operation)["state"] == "settled"
    assert (bucket_of(engine, account)["consumed"], bucket_of(engine, account)["reserved"]) == (60, 0)


def test_charged_seconds_persist_and_the_next_import_adds_to_them(engine, account, tmp_path, monkeypatch):
    world = World(tmp_path, monkeypatch)
    wire(engine)
    assert world.upload(media(61.2, 58.2, "a"), user=account).status_code == 200
    assert bucket_of(engine, account)["consumed"] == 59
    _repository, service = wire(engine)  # a new process
    assert service.account_state(account)["features"][METER]["used"] == 59
    assert world.upload(media(30, tag="b"), user=account).status_code == 200
    assert bucket_of(engine, account)["consumed"] == 89


def test_failures_charge_nothing_and_a_duplicate_is_never_charged_twice(engine, account, tmp_path, monkeypatch):
    from writing_coach.speech_asr import SpeechAsrRequestFailed

    world = World(tmp_path, monkeypatch)
    wire(engine)
    world.asr.error = SpeechAsrRequestFailed(500)
    assert world.upload(media(60, tag="x"), user=account).json()["asset"]["processing_state"] == "failed"
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (0, 0), "a failed import settles 0"
    world.asr.error = None
    first = world.upload(media(60, tag="x"), user=account)
    again = world.upload(media(60, tag="x"), user=account)
    assert first.json()["media_id"] == again.json()["media_id"] and world.asr.calls == 2
    bucket = bucket_of(engine, account)
    assert (bucket["consumed"], bucket["reserved"]) == (60, 0)
    with engine.connect() as connection:
        from sqlalchemy import text

        rows = connection.execute(
            text("SELECT state, actual_units FROM commerce_quota_reservations WHERE bucket_id = :b ORDER BY actual_units"),
            {"b": bucket["id"]}).all()
    assert [tuple(r) for r in rows] == [("settled", 0), ("settled", 60)]


def test_the_month_is_the_learners_local_month(engine, account, tmp_path, monkeypatch):
    clock = Clock(datetime(2026, 10, 31, 16, 59, 0, tzinfo=UTC))  # 23:59 on Oct 31 in Ho Chi Minh City (UTC+7)
    world = World(tmp_path, monkeypatch)
    wire(engine, clock=clock)
    local = {"X-Orena-Timezone": "Asia/Ho_Chi_Minh"}
    with quota.request_facts(timezone="Asia/Ho_Chi_Minh"):
        spend(LIMIT)
    refused = world.upload(media(60, tag="october"), user=account, headers=local)
    assert refused.status_code == 429
    context = refused.json()["detail"]["context"]
    assert context["window"] == "month" and context["resets_at"] == "2026-10-31T17:00:00Z", \
        "the first of the month at midnight in the learner's zone, not UTC"
    assert world.asr.calls == 0 and world.stored_files() == []
    clock.now = datetime(2026, 10, 31, 17, 0, 1, tzinfo=UTC)  # 00:00:01 on Nov 1 locally; still Oct 31 in UTC
    assert world.upload(media(60, tag="november"), user=account, headers=local).status_code == 200
    bucket = bucket_of(engine, account)
    assert bucket["window_id"] == "M:2026-11@Asia/Ho_Chi_Minh" and bucket["consumed"] == 60


def test_the_plan_and_usage_read_equals_the_bucket_after_each_import(engine, account, tmp_path, monkeypatch):
    world = World(tmp_path, monkeypatch)
    _repository, service = wire(engine)
    for step, seconds in enumerate((None, 61.2, 300.0)):
        if seconds is not None:
            assert world.upload(media(seconds, tag=str(step)), user=account).status_code == 200
        state = service.account_state(account)["features"][METER]
        bucket = bucket_of(engine, account)
        used = 0 if bucket is None else bucket["consumed"] + bucket["reserved"]
        assert state["usage_state"] == "known"
        assert (state["used"], state["limit"], state["remaining"]) == (used, LIMIT, LIMIT - used)
        assert (state["unit"], state["display_unit"], state["scale"]) == ("second", "minute", 60)
        assert state["resets_at"] is not None
    assert state["used"] == 62 + 300, "ceil(61.2) + 300 whole seconds; the screen shows 6 minutes of 15"
    assert bucket_of(engine, account)["window_id"].startswith("M:")


def test_a_youtube_link_is_reserved_settled_and_deduplicated_in_the_real_tables(engine, account, tmp_path, monkeypatch):
    world = World(tmp_path, monkeypatch)
    wire(engine)
    world.youtube_seconds = 400.4
    first = world.source(video_url(21), user=account)
    second = world.source(video_url(21, "https://youtu.be/"), user=account)
    assert first.status_code == second.status_code == 200 and first.json()["media_id"] == second.json()["media_id"]
    assert bucket_of(engine, account)["consumed"] == 401 and world.asr.calls == 0
    world.youtube_seconds = 700
    refused = world.source(video_url(22), user=account)
    assert refused.status_code == 429 and refused.json()["detail"]["context"]["used"] == 401
    assert world.ingestion.calls == 1, "the refused link's page and captions were never read"


def test_the_store_down_is_503_and_nothing_is_stored_or_heard(engine, account, tmp_path, monkeypatch):
    world = World(tmp_path, monkeypatch)
    repository, _service = wire(engine)

    def down(**_kwargs):
        raise RuntimeError("database unavailable")

    repository.reserve = down  # type: ignore[method-assign]
    answer = world.upload(media(60), user=account)
    assert answer.status_code == 503 and answer.json()["detail"]["category"] == "quota_unavailable"
    assert world.asr.calls == 0 and world.stored_files() == [] and world.entries() == []


def test_the_reconciler_is_scoped_by_meter_in_the_real_tables(engine, account):
    hour_ago = datetime.now(UTC) - timedelta(hours=1)
    wire(engine, clock=Clock(hour_ago), meters=f"{METER},pronunciation.audio")
    take = quota.begin("pronunciation.audio", units=8, request_digest="take")
    take.dispatch("pronunciation")
    running = quota.begin(METER, units=300, request_digest="a long import")
    quota.dispatch_operation(running.operation_id, media_quota.DISPATCH_REF)
    waiting = quota.begin(METER, units=60, request_digest="a queued import")
    repository = PostgresQuotaRepository(engine)
    quota.reconcile_once(repository, limit=100000)
    assert repository.get_reservation(take.operation_id)["state"] == "settled", "a sync meter is swept after 15 minutes"
    assert repository.get_reservation(running.operation_id)["state"] == "dispatched", "an import is its worker's for hours"
    assert repository.get_reservation(waiting.operation_id)["state"] == "reserved"
    assert (bucket_of(engine, account)["reserved"], bucket_of(engine, account)["consumed"]) == (360, 0)
    # Long after: nobody settled them, so the backstop does (as admitted / released), once.
    long_ago = datetime.now(UTC) - quota.ASYNC_RECONCILE_AFTER - timedelta(minutes=5)
    with engine.begin() as connection:
        from sqlalchemy import text

        connection.execute(text("UPDATE commerce_quota_reservations SET updated_at = :t WHERE operation_id = ANY(:ops)"),
                           {"t": long_ago, "ops": [running.operation_id, waiting.operation_id]})
    quota.reconcile_once(repository, limit=100000)
    assert repository.get_reservation(running.operation_id)["state"] == "settled"
    assert repository.get_reservation(waiting.operation_id)["state"] == "released"
    bucket = bucket_of(engine, account)
    assert (bucket["reserved"], bucket["consumed"]) == (0, 300), "charged at the admitted seconds, never twice"
    quota.reconcile_once(repository, limit=100000)
    assert bucket_of(engine, account)["consumed"] == 300
