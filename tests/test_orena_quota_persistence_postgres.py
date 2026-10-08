"""I3 quota bucket/reservation concurrency proof. Real PostgreSQL, real races.

Skips unless `ORENA_TEST_POSTGRES_URL` names a throwaway database. The
migration this exercises is `migrations/versions/20260912_0007` (approved by
delegated review); the fixture upgrades to the live chain's head.

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


def _window(limit: int | None, *, window_id: str = 'w1', start: datetime | None = None,
            days: int = 30) -> BucketWindow:
    start = start or datetime.now(UTC) - timedelta(minutes=1)
    return BucketWindow(
        window_id=window_id, window_start=start, window_end=start + timedelta(days=days),
        policy_version='p1', unit_limit=limit,
    )


_OPS: dict[str, str] = {}


@pytest.fixture(autouse=True)
def _fresh_operation_ids():
    """Operation ids are global, so each run gets its own: the file can be
    re-run against the same database."""
    _OPS.clear()


def op(name: str) -> str:
    return _OPS.setdefault(name, f'op-{name}-{uuid.uuid4()}')


@pytest.fixture(scope='module')
def engine():
    from alembic import command
    from writing_coach.persistence.runtime import _runtime_alembic_config

    cfg = _runtime_alembic_config()
    cfg.set_main_option('sqlalchemy.url', URL.replace('%', '%%'))
    command.upgrade(cfg, 'head')
    engine = create_engine(URL, future=True, pool_size=20, max_overflow=5)
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
        operation_id=op('1'), requested_units=3,
    )
    assert outcome['status'] == 'admit'
    bucket = repo.get_bucket(incarnation, 'writing.evaluate', 'w1')
    assert bucket['reserved'] == 3 and bucket['consumed'] == 0


def test_reservation_beyond_the_limit_is_exhausted_and_writes_no_row(engine, incarnation):
    repo = PostgresQuotaRepository(engine)
    repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(5),
        operation_id=op('2a'), requested_units=5,
    )
    exhausted = repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(5),
        operation_id=op('2b'), requested_units=1,
    )
    assert exhausted['status'] == 'exhausted'
    # No reservation row for a rejected attempt - retrying the same
    # operation_id later must still be free to succeed once capacity exists.
    assert repo.get_reservation(op('2b')) is None
    bucket = repo.get_bucket(incarnation, 'writing.evaluate', 'w1')
    assert bucket['reserved'] == 5


def test_rejected_operation_id_can_succeed_later_once_capacity_frees_up(engine, incarnation):
    repo = PostgresQuotaRepository(engine)
    repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(1),
        operation_id=op('3a'), requested_units=1,
    )
    first_try = repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(1),
        operation_id=op('3b'), requested_units=1,
    )
    assert first_try['status'] == 'exhausted'
    repo.release(operation_id=op('3a'))
    retry = repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(1),
        operation_id=op('3b'), requested_units=1,
    )
    assert retry['status'] == 'admit'


def test_duplicate_operation_id_replays_without_double_reserving(engine, incarnation):
    repo = PostgresQuotaRepository(engine)
    first = repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(10),
        operation_id=op('4'), requested_units=2,
    )
    assert first['status'] == 'admit'
    replay = repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(10),
        operation_id=op('4'), requested_units=2,
    )
    assert replay['status'] == 'duplicate'
    assert replay['reservation_id'] == first['reservation_id'], 'a replay returns the original result'
    bucket = repo.get_bucket(incarnation, 'writing.evaluate', 'w1')
    assert bucket['reserved'] == 2, 'a replay must never reserve a second time'


def test_operation_id_retried_with_different_units_is_a_payload_conflict(engine, incarnation):
    repo = PostgresQuotaRepository(engine)
    repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(10),
        operation_id=op('5'), requested_units=2,
    )
    conflict = repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(10),
        operation_id=op('5'), requested_units=4,
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
        operation_id=op('6'), requested_units=1,
    )
    assert outcome == {'status': 'denied', 'reason': 'incarnation_deleted'}
    assert repo.get_reservation(op('6')) is None
    assert repo.get_bucket(incarnation, 'writing.evaluate', 'w1') is None, 'no commerce row after deletion'


def test_settle_moves_reserved_to_consumed_and_releases_the_unused_remainder(engine, incarnation):
    repo = PostgresQuotaRepository(engine)
    repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(10),
        operation_id=op('7'), requested_units=5,
    )
    outcome = repo.settle(operation_id=op('7'), actual_units=3)
    assert outcome['status'] == 'settle'
    bucket = repo.get_bucket(incarnation, 'writing.evaluate', 'w1')
    assert bucket['reserved'] == 0 and bucket['consumed'] == 3


def test_settle_is_idempotent_and_rejects_a_conflicting_retry(engine, incarnation):
    repo = PostgresQuotaRepository(engine)
    repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(10),
        operation_id=op('8'), requested_units=5,
    )
    repo.settle(operation_id=op('8'), actual_units=2)
    duplicate = repo.settle(operation_id=op('8'), actual_units=2)
    assert duplicate['status'] == 'duplicate'
    conflict = repo.settle(operation_id=op('8'), actual_units=4)
    assert conflict['status'] == 'payload_conflict'
    bucket = repo.get_bucket(incarnation, 'writing.evaluate', 'w1')
    assert bucket['consumed'] == 2, 'neither replay nor conflict may change the settled amount'


def test_settle_cannot_exceed_the_admitted_bound(engine, incarnation):
    repo = PostgresQuotaRepository(engine)
    repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(10),
        operation_id=op('9'), requested_units=3,
    )
    outcome = repo.settle(operation_id=op('9'), actual_units=4)
    assert outcome['status'] == 'exceeds_admitted'
    bucket = repo.get_bucket(incarnation, 'writing.evaluate', 'w1')
    assert bucket['reserved'] == 3 and bucket['consumed'] == 0


def test_release_before_dispatch_returns_the_units(engine, incarnation):
    repo = PostgresQuotaRepository(engine)
    repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(10),
        operation_id=op('10'), requested_units=4,
    )
    outcome = repo.release(operation_id=op('10'))
    assert outcome['status'] == 'release'
    bucket = repo.get_bucket(incarnation, 'writing.evaluate', 'w1')
    assert bucket['reserved'] == 0 and bucket['consumed'] == 0

    duplicate = repo.release(operation_id=op('10'))
    assert duplicate['status'] == 'duplicate'


def test_release_cannot_undo_a_settlement(engine, incarnation):
    repo = PostgresQuotaRepository(engine)
    repo.reserve(
        incarnation_id=incarnation, meter='writing.evaluate', window=_window(10),
        operation_id=op('11'), requested_units=2,
    )
    repo.settle(operation_id=op('11'), actual_units=2)
    outcome = repo.release(operation_id=op('11'))
    assert outcome['status'] == 'already_settled'
    bucket = repo.get_bucket(incarnation, 'writing.evaluate', 'w1')
    assert bucket['consumed'] == 2


def test_settle_and_release_on_an_unknown_operation_are_named_not_crashed(engine):
    repo = PostgresQuotaRepository(engine)
    assert repo.settle(operation_id=op('never'), actual_units=1)['status'] == 'unknown_operation'
    assert repo.release(operation_id=op('never'))['status'] == 'unknown_operation'


def test_two_racing_reservations_against_a_one_unit_shared_bucket(engine, incarnation):
    """Acceptance matrix: "Quota has one unit, EN and ZH submit concurrently"
    -> one reservation, one exhausted; same shared bucket. Language is
    diagnostic only - both requests target the identical (incarnation, meter,
    window) bucket, distinguished only by operation_id, exactly as two
    submissions in different UI languages would be."""
    repo = PostgresQuotaRepository(engine)
    results, barrier = {}, threading.Barrier(2)
    ids = {name: op(f'race-{name}') for name in ('en', 'zh')}

    def send(name):
        barrier.wait()
        results[name] = repo.reserve(
            incarnation_id=incarnation, meter='writing.evaluate', window=_window(1),
            operation_id=ids[name], requested_units=1,
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
    same = op('same-twice')

    def send(name):
        barrier.wait()
        results[name] = repo.reserve(
            incarnation_id=incarnation, meter='writing.evaluate', window=_window(10),
            operation_id=same, requested_units=1,
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


# --- Review round 1 (0007): identity, windows, dispatch, backstops ----------

def _second_incarnation(engine):
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
                "VALUES (:id, :user, 1, 'active', :now)"
            ),
            {'id': incarnation_id, 'user': user_id, 'now': now},
        )
    return str(incarnation_id)


def test_another_incarnation_replaying_an_operation_id_gets_a_conflict_and_nothing_of_it(engine, incarnation):
    repo = PostgresQuotaRepository(engine)
    first = repo.reserve(incarnation_id=incarnation, meter='writing.evaluate', window=_window(10),
                         operation_id=op('shared'), requested_units=1)
    assert first['status'] == 'admit'
    other = _second_incarnation(engine)
    replay = repo.reserve(incarnation_id=other, meter='writing.evaluate', window=_window(10),
                          operation_id=op('shared'), requested_units=1)
    assert replay == {'status': 'payload_conflict'}, 'no bucket or reservation id of the other account'
    assert repo.get_bucket(other, 'writing.evaluate', 'w1') is None


@pytest.mark.parametrize('change', ['meter', 'window'])
def test_the_same_operation_under_another_meter_or_window_is_a_conflict(engine, incarnation, change):
    repo = PostgresQuotaRepository(engine)
    repo.reserve(incarnation_id=incarnation, meter='writing.evaluate', window=_window(10),
                 operation_id=op('moved'), requested_units=1)
    replay = repo.reserve(
        incarnation_id=incarnation,
        meter='dictionary.lookup' if change == 'meter' else 'writing.evaluate',
        window=_window(10, window_id='w2' if change == 'window' else 'w1'),
        operation_id=op('moved'), requested_units=1,
    )
    assert replay == {'status': 'payload_conflict'}
    assert repo.get_bucket(incarnation, 'writing.evaluate', 'w1')['reserved'] == 1


def test_the_same_operation_from_two_incarnations_at_once_is_one_admission_and_no_error(engine, incarnation):
    repo = PostgresQuotaRepository(engine)
    accounts = {'a': incarnation, 'b': _second_incarnation(engine)}
    same, results, barrier = op('two-accounts'), {}, threading.Barrier(2)

    def send(name):
        barrier.wait()
        try:
            results[name] = repo.reserve(incarnation_id=accounts[name], meter='writing.evaluate',
                                         window=_window(10), operation_id=same, requested_units=1)['status']
        except Exception as error:  # the review reproduced an IntegrityError here
            results[name] = type(error).__name__

    threads = [threading.Thread(target=send, args=(name,)) for name in accounts]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(results.values()) == ['admit', 'payload_conflict']
    reserved = [(repo.get_bucket(inc, 'writing.evaluate', 'w1') or {}).get('reserved', 0) for inc in accounts.values()]
    assert sorted(reserved) == [0, 1]


def test_a_closed_window_admits_nothing_and_writes_nothing(engine, incarnation):
    repo = PostgresQuotaRepository(engine)
    ended = _window(10, start=datetime.now(UTC) - timedelta(days=60))
    outcome = repo.reserve(incarnation_id=incarnation, meter='writing.evaluate', window=ended,
                           operation_id=op('late'), requested_units=1)
    assert outcome == {'status': 'window_closed'}
    assert repo.get_bucket(incarnation, 'writing.evaluate', 'w1') is None
    future = _window(10, window_id='w-next', start=datetime.now(UTC) + timedelta(days=1))
    assert repo.reserve(incarnation_id=incarnation, meter='writing.evaluate', window=future,
                        operation_id=op('early'), requested_units=1)['status'] == 'window_closed'


def test_the_stored_window_decides_and_settlement_still_lands_after_it_ends(engine, incarnation):
    start = datetime.now(UTC) - timedelta(minutes=10)
    window = _window(10, start=start, days=1)
    clock = {'now': start + timedelta(minutes=5)}
    repo = PostgresQuotaRepository(engine, clock=lambda: clock['now'])
    assert repo.reserve(incarnation_id=incarnation, meter='writing.evaluate', window=window,
                        operation_id=op('in'), requested_units=2)['status'] == 'admit'
    clock['now'] = start + timedelta(days=1)  # the half-open end: outside
    # A caller claiming a longer window for the same id does not reopen it.
    stretched = BucketWindow(window_id='w1', window_start=start, window_end=start + timedelta(days=30),
                             policy_version='p1', unit_limit=10)
    assert repo.reserve(incarnation_id=incarnation, meter='writing.evaluate', window=stretched,
                        operation_id=op('after'), requested_units=1)['status'] == 'window_closed'
    assert repo.settle(operation_id=op('in'), actual_units=1)['status'] == 'settle'
    bucket = repo.get_bucket(incarnation, 'writing.evaluate', 'w1')
    assert bucket['reserved'] == 0 and bucket['consumed'] == 1


def test_dispatched_work_keeps_its_reservation_until_settled(engine, incarnation):
    repo = PostgresQuotaRepository(engine)
    repo.reserve(incarnation_id=incarnation, meter='writing.evaluate', window=_window(10),
                 operation_id=op('job'), requested_units=3)
    assert repo.dispatch(operation_id=op('job'), dispatch_ref='job-1')['status'] == 'dispatch'
    assert repo.dispatch(operation_id=op('job'), dispatch_ref='job-1')['status'] == 'duplicate'
    assert repo.dispatch(operation_id=op('job'), dispatch_ref='job-2')['status'] == 'payload_conflict'
    assert repo.release(operation_id=op('job'))['status'] == 'dispatched_retained'
    assert repo.get_bucket(incarnation, 'writing.evaluate', 'w1')['reserved'] == 3
    # A failed outcome that consumes nothing still ends it - by settling 0.
    assert repo.settle(operation_id=op('job'), actual_units=0, outcome_ref='failed')['status'] == 'settle'
    bucket = repo.get_bucket(incarnation, 'writing.evaluate', 'w1')
    assert bucket['reserved'] == 0 and bucket['consumed'] == 0
    assert repo.get_reservation(op('job'))['dispatch_ref'] == 'job-1'


def test_a_deleted_incarnations_work_is_not_dispatched(engine, incarnation):
    repo = PostgresQuotaRepository(engine)
    repo.reserve(incarnation_id=incarnation, meter='writing.evaluate', window=_window(10),
                 operation_id=op('orphan'), requested_units=1)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE account_incarnations SET status = 'deleted', deleted_at = :now WHERE id = :inc"),
            {'now': datetime.now(UTC), 'inc': incarnation},
        )
    assert repo.dispatch(operation_id=op('orphan'), dispatch_ref='j')['status'] == 'denied'
    assert repo.get_reservation(op('orphan'))['state'] == 'reserved'
    assert repo.release(operation_id=op('orphan'))['status'] == 'release'


def test_a_settle_replay_with_another_outcome_is_a_conflict(engine, incarnation):
    repo = PostgresQuotaRepository(engine)
    repo.reserve(incarnation_id=incarnation, meter='writing.evaluate', window=_window(10),
                 operation_id=op('ref'), requested_units=2)
    assert repo.settle(operation_id=op('ref'), actual_units=1, outcome_ref='eval-1')['status'] == 'settle'
    assert repo.settle(operation_id=op('ref'), actual_units=1, outcome_ref='eval-1')['status'] == 'duplicate'
    assert repo.settle(operation_id=op('ref'), actual_units=1, outcome_ref='eval-2')['status'] == 'payload_conflict'
    assert repo.get_reservation(op('ref'))['outcome_ref'] == 'eval-1'


def test_a_reserve_waits_for_an_open_deletion_and_is_then_denied(engine, incarnation):
    """Deterministic: the deletion is held open, uncommitted, while the
    reservation runs; it must wait, then see the deletion."""
    repo = PostgresQuotaRepository(engine)
    holder = engine.connect()
    transaction = holder.begin()
    holder.execute(
        text("UPDATE account_incarnations SET status = 'deleted', deleted_at = :now WHERE id = :inc"),
        {'now': datetime.now(UTC), 'inc': incarnation},
    )
    result, started = {}, threading.Event()

    def send():
        started.set()
        result['outcome'] = repo.reserve(incarnation_id=incarnation, meter='writing.evaluate',
                                         window=_window(10), operation_id=op('racing'), requested_units=1)

    thread = threading.Thread(target=send)
    thread.start()
    started.wait()
    thread.join(timeout=1.0)
    assert thread.is_alive(), 'the reservation must wait for the open deletion'
    transaction.commit()
    holder.close()
    thread.join(timeout=10)
    assert result['outcome'] == {'status': 'denied', 'reason': 'incarnation_deleted'}
    assert repo.get_bucket(incarnation, 'writing.evaluate', 'w1') is None


def test_the_database_refuses_arithmetic_the_code_would_never_write(engine, incarnation):
    from sqlalchemy.exc import IntegrityError

    repo = PostgresQuotaRepository(engine)
    repo.reserve(incarnation_id=incarnation, meter='writing.evaluate', window=_window(2),
                 operation_id=op('guard'), requested_units=2)
    bucket = repo.get_bucket(incarnation, 'writing.evaluate', 'w1')
    for statement in (
        ('UPDATE commerce_quota_buckets SET reserved = reserved + 1 WHERE id = :id', {'id': bucket['id']}),
        ("UPDATE commerce_quota_reservations SET state = 'settled' WHERE operation_id = :op", {'op': op('guard')}),
        ('UPDATE commerce_quota_reservations SET actual_units = 1 WHERE operation_id = :op', {'op': op('guard')}),
        ("UPDATE commerce_quota_reservations SET state = 'settled', actual_units = 3 WHERE operation_id = :op",
         {'op': op('guard')}),
    ):
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(text(statement[0]), statement[1])


# --- Review round 2 (0007): the last unit, and no deadlock ------------------

def test_a_retry_racing_its_original_on_the_last_unit_replays_it(engine, incarnation):
    """Round-2 P1 (a): on a one-unit bucket the retry used to be judged against
    the bucket its twin had just filled and answered `exhausted` while the
    work was admitted and charged."""
    repo = PostgresQuotaRepository(engine)
    for round_ in range(20):
        window = _window(1, window_id=f'last-{round_}')
        same, results, barrier = op(f'last-{round_}'), {}, threading.Barrier(2)

        def send(name, same=same, window=window, results=results, barrier=barrier):
            barrier.wait()
            results[name] = repo.reserve(incarnation_id=incarnation, meter='writing.evaluate',
                                         window=window, operation_id=same, requested_units=1)

        threads = [threading.Thread(target=send, args=(name,)) for name in ('a', 'b')]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert sorted(r['status'] for r in results.values()) == ['admit', 'duplicate'], round_
        assert results['a']['reservation_id'] == results['b']['reservation_id']
        assert repo.get_bucket(incarnation, 'writing.evaluate', window.window_id)['reserved'] == 1


@pytest.mark.parametrize('with_deletion', [False, True])
def test_reserve_retries_mixed_with_dispatch_settle_release_never_deadlock(engine, with_deletion):
    """Round-2 P1 (b), the reviewer's matrix: a reserve retry held the bucket
    and waited on the reservation while settle/release held the reservation
    and waited on the bucket (up to 25 deadlocks per run before the fix)."""
    import random
    import time

    from writing_coach.persistence.incarnation_repository import PostgresIncarnationRepository

    incarnations, repo = PostgresIncarnationRepository(engine), PostgresQuotaRepository(engine)
    errors = []
    for round_ in range(8):
        incarnation = _second_incarnation(engine)
        ids = [op(f'stress-{round_}-{n}') for n in range(10)]
        window = _window(6)
        barrier = threading.Barrier(13 if with_deletion else 12)

        def worker(seed, incarnation=incarnation, ids=ids, window=window, barrier=barrier):
            barrier.wait()
            rnd = random.Random(seed)
            for _ in range(25):
                ident, action = rnd.choice(ids), rnd.choice(('reserve', 'dispatch', 'settle', 'release'))
                try:
                    if action == 'reserve':
                        repo.reserve(incarnation_id=incarnation, meter='m', window=window,
                                     operation_id=ident, requested_units=1)
                    elif action == 'dispatch':
                        repo.dispatch(operation_id=ident, dispatch_ref='d')
                    elif action == 'settle':
                        repo.settle(operation_id=ident, actual_units=rnd.choice((0, 1)))
                    else:
                        repo.release(operation_id=ident)
                except Exception as error:  # a deadlock is what this test exists to catch
                    errors.append(f'{action}: {type(error).__name__}: {" | ".join(str(error).splitlines()[:6])[:700]}')

        def delete(incarnation=incarnation, barrier=barrier):
            barrier.wait()
            time.sleep(random.random() * 0.2)
            incarnations.mark_deleted(incarnation)

        threads = [threading.Thread(target=worker, args=(round_ * 100 + k,)) for k in range(12)]
        if with_deletion:
            threads.append(threading.Thread(target=delete))
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        bucket = repo.get_bucket(incarnation, 'm', window.window_id)
        assert bucket is None or bucket['consumed'] + bucket['reserved'] <= 6
    assert errors == []
