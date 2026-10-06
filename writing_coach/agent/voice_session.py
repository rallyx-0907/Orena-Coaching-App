"""A live voice session in mode A, speech to speech (contract §9; human decision R28, 2026-10-06).

The provider speaks for Orena: Gemini Live (D4) hears the learner and answers aloud. The human chose this over a
server-written reply (mode B) for its conversation, about 1 s to first audio, with barge-in, and accepted that the
spoken words do not pass every gate a text turn does. What the server keeps:

- the key never reaches the client: the client opens the vendor socket with a one-use token, and the token carries
  the whole setup - model, voice, Orena's instruction and context, the tools - locked, so the client cannot change
  who Orena is or what it may call (verified live 2026-10-06: a client "setup" asking for another persona is
  ignored);
- tools run here: the model's function calls come back through `relay`, the read tools read only the signed-in
  learner's data in the session's language, and a reply tool (a button, a coach note, the address) is judged by the
  same `ReplyOutputs` as in text - D-135, no unasked routing, notes only on the learner's own request. Each answer
  is also given as §4 events for the thread;
- fifteen minutes at most (§9), then the token is spent; no audio is stored;
- the time used is priced from the audio catalog into the shared AI ledger, so the daily spend cap counts voice.
"""

from __future__ import annotations

import json
import logging
import secrets
import threading
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any, Protocol

from writing_coach.agent import learner_copy
from writing_coach.agent.context import TurnInput, build_tier1
from writing_coach.agent.events import Event, ToolCallEvent, ToolResultEvent, EvidenceEvent, Display
from writing_coach.agent.outputs import (
    FORGET_NOTE,
    KIND_BY_SOURCE,
    OFFER_ADDRESS,
    PROPOSE_ACTION,
    REMEMBER_NOTE,
    SET_ADDRESS,
    ReplyOutputs,
    asks_to_go,
    reply_tool_specs,
)
from writing_coach.agent.prompts import INSTRUCTION, context_document, selection_line, style_for
from writing_coach.agent.provider import ProviderToolSpec
from writing_coach.agent.redaction import redact_for_provider
from writing_coach.agent.schemas import TurnRequest
from writing_coach.agent.tools import FORBIDDEN_ARGUMENTS, LearnerScope, ToolArgumentsInvalid

_log = logging.getLogger(__name__)

VOICE_MODEL = "gemini-3.8-live"


@dataclass(frozen=True)
class VoiceChoice:
    """One of Orena's voices as the learner picks it: an id and labels of Orena's own, never the vendor's name."""

    id: str
    vendor_voice: str
    gender: str
    label: Mapping[str, str]


# The learner's choice of Orena's voice (R29: about ten of the best, six female and four male). The vendor's voice
# names stay here; the client sees only these ids and labels.
VOICE_CATALOG: tuple[VoiceChoice, ...] = (
    VoiceChoice("f-clear", "Kore", "female", {"en": "Clear", "vi": "Rõ ràng", "zh-CN": "清晰"}),
    VoiceChoice("f-bright", "Aoede", "female", {"en": "Bright", "vi": "Tươi sáng", "zh-CN": "明亮"}),
    VoiceChoice("f-warm", "Sulafat", "female", {"en": "Warm", "vi": "Ấm áp", "zh-CN": "温暖"}),
    VoiceChoice("f-soft", "Achernar", "female", {"en": "Soft", "vi": "Nhẹ nhàng", "zh-CN": "柔和"}),
    VoiceChoice("f-young", "Leda", "female", {"en": "Youthful", "vi": "Trẻ trung", "zh-CN": "年轻"}),
    VoiceChoice("f-gentle", "Vindemiatrix", "female", {"en": "Gentle", "vi": "Dịu dàng", "zh-CN": "温柔"}),
    VoiceChoice("m-calm", "Charon", "male", {"en": "Calm", "vi": "Điềm tĩnh", "zh-CN": "沉稳"}),
    VoiceChoice("m-lively", "Puck", "male", {"en": "Lively", "vi": "Sôi nổi", "zh-CN": "活泼"}),
    VoiceChoice("m-friendly", "Achird", "male", {"en": "Friendly", "vi": "Thân thiện", "zh-CN": "友好"}),
    VoiceChoice("m-steady", "Orus", "male", {"en": "Steady", "vi": "Vững vàng", "zh-CN": "稳重"}),
)
DEFAULT_VOICE = "f-clear"
_VOICES = {choice.id: choice for choice in VOICE_CATALOG}
VOICE_NAME = _VOICES[DEFAULT_VOICE].vendor_voice


