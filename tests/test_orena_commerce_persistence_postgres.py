"""I3 subscription-inbox concurrency proof. Real PostgreSQL, real races.

Skips unless `ORENA_TEST_POSTGRES_URL` names a throwaway database. The
migration this exercises is `migrations/proposed/20260911_0006` — still
awaiting review — so the fixture points Alembic's `version_locations` at
both `versions/` and `proposed/` rather than plain `head`, the same
technique `migrations/proposed/README.md` describes and the way
`test_orena_work_persistence_postgres.py` ran while I2 was still proposed.

Every event and provider-subscription id is unique per run, so the file can
be re-run against the same database.

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
from sqlalchemy.exc import DBAPIError  # noqa: E402

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

_RUN: dict[str, str] = {}


@pytest.fixture(autouse=True)
def _fresh_ids():
    _RUN.clear()
    _RUN['suffix'] = uuid.uuid4().hex[:12]


def ev(name: str) -> str:
    return f'evt-{name}-{_RUN["suffix"]}'


def sub(name: str) -> str:
    return f'sub_{name}_{_RUN["suffix"]}'


def upd(state: str = 'active', subscription: str | None = 'x', *, customer: str | None = None,
        plan: str = 'premium', provider_state: str | None = None) -> SubscriptionUpdate:
    return SubscriptionUpdate(
        state=state, plan_id=plan, external_customer_id=customer,
        external_subscription_id=sub(subscription) if subscription else None,
        paid_through=None, cancel_at_period_end=False, provider_state=provider_state,
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


def _account(engine) -> tuple[str, str]:
    """A fresh account and its active incarnation."""
    user_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                'INSERT INTO users (id, user_key, email, name, picture, role, created_at) '
                'VALUES (:id, :key, :email, :name, :pic, :role, :now)'
            ),
            {'id': user_id, 'key': f'sub-{user_id}', 'email': '', 'name': '',
             'pic': '', 'role': 'user', 'now': datetime.now(UTC)},
        )
    return str(user_id), PostgresIncarnationRepository(engine).ensure_active(str(user_id))


@pytest.fixture
def incarnation(engine):
    return _account(engine)[1]


def _record(repo, incarnation, name, version, update, **extra):
    return repo.record_event(incarnation_id=incarnation, provider='stripe', external_event_id=ev(name),
                             event_object_version=version, update=update, **extra)


def test_first_verified_event_applies(engine, incarnation):
    repo = PostgresCommerceRepository(engine)
    outcome = _record(repo, incarnation, '1', 1, upd(provider_state='active'))
    assert outcome == {'status': 'apply', 'state': 'active', 'current': 'replaced'}
    row = repo.get_subscription(incarnation)
    assert row['state'] == 'active' and row['object_version'] == 1
    assert row['external_subscription_id'] == sub('x') and row['provider_state'] == 'active'
    assert row['reconciliation_state'] == 'current'
    assert repo.get_provider_subscription('stripe', sub('x'))['object_version'] == 1


def test_duplicate_event_id_does_not_repeat_or_move_state(engine, incarnation):
    repo = PostgresCommerceRepository(engine)
    assert _record(repo, incarnation, 'dup', 1, upd())['status'] == 'apply'
    replay = _record(repo, incarnation, 'dup', 1, upd('ended', plan='free'))
    assert replay['status'] == 'duplicate'
    assert repo.get_subscription(incarnation)['state'] == 'active'


def test_reversed_out_of_order_event_of_one_subscription_is_stale(engine, incarnation):
    repo = PostgresCommerceRepository(engine)
    _record(repo, incarnation, 'newer', 5, upd())
    stale = _record(repo, incarnation, 'older', 2, upd('ended', plan='free'))
    assert stale['status'] == 'stale'
    assert repo.get_subscription(incarnation)['object_version'] == 5
    assert repo.get_receipt('stripe', ev('older'))['processing_state'] == 'ignored'


def test_unverifiable_version_does_not_overwrite_known_state_and_marks_reconciliation(engine, incarnation):
    repo = PostgresCommerceRepository(engine)
    _record(repo, incarnation, 'known', 1, upd())
    unknown = _record(repo, incarnation, 'unverifiable', None, upd('ended', plan='free'))
    assert unknown['status'] == 'unknown'
    row = repo.get_subscription(incarnation)
    assert row['state'] == 'active' and row['reconciliation_state'] == 'pending'


def test_an_event_naming_no_subscription_is_unknown_and_erases_nothing(engine, incarnation):
    """Round-1 P2-d: a `past_due` event with no subscription id used to set
    the stored `external_subscription_id` to NULL."""
    repo = PostgresCommerceRepository(engine)
    _record(repo, incarnation, 'mapped', 1, upd(customer='cus_1'))
    outcome = _record(repo, incarnation, 'anonymous', 2, upd('past_due', subscription=None))
    assert outcome['status'] == 'unknown'
    row = repo.get_subscription(incarnation)
    assert row['external_subscription_id'] == sub('x') and row['external_customer_id'] == 'cus_1'
    assert row['state'] == 'active'


def test_an_applied_event_without_a_customer_id_keeps_the_stored_one(engine, incarnation):
    repo = PostgresCommerceRepository(engine)
    _record(repo, incarnation, 'with-customer', 1, upd(customer='cus_1'))
    assert _record(repo, incarnation, 'without', 2, upd('past_due'))['status'] == 'apply'
    row = repo.get_subscription(incarnation)
    assert row['state'] == 'past_due' and row['external_customer_id'] == 'cus_1'


def test_deleted_incarnation_gets_a_durable_receipt_but_no_commerce_row(engine, incarnation):
    PostgresIncarnationRepository(engine).mark_deleted(incarnation)
    repo = PostgresCommerceRepository(engine)
    first = _record(repo, incarnation, 'after-delete', 1, upd())
    assert first['status'] == 'deleted_incarnation_rejected'
    assert repo.get_subscription(incarnation) is None
    assert repo.get_provider_subscription('stripe', sub('x')) is None
    receipt = repo.get_receipt('stripe', ev('after-delete'))
    assert receipt['processing_state'] == 'ignored'
    assert receipt['sanitized_failure_reason'] == 'deleted_incarnation_rejected'
    assert _record(repo, incarnation, 'after-delete', 1, upd())['status'] == 'duplicate'
    assert repo.get_subscription(incarnation) is None


def test_an_old_incarnations_event_is_never_moved_onto_the_new_one(engine):
    """Round-1 P1-A, the reviewer's reproduction: A's event is `unknown`; A is
    deleted and re-registered as B; reconciling the event under B used to
    rewrite the receipt to B and make B's subscription active."""
    user, first = _account(engine)
    incarnations = PostgresIncarnationRepository(engine)
    repo = PostgresCommerceRepository(engine)
    assert _record(repo, first, 'orphan', None, upd())['status'] == 'unknown'
    incarnations.mark_deleted(first)
    second = incarnations.register_new(user)

    outcome = _record(repo, second, 'orphan', 3, upd())
    assert outcome == {'status': 'foreign_incarnation'}
    receipt = repo.get_receipt('stripe', ev('orphan'))
    assert str(receipt['incarnation_id']) == first, 'the stored incarnation is authoritative'
    assert receipt['processing_state'] == 'received', 'a foreign call cannot close the owner reconciliation'
    assert (repo.get_subscription(second) or {}).get('state', 'none') == 'none'

    # The owner's own historical reconciliation still closes it - as deleted.
    assert _record(repo, first, 'orphan', 3, upd())['status'] == 'deleted_incarnation_rejected'
    receipt = repo.get_receipt('stripe', ev('orphan'))
    assert str(receipt['incarnation_id']) == first and receipt['processing_state'] == 'ignored'


