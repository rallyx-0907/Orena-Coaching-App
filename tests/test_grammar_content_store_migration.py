"""The grammar content store migration (20261008_0030; GRAMMAR_CONTENT_STORE.md revision 3a).

Hermetic, on SQLite (the CI backend): where the file lives and what it chains on, that it creates the eight content
tables and nothing else, that its database-level rules hold on this dialect too, that its downgrade returns the
schema exactly, and that the ORM models (`create_all`, the hermetic test schema) say what the migration says. The
PostgreSQL proof (triggers, locks, 100,000 progress rows, read plans, the ETag read order) is
`scripts/rehearse_grammar_content_store.py`, run by hand on a throwaway database.

History: the migration was a proposal behind an architecture gate (issue #99) until the independent review approved
revision 3a (PR #100) and the human authorized its promotion into `migrations/versions/` (2026-10-08, source control
only; it is applied to no runtime by that change).
"""
from __future__ import annotations

import importlib.util
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[1]
NAME = "20261008_0030_grammar_content_store.py"
MIGRATION = ROOT / "migrations" / "versions" / NAME
TABLES = {
    "grammar_import_batches", "grammar_functions", "grammar_points", "grammar_point_versions", "grammar_r5_map",
    "grammar_point_error_tags", "grammar_review_events", "grammar_catalog_state",
}
NOW = datetime(2026, 10, 8, tzinfo=UTC)


def _migration():
    spec = importlib.util.spec_from_file_location("migration_0030", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _script() -> ScriptDirectory:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("path_separator", "os")
    return ScriptDirectory.from_config(cfg)


def _apply(engine, step: str) -> None:
    with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        getattr(_migration(), step)()


def _schema(engine) -> set[tuple]:
    with engine.connect() as connection:
        return set(connection.execute(sa.text("SELECT type, name, tbl_name, sql FROM sqlite_master")).all())


def _without_grammar(engine) -> None:
    from writing_coach.persistence.models import Base

    Base.metadata.create_all(engine, tables=[t for name, t in Base.metadata.tables.items() if name not in TABLES])


@pytest.fixture()
def store():
    engine = sa.create_engine("sqlite://", future=True)
    _apply(engine, "upgrade")
    yield engine
    engine.dispose()


def test_the_migration_is_promoted_and_is_the_chain_head_on_0029():
    assert MIGRATION.exists()
    assert not (ROOT / "migrations" / "proposed" / NAME).exists()
    script = _script()
    assert script.get_heads() == ["20261008_0030"]
    assert script.get_revision("20261008_0030").down_revision == "20261007_0029"
    revisions = [
        re.search(r'^revision = "([^"]+)"', path.read_text(encoding="utf-8"), re.M).group(1)
        for folder in ("versions", "proposed") for path in (ROOT / "migrations" / folder).glob("2*.py")
    ]
    assert [rev for rev in revisions if rev.endswith("_0030")] == ["20261008_0030"]


def test_the_orm_says_what_the_migration_says():
    """`create_all` (the hermetic schema every store test uses) and the migration build the same grammar tables:
    columns, nullability, defaults, indexes (with their WHERE), CHECKs, uniques and foreign keys."""
    from writing_coach.persistence.models import Base

    def grammar(engine) -> dict[str, tuple]:
        inspector = sa.inspect(engine)
        out = {}
        for table in sorted(TABLES):
            columns = tuple((c["name"], str(c["type"]), c["nullable"], str(c.get("default"))) for c in
                            inspector.get_columns(table))
            indexes = tuple(sorted((i["name"], tuple(i["column_names"]), bool(i["unique"]),
                                    str(i.get("dialect_options", {}).get("sqlite_where"))) for i in
                                   inspector.get_indexes(table)))
            checks = tuple(sorted((c["name"], re.sub(r"\s+", " ", c["sqltext"])) for c in
                                  inspector.get_check_constraints(table)))
            uniques = tuple(sorted((u["name"], tuple(u["column_names"])) for u in inspector.get_unique_constraints(table)))
            fks = tuple(sorted((tuple(f["constrained_columns"]), f["referred_table"], tuple(f["referred_columns"]),
                                str(f.get("options", {}).get("ondelete"))) for f in inspector.get_foreign_keys(table)))
            out[table] = (columns, indexes, checks, uniques, fks)
        return out

    by_migration = sa.create_engine("sqlite://", future=True)
    _apply(by_migration, "upgrade")
    by_orm = sa.create_engine("sqlite://", future=True)
    Base.metadata.create_all(by_orm, tables=[Base.metadata.tables[name] for name in TABLES])
    assert grammar(by_orm) == grammar(by_migration)


def test_no_grammar_point_json_ships_with_the_source():
    """D-105.4: content does not ship as JSON with the application source. The vendored export-profile schema is a
    schema, not content, and is the one grammar JSON file allowed under writing_coach/."""
    point_file = re.compile(r"^(en|zh)\.[a-z0-9_]+(\.[a-z0-9_]+)*\.json$")
    shipped = [
        path.relative_to(ROOT).as_posix()
        for folder in ("writing_coach", "static", "templates")
        for path in (ROOT / folder).rglob("*.json")
        if point_file.match(path.name)
    ]
    assert shipped == []
    grammar_json = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "writing_coach").rglob("*.json")
                          if "grammar_store" in p.as_posix())
    assert grammar_json == ["writing_coach/grammar_store/schema/export_profile.schema.json"]


