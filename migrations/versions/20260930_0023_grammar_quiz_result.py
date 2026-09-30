"""The last quiz result beside a grammar point's completion (D4 item I11; D-104 H-4).

`grammar_progress.last_quiz_correct`, `last_quiz_total` (SMALLINT) and `last_quiz_at` (TIMESTAMPTZ), all NULL until
a quiz result is stored. Try-it-yourself results stay in the Writing/evaluator record and are not duplicated. The
`lesson_id` column holds a Grammar Lab point id; historical R5 rows keep their R5 id and are read through the
point's aliases (R5 is not revived as learner authority). A future Grammar API validates the published point before
accepting progress.

On PostgreSQL a CHECK keeps the three columns together and the score in range; SQLite (test backend only)
cannot add a CHECK to an existing table by ALTER, so there it is a repository invariant.

Review and gate. Proposal `docs/project/proposals/LEARNER_RECORDS_D4.md` (revision 3), independent architecture
review `LEARNER_RECORDS_D4.REVIEW.md` (APPROVE at revision 2), human decisions D-104 (2026-09-30). This file
is a PROPOSAL: it lives in `migrations/proposed/`, which Alembic does not read by default, so it is not a head and
triggers no startup refusal. It moves to `migrations/versions/` (one `git mv`, in chain order) only after the
PostgreSQL up/down/up rehearsal (`scripts/rehearse_learner_records_schema.py`) is recorded and the human authorizes
it. Startup never applies it (D-002); only `scripts/bootstrap_runtime_schema.py` does, after a backup.

Additive only. `downgrade()` DROPS learner data and exists for the rehearsal; a runtime holding learner data is
restored from backup, never downgraded (ORENA_ACCOUNT_DATA_ARCHITECTURE section 6).

Revision ID: 20260930_0023
Revises: 20260930_0022
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260930_0023"
down_revision = "20260930_0022"
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


_CHECK = (
    "(last_quiz_total IS NULL AND last_quiz_correct IS NULL AND last_quiz_at IS NULL)"
    " OR (last_quiz_total IS NOT NULL AND last_quiz_correct IS NOT NULL AND last_quiz_at IS NOT NULL"
    " AND last_quiz_total >= 1 AND last_quiz_correct >= 0 AND last_quiz_correct <= last_quiz_total)"
)


def upgrade() -> None:
    _lock_timeout()
    op.add_column("grammar_progress", sa.Column("last_quiz_correct", sa.SmallInteger(), nullable=True))
    op.add_column("grammar_progress", sa.Column("last_quiz_total", sa.SmallInteger(), nullable=True))
    op.add_column("grammar_progress", sa.Column("last_quiz_at", sa.DateTime(timezone=True), nullable=True))
    if op.get_context().dialect.name == "postgresql":
        op.create_check_constraint("ck_grammar_progress_quiz", "grammar_progress", _CHECK)


def downgrade() -> None:
    """DROPS every learner's stored grammar quiz result. Rehearsal only."""
    _lock_timeout()
    if op.get_context().dialect.name == "postgresql":
        op.drop_constraint("ck_grammar_progress_quiz", "grammar_progress", type_="check")
    op.drop_column("grammar_progress", "last_quiz_at")
    op.drop_column("grammar_progress", "last_quiz_total")
    op.drop_column("grammar_progress", "last_quiz_correct")
