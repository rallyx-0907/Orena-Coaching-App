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

import json
import math
import threading
from collections.abc import AsyncIterator, Iterator, Mapping
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from starlette.concurrency import iterate_in_threadpool, run_in_threadpool

from writing_coach.agent import band
from writing_coach.agent.contract import DAILY_AI_LIMIT_VERSION
from writing_coach.agent.events import Event, sse_frame
from writing_coach.agent.locale import interface_languages, to_internal
from writing_coach.agent.ratelimit import SlidingWindowLimiter
from writing_coach.agent.schemas import TurnRequest
from writing_coach.agent.tools import LearnerScope
from writing_coach.agent.turn import AgentRuntime, TurnRefused, learner_context
from writing_coach.agent.voice_session import VoiceService, voice_catalog
from writing_coach.ai.live_voice import VoiceUnavailable
from writing_coach.product import plan_features, quota

router = APIRouter(prefix="/api/agent", tags=["agent"])

_TRUE = frozenset({"1", "true", "yes", "on"})
_runtime: AgentRuntime | None = None
_memory = None  # Orena Memory (agent/memory_runtime.py MemoryRuntime), or None: this server has none
_NO_MORE = object()
MESSAGE_METER = "orena.message"


def agent_enabled(env: Mapping[str, str]) -> bool:
    """AGENT_ENABLED is the switch, in every environment (D-146): the environment is not a feature switch."""

    return str(env.get("AGENT_ENABLED", "")).strip().casefold() in _TRUE


def configure_agent(runtime: AgentRuntime | None) -> None:
    """Install the runtime (enabled) or nothing (disabled)."""

    global _runtime
    _runtime = runtime
    _install_memory()


def configure_memory(memory) -> None:
    """Install Orena Memory (agent/memory_runtime.py) or none. Read by the turn, the voice session and the
    `/api/agent/memory` routes; the learner pack reads it through `PackBuilder.memory`."""

    global _memory
    _memory = memory
    _install_memory()


def _install_memory() -> None:
    if _runtime is None:
        return
    _runtime.memory = _memory
    pack = getattr(_runtime, "pack", None)
    if pack is not None:
        pack.memory = _memory.pack_reader() if _memory is not None else None


def current_memory():
    return _memory


def current_runtime() -> AgentRuntime | None:
    """The installed agent runtime, or None while the agent is off (read by the Admin's AI spend view)."""

    return _runtime


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


async def _declared_version(request: Request) -> int:
    """The contract version the request body declares, read before the body is validated; 0 when there is none."""

    try:
        declared = json.loads(await request.body() or b"{}").get("contract_version")
        if isinstance(declared, bool):
            return 0
        if isinstance(declared, float):
            return int(declared) if declared.is_integer() else 0  # 10.0 validates as 10 (pydantic lax mode)
        return int(declared) if isinstance(declared, int | str) else 0
    except Exception:  # noqa: BLE001 - a body that does not parse is answered by validation, after this check
        return 0


FAULT_RETRY_SECONDS = 60  # a spend limit that cannot be checked: refused (fail closed), then tried again soon


async def _spend_refused(request: Request, runtime: AgentRuntime) -> None:
    """The daily spend limits (agent/budget.py; the system ceiling, ai/spend_gate.py) before anything runs: a request
    they refuse is not counted in the learner's window. v10: `daily_ai_limit`, told once (§2.1); below: `rate_limited`."""

    guard = runtime.spend_guard
    if guard is None:
        return
    check = getattr(guard, "check", None)
    # The guard reads the ledger and the settings store (database reads): never on the event loop (review of #304).
    if callable(check):
        refused = await run_in_threadpool(check)
    else:
        wait = await run_in_threadpool(guard)
        refused = (wait, "agent", False) if wait is not None else None
    if refused is None:
        return
    wait, scope, fault = refused
    if fault:  # a cap or ledger that cannot be read is not "AI off until midnight": wait briefly, then send again
        raise HTTPException(status_code=429, detail="rate_limited", headers={"Retry-After": str(FAULT_RETRY_SECONDS)})
    retry = max(1, math.ceil(wait))
    headers = {"Retry-After": str(retry)}
    if await _declared_version(request) >= DAILY_AI_LIMIT_VERSION:
        resets = (datetime.now(UTC) + timedelta(seconds=retry)).replace(microsecond=0)
        raise HTTPException(status_code=429, headers=headers, detail={
            "category": "daily_ai_limit", "retryable": False,
            "message": "Orena's AI is paused until the daily AI budget resets.",
            "context": {"scope": scope, "resets_at": resets.isoformat()}})  # fmt: skip
    raise HTTPException(status_code=429, detail="rate_limited", headers=headers)


