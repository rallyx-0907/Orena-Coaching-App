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
- the time used is priced from the audio catalog into the shared AI ledger, so the daily spend cap counts voice;
- the learner's plan pays for it by duration (D-16T): when `orena.message` is enforced the session reserves the
  messages it may use (one per `voice_seconds_per_message`), the token's life is the seconds those buy, and the
  session settles what it really used when it ends. The ledger and the allowance are separate things: the allowance
  is what the learner is charged, the ledger is what the vendor charges.
"""

from __future__ import annotations

import json
import logging
import re
import secrets
import threading
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any, Protocol

from writing_coach.agent import learner_copy, surfaces
from writing_coach.agent.context import TurnInput, build_tier1
from writing_coach.agent.contract import SURFACES, WORD_ACTIONS, actions_for_version, intents_for_version
from writing_coach.agent.events import Event, ToolCallEvent, ToolResultEvent, EvidenceEvent, Display
from writing_coach.agent.focus import focus_after, lookup_word
from writing_coach.agent.pending import CANCELLED, COMPLETED, CONFIRM, action_key
from writing_coach.agent.session import ConversationTurn
from writing_coach.agent.outputs import (
    FORGET_NOTE,
    KIND_BY_SOURCE,
    OFFER_ADDRESS,
    PROPOSE_ACTION,
    REMEMBER_NOTE,
    RESOLVE_PENDING,
    SET_ADDRESS,
    ReplyOutputs,
    asked_for,
    reply_tool_specs,
)
from writing_coach.agent.prompts import INSTRUCTION, context_document, selection_line, style_for
from writing_coach.agent.provider import ProviderToolSpec
from writing_coach.agent.redaction import redact_for_provider
from writing_coach.agent.schemas import TurnRequest
from writing_coach.agent.tools import FORBIDDEN_ARGUMENTS, LearnerScope, ToolArgumentsInvalid
from writing_coach.core.errors import orena_http_error
from writing_coach.product import quota

_log = logging.getLogger(__name__)

VOICE_MODEL = "gemini-3.8-live"
VOICE_METER = "orena.message"  # a voice minute is a message: `voice_seconds_per_message` seconds each (D-16T)


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

SESSION_SECONDS = 15 * 60  # §9: a voice session is capped at fifteen minutes, in all its chunks
# D-16T: the session is a chain of short tokens. A chunk is VOICE_CHUNK_UNITS messages of voice (2 x 60 s = 2 minutes
# at the catalogue's default), never under VOICE_MIN_CHUNK_SECONDS whatever an administrator sets, and is charged whole
# when its token is minted. The client asks for the next one RENEW_LEAD_SECONDS before the token it holds dies.
VOICE_CHUNK_UNITS = 2
VOICE_MIN_CHUNK_SECONDS = 60
RENEW_LEAD_SECONDS = 12
# The most characters of a vendor resumption handle a client may hand back (it goes into the next locked setup).
RESUMPTION_HANDLE_PATTERN = re.compile(r"^[A-Za-z0-9._:=/+-]{1,2048}$")
# The reply tools a spoken turn may use besides do_action: a coach note, the address. Evidence ids, styles,
# references and suggestions are a text thread's; the voice says what it read.
VOICE_REPLY_TOOLS = frozenset({REMEMBER_NOTE, FORGET_NOTE, SET_ADDRESS, OFFER_ADDRESS, RESOLVE_PENDING})

# One tool for everything the app can do (R30, 2026-10-06: "an agent that can operate anything in the app"): every
# §7 action the client declares, with flat arguments - the live run showed the voice model never filling
# propose_action's nested payload. The server builds the payload, filling it from what is in view, and judges it as
# propose_action exactly: the client's actions and intents, ids a tool returned, D-135, no unasked routing.
DO_ACTION = "do_action"
_DO_ACTION_ARGS: dict[str, Any] = {
    "content_id": {"type": "string", "description": "a lesson or text: one find_content returned, or the one in view"},
    "essay_id": {"type": "string", "description": "an essay a tool returned, or the one in view"},
    "grammar_id": {"type": "string", "description": "a grammar point a tool returned"},
    "text": {"type": "string", "description": "a word; the selected one if left out"},
    "item_id": {"type": "string", "description": "a line or item; the selected one if left out"},
    "scope": {"type": "string", "enum": ["due", "word"], "description": "start_review: all due words, or one word"},
    "focus": {"type": "string", "enum": ["tone", "stress", "word"], "description": "start_targeted_drill"},
    "item_ids": {"type": "array", "items": {"type": "string"}, "description": "start_targeted_drill: items to drill"},
    "collection_id": {"type": "string", "description": "add_word_to_collection: a collection a tool returned"},
    "requested": {"type": "boolean", "description": "true only when the learner's own words just asked for this or "
                   "accepted your offer of it: the app then does it at once. Otherwise leave it out: a button is shown."},
}


def do_action_spec(actions: Iterable[str], intents: Iterable[str]) -> ProviderToolSpec | None:
    """The do_action tool for this client: only the actions and places it declared."""

    actions, intents = sorted(actions), sorted(intents)
    if not actions:
        return None
    properties: dict[str, Any] = {"type": {"type": "string", "enum": actions}}
    if "navigate" in actions and intents:
        properties["intent"] = {"type": "string", "enum": intents, "description": "navigate: the place to open"}
    properties.update(_DO_ACTION_ARGS)
    return ProviderToolSpec(
        DO_ACTION,
        "Do something in the app for the learner: open a place (navigate with an intent; a lesson or text with its "
        "content_id - call find_content first), play the model audio, save or unsave a word, add it to a "
        "collection, start a review, start a drill. When the learner asked for it, the app does it at once; "
        "otherwise it shows a button. Fill only what the action needs; what is in view fills itself.",
        {"type": "object", "properties": properties, "required": ["type"]},
    )


# The learner asks for a lesson, a video or a text, not a review (R29 phone test): a review action is refused.
_ASKS_CONTENT = re.compile(
    r"(?i)\b(?:video|listening|reading|lesson|podcast|audio|bài nghe|bài đọc|bài học|nghe|đọc|xem)\b"
    r"|视频|听力|阅读|课文|节目"
)
_CONTENT_NOT_REVIEW = ("refused: the learner asked for a lesson, video or text, not a review - call find_content, "
                       "then do_action navigate with the content_id it returned")  # fmt: skip
# Where a content_id opens (contract §6.1): a listening lesson or a reading text.
OPENS_BY_PREFIX = {"media": "listening.workspace", "article": "reading.workspace", "book": "reading.workspace"}
# Recognition hints (contract codes -> BCP-47): the learner speaks their support language and the one they learn,
# often both in a sentence (phone test 2026-10-06: words heard in the wrong language).
RECOGNITION_CODES = {"vi": "vi-VN", "en": "en-US", "zh-CN": "cmn-CN"}

VOICE_RULES = """This is a live voice conversation: everything you say is heard, not read. These rules override any
formatting rule above.
- Speak the support language (context.languages.support), in one to three short spoken sentences. Chinese or
  English words are said as they are. No example unless the learner asks for one.
