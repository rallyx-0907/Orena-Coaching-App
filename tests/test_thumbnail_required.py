"""D-240: every learner-visible content item has a thumbnail.

Publishing without one is refused (Reading, vocabulary collections, media, books at import); the typographic cover is
deterministic and painted only with the kit's tokens; a downloaded picture is attached only from an allow-listed host
under an allowed licence, within 5 MB, with its provenance; a content pack carries the thumbnail with the item; the
audit lists and the backfill covers what was published before the rule. No test touches a network: every fetch is a
fake.
"""
from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

import pytest

from tests.test_content_lifecycle_reversible import _admit, _collection  # noqa: F401
from tests.test_reading_content_repository import _article  # noqa: F401
from tests.test_reading_engine_routes import ARTICLE, call, setup  # noqa: F401 - the route fixture
from tests.test_admin_console_routes import call as console_call, setup as console_setup  # noqa: F401
from tests.test_reading_images import Fetcher, MemoryStore, images, png  # noqa: F401
from writing_coach import media_library_api, thumbnail_audit, thumbnails
from writing_coach.content_packs import PackItem, build_pack, read_pack
from writing_coach.media_library_store import MediaLibraryEntry
from writing_coach.media_safe_fetch import UnsafeMediaFetch
from writing_coach.persistence.reading_content_repository import (
    LEARNER_VISIBLE_STATUS,
    ReadingContentRepository,
)
from writing_coach.persistence.vocabulary_repository import sqlite_vocabulary_repository
from writing_coach.reading_images import learner_image
from writing_coach.thumbnails import (
    ThumbnailRefused,
    ThumbnailRequired,
    fetch_licensed_image,
    host_allowed,
    normalize_provenance,
    typographic_cover_svg,
)

ROOT = Path(__file__).resolve().parents[1]
GOOD_URL = "https://images-assets.nasa.gov/image/PIA12345/PIA12345~orig.png"
LICENCE = {"author": "NASA/JPL", "licence": "Public domain", "licence_url": "https://www.nasa.gov/nasa-brand-center/images-and-media/"}


# ---- the typographic cover -------------------------------------------------------------------------

def test_the_cover_is_deterministic_and_paints_only_with_token_colours():
    first = typographic_cover_svg("Why the sea is salty", language="en", topic="Science", kind="reading")
    assert first == typographic_cover_svg("Why the sea is salty", language="en", topic="Science", kind="reading")
    assert first != typographic_cover_svg("Why the sky is blue", language="en", topic="Science", kind="reading")
    tokens = thumbnails.token_hexes()
    used = {item.upper() for item in re.findall(r"#[0-9A-Fa-f]{3,6}\b", first.decode())}
    assert used and used <= tokens, f"colours outside tokens.css: {used - tokens}"
    # the ratio the media card draws, and nothing that could run or load
    assert b'viewBox="0 0 640 400"' in first
    for forbidden in (b"<script", b"href=", b"onload", b"<image", b"url(http", b"@import"):
        assert forbidden not in first


@pytest.mark.parametrize("title", ["<script>alert(1)</script>", '"><svg onload=alert(1)>', "Tom & Jerry's \"day\""])
def test_a_hostile_title_is_text_never_markup(title):
    svg = typographic_cover_svg(title, language="en").decode()
    assert "<script" not in svg and "<svg onload" not in svg
    assert svg.count("<svg") == 1


def test_the_cover_wraps_chinese_by_character_and_names_the_title_for_assistive_tech():
    title = "为什么海水是咸的这个问题其实很有意思而且值得慢慢读"
    svg = typographic_cover_svg(title, language="zh", topic="科学").decode()
    assert f'aria-label="{title}"' in svg and f"<title>{title}</title>" in svg
    assert svg.count("<tspan") == 2  # 26 characters, 14 to a line
    assert "海" in svg  # the large glyph is the first character


def test_every_kind_is_tinted_by_a_skill_token_hue():
    tokens = thumbnails.design_tokens()
    for kind, name in thumbnails.KIND_HUE.items():
        assert tokens[name] in typographic_cover_svg("A title", kind=kind).decode().upper()


# ---- provenance, hosts, licences ---------------------------------------------------------------------

def test_provenance_requires_everything_for_a_picture_and_nothing_for_a_cover():
    assert normalize_provenance({}, kind="typographic")["licence"] == ""
    ok = normalize_provenance({**LICENCE, "source_url": GOOD_URL}, kind="library_image")
    assert ok["licence"] == "PD" and ok["kind"] == "library_image"
    for missing, code in (("author", "thumbnail_author_required"), ("licence_url", "thumbnail_licence_url_required"),
                          ("licence", "thumbnail_licence_not_allowed"), ("source_url", "thumbnail_host_not_allowed")):
        with pytest.raises(ThumbnailRefused) as caught:
            normalize_provenance({**LICENCE, "source_url": GOOD_URL, missing: ""}, kind="source_image")
        assert caught.value.code == code
    with pytest.raises(ThumbnailRefused):
        normalize_provenance({}, kind="ai_generated")


