"""PR-MON-3 Billing Orders + Reconciliation Safety, without a database: anomalies recorded before acknowledging,
the 503 when they cannot be, Polar refunds, the per-kind resolution rule, the critical gateway block, the payOS
lookup answer and the admin routes. The PostgreSQL proofs are in `test_billing_reconciliation_postgres.py`."""

from __future__ import annotations

import io
import json
import urllib.error
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.test_billing import NOW, PAYOS, POLAR, FakeCommerce, FakeItems, FakeOrders, payos_body, polar_request, service
from tests.test_billing_price_integrity import PLUS_USD, PLUS_VND, billing, facts, start
from writing_coach import billing_api
from writing_coach.billing import readiness
from writing_coach.billing.payos import parse_lookup
from writing_coach.billing.reconciler import RateLimited, Settings, build_lookups, get_json
from writing_coach.persistence.billing_reconciliation_repository import (
    CRITICAL,
    DISMISSABLE,
    KINDS,
    MONEY,
    RESOLUTION_RULES,
    ResolutionRefused,
    check_resolution,
)


class Orders(FakeOrders):
    def __init__(self, status):
        super().__init__()
        self.status = status

    def mark_paid(self, **kwargs):
        self.paid.append(kwargs)
        return {"status": self.status, "incarnation_id": "inc-1", "order_id": "order-1"}


# ---- a verified money anomaly is recorded before it is acknowledged --------------------------------------------

@pytest.mark.parametrize(("status", "kind"), [
    ("unknown_order", "payment_unknown_order"), ("mismatch", "payment_mismatch"),
    ("not_payable", "payment_not_payable"), ("paid_deleted_account", "paid_deleted_account"),
])  # fmt: skip
def test_every_payment_anomaly_is_kept_as_its_reconciliation_item(status, kind):
    items, commerce = FakeItems(), FakeCommerce()
    outcome = service(commerce, Orders(status), items).handle_webhook("payos", {}, payos_body())
    assert outcome.status == status and commerce.events == []
    [item] = items.recorded
    assert item["kind"] == kind and item["gateway"] == "payos"
    assert item["reported_order_code"] == 100001 and item["reported_amount_minor"] == 99_000  # the provider's facts


def test_a_payment_for_an_order_code_orena_cannot_read_is_still_recorded():
    body = json.loads(payos_body())
    body["data"]["orderCode"] = "not-a-number"
    from writing_coach.billing.payos import signing_string
    from writing_coach.billing.gateway import hmac_sha256_hex

    body["signature"] = hmac_sha256_hex("checksum-for-tests", signing_string(body["data"]).encode())
    items = FakeItems()
    assert service(items=items).handle_webhook("payos", {}, json.dumps(body).encode()).status == "unknown_order"
    assert items.recorded[0]["kind"] == "payment_unknown_order"


def test_a_subscription_event_naming_no_checkout_is_kept_for_an_operator():
    items = FakeItems()
    headers, body = polar_request({"type": "subscription.updated", "data": {"id": "sub_x", "status": "active",
                                                                             "modified_at": "2026-10-05T11:00:00Z"}})
    assert service(items=items).handle_webhook("polar", headers, body).status == "unknown"
    assert [item["kind"] for item in items.recorded] == ["event_undecided"]


class Undecided(FakeCommerce):
    def record_event(self, **kwargs):
        return {"status": "foreign_incarnation"}


def test_an_undecidable_subscription_event_is_kept_for_an_operator():
    items = FakeItems()
    commerce = Undecided(mapped={"incarnation_id": "inc-owner"})
    headers, body = polar_request({"type": "subscription.updated", "data": {"id": "sub_1", "status": "active",
                                                                             "modified_at": "2026-10-05T11:00:00Z",
                                                                             "product_id": "prod_123"}})
    assert service(commerce, items=items).handle_webhook("polar", headers, body).status == "foreign_incarnation"
    assert items.recorded[0]["kind"] == "event_undecided" and items.recorded[0]["incarnation_id"] == "inc-owner"


class ResolvingItems(FakeItems):
    def __init__(self):
        super().__init__()
        self.resolved: list = []

    def auto_resolve(self, **kwargs):
        self.resolved.append(kwargs)
        return True


