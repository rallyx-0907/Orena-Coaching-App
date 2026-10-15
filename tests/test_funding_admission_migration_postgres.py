"""PR-MON-6 migration gate: the proposed 0034 on PostgreSQL (`ORENA_TEST_POSTGRES_URL`, throwaway database only).

Each test runs at the Alembic head plus 0027 -> 0031 -> 0032 -> 0033 and the proposed 0034. Learner-side writes run as
the non-superuser runtime role of `test_credit_ledger_postgres` (a member of `orena_credit_runtime`). These are the
schema-level proofs of the approved design (revision 2, §5.6 and §11): one admission per operation id, an immutable
identity and snapshot, forward-only states checked against the backing reservation, refusal only without an open exact
backing, a deleted account never admitted, a grant claimed once per account ever, a promotional bucket over its grant's
window, attribution both-or-neither, and the funding conflict closed only by its fact. The admission service is
PR-MON-6's implementation, after the gate."""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from tests.test_credit_ledger_postgres import MIGRATIONS, URL, _migrate, ledger_world, no_drift, refused
from tests.test_credit_topup_migration_postgres import M33, order, topup_sql

pytestmark = pytest.mark.skipif(not URL, reason="ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")

M34 = "20261015_0034_funding_admissions"
ALL = MIGRATIONS + (M33, M34)
PRICE = 3


@pytest.fixture
def gate():
    yield from ledger_world(ALL)


def digest():
    return uuid.uuid4().hex + uuid.uuid4().hex


INSERT = ("INSERT INTO funding_admissions (id, operation_id, incarnation_id, meter, units, operation_ref, feature, "
          "unit_granularity, request_digest, state, created_at) VALUES (gen_random_uuid(), :op, :inc, :meter, :units, "
          ":ref, 'test', 1, :d, :state, now())")


def admit(gate, incarnation, *, op=None, meter="writing.review", units=2, ref="ref-1", state="admitting", match=None):
    op = op or f"op-{uuid.uuid4().hex}"
    values = dict(op=op, inc=incarnation, meter=meter, units=units, ref=ref, d=digest(), state=state)
    if match:
        refused(gate, INSERT, engine=gate.runtime, match=match, **values)
    else:
        gate.sql(INSERT, engine=gate.runtime, **values)
    return op


def row(gate, op):
    return dict(gate.sql("SELECT * FROM funding_admissions WHERE operation_id = :op", op=op)[0])


def credits(gate, units=100):
    incarnation = gate.account()
    paid = order(gate, incarnation, units=units)
    account = gate.balance(incarnation)["id"]
    topup_sql(gate, account, paid["order_code"], units)
    return incarnation, account


TTL = 600


def reserve_digest(gate, account, amount, meter="writing.review", ref="ref-1", ttl=TTL):
    """PR-MON-4's own reserve digest (`credit_repository.reserve`), for the hold's incarnation."""
    from writing_coach.persistence.credit_repository import digest

    incarnation = gate.sql("SELECT incarnation_id FROM credit_accounts WHERE id = :a", a=account)[0]["incarnation_id"]
    return digest(kind="reserve", account=str(incarnation), amount=amount, meter=meter, operation_ref=ref, ttl=ttl)


def hold(gate, account, key, amount, *, meter="writing.review", ref="ref-1", minutes=None, request_digest=None,
         engine=None, conn=None):
    """A hold inserted directly, as the repository writes one: created_at = now, expires_at = now + ttl (or `minutes`
    from now), with the canonical digest unless `request_digest` overrides it."""
    statement = ("INSERT INTO credit_ledger (id, credit_account_id, kind, posted_delta, reserved_delta, amount, "
                 "idempotency_key, request_digest, meter, operation_ref, expires_at, actor, created_at) VALUES "
                 "(gen_random_uuid(), :a, 'reserve', 0, :n, :n, :key, :d, :meter, :ref, "
                 "now() + make_interval(secs => :secs), 'system', now()) RETURNING id")
    values = dict(a=account, n=amount, key=key, meter=meter, ref=ref,
                  secs=TTL if minutes is None else minutes * 60,
                  d=request_digest or reserve_digest(gate, account, amount, meter, ref))
    if conn is not None:
        return conn.execute(gate.text(statement), values).scalar()
    return gate.sql(statement, engine=engine or gate.runtime, **values)[0]["id"]


def close(gate, account, reserve, held, kind, charge=0):
    posted = -charge if kind == "settle" else 0
    gate.sql("INSERT INTO credit_ledger (id, credit_account_id, kind, posted_delta, reserved_delta, amount, ref_entry_id, "
             "uncharged, idempotency_key, request_digest, actor, created_at) VALUES (gen_random_uuid(), :a, :kind, :p, "
             ":r, :amount, :ref, :unch, :key, 'd', 'system', now())", engine=gate.runtime,
             a=account, kind=kind, p=posted, r=-held, amount=held, ref=reserve,
             unch=held - charge if kind == "settle" else None, key=uuid.uuid4().hex)


