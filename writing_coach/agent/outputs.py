"""How the model shapes a reply beyond its text: the reply tools.

The model streams its answer as text (segment 0, in the support language). The
rest of a contract reply - an action, a suggestion, the evidence a claim rests
on, the voice style, a reference line to hear - it asks for through these
tools. They read nothing and change nothing: the server checks each request
against the contract and the client's declaration, answers the model with what
it accepted, and emits the accepted outputs after the text (contract §12
order: segments, then actions and suggestions).

Every label is server copy in the interface layer, never model text (D-080,
human ruling 2026-09-27). An action the client did not declare is refused and
the model is told to say it in words (contract §3.1).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from pydantic import ValidationError

from writing_coach.agent import learner_copy
from writing_coach.agent.contract import ACTIONS, SURFACES, VOICE_STYLES
from writing_coach.agent.events import ActionEvent, SuggestionEvent, make_action
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


def reply_tool_specs(client: ClientInfo, target: str) -> tuple[ProviderToolSpec, ...]:
    """The reply tools this client can use. No actions declared, no action tool."""

    specs = [
        ProviderToolSpec(
            SUGGEST_NEXT,
            "Offer the learner a next question to ask. Use sparingly, at most three.",
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
    allowed = sorted(client.allowed_actions)
    if allowed:
        specs.insert(
            0,
            ProviderToolSpec(
                PROPOSE_ACTION,
                "Offer a button the app can run. navigate needs 'intent' plus that intent's ids; "
                f"navigable intents: {', '.join(sorted(client.allowed_intents)) or 'none'}.",
                {
                    "type": "object",
                    "properties": {"type": {"type": "string", "enum": allowed}, "payload": {"type": "object"}},
                    "required": ["type", "payload"],
                    "additionalProperties": False,
                },
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
    actions: list[ActionEvent] = field(default_factory=list)
    suggestions: list[SuggestionEvent] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    references: list[tuple[str, str]] = field(default_factory=list)
    voice_style: str = "neutral_explain"

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

    def _label(self, key: str) -> str:
        return learner_copy.text(key, interface=self.interface, support=self.support)[1]

    def _action(self, args: Mapping[str, Any]) -> str:
        action_type, payload = args.get("type"), args.get("payload")
        if len(self.actions) >= MAX_ACTIONS:
            return "refused: at most three actions"
        if action_type not in ACTIONS or not isinstance(payload, Mapping):
            return "refused: unknown action"
        intent = payload.get("intent") if action_type == "navigate" else None
        allowed = action_type in self.client.allowed_actions and (
            action_type != "navigate" or intent in self.client.allowed_intents
        )
        if not allowed:
            return "refused: this app cannot do that here; say it in words instead"
        if action_type == "save_word" and "lang" in payload and payload["lang"] != self.target:
            return f"refused: a word is saved in the language being learned ({self.target})"
        key = action_label_key(action_type, payload)
        if key not in learner_copy.CATALOG:
            return "refused: unknown action"
        try:
            action = make_action(f"a{len(self.actions) + 1}", action_type, self._label(key), dict(payload))
        except (ValidationError, ValueError) as exc:
            return f"refused: payload does not fit {action_type} ({_first_error(exc)})"
        self.actions.append(action)
        return f"accepted: {action.id}"

    def _suggest(self, args: Mapping[str, Any]) -> str:
        intent = args.get("intent")
        if intent not in PROMPT_INTENTS:
            return "refused: unknown intent"
        if len(self.suggestions) >= MAX_SUGGESTIONS or any(s.intent == intent for s in self.suggestions):
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
