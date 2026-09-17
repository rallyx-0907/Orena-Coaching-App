"""Paragraph meaning for Reading, through the engine Listening already translates with.

The provider, its batching limits and its no-failover rule are the shared ones in
`media_translation.py`; only the unit differs. A reading paragraph has no timing,
so it travels as its id and its text, and each paragraph is cached on its own:
a learner who opens one meaning and later asks for all of them pays only for
the ones not already fetched.
"""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from writing_coach.core.support_languages import normalize_support_language
from writing_coach.media_ingestion import primary_language
from writing_coach.media_translation import (
    TranslationProvider,
    TranslationProviderError,
    build_translation_batches,
)

DEFAULT_READING_TRANSLATION_CACHE_ENTRIES = 4096


@dataclass(frozen=True)
class TextSegment:
    segment_id: str
    original_text: str


class ReadingTranslationStatus(StrEnum):
    READY = "ready"
    NOT_REQUIRED = "not_required"
    TOO_LARGE = "too_large"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ReadingTranslation:
    status: ReadingTranslationStatus
    source_language: str
    target_language: str
    translations: tuple[tuple[str, str], ...] = ()


class ReadingTranslationService:
    def __init__(
        self,
        provider: TranslationProvider,
        *,
        cache_entries: int = DEFAULT_READING_TRANSLATION_CACHE_ENTRIES,
    ) -> None:
        self._provider = provider
        self._cache_entries = max(1, int(cache_entries))
        self._cache: OrderedDict[str, str] = OrderedDict()
        self._lock = threading.Lock()

    def translate(
        self,
        source_language: str,
        target_language: str,
        segments: Sequence[TextSegment],
    ) -> ReadingTranslation:
        source = primary_language(source_language)
        target = normalize_support_language(target_language)

        def result(status: ReadingTranslationStatus, pairs=()) -> ReadingTranslation:
            return ReadingTranslation(status, source, target, tuple(pairs))

        if source == target:
            return result(ReadingTranslationStatus.NOT_REQUIRED)

        known: dict[str, str] = {}
        missing: list[TextSegment] = []
        for segment in segments:
            cached = self._cached(self._key(source, target, segment.original_text))
            if cached is None:
                missing.append(segment)
            else:
                known[segment.segment_id] = cached

        if missing:
            batches = build_translation_batches(tuple(missing))
            if batches is None:
                return result(ReadingTranslationStatus.TOO_LARGE)
            generated: dict[str, str] = {}
            try:
                for batch in batches:
                    translated = self._provider.translate_batch(source, target, batch)
                    expected = {segment.segment_id for segment in batch}
                    if set(translated) != expected or any(
                        not str(value).strip() for value in translated.values()
                    ):
                        return result(ReadingTranslationStatus.UNAVAILABLE)
                    generated.update(translated)
            except TranslationProviderError:
                return result(ReadingTranslationStatus.UNAVAILABLE)
            # Kept only once every batch of the request came back whole, so a
            # partial answer is never served later as if it had been sound.
            for segment in missing:
                meaning = generated[segment.segment_id].strip()
                self._remember(self._key(source, target, segment.original_text), meaning)
                known[segment.segment_id] = meaning

        return result(
            ReadingTranslationStatus.READY,
            ((segment.segment_id, known[segment.segment_id]) for segment in segments),
        )

    def _key(self, source: str, target: str, text: str) -> str:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return (
            f"{self._provider.engine_id}:{self._provider.model_version}:"
            f"{source}:{target}:{digest}"
        )

    def _cached(self, key: str) -> str | None:
        with self._lock:
            value = self._cache.get(key)
            if value is not None:
                self._cache.move_to_end(key)
            return value

    def _remember(self, key: str, value: str) -> None:
        with self._lock:
            self._cache[key] = value
            self._cache.move_to_end(key)
            while len(self._cache) > self._cache_entries:
                self._cache.popitem(last=False)
