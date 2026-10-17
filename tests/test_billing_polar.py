"""PR-MON-10: Polar card subscriptions - manage and cancel (§4.4), the Polar-side price check (§4.6) and the Polar
customer clean-up of a deleted account (§4.8). Checkout and lifecycle are in test_billing.py."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.test_billing import NOW, POLAR, USD_MONTH, FakeItems, FakeOrders
from writing_coach import billing_api
from writing_coach.billing.gateway import Price
from writing_coach.billing.polar_cleanup import PolarCustomerCleanup, marker_key
from writing_coach.billing.service import BillingService
from writing_coach.persistence.platform_repository import SettingConflict
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


# ---- §4.8 the Polar customer clean-up of a deleted account -------------------------------------------------------

class Settings:
    """platform_settings with the compare-and-set the runtime repository has."""

    def __init__(self):
        self.rows: dict = {}
        self.version = 0

    def get_setting(self, key):
        return self.rows.get(key)

    def set_setting(self, key, value, *, updated_by="", expected_updated_at=...):
        current = self.rows.get(key)
        if expected_updated_at is not ... and (current["updated_at"] if current else None) != expected_updated_at:
            raise SettingConflict(key)
        self.version += 1
        self.rows[key] = {"value": dict(value), "updated_at": self.version, "updated_by": updated_by}
        return self.rows[key]


class Deleted:
    """The derived obligation over a fake account table: deleted incarnations without a complete marker."""

    def __init__(self, settings, deleted, accounts=None):
        self.settings, self.deleted, self.accounts = settings, list(deleted), dict(accounts or {})

    def _value(self, incarnation):
        return (self.settings.get_setting(marker_key(incarnation)) or {}).get("value", {})

    def _pending(self):
        return [i for i in self.deleted if self._value(i).get("state") != "complete"]

    def due(self, now, limit):
        def ready(incarnation):
            stamp = self._value(incarnation).get("next_attempt_at")
            return stamp is None or datetime.fromisoformat(stamp) <= now
        return [i for i in self._pending() if ready(i)][:limit]

    def counts(self, now):
        return {"pending": len(self._pending()), "escalated": 0}

    def pending_of_same_account(self, incarnation):
        account = self.accounts.get(incarnation)
        return [i for i in self._pending() if i != incarnation and self.accounts.get(i) == account]


class Items(FakeItems):
    def __init__(self):
        super().__init__()
        self.resolved: list = []

    def auto_resolve(self, **kwargs):
        self.resolved.append(kwargs)
        return True


def cleanup(*answers, deleted=("inc-old",), accounts=None, gateway=POLAR, clock=None):
    settings, items, calls = Settings(), Items(), []
    queue = list(answers)

    def call(request):
        calls.append(request)
        answer = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(answer, Exception):
            raise answer
        return answer

    worker = PolarCustomerCleanup(gateway=gateway, incarnations=Deleted(settings, deleted, accounts),
                                  settings=settings, items=items, call=call,
                                  now=clock or (lambda: NOW))  # fmt: skip
    return worker, settings, items, calls


@pytest.mark.parametrize("status", [204, 404])
def test_a_deleted_incarnations_polar_customer_is_deleted_and_the_marker_completes(status):
    worker, settings, _, calls = cleanup(status)
    assert worker.clean("inc-old") == "complete"
    [request] = calls
    assert request["method"] == "DELETE"
    assert request["url"] == "https://sandbox-api.polar.sh/v1/customers/external/inc-old?anonymize=true"
    marker = settings.get_setting(marker_key("inc-old"))["value"]
    assert marker["state"] == "complete" and marker["last_status"] == status
    assert set(marker) <= {"state", "attempts", "first_attempt_at", "last_status", "completed_at"}   # no personal data
    assert worker.clean("inc-old") == "complete" and len(calls) == 1   # repeating is harmless: no second call


@pytest.mark.parametrize("answer", [500, 429, 401, OSError("timed out")])
def test_any_other_answer_keeps_the_obligation_pending_with_a_back_off(answer):
    worker, settings, items, _ = cleanup(answer)
    assert worker.clean("inc-old") == "pending"
    marker = settings.get_setting(marker_key("inc-old"))["value"]
    assert marker["state"] == "pending" and marker["attempts"] == 1
    assert datetime.fromisoformat(marker["next_attempt_at"]) > NOW
    assert items.recorded == []   # not escalated before the bound
    assert worker._incarnations.due(NOW, 10) == []   # backing off


def test_past_the_bound_one_operator_item_is_raised_and_resolved_on_completion():
    clock = [NOW]
    worker, _, items, _ = cleanup(500, 500, 500, 204, clock=lambda: clock[0])
    assert worker.clean("inc-old") == "pending"
    clock[0] = NOW + timedelta(hours=25)
    assert worker.clean("inc-old") == "pending"
    [item] = items.recorded
    assert item["kind"] == "event_undecided" and "polar_customer_cleanup_failed" in item["reason"]
    assert item["incarnation_id"] == "inc-old"
    clock[0] = NOW + timedelta(hours=30)
    assert worker.clean("inc-old") == "pending" and len(items.recorded) == 1   # raised once, retries continue
    assert worker.clean("inc-old") == "complete"
    assert items.resolved and items.resolved[0]["dedupe_key"] == "polar_customer_cleanup_failed:inc-old"


def test_a_lost_marker_only_re_runs_the_delete_which_completes_on_404():
    worker, settings, _, calls = cleanup(204, 404)
    assert worker.clean("inc-old") == "complete"
    settings.rows.clear()   # a restore to before the completion, or a removed row
    assert worker._incarnations.due(NOW, 10) == ["inc-old"]
    assert worker.clean("inc-old") == "complete" and len(calls) == 2
    assert settings.get_setting(marker_key("inc-old"))["value"]["last_status"] == 404


@pytest.mark.parametrize("status", [200, 202, 302, 400, 403, 409, 422, 500, 503])
def test_complete_is_never_written_for_anything_but_204_or_404(status):
    worker, settings, _, _ = cleanup(status)
    worker.clean("inc-old")
    assert settings.get_setting(marker_key("inc-old"))["value"]["state"] == "pending"


def test_another_writer_wins_the_marker_and_this_one_writes_nothing():
    worker, settings, _, _ = cleanup(204)
    original = settings.set_setting

    def racing(key, value, **kwargs):
        settings.rows[key] = {"value": {"state": "pending"}, "updated_at": "other", "updated_by": "x"}
        return original(key, value, **kwargs)

    settings.set_setting = racing
    assert worker.clean("inc-old") == "conflict"


def test_without_polar_nothing_is_called_and_the_obligation_stays_pending():
    worker, _, items, calls = cleanup(204, gateway=None)
    counts = Counter()
    worker.step(counts)
    assert calls == [] and counts == Counter() and items.recorded == []
    assert worker.run()["configured"] is False and worker.counts()["pending"] == 1


def test_the_reconciler_step_cleans_the_due_obligations():
    worker, _, _, calls = cleanup(204, deleted=("inc-a", "inc-b"))
    counts = Counter()
    worker.step(counts)
    assert counts["polar_cleanup_complete"] == 2 and len(calls) == 2
    assert worker.counts()["pending"] == 0


def test_a_re_registration_pays_only_once_its_predecessors_customer_is_gone():
    accounts = {"inc-old": "user-1", "inc-new": "user-1", "inc-other": "user-2"}
    worker, _, _, _ = cleanup(500, deleted=("inc-old", "inc-other"), accounts=accounts)
    assert worker.settle_account_of("inc-new") is False   # the predecessor still failing
    worker, _, _, calls = cleanup(204, deleted=("inc-old", "inc-other"), accounts=accounts)
    assert worker.settle_account_of("inc-new") is True and len(calls) == 1   # only this account's predecessor
    assert worker.settle_account_of("inc-new") is True and len(calls) == 1   # done: nothing called again


def test_a_checkout_waits_for_the_predecessors_clean_up():
    worker, _, _, _ = cleanup(500, accounts={"inc-old": "user-1", "inc-1": "user-1"})
    service, _ = checked(product())
    service.attach_polar_cleanup(worker)
    with pytest.raises(Exception, match="previous_customer_cleanup_pending"):
        service.start_checkout(incarnation_id="inc-1", price_key="plus:month:polar",
                               operation_id="6f1c1a2e-0000-4000-8000-000000000001", return_url="r", cancel_url="c",
                               confirmed_amount_minor=999, confirmed_currency="USD")
    assert service.gateway_report()["polar"]["customer_cleanup"] == {"pending": 1, "escalated": 0}
    assert service.plans_capability()["ready"] is True   # reported, never a blocker of other accounts


def test_the_admin_run_answers_counts_only(monkeypatch):
    worker, _, _, _ = cleanup(204, deleted=("inc-a",))
    service, _ = checked(product())
    service.attach_polar_cleanup(worker)
    seen = []
    monkeypatch.setattr(billing_api, "_service", service)
    monkeypatch.setattr(billing_api, "_admin", lambda request: seen.append("admin") or {"role": "admin"})
    app = FastAPI()
    app.include_router(billing_api.router)
    answer = TestClient(app).post("/api/admin/billing/polar/customer-cleanup").json()
    assert seen == ["admin"]
    assert answer == {"complete": 1, "pending": 0, "conflict": 0, "configured": True, "total_pending": 0,
                      "total_escalated": 0}


def test_the_reconciler_runs_the_clean_up_only_when_polar_is_configured():
    from writing_coach.billing.reconciler import BillingReconciler

    class Lock:
        held = True

        def alive(self):
            return True

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    for gateway, expected in ((POLAR, 1), (None, 0)):
        worker, _, _, calls = cleanup(204, gateway=gateway)
        reconciler = BillingReconciler(service=polar_service(), orders=FakeOrders(), items=FakeItems(),
                                       lock=lambda: Lock(), lookups={}, polar_cleanup=worker)  # fmt: skip
        counts = reconciler.tick()
        assert counts.get("polar_cleanup_complete", 0) == expected and len(calls) == expected


def test_a_late_webhook_of_a_deleted_incarnation_never_attaches_to_its_re_registration():
    """§4.8: the stored mapping names A; B's checkout (its order and metadata) never captures A's subscription."""

    from tests.test_billing import FakeCommerce, polar_request, subscription_event

    commerce = FakeCommerce(mapped={"incarnation_id": "inc-A"})
    billing = BillingService(orders=FakeOrders(), commerce=commerce, gateways={"polar": POLAR},
                             prices={"premium:month:polar": USD_MONTH}, now=lambda: NOW,
                             reconciliation=FakeItems())  # fmt: skip
    late = subscription_event("canceled", metadata={"orena_incarnation": "inc-1", "orena_operation": "op-1"})
    billing.handle_webhook("polar", *polar_request(late))
    assert [event["incarnation_id"] for event in commerce.events] == ["inc-A"]


# ---- review of fdb613b0 -----------------------------------------------------------------------------------------

class EvidenceCommerce:
    """The commerce record's receipts: `record_evidence` is exactly-once per event id; it can be made to fail."""

    def __init__(self, mapped=None, fail=False):
        self.mapped, self.fail = mapped, fail
        self.receipts: dict = {}
        self.events: list = []

    def get_provider_subscription(self, provider, external_id):
        return self.mapped

    def record_event(self, **kwargs):
        self.events.append(kwargs)
        return {"status": "apply"}

    def record_evidence(self, **kwargs):
        if self.fail:
            raise OSError("database down")
        key = (kwargs["provider"], kwargs["external_event_id"])
        if key in self.receipts:
            return {"status": "duplicate"}
        self.receipts[key] = kwargs
        return {"status": "recorded"}


