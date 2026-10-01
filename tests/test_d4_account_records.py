"""D4 slice 6: the records kept with the account - conversation turns, notes and highlights, private
imports, typed and Reading Transfer responses, kept-language provenance, the bounded works list, and the
draft's prompt reference (I5, I6, I8-I10, I12; D-104 H-18).

Backbone OFF: every route answers 503 and nothing claims a save. Backbone ON (real PostgreSQL, the
throwaway database of ORENA_TEST_POSTGRES_URL): the routes run against the real repositories.
"""
from __future__ import annotations

import contextvars
import threading
import uuid
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from writing_coach import account_records_api, work_api
from writing_coach.account_backbone import DISABLED, AccountBackbone, build_backbone
from writing_coach.persistence.ids import stable_uuid
from writing_coach.persistence.models import SavedWord


def _app():
    app = FastAPI()
    app.include_router(work_api.router)
    app.include_router(account_records_api.router)
    return app


class _As(TestClient):
    """A client that is always one account in one language: the work API reads its identity from module
    configuration, so each request re-asserts this client's own before it goes out."""

    def __init__(self, backbone, user, language):
        super().__init__(_app())
        self._identity = (backbone, user, language)

    def request(self, *args, **kwargs):
        backbone, user, language = self._identity
        work_api.configure_work(backbone, user_key=lambda: user, language=lambda: language)
        return super().request(*args, **kwargs)


def _client(backbone, *, user="learner-a", language="en"):
    return _As(backbone, user, language)


@pytest.fixture(autouse=True)
def _reset():
    yield
    work_api.configure_work(AccountBackbone(DISABLED))


_OP = {"operationId": "op-00000000"}
OFF_CALLS = [
    ("get", "/api/works", None),
    ("get", f"/api/works/{uuid.uuid4()}", None),
    ("get", "/api/conversations/conversation:x", None),
    ("post", "/api/conversations/conversation:x/turns", {**_OP, "expectedHead": 0, "id": "t1", "role": "learner", "text": "Hi"}),
    ("get", "/api/annotations/reading:1", None),
    ("put", "/api/annotations/reading:1", {**_OP, "expectedVersion": 0}),
    ("get", "/api/imports", None),
    ("put", f"/api/imports/{uuid.uuid4()}", {**_OP, "expectedVersion": 0, "form": "text", "title": "t", "text": "x"}),
    ("delete", f"/api/imports/{uuid.uuid4()}?operationId=op-00000000&expectedVersion=1", None),
    ("get", "/api/responses/transfer:a:b:1", None),
    ("put", "/api/responses/transfer:a:b:1", {**_OP, "expectedVersion": 0, "mode": "paraphrase"}),
    ("get", "/api/library/vocabulary/harbour/provenance", None),
    ("post", "/api/library/vocabulary/harbour/provenance", {**_OP, "reason": "looked_up"}),
    ("put", "/api/drafts/expression:free", {**_OP, "expectedVersion": 0, "text": "x"}),
]


@pytest.mark.parametrize("method,path,body", OFF_CALLS)
def test_with_the_backbone_off_every_route_says_so_and_claims_nothing(method, path, body):
    client = _client(AccountBackbone(DISABLED))
    response = getattr(client, method)(path, **({"json": body} if body is not None else {}))
    assert response.status_code == 503, (path, response.text)
    assert response.json()["detail"]["category"] == "account_backbone_disabled"


# --- PostgreSQL with the backbone on ---------------------------------------------------------------


@pytest.fixture
def backbone(pg_engine):
    built = build_backbone(pg_engine, inspect(pg_engine).get_table_names(), env={"ORENA_ACCOUNT_BACKBONE": "on"})
    assert built.is_active
    return built


def _account(engine, key=None):
    key = key or f"rec-{uuid.uuid4().hex[:12]}"
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO users (id, user_key, email, name, picture, role, created_at) "
                 "VALUES (:id, :key, '', '', '', 'user', :now) ON CONFLICT DO NOTHING"),
            {"id": stable_uuid("user", key), "key": key, "now": datetime.now(UTC)},
        )
    return key


def op():
    return f"op-{uuid.uuid4()}"


# -- generic route restriction (P1-5) and the bounded list ----------------------------------------


def test_the_generic_route_refuses_the_kinds_that_have_dedicated_routes(pg_engine, backbone):
    client = _client(backbone, user=_account(pg_engine))
    for kind in ("annotation", "imported"):
        refused = client.put(f"/api/works/{uuid.uuid4()}", json={"operationId": op(), "expectedVersion": 0, "kind": kind, "payload": {}})
        assert refused.status_code == 422 and refused.json()["detail"]["category"] == "work_kind_invalid", kind
    accepted = client.put(f"/api/works/{uuid.uuid4()}", json={"operationId": op(), "expectedVersion": 0, "kind": "response", "payload": {"a": 1}})
    assert accepted.status_code == 200


