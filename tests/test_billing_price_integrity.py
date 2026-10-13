"""PR-MON-2: price integrity (D-MON-005, D-MON-015) and truthful runtime readiness, including the startup commerce
discovery that must fail safe when the store is expected but unreadable (R-MON-010, D-MON-016)."""

from __future__ import annotations

import json
import uuid
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from writing_coach.billing import readiness
from writing_coach.billing.gateway import Price
from writing_coach.billing.payos import PayOSGateway
from writing_coach.billing.price_integrity import catalog_amount_minor, check_prices
from writing_coach.billing.service import BillingService, CheckoutRefused, load_prices
from writing_coach.product.catalog import PLANS, PLUS, CatalogUnavailable
from writing_coach.product.entitlement import DiscoveringCommerceSource, table_state

NOW = datetime(2026, 10, 14, 12, tzinfo=UTC)
PAYOS = PayOSGateway(client_id="client", api_key="key", checksum_key="checksum")
# The catalogue's defaults: Plus is 199 000 VND a month and 9.99 USD; Pro is 399 000 VND a month.
PLUS_VND = Price(plan_id="plus", period="month", currency="VND", amount_minor=199_000, gateway="payos")
PRO_VND_YEAR = Price(plan_id="pro", period="year", currency="VND", amount_minor=3_190_000, gateway="payos")


def catalog(**overrides):
    plans = dict(PLANS)
    for plan_id, prices in overrides.items():
        plans[plan_id] = replace(plans[plan_id], prices=prices)
    return lambda: plans


def unreadable():
    raise CatalogUnavailable("store down")


class Orders:
    def __init__(self):
        self.created: list = []

    def create_order(self, **kwargs):
        self.created.append(kwargs)
        return {"id": 1, "order_code": 100001, "state": "created", "conflict": False, **kwargs}

    def set_reference(self, order_id, reference):
        pass


class Commerce:
    def get_subscription(self, incarnation_id):
        return None


def billing(prices, *, plans=None, orders=None, sent=None):
    sent = sent if sent is not None else []

    def send(request):
        sent.append(request)
        return {"data": {"checkoutUrl": "https://pay/x", "paymentLinkId": "plink"}}

    return BillingService(orders=orders or Orders(), commerce=Commerce(), gateways={"payos": PAYOS},
                          prices={f"{p.plan_id}:{p.period}:{p.gateway}": p for p in prices},
                          catalog=plans or catalog(), send=send, now=lambda: NOW)  # fmt: skip


def start(service, key="plus:month:payos", *, amount=199_000, currency="VND"):
    try:
        return service.start_checkout(incarnation_id="inc-1", price_key=key, operation_id=str(uuid.uuid4()),
                                      return_url="https://o/r", cancel_url="https://o/c",
                                      confirmed_amount_minor=amount, confirmed_currency=currency)["redirect_url"]  # fmt: skip
    except CheckoutRefused as refused:
        return refused.code


# ---- the catalogue amount, in minor units -----------------------------------------------------------------

def test_a_catalogue_amount_is_read_in_the_currencys_minor_unit():
    plans = PLANS
    assert catalog_amount_minor(plans, "plus", "month", "VND") == 199_000
    assert catalog_amount_minor(plans, "plus", "month", "USD") == 999
    assert catalog_amount_minor(plans, "pro", "year", "USD") == 15_999
    assert catalog_amount_minor(plans, "plus", "week", "USD") is None
    assert catalog_amount_minor(plans, "plus", "month", "EUR") is None
    assert catalog_amount_minor(plans, "gold", "month", "USD") is None


def test_every_price_is_compared_with_the_catalogue_entry_for_its_plan_period_and_currency():
    wrong = replace(PLUS_VND, amount_minor=99_000)
    checks = check_prices({"a": PLUS_VND, "b": wrong, "c": PRO_VND_YEAR}, PLANS)
    assert [checks[key].status for key in "abc"] == ["match", "mismatch", "match"]
    assert checks["b"].catalog_amount_minor == 199_000 and checks["b"].amount_minor == 99_000


