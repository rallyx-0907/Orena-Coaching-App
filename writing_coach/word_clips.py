"""`/api/library/vocabulary/{word}/clips` — the word, heard in context.

The canonical frames "Vocabulary context clips" (06) and "Vocabulary context
clips mobile" (07). Every clip here is a **real moment in real media**: a
timestamped segment of a lesson in the listening catalogue whose own transcript
contains the word. Nothing is generated, nothing is stitched, and a word that
has never been said in the catalogue has no clips rather than a placeholder
one.

That is also why there is no new store. The catalogue already holds what the
frame draws - the segment's text, its pinyin, its translation, when it starts
and ends, and the lesson it belongs to - so this is a read over what is there,
bounded by how many clips the screen shows.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter, Query

from writing_coach import listening_catalog
from writing_coach.core.errors import orena_http_error
from writing_coach.core.request_context import current_language_code

router = APIRouter(prefix="/api/library", tags=["vocabulary-clips"])

# How many the screen draws: one playing and a short list under it. Reading
# more than that costs the learner time for nothing.
CLIPS = 6


def _text(value: object) -> str:
    return str(value or "").strip()


def at_label(start_ms: int) -> str:
    """Where in the lesson this is, as the frame writes it: mm:ss."""

    seconds = max(0, int(start_ms)) // 1000
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def segment_clip(
    lesson: Any, segment: Mapping[str, Any], *, support: str
) -> dict[str, Any]:
    """One segment, as the frame draws it."""

    start = int(segment.get("start_ms") or 0)
    end = int(segment.get("end_ms") or 0)
    translations = segment.get("translations") or {}
    return {
        "lessonId": _text(getattr(lesson, "lesson_id", "")),
        # The lesson's own title, which lives on the media asset; the topic is
        # what it falls back to, because a clip with no name at all would be a
        # row the learner cannot recognise.
        "title": _text(getattr(getattr(getattr(lesson, "media_object", None), "asset", None), "title", ""))
        or _text(getattr(lesson, "topic", "")),
        "at": at_label(start),
        "startMs": start,
        "endMs": end,
        "seconds": max(0, (end - start)) // 1000,
        "text": _text(segment.get("original_text")),
        "pinyin": _text(segment.get("pinyin")),
        "translation": _text(translations.get(support) if isinstance(translations, Mapping) else ""),
        "artwork": _text(getattr(lesson, "artwork", "")) or "listen",
        # How to play it: the lesson's own rights-reviewed reference, and the
        # kind, because an embed is not something the screen may seek inside.
        "url": _text(getattr(getattr(lesson, "playback", None), "url", "")),
        "kind": _text(getattr(getattr(lesson, "playback", None), "kind", "")),
    }


def clips_for(word: str, lessons: Any, *, support: str, limit: int = CLIPS) -> list[dict[str, Any]]:
    """Every moment in these lessons where the word is actually said.

    Earliest first within a lesson, lessons in the catalogue's own order, so
    the list is the same every time it is asked for. A segment is included only
    when its own transcript contains the word - the lesson's vocabulary list is
    not evidence that the word is in *this* moment.
    """

    wanted = _text(word)
    if not wanted:
        return []
    folded = wanted.casefold()
    found: list[dict[str, Any]] = []
    for lesson in lessons:
        source = getattr(lesson, "source", None)
        for segment in getattr(source, "segments", ()) or ():
            text = _text(segment.get("original_text"))
            if not text or folded not in text.casefold():
                continue
            found.append(segment_clip(lesson, segment, support=support))
            if len(found) >= limit:
                return found
    return found


@router.get("/vocabulary/{word}/clips", name="orena_word_clips")
def word_clips(word: str, limit: int = Query(default=CLIPS, ge=1, le=20)) -> dict[str, Any]:
    """Where this word is said in the catalogue, and what is said around it."""

    wanted = _text(word)
    if not wanted:
        raise orena_http_error(422, "word_required", "Ask about a word.")
    language = current_language_code().strip().casefold()
    lessons = listening_catalog.catalog_lessons(language=language)
    clips = clips_for(wanted, lessons, support=_support(), limit=limit)
    return {"word": wanted, "total": len(clips), "clips": clips}


def _support() -> str:
    from writing_coach.becoming_memory import get_learner_profile

    try:
        return _text(get_learner_profile().get("support_language")).casefold()
    except Exception:
        return ""
