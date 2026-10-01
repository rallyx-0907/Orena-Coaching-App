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
from sqlalchemy import inspect, text

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
