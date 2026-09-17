"""HTTP boundary for paragraph meaning in Reading."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, model_validator

from writing_coach.core.errors import orena_http_error
from writing_coach.core.request_context import current_language_code
from writing_coach.core.support_languages import UnsupportedSupportLanguage
from writing_coach.media_ingestion import primary_language
from writing_coach.media_translation import MAX_TRANSLATION_BATCH_CHARS
from writing_coach.reading_translation import ReadingTranslationService, TextSegment

# One request is at most two provider batches of paragraphs; a reader asking for
# a whole chapter sends it in turns, so the first meanings arrive while the
# rest are still on their way.
MAX_READING_TRANSLATION_SEGMENTS = 48

router = APIRouter(prefix="/api/reading", tags=["reading"])
_service: ReadingTranslationService | None = None


def configure_reading_translation(service: ReadingTranslationService | None) -> None:
    global _service
    _service = service


class ReadingTranslationSegmentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    text: str = Field(min_length=1, max_length=MAX_TRANSLATION_BATCH_CHARS)


class ReadingTranslationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_language: str = Field(min_length=2, max_length=32)
    target_language: str = Field(min_length=2, max_length=32)
    segments: list[ReadingTranslationSegmentIn] = Field(
        min_length=1, max_length=MAX_READING_TRANSLATION_SEGMENTS
    )

    @model_validator(mode="after")
    def segment_ids_are_unique(self) -> ReadingTranslationIn:
        ids = [segment.segment_id for segment in self.segments]
        if len(ids) != len(set(ids)):
            raise ValueError("Each paragraph needs its own segment_id.")
        return self


@router.post("/translate")
def translate_reading(payload: ReadingTranslationIn) -> dict[str, Any]:
    if _service is None:
        raise orena_http_error(
            503,
            "reading_translation_unavailable",
            "Reading translation is not available right now.",
            retryable=False,
        )
    source = primary_language(payload.source_language)
    if source not in {"en", "zh"} or source != primary_language(current_language_code()):
        raise orena_http_error(
            409,
            "reading_language_mismatch",
            "Text language must match the current learning language.",
            retryable=False,
        )
    try:
        result = _service.translate(
            source,
            payload.target_language,
            [TextSegment(segment.segment_id, segment.text) for segment in payload.segments],
        )
    except UnsupportedSupportLanguage as exc:
        raise orena_http_error(
            422,
            "invalid_support_language",
            "Choose a valid support language.",
            retryable=False,
        ) from exc
    return {
        "status": result.status.value,
        "source_language": result.source_language,
        "target_language": result.target_language,
        "translations": [
            {"segment_id": segment_id, "translated_meaning": meaning}
            for segment_id, meaning in result.translations
        ],
    }
