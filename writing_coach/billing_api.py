"""Billing routes (completion plan item 4; proposals/BILLING_GATEWAYS.md). Off unless `BILLING_ENABLED` is on.

- `GET  /api/billing/offers`                     the approved prices whose gateway has keys (empty unless ready)
- `POST /api/billing/checkout`                   a signed-in learner starts paying for one price
- `POST /api/billing/webhooks/{gateway}`         a gateway's signed event (no session; the signature is the proof)
- `POST /api/admin/billing/orders/{code}/refund` an administrator records a domestic refund paid back by hand
- `GET  /api/admin/billing/readiness`            why this runtime can or cannot take a payment (no secrets, PR-MON-2)
- `GET  /api/admin/billing/reconciliation`       the money anomalies kept for an operator (PR-MON-3)
- `POST /api/admin/billing/reconciliation/{id}/resolve`  close one, under its kind's rule; moves no money
- `POST /api/admin/billing/reconcile`            run one reconciliation pass now
- `GET  /api/admin/billing/credits/{incarnation}`              a credit balance and its ledger page (PR-MON-4)
- `POST /api/admin/billing/credits/{incarnation}/adjustments`  an audited ledger delta (C4); never "set balance"

Only the learner entrypoints (offers, checkout) require the runtime to be billing-ready (`billing.readiness`, the
PR-MON-2 review P1): a runtime that is not starts no new payment. A verified webhook and the administrator's routes
never wait on it - money already taken is still received and reconciled.

A verified webhook is acknowledged only once it is durable (PR-MON-3): an anomaly is recorded first, and when
nothing could be recorded the answer is 503, so the provider delivers it again.

There is no learner screen yet: the design draws no plans or checkout page (UI_BACKEND_GAPS BL-1).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
import uuid
from collections.abc import Callable
from typing import Any, Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, field_validator

from writing_coach.billing.service import CREDIT_PREFIX, CheckoutRefused
from writing_coach.core.errors import orena_http_error
from writing_coach.core.request_context import current_user_key
from writing_coach.persistence.ids import stable_uuid

router = APIRouter(tags=["billing"])
_log = logging.getLogger(__name__)

_service: Any = None
_backbone: Any = None
_admin: Callable[[Request], Any] | None = None
_public_base: str = ""
_ready: Callable[[], bool] | None = None  # None: `billing.readiness.billing_ready`
_items: Any = None  # the reconciliation items (PR-MON-3)
_reconcile: Callable[[], Any] | None = None  # one reconciliation pass
_credits: Any = None  # the credit service (PR-MON-4), only when credits are enabled
_sepay_backfill: Callable[[Any, Any], dict] | None = None  # PR-MON-8 §6.4, the operator's SePay recovery
_email: Callable[[Request], str] | None = None  # the signed-in learner's email, for Polar's checkout (PR-MON-10 §4.1)
MAX_WEBHOOK_BYTES = 256 * 1024


def configure_billing(*, service: Any, backbone: Any, admin_guard: Callable[[Request], Any],
                      public_base_url: str, reconciliation: Any = None,
                      reconcile: Callable[[], Any] | None = None, credits: Any = None,
                      sepay_backfill: Callable[[datetime, datetime], dict] | None = None,
                      email: Callable[[Request], str] | None = None) -> None:
    global _service, _backbone, _admin, _public_base, _items, _reconcile, _credits, _sepay_backfill, _email
    _service, _backbone, _admin, _public_base = service, backbone, admin_guard, public_base_url.rstrip("/")
    _items, _reconcile, _credits = reconciliation, reconcile, credits
    _sepay_backfill = sepay_backfill
    _email = email


def _billing_ready() -> bool:
    if _ready is not None:
        return bool(_ready())
    from writing_coach.billing import readiness

    return readiness.billing_ready()


def _learner_email(request: Request) -> str:
    """The signed-in learner's email, or "" (Polar then asks for it). Never logged."""

    if _email is None:
        return ""
    try:
        return str(_email(request) or "")
    except Exception:  # noqa: BLE001 - an email that cannot be read is simply not prefilled
        return ""


def _capability_ready(name: str) -> bool:
    """`plans` or `credits` (PR-MON-8 §14.4): offers and checkouts open per capability, never the other's."""

    if _ready is not None:
        return bool(_ready())
    from writing_coach.billing import readiness

    return readiness.capability_ready(name)


def _require_service() -> Any:
    if _service is None:
        raise orena_http_error(503, "billing_off", "Payments are not open on this deployment.", retryable=False)
    return _service


