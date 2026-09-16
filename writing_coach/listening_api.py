"""Authenticated, audio-free Active Listening progress boundary."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Mapping

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
from writing_coach.media_library_store import MediaLibraryEntry, MediaLibraryStore
from writing_coach.media_source_import import (
    PROVIDER_LABELS,
    playback_for,
    public_thumbnail_url,
    source_label,
)
from writing_coach.becoming_memory import get_learner_profile
from writing_coach.core.support_languages import resolve_support_language
from writing_coach.media_meaning import pinyin_for_segments, resolve_segment_meanings
from writing_coach.media_learning import (
    MediaLearningAsset,
    MediaLearningObject,
    MediaProcessingState,
    MediaTranscript,
    SegmentTranslation,
    TranscriptSegment,
)
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


# The persisted shared media library. `None` means this deployment has no store
# configured, and every endpoint below keeps working from the curated catalog
# alone rather than failing - an import nothing can remember is worse than a
# library that shows what it has.
_media_store: MediaLibraryStore | None = None


def configure_listening_media_library(store: MediaLibraryStore | None) -> None:
    global _media_store
    _media_store = store


def stored_media_entry(media_id: str) -> MediaLibraryEntry | None:
    """One persisted entry, or None when nothing is stored under that id."""
    if _media_store is None:
        return None
    cleaned = str(media_id or "").strip()
    if not cleaned:
        return None
    try:
        return _media_store.get(cleaned)
    except Exception:  # a broken index must not take the library down with it
        return None


def stored_media_payload(media_id: str, target_language: str = "") -> dict[str, Any] | None:
    """The learner-facing payload for one persisted entry.

    Same shape `open_listening_library_lesson` answers with, because the
    encounter must not care whether a moment came from the curated catalog or
    from a source an administrator imported: `asset`, `playback`, `transcript`,
    `translations` and a `catalog` block that carries what the card and the
    practice modes need.
    """
    entry = stored_media_entry(media_id)
    if entry is None:
        return None
    target = resolve_support_language(get_learner_profile().get("native_language"), target_language)
    stored = (entry.lesson or {}).get("payload") if entry.lesson else None
    if isinstance(stored, Mapping):
        response = _stored_acquisition_response(entry, stored)
        media_object = _media_object_from_stored(stored, entry)
        meanings_outcome = resolve_segment_meanings(
            asset_id=str(stored.get("asset", {}).get("asset_id") or entry.media_id),
            segments=media_object.transcript.segments if media_object.transcript else (),
            support_language=target,
            source_language=media_object.asset.source_language,
            preauthored=media_object.translations,
            cache=_translation_cache,
            translate=_curated_translator(media_object),
            provider_model=_translation_provider_model(),
        )
        if meanings_outcome.meanings:
            response["translations"] = [
                {
                    "segment_id": meaning.segment_id,
                    "target_language": meaning.target_language,
                    "translated_meaning": meaning.translated_meaning,
                    "provenance": meaning.provenance,
                }
                for meaning in meanings_outcome.meanings
            ]
        response["translation"] = {
            "status": meanings_outcome.status,
            "target_language": target,
            "source": {
                "capability_key": None,
                "provider": "curated-editorial" if meanings_outcome.provider_calls == 0 else "media-translation",
                "model": _translation_provider_model() if meanings_outcome.provider_calls else None,
                "request_count": meanings_outcome.provider_calls,
            },
            "failure_kind": meanings_outcome.failure_kind,
        }
        pinyin = dict(pinyin_for_segments(media_object.transcript.segments)) if media_object.transcript else {}
        if media_object.asset.source_language.strip().casefold().startswith("zh") and pinyin:
            response["catalog"]["pinyin_by_segment"] = pinyin
        return response
    # No transcript: an imported file or a direct media URL. The learner gets
    # the player and the truth, which is the same 'source only' room a
    # caption-less provider source already opens.
    response = {
        "asset": _stored_asset(entry),
        "playback": playback_for(entry),
        "transcript": None,
        "translations": [],
        "translation": {"status": "unavailable", "target_language": target, "source": None, "failure_kind": None},
    }
    response["catalog"] = stored_media_metadata(entry)
    return response


def _stored_acquisition_response(entry: MediaLibraryEntry, stored: Mapping[str, Any]) -> dict[str, Any]:
    """The stored acquisition payload, with the card's identity on top of it.

    Every existing key is kept exactly as it was persisted - the contract the
    encounter already reads must not change shape - and the media-library fields
    are added beside them.
    """
    response = {
        "asset": {
            **dict(stored.get("asset") or {}),
            # The learning language this entry was filed under is the contract's
            # language. A provider's regional tag ("en-GB" for a British
            # conversation) is provenance, not identity: the encounter compares
            # this field against the learner's current language, and a regional
            # tag would refuse a lesson that is plainly in English.
            "source_language": entry.language,
            # Backfill a length the provider never reported from the catalog,
            # where it was measured from the transcript's own boundaries.
            "duration_ms": (stored.get("asset") or {}).get("duration_ms") or entry.duration_ms or None,
            "thumbnail_url": public_thumbnail_url(entry),
        },
        "playback": playback_for(entry),
        "transcript": stored.get("transcript"),
        "translations": list(stored.get("translations") or []),
        "transcript_origin": stored.get("transcript_origin"),
    }
    response["catalog"] = stored_media_metadata(entry)
    return response


def _stored_asset(entry: MediaLibraryEntry) -> dict[str, Any]:
    return {
        "asset_id": entry.media_id,
        "source_url": entry.canonical_url,
        "source_provider": entry.provider,
        "source_type": entry.source.get("type", "imported-media"),
        "title": entry.title,
        "source_language": entry.language,
        "processing_state": MediaProcessingState.READY.value,
        "duration_ms": entry.duration_ms or None,
        "transcript_available": entry.lesson is not None,
        "translation_available": False,
        "thumbnail_url": public_thumbnail_url(entry),
    }


def stored_media_metadata(entry: MediaLibraryEntry) -> dict[str, Any]:
    """Card metadata for a persisted entry, in the catalog's own vocabulary."""
    lesson = entry.lesson or {}
    payload = lesson.get("payload") or {}
    transcript = payload.get("transcript") or {}
    segments = transcript.get("segments") or []
    return {
        "lesson_id": entry.media_id,
        "media_object_id": entry.media_id,
        "title": entry.title,
        "description": "",
        "language": entry.language,
        "topic": str(lesson.get("topic") or ""),
        "subtopics": [],
        "level": entry.level,
        "estimated_level": entry.level,
        "reviewed_level": entry.level or None,
        "level_source": "editorial-review" if entry.level else "not-estimated",
        "level_evidence": {},
        "duration_ms": entry.duration_ms,
        "excerpt_start_ms": int((segments[0] or {}).get("start_ms") or 0) if segments else 0,
        "excerpt_end_ms": int((segments[-1] or {}).get("end_ms") or entry.duration_ms) if segments else entry.duration_ms,
        "available_modes": ["listen"] if segments else [],
        "content_tags": list(lesson.get("tags") or []),
        "vocabulary": [],
        "speech_speed": None,
        "artwork": str(lesson.get("topic") or "listen"),
        "poster_url": public_thumbnail_url(entry),
        "playback_kind": playback_for(entry)["kind"],
        "published_state": "published",
        "curation_state": "reviewed",
        "is_development_candidate": False,
        "is_shared_import": entry.library == "shared",
        "media_type": entry.media_type,
        "provider": entry.provider,
        "source_label": source_label(entry),
        "source": {
            "source_media_id": entry.media_id,
            "provider": entry.provider,
            "type": entry.source.get("type", "imported-media"),
            "title": entry.title,
            "creator": entry.creator,
            "source_url": entry.canonical_url,
            "provenance_url": entry.source.get("provenance_url", entry.canonical_url),
            "license": entry.source.get("license", ""),
            "license_url": "",
            "allowed_usage_type": entry.source.get("type", "imported-media"),
            "rights_review_status": entry.source.get("review_status", ""),
        },
    }


