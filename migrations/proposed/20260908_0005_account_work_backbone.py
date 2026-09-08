"""Account incarnation, mutation receipts, change stream and the work aggregate.

PROPOSAL — awaiting Codex architecture review and explicit schema authorization
per ORENA_ACCOUNT_DATA_ARCHITECTURE section 6. Additive only: it creates new
tables and touches no existing one, so old readers are unaffected. Nothing
applies it automatically — startup verifies the schema and refuses, and
`scripts/bootstrap_runtime_schema.py` is the only thing that migrates.

Ordered as the migration list in ORENA_BACKBONE_INTEGRATION_GATES requires:
incarnation, receipt and stream primitives first, then work and its turns, then
provenance and the projection checkpoint that read on top of them.

Revision ID: 20260908_0005
Revises: 20260828_0004
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260908_0005"
down_revision = "20260828_0004"
branch_labels = None
depends_on = None

LIFECYCLE = ("active", "completed", "deleted")
CHANGE_KINDS = ("upsert", "delete")
AUTHOR_ROLES = ("learner", "partner")


def upgrade() -> None:
    # ---- 1. Account incarnation, and the durable deletion barrier ----------
    # The external identity mapping stays on `users`. An incarnation is the
    # access epoch: deleting an account leaves its row here as a barrier, and
    # re-registration creates the next epoch rather than reactivating the old
    # one. Everything scoped below hangs off the incarnation, not the user, so
    # a recreated account cannot inherit commands, receipts, cursors or work.
    op.create_table(
        "account_incarnations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("epoch", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("epoch >= 1", name="ck_account_incarnation_epoch"),
        sa.CheckConstraint("status IN ('active','deleted')", name="ck_account_incarnation_status"),
        sa.CheckConstraint(
            "(status = 'deleted') = (deleted_at IS NOT NULL)",
            name="ck_account_incarnation_deleted_at",
        ),
        sa.UniqueConstraint("user_id", "epoch", name="uq_account_incarnation_epoch"),
    )
    # RESTRICT above, and this partial index, are the barrier: at most one
    # active incarnation per account, and a deleted one cannot be removed by a
    # cascade while it is still denying reactivation.
    op.create_index(
        "uq_account_incarnation_active",
        "account_incarnations",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    # ---- 2. The per-incarnation change stream head ------------------------
    # One row per incarnation, locked FOR UPDATE and held until commit, so the
    # next change sequence is allocated in the same transaction as the domain
    # write. A database sequence allocated outside commit order is insufficient
    # because it can be consumed by a transaction that later rolls back.
    op.create_table(
        "account_streams",
        sa.Column(
            "incarnation_id",
            sa.Uuid(),
            sa.ForeignKey("account_incarnations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("next_sequence", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("next_sequence >= 1", name="ck_account_stream_sequence"),
    )

    # ---- 3. Mutation receipts ---------------------------------------------
    # Scoped operation identity, unique. `operation_id` identifies one logical
    # action, not one HTTP try, so a retry finds this row and returns the same
    # committed result. `request_digest` is the guard against reusing an
    # operation id with different input - it is not the identity, because two
    # distinct attempts must not be deduplicated merely because their text is
    # equal.
    op.create_table(
        "mutation_receipts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "incarnation_id",
            sa.Uuid(),
            sa.ForeignKey("account_incarnations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("domain", sa.String(40), nullable=False),
        sa.Column("operation_id", sa.String(120), nullable=False),
        sa.Column("request_digest", sa.String(128), nullable=False),
        sa.Column("result_ref", sa.String(255), nullable=False),
        sa.Column("committed_version", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "incarnation_id", "domain", "operation_id", name="uq_mutation_receipt_operation"
        ),
    )
    # Compaction reads oldest-first while preserving deduplication for every
    # still-valid operation.
    op.create_index(
        "ix_mutation_receipts_stream",
        "mutation_receipts",
        ["incarnation_id", "sequence"],
    )

    # ---- 4. Change records and tombstones ---------------------------------
    # One row per committed change, carrying the sequence allocated under the
    # stream lock. Deletion emits a record here in the same transaction that
    # increments the object's version, so an older update cannot resurrect it.
    op.create_table(
        "change_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "incarnation_id",
            sa.Uuid(),
            sa.ForeignKey("account_incarnations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("language_code", sa.String(20), nullable=False),
        sa.Column("object_domain", sa.String(40), nullable=False),
        sa.Column("object_id", sa.String(120), nullable=False),
        sa.Column("object_version", sa.Integer(), nullable=False),
        sa.Column("change_kind", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "change_kind IN ('upsert','delete')", name="ck_change_record_kind"
        ),
        # The stream's ordering guarantee, enforced rather than assumed.
        sa.UniqueConstraint("incarnation_id", "sequence", name="uq_change_record_sequence"),
    )
    # A language filter must not skip changes in another language, so the pull
    # index is the whole account stream; language is a column to read, not the
    # leading key.
    op.create_index(
        "ix_change_records_pull",
        "change_records",
        ["incarnation_id", "sequence"],
    )

    # ---- 5. The work aggregate --------------------------------------------
    # Drafts, responses and conversations - the mutable work that currently
    # lives only in device memory. Submitted snapshots and their evaluator
    # results stay where they are, on `essays`/`essay_revisions`: this does not
    # move an evidence owner and holds no second copy of one.
    op.create_table(
        "works",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "incarnation_id",
            sa.Uuid(),
            sa.ForeignKey("account_incarnations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language_code", sa.String(20), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("source_kind", sa.String(40), nullable=False, server_default=""),
        sa.Column("source_id", sa.String(200), nullable=False, server_default=""),
        sa.Column("source_revision", sa.String(120), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("lifecycle", sa.String(20), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("updated_sequence", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version >= 1", name="ck_work_version"),
        sa.CheckConstraint(
            "lifecycle IN ('active','completed','deleted')", name="ck_work_lifecycle"
        ),
        # Parent isolation: a turn joins on all three columns, so a child can
        # never be attached across an incarnation or a language.
        sa.UniqueConstraint(
            "id", "incarnation_id", "language_code", name="uq_work_scope_identity"
        ),
    )
    # Work lists page by account + language + updated sequence, with the id as
    # the tie-break so a cursor is stable.
    op.create_index(
        "ix_works_scope_sequence",
        "works",
        ["incarnation_id", "language_code", "updated_sequence", "id"],
    )

    op.create_table(
        "work_turns",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("incarnation_id", sa.Uuid(), nullable=False),
        sa.Column("language_code", sa.String(20), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("author_role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_revision", sa.String(120), nullable=False, server_default=""),
        # An acknowledged evidence reference, when this turn produced one. It
        # points at the owning domain's record; it is not a copy of it.
        sa.Column("evidence_domain", sa.String(40), nullable=True),
        sa.Column("evidence_id", sa.String(120), nullable=True),
        sa.Column("evidence_version", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("ordinal >= 1", name="ck_work_turn_ordinal"),
        sa.CheckConstraint(
            "author_role IN ('learner','partner')", name="ck_work_turn_author"
        ),
        sa.CheckConstraint(
            "(evidence_domain IS NULL) = (evidence_id IS NULL) AND "
            "(evidence_id IS NULL) = (evidence_version IS NULL)",
            name="ck_work_turn_evidence_complete",
        ),
        sa.ForeignKeyConstraint(
            ["work_id", "incarnation_id", "language_code"],
            ["works.id", "works.incarnation_id", "works.language_code"],
            name="fk_work_turn_parent_scope",
            ondelete="CASCADE",
        ),
        # Turns are contiguous and immutable; an expected head cannot be
        # satisfied twice.
        sa.UniqueConstraint("work_id", "ordinal", name="uq_work_turn_ordinal"),
    )

    # ---- 6. Kept-language provenance --------------------------------------
    # The route back and the reason, beside the saved word rather than inside
    # it: `saved_words` owns the word and its review schedule and has no column
    # for where the learner met it. Deleting provenance does not grade or
    # delete a review.
    op.create_table(
        "language_provenance",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "incarnation_id",
            sa.Uuid(),
            sa.ForeignKey("account_incarnations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language_code", sa.String(20), nullable=False),
        sa.Column(
            "saved_word_id",
            sa.Uuid(),
            sa.ForeignKey("saved_words.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_kind", sa.String(40), nullable=False, server_default=""),
        sa.Column("source_id", sa.String(200), nullable=False, server_default=""),
        sa.Column("focus", sa.Text(), nullable=False, server_default=""),
        sa.Column("reason", sa.String(40), nullable=False),
        sa.Column("availability", sa.String(20), nullable=False, server_default="available"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "availability IN ('available','unknown','unavailable')",
            name="ck_language_provenance_availability",
        ),
        # One relation per saved object and source; meeting a word again in a
        # different place is a separate relationship, not an overwrite.
        sa.UniqueConstraint(
            "saved_word_id", "source_kind", "source_id", name="uq_language_provenance_source"
        ),
    )
    op.create_index(
        "ix_language_provenance_scope",
        "language_provenance",
        ["incarnation_id", "language_code", "saved_word_id"],
    )

    # ---- 7. Projection checkpoints ----------------------------------------
    # Discardable by definition: a checkpoint records how far a projection has
    # consumed, and dropping it costs a rebuild, never source evidence.
    op.create_table(
        "projection_checkpoints",
        sa.Column(
            "incarnation_id",
            sa.Uuid(),
            sa.ForeignKey("account_incarnations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("language_code", sa.String(20), primary_key=True),
        sa.Column("policy_version", sa.String(40), primary_key=True),
        sa.Column("consumed_through_sequence", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("projection_checkpoints")
    op.drop_index("ix_language_provenance_scope", table_name="language_provenance")
    op.drop_table("language_provenance")
    op.drop_table("work_turns")
    op.drop_index("ix_works_scope_sequence", table_name="works")
    op.drop_table("works")
    op.drop_index("ix_change_records_pull", table_name="change_records")
    op.drop_table("change_records")
    op.drop_index("ix_mutation_receipts_stream", table_name="mutation_receipts")
    op.drop_table("mutation_receipts")
    op.drop_table("account_streams")
    op.drop_index("uq_account_incarnation_active", table_name="account_incarnations")
    op.drop_table("account_incarnations")