def _incarnation() -> str:
    if _backbone is None or not _backbone.is_active:
        raise orena_http_error(503, "account_backbone_off", "Accounts cannot pay on this deployment.", retryable=False)
    from writing_coach.persistence.incarnation_repository import DeletionBarrier

    try:
        return _backbone.incarnations.ensure_active(str(stable_uuid("user", current_user_key())))
    except DeletionBarrier:
        raise orena_http_error(403, "account_deleted", "This account was deleted.", retryable=False) from None


class CheckoutIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    price: str = Field(min_length=3, max_length=120)
    operation_id: str = Field(min_length=36, max_length=36)
    # The price the learner was shown and confirmed (an offer's `amount_minor` and `currency`). Never charged - the
    # server's price is - but a checkout whose confirmed price is not the server's does not start (D-MON-015).
    amount_minor: int | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    # A credit pack's confirmed units (PR-MON-5): a checkout whose units are not the pack's does not start.
    credit_units: int | None = Field(default=None, gt=0)


# A refused checkout's HTTP answer; anything not named is a conflict with the account's state (409).
_REFUSAL_STATUS = {"catalog_unavailable": 503, "price_unconfirmed": 422, "reconciliation_critical": 503,
                   "credits_not_ready": 503}


class ResolveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resolution: Literal["resolved", "dismissed"]
    outcome: str | None = Field(default=None, max_length=30)
    reference: str | None = Field(default=None, max_length=200)
    note: str = Field(min_length=3, max_length=400)


class AdjustmentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    delta: int = Field(ge=-10**12, le=10**12)
    operation_id: str = Field(min_length=8, max_length=200)
    reason: str = Field(min_length=3, max_length=400)

    @field_validator("delta")
    @classmethod
    def _a_delta(cls, value: int) -> int:
        if value == 0:
            raise ValueError("an adjustment is a non-zero delta")
        return value


class RefundIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str = Field(min_length=3, max_length=200)


@router.get("/api/billing/offers")
def billing_offers() -> dict[str, Any]:
    ready = _service is not None and _billing_ready()
    plans = ready and _capability_ready("plans")
    credits = ready and _capability_ready("credits")
    return {"enabled": _service is not None, "ready": ready, "offers": _service.offered() if plans else [],
            # PR-MON-5 (K5): credit packs, only while the Credits capability is ready (PR-MON-8 §14.4)
            "credit_packs": _service.credit_offers() if credits else []}


@router.post("/api/billing/checkout")
def billing_checkout(payload: CheckoutIn, request: Request) -> dict[str, Any]:
    service = _require_service()
    capability = "credits" if payload.price.startswith(CREDIT_PREFIX) else "plans"
    # before an order is written or a gateway is called; a capability that is not ready sells nothing (§14.4)
    if not _billing_ready() or not _capability_ready(capability):
        raise orena_http_error(503, "billing_not_ready", "Payments are not open right now. Try again later.",
                               retryable=True)
    if current_user_key() in {"", "legacy", "local-admin"}:
        raise orena_http_error(401, "sign_in_required", "Sign in to pay.", retryable=False)
    incarnation = _incarnation()
    base = _public_base or str(request.base_url).rstrip("/")
    # PR-MON-10 §4.1: a plan returns to Plan & usage (the page shows the outcome; only a webhook grants);
    # a credit top-up keeps its existing return page.
    done, back = ((f"{base}/#/plan?checkout=done", f"{base}/#/plan") if capability == "plans"
                  else (f"{base}/#/profile", f"{base}/#/profile"))  # fmt: skip
    try:
        return service.start_checkout(incarnation_id=incarnation, price_key=payload.price, operation_id=payload.operation_id,
                                      return_url=done, cancel_url=back,
                                      confirmed_amount_minor=payload.amount_minor,
                                      confirmed_currency=payload.currency,
                                      confirmed_credit_units=payload.credit_units,
                                      customer_email=_learner_email(request))  # fmt: skip
    except LookupError:
        raise orena_http_error(404, "price_not_offered", "This price is not offered.", retryable=False) from None
    except CheckoutRefused as refused:
        status = _REFUSAL_STATUS.get(refused.code, 409)
        raise orena_http_error(status, refused.code, "This checkout cannot start.", retryable=status == 503) from None
    except ValueError:
        raise orena_http_error(422, "operation_id_invalid", "An operation id is a UUID.", retryable=False) from None
    except Exception:  # noqa: BLE001 - the gateway's own failure: say so, change nothing else
        raise orena_http_error(502, "gateway_unavailable", "The payment page could not be opened. Try again.",
                               retryable=True) from None


