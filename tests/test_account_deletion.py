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


@pytest.fixture
def log(tmp_path):
    return tmp_path / "deletions.jsonl"


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


def test_the_dry_run_changes_nothing_and_apply_deletes_only_that_account(engine, log):
    gone_id, gone_key, gone_inc = _account(engine, f"gone-{uuid.uuid4()}@example.com")
    kept_id, _kept_key, _ = _account(engine, f"kept-{uuid.uuid4()}@example.com")
    summary = deletion.plan_summary(engine, user_key=gone_key)
    assert summary["delete"]["learner_memories.incarnation_id"] == 1
    assert summary["delete"]["audit_logs.user_id"] == 2 and summary["audit_kept_actor_rows"] == 2
    assert summary["fk_without_cascade"] == []  # learner data always cascades; money records are kept, not counted
    assert _one(engine, "SELECT count(*) FROM learner_memories WHERE user_id::text = :u", u=gone_id) == 1  # unchanged

    deletion.apply_plan(engine, log=log, user_key=gone_key)
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


def test_an_unknown_account_is_refused_and_commerce_rows_need_a_choice(engine, log, monkeypatch):
    with pytest.raises(deletion.DeletionRefused):
        deletion.apply_plan(engine, log=log, user_key="no-such-account")
    _buyer_id, key, _ = _account(engine, f"buyer-{uuid.uuid4()}@example.com")
    real = deletion.build_plan

    def with_commerce(conn, account):
        plan = real(conn, account)
        plan.targets.append(deletion.Target("billing_orders", "incarnation_id", "commerce", 2))
        return plan

    monkeypatch.setattr(deletion, "build_plan", with_commerce)
    with pytest.raises(deletion.DeletionRefused, match="commerce"):
        deletion.apply_plan(engine, log=log, user_key=key)
    with pytest.raises(ValueError):  # money records are append-only: there is no delete choice
        deletion.apply_plan(engine, log=log, user_key=key, commerce="delete")
    assert _one(engine, "SELECT name FROM users WHERE user_key = :k", k=key) == "A Learner"  # nothing changed
    deletion.apply_plan(engine, log=log, user_key=key, commerce="keep")  # money records kept; the learner's data goes
    monkeypatch.setattr(deletion, "build_plan", real)
    assert _one(engine, "SELECT name FROM users WHERE user_key = :k", k=key) == ""


def test_an_account_with_no_incarnation_gets_a_deleted_one_as_its_barrier(engine, log):
    gone_id, key, _ = _account(engine, f"never-{uuid.uuid4()}@example.com", with_incarnation=False)
    assert deletion.plan_summary(engine, user_key=key)["account"]["incarnations"] == 0
    deletion.apply_plan(engine, log=log, user_key=key)
    assert _one(engine, "SELECT count(*) FROM account_incarnations WHERE user_id::text = :u AND status = 'deleted'"
                " AND epoch = 1", u=gone_id) == 1


def test_an_email_shared_by_two_accounts_is_refused_and_names_both_keys(engine, log):
    shared = f"shared-{uuid.uuid4()}@example.com"
    _a, key_a, _ = _account(engine, shared)
    _b, key_b, _ = _account(engine, shared.upper())
    with pytest.raises(deletion.DeletionRefused, match="2 accounts") as refused:
        deletion.apply_plan(engine, log=log, email=shared)
    assert key_a in str(refused.value) and key_b in str(refused.value)
    assert _one(engine, "SELECT count(*) FROM users WHERE lower(email) = lower(:e)", e=shared) == 2  # nothing changed


# --- the continuous deletion log (D-054 a) and the replay after a restore (D-054 b) --------------------------------


def _intent(path, account=None, inc=None):
    from writing_coach.persistence import deletion_log

    return deletion_log.write_intent(path, account_id=account or str(uuid.uuid4()),
                                     incarnations=[{"id": inc or str(uuid.uuid4()), "epoch": 1, "created_at": T0}],
                                     at=T0)  # fmt: skip


def test_a_log_records_intent_then_done_and_only_confirmed_operations_replay(tmp_path):
    from writing_coach.persistence import deletion_log

    path = tmp_path / "log.jsonl"
    account, inc = str(uuid.uuid4()), str(uuid.uuid4())
    deletion_log.write_done(path, _intent(path, account, inc), deleted_at=T0)
    rolled_back = _intent(path)
    assert deletion_log.pending(path) == [rolled_back]
    with pytest.raises(deletion_log.DeletionLogInvalid, match="unsettled"):
        deletion_log.confirmed_journal(path)  # never replayed while an intent is unsettled
    deletion_log.write_abandoned(path, rolled_back)
    body = deletion_log.confirmed_journal(path)
    assert [(r["id"], r["user_id"], r["epoch"]) for r in body["records"]] == [(inc, account, 1)]
    assert [op["user_id"] for op in deletion_log.confirmed_operations(path)] == [account]
    assert "@" not in path.read_text(encoding="utf-8")  # ids and times only


