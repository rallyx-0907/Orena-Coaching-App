"""Prepaid credit ledger (PR-MON-4; docs/billing/PR-MON-4_DESIGN.md revision 4, APPROVED FOR IMPLEMENTATION

Promotion (2026-10-14, PR-MON-5 migration gate, the human's choice "promote on the branch, do not merge yet"):
moved from `migrations/proposed/` into the chain with 0027 -> 0031 -> 0032 -> 0033, source control only and on the
Billing lane branch. It is applied to no runtime; once merged, every PostgreSQL runtime must apply it (operator step,
after a backup) before it starts again. The text below is the proposal's, unchanged.
2026-10-14 on `48e1bf2e`; decisions C1-C7 = D-MON-019, D-MON-020, D-MON-021).

Credits are an integer count of credit units; what a unit is worth is a human decision and is never coded here.

- `credit_accounts`: one per account incarnation, never deleted (RESTRICT). `posted` and `reserved` are a snapshot
  of the ledger, written only by the ledger's own trigger function; CHECK `0 <= reserved <= posted`.
- `credit_ledger`: append-only. Eight kinds (topup, reserve, settle, release, reserve_expire, refund, reversal,
  adjustment) whose deltas are fixed by CHECKs; a `SECURITY DEFINER` trigger function owned by `orena_credit_owner`
  locks the account, validates every offset and cap, assigns the gapless `seq` and applies the deltas. Purchased
  credit never expires (C6): only a reserve carries `expires_at`.
- `credit_reversal_requests`: the immutable receipt of every reversal request, globally unique per money-side event;
  its trigger checks that `applied = min(requested, available, remaining_reversible)` (P1-3, P1-5). The ledger's
  `reversal_request_id` is the only link between the two (P1-4).
- `billing_reconciliation_items` (0031) is extended: four credit kinds, structured `credit_*` references, per-kind
  CHECKs, and a replaced guard trigger that also freezes the new facts (P1-6). That is why 0032 depends on 0031.

The write boundary is a database privilege (P1-2): the tables and functions belong to the NOLOGIN
`orena_credit_owner`; the runtime is a member of `orena_credit_runtime`, which cannot UPDATE the snapshot columns or
UPDATE/DELETE/TRUNCATE the ledger and requests. Two supported executor modes, both checked before any credit DDL
(implementation review P1-1):
- a **superuser** creates the roles when absent;
- a **non-superuser** requires them provisioned out of band, and must be a member of `orena_credit_owner` with the SET
  option (to transfer ownership); `orena_credit_owner` must hold CREATE on the schema, which this migration grants when
  the executor owns the schema.
Either way the existing roles are validated: both NOLOGIN, NOSUPERUSER, NOBYPASSRLS, and the runtime group is not a
member of the owner. Anything else fails before DDL.

Review and gate. A PROPOSAL in `migrations/proposed/` (Alembic does not read it). Order 0027 -> 0031 -> 0032, never
promoted ahead of 0031 (H1). Startup never applies it. `downgrade()` refuses while any credit row or credit item
exists, and then restores 0031's CHECKs and guard function exactly; it exists for rehearsal only.

Revision ID: 20261014_0032
Revises: 20261014_0031
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261014_0032"
down_revision = "20261014_0031"
branch_labels = None
depends_on = None

OWNER = "orena_credit_owner"
RUNTIME = "orena_credit_runtime"
KINDS = ("topup", "reserve", "settle", "release", "reserve_expire", "refund", "reversal", "adjustment")

# ---- 0031's reconciliation lists, and the extended ones -----------------------------------------------------
CRITICAL_0031 = ("entitlement_unsynced", "provider_paid_unrecorded")
MONEY_0031 = ("paid_deleted_account", "payment_unknown_order", "payment_mismatch", "payment_not_payable")
DISMISSABLE_0031 = ("event_undecided", "provider_refund", "provider_state_unresolved")
OUTCOMES_0031 = ("entitlement_synced", "payment_recorded", "payment_matched", "refund_confirmed", "reversal_confirmed",
                 "obligation_waived", "recorded")
FACTS_0031 = ("kind", "gateway", "dedupe_key", "external_event_id", "reported_order_code", "reported_amount_minor",
              "reported_currency", "payload_digest", "first_seen_at")

CREDIT_CRITICAL = ("credit_balance_drift",)
CREDIT_MONEY = ("credit_reversal_shortfall", "credit_balance_on_deletion")
CREDIT_DISMISSABLE = ("credit_late_settle",)
CREDIT_KINDS = CREDIT_CRITICAL + CREDIT_MONEY + CREDIT_DISMISSABLE
CREDIT_COLUMNS = (
    ("credit_account_id", "credit_accounts"), ("credit_topup_entry_id", "credit_ledger"),
    ("credit_reversal_request_id", "credit_reversal_requests"), ("credit_reversal_entry_id", "credit_ledger"),
    ("credit_reserve_entry_id", "credit_ledger"), ("credit_closing_entry_id", "credit_ledger"),
)
CREDIT_AMOUNTS = ("credit_requested", "credit_applied", "credit_shortfall", "credit_actual", "credit_expected_posted",
                  "credit_expected_reserved", "credit_snapshot_posted", "credit_snapshot_reserved",
                  "credit_balance_posted", "credit_balance_reserved")
CREDIT_FACTS = tuple(name for name, _ in CREDIT_COLUMNS) + CREDIT_AMOUNTS

_RESOLUTION = ("resolution_outcome", "resolution_reference", "resolution_note", "resolved_by", "resolved_at")


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _changed(column: str) -> str:
    return f"NEW.{column} IS DISTINCT FROM OLD.{column}"


def _item_guard_sql(critical: tuple[str, ...], facts: tuple[str, ...]) -> str:
    """0031's `billing_reconciliation_items_guard()`, for a list of critical kinds and immutable facts. With 0031's
    lists it is 0031's function exactly (the downgrade restores it); 0032 adds the credit kind and columns."""

    facts_changed = " OR ".join(_changed(column) for column in facts)
    links_changed = " OR ".join(f"(OLD.{column} IS NOT NULL AND {_changed(column)})"
                                for column in ("billing_order_id", "incarnation_id"))
    terminal_changes = " OR ".join(_changed(column) for column in (
        "state", "provider_state", "reason", "billing_order_id", "incarnation_id", "reopened") + _RESOLUTION)
    resolution_cleared = " AND ".join(f"NEW.{column} IS NULL" for column in _RESOLUTION)
    return f"""
        CREATE OR REPLACE FUNCTION billing_reconciliation_items_guard() RETURNS trigger LANGUAGE plpgsql AS $$
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
                    IF OLD.kind NOT IN ({_in(critical)}) OR NEW.reopened <> OLD.reopened + 1
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
    """