@pytest.mark.parametrize("url,allowed", [
    ("https://images-assets.nasa.gov/a.png", True), ("https://www.nasa.gov/a.png", True), ("https://nasa.gov/a.png", True),
    ("https://www.noaa.gov/a.png", True), ("https://www.nih.gov/a.png", True), ("https://www.gutenberg.org/a.jpg", True),
    ("https://upload.wikimedia.org/a.jpg", True), ("https://images.unsplash.com/a.jpg", True),
    ("https://images.pexels.com/a.jpg", True),
    ("https://evilnasa.gov/a.png", False), ("https://nasa.gov.evil.example/a.png", False),
    ("https://commons.wikimedia.org/a.jpg", False), ("http://images.pexels.com/a.jpg", False),
    ("https://example.com/a.jpg", False), ("javascript:alert(1)", False), ("", False),
])
def test_only_the_allow_listed_hosts_over_https(url, allowed):
    assert host_allowed(url) is allowed


@pytest.mark.parametrize("name,canonical", [
    ("Public domain", "PD"), ("CC0", "CC0"), ("CC BY 4.0", "CC BY"), ("cc-by-sa-4.0", "CC BY-SA"),
    ("Unsplash License", "Unsplash"), ("Pexels", "Pexels"),
])
def test_the_allowed_licences(name, canonical):
    assert thumbnails.canonical_licence(name) == canonical


@pytest.mark.parametrize("name", ["CC BY-NC", "CC BY-ND 4.0", "All rights reserved", "Fair use", "", "GPL"])
def test_other_licences_are_refused(name):
    assert thumbnails.canonical_licence(name) == ""


# ---- fetching a picture (mocked) ---------------------------------------------------------------------

def test_a_licensed_picture_is_fetched_through_the_guard_and_measured():
    fetcher = Fetcher(png(1200, 800))
    record, provenance = fetch_licensed_image(GOOD_URL, {**LICENCE, "kind": "source_image"}, fetcher=fetcher)
    assert record["content_type"] == "image/png" and (record["width"], record["height"]) == (1200, 800)
    assert provenance == {"kind": "source_image", "source_url": GOOD_URL, "author": "NASA/JPL", "licence": "PD",
                          "licence_url": LICENCE["licence_url"]}
    (url, kwargs), = fetcher.calls
    assert url == GOOD_URL and kwargs["max_bytes"] == 5 * 1024 * 1024
    assert "image/svg+xml" not in kwargs["content_types"]


def test_a_refused_host_or_licence_never_reaches_the_network():
    fetcher = Fetcher()
    with pytest.raises(ThumbnailRefused):
        fetch_licensed_image("https://example.com/a.png", LICENCE, fetcher=fetcher)
    with pytest.raises(ThumbnailRefused):
        fetch_licensed_image(GOOD_URL, {**LICENCE, "licence": "CC BY-NC"}, fetcher=fetcher)
    assert fetcher.calls == []


