"""The learner kept this review to read again (D-072.1).

One nullable timestamp on `essays`. A review has exactly one essay, and the
essay row is already the learner-scoped, language-scoped record
(`uq_essay_legacy_scope`), so curation needs no table of its own and no new
cascade: deleting the user still cascades from `users`.

NULL means "not kept" - the truth for every row written before this column
existed - so the upgrade needs no backfill. Adding a nullable column without a
default is a catalog-only change on PostgreSQL and takes no table rewrite.

A timestamp rather than a boolean: it answers "kept" and "since when", and the
saved-review list orders by it.

Nothing reads the column until the Writing room's saved-review list does, so
this revision is safe to apply ahead of the interface.

Downgrade drops the column and with it the learner's curation. After writes
have happened the account data architecture prefers repairing forward; the
downgrade exists for a rehearsal, not for a live account.

Revision ID: 20260922_0011
Revises: 20260921_0010
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260922_0011"
down_revision = "20260921_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "essays",
        sa.Column("review_kept_at", sa.DateTime(timezone=True), nullable=True),
    )
    # The saved-review list reads "this learner's kept reviews, newest first".
    # Partial, so the index holds only kept rows rather than every essay.
    op.create_index(
        "ix_essays_review_kept",
        "essays",
        ["user_id", "language_code", "review_kept_at"],
        postgresql_where=sa.text("review_kept_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_essays_review_kept", table_name="essays")
    op.drop_column("essays", "review_kept_at")