def bucket(gate, incarnation, *, meter="writing.review", grant=None, window=None, start=None, end=None, limit=10,
           match=None):
    now = datetime.now(UTC)
    statement = ("INSERT INTO commerce_quota_buckets (id, incarnation_id, meter, window_id, window_start, window_end, "
                 "policy_version, unit_limit, created_at, updated_at, promotional_grant_id) VALUES (gen_random_uuid(), "
                 ":inc, :meter, :window, :start, :end, 'v1', :limit, now(), now(), :grant) RETURNING id")
    values = dict(inc=incarnation, meter=meter, window=window or f"2026-10-{uuid.uuid4().hex[:6]}",
                  start=start or now - timedelta(days=1), end=end or now + timedelta(days=30), limit=limit, grant=grant)
    if match:
        refused(gate, statement, engine=gate.runtime, match=match, **values)
        return None
    return gate.sql(statement, engine=gate.runtime, **values)[0]["id"]


def reservation(gate, bucket_id, key, units=2):
    return gate.sql("INSERT INTO commerce_quota_reservations (id, bucket_id, operation_id, admitted_units, state, "
                    "policy_version, created_at, updated_at) VALUES (gen_random_uuid(), :b, :key, :u, 'reserved', 'v1', "
                    "now(), now()) RETURNING id", engine=gate.runtime, b=bucket_id, key=key, u=units)[0]["id"]


def fund(gate, op, *, source="credits", hold_id=None, quota=None, price=PRICE, amount=None, units=2, gate_id="gate-1",
         match=None):
    statement = ("UPDATE funding_admissions SET state = 'funded', source = :source, price_per_unit = :price, "
                 "amount_reserved = :amount, hold_ttl_seconds = :ttl, policy_version = 'catalog-1/prices-1', "
                 "cost_gate_id = :gate_id, "
                 "credit_reserve_entry_id = :hold, quota_reservation_id = :quota, funded_at = now() WHERE operation_id = :op")
    credit = source == "credits"
    values = dict(op=op, source=source, price=price if credit else None,
                  amount=(amount if amount is not None else price * units) if credit else None,
                  gate_id=gate_id if credit else None, hold=hold_id, quota=quota, ttl=TTL if credit else None)
    if match:
        refused(gate, statement, engine=gate.runtime, match=match, **values)
    else:
        gate.sql(statement, engine=gate.runtime, **values)


def move(gate, op, state, *, match=None, units=None, amount=None, reason=None):
    sets = {"dispatched": "dispatched_at = now()",
            "settled": "settled_units = :units, settled_amount = :amount, closed_at = now()",
            "released": "closed_at = now()", "refused": "refusal_reason = :reason, closed_at = now()",
            "funded": "dispatched_at = NULL", "admitting": "funded_at = NULL"}[state]
    statement = f"UPDATE funding_admissions SET state = :state, {sets} WHERE operation_id = :op"
    values = dict(op=op, state=state, units=units, amount=amount, reason=reason)
    if match:
        refused(gate, statement, engine=gate.runtime, match=match, **values)
    else:
        gate.sql(statement, engine=gate.runtime, **values)


def funded_on_credits(gate, units=2):
    incarnation, account = credits(gate)
    op = admit(gate, incarnation, units=units)
    reserve = hold(gate, account, f"fund:{op}", PRICE * units)
    fund(gate, op, hold_id=reserve, units=units)
    return incarnation, account, op, reserve


# ---- the migration ------------------------------------------------------------------------------------------------

