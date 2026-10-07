"""Rehearsal of migration 20261007_0029 and the practice-session lock on a throwaway PostgreSQL (D-142).

`docs/project/proposals/PRACTICE_SESSION_IDENTITY.md`. Run by hand against a database given by URL; not part of CI; it
refuses anything that is not clearly throwaway and empty (the same guard as `rehearse_learner_records_schema.py`).

    export REHEARSAL_PW="$(python -c 'import secrets;print(secrets.token_hex(12))')"
    docker run --rm -d --name orena-pg-rehearsal-$RANDOM -e POSTGRES_PASSWORD="$REHEARSAL_PW" \
        -e POSTGRES_DB=orena_rehearsal -p 127.0.0.1:55436:5432 postgres:16
    # in the application image, repository mounted read-only (REHEARSAL_URL carries the password; never echoed):
    python scripts/rehearse_practice_session_identity.py "$REHEARSAL_URL"

Steps (each a PASS/FAIL row; non-zero exit on any FAIL):
1. chain to 20261004_0025, a legacy attempt row, up to 20261007_0029 (nullable column, index, the row is untouched, no
   backfill), down to 0025 (column and index gone, the attempt stays), up again.
2. the ACTUAL pg_advisory_xact_lock path: a held lock makes a writer WAIT (pg_locks shows an ungranted advisory lock),
   and it completes once released.
3. N concurrent first attempts of one account + language through the real repository: exactly one session id.
4. the same through the real routes (POST /api/speech/attempts, GET ...?session=current) with the flag on.
5. a later attempt within 30 minutes reuses the id; one after more than 30 minutes mints a new one; another account
   and another language never share one.
"""
from __future__ import annotations

import os
import sys
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

import sqlalchemy as sa  # noqa: E402
from alembic import command  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from rehearse_learner_records_schema import refuse_unless_empty, refuse_unless_throwaway  # noqa: E402
from writing_coach.persistence.ids import stable_uuid  # noqa: E402
from writing_coach.persistence.models import User  # noqa: E402
from writing_coach.persistence.runtime import _runtime_alembic_config  # noqa: E402

REV = "20261007_0029"
BEFORE = "20261004_0025"
INDEX = "ix_speaking_attempts_session"
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)


def revision(engine) -> str | None:
    with engine.connect() as c:
        return c.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()


def shape(engine) -> tuple[set[str], set[str]]:
    insp = sa.inspect(engine)
    return ({c["name"] for c in insp.get_columns("speaking_attempts")},
            {i["name"] for i in insp.get_indexes("speaking_attempts")})


def add_user(engine, key: str) -> None:
    with Session(engine) as db, db.begin():
        db.add(User(id=stable_uuid("user", key),
                    user_key=key, email="", name="", picture="", role="user",
                    created_at=datetime.now(UTC), last_login=None))