# ---- the approved prices file -----------------------------------------------------------------------------

@pytest.mark.parametrize("item", [
    {"plan_id": "free", "period": "month", "currency": "VND", "amount_minor": 1, "gateway": "payos"},
    {"plan_id": "premium", "period": "month", "currency": "VND", "amount_minor": 399_000, "gateway": "payos"},
    {"plan_id": "gold", "period": "month", "currency": "VND", "amount_minor": 1, "gateway": "payos"},
    {"plan_id": "plus", "period": "month", "currency": "EUR", "amount_minor": 999, "gateway": "polar",
     "external_price_id": "p"},
    {"plan_id": "plus", "period": "month", "currency": "VND", "amount_minor": 1, "gateway": "stripe"},
])
def test_a_prices_file_names_only_a_paid_catalogue_plan_a_catalogue_currency_and_a_known_gateway(tmp_path, item):
    path = tmp_path / "prices.json"
    path.write_text(json.dumps([item]))
    with pytest.raises(ValueError):
        load_prices({"BILLING_PRICES_FILE": str(path)})


def test_a_prices_file_with_the_same_price_twice_is_refused(tmp_path):
    item = {"plan_id": "plus", "period": "month", "currency": "VND", "amount_minor": 199_000, "gateway": "payos"}
    path = tmp_path / "prices.json"
    path.write_text(json.dumps([item, {**item, "amount_minor": 1}]))
    with pytest.raises(ValueError):
        load_prices({"BILLING_PRICES_FILE": str(path)})


# ---- offers and checkout ----------------------------------------------------------------------------------

def test_only_prices_matching_the_catalogue_are_offered():
    assert [offer["key"] for offer in billing([PLUS_VND, PRO_VND_YEAR]).offered()] == [
        "plus:month:payos", "pro:year:payos"]


def test_one_mismatched_price_blocks_every_offer_and_checkout_of_its_gateway():
    sent, orders = [], Orders()
    service = billing([replace(PLUS_VND, amount_minor=99_000), PRO_VND_YEAR], orders=orders, sent=sent)
    assert service.offered() == []
    assert start(service, "pro:year:payos", amount=3_190_000) == "price_mismatch"
    assert start(service, amount=99_000) == "price_mismatch"
    assert orders.created == [] and sent == []


def test_an_administrators_catalogue_change_blocks_checkout_at_once():
    plans = catalog(plus={"monthly": {"USD": 9.99, "VND": 249_000}, "yearly": dict(PLUS.prices["yearly"])})
    service = billing([PLUS_VND], plans=plans)
    assert service.offered() == [] and start(service) == "price_mismatch"


def test_an_unreadable_catalogue_offers_nothing_and_starts_no_checkout():
    orders = Orders()
    service = billing([PLUS_VND], plans=unreadable, orders=orders)
    assert service.offered() == []
    assert start(service) == "catalog_unavailable" and orders.created == []


@pytest.mark.parametrize(("amount", "currency"), [(99_000, "VND"), (199_000, "USD"), (None, "VND"), (199_000, None)])
def test_checkout_starts_only_at_the_amount_the_learner_confirmed(amount, currency):
    orders = Orders()
    code = start(billing([PLUS_VND], orders=orders), amount=amount, currency=currency)
    assert code == ("price_unconfirmed" if None in (amount, currency) else "price_changed")
    assert orders.created == []


def test_a_matching_confirmed_price_charges_the_servers_amount():
    orders, sent = Orders(), []
    assert start(billing([PLUS_VND], orders=orders, sent=sent), currency="vnd") == "https://pay/x"
    assert orders.created[0]["amount_minor"] == 199_000 and orders.created[0]["plan_id"] == "plus"
    assert sent[0]["json"]["amount"] == 199_000


# ---- gateway readiness ------------------------------------------------------------------------------------

