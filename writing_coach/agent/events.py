"""Server → client events (contract §4-§7) and the stream that orders them.

Each event is a frozen model whose fields are exactly the contract's. The
`TurnStream` is the only way events leave the server, and it refuses what the
contract forbids: an event before `session` or after `done`/`error`, a delta
after its segment ended, a segment citing evidence not yet sent, an action the
client did not declare, a `navigate` to an intent the client does not have, a
risk other than the table's. Refusal raises `ContractViolation`; a caller asks
`allows_action` first and says the thing in words instead (contract §3.1).

Version 2 fields (`display`) never reach a client that declared version 1,
and neither do the actions and intents version 2 changed (contract §0).

Segments carry no citation field on the wire. A caller that states an error
passes the evidence ids it rests on as `cites`, and the stream checks that
each was already sent (contract §4 ordering; spec D10).
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from writing_coach.agent import learner_copy
from writing_coach.agent.contract import (
    ACTIONS,
    AUDIO_FORMATS,
    BUDGET_STATES,
    COLLECTION_SYSTEMS,
    DISPLAY_KINDS,
    ERROR_FALLBACKS,
    EVENT_NAMES,
    EVIDENCE_SOURCES,
    MAX_ACTION_LABEL_CHARS,
    MAX_DISPLAY_REASON_CHARS,
    MEMORY_OPS,
    SURFACES,
    TERMINAL_EVENTS,
    VOICE_ONLY_EVENTS,
    VOICE_STATES,
    VOICE_STYLES,
    WORD_ACTIONS,
    ActionRisk,
    actions_for_version,
    intents_for_version,
)
from writing_coach.agent.errors import ERROR_KINDS
from writing_coach.agent.locale import content_languages
from writing_coach.agent.schemas import ClientInfo, CoachNote

_ID = r"^[A-Za-z0-9._:\-]{1,128}$"
_INTENT = r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$"


class ContractViolation(RuntimeError):
    """The server was about to send something the contract does not allow."""


class ActionNotSupported(ContractViolation):
    """The action is valid, but this client did not declare it (contract §3.1)."""


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    name: ClassVar[str]

    def to_wire(self) -> dict[str, Any]:
        wire = self.model_dump(mode="json", by_alias=True)
        if "display" in wire:
            # §5.5: display and each of its fields are absent when there is none, never null.
            display = {key: value for key, value in (wire.pop("display") or {}).items() if value is not None}
            if display:
                wire["display"] = display
        return wire


class Display(BaseModel):
    """§5.5: title, kind, duration copied from a domain record; `reason` checkable."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    title: str | None = Field(default=None, min_length=1, max_length=120)
    kind: str | None = None
    duration_s: int | None = Field(default=None, ge=0)
    reason: str | None = Field(default=None, min_length=1, max_length=MAX_DISPLAY_REASON_CHARS)

    @field_validator("kind")
    @classmethod
    def _kind(cls, value: str | None) -> str | None:
        if value is not None and value not in DISPLAY_KINDS:
            raise ValueError(f"unknown display kind {value!r}")
        return value


def _lang(value: str) -> str:
    if value not in content_languages():
        raise ValueError(f"{value!r} is not a contract language code")
    return value


class SessionEvent(Event):
    name: ClassVar[str] = "session"
    session_id: str = Field(pattern=_ID)
    contract_version: int = Field(ge=1)


class SegmentDelta(Event):
    name: ClassVar[str] = "segment_delta"
    index: int = Field(ge=0)
    lang: str
    text_delta: str = Field(min_length=1)

    @field_validator("lang")
    @classmethod
    def _language(cls, value: str) -> str:
        return _lang(value)


class SegmentEnd(Event):
    name: ClassVar[str] = "segment_end"
    index: int = Field(ge=0)
    lang: str
    text: str = Field(min_length=1)
    voice_style: str

    @field_validator("lang")
    @classmethod
    def _language(cls, value: str) -> str:
        return _lang(value)

    @field_validator("voice_style")
    @classmethod
    def _style(cls, value: str) -> str:
        if value not in VOICE_STYLES:
            raise ValueError(f"unknown voice_style {value!r}")
        return value


class ToolCallEvent(Event):
    name: ClassVar[str] = "tool_call"
    tool: str = Field(alias="name", pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=1, max_length=80)


