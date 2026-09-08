"""I2 concurrency proof. Real PostgreSQL, real concurrent sessions.

The acceptance matrix rows this package owns cannot be shown with SQLite or
with a single connection: they are about two transactions racing, and about
what a reader sees while a writer holds a lock. Each test below is one row of
the matrix in ORENA_BACKBONE_INTEGRATION_GATES.

These skip unless `ORENA_TEST_POSTGRES_URL` names a throwaway database. They do
not run against the runtime database and they do not create the schema in one:
the migration is applied to the test database by the fixture, and the migration
itself is still awaiting Codex review and schema authorization.

    ORENA_TEST_POSTGRES_URL=postgresql+psycopg://user:pw@host/orena_i2_test \\
        python -m pytest tests/test_orena_work_persistence_postgres.py
"""
from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, UTC

import pytest

sqlalchemy = pytest.importorskip('sqlalchemy')
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from writing_coach.persistence.work_repository import (  # noqa: E402
    PostgresWorkRepository,
    semantic_digest,
)
from writing_coach.reference_backbone import Scope  # noqa: E402
from writing_coach.work_contract import sequence_is_contiguous  # noqa: E402

URL = os.getenv('ORENA_TEST_POSTGRES_URL', '')
pytestmark = pytest.mark.skipif(
    not URL, reason='ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run'
)

TABLES = (
    'projection_checkpoints', 'language_provenance', 'work_turns', 'works',
    'change_records', 'mutation_receipts', 'account_streams', 'account_incarnations',
)


@pytest.fixture(scope='module')
def engine():
    """A throwaway database with the proposal applied to it, and only it.

    The proposal lives in `migrations/proposed`, which Alembic does not look at
    - so it is not a head, and no deployment's startup check sees it. Here it
    is added to `version_locations` explicitly, which is the only place it is
    ever applied until it is reviewed and moved into `versions/`.
    """
    from pathlib import Path

    from alembic import command
    from writing_coach.persistence.runtime import _runtime_alembic_config

    root = Path(__file__).resolve().parents[1]
    cfg = _runtime_alembic_config()
    cfg.set_main_option('sqlalchemy.url', URL.replace('%', '%%'))
    cfg.set_main_option(
        'version_locations',
        f'{root / "migrations" / "versions"}{os.pathsep}{root / "migrations" / "proposed"}',
    )
    command.upgrade(cfg, 'head')
    engine = create_engine(URL, future=True)
    yield engine
    engine.dispose()


@pytest.fixture
def scope(engine):
    """A fresh account incarnation and stream head per test."""
    now = datetime.now(UTC)
    user_id, incarnation = uuid.uuid4(), uuid.uuid4()
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
            {'id': incarnation, 'user': user_id, 'status': 'active', 'now': now},
        )
        connection.execute(
            text(
                'INSERT INTO account_streams (incarnation_id, next_sequence, updated_at) '
                'VALUES (:id, 1, :now)'
            ),
            {'id': incarnation, 'now': now},
        )
    return Scope(str(user_id), str(incarnation), 'en')


def commit(repo, scope, *, op, expected, work_id, text_value, domain='draft'):
    return repo.commit_mutation(
        scope=scope, domain=domain, operation_id=op,
        digest=semantic_digest('draft.write', {'work': work_id}, text_value),
        expected_version=expected, work_id=work_id, payload={'text': text_value},
    )


