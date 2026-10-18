"""PR-MON-9 (design revision 3.1): an existing Polar subscriber's change, cancel, resume and invoices through Polar's
API - the canonical matrix (§3.5), the fail-closed switch (§3.6.1), the operation journal with leases and crash
recovery (§4.2.1), fresh local state (§4.1) and the invoice flow (§4.3). Polar is a recorded fake."""

from __future__ import annotations

import threading
from collections import Counter
from datetime import UTC, datetime, timedelta

import pytest

from tests.test_billing_polar import Settings
from writing_coach.billing.gateway import Price
from writing_coach.billing.polar import PolarGateway
from writing_coach.billing.polar_subscription import (
    CLAIM_WINDOW, LEASE, OP_PREFIX, RETENTION, UNKNOWN_SETTLE, PolarSubscriptions, SubscriptionRefused, classify,
)

NOW = datetime(2026, 10, 17, 12, tzinfo=UTC)
POLAR = PolarGateway(access_token="token", webhook_secret="whsec_c2VjcmV0", environment="sandbox")
PRICES = {f"{plan}:{period}:polar": Price(plan_id=plan, period=period, currency="USD", amount_minor=amount,
                                         gateway="polar", external_price_id=f"prod-{plan}-{period}")
          for plan, period, amount in (("plus", "month", 999), ("plus", "year", 7999), ("pro", "month", 1999),
                                       ("pro", "year", 15999))}  # fmt: skip
OP = "6f1c1a2e-0000-4000-8000-000000000001"


# ---- §3.5 the canonical matrix ------------------------------------------------------------------------------------

@pytest.mark.parametrize(("current", "target", "kind", "proration"), [
    (("plus", "month"), ("pro", "month"), "upgrade", "invoice"),
    (("plus", "year"), ("pro", "month"), "upgrade", "invoice"),
    (("pro", "month"), ("plus", "month"), "downgrade", "next_period"),
    (("pro", "month"), ("plus", "year"), "downgrade", "next_period"),   # the tier wins over the period
    (("pro", "year"), ("plus", "month"), "downgrade", "next_period"),
    (("plus", "month"), ("plus", "year"), "period_up", "invoice"),
    (("pro", "year"), ("pro", "month"), "period_down", "next_period"),
    (("plus", "month"), ("plus", "month"), "none", ""),
])
def test_the_feature_tier_wins_over_the_billing_period(current, target, kind, proration):
    change = classify(current, target)
    assert (change["kind"], change["proration"]) == (kind, proration)
    assert change["effect"] == {"invoice": "now", "next_period": "renewal", "": ""}[proration]


# ---- a fake Polar and a fake commerce record ------------------------------------------------------------------------

class Polar:
    def __init__(self, product="prod-plus-month", **live):
        self.live = {"id": "sub_1", "product_id": product, "cancel_at_period_end": False, "pending_update": None,
                     "recurring_interval": "month", "customer": {"email": "learner@example.test"},
                     "modified_at": "2026-10-17T00:00:00Z", **live}
        self.patches: list = []
        self.answers: list = []   # PATCH answers to give, in order: an int status or an Exception
        self.reads = 0
        self.lock = threading.Lock()

    def __call__(self, request):
        method, url = request["method"], request["url"]
        if method == "GET" and url.endswith("/payment-methods"):
            return 200, {"items": [{"id": "pm_1", "is_default": True, "type": "card",
                                    "method_metadata": {"brand": "visa", "last4": "4242", "exp_month": 8,
                                                        "exp_year": 2028, "wallet": None}}]}
        if method == "GET" and "/v1/subscriptions/" in url:
            self.reads += 1
            return 200, dict(self.live)
        if method == "PATCH":
            with self.lock:
                self.patches.append(request["json"])
                answer = self.answers.pop(0) if self.answers else 200
            if isinstance(answer, Exception):
                raise answer
            if answer == 200:
                self.apply(request["json"])
            return answer, {}
        raise AssertionError(f"unexpected {method} {url}")

    def apply(self, body):
        # Polar's revision moves only on an applied change; stamped at the send (NOW), so a later operation sent at NOW
        # sees no movement after its own send unless a test moves it explicitly.
        self.live["modified_at"] = "2026-10-17T11:59:59Z"
        if "product_id" in body:
            if body["proration_behavior"] == "next_period":
                self.live["pending_update"] = {"product_id": body["product_id"]}
            else:
                self.live["product_id"] = body["product_id"]
        if "cancel_at_period_end" in body:
            self.live["cancel_at_period_end"] = body["cancel_at_period_end"]


