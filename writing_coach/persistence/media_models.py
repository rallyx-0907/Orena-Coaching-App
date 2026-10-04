"""ORM mirror of migration 20261001_0024 (media metadata in PostgreSQL) - PARKED, INERT (D-109).

`docs/project/proposals/MEDIA_METADATA_POSTGRES.md` (revision 2). The migration is still in `migrations/proposed/`, not in
`versions/`, so these tables must not appear anywhere a deployed schema is built from `Base.metadata`. They therefore live on
their OWN declarative base (`MediaBase`), not on `writing_coach.persistence.models.Base`:

- the hermetic SQLite `create_all` (which uses `Base.metadata`) does not create them;
- nothing that enumerates `Base.metadata` (parity tests, readiness checks) sees them;
- `tests/test_media_metadata_postgres.py` compares this declaration with the migrated schema once `0024` is applied from
  `migrations/proposed/` on a throwaway database.

When the migration is authorized and moved to `versions/`, these two classes move into `models.py` on `Base` in the same
commit (and the head-sensitive tests move to `0024`). Until then nothing imports this module except that test and the
parked repository/rehearsal code. PostgreSQL-only CHECKs (regex, JSON operators) are conditional DDL.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    false,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class MediaBase(DeclarativeBase):
    """Separate metadata: inert until the migration is authorized."""


_MEDIA_JSON = JSON().with_variant(JSONB(), "postgresql")
_MEDIA_ID = "'^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$'"


class MediaEntry(MediaBase):
    """One media identity: a shared admin import or a learner's personal upload (not the bytes)."""

    __tablename__ = "media_entries"
    __table_args__ = (
        CheckConstraint("library IN ('shared','personal')", name="ck_media_entries_library"),
        CheckConstraint("status IN ('published','unpublished','archived')", name="ck_media_entries_status"),
        CheckConstraint("media_type IN ('video','audio')", name="ck_media_entries_media_type"),
        CheckConstraint("thumbnail_kind IN ('provider-url','asset','none')", name="ck_media_entries_thumbnail_kind"),
        CheckConstraint("(thumbnail_kind = 'none') = (thumbnail_ref = '')", name="ck_media_entries_thumbnail_ref"),
        CheckConstraint("duration_ms >= 0", name="ck_media_entries_duration"),
        CheckConstraint("length(title) > 0", name="ck_media_entries_title"),
        CheckConstraint("segment_count >= 0", name="ck_media_entries_segments"),
        CheckConstraint("stored_bytes IS NULL OR stored_bytes >= 0", name="ck_media_entries_stored_bytes"),
        CheckConstraint("(library = 'personal') = (owner_token IS NOT NULL)", name="ck_media_entries_owner"),
        CheckConstraint("library <> 'personal' OR provider = 'upload'", name="ck_media_entries_personal_upload"),
        CheckConstraint("(lesson_meta IS NOT NULL) = has_lesson", name="ck_media_entries_lesson_flag"),
        CheckConstraint(f"media_id ~ {_MEDIA_ID}", name="ck_media_entries_media_id").ddl_if(dialect="postgresql"),
        CheckConstraint(
            f"provider ~ {_MEDIA_ID} AND provider_media_id ~ {_MEDIA_ID}", name="ck_media_entries_provider_ids"
        ).ddl_if(dialect="postgresql"),
        CheckConstraint("jsonb_typeof(playback) = 'object'", name="ck_media_entries_playback").ddl_if(dialect="postgresql"),
        CheckConstraint("jsonb_typeof(source) = 'object'", name="ck_media_entries_source").ddl_if(dialect="postgresql"),
        CheckConstraint("jsonb_typeof(tags) = 'array'", name="ck_media_entries_tags").ddl_if(dialect="postgresql"),
        CheckConstraint(
            "lesson_meta IS NULL OR jsonb_typeof(lesson_meta) = 'object'", name="ck_media_entries_lesson_meta"
        ).ddl_if(dialect="postgresql"),
        CheckConstraint(
            "source->>'owner' IS NULL OR source->>'owner' = owner_token", name="ck_media_entries_owner_agrees"
        ).ddl_if(dialect="postgresql"),
        Index("ix_media_entries_browse", "library", "language", "status", text("created_at DESC"), text("media_id DESC")),
        Index("ix_media_entries_library_created", "library", text("created_at DESC"), text("media_id DESC")),
        Index(
            "ix_media_entries_lesson_id", "lesson_id", unique=True,
            postgresql_where=text("library = 'shared' AND lesson_id IS NOT NULL"),
            sqlite_where=text("library = 'shared' AND lesson_id IS NOT NULL"),
        ),
        Index(
            "ix_media_entries_owner", "owner_token", "language", text("created_at DESC"), text("media_id DESC"),
            postgresql_include=["stored_bytes"],
            postgresql_where=text("library = 'personal'"),
            sqlite_where=text("library = 'personal'"),
        ),
    )

    media_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    library: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="published", server_default="published", nullable=False)
    media_type: Mapped[str] = mapped_column(String(5), nullable=False)
    provider: Mapped[str] = mapped_column(String(256), nullable=False)
    provider_media_id: Mapped[str] = mapped_column(String(256), nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, default="", server_default="", nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    creator: Mapped[str] = mapped_column(Text, default="", server_default="", nullable=False)
    duration_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    language: Mapped[str] = mapped_column(String(20), nullable=False)
    level: Mapped[str] = mapped_column(String(16), default="", server_default="", nullable=False)
    playback: Mapped[dict] = mapped_column(_MEDIA_JSON, nullable=False)
    thumbnail_kind: Mapped[str] = mapped_column(String(12), nullable=False)
    thumbnail_ref: Mapped[str] = mapped_column(Text, default="", server_default="", nullable=False)
    source: Mapped[dict] = mapped_column(_MEDIA_JSON, nullable=False)
    owner_token: Mapped[str | None] = mapped_column(String(32), nullable=True)
    lesson_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    topic: Mapped[str] = mapped_column(String(64), default="", server_default="", nullable=False)
    tags: Mapped[list] = mapped_column(_MEDIA_JSON, nullable=False)
    lesson_meta: Mapped[dict | None] = mapped_column(_MEDIA_JSON, nullable=True)
    has_lesson: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    segment_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    stored_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MediaEntryPayload(MediaBase):
    """The lesson payload (transcript, translations) of an entry, 1:1, kept out of the entry row."""

    __tablename__ = "media_entry_payloads"

    media_id: Mapped[str] = mapped_column(
        ForeignKey("media_entries.media_id", ondelete="CASCADE", name="fk_media_entry_payloads_entry"),
        primary_key=True,
    )
    payload: Mapped[dict] = mapped_column(_MEDIA_JSON, nullable=False)
