"""Every table and column D4 touches is in the deletion enumeration D-055(b) needs (proposal 2.6, section 9)."""
from __future__ import annotations


from writing_coach.persistence import deletion_enumeration as enumeration
from writing_coach.persistence.models import Base

# What D4 added or gave learner-owned meaning to: table -> the columns it introduced (or None for the table).
D4_TOUCHED = {
    "users": ("learning_language", "interface_language", "weekly_goal_days", "settings_updated_at"),
    "user_language_profiles": ("declared_level", "review_new_per_day", "review_limit_per_day", "review_modes"),
    "grammar_progress": ("last_quiz_correct", "last_quiz_total", "last_quiz_at"),
    "listening_progress": ("score_source",),
    "library_items": ("place", "place_at"),
    "essay_review_history": None,
}
INCARNATION_TABLES = {"works", "work_turns", "mutation_receipts", "change_records", "language_provenance"}


def test_every_d4_column_is_a_real_orm_column_and_the_users_ones_are_reset_not_deleted():
    for table, columns in D4_TOUCHED.items():
        assert table in Base.metadata.tables, table
        for column in columns or ():
            assert column in Base.metadata.tables[table].c, (table, column)
    assert set(enumeration.USER_COLUMNS_TO_RESET) == set(D4_TOUCHED["users"])
    assert enumeration.USER_COLUMNS_TO_RESET["learning_language"] == ""
    assert enumeration.USER_COLUMNS_TO_RESET["weekly_goal_days"] is None


def test_every_touched_table_is_deleted_reset_or_cascaded():
    covered = set(enumeration.ACCOUNT_KEYED_TABLES) | set(enumeration.CASCADED_TABLES) | {"users"}
    for table in D4_TOUCHED:
        assert table in covered, f"{table} is missing from the deletion enumeration"


def test_the_cascaded_history_really_hangs_off_a_listed_table_with_a_cascade():
    parent = enumeration.CASCADED_TABLES["essay_review_history"]
    assert parent in enumeration.ACCOUNT_KEYED_TABLES
    foreign_keys = Base.metadata.tables["essay_review_history"].foreign_keys
    assert {(fk.column.table.name, fk.ondelete) for fk in foreign_keys} == {(parent, "CASCADE")}


def test_incarnation_keyed_tables_are_listed_because_their_cascade_does_not_fire():
    assert set(enumeration.INCARNATION_KEYED_TABLES) == INCARNATION_TABLES
    for table in INCARNATION_TABLES:
        assert table in enumeration.INCARNATION_KEYED_TABLES


def test_the_account_keyed_tables_are_keyed_by_the_account():
    for table in enumeration.ACCOUNT_KEYED_TABLES:
        assert "user_id" in Base.metadata.tables[table].c, table
