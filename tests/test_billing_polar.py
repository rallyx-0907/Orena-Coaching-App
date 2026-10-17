"""PR-MON-10: Polar card subscriptions - manage and cancel (§4.4), the Polar-side price check (§4.6) and the Polar
customer clean-up of a deleted account (§4.8). Checkout and lifecycle are in test_billing.py."""

from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.test_billing import NOW, POLAR, USD_MONTH, FakeItems, FakeOrders
from writing_coach import billing_api
from writing_coach.billing.gateway import Price
from writing_coach.billing.service import BillingService
from writing_coach.product.catalog import PLANS

PORTAL = "https://sandbox.polar.sh/org/portal?customer_session_token=SECRET-SESSION-TOKEN"


class Subscriptions:
    def __init__(self, current=None):
        self.current = current

    def get_subscription(self, incarnation_id):
        return self.current


def polar_service(current=None, *, send=None, gateways=None):
    return BillingService(orders=FakeOrders(), commerce=Subscriptions(current),
                          gateways=gateways if gateways is not None else {"polar": POLAR},
                          prices={"premium:month:polar": USD_MONTH}, now=lambda: NOW, reconciliation=FakeItems(),
                          send=send or (lambda request: {}))  # fmt: skip


CARD = {"state": "active", "provider": "polar", "external_subscription_id": "sub_1"}


# ---- §4.4 manage and cancel -------------------------------------------------------------------------------------

def test_the_portal_link_is_a_customer_session_for_the_accounts_incarnation():
    sent = []

    def send(request):
        sent.append(request)
        return {"customer_portal_url": PORTAL, "expires_at": "2026-10-17T13:00:00Z", "token": "x"}

    answer = polar_service(CARD, send=send).customer_portal("inc-1", "https://o/#/plan")
    assert answer == {"url": PORTAL, "expires_at": "2026-10-17T13:00:00Z"}
    [request] = sent
    assert request["method"] == "POST" and request["url"] == "https://sandbox-api.polar.sh/v1/customer-sessions/"
    assert request["json"] == {"external_customer_id": "inc-1", "return_url": "https://o/#/plan"}


@pytest.mark.parametrize("current", [None, {"state": "active", "provider": "payos",
                                             "external_subscription_id": "prepaid:inc-1"},
                                      {"state": "ended", "provider": "polar", "external_subscription_id": ""}])
def test_without_a_polar_subscription_there_is_nothing_to_manage(current):
    sent = []
    with pytest.raises(LookupError, match="no_subscription"):
        polar_service(current, send=lambda request: sent.append(request) or {}).customer_portal("inc-1", "r")
    assert sent == []


def test_a_portal_answer_that_is_not_an_https_link_is_a_failure():
    with pytest.raises(RuntimeError):
        polar_service(CARD, send=lambda request: {"customer_portal_url": "javascript:alert(1)"}).customer_portal(
            "inc-1", "r")


@pytest.fixture
def portal_routes(monkeypatch):
    def install(service, *, user="learner-1"):
        monkeypatch.setattr(billing_api, "_service", service)
        monkeypatch.setattr(billing_api, "_public_base", "https://orena.example")
        monkeypatch.setattr(billing_api, "current_user_key", lambda: user)
        monkeypatch.setattr(billing_api, "_incarnation", lambda: "inc-1")
        app = FastAPI()
        app.include_router(billing_api.router)
        return TestClient(app)

    return install


def test_the_portal_route_answers_the_link_and_never_logs_it(portal_routes, caplog):
    caplog.set_level(logging.DEBUG)
    service = polar_service(CARD, send=lambda request: {"customer_portal_url": PORTAL, "expires_at": "t"})
    answer = portal_routes(service).post("/api/billing/portal")
    assert answer.status_code == 200 and answer.json() == {"url": PORTAL, "expires_at": "t"}
    assert "SECRET-SESSION-TOKEN" not in caplog.text


@pytest.mark.parametrize(("current", "send", "gateways", "status", "code"), [
    (None, None, None, 404, "no_subscription"),
    (CARD, lambda request: (_ for _ in ()).throw(OSError("polar down")), None, 502, "gateway_unavailable"),
    (CARD, None, {}, 503, "portal_unavailable"),
])
def test_the_portal_route_says_why_it_cannot_open(portal_routes, current, send, gateways, status, code):
    answer = portal_routes(polar_service(current, send=send, gateways=gateways)).post("/api/billing/portal")
    assert answer.status_code == status and code in answer.text


