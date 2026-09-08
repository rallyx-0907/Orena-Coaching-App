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

from writing_coach.persistence.incarnation_repository import (  # noqa: E402
    DeletionBarrier,
    PostgresIncarnationRepository,
)
from writing_coach.persistence.provenance_repository import (  # noqa: E402
    PostgresProvenanceRepository,
    ProvenanceRejected,
)
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


# ---------------------------------------------------------------------------
# Review finding 3: the persisted incarnation seam.
# ---------------------------------------------------------------------------


def _account(engine):
    """A user row with no incarnation yet."""
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
    return str(user_id)


def test_first_sign_in_bootstraps_one_incarnation_with_its_stream(engine):
    repo = PostgresIncarnationRepository(engine)
    account = _account(engine)
    assert repo.resolve(account) is None, 'resolving must not create one'
    incarnation = repo.ensure_active(account)
    assert repo.resolve(account) == incarnation

    with engine.connect() as connection:
        epoch = connection.execute(
            text('SELECT epoch FROM account_incarnations WHERE id = :id'),
            {'id': incarnation},
        ).scalar_one()
        head = connection.execute(
            text('SELECT next_sequence FROM account_streams WHERE incarnation_id = :id'),
            {'id': incarnation},
        ).scalar_one()
    assert epoch == 1
    assert head == 1, 'an incarnation exists with its stream head, not without it'


def test_concurrent_first_use_produces_one_incarnation_not_two(engine):
    repo = PostgresIncarnationRepository(engine)
    account = _account(engine)
    results, barrier = {}, threading.Barrier(4)

    def sign_in(name):
        barrier.wait()
        results[name] = repo.ensure_active(account)

    threads = [threading.Thread(target=sign_in, args=(n,)) for n in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(set(results.values())) == 1, results
    with engine.connect() as connection:
        count = connection.execute(
            text('SELECT count(*) FROM account_incarnations WHERE user_id = :a'),
            {'a': account},
        ).scalar_one()
    assert count == 1


def test_signing_in_after_deletion_is_refused_rather_than_recreated(engine):
    """The barrier. An ordinary auth upsert must not resurrect an account."""
    repo = PostgresIncarnationRepository(engine)
    account = _account(engine)
    first = repo.ensure_active(account)
    repo.mark_deleted(first)

    assert repo.resolve(account) is None
    with pytest.raises(DeletionBarrier):
        repo.ensure_active(account)

    with engine.connect() as connection:
        count = connection.execute(
            text('SELECT count(*) FROM account_incarnations WHERE user_id = :a'),
            {'a': account},
        ).scalar_one()
    assert count == 1, 'the refused sign-in created an incarnation anyway'


def test_explicit_re_registration_allocates_the_next_epoch(engine):
    repo = PostgresIncarnationRepository(engine)
    account = _account(engine)
    first = repo.ensure_active(account)
    repo.mark_deleted(first)

    second = repo.register_new(account)
    assert second != first
    with engine.connect() as connection:
        epochs = [
            row[0] for row in connection.execute(
                text('SELECT epoch FROM account_incarnations WHERE user_id = :a '
                     'ORDER BY epoch'),
                {'a': account},
            )
        ]
    assert epochs == [1, 2]
    # And the new one is what an ordinary sign-in now resolves to.
    assert repo.ensure_active(account) == second


def test_re_registration_does_not_duplicate_an_active_incarnation(engine):
    repo = PostgresIncarnationRepository(engine)
    account = _account(engine)
    first = repo.ensure_active(account)
    # An account that is not deleted has nothing to re-register; the active
    # incarnation is returned rather than a second one being created.
    assert repo.register_new(account) == first


# ---------------------------------------------------------------------------
# Review finding 4: provenance occurrences and parent scope.
# ---------------------------------------------------------------------------


def _saved_word(engine, account, language, word):
    word_id = uuid.uuid4()
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            text(
                'INSERT INTO saved_words (id, user_id, language_code, word, '
                'normalized_word, added_at, updated_at) VALUES '
                '(:id, :user, :lang, :word, :norm, :now, :now)'
            ),
            {'id': word_id, 'user': account, 'lang': language, 'word': word,
             'norm': word.casefold(), 'now': now},
        )
    return str(word_id)


