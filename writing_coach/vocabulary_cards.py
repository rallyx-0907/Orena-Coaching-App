"""Pure Vocabulary Card projection over the existing saved-word relationship.

The saved-word row remains the learner relationship and owns review state. This
module only shapes the richer card object described by the Vocabulary
Architecture; it does not persist cards, invent missing fields, or create a
second recall scheduler.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _text(row: Mapping[str, Any], key: str) -> str:
    return str(row.get(key) or "").strip()


def _meanings(row: Mapping[str, Any]) -> list[dict[str, str]]:
    meanings: list[dict[str, str]] = []
    definition = _text(row, "definition")
    translation = _text(row, "translation_vi")
    language = _text(row, "language_code").casefold()
    if definition:
        meanings.append({"language": language or "unknown", "text": definition})
    if translation:
        meanings.append({"language": "vi", "text": translation})
    return meanings


def _source_encounters(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    kind = _text(row, "source_kind")
    fragment = _text(row, "source_fragment")
    if not kind or not fragment:
        return []
    encounter: dict[str, Any] = {"kind": kind, "fragment": fragment}
    source_id = row.get("source_essay_id")
    if source_id is not None:
        encounter["sourceId"] = str(source_id)
    return [encounter]


def vocabulary_card_from_saved_word(
    row: Mapping[str, Any], *, orthography: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Return a truthful card projection for one existing saved-word row."""

    headword = _text(row, "word")
    if not headword:
        raise ValueError("Vocabulary Card requires a headword")
    language = _text(row, "language_code").casefold()
    normalized = _text(row, "normalized_word") or headword.casefold()
    card: dict[str, Any] = {
        "identity": {"language": language or "unknown", "normalized": normalized},
        "headword": headword,
        "meanings": _meanings(row),
        "examples": [],
        "collocations": [],
        "related": [],
        "learner_traps": [],
        "source_encounters": _source_encounters(row),
        "memory": {
            "review_stage": int(row.get("review_stage") or 0),
            "successful_recalls": int(row.get("successful_recalls") or 0),
            "lapse_count": int(row.get("lapse_count") or 0),
        },
    }
    pronunciation = _text(row, "phonetic")
    if pronunciation:
        card["pronunciation"] = pronunciation
    part_of_speech = _text(row, "part_of_speech")
    if part_of_speech:
        card["part_of_speech"] = part_of_speech
    if orthography is not None:
        card["orthography"] = dict(orthography)
    return card
