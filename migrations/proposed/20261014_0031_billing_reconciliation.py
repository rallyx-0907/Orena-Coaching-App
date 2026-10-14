"""Billing reconciliation safety (PR-MON-3; docs/billing/PR-MON-3_DESIGN.md §5, design APPROVED 2026-10-14).

A follow-up to the proposed 0027 rather than an edit of it (decision H2: no operator has confirmed that no runtime
ever applied 0027, so its history is not rewritten). It adds:

- to `billing_orders`: the order's expiry (an abandoned checkout ends locally, but payOS is still asked about it
  until a successful lookup settles it), the provider's transaction reference, the provider lookup state the
  reconciler keeps per order, who recorded a refund and its reference, three partial indexes, and a trigger that
  refuses every DELETE (orders are financial records);
- `billing_reconciliation_items`: one durable row per money anomaly, so a verified money event is acknowledged
  only once it is recorded. Provider facts (`reported_*`, the event id, the provider state) have no foreign key, so
  an order code Orena never issued is still kept; Orena's own links (`billing_order_id`, `incarnation_id`) are set
  only when matched. Each kind has its own resolution rule; the safety-critical ones are enforced here by CHECKs
  and a trigger, not only by application code.

Review and gate. A PROPOSAL in `migrations/proposed/` (Alembic does not read it). It needs the implementation's
independent review, the rehearsal and the human's authorization, and it is promoted with 0027 (H1: read the real
head at promotion; one financial migration enters the chain at a time). Startup never applies it. `downgrade()`
refuses while either table holds a row: a runtime that took money cannot lose its financial records through
Alembic; it exists for rehearsal only.

Revision ID: 20261014_0031
Revises: 20261005_0027
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261014_0031"
down_revision = "20261005_0027"
branch_labels = None
depends_on = None

CRITICAL = ("entitlement_unsynced", "provider_paid_unrecorded")
MONEY = ("paid_deleted_account", "payment_unknown_order", "payment_mismatch", "payment_not_payable")
DISMISSABLE = ("event_undecided", "provider_refund", "provider_state_unresolved")
KINDS = CRITICAL + MONEY + DISMISSABLE
OUTCOMES = ("entitlement_synced", "payment_recorded", "payment_matched", "refund_confirmed", "reversal_confirmed",
            "obligation_waived", "recorded")
# A terminal row may change only these; anything else is refused by the trigger (a reopen is its own case).
_COUNTERS = ("occurrences", "last_seen_at")
_FACTS = ("kind", "gateway", "dedupe_key", "external_event_id", "reported_order_code", "reported_amount_minor",
          "reported_currency", "payload_digest", "first_seen_at")
_RESOLUTION = ("resolution_outcome", "resolution_reference", "resolution_note", "resolved_by", "resolved_at")


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _changed(column: str) -> str:
    return f"NEW.{column} IS DISTINCT FROM OLD.{column}"


def upgrade() -> None:
    # ---- billing_orders -------------------------------------------------------------------------------------
    op.add_column("billing_orders", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE billing_orders SET expires_at = created_at + interval '30 minutes'")
    op.alter_column("billing_orders", "expires_at", nullable=False)
    for column in (
        sa.Column("paid_reference", sa.String(200), nullable=True),
        sa.Column("provider_status", sa.String(30), nullable=True),
        sa.Column("provider_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_lookup_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lookup_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_by", sa.String(20), nullable=True),
        sa.Column("refund_reference", sa.String(200), nullable=True),
    ):
        op.add_column("billing_orders", column)
    op.execute("UPDATE billing_orders SET refunded_by = 'operator' WHERE state = 'refunded'")
    op.create_check_constraint("ck_billing_order_lookup_attempts", "billing_orders", "lookup_attempts >= 0")
    op.create_check_constraint("ck_billing_order_refunded_by", "billing_orders",
                               "refunded_by IS NULL OR refunded_by IN ('operator', 'provider')")
    op.create_check_constraint("ck_billing_order_refund_source", "billing_orders",
                               "(state = 'refunded') = (refunded_by IS NOT NULL)")
    op.create_index("ix_billing_orders_refund_reference", "billing_orders", ["gateway", "refund_reference"],
                    unique=True, postgresql_where=sa.text("refund_reference IS NOT NULL"))
    # The reconciler's pull set: every order whose provider outcome is not settled, a locally expired one too,
    # and a webhook-paid one until its confirming lookup, refunded or not.
    op.create_index("ix_billing_orders_pull", "billing_orders", ["gateway", "next_lookup_at"],
                    postgresql_where=sa.text("provider_settled_at IS NULL "
                                             "AND state IN ('created', 'pending', 'expired', 'paid', 'refunded')"))
    op.create_index("ix_billing_orders_open_expiry", "billing_orders", ["state", "expires_at"],
                    postgresql_where=sa.text("state IN ('created', 'pending')"))
    op.create_index("ix_billing_orders_paid", "billing_orders", ["incarnation_id", "paid_sequence"],
                    postgresql_where=sa.text("paid_sequence IS NOT NULL"))
    op.execute("""
        CREATE FUNCTION billing_orders_no_delete() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'billing_orders rows are financial records and are never deleted'
                USING ERRCODE = 'restrict_violation';
        END $$
    """)
    op.execute("CREATE TRIGGER billing_orders_no_delete BEFORE DELETE ON billing_orders "
               "FOR EACH ROW EXECUTE FUNCTION billing_orders_no_delete()")

    # ---- billing_reconciliation_items --------------------------------------------------------------------
    op.create_table(
        "billing_reconciliation_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("gateway", sa.String(40), nullable=False),
        sa.Column("dedupe_key", sa.String(200), nullable=False),
        # What the provider said: no foreign key, so a fact about an order Orena never issued is still kept.
        sa.Column("external_event_id", sa.String(200), nullable=True),
        sa.Column("reported_order_code", sa.BigInteger(), nullable=True),
        sa.Column("reported_amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("reported_currency", sa.String(3), nullable=True),
        sa.Column("provider_state", sa.String(60), nullable=True),
        sa.Column("payload_digest", sa.String(128), nullable=True),
        sa.Column("reason", sa.String(400), nullable=True),
        # Orena's own links, set only when the fact was matched to Orena's records.
        sa.Column("billing_order_id", sa.Uuid(), sa.ForeignKey("billing_orders.id", ondelete="RESTRICT"),
                  nullable=True),
        sa.Column("incarnation_id", sa.Uuid(), sa.ForeignKey("account_incarnations.id", ondelete="RESTRICT"),
                  nullable=True),
        sa.Column("state", sa.String(12), nullable=False, server_default="open"),
        sa.Column("resolution_outcome", sa.String(30), nullable=True),
        sa.Column("resolution_reference", sa.String(200), nullable=True),
        sa.Column("resolution_note", sa.String(400), nullable=True),
        sa.Column("resolved_by", sa.String(200), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reopened", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("occurrences", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("kind", "gateway", "dedupe_key", name="uq_billing_reconciliation_item"),
        sa.CheckConstraint(f"kind IN ({_in(KINDS)})", name="ck_billing_item_kind"),
        sa.CheckConstraint("state IN ('open', 'resolved', 'dismissed')", name="ck_billing_item_state"),
        sa.CheckConstraint("occurrences > 0 AND reopened >= 0", name="ck_billing_item_counts"),
        sa.CheckConstraint("(state = 'open') = (resolved_at IS NULL)", name="ck_billing_item_resolved_at"),
        sa.CheckConstraint(f"resolution_outcome IS NULL OR resolution_outcome IN ({_in(OUTCOMES)})",
                           name="ck_billing_item_outcome"),
        # Only a kind that carries no money obligation may be dismissed.
        sa.CheckConstraint(f"state <> 'dismissed' OR kind IN ({_in(DISMISSABLE)})", name="ck_billing_item_dismiss"),
        # A critical or money kind is resolved only with what actually happened.
        sa.CheckConstraint(f"state <> 'resolved' OR kind NOT IN ({_in(CRITICAL + MONEY)}) "
                           "OR resolution_outcome IS NOT NULL", name="ck_billing_item_outcome_required"),
        # Paid-without-access is closed only by the reconciler, once access was really granted.
        sa.CheckConstraint("kind <> 'entitlement_unsynced' OR state = 'open' "
                           "OR (resolution_outcome = 'entitlement_synced' AND resolved_by = 'reconciler')",
                           name="ck_billing_item_unsynced"),
        # "The payment is recorded" is the system's statement, never an administrator's (review P1-2).
        sa.CheckConstraint("resolution_outcome IS DISTINCT FROM 'payment_recorded' OR resolved_by = 'reconciler'",
                           name="ck_billing_item_payment_recorded"),
        # Waiving an obligation is an auditable financial reason.
        sa.CheckConstraint("resolution_outcome IS DISTINCT FROM 'obligation_waived' OR resolution_note IS NOT NULL",
                           name="ck_billing_item_waiver_reason"),
    )
    op.create_index("ix_billing_items_state_kind", "billing_reconciliation_items", ["state", "kind", "first_seen_at"])
    op.create_index("ix_billing_items_open_gateway", "billing_reconciliation_items", ["gateway"],
                    postgresql_where=sa.text("state = 'open'"))
    op.create_index("ix_billing_items_incarnation", "billing_reconciliation_items", ["incarnation_id"])

    facts_changed = " OR ".join(_changed(column) for column in _FACTS)
    links_changed = " OR ".join(f"(OLD.{column} IS NOT NULL AND {_changed(column)})"
                                for column in ("billing_order_id", "incarnation_id"))
    terminal_changes = " OR ".join(_changed(column) for column in (
        "state", "provider_state", "reason", "billing_order_id", "incarnation_id", "reopened") + _RESOLUTION)
    resolution_cleared = " AND ".join(f"NEW.{column} IS NULL" for column in _RESOLUTION)
    op.execute(f"""
        CREATE FUNCTION billing_reconciliation_items_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'billing reconciliation items are never deleted' USING ERRCODE = 'restrict_violation';
            END IF;
            IF {facts_changed} THEN
                RAISE EXCEPTION 'a reconciliation item''s provider facts never change' USING ERRCODE = 'restrict_violation';
            END IF;
            IF {links_changed} THEN
                RAISE EXCEPTION 'a reconciliation item''s matched link never changes' USING ERRCODE = 'restrict_violation';
            END IF;
            -- "payment_recorded" only when the order it names really holds the payment (review P1-2).
            IF OLD.state = 'open' AND NEW.state = 'resolved' AND NEW.resolution_outcome = 'payment_recorded'
                    AND NOT EXISTS (SELECT 1 FROM billing_orders o WHERE o.id = NEW.billing_order_id
                                    AND o.state IN ('paid', 'refunded')) THEN
                RAISE EXCEPTION 'payment_recorded needs the order to hold the payment' USING ERRCODE = 'check_violation';
            END IF;
            IF OLD.state <> 'open' THEN
                IF NEW.state = 'open' THEN
                    -- a reopen: only a critical kind, counted, with its resolution cleared
                    IF OLD.kind NOT IN ({_in(CRITICAL)}) OR NEW.reopened <> OLD.reopened + 1
                            OR NOT ({resolution_cleared}) THEN
                        RAISE EXCEPTION 'only a critical reconciliation item reopens' USING ERRCODE = 'restrict_violation';
                    END IF;
                ELSIF {terminal_changes} THEN
                    RAISE EXCEPTION 'a resolved reconciliation item changes only its counters'
                        USING ERRCODE = 'restrict_violation';
                END IF;
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute("CREATE TRIGGER billing_reconciliation_items_guard BEFORE UPDATE OR DELETE "
               "ON billing_reconciliation_items FOR EACH ROW EXECUTE FUNCTION billing_reconciliation_items_guard()")