class Commerce:
    def __init__(self, **over):
        self.row = {"provider": "polar", "external_subscription_id": "sub_1", "plan_id": "plus", "state": "active",
                    "paid_through": NOW + timedelta(days=20), "cancel_at_period_end": False, **over}

    def get_subscription(self, incarnation_id):
        return dict(self.row) if incarnation_id == "inc-1" else None


def subs(polar=None, commerce=None, *, scheduled=False, clock=None, settings=None, items=None, index=None):
    polar = polar or Polar()
    worker = PolarSubscriptions(gateway=POLAR, commerce=commerce or Commerce(), prices=PRICES,
                                settings=settings or Settings(), items=items, call=polar,
                                now=clock or (lambda: NOW), scheduled_changes=scheduled, index=index)  # fmt: skip
    return worker, polar


def doc(worker, operation=OP):
    stored = worker._settings.get_setting(OP_PREFIX + operation)
    return dict(stored["value"]) if stored else None


# ---- §4.2 change, §3.6.1 fail-closed ---------------------------------------------------------------------------------

def test_an_upgrade_sends_one_patch_with_invoice_proration_and_grants_nothing_itself():
    worker, polar = subs()
    answer = worker.change("inc-1", "pro:month:polar", OP)
    assert answer["state"] == "done"
    assert polar.patches == [{"product_id": "prod-pro-month", "proration_behavior": "invoice"}]
    assert worker._commerce.row["plan_id"] == "plus"   # access moves only with the webhook


@pytest.mark.parametrize("target", ["plus:month:polar", "plus:year:polar"])
def test_with_scheduled_changes_off_a_downgrade_is_refused_and_no_patch_is_sent(target):
    worker, polar = subs(Polar(product="prod-pro-month"))
    with pytest.raises(SubscriptionRefused, match="change_unavailable"):
        worker.change("inc-1", target, OP)
    assert polar.patches == [] and doc(worker) is None   # no account enters active+pending


def test_with_scheduled_changes_proven_a_downgrade_is_next_period():
    worker, polar = subs(Polar(product="prod-pro-month"), scheduled=True)
    assert worker.change("inc-1", "plus:year:polar", OP)["state"] == "done"
    assert polar.patches == [{"product_id": "prod-plus-year", "proration_behavior": "next_period"}]


@pytest.mark.parametrize(("over", "live", "code"), [
    ({"cancel_at_period_end": True}, {}, "cancelling"),
    ({}, {"pending_update": {"product_id": "prod-plus-month"}}, "change_pending"),
    ({}, {"product_id": "prod-unknown"}, "unknown_product"),
])
def test_a_change_the_state_machine_forbids_is_refused_before_any_write(over, live, code):
    polar = Polar(product=live.pop("product_id", "prod-pro-month"), **live)
    worker, _ = subs(polar, Commerce(**over), scheduled=True)
    with pytest.raises(SubscriptionRefused, match=code):
        worker.change("inc-1", "plus:month:polar", OP)
    assert polar.patches == []


def test_the_same_plan_is_no_change_and_another_accounts_subscription_is_invisible():
    worker, _ = subs()
    with pytest.raises(SubscriptionRefused, match="no_change"):
        worker.change("inc-1", "plus:month:polar", OP)
    with pytest.raises(SubscriptionRefused, match="no_subscription"):
        worker.change("inc-2", "pro:month:polar", OP)


def test_the_preview_is_case_b_until_proven():
    worker, _ = subs()
    assert worker.preview("inc-1", "pro:month:polar") == {"kind": "upgrade", "takes_effect": "now", "due_today": None}


