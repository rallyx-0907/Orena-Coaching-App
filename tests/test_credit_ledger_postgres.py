"""PR-MON-4 prepaid credit ledger on PostgreSQL (`ORENA_TEST_POSTGRES_URL`, throwaway database only).

Each test runs in its own schema at the Alembic head plus the proposed 0027, 0031 and 0032. The credit operations run
as a dedicated non-superuser LOGIN role, a member of `orena_credit_runtime` - the runtime the design requires - so the
privilege boundary is exercised, not assumed. The superuser engine only sets up and probes."""

from __future__ import annotations

import os
import threading
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import pytest

from tests.test_billing import ROOT, _proposed

URL = os.getenv("ORENA_TEST_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")

MIGRATIONS = ("20261005_0027_billing_orders", "20261014_0031_billing_reconciliation", "20261014_0032_credit_ledger")


def _migrate(engine, names, direction="upgrade"):
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext

    with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        for name in (names if direction == "upgrade" else reversed(names)):
            getattr(_proposed(name), direction)()


@pytest.fixture
def ledger():
    pytest.importorskip("alembic")
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    from writing_coach.billing.credits import CreditService
    from writing_coach.persistence.billing_reconciliation_repository import PostgresReconciliationRepository
    from writing_coach.persistence.credit_repository import PostgresCreditRepository

    schema = f"credit_{uuid.uuid4().hex[:10]}"
    role, password = f"orena_rt_{uuid.uuid4().hex[:10]}", uuid.uuid4().hex
    separator = "&" if "?" in URL else "?"
    options = f"{separator}options={quote(f'-csearch_path={schema}')}"
    admin = create_engine(URL, future=True)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("path_separator", "os")
    cfg.set_main_option("sqlalchemy.url", f"{URL}{options}".replace("%", "%%"))
    command.upgrade(cfg, "head")
    owner = create_engine(f"{URL}{options}", future=True)
    _migrate(owner, MIGRATIONS)
    with owner.begin() as connection:
        connection.execute(text(f"CREATE ROLE {role} LOGIN PASSWORD '{password}' NOSUPERUSER NOBYPASSRLS"))
        connection.execute(text(f"GRANT orena_credit_runtime TO {role}"))
        # what the application's runtime role already holds outside the credit tables
        connection.execute(text(f"GRANT SELECT, INSERT, UPDATE ON account_incarnations, users TO {role}"))
    runtime_url = make_url(f"{URL}{options}").set(username=role, password=password)
    runtime = create_engine(runtime_url, future=True, pool_size=12, max_overflow=4)
    repository = PostgresCreditRepository(runtime)
    service = CreditService(repository)

    def account(status="active"):
        user, incarnation = uuid.uuid4(), uuid.uuid4()
        now = datetime.now(UTC)
        with owner.begin() as connection:
            connection.execute(text("INSERT INTO users (id, user_key, email, name, picture, role, created_at) "
                                    "VALUES (:id, :key, '', '', '', 'user', :now)"), {"id": user, "key": f"u-{user}", "now": now})
            connection.execute(text("INSERT INTO account_incarnations (id, user_id, epoch, status, created_at) "
                                    "VALUES (:id, :user, 1, 'active', :now)"), {"id": incarnation, "user": user, "now": now})
        assert service.ensure_account(str(incarnation)) is not None
        if status == "deleted":
            delete(str(incarnation))
        return str(incarnation)

    def delete(incarnation):
        with owner.begin() as connection:
            connection.execute(text("UPDATE account_incarnations SET status = 'deleted', deleted_at = :now WHERE id = :id"),
                               {"now": datetime.now(UTC), "id": incarnation})

    def funded(credits=100):
        incarnation = account()
        topped = service.topup(incarnation, amount=credits, source_type="billing_order", source_ref=f"payos:{uuid.uuid4()}")
        assert topped.status == "applied", topped
        return incarnation, topped.entry

    def balance(incarnation):
        return repository.account(incarnation)

    def sql(statement, engine=None, **values):
        with (engine or owner).begin() as connection:
            result = connection.execute(text(statement), values)
            return result.mappings().all() if result.returns_rows else None

    world = type("Ledger", (), dict(
        owner=owner, runtime=runtime, admin=admin, schema=schema, role=role, repository=repository, service=service,
        items=PostgresReconciliationRepository(runtime), account=staticmethod(account), funded=staticmethod(funded),
        delete=staticmethod(delete), balance=staticmethod(balance), sql=staticmethod(sql),
        text=staticmethod(text)))  # fmt: skip
    yield world
    runtime.dispose()
    owner.dispose()
    with admin.begin() as connection:
        connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        connection.execute(text(f"DROP OWNED BY {role}"))
        connection.execute(text(f"DROP ROLE {role}"))
    admin.dispose()


def credit_items(ledger, kind, state=None):
    """Reconciliation items with their 0032 credit columns (the PR-MON-3 listing predates them)."""
    rows = ledger.sql("SELECT * FROM billing_reconciliation_items WHERE kind = :k ORDER BY first_seen_at", k=kind)
    return [dict(row) for row in rows if state is None or row["state"] == state]


def no_drift(ledger):
    assert ledger.repository.drift() == []


def refused(ledger, statement, engine=None, match=None, **values):
    from sqlalchemy.exc import DBAPIError

    with pytest.raises(DBAPIError, match=match):
        ledger.sql(statement, engine=engine, **values)


# ---- the migration ---------------------------------------------------------------------------------------------

