"""PR-MON-2: price integrity (D-MON-005, D-MON-015) and truthful runtime readiness, including the startup commerce
discovery that must fail safe when the store is expected but unreadable (R-MON-010, D-MON-016)."""

from __future__ import annotations

import json
import uuid
from dataclasses import replace
from types import SimpleNamespace
from datetime import UTC, datetime

import pytest

from writing_coach.billing import readiness
from writing_coach.billing.gateway import Price
from writing_coach.billing.polar import PolarGateway
from writing_coach.billing.price_integrity import catalog_amount_minor, check_prices
from writing_coach.billing.service import BillingService, CheckoutRefused, load_prices
from writing_coach.product.catalog import PLANS, PLUS, CatalogUnavailable
from writing_coach.product.entitlement import DiscoveringCommerceSource, table_state

NOW = datetime(2026, 10, 14, 12, tzinfo=UTC)
POLAR = PolarGateway(access_token="token", webhook_secret="whsec_c2VjcmV0", environment="sandbox")
# The catalogue's defaults: Plus is 199 000 VND and 9.99 USD a month; Pro is 3 190 000 VND and 159.99 USD a year.
PLUS_VND = Price(plan_id="plus", period="month", currency="VND", amount_minor=199_000, gateway="payos")
PRO_VND_YEAR = Price(plan_id="pro", period="year", currency="VND", amount_minor=3_190_000, gateway="payos")
# D-MON-032: plans are sold by Polar only, so offers and checkouts are exercised with Polar prices.
PLUS_USD = Price(plan_id="plus", period="month", currency="USD", amount_minor=999, gateway="polar",
                 external_price_id="prod-plus-month")
PRO_USD_YEAR = Price(plan_id="pro", period="year", currency="USD", amount_minor=15_999, gateway="polar",
                     external_price_id="prod-pro-year")


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
        return {"id": "checkout-1", "url": "https://pay/x"}

    return BillingService(orders=orders or Orders(), commerce=Commerce(), gateways={"polar": POLAR},
                          prices={f"{p.plan_id}:{p.period}:{p.gateway}": p for p in prices},
                          catalog=plans or catalog(), send=send, now=lambda: NOW)  # fmt: skip


def start(service, key="plus:month:polar", *, amount=999, currency="USD"):
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
    {"plan_id": "free", "period": "month", "currency": "USD", "amount_minor": 1, "gateway": "polar",
     "external_price_id": "p"},
    {"plan_id": "premium", "period": "month", "currency": "USD", "amount_minor": 1999, "gateway": "polar",
     "external_price_id": "p"},
    {"plan_id": "gold", "period": "month", "currency": "USD", "amount_minor": 1, "gateway": "polar",
     "external_price_id": "p"},
    {"plan_id": "plus", "period": "month", "currency": "EUR", "amount_minor": 999, "gateway": "polar",
     "external_price_id": "p"},
    {"plan_id": "plus", "period": "month", "currency": "USD", "amount_minor": 999, "gateway": "polar"},
    {"plan_id": "plus", "period": "month", "currency": "VND", "amount_minor": 1, "gateway": "stripe"},
])
def test_a_prices_file_names_only_a_paid_catalogue_plan_a_catalogue_currency_and_a_known_gateway(tmp_path, item):
    path = tmp_path / "prices.json"
    path.write_text(json.dumps([item]))
    with pytest.raises(ValueError):
        load_prices({"BILLING_PRICES_FILE": str(path)})


@pytest.mark.parametrize("gateway", ["payos", "sepay"])
def test_a_plan_price_on_any_domestic_gateway_is_refused(tmp_path, gateway):
    """D-MON-032 (PR-MON-8 §14.2): plans are sold by Polar only; a domestic gateway tops up Credits."""

    item = {"plan_id": "plus", "period": "month", "currency": "VND", "amount_minor": 199_000, "gateway": gateway}
    path = tmp_path / "prices.json"
    path.write_text(json.dumps([item]))
    with pytest.raises(ValueError, match="Polar only"):
        load_prices({"BILLING_PRICES_FILE": str(path)})


def test_a_polar_plan_price_loads(tmp_path):
    item = {"plan_id": "plus", "period": "month", "currency": "USD", "amount_minor": 999, "gateway": "polar",
            "external_price_id": "prod-plus-month"}
    path = tmp_path / "prices.json"
    path.write_text(json.dumps([item]))
    assert load_prices({"BILLING_PRICES_FILE": str(path)}) == {"plus:month:polar": PLUS_USD}


def test_a_plan_price_on_a_domestic_gateway_never_starts_a_checkout_even_when_injected():
    """The second guard: a domestic plan price that reached the service another way sells nothing."""

    from writing_coach.billing.payos import PayOSGateway

    orders, sent = Orders(), []
    service = BillingService(orders=orders, commerce=Commerce(),
                             gateways={"payos": PayOSGateway(client_id="c", api_key="k", checksum_key="s")},
                             prices={"plus:month:payos": PLUS_VND}, catalog=catalog(),
                             send=lambda request: sent.append(request) or {}, now=lambda: NOW)  # fmt: skip
    assert service.offered() == []
    with pytest.raises(LookupError, match="price_not_offered"):
        start(service, "plus:month:payos", amount=199_000, currency="VND")
    assert orders.created == [] and sent == []


