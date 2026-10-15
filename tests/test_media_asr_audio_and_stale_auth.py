"""The ASR audio download is ranged and bounded, and a stale refusal does not outlive its retry (D-217, PROPOSED).

Evidence (2026-10-15, :8021, Supadata trial):

* `youtube-D_IcGTgWoZY` (no captions) never reached Groq ASR. Inside the worker, `yt-dlp` fetched the audio in 3 s, but the
  app's own `download_bounded` on the same resolved googlevideo URL moved 1 MiB per 33 s (about 31 KiB/s, 6.5 MB in total):
  a plain GET without `Range` is throttled by googlevideo, while the same URL answered a `Range: bytes=0-1048575` request
  with 206 and 1 MiB in 0.8 s. The read loop had no wall-clock bound, so the 12 s socket timeout never tripped.
* `youtube-RhaepLsP5eg` showed `provider_auth` on the item the moment a translate-only retry was queued: the retry kept the
  previous run's `translation`/`translation_reason`, so an old refusal (Groq 403 while the machine VPN was on) read as the
  result of the retry; the retry itself translated all 48 lines at 12:16:44. A 401/403 was also the one refusal whose status
  and sentence never reached the log.

Providers, sockets and the downloader here are fakes; nothing reaches a network."""
from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

import pytest

from tests.test_media_caption_path import Ingestion, _translation_world, _world
from tests.test_media_translation_groq import FakeResponse, install, segments
from writing_coach import media_safe_fetch
from writing_coach import media_translation as mt
from writing_coach.media_providers import youtube_audio
from writing_coach.media_safe_fetch import UnsafeMediaFetch, download_bounded


class _Body:
    def __init__(self, data: bytes) -> None:
        self._data, self._at = data, 0

    def read(self, size=-1):
        piece = self._data[self._at:] if size is None or size < 0 else self._data[self._at:self._at + size]
        self._at += len(piece)
        return piece

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Reply(_Body):
    def __init__(self, status: int, data: bytes, headers: dict[str, str]) -> None:
        super().__init__(data)
        self.status = status
        self.headers = headers


class _Server:
    """A host that serves `data`, honours `Range` unless `ignore_range`, and records each request's headers."""

    def __init__(self, data: bytes, *, ignore_range: bool = False) -> None:
        self.data, self.ignore_range, self.requests = data, ignore_range, []

    def __call__(self, url, *, headers=None, **_kwargs):
        headers = dict(headers or {})
        self.requests.append(headers)
        spec = headers.get("Range")
        if spec is None or self.ignore_range:
            return _Reply(200, self.data, {"Content-Length": str(len(self.data))})
        first, last = (int(part) for part in spec.removeprefix("bytes=").split("-"))
        last = min(last, len(self.data) - 1)
        return _Reply(206, self.data[first:last + 1], {"Content-Range": f"bytes {first}-{last}/{len(self.data)}"})


def _download(tmp_path: Path, monkeypatch, server: _Server, **kwargs) -> tuple[int, Path]:
    monkeypatch.setattr(media_safe_fetch, "_open", server)
    destination = tmp_path / "audio" / "source.bin"
    return download_bounded("https://media.example/a.m4a", destination, **kwargs), destination


# -- 1. the download is taken in ranged pieces ----------------------------------------------------------------------


def test_a_ranged_download_asks_for_the_file_in_pieces_and_joins_them(tmp_path, monkeypatch):
    data = bytes(range(256)) * 4 + b"tail"  # 1028 bytes
    server = _Server(data)
    written, destination = _download(tmp_path, monkeypatch, server, range_chunk_bytes=400)
    assert written == len(data) and destination.read_bytes() == data
    assert [request["Range"] for request in server.requests] == ["bytes=0-399", "bytes=400-799", "bytes=800-1199"]


def test_a_host_that_ignores_range_is_still_read_whole_within_the_budget(tmp_path, monkeypatch):
    data = b"x" * 900
    server = _Server(data, ignore_range=True)
    written, destination = _download(tmp_path, monkeypatch, server, range_chunk_bytes=400)
    assert written == 900 and destination.read_bytes() == data and len(server.requests) == 1


def test_a_file_whose_length_exceeds_the_cap_is_refused_before_it_is_read(tmp_path, monkeypatch):
    server = _Server(b"x" * 5000)
    with pytest.raises(UnsafeMediaFetch) as raised:
        _download(tmp_path, monkeypatch, server, range_chunk_bytes=400, max_bytes=1000)
    assert raised.value.too_large is True
    assert len(server.requests) == 1 and not (tmp_path / "audio" / "source.bin").exists()


def test_a_host_that_ignores_range_cannot_exceed_the_cap(tmp_path, monkeypatch):
    server = _Server(b"x" * 5000, ignore_range=True)
    with pytest.raises(UnsafeMediaFetch) as raised:
        _download(tmp_path, monkeypatch, server, range_chunk_bytes=400, max_bytes=1000)
    assert raised.value.too_large is True and not (tmp_path / "audio" / "source.bin").exists()


