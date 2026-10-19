"""Manual corrections of a published media item's cue text, a cue's stored translation, and a vocabulary gloss.

Admin only, audited, $0: every test would fail on a provider call (the translator handed to the read path raises).
"""
from __future__ import annotations

import asyncio
import json
import uuid
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from writing_coach import admin_console_api as console
from writing_coach import media_pack
from writing_coach.book_asset_store import FilesystemBookAssetStore
from writing_coach.content_packs import build_pack, read_pack
from writing_coach.media_library_store import FileMediaLibraryStore, MediaLibraryEntry
from writing_coach.media_meaning import IMPORTED_IDENTITY, cache_key, resolve_segment_meanings
from writing_coach.persistence.admin_repository import AdminConsoleRepository
from writing_coach.persistence.models import AuditLog, Base, VocabularyCollectionMembership, VocabularyEntry
from writing_coach.persistence.vocabulary_repository import sqlite_vocabulary_repository
from writing_coach.vocabulary_source_import import (
    detect_vocabulary_mapping,
    normalize_vocabulary_rows,
    parse_vocabulary_source,
)

ADMIN = {"google_sub": "sub-admin", "email": "admin@example.com", "role": "admin"}
READ_IDENTITY = "PlatformMediaTranslator:default"
LINES = [
    "The weather turned cold in the north of the country last week.",
    "Many families stayed inside and watched the snow fall slowly.",
    "By the weekend the roads were open again for everyone.",
]
MEDIA = "yt-fix"
BASE = f"/api/admin/console/content/media/{MEDIA}/cues"


def guard(request):
    if request.headers.get("x-test-admin") != "1":
        raise HTTPException(403, "Platform administrator access required")
    return ADMIN


class DictCache:
    """The learning cache's two methods over a dict, so the tests see exactly which keys exist."""

    def __init__(self):
        self.rows = {}

    def get_media_translation(self, key):
        return self.rows.get(key)

    def put_media_translation(self, key, translated_text, provenance, generated_at):
        self.rows[key] = {"translated_text": translated_text, "provenance": provenance, "generated_at": generated_at}


def _lesson():
    segments = []
    for i, text in enumerate(LINES):
        words = [{"text": w, "start_ms": i * 4000 + n * 100, "end_ms": i * 4000 + n * 100 + 90}
                 for n, w in enumerate(text.split())]
        segments.append({"segment_id": f"s{i}", "order": i, "start_ms": i * 4000, "end_ms": i * 4000 + 3500,
                         "original_text": text, "words": words})
    return {"topic": "weather", "payload": {"transcript": {"segments": segments}, "translations": [],
                                            "catalog": {"readings_by_segment": {"s0": [{"text": "x"}]}}}}


def _entry():
    source = {"provider": "youtube", "type": "video", "provenance_url": "https://example.org/clip",
              "license": "Permission granted", "rights": "cleared", "review_status": "approved",
              "imported_by": "admin@example.com"}
    return MediaLibraryEntry(
        media_id=MEDIA, media_type="video", provider="youtube", provider_media_id="abcdefghijk",
        canonical_url="https://www.youtube.com/watch?v=abcdefghijk",
        playback={"provider": "youtube", "kind": "video", "url": "https://www.youtube.com/embed/abcdefghijk"},
        title="Weather", thumbnail={"kind": "asset", "ref": f"media/{MEDIA}/thumb.jpg"}, duration_ms=12000,
        language="en", level="B1", creator="A channel", source=source, library="shared",
        created_at="2026-10-01T00:00:00+00:00", lesson=_lesson(), status="published",
        processing={"state": "ready", "stage": "ready"})


def call(app, method, path, admin=True, origin="http://testserver", **kwargs):
    headers = {"x-test-admin": "1"} if admin else {}
    if origin:
        headers["origin"] = origin

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            return await client.request(method, path, headers=headers, **kwargs)
    return asyncio.run(run())


@pytest.fixture()
def setup(tmp_path):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    store = FileMediaLibraryStore(tmp_path / "media")
    store.upsert(_entry())
    cache = DictCache()
    vocabulary = sqlite_vocabulary_repository(tmp_path / "vocab.db")
    vocabulary.initialize()
    console.configure_admin_console(
        admin_guard=guard, backend="postgresql", repository=AdminConsoleRepository(engine),
        vocabulary_repository=vocabulary, media_store=store, media_translations=cache,
        media_provider_models=lambda: [READ_IDENTITY], media_read_identity=lambda: READ_IDENTITY)
    app = FastAPI()
    app.include_router(console.router)
    yield {"app": app, "engine": engine, "store": store, "cache": cache, "vocabulary": vocabulary, "tmp": tmp_path}
    console.configure_admin_console(admin_guard=None)


