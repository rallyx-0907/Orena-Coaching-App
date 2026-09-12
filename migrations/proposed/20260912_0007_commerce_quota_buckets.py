"""Quota buckets and reservations for I3.

PROPOSAL — awaiting review, following the same path
`20260911_0006_commerce_subscription_inbox.py` is on. Not applied anywhere.
Alembic does not read `migrations/proposed/`, so this file is not part of the
revision chain and no running deployment's startup check sees it. Two tables.
Additive only.

Scope, deliberately narrow: this covers only ORENA_COMMERCE_ARCHITECTURE.md
§2/§4's QuotaBucket and Reservation records - the two tables
`writing_coach.reference_backbone.reserve_decision()`, `settle_decision()`
and `release_decision()` need a caller to read/write. It does NOT propose
`PlanVersion` or `PriceReference` (§2) - plan identity stays the existing
`writing_coach/product/catalog.py` static `PLANS` dict, exactly the same
reasoning `20260911_0006` already applied to `commerce_subscriptions.plan_id`.
Nothing here enables enforcement, reads a real request, or wires a caller;
`billing_ready` stays `False` everywhere upstream regardless of this
proposal's outcome.

Chain position, named rather than hidden: this migration revises
`20260911_0006`, which is itself still awaiting re-review - not
`20260908_0005` directly. That is a chain-linearity choice, not a data
dependency: neither new table has any foreign key into
`commerce_subscriptions` or `commerce_billing_event_receipts`, only into
`account_incarnations` (already applied). Rebasing this migration onto
`20260908_0005` directly, or onto whatever revised form `20260911_0006` takes
after its re-review, is a mechanical follow-up if the reviewer prefers a
different chain shape - the table definitions themselves do not change either
way.

Revision ID: 20260912_0007
Revises: 20260911_0006

Reservation lifecycle this schema exists to serve, per §4:

    reserve(operation_id, requested_units) -> one reservation row, state
    'reserved', admitted_units = requested_units; bucket.reserved +=
    admitted_units. Idempotent: retrying the same operation_id with the same
    requested_units returns the existing row's outcome; retrying it with a
    *different* requested_units is a payload conflict, decided by the
    repository comparing the stored admitted_units before ever calling
    reserve_decision() again for that operation_id.

    settle(operation_id, actual_units) -> state 'settled', actual_units
    recorded; bucket.reserved -= admitted_units, bucket.consumed +=
    actual_units. Idempotent per settle_decision().

    release(operation_id) -> state 'released'; bucket.reserved -=
    admitted_units, nothing consumed. Idempotent per release_decision().

A rejected reserve() attempt (denied / exhausted / unknown entitlement) never
writes a reservation row at all - nothing was admitted, so there is nothing
to make idempotent, and a caller retrying the same operation_id later (after
capacity frees up, or entitlement resolves) must be free to succeed then. Only
an *admitted* reservation needs a durable row, for the same reason
`commerce_billing_event_receipts` only needs one for a genuinely undecided
outcome, not for every possible outcome.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260912_0007"
down_revision = "20260911_0006"
branch_labels = None
depends_on = None

# Kept in exact sync with reference_backbone.py's returned vocabulary by the
# review checklist, not a shared import - a migration must not import
# application code that can change under it after being applied, the same
# reasoning 20260908_0005 and 20260911_0006 already established.
RESERVATION_STATES = ("reserved", "settled", "released")


def _in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    # ---- 1. One quota bucket per incarnation + meter + window --------------
    # "QuotaBucket: account incarnation + meter + window ID, limit policy
    # version, consumed and reserved units. Language is diagnostic, not a
    # second allowance" (§2) - so the unique key is (incarnation, meter,
    # window), never language. `unit_limit` is nullable because Quota.limit
    # is explicitly `None = unlimited`, never a guessed number; `meter` is an
    # unconstrained string against catalog.py's entitlement keys
    # (`writing.evaluate`, `dictionary.lookup`, ...) for the same reason
    # `commerce_subscriptions.plan_id` is unconstrained against `PLANS` -
    # catalog values are current configuration, not a migration-worthy
    # pricing decision.
    op.create_table(
        "commerce_quota_buckets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "incarnation_id",
            sa.Uuid(),
            sa.ForeignKey("account_incarnations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("meter", sa.String(80), nullable=False),
        # Stable window identity (e.g. a calendar-month key or a verified
        # billing-period id), never derived from arrival timestamps - "Server
        # time determines windows" (§4), and a renewal creates a new bucket
        # rather than mutating this one's identity.
        sa.Column("window_id", sa.String(60), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("unit_limit", sa.BigInteger(), nullable=True),
        sa.Column("consumed", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("reserved", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("consumed >= 0", name="ck_commerce_quota_bucket_consumed"),
        sa.CheckConstraint("reserved >= 0", name="ck_commerce_quota_bucket_reserved"),
        sa.CheckConstraint(
            "unit_limit IS NULL OR unit_limit >= 0", name="ck_commerce_quota_bucket_limit"
        ),
        sa.CheckConstraint("window_end > window_start", name="ck_commerce_quota_bucket_window"),
        # RESTRICT, matching the deletion-barrier pattern 20260908_0005 and
        # 20260911_0006 both established: a deleted incarnation's quota
        # history must keep denying reactivation, not disappear with it.
        sa.UniqueConstraint(
            "incarnation_id", "meter", "window_id", name="uq_commerce_quota_bucket"
        ),
    )

    # ---- 2. One reservation row per admitted operation ----------------------
    # "Reservation: operation ID, bucket, upper-bound units, state, admitted
    # policy version and dispatch/result reference. Unique operation prevents
    # double charge" (§2) - operation_id is globally unique, the same
    # reasoning `commerce_billing_event_receipts.external_event_id` already
    # applies to a provider's event id: an operation identifies one specific
    # attempted unit of work regardless of which bucket it happens to belong
    # to. No row is written for a rejected reserve() attempt - see the module
    # docstring; only an admitted reservation needs durable idempotency state.
    op.create_table(
        "commerce_quota_reservations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "bucket_id",
            sa.Uuid(),
            sa.ForeignKey("commerce_quota_buckets.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("operation_id", sa.String(200), nullable=False),
        sa.Column("admitted_units", sa.BigInteger(), nullable=False),
        sa.Column("actual_units", sa.BigInteger(), nullable=True),
        sa.Column("state", sa.String(20), nullable=False, server_default="reserved"),
        sa.Column("policy_version", sa.String(40), nullable=False),
        # Opaque dispatch/result reference (e.g. a job or evaluation id) per
        # §2 - never a raw provider/job payload, same discipline
        # `commerce_billing_event_receipts.external_object_reference` already
        # follows.
        sa.Column("outcome_ref", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("admitted_units >= 1", name="ck_commerce_reservation_admitted"),
        sa.CheckConstraint(
            "actual_units IS NULL OR actual_units >= 0", name="ck_commerce_reservation_actual"
        ),
        sa.CheckConstraint(
            f"state IN ({_in_list(RESERVATION_STATES)})",
            name="ck_commerce_reservation_state",
        ),
        sa.UniqueConstraint("operation_id", name="uq_commerce_reservation_operation"),
    )
    op.create_index(
        "ix_commerce_reservations_bucket", "commerce_quota_reservations", ["bucket_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_commerce_reservations_bucket", table_name="commerce_quota_reservations")
    op.drop_table("commerce_quota_reservations")
    op.drop_table("commerce_quota_buckets")