def test_the_generic_route_never_creates_a_work_that_is_already_deleted(pg_engine, backbone):
    """Create-as-deleted, repeated, left a row per call while the live count never rose (limits review P1-1)."""
    client = _client(backbone, user=_account(pg_engine))
    for kind in ("response", "conversation", "draft"):
        ident = uuid.uuid4()
        refused = client.put(f"/api/works/{ident}", json={"operationId": op(), "expectedVersion": 0, "kind": kind, "lifecycle": "deleted", "payload": {"a": 1}})
        assert refused.status_code == 422 and refused.json()["detail"]["category"] == "lifecycle_invalid", kind
        assert client.get(f"/api/works/{ident}").status_code == 404, "nothing was written"
    assert client.get("/api/works", params={"limit": 50}).json()["works"] == []
    # A removal is still a later write against a version that exists.
    ident = uuid.uuid4()
    assert client.put(f"/api/works/{ident}", json={"operationId": op(), "expectedVersion": 0, "kind": "response", "payload": {"a": 1}}).status_code == 200
    assert client.put(f"/api/works/{ident}", json={"operationId": op(), "expectedVersion": 1, "kind": "response", "lifecycle": "deleted", "payload": {"a": 1}}).status_code == 200


def test_create_delete_create_stops_at_the_import_tombstone_bound(pg_engine, backbone, monkeypatch):
    """The live cap of 20 never tripped for a loop that deletes each import; the total of import rows is bounded too."""
    monkeypatch.setenv("ORENA_LIMIT_IMPORT_TOMBSTONES", "52")
    client = _client(backbone, user=_account(pg_engine))
    made = 0
    for _ in range(60):
        ident = uuid.uuid4()
        put = client.put(f"/api/imports/{ident}", json={"operationId": op(), "expectedVersion": 0, "form": "text", "title": "T", "text": "x"})
        if put.status_code != 200:
            assert put.status_code == 422 and put.json()["detail"]["category"] == "import_limit", put.text
            break
        made += 1
        assert client.delete(f"/api/imports/{ident}", params={"operationId": op(), "expectedVersion": 1}).status_code == 200
    assert made == 52, "the loop stops at the tombstone bound, with a live count of zero"
    # Another account, and another language of the same account, are not touched by this one's bound.
    other = _client(backbone, user=_account(pg_engine))
    assert other.put(f"/api/imports/{uuid.uuid4()}", json={"operationId": op(), "expectedVersion": 0, "form": "text", "title": "T", "text": "x"}).status_code == 200


def test_the_import_tombstone_bound_refuses_a_bad_configuration(monkeypatch):
    for bad in ("many", "51", "-3"):
        monkeypatch.setenv("ORENA_LIMIT_IMPORT_TOMBSTONES", bad)
        with pytest.raises(RuntimeError):
            account_records_api._import_row_bound()
    monkeypatch.delenv("ORENA_LIMIT_IMPORT_TOMBSTONES")
    assert account_records_api._import_row_bound() == 360


def test_imported_media_is_kept_with_the_account_and_listed_on_a_new_device_by_language(pg_engine, backbone):
    user = _account(pg_engine)
    client = _client(backbone, user=user)
    link, file_ = str(uuid.uuid4()), str(uuid.uuid4())
    assert client.put(f"/api/imports/{link}", json={"operationId": op(), "expectedVersion": 0, "form": "url", "title": "A talk", "url": "https://example.test/v",
                                                      "kind": "video", "durationMs": 61000, "thumbnailUrl": "https://example.test/t.jpg", "provider": "example"}).status_code == 200
    assert client.put(f"/api/imports/{file_}", json={"operationId": op(), "expectedVersion": 0, "form": "upload", "title": "My file", "mediaId": "stored-123",
                                                       "kind": "audio", "thumbnailUrl": "http://insecure.test/t.jpg"}).status_code == 200
    assert client.put(f"/api/imports/{uuid.uuid4()}", json={"operationId": op(), "expectedVersion": 0, "form": "upload", "title": "x"}).status_code == 422
    listed = {item["id"]: item for item in _client(backbone, user=user).get("/api/imports").json()["imports"]}
    assert listed[f"url:{link}"]["url"] == "https://example.test/v" and listed[f"url:{link}"]["durationMs"] == 61000
    assert listed[f"url:{link}"]["thumbnailUrl"] == "https://example.test/t.jpg" and listed[f"url:{link}"]["provider"] == "example"
    assert listed[f"upload:{file_}"]["mediaId"] == "stored-123" and listed[f"upload:{file_}"]["thumbnailUrl"] == "", "only an https thumbnail is kept"
    assert _client(backbone, user=user, language="zh").get("/api/imports").json()["imports"] == []


def test_the_works_list_is_bounded_newest_first_and_scoped(pg_engine, backbone):
    user = _account(pg_engine)
    client = _client(backbone, user=user)
    for number in range(5):
        client.put(f"/api/works/{uuid.uuid4()}", json={"operationId": op(), "expectedVersion": 0, "kind": "response", "payload": {"n": number}})
    listed = client.get("/api/works", params={"kind": "response", "limit": 3}).json()["works"]
    assert [item["payload"]["n"] for item in listed] == [4, 3, 2]
    assert client.get("/api/works", params={"limit": 51}).status_code == 422
    assert client.get("/api/works", params={"kind": "draft"}).json()["works"] == []
    other = _client(backbone, user=_account(pg_engine))
    assert other.get("/api/works", params={"kind": "response"}).json()["works"] == []
    zh = _client(backbone, user=user, language="zh")
    assert zh.get("/api/works", params={"kind": "response"}).json()["works"] == []


