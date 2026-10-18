"""PR-MON-5 migration gate: the proposed 0033 on PostgreSQL (`ORENA_TEST_POSTGRES_URL`, throwaway database only).

Each test runs at the Alembic head plus the proposed 0027 -> 0031 -> 0032 -> 0033. The credit writes run as the
non-superuser runtime role of `test_credit_ledger_postgres`. These are the schema-level proofs of the approved design
(revision 3): exclusive order payloads, no plan access for credit orders, the ledger trigger's billing-order backstop
and lock order, and the fact-checked terminal outcomes of the two new critical items. The service code is PR-MON-5's
implementation, after the gate."""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime

import pytest

from tests.test_credit_ledger_postgres import MIGRATIONS, URL, _migrate, ledger_world, no_drift, refused

pytestmark = pytest.mark.skipif(not URL, reason="ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")

M33 = "20261015_0033_credit_topup_orders"
ALL = MIGRATIONS + (M33,)


@pytest.fixture
def gate():
    yield from ledger_world(ALL)


def order(gate, incarnation, *, kind="credit_pack", units=100, state="paid", amount=50_000):
    """A billing order inserted directly (the checkout code is PR-MON-5's implementation)."""
    now = datetime.now(UTC)
    values = dict(id=uuid.uuid4(), op=str(uuid.uuid4()), inc=incarnation, now=now, amount=amount,
                  kind=kind, pack="pack-test" if kind == "credit_pack" else None,
                  units=units if kind == "credit_pack" else None,
                  plan="plus" if kind == "plan" else None, period="month" if kind == "plan" else None)
    rows = gate.sql("INSERT INTO billing_orders (id, operation_id, incarnation_id, gateway, plan_id, period, currency, "
                    "amount_minor, state, created_at, updated_at, expires_at, product_kind, credit_pack_id, credit_units) "
                    "VALUES (:id, :op, :inc, 'payos', :plan, :period, 'VND', :amount, 'created', :now, :now, :now, "
                    ":kind, :pack, :units) RETURNING id, order_code", **values)
    row = dict(rows[0])
    if state in ("paid", "refunded"):
        gate.sql("UPDATE billing_orders SET state = 'paid', paid_at = now(), paid_event_id = 'evt' WHERE id = :id",
                 id=row["id"])
    if state == "refunded":
        gate.sql("UPDATE billing_orders SET state = 'refunded', refunded_at = now(), refunded_by = 'operator' "
                 "WHERE id = :id", id=row["id"])
    return row


def topup_digest(gate, account, code, units):
    """The repository's own intent digest of a billing-order top-up (`credit_repository.digest`)."""
    from writing_coach.persistence.credit_repository import digest

    incarnation = gate.sql("SELECT incarnation_id FROM credit_accounts WHERE id = :a", a=account)[0]["incarnation_id"]
    return digest(kind="topup", account=str(incarnation), amount=units, source_type="billing_order",
                  source_ref=f"payos:{code}")


def reversal_digest(incarnation, topup, requested, code):
    from writing_coach.persistence.credit_repository import digest

    return digest(kind="reversal", account=str(incarnation), topup=str(topup), requested=requested,
                  source_type="payos_refund", source_ref=f"payos:{code}")


def topup_sql(gate, account, code, units, *, match=None, request_digest=None):
    statement = ("INSERT INTO credit_ledger (id, credit_account_id, kind, posted_delta, reserved_delta, amount, "
                 "source_type, source_ref, idempotency_key, request_digest, actor, created_at) VALUES (gen_random_uuid(), "
                 ":a, 'topup', :u, 0, :u, 'billing_order', :ref, :ref, :d, 'system', now())")
    values = dict(a=account, u=units, ref=f"payos:{code}",
                  d=request_digest or topup_digest(gate, account, code, units))
    if match is None:
        gate.sql(statement, engine=gate.runtime, **values)
    else:
        refused(gate, statement, engine=gate.runtime, match=match, **values)


# ---- the migration ------------------------------------------------------------------------------------------------

