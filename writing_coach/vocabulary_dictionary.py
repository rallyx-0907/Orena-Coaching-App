"""Complete imported vocabulary rows from vendored dictionary data, never from a model.

A word list arrives with whatever its author typed: often a headword and nothing
else. The facts it leaves out - a reading, a dictionary meaning - are dataset
facts (`docs/ORENA_AI_COST_REDUCTION_PLAN.md`, rule 1), so the importer looks
them up in the language's vendored dictionary at the content boundary and stores
them with the entry, once (D-121). A learner opening the collection reads them;
nothing is generated or translated on the way.

The source always wins. A field the row already carries is never replaced, a
meaning whose language the source did not state is never second-guessed, and
the row's lexical identity (computed from the source) is left untouched. What
the dictionary adds is marked ``origin: "dictionary"`` and the entry's
provenance names the release and licence it came from.

Languages are adapters (`ARCHITECTURE_INVARIANTS.md`): Chinese has a vendored
dictionary (CC-CEDICT, English senses and pinyin). English has no vendored
bilingual data yet, so English rows are returned unchanged - an honest gap, not
a reason to call a model.
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
    meanings: Mapping[str, str] | None = None  # support language -> meaning


@dataclass(frozen=True)
class DictionaryAdapter:
    lookup: Callable[[str], DictionaryFacts | None]
    provenance: Callable[[], Mapping[str, Any]]
    available: Callable[[], bool]


def _chinese_facts(term: str) -> DictionaryFacts | None:
    meaning = chinese_lexicon.short_meaning(term)
    reading = chinese_lexicon.reading(term)
    if not meaning and not reading:
        return None
    return DictionaryFacts(reading=reading, meanings={"en": meaning} if meaning else {})


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


def _stated_languages(meanings: Sequence[Any]) -> set[str] | None:
    """The languages the source's meanings are in, or None when one is unstated."""

    languages: set[str] = set()
    for item in meanings:
        if not isinstance(item, Mapping) or not str(item.get("text") or "").strip():
            continue
        language = str(item.get("language") or "").strip().casefold()
        if not language or language == "unknown":
            return None
        languages.add(language)
    return languages


def complete_from_dictionary(
    records: Sequence[Mapping[str, Any]], language_code: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return the rows with missing dictionary facts filled, and what was filled."""

    adapter = dictionary_for(language_code)
    completed = [copy.deepcopy(dict(record)) for record in records]
    summary: dict[str, Any] = {"source": "", "readings": 0, "meanings": 0, "not_found": 0}
    if adapter is None:
        return completed, summary
    provenance = dict(adapter.provenance())
    summary["source"] = str(provenance.get("label") or provenance.get("source") or "")
    for record in completed:
        facts = adapter.lookup(str(record.get("term") or ""))
        if facts is None:
            summary["not_found"] += 1
            continue
        added: list[str] = []
        origins = dict(record.get("content_origins") or {})
        if facts.reading and not record.get("readings") and not record.get("pronunciations"):
            record["readings"] = [{"text": facts.reading, "kind": "reading", "origin": "dictionary"}]
            origins["readings"] = "dictionary"
            added.append("readings")
            summary["readings"] += 1
        meanings = list(record.get("short_meanings") or [])
        stated = _stated_languages(meanings)
        if stated is not None:
            new = [
                {"language": language, "text": text, "origin": "dictionary"}
                for language, text in (facts.meanings or {}).items()
                if text and language not in stated
            ]
            if new:
                record["short_meanings"] = [*meanings, *new]
                origins.setdefault("short_meanings", "dictionary")
                added.append("short_meanings")
                summary["meanings"] += 1
        if added:
            record["content_origins"] = origins
            record_provenance = dict(record.get("provenance") or {})
            record_provenance["dictionary"] = {**provenance, "fields": added}
            record["provenance"] = record_provenance
    return completed, summary
