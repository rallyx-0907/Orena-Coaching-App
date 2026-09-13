"""Deletion survives a restore (D-054).

Deleting an account is permanent: a deleted incarnation is never restored to
the learner and never reactivated, and re-registration is a new incarnation
(`incarnation_repository.register_new`). A database restore is the one path
that could quietly undo that, because a backup taken before a deletion still
holds the incarnation as `active` - or, for an account that existed before its
incarnation rows did, holds the account and no incarnation at all, which the
sign-in path would read as a first sign-in. The account architecture's rule is
that a restore reapplies every deletion recorded after the backup before
anything is served; this module is how.

It works in two halves, and the halves live in different places on purpose:

  * `export_deletions` reads every deleted incarnation from a database that
    knows about them into a **journal** that lives outside any database, so the
    restore cannot take it back;
  * `reapply_deletions` makes each journal record hold in the restored
    database, in one transaction:
      - an incarnation the restore has as `active` is marked deleted again
        (`reapplied`);
      - one the restore already has as deleted is left alone
        (`already_deleted`);
      - one the restore lacks, while the account itself is there, has its
        barrier row put back with the same id, epoch and times
        (`barrier_restored`) - without it, an ordinary sign-in would create a
        fresh incarnation for a deleted account;
      - one whose account the restore does not have at all is `absent`:
        nothing of that account exists there to serve. (Signing in with the
        same external identity would then create a new, empty account - no
        barrier to meet, but nothing of the deleted one either, so D-054's
        "nothing is restored" still holds.)

Nothing here can set an incarnation active. A journal that disagrees with the
restore about identity - the same id under another account or epoch, or an
epoch already taken by a different id - stops the whole reapplication and
changes nothing. `verify_suppressed` answers, without writing, whether every
journal record holds.

Two preconditions are not met by this module and gate enabling deletion or
re-registration at all (`ORENA_BACKBONE_INTEGRATION_GATES.md`): the journal is
a point-in-time export, so deletions must also be appended to an
out-of-database journal as they happen; and an account's rows in the owner
tables (essays, saved words, ...) are keyed by account rather than incarnation,
so the account-deletion workflow that removes them - not built, and needing
its own independent review - must exist and be replayed after a restore too.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import uuid

JOURNAL_KIND = 'orena.deletion_journal'
# 2: records carry `created_at` (needed to put a barrier row back). A version-1
# journal is refused by name rather than as "malformed".
JOURNAL_VERSION = 2


class JournalInvalid(ValueError):
    """A journal that cannot be trusted is refused whole, never half-applied."""


def _utc(value: Any, field: str, ident: str) -> str:
    if isinstance(value, datetime):
        moment = value
    else:
        text = str(value or '').strip()
        if not text:
            raise JournalInvalid(f'deletion record {ident} has no {field}')
        try:
            moment = datetime.fromisoformat(text.replace('Z', '+00:00'))
        except ValueError:
            raise JournalInvalid(f'deletion record {ident} has an unreadable {field}') from None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    # One offset, so ordering and merging compare instants, not spellings.
    return moment.astimezone(UTC).isoformat()


def _record(row: Mapping[str, Any]) -> dict[str, Any]:
    try:
        ident = str(uuid.UUID(str(row['id'])))
        account = str(uuid.UUID(str(row['user_id'])))
        epoch = int(row['epoch'])
    except (KeyError, TypeError, ValueError) as error:
        raise JournalInvalid(f'malformed deletion record: {error}') from None
    if epoch < 1:
        raise JournalInvalid(f'deletion record {ident} has epoch {epoch}')
    return {
        'id': ident,
        'user_id': account,
        'epoch': epoch,
        'created_at': _utc(row.get('created_at'), 'created_at', ident),
        'deleted_at': _utc(row.get('deleted_at'), 'deleted_at', ident),
    }


def journal(records: Iterable[Mapping[str, Any]], *, exported_at: datetime | None = None) -> dict[str, Any]:
    rows = sorted((_record(row) for row in records), key=lambda r: (r['deleted_at'], r['id']))
    if len({row['id'] for row in rows}) != len(rows):
        raise JournalInvalid('a deletion record appears twice')
    return {
        'kind': JOURNAL_KIND,
        'version': JOURNAL_VERSION,
        'exported_at': (exported_at or datetime.now(UTC)).astimezone(UTC).isoformat(),
        'records': rows,
    }


def read_journal(path: Path) -> dict[str, Any]:
    try:
        body = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise JournalInvalid(f'cannot read journal {path}: {error}') from None
    if not isinstance(body, dict) or body.get('kind') != JOURNAL_KIND:
        raise JournalInvalid(f'{path} is not a deletion journal')
    if body.get('version') != JOURNAL_VERSION:
        raise JournalInvalid(f'{path} is journal version {body.get("version")!r}, expected {JOURNAL_VERSION}')
    records = body.get('records')
    if not isinstance(records, list):
        raise JournalInvalid(f'{path} has no records list')
    try:
        exported_at = datetime.fromisoformat(str(body.get('exported_at')).replace('Z', '+00:00'))
    except ValueError:
        raise JournalInvalid(f'{path} has an unreadable exported_at') from None
    return journal(records, exported_at=exported_at)


def write_journal(path: Path, body: Mapping[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(body, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def merge(*bodies: Mapping[str, Any]) -> dict[str, Any]:
    """Several journals (say, the replaced database's and an earlier copy) as one.

    The same incarnation in two journals is one deletion, and must name the
    same account and epoch; the earliest recorded deletion time is kept.
    Merging never drops a record.
    """
    seen: dict[str, dict[str, Any]] = {}
    for body in bodies:
        for row in journal(body['records'])['records']:
            prior = seen.get(row['id'])
            if prior is None:
                seen[row['id']] = dict(row)
                continue
            if (prior['user_id'], prior['epoch']) != (row['user_id'], row['epoch']):
                raise JournalInvalid(f'journals disagree about incarnation {row["id"]}')
            if datetime.fromisoformat(row['deleted_at']) < datetime.fromisoformat(prior['deleted_at']):
                seen[row['id']] = dict(row)
    return journal(seen.values())


def export_deletions(engine) -> dict[str, Any]:
    """Every deleted incarnation this database knows about."""
    from sqlalchemy import text

    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT id, user_id, epoch, created_at, deleted_at FROM account_incarnations "
                "WHERE status = 'deleted' ORDER BY deleted_at, id"
            )
        ).mappings().all()
    return journal(rows)


def _inspect(connection, row: Mapping[str, Any], *, lock: bool) -> str:
    """Where one journal record stands in this database, without changing it."""
    from sqlalchemy import text

    suffix = ' FOR UPDATE' if lock else ''
    found = connection.execute(
        text(f'SELECT status, user_id, epoch FROM account_incarnations WHERE id = :id{suffix}'),
        {'id': row['id']},
    ).mappings().one_or_none()
    if found is not None:
        if (str(found['user_id']), int(found['epoch'])) != (row['user_id'], row['epoch']):
            # The same id under another account or epoch: the journal and this
            # database disagree about identity. Stop, rather than delete
            # somebody else's incarnation.
            raise JournalInvalid(f'incarnation {row["id"]} has another account or epoch in this database')
        return 'already_deleted' if found['status'] == 'deleted' else 'active'
    account = connection.execute(
        # The account row is the lock every epoch allocation takes, so a
        # restored barrier and a concurrent first sign-in cannot interleave.
        text(f'SELECT id FROM users WHERE id = :account{suffix}'),
        {'account': row['user_id']},
    ).scalar_one_or_none()
    if account is None:
        return 'absent'
    taken = connection.execute(
        text('SELECT id FROM account_incarnations WHERE user_id = :account AND epoch = :epoch'),
        {'account': row['user_id'], 'epoch': row['epoch']},
    ).scalar_one_or_none()
    if taken is not None:
        raise JournalInvalid(
            f'epoch {row["epoch"]} of account {row["user_id"]} belongs to another incarnation in this database'
        )
    return 'missing_barrier'


def reapply_deletions(engine, body: Mapping[str, Any]) -> dict[str, int]:
    """Make every journal record hold in a restored database, all or nothing.

    Returns counts: `reapplied`, `already_deleted`, `barrier_restored`,
    `absent`.
    """
    from sqlalchemy import text

    records = journal(body['records'])['records']
    summary = {'reapplied': 0, 'already_deleted': 0, 'barrier_restored': 0, 'absent': 0}
    with engine.begin() as connection:
        for row in records:
            where = _inspect(connection, row, lock=True)
            if where == 'active':
                connection.execute(
                    text(
                        "UPDATE account_incarnations SET status = 'deleted', deleted_at = :deleted_at "
                        "WHERE id = :id"
                    ),
                    {'id': row['id'], 'deleted_at': datetime.fromisoformat(row['deleted_at'])},
                )
                summary['reapplied'] += 1
            elif where == 'missing_barrier':
                connection.execute(
                    text(
                        'INSERT INTO account_incarnations (id, user_id, epoch, status, created_at, deleted_at) '
                        "VALUES (:id, :account, :epoch, 'deleted', :created_at, :deleted_at)"
                    ),
                    {
                        'id': row['id'], 'account': row['user_id'], 'epoch': row['epoch'],
                        'created_at': datetime.fromisoformat(row['created_at']),
                        'deleted_at': datetime.fromisoformat(row['deleted_at']),
                    },
                )
                summary['barrier_restored'] += 1
            else:
                summary[where] += 1
    return summary


def verify_suppressed(engine, body: Mapping[str, Any]) -> list[str]:
    """Every record that does not yet hold in this database, as sentences.

    Empty means the restore may serve as far as deletions are concerned. Reads
    only; an identity disagreement is reported rather than raised.
    """
    problems: list[str] = []
    with engine.connect() as connection:
        for row in journal(body['records'])['records']:
            try:
                where = _inspect(connection, row, lock=False)
            except JournalInvalid as error:
                problems.append(str(error))
                continue
            if where == 'active':
                problems.append(f'incarnation {row["id"]} is active here but was deleted at {row["deleted_at"]}')
            elif where == 'missing_barrier':
                problems.append(f'account {row["user_id"]} is here without the barrier for incarnation {row["id"]}')
    return problems
