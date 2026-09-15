"""Static curated Vocabulary Library catalog: cross-language aggregation and
structural validation over per-language ``vocabulary_collections.json`` seed
content.

This module mirrors ``writing_coach/grammar_catalog.py``'s role over
``GRAMMAR_COURSE``/``GRAMMAR_BY_ID``: the JSON files colocated with each
language module are the content, the small ``*.vocabulary_collections``
loaders read them at import time, and this module aggregates them across
languages, denormalizes parent collection metadata into each entry, builds a
load-time word index, and validates structure. There is no database table or
membership join here — see
``docs/superpowers/plans/2026-09-14-vocabulary-experience.md`` §2 "Static
catalog, not schema" for why none is needed.

**Seed size is intentionally partial.** ``toeic-600-essential`` and
``common-3000`` ship 35 authored entries each; ``hsk-1`` and ``hsk-2`` ship
the larger first seed batches, while the added CEFR B2/C1/C2 and HSK3–HSK7-9
collections are small level-coverage batches for the current card experience.
None of these is the full breadth named by its collection title — growing a
collection is incremental content authoring against its JSON file, not a
later code task. Provenance on every collection states truthfully that the
content is Orena-curated vocabulary organized to match a public framework's
scope, not licensed or reproduced test material.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from writing_coach.languages.chinese.vocabulary_collections import (
    VOCABULARY_COLLECTIONS as _CHINESE_COLLECTIONS,
)
from writing_coach.languages.english.vocabulary_collections import (
    VOCABULARY_COLLECTIONS as _ENGLISH_COLLECTIONS,
)


class VocabularyCatalogInvalid(ValueError):
    """Raised when a static vocabulary collection catalog is malformed."""


_REQUIRED_COLLECTION_FIELDS = (
    "id",
    "language_code",
    "framework",
    "level",
    "title",
    "provenance",
    "entries",
)
_REQUIRED_STRING_COLLECTION_FIELDS = ("language_code", "framework", "level", "title")
_REQUIRED_ENTRY_FIELDS = ("word", "definition", "support_translations")


def normalize_vocabulary_word(word: object) -> str:
    """Deterministic normalization used for the word index and duplicate checks.

    The repository has no shared word-normalization helper outside the
    persistence layer's inline ``word.casefold()``
    (``writing_coach/persistence/specialized_repository.py``); this mirrors
    that exact rule so a catalog word and a saved word normalize identically.
    """

    return str(word or "").strip().casefold()


def validate_vocabulary_collections(collections: Sequence[Mapping[str, Any]]) -> None:
    """Structural validation over a sequence of raw (non-denormalized) collections.

    Rejects: duplicate collection ids, empty collections, missing required
    fields, non-string/empty ``framework`` or ``level``, duplicate words
    within one collection, and missing/non-mapping ``support_translations``.
    """

    if not isinstance(collections, Sequence) or isinstance(collections, (str, bytes)):
        raise VocabularyCatalogInvalid("Vocabulary collections must be a sequence.")
    seen_collection_ids: set[str] = set()
    for collection in collections:
        if not isinstance(collection, Mapping):
            raise VocabularyCatalogInvalid("Each vocabulary collection must be a mapping.")
        for field in _REQUIRED_COLLECTION_FIELDS:
            if field not in collection:
                raise VocabularyCatalogInvalid(
                    f"Vocabulary collection is missing required field '{field}'."
                )
        collection_id = collection["id"]
        if not isinstance(collection_id, str) or not collection_id.strip():
            raise VocabularyCatalogInvalid("Vocabulary collection id must be a non-empty string.")
        if collection_id in seen_collection_ids:
            raise VocabularyCatalogInvalid(
                f"Duplicate vocabulary collection id '{collection_id}'."
            )
        seen_collection_ids.add(collection_id)
        for field in _REQUIRED_STRING_COLLECTION_FIELDS:
            if not isinstance(collection[field], str) or not collection[field].strip():
                raise VocabularyCatalogInvalid(
                    f"Vocabulary collection '{collection_id}' field '{field}' must be a non-empty string."
                )
        if not isinstance(collection["provenance"], Mapping):
            raise VocabularyCatalogInvalid(
                f"Vocabulary collection '{collection_id}' provenance must be a mapping."
            )
        entries = collection["entries"]
        if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)) or not entries:
            raise VocabularyCatalogInvalid(
                f"Vocabulary collection '{collection_id}' must have a non-empty entries list."
            )
        seen_words: set[str] = set()
        for position, entry in enumerate(entries, start=1):
            if not isinstance(entry, Mapping):
                raise VocabularyCatalogInvalid(
                    f"Vocabulary collection '{collection_id}' entry {position} must be a mapping."
                )
            for field in _REQUIRED_ENTRY_FIELDS:
                if field not in entry:
                    raise VocabularyCatalogInvalid(
                        f"Vocabulary collection '{collection_id}' entry {position} is missing required field '{field}'."
                    )
            word = entry["word"]
            if not isinstance(word, str) or not word.strip():
                raise VocabularyCatalogInvalid(
                    f"Vocabulary collection '{collection_id}' entry {position} word must be a non-empty string."
                )
            normalized = normalize_vocabulary_word(word)
            if normalized in seen_words:
                raise VocabularyCatalogInvalid(
                    f"Vocabulary collection '{collection_id}' has duplicate word '{word}'."
                )
            seen_words.add(normalized)
            definition = entry["definition"]
            if not isinstance(definition, str) or not definition.strip():
                raise VocabularyCatalogInvalid(
                    f"Vocabulary collection '{collection_id}' entry '{word}' definition must be a non-empty string."
                )
            support_translations = entry["support_translations"]
            if not isinstance(support_translations, Mapping):
                raise VocabularyCatalogInvalid(
                    f"Vocabulary collection '{collection_id}' entry '{word}' support_translations must be a mapping."
                )


def _denormalized_entries(collection: Mapping[str, Any]) -> list[dict[str, Any]]:
    origin = collection.get("provenance", {}).get("origin", "curated")
    entries: list[dict[str, Any]] = []
    for raw_entry in collection["entries"]:
        entry = dict(raw_entry)
        entry["language_code"] = collection["language_code"]
        entry["framework"] = collection["framework"]
        entry["collection_id"] = collection["id"]
        entry["origin"] = origin
        entry.setdefault("level", collection.get("level"))
        entry.setdefault("topic", collection.get("topic"))
        entry["normalized_word"] = normalize_vocabulary_word(entry.get("word"))
        entries.append(entry)
    return entries


def _build_catalog(raw_collections: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    for collection in raw_collections:
        entries = _denormalized_entries(collection)
        catalog[collection["id"]] = {
            "id": collection["id"],
            "language_code": collection["language_code"],
            "framework": collection["framework"],
            "level": collection["level"],
            "topic": collection.get("topic"),
            "title": collection["title"],
            "provenance": collection["provenance"],
            "item_count": len(entries),
            "entries": entries,
        }
    return catalog


def _build_word_index(
    catalog: Mapping[str, Mapping[str, Any]]
) -> dict[tuple[str, str], list[str]]:
    index: dict[tuple[str, str], list[str]] = {}
    for collection_id, collection in catalog.items():
        language_code = collection["language_code"]
        for entry in collection["entries"]:
            key = (language_code, entry["normalized_word"])
            bucket = index.setdefault(key, [])
            if collection_id not in bucket:
                bucket.append(collection_id)
    return index


_RAW_COLLECTIONS: list[Mapping[str, Any]] = [*_ENGLISH_COLLECTIONS, *_CHINESE_COLLECTIONS]
_CATALOG_BY_ID = _build_catalog(_RAW_COLLECTIONS)
_WORD_INDEX = _build_word_index(_CATALOG_BY_ID)


def _summary(collection: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": collection["id"],
        "language_code": collection["language_code"],
        "framework": collection["framework"],
        "level": collection["level"],
        "topic": collection.get("topic"),
        "title": collection["title"],
        "item_count": collection["item_count"],
        "provenance": collection["provenance"],
    }


def list_vocabulary_collections(language_code: str) -> list[dict[str, Any]]:
    """Summaries for every collection in ``language_code``, sorted by
    ``framework``, then ``level``, then ``title``."""

    language = str(language_code or "").strip().casefold()
    summaries = [
        _summary(collection)
        for collection in _CATALOG_BY_ID.values()
        if collection["language_code"] == language
    ]
    summaries.sort(key=lambda summary: (summary["framework"], summary["level"], summary["title"]))
    return summaries


def get_vocabulary_collection(collection_id: str) -> dict[str, Any] | None:
    """The collection summary plus its raw denormalized ``entries``, or
    ``None`` when ``collection_id`` is not a known collection."""

    collection = _CATALOG_BY_ID.get(str(collection_id or "").strip())
    if collection is None:
        return None
    summary = _summary(collection)
    summary["entries"] = [dict(entry) for entry in collection["entries"]]
    return summary


def all_vocabulary_entries(language_code: str) -> list[dict[str, Any]]:
    """Every denormalized entry across every collection for ``language_code``."""

    language = str(language_code or "").strip().casefold()
    entries: list[dict[str, Any]] = []
    for collection in _CATALOG_BY_ID.values():
        if collection["language_code"] == language:
            entries.extend(dict(entry) for entry in collection["entries"])
    return entries


def collection_ids_for_word(language_code: str, normalized_word: str) -> list[str]:
    """Curated collection ids containing ``normalized_word``, or ``[]`` when
    the word is not in any curated collection for that language.

    Built from the load-time index; no database membership table and no
    invented match.
    """

    language = str(language_code or "").strip().casefold()
    word = normalize_vocabulary_word(normalized_word)
    return list(_WORD_INDEX.get((language, word), []))