def test_a_gateway_is_ready_only_configured_with_prices_that_all_match():
    report = billing([PLUS_VND]).gateway_report()
    assert report["payos"]["ready"] is True and report["payos"]["configured"] is True
    assert report["polar"] == {"configured": False, "ready": False, "prices": [], "webhook_verification": False}
    assert billing([]).gateway_report()["payos"]["ready"] is False
    mismatched = billing([replace(PLUS_VND, amount_minor=1)]).gateway_report()["payos"]
    assert mismatched["ready"] is False and mismatched["prices"][0]["status"] == "mismatch"
    assert billing([PLUS_VND], plans=unreadable).gateway_report()["payos"]["ready"] is False


def test_the_gateway_report_holds_no_secret():
    secrets = ("SECRET-CLIENT-7f3", "SECRET-API-91a", "SECRET-CHECKSUM-c2d")
    gateway = PayOSGateway(client_id=secrets[0], api_key=secrets[1], checksum_key=secrets[2])
    service = BillingService(orders=Orders(), commerce=Commerce(), gateways={"payos": gateway},
                             prices={"plus:month:payos": PLUS_VND}, catalog=catalog(), now=lambda: NOW)  # fmt: skip
    text = json.dumps(readiness.report(facts(service=service)))
    assert not any(secret in text for secret in secrets)


# ---- runtime readiness ------------------------------------------------------------------------------------

def facts(**overrides):
    values = dict(switch=True, backend="postgresql", backbone="active", commerce_schema=lambda: "present",
                  orders_schema=lambda: "present", entitlement_source=lambda: "installed",
                  service=billing([PLUS_VND]), public_base_url="https://orena.example", production=True)  # fmt: skip
    values.update(overrides)
    return readiness.RuntimeFacts(**values)


def test_billing_is_ready_only_when_every_runtime_capability_is():
    assert readiness.report(facts()) | {"gateways": None} == {
        "ready": True, "blockers": [], "gateways": None,
        "checks": {"switch": "on", "database": "postgresql", "account_backbone": "active", "commerce_schema": "present",
                   "orders_schema": "present", "entitlement_source": "installed", "public_base_url": "https"}}  # fmt: skip


@pytest.mark.parametrize(("override", "blocker"), [
    ({"switch": False, "service": None}, "billing_off"),
    ({"backend": "sqlite", "service": None}, "database_not_postgresql"),
    ({"backbone": "unavailable", "service": None}, "account_backbone_unavailable"),
    ({"commerce_schema": lambda: "unreadable"}, "commerce_schema_unreadable"),
    ({"orders_schema": lambda: "absent"}, "orders_schema_absent"),
    ({"entitlement_source": lambda: "unverified"}, "entitlement_source_unverified"),
    ({"public_base_url": ""}, "public_base_url_unset"),
    ({"public_base_url": "http://orena.example"}, "public_base_url_not_https"),
    ({"service": billing([replace(PLUS_VND, amount_minor=1)])}, "no_gateway_ready"),
    ({"service": billing([PLUS_VND], plans=unreadable)}, "catalog_unavailable"),
])
def test_each_missing_capability_is_named_and_keeps_billing_not_ready(override, blocker):
    report = readiness.report(facts(**override))
    assert report["ready"] is False and blocker in report["blockers"]


def test_plain_http_is_accepted_outside_production():
    assert readiness.report(facts(public_base_url="http://localhost:8031", production=False))["ready"] is True


def test_billing_ready_is_false_until_configured_and_never_raises():
    readiness.configure(None)
    assert readiness.billing_ready() is False

    def broken():
        raise RuntimeError("listing failed")

    readiness.configure(facts(orders_schema=broken))
    try:
        assert readiness.billing_ready() is False
        readiness.configure(facts())
        assert readiness.billing_ready() is True
    finally:
        readiness.configure(None)


def test_billing_off_reads_no_schema():
    def forbidden():
        raise AssertionError("billing off must not inspect the database")

    readiness.configure(facts(switch=False, service=None, commerce_schema=forbidden, orders_schema=forbidden,
                              entitlement_source=forbidden))  # fmt: skip
    try:
        assert readiness.billing_ready() is False
    finally:
        readiness.configure(None)


