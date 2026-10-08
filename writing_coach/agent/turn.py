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

from pydantic import ValidationError

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
from writing_coach.agent.address import ADDRESS_VERSION, Address, address_note, default_address, mirrored_address
from writing_coach.agent.greeting import built as built_greeting
from writing_coach.agent.greeting import states_a_fact
from writing_coach.agent.focus import focus_after, lookup_word
from writing_coach.agent.summary import summarize
from writing_coach.agent.honesty import ClaimGate, asks_for_heading, nothing_done, offer, offer_instead
from writing_coach.agent.notes import (
    CORRECT,
    asks_to_remember_unaccented,
    confirmed_note,
    note_intent,
    notes_the_message_changes,
    unaccented_wish,
)
from writing_coach.agent.notes import nudge as note_nudge
from writing_coach.agent.identity import IdentityQuestion
from writing_coach.agent.events import (
    ActionEvent,
    DoneEvent,
    EvidenceEvent,
    MemoryUpdateEvent,
    Event,
    SegmentDelta,
    SegmentEnd,
    SessionEvent,
    SuggestionEvent,
    ToolCallEvent,
    ToolResultEvent,
    TurnStream,
    Usage,
    error_event,
    make_action,
)
from writing_coach.agent.limits import DEFAULT_LIMITS, AgentLimits
from writing_coach.agent.contract import OPENING_MAX_CHARS, WORD_ACTIONS
from writing_coach.agent.events import Display
from writing_coach.agent.outputs import (
    KEEP_NOTE_INTENT,
    KIND_BY_SOURCE,
    SELECTION_PROMPTS,
    asks_about_status,
    asks_to_go,
    opens_the_offer,
    REPLY_TOOL_NAMES,
    ReplyOutputs,
    opening_suggestions,
    reply_tool_specs,
    selection_kind,
)
from writing_coach.agent.prompts import opening_messages
from writing_coach.agent.pending import CANCELLED, COMPLETED, CONFIRM, PendingInteraction, action_key
from writing_coach.agent.provider import (
    NORMAL_FINISH,
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
from writing_coach.agent.locale import to_internal
from writing_coach.agent.schemas import CoachNote, TurnRequest
from writing_coach.agent.session import SessionCache, ToolResultRecord
from writing_coach.agent.timeline import TurnTimeline
from writing_coach.agent.tools import (
    FORBIDDEN_ARGUMENTS,
    LearnerScope,
    ToolArgumentsInvalid,
    ToolRegistry,
    ToolResult,
)
from writing_coach.core.request_context import LANGUAGE_CODE_CTX, USER_KEY_CTX

EVIDENCE_NUDGE = (
    "This asks for a conclusion about the learner's own learning. You have read none of their records: call "
    "get_recommended_next_activities (what to study) or get_learning_weaknesses (what goes wrong, weak areas) "
    "now, then answer only from what it shows. Where it shows too little, say there is not enough data yet; never "
    "rank skills against each other from counts of different kinds."
)
SCREEN_HELP_REPLY_TOOLS = frozenset({"suggest_next"})  # S1: an answer and follow-ups; no preference change
_log = logging.getLogger(__name__)

Meter = Callable[[str, str, int, str], None]  # (user_key, feature, amount, request_id)
TURN_FEATURE = "agent.turn"
OPEN_FEATURE = "agent.open"
SNAPSHOT_TOOL = "build_learning_snapshot"
FEEDBACK_NUDGE = (
    "The learner asks why this feedback was given on their essay (essay_id {essay_id}). You have not read it: call "
    "get_writing_feedback_items with that essay_id (and get_current_writing_evaluation if you need the whole "
    "review) now, then say from what it shows why this very feedback was given: the reason in one or two short "
    "sentences, and at most one example. Nothing about review or words due, and no offer of more."
)
# A status or navigation question about the word in view ("Mở từ này trong My Library", "Từ này lưu chưa?"):
# answered with that status only (LEX-006 retest, tutor accuracy) - no explanation of the word nobody asked for.
STATUS_ONLY = (
    "The learner asks about this word's place in their library (whether it is saved, or to open it there), not "
    "about its meaning. Read its state if you have not, answer that in one or two sentences, and offer the one "
    "button that fits. Explain nothing about the word itself."
)
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
    # One record per turn (agent/timeline.py): where the time went, for the latency and cost baseline.
    record_turn: Callable[[str, dict], None] | None = None
    # One record per rolling-summary call (agent/summary.py), and its price: (input, output tokens) ->
    # {provider, model, cost}. Both optional; a summary behaves the same without them.
    record_summary: Callable[[str, dict], None] | None = None
    price_summary: Callable[[int, int], dict] | None = None
    # The staging daily spend cap (agent/budget.py): seconds until it resets when reached, else None.
    spend_guard: Callable[[], float | None] | None = None
    # Live voice, mode A (agent/voice_session.py, R28): None unless the server turns voice on.
    voice: Any = None
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
        return _Turn(self, request, learner, should_stop).timed_events()


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
        self.screen_help = False  # set per turn by the decision (F-13)
        self.needs_evidence = False  # a conclusion about the learner's learning: read before answering (3.1)
        self.evidence_nudge = EVIDENCE_NUDGE  # what the model is asked when it answered without reading
        self.focused = False  # the turn is about what is in view (LEX-006, LEX-022)
        self.heard: str | None = None  # what the model was given as the learner's words, kept as the turn's history
        self.said = ""  # what the learner was shown as the answer, kept the same way
        self.live: PendingInteraction | None = None  # the offer open when this turn began (agent/pending.py)
        self.lookups: list[tuple[str, str | None]] = []  # words a tool read this turn (agent/focus.py)
        self.outputs_actions: tuple[ActionEvent, ...] = ()  # the actions of this answer, for the focus
        self.ran: tuple[str, ...] = ()  # keys of the actions this turn ran at the learner's word
        self.settle: str | None = None  # how this turn ended it: completed | cancelled
        self.new_offer: tuple[str, str, dict] | None = None  # (type, label, payload) this answer offers, if any
        self.read_attempted = False  # a read was started this turn, whatever came of it
        self.address_offered_now = False
        self.notes_asked: tuple[CoachNote, ...] = ()  # coach notes the message changes (agent/notes.py)
        self.notes_verdict_logged = False  # one "agent notes" verdict line per turn, never two
        self.notes_intent: str | None = None  # correct | forget, by rule (agent/notes.py)
        self.note_confirmed: str | None = None  # the learner tapped to keep these words (agent/notes.py)
        self.unaccented_keep = False  # a keep request typed without diacritics: asked back, not kept
        self.coach_notes: tuple[CoachNote, ...] = ()
        self.snapshot: dict | None = None
        # The learner's address for this turn (§5.6): used, never logged or stored (contract §10).
        self.address: Address = default_address(request.context.locale.support)
        self.deadline = runtime.clock() + runtime.limits.turn_timeout_seconds
        self.timeline = TurnTimeline(runtime.clock)

    # --- the turn ------------------------------------------------------------

    def timed_events(self) -> Iterator[Event]:
        """The turn's events, with its timeline recorded once at the end, however it ends."""

        outcome = "abandoned"  # the client left before the turn ended
        try:
            for event in self.events():
                if event.name in ("segment_delta", "segment_end"):
                    self.timeline.mark_once("first_visible")
                elif event.name == "error":
                    outcome = f"error:{getattr(event, 'error_class', 'unknown')}"
                elif event.name == "done" and not outcome.startswith("error"):
                    outcome = "success"
                yield event
        finally:
            self._record_turn(outcome)

    def _record_turn(self, outcome: str) -> None:
        if self.rt.record_turn is None:
            return
        context = self.request.context
        self.timeline.facts.update(
            surface=context.surface, activity_type=context.activity_type, opening=self.opening,
            screen_help=self.screen_help, target=self.locale.target, interface=self.locale.interface,
            support=self.locale.support, selected_type=context.selected_item.type if context.selected_item else None,
            provider_rounds=self.provider_rounds, input_tokens=self.usage_in if self.usage_known else None,
            output_tokens=self.usage_out if self.usage_known else None, evidence_count=len(self.evidence_ids),
        )
        try:
            self.rt.record_turn(self.learner.user_key, self.timeline.record(trace_id=self.trace_id, outcome=outcome))
        except Exception:  # telemetry never costs the learner the answer
            _log.warning("agent turn timeline not recorded", exc_info=True, extra={"trace_id": self.trace_id})

    def events(self) -> Iterator[Event]:
        session, _ = self.rt.sessions.open(self.request.session_id, self.learner.user_key)
        yield self.stream.emit(SessionEvent(session_id=session.agent_session_id, contract_version=self.stream.version))
        try:
            turn = TurnInput.from_request(self.request)
            # A changed target language starts from a clean context: nothing kept in the other one is read (3.3).
            session = session.for_target(self.locale.target)
            self.live = None if self.opening else session.live_pending()
            tier1 = build_tier1(turn, session)
            self.address = tier1.address
            self.gate.address = tier1.address
            questions = {DecisionQuestion.CAPABILITY}
            if not self.opening:  # an opening turn has no message to ask about
                questions.add(DecisionQuestion.IDENTITY_QUESTION)
                questions.add(DecisionQuestion.SCREEN_HELP)
                questions.add(DecisionQuestion.NEEDS_TOOLS)
            decisions = self.rt.decider.decide(
                DecisionState(turn=turn, tier1=tier1, registry=self.rt.capabilities), frozenset(questions)
            )
            if self.opening and self.request.context.selected_item is not None:
                yield from self._selection_opening()
            elif (offered := self._offered_again(turn, session)) is not None:
                yield from self._open_offered(offered)
            elif decisions.identity is not None:
                yield from self._identity(decisions.identity)
            else:
                yield from self._model_turn(turn, tier1, decisions, session)
            if self.should_stop():
                return
        except AgentError as exc:
            self._notes_unresolved()
            if not self.should_stop():
                yield self._error(exc.error_class)
            return
        except Exception:  # an unexpected failure still ends the stream properly
            _log.exception("agent turn failed", extra={"trace_id": self.trace_id})
            self._notes_unresolved()
            if not self.should_stop():
                yield self._error("internal_error")
            return
        self._keep(session, turn)
        self._compact(session)
        self._meter()

    @property
    def opening(self) -> bool:
        return self.request.opening and self.stream.version >= 2

    def _mirror(self, turn: TurnInput, tier1) -> tuple[Any, dict | None]:
        """Vietnamese kinship address answered in kind at once: the pair kept and applied to this very turn."""

        # A v4 client is never sent an address note (§5.6): it keeps the defaults.
        if self.opening or self.stream.version < ADDRESS_VERSION or to_internal(self.locale.support) != "vi":
            return tier1, None
        pair = mirrored_address(turn.message)
        if pair is None or pair == tier1.address.pair:
            return tier1, None
        note = address_note(self.locale.support, *pair)
        chosen = Address(pair[0], pair[1], chosen=True, lang=self.locale.support)
        self.address = self.gate.address = chosen
        return replace(tier1, address=chosen), note

    def _model_turn(self, turn: TurnInput, tier1, decisions: Decisions, session) -> Iterator[Event]:
        tier1, mirrored = self._mirror(turn, tier1)
        here = [self.rt.capabilities.get(i) for i in decisions.capability_ids]
        snapshot = self._opening_snapshot() if self.opening else None
        self.snapshot, self.coach_notes = snapshot, tier1.coach_notes
        self.screen_help = decisions.screen_help
        self.needs_evidence = decisions.needs_tools is True
        context = self.request.context
        selected = context.selected_item
        # The turn is about what is in view: no review routing nobody asked for (LEX-006, LEX-022).
        self.focused = not self.opening and bool(selected or context.essay_id)
        self.gate.drop_more_offers = self.focused  # and no closing offer of more examples or a review
        # nor a selected word's saved/due status, unless the learner asks about it
        word_in_view = selected is not None and selected.type == "word"
        self.gate.drop_status = self.focused and word_in_view and not asks_about_status(turn.message)
        self.gate.status_word = selected.text if word_in_view else None
        self.gate.heading_asked = not self.opening and asks_for_heading(turn.message)
        if not self.opening and selected is not None and selected.type == "feedback_item" and context.essay_id:
            # "Why was this feedback given?" (LEX-022): answered from that essay's review, read first.
            self.needs_evidence = True
            self.evidence_nudge = FEEDBACK_NUDGE.format(essay_id=json.dumps(context.essay_id))
        if not self.opening:
            self.notes_asked = notes_the_message_changes(turn.message, tier1.coach_notes)
            self.notes_intent = note_intent(turn.message) if self.notes_asked else None
            self.note_confirmed = confirmed_note(turn.message)
            self.unaccented_keep = to_internal(self.locale.support) == "vi" and asks_to_remember_unaccented(turn.message)
            # It may be written again (a note to change or keep, records to read first) or replaced by the server's
            # question (a keep request without diacritics): nothing streams early.
            self.gate.hold_all = (bool(self.notes_asked) or self.needs_evidence or self.note_confirmed is not None
                                  or self.unaccented_keep)  # fmt: skip
        # A starter the learner tapped is in the interface language; the model is given it in the support language,
        # so it answers in that one (LEX-006). Anything the learner typed reaches it as typed.
        tapped = None if self.opening else learner_copy.prompt_in_support(
            turn.message, interface=self.locale.interface, support=self.locale.support)  # fmt: skip
        self.heard = tapped or turn.message
        messages = opening_messages(
            replace(turn, message=tapped) if tapped else turn, tier1, [c for c in here if c], session,
            opening=self.opening, snapshot=snapshot, screen_help=self.screen_help,
            budget_tokens=self.rt.limits.max_input_tokens_per_turn,
        )
        answering = self.live is not None or bool(session.recent_runs())  # an open offer, or one just sent
        if (self.focused and word_in_view and not answering
                and (asks_about_status(turn.message) or asks_to_go(turn.message))):  # fmt: skip
            # said next to the learner's words, like the selection line. Not while the learner is answering an offer
            # ("ok lưu" is not a question about the library): the conversation is read, not the status words.
            messages.insert(len(messages) - 1, ProviderMessage(role="system", content=STATUS_ONLY))
        self.timeline.mark("context_built")
        outputs = ReplyOutputs(
            client=self.request.client,
            interface=self.locale.interface,
            support=self.locale.support,
            target=self.locale.target,
            version=self.stream.version,
            opening=self.opening,
            take_ref=self.request.context.take_ref,
            address_asked=session.address_asked,
            address_chosen=tier1.address.chosen,
            notes={note.id: note.weight for note in tier1.coach_notes},
            correcting=tuple(n.id for n in self.notes_asked) if self.notes_intent == CORRECT else (),
            asked=tuple(n.id for n in self.notes_asked),
            notes_intent=self.notes_intent,
            learner_words=turn.message or "",
            address_terms=tier1.address.pair,
            unaccented_keep=self.unaccented_keep,
            focused=self.focused,
            text_in_view=self.focused and context.selected_item is not None
            and context.selected_item.type in ("word", "sentence"),
            selected_word=context.selected_item.text
            if context.selected_item is not None and context.selected_item.type == "word" else None,
            pending=self.live,
            settled=frozenset(done for done, _ in session.settled),
            recent_runs=session.recent_runs(),
        )
        if mirrored is not None:
            outputs.memory_updates.append(MemoryUpdateEvent(op="upsert", note=mirrored))
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
        if (not "".join(self.text).strip() and not outputs.actions and not self.notes_asked
                and self.note_confirmed is None and not self.unaccented_keep):  # fmt: skip
            # Nothing to say (or only whitespace) and nothing offered is not an answer: the learner is told,
            # and it is not metered. An action with no words is answered by its offer (agent/honesty.py).
            raise ProviderUnavailable("the provider answered with nothing")
        yield from self._finish(outputs)

    def _opening_snapshot(self) -> dict | None:
        """S13 is built on the learner's snapshot: read here, by the server, not asked of the model."""

        if SNAPSHOT_TOOL not in self.rt.tools.names():
            return None
        learner = replace(self.learner, interface=self.locale.interface)
        try:
            with learner_context(learner):
                return dict(self.rt.tools.invoke(SNAPSHOT_TOOL, learner, {}).data)
        except Exception:
            _log.warning("opening snapshot unavailable", exc_info=True, extra={"trace_id": self.trace_id})
            return None

    def _identity(self, question: IdentityQuestion) -> Iterator[Event]:
        """Spec §35: who Orena is comes from copy, never from a model, and names no provider."""

        lang, answer = learner_copy.text(  # addressed as the learner chose (S15)
            f"identity.{question.value}", interface=self.locale.interface, support=self.locale.support,
            address=self.address,
        )
        self.said = answer
        yield self.stream.emit(SegmentEnd(index=0, lang=lang, text=answer, voice_style="neutral_explain"))
        yield self.stream.emit(DoneEvent(usage=Usage(input_tokens=0, output_tokens=0), trace_id=self.trace_id))

    def _selection_opening(self) -> Iterator[Event]:
        """Orena opened on a selection (UX review LEX-008): the learner came to ask about it, so the greeting asks
        what they want to know about this word or sentence, and the ways forward are questions about it - not the
        snapshot's review reminder or "what is this screen for". From copy: no model, no read (§3.2 read-only)."""

        selected = self.request.context.selected_item
        kind = selection_kind(selected.type, selected.text)  # a dragged part of a sentence is "this part"
        interface, support = self.locale.interface, self.locale.support
        greeting_key = "item" if kind == "part" else kind
        lang, greeting = learner_copy.text(f"opening.selection.{greeting_key}", interface=interface, support=support,
                                           address=self.address)  # fmt: skip
        self.timeline.mark("final_ready")
        self.timeline.facts.update(actions=[], suggestions=len(SELECTION_PROMPTS[kind]))
        yield self.stream.emit(SegmentEnd(index=0, lang=lang, text=greeting, voice_style="neutral_explain"))
        for intent in SELECTION_PROMPTS[kind]:
            label = learner_copy.text(intent, interface=interface, support=support)[1]
            yield self.stream.emit(SuggestionEvent(label=label, intent=intent))
        yield self.stream.emit(DoneEvent(usage=Usage(input_tokens=0, output_tokens=0), trace_id=self.trace_id))

    def _rounds(self, messages: list[ProviderMessage], outputs: ReplyOutputs) -> Iterator[Event]:
        # An opening turn reads nothing itself: the server gave it the snapshot (S13 has no tool_call).
        # A screen-help turn (F-13) is answered from the screen's context: the server offers it no read tool, so
        # no learner data is read to explain a screen, and no action or note: nothing that was not asked for.
        read_specs = () if self.opening or self.screen_help else tuple(
            ProviderToolSpec.from_tool(tool)
            for tool in self.rt.tools.tools()
            if self.learner.contract_language in tool.languages
        )
        reply_specs = reply_tool_specs(
            self.request.client, self.locale.target, version=self.stream.version, opening=self.opening,
            pending=self.live is not None,
        )
        if self.screen_help:
            # Canonical stream S1 (contract §12): an answer, follow-up questions, nothing else.
            reply_specs = tuple(spec for spec in reply_specs if spec.name in SCREEN_HELP_REPLY_TOOLS)
        limit = self.rt.limits.max_tool_iterations_per_turn
        nudged = notes_nudged = evidence_nudged = False
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
            self.timeline.round_started()
            for item in self.rt.provider.stream(request, should_stop=self.should_stop):
                self.timeline.round_event()
                if self.should_stop():
                    return
                if self.rt.clock() > self.deadline:
                    raise ProviderUnavailable("turn timed out")
                if isinstance(item, TextDelta) and item.text:
                    round_text.append(item.text)  # held until the round ends: evidence before any claim
                elif isinstance(item, ToolCallRequest):
                    calls.append(item)
                elif isinstance(item, TurnFinished):
                    if item.input_tokens is None or item.output_tokens is None:
                        self.usage_known = False  # never a guessed zero (R5 counts what was reported)
                    self.usage_in += item.input_tokens or 0
                    self.usage_out += item.output_tokens or 0
                    self.timeline.round_finished(input_tokens=item.input_tokens, output_tokens=item.output_tokens,
                                                 cached=item.cached_input_tokens, tool_calls=len(calls))
                    if item.finish_reason not in NORMAL_FINISH:
                        _log.warning("agent provider round ended abnormally: %s", item.finish_reason,
                                     extra={"trace_id": self.trace_id})  # fmt: skip
                        # Fail closed (independent review 2026-10-04): a round cut off or ended for a reason that is
                        # not a normal stop is never shown as a complete answer.
                        raise ProviderUnavailable(f"the provider round ended with {item.finish_reason!r}")
            if self.should_stop():
                return
            if any(call.name not in REPLY_TOOL_NAMES for call in calls):
                # Text written in the same round as a read was written before its evidence (independent review
                # 2026-10-04, P1): it never reaches the learner, and the model answers again once it has read.
                round_text = []
            elif round_text:
                self.text.extend(round_text)
                if not self.opening:  # an opening greeting is sent whole, once it fits
                    for chunk in self.gate.feed("".join(round_text)):
                        if self.should_stop():
                            return  # the learner left: nothing more is sent
                        yield self.stream.emit(SegmentDelta(index=0, lang=self.locale.support, text_delta=chunk))
            if not calls:
                if self.needs_evidence and not self.read_attempted and not evidence_nudged and round_index < limit:
                    evidence_nudged = True
                    self._ask_again(messages, round_text, self.evidence_nudge, why="answered without reading the records")
                    continue
                if self._note_unchanged(outputs) and not notes_nudged and round_index < limit:
                    notes_nudged = True
                    self._ask_again(messages, round_text, self._note_nudge())
                    continue
                if self.text or outputs.actions or nudged or round_index >= limit:
                    return
                # A round that ended with no words and nothing offered (the live run: a refused action,
                # then silence). Once, the model is asked for its answer in words, not failed at once.
                nudged = True
                messages.append(ProviderMessage(role="user", content=ANSWER_NUDGE))
                continue
            messages.append(ProviderMessage(role="assistant", content="".join(round_text), tool_calls=tuple(calls)))
            read_any = False
            offered = {spec.name for spec in offer}
            for call in calls:
                if call.name not in offered:
                    # A tool the server did not offer this round never runs, whatever the model asks for: an
                    # opening or screen-help turn reads nothing, and the last round may only answer (F-13).
                    _log.warning("agent model called a tool it was not offered: %s", call.name,
                                 extra={"trace_id": self.trace_id})  # fmt: skip
                    messages.append(ProviderMessage(role="tool", content="unavailable: not offered in this turn",
                                                    tool_call_id=call.id))  # fmt: skip
                    continue
                if call.name in REPLY_TOOL_NAMES:
                    answer = outputs.handle(call.name, call.arguments, known_evidence=frozenset(self.evidence_ids))
                else:
                    read_any = True
                    answer = yield from self._read(call, messages, outputs)
                messages.append(ProviderMessage(role="tool", content=answer, tool_call_id=call.id))
            if not read_any and round_text:
                if self._note_unchanged(outputs) and not notes_nudged and round_index < limit:
                    notes_nudged = True
                    self._ask_again(messages, "", self._note_nudge())
                    continue
                return  # the answer is written and its extras are attached

    def _notes_unresolved(self) -> None:
        """A turn about a note that failed before its answer: said, so the operator's per-turn reading of the
        "agent notes" lines never carries an "asked again" over to the next turn (counts only)."""

        if self.notes_asked and not self.notes_verdict_logged:
            self.notes_verdict_logged = True
            _log.warning("agent notes: failed before a verdict", extra={"trace_id": self.trace_id})

    def _note_unchanged(self, outputs: ReplyOutputs) -> bool:
        return (bool(self.notes_asked) or self.note_confirmed is not None) and not outputs.note_changed

    def _keep_question(self, outputs: ReplyOutputs) -> str | None:
        """A keep request typed without diacritics (human direction 2026-10-04): never refused in silence. Orena
        asks back with the note it would keep, and a button whose label, sent back as the learner's next message,
        confirms exactly those words (agent/notes.py `confirmed_note`); nothing is kept until the learner taps."""

        if not self.unaccented_keep or outputs.note_changed:
            return None
        # For the operator: counts only, never the learner's words.
        _log.warning("agent notes: a keep request without diacritics; asked to confirm", extra={"trace_id": self.trace_id})
        interface, support = self.locale.interface, self.locale.support
        wish = outputs.note_offer[1] if outputs.note_offer else unaccented_wish(self.request.message or "")
        if wish:
            label = learner_copy.text("notes.keep_label", interface=interface, support=support, text=wish)[1]
            try:
                button = SuggestionEvent(label=label, intent=KEEP_NOTE_INTENT)
            except ValidationError:
                button = None  # too long for a button: asked to type it again with its marks
            if button is not None:
                outputs.suggestions[:] = [button]
                return learner_copy.text("notes.confirm", interface=interface, support=support,
                                         address=self.address, text=wish)[1]  # fmt: skip
        outputs.suggestions.clear()
        return learner_copy.text("notes.retype", interface=interface, support=support, address=self.address)[1]

    def _note_nudge(self) -> str:
        if self.note_confirmed is not None and not self.notes_asked:
            return (f"The learner tapped to keep this note: {self.note_confirmed!r}. Call remember_note with exactly "
                    "these words as text now, then answer in one sentence.")  # fmt: skip
        return note_nudge(self.notes_asked, self.notes_intent or CORRECT)

    def _ask_again(self, messages: list[ProviderMessage], round_text: str | list[str], ask: str, *,
                   why: str | None = None) -> None:
        """Once: the answer is set aside (nothing of it was streamed) and the model is asked again."""

        # For the operator (which model follows a correction on its own): counts only, no learner words.
        if why is None:
            _log.warning("agent notes: the model changed no note of %d; asked again", len(self.notes_asked),
                         extra={"trace_id": self.trace_id})  # fmt: skip
        else:
            _log.warning("agent: %s; asked again", why, extra={"trace_id": self.trace_id})
        written = "".join(round_text)
        if written:
            messages.append(ProviderMessage(role="assistant", content=written))
        messages.append(ProviderMessage(role="user", content=ask))
        self.gate.discard()
        self.text.clear()

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
        self.timeline.tools.append(tool.name)
        self._note_lookup(tool.name, args)
        self.read_attempted = True
        self.timeline.mark("tool_start")
        yield self.stream.emit(ToolCallEvent(tool=tool.name, label=label))
        try:
            with learner_context(self.learner):
                result = self.rt.tools.invoke(tool.name, replace(self.learner, interface=self.locale.interface), args)
            self.timeline.mark("tool_end")
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

    def _note_lookup(self, name: str, args: Mapping[str, Any]) -> None:
        """A word a tool is asked about is what the talk is about now (agent/focus.py)."""

        if (word := lookup_word(name, args)) is not None:
            self.lookups.append((word, self.locale.target))

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

    def _address(self, language: str) -> Address:
        """The turn's address; copy in another language than the support one takes that language's default."""

        return self.address

    def _finish(self, outputs: ReplyOutputs) -> Iterator[Event]:
        self.timeline.mark("final_ready")
        question = None if self.opening else self._keep_question(outputs)
        if question is not None:
            outputs.actions.clear()  # the turn asks one thing: whether to keep the note
        self.timeline.facts.update(actions=[a.type for a in outputs.actions], suggestions=len(outputs.suggestions))
        index = 0
        support = self.locale.support
        offer_lang = offer_text = action_type = None
        if outputs.actions:  # the server's one offer of the button; the model's own are dropped (agent/honesty.py)
            first = outputs.actions[0]
            action_type = first.type
            offer_lang = learner_copy.language_of(f"offer.{first.type}" if f"offer.{first.type}" in
                                                  learner_copy.CATALOG else "offer.action",
                                                  interface=self.locale.interface, support=support)  # fmt: skip
            offer_text = offer(first.type, first.label, first.payload, interface=self.locale.interface,
                               support=support, address=self._address(offer_lang))[1]  # fmt: skip
            if not self.opening and first.type == "navigate" and asks_to_go(self.request.message):
                # §7: a place the learner's own message asked for opens at once, and the sentence says so instead of
                # asking for a tap. (Running other actions on request is voice's, R30.)
                outputs.actions[0] = first.model_copy(update={"open": True})
                offer_lang, offer_text = learner_copy.text("offer.now.navigate", interface=self.locale.interface,
                                                           support=support, address=self.address)  # fmt: skip
            elif first.open:  # asked for or accepted (agent/pending.py): it runs now, and is not "done"
                now_key = f"offer.now.{first.type}" if f"offer.now.{first.type}" in learner_copy.CATALOG else "offer.now.action"
                offer_lang, offer_text = learner_copy.text(now_key, interface=self.locale.interface, support=support,
                                                           address=self.address)  # fmt: skip
        self.outputs_actions = tuple(outputs.actions)
        self.ran = tuple(action_key(a.type, a.payload) for a in outputs.actions if a.open)
        if outputs.resolution is not None:
            self.settle = COMPLETED if outputs.resolution == CONFIRM else CANCELLED
        offered = next((a for a in outputs.actions if not a.open), None)  # what is only offered stays open for an answer
        same_offer = (offered is not None and self.live is not None
                      and action_key(offered.type, offered.payload) == action_key(self.live.action, self.live.payload))
        if offered is not None and not self.opening and not same_offer:  # the same button again changes nothing
            self.new_offer = (offered.type, offered.label, dict(offered.payload))
        inline = offer_text if offer_lang == support else None  # in the answer's own language, or apart
        apart = offer_text if inline is None else None
        nothing = nothing_done(self.locale.interface, support, self._address(support))
        if self.opening:
            greeting = offer_instead("".join(self.text), None, interface=self.locale.interface, support=support,
                                     pending=bool(outputs.actions), action=action_type, nothing=nothing,
                                     address=self.address)  # fmt: skip
            if not states_a_fact(greeting, self.snapshot):  # never a generic greeting (agent/greeting.py)
                greeting = built_greeting(self.snapshot, interface=self.locale.interface, support=support,
                                          address=self._address(support))  # fmt: skip
            text = _fit_greeting(greeting + (" " + inline if inline else ""))
            if not outputs.suggestions:
                for intent in opening_suggestions(self.request.context.known_surface):
                    outputs.suggest(intent)
        elif question is not None:
            # The server's question, not the model's words: nothing of the held answer was sent (hold_all).
            self.gate.discard()
            yield self.stream.emit(SegmentDelta(index=0, lang=support, text_delta=question))
            text = question
        else:
            unchanged = None
            if (self.notes_asked or self.note_confirmed is not None) and not self.notes_verdict_logged:
                self.notes_verdict_logged = True
                _log.warning("agent notes: %s", "unchanged after asking again" if self._note_unchanged(outputs)
                             else "changed", extra={"trace_id": self.trace_id})  # fmt: skip
            if self._note_unchanged(outputs):  # asked twice and no note changed: said plainly (agent/notes.py)
                key = "notes.not_kept" if self.note_confirmed is not None and not self.notes_asked else "notes.unchanged"
                unchanged = learner_copy.text(key, interface=self.locale.interface, support=support,
                                              address=self.address)[1]  # fmt: skip
            elif self.needs_evidence and not self.records:
                # Asked to read and still read nothing: no conclusion about the learner is made up (3.1).
                unchanged = learner_copy.text("evidence.unread", interface=self.locale.interface, support=support,
                                              address=self.address)[1]  # fmt: skip
            finished = self.gate.finish(
                inline,
                pending=bool(outputs.actions),
                remembered=bool(outputs.memory_updates),
                action=action_type,
                nothing=nothing,
                replace_with=unchanged,
            )
            for chunk in finished:
                yield self.stream.emit(SegmentDelta(index=0, lang=support, text_delta=chunk))
            text = self.gate.text
        self.said = text
        # The device applies a memory_update without a tap, so it comes before the words that say it is
        # applied (S14: memory_update -> segment_end); coach notes and the address (§5.4, §5.6).
        for update in outputs.memory_updates:
            yield self.stream.emit(update)
        if text:
            yield self.stream.emit(
                SegmentEnd(index=0, lang=support, text=text, voice_style=outputs.voice_style),
                cites=outputs.citations,
            )
            index = 1
        if apart:
            yield self.stream.emit(SegmentDelta(index=index, lang=offer_lang, text_delta=apart))
            yield self.stream.emit(SegmentEnd(index=index, lang=offer_lang, text=apart, voice_style="neutral_explain"))
            index += 1
        for lang, reference in outputs.references:
            yield self.stream.emit(SegmentEnd(index=index, lang=lang, text=reference, voice_style="reference"))
            index += 1
        for action in outputs.actions:
            yield self.stream.emit(action)
        for suggestion in outputs.suggestions:
            yield self.stream.emit(suggestion)
        self.address_offered_now = outputs.address_offered_now
        usage = Usage(input_tokens=self.usage_in, output_tokens=self.usage_out)
        yield self.stream.emit(DoneEvent(usage=usage, trace_id=self.trace_id))

    def _error(self, error_class: str) -> Event:
        return self.stream.emit(
            error_event(error_class, interface=self.locale.interface, support=self.locale.support, address=self.address)
        )

    # --- after a completed turn -------------------------------------------------

    def _offered_again(self, turn: TurnInput, session) -> ActionEvent | None:
        """"Open it" right after an offer: the place the last answer offered, as an action this client may run -
        else None (then the model answers as usual)."""

        offer_ = self.live
        if self.opening or offer_ is None or offer_.action != "navigate" or not opens_the_offer(turn.message):
            return None
        payload = dict(offer_.payload)
        if "navigate" not in self.stream.allowed_actions or payload.get("intent") not in self.stream.allowed_intents:
            return None
        try:
            action = make_action(offer_.id, "navigate", offer_.label, payload)
        except (ValueError, ValidationError):
            return None
        self.settle = COMPLETED
        return action.model_copy(update={"open": True})

    def _open_offered(self, action: ActionEvent) -> Iterator[Event]:
        """It opens at once (§7: the learner's message was the request), from copy, with no model call."""

        lang, said = learner_copy.text("offer.now.navigate", interface=self.locale.interface,
                                       support=self.locale.support, address=self.address)  # fmt: skip
        self.said = said
        self.timeline.mark("final_ready")
        self.timeline.facts.update(actions=[action.type], suggestions=0)
        yield self.stream.emit(SegmentDelta(index=0, lang=lang, text_delta=said))
        yield self.stream.emit(SegmentEnd(index=0, lang=lang, text=said, voice_style="brief_ack"))
        yield self.stream.emit(action)
        yield self.stream.emit(DoneEvent(usage=Usage(input_tokens=0, output_tokens=0), trace_id=self.trace_id))

    def _keep(self, session, turn: TurnInput) -> None:
        limit = self.rt.limits.max_recent_tool_results

        def change(state):
            state = state.for_target(self.locale.target).with_context(turn.context)
            if not self.opening:  # an opening turn is not a learner turn (§3.2)
                state = state.with_turn()
            if not self.opening and turn.message and self.said:  # the exchange, for the turns after it
                state = state.with_exchange(self.heard or turn.message, self.said, self.rt.limits)
            if not self.opening:
                state = state.with_focus(self._focus(state, turn))
            if self.address_offered_now:
                state = state.with_address_asked()
            if not self.opening:  # the offer this turn answered ends; one it expired on ends; a new one replaces
                state = state.with_outcome(live=self.live, settle=self.settle, new_offer=self.new_offer, ran=self.ran)
            for record in self.records:
                state = state.with_tool_result(record, limit=limit)
            return state

        # None when it expired meanwhile: the next turn opens a new one.
        self.rt.sessions.update(session.agent_session_id, self.learner.user_key, change)

    def _compact(self, session) -> None:
        """Past the soft budget, fold the oldest turns into the rolling summary. Outside the session lock, after the
        answer; a failure leaves the conversation exactly as it is."""

        # Not gated on `should_stop`: the learner leaves as soon as the answer is done, and this is upkeep of the
        # session, not part of what they are waiting for.
        if self.opening:
            return
        try:
            state = self.rt.sessions.get(session.agent_session_id, self.learner.user_key)
            job = state.compaction_job(self.rt.limits) if state is not None else None
            if job is None:
                return
            old, folded = job
            made = summarize(self.rt.provider, old, folded, limit=self.rt.limits.max_summary_chars)
            self.usage_in += made.input_tokens
            self.usage_out += made.output_tokens
            applied = made.text is not None
            if applied:
                _log.info("agent compaction: folded %d turns into %d characters", len(folded), len(made.text))
                self.rt.sessions.update(session.agent_session_id, self.learner.user_key,
                                        lambda s: s.with_compacted(folded, made.text))  # fmt: skip
            self._record_summary(state, folded, made, applied)
        except Exception:
            _log.warning("agent compaction failed", exc_info=True, extra={"trace_id": self.trace_id})

    def _record_summary(self, state, folded, made, applied: bool) -> None:
        """One `agent.summary` record per summary call: why it ran, what it cost, how it ended. Counts and names only,
        never what was said. A failed summary is `fallback: kept_turns`: the conversation is left as it was."""

        if self.rt.record_summary is None:
            return
        limits = self.rt.limits
        turns, chars = len(state.recent_turns), sum(len(t.text) for t in state.recent_turns)
        over = [name for name, hit in (("turns", turns > limits.compact_after_turns),
                                       ("chars", chars > limits.compact_after_chars)) if hit]
        record = {
            "version": "agent-summary/1", "trace_id": self.trace_id, "outcome": "success" if applied else "failed",
            "reason": made.outcome, "fallback": None if applied else "kept_turns",
            "trigger": {"over": over, "turns": turns, "chars": chars, "after_turns": limits.compact_after_turns,
                        "after_chars": limits.compact_after_chars, "keep_turns": limits.keep_verbatim_turns},
            "folded_turns": len(folded), "folded_chars": sum(len(t.text) for t in folded),
            "had_summary": bool(state.summary), "summary_chars": len(made.text or ""),
            "input_tokens": made.input_tokens, "output_tokens": made.output_tokens, "latency_ms": made.latency_ms,
            **self._price(made),
        }
        try:
            self.rt.record_summary(self.learner.user_key, record)
        except Exception:  # telemetry never costs the learner their session
            _log.warning("agent summary not recorded", exc_info=True, extra={"trace_id": self.trace_id})

    def _price(self, made) -> dict:
        """Provider, model and the estimated cost of the call, from the platform's catalog; unknown when unavailable."""

        none = {"provider": None, "model": None, "cost": None}
        if self.rt.price_summary is None:
            return none
        try:
            return self.rt.price_summary(made.input_tokens, made.output_tokens)
        except Exception:
            return none

    def _focus(self, state, turn: TurnInput):
        """The session's focus after this turn: what was selected, looked up or offered, and a long paste."""

        named = list(self.lookups)
        named += [(a.payload["text"], a.payload.get("lang")) for a in self.outputs_actions
                  if a.type in WORD_ACTIONS and isinstance(a.payload.get("text"), str)]
        context = turn.context
        ids = {k: getattr(context, k) for k in ("content_id", "lesson_id", "essay_id") if getattr(context, k, None)}
        return focus_after(
            state.focus, selected=context.selected_item, word=named[-1] if named else None, ids=ids,
            pasted=turn.message, pasted_cap=self.rt.limits.max_turn_chars,
        )

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
