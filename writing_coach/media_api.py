"""Learner API DTO boundary for shared Media Learning imports."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from writing_coach.core.errors import orena_http_error
from pydantic import BaseModel, ConfigDict, Field, field_validator

from writing_coach.core.request_context import current_language_code, current_user_key
from writing_coach.media_fallback import (
    MediaFallbackResult,
    SupadataMediaFallbackService,
)
from writing_coach.media_ingestion import (
    MediaAcquisition,
    MediaImportCategory,
    MediaImportError,
    MediaIngestionService,
)
from writing_coach.media_learning import (
    MediaLearningAsset,
    MediaLearningContractError,
    MediaLearningObject,
    MediaProcessingState,
    MediaTranscript,
    TranscriptSegment,
)
from writing_coach.media_interaction import router as media_interaction_router
from writing_coach.media_timing import (
    MediaTimingEnrichment,
    MediaTimingService,
)
from writing_coach.media_translation import (
    MediaTranslationResult,
    MediaTranslationService,
    safe_translation_source,
)


router = APIRouter(prefix="/api/media-learning", tags=["media-learning"])
router.include_router(media_interaction_router)
_media_ingestion_service: MediaIngestionService | None = None
_media_translation_service: MediaTranslationService | None = None
_media_timing_service: MediaTimingService | None = None
_media_fallback_service: SupadataMediaFallbackService | None = None


class MediaImportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_url: str = Field(min_length=1, max_length=2048)
    target_language: str = Field(min_length=2, max_length=32)
    include_word_timing: bool = False
    include_translation: bool = True

    @field_validator("target_language")
    @classmethod
    def normalize_target_language(cls, value: str) -> str:
        return value.strip().casefold()


class MediaImportStatusIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=20, max_length=200)
    compact: bool = False


class MediaTranslationAssetIn(BaseModel):
    """Canonical asset metadata supplied by an already completed acquisition."""

    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1, max_length=128)
    source_url: str = Field(min_length=1, max_length=2048)
    source_provider: str = Field(min_length=1, max_length=128)
    source_type: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=2048)
    source_language: str = Field(min_length=2, max_length=32)
    processing_state: MediaProcessingState
    duration_ms: int | None = Field(default=None, gt=0)
    transcript_available: bool


class MediaTranslationSegmentIn(BaseModel):
    """One canonical transcript segment, deliberately excluding provider fields."""

    model_config = ConfigDict(extra="forbid")

    segment_id: str = Field(min_length=1, max_length=128)
    order: int = Field(ge=0)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    original_text: str = Field(min_length=1, max_length=20000)


class MediaTranslationTranscriptIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1, max_length=128)
    source_language: str = Field(min_length=2, max_length=32)
    segments: list[MediaTranslationSegmentIn] = Field(min_length=1)


class MediaTranslationIn(BaseModel):
    """Translate the existing canonical transcript; never acquire media again."""

    model_config = ConfigDict(extra="forbid")

    target_language: str = Field(min_length=2, max_length=32)
    asset: MediaTranslationAssetIn
    transcript: MediaTranslationTranscriptIn

    @field_validator("target_language")
    @classmethod
    def normalize_target_language(cls, value: str) -> str:
        return value.strip().casefold()


def configure_media_ingestion(service: MediaIngestionService) -> None:
    global _media_ingestion_service
    _media_ingestion_service = service


def configure_media_translation(service: MediaTranslationService) -> None:
    global _media_translation_service
    _media_translation_service = service


def configure_media_timing(service: MediaTimingService | None) -> None:
    global _media_timing_service
    _media_timing_service = service


def configure_media_fallback(service: SupadataMediaFallbackService | None) -> None:
    global _media_fallback_service
    _media_fallback_service = service


def _installed_media_ingestion() -> MediaIngestionService:
    if _media_ingestion_service is None:
        raise HTTPException(503, "Media Learning ingestion is not installed.")
    return _media_ingestion_service


def media_translation_service() -> MediaTranslationService | None:
    """The one translation service, or None when it is not installed.

    Curated Listening needs the same engine My Media uses; a second one would be
    a second definition of what a meaning is.
    """

    return _media_translation_service


def _installed_media_translation() -> MediaTranslationService:
    if _media_translation_service is None:
        raise HTTPException(503, "Media Learning translation is not installed.")
    return _media_translation_service


_STATUS_BY_CATEGORY = {
    MediaImportCategory.MALFORMED_URL: 422,
    MediaImportCategory.UNSUPPORTED_PROVIDER: 422,
    MediaImportCategory.MEDIA_UNAVAILABLE: 404,
    MediaImportCategory.PROVIDER_TIMEOUT: 504,
    MediaImportCategory.PROVIDER_FAILURE: 502,
    MediaImportCategory.MALFORMED_TRANSCRIPT: 502,
    MediaImportCategory.UNSUPPORTED_SOURCE_LANGUAGE: 409,
    MediaImportCategory.INVALID_TARGET_LANGUAGE: 422,
}


def _serialize_processing_result(
    result: MediaFallbackResult,
    *,
    timing: MediaTimingEnrichment | None = None,
) -> dict[str, Any]:
    response = serialize_media_acquisition(result.acquisition, timing=timing)
    response["asset"]["processing_state"] = (
        "processing" if result.status == "processing" else "failed"
    )
    response["import_job"] = {
        "job_id": result.job_id,
        "state": result.provider_state or result.status,
        "source": result.source,
        "failure_kind": result.failure_kind,
        "resumable": result.status == "processing" and bool(result.job_id),
    }
    return response


def _serialize_compact_status(result: MediaFallbackResult) -> dict[str, Any]:
    """Serialize only bounded state needed to resume an opaque import job."""
    asset = result.acquisition.media_object.asset
    asset_state = (
        "processing"
        if result.status == "processing"
        else "failed"
        if result.status == "failed"
        else "ready"
    )
    return {
        "status": result.status,
        "asset": {
            "asset_id": asset.asset_id,
            "processing_state": asset_state,
        },
        "import_job": {
            "resume_handle": result.job_id,
            "state": result.provider_state or result.status,
            "source": result.source,
            "failure_kind": result.failure_kind,
            "resumable": result.status == "processing" and bool(result.job_id),
        },
    }


def _ready_response(
    acquisition: MediaAcquisition,
    *,
    target_language: str,
    timing: MediaTimingEnrichment | None = None,
    job: MediaFallbackResult | None = None,
    include_translation: bool = True,
) -> dict[str, Any]:
    translation = (
        _installed_media_translation().translate(
            acquisition.media_object,
            target_language,
        )
        if include_translation
        else None
    )
    response = serialize_media_acquisition(acquisition, translation, timing)
    if job is not None:
        response["import_job"] = {
            "job_id": job.job_id,
            "state": job.provider_state or "completed",
            "source": job.source,
            "failure_kind": None,
            "resumable": False,
        }
        if acquisition.media_object.transcript is not None:
            response["transcript_generation"] = {
                "status": "generated",
                "source": job.source,
            }
            response["transcript_origin"] = (
                TRANSCRIPT_ORIGIN_SUPADATA if job.source == "supadata"
                else TRANSCRIPT_ORIGIN_ASR
            )
    return response


@router.post("/import")
def import_media(payload: MediaImportIn) -> dict[str, Any]:
    """Acquire native media, then Groq timing/transcript, then explicit fallback."""
    learning_language = current_language_code()
    try:
        acquisition = _installed_media_ingestion().import_media(
            payload.source_url,
            payload.target_language,
            learning_language,
        )
    except MediaImportError as exc:
        raise orena_http_error(
            _STATUS_BY_CATEGORY[exc.category],
            exc.category.value,
            exc.learner_message,
        ) from exc

    timing: MediaTimingEnrichment | None = None
    if _media_timing_service is not None and (
        payload.include_word_timing or acquisition.media_object.transcript is None
    ):
        timing = _media_timing_service.enrich(acquisition, learning_language)
        acquisition = timing.acquisition

    if acquisition.media_object.transcript is not None:
        return _ready_response(
            acquisition,
            target_language=payload.target_language,
            include_translation=payload.include_translation,
            timing=timing,
        )

    if _media_fallback_service is None:
        return _ready_response(
            acquisition,
            target_language=payload.target_language,
            include_translation=payload.include_translation,
            timing=timing,
        )

    fallback = _media_fallback_service.start(
        acquisition,
        owner_key=current_user_key(),
        learning_language=learning_language,
        target_language=payload.target_language,
        include_translation=payload.include_translation,
    )
    if fallback.status == "ready":
        return _ready_response(
            fallback.acquisition,
            target_language=payload.target_language,
            include_translation=payload.include_translation,
            job=fallback,
        )
    if fallback.status in {"processing", "failed"}:
        return _serialize_processing_result(fallback, timing=timing)
    return _ready_response(
        acquisition,
        target_language=payload.target_language,
        timing=timing,
    )


@router.post("/import/status")
def import_media_status(payload: MediaImportStatusIn) -> dict[str, Any]:
    service = _media_fallback_service
    if service is None:
        raise orena_http_error(
            404,
            "media_job_unavailable",
            "This transcript job is no longer available.",
            context=(
                {"status": "unavailable", "resumable": False}
                if payload.compact
                else None
            ),
        )
    try:
        result = service.poll(
            payload.job_id,
            owner_key=current_user_key(),
            learning_language=current_language_code(),
        )
    except KeyError as exc:
        raise orena_http_error(
            404,
            "media_job_unavailable",
            "This transcript job is unavailable or expired.",
            context=(
                {"status": "unavailable", "resumable": False}
                if payload.compact
                else None
            ),
        ) from exc

    if payload.compact:
        return _serialize_compact_status(result)

    if result.status == "ready":
        if not result.target_language:
            raise HTTPException(404, "Media import job context is unavailable.")
        return _ready_response(
            result.acquisition,
            target_language=result.target_language,
            include_translation=result.include_translation,
            job=result,
        )
    return _serialize_processing_result(result)


def _media_object_for_translation(payload: MediaTranslationIn) -> MediaLearningObject:
    """Rebuild and validate only the canonical object needed by translation."""
    try:
        asset = MediaLearningAsset(
            asset_id=payload.asset.asset_id,
            source_url=payload.asset.source_url,
            source_provider=payload.asset.source_provider,
            source_type=payload.asset.source_type,
            title=payload.asset.title,
            source_language=payload.asset.source_language,
            processing_state=payload.asset.processing_state,
            duration_ms=payload.asset.duration_ms,
            transcript_available=payload.asset.transcript_available,
            translation_available=False,
        )
        transcript = MediaTranscript(
            asset_id=payload.transcript.asset_id,
            source_language=payload.transcript.source_language,
            segments=tuple(
                TranscriptSegment(
                    segment_id=segment.segment_id,
                    order=segment.order,
                    start_ms=segment.start_ms,
                    end_ms=segment.end_ms,
                    original_text=segment.original_text,
                )
                for segment in payload.transcript.segments
            ),
        )
        return MediaLearningObject(asset=asset, transcript=transcript)
    except (MediaLearningContractError, ValueError) as exc:
        raise orena_http_error(
            422,
            "invalid_media_transcript",
            "The prepared media transcript is invalid.",
        ) from exc


@router.post("/translate")
def translate_media(payload: MediaTranslationIn) -> dict[str, Any]:
    """Translate a previously acquired canonical transcript without re-importing."""
    translation = _installed_media_translation().translate(
        _media_object_for_translation(payload), payload.target_language
    )
    return serialize_media_translation(translation)


# LISTENING_PRODUCT_SPEC B5. A generated transcript is useful and honest; a
# generated transcript presented as official subtitles is neither.
TRANSCRIPT_ORIGIN_PROVIDER = "provider_caption"
TRANSCRIPT_ORIGIN_ASR = "generated_asr"
TRANSCRIPT_ORIGIN_SUPADATA = "supadata_generated"
TRANSCRIPT_ORIGIN_NONE = "none"


def transcript_origin(transcript: Any, timing: Any = None) -> str:
    """Which path produced the transcript now attached to the media object.

    Derived rather than stored on the transcript itself, because the transcript
    is the canonical domain object and provenance is a delivery concern. A
    caller that knows better - the fallback path, which knows a job produced the
    text - overrides this on the response it builds.
    """

    if transcript is None:
        return TRANSCRIPT_ORIGIN_NONE
    if timing is not None and getattr(timing, "source", "") == "groq":
        return TRANSCRIPT_ORIGIN_ASR
    return TRANSCRIPT_ORIGIN_PROVIDER


def serialize_media_acquisition(
    acquisition: MediaAcquisition,
    translation: MediaTranslationResult | None = None,
    timing: MediaTimingEnrichment | None = None,
) -> dict[str, Any]:
    """Serialize M1.1 objects without changing their domain representation."""
    media_object = (
        translation.media_object
        if translation is not None
        else acquisition.media_object
    )
    response = {
        "asset": _serialize_asset(media_object),
        "playback": {
            "provider": acquisition.playback.provider,
            "kind": acquisition.playback.kind,
            "url": acquisition.playback.url,
        },
        "transcript": _serialize_transcript(media_object.transcript, timing),
        # Where this transcript came from, so the learner is never shown an
        # AI-generated transcript labelled as the source's own captions.
        "transcript_origin": transcript_origin(media_object.transcript, timing),
        "translations": [
            {
                "segment_id": translation.segment_id,
                "target_language": translation.target_language,
                "translated_meaning": translation.translated_meaning,
            }
            for translation in media_object.translations
        ],
    }
    if timing is not None:
        response["word_timing"] = {
            "status": timing.status,
            "source": timing.source,
            "model": timing.model,
            "failure_kind": timing.failure_kind,
        }
        if timing.transcript_generated:
            response["transcript_generation"] = {
                "status": "generated",
                "source": timing.source,
            }
    if translation is not None:
        response["translation"] = {
            "status": translation.status.value,
            "target_language": translation.target_language,
            "source": safe_translation_source(translation.provenance),
            "failure_kind": (
                translation.failure_kind.value
                if translation.failure_kind is not None
                else None
            ),
        }
    return response


def serialize_media_translation(translation: MediaTranslationResult) -> dict[str, Any]:
    """Serialize a translation result without exposing an acquisition/playback path."""
    media_object = translation.media_object
    return {
        "asset": _serialize_asset(media_object),
        "transcript": _serialize_transcript(media_object.transcript),
        "translations": [
            {
                "segment_id": item.segment_id,
                "target_language": item.target_language,
                "translated_meaning": item.translated_meaning,
            }
            for item in media_object.translations
        ],
        "translation": {
            "status": translation.status.value,
            "target_language": translation.target_language,
            "source": safe_translation_source(translation.provenance),
            "failure_kind": (
                translation.failure_kind.value
                if translation.failure_kind is not None
                else None
            ),
        },
    }


def _serialize_asset(media_object: MediaLearningObject) -> dict[str, Any]:
    asset = media_object.asset
    return {
        "asset_id": asset.asset_id,
        "source_url": asset.source_url,
        "source_provider": asset.source_provider,
        "source_type": asset.source_type,
        "title": asset.title,
        "source_language": asset.source_language,
        "processing_state": asset.processing_state.value,
        "duration_ms": asset.duration_ms,
        "transcript_available": asset.transcript_available,
        "translation_available": asset.translation_available,
        "thumbnail_url": asset.thumbnail_ref,
    }


def _serialize_transcript(
    transcript: MediaTranscript | None,
    timing: MediaTimingEnrichment | None = None,
) -> dict[str, Any] | None:
    if transcript is None:
        return None
    words_by_segment: dict[str, list[dict[str, Any]]] = {}
    for word in timing.words if timing is not None else ():
        words_by_segment.setdefault(word.segment_id, []).append(
            {"text": word.text, "start_ms": word.start_ms, "end_ms": word.end_ms}
        )
    return {
        "asset_id": transcript.asset_id,
        "source_language": transcript.source_language,
        "segments": [
            {
                "segment_id": segment.segment_id,
                "order": segment.order,
                "start_ms": segment.start_ms,
                "end_ms": segment.end_ms,
                "original_text": segment.original_text,
                "words": words_by_segment.get(segment.segment_id, []),
            }
            for segment in transcript.segments
        ],
    }