@pytest.mark.parametrize(("mapped", "detail", "resolved"), [
    ({"incarnation_id": "inc-1", "state": "ended"}, "refund_matched", True),
    ({"incarnation_id": "inc-1", "state": "active"}, "refund_subscription_live", False),
    ({"incarnation_id": "inc-1"}, "refund_subscription_live", False),  # no known state: kept open, never assumed ended
    (None, "refund_unmatched", False),
])  # fmt: skip
def test_a_polar_refund_is_recorded_and_changes_no_access(mapped, detail, resolved):
    """Access follows the subscription's own events (H4). A refund ends the plan at once (owner, 2026-10-19,
    D-MON-035) by the operator revoking the subscription on Polar: while it is still live, the item stays open."""

    items, commerce = ResolvingItems(), FakeCommerce(mapped=mapped)
    headers, body = polar_request({"type": "refund.created", "data": {
        "id": "re_1", "subscription_id": "sub_1", "order_id": "ord_1", "amount": 1999, "currency": "usd",
        "status": "succeeded"}})  # fmt: skip
    outcome = service(commerce, items=items).handle_webhook("polar", headers, body)
    assert outcome.status == "recorded" and outcome.detail == detail
    [item] = items.recorded
    assert item["kind"] == "provider_refund" and item["dedupe_key"] == "re_1"
    assert item["incarnation_id"] == (mapped or {}).get("incarnation_id")
    assert bool(items.resolved) is resolved
    if detail == "refund_subscription_live":
        assert "revoke" in item["reason"]
    assert commerce.events == []  # the refund itself never changes access


class Unrecordable(FakeItems):
    def record(self, **kwargs):
        raise RuntimeError("database down")


def test_an_anomaly_that_cannot_be_recorded_is_not_acknowledged(monkeypatch):
    app = FastAPI()
    app.include_router(billing_api.router)
    monkeypatch.setattr(billing_api, "_service", service(orders=Orders("mismatch"), items=Unrecordable()))
    answer = TestClient(app).post("/api/billing/webhooks/payos", content=payos_body())
    assert answer.status_code == 503 and answer.json() == {"ok": False}  # the provider delivers it again


def test_a_service_without_reconciliation_items_acknowledges_no_anomaly():
    bare = service(orders=Orders("mismatch"))
    bare._items = None
    with pytest.raises(RuntimeError):
        bare.handle_webhook("payos", {}, payos_body())


# ---- the per-kind resolution rule (P1-3, H6) ----------------------------------------------------------------

def test_every_kind_has_a_rule_and_only_obligation_free_kinds_are_dismissable():
    assert set(RESOLUTION_RULES) == KINDS
    assert DISMISSABLE.isdisjoint(CRITICAL | MONEY)


@pytest.mark.parametrize("kind", sorted(CRITICAL | MONEY))
def test_a_critical_or_money_item_is_never_dismissed(kind):
    with pytest.raises(ResolutionRefused) as refused:
        check_resolution(kind, resolution="dismissed", outcome=None, reference=None, note="nothing to do")
    assert refused.value.code == "not_dismissable"


def test_paid_without_access_is_closed_only_by_the_reconciler():
    for outcome in ("entitlement_synced", "payment_recorded", "obligation_waived"):
        with pytest.raises(ResolutionRefused) as refused:
            check_resolution("entitlement_unsynced", resolution="resolved", outcome=outcome, reference="r", note="done")
        assert refused.value.code == "reconciler_only"


@pytest.mark.parametrize(("kind", "outcome", "reference", "code"), [
    ("provider_paid_unrecorded", "obligation_waived", "x", "outcome_not_allowed"),
    ("provider_paid_unrecorded", "payment_recorded", "FT9", "outcome_not_allowed"),  # the reconciler's only (P1-2)
    ("provider_state_unresolved", "payment_recorded", "FT9", "outcome_not_allowed"),
    ("provider_paid_unrecorded", "refund_confirmed", "", "reference_required"),
    ("paid_deleted_account", "payment_matched", "x", "outcome_not_allowed"),
    ("paid_deleted_account", "refund_confirmed", None, "reference_required"),
    ("payment_unknown_order", None, None, "outcome_not_allowed"),
])  # fmt: skip
def test_a_money_obligation_is_closed_only_with_what_happened(kind, outcome, reference, code):
    with pytest.raises(ResolutionRefused) as refused:
        check_resolution(kind, resolution="resolved", outcome=outcome, reference=reference, note="operator note")
    assert refused.value.code == code