def test_a_deletion_logged_twice_is_one_record_at_its_earliest_time(tmp_path):
    """Review P1-1: two confirmed operations naming the same incarnation must not block every future restore."""
    from writing_coach.persistence import deletion_log

    path = tmp_path / "log.jsonl"
    account, inc = str(uuid.uuid4()), str(uuid.uuid4())
    deletion_log.write_done(path, _intent(path, account, inc), deleted_at=T0)
    later = datetime(2026, 10, 20, tzinfo=UTC)
    deletion_log.write_done(path, _intent(path, account, inc), deleted_at=later)
    records = deletion_log.confirmed_journal(path)["records"]
    assert len(records) == 1 and datetime.fromisoformat(records[0]["deleted_at"]) == T0


def test_after_a_database_loss_an_unsettled_intent_is_applied_only_when_the_operator_accepts_it(tmp_path):
    """Review P1-2: a restore cannot show whether the commit happened; reconciling against it would abandon a committed
    deletion. So reconcile needs the live database, and a restore accepts unsettled intents explicitly."""
    from writing_coach.persistence import deletion_log

    path = tmp_path / "log.jsonl"
    account = str(uuid.uuid4())
    _intent(path, account)
    with pytest.raises(deletion_log.DeletionLogInvalid, match="live"):
        deletion_log.reconcile(object(), path, live=False)
    with pytest.raises(deletion_log.DeletionLogInvalid):
        deletion_log.confirmed_operations(path)
    assert [op["user_id"] for op in deletion_log.confirmed_operations(path, accept_unsettled=True)] == [account]


def test_a_torn_last_line_is_dropped_but_a_torn_middle_line_refuses(tmp_path):
    from writing_coach.persistence import deletion_log

    path = tmp_path / "log.jsonl"
    account = str(uuid.uuid4())
    deletion_log.write_done(path, _intent(path, account), deleted_at=T0)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write('{"kind": "orena.deletion_log", "version": 1, "event": "int')  # a crash mid-write
    assert [op["user_id"] for op in deletion_log.confirmed_operations(path)] == [account]
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("\n" + path.read_text(encoding="utf-8").splitlines()[0] + "\n")
    with pytest.raises(deletion_log.DeletionLogInvalid):
        deletion_log.read_log(path)


@pytest.mark.parametrize("line", ["not json", '{"kind": "other"}',
                                  '{"kind": "orena.deletion_log", "version": 1, "event": "done", "op": "x"}'])
def test_a_log_that_cannot_be_trusted_is_refused_whole(tmp_path, line):
    from writing_coach.persistence import deletion_log

    path = tmp_path / "log.jsonl"
    path.write_text(line + "\n" + line + "\n", encoding="utf-8")  # not only a torn last line
    with pytest.raises(deletion_log.DeletionLogInvalid):
        deletion_log.read_log(path)


def test_apply_without_a_log_is_refused():
    with pytest.raises(ValueError, match="deletion log is required"):
        deletion.apply_plan(object(), log=None, user_key="x")


def _restore_note(engine, account_id, incarnation):
    from sqlalchemy import text

    from writing_coach.agent.memory_keys import MemoryKeys
    from writing_coach.agent.memory_store import MemoryScope
    from writing_coach.persistence.memory_repository import PostgresMemoryRepository

    with engine.begin() as conn:
        conn.execute(text("UPDATE account_incarnations SET status = 'active', deleted_at = NULL"
                          " WHERE id = CAST(:i AS uuid)"), {"i": incarnation})  # fmt: skip
    PostgresMemoryRepository(engine, MemoryKeys.parse("v1:" + "k" * 40)).add_explicit(
        MemoryScope(account_id, incarnation), language="zh", kind="goal", text="Phỏng vấn xin việc", slot=None,
        source="learner_asked", now=T0)  # fmt: skip