@router.post("/api/billing/webhooks/{gateway}")
async def billing_webhook(gateway: str, request: Request) -> JSONResponse:
    service = _require_service()
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_WEBHOOK_BYTES:
        return JSONResponse({"ok": False}, status_code=413)
    body = b""
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_WEBHOOK_BYTES:
            return JSONResponse({"ok": False}, status_code=413)
    try:
        outcome = await run_in_threadpool(service.handle_webhook, gateway, dict(request.headers), body)
    except Exception:  # noqa: BLE001 - nothing durable was recorded: the provider must deliver it again
        _log.exception("billing webhook from %s could not be recorded; answered 503 for a retry", gateway)
        return JSONResponse({"ok": False}, status_code=503)
    if outcome.status == "not_configured":
        return JSONResponse({"ok": False}, status_code=404)
    if outcome.status == "rejected":
        return JSONResponse({"ok": False}, status_code=401)
    # Anything verified is acknowledged: the receipt (or the order) holds it, and a redelivery is a duplicate.
    # PR-MON-8 G4: a gateway with its own success shape (SePay counts only {"success": true}) is answered in it.
    ack = getattr((getattr(service, "gateways", None) or {}).get(gateway), "ack", None)
    if callable(ack):
        return JSONResponse(ack())
    return JSONResponse({"ok": True, "status": outcome.status})


@router.post("/api/admin/billing/orders/{order_code}/refund")
def billing_record_refund(order_code: int, payload: RefundIn, request: Request) -> dict[str, Any]:
    if _admin is None:
        raise orena_http_error(503, "billing_off", "Payments are not open on this deployment.", retryable=False)
    _admin(request)  # the administrator first, then whether billing is on
    outcome = _require_service().record_refund(order_code=order_code, note=payload.note)
    if outcome.status == "unknown_order":
        raise orena_http_error(404, "order_not_found", "No such order.", retryable=False)
    return {"ok": outcome.status in {"apply", "applied", "duplicate"}, "status": outcome.status}


@router.get("/api/admin/billing/readiness")
def billing_readiness(request: Request) -> dict[str, Any]:
    """The runtime's billing readiness: each capability's state, every blocker, and each gateway's prices against
    the catalogue (`writing_coach.billing.readiness`). States and booleans only - never a key or a secret."""
    if _admin is None:
        raise orena_http_error(503, "billing_off", "Payments are not open on this deployment.", retryable=False)
    _admin(request)
    from writing_coach.billing import readiness

    return readiness.current_report()


def _admin_items(request: Request) -> Any:
    if _admin is None:
        raise orena_http_error(503, "billing_off", "Payments are not open on this deployment.", retryable=False)
    admin = _admin(request)  # the administrator first, then whether reconciliation exists
    if _items is None:
        raise orena_http_error(503, "billing_off", "Payments are not open on this deployment.", retryable=False)
    return admin


@router.get("/api/admin/billing/reconciliation")
def billing_reconciliation(request: Request, state: str | None = None, kind: str | None = None) -> dict[str, Any]:
    """The money anomalies kept for an operator: facts and links, never a raw payload, an email or card data."""

    _admin_items(request)
    items = _items.items(state=state or None, kind=kind or None)
    return {"summary": _items.summary(), "items": [_public_item(item) for item in items]}


@router.post("/api/admin/billing/reconciliation/{item_id}/resolve")
def billing_reconciliation_resolve(item_id: str, payload: ResolveIn, request: Request) -> dict[str, Any]:
    """Close one item under its kind's rule (PR-MON-3 §4.2, H6). It records what happened; it moves no money and
    changes no access - a refund, a grant or a revoke is its own operation."""

    from writing_coach.persistence.billing_reconciliation_repository import ResolutionRefused

    admin = _admin_items(request)
    try:
        key = uuid.UUID(item_id)
    except ValueError:
        raise orena_http_error(404, "item_not_found", "No such item.", retryable=False) from None
    actor = str(admin.get("google_sub") or "admin") if isinstance(admin, dict) else "admin"
    try:
        item = _items.resolve(key, resolution=payload.resolution, outcome=payload.outcome,
                              reference=payload.reference, note=payload.note, actor=actor)  # fmt: skip
    except LookupError:
        raise orena_http_error(404, "item_not_found", "No such item.", retryable=False) from None
    except ResolutionRefused as refused:
        raise orena_http_error(409, refused.code, "This item cannot be closed that way.", retryable=False) from None
    return {"ok": True, "item": _public_item(item)}


class SePayBackfillIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date_from: datetime
    date_to: datetime
    # The boundary a previous, incomplete run returned: the run continues after it (§6.4).
    resume_after: str | None = Field(default=None, min_length=1, max_length=80)


