"""Explicit, bounded backfill of model clips for content that was admitted before D-140.

Never runs on navigation. An operator starts it (scripts/backfill_model_clips.py) against a store it names.
It is idempotent (a stored clip is skipped), bounded by lines cut and by audio covered, and calls no provider.
The only network use is the source acquisition that content import itself performs: a catalogue source URL
through the bounded fetcher, or a YouTube source through the same audio downloader the import pipeline uses.
"""
from __future__ import annotations

import logging
import tempfile
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from writing_coach import model_clips

_logger = logging.getLogger(__name__)

Acquire = Callable[[Any, Path], "Path | None"]


def _entry_source(entry: Any, work: Path, *, max_seconds: int) -> Path | None:
    from writing_coach import speaking_library

    if entry.provider == "youtube":
        from writing_coach.media_providers.youtube_audio import download_audio

        return Path(download_audio(entry.canonical_url, work, max_seconds=max_seconds))
    return speaking_library._stored_source_file(entry)


def _lesson_source(lesson: Any) -> Path | None:
    from writing_coach import speaking_library

    if str(lesson.playback.provider).casefold() == "youtube":
        return None
    return speaking_library._source_file(lesson)


def backfill(
    store: Any,
    assets: Any,
    *,
    media_ids: Iterable[str] | None = None,
    include_catalog: bool = True,
    include_entries: bool = True,
    language: str | None = None,
    max_lines: int = 200,
    max_audio_ms: int = 30 * 60 * 1000,
    max_source_seconds: int = 5400,
    dry_run: bool = False,
    entry_source: Callable[..., Path | None] = _entry_source,
    lesson_source: Callable[[Any], Path | None] = _lesson_source,
) -> dict[str, Any]:
    """Prepare the missing clips of admitted content, up to the bounds. Returns what was (or would be) done."""
    from writing_coach import speaking_library
    from writing_coach.listening_catalog import catalog_lessons

    wanted = {item for item in media_ids} if media_ids is not None else None
    report: dict[str, Any] = {"dry_run": dry_run, "items": [], "prepared": 0, "existing": 0, "failed": 0,
                              "missing": 0, "audio_ms": 0, "stopped_by_bound": False}

    targets: list[tuple[str, Any, list[model_clips.ClipLine], str]] = []
    if include_catalog:
        for lesson in catalog_lessons(language=language):
            if wanted is None or lesson.lesson_id in wanted:
                targets.append((lesson.lesson_id, lesson, speaking_library.catalog_clip_lines(lesson), "catalog"))
    if include_entries and store is not None:
        for library in ("shared", "personal"):
            for entry in store.list(language=language, library=library, status=None):
                if wanted is None or entry.media_id in wanted:
                    targets.append((entry.media_id, entry, speaking_library.entry_clip_lines(entry), "stored"))

    lines_left = max_lines
    audio_left = max_audio_ms
    for media_id, subject, lines, kind in targets:
        pending = model_clips.missing_lines(assets, lines)
        speakable = [line for line in lines if line.speakable()]
        item = {"id": media_id, "kind": kind, "lines": len(speakable), "missing": len(pending), "prepared": 0, "failed": 0}
        report["existing"] += len(speakable) - len(pending)
        report["missing"] += len(pending)
        if not pending:
            report["items"].append(item)
            continue
        if dry_run:
            report["items"].append(item)
            continue
        if lines_left <= 0 or audio_left <= 0:
            report["stopped_by_bound"] = True
            report["items"].append({**item, "note": "not reached: bound"})
            continue
        try:
            with tempfile.TemporaryDirectory(prefix="orena-clip-backfill-") as directory:
                source = (
                    lesson_source(subject) if kind == "catalog"
                    else entry_source(subject, Path(directory), max_seconds=max_source_seconds)
                )
                if source is None:
                    item["note"] = "no admitted local source"
                    report["items"].append(item)
                    continue
                result = model_clips.prepare_clips(assets, Path(source), pending, max_lines=lines_left, max_audio_ms=audio_left)
        except Exception as exc:  # noqa: BLE001 - one item's source must not stop the others
            _logger.warning("backfill: %s skipped (%s)", media_id, type(exc).__name__)
            detail = f" ({str(exc)[:100]})" if type(exc).__name__ == "UnsafeMediaFetch" else ""  # that text is learner-safe
            item["note"] = f"source unavailable: {type(exc).__name__}{detail}"
            report["items"].append(item)
            continue
        item["prepared"], item["failed"] = result.prepared, result.failed
        report["prepared"] += result.prepared
        report["failed"] += result.failed
        report["audio_ms"] += result.audio_ms
        lines_left -= result.prepared
        audio_left -= result.audio_ms
        if result.stopped_by_bound:
            report["stopped_by_bound"] = True
        report["items"].append(item)
    return report
