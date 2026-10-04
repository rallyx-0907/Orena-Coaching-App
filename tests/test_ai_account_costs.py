"""AI cost per account (AC-2): what is recorded, for whom, and the 13-month sweep.

`ORENA_TEST_POSTGRES_URL` names a throwaway database for the PostgreSQL proof: the Alembic chain to head in a fresh
schema, then the proposed migration 20261005_0026 applied and rolled back by hand (it is not in the chain yet).
"""

from __future__ import annotations

import importlib.util
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import pytest

from writing_coach.ai.account_costs import RETENTION_DAYS, SWEEP_BATCH, AccountCostRecorder

NOON = datetime(2026, 10, 5, 12, tzinfo=UTC)
CALL = {"capability": "writing_review", "provider": "gemini", "model": "gemini-3.5-flash-lite", "outcome": "success",
        "cost": {"state": "estimated", "amount": 0.0012}, "usage": {"prompt_tokens": 900, "completion_tokens": 300}}


class FakeRepository:
    def __init__(self, *, fail: bool = False, backlog: int = 0) -> None:
        self.recorded: list[tuple[str, dict]] = []
        self.deletes: list[datetime] = []
        self.fail = fail
        self.backlog = backlog

    def record_ai_cost(self, user_key, event):
        if self.fail:
            raise RuntimeError("relation ai_cost_records does not exist")
        self.recorded.append((user_key, event))
        return True

    def delete_ai_costs_before(self, before, *, limit):
        self.deletes.append(before)
        gone = min(limit, self.backlog)
        self.backlog -= gone
        return gone


def recorder(repository, started=None):
    return AccountCostRecorder(repository, now=lambda: NOON, run=(started.append if started is not None else lambda work: work()))


def test_a_signed_in_accounts_answered_call_is_recorded_without_words():
    repository = FakeRepository()
    assert recorder(repository).record("google-sub-1", CALL) is True
    assert repository.recorded == [("google-sub-1", CALL)]


@pytest.mark.parametrize("user_key", ["", "legacy", "local-admin", "local"])
def test_no_record_without_a_real_account(user_key):
    repository = FakeRepository()
    assert recorder(repository).record(user_key, CALL) is False and repository.recorded == []


@pytest.mark.parametrize("event", [{**CALL, "outcome": "provider_error"}, {**CALL, "provider": ""}])
def test_no_record_for_a_call_that_did_not_reach_or_answer(event):
    repository = FakeRepository()
    assert recorder(repository).record("google-sub-1", event) is False and repository.recorded == []


def test_a_database_error_pauses_recording_for_five_minutes_then_it_resumes():
    clock = [NOON]
    repository = FakeRepository(fail=True)
    costs = AccountCostRecorder(repository, now=lambda: clock[0], run=lambda work: work())
    assert costs.record("google-sub-1", CALL) is False
    repository.fail = False
    clock[0] = NOON + timedelta(minutes=4)
    assert costs.record("google-sub-1", CALL) is False and repository.recorded == []  # still paused
    clock[0] = NOON + timedelta(minutes=5)
    assert costs.record("google-sub-1", CALL) is True and len(repository.recorded) == 1


@pytest.mark.parametrize("origin", ["operator_test", "configuration"])
def test_an_operators_test_call_is_not_the_accounts_spend(origin):
    repository = FakeRepository()
    assert recorder(repository).record("google-sub-1", {**CALL, "origin": origin}) is False
    assert recorder(repository).record("google-sub-1", {**CALL, "origin": "learner"}) is True


def test_the_sweep_runs_once_a_day_and_deletes_older_than_13_months_in_bounded_batches():
    started: list = []
    repository = FakeRepository(backlog=SWEEP_BATCH * 2 + 7)
    costs = recorder(repository, started)
    costs.record("google-sub-1", CALL)
    costs.record("google-sub-1", CALL)
    assert len(started) == 1  # one sweep a day per process
    started[0]()
    assert repository.deletes == [NOON - timedelta(days=RETENTION_DAYS)] * 3 and repository.backlog == 0
    assert RETENTION_DAYS >= 395  # 13 months, never shorter