def test_the_portal_needs_a_signed_in_learner(portal_routes):
    answer = portal_routes(polar_service(CARD), user="legacy").post("/api/billing/portal")
    assert answer.status_code == 401 and "sign_in_required" in answer.text


# ---- §4.6 the Polar-side price check (R-MON-011) ---------------------------------------------------------------

# The catalogue's Plus month in USD, priced on a Polar product (PR-MON-2: a price the catalogue does not hold is
# already refused before Polar is asked).
PLUS_MONTH = Price(plan_id="plus", period="month", currency="USD", amount_minor=999, gateway="polar",
                   external_price_id="prod_123")


def product(**over):
    """Shaped like the owner's sandbox products read on 2026-10-17 (ids are configuration, not secrets)."""

    value = {"id": "prod_123", "is_archived": False, "is_recurring": True, "recurring_interval": "month",
             "prices": [{"id": "price_1", "amount_type": "fixed", "price_amount": 999, "price_currency": "usd",
                         "is_archived": False}]}
    value.update(over)
    return value


def checked(answer, *, clock=None):
    calls = []

    def fetch(product_id):
        calls.append(product_id)
        if isinstance(answer, Exception):
            raise answer
        return answer

    service = BillingService(orders=FakeOrders(), commerce=Subscriptions(), gateways={"polar": POLAR},
                             prices={"plus:month:polar": PLUS_MONTH}, catalog=lambda: PLANS, now=lambda: NOW,
                             reconciliation=FakeItems(), polar_products=fetch,
                             clock=clock or (lambda: 0.0))  # fmt: skip
    return service, calls


def test_a_polar_product_that_sells_exactly_the_price_matches():
    service, calls = checked(product())
    assert service.polar_price_state() == "match" and calls == ["prod_123"]
    assert service.gateway_report()["polar"]["provider_prices"] == "match"


@pytest.mark.parametrize("answer", [
    product(prices=[{"amount_type": "fixed", "price_amount": 1099, "price_currency": "usd", "is_archived": False}]),
    product(prices=[{"amount_type": "fixed", "price_amount": 999, "price_currency": "eur", "is_archived": False}]),
    product(recurring_interval="year"),
    product(is_archived=True),
    product(prices=[{"amount_type": "fixed", "price_amount": 999, "price_currency": "usd", "is_archived": True}]),
    product(prices=[{"amount_type": "fixed", "price_amount": 999, "price_currency": "usd", "is_archived": False},
                    {"amount_type": "fixed", "price_amount": 899, "price_currency": "usd", "is_archived": False}]),
    product(prices=[{"amount_type": "custom", "price_amount": 999, "price_currency": "usd", "is_archived": False}]),
    product(id="prod_other"),
])
def test_a_polar_product_that_does_not_sell_exactly_the_price_closes_plans(answer):
    service, _ = checked(answer)
    assert service.polar_price_state() == "mismatch"
    assert "polar_price_mismatch" in service.plans_capability()["blockers"]
    assert service.gateway_report()["polar"]["ready"] is False
    with pytest.raises(Exception, match="polar_price_mismatch"):
        service.start_checkout(incarnation_id="inc-1", price_key="plus:month:polar",
                               operation_id="6f1c1a2e-0000-4000-8000-000000000001", return_url="r", cancel_url="c",
                               confirmed_amount_minor=999, confirmed_currency="USD")


def test_an_unreadable_polar_answer_closes_plans_and_is_asked_again_sooner():
    clock = [0.0]
    service, calls = checked(OSError("polar down"), clock=lambda: clock[0])
    assert service.polar_price_state() == "unreadable"
    assert "polar_unreadable" in service.plans_capability()["blockers"]
    clock[0] = 30
    assert service.polar_price_state() == "unreadable" and len(calls) == 1   # cached inside the retry interval
    clock[0] = 61
    service.polar_price_state()
    assert len(calls) == 2


def test_a_matching_answer_is_kept_and_not_asked_for_on_every_read():
    clock = [0.0]
    service, calls = checked(product(), clock=lambda: clock[0])
    for _ in range(5):
        service.polar_price_state()
    assert len(calls) == 1
    clock[0] = 301
    service.polar_price_state()
    assert len(calls) == 2


def test_without_the_check_wired_nothing_is_fetched_and_nothing_is_blocked():
    assert polar_service().polar_price_state() == "unchecked"


def test_the_product_request_is_a_read_of_one_product():
    request = POLAR.product_request("prod/../x")
    assert request["method"] == "GET" and "json" not in request
    assert request["url"] == "https://sandbox-api.polar.sh/v1/products/prod%2F..%2Fx"
