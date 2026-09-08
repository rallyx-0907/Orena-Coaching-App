"""Authenticated, audio-free Active Listening progress boundary."""

from __future__ import annotations

from datetime import datetime, timezone
from collections.abc import Sequence
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
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


def preview_visible(request: Request | None) -> bool:
    """Whether THIS caller may see preview catalog content.

    Two independent conditions, both required. The deployment must be a preview
    tier - on production tier the artifact is never loaded, so this is moot -
    and the caller must be a platform administrator. Preview content is not
    "visible to anyone who signs in"; it is unreviewed material with unresolved
    rights, so it stays behind an existing trusted role rather than a new
    account system.
    """

    from writing_coach.core.deployment import TIER_PREVIEW, resolve_deployment_tier

    if resolve_deployment_tier() != TIER_PREVIEW:
        return False
    if request is None:
        # No request to authorize against, so no preview content. Failing
        # closed here means an internal caller can never widen visibility.
        return False
    try:
        from auth_support import require_admin

        require_admin(request)
    except Exception:
        return False
    return True


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
    # Progress belongs to a lesson. Empty is the legacy path and is resolved
    # only when the asset is unambiguous; see resolve_progress_lesson().
    lesson_id: str = Field(default="", max_length=255)
    segment_id: str = Field(min_length=1, max_length=255)
    presentation: Literal["prompt", "checked", "revealed"] = "prompt"
    revealed: bool = False
    checked_attempt_count: int = Field(default=0, ge=0, le=1000)
    best_accuracy_percent: int | None = Field(default=None, ge=0, le=100)
    best_exact: bool = False
    last_answer: str = Field(default="", max_length=2000)


class ShadowingProgressIn(BaseModel):
    asset_id: str = Field(min_length=1, max_length=255)
    lesson_id: str = Field(default="", max_length=255)
    segment_id: str = Field(min_length=1, max_length=255)
    completed_rounds: int = Field(default=0, ge=0, le=1000)


def resolve_progress_lesson(
    *,
    asset_id: str,
    lesson_id: str,
    segment_id: str,
    request: Request | None = None,
) -> str:
    """Validate the lesson a progress write claims, and return its canonical id.

    A client-supplied lesson_id is never trusted on its own. The lesson must
    exist, belong to the stated asset, be in the learner's current learning
    language, and actually contain the segment - otherwise progress in one
    excerpt could be written against another.

    An omitted lesson_id is the legacy client path. It resolves ONLY when the
    asset has exactly one lesson; with several, this fails truthfully rather
    than picking one, because guessing would attach real work to the wrong
    excerpt. That compatibility path can be removed once no client omits
    lesson_id - the web client sends it as of this change.
    """

    language = (current_language_code() or "").strip().casefold()
    candidates = [
        lesson for lesson in catalog_lessons(
            language=language or None, include_preview=preview_visible(request))
        if lesson.source.source_media_id == asset_id
    ]

    if lesson_id:
        lesson = next((item for item in candidates if item.lesson_id == lesson_id), None)
        if lesson is None:
            raise orena_http_error(
                400, "listening_lesson_mismatch",
                "This lesson does not exist for that media in this language.")
    elif len(candidates) == 1:
        lesson = candidates[0]
    elif not candidates:
        # Nothing to attach it to. Legacy/unassigned is the truthful answer:
        # the row is still stored, keyed by an empty lesson.
        return ""
    else:
        raise orena_http_error(
            400, "listening_lesson_required",
            "This media has several lessons, so progress must name its lesson.")

    known = {segment.segment_id for segment in _lesson_segments(lesson)}
    if known and segment_id not in known:
        raise orena_http_error(
            400, "listening_segment_mismatch",
            "That segment does not belong to this lesson.")
    return lesson.lesson_id


def _lesson_segments(lesson: Any) -> tuple[Any, ...]:
    transcript = lesson.media_object.transcript
    return tuple(transcript.segments) if transcript is not None else ()


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


def _optional_identity(value: Any) -> str:
    """An optional identifier, tolerant of being called outside FastAPI.

    Called over HTTP this is a string. Called directly - tests, internal callers
    - the parameter default is still FastAPI's Query object, and treating that
    as an identifier would scope a read to nonsense. Anything that is not a
    non-empty string means "no lesson given".
    """

    return value.strip() if isinstance(value, str) and value.strip() else ""