URL = os.getenv("ORENA_TEST_POSTGRES_URL", "")
ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "proposed" / "20261005_0026_ai_cost_records.py"


def _proposed_migration():
    spec = importlib.util.spec_from_file_location("proposed_0026", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_proposed_migration_is_parented_on_the_current_head():
    heads = sorted(path.name for path in (ROOT / "migrations" / "versions").glob("2*.py"))
    assert _proposed_migration().down_revision == heads[-1].split("_", 2)[0] + "_" + heads[-1].split("_", 2)[1]


@pytest.mark.skipif(not URL, reason="ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")
def test_postgres_records_reports_sweeps_only_old_cost_rows_and_cascades_with_the_account():
    pytest.importorskip("alembic")
    from alembic import command
    from alembic.config import Config
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine, func, select, text, update
    from sqlalchemy.orm import Session

    from writing_coach.persistence.models import AICostRecord, AuditLog, User
    from writing_coach.persistence.platform_repository import PostgresPlatformRepository

    schema = f"ai_costs_{uuid.uuid4().hex[:10]}"
    separator = "&" if "?" in URL else "?"
    schema_url = f"{URL}{separator}options={quote(f'-csearch_path={schema}')}"
    admin = create_engine(URL, future=True)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        cfg = Config(str(ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(ROOT / "migrations"))
        cfg.set_main_option("path_separator", "os")
        cfg.set_main_option("sqlalchemy.url", schema_url.replace("%", "%%"))
        command.upgrade(cfg, "head")
        engine = create_engine(schema_url, future=True)
        migration = _proposed_migration()
        try:
            repository = PostgresPlatformRepository(engine=engine)
            assert repository.ai_costs_by_account(NOON) is None  # before the table: "not available", no error
            with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            with Session(engine) as session, session.begin():
                for key in ("sub-a", "sub-b"):
                    session.add(User(id=uuid.uuid4(), user_key=key, email=f"{key}@example.org", name=key,
                                     created_at=NOON))  # fmt: skip
                session.add(AuditLog(id=uuid.uuid4(), user_id=None, action="ai.operation", entity_type="t",
                                     entity_id="keep", payload={}, created_at=NOON - timedelta(days=900)))  # fmt: skip
            assert repository.record_ai_cost("sub-a", CALL) is True
            assert repository.record_ai_cost("sub-a", {**CALL, "cost": {"state": "estimated", "amount": 0.002}})
            assert repository.record_ai_cost("sub-b", CALL) is True
            assert repository.record_ai_cost("nobody", CALL) is False
            report = repository.ai_costs_by_account(NOON - timedelta(days=1))
            assert [(row["email"], row["calls"]) for row in report] == [("sub-a@example.org", 2), ("sub-b@example.org", 1)]
            assert report[0]["usd"] == pytest.approx(0.0032)

            cutoff = datetime.now(UTC) - timedelta(days=RETENTION_DAYS)
            with Session(engine) as session, session.begin():
                first = session.scalars(select(AICostRecord.id).order_by(AICostRecord.occurred_at)).first()
                session.execute(update(AICostRecord).where(AICostRecord.id == first)
                                .values(occurred_at=cutoff - timedelta(days=1)))  # fmt: skip
            assert repository.delete_ai_costs_before(cutoff, limit=100) == 1
            assert repository.delete_ai_costs_before(cutoff, limit=100) == 0
            with Session(engine) as session, session.begin():
                assert session.scalar(select(func.count(AICostRecord.id))) == 2
                assert session.scalar(select(func.count(AuditLog.id))) == 1  # the sweep touches no other table
                session.execute(text("DELETE FROM users WHERE user_key = 'sub-b'"))
            with Session(engine) as session:
                assert session.scalar(select(func.count(AICostRecord.id))) == 1  # the account's records went with it
            with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
                migration.downgrade()
            assert repository.ai_costs_by_account(NOON) is None
        finally:
            engine.dispose()
    finally:
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
