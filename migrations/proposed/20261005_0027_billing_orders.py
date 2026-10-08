"""Billing orders: one row per checkout attempt, for every gateway (completion plan item 4; BILLING_GATEWAYS.md).

A merchant of record (Polar) runs the subscription itself; the order row only binds Orena's checkout - the
account incarnation, the approved price, one operation id - to the gateway's reference. A domestic gateway
(payOS) sells a prepaid period; its order row is also the payment fact: the period it bought, in what sequence,
until when, and whether it was refunded. `commerce_subscriptions` stays the one record of access; the order
row is what the prepaid subscription's state is computed from (billing/prepaid.py), so a crash between the two
writes is repaired by re-applying the order, never by guessing.

Money is an integer in the currency's minor unit (VND has none). `order_code` is the integer payOS requires,
unique, from a sequence. `operation_id` is unique: a retried checkout is the same order. `paid_sequence` is the
order's place among its incarnation's paid orders, assigned under the incarnation's lock; it is the prepaid
subscription's object version, so an out-of-order apply is `stale` and can never shorten access.

Rows are financial records: RESTRICT on the incarnation (matching commerce_subscriptions, 0006), never deleted
with the account; their retention is the human's decision with the refund/terms pages (item 5).

Review and gate. A PROPOSAL in `migrations/proposed/` (Alembic does not read it): it needs an independent
review (payment/entitlement: AGENTS.md §1), the rehearsal, and the human's authorization. It is parented on
0026, the AI cost proposal; promoted alone, it is re-parented on the head of the day. Billing is off until then
and after (BILLING_ENABLED, keys and prices are human gates). `downgrade()` drops the table; rehearsal only.

Revision ID: 20261005_0027
Revises: 20261005_0026
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261005_0027"
down_revision = "20261005_0026"
branch_labels = None
depends_on = None

STATES = ("created", "pending", "paid", "expired", "cancelled", "refunded", "failed")


def upgrade() -> None:
    op.execute("CREATE SEQUENCE billing_order_code_seq START WITH 100001")
    op.create_table(
        "billing_orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("operation_id", sa.String(80), nullable=False, unique=True),
        sa.Column("order_code", sa.BigInteger(), nullable=False, unique=True,
                  server_default=sa.text("nextval('billing_order_code_seq')")),
        sa.Column("incarnation_id", sa.Uuid(), sa.ForeignKey("account_incarnations.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("gateway", sa.String(40), nullable=False),
        sa.Column("plan_id", sa.String(40), nullable=False),
        sa.Column("period", sa.String(10), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("external_reference", sa.String(200), nullable=True),
        sa.Column("state", sa.String(20), nullable=False, server_default="created"),
        sa.Column("paid_event_id", sa.String(200), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_sequence", sa.Integer(), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refund_note", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(f"state IN ({', '.join(repr(s) for s in STATES)})", name="ck_billing_order_state"),
        sa.CheckConstraint("period IN ('month', 'year')", name="ck_billing_order_period"),
        sa.CheckConstraint("amount_minor > 0", name="ck_billing_order_amount"),
        sa.CheckConstraint("(state IN ('paid', 'refunded')) = (paid_at IS NOT NULL)", name="ck_billing_order_paid_at"),
        sa.UniqueConstraint("incarnation_id", "paid_sequence", name="uq_billing_order_paid_sequence"),
    )
    op.create_index("ix_billing_orders_gateway_reference", "billing_orders", ["gateway", "external_reference"],
                    unique=True, postgresql_where=sa.text("external_reference IS NOT NULL"))
    op.create_index("ix_billing_orders_incarnation", "billing_orders", ["incarnation_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_billing_orders_incarnation", table_name="billing_orders")
    op.drop_index("ix_billing_orders_gateway_reference", table_name="billing_orders")
    op.drop_table("billing_orders")
    op.execute("DROP SEQUENCE IF EXISTS billing_order_code_seq")
