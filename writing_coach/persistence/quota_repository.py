"""Quota buckets and the reserve/settle/release transactional seam.

PROPOSAL, NOT DEPLOYED — the tables this reads and writes are in
`migrations/proposed/20260912_0007`, not `migrations/versions/`. Nothing here
runs against any real database until that migration is reviewed, approved and
moved, mirroring I2 and the I3 subscription-inbox path. No caller is wired to
this either way.

Division of responsibility, matching `commerce_repository.py`: this file
never computes a policy decision itself. `writing_coach.reference_backbone`'s
`reserve_decision()`, `settle_decision()` and `release_decision()` decide;
this file only supplies the atomic locking, idempotency lookups and row
writes those decisions assume a caller already has.

Idempotency shape, deliberately narrow (see the migration's own docstring):
a *rejected* reserve() attempt (denied / exhausted / unknown entitlement)
writes no reservation row at all, so a caller may safely retry the same
operation_id later without ever risking a double admission — nothing was
admitted the first time. Only an *admitted* reservation is durable, exactly
the same asymmetry `commerce_billing_event_receipts` already has for
`'unknown'` versus a terminal outcome.

Incarnation lifecycle: this file does not give `reserve_decision()` its own
notion of a deleted incarnation — that decision already has a clean hook for
it. A deleted incarnation is mapped to `entitlement='denied'` before calling
`reserve_decision()`, reusing its existing vocabulary rather than inventing a
parallel one. `settle()` and `release()` act on a reservation already on file
and do not re-check incarnation status: the admission decision is the one
place a deleted incarnation is turned away, matching "no new-account grant"
for a already-admitted operation would rewrite history, not honor it.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from writing_coach.reference_backbone import Quota, reserve_decision, settle_decision, release_decision


class QuotaOutcome(dict):
    """`status` is one of reserve_decision()/settle_decision()/
    release_decision()'s outcomes, or `unknown_incarnation`/
    `deleted_incarnation_rejected` for an admission this repository will not
    even attempt."""


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


class PostgresQuotaRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

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
                    'SELECT bucket_id, admitted_units, actual_units, state, policy_version, '
                    'outcome_ref FROM commerce_quota_reservations WHERE operation_id = :op'
                ),
                {'op': operation_id},
            ).mappings().first()
        return dict(row) if row else None

    def reserve(
        self, *, incarnation_id: str, meter: str, window: BucketWindow,
        operation_id: str, requested_units: int, entitlement: str = 'allowed',
    ) -> QuotaOutcome:
        """One admission attempt, or one idempotent replay of a prior one.

        Order: lock the incarnation (deleted -> denied, reusing
        reserve_decision()'s existing vocabulary rather than a parallel one)
        -> placeholder-insert and lock the reservation row for this exact
        operation_id, so concurrent retries of the same operation are
        exactly-once even the first time it is ever seen -> if a reservation
        already exists, compare requested_units and return 'duplicate' or
        'payload_conflict' without touching any bucket -> otherwise
        placeholder-insert and lock the bucket row (first-use races the same
        way) -> decide with reserve_decision() -> on 'admit', write the
        reservation and update the bucket in the same transaction; on any
        other verdict, write nothing durable at all.
        """
        now = datetime.now(UTC)
        with self._engine.begin() as connection:
            owner = connection.execute(
                text('SELECT status FROM account_incarnations WHERE id = :inc FOR UPDATE'),
                {'inc': incarnation_id},
            ).mappings().first()
            if owner is None:
                return QuotaOutcome(status='unknown_incarnation')
            if owner['status'] != 'active':
                entitlement = 'denied'

            existing = connection.execute(
                text(
                    'SELECT bucket_id, admitted_units, state FROM commerce_quota_reservations '
                    'WHERE operation_id = :op FOR UPDATE'
                ),
                {'op': operation_id},
            ).mappings().first()
            if existing is not None:
                if existing['admitted_units'] != requested_units:
                    return QuotaOutcome(status='payload_conflict')
                return QuotaOutcome(
                    status='duplicate', bucket_id=str(existing['bucket_id']), state=existing['state']
                )

            # Same "concurrent first use" problem the subscription/receipt
            # tables already solve the same way: FOR UPDATE locks nothing
            # against a row that does not exist yet.
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
                    'id': uuid.uuid4(), 'inc': incarnation_id, 'meter': meter,
                    'window_id': window.window_id, 'start': window.window_start,
                    'end': window.window_end, 'policy': window.policy_version,
                    'limit': window.unit_limit, 'now': now,
                },
            )
            bucket = connection.execute(
                text(
                    'SELECT id, policy_version, unit_limit, consumed, reserved '
                    'FROM commerce_quota_buckets '
                    'WHERE incarnation_id = :inc AND meter = :meter AND window_id = :window_id '
                    'FOR UPDATE'
                ),
                {'inc': incarnation_id, 'meter': meter, 'window_id': window.window_id},
            ).mappings().first()

            verdict = reserve_decision(
                Quota(bucket['unit_limit'], bucket['consumed'], bucket['reserved']),
                requested_units, entitlement=entitlement,
            )
            if verdict != 'admit':
                return QuotaOutcome(status=verdict, bucket_id=str(bucket['id']))

            reservation_id = uuid.uuid4()
            connection.execute(
                text(
                    'INSERT INTO commerce_quota_reservations '
                    '(id, bucket_id, operation_id, admitted_units, state, policy_version, '
                    "created_at, updated_at) VALUES "
                    "(:id, :bucket, :op, :units, 'reserved', :policy, :now, :now)"
                ),
                {
                    'id': reservation_id, 'bucket': bucket['id'], 'op': operation_id,
                    'units': requested_units, 'policy': bucket['policy_version'], 'now': now,
                },
            )
            connection.execute(
                text(
                    'UPDATE commerce_quota_buckets SET reserved = reserved + :units, '
                    'updated_at = :now WHERE id = :bucket'
                ),
                {'units': requested_units, 'now': now, 'bucket': bucket['id']},
            )
            return QuotaOutcome(status='admit', bucket_id=str(bucket['id']), reservation_id=str(reservation_id))

    def settle(self, *, operation_id: str, actual_units: int, outcome_ref: str | None = None) -> QuotaOutcome:
        """Idempotent per settle_decision(). Writes nothing at all unless the
        verdict is 'settle' — a duplicate, conflicting or otherwise invalid
        settle call touches neither the reservation nor its bucket."""
        now = datetime.now(UTC)
        with self._engine.begin() as connection:
            reservation = connection.execute(
                text(
                    'SELECT bucket_id, admitted_units, actual_units, state '
                    'FROM commerce_quota_reservations WHERE operation_id = :op FOR UPDATE'
                ),
                {'op': operation_id},
            ).mappings().first()

            verdict = settle_decision(
                reservation_state=reservation['state'] if reservation else None,
                admitted_units=reservation['admitted_units'] if reservation else None,
                actual_units=actual_units,
                prior_actual_units=reservation['actual_units'] if reservation else None,
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
        verdict is 'release'."""
        now = datetime.now(UTC)
        with self._engine.begin() as connection:
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
