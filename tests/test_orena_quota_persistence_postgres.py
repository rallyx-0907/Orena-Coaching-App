"""I3 quota bucket/reservation concurrency proof. Real PostgreSQL, real races.

Skips unless `ORENA_TEST_POSTGRES_URL` names a throwaway database. The
migration this exercises is `migrations/proposed/20260912_0007` — awaiting
review — so the fixture points Alembic's `version_locations` at both
`versions/` and `proposed/` rather than plain `head`, the same technique
`test_orena_commerce_persistence_postgres.py` already uses.

    ORENA_TEST_POSTGRES_URL=postgresql+psycopg://user:pw@host/orena_i3_test \\
        python -m pytest tests/test_orena_quota_persistence_postgres.py
"""
from __future__ import annotations

import os
import threading
import uuid
from datetime import UTC, datetime, timedelta

import pytest

sqlalchemy = pytest.importorskip('sqlalchemy')
from sqlalchemy import create_engine, text  # noqa: E402

from writing_coach.persistence.quota_repository import (  # noqa: E402
    BucketWindow,
    PostgresQuotaRepository,
)

URL = os.getenv('ORENA_TEST_POSTGRES_URL', '')
pytestmark = pytest.mark.skipif(
    not URL, reason='ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run'
)

TABLES = ('commerce_quota_reservations', 'commerce_quota_buckets')


def _window(limit: int | None, *, window_id: str = 'w1') -> BucketWindow:
    now = datetime.now(UTC)
    return BucketWindow(
        window_id=window_id, window_start=now, window_end=now + timedelta(days=30),
        policy_version='p1', unit_limit=limit,
    )


@pytest.fixture(scope='module')
def engine():
    from pathlib import Path

    from alembic import command
    from writing_coach.persistence.runtime import _runtime_alembic_config

    root = Path(__file__).resolve().parents[1]
    cfg = _runtime_alembic_config()
    cfg.set_main_option('sqlalchemy.url', URL.replace('%', '%%'))
    # 'path_separator=os' means "split on os.pathsep" (':' on Linux, ';' on
    # Windows) - not a literal space. See I2_ACTIVATION_RUNBOOK.md §7 and
    # test_orena_commerce_persistence_postgres.py's identical fixture comment.
    import os as _os

    cfg.set_main_option(
        'version_locations',
        _os.pathsep.join([str(root / 'migrations' / 'versions'), str(root / 'migrations' / 'proposed')]),
    )
    cfg.set_main_option('path_separator', 'os')
    command.upgrade(cfg, 'head')
    engine = create_engine(URL, future=True)
    yield engine
    engine.dispose()


@pytest.fixture
def incarnation(engine):
    """A fresh active account incarnation per test."""
    now = datetime.now(UTC)
    user_id, incarnation_id = uuid.uuid4(), uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                'INSERT INTO users (id, user_key, email, name, picture, role, created_at) '
                'VALUES (:id, :key, :email, :name, :pic, :role, :now)'
            ),
            {'id': user_id, 'key': f'quota-{user_id}', 'email': '', 'name': '',
             'pic': '', 'role': 'user', 'now': now},
        )
        connection.execute(
            text(
                'INSERT INTO account_incarnations (id, user_id, epoch, status, created_at) '
                'VALUES (:id, :user, 1, :status, :now)'
            ),
            {'id': incarnation_id, 'user': user_id, 'status': 'active', 'now': now},
        )
    return str(incarnation_id)


def test_first_reservation_admits_and_updates_the_bucket(engine, incarnation):
    repo = PostgresQuotaRepository(engine)
    outcome = repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(10),
        operation_id='op-1', requested_units=3,
    )
    assert outcome['status'] == 'admit'
    bucket = repo.get_bucket(incarnation, 'writing.evaluate', 'w1')
    assert bucket['reserved'] == 3 and bucket['consumed'] == 0


