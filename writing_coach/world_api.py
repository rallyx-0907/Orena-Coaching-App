"""World discovery boundary.

Home asks "what places can this learner enter today?" and gets back semantic
content: which worlds exist, whether each one currently holds real lessons, and
which lesson leads it. No layout, no column counts, no card sizes - the client
decides composition (ORENA_PRODUCT_DNA §12).

Preview content follows exactly the rule discovery already enforces: the same
`preview_visible` check gates the lessons a world is measured against, so an
unreviewed preview lesson can never inflate a world's count for a learner who
is not allowed to see it.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request

from writing_coach.core.request_context import current_language_code
from writing_coach.listening_api import preview_visible
from writing_coach.world_catalog import worlds_for_language

router = APIRouter(prefix="/api/worlds", tags=["worlds"])


@router.get("")
def list_worlds(
    language: str | None = Query(default=None, min_length=2, max_length=32),
    request: Request = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    selected = (language or current_language_code() or "").strip().casefold()
    worlds = worlds_for_language(selected, include_preview=preview_visible(request))
    return {
        "language": selected,
        "worlds": worlds,
        "available_count": sum(1 for world in worlds if world["available"]),
    }
