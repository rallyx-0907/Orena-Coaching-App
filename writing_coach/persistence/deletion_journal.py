"""Deletion survives a restore (D-054).

Deleting an account is permanent: a deleted incarnation is never restored to
the learner and never reactivated, and re-registration is a new incarnation
(`incarnation_repository.register_new`). A database restore is the one path
that could quietly undo that, because a backup taken before a deletion still
holds the incarnation as `active`. The account architecture's rule is that a
restore reapplies every deletion recorded after the backup before anything is
served; this module is how.

It works in two halves, and the halves live in different places on purpose:

  * `export_deletions` reads every deleted incarnation from a database that
    knows about them - normally the database being replaced, at the moment of
    the incident - into a **journal** that lives outside any database, so the
    restore cannot take it back;
  * `reapply_deletions` marks each journal record deleted again in the
    restored database, in one transaction, and reports what it did.

Only the barrier row is reapplied. An incarnation the journal names but the
restored database never had was created after the backup, so nothing of it
exists there to serve; it is reported as `absent`, not invented. A deletion is
never reversed here: a record already deleted in the restore stays deleted,
and nothing in this module can set an incarnation active.

What this does not do, named rather than implied: removing or quarantining an
account's rows in the owner tables (essays, saved words, ...), which are keyed
by account rather than incarnation. That is the account-deletion workflow -
not built, and a destructive lifecycle change that needs its own independent
review - and when it exists it must also be replayed after a restore.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import uuid

JOURNAL_KIND = 'orena.deletion_journal'
JOURNAL_VERSION = 1


class JournalInvalid(ValueError):
    """A journal that cannot be trusted is refused whole, never half-applied."""


def _record(row: Mapping[str, Any]) -> dict[str, Any]:
    try:
        ident = str(uuid.UUID(str(row['id'])))
        account = str(uuid.UUID(str(row['user_id'])))
        epoch = int(row['epoch'])
    except (KeyError, TypeError, ValueError) as error:
        raise JournalInvalid(f'malformed deletion record: {error}') from None
    deleted_at = row.get('deleted_at')
    if isinstance(deleted_at, datetime):
        deleted_at = (deleted_at if deleted_at.tzinfo else deleted_at.replace(tzinfo=UTC)).isoformat()
    if not deleted_at:
        raise JournalInvalid(f'deletion record {ident} has no deleted_at')
    try:
        datetime.fromisoformat(str(deleted_at))
    except ValueError:
        raise JournalInvalid(f'deletion record {ident} has an unreadable deleted_at') from None
    return {'id': ident, 'user_id': account, 'epoch': epoch, 'deleted_at': str(deleted_at)}


def journal(records: Iterable[Mapping[str, Any]], *, exported_at: datetime | None = None) -> dict[str, Any]:
    rows = sorted((_record(row) for row in records), key=lambda r: (r['deleted_at'], r['id']))
    if len({row['id'] for row in rows}) != len(rows):
        raise JournalInvalid('a deletion record appears twice')
    return {
        'kind': JOURNAL_KIND,
        'version': JOURNAL_VERSION,
        'exported_at': (exported_at or datetime.now(UTC)).isoformat(),
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
        exported_at = datetime.fromisoformat(str(body.get('exported_at')))
    except ValueError:
        raise JournalInvalid(f'{path} has an unreadable exported_at') from None
    return journal(records, exported_at=exported_at)


def write_journal(path: Path, body: Mapping[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(body, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def merge(*bodies: Mapping[str, Any]) -> dict[str, Any]:
    """Several journals (say, the replaced database's and an earlier copy) as one.

    The same incarnation in two journals is one deletion; the earliest recorded
    time is kept. Merging never drops a record.
    """
    seen: dict[str, dict[str, Any]] = {}
    for body in bodies:
        for row in body['records']:
            prior = seen.get(row['id'])
            if prior is None or row['deleted_at'] < prior['deleted_at']:
                seen[row['id']] = dict(row)
    return journal(seen.values())


def export_deletions(engine) -> dict[str, Any]:
    """Every deleted incarnation this database knows about."""
    from sqlalchemy import text

    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT id, user_id, epoch, deleted_at FROM account_incarnations "
                "WHERE status = 'deleted' ORDER BY deleted_at, id"
            )
        ).mappings().all()
    return journal(rows)


def reapply_deletions(engine, body: Mapping[str, Any]) -> dict[str, int]:
    """Mark every journal record deleted again in a restored database.

    One transaction: either every record is reapplied or none is, so a
    restore is never served with some deletions back and some not. Returns
    counts - `reapplied` (was active in the restore), `already_deleted`,
    `absent` (created after the backup, so nothing of it is there).
    """
    from sqlalchemy import text

    records = journal(body['records'])['records']
    summary = {'reapplied': 0, 'already_deleted': 0, 'absent': 0}
    with engine.begin() as connection:
        for row in records:
            found = connection.execute(
                text('SELECT status, user_id FROM account_incarnations WHERE id = :id FOR UPDATE'),
                {'id': row['id']},
            ).mappings().one_or_none()
            if found is None:
                summary['absent'] += 1
                continue
            if str(found['user_id']) != row['user_id']:
                # The same id belonging to another account means the journal
                # and this database disagree about identity. Stop, rather than
                # delete somebody else's incarnation.
                raise JournalInvalid(f'incarnation {row["id"]} belongs to another account in this database')
            if found['status'] == 'deleted':
                summary['already_deleted'] += 1
                continue
            connection.execute(
                text(
                    "UPDATE account_incarnations SET status = 'deleted', deleted_at = :deleted_at "
                    "WHERE id = :id"
                ),
                {'id': row['id'], 'deleted_at': datetime.fromisoformat(row['deleted_at'])},
            )
            summary['reapplied'] += 1
    return summary
