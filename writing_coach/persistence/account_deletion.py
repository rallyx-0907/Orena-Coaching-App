"""Manual account deletion: the plan (read-only) and its application in one transaction (PRE-502 R4, D-055).

The operator tool is `scripts/account_deletion.py`; the procedure around it is docs/project/ACCOUNT_DELETION_RUNBOOK.md.
Destructive: nobody applies it against a public runtime until the independent architecture review the runbook names is
recorded in Git, and until D-054's gate is lifted (continuous journaling and replay, `ORENA_BACKBONE_INTEGRATION_GATES`).
The default is a dry run.

**Complete by construction.** The plan does not trust a hand-written list. It reads the live schema
(`information_schema`) and takes every base table with a column that names the account:
- `user_id` or `account_id`: the account's `users.id`;
- `incarnation_id`: any of its incarnations;
- `user_key`: its sign-in key.
`deletion_enumeration.py` stays the documented list, and a test keeps the ORM tables inside what the plan handles.

Each table found is classified:
- **kept as the barrier:**
  - `users`: settings, consent and role reset; email, name and picture anonymised;
  - `account_incarnations`: every incarnation marked deleted. An account that never had one gets a deleted epoch-1
    row, so a returning learner meets the barrier rather than a first sign-in.
- **`audit_logs`:** `user_id` is the actor of an administrator's action, so only the account's own learner actions go
  (`learner.*`, `agent.*`). Every other row is kept as the record of what was done (runbook section 7.3).
- **commerce** (`commerce_*`, `credit_*`, `billing_*`): money records. The schema keeps their history append-only
  (RESTRICT), so they are kept. The operator says so explicitly (`commerce="keep"`); with rows present and no choice,
  `apply` refuses. Whether the public deletion page must disclose this is the owner's decision (runbook).
- **everything else:** the account's rows are deleted. Child rows go by their own `ON DELETE CASCADE`. A child that
  would refuse makes `apply` stop before any change.

The account's sessions end in the same transaction: the revocation instant auth_support reads
(`auth.session_revoked_before.*`, #377). Not here, and listed by the tool as next steps:
- the personal media files (`media_library_api.delete_all_owned_media`, which needs the app's stores);
- the Polar customer clean-up (an admin route);
- the deletion journal export (`scripts/runtime_backup.py deletions`).
"""

from __future__ import annotations

import hashlib
import json
import uuid
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
LEARNER_AUDIT_ACTIONS = ("learner.%", "agent.%")  # the account's own actions; every other row records an actor
SESSION_REVOKED_KEY_PREFIX = "auth.session_revoked_before."  # auth_support.py (#377)
USER_ROLE_AFTER_DELETION = "user"


def anonymous_email(account_id: str) -> str:
    """A per-account placeholder for `users.email` (NOT NULL) that names no one; the internal id is kept anyway."""
    return f"deleted+{account_id}@deleted.invalid"


def session_revoked_key(user_key: str) -> str:
    return SESSION_REVOKED_KEY_PREFIX + hashlib.sha256(user_key.encode("utf-8")).hexdigest()[:40]


class DeletionRefused(Exception):
    """`apply` would not run, or the account cannot be named safely: nothing was changed."""


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
    uuid_column: bool = True


@dataclass
class Plan:
    account: Account
    targets: list[Target] = field(default_factory=list)
    audit_kept: int = 0  # rows naming the account as an actor, kept as the record
    blockers: list[str] = field(default_factory=list)  # child tables with no cascade under a table that loses rows

    @property
    def commerce_rows(self) -> int:
        return sum(t.rows for t in self.targets if t.group == "commerce")

    def summary(self) -> dict[str, Any]:
        return {
            "account": {"id": self.account.id, "incarnations": len(self.account.incarnations)},
            "delete": {f"{t.table}.{t.column}": t.rows for t in self.targets if t.group in ("delete", "audit")},
            "commerce_kept": {f"{t.table}.{t.column}": t.rows for t in self.targets if t.group == "commerce"},
            "audit_kept_actor_rows": self.audit_kept,
            "fk_without_cascade": self.blockers,
            "users_row": "kept as the barrier: settings, consent and role reset; email, name and picture anonymised",
            "incarnations": "marked deleted (kept as the barrier); a deleted epoch-1 row when there is none",
            "sessions": "revoked",
        }