def _seed(cache, language="vi", model=READ_IDENTITY, segment="s0", text=LINES[0], meaning="Bản dịch cũ"):
    cache.put_media_translation(cache_key(MEDIA, segment, text, language, model), meaning, "generated", "2026-10-01T00:00:00+00:00")


def _audit_rows(engine, action):
    with Session(engine) as session:
        return [row.payload if hasattr(row, "payload") else None for row in
                session.query(AuditLog).filter(AuditLog.action == action).all()]


def _boom(*_a, **_k):
    raise AssertionError("a provider was called")


def _read(cache, text, segment="s0", language="vi"):
    return resolve_segment_meanings(
        asset_id=MEDIA, segments=[SimpleNamespace(segment_id=segment, original_text=text)], support_language=language,
        source_language="en", cache=cache, translate=_boom, provider_model=READ_IDENTITY)


def test_routes_are_admin_only_and_same_origin(setup):
    body = {"segment_id": "s0", "text": "Fixed."}
    assert call(setup["app"], "PATCH", f"{BASE}/text", admin=False, json=body).status_code == 403
    assert call(setup["app"], "PATCH", f"{BASE}/text", origin=None, json=body).status_code == 403
    assert call(setup["app"], "PATCH", f"{BASE}/text", origin="https://evil.example", json=body).status_code == 403
    tbody = {"segment_id": "s0", "language": "vi", "text": "x"}
    assert call(setup["app"], "PATCH", f"{BASE}/translation", admin=False, json=tbody).status_code == 403
    assert call(setup["app"], "PATCH", f"{BASE}/translation", origin=None, json=tbody).status_code == 403
    gloss = "/api/admin/console/content/vocabulary/c/entries/" + str(uuid.uuid4()) + "/gloss"
    assert call(setup["app"], "PATCH", gloss, admin=False, json={"language": "vi", "text": "x"}).status_code == 403
    assert setup["store"].get(MEDIA).lesson == _lesson()


def test_cue_text_rekeys_every_identity_so_the_learner_keeps_the_translation_with_no_provider(setup):
    cache, engine = setup["cache"], setup["engine"]
    _seed(cache)                                         # the read path's identity
    _seed(cache, meaning="Bản dịch nhập", model=IMPORTED_IDENTITY)
    _seed(cache, meaning="Bản dịch Groq", model="GroqTranslationProvider:default")
    _seed(cache, language="zh", meaning="旧译文")
    before_calls = len(cache.rows)
    fixed = "The weather turned very cold in the north of the country last week."
    first = call(setup["app"], "PATCH", f"{BASE}/text", json={"segment_id": "s0", "text": fixed})
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["changed"] and body["content_revision"] == 1 and body["words"] == "dropped"  # one more word
    assert body["readings_dropped"] and body["translations"]["carried"] == 4
    assert first.headers["etag"] == f'"{MEDIA}-r1"'
    lesson = setup["store"].get(MEDIA).lesson
    seg = lesson["payload"]["transcript"]["segments"][0]
    assert seg["original_text"] == fixed and seg["words"] == [] and seg["start_ms"] == 0 and seg["end_ms"] == 3500
    assert "s0" not in lesson["payload"]["catalog"]["readings_by_segment"]
    assert lesson["payload"]["transcript"]["segments"][1]["words"]  # other cues untouched

    outcome = _read(cache, fixed)                          # the learner read path: cache hit, translate=_boom
    assert outcome.provider_calls == 0 and outcome.status == "ready"
    assert outcome.meanings[0].translated_meaning == "Bản dịch cũ"
    assert cache.rows[cache_key(MEDIA, "s0", fixed, "vi", IMPORTED_IDENTITY)]["translated_text"] == "Bản dịch nhập"
    assert cache.rows[cache_key(MEDIA, "s0", fixed, "vi", "GroqTranslationProvider:default")]["translated_text"] == "Bản dịch Groq"
    assert cache.rows[cache_key(MEDIA, "s0", fixed, "zh", READ_IDENTITY)]["translated_text"] == "旧译文"
    assert len(cache.rows) == before_calls * 2
    assert _audit_rows(engine, "admin.content.cue_text")[0]["to"] == fixed

    # Second correction: same token count keeps the word timing, with the corrected words.
    again = call(setup["app"], "PATCH", f"{BASE}/text", json={"segment_id": "s1", "text": "Many families stayed inside and watched the snow fall quickly."})
    assert again.json()["words"] == "retexted" and again.json()["content_revision"] == 2
    assert again.headers["etag"] == f'"{MEDIA}-r2"'
    words = setup["store"].get(MEDIA).lesson["payload"]["transcript"]["segments"][1]["words"]
    assert words[-1]["text"] == "quickly." and words[-1]["start_ms"] == 4000 + 9 * 100
    # Same text again is a recorded no-op.
    same = call(setup["app"], "PATCH", f"{BASE}/text", json={"segment_id": "s1", "text": "Many families stayed inside and watched the snow fall quickly."})
    assert same.json()["changed"] is False and setup["store"].get(MEDIA).lesson["content_revision"] == 2