class ToolResultEvent(Event):
    name: ClassVar[str] = "tool_result"
    tool: str = Field(alias="name", pattern=r"^[a-z][a-z0-9_]*$")
    summary: str = Field(min_length=1, max_length=400)
    evidence_ids: list[str] = Field(default_factory=list)


class EvidenceEvent(Event):
    name: ClassVar[str] = "evidence"
    id: str = Field(pattern=_ID)
    source: str
    ref: dict[str, Any]
    excerpt: dict[str, Any]
    display: Display | None = None

    @field_validator("source")
    @classmethod
    def _source(cls, value: str) -> str:
        if value not in EVIDENCE_SOURCES:
            raise ValueError(f"unknown evidence source {value!r}")
        return value


class ActionEvent(Event):
    """Built with `make_action`, which takes the risk from the table (§7)."""

    name: ClassVar[str] = "action"
    id: str = Field(pattern=_ID)
    type: str
    label: str = Field(min_length=1, max_length=MAX_ACTION_LABEL_CHARS)
    payload: dict[str, Any]
    risk: ActionRisk
    display: Display | None = None

    @model_validator(mode="after")
    def _allowlisted(self) -> ActionEvent:
        spec = ACTIONS.get(self.type)
        if spec is None:
            raise ValueError(f"action {self.type!r} is not in the allowlist")
        if self.risk is not spec.risk:
            raise ValueError(f"action {self.type!r} has risk {spec.risk}, not {self.risk}")
        _check_payload(self.type, self.payload)
        return self


def _check_payload(action_type: str, payload: dict[str, Any]) -> None:
    keys = frozenset(payload)
    if action_type == "navigate":
        intent = payload.get("intent")
        if not isinstance(intent, str) or intent not in SURFACES:
            raise ValueError(f"navigate to unknown intent {intent!r}")
        expected = frozenset({"intent", *SURFACES[intent]})
        if keys != expected:
            raise ValueError(f"navigate {intent!r} needs exactly {sorted(expected)}")
    else:
        spec = ACTIONS[action_type]
        if not any(shape.accepts(keys) for shape in spec.shapes):
            raise ValueError(f"payload keys {sorted(keys)} do not fit {action_type!r}")
        for key, allowed in spec.values.items():
            if key in payload and payload[key] not in allowed:
                raise ValueError(f"{action_type}.{key} must be one of {sorted(allowed)}")
    if action_type == "start_review":
        word = {"text", "lang"} <= keys
        if (payload.get("scope") == "word") != word:
            raise ValueError("start_review names a word exactly when its scope is 'word'")
    if action_type == "start_targeted_drill":
        items = payload.get("item_ids")
        if not isinstance(items, list) or not items or not all(isinstance(i, str) and i for i in items):
            raise ValueError("start_targeted_drill.item_ids must be a non-empty list of ids")
    if action_type == "add_word_to_collection" and "target" in payload:
        target = payload["target"]
        if (
            not isinstance(target, dict)
            or set(target) != {"system", "id"}
            or target["system"] not in COLLECTION_SYSTEMS
            or not isinstance(target["id"], str)
            or not target["id"]
        ):
            raise ValueError("add_word_to_collection.target is {system: deck | library, id}")
    if "lang" in payload:
        _lang(payload["lang"])
    for key, value in payload.items():
        if key in {"item_ids", "target"}:
            continue
        if not isinstance(value, str) or not value:
            raise ValueError(f"{action_type}.{key} must be a non-empty string")
    if action_type in WORD_ACTIONS and len(payload.get("text", "")) > 120:
        raise ValueError(f"{action_type}.text is a word or phrase")


def make_action(
    action_id: str, action_type: str, label: str, payload: dict[str, Any], *, display: Display | None = None
) -> ActionEvent:
    spec = ACTIONS.get(action_type)
    if spec is None:
        raise ContractViolation(f"action {action_type!r} is not in the allowlist")
    return ActionEvent(id=action_id, type=action_type, label=label, payload=payload, risk=spec.risk, display=display)


class SuggestionEvent(Event):
    name: ClassVar[str] = "suggestion"
    label: str = Field(min_length=1, max_length=80)
    intent: str = Field(pattern=_INTENT, max_length=64)


