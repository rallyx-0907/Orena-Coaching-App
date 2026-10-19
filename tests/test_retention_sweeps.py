"""PRE-502 R8 (owner, 2026-10-19 16:26): usage counts are kept 12 months and records of administrators' actions 24
months, then swept in bounded batches. The deletes run on PostgreSQL only, when ORENA_TEST_POSTGRES_URL names a
throwaway database; the switches are checked everywhere."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from writing_coach.agent.retention import sweep_enabled
from writing_coach.persistence import retention_sweeps as sweeps

URL = os.getenv("ORENA_TEST_POSTGRES_URL", "")
NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)


def test_the_periods_and_switches():
    assert sweeps.USAGE_RETENTION_DAYS == 365 and sweeps.ADMIN_AUDIT_RETENTION_DAYS == 730
    assert sweep_enabled({sweeps.USAGE_SWEEP_SWITCH: "on"}, sweeps.USAGE_SWEEP_SWITCH)
    assert not sweep_enabled({}, sweeps.ADMIN_AUDIT_SWEEP_SWITCH)  # off by default: deletion is the owner's switch
    with pytest.raises(ValueError):
        sweep_enabled({sweeps.ADMIN_AUDIT_SWEEP_SWITCH: "maybe"}, sweeps.ADMIN_AUDIT_SWEEP_SWITCH)


@pytest.fixture(scope="module")
def engine():
    if not URL:
        pytest.skip("ORENA_TEST_POSTGRES_URL is not set; the sweeps delete on PostgreSQL only")
    sqlalchemy = pytest.importorskip("sqlalchemy")
    from alembic import command

    from writing_coach.persistence.runtime import _runtime_alembic_config

    cfg = _runtime_alembic_config()
    cfg.set_main_option("sqlalchemy.url", URL.replace("%", "%%"))
    command.upgrade(cfg, "head")
    engine = sqlalchemy.create_engine(URL, future=True)
    yield engine
    engine.dispose()


def _seed(engine):
    from sqlalchemy import text

    user, inc = uuid.uuid4(), uuid.uuid4()
    old, recent = NOW - timedelta(days=400), NOW - timedelta(days=30)
    very_old = NOW - timedelta(days=800)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO users (id, user_key, email, name, picture, role, created_at)"
                          " VALUES (:u, :k, :e, '', '', 'user', now())"),
                     {"u": user, "k": f"r8-{user}", "e": f"r8-{user}@example.com"})  # fmt: skip
        conn.execute(text("INSERT INTO account_incarnations (id, user_id, epoch, status, created_at)"
                          " VALUES (:i, :u, 1, 'active', now())"), {"i": inc, "u": user})
        for when in (old, recent):
            conn.execute(text("INSERT INTO usage_events (id, user_id, feature, amount, request_id, occurred_at)"
                              " VALUES (:id, :u, 'agent.turn', 1, :r, :t)"),
                         {"id": uuid.uuid4(), "u": user, "r": f"req-{uuid.uuid4()}", "t": when})  # fmt: skip
        buckets = {}
        for name, when in (("old", old), ("recent", recent)):
            bucket = uuid.uuid4()
            buckets[name] = bucket
            conn.execute(text(
                "INSERT INTO commerce_quota_buckets (id, incarnation_id, meter, window_id, window_start, window_end,"
                " policy_version, consumed, reserved, created_at, updated_at) VALUES (:b, :i, 'orena.text', :w, :s,"
                " :e, 'v1', 0, 0, :s, :s)"),
                {"b": bucket, "i": inc, "w": f"w-{name}-{bucket}", "s": when, "e": when + timedelta(days=1)})  # fmt: skip
            conn.execute(text(
                "INSERT INTO commerce_quota_reservations (id, bucket_id, operation_id, admitted_units, state,"
                " policy_version, created_at, updated_at) VALUES (:r, :b, :o, 1, 'released', 'v1', :t, :t)"),
                {"r": uuid.uuid4(), "b": bucket, "o": f"op-{uuid.uuid4()}", "t": when})  # fmt: skip
        for action, when in (("admin.memory_erase_requested", very_old), ("product.plans.update", very_old),
                             ("platform.policies.update", recent), ("learner.feedback", very_old)):
            conn.execute(text("INSERT INTO audit_logs (id, user_id, action, entity_type, entity_id, payload, created_at)"
                              " VALUES (:a, :u, :act, 'x', '', '{}', :t)"),
                         {"a": uuid.uuid4(), "u": user, "act": action, "t": when})  # fmt: skip
    return user, buckets


def _count(engine, sql, **params):
    from sqlalchemy import text

    with engine.connect() as conn:
        return conn.execute(text(sql), params).scalar()


def test_usage_older_than_12_months_goes_and_recent_stays(engine):
    user, buckets = _seed(engine)
    cutoff = NOW - timedelta(days=sweeps.USAGE_RETENTION_DAYS)
    removed = sum(iter(lambda: sweeps.delete_usage_before(engine, cutoff, 500), 0))
    assert removed >= 3  # one event, one reservation, then its bucket
    assert _count(engine, "SELECT count(*) FROM usage_events WHERE user_id = :u", u=user) == 1
    assert _count(engine, "SELECT count(*) FROM commerce_quota_buckets WHERE id = :b", b=buckets["old"]) == 0
    assert _count(engine, "SELECT count(*) FROM commerce_quota_buckets WHERE id = :b", b=buckets["recent"]) == 1
    assert _count(engine, "SELECT count(*) FROM commerce_quota_reservations WHERE bucket_id = :b",
                  b=buckets["recent"]) == 1  # fmt: skip


def test_a_bucket_still_referenced_by_a_reservation_waits(engine):
    from sqlalchemy import text

    user, buckets = _seed(engine)
    with engine.begin() as conn:  # a recent reservation on the old bucket (RESTRICT): the bucket must wait
        conn.execute(text("INSERT INTO commerce_quota_reservations (id, bucket_id, operation_id, admitted_units, state,"
                          " policy_version, created_at, updated_at) VALUES (:r, :b, :o, 1, 'released', 'v1', :t, :t)"),
                     {"r": uuid.uuid4(), "b": buckets["old"], "o": f"op-{uuid.uuid4()}", "t": NOW})  # fmt: skip
    cutoff = NOW - timedelta(days=sweeps.USAGE_RETENTION_DAYS)
    sum(iter(lambda: sweeps.delete_usage_before(engine, cutoff, 500), 0))
    assert _count(engine, "SELECT count(*) FROM commerce_quota_buckets WHERE id = :b", b=buckets["old"]) == 1


def test_admin_records_older_than_24_months_go_and_nothing_else(engine):
    user, _ = _seed(engine)
    cutoff = NOW - timedelta(days=sweeps.ADMIN_AUDIT_RETENTION_DAYS)
    sum(iter(lambda: sweeps.delete_admin_audit_before(engine, cutoff, 500), 0))
    left = _count(engine, "SELECT string_agg(action, ',' ORDER BY action) FROM audit_logs WHERE user_id = :u", u=user)
    # the recent platform record stays; the learner's own feedback has its own sweep (24 months, feedback.retention)
    assert left == "learner.feedback,platform.policies.update"