def voice_catalog(interface: str) -> dict[str, Any]:
    """GET /api/agent/voice/voices: Orena's voices, labelled in the interface language (en when it has none)."""

    return {
        "default": DEFAULT_VOICE,
        "voices": [{"id": c.id, "gender": c.gender, "label": c.label.get(interface) or c.label["en"]}
                   for c in VOICE_CATALOG],  # fmt: skip
    }


def vendor_voice(choice: object) -> str:
    """The vendor voice for a learner's choice; an unknown or missing one is the default."""

    return _VOICES.get(str(choice), _VOICES[DEFAULT_VOICE]).vendor_voice if choice else VOICE_NAME
SESSION_SECONDS = 15 * 60  # §9: a voice session is capped at fifteen minutes
# The reply tools a spoken turn may use: a button, a coach note, the address. Evidence ids, styles, references and
# suggestions are a text thread's; the voice says what it read.
VOICE_REPLY_TOOLS = frozenset({REMEMBER_NOTE, FORGET_NOTE, SET_ADDRESS, OFFER_ADDRESS})
# A spoken button, as one flat choice: the live run (2026-10-06) showed the voice model never filling
# propose_action's nested payload for "save this word". The server fills the payload from the selection and judges
# it as propose_action exactly (D-135, no unasked routing).
OFFER_BUTTON = "offer_button"
OFFER_BUTTON_SPEC = ProviderToolSpec(
    OFFER_BUTTON,
    "Show the learner a button: save_word (save the selected word), open_word (open the selected word in their "
    "library), start_review (review their due words), or open_content (open a listening lesson or reading text: "
    "first call find_content, then pass the content_id it returned). When the learner asked to open it, the app "
    "opens it at once. Call it whenever they ask for one of these.",
    {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["save_word", "open_word", "start_review", "open_content"]},
        "text": {"type": "string", "description": "the word; the selected one if left out"},
        "content_id": {"type": "string", "description": "for open_content: a content_id find_content returned"}},
     "required": ["action"]},
)  # fmt: skip
# Where a content_id opens (contract §6.1): a listening lesson or a reading text.
OPENS_BY_PREFIX = {"media": "listening.workspace", "article": "reading.workspace", "book": "reading.workspace"}

VOICE_RULES = """This is a live voice conversation: everything you say is heard, not read. These rules override any
formatting rule above.
- Speak the support language (context.languages.support), in one to three short spoken sentences. Chinese or
  English words are said as they are. No example unless the learner asks for one.
- Plain speech only: no Markdown, asterisks, lists, headings, symbols, links or ids.
- To find something to listen to or read, call find_content (by kind, level, topic or title words), then
  offer_button with open_content and the content_id it returned.
- When the learner asks you to save a word, open it in their library, review their words or open a lesson or text,
  call offer_button with that action first. Only after it is accepted may you say there is a button to tap; if it is refused, say why in
  a sentence and never mention a button. Never say it is done, prepared or set up; never say you opened, saved or
  changed anything.
- Read before you claim: a word's meaning or a conclusion about the learner's learning comes from a tool you called.
- If you cannot do what the learner asks - no tool for it, or a tool refused or found nothing - say so once, in one
  sentence ("Mình chưa mở được nội dung đó."), and stop. Never repeat yourself or ask the same thing again.
- If the learner interrupts, stop and listen; answer what they said next."""


