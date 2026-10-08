"""Short-lived YouTube audio URL resolution for media timing enrichment."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from writing_coach.media_providers.youtube import recognizes_youtube_url
from writing_coach.media_timing import (
    MediaAudioResolutionFailed,
    MediaAudioSource,
)


def download_audio(source_url, work, *, max_seconds):
    """Download one bounded provider audio file through the existing resolver."""
    from pathlib import Path
    from writing_coach.media_safe_fetch import download_bounded
    from writing_coach.media_transcript_pipeline import PipelineStop
    if not recognizes_youtube_url(source_url):
        raise PipelineStop("audio_unavailable")
    options = {
        "quiet": True, "no_warnings": True, "skip_download": True,
        "noplaylist": True, "socket_timeout": 15, "js_runtimes": {"node": {}},
    }
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(source_url, download=False)
    duration = info.get("duration") if isinstance(info, dict) else None
    if not isinstance(duration, (int, float)) or duration <= 0:
        raise PipelineStop("audio_unavailable")
    if duration > max_seconds:
        raise PipelineStop("too_long")
    audio = YtDlpYouTubeAudioUrlResolver().resolve(source_url)
    destination = Path(work) / "source.bin"
    download_bounded(audio.url, destination)
    return destination


class YtDlpYouTubeAudioUrlResolver:
    """YouTube resolver with truthful segment-level timing degradation."""

    provider_id = "youtube"
    delivery_mode = "segment_only"

    def __init__(
        self,
        *,
        timeout_seconds: float = 15.0,
        ydl_factory: Callable[[dict[str, Any]], Any] = YoutubeDL,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("YouTube audio resolver timeout must be positive.")
        self._timeout_seconds = float(timeout_seconds)
        self._ydl_factory = ydl_factory

    def resolve(self, source_url: str) -> MediaAudioSource:
        if not recognizes_youtube_url(source_url):
            raise MediaAudioResolutionFailed()

        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            "socket_timeout": self._timeout_seconds,
            "js_runtimes": {"node": {}},
            # Groq accepts direct m4a/webm media URLs. Do not select HLS/DASH
            # manifests because those are not audio-file URLs.
            "format": (
                "bestaudio[protocol^=http][ext=m4a]/"
                "bestaudio[protocol^=http][ext=webm]/"
                "bestaudio[protocol^=http]"
            ),
        }
        try:
            with self._ydl_factory(options) as ydl:
                info = ydl.extract_info(source_url, download=False)
        except (DownloadError, OSError, ValueError) as exc:
            raise MediaAudioResolutionFailed() from exc

        if not isinstance(info, dict) or info.get("_type") == "playlist":
            raise MediaAudioResolutionFailed()

        candidate = info
        requested = info.get("requested_downloads")
        if isinstance(requested, list) and requested and isinstance(requested[0], dict):
            candidate = requested[0]

        audio_url = candidate.get("url") or info.get("url")
        if not isinstance(audio_url, str) or not audio_url.strip():
            raise MediaAudioResolutionFailed()
        audio_url = audio_url.strip()
        try:
            parsed = urlsplit(audio_url)
            hostname = parsed.hostname
        except ValueError as exc:
            raise MediaAudioResolutionFailed() from exc
        if (
            parsed.scheme != "https"
            or not hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise MediaAudioResolutionFailed()

        format_id = str(candidate.get("format_id") or info.get("format_id") or "")
        return MediaAudioSource(
            url=audio_url,
            provider=self.provider_id,
            format_id=format_id[:80],
        )
