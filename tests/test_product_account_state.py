from dataclasses import dataclass

from writing_coach.product.service import ProductService


@dataclass
class Subscription:
    plan_id: str
    status: str


class Repo:
    def __init__(self, subscription=None, usage=None, fail_usage=False, fail_subscription_after_first=False):
        self.subscription = subscription
        self.usage = usage or {}
        self.fail_usage = fail_usage
        self.fail_subscription_after_first = fail_subscription_after_first
        self.subscription_reads = 0

    def get_subscription(self, user_key):
        self.subscription_reads += 1
        if self.fail_subscription_after_first and self.subscription_reads > 1:
            raise RuntimeError("subscription store changed")
        return self.subscription

    def monthly_usage(self, *, user_key, feature):
        if self.fail_usage:
            raise RuntimeError("usage store unavailable")
        return self.usage.get(feature, 0)


def test_inactive_or_unknown_subscription_is_truthfully_defaulted():
    for subscription in (None, Subscription("premium", "canceled"), Subscription("future", "active")):
        state = ProductService(Repo(subscription)).account_state("user-1")
        assert state["available"] is True
        assert state["plan"]["id"] == "free"
        assert state["subscription"]["state"] in {"inactive", "unknown"}
        assert "external_subscription_id" not in state["subscription"]


def test_exhausted_and_unlimited_usage_are_explicit():
    state = ProductService(Repo(
        Subscription("premium", "active"),
        {"writing.evaluate": 500, "library.grammar": 999},
    )).account_state("user-1")
    assert state["features"]["writing.evaluate"]["remaining"] == 0
    assert state["features"]["writing.evaluate"]["entitlement_state"] == "exhausted"
    assert state["features"]["library.grammar"]["remaining"] is None
    assert state["features"]["library.grammar"]["entitlement_state"] == "enabled"


def test_account_state_uses_one_normalized_subscription_snapshot():
    repo = Repo(Subscription("Premium", "ACTIVE"), fail_subscription_after_first=True)
    state = ProductService(repo).account_state("user-1")
    # A stored "premium" subscription is Pro, the plan with Premium's limits (D-153).
    assert state["plan"]["id"] == "pro"
    assert state["features"]["writing.evaluate"]["monthly_limit"] == 500
    assert repo.subscription_reads == 1


def test_usage_failure_is_unavailable_not_zero():
    state = ProductService(Repo(Subscription("premium", "active"), fail_usage=True)).account_state("user-1")
    item = state["features"]["writing.evaluate"]
    assert item["usage_state"] == "unavailable"
    assert item["remaining"] is None
    assert item["entitlement_state"] == "unknown"


def test_admin_account_surface_is_read_only_and_redacted():
    import writing_coach.product.api as product_api

    previous_admin = product_api.require_admin
    previous_service = product_api.product_service
    try:
        product_api.require_admin = lambda request: {"google_sub": "admin-1"}
        product_api.product_service = ProductService(Repo(Subscription("premium", "active")))
        result = product_api.product_admin_account(object())
    finally:
        product_api.require_admin = previous_admin
        product_api.product_service = previous_service
    assert result["read_only"] is True
    assert result["account"]["plan"]["id"] == "pro", "a stored premium subscription is Pro (D-153)"
    assert "external_customer_id" not in result["account"]["subscription"]


def _mobile_plan_schema_fields() -> set[str]:
    """Field names declared by the native client's strict plan schema."""
    import pathlib
    import re

    source = (
        pathlib.Path(__file__).resolve().parents[1]
        / "mobile/src/api/contracts/product.ts"
    ).read_text(encoding="utf-8")
    body = re.search(
        r"export const productPlanSchema = z\.object\(\{(.*?)\}\)\.strict\(\);",
        source,
        re.DOTALL,
    )
    assert body, "productPlanSchema must stay a strict z.object literal"
    return set(re.findall(r"^\s{2}(\w+):", body.group(1), re.MULTILINE))


def test_mobile_plan_contract_matches_account_state_plan():
    """The native strict schema must not require fields the API never returns.

    `productPlanSchema` is `.strict()`, so any drift in either direction makes
    every real `/api/product/me` response fail to parse on device while
    hand-written mobile fixtures keep passing.
    """
    state = ProductService(Repo(Subscription("premium", "active"))).account_state("user-1")
    assert set(state["plan"]) == _mobile_plan_schema_fields()


def test_degraded_account_state_stays_parseable_by_the_mobile_contract():
    class BrokenRepo(Repo):
        def get_subscription(self, user_key):
            raise RuntimeError("subscription store unavailable")

    state = ProductService(BrokenRepo()).account_state("user-1")
    assert state == {
        "available": False,
        "plan": None,
        "subscription": {"state": "unknown", "status": "unknown"},
        "features": {},
        "billing_ready": False,
    }


def test_mobile_me_keeps_its_two_plan_ids():
    """/api/product/me feeds the frozen native schema (id: free | premium): Plus and Pro read as premium there."""
    from writing_coach.product.api import mobile_account_state

    for stored in ("plus", "pro", "premium"):
        state = mobile_account_state(ProductService(Repo(Subscription(stored, "active"))).account_state("user-1"))
        assert state["plan"]["id"] == "premium"
        assert set(state["plan"]) == _mobile_plan_schema_fields()
    free = mobile_account_state(ProductService(Repo(None)).account_state("user-1"))
    assert free["plan"]["id"] == "free"
