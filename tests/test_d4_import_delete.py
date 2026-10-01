"""Deleting an import (D-107): a content-free tombstone that devices can learn from, no resurrection, and the
owned uploaded files removed with the import - only for their owner, in their language, never anyone else's.

Real PostgreSQL (ORENA_TEST_POSTGRES_URL) for the account records; a temporary file store for the media.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import bindparam, inspect, text

from test_d4_account_records import _account, _client, op  # noqa: F401  (shared helpers)
from writing_coach import media_library_api
from writing_coach.account_backbone import build_backbone
from writing_coach.book_asset_store import FilesystemBookAssetStore
from writing_coach.media_library_store import FileMediaLibraryStore, MediaLibraryEntry, owner_token
from writing_coach.persistence import deletion_enumeration as enumeration


@pytest.fixture
def backbone(pg_engine):
    built = build_backbone(pg_engine, inspect(pg_engine).get_table_names(), env={"ORENA_ACCOUNT_BACKBONE": "on"})
    assert built.is_active
    return built


def _entry(token: str, *, owner: str | None, language: str = "en", library: str = "personal") -> MediaLibraryEntry:
    source = {"provider": "upload", "type": "upload", "provenance_url": "", "license": "x", "review_status": "x", "imported_by": "learner"}
    if owner is not None:
        source["owner"] = owner_token(owner)
    return MediaLibraryEntry(
        media_id=f"upload-{token}", media_type="audio", provider="upload", provider_media_id=token, canonical_url="",
        playback={"provider": "orena", "kind": "audio", "url": f"/api/media/files/media/{token}/original.wav"},
        title="Mine", thumbnail={"kind": "asset", "ref": f"media/{token}/thumbnail.jpg"}, duration_ms=2000,
        language=language, level="", creator="", source=source, library=library,
        created_at="2026-10-01T00:00:00Z", lesson=None,
    )


@pytest.fixture
def media(monkeypatch, tmp_path: Path):
    store = FileMediaLibraryStore(tmp_path / "library")
    assets = FilesystemBookAssetStore(tmp_path / "assets")
    monkeypatch.setattr(media_library_api, "_store", store)
    monkeypatch.setattr(media_library_api, "_asset_store", assets)
    monkeypatch.setattr(media_library_api, "_importer", object())

    def seed(token, *, owner, language="en", library="personal"):
        assets.put(f"media/{token}/original.wav", b"RIFF" + token.encode())
        assets.put(f"media/{token}/thumbnail.jpg", b"jpeg")
        assets.put(f"media/{token}/transcript.json", b"{}")
        store.upsert(_entry(token, owner=owner, language=language, library=library))
        return f"upload-{token}"

    return store, assets, seed


def _put(client, ident, **body):
    return client.put(f"/api/imports/{ident}", json={"operationId": op(), "expectedVersion": 0, **body})


def _delete(client, ident, version=1):
    return client.delete(f"/api/imports/{ident}", params={"operationId": op(), "expectedVersion": version})


def _row(engine, ident):
    with engine.connect() as connection:
        return connection.execute(text("SELECT payload, lifecycle, version FROM works WHERE kind = 'imported' AND source_id = :i"), {"i": ident}).mappings().one()


def test_a_deleted_import_leaves_a_content_free_tombstone_devices_can_read(pg_engine, backbone):
    client = _client(backbone, user=_account(pg_engine))
    text_id, link_id, file_id = (str(uuid.uuid4()) for _ in range(3))
    assert _put(client, text_id, form="text", title="Diary", text="private words").status_code == 200
    assert _put(client, link_id, form="url", title="A talk", url="https://example.test/secret?x=1", kind="video").status_code == 200
    assert _put(client, file_id, form="upload", title="My file", mediaId="upload-" + "d" * 32, kind="audio").status_code == 200
    for ident in (text_id, link_id, file_id):
        assert _delete(client, ident).status_code == 200
    rows = {ident: _row(pg_engine, ident) for ident in (text_id, link_id, file_id)}
    assert all(row["lifecycle"] == "deleted" for row in rows.values())
    stored = json.dumps([row["payload"] for row in rows.values()])
    for needle in ("Diary", "private words", "A talk", "example.test", "My file"):
        assert needle not in stored, "the stored tombstone holds no content"
    listed = client.get("/api/imports").json()
    assert listed["imports"] == []
    refs = {item["id"]: item["ref"] for item in listed["deleted"]}
    assert set(refs) == {f"text:{text_id}", f"url:{link_id}", f"upload:{file_id}"}
    assert refs[f"text:{text_id}"] == ""
    assert refs[f"url:{link_id}"] == hashlib.sha256(b"orena.import-ref:url:https://example.test/secret?x=1").hexdigest()
    assert refs[f"upload:{file_id}"] == hashlib.sha256(("orena.import-ref:upload:upload-" + "d" * 32).encode()).hexdigest()
    other = _client(backbone, user=_account(pg_engine))
    assert other.get("/api/imports").json()["deleted"] == []
    assert _client(backbone, user=client._identity[1], language="zh").get("/api/imports").json()["deleted"] == []


def test_a_deleted_import_cannot_be_recreated_or_revived_by_a_stale_device(pg_engine, backbone):
    client = _client(backbone, user=_account(pg_engine))
    ident = str(uuid.uuid4())
    assert _put(client, ident, form="text", title="T", text="x").status_code == 200
    assert _delete(client, ident).status_code == 200
    recreate = _put(client, ident, form="text", title="T", text="x")
    assert recreate.status_code in (409, 422), "the id of a deleted import is never reused"
    stale = client.put(f"/api/imports/{ident}", json={"operationId": op(), "expectedVersion": 1, "form": "text", "title": "T2", "text": "edited"})
    assert stale.status_code in (409, 422), "a device that has not seen the deletion cannot edit it back"
    current = client.put(f"/api/imports/{ident}", json={"operationId": op(), "expectedVersion": 2, "form": "text", "title": "T2", "text": "edited"})
    assert current.status_code >= 400, "even against the right version a deleted import stays deleted"
    assert _row(pg_engine, ident)["lifecycle"] == "deleted" and "text" not in _row(pg_engine, ident)["payload"]
    assert client.get(f"/api/imports/{ident}").status_code == 404
    assert client.get("/api/imports").json()["imports"] == []


def test_deleting_an_upload_import_removes_the_owned_files_and_the_store_entry(pg_engine, backbone, media):
    store, assets, seed = media
    user = _account(pg_engine)
    token = "1" * 32
    media_id = seed(token, owner=user)
    client = _client(backbone, user=user)
    ident = str(uuid.uuid4())
    assert _put(client, ident, form="upload", title="My file", mediaId=media_id, kind="audio").status_code == 200
    assert store.get(media_id) is not None and assets.exists(f"media/{token}/original.wav")
    removed = _delete(client, ident)
    assert removed.status_code == 200 and removed.json()["mediaDeleted"] is True
    assert store.get(media_id) is None
    for name in ("original.wav", "thumbnail.jpg", "transcript.json"):
        assert not assets.exists(f"media/{token}/{name}"), name
    assert _delete(client, ident, version=2).status_code in (200, 409), "a retried request does nothing further"


def test_an_import_naming_someone_elses_or_another_languages_media_deletes_none_of_it(pg_engine, backbone, media):
    store, assets, seed = media
    owner, thief = _account(pg_engine), _account(pg_engine)
    others_id = seed("2" * 32, owner=owner)
    zh_id = seed("3" * 32, owner=thief, language="zh")
    shared_id = seed("4" * 32, owner=None, library="shared")
    client = _client(backbone, user=thief)
    for media_id in (others_id, zh_id, shared_id, "upload-" + "9" * 32):
        ident = str(uuid.uuid4())
        assert _put(client, ident, form="upload", title="x", mediaId=media_id).status_code == 200
        done = _delete(client, ident)
        assert done.status_code == 200 and done.json()["mediaDeleted"] is False, media_id
    for media_id, token in ((others_id, "2" * 32), (zh_id, "3" * 32), (shared_id, "4" * 32)):
        assert store.get(media_id) is not None and assets.exists(f"media/{token}/original.wav"), media_id


def test_a_link_import_deletes_only_orenas_record(pg_engine, backbone, media):
    store, assets, seed = media
    user = _account(pg_engine)
    media_id = seed("5" * 32, owner=user)
    client = _client(backbone, user=user)
    ident = str(uuid.uuid4())
    assert _put(client, ident, form="url", title="A talk", url="https://example.test/v", mediaId=media_id).status_code == 200
    done = _delete(client, ident)
    assert done.status_code == 200 and done.json()["mediaDeleted"] is None
    assert store.get(media_id) is not None, "a link import never removes media"


def test_the_media_route_and_the_account_remover_check_ownership(monkeypatch, media):
    store, assets, seed = media
    caller = {"user": "alice", "language": "en"}
    monkeypatch.setattr(media_library_api, "current_user_key", lambda: caller["user"])
    monkeypatch.setattr(media_library_api, "current_language_code", lambda: caller["language"])
    app = FastAPI()
    app.include_router(media_library_api.router)
    client = TestClient(app)
    mine = seed("6" * 32, owner="alice")
    other = seed("7" * 32, owner="bob")
    caller["language"] = "zh"
    assert client.delete(f"/api/media/my/{mine}").status_code == 404, "another language: not found, nothing removed"
    caller["language"] = "en"
    assert client.delete(f"/api/media/my/{other}").status_code == 404
    assert client.delete(f"/api/media/my/{mine}").json() == {"deleted": True}
    assert client.delete(f"/api/media/my/{mine}").status_code == 404
    assert store.get(other) is not None and assets.exists(f"media/{'7' * 32}/original.wav")
    # The account-deletion remover takes every language of one account, and only that account.
    seed("8" * 32, owner="alice", language="zh")
    seed("a" * 32, owner="alice")
    assert media_library_api.delete_all_owned_media("alice") == 2
    assert not assets.exists(f"media/{'8' * 32}/original.wav") and not assets.exists(f"media/{'a' * 32}/thumbnail.jpg")
    assert store.get(other) is not None


def test_the_file_based_media_store_is_in_the_deletion_enumeration():
    (media_store,) = [item for item in enumeration.FILE_STORES if item["name"] == "media_library"]
    for dotted in (media_store["remove_one"], media_store["remove_account"]):
        module, _, name = dotted.rpartition(".")
        assert callable(getattr(__import__(module, fromlist=[name]), name)), dotted


def test_two_records_naming_one_file_keep_it_until_the_last_is_deleted(pg_engine, backbone, media):
    store, assets, seed = media
    user = _account(pg_engine)
    media_id = seed("b" * 32, owner=user)
    client = _client(backbone, user=user)
    first, second = str(uuid.uuid4()), str(uuid.uuid4())
    assert _put(client, first, form="upload", title="Kept on a phone", mediaId=media_id).status_code == 200
    assert _put(client, second, form="upload", title="Kept on a laptop", mediaId=media_id).status_code == 200
    one = _delete(client, first)
    assert one.status_code == 200 and one.json()["mediaDeleted"] is False
    assert store.get(media_id) is not None and assets.exists(f"media/{'b' * 32}/original.wav"), "another live import still uses it"
    last = _delete(client, second)
    assert last.status_code == 200 and last.json()["mediaDeleted"] is True
    assert store.get(media_id) is None and not assets.exists(f"media/{'b' * 32}/original.wav")


def test_a_corrupt_media_index_refuses_writes_and_deletes_instead_of_rewriting_from_empty(media, tmp_path):
    from writing_coach.media_library_store import MediaIndexUnavailable

    store, assets, seed = media
    mine = seed("c" * 32, owner="alice")
    others = seed("d" * 32, owner="bob")
    index = tmp_path / "library" / "index.json"
    assert store.get(others) is not None
    index.write_text('{"entries": [truncated', encoding="utf-8")
    before = index.read_bytes()
    assert store.get(mine) is None and store.list(library="personal", status=None) == [], "reads answer not-found"
    with pytest.raises(MediaIndexUnavailable):
        store.upsert(_entry("e" * 32, owner="alice"))
    with pytest.raises(MediaIndexUnavailable):
        store.delete(mine)
    assert index.read_bytes() == before, "nothing was rewritten: the other accounts' entries are recoverable"
    # a learner's delete through the media API refuses too (an untrusted index is not "not found")
    with pytest.raises(MediaIndexUnavailable):
        media_library_api.delete_owned_media(mine, user_key="alice", language="en")
    assert assets.exists(f"media/{'c' * 32}/original.wav") and assets.exists(f"media/{'d' * 32}/original.wav")
    # an index that does not exist yet is a fresh start, not corruption
    fresh = FileMediaLibraryStore(tmp_path / "other")
    fresh.upsert(_entry("f" * 32, owner="alice"))
    assert fresh.get("upload-" + "f" * 32) is not None


# --- review f8f5c91: recoverable, complete, never taking another device's file ---------------------------


def test_a_failed_file_removal_leaves_the_entry_and_a_marker_and_a_retry_completes_it(pg_engine, backbone, media, monkeypatch):
    store, assets, seed = media
    user = _account(pg_engine)
    token = "e" * 32
    media_id = seed(token, owner=user)
    client = _client(backbone, user=user)
    ident = str(uuid.uuid4())
    assert _put(client, ident, form="upload", title="My file", mediaId=media_id).status_code == 200
    real = assets.delete_prefix

    def failing(prefix):
        raise OSError("disk went away")

    monkeypatch.setattr(assets, "delete_prefix", failing)
    first = _delete(client, ident)
    assert first.status_code == 200 and first.json()["mediaDeleted"] is False
    assert store.get(media_id) is not None, "the index entry stays, so the bytes are never orphaned"
    assert _row(pg_engine, ident)["payload"].get("mediaPending") == media_id, "the tombstone keeps the opaque id until the files are gone"
    monkeypatch.setattr(assets, "delete_prefix", real)
    retry = _delete(client, ident, version=1)  # a retry, even with a stale version and a new operation id
    assert retry.status_code == 200 and retry.json()["mediaDeleted"] is True
    assert store.get(media_id) is None and not assets.exists(f"media/{token}/original.wav")
    assert "mediaPending" not in _row(pg_engine, ident)["payload"], "the marker clears once the files are confirmed gone"


def test_a_later_list_read_completes_a_removal_that_could_not_be_done(pg_engine, backbone, media, tmp_path):
    store, assets, seed = media
    user = _account(pg_engine)
    token = "f" * 32
    media_id = seed(token, owner=user)
    client = _client(backbone, user=user)
    ident = str(uuid.uuid4())
    assert _put(client, ident, form="upload", title="My file", mediaId=media_id).status_code == 200
    index = tmp_path / "library" / "index.json"
    good = index.read_bytes()
    index.write_text("{corrupt", encoding="utf-8")  # the index cannot be trusted: the delete must refuse, touching nothing
    done = _delete(client, ident)
    assert done.status_code == 200 and done.json()["mediaDeleted"] is False
    assert assets.exists(f"media/{token}/original.wav"), "no file was touched while the index was untrusted"
    assert _row(pg_engine, ident)["payload"].get("mediaPending") == media_id
    index.write_bytes(good)  # repaired
    client.get("/api/imports")  # the sweep
    assert store.get(media_id) is None and not assets.exists(f"media/{token}/original.wav")
    assert "mediaPending" not in _row(pg_engine, ident)["payload"]


def test_the_deleted_list_is_complete_not_the_newest_fifty(pg_engine, backbone):
    client = _client(backbone, user=_account(pg_engine))
    ids = []
    for _ in range(60):
        ident = str(uuid.uuid4())
        assert _put(client, ident, form="text", title="T", text="x").status_code == 200
        assert _delete(client, ident).status_code == 200
        ids.append(f"text:{ident}")
    listed = client.get("/api/imports").json()["deleted"]
    assert {item["id"] for item in listed} == set(ids), "a device that was away learns every deletion it holds"


def test_the_media_route_does_not_take_a_file_another_live_import_still_names(pg_engine, backbone, media, monkeypatch):
    store, assets, seed = media
    user = _account(pg_engine)
    media_id = seed("1a" * 16, owner=user)
    monkeypatch.setattr(media_library_api, "current_user_key", lambda: user)
    monkeypatch.setattr(media_library_api, "current_language_code", lambda: "en")
    client = _client(backbone, user=user)  # also configures the account identity the route consults
    ident = str(uuid.uuid4())
    assert _put(client, ident, form="upload", title="On the laptop", mediaId=media_id).status_code == 200
    app = FastAPI()
    app.include_router(media_library_api.router)
    media_client = TestClient(app)
    from writing_coach import work_api

    work_api.configure_work(backbone, user_key=lambda: user, language=lambda: "en")
    kept = media_client.delete(f"/api/media/my/{media_id}")
    assert kept.status_code == 200 and kept.json() == {"deleted": False, "inUse": True}
    assert store.get(media_id) is not None
    assert _delete(client, ident).json()["mediaDeleted"] is True  # the last live import takes it
    # a device-only upload (no account record names it) is deleted by the route
    lone = seed("2b" * 16, owner=user)
    assert media_client.delete(f"/api/media/my/{lone}").json() == {"deleted": True}
    assert store.get(lone) is None


# --- delta check 02511cc: ordering for a re-import, a bounded sweep, an honest 503 --------------------------


def test_the_list_orders_records_so_a_device_can_tell_a_later_reimport_from_the_one_it_deleted(pg_engine, backbone):
    client = _client(backbone, user=_account(pg_engine))
    first, second = str(uuid.uuid4()), str(uuid.uuid4())
    assert _put(client, first, form="url", title="A", url="https://example.test/same").status_code == 200
    before = client.get("/api/imports").json()
    mark = before["highWater"]
    item = before["imports"][0]
    assert item["sequence"] >= 1 and mark >= item["sequence"], "the mark covers every record the device has just read"
    assert _delete(client, first).status_code == 200
    assert _put(client, second, form="url", title="A again", url="https://example.test/same").status_code == 200
    after = client.get("/api/imports").json()
    (reimport,) = after["imports"]
    assert reimport["sequence"] > mark, "a record kept after the device's last read is newer than its mark"
    assert after["highWater"] >= reimport["sequence"]
    assert any(entry["id"] == f"url:{first}" for entry in after["deleted"])


def test_a_list_read_finishes_only_a_few_owed_file_removals(pg_engine, backbone, media, monkeypatch):
    store, assets, seed = media
    user = _account(pg_engine)
    client = _client(backbone, user=user)
    real = assets.delete_prefix
    monkeypatch.setattr(assets, "delete_prefix", lambda prefix: (_ for _ in ()).throw(OSError("down")))
    idents = []
    for number in range(7):
        media_id = seed(f"{number:x}" * 32, owner=user)
        ident = str(uuid.uuid4())
        idents.append(ident)
        assert _put(client, ident, form="upload", title=f"f{number}", mediaId=media_id).status_code == 200
        assert _delete(client, ident).json()["mediaDeleted"] is False
    monkeypatch.setattr(assets, "delete_prefix", real)

    def pending():
        with pg_engine.connect() as connection:
            return connection.execute(text("SELECT count(*) FROM works WHERE kind = 'imported' AND lifecycle = 'deleted' AND payload->>'mediaPending' IS NOT NULL AND source_id IN :ids").bindparams(bindparam("ids", expanding=True)), {"ids": idents}).scalar_one()

    assert pending() == 7
    client.get("/api/imports")
    assert pending() == 2, "one read finishes at most five"
    client.get("/api/imports")
    assert pending() == 0


def test_the_media_route_answers_503_not_404_for_an_index_it_cannot_trust(media, monkeypatch, tmp_path):
    store, assets, seed = media
    monkeypatch.setattr(media_library_api, "current_user_key", lambda: "alice")
    monkeypatch.setattr(media_library_api, "current_language_code", lambda: "en")
    mine = seed("9" * 32, owner="alice")
    (tmp_path / "library" / "index.json").write_text("{corrupt", encoding="utf-8")
    app = FastAPI()
    app.include_router(media_library_api.router)
    refused = TestClient(app).delete(f"/api/media/my/{mine}")
    assert refused.status_code == 503 and refused.json()["detail"]["category"] == "media_index_unavailable"
    assert assets.exists(f"media/{'9' * 32}/original.wav"), "nothing was touched"


# --- D-108: what a deletion keeps, and a listing that is never silently limited -------------------------


def _save_word_from(engine, user, word, fragment):
    from datetime import UTC, datetime

    from sqlalchemy.orm import Session

    from writing_coach.persistence.ids import stable_uuid
    from writing_coach.persistence.models import SavedWord

    now = datetime.now(UTC)
    with Session(engine) as session, session.begin():
        session.add(SavedWord(
            id=uuid.uuid4(), user_id=stable_uuid("user", user), language_code="en", word=word, normalized_word=word.casefold(),
            phonetic="", part_of_speech="", definition="", translation_vi="", added_at=now, source_fragment=fragment,
            source_kind="reading", focus_note="", review_stage=0, successful_recalls=0, lapse_count=0, next_review_at=now,
            updated_at=now, entry_identity_key="", reading_key=""))


def _fragment(engine, user, word):
    from writing_coach.persistence.ids import stable_uuid

    with engine.connect() as connection:
        return connection.execute(text("SELECT source_fragment FROM saved_words WHERE user_id = :u AND normalized_word = :w"),
                                  {"u": stable_uuid("user", user), "w": word.casefold()}).scalar()


def test_deleting_a_text_import_stops_serving_its_notes_and_hides_the_excerpts_of_kept_words(pg_engine, backbone):
    user = _account(pg_engine)
    client = _client(backbone, user=user)
    ident = str(uuid.uuid4())
    content = f"text:{ident}"
    sentence = "The harbour lights glowed at dusk."
    assert _put(client, ident, form="text", title="Diary", text=sentence).status_code == 200
    saved = client.put(f"/api/annotations/{content}", json={"operationId": op(), "expectedVersion": 0, "cleared": False,
                       "highlights": [{"id": "h1", "segment": "p0", "sentence": sentence, "at": ""}], "notes": []})
    assert saved.status_code == 200
    _save_word_from(pg_engine, user, "harbour", sentence)
    _save_word_from(pg_engine, user, "unrelated", "from somewhere else")
    kept = client.post("/api/library/vocabulary/harbour/provenance", json={
        "operationId": op(), "reason": "from_reading", "sourceKind": "reading", "sourceId": content, "focus": sentence})
    assert kept.status_code == 200
    other = client.post("/api/library/vocabulary/unrelated/provenance", json={
        "operationId": op(), "reason": "from_reading", "sourceKind": "reading", "sourceId": "article:abc", "focus": "from somewhere else"})
    assert other.status_code == 200
    assert client.get(f"/api/annotations/{content}").status_code == 200
    assert _delete(client, ident).status_code == 200
    # notes and highlights of the deleted source are no longer served, and cannot be written back
    assert client.get(f"/api/annotations/{content}").status_code == 404
    revive = client.put(f"/api/annotations/{content}", json={"operationId": op(), "expectedVersion": 1, "cleared": False, "highlights": [], "notes": []})
    assert revive.status_code == 404
    # the saved word is kept; its source is unavailable and no excerpt of the deleted text comes back
    (occurrence,) = client.get("/api/library/vocabulary/harbour/provenance").json()["occurrences"]
    assert occurrence["availability"] == "unavailable" and occurrence["focus"] == ""
    assert occurrence["source"]["id"] == content, "the source is still named, as unavailable"
    assert not _fragment(pg_engine, user, "harbour"), "the stored sentence of the word is gone from its row"
    # a word met somewhere else keeps its sentence and its source
    (kept_other,) = client.get("/api/library/vocabulary/unrelated/provenance").json()["occurrences"]
    assert kept_other["focus"] == "from somewhere else" and kept_other["availability"] != "unavailable"
    assert _fragment(pg_engine, user, "unrelated") == "from somewhere else"


def test_a_deleted_upload_marks_the_sources_of_kept_words_unavailable_whatever_form_they_were_stored_in(pg_engine, backbone, media):
    store, assets, seed = media
    user = _account(pg_engine)
    media_id = seed("7c" * 16, owner=user)
    client = _client(backbone, user=user)
    ident = str(uuid.uuid4())
    assert _put(client, ident, form="upload", title="My file", mediaId=media_id).status_code == 200
    for word, source in (("anchor", f"media:{media_id}"), ("beacon", media_id)):
        _save_word_from(pg_engine, user, word, "heard in the file")
        assert client.post(f"/api/library/vocabulary/{word}/provenance", json={
            "operationId": op(), "reason": "from_listening", "sourceKind": "listening", "sourceId": source, "focus": "heard in the file"}).status_code == 200
    assert _delete(client, ident).status_code == 200
    for word in ("anchor", "beacon"):
        (occurrence,) = client.get(f"/api/library/vocabulary/{word}/provenance").json()["occurrences"]
        assert occurrence["availability"] == "unavailable" and occurrence["focus"] == "", word


def test_a_source_deleted_before_this_change_is_still_reported_unavailable_without_its_excerpt(pg_engine, backbone):
    user = _account(pg_engine)
    client = _client(backbone, user=user)
    ident = str(uuid.uuid4())
    content = f"text:{ident}"
    assert _put(client, ident, form="text", title="Diary", text="x").status_code == 200
    _save_word_from(pg_engine, user, "lantern", "a lamp in the window")
    assert client.post("/api/library/vocabulary/lantern/provenance", json={
        "operationId": op(), "reason": "from_reading", "sourceKind": "reading", "sourceId": content, "focus": "a lamp in the window"}).status_code == 200
    assert _delete(client, ident).status_code == 200
    with pg_engine.begin() as connection:  # put the excerpt back as an older deletion would have left it
        connection.execute(text("UPDATE language_provenance SET focus = 'a lamp in the window', availability = 'unknown' WHERE source_id = :s"), {"s": content})
    (occurrence,) = client.get("/api/library/vocabulary/lantern/provenance").json()["occurrences"]
    assert occurrence["availability"] == "unavailable" and occurrence["focus"] == "", "the read masks it as well"


def test_a_kept_again_link_is_available_again(pg_engine, backbone):
    user = _account(pg_engine)
    client = _client(backbone, user=user)
    first, second = str(uuid.uuid4()), str(uuid.uuid4())
    link = "https://example.test/clip"
    assert _put(client, first, form="url", title="Clip", url=link).status_code == 200
    _save_word_from(pg_engine, user, "ripple", "a ripple on the water")
    assert client.post("/api/library/vocabulary/ripple/provenance", json={
        "operationId": op(), "reason": "from_listening", "sourceKind": "listening", "sourceId": f"url:{link}", "focus": "a ripple on the water"}).status_code == 200
    assert _delete(client, first).status_code == 200
    assert _put(client, second, form="url", title="Clip again", url=link).status_code == 200
    with pg_engine.begin() as connection:
        connection.execute(text("UPDATE language_provenance SET focus = 'a ripple on the water', availability = 'unknown'"))
    (occurrence,) = client.get("/api/library/vocabulary/ripple/provenance").json()["occurrences"]
    assert occurrence["availability"] != "unavailable" and occurrence["focus"] == "a ripple on the water"


def test_the_listing_pages_and_is_never_silently_limited(pg_engine, backbone, monkeypatch):
    from writing_coach import account_records_api

    monkeypatch.setattr(account_records_api, "MAX_IMPORTS", 200)
    client = _client(backbone, user=_account(pg_engine))
    live, gone = [], []
    for number in range(63):
        ident = str(uuid.uuid4())
        assert _put(client, ident, form="url", title=f"L{number}", url=f"https://example.test/{number}").status_code == 200
        live.append(f"url:{ident}")
    for _ in range(17):
        ident = str(uuid.uuid4())
        assert _put(client, ident, form="text", title="T", text="x").status_code == 200
        assert _delete(client, ident).status_code == 200
        gone.append(f"text:{ident}")
    first = client.get("/api/imports").json()
    assert first["nextCursor"] is not None and len(first["imports"]) == 50, "the first page says there is more"
    seen_live, seen_gone, cursor, deleted_cursor, pages = [], [], None, None, 0
    while True:
        params = {"limit": 50, "deletedLimit": 6, "include": "both" if cursor is not None and deleted_cursor is not None or pages == 0 else ("imports" if cursor is not None else "deleted")}
        if cursor is not None:
            params["cursor"] = cursor
        if deleted_cursor is not None:
            params["deletedCursor"] = deleted_cursor
        page = client.get("/api/imports", params=params).json()
        pages += 1
        seen_live += [item["id"] for item in page["imports"]]
        seen_gone += [item["id"] for item in page["deleted"]]
        assert page["highWater"] >= max([item["sequence"] for item in page["imports"]] or [0])
        cursor, deleted_cursor = page["nextCursor"], page["nextDeletedCursor"]
        if cursor is None and deleted_cursor is None:
            break
        assert pages < 20
    assert sorted(seen_live) == sorted(live) and len(set(seen_live)) == 63, "every import arrives, once"
    assert sorted(seen_gone) == sorted(gone) and len(set(seen_gone)) == 17, "every tombstone arrives, once"
    assert pages >= 3
