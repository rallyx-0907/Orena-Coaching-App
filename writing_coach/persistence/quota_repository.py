"""Quota buckets and the reserve/dispatch/settle/release transactional seam.

DEPLOYED, INACTIVE — the tables this reads and writes are in
`migrations/versions/20260912_0007`, approved by delegated review and applied
to the sandbox runtime. No caller is wired to it; enforcement stays off.

Division of responsibility, matching `commerce_repository.py`: this file
never computes a policy decision itself. `writing_coach.reference_backbone`'s
`reserve_decision()`, `dispatch_decision()`, `settle_decision()` and
`release_decision()` decide; this file supplies the locking, idempotency
lookups and row writes those decisions assume a caller already has.

Idempotency shape, deliberately narrow (see the migration's own docstring):
a *rejected* reserve() attempt (denied / exhausted / unknown entitlement /
closed window) writes no reservation row at all, so a caller may safely retry
the same operation_id later without ever risking a double admission — nothing
was admitted the first time. Only an *admitted* reservation is durable, and a
replay of it is recognised by its whole identity: the same operation for the
same incarnation, meter, window and units is the original admission again
(same reservation id); anything else under that operation id is a
`payload_conflict` that names nothing of the other reservation.

Exactly once, and how: operation ids are globally unique, and the recorded
reservation is looked for again *after* the bucket lock is held, before
deciding. Two concurrent uses of one operation on one bucket serialise on that
bucket, so the second finds the first's committed reservation and replays it
- it never decides against a bucket its twin just filled (review round 2:
`admit` + `exhausted` on a one-unit bucket). Across two buckets (another
meter, window or incarnation) the reservation insert is
`ON CONFLICT (operation_id) DO NOTHING`, so the loser replays or conflicts and
its bucket is never touched.

Lock order is the same everywhere, so nothing here can deadlock with itself:
incarnation (`FOR SHARE`) -> bucket -> reservation. `settle()` and `release()`
read the reservation's bucket id unlocked (it never changes), lock the bucket,
then the reservation; `dispatch()` locks the incarnation, then the
reservation, and touches no bucket. The incarnation is held
`FOR SHARE` for the whole admission: enough to make `mark_deleted()`'s `UPDATE`
wait (so an admission and a deletion cannot interleave), without serialising
unrelated reservations of the same learner.

Incarnation lifecycle: a deleted incarnation is `denied` with
`reason='incarnation_deleted'`, reusing reserve_decision()'s vocabulary, and
nothing at all is written for it - not even a bucket. `dispatch()` is turned
away the same way (a deleted account starts no new provider work; its caller
releases instead). `settle()` and `release()` act on a reservation already on
file and do not re-check the incarnation: honouring an already-admitted
operation's accounting is not a new grant.

Windows: server time decides. A reserve outside the bucket's `[start, end)` -
the stored bucket's once it exists, the caller's for its first use - is
`window_closed`. Settlement is against the original window even after it has
ended (§4), so settle does not check it.
"""
from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from writing_coach.reference_backbone import (
    Quota,
    dispatch_decision,
    release_decision,
    reserve_decision,
    settle_decision,
)


class QuotaOutcome(dict):
    """`status` is one decision's verdict. reserve(): `admit`, `exhausted`,
    `denied` (with `reason='incarnation_deleted'` for a deleted incarnation),
    `unknown`, `window_closed`, `duplicate` (the original admission, with its
    `reservation_id`), `payload_conflict` or `unknown_incarnation`.
    dispatch()/settle()/release(): their decision's verdicts, plus `denied`
    for dispatching a deleted incarnation's work."""


@dataclass(frozen=True)
class BucketWindow:
    """Identity and fixed policy of a quota bucket, supplied by the caller
    only for the case this is the first reserve() ever seen for this
    (incarnation, meter, window_id) - an existing bucket's own stored values
    are always authoritative afterward, never overwritten by a later call's
    inputs. See ORENA_COMMERCE_ARCHITECTURE.md §3: "An upgrade cannot reset
    the existing usage window" - a bucket's policy is fixed for its own
    window's lifetime once created.
    """

    window_id: str
    window_start: datetime
    window_end: datetime
    policy_version: str
    unit_limit: int | None


def _open(start: datetime, end: datetime, now: datetime) -> bool:
    return start <= now < end


def _same_incarnation(a: Any, b: Any) -> bool:
    try:
        return uuid.UUID(str(a)) == uuid.UUID(str(b))
    except ValueError:
        return False


