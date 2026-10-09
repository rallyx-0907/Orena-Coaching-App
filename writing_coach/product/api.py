from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from auth_support import AUTH_ENABLED, auth_user, require_admin
from writing_coach.product.catalog import (
    CURRENCIES,
    FEATURE_KEYS,
    PERIODS,
    PlanCatalogInvalid,
    current_plans,
    save_catalog,
    stored_catalog,
)
from writing_coach.product.commerce import accountCommerce
from writing_coach.product.service import product_service

router = APIRouter(prefix="/api/product", tags=["product"])


def current_user_key(request: Request) -> str:
    if not AUTH_ENABLED:
        return "local-development"

    sub = str(request.session.get("user_sub") or "")
    if not sub or not auth_user(sub):
        raise HTTPException(401, "Authentication required")
    return sub


@router.get("/me")
def product_me(request: Request) -> dict[str, Any]:
    # mobile/src/api/contracts/product.ts strictly enums subscription.state to
    # {active, inactive, unknown} and is frozen (ARCHITECTURE_INVARIANTS.md) -
    # this route's shape must not change under it. The web-only canonical
    # read lives at /commerce below.
    return mobile_account_state(product_service.account_state(current_user_key(request)))


def mobile_account_state(state: dict[str, Any]) -> dict[str, Any]:
    """The frozen native contract knows two plan ids, free and premium (mobile/src/api/contracts/product.ts):
    a paid tier (Plus, Pro - D-153) is reported to it as premium. The web reads /commerce and sees the real id."""
    plan = state.get("plan")
    if isinstance(plan, dict) and plan.get("id") not in (None, "free", "premium"):
        return {**state, "plan": {**plan, "id": "premium"}}
    return state


@router.get("/commerce")
def product_commerce(request: Request) -> dict[str, Any]:
    """Canonical I3 read adapter (ORENA_COMMERCE_ARCHITECTURE.md §2).

    Web-only: the full subscription-state vocabulary here is a superset of
    what /me promises mobile, so it is additive rather than a replacement.
    """
    return accountCommerce(current_user_key(request))


@router.get("/plans")
def product_plans(request: Request) -> dict[str, Any]:
    current_user_key(request)
    return {
        "plans": [plan.as_dict() for plan in current_plans().values()],
        "billing_ready": False,
    }


def _admin_catalog() -> dict[str, Any]:
    record = stored_catalog() or {}
    return {
        "plans": [plan.as_dict() for plan in current_plans().values()],
        "features": list(FEATURE_KEYS),
        "currencies": list(CURRENCIES),
        "periods": list(PERIODS),
        "source": "stored" if record else "default",
        "updated_at": record.get("updated_at") or None,
        "updated_by": record.get("updated_by") or None,
        "billing_ready": False,
    }


@router.get("/admin/plans")
def product_admin_plans(request: Request) -> dict[str, Any]:
    """The catalogue in force, for Platform Admin's plan editor (D-153)."""
    require_admin(request)
    return _admin_catalog()


@router.put("/admin/plans")
async def product_admin_plans_save(request: Request) -> dict[str, Any]:
    """Save prices and monthly limits for Free, Plus and Pro. They apply from this moment (D-153)."""
    admin = require_admin(request)
    try:
        document = await request.json()
    except Exception:
        raise HTTPException(400, "The catalogue must be JSON.")
    try:
        save_catalog(document, updated_by=str(admin.get("email") or admin.get("google_sub") or ""))
    except PlanCatalogInvalid as error:
        raise HTTPException(422, str(error))
    _record_admin_event(str(admin.get("google_sub") or ""), document)
    return _admin_catalog()


def _record_admin_event(actor: str, document: Any) -> None:
    from writing_coach.ai.platform import _installed_platform_repository

    try:
        _installed_platform_repository().record_admin_event(
            "product.plans.update",
            actor=actor,
            entity_type="plan_catalog",
            entity_id="product.plan_catalog",
            payload={"plans": [row.get("id") for row in (document or {}).get("plans", []) if isinstance(row, dict)]},
        )
    except Exception:
        # The audit row is best effort; the saved catalogue is the change.
        pass


@router.get("/admin/account")
def product_admin_account(request: Request) -> dict[str, Any]:
    """Read-only account state for the authenticated platform administrator.

    This intentionally exposes no subscription-provider identifiers and does
    not accept a user key, so the admin surface cannot become an account
    enumeration endpoint while the product policy is still pre-billing.
    """
    admin = require_admin(request)
    state = product_service.account_state(str(admin.get("google_sub") or "local-admin"))
    return {"account": state, "read_only": True}
