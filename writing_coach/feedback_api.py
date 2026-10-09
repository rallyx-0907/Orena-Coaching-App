"""Learner feedback routes (D-156): send and read one's own reviews; Platform Admin reads all of them."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from auth_support import require_admin
from writing_coach.feedback import AREAS, FeedbackInvalid, page_bounds, submit
from writing_coach.product.api import current_user_key

router = APIRouter(tags=["feedback"])

# The D-159 retention sweep (app.py installs it when FEEDBACK_RETENTION_SWEEP is on); a send starts it at most daily.
_retention = None


def configure_feedback_retention(retention) -> None:
    global _retention
    _retention = retention


def _store():
    from writing_coach.ai.platform import _installed_platform_repository

    try:
        store = _installed_platform_repository()
    except RuntimeError:
        store = None
    if store is None or not hasattr(store, "record_feedback"):
        raise HTTPException(503, "Feedback is not stored on this deployment.")
    return store


def _public(row: dict[str, Any], *, admin: bool) -> dict[str, Any]:
    created = row.get("created_at")
    item = {
        "id": row.get("id"),
        "created_at": created.isoformat() if isinstance(created, datetime) else created,
        "stars": row.get("stars"),
        "areas": row.get("areas") or [],
        "text": row.get("text") or "",
    }
    if admin:
        item.update({
            "account_id": row.get("account_id"),
            "account_key": row.get("account_key") or "",
            "name": row.get("name") or "",
            "email": row.get("email") or "",
            "language": row.get("language") or "",
            "interface": row.get("interface") or "",
        })
    return item


@router.post("/api/feedback", status_code=201)
async def feedback_send(request: Request) -> dict[str, Any]:
    user_key = current_user_key(request)
    store = _store()
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "The review must be JSON.")
    try:
        saved = submit(store, user_key, body)
    except FeedbackInvalid as error:
        raise HTTPException(422, str(error))
    except OverflowError:
        raise HTTPException(429, "You have sent the most reviews allowed today. Thank you!")
    if _retention is not None:
        _retention.maybe_sweep()
    return {"review": _public(saved, admin=False)}


@router.get("/api/feedback/mine")
def feedback_mine(request: Request) -> dict[str, Any]:
    user_key = current_user_key(request)
    try:
        store = _store()
    except HTTPException:
        return {"available": False, "items": []}
    rows = store.list_feedback(user_key=user_key, limit=50)
    return {"available": True, "items": [_public(row, admin=False) for row in rows]}


@router.get("/api/admin/feedback")
def feedback_admin(request: Request, limit: int = 50, offset: int = 0, stars: int = 0, area: str = "") -> dict[str, Any]:
    require_admin(request)
    store = _store()
    bounded, start = page_bounds(limit, offset)
    if stars and not 1 <= stars <= 5:
        raise HTTPException(422, "Stars are 1 to 5.")
    if area and area not in AREAS:
        raise HTTPException(422, "Unknown area.")
    # Every number is over all stored reviews (SQL), the list is one page of the filtered set.
    return {
        "available": True,
        "summary": store.feedback_summary(),
        "areas": list(AREAS),
        "total": store.count_feedback(stars=stars, area=area),
        "limit": bounded,
        "offset": start,
        "items": [_public(row, admin=True) for row in store.list_feedback(stars=stars, area=area, limit=bounded, offset=start)],
    }
