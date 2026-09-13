"""D-054: a deletion survives a restore; re-registration is a new incarnation.

The hermetic half checks the journal itself - what it records, what it refuses,
and that merging never drops a deletion. The PostgreSQL half (skipped unless
`ORENA_TEST_POSTGRES_URL` names a throwaway database) plays the restore: an
incarnation deleted after the backup comes back `active` in the restored
database, and reapplying the journal makes it deleted again before anything is
served - after which sign-in still meets the barrier and re-registration still
gets a new incarnation that the journal does not touch.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from writing_coach.persistence.deletion_journal import (
    JOURNAL_KIND,
    JournalInvalid,
    journal,
    merge,
    read_journal,
    write_journal,
)


def record(**overrides):
    base = {
        'id': str(uuid.uuid4()),
        'user_id': str(uuid.uuid4()),
        'epoch': 1,
        'deleted_at': '2026-09-13T08:00:00+00:00',
    }
    return {**base, **overrides}


def test_a_journal_records_opaque_ids_and_times_in_a_stable_order():
    later, earlier = record(deleted_at='2026-09-13T09:00:00+00:00'), record()
    body = journal([later, earlier])
    assert body['kind'] == JOURNAL_KIND and body['version'] == 1
    assert [row['id'] for row in body['records']] == [earlier['id'], later['id']]
    assert set(body['records'][0]) == {'id', 'user_id', 'epoch', 'deleted_at'}, 'no content, only identity and time'


def test_naive_datetimes_are_read_as_utc():
    body = journal([record(deleted_at=datetime(2026, 9, 13, 8, 0))])
    assert body['records'][0]['deleted_at'].endswith('+00:00')


@pytest.mark.parametrize('bad', [
    {'id': 'not-a-uuid'},
    {'user_id': None},
    {'epoch': 'one'},
    {'deleted_at': ''},
    {'deleted_at': 'yesterday'},
])
def test_a_malformed_record_refuses_the_whole_journal(bad):
    with pytest.raises(JournalInvalid):
        journal([record(), record(**bad)])


def test_the_same_incarnation_twice_is_refused():
    row = record()
    with pytest.raises(JournalInvalid):
        journal([row, dict(row)])


def test_merging_never_drops_a_deletion_and_keeps_the_earliest_time(tmp_path):
    shared = str(uuid.uuid4())
    account = str(uuid.uuid4())
    first = journal([record(id=shared, user_id=account, deleted_at='2026-09-13T10:00:00+00:00'), record()])
    second = journal([record(id=shared, user_id=account, deleted_at='2026-09-13T09:00:00+00:00'), record()])
    merged = merge(first, second)
    assert len(merged['records']) == 3
    assert next(r for r in merged['records'] if r['id'] == shared)['deleted_at'] == '2026-09-13T09:00:00+00:00'


def test_a_journal_round_trips_and_a_foreign_file_is_refused(tmp_path):
    path = tmp_path / 'deletions.json'
    body = journal([record(), record()])
    write_journal(path, body)
    assert read_journal(path)['records'] == body['records']
    for content in ({'kind': 'something-else'}, {'kind': JOURNAL_KIND, 'version': 2, 'records': []},
                    {'kind': JOURNAL_KIND, 'version': 1, 'records': 'x', 'exported_at': body['exported_at']}):
        path.write_text(json.dumps(content), encoding='utf-8')
        with pytest.raises(JournalInvalid):
            read_journal(path)
    path.write_text('{not json', encoding='utf-8')
    with pytest.raises(JournalInvalid):
        read_journal(path)


def test_the_backup_tool_refuses_a_suppress_without_a_journal(capsys):
    from scripts.runtime_backup import main

    assert main(['suppress', '--url', 'postgresql+psycopg://u:p@localhost/x', '--into', 'restored']) == 1
    assert 'needs at least one --deletions' in capsys.readouterr().err
    assert main(['deletions', '--url', 'postgresql+psycopg://u:p@localhost/x']) == 1


def test_a_journal_that_cannot_be_read_changes_nothing(tmp_path, capsys):
    from scripts.runtime_backup import main

    bad = tmp_path / 'bad.json'
    bad.write_text('{"kind": "nope"}', encoding='utf-8')
    assert main(['suppress', '--url', 'postgresql+psycopg://u:p@localhost/x', '--into', 'restored',
                 '--deletions', str(bad)]) == 1
    assert 'refusing' in capsys.readouterr().err


# --- PostgreSQL: the restore itself ------------------------------------------

URL = os.getenv('ORENA_TEST_POSTGRES_URL', '')
postgres = pytest.mark.skipif(not URL, reason='ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run')


@pytest.fixture(scope='module')
def engine():
    if not URL:
        pytest.skip('ORENA_TEST_POSTGRES_URL is not set')
    from alembic import command
    from sqlalchemy import create_engine
    from writing_coach.persistence.runtime import _runtime_alembic_config

    cfg = _runtime_alembic_config()
    cfg.set_main_option('sqlalchemy.url', URL.replace('%', '%%'))
    command.upgrade(cfg, 'head')
    engine = create_engine(URL, future=True)
    yield engine
    engine.dispose()


def _account(engine):
    from sqlalchemy import text

    account = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                'INSERT INTO users (id, user_key, email, name, picture, role, created_at) '
                'VALUES (:id, :key, :email, :name, :pic, :role, :now)'
            ),
            {'id': account, 'key': f'deletion-journal-{account}', 'email': '', 'name': '',
             'pic': '', 'role': 'user', 'now': datetime.now(UTC)},
        )
    return str(account)


def _status(engine, incarnation):
    from sqlalchemy import text

    with engine.connect() as connection:
        return connection.execute(
            text('SELECT status FROM account_incarnations WHERE id = :id'), {'id': incarnation}
        ).scalar_one()


@postgres
def test_a_deletion_made_after_the_backup_is_reapplied_before_serving(engine):
    from sqlalchemy import text
    from writing_coach.persistence.deletion_journal import export_deletions, reapply_deletions
    from writing_coach.persistence.incarnation_repository import (
        DeletionBarrier, PostgresIncarnationRepository,
    )

    repo = PostgresIncarnationRepository(engine)
    account = _account(engine)
    incarnation = repo.ensure_active(account)
    repo.mark_deleted(incarnation)
    # The journal is exported from the database being replaced, after the
    # deletion; the restore comes from a backup taken before it.
    body = export_deletions(engine)
    assert incarnation in {row['id'] for row in body['records']}
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE account_incarnations SET status = 'active', deleted_at = NULL WHERE id = :id"),
            {'id': incarnation},
        )
    assert _status(engine, incarnation) == 'active', 'the restored database has it back'

    summary = reapply_deletions(engine, body)
    assert summary['reapplied'] >= 1
    assert _status(engine, incarnation) == 'deleted'
    with pytest.raises(DeletionBarrier):
        repo.ensure_active(account)

    # Re-registration is a new incarnation, and reapplying the same journal
    # again neither touches it nor reverses anything.
    fresh = repo.register_new(account)
    assert fresh != incarnation
    again = reapply_deletions(engine, body)
    assert again['reapplied'] == 0
    assert _status(engine, fresh) == 'active'
    assert _status(engine, incarnation) == 'deleted'


@postgres
def test_an_incarnation_the_restore_never_had_is_absent_not_invented(engine):
    from writing_coach.persistence.deletion_journal import reapply_deletions

    account = _account(engine)
    ghost = journal([record(user_id=account)])
    assert reapply_deletions(engine, ghost) == {'reapplied': 0, 'already_deleted': 0, 'absent': 1}


@postgres
def test_an_identity_disagreement_stops_the_whole_reapplication(engine):
    from writing_coach.persistence.deletion_journal import reapply_deletions
    from writing_coach.persistence.incarnation_repository import PostgresIncarnationRepository

    repo = PostgresIncarnationRepository(engine)
    first, second = _account(engine), _account(engine)
    kept = repo.ensure_active(first)
    other = repo.ensure_active(second)
    body = journal([
        record(id=kept, user_id=first, deleted_at=(datetime.now(UTC) - timedelta(minutes=1)).isoformat()),
        record(id=other, user_id=str(uuid.uuid4())),
    ])
    with pytest.raises(JournalInvalid):
        reapply_deletions(engine, body)
    assert _status(engine, kept) == 'active', 'one transaction: nothing was half-applied'
    assert _status(engine, other) == 'active'
