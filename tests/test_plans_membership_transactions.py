"""Review of #112: the plan catalogue's stale-save check, the membership change and their audit rows are atomic.

Runs the real repository code on a SQLAlchemy engine (SQLite here; PostgreSQL in the runtime, where the same reads
are `SELECT ... FOR UPDATE`), plus the frozen SQLite archive store's own compare-and-set under real threads.
"""

import threading
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from writing_coach.persistence import platform_repository as platform
from writing_coach.persistence.models import AuditLog, Base, PlanRecord, PlatformSetting, Subscription, User
from writing_coach.persistence.platform_repository import (
    PostgresPlatformRepository,
    SettingConflict,
    SQLitePlatformRepository,
)
from writing_coach.persistence.product_repository import PostgresProductRepository
from writing_coach.product.membership import MembershipConflict, apply_change

AUDIT = {"action": "product.plans.update", "actor": "admin-sub", "entity_type": "plan_catalog", "entity_id": "x",
         "payload": {"plans": ["free", "plus", "pro"]}}


@pytest.fixture()
def engine(tmp_path):
    engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'tx.db'}", future=True)
    Base.metadata.create_all(engine, tables=[User.__table__, PlanRecord.__table__, Subscription.__table__,
                                             AuditLog.__table__, PlatformSetting.__table__])
    return engine


def audit_rows(engine, action):
    with Session(engine) as session:
        return session.query(AuditLog).filter(AuditLog.action == action).count()


# --- 1. Plan catalogue: compare-and-set in the write transaction, audit committed with it -----------------------------
def test_a_stale_save_is_refused_and_leaves_no_change_and_no_audit(engine):
    repo = PostgresPlatformRepository(engine=engine)
    first = repo.set_setting("k", {"v": 1}, updated_by="a", expected_updated_at=None, audit=AUDIT)
    assert audit_rows(engine, "product.plans.update") == 1
    # Two administrators opened the page at `first`; one saves, then the other.
    second = repo.set_setting("k", {"v": 2}, updated_by="a", expected_updated_at=first["updated_at"], audit=AUDIT)
    with pytest.raises(SettingConflict):
        repo.set_setting("k", {"v": 3}, updated_by="b", expected_updated_at=first["updated_at"], audit=AUDIT)
    assert repo.get_setting("k")["value"] == {"v": 2}, "the later stale write did not win"
    assert audit_rows(engine, "product.plans.update") == 2, "the refused write left no audit row"
    with pytest.raises(SettingConflict):
        repo.set_setting("k", {"v": 4}, expected_updated_at=None)
    assert repo.set_setting("k", {"v": 5}, expected_updated_at=second["updated_at"])["value"] == {"v": 5}


def test_a_failing_audit_row_rolls_the_catalogue_change_back(engine, monkeypatch):
    repo = PostgresPlatformRepository(engine=engine)
    repo.set_setting("k", {"v": 1}, expected_updated_at=None)

    def broken(session, audit, now):
        raise RuntimeError("audit store down")

    monkeypatch.setattr(platform, "_add_audit", broken)
    with pytest.raises(RuntimeError):
        repo.set_setting("k", {"v": 2}, audit=AUDIT)
    assert repo.get_setting("k")["value"] == {"v": 1}, "no unaudited change"


def test_concurrent_writers_from_one_version_let_exactly_one_through(tmp_path):
    repo = SQLitePlatformRepository(tmp_path / "platform.db")
    base = repo.set_setting("k", {"v": 0}, expected_updated_at=None)
    barrier = threading.Barrier(6)
    outcomes = []

    def writer(n):
        barrier.wait()
        try:
            repo.set_setting("k", {"v": n}, expected_updated_at=base["updated_at"])
            outcomes.append("saved")
        except SettingConflict:
            outcomes.append("conflict")

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(1, 7)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert outcomes.count("saved") == 1 and outcomes.count("conflict") == 5


# --- 2. Membership: role + plan + audit in one transaction, billing re-checked under the lock -------------------------
def make_user(engine, key="learner-sub", role="user"):
    with Session(engine) as session, session.begin():
        user = User(id=uuid.uuid4(), user_key=key, email=f"{key}@example.test", name=key, picture="", role=role,
                    created_at=datetime.now(UTC), last_login=None)
        session.add(user)
        return str(user.id)


def test_role_and_plan_commit_together_with_their_audit_row(engine):
    repo = PostgresProductRepository(engine=engine)
    account = make_user(engine)
    until = (datetime.now(UTC) + timedelta(days=30)).isoformat()
    result = apply_change(repo, account, {"role": "admin", "plan_id": "plus", "until": until}, actor_key="admin-sub",
                          protected_emails=set())
    assert result["account"]["role"] == "admin"
    assert result["account"]["plan_id"] == "plus" and result["account"]["provider"] == "manual"
    assert audit_rows(engine, "product.account.membership") == 1


def test_a_billing_subscription_that_appears_after_validation_is_not_overwritten(engine):
    repo = PostgresProductRepository(engine=engine)
    account = make_user(engine)

    class Racing:
        """Validation reads the account before billing writes its subscription; the write happens in between."""

        def account_membership(self, user_id):
            return repo.account_membership(user_id)

        def apply_membership(self, user_id, **kwargs):
            with Session(engine) as session, session.begin():
                session.add(PlanRecord(id="pro", name="Pro", description="", price_label="Pro", active=True))
                session.add(Subscription(id=uuid.uuid4(), user_id=uuid.UUID(user_id), plan_id="pro", status="active",
                                         provider="polar", external_customer_id="c", external_subscription_id="s",
                                         current_period_end=None, updated_at=datetime.now(UTC)))
            return repo.apply_membership(user_id, **kwargs)

    with pytest.raises(MembershipConflict):
        apply_change(Racing(), account, {"role": "admin", "plan_id": "plus"}, actor_key="admin-sub", protected_emails=set())
    after = repo.account_membership(account)
    assert after["role"] == "user", "the role did not change either: one transaction"
    assert after["provider"] == "polar" and after["plan_id"] == "pro", "billing's subscription is untouched"
    assert audit_rows(engine, "product.account.membership") == 0


def test_a_failing_audit_row_rolls_the_membership_change_back(engine, monkeypatch):
    repo = PostgresProductRepository(engine=engine)
    account = make_user(engine)

    def broken(session, audit, now):
        raise RuntimeError("audit store down")

    monkeypatch.setattr(platform, "_add_audit", broken)
    with pytest.raises(RuntimeError):
        apply_change(repo, account, {"role": "admin", "plan_id": "pro"}, actor_key="admin-sub", protected_emails=set())
    after = repo.account_membership(account)
    assert after["role"] == "user" and after["plan_id"] is None, "no unaudited role or plan change"
