"""Localize vocabulary senses into support languages from data and free offline tools (D-124).

A vocabulary sense exists once. The meaning a learner reads in their support
language is a localization of that sense, obtained at the content boundary by a
registered **localization source** for the (target language, support language)
pair, checked deterministically, and stored with the content. Learner use after
publication only reads it.

Sources, asked in this order for each pair, first valid answer kept:

1. the imported list's own meaning in that language - never overwritten;
2. vendored open lexical data (``dictionary``): zh -> en from CC-CEDICT;
3. free offline pivot translation (``pivot_translation``): the repository's own
   Marian service translates a dictionary sense - never a bare headword when a
   sense exists - into the support language. A pivot pair runs only when an
   operator has enabled it (``VOCABULARY_PIVOT_PAIRS``, e.g. ``zh:vi,en:vi``)
   after sampling its quality; unsampled machine output is never published.

No paid model is a source. Adding a support language is registering a source
for its pairs and re-running preparation - no product code changes.
"""

from __future__ import annotations

import copy
import os
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from writing_coach.core.support_languages import (
    AVAILABLE_SUPPORT_LANGUAGES,
    support_language_uses_cjk,
)
from writing_coach.languages.chinese import lexicon as chinese_lexicon

VALIDATION_RULE = "vocabulary-localization-v1"
MAX_GLOSS_CHARS = 160
PIVOT_PAIRS_ENV = "VOCABULARY_PIVOT_PAIRS"
PIVOT_BATCH_SIZE = 24  # the local Marian service's request ceiling

_HAN = re.compile(r"[㐀-鿿豈-﫿]")
_BOOKKEEPING = re.compile(r"^(CL:|see |variant of |old variant of |abbr\. for )", re.IGNORECASE)


@dataclass(frozen=True)
class SenseInput:
    """What a source may use to localize one sense: its words, never a learner."""

    key: str
    term: str
    part_of_speech: str = ""
    # The sense's meanings already known, by language (source list, earlier sources).
    meanings: Mapping[str, str] = field(default_factory=dict)


class LocalizationSource(Protocol):
    source_id: str
    method: str

    def available(self) -> bool: ...
    def provenance(self) -> dict[str, Any]: ...
    def localize(self, target: str, support: str, senses: Sequence[SenseInput]) -> dict[str, str]: ...


def checked_gloss(term: str, gloss: object, support: str) -> str:
    """The gloss when it passes the deterministic checks, else ``""``."""

    clean = " ".join(str(gloss or "").split()).strip(" ;,")
    if not clean or len(clean) > MAX_GLOSS_CHARS:
        return ""
    if clean.casefold() == " ".join(str(term).split()).casefold():
        return ""  # an untranslated echo is not a meaning
    if _BOOKKEEPING.match(clean):
        return ""
    has_han = bool(_HAN.search(clean))
    if not support_language_uses_cjk(support) and has_han:
        return ""
    if support == "zh" and not has_han:
        return ""
    return clean


class ChineseDictionarySource:
    """zh -> en from the vendored CC-CEDICT pack."""

    source_id = "cc-cedict"
    method = "dictionary"

    def available(self) -> bool:
        return chinese_lexicon.installed()

    def provenance(self) -> dict[str, Any]:
        return dict(chinese_lexicon.provenance())

    def localize(self, target: str, support: str, senses: Sequence[SenseInput]) -> dict[str, str]:
        if target != "zh" or support != "en":
            return {}
        return {
            sense.key: meaning
            for sense in senses
            if (meaning := chinese_lexicon.short_meaning(sense.term))
        }


class PivotTranslationSource:
    """Free offline translation of a known sense into the support language.

    For a sense that already has an English meaning (from the list or the
    dictionary), that meaning is translated; an English headword with no
    English gloss is translated as itself. ``translate`` is the local Marian
    service's batch call, ``(source, target, [(id, text)]) -> {id: text}``.
    """

    method = "pivot_translation"

    def __init__(
        self,
        translate: Callable[[str, str, Sequence[tuple[str, str]]], Mapping[str, str]],
        *,
        engine: str,
        model_version: str,
        pairs: Iterable[tuple[str, str]],
        available: Callable[[], bool] = lambda: True,
    ) -> None:
        self._translate = translate
        self._pairs = frozenset(pairs)
        self._available = available
        self.source_id = engine
        self._model_version = model_version

    def available(self) -> bool:
        return bool(self._pairs) and self._available()

    def provenance(self) -> dict[str, Any]:
        return {"source": self.source_id, "model": self._model_version, "license": "repository service"}

    def localize(self, target: str, support: str, senses: Sequence[SenseInput]) -> dict[str, str]:
        if (target, support) not in self._pairs:
            return {}
        items: list[tuple[str, str]] = []
        for sense in senses:
            english = sense.meanings.get("en", "")
            if english:
                items.append((sense.key, english))
            elif target == "en":
                items.append((sense.key, sense.term))
        result: dict[str, str] = {}
        for start in range(0, len(items), PIVOT_BATCH_SIZE):
            batch = items[start:start + PIVOT_BATCH_SIZE]
            try:
                answer = self._translate("en", support, batch)
            except Exception:  # noqa: BLE001 - an unavailable engine leaves the gap, it never fails an import
                break
            result.update({key: str(text) for key, text in answer.items() if key in dict(batch)})
        return result


