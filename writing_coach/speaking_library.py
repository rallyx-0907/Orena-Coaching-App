"""The Speaking library: what a learner can say, from two real sources.

1. The Speaking catalogue (``content/speaking_catalog.v1.json``): items authored for
   speaking - lines to read, sounds to practise, prompts to retell or answer. It ships
   empty. Adding an item is a content decision, not code (UI_BACKEND_GAPS SP-1).
2. Listening lessons that offer the ``shadowing`` mode: a real clip with timed lines,
   so the clip is the model and each line is a line to say.

Every card carries only what the Speaking library frame draws: title, practice type,
level, length, how many lines. Nothing is invented for an item that does not have it.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Query
from fastapi.responses import Response

from writing_coach.core.errors import orena_http_error
from writing_coach.core.request_context import current_language_code
from writing_coach.listening_catalog import catalog_lesson, catalog_lessons
from writing_coach.media_safe_fetch import UnsafeMediaFetch, download_bounded
from writing_coach.book_asset_store import AssetNotFound, InvalidAssetKey

CATALOG_PATH = Path(__file__).resolve().parent / "content" / "speaking_catalog.v1.json"

# The practice types the Speaking library frame names. "clip" is shadowing a model clip.
PRACTICE_TYPES = ("sentences", "clip", "free", "sounds", "retell", "interview")
LANGUAGES = ("en", "zh")
_MAX_LINES = 60
_MAX_TEXT = 400


class SpeakingCatalogInvalid(ValueError):
    """The authored catalogue does not meet its contract."""


@dataclass(frozen=True)
class SpeakingLine:
    line_id: str
    text: str
    reading: str
    translations: Mapping[str, str]


@dataclass(frozen=True)
class SpeakingItem:
    item_id: str
    language: str
    title: str
    practice_type: str
    level: str
    artwork: str
    lines: tuple[SpeakingLine, ...]


def _text(value: Any, field: str, *, required: bool = True, limit: int = _MAX_TEXT) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str):
        raise SpeakingCatalogInvalid(f"{field} must be text")
    cleaned = value.strip()
    if required and not cleaned:
        raise SpeakingCatalogInvalid(f"{field} must not be empty")
    if len(cleaned) > limit:
        raise SpeakingCatalogInvalid(f"{field} is too long")
    return cleaned


def parse_catalog(raw: Mapping[str, Any]) -> tuple[SpeakingItem, ...]:
    """The published items of one catalogue document; anything malformed is refused whole."""
    if not isinstance(raw, Mapping) or raw.get("schema_version") != 1:
        raise SpeakingCatalogInvalid("schema_version must be 1")
    items = raw.get("items")
    if not isinstance(items, list):
        raise SpeakingCatalogInvalid("items must be a list")
    seen: set[str] = set()
    published: list[SpeakingItem] = []
    for index, entry in enumerate(items):
        where = f"items[{index}]"
        if not isinstance(entry, Mapping):
            raise SpeakingCatalogInvalid(f"{where} must be an object")
        item_id = _text(entry.get("item_id"), f"{where}.item_id", limit=120)
        if item_id in seen:
            raise SpeakingCatalogInvalid(f"{where}.item_id is duplicated")
        seen.add(item_id)
        language = _text(entry.get("language"), f"{where}.language", limit=8).casefold()
        if language not in LANGUAGES:
            raise SpeakingCatalogInvalid(f"{where}.language is unsupported")
        practice_type = _text(entry.get("practice_type"), f"{where}.practice_type", limit=20)
        if practice_type not in PRACTICE_TYPES:
            raise SpeakingCatalogInvalid(f"{where}.practice_type is unsupported")
        status = _text(entry.get("status"), f"{where}.status", limit=20).upper()
        raw_lines = entry.get("lines")
        if not isinstance(raw_lines, list) or not raw_lines or len(raw_lines) > _MAX_LINES:
            raise SpeakingCatalogInvalid(f"{where}.lines must hold 1-{_MAX_LINES} lines")
        lines: list[SpeakingLine] = []
        for at, line in enumerate(raw_lines):
            spot = f"{where}.lines[{at}]"
            if not isinstance(line, Mapping):
                raise SpeakingCatalogInvalid(f"{spot} must be an object")
            translations = line.get("translations") or {}
            if not isinstance(translations, Mapping):
                raise SpeakingCatalogInvalid(f"{spot}.translations must be an object")
            lines.append(
                SpeakingLine(
                    line_id=_text(line.get("line_id"), f"{spot}.line_id", limit=120),
                    text=_text(line.get("text"), f"{spot}.text"),
                    reading=_text(line.get("reading"), f"{spot}.reading", required=False),
                    translations={
                        _text(key, f"{spot}.translations key", limit=8): _text(value, f"{spot}.translations.{key}")
                        for key, value in translations.items()
                    },
                )
            )
        if status != "PUBLISHED":
            continue
        published.append(
            SpeakingItem(
                item_id=item_id,
                language=language,
                title=_text(entry.get("title"), f"{where}.title", limit=160),
                practice_type=practice_type,
                level=_text(entry.get("level"), f"{where}.level", required=False, limit=20),
                artwork=_text(entry.get("artwork"), f"{where}.artwork", required=False, limit=40),
                lines=tuple(lines),
            )
        )
    return tuple(published)


@lru_cache(maxsize=1)
def speaking_catalog() -> tuple[SpeakingItem, ...]:
    return parse_catalog(json.loads(CATALOG_PATH.read_text(encoding="utf-8")))


def _catalog_card(item: SpeakingItem) -> dict[str, Any]:
    return {
        "id": f"speak:{item.item_id}",
        "source": "speaking",
        "practice_type": item.practice_type,
        "title": item.title,
        "language": item.language,
        "level": item.level,
        "line_count": len(item.lines),
        "duration_ms": None,
        "artwork": item.artwork or "speaking",
        "thumbnail_url": None,
    }


def _lesson_card(lesson: Any) -> dict[str, Any]:
    transcript = lesson.media_object.transcript
    return {
        "id": f"media:{lesson.lesson_id}",
        "source": "listening",
        "practice_type": "clip",
        "title": lesson.media_object.asset.title,
        "language": lesson.source.language,
        "level": lesson.level or "",
        "line_count": len(transcript.segments) if transcript else 0,
        "duration_ms": lesson.duration_ms,
        "artwork": lesson.artwork,
        "thumbnail_url": lesson.source.poster_url,
    }


def speaking_library(language: str) -> list[dict[str, Any]]:
    authored = [_catalog_card(item) for item in speaking_catalog() if item.language == language]
    shadowable = [
        _lesson_card(lesson)
        for lesson in catalog_lessons(language=language)
        if "shadowing" in lesson.available_modes
        and lesson.media_object.transcript
        and lesson.media_object.transcript.segments
    ]
    return authored + shadowable


router = APIRouter(prefix="/api/speaking", tags=["speaking"])


@router.get("/library")
def read_speaking_library(
    language: str | None = Query(default=None, min_length=2, max_length=8),
) -> dict[str, Any]:
    selected = (language or current_language_code()).strip().casefold()
    if selected not in LANGUAGES:
        raise orena_http_error(422, "speaking_language_invalid", "Unsupported speaking language.")
    return {"language": selected, "items": speaking_library(selected)}


@router.get("/items/{item_id}")
def read_speaking_item(item_id: str) -> dict[str, Any]:
    """One authored item with its lines, for the Speaking workspace."""
    item = next((entry for entry in speaking_catalog() if entry.item_id == item_id), None)
    if item is None:
        raise orena_http_error(404, "speaking_item_not_found", "This Speaking item is unavailable.")
    return {
        **_catalog_card(item),
        "lines": [
            {
                "line_id": line.line_id,
                "text": line.text,
                "reading": line.reading,
                "translations": dict(line.translations),
            }
            for line in item.lines
        ],
    }


# --- The model line's audio, same-origin ------------------------------------------------------
# Compare receives one published line cut from approved source media. It never serves a learner's
# Speaking take; access and language are rechecked before stored media or source-cache reads.
_MODEL_CACHE = Path(tempfile.gettempdir()) / "orena-speaking-model"
_MODEL_LOCK = threading.Lock()
_MAX_SOURCE_BYTES = 64 * 1024 * 1024
_MAX_LINE_MS = 60_000
_MAX_REFERENCE_MS = 30_000
_MAX_REFERENCE_CHARS = 1_200
_YOUTUBE_SOURCE_CACHE_TTL_SECONDS = 300
_YOUTUBE_SOURCE_CACHE_MAX_ENTRIES = 4


class ModelAudioUnavailable(RuntimeError):
    """The source line is valid, but no approved bounded model audio is available."""


def _source_file(lesson: Any, *, access_check: Any = None) -> Path:
    if str(lesson.playback.provider).casefold() == "youtube":
        return _youtube_source_file(
            lesson.source.source_url,
            lesson.source.source_media_id,
            access_check=access_check,
        )
    target = _MODEL_CACHE / f"{lesson.source.source_media_id}.src"
    with _MODEL_LOCK:
        if not target.exists():
            partial = target.with_suffix(".part")
            download_bounded(lesson.playback.url, partial, max_bytes=_MAX_SOURCE_BYTES, timeout=30)
            partial.replace(target)
    return target


def _media_assets() -> Any:
    from writing_coach import media_library_api

    if media_library_api._asset_store is None:
        raise ModelAudioUnavailable("media asset storage is unavailable")
    return media_library_api._asset_store


def _cached_source_path(data: bytes) -> Path:
    revision = hashlib.sha256(data).hexdigest()
    target = _MODEL_CACHE / f"stored-{revision}.src"
    with _MODEL_LOCK:
        if not target.exists():
            _MODEL_CACHE.mkdir(parents=True, exist_ok=True)
            partial = target.with_suffix(".part")
            partial.write_bytes(data)
            partial.replace(target)
    return target


def _youtube_source_file(
    source_url: str,
    source_identity: str,
    *,
    expected_video_id: str = "",
    access_check: Any = None,
) -> Path:
    """Prepare bounded YouTube audio in the existing ephemeral model cache."""
    from writing_coach.media_providers.youtube import parse_youtube_video_id, recognizes_youtube_url
    from writing_coach.media_ingestion import ProviderUrlMalformed

    if not recognizes_youtube_url(source_url):
        raise ModelAudioUnavailable("this source has no approved model audio")
    try:
        video_id = parse_youtube_video_id(source_url)
    except (ProviderUrlMalformed, ValueError) as exc:
        raise ModelAudioUnavailable("this source has no approved model audio") from exc
    if expected_video_id and expected_video_id != video_id:
        raise ModelAudioUnavailable("this source has no approved model audio")
    identity = hashlib.sha256(f"youtube\0{source_identity}\0{source_url}".encode()).hexdigest()
    target = _MODEL_CACHE / f"youtube-{identity}.src"
    if access_check is not None:
        access_check()
    with _MODEL_LOCK:
        _prune_youtube_source_cache()
        if target.is_file():
            target_stat = target.stat()
            if time.time() - target_stat.st_mtime > _YOUTUBE_SOURCE_CACHE_TTL_SECONDS:
                target.unlink(missing_ok=True)
            elif target_stat.st_size > _MAX_SOURCE_BYTES:
                target.unlink(missing_ok=True)
                raise ModelAudioUnavailable("prepared source audio is unavailable")
        if not target.is_file():
            from writing_coach.media_providers.youtube_audio import download_audio
            from writing_coach.media_transcript_pipeline import PipelineStop, _env_int
            from writing_coach.media_timing import MediaAudioResolutionFailed
            from yt_dlp.utils import DownloadError

            max_seconds = _env_int("MEDIA_ASR_MAX_SECONDS", 5400)
            try:
                with tempfile.TemporaryDirectory(prefix="orena-speaking-source-") as work:
                    downloaded = download_audio(source_url, Path(work), max_seconds=max_seconds)
                    if not downloaded.is_file() or downloaded.stat().st_size > _MAX_SOURCE_BYTES:
                        raise ModelAudioUnavailable("bounded source audio preparation failed")
                    data = downloaded.read_bytes()
            except (PipelineStop, MediaAudioResolutionFailed, DownloadError, OSError, UnsafeMediaFetch, ValueError) as exc:
                raise ModelAudioUnavailable("bounded source audio preparation failed") from exc
            if not data or len(data) > _MAX_SOURCE_BYTES:
                raise ModelAudioUnavailable("bounded source audio preparation failed")
            if access_check is not None:
                access_check()
            _MODEL_CACHE.mkdir(parents=True, exist_ok=True)
            partial = target.with_suffix(".part")
            try:
                partial.write_bytes(data)
                partial.replace(target)
            except OSError as exc:
                partial.unlink(missing_ok=True)
                raise ModelAudioUnavailable("prepared source audio could not be cached") from exc
            _prune_youtube_source_cache(preserve=target)
    if access_check is not None:
        access_check()
    return target


def _prune_youtube_source_cache(now: float | None = None, preserve: Path | None = None) -> None:
    current_time = time.time() if now is None else now
    cached_sources = sorted(
        _MODEL_CACHE.glob("youtube-*.src"),
        key=lambda path: path.stat().st_mtime,
    )
    for cached in cached_sources:
        if current_time - cached.stat().st_mtime > _YOUTUBE_SOURCE_CACHE_TTL_SECONDS:
            cached.unlink(missing_ok=True)
    cached_sources = sorted(
        _MODEL_CACHE.glob("youtube-*.src"),
        key=lambda path: path.stat().st_mtime,
    )
    excess = max(0, len(cached_sources) - _YOUTUBE_SOURCE_CACHE_MAX_ENTRIES)
    candidates = [path for path in cached_sources if path != preserve]
    for evicted in candidates[:excess]:
        evicted.unlink(missing_ok=True)


def _stored_source_file(entry: Any, *, access_check: Any = None) -> Path:
    """Read only an Orena-owned media asset, never a URL carried by an entry.

    The library resolver has already checked the current learner and language.
    Re-reading bytes from the configured asset store on each request also gives
    the clip cache a content revision to key against.
    """
    from writing_coach import media_library_api

    playback = entry.playback
    url = str(playback.get("url") or "")
    parsed = urlsplit(url)
    prefix = "/api/media/files/"
    if playback.get("provider") != "orena":
        if (
            entry.provider == "youtube"
            and playback.get("provider") == "youtube"
            and playback.get("kind") in {"embed", "video"}
        ):
            return _youtube_source_file(
                entry.canonical_url,
                entry.media_id,
                expected_video_id=entry.provider_media_id,
                access_check=access_check,
            )
        raise ModelAudioUnavailable("stored model audio has no approved local asset")
    if playback.get("kind") != entry.media_type:
        raise ModelAudioUnavailable("stored model audio is unavailable")
    if not parsed.path.startswith(prefix) or parsed.query or parsed.fragment:
        raise ModelAudioUnavailable("stored model audio has no approved local asset")
    key = parsed.path[len(prefix):]
    if not key or media_library_api._asset_store is None:
        raise ModelAudioUnavailable("stored media assets are unavailable")
    if access_check is not None:
        access_check()
    try:
        data = media_library_api._asset_store.get(key)
    except (AssetNotFound, InvalidAssetKey) as exc:
        raise LookupError(entry.media_id) from exc
    if not isinstance(data, bytes) or not data or len(data) > _MAX_SOURCE_BYTES:
        raise ModelAudioUnavailable("stored model audio is unavailable")
    if access_check is not None:
        access_check()
    return _cached_source_path(data)


def _stored_segment(entry: Any, segment_id: str) -> tuple[Mapping[str, Any], int, int]:
    """Resolve a transcript line after the ownership resolver has run."""
    from writing_coach.core.request_context import current_language_code

    if (
        str(getattr(entry, "status", "")).casefold() != "published"
        or str(getattr(entry, "language", "")).casefold() != current_language_code().strip().casefold()
        or getattr(entry, "media_type", "") not in {"audio", "video"}
    ):
        raise LookupError(segment_id)
    lesson = entry.lesson
    if not isinstance(lesson, Mapping):
        raise LookupError(segment_id)
    if str(lesson.get("status", "PUBLISHED")).upper() != "PUBLISHED":
        # Rights review holds public publication, not the owner's ready private
        # learning flow. Reuse the deterministic admission gate; find_entry has
        # already checked ownership, language and visibility on every access.
        from writing_coach.media_transcript_pipeline import usable_transcript

        if not (
            entry.library == "personal"
            and str(lesson.get("status", "")).upper() == "NEEDS_REVIEW"
            and (entry.processing or {}).get("state") == "ready"
            and usable_transcript(entry)[0]
        ):
            raise LookupError(segment_id)
    payload = lesson.get("payload")
    if not isinstance(payload, Mapping):
        raise LookupError(segment_id)
    asset = payload.get("asset")
    transcript = payload.get("transcript")
    if (
        not isinstance(asset, Mapping)
        or str(asset.get("source_language") or "").strip().casefold() != str(entry.language).strip().casefold()
        or not isinstance(transcript, Mapping)
    ):
        raise LookupError(segment_id)
    segments = transcript.get("segments")
    segment = next(
        (value for value in segments if isinstance(value, Mapping) and str(value.get("segment_id")) == segment_id),
        None,
    ) if isinstance(segments, list) else None
    if segment is None:
        raise LookupError(segment_id)
    try:
        start_ms = int(segment["start_ms"])
        end_ms = int(segment["end_ms"])
    except (KeyError, TypeError, ValueError):
        raise LookupError(segment_id) from None
    if start_ms < 0 or end_ms <= start_ms or end_ms - start_ms > _MAX_LINE_MS:
        raise LookupError(segment_id)
    return segment, start_ms, end_ms


@dataclass(frozen=True)
class _ResolvedModelLine:
    lesson: Any | None
    entry: Any | None
    segment_id: str
    language: str
    reference_text: str
    start_ms: int
    end_ms: int
    canonical_words: tuple[Mapping[str, Any], ...]
    source_identity: str
    source_locator: str


def _resolve_model_line(lesson_id: str, segment_id: str) -> _ResolvedModelLine:
    """Resolve a model line with publication, language and ownership gates."""
    resolved_id = str(lesson_id or "").strip()
    if resolved_id.startswith("upload:"):
        resolved_id = resolved_id[len("upload:"):]
    if not resolved_id or "/" in resolved_id or "\\" in resolved_id:
        raise LookupError(segment_id)
    lesson = catalog_lesson(resolved_id)
    if lesson is not None:
        if lesson.source.language.strip().casefold() != current_language_code().strip().casefold():
            raise LookupError(segment_id)
        transcript = lesson.media_object.transcript
        timed_segment = next(
            (item for item in (transcript.segments if transcript else ()) if item.segment_id == segment_id),
            None,
        )
        if timed_segment is None or lesson.playback.kind not in {"audio", "video"}:
            raise LookupError(segment_id)
        source_segment = next(
            (item for item in lesson.source.segments if item.get("segment_id") == segment_id),
            {},
        )
        raw_words = source_segment.get("words") or ()
        return _ResolvedModelLine(
            lesson=lesson,
            entry=None,
            segment_id=segment_id,
            language=lesson.source.language,
            reference_text=str(source_segment.get("spoken_text") or timed_segment.original_text).strip(),
            start_ms=timed_segment.start_ms,
            end_ms=timed_segment.end_ms,
            canonical_words=tuple(word for word in raw_words if isinstance(word, Mapping)),
            source_identity=f"catalog:{lesson.source.source_media_id}",
            source_locator=lesson.source.source_url,
        )

    from writing_coach import media_library_api

    # find_entry rechecks current owner, language and shared publication before
    # any durable source or reference cache is read.
    entry = media_library_api.find_entry(resolved_id)
    if entry is None:
        raise LookupError(segment_id)
    segment, start_ms, end_ms = _stored_segment(entry, segment_id)
    raw_words = segment.get("words") or ()
    return _ResolvedModelLine(
        lesson=None,
        entry=entry,
        segment_id=segment_id,
        language=str(entry.language),
        reference_text=str(segment.get("spoken_text") or segment.get("original_text") or "").strip(),
        start_ms=start_ms,
        end_ms=end_ms,
        canonical_words=tuple(word for word in raw_words if isinstance(word, Mapping)),
        source_identity=f"stored:{entry.media_id}",
        source_locator=f"{entry.canonical_url}\0{entry.playback.get('url', '')}",
    )


def _recheck_model_line(line: _ResolvedModelLine, lesson_id: str, segment_id: str) -> None:
    current = _resolve_model_line(lesson_id, segment_id)
    if (
        current.source_identity != line.source_identity
        or current.source_locator != line.source_locator
        or current.language != line.language
        or current.reference_text != line.reference_text
        or current.start_ms != line.start_ms
        or current.end_ms != line.end_ms
    ):
        raise LookupError(segment_id)


def _line_source_file(line: _ResolvedModelLine, lesson_id: str, segment_id: str) -> Path:
    access_check = lambda: _recheck_model_line(line, lesson_id, segment_id)
    return (
        _source_file(line.lesson, access_check=access_check)
        if line.lesson is not None
        else _stored_source_file(line.entry, access_check=access_check)
    )


def _cut_model_line(line: _ResolvedModelLine, source: Path) -> bytes:
    start_ms, end_ms = line.start_ms, line.end_ms
    span = end_ms - start_ms
    revision = hashlib.sha256(source.read_bytes()).hexdigest()
    identity = hashlib.sha256(
        f"{line.source_identity}:{line.segment_id}:{revision}:{start_ms}:{end_ms}".encode()
    ).hexdigest()
    cut = _MODEL_CACHE / f"line-{identity}.webm"
    partial = cut.with_name(f"{cut.stem}.part.webm")
    with _MODEL_LOCK:
        if not cut.exists():
            _MODEL_CACHE.mkdir(parents=True, exist_ok=True)
            completed = subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                 "-ss", f"{start_ms / 1000:.3f}", "-t", f"{span / 1000:.3f}", "-i", str(source),
                 "-vn", "-ac", "1", "-ar", "24000", "-c:a", "libopus", "-b:a", "32k", "-f", "webm", str(partial)],
                capture_output=True, check=False, timeout=30,
            )
            if completed.returncode != 0 or not partial.exists():
                partial.unlink(missing_ok=True)
                raise RuntimeError("model line could not be prepared")
            partial.replace(cut)
        return cut.read_bytes()


def _canonical_word_timings(line: _ResolvedModelLine) -> list[dict[str, Any]]:
    words: list[dict[str, Any]] = []
    previous_end_ms = line.start_ms
    for word in line.canonical_words:
        text = str(word.get("text") or word.get("word") or "").strip()
        start_ms = word.get("start_ms")
        end_ms = word.get("end_ms")
        if (
            not isinstance(start_ms, int)
            or isinstance(start_ms, bool)
            or not isinstance(end_ms, int)
            or isinstance(end_ms, bool)
        ):
            return []
        if not text or start_ms < previous_end_ms or end_ms <= start_ms or end_ms > line.end_ms:
            return []
        words.append({
            "text": text,
            "offset_ms": start_ms - line.start_ms,
            "duration_ms": end_ms - start_ms,
            "error_type": "None",
        })
        previous_end_ms = end_ms
    expected = re.sub(r"\W", "", line.reference_text.casefold())
    observed = re.sub(r"\W", "", "".join(word["text"] for word in words).casefold())
    return words if words and expected and expected == observed else []


def _provider_cache_identity(provider: Any, language: str) -> str:
    """Hash only non-secret provider configuration that can change timings."""
    values: dict[str, Any] = {
        "contract": "speaking-reference-v2",
        "provider": str(getattr(provider, "provider_id", "unknown")),
        "class": f"{type(provider).__module__}.{type(provider).__qualname__}",
        "max_bytes": getattr(provider, "max_bytes", None),
        "max_reference_chars": getattr(provider, "max_reference_chars", None),
    }
    for name in ("_region", "_en_locale", "_zh_locale", "_enable_prosody", "_timeout_seconds"):
        value = getattr(provider, name, None)
        if isinstance(value, (str, int, float, bool)):
            values[name] = value
    values["phoneme_alphabet"] = _provider_phoneme_alphabet(provider, language)
    locale = getattr(provider, "_locale", None)
    if callable(locale):
        try:
            values["locale"] = str(locale(language))
        except Exception:
            values["locale"] = language
    serialized = json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode()).hexdigest()


def _provider_phoneme_alphabet(provider: Any, language: str) -> str:
    method = getattr(provider, "phoneme_alphabet", None)
    if not callable(method):
        return ""
    try:
        value = method(language)
    except Exception:
        return ""
    return str(value).strip().upper()


def _read_reference_cache(asset_store: Any, key: str, fingerprint: str) -> dict[str, Any] | None:
    try:
        data = asset_store.get(key)
        cached = json.loads(data.decode("utf-8"))
    except (AssetNotFound, InvalidAssetKey, AttributeError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if (
        not isinstance(cached, dict)
        or cached.get("source_fingerprint") != fingerprint
        or cached.get("score_kind") != "measured"
        or cached.get("model_audio_available") is not True
        or cached.get("reference_available") is not True
        or not isinstance(cached.get("words"), list)
    ):
        return None
    return cached


def _write_reference_cache(asset_store: Any, key: str, value: Mapping[str, Any]) -> None:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    asset_store.put(key, payload)


@router.post("/model-reference/{lesson_id}/{segment_id}")
def read_model_reference(lesson_id: str, segment_id: str) -> dict[str, Any]:
    """Return source word timings only; never record or expose a learner score."""
    try:
        line = _resolve_model_line(lesson_id, segment_id)
        if not line.reference_text or len(line.reference_text) > _MAX_REFERENCE_CHARS:
            raise orena_http_error(422, "speaking_reference_invalid", "This model line is too long to align.")
        if line.end_ms - line.start_ms > _MAX_REFERENCE_MS:
            raise orena_http_error(422, "speaking_reference_invalid", "This model line is too long to align.")
        source = _line_source_file(line, lesson_id, segment_id)
        _recheck_model_line(line, lesson_id, segment_id)
        audio = _cut_model_line(line, source)
        _recheck_model_line(line, lesson_id, segment_id)
    except LookupError as exc:
        raise orena_http_error(404, "speaking_model_not_found", "This model line is unavailable.") from exc
    except ModelAudioUnavailable:
        _recheck_model_line(line, lesson_id, segment_id)
        return {
            "model_audio_available": False,
            "reference_available": False,
            "score_kind": "unavailable",
            "source_fingerprint": None,
            "words": [],
        }
    except (UnsafeMediaFetch, RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        raise orena_http_error(503, "speaking_model_unavailable", "Model audio is not ready.", retryable=True) from exc

    audio_digest = hashlib.sha256(audio).hexdigest()
    audio_fingerprint = hashlib.sha256(
        f"{audio_digest}\0{line.language}\0{line.reference_text}".encode()
    ).hexdigest()
    canonical = _canonical_word_timings(line)
    if canonical:
        _recheck_model_line(line, lesson_id, segment_id)
        return {
            "model_audio_available": True,
            "reference_available": True,
            "score_kind": "measured",
            "source_fingerprint": audio_fingerprint,
            "words": canonical,
        }

    from types import SimpleNamespace

    from writing_coach import speech_api

    try:
        provider = speech_api._pronunciation_provider()
    except Exception as exc:
        # Preserve the canonical 503 envelope from the configured provider resolver.
        from fastapi import HTTPException

        if isinstance(exc, HTTPException):
            raise
        raise orena_http_error(503, "pronunciation_unconfigured", "Pronunciation timing is not configured.") from exc
    provider_id = str(getattr(provider, "provider_id", "")).casefold()
    if provider_id in {"demo-synthetic", "demo"}:
        raise orena_http_error(503, "pronunciation_unconfigured", "Measured pronunciation timing is not configured.")
    provider_limit = int(getattr(provider, "max_reference_chars", _MAX_REFERENCE_CHARS))
    if len(line.reference_text) > min(_MAX_REFERENCE_CHARS, provider_limit):
        raise orena_http_error(422, "speaking_reference_invalid", "This model line is too long to align.")

    phoneme_alphabet = _provider_phoneme_alphabet(provider, line.language)
    provider_config = _provider_cache_identity(provider, line.language)
    fingerprint = hashlib.sha256(
        f"{audio_digest}\0{line.reference_text}\0{line.language}\0{provider_config}".encode()
    ).hexdigest()
    asset_store = _media_assets()
    cache_key = f"speaking/reference/{fingerprint}.json"
    cached = _read_reference_cache(asset_store, cache_key, fingerprint)
    if cached is not None:
        _recheck_model_line(line, lesson_id, segment_id)
        return cached

    try:
        result = speech_api._assess(
            provider,
            audio,
            SimpleNamespace(filename="model.webm", content_type="audio/webm"),
            line.language,
            line.reference_text,
            False,
        )
    except Exception:
        _recheck_model_line(line, lesson_id, segment_id)
        raise
    _recheck_model_line(line, lesson_id, segment_id)
    if str(getattr(result, "score_kind", "")).casefold() != "measured":
        raise orena_http_error(503, "pronunciation_unconfigured", "Measured pronunciation timing is not available.")
    words: list[dict[str, Any]] = []
    for word in getattr(result, "words", ()):
        text = str(getattr(word, "word", "") or "").strip()
        error_type = str(getattr(word, "error_type", "None") or "None")[:60]
        offset_ms = getattr(word, "offset_ms", None)
        duration_ms = getattr(word, "duration_ms", None)
        if error_type.casefold() == "insertion":
            continue
        if (
            not text
            or not isinstance(offset_ms, int)
            or isinstance(offset_ms, bool)
            or not isinstance(duration_ms, int)
            or isinstance(duration_ms, bool)
            or offset_ms < 0
            or duration_ms <= 0
            or offset_ms + duration_ms > _MAX_REFERENCE_MS + 500
        ):
            continue
        projected_word = {
            "text": text[:120],
            "offset_ms": offset_ms,
            "duration_ms": duration_ms,
            "error_type": error_type,
        }
        if phoneme_alphabet == "IPA":
            phoneme_values = [
                str(getattr(phoneme, "phoneme", "") or "").strip()
                for phoneme in getattr(word, "phonemes", ())
            ]
            phoneme_values = [value for value in phoneme_values if value]
            if phoneme_values:
                projected_word["ipa"] = f"/{''.join(phoneme_values)}/"
        words.append(projected_word)
    if not words:
        raise orena_http_error(503, "pronunciation_provider_malformed", "Measured word timing is unavailable.", retryable=True)
    body = {
        "model_audio_available": True,
        "reference_available": True,
        "score_kind": "measured",
        "source_fingerprint": fingerprint,
        "words": words,
    }
    _recheck_model_line(line, lesson_id, segment_id)
    try:
        _write_reference_cache(asset_store, cache_key, body)
    except OSError as exc:
        raise orena_http_error(503, "speaking_reference_cache_unavailable", "Model timing is not ready.", retryable=True) from exc
    _recheck_model_line(line, lesson_id, segment_id)
    return body


def model_line_audio(lesson_id: str, segment_id: str) -> bytes:
    line = _resolve_model_line(lesson_id, segment_id)
    if line.end_ms - line.start_ms > _MAX_LINE_MS:
        raise ModelAudioUnavailable("model line is too long")
    source = _line_source_file(line, lesson_id, segment_id)
    _recheck_model_line(line, lesson_id, segment_id)
    audio = _cut_model_line(line, source)
    _recheck_model_line(line, lesson_id, segment_id)
    return audio


@router.get("/model-audio/{lesson_id}/{segment_id}")
def read_model_audio(lesson_id: str, segment_id: str) -> Response:
    try:
        data = model_line_audio(lesson_id, segment_id)
    except LookupError as exc:
        raise orena_http_error(404, "speaking_model_not_found", "This model line is unavailable.") from exc
    except (UnsafeMediaFetch, RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        raise orena_http_error(502, "speaking_model_unavailable", "The model line could not be prepared.", retryable=True) from exc
    return Response(content=data, media_type="audio/webm", headers={"Cache-Control": "private, no-store"})
