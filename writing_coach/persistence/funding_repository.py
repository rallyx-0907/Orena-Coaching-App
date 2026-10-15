"""Funding admissions on PostgreSQL (PR-MON-6, docs/billing/PR-MON-6_DESIGN.md §5.6; proposed migration 0034).

One row per admitted learner operation. Every write here is one short transaction that takes the admission row first
(the canonical order: admission -> incarnation FOR SHARE -> quota bucket | credit account), and writes the backing
reservation - a 0007 quota reservation or a PR-MON-4 credit hold, keyed `fund:<operation_id>` - in the same
transaction, through the quota and credit repositories' savepoint mode. The database guard of 0034 re-checks every
transition against that backing, so this code is never the only line of defence.

The source is chosen by the caller (`choose`), once: a retry of the same operation id with the same digest replays the
snapshot, a different digest is a conflict, and a terminal row never funds again. A refusal (no source) writes nothing,
as 0007's rejected reserve writes nothing: the same operation may be admitted later. `refused` is the reconciler's
state for a row left `admitting` with no exact backing.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from writing_coach.persistence.credit_repository import digest

TERMINAL = ("settled", "released", "refused")
OPEN = ("funded", "dispatched")
_COLUMNS = ("id, operation_id, incarnation_id, meter, units, operation_ref, feature, unit_granularity, request_digest, "
            "state, source, price_per_unit, amount_reserved, hold_ttl_seconds, policy_version, cost_gate_id, "
            "quota_reservation_id, credit_reserve_entry_id, settled_units, settled_amount, refusal_reason, created_at, "
            "funded_at, dispatched_at, closed_at")


def fund_key(operation_id: str) -> str:
    """The backing reservation's key: derived from the operation id alone, so the admission always finds it."""
    return f"fund:{operation_id}"


@dataclass(frozen=True)
class FundingIntent:
    """What the learner asked for (§5.4). The digest covers the intent, never the decision."""

    incarnation_id: str
    operation_id: str
    meter: str
    units: int
    operation_ref: str
    feature: str
    unit_granularity: int = 1

    @property
    def request_digest(self) -> str:
        return digest(kind="funding_admission", incarnation=self.incarnation_id, operation_id=self.operation_id,
                      meter=self.meter, units=self.units, operation_ref=self.operation_ref, feature=self.feature,
                      unit_granularity=self.unit_granularity)  # fmt: skip


@dataclass(frozen=True)
class Snapshot:
    """The funding decision, written once by `admitting -> funded` and never changed (§5.6)."""

    source: str                    # allowance | promotional | credits
    policy_version: str
    quota_reservation_id: str | None = None
    credit_reserve_entry_id: str | None = None
    price_per_unit: int | None = None
    amount_reserved: int | None = None
    hold_ttl_seconds: int | None = None
    cost_gate_id: str | None = None


@dataclass(frozen=True)
class Refusal:
    """No source funds the operation: nothing is written. `facts` feed the §9 answer."""

    reason: str                    # allowance_exhausted | insufficient_credits | credits_unavailable | ...
    facts: dict[str, Any] = field(default_factory=dict)


@dataclass
class AdmissionOutcome:
    """`funded` (new or replayed), `refused`, `operation_conflict`, `operation_completed`, `operation_closed`."""

    status: str
    row: dict[str, Any] | None = None
    refusal: Refusal | None = None

    @property
    def funded(self) -> bool:
        return self.status == "funded"


