"""Media metadata in PostgreSQL: `media_entries` and `media_entry_payloads` (D-108.5; MEDIA_METADATA_POSTGRES.md rev 2).

The shared media library (`data/media_library/index.json`, one file for every account, read and rewritten whole under a
per-process lock) stops being a writable source of truth. This revision creates the two tables that replace it:

- `media_entries`: one row per media identity (shared admin imports and learners' personal uploads). Ownership of a
  personal row is the explicit `owner_token` (a digest of the account key, not `users.id`); `stored_bytes` is the
  server-measured size of an uploaded file (original + thumbnail) that the uploaded-media quota sums.
- `media_entry_payloads`: the 1:1 lesson payload (transcript, translations) as JSONB, kept out of the entry row so every
  list and every per-request lookup stays narrow.

Additive only: no existing table, column or index is touched, so no lock is taken on one. The asset bytes do not move.
The data move is NOT here: `scripts/import_media_index.py` is an operator command (dry-run by default, refuses unless the
table is empty), never run by this revision or at startup (ARCHITECTURE_INVARIANTS: no startup import).

CHECKs that need PostgreSQL operators (the id pattern, `source->>'owner'`, JSON types) exist on PostgreSQL only; the
SQLite test backend gets the portable ones from the ORM mirror (`writing_coach/persistence/media_models.py`, on its own inert base while parked), which the
PostgreSQL schema-parity test compares with this file.

Review and gate. Proposal `docs/project/proposals/MEDIA_METADATA_POSTGRES.md` (revision 2), independent architecture review
`MEDIA_METADATA_POSTGRES_REVIEW.md` (APPROVE WITH CONDITIONS), human decision D-108.5. This file is a PROPOSAL: it lives in
`migrations/proposed/`, which Alembic does not read by default, so it is not a head and triggers no startup refusal. It moves
to `migrations/versions/` (one `git mv`) only after the PostgreSQL rehearsal (`scripts/rehearse_media_metadata_schema.py`,
recorded in `MEDIA_METADATA_POSTGRES.REHEARSAL.md`) and the human's authorization. Startup never applies it (D-002); only
`scripts/bootstrap_runtime_schema.py` does, after a backup.

`downgrade()` DROPS both tables and every media entry in them. It exists for the rehearsal; a runtime holding media metadata
is fixed forward or restored by an authorized incident operation, never downgraded.

Revision ID: 20261001_0024
Revises: 20260930_0023
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261001_0024"
down_revision = "20260930_0023"
branch_labels = None
depends_on = None

_ID = "'^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$'"


def _postgres() -> bool:
    return op.get_context().dialect.name == "postgresql"


def _json():
    return postgresql.JSONB() if _postgres() else sa.JSON()


def upgrade() -> None:
    pg = _postgres()
    checks = [
        sa.CheckConstraint("library IN ('shared','personal')", name="ck_media_entries_library"),
        sa.CheckConstraint("status IN ('published','unpublished','archived')", name="ck_media_entries_status"),
        sa.CheckConstraint("media_type IN ('video','audio')", name="ck_media_entries_media_type"),
        sa.CheckConstraint("thumbnail_kind IN ('provider-url','asset','none')", name="ck_media_entries_thumbnail_kind"),
        sa.CheckConstraint("(thumbnail_kind = 'none') = (thumbnail_ref = '')", name="ck_media_entries_thumbnail_ref"),
        sa.CheckConstraint("duration_ms >= 0", name="ck_media_entries_duration"),
        sa.CheckConstraint("length(title) > 0", name="ck_media_entries_title"),
        sa.CheckConstraint("segment_count >= 0", name="ck_media_entries_segments"),
        sa.CheckConstraint("stored_bytes IS NULL OR stored_bytes >= 0", name="ck_media_entries_stored_bytes"),
        # A personal row has an owner and a shared row cannot carry one; the only personal writer is the upload.
        sa.CheckConstraint("(library = 'personal') = (owner_token IS NOT NULL)", name="ck_media_entries_owner"),
        sa.CheckConstraint("library <> 'personal' OR provider = 'upload'", name="ck_media_entries_personal_upload"),
        sa.CheckConstraint("(lesson_meta IS NOT NULL) = has_lesson", name="ck_media_entries_lesson_flag"),
    ]
    if pg:
        checks += [
            sa.CheckConstraint(f"media_id ~ {_ID}", name="ck_media_entries_media_id"),
            sa.CheckConstraint(f"provider ~ {_ID} AND provider_media_id ~ {_ID}", name="ck_media_entries_provider_ids"),
            sa.CheckConstraint("jsonb_typeof(playback) = 'object'", name="ck_media_entries_playback"),
            sa.CheckConstraint("jsonb_typeof(source) = 'object'", name="ck_media_entries_source"),
            sa.CheckConstraint("jsonb_typeof(tags) = 'array'", name="ck_media_entries_tags"),
            sa.CheckConstraint(
                "lesson_meta IS NULL OR jsonb_typeof(lesson_meta) = 'object'", name="ck_media_entries_lesson_meta"
            ),
            # One value, two spellings, never disagreeing.
            sa.CheckConstraint(
                "source->>'owner' IS NULL OR source->>'owner' = owner_token", name="ck_media_entries_owner_agrees"
            ),
        ]
    op.create_table(
        "media_entries",
        sa.Column("media_id", sa.String(256), primary_key=True),
        sa.Column("library", sa.String(10), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="published"),
        sa.Column("media_type", sa.String(5), nullable=False),
        sa.Column("provider", sa.String(256), nullable=False),
        sa.Column("provider_media_id", sa.String(256), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("creator", sa.Text(), nullable=False, server_default=""),
        sa.Column("duration_ms", sa.BigInteger(), nullable=False),
        sa.Column("language", sa.String(20), nullable=False),
        sa.Column("level", sa.String(16), nullable=False, server_default=""),
        sa.Column("playback", _json(), nullable=False),
        sa.Column("thumbnail_kind", sa.String(12), nullable=False),
        sa.Column("thumbnail_ref", sa.Text(), nullable=False, server_default=""),
        sa.Column("source", _json(), nullable=False),
        sa.Column("owner_token", sa.String(32), nullable=True),
        sa.Column("lesson_id", sa.String(256), nullable=True),
        sa.Column("topic", sa.String(64), nullable=False, server_default=""),
        sa.Column("tags", _json(), nullable=False),
        # The lesson mapping WITHOUT its payload, verbatim (rehearsal finding: real lessons carry keys beyond lesson_id /
        # topic / tags - sections, status, curation, language - and may lack topic/tags). lesson_id, topic and tags above
        # are derived from it for queries; the payload lives in media_entry_payloads.
        sa.Column("lesson_meta", _json(), nullable=True),
        sa.Column("has_lesson", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("segment_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stored_bytes", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        *checks,
    )
    op.create_table(
        "media_entry_payloads",
        sa.Column(
            "media_id",
            sa.String(256),
            sa.ForeignKey("media_entries.media_id", ondelete="CASCADE", name="fk_media_entry_payloads_entry"),
            primary_key=True,
        ),
        sa.Column("payload", _json(), nullable=False),
    )
    # Shared browse: language, published, newest first, keyset-pageable.
    op.create_index(
        "ix_media_entries_browse", "media_entries",
        ["library", "language", "status", sa.text("created_at DESC"), sa.text("media_id DESC")],
    )
    # Operator listings (all languages, all statuses) and counts.
    op.create_index(
        "ix_media_entries_library_created", "media_entries",
        ["library", sa.text("created_at DESC"), sa.text("media_id DESC")],
    )
    # `resolve_by_lesson_id`. UNIQUE iff the import report shows no duplicate (MEDIA_METADATA_POSTGRES.md Q1); the
    # rehearsal and the import report decide, and this file is edited before it moves to versions/ if they do not.
    op.create_index(
        "ix_media_entries_lesson_id", "media_entries", ["lesson_id"], unique=True,
        postgresql_where=sa.text("library = 'shared' AND lesson_id IS NOT NULL"),
        sqlite_where=sa.text("library = 'shared' AND lesson_id IS NOT NULL"),
    )
    # A learner's uploads, the uploaded-media byte sum (covering: predicate and stored_bytes are both here), the
    # account-deletion remover, per-language listing. All-language paging orders by (language, created_at, media_id).
    op.create_index(
        "ix_media_entries_owner", "media_entries",
        ["owner_token", "language", sa.text("created_at DESC"), sa.text("media_id DESC")],
        postgresql_include=["stored_bytes"],
        postgresql_where=sa.text("library = 'personal'"),
        sqlite_where=sa.text("library = 'personal'"),
    )


def downgrade() -> None:
    """DROPS every media entry and payload. Rehearsal only."""
    op.drop_index("ix_media_entries_owner", table_name="media_entries")
    op.drop_index("ix_media_entries_lesson_id", table_name="media_entries")
    op.drop_index("ix_media_entries_library_created", table_name="media_entries")
    op.drop_index("ix_media_entries_browse", table_name="media_entries")
    op.drop_table("media_entry_payloads")
    op.drop_table("media_entries")
