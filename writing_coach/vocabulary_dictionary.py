"""Complete imported vocabulary rows with dictionary facts from vendored data, never from a model.

A word list often arrives as headwords only. A reading (pinyin) is a dataset fact
(`docs/ORENA_AI_COST_REDUCTION_PLAN.md`, rule 1), so the importer looks it up in
the language's vendored dictionary at the content boundary and stores it with the
entry, once (D-121). Meanings are not handled here: a meaning in a support
language is a localization of the sense (`vocabulary_localization.py`, D-124).

The source always wins: a reading the row already carries is never replaced, and
the row's lexical identity is left untouched. What the dictionary adds is marked
``origin: "dictionary"`` and the provenance names the release and licence.
Languages are adapters (`ARCHITECTURE_INVARIANTS.md`): Chinese has CC-CEDICT;
English rows are returned unchanged.
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from writing_coach.languages.chinese import lexicon as chinese_lexicon


@dataclass(frozen=True)
class DictionaryFacts:
    reading: str = ""


@dataclass(frozen=True)
class DictionaryAdapter:
    lookup: Callable[[str], DictionaryFacts | None]
    provenance: Callable[[], Mapping[str, Any]]
    available: Callable[[], bool]


def _chinese_facts(term: str) -> DictionaryFacts | None:
    reading = chinese_lexicon.reading(term)
    return DictionaryFacts(reading=reading) if reading else None


_ADAPTERS: dict[str, DictionaryAdapter] = {
    "zh": DictionaryAdapter(
        lookup=_chinese_facts,
        provenance=chinese_lexicon.provenance,
        available=chinese_lexicon.installed,
    ),
}


def dictionary_for(language_code: str) -> DictionaryAdapter | None:
    adapter = _ADAPTERS.get(str(language_code or "").strip().casefold().split("-", 1)[0])
    return adapter if adapter is not None and adapter.available() else None


def complete_from_dictionary(
    records: Sequence[Mapping[str, Any]], language_code: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return the rows with missing dictionary readings filled, and what was filled."""

    adapter = dictionary_for(language_code)
    completed = [copy.deepcopy(dict(record)) for record in records]
    summary: dict[str, Any] = {"source": "", "readings": 0, "not_found": 0}
    if adapter is None:
        return completed, summary
    provenance = dict(adapter.provenance())
    summary["source"] = str(provenance.get("label") or provenance.get("source") or "")
    for record in completed:
        facts = adapter.lookup(str(record.get("term") or ""))
        if facts is None:
            summary["not_found"] += 1
            continue
        if facts.reading and not record.get("readings") and not record.get("pronunciations"):
            record["readings"] = [{"text": facts.reading, "kind": "reading", "origin": "dictionary"}]
            origins = dict(record.get("content_origins") or {})
            origins["readings"] = "dictionary"
            record["content_origins"] = origins
            record_provenance = dict(record.get("provenance") or {})
            record_provenance["dictionary"] = {**provenance, "fields": ["readings"]}
            record["provenance"] = record_provenance
            summary["readings"] += 1
    return completed, summary
