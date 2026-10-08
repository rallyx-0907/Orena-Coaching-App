"""The grammar content store: shared, immutable, admin-published grammar content (D-105.4, D-106).

Proposal `docs/project/proposals/GRAMMAR_CONTENT_STORE.md` (revision 3, sections 3-4). Grammar Lab is upstream: an
approved export package (`grammar-export-profile/1`) is imported through Admin into immutable version rows, accepted,
rights-attested and published there, and learners read the published version through `/api/grammar/v1/*`. Nothing
here is learner data and nothing here ships content with the source.

Eight new tables, nothing else:

- `grammar_import_batches`  the receipt of one upload (imported or rejected), with the manifest (no point bodies),
                            the diff, the refusals and the batch rights attestation (which may come after the import).
- `grammar_functions`       Library group labels (`fn.<snake>`), language-neutral.
- `grammar_points`          one row per point id: identity, lifecycle and the serving projection of the published
                            version (NULL until the first publish; a CHECK requires it while published).
- `grammar_point_versions`  the immutable content, one row per (point, version). One published version per point is
                            a partial unique index; "published only when accepted and cleared" is a CHECK. The review
                            verdict (`imported | accepted | rejected`) is separate from serving state (`is_published`,
                            `superseded_at`), so a superseded version stays `accepted` and can be republished (rollback).
- `grammar_r5_map`          old R5 lesson id -> point, written at batch commit and independent of publish state.
                            One resolution (a primary row or a dropped row) per R5 id is a partial unique index.
- `grammar_point_error_tags` the published version's error tags, the `by-error` read path.
- `grammar_review_events`   append-only decision history, written in the same transaction as the change.
- `grammar_catalog_state`   the per-language catalogue revision (the ETag source). No seed row: a language without a
                            row reads as revision 0, so no language is named here.

Invariants:

- **No existing table is altered, and no foreign key points at an existing table.** `grammar_progress` (learner
  progress, 0023) is reused as it is and gets no foreign key to these tables; a point archived later must not cascade
  into a learner's history. The migration therefore takes no lock on any learner table.
- **Foreign keys are cycle-free**: batches <- functions <- points <- versions/map/tags/events. No table points back.
- **Immutability.** On PostgreSQL a row trigger rejects any UPDATE of a version's content columns (`point_id`,
  `version`, `content`, `content_hash`, `source_status`, `provenance`, `batch_id`, `imported_at`) and any DELETE of a
  version; only `review_status`, `is_published`, `superseded_at`, `rights_status` and `reviewed_*` move.
  `grammar_review_events` is append-only (UPDATE and DELETE rejected). Nothing cascades into either table, so a DELETE
  trigger blocks no cascade.
  `content` and `provenance` are `json`, which has no equality operator: they are compared as `CAST(... AS text)`, the
  byte-identity semantics 20260924_0015 established (a rewrite with another key order is refused, by design). On any
  other dialect (SQLite, the hermetic test backend) the same rule is a repository invariant.

Reversible: `downgrade()` drops the triggers, their functions and the eight tables. They hold shared content only,
re-importable from the export packages; no learner row is touched. The R5 map is content too: dropping it loses
old-id resolution until the packages are re-imported (proposal section 16).

Review and gate. Proposal revision 3a, independent architecture review APPROVE at `b3ee8f09`
(`GRAMMAR_CONTENT_STORE.REV3.INDEPENDENT_REVIEW.md`), rehearsed on a throwaway PostgreSQL 16
(`scripts/rehearse_grammar_content_store.py`, `GRAMMAR_CONTENT_STORE.REHEARSAL.md`). Promoted from
`migrations/proposed/` on 2026-10-08 on the human's authorization, in source control only: it is applied to no runtime
by this change. Startup never applies it (D-002); only `scripts/bootstrap_runtime_schema.py` does, after a backup, on
the runtime the human names. A PostgreSQL runtime that takes code at or after this revision refuses to start until it
is applied (the readiness check compares the database with this head).

Revision ID: 20261008_0030
Revises: 20261007_0029
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261008_0030"
down_revision = "20261007_0029"
branch_labels = None
depends_on = None

LIFECYCLES = ("unpublished", "published", "archived")
REVIEW_STATUSES = ("imported", "accepted", "rejected")  # the verdict; supersession is serving state, below
RIGHTS_STATUSES = ("unknown", "cleared", "restricted")
RIGHTS_BASES = ("orena_original", "licensed", "other")
BATCH_STATUSES = ("imported", "rejected")
DISPOSITIONS = ("replaced", "merged", "split_primary", "split_secondary", "dropped")
PRIMARY_DISPOSITIONS = ("replaced", "merged", "split_primary")
EVENT_ACTIONS = (
    "imported", "accepted", "rejected", "rights_set", "rights_attested", "published", "unpublished", "archived",
    "restored", "function_label_changed", "r5_map_changed",
)

# Every table this revision creates, in creation order (foreign keys point only backwards in this list).
TABLES = (
    "grammar_import_batches",
    "grammar_functions",
    "grammar_points",
    "grammar_point_versions",
    "grammar_r5_map",
    "grammar_point_error_tags",
    "grammar_review_events",
    "grammar_catalog_state",
)


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


# The serving projection exists exactly while a point is published (proposal section 3; review P2-4).
_PUBLISHED_HAS_PROJECTION = (
    "lifecycle <> 'published' OR (function_id IS NOT NULL AND level_framework IS NOT NULL AND level_value IS NOT NULL"
    " AND level_rank IS NOT NULL AND sequence IS NOT NULL AND point_type IS NOT NULL AND native_title IS NOT NULL"
    " AND published_at IS NOT NULL)"
)

# `CAST(x AS text)`, not `x::text`: `op.execute` takes the string as SQLAlchemy text, which reads `:name` as a bind.
_VERSION_IMMUTABLE_FUNCTION = """
CREATE OR REPLACE FUNCTION grammar_point_version_is_immutable() RETURNS trigger AS $func$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'grammar_point_versions % is immutable content and is never deleted', OLD.id
            USING ERRCODE = '23514';
    END IF;
    IF NEW.id IS DISTINCT FROM OLD.id
       OR NEW.point_id IS DISTINCT FROM OLD.point_id
       OR NEW.version IS DISTINCT FROM OLD.version
       OR CAST(NEW.content AS text) IS DISTINCT FROM CAST(OLD.content AS text)
       OR NEW.content_hash IS DISTINCT FROM OLD.content_hash
       OR NEW.source_status IS DISTINCT FROM OLD.source_status
       OR CAST(NEW.provenance AS text) IS DISTINCT FROM CAST(OLD.provenance AS text)
       OR NEW.batch_id IS DISTINCT FROM OLD.batch_id
       OR NEW.imported_at IS DISTINCT FROM OLD.imported_at
    THEN
        RAISE EXCEPTION 'grammar_point_versions % is immutable content: import a new version upstream instead', OLD.id
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$func$ LANGUAGE plpgsql
"""

_VERSION_IMMUTABLE_TRIGGER = """
CREATE TRIGGER grammar_point_version_immutable
BEFORE UPDATE OR DELETE ON grammar_point_versions
FOR EACH ROW EXECUTE FUNCTION grammar_point_version_is_immutable()
"""

_EVENTS_APPEND_ONLY_FUNCTION = """
CREATE OR REPLACE FUNCTION grammar_review_event_is_append_only() RETURNS trigger AS $func$
BEGIN
    RAISE EXCEPTION 'grammar_review_events % is append-only', OLD.id
        USING ERRCODE = '23514';
