from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from auth_support import AUTH_ENABLED, auth_user, require_admin
from writing_coach.product.catalog import PLANS
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
    return product_service.account_state(current_user_key(request))


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
        "plans": [plan.as_dict() for plan in PLANS.values()],
        "billing_ready": False,
    }


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
