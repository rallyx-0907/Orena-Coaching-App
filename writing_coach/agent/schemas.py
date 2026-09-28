"""The turn request, contract §3, as the server validates it.

Unknown request fields are ignored rather than refused: a client one contract
version ahead must still work against this server, and it only ever adds
optional fields (AGENT_CONTRACT_V2_PROPOSAL.md). For the same reason a surface
id this version does not know is kept but not recognised (`known_surface`), so
a newer client's surface degrades to "no surface" instead of failing the turn.
What the contract closes - locale codes per layer, activity type, selection and
note kinds, the coach-note budget - is enforced.

Version 2 adds the opening turn: `trigger: "open"` carries no message
(contract §3.2). A client that declared version 1 has no trigger; whatever it
sends there is read as a message turn, which needs a message.
"""

from __future__ import annotations

import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from writing_coach.agent.contract import (
    ACTIONS,
    ACTIVITY_TYPES,
    ADDRESS_NOTE_KIND,
    NOTE_KINDS,
    MAX_COACH_NOTES,
    MAX_COACH_NOTES_BYTES,
    SELECTED_ITEM_TYPES,
    SURFACES,
    TRIGGERS,
    negotiated_version,
)
from writing_coach.agent.locale import InternalLocale, UnsupportedLanguage, require_layer_language, to_internal

_ID = r"^[A-Za-z0-9._:\-]{1,128}$"
_SURFACE_SHAPE = r"^[a-z][a-z_]*(\.[a-z][a-z_]*)*$"
# An implementation ceiling against oversized bodies, not a contract rule: the
# contract sets no message length, and the real bound on a turn is the token
# budget (`AgentLimits.max_input_tokens_per_turn`). It sits above any essay a
# learner might paste.
MAX_MESSAGE_CHARS = 32_000