def test_a_deletion_is_logged_and_a_restore_replays_it_in_full(engine, log):
    from writing_coach.persistence import deletion_log
    from writing_coach.persistence.deletion_journal import reapply_deletions

    gone_id, key, inc = _account(engine, f"restored-{uuid.uuid4()}@example.com")
    deletion.apply_plan(engine, log=log, user_key=key)
    deletion.apply_plan(engine, log=log, user_key=key)  # applied twice: still one record per incarnation
    assert deletion_log.pending(log) == []
    _restore_note(engine, gone_id, inc)  # a restore from before the deletion
    ops = deletion_log.confirmed_operations(log)
    assert deletion.owner_rows_left(engine, ops)  # --check sees it
    summary = reapply_deletions(engine, deletion_log.confirmed_journal(log))
    owners = deletion.reapply_owner_deletions(engine, ops)
    assert summary["reapplied"] == 1 and owners["replayed"] == 1 and owners["returned"] == []
    assert _one(engine, "SELECT status FROM account_incarnations WHERE id::text = :i", i=inc) == "deleted"
    assert _one(engine, "SELECT count(*) FROM learner_memories WHERE user_id::text = :u", u=gone_id) == 0
    assert deletion.owner_rows_left(engine, ops) == []


def test_a_learner_who_came_back_keeps_what_they_wrote_after_the_deletion(engine, log):
    """Review P1-3 (D-055): a replay deletes what the deletion removed, never the returning learner's new life."""
    from sqlalchemy import text

    from writing_coach.persistence import deletion_log

    gone_id, key, inc = _account(engine, f"returned-{uuid.uuid4()}@example.com")
    deletion.apply_plan(engine, log=log, user_key=key, now=T0)
    _restore_note(engine, gone_id, inc)  # restored rows from before the deletion
    with engine.begin() as conn:  # the learner signed in again afterwards and wrote something new
        conn.execute(text("UPDATE users SET last_login = :later, name = 'Back Again' WHERE id = CAST(:u AS uuid)"),
                     {"u": gone_id, "later": datetime(2026, 10, 25, tzinfo=UTC)})  # fmt: skip
        conn.execute(text("INSERT INTO audit_logs (id, user_id, action, entity_type, entity_id, payload, created_at)"
                          " VALUES (:a, CAST(:u AS uuid), 'learner.feedback', 'feedback', '', '{}', :later)"),
                     {"a": uuid.uuid4(), "u": gone_id, "later": datetime(2026, 10, 25, tzinfo=UTC)})  # fmt: skip
    owners = deletion.reapply_owner_deletions(engine, deletion_log.confirmed_operations(log))
    assert owners["returned"] == [gone_id]
    assert _one(engine, "SELECT count(*) FROM learner_memories WHERE user_id::text = :u", u=gone_id) == 0  # logged inc
    assert _one(engine, "SELECT count(*) FROM audit_logs WHERE user_id::text = :u AND action = 'learner.feedback'",
                u=gone_id) == 1  # the new feedback stays  # fmt: skip
    assert _one(engine, "SELECT name FROM users WHERE id::text = :u", u=gone_id) == "Back Again"


def test_a_deletion_that_does_not_commit_is_reconciled_as_abandoned(engine, log, monkeypatch):
    from writing_coach.persistence import deletion_log

    _id, key, inc = _account(engine, f"rollback-{uuid.uuid4()}@example.com")
    real = deletion_log.write_intent

    def intent_then_fail(*args, **kwargs):
        real(*args, **kwargs)
        raise OSError("disk full after the intent")  # the transaction rolls back

    monkeypatch.setattr(deletion_log, "write_intent", intent_then_fail)
    with pytest.raises(OSError):
        deletion.apply_plan(engine, log=log, user_key=key)
    monkeypatch.setattr(deletion_log, "write_intent", real)
    assert _one(engine, "SELECT status FROM account_incarnations WHERE id::text = :i", i=inc) == "active"
    assert deletion_log.reconcile(engine, log, live=True) == {"done": 0, "abandoned": 1}
    assert deletion_log.confirmed_operations(log) == []  # an account that was never deleted is never replayed


def test_a_committed_deletion_whose_done_was_lost_is_confirmed_by_reconcile(engine, log, monkeypatch):
    from writing_coach.persistence import deletion_log

    gone_id, key, _inc = _account(engine, f"nodone-{uuid.uuid4()}@example.com")

    def lost(*args, **kwargs):
        raise OSError("crash after the commit")

    monkeypatch.setattr(deletion_log, "write_done", lost)
    with pytest.raises(deletion.CommittedUnconfirmed):
        deletion.apply_plan(engine, log=log, user_key=key)
    monkeypatch.undo()
    assert _one(engine, "SELECT email FROM users WHERE id::text = :u", u=gone_id) == deletion.anonymous_email(gone_id)
    assert deletion_log.reconcile(engine, log, live=True) == {"done": 1, "abandoned": 0}
    assert [op["user_id"] for op in deletion_log.confirmed_operations(log)] == [gone_id]