async def _turn_allowed(request: Request, runtime: AgentRuntime = Depends(_require_runtime)) -> AgentRuntime:
    await _spend_refused(request, runtime)
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


def _voice(runtime: AgentRuntime, *, new_sessions: bool = False) -> VoiceService:
    # Absent: the routes are not there. Switched off (`is_enabled`): only what OPENS a session (and the voice list) is
    # refused; a session already open can still be used and ended, so its time is billed to the ledger (D-172).
    if runtime.voice is None or (new_sessions and not runtime.voice.is_enabled()):
        raise HTTPException(status_code=404, detail="Not Found")
    return runtime.voice


def _voice_present(runtime: AgentRuntime = Depends(_require_runtime)) -> AgentRuntime:
    if runtime.voice is None:  # absent: the routes are not there, before any cap or window (review of #304)
        raise HTTPException(status_code=404, detail="Not Found")
    return runtime


async def _voice_entitled() -> None:
    """Voice chat with Orena is for Plus and Pro (owner, 2026-10-19; product/plan_features.py): 403
    `feature_not_in_plan` (context.feature "orena.voice") before any limit or token. The plan is a database read."""

    user_key = LearnerScope.from_request_context().user_key
    # The plan has voice, and today's voice minutes are not used up (429 quota_exhausted, feature orena.voice).
    await run_in_threadpool(plan_features.require_voice_time, user_key)


async def _voice_session_allowed(request: Request, runtime: AgentRuntime = Depends(_voice_present)) -> VoiceService:
    await _voice_entitled()
    await _turn_allowed(request, runtime)  # the daily spend cap and the learner's turn window count a session as a turn
    return _voice(runtime, new_sessions=True)


def _voice_list_allowed(runtime: AgentRuntime = Depends(_read_allowed)) -> VoiceService:
    return _voice(runtime, new_sessions=True)


def _voice_call_allowed(runtime: AgentRuntime = Depends(_read_allowed)) -> VoiceService:
    return _voice(runtime)


async def _voice_extend_allowed(request: Request,
                                runtime: AgentRuntime = Depends(_voice_present)) -> VoiceService:  # fmt: skip
    # A renewal mints a paid token, so the daily spend cap applies to it as to an opening; but it carries on a
    # conversation the learner already opened, so it is not counted as one more turn of their window. A plan that lost
    # voice (a downgrade) mints no next chunk: the client ends the session when the token it holds dies.
    await _voice_entitled()
    await _spend_refused(request, runtime)
    _admit(runtime.read_limiter)
    return _voice(runtime)


# --- the weekly recurring-mistake report (Monetisation v2): counts from the learner's own records -------------------

SPEAKING_ATTEMPTS_READ = 200
WEEKLY_REPORT = "progress.weekly_report"  # the plan entitlement (catalog.METERS)


def _source(read, *args):
    try:
        return list(read(*args))
    except Exception:  # noqa: BLE001 - not readable here: unknown, never "no mistakes"
        return None


