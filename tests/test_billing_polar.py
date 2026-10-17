"""PR-MON-10: Polar card subscriptions - manage and cancel (§4.4), the Polar-side price check (§4.6) and the Polar
customer clean-up of a deleted account (§4.8). Checkout and lifecycle are in test_billing.py."""

from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.test_billing import NOW, POLAR, USD_MONTH, FakeItems, FakeOrders
from writing_coach import billing_api
from writing_coach.billing.service import BillingService

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
