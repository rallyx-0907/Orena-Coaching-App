from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from writing_coach.product.catalog import Plan
from writing_coach.product import billing_grace
from writing_coach.product.entitlement import BillingEntitlementSource, EffectiveEntitlement, resolve
from writing_coach.product.repository import ProductRepository


@dataclass(frozen=True)
class FeatureAccess:
    """One plan entitlement and its use in the current window (D-160).

    `usage_state`: `known` (read from the quota buckets enforcement writes), `unavailable` (the store could not
    be read - never shown as 0 used) or `not_metered` (this meter is not enforced on this deployment, so nothing
    counts it and `used` is None). `limit`/`used`/`remaining` are in the meter's stored `unit`."""

    key: str
    enabled: bool
    limit: int | None
    used: int | None
    remaining: int | None
    usage_state: str = "not_metered"
    entitlement_state: str = "enabled"
    window: str | None = None
    unit: str = ""
    display_unit: str = ""
    scale: int = 1
    resets_at: str | None = None

    @property
    def monthly_limit(self) -> int | None:
        return self.limit if self.window == "month" else None

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "enabled": self.enabled,
            "limit": self.limit,
            "monthly_limit": self.monthly_limit,
            "window": self.window,
            "unit": self.unit,
            "display_unit": self.display_unit,
            "scale": self.scale,
            "used": self.used,
            "remaining": self.remaining,
            "resets_at": self.resets_at,
            "usage_state": self.usage_state,
            "entitlement_state": self.entitlement_state,
        }


# (user_key, plan) -> {feature: {"state": "known"|"unavailable", "used": int, "resets_at": iso}}; a feature
# absent from the answer is not metered. Installed by the app (writing_coach.product.quota.usage_for).
UsageReader = Callable[[str, Plan], dict[str, dict[str, Any]]]


class ProductService:
    def __init__(self, repository: ProductRepository | None = None, usage: UsageReader | None = None, *,
                 billing: BillingEntitlementSource | None = None,
                 clock: Callable[[], datetime] = lambda: datetime.now(UTC),
                 grace: Callable[[], billing_grace.GracePolicy] = billing_grace.current) -> None:
        self.repository = repository
        self.usage = usage
        # The billing record (`commerce_subscriptions`); None where the runtime has no commerce store (D-MON-006).
        self.billing = billing
        self.clock = clock
        self.grace = grace   # the billing grace policy in force (D-MON-011), read at each resolution

    def _repository(self) -> ProductRepository:
        if self.repository is None:
            raise RuntimeError("Product repository has not been installed by the persistence runtime.")
        return self.repository

    def entitlement(self, user_key: str) -> EffectiveEntitlement:
        """The account's one effective entitlement (`writing_coach.product.entitlement`): every plan reader - the Plan
        screen, quota admission, the language limit, the Admin membership guard - derives from this. A record that
        cannot be read raises; nothing guesses a plan."""
        legacy = self._repository().get_subscription(user_key)
        billing = self.billing.subscription_for_user(user_key) if self.billing is not None else None
        return resolve(legacy=legacy, billing=billing, now=self.clock(),
                       grace=self.grace() if billing is not None else billing_grace.NO_GRACE)

    def plan_for_user(self, user_key: str, *, strict: bool = False) -> Plan:
        """The effective plan. `strict` (enforcement) raises when the catalogue cannot be read."""
        return self.entitlement(user_key).plan(strict=strict)

    def feature_access(self, *, user_key: str, feature: str) -> FeatureAccess:
        plan = self.plan_for_user(user_key)
        return self._features_for_plan(user_key=user_key, plan=plan, only=feature)[feature]

    def _usage(self, user_key: str, plan: Plan) -> dict[str, dict[str, Any]] | None:
        if self.usage is None:
            return {}
        try:
            return self.usage(user_key, plan)
        except Exception:
            return None

    def _features_for_plan(self, *, user_key: str, plan: Plan, only: str | None = None) -> dict[str, FeatureAccess]:
        entitlements = plan.entitlement_map()
        keys = [only] if only else list(entitlements)
        usage = self._usage(user_key, plan)
        return {key: self._access(key, entitlements.get(key), None if usage is None else usage.get(key, {}))
                for key in keys}

    @staticmethod
    def _access(feature: str, entitlement, usage: dict[str, Any] | None) -> FeatureAccess:
        if not entitlement:
            return FeatureAccess(feature, False, None, None, None, entitlement_state="unavailable")
        meter = entitlement.meter
        shape = {"window": meter.window, "unit": meter.unit, "display_unit": meter.display_unit, "scale": meter.scale}
        limit = entitlement.limit
        state = "unavailable" if usage is None else str(usage.get("state") or "not_metered")
        if state != "known":
            return FeatureAccess(
                feature, entitlement.enabled, limit, None, None, usage_state=state,
                entitlement_state=("disabled" if not entitlement.enabled else ("unknown" if state == "unavailable" else "enabled")),
                **shape,
            )
        used = max(0, int(usage.get("used") or 0))
        remaining = None if limit is None else max(0, limit - used)
        if meter.window is None:
            # A count cap (`languages.target`, D-170): at the cap nothing more can be ADDED, but what the account
            # holds stays usable, so a full count is neither "disabled" nor "exhausted" - `remaining` says 0.
            return FeatureAccess(
                feature, entitlement.enabled, limit, used, remaining, usage_state="known",
                entitlement_state="enabled" if entitlement.enabled else "disabled", **shape,
            )
        return FeatureAccess(
            feature,
            entitlement.enabled and (remaining is None or remaining > 0),
            limit, used, remaining, usage_state="known",
            entitlement_state=("disabled" if not entitlement.enabled else ("exhausted" if remaining == 0 else "enabled")),
            resets_at=usage.get("resets_at"),
            **shape,
        )

    def account_state(self, user_key: str) -> dict[str, Any]:
        try:
            effective = self.entitlement(user_key)
        except Exception:
            return {
                "available": False,
                "plan": None,
                "subscription": {"state": "unknown", "status": "unknown"},
                "features": {},
                "billing_ready": False,
            }

        status = effective.status
        active = effective.active
        plan_known = effective.plan_known
        plan = effective.plan()
        features = {key: access.as_dict() for key, access in self._features_for_plan(user_key=user_key, plan=plan).items()}
        return {
            "available": True,
            "plan": {
                "id": plan.id,
                "name": plan.name,
                "description": plan.description,
                "price_label": plan.price_label,
            },
            "subscription": {
                "state": "active" if active and plan_known else ("unknown" if active and not plan_known else "inactive"),
                "status": status or "unknown",
            },
            "plan_state": "active" if active and plan_known else ("unknown" if active and not plan_known else "default"),
            "features": features,
            "billing_ready": False,
        }


product_service = ProductService()

def configure_product_repository(repository: ProductRepository) -> None:
    product_service.repository = repository


def configure_product_usage(usage: UsageReader | None) -> None:
    product_service.usage = usage


def configure_product_billing(source: BillingEntitlementSource | None) -> None:
    """Install the billing record the effective entitlement reads (D-MON-006); None removes it."""
    product_service.billing = source