def find_account(conn: Any, *, email: str | None = None, user_key: str | None = None) -> Account | None:
    """The account by exactly one of email or sign-in key. `users.email` is not unique: more than one match is
    refused with the candidates' sign-in keys, so the operator names the account by its key."""

    if bool(email) == bool(user_key):
        raise ValueError("name the account by exactly one of email or user_key")
    rows = conn.execute(text("SELECT id::text AS id, user_key FROM users WHERE " +
                             ("lower(email) = lower(:v)" if email else "user_key = :v") + " ORDER BY created_at"),
                        {"v": email or user_key}).mappings().all()  # fmt: skip
    if not rows:
        return None
    if len(rows) > 1:
        raise DeletionRefused(f"{len(rows)} accounts share this email; name one by --user-key: "
                              + ", ".join(r["user_key"] for r in rows))  # fmt: skip
    return Account(rows[0]["id"], rows[0]["user_key"], _incarnations(conn, rows[0]["id"]))


def _incarnations(conn: Any, account_id: str) -> tuple[str, ...]:
    return tuple(r[0] for r in conn.execute(
        text("SELECT id::text FROM account_incarnations WHERE user_id = CAST(:u AS uuid) ORDER BY epoch"),
        {"u": account_id}))  # fmt: skip


def _owner_columns(conn: Any) -> list[tuple[str, str, bool]]:
    names = ACCOUNT_COLUMNS + INCARNATION_COLUMNS + KEY_COLUMNS
    return [(r[0], r[1], r[2] == "uuid") for r in conn.execute(text(
        "SELECT c.table_name, c.column_name, c.data_type FROM information_schema.columns c"
        " JOIN information_schema.tables t ON t.table_schema = c.table_schema AND t.table_name = c.table_name"
        " WHERE c.table_schema = current_schema() AND t.table_type = 'BASE TABLE' AND c.column_name = ANY(:names)"
        " ORDER BY c.table_name, c.column_name"), {"names": list(names)})]  # fmt: skip


def _quote(conn: Any, name: str) -> str:
    return conn.dialect.identifier_preparer.quote(name)


def _where(conn: Any, column: str, uuid_column: bool) -> str:
    """An index-friendly match: a uuid column compared as uuid, never cast to text."""
    col = _quote(conn, column)
    if column in ACCOUNT_COLUMNS:
        return f"{col} = CAST(:account AS uuid)" if uuid_column else f"{col} = :account"
    if column in INCARNATION_COLUMNS:
        return f"{col} = ANY(CAST(:incarnations AS uuid[]))" if uuid_column else f"{col} = ANY(:incarnations)"
    return f"{col} = :user_key"


def _params(account: Account) -> dict[str, Any]:
    return {"account": account.id, "incarnations": list(account.incarnations), "user_key": account.user_key}


def _group(table: str) -> str:
    if table == AUDIT_TABLE:
        return "audit"
    if table.startswith(COMMERCE_PREFIXES):
        return "commerce"
    return "delete"


def _learner_actions() -> str:
    return "(" + " OR ".join(f"action LIKE :learner{i}" for i in range(len(LEARNER_AUDIT_ACTIONS))) + ")"


def _learner_params() -> dict[str, str]:
    return {f"learner{i}": pattern for i, pattern in enumerate(LEARNER_AUDIT_ACTIONS)}