def _media_object_from_stored(stored: Mapping[str, Any], entry: MediaLibraryEntry) -> MediaLearningObject:
    """Rebuild the contract object from what was persisted.

    Only used to resolve meanings: the shared translation path works on the
    canonical object, and re-deriving it here is cheaper than a second
    translation implementation that would have to be kept in step.
    """
    asset_raw = dict(stored.get("asset") or {})
    transcript_raw = stored.get("transcript") or {}
    segments = tuple(
        TranscriptSegment(
            str(segment["segment_id"]),
            int(segment["order"]),
            int(segment["start_ms"]),
            int(segment["end_ms"]),
            str(segment["original_text"]),
        )
        for segment in (transcript_raw.get("segments") or [])
    )
    translations = tuple(
        SegmentTranslation(str(item["segment_id"]), str(item["target_language"]), str(item["translated_meaning"]))
        for item in (stored.get("translations") or [])
    )
    duration = asset_raw.get("duration_ms") or entry.duration_ms
    asset = MediaLearningAsset(
        asset_id=str(asset_raw.get("asset_id") or entry.media_id),
        source_url=str(asset_raw.get("source_url") or entry.canonical_url or "https://www.youtube.com/"),
        source_provider=str(asset_raw.get("source_provider") or entry.provider),
        source_type=str(asset_raw.get("source_type") or "imported-media"),
        title=str(asset_raw.get("title") or entry.title),
        source_language=str(asset_raw.get("source_language") or entry.language),
        processing_state=MediaProcessingState.READY,
        duration_ms=int(duration) if isinstance(duration, int) and duration > 0 else None,
        transcript_available=bool(segments),
        translation_available=bool(translations),
    )
    transcript = (
        MediaTranscript(
            asset_id=asset.asset_id,
            source_language=asset.source_language,
            segments=segments,
        )
        if segments
        else None
    )
    return MediaLearningObject(asset=asset, transcript=transcript, translations=translations)


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
    """Return lightweight discovery metadata; transcripts load per lesson.

    Two sources, one library: the curated catalog and the media an administrator
    imported. A learner browsing a media library should not be able to tell
    which shelf something came from, and should not have to look in two places.
    """
    selected_language = (language or current_language_code()).strip().casefold()
    items = catalog_lessons(language=selected_language, level=level, topic=topic, tag=tag)
    # Real poster-backed video leads every rail, so the first viewport is media
    # rather than seed audio (spec 3.5). The order is deterministic.
    ranked = sorted(items, key=discovery_rank)
    item_metadata = [_library_item(lesson) for lesson in ranked]
    membership = {lesson.lesson_id: discovery_sections(lesson) for lesson in ranked}
    stored = _shared_entries(selected_language, level=level, topic=topic, tag=tag)
    for entry in stored:
        item_metadata.append(stored_media_metadata(entry))
        # An import is new by definition, and a stored audio file belongs in the
        # same audio rail as the seed audio it sits beside - nothing else is
        # claimed, because there is no popularity or progress signal for it.
        rails = ["new"] + (["audio-practice"] if entry.media_type == "audio" else [])
        membership[entry.media_id] = tuple(rails)
    sections = [
        {
            "id": section_id,
            "item_ids": [
                entry_id for entry_id in membership
                if section_id in membership[entry_id]
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
            "levels": sorted({lesson.level for lesson in items} | {entry.level for entry in stored if entry.level}),
            "topics": sorted({lesson.topic for lesson in items} | {str((entry.lesson or {}).get("topic") or "") for entry in stored} - {""}),
            "tags": sorted({tag for lesson in items for tag in lesson.content_tags} | {tag for entry in stored for tag in (entry.lesson or {}).get("tags", [])}),
            "practice_modes": sorted({mode for lesson in items for mode in lesson.available_modes}),
            "media_types": sorted({entry.media_type for entry in stored} | {"video", "audio"}),
            "sources": sorted({entry.provider for entry in stored} | {lesson.source.source_provider for lesson in items}),
        },
        "personalization": "deterministic-curation",
    }


def _library_item(lesson: Any) -> dict[str, Any]:
    """Curated metadata plus the labels a media card needs.

    Additive only: every key the existing surface reads is untouched, and the
    media-library keys sit beside them.
    """
    metadata = lesson_metadata(lesson)
    metadata["thumbnail_url"] = lesson.source.poster_url
    metadata["media_type"] = "audio" if lesson.source.playback.kind == "audio" else "video"
    metadata["provider"] = lesson.source.source_provider
    metadata["source_label"] = PROVIDER_LABELS.get(lesson.source.source_provider, lesson.source.source_provider)
    metadata["is_shared_import"] = False
    return metadata


def _shared_entries(
    language: str,
    *,
    level: str | None = None,
    topic: str | None = None,
    tag: str | None = None,
) -> list[MediaLibraryEntry]:
    """Persisted shared imports, filtered the same way the catalog is."""
    if _media_store is None:
        return []
    try:
        entries = _media_store.list(language=language)
    except Exception:  # a broken index must not empty the learner's library
        return []
    level_key = (level or "").strip().casefold()
    topic_key = (topic or "").strip().casefold()
    tag_key = (tag or "").strip().casefold()
    return [
        entry
        for entry in entries
        if entry.library == "shared"
        and (not level_key or entry.level.casefold() == level_key)
        and (not topic_key or str((entry.lesson or {}).get("topic") or "").casefold() == topic_key)
        and (not tag_key or tag_key in {str(item).casefold() for item in (entry.lesson or {}).get("tags", [])})
    ]


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
    """Resolve a curated excerpt into the universal Media Learning payload.

    An imported source answers through the same route: a card in the learner's
    library carries the id of the entry it points at, and the encounter must not
    need to know whether a moment came from the curated catalog or from
    something an administrator published.
    """
    lesson = catalog_lesson(lesson_id)
    if lesson is None:
        stored = stored_media_payload(lesson_id, target_language)
        if stored is None:
            raise orena_http_error(404, "listening_lesson_not_found", "This Listening lesson is unavailable.")
        return stored
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
