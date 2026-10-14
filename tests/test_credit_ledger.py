"""PR-MON-4 prepaid credits without a database: the request digest, the runtime-privilege gate, the admin routes,
the reconciler step and the migration's role precondition. The PostgreSQL proofs are in
`test_credit_ledger_postgres.py`."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from writing_coach import billing_api
from writing_coach.billing.credits import CreditService, credits_enabled
from writing_coach.persistence.credit_repository import CreditOutcome, digest


def test_the_digest_is_over_intent_in_a_canonical_order():
    assert digest(kind="reserve", amount=5, meter="m") == digest(meter="m", amount=5, kind="reserve")
    assert digest(kind="reserve", amount=5, meter="m") != digest(kind="reserve", amount=6, meter="m")
    assert len(digest(kind="x")) == 64


def test_credits_are_off_unless_switched_on():
    assert credits_enabled({}) is False and credits_enabled({"CREDITS_ENABLED": "1"}) is True


class Repository:
    def __init__(self, violations):
        self.violations = violations
        self.calls = []
        self.checks = 0

    def runtime_privilege_violations(self):
        self.checks += 1
        if isinstance(self.violations, Exception):
            raise self.violations
        return self.violations

    def topup(self, *args, **kwargs):
        self.calls.append(("topup", args, kwargs))
        return CreditOutcome("applied")


def test_a_privileged_connection_gets_no_credit_operation_and_writes_nothing():
    repository = Repository(["superuser", "update_credit_accounts_posted"])
    service = CreditService(repository)
    assert service.topup("inc", amount=1, source_type="t", source_ref="r").status == "credits_runtime_privileged"
    assert repository.calls == [] and service.status() == {
        "runtime_privileges": "privileged", "violations": ["superuser", "update_credit_accounts_posted"], "ready": False}
    assert service.ensure_account("inc") is None


def test_an_unreadable_privilege_check_is_unsafe_and_the_answer_is_kept_a_minute():
    clock = [0.0]
    repository = Repository(RuntimeError("down"))
    service = CreditService(repository, clock=lambda: clock[0])
    assert service.privilege_violations() == ["privilege_check_failed"]
    repository.violations = []
    assert service.privilege_violations() == ["privilege_check_failed"] and repository.checks == 1
    clock[0] = 61
    assert service.privilege_violations() == [] and service.topup("inc", amount=1, source_type="t",
                                                                   source_ref="r").status == "applied"


def test_the_reconciler_runs_the_credit_step_only_when_credits_exist():
    from writing_coach.billing.reconciler import BillingReconciler

    class Lock:
        def __call__(self):
            return self

        def __enter__(self):
            self.held = True
            return self

        def __exit__(self, *exc):
            return False

        def alive(self):
            return True

    class Service:
        def domestic_gateways(self):
            return []

    class Credits:
        def reconcile(self, *, items, now):
            return {"holds_closed": 2, "drift": 0}

    counts = BillingReconciler(service=Service(), orders=None, items=None, lock=Lock(), lookups={},
                               credits=Credits()).tick()  # fmt: skip
    assert counts["credit_holds_closed"] == 2
    plain = BillingReconciler(service=Service(), orders=None, items=None, lock=Lock(), lookups={}).tick()
    assert not any(key.startswith("credit_") for key in plain)


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(billing_api.router)
    monkeypatch.setattr(billing_api, "_admin", lambda request: {"google_sub": "admin-1"})
    return TestClient(app)


def test_the_credit_routes_answer_503_while_credits_are_off(client, monkeypatch):
    monkeypatch.setattr(billing_api, "_credits", None)
    assert client.get("/api/admin/billing/credits/11111111-1111-4111-8111-111111111111").status_code == 503


class Credits:
    def __init__(self):
        self.adjusted = []

    def status(self):
        return {"runtime_privileges": "ok", "violations": [], "ready": True}

    def balance(self, key):
        return {"posted": 5, "reserved": 0}

    def entries(self, key, **kwargs):
        return []

    def ensure_account(self, key):
        return {"id": "acct"}

    def adjust(self, key, **kwargs):
        self.adjusted.append((key, kwargs))
        return CreditOutcome("applied" if kwargs["delta"] > 0 else "insufficient_credits", entry={"id": "e1"})


def test_an_adjustment_is_recorded_with_the_administrator_as_actor(client, monkeypatch):
    credits = Credits()
    monkeypatch.setattr(billing_api, "_credits", credits)
    url = "/api/admin/billing/credits/11111111-1111-4111-8111-111111111111/adjustments"
    ok = client.post(url, json={"delta": 3, "operation_id": "adjust-0001", "reason": "goodwill"})
    assert ok.status_code == 200 and credits.adjusted[0][1]["actor"] == "admin-1"
    assert client.post(url, json={"delta": -9, "operation_id": "adjust-0002", "reason": "correction"}).status_code == 409
    assert client.post(url, json={"delta": 0, "operation_id": "adjust-0003", "reason": "zero"}).status_code == 422
    assert client.post(url, json={"delta": 1, "operation_id": "adjust-0004"}).status_code == 422  # a reason is required
    assert client.post("/api/admin/billing/credits/not-a-uuid/adjustments",
                       json={"delta": 1, "operation_id": "adjust-0005", "reason": "x y z"}).status_code == 404


def test_0032_creates_roles_only_as_a_superuser_and_refuses_before_any_ddl(monkeypatch):
    from tests.test_billing import _proposed

    migration = _proposed("20261014_0032_credit_ledger")

    class Result:
        def __init__(self, value):
            self.value = value

        def first(self):
            return self.value

        def scalar(self):
            return self.value

    class Connection:
        def execute(self, statement, params=None):
            text = str(statement)
            if "FROM pg_roles WHERE rolname = :r" in text:
                return Result(None)  # the roles are absent
            return Result(False)  # and the executor is not a superuser (CREATEROLE alone is not supported)

    created = []
    monkeypatch.setattr(migration.op, "execute", lambda sql: created.append(sql), raising=False)
    with pytest.raises(RuntimeError, match="only as a superuser"):
        migration._prerequisites(Connection(), "s", '"s"')
    assert created == []
