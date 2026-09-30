"""Where a stored Dictation score came from (D4 item I18; D-103.2, D-104 H-14).

`listening_progress.score_source VARCHAR(12) NOT NULL DEFAULT 'client'`, values `client` or `server`. Every
existing row is `client`: its number was reported by the browser and cannot be re-derived (only the last answer is
kept). The server recomputes the score from the canonical line on each checked write and writes `server`; the next
server-verified check supersedes a `client` best, and a `client` number is never rewritten as if verified. No
CHECK: the application owns the two values.

Review and gate. Proposal `docs/project/proposals/LEARNER_RECORDS_D4.md` (revision 3), independent architecture
review `LEARNER_RECORDS_D4.REVIEW.md` (APPROVE at revision 2), human decisions D-104 (2026-09-30). This file
is a PROPOSAL: it lives in `migrations/proposed/`, which Alembic does not read by default, so it is not a head and
triggers no startup refusal. It moves to `migrations/versions/` (one `git mv`, in chain order) only after the
PostgreSQL up/down/up rehearsal (`scripts/rehearse_learner_records_schema.py`) is recorded and the human authorizes
it. Startup never applies it (D-002); only `scripts/bootstrap_runtime_schema.py` does, after a backup.

Additive only. `downgrade()` DROPS learner data and exists for the rehearsal; a runtime holding learner data is
restored from backup, never downgraded (ORENA_ACCOUNT_DATA_ARCHITECTURE section 6).

Revision ID: 20260930_0020
Revises: 20260930_0019
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260930_0020"
down_revision = "20260930_0019"
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
        "listening_progress",
        sa.Column("score_source", sa.String(12), nullable=False, server_default="client"),
    )


def downgrade() -> None:
    """DROPS the provenance of every stored Dictation score. Rehearsal only."""
    _lock_timeout()
    op.drop_column("listening_progress", "score_source")