def enabled_pivot_pairs(env: Mapping[str, str] | None = None) -> tuple[tuple[str, str], ...]:
    """Operator-enabled pivot pairs, ``target:support`` comma-separated."""

    raw = (os.environ if env is None else env).get(PIVOT_PAIRS_ENV, "")
    pairs: list[tuple[str, str]] = []
    for part in str(raw).split(","):
        target, _, support = part.strip().casefold().partition(":")
        if target and support in AVAILABLE_SUPPORT_LANGUAGES and target != support:
            pairs.append((target, support))
    return tuple(pairs)


def _meanings_by_language(record: Mapping[str, Any]) -> tuple[dict[str, str], bool]:
    """The record's meanings by stated language, and whether any language is unstated."""

    known: dict[str, str] = {}
    unstated = False
    for item in record.get("short_meanings") or []:
        if not isinstance(item, Mapping) or not str(item.get("text") or "").strip():
            continue
        language = str(item.get("language") or "").strip().casefold()
        if not language or language == "unknown":
            unstated = True
            continue
        known.setdefault(language, " ".join(str(item["text"]).split()))
    return known, unstated


@dataclass
class LanguageReport:
    language: str
    from_list: int = 0
    added: dict[str, int] = field(default_factory=dict)
    rejected: int = 0
    missing: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "from_list": self.from_list,
            "added": dict(self.added),
            "rejected": self.rejected,
            "missing": self.missing,
        }


def localize_records(
    records: Sequence[Mapping[str, Any]],
    target_language: str,
    sources: Sequence[LocalizationSource],
    support_languages: Sequence[str] = AVAILABLE_SUPPORT_LANGUAGES,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return the records with missing localizations added, and a per-language report.

    Only languages some available source can serve are attempted and reported.
    A record whose meanings include one of unstated language is left alone: the
    source said something in a language it did not name, and guessing which
    would put a meaning under the wrong language.
    """

    target = str(target_language or "").strip().casefold().split("-", 1)[0]
    completed = [copy.deepcopy(dict(record)) for record in records]
    live = [source for source in sources if source.available()]
    reports: list[dict[str, Any]] = []
    for support in support_languages:
        if support == target:
            continue
        report = LanguageReport(language=support)
        pending: list[tuple[int, SenseInput]] = []
        for index, record in enumerate(completed):
            known, unstated = _meanings_by_language(record)
            if support in known:
                report.from_list += 1
            elif not unstated:
                pending.append((index, SenseInput(
                    key=str(index),
                    term=str(record.get("term") or ""),
                    part_of_speech=str(record.get("part_of_speech") or ""),
                    meanings=known,
                )))
        if not pending:
            if report.from_list:
                reports.append(report.to_dict())
            continue
        attempted = False
        for source in live:
            remaining = [sense for _, sense in pending]
            if not remaining:
                break
            answers = source.localize(target, support, remaining)
            if answers:
                attempted = True
            accepted: set[str] = set()
            for sense in remaining:
                gloss = checked_gloss(sense.term, answers.get(sense.key), support)
                if not gloss:
                    if sense.key in answers:
                        report.rejected += 1
                    continue
                record = completed[int(sense.key)]
                record["short_meanings"] = [
                    *(record.get("short_meanings") or []),
                    {"language": support, "text": gloss, "origin": source.method},
                ]
                origins = dict(record.get("content_origins") or {})
                origins.setdefault("short_meanings", source.method)
                record["content_origins"] = origins
                provenance = dict(record.get("provenance") or {})
                localizations = dict(provenance.get("localizations") or {})
                localizations[support] = {**source.provenance(), "method": source.method, "rule": VALIDATION_RULE}
                provenance["localizations"] = localizations
                record["provenance"] = provenance
                report.added[source.source_id] = report.added.get(source.source_id, 0) + 1
                accepted.add(sense.key)
            pending = [(index, sense) for index, sense in pending if sense.key not in accepted]
            # A later source sees what an earlier one produced (a pivot needs the English sense).
            pending = [
                (index, SenseInput(sense.key, sense.term, sense.part_of_speech,
                                   _meanings_by_language(completed[index])[0]))
                for index, sense in pending
            ]
        report.missing = len(pending)
        if attempted or report.from_list or report.added:
            reports.append(report.to_dict())
    return completed, reports


def default_sources() -> list[LocalizationSource]:
    """The registered sources for this deployment: data first, then enabled offline pivots."""

    sources: list[LocalizationSource] = [ChineseDictionarySource()]
    pairs = enabled_pivot_pairs()
    if pairs:
        from writing_coach.media_translation import LocalHttpTranslationProvider
        from writing_coach.reading_translation import TextSegment

        # Always the repository's own local service, whatever engine Listening uses:
        # a paid translator is never a vocabulary localization source.
        provider = LocalHttpTranslationProvider(
            os.getenv("LOCAL_TRANSLATION_URL", "http://local-translator:8090")
        )

        def translate(source: str, target: str, batch: Sequence[tuple[str, str]]) -> Mapping[str, str]:
            return provider.translate_batch(
                source, target, tuple(TextSegment(key, text) for key, text in batch)
            )

        sources.append(
            PivotTranslationSource(
                translate,
                engine=provider.engine_id,
                model_version=provider.model_version,
                pairs=pairs,
            )
        )
    return sources