class MemoryUpdateEvent(Event):
    name: ClassVar[str] = "memory_update"
    op: str
    note: dict[str, Any]

    @model_validator(mode="after")
    def _shape(self) -> MemoryUpdateEvent:
        if self.op not in MEMORY_OPS:
            raise ValueError(f"unknown memory op {self.op!r}")
        if self.op == "remove":
            if set(self.note) != {"id"}:
                raise ValueError("remove carries only the note id")
        else:
            CoachNote.model_validate(self.note)
        return self


class VoiceStateEvent(Event):
    name: ClassVar[str] = "voice_state"
    state: str

    @field_validator("state")
    @classmethod
    def _state(cls, value: str) -> str:
        if value not in VOICE_STATES:
            raise ValueError(f"unknown voice state {value!r}")
        return value


class AudioChunkEvent(Event):
    name: ClassVar[str] = "audio_chunk"
    index: int = Field(ge=0)
    format: str
    data_base64: str = Field(min_length=1)

    @field_validator("format")
    @classmethod
    def _format(cls, value: str) -> str:
        if value not in AUDIO_FORMATS:
            raise ValueError(f"unknown audio format {value!r}")
        return value


class MeteredEvent(Event):
    name: ClassVar[str] = "metered"
    turn_ordinal: int = Field(ge=1)
    budget_state: str

    @field_validator("budget_state")
    @classmethod
    def _budget(cls, value: str) -> str:
        if value not in BUDGET_STATES:
            raise ValueError(f"unknown budget state {value!r}")
        return value


class ErrorEvent(Event):
    """Built with `error_event`, which takes the message from layered copy."""

    name: ClassVar[str] = "error"
    error_class: str = Field(alias="class")
    message: str = Field(min_length=1)
    fallback: str

    @field_validator("fallback")
    @classmethod
    def _fallback(cls, value: str) -> str:
        if value not in ERROR_FALLBACKS:
            raise ValueError(f"unknown fallback {value!r}")
        return value

    @model_validator(mode="after")
    def _known_kind(self) -> ErrorEvent:
        # The fallback belongs to the kind, never to the caller: a failed voice
        # session continues in text and is never retried on another vendor (R2).
        kind = ERROR_KINDS.get(self.error_class)
        if kind is None:
            raise ValueError(f"unknown error class {self.error_class!r}")
        if self.fallback != kind.fallback:
            raise ValueError(f"{self.error_class} falls back to {kind.fallback}, not {self.fallback}")
        return self


def error_event(error_class: str, *, interface: str, support: str) -> ErrorEvent:
    kind = ERROR_KINDS[error_class]
    _, message = learner_copy.text(kind.copy_key, interface=interface, support=support)
    return ErrorEvent(error_class=kind.error_class, message=message, fallback=kind.fallback)


class Usage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class DoneEvent(Event):
    name: ClassVar[str] = "done"
    usage: Usage
    trace_id: str = Field(pattern=_ID)


EVENT_TYPES: tuple[type[Event], ...] = (
    SessionEvent,
    SegmentDelta,
    SegmentEnd,
    ToolCallEvent,
    ToolResultEvent,
    EvidenceEvent,
    ActionEvent,
    SuggestionEvent,
    MemoryUpdateEvent,
    VoiceStateEvent,
    AudioChunkEvent,
    MeteredEvent,
    ErrorEvent,
    DoneEvent,
)
if {event.name for event in EVENT_TYPES} != EVENT_NAMES:
    raise RuntimeError("event models and the contract's event names differ")


def sse_frame(event: Event) -> str:
    """`event: <name>\\ndata: <json>\\n\\n` (contract §2)."""

    data = json.dumps(event.to_wire(), ensure_ascii=False, separators=(",", ":"))
    return f"event: {event.name}\ndata: {data}\n\n"


