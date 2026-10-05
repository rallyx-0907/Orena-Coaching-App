"""HTTP boundary for on-demand meaning in Reading: translation, summary and word lookup."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, model_validator

from writing_coach.core.errors import orena_http_error
from writing_coach.core.request_context import current_language_code
from writing_coach.core.support_languages import UnsupportedSupportLanguage
from writing_coach.media_ingestion import primary_language
from writing_coach.media_translation import MAX_TRANSLATION_BATCH_CHARS
from writing_coach.reading_lookup import ReadingLookupService
from writing_coach.reading_summary import ReadingSummaryService, SummaryUnavailable
from writing_coach.reading_translation import (
    ReadingTranslationService,
    ReadingTranslationStatus,
    TextSegment,
)

# One request is at most two provider batches of paragraphs; a reader asking for
# a whole chapter sends it in turns, so the first meanings arrive while the
# rest are still on their way.
MAX_READING_TRANSLATION_SEGMENTS = 48

router = APIRouter(prefix="/api/reading", tags=["reading"])
_service: ReadingTranslationService | None = None
_lookup_service: ReadingLookupService | None = None
_summary_service: ReadingSummaryService | None = None



def configure_reading_translation(service: ReadingTranslationService | None) -> None:
    global _service
    _service = service


def configure_reading_summary(service: ReadingSummaryService | None) -> None:
    global _summary_service
    _summary_service = service


def persists_to_shared_cache(content_id: str | None) -> bool:
    """Only published articles reach the shared table; a learner's own text stays in this process (D-104)."""
    return str(content_id or "").startswith("article:")


def configure_reading_lookup(service: ReadingLookupService | None) -> None:
    global _lookup_service
    _lookup_service = service


class ReadingTranslationSegmentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    text: str = Field(min_length=1, max_length=MAX_TRANSLATION_BATCH_CHARS)


class ReadingTranslationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_language: str = Field(min_length=2, max_length=32)
    target_language: str = Field(min_length=2, max_length=32)
    # `article:<uuid>` when the text is a published article: only then are the answers kept in the shared table.
    content_id: str | None = Field(default=None, max_length=200)
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
            persist=persists_to_shared_cache(payload.content_id),
        )
    except UnsupportedSupportLanguage as exc:
        raise orena_http_error(
            422,
            "invalid_support_language",
            "Choose a valid support language.",
            retryable=False,
        ) from exc
    if result.status is ReadingTranslationStatus.UNAVAILABLE:
        # The engine could not answer: a retryable error the screen shows as "try again", never "not available".
        raise orena_http_error(
            503,
            "translation_unavailable",
            "The translation could not be made right now. Try again.",
            retryable=True,
        )
    return {
        "status": result.status.value,
        "source_language": result.source_language,
        "target_language": result.target_language,
        "translations": [
            {"segment_id": segment_id, "translated_meaning": meaning}
            for segment_id, meaning in result.translations
        ],
    }


class ReadingLookupIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=80)
    context: str = Field(min_length=1, max_length=1200)
    source_language: str = Field(min_length=2, max_length=32)
    target_language: str = Field(min_length=2, max_length=32)


@router.post("/lookup")
def lookup_reading_text(payload: ReadingLookupIn) -> dict[str, Any]:
    if _lookup_service is None:
        raise orena_http_error(
            503,
            "reading_lookup_unavailable",
            "Reading lookup is not available right now.",
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
    text = payload.text.strip()
    context = payload.context.strip()
    if not text or text.casefold() not in context.casefold():
        raise orena_http_error(
            422,
            "reading_lookup_text_not_in_context",
            "Selected text must come from the supplied reading context.",
            retryable=False,
        )
    try:
        result = _lookup_service.lookup(text, context, source, payload.target_language)
    except UnsupportedSupportLanguage as exc:
        raise orena_http_error(
            422,
            "invalid_support_language",
            "Choose a valid support language.",
            retryable=False,
        ) from exc
    return result.to_dict()


class ReadingSummaryIn(BaseModel):
    """Exactly one of: a published article, a book chapter, or the text itself."""

    model_config = ConfigDict(extra="forbid")

    source_language: str = Field(min_length=2, max_length=32)
    target_language: str = Field(min_length=2, max_length=32)
    article_id: str = Field(default="", max_length=64, pattern=r"^[A-Za-z0-9_-]*$")
    book_id: str = Field(default="", max_length=64, pattern=r"^[A-Za-z0-9_-]*$")
    chapter_id: str = Field(default="", max_length=64, pattern=r"^[A-Za-z0-9_-]*$")
    text: str = Field(default="", max_length=20_000)

    @model_validator(mode="after")
    def exactly_one_source(self) -> ReadingSummaryIn:
        chosen = [bool(self.article_id), bool(self.book_id or self.chapter_id), bool(self.text.strip())]
        if sum(chosen) != 1 or bool(self.book_id) != bool(self.chapter_id):
            raise ValueError("Name one text: an article, a book chapter, or the text itself.")
        return self


def _summary_source(payload: ReadingSummaryIn) -> tuple[str, bool]:
    """(the text, whether the shared table may hold its summary)."""
    from writing_coach import reading_articles_api, reading_library_api

    if payload.article_id:
        repository = reading_articles_api._require_repository()
        article = reading_articles_api._guarded(lambda: repository.get_published_article(payload.article_id))
        if article is None:
            raise orena_http_error(404, "reading_article_not_found", "That article is not available.")
        return str(article.get("body") or ""), True
    if payload.book_id:
        chapter = reading_library_api.get_chapter(payload.book_id, payload.chapter_id)
        return " ".join(str(item) for item in chapter.get("paragraphs") or []), False
    return payload.text, False


@router.post("/summary")
def summarize_reading(payload: ReadingSummaryIn) -> dict[str, Any]:
    """Generated when the learner opens Summary - never on opening the text - once, then reused."""
    if _summary_service is None:
        raise orena_http_error(
            503, "reading_summary_unavailable", "The summary could not be made right now.", retryable=True
        )
    source = primary_language(payload.source_language)
    if source not in {"en", "zh"} or source != primary_language(current_language_code()):
        raise orena_http_error(
            409,
            "reading_language_mismatch",
            "Text language must match the current learning language.",
            retryable=False,
        )
    text, persist = _summary_source(payload)
    if not text.strip():
        raise orena_http_error(422, "reading_summary_empty", "There is no text to summarise.", retryable=False)
    try:
        bullets = _summary_service.summarize(text, source, payload.target_language, persist=persist)
    except UnsupportedSupportLanguage as exc:
        raise orena_http_error(
            422, "invalid_support_language", "Choose a valid support language.", retryable=False
        ) from exc
    except SummaryUnavailable as exc:
        raise orena_http_error(
            503, "reading_summary_unavailable", "The summary could not be made right now.", retryable=True
        ) from exc
    return {
        "status": "ready",
        "source_language": source,
        "target_language": payload.target_language.strip().casefold(),
        "bullets": bullets,
    }
