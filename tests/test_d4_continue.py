"""D4 slice 3: the learner's place in content, on `library_items` (I4, D-104 H-12 Design B).

SQLite builds its schema from `models.py`; PostgreSQL (when `ORENA_TEST_POSTGRES_URL` names a
throwaway database at the head) runs the migrated schema. The same repository code runs on both.
"""
from __future__ import annotations

import contextvars
import threading
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select, text, update
from sqlalchemy.orm import Session

from writing_coach import library_api
from writing_coach.persistence.ids import stable_uuid
from writing_coach.persistence.library_repository import (
    PLACE_COALESCE_SECONDS,
    LibraryConflict,
    LibraryRepository,
)
from writing_coach.persistence.models import Base, LibraryItem, User


@pytest.fixture(params=["sqlite", "postgres"])
def env(request, tmp_path):
    if request.param == "sqlite":
        engine = create_engine(f"sqlite:///{tmp_path / 'library.db'}")

        @event.listens_for(engine, "connect")
        def _fk(connection, _record):  # noqa: ANN001
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(engine)
    else:
        engine = request.getfixturevalue("pg_engine")
    who = {"user": f"cont-{uuid.uuid4().hex[:10]}", "language": "en"}
    now = datetime.now(UTC)
    with Session(engine) as session, session.begin():
        for key in (who["user"], who["user"] + "-b"):
            session.add(User(id=stable_uuid("user", key), user_key=key, email="", name="", picture="", role="user", created_at=now))

    def repository(user=None, language=None):
        return LibraryRepository(
            engine,
            user_key_provider=lambda: user or who["user"],
            language_provider=lambda: language or who["language"],
        )

    return type("Env", (), {"engine": engine, "who": who, "repo": staticmethod(repository), "name": request.param})


def _place(index=2, total=10, **extra):
    return {"index": index, "total": total, "within": 40, "finished": False, "cleared": False,
            "title": "A text", "intent": None, "segment": "", "context": "", **extra}


def _query(env, source_id="reading:14", kind=None):
    conditions = [LibraryItem.user_id == stable_uuid("user", env.who["user"]), LibraryItem.source_id == source_id]
    if kind:
        conditions.append(LibraryItem.kind == kind)
    return select(LibraryItem).where(*conditions)


def _row(env, kind="reading", source_id="reading:14"):
    with Session(env.engine) as session:
        row = session.scalar(_query(env, source_id, kind))
        if row is not None:
            session.expunge(row)
        return row


# --- the repository ------------------------------------------------------------------------


def test_a_place_round_trips_and_a_new_session_reads_it_back(env):
    written = env.repo().set_place(kind="reading", source_id="reading:14", place=_place())
    assert written["status"] == "written"
    fresh = env.repo()  # a different repository object: nothing is cached
    listed = fresh.list_places(limit=10)
    assert [(item["content_id"], item["kind"], item["place"]["index"]) for item in listed] == [("reading:14", "reading", 2)]
    assert listed[0]["place_at"]


def test_ids_of_every_shape_round_trip(env):
    for kind, source_id in (("reading", "text:9f3a"), ("listening", "media:lesson-1"), ("book", "book:b1:c2"), ("reading", "url:abc123")):
        env.repo().set_place(kind=kind, source_id=source_id, place=_place())
    got = {(item["kind"], item["content_id"]) for item in env.repo().list_places(limit=10)}
    assert got == {("reading", "text:9f3a"), ("listening", "media:lesson-1"), ("book", "book:b1:c2"), ("reading", "url:abc123")}


def test_the_list_is_ordered_by_place_at_bounded_and_scoped(env):
    for number in range(5):
        env.repo().set_place(kind="reading", source_id=f"reading:{number}", place=_place())
    assert [item["content_id"] for item in env.repo().list_places(limit=3)] == ["reading:4", "reading:3", "reading:2"]
    assert len(env.repo().list_places(limit=500)) == 5, "the bound is applied, not the asker's number"
    assert env.repo(language="zh").list_places() == [], "another language is another scope"
    assert env.repo(user=env.who["user"] + "-b").list_places() == [], "another account sees nothing"


def test_a_place_write_never_touches_version_or_updated_at_and_a_concurrent_pin_still_lands(env):
    library = env.repo()
    library.set_place(kind="reading", source_id="reading:14", place=_place(1, 10))
    item = library.keep(kind="reading", source_id="reading:14", relationship="started")
    assert item["version"] == 1
    before = _row(env)
    library.set_place(kind="reading", source_id="reading:14", place=_place(5, 10))
    after = _row(env)
    assert (after.version, after.updated_at) == (before.version, before.updated_at)
    assert after.place["index"] == 5
    pinned = library.update(item["id"], expected_version=1, pinned=True)
    assert pinned["pinned"] is True and pinned["version"] == 2
    assert _row(env).place["index"] == 5, "the pin PATCH did not disturb the place"


