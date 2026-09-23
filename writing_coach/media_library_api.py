"""HTTP boundary for the Media Library — stored media, admin source import, learner upload.

Two routers live here on purpose, because they are the same feature seen from
two sides:

* `/api/media/...` — the library's own surface: an opaque-key file route for
  media Orena stores itself (a generated thumbnail, an uploaded file), the admin
  source importer, and the shared-library listing an operator can check.
* `/api/media-learning/upload` — a learner's own file, published into *their*
  content rather than into the shared catalog. It sits on the existing
  media-learning prefix because it answers with the same acquisition payload
  `/api/media-learning/import` already answers with; a learner's file and a
  learner's URL must not produce two different shapes.

Nothing here decides ownership. An admin import is written with
`library="shared"` and is served to every learner; a learner upload is written
with `library="personal"` and is only resolvable by the unguessable identity
this module mints for it. That is the ownership contract the running product
already uses (shared content is reusable, membership is the learner's), not a
second one invented here.
"""
from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Any, Callable, Mapping

from fastapi import APIRouter, File, Form, Request, UploadFile
from pydantic import BaseModel, Field

from writing_coach.book_asset_store import AssetNotFound, BookAssetStore, InvalidAssetKey
from writing_coach.core.errors import orena_http_error
from writing_coach.media_library_store import MediaLibraryEntry
from writing_coach.media_source_import import MediaSourceImporter, UnsafeMediaFetch
from writing_coach.media_thumbnail import MAX_UPLOAD_BYTES, TempMediaFile

router = APIRouter(prefix="/api/media", tags=["media-library"])
media_learning_router = APIRouter(prefix="/api/media-learning", tags=["media-learning"])

_store: Any = None
_asset_store: BookAssetStore | None = None
_importer: MediaSourceImporter | None = None
_admin_guard: Callable[[Request], dict[str, Any]] | None = None
_language_supported: Callable[[str], bool] | None = None
# Set by app.py from the Listening boundary: resolving a stored entry into the
# learner-facing acquisition payload is that module's job (it owns support
# language resolution and the meaning cache), so this route asks for it rather
# than growing a second serializer.
_learner_payload: Callable[[str, str], dict[str, Any] | None] | None = None

MAX_IMPORT_URLS = 50
MEDIA_TYPES = {"video/*", "audio/*"}
_logger = logging.getLogger(__name__)


def configure_media_library(
    store: Any,
    asset_store: BookAssetStore,
    importer: MediaSourceImporter,
    *,
    admin_guard: Callable[[Request], dict[str, Any]],
    language_supported: Callable[[str], bool],
) -> None:
    global _store, _asset_store, _importer, _admin_guard, _language_supported
    _store = store
    _asset_store = asset_store
    _importer = importer
    _admin_guard = admin_guard
    _language_supported = language_supported


def configure_media_library_payload(builder: Callable[[str, str], dict[str, Any] | None]) -> None:
    """Install the stored-entry → learner payload resolver."""
    global _learner_payload
    _learner_payload = builder


def _installed() -> tuple[Any, BookAssetStore, MediaSourceImporter]:
    if _store is None or _asset_store is None or _importer is None:
        raise orena_http_error(
            503, "media_library_unavailable", "The Media Library is not configured for this environment."
        )
    return _store, _asset_store, _importer


def _require_language(raw: str, field: str = "language") -> str:
    language = (raw or "").strip().casefold()
    if not language or _language_supported is None or not _language_supported(language):
        raise orena_http_error(422, "media_library_invalid_language", f"Unsupported {field}.")
    return language


def _require_admin(request: Request) -> dict[str, Any]:
    if _admin_guard is None:
        raise orena_http_error(503, "media_library_unavailable", "The Media Library is not configured for this environment.")
    return _admin_guard(request)


class MediaPreviewIn(BaseModel):
    urls: list[str] = Field(default_factory=list, max_length=MAX_IMPORT_URLS)
    language: str = Field(default="en", max_length=16)