# ---- R-MON-010: commerce discovery ------------------------------------------------------------------------

COMMERCE = ["commerce_subscriptions", "commerce_billing_event_receipts", "account_incarnations"]


def test_a_table_listing_is_present_absent_or_unreadable():
    assert table_state(lambda: COMMERCE + ["x"], COMMERCE) == "present"
    assert table_state(lambda: COMMERCE[:2], COMMERCE) == "absent"

    def broken():
        raise OSError("connection refused")

    assert table_state(broken, COMMERCE) == "unreadable"


class Listing:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = 0

    def __call__(self):
        self.calls += 1
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(answer, Exception):
            raise answer
        return answer


class Source:
    def subscription_for_user(self, user_key):
        return {"state": "active", "plan_id": "pro", "user": user_key}


def test_commerce_that_is_not_deployed_reads_no_billing_row():
    source = DiscoveringCommerceSource(Listing(["users"]), Source)
    assert source.state == "absent" and source.subscription_for_user("u") is None


def test_commerce_that_is_present_reads_the_billing_row():
    source = DiscoveringCommerceSource(Listing(COMMERCE), Source)
    assert source.state == "installed" and source.subscription_for_user("u")["plan_id"] == "pro"


def test_expected_but_unreadable_commerce_fails_closed_then_recovers():
    clock = [0.0]
    listing = Listing(OSError("down"), OSError("down"), COMMERCE)
    source = DiscoveringCommerceSource(listing, Source, clock=lambda: clock[0], retry_seconds=5)
    assert source.state == "unverified"
    with pytest.raises(RuntimeError):
        source.subscription_for_user("u")  # never a silent legacy read for a possibly-paid account
    assert listing.calls == 1  # inside the retry interval: refused without asking again
    clock[0] = 6
    with pytest.raises(RuntimeError):
        source.subscription_for_user("u")
    clock[0] = 12
    assert source.subscription_for_user("u")["plan_id"] == "pro" and source.state == "installed"
    assert source.subscription_for_user("") is None


def test_an_unreadable_billing_record_makes_the_plan_read_fail_not_fall_back():
    from writing_coach.product.service import ProductService

    class Legacy:
        def get_subscription(self, user_key):
            return None

    source = DiscoveringCommerceSource(Listing(OSError("down")), Source)
    service = ProductService(Legacy(), billing=source, clock=lambda: NOW)
    with pytest.raises(RuntimeError):
        service.plan_for_user("u")
    assert service.account_state("u")["available"] is False


# ---- the product surfaces ---------------------------------------------------------------------------------

def test_the_product_reads_report_the_runtimes_readiness_but_the_frozen_mobile_contract_stays_false():
    from writing_coach.product.api import mobile_account_state
    from writing_coach.product.service import ProductService

    class Legacy:
        def get_subscription(self, user_key):
            return None

    service = ProductService(Legacy(), clock=lambda: NOW)
    assert service.account_state("u")["billing_ready"] is False
    service.billing_ready = lambda: True
    state = service.account_state("u")
    assert state["billing_ready"] is True
    assert mobile_account_state(state)["billing_ready"] is False
    service.billing_ready = lambda: (_ for _ in ()).throw(RuntimeError("probe failed"))
    assert service.account_state("u")["billing_ready"] is False


def test_the_running_app_reports_billing_not_ready_and_guards_the_readiness_report(monkeypatch):
    from fastapi import HTTPException
    from fastapi.testclient import TestClient

    import app as app_module
    from writing_coach import billing_api

    client = TestClient(app_module.app)
    assert client.get("/api/product/plans").json()["billing_ready"] is False
    report = client.get("/api/admin/billing/readiness")
    assert report.status_code == 200  # signed-out local administration in the test runtime
    body = report.json()
    assert body["ready"] is False and "billing_off" in body["blockers"]

    def not_admin(request):
        raise HTTPException(403, "Platform administrator access required")

    monkeypatch.setattr(billing_api, "_admin", not_admin)
    assert client.get("/api/admin/billing/readiness").status_code == 403