- Plain speech only: no Markdown, asterisks, lists, headings, symbols, links or ids.
- You can do anything the app can do for the learner with do_action: open any place, a lesson or a text (find it
  with find_content first), play the model audio, save a word, start a review or a drill. When they ask, call it.
  If it is accepted and they asked for it, it happens at once: say in a few words what is happening. Otherwise
  there is a button to tap. If it is refused, say why in a sentence. Never claim something happened that a tool
  did not accept.
- Read before you claim: a word's meaning or a conclusion about the learner's learning comes from a tool you called.
- When what you heard is unclear, makes no sense, or is in a language the learner does not use here, say you did
  not catch it and ask them to say it again. Never act on it.
- If you cannot do what the learner asks - no tool for it, or a tool refused or found nothing - say so once, in one
  sentence, and stop. Never repeat yourself or ask the same thing again.
- The conversation so far is in the context below, whether it was typed or spoken: carry on from it. When
  context.pending_interaction is open and the learner accepts it in any words, call do_action with that same
  action and requested true; if they decline it, call resolve_pending with that offer's id and decision cancel; if
  they ask something else, do nothing about it.
- A line starting "[context]" tells you where the learner is now; use it, never answer it.
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


def recognition_languages(*codes: str | None) -> list[str]:
    """The languages the learner speaks here, as recognition hints: support and target, in that order."""

    out: list[str] = []
    for code in codes:
        bcp = RECOGNITION_CODES.get(str(code or ""))
        if bcp and bcp not in out:
            out.append(bcp)
    return out


def live_setup(instruction: str, specs: Iterable[ProviderToolSpec], *, model: str = VOICE_MODEL,
               voice: str = VOICE_NAME, languages: Iterable[str] = (),
               resumption: Mapping[str, Any] | None = None) -> dict[str, Any]:  # fmt: skip
    """The session's setup, locked into its token: the client cannot change any of it. `resumption` asks the vendor for
    resumption handles (`{}`) or carries the handle of the conversation to carry on (`{"handle": ...}`): the setup of
    each chunk's token is where it is locked, so a client cannot make the vendor resume anything else."""

    languages = list(languages)
    setup = _live_setup(instruction, specs, model=model, voice=voice, languages=languages)
    if resumption is not None:
        setup["sessionResumption"] = dict(resumption)
    return setup