class MediaImportItemIn(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    # Only the fields an operator may overrule after seeing the preview. The
    # provider owns title and duration; a human owns level, topic and tags.
    title: str | None = Field(default=None, max_length=240)
    level: str | None = Field(default=None, max_length=16)
    topic: str | None = Field(default=None, max_length=64)
    tags: list[str] = Field(default_factory=list, max_length=20)
    media_id: str | None = Field(default=None, max_length=255)
    thumbnail_url: str | None = Field(default=None, max_length=1024)


class MediaImportIn(BaseModel):
    language: str = Field(default="en", max_length=16)
    items: list[MediaImportItemIn] = Field(default_factory=list, max_length=MAX_IMPORT_URLS)


@router.get("/files/{key:path}")
def stored_media_file(key: str, variant: str = "") -> Any:
    """Serve bytes this application stores under an opaque, validated key.

    A key is never a path and never a URL: `BookAssetStore` validates every
    segment, so a traversal attempt is a 404 here rather than a read. The
    response is deliberately cacheable forever — the key changes whenever the
    bytes do, so there is no staleness to trade against.
    """
    from fastapi.responses import Response

    _, asset_store, _ = _installed()
    try:
        payload = asset_store.get(key)
    except (AssetNotFound, InvalidAssetKey):
        raise orena_http_error(404, "media_asset_not_found", "This media file is not available.")
    if variant and variant != "thumb":
        raise orena_http_error(422, "media_asset_variant_invalid", "Unsupported media variant.")
    content_type = "image/jpeg" if variant == "thumb" else (mimetypes.guess_type(key)[0] or "application/octet-stream")
    return Response(
        content=payload,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.get("/my/{media_id}")
def open_my_media(media_id: str) -> dict[str, Any]:
    """Resolve one stored media identity into the learner-facing payload.

    Both a learner's own upload and an admin-imported shared source resolve
    here, because a learner does not care which shelf a file came from — the
    catalogue stays the same shape either way.
    """
    store, _, _ = _installed()
    entry = store.get(media_id.strip())
    if entry is None:
        raise orena_http_error(404, "media_not_found", "This media is not available.")
    if _learner_payload is None:
        raise orena_http_error(503, "media_library_unavailable", "The Media Library is not configured for this environment.")
    payload = _learner_payload(entry.media_id, "")
    if payload is None:
        raise orena_http_error(404, "media_not_found", "This media is not available.")
    return payload


@router.get("/admin/library")
def admin_library(request: Request, language: str = "") -> dict[str, Any]:
    """What the shared library currently holds, for an operator to verify."""
    _require_admin(request)
    store, _, _ = _installed()
    selected = language.strip().casefold() or None
    # An operator's listing, so every state: the one they came to look for is
    # usually the one that is no longer in front of learners.
    entries = [item for item in store.list(language=selected, status=None) if item.library == "shared"]
    return {
        "items": [_admin_entry(item) for item in entries],
        "counts": {"shared": len(entries)},
        "storage": {"read_issue": getattr(store, "last_read_issue", "")},
    }


def _admin_entry(entry: MediaLibraryEntry) -> dict[str, Any]:
    from writing_coach.media_source_import import public_thumbnail_url

    return {
        "media_id": entry.media_id,
        "lesson_id": str((entry.lesson or {}).get("lesson_id") or entry.media_id),
        "title": entry.title,
        "media_type": entry.media_type,
        "provider": entry.provider,
        "provider_media_id": entry.provider_media_id,
        "canonical_url": entry.canonical_url,
        "creator": entry.creator,
        "duration_ms": entry.duration_ms,
        "language": entry.language,
        "level": entry.level,
        "thumbnail_url": public_thumbnail_url(entry),
        "playback": dict(entry.playback),
        "library": entry.library,
        "created_at": entry.created_at,
        "imported_by": entry.source.get("imported_by", ""),
        "has_lesson": entry.lesson is not None,
    }


@router.post("/admin/preview")
def admin_preview(request: Request, payload: MediaPreviewIn) -> dict[str, Any]:
    """Resolve metadata for 1..N sources without persisting anything.

    One unusable URL answers as one `error` row. It never raises out of the
    batch, because an operator pasting ten links must not lose the nine that
    were fine to a typo in the tenth.
    """
    _require_admin(request)
    _, _, importer = _installed()
    language = _require_language(payload.language)
    items = [_preview_one(importer, url, language) for url in payload.urls]
    return {"items": items, "summary": _summary(items)}


def _preview_one(importer: MediaSourceImporter, url: str, language: str) -> dict[str, Any]:
    cleaned = str(url or "").strip()
    if not cleaned:
        return {"url": "", "status": "error", "detail": "Enter a media URL."}
    try:
        row = importer.preview(cleaned, language=language)
    except UnsafeMediaFetch as exc:
        return {"url": cleaned, "status": "error", "detail": str(exc)}
    except ValueError as exc:
        return {"url": cleaned, "status": "error", "detail": str(exc)}
    except Exception as exc:  # one bad source must not end the batch
        _logger.warning("media preview failed for %s: %s", cleaned, type(exc).__name__)
        return {"url": cleaned, "status": "error", "detail": "This media source could not be read."}
    return {"url": cleaned, **row}


@router.post("/admin/import")
def admin_import(request: Request, payload: MediaImportIn) -> dict[str, Any]:
    """Persist admin-supplied sources into the Shared Listening Library."""
    user = _require_admin(request)
    _, _, importer = _installed()
    language = _require_language(payload.language)
    imported_by = str(user.get("email") or user.get("name") or "admin")[:120]
    items = [item.model_dump() for item in payload.items]
    try:
        report = importer.import_urls(items, language=language, imported_by=imported_by)
    except Exception as exc:
        _logger.warning("media import failed: %s", type(exc).__name__)
        raise orena_http_error(503, "media_import_unavailable", "Media import is not available right now.") from exc
    rows = [
        {"url": item.url, "status": item.status, "detail": item.detail, "media_id": item.media_id, "lesson_id": item.lesson_id}
        for item in report.items
    ]
    return {"items": rows, "summary": _summary(rows)}


@router.post("/admin/upload")
async def admin_upload(
    request: Request,
    file: list[UploadFile] = File(default=[]),
    language: str = Form(default="en"),
) -> dict[str, Any]:
    """Import audio/video files an operator holds, into the shared library."""
    user = _require_admin(request)
    _, _, importer = _installed()
    selected = _require_language(language)
    imported_by = str(user.get("email") or user.get("name") or "admin")[:120]
    rows: list[dict[str, Any]] = []
    for upload in file or []:
        filename = Path(str(upload.filename or "upload")).name or "upload"
        try:
            with TempMediaFile(suffix=Path(filename).suffix or ".bin") as temp:
                await _stream_upload(upload, temp.path)
                entry = importer.import_upload(
                    temp.path, filename=filename, language=selected, imported_by=imported_by, library="shared"
                )
            rows.append({"url": filename, "status": "ok", "detail": "Imported.", "media_id": entry.media_id, "lesson_id": ""})
        except UnsafeMediaFetch as exc:
            rows.append({"url": filename, "status": "error", "detail": str(exc)})
        except ValueError as exc:
            rows.append({"url": filename, "status": "error", "detail": str(exc)})
        except Exception as exc:
            _logger.warning("media upload failed for %s: %s", filename, type(exc).__name__)
            rows.append({"url": filename, "status": "error", "detail": "This file could not be imported."})
    return {"items": rows, "summary": _summary(rows)}


@media_learning_router.post("/upload")
async def learner_upload(
    file: UploadFile = File(...),
    language: str = Form(default="en"),
    title: str = Form(default=""),
) -> dict[str, Any]:
    """A learner's own audio/video file, stored once and owned by them.

    No transcript is invented: without a transcript the encounter opens the
    existing 'source only' room and plays the file, which is the honest answer
    and the one the learner already sees for a caption-less provider source.
    """
    store, _, importer = _installed()
    if _learner_payload is None:
        raise orena_http_error(503, "media_library_unavailable", "The Media Library is not configured for this environment.")
    selected = _require_language(language, "learning language")
    filename = Path(str(file.filename or "upload")).name or "upload"
    try:
        with TempMediaFile(suffix=Path(filename).suffix or ".bin") as temp:
            await _stream_upload(file, temp.path)
            entry = importer.import_upload(
                temp.path,
                filename=filename,
                language=selected,
                imported_by="learner",
                library="personal",
                title=title.strip(),
            )
    except UnsafeMediaFetch as exc:
        raise orena_http_error(422, "media_upload_invalid", str(exc)) from exc
    except ValueError as exc:
        raise orena_http_error(422, "media_upload_invalid", str(exc)) from exc
    except Exception as exc:
        _logger.warning("learner upload failed for %s: %s", filename, type(exc).__name__)
        raise orena_http_error(503, "media_upload_unavailable", "This file could not be stored right now.") from exc
    payload = _learner_payload(entry.media_id, "")
    if payload is None:
        raise orena_http_error(503, "media_upload_unavailable", "This file could not be stored right now.")
    payload["media_id"] = entry.media_id
    return payload


async def _stream_upload(upload: UploadFile, destination: Path) -> None:
    """Read an upload with the byte budget enforced while reading, not after.

    `UploadFile` is already spooled by Starlette, but reading it whole into
    memory would let one oversized upload cost the process; the same
    MAX_UPLOAD_BYTES the thumbnail pipeline uses is applied per chunk here.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with destination.open("wb") as handle:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                handle.close()
                destination.unlink(missing_ok=True)
                raise UnsafeMediaFetch("This media file is too large.")
            handle.write(chunk)
    if total == 0:
        destination.unlink(missing_ok=True)
        raise ValueError("The uploaded file is empty.")


def _summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total": len(rows),
        "ok": sum(1 for row in rows if row.get("status") == "ok"),
        "error": sum(1 for row in rows if row.get("status") != "ok"),
    }


# `_installed` is used by app.py's smoke check and by tests; keep the name
# stable and explicit rather than exposing the globals directly.
def media_library_installed() -> bool:
    return _store is not None and _asset_store is not None and _importer is not None


# ---------------------------------------------------------------------------
# Resolution: one stored entry → the payload the encounter already renders
# ---------------------------------------------------------------------------


def find_entry(media_id: str) -> MediaLibraryEntry | None:
    """Look up one stored entry, or `None`. Never provider-backed."""
    if _store is None:
        return None
    cleaned = str(media_id or "").strip()
    if not cleaned or "/" in cleaned:
        return None
    return _store.get(cleaned)


def entry_lesson_id(entry: MediaLibraryEntry) -> str:
    lesson = entry.lesson or {}
    value = lesson.get("lesson_id")
    return str(value) if isinstance(value, str) else ""


def browse_item(entry: MediaLibraryEntry) -> dict[str, Any]:
    """One card's truth, and nothing the encounter owns.

    No description: a library is browsed by image and title, and prose belongs to
    the detail view. `id` is the encounter locator, so an imported item opens
    through exactly the route a curated lesson opens through.
    """
    from writing_coach.media_source_import import playback_for, public_thumbnail_url, source_label

    thumbnail = public_thumbnail_url(entry)
    return {
        "id": f"media:{entry.media_id}",
        "media_id": entry.media_id,
        "lesson_id": entry_lesson_id(entry),
        "title": entry.title,
        "language": entry.language,
        "level": entry.level,
        "duration_ms": entry.duration_ms,
        "media_type": entry.media_type,
        "kind": entry.media_type,
        "provider": entry.provider,
        "source_label": source_label(entry),
        "creator": entry.creator,
        "thumbnail_url": thumbnail,
        "topic": str((entry.lesson or {}).get("topic") or ""),
        "tags": [str(tag) for tag in ((entry.lesson or {}).get("tags") or [])],
        "origin": "imported",
        "source_kind": "library",
        "created_at": entry.created_at,
    }


def shared_browse_items(language: str) -> list[dict[str, Any]]:
    """Everything an administrator has published for one learning language."""
    if _store is None:
        return []
    selected = str(language or "").strip().casefold()
    if not selected:
        return []
    return [
        browse_item(entry)
        for entry in _store.list(language=selected, library="shared")
    ]


def _catalog_metadata(entry: MediaLibraryEntry, thumbnail: str) -> dict[str, Any]:
    lesson = entry.lesson or {}
    source = {
        "provider": entry.provider,
        "creator": entry.creator,
        "provenance_url": entry.canonical_url,
        "license": "Provider-hosted media; review provider terms before publishing."
        if entry.canonical_url
        else "File supplied to Orena.",
        "type": "youtube" if entry.provider == "youtube" else entry.provider,
    }
    duration = entry.duration_ms or 0
    return {
        "lesson_id": entry_lesson_id(entry) or entry.media_id,
        "title": entry.title,
        "topic": str(lesson.get("topic") or ""),
        "subtopics": [],
        "level": entry.level,
        "level_source": "editorial-review" if entry.level else "",
        "duration_ms": duration,
        "excerpt_start_ms": 0,
        "excerpt_end_ms": duration,
        "available_modes": ["listen"],
        "content_tags": [str(tag) for tag in (lesson.get("tags") or [])],
        "pinyin_by_segment": {},
        "poster_url": thumbnail,
        "source": source,
    }


def resolve_learner_payload(media_id: str, support_language: str = "") -> dict[str, Any] | None:
    """A stored entry as the one payload the encounter renders.

    The acquisition was serialized when the source was imported, so opening an
    imported item costs no provider request and cannot re-scrape by browsing.
    A source imported without captions still opens and plays; it simply has no
    transcript to follow, which is what the encounter's source-only room already
    expresses. `support_language` is accepted because the caller owns it, and is
    unused here because an imported source has no pre-authored meanings yet.
    """
    from writing_coach.media_source_import import playback_for, public_thumbnail_url

    entry = find_entry(media_id)
    if entry is None:
        return None
    thumbnail = public_thumbnail_url(entry)
    stored = (entry.lesson or {}).get("payload")
    if isinstance(stored, Mapping) and isinstance(stored.get("asset"), Mapping):
        payload: dict[str, Any] = {**stored, "asset": dict(stored["asset"])}
    else:
        payload = {
            "asset": {
                "asset_id": entry.media_id,
                "source_url": entry.canonical_url,
                "source_provider": entry.provider,
                "source_type": entry.media_type,
                "title": entry.title,
                "source_language": entry.language,
                "processing_state": "ready",
                "duration_ms": entry.duration_ms,
                "transcript_available": False,
                "translation_available": False,
            },
            "transcript": None,
            "transcript_origin": None,
            "translations": [],
        }
    payload["asset"]["thumbnail_url"] = thumbnail
    payload["playback"] = playback_for(entry)
    payload["catalog"] = _catalog_metadata(entry, thumbnail)
    payload["media_id"] = entry.media_id
    return payload


def resolve_by_lesson_id(lesson_id: str) -> dict[str, Any] | None:
    """Resolve an imported item the encounter was handed as `media:<lesson_id>`."""
    preferred = find_entry(lesson_id)
    if preferred is not None and entry_lesson_id(preferred) == lesson_id:
        return resolve_learner_payload(preferred.media_id, "")
    if _store is None:
        return None
    for entry in _store.list(library="shared"):
        if entry_lesson_id(entry) == lesson_id:
            return resolve_learner_payload(entry.media_id, "")
    return None