def test_two_edits_from_the_same_version_leave_one_conflict_with_both_texts(engine, scope):
    """Matrix: one accepted, other explicit conflict; both texts retained."""
    repo = PostgresWorkRepository(engine)
    work_id = str(uuid.uuid4())
    first = commit(repo, scope, op='op-create', expected=0, work_id=work_id,
                   text_value='The last train had already gone.')
    assert first['status'] == 'committed'

    results, barrier = {}, threading.Barrier(2)

    def edit(name, body):
        barrier.wait()
        results[name] = commit(repo, scope, op=f'op-{name}', expected=1,
                               work_id=work_id, text_value=body)

    threads = [
        threading.Thread(target=edit, args=('a', 'Edited on the phone.')),
        threading.Thread(target=edit, args=('b', 'Edited on the laptop.')),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    statuses = sorted(r['status'] for r in results.values())
    assert statuses == ['committed', 'conflict'], results
    loser = next(r for r in results.values() if r['status'] == 'conflict')
    # The conflict hands back the server's text so the learner can reconcile;
    # the client still holds its own. Nothing is merged and nobody wins.
    assert loser['server_payload']['text'] in (
        'Edited on the phone.', 'Edited on the laptop.',
    )
    assert loser['current_version'] == 2


def test_a_lost_acknowledgment_replays_the_same_result(engine, scope):
    """Matrix: same operation replays same result; no second write."""
    repo = PostgresWorkRepository(engine)
    work_id = str(uuid.uuid4())
    first = commit(repo, scope, op='op-once', expected=0, work_id=work_id,
                   text_value='Written once.')
    assert first['status'] == 'committed'

    # The client never saw the response and retries the same operation.
    again = commit(repo, scope, op='op-once', expected=0, work_id=work_id,
                   text_value='Written once.')
    assert again['status'] == 'replay'
    assert again['version'] == first['version']

    with engine.connect() as connection:
        changes = connection.execute(
            text('SELECT count(*) FROM change_records WHERE incarnation_id = :inc'),
            {'inc': scope.incarnation},
        ).scalar_one()
    assert changes == 1, 'the retry wrote a second change record'


def test_reusing_an_operation_id_with_different_text_is_refused(engine, scope):
    repo = PostgresWorkRepository(engine)
    work_id = str(uuid.uuid4())
    commit(repo, scope, op='op-x', expected=0, work_id=work_id, text_value='One.')
    reused = commit(repo, scope, op='op-x', expected=0, work_id=work_id, text_value='Two.')
    assert reused['status'] == 'rejected'
    assert reused['reason'] == 'operation_conflict'


def test_a_stalled_transaction_holds_the_stream_so_no_sequence_is_skipped(engine, scope):
    """Matrix: transaction 10 stalls while 11 attempts commit."""
    repo = PostgresWorkRepository(engine)
    started, release = threading.Event(), threading.Event()

    def slow_writer():
        with engine.begin() as connection:
            connection.execute(
                text('SELECT next_sequence FROM account_streams '
                     'WHERE incarnation_id = :inc FOR UPDATE'),
                {'inc': scope.incarnation},
            )
            started.set()
            release.wait(timeout=10)
            connection.execute(
                text('UPDATE account_streams SET next_sequence = next_sequence + 1, '
                     'updated_at = :now WHERE incarnation_id = :inc'),
                {'now': datetime.now(UTC), 'inc': scope.incarnation},
            )
            connection.execute(
                text('INSERT INTO change_records (id, incarnation_id, sequence, '
                     'language_code, object_domain, object_id, object_version, '
                     'change_kind, created_at) VALUES (:id, :inc, 1, :lang, '
                     "'draft', :object, 1, 'upsert', :now)"),
                {'id': uuid.uuid4(), 'inc': scope.incarnation, 'lang': scope.language,
                 'object': str(uuid.uuid4()), 'now': datetime.now(UTC)},
            )

    holder = threading.Thread(target=slow_writer)
    holder.start()
    assert started.wait(timeout=10)

    # The second writer must block on the head rather than allocating past it.
    outcome = {}

    def second():
        outcome['result'] = commit(repo, scope, op='op-second', expected=0,
                                   work_id=str(uuid.uuid4()), text_value='Second.')

    runner = threading.Thread(target=second)
    runner.start()
    runner.join(timeout=2)
    assert runner.is_alive(), 'the second writer did not wait for the held stream head'

    release.set()
    holder.join(timeout=10)
    runner.join(timeout=10)
    assert outcome['result']['status'] == 'committed'

    with engine.connect() as connection:
        sequences = [
            row[0] for row in connection.execute(
                text('SELECT sequence FROM change_records WHERE incarnation_id = :inc '
                     'ORDER BY sequence'),
                {'inc': scope.incarnation},
            )
        ]
    assert sequence_is_contiguous(sequences, after=0), sequences


def test_a_snapshot_read_covers_a_concurrent_write_exactly_once(engine, scope):
    """Matrix: snapshot page and concurrent mutation covers exactly once."""
    repo = PostgresWorkRepository(engine)
    for index in range(3):
        commit(repo, scope, op=f'op-seed-{index}', expected=0,
               work_id=str(uuid.uuid4()), text_value=f'Seed {index}.')

    with engine.connect() as connection:
        watermark = connection.execute(
            text('SELECT coalesce(max(sequence), 0) FROM change_records '
                 'WHERE incarnation_id = :inc'),
            {'inc': scope.incarnation},
        ).scalar_one()

    # A write lands after the watermark was taken.
    commit(repo, scope, op='op-late', expected=0, work_id=str(uuid.uuid4()),
           text_value='Arrived after the snapshot.')

    before = repo.changes_after(scope, 0)
    after = repo.changes_after(scope, watermark)
    ids_before = [row['object_id'] for row in before if row['sequence'] <= watermark]
    ids_after = [row['object_id'] for row in after]
    assert len(set(ids_before) & set(ids_after)) == 0, 'a change was covered twice'
    assert len(ids_before) + len(ids_after) == 4, 'a change was missed'


def test_the_change_stream_is_not_filtered_by_language(engine, scope):
    """A language filter must not skip changes in another language."""
    repo = PostgresWorkRepository(engine)
    commit(repo, scope, op='op-en', expected=0, work_id=str(uuid.uuid4()), text_value='English.')
    zh = Scope(scope.account, scope.incarnation, 'zh')
    commit(repo, zh, op='op-zh', expected=0, work_id=str(uuid.uuid4()), text_value='中文。')
    languages = {row['language_code'] for row in repo.changes_after(scope, 0)}
    assert languages == {'en', 'zh'}


def test_a_deleted_account_cannot_be_written_to(engine, scope):
    repo = PostgresWorkRepository(engine)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE account_incarnations SET status = 'deleted', deleted_at = :now "
                 'WHERE id = :inc'),
            {'now': datetime.now(UTC), 'inc': scope.incarnation},
        )
    result = commit(repo, scope, op='op-after-delete', expected=0,
                    work_id=str(uuid.uuid4()), text_value='Too late.')
    assert result['status'] == 'rejected'
    assert result['reason'] == 'account_not_active'