class _Incoming(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class ClientInfo(_Incoming):
    ui_version: str = Field(min_length=1, max_length=64)
    supported_actions: list[str] = Field(default_factory=list, max_length=64)
    supported_intents: list[str] = Field(default_factory=list, max_length=128)

    @property
    def allowed_actions(self) -> frozenset[str]:
        """Declared action types this contract knows; the rest are ignored."""

        return frozenset(self.supported_actions) & frozenset(ACTIONS)

    @property
    def allowed_intents(self) -> frozenset[str]:
        return frozenset(self.supported_intents) & frozenset(SURFACES)


class ContractLocale(_Incoming):
    interface: str
    support: str
    target: str
    content: str | None = None

    @model_validator(mode="after")
    def _layers(self) -> ContractLocale:
        try:
            for layer in ("interface", "support", "target", "content"):
                value = getattr(self, layer)
                if value is not None:
                    require_layer_language(layer, value)
        except UnsupportedLanguage as exc:
            raise ValueError(str(exc)) from exc
        return self

    def internal(self) -> InternalLocale:
        return InternalLocale(
            interface=to_internal(self.interface),
            support=to_internal(self.support),
            target=to_internal(self.target),
            content=to_internal(self.content) if self.content is not None else None,
        )


class SelectedItem(_Incoming):
    """A word is `{text, lang}` (the product has no word ids); the others carry id and text."""

    type: str
    id: str | None = Field(default=None, pattern=_ID)
    text: str | None = Field(default=None, min_length=1, max_length=500)
    lang: str | None = None

    @field_validator("lang")
    @classmethod
    def _lang(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                require_layer_language("content", value)
            except UnsupportedLanguage as exc:
                raise ValueError(str(exc)) from exc
        return value

    @field_validator("type")
    @classmethod
    def _type(cls, value: str) -> str:
        if value not in SELECTED_ITEM_TYPES:
            raise ValueError(f"unknown selected_item.type {value!r}")
        return value

    @model_validator(mode="after")
    def _identified(self) -> SelectedItem:
        if self.id is None and self.text is None:
            raise ValueError("selected_item needs an id or a text")
        return self


class ClientEvidence(_Incoming):
    pitch_contour_ref: str | None = Field(default=None, max_length=256)


class AppContextSnapshot(_Incoming):
    """Where the learner is and what they have in view (contract §3 `context`)."""

    surface: str | None = Field(default=None, pattern=_SURFACE_SHAPE, max_length=64)
    activity_type: str | None = None
    locale: ContractLocale
    lesson_id: str | None = Field(default=None, pattern=_ID)
    content_id: str | None = Field(default=None, pattern=_ID)
    attempt_id: str | None = Field(default=None, pattern=_ID)
    take_ref: str | None = Field(default=None, pattern=_ID)
    essay_id: str | None = Field(default=None, pattern=_ID)
    selected_item: SelectedItem | None = None
    # §5.6: the learner's address, as raw data. It is checked - and falls back whole to the default - where it is
    # applied (agent/address.py), never refused here: a bad term costs the learner nothing but the default.
    address: dict | None = None
    client_evidence: ClientEvidence | None = None

    @field_validator("activity_type")
    @classmethod
    def _activity(cls, value: str | None) -> str | None:
        if value is not None and value not in ACTIVITY_TYPES:
            raise ValueError(f"unknown activity_type {value!r}")
        return value

    @property
    def known_surface(self) -> str | None:
        """The surface when this contract version knows it; otherwise None."""

        return self.surface if self.surface in SURFACES else None


class CoachNote(_Incoming):
    id: str = Field(pattern=_ID)
    kind: str
    text: str = Field(min_length=1, max_length=400)
    weight: float = Field(ge=0.0, le=1.0)
    last_reinforced: datetime
    expires_at: datetime | None = None
    address: dict[str, str] | None = None  # kind `address` only (§5.6)

    @field_validator("kind")
    @classmethod
    def _kind(cls, value: str) -> str:
        if value not in NOTE_KINDS:
            raise ValueError(f"unknown coach note kind {value!r}")
        return value

    @model_validator(mode="after")
    def _address(self) -> CoachNote:
        # Only an address note carries `address`. An address note that lacks it is accepted here and dropped by
        # TurnRequest (it never belongs in coach_notes): a device's stale note must not refuse the whole turn.
        if self.address is not None and self.kind != ADDRESS_NOTE_KIND:
            raise ValueError("only an address note carries `address`")
        return self


def coach_notes_bytes(notes: list[CoachNote]) -> int:
    payload = [note.model_dump(mode="json") for note in notes]
    return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


class TurnRequest(_Incoming):
    """`POST /api/agent/turn` body (contract §3)."""

    contract_version: int = Field(ge=1)
    session_id: str | None = Field(default=None, pattern=_ID)
    trigger: str = "message"
    message: str | None = Field(default=None, max_length=MAX_MESSAGE_CHARS)
    client: ClientInfo
    context: AppContextSnapshot
    coach_notes: list[CoachNote] = Field(default_factory=list, max_length=MAX_COACH_NOTES)

    @model_validator(mode="after")
    def _turn_kind(self) -> TurnRequest:
        if negotiated_version(self.contract_version) < 2:
            object.__setattr__(self, "trigger", "message")
        if self.trigger not in TRIGGERS:
            raise ValueError(f"unknown trigger {self.trigger!r}")
        if self.trigger == "message" and (self.message is None or not self.message.strip()):
            raise ValueError("a message turn needs a message")
        if self.trigger == "open" and self.message is not None:
            raise ValueError("an opening turn carries no message")
        return self

    @model_validator(mode="after")
    def _no_address_note(self) -> TurnRequest:
        # §3: the address note is never among coach_notes (it travels as context.address); one sent there is ignored.
        kept = [note for note in self.coach_notes if note.kind != ADDRESS_NOTE_KIND]
        if len(kept) != len(self.coach_notes):
            object.__setattr__(self, "coach_notes", kept)
        return self

    @model_validator(mode="after")
    def _notes_budget(self) -> TurnRequest:
        if coach_notes_bytes(self.coach_notes) > MAX_COACH_NOTES_BYTES:
            raise ValueError(f"coach_notes exceed {MAX_COACH_NOTES_BYTES} bytes")
        return self

    @property
    def version(self) -> int:
        return negotiated_version(self.contract_version)

    @property
    def opening(self) -> bool:
        return self.trigger == "open"