def test_upgrade_adds_only_the_eight_tables_and_downgrade_restores_the_schema_exactly():
    engine = sa.create_engine("sqlite://", future=True)
    _without_grammar(engine)
    before = _schema(engine)
    _apply(engine, "upgrade")
    after = _schema(engine)
    assert {row[2] for row in after - before} == TABLES
    assert before <= after  # nothing existing changed
    _apply(engine, "downgrade")
    assert _schema(engine) == before


def _batch(conn, *, status="imported", package_hash=None) -> uuid.UUID:
    batch = uuid.uuid4()
    conn.execute(sa.text(
        "INSERT INTO grammar_import_batches (id, status, language_code, package_hash, export_profile, profile_schema_hash,"
        " schema_version, set_version, source_commit, exported_at, manifest, imported_by, created_at) VALUES (:id, :s,"
        " 'en', :h, 'grammar-export-profile/1', :z, '0.4', 'v', 'c', :now, '{}', 'admin', :now)"),
        {"id": batch.hex, "s": status, "h": package_hash or uuid.uuid4().hex * 2, "z": "0" * 64, "now": NOW})
    return batch


def _point(conn, point_id="en.present_perfect", language="en") -> None:
    conn.execute(sa.text(
        "INSERT INTO grammar_points (id, language_code, created_at, updated_at) VALUES (:id, :l, :now, :now)"),
        {"id": point_id, "l": language, "now": NOW})


def _version(conn, batch, version=1, *, review="accepted", rights="cleared", point_id="en.present_perfect") -> str:
    vid = uuid.uuid4().hex
    conn.execute(sa.text(
        "INSERT INTO grammar_point_versions (id, point_id, version, content, content_hash, source_status, review_status,"
        " rights_status, provenance, batch_id, imported_at) VALUES (:id, :p, :v, '{}', :h, 'approved', :r, :rt, '{}',"
        " :b, :now)"),
        {"id": vid, "p": point_id, "v": version, "h": f"{version:064d}", "r": review, "rt": rights, "b": batch.hex,
         "now": NOW})
    return vid


def _refused(engine, sql, params=None) -> bool:
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            conn.execute(sa.text(sql), params or {})
        except sa.exc.IntegrityError:
            return True
        finally:
            tx.rollback()
    return False


def test_one_published_version_per_point_and_only_when_accepted_and_cleared(store):
    with store.begin() as conn:
        batch = _batch(conn)
        _point(conn)
        first, second = _version(conn, batch, 1), _version(conn, batch, 2)
        uncleared = _version(conn, batch, 3, rights="unknown")
        conn.execute(sa.text("UPDATE grammar_point_versions SET is_published = true WHERE id = :v"), {"v": first})
    assert _refused(store, "UPDATE grammar_point_versions SET is_published = true WHERE id = :v", {"v": second})
    assert _refused(store, "UPDATE grammar_point_versions SET is_published = true WHERE id = :v", {"v": uncleared})
    assert _refused(store, "INSERT INTO grammar_point_versions (id, point_id, version, content, content_hash,"
                           " source_status, provenance, batch_id, imported_at) VALUES ('x', 'en.present_perfect', 9,"
                           " '{}', :h, 'draft_ai', '{}', :b, :now)", {"h": "9" * 64, "b": batch.hex, "now": NOW})


