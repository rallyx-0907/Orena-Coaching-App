"""PostgreSQL authority for media metadata (D-108.5; docs/project/proposals/MEDIA_METADATA_POSTGRES.md rev 2).

NOT WIRED. `app.py` still constructs `FileMediaLibraryStore`; this module exists so the rehearsal
(`scripts/rehearse_media_metadata_schema.py`) and the tests exercise the real code against the proposed schema
(`migrations/proposed/20261001_0024_media_entries.py`). Cutover is a separate, human-gated step (proposal section 6).

The surface is the `MediaLibraryStore` protocol (`list`, `get`, `upsert`, `delete`) plus what the file cannot answer:
keyset-paged listings, a status-only update, the owner's uploaded bytes and the atomic quota insert. Rules from the
proposal that live here:

- `get` is head-only unless asked for the payload (the files route needs visibility, not a 150 KB transcript);
- `upsert` never changes `library` or `owner_token` of an existing row and never changes `created_at`;
- delete, sweep and quota paths RAISE on a database error (`MediaStoreUnavailable`), never "not found";
- the quota is checked in the inserting transaction under `pg_advisory_xact_lock(hashtextextended(owner_token, 0))`;
- nothing here reads or writes `index.json`, and nothing falls back to it.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, InterfaceError, OperationalError

from writing_coach.media_library_store import (
    LEGACY_OWNER_KEY,
    OWNER_FIELD,
    MediaLibraryEntry,
    owner_token,
    validate_entry,
)

LEGACY_OWNER_TOKEN = owner_token(LEGACY_OWNER_KEY)
PAGE_DEFAULT = 24
PAGE_MAX = 50


class MediaStoreUnavailable(RuntimeError):
    """The database could not answer. Delete, sweep and quota paths surface this; they never conclude "not found"."""


class MediaEntryConflict(RuntimeError):
    """An upsert would change `library` or `owner_token` of an existing row, or a shared `lesson_id` already names
    another entry. Refused, never applied."""


class MediaQuotaExceeded(RuntimeError):
    def __init__(self, used: int, adding: int, limit: int):
        super().__init__(f"{used} + {adding} > {limit}")
        self.used, self.adding, self.limit = used, adding, limit


def _parse_created(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _format_created(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def owner_of(entry: MediaLibraryEntry) -> str | None:
    """The explicit owner token of a row: the entry's recorded owner, the legacy token for an unowned personal row
    (today's implicit rule made explicit), None for a shared row."""
    if entry.library != "personal":
        return None
    return str(entry.source.get(OWNER_FIELD, "")) or LEGACY_OWNER_TOKEN


def lesson_parts(entry: MediaLibraryEntry) -> dict[str, Any]:
    """The lesson split for storage: `meta` is the lesson WITHOUT its payload, verbatim; lesson_id/topic/tags are derived
    from it for queries; the payload (when present) goes to its own table."""
    lesson = entry.lesson if isinstance(entry.lesson, Mapping) else None
    if lesson is None:
        return {"meta": None, "lesson_id": None, "topic": "", "tags": [], "has_lesson": False, "segment_count": 0, "payload": None}
    meta = {key: value for key, value in lesson.items() if key != "payload"}
    payload = lesson.get("payload") if "payload" in lesson else None
    if "payload" in lesson and not isinstance(payload, Mapping):
        raise ValueError("lesson.payload must be an object")
    segments = ((payload or {}).get("transcript") or {}).get("segments") if payload is not None else None
    return {
        "meta": meta,
        "lesson_id": str(meta["lesson_id"]) if meta.get("lesson_id") else None,
        "topic": str(meta.get("topic") or ""),
        "tags": [str(tag) for tag in (meta.get("tags") or [])],
        "has_lesson": True,
        "segment_count": len(segments) if isinstance(segments, list) else 0,
        "payload": payload,
    }


def entry_to_row(entry: MediaLibraryEntry, *, stored_bytes: int | None = None) -> dict[str, Any]:
    validate_entry(entry)
    parts = lesson_parts(entry)
    now = datetime.now(UTC)
    return {
        "media_id": entry.media_id,
        "library": entry.library,
        "status": entry.status,
        "media_type": entry.media_type,
        "provider": entry.provider,
        "provider_media_id": entry.provider_media_id,
        "canonical_url": entry.canonical_url,
        "title": entry.title,
        "creator": entry.creator,
        "duration_ms": entry.duration_ms,
        "language": entry.language,
        "level": entry.level,
        "playback": json.dumps(dict(entry.playback), ensure_ascii=False),
        "thumbnail_kind": entry.thumbnail["kind"],
        "thumbnail_ref": entry.thumbnail["ref"],
        "source": json.dumps(dict(entry.source), ensure_ascii=False),
        "owner_token": owner_of(entry),
        "lesson_meta": json.dumps(parts["meta"], ensure_ascii=False) if parts["meta"] is not None else None,
        "lesson_id": parts["lesson_id"],
        "topic": parts["topic"],
        "tags": json.dumps(parts["tags"], ensure_ascii=False),
        "has_lesson": parts["has_lesson"],
        "segment_count": parts["segment_count"],
        "stored_bytes": stored_bytes,
        "created_at": _parse_created(entry.created_at),
        "updated_at": now,
        "payload": json.dumps(parts["payload"], ensure_ascii=False) if parts["payload"] is not None else None,
    }


_HEAD_COLUMNS = (
    "media_id, library, status, media_type, provider, provider_media_id, canonical_url, title, creator, duration_ms, "
    "language, level, playback, thumbnail_kind, thumbnail_ref, source, owner_token, lesson_meta, lesson_id, topic, tags, "
    "has_lesson, segment_count, stored_bytes, created_at"
)


def row_to_entry(row: Mapping[str, Any], payload: Mapping[str, Any] | None = None) -> MediaLibraryEntry:
    lesson: dict[str, Any] | None = None
    if row["has_lesson"]:
        lesson = dict(row["lesson_meta"] or {})
        if payload is not None:
            lesson["payload"] = payload
    return MediaLibraryEntry(
        media_id=row["media_id"],
        media_type=row["media_type"],
        provider=row["provider"],
        provider_media_id=row["provider_media_id"],
        canonical_url=row["canonical_url"],
        playback=dict(row["playback"]),
        title=row["title"],
        thumbnail={"kind": row["thumbnail_kind"], "ref": row["thumbnail_ref"]},
        duration_ms=int(row["duration_ms"]),
        language=row["language"],
        level=row["level"],
        creator=row["creator"],
        source=dict(row["source"]),
        library=row["library"],
        created_at=_format_created(row["created_at"]),
        lesson=lesson,
        status=row["status"],
    )


_UPSERT = text(
    """
    INSERT INTO media_entries (media_id, library, status, media_type, provider, provider_media_id, canonical_url, title,
        creator, duration_ms, language, level, playback, thumbnail_kind, thumbnail_ref, source, owner_token, lesson_meta,
        lesson_id, topic, tags, has_lesson, segment_count, stored_bytes, created_at, updated_at)
    VALUES (:media_id, :library, :status, :media_type, :provider, :provider_media_id, :canonical_url, :title,
        :creator, :duration_ms, :language, :level, CAST(:playback AS JSONB), :thumbnail_kind, :thumbnail_ref,
        CAST(:source AS JSONB), :owner_token, CAST(:lesson_meta AS JSONB), :lesson_id, :topic, CAST(:tags AS JSONB), :has_lesson, :segment_count,
        :stored_bytes, :created_at, :updated_at)
    ON CONFLICT (media_id) DO UPDATE SET
        status = EXCLUDED.status, media_type = EXCLUDED.media_type, provider = EXCLUDED.provider,
        provider_media_id = EXCLUDED.provider_media_id, canonical_url = EXCLUDED.canonical_url, title = EXCLUDED.title,
        creator = EXCLUDED.creator, duration_ms = EXCLUDED.duration_ms, language = EXCLUDED.language,
        level = EXCLUDED.level, playback = EXCLUDED.playback, thumbnail_kind = EXCLUDED.thumbnail_kind,
        thumbnail_ref = EXCLUDED.thumbnail_ref, source = EXCLUDED.source, lesson_meta = EXCLUDED.lesson_meta,
        lesson_id = EXCLUDED.lesson_id,
        topic = EXCLUDED.topic, tags = EXCLUDED.tags, has_lesson = EXCLUDED.has_lesson,
        segment_count = EXCLUDED.segment_count,
        stored_bytes = COALESCE(EXCLUDED.stored_bytes, media_entries.stored_bytes), updated_at = EXCLUDED.updated_at
        -- created_at, library and owner_token are never updated
    WHERE media_entries.library = EXCLUDED.library
      AND media_entries.owner_token IS NOT DISTINCT FROM EXCLUDED.owner_token
    """
)
_PAYLOAD_UPSERT = text(
    "INSERT INTO media_entry_payloads (media_id, payload) VALUES (:media_id, CAST(:payload AS JSONB))"
    " ON CONFLICT (media_id) DO UPDATE SET payload = EXCLUDED.payload"
)


class PostgresMediaLibraryRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # -- plumbing ---------------------------------------------------------------------------------------------

    @staticmethod
    def _unavailable(error: Exception) -> MediaStoreUnavailable:
        failure = MediaStoreUnavailable(type(error).__name__)
        failure.__cause__ = error
        return failure

    def _write(self, function):
        try:
            with self._engine.begin() as connection:
                return function(connection)
        except (OperationalError, InterfaceError) as error:
            raise self._unavailable(error) from error

    def _read(self, function):
        try:
            with self._engine.connect() as connection:
                return function(connection)
        except (OperationalError, InterfaceError) as error:
            raise self._unavailable(error) from error

    # -- reads ------------------------------------------------------------------------------------------------

    def get(self, media_id: str, *, with_payload: bool = False) -> MediaLibraryEntry | None:
        """Head-only by default: no join to, and no read of, `media_entry_payloads`."""

        def run(connection):
            row = connection.execute(
                text(f"SELECT {_HEAD_COLUMNS} FROM media_entries WHERE media_id = :id"), {"id": media_id}
            ).mappings().first()
            if row is None:
                return None
            payload = None
            if with_payload and row["has_lesson"]:
                payload = connection.execute(
                    text("SELECT payload FROM media_entry_payloads WHERE media_id = :id"), {"id": media_id}
                ).scalar()
            return row_to_entry(row, payload)

        return self._read(run)

    def list(
        self, *, language: str | None = None, library: str = "shared", status: str | None = "published"
    ) -> list[MediaLibraryEntry]:
        """Compatibility with the file store's listing (head-only entries, newest first). Callers that page use
        `list_page`."""
        clauses, params = ["library = :library"], {"library": library}
        if language is not None:
            clauses.append("language = :language")
            params["language"] = language
        if status is not None:
            clauses.append("status = :status")
            params["status"] = status
        sql = f"SELECT {_HEAD_COLUMNS} FROM media_entries WHERE {' AND '.join(clauses)} ORDER BY created_at DESC, media_id DESC"
        return self._read(lambda c: [row_to_entry(r) for r in c.execute(text(sql), params).mappings()])

    def list_page(
        self,
        *,
        library: str = "shared",
        language: str | None = None,
        status: str | None = "published",
        after: tuple[datetime, str] | None = None,
        limit: int = PAGE_DEFAULT,
    ) -> list[MediaLibraryEntry]:
        """Keyset page by (created_at DESC, media_id DESC). The cursor carries position only; library, language and
        status come from the request."""
        clauses, params = ["library = :library"], {"library": library, "limit": max(1, min(int(limit), PAGE_MAX))}
        if language is not None:
            clauses.append("language = :language")
            params["language"] = language
        if status is not None:
            clauses.append("status = :status")
            params["status"] = status
        if after is not None:
            clauses.append("(created_at, media_id) < (:after_at, :after_id)")
            params["after_at"], params["after_id"] = after
        sql = (
            f"SELECT {_HEAD_COLUMNS} FROM media_entries WHERE {' AND '.join(clauses)}"
            " ORDER BY created_at DESC, media_id DESC LIMIT :limit"
        )
        return self._read(lambda c: [row_to_entry(r) for r in c.execute(text(sql), params).mappings()])

    def list_owned_page(
        self, owner: str, *, after: tuple[str, datetime, str] | None = None, limit: int = PAGE_DEFAULT
    ) -> list[MediaLibraryEntry]:
        """A learner's uploads in every language, ordered (language, created_at DESC, media_id DESC) to match
        `ix_media_entries_owner`. Cursor = (language, created_at, media_id)."""
        params: dict[str, Any] = {"owner": owner, "limit": max(1, min(int(limit), PAGE_MAX))}
        clause = ""
        if after is not None:
            clause = " AND (language > :al OR (language = :al AND (created_at, media_id) < (:ac, :ai)))"
            params["al"], params["ac"], params["ai"] = after
        sql = (
            f"SELECT {_HEAD_COLUMNS} FROM media_entries WHERE library = 'personal' AND owner_token = :owner{clause}"
            " ORDER BY language, created_at DESC, media_id DESC LIMIT :limit"
        )
        return self._read(lambda c: [row_to_entry(r) for r in c.execute(text(sql), params).mappings()])

    def find_shared_by_lesson_id(self, lesson_id: str) -> MediaLibraryEntry | None:
        def run(connection):
            row = connection.execute(
                text(f"SELECT {_HEAD_COLUMNS} FROM media_entries WHERE library = 'shared' AND lesson_id = :l"),
                {"l": lesson_id},
            ).mappings().first()
            return row_to_entry(row) if row else None

        return self._read(run)

    def sum_upload_bytes(self, owner: str) -> int:
        """Bytes of this owner's stored uploads (entries whose removal is pending still count: the row goes last)."""
        return int(
            self._read(
                lambda c: c.execute(
                    text(
                        "SELECT coalesce(sum(stored_bytes), 0) FROM media_entries"
                        " WHERE library = 'personal' AND owner_token = :o"
                    ),
                    {"o": owner},
                ).scalar()
            )
        )

    def count(self, *, library: str | None = None) -> int:
        sql = "SELECT count(*) FROM media_entries" + (" WHERE library = :l" if library else "")
        return int(self._read(lambda c: c.execute(text(sql), {"l": library} if library else {}).scalar()))

    # -- writes -----------------------------------------------------------------------------------------------

    def upsert(self, entry: MediaLibraryEntry, *, stored_bytes: int | None = None) -> MediaLibraryEntry:
        row = entry_to_row(entry, stored_bytes=stored_bytes)

        def run(connection):
            result = connection.execute(_UPSERT, row)
            if result.rowcount == 0:
                raise MediaEntryConflict("library or owner_token of an existing row cannot change")
            if row["payload"] is not None:
                connection.execute(_PAYLOAD_UPSERT, {"media_id": row["media_id"], "payload": row["payload"]})
            else:
                connection.execute(text("DELETE FROM media_entry_payloads WHERE media_id = :id"), {"id": row["media_id"]})
            return entry

        try:
            return self._write(run)
        except IntegrityError as error:  # the shared lesson_id unique index
            if "ix_media_entries_lesson_id" in str(error.orig):
                raise MediaEntryConflict("another shared entry already has this lesson_id") from error
            raise

    def insert_personal(self, entry: MediaLibraryEntry, *, stored_bytes: int, byte_limit: int) -> MediaLibraryEntry:
        """Insert a personal upload only if the owner's bytes plus this file stay within the limit: one transaction,
        an advisory lock per owner, so two concurrent uploads of one account cannot both pass and different accounts
        never contend. A refusal rolls back (the caller then deletes the files it just stored)."""
        if entry.library != "personal":
            raise ValueError("insert_personal takes a personal entry")
        row = entry_to_row(entry, stored_bytes=stored_bytes)

        def run(connection):
            connection.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:o, 0))"), {"o": row["owner_token"]})
            used = int(
                connection.execute(
                    text(
                        "SELECT coalesce(sum(stored_bytes), 0) FROM media_entries"
                        " WHERE library = 'personal' AND owner_token = :o"
                    ),
                    {"o": row["owner_token"]},
                ).scalar()
            )
            if used + stored_bytes > byte_limit:
                raise MediaQuotaExceeded(used, stored_bytes, byte_limit)
            result = connection.execute(_UPSERT, row)
            if result.rowcount == 0:
                raise MediaEntryConflict("library or owner_token of an existing row cannot change")
            return entry

        return self._write(run)

    def set_status(self, media_id: str, status: str) -> bool:
        """A status-only UPDATE on a shared row (no read-modify-write of the whole entry)."""
        if status not in {"published", "unpublished", "archived"}:
            raise ValueError("status is invalid")
        return bool(
            self._write(
                lambda c: c.execute(
                    text("UPDATE media_entries SET status = :s, updated_at = now() WHERE media_id = :id AND library = 'shared'"),
                    {"s": status, "id": media_id},
                ).rowcount
            )
        )

    def delete(self, media_id: str) -> bool:
        return bool(self._write(lambda c: c.execute(text("DELETE FROM media_entries WHERE media_id = :id"), {"id": media_id}).rowcount))


__all__ = [
    "LEGACY_OWNER_TOKEN",
    "MediaEntryConflict",
    "MediaQuotaExceeded",
    "MediaStoreUnavailable",
    "PostgresMediaLibraryRepository",
    "entry_to_row",
    "lesson_parts",
    "owner_of",
    "row_to_entry",
]