def test_reservation_beyond_the_limit_is_exhausted_and_writes_no_row(engine, incarnation):
    repo = PostgresQuotaRepository(engine)
    repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(5),
        operation_id='op-2a', requested_units=5,
    )
    exhausted = repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(5),
        operation_id='op-2b', requested_units=1,
    )
    assert exhausted['status'] == 'exhausted'
    # No reservation row for a rejected attempt - retrying the same
    # operation_id later must still be free to succeed once capacity exists.
    assert repo.get_reservation('op-2b') is None
    bucket = repo.get_bucket(incarnation, 'writing.evaluate', 'w1')
    assert bucket['reserved'] == 5


def test_rejected_operation_id_can_succeed_later_once_capacity_frees_up(engine, incarnation):
    repo = PostgresQuotaRepository(engine)
    repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(1),
        operation_id='op-3a', requested_units=1,
    )
    first_try = repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(1),
        operation_id='op-3b', requested_units=1,
    )
    assert first_try['status'] == 'exhausted'
    repo.release(operation_id='op-3a')
    retry = repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(1),
        operation_id='op-3b', requested_units=1,
    )
    assert retry['status'] == 'admit'


def test_duplicate_operation_id_replays_without_double_reserving(engine, incarnation):
    repo = PostgresQuotaRepository(engine)
    first = repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(10),
        operation_id='op-4', requested_units=2,
    )
    assert first['status'] == 'admit'
    replay = repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(10),
        operation_id='op-4', requested_units=2,
    )
    assert replay['status'] == 'duplicate'
    bucket = repo.get_bucket(incarnation, 'writing.evaluate', 'w1')
    assert bucket['reserved'] == 2, 'a replay must never reserve a second time'


def test_operation_id_retried_with_different_units_is_a_payload_conflict(engine, incarnation):
    repo = PostgresQuotaRepository(engine)
    repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(10),
        operation_id='op-5', requested_units=2,
    )
    conflict = repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(10),
        operation_id='op-5', requested_units=4,
    )
    assert conflict['status'] == 'payload_conflict'
    bucket = repo.get_bucket(incarnation, 'writing.evaluate', 'w1')
    assert bucket['reserved'] == 2, 'a conflicting retry must not change what was already admitted'


def test_deleted_incarnation_is_denied_and_reserves_nothing(engine, incarnation):
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE account_incarnations SET status = 'deleted', deleted_at = :now "
                'WHERE id = :inc'
            ),
            {'now': datetime.now(UTC), 'inc': incarnation},
        )
    repo = PostgresQuotaRepository(engine)
    outcome = repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(10),
        operation_id='op-6', requested_units=1,
    )
    assert outcome['status'] == 'denied'
    assert repo.get_reservation('op-6') is None


def test_settle_moves_reserved_to_consumed_and_releases_the_unused_remainder(engine, incarnation):
    repo = PostgresQuotaRepository(engine)
    repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(10),
        operation_id='op-7', requested_units=5,
    )
    outcome = repo.settle(operation_id='op-7', actual_units=3)
    assert outcome['status'] == 'settle'
    bucket = repo.get_bucket(incarnation, 'writing.evaluate', 'w1')
    assert bucket['reserved'] == 0 and bucket['consumed'] == 3


def test_settle_is_idempotent_and_rejects_a_conflicting_retry(engine, incarnation):
    repo = PostgresQuotaRepository(engine)
    repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(10),
        operation_id='op-8', requested_units=5,
    )
    repo.settle(operation_id='op-8', actual_units=2)
    duplicate = repo.settle(operation_id='op-8', actual_units=2)
    assert duplicate['status'] == 'duplicate'
    conflict = repo.settle(operation_id='op-8', actual_units=4)
    assert conflict['status'] == 'payload_conflict'
    bucket = repo.get_bucket(incarnation, 'writing.evaluate', 'w1')
    assert bucket['consumed'] == 2, 'neither replay nor conflict may change the settled amount'


