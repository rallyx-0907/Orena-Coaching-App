"""Billing (completion plan item 4): gateway signatures, prepaid periods, the service's decisions, the routes off,
and - with `ORENA_TEST_POSTGRES_URL` - the order table and the commerce record end to end on PostgreSQL."""

from __future__ import annotations

import base64
import importlib.util
import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from writing_coach.billing.gateway import CheckoutIntent, Price, WebhookRejected, hmac_sha256_hex
from writing_coach.billing.payos import PayOSGateway, signing_string
from writing_coach.billing.polar import PolarGateway, sign
from writing_coach.billing.prepaid import add_period, extended_until
from writing_coach.billing.service import BillingService, load_prices

NOW = datetime(2026, 10, 5, 12, tzinfo=UTC)
CHECKSUM = "checksum-for-tests"
POLAR_KEY = b"0123456789abcdef0123456789abcdef"
POLAR_SECRET = "whsec_" + base64.b64encode(POLAR_KEY).decode()
PAYOS = PayOSGateway(client_id="client", api_key="key", checksum_key=CHECKSUM)
POLAR = PolarGateway(access_token="token", webhook_secret=POLAR_SECRET)
VND_MONTH = Price(plan_id="premium", period="month", currency="VND", amount_minor=99_000, gateway="payos")
USD_MONTH = Price(plan_id="premium", period="month", currency="USD", amount_minor=499, gateway="polar",
                  external_price_id="prod_123")  # fmt: skip


def payos_body(*, order=100001, amount=99_000, code="00", key=CHECKSUM, tamper=False) -> bytes:
    data = {"orderCode": order, "amount": amount, "description": "OR100001", "accountNumber": "123", "reference": "FT9",
            "transactionDateTime": "2026-10-05 12:00:00", "currency": "VND", "paymentLinkId": "plink", "code": code,
            "desc": "success", "counterAccountName": None}  # fmt: skip
    signature = hmac_sha256_hex(key, signing_string(data).encode())
    if tamper:
        data["amount"] = 1
    return json.dumps({"code": code, "desc": "success", "success": code == "00", "data": data, "signature": signature}).encode()


def polar_request(event: dict, *, at: datetime = NOW, key: bytes = POLAR_KEY) -> tuple[dict, bytes]:
    body = json.dumps(event).encode()
    stamp = str(int(at.timestamp()))
    return {"webhook-id": "msg_1", "webhook-timestamp": stamp, "webhook-signature": sign(key, "msg_1", stamp, body)}, body


def subscription_event(status="active", *, metadata=None, modified="2026-10-05T11:00:00Z") -> dict:
    return {"type": "subscription.updated", "data": {
        "id": "sub_1", "status": status, "modified_at": modified, "current_period_end": "2026-11-05T11:00:00Z",
        "cancel_at_period_end": False, "customer_id": "cus_1",
        "metadata": metadata if metadata is not None else {"orena_incarnation": "inc-1", "orena_plan": "premium",
                                                            "orena_operation": "op-1"}}}  # fmt: skip


# ---- payOS -------------------------------------------------------------------------------------------------

def test_payos_a_signed_payment_is_a_payment_of_its_order():
    fact = PAYOS.verify({}, payos_body())
    assert (fact.kind, fact.external_reference, fact.amount_minor, fact.currency) == ("payment", "100001", 99_000, "VND")


@pytest.mark.parametrize("body", [payos_body(tamper=True), payos_body(key="another-key"), b"not json", b"{}"])
def test_payos_an_unsigned_or_altered_webhook_is_rejected(body):
    with pytest.raises(WebhookRejected):
        PAYOS.verify({}, body)


def test_payos_a_failed_payment_is_not_a_payment():
    assert PAYOS.verify({}, payos_body(code="01")).kind == "ignored"


def test_payos_payment_request_is_signed_over_its_five_fields():
    intent = CheckoutIntent(operation_id=str(uuid.uuid4()), incarnation_id="inc", price=VND_MONTH,
                            return_url="https://o/r", cancel_url="https://o/c")  # fmt: skip
    request = PAYOS.checkout_request(intent, order_code=100001, description="OR100001")
    body = request["json"]
    expected = hmac_sha256_hex(CHECKSUM, b"amount=99000&cancelUrl=https://o/c&description=OR100001&orderCode=100001&returnUrl=https://o/r")
    assert body["signature"] == expected and request["headers"]["x-client-id"] == "client"