def order_paid(*, subscription="sub_1", metadata=None, reason="subscription_cycle"):
    return {"type": "order.paid", "data": {
        "id": "ord_1", "status": "paid", "billing_reason": reason, "subscription_id": subscription,
        "total_amount": 499, "currency": "usd", "customer_id": "cus_1", "product_id": "prod_123",
        "metadata": metadata if metadata is not None else {}}}


def evidence_service(commerce, items=None):
    return BillingService(orders=FakeOrders(), commerce=commerce, gateways={"polar": POLAR},
                          prices={"premium:month:polar": USD_MONTH}, now=lambda: NOW,
                          reconciliation=items if items is not None else FakeItems())  # fmt: skip


def test_a_renewal_order_paid_is_a_durable_receipt_and_changes_no_access():
    """Review P1-1: evidence only, but logged AND receipted before it is acknowledged."""

    from tests.test_billing import polar_request

    commerce = EvidenceCommerce(mapped={"incarnation_id": "inc-1"})
    billing = evidence_service(commerce)
    outcome = billing.handle_webhook("polar", *polar_request(order_paid()))
    assert (outcome.status, outcome.detail) == ("recorded", "order_paid")
    [receipt] = commerce.receipts.values()
    assert receipt["incarnation_id"] == "inc-1" and receipt["external_object_reference"] == "ord_1"
    assert receipt["external_event_id"] == "msg_1" and receipt["payload_digest"]
    assert commerce.events == []   # never an access change
    again = billing.handle_webhook("polar", *polar_request(order_paid()))   # Polar redelivers the same message
    assert again.status == "duplicate" and len(commerce.receipts) == 1


