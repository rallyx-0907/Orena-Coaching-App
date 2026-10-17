"""Validate a session summariser's output before anything is stored (ORENA_MEMORY.md rev 4.1 §4.3; D-222).

A summary holds learning continuity only: exactly `practised`, `focus` and `open_task`, each entry a closed `event`
code and an `item` that the event's own validator accepts. No validator accepts free personal text, so a summary
cannot carry a personal fact, an excluded category or a deleted item's value; there is nothing for a suppression key
to search. An item no validator accepts is dropped and its entry keeps the event code.

`useful_context` is (slot, code) from the closed lists of `memory_slots`; each must be grounded in a learner message
of that session or it is dropped. It is returned apart, for materialisation into continuity items, and never stored
in the summary.

Output that breaks the schema or its bounds is rejected whole (`None`), not cut: the previous checkpoint stands.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from writing_coach.agent.memory_slots import SLOTS, grounded

EVENTS = (
    "grammar_point",
    "vocabulary_set",
    "pronunciation_word",
    "writing_revision",
    "reading_text",
    "listening_text",
    "interview_answer",
    "roleplay_scenario",
)
# Practice scenarios, by code. None names money, health, belief or a place more precise than a city errand.
SCENARIOS = (
    "self_introduction",
    "why_this_company",
    "strengths_and_weaknesses",
    "describe_a_project",
    "questions_for_the_interviewer",
    "ordering_food",
    "shopping",
    "asking_directions",
    "small_talk",
    "phone_call",
    "meeting",
)
SUMMARY_KEYS = ("practised", "focus", "open_task")
OUTPUT_KEYS = frozenset(SUMMARY_KEYS) | {"useful_context"}
MAX_PRACTISED = 4
MAX_CONTEXT = 6
MAX_ITEM = 60  # characters
MAX_WORDS = 5  # words in one vocabulary or pronunciation item
_WORD_SPLIT = re.compile(r"[,，、;；/]+|\s+")


@dataclass(frozen=True)
class SummaryContext:
    """What the validators may accept, read from the learner's own records and this session."""

    learner_messages: tuple[str, ...] = ()  # learner-authored message fields of the session, nothing else
    known_words: frozenset[str] = frozenset()  # saved words, speaking attempts' words, and this session's words
    is_grammar_point: Callable[[str], bool] = field(default=lambda _item: False)
    essay_ids: frozenset[str] = frozenset()
    reading_titles: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    listening_titles: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))


@dataclass(frozen=True)
class ValidatedSummary:
    summary: dict[str, Any]  # exactly SUMMARY_KEYS: what the summary row stores
    useful_context: tuple[tuple[str, str], ...]  # grounded (slot, code), for continuity items
    dropped: int  # items and context entries no validator accepted (a count for telemetry, never their text)


def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip()


def _words(item: str, known: frozenset[str]) -> str | None:
    words = [word for word in _WORD_SPLIT.split(item) if word]
    if not words or len(words) > MAX_WORDS:
        return None
    folded = {word.casefold() for word in known}
    return "、".join(words) if all(word.casefold() in folded for word in words) else None


def _title(item: str, titles: Mapping[str, str]) -> str | None:
    return titles.get(item)  # the item is a content id; it is rendered as the record's title


_VALIDATORS: Mapping[str, Callable[[str, SummaryContext], str | None]] = MappingProxyType({
    "grammar_point": lambda item, ctx: item if ctx.is_grammar_point(item) else None,
    "vocabulary_set": lambda item, ctx: _words(item, ctx.known_words),
    "pronunciation_word": lambda item, ctx: _words(item, ctx.known_words),
    "writing_revision": lambda item, ctx: item if item in ctx.essay_ids else None,
    "reading_text": lambda item, ctx: _title(item, ctx.reading_titles),
    "listening_text": lambda item, ctx: _title(item, ctx.listening_titles),
    "interview_answer": lambda item, _ctx: item if item in SCENARIOS else None,
    "roleplay_scenario": lambda item, _ctx: item if item in SCENARIOS else None,
})


class _Rejected(Exception):
    """The output breaks the schema or its bounds."""


def _entry(raw: Any, ctx: SummaryContext, dropped: list[int]) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or set(raw) - {"event", "item"} or raw.get("event") not in EVENTS:
        raise _Rejected
    item = raw.get("item")
    if item is None:
        return {"event": raw["event"], "item": None}
    if not isinstance(item, str) or len(item) > MAX_ITEM:
        raise _Rejected
    accepted = _VALIDATORS[raw["event"]](_nfc(item), ctx)
    if accepted is None:
        dropped[0] += 1
    return {"event": raw["event"], "item": accepted}


def _optional(raw: Any, ctx: SummaryContext, dropped: list[int]) -> dict[str, Any] | None:
    return None if raw is None else _entry(raw, ctx, dropped)


def _context(raw: Any, ctx: SummaryContext, dropped: list[int]) -> tuple[tuple[str, str], ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list) or len(raw) > MAX_CONTEXT:
        raise _Rejected
    kept: list[tuple[str, str]] = []
    for entry in raw:
        if not isinstance(entry, Mapping) or set(entry) != {"slot", "code"}:
            raise _Rejected
        slot, code = entry["slot"], entry["code"]
        if slot in SLOTS and code in SLOTS[slot] and grounded(slot, code, ctx.learner_messages):
            if (slot, code) not in kept:
                kept.append((slot, code))
        else:
            dropped[0] += 1  # a slot or code off the lists, or not said by the learner
    return tuple(kept)


def validate_summary(raw: Any, ctx: SummaryContext) -> ValidatedSummary | None:
    """The stored summary and the grounded context, or None when the output is rejected whole."""

    try:
        if not isinstance(raw, Mapping) or set(raw) - OUTPUT_KEYS:
            raise _Rejected
        practised = raw.get("practised") or []
        if not isinstance(practised, list) or len(practised) > MAX_PRACTISED:
            raise _Rejected
        dropped = [0]
        summary = {
            "practised": [_entry(entry, ctx, dropped) for entry in practised],
            "focus": _optional(raw.get("focus"), ctx, dropped),
            "open_task": _optional(raw.get("open_task"), ctx, dropped),
        }
        context = _context(raw.get("useful_context"), ctx, dropped)
    except _Rejected:
        return None
    return ValidatedSummary(summary=summary, useful_context=context, dropped=dropped[0])


# A continuity item whose code a summary entry also carries: deleting the item removes those entries too.
RELATED_EVENTS: Mapping[tuple[str, str], frozenset[str]] = MappingProxyType({
    ("learning_purpose", "job_interview"): frozenset({"interview_answer"}),
})


def without_deleted_item(summary: Mapping[str, Any], slot: str, code: str) -> dict[str, Any]:
    """The summary without the entries that carry a deleted continuity item's code, removed in the same transaction
    as the item, while its (slot, code) is still in hand (§3.4)."""

    events = RELATED_EVENTS.get((slot, code), frozenset())

    def carries(entry: Mapping[str, Any] | None) -> bool:
        return entry is not None and (entry.get("event") in events or entry.get("item") == code)

    kept = dict(summary)
    kept["practised"] = [entry for entry in summary.get("practised") or [] if not carries(entry)]
    for key in ("focus", "open_task"):
        if carries(summary.get(key)):
            kept[key] = None
    return kept
