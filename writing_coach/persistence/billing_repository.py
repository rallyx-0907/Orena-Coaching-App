"""Billing orders (proposed migrations 20261005_0027 and 20261014_0031; proposals/BILLING_GATEWAYS.md,
docs/billing/PR-MON-3_DESIGN.md).

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
- A domestic order is the unit of payment (PR-MON-3): it is paid once. A second verified fact for a paid order with
  the same money and link is a duplicate, whichever source came first (webhook or the reconciler's lookup), unless
  both name a transaction reference and they differ - then it is a second, real payment (`not_payable`).
- The reconciler's state per order (0031): when payOS was last asked, what it answered, when to ask again, and
  whether the provider's outcome is settled. A local expiry never settles it; only a successful lookup does.
- `prepaid_gaps()` finds the accounts whose paid orders are ahead of the access recorded for them (R-MON-002).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from writing_coach.billing.prepaid import extended_until

_ORDER_COLUMNS = (
    "id, operation_id, order_code, incarnation_id, gateway, plan_id, period, currency, amount_minor, "
    "external_reference, state, paid_event_id, paid_at, paid_sequence, period_end, refunded_at, created_at, "
    "expires_at, paid_reference, provider_status, provider_checked_at, next_lookup_at, lookup_attempts, "
    "provider_settled_at"
)
ORDER_TTL = timedelta(minutes=30)  # H5: an operational expiry, never when Orena stops looking for a payment


class PostgresBillingRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # ---- checkout -----------------------------------------------------------------------------------------

    def create_order(self, *, operation_id: str, incarnation_id: str, gateway: str, plan_id: str, period: str,
                     currency: str, amount_minor: int, ttl: timedelta = ORDER_TTL) -> dict[str, Any]:
        """The order for this operation: new, or the one already made by the same operation. The same operation
        id with a different price, gateway or account is a conflict, never a second order."""

        now = datetime.now(UTC)
        values = {"id": uuid.uuid4(), "op": operation_id, "inc": incarnation_id, "gateway": gateway, "plan": plan_id,
                  "period": period, "currency": currency, "amount": int(amount_minor), "now": now,
                  "expires": now + ttl}  # fmt: skip
        with self._engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO billing_orders (id, operation_id, incarnation_id, gateway, plan_id, period, currency, "
                "amount_minor, state, created_at, updated_at, expires_at) VALUES (:id, :op, :inc, :gateway, :plan, :period, "
                ":currency, :amount, 'created', :now, :now, :expires) ON CONFLICT (operation_id) DO NOTHING"), values)
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
                  payment_link_id: str = "", paid_reference: str | None = None, settled: bool = False,
                  now: datetime | None = None) -> dict[str, Any]:
        """Record one verified payment of one order. Returns {'status': ...} with
        `applied` (newly paid), `duplicate` (already paid by this event), `unknown_order`, `mismatch` (amount or
        currency differs: nothing changes, an operator looks), or `not_payable` (refunded, or paid by another
        event), or `paid_deleted_account` (the money arrived for an account deleted since checkout: the order is
        recorded paid so the money is accounted for, nothing is granted, and an operator refunds it), plus the
        order's incarnation and id.

        `settled` is the reconciler's own successful lookup (nothing left to confirm); a webhook's payment instead
        schedules one confirming lookup, which finds an overpayment a second transfer would leave."""

        moment = now or datetime.now(UTC)
        with self._engine.begin() as connection:
            found = connection.execute(text(
                "SELECT incarnation_id FROM billing_orders WHERE order_code = :code"), {"code": order_code}).first()
            if found is None:
                return {"status": "unknown_order"}
            incarnation = found[0]
            # NO KEY UPDATE: serializes this account's payments, refunds and deletion (mark_deleted's UPDATE,
            # record_event's FOR SHARE) without blocking inserts that only reference the row.
            owner = connection.execute(text(
                "SELECT status, deleted_at FROM account_incarnations WHERE id = :inc FOR NO KEY UPDATE"),
                {"inc": incarnation}).one()  # fmt: skip
            status = owner[0]
            order = connection.execute(text(f"SELECT {_ORDER_COLUMNS} FROM billing_orders WHERE order_code = :code "
                                            "FOR UPDATE"), {"code": order_code}).mappings().one()
            result = {"incarnation_id": str(incarnation), "order_code": order_code, "order_id": order["id"]}
            reference = (paid_reference or "").strip()[:200] or None
            same_money = amount_minor == int(order["amount_minor"]) and (currency or "").upper() == order["currency"]
            same_link = not (payment_link_id and order["external_reference"]
                             and payment_link_id != order["external_reference"])  # fmt: skip
            # A payment recorded for an account already deleted stays that on every retry (review P1-1): the
            # refund it owes is recorded again (idempotently) when the first record of it could not be written.
            repeat = ("paid_deleted_account" if owner[1] is not None and order["paid_at"] is not None
                      and order["paid_at"] >= owner[1] else "duplicate")  # fmt: skip
            if order["state"] in ("paid", "refunded") and order["paid_event_id"] == event_id:
                return {**result, "status": repeat}  # a redelivery of the payment already recorded
            if order["state"] == "paid":
                if not (same_money and same_link) or (reference and order["paid_reference"]
                                                      and reference != order["paid_reference"]):
                    return {**result, "status": "not_payable"}  # another payment for an order already paid
                # The same payment, seen from its other source (webhook after lookup, or lookup after webhook).
                connection.execute(text(
                    "UPDATE billing_orders SET paid_reference = COALESCE(paid_reference, :ref), "
                    "provider_settled_at = CASE WHEN :settled THEN :now ELSE provider_settled_at END, updated_at = :now "
                    "WHERE order_code = :code"), {"ref": reference, "settled": settled, "now": moment, "code": order_code})
                return {**result, "status": repeat}
            if order["state"] not in ("created", "pending", "expired", "cancelled"):
                return {**result, "status": "not_payable"}
            if not same_money:
                return {**result, "status": "mismatch"}
            if not same_link:
                return {**result, "status": "mismatch"}  # a payment of another link under the same order code
            chain = self._chain(connection, incarnation, gateway=order["gateway"])
            end = extended_until(chain["paid_through"], moment, order["period"])
            sequence = connection.execute(text(
                "SELECT COALESCE(MAX(paid_sequence), 0) + 1 FROM billing_orders WHERE incarnation_id = :inc"),
                {"inc": incarnation}).scalar_one()
            connection.execute(text(
                "UPDATE billing_orders SET state = 'paid', paid_event_id = :event, paid_at = :now, "
                "paid_sequence = :seq, period_end = :end, paid_reference = :ref, updated_at = :now, "
                # A lookup that saw it paid settles it; a webhook's payment is confirmed by one lookup now.
                "provider_settled_at = CASE WHEN :settled THEN :now ELSE NULL END, "
                "provider_status = CASE WHEN :settled THEN 'PAID' ELSE provider_status END, "
                "next_lookup_at = CASE WHEN :settled THEN next_lookup_at ELSE :now END "
                "WHERE order_code = :code"),
                {"event": event_id, "now": moment, "seq": sequence, "end": end, "code": order_code, "ref": reference,
                 "settled": settled})  # fmt: skip
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
                "refunded_by = 'operator', updated_at = :now WHERE order_code = :code"),
                {"now": moment, "note": note[:200], "code": order_code})
        return {"status": "applied", "incarnation_id": str(found[0])}

    # ---- the reconciler (PR-MON-3 §4.4-4.5): short transactions only, never one open across a provider call ----

    def pull_candidates(self, gateway: str, *, now: datetime, limit: int, min_age: timedelta) -> list[dict[str, Any]]:
        """The orders whose provider outcome is not settled and are due a lookup: unpaid ones older than `min_age`
        (a locally expired one too), and a webhook-paid one awaiting its confirming lookup - also once refunded,
        since the refund does not confirm what payOS received (review P1-3)."""

        with self._engine.connect() as connection:
            rows = connection.execute(text(
                f"SELECT {_ORDER_COLUMNS} FROM billing_orders WHERE gateway = :gateway AND provider_settled_at IS NULL "
                "AND state IN ('created', 'pending', 'expired', 'paid', 'refunded') "
                "AND (next_lookup_at IS NULL OR next_lookup_at <= :now) "
                "AND (state IN ('paid', 'refunded') OR created_at <= :cutoff) "
                "ORDER BY COALESCE(next_lookup_at, created_at) LIMIT :limit"),
                {"gateway": gateway, "now": now, "cutoff": now - min_age, "limit": int(limit)}).mappings().all()  # fmt: skip
        return [dict(row) for row in rows]

    def claim_lookup(self, order_id: Any, *, now: datetime, lease: timedelta) -> bool:
        """Take one order for a lookup: its next lookup moves past the lease, so no other tick reads it meanwhile.
        Committed before the provider is called."""

        with self._engine.begin() as connection:
            claimed = connection.execute(text(
                "UPDATE billing_orders SET next_lookup_at = :until WHERE id = :id AND provider_settled_at IS NULL "
                "AND (next_lookup_at IS NULL OR next_lookup_at <= :now) RETURNING id"),
                {"id": order_id, "now": now, "until": now + lease}).first()  # fmt: skip
        return claimed is not None

    def record_lookup(self, order_id: Any, *, status: str, now: datetime, next_at: datetime | None,
                      settled: bool) -> None:
        with self._engine.begin() as connection:
            connection.execute(text(
                "UPDATE billing_orders SET provider_status = :status, provider_checked_at = :now, "
                "next_lookup_at = :next, lookup_attempts = lookup_attempts + 1, "
                "provider_settled_at = CASE WHEN :settled THEN :now ELSE provider_settled_at END, updated_at = :now "
                "WHERE id = :id"),
                {"status": status[:30], "now": now, "next": next_at, "settled": settled, "id": order_id})  # fmt: skip

    def mark_cancelled(self, order_id: Any, *, now: datetime) -> bool:
        """The provider said the order was cancelled with nothing paid: it is closed and settled."""

        with self._engine.begin() as connection:
            changed = connection.execute(text(
                "UPDATE billing_orders SET state = 'cancelled', provider_settled_at = :now, updated_at = :now "
                "WHERE id = :id AND state IN ('created', 'pending', 'expired') RETURNING id"),
                {"id": order_id, "now": now}).first()  # fmt: skip
        return changed is not None

    def expire_abandoned(self, *, now: datetime) -> int:
        """An unpaid order past its expiry becomes `expired` - locally only: it is not settled, so the lookup keeps
        asking about it, and a verified late payment is still accepted."""

        with self._engine.begin() as connection:
            result = connection.execute(text(
                "UPDATE billing_orders SET state = 'expired', updated_at = :now "
                "WHERE state IN ('created', 'pending') AND expires_at <= :now"), {"now": now})  # fmt: skip
        return int(result.rowcount or 0)

    def prepaid_gaps(self, gateway: str) -> list[dict[str, Any]]:
        """Active accounts whose paid orders on `gateway` are ahead of the prepaid access recorded for them: the
        orders' version (paid orders + refunds, `_chain`) against the applied version of `prepaid:<account>`."""

        with self._engine.connect() as connection:
            rows = connection.execute(text(
                "SELECT o.incarnation_id, COUNT(*) + COUNT(*) FILTER (WHERE o.state = 'refunded') AS version, "
                "MAX(ps.object_version) AS applied FROM billing_orders o "
                "JOIN account_incarnations i ON i.id = o.incarnation_id AND i.status = 'active' "
                "LEFT JOIN commerce_provider_subscriptions ps ON ps.provider = o.gateway "
                "AND ps.external_subscription_id = 'prepaid:' || o.incarnation_id::text "
                "WHERE o.gateway = :gateway AND o.paid_sequence IS NOT NULL GROUP BY o.incarnation_id"),
                {"gateway": gateway}).mappings().all()  # fmt: skip
        return [{"incarnation_id": str(row["incarnation_id"]), "version": int(row["version"]),
                 "applied": None if row["applied"] is None else int(row["applied"])}
                for row in rows if row["applied"] is None or int(row["applied"]) < int(row["version"])]  # fmt: skip

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