class PostgresFundingRepository:
    def __init__(self, engine: Engine, *, quota: Any, credits: Any | None = None,
                 clock: Callable[[], datetime] | None = None) -> None:
        self._engine = engine
        self._quota = quota
        self._credits = credits
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def quota(self) -> Any:
        return self._quota

    @property
    def credits(self) -> Any:
        return self._credits

    # ---- reads ---------------------------------------------------------------------------------------------------

    def get(self, operation_id: str) -> dict[str, Any] | None:
        with self._engine.connect() as connection:
            row = connection.execute(text(f"SELECT {_COLUMNS} FROM funding_admissions WHERE operation_id = :op"),
                                     {"op": operation_id}).mappings().first()
        return dict(row) if row else None

    def live(self, operation_id: str, *, request_digest: str, meter: str, min_hold_seconds: float) -> str | None:
        """The live check before a paid outbound request (§2.1): None when the admission is funded or dispatched, its
        digest and meter match, and its backing is open - for a credit hold, unexpired with at least
        `min_hold_seconds` left. Otherwise the reason it fails, which the caller logs. One indexed read."""
        with self._engine.connect() as connection:
            row = connection.execute(text(
                "SELECT f.state, f.request_digest, f.meter, f.source, r.state AS quota_state, "
                "l.expires_at AS hold_expires_at, "
                "EXISTS (SELECT 1 FROM credit_ledger c WHERE c.ref_entry_id = f.credit_reserve_entry_id "
                "        AND c.kind IN ('settle', 'release', 'reserve_expire')) AS hold_closed, now() AS db_now "
                "FROM funding_admissions f "
                "LEFT JOIN commerce_quota_reservations r ON r.id = f.quota_reservation_id "
                "LEFT JOIN credit_ledger l ON l.id = f.credit_reserve_entry_id "
                "WHERE f.operation_id = :op"), {"op": operation_id}).mappings().first()
        if row is None:
            return "no_admission"
        if row["request_digest"] != request_digest:
            return "digest_mismatch"
        if row["meter"] != meter:
            return "meter_mismatch"
        if row["state"] not in OPEN:
            return f"admission_{row['state']}"
        if row["source"] == "credits":
            if row["hold_closed"]:
                return "hold_closed"
            left = (row["hold_expires_at"] - row["db_now"]).total_seconds()
            if left < min_hold_seconds:
                return "hold_expiring"
            return None
        if row["quota_state"] not in ("reserved", "dispatched"):
            return "quota_closed"
        return None

    def open_rows(self, *, states: tuple[str, ...], older_than: datetime, limit: int = 200) -> list[dict[str, Any]]:
        with self._engine.connect() as connection:
            rows = connection.execute(text(
                f"SELECT {_COLUMNS} FROM funding_admissions WHERE state = ANY(:states) AND created_at < :before "
                "ORDER BY created_at LIMIT :limit"),
                {"states": list(states), "before": older_than, "limit": int(limit)}).mappings().all()  # fmt: skip
        return [dict(row) for row in rows]

    # ---- admission ------------------------------------------------------------------------------------------------

    def admit(self, intent: FundingIntent, choose: Callable[[Any, dict[str, Any]], Snapshot | Refusal]
              ) -> AdmissionOutcome:
        """§5.6 serialization: insert ON CONFLICT DO NOTHING, take the row FOR UPDATE, compare the digest, then -
        only while `admitting` - let `choose(connection, row)` pick the source and write its backing reservation in
        this same transaction (savepoints), and record the snapshot. A refusal rolls everything back."""
        now = self._clock()
        with self._engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.execute(text(
                    "INSERT INTO funding_admissions (id, operation_id, incarnation_id, meter, units, operation_ref, "
                    "feature, unit_granularity, request_digest, state, created_at) VALUES (:id, :op, :inc, :meter, "
                    ":units, :ref, :feature, :granularity, :digest, 'admitting', :now) "
                    "ON CONFLICT (operation_id) DO NOTHING"),
                    {"id": uuid.uuid4(), "op": intent.operation_id, "inc": intent.incarnation_id,
                     "meter": intent.meter, "units": intent.units, "ref": intent.operation_ref,
                     "feature": intent.feature, "granularity": intent.unit_granularity,
                     "digest": intent.request_digest, "now": now})  # fmt: skip
                row = dict(connection.execute(text(
                    f"SELECT {_COLUMNS} FROM funding_admissions WHERE operation_id = :op FOR UPDATE"),
                    {"op": intent.operation_id}).mappings().one())  # fmt: skip
                if row["request_digest"] != intent.request_digest:
                    transaction.rollback()
                    return AdmissionOutcome("operation_conflict")
                if row["state"] != "admitting":
                    transaction.rollback()
                    return _replay(row)
                decision = choose(connection, row)
                if isinstance(decision, Refusal):
                    transaction.rollback()  # nothing written: the operation may be admitted later
                    return AdmissionOutcome("refused", refusal=decision)
                connection.execute(text(
                    "UPDATE funding_admissions SET state = 'funded', source = :source, price_per_unit = :price, "
                    "amount_reserved = :amount, hold_ttl_seconds = :ttl, policy_version = :policy, "
                    "cost_gate_id = :gate, quota_reservation_id = :quota, credit_reserve_entry_id = :hold, "
                    "funded_at = :now WHERE operation_id = :op"),
                    {"source": decision.source, "price": decision.price_per_unit, "amount": decision.amount_reserved,
                     "ttl": decision.hold_ttl_seconds, "policy": decision.policy_version[:120],
                     "gate": decision.cost_gate_id, "quota": decision.quota_reservation_id,
                     "hold": decision.credit_reserve_entry_id, "now": now, "op": intent.operation_id})  # fmt: skip
                funded = dict(connection.execute(text(
                    f"SELECT {_COLUMNS} FROM funding_admissions WHERE operation_id = :op"),
                    {"op": intent.operation_id}).mappings().one())  # fmt: skip
                transaction.commit()
                return AdmissionOutcome("funded", row=funded)
            except BaseException:
                if transaction.is_active:
                    transaction.rollback()
                raise

    # ---- lifecycle ------------------------------------------------------------------------------------------------

    def dispatch(self, operation_id: str, *, ref: str = "dispatch") -> str:
        """`funded -> dispatched` (the first paid request), with the quota ticket's dispatch, in one transaction.
        Idempotent: `dispatched` already is `dispatched`."""
        with self._engine.begin() as connection:
            row = self._lock(connection, operation_id)
            if row is None:
                return "unknown_operation"
            if row["state"] == "dispatched":
                return "dispatched"
            if row["state"] != "funded":
                return f"admission_{row['state']}"
            if row["source"] != "credits":
                outcome = self._quota.dispatch(operation_id=fund_key(operation_id), dispatch_ref=ref[:200],
                                               connection=connection)  # fmt: skip
                if outcome.get("status") not in ("dispatch", "duplicate"):
                    return f"quota_{outcome.get('status')}"
            connection.execute(text("UPDATE funding_admissions SET state = 'dispatched', dispatched_at = :now "
                                    "WHERE operation_id = :op"), {"now": self._clock(), "op": operation_id})
            return "dispatched"

    def settle(self, operation_id: str, *, actual_units: int, outcome_ref: str | None = None) -> str:
        """Close with a result (§5.3): the charge comes only from the snapshot. `actual_units` 0 is a release.
        Idempotent per operation: a terminal row answers its state, never charges twice."""
        actual = int(actual_units)
        if actual <= 0:
            return self.release(operation_id)
        with self._engine.begin() as connection:
            row = self._lock(connection, operation_id)
            if row is None:
                return "unknown_operation"
            if row["state"] in TERMINAL:
                return row["state"]
            if row["state"] not in OPEN:
                return f"admission_{row['state']}"
            units = min(actual, int(row["units"]))
            now = self._clock()
            if row["source"] == "credits":
                amount = int(row["price_per_unit"]) * units
                outcome = self._credits.settle(str(row["incarnation_id"]), reserve_entry_id=row["credit_reserve_entry_id"],
                                               actual=amount, operation_id=f"{fund_key(operation_id)}:settle",
                                               connection=connection)  # fmt: skip
                if outcome.status == "reservation_closed":
                    # The hold expired first: never collected (C7); the admission is released, not settled.
                    self._close(connection, operation_id, "released", now)
                    return "released"
                if not outcome.ok:
                    raise RuntimeError(f"credit settle {operation_id}: {outcome.status}")
                self._close(connection, operation_id, "settled", now, units=units, amount=amount)
                return "settled"
            outcome = self._quota.settle(operation_id=fund_key(operation_id), actual_units=units,
                                         outcome_ref=(outcome_ref or None) and outcome_ref[:200],
                                         connection=connection)  # fmt: skip
            status = outcome.get("status")
            if status not in ("settle", "duplicate"):
                reservation = self._quota_state(connection, row)
                if reservation and reservation["state"] == "settled":
                    units = int(reservation["actual_units"])  # the reconciler settled it first: copy, never resettle
                elif reservation and reservation["state"] == "released":
                    self._close(connection, operation_id, "released", now)
                    return "released"
                else:
                    raise RuntimeError(f"quota settle {operation_id}: {status}")
            if units == 0:
                self._close(connection, operation_id, "released", now)
                return "released"
            self._close(connection, operation_id, "settled", now, units=units)
            return "settled"

    def release(self, operation_id: str, *, reason: str = "") -> str:
        """Close without a result (§5.3): the hold is released, the quota reservation released (or, once
        dispatched, settled at 0). Idempotent."""
        with self._engine.begin() as connection:
            row = self._lock(connection, operation_id)
            if row is None:
                return "unknown_operation"
            if row["state"] in TERMINAL:
                return row["state"]
            if row["state"] not in OPEN:
                return f"admission_{row['state']}"
            now = self._clock()
            if row["source"] == "credits":
                outcome = self._credits.release(str(row["incarnation_id"]), reserve_entry_id=row["credit_reserve_entry_id"],
                                                operation_id=f"{fund_key(operation_id)}:release", reason=reason[:400],
                                                connection=connection)  # fmt: skip
                if not (outcome.ok or outcome.status == "reservation_closed"):
                    raise RuntimeError(f"credit release {operation_id}: {outcome.status}")
            else:
                reservation = self._quota_state(connection, row)
                if reservation is None:
                    raise RuntimeError(f"quota reservation of {operation_id} is missing")
                if reservation["state"] == "reserved":
                    self._quota.release(operation_id=fund_key(operation_id), connection=connection)
                elif reservation["state"] == "dispatched":
                    self._quota.settle(operation_id=fund_key(operation_id), actual_units=0, outcome_ref="released",
                                       connection=connection)  # fmt: skip
                reservation = self._quota_state(connection, row)
                if reservation["state"] == "settled" and int(reservation["actual_units"]) > 0:
                    # Settled by someone else (H-6 abandonment) before this release: copy, never undo a charge.
                    self._close(connection, operation_id, "settled", now, units=int(reservation["actual_units"]))
                    return "settled"
            self._close(connection, operation_id, "released", now)
            return "released"

    def refuse(self, operation_id: str, *, reason: str) -> str:
        """`admitting -> refused` (the reconciler): the guard allows it only while no open, exact backing exists."""
        with self._engine.begin() as connection:
            row = self._lock(connection, operation_id)
            if row is None:
                return "unknown_operation"
            if row["state"] != "admitting":
                return row["state"]
            connection.execute(text("UPDATE funding_admissions SET state = 'refused', refusal_reason = :reason, "
                                    "closed_at = :now WHERE operation_id = :op"),
                               {"reason": reason[:40], "now": self._clock(), "op": operation_id})  # fmt: skip
            return "refused"

    def complete_from_backing(self, operation_id: str) -> str:
        """The reconciler (§5.6 crash table): a funded/dispatched row whose backing already closed is completed from
        the backing's terminal state, copying its amounts; it never re-settles. Answers the new state or `open`."""
        with self._engine.begin() as connection:
            row = self._lock(connection, operation_id)
            if row is None or row["state"] not in OPEN:
                return "unchanged"
            now = self._clock()
            if row["source"] == "credits":
                close = connection.execute(text(
                    "SELECT kind, posted_delta FROM credit_ledger WHERE ref_entry_id = :hold "
                    "AND kind IN ('settle', 'release', 'reserve_expire')"),
                    {"hold": row["credit_reserve_entry_id"]}).mappings().first()  # fmt: skip
                if close is None:
                    return "open"
                charged = -int(close["posted_delta"]) if close["kind"] == "settle" else 0
                price = int(row["price_per_unit"])
                if charged > 0 and charged % price == 0:
                    self._close(connection, operation_id, "settled", now, units=charged // price, amount=charged)
                    return "settled"
                if charged > 0:
                    return "inconsistent"   # left open; the 0034 guard would refuse any other completion
                self._close(connection, operation_id, "released", now)
                return "released"
            reservation = self._quota_state(connection, row)
            if reservation is None or reservation["state"] in ("reserved", "dispatched"):
                return "open"
            if reservation["state"] == "settled" and int(reservation["actual_units"]) > 0:
                self._close(connection, operation_id, "settled", now, units=int(reservation["actual_units"]))
                return "settled"
            self._close(connection, operation_id, "released", now)
            return "released"

    def exact_backing(self, row: dict[str, Any]) -> dict[str, Any] | None:
        """An open backing keyed `fund:<op>` exact for this admitting row (the 0034 guard's own definition), in either
        store; None when there is none. Used by the reconciler before it refuses."""
        key = fund_key(row["operation_id"])
        with self._engine.connect() as connection:
            hold = connection.execute(text(
                "SELECT l.id, l.amount FROM credit_ledger l JOIN credit_accounts a ON a.id = l.credit_account_id "
                "WHERE a.incarnation_id = :inc AND l.kind = 'reserve' AND l.idempotency_key = :key "
                "AND l.meter = :meter AND l.operation_ref = :ref AND NOT EXISTS (SELECT 1 FROM credit_ledger c "
                "WHERE c.ref_entry_id = l.id AND c.kind IN ('settle', 'release', 'reserve_expire'))"),
                {"inc": row["incarnation_id"], "key": key, "meter": row["meter"],
                 "ref": row["operation_ref"]}).mappings().first()  # fmt: skip
            if hold is not None:
                return {"store": "credits", **dict(hold)}
            reservation = connection.execute(text(
                "SELECT r.id FROM commerce_quota_reservations r JOIN commerce_quota_buckets b ON b.id = r.bucket_id "
                "WHERE r.operation_id = :key AND r.admitted_units = :units AND r.state IN ('reserved', 'dispatched') "
                "AND b.incarnation_id = :inc AND b.meter = :meter"),
                {"key": key, "units": row["units"], "inc": row["incarnation_id"],
                 "meter": row["meter"]}).mappings().first()  # fmt: skip
        return {"store": "quota", **dict(reservation)} if reservation is not None else None

    def stray_open(self, operation_id: str) -> bool:
        """Anything keyed `fund:<op>` still open, in any credit account or the quota reservations (review P1-2)."""
        key = fund_key(operation_id)
        with self._engine.connect() as connection:
            return bool(connection.execute(text(
                "SELECT EXISTS (SELECT 1 FROM credit_ledger l WHERE l.kind = 'reserve' AND l.idempotency_key = :key "
                "AND NOT EXISTS (SELECT 1 FROM credit_ledger c WHERE c.ref_entry_id = l.id "
                "AND c.kind IN ('settle', 'release', 'reserve_expire'))) "
                "OR EXISTS (SELECT 1 FROM commerce_quota_reservations r WHERE r.operation_id = :key "
                "AND r.state IN ('reserved', 'dispatched'))"), {"key": key}).scalar())  # fmt: skip

    # ---- funding_admission_conflict (critical, reconciler-only; 0034) -------------------------------------------------

    def open_conflict(self, row: dict[str, Any], *, reason: str) -> None:
        """A non-exact reservation keyed `fund:<op>` was never adopted: one item per admission (re-seen, counted)."""
        now = self._clock()
        with self._engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO billing_reconciliation_items AS item (id, kind, gateway, dedupe_key, reason, incarnation_id, "
                "funding_admission_id, state, first_seen_at, last_seen_at) VALUES (:id, 'funding_admission_conflict', "
                "'funding', :key, :reason, :inc, :admission, 'open', :now, :now) "
                "ON CONFLICT (kind, gateway, dedupe_key) DO UPDATE SET occurrences = item.occurrences + 1, "
                "last_seen_at = :now"),
                {"id": uuid.uuid4(), "key": str(row["id"]), "reason": reason[:400], "inc": row["incarnation_id"],
                 "admission": row["id"], "now": now})  # fmt: skip

    def open_conflicts(self, *, limit: int = 200) -> list[dict[str, Any]]:
        with self._engine.connect() as connection:
            rows = connection.execute(text(
                "SELECT i.id, f.operation_id FROM billing_reconciliation_items i "
                "JOIN funding_admissions f ON f.id = i.funding_admission_id "
                "WHERE i.kind = 'funding_admission_conflict' AND i.state = 'open' ORDER BY i.first_seen_at "
                "LIMIT :limit"), {"limit": int(limit)}).mappings().all()  # fmt: skip
        return [dict(row) for row in rows]

    def resolve_conflict(self, item_id: Any) -> None:
        """`stray_released`: the item guard re-checks that nothing keyed `fund:<op>` is still open, anywhere."""
        with self._engine.begin() as connection:
            connection.execute(text(
                "UPDATE billing_reconciliation_items SET state = 'resolved', resolution_outcome = 'stray_released', "
                "resolved_by = 'reconciler', resolved_at = :now, resolution_note = 'nothing keyed fund:<op> is open' "
                "WHERE id = :id AND state = 'open'"), {"now": self._clock(), "id": item_id})  # fmt: skip

    # ---- helpers --------------------------------------------------------------------------------------------------

    @staticmethod
    def _lock(connection, operation_id: str) -> dict[str, Any] | None:
        row = connection.execute(text(f"SELECT {_COLUMNS} FROM funding_admissions WHERE operation_id = :op FOR UPDATE"),
                                 {"op": operation_id}).mappings().first()
        return dict(row) if row else None

    @staticmethod
    def _quota_state(connection, row: dict[str, Any]) -> dict[str, Any] | None:
        found = connection.execute(text("SELECT state, actual_units FROM commerce_quota_reservations WHERE id = :id"),
                                   {"id": row["quota_reservation_id"]}).mappings().first()
        return dict(found) if found else None

    @staticmethod
    def _close(connection, operation_id: str, state: str, now: datetime, *, units: int | None = None,
               amount: int | None = None) -> None:
        connection.execute(text(
            "UPDATE funding_admissions SET state = :state, settled_units = :units, settled_amount = :amount, "
            "closed_at = :now WHERE operation_id = :op"),
            {"state": state, "units": units, "amount": amount, "now": now, "op": operation_id})  # fmt: skip


def _replay(row: dict[str, Any]) -> AdmissionOutcome:
    """A retry of an operation already decided (§5.4): its snapshot, or 409 when it is over."""
    if row["state"] in OPEN:
        return AdmissionOutcome("funded", row=row)
    if row["state"] == "settled":
        return AdmissionOutcome("operation_completed", row=row)
    return AdmissionOutcome("operation_closed", row=row)


def hold_ttl(row: dict[str, Any]) -> timedelta | None:
    return timedelta(seconds=int(row["hold_ttl_seconds"])) if row.get("hold_ttl_seconds") else None