def test_cue_text_with_a_supplied_translation_uses_it_and_checks_the_request(setup):
    cache = setup["cache"]
    _seed(cache)
    fixed = "The weather turned cold in the north of the nation last week."
    done = call(setup["app"], "PATCH", f"{BASE}/text",
                json={"segment_id": "s0", "text": fixed, "translations": {"vi": "Bản dịch mới"}})
    assert done.status_code == 200
    got = cache.rows[cache_key(MEDIA, "s0", fixed, "vi", READ_IDENTITY)]
    assert got["translated_text"] == "Bản dịch mới" and got["provenance"] == "manual_correction"
    assert cache.rows[cache_key(MEDIA, "s0", fixed, "vi", IMPORTED_IDENTITY)]["translated_text"] == "Bản dịch mới"
    assert call(setup["app"], "PATCH", f"{BASE}/text", json={"segment_id": "nope", "text": "x y"}).status_code == 404
    assert call(setup["app"], "PATCH", f"{BASE}/text", json={"segment_id": "s0", "text": "x", "translations": {"en": "x"}}).status_code == 422
    assert call(setup["app"], "PATCH", f"{BASE}/text", json={"segment_id": "s0", "text": "   "}).status_code in {422}
    assert call(setup["app"], "PATCH", "/api/admin/console/content/media/missing/cues/text",
                json={"segment_id": "s0", "text": "x"}).status_code == 404


def test_cue_translation_sets_the_read_identity_and_pack_import_with_manual_provenance(setup):
    cache, engine = setup["cache"], setup["engine"]
    _seed(cache)
    done = call(setup["app"], "PATCH", f"{BASE}/translation", json={"segment_id": "s0", "language": "VI", "text": " Bản dịch đúng "})
    assert done.status_code == 200 and done.json()["content_revision"] == 1
    assert done.headers["etag"] == f'"{MEDIA}-r1"'
    for model in (READ_IDENTITY, IMPORTED_IDENTITY):
        row = cache.rows[cache_key(MEDIA, "s0", LINES[0], "vi", model)]
        assert row["translated_text"] == "Bản dịch đúng" and row["provenance"] == "manual_correction"
    outcome = _read(cache, LINES[0])
    assert outcome.provider_calls == 0 and outcome.meanings[0].translated_meaning == "Bản dịch đúng"
    audit = _audit_rows(engine, "admin.content.cue_translation")
    assert len(audit) == 1 and audit[0]["provenance"] == "manual_correction" and audit[0]["language"] == "vi"
    assert audit[0]["actor"] == "sub-admin"
    assert call(setup["app"], "PATCH", f"{BASE}/translation", json={"segment_id": "s0", "language": "en", "text": "x"}).status_code == 422
    assert call(setup["app"], "PATCH", f"{BASE}/translation", json={"segment_id": "zz", "language": "vi", "text": "x"}).status_code == 404


def test_a_preauthored_meaning_that_shadows_the_cache_is_corrected_too(setup):
    entry = setup["store"].get(MEDIA)
    lesson = json.loads(json.dumps(entry.lesson))
    lesson["payload"]["translations"] = [{"segment_id": "s0", "target_language": "vi", "translated_meaning": "sai"}]
    from dataclasses import replace
    setup["store"].upsert(replace(entry, lesson=lesson))
    call(setup["app"], "PATCH", f"{BASE}/translation", json={"segment_id": "s0", "language": "vi", "text": "đúng"})
    assert setup["store"].get(MEDIA).lesson["payload"]["translations"][0]["translated_meaning"] == "đúng"