def build_plan(conn: Any, account: Account) -> Plan:
    """Read-only: what deleting this account removes, by table and column, with row counts."""

    plan = Plan(account)
    params = {**_params(account), **_learner_params()}
    for table, column, uuid_column in _owner_columns(conn):
        if table in BARRIER_TABLES or (column in INCARNATION_COLUMNS and not account.incarnations):
            continue  # an account with no incarnation has no incarnation-keyed rows
        group = _group(table)
        where = _where(conn, column, uuid_column)
        name = _quote(conn, table)
        if group == "audit":
            rows = conn.execute(text(f"SELECT count(*) FROM {name} WHERE {where} AND {_learner_actions()}"),
                                params).scalar()  # fmt: skip
            plan.audit_kept += int(conn.execute(text(f"SELECT count(*) FROM {name} WHERE {where}"
                                                     f" AND NOT {_learner_actions()}"), params).scalar() or 0)
        else:
            rows = conn.execute(text(f"SELECT count(*) FROM {name} WHERE {where}"), params).scalar()
        plan.targets.append(Target(table, column, group, int(rows or 0), uuid_column))
    deleted = {t.table for t in plan.targets if t.group != "commerce"}
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


def apply_plan(engine: Any, *, log: Any, email: str | None = None, user_key: str | None = None,
               commerce: str | None = None, now: datetime | None = None) -> Plan:  # fmt: skip
    """Delete the account's data in ONE transaction. The account row is locked first, and the incarnations and the
    plan are read under that lock. Refused, with nothing changed: an unknown or ambiguous account; commerce rows with
    no `commerce="keep"`; a child table that would refuse the delete.

    `log` is the continuous deletion journal (`deletion_log`, D-054 a), and it is required. The intent is fsynced to it
    before the commit, and the done record after."""

    from writing_coach.persistence import deletion_log

    if log is None:
        raise ValueError(f"a deletion log is required (D-054): pass log= or set {deletion_log.LOG_ENV}")
    if commerce not in (None, "keep"):
        raise ValueError('commerce must be "keep": money records are append-only and stay')
    moment = now or datetime.now(UTC)
    with engine.begin() as conn:
        found = find_account(conn, email=email, user_key=user_key)
        if found is None:
            raise DeletionRefused("no such account")
        conn.execute(text("SELECT id FROM users WHERE id = CAST(:a AS uuid) FOR UPDATE"), {"a": found.id})
        account = Account(found.id, found.user_key, _incarnations(conn, found.id))  # read under the lock
        plan = build_plan(conn, account)
        if plan.commerce_rows and commerce is None:
            raise DeletionRefused(f"{plan.commerce_rows} commerce rows: they are kept; say so with commerce='keep'")
        if plan.blockers:
            raise DeletionRefused(f"a child table would refuse the delete: {'; '.join(plan.blockers)}")
        barrier = _mark_incarnations_deleted(conn, account, moment)
        _delete_owned(conn, account, plan)
        _reset_user(conn, account)
        _revoke_sessions(conn, account, moment)
        # D-054 a: on disk outside the database before the commit. A failure here rolls the whole deletion back.
        op = deletion_log.write_intent(log, account_id=account.id, incarnations=barrier, at=moment)
    deletion_log.write_done(log, op, deleted_at=moment)  # committed: confirmed (`reconcile` settles a crash between)
    return plan


def _delete_owned(conn: Any, account: Account, plan: Plan) -> None:
    params = {**_params(account), **_learner_params()}
    for target in plan.targets:
        if target.group == "commerce":
            continue
        where = _where(conn, target.column, target.uuid_column)
        extra = f" AND {_learner_actions()}" if target.group == "audit" else ""
        conn.execute(text(f"DELETE FROM {_quote(conn, target.table)} WHERE {where}{extra}"), params)


def reapply_owner_deletions(engine: Any, account_ids: list[str], *, now: datetime | None = None) -> dict[str, int]:
    """After a restore (D-054 b): each confirmed deletion's owner-table rows are deleted again, and the users row is
    reset, anonymised and its sessions revoked. Incarnation barriers are `deletion_journal.reapply_deletions`. One
    transaction for all; an account the restore does not hold is `absent`."""

    moment = now or datetime.now(UTC)
    summary = {"replayed": 0, "absent": 0}
    with engine.begin() as conn:
        for account_id in account_ids:
            row = conn.execute(text("SELECT user_key FROM users WHERE id = CAST(:a AS uuid) FOR UPDATE"),
                               {"a": account_id}).first()  # fmt: skip
            if row is None:
                summary["absent"] += 1
                continue
            account = Account(account_id, row[0], _incarnations(conn, account_id))
            plan = build_plan(conn, account)
            if plan.blockers:
                raise DeletionRefused(f"a child table would refuse the replay: {'; '.join(plan.blockers)}")
            _delete_owned(conn, account, plan)
            _reset_user(conn, account)
            _revoke_sessions(conn, account, moment)
            summary["replayed"] += 1
    return summary