# ---- Polar -------------------------------------------------------------------------------------------------

def test_polar_a_signed_subscription_event_carries_its_state_and_revision():
    headers, body = polar_request(subscription_event())
    fact = POLAR.verify(headers, body, now=NOW)
    assert (fact.kind, fact.state, fact.plan_id, fact.external_reference, fact.incarnation_hint) == (
        "subscription", "active", "premium", "sub_1", "inc-1")
    assert fact.object_version == int(datetime(2026, 10, 5, 11, tzinfo=UTC).timestamp() * 1_000_000)
    assert fact.paid_through == datetime(2026, 11, 5, 11, tzinfo=UTC)


def test_polar_a_secret_used_as_its_own_bytes_still_verifies():
    headers, body = polar_request(subscription_event(), key=POLAR_SECRET.encode())
    assert POLAR.verify(headers, body, now=NOW).kind == "subscription"


@pytest.mark.parametrize("case", ["wrong_key", "stale", "missing", "tampered"])
def test_polar_an_unsigned_stale_or_altered_webhook_is_rejected(case):
    headers, body = polar_request(subscription_event(), key=b"x" * 32 if case == "wrong_key" else POLAR_KEY,
                                  at=NOW - timedelta(minutes=6) if case == "stale" else NOW)  # fmt: skip
    if case == "missing":
        headers.pop("webhook-signature")
    if case == "tampered":
        body = body.replace(b"active", b"trialing")
    with pytest.raises(WebhookRejected):
        POLAR.verify(headers, body, now=NOW)


@pytest.mark.parametrize(("status", "state"), [("canceled", "ended"), ("past_due", "past_due"), ("weird", "unknown")])
def test_polar_states_map_explicitly(status, state):
    headers, body = polar_request(subscription_event(status))
    assert POLAR.verify(headers, body, now=NOW).state == state


def test_polar_checkout_carries_orenas_account_plan_and_operation():
    intent = CheckoutIntent(operation_id="op-1", incarnation_id="inc-1", price=USD_MONTH, return_url="https://o/r",
                            cancel_url="https://o/c")  # fmt: skip
    body = POLAR.checkout_request(intent)["json"]
    assert body["products"] == ["prod_123"]
    assert body["metadata"] == {"orena_incarnation": "inc-1", "orena_plan": "premium", "orena_operation": "op-1"}


# ---- prepaid periods ---------------------------------------------------------------------------------------

def test_a_month_is_a_calendar_month_clamped_to_the_last_day():
    assert add_period(datetime(2026, 1, 31, tzinfo=UTC), "month") == datetime(2026, 2, 28, tzinfo=UTC)
    assert add_period(datetime(2026, 12, 15, tzinfo=UTC), "month") == datetime(2027, 1, 15, tzinfo=UTC)
    assert add_period(datetime(2028, 2, 29, tzinfo=UTC), "year") == datetime(2029, 2, 28, tzinfo=UTC)


def test_a_payment_extends_from_the_end_while_access_lasts_and_from_now_after():
    assert extended_until(NOW + timedelta(days=10), NOW, "month") == add_period(NOW + timedelta(days=10), "month")
    assert extended_until(NOW - timedelta(days=10), NOW, "month") == add_period(NOW, "month")
    assert extended_until(None, NOW, "year") == add_period(NOW, "year")


def test_prices_come_only_from_the_approved_file(tmp_path):
    assert load_prices({}) == {}
    path = tmp_path / "prices.json"
    path.write_text(json.dumps([{"plan_id": "premium", "period": "month", "currency": "vnd", "amount_minor": 99000,
                                 "gateway": "payos"}]))  # fmt: skip
    assert load_prices({"BILLING_PRICES_FILE": str(path)})["premium:month:payos"].currency == "VND"
    path.write_text(json.dumps([{"plan_id": "p", "period": "month", "currency": "USD", "amount_minor": 4.99, "gateway": "polar"}]))
    with pytest.raises(ValueError):
        load_prices({"BILLING_PRICES_FILE": str(path)})


# ---- the service's decisions -------------------------------------------------------------------------------

