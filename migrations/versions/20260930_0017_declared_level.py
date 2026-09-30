"""The learner's declared level, per learning language (H2, merged into D4 as item I1).

`user_language_profiles.declared_level VARCHAR(20) NOT NULL DEFAULT ''`: a level code from the language
registry of the row's language, or '' meaning "not declared". Validation lives in the application against the
registry (no DB enum or CHECK), so a future language needs no schema change. Design:
`docs/project/proposals/DECLARED_LEVEL_STORAGE.md` sections 1-9.

Review and gate. Proposal `docs/project/proposals/LEARNER_RECORDS_D4.md` (revision 3), independent architecture
review `LEARNER_RECORDS_D4.REVIEW.md` (APPROVE at revision 2), human decisions D-104 (2026-09-30). This file
is a PROPOSAL: it lives in `migrations/proposed/`, which Alembic does not read by default, so it is not a head and
triggers no startup refusal. It moves to `migrations/versions/` (one `git mv`, in chain order) only after the
PostgreSQL up/down/up rehearsal (`scripts/rehearse_learner_records_schema.py`) is recorded and the human authorizes
it. Startup never applies it (D-002); only `scripts/bootstrap_runtime_schema.py` does, after a backup.

Additive only. `downgrade()` DROPS learner data and exists for the rehearsal; a runtime holding learner data is
restored from backup, never downgraded (ORENA_ACCOUNT_DATA_ARCHITECTURE section 6).

Revision ID: 20260930_0017
Revises: 20260924_0016
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260930_0017"
down_revision = "20260924_0016"
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
    op.add_column(
        "user_language_profiles",
        sa.Column("declared_level", sa.String(20), nullable=False, server_default=""),
    )


def downgrade() -> None:
    """DROPS every learner's declared level. Rehearsal only."""
    _lock_timeout()
    op.drop_column("user_language_profiles", "declared_level")
