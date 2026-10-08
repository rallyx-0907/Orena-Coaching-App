"""Task D: the Daily Vocabulary Feed read route.

`GET /api/vocabulary/feed` is a filtered, day-seeded view over the same
static catalog the Library collection routes browse directly
(`writing_coach/vocabulary_feed.py`). It builds its exclusion set from the
learner's existing saved words (`list_library_vocabulary()`) and never
creates a `SavedWord`-equivalent row itself — "keep" reuses the existing
`POST /api/library/vocabulary` with `source_kind="feed"`, unmodified by this
route.
"""
from __future__ import annotations

import asyncio
import re

import httpx
import pytest

import app as app_module
from writing_coach.becoming_library import LibraryVocabularyIn
from writing_coach.core.request_context import LANGUAGE_CODE_CTX


def _seed_saved_word(language_code: str, word: str) -> None:
    token = LANGUAGE_CODE_CTX.set(language_code)
    try:
        app_module.init_db()
        app_module.save_library_vocabulary(
            LibraryVocabularyIn(word=word, definition="seeded", source_kind="manual")
        )
    finally:
        LANGUAGE_CODE_CTX.reset(token)


def _get(path: str) -> httpx.Response:
    async def exercise() -> httpx.Response:
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(path)

    return asyncio.run(exercise())


def test_feed_requires_language_code() -> None:
    assert _get("/api/vocabulary/feed").status_code == 422


@pytest.mark.parametrize("language_code", ["fr", "xx", "vi"])
def test_feed_rejects_unsupported_language_code(language_code: str) -> None:
    response = _get(f"/api/vocabulary/feed?language_code={language_code}")
    assert response.status_code == 422


def test_feed_response_shape_and_stable_date() -> None:
    first = _get("/api/vocabulary/feed?language_code=en")
    second = _get("/api/vocabulary/feed?language_code=en")
    assert first.status_code == 200 and second.status_code == 200
    first_body, second_body = first.json(), second.json()
    assert set(first_body.keys()) == {"items", "date"}
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", first_body["date"])
    assert first_body["date"] == second_body["date"], "the Feed date is stable within the same day"
    assert isinstance(first_body["items"], list) and first_body["items"]


def test_feed_never_claims_memory_or_leaks_an_internal_path() -> None:
    response = _get("/api/vocabulary/feed?language_code=en")
    body = response.json()
    assert all("memory" not in item for item in body["items"])
    serialized = response.text
    assert "vocabulary_collections.json" not in serialized
    assert "writing_coach/languages" not in serialized
    assert "writing_coach\\languages" not in serialized


def test_feed_excludes_an_already_saved_word() -> None:
    baseline = _get("/api/vocabulary/feed?language_code=zh").json()
    assert baseline["items"], "the Chinese Feed pool should not start empty"
    headword_to_exclude = baseline["items"][0]["headword"]

    _seed_saved_word("zh", headword_to_exclude)

    after = _get("/api/vocabulary/feed?language_code=zh").json()
    assert headword_to_exclude not in {item["headword"] for item in after["items"]}


def test_feed_target_level_narrows_the_pool_when_matches_exist() -> None:
    response = _get("/api/vocabulary/feed?language_code=en&target_level=A1")
    body = response.json()
    assert body["items"], "a target_level that matches real entries must not starve the feed"
    assert all(item.get("level") == "A1" for item in body["items"])


def test_feed_target_level_does_not_starve_the_feed_when_nothing_matches() -> None:
    # No seed entry currently carries level "C2"; the pool must fall back to
    # the full per-language catalog rather than returning nothing.
    response = _get("/api/vocabulary/feed?language_code=en&target_level=C2")
    body = response.json()
    assert body["items"], "an unmatched declared target_level must fall back, not starve, the feed"
