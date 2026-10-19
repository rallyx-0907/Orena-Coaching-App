"""Manual account deletion (PRE-502 R4): a dry-run plan from the live schema, and its application in one transaction.

The plan's classification is checked here against the ORM. The deletion itself runs on PostgreSQL only (the
`information_schema` scan, `ANY`, row locks), when ORENA_TEST_POSTGRES_URL names a throwaway database."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest

from writing_coach.persistence import account_deletion as deletion
from writing_coach.persistence import deletion_enumeration as enumeration
from writing_coach.persistence.models import Base

URL = os.getenv("ORENA_TEST_POSTGRES_URL", "")
T0 = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)


def test_every_orm_table_owned_by_an_account_is_deleted_kept_or_decided():
    """Each ORM table with an account column falls in one group the tool handles; nothing is silently skipped."""
    listed = (set(enumeration.ACCOUNT_KEYED_TABLES) | set(enumeration.ACCOUNT_ID_KEYED_TABLES)
              | set(enumeration.PLAN_AND_USAGE_TABLES) | set(enumeration.AUDIT_TABLES) | {"users"})  # fmt: skip
    for table in Base.metadata.tables.values():
        if not {c.name for c in table.c} & set(deletion.ACCOUNT_COLUMNS):
            continue
        assert table.name in listed or table.name.startswith(enumeration.COMMERCE_TABLE_PREFIXES), table.name


def test_the_groups_and_the_placeholder():
    assert deletion._group("audit_logs") == "audit"
    assert deletion._group("billing_orders") == "commerce" and deletion._group("credit_ledger") == "commerce"
    assert deletion._group("saved_words") == "delete"
    email = deletion.anonymous_email("0b0e-id")
    assert email.endswith("@deleted.invalid") and "0b0e-id" in email
    assert set(enumeration.USER_COLUMNS_TO_ANONYMISE) == {"email", "name", "picture"}
    with pytest.raises(ValueError):
        deletion.find_account(None, email="a@b.c", user_key="x")


@pytest.fixture(scope="module")
def engine():
    if not URL:
        pytest.skip("ORENA_TEST_POSTGRES_URL is not set; the deletion runs on PostgreSQL only")
    sqlalchemy = pytest.importorskip("sqlalchemy")
    from alembic import command

    from writing_coach.persistence.runtime import _runtime_alembic_config

    cfg = _runtime_alembic_config()
    cfg.set_main_option("sqlalchemy.url", URL.replace("%", "%%"))
    command.upgrade(cfg, "head")
    engine = sqlalchemy.create_engine(URL, future=True)
    yield engine
    engine.dispose()


def _account(engine, email, *, with_incarnation=True):
    from sqlalchemy import text

    from writing_coach.agent.memory_keys import MemoryKeys
    from writing_coach.agent.memory_store import MemoryScope
    from writing_coach.persistence.memory_repository import PostgresMemoryRepository

    user_id, incarnation = uuid.uuid4(), uuid.uuid4()
    key = f"sub-{user_id}"
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO users (id, user_key, email, name, picture, role, created_at)"
                          " VALUES (:id, :key, :email, 'A Learner', 'https://pic', 'user', now())"),
                     {"id": user_id, "key": key, "email": email})  # fmt: skip
        if with_incarnation:
            conn.execute(text("INSERT INTO account_incarnations (id, user_id, epoch, status, created_at)"
                              " VALUES (:id, :u, 1, 'active', now())"), {"id": incarnation, "u": user_id})
        conn.execute(text("INSERT INTO audit_logs (id, user_id, action, entity_type, entity_id, payload, created_at)"
                          " VALUES (:a, :u, 'learner.feedback', 'feedback', '', '{}', now()),"
                          " (:b, :u, 'agent.turn', 'agent', '', '{}', now()),"
                          " (:c, :u, 'admin.memory_erase_requested', 'account', '', '{}', now()),"
                          " (:d, :u, 'product.plans.update', 'plan', '', '{}', now())"),
                     {"a": uuid.uuid4(), "b": uuid.uuid4(), "c": uuid.uuid4(), "d": uuid.uuid4(), "u": user_id})  # fmt: skip
    if not with_incarnation:
        return str(user_id), key, None
    store = PostgresMemoryRepository(engine, MemoryKeys.parse("v1:" + "k" * 40))
    store.add_explicit(MemoryScope(str(user_id), str(incarnation)), language="zh", kind="goal",
                       text="Phỏng vấn xin việc", slot=None, source="learner_asked", now=T0)  # fmt: skip
    return str(user_id), key, str(incarnation)


def _one(engine, sql, **params):
    from sqlalchemy import text

    with engine.connect() as conn:
        return conn.execute(text(sql), params).scalar()


def test_the_dry_run_changes_nothing_and_apply_deletes_only_that_account(engine):
    gone_id, gone_key, gone_inc = _account(engine, f"gone-{uuid.uuid4()}@example.com")
    kept_id, _kept_key, _ = _account(engine, f"kept-{uuid.uuid4()}@example.com")
    summary = deletion.plan_summary(engine, user_key=gone_key)
    assert summary["delete"]["learner_memories.incarnation_id"] == 1
    assert summary["delete"]["audit_logs.user_id"] == 2 and summary["audit_kept_actor_rows"] == 2
    assert summary["fk_without_cascade"] == []  # learner data always cascades; money records are kept, not counted
    assert _one(engine, "SELECT count(*) FROM learner_memories WHERE user_id::text = :u", u=gone_id) == 1  # unchanged

    deletion.apply_plan(engine, user_key=gone_key)
    assert _one(engine, "SELECT count(*) FROM learner_memories WHERE user_id::text = :u", u=gone_id) == 0
    assert _one(engine, "SELECT count(*) FROM audit_logs WHERE user_id::text = :u", u=gone_id) == 2  # actor rows kept
    assert _one(engine, "SELECT status FROM account_incarnations WHERE id::text = :i", i=gone_inc) == "deleted"
    assert _one(engine, "SELECT email FROM users WHERE id::text = :u", u=gone_id) == deletion.anonymous_email(gone_id)
    assert _one(engine, "SELECT name || picture FROM users WHERE id::text = :u", u=gone_id) == ""
    assert _one(engine, "SELECT user_key FROM users WHERE id::text = :u", u=gone_id) == gone_key  # the barrier stays
    # the other account is untouched
    assert _one(engine, "SELECT count(*) FROM learner_memories WHERE user_id::text = :u", u=kept_id) == 1
    assert _one(engine, "SELECT count(*) FROM audit_logs WHERE user_id::text = :u", u=kept_id) == 4
    assert _one(engine, "SELECT role FROM users WHERE id::text = :u", u=gone_id) == "user"
    revoked = _one(engine, "SELECT value::text FROM platform_settings WHERE key = :k",
                   k=deletion.session_revoked_key(gone_key))  # fmt: skip
    assert revoked and "before_ms" in revoked  # every session of the account ends
    assert _one(engine, "SELECT name FROM users WHERE id::text = :u", u=kept_id) == "A Learner"


def test_an_unknown_account_is_refused_and_commerce_rows_need_a_choice(engine, monkeypatch):
    with pytest.raises(deletion.DeletionRefused):
        deletion.apply_plan(engine, user_key="no-such-account")
    _buyer_id, key, _ = _account(engine, f"buyer-{uuid.uuid4()}@example.com")
    real = deletion.build_plan

    def with_commerce(conn, account):
        plan = real(conn, account)
        plan.targets.append(deletion.Target("billing_orders", "incarnation_id", "commerce", 2))
        return plan

    monkeypatch.setattr(deletion, "build_plan", with_commerce)
    with pytest.raises(deletion.DeletionRefused, match="commerce"):
        deletion.apply_plan(engine, user_key=key)
    with pytest.raises(ValueError):  # money records are append-only: there is no delete choice
        deletion.apply_plan(engine, user_key=key, commerce="delete")
    assert _one(engine, "SELECT name FROM users WHERE user_key = :k", k=key) == "A Learner"  # nothing changed
    deletion.apply_plan(engine, user_key=key, commerce="keep")  # money records kept; the learner's data goes
    monkeypatch.setattr(deletion, "build_plan", real)
    assert _one(engine, "SELECT name FROM users WHERE user_key = :k", k=key) == ""


def test_an_account_with_no_incarnation_gets_a_deleted_one_as_its_barrier(engine):
    gone_id, key, _ = _account(engine, f"never-{uuid.uuid4()}@example.com", with_incarnation=False)
    assert deletion.plan_summary(engine, user_key=key)["account"]["incarnations"] == 0
    deletion.apply_plan(engine, user_key=key)
    assert _one(engine, "SELECT count(*) FROM account_incarnations WHERE user_id::text = :u AND status = 'deleted'"
                " AND epoch = 1", u=gone_id) == 1


def test_an_email_shared_by_two_accounts_is_refused_and_names_both_keys(engine):
    shared = f"shared-{uuid.uuid4()}@example.com"
    _a, key_a, _ = _account(engine, shared)
    _b, key_b, _ = _account(engine, shared.upper())
    with pytest.raises(deletion.DeletionRefused, match="2 accounts") as refused:
        deletion.apply_plan(engine, email=shared)
    assert key_a in str(refused.value) and key_b in str(refused.value)
    assert _one(engine, "SELECT count(*) FROM users WHERE lower(email) = lower(:e)", e=shared) == 2  # nothing changed