def test_0033_downgrade_refuses_over_credit_orders_and_otherwise_restores_0032_exactly(gate):
    from sqlalchemy import create_engine
    from urllib.parse import quote

    from tests.test_credit_ledger_postgres import _head

    probes = {
        "functions": "SELECT p.proname, p.prosrc FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
                     "WHERE n.nspname = :s AND p.proname IN ('credit_apply_entry', 'billing_reconciliation_items_guard') "
                     "ORDER BY 1",
        "checks": "SELECT conrelid::regclass::text AS t, conname, pg_get_constraintdef(oid) AS def FROM pg_constraint "
                  "WHERE conrelid IN ('billing_orders'::regclass, 'billing_reconciliation_items'::regclass) "
                  "AND contype = 'c' ORDER BY 1, 2",
        "nullability": "SELECT column_name, is_nullable FROM information_schema.columns WHERE table_schema = :s "
                       "AND table_name = 'billing_orders' ORDER BY 1",
    }
    incarnation = gate.account()
    order(gate, incarnation)
    with pytest.raises(RuntimeError, match="credit-pack orders"):
        _migrate(gate.owner, (M33,), "downgrade")
    schema = f"credit_{uuid.uuid4().hex[:10]}"
    separator = "&" if "?" in URL else "?"
    engine = create_engine(f"{URL}{separator}options={quote(f'-csearch_path={schema}')}", future=True)
    gate.sql(f'CREATE SCHEMA "{schema}"', engine=gate.admin)
    try:
        _head(engine)
        _migrate(engine, MIGRATIONS)
        before = {name: gate.sql(sql, engine=engine, s=schema) for name, sql in probes.items()}
        _migrate(engine, (M33,))
        assert gate.sql(probes["functions"], engine=engine, s=schema) != before["functions"]
        _migrate(engine, (M33,), "downgrade")
        assert {name: gate.sql(sql, engine=engine, s=schema) for name, sql in probes.items()} == before
        _migrate(engine, (M33,))
    finally:
        engine.dispose()
        gate.sql(f'DROP SCHEMA "{schema}" CASCADE', engine=gate.admin)


def test_order_payloads_are_mutually_exclusive_and_a_credit_order_never_feeds_plan_access(gate):
    incarnation = gate.account()
    insert = ("INSERT INTO billing_orders (id, operation_id, incarnation_id, gateway, plan_id, period, currency, "
              "amount_minor, state, created_at, updated_at, expires_at, product_kind, credit_pack_id, credit_units) "
              "VALUES (gen_random_uuid(), gen_random_uuid()::text, :inc, 'payos', :plan, :period, 'VND', 1000, "
              "'created', now(), now(), now(), :kind, :pack, :units)")
    for case in (dict(kind="plan", plan="plus", period="month", pack="p", units=None),
                 dict(kind="plan", plan="plus", period=None, pack=None, units=None),
                 dict(kind="credit_pack", plan="plus", period=None, pack="p", units=10),
                 dict(kind="credit_pack", plan=None, period="month", pack="p", units=10),
                 dict(kind="credit_pack", plan=None, period=None, pack="p", units=0),
                 dict(kind="credit_pack", plan=None, period=None, pack=None, units=10)):
        refused(gate, insert, match="ck_billing_order_payload", inc=incarnation, **case)
    credit = order(gate, incarnation)
    refused(gate, "UPDATE billing_orders SET paid_sequence = 1 WHERE id = :id", match="ck_billing_order_credit_no_access",
            id=credit["id"])
    refused(gate, "UPDATE billing_orders SET period_end = now() WHERE id = :id", match="ck_billing_order_credit_no_access",
            id=credit["id"])
    plan = order(gate, incarnation, kind="plan")
    gate.sql("UPDATE billing_orders SET paid_sequence = 1 WHERE id = :id", id=plan["id"])  # a plan order may


# ---- the ledger trigger's billing-order backstop (§6.3) --------------------------------------------------------------