def test_settle_cannot_exceed_the_admitted_bound(engine, incarnation):
    repo = PostgresQuotaRepository(engine)
    repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(10),
        operation_id='op-9', requested_units=3,
    )
    outcome = repo.settle(operation_id='op-9', actual_units=4)
    assert outcome['status'] == 'exceeds_admitted'
    bucket = repo.get_bucket(incarnation, 'writing.evaluate', 'w1')
    assert bucket['reserved'] == 3 and bucket['consumed'] == 0


def test_release_before_dispatch_returns_the_units(engine, incarnation):
    repo = PostgresQuotaRepository(engine)
    repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(10),
        operation_id='op-10', requested_units=4,
    )
    outcome = repo.release(operation_id='op-10')
    assert outcome['status'] == 'release'
    bucket = repo.get_bucket(incarnation, 'writing.evaluate', 'w1')
    assert bucket['reserved'] == 0 and bucket['consumed'] == 0

    duplicate = repo.release(operation_id='op-10')
    assert duplicate['status'] == 'duplicate'


def test_release_cannot_undo_a_settlement(engine, incarnation):
    repo = PostgresQuotaRepository(engine)
    repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(10),
        operation_id='op-11', requested_units=2,
    )
    repo.settle(operation_id='op-11', actual_units=2)
    outcome = repo.release(operation_id='op-11')
    assert outcome['status'] == 'already_settled'
    bucket = repo.get_bucket(incarnation, 'writing.evaluate', 'w1')
    assert bucket['consumed'] == 2


def test_settle_and_release_on_an_unknown_operation_are_named_not_crashed(engine):
    repo = PostgresQuotaRepository(engine)
    assert repo.settle(operation_id='never-reserved', actual_units=1)['status'] == 'unknown_operation'
    assert repo.release(operation_id='never-reserved')['status'] == 'unknown_operation'


def test_two_racing_reservations_against_a_one_unit_shared_bucket(engine, incarnation):
    """Acceptance matrix: "Quota has one unit, EN and ZH submit concurrently"
    -> one reservation, one exhausted; same shared bucket. Language is
    diagnostic only - both requests target the identical (incarnation, meter,
    window) bucket, distinguished only by operation_id, exactly as two
    submissions in different UI languages would be."""
    repo = PostgresQuotaRepository(engine)
    results, barrier = {}, threading.Barrier(2)

    def send(name):
        barrier.wait()
        results[name] = repo.reserve(
            incarnation_id=incarnation, meter='writing.evaluate', window=_window(1),
            operation_id=f'op-race-{name}', requested_units=1,
        )

    threads = [threading.Thread(target=send, args=('en',)), threading.Thread(target=send, args=('zh',))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    statuses = sorted(results[name]['status'] for name in ('en', 'zh'))
    assert statuses == ['admit', 'exhausted']
    bucket = repo.get_bucket(incarnation, 'writing.evaluate', 'w1')
    assert bucket['reserved'] == 1, 'never two admissions against a one-unit bucket'


def test_concurrent_retries_of_the_same_operation_id_are_exactly_one_admission(engine, incarnation):
    """Same shape as the commerce inbox's exactly-once regression: a real
    double-send of the identical operation, not two distinct operations."""
    repo = PostgresQuotaRepository(engine)
    results, barrier = {}, threading.Barrier(2)

    def send(name):
        barrier.wait()
        results[name] = repo.reserve(
            incarnation_id=incarnation, meter='writing.evaluate', window=_window(10),
            operation_id='op-same-twice', requested_units=1,
        )

    threads = [threading.Thread(target=send, args=('a',)), threading.Thread(target=send, args=('b',))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    statuses = sorted(results[name]['status'] for name in ('a', 'b'))
    assert statuses == ['admit', 'duplicate']
    bucket = repo.get_bucket(incarnation, 'writing.evaluate', 'w1')
    assert bucket['reserved'] == 1
