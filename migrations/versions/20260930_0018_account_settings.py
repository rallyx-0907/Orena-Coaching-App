"""Account-wide learner settings on the `users` row (D4 items I2, I3, I3b; D-104 H-18, H-17).

`users` is the account row and it SURVIVES account deletion (`account_incarnations.user_id -> users ON DELETE
RESTRICT`), so the D-055(b) deletion workflow must RESET these columns to their defaults; nothing else removes
them (proposal section 2.6).

- `learning_language` ('' = never chosen): seeds a session that has no language; not per-language.
- `interface_language` ('' = follow the device).
- `weekly_goal_days` (NULL = not set): target study days per week, 1-7 validated by the application.
- `settings_updated_at` (NULL = never written): the server-owned version token of the account scalars. A
  conditional update compares it (`WHERE settings_updated_at IS NOT DISTINCT FROM :expected`) and a stale token is a
  409; a client timestamp never resolves a conflict (D-104 H-17). TIMESTAMPTZ has microsecond resolution.

`users` is written on every sign-in and read by every request, so this is its own operator step, after a fresh
`scripts/runtime_backup.py` backup, under `lock_timeout`.

Review and gate. Proposal `docs/project/proposals/LEARNER_RECORDS_D4.md` (revision 3), independent architecture
review `LEARNER_RECORDS_D4.REVIEW.md` (APPROVE at revision 2), human decisions D-104 (2026-09-30). This file
is a PROPOSAL: it lives in `migrations/proposed/`, which Alembic does not read by default, so it is not a head and
triggers no startup refusal. It moves to `migrations/versions/` (one `git mv`, in chain order) only after the
PostgreSQL up/down/up rehearsal (`scripts/rehearse_learner_records_schema.py`) is recorded and the human authorizes
it. Startup never applies it (D-002); only `scripts/bootstrap_runtime_schema.py` does, after a backup.

Additive only. `downgrade()` DROPS learner data and exists for the rehearsal; a runtime holding learner data is
restored from backup, never downgraded (ORENA_ACCOUNT_DATA_ARCHITECTURE section 6).

Revision ID: 20260930_0018
Revises: 20260930_0017
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260930_0018"
down_revision = "20260930_0017"
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
    op.add_column("users", sa.Column("learning_language", sa.String(20), nullable=False, server_default=""))
    op.add_column("users", sa.Column("interface_language", sa.String(8), nullable=False, server_default=""))
    op.add_column("users", sa.Column("weekly_goal_days", sa.SmallInteger(), nullable=True))
    op.add_column("users", sa.Column("settings_updated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """DROPS every account's stored language choices, weekly goal and settings token. Rehearsal only."""
    _lock_timeout()
    op.drop_column("users", "settings_updated_at")
    op.drop_column("users", "weekly_goal_days")
    op.drop_column("users", "interface_language")
    op.drop_column("users", "learning_language")