def _item_checks(kinds, dismissable, outcomes, outcome_required) -> list[tuple[str, str]]:
    return [
        ("ck_billing_item_kind", f"kind IN ({_in(kinds)})"),
        ("ck_billing_item_outcome", f"resolution_outcome IS NULL OR resolution_outcome IN ({_in(outcomes)})"),
        ("ck_billing_item_dismiss", f"state <> 'dismissed' OR kind IN ({_in(dismissable)})"),
        ("ck_billing_item_outcome_required",
         f"state <> 'resolved' OR kind NOT IN ({_in(outcome_required)}) OR resolution_outcome IS NOT NULL"),
    ]


ITEM_CHECKS_0031 = _item_checks(CRITICAL_0031 + MONEY_0031 + DISMISSABLE_0031, DISMISSABLE_0031, OUTCOMES_0031,
                                CRITICAL_0031 + MONEY_0031)
ITEM_CHECKS_0032 = _item_checks(CRITICAL_0031 + MONEY_0031 + DISMISSABLE_0031 + CREDIT_KINDS,
                                DISMISSABLE_0031 + CREDIT_DISMISSABLE, OUTCOMES_0031 + ("balance_consistent",),
                                CRITICAL_0031 + MONEY_0031 + CREDIT_CRITICAL + CREDIT_MONEY)
