"""Pure Vocabulary Card projection over the existing saved-word relationship.

The saved-word row remains the learner relationship and owns review state. This
module only shapes the richer card object described by the Vocabulary
Architecture; it does not persist cards, invent missing fields, or create a
second recall scheduler.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from writing_coach.orthography import (
    OrthographyContractError,
    explanation_kinds,
    validate_orthography,
    validate_provenance,
)


class VocabularyCardError(ValueError):
    """Raised when a Vocabulary Card breaks its domain contract."""


_COLLECTION_FIELDS = (
    "examples",
    "collocations",
    "related",
    "learner_traps",
    "learner_examples",
    "understanding_refs",
    "explanation_artifacts",
)

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


def _list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise VocabularyCardError(f"{path} must be a list.")
    return value


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise VocabularyCardError(f"{path} must be a mapping.")
    return value


def _required_text(value: Any, path: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise VocabularyCardError(f"{path} must be non-empty text.")


def _validate_collection(value: Any, path: str, *, text_required: bool = False) -> None:
    for index, item in enumerate(_list(value, path)):
        if isinstance(item, str):
            if text_required:
                _required_text(item, f"{path}[{index}]")
            continue
        entry = _mapping(item, f"{path}[{index}]")
        if text_required or "text" in entry:
            _required_text(entry.get("text"), f"{path}[{index}].text")


def _validate_meanings(value: Any) -> None:
    for index, item in enumerate(_list(value, "card.meanings")):
        meaning = _mapping(item, f"card.meanings[{index}]")
        _required_text(meaning.get("language"), f"card.meanings[{index}].language")
        _required_text(meaning.get("text"), f"card.meanings[{index}].text")
        if "contexts" in meaning:
            for context_index, context in enumerate(
                _list(meaning["contexts"], f"card.meanings[{index}].contexts")
            ):
                _required_text(
                    context,
                    f"card.meanings[{index}].contexts[{context_index}]",
                )


def _validate_understanding_refs(value: Any) -> None:
    kinds = explanation_kinds()
    for index, item in enumerate(_list(value, "card.understanding_refs")):
        reference = _mapping(item, f"card.understanding_refs[{index}]")
        if not any(reference.get(key) for key in ("id", "reference", "url")):
            raise VocabularyCardError(
                f"card.understanding_refs[{index}] needs an id or reference."
            )
        if reference.get("kind") not in kinds:
            raise VocabularyCardError(
                f"card.understanding_refs[{index}].kind must be one of {sorted(kinds)}."
            )
        if "context" in reference:
            _required_text(reference["context"], f"card.understanding_refs[{index}].context")


def _validate_explanation_artifacts(value: Any) -> None:
    kinds = explanation_kinds()
    for index, item in enumerate(_list(value, "card.explanation_artifacts")):
        artifact = _mapping(item, f"card.explanation_artifacts[{index}]")
        kind = artifact.get("kind")
        if kind not in kinds:
            raise VocabularyCardError(
                f"card.explanation_artifacts[{index}].kind must be one of {sorted(kinds)}."
            )
        if not any(
            isinstance(artifact.get(key), str) and artifact[key].strip()
            for key in ("text", "reference", "id")
        ):
            raise VocabularyCardError(
                f"card.explanation_artifacts[{index}] needs text or a reference."
            )
        if artifact.get("provenance") is not None:
            try:
                validate_provenance(
                    artifact["provenance"],
                    f"card.explanation_artifacts[{index}].provenance",
                    trusted_required=kind == "verified_etymology",
                )
            except OrthographyContractError as error:
                raise VocabularyCardError(str(error)) from error
        elif kind == "verified_etymology":
            raise VocabularyCardError(
                "verified etymology requires trusted provenance."
            )


def _validate_legacy_orthography(value: Mapping[str, Any]) -> None:
    """Keep the existing stroke endpoint payload readable during transition."""

    _required_text(value.get("script"), "card.orthography.script")
    characters = _list(value.get("characters"), "card.orthography.characters")
    if not value.get("source") or not value.get("source_version"):
        raise VocabularyCardError(
            "legacy orthography requires source and source_version provenance."
        )
    for index, character in enumerate(characters):
        entry = _mapping(character, f"card.orthography.characters[{index}]")
        _required_text(entry.get("character"), f"card.orthography.characters[{index}].character")


def _validate_card_orthography(value: Any) -> None:
    orthography = _mapping(value, "card.orthography")
    try:
        if "units" in orthography:
            validate_orthography(orthography)
        else:
            _validate_legacy_orthography(orthography)
    except OrthographyContractError as error:
        raise VocabularyCardError(str(error)) from error


def validate_vocabulary_card(card: Mapping[str, Any]) -> None:
    """Validate a rich card without generating missing language facts."""

    payload = _mapping(card, "card")
    identity = _mapping(payload.get("identity"), "card.identity")
    _required_text(identity.get("language"), "card.identity.language")
    _required_text(identity.get("normalized"), "card.identity.normalized")
    _required_text(payload.get("headword"), "card.headword")
    _validate_meanings(payload.get("meanings"))
    for field in _COLLECTION_FIELDS:
        if field not in payload:
            continue
        if field == "understanding_refs":
            _validate_understanding_refs(payload[field])
        elif field == "explanation_artifacts":
            _validate_explanation_artifacts(payload[field])
        else:
            _validate_collection(payload[field], f"card.{field}")
    if "orthography" in payload:
        _validate_card_orthography(payload["orthography"])


def vocabulary_card_from_saved_word(
    row: Mapping[str, Any],
    *,
    orthography: Mapping[str, Any] | None = None,
    enrichments: Mapping[str, Any] | None = None,
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
    for field in ("meanings", *_COLLECTION_FIELDS):
        if enrichments is not None and field in enrichments:
            value = enrichments[field]
            card[field] = list(value) if isinstance(value, list) else value
    return card
