"""How the model shapes a reply beyond its text: the reply tools.

The model streams its answer as text (segment 0, in the support language). The
rest of a contract reply - an action, a suggestion, the evidence a claim rests
on, the voice style, a reference line to hear - it asks for through these
tools. They read nothing and change nothing: the server checks each request
against the contract and the client's declaration, answers the model with what
it accepted, and emits the accepted outputs after the text (contract §12
order: segments, then actions and suggestions).

Every label is server copy in the interface layer, never model text (D-080,
human ruling 2026-09-27). An action the client did not declare, or that its
contract version does not have, is refused and the model is told to say it in
words (contract §3.1).

Contract version 2 (§7): an id in a payload comes from what a tool read or what
the request named - never from generation - and a `take_ref` only from the
request. A word action names the word in the language being learned. An
opening turn offers at most two actions, all LOW. `display.reason` is the
model's one checkable line; `display.kind` is the domain of the record the
action's id was read from, and absent when there is none.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from pydantic import ValidationError

from writing_coach.agent import learner_copy
from writing_coach.agent.contract import (
    ACTIONS,
    CONTRACT_VERSION,
    MAX_DISPLAY_REASON_CHARS,
    OPENING_MAX_ACTIONS,
    OPENING_MAX_SUGGESTIONS,
    READ_ID_KEYS,
    SURFACES,
    VOICE_STYLES,
    ActionRisk,
    actions_for_version,
    intents_for_version,
)
from writing_coach.agent.events import ActionEvent, Display, SuggestionEvent, make_action
from writing_coach.agent.provider import ProviderToolSpec
from writing_coach.agent.schemas import ClientInfo

# Prompt intents (contract §4 `suggestion.intent`): what a suggestion asks,
# not where it goes. The contract leaves the vocabulary to the server; it is
# this table, and none of its ids is a surface id.
PROMPT_INTENTS: Mapping[str, str] = MappingProxyType(
    {
        "review_due": "suggest.review_due",
        "writing_feedback": "suggest.writing_feedback",
        "app_help": "suggest.app_help",
    }
)
if set(PROMPT_INTENTS) & set(SURFACES):
    raise RuntimeError("a prompt intent may not be a navigation intent")

# The domain a record belongs to, by the evidence source a tool read it as (§5.5 `kind`).
KIND_BY_SOURCE: Mapping[str, str] = MappingProxyType(
    {
        "speech.pronunciation": "speaking",
        "writing.evaluation": "writing",
        "reading.comprehension": "reading",
        "listening.dictation": "listening",
        "vocabulary.review": "vocabulary",
        "grammar.catalog": "grammar",
    }
)
# Keys whose values in a tool result are ids an action may name.
_ID_KEYS = READ_ID_KEYS | {"id", "lesson_id", "deck_id", "collection_id"}

REPLY_STYLES = tuple(sorted(VOICE_STYLES - {"reference"}))
MAX_ACTIONS = 3
MAX_SUGGESTIONS = 3
MAX_REFERENCES = 3
MAX_REFERENCE_CHARS = 40

PROPOSE_ACTION = "propose_action"
SUGGEST_NEXT = "suggest_next"
CITE_EVIDENCE = "cite_evidence"
SET_VOICE_STYLE = "set_voice_style"
ADD_REFERENCE = "add_reference"
REPLY_TOOL_NAMES = frozenset({PROPOSE_ACTION, SUGGEST_NEXT, CITE_EVIDENCE, SET_VOICE_STYLE, ADD_REFERENCE})


def action_label_key(action_type: str, payload: Mapping[str, Any]) -> str:
    if action_type == "navigate":
        return f"navigate.{payload.get('intent')}"
    return f"action.{action_type}"


def opening_suggestions(surface: str | None) -> tuple[str, ...]:
    """The ways forward an opening turn offers when the model named none (§3.2: at least one)."""

    if surface is None or surface in {"home", "orena.home"} or surface.startswith("vocabulary."):
        return ("review_due", "app_help")
    if surface.startswith("writing."):
        return ("writing_feedback", "app_help")
    return ("app_help",)


def reply_tool_specs(
    client: ClientInfo, target: str, *, version: int = CONTRACT_VERSION
) -> tuple[ProviderToolSpec, ...]:
    """The reply tools this client can use. No actions declared, no action tool."""

    specs = [
        ProviderToolSpec(
            SUGGEST_NEXT,
            "Offer the learner a next question to ask. Use sparingly.",
            {
                "type": "object",
                "properties": {"intent": {"type": "string", "enum": sorted(PROMPT_INTENTS)}},
                "required": ["intent"],
                "additionalProperties": False,
            },
        ),
        ProviderToolSpec(
            CITE_EVIDENCE,
            "Name the evidence ids your answer rests on. Required whenever you say the learner made an error.",
            {
                "type": "object",
                "properties": {"evidence_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1}},
                "required": ["evidence_ids"],
                "additionalProperties": False,
            },
        ),
        ProviderToolSpec(
            SET_VOICE_STYLE,
            "How your answer should sound when spoken.",
            {
                "type": "object",
                "properties": {"voice_style": {"type": "string", "enum": list(REPLY_STYLES)}},
                "required": ["voice_style"],
                "additionalProperties": False,
            },
        ),
        ProviderToolSpec(
            ADD_REFERENCE,
            "Add a short line in the language being learned for the learner to hear as a model.",
            {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "maxLength": MAX_REFERENCE_CHARS},
                    "lang": {"type": "string", "enum": [target]},
                },
                "required": ["text", "lang"],
                "additionalProperties": False,
            },
        ),
    ]
    allowed = sorted(client.allowed_actions & actions_for_version(version))
    if allowed:
        intents = sorted(client.allowed_intents & intents_for_version(version))
        properties: dict[str, Any] = {"type": {"type": "string", "enum": allowed}, "payload": {"type": "object"}}
        if version >= 2:
            properties["reason"] = {"type": "string", "maxLength": MAX_DISPLAY_REASON_CHARS}
        specs.insert(
            0,
            ProviderToolSpec(
                PROPOSE_ACTION,
                "Offer a button the app can run. Ids in the payload must come from a tool result or the "
                "context, never invented; a word is {text, lang} in the language being learned. navigate "
                f"needs 'intent' plus that intent's ids; navigable intents: {', '.join(intents) or 'none'}."
                + (" 'reason' is one short, checkable line on why, in the support language." if version >= 2 else ""),
                {"type": "object", "properties": properties, "required": ["type", "payload"], "additionalProperties": False},
            ),
        )
    return tuple(specs)


@dataclass
class ReplyOutputs:
    """What the model asked for, as accepted by the server."""

    client: ClientInfo
    interface: str
    support: str
    target: str
    version: int = CONTRACT_VERSION
    opening: bool = False
    take_ref: str | None = None
    known_ids: dict[str, str | None] = field(default_factory=dict)  # id -> domain kind of its record
    actions: list[ActionEvent] = field(default_factory=list)
    suggestions: list[SuggestionEvent] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    references: list[tuple[str, str]] = field(default_factory=list)
    voice_style: str = "neutral_explain"

    # --- ids the turn has seen ------------------------------------------------

    def learn_ids(self, ids: Iterable[object], *, kind: str | None = None) -> None:
        for value in ids:
            if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value):
                key = str(value)
                if self.known_ids.get(key) is None:
                    self.known_ids[key] = kind

    def learn_from(self, value: Any, *, kind: str | None = None) -> None:
        """Every id-keyed value anywhere in a tool's data or evidence reference."""

        if isinstance(value, Mapping):
            for key, item in value.items():
                if str(key) in _ID_KEYS and not isinstance(item, (Mapping, list, tuple)):
                    self.learn_ids((item,), kind=kind)
                else:
                    self.learn_from(item, kind=kind)
        elif isinstance(value, (list, tuple)):
            for item in value:
                self.learn_from(item, kind=kind)

    # --- the reply tools -------------------------------------------------------

    def handle(self, name: str, args: Mapping[str, Any], *, known_evidence: frozenset[str]) -> str:
        """Apply one reply-tool call; return what to tell the model."""

        if not isinstance(args, Mapping):
            return "refused: arguments must be an object"
        if name == CITE_EVIDENCE:
            return self._cite(args, known_evidence)
        handlers = {
            PROPOSE_ACTION: self._action,
            SUGGEST_NEXT: self._suggest,
            SET_VOICE_STYLE: self._style,
            ADD_REFERENCE: self._reference,
        }
        return handlers[name](args)

    def suggest(self, intent: str) -> bool:
        return self._suggest({"intent": intent}) == "accepted"

    def _label(self, key: str) -> str:
        return learner_copy.text(key, interface=self.interface, support=self.support)[1]

    def _action(self, args: Mapping[str, Any]) -> str:
        action_type, payload = args.get("type"), args.get("payload")
        limit = OPENING_MAX_ACTIONS if self.opening else MAX_ACTIONS
        if len(self.actions) >= limit:
            return f"refused: at most {limit} actions"
        if action_type not in ACTIONS or not isinstance(payload, Mapping):
            return "refused: unknown action"
        payload = dict(payload)
        intent = payload.get("intent") if action_type == "navigate" else None
        allowed = action_type in (self.client.allowed_actions & actions_for_version(self.version)) and (
            action_type != "navigate" or intent in (self.client.allowed_intents & intents_for_version(self.version))
        )
        if not allowed:
            return "refused: this app cannot do that here; say it in words instead"
        if self.opening and ACTIONS[action_type].risk is not ActionRisk.LOW:
            return "refused: an opening turn offers only actions that need no confirmation"
        refusal = self._provenance(action_type, payload)
        if refusal:
            return refusal
        key = action_label_key(action_type, payload)
        if key not in learner_copy.CATALOG:
            return "refused: unknown action"
        try:
            action = make_action(
                f"a{len(self.actions) + 1}", action_type, self._label(key), payload, display=self._display(args, payload)
            )
        except (ValidationError, ValueError) as exc:
            return f"refused: payload does not fit {action_type} ({_first_error(exc)})"
        self.actions.append(action)
        return f"accepted: {action.id}"

    def _provenance(self, action_type: str, payload: Mapping[str, Any]) -> str | None:
        """None when every id and word in the payload is one the turn may name."""

        for key in READ_ID_KEYS & set(payload):
            if str(payload[key]) not in self.known_ids:
                return f"refused: {key} must come from a tool result or the context, never be invented"
        target = payload.get("target")
        if isinstance(target, Mapping) and str(target.get("id")) not in self.known_ids:
            return "refused: target.id must come from a tool result, never be invented"
        items = payload.get("item_ids")
        if isinstance(items, list) and any(str(item) not in self.known_ids for item in items):
            return "refused: item_ids must come from a tool result or the context"
        if "take_ref" in payload and (self.take_ref is None or payload["take_ref"] != self.take_ref):
            return "refused: take_ref only as the client sent it"
        if "lang" in payload and payload["lang"] != self.target:
            return f"refused: a word is named in the language being learned ({self.target})"
        return None

    def _display(self, args: Mapping[str, Any], payload: Mapping[str, Any]) -> Display | None:
        if self.version < 2:
            return None
        reason = args.get("reason")
        reason = reason.strip() if isinstance(reason, str) and reason.strip() else None
        if reason is not None and len(reason) > MAX_DISPLAY_REASON_CHARS:
            reason = None  # an over-long reason is dropped, not cut mid-thought
        kind = None
        for key in ("essay_id", "content_id", "grammar_id"):
            if key in payload:
                kind = self.known_ids.get(str(payload[key]))
                break
        target = payload.get("target")
        if kind is None and isinstance(target, Mapping):
            kind = self.known_ids.get(str(target.get("id")))
        if reason is None and kind is None:
            return None
        return Display(kind=kind, reason=reason)

    def _suggest(self, args: Mapping[str, Any]) -> str:
        intent = args.get("intent")
        if intent not in PROMPT_INTENTS:
            return "refused: unknown intent"
        limit = OPENING_MAX_SUGGESTIONS if self.opening else MAX_SUGGESTIONS
        if len(self.suggestions) >= limit or any(s.intent == intent for s in self.suggestions):
            return "refused: already suggested"
        self.suggestions.append(SuggestionEvent(label=self._label(PROMPT_INTENTS[intent]), intent=intent))
        return "accepted"

    def _cite(self, args: Mapping[str, Any], known_evidence: frozenset[str]) -> str:
        ids = args.get("evidence_ids")
        if not isinstance(ids, list) or not ids:
            return "refused: evidence_ids must be a non-empty list"
        unknown = [i for i in ids if i not in known_evidence]
        if unknown:
            return f"refused: no such evidence {unknown}; cite only ids a tool returned"
        for evidence_id in ids:
            if evidence_id not in self.citations:
                self.citations.append(evidence_id)
        return "accepted"

    def _style(self, args: Mapping[str, Any]) -> str:
        style = args.get("voice_style")
        if style not in REPLY_STYLES:
            return "refused: unknown voice style"
        self.voice_style = style
        return "accepted"

    def _reference(self, args: Mapping[str, Any]) -> str:
        text, lang = args.get("text"), args.get("lang")
        if lang != self.target or not isinstance(text, str) or not 0 < len(text.strip()) <= MAX_REFERENCE_CHARS:
            return f"refused: a reference is up to {MAX_REFERENCE_CHARS} characters in {self.target}"
        if len(self.references) >= MAX_REFERENCES:
            return "refused: at most three references"
        self.references.append((lang, text.strip()))
        return "accepted"


def _first_error(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        errors = exc.errors()
        return str(errors[0].get("msg", "invalid")) if errors else "invalid"
    return str(exc)
