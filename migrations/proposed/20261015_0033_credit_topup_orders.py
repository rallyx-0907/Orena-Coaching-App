"""payOS credit top-up orders (PR-MON-5; docs/billing/PR-MON-5_DESIGN.md revision 3, APPROVED FOR IMPLEMENTATION
2026-10-14 on `89e97942`; D-MON-022).

- `billing_orders` (0027/0031) gains a product kind. A `credit_pack` order snapshots its pack and units. The payloads
  are mutually exclusive, and a credit order never takes `paid_sequence` or `period_end`, so it can never feed plan
  access (the design's hard constraint, §1).
- `billing_reconciliation_items` (0031/0032) gains two critical, reconciler-only credit kinds:
  `credit_topup_unapplied` (credit_applied | payment_refunded | refund_obligation_recorded) and
  `credit_reversal_unapplied` (credit_reversed). The guard verifies each outcome's fact when the item is resolved
  (§6.2, §7.1), and it freezes the facts as 0032 does.
- `credit_apply_entry()` (0032) is replaced: a top-up whose source is a billing order also locks that order (between
  the incarnation and the account: the canonical lock order of §6.3) and requires a paid credit-pack order with the
  same units and incarnation. The owner role gets `SELECT, UPDATE (updated_at)` on `billing_orders`, for that row
  lock only.

0033 reuses 0032's own builders and reads 0032's function text from its file, so the downgrade restores 0032 exactly.

Review and gate. A PROPOSAL in `migrations/proposed/` (Alembic does not read it). Order 0027 -> 0031 -> 0032 -> 0033
(H1; promoted together under the human's migration gate). Startup never applies it. `downgrade()` refuses while any
credit-pack order or new-kind item exists; it exists for rehearsal only.

Revision ID: 20261015_0033
Revises: 20261014_0032
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "20261015_0033"
down_revision = "20261014_0032"
branch_labels = None
depends_on = None

OWNER = "orena_credit_owner"
_0032_FILE = Path(__file__).with_name("20261014_0032_credit_ledger.py")


def _load_0032():
    spec = importlib.util.spec_from_file_location("orena_migration_0032", _0032_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M32 = _load_0032()
_in = M32._in

NEW_CRITICAL = ("credit_topup_unapplied", "credit_reversal_unapplied")
TOPUP_OUTCOMES = ("credit_applied", "payment_refunded", "refund_obligation_recorded")
REVERSAL_OUTCOMES = ("credit_reversed",)
CRITICAL = M32.CRITICAL_0031 + M32.CREDIT_CRITICAL + NEW_CRITICAL
CREDIT_KINDS = M32.CREDIT_KINDS + NEW_CRITICAL
ITEM_CHECKS_0033 = M32._item_checks(
    M32.CRITICAL_0031 + M32.MONEY_0031 + M32.DISMISSABLE_0031 + CREDIT_KINDS,
    M32.DISMISSABLE_0031 + M32.CREDIT_DISMISSABLE,
    M32.OUTCOMES_0031 + ("balance_consistent",) + TOPUP_OUTCOMES + REVERSAL_OUTCOMES,
    M32.CRITICAL_0031 + M32.MONEY_0031 + M32.CREDIT_CRITICAL + M32.CREDIT_MONEY + NEW_CRITICAL)
SCOPE_0032 = dict(M32.CREDIT_ITEM_CHECKS)["ck_billing_item_credit_scope"]
SCOPE_0033 = (f"(kind IN ({_in(CREDIT_KINDS)}) AND gateway = 'credits') OR (kind NOT IN ({_in(CREDIT_KINDS)}) AND "
              + " AND ".join(f"{column} IS NULL" for column in M32.CREDIT_FACTS) + ")")
NEW_ITEM_CHECKS = [
    ("ck_billing_item_credit_topup_gap",
     "kind <> 'credit_topup_unapplied' OR (billing_order_id IS NOT NULL AND credit_account_id IS NOT NULL "
     "AND credit_requested IS NOT NULL AND credit_requested > 0)"),
    ("ck_billing_item_credit_reversal_gap",
     "kind <> 'credit_reversal_unapplied' OR (billing_order_id IS NOT NULL AND credit_account_id IS NOT NULL "
     "AND credit_topup_entry_id IS NOT NULL AND credit_requested IS NOT NULL AND credit_requested > 0)"),
    # terminal outcomes: the reconciler's alone, and only the kind's own (§6.2, §7.1)
    ("ck_billing_item_credit_topup_outcome",
     f"kind <> 'credit_topup_unapplied' OR state = 'open' "
     f"OR (resolved_by = 'reconciler' AND resolution_outcome IN ({_in(TOPUP_OUTCOMES)}))"),
    ("ck_billing_item_credit_reversal_outcome",
     "kind <> 'credit_reversal_unapplied' OR state = 'open' "
     "OR (resolved_by = 'reconciler' AND resolution_outcome = 'credit_reversed')"),
    ("ck_billing_item_credit_outcomes_reconciler",
     f"resolution_outcome IS NULL OR resolution_outcome NOT IN ({_in(TOPUP_OUTCOMES + REVERSAL_OUTCOMES)}) "
     "OR resolved_by = 'reconciler'"),
]
ORDER_CHECKS = [
    ("ck_billing_order_kind", "product_kind IN ('plan', 'credit_pack')"),
    # the payloads are mutually exclusive (review of `5a5c4053`, schema hardening)
    ("ck_billing_order_payload",
     "(product_kind = 'plan' AND plan_id IS NOT NULL AND period IS NOT NULL AND credit_pack_id IS NULL "
     "AND credit_units IS NULL) OR (product_kind = 'credit_pack' AND plan_id IS NULL AND period IS NULL "
     "AND credit_pack_id IS NOT NULL AND credit_units > 0)"),
    # a credit order never feeds plan access (§1)
    ("ck_billing_order_credit_no_access",
     "product_kind = 'plan' OR (paid_sequence IS NULL AND period_end IS NULL)"),
]

# The exact top-up and the complete reversal (§6.1, §7.1), as SQL over the item's order. The intent digest is the
# repository's check; the database checks every structural part.
_EXACT_TOPUP = """EXISTS (SELECT 1 FROM credit_ledger l JOIN credit_accounts a ON a.id = l.credit_account_id
                     JOIN billing_orders o ON o.id = NEW.billing_order_id
                     WHERE l.kind = 'topup' AND l.source_type = 'billing_order'
                       AND l.source_ref = o.gateway || ':' || o.order_code::text
                       AND a.incarnation_id = o.incarnation_id AND l.amount = o.credit_units)"""
_COMPLETE_REVERSAL = """EXISTS (SELECT 1 FROM credit_reversal_requests r JOIN billing_orders o ON o.id = NEW.billing_order_id
                     WHERE r.source_type = 'payos_refund' AND r.source_ref = o.gateway || ':' || o.order_code::text
                       AND r.credit_account_id = NEW.credit_account_id AND r.topup_entry_id = NEW.credit_topup_entry_id
                       AND r.requested = o.credit_units
                       AND (r.applied = 0 OR (SELECT count(*) FROM credit_ledger e WHERE e.reversal_request_id = r.id
                            AND e.kind = 'reversal' AND e.credit_account_id = r.credit_account_id
                            AND e.ref_entry_id = r.topup_entry_id AND e.amount = r.applied) = 1)
                       AND (r.shortfall = 0 OR EXISTS (SELECT 1 FROM billing_reconciliation_items s
                            WHERE s.kind = 'credit_reversal_shortfall' AND s.dedupe_key = r.id::text
                              AND s.credit_reversal_request_id = r.id AND s.credit_topup_entry_id = r.topup_entry_id
                              AND s.credit_requested = r.requested AND s.credit_applied = r.applied
                              AND s.credit_shortfall = r.shortfall)))"""
_OUTCOME_FACTS = f"""
            -- PR-MON-5: a credit gap is closed only by the fact its outcome names (§6.2, §7.1).
            IF OLD.state = 'open' AND NEW.state = 'resolved' THEN
                IF NEW.resolution_outcome = 'credit_applied' AND NOT {_EXACT_TOPUP} THEN
                    RAISE EXCEPTION 'credit_applied needs the exact top-up' USING ERRCODE = 'check_violation';
                END IF;
                IF NEW.resolution_outcome = 'payment_refunded' AND NOT (
                        EXISTS (SELECT 1 FROM billing_orders o WHERE o.id = NEW.billing_order_id AND o.state = 'refunded')
                        AND NOT {_EXACT_TOPUP}) THEN
                    RAISE EXCEPTION 'payment_refunded needs a refunded order with no top-up' USING ERRCODE = 'check_violation';
                END IF;
                IF NEW.resolution_outcome = 'refund_obligation_recorded' AND NOT EXISTS (
                        SELECT 1 FROM billing_reconciliation_items d WHERE d.kind = 'paid_deleted_account'
                        AND d.billing_order_id = NEW.billing_order_id) THEN
                    RAISE EXCEPTION 'refund_obligation_recorded needs the paid_deleted_account item'
                        USING ERRCODE = 'check_violation';
                END IF;
                IF NEW.resolution_outcome = 'credit_reversed' AND NOT {_COMPLETE_REVERSAL} THEN
                    RAISE EXCEPTION 'credit_reversed needs the complete reversal' USING ERRCODE = 'check_violation';
                END IF;
            END IF;
            IF OLD.state <> 'open' THEN"""


def _guard_sql() -> str:
    base = M32._item_guard_sql(CRITICAL, M32.FACTS_0031 + M32.CREDIT_FACTS)
    marker = "\n            IF OLD.state <> 'open' THEN"
    assert base.count(marker) == 1
    return base.replace(marker, _OUTCOME_FACTS, 1)


def _apply_entry_0032(q: str) -> str:
    """0032's `credit_apply_entry()` exactly as 0032 creates it (read from its file, not copied)."""

    text = _0032_FILE.read_text(encoding="utf-8")
    start = text.index("        CREATE FUNCTION {q}.credit_apply_entry()")
    end = text.index("        END $$", start) + len("        END $$")
    return text[start:end].replace("{q}", q).replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)


