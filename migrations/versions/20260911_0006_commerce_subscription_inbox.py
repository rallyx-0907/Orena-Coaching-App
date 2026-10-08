"""Subscription state and the provider-event inbox for I3.

APPROVED - delegated independent review, round 3 of `7020925` (APPROVED
WITH REQUIRED CHANGES; the required code reorder made in `6c4131a`); trail in
`docs/project/I3_SCHEMA_REVIEW_REQUEST.md`. In the live chain; applied to the
sandbox runtime only, under D-054's delegation. Additive only. Nothing here
enables billing or wires a caller.

Scope, deliberately narrow: this covers only ORENA_COMMERCE_ARCHITECTURE.md
§3's subscription state and inbound-event reconciliation - the two tables
`writing_coach.reference_backbone.subscription_event_decision()` needs a
caller to read/write. It does NOT propose PlanVersion or PriceReference
(§2); QuotaBucket and Reservation (§4) are `20260912_0007`, which revises this
one. Nothing here enables billing, activates a caller, or reads real provider
credentials.

Revision ID: 20260911_0006
Revises: 20260908_0005

Changes from the first submission, per docs/project/I3_SCHEMA_REVIEW_REQUEST.md:

- `commerce_billing_event_receipts.processing_state` drops 'failed': a
  receipt is now either 'received' (non-terminal - exists durably, does not
  yet block reconciliation) or a terminal 'applied'/'ignored'. Only a
  terminal receipt makes a repeat of the same (provider, external_event_id)
  a 'duplicate'; a 'received' one lets the same event id be re-decided once
  authoritative provider state is available. See commerce_repository.py.
- Added `commerce_billing_event_receipts.external_object_reference` and
  `.payload_digest`, completing parity with ORENA_COMMERCE_ARCHITECTURE.md
  §2's BillingEventReceipt ("external object reference... revision/digest").
  Both are caller-supplied identifiers/hashes, never raw provider payload.
- Added a partial unique index on `commerce_subscriptions
  (provider, external_subscription_id)` so one provider subscription can
  never map to more than one incarnation - required before any webhook
  resolver can be built on this schema, not after.

Changes from the re-review (round 1 of the delegated review):

- Added `commerce_provider_subscriptions`: one row per provider subscription
  with its own last object version, state and owning incarnation. Versions
  are compared only within one provider subscription, never against another
  one's (a resubscription is no longer 'stale' against the ended
  subscription it replaces, and a late event from the old one no longer
  overwrites the new one). The mapping of a provider subscription to one
  incarnation is enforced here for good, so a conflict is detected before
  anything is written and gets a terminal receipt instead of an integrity
  error that rolled the receipt back.
- `commerce_subscriptions` keeps the provider's original state name
  (`provider_state`, §3 "retain the original state internally"). Whether it
  waits on reconciliation (§2) is derived when read - any `received`
  receipt for the incarnation - not stored, so it cannot go stale (round 2).
- A terminal receipt is immutable in the database, not only by convention:
  a trigger refuses any update or delete of an `applied`/`ignored` receipt.
  Receipt compaction under a future retention policy is a reviewed
  migration that changes this trigger, not a quiet DELETE.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260911_0006"
down_revision = "20260908_0005"
branch_labels = None
depends_on = None

# The full canonical vocabulary from ORENA_COMMERCE_ARCHITECTURE.md §3 and
# writing_coach.product.commerce.SubscriptionState - kept in exact sync by
# the review checklist, not by a shared import (a migration must not import
# application code that can change under it after the migration is applied).
SUBSCRIPTION_STATES = (
    "none", "pending", "trialing", "active", "past_due", "paused", "ended", "unknown",
)
# 'received': durable, non-terminal - does not make a repeat delivery a
# duplicate. 'applied' / 'ignored': terminal - immutable once written, and
# the only two states a repeat delivery of the same event id is compared
# against for idempotency.
RECEIPT_PROCESSING_STATES = ("received", "applied", "ignored")


def _in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    # ---- 1. Current subscription state, one row per incarnation -----------
    # Mutable current-state row, not an event log - the inbox below is the
    # log. `object_version` is the provider's own authoritative revision,
    # nullable because "no verified revision yet" is a real, common state
    # (never verified, or the adapter could not read one) and must reach
    # subscription_event_decision() as an explicit unknown, never a guessed 0.
    op.create_table(
        "commerce_subscriptions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "incarnation_id",
            sa.Uuid(),
            sa.ForeignKey("account_incarnations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(40), nullable=False, server_default=""),
        sa.Column("external_customer_id", sa.String(200), nullable=True),
        sa.Column("external_subscription_id", sa.String(200), nullable=True),
        sa.Column("plan_id", sa.String(40), nullable=False, server_default="free"),
        sa.Column("state", sa.String(20), nullable=False, server_default="none"),
        sa.Column("object_version", sa.BigInteger(), nullable=True),
        sa.Column("paid_through", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
        # The provider's own state name, as received - normalized `state` is
        # what everything reads; this is retained for audit and remapping.
        sa.Column("provider_state", sa.String(60), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # RESTRICT, matching account_incarnations' own deletion-barrier design
        # in 20260908_0005: a deleted incarnation's subscription row must
        # keep denying reactivation, not disappear with it.
        sa.CheckConstraint(
            f"state IN ({_in_list(SUBSCRIPTION_STATES)})",
            name="ck_commerce_subscription_state",
        ),
        sa.CheckConstraint(
            "object_version IS NULL OR object_version >= 0",
            name="ck_commerce_subscription_object_version",
        ),
        # One current-subscription row per incarnation - "Subscription:
        # account incarnation, provider/customer/subscription mapping..." is
        # 1:1 in §2, and a second row would make "the" subscription ambiguous
        # for the exact read accountCommerce()/resolveEntitlement() already
        # do the honest-unknown work for.
        sa.UniqueConstraint("incarnation_id", name="uq_commerce_subscription_incarnation"),
    )
    # Review finding: nothing stopped one provider subscription mapping to
    # more than one incarnation, which any future webhook resolver would need
    # to be false to trust its own lookup. Partial - most rows have no
    # external subscription yet, and NULL must never collide with NULL.
    op.create_index(
        "uq_commerce_subscription_external",
        "commerce_subscriptions",
        ["provider", "external_subscription_id"],
        unique=True,
        postgresql_where=sa.text("external_subscription_id IS NOT NULL"),
    )

    # ---- 2. Every provider subscription an incarnation has had -------------
    # "Use provider object version when authoritative ... serialize
    # reconciliation per subscription" (§3): a provider's object version
    # orders the revisions of one subscription and says nothing about another,
    # so each provider subscription keeps its own. The row is the permanent
    # mapping of that subscription to one incarnation - kept after the
    # incarnation's current subscription moves on, and after deletion
    # (RESTRICT), so an old subscription's late events stay attributable and
    # can never be picked up by a new incarnation.
    op.create_table(
        "commerce_provider_subscriptions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "incarnation_id",
            sa.Uuid(),
            sa.ForeignKey("account_incarnations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("external_subscription_id", sa.String(200), nullable=False),
        # NULL only inside the transaction that placed it to make a first
        # use lockable: an applied event sets it, and anything else deletes
        # the placeholder again, so no committed row has NULL here.
        sa.Column("object_version", sa.BigInteger(), nullable=True),
        sa.Column("state", sa.String(20), nullable=False, server_default="none"),
        sa.Column("provider_state", sa.String(60), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"state IN ({_in_list(SUBSCRIPTION_STATES)})",
            name="ck_commerce_provider_subscription_state",
        ),
        sa.CheckConstraint(
            "object_version IS NULL OR object_version >= 0",
            name="ck_commerce_provider_subscription_version",
        ),
        sa.UniqueConstraint(
            "provider", "external_subscription_id", name="uq_commerce_provider_subscription"
        ),
    )
    op.create_index(
        "ix_commerce_provider_subscriptions_incarnation",
        "commerce_provider_subscriptions",
        ["incarnation_id"],
    )

    # ---- 3. The provider-event inbox, for dedup and stale rejection --------
    # "Duplicate event IDs do not repeat grants" (§3) is enforced here, not
    # trusted to caller discipline: (provider, external_event_id) is globally
    # unique because a provider's event id is a global identifier, not scoped
    # to one incarnation. No raw payload column - "private raw payload
    # retention is separately governed; never expose it in learner APIs" -
    # `payload_digest` is a caller-computed hash, `sanitized_failure_reason`
    # the only free-text field, and `external_object_reference` an opaque
    # provider-issued id, never provider payload content.
    op.create_table(
        "commerce_billing_event_receipts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "incarnation_id",
            sa.Uuid(),
            sa.ForeignKey("account_incarnations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("external_event_id", sa.String(200), nullable=False),
        # The provider object (subscription/customer id) this event concerns
        # - §2's "external object reference" - distinct from the event's own
        # id above.
        sa.Column("external_object_reference", sa.String(200), nullable=True),
        sa.Column("object_version", sa.BigInteger(), nullable=True),
        # §2's "revision/digest": a caller-computed hash of the normalized,
        # already-sanitized event content, never the raw payload. Detecting a
        # reused event id carrying different content is a natural use, not
        # implemented by this proposal - stored for that and for audit.
        sa.Column("payload_digest", sa.String(64), nullable=True),
        sa.Column("processing_state", sa.String(20), nullable=False),
        sa.Column("sanitized_failure_reason", sa.String(400), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"processing_state IN ({_in_list(RECEIPT_PROCESSING_STATES)})",
            name="ck_commerce_receipt_processing_state",
        ),
        sa.CheckConstraint(
            "object_version IS NULL OR object_version >= 0",
            name="ck_commerce_receipt_object_version",
        ),
        sa.UniqueConstraint(
            "provider", "external_event_id", name="uq_commerce_receipt_provider_event"
        ),
    )
    op.create_index(
        "ix_commerce_receipts_incarnation_received",
        "commerce_billing_event_receipts",
        ["incarnation_id", "received_at"],
    )
    # A terminal receipt is the one durable answer to "was this event
    # handled"; the database, not only the repository, keeps it that way.
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "CREATE FUNCTION commerce_receipt_terminal_is_final() RETURNS trigger "
            "LANGUAGE plpgsql AS $$ BEGIN "
            "RAISE EXCEPTION 'terminal billing event receipt % is immutable', OLD.id "
            "USING ERRCODE = 'integrity_constraint_violation'; "
            "END $$"
        )
        op.execute(
            "CREATE TRIGGER commerce_receipt_terminal_is_final "
            "BEFORE UPDATE OR DELETE ON commerce_billing_event_receipts FOR EACH ROW "
            "WHEN (OLD.processing_state IN ('applied', 'ignored')) "
            "EXECUTE FUNCTION commerce_receipt_terminal_is_final()"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS commerce_receipt_terminal_is_final ON commerce_billing_event_receipts"
        )
        op.execute("DROP FUNCTION IF EXISTS commerce_receipt_terminal_is_final()")
    op.drop_index(
        "ix_commerce_receipts_incarnation_received",
        table_name="commerce_billing_event_receipts",
    )
    op.drop_table("commerce_billing_event_receipts")
    op.drop_index(
        "ix_commerce_provider_subscriptions_incarnation",
        table_name="commerce_provider_subscriptions",
    )
    op.drop_table("commerce_provider_subscriptions")
    op.drop_index("uq_commerce_subscription_external", table_name="commerce_subscriptions")
    op.drop_table("commerce_subscriptions")
