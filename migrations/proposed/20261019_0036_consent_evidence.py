"""Consent evidence and voice consent on the account row (D-233, PRE-005; D-229 clause 5).

Five columns on `users`, all additive, none rewriting data:

- `consent_version` (varchar 32, NULL = no record): the Terms / Privacy effective version the learner accepted
  (the deploy-stamped `LEGAL_EFFECTIVE_DATE`, `YYYY-MM-DD`; D-229 clause 3).
- `consent_accepted_at` (timestamptz, NULL = no record): when, by the server clock.
- `consent_language` (varchar 16, NULL = no record): the interface language the learner saw it in.
- `voice_consent` (boolean NOT NULL DEFAULT false): the learner allows their voice to be recorded and sent to an
  AI service. A constant default, so PostgreSQL 11+ adds the column without rewriting the table.
- `voice_consent_at` (timestamptz, NULL): when the voice answer last changed.

`users` SURVIVES account deletion (`account_incarnations.user_id -> users ON DELETE RESTRICT`), so the D-055 deletion
workflow RESETS these five (`persistence/deletion_enumeration.CONSENT_COLUMNS_TO_RESET`); nothing else removes them.
Account-wide, not per language; no history (a changed answer replaces the last). No ORM column maps them: the code
reads and writes them with raw statements guarded by a column-presence check (`persistence/consent_store.py`), so
this code runs, and records "no consent record", on a runtime that has not applied the revision yet. Merging the code
is therefore safe before the revision is applied; the endpoints record nothing until it is.

Safe on populated tables: five `ADD COLUMN`s, four nullable without default and one with a constant default, under
`lock_timeout`; no backfill, no index, no constraint. `users` is read on every request, so this is its own operator
step after a fresh `scripts/runtime_backup.py` backup, like 0018.

Status: PROPOSED. It lives in `migrations/proposed/`, which Alembic does not read, so it is not a head and triggers no
startup refusal. Schema change: an INDEPENDENT architecture review is required before promotion (AGENTS.md,
"Architecture review authority"), and promotion and application to any runtime are human gates. It is parented on
20261018_0035, the head of the day; Billing's proposed 0034 (parented on 0033 in the file) re-parents on whichever
revision is the head when it is promoted, and this one does likewise if 0034 is promoted first.

`downgrade()` DROPS every account's consent evidence and voice consent. It exists for the rehearsal; a runtime holding
consent records is restored from backup, never downgraded.

Revision ID: 20261019_0036
Revises: 20261018_0035
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261019_0036"
down_revision = "20261018_0035"
branch_labels = None
depends_on = None


def _lock_timeout() -> None:
    """Bound the wait for the brief ACCESS EXCLUSIVE lock; PostgreSQL only (as 0018)."""
    if op.get_context().dialect.name == "postgresql":
        op.execute("SET LOCAL lock_timeout = '5s'")


def upgrade() -> None:
    _lock_timeout()
    op.add_column("users", sa.Column("consent_version", sa.String(32), nullable=True))
    op.add_column("users", sa.Column("consent_accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("consent_language", sa.String(16), nullable=True))
    op.add_column("users", sa.Column("voice_consent", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("voice_consent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """DROPS every account's consent evidence and voice consent. Rehearsal only."""
    _lock_timeout()
    op.drop_column("users", "voice_consent_at")
    op.drop_column("users", "voice_consent")
    op.drop_column("users", "consent_language")
    op.drop_column("users", "consent_accepted_at")
    op.drop_column("users", "consent_version")
