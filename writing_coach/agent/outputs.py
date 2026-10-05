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
    COACH_NOTE_KINDS,
    CONTRACT_VERSION,
    MAX_DISPLAY_REASON_CHARS,
    OPENING_MAX_ACTIONS,
    OPENING_MAX_SUGGESTIONS,
    PROMPT_NAMESPACE,
    READ_ID_KEYS,
    SURFACES,
    VOICE_STYLES,
    ActionRisk,
    actions_for_version,
    intents_for_version,
)
import secrets
from datetime import UTC, datetime

from writing_coach.agent.address import (
    ADDRESS_VERSION,
    CASUAL,
    GENDERED,
    address_note,
    explicit_request,
    used_by_learner,
    valid_term,
)
from writing_coach.agent.events import ActionEvent, Display, MemoryUpdateEvent, SuggestionEvent, make_action
from writing_coach.agent.notes import FORGET, asks_to_remember, confirmed_note, same_note
from writing_coach.agent.provider import ProviderToolSpec
from writing_coach.agent.schemas import ClientInfo

# Prompt intents (contract §4 `suggestion.intent`, v3): what a suggestion asks,
# not where it goes, in the `prompt.` namespace. The contract leaves the
# vocabulary to the server; it is this table, each id keyed to its label copy.
PROMPT_INTENTS: Mapping[str, str] = MappingProxyType(
    {
        "prompt.review_due": "prompt.review_due",
        "prompt.writing_feedback": "prompt.writing_feedback",
        "prompt.app_help": "prompt.app_help",
    }
)
if set(PROMPT_INTENTS) & set(SURFACES) or not all(i.startswith(PROMPT_NAMESPACE) for i in PROMPT_INTENTS):
    raise RuntimeError("a prompt intent is in the prompt. namespace and is never a navigation intent")
# The button that confirms a note asked back (agent/turn.py): the server's alone, never offered to the model.
KEEP_NOTE_INTENT = "prompt.keep_note"
if KEEP_NOTE_INTENT in PROMPT_INTENTS or KEEP_NOTE_INTENT in SURFACES:
    raise RuntimeError("the keep-note button is the server's, and a prompt intent")
# The ways forward when Orena is opened on a selection (UX review LEX-008), by what was selected; the server's own,
# each keyed to its label copy (agent/learner_copy.py). A word, a sentence, or anything else selected.
SELECTION_PROMPTS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "word": ("prompt.word_meaning", "prompt.word_usage"),
        "sentence": ("prompt.sentence_meaning", "prompt.sentence_grammar"),
        "item": ("prompt.explain_selection",),
    }
)
if any(i in SURFACES or not i.startswith(PROMPT_NAMESPACE) for v in SELECTION_PROMPTS.values() for i in v):
    raise RuntimeError("a selection prompt is a prompt intent, never a navigation intent")

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
# Keys whose values in a tool result are ids an action may name - each only
# under the same key it was read as (contract §7): an essay id is never a
# grammar id, however equal the two strings are.
_ID_KEYS = READ_ID_KEYS | {"lesson_id", "attempt_id", "deck_id", "collection_id"}
# `target.system` -> the key a collection id must have been read as.
TARGET_ID_KEYS: Mapping[str, str] = MappingProxyType({"deck": "deck_id", "library": "collection_id"})

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
SET_ADDRESS = "set_address"
OFFER_ADDRESS = "offer_address"
REMEMBER_NOTE = "remember_note"
FORGET_NOTE = "forget_note"
REPLY_TOOL_NAMES = frozenset(
    {
        PROPOSE_ACTION, SUGGEST_NEXT, CITE_EVIDENCE, SET_VOICE_STYLE, ADD_REFERENCE, SET_ADDRESS, OFFER_ADDRESS,
        REMEMBER_NOTE, FORGET_NOTE,
    }
)  # fmt: skip
MAX_NOTE_CHARS = 200
MAX_NOTE_UPDATES = 2  # coach notes a turn may propose, besides the address
NEW_NOTE_WEIGHT = 0.6
REINFORCE = 0.2
_ADDRESS_ARGS = {
    "type": "object",
    "properties": {
        "self_term": {"type": "string", "description": "How you will call yourself, e.g. chị, em, tôi, 我."},
        "user_term": {"type": "string", "description": "How you will call the learner, e.g. em, anh, bạn, a name."},
        "register": {"type": "string", "enum": ["plain", "polite"],
                     "description": "Chinese only: polite (您) only when the learner asks for it."},  # fmt: skip
    },
    "required": ["self_term", "user_term"],
    "additionalProperties": False,
}
TERM_RULE = "each term is 1-24 letters, at most 3 words with single spaces between, nothing else (§5.6)"