def test_0034_downgrade_refuses_over_records_and_otherwise_restores_0033_exactly(gate):
    from urllib.parse import quote

    from sqlalchemy import create_engine

    from tests.test_credit_ledger_postgres import _head

    tables = ("billing_reconciliation_items", "commerce_quota_buckets", "ai_cost_records", "account_incarnations",
              "commerce_quota_reservations")
    probes = {
        "functions": "SELECT p.proname, p.prosrc, p.prosecdef FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
                     "WHERE n.nspname = :s ORDER BY 1",
        "tables": "SELECT tablename, tableowner FROM pg_tables WHERE schemaname = :s ORDER BY 1",
        "checks": "SELECT conrelid::regclass::text AS t, conname, pg_get_constraintdef(oid) AS def FROM pg_constraint "
                  "WHERE connamespace = (SELECT oid FROM pg_namespace WHERE nspname = :s) ORDER BY 1, 2",
        "columns": "SELECT table_name, column_name, is_nullable, data_type FROM information_schema.columns "
                   "WHERE table_schema = :s ORDER BY 1, 2",
        "triggers": "SELECT tgrelid::regclass::text AS t, tgname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
                    "WHERE c.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = :s) AND NOT tgisinternal "
                    "ORDER BY 1, 2",
        "indexes": "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = :s ORDER BY 1",
        "grants": "SELECT table_name, grantee, privilege_type FROM information_schema.role_table_grants "
                  f"WHERE table_schema = :s AND table_name IN {tables} ORDER BY 1, 2, 3",
    }
    funded_on_credits(gate)
    with pytest.raises(RuntimeError, match="funding admissions exist"):
        _migrate(gate.owner, (M34,), "downgrade")
    schema = f"credit_{uuid.uuid4().hex[:10]}"
    separator = "&" if "?" in URL else "?"
    engine = create_engine(f"{URL}{separator}options={quote(f'-csearch_path={schema}')}", future=True)
    gate.sql(f'CREATE SCHEMA "{schema}"', engine=gate.admin)
    try:
        _head(engine)
        _migrate(engine, MIGRATIONS + (M33,))
        before = {name: gate.sql(sql, engine=engine, s=schema) for name, sql in probes.items()}
        _migrate(engine, (M34,))
        after = {name: gate.sql(sql, engine=engine, s=schema) for name, sql in probes.items()}
        assert {r["tablename"]: r["tableowner"] for r in after["tables"]}["funding_admissions"] == "orena_credit_owner"
        assert after["functions"] != before["functions"]
        _migrate(engine, (M34,), "downgrade")
        assert {name: gate.sql(sql, engine=engine, s=schema) for name, sql in probes.items()} == before
        _migrate(engine, (M34,))
    finally:
        engine.dispose()
        gate.sql(f'DROP SCHEMA "{schema}" CASCADE', engine=gate.admin)


@pytest.mark.parametrize("what", ["grant", "attributed cost"])
def test_0034_downgrade_refuses_over_grants_and_attributed_costs(gate, what):
    """A promotional bucket and a conflict item cannot exist without a grant or an admission (foreign keys)."""
    incarnation = gate.account()
    user = gate.sql("SELECT user_id FROM account_incarnations WHERE id = :i", i=incarnation)[0]["user_id"]
    if what == "grant":
        claim(gate, user, incarnation)
    else:
        gate.sql("INSERT INTO ai_cost_records (id, account_id, occurred_at, feature, cost_state, operation_id, meter) "
                 "VALUES (gen_random_uuid(), :u, now(), 'test', 'estimated', 'op-1', 'writing.review')", u=user)
    with pytest.raises(RuntimeError, match=f"{'promotional grants' if what == 'grant' else 'attributed cost records'} exist"):
        _migrate(gate.owner, (M34,), "downgrade")


# ---- identity, intent and the forward-only lifecycle ----------------------------------------------------------------

def test_an_admission_starts_admitting_for_an_active_account_and_its_intent_never_changes(gate):
    incarnation = gate.account()
    admit(gate, incarnation, state="funded", match="starts admitting")
    admit(gate, gate.account(status="deleted"), match="deleted account is never admitted")
    admit(gate, incarnation, op="x" * 191, match="ck_funding_identity|value too long")
    refused(gate, INSERT.replace(":d", "'not-a-digest'"), engine=gate.runtime, match="ck_funding_identity",
            op="op-digest", inc=incarnation, meter="writing.review", units=1, ref="r", state="admitting")
    op = admit(gate, incarnation)
    for column, value in (("meter", "'orena.message'"), ("units", "9"), ("operation_ref", "'other'"),
                          ("request_digest", f"'{digest()}'"), ("incarnation_id", f"'{gate.account()}'")):
        refused(gate, f"UPDATE funding_admissions SET {column} = {value} WHERE operation_id = :op", engine=gate.runtime,
                match="permission denied", op=op)
        refused(gate, f"UPDATE funding_admissions SET {column} = {value} WHERE operation_id = :op",
                match="identity and intent never change", op=op)
    refused(gate, "DELETE FROM funding_admissions WHERE operation_id = :op", engine=gate.runtime,
            match="permission denied", op=op)
    refused(gate, "DELETE FROM funding_admissions WHERE operation_id = :op", match="never deleted", op=op)
    refused(gate, "TRUNCATE funding_admissions CASCADE", match="append-only")
    assert row(gate, op)["state"] == "admitting"


