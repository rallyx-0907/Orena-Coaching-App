"""Task 1 of docs/superpowers/plans/2026-09-11-orena-commerce-read-adapter.md.

Canonical read-adapter contract from ORENA_COMMERCE_ARCHITECTURE.md §2, built
additively on top of the existing, already-locked ProductService/account_state
path (tests/test_product_account_state.py). No schema, no enforcement, no
provider identifier ever leaves this layer.
"""
from dataclasses import dataclass

from writing_coach.product.commerce import accountCommerce, resolveEntitlement
from writing_coach.product.service import ProductService


@dataclass
class Subscription:
    plan_id: str
    status: str


class Repo:
    def __init__(self, subscription=None, usage=None, fail_usage=False):
        self.subscription = subscription
        self.usage = usage or {}
        self.fail_usage = fail_usage

    def get_subscription(self, user_key):
        return self.subscription

    def monthly_usage(self, *, user_key, feature):
        if self.fail_usage:
            raise RuntimeError("usage store unavailable")
        return self.usage.get(feature, 0)


def test_no_subscription_is_the_canonical_none_state():
    service = ProductService(Repo(None))
    result = accountCommerce("user-1", service=service)
    assert result["subscription"]["state"] == "none"


def test_recognized_non_active_status_keeps_its_own_canonical_state():
    for status, expected in (
        ("past_due", "past_due"),
        ("paused", "paused"),
        ("canceled", "ended"),
        ("cancelled", "ended"),
        ("ended", "ended"),
        ("pending", "pending"),
        ("incomplete", "pending"),
        ("trialing", "trialing"),
    ):
        service = ProductService(Repo(Subscription("premium", status)))
        result = accountCommerce("user-1", service=service)
        assert result["subscription"]["state"] == expected, status


def test_unrecognized_status_is_unknown_not_collapsed_into_inactive():
    service = ProductService(Repo(Subscription("premium", "some-new-provider-status")))
    result = accountCommerce("user-1", service=service)
    assert result["subscription"]["state"] == "unknown"


def test_active_with_unrecognized_plan_is_unknown():
    service = ProductService(Repo(Subscription("future-plan", "active")))
    result = accountCommerce("user-1", service=service)
    assert result["subscription"]["state"] == "unknown"


def test_account_commerce_never_carries_a_provider_identifier():
    service = ProductService(Repo(Subscription("premium", "active")))
    result = accountCommerce("user-1", service=service)
    blob = str(result)
    assert "external_customer_id" not in blob
    assert "external_subscription_id" not in blob


def test_account_commerce_stays_read_only():
    service = ProductService(Repo(Subscription("premium", "active")))
    result = accountCommerce("user-1", service=service)
    assert result["billing_ready"] is False


def test_account_commerce_readiness_reflects_degraded_repository():
    class BrokenRepo(Repo):
        def get_subscription(self, user_key):
            raise RuntimeError("subscription store unavailable")

    service = ProductService(BrokenRepo())
    result = accountCommerce("user-1", service=service)
    assert result["readiness"] == "unavailable"


def test_account_commerce_readiness_known_when_available():
    service = ProductService(Repo(Subscription("premium", "active")))
    result = accountCommerce("user-1", service=service)
    assert result["readiness"] == "known"


def test_resolve_entitlement_allowed_within_quota():
    service = ProductService(Repo(Subscription("premium", "active"), {"writing.evaluate": 10}))
    decision = resolveEntitlement("user-1", "writing.evaluate", service=service)
    assert decision.allowed is True
    assert decision.entitlement_state == "enabled"
    assert decision.quota == {"limit": 500, "used": 10, "remaining": 490}


def test_resolve_entitlement_denied_when_exhausted():
    service = ProductService(Repo(Subscription("premium", "active"), {"writing.evaluate": 500}))
    decision = resolveEntitlement("user-1", "writing.evaluate", service=service)
    assert decision.allowed is False
    assert decision.reason == "quota_exhausted"


def test_resolve_entitlement_denied_when_not_in_plan():
    service = ProductService(Repo(Subscription("free", "active")))
    decision = resolveEntitlement("user-1", "practice.personalized", service=service)
    assert decision.allowed is False
    assert decision.reason == "disabled_for_plan"


def test_resolve_entitlement_unavailable_feature_is_denied_not_unknown():
    service = ProductService(Repo(Subscription("premium", "active")))
    decision = resolveEntitlement("user-1", "no-such-feature", service=service)
    assert decision.allowed is False
    assert decision.reason == "not_in_plan"


def test_resolve_entitlement_is_unknown_not_denied_when_usage_read_fails():
    service = ProductService(Repo(Subscription("premium", "active"), fail_usage=True))
    decision = resolveEntitlement("user-1", "writing.evaluate", service=service)
    assert decision.allowed is None
    assert decision.reason == "usage_unavailable"


def test_existing_account_state_is_unmodified_by_this_module_existing():
    service = ProductService(Repo(Subscription("premium", "canceled")))
    state = service.account_state("user-1")
    assert state["subscription"]["state"] == "inactive"
