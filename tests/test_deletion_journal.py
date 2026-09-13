"""D-054: a deletion survives a restore; re-registration is a new incarnation.

The hermetic half checks the journal - what it records, what it refuses, and
that merging never drops a deletion. The PostgreSQL half (skipped unless
`ORENA_TEST_POSTGRES_URL` names a throwaway database) plays the restore: an
incarnation deleted after the backup comes back `active`, or - for an account
older than its incarnation rows - does not come back at all while the account
does. Reapplying the journal makes both hold before anything is served, after
which sign-in meets the barrier and re-registration still gets a new
incarnation that the journal does not touch.
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
        'created_at': '2026-09-01T08:00:00+00:00',
        'deleted_at': '2026-09-13T08:00:00+00:00',
    }
    return {**base, **overrides}


def test_a_journal_records_opaque_ids_and_times_in_order_of_the_instant():
    later = record(deleted_at='2026-09-13T15:30:00+07:00')   # 08:30 UTC
    earlier = record(deleted_at='2026-09-13T08:10:00+00:00')
    body = journal([later, earlier])
    assert body['kind'] == JOURNAL_KIND and body['version'] == 2
    assert [row['id'] for row in body['records']] == [earlier['id'], later['id']], 'instants, not spellings'
    assert body['records'][1]['deleted_at'] == '2026-09-13T08:30:00+00:00', 'one offset'
    assert set(body['records'][0]) == {'id', 'user_id', 'epoch', 'created_at', 'deleted_at'}, 'no content'


def test_naive_datetimes_are_read_as_utc():
    body = journal([record(deleted_at=datetime(2026, 9, 13, 8, 0))])
    assert body['records'][0]['deleted_at'].endswith('+00:00')


@pytest.mark.parametrize('bad', [
    {'id': 'not-a-uuid'},
    {'user_id': None},
    {'epoch': 'one'},
    {'epoch': 0},
    {'deleted_at': ''},
    {'deleted_at': 'yesterday'},
    {'created_at': None},
])
def test_a_malformed_record_refuses_the_whole_journal(bad):
    with pytest.raises(JournalInvalid):
        journal([record(), record(**bad)])


def test_the_same_incarnation_twice_is_refused():
    row = record()
    with pytest.raises(JournalInvalid):
        journal([row, dict(row)])


def test_merging_never_drops_a_deletion_and_keeps_the_earliest_instant():
    shared, account = str(uuid.uuid4()), str(uuid.uuid4())
    first = journal([record(id=shared, user_id=account, deleted_at='2026-09-13T10:00:00+00:00'), record()])
    # 09:30 UTC, spelled in another offset: earlier by instant, later by string.
    second = journal([record(id=shared, user_id=account, deleted_at='2026-09-13T16:30:00+07:00'), record()])
    merged = merge(first, second)
    assert len(merged['records']) == 3
    assert next(r for r in merged['records'] if r['id'] == shared)['deleted_at'] == '2026-09-13T09:30:00+00:00'


def test_journals_that_disagree_about_an_incarnation_are_refused():
    shared = str(uuid.uuid4())
    with pytest.raises(JournalInvalid):
        merge(journal([record(id=shared, epoch=1)]), journal([record(id=shared, epoch=2)]))


def test_a_journal_round_trips_and_a_foreign_file_is_refused(tmp_path):
    path = tmp_path / 'deletions.json'
    body = journal([record(), record()])
    write_journal(path, body)
    assert read_journal(path)['records'] == body['records']
    for content in ({'kind': 'something-else'}, {'kind': JOURNAL_KIND, 'version': 1, 'records': []},
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
        ).scalar_one_or_none()


def _forget(engine, incarnation):
    """What a backup from before the account's incarnation rows looks like."""
    from sqlalchemy import text

    with engine.begin() as connection:
        connection.execute(text('DELETE FROM account_streams WHERE incarnation_id = :id'), {'id': incarnation})
        connection.execute(text('DELETE FROM account_incarnations WHERE id = :id'), {'id': incarnation})


@postgres
def test_a_deletion_made_after_the_backup_is_reapplied_before_serving(engine):
    from sqlalchemy import text
    from writing_coach.persistence.deletion_journal import export_deletions, reapply_deletions, verify_suppressed
    from writing_coach.persistence.incarnation_repository import (
        DeletionBarrier, PostgresIncarnationRepository,
    )

    repo = PostgresIncarnationRepository(engine)
    account = _account(engine)
    incarnation = repo.ensure_active(account)
    repo.mark_deleted(incarnation)
    body = export_deletions(engine)
    assert incarnation in {row['id'] for row in body['records']}
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE account_incarnations SET status = 'active', deleted_at = NULL WHERE id = :id"),
            {'id': incarnation},
        )
    assert verify_suppressed(engine, body), 'the check sees the restore is not yet safe'

    summary = reapply_deletions(engine, body)
    assert summary['reapplied'] >= 1
    assert _status(engine, incarnation) == 'deleted'
    assert verify_suppressed(engine, body) == []
    with pytest.raises(DeletionBarrier):
        repo.ensure_active(account)

    fresh = repo.register_new(account)
    assert fresh != incarnation
    again = reapply_deletions(engine, body)
    assert again['reapplied'] == 0 and again['barrier_restored'] == 0
    assert _status(engine, fresh) == 'active'
    assert _status(engine, incarnation) == 'deleted'


