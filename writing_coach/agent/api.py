"""`/api/agent/*` (contract §2): the turn stream and the capability registry.

Off unless the server says otherwise. `AGENT_ENABLED` is the switch in every
environment (D-146: the environment is not a feature switch); turning it on for
a runtime learners use is the human's decision. While off, both routes answer
404.

The learner is the authenticated caller, read from the request context the
auth middleware sets; the session language decides which learner data the
tools read, so a request whose target language disagrees with it is refused
before anything runs.

Each learner may send `turns_per_window` turns and `capability_reads_per_window`
capability reads in a sliding window (spec §22). One more is answered 429
`rate_limited` with `Retry-After`, after the 404 and before the body is read,
so a malformed request counts too.

Plan quota (D-163): when `orena.message` is enforced, a learner's message turn is admitted
before anything streams - exhausted is a plain 429 `quota_exhausted` JSON response, never an
SSE frame - and the opening greeting and the answers that ask no model are free (agent/turn.py).
Live voice is charged against the same meter by duration (D-169, contract v8): one message per
`voice_seconds_per_message` seconds, one short vendor token at a time. `POST /voice/session` mints the first
chunk and `POST /voice/extend` each next one (agent/voice_session.py): every chunk is admitted before its token is
minted - 429 `quota_exhausted` when not even one message remains, 503 `quota_unavailable` when enforcement cannot be
read - and charged whole when the token exists. `/voice/end` only stops further chunks.
"""

from __future__ import annotations

import math
import threading
from collections.abc import AsyncIterator, Iterator, Mapping

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from starlette.concurrency import iterate_in_threadpool, run_in_threadpool

from writing_coach.agent.events import Event, sse_frame
from writing_coach.agent.locale import interface_languages, to_internal
from writing_coach.agent.ratelimit import SlidingWindowLimiter
from writing_coach.agent.schemas import TurnRequest
from writing_coach.agent.tools import LearnerScope
from writing_coach.agent.turn import AgentRuntime, TurnRefused, learner_context
from writing_coach.agent.voice_session import VoiceService, voice_catalog
from writing_coach.ai.live_voice import VoiceUnavailable
from writing_coach.product import quota

router = APIRouter(prefix="/api/agent", tags=["agent"])

_TRUE = frozenset({"1", "true", "yes", "on"})
_runtime: AgentRuntime | None = None
_NO_MORE = object()
MESSAGE_METER = "orena.message"


def agent_enabled(env: Mapping[str, str]) -> bool:
    """AGENT_ENABLED is the switch, in every environment (D-146): the environment is not a feature switch."""

    return str(env.get("AGENT_ENABLED", "")).strip().casefold() in _TRUE


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


def _message_admission(body: TurnRequest, learner: LearnerScope):
    """One learner message of `orena.message`, reserved when the turn reaches its model (agent/turn.py). The
    request's own facts (Idempotency-Key, timezone) are captured here, in the request's context, and replayed in
    the turn's worker thread, where the contextvars are not the request's."""

    facts = quota.current_facts()
    digest = quota.request_digest(body)

    def admission():
        with learner_context(learner), quota.request_facts(
            idempotency_key=facts.idempotency_key, timezone=facts.timezone
        ):
            return quota.begin(MESSAGE_METER, units=1, request_digest=digest)

    return admission


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
    events: Iterator[Event] = runtime.run(
        body, learner, should_stop=stop.is_set, admission=_message_admission(body, learner)
    )
    # The turn is admitted (or refused) before its first event is released: read that event here, before the response
    # exists, so a plan-limit refusal is an ordinary 429 and never a frame in a stream.
    try:
        first = await run_in_threadpool(next, events, _NO_MORE)
    except TurnRefused as refused:
        raise refused.cause from None

    async def frames() -> AsyncIterator[str]:
        try:
            if first is not _NO_MORE:
                yield sse_frame(first)
                if await request.is_disconnected():
                    stop.set()
                    return
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


# --- live voice (contract §9, mode A: R28) -------------------------------------------------------------------------


def voice_enabled(env: Mapping[str, str]) -> bool:
    """Voice is on only where the agent is, and only when `AGENT_VOICE_ENABLED` says so."""

    return str(env.get("AGENT_VOICE_ENABLED", "")).strip().casefold() in _TRUE


def voice_resumption(env: Mapping[str, str]) -> bool:
    """Session resumption in a metered voice session's token (D-169): on unless `AGENT_VOICE_RESUMPTION` is false, the
    switch for a vendor that accepts the token but refuses its socket because of the field."""

    return str(env.get("AGENT_VOICE_RESUMPTION", "")).strip().casefold() not in {"0", "false", "no", "off"}


def _voice(runtime: AgentRuntime) -> VoiceService:
    if runtime.voice is None:
        raise HTTPException(status_code=404, detail="Not Found")
    return runtime.voice


def _voice_session_allowed(runtime: AgentRuntime = Depends(_turn_allowed)) -> VoiceService:
    return _voice(runtime)  # the daily spend cap and the learner's turn window count a session as a turn


def _voice_call_allowed(runtime: AgentRuntime = Depends(_read_allowed)) -> VoiceService:
    return _voice(runtime)


def _voice_extend_allowed(runtime: AgentRuntime = Depends(_require_runtime)) -> VoiceService:
    # A renewal mints a paid token, so the daily spend cap applies to it as to an opening; but it carries on a
    # conversation the learner already opened, so it is not counted as one more turn of their window.
    wait = runtime.spend_guard() if runtime.spend_guard is not None else None
    if wait is not None:
        raise HTTPException(status_code=429, detail="rate_limited", headers={"Retry-After": str(max(1, math.ceil(wait)))})
    _admit(runtime.read_limiter)
    return _voice(runtime)