def test_the_same_word_in_one_source_with_different_focus_is_two_occurrences(engine, scope):
    """The shape the first proposal could not represent."""
    repo = PostgresProvenanceRepository(engine)
    word = _saved_word(engine, scope.account, scope.language, 'gave way to')
    source = {'kind': 'story', 'id': 'last-train', 'revision': 'r3'}

    first = repo.attach_occurrence(
        scope=scope, occurrence_id=str(uuid.uuid4()), operation_id='op-a',
        saved_word_id=word, reason='from_reading', source=source,
        focus='the last shops gave way to fields',
    )
    second = repo.attach_occurrence(
        scope=scope, occurrence_id=str(uuid.uuid4()), operation_id='op-b',
        saved_word_id=word, reason='from_reading', source=source,
        focus='the light gave way to dusk',
    )
    assert first['result_ref'] != second['result_ref']
    assert len(repo.occurrences_for(scope, word)) == 2


def test_an_unchecked_origin_is_unknown_and_not_available(engine, scope):
    repo = PostgresProvenanceRepository(engine)
    word = _saved_word(engine, scope.account, scope.language, 'quiet')
    repo.attach_occurrence(
        scope=scope, occurrence_id=str(uuid.uuid4()), operation_id='op-q',
        saved_word_id=word, reason='looked_up',
    )
    assert repo.occurrences_for(scope, word)[0]['availability'] == 'unknown'


def test_source_revision_is_retained_where_known(engine, scope):
    repo = PostgresProvenanceRepository(engine)
    word = _saved_word(engine, scope.account, scope.language, 'platform-rev')
    repo.attach_occurrence(
        scope=scope, occurrence_id=str(uuid.uuid4()), operation_id='op-r',
        saved_word_id=word, reason='from_reading',
        source={'kind': 'story', 'id': 'last-train', 'revision': 'r7'},
    )
    assert repo.occurrences_for(scope, word)[0]['source_revision'] == 'r7'


def test_an_occurrence_carries_its_own_version(engine, scope):
    repo = PostgresProvenanceRepository(engine)
    word = _saved_word(engine, scope.account, scope.language, 'carriage-v')
    repo.attach_occurrence(
        scope=scope, occurrence_id=str(uuid.uuid4()), operation_id='op-v',
        saved_word_id=word, reason='looked_up',
    )
    assert repo.occurrences_for(scope, word)[0]['version'] == 1


def test_another_accounts_saved_word_is_refused(engine, scope):
    """Parent scope, checked in the transaction because no FK can check it."""
    repo = PostgresProvenanceRepository(engine)
    stranger = _account(engine)
    theirs = _saved_word(engine, stranger, 'en', 'theirs')
    result = repo.attach_occurrence(
        scope=scope, occurrence_id=str(uuid.uuid4()), operation_id='op-x',
        saved_word_id=theirs, reason='looked_up',
    )
    assert result['status'] == 'rejected'
    assert result['reason'] == 'cross_account_saved_word'
    with engine.connect() as connection:
        written = connection.execute(
            text('SELECT count(*) FROM language_provenance WHERE saved_word_id = :w'),
            {'w': theirs},
        ).scalar_one()
    assert written == 0


def test_the_same_accounts_word_in_another_language_is_refused(engine, scope):
    repo = PostgresProvenanceRepository(engine)
    chinese_word = _saved_word(engine, scope.account, 'zh', 'quiet-zh')
    result = repo.attach_occurrence(
        scope=scope, occurrence_id=str(uuid.uuid4()), operation_id='op-l',
        saved_word_id=chinese_word, reason='looked_up',
    )
    assert result['status'] == 'rejected'
    assert result['reason'] == 'cross_language_saved_word'