def main(url: str) -> int:
    refuse_unless_throwaway(url)
    engine = create_engine(url, future=True, pool_size=24, max_overflow=24)
    refuse_unless_empty(engine)
    with engine.connect() as c:
        print("server:", c.execute(sa.text("SHOW server_version")).scalar())
    cfg = _runtime_alembic_config()
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))

    # 1. migrations -------------------------------------------------------------------------------------------------
    command.upgrade(cfg, BEFORE)
    check("chain applied to 0025", revision(engine) == BEFORE, str(revision(engine)))
    columns, indexes = shape(engine)
    check("0025 has neither the column nor the index", "practice_session_id" not in columns and INDEX not in indexes)
    legacy_user = "legacy-account"
    add_user(engine, legacy_user)
    legacy_uid = stable_uuid("user", legacy_user)
    with engine.begin() as c:
        c.execute(sa.text(
            "INSERT INTO speaking_attempts (id, user_id, language_code, take_id, asset_id, segment_id, reference_text,"
            " transcript_text, dimensions, provenance, evidence, created_at) VALUES (:id, :u, 'en', 'legacy-take', '', '',"
            " '', 'old', '{}'::json, '{}'::json, '{}'::json, now())"), {"id": uuid.uuid4(), "u": legacy_uid})
    command.upgrade(cfg, REV)
    columns, indexes = shape(engine)
    col = {c["name"]: c for c in sa.inspect(engine).get_columns("speaking_attempts")}["practice_session_id"]
    check("up to 0029: nullable uuid column, no default", revision(engine) == REV and col["nullable"] and col["default"] is None,
          f"type={col['type']}")
    check("up to 0029: the index exists", INDEX in indexes)
    with engine.connect() as c:
        legacy = c.execute(sa.text("SELECT take_id, practice_session_id FROM speaking_attempts")).all()
    check("legacy row untouched, no backfill", legacy == [("legacy-take", None)], str(legacy))
    command.downgrade(cfg, BEFORE)
    columns, indexes = shape(engine)
    with engine.connect() as c:
        kept = c.execute(sa.text("SELECT count(*) FROM speaking_attempts")).scalar()
    check("down to 0025: column and index gone, the attempt stays",
          revision(engine) == BEFORE and "practice_session_id" not in columns and INDEX not in indexes and kept == 1,
          f"attempts={kept}")
    command.upgrade(cfg, REV)
    columns, indexes = shape(engine)
    check("up again to 0029", revision(engine) == REV and "practice_session_id" in columns and INDEX in indexes)

    # The repository over the real PostgreSQL ------------------------------------------------------------------------
    from writing_coach import speech_api
    from writing_coach.persistence.specialized_repository import PRACTICE_SESSION_IDLE_MINUTES, PostgresSpecializedLearningRepository

    def repo(key: str, lang: str = "en"):
        return PostgresSpecializedLearningRepository(engine, user_key_provider=lambda: key, language_provider=lambda: lang)

    def values(take: str, at: datetime, lang: str = "en") -> dict:
        return {"created_at": at.isoformat(), "language": lang, "take_id": take, "asset_id": "free", "segment_id": "s",
                "reference_text": "", "transcript_text": "hello", "dimensions": {"fluency": 80}, "provenance": {}, "evidence": {}}

    def write(key: str, take: str, at: datetime, lang: str = "en") -> str:
        return repo(key, lang).create_speaking_attempt_record(values(take, at, lang), assign_session=True)["practice_session_id"]

    now = datetime.now(UTC)

    # 2. the actual advisory lock -----------------------------------------------------------------------------------
    lock_user = "lock-account"
    add_user(engine, lock_user)
    lock_uid = stable_uuid("user", lock_user)
    holder = engine.connect()
    holder_tx = holder.begin()
    holder.execute(sa.text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": f"practice-session:{lock_uid}:en"})
    finished = threading.Event()
    out: dict = {}

    def blocked_writer() -> None:
        out["id"] = write(lock_user, "locked-1", now)
        finished.set()

    thread = threading.Thread(target=blocked_writer)
    thread.start()
    time.sleep(2.0)
    with engine.connect() as c:
        waiting = c.execute(sa.text("SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND NOT granted")).scalar()
    check("a writer WAITS while the advisory lock is held", not finished.is_set() and waiting >= 1, f"ungranted advisory locks={waiting}")
    holder_tx.rollback()
    holder.close()
    thread.join(10)
    check("the writer completes once it is released", finished.is_set() and bool(out.get("id")), str(out.get("id")))

    # 3. concurrent first attempts, real repository ------------------------------------------------------------------
    racers = 12
    race_user = "race-account"
    add_user(engine, race_user)
    barrier = threading.Barrier(racers)
    ids: list[str] = []
    errors: list[BaseException] = []

    def racer(n: int) -> None:
        try:
            barrier.wait(10)
            ids.append(write(race_user, f"race-{n}", datetime.now(UTC)))
        except BaseException as exc:  # noqa: BLE001 - reported below
            errors.append(exc)

    threads = [threading.Thread(target=racer, args=(n,)) for n in range(racers)]
    [t.start() for t in threads]
    [t.join(30) for t in threads]
    with engine.connect() as c:
        stored = c.execute(sa.text(
            "SELECT count(*), count(DISTINCT practice_session_id) FROM speaking_attempts a JOIN users u ON u.id = a.user_id"
            " WHERE u.user_key = :k"), {"k": race_user}).one()
    check(f"{racers} concurrent first attempts mint exactly one session id (repository)",
          not errors and len(ids) == racers and len(set(ids)) == 1 and stored == (racers, 1),
          f"returned ids={len(set(ids))} stored rows={stored[0]} distinct ids={stored[1]} errors={errors[:1]}")

    # 5. window, accounts, languages -------------------------------------------------------------------------------
    first = write(race_user, "later-10min", now + timedelta(minutes=10))
    check("a later attempt within 30 minutes reuses the id", first == ids[0])
    after_idle = write(race_user, "after-idle", now + timedelta(minutes=10 + PRACTICE_SESSION_IDLE_MINUTES + 1))
    check("an attempt after more than 30 idle minutes starts a new session", after_idle != ids[0])
    other = "other-account"
    add_user(engine, other)
    check("another account never shares the session", write(other, "o1", now) not in {ids[0], after_idle})
    check("another language never shares the session", write(race_user, "zh1", now + timedelta(minutes=11), "zh") not in {ids[0], after_idle})

    # 4. the real routes ---------------------------------------------------------------------------------------------
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    route_user = "route-account"
    add_user(engine, route_user)
    os.environ[speech_api.PRACTICE_SESSION_FLAG] = "on"
    speech_api.configure_speaking_attempt_repository(repo(route_user))
    app = FastAPI()
    app.include_router(speech_api.router)
    client = TestClient(app)
    body = lambda take: {"language": "en", "take_id": take, "asset_id": "free", "segment_id": "s", "reference_text": "",  # noqa: E731
                         "transcript_text": "hello", "evaluation": {"dimensions": {"fluency": 80}, "provenance": {}, "evidence": {}}}
    barrier2 = threading.Barrier(racers)
    codes: list[int] = []

    def post(n: int) -> None:
        barrier2.wait(10)
        codes.append(client.post("/api/speech/attempts", json=body(f"route-{n}")).status_code)

    threads = [threading.Thread(target=post, args=(n,)) for n in range(racers)]
    [t.start() for t in threads]
    [t.join(60) for t in threads]
    current = client.get("/api/speech/attempts?session=current&limit=100").json()
    check(f"{racers} concurrent POSTs through the route: one session holding all of them",
          codes == [200] * racers and current["session"] and current["session"]["count"] == racers and len(current["items"]) == racers,
          f"statuses ok={codes.count(200)} count={current['session'] and current['session']['count']} id={current['session'] and current['session']['id']}")
    os.environ.pop(speech_api.PRACTICE_SESSION_FLAG)
    speech_api.configure_speaking_attempt_repository(None)
    check("flag off: the read route answers the explicit 404 practice_session_disabled",
          (lambda r: r.status_code == 404 and r.json()["detail"].get("category") == "practice_session_disabled")(
              (lambda: (speech_api.configure_speaking_attempt_repository(repo(route_user)), client.get("/api/speech/attempts?session=current"))[1])()))
    speech_api.configure_speaking_attempt_repository(None)

    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)} PASS, {len(failed)} FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
