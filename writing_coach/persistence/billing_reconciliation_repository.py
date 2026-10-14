"""Billing reconciliation items (proposed migration 20261014_0031; docs/billing/PR-MON-3_DESIGN.md §4.2).

One durable row per money anomaly. A verified money event is acknowledged only once it is recorded here (or as an
order or a receipt), so nothing that moved money is ever only a log line.

- `record()` is idempotent on (kind, gateway, dedupe key): a replay raises `occurrences`; a critical item whose
  condition is seen again goes back to `open` (`reopened` + 1).
- `resolve()` applies each kind's own rule (`RESOLUTION_RULES`). The database enforces the safety-critical part of
  it too (CHECKs and a trigger), so the rule holds even for a writer that bypasses this class.
- Provider facts are stored as reported, never as a foreign key; Orena's links are set only when matched.

Nothing here moves money or changes access: a refund, a grant or a revoke is its own recorded operation.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

CRITICAL = frozenset({"entitlement_unsynced", "provider_paid_unrecorded"})
MONEY = frozenset({"paid_deleted_account", "payment_unknown_order", "payment_mismatch", "payment_not_payable"})
DISMISSABLE = frozenset({"event_undecided", "provider_refund", "provider_state_unresolved"})
KINDS = CRITICAL | MONEY | DISMISSABLE
RECONCILER = "reconciler"

# What closes each kind (design §4.2): the outcomes an administrator may give, and whether a reference is required
# with them. `entitlement_unsynced` has none: only the reconciler closes it, once access was really granted.
_MONEY_OUTCOMES = {"payment_matched": True, "refund_confirmed": True, "obligation_waived": False}
RESOLUTION_RULES: dict[str, dict[str, bool]] = {
    "entitlement_unsynced": {},
    "provider_paid_unrecorded": {"payment_recorded": True, "refund_confirmed": True, "reversal_confirmed": True},
    "paid_deleted_account": {"refund_confirmed": True, "obligation_waived": False},
    "payment_unknown_order": dict(_MONEY_OUTCOMES),
    "payment_mismatch": dict(_MONEY_OUTCOMES),
    "payment_not_payable": dict(_MONEY_OUTCOMES),
    "event_undecided": {"recorded": False},
    "provider_refund": {"recorded": False, "refund_confirmed": True},
    "provider_state_unresolved": {"recorded": False, "payment_recorded": True, "refund_confirmed": True},
}

_COLUMNS = (
    "id, kind, gateway, dedupe_key, external_event_id, reported_order_code, reported_amount_minor, reported_currency, "
    "provider_state, reason, billing_order_id, incarnation_id, state, resolution_outcome, resolution_reference, "
    "resolution_note, resolved_by, resolved_at, reopened, occurrences, first_seen_at, last_seen_at"
)


class ResolutionRefused(Exception):
    """A resolution the item's kind does not allow; `code` is said to the administrator as is."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def check_resolution(kind: str, *, resolution: str, outcome: str | None, reference: str | None, note: str) -> None:
    """Raise `ResolutionRefused` unless an administrator may close an item of `kind` this way."""

    if not note.strip():
        raise ResolutionRefused("note_required")
    if resolution == "dismissed":
        if kind not in DISMISSABLE:
            raise ResolutionRefused("not_dismissable")
        return
    if resolution != "resolved":
        raise ResolutionRefused("resolution_invalid")
    allowed = RESOLUTION_RULES.get(kind, {})
    if not allowed:
        raise ResolutionRefused("reconciler_only")
    if outcome not in allowed:
        raise ResolutionRefused("outcome_not_allowed")
    if allowed[outcome] and not (reference or "").strip():
        raise ResolutionRefused("reference_required")


class PostgresReconciliationRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def record(self, *, kind: str, gateway: str, dedupe_key: str, external_event_id: str | None = None,
               reported_order_code: int | None = None, reported_amount_minor: int | None = None,
               reported_currency: str | None = None, provider_state: str | None = None,
               payload_digest: str | None = None, reason: str | None = None, billing_order_id: Any = None,
               incarnation_id: Any = None, now: datetime | None = None) -> dict[str, Any]:
        """The item for this anomaly, new or seen again. Committed when this returns; raises when it cannot be."""

        if kind not in KINDS:
            raise ValueError(f"unknown reconciliation kind {kind!r}")
        moment = now or datetime.now(UTC)
        values = {
            "id": uuid.uuid4(), "kind": kind, "gateway": gateway, "key": dedupe_key[:200],
            "event": external_event_id, "code": reported_order_code, "amount": reported_amount_minor,
            "currency": (reported_currency or None) and reported_currency[:3], "pstate": (provider_state or None) and provider_state[:60],
            "digest": payload_digest, "reason": (reason or None) and reason[:400],
            "order": billing_order_id, "inc": incarnation_id, "now": moment, "critical": kind in CRITICAL,
        }  # fmt: skip
        with self._engine.begin() as connection:
            row = connection.execute(text(
                "INSERT INTO billing_reconciliation_items AS item (id, kind, gateway, dedupe_key, external_event_id, "
                "reported_order_code, reported_amount_minor, reported_currency, provider_state, payload_digest, reason, "
                "billing_order_id, incarnation_id, state, first_seen_at, last_seen_at) VALUES (:id, :kind, :gateway, "
                ":key, :event, :code, :amount, :currency, :pstate, :digest, :reason, :order, :inc, 'open', :now, :now) "
                "ON CONFLICT (kind, gateway, dedupe_key) DO UPDATE SET "
                "occurrences = item.occurrences + 1, last_seen_at = :now, "
                # A critical condition seen again reopens its item; anything else only counts the repeat.
                "state = CASE WHEN :critical AND item.state <> 'open' THEN 'open' ELSE item.state END, "
                "reopened = CASE WHEN :critical AND item.state <> 'open' THEN item.reopened + 1 ELSE item.reopened END, "
                + ", ".join(f"{column} = CASE WHEN :critical AND item.state <> 'open' THEN NULL ELSE item.{column} END"
                            for column in ("resolution_outcome", "resolution_reference", "resolution_note",
                                           "resolved_by", "resolved_at"))
                + ", provider_state = CASE WHEN item.state = 'open' OR :critical THEN COALESCE(:pstate, item.provider_state) "
                "ELSE item.provider_state END, "
                "reason = CASE WHEN item.state = 'open' OR :critical THEN COALESCE(:reason, item.reason) ELSE item.reason END, "
                "billing_order_id = CASE WHEN item.state = 'open' OR :critical THEN COALESCE(item.billing_order_id, :order) "
                "ELSE item.billing_order_id END, "
                "incarnation_id = CASE WHEN item.state = 'open' OR :critical THEN COALESCE(item.incarnation_id, :inc) "
                "ELSE item.incarnation_id END "
                f"RETURNING {_COLUMNS}"), values).mappings().one()  # fmt: skip
        return dict(row)

    def resolve(self, item_id: Any, *, resolution: str, outcome: str | None, reference: str | None, note: str,
                actor: str, now: datetime | None = None) -> dict[str, Any]:
        """An administrator closes an open item, under its kind's rule. Moves no money and changes no access."""

        if actor == RECONCILER:
            raise ResolutionRefused("reconciler_only")
        with self._engine.begin() as connection:
            row = connection.execute(text(f"SELECT {_COLUMNS} FROM billing_reconciliation_items WHERE id = :id FOR UPDATE"),
                                     {"id": item_id}).mappings().first()  # fmt: skip
            if row is None:
                raise LookupError("item_not_found")
            if row["state"] != "open":
                raise ResolutionRefused("not_open")
            check_resolution(row["kind"], resolution=resolution, outcome=outcome, reference=reference, note=note)
            return self._close(connection, item_id, state=resolution, outcome=outcome if resolution == "resolved" else None,
                               reference=reference, note=note, actor=actor, now=now or datetime.now(UTC))  # fmt: skip

    def auto_resolve(self, *, kind: str, gateway: str, dedupe_key: str, outcome: str, note: str,
                     now: datetime | None = None) -> bool:
        """The reconciler closes an open item whose condition it has seen end. True when one was closed."""

        with self._engine.begin() as connection:
            row = connection.execute(text(
                "SELECT id FROM billing_reconciliation_items WHERE kind = :kind AND gateway = :gateway "
                "AND dedupe_key = :key AND state = 'open' FOR UPDATE"),
                {"kind": kind, "gateway": gateway, "key": dedupe_key}).first()  # fmt: skip
            if row is None:
                return False
            self._close(connection, row[0], state="resolved", outcome=outcome, reference=None, note=note,
                        actor=RECONCILER, now=now or datetime.now(UTC))  # fmt: skip
            return True

    @staticmethod
    def _close(connection, item_id: Any, *, state: str, outcome: str | None, reference: str | None, note: str,
               actor: str, now: datetime) -> dict[str, Any]:
        return dict(connection.execute(text(
            "UPDATE billing_reconciliation_items SET state = :state, resolution_outcome = :outcome, "
            "resolution_reference = :reference, resolution_note = :note, resolved_by = :actor, resolved_at = :now "
            f"WHERE id = :id RETURNING {_COLUMNS}"),
            {"state": state, "outcome": outcome, "reference": (reference or "").strip()[:200] or None,
             "note": note.strip()[:400], "actor": actor[:200], "now": now, "id": item_id}).mappings().one())  # fmt: skip

    def open_items(self, *, kind: str) -> list[dict[str, Any]]:
        with self._engine.connect() as connection:
            rows = connection.execute(text(
                f"SELECT {_COLUMNS} FROM billing_reconciliation_items WHERE state = 'open' AND kind = :kind "
                "ORDER BY first_seen_at"), {"kind": kind}).mappings().all()  # fmt: skip
        return [dict(row) for row in rows]

    def items(self, *, state: str | None = None, kind: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        clauses, values = [], {"limit": max(1, min(int(limit), 1000))}
        if state:
            clauses.append("state = :state")
            values["state"] = state
        if kind:
            clauses.append("kind = :kind")
            values["kind"] = kind
        where = f"WHERE {' AND '.join(clauses)} " if clauses else ""
        with self._engine.connect() as connection:
            rows = connection.execute(text(
                f"SELECT {_COLUMNS} FROM billing_reconciliation_items {where}ORDER BY first_seen_at DESC LIMIT :limit"),
                values).mappings().all()  # fmt: skip
        return [dict(row) for row in rows]

    def summary(self) -> dict[str, Any]:
        """Open items per kind, and the open critical ones per gateway (what blocks a gateway's readiness)."""

        with self._engine.connect() as connection:
            rows = connection.execute(text(
                "SELECT kind, gateway, COUNT(*) FROM billing_reconciliation_items WHERE state = 'open' "
                "GROUP BY kind, gateway")).all()  # fmt: skip
        by_kind: dict[str, int] = {}
        critical: dict[str, int] = {}
        for kind, gateway, count in rows:
            by_kind[kind] = by_kind.get(kind, 0) + int(count)
            if kind in CRITICAL:
                critical[gateway] = critical.get(gateway, 0) + int(count)
        return {"open": sum(by_kind.values()), "open_by_kind": by_kind, "critical_by_gateway": critical}

    def critical_by_gateway(self) -> Mapping[str, int]:
        return self.summary()["critical_by_gateway"]