# ---- §4.2.1 the operation journal -------------------------------------------------------------------------------------

def test_the_operation_is_persisted_before_the_patch():
    worker, polar = subs()
    seen = []
    original = polar.__call__

    def watching(request):
        if request["method"] == "PATCH":
            seen.append(doc(worker)["state"])
        return original(request)

    worker._call = watching
    worker.change("inc-1", "pro:month:polar", OP)
    assert seen == ["sent"] and doc(worker)["state"] == "done"


def test_the_same_operation_never_sends_a_second_patch_and_a_different_request_conflicts():
    worker, polar = subs()
    worker.change("inc-1", "pro:month:polar", OP)
    assert worker.change("inc-1", "pro:month:polar", OP)["state"] == "done"
    assert len(polar.patches) == 1
    with pytest.raises(SubscriptionRefused, match="operation_conflict"):
        worker.change("inc-1", "pro:year:polar", OP)
    with pytest.raises(SubscriptionRefused, match="operation_conflict"):
        worker.cancel("inc-1", "too_expensive", OP)
    assert len(polar.patches) == 1


@pytest.mark.parametrize("failure", [TimeoutError("read timed out"), 500, 503, 0])
def test_an_ambiguous_patch_is_provider_unknown_and_reconciled_by_reads_only(failure):
    clock = [NOW]
    worker, polar = subs(clock=lambda: clock[0])
    polar.answers = [failure]
    first = worker.change("inc-1", "pro:month:polar", OP)
    assert first["state"] == "provider_unknown" and len(polar.patches) == 1
    clock[0] = NOW + LEASE + timedelta(seconds=1)
    assert worker.change("inc-1", "pro:month:polar", OP)["state"] == "provider_unknown"   # GET, no PATCH
    clock[0] = NOW + UNKNOWN_SETTLE + timedelta(seconds=1)
    assert worker.operation("inc-1", OP)["state"] == "not_applied"
    assert len(polar.patches) == 1 and polar.reads >= 2


def test_an_ambiguous_patch_that_did_apply_reconciles_to_done():
    clock = [NOW]
    worker, polar = subs(clock=lambda: clock[0])
    polar.answers = [TimeoutError("timed out after the charge")]
    original = polar.__call__

    def applied_then_lost(request):
        if request["method"] == "PATCH":
            polar.apply(request["json"])
        return original(request)

    worker._call = applied_then_lost
    assert worker.change("inc-1", "pro:month:polar", OP)["state"] in ("provider_unknown", "done")
    clock[0] = NOW + LEASE + timedelta(seconds=1)
    assert worker.operation("inc-1", OP)["state"] == "done"
    assert len(polar.patches) == 1


@pytest.mark.parametrize("status", [402, 409, 422])
def test_a_definite_refusal_is_terminal(status):
    worker, polar = subs()
    polar.answers = [status]
    assert worker.change("inc-1", "pro:month:polar", OP) == {"state": "refused", "action": "change", "status": status}
    assert worker.change("inc-1", "pro:month:polar", OP)["state"] == "refused" and len(polar.patches) == 1


def crash_after(worker, state, created):
    """A document as a dead process left it."""

    request = {"action": "change", "subscription": "sub_1",
               "body": {"product_id": "prod-pro-month", "proration_behavior": "invoice"}}
    from writing_coach.billing.polar_subscription import _digest

    digest = _digest({"action": "change", "subscription": "sub_1", "asked": {"price": "pro:month:polar"}})
    value = {"incarnation": "inc-1", "action": "change", "request_digest": digest, "request": request,
             "expect": {"product_id": "prod-pro-month"}, "state": state, "owner": "dead",
             "lease_until": (created + LEASE).isoformat(), "created_at": created.isoformat(),
             "updated_at": created.isoformat()}  # fmt: skip
    if state == "sent":
        value["sent_at"] = created.isoformat()
    worker._settings.set_setting(OP_PREFIX + OP, value, expected_updated_at=None)