def payload_shapes(action_type: str, target: str, intents: list[str] | None = None) -> str:
    """The payloads an action takes, spelled out for the model (the live run: it guessed four wrong shapes).

    From the contract's own table: `save_word: {"text": "…", "lang": "zh-CN"}`. `lang` is always the language
    being learned; a closed set is listed; `navigate` takes `intent` plus that intent's ids.
    """

    spec = ACTIONS[action_type]
    if action_type == "navigate":
        return 'navigate: {"intent": <one of the navigable intents>, …that intent\'s ids}'
    forms = []
    for shape in spec.shapes:
        fields = []
        for key in sorted(shape.required) + sorted(shape.optional):
            if key == "lang":
                value = f'"{target}"'
            elif key in spec.values:
                value = " | ".join(f'"{v}"' for v in sorted(spec.values[key]))
            elif key == "target":
                value = '{"system": "deck" | "library", "id": "…"}'
            elif key == "item_ids":
                value = '["…"]'
            else:
                value = '"…"'
            fields.append(f'"{key}": {value}' + ("" if key in shape.required else " (optional)"))
        forms.append("{" + ", ".join(fields) + "}")
    return f"{action_type}: " + " or ".join(forms)


def action_label_key(action_type: str, payload: Mapping[str, Any]) -> str:
    if action_type == "navigate":
        return f"navigate.{payload.get('intent')}"
    return f"action.{action_type}"


def opening_suggestions(surface: str | None) -> tuple[str, ...]:
    """The ways forward an opening turn offers when the model named none (§3.2: at least one)."""

    if surface is None or surface in {"home", "orena.home"} or surface.startswith("vocabulary."):
        return ("prompt.review_due", "prompt.app_help")
    if surface.startswith("writing."):
        return ("prompt.writing_feedback", "prompt.app_help")
    return ("prompt.app_help",)


