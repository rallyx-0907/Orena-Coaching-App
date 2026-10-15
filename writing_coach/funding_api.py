"""Read-only funding answers for the learner UI and the operator (PR-MON-6 §8, §10).

- `GET /api/billing/funding`: per metered feature, whether the plan enables it, what allowance and promotional grants
  remain, whether credits may fund it and at what price per unit, and the credit balance.
- `GET /api/billing/estimate?meter=&units=`: which source would fund that much work now, the credits it would need,
  or why it would be refused - without reserving anything. This is what "this will use 2 credits" is drawn from.
- `GET /api/admin/billing/cost-model`: the operation-level cost evidence per meter and the per-pack gate (§8).

All of it is server-computed (the UI never does arithmetic on prices) and none of it writes.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query, Request

from writing_coach.core.errors import orena_http_error
from writing_coach.core.request_context import current_user_key

router = APIRouter()

_funding: Any = None
_admin: Callable[[Request], Any] | None = None


def configure_funding_api(*, funding: Any, admin_guard: Callable[[Request], Any]) -> None:
    global _funding, _admin
    _funding, _admin = funding, admin_guard


def _plan_and_usage(user_key: str) -> tuple[Any, dict[str, Any], dict[str, dict[str, Any]], Any]:
    from writing_coach.product import quota
    from writing_coach.product.catalog import CatalogUnavailable, current_catalog

    runtime = quota.runtime()
    if runtime.plan_for is None:
        raise orena_http_error(503, "quota_unavailable", "Usage cannot be read right now.", retryable=True)
    try:
        plans, _revision = current_catalog(strict=True)
        plan = plans.get(runtime.plan_for(user_key, strict=True).id)
    except CatalogUnavailable:
        plan = None
    if plan is None:
        raise orena_http_error(503, "quota_unavailable", "Usage cannot be read right now.", retryable=True)
    incarnation = None
    if runtime.incarnations is not None:
        try:
            incarnation = runtime.incarnations.resolve(quota.account_id(user_key))
        except Exception:  # noqa: BLE001 - no incarnation, no balances: reported as unknown
            incarnation = None
    return plan, plan.entitlement_map(), quota.usage_for(user_key, plan), incarnation


def _promotional(incarnation: Any, meter: str) -> list[dict[str, Any]]:
    if _funding is None or incarnation is None:
        return []
    from writing_coach.billing.promotional import remaining

    try:
        rows = remaining(_funding.repository.engine, str(incarnation), meter)
    except Exception:  # noqa: BLE001 - absent tables or a failed read: nothing promised
        return []
    return [{"grant": row["grant_id"], "remaining": max(0, int(row["remaining"])),
             "expires_at": row["expires_at"].astimezone(UTC).isoformat().replace("+00:00", "Z")} for row in rows]


def _balance(incarnation: Any) -> dict[str, Any] | None:
    if _funding is None or incarnation is None or _funding.repository.credits is None:
        return None
    try:
        account = _funding.repository.credits.account(str(incarnation))
    except Exception:  # noqa: BLE001
        return None
    if account is None:
        return {"available": 0, "held": 0}
    return {"available": int(account["available"]), "held": int(account["reserved"])}


def _meter_view(meter: str, entitlement: Any, usage: dict[str, Any], incarnation: Any) -> dict[str, Any]:
    enabled = bool(entitlement is not None and entitlement.enabled)
    limit = entitlement.limit if entitlement is not None else None
    allowance: dict[str, Any] = {"metered": usage.get("state") == "known", "limit": limit}
    if usage.get("state") == "known":
        used = int(usage.get("used", 0))
        allowance.update({"used": used, "remaining": None if limit is None else max(0, limit - used),
                          "window_resets_at": usage.get("resets_at")})
    elif usage.get("state") == "unavailable":
        allowance["state"] = "unavailable"
    terms = _funding.credit_terms(meter)[0] if _funding is not None else None
    return {"meter": meter, "enabled": enabled, "allowance": allowance, "promotional": _promotional(incarnation, meter),
            "credit_eligible": terms is not None, "price_per_unit": terms.price if terms is not None else None}


@router.get("/api/billing/funding")
def billing_funding() -> dict[str, Any]:
    from writing_coach.product.quota import WIRED_METERS

    user_key = current_user_key()
    plan, entitlements, usage, incarnation = _plan_and_usage(user_key)
    meters = [_meter_view(meter, entitlements.get(meter), usage.get(meter, {}), incarnation) for meter in WIRED_METERS]
    return {"plan": plan.id, "meters": meters, "credits": _balance(incarnation)}


@router.get("/api/billing/estimate")
def billing_estimate(meter: str = Query(min_length=3, max_length=80), units: int = Query(default=1, ge=1, le=100_000)
                     ) -> dict[str, Any]:
    """Pre-flight, no reservation: the source that would fund `units` of `meter` now, in the gate's order."""
    from writing_coach.product.quota import WIRED_METERS, enforces

    if meter not in WIRED_METERS:
        raise orena_http_error(404, "meter_unknown", "No such metered feature.", retryable=False)
    user_key = current_user_key()
    _plan, entitlements, usage, incarnation = _plan_and_usage(user_key)
    view = _meter_view(meter, entitlements.get(meter), usage.get(meter, {}), incarnation)
    answer: dict[str, Any] = {"meter": meter, "units": units, "credits_needed": 0}
    if not view["enabled"]:
        return {**answer, "refused": True, "status": 403, "reason": "feature_not_in_plan"}
    if not enforces(meter):
        return {**answer, "refused": False, "source": "not_metered"}
    if sum(grant["remaining"] for grant in view["promotional"][:1]) >= units:
        return {**answer, "refused": False, "source": "promotional"}
    remaining = view["allowance"].get("remaining")
    if view["allowance"].get("metered") and (view["allowance"]["limit"] is None or (remaining or 0) >= units):
        return {**answer, "refused": False, "source": "allowance"}
    if not view["credit_eligible"]:
        reason = "allowance_exhausted" if meter == "media.import" else "not_credit_eligible"
        return {**answer, "refused": True, "status": 429, "reason": reason}
    needed = int(view["price_per_unit"]) * units
    balance = _balance(incarnation) or {"available": 0}
    if balance["available"] < needed:
        return {**answer, "refused": True, "status": 429, "reason": "insufficient_credits", "credits_needed": needed,
                "credits_available": balance["available"]}
    return {**answer, "refused": False, "source": "credits", "credits_needed": needed}


@router.get("/api/admin/billing/cost-model")
def billing_cost_model(request: Request, days: int = Query(default=90, ge=1, le=400)) -> dict[str, Any]:
    if _admin is None:
        raise orena_http_error(503, "funding_off", "Funding is not open on this deployment.", retryable=False)
    _admin(request)
    if _funding is None:
        raise orena_http_error(503, "funding_off", "Funding is not open on this deployment.", retryable=False)
    from writing_coach.billing.cost_model import meter_stats, read_operations

    operations, unattributed = read_operations(_funding.repository.engine,
                                               since=datetime.now(UTC) - timedelta(days=days),
                                               tier_of=_funding.tier_of)  # fmt: skip
    stats = meter_stats(operations)
    gate = _funding.gate(refresh=True)
    return {"days": days, "meters": [entry.as_dict() for _meter, entry in sorted(stats.items())],
            "unattributed_calls": unattributed,
            "gate": {"id": gate.gate_id, "meters": gate.meters, "packs": gate.packs, "reasons": gate.reasons,
                     "inputs_configured": _funding.gate_inputs_configured}}