@router.post("/voice/session")
def agent_voice_session(body: dict = Body(...), voice: VoiceService = Depends(_voice_session_allowed)) -> dict:
    # Voice talks to the vendor directly on a token minted here, a chunk of it at a time. The plan messages are
    # charged by `VoiceService.open` before the token exists (429 / 503 / 409 / 403 are the quota gate own).
    learner = LearnerScope.from_request_context()
    try:
        target = to_internal(str(((body.get("context") or {}).get("locale") or {}).get("target") or ""))
    except Exception:
        target = ""
    if target and target != learner.language:
        raise HTTPException(status_code=409, detail="target_language_mismatch")
    try:
        return voice.open(body, learner)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_url=False, include_context=False)) from exc
    except VoiceUnavailable as exc:
        raise HTTPException(status_code=503, detail="voice_unavailable") from exc


@router.post("/voice/extend")
def agent_voice_extend(body: dict = Body(...), voice: VoiceService = Depends(_voice_extend_allowed)) -> dict:
    """The next chunk of a voice session (contract §9, v8): a new vendor token, admitted and charged like the first.
    `chunk` is the index wanted (the number of tokens the client holds); a repeat of the last request returns the same
    token without a second charge. 429 `quota_exhausted` when no message is left, 503 `quota_unavailable` when the
    limit cannot be read, 404 `voice_session_not_found` when the session is over, 409 for a chunk out of order or a
    session at its time limit: in every case the client ends the session when the token it holds dies."""

    learner = LearnerScope.from_request_context()
    try:
        answer = voice.extend(str(body.get("voice_session_id") or ""), learner, body.get("chunk"), body.get("resumption"))
    except VoiceUnavailable as exc:
        raise HTTPException(status_code=503, detail="voice_unavailable") from exc
    if answer is None:
        raise HTTPException(status_code=404, detail="voice_session_not_found")
    return answer


@router.get("/voice/voices")
def agent_voice_voices(
    interface: str = Query(default="en", max_length=16), voice: VoiceService = Depends(_voice_call_allowed)
) -> dict:
    """Orena's voices to choose from (R29), labelled in the interface language; the choice goes in the session body."""

    if interface not in interface_languages():
        raise HTTPException(status_code=422, detail="unknown interface language")
    return voice_catalog(interface)


@router.post("/voice/tool")
def agent_voice_tool(body: dict = Body(...), voice: VoiceService = Depends(_voice_call_allowed)) -> dict:
    calls = body.get("calls")
    if not isinstance(calls, list) or not all(isinstance(c, dict) for c in calls) or len(calls) > 8:
        raise HTTPException(status_code=422, detail="calls must be a list of at most 8 function calls")
    heard = body.get("heard") if isinstance(body.get("heard"), str) else None
    utterance = body.get("utterance") if isinstance(body.get("utterance"), str) else None
    answer = voice.relay(str(body.get("voice_session_id") or ""), calls, LearnerScope.from_request_context(), heard,
                         utterance)
    if answer is None:
        raise HTTPException(status_code=404, detail="voice_session_not_found")
    return answer


@router.post("/voice/turn")
def agent_voice_turn(body: dict = Body(...), voice: VoiceService = Depends(_voice_call_allowed)) -> dict:
    """The end of one spoken utterance (the vendor's turn end), whatever tools it called: it is one turn of the
    conversation. `utterance` is the client's own sequence token for the session, never the words."""

    heard = body.get("heard") if isinstance(body.get("heard"), str) else None
    utterance = body.get("utterance") if isinstance(body.get("utterance"), str) else None
    answer = voice.utterance_turn(str(body.get("voice_session_id") or ""), utterance, heard, LearnerScope.from_request_context())
    if answer is None:
        raise HTTPException(status_code=404, detail="voice_session_not_found")
    return answer


@router.post("/voice/context")
def agent_voice_context(body: dict = Body(...), voice: VoiceService = Depends(_voice_call_allowed)) -> dict:
    """The learner moved while the session stays open (R30): its context follows; the answer's `note` goes to the
    model as a context line."""

    context = body.get("context")
    if not isinstance(context, dict):
        raise HTTPException(status_code=422, detail="context must be an object")
    try:
        answer = voice.update_context(str(body.get("voice_session_id") or ""), context, LearnerScope.from_request_context())
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_url=False, include_context=False)) from exc
    if answer is None:
        raise HTTPException(status_code=404, detail="voice_session_not_found")
    return answer


@router.post("/voice/end")
def agent_voice_end(body: dict = Body(...), voice: VoiceService = Depends(_voice_call_allowed)) -> dict:
    answer = voice.end(str(body.get("voice_session_id") or ""), LearnerScope.from_request_context(),
                       body.get("transcript"))  # optional: the turns the client heard and showed
    if answer is None:
        raise HTTPException(status_code=404, detail="voice_session_not_found")
    return answer


@router.get("/capabilities")
def agent_capabilities(
    interface: str = Query(default="en", max_length=16), runtime: AgentRuntime = Depends(_read_allowed)
) -> dict:
    if interface not in interface_languages():
        raise HTTPException(status_code=422, detail="unknown interface language")
    target = LearnerScope.from_request_context().contract_language
    return runtime.capabilities.public(interface=interface, target=target)
