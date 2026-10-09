from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from auth_support import AUTH_ENABLED, auth_user, require_admin
from writing_coach.persistence.platform_repository import SettingConflict
from writing_coach.core.request_context import current_user_key as request_user_key
from writing_coach.product import quota
from writing_coach.product.catalog import (
    CURRENCIES,
    FEATURE_KEYS,
    METERS,
    PERIODS,
    PlanCatalogInvalid,
    current_plans,
    save_catalog,
    stored_catalog,
)
from writing_coach.product.commerce import accountCommerce
from writing_coach.product.membership import ROLES, MembershipConflict, MembershipInvalid, apply_change
from writing_coach.product.service import product_service

router = APIRouter(prefix="/api/product", tags=["product"])


def current_user_key(request: Request) -> str:
    """The account a product read is about: the same request-context key quota enforcement meters (D-160).

    Signed in, the session's Google subject; with authentication off, the one local account the middleware
    keys every request by ("legacy") - not a second, made-up account, so the Plan screen and enforcement agree."""
    if not AUTH_ENABLED:
        return request_user_key()

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


MOBILE_FEATURE_FIELDS = ("key", "enabled", "monthly_limit", "used", "remaining", "usage_state", "entitlement_state")


def _mobile_feature(item: dict[str, Any]) -> dict[str, Any]:
    """The frozen native shape of one feature (strict: no extra field; usage_state known | unavailable)."""
    known = item.get("usage_state") == "known"
    return {
        "key": item.get("key"),
        "enabled": bool(item.get("enabled")),
        "monthly_limit": item.get("monthly_limit"),
        "used": int(item.get("used") or 0) if known else 0,
        "remaining": item.get("remaining") if known else None,
        "usage_state": "known" if known else "unavailable",
        "entitlement_state": item.get("entitlement_state"),
    }


def mobile_account_state(state: dict[str, Any]) -> dict[str, Any]:
    """The frozen native contract knows two plan ids, free and premium (mobile/src/api/contracts/product.ts):
    a paid tier (Plus, Pro - D-153) is reported to it as premium, and each feature is projected onto the
    native feature shape (D-160 added fields the strict native schema would refuse). The web reads /commerce
    and sees the real id and every field."""
    plan = state.get("plan")
    if isinstance(plan, dict) and plan.get("id") not in (None, "free", "premium"):
        state = {**state, "plan": {**plan, "id": "premium"}}
    features = state.get("features")
    if isinstance(features, dict):
        state = {**state, "features": {key: _mobile_feature(item) for key, item in features.items()}}
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
        # What each feature is - window, unit, display unit and scale - is the code's; the editor shows it beside
        # the number it edits (D-160).
        "meters": {
            key: {"window": meter.window, "unit": meter.unit, "display_unit": meter.display_unit,
                  "scale": meter.scale, "params": {name: list(bounds) for name, bounds in meter.params.items()}}
            for key, meter in METERS.items()
        },
        "version": 2,
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
    """Save prices and limits for Free, Plus and Pro. They apply from this moment (D-153), and quota
    enforcement reads them within the catalogue cache (D-160)."""
    admin = require_admin(request)
    try:
        document = await request.json()
    except Exception:
        raise HTTPException(400, "The catalogue must be JSON.")
    if not isinstance(document, dict):
        raise HTTPException(422, "The catalogue must be an object.")
    # Two administrators editing at once: the version the editor loaded is compared inside the write transaction
    # (compare-and-set), and the audit row commits with the change (review of #112).
    actor = str(admin.get("google_sub") or "")
    audit = {
        "action": "product.plans.update", "actor": actor, "entity_type": "plan_catalog",
        "entity_id": "product.plan_catalog",
        "payload": {"plans": [row.get("id") for row in document.get("plans", []) if isinstance(row, dict)]},
    }
    try:
        save_catalog(document, updated_by=str(admin.get("email") or actor),
                     expected_updated_at=document.get("expected_updated_at", ...), audit=audit)
    except PlanCatalogInvalid as error:
        raise HTTPException(422, str(error))
    except SettingConflict:
        raise HTTPException(409, "The plans were changed by someone else since you opened this page. Reload to see them.")
    except RuntimeError:
        raise HTTPException(503, "Plans are not editable on this deployment.")
    return _admin_catalog()


@router.get("/admin/quota")
def product_admin_quota(request: Request) -> dict[str, Any]:
    """The quota enforcement switch and where it comes from (D-160)."""
    require_admin(request)
    return quota.switch()


@router.put("/admin/quota")
async def product_admin_quota_save(request: Request) -> dict[str, Any]:
    """Switch enforcement on or off and choose the meters, without a restart. The environment
    (ORENA_QUOTA_ENFORCEMENT / ORENA_QUOTA_METERS), when set, still wins; the answer says which applies."""
    admin = require_admin(request)
    try:
        document = await request.json()
    except Exception:
        raise HTTPException(400, "The switch must be JSON.")
    actor = str(admin.get("google_sub") or "")
    audit = {"action": "product.quota.update", "actor": actor, "entity_type": "platform_setting",
             "entity_id": quota.SETTING_KEY, "payload": document if isinstance(document, dict) else {}}
    try:
        return quota.save_switch(document, updated_by=str(admin.get("email") or actor), audit=audit)
    except ValueError as error:
        raise HTTPException(422, str(error))
    except RuntimeError:
        raise HTTPException(503, "The quota switch is not editable on this deployment.")


def _membership_store():
    store = product_service.repository
    if store is None or not hasattr(store, "account_membership"):
        raise HTTPException(503, "Accounts are not editable on this deployment.")
    return store


def _membership_body(account: dict[str, Any]) -> dict[str, Any]:
    return {
        "available": True,
        "account": account,
        "roles": list(ROLES),
        "plans": [{"id": plan.id, "name": plan.name, "rank": plan.rank} for plan in current_plans().values()],
    }


@router.get("/admin/accounts/{user_id}/membership")
def product_admin_membership(user_id: str, request: Request) -> dict[str, Any]:
    """One account's role and plan, for Platform Admin's account page (D-154)."""
    require_admin(request)
    account = _membership_store().account_membership(user_id)
    if account is None:
        raise HTTPException(404, "No account has this identifier.")
    return _membership_body(account)


@router.put("/admin/accounts/{user_id}/membership")
async def product_admin_membership_save(user_id: str, request: Request) -> dict[str, Any]:
    """Set an account's role and/or plan by hand; applies from this moment (D-154)."""
    admin = require_admin(request)
    store = _membership_store()
    try:
        change = await request.json()
    except Exception:
        raise HTTPException(400, "The change must be JSON.")
    from auth_support import PLATFORM_ADMIN_EMAILS

    try:
        result = apply_change(
            store, user_id, change, actor_key=str(admin.get("google_sub") or ""),
            protected_emails={str(email).casefold() for email in PLATFORM_ADMIN_EMAILS},
        )
    except LookupError:
        raise HTTPException(404, "No account has this identifier.")
    except MembershipInvalid as error:
        raise HTTPException(422, str(error))
    except MembershipConflict as error:
        raise HTTPException(409, str(error))
    return _membership_body(result["account"])


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