def _apply_entry_0033(q: str) -> str:
    sql = _apply_entry_0032(q)
    declare = "            total bigint;\n"
    lock = (f"            SELECT status INTO inc_status FROM {q}.account_incarnations WHERE id = inc_id FOR SHARE;\n")
    assert sql.count(declare) == 1 and sql.count(lock) == 1
    sql = sql.replace(declare, declare + "            ord record;\n", 1)
    return sql.replace(lock, lock + f"""            -- PR-MON-5 §6.3: a billing-order top-up locks its order between the incarnation and the account (the
            -- canonical order) and credits exactly a paid credit-pack order of this account's incarnation.
            IF NEW.kind = 'topup' AND NEW.source_type = 'billing_order' THEN
                SELECT o.product_kind, o.state, o.credit_units, o.incarnation_id INTO ord FROM {q}.billing_orders o
                    WHERE o.gateway = split_part(NEW.source_ref, ':', 1)
                      AND o.order_code::text = split_part(NEW.source_ref, ':', 2) FOR SHARE;
                IF NOT FOUND OR ord.product_kind <> 'credit_pack' OR ord.state <> 'paid'
                        OR ord.credit_units <> NEW.amount OR ord.incarnation_id <> inc_id THEN
                    RAISE EXCEPTION 'a billing-order top-up credits exactly its paid credit-pack order'
                        USING ERRCODE = 'check_violation';
                END IF;
            END IF;
""", 1)