def _mark_incarnations_deleted(conn: Any, account: Account, moment: datetime) -> list[dict[str, Any]]:
    """Every incarnation deleted; returns them (id, epoch, created_at) for the journal."""
    if not account.incarnations:
        # Never registered on the backbone: a deleted epoch-1 row, so the next sign-in meets the barrier (D-054).
        conn.execute(text("INSERT INTO account_incarnations (id, user_id, epoch, status, created_at, deleted_at)"
                          " VALUES (CAST(:id AS uuid), CAST(:a AS uuid), 1, 'deleted', :now, :now)"),
                     {"id": str(uuid.uuid4()), "a": account.id, "now": moment})  # fmt: skip
    else:
        conn.execute(text("UPDATE account_incarnations SET status = 'deleted', deleted_at = :now"
                          " WHERE user_id = CAST(:a AS uuid) AND status = 'active'"), {"a": account.id, "now": moment})
    return [{"id": str(r[0]), "epoch": int(r[1]), "created_at": r[2]} for r in conn.execute(text(
        "SELECT id, epoch, created_at FROM account_incarnations WHERE user_id = CAST(:a AS uuid) ORDER BY epoch"),
        {"a": account.id})]  # fmt: skip


def _reset_user(conn: Any, account: Account) -> None:
    present = {r[0] for r in conn.execute(text(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = current_schema()"
        " AND table_name = 'users'"))}  # fmt: skip
    values: dict[str, Any] = {k: v for k, v in {**USER_COLUMNS_TO_RESET, **CONSENT_COLUMNS_TO_RESET}.items()
                              if k in present}  # fmt: skip
    values.update({k: v for k, v in {"email": anonymous_email(account.id), "name": "", "picture": "",
                                     "role": USER_ROLE_AFTER_DELETION}.items() if k in present})  # fmt: skip
    if not values:
        return
    assignments = ", ".join(f"{_quote(conn, column)} = :{column}" for column in values)
    conn.execute(text(f"UPDATE users SET {assignments} WHERE id = CAST(:account_id AS uuid)"),
                 {**values, "account_id": account.id})  # fmt: skip


def _revoke_sessions(conn: Any, account: Account, moment: datetime) -> None:
    """Every session of the account ends: the instant auth_support refuses cookies issued before (#377)."""
    conn.execute(text(
        "INSERT INTO platform_settings (key, value, updated_at, updated_by) VALUES (:k, CAST(:v AS json), :now, :by)"
        " ON CONFLICT (key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at,"
        " updated_by = excluded.updated_by"),
        {"k": session_revoked_key(account.user_key), "v": json.dumps({"before_ms": int(moment.timestamp() * 1000)}),
         "now": moment, "by": "account-deletion"})  # fmt: skip


def plan_summary(engine: Any, *, email: str | None = None, user_key: str | None = None) -> dict[str, Any] | None:
    """The dry run: the plan in a READ ONLY transaction. None when no account matches."""

    with engine.connect() as conn, conn.begin():
        conn.execute(text("SET TRANSACTION READ ONLY"))
        account = find_account(conn, email=email, user_key=user_key)
        return None if account is None else build_plan(conn, account).summary()


def next_steps(user_key: str = "<user_key>") -> list[str]:
    return [
        "Personal media files (inside the app container): python -c \"import app; from writing_coach.media_library_api "
        f"import delete_all_owned_media; print(delete_all_owned_media('{user_key}'))\"",
        "Polar customer clean-up: POST /api/admin/billing/polar/customer-cleanup, until its marker is 'complete'",
        "Deletion journal: python scripts/runtime_backup.py deletions --out <journal path outside any database>",
        "Verify (runbook section 5), then close the request",
    ]
