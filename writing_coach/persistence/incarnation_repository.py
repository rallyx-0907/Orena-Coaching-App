"""Resolving an account's incarnation. The one place that reads the row.

PROPOSAL — the table this reads is in `migrations/proposed/20260908_0005`,
awaiting re-review and schema authorization. No caller is wired to it.

I1 built scope from an incarnation derived in the pure decision layer, out of
the account's id and creation time. Review finding 3: that made a module with
no database the authority on an identity fact it cannot see, and it could not
express the deletion barrier at all, because a barrier is a stored row.

The boundary is now explicit. This adapter resolves, bootstraps and
re-registers; `account_profile.scope_of` receives the resolved value and
decides nothing about it. The barrier lives here because only here can it be
durable.

Four situations, and they are not the same situation:

  * an account signing in for the first time - bootstrap epoch 1;
  * two requests doing that at once - one wins, the other reads the winner;
  * an account whose incarnation was deleted - **refused**, because an ordinary
    auth upsert must not silently recreate an active account;
  * a deliberate re-registration - a new epoch, and everything scoped to the
    old one stops matching.
"""
from __future__ import annotations

from datetime import UTC, datetime
import uuid

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError


class DeletionBarrier(RuntimeError):
    """This account was deleted. Reactivation needs an explicit re-registration.

    Raised instead of quietly creating a new active incarnation, which is what
    an ordinary sign-in would otherwise do and what the barrier exists to stop.
    """

    def __init__(self, account: str):
        super().__init__(f'account {account} is deleted; re-registration is explicit')
        self.account = account


class PostgresIncarnationRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def resolve(self, account: str) -> str | None:
        """The active incarnation, or None. Never creates one."""
        with self._engine.connect() as connection:
            found = connection.execute(
                text(
                    "SELECT id FROM account_incarnations "
                    "WHERE user_id = :account AND status = 'active'"
                ),
                {'account': account},
            ).scalar_one_or_none()
        return str(found) if found else None

    def ensure_active(self, account: str) -> str:
        """Resolve, or bootstrap a first incarnation. Refuses after deletion.

        This is the sign-in path, so it is the one that must not resurrect. A
        first-ever account gets epoch 1; an account that has been deleted gets
        `DeletionBarrier` and nothing else.
        """
        existing = self.resolve(account)
        if existing:
            return existing
        try:
            return self._allocate(account, first_only=True)
        except IntegrityError:
            # Concurrent first use: the partial unique index on the active
            # incarnation let exactly one of us through. Read the winner rather
            # than retrying the insert, so both requests end up in one epoch.
            winner = self.resolve(account)
            if not winner:
                raise
            return winner

    def register_new(self, account: str) -> str:
        """Deliberate re-registration after deletion. Allocates the next epoch."""
        return self._allocate(account, first_only=False)

    def mark_deleted(self, incarnation: str) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE account_incarnations SET status = 'deleted', deleted_at = :now "
                    "WHERE id = :id AND status = 'active'"
                ),
                {'now': datetime.now(UTC), 'id': incarnation},
            )

    def _allocate(self, account: str, *, first_only: bool) -> str:
        now = datetime.now(UTC)
        with self._engine.begin() as connection:
            # Epoch allocation is serialized on the account row. Reading
            # max(epoch) without holding it lets two re-registrations pick the
            # same number and race on the unique constraint; the lock makes the
            # answer stable for the length of the transaction.
            locked = connection.execute(
                text('SELECT id FROM users WHERE id = :account FOR UPDATE'),
                {'account': account},
            ).scalar_one_or_none()
            if locked is None:
                raise ValueError('No such account')

            rows = connection.execute(
                text(
                    'SELECT epoch, status FROM account_incarnations '
                    'WHERE user_id = :account ORDER BY epoch'
                ),
                {'account': account},
            ).mappings().all()
            for row in rows:
                if row['status'] == 'active':
                    return str(
                        connection.execute(
                            text(
                                "SELECT id FROM account_incarnations WHERE user_id = :account "
                                "AND status = 'active'"
                            ),
                            {'account': account},
                        ).scalar_one()
                    )
            if rows and first_only:
                # Every incarnation this account has is deleted, and this is
                # the sign-in path. The barrier holds.
                raise DeletionBarrier(account)

            incarnation = uuid.uuid4()
            connection.execute(
                text(
                    'INSERT INTO account_incarnations '
                    '(id, user_id, epoch, status, created_at) '
                    "VALUES (:id, :account, :epoch, 'active', :now)"
                ),
                {
                    'id': incarnation,
                    'account': account,
                    'epoch': max((row['epoch'] for row in rows), default=0) + 1,
                    'now': now,
                },
            )
            # The stream head is part of an incarnation existing, not something
            # a later writer creates on demand: a mutation locks it first, and
            # a missing head would be an account that cannot be written to.
            connection.execute(
                text(
                    'INSERT INTO account_streams (incarnation_id, next_sequence, updated_at) '
                    'VALUES (:id, 1, :now)'
                ),
                {'id': incarnation, 'now': now},
            )
            return str(incarnation)
