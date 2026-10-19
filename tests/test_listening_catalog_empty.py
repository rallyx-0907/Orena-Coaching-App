"""The shipped built-in Listening catalogue is empty (D-245): every consumer reads zero lessons cleanly.

The six sample lessons were retired. Learner rows that name them (progress, places, takes, annotations) stay where
they are; a lookup of a retired id is the same as a lookup of a lesson that is not on the shelf - absent from every
list, 404 when opened, nothing resolved - never a 500. These tests run on the real shipped manifest, without the
fixture-local catalogue the catalogue-contract tests use.
"""
from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from writing_coach import listening_api, listening_catalog, model_clip_backfill, speaking_library
from writing_coach.collection_api import catalog_lesson_resolver
from writing_coach.media_library_store import FileMediaLibraryStore
from writing_coach.word_clips import clips_for

RETIRED_LESSONS = {
    "en-daily-pen-in-my-bag": ("commons-voa-anna-pen", "en"),
    "zh-daily-what-is-this": ("commons-zh-lesson-7-dialogue-1", "zh"),
    "zh-culture-nationalities": ("commons-zh-lesson-1-dialogue-2", "zh"),
    "zh-culture-where-are-you-from": ("commons-zh-lesson-1-dialogue-2", "zh"),
    "en-science-cosmic-calendar": ("commons-royalsociety-cosmic-calendar", "en"),
    "zh-technology-search-wikipedia": ("commons-zh-wikipedia-tutorial-1", "zh"),
}


@pytest.fixture(autouse=True)
def _no_imported_media(tmp_path):
    """Only the built-in shelf: imported media would fill the library and stop this being about the catalogue."""
    previous = listening_api._media_store
    listening_api.configure_listening_media_library(FileMediaLibraryStore(tmp_path / "media_library"))
    try:
        yield
    finally:
        listening_api.configure_listening_media_library(previous)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(listening_api.router)
    app.include_router(speaking_library.router)
    return TestClient(app)


def test_the_shipped_manifest_is_valid_and_carries_no_lesson():
    raw = json.loads(listening_catalog.CATALOG_MANIFEST.read_text(encoding="utf-8"))
    assert raw == {"schema_version": 1, "sources": [], "lessons": []}
    sources, lessons = listening_catalog.load_catalog_manifest(listening_catalog.CATALOG_MANIFEST)
    assert dict(sources) == {} and lessons == ()
    assert listening_catalog.CATALOG == ()
    assert listening_catalog.catalog_lessons() == ()


@pytest.mark.parametrize("language", ["en", "zh"])
def test_the_library_answers_an_empty_shelf_with_no_section(client, language):
    response = client.get(f"/api/listening/library?language={language}")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == [] and body["sections"] == []
    assert body["topics"] == [] and body["tags"] == []
    assert body["filters"]["levels"] == [] and body["filters"]["practice_modes"] == []


@pytest.mark.parametrize("lesson_id", sorted(RETIRED_LESSONS))
def test_a_retired_lesson_is_absent_and_answers_404_never_500(client, lesson_id):
    asset, _language = RETIRED_LESSONS[lesson_id]
    assert listening_catalog.catalog_lesson(lesson_id) is None
    assert client.get(f"/api/listening/library/{lesson_id}").status_code == 404
    assert client.get(f"/api/speaking/model-audio/{lesson_id}/{asset}:000").status_code == 404
    # A stored progress row or saved line that names the retired source resolves to nothing, as a hidden lesson does.
    assert listening_api.resolve_progress_line(asset, f"{asset}:000") is None
    assert catalog_lesson_resolver()(asset, f"{asset}:000") is None


@pytest.mark.parametrize("language", ["en", "zh"])
def test_speaking_word_clips_and_model_clip_backfill_read_zero_lessons(language):
    cards = speaking_library.speaking_library(language)
    assert not [card for card in cards if str(card.get("id", "")).startswith("media:")]
    assert clips_for("pen" if language == "en" else "什么", listening_catalog.catalog_lessons(language=language),
                     support="vi", limit=5) == []
    report = model_clip_backfill.backfill(
        None, None, language=language, include_catalog=True, include_entries=False, dry_run=True,
    )
    assert report["items"] == [] and report["prepared"] == report["failed"] == report["missing"] == 0
