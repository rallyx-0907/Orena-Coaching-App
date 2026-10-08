"""Where the learner is in a piece of content: continuation on `library_items` (D4 item I4; D-104 H-12, Design B).

`place JSON NULL` and `place_at TIMESTAMPTZ NULL` on the relationship record, written on the `started`
relationship for reading, listening and book content and updated in place. It is navigation and progress state,
not learning evidence, and it deliberately produces no mutation receipt and no change record (no growth in the
receipt stream, which is reserved). Writing the place does NOT touch `version` or `updated_at`, so it can never
make a learner's pin, note or state PATCH conflict. `place_at` is the server-set time of the last place write and
orders the "continue" list.

A partial index serves that list. Both dialects carry the same predicate.

Review and gate. Proposal `docs/project/proposals/LEARNER_RECORDS_D4.md` (revision 3), independent architecture
review `LEARNER_RECORDS_D4.REVIEW.md` (APPROVE at revision 2), human decisions D-104 (2026-09-30). This file
is a PROPOSAL: it lives in `migrations/proposed/`, which Alembic does not read by default, so it is not a head and
triggers no startup refusal. It moves to `migrations/versions/` (one `git mv`, in chain order) only after the
PostgreSQL up/down/up rehearsal (`scripts/rehearse_learner_records_schema.py`) is recorded and the human authorizes
it. Startup never applies it (D-002); only `scripts/bootstrap_runtime_schema.py` does, after a backup.

Additive only. `downgrade()` DROPS learner data and exists for the rehearsal; a runtime holding learner data is
restored from backup, never downgraded (ORENA_ACCOUNT_DATA_ARCHITECTURE section 6).

Revision ID: 20260930_0022
Revises: 20260930_0021
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260930_0022"
down_revision = "20260930_0021"
branch_labels = None
depends_on = None


def _lock_timeout() -> None:
    """Bound the wait for the brief ACCESS EXCLUSIVE lock; PostgreSQL only.

    `SET LOCAL` lasts for the transaction, and `env.py` runs the whole chain in one
    transaction, so it also applies to any later revision applied in the same run.
    `op.get_context()` rather than `get_bind()`, so an offline (SQL-rendering) run works.
    """
    if op.get_context().dialect.name == "postgresql":
        op.execute("SET LOCAL lock_timeout = '5s'")


def upgrade() -> None:
    _lock_timeout()
    op.add_column("library_items", sa.Column("place", sa.JSON(), nullable=True))
    op.add_column("library_items", sa.Column("place_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_library_items_place",
        "library_items",
        ["user_id", "language_code", "place_at"],
        postgresql_where=sa.text("place IS NOT NULL"),
        sqlite_where=sa.text("place IS NOT NULL"),
    )


def downgrade() -> None:
    """DROPS every learner's saved place in every piece of content. Rehearsal only."""
    _lock_timeout()
    op.drop_index("ix_library_items_place", table_name="library_items")
    op.drop_column("library_items", "place_at")
    op.drop_column("library_items", "place")