@postgres
def test_an_account_restored_without_its_incarnation_gets_its_barrier_back(engine):
    """The reviewer's round-1 P1: `absent` used to lose the barrier, and an
    ordinary sign-in then created a fresh incarnation for a deleted account."""
    from writing_coach.persistence.deletion_journal import export_deletions, reapply_deletions, verify_suppressed
    from writing_coach.persistence.incarnation_repository import (
        DeletionBarrier, PostgresIncarnationRepository,
    )

    repo = PostgresIncarnationRepository(engine)
    account = _account(engine)
    incarnation = repo.ensure_active(account)
    repo.mark_deleted(incarnation)
    body = export_deletions(engine)
    _forget(engine, incarnation)
    assert _status(engine, incarnation) is None
    assert any(account in problem for problem in verify_suppressed(engine, body))

    summary = reapply_deletions(engine, body)
    assert summary['barrier_restored'] >= 1
    assert _status(engine, incarnation) == 'deleted'
    assert verify_suppressed(engine, body) == []
    with pytest.raises(DeletionBarrier):
        repo.ensure_active(account)


@postgres
def test_an_account_the_restore_never_had_is_absent_not_invented(engine):
    from writing_coach.persistence.deletion_journal import reapply_deletions

    ghost = journal([record()])
    assert reapply_deletions(engine, ghost) == {'reapplied': 0, 'already_deleted': 0, 'barrier_restored': 0, 'absent': 1}


@postgres
@pytest.mark.parametrize('disagreement', ['other_account', 'other_epoch', 'epoch_taken'])
def test_an_identity_disagreement_stops_the_whole_reapplication(engine, disagreement):
    from writing_coach.persistence.deletion_journal import reapply_deletions
    from writing_coach.persistence.incarnation_repository import PostgresIncarnationRepository

    repo = PostgresIncarnationRepository(engine)
    first, second = _account(engine), _account(engine)
    kept = repo.ensure_active(first)
    other = repo.ensure_active(second)
    good = record(id=kept, user_id=first, deleted_at=(datetime.now(UTC) - timedelta(minutes=1)).isoformat())
    bad = {
        'other_account': record(id=other, user_id=str(uuid.uuid4())),
        'other_epoch': record(id=other, user_id=second, epoch=2),
        # A different id claiming an epoch the restore already has.
        'epoch_taken': record(user_id=second, epoch=1),
    }[disagreement]
    with pytest.raises(JournalInvalid):
        reapply_deletions(engine, journal([good, bad]))
    assert _status(engine, kept) == 'active', 'one transaction: nothing was half-applied'
    assert _status(engine, other) == 'active'


# --- The gate: nothing may delete or re-register until its preconditions exist

def test_no_runtime_code_deletes_or_re_registers_an_account_yet():
    """D-054's preconditions (continuous out-of-database journaling and the
    owner-table deletion workflow, `ORENA_BACKBONE_INTEGRATION_GATES.md`) are
    not built, so no runtime path may call `mark_deleted` or `register_new`.
    Lifting this is a reviewed change to the gate, not an edit to this list."""
    import ast
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    repository = root / 'writing_coach' / 'persistence' / 'incarnation_repository.py'
    journal_module = root / 'writing_coach' / 'persistence' / 'deletion_journal.py'
    # A raw write of a deleted status, the way round the repository methods.
    raw_delete = re.compile(r"account_incarnations\s+SET\s+status\s*=\s*'deleted'", re.IGNORECASE)
    callers = []
    for path in [root / 'app.py', *(root / 'writing_coach').rglob('*.py'), *(root / 'scripts').rglob('*.py')]:
        if path == repository:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in {'mark_deleted', 'register_new', '_allocate'}):
                callers.append(f'{path.relative_to(root)}:{node.lineno}')
            # Restore suppression re-marks deletions that already happened;
            # that one module may write the status, nothing else may.
            if (path != journal_module and isinstance(node, ast.Constant)
                    and isinstance(node.value, str) and raw_delete.search(node.value)):
                callers.append(f'{path.relative_to(root)}:{node.lineno} (raw SQL)')
    assert callers == []
