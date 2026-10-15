"""PR-MON-6 funding admissions on PostgreSQL (`ORENA_TEST_POSTGRES_URL`, throwaway database only).

The schema is the Alembic head plus 0027 -> 0033 and the proposed 0034 (not promoted). Everything runs as the
non-superuser runtime role (a member of `orena_credit_runtime`), so the 0034 guards and column grants are exercised by
the service, not bypassed. Prices and the cost gate are test values injected here; nothing in the product has any."""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from tests.test_credit_ledger_postgres import URL, ledger_world, no_drift
from tests.test_funding_admission_migration_postgres import ALL, credits

pytestmark = pytest.mark.skipif(not URL, reason="ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")

PRICE = 4


@pytest.fixture
def world():
    yield from ledger_world(ALL)


class Gate:
    def __init__(self, meters):
        from writing_coach.billing.cost_model import GateResult

        self.result = GateResult(gate_id="cg1:test", meters={m: True for m in meters})


def service(world, *, price=PRICE, ready=True, eligible=("writing.review",), clock=None):
    from writing_coach.billing.funding import FundingService, MeterPrice
    from writing_coach.persistence.funding_repository import PostgresFundingRepository
    from writing_coach.persistence.quota_repository import PostgresQuotaRepository

    repository = PostgresFundingRepository(world.runtime, quota=PostgresQuotaRepository(world.runtime),
                                           credits=world.repository, clock=clock)
    prices = {m: MeterPrice(m, price, 600, "test-prices-1") for m in eligible}
    svc = FundingService(repository, prices=prices, credits_ready=lambda: ready)
    gate = Gate(eligible)
    svc.gate = lambda refresh=False: gate.result  # the H-7 gate is the human's; a test result stands in for it
    return svc


def window(limit=1, *, wid=None):
    from writing_coach.persistence.quota_repository import BucketWindow

    now = datetime.now(UTC)
    return BucketWindow(wid or f"2026-10-{uuid.uuid4().hex[:6]}", now - timedelta(hours=1), now + timedelta(days=30),
                        "plus@rev1", limit)


def wider(win, limit):
    """The same plan window with another current limit (an administrator's edit or an upgrade)."""
    from writing_coach.persistence.quota_repository import BucketWindow

    return BucketWindow(win.window_id, win.window_start, win.window_end, win.policy_version, limit)


def intent(incarnation, *, op=None, meter="writing.review", units=1, ref="review-1"):
    from writing_coach.persistence.funding_repository import FundingIntent

    return FundingIntent(incarnation_id=incarnation, operation_id=op or f"q1:{uuid.uuid4().hex}", meter=meter,
                         units=units, operation_ref=ref, feature="test")


def plan(win):
    from writing_coach.billing.funding import PlanAllowance

    return PlanAllowance(win)


def exhaust(world, svc, incarnation, win):
    """Spend the plan allowance of `win` with one settled operation."""
    first = svc.admit(intent(incarnation), plan=plan(win))
    assert first.funded and first.row["source"] == "allowance"
    assert svc.settle(first.row["operation_id"], 1) == "settled"


def counts(world, op):
    return world.sql("SELECT (SELECT count(*) FROM funding_admissions WHERE operation_id = :op) AS admissions, "
                     "(SELECT count(*) FROM commerce_quota_reservations WHERE operation_id = :key) AS reservations, "
                     "(SELECT count(*) FROM credit_ledger WHERE idempotency_key = :key) AS holds",
                     op=op, key=f"fund:{op}")[0]


# ---- precedence: promotional -> plan -> credits -> refuse ---------------------------------------------------------------

def test_allowance_first_then_credits_then_refuse(world):
    svc = service(world)
    incarnation, _account = credits(world, units=PRICE * 1)  # enough for one operation on credits
    win = window(limit=1)
    exhaust(world, svc, incarnation, win)
    second = svc.admit(intent(incarnation), plan=plan(win))
    assert second.funded and second.row["source"] == "credits"
    assert second.row["price_per_unit"] == PRICE and second.row["amount_reserved"] == PRICE
    assert world.balance(incarnation)["reserved"] == PRICE
    op = f"q1:{uuid.uuid4().hex}"
    third = svc.admit(intent(incarnation, op=op), plan=plan(win))
    assert third.status == "refused" and third.refusal.reason == "insufficient_credits"
    assert third.refusal.facts["credits"] == {"available": 0, "needed": PRICE, "price_per_unit": PRICE}
    assert counts(world, op) == {"admissions": 0, "reservations": 0, "holds": 0}  # a refusal writes nothing
    no_drift(world)