def test_export_carries_the_corrections_and_a_reimport_is_idempotent(setup):
    store, cache, tmp = setup["store"], setup["cache"], setup["tmp"]
    for i, line in enumerate(LINES):
        _seed(cache, segment=f"s{i}", text=line, meaning=f"cũ {i}")
    fixed = "The weather turned very cold in the north of the country last week."
    assert call(setup["app"], "PATCH", f"{BASE}/text", json={"segment_id": "s0", "text": fixed}).status_code == 200
    assert call(setup["app"], "PATCH", f"{BASE}/translation", json={"segment_id": "s1", "language": "vi", "text": "đã sửa"}).status_code == 200
    assets = FilesystemBookAssetStore(tmp / "assets")
    assets.put(f"media/{MEDIA}/thumb.jpg", b"\xff\xd8\xff thumb")
    items, blobs, _ = media_pack.build_media_items(store, assets, translations=cache, provider_models=[READ_IDENTITY],
                                                   include_derived_text=True)
    raw = build_pack(items, created_by="t", environment="x", app_version="v", filters={}, assets=blobs)
    pack = read_pack(raw)
    data = pack.items[0].data
    segments = data["entry"]["lesson"]["payload"]["transcript"]["segments"]
    assert segments[0]["original_text"] == fixed
    by_segment = {row["segment_id"]: row["translated_text"] for row in data["translations"] if row["target_language"] == "vi"}
    assert by_segment == {"s0": "cũ 0", "s1": "đã sửa", "s2": "cũ 2"}
    assert any(row["provenance"] == "manual_correction" for row in data["translations"])

    dst, dst_assets, dst_cache = FileMediaLibraryStore(tmp / "dst"), FilesystemBookAssetStore(tmp / "dst-assets"), DictCache()
    first = media_pack.apply_media_items(pack, dst, dst_assets, dry_run=False, translations=dst_cache)
    assert first[0]["outcome"] == "new" and first[0]["translations"]["new"] >= 3
    assert dst.get(MEDIA).lesson["payload"]["transcript"]["segments"][0]["original_text"] == fixed
    assert dst_cache.rows[cache_key(MEDIA, "s1", LINES[1], "vi", IMPORTED_IDENTITY)]["translated_text"] == "đã sửa"
    again = media_pack.apply_media_items(pack, dst, dst_assets, dry_run=False, translations=dst_cache)
    assert again[0]["outcome"] == "unchanged" and again[0]["translations"]["unchanged"] >= 3
    assert "written" not in again[0]["translations"]


def test_vocabulary_gloss_correction_edits_a_published_entry_and_its_snapshot(setup):
    repository = setup["vocabulary"]
    csv = "word,meaning" + chr(10) + "allocate,phan bo" + chr(10)
    parsed = parse_vocabulary_source("pack.csv", csv.encode("utf-8"))
    detected = detect_vocabulary_mapping(parsed)
    normalized = normalize_vocabulary_rows(parsed, mapping=detected.mapping, language_code="en", meaning_language="vi",
                                           collection_framework="TOEIC", collection_level="B1")
    repository.import_source(
        collection={"id": "pack", "title": "A pack", "language_code": "en", "framework": "TOEIC", "level": "B1",
                    "catalog_status": "pending_review", "origin": "imported", "provenance": {"publisher": "test"}},
        source=normalized, records=normalized["records"], mapping=detected.mapping, imported_by="admin@example.com")
    repository.finalize_collection_publication("pack", admission={
        "rights_status": "licensed", "completeness": "complete", "review_status": "approved",
        "publication_attested": True, "attested_by": "admin@example.com"})
    entry = repository.list_entries("pack")[0][0]
    path = f"/api/admin/console/content/vocabulary/pack/entries/{entry['id']}/gloss"
    done = call(setup["app"], "PATCH", path, json={"language": "vi", "text": "phân bổ"})
    assert done.status_code == 200 and done.json()["changed"]
    corrected = repository.get_collection("pack")["entries"][0]
    assert corrected["support_translations"]["vi"] == "phân bổ"
    assert corrected["provenance"]["gloss_corrections"][0]["actor"] == "sub-admin"
    audit = _audit_rows(setup["engine"], "admin.content.vocabulary_gloss")
    assert audit[0]["from"] == "phan bo" and audit[0]["to"] == "phân bổ"
    assert call(setup["app"], "PATCH", path, json={"language": "vi", "text": "phân bổ"}).json()["changed"] is False
    assert call(setup["app"], "PATCH", f"/api/admin/console/content/vocabulary/pack/entries/{uuid.uuid4()}/gloss",
                json={"language": "vi", "text": "x"}).status_code == 404
    assert call(setup["app"], "PATCH", path, json={"language": "xx", "text": "x"}).status_code == 422