def test_a_billing_order_topup_credits_exactly_its_paid_credit_pack_order(gate):
    incarnation = gate.account()
    account = gate.balance(incarnation)["id"]
    other = gate.account()
    unpaid = order(gate, incarnation, state="created")
    refunded = order(gate, incarnation, state="refunded")
    plan = order(gate, incarnation, kind="plan")
    others = order(gate, other)
    paid = order(gate, incarnation, units=120)
    message = "credits exactly its paid credit-pack order"
    topup_sql(gate, account, unpaid["order_code"], 100, match=message)
    topup_sql(gate, account, refunded["order_code"], 100, match=message)
    topup_sql(gate, account, plan["order_code"], 100, match=message)
    topup_sql(gate, account, others["order_code"], 100, match=message)  # another incarnation's order
    topup_sql(gate, account, paid["order_code"], 119, match=message)  # not the snapshot units
    topup_sql(gate, account, 999999999, 100, match=message)  # no such order
    topup_sql(gate, account, paid["order_code"], 120)
    assert gate.balance(incarnation)["posted"] == 120
    no_drift(gate)


@pytest.mark.parametrize("first", ["refund", "topup"])
def test_refund_and_topup_serialize_in_both_orderings(gate, first):
    incarnation = gate.account()
    account = gate.balance(incarnation)["id"]
    paid = order(gate, incarnation, units=80)
    outcome, holder = {}, gate.owner.connect() if first == "refund" else gate.runtime.connect()
    transaction = holder.begin()

    def second():
        try:
            if first == "refund":
                topup_sql(gate, account, paid["order_code"], 80)
            else:
                gate.sql("UPDATE billing_orders SET state = 'refunded', refunded_at = now(), refunded_by = 'operator' "
                         "WHERE id = :id", id=paid["id"])
            outcome["result"] = "done"
        except Exception as error:  # noqa: BLE001 - the refusal is an expected outcome
            outcome["result"] = str(error)

    worker = threading.Thread(target=second, daemon=True)
    try:
        if first == "refund":  # mark_refunded's locks: the incarnation, then the order
            holder.execute(gate.text("SELECT 1 FROM account_incarnations WHERE id = :i FOR NO KEY UPDATE"), {"i": incarnation})
            holder.execute(gate.text("UPDATE billing_orders SET state = 'refunded', refunded_at = now(), "
                                     "refunded_by = 'operator' WHERE id = :id"), {"id": paid["id"]})
        else:  # the top-up's transaction, through the trigger: incarnation, order, account
            holder.execute(gate.text(
                "INSERT INTO credit_ledger (id, credit_account_id, kind, posted_delta, reserved_delta, amount, "
                "source_type, source_ref, idempotency_key, request_digest, actor, created_at) VALUES "
                "(gen_random_uuid(), :a, 'topup', 80, 0, 80, 'billing_order', :ref, :ref, 'd', 'system', now())"),
                {"a": account, "ref": f"payos:{paid['order_code']}"})
        worker.start()
        worker.join(timeout=2.0)
        waited = worker.is_alive()
        transaction.commit()
    finally:
        if transaction.is_active:
            transaction.rollback()
        holder.close()
    worker.join(timeout=10)
    assert waited, "the second transaction must wait behind the first"
    if first == "refund":  # the top-up re-reads the refunded order and writes nothing
        assert "credits exactly its paid credit-pack order" in outcome["result"]
        assert gate.balance(incarnation)["posted"] == 0
    else:  # the refund follows the committed top-up; the reversal lifecycle takes over
        assert outcome["result"] == "done" and gate.balance(incarnation)["posted"] == 80
    assert gate.sql("SELECT state FROM billing_orders WHERE id = :id", id=paid["id"])[0]["state"] == "refunded"
    no_drift(gate)


# ---- the terminal outcomes are the reconciler's, and fact-checked (§6.2, §7.1) ---------------------------------------

def gap_item(gate, kind, incarnation, paid, **extra):
    account = gate.balance(incarnation)["id"]
    values = dict(kind=kind, key=f"{kind}:{paid['order_code']}", order=paid["id"], a=account, units=extra.pop("units", 100),
                  topup=extra.pop("topup", None))
    rows = gate.sql("INSERT INTO billing_reconciliation_items (id, kind, gateway, dedupe_key, billing_order_id, state, "
                    "first_seen_at, last_seen_at, credit_account_id, credit_requested, credit_topup_entry_id) VALUES "
                    "(gen_random_uuid(), :kind, 'credits', :key, :order, 'open', now(), now(), :a, :units, :topup) "
                    "RETURNING id", engine=gate.runtime, **values)
    return rows[0]["id"]


