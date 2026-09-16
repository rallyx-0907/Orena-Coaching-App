"""Local media inspection and truthful thumbnail extraction helpers."""
from __future__ import annotations

import json
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from urllib.parse import urlsplit

from writing_coach.listening_catalog import REVIEWED_POSTER_HOSTS


@dataclass(frozen=True)
class MediaProbe:
    duration_ms: int
    media_type: str
    width: int | None
    height: int | None
    has_video: bool
    has_audio: bool


# Kept in one place: `listening_catalog.REVIEWED_POSTER_HOSTS` is the boundary
# the curated catalog already validates posters against, and a second copy here
# would be a second policy for the same question.
_TIMEOUT_SECONDS = 20
MAX_UPLOAD_BYTES = 64 * 1024 * 1024
_TEMP_ROOT = Path(__file__).resolve().parents[1] / "data" / "media_temp"


@dataclass(frozen=True)
class TempFileHandle:
    """One caller-owned temporary media path."""

    path: Path


@contextmanager
def TempMediaFile(*, suffix: str = ".bin") -> Iterator[TempFileHandle]:
    """Yield a temporary path under the workspace temp root, always cleaned up.

    Media arrives as bytes that must be probed with ffprobe, which needs a real
    file. The path is always inside `data/media_temp`, so a failed import leaves
    at most one unloved file in a directory this codebase already owns, and the
    file is removed on the way out whichever way the caller leaves.
    """
    _TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    safe_suffix = suffix if suffix.startswith(".") and len(suffix) <= 8 and suffix[1:].isalnum() else ".bin"
    path = _TEMP_ROOT / f"media-{uuid.uuid4().hex}{safe_suffix.casefold()}"
    try:
        yield TempFileHandle(path)
    finally:
        path.unlink(missing_ok=True)


def _run(args: list[str], *, timeout: int = _TIMEOUT_SECONDS) -> subprocess.CompletedProcess[bytes] | None:
    try:
        return subprocess.run(args, capture_output=True, check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None


def probe_media(path: Path) -> MediaProbe:
    """Read media facts only; ffprobe is the authority over file extensions."""
    result = _run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)])
    if result is None or result.returncode != 0:
        raise ValueError("The media file could not be read.")
    try:
        payload = json.loads(result.stdout)
        streams = payload.get("streams", [])
        video = next((item for item in streams if item.get("codec_type") == "video"), None)
        audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
        duration = float(payload.get("format", {}).get("duration") or 0)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("The media file could not be read.") from exc
    if not video and not audio:
        raise ValueError("The file is not audio or video media.")
    return MediaProbe(
        duration_ms=max(0, round(duration * 1000)),
        media_type="video" if video else "audio",
        width=int(video["width"]) if video and str(video.get("width", "")).isdigit() else None,
        height=int(video["height"]) if video and str(video.get("height", "")).isdigit() else None,
        has_video=video is not None,
        has_audio=audio is not None,
    )


def _luma_is_usable(path: Path) -> bool:
    result = _run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-frames:v", "1", "-vf", "scale=32:18", "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"])
    if result is None or result.returncode != 0 or not result.stdout:
        return False
    return sum(result.stdout) / len(result.stdout) >= 12


def video_frame_thumbnail(path: Path, *, duration_ms: int, width: int = 640) -> bytes:
    """Return a non-blank JPEG frame, never a synthetic substitute."""
    if width <= 0:
        raise ValueError("width must be positive")
    duration = max(1, duration_ms) / 1000
    candidates = (0.08, 0.2, 0.45, 0.7, 0.9)
    _TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="orena-media-thumb-", dir=_TEMP_ROOT) as temporary:
        root = Path(temporary)
        for fraction in candidates:
            frame = root / f"frame-{fraction}.jpg"
            at = max(0.05, min(duration * fraction, max(0.05, duration - 0.05)))
            result = _run([
                "ffmpeg", "-nostdin", "-v", "error", "-ss", f"{at:.3f}", "-i", str(path),
                "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "3", "-f", "image2", "-y", str(frame),
            ])
            if result is not None and result.returncode == 0 and frame.is_file() and _luma_is_usable(frame):
                return frame.read_bytes()
    return b""


def embedded_audio_artwork(path: Path) -> bytes | None:
    """Extract embedded artwork if present; an audio item gets no invented art."""
    _TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="orena-media-art-", dir=_TEMP_ROOT) as temporary:
        cover = Path(temporary) / "cover.jpg"
        result = _run([
            "ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-an", "-c:v", "copy", "-frames:v", "1", "-y", str(cover),
        ])
        if result is None or result.returncode != 0 or not cover.is_file():
            return None
        return cover.read_bytes()


def provider_poster_url(provider: str, provider_media_id: str, advertised: str = "") -> str:
    """Accept only reviewed poster hosts, with a deterministic YouTube fallback."""
    hosts = REVIEWED_POSTER_HOSTS.get(provider, frozenset())
    try:
        parsed = urlsplit(advertised)
        if (
            advertised
            and parsed.scheme == "https"
            and not parsed.username
            and not parsed.password
            and (parsed.hostname or "").casefold() in hosts
        ):
            return advertised
    except ValueError:
        pass
    if provider == "youtube" and provider_media_id:
        return f"https://i.ytimg.com/vi/{provider_media_id}/hqdefault.jpg"
    return ""