# -- conversations (I6) -----------------------------------------------------------------------------


def _turn(client, key, head, role, text_, *, turn_id, reply_to=None, operation=None, **extra):
    return client.post(f"/api/conversations/{key}/turns", json={
        "operationId": operation or op(), "expectedHead": head, "id": turn_id, "role": role, "text": text_,
        "replyTo": reply_to, "title": "Ordering coffee", "situation": "You are at a cafe.", **extra})


def test_turns_append_at_the_head_replay_and_restore_on_a_new_device(pg_engine, backbone):
    user = _account(pg_engine)
    client = _client(backbone, user=user)
    key = f"conversation:{uuid.uuid4().hex[:8]}"
    first_op = op()
    first = _turn(client, key, 0, "learner", "Hello, a coffee please.", turn_id="t1", operation=first_op)
    assert first.status_code == 200 and first.json()["turn"]["ordinal"] == 1 and first.json()["head"] == 1
    again = _turn(client, key, 0, "learner", "Hello, a coffee please.", turn_id="t1", operation=first_op)
    assert again.json()["status"] == "replay" and again.json()["turn"] == first.json()["turn"], "a retry returns the same turn"
    reply = _turn(client, key, 1, "partner", "Of course. Anything else?", turn_id="reply-t1", reply_to="t1", meaning="Tất nhiên.", support="vi")
    assert reply.status_code == 200 and reply.json()["turn"]["role"] == "partner" and reply.json()["turn"]["meaning"] == "Tất nhiên."
    restored = _client(backbone, user=user).get(f"/api/conversations/{key}").json()["conversation"]
    assert restored["head"] == 2 and [t["ordinal"] for t in restored["turns"]] == [1, 2]
    assert restored["title"] == "Ordering coffee" and restored["ended"] is False
    listed = client.get("/api/works", params={"kind": "conversation"}).json()["works"]
    assert any(item["payload"].get("situation") == "You are at a cafe." for item in listed)