def test_an_incomplete_source_reference_is_refused(engine, scope):
    repo = PostgresProvenanceRepository(engine)
    word = _saved_word(engine, scope.account, scope.language, 'fragment')
    for source in ({'kind': 'story'}, {'id': 'last-train'}):
        with pytest.raises(ProvenanceRejected) as caught:
            repo.attach_occurrence(
                scope=scope, occurrence_id=str(uuid.uuid4()), operation_id='op-s',
                saved_word_id=word, reason='looked_up', source=source,
            )
        assert caught.exception.reason == 'incomplete_source_ref'


def test_a_receipt_is_compared_against_persisted_facts_only(engine, scope):
    """Review findings 1 and 2, in the database rather than in the docstring."""
    repo = PostgresWorkRepository(engine)
    work_id = str(uuid.uuid4())
    first = commit(repo, scope, op='op-persisted', expected=0, work_id=work_id,
                   text_value='Once.')
    assert first['status'] == 'committed'

    with engine.connect() as connection:
        row = connection.execute(
            text('SELECT language_code, domain, resource_id, expected_version '
                 'FROM mutation_receipts WHERE incarnation_id = :inc '
                 "AND operation_id = 'op-persisted'"),
            {'inc': scope.incarnation},
        ).mappings().one()
    assert row['expected_version'] == 0, 'the issued version was not persisted'
    assert row['resource_id'] == work_id
    assert row['language_code'] == scope.language
    assert row['domain'] == 'draft'


def test_an_unregistered_work_kind_is_refused_before_anything_is_written(engine, scope):
    """Finding 9: strings in the column, strict validation in the application."""
    from writing_coach.work_contract import UnknownRegistryValue

    repo = PostgresWorkRepository(engine)
    with pytest.raises(UnknownRegistryValue):
        repo.commit_mutation(
            scope=scope, domain='draft', operation_id='op-bad-kind',
            digest='d', expected_version=0, work_id=str(uuid.uuid4()),
            kind='screenplay', payload={},
        )
    with pytest.raises(UnknownRegistryValue):
        repo.commit_mutation(
            scope=scope, domain='billing', operation_id='op-bad-domain',
            digest='d', expected_version=0, work_id=str(uuid.uuid4()), payload={},
        )


# ---------------------------------------------------------------------------
# Re-review corrections.
# ---------------------------------------------------------------------------


def attach(repo, scope, *, op, occurrence, word, focus='', source=None, reason='from_reading'):
    return repo.attach_occurrence(
        scope=scope, occurrence_id=occurrence, operation_id=op,
        saved_word_id=word, reason=reason, source=source, focus=focus,
    )


def test_two_operations_with_identical_content_are_two_occurrences(engine, scope):
    """Correction 1: occurrence identity is independent of semantic equality.

    The same word, the same source, the same focus, twice - two events, and
    nothing in the schema may collapse them into one.
    """
    repo = PostgresProvenanceRepository(engine)
    word = _saved_word(engine, scope.account, scope.language, 'gave way')
    source = {'kind': 'story', 'id': 'last-train'}

    first = attach(repo, scope, op='op-one', occurrence=str(uuid.uuid4()),
                   word=word, focus='same line', source=source)
    second = attach(repo, scope, op='op-two', occurrence=str(uuid.uuid4()),
                    word=word, focus='same line', source=source)
    assert first['status'] == 'committed'
    assert second['status'] == 'committed'
    assert first['result_ref'] != second['result_ref']
    assert len(repo.occurrences_for(scope, word)) == 2