def test_a_resubscription_after_an_ended_subscription_applies(engine, incarnation):
    """Round-1 P1-B, the reviewer's reproduction: sub_X applied at v7, ended
    at v8; the learner resubscribes as sub_Y at v1, which used to be `stale`
    for good."""
    repo = PostgresCommerceRepository(engine)
    _record(repo, incarnation, 'x7', 7, upd('active', 'x'))
    _record(repo, incarnation, 'x8', 8, upd('ended', 'x', plan='free'))
    outcome = _record(repo, incarnation, 'y1', 1, upd('active', 'y'))
    assert outcome == {'status': 'apply', 'state': 'active', 'current': 'replaced'}
    row = repo.get_subscription(incarnation)
    assert row['external_subscription_id'] == sub('y') and row['state'] == 'active'
    assert row['object_version'] == 1


def test_a_late_event_of_the_old_subscription_never_overwrites_the_new_one(engine, incarnation):
    """Round-1 P1-B, the reverse: a late event of the old subscription with a
    higher version used to overwrite the new, active one."""
    repo = PostgresCommerceRepository(engine)
    _record(repo, incarnation, 'x7', 7, upd('active', 'x'))
    _record(repo, incarnation, 'x8', 8, upd('ended', 'x', plan='free'))
    _record(repo, incarnation, 'y1', 1, upd('active', 'y'))

    # Stale against sub_X's own history.
    assert _record(repo, incarnation, 'x5', 5, upd('active', 'x'))['status'] == 'stale'
    # sub_X's own history moves on; the current subscription is untouched.
    kept = _record(repo, incarnation, 'x9', 9, upd('ended', 'x', plan='free'))
    assert kept == {'status': 'apply', 'state': 'ended', 'current': 'kept'}
    assert repo.get_provider_subscription('stripe', sub('x'))['object_version'] == 9
    # sub_X claiming to be live again while sub_Y is live: refetch, never guess.
    assert _record(repo, incarnation, 'x10', 10, upd('active', 'x'))['status'] == 'unknown'
    row = repo.get_subscription(incarnation)
    assert row['external_subscription_id'] == sub('y') and row['state'] == 'active'
    assert row['object_version'] == 1 and row['reconciliation_state'] == 'pending'
    assert repo.get_provider_subscription('stripe', sub('x'))['object_version'] == 9, 'not advanced'