def test_a_repeat_write_within_thirty_seconds_that_crosses_no_boundary_is_coalesced(env):
    library = env.repo()
    library.set_place(kind="reading", source_id="reading:14", place=_place(3, 10, within=10))
    stamp = _row(env).place_at
    quick = library.set_place(kind="reading", source_id="reading:14", place=_place(3, 10, within=55))
    assert quick["status"] == "coalesced" and quick["place"]["within"] == 10
    assert _row(env).place_at == stamp, "a coalesced write is not an UPDATE"
    for boundary in (_place(4, 10, within=55), _place(3, 10, within=55, finished=True), _place(3, 10, within=55, cleared=True), _place(3, 11, within=55)):
        assert library.set_place(kind="reading", source_id="reading:14", place=boundary)["status"] == "written"
    assert PLACE_COALESCE_SECONDS == 30


def test_after_thirty_seconds_the_same_position_is_written_again(env):
    library = env.repo()
    library.set_place(kind="reading", source_id="reading:14", place=_place(3, 10, within=10))
    with Session(env.engine) as session, session.begin():
        session.execute(update(LibraryItem).where(*_query(env).whereclause.clauses).values(place_at=datetime.now(UTC) - timedelta(seconds=90)))
    assert library.set_place(kind="reading", source_id="reading:14", place=_place(3, 10, within=60))["status"] == "written"
    assert library.list_places()[0]["place"]["within"] == 60


def test_finished_and_cleared_round_trip_and_a_cleared_place_keeps_the_relationship(env):
    library = env.repo()
    library.set_place(kind="reading", source_id="reading:14", place=_place(10, 10, within=100, finished=True))
    assert library.list_places()[0]["place"]["finished"] is True
    library.set_place(kind="reading", source_id="reading:14", place=_place(10, 10, finished=True, cleared=True))
    assert library.list_places() == [], "a cleared place is not offered as something to continue"
    assert _row(env) is not None, "clearing deletes nothing the learner may also have kept or pinned"


def test_unsetting_a_place_is_sql_null_never_json_null(env):
    """Delta review P2-3: with `none_as_null` a cleared column is not in the partial index."""
    assert LibraryItem.__table__.c.place.type.none_as_null is True
    library = env.repo()
    library.set_place(kind="reading", source_id="reading:14", place=_place())
    library.set_place(kind="reading", source_id="reading:14", place=None)
    with env.engine.connect() as connection:
        row = connection.execute(
            select(LibraryItem.place.is_(None), LibraryItem.place_at.is_(None), LibraryItem.place.is_not(None)).where(*_query(env).whereclause.clauses)
        ).one()
    assert tuple(row) == (True, True, False), "the column is SQL NULL, not a JSON null that would enter the index"
    assert library.list_places() == []
    if env.name == "postgres":
        with env.engine.connect() as connection:
            index = connection.execute(text("SELECT indexdef FROM pg_indexes WHERE indexname='ix_library_items_place'")).scalar()
        assert "WHERE (place IS NOT NULL)" in index


def test_the_started_row_of_one_item_is_one_row(env):
    library = env.repo()
    for index in (1, 2, 3):
        library.set_place(kind="reading", source_id="reading:14", place=_place(index, 10))
    with Session(env.engine) as session:
        count = session.scalar(select(func.count()).select_from(LibraryItem).where(
            *_query(env).whereclause.clauses, LibraryItem.relationship_kind == "started"))
    assert count == 1


def test_unknown_kinds_are_refused(env):
    with pytest.raises(LibraryConflict):
        env.repo().set_place(kind="word", source_id="x", place=_place())
    with pytest.raises(LibraryConflict):
        env.repo().set_place(kind="reading", source_id="  ", place=_place())


