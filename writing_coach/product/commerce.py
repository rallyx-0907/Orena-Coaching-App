"""I3 read-adapter contract: docs/product/ORENA_COMMERCE_ARCHITECTURE.md §2, §5.

"First implement versioned read adapters preserving current truthful states."
This module is additive over `ProductService`/`account_state` — it does not
replace them (`tests/test_product_account_state.py` and the mobile contract
already lock that shape) — and it enforces nothing: `billing_ready` stays
`False` and no route may deny a request from `resolveEntitlement` yet.

Identity note: canonical commerce is specified against an account incarnation
(`reference_backbone.Scope`), but nothing in this codebase resolves a live
incarnation from a request yet — I1's `account_profile.scope_of()` has no
production caller. This adapter therefore keys off the same `user_key` the
existing `/api/product/*` routes already use, and does not invent incarnation
wiring as a side effect. See the plan doc for the full reasoning.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from writing_coach.product.service import ProductService, product_service

# The full canonical vocabulary from ORENA_COMMERCE_ARCHITECTURE.md §3.
# Only a subset is reachable from today's repository (no provider adapter
# exists), but a status the repository already reports must not be collapsed
# into a coarser bucket than the one it actually names.
SubscriptionState = Literal[
    "none", "pending", "trialing", "active", "past_due", "paused", "ended", "unknown"
]

_STATUS_TO_STATE: dict[str, SubscriptionState] = {
    "active": "active",
    "trialing": "trialing",
    "past_due": "past_due",
    "paused": "paused",
    "canceled": "ended",
    "cancelled": "ended",
    "ended": "ended",
    "pending": "pending",
    "incomplete": "pending",
}


def _canonical_subscription_state(state: dict[str, Any]) -> SubscriptionState:
    """Derived from `account_state()`'s own snapshot — never a second query.

    `account_state` already reads the subscription exactly once
    (`test_account_state_uses_one_normalized_subscription_snapshot`); this
    only relabels what it already computed.
    """
    status = state["subscription"]["status"]
    if status == "inactive":
        # The service's own literal for "no subscription row at all" — see
        # ProductService.account_state, where a missing subscription is the
        # only path that produces this exact string.
        return "none"
    if state.get("plan_state") == "unknown":
        return "unknown"
    return _STATUS_TO_STATE.get(status, "unknown")


def accountCommerce(user_key: str, *, service: ProductService | None = None) -> dict[str, Any]:
    """Known plan/subscription/entitlement/quota facts. Unknown data stays unknown.

    Read-only UI badges are not access enforcement; this never denies a
    request on its own.
    """
    svc = service or product_service
    state = svc.account_state(user_key)
    if not state["available"]:
        return {**state, "readiness": "unavailable"}

    canonical_state = _canonical_subscription_state(state)
    return {
        **state,
        "subscription": {**state["subscription"], "state": canonical_state},
        "readiness": "known",
    }


@dataclass(frozen=True)
class EntitlementDecision:
    """feature, allowed/denied/unknown, reason — ORENA_COMMERCE_ARCHITECTURE.md §2.

    `allowed=None` is the unknown state: it must never be read as granted or
    denied by a caller.
    """

    feature: str
    allowed: bool | None
    reason: str
    entitlement_state: str
    quota: dict[str, int | None]

    def as_dict(self) -> dict[str, Any]:
        return {
            "feature": self.feature,
            "allowed": self.allowed,
            "reason": self.reason,
            "entitlement_state": self.entitlement_state,
            "quota": self.quota,
        }


_REASON_BY_ENTITLEMENT_STATE = {
    "unavailable": "not_in_plan",
    "disabled": "disabled_for_plan",
    "exhausted": "quota_exhausted",
}


def resolveEntitlement(
    user_key: str, feature: str, *, service: ProductService | None = None
) -> EntitlementDecision:
    """The one server resolver every entry path should consume.

    Feature code must consume this decision, never compare a plan ID
    directly — that is the mistake §2 names by name.
    """
    svc = service or product_service
    access = svc.feature_access(user_key=user_key, feature=feature)
    quota = {"limit": access.monthly_limit, "used": access.used, "remaining": access.remaining}
    if access.entitlement_state == "unknown":
        return EntitlementDecision(feature, None, "usage_unavailable", access.entitlement_state, quota)
    if access.enabled:
        reason = "unlimited" if access.monthly_limit is None else "within_quota"
        return EntitlementDecision(feature, True, reason, access.entitlement_state, quota)
    reason = _REASON_BY_ENTITLEMENT_STATE.get(access.entitlement_state, "denied")
    return EntitlementDecision(feature, False, reason, access.entitlement_state, quota)
