"""Orena Worlds: the discovery layer above lessons.

A World is the first level of the canonical content graph
(Language -> World -> Zone -> Journey -> Lesson -> Activity). It is an
editorial place a learner enters, which is why the definitions live in one
versioned file rather than inside a screen.

The one rule that matters here: a World never asserts content. The editorial
file says which world exists and which lesson topics belong to it; every count,
every lead lesson and the availability flag itself are computed from the real
curated catalog at request time. A world with no real lesson today reports
available=False with a count of zero, and the client does not render it. That
is why the file can already describe six worlds per language while the catalog
holds three.

Membership is by canonical lesson topic, not by content tag. Tags are loose -
one lesson carries `conversation`, `daily-life`, `quick-practice`, `education` -
so tag membership would scatter a single lesson across four worlds and make
every count meaningless. Topic is the lesson's one canonical subject.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from writing_coach.listening_catalog import (
    CuratedListeningLesson,
    catalog_lessons,
    discovery_rank,
)

WORLD_MANIFEST = Path(__file__).with_name("content") / "orena_worlds.v1.json"

# The locales the interface is written in. A world carries copy for each, so a
# Vietnamese-interface learner studying Chinese reads the world in Vietnamese
# while the content stays Chinese.
UI_LOCALES = ("en", "zh", "vi")


class WorldCatalogInvalid(ValueError):
    """The editorial world file is not usable."""


@dataclass(frozen=True)
class World:
    world_id: str
    learning_language: str
    order: int
    topics: tuple[str, ...]
    artwork: str
    accent_family: str
    title: dict[str, str]
    description: dict[str, str]


def _text_map(raw: Any, *, field: str, world_id: str) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise WorldCatalogInvalid(f"{world_id}: {field} must be a locale map.")
    values = {}
    for locale in UI_LOCALES:
        value = raw.get(locale)
        if not isinstance(value, str) or not value.strip():
            raise WorldCatalogInvalid(
                f"{world_id}: {field} is missing {locale}. EN/ZH parity is not optional.")
        values[locale] = value.strip()
    return values


def load_world_manifest(path: Path = WORLD_MANIFEST) -> tuple[World, ...]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema_version") != 1:
        raise WorldCatalogInvalid("Unsupported world manifest schema version.")
    worlds: list[World] = []
    seen: set[str] = set()
    for entry in raw.get("worlds", ()):
        world_id = str(entry.get("world_id", "")).strip()
        if not world_id:
            raise WorldCatalogInvalid("A world is missing its id.")
        if world_id in seen:
            raise WorldCatalogInvalid(f"Duplicate world id {world_id}.")
        seen.add(world_id)
        topics = tuple(
            str(topic).strip().casefold()
            for topic in entry.get("topics", ())
            if str(topic).strip()
        )
        if not topics:
            raise WorldCatalogInvalid(f"{world_id}: a world needs at least one topic rule.")
        worlds.append(World(
            world_id=world_id,
            learning_language=str(entry.get("learning_language", "")).strip().casefold(),
            order=int(entry.get("order", 0)),
            topics=topics,
            artwork=str(entry.get("artwork", "")).strip(),
            accent_family=str(entry.get("accent_family", "")).strip(),
            title=_text_map(entry.get("title"), field="title", world_id=world_id),
            description=_text_map(entry.get("description"), field="description", world_id=world_id),
        ))
    return tuple(sorted(worlds, key=lambda world: (world.learning_language, world.order, world.world_id)))


@lru_cache(maxsize=1)
def _cached_manifest() -> tuple[World, ...]:
    return load_world_manifest()


def world_definitions(*, language: str | None = None) -> tuple[World, ...]:
    key = (language or "").strip().casefold()
    return tuple(
        world for world in _cached_manifest()
        if not key or world.learning_language == key
    )


def _members(world: World, lessons: tuple[CuratedListeningLesson, ...]) -> list[CuratedListeningLesson]:
    wanted = set(world.topics)
    return [lesson for lesson in lessons if lesson.topic.strip().casefold() in wanted]


def world_metadata(world: World, lessons: tuple[CuratedListeningLesson, ...]) -> dict[str, Any]:
    """One world, described against the content that actually exists.

    `lead_lesson_id` is the lesson the client opens when the learner enters the
    world, chosen by the same discovery ordering the Listening library uses, so
    a learner meets real poster-backed media first and the choice never wobbles
    between requests.
    """

    members = sorted(_members(world, lessons), key=discovery_rank)
    lead = members[0] if members else None
    return {
        "world_id": world.world_id,
        "learning_language": world.learning_language,
        "title": dict(world.title),
        "description": dict(world.description),
        "artwork": world.artwork,
        "accent_family": world.accent_family,
        "topics": list(world.topics),
        # Everything below is measured, never declared.
        "available": bool(members),
        "lesson_count": len(members),
        "lead_lesson_id": lead.lesson_id if lead is not None else "",
        "lead_lesson_title": lead.media_object.asset.title if lead is not None else "",
        "lead_lesson_source_url": lead.source.source_url if lead is not None else "",
        "lead_lesson_poster_url": lead.source.poster_url if lead is not None else "",
    }


def worlds_for_language(language: str, *, include_preview: bool = False) -> list[dict[str, Any]]:
    """Every defined world for a learning language, with real availability.

    Unavailable worlds are returned too, marked available=False and counted at
    zero. The client decides what to render; the contract stays honest about
    what the editorial plan is versus what exists today.
    """

    key = (language or "").strip().casefold()
    lessons = catalog_lessons(language=key or None, include_preview=include_preview)
    return [world_metadata(world, lessons) for world in world_definitions(language=key)]