def test_allowed_resolutions_pass_and_a_note_is_always_required():
    check_resolution("paid_deleted_account", resolution="resolved", outcome="refund_confirmed", reference="FT1", note="ok")
    check_resolution("paid_deleted_account", resolution="resolved", outcome="obligation_waived", reference=None,
                     note="below the bank's refund minimum; recorded by finance")  # fmt: skip
    check_resolution("event_undecided", resolution="dismissed", outcome=None, reference=None, note="test event")
    with pytest.raises(ResolutionRefused):
        check_resolution("event_undecided", resolution="dismissed", outcome=None, reference=None, note="  ")


# ---- an open critical item closes new checkouts on its gateway (P1-3) ------------------------------------------

class Critical(FakeItems):
    def __init__(self, counts):
        super().__init__()
        self.counts = counts

    def critical_by_gateway(self):
        if self.counts is None:
            raise RuntimeError("cannot read")
        return self.counts

    def summary(self):
        return {"open": 1, "open_by_kind": {"entitlement_unsynced": 1}, "critical_by_gateway": self.critical_by_gateway()}


def with_items(service_, items):
    service_._items = items
    return service_


def test_an_open_critical_item_blocks_its_gateway_and_readiness_says_why():
    blocked = with_items(billing([PLUS_USD]), Critical({"polar": 1}))
    assert blocked.offered() == []
    assert start(blocked) == "reconciliation_critical"
    report = readiness.report(facts(service=blocked))
    # PR-MON-8 §14.4: the plans capability says why; the top level says only that no capability is ready
    assert report["ready"] is False and report["blockers"] == ["no_billing_capability_ready"]
    assert "reconciliation_critical" in report["capabilities"]["plans"]["blockers"]
    assert report["gateways"]["polar"]["reconciliation_critical"] == 1 and report["gateways"]["polar"]["ready"] is False
    assert report["reconciliation"]["critical_by_gateway"] == {"polar": 1}


def test_a_critical_item_on_another_gateway_does_not_block_this_one():
    other = with_items(billing([PLUS_USD]), Critical({"payos": 2}))
    assert [offer["key"] for offer in other.offered()] == ["plus:month:polar"]
    assert start(other).startswith("https://")
    assert readiness.report(facts(service=other))["capabilities"]["plans"] == {"ready": True, "blockers": []}


def test_unreadable_reconciliation_state_sells_nothing():
    unknown = with_items(billing([PLUS_USD]), Critical(None))
    assert unknown.offered() == [] and start(unknown) == "reconciliation_critical"
    report = readiness.report(facts(service=unknown))
    assert report["ready"] is False and "reconciliation_unavailable" in report["capabilities"]["plans"]["blockers"]


def test_a_critical_refusal_is_a_retryable_503(monkeypatch):
    app = FastAPI()
    app.include_router(billing_api.router)
    blocked = with_items(billing([PLUS_USD]), Critical({"polar": 1}))
    monkeypatch.setattr(billing_api, "_service", blocked)
    monkeypatch.setattr(billing_api, "_ready", lambda: True)
    monkeypatch.setattr(billing_api, "current_user_key", lambda: "learner-1")
    monkeypatch.setattr(billing_api, "_incarnation", lambda: "inc-1")
    answer = TestClient(app).post("/api/billing/checkout", json={
        "price": "plus:month:polar", "operation_id": "6f1c1a2e-0000-4000-8000-000000000001", "amount_minor": 999,
        "currency": "USD"})  # fmt: skip
    assert answer.status_code == 503 and "reconciliation_critical" in answer.text


# ---- the payOS lookup -------------------------------------------------------------------------------------

def lookup_answer(status="PAID", *, paid=199_000, transactions=None, code="00"):
    return {"code": code, "desc": "success", "data": {
        "id": "plink", "orderCode": 100001, "amount": 199_000, "amountPaid": paid, "status": status,
        "transactions": transactions if transactions is not None else [{"reference": "FT9", "amount": paid}]}}


def test_a_lookup_answer_is_read_without_guessing():
    answer = parse_lookup(lookup_answer())
    assert (answer.status, answer.amount_paid, answer.reference, answer.documented) == ("PAID", 199_000, "FT9", True)
    two = parse_lookup(lookup_answer(transactions=[{"reference": "A"}, {"reference": "B"}]))
    assert two.reference is None  # two transfers: no single reference to keep
    assert parse_lookup(lookup_answer(transactions=[{"ref": "x"}])).reference is None
    assert parse_lookup(lookup_answer("EXPIRED")).documented is False
    with pytest.raises(ValueError):
        parse_lookup(lookup_answer(code="101"))
    with pytest.raises(ValueError):
        parse_lookup({"code": "00", "data": None})