END;
$func$ LANGUAGE plpgsql
"""

_EVENTS_APPEND_ONLY_TRIGGER = """
CREATE TRIGGER grammar_review_event_append_only
BEFORE UPDATE OR DELETE ON grammar_review_events
FOR EACH ROW EXECUTE FUNCTION grammar_review_event_is_append_only()
"""


def upgrade() -> None:
    op.create_table(
        "grammar_import_batches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False),
        # NULL only on a `rejected` receipt whose manifest could not be read (CHECK below).
        sa.Column("language_code", sa.String(20), nullable=True),
        sa.Column("package_hash", sa.String(64), nullable=True),
        sa.Column("export_profile", sa.String(60), nullable=True),
        sa.Column("profile_schema_hash", sa.String(64), nullable=True),
        sa.Column("schema_version", sa.String(20), nullable=True),
        sa.Column("set_version", sa.String(120), nullable=True),
        sa.Column("source_commit", sa.String(64), nullable=True),
        sa.Column("exported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("filename", sa.String(255), nullable=False, server_default=""),
        sa.Column("new_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("changed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unchanged_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("refused_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unlisted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("diff", sa.JSON(), nullable=True),
        sa.Column("refusals", sa.JSON(), nullable=True),
        # The manifest without point bodies: validator verdict, r5_map, per-point provenance, rights policy.
        sa.Column("manifest", sa.JSON(), nullable=True),
        # The batch rights attestation (section 6, review N-4): given at commit or later, after the diff is read.
        sa.Column("rights_basis", sa.String(40), nullable=True),
        sa.Column("rights_attestation", sa.Text(), nullable=True),
        sa.Column("rights_attested_by", sa.String(255), nullable=True),
        sa.Column("rights_attested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("imported_by", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(f"status IN ({_in(BATCH_STATUSES)})", name="ck_grammar_import_batches_status"),
        sa.CheckConstraint(
            "status <> 'imported' OR (language_code IS NOT NULL AND package_hash IS NOT NULL"
            " AND export_profile IS NOT NULL AND profile_schema_hash IS NOT NULL AND schema_version IS NOT NULL"
            " AND set_version IS NOT NULL AND source_commit IS NOT NULL AND exported_at IS NOT NULL"
            " AND manifest IS NOT NULL)",
            name="ck_grammar_import_batches_imported_complete",
        ),
        sa.CheckConstraint(
            "(rights_basis IS NULL AND rights_attestation IS NULL AND rights_attested_by IS NULL"
            " AND rights_attested_at IS NULL)"
            f" OR (rights_basis IN ({_in(RIGHTS_BASES)}) AND rights_attestation IS NOT NULL"
            " AND rights_attested_by IS NOT NULL AND rights_attested_at IS NOT NULL AND status = 'imported')",
            name="ck_grammar_import_batches_rights",
        ),
        sa.CheckConstraint(
            "new_count >= 0 AND changed_count >= 0 AND unchanged_count >= 0 AND refused_count >= 0"
            " AND unlisted_count >= 0",
            name="ck_grammar_import_batches_counts",
        ),
    )
    # `already_imported` is answered only for an imported batch; a corrected re-upload of a rejected file is new.
    op.create_index(
        "uq_grammar_import_batches_package",
        "grammar_import_batches",
        ["package_hash"],
        unique=True,
        postgresql_where=sa.text("status = 'imported'"),
        sqlite_where=sa.text("status = 'imported'"),
    )
    op.create_index("ix_grammar_import_batches_recent", "grammar_import_batches", ["created_at", "id"])

    op.create_table(
        "grammar_functions",
        sa.Column("id", sa.String(120), primary_key=True),
        sa.Column("title", sa.JSON(), nullable=False),
        sa.Column(
            "batch_id", sa.Uuid(), sa.ForeignKey("grammar_import_batches.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "grammar_points",
        sa.Column("id", sa.String(120), primary_key=True),
        sa.Column("language_code", sa.String(20), nullable=False),
        sa.Column("lifecycle", sa.String(20), nullable=False, server_default="unpublished"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unpublished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # Serving projection of the published version; NULL until the first publish, rewritten by each publish.
        sa.Column(
            "function_id", sa.String(120), sa.ForeignKey("grammar_functions.id", ondelete="RESTRICT"), nullable=True
        ),
        sa.Column("level_framework", sa.String(20), nullable=True),
        sa.Column("level_value", sa.String(20), nullable=True),
        sa.Column("level_rank", sa.SmallInteger(), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=True),
        sa.Column("point_type", sa.String(40), nullable=True),
        sa.Column("native_title", sa.Text(), nullable=True),
        sa.Column("native_title_pinyin", sa.JSON(), nullable=True),
        sa.CheckConstraint(f"lifecycle IN ({_in(LIFECYCLES)})", name="ck_grammar_points_lifecycle"),
        # `<lang>.<slug>`: the id carries its language, and the row agrees with it.
        sa.CheckConstraint(
            "substr(id, 1, length(language_code) + 1) = language_code || '.'", name="ck_grammar_points_id_language"
        ),
        sa.CheckConstraint(_PUBLISHED_HAS_PROJECTION, name="ck_grammar_points_published_projection"),
    )
    op.create_index(
        "ix_grammar_points_catalog",
        "grammar_points",
        ["language_code", "lifecycle", "level_rank", "function_id", "sequence"],
    )

    op.create_table(
        "grammar_point_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "point_id", sa.String(120), sa.ForeignKey("grammar_points.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("source_status", sa.String(20), nullable=False),
        sa.Column("review_status", sa.String(20), nullable=False, server_default="imported"),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        # When a later publish replaced this version; NULL while published or never published. Not a review verdict.
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rights_status", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column(
            "batch_id", sa.Uuid(), sa.ForeignKey("grammar_import_batches.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_by", sa.String(255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.UniqueConstraint("point_id", "version", name="uq_grammar_point_versions_version"),
        sa.UniqueConstraint("point_id", "content_hash", name="uq_grammar_point_versions_hash"),
        sa.CheckConstraint("version >= 1", name="ck_grammar_point_versions_version"),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_grammar_point_versions_hash"),
        sa.CheckConstraint("source_status = 'approved'", name="ck_grammar_point_versions_source"),
        sa.CheckConstraint(f"review_status IN ({_in(REVIEW_STATUSES)})", name="ck_grammar_point_versions_review"),
        sa.CheckConstraint(f"rights_status IN ({_in(RIGHTS_STATUSES)})", name="ck_grammar_point_versions_rights"),
        # The publish gate as a database fact (D-105.5a, D-106.6): only an accepted, cleared version is served.
        sa.CheckConstraint(
            "is_published = false OR (review_status = 'accepted' AND rights_status = 'cleared')",
            name="ck_grammar_point_versions_publishable",
        ),
        sa.CheckConstraint(
            "is_published = false OR superseded_at IS NULL", name="ck_grammar_point_versions_superseded"
        ),
    )
    # One published version per point (review P2-2: no foreign key from the point to a version).
    op.create_index(
        "uq_grammar_point_versions_published",
        "grammar_point_versions",
        ["point_id"],
        unique=True,
        postgresql_where=sa.text("is_published"),
        sqlite_where=sa.text("is_published"),
    )
    op.create_index("ix_grammar_point_versions_review", "grammar_point_versions", ["review_status", "imported_at"])
    op.create_index("ix_grammar_point_versions_batch", "grammar_point_versions", ["batch_id"])

    op.create_table(
        "grammar_r5_map",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("language_code", sa.String(20), nullable=False),
        sa.Column("r5_id", sa.String(255), nullable=False),
        sa.Column(
            "point_id", sa.String(120), sa.ForeignKey("grammar_points.id", ondelete="RESTRICT"), nullable=True
        ),
        sa.Column("disposition", sa.String(20), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column(
            "batch_id", sa.Uuid(), sa.ForeignKey("grammar_import_batches.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(f"disposition IN ({_in(DISPOSITIONS)})", name="ck_grammar_r5_map_disposition"),
        sa.CheckConstraint(
            "(disposition = 'dropped' AND point_id IS NULL) OR (disposition <> 'dropped' AND point_id IS NOT NULL)",
            name="ck_grammar_r5_map_dropped",
        ),
        sa.CheckConstraint(
            f"(is_primary = true AND disposition IN ({_in(PRIMARY_DISPOSITIONS)}))"
            " OR (is_primary = false AND disposition IN ('split_secondary', 'dropped'))",
            name="ck_grammar_r5_map_primary",
        ),
        sa.UniqueConstraint("language_code", "r5_id", "point_id", name="uq_grammar_r5_map_piece"),
    )
    # One resolution per R5 id: a primary row OR a dropped row, never two, never both (review N-3, at the database).
    op.create_index(
        "uq_grammar_r5_map_resolution",
        "grammar_r5_map",
        ["language_code", "r5_id"],
        unique=True,
        postgresql_where=sa.text("is_primary OR point_id IS NULL"),
        sqlite_where=sa.text("is_primary OR point_id IS NULL"),
    )
    op.create_index("ix_grammar_r5_map_point", "grammar_r5_map", ["point_id"])

    op.create_table(
        "grammar_point_error_tags",
        sa.Column(
            "point_id", sa.String(120), sa.ForeignKey("grammar_points.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("error_tag", sa.String(80), nullable=False),
        sa.Column("has_mistake", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.PrimaryKeyConstraint("point_id", "error_tag", name="pk_grammar_point_error_tags"),
    )
    op.create_index("ix_grammar_point_error_tags_tag", "grammar_point_error_tags", ["error_tag"])

    op.create_table(
        "grammar_review_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "point_id", sa.String(120), sa.ForeignKey("grammar_points.id", ondelete="RESTRICT"), nullable=True
        ),
        sa.Column(
            "version_id", sa.Uuid(), sa.ForeignKey("grammar_point_versions.id", ondelete="RESTRICT"), nullable=True
        ),
        sa.Column(
            "batch_id", sa.Uuid(), sa.ForeignKey("grammar_import_batches.id", ondelete="RESTRICT"), nullable=True
        ),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("changes", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(f"action IN ({_in(EVENT_ACTIONS)})", name="ck_grammar_review_events_action"),
    )
    op.create_index("ix_grammar_review_events_point", "grammar_review_events", ["point_id", "created_at"])
    op.create_index("ix_grammar_review_events_batch", "grammar_review_events", ["batch_id", "created_at"])

    op.create_table(
        "grammar_catalog_state",
        sa.Column("language_code", sa.String(20), primary_key=True),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("revision >= 0", name="ck_grammar_catalog_state_revision"),
    )

    if op.get_context().dialect.name == "postgresql":
        op.execute(_VERSION_IMMUTABLE_FUNCTION)
        op.execute(_VERSION_IMMUTABLE_TRIGGER)
        op.execute(_EVENTS_APPEND_ONLY_FUNCTION)
        op.execute(_EVENTS_APPEND_ONLY_TRIGGER)


def downgrade() -> None:
    """Drops the grammar content store (shared content only, re-importable). No learner table is touched."""
    if op.get_context().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS grammar_review_event_append_only ON grammar_review_events")
        op.execute("DROP FUNCTION IF EXISTS grammar_review_event_is_append_only()")
        op.execute("DROP TRIGGER IF EXISTS grammar_point_version_immutable ON grammar_point_versions")
        op.execute("DROP FUNCTION IF EXISTS grammar_point_version_is_immutable()")
    for table in reversed(TABLES):
        op.drop_table(table)
