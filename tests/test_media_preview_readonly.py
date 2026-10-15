"""A held (not published) shared media id never receives learner state, whoever sends it (D-210).

The admin preview of a held import (D-206) opens the real learner player. The player is not allowed to
leave anything of the administrator behind on the item: the client sends no write from a preview, and
every server route that stores learner state against a media id refuses an id that is not
published-and-visible to the learner. A published shared item and the learner's own personal import
keep writing; another learner's personal import and an unknown id are not this rule's business (an
unknown id is a curated lesson or a text, and keeps working).
"""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.test_media_lifecycle import _entry
from writing_coach import account_records_api, library_api, listening_api
from writing_coach.core.request_context import LANGUAGE_CODE_CTX, USER_KEY_CTX
from writing_coach.media_library_store import OWNER_FIELD, owner_token
from writing_coach.media_segmentation import Cue
from writing_coach.media_transcript_pipeline import build_transcript, lesson_payload

HELD = "held-preview-one"
HELD_UPLOAD = "upload-held-two"
PUBLISHED = "published-one"
MINE = "upload-mine-one"
THEIRS = "upload-theirs-one"
LINE = "Today we are walking through the city."
USER = "learner-preview-test"


def _with_lesson(entry):
    transcript = build_transcript(entry.media_id, "en", [Cue(0, 4000, LINE)])
    return replace(entry, lesson={"payload": lesson_payload(entry, transcript, "generated_asr", 4000)})


def _shared(media_id, status):
    return _with_lesson(replace(_entry(media_id), status=status))


def _personal(media_id, owner):
    entry = _entry(media_id, library="personal")
    entry = replace(entry, source={**entry.source, OWNER_FIELD: owner_token(owner)})
    return _with_lesson(entry)


class MemoryStore:
    def __init__(self, entries):
        self.entries = {entry.media_id: entry for entry in entries}

    def get(self, media_id):
        return self.entries.get(media_id)


class Recorder:
    """Stands in for every repository a route would write through, and remembers each write."""

    def __init__(self):
        self.writes: list[tuple[str, object]] = []

    # library_api
    def set_place(self, **kwargs):
        self.writes.append(("continue", kwargs["source_id"]))
        return {"status": "written"}

    def keep(self, **kwargs):
        self.writes.append(("keep", kwargs["source_id"]))
        return {"id": "item-1"}

    # listening progress
    def save_listening_progress_record(self, values):
        self.writes.append(("dictation", values["asset_id"]))
        return dict(values)

    def save_shadowing_progress_record(self, values):
        self.writes.append(("shadowing", values["asset_id"]))
        return dict(values)

    # account backbone
    @property
    def work(self):
        recorder = self

        class Work:
            def get_work(self, scope, ident):
                return None

            def commit_mutation(self, **kwargs):
                recorder.writes.append(("work", kwargs["kind"]))
                return {"status": "committed", "version": 1}

        return Work()

    @property
    def provenance(self):
        recorder = self

        class Provenance:
            def attach_occurrence(self, **kwargs):
                recorder.writes.append(("provenance", kwargs["source"].get("id", "")))
                return {"status": "committed"}

        return Provenance()


@pytest.fixture()
def world(monkeypatch):
    recorder = Recorder()
    store = MemoryStore([
        _shared(HELD, "review"),
        _shared(HELD_UPLOAD, "unpublished"),
        _shared(PUBLISHED, "published"),
        _personal(MINE, USER),
        _personal(THEIRS, "somebody-else"),
    ])
    user_token = USER_KEY_CTX.set(USER)
    language_token = LANGUAGE_CODE_CTX.set("en")
    monkeypatch.setattr(listening_api, "_media_store", store)
    listening_api.configure_listening_progress(recorder)
    library_api.configure_library(lambda: recorder)
    monkeypatch.setattr(account_records_api.work_api, "_scope",
                        lambda: SimpleNamespace(account="a", incarnation=1, language="en"))
    monkeypatch.setattr(account_records_api, "_backbone", lambda: recorder)
    monkeypatch.setattr(account_records_api, "_text_import_deleted", lambda scope, content_id: False)
    monkeypatch.setattr(account_records_api, "_saved_word_id", lambda scope, word: "saved-1")
    app = FastAPI()
    app.include_router(listening_api.router)
    app.include_router(library_api.router)
    app.include_router(library_api.continue_router)
    app.include_router(account_records_api.router)
    yield TestClient(app), recorder
    LANGUAGE_CODE_CTX.reset(language_token)
    USER_KEY_CTX.reset(user_token)
    listening_api.configure_listening_progress(None)
    library_api.configure_library(None)


def _forms(media_id):
    """Every spelling a client gives one media id: bare, the content id, the upload and preview routes."""
    return [media_id, f"media:{media_id}", f"media:preview:{media_id}", f"preview:{media_id}", f"media:upload:{media_id}"]


# One call per learner-state route that names a media id. Each returns the response.
def _continue(client, cid):
    return client.put(f"/api/continue/{cid}", json={"kind": "listening", "place": {"index": 1, "total": 1, "within": 20}})