# --- the vendor setup -------------------------------------------------------------------------------------------


_DROPPED_SCHEMA_KEYS = frozenset({"additionalProperties", "$schema", "title", "minItems", "maxItems", "default"})


def gemini_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
    """A JSON schema in the subset a Gemini function declaration takes (OpenAPI types, upper case)."""

    out: dict[str, Any] = {}
    for key, value in schema.items():
        if key in _DROPPED_SCHEMA_KEYS:
            continue
        if key == "type":
            types = [value] if isinstance(value, str) else [t for t in value if t != "null"]
            out["type"] = str(types[0] if types else "string").upper()
            if not isinstance(value, str) and "null" in value:
                out["nullable"] = True
        elif key == "properties" and isinstance(value, Mapping):
            out["properties"] = {name: gemini_schema(sub) for name, sub in value.items() if isinstance(sub, Mapping)}
        elif key == "items" and isinstance(value, Mapping):
            out["items"] = gemini_schema(value)
        elif key in ("anyOf", "oneOf") and isinstance(value, list):
            choices = [gemini_schema(sub) for sub in value if isinstance(sub, Mapping) and sub.get("type") != "null"]
            if choices:
                out.update(choices[0])  # the first concrete choice; Live takes no unions
        elif key in ("description", "enum", "required", "format", "minimum", "maximum"):
            out[key] = value
    return out


def function_declarations(specs: Iterable[ProviderToolSpec]) -> list[dict[str, Any]]:
    return [{"name": s.name, "description": s.description, "parameters": gemini_schema(s.parameters)} for s in specs]


def live_setup(instruction: str, specs: Iterable[ProviderToolSpec], *, model: str = VOICE_MODEL,
               voice: str = VOICE_NAME) -> dict[str, Any]:  # fmt: skip
    """The session's setup, locked into its token: the client cannot change any of it."""

    return {
        "model": f"models/{model}",
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
        "systemInstruction": {"parts": [{"text": instruction}]},
        "tools": [{"functionDeclarations": function_declarations(specs)}],
        "inputAudioTranscription": {},
        "outputAudioTranscription": {},
    }


class VoiceTokens(Protocol):
    """The provider side (ai/live_voice.py): a one-use token for this setup, locked in; and its socket."""

    socket_url: str

    def mint(self, setup: Mapping[str, Any], *, now: datetime, seconds: int) -> tuple[str, str]: ...

# --- sessions ----------------------------------------------------------------------------------------------------


@dataclass
class VoiceSession:
    voice_session_id: str
    user_key: str
    learner: LearnerScope
    request: TurnRequest
    model: str
    opened: float  # the clock's seconds
    outputs: ReplyOutputs
    evidence_count: int = 0
    ended: bool = False


@dataclass
class VoiceSessions:
    """The open sessions, in this process (one worker on staging, R26), each with its learner and clock."""

    clock: Callable[[], float] = time.monotonic
    _sessions: dict[str, VoiceSession] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, session: VoiceSession) -> None:
        with self._lock:
            self._sessions[session.voice_session_id] = session

    def get(self, voice_session_id: str, user_key: str) -> VoiceSession | None:
        """The learner's own session while it lasts; another learner's id is as good as none."""

        with self._lock:
            session = self._sessions.get(voice_session_id)
        if session is None or session.user_key != user_key or session.ended:
            return None
        if self.clock() - session.opened > SESSION_SECONDS:
            return None
        return session

    def close(self, voice_session_id: str, user_key: str) -> VoiceSession | None:
        with self._lock:
            session = self._sessions.get(voice_session_id)
            if session is None or session.user_key != user_key or session.ended:
                return None
            session.ended = True
            del self._sessions[voice_session_id]
            return session

    def expired(self) -> list[VoiceSession]:
        """Sessions past their fifteen minutes, taken out (each is billed once, at its cap)."""

        now = self.clock()
        with self._lock:
            gone = [s for s in self._sessions.values() if now - s.opened > SESSION_SECONDS]
            for session in gone:
                session.ended = True
                del self._sessions[session.voice_session_id]
        return gone


