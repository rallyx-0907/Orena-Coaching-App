"""The closed vocabularies of AGENT_CONTRACT.md, each held in one table.

Everything the contract enumerates lives here and nowhere else: surface ids
(which double as navigation intents, §6.1), activity types (§3), event names
(§4), voice styles (§5.2), evidence sources (§5.3) and the action allowlist with
its fixed risk (§7). `tests/test_agent_contract_tables.py` reads the contract
file and fails when a table here and the file disagree, so a contract bump that
reaches this lane by merge cannot be missed.

Adding an id is a contract change made on `codex/work`, never here.

Version 5 (D-096) is served: the learner's address travels as
`context.address` and is kept as a note of kind `address` (§5.6); the server's
fixed support copy follows it; a reply with an action offers it and never
reports it done; surface names come from the UI's surfaces.json (§6.2). A
client that declares 4 or less sends no address and is never sent an address
note (agent/address.py).
Version 4 (D-095) names the HTTP statuses (§2.1) and the
error classes (§4.1) this server already answered with, and changes no event.
Version 3 (D-094) changed no shape either: an action's label is
interface copy (it always was here, ruling R12) and a suggestion's intent is a
prompt intent in the `prompt.` namespace (`PROMPT_NAMESPACE`), never a §6.1
id. Both hold for every client, since neither is a field an older client lacks.
A client that declares version 1 gets nothing version 2 added or changed: no
`display`, no opening turn, no `orena.home`, and none of the actions or
navigation intents whose payload changed (`V1_ACTIONS`, `V1_SURFACES`).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

CONTRACT_VERSION = 7


def negotiated_version(client_version: int) -> int:
    """The version both sides speak: never above what the client declared.

    A newer client talking to this server gets this server's version; a server
    never sends a field the client's declared version does not have.
    """

    if client_version < 1:
        raise ValueError("contract_version starts at 1")
    return min(client_version, CONTRACT_VERSION)


# --- §6.1 surface ids and navigation intents --------------------------------
# One id space serves both. The value is the parameters a `navigate` payload
# must carry for that intent.

SURFACES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "home": (),
        "orena.home": (),
        "library": (),
        "reading.library": (),
        "reading.workspace": ("content_id",),
        "listening.library": (),
        "listening.workspace": ("content_id",),
        "listening.dictation": ("content_id",),
        "speaking.library": (),
        "speaking.workspace": ("content_id",),
        "speaking.free_talk": (),
        "speaking.word_detail": ("take_ref", "item_id"),
        "speaking.compare": ("take_ref", "item_id"),
        "writing.workspace": (),
        "writing.review": ("essay_id",),
        "writing.revision": ("essay_id",),
        "vocabulary.my_language": (),
        "vocabulary.word": ("text", "lang"),
        "vocabulary.review_due": (),
        "grammar.catalog": (),
        "grammar.point": ("grammar_id",),
        "progress": (),
        "preferences": (),
        "preferences.agent_memory": (),
    }
)
# What a version-1 client may be sent as a navigation intent: every id whose
# parameters did not change in version 2, and none that version 2 added.
V1_SURFACES = frozenset(SURFACES) - {"orena.home", "speaking.word_detail", "speaking.compare", "vocabulary.word"}


# --- §3 request vocabularies -------------------------------------------------

ACTIVITY_TYPES = frozenset(
    {
        "app_help",
        "coaching",
        "review",
        "reading",
        "listening",
        "pronunciation_practice",
        "free_talk",
        "conversation_practice",
        "writing",
        "grammar",
        "vocabulary",
    }
)
SELECTED_ITEM_TYPES = frozenset({"word", "sentence", "feedback_item", "grammar_point"})
TRIGGERS = frozenset({"message", "open"})
COACH_NOTE_KINDS = frozenset({"preference", "goal", "plan"})  # what `coach_notes` carries (§3, §5.4)
ADDRESS_NOTE_KIND = "address"  # §5.6: its own rules; sent back as context.address, never in coach_notes
NOTE_KINDS = COACH_NOTE_KINDS | {ADDRESS_NOTE_KIND}
MAX_COACH_NOTES = 20
MAX_COACH_NOTES_BYTES = 2048


# --- §4 events ---------------------------------------------------------------

EVENT_NAMES = frozenset(
    {
        "session",
        "segment_delta",
        "segment_end",
        "tool_call",
        "tool_result",
        "evidence",
        "action",
        "suggestion",
        "memory_update",
        "voice_state",
        "audio_chunk",
        "metered",
        "error",
        "done",
    }
)
TERMINAL_EVENTS = frozenset({"done", "error"})
VOICE_ONLY_EVENTS = frozenset({"voice_state", "audio_chunk"})
VOICE_STATES = frozenset({"listening", "thinking", "speaking", "interrupted"})
AUDIO_FORMATS = frozenset({"pcm16_24k"})
BUDGET_STATES = frozenset({"ok", "soft_limited"})
ERROR_FALLBACKS = frozenset({"retry", "text_only", "none"})
MEMORY_OPS = frozenset({"upsert", "remove"})


# --- §5 payload types --------------------------------------------------------

VOICE_STYLES = frozenset(
    {"neutral_explain", "encouraging", "gentle_correction", "celebrate", "brief_ack", "reference"}
)
EVIDENCE_SOURCES = frozenset(
    {
        "speech.pronunciation",
        "writing.evaluation",
        "reading.comprehension",
        "listening.dictation",
        "vocabulary.review",
        "grammar.catalog",
        "learner_summary",
    }
)


# §5.5 display on an action or evidence (version 2)
DISPLAY_KINDS = frozenset({"reading", "listening", "speaking", "writing", "vocabulary", "grammar", "review"})
MAX_DISPLAY_REASON_CHARS = 90

# §3.2 the opening turn (version 2)
OPENING_MAX_CHARS = 240
OPENING_MAX_SUGGESTIONS = 5
OPENING_MAX_ACTIONS = 2


# --- §7 actions --------------------------------------------------------------


class ActionRisk(StrEnum):
    LOW = "LOW"
    CONFIRM = "CONFIRM"


@dataclass(frozen=True)
class PayloadShape:
    """One accepted payload: these keys required, these allowed besides."""

    required: frozenset[str]
    optional: frozenset[str] = frozenset()

    def accepts(self, keys: frozenset[str]) -> bool:
        return self.required <= keys <= self.required | self.optional


@dataclass(frozen=True)
class ActionSpec:
    risk: ActionRisk
    shapes: tuple[PayloadShape, ...]
    # Closed value sets for keys the contract enumerates (`scope`, `focus`).
    values: Mapping[str, frozenset[str]] = field(default_factory=lambda: MappingProxyType({}))


def _shape(*required: str, optional: tuple[str, ...] = ()) -> PayloadShape:
    return PayloadShape(frozenset(required), frozenset(optional))


# `navigate` is the one action whose payload depends on another table: it
# carries `intent` plus that intent's parameters from SURFACES.
ACTIONS: Mapping[str, ActionSpec] = MappingProxyType(
    {
        "navigate": ActionSpec(ActionRisk.LOW, ()),
        "play_model": ActionSpec(ActionRisk.LOW, (_shape("content_id", optional=("item_id",)),)),
        "play_user": ActionSpec(ActionRisk.LOW, (_shape("take_ref", optional=("item_id",)),)),
        "say_again": ActionSpec(ActionRisk.LOW, (_shape("content_id", optional=("item_id",)),)),
        "compare_with_model": ActionSpec(ActionRisk.LOW, (_shape("take_ref", "item_id"),)),
        "save_word": ActionSpec(ActionRisk.LOW, (_shape("text", "lang"),)),
        "add_word_to_collection": ActionSpec(ActionRisk.LOW, (_shape("text", "lang", optional=("target",)),)),
        "start_review": ActionSpec(
            ActionRisk.LOW,
            (_shape("scope"), _shape("scope", "text", "lang")),
            MappingProxyType({"scope": frozenset({"due", "word"})}),
        ),
        "start_targeted_drill": ActionSpec(
            ActionRisk.LOW,
            (_shape("focus", "item_ids"),),
            MappingProxyType({"focus": frozenset({"tone", "stress", "word"})}),
        ),
        "unsave_word": ActionSpec(ActionRisk.CONFIRM, (_shape("text", "lang"),)),
    }
)
# `add_word_to_collection.target` names the collection system (§7).
COLLECTION_SYSTEMS = frozenset({"deck", "library"})
# Payload keys that name a word (§7): a word is its text in the learning language.
WORD_ACTIONS = frozenset({"save_word", "unsave_word", "add_word_to_collection"})
# Payload keys holding an id, which must come from a tool read or the request
# (§7 "Ids in payloads come from tool reads, never from generation").
READ_ID_KEYS = frozenset({"content_id", "grammar_id", "essay_id", "item_id"})
# The actions whose shape version 2 left unchanged: all a version-1 client gets.
V1_ACTIONS = frozenset({"navigate", "play_model", "start_targeted_drill"})


def actions_for_version(version: int) -> frozenset[str]:
    return frozenset(ACTIONS) if version >= 2 else V1_ACTIONS


def intents_for_version(version: int) -> frozenset[str]:
    return frozenset(SURFACES) if version >= 2 else V1_SURFACES


MAX_ACTION_LABEL_CHARS = 24
# §4: a suggestion's intent names the question it asks, in this namespace (v3, D-094).
PROMPT_NAMESPACE = "prompt."
