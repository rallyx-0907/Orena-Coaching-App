"""The closed vocabularies of AGENT_CONTRACT.md, each held in one table.

Everything the contract enumerates lives here and nowhere else: surface ids
(which double as navigation intents, §6.1), activity types (§3), event names
(§4), voice styles (§5.2), evidence sources (§5.3) and the action allowlist with
its fixed risk (§7). `tests/test_agent_contract_tables.py` reads the contract
file and fails when a table here and the file disagree, so a contract bump that
reaches this lane by merge cannot be missed.

Adding an id is a contract change made on `codex/work`, never here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

CONTRACT_VERSION = 1


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
        "library": (),
        "reading.library": (),
        "reading.workspace": ("content_id",),
        "listening.library": (),
        "listening.workspace": ("content_id",),
        "listening.dictation": ("content_id",),
        "speaking.library": (),
        "speaking.workspace": ("content_id",),
        "speaking.free_talk": (),
        "speaking.word_detail": ("attempt_id", "item_id"),
        "speaking.compare": ("attempt_id", "item_id"),
        "writing.workspace": (),
        "writing.review": ("essay_id",),
        "writing.revision": ("essay_id",),
        "vocabulary.my_language": (),
        "vocabulary.word": ("word_id",),
        "vocabulary.review_due": (),
        "grammar.catalog": (),
        "grammar.point": ("grammar_id",),
        "progress": (),
        "preferences": (),
        "preferences.agent_memory": (),
    }
)


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
COACH_NOTE_KINDS = frozenset({"preference", "goal", "plan"})
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
        "play_user": ActionSpec(ActionRisk.LOW, (_shape("attempt_id", optional=("item_id",)),)),
        "say_again": ActionSpec(
            ActionRisk.LOW,
            (_shape("attempt_id", optional=("item_id",)), _shape("content_id", optional=("item_id",))),
        ),
        "compare_with_model": ActionSpec(ActionRisk.LOW, (_shape("attempt_id", "item_id"),)),
        "save_word": ActionSpec(ActionRisk.LOW, (_shape("word_id"), _shape("text", "lang"))),
        "add_word_to_collection": ActionSpec(
            ActionRisk.LOW, (_shape("word_id", optional=("collection_id",)),)
        ),
        "start_review": ActionSpec(
            ActionRisk.LOW,
            (_shape("scope", optional=("word_id",)),),
            MappingProxyType({"scope": frozenset({"due", "word"})}),
        ),
        "start_targeted_drill": ActionSpec(
            ActionRisk.LOW,
            (_shape("focus", "item_ids"),),
            MappingProxyType({"focus": frozenset({"tone", "stress", "word"})}),
        ),
        "unsave_word": ActionSpec(ActionRisk.CONFIRM, (_shape("word_id"),)),
    }
)
MAX_ACTION_LABEL_CHARS = 24