def test_a_recreated_account_cannot_reuse_the_old_incarnations_receipts(engine, scope):
    """Matrix: new incarnation rejects an old command."""
    repo = PostgresWorkRepository(engine)
    work_id = str(uuid.uuid4())
    commit(repo, scope, op='op-old', expected=0, work_id=work_id, text_value='Old life.')

    now = datetime.now(UTC)
    new_incarnation = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE account_incarnations SET status = 'deleted', deleted_at = :now "
                 'WHERE id = :inc'),
            {'now': now, 'inc': scope.incarnation},
        )
        connection.execute(
            text('INSERT INTO account_incarnations (id, user_id, epoch, status, created_at) '
                 "VALUES (:id, :user, 2, 'active', :now)"),
            {'id': new_incarnation, 'user': scope.account, 'now': now},
        )
        connection.execute(
            text('INSERT INTO account_streams (incarnation_id, next_sequence, updated_at) '
                 'VALUES (:id, 1, :now)'),
            {'id': new_incarnation, 'now': now},
        )

    fresh = Scope(scope.account, str(new_incarnation), 'en')
    # The same operation id under the new incarnation is a new command, and the
    # old work is not visible to it.
    assert repo.get_work(fresh, work_id) is None
    result = commit(repo, fresh, op='op-old', expected=0, work_id=str(uuid.uuid4()),
                    text_value='New life.')
    assert result['status'] == 'committed'
    assert result['sequence'] == 1, 'the new incarnation started its own stream'


def test_at_most_one_active_incarnation_per_account(engine, scope):
    now = datetime.now(UTC)
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text('INSERT INTO account_incarnations (id, user_id, epoch, status, created_at) '
                     "VALUES (:id, :user, 2, 'active', :now)"),
                {'id': uuid.uuid4(), 'user': scope.account, 'now': now},
            )


def test_a_turn_cannot_be_attached_across_a_language(engine, scope):
    """Parent isolation: the child joins on the whole scope, not just the id."""
    repo = PostgresWorkRepository(engine)
    work_id = str(uuid.uuid4())
    commit(repo, scope, op='op-conv', expected=0, work_id=work_id,
           text_value='Ordering coffee.', domain='conversation')
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text('INSERT INTO work_turns (id, work_id, incarnation_id, language_code, '
                     'ordinal, author_role, content, created_at) VALUES '
                     "(:id, :work, :inc, 'zh', 1, 'learner', :content, :now)"),
                {'id': uuid.uuid4(), 'work': work_id, 'inc': scope.incarnation,
                 'content': 'wrong language', 'now': datetime.now(UTC)},
            )
