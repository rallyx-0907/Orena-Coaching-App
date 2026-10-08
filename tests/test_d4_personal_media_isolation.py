"""A learner's personal media is private to the account and learning language that made it (D4).

Seeds entries straight into a temporary store, so no ffprobe is needed, and varies the
caller's account key and learning language the way the request middleware does. Every refusal
is a 404 - the answer an identity nothing holds gets - so existence is not leaked.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app as app_module  # noqa: E402
from writing_coach import listening_api, media_library_api  # noqa: E402
from writing_coach.book_asset_store import FilesystemBookAssetStore  # noqa: E402
from writing_coach.media_library_store import (  # noqa: E402
    FileMediaLibraryStore, MediaLibraryEntry, owner_token, visible_to,
)

TOKEN = "a" * 32


def _entry(media_id: str, *, library: str, language: str = "en", owner: str | None = None, token: str = TOKEN) -> MediaLibraryEntry:
    source = {"provider": "upload", "type": "upload", "provenance_url": "", "license": "x", "review_status": "x", "imported_by": "learner"}
    if owner is not None:
        source["owner"] = owner_token(owner)
    return MediaLibraryEntry(
        media_id=media_id, media_type="audio", provider="upload", provider_media_id=token, canonical_url="",
        playback={"provider": "orena", "kind": "audio", "url": f"/api/media/files/media/{token}/original.wav"},
        title="Mine", thumbnail={"kind": "asset", "ref": f"media/{token}/thumbnail.jpg"}, duration_ms=2000,
        language=language, level="", creator="", source=source, library=library,
        created_at="2026-10-01T00:00:00Z", lesson=None,
    )


@pytest.fixture()
def env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    store = FileMediaLibraryStore(tmp_path / "library")
    assets = FilesystemBookAssetStore(tmp_path / "assets")
    assets.put(f"media/{TOKEN}/original.wav", b"RIFFpersonal")
    assets.put(f"media/{TOKEN}/thumbnail.jpg", b"jpeg")
    assets.put("media/direct-shared/original.wav", b"RIFFshared")
    store.upsert(_entry(f"upload-{TOKEN}", library="personal", owner="alice"))
    store.upsert(_entry("upload-" + "b" * 32, library="personal", owner=None, token="b" * 32))  # written before owners existed
    store.upsert(_entry("shared-one", library="shared", token="c" * 32))
    monkeypatch.setattr(media_library_api, "_store", store)
    monkeypatch.setattr(media_library_api, "_asset_store", assets)
    monkeypatch.setattr(listening_api, "_media_store", store)
    caller = {"user": "alice", "language": "en"}
    for module in (media_library_api, listening_api):
        monkeypatch.setattr(module, "current_user_key", lambda: caller["user"])
        monkeypatch.setattr(module, "current_language_code", lambda: caller["language"])
    return TestClient(app_module.app), caller


def _statuses(client: TestClient, media_id: str) -> tuple[int, int]:
    return (
        client.get(f"/api/media/my/{media_id}").status_code,
        client.get(f"/api/listening/library/{media_id}").status_code,
    )


def test_the_owner_in_the_same_language_opens_a_personal_entry_everywhere(env) -> None:
    client, _ = env
    my, library = _statuses(client, f"upload-{TOKEN}")
    assert my == 200 and library == 200
    assert client.get(f"/api/media/files/media/{TOKEN}/original.wav").status_code == 200
    assert client.get(f"/api/media/files/media/{TOKEN}/thumbnail.jpg?variant=thumb").status_code == 200


def test_another_account_gets_404_for_the_entry_the_library_route_and_the_files(env) -> None:
    client, caller = env
    caller["user"] = "bob"
    assert _statuses(client, f"upload-{TOKEN}") == (404, 404)
    assert client.get(f"/api/media/files/media/{TOKEN}/original.wav").status_code == 404
    assert client.get(f"/api/media/files/media/{TOKEN}/thumbnail.jpg?variant=thumb").status_code == 404


def test_the_owner_in_another_learning_language_gets_404(env) -> None:
    client, caller = env
    caller["language"] = "zh"
    assert _statuses(client, f"upload-{TOKEN}") == (404, 404)
    assert client.get(f"/api/media/files/media/{TOKEN}/original.wav").status_code == 404


def test_a_refusal_looks_like_an_identity_nothing_holds(env) -> None:
    client, caller = env
    caller["user"] = "bob"
    refused = client.get(f"/api/media/my/upload-{TOKEN}")
    missing = client.get("/api/media/my/upload-" + "f" * 32)
    assert refused.status_code == missing.status_code == 404
    assert refused.json() == missing.json()


def test_shared_media_and_its_files_are_unaffected(env) -> None:
    client, caller = env
    caller.update(user="bob", language="zh")
    assert client.get("/api/media/files/media/direct-shared/original.wav").status_code == 200
    entry = listening_api.stored_media_entry("shared-one")
    assert entry is not None and entry.library == "shared"


def test_an_entry_without_an_owner_belongs_to_the_local_account_only(env) -> None:
    client, caller = env
    legacy_id = "upload-" + "b" * 32
    caller["user"] = "legacy"
    assert client.get(f"/api/media/my/{legacy_id}").status_code == 200
    caller["user"] = "alice"
    assert client.get(f"/api/media/my/{legacy_id}").status_code == 404


def test_listening_progress_lines_do_not_resolve_another_accounts_personal_media(env, monkeypatch: pytest.MonkeyPatch) -> None:
    _, caller = env
    caller["user"] = "bob"
    assert listening_api.stored_media_entry(f"upload-{TOKEN}") is None
    caller["user"] = "alice"
    assert listening_api.stored_media_entry(f"upload-{TOKEN}") is not None


def test_visible_to_is_the_one_rule() -> None:
    mine = _entry("upload-x", library="personal", owner="alice")
    assert visible_to(mine, user_key="alice", language="en")
    assert not visible_to(mine, user_key="bob", language="en")
    assert not visible_to(mine, user_key="alice", language="zh")
    assert visible_to(_entry("s", library="shared"), user_key="bob", language="zh")


def test_a_new_personal_upload_is_stamped_with_its_owner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from writing_coach import media_source_import
    from writing_coach.media_source_import import MediaSourceImporter

    class Probe:
        duration_ms, media_type = 2000, "audio"

    monkeypatch.setattr(media_source_import, "probe_media", lambda path: Probe())
    monkeypatch.setattr(MediaSourceImporter, "_persist_thumbnail", lambda *a, **k: "")
    store = FileMediaLibraryStore(tmp_path / "library")
    importer = MediaSourceImporter(None, store, FilesystemBookAssetStore(tmp_path / "assets"))
    sample = tmp_path / "t.wav"
    sample.write_bytes(b"RIFF")
    entry = importer.import_upload(sample, filename="t.wav", language="zh", imported_by="learner", library="personal", owner_key="alice")
    assert entry.source["owner"] == owner_token("alice") and entry.language == "zh"
    assert visible_to(store.get(entry.media_id), user_key="alice", language="zh")
    with pytest.raises(ValueError):
        importer.import_upload(sample, filename="t.wav", language="zh", imported_by="learner", library="personal")