def test_the_lookup_is_a_read_only_get_of_one_order():
    request = PAYOS.lookup_request(100001)
    assert request["method"] == "GET" and request["url"].endswith("/v2/payment-requests/100001")
    assert "json" not in request


def test_the_payment_link_expires_with_its_order():
    from writing_coach.billing.gateway import CheckoutIntent

    intent = CheckoutIntent(operation_id="op", incarnation_id="inc", price=PLUS_VND, return_url="https://o/r",
                            cancel_url="https://o/c")  # fmt: skip
    request = PAYOS.checkout_request(intent, order_code=100001, description="OR100001", expires_at=NOW + timedelta(minutes=30))
    assert request["json"]["expiredAt"] == int((NOW + timedelta(minutes=30)).timestamp())


def test_only_payos_has_a_lookup():
    assert set(build_lookups({"payos": PAYOS, "polar": POLAR}, fetch=lambda request: lookup_answer())) == {"payos"}


def test_a_429_is_rate_limited_with_the_providers_wait(monkeypatch):
    def refuse(*args, **kwargs):
        raise urllib.error.HTTPError("https://x", 429, "Too Many Requests", {"Retry-After": "30"}, io.BytesIO(b""))

    monkeypatch.setattr("urllib.request.urlopen", refuse)
    with pytest.raises(RateLimited) as limited:
        get_json(PAYOS.lookup_request(1))
    assert limited.value.retry_after == 30.0


def test_reconciler_settings_have_safe_floors():
    settings = Settings.from_env({"BILLING_PULL_PER_TICK": "0", "BILLING_RECONCILE_INTERVAL_SECONDS": "x",
                                  "BILLING_PULL_HORIZON_DAYS": "0"})
    assert settings.per_tick == 1 and settings.interval == 60 and settings.horizon == timedelta(days=1)


# ---- the admin routes -------------------------------------------------------------------------------------

class AdminItems(FakeItems):
    def items(self, *, state=None, kind=None):
        return [{"id": "11111111-1111-4111-8111-111111111111", "kind": "payment_mismatch", "state": "open",
                 "first_seen_at": NOW}]

    def summary(self):
        return {"open": 1, "open_by_kind": {"payment_mismatch": 1}, "critical_by_gateway": {}}

    def resolve(self, item_id, **kwargs):
        if kwargs["resolution"] == "dismissed":
            raise ResolutionRefused("not_dismissable")
        return {"id": item_id, "state": "resolved", "resolved_by": kwargs["actor"]}


@pytest.fixture
def admin_client(monkeypatch):
    app = FastAPI()
    app.include_router(billing_api.router)
    monkeypatch.setattr(billing_api, "_admin", lambda request: {"google_sub": "admin-1"})
    monkeypatch.setattr(billing_api, "_items", AdminItems())
    monkeypatch.setattr(billing_api, "_reconcile", lambda: {"looked_up": 2})
    return TestClient(app)


def test_an_administrator_reads_the_items_and_closes_one_under_its_rule(admin_client):
    listing = admin_client.get("/api/admin/billing/reconciliation?state=open").json()
    assert listing["summary"]["open"] == 1 and listing["items"][0]["first_seen_at"] == NOW.isoformat()
    item = "11111111-1111-4111-8111-111111111111"
    resolved = admin_client.post(f"/api/admin/billing/reconciliation/{item}/resolve", json={
        "resolution": "resolved", "outcome": "refund_confirmed", "reference": "FT1", "note": "returned by transfer"})
    assert resolved.status_code == 200 and resolved.json()["item"]["resolved_by"] == "admin-1"
    refused = admin_client.post(f"/api/admin/billing/reconciliation/{item}/resolve", json={
        "resolution": "dismissed", "note": "not needed"})
    assert refused.status_code == 409 and "not_dismissable" in refused.text
    assert admin_client.post("/api/admin/billing/reconciliation/not-a-uuid/resolve", json={
        "resolution": "resolved", "outcome": "recorded", "note": "x y z"}).status_code == 404
    assert admin_client.post("/api/admin/billing/reconcile").json() == {"ran": True, "counts": {"looked_up": 2}}


def test_the_reconciliation_routes_are_admin_only(admin_client, monkeypatch):
    from fastapi import HTTPException

    def not_admin(request):
        raise HTTPException(403, "Platform administrator access required")

    monkeypatch.setattr(billing_api, "_admin", not_admin)
    assert admin_client.get("/api/admin/billing/reconciliation").status_code == 403
    assert admin_client.post("/api/admin/billing/reconcile").status_code == 403