CREDIT_ITEM_CHECKS = [
    # a non-credit kind carries no credit fact; a credit kind belongs to the `credits` pseudo-gateway
    ("ck_billing_item_credit_scope",
     f"(kind IN ({_in(CREDIT_KINDS)}) AND gateway = 'credits') OR (kind NOT IN ({_in(CREDIT_KINDS)}) AND "
     + " AND ".join(f"{column} IS NULL" for column in CREDIT_FACTS) + ")"),
    ("ck_billing_item_credit_shortfall",
     "kind <> 'credit_reversal_shortfall' OR (credit_account_id IS NOT NULL AND credit_topup_entry_id IS NOT NULL "
     "AND credit_reversal_request_id IS NOT NULL AND credit_requested IS NOT NULL AND credit_applied IS NOT NULL "
     "AND credit_shortfall IS NOT NULL AND credit_applied + credit_shortfall = credit_requested "
     "AND credit_shortfall > 0 AND credit_applied >= 0 "
     "AND (credit_applied > 0) = (credit_reversal_entry_id IS NOT NULL))"),
    ("ck_billing_item_credit_late_settle",
     "kind <> 'credit_late_settle' OR (credit_account_id IS NOT NULL AND credit_reserve_entry_id IS NOT NULL "
     "AND credit_closing_entry_id IS NOT NULL AND credit_actual IS NOT NULL AND credit_actual >= 0)"),
    ("ck_billing_item_credit_drift",
     "kind <> 'credit_balance_drift' OR (credit_account_id IS NOT NULL AND credit_expected_posted IS NOT NULL "
     "AND credit_expected_reserved IS NOT NULL AND credit_snapshot_posted IS NOT NULL "
     "AND credit_snapshot_reserved IS NOT NULL AND (credit_expected_posted <> credit_snapshot_posted "
     "OR credit_expected_reserved <> credit_snapshot_reserved))"),
    ("ck_billing_item_credit_on_deletion",
     "kind <> 'credit_balance_on_deletion' OR (credit_account_id IS NOT NULL AND incarnation_id IS NOT NULL "
     "AND credit_balance_posted IS NOT NULL AND credit_balance_reserved IS NOT NULL AND credit_balance_posted > 0)"),
    # a drift is closed only by the reconciler, once the ledger and the snapshot agree again
    ("ck_billing_item_credit_drift_reconciler",
     "kind <> 'credit_balance_drift' OR state = 'open' "
     "OR (resolution_outcome = 'balance_consistent' AND resolved_by = 'reconciler')"),
    ("ck_billing_item_balance_consistent",
     "resolution_outcome IS DISTINCT FROM 'balance_consistent' OR resolved_by = 'reconciler'"),
]


