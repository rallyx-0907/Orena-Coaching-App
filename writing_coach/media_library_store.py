"""Durable, single-process shared Listening Library index.

The sandbox runs one uvicorn process. An atomic replace keeps the file whole,
and one lock per index file keeps two threads of that process from each
reading the index, adding an entry and writing back over the other's entry -
FastAPI runs plain `def` routes in a thread pool, so imports and uploads do
overlap. A future multi-process deployment must replace this implementation
rather than pretending a JSON file has cross-process locks.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
from dataclasses import asdict, dataclass
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit

from writing_coach.listening_catalog import EN_LEVELS, ZH_LEVELS

MEDIA_LIBRARY_ROOT = Path(
    os.getenv("MEDIA_LIBRARY_ROOT", str(Path(__file__).resolve().parents[1] / "data" / "media_library"))
)
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_WRITERS: dict[str, threading.Lock] = {}
_WRITERS_GUARD = threading.Lock()


def _writer_for(index: Path) -> threading.Lock:
    """One lock per index file, shared by every store object that opens it."""
    key = os.path.normcase(os.path.abspath(index))
    with _WRITERS_GUARD:
        return _WRITERS.setdefault(key, threading.Lock())


@dataclass(frozen=True)
class MediaLibraryEntry:
    media_id: str
    media_type: str
    provider: str
    provider_media_id: str
    canonical_url: str
    playback: Mapping[str, str]
    title: str
    thumbnail: Mapping[str, str]
    duration_ms: int
    language: str
    level: str
    creator: str
    source: Mapping[str, str]
    library: str
    created_at: str
    lesson: Mapping[str, Any] | None
    # Where this item is in its life, not where it is stored. An index written
    # before this field existed holds rows that were, by being in it, published
    # - which is why the default is the only honest one.
    status: str = "published"


class MediaLibraryStore(Protocol):
    def list(self, *, language: str | None = None) -> list[MediaLibraryEntry]: ...
    def get(self, media_id: str) -> MediaLibraryEntry | None: ...
    def upsert(self, entry: MediaLibraryEntry) -> MediaLibraryEntry: ...
    def delete(self, media_id: str) -> bool: ...


def _require_text(value: object, name: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or value != value.strip() or (not value and not allow_empty):
        raise ValueError(f"{name} is invalid")
    return value


def _mapping(value: object, name: str) -> Mapping[str, str]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) and isinstance(item, str) for key, item in value.items()):
        raise ValueError(f"{name} is invalid")
    return value


def validate_entry(entry: MediaLibraryEntry) -> MediaLibraryEntry:
    """Keep corrupt rows from becoming a browse-time learner failure."""
    for name in ("media_id", "provider", "provider_media_id"):
        value = _require_text(getattr(entry, name), name)
        if not _ID.fullmatch(value):
            raise ValueError(f"{name} is invalid")
    if entry.media_type not in {"video", "audio"}:
        raise ValueError("media_type is invalid")
    # Two libraries share one store and are never listed together: `shared` is
    # what an administrator published and every learner may browse; `personal` is
    # a file one learner uploaded, resolvable only through the unguessable id
    # minted for it. Which items a learner *has* stays on their device
    # (`static/orena/product/memory.js`); this row is bytes and metadata, not
    # ownership, because learner-owned persistence is a reserved decision.
    if entry.library not in {"shared", "personal"}:
        raise ValueError("library is invalid")
    # Three states and no fourth: `published` is served, `unpublished` is off
    # the shelf for now, `archived` is retired. None of them is a deletion -
    # the bytes, the provenance and the transcript survive all three, so a
    # decision can be taken back.
    if entry.status not in {"published", "unpublished", "archived"}:
        raise ValueError("status is invalid")
    if entry.language not in {"en", "zh"}:
        raise ValueError("language is invalid")
    if entry.level and entry.level not in (EN_LEVELS if entry.language == "en" else ZH_LEVELS):
        raise ValueError("level is invalid")
    _require_text(entry.title, "title")
    _require_text(entry.creator, "creator", allow_empty=True)
    _require_text(entry.canonical_url, "canonical_url", allow_empty=True)
    if entry.canonical_url:
        parsed = urlsplit(entry.canonical_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("canonical_url is invalid")
    if not isinstance(entry.duration_ms, int) or isinstance(entry.duration_ms, bool) or entry.duration_ms < 0:
        raise ValueError("duration_ms is invalid")
    playback = _mapping(entry.playback, "playback")
    if set(playback) != {"provider", "kind", "url"} or not all(playback.values()):
        raise ValueError("playback is invalid")
    thumbnail = _mapping(entry.thumbnail, "thumbnail")
    if set(thumbnail) != {"kind", "ref"} or thumbnail["kind"] not in {"provider-url", "asset", "none"}:
        raise ValueError("thumbnail is invalid")
    if (thumbnail["kind"] == "none") != (thumbnail["ref"] == ""):
        raise ValueError("thumbnail is invalid")
    source = _mapping(entry.source, "source")
    required_source = {"provider", "type", "provenance_url", "license", "review_status", "imported_by"}
    if not required_source.issubset(source):
        raise ValueError("source is invalid")
    try:
        parsed_created = datetime.fromisoformat(entry.created_at.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("created_at is invalid") from exc
    if parsed_created.tzinfo is None:
        raise ValueError("created_at is invalid")
    if entry.lesson is not None and not isinstance(entry.lesson, Mapping):
        raise ValueError("lesson is invalid")
    return entry


class FileMediaLibraryStore:
    """JSON-backed shared index with integrity checks and atomic writes."""

    def __init__(self, root: Path = MEDIA_LIBRARY_ROOT) -> None:
        self._root = Path(root)
        self._index = self._root / "index.json"
        self._writer = _writer_for(self._index)
        self.last_read_issue = ""

    def _read(self) -> dict[str, MediaLibraryEntry]:
        self.last_read_issue = ""
        try:
            raw = self._index.read_text(encoding="utf-8")
        except FileNotFoundError:
            self.last_read_issue = "index_missing"
            return {}
        except OSError:
            self.last_read_issue = "index_unreadable"
            return {}
        try:
            payload = json.loads(raw)
            body = payload["entries"]
            expected = payload["integrity"]
            canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
            if hashlib.sha256(canonical).hexdigest() != expected or not isinstance(body, list):
                raise ValueError("integrity")
            entries = [validate_entry(MediaLibraryEntry(**item)) for item in body]
            if len({item.media_id for item in entries}) != len(entries):
                raise ValueError("duplicate")
            return {item.media_id: item for item in entries}
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            self.last_read_issue = "index_corrupt"
            return {}

    def _write(self, entries: Mapping[str, MediaLibraryEntry]) -> None:
        ordered = [asdict(entries[key]) for key in sorted(entries)]
        body = json.dumps(ordered, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        payload = {"schema_version": 1, "entries": ordered, "integrity": hashlib.sha256(body.encode()).hexdigest()}
        self._root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self._root, delete=False) as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            temporary = Path(handle.name)
        temporary.replace(self._index)

    def list(
        self,
        *,
        language: str | None = None,
        library: str = "shared",
        status: str | None = "published",
    ) -> list[MediaLibraryEntry]:
        """Published only, unless the caller says otherwise.

        The default is what a learner may see, because every learner-facing
        path reaches this method and a new state must never become visible by
        forgetting to filter. `status=None` is the operator's listing.
        """
        entries = self._read().values()
        return sorted(
            (
                item
                for item in entries
                if item.library == library
                and (language is None or item.language == language)
                and (status is None or item.status == status)
            ),
            key=lambda item: (item.created_at, item.media_id), reverse=True,
        )

    def get(self, media_id: str) -> MediaLibraryEntry | None:
        return self._read().get(media_id)

    def upsert(self, entry: MediaLibraryEntry) -> MediaLibraryEntry:
        validate_entry(entry)
        with self._writer:
            entries = self._read()
            entries[entry.media_id] = entry
            self._write(entries)
        return entry

    def delete(self, media_id: str) -> bool:
        with self._writer:
            entries = self._read()
            if media_id not in entries:
                return False
            del entries[media_id]
            self._write(entries)
        return True
