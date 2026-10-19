"""D-244, amended 2026-10-20 (#418): for YouTube Orena uses only the captions the channel provides.

* Model clips: a YouTube item is never cut, so its audio is never downloaded. It is skipped with
  `youtube_no_audio_download (D-244)`, in the backfill report and in the admin outcome, never as an error.
  Uploads are cut exactly as before.
* Supadata: `mode=generate` (or `auto`, which may generate) is never requested for a YouTube URL, by any caller.
  A YouTube video whose channel has no captions ends as `youtube_no_channel_captions`, which the learner's
  Import sheet says in its existing error slot, in English, Vietnamese and Chinese.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import pytest

from test_media_fallback import FakeClient, InlineExecutor, base_acquisition, completed_transcript
from test_model_clips import MemoryAssets, _entry, _Store

from writing_coach import admin_content, model_clips
from writing_coach.media_fallback import SupadataMediaFallbackService
from writing_coach.media_ingestion import MediaAcquisition
from writing_coach.media_providers.supadata import (
    SupadataTranscriptClient,
    SupadataTranscriptNotFound,
    SupadataYouTubeGenerationRefused,
    is_youtube_url,
)
from writing_coach.media_providers.youtube import YouTubeMediaProviderAdapter
from writing_coach.media_transcript_pipeline import MediaPipeline

ROOT = Path(__file__).resolve().parents[1]
YOUTUBE_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def _youtube_entry(**overrides):
    return _entry(
        media_id="yt-item", media_type="video", provider="youtube", provider_media_id="dQw4w9WgXcQ",
        canonical_url=YOUTUBE_URL, library="shared", source={"rights": "cleared"},
        playback={"provider": "youtube", "kind": "embed", "url": "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"},
        **overrides,
    )


@pytest.fixture
def cuts(monkeypatch):
    calls: list[tuple[str, int]] = []

    def fake_cut(source, line):
        calls.append((line.segment_id, line.start_ms))
        return b"clip:" + line.segment_id.encode()

    monkeypatch.setattr(model_clips, "cut_clip", fake_cut)
    return calls


# ---- model clips -------------------------------------------------------------------------------------------------

def test_the_backfill_skips_youtube_and_never_calls_the_downloader(cuts, monkeypatch):
    from writing_coach.media_providers import youtube_audio
    from writing_coach.model_clip_backfill import backfill

    def forbidden(*_args, **_kwargs):
        raise AssertionError("YouTube audio must never be downloaded for a model clip (D-244)")

    monkeypatch.setattr(youtube_audio, "download_audio", forbidden)
    sources: list[str] = []

    def entry_source(entry, work, **_kwargs):
        sources.append(entry.media_id)
        return Path("source")

    store = _Store([_youtube_entry(), _entry()])
    for dry_run in (True, False):
        report = backfill(store, MemoryAssets(), include_catalog=False, entry_source=entry_source, dry_run=dry_run)
        youtube = next(item for item in report["items"] if item["id"] == "yt-item")
        assert youtube["skipped"] == "youtube_no_audio_download"
        assert youtube["note"] == "youtube_no_audio_download (D-244)"
        assert youtube["prepared"] == 0 and youtube["failed"] == 0
        assert report["skipped"] == 1 and report["failed"] == 0
        assert report["missing"] == 2, "only the upload's two speakable lines are missing"
    assert sources == ["upload-owned"], "the YouTube item never reached a source acquisition"
    assert [segment for segment, _ in cuts] == ["a", "b"], "the upload is cut as before"


def test_the_default_entry_source_never_downloads_youtube(monkeypatch, tmp_path):
    from writing_coach.media_providers import youtube_audio
    from writing_coach.model_clip_backfill import _entry_source

    monkeypatch.setattr(youtube_audio, "download_audio", lambda *_a, **_k: pytest.fail("downloader called"))
    assert _entry_source(_youtube_entry(), tmp_path, max_seconds=60) is None


def test_readiness_skips_youtube_clips_without_downloading(cuts, caplog):
    pipeline = MediaPipeline(ledger=object(), workers=1)
    downloads: list[str] = []
    pipeline._youtube_audio = lambda url, *_a, **_k: downloads.append(url) or Path("never")

    with caplog.at_level(logging.INFO):
        skipped = pipeline._prepare_model_clips(MemoryAssets(), _youtube_entry())
    assert skipped == "youtube_no_audio_download"
    assert downloads == [] and cuts == []
    assert "could not be prepared" not in caplog.text, "a skip is not an error"
    assert "youtube_no_audio_download (D-244)" in caplog.text


def test_readiness_still_cuts_an_upload(cuts):
    assets = MemoryAssets({"media/owned/original.wav": b"source"})
    assert MediaPipeline(ledger=object(), workers=1)._prepare_model_clips(assets, _entry()) is None
    assert [segment for segment, _ in cuts] == ["a", "b"]


def test_the_admin_outcome_reports_the_skip_not_an_error():
    entry = _youtube_entry(processing={"state": "ready", "model_clips_skipped": "youtube_no_audio_download"})
    outcome = admin_content.media_outcome(entry)
    assert outcome["state"] == "ready" and outcome["reason"] == ""
    assert outcome["model_clips_skipped"] == "youtube_no_audio_download"
    assert admin_content.media_outcome(_entry(processing={"state": "ready"}))["model_clips_skipped"] == ""


# ---- Supadata ----------------------------------------------------------------------------------------------------

class _Response:
    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


class _Session:
    def __init__(self, *responses: _Response) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, **kwargs: Any) -> _Response:
        self.calls.append({"url": url, **kwargs})
        return self.responses.pop(0)


def _transcript_payload() -> dict[str, Any]:
    return {"lang": "en", "content": [{"text": "Hello", "offset": 0, "duration": 900, "lang": "en"}]}


@pytest.mark.parametrize("url", [
    YOUTUBE_URL, "https://youtu.be/dQw4w9WgXcQ", "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://music.youtube.com/watch?v=dQw4w9WgXcQ", "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ",
])
@pytest.mark.parametrize("mode", ["generate", "auto"])
def test_the_client_never_sends_generate_or_auto_for_youtube(url, mode):
    session = _Session(_Response(200, _transcript_payload()))
    client = SupadataTranscriptClient("k", session=session)  # type: ignore[arg-type]
    for call in (client.start, client.fetch):
        with pytest.raises(SupadataYouTubeGenerationRefused):
            call(url, "en", mode=mode)
    assert session.calls == [], "refused before any request"


def test_the_client_asks_youtube_in_native_mode_by_default():
    session = _Session(_Response(200, _transcript_payload()), _Response(200, _transcript_payload()))
    client = SupadataTranscriptClient("k", session=session)  # type: ignore[arg-type]
    client.start(YOUTUBE_URL, "en")
    client.fetch(YOUTUBE_URL, "en")
    assert [call["params"]["mode"] for call in session.calls] == ["native", "native"]


def test_youtube_detection_is_by_host():
    assert is_youtube_url(YOUTUBE_URL) and is_youtube_url("https://YouTu.be/x")
    assert not is_youtube_url("https://example.org/youtube.com/watch") and not is_youtube_url("not a url")


def test_the_fallback_service_asks_youtube_for_native_captions_only():
    client = FakeClient(completed_transcript())
    service = SupadataMediaFallbackService(client, executor=InlineExecutor())  # type: ignore[arg-type]
    service.start(base_acquisition(), owner_key="learner-a", learning_language="en", target_language="vi")
    assert [mode for _url, _lang, mode in client.start_calls] == ["native"]


@pytest.mark.parametrize("answer", [None, SupadataTranscriptNotFound()])
def test_a_youtube_video_without_channel_captions_is_refused_with_the_stable_reason(answer):
    class Client(FakeClient):
        def start(self, source_url, preferred_language, *, mode):
            self.start_calls.append((source_url, preferred_language, mode))
            if isinstance(answer, Exception):
                raise answer
            return answer

    client = Client(None)
    service = SupadataMediaFallbackService(client, executor=InlineExecutor())  # type: ignore[arg-type]
    started = service.start(base_acquisition(), owner_key="learner-a", learning_language="en", target_language="vi")
    status = service.poll(started.job_id, owner_key="learner-a", learning_language="en")
    assert status.status == "failed" and status.failure_kind == "youtube_no_channel_captions"
    assert [mode for *_rest, mode in client.start_calls] == ["native"]


def test_the_real_client_behind_the_service_sends_native_for_youtube():
    session = _Session(_Response(404, {}))
    service = SupadataMediaFallbackService(
        SupadataTranscriptClient("k", session=session), executor=InlineExecutor(),  # type: ignore[arg-type]
    )
    started = service.start(base_acquisition(), owner_key="learner-a", learning_language="en", target_language="vi")
    assert [call["params"]["mode"] for call in session.calls] == ["native"]
    assert service.poll(started.job_id, owner_key="learner-a", learning_language="en").failure_kind == (
        "youtube_no_channel_captions"
    )


def test_a_non_youtube_source_keeps_its_fallback_unchanged():
    from dataclasses import replace as dc_replace

    acquisition = base_acquisition()
    asset = dc_replace(acquisition.media_object.asset, asset_id="upload:x", source_url="https://example.org/a.mp3",
                       source_provider="example")
    other = MediaAcquisition(media_object=dc_replace(acquisition.media_object, asset=asset), playback=acquisition.playback)
    client = FakeClient(None)
    service = SupadataMediaFallbackService(client, executor=InlineExecutor())  # type: ignore[arg-type]
    started = service.start(other, owner_key="learner-a", learning_language="en", target_language="vi")
    assert [mode for *_rest, mode in client.start_calls] == ["generate"]
    assert service.poll(started.job_id, owner_key="learner-a", learning_language="en").failure_kind == "transcript_unavailable"


def test_the_youtube_adapter_inline_fallback_asks_native_only():
    class Metadata:
        def fetch_title(self, _url):
            return "Lesson"

    class NoCaptions:
        def fetch_track(self, _video_id, _language):
            return None

    class Fallback:
        def __init__(self):
            self.modes: list[str] = []

        def fetch(self, _url, _language, *, mode):
            self.modes.append(mode)
            return None

    fallback = Fallback()
    adapter = YouTubeMediaProviderAdapter(Metadata(), NoCaptions(), fallback,  # type: ignore[arg-type]
                                          enable_fallback=True, defer_transcript_recovery=True)
    acquisition = adapter.acquire(YOUTUBE_URL, "en")
    assert acquisition.media_object.transcript is None
    assert fallback.modes == ["native"]


def test_no_production_code_requests_generate_for_youtube():
    """The one remaining `generate` is the fallback service's non-YouTube branch."""
    hits = []
    for path in (ROOT / "writing_coach").rglob("*.py"):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"mode\s*=\s*\"(generate|auto)\"", line):
                hits.append(f"{path.relative_to(ROOT).as_posix()}:{number}")
    assert all(hit.startswith("writing_coach/media_fallback.py:") for hit in hits), hits
    assert len(hits) <= 1, hits


# ---- the learner's words -----------------------------------------------------------------------------------------

def test_the_learner_refusal_exists_in_three_languages_in_the_existing_error_slot():
    copy = (ROOT / "static/orena/screens/import/copy.js").read_text(encoding="utf-8")
    model = (ROOT / "static/orena/screens/import/model.js").read_text(encoding="utf-8")
    assert "'youtube_no_channel_captions'" in model, "importErrorKey maps the category to its copy key"
    assert "'error_youtube_no_channel_captions'" in copy, "declared as support copy"
    lines = re.findall(r"^\s*error_youtube_no_channel_captions: '([^']+)',", copy, flags=re.M)
    assert len(lines) == 3, "English, Vietnamese and Chinese"
    english, vietnamese, chinese = lines
    assert "YouTube" in english and "captions" in english
    assert "phụ đề" in vietnamese
    assert "字幕" in chinese