def test_a_subscription_mapped_elsewhere_is_refused_without_an_error_or_a_lost_receipt(engine, incarnation):
    """Round-1 P2-c: the mapping conflict used to raise and roll back the
    receipt, so every webhook retry raised again."""
    repo = PostgresCommerceRepository(engine)
    assert _record(repo, incarnation, 'map-1', 1, upd(customer='cus_shared'))['status'] == 'apply'
    other = _account(engine)[1]
    for _ in range(2):
        assert _record(repo, other, 'map-2', 1, upd(customer='cus_shared')) == {'status': 'foreign_incarnation'}
    receipt = repo.get_receipt('stripe', ev('map-2'))
    assert receipt is not None and str(receipt['incarnation_id']) == incarnation
    assert (repo.get_subscription(other) or {}).get('external_subscription_id') is None
    assert str(repo.get_provider_subscription('stripe', sub('x'))['incarnation_id']) == incarnation


def test_a_misrouted_first_delivery_leaves_the_event_for_its_owner(engine, incarnation):
    """Round-2 P2-1 (N1): A owns sub_X at v1; v2 is first routed to C. It used
    to be filed under C as final `ignored`, so A's own delivery was a
    `duplicate` and A's update was lost."""
    repo = PostgresCommerceRepository(engine)
    _record(repo, incarnation, 'n1-v1', 1, upd('active'))
    stranger = _account(engine)[1]
    assert _record(repo, stranger, 'n1-v2', 2, upd('past_due')) == {'status': 'foreign_incarnation'}
    receipt = repo.get_receipt('stripe', ev('n1-v2'))
    assert str(receipt['incarnation_id']) == incarnation and receipt['processing_state'] == 'received'
    assert _record(repo, incarnation, 'n1-v2', 2, upd('past_due'))['status'] == 'apply'
    assert repo.get_provider_subscription('stripe', sub('x'))['object_version'] == 2
    assert repo.get_subscription(incarnation)['state'] == 'past_due'


def test_an_undecided_event_first_filed_under_a_stranger_is_handed_to_the_owner(engine, incarnation):
    repo = PostgresCommerceRepository(engine)
    _record(repo, incarnation, 'n1b-v1', 1, upd('active'))
    stranger = _account(engine)[1]
    # No version yet: the stranger's call is `foreign_incarnation` all the same.
    assert _record(repo, stranger, 'n1b-v2', None, upd('past_due'))['status'] == 'foreign_incarnation'
    assert str(repo.get_receipt('stripe', ev('n1b-v2'))['incarnation_id']) == incarnation
    assert _record(repo, incarnation, 'n1b-v2', 2, upd('past_due'))['status'] == 'apply'