def resolve(gate, item, outcome, actor="reconciler"):
    gate.sql("UPDATE billing_reconciliation_items SET state = 'resolved', resolution_outcome = :o, resolved_by = :a, "
             "resolved_at = now() WHERE id = :id", engine=gate.runtime, o=outcome, a=actor, id=item)


def test_a_topup_gap_closes_only_with_the_fact_its_outcome_names(gate):
    from sqlalchemy.exc import DBAPIError

    incarnation = gate.account()
    account = gate.balance(incarnation)["id"]
    paid = order(gate, incarnation)
    item = gap_item(gate, "credit_topup_unapplied", incarnation, paid)
    for outcome, message in (("credit_applied", "exact top-up"), ("payment_refunded", "refunded order with no top-up"),
                             ("refund_obligation_recorded", "paid_deleted_account")):
        with pytest.raises(DBAPIError, match=message):
            resolve(gate, item, outcome)
    topup_sql(gate, account, paid["order_code"], 100)
    # the fact now exists, so only the reconciler-only CHECK can refuse an administrator
    with pytest.raises(DBAPIError, match="ck_billing_item_credit_(topup_outcome|outcomes_reconciler)"):
        resolve(gate, item, "credit_applied", actor="admin-1")
    with pytest.raises(DBAPIError, match="refunded order with no top-up"):  # refunded, but credit was given
        gate.sql("UPDATE billing_orders SET state = 'refunded', refunded_at = now(), refunded_by = 'operator' "
                 "WHERE id = :id", id=paid["id"])
        resolve(gate, item, "payment_refunded")
    resolve(gate, item, "credit_applied")
    assert gate.sql("SELECT state FROM billing_reconciliation_items WHERE id = :id", id=item)[0]["state"] == "resolved"

    refunded_first = order(gate, incarnation, state="refunded")
    second = gap_item(gate, "credit_topup_unapplied", incarnation, refunded_first)
    resolve(gate, second, "payment_refunded")  # refunded, and no credit was ever given


def test_a_reversal_gap_closes_only_with_the_complete_reversal(gate):
    from sqlalchemy.exc import DBAPIError

    incarnation = gate.account()
    account = gate.balance(incarnation)["id"]
    paid = order(gate, incarnation, units=100)
    topup_sql(gate, account, paid["order_code"], 100)
    topup = gate.sql("SELECT id FROM credit_ledger WHERE source_ref = :r", r=f"payos:{paid['order_code']}")[0]["id"]
    hold = gate.service.reserve(incarnation, amount=40, operation_id="op", meter="m").entry  # 40 cannot be reversed
    gate.sql("UPDATE billing_orders SET state = 'refunded', refunded_at = now(), refunded_by = 'operator' "
             "WHERE id = :id", id=paid["id"])
    item = gap_item(gate, "credit_reversal_unapplied", incarnation, paid, topup=topup)
    with pytest.raises(DBAPIError, match="complete reversal"):
        resolve(gate, item, "credit_reversed")  # nothing reversed yet
    reversed_ = gate.service.reverse(incarnation, topup_entry_id=topup, requested=100, source_type="payos_refund",
                                     source_ref=f"payos:{paid['order_code']}", actor="system", reason="refunded")
    request = reversed_.extra["request"]
    assert (request["applied"], request["shortfall"]) == (60, 40)
    with pytest.raises(DBAPIError, match="ck_billing_item_credit_(reversal_outcome|outcomes_reconciler)"):
        resolve(gate, item, "credit_reversed", actor="admin-1")  # complete, yet never an administrator
    resolve(gate, item, "credit_reversed")  # request + its entry + its shortfall item: complete
    gate.service.release(incarnation, reserve_entry_id=hold["id"], operation_id="rl")
    no_drift(gate)