class FakeOrders:
    def __init__(self):
        self.orders = {"op-1": {"id": 1, "operation_id": "op-1", "incarnation_id": "inc-1", "gateway": "polar", "order_code": 100001,
                                "plan_id": "premium"}}
        self.paid: list = []

    def order(self, *, order_code=None, operation_id=None):
        return self.orders.get(operation_id) if operation_id else None

    def mark_paid(self, **kwargs):
        self.paid.append(kwargs)
        return {"status": "applied" if kwargs["amount_minor"] == 99_000 else "mismatch", "incarnation_id": "inc-1"}

    def prepaid_state(self, incarnation_id, gateway):
        return {"paid_through": NOW + timedelta(days=31), "plan_id": "premium", "version": len(self.paid)}


class FakeCommerce:
    def __init__(self, mapped=None):
        self.events: list = []
        self.mapped = mapped

    def get_provider_subscription(self, provider, external_id):
        return self.mapped

    def record_event(self, **kwargs):
        self.events.append(kwargs)
        return {"status": "apply"}


def service(commerce=None, orders=None):
    return BillingService(orders=orders or FakeOrders(), commerce=commerce or FakeCommerce(),
                          gateways={"payos": PAYOS, "polar": POLAR}, prices={}, now=lambda: NOW)  # fmt: skip


def test_a_first_subscription_event_attaches_only_to_an_account_orenas_checkout_named():
    commerce = FakeCommerce()
    headers, body = polar_request(subscription_event())
    assert service(commerce).handle_webhook("polar", headers, body).status == "apply"
    assert commerce.events[0]["incarnation_id"] == "inc-1"
    stranger = subscription_event(metadata={"orena_incarnation": "inc-2", "orena_operation": "op-1"})
    headers, body = polar_request(stranger)
    commerce = FakeCommerce()
    assert service(commerce).handle_webhook("polar", headers, body).status == "unknown" and commerce.events == []


def test_a_known_subscription_follows_its_stored_owner_not_the_metadata():
    commerce = FakeCommerce(mapped={"incarnation_id": "inc-owner"})
    headers, body = polar_request(subscription_event(metadata={"orena_incarnation": "inc-2"}))
    service(commerce).handle_webhook("polar", headers, body)
    assert commerce.events[0]["incarnation_id"] == "inc-owner"


def test_a_paid_order_records_the_prepaid_state_replayed_from_orders():
    commerce, orders = FakeCommerce(), FakeOrders()
    assert service(commerce, orders).handle_webhook("payos", {}, payos_body()).status == "apply"
    event = commerce.events[0]
    assert event["update"].external_subscription_id == "prepaid:inc-1" and event["update"].state == "active"
    assert event["event_object_version"] == 1 and event["update"].cancel_at_period_end is True


def test_a_payment_of_the_wrong_amount_changes_no_access():
    commerce = FakeCommerce()
    assert service(commerce).handle_webhook("payos", {}, payos_body(amount=1_000)).status in {"rejected", "mismatch"}
    assert commerce.events == []


def test_a_rejected_webhook_changes_nothing():
    commerce, orders = FakeCommerce(), FakeOrders()
    assert service(commerce, orders).handle_webhook("payos", {}, payos_body(tamper=True)).status == "rejected"
    assert commerce.events == [] and orders.paid == []


# ---- the routes, off --------------------------------------------------------------------------------------

def test_billing_is_off_by_default():
    import app as app_module

    client = TestClient(app_module.app)
    assert client.get("/api/billing/offers").json() == {"enabled": False, "offers": []}
    assert client.post("/api/billing/webhooks/payos", content=payos_body()).status_code == 503
    checkout = client.post("/api/billing/checkout", json={"price": "premium:month:payos", "operation_id": str(uuid.uuid4())})
    assert checkout.status_code == 503


# ---- PostgreSQL: orders, prepaid access and the commerce record ---------------------------------------------

URL = os.getenv("ORENA_TEST_POSTGRES_URL", "")
ROOT = Path(__file__).resolve().parents[1]


