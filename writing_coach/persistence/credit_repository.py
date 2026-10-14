"""The prepaid credit ledger (proposed migration 20261014_0032; docs/billing/PR-MON-4_DESIGN.md, APPROVED).

Every operation is one short transaction, in one lock order: the account incarnation (`FOR SHARE`, against a
deletion), then the credit account (`FOR UPDATE`, which serializes every credit mutation of that account). Then the
idempotency lookup, the decision, and one INSERT into the ledger; the database's own trigger applies the deltas to
the snapshot, assigns the sequence and enforces every cap, so a decision this code got wrong still cannot make a
balance negative, double-close a hold or over-refund.

- A replay (same key, same digest) returns the original entry; the same key with another intent is a `conflict`.
- The digest is over the request's intent (§6), never over a derived result.
- A reversal is decided once (`credit_reversal_requests`), never re-evaluated on a replay (P1-3).
- No provider is called here, and nothing here sets a balance: there is no such operation.
- PR-MON-5 (design revision 3, migration 0033): a paid credit-pack order is credited by `apply_credit_topup` - one
  transaction in the canonical lock order (incarnation -> the order -> the credit account) that re-reads the order
  under its lock, so a refund that won the race is seen and nothing is credited. Fulfillment is an **exact** match
  (kind, source, the order's account, the snapshot units, the intent digest); a conflicting source never counts.
  A refunded order's credit is taken back by `reverse_credit_topup` (C5), and a reversal counts only when its whole
  durable result exists (the request, its entry, its shortfall item).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

HOLD_TTL = timedelta(minutes=30)  # C7: the default; a stored `expires_at` is authoritative
CREDITS_GATEWAY = "credits"
_ENTRY_COLUMNS = (
    "id, credit_account_id, seq, kind, posted_delta, reserved_delta, amount, ref_entry_id, reversal_request_id, "
    "idempotency_key, request_digest, source_type, source_ref, meter, operation_ref, expires_at, uncharged, actor, "
    "reason, created_at"
)
_ENTRY_COLUMNS_L = ", ".join("l." + column.strip() for column in _ENTRY_COLUMNS.split(","))
_REQUEST_COLUMNS = (
    "id, credit_account_id, topup_entry_id, idempotency_key, request_digest, requested, applied, shortfall, "
    "source_type, source_ref, actor, reason, created_at"
)


def digest(**intent: Any) -> str:
    """sha256 over the request's semantic inputs, canonically ordered (§6)."""

    canonical = json.dumps({key: (str(value) if value is not None else None) for key, value in intent.items()},
                           sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _digest_sql(fields: list[tuple[str, str]]) -> str:
    """`digest()` recomputed in SQL: sha256 of the canonical JSON (sorted keys, string values, no spaces). The
    values used here are ASCII only (UUIDs, integers, `payos:<code>`), so the JSON needs no escaping."""

    parts = ['"' + key + '":"\' || (' + expression + ")::text || '\"" for key, expression in sorted(fields)]
    return "encode(sha256(convert_to('{" + ",".join(parts) + "}', 'UTF8')), 'hex')"


ORDER_SOURCE = "o.gateway || ':' || o.order_code::text"
EXACT_TOPUP = (
    "EXISTS (SELECT 1 FROM credit_ledger l JOIN credit_accounts a ON a.id = l.credit_account_id "
    "WHERE l.kind = 'topup' AND l.source_type = 'billing_order' AND l.source_ref = " + ORDER_SOURCE + " "
    "AND a.incarnation_id = o.incarnation_id AND l.amount = o.credit_units AND l.request_digest = "
    + _digest_sql([("account", "a.incarnation_id"), ("amount", "o.credit_units"), ("kind", "'topup'"),
                   ("source_ref", ORDER_SOURCE), ("source_type", "'billing_order'")]) + ")")
COMPLETE_REVERSAL = (
    "EXISTS (SELECT 1 FROM credit_reversal_requests r JOIN credit_accounts a ON a.id = r.credit_account_id "
    "JOIN credit_ledger t ON t.id = r.topup_entry_id "
    "WHERE r.source_type = 'payos_refund' AND r.source_ref = " + ORDER_SOURCE + " "
    "AND a.incarnation_id = o.incarnation_id AND t.kind = 'topup' AND t.source_type = 'billing_order' "
    "AND t.source_ref = " + ORDER_SOURCE + " AND r.requested = o.credit_units AND r.request_digest = "
    + _digest_sql([("account", "a.incarnation_id"), ("kind", "'reversal'"), ("requested", "o.credit_units"),
                   ("source_ref", ORDER_SOURCE), ("source_type", "'payos_refund'"), ("topup", "r.topup_entry_id")])
    + " AND (r.applied = 0 OR (SELECT count(*) FROM credit_ledger e WHERE e.reversal_request_id = r.id "
    "AND e.kind = 'reversal' AND e.credit_account_id = r.credit_account_id AND e.ref_entry_id = r.topup_entry_id "
    "AND e.amount = r.applied) = 1) AND (r.shortfall = 0 OR EXISTS (SELECT 1 FROM billing_reconciliation_items s "
    "WHERE s.kind = 'credit_reversal_shortfall' AND s.dedupe_key = r.id::text AND s.credit_reversal_request_id = r.id "
    "AND s.credit_topup_entry_id = r.topup_entry_id AND s.credit_requested = r.requested "
    "AND s.credit_applied = r.applied AND s.credit_shortfall = r.shortfall)))")


# When a gap was last escalated: the reconciler works through the least recently seen gaps first (no starvation).
_LAST_ESCALATED = ("(SELECT max(g.last_seen_at) FROM billing_reconciliation_items g WHERE g.billing_order_id = o.id "
                   "AND g.kind = '{kind}')")


@dataclass
class CreditOutcome:
    """`applied`, `duplicate`, `conflict`, `insufficient_credits`, `reservation_closed`, `account_deleted`,
    `account_under_review` (an open drift item), `not_found`, `invalid`."""

    status: str
    entry: dict[str, Any] | None = None
    detail: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status in {"applied", "duplicate"}


class PostgresCreditRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # ---- accounts --------------------------------------------------------------------------------------------

    def ensure_account(self, incarnation_id: str) -> dict[str, Any]:
        now = datetime.now(UTC)
        with self._engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO credit_accounts (id, incarnation_id, created_at, updated_at) "
                "VALUES (:id, :inc, :now, :now) ON CONFLICT (incarnation_id) DO NOTHING"),
                {"id": uuid.uuid4(), "inc": incarnation_id, "now": now})  # fmt: skip
            return dict(connection.execute(text(
                "SELECT id, incarnation_id, posted, reserved, entry_count FROM credit_accounts "
                "WHERE incarnation_id = :inc"), {"inc": incarnation_id}).mappings().one())

    def account(self, incarnation_id: str) -> dict[str, Any] | None:
        with self._engine.connect() as connection:
            row = connection.execute(text(
                "SELECT id, incarnation_id, posted, reserved, posted - reserved AS available, entry_count, "
                "updated_at FROM credit_accounts WHERE incarnation_id = :inc"), {"inc": incarnation_id}).mappings().first()
        return dict(row) if row else None

    def entries(self, incarnation_id: str, *, limit: int = 100, before_seq: int | None = None) -> list[dict[str, Any]]:
        with self._engine.connect() as connection:
            rows = connection.execute(text(
                f"SELECT {_ENTRY_COLUMNS_L} FROM credit_ledger l "
                "JOIN credit_accounts a ON a.id = l.credit_account_id WHERE a.incarnation_id = :inc "
                "AND (:before IS NULL OR l.seq < :before) ORDER BY l.seq DESC LIMIT :limit"),
                {"inc": incarnation_id, "before": before_seq, "limit": max(1, min(int(limit), 500))}).mappings().all()
        return [dict(row) for row in rows]

    # ---- the shared transaction skeleton ---------------------------------------------------------------------

    @staticmethod
    def _lock(connection: Connection, incarnation_id: str) -> tuple[dict[str, Any] | None, str | None]:
        status = connection.execute(text("SELECT status FROM account_incarnations WHERE id = :inc FOR SHARE"),
                                    {"inc": incarnation_id}).scalar()  # fmt: skip
        if status is None:
            return None, None
        account = connection.execute(text(
            "SELECT id, incarnation_id, posted, reserved, entry_count FROM credit_accounts "
            "WHERE incarnation_id = :inc FOR UPDATE"), {"inc": incarnation_id}).mappings().first()
        return (dict(account) if account else None), status

    @staticmethod
    def _under_review(connection: Connection, account_id: Any) -> bool:
        return connection.execute(text(
            "SELECT EXISTS (SELECT 1 FROM billing_reconciliation_items WHERE kind = 'credit_balance_drift' "
            "AND state = 'open' AND credit_account_id = :acct)"), {"acct": account_id}).scalar()

    @staticmethod
    def _existing(connection: Connection, account_id: Any, kind: str, key: str) -> dict[str, Any] | None:
        row = connection.execute(text(
            f"SELECT {_ENTRY_COLUMNS} FROM credit_ledger WHERE credit_account_id = :acct AND kind = :kind "
            "AND idempotency_key = :key"), {"acct": account_id, "kind": kind, "key": key}).mappings().first()
        return dict(row) if row else None

    @staticmethod
    def _insert(connection: Connection, account_id: Any, *, kind: str, posted: int, reserved: int, amount: int,
                key: str, request_digest: str, actor: str, now: datetime, **columns: Any) -> dict[str, Any]:
        values = {"id": uuid.uuid4(), "acct": account_id, "kind": kind, "posted": posted, "reserved": reserved,
                  "amount": amount, "key": key, "digest": request_digest, "actor": actor[:200], "now": now,
                  "ref": None, "req": None, "stype": None, "sref": None, "meter": None, "opref": None,
                  "expires": None, "uncharged": None, "reason": None}  # fmt: skip
        values.update(columns)
        return dict(connection.execute(text(
            "INSERT INTO credit_ledger (id, credit_account_id, kind, posted_delta, reserved_delta, amount, "
            "ref_entry_id, reversal_request_id, idempotency_key, request_digest, source_type, source_ref, meter, "
            "operation_ref, expires_at, uncharged, actor, reason, created_at) VALUES (:id, :acct, :kind, :posted, "
            ":reserved, :amount, :ref, :req, :key, :digest, :stype, :sref, :meter, :opref, :expires, :uncharged, "
            f":actor, :reason, :now) RETURNING {_ENTRY_COLUMNS}"), values).mappings().one())

    def _mutate(self, incarnation_id: str, decide, *, allow_deleted: bool) -> CreditOutcome:
        """Lock, refuse a deleted or under-review account where needed, then let `decide` look up and insert."""

        try:
            with self._engine.begin() as connection:
                account, status = self._lock(connection, incarnation_id)
                if status is None or account is None:
                    return CreditOutcome("not_found", detail="no credit account")
                if status != "active" and not allow_deleted:
                    return CreditOutcome("account_deleted")
                if self._under_review(connection, account["id"]):
                    return CreditOutcome("account_under_review")
                return decide(connection, account, datetime.now(UTC))
        except IntegrityError as error:
            # A database backstop refused what the decision allowed: nothing was written.
            return CreditOutcome("conflict", detail=str(error.orig).splitlines()[0][:200])

    @staticmethod
    def _replay(existing: dict[str, Any] | None, request_digest: str) -> CreditOutcome | None:
        if existing is None:
            return None
        if existing["request_digest"] == request_digest:
            return CreditOutcome("duplicate", entry=existing)
        return CreditOutcome("conflict", entry=existing, detail="same key, different request")

    # ---- topup / reserve / settle / release / reserve_expire ------------------------------------------------------

    def topup(self, incarnation_id: str, *, amount: int, source_type: str, source_ref: str,
              actor: str = "system") -> CreditOutcome:
        """One verified money event credits one account, once (global UNIQUE on the source)."""

        if amount <= 0:
            return CreditOutcome("invalid", detail="amount")
        key = f"{source_type}:{source_ref}"
        request_digest = digest(kind="topup", account=incarnation_id, amount=amount, source_type=source_type,
                                source_ref=source_ref)  # fmt: skip

        def decide(connection, account, now):
            other = connection.execute(text(
                f"SELECT {_ENTRY_COLUMNS} FROM credit_ledger WHERE kind = 'topup' AND source_type = :t "
                "AND source_ref = :r"), {"t": source_type, "r": source_ref}).mappings().first()
            if other is not None:
                return self._replay(dict(other), request_digest)
            entry = self._insert(connection, account["id"], kind="topup", posted=amount, reserved=0, amount=amount,
                                 key=key, request_digest=request_digest, actor=actor, now=now, stype=source_type,
                                 sref=source_ref)  # fmt: skip
            return CreditOutcome("applied", entry=entry)

        return self._mutate(incarnation_id, decide, allow_deleted=False)

    def reserve(self, incarnation_id: str, *, amount: int, operation_id: str, meter: str, operation_ref: str = "",
                ttl: timedelta | None = None, actor: str = "system") -> CreditOutcome:
        if amount <= 0 or (ttl is not None and not timedelta(0) < ttl <= HOLD_TTL):
            return CreditOutcome("invalid", detail="amount or ttl")
        request_digest = digest(kind="reserve", account=incarnation_id, amount=amount, meter=meter,
                                operation_ref=operation_ref,
                                ttl="default" if ttl is None else int(ttl.total_seconds()))  # fmt: skip

        def decide(connection, account, now):
            replay = self._replay(self._existing(connection, account["id"], "reserve", operation_id), request_digest)
            if replay is not None:
                return replay
            if account["posted"] - account["reserved"] < amount:
                return CreditOutcome("insufficient_credits",
                                     extra={"available": account["posted"] - account["reserved"]})
            entry = self._insert(connection, account["id"], kind="reserve", posted=0, reserved=amount, amount=amount,
                                 key=operation_id, request_digest=request_digest, actor=actor, now=now, meter=meter,
                                 opref=operation_ref or None, expires=now + (ttl or HOLD_TTL))  # fmt: skip
            return CreditOutcome("applied", entry=entry)

        return self._mutate(incarnation_id, decide, allow_deleted=False)

    @staticmethod
    def _hold(connection, account_id, reserve_entry_id) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        hold = connection.execute(text(
            f"SELECT {_ENTRY_COLUMNS} FROM credit_ledger WHERE id = :id AND credit_account_id = :acct "
            "AND kind = 'reserve'"), {"id": reserve_entry_id, "acct": account_id}).mappings().first()
        if hold is None:
            return None, None
        close = connection.execute(text(
            f"SELECT {_ENTRY_COLUMNS} FROM credit_ledger WHERE ref_entry_id = :id "
            "AND kind IN ('settle', 'release', 'reserve_expire')"), {"id": reserve_entry_id}).mappings().first()
        return dict(hold), (dict(close) if close else None)

    def settle(self, incarnation_id: str, *, reserve_entry_id: Any, actual: int, operation_id: str,
               actor: str = "system") -> CreditOutcome:
        """Charge `min(actual, hold)` and close the hold; the rest is `uncharged`, never collected (C3). A settle of
        a hold already released or expired charges nothing and is recorded as `credit_late_settle`."""

        if actual <= 0:
            return CreditOutcome("invalid", detail="nothing was used: release the hold instead")
        request_digest = digest(kind="settle", reserve=reserve_entry_id, amount=actual)

        def decide(connection, account, now):
            replay = self._replay(self._existing(connection, account["id"], "settle", operation_id), request_digest)
            if replay is not None:
                return replay
            hold, close = self._hold(connection, account["id"], reserve_entry_id)
            if hold is None:
                return CreditOutcome("not_found", detail="no such hold")
            if close is not None:
                if close["kind"] in ("release", "reserve_expire"):
                    self._late_settle(connection, account, hold, close, actual, operation_id, now)
                return CreditOutcome("reservation_closed", entry=close)
            charged = min(actual, int(hold["amount"]))
            entry = self._insert(connection, account["id"], kind="settle", posted=-charged,
                                 reserved=-int(hold["amount"]), amount=actual, key=operation_id,
                                 request_digest=request_digest, actor=actor, now=now, ref=hold["id"],
                                 uncharged=actual - charged)  # fmt: skip
            return CreditOutcome("applied", entry=entry, extra={"charged": charged, "uncharged": actual - charged})

        return self._mutate(incarnation_id, decide, allow_deleted=False)

    def release(self, incarnation_id: str, *, reserve_entry_id: Any, operation_id: str, actor: str = "system",
                reason: str = "") -> CreditOutcome:
        request_digest = digest(kind="release", reserve=reserve_entry_id)
        return self._close(incarnation_id, "release", reserve_entry_id, operation_id, request_digest, actor,
                           reason or None)  # fmt: skip

    def expire_reserve(self, incarnation_id: str, *, reserve_entry_id: Any) -> CreditOutcome:
        """The reconciler closes a hold past its `expires_at`, or any hold of a deleted account. Idempotent: the key
        is the reserve entry's id, so a retry never writes a second expiration (C7)."""

        request_digest = digest(kind="reserve_expire", reserve=reserve_entry_id)
        return self._close(incarnation_id, "reserve_expire", reserve_entry_id, str(reserve_entry_id), request_digest,
                           "reconciler", None)  # fmt: skip

    def _close(self, incarnation_id, kind, reserve_entry_id, key, request_digest, actor, reason) -> CreditOutcome:
        def decide(connection, account, now):
            replay = self._replay(self._existing(connection, account["id"], kind, key), request_digest)
            if replay is not None:
                return replay
            hold, close = self._hold(connection, account["id"], reserve_entry_id)
            if hold is None:
                return CreditOutcome("not_found", detail="no such hold")
            if close is not None:
                return CreditOutcome("reservation_closed", entry=close)
            entry = self._insert(connection, account["id"], kind=kind, posted=0, reserved=-int(hold["amount"]),
                                 amount=int(hold["amount"]), key=key, request_digest=request_digest, actor=actor,
                                 now=now, ref=hold["id"], reason=reason)  # fmt: skip
            return CreditOutcome("applied", entry=entry)

        return self._mutate(incarnation_id, decide, allow_deleted=True)

    @staticmethod
    def _late_settle(connection, account, hold, close, actual, operation_id, now) -> None:
        _item(connection, kind="credit_late_settle", dedupe_key=f"{hold['id']}:{operation_id}", now=now,
              incarnation_id=account["incarnation_id"], reason="usage arrived after the hold was closed; not charged",
              credit_account_id=account["id"], credit_reserve_entry_id=hold["id"], credit_closing_entry_id=close["id"],
              credit_actual=actual)  # fmt: skip

    # ---- refund / adjustment ----------------------------------------------------------------------------------------

    def refund(self, incarnation_id: str, *, settle_entry_id: Any, amount: int, operation_id: str, actor: str,
               reason: str) -> CreditOutcome:
        if amount <= 0 or not reason.strip():
            return CreditOutcome("invalid", detail="amount or reason")
        request_digest = digest(kind="refund", account=incarnation_id, settle=settle_entry_id, amount=amount)

        def decide(connection, account, now):
            replay = self._replay(self._existing(connection, account["id"], "refund", operation_id), request_digest)
            if replay is not None:
                return replay
            charge = connection.execute(text(
                "SELECT id, posted_delta FROM credit_ledger WHERE id = :id AND credit_account_id = :acct "
                "AND kind = 'settle'"), {"id": settle_entry_id, "acct": account["id"]}).mappings().first()
            if charge is None:
                return CreditOutcome("not_found", detail="no such charge")
            refunded = connection.execute(text(
                "SELECT COALESCE(SUM(amount), 0) FROM credit_ledger WHERE ref_entry_id = :id AND kind = 'refund'"),
                {"id": settle_entry_id}).scalar()  # fmt: skip
            if int(refunded) + amount > -int(charge["posted_delta"]):
                return CreditOutcome("invalid", detail="refunds of a charge never exceed it")
            entry = self._insert(connection, account["id"], kind="refund", posted=amount, reserved=0, amount=amount,
                                 key=operation_id, request_digest=request_digest, actor=actor, now=now,
                                 ref=settle_entry_id, reason=reason[:400])  # fmt: skip
            return CreditOutcome("applied", entry=entry)

        return self._mutate(incarnation_id, decide, allow_deleted=True)

    def adjust(self, incarnation_id: str, *, delta: int, operation_id: str, actor: str, reason: str) -> CreditOutcome:
        """An administrator's correction, as a ledger delta (C4). There is no "set balance"."""

        if delta == 0 or not reason.strip() or not operation_id.strip() or not actor.strip():
            return CreditOutcome("invalid", detail="delta, key, actor and reason are required")
        request_digest = digest(kind="adjustment", account=incarnation_id, amount=delta)

        def decide(connection, account, now):
            replay = self._replay(self._existing(connection, account["id"], "adjustment", operation_id), request_digest)
            if replay is not None:
                return replay
            if delta < 0 and account["posted"] - account["reserved"] < -delta:
                return CreditOutcome("insufficient_credits",
                                     extra={"available": account["posted"] - account["reserved"]})
            entry = self._insert(connection, account["id"], kind="adjustment", posted=delta, reserved=0,
                                 amount=abs(delta), key=operation_id, request_digest=request_digest, actor=actor,
                                 now=now, reason=reason[:400])  # fmt: skip
            return CreditOutcome("applied", entry=entry)

        return self._mutate(incarnation_id, decide, allow_deleted=True)

    # ---- reversal (C5, P1-3, P1-4, P1-5) ---------------------------------------------------------------------------

    def reverse(self, incarnation_id: str, *, topup_entry_id: Any, requested: int, source_type: str, source_ref: str,
                actor: str, reason: str) -> CreditOutcome:
        """Reverse `min(requested, available, remaining_reversible)` of a top-up because its money went back, and
        record the shortfall. Decided once: a replay returns the stored receipt, whatever the balance is now."""

        if requested <= 0 or not reason.strip():
            return CreditOutcome("invalid", detail="requested or reason")
        key = f"{source_type}:{source_ref}"
        request_digest = digest(kind="reversal", account=incarnation_id, topup=topup_entry_id, requested=requested,
                                source_type=source_type, source_ref=source_ref)  # fmt: skip

        def decide(connection, account, now):
            receipt = connection.execute(text(
                f"SELECT {_REQUEST_COLUMNS} FROM credit_reversal_requests WHERE source_type = :t AND source_ref = :r"),
                {"t": source_type, "r": source_ref}).mappings().first()  # fmt: skip
            if receipt is not None:
                receipt = dict(receipt)
                entry = connection.execute(text(
                    f"SELECT {_ENTRY_COLUMNS} FROM credit_ledger WHERE reversal_request_id = :id"),
                    {"id": receipt["id"]}).mappings().first()  # fmt: skip
                status = "duplicate" if receipt["request_digest"] == request_digest else "conflict"
                return CreditOutcome(status, entry=dict(entry) if entry else None, extra={"request": receipt})
            topup = connection.execute(text(
                "SELECT id, amount FROM credit_ledger WHERE id = :id AND credit_account_id = :acct AND kind = 'topup'"),
                {"id": topup_entry_id, "acct": account["id"]}).mappings().first()  # fmt: skip
            if topup is None:
                return CreditOutcome("not_found", detail="no such top-up")
            reversed_already = int(connection.execute(text(
                "SELECT COALESCE(SUM(amount), 0) FROM credit_ledger WHERE ref_entry_id = :id AND kind = 'reversal'"),
                {"id": topup_entry_id}).scalar())  # fmt: skip
            applied = min(requested, account["posted"] - account["reserved"], int(topup["amount"]) - reversed_already)
            applied = max(applied, 0)
            shortfall = requested - applied
            request = dict(connection.execute(text(
                "INSERT INTO credit_reversal_requests (id, credit_account_id, topup_entry_id, idempotency_key, "
                "request_digest, requested, applied, shortfall, source_type, source_ref, actor, reason, created_at) "
                "VALUES (:id, :acct, :topup, :key, :digest, :requested, :applied, :shortfall, :t, :r, :actor, "
                f":reason, :now) RETURNING {_REQUEST_COLUMNS}"),
                {"id": uuid.uuid4(), "acct": account["id"], "topup": topup_entry_id, "key": key,
                 "digest": request_digest, "requested": requested, "applied": applied, "shortfall": shortfall,
                 "t": source_type, "r": source_ref, "actor": actor[:200], "reason": reason[:400],
                 "now": now}).mappings().one())  # fmt: skip
            entry = None
            if applied > 0:
                entry = self._insert(connection, account["id"], kind="reversal", posted=-applied, reserved=0,
                                     amount=applied, key=key, request_digest=request_digest, actor=actor, now=now,
                                     ref=topup_entry_id, req=request["id"], reason=reason[:400])  # fmt: skip
            if shortfall > 0:
                _item(connection, kind="credit_reversal_shortfall", dedupe_key=str(request["id"]), now=now,
                      incarnation_id=account["incarnation_id"], external_event_id=key[:200],
                      reason=f"{shortfall} of {requested} credits could not be reversed (spent or reserved)",
                      credit_account_id=account["id"], credit_topup_entry_id=topup_entry_id,
                      credit_reversal_request_id=request["id"], credit_reversal_entry_id=entry["id"] if entry else None,
                      credit_requested=requested, credit_applied=applied, credit_shortfall=shortfall)  # fmt: skip
            return CreditOutcome("applied", entry=entry, extra={"request": request})

        return self._mutate(incarnation_id, decide, allow_deleted=True)

    # ---- PR-MON-5: a paid credit-pack order's credit (design §6.1-§6.3, §7.1) ------------------------------------------

    def apply_credit_topup(self, order_code: int, *, actor: str = "system") -> CreditOutcome:
        """Credit a paid credit-pack order exactly once, in one transaction: the incarnation `FOR SHARE`, then the order
        `FOR SHARE` (re-read here: a refund that committed first is seen), then the credit account `FOR UPDATE` and
        the top-up. `duplicate` only for the exact expected top-up; any other entry on the order's source is a
        `conflict` and the order stays unfulfilled. No provider is called."""

        source_ref = None
        try:
            with self._engine.begin() as connection:
                head = connection.execute(text(
                    "SELECT incarnation_id, gateway, order_code FROM billing_orders WHERE order_code = :code"),
                    {"code": order_code}).mappings().first()  # fmt: skip
                if head is None:
                    return CreditOutcome("not_found", detail="no such order")
                incarnation = str(head["incarnation_id"])
                status = connection.execute(text(
                    "SELECT status FROM account_incarnations WHERE id = :inc FOR SHARE"), {"inc": incarnation}).scalar()
                order = connection.execute(text(
                    "SELECT id, product_kind, state, credit_units, gateway, order_code FROM billing_orders "
                    "WHERE order_code = :code FOR SHARE"), {"code": order_code}).mappings().one()
                if order["product_kind"] != "credit_pack":
                    return CreditOutcome("invalid", detail="not a credit-pack order")
                if order["state"] == "refunded":
                    return CreditOutcome("order_refunded")
                if order["state"] != "paid":
                    return CreditOutcome("not_paid")
                if status != "active":
                    return CreditOutcome("account_deleted")
                connection.execute(text(
                    "INSERT INTO credit_accounts (id, incarnation_id, created_at, updated_at) VALUES (:id, :inc, :now, :now) "
                    "ON CONFLICT (incarnation_id) DO NOTHING"),
                    {"id": uuid.uuid4(), "inc": incarnation, "now": datetime.now(UTC)})  # fmt: skip
                account = dict(connection.execute(text(
                    "SELECT id, incarnation_id, posted, reserved, entry_count FROM credit_accounts "
                    "WHERE incarnation_id = :inc FOR UPDATE"), {"inc": incarnation}).mappings().one())
                units = int(order["credit_units"])
                source_ref = f"{order['gateway']}:{order['order_code']}"
                request_digest = digest(kind="topup", account=incarnation, amount=units, source_type="billing_order",
                                        source_ref=source_ref)  # fmt: skip
                existing = connection.execute(text(
                    f"SELECT {_ENTRY_COLUMNS} FROM credit_ledger WHERE kind = 'topup' AND source_type = 'billing_order' "
                    "AND source_ref = :r"), {"r": source_ref}).mappings().first()
                if existing is not None:
                    existing = dict(existing)
                    exact = (str(existing["credit_account_id"]) == str(account["id"]) and int(existing["amount"]) == units
                             and existing["request_digest"] == request_digest)  # fmt: skip
                    return CreditOutcome("duplicate" if exact else "conflict", entry=existing,
                                         detail="" if exact else "the order's source holds another top-up")
                # checked after the duplicate lookup: a redelivery of a credited order stays a duplicate under review
                if self._under_review(connection, account["id"]):
                    return CreditOutcome("account_under_review")
                entry = self._insert(connection, account["id"], kind="topup", posted=units, reserved=0, amount=units,
                                     key=source_ref, request_digest=request_digest, actor=actor,
                                     now=datetime.now(UTC), stype="billing_order", sref=source_ref)  # fmt: skip
                return CreditOutcome("applied", entry=entry, extra={"credit_account_id": account["id"]})
        except IntegrityError as error:
            return CreditOutcome("conflict", detail=str(error.orig).splitlines()[0][:200],
                                 extra={"source_ref": source_ref})

    def reverse_credit_topup(self, order_code: int, *, actor: str, reason: str) -> CreditOutcome:
        """A refunded credit-pack order takes back its full `credit_units` (K2), C5 deciding what can be reversed;
        the money event is `payos_refund:<gateway>:<code>`. Nothing to reverse when the order was never credited."""

        with self._engine.connect() as connection:
            order = connection.execute(text(
                f"SELECT o.incarnation_id, o.gateway, o.order_code, o.credit_units, o.state, o.product_kind, "
                f"{EXACT_TOPUP} AS credited FROM billing_orders o WHERE o.order_code = :code"),
                {"code": order_code}).mappings().first()  # fmt: skip
            if order is None or order["product_kind"] != "credit_pack":
                return CreditOutcome("not_found", detail="no such credit-pack order")
            if order["state"] != "refunded":
                return CreditOutcome("invalid", detail="the order is not refunded")
            if not order["credited"]:
                return CreditOutcome("not_credited")
            source_ref = f"{order['gateway']}:{order['order_code']}"
            topup = connection.execute(text(
                "SELECT id FROM credit_ledger WHERE kind = 'topup' AND source_type = 'billing_order' AND source_ref = :r"),
                {"r": source_ref}).scalar_one()  # fmt: skip
        return self.reverse(str(order["incarnation_id"]), topup_entry_id=topup, requested=int(order["credit_units"]),
                            source_type="payos_refund", source_ref=source_ref, actor=actor, reason=reason)  # fmt: skip

    def credit_order_state(self, order_code: int) -> dict[str, Any] | None:
        """What the reconciler needs about one credit-pack order: its state, whether its exact top-up exists, and
        whether its complete reversal exists."""

        with self._engine.connect() as connection:
            row = connection.execute(text(
                f"SELECT o.id, o.incarnation_id, o.state, o.credit_units, o.gateway, o.order_code, {EXACT_TOPUP} AS credited, "
                f"{COMPLETE_REVERSAL} AS reversed FROM billing_orders o "
                "WHERE o.order_code = :code AND o.product_kind = 'credit_pack'"), {"code": order_code}).mappings().first()
        return dict(row) if row else None

    def credit_topup_gaps(self, *, limit: int) -> list[dict[str, Any]]:
        """Paid credit-pack orders without their exact top-up (§6.1)."""

        with self._engine.connect() as connection:
            rows = connection.execute(text(
                "SELECT o.id, o.order_code, o.incarnation_id, o.credit_units, o.gateway FROM billing_orders o "
                f"WHERE o.product_kind = 'credit_pack' AND o.state = 'paid' AND NOT {EXACT_TOPUP} "
                f"ORDER BY {_LAST_ESCALATED.format(kind='credit_topup_unapplied')} NULLS FIRST, o.paid_at "
                "LIMIT :limit"), {"limit": int(limit)}).mappings().all()
        return [dict(row) for row in rows]

    def credit_reversal_gaps(self, *, limit: int) -> list[dict[str, Any]]:
        """Refunded credit-pack orders whose exact top-up exists without their complete reversal (§7.1)."""

        with self._engine.connect() as connection:
            rows = connection.execute(text(
                "SELECT o.id, o.order_code, o.incarnation_id, o.credit_units, o.gateway FROM billing_orders o "
                f"WHERE o.product_kind = 'credit_pack' AND o.state = 'refunded' AND {EXACT_TOPUP} "
                f"AND NOT {COMPLETE_REVERSAL} "
                f"ORDER BY {_LAST_ESCALATED.format(kind='credit_reversal_unapplied')} NULLS FIRST, o.refunded_at "
                "LIMIT :limit"),
                {"limit": int(limit)}).mappings().all()  # fmt: skip
        return [dict(row) for row in rows]

    def record_credit_gap(self, *, kind: str, order: dict[str, Any], reason: str, topup_entry_id: Any = None) -> bool:
        """Open (or reopen) `credit_topup_unapplied` / `credit_reversal_unapplied` for an order. False when the
        account has no credit account to name (credits were never set up for it): the gap stays derivable."""

        now = datetime.now(UTC)
        with self._engine.begin() as connection:
            account = connection.execute(text("SELECT id FROM credit_accounts WHERE incarnation_id = :inc"),
                                         {"inc": order["incarnation_id"]}).scalar()  # fmt: skip
            if account is None:
                return False
            columns = {"credit_account_id": account, "credit_requested": int(order["credit_units"])}
            if topup_entry_id is not None:
                columns["credit_topup_entry_id"] = topup_entry_id
            connection.execute(text(
                "INSERT INTO billing_reconciliation_items AS item (id, kind, gateway, dedupe_key, reason, incarnation_id, "
                f"billing_order_id, state, first_seen_at, last_seen_at, {', '.join(columns)}) VALUES (:id, :kind, "
                f"'{CREDITS_GATEWAY}', :key, :reason, :inc, :order, 'open', :now, :now, "
                f"{', '.join(':' + name for name in columns)}) ON CONFLICT (kind, gateway, dedupe_key) DO UPDATE SET "
                "occurrences = item.occurrences + 1, last_seen_at = :now, "
                "state = CASE WHEN item.state <> 'open' THEN 'open' ELSE item.state END, "
                "reopened = CASE WHEN item.state <> 'open' THEN item.reopened + 1 ELSE item.reopened END, "
                + ", ".join(f"{column} = CASE WHEN item.state <> 'open' THEN NULL ELSE item.{column} END"
                            for column in ("resolution_outcome", "resolution_reference", "resolution_note", "resolved_by",
                                           "resolved_at"))),
                {"id": uuid.uuid4(), "kind": kind, "key": str(order["order_code"]), "reason": reason[:400],
                 "inc": order["incarnation_id"], "order": order["id"], "now": now, **columns})  # fmt: skip
        return True

    def entries_by_source(self, source_type: str, source_ref: str) -> Any:
        """The id of the top-up holding a money source, or None."""

        with self._engine.connect() as connection:
            return connection.execute(text(
                "SELECT id FROM credit_ledger WHERE kind = 'topup' AND source_type = :t AND source_ref = :r"),
                {"t": source_type, "r": source_ref}).scalar()  # fmt: skip

    def refund_obligation_recorded(self, order_id: Any) -> bool:
        """A `paid_deleted_account` item exists for the order: its money is owed back through that path (§6.2)."""

        if order_id is None:
            return False
        with self._engine.connect() as connection:
            return bool(connection.execute(text(
                "SELECT EXISTS (SELECT 1 FROM billing_reconciliation_items WHERE kind = 'paid_deleted_account' "
                "AND billing_order_id = :order)"), {"order": order_id}).scalar())

    def open_credit_gaps(self, kind: str) -> list[dict[str, Any]]:
        with self._engine.connect() as connection:
            rows = connection.execute(text(
                "SELECT i.dedupe_key, o.order_code FROM billing_reconciliation_items i "
                "JOIN billing_orders o ON o.id = i.billing_order_id WHERE i.kind = :kind AND i.state = 'open'"),
                {"kind": kind}).mappings().all()  # fmt: skip
        return [dict(row) for row in rows]

    # ---- the reconciler's reads and writes (short transactions) -------------------------------------------------------

    def holds_to_close(self, *, now: datetime, limit: int) -> list[dict[str, Any]]:
        """Open holds past their `expires_at`, and every open hold of a deleted account."""

        with self._engine.connect() as connection:
            rows = connection.execute(text(
                "SELECT l.id AS reserve_entry_id, a.incarnation_id FROM credit_ledger l "
                "JOIN credit_accounts a ON a.id = l.credit_account_id "
                "JOIN account_incarnations i ON i.id = a.incarnation_id "
                "WHERE l.kind = 'reserve' AND (l.expires_at <= :now OR i.status <> 'active') "
                "AND NOT EXISTS (SELECT 1 FROM credit_ledger c WHERE c.ref_entry_id = l.id "
                "AND c.kind IN ('settle', 'release', 'reserve_expire')) ORDER BY l.expires_at LIMIT :limit"),
                {"now": now, "limit": int(limit)}).mappings().all()  # fmt: skip
        return [dict(row) for row in rows]

    def drift(self) -> list[dict[str, Any]]:
        """Accounts whose snapshot differs from their ledger (should never happen; an incident, never repaired)."""

        with self._engine.connect() as connection:
            rows = connection.execute(text(
                "SELECT a.id AS credit_account_id, a.incarnation_id, a.posted AS snapshot_posted, "
                "a.reserved AS snapshot_reserved, a.entry_count, COALESCE(s.posted, 0) AS expected_posted, "
                "COALESCE(s.reserved, 0) AS expected_reserved FROM credit_accounts a LEFT JOIN ("
                "SELECT credit_account_id, SUM(posted_delta) AS posted, SUM(reserved_delta) AS reserved "
                "FROM credit_ledger GROUP BY credit_account_id) s ON s.credit_account_id = a.id "
                "WHERE a.posted <> COALESCE(s.posted, 0) OR a.reserved <> COALESCE(s.reserved, 0)")).mappings().all()
        return [dict(row) for row in rows]

    def record_drift(self, row: dict[str, Any]) -> None:
        now = datetime.now(UTC)
        with self._engine.begin() as connection:
            _item(connection, kind="credit_balance_drift", dedupe_key=str(row["credit_account_id"]), now=now,
                  reopen=True, incarnation_id=row["incarnation_id"], reason="the snapshot differs from the ledger",
                  credit_account_id=row["credit_account_id"], credit_expected_posted=row["expected_posted"],
                  credit_expected_reserved=row["expected_reserved"], credit_snapshot_posted=row["snapshot_posted"],
                  credit_snapshot_reserved=row["snapshot_reserved"])  # fmt: skip

    def open_drift_accounts(self) -> list[str]:
        with self._engine.connect() as connection:
            return [str(row[0]) for row in connection.execute(text(
                "SELECT dedupe_key FROM billing_reconciliation_items WHERE kind = 'credit_balance_drift' "
                "AND state = 'open'")).all()]

    def deleted_with_balance(self, *, limit: int) -> list[dict[str, Any]]:
        """Deleted accounts holding credit and no open liability item yet (C1)."""

        with self._engine.connect() as connection:
            rows = connection.execute(text(
                "SELECT a.id AS credit_account_id, a.incarnation_id, a.posted, a.reserved FROM credit_accounts a "
                "JOIN account_incarnations i ON i.id = a.incarnation_id WHERE i.status <> 'active' AND a.posted > 0 "
                "AND NOT EXISTS (SELECT 1 FROM billing_reconciliation_items r WHERE r.kind = 'credit_balance_on_deletion' "
                "AND r.credit_account_id = a.id) LIMIT :limit"), {"limit": int(limit)}).mappings().all()  # fmt: skip
        return [dict(row) for row in rows]

    def record_deletion_liability(self, row: dict[str, Any]) -> None:
        now = datetime.now(UTC)
        with self._engine.begin() as connection:
            _item(connection, kind="credit_balance_on_deletion", dedupe_key=str(row["credit_account_id"]), now=now,
                  incarnation_id=row["incarnation_id"],
                  reason="credit left on a deleted account: a financial liability (C1), not forfeited or refunded",
                  credit_account_id=row["credit_account_id"], credit_balance_posted=row["posted"],
                  credit_balance_reserved=row["reserved"])  # fmt: skip

    # ---- the runtime boundary (P1-2) ---------------------------------------------------------------------------------

    def runtime_privilege_violations(self) -> list[str]:
        """Every privilege of the connected role that would defeat the financial boundary, and every privilege it
        lacks to run a credit transaction. Empty means safe and able."""

        checks = {
            "superuser": "SELECT rolsuper FROM pg_roles WHERE rolname = current_user",
            "bypassrls": "SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user",
            "member_of_owner": "SELECT pg_has_role(current_user, 'orena_credit_owner', 'MEMBER')",
            "owns_credit_tables": "SELECT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = current_schema() "
                                  "AND tablename IN ('credit_accounts', 'credit_ledger', 'credit_reversal_requests') "
                                  "AND tableowner = current_user)",
            "owns_schema": "SELECT EXISTS (SELECT 1 FROM pg_namespace n JOIN pg_roles r ON r.oid = n.nspowner "
                           "WHERE n.nspname = current_schema() AND r.rolname = current_user)",
            "create_on_schema": "SELECT has_schema_privilege(current_user, current_schema(), 'CREATE')",
            "execute_apply_entry": "SELECT has_function_privilege(current_user, "
                                   "current_schema() || '.credit_apply_entry()', 'EXECUTE')",
        }
        for column in ("posted", "reserved", "entry_count", "last_entry_id"):
            checks[f"update_credit_accounts_{column}"] = (
                f"SELECT has_column_privilege(current_user, 'credit_accounts', '{column}', 'UPDATE')")
        for table, privileges in (("credit_accounts", ("DELETE", "TRUNCATE")),
                                  ("credit_ledger", ("UPDATE", "DELETE", "TRUNCATE")),
                                  ("credit_reversal_requests", ("UPDATE", "DELETE", "TRUNCATE")),
                                  ("billing_reconciliation_items", ("DELETE", "TRUNCATE"))):
            for privilege in privileges:
                checks[f"{privilege.lower()}_{table}"] = (
                    f"SELECT has_table_privilege(current_user, '{table}', '{privilege}')")
        # What the runtime must hold (review P1-2): membership of the runtime group, and the effective privileges a
        # credit transaction uses. Without them `ready` would claim an operation that then fails.
        required = {
            "missing_runtime_membership": "SELECT pg_has_role(current_user, 'orena_credit_runtime', 'MEMBER')",
            "missing_select_credit_accounts": "SELECT has_table_privilege(current_user, 'credit_accounts', 'SELECT')",
            "missing_insert_credit_accounts": "SELECT has_column_privilege(current_user, 'credit_accounts', "
                                              "'incarnation_id', 'INSERT')",
            "missing_lock_credit_accounts": "SELECT has_column_privilege(current_user, 'credit_accounts', "
                                            "'updated_at', 'UPDATE')",
            "missing_lock_account_incarnations": "SELECT has_any_column_privilege(current_user, 'account_incarnations', "
                                                 "'UPDATE') AND has_table_privilege(current_user, "
                                                 "'account_incarnations', 'SELECT')",
            # PR-MON-5 §6.3: a credit-pack top-up locks its order
            "missing_lock_billing_orders": "SELECT has_any_column_privilege(current_user, 'billing_orders', 'UPDATE') "
                                           "AND has_table_privilege(current_user, 'billing_orders', 'SELECT')",
        }
        for table, privileges in (("credit_ledger", ("SELECT", "INSERT")), ("credit_reversal_requests", ("SELECT", "INSERT")),
                                  ("billing_reconciliation_items", ("SELECT", "INSERT", "UPDATE"))):
            for privilege in privileges:
                required[f"missing_{privilege.lower()}_{table}"] = (
                    f"SELECT has_table_privilege(current_user, '{table}', '{privilege}')")
        with self._engine.connect() as connection:
            violations = [name for name, sql in checks.items() if connection.execute(text(sql)).scalar()]
            violations += [name for name, sql in required.items() if not connection.execute(text(sql)).scalar()]
        return violations


