"""One agent turn: request in, contract events out (spec §20, contract §4).

    session → context → model rounds (read tools, reply tools) → text →
    references → actions → suggestions → done

A round streams text, which goes straight out as `segment_delta`, and may ask
for tools. A read tool runs through the registry for the authenticated
learner, inside that learner's request context, and its evidence is sent
before any claim that cites it. A reply tool shapes the answer and runs
nothing. At most `max_tool_iterations_per_turn` rounds may call tools; the
round after that is offered no tools and must answer.

An opening turn (contract §3.2, `trigger: "open"`) has no learner message:
one short greeting, sent whole rather than streamed so it can be held to
240 characters, then at least one suggestion and at most two LOW actions.
It is not a learner turn: it is counted as `agent.open`, not `agent.turn`.

A learner who asks who Orena is, or which model answers (spec §35), is
answered from copy, the same every time, before any model is asked: one
segment in the support language, then `done`. The `DecisionProvider` decides
whether a message is that question.

A provider that fails ends the turn with an `error` event (`retry`); nothing
switches provider. A client that goes away stops the turn where it is. A turn
that completes is metered - counted, never refused (R5) - and its session is
kept for the next turn.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any

from writing_coach.agent import learner_copy
from writing_coach.agent.capability_registry import CapabilityRegistry
from writing_coach.agent.context import TurnInput, build_tier1
from writing_coach.agent.decision import (
    DecisionProvider,
    DecisionQuestion,
    Decisions,
    DecisionState,
    RuleDecisionProvider,
)
from writing_coach.agent.errors import AgentError, ProviderUnavailable
from writing_coach.agent.address import address_for
from writing_coach.agent.honesty import ClaimGate, offer_for, offer_instead
from writing_coach.agent.identity import IdentityQuestion
from writing_coach.agent.events import (
    DoneEvent,
    EvidenceEvent,
    Event,
    SegmentDelta,
    SegmentEnd,
    SessionEvent,
    ToolCallEvent,
    ToolResultEvent,
    TurnStream,
    Usage,
    error_event,
)
from writing_coach.agent.limits import DEFAULT_LIMITS, AgentLimits
from writing_coach.agent.contract import OPENING_MAX_CHARS
from writing_coach.agent.events import Display
from writing_coach.agent.outputs import (
    KIND_BY_SOURCE,
    REPLY_TOOL_NAMES,
    ReplyOutputs,
    opening_suggestions,
    reply_tool_specs,
)
from writing_coach.agent.prompts import opening_messages
from writing_coach.agent.provider import (
    AgentTurnProvider,
    ProviderMessage,
    ProviderToolSpec,
    ProviderTurnRequest,
    TextDelta,
    ToolCallRequest,
    TurnFinished,
    never_stop,
)
from writing_coach.agent.ratelimit import SlidingWindowLimiter
from writing_coach.agent.redaction import redact_for_provider
from writing_coach.agent.schemas import TurnRequest
from writing_coach.agent.session import SessionCache, ToolResultRecord
from writing_coach.agent.tools import (
    FORBIDDEN_ARGUMENTS,
    LearnerScope,
    ToolArgumentsInvalid,
    ToolRegistry,
    ToolResult,
)
from writing_coach.core.request_context import LANGUAGE_CODE_CTX, USER_KEY_CTX

_log = logging.getLogger(__name__)

Meter = Callable[[str, str, int, str], None]  # (user_key, feature, amount, request_id)
TURN_FEATURE = "agent.turn"
OPEN_FEATURE = "agent.open"
ANSWER_NUDGE = "[No answer was written. Answer the learner now, in words, in their support language.]"
TOKENS_FEATURE = "agent.tokens"


@contextmanager
def learner_context(learner: LearnerScope) -> Iterator[None]:
    """Run services as the authenticated learner, whatever thread this is."""

    user_token = USER_KEY_CTX.set(learner.user_key)
    language_token = LANGUAGE_CODE_CTX.set(learner.language)
    try:
        yield
    finally:
        LANGUAGE_CODE_CTX.reset(language_token)
        USER_KEY_CTX.reset(user_token)


# A selected item's id names what its type is; a word has no id (§3) and a feedback item is no payload field.
SELECTED_ID_KEYS = MappingProxyType({"grammar_point": "grammar_id", "sentence": "item_id"})


def _fit_greeting(text: str) -> str:
    """An opening greeting within 240 characters, cut at a sentence end when one fits."""

    text = text.strip()
    if len(text) <= OPENING_MAX_CHARS:
        return text
    head = text[:OPENING_MAX_CHARS]
    ends = [head.rfind(mark) for mark in (". ", "! ", "? ", "。", "！", "？")]
    cut = max(ends)
    if cut >= OPENING_MAX_CHARS // 3:
        return head[: cut + 1].strip()
    return head[: OPENING_MAX_CHARS - 1].rstrip() + "…"


def _estimate_tokens(messages: list[ProviderMessage]) -> int:
    return sum((len(m.content) + 3) // 4 for m in messages)


@dataclass
class AgentRuntime:
    provider: AgentTurnProvider
    tools: ToolRegistry
    capabilities: CapabilityRegistry
    sessions: SessionCache
    decider: DecisionProvider = field(default_factory=RuleDecisionProvider)
    limits: AgentLimits = DEFAULT_LIMITS
    meter: Meter | None = None
    clock: Callable[[], float] = time.monotonic
    new_trace_id: Callable[[], str] = lambda: uuid.uuid4().hex
    max_output_tokens: int = 1024
    turn_limiter: SlidingWindowLimiter = field(init=False)
    read_limiter: SlidingWindowLimiter = field(init=False)

    def __post_init__(self) -> None:
        limits = self.limits
        self.turn_limiter = SlidingWindowLimiter(
            limits.turns_per_window, limits.rate_window_seconds, max_keys=limits.rate_limited_learners, clock=self.clock
        )
        self.read_limiter = SlidingWindowLimiter(
            limits.capability_reads_per_window,
            limits.rate_window_seconds,
            max_keys=limits.rate_limited_learners,
            clock=self.clock,
        )

    def run(
        self, request: TurnRequest, learner: LearnerScope, *, should_stop: Callable[[], bool] = never_stop
    ) -> Iterator[Event]:
        return _Turn(self, request, learner, should_stop).events()


class _Turn:
    def __init__(
        self, runtime: AgentRuntime, request: TurnRequest, learner: LearnerScope, should_stop: Callable[[], bool]
    ) -> None:
        self.rt = runtime
        self.request = request
        self.learner = learner
        self.should_stop = should_stop
        self.locale = request.context.locale
        self.stream = TurnStream(version=request.version, client=request.client)
        self.trace_id = runtime.new_trace_id()
        self.usage_in = 0
        self.usage_out = 0
        self.usage_known = True
        self.evidence_ids: list[str] = []
        self.records: list[ToolResultRecord] = []
        self.text: list[str] = []
        # What is streamed; an action is never reported as done (agent/honesty.py).
        self.gate = ClaimGate(interface=request.context.locale.interface, support=request.context.locale.support)
        self.provider_rounds = 0
        self.address_offered_now = False
        self.deadline = runtime.clock() + runtime.limits.turn_timeout_seconds

    # --- the turn ------------------------------------------------------------

    def events(self) -> Iterator[Event]:
        session, _ = self.rt.sessions.open(self.request.session_id, self.learner.user_key)
        yield self.stream.emit(SessionEvent(session_id=session.agent_session_id, contract_version=self.stream.version))
        try:
            turn = TurnInput.from_request(self.request)
            tier1 = build_tier1(turn, session)
            questions = {DecisionQuestion.CAPABILITY}
            if not self.opening:  # an opening turn has no message to ask about
                questions.add(DecisionQuestion.IDENTITY_QUESTION)
            decisions = self.rt.decider.decide(
                DecisionState(turn=turn, tier1=tier1, registry=self.rt.capabilities), frozenset(questions)
            )
            if decisions.identity is not None:
                yield from self._identity(decisions.identity)
            else:
                yield from self._model_turn(turn, tier1, decisions, session)
            if self.should_stop():
                return
        except AgentError as exc:
            if not self.should_stop():
                yield self._error(exc.error_class)
            return
        except Exception:  # an unexpected failure still ends the stream properly
            _log.exception("agent turn failed", extra={"trace_id": self.trace_id})
            if not self.should_stop():
                yield self._error("internal_error")
            return
        self._keep(session, turn)
        self._meter()

    @property
    def opening(self) -> bool:
        return self.request.opening and self.stream.version >= 2

    def _model_turn(self, turn: TurnInput, tier1, decisions: Decisions, session) -> Iterator[Event]:
        here = [self.rt.capabilities.get(i) for i in decisions.capability_ids]
        messages = opening_messages(turn, tier1, [c for c in here if c], session, opening=self.opening)
        outputs = ReplyOutputs(
            client=self.request.client,
            interface=self.locale.interface,
            support=self.locale.support,
            target=self.locale.target,
            version=self.stream.version,
            opening=self.opening,
            take_ref=self.request.context.take_ref,
            address_asked=session.address_asked,
            address_chosen=address_for(tier1.coach_notes, self.locale.support).chosen,
        )
        # What the request named may be named back, as what it named; everything else must be read first.
        context = self.request.context
        for key in ("content_id", "lesson_id", "essay_id", "attempt_id"):
            outputs.learn_ids(key, (getattr(context, key),))
        selected = context.selected_item
        if selected is not None and selected.type in SELECTED_ID_KEYS:
            outputs.learn_ids(SELECTED_ID_KEYS[selected.type], (selected.id,))
        yield from self._rounds(messages, outputs)
        if self.should_stop():
            return
        if not "".join(self.text).strip() and not outputs.actions:
            # Nothing to say (or only whitespace) and nothing offered is not an answer: the learner is told,
            # and it is not metered. An action with no words is answered by its offer (agent/honesty.py).
            raise ProviderUnavailable("the provider answered with nothing")
        yield from self._finish(outputs)

    def _identity(self, question: IdentityQuestion) -> Iterator[Event]:
        """Spec §35: who Orena is comes from copy, never from a model, and names no provider."""

        lang, answer = learner_copy.text(
            f"identity.{question.value}", interface=self.locale.interface, support=self.locale.support
        )
        yield self.stream.emit(SegmentEnd(index=0, lang=lang, text=answer, voice_style="neutral_explain"))
        yield self.stream.emit(DoneEvent(usage=Usage(input_tokens=0, output_tokens=0), trace_id=self.trace_id))

    def _rounds(self, messages: list[ProviderMessage], outputs: ReplyOutputs) -> Iterator[Event]:
        read_specs = tuple(
            ProviderToolSpec.from_tool(tool)
            for tool in self.rt.tools.tools()
            if self.learner.contract_language in tool.languages
        )
        reply_specs = reply_tool_specs(
            self.request.client, self.locale.target, version=self.stream.version, opening=self.opening
        )
        limit = self.rt.limits.max_tool_iterations_per_turn
        nudged = False
        for round_index in range(limit + 1):
            remaining = self.deadline - self.rt.clock()
            if remaining <= 0:
                raise ProviderUnavailable("turn timed out")
            offer = () if round_index == limit else read_specs + reply_specs
            request = ProviderTurnRequest(
                messages=tuple(messages),
                tools=offer,
                max_output_tokens=self.rt.max_output_tokens,
                timeout_seconds=remaining,
            )
            round_text: list[str] = []
            calls: list[ToolCallRequest] = []
            self.provider_rounds += 1
            for item in self.rt.provider.stream(request, should_stop=self.should_stop):
                if self.should_stop():
                    return
                if self.rt.clock() > self.deadline:
                    raise ProviderUnavailable("turn timed out")
                if isinstance(item, TextDelta) and item.text:
                    round_text.append(item.text)
                    self.text.append(item.text)
                    if not self.opening:  # an opening greeting is sent whole, once it fits
                        for chunk in self.gate.feed(item.text):
                            yield self.stream.emit(SegmentDelta(index=0, lang=self.locale.support, text_delta=chunk))
                elif isinstance(item, ToolCallRequest):
                    calls.append(item)
                elif isinstance(item, TurnFinished):
                    if item.input_tokens is None or item.output_tokens is None:
                        self.usage_known = False  # never a guessed zero (R5 counts what was reported)
                    self.usage_in += item.input_tokens or 0
                    self.usage_out += item.output_tokens or 0
            if self.should_stop():
                return
            if not calls:
                if self.text or outputs.actions or nudged or round_index >= limit:
                    return
                # A round that ended with no words and nothing offered (the live run: a refused action,
                # then silence). Once, the model is asked for its answer in words, not failed at once.
                nudged = True
                messages.append(ProviderMessage(role="user", content=ANSWER_NUDGE))
                continue
            messages.append(ProviderMessage(role="assistant", content="".join(round_text), tool_calls=tuple(calls)))
            read_any = False
            for call in calls:
                if call.name in REPLY_TOOL_NAMES:
                    answer = outputs.handle(call.name, call.arguments, known_evidence=frozenset(self.evidence_ids))
                else:
                    read_any = True
                    answer = yield from self._read(call, messages, outputs)
                messages.append(ProviderMessage(role="tool", content=answer, tool_call_id=call.id))
            if not read_any and round_text:
                return  # the answer is written and its extras are attached

    def _read(self, call: ToolCallRequest, messages: list[ProviderMessage], outputs: ReplyOutputs) -> Iterator[Event]:
        registered = call.name in self.rt.tools.names()
        tool = self.rt.tools.get(call.name) if registered else None
        if tool is None or self.learner.contract_language not in tool.languages:
            return "unavailable: no such tool here"
        args = call.arguments if isinstance(call.arguments, Mapping) else {}
        if FORBIDDEN_ARGUMENTS & {str(key).casefold() for key in args}:
            # Never a tool call for another learner's data: refused before it starts (contract S8).
            return "refused: tools read only the signed-in learner's own data"
        label = learner_copy.text(f"tool.{tool.name}", interface=self.locale.interface, support=self.locale.support)[1]
        yield self.stream.emit(ToolCallEvent(tool=tool.name, label=label))
        try:
            with learner_context(self.learner):
                result = self.rt.tools.invoke(tool.name, replace(self.learner, interface=self.locale.interface), args)
        except ToolArgumentsInvalid:
            yield self._unavailable(tool.name)
            return "refused: arguments do not fit this tool's schema"
        except Exception:
            _log.warning("agent tool %s failed", tool.name, exc_info=True, extra={"trace_id": self.trace_id})
            yield self._unavailable(tool.name)
            return "unavailable: the service did not answer"
        yield from self._report(tool.name, result)
        kind = next((KIND_BY_SOURCE.get(e.source) for e in result.evidence if e.source in KIND_BY_SOURCE), None)
        outputs.learn_from(result.data, kind=kind)
        outputs.learn_from([dict(e.ref) for e in result.evidence], kind=kind)
        return self._tool_message(result, messages)

    def _report(self, name: str, result: ToolResult) -> Iterator[Event]:
        first = len(self.evidence_ids)
        ids = [f"e{first + i + 1}" for i in range(len(result.evidence))]
        summary = learner_copy.text(
            f"result.{name}", interface=self.locale.interface, support=self.locale.support, n=result.count
        )[1]
        yield self.stream.emit(ToolResultEvent(tool=name, summary=summary, evidence_ids=ids))
        for evidence_id, evidence in zip(ids, result.evidence, strict=True):
            yield self.stream.emit(
                EvidenceEvent(
                    id=evidence_id,
                    source=evidence.source,
                    ref=dict(evidence.ref),
                    excerpt=dict(evidence.excerpt),
                    display=Display(kind=KIND_BY_SOURCE[evidence.source]) if evidence.source in KIND_BY_SOURCE else None,
                )
            )
        self.evidence_ids.extend(ids)
        self.records.append(ToolResultRecord(tool=name, summary=result.summary, evidence_ids=tuple(ids)))

    def _tool_message(self, result: ToolResult, messages: list[ProviderMessage]) -> str:
        first = len(self.evidence_ids) - len(result.evidence)
        body: dict[str, Any] = {
            "summary": result.summary,
            "data": redact_for_provider(dict(result.data)),
            "evidence": [
                {
                    "id": f"e{first + i + 1}",
                    "source": e.source,
                    "ref": redact_for_provider(dict(e.ref)),
                    "excerpt": redact_for_provider(dict(e.excerpt)),
                }
                for i, e in enumerate(result.evidence)
            ],
        }
        content = json.dumps(body, ensure_ascii=False, default=str)
        if _estimate_tokens(messages) + (len(content) + 3) // 4 > self.rt.limits.max_input_tokens_per_turn:
            return json.dumps({"summary": result.summary, "note": "details omitted: this turn's input budget is used"})
        return content

    def _unavailable(self, name: str) -> ToolResultEvent:
        summary = learner_copy.text("result.unavailable", interface=self.locale.interface, support=self.locale.support)[1]
        return self.stream.emit(ToolResultEvent(tool=name, summary=summary, evidence_ids=[]))

    def _finish(self, outputs: ReplyOutputs) -> Iterator[Event]:
        index = 0
        offer = None
        if outputs.actions:  # an action is offered, never reported as done (agent/honesty.py)
            first = outputs.actions[0]
            offer = offer_for(
                first.type, first.label, first.payload, interface=self.locale.interface, support=self.locale.support
            )
        if self.opening:
            text = "".join(self.text)
            text = offer_instead(text, offer, interface=self.locale.interface, support=self.locale.support)
            if not text.strip() and offer is not None:
                text = offer
            text = _fit_greeting(text)
            if not outputs.suggestions:
                for intent in opening_suggestions(self.request.context.known_surface):
                    outputs.suggest(intent)
        else:
            for chunk in self.gate.finish(offer):
                yield self.stream.emit(SegmentDelta(index=0, lang=self.locale.support, text_delta=chunk))
            text = self.gate.text
        if text:
            yield self.stream.emit(
                SegmentEnd(index=0, lang=self.locale.support, text=text, voice_style=outputs.voice_style),
                cites=outputs.citations,
            )
            index = 1
        for lang, reference in outputs.references:
            yield self.stream.emit(SegmentEnd(index=index, lang=lang, text=reference, voice_style="reference"))
            index += 1
        for action in outputs.actions:
            yield self.stream.emit(action)
        for suggestion in outputs.suggestions:
            yield self.stream.emit(suggestion)
        for update in outputs.memory_updates:  # the address pair the learner chose (agent/address.py)
            yield self.stream.emit(update)
        self.address_offered_now = outputs.address_offered_now
        usage = Usage(input_tokens=self.usage_in, output_tokens=self.usage_out)
        yield self.stream.emit(DoneEvent(usage=usage, trace_id=self.trace_id))

    def _error(self, error_class: str) -> Event:
        return self.stream.emit(error_event(error_class, interface=self.locale.interface, support=self.locale.support))

    # --- after a completed turn -------------------------------------------------

    def _keep(self, session, turn: TurnInput) -> None:
        limit = self.rt.limits.max_recent_tool_results

        def change(state):
            state = state.with_context(turn.context)
            if not self.opening:  # an opening turn is not a learner turn (§3.2)
                state = state.with_turn()
            if self.address_offered_now:
                state = state.with_address_asked()
            for record in self.records:
                state = state.with_tool_result(record, limit=limit)
            return state

        # None when it expired meanwhile: the next turn opens a new one.
        self.rt.sessions.update(session.agent_session_id, self.learner.user_key, change)

    def _meter(self) -> None:
        if self.rt.meter is None:
            return
        counted = [(OPEN_FEATURE if self.opening else TURN_FEATURE, 1)]
        if self.usage_known and self.provider_rounds:  # an identity answer asks no model
            counted.append((TOKENS_FEATURE, self.usage_in + self.usage_out))
        for feature, amount in counted:
            try:
                self.rt.meter(self.learner.user_key, feature, amount, f"{self.trace_id}:{feature}")
            except Exception:
                # Metering never costs a learner their answer (text_discussion.py pattern).
                _log.warning("agent metering failed", exc_info=True)
