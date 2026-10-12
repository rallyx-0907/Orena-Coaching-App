"""Typed items in `vocabulary_entries.usage_notes` (D-17V).

`usage_notes` is a JSON list on the shared lexical entry. It used to hold only
free usage text (`{"language", "text", "origin"}`); it now also carries the
other entry-level facts a vocabulary card shows, each item naming what it is
with `type`. No column was added for them: the list is JSON, has no CHECK, and
is part of the published-membership snapshot, so a typed item travels with the
entry like every other field.

The vocabulary is closed. A reader groups by `type` and never shows an item
under another type's heading - in particular, free usage text is `usage` and is
never presented as a "common mistake"; only an item that says
`type: "common_mistake"` is one.

An item written before types existed has no `type` and is read as `usage`,
which is what it always was.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

USAGE_NOTE_TYPES = (
    "collocation",
    "synonym",
    "antonym",
    "word_family",
    "related",
    "classifier",
    "memory_tip",
    "usage",
    "common_mistake",
)
LEGACY_USAGE_NOTE_TYPE = "usage"
# The relation groups a card draws together.
RELATION_TYPES = ("synonym", "antonym", "word_family", "related")


class UsageNoteError(ValueError):
    """A typed usage note that breaks the contract."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def note_type(item: Any) -> str:
    """The item's type; an untyped legacy item (or a bare string) is `usage`."""

    if isinstance(item, Mapping):
        return _text(item.get("type")) or LEGACY_USAGE_NOTE_TYPE
    return LEGACY_USAGE_NOTE_TYPE


def note_text(item: Any) -> str:
    if isinstance(item, Mapping):
        return _text(item.get("text"))
    return _text(item)


def validate_usage_note(item: Any, path: str = "usage_note") -> None:
    """A written item names a known type and carries text."""

    if not isinstance(item, Mapping):
        raise UsageNoteError(f"{path} must be an object.")
    kind = _text(item.get("type"))
    if kind not in USAGE_NOTE_TYPES:
        raise UsageNoteError(f"{path}.type must be one of {list(USAGE_NOTE_TYPES)}.")
    if not note_text(item):
        raise UsageNoteError(f"{path}.text must be non-empty.")


def notes_of_type(notes: Any, *types: str) -> list[dict[str, Any]]:
    """The items of the given types, in their stored order, as dicts.

    A legacy string becomes `{"type": "usage", "text": ...}` so a caller never
    has to know the old shape.
    """

    wanted = set(types)
    out: list[dict[str, Any]] = []
    for item in notes if isinstance(notes, list) else ():
        kind = note_type(item)
        if kind not in wanted or not note_text(item):
            continue
        if isinstance(item, Mapping):
            out.append({**dict(item), "type": kind})
        else:
            out.append({"type": kind, "text": note_text(item)})
    return out


def texts_of_type(notes: Any, *types: str) -> list[str]:
    seen: list[str] = []
    for item in notes_of_type(notes, *types):
        text = note_text(item)
        if text not in seen:
            seen.append(text)
    return seen


def group_usage_notes(notes: Iterable[Any] | None) -> dict[str, list[dict[str, Any]]]:
    """Every known type, each with its items (possibly empty). Unknown types are dropped."""

    listed = list(notes or ())
    return {kind: notes_of_type(listed, kind) for kind in USAGE_NOTE_TYPES}
