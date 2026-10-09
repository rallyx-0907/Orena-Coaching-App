from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from writing_coach.product.catalog import DEFAULT_PLAN_ID, Plan, known_plan_id, plan_by_id
from writing_coach.product.repository import ProductRepository


@dataclass(frozen=True)
class FeatureAccess:
    key: str
    enabled: bool
    monthly_limit: int | None
    used: int
    remaining: int | None
    usage_state: str = "known"
    entitlement_state: str = "enabled"

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "enabled": self.enabled,
            "monthly_limit": self.monthly_limit,
            "used": self.used,
            "remaining": self.remaining,
            "usage_state": self.usage_state,
            "entitlement_state": self.entitlement_state,
        }


class ProductService:
    def __init__(self, repository: ProductRepository | None = None) -> None:
        self.repository = repository

    def _repository(self) -> ProductRepository:
        if self.repository is None:
            raise RuntimeError("Product repository has not been installed by the persistence runtime.")
        return self.repository

    def plan_for_user(self, user_key: str) -> Plan:
        subscription = self._repository().get_subscription(user_key)
        return self._plan_for_subscription(subscription)

    @staticmethod
    def _plan_for_subscription(subscription: object | None) -> Plan:
        status = str(getattr(subscription, "status", "") or "").strip().casefold()
        plan_id = str(getattr(subscription, "plan_id", "") or "").strip().casefold()
        if not subscription or status not in {"active", "trialing"}:
            return plan_by_id(DEFAULT_PLAN_ID)
        return plan_by_id(plan_id)

    def _subscription(self, user_key: str):
        return self._repository().get_subscription(user_key)

    def feature_access(self, *, user_key: str, feature: str) -> FeatureAccess:
        plan = self.plan_for_user(user_key)
        return self._feature_access_for_plan(user_key=user_key, feature=feature, plan=plan)

    def _feature_access_for_plan(self, *, user_key: str, feature: str, plan: Plan) -> FeatureAccess:
        entitlement = plan.entitlement_map().get(feature)
        if not entitlement:
            return FeatureAccess(feature, False, None, 0, None, entitlement_state="unavailable")

        try:
            used = self._repository().monthly_usage(user_key=user_key, feature=feature)
        except Exception:
            return FeatureAccess(
                key=feature,
                enabled=entitlement.enabled,
                monthly_limit=entitlement.monthly_limit,
                used=0,
                remaining=None,
                usage_state="unavailable",
                entitlement_state="unknown",
            )
        remaining = (
            None
            if entitlement.monthly_limit is None
            else max(0, entitlement.monthly_limit - used)
        )
        enabled = entitlement.enabled and (remaining is None or remaining > 0)
        return FeatureAccess(
            key=feature,
            enabled=enabled,
            monthly_limit=entitlement.monthly_limit,
            used=used,
            remaining=remaining,
            entitlement_state=("disabled" if not entitlement.enabled else ("exhausted" if remaining == 0 else "enabled")),
        )

    def account_state(self, user_key: str) -> dict[str, Any]:
        try:
            subscription = self._subscription(user_key)
        except Exception:
            return {
                "available": False,
                "plan": None,
                "subscription": {"state": "unknown", "status": "unknown"},
                "features": {},
                "billing_ready": False,
            }

        status = str(getattr(subscription, "status", "") or "").strip().casefold() if subscription else "inactive"
        active = status in {"active", "trialing"}
        raw_plan_id = str(getattr(subscription, "plan_id", "") or "").strip().casefold() if subscription else DEFAULT_PLAN_ID
        plan_known = known_plan_id(raw_plan_id)
        plan = plan_by_id(raw_plan_id if active and plan_known else DEFAULT_PLAN_ID)
        features = {
            item.key: self._feature_access_for_plan(user_key=user_key, feature=item.key, plan=plan).as_dict()
            for item in plan.entitlements
        }
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
