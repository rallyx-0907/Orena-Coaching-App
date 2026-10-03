from __future__ import annotations

from typing import Any

import pytest

from writing_coach.media_providers.youtube_audio import (
    YtDlpYouTubeAudioUrlResolver,
)
from writing_coach.media_timing import MediaAudioResolutionFailed


class FakeYdl:
    def __init__(self, options: dict[str, Any], info: dict[str, Any]) -> None:
        self.options = options
        self.info = info
        self.calls: list[tuple[str, bool]] = []

    def __enter__(self) -> FakeYdl:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def extract_info(self, source_url: str, *, download: bool) -> dict[str, Any]:
        self.calls.append((source_url, download))
        return self.info


def test_resolver_returns_https_audio_without_downloading_media() -> None:
    captured: dict[str, Any] = {}

    def factory(options: dict[str, Any]) -> FakeYdl:
        captured["options"] = options
        fake = FakeYdl(
            options,
            {
                "id": "dQw4w9WgXcQ",
                "url": "https://audio.googlevideo.example.test/videoplayback?sig=signed",
                "format_id": "140",
                "ext": "m4a",
            },
        )
        captured["ydl"] = fake
        return fake

    resolver = YtDlpYouTubeAudioUrlResolver(ydl_factory=factory)
    result = resolver.resolve("https://youtu.be/dQw4w9WgXcQ")

    assert result.provider == "youtube"
    assert result.format_id == "140"
    assert result.url.startswith("https://audio.googlevideo.example.test/")
    assert captured["options"]["skip_download"] is True
    assert captured["options"]["noplaylist"] is True
    assert captured["options"]["js_runtimes"] == {"node": {}}
    assert captured["ydl"].calls == [
        ("https://youtu.be/dQw4w9WgXcQ", False)
    ]


@pytest.mark.parametrize(
    "source_url",
    (
        "https://example.test/video",
        "not-a-url",
    ),
)
def test_resolver_rejects_non_youtube_sources(source_url: str) -> None:
    resolver = YtDlpYouTubeAudioUrlResolver(
        ydl_factory=lambda _options: pytest.fail("yt-dlp must not run")
    )
    with pytest.raises(MediaAudioResolutionFailed):
        resolver.resolve(source_url)


def test_resolver_rejects_non_https_resolved_media() -> None:
    def factory(options: dict[str, Any]) -> FakeYdl:
        return FakeYdl(
            options,
            {
                "url": "http://media.example.test/audio.m4a",
                "format_id": "140",
            },
        )

    resolver = YtDlpYouTubeAudioUrlResolver(ydl_factory=factory)
    with pytest.raises(MediaAudioResolutionFailed):
        resolver.resolve("https://youtu.be/dQw4w9WgXcQ")

def test_youtube_timing_transport_is_explicitly_segment_only() -> None:
    resolver = YtDlpYouTubeAudioUrlResolver(
        ydl_factory=lambda _options: pytest.fail("must not contact yt-dlp")
    )
    assert resolver.delivery_mode == "segment_only"