def test_a_reversal_request_without_its_durable_effects_is_not_complete(gate):
    from sqlalchemy.exc import DBAPIError

    incarnation = gate.account()
    account = gate.balance(incarnation)["id"]
    paid = order(gate, incarnation, units=100)
    topup_sql(gate, account, paid["order_code"], 100)
    topup = gate.sql("SELECT id FROM credit_ledger WHERE source_ref = :r", r=f"payos:{paid['order_code']}")[0]["id"]
    gate.sql("UPDATE billing_orders SET state = 'refunded', refunded_at = now(), refunded_by = 'operator' "
             "WHERE id = :id", id=paid["id"])
    # a request row alone (written around the repository): applied 100, but no reversal entry
    gate.sql("INSERT INTO credit_reversal_requests (id, credit_account_id, topup_entry_id, idempotency_key, "
             "request_digest, requested, applied, shortfall, source_type, source_ref, actor, reason, created_at) "
             "VALUES (gen_random_uuid(), :a, :t, :ref, :d, 100, 100, 0, 'payos_refund', :ref, 'x', 'x', now())",
             engine=gate.runtime, a=account, t=topup, ref=f"payos:{paid['order_code']}",
             d=reversal_digest(incarnation, topup, 100, paid["order_code"]))
    item = gap_item(gate, "credit_reversal_unapplied", incarnation, paid, topup=topup)
    with pytest.raises(DBAPIError, match="complete reversal"):
        resolve(gate, item, "credit_reversed")


def test_a_reversal_with_its_entry_but_without_its_shortfall_item_is_not_complete(gate):
    from sqlalchemy.exc import DBAPIError

    incarnation = gate.account()
    account = gate.balance(incarnation)["id"]
    paid = order(gate, incarnation, units=100)
    topup_sql(gate, account, paid["order_code"], 100)
    topup = gate.sql("SELECT id FROM credit_ledger WHERE source_ref = :r", r=f"payos:{paid['order_code']}")[0]["id"]
    gate.service.reserve(incarnation, amount=40, operation_id="op", meter="m")  # 40 cannot be reversed
    gate.sql("UPDATE billing_orders SET state = 'refunded', refunded_at = now(), refunded_by = 'operator' "
             "WHERE id = :id", id=paid["id"])
    ref = f"payos:{paid['order_code']}"
    request = gate.sql("INSERT INTO credit_reversal_requests (id, credit_account_id, topup_entry_id, idempotency_key, "
                       "request_digest, requested, applied, shortfall, source_type, source_ref, actor, reason, created_at) "
                       "VALUES (gen_random_uuid(), :a, :t, :ref, :d, 100, 60, 40, 'payos_refund', :ref, 'x', 'x', now()) "
                       "RETURNING id", engine=gate.runtime, a=account, t=topup, ref=ref,
                       d=reversal_digest(incarnation, topup, 100, paid["order_code"]))[0]["id"]
    gate.sql("INSERT INTO credit_ledger (id, credit_account_id, kind, posted_delta, reserved_delta, amount, ref_entry_id, "
             "reversal_request_id, idempotency_key, request_digest, actor, reason, created_at) VALUES (gen_random_uuid(), "
             ":a, 'reversal', -60, 0, 60, :t, :req, :ref, 'd', 'x', 'x', now())",
             engine=gate.runtime, a=account, t=topup, req=request, ref=ref)
    item = gap_item(gate, "credit_reversal_unapplied", incarnation, paid, topup=topup)
    with pytest.raises(DBAPIError, match="complete reversal"):  # the 40 shortfall has no item
        resolve(gate, item, "credit_reversed")


def test_the_promoted_chain_upgrades_and_downgrades_through_alembic(gate):
    """The migration gate's rehearsal: the promoted 0027 -> 0031 -> 0032 -> 0033 is the single head, `alembic upgrade
    head` applies all four, and an empty schema goes back to 0026 and up again."""
    from urllib.parse import quote

    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine

    from tests.test_billing import ROOT

    schema = f"credit_{uuid.uuid4().hex[:10]}"
    separator = "&" if "?" in URL else "?"
    engine = create_engine(f"{URL}{separator}options={quote(f'-csearch_path={schema}')}", future=True)
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("path_separator", "os")
    cfg.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False).replace("%", "%%"))
    script = ScriptDirectory.from_config(cfg)
    # The Billing chain is exact; later revisions (0035 Orena Memory) may sit above it, so the proof upgrades to
    # 0033 by name rather than to "head".
    assert len(script.get_heads()) == 1
    assert "20261015_0033" in {rev.revision for rev in script.iterate_revisions("heads", "base")}
    assert [script.get_revision(r).down_revision for r in ("20261005_0027", "20261014_0031", "20261014_0032",
                                                         "20261015_0033")] == [
        "20261005_0026", "20261005_0027", "20261014_0031", "20261014_0032"]
    gate.sql(f'CREATE SCHEMA "{schema}"', engine=gate.admin)
    try:
        command.upgrade(cfg, "20261015_0033")
        version = "SELECT version_num FROM alembic_version"
        assert gate.sql(version, engine=engine)[0]["version_num"] == "20261015_0033"
        assert gate.sql("SELECT to_regclass('credit_ledger') AS t", engine=engine)[0]["t"] is not None
        command.downgrade(cfg, "20261005_0026")
        assert gate.sql(version, engine=engine)[0]["version_num"] == "20261005_0026"
        assert gate.sql("SELECT to_regclass('billing_orders') AS t", engine=engine)[0]["t"] is None
        command.upgrade(cfg, "20261015_0033")
        assert gate.sql(version, engine=engine)[0]["version_num"] == "20261015_0033"
    finally:
        engine.dispose()
        gate.sql(f'DROP SCHEMA "{schema}" CASCADE', engine=gate.admin)