def test_a_crash_before_sent_is_claimed_within_the_window_and_sends_the_first_patch():
    clock = [NOW]
    worker, polar = subs(clock=lambda: clock[0])
    crash_after(worker, "pending", NOW)
    assert worker.change("inc-1", "pro:month:polar", OP)["state"] == "pending"   # lease live: its owner works
    assert polar.patches == []
    clock[0] = NOW + LEASE + timedelta(seconds=1)
    assert worker.change("inc-1", "pro:month:polar", OP)["state"] == "done"
    assert len(polar.patches) == 1


def test_a_crash_before_sent_older_than_the_window_is_not_applied_without_a_patch():
    worker, polar = subs(clock=lambda: NOW + CLAIM_WINDOW + timedelta(seconds=1))
    crash_after(worker, "pending", NOW)
    assert worker.change("inc-1", "pro:month:polar", OP)["state"] == "not_applied"
    assert polar.patches == []


def test_a_crash_after_sent_is_never_resent():
    worker, polar = subs(clock=lambda: NOW + LEASE + timedelta(seconds=1))
    crash_after(worker, "sent", NOW)
    assert worker.change("inc-1", "pro:month:polar", OP)["state"] == "provider_unknown"
    assert polar.patches == [] and polar.reads == 1


def test_two_claimers_of_one_stale_operation_send_exactly_one_patch():
    settings = Settings()
    polar = Polar()
    clock = lambda: NOW + LEASE + timedelta(seconds=1)  # noqa: E731
    first, _ = subs(polar, settings=settings, clock=clock)
    second, _ = subs(polar, settings=settings, clock=clock)
    crash_after(first, "pending", NOW)
    barrier = threading.Barrier(2)
    answers = []

    def claim(worker):
        barrier.wait()
        answers.append(worker.change("inc-1", "pro:month:polar", OP)["state"])

    threads = [threading.Thread(target=claim, args=(w,)) for w in (first, second)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(polar.patches) == 1


# ---- §4.3 cancel and resume -------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("reason", "polar_reason"), [("too_expensive", "too_expensive"), ("not_using", "unused"),
                                                      ("missing_feature", "missing_features"),
                                                      ("taking_a_break", "other")])
def test_cancel_sends_the_mapped_reason_and_no_comment(reason, polar_reason):
    worker, polar = subs()
    assert worker.cancel("inc-1", reason, OP)["state"] == "done"
    assert polar.patches == [{"cancel_at_period_end": True, "customer_cancellation_reason": polar_reason}]


def test_cancel_without_a_reason_sends_none():
    worker, polar = subs()
    assert worker.cancel("inc-1", None, OP)["state"] == "done"
    assert polar.patches == [{"cancel_at_period_end": True}]


def test_cancel_is_allowed_while_a_change_is_pending_and_resume_only_when_cancelling():
    worker, polar = subs(Polar(pending_update={"product_id": "prod-plus-month"}))
    assert worker.cancel("inc-1", "taking_a_break", OP)["state"] == "done"
    with pytest.raises(SubscriptionRefused, match="not_cancelling"):
        worker.resume("inc-1", "6f1c1a2e-0000-4000-8000-000000000002")
    cancelling, polar = subs(commerce=Commerce(cancel_at_period_end=True))
    assert cancelling.resume("inc-1", "6f1c1a2e-0000-4000-8000-000000000003")["state"] == "done"
    assert polar.patches == [{"cancel_at_period_end": False}]
    with pytest.raises(SubscriptionRefused, match="reason_invalid"):
        worker.cancel("inc-1", "free text", "6f1c1a2e-0000-4000-8000-000000000004")


# ---- §4.1 fresh local state ------------------------------------------------------------------------------------------

def test_the_access_fields_are_fresh_every_read_and_only_enrichment_is_cached():
    worker, polar = subs()
    first = worker.view("inc-1")
    assert first["plan"] == "plus" and first["period"] == "month" and first["enrichment"] == "live"
    worker._commerce.row.update(plan_id="pro", cancel_at_period_end=True)   # the webhook's write
    second = worker.view("inc-1")
    assert second["plan"] == "pro" and second["cancel_at_period_end"] is True   # no cache on local fields
    assert polar.reads == 1   # enrichment within 30 s is cached
    worker.forget("inc-1")
    worker.view("inc-1")
    assert polar.reads == 2