@pytest.mark.parametrize("fetcher,code", [
    (Fetcher(error=UnsafeMediaFetch("The media is too large.")), "image_too_large"),
    (Fetcher(body=b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"), "image_unsupported_type"),
    (Fetcher(body=b"<html></html>"), "image_unsupported_type"),
    (Fetcher(body=png(200, 200)), "image_too_small"),
    (Fetcher(body=png(3000, 400)), "image_bad_aspect"),
    (Fetcher(error=UnsafeMediaFetch("The media address is not allowed.")), "image_unsafe_url"),
])
def test_size_type_and_shape_are_checked_on_the_bytes(fetcher, code):
    with pytest.raises(ThumbnailRefused) as caught:
        fetch_licensed_image(GOOD_URL, LICENCE, fetcher=fetcher)
    assert caught.value.code == code


# ---- Reading: the publish gate ---------------------------------------------------------------------------

@pytest.fixture()
def gated(tmp_path):
    import sqlalchemy as sa

    from writing_coach.persistence.models import Base

    engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'content.db'}")
    Base.metadata.create_all(engine)
    store = MemoryStore()
    repository = ReadingContentRepository(engine)
    repository.ensure_built_in_sources()
    thumbnails.require_reading_thumbnails(repository, store)
    return repository, store


def _bare_article(repository, **kwargs):
    """An article made the way it was before admission gave every article its cover (the :8000 held articles)."""
    factory, repository.cover_factory = repository.cover_factory, None
    try:
        return _article(repository, **kwargs)
    finally:
        repository.cover_factory = factory


def test_an_article_without_a_thumbnail_cannot_be_published(gated):
    repository, store = gated
    article = _bare_article(repository)
    assert repository.has_thumbnail(article["id"]) is False
    with pytest.raises(ThumbnailRequired):
        repository.set_status(article["id"], LEARNER_VISIBLE_STATUS, actor="admin")
    assert repository.get_article(article["id"])["status"] != LEARNER_VISIBLE_STATUS
    stored = thumbnails.make_reading_cover(store, article_id=article["id"], title="Rain returns", language="en", topic="")
    assert repository.approve_image(article["id"], stored, actor="admin")
    assert repository.set_status(article["id"], LEARNER_VISIBLE_STATUS, actor="admin")["status"] == LEARNER_VISIBLE_STATUS
    assert repository.published_thumbnail(article["id"])["kind"] == "typographic"


def test_the_cover_is_what_the_learner_payload_and_the_serve_route_name(gated):
    repository, store = gated
    article = _article(repository)
    stored = thumbnails.make_reading_cover(store, article_id=article["id"], title="Rain returns", language="en", topic="")
    repository.approve_image(article["id"], stored, actor="admin")
    repository.set_status(article["id"], LEARNER_VISIBLE_STATUS, actor="admin")
    row = repository.list_published(language="en")["items"][0]
    assert row["image"]["typographic"] is True and row["image"]["credit"] == "" and row["image"]["alt"] == "Rain returns"
    assert row["image"]["url"].startswith(f"/api/reading/articles/{article['id']}/image?v=")
    served = repository.approved_image_asset(article["id"])
    assert served["content_type"] == "image/svg+xml" and store.get(served["asset_key"]).startswith(b"<svg")


def test_a_licensed_picture_shows_its_author_and_licence_and_needs_no_source_policy(gated):
    repository, store = gated
    article = _article(repository)
    record, provenance = fetch_licensed_image(GOOD_URL, LICENCE, fetcher=Fetcher(png(1200, 800)))
    stored = thumbnails.store_licensed(store, "reading", article["id"], record, provenance, alt="A river")
    repository.approve_image(article["id"], stored, actor="admin")
    repository.set_status(article["id"], LEARNER_VISIBLE_STATUS, actor="admin")
    image = repository.list_published(language="en")["items"][0]["image"]
    assert image["credit"] == "NASA/JPL · PD" and "typographic" not in image
    assert stored["licence_url"] == LICENCE["licence_url"] and stored["kind"] == "library_image"


def test_a_picture_with_no_credit_line_is_not_shown():
    approved = {"asset_key": "k", "kind": "library_image", "author": "", "licence": ""}
    assert learner_image(article_id="a", revision=1, policy_allowed=True, approved=approved, publisher="P") is None


def test_automatic_admission_makes_its_own_cover_or_waits_for_review(gated, monkeypatch):
    repository, store = gated
    monkeypatch.setattr("writing_coach.reading_admission.automatic_admission", lambda **kwargs: {"decision": "published"})

    def admit(native):
        snapshot = repository.record_source_item(
            source_id=repository.built_in_source_id("manual"), source_native_id=native, canonical_url="", title="T",
            author="A", published_at=None, language="en", body="Words " + native, content_hash=f"{abs(hash(native)):064x}"[:64],
            metadata={}, rights={"can_republish": True})
        return repository.create_article(
            source_item_id=snapshot["id"], title="Rain returns", body="Words " + native, excerpt="", language="en",
            topic="environment", estimated_level="B1", estimated_confidence=0.6, word_count=2, reading_time_seconds=5,
            analysis={}, targets=[], automatic_admission=True)

    assert admit("one")["status"] == LEARNER_VISIBLE_STATUS
    published = repository.list_published(language="en")["items"]
    assert len(published) == 1 and published[0]["image"]["typographic"] is True
    repository.cover_factory = None  # no way to make a cover: the engine must not publish a bare article
    assert admit("two")["status"] == "needs_review"


def test_every_admitted_article_gets_its_cover_even_when_it_waits_for_review(gated, monkeypatch):
    """The :8000 gap (2026-10-19): articles held for review were created bare, and publishing them failed with
    ThumbnailRequired. Admission now gives every new article its typographic cover, published or held."""
    repository, store = gated
    held = _article(repository)  # the direct submit path: no automatic admission, it waits for review
    assert held["status"] == "needs_review" and repository.has_thumbnail(held["id"])
    assert repository.image_review(held["id"])["approved"]["kind"] == "typographic"
    monkeypatch.setattr("writing_coach.reading_admission.automatic_admission",
                        lambda **kwargs: {"decision": "needs_review", "reasons": ["held"]})
    snapshot = repository.record_source_item(
        source_id=repository.built_in_source_id("manual"), source_native_id="held-2", canonical_url="", title="T",
        author="A", published_at=None, language="zh", body="雨回来了", content_hash="b" * 64, metadata={},
        rights={"can_republish": True})
    automatic = repository.create_article(
        source_item_id=snapshot["id"], title="雨回来了", body="雨回来了", excerpt="", language="zh", topic="",
        estimated_level="HSK2", estimated_confidence=0.5, word_count=4, reading_time_seconds=5, analysis={},
        targets=[], automatic_admission=True)
    assert automatic["status"] == "needs_review" and repository.has_thumbnail(automatic["id"])
    assert repository.set_status(automatic["id"], LEARNER_VISIBLE_STATUS, actor="admin")["status"] == LEARNER_VISIBLE_STATUS
    assert repository.published_thumbnail(automatic["id"])["kind"] == "typographic"


def test_a_cover_that_cannot_be_made_never_loses_the_article(gated):
    repository, _ = gated

    def broken(_item):
        raise OSError("disk full")

    repository.cover_factory = broken
    article = _article(repository)
    assert article["status"] == "needs_review" and repository.has_thumbnail(article["id"]) is False


# ---- Reading: the admin routes -----------------------------------------------------------------------------

def _candidate(images):  # noqa: F811
    response = call(images["admin"], "POST", "/api/admin/reading/jobs",
                    data={"kind": "text", "text": ARTICLE, "title": "Rain returns", "language": "en",
                          "can_republish": "true", "attribution_required": "false"})
    assert response.status_code == 202
    return images["engine"].process(images["jobs"].claim("worker-1"))["article_id"]


def test_the_publish_route_refuses_with_thumbnail_required_then_accepts_a_typographic_cover(images):  # noqa: F811
    images["content"].require_thumbnail = True
    article_id = _candidate(images)
    refused = call(images["admin"], "POST", f"/api/admin/reading/articles/{article_id}/status", json={"status": "published"})
    assert refused.status_code == 409 and refused.json()["detail"]["category"] == "thumbnail_required"
    made = call(images["admin"], "POST", f"/api/admin/reading/articles/{article_id}/thumbnail/typographic", json={})
    assert made.status_code == 200 and made.json()["approved"]["kind"] == "typographic"
    again = call(images["admin"], "POST", f"/api/admin/reading/articles/{article_id}/thumbnail/typographic", json={})
    assert again.status_code == 200  # the same bytes, the same key: idempotent
    assert call(images["admin"], "POST", f"/api/admin/reading/articles/{article_id}/status",
                json={"status": "published"}).status_code == 200
    served = call(images["learner"], "GET", f"/api/reading/articles/{article_id}/image")
    assert served.status_code == 200 and served.headers["content-type"].startswith("image/svg+xml")
    assert "sandbox" in served.headers["content-security-policy"]
    assert call(images["admin"], "POST", f"/api/admin/reading/articles/{article_id}/thumbnail/typographic",
                json={}, admin=False).status_code == 403


def test_attach_from_url_checks_host_licence_and_records_an_audited_provenance(images):  # noqa: F811
    article_id = _candidate(images)
    images["fetcher"].body = png(1200, 800)
    url = f"/api/admin/reading/articles/{article_id}/thumbnail/from-url"
    body = {"url": GOOD_URL, "kind": "source_image", **LICENCE}
    for bad, code in (({"url": "https://example.com/a.png"}, "thumbnail_host_not_allowed"),
                      ({"licence": "CC BY-NC"}, "thumbnail_licence_not_allowed"),
                      ({"author": ""}, "thumbnail_author_required"),
                      ({"licence_url": ""}, "thumbnail_licence_url_required")):
        refused = call(images["admin"], "POST", url, json={**body, **bad})
        assert refused.status_code == 422 and refused.json()["detail"]["category"] == code
    assert images["fetcher"].calls == [] and images["store"].files == {}
    done = call(images["admin"], "POST", url, json={**body, "alt": "Mars"})
    assert done.status_code == 200 and done.json()["approved"]["kind"] == "source_image"
    assert len(images["fetcher"].calls) == 1
    folded = images["content"].published_thumbnail(article_id)
    assert folded is None or folded["licence"] == "PD"  # not published yet: nothing is shown
    approved = images["content"].image_review(article_id)["approved"]
    assert approved["alt"] == "Mars"
    assert any(row["action"] == "admin.reading_thumbnail_attached" for row in images["audit"])
    assert call(images["admin"], "POST", url, json=body, admin=False).status_code == 403
    too_big = images["fetcher"]
    too_big.error = UnsafeMediaFetch("The media is too large.")
    big = call(images["admin"], "POST", url, json=body)
    assert big.status_code == 422 and big.json()["detail"]["category"] == "image_too_large"


# ---- vocabulary collections ------------------------------------------------------------------------------

@pytest.fixture()
def vocabulary(tmp_path):
    repository = sqlite_vocabulary_repository(tmp_path / "vocabulary.db")
    repository.initialize()
    return repository


def test_a_collection_is_published_only_with_a_thumbnail(vocabulary):
    store = MemoryStore()
    collection_id = _collection(vocabulary)
    _admit(vocabulary, collection_id)  # a bare repository stays permissive
    vocabulary.set_collection_status(collection_id, "unpublished", actor="admin")
    vocabulary.cover_store = store  # the application sets this at wiring
    with pytest.raises(ThumbnailRequired):
        vocabulary.set_collection_status(collection_id, "published", actor="admin")
    stored = thumbnails.make_cover(store, "vocabulary", collection_id, title="A pack", language="en", topic="TOEIC",
                                   kind="vocabulary")
    summary = vocabulary.set_collection_thumbnail(collection_id, stored)
    assert summary["thumbnail"]["stored"] is True and summary["thumbnail"]["alt"] == "A pack"
    assert vocabulary.set_collection_status(collection_id, "published", actor="admin")["catalog_status"] == "published"
    assert vocabulary.collection_thumbnail(collection_id)["asset_key"] == stored["asset_key"]


def test_the_import_pipeline_publishes_with_a_cover_it_makes(vocabulary):
    store = MemoryStore()
    vocabulary.cover_store = store
    collection_id = _collection(vocabulary, "auto-pack")
    _admit(vocabulary, collection_id)
    stored = vocabulary.collection_thumbnail(collection_id)
    assert stored["kind"] == "typographic" and store.get(stored["asset_key"]).startswith(b"<svg")
    view = vocabulary.list_collections("en")[0]["thumbnail"]
    assert view["url"].startswith("/api/vocabulary/library/collections/auto-pack/cover?v=") and view["credit"] == ""


def test_a_static_collection_still_gets_a_cover_view():
    view = thumbnails.collection_view("common-3000", "3000 Common Words", {})
    assert view["kind"] == "typographic" and view["stored"] is False and view["alt"] == "3000 Common Words"


# ---- media -----------------------------------------------------------------------------------------------------

def _entry(**changes):
    base = MediaLibraryEntry(
        media_id="direct-1", media_type="audio", provider="direct", provider_media_id="direct-1", canonical_url="",
        playback={"provider": "orena", "kind": "audio", "url": "/api/media/files/media/direct-1/a.mp3"}, title="A talk",
        thumbnail={"kind": "none", "ref": ""}, duration_ms=1000, language="en", level="B1", creator="",
        source={"provider": "direct", "type": "upload", "provenance_url": "", "license": "own", "review_status": "ok",
                "imported_by": "admin"},
        library="shared", created_at="2026-10-19T00:00:00+00:00", lesson=None, status="published")
    return replace(base, **changes)


def test_a_provider_thumbnail_counts_and_an_empty_one_does_not():
    assert thumbnails.has_media_thumbnail({"kind": "provider-url", "ref": "https://i.ytimg.com/vi/x/hqdefault.jpg"})
    assert thumbnails.has_media_thumbnail({"kind": "asset", "ref": "media/direct-1/thumb.svg"})
    assert not thumbnails.has_media_thumbnail({"kind": "none", "ref": ""})
    assert not thumbnails.has_media_thumbnail(None)


def test_media_gets_a_cover_under_the_directory_its_entry_owns():
    store = MemoryStore()
    covered = thumbnails.media_entry_with_cover(_entry(), store)
    ref = covered.thumbnail["ref"]
    assert covered.thumbnail["kind"] == "asset" and ref.startswith("media/direct-1/thumb-") and ref.endswith(".svg")
    assert covered.source["thumbnail_kind"] == "typographic" and store.get(ref).startswith(b"<svg")
    assert thumbnails.media_thumbnail_provenance(covered.source)["kind"] == "typographic"


@pytest.fixture()
def media_console(console_setup, monkeypatch):  # noqa: F811
    assets = MemoryStore()
    # The module's globals are shared with other tests in this worker: put back exactly what was there.
    before = (media_library_api._store, media_library_api._asset_store, media_library_api._importer,
              media_library_api._admin_guard, media_library_api._language_supported)
    media_library_api.configure_media_library(
        console_setup["store"], assets, object(), admin_guard=lambda request: {"email": "admin@example.com"},
        language_supported=lambda code: True)
    app = console_setup["app"]
    app.include_router(media_library_api.router)
    entry = console_setup["store"].get("youtube-abcdefghijk")
    console_setup["store"].upsert(replace(
        entry, status="review", thumbnail={"kind": "none", "ref": ""}, source={**entry.source, "rights": "cleared"},
        lesson={"payload": {"transcript": {"segments": [
            {"start_ms": 0, "end_ms": 42000, "original_text": "各位旅客请注意，开往北京的列车马上到站，请准备上车。"}]}}}))
    yield {**console_setup, "assets": assets, "http": app}
    (media_library_api._store, media_library_api._asset_store, media_library_api._importer,
     media_library_api._admin_guard, media_library_api._language_supported) = before


MEDIA_ID = "youtube-abcdefghijk"
CONSOLE = "/api/admin/console/content"


def test_media_is_published_only_with_a_thumbnail_and_the_cover_is_served_as_a_sandboxed_image(media_console):
    app = media_console["http"]
    refused = console_call(app, "POST", f"{CONSOLE}/media/{MEDIA_ID}/status", json={"status": "published"})
    assert refused.status_code == 409 and refused.json()["detail"]["category"] == "thumbnail_required"
    assert media_console["store"].get(MEDIA_ID).status == "review"
    made = console_call(app, "POST", f"{CONSOLE}/media/{MEDIA_ID}/thumbnail", json={"mode": "typographic"})
    assert made.status_code == 200 and made.json()["thumbnail"]["kind"] == "typographic"
    entry = media_console["store"].get(MEDIA_ID)
    assert entry.thumbnail["kind"] == "asset" and entry.source["thumbnail_kind"] == "typographic"
    assert console_call(app, "POST", f"{CONSOLE}/media/{MEDIA_ID}/status", json={"status": "published"}).status_code == 200
    served = console_call(app, "GET", f"/api/media/files/{entry.thumbnail['ref']}?variant=thumb")
    assert served.status_code == 200 and served.headers["content-type"].startswith("image/svg+xml")
    assert "sandbox" in served.headers["content-security-policy"] and served.content.startswith(b"<svg")


def test_a_stored_svg_that_is_not_our_cover_is_still_never_an_image(media_console):
    app = media_console["http"]
    console_call(app, "POST", f"{CONSOLE}/media/{MEDIA_ID}/status", json={"status": "published"})
    for key, body in ((f"media/{MEDIA_ID}/evil.svg", b"<svg xmlns='http://www.w3.org/2000/svg' onload='alert(1)'/>"),
                      (f"media/{MEDIA_ID}/thumb-{'a' * 24}.svg", b"<svg xmlns='http://www.w3.org/2000/svg' onload='alert(1)'/>"),
                      (f"media/{MEDIA_ID}/thumb-{'b' * 24}.svg",
                       typographic_cover_svg("x").replace(b"<title>", b"<script>alert(1)</script><title>"))):
        media_console["assets"].put(key, body)
        response = console_call(app, "GET", f"/api/media/files/{key}")
        assert not response.headers["content-type"].startswith("image/svg+xml"), key


def test_media_attach_from_url_records_the_licence_and_refuses_the_rest(media_console, monkeypatch):
    app = media_console["http"]
    monkeypatch.setattr(thumbnails, "FETCHER", Fetcher(png(1200, 800)))
    body = {"mode": "url", "url": "https://upload.wikimedia.org/wikipedia/commons/a/a1/Train.png", "author": "A. Tran",
            "licence": "CC BY-SA 4.0", "licence_url": "https://creativecommons.org/licenses/by-sa/4.0/", "kind": "library_image"}
    for bad, code in (({"licence": "CC BY-NC"}, "thumbnail_licence_not_allowed"),
                      ({"url": "https://example.com/a.png"}, "thumbnail_host_not_allowed"),
                      ({"mode": "ai"}, "thumbnail_mode_invalid")):
        refused = console_call(app, "POST", f"{CONSOLE}/media/{MEDIA_ID}/thumbnail", json={**body, **bad})
        assert refused.status_code == 422 and refused.json()["detail"]["category"] == code
    assert thumbnails.FETCHER.calls == []
    done = console_call(app, "POST", f"{CONSOLE}/media/{MEDIA_ID}/thumbnail", json=body)
    assert done.status_code == 200, done.text
    source = media_console["store"].get(MEDIA_ID).source
    assert thumbnails.media_thumbnail_provenance(source) == {
        "kind": "library_image", "source_url": body["url"], "author": "A. Tran", "licence": "CC BY-SA",
        "licence_url": body["licence_url"]}
    assert console_call(app, "POST", f"{CONSOLE}/media/{MEDIA_ID}/thumbnail", json=body, admin=False).status_code == 403
    assert console_call(app, "POST", f"{CONSOLE}/nothing/{MEDIA_ID}/thumbnail", json=body).status_code == 404


# ---- content packs ---------------------------------------------------------------------------------------------

def test_a_pack_round_trips_a_thumbnail_with_its_bytes_and_provenance():
    record, provenance = fetch_licensed_image(GOOD_URL, LICENCE, fetcher=Fetcher(png(1200, 800)))
    stored = thumbnails.stored_dict({**record, "alt": "Mars"}, "thumbnails/vocabulary/pack/abc.png", provenance)
    data = {"id": "pack", "language_code": "en", "entries": [], "thumbnail": thumbnails.pack_meta(stored)}
    raw = build_pack([PackItem(kind="vocabulary_collection", natural_key="pack", data=data)], created_by="t",
                     environment="test", app_version="1", filters={},
                     assets={stored["asset_key"]: record["data"]})
    pack = read_pack(raw)
    meta = pack.items[0].data["thumbnail"]
    parsed, back = thumbnails.read_pack_thumbnail(meta, pack.assets)
    assert parsed["data"] == record["data"] and back["licence"] == "PD" and back["author"] == "NASA/JPL"
    assert pack.manifest["version"] == 2


def test_a_pack_thumbnail_that_does_not_verify_fails_the_item():
    record, provenance = fetch_licensed_image(GOOD_URL, LICENCE, fetcher=Fetcher(png(1200, 800)))
    stored = thumbnails.stored_dict(record, "thumbnails/vocabulary/pack/abc.png", provenance)
    meta = thumbnails.pack_meta(stored)
    assets = {f"assets/{stored['asset_key']}": record["data"]}
    assert thumbnails.read_pack_thumbnail(meta, assets) is not None
    for broken, code in (
        ({**meta, "licence": "CC BY-NC"}, "thumbnail_licence_not_allowed"),
        ({**meta, "source_url": "https://example.com/a.png"}, "thumbnail_host_not_allowed"),
        ({**meta, "sha256": "0" * 64}, "thumbnail_pack_asset_invalid"),
        ({**meta, "asset_key": "thumbnails/other/x.png"}, "thumbnail_pack_asset_missing"),
    ):
        with pytest.raises(ThumbnailRefused) as caught:
            thumbnails.read_pack_thumbnail(broken, assets)
        assert caught.value.code == code
    with pytest.raises(ThumbnailRefused):
        thumbnails.read_pack_thumbnail(meta, {f"assets/{stored['asset_key']}": b"<svg onload=alert(1)>"})


def test_a_typographic_pack_thumbnail_is_never_read_from_the_pack():
    meta = {"kind": "typographic", "asset_key": "thumbnails/x/y/z.svg", "sha256": "0" * 64}
    assert thumbnails.read_pack_thumbnail(meta, {"assets/thumbnails/x/y/z.svg": b"<svg onload=x>"}) is None
    assert thumbnails.read_pack_thumbnail(None, {}) is None


# ---- the audit and the backfill ----------------------------------------------------------------------------------

class _FakeMedia:
    def __init__(self, *entries):
        self.entries = {entry.media_id: entry for entry in entries}

    def list(self, *, library="shared", status="published", **_):
        return [e for e in self.entries.values() if e.library == library and (status is None or e.status == status)]

    def get(self, media_id):
        return self.entries.get(media_id)

    def upsert(self, entry):
        self.entries[entry.media_id] = entry
        return entry


def test_the_audit_lists_published_items_without_a_thumbnail_and_the_backfill_covers_them(gated, vocabulary):
    repository, store = gated
    article = _bare_article(repository)
    repository.require_thumbnail = False  # before the rule: published bare
    repository.set_status(article["id"], LEARNER_VISIBLE_STATUS, actor="admin")
    collection_id = _collection(vocabulary)
    _admit(vocabulary, collection_id)
    youtube = _entry(media_id="yt-1", thumbnail={"kind": "provider-url", "ref": "https://i.ytimg.com/vi/x/hqdefault.jpg"})
    bare = _entry(media_id="up-1")
    draft = _entry(media_id="up-2", status="unpublished")
    media = _FakeMedia(youtube, bare, draft)
    sources = thumbnail_audit.Sources(reading=repository, reading_assets=store, vocabulary=vocabulary, media=media,
                                      media_assets=store)

    report = thumbnail_audit.audit(sources)
    assert {kind: [row["id"] for row in rows] for kind, rows in report["missing"].items()} == {
        "reading": [article["id"]], "vocabulary": [collection_id], "media": ["up-1"]}
    assert report["skipped"] == ["book"] and report["total_missing"] == 3
    assert [row["published"] for row in thumbnail_audit.audit(sources, include_unpublished=True)["missing"]["media"]] == [True, False]

    before = dict(store.files)
    dry = thumbnail_audit.backfill(sources)
    assert dry["dry_run"] is True and len(dry["items"]) == 3 and store.files == before
    assert media.entries["up-1"].thumbnail["kind"] == "none"

    applied = thumbnail_audit.backfill(sources, apply=True)
    assert applied["failed"] == [] and len(applied["items"]) == 3
    assert repository.has_thumbnail(article["id"]) and vocabulary.collection_thumbnail(collection_id) is not None
    assert thumbnails.has_media_thumbnail(media.entries["up-1"].thumbnail)
    assert media.entries["yt-1"].thumbnail["kind"] == "provider-url", "a provider-hosted thumbnail is left alone"
    assert thumbnail_audit.audit(sources)["total_missing"] == 0


def test_the_backfill_covers_named_review_articles_once_and_keeps_what_is_there(gated):
    repository, store = gated
    held = _bare_article(repository)
    other = _bare_article(repository, body="Another text about the harbour and its boats, long enough to read.")
    covered = _article(repository, body="A third text that was given its own cover when it was admitted here.")
    before = repository.image_review(covered["id"])["approved"]
    sources = thumbnail_audit.Sources(reading=repository, reading_assets=store)

    assert thumbnail_audit.audit(sources)["missing"]["reading"] == [], "the default sweep is published items only"
    in_review = thumbnail_audit.audit(sources, include_unpublished=True)["missing"]["reading"]
    assert sorted(row["id"] for row in in_review) == sorted([held["id"], other["id"]])
    assert {row["status"] for row in in_review} == {"needs_review"}

    files = dict(store.files)
    dry = thumbnail_audit.backfill(sources, ids=(held["id"], covered["id"], "missing-id"))
    assert dry["dry_run"] is True and store.files == files and repository.has_thumbnail(held["id"]) is False
    assert {(i["id"], i["action"]) for i in dry["items"]} == {
        (held["id"], "would_add_typographic_cover"), (covered["id"], "kept_existing_thumbnail")}
    assert dry["failed"] == [{"kind": "reading", "id": "missing-id", "title": "", "error": "not_found"}]

    applied = thumbnail_audit.backfill(sources, apply=True, ids=(held["id"], held["id"]))
    assert applied["failed"] == [] and [i["action"] for i in applied["items"]] == ["typographic_cover_added"]
    approved = repository.published_thumbnail(held["id"])
    assert approved["kind"] == "typographic" and store.get(approved["asset_key"]).startswith(b"<svg")
    assert repository.has_thumbnail(other["id"]) is False, "--id covers only the named articles"
    assert repository.image_review(covered["id"])["approved"] == before, "an existing thumbnail is never replaced"
    assert repository.set_status(held["id"], LEARNER_VISIBLE_STATUS, actor="admin")["status"] == LEARNER_VISIBLE_STATUS

    again = thumbnail_audit.backfill(sources, apply=True, ids=(held["id"],))
    assert [i["action"] for i in again["items"]] == ["kept_existing_thumbnail"], "idempotent"
    swept = thumbnail_audit.backfill(sources, apply=True, include_unpublished=True)
    assert [i["id"] for i in swept["items"]] == [other["id"]] and swept["failed"] == []
    assert thumbnail_audit.audit(sources, include_unpublished=True)["missing"]["reading"] == []


class _FakeBooks:
    def __init__(self):
        self.covers = {}
        self.rows = [{"id": "b1", "title": "A Book", "author": "Ann", "learning_language": "en", "cover_asset_key": None},
                     {"id": "b2", "title": "Covered", "author": "Bo", "learning_language": "en", "cover_asset_key": "books/b2/cover.jpg"}]

    def list_books(self, *, learning_language, cursor=None, limit=50):
        return {"items": [r for r in self.rows if r["learning_language"] == learning_language], "next_cursor": None}

    def set_cover_key(self, book_id, key):
        self.covers[book_id] = key
        return True


def test_books_without_a_cover_get_one():
    books, store = _FakeBooks(), MemoryStore()
    sources = thumbnail_audit.Sources(books=books, reading_assets=store)
    assert [row["id"] for row in thumbnail_audit.audit(sources)["missing"]["book"]] == ["b1"]
    thumbnail_audit.backfill(sources, apply=True)
    assert books.covers == {"b1": "books/b1/cover.svg"} and store.get("books/b1/cover.svg").startswith(b"<svg")


def test_the_scripts_are_dry_run_by_default_and_never_print_a_url():
    audit_source = (ROOT / "scripts" / "audit_thumbnails.py").read_text(encoding="utf-8")
    backfill_source = (ROOT / "scripts" / "backfill_typographic_covers.py").read_text(encoding="utf-8")
    assert 'add_argument("--apply", action="store_true"' in backfill_source
    assert "apply=args.apply" in backfill_source
    assert '"--include-unpublished"' in backfill_source and 'action="append"' in backfill_source
    assert "print(args.url" not in audit_source + backfill_source
    assert "backfill" not in audit_source.split("def main", 1)[1], "the audit never writes"


def test_the_decision_is_recorded():
    log = (ROOT / "docs" / "project" / "DECISION_LOG.md").read_text(encoding="utf-8")
    entry = log.split("## D-240 ", 1)[1].split("\n## D-", 1)[0]
    assert "ACCEPTED (owner, 2026-10-19 11:28, relayed by Hermes)" in entry
    assert "Bài nào cũng cần có ảnh thumbnail hết nhé, không được để trống." in entry


# ---- redirects and the EPUB cover record (review of #354) --------------------------------------------------------

def _redirect(monkeypatch, new_url):
    """The redirect handler of the real fetch, asked about one hop; DNS answers a public address."""
    import socket
    from urllib.request import Request

    from writing_coach import media_safe_fetch

    monkeypatch.setattr(media_safe_fetch.socket, "getaddrinfo",
                        lambda host, port, **_: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))])
    handler = media_safe_fetch._CheckedRedirects(max_redirects=3, allowed_hosts=frozenset(thumbnails.ALLOWED_HOSTS))
    return handler.redirect_request(Request(GOOD_URL), None, 302, "Found", {}, new_url)