def _item(connection: Connection, *, kind: str, dedupe_key: str, now: datetime, reopen: bool = False,
          incarnation_id: Any = None, external_event_id: str | None = None, reason: str | None = None,
          **credit: Any) -> None:
    """A credit reconciliation item, in the caller's transaction. Idempotent on (kind, gateway, dedupe key): a repeat
    only counts; a critical one (`reopen`) seen again after it was resolved goes back to open."""

    names = ", ".join(credit)
    params = ", ".join(f":{name}" for name in credit)
    reopen_sql = ""
    if reopen:
        reopen_sql = (", state = CASE WHEN item.state <> 'open' THEN 'open' ELSE item.state END, "
                      "reopened = CASE WHEN item.state <> 'open' THEN item.reopened + 1 ELSE item.reopened END, "
                      + ", ".join(f"{column} = CASE WHEN item.state <> 'open' THEN NULL ELSE item.{column} END"
                                  for column in ("resolution_outcome", "resolution_reference", "resolution_note",
                                                 "resolved_by", "resolved_at")))
    connection.execute(text(
        "INSERT INTO billing_reconciliation_items AS item (id, kind, gateway, dedupe_key, external_event_id, reason, "
        f"incarnation_id, state, first_seen_at, last_seen_at, {names}) VALUES (:id, :kind, :gateway, :key, :event, "
        f":reason, :inc, 'open', :now, :now, {params}) ON CONFLICT (kind, gateway, dedupe_key) DO UPDATE SET "
        f"occurrences = item.occurrences + 1, last_seen_at = :now{reopen_sql}"),
        {"id": uuid.uuid4(), "kind": kind, "gateway": CREDITS_GATEWAY, "key": dedupe_key[:200],
         "event": external_event_id, "reason": (reason or None) and reason[:400], "inc": incarnation_id, "now": now,
         **credit})  # fmt: skip