def test_retrying_one_attachment_replays_its_occurrence(engine, scope):
    """Correction 2: the retry is deduplicated by the operation, not the content."""
    repo = PostgresProvenanceRepository(engine)
    word = _saved_word(engine, scope.account, scope.language, 'platform')
    occurrence = str(uuid.uuid4())

    first = attach(repo, scope, op='op-attach', occurrence=occurrence, word=word,
                   focus='on the platform')
    again = attach(repo, scope, op='op-attach', occurrence=occurrence, word=word,
                   focus='on the platform')
    assert first['status'] == 'committed'
    assert again['status'] == 'replay'
    assert again['result_ref'] == first['result_ref']
    assert len(repo.occurrences_for(scope, word)) == 1, 'the retry created a second one'


def test_attaching_provenance_writes_a_receipt_and_a_change_record(engine, scope):
    """Correction 2: it is a mutation, not a write beside the contract."""
    repo = PostgresProvenanceRepository(engine)
    word = _saved_word(engine, scope.account, scope.language, 'carriage')
    attach(repo, scope, op='op-stream', occurrence=str(uuid.uuid4()), word=word)

    with engine.connect() as connection:
        receipt = connection.execute(
            text("SELECT domain, expected_version FROM mutation_receipts "
                 "WHERE incarnation_id = :inc AND operation_id = 'op-stream'"),
            {'inc': scope.incarnation},
        ).mappings().one()
        change = connection.execute(
            text("SELECT object_domain, change_kind FROM change_records "
                 "WHERE incarnation_id = :inc AND object_domain = 'provenance'"),
            {'inc': scope.incarnation},
        ).mappings().one()
    assert receipt['domain'] == 'provenance'
    assert receipt['expected_version'] == 0
    assert change['change_kind'] == 'upsert'


def test_provenance_shares_the_account_sequence_with_work(engine, scope):
    """One stream per account, whatever domain is writing to it."""
    work_repo = PostgresWorkRepository(engine)
    prov_repo = PostgresProvenanceRepository(engine)
    word = _saved_word(engine, scope.account, scope.language, 'shared')

    commit(work_repo, scope, op='op-w1', expected=0, work_id=str(uuid.uuid4()),
           text_value='A draft.')
    attach(prov_repo, scope, op='op-p1', occurrence=str(uuid.uuid4()), word=word)
    commit(work_repo, scope, op='op-w2', expected=0, work_id=str(uuid.uuid4()),
           text_value='Another draft.')

    with engine.connect() as connection:
        sequences = [
            row[0] for row in connection.execute(
                text('SELECT sequence FROM change_records WHERE incarnation_id = :inc '
                     'ORDER BY sequence'),
                {'inc': scope.incarnation},
            )
        ]
    assert sequence_is_contiguous(sequences, after=0), sequences
    assert len(sequences) == 3


def test_an_account_that_does_not_own_the_incarnation_is_refused(engine, scope):
    """Correction 3: the account is re-resolved from the incarnation row.

    A request that presents someone else's incarnation alongside its own
    account id must not have its own claim believed.
    """
    repo = PostgresWorkRepository(engine)
    stranger = _account(engine)
    forged = Scope(stranger, scope.incarnation, scope.language)
    result = commit(repo, forged, op='op-forged', expected=0,
                    work_id=str(uuid.uuid4()), text_value='Not mine.')
    assert result['status'] == 'rejected'
    assert result['reason'] == 'account_incarnation_mismatch'

    with engine.connect() as connection:
        written = connection.execute(
            text('SELECT count(*) FROM works WHERE incarnation_id = :inc'),
            {'inc': scope.incarnation},
        ).scalar_one()
    assert written == 0