def _clean_identity(value: str, field: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise orena_http_error(422, "listening_progress_invalid", f"{field} must not be empty.")
    return cleaned


# How many lessons the first rail may carry. A resume rail is a short list of
# what you were actually doing, not a history page.
CONTINUE_LEARNING_LIMIT = 8


def continue_learning_lessons(
    ranked: Sequence[Any],
    *,
    language: str,
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    """Lessons this learner actually has progress in, most recent first.

    Built from durable PostgreSQL progress, never from catalog metadata,
    localStorage or a guess. Every candidate is joined against the catalog the
    caller can currently see, so a lesson that was removed, belongs to another
    learning language, or is preview content this learner may not access simply
    does not appear - the visibility rule is the same one discovery uses,
    enforced here rather than in the client.

    Returns the ordered lesson ids and, per lesson, the resume hint the existing
    frontend needs. No transcript is duplicated into discovery: opening the
    lesson still goes through the lesson endpoint and its persisted transcript.
    """

    if _repository is None:
        return [], {}
    try:
        records = _repository.list_recent_listening_progress_records(limit=60)
    except RuntimeError:
        # Progress is a PostgreSQL capability. Without it there is simply
        # nothing to continue; discovery still renders.
        return [], {}

    visible = {lesson.lesson_id: lesson for lesson in ranked}
    ordered: list[str] = []
    resume: dict[str, dict[str, Any]] = {}
    for record in records:
        lesson_id = str(record.get("lesson_id") or "")
        # Legacy rows carry no lesson, so there is nothing truthful to resume.
        if not lesson_id or lesson_id in resume:
            continue
        lesson = visible.get(lesson_id)
        if lesson is None or lesson.source.language.strip().casefold() != language:
            continue
        segment_id = str(record.get("segment_id") or "")
        known = {segment.segment_id for segment in _lesson_segments(lesson)}
        resume[lesson_id] = {
            "lesson_id": lesson_id,
            "asset_id": lesson.source.source_media_id,
            # A revised lesson may no longer contain the segment the learner
            # left off at. Resume at its start rather than seeking to something
            # that is gone.
            "segment_id": segment_id if segment_id in known else "",
            "presentation": record.get("presentation") or "prompt",
            "checked_attempt_count": int(record.get("checked_attempt_count") or 0),
            "best_exact": bool(record.get("best_exact")),
            "updated_at": record.get("updated_at"),
        }
        ordered.append(lesson_id)
        if len(ordered) >= CONTINUE_LEARNING_LIMIT:
            break
    return ordered, resume


@router.get("/library")
def listening_library(
    language: str | None = Query(default=None, min_length=2, max_length=32),
    level: str | None = Query(default=None, min_length=1, max_length=32),
    topic: str | None = Query(default=None, min_length=1, max_length=64),
    tag: str | None = Query(default=None, min_length=1, max_length=64),
    request: Request = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    """Return lightweight discovery metadata; transcripts load per lesson."""
    selected_language = (language or current_language_code()).strip().casefold()
    items = catalog_lessons(
        language=selected_language, level=level, topic=topic, tag=tag,
        include_preview=preview_visible(request),
    )
    # Real poster-backed video leads every rail, so the first viewport is media
    # rather than seed audio (spec 3.5). The order is deterministic.
    ranked = sorted(items, key=discovery_rank)
    item_metadata = [lesson_metadata(lesson) for lesson in ranked]
    membership = {lesson.lesson_id: discovery_sections(lesson) for lesson in ranked}
    continue_ids, resume = continue_learning_lessons(ranked, language=selected_language)
    sections = [
        {
            "id": section_id,
            # Continue Learning is ordered by real recency, not by curation
            # rank, so it keeps the progress order rather than the catalog's.
            "item_ids": continue_ids if section_id == "continue-learning" else [
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
        # Enough to reopen at the right excerpt and segment; the transcript
        # itself still comes from the lesson endpoint.
        "resume": resume,
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
    request: Request = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    """Resolve a curated excerpt into the universal Media Learning payload."""
    lesson = catalog_lesson(lesson_id, include_preview=preview_visible(request))
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
    lesson_id: str = Query(default="", max_length=255),
) -> dict[str, Any]:
    repository = _installed()
    asset = _clean_identity(asset_id, "asset_id")
    lesson = _optional_identity(lesson_id)
    try:
        return {"items": repository.list_listening_progress_records(asset, lesson)}
    except RuntimeError as exc:
        raise orena_http_error(503, "listening_progress_unavailable", str(exc)) from exc


@router.post("/progress")
def save_listening_progress(
    payload: ListeningProgressIn,
    request: Request = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    repository = _installed()
    values = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    values["asset_id"] = _clean_identity(values["asset_id"], "asset_id")
    values["segment_id"] = _clean_identity(values["segment_id"], "segment_id")
    values["lesson_id"] = resolve_progress_lesson(
        asset_id=values["asset_id"], lesson_id=str(values.get("lesson_id") or ""),
        segment_id=values["segment_id"], request=request,
    )
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
    lesson_id: str = Query(default="", max_length=255),
) -> dict[str, Any]:
    repository = _installed()
    asset = _clean_identity(asset_id, "asset_id")
    lesson = _optional_identity(lesson_id)
    try:
        return {"items": repository.list_shadowing_progress_records(asset, lesson)}
    except RuntimeError as exc:
        raise orena_http_error(503, "shadowing_progress_unavailable", str(exc)) from exc


@router.post("/shadowing-progress")
def save_shadowing_progress(
    payload: ShadowingProgressIn,
    request: Request = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    repository = _installed()
    values = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    values["asset_id"] = _clean_identity(values["asset_id"], "asset_id")
    values["segment_id"] = _clean_identity(values["segment_id"], "segment_id")
    values["lesson_id"] = resolve_progress_lesson(
        asset_id=values["asset_id"], lesson_id=str(values.get("lesson_id") or ""),
        segment_id=values["segment_id"], request=request,
    )
    values["updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        item = repository.save_shadowing_progress_record(values)
    except (RuntimeError, ValueError) as exc:
        category = "shadowing_progress_unavailable" if isinstance(exc, RuntimeError) else "shadowing_progress_invalid"
        raise orena_http_error(503 if isinstance(exc, RuntimeError) else 422, category, str(exc)) from exc
    return {"item": item}
