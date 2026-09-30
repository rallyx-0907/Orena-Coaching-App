"""The previous review of an essay, kept as immutable history (D4 item I19; D-103.7).

When an old Chinese essay is refreshed under the current evaluator, the review it replaces is inserted here first,
in the same transaction that updates the essay: audit evidence, not learner work. `essays` still holds the
current review; no learner revision is created.

- `UNIQUE (essay_id, prior_fingerprint)` makes a refresh idempotent under concurrency: a second writer of the
  same prior review is refused, so one prior review is one history row.
- `review` is the whole prior review (dimension scores, overall, level estimate, evaluator, summary, strengths,
  strength evidence, priorities, errors, grammar links) as JSON.
- **Scope is the parent's.** The table carries no `user_id` or `language_code` of its own (delta review P2-4): a copy
  could disagree with the essay's, and a composite foreign key would need a new unique key on `essays`. Every read goes
  through the essay, which is already scope-checked (`get_essay`). The one foreign key cascades: deleting an essay, or
  the account's essays, deletes its history. That is intended; the history is the learner's own record of that essay.
  The D-055(b) workflow deletes the account's `essays` explicitly because the `users` row survives, and the history
  follows them.
- Immutability. On PostgreSQL a BEFORE UPDATE row trigger rejects any UPDATE (precedent: 20260924_0015's
  reading source snapshot). It is UPDATE only: a DELETE trigger would block the ON DELETE CASCADE above. On any
  other dialect the same rule is a repository invariant (insert and read only) with a test that asserts it.

Review and gate. Proposal `docs/project/proposals/LEARNER_RECORDS_D4.md` (revision 3), independent architecture
review `LEARNER_RECORDS_D4.REVIEW.md` (APPROVE at revision 2), human decisions D-104 (2026-09-30). This file
is a PROPOSAL: it lives in `migrations/proposed/`, which Alembic does not read by default, so it is not a head and
triggers no startup refusal. It moves to `migrations/versions/` (one `git mv`, in chain order) only after the
PostgreSQL up/down/up rehearsal (`scripts/rehearse_learner_records_schema.py`) is recorded and the human authorizes
it. Startup never applies it (D-002); only `scripts/bootstrap_runtime_schema.py` does, after a backup.

Additive only. `downgrade()` DROPS learner data and exists for the rehearsal; a runtime holding learner data is
restored from backup, never downgraded (ORENA_ACCOUNT_DATA_ARCHITECTURE section 6).

Revision ID: 20260930_0021
Revises: 20260930_0020
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260930_0021"
down_revision = "20260930_0020"
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


_TRIGGER_FUNCTION = """
CREATE OR REPLACE FUNCTION essay_review_history_is_immutable() RETURNS trigger AS $func$
BEGIN
    RAISE EXCEPTION 'essay review history % is immutable', OLD.id
        USING ERRCODE = 'integrity_constraint_violation';
END;
$func$ LANGUAGE plpgsql
"""

_TRIGGER = """
CREATE TRIGGER essay_review_history_immutable
BEFORE UPDATE ON essay_review_history
FOR EACH ROW EXECUTE FUNCTION essay_review_history_is_immutable()
"""


def upgrade() -> None:
    _lock_timeout()
    op.create_table(
        "essay_review_history",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("essay_id", sa.Uuid(), sa.ForeignKey("essays.id", ondelete="CASCADE"), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(40), nullable=False),
        sa.Column("prior_fingerprint", sa.String(64), nullable=False),
        sa.Column("prior_contract", sa.String(40), nullable=False),
        sa.Column("replaced_by_fingerprint", sa.String(64), nullable=False),
        sa.Column("review", sa.JSON(), nullable=False),
        sa.UniqueConstraint("essay_id", "prior_fingerprint", name="uq_essay_review_history_prior"),
    )
    op.create_index(
        "ix_essay_review_history_essay",
        "essay_review_history",
        ["essay_id", "superseded_at"],
    )
    if op.get_context().dialect.name == "postgresql":
        op.execute(_TRIGGER_FUNCTION)
        op.execute(_TRIGGER)


def downgrade() -> None:
    """DROPS every essay's review history (audit evidence). Rehearsal only."""
    _lock_timeout()
    if op.get_context().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS essay_review_history_immutable ON essay_review_history")
        op.execute("DROP FUNCTION IF EXISTS essay_review_history_is_immutable()")
    op.drop_index("ix_essay_review_history_essay", table_name="essay_review_history")
    op.drop_table("essay_review_history")
