"""The D4 ORM equals the migrated schema (0017-0023), column for column (proposal section 15).

PostgreSQL only: the migrated head is the authority and the ORM mirror is what `create_all` builds for
the hermetic suite, so a drift between them would let SQLite tests pass against a shape production
does not have.
"""
from __future__ import annotations

import pytest
from sqlalchemy import inspect

from writing_coach.persistence.models import Base

D4_COLUMNS = {
    "users": ("learning_language", "interface_language", "weekly_goal_days", "settings_updated_at"),
    "user_language_profiles": ("declared_level", "review_new_per_day", "review_limit_per_day", "review_modes"),
    "listening_progress": ("score_source",),
    "library_items": ("place", "place_at"),
    "grammar_progress": ("last_quiz_correct", "last_quiz_total", "last_quiz_at"),
}


def _kind(type_) -> str:
    text = str(type_).upper()
    text = text.replace("DATETIME", "TIMESTAMP")
    for name in ("SMALLINT", "INTEGER", "VARCHAR", "TIMESTAMP", "JSON", "UUID", "BOOLEAN", "TEXT"):
        if name in text:
            return name
    return text


@pytest.mark.parametrize("table", sorted(D4_COLUMNS))
def test_every_d4_column_matches_the_migrated_type_length_and_nullability(pg_engine, table):
    live = {column["name"]: column for column in inspect(pg_engine).get_columns(table)}
    for name in D4_COLUMNS[table]:
        orm = Base.metadata.tables[table].c[name]
        assert name in live, f"{table}.{name} is not in the migrated schema"
        assert _kind(orm.type) == _kind(live[name]["type"]), (table, name, orm.type, live[name]["type"])
        assert orm.nullable == live[name]["nullable"], (table, name)
        if hasattr(orm.type, "length") and orm.type.length and hasattr(live[name]["type"], "length"):
            assert orm.type.length == live[name]["type"].length, (table, name)


def test_the_history_table_matches_and_has_no_scope_columns(pg_engine):
    live = {column["name"]: column for column in inspect(pg_engine).get_columns("essay_review_history")}
    orm = Base.metadata.tables["essay_review_history"]
    assert set(live) == set(orm.c.keys()) == {
        "id", "essay_id", "superseded_at", "reason", "prior_fingerprint", "prior_contract",
        "replaced_by_fingerprint", "review",
    }
    assert "user_id" not in live and "language_code" not in live
    assert all(orm.c[name].nullable == live[name]["nullable"] for name in live)
    uniques = {tuple(item["column_names"]) for item in inspect(pg_engine).get_unique_constraints("essay_review_history")}
    assert ("essay_id", "prior_fingerprint") in uniques
    assert {index["name"] for index in inspect(pg_engine).get_indexes("essay_review_history")} >= {"ix_essay_review_history_essay"}


def test_the_named_indexes_and_the_quiz_check_exist_under_the_orm_names(pg_engine):
    library = {index["name"] for index in inspect(pg_engine).get_indexes("library_items")}
    assert "ix_library_items_place" in library
    orm_checks = {c.name for c in Base.metadata.tables["grammar_progress"].constraints if getattr(c, "name", None)}
    live_checks = {c["name"] for c in inspect(pg_engine).get_check_constraints("grammar_progress")}
    assert "ck_grammar_progress_quiz" in orm_checks and "ck_grammar_progress_quiz" in live_checks


def test_place_and_review_modes_are_declared_none_as_null():
    assert Base.metadata.tables["library_items"].c.place.type.none_as_null is True
    assert Base.metadata.tables["user_language_profiles"].c.review_modes.type.none_as_null is True
