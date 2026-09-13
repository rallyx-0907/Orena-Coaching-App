"""Subscription state and the provider-event inbox.

PROPOSAL, NOT DEPLOYED — the tables this reads and writes are in
`migrations/proposed/20260911_0006`, not `migrations/versions/`. Nothing here
runs against any real database until that migration is reviewed, approved and
moved, mirroring I2's path. No caller is wired to this either way.

Revised against two rounds of review (docs/project/I3_SCHEMA_REVIEW_REQUEST.md):

1. A receipt's mere existence does not mean 'duplicate'. Only a *terminal*
   receipt (`applied` / `ignored`) does; a `received` one — written for
   `'unknown'` — does not, so the same (provider, external_event_id) can be
   re-decided once authoritative provider state is available.
   `record_event()` is that re-decision path too.
2. The incarnation row is held `FOR SHARE` for the whole event, so it
   serializes against `incarnation_repository.mark_deleted()`'s `UPDATE`
   rather than racing it, without serializing unrelated readers.
3. A deleted incarnation still gets a durable, terminal receipt (`ignored`,
   reason `deleted_incarnation_rejected`) and no subscription row of any kind.
4. **Whose event it is comes from stored identity, never the caller.**
   The provider-subscription mapping names the owner of every event about
   that subscription; failing that, the receipt's stored incarnation does. A
   call for another incarnation - a new incarnation after delete and
   re-register, or a misrouted webhook - is `foreign_incarnation`. It can
   neither take the event over nor close it: a receipt that belongs to
   someone else is not written at all, and a receipt this call created (or
   an earlier misrouted call left non-final) is handed to the incarnation the
   mapping names and left `received`, so the owner's own delivery still
   decides it (review round 2, P2-1). That hand-over of a non-final receipt
   is the only update its incarnation column ever gets.
5. **Versions are per provider subscription.** Each provider subscription has
   its own row (`commerce_provider_subscriptions`) with its last applied
   version and its owning incarnation. An event is compared only against its
   own subscription's version; whether it then changes the incarnation's
   *current* subscription is `current_subscription_decision()`'s question (a
   resubscription replaces an ended subscription; a late event from an older
   one never overwrites a live one; two live ones are 'unknown').
6. **A mapping conflict is decided, not raised.** A provider subscription
   already mapped to another incarnation makes the event
   `foreign_incarnation` before anything else is written - no integrity
   error, no lost receipt, no retry loop. A mapping is committed only by an
   applied event; an undecided one leaves none behind (round 2, P3).
7. An applied event never erases known state: a missing customer id keeps
   the stored one, and an event that names no provider subscription is
   'unknown' (it cannot be versioned or attributed), never applied.
8. A reused event id whose content digest differs from the stored one is
   `payload_conflict` and changes nothing.
9. Whether an incarnation waits on reconciliation is not stored: it is
   whether any of its receipts is still `received`, read when asked, so it
   can neither stick after the event is decided nor clear while another still
   waits (round 2, P2-2). `paid_through` is kept when an event of the same
   subscription does not carry one.

Still out of scope, named: resolving *which* incarnation a raw webhook
belongs to. The caller passes an incarnation; the receipt and the
provider-subscription mapping, once stored, overrule it.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from writing_coach.reference_backbone import (
    ProviderEvent,
    current_subscription_decision,
    subscription_event_decision,
)

_TERMINAL_RECEIPT_STATES = ('applied', 'ignored')

# Every verdict's receipt state. 'unknown' stays 'received' (non-terminal);
# 'duplicate' and 'payload_conflict' write nothing at all.
# 'foreign_incarnation' is absent on purpose: another incarnation's event is
# never closed by this call.
_RECEIPT_STATE = {
    'apply': 'applied',
    'unknown': 'received',
    'stale': 'ignored',
    'deleted_incarnation_rejected': 'ignored',
}


@dataclass(frozen=True)
class SubscriptionUpdate:
    """What an adapter normalized from one provider event, if it applies.

    The repository never inspects a provider payload itself; normalizing one
    into this shape is the caller's job, same division as
    `writing_coach.product.commerce`'s read side never touching a repository.
    `provider_state` is the provider's own state name, kept for audit.
    """

    state: str
    plan_id: str
    external_customer_id: str | None
    external_subscription_id: str | None
    paid_through: datetime | None
    cancel_at_period_end: bool
    provider_state: str | None = None


class CommerceOutcome(dict):
    """`status` is one of subscription_event_decision()'s outcomes ('apply'
    also says whether the current subscription was `replaced` or `kept`), or
    `rejected` for an incarnation this repository does not know at all."""


def _same(a: Any, b: Any) -> bool:
    try:
        return uuid.UUID(str(a)) == uuid.UUID(str(b))
    except ValueError:
        return False


class PostgresCommerceRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get_subscription(self, incarnation_id: str) -> dict[str, Any] | None:
        with self._engine.connect() as connection:
            row = connection.execute(
                text(
                    'SELECT provider, external_customer_id, external_subscription_id, '
                    'plan_id, state, object_version, paid_through, cancel_at_period_end, '
                    'provider_state, '
                    "CASE WHEN EXISTS (SELECT 1 FROM commerce_billing_event_receipts r "
                    "WHERE r.incarnation_id = s.incarnation_id AND r.processing_state = 'received') "
                    "THEN 'pending' ELSE 'current' END AS reconciliation_state "
                    'FROM commerce_subscriptions s WHERE incarnation_id = :inc'
                ),
                {'inc': incarnation_id},
            ).mappings().first()
        return dict(row) if row else None

    def reconciliation_state(self, incarnation_id: str) -> str:
        """`pending` while any event of this incarnation is undecided, else
        `current` - also for an incarnation with no subscription row yet."""
        with self._engine.connect() as connection:
            waiting = connection.execute(
                text(
                    'SELECT EXISTS (SELECT 1 FROM commerce_billing_event_receipts '
                    "WHERE incarnation_id = :inc AND processing_state = 'received')"
                ),
                {'inc': incarnation_id},
            ).scalar_one()
        return 'pending' if waiting else 'current'

    def get_provider_subscription(self, provider: str, external_subscription_id: str) -> dict[str, Any] | None:
        with self._engine.connect() as connection:
            row = connection.execute(
                text(
                    'SELECT incarnation_id, object_version, state, provider_state '
                    'FROM commerce_provider_subscriptions '
                    'WHERE provider = :provider AND external_subscription_id = :sub'
                ),
                {'provider': provider, 'sub': external_subscription_id},
            ).mappings().first()
        return dict(row) if row else None

    def get_receipt(self, provider: str, external_event_id: str) -> dict[str, Any] | None:
        with self._engine.connect() as connection:
            row = connection.execute(
                text(
                    'SELECT incarnation_id, external_object_reference, object_version, '
                    'payload_digest, processing_state, sanitized_failure_reason, received_at '
                    'FROM commerce_billing_event_receipts '
                    'WHERE provider = :provider AND external_event_id = :event'
                ),
                {'provider': provider, 'event': external_event_id},
            ).mappings().first()
        return dict(row) if row else None

    @staticmethod
    def _hand_over(connection, provider: str, external_event_id: str, owner: Any) -> None:
        """A non-final receipt goes to the incarnation its subscription maps
        to. The only update a receipt's incarnation ever gets; a terminal
        receipt is left exactly as it is (and the database refuses otherwise)."""
        connection.execute(
            text(
                'UPDATE commerce_billing_event_receipts SET incarnation_id = :owner '
                'WHERE provider = :provider AND external_event_id = :event '
                "AND processing_state = 'received'"
            ),
            {'owner': owner, 'provider': provider, 'event': external_event_id},
        )

    @staticmethod
    def _current_row(connection, incarnation_id: str, now: datetime) -> dict[str, Any]:
        # FOR UPDATE locks nothing against a row that does not exist yet, so
        # the first event for an incarnation places one first.
        connection.execute(
            text(
                'INSERT INTO commerce_subscriptions '
                '(id, incarnation_id, provider, plan_id, state, created_at, updated_at) '
                "VALUES (:id, :inc, '', 'free', 'none', :now, :now) "
                'ON CONFLICT (incarnation_id) DO NOTHING'
            ),
            {'id': uuid.uuid4(), 'inc': incarnation_id, 'now': now},
        )
        return dict(connection.execute(
            text(
                'SELECT external_subscription_id, state FROM commerce_subscriptions '
                'WHERE incarnation_id = :inc FOR UPDATE'
            ),
            {'inc': incarnation_id},
        ).mappings().one())

    def record_event(
        self, *, incarnation_id: str, provider: str, external_event_id: str,
        event_object_version: int | None, update: SubscriptionUpdate,
        external_object_reference: str | None = None, payload_digest: str | None = None,
    ) -> CommerceOutcome:
        """One inbound event or one reconciliation of a previously-`unknown`
        one — the same operation either way, in one transaction.

        Lock order, always the same so two events cannot deadlock: the
        incarnation (`FOR SHARE`) -> the receipt for this exact (provider,
        external_event_id), placeholder-inserted first so the very first
        delivery is exactly-once too -> the provider subscription the event
        names, placeholder-inserted the same way -> the incarnation's current
        subscription row. Then decide; write the receipt (unless it belongs to
        another incarnation), the provider subscription's own version, and -
        when `current_subscription_decision()` says so - the current row.
        """
        now = datetime.now(UTC)
        subscription_id = update.external_subscription_id or None
        with self._engine.begin() as connection:
            owner = connection.execute(
                text('SELECT status FROM account_incarnations WHERE id = :inc FOR SHARE'),
                {'inc': incarnation_id},
            ).mappings().first()
            if owner is None:
                return CommerceOutcome(status='rejected', reason='unknown_incarnation')
            incarnation_deleted = owner['status'] != 'active'

            connection.execute(
                text(
                    'INSERT INTO commerce_billing_event_receipts '
                    '(id, incarnation_id, provider, external_event_id, '
                    'external_object_reference, object_version, payload_digest, '
                    "processing_state, received_at) VALUES "
                    "(:id, :inc, :provider, :event, :ref, :version, :digest, 'received', :now) "
                    'ON CONFLICT (provider, external_event_id) DO NOTHING'
                ),
                {
                    'id': uuid.uuid4(), 'inc': incarnation_id, 'provider': provider,
                    'event': external_event_id, 'ref': external_object_reference,
                    'version': event_object_version, 'digest': payload_digest, 'now': now,
                },
            )
            receipt = connection.execute(
                text(
                    'SELECT incarnation_id, processing_state, payload_digest '
                    'FROM commerce_billing_event_receipts '
                    'WHERE provider = :provider AND external_event_id = :event FOR UPDATE'
                ),
                {'provider': provider, 'event': external_event_id},
            ).mappings().one()
            receipt_incarnation = receipt['incarnation_id']
            # First, before anything can be written: a reused event id carrying
            # other content changes nothing - not even whose receipt it is
            # (review round 3).
            payload_matches = not (
                receipt['payload_digest'] and payload_digest and receipt['payload_digest'] != payload_digest
            )
            if not payload_matches:
                return CommerceOutcome(status='payload_conflict')

            # Whose event this is: the incarnation a committed mapping names
            # for its subscription (permanent once committed, so an unlocked
            # read is stable), else the receipt's stored one - never the
            # caller's. A non-final receipt filed under anyone else goes to
            # the mapped owner, still `received`.
            mapped_owner = None
            if subscription_id is not None:
                mapped_owner = connection.execute(
                    text(
                        'SELECT incarnation_id FROM commerce_provider_subscriptions '
                        'WHERE provider = :provider AND external_subscription_id = :sub '
                        'AND object_version IS NOT NULL'
                    ),
                    {'provider': provider, 'sub': subscription_id},
                ).scalar_one_or_none()
            if (mapped_owner is not None and receipt['processing_state'] == 'received'
                    and not _same(receipt_incarnation, mapped_owner)):
                self._hand_over(connection, provider, external_event_id, mapped_owner)
                receipt_incarnation = mapped_owner
            if mapped_owner is not None and not _same(mapped_owner, incarnation_id):
                return CommerceOutcome(status='foreign_incarnation')

            receipt_is_ours = _same(receipt_incarnation, incarnation_id)
            belongs_to = incarnation_id if receipt_is_ours else str(receipt_incarnation)
            already_processed = receipt['processing_state'] in _TERMINAL_RECEIPT_STATES

            subscription_version = None
            decidable = (receipt_is_ours and not incarnation_deleted and not already_processed
                         and payload_matches and subscription_id is not None
                         and event_object_version is not None)
            if decidable:
                connection.execute(
                    text(
                        'INSERT INTO commerce_provider_subscriptions '
                        '(id, incarnation_id, provider, external_subscription_id, state, '
                        'created_at, updated_at) VALUES '
                        "(:id, :inc, :provider, :sub, 'none', :now, :now) "
                        'ON CONFLICT (provider, external_subscription_id) DO NOTHING'
                    ),
                    {'id': uuid.uuid4(), 'inc': incarnation_id, 'provider': provider,
                     'sub': subscription_id, 'now': now},
                )
                mapped = connection.execute(
                    text(
                        'SELECT incarnation_id, object_version FROM commerce_provider_subscriptions '
                        'WHERE provider = :provider AND external_subscription_id = :sub FOR UPDATE'
                    ),
                    {'provider': provider, 'sub': subscription_id},
                ).mappings().one()
                if not _same(mapped['incarnation_id'], incarnation_id):
                    # Mapped by a transaction that committed after the read
                    # above: the same answer, now under its lock.
                    self._hand_over(connection, provider, external_event_id, mapped['incarnation_id'])
                    return CommerceOutcome(status='foreign_incarnation')
                subscription_version = mapped['object_version']

            verdict = subscription_event_decision(
                ProviderEvent(external_event_id, belongs_to, event_object_version),
                current_incarnation=incarnation_id,
                incarnation_deleted=incarnation_deleted,
                already_processed=already_processed,
                current_object_version=subscription_version,
                subscription_known=subscription_id is not None,
                payload_matches=payload_matches,
            )

            current_change = None
            if verdict == 'apply':
                current = self._current_row(connection, incarnation_id, now)
                current_change = current_subscription_decision(
                    current_subscription=current['external_subscription_id'],
                    current_state=current['state'],
                    event_subscription=subscription_id,
                    event_state=update.state,
                )
                if current_change == 'unknown':
                    verdict = 'unknown'
            if decidable and verdict != 'apply' and subscription_version is None:
                # Only an applied event maps a subscription. A placeholder that
                # nothing applied to goes again, so an undecided event claims
                # nothing (a NULL version never survives a commit).
                connection.execute(
                    text(
                        'DELETE FROM commerce_provider_subscriptions WHERE provider = :provider '
                        'AND external_subscription_id = :sub AND object_version IS NULL'
                    ),
                    {'provider': provider, 'sub': subscription_id},
                )

            # Written only when the receipt is this incarnation's and the
            # verdict has something to record. The incarnation column is never
            # part of the update.
            if receipt_is_ours and verdict in _RECEIPT_STATE:
                connection.execute(
                    text(
                        'UPDATE commerce_billing_event_receipts SET '
                        'external_object_reference = :ref, object_version = :version, '
                        'payload_digest = COALESCE(payload_digest, :digest), '
                        'processing_state = :state, sanitized_failure_reason = :reason '
                        'WHERE provider = :provider AND external_event_id = :event'
                    ),
                    {
                        'ref': external_object_reference, 'version': event_object_version,
                        'digest': payload_digest, 'state': _RECEIPT_STATE[verdict],
                        'reason': None if verdict == 'apply' else verdict,
                        'provider': provider, 'event': external_event_id,
                    },
                )

            if verdict != 'apply':
                return CommerceOutcome(status=verdict)

            connection.execute(
                text(
                    'UPDATE commerce_provider_subscriptions SET object_version = :version, '
                    'state = :state, provider_state = :provider_state, updated_at = :now '
                    'WHERE provider = :provider AND external_subscription_id = :sub'
                ),
                {
                    'version': event_object_version, 'state': update.state,
                    'provider_state': update.provider_state, 'now': now,
                    'provider': provider, 'sub': subscription_id,
                },
            )
            if current_change == 'replace':
                connection.execute(
                    text(
                        'UPDATE commerce_subscriptions SET provider = :provider, '
                        'external_customer_id = COALESCE(:customer, external_customer_id), '
                        'external_subscription_id = :sub, plan_id = :plan, state = :state, '
                        'object_version = :version, '
                        # Right-hand sides read the row as it was: the same
                        # subscription keeps a known paid-through date an
                        # event does not carry; a new subscription does not
                        # inherit the old one's.
                        'paid_through = CASE WHEN external_subscription_id = :same_sub '
                        'THEN COALESCE(:paid_through, paid_through) ELSE :paid_through END, '
                        'cancel_at_period_end = :cancel, provider_state = :provider_state, '
                        'updated_at = :now WHERE incarnation_id = :inc'
                    ),
                    {
                        'inc': incarnation_id, 'provider': provider,
                        'customer': update.external_customer_id, 'sub': subscription_id,
                        'same_sub': subscription_id,
                        'plan': update.plan_id, 'state': update.state,
                        'version': event_object_version, 'paid_through': update.paid_through,
                        'cancel': update.cancel_at_period_end,
                        'provider_state': update.provider_state, 'now': now,
                    },
                )
            return CommerceOutcome(
                status='apply', state=update.state,
                current='replaced' if current_change == 'replace' else 'kept',
            )
