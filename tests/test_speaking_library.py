"""The Speaking library reads two real sources and invents nothing for either."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from writing_coach import speaking_library
from writing_coach.speaking_library import SpeakingCatalogInvalid, parse_catalog


class _MemoryAssets:
    def __init__(self, items=None):
        self.items = dict(items or {})
        self.reads = []

    def get(self, key):
        from writing_coach.book_asset_store import AssetNotFound

        self.reads.append(key)
        try:
            return self.items[key]
        except KeyError as exc:
            raise AssetNotFound(key) from exc

    def put(self, key, data):
        self.items[key] = data


def _fake_ffmpeg(command, **kwargs):
    Path(command[-1]).write_bytes(b"owned-line-clip")
    return type("Completed", (), {"returncode": 0})()


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


def test_model_audio_serves_only_a_catalogue_lessons_own_line(client, monkeypatch):
    calls = []
    monkeypatch.setattr(speaking_library, "_source_file", lambda lesson: calls.append(lesson.lesson_id) or None)
    assert client.get("/api/speaking/model-audio/not-a-lesson/x").status_code == 404
    assert client.get("/api/speaking/model-audio/en-daily-pen-in-my-bag/some-other-segment").status_code == 404
    assert calls == [], "nothing is fetched for a line that is not the lesson's own"


def test_model_audio_returns_the_cut_line(client, monkeypatch):
    monkeypatch.setattr(speaking_library, "model_line_audio", lambda lesson, segment: b"OggS-line")
    response = client.get("/api/speaking/model-audio/en-daily-pen-in-my-bag/commons-voa-anna-pen:000")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/webm")
    assert response.headers["cache-control"] == "private, no-store"
    assert response.content == b"OggS-line"


def test_model_audio_serves_a_published_owned_import_from_its_durable_asset(client, monkeypatch, tmp_path):
    from writing_coach import media_library_api
    from writing_coach.media_library_store import MediaLibraryEntry

    segment = {"segment_id": "owned-line", "start_ms": 1200, "end_ms": 2600, "original_text": "Say this."}
    entry = MediaLibraryEntry(
        media_id="upload-owned",
        media_type="audio",
        provider="upload",
        provider_media_id="owned",
        canonical_url="",
        playback={"provider": "orena", "kind": "audio", "url": "/api/media/files/media/owned/original.wav"},
        title="Owned recording",
        thumbnail={"kind": "none", "ref": ""},
        duration_ms=4000,
        language="en",
        level="",
        creator="",
        source={"owner": "owner-token"},
        library="personal",
        created_at="2026-10-03T00:00:00+00:00",
        lesson={"status": "PUBLISHED", "payload": {
            "asset": {"source_language": "en"},
            "transcript": {"segments": [segment]},
        }},
    )

    class Assets:
        def get(self, key):
            assert key == "media/owned/original.wav"
            return b"durable-private-audio"

    monkeypatch.setattr(media_library_api, "find_entry", lambda media_id: entry if media_id == entry.media_id else None)
    monkeypatch.setattr(media_library_api, "_asset_store", Assets())
    monkeypatch.setattr(speaking_library, "_MODEL_CACHE", tmp_path)
    commands = []

    def fake_ffmpeg(command, **kwargs):
        commands.append(command)
        Path(command[-1]).write_bytes(b"owned-line-clip")
        return type("Completed", (), {"returncode": 0})()

    monkeypatch.setattr(speaking_library.subprocess, "run", fake_ffmpeg)
    response = client.get("/api/speaking/model-audio/upload:upload-owned/owned-line")

    assert response.status_code == 200
    assert response.content == b"owned-line-clip"
    assert commands and commands[0][commands[0].index("-ss") + 1] == "1.200"


def test_cached_import_model_audio_rechecks_visibility_and_language(client, monkeypatch, tmp_path):
    from writing_coach import media_library_api
    from writing_coach.media_library_store import MediaLibraryEntry

    entry = MediaLibraryEntry(
        media_id="upload-owned",
        media_type="audio",
        provider="upload",
        provider_media_id="owned",
        canonical_url="",
        playback={"provider": "orena", "kind": "audio", "url": "/api/media/files/media/owned/original.wav"},
        title="Owned recording",
        thumbnail={"kind": "none", "ref": ""},
        duration_ms=4000,
        language="en",
        level="",
        creator="",
        source={"owner": "owner-token"},
        library="personal",
        created_at="2026-10-03T00:00:00+00:00",
        lesson={"status": "PUBLISHED", "payload": {
            "asset": {"source_language": "en"},
            "transcript": {"segments": [{"segment_id": "owned-line", "start_ms": 0, "end_ms": 1000, "original_text": "Say this."}]},
        }},
    )

    class Assets:
        def get(self, key):
            return b"durable-private-audio"

    visible = True
    monkeypatch.setattr(media_library_api, "find_entry", lambda _media_id: entry if visible else None)
    monkeypatch.setattr(media_library_api, "_asset_store", Assets())
    monkeypatch.setattr(speaking_library, "_MODEL_CACHE", tmp_path)

    def fake_ffmpeg(command, **kwargs):
        Path(command[-1]).write_bytes(b"owned-line-clip")
        return type("Completed", (), {"returncode": 0})()

    monkeypatch.setattr(speaking_library.subprocess, "run", fake_ffmpeg)
    assert client.get("/api/speaking/model-audio/upload-owned/owned-line").status_code == 200

    visible = False
    assert client.get("/api/speaking/model-audio/upload-owned/owned-line").status_code == 404


@pytest.mark.parametrize("reason", ["unpublished", "other-language"])
def test_model_audio_rejects_unpublished_or_other_language_imports(client, monkeypatch, reason):
    from writing_coach import media_library_api
    from writing_coach.core import request_context
    from writing_coach.media_library_store import MediaLibraryEntry

    entry = MediaLibraryEntry(
        media_id="upload-owned",
        media_type="audio",
        provider="upload",
        provider_media_id="owned",
        canonical_url="",
        playback={"provider": "orena", "kind": "audio", "url": "/api/media/files/media/owned/original.wav"},
        title="Owned recording",
        thumbnail={"kind": "none", "ref": ""},
        duration_ms=4000,
        language="en",
        level="",
        creator="",
        source={"owner": "owner-token"},
        library="personal",
        created_at="2026-10-03T00:00:00+00:00",
        lesson={"status": "PUBLISHED", "payload": {
            "asset": {"source_language": "en"},
            "transcript": {"segments": [{"segment_id": "owned-line", "start_ms": 0, "end_ms": 1000, "original_text": "Say this."}]},
        }},
    )
    if reason == "unpublished":
        entry = replace(entry, status="unpublished")
    else:
        monkeypatch.setattr(request_context, "current_language_code", lambda: "zh")
    monkeypatch.setattr(media_library_api, "find_entry", lambda _media_id: entry)

    response = client.get("/api/speaking/model-audio/upload-owned/owned-line")

    assert response.status_code == 404


def test_model_reference_uses_canonical_word_times_without_provider_assessment(client, monkeypatch, tmp_path):
    from writing_coach import media_library_api, speech_api
    from writing_coach.media_library_store import MediaLibraryEntry

    entry = MediaLibraryEntry(
        media_id="upload-owned",
        media_type="audio",
        provider="upload",
        provider_media_id="owned",
        canonical_url="",
        playback={"provider": "orena", "kind": "audio", "url": "/api/media/files/media/owned/original.wav"},
        title="Owned recording",
        thumbnail={"kind": "none", "ref": ""},
        duration_ms=4000,
        language="en",
        level="",
        creator="",
        source={"owner": "owner-token"},
        library="personal",
        created_at="2026-10-03T00:00:00+00:00",
        lesson={"status": "PUBLISHED", "payload": {
            "asset": {"source_language": "en"},
            "transcript": {"segments": [{
                "segment_id": "owned-line", "start_ms": 1200, "end_ms": 2600,
                "original_text": "Say this.",
                "words": [
                    {"text": "Say", "start_ms": 1250, "end_ms": 1600},
                    {"text": "this.", "start_ms": 1650, "end_ms": 2050},
                ],
            }]},
        }},
    )
    assets = _MemoryAssets({"media/owned/original.wav": b"durable-private-audio"})
    monkeypatch.setattr(media_library_api, "find_entry", lambda _media_id: entry)
    monkeypatch.setattr(media_library_api, "_asset_store", assets)
    monkeypatch.setattr(speaking_library, "_MODEL_CACHE", tmp_path)
    monkeypatch.setattr(speech_api, "_pronunciation_provider", lambda: pytest.fail("canonical timing must avoid assessment"))
    monkeypatch.setattr(speaking_library.subprocess, "run", _fake_ffmpeg)

    response = client.post("/api/speaking/model-reference/upload-owned/owned-line", json={"reference_text": "ignored"})

    assert response.status_code == 200
    body = response.json()
    assert body["model_audio_available"] is True
    assert body["score_kind"] == "measured"
    assert body["words"] == [
        {"text": "Say", "offset_ms": 50, "duration_ms": 350, "error_type": "None"},
        {"text": "this.", "offset_ms": 450, "duration_ms": 400, "error_type": "None"},
    ]
    assert body["source_fingerprint"]
    assert "accuracy_score" not in body


@pytest.mark.parametrize("alphabet, expected_ipa", [("IPA", "/seɪ/"), ("SAPI", None)])
def test_model_reference_calls_configured_provider_once_and_rechecks_source(client, monkeypatch, tmp_path, alphabet, expected_ipa):
    from types import SimpleNamespace

    from writing_coach import media_library_api, speech_api
    from writing_coach.media_library_store import MediaLibraryEntry

    entry = MediaLibraryEntry(
        media_id="upload-owned",
        media_type="audio",
        provider="upload",
        provider_media_id="owned",
        canonical_url="",
        playback={"provider": "orena", "kind": "audio", "url": "/api/media/files/media/owned/original.wav"},
        title="Owned recording",
        thumbnail={"kind": "none", "ref": ""},
        duration_ms=4000,
        language="en",
        level="",
        creator="",
        source={"owner": "owner-token"},
        library="personal",
        created_at="2026-10-03T00:00:00+00:00",
        lesson={"status": "PUBLISHED", "payload": {
            "asset": {"source_language": "en"},
            "transcript": {"segments": [{"segment_id": "owned-line", "start_ms": 0, "end_ms": 1000, "original_text": "Say this."}]},
        }},
    )
    assets = _MemoryAssets({"media/owned/original.wav": b"durable-private-audio"})
    visible = True
    monkeypatch.setattr(media_library_api, "find_entry", lambda _media_id: entry if visible else None)
    monkeypatch.setattr(media_library_api, "_asset_store", assets)
    monkeypatch.setattr(speaking_library, "_MODEL_CACHE", tmp_path)
    monkeypatch.setattr(speaking_library.subprocess, "run", _fake_ffmpeg)
    provider = SimpleNamespace(
        provider_id="azure-speech", _region="westus", _en_locale="en-US", _zh_locale="zh-CN",
        _enable_prosody=False, phoneme_alphabet=lambda _language: alphabet,
    )
    monkeypatch.setattr(speech_api, "_pronunciation_provider", lambda: provider)
    calls = []

    def assess(_provider, data, file, language, reference, unscripted=False):
        calls.append((data, file.filename, language, reference, unscripted))
        return SimpleNamespace(
            provider="azure-speech",
            score_kind="measured",
            words=[SimpleNamespace(word="Say", offset_ms=100, duration_ms=250, error_type="None",
                                   phonemes=[SimpleNamespace(phoneme="s", accuracy_score=91),
                                             SimpleNamespace(phoneme="eɪ", accuracy_score=92)]),
                   SimpleNamespace(word="inserted", offset_ms=350, duration_ms=90, error_type="Insertion")],
        )

    monkeypatch.setattr(speech_api, "_assess", assess)
    first = client.post("/api/speaking/model-reference/upload-owned/owned-line", json={"reference_text": "attacker text"})
    second = client.post("/api/speaking/model-reference/upload-owned/owned-line")

    assert first.status_code == second.status_code == 200
    expected_word = {"text": "Say", "offset_ms": 100, "duration_ms": 250, "error_type": "None"}
    if expected_ipa:
        expected_word["ipa"] = expected_ipa
    assert first.json()["words"] == [expected_word]
    assert len(calls) == 1
    assert calls[0][2:] == ("en", "Say this.", False)
    assert not ({"pron_score", "accuracy_score", "fluency_score"} & set(first.json()))

    reads_before_revocation = len(assets.reads)
    visible = False
    assert client.post("/api/speaking/model-reference/upload-owned/owned-line").status_code == 404
    assert len(assets.reads) == reads_before_revocation


@pytest.mark.parametrize("lesson_status,library,processing,text,allowed", [
    ("PUBLISHED", "personal", "ready", "Say this sentence aloud.", True),
    ("NEEDS_REVIEW", "personal", "ready", "Say this sentence aloud.", True),
    ("NEEDS_REVIEW", "shared", "ready", "Say this sentence aloud.", False),
    ("NEEDS_REVIEW", "personal", "processing", "Say this sentence aloud.", False),
    ("NEEDS_REVIEW", "personal", "ready", "", False),
])
def test_youtube_reference_audio_uses_bounded_ephemeral_cache_and_rechecks_access(client, monkeypatch, tmp_path, lesson_status, library, processing, text, allowed):
    from writing_coach import media_library_api
    from writing_coach.media_library_store import MediaLibraryEntry
    from writing_coach.media_providers import youtube_audio

    entry = MediaLibraryEntry(
        media_id="youtube-abcd1234567",
        media_type="video",
        provider="youtube",
        provider_media_id="abcd1234567",
        canonical_url="https://www.youtube.com/watch?v=abcd1234567",
        playback={"provider": "youtube", "kind": "embed", "url": "https://www.youtube-nocookie.com/embed/abcd1234567"},
        title="Published clip",
        thumbnail={"kind": "none", "ref": ""},
        duration_ms=1000,
        language="en",
        level="",
        creator="",
        source={"owner": ""},
        library=library,
        created_at="2026-10-03T00:00:00+00:00",
        processing={"state": processing},
        lesson={"status": lesson_status, "payload": {
            "asset": {"source_language": "en"},
            "transcript": {"segments": [{"segment_id": "line", "start_ms": 0, "end_ms": 1000, "original_text": text}]},
        }},
    )
    assets = _MemoryAssets()
    monkeypatch.setattr(media_library_api, "find_entry", lambda _media_id: entry)
    monkeypatch.setattr(media_library_api, "_asset_store", assets)
    monkeypatch.setattr(speaking_library, "_MODEL_CACHE", tmp_path)
    monkeypatch.setattr(speaking_library.subprocess, "run", _fake_ffmpeg)
    monkeypatch.setenv("MEDIA_ASR_MAX_SECONDS", "17")
    downloads = []

    def download(url, work, *, max_seconds):
        downloads.append((url, max_seconds))
        path = Path(work) / "source.bin"
        path.write_bytes(b"bounded-youtube-audio")
        return path

    monkeypatch.setattr(youtube_audio, "download_audio", download)
    first = client.get("/api/speaking/model-audio/youtube-abcd1234567/line")
    if not allowed:
        assert first.status_code == 404
        assert downloads == [], "unusable or shared review content must be rejected before fetching"
        return
    second = client.get("/api/speaking/model-audio/youtube-abcd1234567/line")

    assert first.status_code == second.status_code == 200
    assert len(downloads) == 1
    assert downloads[0] == (entry.canonical_url, 17)
    assert list(tmp_path.glob("youtube-*.src")), "prepared source audio stays in the ephemeral model cache"
    assert assets.items == {}, "source audio must not be written to durable media storage"
    assert assets.reads == [], "source audio must not be read from durable media storage"
    import os
    import time

    cached_audio = next(tmp_path.glob("youtube-*.src"))
    expired_at = time.time() - speaking_library._YOUTUBE_SOURCE_CACHE_TTL_SECONDS - 1
    os.utime(cached_audio, (expired_at, expired_at))
    assert client.get("/api/speaking/model-audio/youtube-abcd1234567/line").status_code == 200
    assert len(downloads) == 2, "expired source audio is prepared again through the bounded resolver"
    monkeypatch.setattr(media_library_api, "find_entry", lambda _media_id: None)
    assert client.get("/api/speaking/model-audio/youtube-abcd1234567/line").status_code == 404
    assert len(downloads) == 2, "revoked access must be rejected before ephemeral cache reuse"


def test_youtube_audio_rejects_non_youtube_source_and_long_reference_line(client, monkeypatch, tmp_path):
    from dataclasses import replace

    from writing_coach import media_library_api
    from writing_coach.media_library_store import MediaLibraryEntry
    from writing_coach.media_providers import youtube_audio

    entry = MediaLibraryEntry(
        media_id="youtube-abcd1234567",
        media_type="video",
        provider="youtube",
        provider_media_id="abcd1234567",
        canonical_url="https://attacker.example/watch?v=abcd1234567",
        playback={"provider": "youtube", "kind": "video", "url": "https://www.youtube.com/embed/abcd1234567"},
        title="Published clip",
        thumbnail={"kind": "none", "ref": ""},
        duration_ms=40000,
        language="en",
        level="",
        creator="",
        source={"owner": ""},
        library="shared",
        created_at="2026-10-03T00:00:00+00:00",
        lesson={"status": "PUBLISHED", "payload": {
            "asset": {"source_language": "en"},
            "transcript": {"segments": [{"segment_id": "line", "start_ms": 0, "end_ms": 1000, "original_text": "Say this."}]},
        }},
    )
    monkeypatch.setattr(media_library_api, "find_entry", lambda _media_id: entry)
    monkeypatch.setattr(media_library_api, "_asset_store", _MemoryAssets())
    monkeypatch.setattr(speaking_library, "_MODEL_CACHE", tmp_path)
    monkeypatch.setattr(youtube_audio, "download_audio", lambda *_args, **_kwargs: pytest.fail("arbitrary URL fetched"))

    response = client.post("/api/speaking/model-reference/youtube-abcd1234567/line")
    assert response.status_code == 200
    assert response.json()["model_audio_available"] is False

    long_entry = replace(entry, canonical_url="https://www.youtube.com/watch?v=abcd1234567", lesson={
        "status": "PUBLISHED", "payload": {
            "asset": {"source_language": "en"},
            "transcript": {"segments": [{"segment_id": "line", "start_ms": 0, "end_ms": 31_000, "original_text": "Say this."}]},
        },
    })
    monkeypatch.setattr(media_library_api, "find_entry", lambda _media_id: long_entry)
    long_response = client.post("/api/speaking/model-reference/youtube-abcd1234567/line")
    assert long_response.status_code == 422


def test_model_reference_never_uses_the_demo_pronunciation_provider(client, monkeypatch):
    from types import SimpleNamespace

    from writing_coach import speech_api

    line = speaking_library._ResolvedModelLine(
        lesson=None,
        entry=object(),
        segment_id="line",
        language="en",
        reference_text="Say this.",
        start_ms=0,
        end_ms=1000,
        canonical_words=(),
        source_identity="stored:demo-check",
        source_locator="stored:demo-check",
    )
    monkeypatch.setattr(speaking_library, "_resolve_model_line", lambda *_args: line)
    monkeypatch.setattr(speaking_library, "_line_source_file", lambda *_args: None)
    monkeypatch.setattr(speaking_library, "_cut_model_line", lambda *_args: b"source-line-audio")
    monkeypatch.setattr(speech_api, "_pronunciation_provider", lambda: SimpleNamespace(provider_id="demo-synthetic"))
    monkeypatch.setattr(speech_api, "_assess", lambda *_args: pytest.fail("demo assessment must not run"))

    response = client.post("/api/speaking/model-reference/demo/line")

    assert response.status_code == 503


@pytest.mark.parametrize("word", [
    {"text": "Say", "start_ms": True, "end_ms": 500},
    {"text": "Say", "start_ms": 100.0, "end_ms": 500},
    {"text": "Say", "start_ms": 100},
])
def test_canonical_reference_timings_reject_coercion_and_missing_bounds(word):
    line = speaking_library._ResolvedModelLine(
        lesson=None,
        entry=None,
        segment_id="line",
        language="en",
        reference_text="Say",
        start_ms=0,
        end_ms=1000,
        canonical_words=(word,),
        source_identity="stored:strict-timing",
        source_locator="stored:strict-timing",
    )

    assert speaking_library._canonical_word_timings(line) == []


def test_canonical_reference_timings_reject_overlapping_words():
    line = speaking_library._ResolvedModelLine(
        lesson=None,
        entry=None,
        segment_id="line",
        language="en",
        reference_text="Say this",
        start_ms=0,
        end_ms=1000,
        canonical_words=(
            {"text": "Say", "start_ms": 100, "end_ms": 500},
            {"text": "this", "start_ms": 450, "end_ms": 700},
        ),
        source_identity="stored:overlapping-timing",
        source_locator="stored:overlapping-timing",
    )

    assert speaking_library._canonical_word_timings(line) == []