@router.post("/api/admin/billing/sepay/backfill")
def billing_sepay_backfill(payload: SePayBackfillIn, request: Request) -> dict[str, Any]:
    """PR-MON-8 §6.4: an operator's recovery of one SePay date range through the same rules and payment path as the
    feed. It never moves the feed's cursor. Needs SEPAY_API_TOKEN; works while the feed itself is off."""

    _admin_items(request)
    if _sepay_backfill is None:
        raise orena_http_error(503, "sepay_backfill_unavailable", "SePay recovery is not configured here.",
                               retryable=False)
    start, end = (value if value.tzinfo else value.replace(tzinfo=UTC) for value in (payload.date_from, payload.date_to))
    try:
        result = _sepay_backfill(start, end, resume_after=payload.resume_after)
    except ValueError as invalid:
        raise orena_http_error(422, "backfill_range_invalid", str(invalid), retryable=False) from None
    except PermissionError:
        raise orena_http_error(503, "sepay_backfill_unavailable", "SePay recovery is not configured here.",
                               retryable=False) from None
    if not result["complete"]:
        # A partial recovery is never a success: the operator continues with `resume_after` (after `retry_after`).
        status = 429 if result["reason"] == "rate_limited" else 409
        raise orena_http_error(status, "backfill_incomplete", "The range is not fully recovered yet; resume it.",
                               retryable=True, context={"reason": result["reason"],
                                                        "resume_after": result["resume_after"],
                                                        "retry_after": result["retry_after"],
                                                        "counts": result["counts"]})
    return {"ok": True, "complete": True, "counts": result["counts"]}


@router.post("/api/admin/billing/reconcile")
def billing_reconcile_now(request: Request) -> dict[str, Any]:
    _admin_items(request)
    if _reconcile is None:
        raise orena_http_error(503, "billing_off", "Payments are not open on this deployment.", retryable=False)
    counts = _reconcile()
    return {"ran": counts is not None, "counts": counts or {}}


def _public_item(item: dict[str, Any]) -> dict[str, Any]:
    return {key: (str(value) if isinstance(value, uuid.UUID)
                  else value.isoformat() if hasattr(value, "isoformat") else value)
            for key, value in item.items()}  # fmt: skip


# ---- credits (PR-MON-4): read and audited adjustment only; top-up is PR-MON-5, consumption PR-MON-6 ----------------

_CREDIT_REFUSAL = {"credits_runtime_privileged": 503, "account_under_review": 409, "insufficient_credits": 409,
                   "conflict": 409, "not_found": 404, "invalid": 422}


def _admin_credits(request: Request) -> Any:
    if _admin is None:
        raise orena_http_error(503, "credits_off", "Credits are not open on this deployment.", retryable=False)
    admin = _admin(request)  # the administrator first, then whether credits exist
    if _credits is None:
        raise orena_http_error(503, "credits_off", "Credits are not open on this deployment.", retryable=False)
    return admin


def _incarnation_key(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise orena_http_error(404, "account_not_found", "No such account.", retryable=False) from None


@router.get("/api/admin/billing/credits/{incarnation_id}")
def billing_credit_account(incarnation_id: str, request: Request, before_seq: int | None = None) -> dict[str, Any]:
    _admin_credits(request)
    key = _incarnation_key(incarnation_id)
    return {"status": _credits.status(), "account": _public_item(_credits.balance(key) or {}),
            "entries": [_public_item(entry) for entry in _credits.entries(key, before_seq=before_seq)]}


@router.post("/api/admin/billing/credits/{incarnation_id}/adjustments")
def billing_credit_adjustment(incarnation_id: str, payload: AdjustmentIn, request: Request) -> dict[str, Any]:
    """An administrator's correction, as an audited ledger delta (C4): reason, actor and an idempotency key, never
    below zero, and no "set balance"."""

    admin = _admin_credits(request)
    key = _incarnation_key(incarnation_id)
    actor = str(admin.get("google_sub") or "admin") if isinstance(admin, dict) else "admin"
    if _credits.ensure_account(key) is None:
        raise orena_http_error(503, "credits_runtime_privileged", "Credits are refused on this connection.",
                               retryable=False)
    outcome = _credits.adjust(key, delta=payload.delta, operation_id=payload.operation_id, actor=actor,
                              reason=payload.reason)  # fmt: skip
    if not outcome.ok:
        status = _CREDIT_REFUSAL.get(outcome.status, 409)
        raise orena_http_error(status, outcome.status, "This adjustment cannot be recorded.", retryable=status == 503)
    return {"ok": True, "status": outcome.status, "entry": _public_item(outcome.entry or {})}
