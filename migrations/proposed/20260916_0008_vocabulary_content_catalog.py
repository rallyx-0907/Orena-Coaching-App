"""PROPOSAL - shared Vocabulary Source Import content catalog.

PENDING INDEPENDENT ARCHITECTURE REVIEW AND HUMAN SCHEMA/RUNTIME
AUTHORIZATION.  This file intentionally lives under ``migrations/proposed``;
it is not part of the live Alembic chain and must not be moved to
``migrations/versions`` until the named gate is complete.

Scope is shared content only: collections, reusable lexical entries, their
many-to-many memberships, and per-source import receipts.  It does not add a
SavedWord equivalent, learner progress, review history, an SRS scheduler, or
AI-generated enrichment.  Existing learner vocabulary state remains the owner
of save/review behaviour.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260916_0008"
down_revision = "20260912_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vocabulary_collections",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("language_code", sa.String(20), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("framework", sa.String(80), nullable=False),
        sa.Column("level", sa.String(80), nullable=False),
        sa.Column("level_range", sa.String(80), nullable=False),
        sa.Column("topic", sa.String(160), nullable=False),
        sa.Column("catalog_status", sa.String(30), nullable=False),
        sa.Column("origin", sa.String(40), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_vocabulary_collections_language_status",
        "vocabulary_collections",
        ["language_code", "catalog_status"],
    )

    op.create_table(
        "vocabulary_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("language_code", sa.String(20), nullable=False),
        sa.Column("term", sa.String(500), nullable=False),
        sa.Column("normalized_term", sa.String(500), nullable=False),
        sa.Column("identity_key", sa.String(900), nullable=False),
        sa.Column("sense_key", sa.String(240), nullable=False),
        sa.Column("pronunciations", sa.JSON(), nullable=False),
        sa.Column("readings", sa.JSON(), nullable=False),
        sa.Column("short_meanings", sa.JSON(), nullable=False),
        sa.Column("detailed_definitions", sa.JSON(), nullable=False),
        sa.Column("part_of_speech", sa.String(160), nullable=False),
        sa.Column("examples", sa.JSON(), nullable=False),
        sa.Column("usage_notes", sa.JSON(), nullable=False),
        sa.Column("orthography", sa.JSON(), nullable=False),
        sa.Column("level", sa.String(80), nullable=False),
        sa.Column("framework", sa.String(80), nullable=False),
        sa.Column("topic", sa.String(160), nullable=False),
        sa.Column("content_origins", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("identity_key", name="uq_vocabulary_entry_identity"),
    )
    op.create_index(
        "ix_vocabulary_entries_language_term",
        "vocabulary_entries",
        ["language_code", "normalized_term"],
    )

    op.create_table(
        "vocabulary_source_imports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "collection_id",
            sa.String(160),
            sa.ForeignKey("vocabulary_collections.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("source_format", sa.String(20), nullable=False),
        sa.Column("content_hash", sa.String(128), nullable=False),
        sa.Column("mapping", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("imported_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("warning_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.Column("imported_by", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_vocabulary_source_imports_collection_created",
        "vocabulary_source_imports",
        ["collection_id", "created_at"],
    )

    op.create_table(
        "vocabulary_collection_memberships",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "collection_id",
            sa.String(160),
            sa.ForeignKey("vocabulary_collections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entry_id",
            sa.Uuid(),
            sa.ForeignKey("vocabulary_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_import_id",
            sa.Uuid(),
            sa.ForeignKey("vocabulary_source_imports.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.UniqueConstraint(
            "collection_id", "entry_id", name="uq_vocabulary_collection_membership"
        ),
    )
    op.create_index(
        "ix_vocabulary_memberships_collection_position",
        "vocabulary_collection_memberships",
        ["collection_id", "position"],
    )
    op.create_index(
        "ix_vocabulary_memberships_entry",
        "vocabulary_collection_memberships",
        ["entry_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_vocabulary_memberships_entry",
        table_name="vocabulary_collection_memberships",
    )
    op.drop_index(
        "ix_vocabulary_memberships_collection_position",
        table_name="vocabulary_collection_memberships",
    )
    op.drop_table("vocabulary_collection_memberships")
    op.drop_index(
        "ix_vocabulary_source_imports_collection_created",
        table_name="vocabulary_source_imports",
    )
    op.drop_table("vocabulary_source_imports")
    op.drop_index(
        "ix_vocabulary_entries_language_term", table_name="vocabulary_entries"
    )
    op.drop_table("vocabulary_entries")
    op.drop_index(
        "ix_vocabulary_collections_language_status",
        table_name="vocabulary_collections",
    )
    op.drop_table("vocabulary_collections")
