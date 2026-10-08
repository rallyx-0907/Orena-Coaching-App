"""`GET /api/learner-summary` - the read route over `learner_summary` (I6).

Read-only and additive: each domain is read through the read the app already
serves, in the request's account and learning language. No surface calls it
yet; Profile and Growth views that consume it are later, separate slices.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from fastapi import APIRouter, Query

from writing_coach.core.errors import orena_http_error
from writing_coach.core.request_context import current_language_code
from writing_coach.learner_summary import Source, SummaryRequestError, learner_summary

router = APIRouter(prefix='/api', tags=['learner-summary'])

READING_BOUND = 30
LISTENING_BOUND = 100
SPEAKING_BOUND = 50
# Saved language is paged, so this is one bounded page. A page that fills its
# bound makes this domain's counts a lower bound, which is true - an unbounded
# call would quietly take the default page and report it as the whole library.
LANGUAGE_BOUND = 200

_sources: Callable[[], Sequence[Source]] | None = None


def configure_learner_summary(sources: Callable[[], Sequence[Source]] | None) -> None:
    global _sources
    _sources = sources


def runtime_sources(*, essays: Callable[[], Sequence[dict[str, Any]]], reading: Callable[[int], dict[str, Any]],
                    grammar: Callable[[], Any], library: Callable[[int], dict[str, Any]],
                    specialized: Any) -> Callable[[], list[Source]]:
    """The six domains, wired to the reads the app already serves."""

    def build() -> list[Source]:
        return [
            Source('writing', essays),
            Source('reading', lambda: reading(READING_BOUND).get('items', []), READING_BOUND),
            Source('listening', lambda: specialized.list_recent_listening_progress_records(LISTENING_BOUND), LISTENING_BOUND),
            Source('speaking', lambda: specialized.list_speaking_attempt_records(SPEAKING_BOUND), SPEAKING_BOUND),
            Source('grammar', grammar),
            Source('language', lambda: library(LANGUAGE_BOUND).get('items', []), LANGUAGE_BOUND),
        ]

    return build


@router.get('/learner-summary', name='orena_learner_summary')
def summary(window: str = Query('30d', max_length=8)) -> dict[str, Any]:
    if _sources is None:
        raise orena_http_error(503, 'learner_summary_unavailable', 'The learner summary is not configured.')
    try:
        return learner_summary(current_language_code(), _sources(), window=window)
    except SummaryRequestError as error:
        raise orena_http_error(422, error.reason, 'The learner summary request was refused.') from error
