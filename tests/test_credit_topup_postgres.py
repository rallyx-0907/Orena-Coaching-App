"""PR-MON-5 payOS credit top-up, end to end on PostgreSQL (`ORENA_TEST_POSTGRES_URL`, throwaway database only).

The chain is at `20261015_0033`; the credit writes run as the non-superuser runtime member of `orena_credit_runtime`.
Every payment goes through the real `BillingService.record_payment` (the webhook's and the lookup's path), every top-up
through `apply_credit_topup`, every gap through `reconcile_credit_orders`. payOS itself is a fake; nothing is called."""

from __future__ import annotations

import json
import threading
import uuid

import pytest

from tests.test_billing import PAYOS
from tests.test_billing_reconciliation_postgres import payos_body
from tests.test_credit_ledger_postgres import URL, ledger_world, no_drift
from tests.test_credit_topup_migration_postgres import ALL

pytestmark = pytest.mark.skipif(not URL, reason="ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")

PACK = {"pack_id": "starter", "credit_units": 500, "currency": "VND", "amount_minor": 50_000, "gateway": "payos"}


@pytest.fixture
def shop(tmp_path):
    from writing_coach.billing.service import BillingService, load_credit_packs
    from writing_coach.persistence.billing_reconciliation_repository import PostgresReconciliationRepository
    from writing_coach.persistence.billing_repository import PostgresBillingRepository
    from writing_coach.persistence.commerce_repository import PostgresCommerceRepository

    for world in ledger_world(ALL):
        def build(packs=(PACK,), world=world):
            path = tmp_path / f"packs-{uuid.uuid4().hex}.json"
            path.write_text(json.dumps(list(packs)))

            def send(request):
                code = request["json"]["orderCode"]
                return {"data": {"checkoutUrl": "https://pay/x", "paymentLinkId": f"plink-{code}"}}

            return BillingService(orders=PostgresBillingRepository(world.runtime),
                                  commerce=PostgresCommerceRepository(world.runtime), gateways={"payos": PAYOS},
                                  prices={}, reconciliation=PostgresReconciliationRepository(world.runtime),
                                  credit_packs=load_credit_packs({"BILLING_CREDIT_PACKS_FILE": str(path)}),
                                  credits=world.service, send=send)  # fmt: skip

        world.build = staticmethod(build)
        world.billing = build()
        yield world


def checkout(shop, incarnation, *, billing=None, units=500, amount=50_000):
    from writing_coach.billing.service import CheckoutRefused

    try:
        return (billing or shop.billing).start_checkout(
            incarnation_id=incarnation, price_key="credits:starter:payos", operation_id=str(uuid.uuid4()),
            return_url="https://o/r", cancel_url="https://o/c", confirmed_amount_minor=amount,
            confirmed_currency="VND", confirmed_credit_units=units)["order_code"]
    except CheckoutRefused as refused:
        return refused.code


def pay(shop, code, amount=50_000):
    return shop.billing.handle_webhook("payos", {}, payos_body(order=code, amount=amount)).status


def credited(shop, incarnation):
    return shop.balance(incarnation)["posted"]


def gap_items(shop, kind):
    return [dict(r) for r in shop.sql("SELECT * FROM billing_reconciliation_items WHERE kind = :k", k=kind)]


# ---- contracts 1-4: a paid credit-pack order credits exactly once, whichever path recorded it -------------------------

