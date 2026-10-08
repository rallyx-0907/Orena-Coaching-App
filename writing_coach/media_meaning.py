"""Segment meaning in the learner's support language, resolved once and kept.

A curated lesson ships with pre-authored translations for a few languages. A
learner whose support language is not one of them still needs meaning, so the
live translation service fills the gap - but calling a paid provider every time
somebody opens a lesson would be indefensible, so generated meaning is persisted
and reused.

Resolution order, and the reason for it:

    1. pre-authored / reviewed translation   - a human wrote it; never override
                                               it with machine output
    2. persisted generated translation       - already paid for, reuse it
    3. live MediaTranslationService          - generate once, then persist
    4. truthful unavailable                  - only when translation actually
                                               failed

The canonical transcript is never modified and never duplicated per language.
Meaning travels beside it.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Any, Protocol

# Where a meaning came from. A learner is entitled to know whether a human wrote
# it, and a reviewed translation must never be relabelled as machine output.
PROVENANCE_EDITORIAL = "editorial"
PROVENANCE_GENERATED = "generated"
PROVENANCE_CACHED_GENERATED = "cached-generated"

# Cache identity version. Bumping it invalidates every stored meaning, which is
# the escape hatch if the key ever has to change shape.
CACHE_SCHEMA = "v1"


class TranslationCache(Protocol):
    def get_media_translation(self, key: str) -> dict[str, Any] | None: ...
    def put_media_translation(
        self, key: str, translated_text: str, provenance: str, generated_at: str
    ) -> None: ...


@dataclass(frozen=True)
class SegmentMeaning:
    segment_id: str
    target_language: str
    translated_meaning: str
    provenance: str


@dataclass(frozen=True)
class MeaningOutcome:
    """What the learner gets, and how much it cost to get it."""

    meanings: tuple[SegmentMeaning, ...]
    status: str                  # ready | not_required | unavailable
    provider_calls: int          # 0 when everything was pre-authored or cached
    failure_kind: str | None = None


def text_fingerprint(text: str) -> str:
    """Identity of the source text, so a canonical edit invalidates its meaning."""

    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()[:32]


def cache_key(
    asset_id: str,
    segment_id: str,
    source_text: str,
    support_language: str,
    provider_model: str,
) -> str:
    """The whole identity in one key.

    Asset and segment locate it; the text fingerprint expires it when canonical
    text changes; the language and the provider/model keep two different answers
    from colliding.
    """

    parts = (
        CACHE_SCHEMA, asset_id, segment_id,
        text_fingerprint(source_text), support_language, provider_model,
    )
    return hashlib.sha256(" ".join(parts).encode("utf-8")).hexdigest()


def _preauthored_index(preauthored: Sequence[Any], support_language: str) -> dict[str, str]:
    index: dict[str, str] = {}
    for item in preauthored or ():
        language = str(getattr(item, "target_language", "") or "").casefold()
        if language != support_language:
            continue
        text = str(getattr(item, "translated_meaning", "") or "").strip()
        if text:
            index[str(getattr(item, "segment_id", ""))] = text
    return index


def resolve_segment_meanings(
    *,
    asset_id: str,
    segments: Sequence[Any],
    support_language: str,
    source_language: str,
    preauthored: Sequence[Any] = (),
    cache: TranslationCache | None = None,
    translate: Any = None,
    provider_model: str = "unknown",
    now: str | None = None,
) -> MeaningOutcome:
    """Resolve meaning for every segment, spending as little as possible.

    `translate` is called at most once per request, and only for the segments
    that are neither pre-authored nor already cached, so the second learner in a
    given language costs nothing.
    """

    target = str(support_language or "").strip().casefold()
    if not target or not segments:
        return MeaningOutcome((), "unavailable", 0, "no_target_language")
    if target == str(source_language or "").strip().casefold():
        return MeaningOutcome((), "not_required", 0)

    editorial = _preauthored_index(preauthored, target)
    resolved: dict[str, SegmentMeaning] = {}
    missing: list[Any] = []

    for segment in segments:
        segment_id = str(getattr(segment, "segment_id", ""))
        if segment_id in editorial:
            resolved[segment_id] = SegmentMeaning(
                segment_id, target, editorial[segment_id], PROVENANCE_EDITORIAL)
            continue
        text = str(getattr(segment, "original_text", "") or "")
        hit = None
        if cache is not None:
            hit = cache.get_media_translation(
                cache_key(asset_id, segment_id, text, target, provider_model))
        if hit and str(hit.get("translated_text") or "").strip():
            resolved[segment_id] = SegmentMeaning(
                segment_id, target, str(hit["translated_text"]), PROVENANCE_CACHED_GENERATED)
            continue
        missing.append(segment)

    provider_calls = 0
    if missing and translate is not None:
        provider_calls = 1
        generated = translate(tuple(missing), target)
        if not generated:
            # The original transcript stays usable; only meaning is missing.
            return MeaningOutcome(
                tuple(resolved[str(getattr(s, "segment_id", ""))] for s in segments
                      if str(getattr(s, "segment_id", "")) in resolved),
                "unavailable", provider_calls, "translation_failed")
        stamp = now or datetime.now(UTC).isoformat()
        for segment in missing:
            segment_id = str(getattr(segment, "segment_id", ""))
            text = str(generated.get(segment_id) or "").strip()
            if not text:
                continue
            resolved[segment_id] = SegmentMeaning(
                segment_id, target, text, PROVENANCE_GENERATED)
            if cache is not None:
                cache.put_media_translation(
                    cache_key(asset_id, segment_id,
                              str(getattr(segment, "original_text", "") or ""),
                              target, provider_model),
                    text, PROVENANCE_GENERATED, stamp,
                )

    ordered = tuple(
        resolved[str(getattr(segment, "segment_id", ""))]
        for segment in segments
        if str(getattr(segment, "segment_id", "")) in resolved
    )
    if not ordered:
        return MeaningOutcome((), "unavailable", provider_calls, "translation_unavailable")
    if len(ordered) != len(segments):
        return MeaningOutcome(ordered, "unavailable", provider_calls, "translation_incomplete")
    return MeaningOutcome(ordered, "ready", provider_calls)


def pinyin_for_segments(segments: Sequence[Any]) -> Mapping[str, str]:
    """Toned Pinyin per Chinese segment.

    A reading of the Hanzi, so it does not vary with the support language and is
    not a translation. Timing is never derived from it.
    """

    try:
        from pypinyin import Style, lazy_pinyin
    except ImportError:  # pragma: no cover - dependency is installed in the app image
        return {}

    readings: dict[str, str] = {}
    for segment in segments or ():
        text = str(getattr(segment, "original_text", "") or "")
        # lazy_pinyin passes non-Chinese text straight through, which would show
        # an English line back to the learner as though it were a reading.
        if not text or not any("一" <= ch <= "鿿" for ch in text):
            continue
        reading = " ".join(lazy_pinyin(text, style=Style.TONE)).strip()
        if reading:
            readings[str(getattr(segment, "segment_id", ""))] = reading
    return readings
