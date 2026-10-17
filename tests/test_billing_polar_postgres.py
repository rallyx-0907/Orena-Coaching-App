"""PR-MON-10 §4.8 on PostgreSQL (`ORENA_TEST_POSTGRES_URL`, throwaway database only): the derived Polar customer
clean-up obligation against the real `account_incarnations` and `platform_settings` (compare-and-set). Polar itself
is a recorded fake; nothing is called."""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta

import pytest

from tests.test_billing import POLAR
from tests.test_credit_ledger_postgres import URL, ledger_world
from tests.test_credit_topup_migration_postgres import ALL
from writing_coach.billing.polar_cleanup import PolarCustomerCleanup, PostgresDeletedIncarnations, marker_key

pytestmark = pytest.mark.skipif(not URL, reason="ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")


@pytest.fixture
def world():
    from writing_coach.persistence.platform_repository import PostgresPlatformRepository

    for ledger in ledger_world(ALL):
        ledger.settings = PostgresPlatformRepository(ledger.runtime)
        ledger.deleted = PostgresDeletedIncarnations(ledger.runtime)
        yield ledger


def worker(world, *answers, now=None):
    calls = []
    queue = list(answers)

    def call(request):
        calls.append(request["url"])
        return queue.pop(0) if len(queue) > 1 else queue[0]

    cleanup = PolarCustomerCleanup(gateway=POLAR, incarnations=world.deleted, settings=world.settings,
                                   items=world.items, call=call,
                                   now=now or (lambda: datetime.now(UTC)))  # fmt: skip
    return cleanup, calls


def reregister(world, incarnation):
    """A new incarnation (epoch 2) of the same account, as `register_new` allocates it."""

    user = world.sql("SELECT user_id FROM account_incarnations WHERE id = :i", i=incarnation)[0]["user_id"]
    new = uuid.uuid4()
    world.sql("INSERT INTO account_incarnations (id, user_id, epoch, status, created_at) "
              "VALUES (:id, :user, 2, 'active', :now)", id=new, user=user, now=datetime.now(UTC))
    return str(new)


def test_every_deleted_incarnation_is_an_obligation_with_no_polar_evidence_at_all(world):
    """The restore gap (review P1 of b99715c4): a backup from before the Polar checkout holds no Polar order and no
    mapping; the journal reapplies the deletion; the clean-up must still call DELETE."""

    live, gone = world.account(), world.account()
    world.delete(gone)
    assert world.sql("SELECT COUNT(*) AS n FROM billing_orders")[0]["n"] == 0   # no Polar evidence anywhere
    now = datetime.now(UTC)
    assert world.deleted.due(now, 10) == [gone] and live not in world.deleted.due(now, 10)
    cleanup, calls = worker(world, 204)
    counts = Counter()
    cleanup.step(counts)
    assert counts["polar_cleanup_complete"] == 1
    assert calls == [f"https://sandbox-api.polar.sh/v1/customers/external/{gone}?anonymize=true"]
    assert world.settings.get_setting(marker_key(gone))["value"]["state"] == "complete"
    assert world.deleted.due(now, 10) == [] and world.deleted.counts(now)["pending"] == 0


def test_a_lost_marker_brings_the_obligation_back_and_404_completes_it(world):
    gone = world.account()
    world.delete(gone)
    cleanup, calls = worker(world, 204, 404)
    assert cleanup.clean(gone) == "complete"
    world.sql("DELETE FROM platform_settings WHERE key = :k", k=marker_key(gone))   # a restore to before completion
    assert world.deleted.due(datetime.now(UTC), 10) == [gone]
    assert cleanup.clean(gone) == "complete" and len(calls) == 2


def test_a_back_off_hides_an_obligation_until_it_is_due_and_the_bound_counts_it_escalated(world):
    gone = world.account()
    world.delete(gone)
    start = datetime.now(UTC)
    cleanup, _ = worker(world, 500, now=lambda: start)
    assert cleanup.clean(gone) == "pending"
    assert world.deleted.due(start, 10) == []
    assert world.deleted.due(start + timedelta(hours=7), 10) == [gone]
    assert world.deleted.counts(start)["escalated"] == 0
    assert world.deleted.counts(start + timedelta(hours=25)) == {"pending": 1, "escalated": 1}