def _live_setup(instruction: str, specs: Iterable[ProviderToolSpec], *, model: str, voice: str,
                languages: list[str]) -> dict[str, Any]:
    return {
        "model": f"models/{model}",
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
        "systemInstruction": {"parts": [{"text": instruction}]},
        "tools": [{"functionDeclarations": function_declarations(specs)}],
        # Recognition hints (verified accepted live 2026-10-06): heard in these languages, not guessed among all.
        "inputAudioTranscription": {"languageCodes": languages} if languages else {},
        "outputAudioTranscription": {},
    }


def _in_view(outputs: ReplyOutputs, context: Any) -> None:
    """What is on the learner's screen, for judging the session's actions: the ids it may name, the selection."""

    selected = context.selected_item
    outputs.take_ref = context.take_ref
    outputs.focused = bool(selected or context.essay_id)
    outputs.text_in_view = selected is not None and selected.type in ("word", "sentence")
    outputs.selected_word = selected.text if selected is not None and selected.type == "word" else None
    for key in ("content_id", "lesson_id", "essay_id", "attempt_id"):
        outputs.learn_ids(key, (getattr(context, key),))
    if selected is not None and selected.id:
        outputs.learn_ids("item_id", (selected.id,))


def _context_note(context: Any) -> str:
    """The learner's place now, as the line the client hands the model ("[context] …"): escaped data, never prose
    a client could slip an instruction into."""

    place = {
        "surface": context.known_surface,
        "screen": surfaces.name(context.known_surface, context.locale.interface) if context.known_surface else None,
        "in_view": {key: getattr(context, key) for key in ("content_id", "lesson_id", "essay_id", "take_ref")
                    if getattr(context, key)},
        "selection": context.selected_item.model_dump(exclude_none=True) if context.selected_item else None,
    }  # fmt: skip
    data = json.dumps(redact_for_provider({k: v for k, v in place.items() if v}), ensure_ascii=False)
    return f"[context] The learner is now here: {data}. \"This\" means what is in view."


class VoiceTokens(Protocol):
    """The provider side (ai/live_voice.py): a one-use token for this setup, locked in; and its socket."""

    socket_url: str

    def mint(self, setup: Mapping[str, Any], *, now: datetime, seconds: int) -> tuple[str, str]: ...

TRANSCRIPT_MAX_TURNS = 40
TRANSCRIPT_TURN_CHARS = 4000
INSTRUCTION_TURNS = 12
INSTRUCTION_CHARS = 4000


def _conversation_so_far(state: Any) -> str:
    """The last turns of the conversation, typed or spoken, for the voice model's instruction (it speaks, so it
    must know what was said before the session opened)."""

    lines: list[dict[str, str]] = []
    total = 0
    for turn in reversed(state.recent_turns[-INSTRUCTION_TURNS:]):
        text = turn.text if len(turn.text) <= 600 else turn.text[:600] + "…"
        if total + len(text) > INSTRUCTION_CHARS and lines:
            break
        total += len(text)
        lines.append({"who": "learner" if turn.role == "user" else "orena", "said": text})
    if not lines:
        return ""
    earlier = f" Earlier, in short: {state.summary}" if state.summary else ""
    return ("The conversation so far (typed or spoken; carry on from it, never restart it): "
            + json.dumps(list(reversed(lines)), ensure_ascii=False) + earlier)


_UTTERANCE_ID = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")


