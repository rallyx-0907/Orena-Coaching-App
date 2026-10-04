"""Licences and data sources: one registry for the page and THIRD_PARTY_NOTICES, per-item credits from data."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

import app as app_module
from writing_coach.book_asset_store import FilesystemBookAssetStore
from writing_coach.licences import DATASETS, licences_payload
from writing_coach.word_audio import WordAudioLibrary

ROOT = Path(__file__).resolve().parents[1]


def test_every_registered_dataset_is_in_the_notices_file() -> None:
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    for dataset in DATASETS:
        assert f"`{dataset.id}`" in notices, dataset.id
        assert dataset.licence and dataset.attribution and dataset.source_url.startswith("https://")


def test_each_stored_word_recording_is_credited_from_its_own_record(tmp_path) -> None:
    store = FilesystemBookAssetStore(tmp_path)
    store.put("word-audio/abc.ogg", b"OggS")
    store.put("word-audio/abc.json", json.dumps({
        "key": "word-audio/abc.ogg", "mediaType": "audio/ogg",
        "source": "https://commons.wikimedia.org/wiki/File:En-us-basket.ogg",
        "license": "CC BY-SA 3.0", "attribution": "Some Speaker", "voice": "commons", "reading": "basket",
    }).encode("utf-8"))
    payload = licences_payload(word_audio=lambda: WordAudioLibrary(store, ()).credits())
    assert payload["audio"] == [{
        "source": "https://commons.wikimedia.org/wiki/File:En-us-basket.ogg", "licence": "CC BY-SA 3.0",
        "attribution": "Some Speaker", "reading": "basket", "voice": "commons",
    }]
    assert store.list_prefix("word-audio") == ["word-audio/abc.json", "word-audio/abc.ogg"]


def test_content_credits_come_from_their_owners_and_a_missing_owner_is_empty() -> None:
    def broken():
        raise RuntimeError("no PostgreSQL here")

    payload = licences_payload(
        listening=lambda: [{"title": "A pen", "source": {"title": "VOA clip", "creator": "VOA", "license": "Public domain", "provenance_url": "https://commons.wikimedia.org/x"}}],
        reading_sources=lambda: [
            {"name": "Open texts", "state": "active", "can_republish": True, "license_note": "CC BY 4.0", "base_url": "https://example.org"},
            {"name": "Paused", "state": "paused", "can_republish": True, "license_note": "CC BY 4.0", "base_url": "https://p.example"},
        ],
        books=broken,
    )
    assert [row["title"] for row in payload["content"]] == ["VOA clip", "Open texts"]
    assert {dataset["id"] for dataset in payload["datasets"]} >= {"cc-cedict", "wiktionary-vi", "open-dsl-dict"}


def test_the_licences_route_answers_without_a_provider() -> None:
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app_module.app), base_url="http://testserver") as client:
            return await client.get("/api/licences")

    response = asyncio.run(run())
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert set(body) == {"datasets", "content", "audio"}
    assert body["datasets"][0]["id"] == "cc-cedict"
