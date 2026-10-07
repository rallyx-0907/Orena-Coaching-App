"""D-140: a line's model clip is cut once at content readiness and only ever read afterwards (D-121)."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from writing_coach import media_library_api, model_clips, speaking_library
from writing_coach.book_asset_store import AssetNotFound
from writing_coach.media_library_store import MediaLibraryEntry
from writing_coach.media_transcript_pipeline import MediaPipeline

LESSON = "en-daily-pen-in-my-bag"


class MemoryAssets:
    def __init__(self, items=None):
        self.items = dict(items or {})
        self.puts: list[str] = []

    def get(self, key):
        try:
            return self.items[key]
        except KeyError as exc:
            raise AssetNotFound(key) from exc

    def exists(self, key):
        return key in self.items

    def put(self, key, data):
        self.puts.append(key)
        self.items[key] = data


def _entry(**overrides) -> MediaLibraryEntry:
    segments = [
        {"segment_id": "a", "start_ms": 0, "end_ms": 1500, "original_text": "One."},
        {"segment_id": "b", "start_ms": 1500, "end_ms": 3000, "original_text": "Two."},
        {"segment_id": "too-long", "start_ms": 3000, "end_ms": 3000 + 70_000, "original_text": "Long."},
    ]
    base = dict(
        media_id="upload-owned", media_type="audio", provider="upload", provider_media_id="owned", canonical_url="",
        playback={"provider": "orena", "kind": "audio", "url": "/api/media/files/media/owned/original.wav"},
        title="Owned", thumbnail={"kind": "none", "ref": ""}, duration_ms=80_000, language="en", level="",
        creator="", source={"owner": "owner-token"}, library="personal", created_at="2026-10-07T00:00:00+00:00",
        status="published",
        lesson={"status": "PUBLISHED", "payload": {"asset": {"source_language": "en"}, "transcript": {"segments": segments}}},
    )
    base.update(overrides)
    return MediaLibraryEntry(**base)


@pytest.fixture
def cuts(monkeypatch):
    calls: list[tuple[int, int]] = []

    def fake_cut(source, line):
        calls.append((line.start_ms, line.end_ms))
        return b"clip:" + line.segment_id.encode()

    monkeypatch.setattr(model_clips, "cut_clip", fake_cut)
    return calls


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(speaking_library.router)
    return TestClient(app)


def test_readiness_materializes_each_line_once_per_revision(cuts, monkeypatch):
    assets = MemoryAssets({"media/owned/original.wav": b"source"})
    pipeline = MediaPipeline(ledger=object(), workers=1)
    entry = _entry(status="processing", lesson={**_entry().lesson, "status": "NEEDS_REVIEW"})

    pipeline._prepare_model_clips(assets, entry)
    assert cuts == [(0, 1500), (1500, 3000)], "the over-long line is not speakable"
    assert all(key.startswith("media/owned/model-clip/") for key in assets.puts), "a private upload's clips live under it"

    cuts.clear()
    pipeline._prepare_model_clips(assets, entry)
    assert cuts == [], "a second readiness run cuts nothing"

    moved = replace(entry, playback={**entry.playback, "url": "/api/media/files/media/owned/original-2.wav"})
    assets.items["media/owned/original-2.wav"] = b"other"
    pipeline._prepare_model_clips(assets, moved)
    assert len(cuts) == 2, "a new source revision is a new identity"


def test_a_failed_preparation_never_fails_readiness(monkeypatch):
    assets = MemoryAssets()  # the source is missing
    MediaPipeline(ledger=object(), workers=1)._prepare_model_clips(assets, _entry())
    assert assets.puts == []


def test_the_clip_route_serves_stored_bytes_and_never_cuts(client, monkeypatch, cuts):
    entry = _entry()
    assets = MemoryAssets()
    monkeypatch.setattr(media_library_api, "find_entry", lambda media_id: entry if media_id == entry.media_id else None)
    monkeypatch.setattr(media_library_api, "_asset_store", assets)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("a read must not cut, fetch or prepare")

    monkeypatch.setattr(speaking_library, "_line_source_file", forbidden)
    monkeypatch.setattr(speaking_library, "_cut_model_line", forbidden)
    monkeypatch.setattr(speaking_library.subprocess, "run", forbidden)

    miss = client.get("/api/speaking/model-clip/upload-owned/a")
    assert miss.status_code == 404 and "speaking_model_clip_not_prepared" in miss.text
    assert cuts == [] and assets.puts == []

    line = next(item for item in speaking_library.entry_clip_lines(entry) if item.segment_id == "a")
    assets.items[line.key] = b"stored-clip"
    hit = client.get("/api/speaking/model-clip/upload-owned/a")
    assert hit.status_code == 200 and hit.content == b"stored-clip"
    assert hit.headers["content-type"].startswith("audio/webm")
    assert client.get("/api/speaking/model-clip/upload-owned/other-line").status_code == 404
    assert cuts == [] and assets.puts == []


def test_the_clip_route_keeps_the_access_gates(client, monkeypatch):
    entry = _entry()
    assets = MemoryAssets()
    line = next(item for item in speaking_library.entry_clip_lines(entry) if item.segment_id == "a")
    assets.items[line.key] = b"stored-clip"
    monkeypatch.setattr(media_library_api, "_asset_store", assets)
    monkeypatch.setattr(media_library_api, "find_entry", lambda _media_id: None)
    assert client.get("/api/speaking/model-clip/upload-owned/a").status_code == 404


def test_catalogue_clips_use_the_identity_the_route_reads(client, monkeypatch, cuts):
    from writing_coach.listening_catalog import catalog_lesson

    lesson = catalog_lesson(LESSON)
    lines = speaking_library.catalog_clip_lines(lesson)
    assert lines
    assets = MemoryAssets()
    monkeypatch.setattr(media_library_api, "_asset_store", assets)
    result = model_clips.prepare_clips(assets, Path("unused"), lines[:1])
    assert result.prepared == 1
    first = lines[0].segment_id
    assert client.get(f"/api/speaking/model-clip/{LESSON}/{first}").content == b"clip:" + first.encode()
    assert speaking_library.prepared_clip_segments(LESSON, lesson=lesson) == [first]
    other = lines[1].segment_id if len(lines) > 1 else None
    if other:
        assert client.get(f"/api/speaking/model-clip/{LESSON}/{other}").status_code == 404


class _Store:
    def __init__(self, entries):
        self.entries = entries

    def list(self, *, language=None, library="shared", status="published"):
        return [item for item in self.entries if item.library == library]


def test_backfill_is_idempotent_and_bounded(cuts):
    from writing_coach.model_clip_backfill import backfill

    store = _Store([_entry()])
    assets = MemoryAssets()
    sources = []

    def entry_source(entry, work, **_kwargs):
        sources.append(entry.media_id)
        return Path("source")

    common = dict(include_catalog=False, entry_source=entry_source)
    dry = backfill(store, assets, dry_run=True, **common)
    assert dry["missing"] == 2 and cuts == [] and sources == []

    bounded = backfill(store, assets, max_lines=1, **common)
    assert bounded["prepared"] == 1 and bounded["stopped_by_bound"] is True and len(cuts) == 1

    rest = backfill(store, assets, **common)
    assert rest["prepared"] == 1 and rest["existing"] == 1 and len(cuts) == 2

    again = backfill(store, assets, **common)
    assert again["prepared"] == 0 and again["missing"] == 0 and len(cuts) == 2
    assert sources == ["upload-owned", "upload-owned"], "a complete item is never re-acquired"


def test_backfill_bounds_the_audio_it_covers(cuts):
    from writing_coach.model_clip_backfill import backfill

    report = backfill(_Store([_entry()]), MemoryAssets(), include_catalog=False, max_audio_ms=2000,
                      entry_source=lambda *_a, **_k: Path("source"))
    assert report["prepared"] == 1 and report["stopped_by_bound"] is True


def test_the_lesson_payload_names_prepared_segments_only(monkeypatch):
    from writing_coach import listening_api
    from writing_coach.listening_catalog import catalog_lesson

    lesson = catalog_lesson(LESSON)
    lines = speaking_library.catalog_clip_lines(lesson)
    assets = MemoryAssets({lines[0].key: b"x"})
    monkeypatch.setattr(media_library_api, "_asset_store", assets)
    assert listening_api._prepared_model_clips(lesson=lesson) == [lines[0].segment_id]
    monkeypatch.setattr(media_library_api, "_asset_store", None)
    assert listening_api._prepared_model_clips(lesson=lesson) == []


def test_a_chinese_catalogue_clip_is_served_in_chinese_and_refused_in_english(client, monkeypatch, cuts):
    from writing_coach.listening_catalog import catalog_lessons

    lesson = next(item for item in catalog_lessons(language="zh") if item.playback.kind in {"audio", "video"})
    lines = speaking_library.catalog_clip_lines(lesson)
    assets = MemoryAssets()
    monkeypatch.setattr(media_library_api, "_asset_store", assets)
    model_clips.prepare_clips(assets, Path("unused"), lines)
    url = f"/api/speaking/model-clip/{lesson.lesson_id}/{lines[0].segment_id}"
    assert client.get(url).status_code == 404, "the learner's language is English"
    monkeypatch.setattr(speaking_library, "current_language_code", lambda: "zh")
    assert client.get(url).content == b"clip:" + lines[0].segment_id.encode()