class PostgresQuotaRepository:
    def __init__(self, engine: Engine, *, clock: Callable[[], datetime] | None = None) -> None:
        self._engine = engine
        # Server time decides windows; a controlled clock is for the
        # period-boundary proofs only.
        self._clock = clock or (lambda: datetime.now(UTC))

    def get_bucket(self, incarnation_id: str, meter: str, window_id: str) -> dict[str, Any] | None:
        with self._engine.connect() as connection:
            row = connection.execute(
                text(
                    'SELECT id, window_start, window_end, policy_version, unit_limit, '
                    'consumed, reserved FROM commerce_quota_buckets '
                    'WHERE incarnation_id = :inc AND meter = :meter AND window_id = :window'
                ),
                {'inc': incarnation_id, 'meter': meter, 'window': window_id},
            ).mappings().first()
        return dict(row) if row else None

    def get_reservation(self, operation_id: str) -> dict[str, Any] | None:
        with self._engine.connect() as connection:
            row = connection.execute(
                text(
                    'SELECT id, bucket_id, admitted_units, actual_units, state, policy_version, '
                    'dispatch_ref, outcome_ref FROM commerce_quota_reservations WHERE operation_id = :op'
                ),
                {'op': operation_id},
            ).mappings().first()
        return dict(row) if row else None

    @staticmethod
    def _recorded(connection, operation_id: str) -> dict[str, Any] | None:
        row = connection.execute(
            text(
                'SELECT r.id, r.bucket_id, r.admitted_units, r.state, '
                'b.incarnation_id, b.meter, b.window_id '
                'FROM commerce_quota_reservations r '
                'JOIN commerce_quota_buckets b ON b.id = r.bucket_id '
                'WHERE r.operation_id = :op'
            ),
            {'op': operation_id},
        ).mappings().first()
        return dict(row) if row else None

    @staticmethod
    def _lock_bucket_of(connection, operation_id: str) -> bool:
        """Bucket before reservation, the order reserve() takes them in.

        False when the operation has no reservation at this moment. The caller
        then answers `unknown_operation` without reading the reservation
        again: one committed in between would otherwise be locked and changed
        without its bucket held (review round 2 stress).
        """
        bucket_id = connection.execute(
            text('SELECT bucket_id FROM commerce_quota_reservations WHERE operation_id = :op'),
            {'op': operation_id},
        ).scalar_one_or_none()
        if bucket_id is None:
            return False
        connection.execute(
            text('SELECT id FROM commerce_quota_buckets WHERE id = :id FOR UPDATE'),
            {'id': bucket_id},
        )
        return True

    @staticmethod
    def _replay(recorded: dict[str, Any], *, incarnation_id: str, meter: str,
                window_id: str, units: int) -> QuotaOutcome:
        same = (
            _same_incarnation(recorded['incarnation_id'], incarnation_id)
            and recorded['meter'] == meter
            and recorded['window_id'] == window_id
            and recorded['admitted_units'] == units
        )
        if not same:
            # Nothing of the other reservation - not its bucket, not its
            # incarnation - is returned.
            return QuotaOutcome(status='payload_conflict')
        return QuotaOutcome(
            status='duplicate', reservation_id=str(recorded['id']),
            bucket_id=str(recorded['bucket_id']), admitted_units=recorded['admitted_units'],
            state=recorded['state'],
        )

    def reserve(
        self, *, incarnation_id: str, meter: str, window: BucketWindow,
        operation_id: str, requested_units: int, entitlement: str = 'allowed',
    ) -> QuotaOutcome:
        """One admission attempt, or one idempotent replay of a prior one.

        Order: hold the incarnation `FOR SHARE` (deleted -> denied, nothing
        written) -> a recorded reservation for this operation is replayed or
        refused by its whole identity -> entitlement other than allowed ->
        its verdict, nothing written -> lock the bucket, creating it first if
        this is its first use and its window is open -> window closed by
        server time -> `window_closed` -> reserve_decision() -> on 'admit',
        insert the reservation `ON CONFLICT (operation_id) DO NOTHING`; if a
        concurrent first use won, replay against it and leave the bucket
        alone; otherwise add the units to the bucket, same transaction.
        """
        # Validates the units (and entitlement vocabulary) before any SQL;
        # 'admit' here only means "entitlement allows asking".
        asked = reserve_decision(Quota(None, 0, 0), requested_units, entitlement=entitlement)
        now = self._clock()
        with self._engine.begin() as connection:
            owner = connection.execute(
                text('SELECT status FROM account_incarnations WHERE id = :inc FOR SHARE'),
                {'inc': incarnation_id},
            ).mappings().first()
            if owner is None:
                return QuotaOutcome(status='unknown_incarnation')
            if owner['status'] != 'active':
                return QuotaOutcome(status='denied', reason='incarnation_deleted')

            identity = {'incarnation_id': incarnation_id, 'meter': meter,
                        'window_id': window.window_id, 'units': requested_units}
            recorded = self._recorded(connection, operation_id)
            if recorded is not None:
                return self._replay(recorded, **identity)
            if asked != 'admit':
                return QuotaOutcome(status=asked)

            select_bucket = text(
                'SELECT id, window_start, window_end, policy_version, unit_limit, consumed, reserved '
                'FROM commerce_quota_buckets '
                'WHERE incarnation_id = :inc AND meter = :meter AND window_id = :window_id '
                'FOR UPDATE'
            )
            key = {'inc': incarnation_id, 'meter': meter, 'window_id': window.window_id}
            bucket = connection.execute(select_bucket, key).mappings().first()
            if bucket is None:
                if not _open(window.window_start, window.window_end, now):
                    return QuotaOutcome(status='window_closed')
                # FOR UPDATE locks nothing against a row that does not exist
                # yet, so a first use inserts first and then locks.
                connection.execute(
                    text(
                        'INSERT INTO commerce_quota_buckets '
                        '(id, incarnation_id, meter, window_id, window_start, window_end, '
                        'policy_version, unit_limit, consumed, reserved, created_at, updated_at) '
                        'VALUES (:id, :inc, :meter, :window_id, :start, :end, :policy, :limit, '
                        '0, 0, :now, :now) '
                        'ON CONFLICT (incarnation_id, meter, window_id) DO NOTHING'
                    ),
                    {
                        **key, 'id': uuid.uuid4(), 'start': window.window_start,
                        'end': window.window_end, 'policy': window.policy_version,
                        'limit': window.unit_limit, 'now': now,
                    },
                )
                bucket = connection.execute(select_bucket, key).mappings().first()
            if not _open(bucket['window_start'], bucket['window_end'], now):
                return QuotaOutcome(status='window_closed')
            # Again, under the bucket lock: a twin of this operation on this
            # bucket has committed by now, and replaying it is the only
            # truthful answer.
            recorded = self._recorded(connection, operation_id)
            if recorded is not None:
                return self._replay(recorded, **identity)

            verdict = reserve_decision(
                Quota(bucket['unit_limit'], bucket['consumed'], bucket['reserved']),
                requested_units, entitlement=entitlement,
            )
            if verdict != 'admit':
                return QuotaOutcome(status=verdict, bucket_id=str(bucket['id']))

            reservation_id = connection.execute(
                text(
                    'INSERT INTO commerce_quota_reservations '
                    '(id, bucket_id, operation_id, admitted_units, state, policy_version, '
                    'created_at, updated_at) VALUES '
                    "(:id, :bucket, :op, :units, 'reserved', :policy, :now, :now) "
                    'ON CONFLICT (operation_id) DO NOTHING RETURNING id'
                ),
                {
                    'id': uuid.uuid4(), 'bucket': bucket['id'], 'op': operation_id,
                    'units': requested_units, 'policy': bucket['policy_version'], 'now': now,
                },
            ).scalar_one_or_none()
            if reservation_id is None:
                # A concurrent first use of this operation committed first.
                return self._replay(self._recorded(connection, operation_id), **identity)
            connection.execute(
                text(
                    'UPDATE commerce_quota_buckets SET reserved = reserved + :units, '
                    'updated_at = :now WHERE id = :bucket'
                ),
                {'units': requested_units, 'now': now, 'bucket': bucket['id']},
            )
            return QuotaOutcome(
                status='admit', reservation_id=str(reservation_id), bucket_id=str(bucket['id']),
                admitted_units=requested_units, state='reserved',
            )

    def dispatch(self, *, operation_id: str, dispatch_ref: str | None = None) -> QuotaOutcome:
        """The reservation's work has been handed to a provider: from now on
        it can only be settled, never released. Writes nothing unless the
        verdict is 'dispatch'; a deleted incarnation's work is not dispatched."""
        now = self._clock()
        with self._engine.begin() as connection:
            # Incarnation first, then the reservation - the global order. Taking
            # the reservation first and the incarnation second deadlocks behind
            # a queued mark_deleted() (review round 2 stress).
            owner = connection.execute(
                text(
                    'SELECT b.incarnation_id FROM commerce_quota_reservations r '
                    'JOIN commerce_quota_buckets b ON b.id = r.bucket_id '
                    'WHERE r.operation_id = :op'
                ),
                {'op': operation_id},
            ).scalar_one_or_none()
            if owner is None:
                # No reservation at this moment - and not one to lock later
                # without its incarnation held first.
                return QuotaOutcome(status='unknown_operation')
            incarnation_status = connection.execute(
                text('SELECT status FROM account_incarnations WHERE id = :inc FOR SHARE'),
                {'inc': owner},
            ).scalar_one()
            reservation = connection.execute(
                text(
                    'SELECT state, dispatch_ref FROM commerce_quota_reservations '
                    'WHERE operation_id = :op FOR UPDATE'
                ),
                {'op': operation_id},
            ).mappings().first()
            verdict = dispatch_decision(
                reservation_state=reservation['state'] if reservation else None,
                dispatch_ref=dispatch_ref,
                prior_dispatch_ref=reservation['dispatch_ref'] if reservation else None,
            )
            if verdict == 'dispatch' and incarnation_status != 'active':
                return QuotaOutcome(status='denied', reason='incarnation_deleted')
            if verdict != 'dispatch':
                return QuotaOutcome(status=verdict)
            connection.execute(
                text(
                    "UPDATE commerce_quota_reservations SET state = 'dispatched', "
                    'dispatch_ref = :ref, updated_at = :now WHERE operation_id = :op'
                ),
                {'ref': dispatch_ref, 'now': now, 'op': operation_id},
            )
            return QuotaOutcome(status='dispatch')

    def settle(self, *, operation_id: str, actual_units: int, outcome_ref: str | None = None) -> QuotaOutcome:
        """Idempotent per settle_decision(). Writes nothing at all unless the
        verdict is 'settle' — a duplicate, conflicting or otherwise invalid
        settle call touches neither the reservation nor its bucket."""
        now = self._clock()
        with self._engine.begin() as connection:
            if not self._lock_bucket_of(connection, operation_id):
                return QuotaOutcome(status='unknown_operation')
            reservation = connection.execute(
                text(
                    'SELECT bucket_id, admitted_units, actual_units, state, outcome_ref '
                    'FROM commerce_quota_reservations WHERE operation_id = :op FOR UPDATE'
                ),
                {'op': operation_id},
            ).mappings().first()

            verdict = settle_decision(
                reservation_state=reservation['state'] if reservation else None,
                admitted_units=reservation['admitted_units'] if reservation else None,
                actual_units=actual_units,
                prior_actual_units=reservation['actual_units'] if reservation else None,
                outcome_ref=outcome_ref,
                prior_outcome_ref=reservation['outcome_ref'] if reservation else None,
            )
            if verdict != 'settle':
                return QuotaOutcome(status=verdict)

            connection.execute(
                text(
                    'UPDATE commerce_quota_reservations SET state = \'settled\', '
                    'actual_units = :actual, outcome_ref = :ref, updated_at = :now '
                    'WHERE operation_id = :op'
                ),
                {'actual': actual_units, 'ref': outcome_ref, 'now': now, 'op': operation_id},
            )
            connection.execute(
                text(
                    'UPDATE commerce_quota_buckets SET '
                    'reserved = reserved - :admitted, consumed = consumed + :actual, '
                    'updated_at = :now WHERE id = :bucket'
                ),
                {
                    'admitted': reservation['admitted_units'], 'actual': actual_units,
                    'now': now, 'bucket': reservation['bucket_id'],
                },
            )
            return QuotaOutcome(status='settle')

    def release(self, *, operation_id: str) -> QuotaOutcome:
        """Idempotent per release_decision(). Writes nothing unless the
        verdict is 'release' — dispatched work keeps its reservation."""
        now = self._clock()
        with self._engine.begin() as connection:
            if not self._lock_bucket_of(connection, operation_id):
                return QuotaOutcome(status='unknown_operation')
            reservation = connection.execute(
                text(
                    'SELECT bucket_id, admitted_units, state '
                    'FROM commerce_quota_reservations WHERE operation_id = :op FOR UPDATE'
                ),
                {'op': operation_id},
            ).mappings().first()

            verdict = release_decision(reservation_state=reservation['state'] if reservation else None)
            if verdict != 'release':
                return QuotaOutcome(status=verdict)

            connection.execute(
                text(
                    'UPDATE commerce_quota_reservations SET state = \'released\', '
                    'updated_at = :now WHERE operation_id = :op'
                ),
                {'now': now, 'op': operation_id},
            )
            connection.execute(
                text(
                    'UPDATE commerce_quota_buckets SET reserved = reserved - :admitted, '
                    'updated_at = :now WHERE id = :bucket'
                ),
                {'admitted': reservation['admitted_units'], 'now': now, 'bucket': reservation['bucket_id']},
            )
            return QuotaOutcome(status='release')
