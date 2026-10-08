"""Practice session identity on Speaking attempts (D-141, D-142; PRACTICE_SESSION_IDENTITY.md).

Adds one nullable column, `speaking_attempts.practice_session_id`, minted by the server, and the index the "current
session" read needs. No default, no backfill, no constraint, no rewrite: every existing row keeps NULL (D-142.4). On
PostgreSQL a nullable column without a default is a metadata-only change.

Reversible: `downgrade()` drops the index, then the column, and loses only the identity (the attempts stay).
Old code ignores the column; new code tolerates NULL. Startup never applies this (D-002); it is applied only by the
operator under the human's gate, after a backup.

Revision ID: 20261007_0029
Revises: 20261004_0025
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261007_0029"
down_revision = "20261004_0025"
branch_labels = None
depends_on = None

INDEX = "ix_speaking_attempts_session"


def upgrade() -> None:
    op.add_column("speaking_attempts", sa.Column("practice_session_id", sa.Uuid(), nullable=True))
    op.create_index(
        INDEX,
        "speaking_attempts",
        ["user_id", "language_code", "practice_session_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(INDEX, table_name="speaking_attempts")
    op.drop_column("speaking_attempts", "practice_session_id")