def test_a_first_payment_order_is_receipted_through_orenas_own_checkout():
    from tests.test_billing import polar_request

    commerce = EvidenceCommerce(mapped=None)   # the subscription event has not landed yet
    first = order_paid(reason="subscription_create",
                       metadata={"orena_incarnation": "inc-1", "orena_operation": "op-1", "orena_plan": "premium"})
    assert evidence_service(commerce).handle_webhook("polar", *polar_request(first)).status == "recorded"
    assert [r["incarnation_id"] for r in commerce.receipts.values()] == ["inc-1"]


def test_an_order_naming_no_account_of_orena_is_an_operator_item_never_a_silent_ack():
    from tests.test_billing import polar_request

    items = FakeItems()
    outcome = evidence_service(EvidenceCommerce(), items).handle_webhook("polar", *polar_request(order_paid()))
    assert (outcome.status, outcome.detail) == ("unknown", "order_unmatched")
    [item] = items.recorded
    assert item["kind"] == "event_undecided" and item["reported_amount_minor"] == 499


def test_an_order_paid_that_cannot_be_recorded_is_answered_503_for_a_retry(monkeypatch):
    from tests.test_billing import polar_request

    monkeypatch.setattr(billing_api, "_service", evidence_service(EvidenceCommerce(mapped={"incarnation_id": "inc-1"},
                                                                                   fail=True)))
    app = FastAPI()
    app.include_router(billing_api.router)
    headers, body = polar_request(order_paid())
    answer = TestClient(app).post("/api/billing/webhooks/polar", content=body, headers=headers)
    assert answer.status_code == 503   # nothing durable: Polar must deliver it again


