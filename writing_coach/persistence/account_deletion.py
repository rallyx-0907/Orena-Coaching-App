"""Manual account deletion: the plan (read-only) and its application in one transaction (PRE-502 R4, D-055).

The operator tool is `scripts/account_deletion.py`; the procedure around it is docs/project/ACCOUNT_DELETION_RUNBOOK.md.
Destructive: nobody applies it against a public runtime until the independent architecture review the runbook names is
recorded in Git. The default is a dry run.

**Complete by construction.** The plan does not trust a hand-written list. It reads the live schema
(`information_schema`) and takes every base table with a column that names the account:
- `user_id` or `account_id`: the account's `users.id`;
- `incarnation_id`: any of its incarnations;
- `user_key`: its sign-in key.
`deletion_enumeration.py` stays the documented list, and a test keeps it inside what the scan finds.

Each table found is classified:
- **kept as the barrier:** `users` (its columns are reset and anonymised) and `account_incarnations` (marked deleted);
- **`audit_logs`:** the account's own rows are deleted. `admin.*` rows stay as the record of what administrators did,
  pending the reviewer's decision (runbook §7.3);
- **commerce** (`commerce_*`, `credit_*`, `billing_*`): money records. They are deleted only with an explicit
  `commerce="delete"`, or kept with `"keep"`. With rows present and no choice, `apply` refuses;
- **everything else:** the account's rows are deleted. Child rows go by their own `ON DELETE CASCADE`. A child
  without one makes the transaction fail and roll back: nothing is half-deleted.

Not here, and listed by the tool as next steps:
- the personal media files (`media_library_api.delete_all_owned_media`, which needs the app's stores);
- the Polar customer clean-up (an admin route);
- the deletion journal export (`scripts/runtime_backup.py deletions`).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

from writing_coach.persistence.deletion_enumeration import CONSENT_COLUMNS_TO_RESET, USER_COLUMNS_TO_RESET

ACCOUNT_COLUMNS = ("user_id", "account_id")
INCARNATION_COLUMNS = ("incarnation_id",)
KEY_COLUMNS = ("user_key",)
BARRIER_TABLES = frozenset({"users", "account_incarnations"})
COMMERCE_PREFIXES = ("commerce_", "credit_", "billing_")
AUDIT_TABLE = "audit_logs"
ANONYMOUS_NAME = ""
ANONYMOUS_PICTURE = ""


def anonymous_email(account_id: str) -> str:
    """`users.email` is UNIQUE and NOT NULL: a per-account placeholder that names no one (runbook §0, reviewer)."""
    return f"deleted+{account_id}@deleted.invalid"


@dataclass(frozen=True)
class Account:
    id: str
    user_key: str
    incarnations: tuple[str, ...]


@dataclass(frozen=True)
class Target:
    table: str
    column: str
    group: str  # "delete" | "commerce" | "audit"
    rows: int


@dataclass
class Plan:
    account: Account
    targets: list[Target] = field(default_factory=list)
    audit_kept: int = 0  # admin.* rows about/by the account, kept as the record
    blockers: list[str] = field(default_factory=list)  # child tables that would refuse the delete (no cascade)

    @property
    def commerce_rows(self) -> int:
        return sum(t.rows for t in self.targets if t.group == "commerce")

    def summary(self) -> dict[str, Any]:
        return {
            "account": {"id": self.account.id, "incarnations": len(self.account.incarnations)},
            "delete": {f"{t.table}.{t.column}": t.rows for t in self.targets if t.group in ("delete", "audit")},
            "commerce": {f"{t.table}.{t.column}": t.rows for t in self.targets if t.group == "commerce"},
            "audit_kept_admin_rows": self.audit_kept,
            "fk_without_cascade": self.blockers,
            "users_row": "kept as the barrier: settings and consent reset; email, name and picture anonymised",
            "incarnations": "marked deleted (kept as the barrier)",
        }


def find_account(conn: Any, *, email: str | None = None, user_key: str | None = None) -> Account | None:
    if bool(email) == bool(user_key):
        raise ValueError("name the account by exactly one of email or user_key")
    row = conn.execute(text("SELECT id::text AS id, user_key FROM users WHERE " +
                            ("lower(email) = lower(:v)" if email else "user_key = :v")),
                       {"v": email or user_key}).mappings().first()  # fmt: skip
    if row is None:
        return None
    incarnations = tuple(r[0] for r in conn.execute(
        text("SELECT id::text FROM account_incarnations WHERE user_id::text = :u ORDER BY epoch"), {"u": row["id"]}))
    return Account(row["id"], row["user_key"], incarnations)


def _owner_columns(conn: Any) -> list[tuple[str, str]]:
    names = ACCOUNT_COLUMNS + INCARNATION_COLUMNS + KEY_COLUMNS
    return [(r[0], r[1]) for r in conn.execute(text(
        "SELECT c.table_name, c.column_name FROM information_schema.columns c"
        " JOIN information_schema.tables t ON t.table_schema = c.table_schema AND t.table_name = c.table_name"
        " WHERE c.table_schema = current_schema() AND t.table_type = 'BASE TABLE' AND c.column_name = ANY(:names)"
        " ORDER BY c.table_name, c.column_name"), {"names": list(names)})]  # fmt: skip


def _where(column: str) -> str:
    if column in ACCOUNT_COLUMNS:
        return f'"{column}"::text = :account'
    if column in INCARNATION_COLUMNS:
        return f'"{column}"::text = ANY(:incarnations)'
    return f'"{column}" = :user_key'


def _params(account: Account) -> dict[str, Any]:
    return {"account": account.id, "incarnations": list(account.incarnations), "user_key": account.user_key}


def _group(table: str) -> str:
    if table == AUDIT_TABLE:
        return "audit"
    if table.startswith(COMMERCE_PREFIXES):
        return "commerce"
    return "delete"


def build_plan(conn: Any, account: Account) -> Plan:
    """Read-only: what deleting this account removes, by table and column, with row counts."""

    plan = Plan(account)
    params = _params(account)
    for table, column in _owner_columns(conn):
        if table in BARRIER_TABLES:
            continue
        group = _group(table)
        where = _where(column)
        if group == "audit":
            rows = conn.execute(text(f'SELECT count(*) FROM "{table}" WHERE {where} AND action NOT LIKE :admin'),
                                {**params, "admin": "admin.%"}).scalar()  # fmt: skip
            plan.audit_kept += int(conn.execute(text(f'SELECT count(*) FROM "{table}" WHERE {where}'
                                                     " AND action LIKE :admin"), {**params, "admin": "admin.%"}).scalar())
        else:
            rows = conn.execute(text(f'SELECT count(*) FROM "{table}" WHERE {where}'), params).scalar()
        plan.targets.append(Target(table, column, group, int(rows or 0)))
    deleted = {t.table for t in plan.targets}
    for child, parent, rule in conn.execute(text(
            "SELECT tc.table_name, ccu.table_name, rc.delete_rule FROM information_schema.referential_constraints rc"
            " JOIN information_schema.table_constraints tc ON tc.constraint_name = rc.constraint_name"
            "  AND tc.constraint_schema = rc.constraint_schema"
            " JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = rc.unique_constraint_name"
            "  AND ccu.constraint_schema = rc.unique_constraint_schema"
            " WHERE rc.constraint_schema = current_schema()")):  # fmt: skip
        if parent in deleted and rule not in ("CASCADE", "SET NULL") and child not in deleted:
            plan.blockers.append(f"{child} -> {parent} ({rule})")
    plan.blockers = sorted(set(plan.blockers))
    return plan


class DeletionRefused(Exception):
    """`apply` would not run: the plan needs a decision first. Nothing was changed."""


def apply_plan(engine: Any, *, email: str | None = None, user_key: str | None = None, commerce: str | None = None,
               now: datetime | None = None) -> Plan:  # fmt: skip
    """Delete the account's data in ONE transaction, re-planned inside it under a lock on the `users` row. Refused,
    with nothing changed, when commerce rows exist and `commerce` is not "delete" or "keep"."""

    if commerce not in (None, "delete", "keep"):
        raise ValueError('commerce must be "delete" or "keep"')
    moment = now or datetime.now(UTC)
    with engine.begin() as conn:
        account = find_account(conn, email=email, user_key=user_key)
        if account is None:
            raise DeletionRefused("no such account")
        conn.execute(text("SELECT id FROM users WHERE id::text = :a FOR UPDATE"), {"a": account.id})
        plan = build_plan(conn, account)
        if plan.commerce_rows and commerce is None:
            raise DeletionRefused(f"{plan.commerce_rows} commerce rows: choose commerce='delete' or 'keep' first")
        params = _params(account)
        conn.execute(text("UPDATE account_incarnations SET status = 'deleted', deleted_at = :now"
                          " WHERE user_id::text = :account AND status = 'active'"), {**params, "now": moment})  # fmt: skip
        for target in plan.targets:
            if target.group == "commerce" and commerce != "delete":
                continue
            where = _where(target.column)
            if target.group == "audit":
                conn.execute(text(f'DELETE FROM "{target.table}" WHERE {where} AND action NOT LIKE :admin'),
                             {**params, "admin": "admin.%"})  # fmt: skip
            else:
                conn.execute(text(f'DELETE FROM "{target.table}" WHERE {where}'), params)
        _reset_user(conn, account)
    return plan


def _reset_user(conn: Any, account: Account) -> None:
    present = {r[0] for r in conn.execute(text(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = current_schema()"
        " AND table_name = 'users'"))}  # fmt: skip
    values: dict[str, Any] = {k: v for k, v in {**USER_COLUMNS_TO_RESET, **CONSENT_COLUMNS_TO_RESET}.items()
                              if k in present}  # fmt: skip
    values.update({k: v for k, v in {"email": anonymous_email(account.id), "name": ANONYMOUS_NAME,
                                     "picture": ANONYMOUS_PICTURE}.items() if k in present})  # fmt: skip
    if not values:
        return
    assignments = ", ".join(f'"{column}" = :{column}' for column in values)
    conn.execute(text(f"UPDATE users SET {assignments} WHERE id::text = :account_id"), {**values, "account_id": account.id})


def plan_summary(engine: Any, *, email: str | None = None, user_key: str | None = None) -> dict[str, Any] | None:
    """The dry run: the plan in a READ ONLY transaction. None when no account matches."""

    with engine.connect() as conn, conn.begin():
        conn.execute(text("SET TRANSACTION READ ONLY"))
        account = find_account(conn, email=email, user_key=user_key)
        return None if account is None else build_plan(conn, account).summary()


def next_steps(account_user_key_hint: str = "<user_key>") -> list[str]:
    return [
        "Personal media files (inside the app container): python -c \"import app; from writing_coach.media_library_api "
        f"import delete_all_owned_media; print(delete_all_owned_media('{account_user_key_hint}'))\"",
        "Polar customer clean-up: POST /api/admin/billing/polar/customer-cleanup, until its marker is 'complete'",
        "Deletion journal: python scripts/runtime_backup.py deletions --out <journal path outside any database>",
        "Verify (runbook section 5), then close the request",
    ]


def _mapping(value: Mapping[str, Any]) -> dict[str, Any]:  # kept small for the tool's JSON output
    return dict(value)