def test_a_re_registration_sees_only_its_own_predecessors_obligation(world):
    old, other = world.account(), world.account()
    world.delete(old)
    world.delete(other)
    new = reregister(world, old)
    assert world.deleted.pending_of_same_account(new) == [old]
    cleanup, calls = worker(world, 204)
    assert cleanup.settle_account_of(new) is True and len(calls) == 1
    assert world.deleted.pending_of_same_account(new) == []
    assert world.deleted.due(datetime.now(UTC), 10) == [other]   # another account's obligation is untouched


def test_two_writers_of_one_marker_cannot_both_complete_it(world):
    """Compare-and-set: the second writer from the same version is refused and writes nothing."""

    from writing_coach.persistence.platform_repository import SettingConflict

    gone = world.account()
    world.delete(gone)
    world.settings.set_setting(marker_key(gone), {"state": "pending", "attempts": 1}, updated_by="a",
                               expected_updated_at=None)
    version = world.settings.get_setting(marker_key(gone))["updated_at"]
    world.settings.set_setting(marker_key(gone), {"state": "complete"}, updated_by="a", expected_updated_at=version)
    with pytest.raises(SettingConflict):
        world.settings.set_setting(marker_key(gone), {"state": "pending"}, updated_by="b", expected_updated_at=version)


def test_order_paid_evidence_is_one_terminal_receipt_and_never_an_access_change(world):
    """Review P1-1 of fdb613b0: a durable, idempotent receipt; the subscription record is untouched."""

    from writing_coach.persistence.commerce_repository import PostgresCommerceRepository

    commerce = PostgresCommerceRepository(world.runtime)
    owner = world.account()
    before = world.sql("SELECT COUNT(*) AS n FROM commerce_subscriptions")[0]["n"]
    first = commerce.record_evidence(incarnation_id=owner, provider="polar", external_event_id="msg_ord_1",
                                     external_object_reference="ord_1", payload_digest="d1", note="evidence order.paid")
    assert first["status"] == "recorded"
    again = commerce.record_evidence(incarnation_id=owner, provider="polar", external_event_id="msg_ord_1",
                                     external_object_reference="ord_1", payload_digest="d1", note="evidence order.paid")
    assert again["status"] == "duplicate"
    other = commerce.record_evidence(incarnation_id=owner, provider="polar", external_event_id="msg_ord_1",
                                     external_object_reference="ord_1", payload_digest="d2", note="evidence order.paid")
    assert other["status"] == "payload_conflict"
    [row] = world.sql("SELECT processing_state, incarnation_id::text AS inc, external_object_reference AS ref "
                      "FROM commerce_billing_event_receipts WHERE provider = 'polar' AND external_event_id = 'msg_ord_1'")
    assert (row["processing_state"], row["inc"], row["ref"]) == ("ignored", owner, "ord_1")
    assert world.sql("SELECT COUNT(*) AS n FROM commerce_subscriptions")[0]["n"] == before
    missing = commerce.record_evidence(incarnation_id=str(uuid.uuid4()), provider="polar", external_event_id="msg_x",
                                       external_object_reference=None, payload_digest=None, note="evidence")
    assert missing["status"] == "rejected"