def test_a_prices_file_with_the_same_price_twice_is_refused(tmp_path):
    item = {"plan_id": "plus", "period": "month", "currency": "USD", "amount_minor": 999, "gateway": "polar",
            "external_price_id": "prod-plus-month"}
    path = tmp_path / "prices.json"
    path.write_text(json.dumps([item, {**item, "amount_minor": 1}]))
    with pytest.raises(ValueError):
        load_prices({"BILLING_PRICES_FILE": str(path)})


# ---- offers and checkout ----------------------------------------------------------------------------------

def test_only_prices_matching_the_catalogue_are_offered():
    assert [offer["key"] for offer in billing([PLUS_USD, PRO_USD_YEAR]).offered()] == [
        "plus:month:polar", "pro:year:polar"]


def test_one_mismatched_price_blocks_every_offer_and_checkout_of_its_gateway():
    sent, orders = [], Orders()
    service = billing([replace(PLUS_USD, amount_minor=899), PRO_USD_YEAR], orders=orders, sent=sent)
    assert service.offered() == []
    assert start(service, "pro:year:polar", amount=15_999) == "price_mismatch"
    assert start(service, amount=899) == "price_mismatch"
    assert orders.created == [] and sent == []


def test_an_administrators_catalogue_change_blocks_checkout_at_once():
    plans = catalog(plus={"monthly": {"USD": 12.99, "VND": 199_000}, "yearly": dict(PLUS.prices["yearly"])})
    service = billing([PLUS_USD], plans=plans)
    assert service.offered() == [] and start(service) == "price_mismatch"


def test_an_unreadable_catalogue_offers_nothing_and_starts_no_checkout():
    orders = Orders()
    service = billing([PLUS_USD], plans=unreadable, orders=orders)
    assert service.offered() == []
    assert start(service) == "catalog_unavailable" and orders.created == []


@pytest.mark.parametrize(("amount", "currency"), [(899, "USD"), (999, "VND"), (None, "USD"), (999, None)])
def test_checkout_starts_only_at_the_amount_the_learner_confirmed(amount, currency):
    orders = Orders()
    code = start(billing([PLUS_USD], orders=orders), amount=amount, currency=currency)
    assert code == ("price_unconfirmed" if None in (amount, currency) else "price_changed")
    assert orders.created == []


def test_a_matching_confirmed_price_charges_the_servers_amount():
    orders, sent = Orders(), []
    assert start(billing([PLUS_USD], orders=orders, sent=sent), currency="usd") == "https://pay/x"
    assert orders.created[0]["amount_minor"] == 999 and orders.created[0]["plan_id"] == "plus"
    # Polar charges its product's own price, which the Polar-side check (PR-MON-10) holds to the catalogue.
    assert sent[0]["json"]["products"] == ["prod-plus-month"]


# ---- gateway readiness ------------------------------------------------------------------------------------

def test_a_gateway_is_ready_only_configured_with_prices_that_all_match():
    report = billing([PLUS_USD]).gateway_report()
    assert report["polar"]["ready"] is True and report["polar"]["configured"] is True
    assert report["payos"] == {"configured": False, "ready": False, "prices": [], "webhook_verification": False,
                               "active_domestic": False}
    assert billing([]).gateway_report()["polar"]["ready"] is False
    mismatched = billing([replace(PLUS_USD, amount_minor=1)]).gateway_report()["polar"]
    assert mismatched["ready"] is False and mismatched["prices"][0]["status"] == "mismatch"
    assert billing([PLUS_USD], plans=unreadable).gateway_report()["polar"]["ready"] is False


def test_the_gateway_report_holds_no_secret():
    secrets = ("SECRET-TOKEN-7f3", "whsec_U0VDUkVULVdFQkhPT0stOTFh")
    gateway = PolarGateway(access_token=secrets[0], webhook_secret=secrets[1], environment="sandbox")
    service = BillingService(orders=Orders(), commerce=Commerce(), gateways={"polar": gateway},
                             prices={"plus:month:polar": PLUS_USD}, catalog=catalog(), now=lambda: NOW)  # fmt: skip
    text = json.dumps(readiness.report(facts(service=service)))
    assert not any(secret in text for secret in secrets)


# ---- runtime readiness ------------------------------------------------------------------------------------

def facts(**overrides):
    values = dict(switch=True, backend="postgresql", backbone="active", commerce_schema=lambda: "present",
                  orders_schema=lambda: "present", entitlement_source=lambda: "installed",
                  service=billing([PLUS_USD]), public_base_url="https://orena.example", production=True)  # fmt: skip
    values.update(overrides)
    return readiness.RuntimeFacts(**values)