def test_credits_not_ready_or_not_eligible_refuses_with_its_reason(world):
    incarnation, _ = credits(world)
    win = window(limit=1)
    svc = service(world, ready=False)
    exhaust(world, svc, incarnation, win)
    assert svc.admit(intent(incarnation), plan=plan(win)).refusal.reason == "credits_unavailable"
    unpriced = service(world, eligible=())
    assert unpriced.admit(intent(incarnation), plan=plan(win)).refusal.reason == "not_credit_eligible"
    assert world.balance(incarnation)["reserved"] == 0


def test_media_import_is_allowance_only_even_with_credits_ready(world):
    from writing_coach.billing.funding import load_meter_prices

    incarnation, _ = credits(world)
    win = window(limit=1)
    svc = service(world)
    first = svc.admit(intent(incarnation, meter="media.import"), plan=plan(win))
    assert first.funded and first.row["source"] == "allowance"
    refused = svc.admit(intent(incarnation, meter="media.import"), plan=plan(win))
    assert refused.refusal.reason == "allowance_exhausted"
    assert world.balance(incarnation)["reserved"] == 0
    assert svc.credit_terms("media.import") == (None, "not_credit_eligible")
    with pytest.raises(ValueError, match="cannot be funded by credits"):
        path = _prices_file([{"meter": "media.import", "credit_price": 1, "hold_ttl_seconds": 60, "revision": "x"}])
        load_meter_prices({"BILLING_METER_PRICES_FILE": path})


def _prices_file(items):
    import json
    import tempfile

    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(items, handle)
    handle.close()
    return handle.name


def test_promotional_grants_before_the_plan_earliest_expiry_first(world):
    svc = service(world)
    incarnation = world.account()
    user = world.sql("SELECT user_id FROM account_incarnations WHERE id = :i", i=incarnation)[0]["user_id"]
    late = _grant(world, user, incarnation, "late", days=20)
    early = _grant(world, user, incarnation, "early", days=5)
    win = window(limit=5)
    sources = []
    for _ in range(3):
        outcome = svc.admit(intent(incarnation), plan=plan(win))
        bucket = world.sql("SELECT b.window_id FROM commerce_quota_reservations r JOIN commerce_quota_buckets b "
                           "ON b.id = r.bucket_id WHERE r.id = :r", r=outcome.row["quota_reservation_id"])[0]
        sources.append((outcome.row["source"], bucket["window_id"]))
    assert sources == [("promotional", f"promo:{early}"), ("promotional", f"promo:{late}"),
                       ("allowance", win.window_id)]


def _grant(world, user, incarnation, grant_id, *, days, meter="writing.review", units=1):
    from writing_coach.billing.promotional import GrantDefinition, claim

    definition = GrantDefinition(grant_id=grant_id, meters={meter: units}, valid_days=days, policy_version="test")
    return claim(world.runtime, definition, user_id=str(user), incarnation_id=incarnation)


# ---- idempotency and races -------------------------------------------------------------------------------------------

def test_a_retry_replays_its_source_and_a_different_intent_is_a_conflict(world):
    svc = service(world)
    incarnation, _ = credits(world)
    win = window(limit=1)
    exhaust(world, svc, incarnation, win)
    op = f"q1:{uuid.uuid4().hex}"
    first = svc.admit(intent(incarnation, op=op), plan=plan(win))
    assert first.row["source"] == "credits"
    bigger = wider(win, 100)  # allowance would now be available: a retry never chooses again
    again = svc.admit(intent(incarnation, op=op), plan=plan(bigger))
    assert again.funded and again.row["credit_reserve_entry_id"] == first.row["credit_reserve_entry_id"]
    assert svc.admit(intent(incarnation, op=op, units=2), plan=plan(win)).status == "operation_conflict"
    assert svc.admit(intent(incarnation, op=op, ref="other"), plan=plan(win)).status == "operation_conflict"
    assert svc.settle(op, 1) == "settled"
    assert svc.admit(intent(incarnation, op=op), plan=plan(win)).status == "operation_completed"
    op2 = f"q1:{uuid.uuid4().hex}"
    svc.admit(intent(incarnation, op=op2), plan=plan(bigger))
    svc.release(op2)
    assert svc.admit(intent(incarnation, op=op2), plan=plan(bigger)).status == "operation_closed"


