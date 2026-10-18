"""`/api/agent/memory` (contract v9 §10; ORENA_MEMORY.md rev 4.1 §6): what Orena remembers for the learner, deleted
and switched off by them.

The learner's own session only, scoped by account and active incarnation; behind `AGENT_ENABLED` like every agent
route (404 while off, before anything is read), and 503 `memory_unavailable` when this server has no Orena Memory or
the learner has no active incarnation. The state-changing routes pass the app-wide origin check every `/api/` write
does (core/http_security.py). Every change bumps the learner's memory version, so it reaches the next model call on
any worker or device (§5.2). Deleting and the switch work while memory is OFF (§6).

The listing gives each item's reason as a code and parameters, never a server-written sentence: the UI renders it in
the learner's language. Pin and session delete are M3's and are not served before it; the listing carries no session
summaries until then.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import Body, Depends, HTTPException, Query, Response

from writing_coach.agent.api import _read_allowed, _require_runtime, current_memory, router
from writing_coach.agent.locale import to_contract, to_internal
from writing_coach.agent.memory_store import (
    CONTINUITY,
    EXPLICIT,
    INFERRED,
    MemoryItem,
    MemoryScope,
    MemoryUnavailable,
)
from writing_coach.agent.tools import LearnerScope

UNAVAILABLE = "memory_unavailable"


def _memory_scope(*, create: bool) -> tuple[Any, MemoryScope]:
    memory = current_memory()
    if memory is None:
        raise HTTPException(status_code=503, detail=UNAVAILABLE)
    scope = memory.scope(LearnerScope.from_request_context().user_key, create=create)
    if scope is None:
        raise HTTPException(status_code=503, detail=UNAVAILABLE)
    return memory, scope


def _item(item: MemoryItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "kind": item.kind,
        "slot": item.slot,
        "code": item.code,
        "text": item.text,
        "language": item.language_code,
        "reason": {
            "source": item.source,
            "evidence_count": getattr(item, "evidence_count", None),
            "confidence": getattr(item, "confidence", None),
            "expires_at": item.expires_at.isoformat() if item.expires_at else None,
        },
    }


@router.get("/memory")
def list_memory(language: str | None = Query(default=None, max_length=20),
                runtime=Depends(_read_allowed)) -> dict[str, Any]:  # fmt: skip
    memory, scope = _memory_scope(create=False)
    internal = to_internal(language) if language else LearnerScope.from_request_context().language
    now = memory.clock()
    read = memory.store.snapshot(scope, internal, now, 0)  # one consistent read (§5.2)
    by_class: dict[str, list[dict[str, Any]]] = {EXPLICIT: [], INFERRED: [], CONTINUITY: []}
    for item in read.items:
        by_class.setdefault(item.cls, []).append(_item(item))
    return {
        "language": to_contract(internal),
        "enabled": read.state.enabled,
        "version": read.state.version,
        "items": by_class,
        "sessions": [],  # M3
    }


@router.delete("/memory/items/{item_id}", status_code=204)
def delete_memory_item(item_id: str, runtime=Depends(_require_runtime)) -> Response:
    memory, scope = _memory_scope(create=False)
    try:
        deleted = memory.store.delete_item(scope, item_id, memory.clock())
    except MemoryUnavailable:
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None
    if not deleted:
        raise HTTPException(status_code=404, detail="not_found")
    return Response(status_code=204)


@router.delete("/memory")
def delete_memory(scope: Literal["items", "sessions", "all"] = Query(...),
                  runtime=Depends(_require_runtime)) -> dict[str, Any]:  # fmt: skip
    memory, memory_scope = _memory_scope(create=False)
    try:
        removed = memory.store.delete_all(memory_scope, scope, memory.clock())
    except MemoryUnavailable:
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None
    return {"removed": removed, "version": memory.store.state(memory_scope).version}


@router.put("/memory/settings")
def memory_settings(enabled: bool = Body(..., embed=True), runtime=Depends(_require_runtime)) -> dict[str, Any]:
    memory, scope = _memory_scope(create=True)
    try:
        state = memory.store.set_enabled(scope, enabled)
    except MemoryUnavailable:
        raise HTTPException(status_code=503, detail=UNAVAILABLE) from None
    return {"enabled": state.enabled, "version": state.version}