def test_the_replayed_receipt_identity_does_not_come_from_the_retrying_request(engine, scope):
    """Correction 3, the other half.

    A retry presenting a mismatched account is refused before any receipt is
    consulted, so a forged account id cannot become the account half of the
    identity a replay is compared against.
    """
    repo = PostgresWorkRepository(engine)
    work_id = str(uuid.uuid4())
    commit(repo, scope, op='op-legit', expected=0, work_id=work_id, text_value='Mine.')

    stranger = _account(engine)
    forged = Scope(stranger, scope.incarnation, scope.language)
    result = commit(repo, forged, op='op-legit', expected=0, work_id=work_id,
                    text_value='Mine.')
    assert result['status'] == 'rejected'
    assert result['reason'] == 'account_incarnation_mismatch'
    assert result.get('result_ref') is None, 'a forged account was replayed a result'


def test_the_same_operation_with_a_changed_expected_version_conflicts(engine, scope):
    """Correction 4: same operation id, same payload, different expected version.

    The payload digest matches, so a comparison that ignored the expected
    version would call this a retry and replay - handing back a success for a
    command that was never issued. It is an operation conflict.
    """
    repo = PostgresWorkRepository(engine)
    work_id = str(uuid.uuid4())
    first = commit(repo, scope, op='op-version', expected=0, work_id=work_id,
                   text_value='One.')
    assert first['status'] == 'committed'

    same_payload_new_version = commit(repo, scope, op='op-version', expected=1,
                                      work_id=work_id, text_value='One.')
    assert same_payload_new_version['status'] == 'rejected'
    assert same_payload_new_version['reason'] == 'operation_conflict'

    with engine.connect() as connection:
        version = connection.execute(
            text('SELECT version FROM works WHERE id = :id'), {'id': work_id},
        ).scalar_one()
    assert version == 1, 'the conflicting operation wrote anyway'


def test_a_work_source_revision_without_a_source_is_refused(engine, scope):
    """Correction 5, in the repository."""
    repo = PostgresWorkRepository(engine)
    with pytest.raises(ValueError):
        repo.commit_mutation(
            scope=scope, domain='draft', operation_id='op-rev', digest='d',
            expected_version=0, work_id=str(uuid.uuid4()), payload={},
            source={'revision': 'r3'},
        )


def test_the_database_also_refuses_a_work_revision_without_a_source(engine, scope):
    """Correction 5, in the constraint - so nothing else can write it either."""
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    'INSERT INTO works (id, incarnation_id, language_code, kind, '
                    'source_kind, source_id, source_revision, version, lifecycle, '
                    "payload, updated_sequence, created_at, updated_at) VALUES "
                    "(:id, :inc, :lang, 'draft', '', '', 'r3', 1, 'active', "
                    "CAST('{}' AS JSON), 1, :now, :now)"
                ),
                {'id': uuid.uuid4(), 'inc': scope.incarnation, 'lang': scope.language,
                 'now': datetime.now(UTC)},
            )


def test_the_work_owner_refuses_provenance_as_a_work_domain(engine, scope):
    """Correction 6: provenance mutates, but it is not a kind of work."""
    from writing_coach.work_contract import UnknownRegistryValue

    repo = PostgresWorkRepository(engine)
    with pytest.raises(UnknownRegistryValue) as caught:
        repo.commit_mutation(
            scope=scope, domain='provenance', operation_id='op-wrong-owner',
            digest='d', expected_version=0, work_id=str(uuid.uuid4()), payload={},
        )
    assert caught.exception.registry == 'works.domain'

    with engine.connect() as connection:
        written = connection.execute(
            text("SELECT count(*) FROM mutation_receipts WHERE incarnation_id = :inc "
                 "AND operation_id = 'op-wrong-owner'"),
            {'inc': scope.incarnation},
        ).scalar_one()
    assert written == 0, 'a refused domain still opened a transaction'


def test_provenance_remains_a_valid_global_mutation_domain(engine, scope):
    """The narrower work registry does not remove it from the global one."""
    repo = PostgresProvenanceRepository(engine)
    word = _saved_word(engine, scope.account, scope.language, 'still-valid')
    result = attach(repo, scope, op='op-global', occurrence=str(uuid.uuid4()), word=word)
    assert result['status'] == 'committed'
