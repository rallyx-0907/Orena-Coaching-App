"""The one-off scrub of imports deleted before the tombstone fix (scripts/scrub_deleted_imports.py; human-approved).

Real PostgreSQL (ORENA_TEST_POSTGRES_URL). A legacy deleted import is seeded by deleting through the API and then
writing the old full payload back - exactly what a pre-fix deletion left behind.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import inspect, text

from test_d4_account_records import _account, _client, op  # noqa: F401  (shared helpers)
from writing_coach.account_backbone import build_backbone

_SPEC = importlib.util.spec_from_file_location("scrub_deleted_imports", Path(__file__).resolve().parents[1] / "scripts" / "scrub_deleted_imports.py")
scrub_module = importlib.util.module_from_spec(_SPEC)
sys.modules["scrub_deleted_imports"] = scrub_module
_SPEC.loader.exec_module(scrub_module)


@pytest.fixture
def backbone(pg_engine):
    built = build_backbone(pg_engine, inspect(pg_engine).get_table_names(), env={"ORENA_ACCOUNT_BACKBONE": "on"})
    assert built.is_active
    return built


def _import(client, title, text_):
    ident = str(uuid.uuid4())
    saved = client.put(f"/api/imports/{ident}", json={"operationId": op(), "expectedVersion": 0, "form": "text", "title": title, "text": text_})
    assert saved.status_code == 200, saved.text
    return ident


def _payload(engine, ident):
    with engine.connect() as connection:
        return connection.execute(text("SELECT payload FROM works WHERE kind = 'imported' AND source_id = :i"), {"i": ident}).scalar_one()


def _row(engine, ident):
    with engine.connect() as connection:
        return dict(connection.execute(text("SELECT version, updated_sequence, lifecycle FROM works WHERE kind = 'imported' AND source_id = :i"), {"i": ident}).mappings().one())


def _legacy_delete(engine, client, ident):
    """Delete through the API (now a tombstone), then put the old full payload back: the pre-fix state."""
    removed = client.delete(f"/api/imports/{ident}", params={"operationId": op(), "expectedVersion": 1})
    assert removed.status_code == 200, removed.text
    full = {"id": ident, "form": "text", "title": "Secret diary", "text": "the private words", "url": "https://example.test/private"}
    with engine.begin() as connection:
        connection.execute(text("UPDATE works SET payload = CAST(:p AS JSON) WHERE kind = 'imported' AND source_id = :i"), {"p": json.dumps(full), "i": ident})


def _counts(engine):
    with engine.connect() as connection:
        return (
            connection.execute(text("SELECT count(*) FROM mutation_receipts")).scalar_one(),
            connection.execute(text("SELECT count(*) FROM change_records")).scalar_one(),
        )


def test_dry_run_changes_nothing_and_apply_scrubs_only_deleted_imports_with_content(pg_engine, backbone):
    client = _client(backbone, user=_account(pg_engine))
    legacy = _import(client, "Secret diary", "the private words")
    already_clean = _import(client, "Gone", "x")
    live = _import(client, "Keep me", "still here")
    _legacy_delete(pg_engine, client, legacy)
    assert client.delete(f"/api/imports/{already_clean}", params={"operationId": op(), "expectedVersion": 1}).status_code == 200
    before_live = _payload(pg_engine, live)
    before_row = _row(pg_engine, legacy)
    before_counts = _counts(pg_engine)

    dry = scrub_module.scrub(pg_engine, apply=False)
    assert dry["with_content"] >= 1 and dry["scrubbed"] == 0 and dry["applied"] is False
    assert set(_payload(pg_engine, legacy)) > {"id", "form"}, "a dry run writes nothing"

    done = scrub_module.scrub(pg_engine, apply=True)
    assert done["scrubbed"] == dry["with_content"] and done["applied"] is True
    assert _payload(pg_engine, legacy) == {"id": legacy, "form": "text"}
    assert set(_payload(pg_engine, already_clean)) == {"id", "form"}, "an already-clean tombstone is skipped"
    assert _payload(pg_engine, live) == before_live and "title" in before_live, "an active import is untouched"
    assert _row(pg_engine, legacy) == before_row, "version, sequence and lifecycle do not move - no sync client sees a change"
    assert _counts(pg_engine) == before_counts, "the scrub writes no receipt and no change record"

    again = scrub_module.scrub(pg_engine, apply=True)
    assert again["with_content"] == 0 and again["scrubbed"] == 0, "idempotent: a rerun finds nothing"


def test_the_report_holds_counts_only_and_names_no_content_column_on_receipts(pg_engine, backbone):
    client = _client(backbone, user=_account(pg_engine))
    ident = _import(client, "Secret diary", "the private words")
    _legacy_delete(pg_engine, client, ident)
    report = scrub_module.scrub(pg_engine, apply=True)
    rendered = json.dumps(report)
    for needle in ("Secret diary", "private words", "example.test", ident):
        assert needle not in rendered
    assert report["receipt_columns_that_could_hold_content"] == {"mutation_receipts": [], "change_records": []}
    assert set(report["derived_records_left_untouched"]) == {"annotations", "responses", "places"}
