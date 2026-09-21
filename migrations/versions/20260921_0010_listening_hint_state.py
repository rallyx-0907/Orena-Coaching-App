"""Record whether a hint was used in the last checked Dictation attempt (D-068, DC-5).

Two columns on the segment's progress row: `last_used_hint` and `last_hint_level`. They describe the last
checked attempt the way `last_answer` does. They are a fact about the attempt and carry no scoring rule.
Existing rows read as "no hint used" (the server defaults), so the upgrade needs no backfill.

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


def downgrade() -> None:
    op.drop_column("listening_progress", "last_hint_level")
    op.drop_column("listening_progress", "last_used_hint")
