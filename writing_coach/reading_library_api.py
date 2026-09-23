"""HTTP boundary for the Shared Reading Library - admin EPUB import, and the
learner-facing catalog/chapter reads.

Failure semantics (assets vs. database row): every asset for a book is
written to the `BookAssetStore` *before* `reading_library_repository.
create_book()` runs, and the book id used to build every asset key is minted
here, before any write, so the eventual database row can only ever reference
keys that already exist. If the database transaction itself fails after
assets were written, `_import_one` best-effort deletes exactly the keys it
just wrote (`BookAssetStore.delete` is idempotent) - the row was never
created, so nothing else can reference the orphaned bytes; a stray filesystem
object with no database row is inert, never served, and safe to leave for a
future cleanup pass rather than something this request path must guarantee
synchronously.

Every EPUB parse failure and every storage failure is reported per-file in
one batch response (`status: 'ok' | 'error'`) - one bad file in a batch never
aborts the files after it.

The learner reads carry one derived field the repository does not store:
`reading_time_seconds`, on the book and on each chapter, computed from the
`word_count` that is already there at the pace `reading_processing` already
defines for a learner. It is a projection, not a column: nothing is written,
and the import path above is untouched by it.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Any
from collections.abc import Callable

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from sqlalchemy.exc import ProgrammingError

from writing_coach.book_asset_store import AssetNotFound, BookAssetStore
from writing_coach.core.errors import orena_http_error
from writing_coach import reading_processing
from writing_coach.epub_import import COVER_CONTENT_TYPES, MAX_EPUB_BYTES, EpubImportError, parse_epub
from writing_coach.persistence.reading_library_repository import (
    ChapterInput,
    InvalidCursor,
    PostgresReadingLibraryRepository,
)

router = APIRouter(prefix="/api/reading/library", tags=["reading-library"])

_repository: PostgresReadingLibraryRepository | None = None
_asset_store: BookAssetStore | None = None
_admin_guard: Callable[[Request], dict[str, Any]] | None = None
_language_supported: Callable[[str], bool] | None = None

MAX_IMPORT_FILES = 20
_UPLOAD_READ_CHUNK_BYTES = 1024 * 1024
_CONTENT_TYPE_BY_EXTENSION = {ext: content_type for content_type, ext in COVER_CONTENT_TYPES.items()}

_logger = logging.getLogger(__name__)


def configure_reading_library(
    repository: PostgresReadingLibraryRepository | None,
    asset_store: BookAssetStore | None,
    *,
    admin_guard: Callable[[Request], dict[str, Any]],
    language_supported: Callable[[str], bool],
) -> None:
    global _repository, _asset_store, _admin_guard, _language_supported
    _repository = repository
    _asset_store = asset_store
    _admin_guard = admin_guard
    _language_supported = language_supported


def _require_backend() -> tuple[PostgresReadingLibraryRepository, BookAssetStore]:
    if _repository is None or _asset_store is None:
        raise orena_http_error(
            503, "reading_library_unavailable", "The Reading Library is not configured for this deployment."
        )
    return _repository, _asset_store


def _require_language(raw: str) -> str:
    language = (raw or "").strip().casefold()
    if not language or _language_supported is None or not _language_supported(language):
        raise orena_http_error(422, "reading_library_invalid_language", "Unsupported learning language.")
    return language


def _call_repository(fn: Callable[[], Any]) -> Any:
    """Run one repository read, turning "configured but the reviewed schema
    is not applied yet" into the same 503 `_require_backend()` already
    answers with when the repository is not configured at all - a learner
    sees one truthful "temporarily unavailable", never a raw database
    traceback, whichever of those two states this deployment is actually in.
    """
    try:
        return fn()
    except ProgrammingError as exc:
        _logger.warning("reading library: schema not ready for a repository read", exc_info=True)
        raise orena_http_error(
            503, "reading_library_unavailable", "The Reading Library is not available yet."
        ) from exc


async def _read_upload_limited(file: UploadFile, *, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_UPLOAD_READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise EpubImportError("archive_too_large", "upload exceeds the maximum EPUB size")
        chunks.append(chunk)
    return b"".join(chunks)


async def _import_one(
    upload: UploadFile,
    *,
    language: str,
    imported_by: str,
    repository: PostgresReadingLibraryRepository,
    asset_store: BookAssetStore,
) -> dict[str, Any]:
    filename = upload.filename or "book.epub"
    try:
        data = await _read_upload_limited(upload, max_bytes=MAX_EPUB_BYTES)
    except EpubImportError as exc:
        return {"filename": filename, "status": "error", "category": exc.category}

    source_hash = hashlib.sha256(data).hexdigest()
    try:
        # Optimization only - skip parsing/writing assets for an exact
        # re-upload. Not the correctness boundary; create_book()'s UNIQUE
        # constraint is, and still applies below even if this check races.
        existing = _call_repository(lambda: repository.get_book_by_hash(source_hash))
    except HTTPException:
        existing = None  # schema not ready yet; let create_book() below report it the same way
    if existing is not None:
        return {
            "filename": filename, "status": "duplicate", "book_id": existing["id"],
            "title": existing["title"], "chapter_count": existing["chapter_count"],
        }

    try:
        parsed = parse_epub(data)
    except EpubImportError as exc:
        return {"filename": filename, "status": "error", "category": exc.category}
    except Exception:  # noqa: BLE001 - never leak a raw parser traceback to the client
        _logger.warning("reading library import: unexpected parse failure for %s", filename, exc_info=True)
        return {"filename": filename, "status": "error", "category": "import_failed"}

    book_id = uuid.uuid4()
    written_keys: list[str] = []
    try:
        original_key = f"books/{book_id}/original.epub"
        asset_store.put(original_key, data)
        written_keys.append(original_key)

        cover_key = None
        if parsed.cover is not None:
            extension = COVER_CONTENT_TYPES.get(parsed.cover.content_type)
            if extension:
                cover_key = f"books/{book_id}/cover{extension}"
                asset_store.put(cover_key, parsed.cover.data)
                written_keys.append(cover_key)

        chapter_inputs: list[ChapterInput] = []
        for index, chapter in enumerate(parsed.chapters):
            content_key = f"books/{book_id}/chapters/{index}.json"
            asset_store.put(
                content_key,
                json.dumps(
                    {"format": 2, "blocks": list(chapter.blocks), "paragraphs": list(chapter.paragraphs)}
                ).encode("utf-8"),
            )
            written_keys.append(content_key)
            chapter_inputs.append(
                ChapterInput(
                    chapter_key=chapter.chapter_key,
                    title=chapter.title,
                    content_asset_key=content_key,
                    word_count=chapter.word_count,
                )
            )

        manifest_key = f"books/{book_id}/manifest.json"
        written_keys.append(manifest_key)
        asset_store.put(
            manifest_key,
            json.dumps({"format": 2, "provenance": parsed.provenance}).encode("utf-8"),
        )

        book = repository.create_book(
            book_id=book_id,
            title=parsed.title,
            author=parsed.author,
            description=parsed.description,
            learning_language=language,
            source_kind="epub",
            source_hash=source_hash,
            cover_asset_key=cover_key,
            original_asset_key=original_key,
            imported_by=imported_by,
            chapters=chapter_inputs,
        )
    except ProgrammingError:
        _logger.warning("reading library import: schema not ready for %s", filename, exc_info=True)
        for key in written_keys:
            try:
                asset_store.delete(key)
            except Exception:  # noqa: BLE001 - best-effort cleanup must not itself raise
                _logger.warning("reading library import: cleanup failed for %s", key, exc_info=True)
        return {"filename": filename, "status": "error", "category": "reading_library_unavailable"}
    except Exception:  # noqa: BLE001 - roll back the assets this attempt wrote, report, move on
        _logger.warning("reading library import: storage failure for %s", filename, exc_info=True)
        for key in written_keys:
            try:
                asset_store.delete(key)
            except Exception:  # noqa: BLE001 - best-effort cleanup must not itself raise
                _logger.warning("reading library import: cleanup failed for %s", key, exc_info=True)
        return {"filename": filename, "status": "error", "category": "storage_failed"}

    if book["duplicate"]:
        # Lost the race against a concurrent upload of the same bytes between
        # the pre-check above and this transaction; this attempt's own assets
        # (already written) are orphaned, never referenced - clean them up.
        for key in written_keys:
            try:
                asset_store.delete(key)
            except Exception:  # noqa: BLE001 - best-effort cleanup must not itself raise
                _logger.warning("reading library import: cleanup failed for %s", key, exc_info=True)
        return {
            "filename": filename, "status": "duplicate", "book_id": book["id"],
            "title": book["title"], "chapter_count": book["chapter_count"],
        }

    return {
        "filename": filename, "status": "ok", "book_id": book["id"],
        "title": book["title"], "chapter_count": book["chapter_count"],
    }


@router.post("/import")
async def import_books(
    request: Request,
    files: list[UploadFile] = File(...),
    learning_language: str = Form(...),
) -> dict[str, Any]:
    admin = _admin_guard(request) if _admin_guard else {}
    repository, asset_store = _require_backend()
    language = _require_language(learning_language)
    if not files:
        raise orena_http_error(422, "reading_library_no_files", "Select at least one EPUB file.")
    if len(files) > MAX_IMPORT_FILES:
        raise orena_http_error(
            422, "reading_library_too_many_files", f"Import at most {MAX_IMPORT_FILES} files at a time."
        )
    imported_by = str(admin.get("email") or admin.get("google_sub") or "admin")
    results = [
        await _import_one(
            upload, language=language, imported_by=imported_by, repository=repository, asset_store=asset_store
        )
        for upload in files
    ]
    return {"results": results}


def reading_seconds(word_count: object, learning_language: str) -> int:
    """How long `word_count` takes a learner, at the pace the product uses.

    Chinese is counted in characters and English in words, which is why the
    pace differs; anything else is read at the English pace rather than being
    refused, because a rough duration is more use to a learner than none and
    the alternative is a blank where the frame draws a number.
    """

    try:
        count = int(word_count or 0)
    except (TypeError, ValueError):
        return 0
    if count <= 0:
        return 0
    per_minute = (
        reading_processing.ZH_CHARS_PER_MINUTE
        if str(learning_language or "").strip().casefold().startswith("zh")
        else reading_processing.EN_WORDS_PER_MINUTE
    )
    return int(round(count / per_minute * 60))


def _with_reading_time(book: dict[str, Any]) -> dict[str, Any]:
    """The same book, with the duration the frames draw.

    A learner projection: the repository stores none of this, and the admin
    import path never sees it.
    """

    language = str(book.get("learning_language") or "")
    projected = dict(book)
    projected["reading_time_seconds"] = reading_seconds(book.get("word_count"), language)
    chapters = book.get("chapters")
    if isinstance(chapters, list):
        projected["chapters"] = [
            {**chapter, "reading_time_seconds": reading_seconds(chapter.get("word_count"), language)}
            for chapter in chapters
            if isinstance(chapter, dict)
        ]
    return projected


@router.get("/books")
def list_books(learning_language: str, cursor: str | None = None, limit: int = 24) -> dict[str, Any]:
    repository, _asset = _require_backend()
    language = _require_language(learning_language)
    try:
        return _call_repository(
            lambda: repository.list_books(learning_language=language, cursor=cursor, limit=limit)
        )
    except InvalidCursor as exc:
        raise orena_http_error(422, "reading_library_invalid_cursor", "Invalid pagination cursor.") from exc


@router.get("/books/{book_id}")
def get_book(book_id: str) -> dict[str, Any]:
    repository, asset_store = _require_backend()
    book = _call_repository(lambda: repository.get_book(book_id))
    if book is None:
        raise HTTPException(404, "Book not found.")
    response = _with_reading_time(book)
    response["provenance"] = None
    try:
        manifest = json.loads(asset_store.get(f"books/{book_id}/manifest.json"))
        provenance = manifest.get("provenance") if isinstance(manifest, dict) else None
        if isinstance(provenance, dict):
            response["provenance"] = provenance
    except Exception:  # noqa: BLE001 - provenance is optional metadata, never a book-read blocker
        pass
    return response


@router.get("/books/{book_id}/chapters/{chapter_id}")
def get_chapter(book_id: str, chapter_id: str) -> dict[str, Any]:
    repository, asset_store = _require_backend()
    chapter = _call_repository(lambda: repository.get_chapter(book_id, chapter_id))
    if chapter is None:
        raise HTTPException(404, "Chapter not found.")
    try:
        raw = asset_store.get(chapter["content_asset_key"])
        payload = json.loads(raw)
        paragraphs = payload["paragraphs"]
        blocks = payload.get("blocks")
        if not isinstance(blocks, list):
            blocks = [{"type": "paragraph", "text": paragraph} for paragraph in paragraphs]
    except (AssetNotFound, json.JSONDecodeError, KeyError, TypeError, AttributeError) as exc:
        raise orena_http_error(503, "reading_library_chapter_unavailable", "Chapter content is unavailable.") from exc
    return {
        "id": str(chapter["id"]),
        "book_id": book_id,
        "title": chapter["title"],
        "book_title": chapter["book_title"],
        "author": chapter["author"],
        "language": chapter["learning_language"],
        "position": chapter["position"],
        "content_revision": chapter["content_revision"],
        "blocks": blocks,
        "paragraphs": paragraphs,
    }


@router.get("/books/{book_id}/cover", include_in_schema=False)
def get_cover(book_id: str, request: Request) -> Response:
    repository, asset_store = _require_backend()
    book = _call_repository(lambda: repository.get_book(book_id))
    cover_key = book.get("cover_asset_key") if book else None
    if not cover_key:
        raise HTTPException(404, "Cover not found.")
    extension = "." + cover_key.rsplit(".", 1)[-1] if "." in cover_key else ""
    content_type = _CONTENT_TYPE_BY_EXTENSION.get(extension, "application/octet-stream")
    try:
        data = asset_store.get(cover_key)
    except AssetNotFound as exc:
        raise HTTPException(404, "Cover not found.") from exc
    etag = '"' + hashlib.md5(data).hexdigest() + '"'
    headers = {"Cache-Control": "no-cache", "ETag": etag}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=data, media_type=content_type, headers=headers)


@router.post("/books/{book_id}/archive")
def archive_book(book_id: str, request: Request) -> dict[str, Any]:
    """Admin recovery for a wrong or duplicate import - hides the book from
    every learner-facing read without deleting its row or assets (see
    `PostgresReadingLibraryRepository.archive_book`)."""
    if _admin_guard:
        _admin_guard(request)
    repository, _asset = _require_backend()
    archived = _call_repository(lambda: repository.archive_book(book_id))
    if not archived:
        raise HTTPException(404, "Book not found.")
    return {"archived": True, "id": book_id}
