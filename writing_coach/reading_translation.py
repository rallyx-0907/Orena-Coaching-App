"""Sentence and paragraph meaning for Reading, generated on demand and kept.

The provider, its batching limits and its no-failover rule are the shared ones in
`media_translation.py`; only the unit differs. A reading unit has no timing, so it
travels as its id and its text. The unit that is cached is the *sentence text*: the key is the normalized
text with the learning and support languages (`reading_derived.py`), never the segment id, so the Reader's
paragraph (its sentences, each asked for on its own) and the Sentence Quick Sheet share one entry and a sentence
is generated once, ever. A learner who opens one meaning and later asks for all of them pays only for the
ones not already fetched.

Engines (`READING_TRANSLATION_PROVIDER`, chosen once at start-up, never a runtime failover):
`ai` (default; the platform's `learner_translation` capability, so the operator's provider/model choice and
cost record apply), `local` (the Marian service) and `groq`.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from writing_coach.core.support_languages import normalize_support_language, support_language
from writing_coach.media_ingestion import primary_language
from writing_coach.media_translation import (
    TranslationBatch,
    TranslationProvider,
    TranslationProviderError,
    build_translation_batches,
)
from writing_coach.reading_derived import (
    DEFAULT_ENTRIES,
    KIND_TRANSLATION,
    DerivedCache,
    content_key,
    normalize_text,
)

DEFAULT_READING_TRANSLATION_CACHE_ENTRIES = DEFAULT_ENTRIES

READING_TRANSLATION_PROVIDER_IDS = ("ai", "local", "groq")
DEFAULT_READING_TRANSLATION_PROVIDER = "ai"


def resolve_reading_translation_provider_id(configured: str, *, groq_key: str) -> str:
    """Which engine translates reading text, decided once from configuration.

    The default is `ai`: translation is generated on demand by the platform AI and cached (human decision
    2026-10-05). Reading never inherits Listening's engine choice, and `local` or `groq` are used only when an
    operator explicitly asks for them (`ARCHITECTURE_INVARIANTS.md`: no silent provider fallback, no automatic
    failover between engines).
    """
    chosen = str(configured or "").strip().casefold() or DEFAULT_READING_TRANSLATION_PROVIDER
    if chosen not in READING_TRANSLATION_PROVIDER_IDS:
        raise ValueError(
            "READING_TRANSLATION_PROVIDER must be "
            + " or ".join(repr(item) for item in READING_TRANSLATION_PROVIDER_IDS)
            + "."
        )
    if chosen == "groq" and not str(groq_key or "").strip():
        raise ValueError("READING_TRANSLATION_PROVIDER='groq' requires GROQ_API_KEY.")
    return chosen


_TRANSLATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "translations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "string"}, "text": {"type": "string"}},
                "required": ["id", "text"],
            },
        }
    },
    "required": ["translations"],
}


def _platform_generate(**kwargs: Any) -> dict[str, Any]:
    from writing_coach.ai.base import AICapabilityError, AIProviderError
    from writing_coach.ai.platform import generate_structured

    try:
        result = generate_structured(capability_key="learner_translation", temperature=0.0, seed=42, **kwargs)
    except (AIProviderError, AICapabilityError) as exc:
        raise TranslationProviderError(type(exc).__name__) from exc
    return result.data if isinstance(result.data, dict) else {}


class PlatformAITranslationProvider:
    """Translation through the platform's `learner_translation` capability (one structured call per batch)."""

    engine_id = "ai"
    model_version = "learner_translation-v1"

    def __init__(self, generate: Callable[..., dict[str, Any]] = _platform_generate) -> None:
        self._generate = generate

    def translate_batch(
        self, source_language: str, target_language: str, segments: TranslationBatch
    ) -> dict[str, str]:
        source = support_language(source_language)
        target = support_language(target_language)
        source_name = source.translation_label if source else source_language
        target_name = target.translation_label if target else target_language
        items = [{"id": item.segment_id, "text": item.original_text} for item in segments]
        total = sum(len(item["text"]) for item in items)
        raw = self._generate(
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You translate {source_name} reading text for a learner into {target_name}. Give each "
                        "item's natural, faithful meaning as a fluent sentence a native speaker would write. "
                        "Translate only what is given: no notes, no explanations, no additions. Return every "
                        "id exactly once."
                    ),
                },
                {"role": "user", "content": json.dumps(items, ensure_ascii=False)},
            ],
            schema=_TRANSLATION_SCHEMA,
            max_output_tokens=max(400, min(4096, total * 3 + 60 * len(items))),
        )
        rows = raw.get("translations")
        if not isinstance(rows, list):
            raise TranslationProviderError("malformed translation answer")
        return {
            str(row.get("id")): str(row.get("text") or "")
            for row in rows
            if isinstance(row, dict) and row.get("id") is not None
        }


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
        cache: DerivedCache | None = None,
    ) -> None:
        self._provider = provider
        self._cache = cache if cache is not None else DerivedCache(entries=cache_entries)

    @property
    def uses_ai(self) -> bool:
        """Whether this engine is the platform AI. Word lookup stays non-AI (its contextual meaning is /word-detail)."""
        return self._provider.engine_id == "ai"

    def translate(
        self,
        source_language: str,
        target_language: str,
        segments: Sequence[TextSegment],
        *,
        persist: bool = False,
    ) -> ReadingTranslation:
        """`persist` lets the shared table hold the answers; the caller sets it only for published text."""
        source = primary_language(source_language)
        target = normalize_support_language(target_language)

        def result(status: ReadingTranslationStatus, pairs=()) -> ReadingTranslation:
            return ReadingTranslation(status, source, target, tuple(pairs))

        if source == target:
            return result(ReadingTranslationStatus.NOT_REQUIRED)

        keys = {segment.segment_id: self._key(source, segment.original_text) for segment in segments}
        cached = self._cache.get_many(KIND_TRANSLATION, target, keys.values(), persist=persist)
        known: dict[str, str] = {}
        missing: list[TextSegment] = []
        for segment in segments:
            hit = cached.get(keys[segment.segment_id])
            text = str(hit.get("text") or "") if hit else ""
            if text:
                known[segment.segment_id] = text
            else:
                missing.append(segment)

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
            rows: dict[str, dict[str, Any]] = {}
            for segment in missing:
                meaning = generated[segment.segment_id].strip()
                rows[keys[segment.segment_id]] = {"text": meaning}
                known[segment.segment_id] = meaning
            self._cache.put_many(
                KIND_TRANSLATION,
                target,
                source,
                list(rows.items()),
                persist=persist,
                provider=str(self._provider.engine_id),
                model=str(self._provider.model_version),
            )

        return result(
            ReadingTranslationStatus.READY,
            ((segment.segment_id, known[segment.segment_id]) for segment in segments),
        )

    @staticmethod
    def _key(source: str, text: str) -> str:
        return content_key(KIND_TRANSLATION, source, normalize_text(text))
