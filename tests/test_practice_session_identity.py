"""D-142: the persisted practice session identity (PRACTICE_SESSION_IDENTITY.md).

The repository is the real PostgreSQL one run on a throwaway SQLite engine (as `specialized_repository_selftest`
does); the advisory lock is PostgreSQL-only and a process lock stands in on SQLite. Time is the server's and is
frozen by patching `speech_api._server_now`. No provider is called and no real database is touched.
"""
from __future__ import annotations

import importlib.util
import threading
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from writing_coach import speech_api
from writing_coach.core.request_context import LANGUAGE_CODE_CTX, USER_KEY_CTX
from writing_coach.persistence.ids import stable_uuid
from writing_coach.persistence.models import Base, User
from writing_coach.persistence.specialized_repository import (
    PRACTICE_SESSION_IDLE_MINUTES,
    PostgresSpecializedLearningRepository,
)

T0 = datetime(2026, 10, 7, 9, 0, tzinfo=UTC)


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kw) -> None:
        self.now += timedelta(**kw)


@pytest.fixture(autouse=True)
def _leave_no_process_state_behind():
    """Everything these tests set on the process is put back: the request ContextVars (token + reset, so it does not
    rest on tests/conftest.py alone) and the speaking repository `app.py` configures at import, which a plain
    `configure_...(None)` would otherwise leave cleared for every later module."""
    tokens = [(var, var.set(var.get())) for var in (USER_KEY_CTX, LANGUAGE_CODE_CTX)]
    previous = speech_api._speaking_attempt_repository
    try:
        yield
    finally:
        speech_api.configure_speaking_attempt_repository(previous)
        for var, token in reversed(tokens):
            var.reset(token)