def test_an_undecided_event_maps_no_subscription(engine, incarnation):
    """Round-2 P3 (N2): an event that ends `unknown` used to commit a
    permanent mapping of its subscription, with no version."""
    repo = PostgresCommerceRepository(engine)
    _record(repo, incarnation, 'n2-y', 1, upd('active', 'y'))
    # sub_Z live while sub_Y is live: undecided.
    assert _record(repo, incarnation, 'n2-z', 1, upd('active', 'z'))['status'] == 'unknown'
    assert repo.get_provider_subscription('stripe', sub('z')) is None
    # Nothing was claimed, so another account's verified event for sub_Z is
    # decided on its own merits.
    other = _account(engine)[1]
    assert _record(repo, other, 'n2-z-other', 1, upd('active', 'z'))['status'] == 'apply'


def test_reconciliation_is_pending_exactly_while_an_event_waits(engine, incarnation):
    """Round-2 P2-2: the flag stuck at `pending` after the waiting event was
    decided as `kept` (N3), and cleared while another still waited (N4)."""
    repo = PostgresCommerceRepository(engine)
    _record(repo, incarnation, 'r-x1', 1, upd('active', 'x'))
    _record(repo, incarnation, 'r-x2', 2, upd('ended', 'x', plan='free'))
    _record(repo, incarnation, 'r-y1', 1, upd('active', 'y'))
    # N3: an undecided event for the ended sub_X, later decided as `kept`.
    assert _record(repo, incarnation, 'r-x3', None, upd('ended', 'x'))['status'] == 'unknown'
    assert repo.get_subscription(incarnation)['reconciliation_state'] == 'pending'
    assert _record(repo, incarnation, 'r-x3', 3, upd('ended', 'x'))['current'] == 'kept'
    assert repo.get_subscription(incarnation)['reconciliation_state'] == 'current'
    # N4: a `replace` does not clear it while another event still waits.
    assert _record(repo, incarnation, 'r-y-wait', None, upd('past_due', 'y'))['status'] == 'unknown'
    assert _record(repo, incarnation, 'r-y2', 2, upd('active', 'y'))['current'] == 'replaced'
    assert repo.get_subscription(incarnation)['reconciliation_state'] == 'pending'
    assert _record(repo, incarnation, 'r-y-wait', 3, upd('past_due', 'y'))['status'] == 'apply'
    assert repo.get_subscription(incarnation)['reconciliation_state'] == 'current'


def test_a_known_paid_through_date_is_kept_but_not_inherited(engine, incarnation):
    repo = PostgresCommerceRepository(engine)
    until = datetime(2026, 10, 13, tzinfo=UTC)
    dated = SubscriptionUpdate('active', 'premium', None, sub('x'), until, False)
    _record(repo, incarnation, 'pt-1', 1, dated)
    _record(repo, incarnation, 'pt-2', 2, upd('active', 'x'))
    assert repo.get_subscription(incarnation)['paid_through'] == until
    _record(repo, incarnation, 'pt-3', 3, upd('ended', 'x', plan='free'))
    _record(repo, incarnation, 'pt-y', 1, upd('active', 'y'))
    assert repo.get_subscription(incarnation)['paid_through'] is None, 'a new subscription starts clean'


def test_a_reused_event_id_with_other_content_changes_nothing(engine, incarnation):
    repo = PostgresCommerceRepository(engine)
    _record(repo, incarnation, 'digest', None, upd(), payload_digest='a' * 64)
    clash = _record(repo, incarnation, 'digest', 2, upd('ended'), payload_digest='b' * 64)
    assert clash == {'status': 'payload_conflict'}
    assert repo.get_receipt('stripe', ev('digest'))['processing_state'] == 'received'
    assert _record(repo, incarnation, 'digest', 2, upd(), payload_digest='a' * 64)['status'] == 'apply'


