"""Reading Library catalog repository - `reading_books` / `reading_book_chapters`.

Schema: `migrations/versions/20260916_0009_reading_library.py` - reviewed
(three rounds, APPROVED), human-authorized, applied to the sandbox runtime
only. See `docs/project/READING_LIBRARY_SCHEMA_REVIEW_REQUEST.md`.

Division of responsibility: this file only reads/writes rows that already
represent a fully valid, fully stored book - it never decides whether an
EPUB is usable (`writing_coach.epub_import` does that) and never writes or
deletes asset bytes (`writing_coach.book_asset_store` does that). Ordering
"assets first, then this transaction" so a `reading_books` row never
references a key that was not actually written is the caller's
responsibility (`writing_coach/reading_library_api.py`), not this module's.

`reading_books.id` and `reading_book_chapters.id` are the stable identities a
learner-facing locator (a future I4 `ContentMembership.sourceRef`, reading
position, highlight...) is meant to reference. `position` is display order
only and must never be treated as identity - it can change on a future
re-import without invalidating anything that recorded a chapter `id`.
`content_revision` exists for the same reason: absent today (re-import is out
of this round's scope), it lets a future locator detect "this reference was
captured against an older revision" instead of silently reading the wrong
content.
"""
from __future__ import annotations

import base64
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

DEFAULT_PAGE_LIMIT = 24
MAX_PAGE_LIMIT = 60


@dataclass(frozen=True)
class ChapterInput:
    chapter_key: str
    title: str
    content_asset_key: str
    word_count: int


class InvalidCursor(ValueError):
    """A `cursor` value that does not decode to this query's own shape."""


def _encode_cursor(created_at: datetime, book_id: str) -> str:
    payload = json.dumps({"created_at": created_at.isoformat(), "id": book_id}).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii")


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")))
        return datetime.fromisoformat(payload["created_at"]), str(payload["id"])
    except Exception as exc:  # noqa: BLE001 - any malformed cursor is the same outcome
        raise InvalidCursor(cursor) from exc


def _as_uuid(value: str) -> uuid.UUID | None:
    """The identity a row can actually have, or nothing.

    `reading_books.id` and `reading_book_chapters.id` are `uuid` columns, so a
    string that is not a UUID cannot name a row - PostgreSQL does not treat it
    as a miss, it raises `InvalidTextRepresentation` and the request becomes a
    500. A learner can arrive with such an id: the Library's own cards carry
    routing identities like `text:book-probe`. Parsing here turns "cannot name
    a row" into "found nothing", which is what it means, and keeps the
    malformed value away from the query entirely.
    """
    try:
        return uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError):
        return None


class PostgresReadingLibraryRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get_book_by_hash(self, source_hash: str) -> dict[str, Any] | None:
        """Optimization only, not the correctness boundary - see `create_book()`.
        Lets a caller skip parsing/writing assets for an exact re-upload
        before doing either, without a race: the `UNIQUE (source_hash)`
        constraint plus `create_book()`'s `ON CONFLICT` is what actually
        prevents a duplicate row even if two callers both pass this check."""
        with self._engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT id, title, chapter_count FROM reading_books "
                    "WHERE source_hash = :hash AND status = 'ready'"
                ),
                {"hash": source_hash},
            ).mappings().first()
        if row is None:
            return None
        return {"id": str(row["id"]), "title": row["title"], "chapter_count": row["chapter_count"]}

    def create_book(
        self,
        *,
        book_id: uuid.UUID,
        title: str,
        author: str,
        description: str,
        learning_language: str,
        source_kind: str,
        source_hash: str,
        cover_asset_key: str | None,
        original_asset_key: str,
        imported_by: str,
        chapters: list[ChapterInput],
    ) -> dict[str, Any]:
        """`book_id` is supplied by the caller, never generated here: the
        caller (`writing_coach/reading_library_api.py`) must mint the id
        before writing any asset, so every `content_asset_key`/`cover_asset_key`
        it passes in already embeds the same id this transaction stores.

        Returns `{"duplicate": True, ...the existing book...}` when
        `source_hash` already belongs to a `'ready'` book - the exact bytes
        were imported before, so this attempt's already-written assets are
        the caller's to clean up; nothing here writes a second row for them.
        """
        if not chapters:
            raise ValueError("A book must have at least one chapter.")
        now = datetime.now(UTC)
        word_count = sum(chapter.word_count for chapter in chapters)
        with self._engine.begin() as connection:
            inserted_id = connection.execute(
                text(
                    "INSERT INTO reading_books "
                    "(id, title, author, description, learning_language, source_kind, source_hash, "
                    "status, chapter_count, content_revision, cover_asset_key, original_asset_key, "
                    "word_count, imported_by, created_at, updated_at) "
                    "VALUES (:id, :title, :author, :description, :language, :source_kind, :source_hash, "
                    "'ready', :chapter_count, 1, :cover_key, :original_key, :word_count, :imported_by, :now, :now) "
                    # Targets the partial index (status = 'ready' rows only) -
                    # an archived book's hash never conflicts, so re-importing
                    # the same file after archiving succeeds.
                    "ON CONFLICT (source_hash) WHERE status = 'ready' DO NOTHING RETURNING id"
                ),
                {
                    "id": book_id, "title": title, "author": author, "description": description,
                    "language": learning_language, "source_kind": source_kind, "source_hash": source_hash,
                    "chapter_count": len(chapters), "cover_key": cover_asset_key,
                    "original_key": original_asset_key, "word_count": word_count,
                    "imported_by": imported_by, "now": now,
                },
            ).scalar_one_or_none()
            if inserted_id is None:
                existing = connection.execute(
                    text(
                        "SELECT id, title, chapter_count FROM reading_books "
                        "WHERE source_hash = :hash AND status = 'ready'"
                    ),
                    {"hash": source_hash},
                ).mappings().first()
                return {
                    "duplicate": True,
                    "id": str(existing["id"]), "title": existing["title"],
                    "chapter_count": existing["chapter_count"],
                }
            for position, chapter in enumerate(chapters):
                connection.execute(
                    text(
                        "INSERT INTO reading_book_chapters "
                        "(id, book_id, position, chapter_key, title, content_asset_key, word_count, created_at) "
                        "VALUES (:id, :book_id, :position, :chapter_key, :title, :asset_key, :word_count, :now)"
                    ),
                    {
                        "id": uuid.uuid4(), "book_id": book_id, "position": position,
                        "chapter_key": chapter.chapter_key, "title": chapter.title,
                        "asset_key": chapter.content_asset_key, "word_count": chapter.word_count,
                        "now": now,
                    },
                )
        return {"duplicate": False, "id": str(book_id), "title": title, "chapter_count": len(chapters)}

    def archive_book(self, book_id: str) -> bool:
        """Admin recovery path for a wrong/duplicate import, without raw SQL.
        Sets `status='archived'` so it stops appearing in `list_books()`/
        `get_book()` (both already filter `status = 'ready'`); never deletes
        the row or its assets. Returns whether a `'ready'` row was found."""
        identity = _as_uuid(book_id)
        if identity is None:
            return False
        with self._engine.begin() as connection:
            updated_id = connection.execute(
                text(
                    "UPDATE reading_books SET status = 'archived', updated_at = :now "
                    "WHERE id = :id AND status = 'ready' RETURNING id"
                ),
                {"id": identity, "now": datetime.now(UTC)},
            ).scalar_one_or_none()
        return updated_id is not None

    def list_books(
        self, *, learning_language: str, cursor: str | None = None, limit: int = DEFAULT_PAGE_LIMIT
    ) -> dict[str, Any]:
        bounded_limit = max(1, min(int(limit), MAX_PAGE_LIMIT))
        params: dict[str, Any] = {"language": learning_language, "limit": bounded_limit + 1}
        cursor_clause = ""
        if cursor:
            after_created_at, after_id = _decode_cursor(cursor)
            cursor_clause = (
                " AND (created_at, id) < (:after_created_at, :after_id)"
            )
            params["after_created_at"] = after_created_at
            params["after_id"] = after_id
        with self._engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT id, title, author, learning_language, cover_asset_key, "
                    "chapter_count, word_count, created_at "
                    "FROM reading_books "
                    "WHERE status = 'ready' AND learning_language = :language" + cursor_clause + " "
                    "ORDER BY created_at DESC, id DESC LIMIT :limit"
                ),
                params,
            ).mappings().all()
        page = rows[:bounded_limit]
        next_cursor = (
            _encode_cursor(page[-1]["created_at"], str(page[-1]["id"]))
            if len(rows) > bounded_limit
            else None
        )
        return {
            "items": [
                {
                    "id": str(row["id"]), "title": row["title"], "author": row["author"],
                    "learning_language": row["learning_language"],
                    "cover_asset_key": row["cover_asset_key"],
                    "chapter_count": row["chapter_count"], "word_count": row["word_count"],
                }
                for row in page
            ],
            "next_cursor": next_cursor,
        }

    def get_book(self, book_id: str) -> dict[str, Any] | None:
        identity = _as_uuid(book_id)
        if identity is None:
            return None
        with self._engine.connect() as connection:
            book = connection.execute(
                text(
                    "SELECT id, title, author, description, learning_language, cover_asset_key, "
                    "chapter_count, word_count, content_revision, created_at "
                    "FROM reading_books WHERE id = :id AND status = 'ready'"
                ),
                {"id": identity},
            ).mappings().first()
            if book is None:
                return None
            chapters = connection.execute(
                text(
                    "SELECT id, position, title, word_count FROM reading_book_chapters "
                    "WHERE book_id = :id ORDER BY position ASC"
                ),
                {"id": identity},
            ).mappings().all()
        return {
            "id": str(book["id"]), "title": book["title"], "author": book["author"],
            "description": book["description"], "learning_language": book["learning_language"],
            "cover_asset_key": book["cover_asset_key"], "chapter_count": book["chapter_count"],
            "word_count": book["word_count"], "content_revision": book["content_revision"],
            "chapters": [
                {
                    "id": str(chapter["id"]), "position": chapter["position"],
                    "title": chapter["title"], "word_count": chapter["word_count"],
                }
                for chapter in chapters
            ],
        }

    def get_chapter(self, book_id: str, chapter_id: str) -> dict[str, Any] | None:
        book_identity, chapter_identity = _as_uuid(book_id), _as_uuid(chapter_id)
        if book_identity is None or chapter_identity is None:
            return None
        with self._engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT c.id, c.position, c.title, c.content_asset_key, "
                    "b.title AS book_title, b.author, b.learning_language, b.content_revision "
                    "FROM reading_book_chapters c "
                    "JOIN reading_books b ON b.id = c.book_id "
                    "WHERE c.book_id = :book_id AND c.id = :chapter_id AND b.status = 'ready'"
                ),
                {"book_id": book_identity, "chapter_id": chapter_identity},
            ).mappings().first()
        return dict(row) if row else None
