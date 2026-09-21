"""Record whether a hint was used in the last checked Dictation attempt (D-068, D-069, DC-5).

Two additive columns on the segment's progress row: `last_used_hint` and `last_hint_level`, with a CHECK
that the level is 0-3 and that the flag is exactly "level above zero". They describe the last checked
attempt the way `last_answer` does. They are a fact about the attempt and carry no scoring rule.

Existing rows read as "no hint used" through the server defaults, so the upgrade needs no backfill, and
on PostgreSQL 11+ adding a NOT NULL column with a constant default is a metadata change. This revision
sits on top of 20260916_0008 and 20260916_0009 (the chain is linear).

An older client does not send the fields, so its save writes "no hint, level 0" for the segment: the same
replace-the-aggregate behaviour `last_answer` has.

Downgrade drops the two columns and with them the stored hint facts. After writes have happened, the
account data architecture prefers turning the writes off and repairing forward to down-migrating learner
data away; the downgrade exists for a rehearsal, not for a live account.

Revision ID: 20260921_0010
Revises: 20260916_0009
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260921_0010"
down_revision = "20260916_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "listening_progress",
        sa.Column("last_used_hint", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "listening_progress",
        sa.Column("last_hint_level", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_listening_progress_hint_level", "listening_progress", "last_hint_level BETWEEN 0 AND 3"
    )
    op.create_check_constraint(
        "ck_listening_progress_hint_flag", "listening_progress", "last_used_hint = (last_hint_level > 0)"
    )


def downgrade() -> None:
    op.drop_constraint("ck_listening_progress_hint_flag", "listening_progress", type_="check")
    op.drop_constraint("ck_listening_progress_hint_level", "listening_progress", type_="check")
    op.drop_column("listening_progress", "last_hint_level")
    op.drop_column("listening_progress", "last_used_hint")