def upgrade() -> None:
    connection = op.get_bind()
    schema = connection.execute(sa.text("SELECT current_schema()")).scalar()
    q = '"' + schema.replace('"', '""') + '"'

    # ---- billing_orders -------------------------------------------------------------------------------------------
    op.add_column("billing_orders", sa.Column("product_kind", sa.String(20), nullable=False, server_default="plan"))
    op.add_column("billing_orders", sa.Column("credit_pack_id", sa.String(40), nullable=True))
    op.add_column("billing_orders", sa.Column("credit_units", sa.BigInteger(), nullable=True))
    op.alter_column("billing_orders", "plan_id", nullable=True)
    op.alter_column("billing_orders", "period", nullable=True)
    op.drop_constraint("ck_billing_order_period", "billing_orders", type_="check")
    op.create_check_constraint("ck_billing_order_period", "billing_orders",
                               "period IS NULL OR period IN ('month', 'year')")
    for name, condition in ORDER_CHECKS:
        op.create_check_constraint(name, "billing_orders", condition)
    op.create_index("ix_billing_orders_credit_paid", "billing_orders", ["state"],
                    postgresql_where=sa.text("product_kind = 'credit_pack' AND state IN ('paid', 'refunded')"))

    # ---- billing_reconciliation_items --------------------------------------------------------------------------
    for name, _ in M32.ITEM_CHECKS_0032:
        op.drop_constraint(name, "billing_reconciliation_items", type_="check")
    op.drop_constraint("ck_billing_item_credit_scope", "billing_reconciliation_items", type_="check")
    for name, condition in ITEM_CHECKS_0033 + [("ck_billing_item_credit_scope", SCOPE_0033)] + NEW_ITEM_CHECKS:
        op.create_check_constraint(name, "billing_reconciliation_items", condition)
    op.execute(_guard_sql())

    # ---- the ledger trigger's billing-order backstop (§6.3) ------------------------------------------------------------
    op.execute(f"GRANT SELECT, UPDATE (updated_at) ON {q}.billing_orders TO {OWNER}")
    op.execute(_apply_entry_0033(q))