def test_a_paid_pack_credits_once_from_the_webhook_and_the_lookup(shop):
    incarnation = shop.account()
    code = checkout(shop, incarnation)
    order = shop.sql("SELECT product_kind, credit_pack_id, credit_units, plan_id, period FROM billing_orders "
                     "WHERE order_code = :c", c=code)[0]
    assert dict(order) == {"product_kind": "credit_pack", "credit_pack_id": "starter", "credit_units": 500,
                           "plan_id": None, "period": None}
    assert pay(shop, code) == "apply" and credited(shop, incarnation) == 500
    assert pay(shop, code) == "duplicate"  # the webhook again
    lookup = shop.billing.record_payment(order_code=code, gateway="payos", event_id=f"payos:order:{code}",
                                         amount_minor=50_000, currency="VND", payment_link_id=f"plink-{code}",
                                         settled=True)  # fmt: skip
    assert lookup.status == "duplicate" and credited(shop, incarnation) == 500
    assert shop.sql("SELECT count(*) AS n FROM credit_ledger WHERE kind = 'topup'")[0]["n"] == 1
    paid = shop.sql("SELECT paid_sequence, period_end FROM billing_orders WHERE order_code = :c", c=code)[0]
    assert (paid["paid_sequence"], paid["period_end"]) == (None, None)  # never plan access
    assert shop.billing.orders.prepaid_gaps("payos") == []
    no_drift(shop)