def _utterance_id(value: object) -> str | None:
    """The client's identity of one utterance: a short opaque token it numbers itself. Anything else is no identity."""

    return value if isinstance(value, str) and _UTTERANCE_ID.match(value) else None


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
    agent_session_id: str = ""  # the conversation this voice session is part of (the typed turns' session)
    # The session is a chain of short vendor tokens, one per chunk (D-16T), each charged whole when it is minted: how
    # many exist, the seconds they were minted for in all, the session-clock instant the newest one dies, the setup
    # every one of them locks in, and the last renewal answer (a repeat of that request gets the same token back).
    setup: dict[str, Any] = field(default_factory=dict)
    chunks: int = 1
    minted_seconds: int = 0
    valid_until: float = 0.0
    attempts: int = 0
    last_extend: tuple[int, dict[str, Any]] | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)
    # The client's own utterance sequence (never the words): the one in progress, the ones already counted as a turn
    # of the conversation, and the ones whose words are already in it.
    utterance: str | None = None
    counted: set[str] = field(default_factory=set)
    texted: set[str] = field(default_factory=set)

    def ref(self, utterance: str) -> str:
        return f"{self.voice_session_id}:{utterance}"


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
        if self.clock() > session.valid_until:
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
        """Sessions whose newest token is dead, taken out. Nothing is owed on them: every chunk was charged whole when
        its token was minted (D-16T), so a session nobody ended costs what it already cost."""

        now = self.clock()
        with self._lock:
            gone = [s for s in self._sessions.values() if now > s.valid_until]
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
        self._sweep()
        request = TurnRequest.model_validate({**dict(body), "trigger": "open"})
        turn = TurnInput.from_request(request)
        session_state, _ = self.runtime.sessions.open(request.session_id, learner.user_key)
        tier1 = build_tier1(turn, session_state.for_target(request.context.locale.target))
        here = [c for c in (self.runtime.capabilities.get(i) for i in self._capability_ids(tier1)) if c]
        instruction = self._instruction(turn, tier1, here, session_state)
        specs = self._tool_specs(request, learner)
        locale = request.context.locale
        setup = live_setup(instruction, specs, model=self.model, voice=vendor_voice(body.get("voice")),
                           languages=recognition_languages(locale.support, locale.target),
                           resumption={})  # fmt: skip
        outputs = ReplyOutputs(
            client=request.client, interface=locale.interface, support=locale.support, target=locale.target,
            version=request.version, notes={note.id: note.weight for note in tier1.coach_notes},
            address_terms=tier1.address.pair, address_chosen=tier1.address.chosen,
            pending=session_state.live_pending(), settled=frozenset(done for done, _ in session_state.settled),
            recent_runs=session_state.recent_runs(),
        )  # fmt: skip
        _in_view(outputs, request.context)
        voice_session_id = f"vs-{secrets.token_hex(8)}"
        # The first chunk (D-16T): admitted before anything is sent to the vendor. A learner with no message left today
        # is a 429 here and no token is minted; a repeat of the request's `Idempotency-Key` is the same operation
        # (409, never a second charge); without a key each request is its own session.
        opened = self.sessions.clock()
        minted = self._mint_chunk(setup, session_id=voice_session_id, user_key=learner.user_key, index=0, minted=0,
                                  digest=quota.request_digest(dict(body)), key=None, resumption=None)
        session = VoiceSession(
            voice_session_id=voice_session_id, user_key=learner.user_key, learner=learner,
            request=request, model=self.model, opened=opened, outputs=outputs,
            agent_session_id=session_state.agent_session_id, setup=setup, chunks=1,
            minted_seconds=minted["seconds"], valid_until=opened + minted["seconds"],
        )  # fmt: skip
        self.sessions.add(session)
        return {
            "voice_session_id": voice_session_id,
            "session_id": session_state.agent_session_id,  # the conversation: typed turns use the same one
            "mode": "s2s",
            "transport": "websocket",
            **self._chunk_answer(minted, index=0),
        }

    # -- the chain of tokens (D-16T) ---------------------------------------------------------------------------

    def _mint_chunk(self, setup: dict[str, Any], *, session_id: str, user_key: str, index: int, minted: int,
                    digest: str, key: str | None, resumption: str | None) -> dict[str, Any]:
        """Admit, mint and charge one chunk. The learner's messages for the chunk are reserved, the token is minted
        for the seconds they buy (never past the session's 900), and the chunk is settled whole at once: it is charged
        when it exists, and nothing is refunded when the learner ends early, because the server cannot see the vendor
        socket and the token is what it lets them hold. A mint that fails charges nothing."""

        ticket = quota.begin_voice(
            VOICE_METER, max_seconds=SESSION_SECONDS - minted, chunk_units=VOICE_CHUNK_UNITS,
            min_chunk_seconds=VOICE_MIN_CHUNK_SECONDS, request_digest=digest, idempotency_key=key,
        )
        # Messages not enforced: one token for what is left of the session, exactly as before the plan limit.
        seconds = int(ticket.max_seconds) if ticket.max_seconds else SESSION_SECONDS - minted
        locked = dict(setup)
        if resumption:
            locked["sessionResumption"] = {"handle": resumption}
        try:
            ticket.dispatch(f"voice:{session_id}:{index}")
            token, expires = self.tokens.mint(locked, now=self.now(), seconds=seconds)
        except BaseException:
            ticket.settle(0, "failed")  # nothing was handed to the learner
            raise
        ticket.settle(ticket.units, "chunk")
        self._record_chunk(session_id, user_key, index, seconds)
        last = minted + seconds >= SESSION_SECONDS or not ticket.enforced
        return {"token": token, "expires": expires, "seconds": seconds, "last": last}

    def _chunk_answer(self, minted: dict[str, Any], *, index: int) -> dict[str, Any]:
        seconds = minted["seconds"]
        return {
            "connect": {
                "url": self.tokens.socket_url,
                "ephemeral_token": minted["token"],
                "expires_at": minted["expires"],
                # the one message the client sends first; the token's locked setup decides everything else
                "setup": {"setup": {"model": f"models/{self.model}"}},
            },
            "chunk": index,
            # This token's life in seconds: the client closes the session there if it holds nothing newer, and asks
            # for the next chunk `renew_in` seconds after it got this one (absent on the last chunk).
            "max_seconds": seconds,
            "session_max_seconds": SESSION_SECONDS,
            "renew_in": None if minted["last"] else max(1, seconds - RENEW_LEAD_SECONDS),
            "last": minted["last"],
        }

    def extend(self, voice_session_id: str, learner: LearnerScope, chunk: Any, resumption: Any = None) -> dict | None:
        """The next chunk of a session, for a learner who is still talking: None when the session is not this learner's
        or is over (the client ends it). `chunk` is the index of the chunk wanted, the number of tokens the client
        already holds: a repeat of the last request (a lost answer) gets that same token back without a second
        charge, any other index is a 409. A learner with no message left is the gate's 429, and the client ends the
        session when the token it holds dies."""

        session = self.sessions.get(voice_session_id, learner.user_key)
        if session is None:
            return None
        with session.lock:
            if session.ended:
                return None
            if session.last_extend is not None and session.last_extend[0] == chunk:
                return session.last_extend[1]
            if type(chunk) is not int or chunk != session.chunks:
                raise orena_http_error(409, "voice_chunk_mismatch", "That is not the next part of this conversation.",
                                       retryable=False)
            if session.minted_seconds >= SESSION_SECONDS:
                raise orena_http_error(409, "voice_session_over", "This conversation reached its time limit.",
                                       retryable=False)
            handle = resumption if isinstance(resumption, str) and RESUMPTION_HANDLE_PATTERN.match(resumption) else None
            try:
                minted = self._mint_chunk(
                    session.setup, session_id=voice_session_id, user_key=session.user_key, index=chunk,
                    minted=session.minted_seconds, digest=quota.request_digest({"voice": voice_session_id, "chunk": chunk}),
                    key=f"voice:{voice_session_id}:{chunk}:{session.attempts}", resumption=handle,
                )
            except BaseException:
                session.attempts += 1  # a refused or failed attempt is over: the next one is a new operation
                raise
            session.chunks += 1
            session.minted_seconds += minted["seconds"]
            session.valid_until = max(session.valid_until, self.sessions.clock() + minted["seconds"])
            answer = {"voice_session_id": voice_session_id, **self._chunk_answer(minted, index=chunk)}
            session.last_extend = (chunk, answer)
            return answer

    def _record_chunk(self, session_id: str, user_key: str, index: int, seconds: int) -> None:
        """The vendor ledger gets the chunk when its token is minted, at the seconds the token can be used for: the
        most the vendor can charge for it, whatever the learner does next. (Gemini Live reports its real usage only to
        the client on the socket, and the ledger has no field for tokens, a schema decision, so the token's life is
        the figure the server can know.)"""

        if self.record_audio is not None:
            try:
                self.record_audio("agent_voice", provider="gemini", model=self.model, outcome="success",
                                  latency_ms=None, audio_seconds=float(seconds))  # fmt: skip
            except Exception:  # billing telemetry never fails the learner's request
                _log.warning("voice session not recorded", exc_info=True)
        meter = getattr(self.runtime, "meter", None)
        if meter is not None:
            try:
                meter(user_key, "agent.voice_seconds", int(seconds), f"{session_id}:voice:{index}")
            except Exception:
                _log.warning("voice metering failed", exc_info=True)



    def _capability_ids(self, tier1) -> tuple[str, ...]:
        target = tier1.contract_locale.target
        return tuple(entry.id for entry in self.runtime.capabilities.for_surface(tier1.surface, target))

    def _instruction(self, turn: TurnInput, tier1, here, session_state) -> str:
        context = json.dumps(context_document(turn, tier1, here, session_state), ensure_ascii=False)
        parts = [INSTRUCTION, VOICE_RULES, f"context: {context}"]
        earlier = _conversation_so_far(session_state)
        if earlier:
            parts.append(earlier)
        style = style_for(tier1.contract_locale.support, tier1.address)
        if style:
            parts.append(style)
        selected = selection_line(tier1)
        if selected:
            parts.append(selected)
        return "\n\n".join(parts)

    def _tool_specs(self, request: TurnRequest, learner: LearnerScope) -> list[ProviderToolSpec]:
        reads = [ProviderToolSpec.from_tool(t) for t in self.runtime.tools.tools() if learner.contract_language in t.languages]
        replies = [s for s in reply_tool_specs(request.client, request.context.locale.target, version=request.version, pending=True)
                   if s.name in VOICE_REPLY_TOOLS]  # fmt: skip
        actions = request.client.allowed_actions & actions_for_version(request.version)
        intents = request.client.allowed_intents & intents_for_version(request.version)
        spec = do_action_spec(actions, intents)
        return reads + replies + ([spec] if spec else [])

    def _action(self, session: VoiceSession, args: Mapping[str, Any]) -> dict[str, Any]:
        """do_action as the propose_action it stands for: the payload built from its flat arguments, what is not
        given filled from what is in view (the selected word or line, the lesson, essay or take on screen)."""

        context = session.request.context
        selected = context.selected_item

        def given(key: str) -> str | None:
            value = args.get(key)
            return value.strip() if isinstance(value, str) and value.strip() else None

        word = given("text") or (selected.text if selected is not None and selected.type == "word" else None)
        item = given("item_id") or (selected.id if selected is not None and selected.id else None)
        in_view = {"content_id": given("content_id") or context.content_id, "essay_id": given("essay_id") or context.essay_id,
                   "grammar_id": given("grammar_id"), "take_ref": context.take_ref, "item_id": item,
                   "text": word, "lang": context.locale.target}  # fmt: skip
        kind = str(args.get("type") or "")
        if kind == "navigate":
            intent = given("intent")
            if intent is None and given("content_id"):  # a lesson or text named by its id alone
                intent = OPENS_BY_PREFIX.get(given("content_id").partition(":")[0])
            payload: dict[str, Any] = {"intent": intent}
            for name in SURFACES.get(str(intent), ()):
                if in_view.get(name):
                    payload[name] = in_view[name]
            return {"type": kind, "payload": payload}
        if kind in ("play_model", "say_again"):
            return {"type": kind, "payload": {k: in_view[k] for k in ("content_id", "item_id") if in_view[k]}}
        if kind in ("play_user", "compare_with_model"):
            return {"type": kind, "payload": {k: in_view[k] for k in ("take_ref", "item_id") if in_view[k]}}
        if kind in ("save_word", "unsave_word"):
            return {"type": kind, "payload": {"text": word, "lang": context.locale.target}}
        if kind == "add_word_to_collection":
            payload = {"text": word, "lang": context.locale.target}
            if given("collection_id"):
                payload["target"] = {"system": "library", "id": given("collection_id")}
            return {"type": kind, "payload": payload}
        if kind == "start_review":
            if args.get("scope") == "word" and word:
                return {"type": kind, "payload": {"scope": "word", "text": word, "lang": context.locale.target}}
            return {"type": kind, "payload": {"scope": "due"}}
        if kind == "start_targeted_drill":
            ids = [str(i) for i in args.get("item_ids") or () if str(i).strip()] or ([item] if item else [])
            return {"type": kind, "payload": {"focus": args.get("focus") or "word", "item_ids": ids}}
        return {"type": kind, "payload": {}}

    # -- tool calls --------------------------------------------------------------------------------------------

    def relay(self, voice_session_id: str, calls: Iterable[Mapping[str, Any]], learner: LearnerScope,
              heard: str | None = None, utterance: str | None = None) -> dict[str, Any] | None:  # fmt: skip
        """Run the model's function calls; None when the session is not this learner's or is over. `utterance` is the
        client's identity of what the learner is saying (see `utterance_turn`)."""

        session = self.sessions.get(voice_session_id, learner.user_key)
        if session is None:
            return None
        # An empty `heard` is a transcript that had not arrived yet, never an utterance of no words: it changes
        # nothing (the phone test: "" cleared the request to open and the turn's buttons).
        heard = heard if heard is not None and heard.strip() else None
        self._refresh(session)  # a typed turn may have changed the offer or run something since the last call
        utterance = _utterance_id(utterance)
        if utterance is not None:
            new_utterance = utterance != session.utterance
            session.utterance = utterance
        else:  # a client with no identity: a change of words is the only sign of a new utterance
            new_utterance = heard is not None and heard[:2000] != session.outputs.learner_words
        if new_utterance:
            # A new utterance is a new turn: its buttons and notes are counted afresh (what was read stays known).
            session.outputs.learner_words = ""
            session.outputs.actions.clear()
            session.outputs.memory_updates.clear()
            session.outputs.resolution = None
        if heard is not None:
            session.outputs.learner_words = heard[:2000]  # what the learner just said: a note needs their words
        new_heard = heard[:2000] if heard is not None and (utterance is not None or new_utterance) else None
        responses: list[dict[str, Any]] = []
        events: list[Event] = []
        opened: str | None = None
        words: list[tuple[str, str | None]] = []  # words a tool was asked about or an action named: the focus
        for call in calls:
            name, args, call_id = str(call.get("name") or ""), call.get("args"), call.get("id")
            args = args if isinstance(args, Mapping) else {}
            if name == DO_ACTION and args.get("type") == "start_review" and _ASKS_CONTENT.search(
                    session.outputs.learner_words or ""):  # fmt: skip
                # The phone test: "open any video in Listening" got a review button that opened an empty Review.
                responses.append({"id": call_id, "name": name, "response": {"result": _CONTENT_NOT_REVIEW}})
                continue
            if name == DO_ACTION:
                before = len(session.outputs.actions)
                proposal = self._action(session, args)
                if args.get("requested") is True:  # the model's own judgement that the learner asked (agent/outputs.py)
                    proposal["requested"] = True
                answer = session.outputs.handle(PROPOSE_ACTION, proposal, known_evidence=frozenset())
                added = session.outputs.actions[before:]
                events.extend(added)
                if added and added[0].open:
                    opened = added[0].id
                    answer += " It happens now: say in a few words what is happening."
                # R29/R30: what the learner's own words asked for happens at once - a place opens (§7), a low-risk
                # action runs, a CONFIRM one goes through the app's own confirmation; the button stays in the thread.
                if added and not added[0].open and asked_for(added[0].type, session.outputs.learner_words):
                    events[events.index(added[0])] = added[0].model_copy(update={"open": True})
                    opened = added[0].id
                    answer += " It happens now: say in a few words what is happening."
                responses.append({"id": call_id, "name": name, "response": {"result": answer}})
                continue
            if name in VOICE_REPLY_TOOLS:
                seen = (list(session.outputs.actions), len(session.outputs.memory_updates))
                answer = session.outputs.handle(name, args, known_evidence=frozenset())
                added = [a for a in session.outputs.actions if not any(a is old for old in seen[0])]  # a confirmed offer is put first
                events.extend(added)
                events.extend(session.outputs.memory_updates[seen[1]:])
                if added and added[0].open:  # accepting the open offer by its id: it runs now, once
                    opened = added[0].id
                result: dict[str, Any] = {"result": answer}
            else:
                if (word := lookup_word(name, args)) is not None:
                    words.append((word, session.request.context.locale.target))
                result, read_events = self._read(session, name, args)
                events.extend(read_events)
            responses.append({"id": call_id, "name": name, "response": result})
        self._remember(session, heard=new_heard, utterance=utterance, events=events, words=words)
        answer = {"responses": responses, "events": [{"event": e.name, "data": e.to_wire()} for e in events]}
        if opened is not None:
            answer["open"] = opened  # the client runs this action now, without a tap (R29)
        return answer

    # -- where the learner is now ----------------------------------------------------------------------------------

    def update_context(self, voice_session_id: str, context: Mapping[str, Any], learner: LearnerScope) -> dict | None:
        """The learner moved (another place, a lesson, a line): the session's context follows, so "this sentence"
        or "this lesson" means what is on their screen now. Answers a note for the client to give the model as a
        context line (it is not a turn: no answer is asked)."""

        session = self.sessions.get(voice_session_id, learner.user_key)
        if session is None:
            return None
        body = session.request.model_dump(mode="json", exclude_none=True, by_alias=True)
        was = body.get("context", {})
        moved = {**dict(context), "locale": was.get("locale")}  # the session's languages stay what it opened with
        if "address" not in moved and "address" in was:
            moved["address"] = was["address"]
        request = TurnRequest.model_validate({**body, "context": moved, "trigger": "open"})
        session.request = request
        _in_view(session.outputs, request.context)
        return {"voice_session_id": voice_session_id, "note": _context_note(request.context)}

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

    # -- one conversation with the typed turns -------------------------------------------------------------------

    def _refresh(self, session: VoiceSession) -> None:
        """The open offer and what was just sent, as the conversation holds them now."""

        state = self.runtime.sessions.get(session.agent_session_id, session.user_key)
        if state is not None:
            session.outputs.pending = state.live_pending()
            session.outputs.settled = frozenset(done for done, _ in state.settled)
            session.outputs.recent_runs = state.recent_runs()

    def _remember(self, session: VoiceSession, *, heard: str | None, utterance: str | None, events: list[Event],
                  words: list[tuple[str, str | None]]) -> None:
        """What the server saw of a spoken turn joins the conversation: the learner's words, the offer made or
        accepted, what ran, the word it was about. An utterance with an identity is one turn of the conversation,
        counted once however many calls it made (none, one or several), and its words are put in once."""

        actions = [e for e in events if e.name == "action"]
        offered = next((a for a in actions if not a.open), None)
        outputs = session.outputs
        live = outputs.pending
        settle = None if live is None or outputs.resolution is None else (
            COMPLETED if outputs.resolution == CONFIRM else CANCELLED)
        words += [(a.payload["text"], a.payload.get("lang")) for a in actions
                  if a.type in WORD_ACTIONS and isinstance(a.payload.get("text"), str)]
        same_offer = (offered is not None and live is not None
                      and action_key(offered.type, offered.payload) == action_key(live.action, live.payload))
        new_offer = (offered.type, offered.label, dict(offered.payload)) if offered is not None and not same_offer else None
        ran = tuple(action_key(a.type, a.payload) for a in actions if a.open)
        ref = session.ref(utterance) if utterance is not None else None
        count_turn = ref is not None and ref not in session.counted
        put_words = heard is not None and (ref is None or ref not in session.texted)
        if not (count_turn or put_words or actions or words):
            return
        if ref is not None:
            session.counted.add(ref)
            if put_words:
                session.texted.add(ref)
        limits = self.runtime.limits

        def change(state):
            if count_turn:  # a spoken utterance is a turn of the conversation, as a typed one is
                state = state.with_turn()
            if put_words:
                state = state.with_spoken((ConversationTurn("user", heard, ref),), limits)
            state = state.with_outcome(live=live, settle=settle, new_offer=new_offer, ran=ran)
            return state.with_focus(focus_after(state.focus, word=words[-1] if words else None))

        self.runtime.sessions.update(session.agent_session_id, session.user_key, change)

    def utterance_turn(self, voice_session_id: str, utterance: str | None, heard: str | None,
                       learner: LearnerScope) -> dict[str, Any] | None:
        """The boundary of one spoken utterance, from the client (the vendor's turn end): it is counted as a turn of
        the conversation if no tool call has counted it already, and its words are put in if they are not yet. The
        identity is the client's own sequence number for the session - never the words - so the same words said twice
        are two turns, and one utterance is one turn however many tools it called."""

        session = self.sessions.get(voice_session_id, learner.user_key)
        utterance = _utterance_id(utterance)
        if session is None:
            return None
        if utterance is None:
            return {"voice_session_id": voice_session_id, "counted": False}
        heard = heard.strip()[:2000] if isinstance(heard, str) and heard.strip() else None
        self._refresh(session)
        fresh = session.ref(utterance) not in session.counted
        self._remember(session, heard=heard, utterance=utterance, events=[], words=[])
        return {"voice_session_id": voice_session_id, "counted": fresh}

    def _flush_transcript(self, session: VoiceSession, transcript: Any) -> None:
        """The client's transcript of the session, if it sent one (optional, additive): the turns it holds that
        the server did not already hear. Bounded, and anything that is not a turn is ignored."""

        if not isinstance(transcript, list):
            return
        turns: list[ConversationTurn] = []
        for item in transcript[:TRANSCRIPT_MAX_TURNS]:
            role = item.get("role") if isinstance(item, Mapping) else None
            text = item.get("text") if isinstance(item, Mapping) else None
            if role not in ("user", "assistant") or not isinstance(text, str) or not text.strip():
                continue
            utterance = _utterance_id(item.get("utterance"))
            turns.append(ConversationTurn(role, text.strip()[:TRANSCRIPT_TURN_CHARS],
                                          session.ref(utterance) if utterance is not None else None))
        if turns:
            limits, counted = self.runtime.limits, frozenset(session.counted)
            self.runtime.sessions.update(session.agent_session_id, session.user_key,
                                         lambda state: state.with_transcript(tuple(turns), limits, counted))

    # -- close ---------------------------------------------------------------------------------------------------

    def end(self, voice_session_id: str, learner: LearnerScope, transcript: Any = None) -> dict[str, Any] | None:
        """The learner stops: no further chunk is minted for the session. Nothing is refunded and nothing more is owed -
        every chunk was charged whole when its token was minted (D-16T), and the server never saw the vendor socket, so
        the end changes what the learner may ask for next, not what they hold. `seconds` is the wall-clock time from
        the first token to now, at most the seconds minted: what the client sees, not what was charged."""

        session = self.sessions.close(voice_session_id, learner.user_key)
        if session is None:
            return None
        with session.lock:
            session.ended = True
        try:
            self._flush_transcript(session, transcript)
        finally:
            seconds = round(min(float(session.minted_seconds), max(0.0, self.sessions.clock() - session.opened)), 1)
        self._sweep()
        return {"voice_session_id": voice_session_id, "seconds": seconds}

    def _sweep(self) -> None:
        """Forget the sessions of this process whose newest token is dead (they owe nothing, see `expired`)."""

        self.sessions.expired()
