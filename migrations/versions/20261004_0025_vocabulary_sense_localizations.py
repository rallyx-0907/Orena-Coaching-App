"""Vocabulary localizations: a sense's meaning per support language (D-124; VOCABULARY_LOCALIZATION.md rev 2 §5).

A vocabulary sense (`vocabulary_entries`) exists once. The meaning a learner reads in their support language is a
separate, reusable record of that sense in that language, so adding a support language never duplicates the corpus and
never mutates a published sense: inserting a localization leaves the sense row and every published membership snapshot
as they are. Localizations are outside the snapshot contract (rev 2 §6).

One row per (sense, support language, source). Alternates from several sources are kept; exactly one is `selected` per
(sense, support language), enforced by a partial unique index. Changing the selection is an operator action recorded in
`selection_reason`; the replaced row stays, so the history is the rows themselves (review P1-2). Precedence between
sources is decided in code (`writing_coach/vocabulary_localization.py`), never by insert order.

Backfill: every existing `short_meanings` item whose (normalized primary) language is a support language and not the
sense's own language becomes a row. Origins map explicitly (`source`, `curated`, `dictionary`; `prepared` →
`legacy-prepared`, unverified; anything else → `legacy-unknown`). When one entry has several items in one language, the
highest-priority origin is selected (source > curated > dictionary > others) and the others are kept unselected. Glosses
over 160 characters are kept but marked `over_length` in `validation` (legacy content; the pipeline's own cap applies to
new rows). Entries are read in chunks. `short_meanings` is not altered. `saved_words` is untouched (AGENTS.md §7).

The migration runs in one transaction; it re-runs only after a downgrade (it is not idempotent against an existing
table). `validation` is JSONB on PostgreSQL (audit data, matching 0024's choice) and JSON on the SQLite test backend.

Review and gate. Proposal `docs/project/proposals/VOCABULARY_LOCALIZATION.md` rev 2, independent review
`VOCABULARY_LOCALIZATION.REVIEW.md` (APPROVE WITH CONDITIONS). This file is a PROPOSAL in `migrations/proposed/`, which
Alembic does not read, so it is not a head and triggers no startup refusal. It moves to `migrations/versions/` only after
the rehearsal and the human's authorization. It is parented on the current head 0023; if the 0024 media-entries proposal
is promoted first, this file is re-parented on it at promotion (the two tables are independent). Startup never applies it
(D-002). Schema first (operator step, after a backup), then code; the read path works with the table absent or empty.

`downgrade()` DROPS the table and every localization in it. It exists for rehearsal only.

Revision ID: 20261004_0025
Revises: 20260930_0023
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261004_0025"
down_revision = "20260930_0023"
branch_labels = None
depends_on = None

_CHUNK = 2000
_MAX_GLOSS = 160
# origin in short_meanings -> (source, method, priority); lower priority wins the selection.
_ORIGINS = {
    "source": ("source-list", "source", 0),
    "curated": ("curated", "curated", 1),
    "dictionary": ("cc-cedict", "dictionary", 2),
    "prepared": ("legacy-prepared", "pivot_translation", 3),
}
_UNKNOWN = ("legacy-unknown", "source", 4)


def _postgres() -> bool:
    return op.get_context().dialect.name == "postgresql"


def _primary(tag: object) -> str:
    return str(tag or "").strip().replace("_", "-").casefold().split("-", 1)[0]


def upgrade() -> None:
    pg = _postgres()
    json_type = postgresql.JSONB() if pg else sa.JSON()
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
        sa.Column("source_version", sa.String(120), nullable=False),
        sa.Column("method", sa.String(40), nullable=False),
        sa.Column("selected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("selection_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("validation", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("entry_id", "support_language", "source", name="uq_vocabulary_localization_source"),
        sa.CheckConstraint(
            "support_language <> '' AND gloss <> '' AND source <> '' AND source_version <> ''",
            name="ck_vocabulary_localization_identity",
        ),
        sa.CheckConstraint(
            "method IN ('source', 'curated', 'dictionary', 'pivot_translation', 'reviewed_batch')",
            name="ck_vocabulary_localization_method",
        ),
    )
    op.create_index(
        "uq_vocabulary_localization_selected",
        "vocabulary_sense_localizations",
        ["entry_id", "support_language"],
        unique=True,
        postgresql_where=sa.text("selected"),
        sqlite_where=sa.text("selected = 1"),
    )

    bind = op.get_bind()
    entries = sa.table(
        "vocabulary_entries",
        sa.column("id", sa.Uuid()),
        sa.column("language_code", sa.String()),
        sa.column("short_meanings", sa.JSON()),
    )
    # Typed, so the driver binds `validation` as JSON(B) rather than an unadaptable dict.
    localizations = sa.table(
        "vocabulary_sense_localizations",
        sa.column("id", sa.Uuid()),
        sa.column("entry_id", sa.Uuid()),
        sa.column("support_language", sa.String()),
        sa.column("gloss", sa.Text()),
        sa.column("source", sa.String()),
        sa.column("source_version", sa.String()),
        sa.column("method", sa.String()),
        sa.column("selected", sa.Boolean()),
        sa.column("selection_reason", sa.Text()),
        sa.column("validation", json_type),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(UTC)
    offset = 0
    while True:
        chunk = bind.execute(
            sa.select(entries.c.id, entries.c.language_code, entries.c.short_meanings)
            .order_by(entries.c.id).limit(_CHUNK).offset(offset)
        ).all()
        if not chunk:
            break
        offset += len(chunk)
        rows = []
        for entry_id, language, meanings in chunk:
            own = _primary(language)
            candidates: dict[tuple[str, str], tuple[int, str, str, str]] = {}
            for item in meanings if isinstance(meanings, list) else []:
                if not isinstance(item, dict):
                    continue
                support = _primary(item.get("language"))
                gloss = " ".join(str(item.get("text") or "").split())
                if not support or support in {own, "unknown"} or not gloss:
                    continue
                source, method, priority = _ORIGINS.get(str(item.get("origin") or "source").strip().casefold(), _UNKNOWN)
                key = (support, source)
                if key not in candidates:
                    candidates[key] = (priority, gloss, method, source)
            best: dict[str, tuple[int, str]] = {}
            for (support, source), (priority, *_rest) in candidates.items():
                if support not in best or priority < best[support][0]:
                    best[support] = (priority, source)
            for (support, source), (_priority, gloss, method, _source) in candidates.items():
                validation = {"backfilled_from": "short_meanings", "rule": "20261004_0025"}
                if len(gloss) > _MAX_GLOSS:
                    validation["over_length"] = True
                if source.startswith("legacy-"):
                    validation["verified"] = False
                rows.append({
                    "id": uuid.uuid4(),
                    "entry_id": entry_id,
                    "support_language": support,
                    "gloss": gloss,
                    "source": source,
                    "source_version": "legacy-short_meanings",
                    "method": method,
                    "selected": best[support][1] == source,
                    "selection_reason": "backfill: highest-priority origin" if best[support][1] == source else "",
                    "validation": validation,
                    "created_at": now,
                    "updated_at": now,
                })
        if rows:
            bind.execute(localizations.insert(), rows)


def downgrade() -> None:
    op.drop_index("uq_vocabulary_localization_selected", table_name="vocabulary_sense_localizations")
    op.drop_table("vocabulary_sense_localizations")
