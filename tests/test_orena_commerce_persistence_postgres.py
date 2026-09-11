"""I3 subscription-inbox concurrency proof. Real PostgreSQL, real races.

Skips unless `ORENA_TEST_POSTGRES_URL` names a throwaway database. The
migration this exercises is `migrations/proposed/20260911_0006` — still
awaiting review — so the fixture points Alembic's `version_locations` at
both `versions/` and `proposed/` rather than plain `head`, the same
technique `migrations/proposed/README.md` describes and the way
`test_orena_work_persistence_postgres.py` ran while I2 was still proposed.

    ORENA_TEST_POSTGRES_URL=postgresql+psycopg://user:pw@host/orena_i3_test \\
        python -m pytest tests/test_orena_commerce_persistence_postgres.py
"""
from __future__ import annotations

import os
import threading
import uuid
from datetime import UTC, datetime

import pytest

sqlalchemy = pytest.importorskip('sqlalchemy')
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from writing_coach.persistence.commerce_repository import (  # noqa: E402
    PostgresCommerceRepository,
    SubscriptionUpdate,
)
from writing_coach.persistence.incarnation_repository import (  # noqa: E402
    PostgresIncarnationRepository,
)

URL = os.getenv('ORENA_TEST_POSTGRES_URL', '')
pytestmark = pytest.mark.skipif(
    not URL, reason='ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run'
)

TABLES = ('commerce_billing_event_receipts', 'commerce_subscriptions')

# No external_subscription_id here: it is now unique per (provider, id) via
# uq_commerce_subscription_external, and this fixture is shared by tests that
# each create their own incarnation - a fixed non-NULL value would collide
# across them the moment more than one test in the module applies it. Left
# NULL by default; the one test that actually exercises the uniqueness
# invariant sets its own explicit, test-local values.
_UPDATE = SubscriptionUpdate(
    state='active', plan_id='premium', external_customer_id=None,
    external_subscription_id=None, paid_through=None, cancel_at_period_end=False,
)


@pytest.fixture(scope='module')
def engine():
    from pathlib import Path

    from alembic import command
    from writing_coach.persistence.runtime import _runtime_alembic_config

    root = Path(__file__).resolve().parents[1]
    cfg = _runtime_alembic_config()
    cfg.set_main_option('sqlalchemy.url', URL.replace('%', '%%'))
    # `path_separator=os` means "split on os.pathsep" (':' on Linux, ';' on
    # Windows) - not a literal space. Joining with anything else here is
    # exactly the defect I2_ACTIVATION_RUNBOOK.md §7 already names: a
    # mismatched separator silently produces a one-element, nonexistent path
    # and every revision in it goes undiscovered rather than erroring loudly.
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
            {'id': user_id, 'key': f'sub-{user_id}', 'email': '', 'name': '',
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


def test_first_verified_event_applies(engine, incarnation):
    repo = PostgresCommerceRepository(engine)
    outcome = repo.record_event(
        incarnation_id=incarnation, provider='stripe', external_event_id='evt-1',
        event_object_version=1, update=_UPDATE,
    )
    assert outcome['status'] == 'apply'
    row = repo.get_subscription(incarnation)
    assert row['state'] == 'active' and row['object_version'] == 1


def test_duplicate_event_id_does_not_repeat_or_move_state(engine, incarnation):
    repo = PostgresCommerceRepository(engine)
    first = repo.record_event(
        incarnation_id=incarnation, provider='stripe', external_event_id='evt-dup',
        event_object_version=1, update=_UPDATE,
    )
    assert first['status'] == 'apply'
    replay = repo.record_event(
        incarnation_id=incarnation, provider='stripe', external_event_id='evt-dup',
        event_object_version=1,
        update=SubscriptionUpdate('ended', 'free', None, None, None, False),
    )
    assert replay['status'] == 'duplicate'
    # The replay's (different) payload must never have been applied.
    assert repo.get_subscription(incarnation)['state'] == 'active'


def test_reversed_out_of_order_event_is_rejected_as_stale(engine, incarnation):
    repo = PostgresCommerceRepository(engine)
    repo.record_event(
        incarnation_id=incarnation, provider='stripe', external_event_id='evt-newer',
        event_object_version=5, update=_UPDATE,
    )
    stale = repo.record_event(
        incarnation_id=incarnation, provider='stripe', external_event_id='evt-older',
        event_object_version=2,
        update=SubscriptionUpdate('ended', 'free', None, None, None, False),
    )
    assert stale['status'] == 'stale'
    assert repo.get_subscription(incarnation)['object_version'] == 5


def test_unverifiable_version_does_not_overwrite_known_state(engine, incarnation):
    repo = PostgresCommerceRepository(engine)
    repo.record_event(
        incarnation_id=incarnation, provider='stripe', external_event_id='evt-known',
        event_object_version=1, update=_UPDATE,
    )
    unknown = repo.record_event(
        incarnation_id=incarnation, provider='stripe', external_event_id='evt-unverifiable',
        event_object_version=None,
        update=SubscriptionUpdate('ended', 'free', None, None, None, False),
    )
    assert unknown['status'] == 'unknown'
    assert repo.get_subscription(incarnation)['state'] == 'active'


def test_deleted_incarnation_gets_a_durable_receipt_but_no_subscription_row(engine, incarnation):
    """P1 finding 3: a receipt is idempotency/audit state, not a grant - a
    deleted incarnation still gets one, durably, but never a subscription
    row, and redelivery does not create either kind of state."""
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE account_incarnations SET status = 'deleted', deleted_at = :now "
                'WHERE id = :inc'
            ),
            {'now': datetime.now(UTC), 'inc': incarnation},
        )
    repo = PostgresCommerceRepository(engine)
    first = repo.record_event(
        incarnation_id=incarnation, provider='stripe', external_event_id='evt-after-delete',
        event_object_version=1, update=_UPDATE,
    )
    assert first['status'] == 'deleted_incarnation_rejected'
    assert repo.get_subscription(incarnation) is None
    receipt = repo.get_receipt('stripe', 'evt-after-delete')
    assert receipt is not None, 'the event must be durably retained, not silently dropped'
    assert receipt['processing_state'] == 'ignored'
    assert receipt['sanitized_failure_reason'] == 'deleted_incarnation_rejected'

    # Repeated delivery of the same provider event is not a brand-new event:
    # once terminal, a redelivery is 'duplicate', not re-evaluated against
    # (still) 'deleted_incarnation_rejected' or anything else.
    again = repo.record_event(
        incarnation_id=incarnation, provider='stripe', external_event_id='evt-after-delete',
        event_object_version=1, update=_UPDATE,
    )
    assert again['status'] == 'duplicate'
    assert repo.get_subscription(incarnation) is None


