"""Authenticated, audio-free Active Listening progress boundary."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from writing_coach.core.errors import orena_http_error
from writing_coach.core.request_context import current_language_code
from writing_coach.listening_catalog import (
    catalog_lesson,
    catalog_lessons,
    discovery_rank,
    discovery_sections,
    lesson_metadata,
    translated_media_object,
)
from writing_coach.becoming_memory import get_learner_profile
from writing_coach.core.support_languages import resolve_support_language
from writing_coach.media_meaning import pinyin_for_segments, resolve_segment_meanings
from writing_coach.media_learning import MediaLearningObject, MediaTranscript
from writing_coach.media_translation import MediaTranslationStatus
from writing_coach.media_api import media_translation_service
from writing_coach.media_api import serialize_media_acquisition
from writing_coach.media_ingestion import MediaAcquisition
from writing_coach.persistence.specialized_repository import SpecializedLearningRepository


router = APIRouter(prefix="/api/listening", tags=["listening"])
_repository: SpecializedLearningRepository | None = None
# LISTENING_PRODUCT_SPEC 3.4, in the order the learner should meet them.
# `continue-learning` stays first and is filled from real progress, so it is
# empty until a learner has some. `popular` is listed but never populated: there
# is no popularity signal yet, and the spec allows that rail only with real data.
_DISCOVERY_SECTION_ORDER = (
    "continue-learning",
    "recommended",
    "quick-practice",
    "movie-animation",
    "daily-conversations",
    "stories",
    "podcast-interview",
    "science-technology",
    "culture",
    "kids-family",
    "dictation",
    "shadowing",
    "new",
    "popular",
    "audio-practice",
    "beginner",
    "intermediate",
    "advanced",
    "needs-review",
)


class ListeningProgressIn(BaseModel):
    asset_id: str = Field(min_length=1, max_length=255)
    segment_id: str = Field(min_length=1, max_length=255)
    presentation: Literal["prompt", "checked", "revealed"] = "prompt"
    revealed: bool = False
    checked_attempt_count: int = Field(default=0, ge=0, le=1000)
    best_accuracy_percent: int | None = Field(default=None, ge=0, le=100)
    best_exact: bool = False
    last_answer: str = Field(default="", max_length=2000)


class ShadowingProgressIn(BaseModel):
    asset_id: str = Field(min_length=1, max_length=255)
    segment_id: str = Field(min_length=1, max_length=255)
    completed_rounds: int = Field(default=0, ge=0, le=1000)


def configure_listening_progress(repository: SpecializedLearningRepository | None) -> None:
    global _repository
    _repository = repository


def _installed() -> SpecializedLearningRepository:
    if _repository is None:
        raise orena_http_error(
            503,
            "listening_progress_unconfigured",
            "Active Listening progress is not configured on this environment.",
        )
    return _repository


def _clean_identity(value: str, field: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise orena_http_error(422, "listening_progress_invalid", f"{field} must not be empty.")
    return cleaned


@router.get("/library")
def listening_library(
    language: str | None = Query(default=None, min_length=2, max_length=32),
    level: str | None = Query(default=None, min_length=1, max_length=32),
    topic: str | None = Query(default=None, min_length=1, max_length=64),
    tag: str | None = Query(default=None, min_length=1, max_length=64),
) -> dict[str, Any]:
    """Return lightweight discovery metadata; transcripts load per lesson."""
    selected_language = (language or current_language_code()).strip().casefold()
    items = catalog_lessons(language=selected_language, level=level, topic=topic, tag=tag)
    # Real poster-backed video leads every rail, so the first viewport is media
    # rather than seed audio (spec 3.5). The order is deterministic.
    ranked = sorted(items, key=discovery_rank)
    item_metadata = [lesson_metadata(lesson) for lesson in ranked]
    membership = {lesson.lesson_id: discovery_sections(lesson) for lesson in ranked}
    sections = [
        {
            "id": section_id,
            "item_ids": [
                lesson.lesson_id for lesson in ranked
                if section_id in membership[lesson.lesson_id]
            ],
        }
        for section_id in _DISCOVERY_SECTION_ORDER
    ]
    return {
        "items": item_metadata,
        "sections": [section for section in sections if section["item_ids"]],
        "topics": sorted({lesson.topic for lesson in items}),
        "tags": sorted({tag for lesson in items for tag in lesson.content_tags}),
        "filters": {
            "language": selected_language,
            "levels": sorted({lesson.level for lesson in items}),
            "topics": sorted({lesson.topic for lesson in items}),
            "tags": sorted({tag for lesson in items for tag in lesson.content_tags}),
            "practice_modes": sorted({mode for lesson in items for mode in lesson.available_modes}),
        },
        "personalization": "deterministic-curation",
    }


_translation_cache: Any = None


def configure_listening_translation_cache(cache: Any) -> None:
    """Install the persisted meaning cache. Without it, nothing is reused."""

    global _translation_cache
    _translation_cache = cache


def _translation_provider_model() -> str:
    """Identity of whatever will translate, so a provider change misses the cache."""

    service = media_translation_service()
    provider = getattr(service, "_provider", None) if service is not None else None
    return f"{type(provider).__name__}:{getattr(provider, 'model', '') or 'default'}"


def _curated_translator(media_object: Any):
    """Translate only the missing segments, through the one shared service."""

    service = media_translation_service()
    if service is None:
        return None

    def translate(segments: Any, target_language: str) -> dict[str, str]:
        partial = MediaLearningObject(
            asset=media_object.asset,
            transcript=MediaTranscript(
                media_object.asset.asset_id,
                media_object.asset.source_language,
                tuple(segments),
            ),
        )
        result = service.translate(partial, target_language)
        if result.status is not MediaTranslationStatus.READY:
            return {}
        return {item.segment_id: item.translated_meaning for item in result.media_object.translations}

    return translate


@router.get("/library/{lesson_id}")
def open_listening_library_lesson(
    lesson_id: str,
    # No language default lives here. An omitted target resolves against the
    # learner's stored support language, then the configured neutral default.
    target_language: str = Query(default="", max_length=32),
) -> dict[str, Any]:
    """Resolve a curated excerpt into the universal Media Learning payload."""
    lesson = catalog_lesson(lesson_id)
    if lesson is None:
        raise orena_http_error(404, "listening_lesson_not_found", "This Listening lesson is unavailable.")
    target_language = resolve_support_language(
        get_learner_profile().get("native_language"), target_language
    )
    media_object = translated_media_object(lesson, target_language)
    response = serialize_media_acquisition(MediaAcquisition(media_object, lesson.playback))

    # A curated lesson pre-authors meaning for a few languages. Any other
    # support language falls back to the same live service My Media uses, and
    # the result is persisted so the next learner in that language costs
    # nothing. A reviewed translation always wins over machine output.
    segments = media_object.transcript.segments if media_object.transcript else ()
    outcome = resolve_segment_meanings(
        asset_id=media_object.asset.asset_id,
        segments=segments,
        support_language=target_language,
        source_language=media_object.asset.source_language,
        preauthored=media_object.translations,
        cache=_translation_cache,
        translate=_curated_translator(media_object),
        provider_model=_translation_provider_model(),
    )
    if outcome.meanings:
        response["translations"] = [
            {
                "segment_id": meaning.segment_id,
                "target_language": meaning.target_language,
                "translated_meaning": meaning.translated_meaning,
                "provenance": meaning.provenance,
            }
            for meaning in outcome.meanings
        ]
    response["translation"] = {
        "status": outcome.status,
        "target_language": target_language,
        "source": {
            "capability_key": None,
            # Editorial when nothing had to be generated for this learner.
            "provider": "curated-editorial" if outcome.provider_calls == 0 else "media-translation",
            "model": _translation_provider_model() if outcome.provider_calls else None,
            "request_count": outcome.provider_calls,
        },
        "failure_kind": outcome.failure_kind,
    }
    metadata = lesson_metadata(lesson)
    # Pinyin is a reading of the Hanzi, so it is the same whatever the learner's
    # support language is. Pre-authored readings win; the rest are derived.
    pinyin = dict(lesson.pinyin_by_segment)
    if media_object.asset.source_language.strip().casefold().startswith("zh"):
        for segment_id, reading in pinyin_for_segments(segments).items():
            if not pinyin.get(segment_id):
                pinyin[segment_id] = reading
    metadata["pinyin_by_segment"] = pinyin
    response["catalog"] = metadata
    return response


@router.get("/progress")
def list_listening_progress(
    asset_id: str = Query(..., min_length=1, max_length=255),
) -> dict[str, Any]:
    repository = _installed()
    asset = _clean_identity(asset_id, "asset_id")
    try:
        return {"items": repository.list_listening_progress_records(asset)}
    except RuntimeError as exc:
        raise orena_http_error(503, "listening_progress_unavailable", str(exc)) from exc


@router.post("/progress")
def save_listening_progress(payload: ListeningProgressIn) -> dict[str, Any]:
    repository = _installed()
    values = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    values["asset_id"] = _clean_identity(values["asset_id"], "asset_id")
    values["segment_id"] = _clean_identity(values["segment_id"], "segment_id")
    if values["presentation"] == "revealed":
        values["revealed"] = True
    if values["revealed"] and values["presentation"] == "prompt":
        values["presentation"] = "revealed"
    values["updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        item = repository.save_listening_progress_record(values)
    except (RuntimeError, ValueError) as exc:
        category = "listening_progress_unavailable" if isinstance(exc, RuntimeError) else "listening_progress_invalid"
        raise orena_http_error(503 if isinstance(exc, RuntimeError) else 422, category, str(exc)) from exc
    return {"item": item}


@router.get("/shadowing-progress")
def list_shadowing_progress(
    asset_id: str = Query(..., min_length=1, max_length=255),
) -> dict[str, Any]:
    repository = _installed()
    asset = _clean_identity(asset_id, "asset_id")
    try:
        return {"items": repository.list_shadowing_progress_records(asset)}
    except RuntimeError as exc:
        raise orena_http_error(503, "shadowing_progress_unavailable", str(exc)) from exc


@router.post("/shadowing-progress")
def save_shadowing_progress(payload: ShadowingProgressIn) -> dict[str, Any]:
    repository = _installed()
    values = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    values["asset_id"] = _clean_identity(values["asset_id"], "asset_id")
    values["segment_id"] = _clean_identity(values["segment_id"], "segment_id")
    values["updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        item = repository.save_shadowing_progress_record(values)
    except (RuntimeError, ValueError) as exc:
        category = "shadowing_progress_unavailable" if isinstance(exc, RuntimeError) else "shadowing_progress_invalid"
        raise orena_http_error(503 if isinstance(exc, RuntimeError) else 422, category, str(exc)) from exc
    return {"item": item}
