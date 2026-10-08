"""Prepared model clips: one line of an admitted source, cut once and stored (D-140, within D-121).

Compare measures the model's pitch and word timing in the browser, which needs the model's audio as a
file. D-121 forbids cutting, fetching or preparing a source on navigation, so the clip is a source
artifact: it is cut at content readiness (or by the explicit backfill), stored in the existing media
asset store, and only ever *read* afterwards. A read of a clip that was not prepared is a miss, never
a reason to prepare it.

Identity is the content + its source revision + kind + language + codec configuration: the source
identity and locator (which carry the stored asset key or the catalogue URL), the segment id, the
line bounds, the language and the encoding. Anything that changes the audio changes the key, so a
changed revision is prepared again and the old key is simply never read.

No provider is called here. No schema is involved: the asset store is the owner.
"""
from __future__ import annotations

import hashlib
import logging
import subprocess
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from writing_coach.book_asset_store import AssetNotFound, InvalidAssetKey

_logger = logging.getLogger(__name__)

CONTRACT = "model-clip-v1"
CODEC = "webm-opus-mono-24k-32k"
MAX_LINE_MS = 60_000
DEFAULT_MAX_LINES = 500
KEY_PREFIX = "speaking/model-clip/"


@dataclass(frozen=True)
class ClipLine:
    """One speakable line of a source: everything that determines its clip, nothing that is learner data."""

    source_identity: str
    source_locator: str
    segment_id: str
    language: str
    start_ms: int
    end_ms: int
    # Where the key lives. A private upload's clip sits under that upload's own prefix so removing the
    # upload removes it; everything else shares the speaking prefix.
    owned_prefix: str = ""

    @property
    def span_ms(self) -> int:
        return self.end_ms - self.start_ms

    def speakable(self) -> bool:
        return 0 <= self.start_ms < self.end_ms and self.span_ms <= MAX_LINE_MS and bool(self.segment_id)

    def identity(self) -> str:
        text = "\0".join((
            CONTRACT, CODEC, self.source_identity, self.source_locator, self.segment_id,
            self.language.strip().casefold(), str(self.start_ms), str(self.end_ms),
        ))
        return hashlib.sha256(text.encode()).hexdigest()

    @property
    def key(self) -> str:
        prefix = f"{self.owned_prefix.rstrip('/')}/model-clip/" if self.owned_prefix else KEY_PREFIX
        return f"{prefix}{self.identity()}.webm"


def read_clip(assets: Any, line: ClipLine) -> bytes | None:
    """The stored clip, or None. Never cuts, never fetches a source."""
    try:
        data = assets.get(line.key)
    except (AssetNotFound, InvalidAssetKey):
        return None
    return data if isinstance(data, bytes) and data else None


def prepared_segment_ids(assets: Any, lines: Iterable[ClipLine]) -> list[str]:
    """Which of these lines have a stored clip (existence only; no bytes are read)."""
    found: list[str] = []
    for line in lines:
        if not line.speakable():
            continue
        try:
            if assets.exists(line.key):
                found.append(line.segment_id)
        except (InvalidAssetKey, OSError):
            continue
    return found


def cut_clip(source: Path, line: ClipLine) -> bytes:
    """Cut one line of a local source file to the model-clip encoding (ffmpeg, no network)."""
    with tempfile.TemporaryDirectory(prefix="orena-clip-") as directory:
        target = Path(directory) / "clip.webm"
        completed = subprocess.run(
            ["ffmpeg", "-protocol_whitelist", "file,pipe", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
             "-ss", f"{line.start_ms / 1000:.3f}", "-t", f"{line.span_ms / 1000:.3f}", "-i", str(source),
             "-vn", "-ac", "1", "-ar", "24000", "-c:a", "libopus", "-b:a", "32k", "-f", "webm", str(target)],
            capture_output=True, check=False, timeout=30,
        )
        if completed.returncode != 0 or not target.exists():
            raise RuntimeError("model clip could not be cut")
        data = target.read_bytes()
    if not data:
        raise RuntimeError("model clip is empty")
    return data


@dataclass
class PrepareResult:
    prepared: int = 0
    existing: int = 0
    skipped: int = 0
    failed: int = 0
    audio_ms: int = 0
    stopped_by_bound: bool = False
    failures: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "prepared": self.prepared, "existing": self.existing, "skipped": self.skipped,
            "failed": self.failed, "audio_ms": self.audio_ms, "stopped_by_bound": self.stopped_by_bound,
        }


def missing_lines(assets: Any, lines: Iterable[ClipLine]) -> list[ClipLine]:
    """The speakable lines that have no stored clip yet."""
    wanted = [line for line in lines if line.speakable()]
    have = set(prepared_segment_ids(assets, wanted))
    return [line for line in wanted if line.segment_id not in have]


def prepare_clips(
    assets: Any,
    source: Path,
    lines: Iterable[ClipLine],
    *,
    max_lines: int = DEFAULT_MAX_LINES,
    max_audio_ms: int | None = None,
) -> PrepareResult:
    """Cut and store every missing line from one local source. Idempotent: a stored clip is never cut again.

    Bounded by the number of lines cut and, optionally, the total audio they cover. A bound stops the run
    cleanly; the next run continues with what is still missing.
    """
    result = PrepareResult()
    all_lines = list(lines)
    result.skipped = sum(1 for line in all_lines if not line.speakable())
    speakable = [line for line in all_lines if line.speakable()]
    pending = missing_lines(assets, speakable)
    result.existing = len(speakable) - len(pending)
    for line in pending:
        if result.prepared >= max_lines or (max_audio_ms is not None and result.audio_ms + line.span_ms > max_audio_ms):
            result.stopped_by_bound = True
            break
        try:
            assets.put(line.key, cut_clip(source, line))
        except (RuntimeError, OSError, subprocess.TimeoutExpired, InvalidAssetKey) as exc:
            result.failed += 1
            result.failures.append(f"{line.segment_id}: {type(exc).__name__}")
            _logger.warning("model clip not prepared for %s", line.segment_id)
            continue
        result.prepared += 1
        result.audio_ms += line.span_ms
    return result