def _superuser(connection) -> bool:
    return bool(connection.execute(sa.text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")).scalar())


def _prerequisites(connection, schema: str, q: str) -> None:
    """The roles and the executor's capability, validated before any credit DDL; fails closed (P1-1)."""

    superuser = _superuser(connection)
    missing = [role for role in (OWNER, RUNTIME)
               if not connection.execute(sa.text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": role}).first()]
    if missing:
        if not superuser:
            raise RuntimeError(f"0032 creates {', '.join(missing)} only as a superuser; otherwise provision them out of "
                               "band (NOLOGIN NOSUPERUSER NOBYPASSRLS) and make the executor a member of "
                               f"{OWNER} WITH SET")
        for role in missing:
            op.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS")
    for role in (OWNER, RUNTIME):
        login, super_, bypass = connection.execute(sa.text(
            "SELECT rolcanlogin, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :r"), {"r": role}).one()
        if login or super_ or bypass:
            raise RuntimeError(f"{role} must be NOLOGIN, NOSUPERUSER and NOBYPASSRLS; 0032 does not use it as it is")
    if connection.execute(sa.text("SELECT pg_has_role(:runtime, :owner, 'MEMBER')"),
                          {"runtime": RUNTIME, "owner": OWNER}).scalar():
        raise RuntimeError(f"{RUNTIME} must not be a member of {OWNER}")
    if superuser:
        return
    if not connection.execute(sa.text("SELECT pg_has_role(current_user, :owner, 'SET')"), {"owner": OWNER}).scalar():
        raise RuntimeError(f"a non-superuser executor must be a member of {OWNER} WITH SET to transfer ownership")
    if not connection.execute(sa.text("SELECT has_schema_privilege(:owner, :schema, 'CREATE')"),
                              {"owner": OWNER, "schema": schema}).scalar():
        owns_schema = connection.execute(sa.text(
            "SELECT pg_get_userbyid(nspowner) = current_user FROM pg_namespace WHERE nspname = :schema"),
            {"schema": schema}).scalar()  # fmt: skip
        if not owns_schema:
            raise RuntimeError(f"{OWNER} needs CREATE on schema {schema}, and the executor does not own it to grant it")
        op.execute(f"GRANT CREATE ON SCHEMA {q} TO {OWNER}")  # the new owner of a table needs CREATE on its schema


def upgrade() -> None:
    connection = op.get_bind()
    schema = connection.execute(sa.text("SELECT current_schema()")).scalar()
    q = '"' + schema.replace('"', '""') + '"'
    _prerequisites(connection, schema, q)

    # ---- credit_accounts ---------------------------------------------------------------------------------------
    op.create_table(
        "credit_accounts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("incarnation_id", sa.Uuid(), sa.ForeignKey("account_incarnations.id", ondelete="RESTRICT"),
                  nullable=False, unique=True),
        sa.Column("posted", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("reserved", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("entry_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("last_entry_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("posted >= 0 AND reserved >= 0 AND reserved <= posted AND entry_count >= 0",
                           name="ck_credit_account_balance"),
    )

    # ---- credit_reversal_requests (before the ledger, which references it) --------------------------------------
    op.create_table(
        "credit_reversal_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("credit_account_id", sa.Uuid(), sa.ForeignKey("credit_accounts.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("topup_entry_id", sa.Uuid(), nullable=False),  # FK added once the ledger exists
        sa.Column("idempotency_key", sa.String(250), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("requested", sa.BigInteger(), nullable=False),
        sa.Column("applied", sa.BigInteger(), nullable=False),
        sa.Column("shortfall", sa.BigInteger(), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_ref", sa.String(200), nullable=False),
        sa.Column("actor", sa.String(200), nullable=False),
        sa.Column("reason", sa.String(400), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_type", "source_ref", name="uq_credit_reversal_money_event"),
        sa.UniqueConstraint("credit_account_id", "idempotency_key", name="uq_credit_reversal_request_key"),
        sa.CheckConstraint("requested > 0 AND applied >= 0 AND shortfall >= 0 AND applied + shortfall = requested",
                           name="ck_credit_reversal_request_amounts"),
    )

    # ---- credit_ledger -------------------------------------------------------------------------------------------
    op.create_table(
        "credit_ledger",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("credit_account_id", sa.Uuid(), sa.ForeignKey("credit_accounts.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("seq", sa.BigInteger(), nullable=False, server_default="0"),  # assigned by the trigger
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("posted_delta", sa.BigInteger(), nullable=False),
        sa.Column("reserved_delta", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("ref_entry_id", sa.Uuid(), sa.ForeignKey("credit_ledger.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("reversal_request_id", sa.Uuid(),
                  sa.ForeignKey("credit_reversal_requests.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("idempotency_key", sa.String(250), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=True),
        sa.Column("source_ref", sa.String(200), nullable=True),
        sa.Column("meter", sa.String(80), nullable=True),
        sa.Column("operation_ref", sa.String(200), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uncharged", sa.BigInteger(), nullable=True),
        sa.Column("actor", sa.String(200), nullable=False),
        sa.Column("reason", sa.String(400), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("credit_account_id", "seq", name="uq_credit_ledger_seq"),
        sa.UniqueConstraint("credit_account_id", "kind", "idempotency_key", name="uq_credit_ledger_operation"),
        sa.CheckConstraint(f"kind IN ({_in(KINDS)})", name="ck_credit_ledger_kind"),
        sa.CheckConstraint("amount > 0", name="ck_credit_ledger_amount"),
        # Purchased credit never expires (C6): only a hold has an expiry.
        sa.CheckConstraint("(kind = 'reserve') = (expires_at IS NOT NULL)", name="ck_credit_ledger_expiry"),
        sa.CheckConstraint("(kind = 'reversal') = (reversal_request_id IS NOT NULL)",
                           name="ck_credit_ledger_reversal_request"),
        sa.CheckConstraint("(kind = 'settle') = (uncharged IS NOT NULL)", name="ck_credit_ledger_uncharged"),
        sa.CheckConstraint("(kind IN ('settle', 'release', 'reserve_expire', 'refund', 'reversal')) "
                           "= (ref_entry_id IS NOT NULL)", name="ck_credit_ledger_reference"),
        sa.CheckConstraint("(kind = 'topup') = (source_type IS NOT NULL AND source_ref IS NOT NULL)",
                           name="ck_credit_ledger_source"),
        sa.CheckConstraint("kind NOT IN ('refund', 'reversal', 'adjustment') OR reason IS NOT NULL",
                           name="ck_credit_ledger_reason"),
        # Each kind's effect on the balance (§4).
        sa.CheckConstraint(
            "(kind = 'topup' AND posted_delta = amount AND reserved_delta = 0) "
            "OR (kind = 'reserve' AND posted_delta = 0 AND reserved_delta = amount) "
            "OR (kind = 'settle' AND posted_delta <= 0 AND reserved_delta < 0 AND uncharged >= 0 "
            "    AND amount = -posted_delta + uncharged) "
            "OR (kind IN ('release', 'reserve_expire') AND posted_delta = 0 AND reserved_delta < 0) "
            "OR (kind = 'refund' AND posted_delta = amount AND reserved_delta = 0) "
            "OR (kind = 'reversal' AND posted_delta = -amount AND reserved_delta = 0) "
            "OR (kind = 'adjustment' AND abs(posted_delta) = amount AND reserved_delta = 0)",
            name="ck_credit_ledger_effect"),
    )
    op.create_foreign_key("fk_credit_reversal_request_topup", "credit_reversal_requests", "credit_ledger",
                          ["topup_entry_id"], ["id"], ondelete="RESTRICT")
    # One money event credits one account once; one hold closes once; one request has at most one entry.
    op.create_index("uq_credit_ledger_topup_source", "credit_ledger", ["source_type", "source_ref"], unique=True,
                    postgresql_where=sa.text("kind = 'topup'"))
    op.create_index("uq_credit_ledger_close_once", "credit_ledger", ["ref_entry_id"], unique=True,
                    postgresql_where=sa.text("kind IN ('settle', 'release', 'reserve_expire')"))
    op.create_index("uq_credit_ledger_reversal_request", "credit_ledger", ["reversal_request_id"], unique=True,
                    postgresql_where=sa.text("reversal_request_id IS NOT NULL"))
    op.create_index("ix_credit_ledger_ref", "credit_ledger", ["ref_entry_id"],
                    postgresql_where=sa.text("ref_entry_id IS NOT NULL"))
    op.create_index("ix_credit_ledger_open_holds", "credit_ledger", ["expires_at"],
                    postgresql_where=sa.text("kind = 'reserve'"))

    # ---- the only write path to the snapshot: a SECURITY DEFINER trigger function (P1-2) --------------------------
    op.execute(f"""
        CREATE FUNCTION {q}.credit_apply_entry() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = {q}, pg_catalog, pg_temp AS $$
        DECLARE
            acct {q}.credit_accounts%ROWTYPE;
            ref {q}.credit_ledger%ROWTYPE;
            req {q}.credit_reversal_requests%ROWTYPE;
            inc_id uuid;
            inc_status text;
            total bigint;
        BEGIN
            -- One lock order, the repository's (review P1-3): the incarnation FOR SHARE, which waits for and then
            -- excludes a concurrent deletion, then the credit account FOR UPDATE.
            SELECT incarnation_id INTO inc_id FROM {q}.credit_accounts WHERE id = NEW.credit_account_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'unknown credit account' USING ERRCODE = 'foreign_key_violation';
            END IF;
            SELECT status INTO inc_status FROM {q}.account_incarnations WHERE id = inc_id FOR SHARE;
            SELECT * INTO acct FROM {q}.credit_accounts WHERE id = NEW.credit_account_id FOR UPDATE;
            IF NEW.kind IN ('topup', 'reserve', 'settle') THEN
                IF inc_status IS DISTINCT FROM 'active' THEN
                    RAISE EXCEPTION 'a deleted account takes no new credit, hold or charge' USING ERRCODE = 'check_violation';
                END IF;
            END IF;
            IF NEW.ref_entry_id IS NOT NULL THEN
                SELECT * INTO ref FROM {q}.credit_ledger WHERE id = NEW.ref_entry_id;
                IF NOT FOUND OR ref.credit_account_id <> NEW.credit_account_id THEN
                    RAISE EXCEPTION 'an offset names an entry of its own account' USING ERRCODE = 'check_violation';
                END IF;
            END IF;
            IF NEW.kind IN ('settle', 'release', 'reserve_expire') THEN
                IF ref.kind <> 'reserve' OR NEW.reserved_delta <> -ref.amount THEN
                    RAISE EXCEPTION 'a close names a reserve and releases exactly its hold' USING ERRCODE = 'check_violation';
                END IF;
                IF NEW.kind = 'settle' AND (-NEW.posted_delta > ref.amount
                        OR (NEW.uncharged > 0 AND -NEW.posted_delta <> ref.amount)) THEN
                    RAISE EXCEPTION 'a settle charges at most its hold (C3)' USING ERRCODE = 'check_violation';
                END IF;
            ELSIF NEW.kind = 'refund' THEN
                IF ref.kind <> 'settle' THEN
                    RAISE EXCEPTION 'a refund names a settle' USING ERRCODE = 'check_violation';
                END IF;
                SELECT COALESCE(SUM(amount), 0) INTO total FROM {q}.credit_ledger
                    WHERE ref_entry_id = ref.id AND kind = 'refund';
                IF total + NEW.amount > -ref.posted_delta THEN
                    RAISE EXCEPTION 'refunds of a charge never exceed it' USING ERRCODE = 'check_violation';
                END IF;
            ELSIF NEW.kind = 'reversal' THEN
                IF ref.kind <> 'topup' THEN
                    RAISE EXCEPTION 'a reversal names a top-up' USING ERRCODE = 'check_violation';
                END IF;
                SELECT * INTO req FROM {q}.credit_reversal_requests WHERE id = NEW.reversal_request_id;
                IF NOT FOUND OR req.credit_account_id <> NEW.credit_account_id OR req.topup_entry_id <> ref.id
                        OR req.applied <> NEW.amount THEN
                    RAISE EXCEPTION 'a reversal applies exactly its request' USING ERRCODE = 'check_violation';
                END IF;
                SELECT COALESCE(SUM(amount), 0) INTO total FROM {q}.credit_ledger
                    WHERE ref_entry_id = ref.id AND kind = 'reversal';
                IF total + NEW.amount > ref.amount THEN
                    RAISE EXCEPTION 'reversals of a top-up never exceed it' USING ERRCODE = 'check_violation';
                END IF;
            END IF;
            NEW.seq := acct.entry_count + 1;
            UPDATE {q}.credit_accounts SET posted = posted + NEW.posted_delta, reserved = reserved + NEW.reserved_delta,
                   entry_count = entry_count + 1, last_entry_id = NEW.id, updated_at = NEW.created_at
             WHERE id = acct.id;
            RETURN NEW;
        END $$
    """)
    op.execute(f"""
        CREATE FUNCTION {q}.credit_check_reversal_request() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = {q}, pg_catalog, pg_temp AS $$
        DECLARE
            acct {q}.credit_accounts%ROWTYPE;
            topup {q}.credit_ledger%ROWTYPE;
            reversed bigint;
        BEGIN
            PERFORM 1 FROM {q}.account_incarnations i JOIN {q}.credit_accounts a ON a.incarnation_id = i.id
                WHERE a.id = NEW.credit_account_id FOR SHARE OF i;  -- the same lock order (P1-3)
            SELECT * INTO acct FROM {q}.credit_accounts WHERE id = NEW.credit_account_id FOR UPDATE;
            SELECT * INTO topup FROM {q}.credit_ledger WHERE id = NEW.topup_entry_id;
            IF NOT FOUND OR topup.kind <> 'topup' OR topup.credit_account_id <> NEW.credit_account_id THEN
                RAISE EXCEPTION 'a reversal request names a top-up of its own account' USING ERRCODE = 'check_violation';
            END IF;
            SELECT COALESCE(SUM(amount), 0) INTO reversed FROM {q}.credit_ledger
                WHERE ref_entry_id = topup.id AND kind = 'reversal';
            -- applied = min(requested, available, remaining reversible), decided once (C5, P1-3)
            IF NEW.applied <> LEAST(NEW.requested, acct.posted - acct.reserved, topup.amount - reversed) THEN
                RAISE EXCEPTION 'a reversal applies min(requested, available, remaining reversible)'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute(f"""
        CREATE FUNCTION {q}.credit_refuse_change() RETURNS trigger LANGUAGE plpgsql
        SET search_path = {q}, pg_catalog, pg_temp AS $$
        BEGIN
            RAISE EXCEPTION '% is append-only financial history: % refused', TG_TABLE_NAME, TG_OP
                USING ERRCODE = 'restrict_violation';
        END $$
    """)
    op.execute(f"""
        CREATE FUNCTION {q}.credit_account_guard() RETURNS trigger LANGUAGE plpgsql
        SET search_path = {q}, pg_catalog, pg_temp AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'a credit account is never deleted' USING ERRCODE = 'restrict_violation';
            END IF;
            IF NEW.id IS DISTINCT FROM OLD.id OR NEW.incarnation_id IS DISTINCT FROM OLD.incarnation_id THEN
                RAISE EXCEPTION 'a credit account never changes owner' USING ERRCODE = 'restrict_violation';
            END IF;
            -- defense in depth (the privileges are the boundary): only the ledger function writes the snapshot
            IF (NEW.posted IS DISTINCT FROM OLD.posted OR NEW.reserved IS DISTINCT FROM OLD.reserved
                    OR NEW.entry_count IS DISTINCT FROM OLD.entry_count
                    OR NEW.last_entry_id IS DISTINCT FROM OLD.last_entry_id)
                    AND current_user <> '{OWNER}' THEN
                RAISE EXCEPTION 'a credit balance changes only through the ledger' USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute("CREATE TRIGGER credit_apply_entry BEFORE INSERT ON credit_ledger "
               "FOR EACH ROW EXECUTE FUNCTION credit_apply_entry()")
    op.execute("CREATE TRIGGER credit_check_reversal_request BEFORE INSERT ON credit_reversal_requests "
               "FOR EACH ROW EXECUTE FUNCTION credit_check_reversal_request()")
    for table in ("credit_ledger", "credit_reversal_requests"):
        op.execute(f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
                   "FOR EACH ROW EXECUTE FUNCTION credit_refuse_change()")
    for table in ("credit_ledger", "credit_reversal_requests", "credit_accounts"):
        op.execute(f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
                   "FOR EACH STATEMENT EXECUTE FUNCTION credit_refuse_change()")
    op.execute("CREATE TRIGGER credit_accounts_guard BEFORE UPDATE OR DELETE ON credit_accounts "
               "FOR EACH ROW EXECUTE FUNCTION credit_account_guard()")

    # ---- billing_reconciliation_items: the credit references (P1-6) -----------------------------------------------
    for column, table in CREDIT_COLUMNS:
        op.add_column("billing_reconciliation_items",
                      sa.Column(column, sa.Uuid(), sa.ForeignKey(f"{table}.id", ondelete="RESTRICT"), nullable=True))
    for column in CREDIT_AMOUNTS:
        op.add_column("billing_reconciliation_items", sa.Column(column, sa.BigInteger(), nullable=True))
    for name, _ in ITEM_CHECKS_0031:
        op.drop_constraint(name, "billing_reconciliation_items", type_="check")
    for name, condition in ITEM_CHECKS_0032 + CREDIT_ITEM_CHECKS:
        op.create_check_constraint(name, "billing_reconciliation_items", condition)
    op.create_index("ix_billing_items_open_credit_account", "billing_reconciliation_items", ["credit_account_id"],
                    postgresql_where=sa.text("state = 'open' AND credit_account_id IS NOT NULL"))
    op.execute(_item_guard_sql(CRITICAL_0031 + CREDIT_CRITICAL, FACTS_0031 + CREDIT_FACTS))

    # ---- ownership and privileges ----------------------------------------------------------------------------------
    op.execute(f"REVOKE CREATE ON SCHEMA {q} FROM PUBLIC")
    op.execute(f"GRANT USAGE ON SCHEMA {q} TO {OWNER}, {RUNTIME}")
    op.execute(f"REVOKE CREATE ON SCHEMA {q} FROM {RUNTIME}")
    # The trigger reads an incarnation's status under FOR SHARE (P1-3). A row lock needs UPDATE on at least one
    # column; `created_at` is granted for that alone - no function of the owner updates an incarnation.
    op.execute(f"GRANT SELECT, UPDATE (created_at) ON {q}.account_incarnations TO {OWNER}")
    for table in ("credit_accounts", "credit_ledger", "credit_reversal_requests"):
        op.execute(f"ALTER TABLE {q}.{table} OWNER TO {OWNER}")
        op.execute(f"REVOKE ALL ON {q}.{table} FROM PUBLIC")
    for function in ("credit_apply_entry()", "credit_check_reversal_request()", "credit_refuse_change()",
                     "credit_account_guard()"):
        op.execute(f"ALTER FUNCTION {q}.{function} OWNER TO {OWNER}")
        op.execute(f"REVOKE EXECUTE ON FUNCTION {q}.{function} FROM PUBLIC")
    op.execute(f"GRANT SELECT ON {q}.credit_accounts TO {RUNTIME}")
    op.execute(f"GRANT INSERT (id, incarnation_id, created_at, updated_at) ON {q}.credit_accounts TO {RUNTIME}")
    op.execute(f"GRANT UPDATE (updated_at) ON {q}.credit_accounts TO {RUNTIME}")  # the row lock needs it
    op.execute(f"GRANT SELECT, INSERT ON {q}.credit_ledger, {q}.credit_reversal_requests TO {RUNTIME}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON {q}.billing_reconciliation_items TO {RUNTIME}")


def downgrade() -> None:
    connection = op.get_bind()
    schema = connection.execute(sa.text("SELECT current_schema()")).scalar()
    q = '"' + schema.replace('"', '""') + '"'
    for table in ("credit_ledger", "credit_accounts", "credit_reversal_requests"):
        if connection.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM {q}.{table})")).scalar():
            raise RuntimeError(f"{table} holds financial records; this revision is not downgraded over them")
    if connection.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM {q}.billing_reconciliation_items "
                                  f"WHERE kind IN ({_in(CREDIT_KINDS)}))")).scalar():
        raise RuntimeError("credit reconciliation items exist; this revision is not downgraded over them")
    op.execute(_item_guard_sql(CRITICAL_0031, FACTS_0031))
    op.drop_index("ix_billing_items_open_credit_account", table_name="billing_reconciliation_items")
    for name, _ in ITEM_CHECKS_0032 + CREDIT_ITEM_CHECKS:
        op.drop_constraint(name, "billing_reconciliation_items", type_="check")
    for name, condition in ITEM_CHECKS_0031:
        op.create_check_constraint(name, "billing_reconciliation_items", condition)
    for column in reversed(CREDIT_FACTS):
        op.drop_column("billing_reconciliation_items", column)
    op.execute(f"REVOKE ALL ON {q}.billing_reconciliation_items FROM {RUNTIME}")
    op.execute(f"REVOKE ALL ON {q}.account_incarnations FROM {OWNER}")
    op.drop_constraint("fk_credit_reversal_request_topup", "credit_reversal_requests", type_="foreignkey")
    for table in ("credit_ledger", "credit_reversal_requests", "credit_accounts"):
        op.execute(f"DROP TABLE {q}.{table}")
    for function in ("credit_apply_entry()", "credit_check_reversal_request()", "credit_refuse_change()",
                     "credit_account_guard()"):
        op.execute(f"DROP FUNCTION {q}.{function}")
    op.execute(f"REVOKE ALL ON SCHEMA {q} FROM {OWNER}, {RUNTIME}")
    if not _superuser(connection):
        return  # provisioned out of band: the roles stay with whoever provisioned them
    # Roles are cluster-wide: dropped only when nothing anywhere still depends on them.
    for role in (RUNTIME, OWNER):
        op.execute(f"""DO $$ BEGIN
            DROP ROLE IF EXISTS {role};
        EXCEPTION WHEN dependent_objects_still_exist THEN NULL;
        END $$""")
