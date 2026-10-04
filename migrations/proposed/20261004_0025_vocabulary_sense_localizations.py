"""Vocabulary localizations: one row per (sense, support language) (D-124; VOCABULARY_LOCALIZATION.md §5).

A vocabulary sense (`vocabulary_entries`) exists once. The meaning a learner reads in their support language is a
separate, reusable record keyed by (sense, support language), so adding a support language never duplicates the corpus
and never mutates a published sense: inserting a localization leaves the sense row and every published snapshot as they
are.

Additive only. The backfill copies every existing `short_meanings` item whose language is not the sense's own language
into a row (`source` from the item's `origin`, `method` derived from it), skipping duplicates, so the read path can move
to this table without losing a gloss. `short_meanings` is not altered: it keeps the source corpus's own meanings.
`saved_words.translation_vi` is untouched (learner data; AGENTS.md §7 hold).

Review and gate. Proposal `docs/project/proposals/VOCABULARY_LOCALIZATION.md`. This file is a PROPOSAL in
`migrations/proposed/`, which Alembic does not read, so it is not a head and triggers no startup refusal. It moves to
`migrations/versions/` only after independent architecture review and the human's authorization; its `down_revision` is
settled then against the open 0024 media-entries proposal and the deferred Grammar slot. Startup never applies it (D-002).

`downgrade()` DROPS the table and every localization in it. It exists for rehearsal only.

Revision ID: 20261004_0025
Revises: 20261001_0024
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "20261004_0025"
down_revision = "20261001_0024"
branch_labels = None
depends_on = None

_METHOD_BY_ORIGIN = {"source": "source", "dictionary": "dictionary", "prepared": "pivot_translation"}


def upgrade() -> None:
    op.create_table(
        "vocabulary_sense_localizations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "entry_id",
            sa.Uuid(),
            sa.ForeignKey("vocabulary_entries.id", ondelete="CASCADE", name="fk_vocabulary_localization_entry"),
            nullable=False,
        ),
        sa.Column("support_language", sa.String(20), nullable=False),
        sa.Column("gloss", sa.Text(), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("source_version", sa.String(120), nullable=False, server_default=""),
        sa.Column("method", sa.String(40), nullable=False),
        sa.Column("validation", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("entry_id", "support_language", name="uq_vocabulary_localization_sense_language"),
        sa.CheckConstraint(
            "support_language <> '' AND gloss <> '' AND source <> ''",
            name="ck_vocabulary_localization_identity",
        ),
        sa.CheckConstraint(
            "method IN ('source', 'curated', 'dictionary', 'pivot_translation', 'reviewed_batch')",
            name="ck_vocabulary_localization_method",
        ),
    )
    op.create_index(
        "ix_vocabulary_localizations_language",
        "vocabulary_sense_localizations",
        ["support_language", "entry_id"],
    )

    bind = op.get_bind()
    entries = sa.table(
        "vocabulary_entries",
        sa.column("id", sa.Uuid()),
        sa.column("language_code", sa.String()),
        sa.column("short_meanings", sa.JSON()),
    )
    localizations = sa.table(
        "vocabulary_sense_localizations",
        sa.column("id", sa.Uuid()),
        sa.column("entry_id", sa.Uuid()),
        sa.column("support_language", sa.String()),
        sa.column("gloss", sa.Text()),
        sa.column("source", sa.String()),
        sa.column("source_version", sa.String()),
        sa.column("method", sa.String()),
        sa.column("validation", sa.JSON()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(UTC)
    rows = []
    for entry_id, language, meanings in bind.execute(
        sa.select(entries.c.id, entries.c.language_code, entries.c.short_meanings)
    ):
        own = str(language or "").strip().casefold()
        seen: set[str] = set()
        for item in meanings if isinstance(meanings, list) else []:
            if not isinstance(item, dict):
                continue
            support = str(item.get("language") or "").strip().casefold()
            gloss = " ".join(str(item.get("text") or "").split())
            if not support or support in {own, "unknown"} or not gloss or support in seen:
                continue
            seen.add(support)
            origin = str(item.get("origin") or "source").strip().casefold()
            rows.append(
                {
                    "id": uuid.uuid4(),
                    "entry_id": entry_id,
                    "support_language": support,
                    "gloss": gloss,
                    "source": "source-list" if origin == "source" else origin,
                    "source_version": "",
                    "method": _METHOD_BY_ORIGIN.get(origin, "source"),
                    "validation": {"backfilled_from": "short_meanings", "rule": "20261004_0025"},
                    "created_at": now,
                    "updated_at": now,
                }
            )
    if rows:
        op.bulk_insert(localizations, rows)


def downgrade() -> None:
    op.drop_index("ix_vocabulary_localizations_language", table_name="vocabulary_sense_localizations")
    op.drop_table("vocabulary_sense_localizations")