RecordAudio = Callable[..., None]


@dataclass
class VoiceService:
    """Opens a learner's voice session, runs its tool calls, and closes and bills it."""

    runtime: Any  # AgentRuntime: its tools, capabilities and session cache
    tokens: VoiceTokens
    record_audio: RecordAudio | None = None
    sessions: VoiceSessions = field(default_factory=VoiceSessions)
    model: str = VOICE_MODEL
    now: Callable[[], datetime] = lambda: datetime.now(UTC)

    # -- open ------------------------------------------------------------------------------------------------

    def open(self, body: Mapping[str, Any], learner: LearnerScope) -> dict[str, Any]:
        self._bill_expired()
        request = TurnRequest.model_validate({**dict(body), "trigger": "open"})
        turn = TurnInput.from_request(request)
        session_state, _ = self.runtime.sessions.open(request.session_id, learner.user_key)
        tier1 = build_tier1(turn, session_state.for_target(request.context.locale.target))
        here = [c for c in (self.runtime.capabilities.get(i) for i in self._capability_ids(tier1)) if c]
        instruction = self._instruction(turn, tier1, here, session_state)
        specs = self._tool_specs(request, learner)
        now = self.now()
        setup = live_setup(instruction, specs, model=self.model, voice=vendor_voice(body.get("voice")))
        token, expires = self.tokens.mint(setup, now=now, seconds=SESSION_SECONDS)
        selected = request.context.selected_item
        outputs = ReplyOutputs(
            client=request.client, interface=request.context.locale.interface,
            support=request.context.locale.support, target=request.context.locale.target, version=request.version,
            notes={note.id: note.weight for note in tier1.coach_notes}, address_terms=tier1.address.pair,
            address_chosen=tier1.address.chosen, take_ref=request.context.take_ref,
            focused=bool(selected or request.context.essay_id),
            text_in_view=selected is not None and selected.type in ("word", "sentence"),
            selected_word=selected.text if selected is not None and selected.type == "word" else None,
        )  # fmt: skip
        for key in ("content_id", "lesson_id", "essay_id", "attempt_id"):
            outputs.learn_ids(key, (getattr(request.context, key),))
        session = VoiceSession(
            voice_session_id=f"vs-{secrets.token_hex(8)}", user_key=learner.user_key, learner=learner,
            request=request, model=self.model, opened=self.sessions.clock(), outputs=outputs,
        )  # fmt: skip
        self.sessions.add(session)
        return {
            "voice_session_id": session.voice_session_id,
            "mode": "s2s",
            "transport": "websocket",
            "connect": {
                "url": self.tokens.socket_url,
                "ephemeral_token": token,
                "expires_at": expires,
                # the one message the client sends first; the token's locked setup decides everything else
                "setup": {"setup": {"model": f"models/{self.model}"}},
            },
            "max_seconds": SESSION_SECONDS,
        }

    def _capability_ids(self, tier1) -> tuple[str, ...]:
        target = tier1.contract_locale.target
        return tuple(entry.id for entry in self.runtime.capabilities.for_surface(tier1.surface, target))

    def _instruction(self, turn: TurnInput, tier1, here, session_state) -> str:
        context = json.dumps(context_document(turn, tier1, here, session_state), ensure_ascii=False)
        parts = [INSTRUCTION, VOICE_RULES, f"context: {context}"]
        style = style_for(tier1.contract_locale.support, tier1.address)
        if style:
            parts.append(style)
        selected = selection_line(tier1)
        if selected:
            parts.append(selected)
        return "\n\n".join(parts)

    def _tool_specs(self, request: TurnRequest, learner: LearnerScope) -> list[ProviderToolSpec]:
        reads = [ProviderToolSpec.from_tool(t) for t in self.runtime.tools.tools() if learner.contract_language in t.languages]
        replies = [s for s in reply_tool_specs(request.client, request.context.locale.target, version=request.version)
                   if s.name in VOICE_REPLY_TOOLS]  # fmt: skip
        if request.client.allowed_actions & {"save_word", "navigate", "start_review"}:
            replies.append(OFFER_BUTTON_SPEC)
        return reads + replies

    def _button(self, session: VoiceSession, args: Mapping[str, Any]) -> dict[str, Any]:
        """offer_button as the propose_action it stands for: the payload filled from the selection."""

        context = session.request.context
        selected = context.selected_item
        text = args.get("text") if isinstance(args.get("text"), str) and args.get("text").strip() else (
            selected.text if selected is not None and selected.type == "word" else None)  # fmt: skip
        target = context.locale.target
        action = args.get("action")
        if action == "save_word":
            return {"type": "save_word", "payload": {"text": text, "lang": target}}
        if action == "open_word":
            return {"type": "navigate", "payload": {"intent": "vocabulary.word", "text": text, "lang": target}}
        if action == "start_review":
            return {"type": "start_review", "payload": {"scope": "due"}}
        if action == "open_content":
            content_id = str(args.get("content_id") or "")
            intent = OPENS_BY_PREFIX.get(content_id.partition(":")[0], "listening.workspace")
            return {"type": "navigate", "payload": {"intent": intent, "content_id": content_id}}
        return {"type": str(action), "payload": {}}

    # -- tool calls --------------------------------------------------------------------------------------------

    def relay(self, voice_session_id: str, calls: Iterable[Mapping[str, Any]], learner: LearnerScope,
              heard: str | None = None) -> dict[str, Any] | None:  # fmt: skip
        """Run the model's function calls; None when the session is not this learner's or is over."""

        session = self.sessions.get(voice_session_id, learner.user_key)
        if session is None:
            return None
        if heard is not None and heard[:2000] != session.outputs.learner_words:
            # A new utterance is a new turn: its buttons and notes are counted afresh (what was read stays known).
            session.outputs.learner_words = heard[:2000]  # what the learner just said: a note needs their words
            session.outputs.actions.clear()
            session.outputs.memory_updates.clear()
        responses: list[dict[str, Any]] = []
        events: list[Event] = []
        opened: str | None = None
        for call in calls:
            name, args, call_id = str(call.get("name") or ""), call.get("args"), call.get("id")
            args = args if isinstance(args, Mapping) else {}
            if name == OFFER_BUTTON:
                before = len(session.outputs.actions)
                answer = session.outputs.handle(PROPOSE_ACTION, self._button(session, args), known_evidence=frozenset())
                added = session.outputs.actions[before:]
                events.extend(added)
                # R29: a place the learner asked to go to opens at once (§7: navigate runs when the learner's own
                # words were the request); the button stays in the thread.
                if added and added[0].type == "navigate" and asks_to_go(session.outputs.learner_words):
                    opened = added[0].id
                    answer += " It opens now: say in a few words what is opening."
                responses.append({"id": call_id, "name": name, "response": {"result": answer}})
                continue
            if name in VOICE_REPLY_TOOLS:
                before = (len(session.outputs.actions), len(session.outputs.memory_updates))
                answer = session.outputs.handle(name, args, known_evidence=frozenset())
                events.extend(session.outputs.actions[before[0]:])
                events.extend(session.outputs.memory_updates[before[1]:])
                result: dict[str, Any] = {"result": answer}
            else:
                result, read_events = self._read(session, name, args)
                events.extend(read_events)
            responses.append({"id": call_id, "name": name, "response": result})
        answer = {"responses": responses, "events": [{"event": e.name, "data": e.to_wire()} for e in events]}
        if opened is not None:
            answer["open"] = opened  # the client runs this action now, without a tap (R29)
        return answer

    def _read(self, session: VoiceSession, name: str, args: Mapping[str, Any]) -> tuple[dict[str, Any], list[Event]]:
        from writing_coach.agent.turn import learner_context  # the request context the repositories scope by

        tools = self.runtime.tools
        tool = tools.get(name) if name in tools.names() else None
        if tool is None or session.learner.contract_language not in tool.languages:
            return {"result": "unavailable: no such tool here"}, []
        if FORBIDDEN_ARGUMENTS & {str(key).casefold() for key in args}:
            return {"result": "refused: tools read only the signed-in learner's own data"}, []
        support = session.request.context.locale.support
        interface = session.request.context.locale.interface
        label = learner_copy.text(f"tool.{tool.name}", interface=interface, support=support)[1]
        events: list[Event] = [ToolCallEvent(tool=tool.name, label=label)]
        learner = replace(session.learner, interface=interface)
        try:
            with learner_context(session.learner):
                result = tools.invoke(tool.name, learner, dict(args))
        except ToolArgumentsInvalid:
            return {"result": "refused: arguments do not fit this tool's schema"}, events
        except Exception:
            _log.warning("voice tool %s failed", tool.name, exc_info=True)
            summary = learner_copy.text("result.unavailable", interface=interface, support=support)[1]
            return {"result": "unavailable: the service did not answer"}, [*events, ToolResultEvent(tool=tool.name, summary=summary, evidence_ids=[])]
        first = session.evidence_count
        ids = [f"v{first + i + 1}" for i in range(len(result.evidence))]
        session.evidence_count += len(ids)
        summary = learner_copy.text(f"result.{tool.name}", interface=interface, support=support, n=result.count)[1]
        events.append(ToolResultEvent(tool=tool.name, summary=summary, evidence_ids=ids))
        for evidence_id, evidence in zip(ids, result.evidence, strict=True):
            events.append(EvidenceEvent(
                id=evidence_id, source=evidence.source, ref=dict(evidence.ref), excerpt=dict(evidence.excerpt),
                display=Display(kind=KIND_BY_SOURCE[evidence.source]) if evidence.source in KIND_BY_SOURCE else None,
            ))  # fmt: skip
        kind = next((KIND_BY_SOURCE.get(e.source) for e in result.evidence if e.source in KIND_BY_SOURCE), None)
        session.outputs.learn_from(result.data, kind=kind)
        session.outputs.learn_from([dict(e.ref) for e in result.evidence], kind=kind)
        return {"summary": result.summary, "data": redact_for_provider(dict(result.data))}, events

    # -- close and bill ------------------------------------------------------------------------------------------

    def end(self, voice_session_id: str, learner: LearnerScope) -> dict[str, Any] | None:
        session = self.sessions.close(voice_session_id, learner.user_key)
        if session is None:
            return None
        seconds = self._bill(session)
        return {"voice_session_id": voice_session_id, "seconds": seconds}

    def _bill_expired(self) -> None:
        for session in self.sessions.expired():
            self._bill(session)

    def _bill(self, session: VoiceSession) -> float:
        seconds = round(min(SESSION_SECONDS, max(0.0, self.sessions.clock() - session.opened)), 1)
        if self.record_audio is not None:
            try:
                self.record_audio("agent_voice", provider="gemini", model=session.model, outcome="success",
                                  latency_ms=None, audio_seconds=seconds)  # fmt: skip
            except Exception:  # billing telemetry never fails the learner's request
                _log.warning("voice session not recorded", exc_info=True)
        meter = getattr(self.runtime, "meter", None)
        if meter is not None:
            try:
                meter(session.user_key, "agent.voice_seconds", int(seconds), f"{session.voice_session_id}:voice")
            except Exception:
                _log.warning("voice metering failed", exc_info=True)
        return seconds