QUOTED = "这个计划画蛇添足，反而不好。"
EXAMPLES = [
    {"language": "zh", "text": "他写完了还要加一句，真是画蛇添足。", "reading": "tā xiě wán le hái yào jiā yī jù",
     "highlight": {"match": "画蛇添足"}, "translation": {"vi": "Viết xong còn thêm một câu.", "en": "He added one more line."},
     "origin": "source"},
    {"language": "zh", "text": QUOTED, "reading": "zhè ge jì huà huà shé tiān zú", "highlight": {"match": "画蛇添足"},
     "translation": {"vi": "Kế hoạch này vẽ rắn thêm chân.", "en": "This plan gilds the lily."}, "origin": "source"},
    {"language": "zh", "text": "不要画蛇添足。", "reading": "bú yào huà shé tiān zú",
     "translation": {"vi": "Đừng vẽ rắn thêm chân.", "en": "Don't overdo it."}, "origin": "source"},
]


def _published_idiom(repository, collection="idioms"):
    csv = "word,meaning" + chr(10) + "画蛇添足,vẽ rắn thêm chân" + chr(10)
    parsed = parse_vocabulary_source("pack.csv", csv.encode("utf-8"))
    detected = detect_vocabulary_mapping(parsed)
    normalized = normalize_vocabulary_rows(parsed, mapping=detected.mapping, language_code="zh", meaning_language="vi",
                                           collection_framework="HSK", collection_level="HSK5")
    repository.import_source(
        collection={"id": collection, "title": "Idioms", "language_code": "zh", "framework": "HSK", "level": "HSK5",
                    "catalog_status": "pending_review", "origin": "imported", "provenance": {"publisher": "test"}},
        source=normalized, records=normalized["records"], mapping=detected.mapping, imported_by="admin@example.com")
    repository.finalize_collection_publication(collection, admission={
        "rights_status": "licensed", "completeness": "complete", "review_status": "approved",
        "publication_attested": True, "attested_by": "admin@example.com"})
    entry_id = repository.list_entries(collection)[0][0]["id"]
    with Session(repository.engine) as session, session.begin():
        entry = session.get(VocabularyEntry, uuid.UUID(entry_id))
        entry.examples = json.loads(json.dumps(EXAMPLES))
        membership = session.query(VocabularyCollectionMembership).filter_by(
            collection_id=collection, entry_id=uuid.UUID(entry_id)).one()
        membership.membership_metadata = {**(membership.membership_metadata or {}),
                                          "content_snapshot": {"examples": json.loads(json.dumps(EXAMPLES))}}
    return entry_id


def _snapshot(repository, collection, entry_id):
    with Session(repository.engine) as session:
        membership = session.query(VocabularyCollectionMembership).filter_by(
            collection_id=collection, entry_id=uuid.UUID(entry_id)).one()
        return membership.membership_metadata["content_snapshot"]


