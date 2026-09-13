"""Account incarnation, mutation receipts, change stream and the work aggregate.

PROPOSAL — reviewed at `69ceb53` (APPROVED WITH REQUIRED CHANGES) and revised
against those nine findings; awaiting re-review and then explicit schema
authorization per ORENA_ACCOUNT_DATA_ARCHITECTURE section 6. Eight tables.
Additive only: it creates new tables and touches no existing one, so old
readers are unaffected. Nothing applies it automatically — startup verifies the
schema and refuses, and `scripts/bootstrap_runtime_schema.py` is the only thing
that migrates.

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
        # The whole canonical command identity, persisted. A retry is compared
        # against these columns and against nothing taken from the request that
        # is retrying: reconstructing any part of a historical command from
        # current input lets a changed field pass as a match.
        sa.Column("language_code", sa.String(20), nullable=False),
        sa.Column("domain", sa.String(40), nullable=False),
        sa.Column("resource_id", sa.String(120), nullable=False),
        sa.Column("operation_id", sa.String(120), nullable=False),
        sa.Column("request_digest", sa.String(128), nullable=False),
        # The version the command was issued against, stored rather than
        # inferred. Inferring it assumed one command advances a work by exactly
        # one, which is true of drafts today and is not a property to rely on.
        sa.Column("expected_version", sa.Integer(), nullable=False),
        sa.Column("result_ref", sa.String(255), nullable=False),
        sa.Column("committed_version", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        # Version 0 is the creation case; a committed version is always real.
        sa.CheckConstraint("expected_version >= 0", name="ck_mutation_receipt_expected"),
        sa.CheckConstraint("committed_version >= 1", name="ck_mutation_receipt_committed"),
        sa.CheckConstraint("sequence >= 1", name="ck_mutation_receipt_sequence"),
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
        sa.CheckConstraint("sequence >= 1", name="ck_change_record_sequence_positive"),
        sa.CheckConstraint("object_version >= 1", name="ck_change_record_object_version"),
        # The stream's ordering guarantee, enforced rather than assumed - and
        # the pull's index. A separate index on the same two columns would be a
        # duplicate: the unique constraint already provides one, and the pull
        # reads the whole account stream because a language filter must not
        # skip changes in another language.
        sa.UniqueConstraint("incarnation_id", "sequence", name="uq_change_record_sequence"),
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
        sa.CheckConstraint("updated_sequence >= 1", name="ck_work_updated_sequence"),
        # A SourceRef is both halves or neither. A kind with no id names nothing
        # and an id with no kind cannot be resolved; either alone is a dangling
        # reference that reads as provenance.
        sa.CheckConstraint(
            "(source_kind = '') = (source_id = '')", name="ck_work_source_ref_integrity"
        ),
        # A revision of nothing. The repository refuses this before opening a
        # transaction; the constraint means nothing else can write it either.
        sa.CheckConstraint(
            "source_revision = '' OR source_id <> ''",
            name="ck_work_revision_needs_source",
        ),
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
            "evidence_version IS NULL OR evidence_version >= 1",
            name="ck_work_turn_evidence_version",
        ),
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
    #
    # An *occurrence*, not a fact about the pair. Meeting the same word twice
    # in one source is two occurrences, whether or not the focus differs, so
    # nothing here is unique over content. Identity is the row id; a retry is
    # made safe by the operation receipt rather than by a constraint that
    # cannot tell a retry from a second attachment.
    #
    # The foreign key is the saved word's id alone. A composite key on account
    # and language would need `saved_words` to carry a matching unique
    # constraint, and altering that owner table to manufacture one is outside
    # this migration; parent scope is therefore validated transactionally in
    # the repository, with cross-account and cross-language rejection tested.
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
        # Retained where known, so an occurrence can say which revision of a
        # source it points into rather than silently meaning "the latest".
        sa.Column("source_revision", sa.String(120), nullable=False, server_default=""),
        sa.Column("focus", sa.Text(), nullable=False, server_default=""),
        # A bounded stand-in for unbounded focus text, for reading and
        # comparison. Deliberately not part of any key.
        sa.Column("focus_digest", sa.String(64), nullable=False),
        sa.Column("reason", sa.String(40), nullable=False),
        # A relation has its own version: an occurrence can be corrected -
        # its focus refined, its availability changed - and a reader needs to
        # know which state it saw.
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        # Unknown by default. An origin nobody has checked is not the same as
        # one confirmed reachable, and defaulting to available asserts a fact
        # the row does not have.
        sa.Column("availability", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "availability IN ('available','unknown','unavailable')",
            name="ck_language_provenance_availability",
        ),
        sa.CheckConstraint("version >= 1", name="ck_language_provenance_version"),
        sa.CheckConstraint(
            "(source_kind = '') = (source_id = '')",
            name="ck_language_provenance_source_ref_integrity",
        ),
        # Source revision without a source is a reference to nothing.
        sa.CheckConstraint(
            "source_revision = '' OR source_id <> ''",
            name="ck_language_provenance_revision_needs_source",
        ),
        # No uniqueness over content. An occurrence is an event, and two
        # distinct operations that say exactly the same thing are two events -
        # the same word, met twice in one source, attended to the same way.
        # Deduplication belongs to the operation: the receipt in
        # `mutation_receipts` makes a *retry* replay its original occurrence,
        # while a genuinely different operation creates another. A semantic
        # unique constraint here would collapse the second case into the first
        # and there would be no way to tell them apart afterwards.
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
        # Nothing consumed yet is 0; a checkpoint never goes negative.
        sa.CheckConstraint(
            "consumed_through_sequence >= 0", name="ck_projection_checkpoint_sequence"
        ),
    )


def downgrade() -> None:
    op.drop_table("projection_checkpoints")
    op.drop_index("ix_language_provenance_scope", table_name="language_provenance")
    op.drop_table("language_provenance")
    op.drop_table("work_turns")
    op.drop_index("ix_works_scope_sequence", table_name="works")
    op.drop_table("works")
    op.drop_table("change_records")
    op.drop_index("ix_mutation_receipts_stream", table_name="mutation_receipts")
    op.drop_table("mutation_receipts")
    op.drop_table("account_streams")
    op.drop_index("uq_account_incarnation_active", table_name="account_incarnations")
    op.drop_table("account_incarnations")
