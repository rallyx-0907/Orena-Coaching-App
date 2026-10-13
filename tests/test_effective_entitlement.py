"""PR-MON-1 / D-MON-006: one canonical effective entitlement.

A verified payment is recorded in `commerce_subscriptions` (billing); a hand-set plan lives on the legacy
`subscriptions` row (D-154). The effective plan is decided once, by `writing_coach.product.entitlement.resolve`, and
the Plan screen (`account_state`), quota admission and the language limit all read that one answer.

Precedence, pinned here so it cannot drift:
  1. a valid billing grant (state active/trialing, `paid_through` absent or in the future; or a recoverable state
     inside its grace - Polar `past_due`, 2 days from `paid_through`, D-MON-011)
  2. a valid manual / legacy subscription (today's rule, unchanged)
  3. Free
The billing source here is a TEST DOUBLE of `CommerceEntitlementSource`; the PostgreSQL read is proved in
`tests/test_effective_entitlement_postgres.py`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from writing_coach.product import billing_grace, catalog
from writing_coach.product.billing_grace import NO_GRACE
from writing_coach.product.entitlement import resolve
from writing_coach.product.membership import MembershipConflict, apply_change
from writing_coach.product.service import ProductService

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
FUTURE = NOW + timedelta(days=20)
PAST = NOW - timedelta(seconds=1)


@dataclass(frozen=True)
class Legacy:
    """The legacy `subscriptions` row (`SubscriptionRecord`'s fields the service reads)."""

    plan_id: str
    status: str
    provider: str = ""
    current_period_end: str = ""
    user_key: str = "learner"
    external_customer_id: str = ""
    external_subscription_id: str = ""
    updated_at: str = ""


def manual(plan_id: str, until: datetime | None = None) -> Legacy:
    return Legacy(plan_id, "active", provider="manual", current_period_end=until.isoformat() if until else "")


def billing(plan_id: str, state: str = "active", *, provider: str = "polar", paid_through: datetime | None = FUTURE,
            external: str = "sub_1", reconciliation: str = "current") -> dict:
    """A `commerce_subscriptions` row as `CommerceEntitlementSource.subscription_for_user` returns it."""
    return {"provider": provider, "plan_id": plan_id, "state": state, "paid_through": paid_through,
            "cancel_at_period_end": False, "external_subscription_id": external,
            "reconciliation_state": reconciliation}


def prepaid(plan_id: str, state: str = "active", *, paid_through: datetime | None = FUTURE) -> dict:
    """What `BillingService.sync_prepaid` records for payOS: subscription `prepaid:<incarnation>`."""
    return billing(plan_id, state, provider="payos", paid_through=paid_through, external="prepaid:inc-1")


class LegacyRepo:
    def __init__(self, row: Legacy | None = None, *, fail: bool = False):
        self.row, self.fail, self.reads = row, fail, 0

    def get_subscription(self, user_key):
        self.reads += 1
        if self.fail:
            raise RuntimeError("legacy store down")
        return self.row


class BillingSource:
    def __init__(self, row: dict | None = None, *, fail: bool = False):
        self.row, self.fail, self.reads = row, fail, 0

    def subscription_for_user(self, user_key):
        self.reads += 1
        if self.fail:
            raise RuntimeError("commerce store down")
        return None if self.row is None else dict(self.row)


GRACE = billing_grace.current({})   # the approved Billing v1 policy: Polar past_due, 48 hours


def service(legacy: Legacy | None = None, bill: dict | None = None, *, billing_source: BillingSource | None = None,
            usage=None, grace=GRACE) -> ProductService:
    source = billing_source if billing_source is not None else (BillingSource(bill) if bill is not None else None)
    return ProductService(LegacyRepo(legacy), usage=usage, billing=source, clock=lambda: NOW, grace=lambda: grace)


@pytest.fixture(autouse=True)
def _default_catalogue():
    catalog.configure_plan_store(None)
    yield
    catalog.configure_plan_store(None)


# ------------------------------------------------------------------------------------------ resolution --

def test_an_active_payos_prepaid_subscription_is_its_paid_plan():
    effective = service(None, prepaid("plus")).entitlement("learner")
    assert (effective.plan_id, effective.source, effective.active, effective.status) == ("plus", "billing", True, "active")
    assert effective.valid_until == FUTURE
    assert service(None, prepaid("plus")).plan_for_user("learner").id == "plus"


def test_an_active_polar_subscription_is_its_paid_plan():
    assert service(None, billing("pro")).plan_for_user("learner").id == "pro"
    assert service(None, billing("pro", "trialing")).plan_for_user("learner").id == "pro"


def test_a_billing_grant_without_a_validity_boundary_is_valid():
    assert service(None, billing("pro", paid_through=None)).plan_for_user("learner").id == "pro"


def test_a_valid_manual_grant_is_its_plan():
    effective = service(manual("pro", FUTURE)).entitlement("learner")
    assert (effective.plan_id, effective.source, effective.active) == ("pro", "manual", True)


def test_an_expired_manual_grant_is_free():
    effective = service(manual("pro", PAST)).entitlement("learner")
    assert (effective.plan_id, effective.source, effective.active) == ("free", "none", False)


def test_a_cancelled_or_ended_billing_subscription_is_free():
    for state in ("ended", "none"):
        assert service(None, billing("pro", state)).plan_for_user("learner").id == "free", state
    ended = service(None, billing("pro", "ended")).entitlement("learner")
    assert (ended.source, ended.status, ended.active) == ("none", "ended", False)


def test_a_billing_grant_past_its_paid_through_is_ended():
    """Commerce architecture §3: a verified grant is usable only until its explicit validity boundary."""
    effective = service(None, prepaid("plus", paid_through=PAST)).entitlement("learner")
    assert (effective.plan_id, effective.active, effective.status) == ("free", False, "ended")
    assert service(None, billing("pro", paid_through=NOW)).plan_for_user("learner").id == "free", "the boundary is exclusive"


def test_a_fully_refunded_domestic_purchase_is_free():
    """`sync_prepaid` after the last order is refunded: state ended, paid_through = the refund time."""
    refunded = prepaid("plus", "ended", paid_through=NOW - timedelta(minutes=5))
    effective = service(None, refunded).entitlement("learner")
    assert (effective.plan_id, effective.active, effective.status) == ("free", False, "ended")


def test_no_entitlement_is_free():
    effective = service().entitlement("learner")
    assert (effective.plan_id, effective.source, effective.active, effective.status) == ("free", "none", False, "inactive")
    assert service(None, None, billing_source=BillingSource(None)).entitlement("learner") == effective


@pytest.mark.parametrize("state", ["paused", "pending", "unknown"])
def test_a_billing_state_without_an_approved_grace_policy_grants_nothing(state):
    effective = service(None, billing("pro", state, paid_through=NOW - timedelta(hours=1))).entitlement("learner")
    assert (effective.plan_id, effective.active, effective.status) == ("free", False, state)
    assert effective.billing_live is (state != "unknown")


# ----------------------------------------------------------------------------- grace (D-MON-011) --

def test_a_polar_past_due_subscription_keeps_its_plan_inside_the_two_day_grace():
    failed = NOW - timedelta(days=1)
    effective = service(None, billing("pro", "past_due", paid_through=failed)).entitlement("learner")
    assert (effective.plan_id, effective.source, effective.status, effective.active) == ("pro", "billing", "past_due", True)
    assert effective.valid_until == failed + timedelta(hours=48)


def test_a_polar_past_due_subscription_reads_free_when_the_grace_ends():
    for failed in (NOW - timedelta(hours=48), NOW - timedelta(days=3)):
        effective = service(None, billing("pro", "past_due", paid_through=failed)).entitlement("learner")
        assert (effective.plan_id, effective.active, effective.status) == ("free", False, "past_due"), failed
        assert effective.billing_live, "still billing-owned: Polar is retrying, an Admin cannot hand-set a plan"
    just_inside = NOW - timedelta(hours=48) + timedelta(seconds=1)
    assert service(None, billing("pro", "past_due", paid_through=just_inside)).plan_for_user("learner").id == "pro"


def test_a_recovered_payment_restores_the_plan_from_polars_state():
    lapsed = service(None, billing("pro", "past_due", paid_through=NOW - timedelta(days=3)))
    recovered = service(None, billing("pro", "active", paid_through=NOW + timedelta(days=30)))
    assert (lapsed.plan_for_user("learner").id, recovered.plan_for_user("learner").id) == ("free", "pro")


def test_a_past_due_subscription_without_an_anchor_has_no_grace():
    assert service(None, billing("pro", "past_due", paid_through=None)).plan_for_user("learner").id == "free"


def test_grace_is_the_policys_not_the_resolvers():
    row = billing("pro", "past_due", paid_through=NOW - timedelta(days=3))
    assert resolve(legacy=None, billing=row, now=NOW).plan_id == "free", "no policy, no grace"
    assert resolve(legacy=None, billing=row, now=NOW, grace=billing_grace.current({billing_grace.ENV: "168"})).plan_id == "pro"
    one_hour = billing("pro", "past_due", paid_through=NOW - timedelta(hours=1))
    assert resolve(legacy=None, billing=one_hour, now=NOW, grace=billing_grace.current({billing_grace.ENV: "0"})).plan_id == "free"
    assert service(None, row, grace=NO_GRACE).plan_for_user("learner").id == "free"


def test_only_polar_past_due_has_grace():
    recent = NOW - timedelta(hours=1)
    assert service(None, billing("pro", "past_due", provider="payos", paid_through=recent)).plan_for_user("learner").id == "free"
    for state in ("paused", "pending"):
        assert service(None, billing("pro", state, paid_through=recent)).plan_for_user("learner").id == "free", state


@pytest.mark.parametrize(("raw", "hours"), [(None, 48), ("", 48), ("48", 48), ("0", 0), ("336", 336), ("337", 48),
                                            ("-1", 48), ("two days", 48), ("1.5", 48)])
def test_the_grace_hours_come_from_the_environment_within_range(raw, hours):
    env = {} if raw is None else {billing_grace.ENV: raw}
    assert billing_grace.past_due_hours(env) == hours
    window = billing_grace.current(env).window("polar", "past_due")
    assert window == (timedelta(hours=hours) if hours else None)


def test_an_unknown_plan_id_on_a_billing_grant_is_reported_unknown_and_admits_as_free():
    """Same as an unknown plan on the legacy row today: never promoted, never shown as a real plan."""
    svc = service(None, billing("enterprise"))
    assert svc.plan_for_user("learner").id == "free"
    state = svc.account_state("learner")
    assert (state["plan_state"], state["subscription"]["state"], state["plan"]["id"]) == ("unknown", "unknown", "free")


# ------------------------------------------------------------------------------------------ precedence --

def test_precedence_a_valid_billing_grant_outranks_a_manual_grant():
    """D-154: a subscription billing owns is never overridden by hand - also when the manual plan ranks higher."""
    effective = service(manual("pro", FUTURE), billing("plus")).entitlement("learner")
    assert (effective.plan_id, effective.source) == ("plus", "billing")


def test_precedence_a_billing_subscription_that_grants_nothing_falls_through_to_a_valid_manual_grant():
    for row in (billing("plus", "ended"), billing("plus", "past_due", paid_through=NOW - timedelta(days=3)),
                billing("plus", "paused"), prepaid("plus", paid_through=PAST)):
        effective = service(manual("pro", FUTURE), row).entitlement("learner")
        assert (effective.plan_id, effective.source) == ("pro", "manual"), row["state"]


def test_precedence_a_valid_billing_grant_outranks_a_legacy_provider_row():
    effective = service(Legacy("pro", "active", provider="stripe"), billing("plus")).entitlement("learner")
    assert (effective.plan_id, effective.source) == ("plus", "billing")
    legacy_only = service(Legacy("pro", "active", provider="stripe")).entitlement("learner")
    assert (legacy_only.plan_id, legacy_only.source) == ("pro", "legacy")


def test_precedence_the_placeholder_billing_row_is_absent():
    """`commerce_repository._current_row` places `state='none'` before the first event decides anything."""
    effective = service(manual("pro", FUTURE), billing("free", "none", provider="")).entitlement("learner")
    assert (effective.plan_id, effective.source, effective.billing_live) == ("pro", "manual", False)


def test_the_pure_resolver_is_the_whole_decision():
    """`resolve` is a pure function of the two rows and the clock: the service adds only the reads."""
    assert resolve(legacy=None, billing=billing("pro"), now=NOW).plan_id == "pro"
    assert resolve(legacy=manual("plus", FUTURE), billing=None, now=NOW).plan_id == "plus"
    assert resolve(legacy=None, billing=None, now=NOW).plan_id == "free"
    assert resolve(legacy=manual("plus", FUTURE), billing=billing("pro"), now=FUTURE + timedelta(days=1)).plan_id == "free"


# --------------------------------------------------------------------------- one answer for every reader --

def test_the_plan_screen_reads_the_billing_grant():
    state = service(None, prepaid("plus")).account_state("learner")
    assert state["plan"]["id"] == "plus"
    assert (state["plan_state"], state["subscription"]) == ("active", {"state": "active", "status": "active"})
    assert state["features"]["writing.review"]["limit"] == catalog.plan_by_id("plus").entitlement_map()["writing.review"].limit
    assert "provider" not in str(state), "the learner read carries no provider or customer identifiers"


def test_the_plan_screen_reads_each_record_once():
    legacy, source = LegacyRepo(manual("pro", FUTURE)), BillingSource(billing("plus"))
    ProductService(legacy, billing=source, clock=lambda: NOW).account_state("learner")
    assert (legacy.reads, source.reads) == (1, 1)


def test_inside_the_grace_quota_and_the_plan_screen_still_read_the_paid_plan(monkeypatch):
    from tests.test_quota_gate import FakeIncarnations, FakeQuotaRepository, MemorySettings
    from writing_coach.product import language_limit, quota

    svc = service(None, billing("plus", "past_due", paid_through=NOW - timedelta(hours=12)))
    previous = quota.runtime()
    monkeypatch.setattr(quota, "current_user_key", lambda: "learner")
    try:
        quota.configure_quota(repository=FakeQuotaRepository(), incarnations=FakeIncarnations(), plan_for=svc.plan_for_user,
                              settings=MemorySettings(), env={quota.FLAG: "on", quota.METERS_FLAG: "writing.review"},
                              clock=lambda: NOW)
        assert (svc.account_state("learner")["plan"]["id"], language_limit._limit("learner")[1]) == ("plus", "plus")
        with quota.admit("writing.review", request_digest="in-grace") as ticket:
            ticket.dispatch("p")
            ticket.settle(1)
    finally:
        quota.configure_quota(**{f: getattr(previous, f) for f in
                                 ("repository", "incarnations", "plan_for", "settings", "reason", "env", "clock")})


def test_plan_resolution_quota_admission_and_the_language_limit_agree(monkeypatch):
    from fastapi import HTTPException

    from tests.test_quota_gate import FakeIncarnations, FakeQuotaRepository, MemorySettings
    from writing_coach.product import language_limit, quota

    svc = service(manual("free"), prepaid("plus"))
    previous = quota.runtime()
    monkeypatch.setattr(quota, "current_user_key", lambda: "learner")
    try:
        quota.configure_quota(repository=FakeQuotaRepository(), incarnations=FakeIncarnations(), plan_for=svc.plan_for_user,
                              settings=MemorySettings(), env={quota.FLAG: "on", quota.METERS_FLAG: "writing.review"},
                              clock=lambda: NOW)
        svc.usage = quota.usage_for
        limit = catalog.plan_by_id("plus").entitlement_map()["writing.review"].limit
        assert limit > catalog.plan_by_id("free").entitlement_map()["writing.review"].limit
        for n in range(limit):
            with quota.admit("writing.review", request_digest=f"r{n}") as ticket:
                ticket.dispatch("p")
                ticket.settle(1)
        with pytest.raises(HTTPException) as refused:
            with quota.admit("writing.review", request_digest="over"):
                pytest.fail("no provider work past the paid plan's limit")
        assert refused.value.detail["context"]["plan"] == "plus"
        feature = svc.account_state("learner")["features"]["writing.review"]
        assert (feature["limit"], feature["used"], feature["remaining"]) == (limit, limit, 0)
        assert svc.account_state("learner")["plan"]["id"] == refused.value.detail["context"]["plan"]
        assert language_limit._limit("learner")[1] == "plus"
    finally:
        quota.configure_quota(**{f: getattr(previous, f) for f in
                                 ("repository", "incarnations", "plan_for", "settings", "reason", "env", "clock")})


def test_an_unreadable_billing_store_fails_closed_like_the_legacy_store():
    svc = service(manual("pro", FUTURE), billing_source=BillingSource(fail=True))
    with pytest.raises(RuntimeError):
        svc.plan_for_user("learner", strict=True)
    assert svc.account_state("learner")["available"] is False


# ------------------------------------------------------------------------------------------ billing off --

@pytest.mark.parametrize("row", [None, manual("pro", FUTURE), manual("pro", PAST), Legacy("plus", "trialing"),
                                 Legacy("plus", "canceled"), Legacy("enterprise", "active")])
def test_without_a_billing_source_every_answer_is_todays(row):
    """Billing off (or SQLite, or no account backbone): no billing source is installed and nothing changes."""
    without = ProductService(LegacyRepo(row))
    empty = ProductService(LegacyRepo(row), billing=BillingSource(None), clock=lambda: NOW)
    assert without.billing is None
    for svc in (without, empty):
        assert svc.plan_for_user("learner").id == legacy_rule_plan(row)
    assert without.account_state("learner") == empty.account_state("learner")


def legacy_rule_plan(row: Legacy | None) -> str:
    """The pre-PR-MON-1 rule, restated independently as the regression oracle."""
    if row is None or row.status not in ("active", "trialing"):
        return "free"
    if row.provider == "manual" and row.current_period_end and datetime.fromisoformat(row.current_period_end) <= datetime.now(UTC):
        return "free"
    return row.plan_id if catalog.known_plan_id(row.plan_id) else "free"


def test_the_app_installs_no_billing_source_without_postgresql():
    from writing_coach.product.service import product_service

    assert product_service.billing is None


# ------------------------------------------------------------------------------------------ manual grants --

class MembershipStore:
    def __init__(self, **account):
        self.account = {"id": "11111111-1111-1111-1111-111111111111", "user_key": "learner", "email": "l@example.test",
                        "role": "user", "plan_id": None, "status": None, "provider": None, "until": None, **account}
        self.applied = []

    def account_membership(self, user_id):
        return dict(self.account) if user_id == self.account["id"] else None

    def apply_membership(self, user_id, **change):
        self.applied.append(change)


@pytest.mark.parametrize("state", ["active", "trialing", "past_due", "paused", "pending"])
def test_an_admin_cannot_set_a_plan_by_hand_on_an_account_billing_owns(state):
    from writing_coach.product.api import billing_aware_membership

    svc = service(None, billing("plus", state))
    store = billing_aware_membership(MembershipStore(), svc)
    with pytest.raises(MembershipConflict):
        apply_change(store, store.account_membership("11111111-1111-1111-1111-111111111111")["id"],
                     {"plan_id": "pro"}, actor_key="admin", protected_emails=set())
    assert store.inner.applied == [], "nothing is written"


def test_the_admin_membership_read_shows_the_billing_plan():
    from writing_coach.product.api import billing_aware_membership

    store = billing_aware_membership(MembershipStore(), service(None, prepaid("plus")))
    account = store.account_membership("11111111-1111-1111-1111-111111111111")
    assert (account["plan_id"], account["status"], account["provider"], account["billing_owned"]) == (
        "plus", "active", "payos", True)


def test_an_admin_can_still_set_a_plan_when_billing_owns_nothing():
    from writing_coach.product.api import billing_aware_membership

    for row in (None, billing("plus", "ended"), prepaid("plus", paid_through=PAST)):
        store = billing_aware_membership(MembershipStore(), service(None, row))
        apply_change(store, "11111111-1111-1111-1111-111111111111", {"plan_id": "pro"}, actor_key="admin",
                     protected_emails=set())
        assert store.inner.applied, row
        assert store.account_membership("11111111-1111-1111-1111-111111111111")["billing_owned"] is False