def test_an_order_paid_after_deletion_is_one_open_paid_deleted_account_item_and_no_access_change(world):
    """Review P1 of 06675882 on PostgreSQL: deleted A, Orena's own checkout order for A, Polar's renewal charge
    arrives - one receipt, one open `paid_deleted_account` item with the amount, the subscription untouched, and a
    redelivery changes nothing."""

    from tests.test_billing import polar_request
    from writing_coach.billing.gateway import Price
    from writing_coach.billing.service import BillingService
    from writing_coach.persistence.commerce_repository import PostgresCommerceRepository

    owner = world.account()
    world.delete(owner)

    class Orders:
        def order(self, *, order_code=None, operation_id=None):
            return {"incarnation_id": owner, "gateway": "polar", "plan_id": "plus"} if operation_id == "op-A" else None

    price = Price(plan_id="plus", period="month", currency="USD", amount_minor=999, gateway="polar",
                  external_price_id="prod_plus")
    billing = BillingService(orders=Orders(), commerce=PostgresCommerceRepository(world.runtime),
                             gateways={"polar": POLAR}, prices={"plus:month:polar": price},
                             reconciliation=world.items)  # fmt: skip
    event = {"type": "order.paid", "data": {
        "id": "ord_after_delete", "status": "paid", "billing_reason": "subscription_cycle", "subscription_id": "",
        "total_amount": 999, "currency": "usd", "product_id": "prod_plus",
        "metadata": {"orena_incarnation": owner, "orena_operation": "op-A", "orena_plan": "plus"}}}
    before = world.sql("SELECT COUNT(*) AS n FROM commerce_subscriptions")[0]["n"]
    headers, body = polar_request(event, at=datetime.now(UTC))
    assert billing.handle_webhook("polar", headers, body).status == "paid_deleted_account"
    headers, body = polar_request(event, at=datetime.now(UTC))
    assert billing.handle_webhook("polar", headers, body).status == "paid_deleted_account"
    items = world.sql("SELECT kind, state, reported_amount_minor AS amount, reported_currency AS currency, "
                      "incarnation_id::text AS inc FROM billing_reconciliation_items WHERE kind = 'paid_deleted_account'")
    assert [dict(item) for item in items] == [{"kind": "paid_deleted_account", "state": "open", "amount": 999,
                                               "currency": "USD", "inc": owner}]
    receipts = world.sql("SELECT processing_state FROM commerce_billing_event_receipts WHERE provider = 'polar'")
    assert [r["processing_state"] for r in receipts] == ["ignored"]
    assert world.sql("SELECT COUNT(*) AS n FROM commerce_subscriptions")[0]["n"] == before


def test_the_operation_journal_sends_at_most_one_patch_under_real_cas_and_threads(world):
    """PR-MON-9 §4.2.1 on PostgreSQL: a stale `pending` claimed by two workers at once -> exactly one PATCH; a stale
    `sent` -> reads only; retention deletes only this module's keys."""

    import threading

    from tests.test_billing_polar_subscription import OP, Commerce, Polar, crash_after, subs
    from writing_coach.billing.polar_subscription import LEASE, OP_PREFIX, PostgresOperationIndex

    polar = Polar()
    later = datetime.now(UTC) + LEASE + timedelta(seconds=5)
    workers = [subs(polar, Commerce(), settings=world.settings, clock=lambda: later)[0] for _ in range(4)]
    crash_after(workers[0], "pending", datetime.now(UTC))
    barrier = threading.Barrier(len(workers))

    def claim(worker):
        barrier.wait()
        worker.change("inc-1", "pro:month:polar", OP)

    threads = [threading.Thread(target=claim, args=(w,)) for w in workers]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(polar.patches) == 1
    state = world.settings.get_setting(OP_PREFIX + OP)["value"]["state"]
    assert state == "done"

    # RUNBOOK_R-MON-014 §2 grants the runtime DELETE on ordinary tables (platform_settings included; revoked only on
    # the financial ones). The shared fixture grants less; give exactly the runbook's grant for this table.
    world.sql(f'GRANT DELETE ON platform_settings TO "{world.role}"')
    index = PostgresOperationIndex(world.runtime)
    world.settings.set_setting("billing.sepay.feed_cursor", {"since_id": 1}, expected_updated_at=None)
    assert index.keys(OP_PREFIX) == [OP_PREFIX + OP]
    index.delete(OP_PREFIX + OP)
    assert world.settings.get_setting(OP_PREFIX + OP) is None
    with pytest.raises(ValueError):
        index.delete("billing.sepay.feed_cursor")   # never another module's key
    assert world.settings.get_setting("billing.sepay.feed_cursor") is not None
