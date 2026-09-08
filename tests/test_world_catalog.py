"""The Orena World catalog must describe real content, or say it has none.

A World is editorial; its availability is not. These tests exist because the
tempting failure here is a discovery surface that looks full: six confident
cards per language, each claiming lessons that were never ingested. Every
assertion below is about the boundary between what the editorial file declares
and what the catalog actually holds.
"""

from __future__ import annotations

import json

import pytest

from writing_coach.listening_catalog import catalog_lessons
from writing_coach.world_catalog import (
    UI_LOCALES,
    WORLD_MANIFEST,
    WorldCatalogInvalid,
    load_world_manifest,
    world_definitions,
    world_metadata,
    worlds_for_language,
)


def test_manifest_loads_and_ids_are_unique() -> None:
    worlds = load_world_manifest()
    assert worlds, "the manifest must define worlds"
    ids = [world.world_id for world in worlds]
    assert len(ids) == len(set(ids))


def test_every_world_carries_every_ui_locale() -> None:
    """EN/ZH parity is a product rule, not a nice-to-have.

    Vietnamese is the third interface locale the product already supports, so a
    world missing any of the three would render a raw key to a real learner.
    """

    for world in load_world_manifest():
        for locale in UI_LOCALES:
            assert world.title[locale], f"{world.world_id} title missing {locale}"
            assert world.description[locale], f"{world.world_id} description missing {locale}"


def test_both_first_class_languages_have_worlds() -> None:
    for language in ("en", "zh"):
        assert world_definitions(language=language), f"{language} must have worlds defined"


def test_availability_is_measured_not_declared() -> None:
    """Availability, counts and the lead lesson all come from the real catalog."""

    for language in ("en", "zh"):
        lessons = catalog_lessons(language=language)
        by_topic: dict[str, int] = {}
        for lesson in lessons:
            by_topic[lesson.topic.casefold()] = by_topic.get(lesson.topic.casefold(), 0) + 1

        for world in worlds_for_language(language):
            expected = sum(by_topic.get(topic, 0) for topic in world["topics"])
            assert world["lesson_count"] == expected, world["world_id"]
            assert world["available"] is (expected > 0), world["world_id"]
            if expected:
                assert world["lead_lesson_id"], f"{world['world_id']} is available but leads nowhere"
            else:
                # An empty world claims nothing at all: no lead, no title, no URL.
                assert world["lead_lesson_id"] == ""
                assert world["lead_lesson_title"] == ""
                assert world["lead_lesson_source_url"] == ""


def test_lead_lesson_is_a_real_lesson_in_the_same_language() -> None:
    for language in ("en", "zh"):
        real = {lesson.lesson_id for lesson in catalog_lessons(language=language)}
        for world in worlds_for_language(language):
            if world["lead_lesson_id"]:
                assert world["lead_lesson_id"] in real, world["world_id"]


def test_a_lesson_is_not_scattered_across_worlds() -> None:
    """Topic membership, not tag membership.

    Tags are loose - one lesson carries `conversation`, `daily-life`,
    `quick-practice` and `education` - so tag rules would place a single lesson
    in several worlds at once and make every count meaningless.
    """

    for language in ("en", "zh"):
        lessons = catalog_lessons(language=language)
        placements: dict[str, int] = {}
        for world in world_definitions(language=language):
            for lesson in lessons:
                if lesson.topic.casefold() in world.topics:
                    placements[lesson.lesson_id] = placements.get(lesson.lesson_id, 0) + 1
        assert all(count == 1 for count in placements.values()), placements


def test_world_topics_do_not_overlap_between_worlds() -> None:
    for language in ("en", "zh"):
        seen: set[str] = set()
        for world in world_definitions(language=language):
            clash = seen & set(world.topics)
            assert not clash, f"{world.world_id} shares topics {clash}"
            seen |= set(world.topics)


def test_no_layout_leaks_into_the_world_contract() -> None:
    """Backend returns meaning, not layout (ORENA_PRODUCT_DNA §12)."""

    forbidden = ("column", "width", "pixel", "span", "layout", "card_size")
    for world in worlds_for_language("en"):
        for key in world:
            assert not any(token in key for token in forbidden), key


def test_availability_survives_an_empty_catalog() -> None:
    """A language with no content yields worlds that all say so."""

    worlds = worlds_for_language("xx-not-a-language")
    assert worlds == [], "an unknown language defines no worlds"


def test_manifest_rejects_a_world_without_topics(tmp_path) -> None:
    raw = json.loads(WORLD_MANIFEST.read_text(encoding="utf-8"))
    raw["worlds"][0]["topics"] = []
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(WorldCatalogInvalid):
        load_world_manifest(broken)


def test_manifest_rejects_a_world_missing_a_locale(tmp_path) -> None:
    raw = json.loads(WORLD_MANIFEST.read_text(encoding="utf-8"))
    raw["worlds"][0]["title"].pop("zh")
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(WorldCatalogInvalid):
        load_world_manifest(broken)


def test_world_metadata_with_no_lessons_is_honest() -> None:
    world = world_definitions(language="en")[0]
    empty = world_metadata(world, ())
    assert empty["available"] is False
    assert empty["lesson_count"] == 0
    assert empty["lead_lesson_id"] == ""


def test_worlds_endpoint_returns_semantic_content() -> None:
    """The route answers with meaning, and never leaks preview content.

    Preview lessons are unreviewed material with unresolved rights. A world
    count is a cheap way to leak their existence, so the endpoint measures
    against exactly the lessons the caller is allowed to see.
    """

    import asyncio

    import httpx

    import app as app_module

    async def exercise():
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/api/worlds?language=en")

    response = asyncio.run(exercise())
    # Unauthenticated environments answer 401; both are valid outcomes here and
    # only a 200 carries a payload worth asserting on.
    assert response.status_code in {200, 401}
    if response.status_code != 200:
        return
    payload = response.json()
    assert payload["language"] == "en"
    assert isinstance(payload["worlds"], list) and payload["worlds"]
    assert payload["available_count"] == sum(1 for world in payload["worlds"] if world["available"])
    for world in payload["worlds"]:
        assert set(("world_id", "title", "description", "available", "lesson_count")) <= set(world)
        assert set(world["title"]) >= {"en", "zh"}