# ---- retention ---------------------------------------------------------------------------------------------------

class Index:
    def __init__(self, settings):
        self.settings = settings
        self.deleted: list = []

    def keys(self, prefix):
        return [key for key in list(self.settings.rows) if key.startswith(prefix)]

    def delete(self, key):
        self.deleted.append(key)
        self.settings.rows.pop(key, None)

    def incarnation_deleted(self, incarnation):
        return False


def test_terminal_operations_are_deleted_after_the_retention_and_unresolved_ones_escalate():
    from tests.test_billing_polar import Items

    settings, items = Settings(), Items()
    clock = [NOW]
    worker, polar = subs(settings=settings, items=items, index=Index(settings), clock=lambda: clock[0])
    worker.change("inc-1", "pro:month:polar", OP)
    polar.answers = [TimeoutError("lost")]
    other = "6f1c1a2e-0000-4000-8000-000000000009"
    worker.cancel("inc-1", "not_using", other)
    clock[0] = NOW + timedelta(hours=25)
    polar.live["cancel_at_period_end"] = False   # Polar never applied the cancel
    counts = Counter()
    worker.step(counts)
    assert doc(worker, other)["state"] == "not_applied"   # past the settle time, by reads only
    clock[0] = NOW + RETENTION + timedelta(days=2)
    worker.step(Counter())
    assert settings.rows == {}   # both terminal documents deleted after 90 days


def test_an_operation_that_stays_unresolved_past_a_day_raises_one_operator_item():
    from tests.test_billing_polar import Items

    settings, items = Settings(), Items()
    clock = [NOW]
    worker, polar = subs(settings=settings, items=items, index=Index(settings), clock=lambda: clock[0])
    polar.answers = [TimeoutError("lost")]
    worker.change("inc-1", "pro:month:polar", OP)
    original = polar.__call__

    def reads_fail(request):
        if request["method"] == "GET":
            raise OSError("polar down")
        return original(request)

    worker._call = reads_fail
    clock[0] = NOW + timedelta(hours=25)
    worker.step(Counter())
    worker.step(Counter())
    assert doc(worker)["state"] == "provider_unknown" and len(polar.patches) == 1
    assert [i["dedupe_key"] for i in items.recorded] == [f"polar_op_unresolved:{OP}"]   # raised once


# ---- the routes ---------------------------------------------------------------------------------------------------

