"""Billing orders (proposed migration 20261005_0027; proposals/BILLING_GATEWAYS.md).

PROPOSED, INACTIVE: the table is a proposal until the human authorizes it, and no route accepts a payment until
BILLING_ENABLED is on with keys and prices (human gates).

An order binds one checkout attempt - incarnation, approved price, operation id - to the gateway's reference.
For a domestic gateway the paid order is also the payment fact the prepaid subscription is derived from:

- `mark_paid()` locks the incarnation `FOR NO KEY UPDATE` (serializing every payment and refund of that
  account, and a deletion), then the order; checks the amount, currency and payment link against the order;
  assigns the next `paid_sequence`; and stores `period_end`, the end of access this payment produced at the time
  (an audit fact: after a refund the replay, not this column, is the account's access).
- `prepaid_state()` replays the account's paid, unrefunded orders in sequence (billing/prepaid.py): the end of
  access, the plan of the latest order, and a version that only grows (paid orders + refunds). The caller hands
  that state to the commerce repository's `record_event()`; a replay or an out-of-order apply is a duplicate or
  `stale` there, and re-applying after a crash between the two writes gives the same state, never a guess.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from writing_coach.billing.prepaid import extended_until

_ORDER_COLUMNS = (
    "id, operation_id, order_code, incarnation_id, gateway, plan_id, period, currency, amount_minor, "
    "external_reference, state, paid_event_id, paid_at, paid_sequence, period_end, refunded_at, created_at"
)


class PostgresBillingRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # ---- checkout -----------------------------------------------------------------------------------------

    def create_order(self, *, operation_id: str, incarnation_id: str, gateway: str, plan_id: str, period: str,
                     currency: str, amount_minor: int) -> dict[str, Any]:
        """The order for this operation: new, or the one already made by the same operation. The same operation
        id with a different price, gateway or account is a conflict, never a second order."""

        now = datetime.now(UTC)
        values = {"id": uuid.uuid4(), "op": operation_id, "inc": incarnation_id, "gateway": gateway, "plan": plan_id,
                  "period": period, "currency": currency, "amount": int(amount_minor), "now": now}  # fmt: skip
        with self._engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO billing_orders (id, operation_id, incarnation_id, gateway, plan_id, period, currency, "
                "amount_minor, state, created_at, updated_at) VALUES (:id, :op, :inc, :gateway, :plan, :period, "
                ":currency, :amount, 'created', :now, :now) ON CONFLICT (operation_id) DO NOTHING"), values)
            row = connection.execute(text(f"SELECT {_ORDER_COLUMNS} FROM billing_orders WHERE operation_id = :op"),
                                     {"op": operation_id}).mappings().one()
        order = dict(row)
        same = (str(order["incarnation_id"]) == str(incarnation_id) and order["gateway"] == gateway
                and order["plan_id"] == plan_id and order["period"] == period and order["currency"] == currency
                and int(order["amount_minor"]) == int(amount_minor))  # fmt: skip
        order["conflict"] = not same
        return order

    def set_reference(self, order_id: Any, external_reference: str) -> None:
        with self._engine.begin() as connection:
            connection.execute(text(
                "UPDATE billing_orders SET external_reference = :ref, state = 'pending', updated_at = :now "
                "WHERE id = :id AND state IN ('created', 'pending')"),
                {"ref": external_reference, "id": order_id, "now": datetime.now(UTC)})

    def order(self, *, order_code: int | None = None, operation_id: str | None = None) -> dict[str, Any] | None:
        column, value = ("order_code", order_code) if order_code is not None else ("operation_id", operation_id)
        with self._engine.connect() as connection:
            row = connection.execute(text(f"SELECT {_ORDER_COLUMNS} FROM billing_orders WHERE {column} = :value"),
                                     {"value": value}).mappings().first()
        return dict(row) if row else None

    # ---- domestic prepaid payments ------------------------------------------------------------------------

    def mark_paid(self, *, order_code: int, event_id: str, amount_minor: int | None, currency: str | None,
                  payment_link_id: str = "", now: datetime | None = None) -> dict[str, Any]:
        """Record one verified payment of one order. Returns {'status': ...} with
        `applied` (newly paid), `duplicate` (already paid by this event), `unknown_order`, `mismatch` (amount or
        currency differs: nothing changes, an operator looks), or `not_payable` (refunded, or paid by another
        event), or `paid_deleted_account` (the money arrived for an account deleted since checkout: the order is
        recorded paid so the money is accounted for, nothing is granted, and an operator refunds it), plus the
        order's incarnation."""

        moment = now or datetime.now(UTC)
        with self._engine.begin() as connection:
            found = connection.execute(text(
                "SELECT incarnation_id FROM billing_orders WHERE order_code = :code"), {"code": order_code}).first()
            if found is None:
                return {"status": "unknown_order"}
            incarnation = found[0]
            # NO KEY UPDATE: serializes this account's payments, refunds and deletion (mark_deleted's UPDATE,
            # record_event's FOR SHARE) without blocking inserts that only reference the row.
            status = connection.execute(text(
                "SELECT status FROM account_incarnations WHERE id = :inc FOR NO KEY UPDATE"), {"inc": incarnation}).scalar_one()
            order = connection.execute(text(f"SELECT {_ORDER_COLUMNS} FROM billing_orders WHERE order_code = :code "
                                            "FOR UPDATE"), {"code": order_code}).mappings().one()
            result = {"incarnation_id": str(incarnation), "order_code": order_code}
            if order["state"] == "paid":
                return {**result, "status": "duplicate" if order["paid_event_id"] == event_id else "not_payable"}
            if order["state"] not in ("created", "pending", "expired", "cancelled"):
                return {**result, "status": "not_payable"}
            if amount_minor != int(order["amount_minor"]) or (currency or "").upper() != order["currency"]:
                return {**result, "status": "mismatch"}
            if payment_link_id and order["external_reference"] and payment_link_id != order["external_reference"]:
                return {**result, "status": "mismatch"}  # a payment of another link under the same order code
            chain = self._chain(connection, incarnation, gateway=order["gateway"])
            end = extended_until(chain["paid_through"], moment, order["period"])
            sequence = connection.execute(text(
                "SELECT COALESCE(MAX(paid_sequence), 0) + 1 FROM billing_orders WHERE incarnation_id = :inc"),
                {"inc": incarnation}).scalar_one()
            connection.execute(text(
                "UPDATE billing_orders SET state = 'paid', paid_event_id = :event, paid_at = :now, "
                "paid_sequence = :seq, period_end = :end, updated_at = :now WHERE order_code = :code"),
                {"event": event_id, "now": moment, "seq": sequence, "end": end, "code": order_code})
        return {**result, "status": "applied" if status == "active" else "paid_deleted_account"}

    def mark_refunded(self, *, order_code: int, note: str, now: datetime | None = None) -> dict[str, Any]:
        """An operator's record that a paid order's money was returned (payOS has no refund API: the money goes
        back by bank transfer). The order stops counting; access is recomputed from what remains."""

        moment = now or datetime.now(UTC)
        with self._engine.begin() as connection:
            found = connection.execute(text(
                "SELECT incarnation_id FROM billing_orders WHERE order_code = :code"), {"code": order_code}).first()
            if found is None:
                return {"status": "unknown_order"}
            connection.execute(text("SELECT id FROM account_incarnations WHERE id = :inc FOR NO KEY UPDATE"),
                               {"inc": found[0]})
            state = connection.execute(text("SELECT state FROM billing_orders WHERE order_code = :code FOR UPDATE"),
                                       {"code": order_code}).scalar_one()
            if state == "refunded":
                # Already recorded: the caller syncs access again, which repairs a crash between the two writes.
                return {"status": "already_refunded", "incarnation_id": str(found[0])}
            if state != "paid":
                return {"status": "not_refundable", "incarnation_id": str(found[0])}
            connection.execute(text(
                "UPDATE billing_orders SET state = 'refunded', refunded_at = :now, refund_note = :note, "
                "updated_at = :now WHERE order_code = :code"), {"now": moment, "note": note[:200], "code": order_code})
        return {"status": "applied", "incarnation_id": str(found[0])}

    def prepaid_state(self, incarnation_id: str, gateway: str) -> dict[str, Any]:
        with self._engine.connect() as connection:
            return self._chain(connection, incarnation_id, gateway=gateway)

    @staticmethod
    def _chain(connection, incarnation_id: Any, *, gateway: str | None = None) -> dict[str, Any]:
        """The account's prepaid access, replayed from its orders: each unrefunded paid order extends from its
        own payment time, in sequence (the same arithmetic `mark_paid` used, so the replay reproduces it)."""

        rows = connection.execute(text(
            "SELECT plan_id, period, paid_at, state, gateway FROM billing_orders "
            "WHERE incarnation_id = :inc AND paid_sequence IS NOT NULL ORDER BY paid_sequence"),
            {"inc": incarnation_id}).mappings().all()
        end, plan, refunds = None, None, 0
        for row in rows:
            if gateway is not None and row["gateway"] != gateway:
                continue
            if row["state"] == "refunded":
                refunds += 1
                continue
            end = extended_until(end, row["paid_at"], row["period"])
            plan = row["plan_id"]
        paid = sum(1 for row in rows if gateway is None or row["gateway"] == gateway)
        return {"paid_through": end, "plan_id": plan, "version": paid + refunds}
