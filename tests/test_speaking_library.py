"""The Speaking library reads two real sources and invents nothing for either."""
from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from writing_coach import speaking_library
from writing_coach.speaking_library import SpeakingCatalogInvalid, parse_catalog


def item(**overrides):
    base = {
        "item_id": "restaurant-lines",
        "language": "zh",
        "title": "在餐厅点菜",
        "practice_type": "sentences",
        "level": "HSK 2",
        "status": "PUBLISHED",
        "lines": [{"line_id": "l1", "text": "我们想要一张靠窗的桌子。", "reading": "wǒmen xiǎng yào yì zhāng kào chuāng de zhuōzi", "translations": {"vi": "Chúng tôi muốn một bàn cạnh cửa sổ."}}],
    }
    base.update(overrides)
    return base


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(speaking_library.router)
    return TestClient(app)


def test_the_shipped_catalogue_is_valid_and_empty():
    raw = json.loads(speaking_library.CATALOG_PATH.read_text(encoding="utf-8"))
    assert parse_catalog(raw) == ()


def test_only_published_items_reach_the_library():
    items = parse_catalog({"schema_version": 1, "items": [item(), item(item_id="draft", status="DRAFT")]})
    assert [entry.item_id for entry in items] == ["restaurant-lines"]
    assert items[0].lines[0].text == "我们想要一张靠窗的桌子。"


@pytest.mark.parametrize(
    "broken",
    [
        {"practice_type": "karaoke"},
        {"language": "fr"},
        {"lines": []},
        {"lines": [{"line_id": "l1", "text": ""}]},
        {"title": 7},
    ],
)
def test_a_malformed_item_refuses_the_whole_catalogue(broken):
    with pytest.raises(SpeakingCatalogInvalid):
        parse_catalog({"schema_version": 1, "items": [item(**broken)]})


def test_duplicate_ids_are_refused():
    with pytest.raises(SpeakingCatalogInvalid):
        parse_catalog({"schema_version": 1, "items": [item(), item()]})


@pytest.mark.parametrize("language", ["en", "zh"])
def test_listening_lessons_that_can_be_shadowed_are_clip_items(client, language):
    body = client.get(f"/api/speaking/library?language={language}").json()
    assert body["language"] == language
    clips = [entry for entry in body["items"] if entry["source"] == "listening"]
    assert clips, "the catalogue ships shadowable lessons in both languages"
    for entry in clips:
        assert entry["practice_type"] == "clip"
        assert entry["id"].startswith("media:")
        assert entry["language"] == language
        assert entry["line_count"] >= 1
        # Only what a card draws; nothing about the provider or the source's rights.
        assert set(entry) == {"id", "source", "practice_type", "title", "language", "level", "line_count", "duration_ms", "artwork", "thumbnail_url"}


def test_authored_items_lead_and_open_with_their_lines(client, monkeypatch):
    authored = parse_catalog({"schema_version": 1, "items": [item()]})
    monkeypatch.setattr(speaking_library, "speaking_catalog", lambda: authored)
    body = client.get("/api/speaking/library?language=zh").json()
    assert body["items"][0]["id"] == "speak:restaurant-lines"
    assert body["items"][0]["line_count"] == 1
    opened = client.get("/api/speaking/items/restaurant-lines").json()
    assert opened["lines"][0]["reading"].startswith("wǒmen")
    assert client.get("/api/speaking/items/missing").status_code == 404


def test_an_unsupported_language_is_refused(client):
    assert client.get("/api/speaking/library?language=fr").status_code == 422
