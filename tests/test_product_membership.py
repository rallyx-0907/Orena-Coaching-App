"""D-154: an administrator sets an account's role and plan by hand."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from writing_coach.product.membership import (
    MembershipConflict,
    MembershipInvalid,
    apply_change,
    manual_expired,
)
from writing_coach.product.service import ProductService

ADMIN_KEY = "admin-sub"
FUTURE = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
PAST = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()


class Store:
    def __init__(self, **account):
        self.account = {
            "id": "11111111-1111-1111-1111-111111111111", "user_key": "learner-sub", "email": "learner@example.test",
            "role": "user", "plan_id": None, "status": None, "provider": None, "until": None, **account,
        }

    def account_membership(self, user_id):
        return dict(self.account) if user_id == self.account["id"] else None

    audits = None

    def apply_membership(self, user_id, *, role=None, plan=..., until=None, audit=None):
        self.audits = (self.audits or []) + [audit]
        if role is not None:
            self.account["role"] = role
        if plan is ...:
            return
        if plan is None:
            if self.account["provider"] == "manual":
                self.account.update(plan_id=None, status=None, provider=None, until=None)
            return
        self.account.update(plan_id=plan, status="active", provider="manual", until=until.isoformat() if until else None)


def change(store, body, **kwargs):
    return apply_change(store, store.account["id"], body, actor_key=kwargs.get("actor", ADMIN_KEY),
                        protected_emails=kwargs.get("protected", set()))


def test_set_role_and_plan():
    store = Store()
    result = change(store, {"role": "admin", "plan_id": "pro", "until": FUTURE})
    assert result["applied"]["role"] == "admin"
    assert result["applied"]["plan_id"] == "pro"
    assert result["account"]["role"] == "admin"
    assert result["account"]["provider"] == "manual"
    assert result["account"]["until"]


def test_free_removes_the_manual_plan_and_ignores_a_date():
    store = Store(plan_id="plus", status="active", provider="manual")
    result = change(store, {"plan_id": "free", "until": FUTURE})
    assert result["account"]["plan_id"] is None
    assert result["applied"]["until"] is None


def test_an_admin_cannot_change_their_own_role():
    store = Store(user_key=ADMIN_KEY, role="admin")
    with pytest.raises(MembershipConflict, match="own role"):
        change(store, {"role": "user"})


def test_a_configured_admin_address_stays_admin():
    store = Store(role="admin", email="Owner@Example.test")
    with pytest.raises(MembershipConflict, match="configured"):
        change(store, {"role": "user"}, protected={"owner@example.test"})


def test_a_billing_owned_plan_is_not_overwritten():
    store = Store(plan_id="pro", status="active", provider="polar")
    with pytest.raises(MembershipConflict, match="billing"):
        change(store, {"plan_id": "plus"})


@pytest.mark.parametrize("body, message", [
    ({"role": "owner"}, "Unknown role"),
    ({"plan_id": "gold"}, "Unknown plan"),
    ({"plan_id": "plus", "until": "not a date"}, "ISO"),
    ({"plan_id": "plus", "until": PAST}, "future"),
])
def test_invalid_changes_are_refused(body, message):
    with pytest.raises(MembershipInvalid, match=message):
        change(Store(), body)


def test_an_unknown_account_is_a_lookup_error():
    with pytest.raises(LookupError):
        apply_change(Store(), "nope", {"role": "admin"}, actor_key=ADMIN_KEY, protected_emails=set())


def test_an_unchanged_role_applies_nothing():
    assert change(Store(), {"role": "user"})["applied"] == {}


@dataclass
class Subscription:
    plan_id: str
    status: str
    provider: str = "manual"
    current_period_end: str = ""


class Repo:
    def __init__(self, subscription):
        self.subscription = subscription

    def get_subscription(self, user_key):
        return self.subscription

    def monthly_usage(self, *, user_key, feature):
        return 0


def test_a_manual_plan_ends_on_its_date():
    assert manual_expired(Subscription("plus", "active", current_period_end=PAST)) is True
    assert manual_expired(Subscription("plus", "active", current_period_end=FUTURE)) is False
    assert manual_expired(Subscription("plus", "active", provider="polar", current_period_end=PAST)) is False
    ended = ProductService(Repo(Subscription("plus", "active", current_period_end=PAST))).account_state("u")
    assert ended["plan"]["id"] == "free"
    live = ProductService(Repo(Subscription("plus", "active", current_period_end=FUTURE))).account_state("u")
    assert live["plan"]["id"] == "plus"
    assert ProductService(Repo(Subscription("pro", "active"))).plan_for_user("u").id == "pro"


def test_membership_routes(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import writing_coach.product.api as product_api

    store = Store()
    monkeypatch.setattr(product_api, "require_admin", lambda request: {"google_sub": ADMIN_KEY, "email": "a@example.test"})
    monkeypatch.setattr(product_api.product_service, "repository", store)
    app = FastAPI()
    app.include_router(product_api.router)
    client = TestClient(app)
    path = f"/api/product/admin/accounts/{store.account['id']}/membership"

    body = client.get(path).json()
    assert body["roles"] == ["user", "admin"]
    assert [plan["id"] for plan in body["plans"]] == ["free", "plus", "pro"]
    assert client.put(path, json={"plan_id": "plus", "until": FUTURE}).json()["account"]["plan_id"] == "plus"
    assert client.put(path, json={"role": "owner"}).status_code == 422
    store.account["user_key"] = ADMIN_KEY
    assert client.put(path, json={"role": "admin"}).status_code == 409
    assert client.get("/api/product/admin/accounts/nope/membership").status_code == 404


def test_a_refused_plan_change_does_not_apply_the_role_either():
    """Review P1: {role, plan} with a refused plan must not leave the role changed (and unaudited)."""
    billing = Store(plan_id="pro", status="active", provider="polar")
    with pytest.raises(MembershipConflict):
        change(billing, {"role": "admin", "plan_id": "plus"})
    assert billing.account["role"] == "user"
    past = Store()
    with pytest.raises(MembershipInvalid):
        change(past, {"role": "admin", "plan_id": "plus", "until": PAST})
    assert past.account["role"] == "user"