@pytest.fixture
def routes(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from writing_coach import billing_api

    def install(worker, *, user="learner-1", ready=True):
        service = type("Service", (), {"polar_subscriptions": worker})()
        monkeypatch.setattr(billing_api, "_service", service)
        monkeypatch.setattr(billing_api, "_ready", lambda: ready)
        monkeypatch.setattr(billing_api, "current_user_key", lambda: user)
        monkeypatch.setattr(billing_api, "_incarnation", lambda: "inc-1")
        app = FastAPI()
        app.include_router(billing_api.router)
        return TestClient(app)

    return install


def test_the_routes_answer_the_journal_states(routes):
    worker, polar = subs()
    client = routes(worker)
    body = {"price": "pro:month:polar", "operation_id": OP}
    assert client.post("/api/billing/subscription/change", json=body).json()["state"] == "done"
    assert client.post("/api/billing/subscription/change", json=body).status_code == 200
    assert len(polar.patches) == 1
    conflict = client.post("/api/billing/subscription/change", json={**body, "price": "pro:year:polar"})
    assert conflict.status_code == 409 and "operation_conflict" in conflict.text
    view = client.get("/api/billing/subscription").json()
    assert view["plan"] == "plus" and "token" not in str(view)


def test_an_ambiguous_change_answers_202_and_a_declined_card_402(routes):
    worker, polar = subs()
    polar.answers = [TimeoutError("lost")]
    client = routes(worker)
    assert client.post("/api/billing/subscription/change",
                       json={"price": "pro:month:polar", "operation_id": OP}).status_code == 202
    declined, polar2 = subs()
    polar2.answers = [402]
    answer = routes(declined).post("/api/billing/subscription/change",
                                   json={"price": "pro:month:polar", "operation_id": OP})
    assert answer.status_code == 402 and answer.json()["code"] == "payment_failed"


@pytest.mark.parametrize(("path", "body"), [
    ("/api/billing/subscription/cancel", {"reason": "too_expensive"}),
    ("/api/billing/subscription/resume", {}),
    ("/api/billing/subscription/change", {"price": "pro:month:polar"}),
])
def test_every_write_route_requires_an_operation_id(routes, path, body):
    worker, polar = subs()
    assert routes(worker).post(path, json=body).status_code == 422 and polar.patches == []


def test_a_signed_out_request_and_a_closed_change_are_refused(routes):
    worker, polar = subs(Polar(product="prod-pro-month"))
    assert routes(worker, user="legacy").get("/api/billing/subscription").status_code == 401
    refused = routes(worker).post("/api/billing/subscription/change",
                                  json={"price": "plus:month:polar", "operation_id": OP})
    assert refused.status_code == 409 and "change_unavailable" in refused.text and polar.patches == []


# ---- §4.3 invoices -------------------------------------------------------------------------------------------------

class InvoicePolar(Polar):
    def __init__(self, invoice_ready=False, owner="cus_1"):
        super().__init__()
        self.invoice_ready, self.owner, self.generated = invoice_ready, owner, 0

    def __call__(self, request):
        method, url = request["method"], request["url"]
        if url.endswith("/v1/customers/external/inc-1"):
            return 200, {"id": "cus_1"}
        if "/v1/orders/?" in url:
            return 200, {"items": [{"id": "ord_1", "created_at": "2026-10-17T08:21:44Z", "product_id": "prod-plus-month",
                                    "total_amount": 999, "currency": "usd", "status": "paid"}],
                         "pagination": {"max_page": 1}}
        if url.endswith("/invoice") and method == "POST":
            self.generated += 1
            return 202, None
        if url.endswith("/invoice"):
            return (200, {"url": "https://sandbox-api.polar.sh/invoice.pdf"}) if self.invoice_ready else (404, None)
        if "/v1/orders/" in url:
            return 200, {"id": "ord_1", "customer_id": self.owner}
        return super().__call__(request)


def test_the_invoice_list_is_this_accounts_orders():
    worker, _ = subs(InvoicePolar())
    assert worker.invoices("inc-1") == {"items": [{"id": "ord_1", "created_at": "2026-10-17T08:21:44Z", "plan": "plus",
                                                   "period": "month", "amount_minor": 999, "currency": "USD",
                                                   "status": "paid"}], "page": 1, "has_more": False}


def test_an_invoice_is_prepared_asynchronously_and_asked_at_most_once_a_minute():
    clock = [NOW]
    polar = InvoicePolar()
    worker, _ = subs(polar, clock=lambda: clock[0])
    assert worker.invoice("inc-1", "ord_1") == {"state": "preparing"}
    assert worker.invoice("inc-1", "ord_1") == {"state": "preparing"} and polar.generated == 1
    clock[0] = NOW + timedelta(minutes=2)
    worker.invoice("inc-1", "ord_1")
    assert polar.generated == 2
    polar.invoice_ready = True
    assert worker.invoice("inc-1", "ord_1") == {"state": "ready", "url": "https://sandbox-api.polar.sh/invoice.pdf"}


def test_another_accounts_order_is_never_found_by_a_direct_ownership_check():
    worker, polar = subs(InvoicePolar(invoice_ready=True, owner="cus_someone_else"))
    with pytest.raises(SubscriptionRefused, match="order_not_found"):
        worker.invoice("inc-1", "ord_1")
    assert polar.generated == 0


# ---- §3.2 the embedded checkout's origin ------------------------------------------------------------------------------

def test_the_embed_origin_comes_from_configuration_only():
    from writing_coach.billing.gateway import CheckoutIntent

    intent = CheckoutIntent(operation_id="op", incarnation_id="inc-1", price=PRICES["plus:month:polar"],
                            return_url="http://localhost:8031/#/plan?checkout=done", cancel_url="http://localhost:8031/#/plan",
                            embed_origin="http://localhost:8031")  # fmt: skip
    assert POLAR.checkout_request(intent)["json"]["embed_origin"] == "http://localhost:8031"
    plain = CheckoutIntent(operation_id="op", incarnation_id="inc-1", price=PRICES["plus:month:polar"],
                           return_url="r", cancel_url="c")
    assert "embed_origin" not in POLAR.checkout_request(plain)["json"]


def test_the_card_summary_is_brand_last4_and_expiry_only():
    """§4.4, proved on the sandbox 2026-10-18: an organization token reads the customer's payment methods."""

    worker, _ = subs(Polar(customer_id="cus_1"))
    assert worker.view("inc-1")["payment_method"] == {"brand": "visa", "last4": "4242", "exp_month": 8, "exp_year": 2028}
    without, _ = subs(Polar())
    assert without.view("inc-1")["payment_method"] is None


# ---- review of 4a3b0438 -----------------------------------------------------------------------------------------

OP2 = "6f1c1a2e-0000-4000-8000-000000000002"


def test_a_second_operation_on_the_same_subscription_waits_for_the_first():
    """P1-1: one unresolved Polar write per subscription - different operation ids cannot both PATCH."""

    clock = [NOW]
    worker, polar = subs(clock=lambda: clock[0])
    polar.answers = [TimeoutError("lost")]
    assert worker.change("inc-1", "pro:month:polar", OP)["state"] == "provider_unknown"
    with pytest.raises(SubscriptionRefused, match="operation_in_progress"):
        worker.change("inc-1", "pro:year:polar", OP2)
    with pytest.raises(SubscriptionRefused, match="operation_in_progress"):
        worker.cancel("inc-1", None, "6f1c1a2e-0000-4000-8000-000000000003")
    assert len(polar.patches) == 1
    clock[0] = NOW + UNKNOWN_SETTLE + timedelta(seconds=1)
    assert worker.operation("inc-1", OP)["state"] == "not_applied"   # nothing moved on Polar: it did not happen
    assert worker.change("inc-1", "pro:year:polar", OP2)["state"] == "done"   # the fence is free again
    assert len(polar.patches) == 2


def test_a_fence_claimed_by_a_crashed_request_frees_after_the_lease():
    from writing_coach.billing.polar_subscription import FENCE_PREFIX

    clock = [NOW]
    worker, polar = subs(clock=lambda: clock[0])
    worker._settings.set_setting(FENCE_PREFIX + "sub_1", {"operation_id": "ghost", "claimed_at": NOW.isoformat()},
                                 expected_updated_at=None)
    with pytest.raises(SubscriptionRefused, match="operation_in_progress"):
        worker.change("inc-1", "pro:month:polar", OP)
    clock[0] = NOW + LEASE + timedelta(seconds=1)
    assert worker.change("inc-1", "pro:month:polar", OP)["state"] == "done" and len(polar.patches) == 1


def test_two_operations_racing_on_one_subscription_send_one_patch():
    settings, polar = Settings(), Polar()
    workers = [subs(polar, settings=settings)[0] for _ in range(2)]
    barrier = threading.Barrier(2)
    calls = [lambda w: w.change("inc-1", "pro:month:polar", OP), lambda w: w.cancel("inc-1", None, OP2)]
    refused = []

    def run(worker, call):
        barrier.wait()
        try:
            call(worker)
        except SubscriptionRefused as error:
            refused.append(error.code)

    threads = [threading.Thread(target=run, args=(w, c)) for w, c in zip(workers, calls, strict=True)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(polar.patches) + len(refused) == 2 and len(polar.patches) >= 1
    assert set(refused) <= {"operation_in_progress"}


def test_an_unknown_operation_overtaken_on_polar_is_never_called_not_applied():
    """P1-2: A applied and its answer was lost; then the subscription moved again. A's target is gone, but Polar's
    revision moved after A was sent: A stays provider_unknown and goes to an operator at once."""

    from tests.test_billing_polar import Items

    clock = [NOW]
    settings, items = Settings(), Items()
    worker, polar = subs(clock=lambda: clock[0], settings=settings, items=items, index=Index(settings))
    original = polar.__call__

    down = [False]

    def applied_then_lost(request):
        if request["method"] == "PATCH":
            polar.patches.append(request["json"])
            polar.apply(request["json"])
            down[0] = True   # Polar unreachable right after: the first reconcile reads nothing
            raise TimeoutError("answer lost after the charge")
        if down[0]:
            raise OSError("Polar unreachable for the first reconcile")
        return original(request)

    worker._call = applied_then_lost
    assert worker.change("inc-1", "pro:month:polar", OP)["state"] == "provider_unknown"
    # overtaken: changed again on Polar (the portal, another device) after A was sent
    polar.live.update(product_id="prod-pro-year", modified_at="2026-10-17T12:05:00Z")
    down[0] = False
    clock[0] = NOW + UNKNOWN_SETTLE + timedelta(minutes=5)
    assert worker.operation("inc-1", OP)["state"] == "provider_unknown"
    assert doc(worker)["moved"] is True
    worker.step(Counter())
    assert [i["dedupe_key"] for i in items.recorded] == [f"polar_op_unresolved:{OP}"]   # at once, not after 24 h
    with pytest.raises(SubscriptionRefused, match="operation_in_progress"):
        worker.cancel("inc-1", None, OP2)   # the subscription stays fenced: never treated as if nothing happened


def test_an_unreadable_revision_fails_closed():
    clock = [NOW]
    worker, polar = subs(clock=lambda: clock[0])
    polar.answers = [TimeoutError("lost")]
    worker.change("inc-1", "pro:month:polar", OP)
    del polar.live["modified_at"]
    clock[0] = NOW + UNKNOWN_SETTLE + timedelta(minutes=1)
    assert worker.operation("inc-1", OP)["state"] == "provider_unknown"


def test_an_in_app_change_closes_with_sales_but_cancel_and_resume_stay_open(routes):
    """P1-3: BILLING_NEW_SALES=off (or plans not ready) closes the change and its preview; cancel stays open."""

    worker, polar = subs()
    closed = routes(worker, ready=False)
    for path, body in (("/api/billing/subscription/change", {"price": "pro:month:polar", "operation_id": OP}),
                       ("/api/billing/subscription/change/preview", {"price": "pro:month:polar"})):
        answer = closed.post(path, json=body)
        assert answer.status_code == 503 and "billing_not_ready" in answer.text
    assert polar.patches == []
    assert closed.post("/api/billing/subscription/cancel", json={"operation_id": OP2}).status_code == 200
    assert polar.patches == [{"cancel_at_period_end": True}]


def test_the_invoice_marker_is_claimed_before_polar_is_asked():
    """P2: two concurrent first requests ask Polar to generate once."""

    from writing_coach.persistence.platform_repository import SettingConflict

    polar = InvoicePolar()
    worker, _ = subs(polar)
    original = worker._settings.set_setting

    def lose_the_race(key, value, **kwargs):
        if key.startswith("billing.polar.invoice_asked."):
            raise SettingConflict(key)
        return original(key, value, **kwargs)

    worker._settings.set_setting = lose_the_race
    assert worker.invoice("inc-1", "ord_1") == {"state": "preparing"}
    assert polar.generated == 0   # the winner asks; the loser does not


def test_a_deleted_accounts_terminal_operations_are_scrubbed():
    settings = Settings()
    index = Index(settings)
    index.incarnation_deleted = lambda incarnation: incarnation == "inc-1"
    worker, _ = subs(settings=settings, index=index)
    worker.change("inc-1", "pro:month:polar", OP)
    worker.step(Counter())
    assert doc(worker) is None
