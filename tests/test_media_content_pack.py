"""Published shared media moved between two environments (D-233): the rehearsal.

A temp source store with mixed entries is exported; only the published shared ones travel. They are imported into
an empty temp store: transcripts and translations arrive byte for byte, asset checksums match, a second import
changes nothing, and a dry run writes nothing. No provider is called anywhere in this file.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import replace

import httpx
import pytest
from fastapi import FastAPI, HTTPException

from writing_coach import content_pack_api, media_pack
from writing_coach import reading_admin_api as admin_api
from writing_coach.book_asset_store import FilesystemBookAssetStore
from writing_coach.content_packs import PackError, PackItem, build_pack, read_pack
from writing_coach.media_library_store import FileMediaLibraryStore, MediaLibraryEntry

LINES = [
    "The weather turned cold in the north of the country last week.",
    "Many families stayed inside and watched the snow fall slowly.",
    "By the weekend the roads were open again for everyone.",
]
CLIP = "speaking/model-clip/" + "a" * 64 + ".webm"
CLIP_BYTES = b"\x1aE\xdf\xa3 pretend webm opus \x00\x01\x02"
THUMB_BYTES = b"\xff\xd8\xff pretend jpeg \x00\xff"


def _lesson() -> dict:
    segments = [
        {"segment_id": f"s{i}", "start_ms": i * 4000, "end_ms": i * 4000 + 3500, "original_text": text,
         "translations": {"vi": f"Bản dịch {i + 1}", "zh": f"翻译 {i + 1}"}}
        for i, text in enumerate(LINES)
    ]
    return {"topic": "weather", "payload": {"transcript": {"segments": segments}}}


def _entry(media_id: str, **overrides) -> MediaLibraryEntry:
    source = {"provider": "youtube", "type": "video", "provenance_url": "https://example.org/clip",
              "license": "Permission granted by the channel owner, 2026-10-01", "rights": "cleared",
              "review_status": "approved", "imported_by": "admin@example.com"}
    fields = dict(
        media_id=media_id, media_type="video", provider="youtube", provider_media_id="abcdefghijk",
        canonical_url="https://www.youtube.com/watch?v=abcdefghijk",
        playback={"provider": "youtube", "kind": "video", "url": "https://www.youtube.com/embed/abcdefghijk"},
        title=f"Title of {media_id}", thumbnail={"kind": "asset", "ref": f"media/{media_id}/thumb.jpg"},
        duration_ms=12000, language="en", level="B1", creator="A channel", source=source, library="shared",
        created_at="2026-10-01T00:00:00+00:00", lesson=_lesson(), status="published",
        processing={"state": "ready", "stage": "ready", "attempts": 3, "spend": 0.42},
    )
    fields.update(overrides)
    return MediaLibraryEntry(**fields)


def _clip_keys(entry: MediaLibraryEntry) -> list[str]:
    return [CLIP] if entry.media_id == "yt-good" else []


@pytest.fixture()
def source(tmp_path):
    store = FileMediaLibraryStore(tmp_path / "src")
    assets = FilesystemBookAssetStore(tmp_path / "src-assets")
    assets.put("media/yt-good/thumb.jpg", THUMB_BYTES)
    assets.put(CLIP, CLIP_BYTES)
    assets.put("media/yt-norights/thumb.jpg", THUMB_BYTES)
    assets.put("media/qa-published/thumb.jpg", THUMB_BYTES)
    no_rights = {**_entry("x").source, "rights": "unknown", "license": "", "review_status": "unknown"}
    for entry in (
        _entry("yt-good"),
        _entry("yt-norights", source=no_rights),
        _entry("qa-published"),
        _entry("yt-personal", library="personal", source={**_entry("x").source, "owner": "abc"}),
        _entry("yt-held", status="review", processing={"state": "held"}),
        _entry("yt-archived", status="archived"),
        _entry("yt-unpublished", status="unpublished"),
        _entry("up-local", provider="upload", provider_media_id="up-local", thumbnail={"kind": "none", "ref": ""},
               playback={"provider": "orena", "kind": "video", "url": "/api/media/files/media/up-local/original.mp4"}),
    ):
        store.upsert(entry)
    return store, assets


def _export(source, **kwargs):
    store, assets = source
    items, blobs, excluded = media_pack.build_media_items(store, assets, clip_keys=_clip_keys, **kwargs)
    raw = build_pack(items, created_by="t", environment="lane-8021", app_version="v", filters={}, assets=blobs,
                     extra_manifest={"source_commit": "abc123", "media_excluded": excluded})
    return read_pack(raw), raw, excluded


def _target(tmp_path):
    return FileMediaLibraryStore(tmp_path / "dst"), FilesystemBookAssetStore(tmp_path / "dst-assets")


def _canon(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def test_only_published_shared_entries_are_exported_and_the_pack_describes_itself(source):
    pack, _raw, excluded = _export(source, exclude_prefixes=("qa-",))
    assert [item.natural_key for item in pack.items] == ["yt-good", "yt-norights"]
    assert {row["media_id"]: row["reason"] for row in excluded} == {
        "qa-published": "excluded_by_prefix", "up-local": "local_playback_not_packable"}
    manifest = pack.manifest
    assert manifest["format"] == "orena-content-pack" and manifest["version"] == 2
    assert manifest["source_commit"] == "abc123" and manifest["source_environment"]["label"] == "lane-8021"
    assert sorted(path for path in manifest["counts"]) == ["media_item"]
    listed = {entry["path"]: entry for entry in manifest["files"]}
    assert listed[f"assets/{CLIP}"]["sha256"] == hashlib.sha256(CLIP_BYTES).hexdigest()
    packed = json.dumps([item.data for item in pack.items])
    assert "admin@example.com" not in packed  # an administrator's address never travels


def test_import_into_an_empty_store_is_exact_idempotent_and_a_dry_run_writes_nothing(source, tmp_path):
    pack, _raw, _ = _export(source, exclude_prefixes=("qa-",))
    store, assets = _target(tmp_path)

    dry = media_pack.apply_media_items(pack, store, assets, dry_run=True, clip_keys=_clip_keys)
    assert [(row["natural_key"], row["outcome"]) for row in dry] == [("yt-good", "new"), ("yt-norights", "new")]
    assert not (tmp_path / "dst").exists() and not (tmp_path / "dst-assets").exists()

    rows = media_pack.apply_media_items(pack, store, assets, dry_run=False, clip_keys=_clip_keys)
    assert [row["outcome"] for row in rows] == ["new", "new"]
    assert sorted(entry.media_id for entry in store.list(status=None)) == ["yt-good", "yt-norights"]

    src_store, src_assets = source
    arrived, original = store.get("yt-good"), src_store.get("yt-good")
    assert _canon(arrived.lesson) == _canon(original.lesson)  # transcript, timing and translations, byte for byte
    assert arrived.status == "published" and arrived.level == "B1" and arrived.created_at == original.created_at
    assert arrived.source["license"] == original.source["license"] and arrived.source["rights"] == "cleared"
    assert arrived.processing["state"] == "ready" and arrived.processing["origin"] == "content-pack"
    assert hashlib.sha256(assets.get("media/yt-good/thumb.jpg")).hexdigest() == hashlib.sha256(THUMB_BYTES).hexdigest()
    assert assets.get(CLIP) == CLIP_BYTES

    held = store.get("yt-norights")  # rights fields incomplete: arrives unpublished and the report says why
    assert held.status == "unpublished"
    assert next(row for row in rows if row["natural_key"] == "yt-norights")["held"] == "rights_incomplete"
    for absent in ("yt-personal", "yt-held", "yt-archived", "yt-unpublished", "qa-published", "up-local"):
        assert store.get(absent) is None

    before = (tmp_path / "dst" / "index.json").read_bytes()
    again = media_pack.apply_media_items(pack, store, assets, dry_run=False, clip_keys=_clip_keys)
    assert [row["outcome"] for row in again] == ["unchanged", "unchanged"]
    assert (tmp_path / "dst" / "index.json").read_bytes() == before
    assert len(store.list(status=None)) == 2


def test_a_different_local_item_is_a_conflict_until_overwrite_is_explicit(source, tmp_path):
    pack, _raw, _ = _export(source, ids=["yt-good"])
    store, assets = _target(tmp_path)
    media_pack.apply_media_items(pack, store, assets, dry_run=False, clip_keys=_clip_keys)
    store.upsert(replace(store.get("yt-good"), title="Edited here"))

    report = media_pack.apply_media_items(pack, store, assets, dry_run=False, clip_keys=_clip_keys)
    assert report[0]["outcome"] == "conflict" and report[0]["reason"] == "fields_differ"
    assert store.get("yt-good").title == "Edited here"

    dry = media_pack.apply_media_items(pack, store, assets, overwrite=True, dry_run=True, clip_keys=_clip_keys)
    assert dry[0]["outcome"] == "overwritten" and store.get("yt-good").title == "Edited here"
    media_pack.apply_media_items(pack, store, assets, overwrite=True, dry_run=False, clip_keys=_clip_keys)
    assert store.get("yt-good").title == "Title of yt-good"


def test_a_personal_entry_with_the_same_id_is_never_replaced(source, tmp_path):
    pack, _raw, _ = _export(source, ids=["yt-good"])
    store, assets = _target(tmp_path)
    store.upsert(_entry("yt-good", library="personal", source={**_entry("x").source, "owner": "abc"}))
    report = media_pack.apply_media_items(pack, store, assets, overwrite=True, dry_run=False, clip_keys=_clip_keys)
    assert report[0]["outcome"] == "refused" and report[0]["reason"] == "id_in_use_by_personal_entry"
    assert store.get("yt-good").library == "personal"


def test_a_tampered_asset_is_refused_when_the_pack_is_read(source):
    _pack, raw, _ = _export(source, ids=["yt-good"])
    import io
    import zipfile

    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as zin, zipfile.ZipFile(out, "w") as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            zout.writestr(info.filename, data + b"x" if info.filename == f"assets/{CLIP}" else data)
    with pytest.raises(PackError) as refused:
        read_pack(out.getvalue())
    assert refused.value.code == "pack_hash_mismatch"


def test_an_asset_outside_the_media_prefixes_is_refused_not_written(source, tmp_path):
    pack, _raw, _ = _export(source, ids=["yt-good"])
    item = pack.items[0]
    data = json.loads(json.dumps(item.data))
    data["assets"] = [{"key": "reading/evil.bin", "sha256": hashlib.sha256(b"z").hexdigest(), "bytes": 1}]
    raw = build_pack([PackItem(kind="media_item", natural_key="yt-good", data=data)], created_by="t", environment="x",
                     app_version="", filters={}, assets={"reading/evil.bin": b"z"})
    store, assets = _target(tmp_path)
    report = media_pack.apply_media_items(read_pack(raw), store, assets, dry_run=False, clip_keys=_clip_keys)
    assert report[0]["outcome"] == "refused" and report[0]["reason"] == "asset_key_not_allowed"
    assert store.get("yt-good") is None and not assets.exists("reading/evil.bin")


def test_an_unusable_transcript_arrives_unpublished(source, tmp_path):
    store_src, assets_src = source
    store_src.upsert(_entry("yt-empty", lesson={"topic": "x", "payload": {"transcript": {"segments": []}}}))
    assets_src.put("media/yt-empty/thumb.jpg", THUMB_BYTES)
    pack, _raw, _ = _export(source, ids=["yt-empty"])
    store, assets = _target(tmp_path)
    report = media_pack.apply_media_items(pack, store, assets, dry_run=False, clip_keys=_clip_keys)
    assert report[0]["held"].startswith("transcript_") and store.get("yt-empty").status == "unpublished"


def test_a_reading_only_pack_keeps_format_version_one():
    raw = build_pack([PackItem(kind="vocabulary_collection", natural_key="v", data={
        "id": "v", "language_code": "en", "entries": []})], created_by="t", environment="x", app_version="", filters={})
    assert read_pack(raw).manifest["version"] == 1


# ---- the Admin route shares the implementation ------------------------------------------------------------


def _guard(request):
    if request.headers.get("x-test-admin") != "1":
        raise HTTPException(403, "Platform administrator access required")
    return {"email": "admin@example.com", "google_sub": "admin"}


def _call(app, method, path, **kwargs):
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            return await client.request(method, path, headers={"x-test-admin": "1", "origin": "http://testserver"},
                                        **kwargs)

    return asyncio.run(run())


def test_the_admin_route_exports_plans_and_imports_media(source, tmp_path, monkeypatch):
    monkeypatch.setattr(media_pack, "default_clip_keys", _clip_keys)
    audits = []
    admin_api.configure_reading_admin(admin_guard=_guard, audit=lambda action, **kw: audits.append((action, kw)))
    app = FastAPI()
    app.include_router(content_pack_api.router)
    try:
        src_store, src_assets = source
        content_pack_api.configure_content_packs(media_store=src_store, media_assets=src_assets)
        denied = asyncio.run(_raw_forbidden(app))
        assert denied == 403
        response = _call(app, "POST", "/api/admin/content-packs/export",
                         json={"kinds": ["media"], "exclude_media_id_prefixes": ["qa-"], "media_ids": ["yt-good"]})
        assert response.status_code == 200, response.text
        store, assets = _target(tmp_path)
        content_pack_api.configure_content_packs(media_store=store, media_assets=assets)
        files = {"file": ("m.orenapack", response.content, "application/zip")}
        plan = _call(app, "POST", "/api/admin/content-packs/plan", files=files).json()
        assert plan["summary"] == {"new": 1} and store.get("yt-good") is None
        done = _call(app, "POST", "/api/admin/content-packs/import", files=files).json()
        assert done["summary"] == {"media_new": 1} and store.get("yt-good").status == "published"
        assert audits and audits[-1][0] == "admin.content_pack_import"
        again = _call(app, "POST", "/api/admin/content-packs/import", files=files).json()
        assert again["summary"] == {"media_unchanged": 1}
    finally:
        admin_api.configure_reading_admin(admin_guard=None)
        content_pack_api.configure_content_packs()


async def _raw_forbidden(app) -> int:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        return (await client.post("/api/admin/content-packs/export", json={"kinds": ["media"]},
                                  headers={"origin": "http://testserver"})).status_code
