"""`/api/media/files` serves a file by the stored entry that owns it, whatever its id or path prefix (#216, D-209).

One rule: a published shared item is everyone's; a held or unpublished shared item is an administrator's only
(learner and anonymous get 404); a personal item is its owner's. A file no entry owns is a 404, and a key that
tries to leave the store is a 404 before any lookup.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from tests.test_admin_authorization_matrix import ADMIN, LEARNER, _request, secured  # noqa: F401
from tests.test_media_lifecycle import _entry
from writing_coach import listening_api, media_library_api
from writing_coach.book_asset_store import FilesystemBookAssetStore
from writing_coach.media_library_store import FileMediaLibraryStore

# (media_id, provider, directory under media/) - the id and the directory differ for an upload only.
SOURCES = {
    "upload": ("upload-aaaa1111", "upload", "aaaa1111"),
    "direct": ("direct-bbbb2222", "direct", "direct-bbbb2222"),
    "commons": ("direct-cccc3333", "direct", "direct-cccc3333"),
    "archive": ("archive-dddd4444", "archive", "archive-dddd4444"),
}
BYTES = b"RIFFgate"
THUMB = b"\xff\xd8thumb"


def _shared(source: str, *, published: bool):
    media_id, provider, directory = SOURCES[source]
    extra = {"platform": "wikimedia-commons", "license_name": "CC BY"} if source == "commons" else {}
    return replace(
        _entry(media_id),
        provider=provider,
        provider_media_id=directory.removeprefix("direct-"),
        playback={"provider": "orena", "kind": "audio", "url": f"/api/media/files/media/{directory}/original.wav"},
        thumbnail={"kind": "asset", "ref": f"media/{directory}/thumbnail.jpg"},
        status="published" if published else "review",
        processing={} if published else {"state": "held", "reason": "rights_unknown"},
        source={"provider": provider, "type": provider, "provenance_url": "", "license": "", "review_status": "",
                "imported_by": "admin", "rights": "unknown", **extra},
    )


@pytest.fixture()
def gate(secured, monkeypatch, tmp_path):  # noqa: F811
    store = FileMediaLibraryStore(tmp_path / "index")
    assets = FilesystemBookAssetStore(tmp_path / "assets")
    monkeypatch.setattr(media_library_api, "_store", store)
    monkeypatch.setattr(media_library_api, "_asset_store", assets)
    monkeypatch.setattr(listening_api, "_media_store", store)
    return secured, store, assets


def _get(app, path, who):
    return _request(app, "GET", path, {}, who)


def _put(assets, source, name="original.wav", data=BYTES):
    directory = SOURCES[source][2]
    assets.put(f"media/{directory}/{name}", data)
    return f"/api/media/files/media/{directory}/{name}"


@pytest.mark.parametrize("source", sorted(SOURCES))
def test_a_published_shared_file_plays_for_everyone(gate, source):
    app, store, assets = gate
    store.upsert(_shared(source, published=True))
    path = _put(assets, source)
    for who in (LEARNER, ADMIN):
        served = _get(app, path, who)
        assert served.status_code == 200 and served.content == BYTES, (who, served.status_code)
    # An anonymous caller is stopped by the session guard before the route, as it always was.
    assert _get(app, path, None).status_code == 401


@pytest.mark.parametrize("source", sorted(SOURCES))
def test_a_held_shared_file_plays_for_an_administrator_only(gate, source):
    app, store, assets = gate
    store.upsert(_shared(source, published=False))
    path = _put(assets, source)
    assert _get(app, path, LEARNER).status_code == 404
    assert _get(app, path, None).status_code in {401, 404}
    served = _get(app, path, ADMIN)
    assert served.status_code == 200 and served.content == BYTES


@pytest.mark.parametrize("source", sorted(SOURCES))
def test_a_held_shared_thumbnail_is_gated_like_its_file(gate, source):
    app, store, assets = gate
    store.upsert(_shared(source, published=False))
    path = _put(assets, source, "thumbnail.jpg", THUMB) + "?variant=thumb"
    assert _get(app, path, LEARNER).status_code == 404
    assert _get(app, path, None).status_code in {401, 404}
    assert _get(app, path, ADMIN).content == THUMB


@pytest.mark.parametrize("source", sorted(SOURCES))
def test_a_file_under_an_entry_in_any_other_state_is_gated(gate, source):
    app, store, assets = gate
    path = _put(assets, source)
    store.upsert(replace(_shared(source, published=True), status="unpublished"))
    assert _get(app, path, LEARNER).status_code == 404
    assert _get(app, path, ADMIN).status_code == 200


def test_an_entry_is_found_by_the_files_it_points_at_not_by_its_id(gate):
    """A directory name that is neither the id nor `upload-` plus the id is still owned by the entry that points at it."""
    app, store, assets = gate
    entry = replace(
        _shared("direct", published=False),
        media_id="odd-id-one",
        provider_media_id="odd-id-one",
        playback={"provider": "orena", "kind": "audio", "url": "/api/media/files/media/some-other-dir/original.wav"},
        thumbnail={"kind": "asset", "ref": "media/some-other-dir/thumbnail.jpg"},
    )
    store.upsert(entry)
    assets.put("media/some-other-dir/original.wav", BYTES)
    path = "/api/media/files/media/some-other-dir/original.wav"
    assert _get(app, path, LEARNER).status_code == 404
    assert _get(app, path, ADMIN).status_code == 200


def test_another_accounts_personal_file_is_404_for_everyone_including_an_administrator(gate):
    app, store, assets = gate
    personal = replace(_shared("upload", published=True), library="personal",
                       source={"provider": "upload", "type": "upload", "provenance_url": "", "license": "",
                               "review_status": "", "imported_by": "x", "owner": "somebody-else"})
    store.upsert(personal)
    path = _put(assets, "upload")
    for who in (LEARNER, ADMIN):
        assert _get(app, path, who).status_code == 404
    assert _get(app, path, None).status_code in {401, 404}


def test_a_file_no_entry_owns_is_404_even_for_an_administrator(gate):
    app, store, assets = gate
    assets.put("media/orphan-0000/original.wav", BYTES)
    assets.put("media/direct-ffff9999/original.wav", BYTES)
    assets.put("other/area/file.wav", BYTES)
    for path in (
        "/api/media/files/media/orphan-0000/original.wav",
        "/api/media/files/media/direct-ffff9999/original.wav",
        "/api/media/files/other/area/file.wav",
    ):
        for who in (LEARNER, ADMIN):
            assert _get(app, path, who).status_code == 404, (path, who)


def test_a_model_clip_under_an_items_prefix_follows_the_item(gate):
    app, store, assets = gate
    store.upsert(_shared("direct", published=False))
    assets.put("media/direct-bbbb2222/model-clip/abc.webm", b"clip")
    path = "/api/media/files/media/direct-bbbb2222/model-clip/abc.webm"
    assert _get(app, path, LEARNER).status_code == 404
    assert _get(app, path, ADMIN).status_code == 200


@pytest.mark.parametrize("key", [
    "media/../../etc/passwd",
    "media/%2e%2e/%2e%2e/etc/passwd",
    "media/..%2f..%2fetc/passwd",
    "media/direct-bbbb2222/../upload-aaaa1111/original.wav",
    "media/direct-bbbb2222/%2e%2e/%2e%2e/secret",
    "media//direct-bbbb2222/original.wav",
    "media/direct-bbbb2222//original.wav",
    "media/direct-bbbb2222/.%2e/original.wav",
    "media/direct-bbbb2222%5c..%5coriginal.wav",
    "media/direct-bbbb2222/original.wav%00.jpg",
    "..%2f..%2fapp.py",
])
def test_a_traversal_attempt_is_404_for_every_role_and_reads_nothing(gate, key):
    app, store, assets = gate
    store.upsert(_shared("direct", published=True))
    store.upsert(_shared("upload", published=False))
    _put(assets, "direct")
    _put(assets, "upload")
    for who in (LEARNER, ADMIN):
        response = _get(app, f"/api/media/files/{key}", who)
        assert response.status_code == 404, (key, who, response.status_code)
        assert b"RIFF" not in response.content
    assert _get(app, f"/api/media/files/{key}", None).status_code in {401, 404}


def test_a_dot_segment_cannot_borrow_a_published_items_ownership(gate):
    """`media/<published>/../<held>/file` must not pass because its first directory is a published item's."""
    app, store, assets = gate
    store.upsert(_shared("direct", published=True))
    store.upsert(_shared("upload", published=False))
    _put(assets, "direct")
    _put(assets, "upload")
    path = "/api/media/files/media/direct-bbbb2222/../aaaa1111/original.wav"
    assert _get(app, path, LEARNER).status_code == 404