def test_a_superseded_version_stays_accepted_and_can_be_republished_for_rollback(store):
    """Codex review P1 (PR #100): supersession is serving state, not a review verdict, so rollback passes the gate."""
    assert _migration().REVIEW_STATUSES == ("imported", "accepted", "rejected")
    supersede = ("UPDATE grammar_point_versions SET is_published = false, superseded_at = :now"
                 " WHERE point_id = 'en.present_perfect' AND is_published AND id <> :new")
    publish = "UPDATE grammar_point_versions SET is_published = true, superseded_at = NULL WHERE id = :new"

    def swap(conn, new):  # the publish transaction's order: supersede, then publish (section 6)
        conn.execute(sa.text(supersede), {"new": new, "now": NOW})
        conn.execute(sa.text(publish), {"new": new})
    with store.begin() as conn:
        batch = _batch(conn)
        _point(conn)
        old, new = _version(conn, batch, 1), _version(conn, batch, 2)
        conn.execute(sa.text("UPDATE grammar_point_versions SET is_published = true WHERE id = :v"), {"v": old})
        swap(conn, new)  # publish v2: v1 is superseded, still accepted
        swap(conn, old)  # roll back to v1
        rows = dict(conn.execute(sa.text(
            "SELECT id, review_status || ':' || is_published || ':' || (superseded_at IS NULL) FROM grammar_point_versions"
        )).all())
    assert rows == {old: "accepted:1:1", new: "accepted:0:0"}
    assert _refused(store, "UPDATE grammar_point_versions SET superseded_at = :now WHERE id = :v", {"v": old, "now": NOW})
    assert _refused(store, "UPDATE grammar_point_versions SET review_status = 'superseded' WHERE id = :v", {"v": new})


def test_a_rejected_version_cannot_be_published(store):
    with store.begin() as conn:
        batch = _batch(conn)
        _point(conn)
        rejected = _version(conn, batch, 1, review="rejected")
    assert _refused(store, "UPDATE grammar_point_versions SET is_published = true WHERE id = :v", {"v": rejected})


def test_a_published_point_carries_its_projection_and_its_id_matches_its_language(store):
    with store.begin() as conn:
        _point(conn)
    assert _refused(store, "UPDATE grammar_points SET lifecycle = 'published' WHERE id = 'en.present_perfect'")
    assert _refused(store, "INSERT INTO grammar_points (id, language_code, created_at, updated_at)"
                           " VALUES ('zh.le_completion', 'en', :now, :now)", {"now": NOW})


def test_one_resolution_per_r5_id_across_batches(store):
    sql = ("INSERT INTO grammar_r5_map (id, language_code, r5_id, point_id, disposition, is_primary, batch_id,"
           " created_at) VALUES (:id, 'en', :r5, :p, :d, :pr, :b, :now)")
    with store.begin() as conn:
        first, second = _batch(conn), _batch(conn)
        _point(conn)
        _point(conn, "en.present_perfect_experience")
        conn.execute(sa.text(sql), {"id": uuid.uuid4().hex, "r5": "a1-present-perfect", "p": "en.present_perfect",
                                    "d": "split_primary", "pr": True, "b": first.hex, "now": NOW})
        conn.execute(sa.text(sql), {"id": uuid.uuid4().hex, "r5": "a1-present-perfect",
                                    "p": "en.present_perfect_experience", "d": "split_secondary", "pr": False,
                                    "b": first.hex, "now": NOW})

    def row(**kw):
        return {"id": uuid.uuid4().hex, "r5": "a1-present-perfect", "b": second.hex, "now": NOW, **kw}
    assert _refused(store, sql, row(p=None, d="dropped", pr=False))  # mapped and dropped (review N-3)
    assert _refused(store, sql, row(p="en.present_perfect_experience", d="replaced", pr=True))  # a second primary
    assert _refused(store, sql, row(r5="other", p="en.present_perfect", d="dropped", pr=False))  # dropped with a point
    assert _refused(store, sql, row(r5="other", p="en.present_perfect", d="split_secondary", pr=True))


def test_an_imported_package_hash_is_unique_but_a_rejected_receipt_may_repeat_it(store):
    with store.begin() as conn:
        _batch(conn, package_hash="a" * 64)
        _batch(conn, status="rejected", package_hash="a" * 64)
    with store.connect() as conn:
        tx = conn.begin()
        with pytest.raises(sa.exc.IntegrityError):
            _batch(conn, package_hash="a" * 64)
        tx.rollback()


def test_the_downgrade_drops_only_the_content_tables(store):
    _apply(store, "downgrade")
    assert not TABLES & set(sa.inspect(store).get_table_names())
