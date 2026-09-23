"""The Speaking library: what a learner can say, from two real sources.

1. The Speaking catalogue (``content/speaking_catalog.v1.json``): items authored for
   speaking - lines to read, sounds to practise, prompts to retell or answer. It ships
   empty. Adding an item is a content decision, not code (UI_BACKEND_GAPS SP-1).
2. Listening lessons that offer the ``shadowing`` mode: a real clip with timed lines,
   so the clip is the model and each line is a line to say.

Every card carries only what the Speaking library frame draws: title, practice type,
level, length, how many lines. Nothing is invented for an item that does not have it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from fastapi import APIRouter, Query

from writing_coach.core.errors import orena_http_error
from writing_coach.core.request_context import current_language_code
from writing_coach.listening_catalog import catalog_lessons

CATALOG_PATH = Path(__file__).resolve().parent / "content" / "speaking_catalog.v1.json"

# The practice types the Speaking library frame names. "clip" is shadowing a model clip.
PRACTICE_TYPES = ("sentences", "clip", "free", "sounds", "retell", "interview")
LANGUAGES = ("en", "zh")
_MAX_LINES = 60
_MAX_TEXT = 400


class SpeakingCatalogInvalid(ValueError):
    """The authored catalogue does not meet its contract."""


@dataclass(frozen=True)
class SpeakingLine:
    line_id: str
    text: str
    reading: str
    translations: Mapping[str, str]


@dataclass(frozen=True)
class SpeakingItem:
    item_id: str
    language: str
    title: str
    practice_type: str
    level: str
    artwork: str
    lines: tuple[SpeakingLine, ...]


def _text(value: Any, field: str, *, required: bool = True, limit: int = _MAX_TEXT) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str):
        raise SpeakingCatalogInvalid(f"{field} must be text")
    cleaned = value.strip()
    if required and not cleaned:
        raise SpeakingCatalogInvalid(f"{field} must not be empty")
    if len(cleaned) > limit:
        raise SpeakingCatalogInvalid(f"{field} is too long")
    return cleaned


def parse_catalog(raw: Mapping[str, Any]) -> tuple[SpeakingItem, ...]:
    """The published items of one catalogue document; anything malformed is refused whole."""
    if not isinstance(raw, Mapping) or raw.get("schema_version") != 1:
        raise SpeakingCatalogInvalid("schema_version must be 1")
    items = raw.get("items")
    if not isinstance(items, list):
        raise SpeakingCatalogInvalid("items must be a list")
    seen: set[str] = set()
    published: list[SpeakingItem] = []
    for index, entry in enumerate(items):
        where = f"items[{index}]"
        if not isinstance(entry, Mapping):
            raise SpeakingCatalogInvalid(f"{where} must be an object")
        item_id = _text(entry.get("item_id"), f"{where}.item_id", limit=120)
        if item_id in seen:
            raise SpeakingCatalogInvalid(f"{where}.item_id is duplicated")
        seen.add(item_id)
        language = _text(entry.get("language"), f"{where}.language", limit=8).casefold()
        if language not in LANGUAGES:
            raise SpeakingCatalogInvalid(f"{where}.language is unsupported")
        practice_type = _text(entry.get("practice_type"), f"{where}.practice_type", limit=20)
        if practice_type not in PRACTICE_TYPES:
            raise SpeakingCatalogInvalid(f"{where}.practice_type is unsupported")
        status = _text(entry.get("status"), f"{where}.status", limit=20).upper()
        raw_lines = entry.get("lines")
        if not isinstance(raw_lines, list) or not raw_lines or len(raw_lines) > _MAX_LINES:
            raise SpeakingCatalogInvalid(f"{where}.lines must hold 1-{_MAX_LINES} lines")
        lines: list[SpeakingLine] = []
        for at, line in enumerate(raw_lines):
            spot = f"{where}.lines[{at}]"
            if not isinstance(line, Mapping):
                raise SpeakingCatalogInvalid(f"{spot} must be an object")
            translations = line.get("translations") or {}
            if not isinstance(translations, Mapping):
                raise SpeakingCatalogInvalid(f"{spot}.translations must be an object")
            lines.append(
                SpeakingLine(
                    line_id=_text(line.get("line_id"), f"{spot}.line_id", limit=120),
                    text=_text(line.get("text"), f"{spot}.text"),
                    reading=_text(line.get("reading"), f"{spot}.reading", required=False),
                    translations={
                        _text(key, f"{spot}.translations key", limit=8): _text(value, f"{spot}.translations.{key}")
                        for key, value in translations.items()
                    },
                )
            )
        if status != "PUBLISHED":
            continue
        published.append(
            SpeakingItem(
                item_id=item_id,
                language=language,
                title=_text(entry.get("title"), f"{where}.title", limit=160),
                practice_type=practice_type,
                level=_text(entry.get("level"), f"{where}.level", required=False, limit=20),
                artwork=_text(entry.get("artwork"), f"{where}.artwork", required=False, limit=40),
                lines=tuple(lines),
            )
        )
    return tuple(published)


@lru_cache(maxsize=1)
def speaking_catalog() -> tuple[SpeakingItem, ...]:
    return parse_catalog(json.loads(CATALOG_PATH.read_text(encoding="utf-8")))


def _catalog_card(item: SpeakingItem) -> dict[str, Any]:
    return {
        "id": f"speak:{item.item_id}",
        "source": "speaking",
        "practice_type": item.practice_type,
        "title": item.title,
        "language": item.language,
        "level": item.level,
        "line_count": len(item.lines),
        "duration_ms": None,
        "artwork": item.artwork or "speaking",
        "thumbnail_url": None,
    }


def _lesson_card(lesson: Any) -> dict[str, Any]:
    transcript = lesson.media_object.transcript
    return {
        "id": f"media:{lesson.lesson_id}",
        "source": "listening",
        "practice_type": "clip",
        "title": lesson.media_object.asset.title,
        "language": lesson.source.language,
        "level": lesson.level or "",
        "line_count": len(transcript.segments) if transcript else 0,
        "duration_ms": lesson.duration_ms,
        "artwork": lesson.artwork,
        "thumbnail_url": lesson.source.poster_url,
    }


def speaking_library(language: str) -> list[dict[str, Any]]:
    authored = [_catalog_card(item) for item in speaking_catalog() if item.language == language]
    shadowable = [
        _lesson_card(lesson)
        for lesson in catalog_lessons(language=language)
        if "shadowing" in lesson.available_modes
        and lesson.media_object.transcript
        and lesson.media_object.transcript.segments
    ]
    return authored + shadowable


router = APIRouter(prefix="/api/speaking", tags=["speaking"])


@router.get("/library")
def read_speaking_library(
    language: str | None = Query(default=None, min_length=2, max_length=8),
) -> dict[str, Any]:
    selected = (language or current_language_code()).strip().casefold()
    if selected not in LANGUAGES:
        raise orena_http_error(422, "speaking_language_invalid", "Unsupported speaking language.")
    return {"language": selected, "items": speaking_library(selected)}


@router.get("/items/{item_id}")
def read_speaking_item(item_id: str) -> dict[str, Any]:
    """One authored item with its lines, for the Speaking workspace."""
    item = next((entry for entry in speaking_catalog() if entry.item_id == item_id), None)
    if item is None:
        raise orena_http_error(404, "speaking_item_not_found", "This Speaking item is unavailable.")
    return {
        **_catalog_card(item),
        "lines": [
            {
                "line_id": line.line_id,
                "text": line.text,
                "reading": line.reading,
                "translations": dict(line.translations),
            }
            for line in item.lines
        ],
    }
