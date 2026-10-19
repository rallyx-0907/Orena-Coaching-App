"""A plan feature that is on or off, not counted: voice chat with Orena (`orena.voice`).

Owner, 2026-10-19: voice chat with Orena is for Plus and Pro only; Free chats in text. Speaking practice is a different
feature and is not touched. The catalogue's `orena.voice` entitlement (Free off, Plus and Pro on by the code's defaults)
decides, read from the strict catalogue and the account's effective plan - a plan an administrator granted (D-154)
counts. It is a product rule, so it holds whether or not usage limits are enforced. A plan or catalogue that cannot be
read refuses (503 `quota_unavailable`, fail closed). A server with no plan system at all (no `plan_for`: tests, a bare
development server) has no plans to tell apart, and lets the feature through.
"""

from __future__ import annotations

from writing_coach.core.errors import orena_http_error
from writing_coach.product import quota
from writing_coach.product.catalog import CatalogUnavailable, current_catalog

VOICE = "orena.voice"


def _plan(user_key: str):
    """The account's effective plan from the strict catalogue; None when this server has no plan system."""

    runtime = quota.runtime()
    if runtime.plan_for is None:
        return None
    try:
        plans, _revision = current_catalog(strict=True)
        plan = plans.get(runtime.plan_for(user_key, strict=True).id)
    except CatalogUnavailable as error:
        raise quota._unavailable("catalogue") from error
    except Exception as error:  # noqa: BLE001 - the subscription store or the plan read failed: fail closed
        raise quota._unavailable("subscription") from error
    if plan is None:
        raise quota._unavailable("catalogue")
    return plan


def require(user_key: str, feature: str) -> None:
    """403 `feature_not_in_plan` when the account's plan does not include `feature`; 503 when it cannot be read."""

    plan = _plan(user_key)
    if plan is None:
        return
    entitlement = plan.entitlement_map().get(feature)
    if entitlement is None or not entitlement.enabled:
        raise orena_http_error(403, "feature_not_in_plan", "This feature is not part of your plan.", retryable=False,
                               context={"feature": feature, "plan": plan.id, "upgrade": quota.UPGRADE_HREF})


def entitled(user_key: str, feature: str) -> bool | None:
    """Whether the account's plan includes `feature`; None when the plan cannot be read right now - not "no", so a
    paying learner is never shown an upgrade over a moment's outage (`require` still refuses it with a 503)."""

    from fastapi import HTTPException

    try:
        require(user_key, feature)
    except HTTPException as refused:
        return None if refused.status_code == 503 else False
    return True