def test_two_racing_events_only_the_newer_verified_version_wins(engine, incarnation):
    """Matrix: duplicate/reversed provider subscription events -> canonical
    current state, no duplicate grant or usage reset."""
    repo = PostgresCommerceRepository(engine)
    results, barrier = {}, threading.Barrier(2)

    def send(name, version):
        barrier.wait()
        results[name] = repo.record_event(
            incarnation_id=incarnation, provider='stripe', external_event_id=f'evt-race-{name}',
            event_object_version=version, update=_UPDATE,
        )

    threads = [
        threading.Thread(target=send, args=('a', 10)),
        threading.Thread(target=send, args=('b', 7)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # Order-independent invariant, not a specific pair of statuses: whichever
    # arrives first applies outright (nothing recorded yet to be stale
    # against); if the lower version (7) happens to go first, the higher one
    # (10) still applies after it, so both can legitimately read 'apply'.
    # What must never happen is the lower version winning the final state, or
    # either side reading 'unknown'/'duplicate'/anything but apply-or-stale.
    statuses = {results[name]['status'] for name in ('a', 'b')}
    assert statuses <= {'apply', 'stale'}
    assert 'apply' in statuses
    assert repo.get_subscription(incarnation)['object_version'] == 10


def test_unknown_event_reconciles_to_apply_then_further_retries_are_duplicate(engine, incarnation):
    """P1 finding 1, full lifecycle required by review:
    unknown -> receipt retained -> no state changed -> authoritative version
    obtained -> same event id reconciles to apply -> further retry duplicate.
    """
    repo = PostgresCommerceRepository(engine)

    first = repo.record_event(
        incarnation_id=incarnation, provider='stripe', external_event_id='evt-reconcile',
        event_object_version=None, update=_UPDATE,
    )
    assert first['status'] == 'unknown'
    # A neutral placeholder row (state='none') is expected - it exists only
    # so the next event has something to lock against - but it must never be
    # a known-good/paid state.
    placeholder = repo.get_subscription(incarnation)
    assert placeholder is None or placeholder['state'] == 'none'
    receipt = repo.get_receipt('stripe', 'evt-reconcile')
    assert receipt['processing_state'] == 'received', 'non-terminal: must not block reconciliation'

    # Authoritative provider state is later obtained; the same event id is
    # reconciled by calling record_event() again, now with a real version.
    reconciled = repo.record_event(
        incarnation_id=incarnation, provider='stripe', external_event_id='evt-reconcile',
        event_object_version=3, update=_UPDATE,
    )
    assert reconciled['status'] == 'apply'
    assert repo.get_subscription(incarnation)['object_version'] == 3
    assert repo.get_receipt('stripe', 'evt-reconcile')['processing_state'] == 'applied'

    # Now terminal: a further retry of the same event id is a duplicate, not
    # a second reconciliation.
    again = repo.record_event(
        incarnation_id=incarnation, provider='stripe', external_event_id='evt-reconcile',
        event_object_version=3, update=_UPDATE,
    )
    assert again['status'] == 'duplicate'


def test_billing_callback_serializes_with_incarnation_deletion(engine):
    """P1 finding 2: record_event() vs incarnation_repository.mark_deleted()
    must not race. After both finish, a callback can never have applied paid
    state past the deletion boundary."""
    now = datetime.now(UTC)
    user_id, incarnation_id = uuid.uuid4(), uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                'INSERT INTO users (id, user_key, email, name, picture, role, created_at) '
                'VALUES (:id, :key, :email, :name, :pic, :role, :now)'
            ),
            {'id': user_id, 'key': f'sub-{user_id}', 'email': '', 'name': '',
             'pic': '', 'role': 'user', 'now': now},
        )
        connection.execute(
            text(
                'INSERT INTO account_incarnations (id, user_id, epoch, status, created_at) '
                'VALUES (:id, :user, 1, :status, :now)'
            ),
            {'id': incarnation_id, 'user': user_id, 'status': 'active', 'now': now},
        )
    incarnation_id = str(incarnation_id)

    commerce = PostgresCommerceRepository(engine)
    incarnations = PostgresIncarnationRepository(engine)
    results, barrier = {}, threading.Barrier(2)

    def bill():
        barrier.wait()
        results['billing'] = commerce.record_event(
            incarnation_id=incarnation_id, provider='stripe', external_event_id='evt-vs-delete',
            event_object_version=1, update=_UPDATE,
        )

    def delete():
        barrier.wait()
        incarnations.mark_deleted(incarnation_id)

    threads = [threading.Thread(target=bill), threading.Thread(target=delete)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    with engine.connect() as connection:
        status = connection.execute(
            text('SELECT status FROM account_incarnations WHERE id = :id'),
            {'id': incarnation_id},
        ).scalar_one()
    assert status == 'deleted'

    subscription = commerce.get_subscription(incarnation_id)
    if results['billing']['status'] == 'apply':
        # Billing's transaction committed first (deletion serialized after
        # it, on the same row) - a legitimate ordering, but the deletion must
        # not have left paid state behind it: nothing here re-derives that
        # invariant automatically, so the case this test exists to catch is
        # the *other* branch below. Documented, not silently accepted:
        # activation/downgrade-on-delete policy is a human gate ARCHITECTURE_
        # INVARIANTS.md §7 reserves, not decided by this proposal.
        assert subscription is not None and subscription['state'] == 'active'
    else:
        # Deletion won the race: billing must see the incarnation as already
        # deleted and create no subscription state past that boundary.
        assert results['billing']['status'] == 'deleted_incarnation_rejected'
        assert subscription is None


def test_duplicate_external_subscription_mapping_is_rejected_by_the_database(engine, incarnation):
    """P2 finding 4: one provider subscription must never map to more than
    one incarnation - enforced by the schema itself, not caller discipline."""
    now = datetime.now(UTC)
    user_id, other_incarnation = uuid.uuid4(), uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                'INSERT INTO users (id, user_key, email, name, picture, role, created_at) '
                'VALUES (:id, :key, :email, :name, :pic, :role, :now)'
            ),
            {'id': user_id, 'key': f'sub-{user_id}', 'email': '', 'name': '',
             'pic': '', 'role': 'user', 'now': now},
        )
        connection.execute(
            text(
                'INSERT INTO account_incarnations (id, user_id, epoch, status, created_at) '
                'VALUES (:id, :user, 1, :status, :now)'
            ),
            {'id': other_incarnation, 'user': user_id, 'status': 'active', 'now': now},
        )

    repo = PostgresCommerceRepository(engine)
    shared_mapping = SubscriptionUpdate(
        state='active', plan_id='premium', external_customer_id='cus_shared',
        external_subscription_id='sub_shared', paid_through=None, cancel_at_period_end=False,
    )
    first = repo.record_event(
        incarnation_id=incarnation, provider='stripe', external_event_id='evt-map-1',
        event_object_version=1, update=shared_mapping,
    )
    assert first['status'] == 'apply'

    with pytest.raises(IntegrityError):
        repo.record_event(
            incarnation_id=str(other_incarnation), provider='stripe', external_event_id='evt-map-2',
            event_object_version=1, update=shared_mapping,
        )


def test_same_event_id_under_concurrent_processing_is_exactly_once(engine, incarnation):
    """Required regression coverage: the same provider event delivered
    concurrently (a real double-send, not two distinct events) is exactly
    one outcome, not an 'apply' racing another 'apply'."""
    repo = PostgresCommerceRepository(engine)
    results, barrier = {}, threading.Barrier(2)

    def send(name):
        barrier.wait()
        results[name] = repo.record_event(
            incarnation_id=incarnation, provider='stripe', external_event_id='evt-same-twice',
            event_object_version=1, update=_UPDATE,
        )

    threads = [threading.Thread(target=send, args=('a',)), threading.Thread(target=send, args=('b',))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    statuses = sorted(results[name]['status'] for name in ('a', 'b'))
    assert statuses == ['apply', 'duplicate']
    assert repo.get_subscription(incarnation)['object_version'] == 1