def reply_tool_specs(
    client: ClientInfo, target: str, *, version: int = CONTRACT_VERSION, opening: bool = False
) -> tuple[ProviderToolSpec, ...]:
    """The reply tools this client can use. No actions declared, no action tool; no address tools when opening."""

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
                "Offer a button the learner can tap. Nothing happens until they tap it, so your answer "
                "invites them to tap it by its label, in the support language, and never says it is done. "
                "Payloads, exactly: " + "; ".join(payload_shapes(a, target) for a in allowed) + ". "
                "Ids in the payload must come from a tool result or the "
                "context, never invented; a word is {text, lang} in the language being learned. navigate "
                f"needs 'intent' plus that intent's ids; navigable intents: {', '.join(intents) or 'none'}."
                + (" 'reason' is one short, checkable line on why, in the support language." if version >= 2 else ""),
                {"type": "object", "properties": properties, "required": ["type", "payload"], "additionalProperties": False},
            ),
        )
    if not opening:  # an opening turn has no learner words to take a note from (§3.2: no memory_update)
        specs += [
            ProviderToolSpec(
                REMEMBER_NOTE,
                "Keep something the learner said directly about how they learn: a preference (\"explain "
                "briefly\"), a goal (\"HSK4 in December\") or a plan (\"15 minutes a day\"), in their words. Never "
                "feelings, circumstances or health; never what their records already show. To correct or restate "
                "one, give its id as replaces. The device keeps it.",
                {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": sorted(COACH_NOTE_KINDS)},
                        "text": {"type": "string", "maxLength": MAX_NOTE_CHARS},
                        "replaces": {"type": "string", "description": "The id of the coach note this corrects."},
                    },
                    "required": ["kind", "text"],
                    "additionalProperties": False,
                },
            ),
            ProviderToolSpec(
                FORGET_NOTE,
                "Forget a coach note the learner asked you to forget, by its id.",
                {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"], "additionalProperties": False},
            ),
        ]
    if not opening and version >= ADDRESS_VERSION:  # a v4 client is never sent an address note (§5.6)
        specs += [
            ProviderToolSpec(
                SET_ADDRESS,
                "Keep how you and the learner are called from now on - only when the learner asked for this pair "
                "or said yes when you offered it. The device remembers it.",
                _ADDRESS_ARGS,
            ),
            ProviderToolSpec(
                OFFER_ADDRESS,
                "Before asking the learner, once, whether they want the pair they keep using themselves. "
                "Refused if you already asked in this session.",
                _ADDRESS_ARGS,
            ),
        ]
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
    # key an id was read as -> {id -> domain kind of its record}
    known_ids: dict[str, dict[str, str | None]] = field(default_factory=dict)
    actions: list[ActionEvent] = field(default_factory=list)
    suggestions: list[SuggestionEvent] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    references: list[tuple[str, str]] = field(default_factory=list)
    voice_style: str = "neutral_explain"
    address_asked: bool = False  # already offered in this session
    address_chosen: bool = False  # the learner already chose a pair (or said no): no offer
    notes: Mapping[str, float] = field(default_factory=dict)  # coach note id -> weight, as the device sent them
    # A turn the server read as correcting these notes (agent/notes.py): a correction replaces, it never forgets.
    correcting: tuple[str, ...] = ()
    # The notes this message names as changed, and how (agent/notes.py): what a replace or a forget may touch (3.2).
    asked: tuple[str, ...] = ()
    notes_intent: str | None = None
    learner_words: str = ""  # this turn's message: a gendered or casual term must come from it
    address_terms: tuple[str | None, str | None] = (None, None)  # the pair in use
    address_offered_now: bool = False
    memory_updates: list[MemoryUpdateEvent] = field(default_factory=list)
    # A keep request typed without Vietnamese diacritics (agent/notes.py): nothing is kept on it; the note the model
    # proposes, (kind, text), is put to the learner to confirm with a button (human direction 2026-10-04).
    unaccented_keep: bool = False
    note_offer: tuple[str, str] | None = None

    # --- ids the turn has seen ------------------------------------------------

    def learn_ids(self, key: str, ids: Iterable[object], *, kind: str | None = None) -> None:
        """Ids the turn may name back, each as the `key` it was read or sent as."""

        known = self.known_ids.setdefault(key, {})
        for value in ids:
            if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value):
                if known.get(str(value)) is None:
                    known[str(value)] = kind

    def knows(self, key: str, value: object) -> bool:
        return str(value) in self.known_ids.get(key, {})

    def learn_from(self, value: Any, *, kind: str | None = None) -> None:
        """Every id-keyed value anywhere in a tool's data or evidence reference."""

        if isinstance(value, Mapping):
            for key, item in value.items():
                if str(key) in _ID_KEYS and not isinstance(item, (Mapping, list, tuple)):
                    self.learn_ids(str(key), (item,), kind=kind)
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
            REMEMBER_NOTE: self._remember,
            FORGET_NOTE: self._forget,
            SET_ADDRESS: self._set_address,
            OFFER_ADDRESS: self._offer_address,
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
            return (
                f"refused: payload does not fit {action_type} ({_first_error(exc)}). "
                f"It takes {payload_shapes(action_type, self.target)}"
            )
        self.actions.append(action)
        return (
            f"accepted: {action.id}, shown as the button '{action.label}'. The learner has not tapped it: "
            "offer it by that label; do not say it is done."
        )

    def _provenance(self, action_type: str, payload: Mapping[str, Any]) -> str | None:
        """None when every id and word in the payload is one the turn may name."""

        for key in READ_ID_KEYS & set(payload):
            if not self.knows(key, payload[key]):
                return f"refused: {key} must be one a tool returned as {key} or the context sent, never invented"
        target = payload.get("target")
        if isinstance(target, Mapping):
            read_as = TARGET_ID_KEYS.get(str(target.get("system")))
            if read_as is None or not self.knows(read_as, target.get("id")):
                return "refused: target.id must be a collection a tool returned, never invented"
        items = payload.get("item_ids")
        if isinstance(items, list) and not all(self.knows("item_id", item) for item in items):
            return "refused: item_ids must be items a tool returned or the context sent"
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
                kind = self.known_ids.get(key, {}).get(str(payload[key]))
                break
        target = payload.get("target")
        if kind is None and isinstance(target, Mapping):
            read_as = TARGET_ID_KEYS.get(str(target.get("system")), "")
            kind = self.known_ids.get(read_as, {}).get(str(target.get("id")))
        if reason is None and kind is None:
            return None
        return Display(kind=kind, reason=reason)

    def _address_terms(self, args: Mapping[str, Any]) -> tuple[str, str] | None:
        self_term, user_term = args.get("self_term"), args.get("user_term")
        if not (valid_term(self_term) and valid_term(user_term)):  # the UI's rule, checked again here (§5.6)
            return None
        return str(self_term), str(user_term)

    def _set_address(self, args: Mapping[str, Any]) -> str:
        if self.opening:
            return "refused: not in an opening turn"
        if self.version < ADDRESS_VERSION:
            return "refused: this app does not keep an address yet"
        terms = self._address_terms(args)
        if terms is None:
            return f"refused: {TERM_RULE}"
        for term in terms:
            if term in self.address_terms:
                continue  # the pair in use may always be kept
            if term.casefold() in GENDERED and not used_by_learner(term, self.learner_words):
                return f"refused: '{term}' is never used unless the learner used it (no guessing gender or age)"
            if term.casefold() in CASUAL and not explicit_request(term, self.learner_words):
                return f"refused: '{term}' only when the learner asks for it in so many words"
        register = "polite" if args.get("register") == "polite" or terms[1] == "您" else "plain"
        self_term, user_term = terms
        if self.support == "zh-CN" and user_term in {"你", "您"}:
            user_term = None  # 你 / 您 is the register, not a form of address (§5.6)
        try:
            note = address_note(self.support, self_term, user_term, register=register)
        except ValueError:
            return "refused: this support language keeps no address (§5.6); use its ordinary first and second person"
        # one pair per support language: a second call in the turn replaces the first
        self.memory_updates = [u for u in self.memory_updates if u.note.get("id") != note["id"]]
        self.memory_updates.append(MemoryUpdateEvent(op="upsert", note=note))
        return (
            f"accepted: from this answer on you are '{terms[0]}' and the learner is '{terms[1]}'. "
            "The words change; the respect does not."
        )

    def _note_updates(self) -> int:
        return sum(1 for u in self.memory_updates if not str(u.note.get("id", "")).startswith("address-"))

    @property
    def note_changed(self) -> bool:
        """A coach note (not the address) was kept, replaced or forgotten in this turn."""

        return self._note_updates() > 0

    def _remember(self, args: Mapping[str, Any]) -> str:
        """A coach note (spec §12 layer 3): only what the learner said directly; the device keeps it (§5.4)."""

        if self.opening:
            return "refused: not in an opening turn"
        kind, text, replaces = args.get("kind"), args.get("text"), args.get("replaces")
        if replaces is None and len(self.correcting) == 1:
            replaces = self.correcting[0]  # the learner corrected this very note: the new words replace it
        if kind not in COACH_NOTE_KINDS or not isinstance(text, str) or not text.strip():
            return f"refused: kind is one of {sorted(COACH_NOTE_KINDS)} and text is the learner's own words"
        if len(text.strip()) > MAX_NOTE_CHARS:
            return f"refused: at most {MAX_NOTE_CHARS} characters"
        if replaces is not None and (str(replaces) not in self.notes or str(replaces).startswith("address-")):
            return "refused: replaces names a coach note the learner has (not an address note: use set_address)"
        # The server, not the model, decides a note may be written (dogfood gate 3.2): a new note only when the
        # learner asks for it in so many words; a replacement only of the note their message corrects.
        if replaces is None and self.unaccented_keep:
            if self.note_offer is None:
                self.note_offer = (str(kind), text.strip())
            return ("refused: typed without diacritics, so the server asks the learner to confirm this note with a "
                    "button - do not say it is kept, and do not ask about it yourself")  # fmt: skip
        if replaces is None and not asks_to_remember(self.learner_words):
            return ("refused: the learner did not ask you to remember anything - if it seems worth keeping, "
                    "ask them in words, and keep it only when they say so")  # fmt: skip
        confirmed = confirmed_note(self.learner_words)
        if replaces is None and confirmed is not None and not same_note(text, confirmed):
            # The learner tapped to keep these very words (notes.keep_label): nothing else is kept on that tap.
            return f"refused: keep exactly the words the learner confirmed: {confirmed}"
        if replaces is not None and str(replaces) not in self.correcting:
            return "refused: the learner's message does not correct that note"
        if self._note_updates() >= MAX_NOTE_UPDATES:
            return f"refused: at most {MAX_NOTE_UPDATES} notes a turn"
        weight = min(1.0, self.notes[str(replaces)] + REINFORCE) if replaces is not None else NEW_NOTE_WEIGHT
        note = {
            "id": str(replaces) if replaces is not None else f"n-{secrets.token_hex(5)}",
            "kind": kind,
            "text": text.strip(),
            "weight": round(weight, 2),
            "last_reinforced": datetime.now(UTC).isoformat(),
            "expires_at": None,
        }
        self.memory_updates.append(MemoryUpdateEvent(op="upsert", note=note))
        return f"accepted: kept as {note['id']}; you may say it is noted"

    def _forget(self, args: Mapping[str, Any]) -> str:
        if self.opening:
            return "refused: not in an opening turn"
        note_id = str(args.get("id") or "")
        if note_id not in self.notes or note_id.startswith("address-"):
            return "refused: no such coach note (an address is changed with set_address)"
        if note_id in self.correcting:
            return ("refused: the learner corrected this note with a new wish, they did not ask to forget it - call "
                    "remember_note with replaces set to its id and the new wish")  # fmt: skip
        if note_id not in self.asked or self.notes_intent != FORGET:
            return "refused: the learner did not ask to forget that note"
        self.memory_updates.append(MemoryUpdateEvent(op="remove", note={"id": note_id}))
        return f"accepted: {note_id} is forgotten; you may say so"

    def _offer_address(self, args: Mapping[str, Any]) -> str:
        if self.opening:
            return "refused: not in an opening turn"
        if self.address_chosen:
            return "refused: the learner already chose how you are called; change it only if they ask"
        if self.address_asked or self.address_offered_now:
            return "refused: you already asked in this session; keep the current address and do not ask again"
        if self._address_terms(args) is None:
            return f"refused: {TERM_RULE}"
        self.address_offered_now = True
        return "accepted: ask once, in your answer, whether they want this pair; call set_address only on a yes"

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
