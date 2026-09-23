"""The learner's side of the Reading Content Engine - published articles only.

Two routes, and the whole design of this file is in what they refuse to do.

`GET /api/reading/articles` is a page of lightweight cards: id, title,
language, level, topic, reading time, excerpt. No body, no source snapshot, no
analysis, no learning targets, no review history, no job state. Filtering and
ordering happen in the database with a bounded limit and a keyset cursor, so a
learner's request is the same size whether the corpus holds 500 articles or
500,000 - which is the point of the whole engine's persistence design.

`GET /api/reading/articles/{id}` is one article: its text, the targets an
admin approved, and the attribution its rights require. It carries an ETag
built from the article's `content_revision`, so a learner who opens the same
article again revalidates cheaply instead of downloading it twice.

Neither route exposes anything about ingestion. A learner session never polls
a job endpoint, never sees a candidate, and never learns that an article was
once in a review queue.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Request, Response
from sqlalchemy.exc import SQLAlchemyError

from writing_coach.core.errors import orena_http_error
from writing_coach.persistence.reading_content_repository import (
    MAX_ARTICLE_PAGE,
    InvalidCursor,
    ReadingContentRepository,
)

router = APIRouter(prefix="/api/reading/articles", tags=["reading-articles"])
_logger = logging.getLogger(__name__)

DEFAULT_PAGE = 24
# A learner's published content is worth revalidating rather than refetching,
# and worth a short shared cache: an article changes only when an admin edits
# it, and its `content_revision` moves when that happens.
LEARNER_CACHE_CONTROL = "public, max-age=60, stale-while-revalidate=600"

_repository: ReadingContentRepository | None = None
_language_supported: Callable[[str], bool] | None = None


def configure_reading_articles(
    repository: ReadingContentRepository | None,
    *,
    language_supported: Callable[[str], bool] | None = None,
) -> None:
    global _repository, _language_supported
    _repository = repository
    _language_supported = language_supported


def _require_repository() -> ReadingContentRepository:
    if _repository is None:
        raise orena_http_error(
            503, "reading_articles_unavailable", "Reading articles are not available yet."
        )
    return _repository


def _language(raw: str) -> str:
    language = (raw or "").strip().casefold()
    if not language:
        raise orena_http_error(422, "reading_invalid_language", "Choose a learning language.")
    if _language_supported is not None and not _language_supported(language):
        raise orena_http_error(422, "reading_invalid_language", "Unsupported learning language.")
    return language


def _guarded(call: Callable[[], Any]) -> Any:
    """One truthful "not available yet" for a learner, never a database error."""
    try:
        return call()
    except InvalidCursor as exc:
        raise orena_http_error(422, "reading_invalid_cursor", "That page is no longer valid.") from exc
    except SQLAlchemyError as exc:
        _logger.warning("reading articles: schema not ready", exc_info=True)
        raise orena_http_error(
            503, "reading_articles_unavailable", "Reading articles are not available yet."
        ) from exc


@router.get("")
def list_articles(
    request: Request,
    response: Response,
    language: str,
    level: str = "",
    topic: str = "",
    cursor: str = "",
    limit: int = DEFAULT_PAGE,
) -> dict[str, Any]:
    """One bounded page of published cards, newest first."""
    repository = _require_repository()
    page = _guarded(
        lambda: repository.list_published(
            language=_language(language),
            level=level.strip() or None,
            topic=topic.strip() or None,
            cursor=cursor or None,
            limit=max(1, min(int(limit), MAX_ARTICLE_PAGE)),
        )
    )
    response.headers["Cache-Control"] = LEARNER_CACHE_CONTROL
    return page


@router.get("/{article_id}")
def read_article(request: Request, response: Response, article_id: str) -> Any:
    """One published article, revalidated by its content revision.

    An article that is not published is a 404, not a 403: a learner has no
    business learning that a candidate exists, and "not found" is the truthful
    answer to "may I read this".
    """
    repository = _require_repository()
    article = _guarded(lambda: repository.get_published_article(article_id))
    if article is None:
        raise orena_http_error(404, "reading_article_not_found", "That article is not available.")
    etag = f'W/"reading-{article["id"]}-{article["content_revision"]}"'
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = LEARNER_CACHE_CONTROL
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=dict(response.headers))
    return article
