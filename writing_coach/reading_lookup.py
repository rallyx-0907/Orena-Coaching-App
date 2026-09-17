"""Non-LLM word/phrase lookup for Reading.

A learner tapping a word wants a fast, deterministic answer: the shared local
tagger, then the shared vocabulary catalog, then (English only) a monolingual
dictionary, then - only as a last resort - the reading-specific machine
translation engine. None of these are a language model; Explain
(`POST /api/dictionary/contextual`) is the only AI surface a selection can
reach, and it is a separate, explicit request.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from writing_coach.core.support_languages import normalize_support_language
from writing_coach.linguistic_annotation import annotate
from writing_coach.media_ingestion import primary_language
from writing_coach.persistence.vocabulary_repository import VocabularyContentUnavailable
from writing_coach.reading_translation import (
    ReadingTranslationService,
    ReadingTranslationStatus,
    TextSegment,
)
from writing_coach.vocabulary_library import normalize_vocabulary_word

_MAX_DICTIONARY_DEFINITIONS = 3


class VocabularyLookup(Protocol):
    def find_entry(self, language_code: str, normalized_term: str) -> dict[str, Any] | None: ...


@dataclass(frozen=True)
class LookupMeaning:
    text: str
    source: str


@dataclass(frozen=True)
class LookupDefinition:
    part_of_speech: str
    definition: str


@dataclass(frozen=True)
class LookupResult:
    selected_text: str
    source_language: str
    target_language: str
    base_form: str
    part_of_speech: str
    pronunciation: str
    audio_url: str
    meanings: tuple[LookupMeaning, ...]
    definitions: tuple[LookupDefinition, ...]

    @property
    def available(self) -> bool:
        return bool(self.meanings or self.definitions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_text": self.selected_text,
            "source_language": self.source_language,
            "target_language": self.target_language,
            "base_form": self.base_form,
            "part_of_speech": self.part_of_speech,
            "pronunciation": self.pronunciation,
            "audio_url": self.audio_url,
            "meanings": [{"text": item.text, "source": item.source} for item in self.meanings],
            "definitions": [
                {"part_of_speech": item.part_of_speech, "definition": item.definition}
                for item in self.definitions
            ],
            "available": self.available,
            "claim": "reading_lookup" if self.available else "reading_lookup_unavailable",
        }


def _local_token_facts(language: str, context: str, selection: str) -> dict[str, str]:
    """What the shared tagger knows about the selection where it stands.

    Tagged in its sentence rather than alone, because a word's class is a fact
    about its use. `lemma` is kept separately from `base_form`: the catalog
    fallback lookup wants a lemma in any language, while `base_form` is only
    ever surfaced from the tagger for Chinese (`ARCHITECTURE_INVARIANTS.md`).
    """

    found = re.search(re.escape(selection), context, flags=re.IGNORECASE)
    if found is None:
        return {"part_of_speech": "", "pronunciation": "", "base_form": "", "lemma": ""}
    start, end = found.span()
    tokens = [
        token
        for token in annotate(language, context)
        if token["start"] < end and token["end"] > start
    ]
    if not tokens:
        return {"part_of_speech": "", "pronunciation": "", "base_form": "", "lemma": ""}
    single = len(tokens) == 1 and tokens[0]["start"] == start and tokens[0]["end"] == end
    lemma = tokens[0]["lemma"] if single else ""
    return {
        "part_of_speech": tokens[0]["pos"] if single else "",
        "pronunciation": " ".join(token["pronunciation"] for token in tokens if token["pronunciation"]),
        "base_form": lemma if single and language == "zh" else "",
        "lemma": lemma,
    }


def _catalog_candidates(selection: str, lemma: str) -> list[str]:
    primary = normalize_vocabulary_word(selection)
    candidates = [primary] if primary else []
    secondary = normalize_vocabulary_word(lemma)
    if secondary and secondary != primary:
        candidates.append(secondary)
    return candidates


def _safe_find_entry(
    repository: VocabularyLookup, language: str, normalized_term: str
) -> dict[str, Any] | None:
    try:
        return repository.find_entry(language, normalized_term)
    except VocabularyContentUnavailable:
        return None


def _safe_english_dictionary(
    lookup: Callable[[str], dict[str, Any] | None], word: str
) -> dict[str, Any] | None:
    try:
        payload = lookup(word)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _safe_machine_translation(
    service: ReadingTranslationService, source: str, target: str, text: str
) -> str | None:
    try:
        result = service.translate(source, target, [TextSegment("selection", text)])
    except Exception:
        return None
    if result.status is not ReadingTranslationStatus.READY or not result.translations:
        return None
    return result.translations[0][1]


class ReadingLookupService:
    """Dictionary-first, translation-last word/phrase lookup. Never AI."""

    def __init__(
        self,
        vocabulary_repository: VocabularyLookup | None,
        english_dictionary: Callable[[str], dict[str, Any] | None],
        translation_service: ReadingTranslationService,
    ) -> None:
        self._vocabulary_repository = vocabulary_repository
        self._english_dictionary = english_dictionary
        self._translation_service = translation_service

    def lookup(
        self, text: str, context: str, source_language: str, target_language: str
    ) -> LookupResult:
        source = primary_language(source_language)
        target = normalize_support_language(target_language)
        selection = text.strip()

        local = _local_token_facts(source, context, selection)
        part_of_speech = local["part_of_speech"]
        pronunciation = local["pronunciation"]
        base_form = local["base_form"]
        audio_url = ""
        meanings: list[LookupMeaning] = []
        definitions: list[LookupDefinition] = []

        entry = None
        if self._vocabulary_repository is not None:
            for normalized in _catalog_candidates(selection, local["lemma"]):
                entry = _safe_find_entry(self._vocabulary_repository, source, normalized)
                if entry is not None:
                    break
        if entry is not None:
            for item in entry.get("short_meanings") or []:
                if not isinstance(item, dict):
                    continue
                if str(item.get("language") or "").strip().casefold() != target:
                    continue
                value = str(item.get("text") or "").strip()
                if value:
                    meanings.append(LookupMeaning(value, "collection"))
                    break
            if not pronunciation:
                pronunciation = str(entry.get("phonetic") or "").strip()
            if not part_of_speech:
                part_of_speech = str(entry.get("part_of_speech") or "").strip()
            if not base_form:
                base_form = str(entry.get("term") or "").strip()

        is_single_word = bool(selection) and len(selection.split()) == 1
        if source == "en" and is_single_word:
            payload = _safe_english_dictionary(self._english_dictionary, selection)
            if payload is not None:
                for item in (payload.get("definitions") or [])[:_MAX_DICTIONARY_DEFINITIONS]:
                    if not isinstance(item, dict):
                        continue
                    definition_text = str(item.get("definition") or "").strip()
                    if not definition_text:
                        continue
                    definitions.append(
                        LookupDefinition(str(item.get("part_of_speech") or "").strip(), definition_text)
                    )
                if not pronunciation:
                    pronunciation = str(payload.get("phonetic") or "").strip()
                if not audio_url:
                    audio_url = str(payload.get("audio") or "").strip()

        if not meanings and target != source:
            translated = _safe_machine_translation(self._translation_service, source, target, selection)
            if translated:
                meanings.append(LookupMeaning(translated, "machine_translation"))

        return LookupResult(
            selected_text=selection,
            source_language=source,
            target_language=target,
            base_form=base_form,
            part_of_speech=part_of_speech,
            pronunciation=pronunciation,
            audio_url=audio_url,
            meanings=tuple(meanings),
            definitions=tuple(definitions),
        )
