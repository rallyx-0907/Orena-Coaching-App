"""PR-MON-3 on PostgreSQL (`ORENA_TEST_POSTGRES_URL`): the proposed 0031 (constraints, triggers, downgrade guard),
the four design P1s end to end, idempotency between a webhook and a lookup, crash repair and rate limiting.

Each test runs in its own schema at the Alembic head plus the proposed 0027 and 0031, on a throwaway database
only. The payOS lookup is a fake; no provider is called."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import pytest

from tests.test_billing import BILLING_BASE, CHECKSUM, PAYOS, ROOT, _proposed
from writing_coach.billing.gateway import hmac_sha256_hex
from writing_coach.billing.payos import signing_string

URL = os.getenv("ORENA_TEST_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")

T0 = datetime(2026, 10, 14, 9, tzinfo=UTC)
AMOUNT = 99_000


def link(order_code):
    return f"plink-{order_code}"  # each order has its own payment link (the reference index is unique)


def payos_body(*, order, amount=AMOUNT, reference="FT9", payment_link=None) -> bytes:
    """A signed payOS payment webhook for one order and its own link."""
    import json

    data = {"orderCode": order, "amount": amount, "description": f"OR{order}", "accountNumber": "123",
            "reference": reference, "transactionDateTime": "2026-10-14 09:00:00", "currency": "VND",
            "paymentLinkId": payment_link or link(order), "code": "00", "desc": "success", "counterAccountName": None}
    signature = hmac_sha256_hex(CHECKSUM, signing_string(data).encode())
    return json.dumps({"code": "00", "desc": "success", "success": True, "data": data, "signature": signature}).encode()


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now


@pytest.fixture
def world():
    pytest.importorskip("alembic")
    from alembic import command
    from alembic.config import Config
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine, text

    from writing_coach.billing.reconciler import BillingReconciler, PostgresTickLock
    from writing_coach.billing.service import BillingService
    from writing_coach.persistence.billing_reconciliation_repository import PostgresReconciliationRepository
    from writing_coach.persistence.billing_repository import PostgresBillingRepository
    from writing_coach.persistence.commerce_repository import PostgresCommerceRepository

    schema = f"recon_{uuid.uuid4().hex[:10]}"
    app_name = f"orena-{schema}"
    separator = "&" if "?" in URL else "?"
    schema_url = f"{URL}{separator}options={quote(f'-csearch_path={schema}')}"
    admin = create_engine(URL, future=True)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("path_separator", "os")
    cfg.set_main_option("sqlalchemy.url", schema_url.replace("%", "%%"))
    command.upgrade(cfg, BILLING_BASE)
    engine = create_engine(schema_url, future=True, connect_args={"application_name": app_name})
    migrations = [_proposed("20261005_0027_billing_orders"), _proposed("20261014_0031_billing_reconciliation")]
    with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        for migration in migrations:
            migration.upgrade()

    clock = Clock()
    orders = PostgresBillingRepository(engine)
    commerce = PostgresCommerceRepository(engine)
    items = PostgresReconciliationRepository(engine)
    service = BillingService(orders=orders, commerce=commerce, gateways={"payos": PAYOS}, prices={}, now=clock,
                             reconciliation=items)  # fmt: skip
    answers: dict[int, object] = {}

    def lookup(order_code):
        answer = answers.get(order_code)
        if callable(answer):
            return answer(order_code)
        if isinstance(answer, BaseException):
            raise answer
        if answer is None:
            raise TimeoutError("no answer")
        return answer

    def reconciler(**overrides):
        values = dict(service=service, orders=orders, items=items, lock=PostgresTickLock(engine),
                      lookups={"payos": lookup}, now=clock)  # fmt: skip
        values.update(overrides)
        return BillingReconciler(**values)

    def account(status="active"):
        user, incarnation = uuid.uuid4(), uuid.uuid4()
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO users (id, user_key, email, name, picture, role, created_at) "
                                    "VALUES (:id, :key, '', '', '', 'user', :now)"),
                               {"id": user, "key": f"sub-{user}", "now": T0})
            connection.execute(text("INSERT INTO account_incarnations (id, user_id, epoch, status, created_at) "
                                    "VALUES (:id, :user, 1, 'active', :now)"), {"id": incarnation, "user": user, "now": T0})
        if status == "deleted":
            with engine.begin() as connection:
                connection.execute(text("UPDATE account_incarnations SET status = 'deleted', deleted_at = :now "
                                        "WHERE id = :id"), {"now": T0, "id": incarnation})
        return str(incarnation)

    def order(incarnation, *, created=None):
        made = orders.create_order(operation_id=str(uuid.uuid4()), incarnation_id=incarnation, gateway="payos",
                                   plan_id="plus", period="month", currency="VND", amount_minor=AMOUNT)
        when = created or clock.now
        with engine.begin() as connection:
            connection.execute(text("UPDATE billing_orders SET created_at = :at, expires_at = :at + interval '30 minutes', "
                                    "state = 'pending', external_reference = :link WHERE id = :id"),
                               {"at": when, "id": made["id"], "link": link(made["order_code"])})
        return orders.order(order_code=int(made["order_code"]))

    def row(sql, **values):
        with engine.connect() as connection:
            return connection.execute(text(sql), values).mappings().first()

    yield type("World", (), dict(engine=engine, admin=admin, schema=schema, app_name=app_name, clock=clock,
                                 orders=orders, commerce=commerce, items=items, service=service, answers=answers,
                                 reconciler=staticmethod(reconciler), account=staticmethod(account),
                                 order=staticmethod(order), row=staticmethod(row), migrations=migrations,
                                 text=staticmethod(text), Operations=Operations,
                                 MigrationContext=MigrationContext))  # fmt: skip
    engine.dispose()
    with admin.begin() as connection:
        connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    admin.dispose()


def paid_answer(order_code, *, status="PAID", paid=AMOUNT, reference="FT9"):
    from writing_coach.billing.payos import parse_lookup

    return parse_lookup({"code": "00", "data": {"id": link(order_code), "orderCode": order_code, "amount": AMOUNT,
                                                "amountPaid": paid, "status": status,
                                                "transactions": [{"reference": reference}] if reference else []}})


def access(world, incarnation):
    return world.commerce.get_subscription(incarnation)


# ---- the migration ----------------------------------------------------------------------------------------

def test_the_migration_goes_down_only_while_empty_and_up_again(world):
    def down():
        with world.engine.begin() as connection, world.Operations.context(world.MigrationContext.configure(connection)):
            world.migrations[1].downgrade()

    def up():
        with world.engine.begin() as connection, world.Operations.context(world.MigrationContext.configure(connection)):
            world.migrations[1].upgrade()

    down()
    up()
    world.order(world.account())
    with pytest.raises(RuntimeError, match="financial records"):
        down()
    assert world.row("SELECT COUNT(*) AS n FROM billing_orders")["n"] == 1


def test_the_proposed_0028_still_applies_on_top(world):
    reading = _proposed("20261005_0028_reading_derived_texts")
    with world.engine.begin() as connection, world.Operations.context(world.MigrationContext.configure(connection)):
        reading.upgrade()
        reading.downgrade()


def test_orders_and_items_are_never_deleted(world):
    from sqlalchemy.exc import DBAPIError

    placed = world.order(world.account())
    world.items.record(kind="event_undecided", gateway="polar", dedupe_key="evt-1")
    for statement in ("DELETE FROM billing_orders WHERE id = :id", "DELETE FROM billing_reconciliation_items"):
        with pytest.raises(DBAPIError, match="never deleted"):
            with world.engine.begin() as connection:
                connection.execute(world.text(statement), {"id": placed["id"]})


def test_the_database_enforces_the_safety_critical_resolution_rules(world):
    from sqlalchemy.exc import DBAPIError

    def update(sql, item_id):
        with world.engine.begin() as connection:
            connection.execute(world.text(sql), {"id": item_id, "now": T0})

    unsynced = world.items.record(kind="entitlement_unsynced", gateway="payos", dedupe_key="inc:1")
    money = world.items.record(kind="paid_deleted_account", gateway="payos", dedupe_key="100001",
                               reported_order_code=100001)
    refused = {
        "an administrator resolving paid-without-access":
            ("UPDATE billing_reconciliation_items SET state = 'resolved', resolution_outcome = 'entitlement_synced', "
             "resolved_by = 'admin-1', resolved_at = :now WHERE id = :id", unsynced["id"]),
        "dismissing a money item":
            ("UPDATE billing_reconciliation_items SET state = 'dismissed', resolved_by = 'admin-1', resolved_at = :now "
             "WHERE id = :id", money["id"]),
        "resolving a money item without an outcome":
            ("UPDATE billing_reconciliation_items SET state = 'resolved', resolved_by = 'admin-1', resolved_at = :now "
             "WHERE id = :id", money["id"]),
        "waiving without a reason":
            ("UPDATE billing_reconciliation_items SET state = 'resolved', resolution_outcome = 'obligation_waived', "
             "resolved_by = 'admin-1', resolved_at = :now WHERE id = :id", money["id"]),
        "rewriting a provider fact":
            ("UPDATE billing_reconciliation_items SET reported_order_code = 1 WHERE id = :id", money["id"]),
    }
    for name, (sql, item_id) in refused.items():
        with pytest.raises(DBAPIError):
            update(sql, item_id)
        assert world.row("SELECT state FROM billing_reconciliation_items WHERE id = :id", id=item_id)["state"] == "open", name


def test_a_resolved_item_only_counts_repeats_and_only_a_critical_one_reopens(world):
    from sqlalchemy.exc import DBAPIError

    undecided = world.items.record(kind="event_undecided", gateway="polar", dedupe_key="evt-9")
    world.items.resolve(undecided["id"], resolution="dismissed", outcome=None, reference=None, note="test event",
                        actor="admin-1")  # fmt: skip
    again = world.items.record(kind="event_undecided", gateway="polar", dedupe_key="evt-9")
    assert again["state"] == "dismissed" and again["occurrences"] == 2
    with pytest.raises(DBAPIError):
        with world.engine.begin() as connection:
            connection.execute(world.text("UPDATE billing_reconciliation_items SET state = 'open', resolved_at = NULL, "
                                          "reopened = reopened + 1 WHERE id = :id"), {"id": undecided["id"]})

    placed = world.order(world.account())  # the reconciler always names the order payOS reported paid
    critical = world.items.record(kind="provider_paid_unrecorded", gateway="payos", dedupe_key="100002",
                                  billing_order_id=placed["id"])
    world.items.resolve(critical["id"], resolution="resolved", outcome="refund_confirmed", reference="FT77",
                        note="returned by transfer", actor="admin-1")  # fmt: skip
    seen_again = world.items.record(kind="provider_paid_unrecorded", gateway="payos", dedupe_key="100002")
    assert (seen_again["state"], seen_again["reopened"], seen_again["resolution_outcome"]) == ("open", 1, None)


# ---- P1-1: a payment for an order Orena never issued --------------------------------------------------------

def test_a_payment_for_an_unknown_order_code_is_kept_with_the_code_the_provider_reported(world, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from writing_coach import billing_api

    app = FastAPI()
    app.include_router(billing_api.router)
    monkeypatch.setattr(billing_api, "_service", world.service)
    client = TestClient(app)
    first = client.post("/api/billing/webhooks/payos", content=payos_body(order=987654))
    assert first.status_code == 200 and first.json()["status"] == "unknown_order"
    item = world.row("SELECT * FROM billing_reconciliation_items WHERE kind = 'payment_unknown_order'")
    assert item["reported_order_code"] == 987654 and item["billing_order_id"] is None and item["occurrences"] == 1
    assert client.post("/api/billing/webhooks/payos", content=payos_body(order=987654)).status_code == 200
    assert world.row("SELECT occurrences FROM billing_reconciliation_items WHERE id = :id", id=item["id"])["occurrences"] == 2


# ---- P1-2: local expiry never stops the search ---------------------------------------------------------------

def test_a_payment_whose_webhook_was_lost_is_found_after_the_order_expired(world):
    from writing_coach.billing.reconciler import RateLimited

    incarnation = world.account()
    placed = world.order(incarnation)
    code = int(placed["order_code"])
    reconciler = world.reconciler()
    world.clock.now = T0 + timedelta(minutes=29)
    world.answers[code] = RateLimited(None)  # the last lookup before expiry fails
    assert reconciler.tick()["rate_limited"] == 1
    world.clock.now = T0 + timedelta(minutes=45)
    assert reconciler.tick()["expired"] == 1
    assert world.orders.order(order_code=code)["state"] == "expired"
    world.answers[code] = paid_answer(code)
    world.clock.now = T0 + timedelta(hours=7)
    counts = reconciler.tick()
    assert counts["paid_recovered"] == 1
    settled = world.orders.order(order_code=code)
    assert settled["state"] == "paid" and settled["provider_settled_at"] is not None and settled["paid_reference"] == "FT9"
    assert access(world, incarnation)["state"] == "active"  # granted with no webhook at all
    assert world.items.summary()["open"] == 0


@pytest.mark.parametrize("status", ["EXPIRED", "PENDING", "PROCESSING", "SOMETHING_NEW"])
def test_a_non_terminal_or_undocumented_answer_keeps_the_order_in_the_pull_set(world, status):
    placed = world.order(world.account())
    code = int(placed["order_code"])
    world.answers[code] = paid_answer(code, status=status, paid=0, reference=None)
    world.clock.now = T0 + timedelta(hours=1)
    world.reconciler().tick()
    after = world.orders.order(order_code=code)
    assert after["provider_settled_at"] is None and after["next_lookup_at"] > world.clock.now
    unresolved = world.items.items(kind="provider_state_unresolved")
    assert len(unresolved) == (0 if status in {"PENDING", "PROCESSING"} else 1)


def test_past_the_horizon_an_item_opens_and_the_order_is_still_asked_daily(world):
    placed = world.order(world.account(), created=T0 - timedelta(days=20))
    code = int(placed["order_code"])
    world.answers[code] = paid_answer(code, status="PENDING", paid=0, reference=None)
    world.reconciler().tick()
    after = world.orders.order(order_code=code)
    assert after["next_lookup_at"] == T0 + timedelta(days=1) and after["provider_settled_at"] is None
    assert world.items.items(kind="provider_state_unresolved")[0]["reason"].startswith("no terminal payOS answer")


def test_cancelled_with_nothing_paid_settles_the_order(world):
    placed = world.order(world.account())
    code = int(placed["order_code"])
    world.answers[code] = paid_answer(code, status="CANCELLED", paid=0, reference=None)
    world.clock.now = T0 + timedelta(hours=1)
    world.reconciler().tick()
    after = world.orders.order(order_code=code)
    assert after["state"] == "cancelled" and after["provider_settled_at"] is not None


def test_a_rate_limit_stops_the_step_opens_no_item_and_honours_the_wait(world):
    from writing_coach.billing.reconciler import RateLimited

    first, second = world.order(world.account()), world.order(world.account())
    for placed in (first, second):
        world.answers[int(placed["order_code"])] = RateLimited(900)
    world.clock.now = T0 + timedelta(hours=1)
    counts = world.reconciler().tick()
    assert counts["rate_limited"] == 1 and counts.get("looked_up", 0) == 0
    asked = [world.orders.order(order_code=int(placed["order_code"])) for placed in (first, second)]
    assert sorted(o["provider_status"] or "" for o in asked) == ["", "RATE_LIMITED"]
    limited = next(o for o in asked if o["provider_status"] == "RATE_LIMITED")
    assert limited["next_lookup_at"] == world.clock.now + timedelta(seconds=900)
    assert world.items.summary()["open"] == 0


# ---- P1-3: paid without access is critical until it is really repaired ---------------------------------------

class FailingCommerce:
    """The commerce record, failing to record access while `failing` is set (a crash between the two writes)."""

    def __init__(self, inner):
        self.inner = inner
        self.failing = True

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def record_event(self, **kwargs):
        if self.failing:
            raise RuntimeError("the access write failed")
        return self.inner.record_event(**kwargs)


def test_paid_without_access_blocks_its_gateway_until_the_reconciler_repairs_it(world, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from writing_coach import billing_api
    from writing_coach.billing.service import BillingService
    from writing_coach.persistence.billing_reconciliation_repository import ResolutionRefused

    commerce = FailingCommerce(world.commerce)
    service = BillingService(orders=world.orders, commerce=commerce, gateways={"payos": PAYOS}, prices={},
                             now=world.clock, reconciliation=world.items)  # fmt: skip
    incarnation = world.account()
    placed = world.order(incarnation)
    code = int(placed["order_code"])

    # The webhook: mark_paid commits, the access write fails -> 503, so payOS may deliver it again.
    app = FastAPI()
    app.include_router(billing_api.router)
    monkeypatch.setattr(billing_api, "_service", service)
    answer = TestClient(app).post("/api/billing/webhooks/payos", content=payos_body(order=code, amount=AMOUNT))
    assert answer.status_code == 503
    assert world.orders.order(order_code=code)["state"] == "paid" and access(world, incarnation) is None

    # No redelivery. The repair fails too, so the gap is recorded as critical and closes payOS checkouts.
    reconciler = world.reconciler(service=service, lookups={})
    assert reconciler.tick()["entitlement_unsynced"] == 1
    [item] = world.items.open_items(kind="entitlement_unsynced")
    assert service.critical_by_gateway() == {"payos": 1}
    assert service.gateway_report()["payos"]["reconciliation_critical"] == 1
    with pytest.raises(ResolutionRefused):
        world.items.resolve(item["id"], resolution="resolved", outcome="entitlement_synced", reference=None,
                            note="looks fine", actor="admin-1")  # fmt: skip

    # The access write works again: the next tick repairs the gap and closes the item itself.
    commerce.failing = False
    counts = reconciler.tick()
    assert counts["gap_repaired"] == 1 and counts["entitlement_synced"] == 1
    assert access(world, incarnation)["state"] == "active"
    closed = world.row("SELECT state, resolution_outcome, resolved_by FROM billing_reconciliation_items WHERE id = :id",
                       id=item["id"])  # fmt: skip
    assert dict(closed) == {"state": "resolved", "resolution_outcome": "entitlement_synced", "resolved_by": "reconciler"}
    assert service.critical_by_gateway() == {}


def test_a_gap_that_a_single_repair_closes_opens_no_item(world):
    incarnation = world.account()
    placed = world.order(incarnation)
    world.orders.mark_paid(order_code=int(placed["order_code"]), event_id="evt", amount_minor=AMOUNT, currency="VND")
    counts = world.reconciler(lookups={}).tick()
    assert counts["gap_repaired"] == 1 and counts.get("entitlement_unsynced", 0) == 0
    assert access(world, incarnation)["state"] == "active"


def test_payos_says_paid_but_orena_cannot_record_it_is_critical_until_recorded(world):
    incarnation = world.account()
    placed = world.order(incarnation)
    code = int(placed["order_code"])
    with world.engine.begin() as connection:  # a state mark_paid refuses: the payment cannot be recorded
        connection.execute(world.text("UPDATE billing_orders SET external_reference = 'another-link' WHERE id = :id"),
                           {"id": placed["id"]})
    world.answers[code] = paid_answer(code)
    world.clock.now = T0 + timedelta(hours=1)
    counts = world.reconciler().tick()
    assert counts["paid_unrecorded"] == 1
    assert world.service.critical_by_gateway() == {"payos": 1}
    assert world.orders.order(order_code=code)["provider_settled_at"] is None  # still asked


# ---- P1-4: one tick at a time, no transaction across the provider call ----------------------------------------

def test_one_tick_at_a_time_and_the_lock_is_released_after_an_error(world):
    from writing_coach.billing.reconciler import PostgresTickLock

    with PostgresTickLock(world.engine)() as held:
        assert held.held
        assert world.reconciler().tick() is None  # another process holds the tick
    broken = world.reconciler(lookups={"payos": lambda code: (_ for _ in ()).throw(RuntimeError("boom"))})
    world.order(world.account())
    world.clock.now = T0 + timedelta(hours=1)
    assert broken.tick()["lookup_failed"] == 1
    with PostgresTickLock(world.engine)() as again:
        assert again.held


def test_no_transaction_or_row_lock_is_open_while_payos_is_called(world):
    placed = world.order(world.account())
    code = int(placed["order_code"])
    seen = {}

    def observe(order_code):
        with world.admin.connect() as connection:
            seen["open"] = connection.execute(world.text(
                "SELECT COUNT(*) FROM pg_stat_activity WHERE application_name = :app "
                "AND state IN ('idle in transaction', 'idle in transaction (aborted)', 'active')"),
                {"app": world.app_name}).scalar()
            seen["row_locks"] = connection.execute(world.text(
                "SELECT COUNT(*) FROM pg_locks l JOIN pg_class c ON c.oid = l.relation "
                "JOIN pg_namespace n ON n.oid = c.relnamespace JOIN pg_stat_activity a ON a.pid = l.pid "
                "WHERE n.nspname = :schema AND a.application_name = :app AND l.mode <> 'AccessShareLock'"),
                {"schema": world.schema, "app": world.app_name}).scalar()
            seen["advisory"] = connection.execute(world.text(
                "SELECT COUNT(*) FROM pg_locks l JOIN pg_stat_activity a ON a.pid = l.pid "
                "WHERE l.locktype = 'advisory' AND a.application_name = :app"), {"app": world.app_name}).scalar()
        return paid_answer(order_code)

    world.answers[code] = observe
    world.clock.now = T0 + timedelta(hours=1)
    world.reconciler().tick()
    assert seen == {"open": 0, "row_locks": 0, "advisory": 1}  # only the session lock, held on an idle connection


def test_a_lost_lock_connection_stops_the_tick(world):
    from sqlalchemy import text

    placed = [world.order(world.account()) for _ in range(3)]

    def kill_lock(order_code):
        with world.admin.begin() as connection:
            connection.execute(text(
                "SELECT pg_terminate_backend(l.pid) FROM pg_locks l JOIN pg_stat_activity a ON a.pid = l.pid "
                "WHERE l.locktype = 'advisory' AND a.application_name = :app"), {"app": world.app_name})
        return paid_answer(order_code, status="PENDING", paid=0, reference=None)

    for order in placed:
        world.answers[int(order["order_code"])] = kill_lock
    world.clock.now = T0 + timedelta(hours=1)
    counts = world.reconciler().tick()
    assert counts["lock_lost"] >= 1 and counts["looked_up"] == 1


# ---- idempotency between the webhook and the lookup ---------------------------------------------------------

def test_webhook_then_lookup_and_lookup_then_webhook_are_one_payment(world):
    first_account, second_account = world.account(), world.account()
    by_webhook, by_lookup = world.order(first_account), world.order(second_account)
    webhook_code, lookup_code = int(by_webhook["order_code"]), int(by_lookup["order_code"])

    assert world.service.handle_webhook("payos", {}, payos_body(order=webhook_code, amount=AMOUNT)).status == "apply"
    assert world.orders.order(order_code=webhook_code)["next_lookup_at"] is not None  # one confirming lookup due
    world.answers[webhook_code] = paid_answer(webhook_code)
    world.answers[lookup_code] = paid_answer(lookup_code)
    world.clock.now = T0 + timedelta(hours=1)
    counts = world.reconciler().tick()
    assert counts["paid_confirmed"] == 1 and counts["paid_recovered"] == 1
    late = world.service.handle_webhook("payos", {}, payos_body(order=lookup_code, amount=AMOUNT))
    assert late.status in {"duplicate", "stale"}
    for code in (webhook_code, lookup_code):
        assert world.row("SELECT COUNT(*) AS n FROM billing_orders WHERE order_code = :c AND paid_sequence IS NOT NULL",
                         c=code)["n"] == 1  # fmt: skip
        assert world.orders.order(order_code=code)["provider_settled_at"] is not None
    assert access(world, first_account)["object_version"] == 1 and access(world, second_account)["object_version"] == 1
    assert world.items.summary()["open"] == 0


def test_a_second_payment_with_its_own_reference_is_kept_as_an_anomaly(world):
    placed = world.order(world.account())
    code = int(placed["order_code"])
    world.orders.mark_paid(order_code=code, event_id="evt-1", amount_minor=AMOUNT, currency="VND", paid_reference="FT1")
    outcome = world.service.record_payment(order_code=code, gateway="payos", event_id="evt-2", amount_minor=AMOUNT,
                                           currency="VND", paid_reference="FT2")  # fmt: skip
    assert outcome.status == "not_payable"
    assert [item["kind"] for item in world.items.items(state="open")] == ["payment_not_payable"]


def test_the_confirming_lookup_finds_an_overpayment(world):
    placed = world.order(world.account())
    code = int(placed["order_code"])
    world.service.handle_webhook("payos", {}, payos_body(order=code, amount=AMOUNT))
    world.answers[code] = paid_answer(code, paid=2 * AMOUNT, reference=None)
    world.clock.now = T0 + timedelta(hours=1)
    assert world.reconciler().tick()["payment_mismatch"] == 1
    [item] = world.items.items(kind="payment_mismatch")
    assert item["reported_amount_minor"] == 2 * AMOUNT and str(item["billing_order_id"]) == str(placed["id"])
    assert world.orders.order(order_code=code)["provider_settled_at"] is not None


def test_a_payment_for_a_deleted_account_is_kept_as_a_refund_owed(world):
    incarnation = world.account(status="deleted")
    placed = world.order(incarnation)
    code = int(placed["order_code"])
    assert world.service.handle_webhook("payos", {}, payos_body(order=code, amount=AMOUNT)).status == "paid_deleted_account"
    [owed] = world.items.items(kind="paid_deleted_account")
    assert str(owed["incarnation_id"]) == incarnation and owed["state"] == "open"
    assert world.reconciler(lookups={}).tick().get("entitlement_unsynced", 0) == 0  # not an access gap: no access owed


# ---- implementation review P1s (2026-10-14) -------------------------------------------------------------------

class FlakyItems:
    """The reconciliation items, failing the first `failures` records (the database refused the write)."""

    def __init__(self, inner, failures=1):
        self.inner = inner
        self.failures = failures

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def record(self, **kwargs):
        if self.failures:
            self.failures -= 1
            raise RuntimeError("the item write failed")
        return self.inner.record(**kwargs)


def webhook_client(monkeypatch, service):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from writing_coach import billing_api

    app = FastAPI()
    app.include_router(billing_api.router)
    monkeypatch.setattr(billing_api, "_service", service)
    return TestClient(app)


def test_p1_1_a_refund_owed_for_a_deleted_account_survives_a_failed_first_record(world, monkeypatch):
    from writing_coach.billing.service import BillingService

    service = BillingService(orders=world.orders, commerce=world.commerce, gateways={"payos": PAYOS}, prices={},
                             now=world.clock, reconciliation=FlakyItems(world.items))  # fmt: skip
    incarnation = world.account(status="deleted")
    code = int(world.order(incarnation)["order_code"])
    client = webhook_client(monkeypatch, service)
    assert client.post("/api/billing/webhooks/payos", content=payos_body(order=code)).status_code == 503
    assert world.orders.order(order_code=code)["state"] == "paid" and world.items.items() == []
    retried = client.post("/api/billing/webhooks/payos", content=payos_body(order=code))  # the same event again
    assert retried.status_code == 200 and retried.json()["status"] == "paid_deleted_account"
    [owed] = world.items.items(kind="paid_deleted_account")
    assert owed["reported_order_code"] == code and str(owed["incarnation_id"]) == incarnation
    again = client.post("/api/billing/webhooks/payos", content=payos_body(order=code))
    assert again.json()["status"] == "paid_deleted_account"
    assert world.items.items(kind="paid_deleted_account")[0]["occurrences"] == 2  # stable, never a second item


def test_p1_1_a_payment_made_before_the_account_was_deleted_owes_no_refund_on_redelivery(world):
    incarnation = world.account()
    code = int(world.order(incarnation)["order_code"])
    assert world.service.handle_webhook("payos", {}, payos_body(order=code)).status == "apply"
    with world.engine.begin() as connection:
        connection.execute(world.text("UPDATE account_incarnations SET status = 'deleted', deleted_at = :at "
                                      "WHERE id = :id"), {"at": T0 + timedelta(days=1), "id": incarnation})
    assert world.service.handle_webhook("payos", {}, payos_body(order=code)).status != "paid_deleted_account"
    assert world.items.items(kind="paid_deleted_account") == []


def unrecordable_paid(world):
    """payOS reports PAID for an order Orena cannot record (another payment link): a critical item opens."""
    placed = world.order(world.account())
    code = int(placed["order_code"])
    with world.engine.begin() as connection:
        connection.execute(world.text("UPDATE billing_orders SET external_reference = 'another-link' WHERE id = :id"),
                           {"id": placed["id"]})
    world.answers[code] = paid_answer(code)
    world.clock.now = T0 + timedelta(hours=1)
    assert world.reconciler().tick()["paid_unrecorded"] == 1
    [item] = world.items.open_items(kind="provider_paid_unrecorded")
    return placed, code, item


def test_p1_2_payment_recorded_is_the_reconcilers_statement_and_needs_the_paid_order(world):
    from sqlalchemy.exc import DBAPIError

    from writing_coach.persistence.billing_reconciliation_repository import ResolutionRefused

    placed, code, item = unrecordable_paid(world)
    with pytest.raises(ResolutionRefused) as refused:
        world.items.resolve(item["id"], resolution="resolved", outcome="payment_recorded", reference="FT9",
                            note="I think it is recorded", actor="admin-1")  # fmt: skip
    assert refused.value.code == "outcome_not_allowed"
    with pytest.raises(DBAPIError):  # an administrator's write around the repository is refused too
        with world.engine.begin() as connection:
            connection.execute(world.text(
                "UPDATE billing_reconciliation_items SET state = 'resolved', resolution_outcome = 'payment_recorded', "
                "resolved_by = 'admin-1', resolved_at = :now WHERE id = :id"), {"now": T0, "id": item["id"]})
    with pytest.raises(DBAPIError, match="payment_recorded needs the order"):  # the reconciler, order unpaid
        world.items.auto_resolve(kind="provider_paid_unrecorded", gateway="payos", dedupe_key=str(code),
                                 outcome="payment_recorded", note="not yet", now=T0)  # fmt: skip
    assert world.items.open_items(kind="provider_paid_unrecorded")[0]["id"] == item["id"]


def test_p1_2_a_confirmed_refund_settles_the_order_so_the_next_paid_lookup_does_not_reopen_it(world):
    placed, code, item = unrecordable_paid(world)
    world.items.resolve(item["id"], resolution="resolved", outcome="refund_confirmed", reference="FT-RETURN-1",
                        note="returned to the payer by bank transfer", actor="admin-1")  # fmt: skip
    after = world.orders.order(order_code=code)
    assert after["provider_settled_at"] is not None and after["next_lookup_at"] is None
    world.clock.now = T0 + timedelta(days=2)  # past any backoff; payOS still says PAID
    counts = world.reconciler().tick()
    assert counts.get("looked_up", 0) == 0 and counts.get("paid_unrecorded", 0) == 0
    closed = world.row("SELECT state, reopened, resolution_outcome FROM billing_reconciliation_items WHERE id = :id",
                       id=item["id"])  # fmt: skip
    assert dict(closed) == {"state": "resolved", "reopened": 0, "resolution_outcome": "refund_confirmed"}
    assert world.service.critical_by_gateway() == {}


def test_p1_3_a_webhook_during_the_lookup_is_never_overwritten_by_cancelled(world):
    incarnation = world.account()
    code = int(world.order(incarnation)["order_code"])

    def webhook_then_cancelled(order_code):
        # while payOS is being asked, the webhook arrives and records the payment
        assert world.service.handle_webhook("payos", {}, payos_body(order=order_code)).status == "apply"
        return paid_answer(order_code, status="CANCELLED", paid=0, reference=None)

    world.answers[code] = webhook_then_cancelled
    world.clock.now = T0 + timedelta(hours=1)
    counts = world.reconciler().tick()
    after = world.orders.order(order_code=code)
    assert after["state"] == "paid" and after["provider_settled_at"] is None  # not settled as CANCELLED
    assert counts.get("cancelled", 0) == 0 and access(world, incarnation)["state"] == "active"
    assert world.items.items(kind="provider_state_unresolved")[0]["reason"].startswith("payOS reports cancelled")


def test_p1_3_a_refund_before_the_confirming_lookup_keeps_that_lookup(world):
    placed = world.order(world.account())
    code = int(placed["order_code"])
    assert world.service.handle_webhook("payos", {}, payos_body(order=code)).status == "apply"
    assert world.service.record_refund(order_code=code, note="returned by transfer").status == "apply"
    assert world.orders.order(order_code=code)["state"] == "refunded"
    world.answers[code] = paid_answer(code, paid=2 * AMOUNT, reference=None)  # a second transfer was made
    world.clock.now = T0 + timedelta(hours=1)
    assert world.reconciler().tick()["payment_mismatch"] == 1
    assert world.orders.order(order_code=code)["provider_settled_at"] is not None
    [item] = world.items.items(kind="payment_mismatch")
    assert item["reported_amount_minor"] == 2 * AMOUNT


def test_p1_3_a_refunded_order_confirmed_paid_is_settled_without_a_false_anomaly(world):
    placed = world.order(world.account())
    code = int(placed["order_code"])
    world.service.handle_webhook("payos", {}, payos_body(order=code))
    world.service.record_refund(order_code=code, note="returned by transfer")
    world.answers[code] = paid_answer(code)
    world.clock.now = T0 + timedelta(hours=1)
    assert world.reconciler().tick()["paid_confirmed"] == 1
    assert world.orders.order(order_code=code)["provider_settled_at"] is not None
    assert world.items.summary()["open"] == 0


def test_p1_3_a_payment_and_refund_during_the_lookup_are_decided_on_the_order_as_it_is_now(world):
    """While payOS is asked, the webhook records the payment and an operator refunds it. payOS then says PAID: the
    lookup must see the refunded order - not the pending snapshot taken before the call - and raise no anomaly."""
    code = int(world.order(world.account())["order_code"])

    def paid_and_refunded_meanwhile(order_code):
        assert world.service.handle_webhook("payos", {}, payos_body(order=order_code)).status == "apply"
        assert world.service.record_refund(order_code=order_code, note="returned by transfer").status == "apply"
        return paid_answer(order_code)

    world.answers[code] = paid_and_refunded_meanwhile
    world.clock.now = T0 + timedelta(hours=1)
    counts = world.reconciler().tick()
    assert counts["paid_confirmed"] == 1 and counts.get("paid_recovered", 0) == 0
    assert world.orders.order(order_code=code)["state"] == "refunded"
    assert world.orders.order(order_code=code)["provider_settled_at"] is not None
    assert world.items.summary()["open"] == 0  # no false "second payment" for the refunded order


def test_p1_2_a_disposition_made_during_the_lookup_is_not_undone_by_its_stale_answer(world):
    """Focused re-review: provider_paid_unrecorded is open; the reconciler claims the order and asks payOS; while it
    waits, an administrator resolves the item as refunded (settling the order); payOS then answers PAID. The stale
    answer reopens nothing, raises no new anomaly, and leaves the order settled and the gateway open."""
    placed, code, item = unrecordable_paid(world)

    def refunded_meanwhile(order_code):
        world.items.resolve(item["id"], resolution="resolved", outcome="refund_confirmed", reference="FT-RETURN-2",
                            note="returned to the payer by bank transfer", actor="admin-1")  # fmt: skip
        return paid_answer(order_code)

    world.answers[code] = refunded_meanwhile
    world.clock.now = T0 + timedelta(hours=8)  # past the first item's backoff, so the order is asked again
    counts = world.reconciler().tick()
    assert counts["stale_lookup"] == 1 and counts.get("paid_unrecorded", 0) == 0
    closed = world.row("SELECT state, reopened, resolution_outcome FROM billing_reconciliation_items WHERE id = :id",
                       id=item["id"])  # fmt: skip
    assert dict(closed) == {"state": "resolved", "reopened": 0, "resolution_outcome": "refund_confirmed"}
    assert world.service.critical_by_gateway() == {}
    assert world.orders.order(order_code=code)["provider_settled_at"] is not None
    kinds = [row["kind"] for row in world.items.items()]
    assert kinds.count("payment_mismatch") == 1 and "payment_not_payable" not in kinds  # only the first tick's