@pytest.fixture
def engine(tmp_path):
    eng = create_engine(f"sqlite+pysqlite:///{tmp_path / 'sessions.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


def _user(engine, key: str) -> None:
    with Session(engine) as db, db.begin():
        db.add(User(id=stable_uuid("user", key), user_key=key, email="", name="", picture="", role="user",
                    created_at=T0, last_login=None))


def _repo(engine, key: str = "ann", lang: str = "en"):
    return PostgresSpecializedLearningRepository(engine, user_key_provider=lambda: key, language_provider=lambda: lang)


@pytest.fixture
def client(engine, monkeypatch):
    """The real route over the real repository for the account `ann`, English, with a frozen server clock."""
    _user(engine, "ann")
    clock = Clock(T0)
    monkeypatch.setattr(speech_api, "_server_now", clock)
    monkeypatch.setenv(speech_api.PRACTICE_SESSION_FLAG, "on")
    USER_KEY_CTX.set("ann")
    LANGUAGE_CODE_CTX.set("en")
    speech_api.configure_speaking_attempt_repository(_repo(engine))
    app = FastAPI()
    app.include_router(speech_api.router)
    test_client = TestClient(app)
    test_client.clock = clock  # type: ignore[attr-defined]
    yield test_client
    speech_api.configure_speaking_attempt_repository(None)


def _body(take: str, text: str = "hello there") -> dict:
    return {
        "language": "en", "take_id": take, "asset_id": "free", "segment_id": "invite-1", "reference_text": "",
        "transcript_text": text,
        "evaluation": {"dimensions": {"fluency": 80}, "provenance": {}, "evidence": {}},
    }


def _post(client, take: str):
    response = client.post("/api/speech/attempts", json=_body(take))
    assert response.status_code == 200, response.text
    return response.json()["item"]


def _stored_ids(engine) -> dict[str, str | None]:
    with engine.connect() as c:
        rows = c.execute(sa.text("SELECT take_id, practice_session_id FROM speaking_attempts")).all()
    return {take: sid for take, sid in rows}


# --- flag off: byte-identical to today ---------------------------------------------------------------------------


def test_flag_off_writes_no_identity_and_the_read_route_is_404(client, engine, monkeypatch):
    monkeypatch.delenv(speech_api.PRACTICE_SESSION_FLAG)
    item = _post(client, "t1")
    assert "practice_session_id" not in item
    assert _stored_ids(engine) == {"t1": None}
    response = client.get("/api/speech/attempts", params={"session": "current"})
    assert response.status_code == 404
    assert "practice_session_disabled" in response.text
    assert [x["take_id"] for x in client.get("/api/speech/attempts").json()["items"]] == ["t1"]


def test_flag_off_calls_the_repository_exactly_as_before(monkeypatch):
    calls = []

    class Fake:
        def create_speaking_attempt_record(self, values, **kw):
            calls.append(kw)
            return {"id": "x"}

        def speaking_progress(self):
            return {}

    monkeypatch.delenv(speech_api.PRACTICE_SESSION_FLAG, raising=False)
    LANGUAGE_CODE_CTX.set("en")
    speech_api.configure_speaking_attempt_repository(Fake())
    try:
        app = FastAPI()
        app.include_router(speech_api.router)
        assert TestClient(app).post("/api/speech/attempts", json=_body("t")).status_code == 200
    finally:
        speech_api.configure_speaking_attempt_repository(None)
    assert calls == [{}]


# --- the 30-minute window, judged by the server -------------------------------------------------------------------


def test_takes_inside_the_window_share_one_session_and_the_window_slides(client, engine):
    first = _post(client, "t1")
    client.clock.advance(minutes=PRACTICE_SESSION_IDLE_MINUTES)  # exactly 30 minutes: still inside
    second = _post(client, "t2")
    client.clock.advance(minutes=PRACTICE_SESSION_IDLE_MINUTES)  # 30 after the SECOND: activity refreshed the window
    third = _post(client, "t3")
    assert first["practice_session_id"] == second["practice_session_id"] == third["practice_session_id"]
    assert uuid.UUID(first["practice_session_id"])


def test_a_take_after_the_window_starts_a_new_session(client):
    first = _post(client, "t1")
    client.clock.advance(minutes=PRACTICE_SESSION_IDLE_MINUTES, seconds=1)
    second = _post(client, "t2")
    assert first["practice_session_id"] != second["practice_session_id"]


def test_two_devices_of_one_account_share_the_session(client, engine):
    first = _post(client, "phone-1")
    client.clock.advance(minutes=10)
    other_device = TestClient(client.app)  # a second client, no shared state but the account
    response = other_device.post("/api/speech/attempts", json=_body("laptop-1"))
    assert response.json()["item"]["practice_session_id"] == first["practice_session_id"]


def test_a_replay_of_the_same_take_keeps_its_original_session(client, engine):
    first = _post(client, "t1")
    client.clock.advance(minutes=45)  # the window has lapsed; a replay must not re-derive anything
    replay = _post(client, "t1")
    assert replay["practice_session_id"] == first["practice_session_id"]
    assert len(_stored_ids(engine)) == 1


def test_accounts_and_languages_never_share_a_session(client, engine):
    mine = _post(client, "t1")
    _user(engine, "bob")
    bob = _repo(engine, "bob")
    values = speech_api._normalize_speaking_attempt(speech_api.SpeakingAttemptIn(**_body("t1")))
    other = bob.create_speaking_attempt_record(values, assign_session=True)
    assert other["practice_session_id"] != mine["practice_session_id"]
    zh = _repo(engine, "ann", "zh").create_speaking_attempt_record(values | {"language": "zh"}, assign_session=True)
    assert zh["practice_session_id"] not in {mine["practice_session_id"], other["practice_session_id"]}


def test_concurrent_first_takes_mint_exactly_one_session(engine):
    _user(engine, "ann")
    values = speech_api._normalize_speaking_attempt(speech_api.SpeakingAttemptIn(**_body("seed")))
    LANGUAGE_CODE_CTX.set("en")
    results: list[str] = []
    errors: list[BaseException] = []

    def write(n: int) -> None:
        try:
            saved = _repo(engine).create_speaking_attempt_record(
                values | {"take_id": f"race-{n}", "created_at": T0.isoformat()}, assign_session=True)
            results.append(saved["practice_session_id"])
        except BaseException as exc:  # noqa: BLE001 - surfaced below
            errors.append(exc)

    threads = [threading.Thread(target=write, args=(n,)) for n in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors and len(results) == 6 and len(set(results)) == 1


def test_legacy_rows_stay_null_and_are_never_the_current_session(client, engine):
    legacy = _repo(engine).create_speaking_attempt_record(
        speech_api._normalize_speaking_attempt(speech_api.SpeakingAttemptIn(**_body("old"))) | {"created_at": T0.isoformat()})
    assert "practice_session_id" not in legacy and _stored_ids(engine) == {"old": None}
    live = client.get("/api/speech/attempts", params={"session": "current"}).json()
    assert live["items"] == [] and live["session"] is None
    client.clock.advance(minutes=1)
    fresh = _post(client, "new")
    current = client.get("/api/speech/attempts", params={"session": "current"}).json()
    assert [x["take_id"] for x in current["items"]] == ["new"], "a legacy row is never invented into the session"
    assert current["session"]["id"] == fresh["practice_session_id"]
    assert {x["take_id"] for x in client.get("/api/speech/attempts").json()["items"]} == {"old", "new"}


# --- the read ----------------------------------------------------------------------------------------------------


def test_current_session_returns_its_attempts_and_metadata_then_nothing_once_idle(client):
    _post(client, "t1")
    client.clock.advance(minutes=5)
    _post(client, "t2")
    client.clock.advance(minutes=10)
    body = client.get("/api/speech/attempts", params={"session": "current"}).json()
    assert [x["take_id"] for x in body["items"]] == ["t2", "t1"]
    meta = body["session"]
    assert meta["count"] == 2 and "items" not in meta
    assert meta["started_at"] == T0.isoformat().replace("+00:00", "Z") or meta["started_at"].startswith("2026-10-07T09:00")
    assert meta["last_activity_at"].startswith("2026-10-07T09:05")
    assert meta["expires_at"].startswith("2026-10-07T09:35")
    client.clock.advance(minutes=21)  # 31 minutes after the last take
    gone = client.get("/api/speech/attempts", params={"session": "current"}).json()
    assert gone["items"] == [] and gone["session"] is None


def test_the_read_is_exclusive_and_only_knows_current(client):
    assert client.get("/api/speech/attempts", params={"session": "current", "since": "2026-10-07T00:00:00Z"}).status_code == 422
    assert client.get("/api/speech/attempts", params={"session": "current", "asset_id": "x"}).status_code == 422
    assert client.get("/api/speech/attempts", params={"session": str(uuid.uuid4())}).status_code == 422


def test_the_read_never_extends_the_window(client):
    _post(client, "t1")
    client.clock.advance(minutes=29)
    assert client.get("/api/speech/attempts", params={"session": "current"}).json()["session"] is not None
    client.clock.advance(minutes=2)  # 31 after the take; the read at 29 did not refresh it
    assert client.get("/api/speech/attempts", params={"session": "current"}).json()["session"] is None


# --- the migration -----------------------------------------------------------------------------------------------


def _migration():
    path = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "20261007_0029_practice_session_id.py"
    spec = importlib.util.spec_from_file_location("rev_0029", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_is_additive_nullable_and_reversible(tmp_path):
    module = _migration()
    assert module.revision == "20261007_0029" and module.down_revision == "20261004_0025"
    eng = create_engine(f"sqlite+pysqlite:///{tmp_path / 'm.db'}")
    with eng.begin() as c:
        c.execute(sa.text(
            "CREATE TABLE speaking_attempts (id CHAR(32) PRIMARY KEY, user_id CHAR(32) NOT NULL, "
            "language_code VARCHAR(20) NOT NULL, take_id VARCHAR(120) NOT NULL, created_at DATETIME NOT NULL)"))
        c.execute(sa.text("INSERT INTO speaking_attempts VALUES ('a', 'u', 'en', 't', '2026-10-01')"))

    def run(fn):
        with eng.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                fn()

    run(module.upgrade)
    insp = sa.inspect(eng)
    column = {c["name"]: c for c in insp.get_columns("speaking_attempts")}["practice_session_id"]
    assert column["nullable"] is True
    assert module.INDEX in {i["name"] for i in insp.get_indexes("speaking_attempts")}
    with eng.connect() as c:
        assert c.execute(sa.text("SELECT practice_session_id FROM speaking_attempts")).scalar() is None, "no backfill"
    run(module.downgrade)
    insp = sa.inspect(eng)
    assert "practice_session_id" not in {c["name"] for c in insp.get_columns("speaking_attempts")}
    assert module.INDEX not in {i["name"] for i in insp.get_indexes("speaking_attempts")}
    with eng.connect() as c:
        assert c.execute(sa.text("SELECT count(*) FROM speaking_attempts")).scalar() == 1, "downgrade loses only the id"
    run(module.upgrade)  # up / down / up


def test_the_model_and_the_revision_agree_on_the_index():
    names = {i.name for i in Base.metadata.tables["speaking_attempts"].indexes}
    assert _migration().INDEX in names
    assert Base.metadata.tables["speaking_attempts"].c.practice_session_id.nullable is True
