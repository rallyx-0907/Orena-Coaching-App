"""`/api/agent/*` (contract §2): the turn stream and the capability registry.

Off unless the server says otherwise. `AGENT_ENABLED` turns it on for a
development or sandbox runtime; production never serves it, whatever the flag
says - activating the agent for learners is a human gate (human ruling
2026-09-27). While off, both routes answer 404.

The learner is the authenticated caller, read from the request context the
auth middleware sets; the session language decides which learner data the
tools read, so a request whose target language disagrees with it is refused
before anything runs.

Each learner may send `turns_per_window` turns and `capability_reads_per_window`
capability reads in a sliding window (spec §22). One more is answered 429
`rate_limited` with `Retry-After`, after the 404 and before the body is read,
so a malformed request counts too.
"""

from __future__ import annotations

import math
import threading
from collections.abc import AsyncIterator, Iterator, Mapping

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import iterate_in_threadpool

from writing_coach.agent.events import Event, sse_frame
from writing_coach.agent.locale import interface_languages, to_internal
from writing_coach.agent.ratelimit import SlidingWindowLimiter
from writing_coach.agent.schemas import TurnRequest
from writing_coach.agent.tools import LearnerScope
from writing_coach.agent.turn import AgentRuntime

router = APIRouter(prefix="/api/agent", tags=["agent"])

_TRUE = frozenset({"1", "true", "yes", "on"})
_runtime: AgentRuntime | None = None


def agent_enabled(env: Mapping[str, str], *, production: bool) -> bool:
    """On only when the flag says so and the runtime is not production."""

    return not production and str(env.get("AGENT_ENABLED", "")).strip().casefold() in _TRUE


def configure_agent(runtime: AgentRuntime | None) -> None:
    """Install the runtime (enabled) or nothing (disabled)."""

    global _runtime
    _runtime = runtime


def _require_runtime() -> AgentRuntime:
    if _runtime is None:
        raise HTTPException(status_code=404, detail="Not Found")
    return _runtime


def _admit(limiter: SlidingWindowLimiter) -> None:
    wait = limiter.check(LearnerScope.from_request_context().user_key)
    if wait is not None:
        raise HTTPException(
            status_code=429, detail="rate_limited", headers={"Retry-After": str(max(1, math.ceil(wait)))}
        )


def _turn_allowed(runtime: AgentRuntime = Depends(_require_runtime)) -> AgentRuntime:
    # The daily spend cap first (agent/budget.py): a request it refuses is not counted in the learner's window.
    wait = runtime.spend_guard() if runtime.spend_guard is not None else None
    if wait is not None:
        raise HTTPException(status_code=429, detail="rate_limited", headers={"Retry-After": str(max(1, math.ceil(wait)))})
    _admit(runtime.turn_limiter)
    return runtime


def _read_allowed(runtime: AgentRuntime = Depends(_require_runtime)) -> AgentRuntime:
    _admit(runtime.read_limiter)
    return runtime


# `Depends` runs before the body and query are validated, so while the agent is
# off every request is 404 - a malformed one too, never a 422 naming the schema.
@router.post("/turn")
async def agent_turn(
    body: TurnRequest, request: Request, runtime: AgentRuntime = Depends(_turn_allowed)
) -> StreamingResponse:
    learner = LearnerScope.from_request_context()
    if to_internal(body.context.locale.target) != learner.language:
        raise HTTPException(status_code=409, detail="target_language_mismatch")
    stop = threading.Event()
    events: Iterator[Event] = runtime.run(body, learner, should_stop=stop.is_set)

    async def frames() -> AsyncIterator[str]:
        try:
            async for event in iterate_in_threadpool(events):
                yield sse_frame(event)
                if await request.is_disconnected():
                    stop.set()
                    break
        finally:
            stop.set()
            # Close the turn (and the provider's response) now rather than at
            # garbage collection. A turn still running in its worker thread
            # cannot be closed from here; the stop flag ends it at its next event.
            close = getattr(events, "close", None)
            if close is not None:
                try:
                    close()
                except ValueError:
                    pass

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.get("/capabilities")
def agent_capabilities(
    interface: str = Query(default="en", max_length=16), runtime: AgentRuntime = Depends(_read_allowed)
) -> dict:
    if interface not in interface_languages():
        raise HTTPException(status_code=422, detail="unknown interface language")
    target = LearnerScope.from_request_context().contract_language
    return runtime.capabilities.public(interface=interface, target=target)