def test_paused_sales_close_checkout_but_webhooks_and_the_portal_keep_working(monkeypatch):
    """Review P1-2: the rollback closes new sales only; a live subscription's lifecycle is still followed."""

    from tests.test_billing import polar_request, subscription_event
    from tests.test_billing_price_integrity import facts
    from writing_coach.billing import readiness

    commerce = EvidenceCommerce(mapped={"incarnation_id": "inc-1"})
    service = checked(product())[0]
    service._commerce = commerce
    service._commerce.get_subscription = lambda incarnation: CARD
    service._send = lambda request: {"customer_portal_url": PORTAL, "expires_at": "t"}
    paused = facts(service=service, new_sales=False)
    report = readiness.report(paused)
    assert report["ready"] is False and report["blockers"] == ["new_sales_paused"]
    assert report["checks"]["new_sales"] == "paused"
    readiness.configure(paused)
    try:
        monkeypatch.setattr(billing_api, "_service", service)
        monkeypatch.setattr(billing_api, "_ready", None)
        monkeypatch.setattr(billing_api, "_public_base", "https://orena.example")
        monkeypatch.setattr(billing_api, "current_user_key", lambda: "learner-1")
        monkeypatch.setattr(billing_api, "_incarnation", lambda: "inc-1")
        app = FastAPI()
        app.include_router(billing_api.router)
        client = TestClient(app)
        assert client.get("/api/billing/offers").json()["offers"] == []
        refused = client.post("/api/billing/checkout", json={
            "price": "plus:month:polar", "operation_id": "6f1c1a2e-0000-4000-8000-000000000001", "amount_minor": 999,
            "currency": "USD"})  # fmt: skip
        assert refused.status_code == 503 and "billing_not_ready" in refused.text
        event = subscription_event(product="prod_123")
        received = client.post("/api/billing/webhooks/polar", content=polar_request(event)[1],
                               headers=polar_request(event)[0])
        assert received.status_code == 200 and received.json()["status"] == "apply"
        assert client.post("/api/billing/portal").json()["url"] == PORTAL
    finally:
        readiness.configure(None)


