"""`GET /api/collection` - the read route over `collection_query` (I4 step 1).

Read-only and additive. The route reads each owner through the read it already
exposes, in the request's account and learning language, and changes nothing a
learner sees: no surface calls it yet, and the deferred `#/collection`
presentation stays as it is. Connecting My Content / My Language to it is a
later, separate slice.
"""
from __future__ import annotations

import os
import secrets
from collections.abc import Callable, Sequence
from typing import Any

from fastapi import APIRouter, Query

from writing_coach.collection_query import (
    CollectionQueryError,
    LessonRef,
    Owner,
    QueryScope,
    language_entries,
    media_entries_with,
    query_collection,
    reading_entries,
    speaking_entries_with,
    writing_entries,
)
from writing_coach.core.errors import orena_http_error
from writing_coach.core.request_context import current_language_code, current_user_key

router = APIRouter(prefix='/api', tags=['collection'])

# Each owner read is bounded where the owner bounds it; a read that fills its
# bound makes the collection's count unknown rather than guessed.
READING_BOUND = 30
LISTENING_BOUND = 100
SPEAKING_BOUND = 50
# The saved language arrives a page at a time, so this read takes one bounded
# page rather than the whole library. Asking for all of it is what made every
# screen that touched vocabulary cost what the whole vocabulary costs; asking
# without a bound would now silently take the first default page instead and
# call it everything.
LANGUAGE_BOUND = 200

_owners: Callable[[], Sequence[Owner]] | None = None
# Cursors are signed with the session secret when there is one. Without it they
# are signed per process, so a restart asks the client to start again - true,
# rather than a cursor anyone could forge.
_secret: bytes = (os.environ.get('SESSION_SECRET') or '').encode() or secrets.token_bytes(32)


def configure_collection(owners: Callable[[], Sequence[Owner]] | None, *, secret: bytes | None = None) -> None:
    global _owners, _secret
    _owners = owners
    if secret is not None:
        _secret = secret


def catalog_lesson_resolver() -> Callable[[str, str], LessonRef | None]:
    """The lesson a stored (source media, segment) pair belongs to.

    One source can back several lessons, so the segment has to fall inside the
    lesson's excerpt; a pair no visible lesson claims resolves to nothing.
    """
    from writing_coach.listening_catalog import catalog_lessons

    lessons = catalog_lessons()

    def resolve(asset: str, segment: str) -> LessonRef | None:
        for lesson in lessons:
            if lesson.source.source_media_id != asset:
                continue
            for item in lesson.source.segments:
                if str(item.get('segment_id')) != segment:
                    continue
                if int(item['start_ms']) >= lesson.excerpt_start_ms and int(item['end_ms']) <= lesson.excerpt_end_ms:
                    return LessonRef(lesson.lesson_id, lesson.media_object.asset.title)
        return None

    return resolve


def runtime_owners(*, library: Callable[[int], dict[str, Any]], reading: Callable[[int], dict[str, Any]],
                   essays: Callable[[], Sequence[dict[str, Any]]], specialized: Any) -> Callable[[], list[Owner]]:
    """The five owners, wired to the reads the app already serves."""
    resolve = catalog_lesson_resolver()

    def build() -> list[Owner]:
        return [
            Owner('language', lambda: library(LANGUAGE_BOUND).get('items', []), language_entries, LANGUAGE_BOUND),
            Owner('reading', lambda: reading(READING_BOUND).get('items', []), reading_entries, READING_BOUND),
            Owner('media', lambda: specialized.list_recent_listening_progress_records(LISTENING_BOUND),
                  media_entries_with(resolve), LISTENING_BOUND),
            Owner('writing', essays, writing_entries),
            Owner('speaking', lambda: specialized.list_speaking_attempt_records(SPEAKING_BOUND),
                  speaking_entries_with(resolve), SPEAKING_BOUND),
        ]

    return build


@router.get('/collection', name='orena_collection_query')
def collection(
    query: str = Query('', max_length=240),
    kinds: str = Query('', max_length=120),
    cursor: str = Query('', max_length=2048),
    limit: int = Query(20),
) -> dict[str, Any]:
    if _owners is None:
        raise orena_http_error(503, 'collection_unavailable', 'Collection retrieval is not configured.')
    scope = QueryScope(account=current_user_key(), language=current_language_code())
    try:
        return query_collection(
            scope,
            _owners(),
            secret=_secret,
            query=query,
            kinds=[kind for kind in kinds.split(',') if kind],
            cursor=cursor or None,
            limit=limit,
        )
    except CollectionQueryError as error:
        # A changed result is a conflict with the cursor, not a bad request:
        # the client starts again from the first page.
        status = 409 if error.reason == 'refresh_required' else 422
        raise orena_http_error(status, error.reason, 'The collection query was refused.') from error