@router.get("/progress/weekly")
def agent_progress_weekly(request: Request, response: Response, tz: str | None = Query(default=None, max_length=64),
                          interface: str = Query(default="en", max_length=16),
                          runtime: AgentRuntime = Depends(_read_allowed)) -> dict:  # fmt: skip
    """This ISO week's recurring mistakes against the four weeks before (agent/weekly_report.py), in the learner's time
    zone (`tz`, else `X-Orena-Timezone`, else UTC). Read from the rows Orena Memory reads; no model call, no cost."""

    from datetime import UTC, datetime

    from writing_coach.agent import weekly_report

    if interface not in interface_languages():
        raise HTTPException(status_code=422, detail="unknown interface language")
    # Plus and Pro (MV2-6a, D-248): 403 feature_not_in_plan for Free before anything is read; 503 when the plan cannot
    # be read (fail closed).
    plan_features.require(LearnerScope.from_request_context().user_key, WEEKLY_REPORT)
    sources = getattr(runtime.pack, "sources", None)
    zone = tz or request.headers.get("X-Orena-Timezone") or "UTC"
    if not tz and not weekly_report.known_zone(zone):
        zone = "UTC"  # a device's bad header falls back; only an explicit `tz` is refused
    try:
        answer = weekly_report.weekly_report(
            writing=_source(sources.writing_events) if sources is not None else None,
            speaking=_source(sources.speaking_attempts, SPEAKING_ATTEMPTS_READ) if sources is not None else None,
            now=datetime.now(UTC), tz=zone, interface=interface)  # fmt: skip
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="unknown_time_zone") from exc
    response.headers["Cache-Control"] = "private, no-store"
    return answer


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
    interface: str = Query(default="en", max_length=16), voice: VoiceService = Depends(_voice_list_allowed)
) -> dict:
    """Orena's voices to choose from (R29), labelled in the interface language; the choice goes in the session body."""

    if interface not in interface_languages():
        raise HTTPException(status_code=422, detail="unknown interface language")
    # `entitled`: whether this account's plan has voice chat, so the client offers the upgrade before the tap; the 403
    # on /voice/session stays the authority.
    user_key = LearnerScope.from_request_context().user_key
    return {**voice_catalog(interface), "entitled": plan_features.entitled(user_key, plan_features.VOICE)}


@router.get("/voice/allowance")
def agent_voice_allowance(response: Response, voice: VoiceService = Depends(_voice_call_allowed)) -> dict:
    """Today's voice minutes with Orena for the energy bar (Monetisation v2): `limit`, `used`, `left` in seconds,
    `resets_at` (next UTC midnight), `entitled`. A read: nothing is minted or charged; /voice/session stays the
    authority (403 / 429). Absent where voice is not configured."""

    response.headers["Cache-Control"] = "no-store"
    return plan_features.voice_allowance(LearnerScope.from_request_context().user_key)


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


# `/api/agent/memory` (contract v9 §10) is on this router too.
# --- the band estimator (Monetisation v2): administrators only until calibrated --------------------------------------


def _band_admin(request: Request) -> dict:
    from auth_support import require_admin

    return require_admin(request)


@router.post("/band/writing")
def agent_band_writing(body: band.BandRequest, request: Request, response: Response,
                       runtime: AgentRuntime = Depends(_read_allowed)) -> dict:  # fmt: skip
    """An estimated IELTS Writing band or HSK level for a piece of writing (agent/band.py). Experimental and for
    administrators until the pilot calibration agrees with real scores; `BAND_ESTIMATOR=off` removes it."""

    if band.mode() == "off":
        raise HTTPException(status_code=404, detail="Not Found")
    _band_admin(request)
    learner = LearnerScope.from_request_context()
    if band.exam_for_language(learner.language) != body.exam:  # None: no exam for this language
        raise HTTPException(status_code=409, detail="exam_language_mismatch")
    response.headers["Cache-Control"] = "no-store"
    from writing_coach.ai import spend_gate
    from writing_coach.ai.base import AICapabilityError, AIProviderError

    try:
        return band.estimate(body)
    except band.BandUnavailable as exc:
        raise HTTPException(status_code=502, detail="band_unavailable") from exc
    except spend_gate.SpendCeilingReached:
        raise  # the app's handler answers it, with the paused header
    except (AICapabilityError, AIProviderError) as exc:
        raise HTTPException(status_code=503, detail="ai_unavailable") from exc


from writing_coach.agent import memory_api  # noqa: E402, F401