def test_an_escalated_item_is_closed_even_when_the_marker_was_lost():
    """Review P2: marker removed after escalation, the DELETE answers 404 - the open item is still resolved."""

    clock = [NOW]
    worker, settings, items, _ = cleanup(500, 500, 404, clock=lambda: clock[0])
    worker.clean("inc-old")
    clock[0] = NOW + timedelta(hours=25)
    worker.clean("inc-old")
    assert len(items.recorded) == 1
    settings.rows.clear()   # the marker (and its `escalated` flag) is lost
    assert worker.clean("inc-old") == "complete"
    assert [r["dedupe_key"] for r in items.resolved] == ["polar_customer_cleanup_failed:inc-old"]


# ---- review of 06675882: money taken after a deletion -----------------------------------------------------------

class DeletedEvidenceCommerce(EvidenceCommerce):
    def record_evidence(self, **kwargs):
        outcome = super().record_evidence(**kwargs)
        return {**outcome, "incarnation_deleted": True}


def test_an_order_paid_after_the_account_was_deleted_is_a_paid_deleted_account_item():
    """Deleted A, its mapping kept, a renewal charged before the clean-up completed: an operator's refund
    obligation with what was paid - never ordinary evidence, never an access change."""

    from tests.test_billing import polar_request

    commerce, items = DeletedEvidenceCommerce(mapped={"incarnation_id": "inc-A"}), FakeItems()
    billing = evidence_service(commerce, items)
    outcome = billing.handle_webhook("polar", *polar_request(order_paid()))
    assert (outcome.status, outcome.detail) == ("paid_deleted_account", "order_paid")
    [item] = items.recorded
    assert item["kind"] == "paid_deleted_account" and item["dedupe_key"] == "order:ord_1"
    assert (item["reported_amount_minor"], item["reported_currency"]) == (499, "USD")
    assert item["incarnation_id"] == "inc-A" and item["external_event_id"] == "msg_1"
    assert commerce.events == []
    again = billing.handle_webhook("polar", *polar_request(order_paid()))   # a redelivery stays on this path
    assert again.status == "paid_deleted_account" and len(commerce.receipts) == 1
    assert {i["dedupe_key"] for i in items.recorded} == {"order:ord_1"}   # the repository keeps one item per key


def test_a_deleted_accounts_order_whose_item_cannot_be_recorded_is_answered_503(monkeypatch):
    from tests.test_billing import polar_request

    class Broken(FakeItems):
        def record(self, **kwargs):
            raise OSError("database down")

    monkeypatch.setattr(billing_api, "_service",
                        evidence_service(DeletedEvidenceCommerce(mapped={"incarnation_id": "inc-A"}), Broken()))
    app = FastAPI()
    app.include_router(billing_api.router)
    headers, body = polar_request(order_paid())
    assert TestClient(app).post("/api/billing/webhooks/polar", content=body, headers=headers).status_code == 503
