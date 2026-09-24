"""The ORM's canonical Reading schema is the migration's, on SQLite.

The hermetic suite builds SQLite from `Base.metadata.create_all`, and the
runtime gets its schema from migration `20260924_0014`. Two paths to one schema
drift unless something compares them, so this does:

- the ORM's copy of the SQLite triggers is the migration's list, verbatim;
- a database built by `create_all`, and the same database taken down by the
  migration's `downgrade()` and back up by its `upgrade()`, have the same
  tables, columns, nullability, indexes and triggers.

Constraint *names* are allowed to differ where SQLite cannot keep one across a
table rebuild; what each constraint refuses is proved in
`tests/test_adaptive_reading_schema.py` on both paths.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("alembic")
import sqlalchemy as sa  # noqa: E402
from sqlalchemy import create_engine, event, text  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "versions" / "20260924_0014_adaptive_reading.py"
CANONICAL = (
    "reading_articles",
    "reading_comprehension_sets",
    "reading_comprehension_questions",
    "reading_attempts",
    "reading_ability_projections",
    "reading_legacy_sessions",
    "reading_legacy_attempts",
)


def _migration():
    spec = importlib.util.spec_from_file_location("adaptive_reading_parity", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _engine(path: Path):
    engine = create_engine(f"sqlite+pysqlite:///{path}", future=True)

    @event.listens_for(engine, "connect")
    def _foreign_keys(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    return engine


def _run(engine, step: str) -> None:
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext

    module = _migration()
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            getattr(module, step)()


def _shape(engine) -> dict:
    inspector = sa.inspect(engine)
    shape: dict = {}
    for table in CANONICAL:
        shape[table] = {
            "columns": {
                column["name"]: (str(column["type"]).upper(), bool(column["nullable"]))
                for column in inspector.get_columns(table)
            },
            "indexes": {
                (index["name"], tuple(index["column_names"]), bool(index["unique"]))
                for index in inspector.get_indexes(table)
            },
            "foreign_keys": {
                (tuple(key["constrained_columns"]), key["referred_table"], tuple(key["referred_columns"]),
                 (key.get("options") or {}).get("ondelete"))
                for key in inspector.get_foreign_keys(table)
            },
        }
    with engine.connect() as connection:
        shape["triggers"] = {
            row.name: " ".join(row.sql.split())
            for row in connection.execute(text("SELECT name, sql FROM sqlite_master WHERE type = 'trigger'"))
        }
    return shape


def test_the_orm_trigger_list_is_the_migrations_verbatim():
    from writing_coach.persistence.reading_evidence_ddl import SQLITE_TRIGGERS

    assert tuple(SQLITE_TRIGGERS) == tuple(_migration()._SQLITE_TRIGGERS)


def test_create_all_and_the_migration_build_the_same_canonical_schema(tmp_path):
    from writing_coach.persistence.models import Base

    engine = _engine(tmp_path / "parity.db")
    try:
        Base.metadata.create_all(engine)
        built = _shape(engine)
        _run(engine, "downgrade")
        with engine.connect() as connection:
            left = connection.execute(text(
                "SELECT count(*) FROM sqlite_master WHERE type = 'trigger' AND name LIKE 'reading_%'")).scalar_one()
        assert left == 0, "the downgrade leaves no canonical trigger behind"
        _run(engine, "upgrade")
        migrated = _shape(engine)
    finally:
        engine.dispose()
    assert set(built["triggers"]) == set(migrated["triggers"])
    for name, sql in built["triggers"].items():
        assert sql == migrated["triggers"][name], name
    for table in CANONICAL:
        assert built[table]["columns"] == migrated[table]["columns"], table
        assert built[table]["foreign_keys"] == migrated[table]["foreign_keys"], table
        # Index names match; SQLite reports the same unique/partial indexes by
        # name whichever path created them.
        assert built[table]["indexes"] == migrated[table]["indexes"], table