def test_the_database_keeps_a_terminal_receipt_final(engine, incarnation):
    repo = PostgresCommerceRepository(engine)
    _record(repo, incarnation, 'final', 1, upd())
    for statement in (
        "UPDATE commerce_billing_event_receipts SET processing_state = 'received' "
        'WHERE provider = :p AND external_event_id = :e',
        # Round-2 P3 (N9): the trigger covered UPDATE only.
        'DELETE FROM commerce_billing_event_receipts WHERE provider = :p AND external_event_id = :e',
    ):
        with pytest.raises(DBAPIError):
            with engine.begin() as connection:
                connection.execute(text(statement), {'p': 'stripe', 'e': ev('final')})
    assert repo.get_receipt('stripe', ev('final'))['processing_state'] == 'applied'


def test_two_racing_events_only_the_newer_verified_version_wins(engine, incarnation):
    """Matrix: duplicate/reversed provider subscription events -> canonical
    current state, no duplicate grant or usage reset."""
    repo = PostgresCommerceRepository(engine)
    results, barrier = {}, threading.Barrier(2)

    def send(name, version):
        barrier.wait()
        results[name] = _record(repo, incarnation, f'race-{name}', version, upd())

    threads = [threading.Thread(target=send, args=('a', 10)), threading.Thread(target=send, args=('b', 7))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    statuses = {results[name]['status'] for name in ('a', 'b')}
    assert statuses <= {'apply', 'stale'} and 'apply' in statuses
    assert repo.get_subscription(incarnation)['object_version'] == 10


def test_unknown_event_reconciles_to_apply_then_further_retries_are_duplicate(engine, incarnation):
    repo = PostgresCommerceRepository(engine)
    assert _record(repo, incarnation, 'reconcile', None, upd())['status'] == 'unknown'
    assert repo.get_subscription(incarnation) is None, 'an undecided event creates no subscription state'
    assert repo.reconciliation_state(incarnation) == 'pending'
    assert repo.get_receipt('stripe', ev('reconcile'))['processing_state'] == 'received'

    reconciled = _record(repo, incarnation, 'reconcile', 3, upd())
    assert reconciled['status'] == 'apply'
    row = repo.get_subscription(incarnation)
    assert row['object_version'] == 3 and row['reconciliation_state'] == 'current'
    assert repo.get_receipt('stripe', ev('reconcile'))['processing_state'] == 'applied'
    assert _record(repo, incarnation, 'reconcile', 3, upd())['status'] == 'duplicate'


def test_a_billing_callback_waits_for_an_open_deletion_and_is_then_rejected(engine, incarnation):
    """Round-1 P2-e: deterministic. The deletion is held open, uncommitted,
    while the callback runs: the callback must wait, then see the deletion.
    (The earlier racing version also accepted the pre-fix outcome.)"""
    repo = PostgresCommerceRepository(engine)
    holder = engine.connect()
    transaction = holder.begin()
    holder.execute(
        text("UPDATE account_incarnations SET status = 'deleted', deleted_at = :now WHERE id = :inc"),
        {'now': datetime.now(UTC), 'inc': incarnation},
    )
    result, started = {}, threading.Event()

    def bill():
        started.set()
        result['outcome'] = _record(repo, incarnation, 'vs-delete', 1, upd())

    thread = threading.Thread(target=bill)
    thread.start()
    started.wait()
    thread.join(timeout=1.0)
    assert thread.is_alive(), 'the callback must wait for the open deletion'
    transaction.commit()
    holder.close()
    thread.join(timeout=10)
    assert result['outcome'] == {'status': 'deleted_incarnation_rejected'}
    assert repo.get_subscription(incarnation) is None
    assert repo.get_provider_subscription('stripe', sub('x')) is None


def test_same_event_id_under_concurrent_processing_is_exactly_once(engine, incarnation):
    repo = PostgresCommerceRepository(engine)
    results, barrier = {}, threading.Barrier(2)

    def send(name):
        barrier.wait()
        results[name] = _record(repo, incarnation, 'same-twice', 1, upd())

    threads = [threading.Thread(target=send, args=(name,)) for name in ('a', 'b')]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(results[name]['status'] for name in ('a', 'b')) == ['apply', 'duplicate']
    assert repo.get_subscription(incarnation)['object_version'] == 1