def test_a_download_that_drips_is_stopped_by_the_wall_clock_not_the_socket(tmp_path, monkeypatch):
    now = [0.0]

    class _Slow(_Body):
        status, headers = 200, {}

        def read(self, size=-1):
            now[0] += 10.0  # each read "returns" within the socket timeout, ten seconds later
            return b"x"

    monkeypatch.setattr(media_safe_fetch.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(media_safe_fetch, "_open", lambda url, **kwargs: _Slow(b""))
    with pytest.raises(UnsafeMediaFetch):
        download_bounded("https://media.example/a.m4a", tmp_path / "s.bin", range_chunk_bytes=400, total_timeout=30)
    assert not (tmp_path / "s.bin").exists()


def test_a_ranged_download_checks_every_piece_through_the_same_boundary(tmp_path, monkeypatch):
    seen = []

    def refuse(url, **kwargs):
        seen.append((url, kwargs.get("allowed_hosts"), kwargs.get("max_redirects")))
        raise UnsafeMediaFetch("This media address is not allowed.")

    monkeypatch.setattr(media_safe_fetch, "_open", refuse)
    with pytest.raises(UnsafeMediaFetch):
        download_bounded("https://media.example/a.m4a", tmp_path / "s.bin", range_chunk_bytes=400, max_redirects=1)
    assert seen == [("https://media.example/a.m4a", None, 1)]


# -- 2. the YouTube path uses it, with the same caps -----------------------------------------------------------------


class _Ydl:
    def __init__(self, info):
        self.info = info

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download=False):
        if isinstance(self.info, Exception):
            raise self.info
        return self.info


def test_the_audio_download_is_ranged_and_keeps_the_size_cap(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(youtube_audio, "YoutubeDL", lambda options: _Ydl({"duration": 400}))
    monkeypatch.setattr(youtube_audio.YtDlpYouTubeAudioUrlResolver, "resolve",
                        lambda self, url: type("A", (), {"url": "https://rr1.googlevideo.com/videoplayback?x=1"})())

    def fake_download(url, destination, **kwargs):
        calls.append((url, kwargs))
        return 0

    monkeypatch.setattr(media_safe_fetch, "download_bounded", fake_download)
    result = youtube_audio.download_audio("https://www.youtube.com/watch?v=D_IcGTgWoZY", tmp_path, max_seconds=3600)
    assert result == tmp_path / "source.bin"
    (url, kwargs), = calls
    assert url.startswith("https://rr1.googlevideo.com/")
    assert kwargs["range_chunk_bytes"] and kwargs.get("max_bytes", media_safe_fetch.MAX_MEDIA_BYTES) == media_safe_fetch.MAX_MEDIA_BYTES
    assert 0 < kwargs["total_timeout"] <= 600


def test_a_metadata_failure_in_the_audio_path_is_logged_with_its_class_and_still_unavailable(tmp_path, monkeypatch, caplog):
    from writing_coach.media_transcript_pipeline import PipelineStop

    monkeypatch.setattr(youtube_audio, "YoutubeDL", lambda options: _Ydl(OSError("Sign in to confirm you're not a bot")))
    with caplog.at_level(logging.WARNING):
        with pytest.raises(PipelineStop) as stop:
            youtube_audio.download_audio("https://www.youtube.com/watch?v=D_IcGTgWoZY", tmp_path, max_seconds=3600)
    assert stop.value.code == "audio_unavailable"
    text = " ".join(record.getMessage() for record in caplog.records)
    assert "OSError" in text and "not a bot" in text


# -- 3. a stale refusal does not outlive its retry -------------------------------------------------------------------


class _Recorder:
    def __init__(self):
        self.jobs = []

    def submit(self, fn, *args):
        self.jobs.append((fn, args))


def test_queueing_a_translate_only_retry_clears_the_previous_runs_refusal(tmp_path, monkeypatch):
    monkeypatch.delenv("MEDIA_PIPELINE_INLINE", raising=False)
    store, before, pipeline, _asked = _translation_world(tmp_path, cached=3)
    store.update_if_present(before.media_id, lambda e: replace(e, processing={
        **e.processing, "translation": "failed", "translation_reason": "provider_auth", "translation_retry_after": 12.0}))
    pipeline._pool = _Recorder()
    assert pipeline.retry_translation(store, before.media_id) == "queued"
    processing = store.get(before.media_id).processing
    assert processing["translation_reason"] == "" and processing["translation"] == "" and processing["translation_retry_after"] == 0
    assert processing["translation_counts"] == before.processing["translation_counts"], "lines already done stay counted"
    assert len(pipeline._pool.jobs) == 1


def test_a_retry_that_ends_in_a_real_refusal_still_records_it(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_PIPELINE_INLINE", "1")
    monkeypatch.setenv("MEDIA_PRETRANSLATE_LANGUAGES", "vi")
    from types import SimpleNamespace

    def meanings(entry, target):
        return SimpleNamespace(status="partial", meanings=[], provider_calls=1, reason="provider_auth", retry_after=0.0)

    store, before, pipeline = _world(tmp_path, ingestion=Ingestion(), meanings=meanings)
    assert pipeline.retry_translation(store, before.media_id) == "queued"
    processing = store.get(before.media_id).processing
    assert processing["translation"] in {"failed", "partial"}
    assert processing["translation_reason"] == "provider_auth"


@pytest.mark.parametrize("status", [401, 403])
def test_an_auth_refusal_is_logged_with_its_status_and_no_credential(monkeypatch, caplog, status):
    install(monkeypatch, FakeResponse({"error": {"message": "Access denied. Please check your network settings."}},
                                      status=status, headers={"authorization": "Bearer secret-value"}))
    with caplog.at_level(logging.WARNING, logger="writing_coach.media_translation"):
        with pytest.raises(mt.TranslationProviderError) as raised:
            mt.GroqTranslationProvider("secret-key", model="m").translate_batch("en", "vi", segments("One."))
    assert raised.value.reason == "provider_auth"
    text = " ".join(record.getMessage() for record in caplog.records)
    assert f"status={status}" in text and "Access denied" in text
    assert "secret" not in text