class TurnStream:
    """One turn's events, in an order the contract allows."""

    def __init__(self, *, version: int, client: ClientInfo, mode: Literal["text", "voice"] = "text") -> None:
        self.version = version
        self.client = client
        self.mode = mode
        # What this client may be sent: what it declared, within what its version has.
        self.allowed_actions = client.allowed_actions & actions_for_version(version)
        self.allowed_intents = client.allowed_intents & intents_for_version(version)
        self.events: list[Event] = []
        self._segments: dict[int, dict[str, Any]] = {}
        self._ended: set[int] = set()
        self._evidence: set[str] = set()
        self._cited_by_tools: set[str] = set()
        self._action_ids: set[str] = set()

    @property
    def finished(self) -> bool:
        return bool(self.events) and self.events[-1].name in TERMINAL_EVENTS

    def allows_action(self, action_type: str, intent: str | None = None) -> bool:
        if action_type not in self.allowed_actions:
            return False
        if action_type == "navigate":
            return intent in self.allowed_intents
        return True

    def emit(self, event: Event, *, cites: Iterable[str] = ()) -> Event:
        cites = tuple(cites)
        if self.finished:
            raise ContractViolation(f"{event.name} after the stream ended")
        if not self.events and event.name != "session":
            raise ContractViolation("the first event must be session")
        if self.events and event.name == "session":
            raise ContractViolation("session is sent once, first")
        if event.name in VOICE_ONLY_EVENTS and self.mode != "voice":
            raise ContractViolation(f"{event.name} is voice only")
        if cites and event.name != "segment_end":
            raise ContractViolation("only a segment cites evidence")
        if self.version < 2 and getattr(event, "display", None) is not None:
            event = event.model_copy(update={"display": None})  # a version-2 field
        check = getattr(self, f"_check_{event.name}", None)
        if check is not None:
            check(event, cites)
        self.events.append(event)
        return event

    def frames(self) -> Iterator[str]:
        for event in self.events:
            yield sse_frame(event)

    # --- per-event rules ---------------------------------------------------

    def _check_session(self, event: SessionEvent, cites: tuple[str, ...]) -> None:
        if event.contract_version != self.version:
            raise ContractViolation("session must carry the negotiated contract version")

    def _open_segment(self, index: int, lang: str) -> dict[str, Any]:
        if index in self._ended:
            raise ContractViolation(f"segment {index} already ended")
        segment = self._segments.get(index)
        if segment is None:
            expected = max(self._segments, default=-1) + 1
            if index != expected:
                raise ContractViolation(f"segment {index} opened before segment {expected}")
            segment = self._segments[index] = {"lang": lang, "text": []}
        elif segment["lang"] != lang:
            raise ContractViolation(f"segment {index} changed language")
        return segment

    def _check_segment_delta(self, event: SegmentDelta, cites: tuple[str, ...]) -> None:
        self._open_segment(event.index, event.lang)["text"].append(event.text_delta)

    def _check_segment_end(self, event: SegmentEnd, cites: tuple[str, ...]) -> None:
        segment = self._open_segment(event.index, event.lang)
        if segment["text"] and "".join(segment["text"]) != event.text:
            raise ContractViolation(f"segment {event.index} text differs from its deltas")
        missing = [evidence for evidence in cites if evidence not in self._evidence]
        if missing:
            raise ContractViolation(f"segment {event.index} cites evidence not yet sent: {missing}")
        self._ended.add(event.index)

    def _check_tool_result(self, event: ToolResultEvent, cites: tuple[str, ...]) -> None:
        self._cited_by_tools.update(event.evidence_ids)

    def _check_evidence(self, event: EvidenceEvent, cites: tuple[str, ...]) -> None:
        if event.id in self._evidence:
            raise ContractViolation(f"evidence {event.id} sent twice")
        self._evidence.add(event.id)

    def _check_action(self, event: ActionEvent, cites: tuple[str, ...]) -> None:
        intent = event.payload.get("intent") if event.type == "navigate" else None
        if not self.allows_action(event.type, intent):
            raise ActionNotSupported(f"client does not support {event.type} {intent or ''}".strip())
        if event.id in self._action_ids:
            raise ContractViolation(f"action {event.id} sent twice")
        self._action_ids.add(event.id)

    def _check_done(self, event: DoneEvent, cites: tuple[str, ...]) -> None:
        open_segments = set(self._segments) - self._ended
        if open_segments:
            raise ContractViolation(f"segments never ended: {sorted(open_segments)}")
        unsent = self._cited_by_tools - self._evidence
        if unsent:
            raise ContractViolation(f"tool results name evidence never sent: {sorted(unsent)}")
