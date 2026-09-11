"""Subscription state and the provider-event inbox.

PROPOSAL, NOT DEPLOYED — the tables this reads and writes are in
`migrations/proposed/20260911_0006`, not `migrations/versions/`. Nothing here
runs against any real database until that migration is reviewed, approved and
moved, mirroring I2's path. No caller is wired to this either way.

Revised against review findings (docs/project/I3_SCHEMA_REVIEW_REQUEST.md):

1. A receipt's mere existence no longer means 'duplicate'. Only a *terminal*
   receipt (`applied` / `ignored`) does; a `received` one — written for
   `'unknown'`, when the event itself had no verifiable version — does not,
   so the same (provider, external_event_id) can be re-decided once
   authoritative provider state is available. `record_event()` is that
   re-decision path too: calling it again with the same event id and a now-
   known `event_object_version` is reconciliation, not a second event.
2. `account_incarnations` is now read `FOR UPDATE`, so this transaction
   serializes against `incarnation_repository.mark_deleted()`'s `UPDATE` on
   the same row rather than racing it under READ COMMITTED.
3. A deleted incarnation now still gets a durable, terminal receipt
   (`ignored`, reason `deleted_incarnation_rejected`) — idempotency/audit
   state, not an entitlement grant — while `commerce_subscriptions` gets no
   row at all for it, same as before.

Open question left for review, not hidden: `record_event()` takes the
incarnation it should apply the event to as a trusted input. A real provider
webhook names an external customer/subscription id, not an incarnation id, so
resolving *which* incarnation a webhook belongs to is a lookup this file does
not perform — the same gap I1's incarnation resolution already has (no
production caller resolves one from a request yet). Until that lookup exists,
`subscription_event_decision()`'s `foreign_incarnation` branch is reachable
only if a caller passes a stale/cached incarnation that no longer matches
`current_incarnation` — never from a genuinely misrouted webhook, because
nothing here routes one from raw provider identifiers yet.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from writing_coach.reference_backbone import ProviderEvent, subscription_event_decision

_TERMINAL_RECEIPT_STATES = ('applied', 'ignored')

# Every non-'apply' verdict's terminal receipt state and its sanitized reason.
# 'unknown' is deliberately absent: it writes 'received' (non-terminal), not
# a row from this table.
_TERMINAL_OUTCOME = {
    'stale': 'ignored',
    'deleted_incarnation_rejected': 'ignored',
    'foreign_incarnation': 'ignored',
}


@dataclass(frozen=True)
class SubscriptionUpdate:
    """What an adapter normalized from one provider event, if it applies.

    The repository never inspects a provider payload itself; normalizing one
    into this shape is the caller's job, same division as
    `writing_coach.product.commerce`'s read side never touching a repository.
    """

    state: str
    plan_id: str
    external_customer_id: str | None
    external_subscription_id: str | None
    paid_through: datetime | None
    cancel_at_period_end: bool


class CommerceOutcome(dict):
    """`status` is one of subscription_event_decision()'s six outcomes, or
    `rejected` for an incarnation this repository does not know about at all."""


class PostgresCommerceRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get_subscription(self, incarnation_id: str) -> dict[str, Any] | None:
        with self._engine.connect() as connection:
            row = connection.execute(
                text(
                    'SELECT provider, external_customer_id, external_subscription_id, '
                    'plan_id, state, object_version, paid_through, cancel_at_period_end '
                    'FROM commerce_subscriptions WHERE incarnation_id = :inc'
                ),
                {'inc': incarnation_id},
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

    def record_event(
        self, *, incarnation_id: str, provider: str, external_event_id: str,
        event_object_version: int | None, update: SubscriptionUpdate,
        external_object_reference: str | None = None, payload_digest: str | None = None,
    ) -> CommerceOutcome:
        """One inbound event or one reconciliation of a previously-`unknown`
        one — the same operation either way, in one transaction.

        Order: lock the incarnation (serializing against `mark_deleted()`) →
        placeholder-insert and lock the receipt row for this exact
        (provider, external_event_id) so concurrent delivery of the same
        event id is exactly-once even the first time it is ever seen →
        decide, using only a *terminal* prior receipt as 'already_processed'
        → placeholder-insert and lock the subscription row (skipped for a
        deleted incarnation - it gets a receipt, never a subscription row) →
        write the receipt (terminal, or 'received' again if still unknown) →
        on 'apply' only, write the subscription row.
        """
        now = datetime.now(UTC)
        with self._engine.begin() as connection:
            owner = connection.execute(
                text('SELECT status FROM account_incarnations WHERE id = :inc FOR UPDATE'),
                {'inc': incarnation_id},
            ).mappings().first()
            if owner is None:
                return CommerceOutcome(status='rejected', reason='unknown_incarnation')
            incarnation_deleted = owner['status'] != 'active'

            # Same "concurrent first use" problem as the subscription row
            # below: `FOR UPDATE` locks nothing against a row that does not
            # exist, so the very first delivery of a given event id must
            # place a lockable row before two concurrent deliveries can race.
            # 'received' is the correct initial state regardless of what this
            # call's own verdict turns out to be - it is only ever read back
            # and then updated in place.
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
                    'SELECT processing_state FROM commerce_billing_event_receipts '
                    'WHERE provider = :provider AND external_event_id = :event FOR UPDATE'
                ),
                {'provider': provider, 'event': external_event_id},
            ).mappings().first()
            already_processed = receipt['processing_state'] in _TERMINAL_RECEIPT_STATES

            current_object_version = None
            if not incarnation_deleted and not already_processed:
                # Placeholder-insert + lock, same pattern as the receipt
                # above and for the same reason - the very first event ever
                # recorded for an incarnation needs a row to lock too.
                # Skipped for a deleted incarnation: "no new-account grant"
                # means no commerce row of any kind, not a neutral one.
                connection.execute(
                    text(
                        'INSERT INTO commerce_subscriptions '
                        '(id, incarnation_id, provider, plan_id, state, created_at, updated_at) '
                        "VALUES (:id, :inc, '', 'free', 'none', :now, :now) "
                        'ON CONFLICT (incarnation_id) DO NOTHING'
                    ),
                    {'id': uuid.uuid4(), 'inc': incarnation_id, 'now': now},
                )
                subscription = connection.execute(
                    text(
                        'SELECT object_version FROM commerce_subscriptions '
                        'WHERE incarnation_id = :inc FOR UPDATE'
                    ),
                    {'inc': incarnation_id},
                ).mappings().first()
                current_object_version = subscription['object_version']

            event = ProviderEvent(external_event_id, incarnation_id, event_object_version)
            verdict = subscription_event_decision(
                event,
                current_incarnation=incarnation_id,
                incarnation_deleted=incarnation_deleted,
                already_processed=already_processed,
                current_object_version=current_object_version,
            )

            # A terminal receipt is immutable once written - a 'duplicate'
            # verdict means exactly that one already exists, so there is
            # nothing to update. Every other verdict updates the row the
            # placeholder insert above guarantees exists.
            if verdict != 'duplicate':
                connection.execute(
                    text(
                        'UPDATE commerce_billing_event_receipts SET '
                        'incarnation_id = :inc, external_object_reference = :ref, '
                        'object_version = :version, payload_digest = :digest, '
                        'processing_state = :state, sanitized_failure_reason = :reason '
                        'WHERE provider = :provider AND external_event_id = :event'
                    ),
                    {
                        'inc': incarnation_id, 'ref': external_object_reference,
                        'version': event_object_version, 'digest': payload_digest,
                        'state': 'applied' if verdict == 'apply' else _TERMINAL_OUTCOME.get(
                            verdict, 'received'
                        ),
                        'reason': None if verdict == 'apply' else verdict,
                        'provider': provider, 'event': external_event_id,
                    },
                )

            if verdict != 'apply':
                return CommerceOutcome(status=verdict)

            connection.execute(
                text(
                    'UPDATE commerce_subscriptions SET provider = :provider, '
                    'external_customer_id = :customer, external_subscription_id = :sub, '
                    'plan_id = :plan, state = :state, object_version = :version, '
                    'paid_through = :paid_through, cancel_at_period_end = :cancel, '
                    'updated_at = :now WHERE incarnation_id = :inc'
                ),
                {
                    'inc': incarnation_id, 'provider': provider,
                    'customer': update.external_customer_id, 'sub': update.external_subscription_id,
                    'plan': update.plan_id, 'state': update.state,
                    'version': event_object_version, 'paid_through': update.paid_through,
                    'cancel': update.cancel_at_period_end, 'now': now,
                },
            )
            return CommerceOutcome(status='apply', state=update.state)