def test_vocabulary_example_correction_replaces_one_published_example_and_its_snapshot(setup):
    repository = setup["vocabulary"]
    entry_id = _published_idiom(repository)
    path = f"/api/admin/console/content/vocabulary/idioms/entries/{entry_id}/examples/1"
    new = "我们的报告已经很好了，再加图表就是画蛇添足。"
    body = {"text": f" {new} ", "reading": "wǒ men de bào gào yǐ jīng hěn hǎo le", "language": "zh",
            "translations": {"vi": "Báo cáo đã tốt rồi.", "EN": "Our report is good already."},
            "reason": "PRE-201 F3: quoted from a video transcript without credit"}
    done = call(setup["app"], "PATCH", path, json=body)
    assert done.status_code == 200, done.text
    assert done.json()["changed"] is True
    examples = repository.get_collection("idioms")["entries"][0]["examples"]
    assert examples[0] == EXAMPLES[0] and examples[2] == EXAMPLES[2]
    assert examples[1] == {"language": "zh", "text": new, "reading": "wǒ men de bào gào yǐ jīng hěn hǎo le",
                           "highlight": {"match": "画蛇添足"}, "origin": "source",
                           "translation": {"vi": "Báo cáo đã tốt rồi.", "en": "Our report is good already."}}
    snapshot = _snapshot(repository, "idioms", entry_id)["examples"]
    assert snapshot[1]["text"] == new and snapshot[1]["translation"]["en"] == "Our report is good already."
    assert snapshot[0] == EXAMPLES[0] and snapshot[2] == EXAMPLES[2]
    with Session(repository.engine) as session:
        provenance = session.get(VocabularyEntry, uuid.UUID(entry_id)).provenance
    record = provenance["example_corrections"][0]
    assert record["actor"] == "sub-admin" and record["from"] == QUOTED and record["to"] == new
    assert record["index"] == 1 and record["reason"].startswith("PRE-201") and record["at"]
    audit = _audit_rows(setup["engine"], "admin.content.vocabulary_example")
    assert len(audit) == 1 and audit[0]["from"] == QUOTED and audit[0]["to"] == new
    assert audit[0]["actor"] == "sub-admin" and audit[0]["outcome"] == "ok" and audit[0]["index"] == 1
    again = call(setup["app"], "PATCH", path, json=body)
    assert again.status_code == 200 and again.json()["changed"] is False


def test_vocabulary_example_correction_refuses_bad_input(setup):
    repository = setup["vocabulary"]
    entry_id = _published_idiom(repository)
    base = f"/api/admin/console/content/vocabulary/idioms/entries/{entry_id}/examples"
    good = {"text": "新句子。", "reading": "xīn jù zi", "translations": {"vi": "Câu mới.", "en": "A new sentence."},
            "reason": "uncredited quote"}

    def status(path, **changes):
        return call(setup["app"], "PATCH", path, json={**good, **changes}).status_code

    assert status(f"{base}/3") == 422                                    # out of range
    assert status(f"{base}/-1") == 422
    assert status(f"{base}/0", text="   ") == 422                         # empty sentence
    assert status(f"{base}/0", text="") == 422
    assert status(f"{base}/0", reason=" ") == 422                         # a reason is required
    assert status(f"{base}/0", language="en") == 422                      # not the entry's language
    assert status(f"{base}/0", translations={"vi": "Câu mới."}) == 422     # the old EN gloss would go stale
    assert status(f"{base}/0", translations={"vi": "Câu mới.", "en": " "}) == 422
    assert status(f"{base}/0", translations={"vi": "x", "en": "x", "xx": "x"}) == 422
    assert status(f"{base}/0", reading=None) == 422                       # the old pinyin would go stale
    assert status(f"/api/admin/console/content/vocabulary/idioms/entries/{uuid.uuid4()}/examples/0") == 404
    assert status(f"/api/admin/console/content/vocabulary/other/entries/{entry_id}/examples/0") == 404
    assert repository.get_collection("idioms")["entries"][0]["examples"] == EXAMPLES
    assert _audit_rows(setup["engine"], "admin.content.vocabulary_example") == []
    with pytest.raises(ValueError):
        repository.correct_entry_example("idioms", entry_id, 5, text="x", translations={}, actor="a", reason="r")


def test_vocabulary_example_route_is_admin_only_and_same_origin(setup):
    repository = setup["vocabulary"]
    entry_id = _published_idiom(repository)
    path = f"/api/admin/console/content/vocabulary/idioms/entries/{entry_id}/examples/1"
    body = {"text": "新句子。", "reading": "xīn jù zi", "translations": {"vi": "Câu mới.", "en": "A new sentence."},
            "reason": "uncredited quote"}
    assert call(setup["app"], "PATCH", path, admin=False, json=body).status_code == 403
    assert call(setup["app"], "PATCH", path, origin=None, json=body).status_code == 403
    assert call(setup["app"], "PATCH", path, origin="https://evil.example", json=body).status_code == 403
    assert repository.get_collection("idioms")["entries"][0]["examples"] == EXAMPLES
    assert _audit_rows(setup["engine"], "admin.content.vocabulary_example") == []
