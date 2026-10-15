"""Funding admissions, promotional grants and cost attribution (PR-MON-6; docs/billing/PR-MON-6_DESIGN.md revision 2,
APPROVED FOR IMPLEMENTATION / MIGRATION GATE 2026-10-15 on `418e937e`; D-MON-023). Design §5.6 and §11.

- `funding_admissions`: one row per admitted learner operation, the durable half of I-1 ("no funded admission, no
  paid-provider call"). `operation_id` is unique (the serialization point, §5.6); identity and intent, with the
  request digest, never change; the funding snapshot (source, price, amount, policy, cost gate, the one backing
  reservation) is written once, in the transaction that makes the row `funded`, and never changes; the state only
  moves forward (admitting -> funded | refused; funded -> dispatched | settled | released; dispatched -> settled |
  released). A `SECURITY DEFINER` guard owned by `orena_credit_owner` checks each transition against the backing
  reservation, so a row is `funded` only over its own open, exact hold or quota reservation (key `fund:<operation>`),
  `settled` only over the backing's settle with the snapshot's charge, `released` only over its release or expiry,
  and `refused` only while no open, exact backing exists (§5.6, crash table). A deleted account is never admitted.
- `promotional_grants`: the claimed instance of a configured grant (H-8: no grant is configured). Unique
  `(grant_id, user_id)`: `users` is the account row that survives delete-and-re-register (the incarnation barrier,
  D-054/D-055), so a grant is claimed once per person, ever (R-MON-003). Immutable and never deleted. Its usage is not
  a new table: it is 0007's quota bucket, marked with `promotional_grant_id`, whose window is the grant's
  (`promo:<grant>`, claimed_at -> expires_at) and whose reservations are 0007's - the quota system is extended, not
  replaced (§11).
- `ai_cost_records` (0026) gains nullable `operation_id` and `meter`, both or neither (§8). No foreign key: the cost
  record keeps its 13-month sweep and account deletion, and a system-funded call has no admission.
- `billing_reconciliation_items` gains `funding_admission_conflict` (critical, reconciler-only), for a non-exact
  reservation keyed `fund:<operation>` that was never adopted (§5.6). It closes only as `stray_released`, which the
  guard checks: the admission is `refused` and nothing keyed `fund:<operation>` is still open.

Topology (the one-transaction precondition of §5.6): the quota tables, the credit tables and the new tables must be in
one PostgreSQL database and schema; the foreign keys make that structural, and the upgrade refuses before any DDL if a
table is missing. The new tables and functions belong to `orena_credit_owner` (0032's roles, validated again here); the
runtime, through `orena_credit_runtime`, may insert an admission's identity and update only its lifecycle and snapshot
columns, and may only insert a grant. Lock order (§5.6): the admission row, then the incarnation FOR SHARE (taken by
the guard on `funded`), then the bucket or the credit account (taken by their own writers).

0034 reuses 0032's and 0033's builders (loaded from their files), so the downgrade restores 0033 exactly.

Review and gate. A PROPOSAL in `migrations/proposed/` (Alembic does not read it). Order ... -> 0033 -> 0034. Startup
never applies it; promotion and application are human gates. `downgrade()` refuses while any admission, grant,
promotional bucket, attributed cost record or conflict item exists; it exists for rehearsal only.

Revision ID: 20261015_0034
Revises: 20261015_0033
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "20261015_0034"
down_revision = "20261015_0033"
branch_labels = None
depends_on = None

_M33_NAME = "20261015_0033_credit_topup_orders.py"


def _load_0033():
    here = Path(__file__)
    path = here.with_name(_M33_NAME)  # once promoted, 0033 sits beside it in versions/
    if not path.exists():
        path = here.parent.parent / "versions" / _M33_NAME
    spec = importlib.util.spec_from_file_location("orena_migration_0033", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M33 = _load_0033()
M32 = M33.M32
_in = M32._in
OWNER, RUNTIME = M32.OWNER, M32.RUNTIME

STATES = ("admitting", "funded", "dispatched", "settled", "released", "refused")
TERMINAL = ("settled", "released", "refused")
SOURCES = ("allowance", "promotional", "credits")
IDENTITY = ("id", "operation_id", "incarnation_id", "meter", "units", "operation_ref", "feature", "unit_granularity",
            "request_digest", "created_at")
SNAPSHOT = ("source", "price_per_unit", "amount_reserved", "policy_version", "cost_gate_id", "quota_reservation_id",
            "credit_reserve_entry_id", "funded_at")
LIFECYCLE = ("state", "dispatched_at", "settled_units", "settled_amount", "refusal_reason", "closed_at")
REQUIRED_TABLES = ("account_incarnations", "users", "commerce_quota_buckets", "commerce_quota_reservations",
                   "credit_accounts", "credit_ledger", "billing_reconciliation_items", "ai_cost_records")

ADMISSION_CHECKS = [
    ("ck_funding_state", f"state IN ({_in(STATES)})"),
    ("ck_funding_source", f"source IS NULL OR source IN ({_in(SOURCES)})"),
    # the backing key `fund:<operation>` fits 0007's operation_id (200) and the ledger's idempotency key (250)
    ("ck_funding_identity", "length(operation_id) BETWEEN 1 AND 190 AND units > 0 AND unit_granularity > 0 "
                            "AND request_digest ~ '^[0-9a-f]{64}$'"),
    ("ck_funding_unfunded",
     "state NOT IN ('admitting', 'refused') OR (" + " AND ".join(f"{c} IS NULL" for c in SNAPSHOT + (
         "dispatched_at", "settled_units", "settled_amount")) + ")"),
    ("ck_funding_snapshot",
     "state IN ('admitting', 'refused') OR (source IS NOT NULL AND policy_version IS NOT NULL AND funded_at IS NOT NULL "
     "AND ((source = 'credits' AND credit_reserve_entry_id IS NOT NULL AND quota_reservation_id IS NULL "
     "      AND price_per_unit > 0 AND amount_reserved = price_per_unit * units AND cost_gate_id IS NOT NULL) "
     "  OR (source IN ('allowance', 'promotional') AND quota_reservation_id IS NOT NULL "
     "      AND credit_reserve_entry_id IS NULL AND price_per_unit IS NULL AND amount_reserved IS NULL "
     "      AND cost_gate_id IS NULL)))"),
    ("ck_funding_dispatched",
     "state IN ('settled', 'released') OR (state = 'dispatched') = (dispatched_at IS NOT NULL)"),
    ("ck_funding_closed", f"(state IN ({_in(TERMINAL)})) = (closed_at IS NOT NULL)"),
    ("ck_funding_refused", "(state = 'refused') = (refusal_reason IS NOT NULL)"),
    # a zero outcome is a release, never a settle; credits settle exactly the snapshot price per settled unit
    ("ck_funding_settled",
     "(state = 'settled' AND settled_units BETWEEN 1 AND units AND ((source = 'credits' "
     "  AND settled_amount = price_per_unit * settled_units) OR (source <> 'credits' AND settled_amount IS NULL))) "
     "OR (state <> 'settled' AND settled_units IS NULL AND settled_amount IS NULL)"),
]

CONFLICT = "funding_admission_conflict"
CONFLICT_OUTCOME = "stray_released"
_KINDS_0033 = M32.CRITICAL_0031 + M32.MONEY_0031 + M32.DISMISSABLE_0031 + M33.CREDIT_KINDS
_DISMISSABLE = M32.DISMISSABLE_0031 + M32.CREDIT_DISMISSABLE
_OUTCOMES_0033 = M32.OUTCOMES_0031 + ("balance_consistent",) + M33.TOPUP_OUTCOMES + M33.REVERSAL_OUTCOMES
_REQUIRED_0033 = (M32.CRITICAL_0031 + M32.MONEY_0031 + M32.CREDIT_CRITICAL + M32.CREDIT_MONEY + M33.NEW_CRITICAL)
assert M32._item_checks(_KINDS_0033, _DISMISSABLE, _OUTCOMES_0033, _REQUIRED_0033) == M33.ITEM_CHECKS_0033
ITEM_CHECKS_0034 = M32._item_checks(_KINDS_0033 + (CONFLICT,), _DISMISSABLE, _OUTCOMES_0033 + (CONFLICT_OUTCOME,),
                                    _REQUIRED_0033 + (CONFLICT,))
CONFLICT_ITEM_CHECKS = [
    ("ck_billing_item_funding_conflict",
     f"(kind = '{CONFLICT}') = (funding_admission_id IS NOT NULL) AND (kind <> '{CONFLICT}' "
     "OR (gateway = 'funding' AND dedupe_key = funding_admission_id::text))"),
    ("ck_billing_item_funding_outcome",
     f"kind <> '{CONFLICT}' OR state = 'open' OR (resolved_by = 'reconciler' AND resolution_outcome = '{CONFLICT_OUTCOME}')"),
    ("ck_billing_item_stray_released",
     f"resolution_outcome IS DISTINCT FROM '{CONFLICT_OUTCOME}' OR (kind = '{CONFLICT}' AND resolved_by = 'reconciler')"),
]
_STRAY_RELEASED = f"""
            -- PR-MON-6 §5.6: a funding conflict closes only once its admission is refused and nothing keyed
            -- `fund:<operation>` is still open, in the credit ledger or the quota reservations.
            IF OLD.state = 'open' AND NEW.state = 'resolved' AND NEW.resolution_outcome = '{CONFLICT_OUTCOME}'
                    AND NOT EXISTS (SELECT 1 FROM funding_admissions f WHERE f.id = NEW.funding_admission_id
                        AND f.state = 'refused'
                        AND NOT EXISTS (SELECT 1 FROM credit_ledger l JOIN credit_accounts a ON a.id = l.credit_account_id
                            WHERE a.incarnation_id = f.incarnation_id AND l.kind = 'reserve'
                              AND l.idempotency_key = 'fund:' || f.operation_id
                              AND NOT EXISTS (SELECT 1 FROM credit_ledger c WHERE c.ref_entry_id = l.id
                                              AND c.kind IN ('settle', 'release', 'reserve_expire')))
                        AND NOT EXISTS (SELECT 1 FROM commerce_quota_reservations r
                            WHERE r.operation_id = 'fund:' || f.operation_id AND r.state IN ('reserved', 'dispatched'))) THEN
                RAISE EXCEPTION 'stray_released needs a refused admission with nothing still open'
                    USING ERRCODE = 'check_violation';
            END IF;"""


def _item_guard_0034() -> str:
    base = M32._item_guard_sql(M33.CRITICAL + (CONFLICT,), M32.FACTS_0031 + M32.CREDIT_FACTS + ("funding_admission_id",))
    marker = "\n            IF OLD.state <> 'open' THEN"
    assert base.count(marker) == 1 and M33._OUTCOME_FACTS.endswith(marker)
    facts = M33._OUTCOME_FACTS[: -len(marker)] + _STRAY_RELEASED + marker
    return base.replace(marker, facts, 1)


def _changed(columns) -> str:
    return " OR ".join(f"NEW.{c} IS DISTINCT FROM OLD.{c}" for c in columns)


def _admission_guard(q: str) -> str:
    # The exact backing (§5.6): keyed `fund:<operation>`, of this incarnation and meter, with the snapshot's amount.
    hold = (f"SELECT 1 FROM {q}.credit_ledger l WHERE l.id = NEW.credit_reserve_entry_id AND l.kind = 'reserve' "
            f"AND l.credit_account_id = (SELECT id FROM {q}.credit_accounts WHERE incarnation_id = NEW.incarnation_id) "
            "AND l.idempotency_key = fund_key AND l.meter = NEW.meter AND l.operation_ref = NEW.operation_ref "
            "AND l.amount = NEW.amount_reserved")
    open_hold = (f"NOT EXISTS (SELECT 1 FROM {q}.credit_ledger c WHERE c.ref_entry_id = NEW.credit_reserve_entry_id "
                 "AND c.kind IN ('settle', 'release', 'reserve_expire'))")
    reservation = (f"SELECT r.state, r.actual_units, r.admitted_units, r.operation_id, b.incarnation_id, b.meter, "
                   f"b.promotional_grant_id FROM {q}.commerce_quota_reservations r "
                   f"JOIN {q}.commerce_quota_buckets b ON b.id = r.bucket_id WHERE r.id = NEW.quota_reservation_id")
    return f"""
        CREATE FUNCTION {q}.funding_admission_guard() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = {q}, pg_catalog, pg_temp AS $$
        DECLARE
            fund_key text;
            inc_status text;
            res record;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'a funding admission is never deleted' USING ERRCODE = 'restrict_violation';
            END IF;
            fund_key := 'fund:' || NEW.operation_id;
            IF TG_OP = 'INSERT' THEN
                IF NEW.state <> 'admitting' THEN
                    RAISE EXCEPTION 'an admission starts admitting' USING ERRCODE = 'check_violation';
                END IF;
                SELECT status INTO inc_status FROM {q}.account_incarnations WHERE id = NEW.incarnation_id;
                IF inc_status IS DISTINCT FROM 'active' THEN
                    RAISE EXCEPTION 'a deleted account is never admitted' USING ERRCODE = 'check_violation';
                END IF;
                RETURN NEW;
            END IF;
            IF {_changed(IDENTITY)} THEN
                RAISE EXCEPTION 'an admission''s identity and intent never change' USING ERRCODE = 'restrict_violation';
            END IF;
            IF NEW.state = OLD.state THEN
                IF NEW IS DISTINCT FROM OLD THEN
                    RAISE EXCEPTION 'an admission changes only by a forward transition' USING ERRCODE = 'restrict_violation';
                END IF;
                RETURN NEW;
            END IF;
            IF NOT ((OLD.state = 'admitting' AND NEW.state IN ('funded', 'refused'))
                    OR (OLD.state = 'funded' AND NEW.state IN ('dispatched', 'settled', 'released'))
                    OR (OLD.state = 'dispatched' AND NEW.state IN ('settled', 'released'))) THEN
                RAISE EXCEPTION 'admission % -> % is not a forward transition', OLD.state, NEW.state
                    USING ERRCODE = 'restrict_violation';
            END IF;
            IF OLD.state <> 'admitting' AND ({_changed(SNAPSHOT)}) THEN
                RAISE EXCEPTION 'the funding snapshot never changes' USING ERRCODE = 'restrict_violation';
            END IF;
            IF NEW.dispatched_at IS DISTINCT FROM OLD.dispatched_at AND NEW.state <> 'dispatched' THEN
                RAISE EXCEPTION 'dispatched_at is written only by funded -> dispatched' USING ERRCODE = 'restrict_violation';
            END IF;

            IF NEW.state = 'funded' THEN
                -- the canonical order: this row is locked; now the incarnation FOR SHARE (C1 mirrored)
                SELECT status INTO inc_status FROM {q}.account_incarnations WHERE id = NEW.incarnation_id FOR SHARE;
                IF inc_status IS DISTINCT FROM 'active' THEN
                    RAISE EXCEPTION 'a deleted account is never admitted' USING ERRCODE = 'check_violation';
                END IF;
                IF NEW.source = 'credits' THEN
                    IF NOT EXISTS ({hold} AND l.expires_at > now()) OR NOT {open_hold} THEN
                        RAISE EXCEPTION 'a credits admission is backed by its own open, exact hold'
                            USING ERRCODE = 'check_violation';
                    END IF;
                ELSE
                    {reservation} INTO res;
                    IF NOT FOUND OR res.operation_id <> fund_key OR res.admitted_units <> NEW.units
                            OR res.state <> 'reserved' OR res.incarnation_id <> NEW.incarnation_id
                            OR res.meter <> NEW.meter
                            OR (res.promotional_grant_id IS NOT NULL) <> (NEW.source = 'promotional') THEN
                        RAISE EXCEPTION 'an allowance admission is backed by its own open, exact quota reservation'
                            USING ERRCODE = 'check_violation';
                    END IF;
                END IF;
            ELSIF NEW.state = 'dispatched' THEN
                IF NEW.source = 'credits' THEN
                    IF NOT EXISTS ({hold} AND l.expires_at > now()) OR NOT {open_hold} THEN
                        RAISE EXCEPTION 'a dispatch needs its hold still open' USING ERRCODE = 'check_violation';
                    END IF;
                ELSE
                    {reservation} INTO res;
                    IF res.state NOT IN ('reserved', 'dispatched') THEN
                        RAISE EXCEPTION 'a dispatch needs its quota reservation still open' USING ERRCODE = 'check_violation';
                    END IF;
                END IF;
            ELSIF NEW.state = 'settled' THEN
                IF NEW.source = 'credits' THEN
                    IF NOT EXISTS (SELECT 1 FROM {q}.credit_ledger c WHERE c.ref_entry_id = NEW.credit_reserve_entry_id
                                   AND c.kind = 'settle' AND -c.posted_delta = NEW.settled_amount) THEN
                        RAISE EXCEPTION 'a credits admission settles over its hold''s settle, at the snapshot price'
                            USING ERRCODE = 'check_violation';
                    END IF;
                ELSE
                    {reservation} INTO res;
                    IF res.state <> 'settled' OR res.actual_units <> NEW.settled_units THEN
                        RAISE EXCEPTION 'an allowance admission settles over its settled quota reservation'
                            USING ERRCODE = 'check_violation';
                    END IF;
                END IF;
            ELSIF NEW.state = 'released' THEN
                IF NEW.source = 'credits' THEN
                    IF NOT EXISTS (SELECT 1 FROM {q}.credit_ledger c WHERE c.ref_entry_id = NEW.credit_reserve_entry_id
                                   AND (c.kind IN ('release', 'reserve_expire') OR (c.kind = 'settle' AND c.posted_delta = 0))) THEN
                        RAISE EXCEPTION 'a credits admission is released over its hold''s release or expiry'
                            USING ERRCODE = 'check_violation';
                    END IF;
                ELSE
                    {reservation} INTO res;
                    IF NOT (res.state = 'released' OR (res.state = 'settled' AND res.actual_units = 0)) THEN
                        RAISE EXCEPTION 'an allowance admission is released over its released quota reservation'
                            USING ERRCODE = 'check_violation';
                    END IF;
                END IF;
            ELSIF NEW.state = 'refused' THEN
                -- refused only while no open, exact backing exists (§5.6: an exact one is adopted, never orphaned)
                IF EXISTS (SELECT 1 FROM {q}.credit_ledger l
                           WHERE l.credit_account_id = (SELECT id FROM {q}.credit_accounts
                                                        WHERE incarnation_id = NEW.incarnation_id)
                             AND l.kind = 'reserve' AND l.idempotency_key = fund_key AND l.meter = NEW.meter
                             AND l.operation_ref = NEW.operation_ref
                             AND NOT EXISTS (SELECT 1 FROM {q}.credit_ledger c WHERE c.ref_entry_id = l.id
                                             AND c.kind IN ('settle', 'release', 'reserve_expire')))
                        OR EXISTS (SELECT 1 FROM {q}.commerce_quota_reservations r
                                   JOIN {q}.commerce_quota_buckets b ON b.id = r.bucket_id
                                   WHERE r.operation_id = fund_key AND r.admitted_units = NEW.units
                                     AND r.state IN ('reserved', 'dispatched') AND b.incarnation_id = NEW.incarnation_id
                                     AND b.meter = NEW.meter) THEN
                    RAISE EXCEPTION 'an admission with an open, exact backing is adopted, never refused'
                        USING ERRCODE = 'check_violation';
                END IF;
            END IF;
            RETURN NEW;
        END $$
    """


def _grant_guard(q: str) -> str:
    return f"""
        CREATE FUNCTION {q}.promotional_grant_guard() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = {q}, pg_catalog, pg_temp AS $$
        DECLARE
            inc record;
        BEGIN
            IF TG_OP <> 'INSERT' THEN
                RAISE EXCEPTION 'a promotional grant is immutable and never deleted: % refused', TG_OP
                    USING ERRCODE = 'restrict_violation';
            END IF;
            SELECT user_id, status INTO inc FROM {q}.account_incarnations WHERE id = NEW.incarnation_id FOR SHARE;
            IF NOT FOUND OR inc.user_id <> NEW.user_id OR inc.status <> 'active' THEN
                RAISE EXCEPTION 'a grant is claimed by an active incarnation of its own account'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END $$
    """


def _bucket_guard(q: str) -> str:
    frozen = ("promotional_grant_id", "incarnation_id", "meter", "window_id", "window_start", "window_end",
              "unit_limit")
    return f"""
        CREATE FUNCTION {q}.quota_bucket_promotional_guard() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = {q}, pg_catalog, pg_temp AS $$
        DECLARE
            g {q}.promotional_grants%ROWTYPE;
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                IF (OLD.promotional_grant_id IS NOT NULL OR NEW.promotional_grant_id IS NOT NULL)
                        AND ({_changed(frozen)}) THEN
                    RAISE EXCEPTION 'a promotional bucket''s grant, owner and window never change'
                        USING ERRCODE = 'restrict_violation';
                END IF;
                RETURN NEW;
            END IF;
            IF NEW.promotional_grant_id IS NOT NULL THEN
                SELECT * INTO g FROM {q}.promotional_grants WHERE id = NEW.promotional_grant_id;
                IF NOT FOUND OR g.incarnation_id <> NEW.incarnation_id OR g.claimed_at <> NEW.window_start
                        OR g.expires_at <> NEW.window_end THEN
                    RAISE EXCEPTION 'a promotional bucket is its grant''s, over the grant''s window'
                        USING ERRCODE = 'check_violation';
                END IF;
            END IF;
            RETURN NEW;
        END $$
    """


FUNCTIONS = ("funding_admission_guard()", "promotional_grant_guard()", "quota_bucket_promotional_guard()")


def upgrade() -> None:
    connection = op.get_bind()
    schema = connection.execute(sa.text("SELECT current_schema()")).scalar()
    q = '"' + schema.replace('"', '""') + '"'
    missing = [t for t in REQUIRED_TABLES
               if connection.execute(sa.text("SELECT to_regclass(:t)"), {"t": f"{q}.{t}"}).scalar() is None]
    if missing:
        raise RuntimeError(f"0034 needs {', '.join(missing)} in schema {schema}: admission, quota and credit tables "
                           "share one database and one transaction (PR-MON-6 §5.6)")
    M32._prerequisites(connection, schema, q)

    # ---- promotional_grants -------------------------------------------------------------------------------------
    op.create_table(
        "promotional_grants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("grant_id", sa.String(40), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("incarnation_id", sa.Uuid(), sa.ForeignKey("account_incarnations.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("grant_id", "user_id", name="uq_promotional_grant_once_per_account"),
        sa.CheckConstraint("length(grant_id) >= 1 AND expires_at > claimed_at", name="ck_promotional_grant"),
    )
    op.create_index("ix_promotional_grants_incarnation", "promotional_grants", ["incarnation_id"])

    # ---- 0007's bucket carries a grant's allowance ----------------------------------------------------------------
    op.add_column("commerce_quota_buckets",
                  sa.Column("promotional_grant_id", sa.Uuid(),
                            sa.ForeignKey("promotional_grants.id", ondelete="RESTRICT"), nullable=True))
    op.create_check_constraint(
        "ck_commerce_quota_bucket_promotional", "commerce_quota_buckets",
        "(promotional_grant_id IS NULL AND window_id NOT LIKE 'promo:%') OR (promotional_grant_id IS NOT NULL "
        "AND window_id = 'promo:' || promotional_grant_id::text AND unit_limit IS NOT NULL)")
    op.create_index("ix_commerce_quota_buckets_promotional", "commerce_quota_buckets", ["promotional_grant_id"],
                    postgresql_where=sa.text("promotional_grant_id IS NOT NULL"))

    # ---- funding_admissions -------------------------------------------------------------------------------------
    op.create_table(
        "funding_admissions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("operation_id", sa.String(190), nullable=False),
        sa.Column("incarnation_id", sa.Uuid(), sa.ForeignKey("account_incarnations.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("meter", sa.String(80), nullable=False),
        sa.Column("units", sa.BigInteger(), nullable=False),
        sa.Column("operation_ref", sa.String(200), nullable=False),
        sa.Column("feature", sa.String(80), nullable=False),
        sa.Column("unit_granularity", sa.Integer(), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("state", sa.String(12), nullable=False, server_default="admitting"),
        sa.Column("source", sa.String(12), nullable=True),
        sa.Column("price_per_unit", sa.BigInteger(), nullable=True),
        sa.Column("amount_reserved", sa.BigInteger(), nullable=True),
        sa.Column("policy_version", sa.String(120), nullable=True),
        sa.Column("cost_gate_id", sa.String(80), nullable=True),
        sa.Column("quota_reservation_id", sa.Uuid(),
                  sa.ForeignKey("commerce_quota_reservations.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("credit_reserve_entry_id", sa.Uuid(), sa.ForeignKey("credit_ledger.id", ondelete="RESTRICT"),
                  nullable=True),
        sa.Column("settled_units", sa.BigInteger(), nullable=True),
        sa.Column("settled_amount", sa.BigInteger(), nullable=True),
        sa.Column("refusal_reason", sa.String(40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("funded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("operation_id", name="uq_funding_admission_operation"),
        *(sa.CheckConstraint(condition, name=name) for name, condition in ADMISSION_CHECKS),
    )
    # one backing reservation funds one admission
    op.create_index("uq_funding_admission_quota", "funding_admissions", ["quota_reservation_id"], unique=True,
                    postgresql_where=sa.text("quota_reservation_id IS NOT NULL"))
    op.create_index("uq_funding_admission_hold", "funding_admissions", ["credit_reserve_entry_id"], unique=True,
                    postgresql_where=sa.text("credit_reserve_entry_id IS NOT NULL"))
    op.create_index("ix_funding_admissions_open", "funding_admissions", ["state", "created_at"],
                    postgresql_where=sa.text("state IN ('admitting', 'funded', 'dispatched')"))
    op.create_index("ix_funding_admissions_incarnation", "funding_admissions", ["incarnation_id"])

    # ---- ai_cost_records: attribution (§8) ------------------------------------------------------------------------
    op.add_column("ai_cost_records", sa.Column("operation_id", sa.String(200), nullable=True))
    op.add_column("ai_cost_records", sa.Column("meter", sa.String(80), nullable=True))
    op.create_check_constraint("ck_ai_cost_attribution", "ai_cost_records", "(operation_id IS NULL) = (meter IS NULL)")
    op.create_index("ix_ai_cost_records_operation", "ai_cost_records", ["operation_id", "meter"],
                    postgresql_where=sa.text("operation_id IS NOT NULL"))

    # ---- billing_reconciliation_items: the funding conflict -----------------------------------------------------------
    op.add_column("billing_reconciliation_items",
                  sa.Column("funding_admission_id", sa.Uuid(),
                            sa.ForeignKey("funding_admissions.id", ondelete="RESTRICT"), nullable=True))
    for name, _ in M33.ITEM_CHECKS_0033:
        op.drop_constraint(name, "billing_reconciliation_items", type_="check")
    for name, condition in ITEM_CHECKS_0034 + CONFLICT_ITEM_CHECKS:
        op.create_check_constraint(name, "billing_reconciliation_items", condition)
    op.execute(_item_guard_0034())

    # ---- guards ---------------------------------------------------------------------------------------------------
    op.execute(_admission_guard(q))
    op.execute(_grant_guard(q))
    op.execute(_bucket_guard(q))
    op.execute("CREATE TRIGGER funding_admission_guard BEFORE INSERT OR UPDATE OR DELETE ON funding_admissions "
               "FOR EACH ROW EXECUTE FUNCTION funding_admission_guard()")
    op.execute("CREATE TRIGGER promotional_grant_guard BEFORE INSERT OR UPDATE OR DELETE ON promotional_grants "
               "FOR EACH ROW EXECUTE FUNCTION promotional_grant_guard()")
    op.execute("CREATE TRIGGER quota_bucket_promotional_guard BEFORE INSERT OR UPDATE ON commerce_quota_buckets "
               "FOR EACH ROW EXECUTE FUNCTION quota_bucket_promotional_guard()")
    for table in ("funding_admissions", "promotional_grants"):
        op.execute(f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
                   "FOR EACH STATEMENT EXECUTE FUNCTION credit_refuse_change()")

    # ---- ownership and privileges -----------------------------------------------------------------------------------
    op.execute(f"GRANT SELECT ON {q}.commerce_quota_buckets, {q}.commerce_quota_reservations TO {OWNER}")
    for table in ("funding_admissions", "promotional_grants"):
        op.execute(f"ALTER TABLE {q}.{table} OWNER TO {OWNER}")
        op.execute(f"REVOKE ALL ON {q}.{table} FROM PUBLIC")
    for function in FUNCTIONS:
        op.execute(f"ALTER FUNCTION {q}.{function} OWNER TO {OWNER}")
        op.execute(f"REVOKE EXECUTE ON FUNCTION {q}.{function} FROM PUBLIC")
    op.execute(f"GRANT SELECT ON {q}.funding_admissions, {q}.promotional_grants TO {RUNTIME}")
    op.execute(f"GRANT INSERT ({', '.join(IDENTITY + ('state',))}) ON {q}.funding_admissions TO {RUNTIME}")
    op.execute(f"GRANT UPDATE ({', '.join(SNAPSHOT + LIFECYCLE)}) ON {q}.funding_admissions TO {RUNTIME}")
    op.execute(f"GRANT INSERT ON {q}.promotional_grants TO {RUNTIME}")


def downgrade() -> None:
    connection = op.get_bind()
    schema = connection.execute(sa.text("SELECT current_schema()")).scalar()
    q = '"' + schema.replace('"', '""') + '"'
    for what, sql in (
            ("funding admissions", "SELECT EXISTS (SELECT 1 FROM funding_admissions)"),
            ("promotional grants", "SELECT EXISTS (SELECT 1 FROM promotional_grants)"),
            ("promotional buckets", "SELECT EXISTS (SELECT 1 FROM commerce_quota_buckets "
                                    "WHERE promotional_grant_id IS NOT NULL)"),
            ("attributed cost records", "SELECT EXISTS (SELECT 1 FROM ai_cost_records WHERE operation_id IS NOT NULL)"),
            ("funding conflict items", f"SELECT EXISTS (SELECT 1 FROM billing_reconciliation_items "
                                       f"WHERE kind = '{CONFLICT}')")):
        if connection.execute(sa.text(sql)).scalar():
            raise RuntimeError(f"{what} exist; this revision is not downgraded over them")
    op.execute(M33._guard_sql())
    for name, _ in ITEM_CHECKS_0034 + CONFLICT_ITEM_CHECKS:
        op.drop_constraint(name, "billing_reconciliation_items", type_="check")
    for name, condition in M33.ITEM_CHECKS_0033:
        op.create_check_constraint(name, "billing_reconciliation_items", condition)
    op.drop_column("billing_reconciliation_items", "funding_admission_id")
    op.drop_index("ix_ai_cost_records_operation", table_name="ai_cost_records")
    op.drop_constraint("ck_ai_cost_attribution", "ai_cost_records", type_="check")
    op.drop_column("ai_cost_records", "meter")
    op.drop_column("ai_cost_records", "operation_id")
    op.execute("DROP TRIGGER quota_bucket_promotional_guard ON commerce_quota_buckets")
    op.drop_index("ix_commerce_quota_buckets_promotional", table_name="commerce_quota_buckets")
    op.drop_constraint("ck_commerce_quota_bucket_promotional", "commerce_quota_buckets", type_="check")
    op.drop_column("commerce_quota_buckets", "promotional_grant_id")
    op.execute(f"DROP TABLE {q}.funding_admissions")
    op.execute(f"DROP TABLE {q}.promotional_grants")
    for function in FUNCTIONS:
        op.execute(f"DROP FUNCTION {q}.{function}")
    op.execute(f"REVOKE ALL ON {q}.commerce_quota_buckets, {q}.commerce_quota_reservations FROM {OWNER}")