def test_0032_goes_down_only_while_empty_and_restores_0031_exactly(ledger):
    guard = "SELECT prosrc FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace " \
            "WHERE p.proname = 'billing_reconciliation_items_guard' AND n.nspname = :s"
    checks = "SELECT conname, pg_get_constraintdef(oid) AS def FROM pg_constraint " \
             "WHERE conrelid = 'billing_reconciliation_items'::regclass ORDER BY conname"
    ledger.funded(10)
    with pytest.raises(RuntimeError, match="financial records"):
        _migrate(ledger.owner, (MIGRATIONS[2],), "downgrade")
    # a fresh schema: 0031 alone, then 0032 up and down, must leave 0031's guard and CHECKs exactly as they were
    from sqlalchemy import create_engine

    schema = f"credit_{uuid.uuid4().hex[:10]}"
    separator = "&" if "?" in URL else "?"
    engine = create_engine(f"{URL}{separator}options={quote(f'-csearch_path={schema}')}", future=True)
    try:
        ledger.sql(f'CREATE SCHEMA "{schema}"', engine=ledger.admin)
        from alembic import command
        from alembic.config import Config

        cfg = Config(str(ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(ROOT / "migrations"))
        cfg.set_main_option("path_separator", "os")
        cfg.set_main_option("sqlalchemy.url", str(engine.url.render_as_string(hide_password=False)).replace("%", "%%"))
        command.upgrade(cfg, "head")
        _migrate(engine, MIGRATIONS[:2])
        before = (ledger.sql(guard, engine=engine, s=schema), ledger.sql(checks, engine=engine))
        _migrate(engine, (MIGRATIONS[2],))
        after_up = ledger.sql(guard, engine=engine, s=schema)
        assert after_up != before[0] and "credit_requested" in after_up[0]["prosrc"]
        _migrate(engine, (MIGRATIONS[2],), "downgrade")
        assert (ledger.sql(guard, engine=engine, s=schema), ledger.sql(checks, engine=engine)) == before
        _migrate(engine, (MIGRATIONS[2],))  # and up again
    finally:
        engine.dispose()
        ledger.sql(f'DROP SCHEMA "{schema}" CASCADE', engine=ledger.admin)


def test_the_proposed_0028_still_applies_after_0032(ledger):
    with ledger.owner.begin() as connection:
        from alembic.operations import Operations
        from alembic.runtime.migration import MigrationContext

        reading = _proposed("20261005_0028_reading_derived_texts")
        with Operations.context(MigrationContext.configure(connection)):
            reading.upgrade()
            reading.downgrade()


# ---- the privilege boundary (P1-2) --------------------------------------------------------------------------------

def test_the_runtime_role_cannot_write_a_balance_or_rewrite_history(ledger):
    incarnation, topup = ledger.funded(50)
    rt = ledger.runtime
    for column in ("posted", "reserved", "entry_count", "last_entry_id"):
        value = "NULL" if column == "last_entry_id" else "999"
        refused(ledger, f"UPDATE credit_accounts SET {column} = {value} WHERE incarnation_id = :i", engine=rt,
                match="permission denied", i=incarnation)
    for statement in ("DELETE FROM credit_accounts", "TRUNCATE credit_accounts", "UPDATE credit_ledger SET amount = 1",
                      "DELETE FROM credit_ledger", "TRUNCATE credit_ledger", "UPDATE credit_reversal_requests SET applied = 0",
                      "DELETE FROM credit_reversal_requests", "TRUNCATE credit_reversal_requests",
                      "DELETE FROM billing_reconciliation_items", "TRUNCATE billing_reconciliation_items",
                      "CREATE TABLE intruder (x int)"):
        refused(ledger, statement, engine=rt, match="permission denied")
    refused(ledger, "INSERT INTO credit_accounts (id, incarnation_id, posted, created_at, updated_at) "
                    "VALUES (gen_random_uuid(), gen_random_uuid(), 5, now(), now())", engine=rt, match="permission denied")
    assert ledger.repository.runtime_privilege_violations() == []
    assert ledger.balance(incarnation)["posted"] == 50  # and the ledger insert did update it, through the function
    no_drift(ledger)


def test_the_guard_trigger_refuses_even_a_superuser_and_the_check_names_each_privilege(ledger):
    incarnation, _ = ledger.funded(5)
    refused(ledger, "UPDATE credit_accounts SET posted = 999 WHERE incarnation_id = :i", match="only through the ledger",
            i=incarnation)
    refused(ledger, "DELETE FROM credit_ledger", match="append-only")
    refused(ledger, "TRUNCATE credit_ledger", match="append-only|foreign key")  # refused either way
    from writing_coach.persistence.credit_repository import PostgresCreditRepository

    assert {"superuser", "bypassrls"} <= set(PostgresCreditRepository(ledger.owner).runtime_privilege_violations())
    for grant, violation in (("GRANT UPDATE (posted) ON credit_accounts TO {r}", "update_credit_accounts_posted"),
                             ("GRANT DELETE ON credit_ledger TO {r}", "delete_credit_ledger"),
                             ("GRANT TRUNCATE ON credit_reversal_requests TO {r}", "truncate_credit_reversal_requests"),
                             ("GRANT DELETE ON billing_reconciliation_items TO {r}", "delete_billing_reconciliation_items"),
                             ("GRANT CREATE ON SCHEMA {s} TO {r}", "create_on_schema"),
                             ("GRANT orena_credit_owner TO {r}", "member_of_owner")):
        ledger.sql(grant.format(r=ledger.role, s=f'"{ledger.schema}"'))
        assert violation in ledger.repository.runtime_privilege_violations(), violation
        ledger.sql(grant.format(r=ledger.role, s=f'"{ledger.schema}"').replace("GRANT", "REVOKE").replace(" TO ", " FROM "))
    assert ledger.repository.runtime_privilege_violations() == []


def test_a_privileged_connection_gets_no_credit_operation(ledger):
    from writing_coach.billing.credits import CreditService
    from writing_coach.persistence.credit_repository import PostgresCreditRepository

    incarnation = ledger.account()
    privileged = CreditService(PostgresCreditRepository(ledger.owner))
    outcome = privileged.topup(incarnation, amount=10, source_type="billing_order", source_ref="payos:x")
    assert outcome.status == "credits_runtime_privileged" and ledger.balance(incarnation)["posted"] == 0
    assert privileged.status()["ready"] is False


# ---- reserve / settle / release / reserve_expire --------------------------------------------------------------------

def test_reserve_settle_release_and_the_hard_cap(ledger):
    incarnation, _ = ledger.funded(100)
    s = ledger.service
    hold = s.reserve(incarnation, amount=40, operation_id="op-1", meter="orena.message")
    assert hold.status == "applied" and ledger.balance(incarnation)["available"] == 60
    assert s.reserve(incarnation, amount=40, operation_id="op-1", meter="orena.message").status == "duplicate"
    assert s.reserve(incarnation, amount=41, operation_id="op-1", meter="orena.message").status == "conflict"
    assert s.reserve(incarnation, amount=61, operation_id="op-2", meter="orena.message").status == "insufficient_credits"
    over = s.settle(incarnation, reserve_entry_id=hold.entry["id"], actual=55, operation_id="st-1")
    assert over.status == "applied" and over.extra == {"charged": 40, "uncharged": 15}  # C3: never beyond the hold
    assert ledger.balance(incarnation)["posted"] == 60 and ledger.balance(incarnation)["reserved"] == 0
    assert s.settle(incarnation, reserve_entry_id=hold.entry["id"], actual=55, operation_id="st-1").status == "duplicate"
    assert s.release(incarnation, reserve_entry_id=hold.entry["id"], operation_id="rl-1").status == "reservation_closed"
    second = s.reserve(incarnation, amount=10, operation_id="op-3", meter="orena.message")
    assert s.release(incarnation, reserve_entry_id=second.entry["id"], operation_id="rl-2").status == "applied"
    assert ledger.balance(incarnation)["available"] == 60
    no_drift(ledger)


def test_the_database_refuses_a_settle_beyond_its_hold_and_an_expiry_on_purchased_credit(ledger):
    incarnation, topup = ledger.funded(100)
    hold = ledger.service.reserve(incarnation, amount=10, operation_id="op", meter="m").entry
    account = ledger.balance(incarnation)["id"]
    insert = ("INSERT INTO credit_ledger (id, credit_account_id, kind, posted_delta, reserved_delta, amount, ref_entry_id, "
              "uncharged, expires_at, source_type, source_ref, idempotency_key, request_digest, actor, created_at) "
              "VALUES (gen_random_uuid(), :a, :kind, :p, :r, :amount, :ref, :unch, :exp, :st, :sr, :key, 'd', 'x', now())")
    refused(ledger, insert, engine=ledger.runtime, match="at most its hold", a=account, kind="settle", p=-11, r=-10,
            amount=11, ref=hold["id"], unch=0, exp=None, st=None, sr=None, key="k1")
    refused(ledger, insert, engine=ledger.runtime, match="ck_credit_ledger_expiry", a=account, kind="topup", p=5, r=0,
            amount=5, ref=None, unch=None, exp=datetime.now(UTC), st="t", sr="s", key="k2")
    refused(ledger, insert, engine=ledger.runtime, match="exactly its hold", a=account, kind="release", p=0, r=-3,
            amount=3, ref=hold["id"], unch=None, exp=None, st=None, sr=None, key="k3")
    refused(ledger, insert, engine=ledger.runtime, match="own account|names a reserve", a=account, kind="release", p=0,
            r=-100, amount=100, ref=topup["id"], unch=None, exp=None, st=None, sr=None, key="k4")
    no_drift(ledger)


def test_expires_at_is_set_in_the_reserve_transaction_and_is_authoritative(ledger):
    incarnation, _ = ledger.funded(10)
    before = datetime.now(UTC)
    hold = ledger.service.reserve(incarnation, amount=5, operation_id="op", meter="m").entry
    assert before + timedelta(minutes=29) < hold["expires_at"] <= datetime.now(UTC) + timedelta(minutes=30)
    short = ledger.service.reserve(incarnation, amount=1, operation_id="op-short", meter="m", ttl=timedelta(minutes=5))
    assert short.entry["expires_at"] < hold["expires_at"]
    assert ledger.service.reserve(incarnation, amount=1, operation_id="op-long", meter="m",
                                  ttl=timedelta(hours=2)).status == "invalid"


def test_a_late_settle_after_expiry_is_never_charged_and_is_recorded(ledger):
    incarnation, _ = ledger.funded(100)
    hold = ledger.service.reserve(incarnation, amount=30, operation_id="op", meter="m").entry
    later = datetime.now(UTC) + timedelta(minutes=31)
    assert ledger.service.reconcile(items=ledger.items, now=later)["holds_closed"] == 1
    assert ledger.service.reconcile(items=ledger.items, now=later)["holds_closed"] == 0  # a retry writes nothing
    assert ledger.repository.expire_reserve(incarnation, reserve_entry_id=hold["id"]).status == "duplicate"
    late = ledger.service.settle(incarnation, reserve_entry_id=hold["id"], actual=20, operation_id="st")
    assert late.status == "reservation_closed" and ledger.balance(incarnation)["posted"] == 100
    [item] = credit_items(ledger, "credit_late_settle")
    assert item["state"] == "open" and item["gateway"] == "credits"
    no_drift(ledger)


def test_concurrent_reserves_never_overdraw(ledger):
    incarnation, _ = ledger.funded(100)
    results, barrier = [], threading.Barrier(10)

    def reserve(index):
        barrier.wait()
        results.append(ledger.service.reserve(incarnation, amount=30, operation_id=f"op-{index}", meter="m").status)

    threads = [threading.Thread(target=reserve, args=(index,)) for index in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(results).count("applied") == 3 and results.count("insufficient_credits") == 7
    assert ledger.balance(incarnation)["reserved"] == 90
    no_drift(ledger)


def test_concurrent_closes_of_one_hold_close_it_once(ledger):
    incarnation, _ = ledger.funded(50)
    hold = ledger.service.reserve(incarnation, amount=20, operation_id="op", meter="m").entry
    results, barrier = [], threading.Barrier(6)

    def close(index):
        barrier.wait()
        if index % 2:
            results.append(ledger.service.settle(incarnation, reserve_entry_id=hold["id"], actual=5,
                                                 operation_id=f"st-{index}").status)
        else:
            results.append(ledger.service.release(incarnation, reserve_entry_id=hold["id"],
                                                  operation_id=f"rl-{index}").status)

    threads = [threading.Thread(target=close, args=(index,)) for index in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results.count("applied") == 1 and results.count("reservation_closed") == 5
    closes = ledger.sql("SELECT count(*) AS n FROM credit_ledger WHERE ref_entry_id = :h", h=hold["id"])
    assert closes[0]["n"] == 1
    no_drift(ledger)


# ---- refund / adjustment ------------------------------------------------------------------------------------------

def test_refunds_never_exceed_their_charge_even_concurrently(ledger):
    incarnation, _ = ledger.funded(100)
    hold = ledger.service.reserve(incarnation, amount=40, operation_id="op", meter="m").entry
    charge = ledger.service.settle(incarnation, reserve_entry_id=hold["id"], actual=40, operation_id="st").entry
    results, barrier = [], threading.Barrier(5)

    def refund(index):
        barrier.wait()
        results.append(ledger.service.refund(incarnation, settle_entry_id=charge["id"], amount=15,
                                             operation_id=f"rf-{index}", actor="admin-1", reason="provider failed").status)

    threads = [threading.Thread(target=refund, args=(index,)) for index in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results.count("applied") == 2  # 30 of the 40 charged; a third 15 would exceed it
    assert ledger.balance(incarnation)["posted"] == 90
    no_drift(ledger)


def test_an_adjustment_is_an_audited_delta_never_below_zero(ledger):
    incarnation, _ = ledger.funded(20)
    s = ledger.service
    assert s.adjust(incarnation, delta=5, operation_id="adj-1", actor="admin-1", reason="").status == "invalid"
    assert s.adjust(incarnation, delta=5, operation_id="adj-1", actor="admin-1", reason="goodwill").status == "applied"
    assert s.adjust(incarnation, delta=5, operation_id="adj-1", actor="admin-2", reason="other text").status == "duplicate"
    assert s.adjust(incarnation, delta=6, operation_id="adj-1", actor="admin-1", reason="goodwill").status == "conflict"
    assert s.adjust(incarnation, delta=-26, operation_id="adj-2", actor="admin-1", reason="x").status == "insufficient_credits"
    assert ledger.balance(incarnation)["posted"] == 25
    no_drift(ledger)


# ---- reversal (C5, P1-3, P1-4, P1-5) ---------------------------------------------------------------------------------

def reverse(ledger, incarnation, topup, requested, event):
    return ledger.service.reverse(incarnation, topup_entry_id=topup["id"], requested=requested, source_type="payos_refund",
                                  source_ref=event, actor="system", reason="the payment was refunded")


def test_case_1_a_partly_reversed_topup_reverses_only_what_remains(ledger):
    incarnation, topup = ledger.funded(100)
    assert reverse(ledger, incarnation, topup, 80, "rf-1").extra["request"]["applied"] == 80
    ledger.service.topup(incarnation, amount=50, source_type="billing_order", source_ref="payos:more")
    outcome = reverse(ledger, incarnation, topup, 30, "rf-2")
    request = outcome.extra["request"]
    assert (request["requested"], request["applied"], request["shortfall"]) == (30, 20, 10)
    assert outcome.entry["amount"] == 20
    [item] = credit_items(ledger, "credit_reversal_shortfall")
    assert (item["credit_requested"], item["credit_applied"], item["credit_shortfall"]) == (30, 20, 10)
    assert str(item["credit_reversal_entry_id"]) == str(outcome.entry["id"])
    no_drift(ledger)


def test_case_2_and_3_a_reversal_with_nothing_available_is_final(ledger):
    incarnation, topup = ledger.funded(40)
    hold = ledger.service.reserve(incarnation, amount=40, operation_id="op", meter="m").entry  # all credit held
    first = reverse(ledger, incarnation, topup, 40, "rf-0")
    assert first.entry is None and first.extra["request"]["applied"] == 0 and first.extra["request"]["shortfall"] == 40
    assert ledger.balance(incarnation)["reserved"] == 40  # never taken from a reservation
    ledger.service.release(incarnation, reserve_entry_id=hold["id"], operation_id="rl")
    ledger.service.topup(incarnation, amount=100, source_type="billing_order", source_ref="payos:later")
    again = reverse(ledger, incarnation, topup, 40, "rf-0")  # case 3: newly available credit is not reversed
    assert again.status == "duplicate" and again.entry is None and again.extra["request"]["applied"] == 0
    assert ledger.balance(incarnation)["posted"] == 140
    assert ledger.sql("SELECT count(*) AS n FROM credit_ledger WHERE kind = 'reversal'")[0]["n"] == 0
    [item] = credit_items(ledger, "credit_reversal_shortfall")
    assert item["credit_reversal_entry_id"] is None and item["credit_shortfall"] == 40


def test_case_4_and_p1_5_one_money_event_reverses_once_in_one_account(ledger):
    incarnation, topup = ledger.funded(100)
    other, other_topup = ledger.funded(100)
    assert reverse(ledger, incarnation, topup, 10, "rf-x").status == "applied"
    assert reverse(ledger, incarnation, topup, 11, "rf-x").status == "conflict"  # changed requested
    assert reverse(ledger, other, other_topup, 10, "rf-x").status == "conflict"  # another account
    refused(ledger, "INSERT INTO credit_reversal_requests (id, credit_account_id, topup_entry_id, idempotency_key, "
                    "request_digest, requested, applied, shortfall, source_type, source_ref, actor, reason, created_at) "
                    "VALUES (gen_random_uuid(), :a, :t, 'k', 'd', 1, 1, 0, 'payos_refund', 'rf-x', 'x', 'x', now())",
            engine=ledger.runtime, match="uq_credit_reversal_money_event", a=ledger.balance(other)["id"], t=other_topup["id"])
    assert ledger.balance(incarnation)["posted"] == 90 and ledger.balance(other)["posted"] == 100


def test_case_5_concurrent_reversals_never_exceed_the_topup(ledger):
    incarnation, topup = ledger.funded(100)
    ledger.service.topup(incarnation, amount=500, source_type="billing_order", source_ref="payos:pad")
    results, barrier = [], threading.Barrier(6)

    def run(index):
        barrier.wait()
        results.append(reverse(ledger, incarnation, topup, 30, f"rf-c{index}").extra["request"]["applied"])

    threads = [threading.Thread(target=run, args=(index,)) for index in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sum(results) == 100 and sorted(results) == [0, 0, 10, 30, 30, 30]
    no_drift(ledger)


def test_p1_4_a_reversal_entry_applies_exactly_its_own_request(ledger):
    incarnation, topup = ledger.funded(100)
    request = reverse(ledger, incarnation, topup, 10, "rf-a").extra["request"]
    account = ledger.balance(incarnation)["id"]
    insert = ("INSERT INTO credit_ledger (id, credit_account_id, kind, posted_delta, reserved_delta, amount, ref_entry_id, "
              "reversal_request_id, idempotency_key, request_digest, actor, reason, created_at) VALUES "
              "(gen_random_uuid(), :a, 'reversal', :p, 0, :amount, :ref, :req, :key, 'd', 'x', 'x', now())")
    refused(ledger, insert, engine=ledger.runtime, match="uq_credit_ledger_reversal_request", a=account, p=-10, amount=10,
            ref=topup["id"], req=request["id"], key="again")
    refused(ledger, "INSERT INTO credit_ledger (id, credit_account_id, kind, posted_delta, reserved_delta, amount, "
                    "ref_entry_id, idempotency_key, request_digest, actor, reason, created_at) VALUES (gen_random_uuid(), "
                    ":a, 'reversal', -5, 0, 5, :ref, 'k', 'd', 'x', 'x', now())", engine=ledger.runtime,
            match="ck_credit_ledger_reversal_request|exactly its request", a=account, ref=topup["id"])
    refused(ledger, "INSERT INTO credit_reversal_requests (id, credit_account_id, topup_entry_id, idempotency_key, "
                    "request_digest, requested, applied, shortfall, source_type, source_ref, actor, reason, created_at) "
                    "VALUES (gen_random_uuid(), :a, :t, 'k2', 'd', 50, 40, 10, 's', 'r2', 'x', 'x', now())",
            engine=ledger.runtime, match="min\\(requested, available, remaining", a=account, t=topup["id"])


# ---- deletion (C1, C2) ---------------------------------------------------------------------------------------------

def test_a_deleted_account_keeps_its_credit_as_a_liability_and_takes_no_new_charge(ledger):
    incarnation, topup = ledger.funded(70)
    hold = ledger.service.reserve(incarnation, amount=20, operation_id="op", meter="m").entry
    ledger.delete(incarnation)
    s = ledger.service
    assert s.topup(incarnation, amount=5, source_type="billing_order", source_ref="payos:after").status == "account_deleted"
    assert s.reserve(incarnation, amount=5, operation_id="op2", meter="m").status == "account_deleted"
    assert s.settle(incarnation, reserve_entry_id=hold["id"], actual=5, operation_id="st").status == "account_deleted"
    refused(ledger, "INSERT INTO credit_ledger (id, credit_account_id, kind, posted_delta, reserved_delta, amount, "
                    "source_type, source_ref, idempotency_key, request_digest, actor, created_at) VALUES "
                    "(gen_random_uuid(), :a, 'topup', 5, 0, 5, 't', 'direct', 'k', 'd', 'x', now())",
            engine=ledger.runtime, match="deleted account", a=ledger.balance(incarnation)["id"])
    counts = s.reconcile(items=ledger.items, now=datetime.now(UTC))
    assert counts["holds_closed"] == 1 and counts["deletion_liabilities"] == 1
    [liability] = credit_items(ledger, "credit_balance_on_deletion")
    assert liability["credit_balance_posted"] == 70 and liability["state"] == "open"
    assert s.reconcile(items=ledger.items, now=datetime.now(UTC))["deletion_liabilities"] == 0
    assert s.reverse(incarnation, topup_entry_id=topup["id"], requested=10, source_type="payos_refund", source_ref="del",
                     actor="admin-1", reason="refunded").status == "applied"  # obligations can still be settled
    refused(ledger, "DELETE FROM account_incarnations WHERE id = :i", match="foreign key|violates", i=incarnation)
    fresh = ledger.account()  # C2: a new incarnation starts empty, never inherits
    assert ledger.balance(fresh)["posted"] == 0
    no_drift(ledger)


# ---- drift (an incident, never repaired by hand) ---------------------------------------------------------------------

def test_drift_opens_a_critical_item_stops_the_account_and_resolves_only_when_consistent(ledger):
    incarnation, _ = ledger.funded(30)
    with ledger.owner.begin() as connection:  # simulate the impossible: bypass the triggers as a superuser
        connection.execute(ledger.text("SET LOCAL session_replication_role = replica"))
        connection.execute(ledger.text("UPDATE credit_accounts SET posted = 31 WHERE incarnation_id = :i"), {"i": incarnation})
    counts = ledger.service.reconcile(items=ledger.items, now=datetime.now(UTC))
    assert counts["drift"] == 1
    [item] = credit_items(ledger, "credit_balance_drift", "open")
    assert (item["credit_expected_posted"], item["credit_snapshot_posted"]) == (30, 31)
    assert ledger.service.reserve(incarnation, amount=1, operation_id="op", meter="m").status == "account_under_review"
    from writing_coach.persistence.billing_reconciliation_repository import ResolutionRefused

    with pytest.raises(ResolutionRefused):
        ledger.items.resolve(item["id"], resolution="resolved", outcome="balance_consistent", reference=None,
                             note="fixed", actor="admin-1")  # fmt: skip
    with ledger.owner.begin() as connection:
        connection.execute(ledger.text("SET LOCAL session_replication_role = replica"))
        connection.execute(ledger.text("UPDATE credit_accounts SET posted = 30 WHERE incarnation_id = :i"), {"i": incarnation})
    assert ledger.service.reconcile(items=ledger.items, now=datetime.now(UTC))["drift_resolved"] == 1
    assert ledger.service.reserve(incarnation, amount=1, operation_id="op", meter="m").status == "applied"


# ---- the reconciliation schema 0032 adds (P1-6) ----------------------------------------------------------------------

def test_credit_items_need_their_references_and_their_facts_never_change(ledger):
    incarnation, topup = ledger.funded(10)
    account = ledger.balance(incarnation)["id"]
    insert = ("INSERT INTO billing_reconciliation_items (id, kind, gateway, dedupe_key, state, first_seen_at, last_seen_at, "
              "credit_account_id, credit_topup_entry_id, credit_requested, credit_applied, credit_shortfall) VALUES "
              "(gen_random_uuid(), :kind, :gw, :key, 'open', now(), now(), :a, :t, :rq, :ap, :sf)")
    refused(ledger, insert, engine=ledger.runtime, match="ck_billing_item_credit_shortfall", kind="credit_reversal_shortfall",
            gw="credits", key="k1", a=account, t=topup["id"], rq=10, ap=5, sf=5)  # no request reference
    refused(ledger, insert, engine=ledger.runtime, match="ck_billing_item_credit_scope", kind="event_undecided",
            gw="polar", key="k2", a=account, t=None, rq=None, ap=None, sf=None)  # a credit fact on a non-credit kind
    refused(ledger, insert, engine=ledger.runtime, match="ck_billing_item_credit_(scope|late_settle)", kind="credit_late_settle",
            gw="payos", key="k3", a=account, t=None, rq=None, ap=None, sf=None)
    hold = ledger.service.reserve(incarnation, amount=5, operation_id="op", meter="m").entry
    ledger.service.release(incarnation, reserve_entry_id=hold["id"], operation_id="rl")
    ledger.service.settle(incarnation, reserve_entry_id=hold["id"], actual=3, operation_id="late")
    [item] = credit_items(ledger, "credit_late_settle")
    refused(ledger, "UPDATE billing_reconciliation_items SET credit_actual = 0 WHERE id = :id", engine=ledger.runtime,
            match="facts never change", id=item["id"])
    ledger.items.resolve(item["id"], resolution="dismissed", outcome=None, reference=None, note="cost absorbed",
                         actor="admin-1")  # fmt: skip
    # PR-MON-3's own rules still hold after 0032
    money = ledger.items.record(kind="payment_mismatch", gateway="payos", dedupe_key="evt-1")
    refused(ledger, "UPDATE billing_reconciliation_items SET state = 'dismissed', resolved_by = 'a', resolved_at = now() "
                    "WHERE id = :id", engine=ledger.runtime, match="ck_billing_item_dismiss", id=money["id"])


# ---- database backstops without the repository (a writer that skips its checks) --------------------------------------

DIRECT = ("INSERT INTO credit_ledger (id, credit_account_id, kind, posted_delta, reserved_delta, amount, ref_entry_id, "
          "uncharged, expires_at, source_type, source_ref, idempotency_key, request_digest, actor, reason, created_at) "
          "VALUES (gen_random_uuid(), :a, :kind, :p, :r, :amount, :ref, :unch, :exp, :st, :sr, :key, 'd', 'x', :reason, now())")


def direct(ledger, account, kind, posted, reserved, amount, *, ref=None, uncharged=None, expires=None, source=None,
           key=None, reason=None, match=None):
    values = dict(a=account, kind=kind, p=posted, r=reserved, amount=amount, ref=ref, unch=uncharged, exp=expires,
                  st=source and "billing_order", sr=source, key=key or uuid.uuid4().hex, reason=reason)
    if match is None:
        ledger.sql(DIRECT, engine=ledger.runtime, **values)
    else:
        refused(ledger, DIRECT, engine=ledger.runtime, match=match, **values)


def test_the_balance_check_refuses_an_overdraw_the_repository_did_not_stop(ledger):
    incarnation, _ = ledger.funded(10)
    account = ledger.balance(incarnation)["id"]
    direct(ledger, account, "reserve", 0, 11, 11, expires=datetime.now(UTC) + timedelta(minutes=5),
           match="ck_credit_account_balance")
    direct(ledger, account, "adjustment", -11, 0, 11, reason="x", match="ck_credit_account_balance")
    assert ledger.balance(incarnation)["posted"] == 10 and ledger.balance(incarnation)["reserved"] == 0
    no_drift(ledger)


def test_a_hold_closes_once_and_offsets_name_their_own_kind_even_inserted_directly(ledger):
    incarnation, topup = ledger.funded(100)
    account = ledger.balance(incarnation)["id"]
    hold = ledger.service.reserve(incarnation, amount=20, operation_id="op", meter="m").entry
    charge = ledger.service.settle(incarnation, reserve_entry_id=hold["id"], actual=20, operation_id="st").entry
    # another open hold keeps `reserved` high enough, so only the close-once index can refuse a second close
    ledger.service.reserve(incarnation, amount=30, operation_id="op-2", meter="m")
    direct(ledger, account, "release", 0, -20, 20, ref=hold["id"], match="uq_credit_ledger_close_once")
    direct(ledger, account, "refund", 5, 0, 5, ref=topup["id"], reason="x", match="a refund names a settle")
    direct(ledger, account, "refund", 15, 0, 15, ref=charge["id"], reason="x")
    direct(ledger, account, "refund", 6, 0, 6, ref=charge["id"], reason="x", match="never exceed it")
    assert ledger.balance(incarnation)["posted"] == 95 and ledger.balance(incarnation)["reserved"] == 30
    no_drift(ledger)


def test_one_money_event_credits_once_even_inserted_directly(ledger):
    incarnation, topup = ledger.funded(10)
    other = ledger.account()
    direct(ledger, ledger.balance(other)["id"], "topup", 10, 0, 10, source=topup["source_ref"],
           match="uq_credit_ledger_topup_source")
    assert ledger.balance(other)["posted"] == 0


def test_an_empty_credit_account_is_still_never_deleted(ledger):
    incarnation = ledger.account()
    refused(ledger, "DELETE FROM credit_accounts WHERE incarnation_id = :i", match="never deleted", i=incarnation)


def test_the_snapshot_function_is_security_definer_with_a_fixed_search_path(ledger):
    rows = ledger.sql("SELECT p.proname, p.prosecdef, p.proconfig, pg_get_userbyid(p.proowner) AS owner FROM pg_proc p "
                      "JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = :s AND p.proname IN "
                      "('credit_apply_entry', 'credit_check_reversal_request')", s=ledger.schema)
    assert len(rows) == 2
    for row in rows:
        assert row["prosecdef"] is True and row["owner"] == "orena_credit_owner"
        assert row["proconfig"] == [f"search_path={ledger.schema}, pg_catalog, pg_temp"]
    privileges = ledger.sql("SELECT has_function_privilege(:r, :f, 'EXECUTE') AS can", r=ledger.role,
                            f=f"{ledger.schema}.credit_apply_entry()")
    assert privileges[0]["can"] is False


# ---- implementation review P1s (2026-10-14) ----------------------------------------------------------------------------

def _login(admin, name, password):
    from sqlalchemy import text

    with admin.begin() as connection:
        connection.execute(text(f"CREATE ROLE {name} LOGIN PASSWORD '{password}' NOSUPERUSER NOBYPASSRLS"))


def _engine_as(name, password, schema):
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url

    separator = "&" if "?" in URL else "?"
    url = make_url(f"{URL}{separator}options={quote(f'-csearch_path={schema}')}").set(username=name, password=password)
    return create_engine(url, future=True)


def _head(engine):
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("path_separator", "os")
    cfg.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False).replace("%", "%%"))
    command.upgrade(cfg, "head")


def test_p1_1_a_non_superuser_executor_with_provisioned_roles_runs_0032_and_its_downgrade(ledger):
    from sqlalchemy import text

    executor, password = f"orena_exec_{uuid.uuid4().hex[:8]}", uuid.uuid4().hex
    schema = f"credit_{uuid.uuid4().hex[:10]}"
    _login(ledger.admin, executor, password)
    ledger.sql(f'CREATE SCHEMA "{schema}" AUTHORIZATION {executor}', engine=ledger.admin)
    engine = _engine_as(executor, password, schema)
    try:
        _head(engine)  # the whole chain, as the non-superuser that owns the schema
        _migrate(engine, MIGRATIONS[:2])
        # not yet able to act as the owner role: refused before any credit DDL
        with pytest.raises(RuntimeError, match="WITH SET"):
            _migrate(engine, (MIGRATIONS[2],))
        assert ledger.sql("SELECT to_regclass(:t) AS t", t=f'"{schema}".credit_accounts')[0]["t"] is None
        ledger.sql(f"GRANT orena_credit_owner TO {executor}", engine=ledger.admin)  # provisioned out of band
        _migrate(engine, (MIGRATIONS[2],))
        owners = ledger.sql("SELECT tablename, tableowner FROM pg_tables WHERE schemaname = :s AND tablename LIKE 'credit_%'",
                            s=schema)
        assert {row["tableowner"] for row in owners} == {"orena_credit_owner"} and len(owners) == 3
        _migrate(engine, (MIGRATIONS[2],), "downgrade")  # an empty schema goes down in this mode too
        assert ledger.sql("SELECT to_regclass(:t) AS t", t=f'"{schema}".credit_ledger')[0]["t"] is None
        assert ledger.sql("SELECT count(*) AS n FROM pg_roles WHERE rolname = 'orena_credit_owner'")[0]["n"] == 1
        _migrate(engine, (MIGRATIONS[2],))  # and up again
        with engine.connect() as connection:
            assert connection.execute(text("SELECT count(*) FROM credit_accounts")).scalar() == 0
    finally:
        engine.dispose()
        ledger.sql(f'DROP SCHEMA "{schema}" CASCADE', engine=ledger.admin)
        ledger.sql(f"DROP OWNED BY {executor}", engine=ledger.admin)
        ledger.sql(f"DROP ROLE {executor}", engine=ledger.admin)


def test_p1_1_an_existing_role_that_is_not_safe_is_refused_before_any_ddl(ledger):
    from sqlalchemy import create_engine

    schema = f"credit_{uuid.uuid4().hex[:10]}"
    separator = "&" if "?" in URL else "?"
    engine = create_engine(f"{URL}{separator}options={quote(f'-csearch_path={schema}')}", future=True)
    ledger.sql(f'CREATE SCHEMA "{schema}"', engine=ledger.admin)
    try:
        _head(engine)
        _migrate(engine, MIGRATIONS[:2])
        for unsafe, restore in (("LOGIN", "NOLOGIN"), ("BYPASSRLS", "NOBYPASSRLS")):
            ledger.sql(f"ALTER ROLE orena_credit_owner {unsafe}", engine=ledger.admin)
            try:
                with pytest.raises(RuntimeError, match="NOLOGIN, NOSUPERUSER and NOBYPASSRLS"):
                    _migrate(engine, (MIGRATIONS[2],))
            finally:
                ledger.sql(f"ALTER ROLE orena_credit_owner {restore}", engine=ledger.admin)
            assert ledger.sql("SELECT to_regclass(:t) AS t", t=f'"{schema}".credit_accounts')[0]["t"] is None
        ledger.sql("GRANT orena_credit_owner TO orena_credit_runtime", engine=ledger.admin)
        try:
            with pytest.raises(RuntimeError, match="must not be a member"):
                _migrate(engine, (MIGRATIONS[2],))
        finally:
            ledger.sql("REVOKE orena_credit_owner FROM orena_credit_runtime", engine=ledger.admin)
    finally:
        engine.dispose()
        ledger.sql(f'DROP SCHEMA "{schema}" CASCADE', engine=ledger.admin)


def test_p1_2_a_harmless_role_without_runtime_membership_is_not_ready_until_it_is_a_member(ledger):
    from writing_coach.billing.credits import CreditService
    from writing_coach.persistence.credit_repository import PostgresCreditRepository

    incarnation = ledger.account()
    name, password = f"orena_lonely_{uuid.uuid4().hex[:8]}", uuid.uuid4().hex
    _login(ledger.admin, name, password)
    ledger.sql(f'GRANT USAGE ON SCHEMA "{ledger.schema}" TO {name}')
    ledger.sql(f"GRANT SELECT, INSERT, UPDATE ON account_incarnations, users TO {name}")
    engine = _engine_as(name, password, ledger.schema)
    try:
        lonely = CreditService(PostgresCreditRepository(engine))
        status = lonely.status()
        assert status["ready"] is False and "missing_runtime_membership" in status["violations"]
        assert not ({"superuser", "bypassrls", "member_of_owner", "create_on_schema"} & set(status["violations"]))
        refused_topup = lonely.topup(incarnation, amount=10, source_type="billing_order", source_ref="payos:lonely")
        assert refused_topup.status == "credits_runtime_privileged"
        assert ledger.sql("SELECT count(*) AS n FROM credit_ledger")[0]["n"] == 0  # refused before any mutation
        ledger.sql(f"GRANT orena_credit_runtime TO {name}")
        member = CreditService(PostgresCreditRepository(engine))  # a fresh check, not the cached answer
        assert member.status() == {"runtime_privileges": "ok", "violations": [], "ready": True}
        assert member.topup(incarnation, amount=10, source_type="billing_order", source_ref="payos:lonely").status == "applied"
    finally:
        engine.dispose()
        ledger.sql(f"DROP OWNED BY {name}", engine=ledger.admin)
        ledger.sql(f"DROP ROLE {name}", engine=ledger.admin)


@pytest.mark.parametrize("kind", ["topup", "reserve"])
def test_p1_3_a_direct_insert_waits_for_a_deletion_and_then_fails(ledger, kind):
    incarnation, _ = ledger.funded(50) if kind == "reserve" else (ledger.account(), None)
    account = ledger.balance(incarnation)["id"]
    before = ledger.balance(incarnation)
    entries = ledger.sql("SELECT count(*) AS n FROM credit_ledger WHERE credit_account_id = :a", a=account)[0]["n"]
    outcome = {}

    def insert():
        try:
            if kind == "topup":
                direct(ledger, account, "topup", 10, 0, 10, source=f"payos:race-{uuid.uuid4()}")
            else:
                direct(ledger, account, "reserve", 0, 10, 10, expires=datetime.now(UTC) + timedelta(minutes=5))
            outcome["result"] = "inserted"
        except Exception as error:  # noqa: BLE001 - the refusal is the expected outcome
            outcome["result"] = str(error)

    deletion = ledger.owner.connect()
    transaction = deletion.begin()
    worker = threading.Thread(target=insert, daemon=True)
    try:
        deletion.execute(ledger.text("UPDATE account_incarnations SET status = 'deleted', deleted_at = now() "
                                     "WHERE id = :id"), {"id": incarnation})  # locked and changed, not committed
        worker.start()
        worker.join(timeout=2.0)
        waited = worker.is_alive()
        transaction.commit()
    finally:
        # never leave the deletion open: a failed assertion must not hold locks the teardown needs
        if transaction.is_active:
            transaction.rollback()
        deletion.close()
    worker.join(timeout=10)
    assert waited, "the insert must wait behind the deletion's incarnation lock"
    assert "deleted account" in outcome["result"]
    assert ledger.balance(incarnation)["posted"] == before["posted"]
    assert ledger.balance(incarnation)["reserved"] == before["reserved"]
    assert ledger.sql("SELECT count(*) AS n FROM credit_ledger WHERE credit_account_id = :a", a=account)[0]["n"] == entries
    no_drift(ledger)
