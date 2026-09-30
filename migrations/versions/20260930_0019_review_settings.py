"""Review modes and limits, per learning language (D4 item I13).

Named columns on `user_language_profiles` (ADA section 1: profile updates patch named supported fields), NULL =
"the client defaults":

- `review_new_per_day`, `review_limit_per_day`: whole numbers, clamped by the application to the bounds the
  client uses (`static/orena/product/recall-modes.js`).
- `review_modes`: a JSON object of booleans keyed by the modes the staging Review draws (`target`, `cloze`); any
  other key is dropped by the application (D-103.1: recall modes with no frame retire).

Review and gate. Proposal `docs/project/proposals/LEARNER_RECORDS_D4.md` (revision 3), independent architecture
review `LEARNER_RECORDS_D4.REVIEW.md` (APPROVE at revision 2), human decisions D-104 (2026-09-30). This file
is a PROPOSAL: it lives in `migrations/proposed/`, which Alembic does not read by default, so it is not a head and
triggers no startup refusal. It moves to `migrations/versions/` (one `git mv`, in chain order) only after the
PostgreSQL up/down/up rehearsal (`scripts/rehearse_learner_records_schema.py`) is recorded and the human authorizes
it. Startup never applies it (D-002); only `scripts/bootstrap_runtime_schema.py` does, after a backup.

Additive only. `downgrade()` DROPS learner data and exists for the rehearsal; a runtime holding learner data is
restored from backup, never downgraded (ORENA_ACCOUNT_DATA_ARCHITECTURE section 6).

Revision ID: 20260930_0019
Revises: 20260930_0018
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260930_0019"
down_revision = "20260930_0018"
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
    op.add_column("user_language_profiles", sa.Column("review_new_per_day", sa.SmallInteger(), nullable=True))
    op.add_column("user_language_profiles", sa.Column("review_limit_per_day", sa.SmallInteger(), nullable=True))
    op.add_column("user_language_profiles", sa.Column("review_modes", sa.JSON(), nullable=True))


def downgrade() -> None:
    """DROPS every learner's stored review settings. Rehearsal only."""
    _lock_timeout()
    op.drop_column("user_language_profiles", "review_modes")
    op.drop_column("user_language_profiles", "review_limit_per_day")
    op.drop_column("user_language_profiles", "review_new_per_day")