def test_two_appends_at_one_head_give_one_turn_and_one_conflict(pg_engine, backbone):
    client = _client(backbone, user=_account(pg_engine))
    key = f"conversation:{uuid.uuid4().hex[:8]}"
    _turn(client, key, 0, "learner", "One", turn_id="t1")
    results = []
    barrier = threading.Barrier(2)

    def go(number):
        barrier.wait()
        results.append(_turn(client, key, 1, "partner", f"Reply {number}", turn_id=f"r{number}", reply_to="t1").status_code)

    threads = [threading.Thread(target=contextvars.copy_context().run, args=(go, n)) for n in (1, 2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(results) == [200, 409], results
    state = client.get(f"/api/conversations/{key}").json()["conversation"]
    assert state["head"] == 2 and [t["ordinal"] for t in state["turns"]] == [1, 2]
    stale = _turn(client, key, 1, "partner", "Late", turn_id="late", reply_to="t1")
    assert stale.status_code == 409 and stale.json()["detail"]["context"]["serverHead"] == 2


@pytest.mark.parametrize("plan,code", [
    ([("learner", "a", None), ("learner", "b", None)], "role_order"),
    ([("learner", "a", None), ("partner", "r", "wrong")], "reply_to_mismatch"),
    ([("learner", "a", None), ("partner", "a", "a")], "duplicate_turn_id"),
])
def test_the_conversation_rules_are_enforced_on_the_server(pg_engine, backbone, plan, code):
    client = _client(backbone, user=_account(pg_engine))
    key = f"conversation:{uuid.uuid4().hex[:8]}"
    responses = [_turn(client, key, head, role, f"text {turn_id}", turn_id=turn_id, reply_to=reply_to)
                 for head, (role, turn_id, reply_to) in enumerate(plan)]
    assert [r.status_code for r in responses[:-1]] == [200] * (len(plan) - 1)
    assert responses[-1].status_code == 422 and responses[-1].json()["detail"]["category"] == code
    assert client.get(f"/api/conversations/{key}").json()["conversation"]["head"] == len(plan) - 1, "a refused turn writes nothing"


def test_an_ended_conversation_and_the_turn_limit_take_no_more(pg_engine, backbone):
    client = _client(backbone, user=_account(pg_engine))
    key = f"conversation:{uuid.uuid4().hex[:8]}"
    _turn(client, key, 0, "learner", "Hi", turn_id="t1")
    _turn(client, key, 1, "partner", "Bye", turn_id="r1", reply_to="t1", ended=True)
    assert client.get(f"/api/conversations/{key}").json()["conversation"]["ended"] is True
    closed = _turn(client, key, 2, "learner", "More", turn_id="t2")
    assert closed.status_code == 422 and closed.json()["detail"]["category"] == "conversation_ended"
    long_key = f"conversation:{uuid.uuid4().hex[:8]}"
    previous = None
    for number in range(24):
        role = "learner" if number % 2 == 0 else "partner"
        turn_id = f"x{number}"
        response = _turn(client, long_key, number, role, f"line {number}", turn_id=turn_id, reply_to=previous if role == "partner" else None)
        assert response.status_code == 200, (number, response.text)
        previous = turn_id
    over = _turn(client, long_key, 24, "learner", "one too many", turn_id="x24")
    assert over.status_code == 422 and over.json()["detail"]["category"] == "turn_limit"


def test_another_account_and_another_language_cannot_read_or_extend_a_conversation(pg_engine, backbone):
    owner = _account(pg_engine)
    key = f"conversation:{uuid.uuid4().hex[:8]}"
    _turn(_client(backbone, user=owner), key, 0, "learner", "Private", turn_id="t1")
    for other in (_client(backbone, user=_account(pg_engine)), _client(backbone, user=owner, language="zh")):
        assert other.get(f"/api/conversations/{key}").status_code == 404
    assert _client(backbone, user=owner, language="zh").get(f"/api/conversations/{key}").status_code == 404


def test_turns_are_immutable_and_contiguous_in_the_database(pg_engine, backbone):
    user = _account(pg_engine)
    client = _client(backbone, user=user)
    key = f"conversation:{uuid.uuid4().hex[:8]}"
    _turn(client, key, 0, "learner", "Hi", turn_id="t1")
    _turn(client, key, 1, "partner", "Hello", turn_id="r1", reply_to="t1")
    ident = str(stable_uuid("work", str(stable_uuid("user", user)), _incarnation(pg_engine, user), "en", "conversation", key))
    with pg_engine.connect() as connection:
        ordinals = [row[0] for row in connection.execute(text("SELECT ordinal FROM work_turns WHERE work_id=:w ORDER BY ordinal"), {"w": ident})]
    assert ordinals == [1, 2]


def _incarnation(engine, user):
    with engine.connect() as connection:
        return str(connection.execute(text("SELECT i.id FROM account_incarnations i JOIN users u ON u.id=i.user_id WHERE u.user_key=:k AND i.status='active'"), {"k": user}).scalar())


# -- notes and highlights (I10) ----------------------------------------------------------------------


def _annotate(client, content, version, highlights=(), notes=(), **extra):
    return client.put(f"/api/annotations/{content}", json={"operationId": op(), "expectedVersion": version,
                                                           "highlights": list(highlights), "notes": list(notes), **extra})


H1 = {"id": "h1", "segment": "p1s1", "sentence": "The river rose overnight.", "at": "2026-09-30T10:00:00Z"}
H2 = {"id": "h2", "segment": "p2s1", "sentence": "By morning it was a lake.", "at": "2026-09-30T10:05:00Z"}
N1 = {"id": "n1", "key": "p1s1", "type": "question", "text": "Why overnight?", "at": "2026-09-30T10:01:00Z"}


def test_notes_and_highlights_round_trip_on_a_new_device_and_in_every_content_id_shape(pg_engine, backbone):
    user = _account(pg_engine)
    client = _client(backbone, user=user)
    for content in ("reading:14", "book:b1:c2", "text:9f3a", "media:lesson-1"):
        saved = _annotate(client, content, 0, [H1], [N1])
        assert saved.status_code == 200 and saved.json()["version"] == 1, content
        read = _client(backbone, user=user).get(f"/api/annotations/{content}").json()["annotation"]
        assert read["highlights"] == [H1] and read["notes"] == [N1] and read["cleared"] is False


def test_two_clients_adding_at_once_conflict_and_a_union_keeps_both(pg_engine, backbone):
    user = _account(pg_engine)
    one, two = _client(backbone, user=user), _client(backbone, user=user)
    assert _annotate(one, "reading:20", 0, [H1]).status_code == 200
    stale = _annotate(two, "reading:20", 0, [H2])
    assert stale.status_code == 409
    server = stale.json()["detail"]["context"]
    assert server["serverVersion"] == 1 and [h["id"] for h in server["serverPayload"]["highlights"]] == ["h1"], "nothing was merged"
    current = one.get("/api/annotations/reading:20").json()["annotation"]
    union = {item["id"]: item for item in current["highlights"] + [H1, H2]}
    merged = _annotate(two, "reading:20", current["version"], list(union.values()))
    assert merged.status_code == 200
    ids = {item["id"] for item in one.get("/api/annotations/reading:20").json()["annotation"]["highlights"]}
    assert ids == {"h1", "h2"}


def test_annotation_bounds_are_enforced_and_clearing_is_a_flag_not_a_deletion(pg_engine, backbone):
    client = _client(backbone, user=_account(pg_engine))
    many = [{"id": f"h{n}", "sentence": "x"} for n in range(81)]
    assert _annotate(client, "reading:1", 0, many).status_code == 422
    assert _annotate(client, "reading:1", 0, [{"id": "h", "sentence": "x" * 401}]).status_code == 422
    assert _annotate(client, "reading:1", 0, notes=[{"id": f"n{n}", "text": "x"} for n in range(121)]).status_code == 422
    assert _annotate(client, "reading:1", 0, notes=[{"id": "n", "text": "x" * 601}]).status_code == 422
    assert _annotate(client, "reading:1", 0, notes=[{"id": "n", "type": "essay", "text": "x"}]).status_code == 422
    assert _annotate(client, "reading:1", 0, [{"id": "same", "sentence": "a"}], [{"id": "same", "text": "b"}]).status_code == 422
    full = _annotate(client, "reading:2", 0, [{"id": f"h{n}", "sentence": "y" * 400} for n in range(80)],
                     [{"id": f"n{n}", "text": "z" * 600} for n in range(120)])
    assert full.status_code == 200, "the worst case fits the payload bound"
    cleared = _annotate(client, "reading:2", 1, cleared=True)
    assert cleared.status_code == 200
    read = client.get("/api/annotations/reading:2").json()["annotation"]
    assert read["cleared"] is True and read["highlights"] == [] and read["notes"] == []
    # Named contract change (tombstones): an id that was cleared is remembered and never comes back; a NEW item is fine.
    assert _annotate(client, "reading:2", 2, [H1]).status_code == 422, "a cleared id is not resurrected"
    assert _annotate(client, "reading:2", 2, [{**H1, "id": "fresh-after-clear"}]).status_code == 200, "a cleared record is written again with new items"


def test_annotations_are_private_to_the_account_and_language(pg_engine, backbone):
    owner = _account(pg_engine)
    _annotate(_client(backbone, user=owner), "reading:30", 0, [H1])
    assert _client(backbone, user=_account(pg_engine)).get("/api/annotations/reading:30").status_code == 404
    assert _client(backbone, user=owner, language="zh").get("/api/annotations/reading:30").status_code == 404
    assert _annotate(_client(backbone, user=_account(pg_engine)), "reading:30", 0, [H2]).status_code == 200, "another account's own record, not the owner's"


def test_a_lost_acknowledgment_replays_the_same_annotation_write(pg_engine, backbone):
    client = _client(backbone, user=_account(pg_engine))
    operation = op()
    body = {"operationId": operation, "expectedVersion": 0, "highlights": [H1], "notes": []}
    assert client.put("/api/annotations/reading:40", json=body).json()["status"] == "committed"
    assert client.put("/api/annotations/reading:40", json=body).json()["status"] == "replay"


# -- private imports (I12) -----------------------------------------------------------------------------


def test_an_imported_text_is_kept_listed_opened_on_a_new_device_and_deleted(pg_engine, backbone):
    user = _account(pg_engine)
    client = _client(backbone, user=user)
    client_id = str(uuid.uuid4())
    saved = client.put(f"/api/imports/{client_id}", json={"operationId": op(), "expectedVersion": 0, "form": "text",
                                                          "title": "My essay", "text": "A private text."})
    assert saved.status_code == 200 and saved.json()["version"] == 1
    fresh = _client(backbone, user=user)
    opened = fresh.get(f"/api/imports/{client_id}").json()["import"]
    assert opened["id"] == f"text:{client_id}" and opened["text"] == "A private text." and opened["title"] == "My essay"
    assert [item["id"] for item in fresh.get("/api/imports").json()["imports"]] == [f"text:{client_id}"]
    other = _client(backbone, user=_account(pg_engine))
    assert other.get(f"/api/imports/{client_id}").status_code == 404
    assert other.get("/api/imports").json()["imports"] == []
    removed = client.delete(f"/api/imports/{client_id}", params={"operationId": op(), "expectedVersion": 1})
    assert removed.status_code == 200
    assert fresh.get(f"/api/imports/{client_id}").status_code == 404
    assert fresh.get("/api/imports").json()["imports"] == []


def test_a_url_import_keeps_the_reference_not_a_body_and_validates(pg_engine, backbone):
    client = _client(backbone, user=_account(pg_engine))
    ident = str(uuid.uuid4())
    ok = client.put(f"/api/imports/{ident}", json={"operationId": op(), "expectedVersion": 0, "form": "url", "title": "A talk", "url": "https://example.test/v"})
    assert ok.status_code == 200
    opened = client.get(f"/api/imports/{ident}").json()["import"]
    assert opened["id"] == f"url:{ident}" and opened["url"] == "https://example.test/v" and opened["text"] == ""
    for bad in ({"form": "url", "url": "ftp://x"}, {"form": "text", "text": "   "}, {"form": "pdf"}):
        response = client.put(f"/api/imports/{uuid.uuid4()}", json={"operationId": op(), "expectedVersion": 0, "title": "t", **bad})
        assert response.status_code == 422, bad
    assert client.put("/api/imports/not-a-uuid", json={"operationId": op(), "expectedVersion": 0, "form": "text", "title": "t", "text": "x"}).status_code == 422


def test_the_twenty_first_import_is_refused_and_a_stale_edit_is_a_conflict(pg_engine, backbone):
    client = _client(backbone, user=_account(pg_engine))
    first = str(uuid.uuid4())
    for number in range(20):
        ident = first if number == 0 else str(uuid.uuid4())
        assert client.put(f"/api/imports/{ident}", json={"operationId": op(), "expectedVersion": 0, "form": "text", "title": f"T{number}", "text": "x"}).status_code == 200
    over = client.put(f"/api/imports/{uuid.uuid4()}", json={"operationId": op(), "expectedVersion": 0, "form": "text", "title": "T21", "text": "x"})
    assert over.status_code == 422 and over.json()["detail"]["category"] == "import_limit"
    edit = {"operationId": op(), "expectedVersion": 1, "form": "text", "title": "T0", "text": "edited"}
    assert client.put(f"/api/imports/{first}", json=edit).status_code == 200
    stale = client.put(f"/api/imports/{first}", json={**edit, "operationId": op(), "text": "stale"})
    assert stale.status_code == 409 and stale.json()["detail"]["context"]["serverPayload"]["text"] == "edited"


# -- typed and Reading Transfer responses (I8, I9) ---------------------------------------------------------


def test_a_response_is_kept_as_learner_work_and_is_not_a_score(pg_engine, backbone):
    user = _account(pg_engine)
    client = _client(backbone, user=user)
    key = "transfer:reading:14:p1s1:1"
    body = {"operationId": op(), "expectedVersion": 0, "mode": "paraphrase", "answer": "The river got high in the night.",
            "coaching": "Good: same meaning.", "sentenceRef": "p1s1", "sourceKind": "text", "sourceId": "reading:14"}
    assert client.put(f"/api/responses/{key}", json=body).status_code == 200
    read = _client(backbone, user=user).get(f"/api/responses/{key}").json()["response"]
    assert read == {"mode": "paraphrase", "answer": "The river got high in the night.", "coaching": "Good: same meaning.",
                    "sentenceRef": "p1s1", "version": 1}
    assert "score" not in read and "accuracy" not in read
    stale = client.put(f"/api/responses/{key}", json={**body, "operationId": op()})
    assert stale.status_code == 409
    assert client.put(f"/api/responses/{key}", json={**body, "operationId": op(), "expectedVersion": 1, "sourceId": ""}).status_code == 422
    assert _client(backbone, user=_account(pg_engine)).get(f"/api/responses/{key}").status_code == 404
    listed = client.get("/api/works", params={"kind": "response"}).json()["works"]
    assert listed and listed[0]["payload"]["mode"] == "paraphrase"


# -- drafts: the prompt reference (I5, D-103.6) -----------------------------------------------------------------


def test_a_draft_carries_an_optional_bounded_prompt_reference(pg_engine, backbone):
    client = _client(backbone, user=_account(pg_engine))
    saved = client.put("/api/drafts/expression:free", json={"operationId": op(), "expectedVersion": 0, "text": "Dear Anna",
                                                             "task": "", "promptRef": {"source": "prompt-bank", "id": "email-01"}})
    assert saved.status_code == 200
    draft = client.get("/api/drafts/expression:free").json()["draft"]
    assert draft["promptRef"] == {"source": "prompt-bank", "id": "email-01"}
    plain = client.put("/api/drafts/essay:9", json={"operationId": op(), "expectedVersion": 0, "text": "x", "task": ""})
    assert plain.status_code == 200 and "promptRef" not in client.get("/api/drafts/essay:9").json()["draft"]
    assert client.put("/api/drafts/essay:8", json={"operationId": op(), "expectedVersion": 0, "text": "x",
                                                   "promptRef": {"source": "Bad Source", "id": "x"}}).status_code == 422


# -- kept-language provenance (I12d) ----------------------------------------------------------------------


def _save_word(engine, user, word, language="en"):
    now = datetime.now(UTC)
    with Session(engine) as session, session.begin():
        session.add(SavedWord(
            id=uuid.uuid4(), user_id=stable_uuid("user", user), language_code=language, word=word, normalized_word=word.casefold(),
            phonetic="", part_of_speech="", definition="", translation_vi="", added_at=now, source_fragment="", source_kind="manual",
            focus_note="", review_stage=0, successful_recalls=0, lapse_count=0, next_review_at=now, updated_at=now,
            entry_identity_key="", reading_key=""))


def test_where_a_word_was_met_is_kept_and_read_back_and_a_retry_replays(pg_engine, backbone):
    user = _account(pg_engine)
    _save_word(pg_engine, user, "harbour")
    client = _client(backbone, user=user)
    operation = op()
    body = {"operationId": operation, "reason": "from_reading", "sourceKind": "reading", "sourceId": "reading:14",
            "focus": "the harbour lights"}
    first = client.post("/api/library/vocabulary/harbour/provenance", json=body)
    assert first.status_code == 200 and first.json()["status"] == "committed"
    assert client.post("/api/library/vocabulary/harbour/provenance", json=body).json()["status"] == "replay"
    second = client.post("/api/library/vocabulary/harbour/provenance", json={**body, "operationId": op()})
    assert second.json()["id"] != first.json()["id"], "the same content under another operation is another occurrence"
    read = _client(backbone, user=user).get("/api/library/vocabulary/harbour/provenance").json()["occurrences"]
    assert len(read) == 2 and read[0]["reason"] == "from_reading" and read[0]["source"]["id"] == "reading:14"


def test_a_word_kept_from_reading_and_from_listening_shows_both_occurrences_scoped_to_the_account(pg_engine, backbone):
    owner = _account(pg_engine)
    stranger = _account(pg_engine)
    _save_word(pg_engine, owner, "galaxy")
    _save_word(pg_engine, stranger, "galaxy")
    client = _client(backbone, user=owner)
    reading = {"operationId": op(), "reason": "from_reading", "sourceKind": "reading", "sourceId": "article:734b", "focus": "A galaxy turns."}
    listening = {"operationId": op(), "reason": "from_listening", "sourceKind": "listening", "sourceId": "media:upload-abc123",
                 "sourceRevision": "seg-0003", "focus": "A galaxy is a city of stars."}
    assert client.post("/api/library/vocabulary/galaxy/provenance", json=reading).status_code == 200
    assert client.post("/api/library/vocabulary/galaxy/provenance", json=listening).status_code == 200
    read = _client(backbone, user=owner).get("/api/library/vocabulary/galaxy/provenance").json()["occurrences"]
    assert [row["source"]["kind"] for row in read] == ["reading", "listening"]
    assert read[1]["source"] == {"kind": "listening", "id": "media:upload-abc123", "revision": "seg-0003"}
    assert read[1]["focus"] == "A galaxy is a city of stars."
    # Another account's own keep of the same word never sees the owner's personal media id.
    assert _client(backbone, user=stranger).get("/api/library/vocabulary/galaxy/provenance").json()["occurrences"] == []
    # And another learning language of the owner does not read it either.
    assert _client(backbone, user=owner, language="zh").get("/api/library/vocabulary/galaxy/provenance").status_code == 404


def test_provenance_refuses_other_accounts_words_unknown_words_and_unknown_reasons(pg_engine, backbone):
    owner = _account(pg_engine)
    _save_word(pg_engine, owner, "lantern")
    stranger = _client(backbone, user=_account(pg_engine))
    body = {"operationId": op(), "reason": "looked_up"}
    assert stranger.post("/api/library/vocabulary/lantern/provenance", json=body).status_code == 404
    client = _client(backbone, user=owner)
    assert client.post("/api/library/vocabulary/nothing/provenance", json=body).status_code == 404
    assert client.post("/api/library/vocabulary/lantern/provenance", json={**body, "operationId": op(), "reason": "because"}).status_code == 422
    assert _client(backbone, user=owner, language="zh").post("/api/library/vocabulary/lantern/provenance", json={**body, "operationId": op()}).status_code == 404


def test_the_real_app_serves_the_new_routes_and_the_vocabulary_routes_are_undisturbed():
    import app as app_module

    paths = set(app_module.app.openapi()["paths"])
    for wanted in ("/api/works", "/api/conversations/{key}/turns", "/api/annotations/{content_id}", "/api/imports/{import_id}",
                   "/api/responses/{key}", "/api/library/vocabulary/{word}/provenance", "/api/continue/{content_id}",
                   "/api/account-settings", "/api/essays/{essay_id}/review/refresh", "/api/essays/{essay_id}/review/history"):
        assert wanted in paths, wanted
    work_api.configure_work(AccountBackbone(DISABLED))
    client = TestClient(app_module.app)
    assert client.get("/api/library/vocabulary/harbour/provenance").status_code == 503
    assert client.get("/api/account-backbone").json() == {"state": "disabled"}


# -- a deleted import is erased, not hidden (implementation review P1-2) ---------------------------------


def test_deleting_an_import_drops_its_content_from_the_stored_row_and_the_work_is_no_longer_served(pg_engine, backbone):
    user = _account(pg_engine)
    client = _client(backbone, user=user)
    client_id = str(uuid.uuid4())
    secret = "A private paragraph the learner erased."
    client.put(f"/api/imports/{client_id}", json={"operationId": op(), "expectedVersion": 0, "form": "text",
                                                  "title": "Diary", "text": secret})
    ident = str(stable_uuid("work", str(stable_uuid("user", user)), _incarnation(pg_engine, user), "en", "imported", client_id))
    assert client.get(f"/api/works/{ident}").json()["work"]["payload"]["text"] == secret
    operation = op()
    removed = client.delete(f"/api/imports/{client_id}", params={"operationId": operation, "expectedVersion": 1})
    assert removed.status_code == 200
    with pg_engine.connect() as connection:
        stored = connection.execute(text("SELECT payload::text, lifecycle FROM works WHERE id=:w"), {"w": ident}).one()
    assert stored[1] == "deleted"
    for content in (secret, "Diary"):
        assert content not in stored[0], f"the stored row still holds {content!r}"
    assert client.get(f"/api/works/{ident}").status_code == 404, "a deleted work is not served"
    assert client.get("/api/imports").json()["imports"] == [] and client.get(f"/api/imports/{client_id}").status_code == 404
    assert secret not in repr(client.get("/api/works", params={"kind": "imported"}).json())
    replay = client.delete(f"/api/imports/{client_id}", params={"operationId": operation, "expectedVersion": 1})
    assert replay.status_code == 200 and replay.json()["status"] == "replay", "a lost acknowledgment of the delete replays"


def test_two_imports_created_at_the_limit_at_once_give_exactly_twenty(pg_engine, backbone):
    """Implementation review P3-4 / proposal I12: the bound is counted where no other creation can interleave."""
    client = _client(backbone, user=_account(pg_engine))
    for number in range(19):
        assert client.put(f"/api/imports/{uuid.uuid4()}", json={"operationId": op(), "expectedVersion": 0, "form": "text", "title": f"T{number}", "text": "x"}).status_code == 200
    results = []
    barrier = threading.Barrier(2)

    def create():
        barrier.wait()
        results.append(client.put(f"/api/imports/{uuid.uuid4()}", json={"operationId": op(), "expectedVersion": 0, "form": "text", "title": "T", "text": "x"}).status_code)

    threads = [threading.Thread(target=contextvars.copy_context().run, args=(create,)) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(results) == [200, 422], results
    assert len(client.get("/api/imports", params={"limit": 50}).json()["imports"]) == 20


# -- a removal holds across devices (runtime acceptance item 3) ------------------------------------------------


def _hl(name):
    return {"id": name, "segment": f"p{name}", "sentence": f"Sentence {name}.", "at": ""}


def test_a_removed_note_or_highlight_is_remembered_by_the_server_and_cannot_come_back(pg_engine, backbone):
    client = _client(backbone, user=_account(pg_engine))
    note = {"id": "n1", "key": "k", "type": "question", "text": "Why?", "at": ""}
    assert _annotate(client, "reading:t1", 0, [_hl("h1"), _hl("h2")], [note]).status_code == 200
    assert client.get("/api/annotations/reading:t1").json()["annotation"]["tombstones"] == []
    assert _annotate(client, "reading:t1", 1, [_hl("h1")], []).status_code == 200
    current = client.get("/api/annotations/reading:t1").json()["annotation"]
    assert sorted(current["tombstones"]) == ["h2", "n1"] and current["version"] == 2
    back = _annotate(client, "reading:t1", 2, [_hl("h1"), _hl("h2")], [])
    assert back.status_code == 422 and back.json()["detail"]["category"] == "annotation_tombstoned"
    assert back.json()["detail"]["context"]["ids"] == ["h2"]
    assert [h["id"] for h in client.get("/api/annotations/reading:t1").json()["annotation"]["highlights"]] == ["h1"]
    assert _annotate(client, "reading:t1", 2, [_hl("h1"), _hl("h3")], []).status_code == 200, "a NEW item is fine"


def test_an_older_device_cannot_write_over_a_removal_it_has_not_seen(pg_engine, backbone):
    user = _account(pg_engine)
    one, two = _client(backbone, user=user), _client(backbone, user=user)
    _annotate(one, "reading:t2", 0, [_hl("h1"), _hl("h2")])
    _annotate(one, "reading:t2", 1, [_hl("h1")])  # device one removed h2
    stale = _annotate(two, "reading:t2", 1, [_hl("h1"), _hl("h2"), _hl("h3")])  # device two still holds h2 at version 1
    assert stale.status_code == 409
    server = stale.json()["detail"]["context"]["serverPayload"]
    assert server["tombstones"] == ["h2"] and [h["id"] for h in server["highlights"]] == ["h1"], "nothing was merged"
    merged = _annotate(two, "reading:t2", 2, [_hl("h1"), _hl("h3")])
    assert merged.status_code == 200
    assert {h["id"] for h in one.get("/api/annotations/reading:t2").json()["annotation"]["highlights"]} == {"h1", "h3"}


def test_clearing_remembers_everything_it_removed_and_a_replayed_removal_is_not_undone(pg_engine, backbone):
    client = _client(backbone, user=_account(pg_engine))
    _annotate(client, "reading:t3", 0, [_hl("h1"), _hl("h2")], [{"id": "n1", "key": "k", "type": "factual", "text": "x", "at": ""}])
    operation = op()
    body = {"operationId": operation, "expectedVersion": 1, "highlights": [_hl("h1")], "notes": []}
    assert client.put("/api/annotations/reading:t3", json=body).json()["status"] == "committed"
    _annotate(client, "reading:t3", 2, [_hl("h1"), _hl("h4")])
    replay = client.put("/api/annotations/reading:t3", json=body)
    assert replay.status_code == 200 and replay.json()["status"] == "replay", "a lost acknowledgment still replays"
    cleared = _annotate(client, "reading:t3", 3, cleared=True)
    assert cleared.status_code == 200
    read = client.get("/api/annotations/reading:t3").json()["annotation"]
    assert read["cleared"] is True and set(read["tombstones"]) == {"h1", "h2", "h4", "n1"}


def test_the_tombstone_list_is_bounded_and_keeps_the_newest(pg_engine, backbone, monkeypatch):
    monkeypatch.setattr(account_records_api, "MAX_TOMBSTONES", 3)
    client = _client(backbone, user=_account(pg_engine))
    items = [_hl(f"h{n}") for n in range(6)]
    _annotate(client, "reading:t4", 0, items)
    version = 1
    for _ in range(5):
        items = items[1:]
        assert _annotate(client, "reading:t4", version, items).status_code == 200
        version += 1
    assert client.get("/api/annotations/reading:t4").json()["annotation"]["tombstones"] == ["h2", "h3", "h4"]