def test_one_operation_id_reserves_one_source_even_concurrently(gate):
    """§5.6 serialization: INSERT ON CONFLICT DO NOTHING, the row FOR UPDATE, then source and reservation in one
    transaction. Six racers for one operation id produce one hold and one snapshot."""
    incarnation, account = credits(gate)
    op, results, barrier = f"op-{uuid.uuid4().hex}", [], threading.Barrier(6)

    def racer():
        barrier.wait()
        with gate.runtime.begin() as connection:
            connection.execute(gate.text(INSERT.replace("now())", "now()) ON CONFLICT (operation_id) DO NOTHING")),
                               dict(op=op, inc=incarnation, meter="writing.review", units=2, ref="ref-1",
                                    d="a" * 64, state="admitting"))
            state = connection.execute(gate.text("SELECT state FROM funding_admissions WHERE operation_id = :op "
                                                 "FOR UPDATE"), {"op": op}).scalar()
            if state == "admitting":
                reserve = hold(gate, account, f"fund:{op}", PRICE * 2, conn=connection)
                connection.execute(gate.text(
                    "UPDATE funding_admissions SET state = 'funded', source = 'credits', price_per_unit = :p, "
                    "amount_reserved = :a, hold_ttl_seconds = 600, policy_version = 'v', cost_gate_id = 'g', "
                    "credit_reserve_entry_id = :h, "
                    "funded_at = now() WHERE operation_id = :op"), dict(p=PRICE, a=PRICE * 2, h=reserve, op=op))
            results.append(connection.execute(gate.text(
                "SELECT credit_reserve_entry_id FROM funding_admissions WHERE operation_id = :op"), {"op": op}).scalar())

    threads = [threading.Thread(target=racer) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert len(results) == 6 and len(set(results)) == 1 and results[0] is not None
    assert gate.sql("SELECT count(*) AS n FROM credit_ledger WHERE kind = 'reserve' AND idempotency_key = :k",
                    k=f"fund:{op}")[0]["n"] == 1
    assert gate.balance(incarnation)["reserved"] == PRICE * 2
    no_drift(gate)


def test_the_state_only_moves_forward_and_the_snapshot_never_changes(gate):
    incarnation, account, op, reserve = funded_on_credits(gate)
    for column, value in (("price_per_unit", "1"), ("policy_version", "'other'"), ("cost_gate_id", "'other'"),
                          ("source", "'allowance'"), ("credit_reserve_entry_id", "NULL")):
        refused(gate, f"UPDATE funding_admissions SET {column} = {value} WHERE operation_id = :op", engine=gate.runtime,
                match="snapshot never changes|forward transition|ck_funding", op=op)
    move(gate, op, "admitting", match="not a forward transition|ck_funding")
    move(gate, op, "refused", reason="x", match="not a forward transition")
    refused(gate, "UPDATE funding_admissions SET state = 'dispatched', dispatched_at = now(), policy_version = 'other' "
            "WHERE operation_id = :op", engine=gate.runtime, match="snapshot never changes", op=op)
    move(gate, op, "dispatched")
    move(gate, op, "funded", match="not a forward transition")
    close(gate, account, reserve, PRICE * 2, "settle", charge=PRICE * 2)
    move(gate, op, "settled", units=2, amount=PRICE * 2)
    move(gate, op, "released", match="not a forward transition")
    refused(gate, "UPDATE funding_admissions SET closed_at = now() - interval '1 day' WHERE operation_id = :op",
            engine=gate.runtime, match="only by a forward transition", op=op)
    fresh = admit(gate, incarnation)
    move(gate, fresh, "settled", units=1, amount=None, match="not a forward transition|ck_funding")
    move(gate, fresh, "dispatched", match="not a forward transition|ck_funding")
    no_drift(gate)


# ---- funded only over its own open, exact backing ------------------------------------------------------------------

def test_a_credits_admission_is_funded_only_over_its_own_open_exact_hold(gate):
    """Each case is keyed `fund:<op>` and wrong in exactly one attribute, so every clause is tested on its own."""
    incarnation, account = credits(gate)
    _, other_account = credits(gate)
    exact = "its own open, exact hold"
    cases = [dict(key="fund:not-{op}"), dict(meter="orena.message"), dict(account=other_account),
             dict(ref="other-ref"), dict(amount=PRICE * 2 - 1), dict(minutes=-1), dict(closed=True),
             dict(request_digest="0" * 64)]
    for case in cases:
        op = admit(gate, incarnation)
        held = PRICE * 2 if "amount" not in case else case["amount"]
        reserve = hold(gate, case.get("account", account), case.get("key", "fund:{op}").format(op=op), held,
                       meter=case.get("meter", "writing.review"), ref=case.get("ref", "ref-1"),
                       minutes=case.get("minutes"), request_digest=case.get("request_digest"))
        if case.get("closed"):
            close(gate, account, reserve, held, "release")  # closed while unexpired
        fund(gate, op, hold_id=reserve, match=exact)
        assert row(gate, op)["state"] == "admitting", case
    op = admit(gate, incarnation)
    fund(gate, op, hold_id=None, match=f"{exact}|ck_funding_snapshot")  # the guard runs before the CHECK
    live = hold(gate, account, f"fund:{op}", PRICE * 2)
    fund(gate, op, hold_id=live, gate_id=None, match="ck_funding_snapshot")
    fund(gate, op, hold_id=live, amount=PRICE * 2 + 1, match=f"{exact}|ck_funding_snapshot")
    fund(gate, op, hold_id=live)
    assert row(gate, op)["state"] == "funded"
    no_drift(gate)


def test_an_allowance_admission_is_funded_only_over_its_own_open_exact_quota_reservation(gate):
    """Each case is keyed `fund:<op>` (0007's operation id is globally unique) and wrong in exactly one attribute."""
    incarnation = gate.account()
    plan = bucket(gate, incarnation)
    other = bucket(gate, gate.account())
    other_meter = bucket(gate, incarnation, meter="orena.message")
    exact = "its own open, exact quota reservation"
    for case in (dict(key="fund:not-{op}"), dict(units=3), dict(bucket=other), dict(bucket=other_meter),
                 dict(released=True), dict(source="promotional")):
        op = admit(gate, incarnation)
        live = reservation(gate, case.get("bucket", plan), case.get("key", "fund:{op}").format(op=op),
                           units=case.get("units", 2))
        if case.get("released"):
            gate.sql("UPDATE commerce_quota_reservations SET state = 'released' WHERE id = :r", engine=gate.runtime,
                     r=live)
        fund(gate, op, source=case.get("source", "allowance"), quota=live, match=exact)  # a plan bucket is no grant
        assert row(gate, op)["state"] == "admitting", case
    op = admit(gate, incarnation)
    live = reservation(gate, plan, f"fund:{op}")
    fund(gate, op, source="allowance", quota=live)
    assert row(gate, op)["source"] == "allowance"


def test_a_deleted_account_is_never_funded_and_funding_waits_for_a_deletion(gate):
    incarnation = gate.account()
    plan = bucket(gate, incarnation)
    op = admit(gate, incarnation)
    live = reservation(gate, plan, f"fund:{op}")
    outcome = {}

    def funding():
        try:
            fund(gate, op, source="allowance", quota=live)
            outcome["result"] = "funded"
        except Exception as error:  # noqa: BLE001 - the refusal is the expected outcome
            outcome["result"] = str(error)

    deletion = gate.owner.connect()
    transaction = deletion.begin()
    worker = threading.Thread(target=funding, daemon=True)
    try:
        deletion.execute(gate.text("UPDATE account_incarnations SET status = 'deleted', deleted_at = now() "
                                   "WHERE id = :id"), {"id": incarnation})
        worker.start()
        worker.join(timeout=2.0)
        waited = worker.is_alive()
        transaction.commit()
    finally:
        if transaction.is_active:
            transaction.rollback()
        deletion.close()
    worker.join(timeout=10)
    assert waited, "funding must wait behind the deletion's incarnation lock"
    assert "deleted account is never admitted" in outcome["result"]
    assert row(gate, op)["state"] == "admitting"


# ---- settle, release, dispatch and refuse follow the backing --------------------------------------------------------

def test_a_credits_admission_settles_and_releases_only_over_its_holds_close(gate):
    incarnation, account, op, reserve = funded_on_credits(gate)
    move(gate, op, "settled", units=2, amount=PRICE * 2, match="settles over its hold")
    close(gate, account, reserve, PRICE * 2, "settle", charge=PRICE * 2)
    move(gate, op, "settled", units=1, amount=PRICE, match="settles over its hold")
    move(gate, op, "settled", units=1, amount=PRICE * 2, match="ck_funding_settled")
    move(gate, op, "released", match="released over its hold")
    move(gate, op, "settled", units=2, amount=PRICE * 2)
    _, _, released, held = funded_on_credits(gate)
    other = gate.sql("SELECT credit_account_id FROM credit_ledger WHERE id = :h", h=held)[0]["credit_account_id"]
    move(gate, released, "settled", units=0, amount=0, match="settles over its hold|ck_funding_settled")  # a zero outcome is a release
    move(gate, released, "released", match="released over its hold")
    close(gate, other, held, PRICE * 2, "release")
    move(gate, released, "released")
    no_drift(gate)


def test_an_allowance_admission_settles_and_releases_only_over_its_quota_reservation(gate):
    incarnation = gate.account()
    plan = bucket(gate, incarnation)
    ops = []
    for _ in range(3):
        op = admit(gate, incarnation)
        live = reservation(gate, plan, f"fund:{op}")
        fund(gate, op, source="allowance", quota=live)
        ops.append((op, live))
    (settle_op, settle_res), (zero_op, zero_res), (release_op, release_res) = ops
    move(gate, settle_op, "settled", units=2, match="settles over its settled quota")
    gate.sql("UPDATE commerce_quota_reservations SET state = 'settled', actual_units = 1 WHERE id = :r",
             engine=gate.runtime, r=settle_res)
    move(gate, settle_op, "settled", units=2, match="settles over its settled quota")
    move(gate, settle_op, "settled", units=1)
    gate.sql("UPDATE commerce_quota_reservations SET state = 'settled', actual_units = 0 WHERE id = :r",
             engine=gate.runtime, r=zero_res)
    move(gate, zero_op, "settled", units=0, match="ck_funding_settled")  # a zero outcome is a release
    move(gate, zero_op, "released")
    move(gate, release_op, "released", match="released over its released quota")
    gate.sql("UPDATE commerce_quota_reservations SET state = 'released' WHERE id = :r", engine=gate.runtime, r=release_res)
    move(gate, release_op, "released")


def test_a_dispatch_needs_its_backing_still_open(gate):
    incarnation, account, op, reserve = funded_on_credits(gate)
    close(gate, account, reserve, PRICE * 2, "reserve_expire")
    move(gate, op, "dispatched", match="hold still open")
    move(gate, op, "released")
    plan = bucket(gate, incarnation)
    op2 = admit(gate, incarnation)
    live = reservation(gate, plan, f"fund:{op2}")
    fund(gate, op2, source="allowance", quota=live)
    gate.sql("UPDATE commerce_quota_reservations SET state = 'released' WHERE id = :r", engine=gate.runtime, r=live)
    move(gate, op2, "dispatched", match="quota reservation still open")


def test_an_admission_is_refused_only_while_no_open_exact_backing_exists(gate):
    incarnation, account = credits(gate)
    op = admit(gate, incarnation)
    exact = hold(gate, account, f"fund:{op}", PRICE * 2)
    move(gate, op, "refused", reason="unbacked", match="adopted, never refused")
    close(gate, account, exact, PRICE * 2, "release")
    move(gate, op, "refused", reason="unbacked")
    plan = bucket(gate, incarnation)
    op2 = admit(gate, incarnation)
    live = reservation(gate, plan, f"fund:{op2}")
    move(gate, op2, "refused", reason="unbacked", match="adopted, never refused")
    gate.sql("UPDATE commerce_quota_reservations SET state = 'released' WHERE id = :r", engine=gate.runtime, r=live)
    move(gate, op2, "refused", reason="unbacked")
    op3 = admit(gate, incarnation)
    hold(gate, account, f"fund:{op3}", PRICE * 2, meter="orena.message")  # not exact: does not block, is a conflict
    move(gate, op3, "refused", reason="non_exact_backing")
    move(gate, admit(gate, incarnation), "refused", match="ck_funding_refused")


# ---- promotional grants --------------------------------------------------------------------------------------------

def claim(gate, user, incarnation, grant_id="welcome", *, days=7, match=None):
    statement = ("INSERT INTO promotional_grants (id, grant_id, user_id, incarnation_id, policy_version, claimed_at, "
                 "expires_at) VALUES (gen_random_uuid(), :g, :u, :i, 'grants-1', date_trunc('second', now()), "
                 "date_trunc('second', now()) + make_interval(days => :days)) RETURNING id")
    values = dict(g=grant_id, u=user, i=incarnation, days=days)
    if match:
        refused(gate, statement, engine=gate.runtime, match=match, **values)
        return None
    return gate.sql(statement, engine=gate.runtime, **values)[0]["id"]


def test_a_grant_is_claimed_once_per_account_ever_even_after_delete_and_re_register(gate):
    incarnation = gate.account()
    user = gate.sql("SELECT user_id FROM account_incarnations WHERE id = :i", i=incarnation)[0]["user_id"]
    grant = claim(gate, user, incarnation)
    claim(gate, user, incarnation, match="uq_promotional_grant_once_per_account")
    stranger = gate.account()
    claim(gate, user, stranger, grant_id="other", match="active incarnation of its own account")
    gate.delete(incarnation)
    claim(gate, user, incarnation, grant_id="other", match="active incarnation of its own account")
    reborn = uuid.uuid4()
    gate.sql("INSERT INTO account_incarnations (id, user_id, epoch, status, created_at) VALUES (:id, :u, 2, 'active', "
             "now())", id=reborn, u=user)
    claim(gate, user, reborn, match="uq_promotional_grant_once_per_account")
    claim(gate, user, reborn, grant_id="spring")
    for statement in ("UPDATE promotional_grants SET expires_at = expires_at + interval '1 day' WHERE id = :g",
                      "DELETE FROM promotional_grants WHERE id = :g"):
        refused(gate, statement, engine=gate.runtime, match="permission denied", g=grant)
        refused(gate, statement, match="immutable and never deleted", g=grant)
    refused(gate, "TRUNCATE promotional_grants CASCADE", match="append-only")


def test_a_promotional_bucket_is_its_grants_over_its_window_and_funds_a_promotional_admission(gate):
    incarnation = gate.account()
    user = gate.sql("SELECT user_id FROM account_incarnations WHERE id = :i", i=incarnation)[0]["user_id"]
    grant = claim(gate, user, incarnation)
    g = gate.sql("SELECT * FROM promotional_grants WHERE id = :g", g=grant)[0]
    window = dict(window=f"promo:{grant}", start=g["claimed_at"], end=g["expires_at"])
    bucket(gate, incarnation, grant=grant, window=f"promo:{grant}", start=g["claimed_at"],
           end=g["expires_at"] + timedelta(days=1), match="over the grant's window")
    bucket(gate, gate.account(), grant=grant, **window, match="its grant's")
    bucket(gate, incarnation, grant=grant, **dict(window, window="promo:other"), match="ck_commerce_quota_bucket_promotional")
    bucket(gate, incarnation, grant=grant, **window, limit=None, match="ck_commerce_quota_bucket_promotional")
    bucket(gate, incarnation, window=f"promo:{uuid.uuid4()}", match="ck_commerce_quota_bucket_promotional")
    promo = bucket(gate, incarnation, grant=grant, **window)
    refused(gate, "UPDATE commerce_quota_buckets SET window_end = window_end + interval '1 day' WHERE id = :b",
            engine=gate.runtime, match="never change", b=promo)
    gate.sql("UPDATE commerce_quota_buckets SET reserved = 2 WHERE id = :b", engine=gate.runtime, b=promo)
    op = admit(gate, incarnation)
    live = reservation(gate, promo, f"fund:{op}")
    fund(gate, op, source="allowance", quota=live, match="its own open, exact quota reservation")
    fund(gate, op, source="promotional", quota=live)
    assert row(gate, op)["source"] == "promotional"


# ---- attribution, the conflict item, privileges ----------------------------------------------------------------------

def test_a_cost_record_carries_operation_and_meter_both_or_neither(gate):
    incarnation = gate.account()
    user = gate.sql("SELECT user_id FROM account_incarnations WHERE id = :i", i=incarnation)[0]["user_id"]
    insert = ("INSERT INTO ai_cost_records (id, account_id, occurred_at, feature, cost_state, operation_id, meter) "
              "VALUES (gen_random_uuid(), :u, now(), 'test', 'estimated', :op, :m)")
    refused(gate, insert, engine=gate.runtime, match="ck_ai_cost_attribution", u=user, op="op-1", m=None)
    refused(gate, insert, engine=gate.runtime, match="ck_ai_cost_attribution", u=user, op=None, m="writing.review")
    gate.sql(insert, engine=gate.runtime, u=user, op="op-1", m="writing.review")
    gate.sql(insert, engine=gate.runtime, u=user, op=None, m=None)


def conflict_item(gate, op, *, admission=True):
    admission_id = row(gate, op)["id"]
    gate.sql("INSERT INTO billing_reconciliation_items (id, kind, gateway, dedupe_key, funding_admission_id, "
             "first_seen_at, last_seen_at) VALUES (gen_random_uuid(), 'funding_admission_conflict', 'funding', :k, :f, "
             "now(), now())", engine=gate.runtime, k=str(admission_id), f=admission_id if admission else None)
    return admission_id


def test_a_funding_conflict_closes_only_as_stray_released_by_the_reconciler(gate):
    incarnation, account = credits(gate)
    op = admit(gate, incarnation)
    stray = hold(gate, account, f"fund:{op}", PRICE * 2, meter="orena.message")
    move(gate, op, "refused", reason="non_exact_backing")
    with pytest.raises(Exception, match="ck_billing_item_funding_conflict"):
        conflict_item(gate, op, admission=False)
    admission_id = conflict_item(gate, op)
    resolve = ("UPDATE billing_reconciliation_items SET state = 'resolved', resolution_outcome = :o, resolved_by = :by, "
               "resolved_at = now() WHERE funding_admission_id = :f")
    refused(gate, resolve, engine=gate.runtime, match="nothing still open", o="stray_released", by="reconciler",
            f=admission_id)
    close(gate, account, stray, PRICE * 2, "release")
    refused(gate, resolve, engine=gate.runtime, match="ck_billing_item_funding_outcome|ck_billing_item_stray_released",
            o="stray_released", by="operator", f=admission_id)
    refused(gate, "UPDATE billing_reconciliation_items SET state = 'dismissed', resolved_at = now() "
            "WHERE funding_admission_id = :f", engine=gate.runtime, match="ck_billing_item_dismiss", f=admission_id)
    gate.sql(resolve, engine=gate.runtime, o="stray_released", by="reconciler", f=admission_id)
    refused(gate, "UPDATE billing_reconciliation_items SET funding_admission_id = NULL WHERE funding_admission_id = :f",
            engine=gate.runtime, match="never change|ck_billing_item_funding_conflict", f=admission_id)
    no_drift(gate)


def test_the_new_tables_belong_to_the_credit_owner_and_the_runtime_writes_only_lifecycle_columns(gate):
    owners = gate.sql("SELECT tablename, tableowner FROM pg_tables WHERE schemaname = :s AND tablename IN "
                      "('funding_admissions', 'promotional_grants')", s=gate.schema)
    assert {r["tableowner"] for r in owners} == {"orena_credit_owner"} and len(owners) == 2
    functions = gate.sql("SELECT p.proname, p.prosecdef, p.proconfig, pg_get_userbyid(p.proowner) AS owner FROM pg_proc p "
                         "JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = :s AND p.proname IN "
                         "('funding_admission_guard', 'promotional_grant_guard', 'quota_bucket_promotional_guard')",
                         s=gate.schema)
    assert len(functions) == 3
    for function in functions:
        assert function["prosecdef"] and function["owner"] == "orena_credit_owner"
        assert any(setting.startswith("search_path=") for setting in function["proconfig"])
    can = gate.sql("SELECT has_column_privilege(:r, 'funding_admissions', :c, 'UPDATE') AS can", r=gate.role, c="meter")
    assert can[0]["can"] is False
    for column in ("state", "settled_units", "credit_reserve_entry_id"):
        assert gate.sql("SELECT has_column_privilege(:r, 'funding_admissions', :c, 'UPDATE') AS can", r=gate.role,
                        c=column)[0]["can"] is True
    for table in ("funding_admissions", "promotional_grants"):
        for privilege in ("DELETE", "TRUNCATE"):
            assert gate.sql("SELECT has_table_privilege(:r, :t, :p) AS can", r=gate.role, t=table,
                            p=privilege)[0]["can"] is False
    assert gate.sql("SELECT has_table_privilege(:r, 'promotional_grants', 'UPDATE') AS can",
                    r=gate.role)[0]["can"] is False


# ---- migration-gate review of `5a2f5fd5` -----------------------------------------------------------------------------

def test_p1_1_the_exact_hold_carries_pr_mon_4s_reserve_digest(gate):
    """A hold made by PR-MON-4's own `reserve` with the admission's intent funds it; the same hold with any other
    digest is not exact: it cannot fund, and it does not block a refusal (it is a stray, never adopted)."""
    incarnation, account = credits(gate)
    op = admit(gate, incarnation)
    outcome = gate.repository.reserve(incarnation, amount=PRICE * 2, operation_id=f"fund:{op}", meter="writing.review",
                                      operation_ref="ref-1", ttl=timedelta(seconds=TTL))
    assert outcome.status == "applied", outcome
    move(gate, op, "refused", reason="unbacked", match="adopted, never refused")  # canonical: adopt it
    fund(gate, op, hold_id=outcome.entry["id"])
    assert row(gate, op)["state"] == "funded"

    forged = admit(gate, incarnation)
    wrong = hold(gate, account, f"fund:{forged}", PRICE * 2, request_digest=reserve_digest(gate, account, PRICE * 2,
                                                                                            ttl=TTL + 1))
    fund(gate, forged, hold_id=wrong, match="its own open, exact hold")
    assert row(gate, forged)["state"] == "admitting"
    move(gate, forged, "refused", reason="non_exact_backing")  # not exact: never adopted
    assert row(gate, forged)["state"] == "refused"
    no_drift(gate)


def test_p1_2_a_stray_in_another_account_keeps_the_conflict_open(gate):
    incarnation_a, _ = credits(gate)
    _, account_b = credits(gate)
    op = admit(gate, incarnation_a)
    stray = hold(gate, account_b, f"fund:{op}", PRICE * 2)  # B's open hold under A's key: a valid non-exact stray
    move(gate, op, "refused", reason="non_exact_backing")
    admission_id = conflict_item(gate, op)
    resolve = ("UPDATE billing_reconciliation_items SET state = 'resolved', resolution_outcome = 'stray_released', "
               "resolved_by = 'reconciler', resolved_at = now() WHERE funding_admission_id = :f")
    refused(gate, resolve, engine=gate.runtime, match="nothing still open", f=admission_id)
    close(gate, account_b, stray, PRICE * 2, "reserve_expire")
    gate.sql(resolve, engine=gate.runtime, f=admission_id)
    assert gate.sql("SELECT state FROM billing_reconciliation_items WHERE funding_admission_id = :f",
                    f=admission_id)[0]["state"] == "resolved"
    no_drift(gate)