def _annotations(client, cid):
    return client.put(f"/api/annotations/{cid}", json={
        "operationId": "op-00000001", "expectedVersion": 0,
        "highlights": [{"id": "h1", "segment": "s1", "sentence": LINE, "at": ""}], "notes": [],
    })


def _response(client, cid):
    return client.put("/api/responses/react:one", json={
        "operationId": "op-00000002", "expectedVersion": 0, "mode": "react", "answer": "x",
        "sourceKind": "media", "sourceId": cid,
    })


def _provenance(client, cid):
    return client.post("/api/library/vocabulary/harbour/provenance", json={
        "operationId": "op-00000003", "reason": "from_listening", "sourceKind": "listening", "sourceId": cid,
    })


def _keep(client, cid):
    return client.post("/api/library/items", json={"kind": "media", "source_id": cid})


def _segment(bare):
    """The id of the entry's real first line: progress is only accepted for a line the app serves."""
    return listening_api._media_store.get(bare).lesson["payload"]["transcript"]["segments"][0]["segment_id"]


def _dictation(client, cid):
    bare = cid.split(":")[-1]
    return client.post("/api/listening/progress", json={
        "asset_id": bare, "segment_id": _segment(bare), "presentation": "checked", "last_answer": LINE,
        "checked_attempt_count": 1,
    })


def _shadowing(client, cid):
    bare = cid.split(":")[-1]
    return client.post("/api/listening/shadowing-progress", json={"asset_id": bare, "segment_id": _segment(bare), "completed_rounds": 1})


WRITERS = {
    "continue": _continue,
    "annotations": _annotations,
    "response": _response,
    "provenance": _provenance,
    "keep": _keep,
}
PROGRESS_WRITERS = {"dictation": _dictation, "shadowing": _shadowing}


@pytest.mark.parametrize("name", sorted(WRITERS))
@pytest.mark.parametrize("media_id", [HELD, HELD_UPLOAD])
def test_a_held_shared_id_receives_no_state_in_any_spelling(world, name, media_id):
    client, recorder = world
    for cid in _forms(media_id):
        response = WRITERS[name](client, cid)
        assert response.status_code == 404, (name, cid, response.text)
        assert "media_not_available" in response.text, response.text
    assert recorder.writes == [], f"{name} wrote for a held id: {recorder.writes}"


@pytest.mark.parametrize("name", sorted(PROGRESS_WRITERS))
def test_practice_progress_for_a_held_id_is_refused_and_unwritten(world, name):
    client, recorder = world
    response = PROGRESS_WRITERS[name](client, HELD)
    assert response.status_code == 404, response.text
    assert recorder.writes == []


@pytest.mark.parametrize("name", sorted(WRITERS))
def test_another_learners_personal_import_receives_no_state(world, name):
    client, recorder = world
    for cid in _forms(THEIRS):
        assert WRITERS[name](client, cid).status_code == 404
    assert recorder.writes == []


@pytest.mark.parametrize("name", sorted(WRITERS))
def test_a_published_shared_item_still_writes(world, name):
    client, recorder = world
    response = WRITERS[name](client, f"media:{PUBLISHED}")
    assert response.status_code == 200, response.text
    assert len(recorder.writes) == 1


@pytest.mark.parametrize("name", sorted(WRITERS))
def test_the_learners_own_personal_import_still_writes(world, name):
    client, recorder = world
    response = WRITERS[name](client, f"media:upload:{MINE}")
    assert response.status_code == 200, response.text
    assert len(recorder.writes) == 1


def test_a_published_item_still_saves_practice_progress(world):
    client, recorder = world
    assert _dictation(client, PUBLISHED).status_code == 200
    assert _shadowing(client, PUBLISHED).status_code == 200
    assert [kind for kind, _ in recorder.writes] == ["dictation", "shadowing"]


def test_the_learners_own_personal_import_still_saves_practice_progress(world):
    client, recorder = world
    assert _dictation(client, MINE).status_code == 200
    assert [kind for kind, _ in recorder.writes] == ["dictation"]


# --- Cost and failure behaviour of the guard (review #220: P2-3, P2-5) ----------------------------


class CountingStore(MemoryStore):
    def __init__(self, entries, issue=""):
        super().__init__(entries)
        self.reads = 0
        self.last_read_issue = issue

    def get(self, media_id):
        self.reads += 1
        if self.last_read_issue in {"index_corrupt", "index_unreadable"}:
            return None  # what FileMediaLibraryStore answers: an empty index and the reason
        return super().get(media_id)

    def lookup(self, media_id):
        """One read, the entry and the read's own issue together (FileMediaLibraryStore.lookup)."""
        issue = self.last_read_issue
        return self.get(media_id), issue


def _counting(monkeypatch, issue=""):
    store = CountingStore(list(listening_api._media_store.entries.values()), issue)
    monkeypatch.setattr(listening_api, "_media_store", store)
    return store