def test_billing_is_ready_only_when_every_runtime_capability_is():
    assert readiness.report(facts()) | {"gateways": None} == {
        "ready": True, "blockers": [], "gateways": None, "reconciliation": "not_configured",
        # PR-MON-8 §14.4: a Polar-only runtime is ready; the Credits blocker stays under its own capability
        "capabilities": {"plans": {"ready": True, "blockers": []},
                         "credits": {"ready": False, "blockers": ["credits_not_configured"]}},
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
])
def test_each_missing_runtime_capability_is_named_and_keeps_billing_not_ready(override, blocker):
    report = readiness.report(facts(**override))
    assert report["ready"] is False and blocker in report["blockers"]


@pytest.mark.parametrize(("override", "plans_blocker"), [
    ({"service": billing([replace(PLUS_USD, amount_minor=1)])}, "price_mismatch"),
    ({"service": billing([PLUS_USD], plans=unreadable)}, "catalog_unavailable"),
    ({"service": billing([])}, "no_polar_price"),
])
def test_a_capability_blocker_stays_in_its_capability(override, plans_blocker):
    """PR-MON-8 §14.4: the top level holds runtime blockers only, plus `no_billing_capability_ready`."""

    report = readiness.report(facts(**override))
    assert report["ready"] is False and report["blockers"] == ["no_billing_capability_ready"]
    assert plans_blocker in report["capabilities"]["plans"]["blockers"]
    assert report["capabilities"]["plans"]["ready"] is False


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


# ---- the learner entrypoints require a ready runtime (PR-MON-2 review P1) -----------------------------------

@pytest.fixture
def billing_routes(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from writing_coach import billing_api

    def install(service, runtime):
        readiness.configure(runtime)
        monkeypatch.setattr(billing_api, "_service", service)
        monkeypatch.setattr(billing_api, "_ready", None)  # the real readiness decision
        monkeypatch.setattr(billing_api, "_public_base", "https://orena.example")
        monkeypatch.setattr(billing_api, "current_user_key", lambda: "learner-1")
        monkeypatch.setattr(billing_api, "_incarnation", lambda: "inc-1")
        app = FastAPI()
        app.include_router(billing_api.router)
        return TestClient(app)

    yield install
    readiness.configure(None)


def body(**overrides):
    return {"price": "plus:month:polar", "operation_id": str(uuid.uuid4()), "amount_minor": 999,
            "currency": "USD", **overrides}  # fmt: skip


@pytest.mark.parametrize("override", [
    {"orders_schema": lambda: "absent"},  # configured, but 0027 `billing_orders` not applied
    {"public_base_url": "http://orena.example"},  # production without https
    {"public_base_url": ""},  # production without a public URL
])
def test_a_runtime_that_is_not_billing_ready_offers_nothing_and_starts_no_checkout(billing_routes, override):
    install = billing_routes
    orders, sent = Orders(), []
    service = billing([PLUS_USD], orders=orders, sent=sent)
    client = install(service, facts(service=service, **override))

    assert client.get("/api/billing/offers").json() == {"enabled": True, "ready": False, "offers": [], "credit_packs": []}
    refused = client.post("/api/billing/checkout", json=body())
    assert refused.status_code == 503 and "billing_not_ready" in refused.text
    assert orders.created == [] and sent == []


def test_a_billing_ready_runtime_offers_and_starts_checkout_as_before(billing_routes):
    install = billing_routes
    orders, sent = Orders(), []
    service = billing([PLUS_USD], orders=orders, sent=sent)
    client = install(service, facts(service=service))

    offers = client.get("/api/billing/offers").json()
    assert offers["enabled"] is True and offers["ready"] is True and len(offers["offers"]) == 1
    started = client.post("/api/billing/checkout", json=body())
    assert started.status_code == 200 and started.json()["redirect_url"] == "https://pay/x"
    assert len(orders.created) == 1 and len(sent) == 1


def test_a_checkout_for_a_capability_that_is_not_ready_is_refused_while_the_other_sells(billing_routes):
    """PR-MON-8 §14.4: a Polar-only runtime is ready, but a credit-pack checkout stays closed (`billing_not_ready`)."""

    install = billing_routes
    orders, sent = Orders(), []
    service = billing([PLUS_USD], orders=orders, sent=sent)
    client = install(service, facts(service=service))

    offers = client.get("/api/billing/offers").json()
    assert offers["ready"] is True and len(offers["offers"]) == 1 and offers["credit_packs"] == []
    refused = client.post("/api/billing/checkout", json=body(price="credits:small:sepay", amount_minor=50_000,
                                                             currency="VND", credit_units=100))  # fmt: skip
    assert refused.status_code == 503 and "billing_not_ready" in refused.text
    assert orders.created == [] and sent == []


def test_a_verified_webhook_is_received_while_new_checkouts_are_closed(billing_routes):
    install = billing_routes
    received = []

    class Service:
        def handle_webhook(self, gateway, headers, raw):
            received.append(gateway)
            return SimpleNamespace(status="applied")

    client = install(Service(), facts(orders_schema=lambda: "absent"))
    answer = client.post("/api/billing/webhooks/payos", content=b"{}")
    assert answer.status_code == 200 and answer.json() == {"ok": True, "status": "applied"}
    assert received == ["payos"]