def downgrade() -> None:
    connection = op.get_bind()
    schema = connection.execute(sa.text("SELECT current_schema()")).scalar()
    q = '"' + schema.replace('"', '""') + '"'
    if connection.execute(sa.text("SELECT EXISTS (SELECT 1 FROM billing_orders WHERE product_kind <> 'plan')")).scalar():
        raise RuntimeError("credit-pack orders are financial records; this revision is not downgraded over them")
    if connection.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM billing_reconciliation_items "
                                  f"WHERE kind IN ({_in(NEW_CRITICAL)}))")).scalar():
        raise RuntimeError("credit top-up reconciliation items exist; this revision is not downgraded over them")
    op.execute(_apply_entry_0032(q))
    op.execute(f"REVOKE ALL ON {q}.billing_orders FROM {OWNER}")
    op.execute(M32._item_guard_sql(M32.CRITICAL_0031 + M32.CREDIT_CRITICAL, M32.FACTS_0031 + M32.CREDIT_FACTS))
    for name, _ in ITEM_CHECKS_0033 + [("ck_billing_item_credit_scope", None)] + NEW_ITEM_CHECKS:
        op.drop_constraint(name, "billing_reconciliation_items", type_="check")
    for name, condition in M32.ITEM_CHECKS_0032 + [("ck_billing_item_credit_scope", SCOPE_0032)]:
        op.create_check_constraint(name, "billing_reconciliation_items", condition)
    op.drop_index("ix_billing_orders_credit_paid", table_name="billing_orders")
    for name, _ in ORDER_CHECKS:
        op.drop_constraint(name, "billing_orders", type_="check")
    op.drop_constraint("ck_billing_order_period", "billing_orders", type_="check")
    op.create_check_constraint("ck_billing_order_period", "billing_orders", "period IN ('month', 'year')")
    op.alter_column("billing_orders", "period", nullable=False)
    op.alter_column("billing_orders", "plan_id", nullable=False)
    for column in ("credit_units", "credit_pack_id", "product_kind"):
        op.drop_column("billing_orders", column)