@pytest.mark.parametrize("cid", [HELD, f"media:{HELD}", f"media:preview:{HELD}", f"preview:{HELD}",
                                  f"media:upload:{HELD_UPLOAD}", f"media:{PUBLISHED}", f"media:upload:{MINE}",
                                  f"media:{THEIRS}"])
def test_the_guard_reads_the_store_at_most_once_per_write(world, monkeypatch, cid):
    store = _counting(monkeypatch)
    listening_api.media_state_writable(cid)
    assert store.reads <= 1, (cid, store.reads)


@pytest.mark.parametrize("cid", ["", "   ", "has space", "x" * 300, "-leading-dash", "semi;colon"])
def test_an_id_the_store_could_never_hold_costs_no_store_read(world, monkeypatch, cid):
    store = _counting(monkeypatch)
    assert listening_api.media_state_writable(cid) is True
    assert store.reads == 0


@pytest.mark.parametrize("cid", ["reading:14", "book:b1:c2", "text:9f3a", "url:abc123", "conversation:x"])
def test_any_id_the_store_could_hold_is_media_shaped_and_costs_one_read(world, monkeypatch, cid):
    """The store allows ':' in an id (media_library_store._ID), so `reading:14` is one it could hold: one read, no more."""
    store = _counting(monkeypatch)
    assert listening_api.media_state_writable(cid) is True
    assert store.reads == 1


def test_a_stored_id_containing_a_colon_is_guarded(world, monkeypatch):
    odd = "odd:held-id"
    store = _counting(monkeypatch)
    store.entries[odd] = _shared(odd, "review")
    assert listening_api.media_state_writable(odd) is False
    assert listening_api.media_state_writable(f"media:{odd}") is False
    assert listening_api.media_state_writable(f"media:preview:{odd}") is False


def test_a_read_that_another_request_interleaves_with_cannot_make_a_corrupt_index_look_empty(tmp_path, monkeypatch):
    """The issue travels with the read's own result, not through an attribute every read resets."""
    from writing_coach.media_library_store import FileMediaLibraryStore

    store = FileMediaLibraryStore(tmp_path)
    store.upsert(_shared(PUBLISHED, "published"))
    (tmp_path / "index.json").write_text("{not json", encoding="utf-8")
    assert store.lookup(PUBLISHED) == (None, "index_corrupt")

    original = FileMediaLibraryStore._read_checked

    def interleaved(self):
        result = original(self)
        self.last_read_issue = ""  # a concurrent request's read finished here and reset the shared attribute
        return result

    monkeypatch.setattr(FileMediaLibraryStore, "_read_checked", interleaved)
    monkeypatch.setattr(listening_api, "_media_store", store)
    assert listening_api.media_state_writable(f"media:{PUBLISHED}") is False
    assert listening_api.media_state_writable("reading:14") is False  # store-shaped, unverifiable: refused
    # A healthy index with no such entry is a plain "no entry", and a missing index is a fresh start.
    (tmp_path / "index.json").unlink()
    assert store.lookup("whatever") == (None, "index_missing")
    assert listening_api.media_state_writable("media:curated-lesson-1") is True


@pytest.mark.parametrize("issue", ["index_corrupt", "index_unreadable"])
def test_an_unreadable_index_refuses_a_media_shaped_write_and_spares_the_rest(world, monkeypatch, issue):
    client, recorder = world
    _counting(monkeypatch, issue)
    # The store cannot say whether the item is held: nothing is written against it.
    assert _continue(client, f"media:preview:{HELD}").status_code == 404
    assert _continue(client, f"media:{PUBLISHED}").status_code == 404
    assert recorder.writes == []
    # An id the store could never hold is not this rule's business, whatever state the index is in.
    assert listening_api.media_state_writable("") is True
    assert listening_api.media_state_writable("has space") is True


def test_a_missing_index_is_a_fresh_start_not_a_failure(world, monkeypatch):
    client, recorder = world
    _counting(monkeypatch, "index_missing")
    assert _continue(client, "media:curated-lesson-1").status_code == 200


@pytest.mark.parametrize("name", sorted(WRITERS))
def test_an_id_no_media_store_names_keeps_writing(world, name):
    """A curated lesson, a text, a book: not stored media, so this rule says nothing about them."""
    client, recorder = world
    cid = "reading:14" if name != "continue" else "media:curated-lesson-1"
    response = WRITERS[name](client, cid)
    assert response.status_code == 200, response.text
    assert len(recorder.writes) == 1


def test_without_a_media_store_nothing_changes(world, monkeypatch):
    client, recorder = world
    monkeypatch.setattr(listening_api, "_media_store", None)
    assert _continue(client, f"media:{HELD}").status_code == 200
    assert len(recorder.writes) == 1


def test_the_rule_itself_in_every_spelling(world):
    for cid in _forms(HELD) + _forms(HELD_UPLOAD) + _forms(THEIRS):
        assert listening_api.media_state_writable(cid) is False, cid
    for cid in _forms(PUBLISHED) + [f"media:upload:{MINE}", MINE, "reading:14", "", "book:b1:c2"]:
        assert listening_api.media_state_writable(cid) is True, cid