def downgrade() -> None:
    connection = op.get_bind()
    for table in ("billing_reconciliation_items", "billing_orders"):
        if connection.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM {table})")).scalar():
            raise RuntimeError(f"{table} holds financial records; this revision is not downgraded over them")
    op.execute("DROP TRIGGER billing_reconciliation_items_guard ON billing_reconciliation_items")
    op.execute("DROP FUNCTION billing_reconciliation_items_guard()")
    op.drop_table("billing_reconciliation_items")
    op.execute("DROP TRIGGER billing_orders_no_delete ON billing_orders")
    op.execute("DROP FUNCTION billing_orders_no_delete()")
    for index in ("ix_billing_orders_paid", "ix_billing_orders_open_expiry", "ix_billing_orders_pull",
                  "ix_billing_orders_refund_reference"):
        op.drop_index(index, table_name="billing_orders")
    for constraint in ("ck_billing_order_refund_source", "ck_billing_order_refunded_by",
                       "ck_billing_order_lookup_attempts"):
        op.drop_constraint(constraint, "billing_orders", type_="check")
    for column in ("refund_reference", "refunded_by", "provider_settled_at", "lookup_attempts", "next_lookup_at",
                   "provider_checked_at", "provider_status", "paid_reference", "expires_at"):
        op.drop_column("billing_orders", column)