def test_concurrent_admissions_of_one_operation_reserve_one_source(world):
    svc = service(world)
    incarnation, _ = credits(world, units=100)
    win = window(limit=1)
    exhaust(world, svc, incarnation, win)
    op, results, barrier = f"q1:{uuid.uuid4().hex}", [], threading.Barrier(6)

    def racer():
        barrier.wait()
        results.append(svc.admit(intent(incarnation, op=op), plan=plan(win)))

    threads = [threading.Thread(target=racer) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert len(results) == 6 and all(r.funded for r in results)
    assert len({str(r.row["credit_reserve_entry_id"]) for r in results}) == 1
    assert counts(world, op) == {"admissions": 1, "reservations": 0, "holds": 1}
    assert world.balance(incarnation)["reserved"] == PRICE
    no_drift(world)


# ---- settlement: the snapshot, H-3, idempotency ------------------------------------------------------------------------

def test_settlement_uses_the_snapshot_even_after_the_price_changes(world):
    incarnation, _ = credits(world, units=100)
    win = window(limit=1)
    old = service(world, price=PRICE)
    exhaust(world, old, incarnation, win)
    funded = old.admit(intent(incarnation, units=3), plan=plan(win))
    assert funded.row["amount_reserved"] == PRICE * 3
    new = service(world, price=PRICE * 10)   # a later H-1 price: never touches an admitted operation
    assert new.settle(funded.row["operation_id"], 2) == "settled"
    row = new.repository.get(funded.row["operation_id"])
    assert (row["settled_units"], row["settled_amount"]) == (2, PRICE * 2)
    assert world.balance(incarnation)["posted"] == 100 - PRICE * 2 and world.balance(incarnation)["reserved"] == 0
    no_drift(world)


def test_a_credits_operation_served_by_a_free_or_local_rung_still_charges(world):
    """H-3: credits pay for metered work. The service has no notion of which rung served: a result is settled."""
    incarnation, _ = credits(world, units=100)
    svc = service(world)
    win = window(limit=1)
    exhaust(world, svc, incarnation, win)
    for _ in range(3):   # the reusable-credit loop: allowance exhausted -> credits -> served free -> ...
        funded = svc.admit(intent(incarnation), plan=plan(win))
        assert funded.row["source"] == "credits"
        assert svc.settle(funded.row["operation_id"], 1) == "settled"
    assert world.balance(incarnation)["posted"] == 100 - 3 * PRICE
    no_drift(world)


def test_settle_and_release_are_idempotent_and_never_charge_twice(world):
    incarnation, _ = credits(world, units=100)
    svc = service(world)
    win = window(limit=1)
    exhaust(world, svc, incarnation, win)
    funded = svc.admit(intent(incarnation, units=2), plan=plan(win))
    op = funded.row["operation_id"]
    assert svc.settle(op, 2) == "settled"
    assert svc.settle(op, 2) == "settled" and svc.release(op) == "settled"
    assert world.balance(incarnation)["posted"] == 100 - 2 * PRICE
    released = svc.admit(intent(incarnation), plan=plan(win))
    assert svc.release(released.row["operation_id"]) == "released"
    assert svc.settle(released.row["operation_id"], 1) == "released"
    assert svc.settle(svc.admit(intent(incarnation), plan=plan(win)).row["operation_id"], 0) == "released"
    assert world.balance(incarnation)["reserved"] == 0
    no_drift(world)


def test_an_allowance_operation_dispatched_then_released_settles_its_quota_at_zero(world):
    svc = service(world)
    incarnation = world.account()
    win = window(limit=3)
    funded = svc.admit(intent(incarnation, units=2), plan=plan(win))
    op = funded.row["operation_id"]
    assert svc.dispatch(op) == "dispatched" and svc.dispatch(op) == "dispatched"
    assert svc.release(op) == "released"
    reservation = world.sql("SELECT state, actual_units FROM commerce_quota_reservations WHERE operation_id = :k",
                            k=f"fund:{op}")[0]
    assert dict(reservation) == {"state": "settled", "actual_units": 0}


# ---- the live check (§2.1) ------------------------------------------------------------------------------------------

def test_the_live_check_follows_the_durable_state(world):
    incarnation, _ = credits(world, units=100)
    svc = service(world)
    win = window(limit=1)
    allowance = svc.admit(intent(incarnation), plan=plan(win))
    digest = intent(incarnation, op=allowance.row["operation_id"]).request_digest
    op = allowance.row["operation_id"]
    assert svc.live(op, request_digest=digest, meter="writing.review", min_hold_seconds=30) is None
    assert svc.live(op, request_digest="0" * 64, meter="writing.review", min_hold_seconds=30) == "digest_mismatch"
    assert svc.live(op, request_digest=digest, meter="orena.message", min_hold_seconds=30) == "meter_mismatch"
    svc.settle(op, 1)
    assert svc.live(op, request_digest=digest, meter="writing.review", min_hold_seconds=30) == "admission_settled"
    held = svc.admit(intent(incarnation), plan=plan(win))
    held_digest = intent(incarnation, op=held.row["operation_id"]).request_digest
    hop = held.row["operation_id"]
    assert svc.live(hop, request_digest=held_digest, meter="writing.review", min_hold_seconds=60) is None
    assert svc.live(hop, request_digest=held_digest, meter="writing.review", min_hold_seconds=601) == "hold_expiring"
    world.repository.expire_reserve(incarnation, reserve_entry_id=held.row["credit_reserve_entry_id"])
    assert svc.live(hop, request_digest=held_digest, meter="writing.review", min_hold_seconds=1) == "hold_closed"
    assert svc.live("q1:none", request_digest=held_digest, meter="writing.review", min_hold_seconds=1) == "no_admission"


# ---- reconciliation (§5.6 crash table) ----------------------------------------------------------------------------------

def test_the_reconciler_completes_closed_backings_and_refuses_only_unbacked_rows(world):
    incarnation, account = credits(world, units=100)
    svc = service(world)
    win = window(limit=1)
    exhaust(world, svc, incarnation, win)
    expired = svc.admit(intent(incarnation), plan=plan(win))
    world.repository.expire_reserve(incarnation, reserve_entry_id=expired.row["credit_reserve_entry_id"])
    later = datetime.now(UTC) + timedelta(hours=1)
    # a row left `admitting` by a crash (a two-phase leftover), with and without an exact backing
    unbacked = _admitting(world, incarnation)
    adoptable = _admitting(world, incarnation)
    from tests.test_funding_admission_migration_postgres import hold

    hold(world, account, f"fund:{adoptable}", PRICE * 1, meter="writing.review", ref="review-1")
    stray_op = _admitting(world, incarnation)
    stray = hold(world, account, f"fund:{stray_op}", PRICE, meter="orena.message", ref="review-1")
    result = svc.reconcile(now=later)
    assert svc.repository.get(expired.row["operation_id"])["state"] == "released"
    assert svc.repository.get(unbacked)["state"] == "refused"
    assert svc.repository.get(adoptable)["state"] == "admitting"   # never orphaned: the retry adopts it
    assert svc.repository.get(stray_op)["state"] == "refused"
    assert result["conflict_opened"] == 1 and "conflict_resolved" not in result
    world.repository.release(incarnation, reserve_entry_id=stray, operation_id="release-stray")
    assert svc.reconcile(now=later)["conflict_resolved"] == 1
    retried = svc.admit(intent(incarnation, op=adoptable), plan=plan(win))
    assert retried.funded and retried.row["source"] == "credits"   # the exact hold was adopted, not duplicated
    assert counts(world, adoptable)["holds"] == 1
    no_drift(world)


def _admitting(world, incarnation):
    op = f"q1:{uuid.uuid4().hex}"
    probe = intent(incarnation, op=op)
    world.sql("INSERT INTO funding_admissions (id, operation_id, incarnation_id, meter, units, operation_ref, feature, "
              "unit_granularity, request_digest, state, created_at) VALUES (gen_random_uuid(), :op, :inc, :meter, 1, "
              ":ref, 'test', 1, :d, 'admitting', now())", engine=world.runtime,
              op=op, inc=incarnation, meter=probe.meter, ref=probe.operation_ref, d=probe.request_digest)
    return op


def test_a_deleted_account_is_never_admitted(world):
    from writing_coach.billing.funding import AccountDeleted

    svc = service(world)
    incarnation = world.account()
    world.delete(incarnation)
    with pytest.raises(Exception) as caught:
        svc.admit(intent(incarnation), plan=plan(window(limit=5)))
    assert isinstance(caught.value, AccountDeleted) or "deleted account is never admitted" in str(caught.value)


def test_one_bad_reconciler_row_never_stops_the_rest(world, monkeypatch):
    """Formal review P2: a corrupt or failing row is logged and skipped; a repairable row after it is still repaired."""
    incarnation, _ = credits(world, units=100)
    svc = service(world)
    win = window(limit=1)
    exhaust(world, svc, incarnation, win)
    first = svc.admit(intent(incarnation), plan=plan(win))
    second = svc.admit(intent(incarnation), plan=plan(win))
    for funded in (first, second):
        world.repository.expire_reserve(incarnation, reserve_entry_id=funded.row["credit_reserve_entry_id"])
    real = svc.repository.complete_from_backing

    def flaky(operation_id):
        if operation_id == first.row["operation_id"]:
            raise RuntimeError("corrupt row")
        return real(operation_id)

    monkeypatch.setattr(svc.repository, "complete_from_backing", flaky)
    counts = svc.reconcile(now=datetime.now(UTC) + timedelta(hours=1))
    assert counts.get("complete_failed") == 1 and counts.get("completed_released") == 1
    assert svc.repository.get(first.row["operation_id"])["state"] == "funded"
    assert svc.repository.get(second.row["operation_id"])["state"] == "released"
    no_drift(world)
