"""agent.turn telemetry in audit_logs is kept 90 days and swept automatically (human direction 2026-10-04).

The unit tests drive the sweeper with a clock and a fake delete. The PostgreSQL proof runs when
`ORENA_TEST_POSTGRES_URL` names a throwaway database: the Alembic chain in a fresh schema, then the repository's
own delete - only `agent.turn` rows older than the cut-off go; every other audit row stays.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import pytest

from writing_coach.agent.retention import (
    SWEEP_BATCH,
    SWEEP_INTERVAL_SECONDS,
    TURN_RETENTION_DAYS,
    TurnTelemetryRetention,
    sweep_enabled,
)

NOON = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.now = NOON

    def __call__(self) -> datetime:
        return self.now


def sweeper(rows: int = 0, *, fail: bool = False, clock: Clock | None = None):
    calls: list[tuple[datetime, int]] = []
    left = [rows]

    def delete(before: datetime, limit: int) -> int:
        calls.append((before, limit))
        if fail:
            raise RuntimeError("database down")
        gone = min(left[0], limit)
        left[0] -= gone
        return gone

    retention = TurnTelemetryRetention(delete, now=clock or Clock(), run=lambda work: work())
    return retention, calls


@pytest.mark.parametrize("env", [{}, {"AGENT_TURN_RETENTION_SWEEP": ""}, {"AGENT_TURN_RETENTION_SWEEP": "0"},
                                 {"AGENT_TURN_RETENTION_SWEEP": "false"}, {"AGENT_TURN_RETENTION_SWEEP": "off"}])
def test_the_sweep_is_off_unless_switched_on(env):
    """Human direction 2026-10-04: automatic deletion stays off until its independent review passes."""

    assert sweep_enabled(env) is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "on", "yes"])
def test_the_sweep_is_switched_on_only_by_its_environment_variable(value):
    assert sweep_enabled({"AGENT_TURN_RETENTION_SWEEP": value}) is True


def test_an_unclear_switch_refuses_to_start_rather_than_guess():
    with pytest.raises(ValueError):
        sweep_enabled({"AGENT_TURN_RETENTION_SWEEP": "maybe"})


def test_the_app_deletes_nothing_when_the_sweep_is_off(monkeypatch):
    import app

    monkeypatch.delenv("AGENT_TURN_RETENTION_SWEEP", raising=False)
    assert app._agent_turn_retention is None  # the test environment never sets it
    deleted = []
    monkeypatch.setattr(app, "_delete_agent_turns_before", lambda before, limit: deleted.append(before) or 0)
    writes = []
    monkeypatch.setattr(app._persistence_runtime.platform_repository, "record_admin_event",
                        lambda *a, **k: writes.append(a), raising=False)  # fmt: skip
    app._record_agent_turn("learner-1", {"trace_id": "t1"})
    assert writes and not deleted


def test_turn_telemetry_is_kept_ninety_days():
    assert TURN_RETENTION_DAYS == 90
    retention, calls = sweeper()
    retention.maybe_sweep()
    assert calls == [(NOON - timedelta(days=90), SWEEP_BATCH)]


def test_the_sweep_runs_at_most_once_a_day_and_again_the_next_day():
    clock = Clock()
    retention, calls = sweeper(clock=clock)
    retention.maybe_sweep()
    clock.now += timedelta(seconds=SWEEP_INTERVAL_SECONDS - 1)
    retention.maybe_sweep()
    assert len(calls) == 1
    clock.now += timedelta(seconds=1)
    retention.maybe_sweep()
    assert len(calls) == 2


def test_a_backlog_is_removed_in_bounded_batches_until_a_short_one():
    retention, calls = sweeper(rows=2 * SWEEP_BATCH + 7)
    assert retention.maybe_sweep() == 2 * SWEEP_BATCH + 7
    assert [limit for _, limit in calls] == [SWEEP_BATCH] * 3


def test_one_sweep_stops_after_its_batch_budget():
    retention, calls = sweeper(rows=10**9)
    retention.maybe_sweep()
    assert len(calls) == TurnTelemetryRetention.MAX_BATCHES


def test_a_failing_sweep_never_costs_the_turn_and_is_tried_again_the_next_day(caplog):
    clock = Clock()
    retention, calls = sweeper(fail=True, clock=clock)
    assert retention.maybe_sweep() is None
    assert "agent turn telemetry sweep failed" in caplog.text
    clock.now += timedelta(seconds=SWEEP_INTERVAL_SECONDS)
    retention.maybe_sweep()
    assert len(calls) == 2


def test_the_sweep_runs_off_the_request_thread_by_default():
    started = []
    retention = TurnTelemetryRetention(lambda before, limit: 0, now=Clock(), run=started.append)
    retention.maybe_sweep()
    assert len(started) == 1 and callable(started[0])


# --- PostgreSQL: only agent.turn rows older than the cut-off go -------------------------------------------------

URL = os.getenv("ORENA_TEST_POSTGRES_URL", "")
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(not URL, reason="ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")
def test_postgres_deletes_only_old_agent_turn_rows():
    pytest.importorskip("alembic")
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, select, text
    from sqlalchemy.orm import Session

    from writing_coach.persistence.models import AuditLog
    from writing_coach.persistence.platform_repository import PostgresPlatformRepository

    schema = f"agent_retention_{uuid.uuid4().hex[:10]}"
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
        try:
            cutoff = NOON - timedelta(days=TURN_RETENTION_DAYS)
            rows = {
                "old-turn-1": ("agent.turn", cutoff - timedelta(days=1)),
                "old-turn-2": ("agent.turn", cutoff - timedelta(seconds=1)),
                "new-turn": ("agent.turn", cutoff + timedelta(seconds=1)),
                "old-operation": ("ai.operation", cutoff - timedelta(days=30)),
                "old-admin": ("ai.config.update", cutoff - timedelta(days=30)),
            }
            with Session(engine) as session, session.begin():
                for entity_id, (action, created_at) in rows.items():
                    session.add(AuditLog(id=uuid.uuid4(), user_id=None, action=action, entity_type="t",
                                         entity_id=entity_id, payload={}, created_at=created_at))  # fmt: skip
            repository = PostgresPlatformRepository(engine=engine)
            assert repository.delete_agent_turns_before(cutoff, limit=1) == 1  # bounded, the oldest first
            assert repository.delete_agent_turns_before(cutoff, limit=100) == 1
            assert repository.delete_agent_turns_before(cutoff, limit=100) == 0
            with Session(engine) as session:
                left = set(session.scalars(select(AuditLog.entity_id)))
            assert left == {"new-turn", "old-operation", "old-admin"}
        finally:
            engine.dispose()
    finally:
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