def test_two_first_opens_at_once_make_one_row(env):
    results = []
    barrier = threading.Barrier(4)

    def open_it(number):
        barrier.wait()
        try:
            results.append(env.repo().set_place(kind="reading", source_id="reading:race", place=_place(number + 1, 10))["status"])
        except LibraryConflict:
            results.append("conflict")

    threads = [threading.Thread(target=contextvars.copy_context().run, args=(open_it, n)) for n in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert set(results) <= {"written", "coalesced"}, results
    with Session(env.engine) as session:
        count = session.scalar(select(func.count()).select_from(LibraryItem).where(*_query(env, "reading:race").whereclause.clauses))
    assert count == 1


# --- the routes -----------------------------------------------------------------------------


@pytest.fixture
def client(env):
    library_api.configure_library(lambda: env.repo())
    app = FastAPI()
    app.include_router(library_api.continue_router)
    yield TestClient(app)
    library_api.configure_library(None)


def test_put_then_get_returns_the_place(client):
    put = client.put("/api/continue/reading:14", json={"kind": "reading", "place": _place(3, 12, segment="p2s1", context="A Book")})
    assert put.status_code == 200 and put.json()["status"] == "written"
    items = client.get("/api/continue", params={"limit": 5}).json()["items"]
    assert items[0]["content_id"] == "reading:14"
    assert items[0]["place"]["segment"] == "p2s1" and items[0]["place"]["context"] == "A Book"


def test_a_place_that_cannot_be_true_is_refused(client):
    for bad in (_place(11, 10), _place(0, 10), {"finished": False}, _place(2, 10, within=101), _place(2, 10, intent="Has Spaces")):
        response = client.put("/api/continue/reading:14", json={"kind": "reading", "place": bad})
        assert response.status_code == 422, bad
    assert client.put("/api/continue/reading:14", json={"kind": "note", "place": _place()}).status_code == 422
    assert client.put("/api/continue/reading:14", json={"kind": "reading", "place": {**_place(), "extra": 1}}).status_code == 422
    assert client.get("/api/continue").json()["items"] == []


def test_a_cleared_write_needs_no_position_and_a_null_place_unsets(client):
    client.put("/api/continue/reading:14", json={"kind": "reading", "place": _place()})
    cleared = client.put("/api/continue/reading:14", json={"kind": "reading", "place": {"cleared": True}})
    assert cleared.status_code == 200
    assert client.get("/api/continue").json()["items"] == []
    client.put("/api/continue/reading:15", json={"kind": "reading", "place": _place()})
    assert client.put("/api/continue/reading:15", json={"kind": "reading", "place": None}).status_code == 200
    assert client.get("/api/continue").json()["items"] == []


def test_the_limit_is_bounded(client):
    assert client.get("/api/continue", params={"limit": 51}).status_code == 422
    assert client.get("/api/continue", params={"limit": 0}).status_code == 422


def test_without_the_postgres_runtime_the_route_says_so():
    library_api.configure_library(lambda: None)
    try:
        app = FastAPI()
        app.include_router(library_api.continue_router)
        response = TestClient(app).get("/api/continue")
        assert response.status_code == 503 and response.json()["detail"]["category"] == "library_unavailable"
    finally:
        library_api.configure_library(None)


# --- a place is never a bookmark (implementation review P1-1) -------------------------------------


def test_a_place_never_reads_as_saved_and_keeping_after_a_place_returns_exactly_the_kept_row(env):
    library = env.repo()
    library.set_place(kind="reading", source_id="reading:77", place=_place())
    assert library.lookup(kind="reading", source_ids=("reading:77",)) == [], "opened is not saved"
    kept = library.keep(kind="reading", source_id="reading:77")
    found = library.lookup(kind="reading", source_ids=("reading:77",))
    assert [(row["id"], row["relationship"]) for row in found] == [(kept["id"], "kept")]
    assert library.list_places()[0]["content_id"] == "reading:77", "the place is still there"


def test_where_a_marked_row_and_a_kept_row_share_a_source_the_kept_one_comes_first(env):
    library = env.repo()
    library.set_place(kind="reading", source_id="reading:78", place=_place())
    started = library.keep(kind="reading", source_id="reading:78", relationship="started")
    library.update(started["id"], expected_version=started["version"], pinned=True)
    kept = library.keep(kind="reading", source_id="reading:78")
    rows = library.lookup(kind="reading", source_ids=("reading:78",))
    assert [row["relationship"] for row in rows] == ["kept", "started"] and rows[0]["id"] == kept["id"]


def test_forgetting_a_bookmark_leaves_the_place_and_unmarking_a_read_item_never_destroys_it(env):
    library = env.repo()
    library.set_place(kind="reading", source_id="reading:79", place=_place(4, 9))
    kept = library.keep(kind="reading", source_id="reading:79")
    assert library.forget(kept["id"]) is True
    assert library.list_places()[0]["place"]["index"] == 4, "removing the bookmark left the place"
    started = library.keep(kind="reading", source_id="reading:79", relationship="started")
    marked = library.update(started["id"], expected_version=started["version"], pinned=True, note="remember")
    assert marked["pinned"] is True
    assert len(library.lookup(kind="reading", source_ids=("reading:79",))) == 1, "a marked row is visible"
    assert library.forget(started["id"]) is True
    assert library.list_places()[0]["place"]["index"] == 4, "un-marking kept where the learner was"
    assert library.lookup(kind="reading", source_ids=("reading:79",)) == [], "and it no longer reads as anything saved"
    assert _row(env, source_id="reading:79", kind="reading") is not None


def test_the_items_route_never_returns_a_place_only_row(env):
    library_api.configure_library(lambda: env.repo())
    try:
        app = FastAPI()
        app.include_router(library_api.router)
        client = TestClient(app)
        env.repo().set_place(kind="listening", source_id="media:x1", place=_place())
        assert client.get("/api/library/items", params={"kind": "listening", "sources": "media:x1"}).json() == {"items": []}
        client.post("/api/library/items", json={"kind": "listening", "source_id": "media:x1"})
        items = client.get("/api/library/items", params={"kind": "listening", "sources": "media:x1"}).json()["items"]
        assert [row["relationship"] for row in items] == ["kept"]
    finally:
        library_api.configure_library(None)
