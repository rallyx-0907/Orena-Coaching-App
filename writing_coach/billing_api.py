"""Billing routes (completion plan item 4; proposals/BILLING_GATEWAYS.md). Off unless `BILLING_ENABLED` is on.

- `GET  /api/billing/offers`                     the approved prices whose gateway has keys (empty when off)
- `POST /api/billing/checkout`                   a signed-in learner starts paying for one price
- `POST /api/billing/webhooks/{gateway}`         a gateway's signed event (no session; the signature is the proof)
- `POST /api/admin/billing/orders/{code}/refund` an administrator records a domestic refund paid back by hand

There is no learner screen yet: the design draws no plans or checkout page (UI_BACKEND_GAPS BL-1).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field

from writing_coach.billing.service import CheckoutRefused
from writing_coach.core.errors import orena_http_error
from writing_coach.core.request_context import current_user_key
from writing_coach.persistence.ids import stable_uuid

router = APIRouter(tags=["billing"])

_service: Any = None
_backbone: Any = None
_admin: Callable[[Request], Any] | None = None
_public_base: str = ""
MAX_WEBHOOK_BYTES = 256 * 1024


def configure_billing(*, service: Any, backbone: Any, admin_guard: Callable[[Request], Any],
                      public_base_url: str) -> None:
    global _service, _backbone, _admin, _public_base
    _service, _backbone, _admin, _public_base = service, backbone, admin_guard, public_base_url.rstrip("/")


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


class RefundIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str = Field(min_length=3, max_length=200)


@router.get("/api/billing/offers")
def billing_offers() -> dict[str, Any]:
    return {"enabled": _service is not None, "offers": _service.offered() if _service is not None else []}


@router.post("/api/billing/checkout")
def billing_checkout(payload: CheckoutIn, request: Request) -> dict[str, Any]:
    service = _require_service()
    if current_user_key() in {"", "legacy", "local-admin"}:
        raise orena_http_error(401, "sign_in_required", "Sign in to pay.", retryable=False)
    incarnation = _incarnation()
    base = _public_base or str(request.base_url).rstrip("/")
    try:
        return service.start_checkout(incarnation_id=incarnation, price_key=payload.price, operation_id=payload.operation_id,
                                      return_url=f"{base}/#/profile", cancel_url=f"{base}/#/profile")  # fmt: skip
    except LookupError:
        raise orena_http_error(404, "price_not_offered", "This price is not offered.", retryable=False) from None
    except CheckoutRefused as refused:
        raise orena_http_error(409, refused.code, "This checkout cannot start.", retryable=False) from None
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
    outcome = await run_in_threadpool(service.handle_webhook, gateway, dict(request.headers), body)
    if outcome.status == "not_configured":
        return JSONResponse({"ok": False}, status_code=404)
    if outcome.status == "rejected":
        return JSONResponse({"ok": False}, status_code=401)
    # Anything verified is acknowledged: the receipt (or the order) holds it, and a redelivery is a duplicate.
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
