"""Persistence adapter for shared vocabulary content.

The repository owns collections, lexical entries, memberships, and import
receipts.  It deliberately does *not* own saved words, review schedules, or
learner progress; those continue through the existing learner repositories.

PostgreSQL is fail-closed until the vocabulary-content migration is explicitly
reviewed and applied.  The SQLite implementation is only a hermetic test/local
archive adapter and creates its four content tables when the app is running in
the SQLite test backend.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, func, inspect, or_, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from writing_coach.persistence.models import (
    Base,
    VocabularyCollection,
    VocabularyCollectionMembership,
    VocabularyEntry,
    VocabularySourceImport,
)


VOCABULARY_TABLES = (
    "vocabulary_collections",
    "vocabulary_entries",
    "vocabulary_source_imports",
    "vocabulary_collection_memberships",
)
VOCABULARY_SCHEMA_REVISION = "20260916_0008"
VOCABULARY_REQUIRED_COLUMNS = {
    "vocabulary_collections": {
        "id", "language_code", "title", "framework", "level", "level_range",
        "topic", "catalog_status", "origin", "provenance", "created_at", "updated_at",
    },
    "vocabulary_entries": {
        "id", "language_code", "term", "normalized_term", "identity_key", "sense_key",
        "pronunciations", "readings", "short_meanings", "detailed_definitions",
        "part_of_speech", "examples", "usage_notes", "orthography", "level", "framework",
        "topic", "content_origins", "provenance", "created_at", "updated_at",
    },
    "vocabulary_source_imports": {
        "id", "collection_id", "filename", "source_format", "content_hash", "mapping",
        "status", "imported_count", "skipped_count", "duplicate_count", "warning_count",
        "failed_count", "warnings", "errors", "imported_by", "created_at", "updated_at",
    },
    "vocabulary_collection_memberships": {
        "id", "collection_id", "entry_id", "source_import_id", "position", "metadata",
    },
}
_VOCABULARY_PUBLISHABLE_RIGHTS = {
    "public_domain",
    "licensed",
    "creator_authorized",
    "internal_curated",
}
_VOCABULARY_CATALOG_STATUSES = {"pending_review", "published"}


def _vocabulary_revision_is_usable(current_revision: str) -> bool:
    """Accept the vocabulary migration and any later linear descendant."""

    if current_revision == VOCABULARY_SCHEMA_REVISION:
        return True
    try:
        root = Path(__file__).resolve().parents[2]
        config = Config(str(root / "alembic.ini"))
        config.set_main_option("script_location", str(root / "migrations"))
        script = ScriptDirectory.from_config(config)
        return any(
            revision.revision == VOCABULARY_SCHEMA_REVISION
            for revision in script.iterate_revisions(current_revision, VOCABULARY_SCHEMA_REVISION)
        )
    except Exception:
        return False


class VocabularyContentUnavailable(RuntimeError):
    """The shared vocabulary schema is not available in this runtime."""


class VocabularyRepository(Protocol):
    def available(self) -> bool: ...
    def initialize(self) -> None: ...
    def import_source(
        self,
        *,
        collection: Mapping[str, Any],
        source: Mapping[str, Any],
        records: Iterable[Mapping[str, Any]],
        mapping: Mapping[str, Any],
        imported_by: str = "",
    ) -> dict[str, Any]: ...
    def record_source_failure(
        self,
        *,
        collection_id: str | None,
        filename: str,
        source_format: str = "",
        content_hash: str = "",
        mapping: Mapping[str, Any] | None = None,
        failure_reason: str,
        imported_by: str = "",
    ) -> dict[str, Any]: ...
    def list_collections(self, language_code: str) -> list[dict[str, Any]]: ...
    def get_collection(
        self,
        collection_id: str,
        *,
        search: str = "",
        level: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any] | None: ...
    def find_entry(self, language_code: str, normalized_term: str) -> dict[str, Any] | None: ...
    def list_entries_for_language(
        self, language_code: str, *, limit: int = 1000
    ) -> list[dict[str, Any]]: ...
    def list_entries(
        self,
        collection_id: str,
        *,
        search: str = "",
        level: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]: ...


def _now() -> datetime:
    return datetime.now(UTC)


def _copy_json(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    try:
        return json.loads(json.dumps(value, ensure_ascii=False))
    except (TypeError, ValueError):
        return fallback


def _level_sort_key(value: object) -> tuple[int, int, str]:
    text = str(value or "").strip().upper().replace("–", "-").replace("—", "-")
    if text.startswith("HSK"):
        suffix = text.removeprefix("HSK")
        if suffix == "7-9":
            return (1, 7, text)
        if suffix.isdigit():
            return (1, int(suffix), text)
    order = {name: index for index, name in enumerate(("A1", "A2", "B1", "B2", "C1", "C2"), start=1)}
    if text in order:
        return (0, order[text], text)
    return (2, 0, text)


def _level_range(levels: list[str], fallback: str = "") -> str:
    unique = sorted({str(value).strip() for value in levels if str(value).strip()}, key=_level_sort_key)
    if len(unique) >= 2:
        return f"{unique[0]}–{unique[-1]}"
    return unique[0] if unique else str(fallback or "").strip()


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _merge_list(existing: Any, incoming: Any) -> list[Any]:
    current = list(existing) if isinstance(existing, list) else []
    additions = incoming if isinstance(incoming, list) else []
    seen = {json.dumps(item, ensure_ascii=False, sort_keys=True) for item in current}
    for item in additions:
        marker = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if marker not in seen:
            current.append(_copy_json(item, item))
            seen.add(marker)
    return current


def _entry_dict(entry: VocabularyEntry) -> dict[str, Any]:
    return {
        "id": str(entry.id),
        "word": entry.term,
        "term": entry.term,
        "language_code": entry.language_code,
        "normalized_word": entry.normalized_term,
        "normalized_term": entry.normalized_term,
        "identity_key": entry.identity_key,
        "sense_key": entry.sense_key,
        "pronunciations": _copy_json(entry.pronunciations, []),
        "readings": _copy_json(entry.readings, []),
        "short_meanings": _copy_json(entry.short_meanings, []),
        "detailed_definitions": _copy_json(entry.detailed_definitions, []),
        "support_translations": {
            item.get("language"): item.get("text")
            for item in (_copy_json(entry.short_meanings, []) or [])
            if isinstance(item, Mapping) and item.get("language") and item.get("text")
        },
        "phonetic": (
            (_copy_json(entry.pronunciations, []) or [{}])[0].get("text", "")
            if isinstance((_copy_json(entry.pronunciations, []) or [{}])[0], Mapping)
            else ((_copy_json(entry.pronunciations, []) or [""])[0])
        ),
        "part_of_speech": entry.part_of_speech,
        "examples": _copy_json(entry.examples, []),
        "usage_notes": _copy_json(entry.usage_notes, []),
        "orthography": _copy_json(entry.orthography, {}),
        "level": entry.level,
        "framework": entry.framework,
        "topic": entry.topic,
        "content_origins": _copy_json(entry.content_origins, {}),
        "provenance": _copy_json(entry.provenance, {}),
    }


class SQLAlchemyVocabularyRepository:
    """Shared repository implementation for PostgreSQL and test SQLite."""

    def __init__(self, engine: Engine, *, allow_sqlite_initialize: bool = False) -> None:
        self.engine = engine
        self.allow_sqlite_initialize = allow_sqlite_initialize

    def available(self) -> bool:
        try:
            inspector = inspect(self.engine)
            tables = set(inspector.get_table_names())
            if not set(VOCABULARY_TABLES).issubset(tables):
                return False
            for table, required in VOCABULARY_REQUIRED_COLUMNS.items():
                actual = {column["name"] for column in inspector.get_columns(table)}
                if not required.issubset(actual):
                    return False
            if self.engine.dialect.name != "postgresql":
                return self.allow_sqlite_initialize
            with self.engine.connect() as connection:
                revisions = {
                    str(row[0] or "")
                    for row in connection.execute(
                        text("SELECT version_num FROM alembic_version")
                    ).all()
                }
            return len(revisions) == 1 and _vocabulary_revision_is_usable(revisions.pop())
        except Exception:
            return False

    def initialize(self) -> None:
        """Create only the isolated SQLite content schema when permitted."""

        if not self.allow_sqlite_initialize:
            return
        if self.engine.dialect.name != "sqlite":
            raise VocabularyContentUnavailable(
                "The PostgreSQL vocabulary schema must be applied by the reviewed migration."
            )
        Base.metadata.create_all(
            self.engine,
            tables=[
                VocabularyCollection.__table__,
                VocabularyEntry.__table__,
                VocabularySourceImport.__table__,
                VocabularyCollectionMembership.__table__,
            ],
        )

    def _require_available(self) -> None:
        if not self.available():
            raise VocabularyContentUnavailable(
                "The vocabulary content schema is unavailable; the import was not written."
            )

    def import_source(
        self,
        *,
        collection: Mapping[str, Any],
        source: Mapping[str, Any],
        records: Iterable[Mapping[str, Any]],
        mapping: Mapping[str, Any],
        imported_by: str = "",
    ) -> dict[str, Any]:
        self._require_available()
        collection_id = _text(collection.get("id"))
        if not collection_id:
            raise ValueError("A stable collection id is required.")
        language_code = _text(collection.get("language_code")).casefold()
        if not language_code:
            raise ValueError("A collection language_code is required.")
        catalog_status = _text(collection.get("catalog_status")).casefold() or "pending_review"
        if catalog_status not in _VOCABULARY_CATALOG_STATUSES:
            raise ValueError(f"Unsupported vocabulary catalog status '{catalog_status}'.")
        collection_provenance = _copy_json(collection.get("provenance"), {}) or {}
        if catalog_status == "published":
            admission = collection_provenance.get("admission")
            if not isinstance(admission, Mapping) or (
                admission.get("review_status") != "approved"
                or admission.get("publication_attested") is not True
                or _text(admission.get("rights_status")) not in _VOCABULARY_PUBLISHABLE_RIGHTS
                or _text(admission.get("completeness")).casefold() != "complete"
            ):
                raise ValueError(
                    "A vocabulary collection needs an approved rights/completeness admission before publication."
                )
        now = _now()
        rows = list(records)
        source_id = uuid.uuid4()
        warnings = [str(item) for item in source.get("warnings", []) if str(item).strip()]
        skipped_details = [item for item in source.get("skipped", []) if isinstance(item, Mapping)]
        imported_count = 0
        duplicate_count = 0
        skipped_count = len(skipped_details)
        source_format = _text(source.get("format"))
        filename = _text(source.get("filename")) or "source"
        content_hash = _text(source.get("content_hash"))
        if not content_hash:
            content_hash = hashlib.sha256(filename.encode("utf-8")).hexdigest()

        with Session(self.engine) as session, session.begin():
            collection_row = session.get(VocabularyCollection, collection_id)
            if collection_row is None:
                collection_row = VocabularyCollection(
                    id=collection_id,
                    language_code=language_code,
                    title=_text(collection.get("title")) or collection_id,
                    framework=_text(collection.get("framework")),
                    level=_text(collection.get("level")),
                    level_range=_text(collection.get("level_range")),
                    topic=_text(collection.get("topic")),
                    catalog_status=catalog_status,
                    origin=_text(collection.get("origin")) or "imported",
                    provenance=collection_provenance,
                    created_at=now,
                    updated_at=now,
                )
                session.add(collection_row)
            elif collection_row.language_code != language_code:
                raise ValueError(
                    f"Collection '{collection_id}' already belongs to language '{collection_row.language_code}'."
                )
            else:
                # Re-importing a collection may update human-entered display
                # metadata, but never changes the collection's stable identity.
                for field in ("title", "framework", "level", "level_range", "topic", "catalog_status"):
                    value = _text(collection.get(field))
                    if field == "catalog_status" and value.casefold() != "published" and collection_row.catalog_status == "published":
                        continue
                    if value:
                        setattr(collection_row, field, value)
                collection_row.provenance = _merge_list([], [collection.get("provenance", {})])[0]
                collection_row.updated_at = now

            import_row = VocabularySourceImport(
                id=source_id,
                collection_id=collection_id,
                filename=filename,
                source_format=source_format,
                content_hash=content_hash,
                mapping=_copy_json(mapping, {}),
                status="importing",
                warnings=warnings,
                errors=[],
                imported_by=_text(imported_by),
                created_at=now,
                updated_at=now,
            )
            session.add(import_row)
            session.flush()

            next_position = int(
                session.scalar(
                    select(func.max(VocabularyCollectionMembership.position)).where(
                        VocabularyCollectionMembership.collection_id == collection_id
                    )
                )
                or 0
            )
            for source_position, raw_record in enumerate(rows, start=1):
                record = dict(raw_record)
                identity_key = _text(record.get("identity_key"))
                if not identity_key:
                    skipped_count += 1
                    skipped_details.append({"position": source_position, "reason": "missing identity key"})
                    continue
                entry = session.scalar(
                    select(VocabularyEntry).where(VocabularyEntry.identity_key == identity_key)
                )
                if entry is None:
                    entry = VocabularyEntry(
                        id=uuid.uuid4(),
                        language_code=language_code,
                        term=_text(record.get("term")),
                        normalized_term=_text(record.get("normalized_term")),
                        identity_key=identity_key,
                        sense_key=_text(record.get("sense_key")),
                        pronunciations=_copy_json(record.get("pronunciations"), []),
                        readings=_copy_json(record.get("readings"), []),
                        short_meanings=_copy_json(record.get("short_meanings"), []),
                        detailed_definitions=_copy_json(record.get("detailed_definitions"), []),
                        part_of_speech=_text(record.get("part_of_speech")),
                        examples=_copy_json(record.get("examples"), []),
                        usage_notes=_copy_json(record.get("usage_notes"), []),
                        orthography=_copy_json(record.get("orthography"), {}),
                        level=_text(record.get("level")),
                        framework=_text(record.get("framework")),
                        topic=_text(record.get("topic")),
                        content_origins=_copy_json(record.get("content_origins"), {}),
                        provenance=_copy_json(record.get("provenance"), {}),
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(entry)
                    session.flush()
                else:
                    duplicate_count += 1
                    _merge_existing_entry(entry, record, warnings)
                    entry.updated_at = now

                membership = session.scalar(
                    select(VocabularyCollectionMembership).where(
                        VocabularyCollectionMembership.collection_id == collection_id,
                        VocabularyCollectionMembership.entry_id == entry.id,
                    )
                )
                if membership is not None:
                    skipped_count += 1
                    skipped_details.append(
                        {"position": source_position, "reason": "already a member of collection", "term": entry.term}
                    )
                    continue
                membership = VocabularyCollectionMembership(
                    id=uuid.uuid4(),
                    collection_id=collection_id,
                    entry_id=entry.id,
                    source_import_id=source_id,
                    position=next_position + 1,
                    membership_metadata={
                        "source_row": record.get("provenance", {}).get("row"),
                        "origin": "source",
                        "level": _text(record.get("level")),
                        "framework": _text(record.get("framework")),
                        "topic": _text(record.get("topic")),
                    },
                )
                session.add(membership)
                imported_count += 1
                next_position += 1

            import_row.status = "imported" if imported_count else "skipped"
            import_row.imported_count = imported_count
            import_row.skipped_count = skipped_count
            import_row.duplicate_count = duplicate_count
            import_row.warning_count = len(warnings)
            import_row.failed_count = 0
            import_row.warnings = warnings
            import_row.errors = skipped_details
            import_row.updated_at = _now()

            if not collection_row.level_range:
                levels = list(
                    session.scalars(
                        select(VocabularyEntry.level)
                        .join(
                            VocabularyCollectionMembership,
                            VocabularyCollectionMembership.entry_id == VocabularyEntry.id,
                        )
                        .where(VocabularyCollectionMembership.collection_id == collection_id)
                    )
                )
                collection_row.level_range = _level_range(levels, collection_row.level)

        return {
            "source_import_id": str(source_id),
            "filename": filename,
            "status": "imported" if imported_count else "skipped",
            "imported": imported_count,
            "skipped": skipped_count,
            "duplicates": duplicate_count,
            "warnings": warnings,
            "failed": 0,
            "failure_reason": "",
        }

    def record_source_failure(
        self,
        *,
        collection_id: str | None,
        filename: str,
        source_format: str = "",
        content_hash: str = "",
        mapping: Mapping[str, Any] | None = None,
        failure_reason: str,
        imported_by: str = "",
    ) -> dict[str, Any]:
        """Persist a failed source receipt without creating lexical content."""

        self._require_available()
        source_id = uuid.uuid4()
        now = _now()
        clean_filename = _text(filename) or "source"
        clean_hash = _text(content_hash) or hashlib.sha256(
            clean_filename.encode("utf-8")
        ).hexdigest()
        error = {"reason": _text(failure_reason) or "source import failed"}
        with Session(self.engine) as session, session.begin():
            session.add(
                VocabularySourceImport(
                    id=source_id,
                    collection_id=_text(collection_id) or None,
                    filename=clean_filename,
                    source_format=_text(source_format),
                    content_hash=clean_hash,
                    mapping=_copy_json(mapping, {}) or {},
                    status="failed",
                    imported_count=0,
                    skipped_count=0,
                    duplicate_count=0,
                    warning_count=0,
                    failed_count=1,
                    warnings=[],
                    errors=[error],
                    imported_by=_text(imported_by),
                    created_at=now,
                    updated_at=now,
                )
            )
        return {
            "source_import_id": str(source_id),
            "filename": clean_filename,
            "status": "failed",
            "imported": 0,
            "skipped": 0,
            "duplicates": 0,
            "warnings": [],
            "failed": 1,
            "failure_reason": error["reason"],
        }

    def list_collections(self, language_code: str) -> list[dict[str, Any]]:
        self._require_available()
        language = _text(language_code).casefold()
        with Session(self.engine) as session:
            collections = list(
                session.scalars(
                    select(VocabularyCollection)
                    .where(
                        VocabularyCollection.language_code == language,
                        VocabularyCollection.catalog_status == "published",
                    )
                    .order_by(VocabularyCollection.title)
                )
            )
            result: list[dict[str, Any]] = []
            for collection in collections:
                levels, item_count = self._collection_stats(session, collection.id)
                result.append(_collection_summary(collection, levels, item_count))
            return result

    def get_collection(
        self,
        collection_id: str,
        *,
        search: str = "",
        level: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any] | None:
        self._require_available()
        with Session(self.engine) as session:
            collection = session.scalar(
                select(VocabularyCollection).where(
                    VocabularyCollection.id == _text(collection_id),
                    VocabularyCollection.catalog_status == "published",
                )
            )
            if collection is None:
                return None
            entries, total = self._list_entries_in_session(
                session,
                collection.id,
                search=_text(search),
                level=_text(level),
                limit=limit,
                offset=offset,
            )
            levels, item_count = self._collection_stats(session, collection.id)
            result = _collection_summary(collection, levels, item_count)
            result["entries"] = entries
            result["pagination"] = {
                "limit": max(0, min(limit, 5000)),
                "offset": max(0, offset),
                "total": total,
                "has_more": max(0, offset) + len(entries) < total,
            }
            return result

    @staticmethod
    def _collection_stats(
        session: Session, collection_id: str
    ) -> tuple[list[str], int]:
        rows = session.execute(
            select(VocabularyEntry.level, VocabularyCollectionMembership.membership_metadata)
            .join(
                VocabularyCollectionMembership,
                VocabularyCollectionMembership.entry_id == VocabularyEntry.id,
            )
            .where(VocabularyCollectionMembership.collection_id == collection_id)
        ).all()
        levels: list[str] = []
        for entry_level, raw_metadata in rows:
            metadata = _copy_json(raw_metadata, {}) or {}
            effective_level = _text(metadata.get("level")) or _text(entry_level)
            if effective_level:
                levels.append(effective_level)
        return levels, len(rows)

    def list_entries(
        self,
        collection_id: str,
        *,
        search: str = "",
        level: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        self._require_available()
        with Session(self.engine) as session:
            return self._list_entries_in_session(
                session,
                _text(collection_id),
                search=_text(search),
                level=_text(level),
                limit=limit,
                offset=offset,
            )

    def find_entry(self, language_code: str, normalized_term: str) -> dict[str, Any] | None:
        self._require_available()
        with Session(self.engine) as session:
            entry = session.scalar(
                select(VocabularyEntry)
                .where(
                    VocabularyEntry.language_code == _text(language_code).casefold(),
                    VocabularyEntry.normalized_term == _text(normalized_term),
                )
                .order_by(VocabularyEntry.identity_key)
            )
            return _entry_dict(entry) if entry is not None else None

    def list_entries_for_language(
        self, language_code: str, *, limit: int = 1000
    ) -> list[dict[str, Any]]:
        self._require_available()
        with Session(self.engine) as session:
            rows = list(
                session.execute(
                    select(VocabularyEntry)
                    .join(
                        VocabularyCollectionMembership,
                        VocabularyCollectionMembership.entry_id == VocabularyEntry.id,
                    )
                    .join(
                        VocabularyCollection,
                        VocabularyCollection.id == VocabularyCollectionMembership.collection_id,
                    )
                    .where(
                        VocabularyEntry.language_code == _text(language_code).casefold(),
                        VocabularyCollection.catalog_status == "published",
                    )
                    .order_by(VocabularyEntry.identity_key)
                    .limit(max(0, min(limit, 5000)))
                ).scalars()
            )
            seen: set[uuid.UUID] = set()
            result: list[dict[str, Any]] = []
            for entry in rows:
                if entry.id in seen:
                    continue
                seen.add(entry.id)
                result.append(_entry_dict(entry))
            return result

    def _list_entries_in_session(
        self,
        session: Session,
        collection_id: str,
        *,
        search: str = "",
        level: str = "",
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        conditions = [VocabularyCollectionMembership.collection_id == collection_id]
        needle = _text(search).casefold()
        wanted_level = _text(level).casefold()
        if needle:
            pattern = f"%{needle}%"
            conditions.append(
                or_(
                    VocabularyEntry.term.ilike(pattern),
                    VocabularyEntry.normalized_term.ilike(pattern),
                )
            )
        if wanted_level:
            membership_level = VocabularyCollectionMembership.membership_metadata[
                "level"
            ].as_string()
            conditions.append(
                or_(
                    func.lower(VocabularyEntry.level) == wanted_level,
                    func.lower(membership_level) == wanted_level,
                )
            )

        total = int(
            session.scalar(
                select(func.count())
                .select_from(VocabularyEntry)
                .join(
                    VocabularyCollectionMembership,
                    VocabularyCollectionMembership.entry_id == VocabularyEntry.id,
                )
                .where(*conditions)
            )
            or 0
        )
        statement = (
            select(VocabularyEntry, VocabularyCollectionMembership)
            .join(
                VocabularyCollectionMembership,
                VocabularyCollectionMembership.entry_id == VocabularyEntry.id,
            )
            .where(*conditions)
            .order_by(VocabularyCollectionMembership.position, VocabularyEntry.term)
        )
        if limit is not None:
            statement = statement.offset(max(0, offset)).limit(max(0, min(limit, 5000)))
        else:
            statement = statement.offset(max(0, offset))
        rows = list(session.execute(statement).all())
        items: list[dict[str, Any]] = []
        for entry, membership in rows:
            item = _entry_dict(entry)
            item["collection_id"] = collection_id
            item["position"] = membership.position
            membership_metadata = _copy_json(membership.membership_metadata, {}) or {}
            for field in ("level", "framework", "topic"):
                if membership_metadata.get(field):
                    item[field] = membership_metadata[field]
            items.append(item)
        return items, total


def _merge_existing_entry(
    entry: VocabularyEntry, record: Mapping[str, Any], warnings: list[str]
) -> None:
    """Merge only missing shared fields; do not overwrite source truth silently."""

    scalar_fields = (
        "term", "normalized_term", "sense_key", "part_of_speech", "level", "framework", "topic"
    )
    for field in scalar_fields:
        incoming = _text(record.get(field))
        current = _text(getattr(entry, field))
        if incoming and not current:
            setattr(entry, field, incoming)
        elif incoming and current and incoming != current and field in {"term", "part_of_speech"}:
            warnings.append(
                f"Existing entry '{entry.term}' kept its {field}; the source supplied a different value."
            )
    for field in (
        "pronunciations", "readings", "short_meanings", "detailed_definitions",
        "examples", "usage_notes",
    ):
        setattr(entry, field, _merge_list(getattr(entry, field), record.get(field)))
    incoming_orthography = record.get("orthography")
    if incoming_orthography and not entry.orthography:
        entry.orthography = _copy_json(incoming_orthography, {})
    entry.content_origins = {
        **(_copy_json(entry.content_origins, {}) or {}),
        **(_copy_json(record.get("content_origins"), {}) or {}),
    }
    existing_provenance = _copy_json(entry.provenance, {}) or {}
    incoming_provenance = _copy_json(record.get("provenance"), {}) or {}
    sources = existing_provenance.get("sources", [])
    if not isinstance(sources, list):
        sources = []
    source_marker = {key: incoming_provenance.get(key) for key in ("filename", "format", "row", "content_hash")}
    if source_marker not in sources:
        sources.append(source_marker)
    entry.provenance = {**existing_provenance, "sources": sources}


def _collection_summary(
    collection: VocabularyCollection, levels: list[str], item_count: int
) -> dict[str, Any]:
    clean_levels = sorted({value for value in levels if value}, key=_level_sort_key)
    fallback = _text(collection.level)
    return {
        "id": collection.id,
        "language_code": collection.language_code,
        "framework": collection.framework,
        "level": collection.level,
        "topic": collection.topic,
        "title": collection.title,
        "item_count": item_count,
        "levels": clean_levels,
        "level_range": _level_range(clean_levels, collection.level_range or fallback),
        "provenance": _copy_json(collection.provenance, {}),
        "catalog_status": collection.catalog_status,
        "origin": collection.origin,
    }


def sqlite_vocabulary_repository(path: Path) -> SQLAlchemyVocabularyRepository:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite+pysqlite:///{path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    return SQLAlchemyVocabularyRepository(engine, allow_sqlite_initialize=True)


def vocabulary_db_path(product_db: Path) -> Path:
    configured = os.getenv("VOCABULARY_DB", "").strip()
    if configured:
        return Path(configured)
    return Path(product_db).with_name("vocabulary.db")
