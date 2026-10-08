"""The grammar store on PostgreSQL (runs when ORENA_TEST_POSTGRES_URL is set; the database is migrated to head, 0030).

What only PostgreSQL proves: the 0030 triggers under the repository (content immutable, versions undeletable, events
append-only), row locks under concurrent publishes, the partial unique index under concurrent imports of one package,
and learner progress through `PostgresLearningRepository` with R5 composite keys. Ids carry a per-test prefix because
the database is shared by the session.
"""
from __future__ import annotations

import threading
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from tests.grammar_store_support import body, manifest, zip_package
from writing_coach.core.request_context import LANGUAGE_CODE_CTX, USER_KEY_CTX
from writing_coach.grammar_store.package import read_package, validate_package
from writing_coach.persistence.auth_repository import PostgresAuthRepository
from writing_coach.persistence.grammar_store_repository import GrammarStoreRefusal, GrammarStoreRepository
from writing_coach.persistence.learning_repository import PostgresLearningRepository

ADMIN = "pg-admin@example.org"


@pytest.fixture()
def store(pg_engine):
    return GrammarStoreRepository(pg_engine)


@pytest.fixture()
def tag():
    return "t" + uuid.uuid4().hex[:10]


def _import(store, bodies, **kw):
    m = manifest(bodies, set_version=uuid.uuid4().hex, **kw)
    pkg = validate_package(read_package(zip_package(m, bodies)))
    assert pkg.ok, pkg.problems
    return store.commit_import(pkg, filename="p.zip", actor=ADMIN, echoed_hash=m["package_hash"],
                               rights={"basis": "orena_original", "attestation": "Synthetic test content."})


def _accepted(store, point_id, version=1):
    vid = next(v["id"] for v in store.admin_point(point_id)["versions"] if v["version"] == version)
    store.review_version(vid, decision="accept", actor=ADMIN)
    return vid


def test_the_triggers_hold_under_the_repository(store, pg_engine, tag):
    pid = f"en.{tag}.a"
    _import(store, [body(pid)])
    vid = _accepted(store, pid)
    store.publish([(pid, vid)], actor=ADMIN)
    with pg_engine.connect() as connection:
        for sql in ("UPDATE grammar_point_versions SET content = CAST('{}' AS json) WHERE id = :v",
                    "DELETE FROM grammar_point_versions WHERE id = :v",
                    "UPDATE grammar_review_events SET reason = 'x' WHERE version_id = :v"):
            tx = connection.begin()
            with pytest.raises(DBAPIError) as error:
                connection.execute(text(sql), {"v": vid})
            tx.rollback()
            assert getattr(error.value.orig, "sqlstate", "") == "23514"
    assert store.published("en", pid)["version"] == 1


def test_concurrent_publishes_of_one_point_serialize_and_leave_one_published_version(store, tag):
    pid = f"en.{tag}.a"
    _import(store, [body(pid)])
    v1 = _accepted(store, pid)
    _import(store, [body(pid, version=2, title="Two")])
    v2 = _accepted(store, pid, 2)
    errors: list[BaseException] = []
    barrier = threading.Barrier(2)

    def go(vid):
        try:
            barrier.wait(10)
            store.publish([(pid, vid)], actor=ADMIN)
        except BaseException as exc:  # noqa: BLE001 - reported below
            errors.append(exc)

    threads = [threading.Thread(target=go, args=(v,)) for v in (v1, v2)]
    [t.start() for t in threads]
    [t.join(30) for t in threads]
    assert not errors
    versions = store.admin_point(pid)["versions"]
    assert sum(v["is_published"] for v in versions) == 1
    assert all(v["review_status"] == "accepted" for v in versions)


def test_concurrent_commits_of_one_package_import_it_once(store, tag):
    bodies = [body(f"en.{tag}.a"), body(f"en.{tag}.b", sequence=2)]
    m = manifest(bodies, set_version=tag)
    data = zip_package(m, bodies)
    outcomes: list = []
    barrier = threading.Barrier(3)

    def go():
        pkg = validate_package(read_package(data))
        barrier.wait(10)
        outcomes.append(store.commit_import(pkg, filename="p.zip", actor=ADMIN, echoed_hash=m["package_hash"]))

    threads = [threading.Thread(target=go) for _ in range(3)]
    [t.start() for t in threads]
    [t.join(30) for t in threads]
    assert sorted(o.status for o in outcomes) == ["already_imported", "already_imported", "imported"]
    assert len({o.batch["id"] for o in outcomes}) == 1


def test_learner_progress_on_postgres_reads_r5_composites_through_the_map(store, pg_engine, tag):
    pid = f"en.{tag}.m"
    r5a, r5b = f"{tag}-be", f"{tag}-be-q"
    _import(store, [body(pid, aliases=[r5a, r5b])],
            r5_map=[{"r5_id": r5a, "point_id": pid, "disposition": "merged", "is_primary": True},
                    {"r5_id": r5b, "point_id": pid, "disposition": "merged", "is_primary": True}])
    store.publish([(pid, _accepted(store, pid))], actor=ADMIN)
    user = f"gram-{tag}"
    PostgresAuthRepository(pg_engine).upsert_user({"sub": user, "email": f"{user}@example.test", "name": user}, set())
    tokens = (USER_KEY_CTX.set(user), LANGUAGE_CODE_CTX.set("en"))
    from writing_coach import grammar_api

    saved = grammar_api._state
    try:
        repo = PostgresLearningRepository(pg_engine)
        repo.set_grammar_completed(f"en:grammar:v2:{r5a}", "2026-09-01T00:00:00+00:00")
        assert store.progress_map("en", [pid]) == {pid: sorted([r5a, r5b])}
        from writing_coach import grammar_api

        grammar_api.configure_grammar_api(store, repo, language=lambda: "en")
        assert pid not in {e["point_id"] for e in grammar_api.progress()["progress"]}  # merged: needs both
        repo.set_grammar_completed(f"en:grammar:v1:{r5b}", "2026-09-02T00:00:00+00:00")
        entry = next(e for e in grammar_api.progress()["progress"] if e["point_id"] == pid)
        assert entry["via"] == "r5" and entry["completed_at"].startswith("2026-09-01")
        saved = grammar_api.record_progress(pid, grammar_api.ProgressBody(answers=[0, 1, 0]))
        assert saved["last_quiz"]["correct"] == 3
    finally:
        grammar_api._state = saved
        LANGUAGE_CODE_CTX.reset(tokens[1])
        USER_KEY_CTX.reset(tokens[0])


def test_a_restricted_published_version_is_unpublished_in_the_same_transaction(store, tag):
    pid = f"en.{tag}.a"
    _import(store, [body(pid)])
    vid = _accepted(store, pid)
    store.publish([(pid, vid)], actor=ADMIN)
    store.set_version_rights(vid, status="restricted", actor=ADMIN, reason="licence withdrawn")
    assert store.published("en", pid) is None
    with pytest.raises(GrammarStoreRefusal):
        store.publish([(pid, vid)], actor=ADMIN)
