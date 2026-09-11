"""Subscription state and the provider-event inbox.

PROPOSAL, NOT DEPLOYED — the tables this reads and writes are in
`migrations/proposed/20260911_0006`, not `migrations/versions/`. Nothing here
runs against any real database until that migration is reviewed, approved and
moved, mirroring I2's path. No caller is wired to this either way.

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

    def record_event(
        self, *, incarnation_id: str, provider: str, external_event_id: str,
        event_object_version: int | None, update: SubscriptionUpdate,
    ) -> CommerceOutcome:
        """One inbound event, start to finish, in one transaction.

        Order matches ORENA_COMMERCE_ARCHITECTURE.md §3: lock the current
        subscription row, look up the receipt for this exact
        (provider, external_event_id) *before* deciding — so a lost
        acknowledgment sees the same outcome its first attempt got rather
        than being re-evaluated against state its own first attempt already
        changed — decide, then write the receipt and (on 'apply' only) the
        subscription row together.
        """
        now = datetime.now(UTC)
        with self._engine.begin() as connection:
            owner = connection.execute(
                text('SELECT status FROM account_incarnations WHERE id = :inc'),
                {'inc': incarnation_id},
            ).mappings().first()
            if owner is None:
                return CommerceOutcome(status='rejected', reason='unknown_incarnation')
            # Checked, and acted on, before anything below is written: "no
            # new-account grant" (§3) means a deleted incarnation gets no
            # commerce row of any kind, not a neutral placeholder one either.
            if owner['status'] != 'active':
                return CommerceOutcome(status='deleted_incarnation_rejected')

            # `FOR UPDATE` locks a row that exists; it locks nothing at all
            # against a row that does not, so the very first event for an
            # incarnation would otherwise race unserialized - "concurrent
            # first use" the same way I2's stream head had to solve it. The
            # placeholder insert is racy by construction and safe *because*
            # of it: the unique constraint lets exactly one concurrent
            # attempt create the row, `DO NOTHING` absorbs the rest, and every
            # caller then serializes on the `FOR UPDATE` below against a row
            # that is now guaranteed to exist.
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

            already_processed = connection.execute(
                text(
                    'SELECT 1 FROM commerce_billing_event_receipts '
                    'WHERE provider = :provider AND external_event_id = :event'
                ),
                {'provider': provider, 'event': external_event_id},
            ).first() is not None

            event = ProviderEvent(external_event_id, incarnation_id, event_object_version)
            verdict = subscription_event_decision(
                event,
                current_incarnation=incarnation_id,
                incarnation_deleted=False,  # the early return above is the only path there
                already_processed=already_processed,
                current_object_version=current_object_version,
            )

            # 'duplicate' means a receipt for this exact (provider,
            # external_event_id) already exists - inserting another would
            # violate the same uniqueness constraint that made it 'duplicate'
            # in the first place, and there is nothing new to record: the
            # receipt from the event's *first* arrival already stands.
            if verdict != 'duplicate':
                connection.execute(
                    text(
                        'INSERT INTO commerce_billing_event_receipts '
                        '(id, incarnation_id, provider, external_event_id, object_version, '
                        'processing_state, received_at) VALUES '
                        '(:id, :inc, :provider, :event, :version, :state, :now)'
                    ),
                    {
                        'id': uuid.uuid4(), 'inc': incarnation_id, 'provider': provider,
                        'event': external_event_id, 'version': event_object_version,
                        'state': 'applied' if verdict == 'apply' else (
                            'ignored' if verdict == 'stale' else 'failed'
                        ),
                        'now': now,
                    },
                )

            if verdict != 'apply':
                return CommerceOutcome(status=verdict)

            # The placeholder insert above guarantees this row exists (and is
            # held under our own FOR UPDATE lock) by this point, so applying
            # is always an update - never a second INSERT racing the one that
            # just ran.
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