def test_a_redirect_to_a_foreign_host_is_refused_at_every_hop(monkeypatch):
    for target in ("https://evil.example/a.png", "https://nasa.gov.evil.example/a.png", "https://evilnasa.gov/a.png",
                   "https://commons.wikimedia.org/a.png"):
        with pytest.raises(UnsafeMediaFetch):
            _redirect(monkeypatch, target)


def test_a_redirect_inside_the_allow_list_is_followed(monkeypatch):
    for target in ("https://www.nasa.gov/a.png", "https://images-assets.nasa.gov/b.png", "https://upload.wikimedia.org/c.jpg"):
        assert _redirect(monkeypatch, target).full_url == target


def test_the_allow_list_travels_into_the_fetch_so_redirects_are_checked():
    fetcher = Fetcher(png(1200, 800))
    fetch_licensed_image(GOOD_URL, LICENCE, fetcher=fetcher)
    assert fetcher.calls[0][1]["allowed_hosts"] == frozenset(thumbnails.ALLOWED_HOSTS)


def _epub_with_cover(title):
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("META-INF/container.xml",
                    '<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">'
                    '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
                    "</rootfiles></container>")
        zf.writestr("OEBPS/content.opf",
                    '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
                    f'<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>{title}</dc:title>'
                    '<dc:language>en</dc:language><meta name="cover" content="cover-img"/></metadata>'
                    '<manifest><item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/>'
                    '<item id="cover-img" href="cover.jpg" media-type="image/jpeg"/></manifest>'
                    '<spine><itemref idref="c1"/></spine></package>')
        zf.writestr("OEBPS/c1.xhtml", '<html xmlns="http://www.w3.org/1999/xhtml"><body><p>Hello world.</p></body></html>')
        zf.writestr("OEBPS/cover.jpg", b"\xff\xd8\xff\xe0fakejpegbytes")
    return buffer.getvalue()


def test_every_book_cover_has_its_provenance_stored_beside_it():
    import json

    from tests.test_reading_library_api import _client, _minimal_epub_bytes

    client, repo, store = _client()
    for title, raw, expected_kind in (("Embedded", _epub_with_cover("Embedded"), "source_image"),
                                      ("Plain", _minimal_epub_bytes("Plain"), "typographic")):
        response = client.post("/api/reading/library/import", files=[("files", ("b.epub", raw, "application/epub+zip"))],
                               data={"learning_language": "en"}, headers={"x-test-admin": "1"})
        book_id = response.json()["results"][0]["book_id"]
        cover_key = repo.get_book(book_id)["cover_asset_key"]
        assert cover_key and cover_key in store.data, title
        recorded = json.loads(store.data[f"books/{book_id}/cover.provenance.json"])
        assert recorded["kind"] == expected_kind, title
    assert recorded["licence"] == "" and len(recorded["sha256"]) == 64
    assert cover_key.endswith(".svg")
