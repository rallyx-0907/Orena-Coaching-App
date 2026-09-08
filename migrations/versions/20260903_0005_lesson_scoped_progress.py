"""Scope Listening and Shadowing progress to a lesson, not to a media asset.

Revision ID: 20260903_0005
Revises: 20260828_0004

One source can carry several curated excerpts. Keyed by asset_id, progress in
excerpt A made excerpt B look already started, and the two shared a row whenever
they shared a segment. Progress belongs to the LESSON the learner was working
in; asset_id stays as provenance.

Backfill rule, and the reason for it: a legacy row is associated with a lesson
ONLY when its asset maps to exactly one lesson. If the asset maps to none, or to
several, the row keeps lesson_id = "" and stays legacy/unassigned. Picking the
first or newest lesson would manufacture a certainty the data does not contain,
and would silently attach somebody's real work to the wrong excerpt.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260903_0005"
down_revision = "20260828_0004"
branch_labels = None
depends_on = None

TABLES = ("listening_progress", "shadowing_progress")

# The old constraint/index names, per table.
OLD_UNIQUE = {
    "listening_progress": "uq_listening_progress_scope_segment",
    "shadowing_progress": "uq_shadowing_progress_scope_segment",
}
NEW_UNIQUE = {
    "listening_progress": "uq_listening_progress_scope_lesson_segment",
    "shadowing_progress": "uq_shadowing_progress_scope_lesson_segment",
}
NEW_LESSON_INDEX = {
    "listening_progress": "ix_listening_progress_user_language_lesson",
    "shadowing_progress": "ix_shadowing_progress_user_language_lesson",
}


def _unambiguous_asset_lessons() -> dict[str, str]:
    """asset_id -> lesson_id, only where exactly one lesson uses that asset.

    Read from the catalog the application itself loads, so the migration and the
    runtime agree about what a lesson is.
    """

    from writing_coach.listening_catalog import load_catalog

    _sources, lessons = load_catalog()
    by_asset: dict[str, list[str]] = {}
    for lesson in lessons:
        by_asset.setdefault(lesson.source.source_media_id, []).append(lesson.lesson_id)
    return {
        asset: found[0]
        for asset, found in by_asset.items()
        if len(found) == 1
    }


def upgrade() -> None:
    for table in TABLES:
        op.add_column(
            table,
            sa.Column("lesson_id", sa.String(255), nullable=False, server_default=""),
        )

    # Backfill before the new uniqueness exists, so a legacy duplicate surfaces
    # as a migration failure rather than as silently merged learner progress.
    mapping = _unambiguous_asset_lessons()
    connection = op.get_bind()
    for table in TABLES:
        for asset_id, lesson_id in mapping.items():
            connection.execute(
                sa.text(
                    f"UPDATE {table} SET lesson_id = :lesson_id "  # noqa: S608 - fixed names
                    "WHERE asset_id = :asset_id AND lesson_id = ''"
                ),
                {"lesson_id": lesson_id, "asset_id": asset_id},
            )

    for table in TABLES:
        op.drop_constraint(OLD_UNIQUE[table], table, type_="unique")
        op.create_unique_constraint(
            NEW_UNIQUE[table], table,
            ["user_id", "language_code", "lesson_id", "segment_id"],
        )
        op.create_index(
            NEW_LESSON_INDEX[table], table,
            ["user_id", "language_code", "lesson_id"],
        )

    # Continue Learning orders by recency for one learner and language.
    op.create_index(
        "ix_listening_progress_user_language_updated",
        "listening_progress",
        ["user_id", "language_code", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_listening_progress_user_language_updated", table_name="listening_progress")
    for table in TABLES:
        op.drop_index(NEW_LESSON_INDEX[table], table_name=table)
        op.drop_constraint(NEW_UNIQUE[table], table, type_="unique")
        # Two lessons of one asset may hold rows that collide once lesson_id is
        # gone, so the old constraint cannot always be restored. Dropping the
        # column keeps the schema coherent and loses only the lesson scoping
        # this revision added; the by-asset rows themselves survive.
        op.drop_column(table, "lesson_id")
    for table in TABLES:
        op.create_unique_constraint(
            OLD_UNIQUE[table], table,
            ["user_id", "language_code", "asset_id", "segment_id"],
        )