def _proposed(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "migrations" / "proposed" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(not URL, reason="ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")
def test_postgres_prepaid_orders_extend_refund_and_record_access():
    pytest.importorskip("alembic")
    from alembic import command
    from alembic.config import Config
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine, text

    from writing_coach.persistence.billing_repository import PostgresBillingRepository
    from writing_coach.persistence.commerce_repository import PostgresCommerceRepository

    schema = f"billing_{uuid.uuid4().hex[:10]}"
    separator = "&" if "?" in URL else "?"
    schema_url = f"{URL}{separator}options={quote(f'-csearch_path={schema}')}"
    admin = create_engine(URL, future=True)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        cfg = Config(str(ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(ROOT / "migrations"))
        cfg.set_main_option("path_separator", "os")
        cfg.set_main_option("sqlalchemy.url", schema_url.replace("%", "%%"))
        command.upgrade(cfg, "head")
        engine = create_engine(schema_url, future=True)
        migrations = [_proposed("20261005_0026_ai_cost_records"), _proposed("20261005_0027_billing_orders")]
        try:
            with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
                for migration in migrations:
                    migration.upgrade()
            user, incarnation = uuid.uuid4(), uuid.uuid4()
            with engine.begin() as connection:
                connection.execute(text("INSERT INTO users (id, user_key, email, name, picture, role, created_at) "
                                        "VALUES (:id, 'sub-pay', '', '', '', 'user', :now)"), {"id": user, "now": NOW})
                connection.execute(text("INSERT INTO account_incarnations (id, user_id, epoch, status, created_at) "
                                        "VALUES (:id, :user, 1, 'active', :now)"), {"id": incarnation, "user": user, "now": NOW})
            orders = PostgresBillingRepository(engine)
            commerce = PostgresCommerceRepository(engine)
            clock = [NOW]
            billing = BillingService(orders=orders, commerce=commerce, gateways={"payos": PAYOS}, prices={},
                                     now=lambda: clock[0])  # fmt: skip

            def order(operation):
                return orders.create_order(operation_id=operation, incarnation_id=str(incarnation), gateway="payos",
                                           plan_id="premium", period="month", currency="VND", amount_minor=99_000)

            first = order("op-a")
            assert order("op-a")["order_code"] == first["order_code"]  # a retried checkout is the same order
            assert orders.create_order(operation_id="op-a", incarnation_id=str(incarnation), gateway="payos",
                                       plan_id="premium", period="year", currency="VND", amount_minor=99_000)["conflict"]
            second = order("op-b")

            assert billing.handle_webhook("payos", {}, payos_body(order=first["order_code"])).status == "apply"
            assert billing.handle_webhook("payos", {}, payos_body(order=first["order_code"])).status == "duplicate"
            assert billing.handle_webhook("payos", {}, payos_body(order=second["order_code"], amount=5)).status == "mismatch"
            clock[0] = NOW + timedelta(days=3)
            assert billing.handle_webhook("payos", {}, payos_body(order=second["order_code"])).status == "apply"
            current = commerce.get_subscription(str(incarnation))
            assert current["state"] == "active" and current["object_version"] == 2
            assert current["paid_through"] == add_period(add_period(NOW, "month"), "month")  # two months, none lost

            assert billing.record_refund(order_code=first["order_code"], note="returned by transfer").status == "apply"
            current = commerce.get_subscription(str(incarnation))
            assert current["object_version"] == 3
            assert current["paid_through"] == add_period(NOW + timedelta(days=3), "month")  # only the second remains
            # A crash between the refund record and the access record is repaired by recording the refund again.
            assert billing.record_refund(order_code=first["order_code"], note="again").status == "duplicate"
            assert commerce.get_subscription(str(incarnation))["object_version"] == 3

            # A payment that arrives after the account was deleted is accounted for and grants nothing.
            third = order("op-c")
            with engine.begin() as connection:
                connection.execute(text("UPDATE account_incarnations SET status = 'deleted', deleted_at = :now WHERE id = :id"),
                                   {"now": NOW, "id": incarnation})
            assert billing.handle_webhook("payos", {}, payos_body(order=third["order_code"])).status == "paid_deleted_account"
            assert commerce.get_subscription(str(incarnation))["object_version"] == 3
            with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
                for migration in reversed(migrations):
                    migration.downgrade()
        finally:
            engine.dispose()
    finally:
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


# ---- independent review conditions (2026-10-05) -------------------------------------------------------------

def test_the_webhook_path_is_reachable_without_a_session():
    import inspect

    import auth_support

    assert '"/api/billing/webhooks/"' in inspect.getsource(auth_support)


@pytest.mark.parametrize("headers", [
    {"webhook-id": "m", "webhook-timestamp": "99999999999999999999", "webhook-signature": "v1,abc"},
    {"webhook-id": "m", "webhook-timestamp": "²", "webhook-signature": "v1,abc"},
    {"webhook-id": "m", "webhook-timestamp": str(int(NOW.timestamp())), "webhook-signature": "v1,ñ"},
])  # fmt: skip
def test_a_malformed_polar_header_is_a_rejection_not_a_crash(headers):
    with pytest.raises(WebhookRejected):
        POLAR.verify(headers, b"{}", now=NOW)


def test_a_malformed_payos_signature_is_a_rejection_not_a_crash():
    body = json.loads(payos_body())
    body["signature"] = "ñ" * 64
    with pytest.raises(WebhookRejected):
        PAYOS.verify({}, json.dumps(body).encode())


def test_a_period_is_counted_in_utc_whatever_zone_the_database_answers_in():
    from datetime import timezone

    late_evening = datetime(2026, 1, 31, 20, tzinfo=timezone(timedelta(hours=-5)))  # 1 Feb 01:00 UTC
    assert add_period(late_evening, "month") == datetime(2026, 3, 1, 1, tzinfo=UTC)


def test_prices_are_checked_against_what_each_gateway_takes(tmp_path):
    path = tmp_path / "prices.json"
    for wrong in ({"plan_id": "p", "period": "month", "currency": "USD", "amount_minor": 499, "gateway": "payos"},
                  {"plan_id": "p", "period": "month", "currency": "USD", "amount_minor": 499, "gateway": "polar"}):
        path.write_text(json.dumps([wrong]))
        with pytest.raises(ValueError):
            load_prices({"BILLING_PRICES_FILE": str(path)})


class LiveCommerce(FakeCommerce):
    def __init__(self, current):
        super().__init__()
        self.current = current

    def get_subscription(self, incarnation_id):
        return self.current


class CheckoutOrders(FakeOrders):
    def __init__(self, state="created"):
        super().__init__()
        self.state = state

    def create_order(self, **kwargs):
        return {"id": 9, "order_code": 100009, "state": self.state, "conflict": False, **kwargs}

    def set_reference(self, order_id, reference):
        pass


def checkout(commerce, orders, price_key="premium:month:payos"):
    from writing_coach.billing.service import CheckoutRefused

    billing = BillingService(orders=orders, commerce=commerce, gateways={"payos": PAYOS, "polar": POLAR},
                             prices={"premium:month:payos": VND_MONTH, "premium:month:polar": USD_MONTH},
                             send=lambda request: {"data": {"checkoutUrl": "https://pay/x", "paymentLinkId": "plink"}, "id": "chk", "url": "https://pay/y"},
                             now=lambda: NOW)  # fmt: skip
    try:
        return billing.start_checkout(incarnation_id="inc-1", price_key=price_key, operation_id=str(uuid.uuid4()),
                                      return_url="https://o/r", cancel_url="https://o/c")["redirect_url"]
    except CheckoutRefused as refused:
        return refused.code


def test_one_live_subscription_per_account_but_prepaid_access_may_be_renewed():
    card = {"state": "active", "provider": "polar", "external_subscription_id": "sub_1", "paid_through": NOW + timedelta(days=9)}
    prepaid = {"state": "active", "provider": "payos", "external_subscription_id": "prepaid:inc-1", "paid_through": NOW + timedelta(days=9)}
    lapsed = {**card, "paid_through": NOW - timedelta(days=1)}
    assert checkout(LiveCommerce(card), CheckoutOrders()) == "subscription_live"
    assert checkout(LiveCommerce(prepaid), CheckoutOrders(), "premium:month:polar") == "subscription_live"
    assert checkout(LiveCommerce(prepaid), CheckoutOrders()) == "https://pay/x"
    assert checkout(LiveCommerce(lapsed), CheckoutOrders()) == "https://pay/x"


@pytest.mark.parametrize(("state", "code"), [("pending", "checkout_already_started"), ("paid", "order_closed"), ("refunded", "order_closed")])
def test_an_order_already_started_or_closed_never_gets_a_second_link(state, code):
    assert checkout(LiveCommerce(None), CheckoutOrders(state)) == code
