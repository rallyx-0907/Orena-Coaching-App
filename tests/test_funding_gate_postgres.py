"""PR-MON-6 end to end on PostgreSQL: the quota gate funds through `funding_admissions` (0034, proposed), the
paid-provider backstop reads the live admission, and a provider call's cost is attributed to its operation and
aggregated by the cost model. Throwaway database only (`ORENA_TEST_POSTGRES_URL`); every write as the runtime role.
The credit price and the cost gate are test values injected here (H-1 and H-7 have none)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip("fastapi")
from fastapi import HTTPException  # noqa: E402

from tests.test_credit_ledger_postgres import URL, ledger_world, no_drift  # noqa: E402
from tests.test_credit_topup_migration_postgres import order, topup_sql  # noqa: E402
from tests.test_funding_admission_migration_postgres import ALL  # noqa: E402
from tests.test_funding_postgres import PRICE, Gate  # noqa: E402

pytestmark = pytest.mark.skipif(not URL, reason="ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")


@pytest.fixture
def world(monkeypatch):
    from writing_coach.billing import funding_context as fc
    from writing_coach.product import catalog, quota

    previous = quota.runtime()
    previous_fc = (fc._runtime.mode, fc._runtime.live, fc._runtime.dispatch)
    catalog.configure_plan_store(None)
    yield from ledger_world(ALL)
    quota.configure_funding(None)
    quota.configure_quota(**{f: getattr(previous, f) for f in
                             ("repository", "incarnations", "plan_for", "settings", "reason", "env", "clock")})
    fc._runtime.mode, fc._runtime.live, fc._runtime.dispatch = previous_fc


def wire(world, monkeypatch, *, meters="writing.review", credits_ready=True, mode="enforce"):
    from sqlalchemy import text

    from writing_coach.billing import funding_context as fc
    from writing_coach.billing.funding import FundingService, MeterPrice
    from writing_coach.persistence.funding_repository import PostgresFundingRepository
    from writing_coach.persistence.ids import stable_uuid
    from writing_coach.persistence.incarnation_repository import PostgresIncarnationRepository
    from writing_coach.persistence.product_repository import PostgresProductRepository
    from writing_coach.persistence.quota_repository import PostgresQuotaRepository
    from writing_coach.product import quota
    from writing_coach.product.service import ProductService

    key = f"funding-gate-{uuid.uuid4()}"
    with world.owner.begin() as connection:
        connection.execute(text("INSERT INTO users (id, user_key, email, name, picture, role, created_at) "
                                "VALUES (:id, :key, '', '', '', 'user', :now)"),
                           {"id": stable_uuid("user", key), "key": key, "now": datetime.now(UTC)})
    monkeypatch.setattr(quota, "current_user_key", lambda: key)
    incarnations = PostgresIncarnationRepository(world.runtime)
    repository = PostgresQuotaRepository(world.runtime)
    quota.configure_quota(repository=repository, incarnations=incarnations,
                          plan_for=ProductService(PostgresProductRepository(world.runtime)).plan_for_user,
                          settings=None, env={quota.FLAG: "on", quota.METERS_FLAG: meters})  # fmt: skip
    incarnation = incarnations.ensure_active(str(stable_uuid("user", key)))
    funding_repository = PostgresFundingRepository(world.runtime, quota=repository, credits=world.repository)
    service = FundingService(funding_repository, prices={"writing.review": MeterPrice("writing.review", PRICE, 600, "t")},
                             credits_ready=lambda: credits_ready)
    gate = Gate(("writing.review",))
    service.gate = lambda refresh=False: gate.result
    quota.configure_funding(service)
    fc.configure(mode=mode, live=service.live, dispatch=service.dispatch_for_backstop)
    return key, incarnation, service


def top_up(world, incarnation, units):
    assert world.service.ensure_account(incarnation) is not None
    paid = order(world, incarnation, units=units)
    topup_sql(world, world.balance(incarnation)["id"], paid["order_code"], units)


def spend(quota, n, prefix):
    for index in range(n):
        with quota.admit("writing.review", request_digest=f"{prefix}-{index}") as ticket:
            ticket.dispatch("p")


# ---- precedence through the gate ------------------------------------------------------------------------------------

def test_allowance_then_credits_then_refuse_through_the_gate(world, monkeypatch):
    from writing_coach.product import quota

    _key, incarnation, service = wire(world, monkeypatch)
    top_up(world, incarnation, PRICE)        # one operation's worth
    spend(quota, 2, "free")                  # Free: 2 reviews a month, both on the allowance
    with quota.admit("writing.review", request_digest="third") as ticket:
        assert ticket.source == "credits"
        ticket.dispatch("p")
    assert world.balance(incarnation)["posted"] == 0
    with pytest.raises(HTTPException) as refused:
        with quota.admit("writing.review", request_digest="fourth"):
            pass
    context = refused.value.detail["context"]
    assert refused.value.status_code == 429 and context["reason"] == "insufficient_credits"
    assert context["credits"]["needed"] == PRICE and context["credits"]["available"] == 0
    sources = world.sql("SELECT source, count(*) AS n FROM funding_admissions WHERE incarnation_id = :i "
                        "GROUP BY source ORDER BY source", i=incarnation)
    assert [(r["source"], r["n"]) for r in sources] == [("allowance", 2), ("credits", 1)]
    no_drift(world)


def test_credits_not_ready_refuse_with_credits_unavailable_and_spend_nothing(world, monkeypatch):
    from writing_coach.product import quota

    _key, incarnation, _service = wire(world, monkeypatch, credits_ready=False)
    top_up(world, incarnation, 100)
    spend(quota, 2, "free")
    with pytest.raises(HTTPException) as refused:
        with quota.admit("writing.review", request_digest="third"):
            pass
    assert refused.value.detail["context"]["reason"] == "credits_unavailable"
    assert world.balance(incarnation)["reserved"] == 0 and world.balance(incarnation)["posted"] == 100


# ---- I-1: the backstop reads the live admission ---------------------------------------------------------------------

def test_a_paid_request_needs_a_live_funded_admission(world, monkeypatch):
    from writing_coach.billing import funding_context as fc
    from writing_coach.product import quota

    _key, incarnation, service = wire(world, monkeypatch)
    assert fc.paid_allowed(capability="writing_evaluator", provider="openai") is False   # no context at all
    with quota.admit("writing.review", request_digest="one") as ticket:
        assert fc.paid_allowed(capability="writing_evaluator", provider="openai", timeout_seconds=30) is True
        assert service.repository.get(ticket.operation_id)["state"] == "dispatched"   # the first paid request
        stale = fc.current()
    with fc.funded(stale):     # an old context, after settlement: not authorization by itself
        assert fc.check_paid(capability="writing_evaluator", provider="openai") == "admission_settled"


def test_an_expired_or_short_credit_hold_blocks_the_paid_dispatch(world, monkeypatch):
    from writing_coach.billing import funding_context as fc
    from writing_coach.product import quota

    _key, incarnation, service = wire(world, monkeypatch)
    top_up(world, incarnation, 100)
    spend(quota, 2, "free")
    with pytest.raises(HTTPException) as refused:
        with quota.admit("writing.review", request_digest="credits") as ticket:
            assert ticket.source == "credits"
            # the hold has 600 s; a provider timeout longer than what is left cannot be authorized by it
            assert fc.check_paid(capability="c", provider="openai", timeout_seconds=900) == "hold_expiring"
            row = service.repository.get(ticket.operation_id)
            world.repository.expire_reserve(incarnation, reserve_entry_id=row["credit_reserve_entry_id"])
            assert fc.check_paid(capability="c", provider="openai", timeout_seconds=1) == "hold_closed"
            ticket.dispatch("p")   # the database refuses to dispatch over a closed hold
    assert refused.value.status_code == 503
    assert service.repository.get(ticket.operation_id)["state"] == "released"   # never charged (C7)
    assert world.balance(incarnation)["posted"] == 100
    no_drift(world)


# ---- §8 attribution and the operation-level report ------------------------------------------------------------------

def test_a_provider_calls_cost_is_attributed_to_its_operation_and_aggregated(world, monkeypatch):
    from writing_coach.ai import account_costs
    from writing_coach.billing.cost_model import meter_stats, read_operations
    from writing_coach.persistence.platform_repository import PostgresPlatformRepository
    from writing_coach.product import quota

    key, _incarnation, service = wire(world, monkeypatch)
    platform = PostgresPlatformRepository(world.owner)
    account_costs.install(platform)
    monkeypatch.setattr("writing_coach.core.request_context.current_user_key", lambda: key)
    event = {"capability": "writing_evaluator", "origin": "learner", "provider": "openai", "model": "gpt-4.1",
             "outcome": "success", "cost": {"state": "estimated", "amount": "0.0125"},
             "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
    try:
        with quota.admit("writing.review", request_digest="attributed") as ticket:
            account_costs.record_for_current_account(event)          # round 1
            account_costs.record_for_current_account(event)          # round 2 of the same operation
            ticket.dispatch("p")
        account_costs.record_for_current_account(event)              # outside any operation: unattributed
    finally:
        account_costs.install(None)
    rows = world.sql("SELECT operation_id, meter FROM ai_cost_records ORDER BY operation_id NULLS LAST")
    assert [(r["operation_id"], r["meter"]) for r in rows] == [
        (ticket.operation_id, "writing.review"), (ticket.operation_id, "writing.review"), (None, None)]
    operations, unattributed = read_operations(world.runtime, since=datetime.now(UTC) - timedelta(hours=1),
                                               tier_of=lambda provider, model: "paid")
    stats = meter_stats(operations)["writing.review"]
    assert unattributed == 1 and stats.complete_paid == 1 and str(stats.max_paid) == "0.02500000"