def test_the_webhook_and_the_lookup_racing_credit_once(shop):
    incarnation = shop.account()
    code = checkout(shop, incarnation)
    results, barrier = [], threading.Barrier(4)

    def deliver(index):
        barrier.wait()
        if index % 2:
            results.append(pay(shop, code))
        else:
            results.append(shop.billing.record_payment(order_code=code, gateway="payos", event_id=f"payos:order:{code}",
                                                       amount_minor=50_000, currency="VND",
                                                       payment_link_id=f"plink-{code}", settled=True).status)

    threads = [threading.Thread(target=deliver, args=(index,)) for index in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results.count("apply") == 1 and credited(shop, incarnation) == 500
    no_drift(shop)


def test_the_credited_units_are_the_orders_snapshot(shop):
    incarnation = shop.account()
    code = checkout(shop, incarnation)
    shop.billing = shop.build([{**PACK, "credit_units": 900}])  # the packs file changes after checkout
    assert pay(shop, code) == "apply" and credited(shop, incarnation) == 500


# ---- contract 5: what may be bought, and when ------------------------------------------------------------------------

def test_a_pack_is_sold_only_as_configured_confirmed_and_while_credits_are_ready(shop):
    from writing_coach.billing.credits import CreditService
    from writing_coach.persistence.credit_repository import PostgresCreditRepository

    incarnation = shop.account()
    assert [offer["key"] for offer in shop.billing.credit_offers()] == ["credits:starter:payos"]
    assert checkout(shop, incarnation, units=499) == "price_changed"
    assert checkout(shop, incarnation, amount=49_999) == "price_changed"
    with pytest.raises(LookupError):
        checkout(shop, incarnation, billing=shop.build([]))  # no packs, nothing sold
    assert shop.build([]).credit_offers() == []
    privileged = shop.build()
    privileged.attach_credits(CreditService(PostgresCreditRepository(shop.owner)))  # a superuser connection
    assert checkout(shop, incarnation, billing=privileged) == "credits_not_ready" and privileged.credit_offers() == []
    assert shop.sql("SELECT count(*) AS n FROM billing_orders")[0]["n"] == 0  # refused before any order


# ---- contracts 6-7 and §6.1-§6.2: gaps, exact fulfillment, terminal outcomes --------------------------------------------

def test_a_crash_between_payment_and_credit_is_repaired_by_the_reconciler(shop):
    incarnation = shop.account()
    code = checkout(shop, incarnation)
    shop.billing.orders.mark_paid(order_code=code, event_id="evt", amount_minor=50_000, currency="VND",
                                  payment_link_id=f"plink-{code}")  # recorded, never credited (a crash)
    assert credited(shop, incarnation) == 0
    counts = shop.billing.reconcile_credit_orders()
    assert counts["credit_topup_repaired"] == 1 and credited(shop, incarnation) == 500
    assert gap_items(shop, "credit_topup_unapplied") == []


def test_a_conflicting_source_is_never_fulfillment_and_escalates_until_resolved_by_the_exact_topup(shop):
    from tests.test_credit_topup_migration_postgres import topup_sql

    incarnation = shop.account()
    code = checkout(shop, incarnation)
    shop.billing.orders.mark_paid(order_code=code, event_id="evt", amount_minor=50_000, currency="VND",
                                  payment_link_id=f"plink-{code}")
    account = shop.balance(incarnation)["id"]
    topup_sql(shop, account, code, 500, request_digest="0" * 64)  # the right source and units, another intent
    outcome = shop.billing.apply_credit_topup(code)
    assert (outcome.status, outcome.detail) == ("credit_pending", "conflict")
    counts = shop.billing.reconcile_credit_orders()
    assert counts["credit_topup_unapplied"] == 1
    [item] = gap_items(shop, "credit_topup_unapplied")
    assert item["state"] == "open" and item["credit_requested"] == 500
    assert shop.billing.credit_offers() == []  # credit-pack checkout is closed
    assert checkout(shop, shop.account()) == "reconciliation_critical"
    assert "payos" not in shop.billing.critical_by_gateway()  # plan checkout is not


def test_a_refund_before_any_credit_closes_the_gap_as_payment_refunded(shop):
    incarnation = shop.account()
    code = checkout(shop, incarnation)
    shop.billing.orders.mark_paid(order_code=code, event_id="evt", amount_minor=50_000, currency="VND",
                                  payment_link_id=f"plink-{code}")
    with shop.owner.begin() as connection:  # credits stop working for this account: the gap persists
        connection.execute(shop.text("INSERT INTO billing_reconciliation_items (id, kind, gateway, dedupe_key, state, "
                                     "first_seen_at, last_seen_at, credit_account_id, credit_expected_posted, "
                                     "credit_expected_reserved, credit_snapshot_posted, credit_snapshot_reserved) VALUES "
                                     "(gen_random_uuid(), 'credit_balance_drift', 'credits', :k, 'open', now(), now(), "
                                     ":a, 0, 0, 1, 0)"), {"k": str(uuid.uuid4()), "a": shop.balance(incarnation)["id"]})
    assert shop.billing.reconcile_credit_orders()["credit_topup_unapplied"] == 1
    assert shop.billing.record_refund(order_code=code, note="returned by transfer").status == "refunded"
    assert shop.billing.reconcile_credit_orders()["credit_gap_resolved"] == 1
    [item] = gap_items(shop, "credit_topup_unapplied")
    assert (item["state"], item["resolution_outcome"], item["resolved_by"]) == ("resolved", "payment_refunded", "reconciler")
    assert credited(shop, incarnation) == 0  # and never credited afterwards


def test_a_deletion_before_the_credit_moves_the_money_to_the_refund_path(shop):
    incarnation = shop.account()
    code = checkout(shop, incarnation)
    shop.billing.orders.mark_paid(order_code=code, event_id="evt", amount_minor=50_000, currency="VND",
                                  payment_link_id=f"plink-{code}")
    shop.delete(incarnation)
    shop.billing.reconcile_credit_orders()
    [owed] = gap_items(shop, "paid_deleted_account")
    assert owed["dedupe_key"] == str(code) and owed["state"] == "open"  # the refund owed, a money item
    assert gap_items(shop, "credit_topup_unapplied") == [] and credited(shop, incarnation) == 0


# ---- contract 8 and §7.1: refund after the credit ------------------------------------------------------------------------

def test_a_full_refund_reverses_what_it_can_and_records_the_shortfall(shop):
    incarnation = shop.account()
    code = checkout(shop, incarnation)
    assert pay(shop, code) == "apply"
    shop.service.reserve(incarnation, amount=200, operation_id="op", meter="m")  # 200 are held: not reversible
    outcome = shop.billing.record_refund(order_code=code, note="returned by transfer")
    assert outcome.status == "apply"
    request = shop.sql("SELECT requested, applied, shortfall FROM credit_reversal_requests")[0]
    assert dict(request) == {"requested": 500, "applied": 300, "shortfall": 200}
    assert len(gap_items(shop, "credit_reversal_shortfall")) == 1
    assert shop.billing.record_refund(order_code=code, note="again").status == "duplicate"
    assert shop.billing.reconcile_credit_orders()["credit_reversal_unapplied"] == 0
    no_drift(shop)


def test_a_crash_between_refund_and_reversal_is_repaired_and_a_persistent_one_escalates(shop):
    incarnation = shop.account()
    code = checkout(shop, incarnation)
    assert pay(shop, code) == "apply"
    shop.billing.orders.mark_refunded(order_code=code, note="returned")  # recorded; the reversal never ran
    drift_key = str(uuid.uuid4())
    with shop.owner.begin() as connection:  # the account's credit is under review: the reversal cannot run
        connection.execute(shop.text("INSERT INTO billing_reconciliation_items (id, kind, gateway, dedupe_key, state, "
                                     "first_seen_at, last_seen_at, credit_account_id, credit_expected_posted, "
                                     "credit_expected_reserved, credit_snapshot_posted, credit_snapshot_reserved) VALUES "
                                     "(gen_random_uuid(), 'credit_balance_drift', 'credits', :k, 'open', now(), now(), "
                                     ":a, 0, 0, 1, 0)"), {"k": drift_key, "a": shop.balance(incarnation)["id"]})
    assert shop.billing.reconcile_credit_orders()["credit_reversal_unapplied"] == 1
    assert shop.billing.credit_offers() == []
    with shop.owner.begin() as connection:  # the review ends
        connection.execute(shop.text("UPDATE billing_reconciliation_items SET state = 'resolved', resolution_outcome = "
                                     "'balance_consistent', resolved_by = 'reconciler', resolved_at = now() "
                                     "WHERE dedupe_key = :k"), {"k": drift_key})
    counts = shop.billing.reconcile_credit_orders()
    assert counts["credit_reversal_repaired"] == 1 and counts["credit_gap_resolved"] == 1
    [item] = gap_items(shop, "credit_reversal_unapplied")
    assert (item["state"], item["resolution_outcome"]) == ("resolved", "credit_reversed")
    assert credited(shop, incarnation) == 0


# ---- §6.3: refund and top-up serialize through the real repository code --------------------------------------------------

@pytest.mark.parametrize("first", ["refund", "topup"])
def test_refund_and_topup_serialize_through_the_repositories(shop, first):
    incarnation = shop.account()
    code = checkout(shop, incarnation)
    shop.billing.orders.mark_paid(order_code=code, event_id="evt", amount_minor=50_000, currency="VND",
                                  payment_link_id=f"plink-{code}")
    holder = shop.owner.connect() if first == "refund" else shop.runtime.connect()
    transaction = holder.begin()
    outcome = {}

    def second():
        if first == "refund":
            outcome["status"] = shop.billing.credits.apply_credit_topup(code).status
        else:
            outcome["status"] = shop.billing.orders.mark_refunded(order_code=code, note="returned")["status"]

    worker = threading.Thread(target=second, daemon=True)
    try:
        if first == "refund":  # mark_refunded's locks, held: the incarnation, then the order
            holder.execute(shop.text("SELECT 1 FROM account_incarnations WHERE id = :i FOR NO KEY UPDATE"),
                           {"i": incarnation})
            holder.execute(shop.text("UPDATE billing_orders SET state = 'refunded', refunded_at = now(), "
                                     "refunded_by = 'operator' WHERE order_code = :c"), {"c": code})
        else:  # apply_credit_topup's locks, held: the incarnation, then the order (FOR SHARE)
            holder.execute(shop.text("SELECT 1 FROM account_incarnations WHERE id = :i FOR SHARE"), {"i": incarnation})
            holder.execute(shop.text("SELECT 1 FROM billing_orders WHERE order_code = :c FOR SHARE"), {"c": code})
        worker.start()
        worker.join(timeout=2.0)
        waited = worker.is_alive()
        transaction.commit()
    finally:
        if transaction.is_active:
            transaction.rollback()
        holder.close()
    worker.join(timeout=10)
    assert waited, "the second transaction must wait behind the first"
    if first == "refund":
        assert outcome["status"] == "order_refunded" and credited(shop, incarnation) == 0
    else:
        assert outcome["status"] == "applied"
        assert shop.sql("SELECT state FROM billing_orders WHERE order_code = :c", c=code)[0]["state"] == "refunded"