# ---- the request digest is part of the exact match (migration-gate review of `f81f0322`) -----------------------------

def test_a_topup_with_the_wrong_digest_is_not_the_exact_topup(gate):
    from sqlalchemy.exc import DBAPIError

    incarnation = gate.account()
    account = gate.balance(incarnation)["id"]
    paid = order(gate, incarnation, units=100)
    item = gap_item(gate, "credit_topup_unapplied", incarnation, paid)
    # the right source, account and units, but another intent's digest
    topup_sql(gate, account, paid["order_code"], 100, request_digest="0" * 64)
    with pytest.raises(DBAPIError, match="exact top-up"):
        resolve(gate, item, "credit_applied")
    assert gate.sql("SELECT state FROM billing_reconciliation_items WHERE id = :id", id=item)[0]["state"] == "open"


def test_the_right_digest_makes_the_exact_topup(gate):
    incarnation = gate.account()
    account = gate.balance(incarnation)["id"]
    paid = order(gate, incarnation, units=100)
    item = gap_item(gate, "credit_topup_unapplied", incarnation, paid)
    topup_sql(gate, account, paid["order_code"], 100)  # the repository's digest, recomputed by the database
    resolve(gate, item, "credit_applied")


def test_a_reversal_request_with_the_wrong_digest_is_not_complete(gate):
    from sqlalchemy.exc import DBAPIError

    incarnation = gate.account()
    account = gate.balance(incarnation)["id"]
    paid = order(gate, incarnation, units=100)
    topup_sql(gate, account, paid["order_code"], 100)
    topup = gate.sql("SELECT id FROM credit_ledger WHERE source_ref = :r", r=f"payos:{paid['order_code']}")[0]["id"]
    gate.sql("UPDATE billing_orders SET state = 'refunded', refunded_at = now(), refunded_by = 'operator' "
             "WHERE id = :id", id=paid["id"])
    ref = f"payos:{paid['order_code']}"
    # account, top-up, source and requested all right; applied in full with its entry; only the digest is not the intent
    request = gate.sql("INSERT INTO credit_reversal_requests (id, credit_account_id, topup_entry_id, idempotency_key, "
                       "request_digest, requested, applied, shortfall, source_type, source_ref, actor, reason, created_at) "
                       "VALUES (gen_random_uuid(), :a, :t, :ref, :d, 100, 100, 0, 'payos_refund', :ref, 'x', 'x', now()) "
                       "RETURNING id", engine=gate.runtime, a=account, t=topup, ref=ref, d="f" * 64)[0]["id"]
    gate.sql("INSERT INTO credit_ledger (id, credit_account_id, kind, posted_delta, reserved_delta, amount, ref_entry_id, "
             "reversal_request_id, idempotency_key, request_digest, actor, reason, created_at) VALUES (gen_random_uuid(), "
             ":a, 'reversal', -100, 0, 100, :t, :req, :ref, 'd', 'x', 'x', now())",
             engine=gate.runtime, a=account, t=topup, req=request, ref=ref)
    item = gap_item(gate, "credit_reversal_unapplied", incarnation, paid, topup=topup)
    with pytest.raises(DBAPIError, match="complete reversal"):
        resolve(gate, item, "credit_reversed")

