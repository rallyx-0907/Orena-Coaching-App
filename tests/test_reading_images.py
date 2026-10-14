"""D-194 (proposed): a Reading card shows a real picture only under three conditions at once.

The source's image policy allows it (off by default), an administrator approved that candidate, and a credit
exists. Otherwise the learner gets the generated letter tile. The picture is fetched once, at approval, through
the existing SSRF guard, kept in the asset store and served same-origin; no learner payload ever names the
publisher's address.
"""
from __future__ import annotations

import struct
import uuid
from urllib.parse import urlsplit

import pytest
from sqlalchemy import update

from tests.test_reading_engine_routes import _publish_one, call, setup  # noqa: F401 - the route fixture
from writing_coach import media_safe_fetch
from writing_coach import reading_admin_api as admin_api
from writing_coach import reading_articles_api as learner_api
from writing_coach.book_asset_store import AssetNotFound
from writing_coach.media_safe_fetch import UnsafeMediaFetch
from writing_coach.persistence.models import ReadingSourceItem
from writing_coach.reading_admission import automatic_admission
from writing_coach.reading_images import (
    ImageRefused,
    assess_candidates,
    fetch_image,
    image_policy_allowed,
    learner_image,
    shared_url_counts,
    sniff_image,
    with_image_policy,
)

IMAGE_URL = "https://media.example.org/photos/river-flood.jpg"
OTHER_URL = "https://media.example.org/photos/second.png"
ADMIN_BASE = "/api/admin/reading"


def png(width=800, height=500, extra=b""):
    header = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + struct.pack(">II", width, height) + b"\x08\x06\x00\x00\x00"
    return header + b"\x00" * 16 + extra


def jpeg(width=800, height=500):
    sof = b"\xff\xc0" + struct.pack(">HBHHB", 17, 8, height, width, 3) + b"\x01\x11\x00\x02\x11\x00\x03\x11\x00"
    return b"\xff\xd8" + b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + sof + b"\xff\xd9"


def gif(width=800, height=500):
    return b"GIF89a" + struct.pack("<HH", width, height) + b"\x00\x00\x00"


def webp_vp8x(width=800, height=500):
    return (b"RIFF" + b"\x00\x00\x00\x00" + b"WEBPVP8X" + b"\x0a\x00\x00\x00" + b"\x00\x00\x00\x00"
            + (width - 1).to_bytes(3, "little") + (height - 1).to_bytes(3, "little"))


class MemoryStore:
    def __init__(self):
        self.files = {}

    def put(self, key, data):
        self.files[key] = data

    def get(self, key):
        try:
            return self.files[key]
        except KeyError as exc:
            raise AssetNotFound(key) from exc

    def exists(self, key):
        return key in self.files

    def delete(self, key):
        self.files.pop(key, None)

    def delete_prefix(self, prefix):
        return 0


class Fetcher:
    """Stands in for media_safe.fetch_bounded: records every call and serves a prepared body."""

    def __init__(self, body=None, error=None):
        self.body, self.error, self.calls = body if body is not None else png(), error, []

    def __call__(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error:
            raise self.error
        return self.body, "image/png"


# ---- pure rules ----------------------------------------------------------------------------------

@pytest.mark.parametrize("data,expected", [
    (png(640, 480), ("image/png", 640, 480)),
    (jpeg(1200, 630), ("image/jpeg", 1200, 630)),
    (gif(500, 500), ("image/gif", 500, 500)),
    (webp_vp8x(900, 600), ("image/webp", 900, 600)),
], ids=["png", "jpeg", "gif", "webp"])
def test_images_are_recognised_by_their_bytes_and_measured(data, expected):
    assert sniff_image(data) == expected


@pytest.mark.parametrize("data", [
    b"<svg xmlns='http://www.w3.org/2000/svg' width='800' height='500'></svg>",
    b"<html><body>not a picture</body></html>",
    b"",
    b"\x89PNG\r\n\x1a\n",
    b"%PDF-1.7",
], ids=["svg", "html", "empty", "truncated-png", "pdf"])
def test_svg_html_and_truncated_files_are_not_pictures(data):
    assert sniff_image(data) is None


def test_the_source_policy_is_off_unless_it_was_turned_on():
    assert image_policy_allowed({}) is False
    assert image_policy_allowed(None) is False
    assert image_policy_allowed({"image_policy": {"allowed": "yes"}}) is False
    assert image_policy_allowed(with_image_policy({"keep": 1}, True)) is True
    assert with_image_policy({"keep": 1}, False) == {"keep": 1, "image_policy": {"allowed": False}}


def test_candidates_are_ordered_and_filtered_by_their_declared_shape():
    media = [
        {"role": "inline", "url": "https://x.example/a.jpg", "source": "article:img", "width": 800, "height": 600},
        {"role": "hero", "url": "https://x.example/hero.jpg", "source": "article:img", "width": 0, "height": 0},
        {"role": "og", "url": "https://x.example/og.jpg", "source": "meta:og:image", "width": 0, "height": 0},
        {"role": "inline", "url": "https://x.example/small.jpg", "source": "article:img", "width": 300, "height": 300},
        {"role": "inline", "url": "https://x.example/wide.jpg", "source": "article:img", "width": 2400, "height": 500},
        {"role": "inline", "url": "https://x.example/shared.jpg", "source": "article:img", "width": 800, "height": 600},
        {"role": "inline", "url": "javascript:alert(1)", "source": "article:img"},
    ]
    rows = assess_candidates(media, shared_counts={"https://x.example/shared.jpg": 2},
                             rejected=frozenset({"https://x.example/a.jpg"}))
    assert [row["index"] for row in rows[:3]] == [2, 1, 0], "og first, then the hero, then the rest"
    reasons = {row["index"]: row["reason"] for row in rows}
    assert reasons == {2: "", 1: "", 0: "rejected", 3: "small", 4: "aspect", 5: "shared"}
    assert all("url" not in row for row in rows), "a review row names an index, never an address"


def test_an_address_carried_by_other_items_of_the_source_is_counted():
    counts = shared_url_counts([[{"url": "https://x.example/logo.png"}], [{"url": "https://x.example/logo.png"},
                                {"url": "https://x.example/b.png"}], []])
    assert counts == {"https://x.example/logo.png": 2, "https://x.example/b.png": 1}


@pytest.mark.parametrize("policy,approved,publisher,shown", [
    (False, {"asset_key": "k", "credit": "Photo: A"}, "Pub", False),
    (True, None, "Pub", False),
    (True, {"asset_key": "", "credit": "Photo: A"}, "Pub", False),
    (True, {"asset_key": "k", "credit": ""}, "", False),
    (True, {"asset_key": "k", "credit": ""}, "Pub", True),
    (True, {"asset_key": "k", "credit": "Photo: A"}, "", True),
])
def test_the_three_conditions_are_all_needed(policy, approved, publisher, shown):
    image = learner_image(article_id="a" * 8 + "-" + "b" * 27, revision=3, policy_allowed=policy,
                          approved=approved, publisher=publisher)
    assert (image is not None) is shown
    if image:
        assert image["url"].endswith("/image?v=3") and image["credit"] == (approved["credit"] or publisher)


# ---- the fetch ----------------------------------------------------------------------------------

def test_a_good_picture_is_fetched_under_the_shared_guard_with_a_byte_budget_and_a_type_allowlist():
    fetcher = Fetcher(png(800, 500))
    fetched = fetch_image(IMAGE_URL, fetcher=fetcher)
    assert (fetched["content_type"], fetched["ext"], fetched["width"], fetched["height"]) == ("image/png", "png", 800, 500)
    _, options = fetcher.calls[0]
    assert options["max_bytes"] == 5 * 1024 * 1024 and options["timeout"] <= 15
    assert options["content_types"] == frozenset({"image/jpeg", "image/png", "image/webp", "image/gif"})


@pytest.mark.parametrize("body,code", [
    (b"<svg></svg>", "image_unsupported_type"),
    (png(300, 300), "image_too_small"),
    (png(3000, 400), "image_bad_aspect"),
    (png(800, 500, extra=b"\x00" * (5 * 1024 * 1024)), "image_too_large"),
], ids=["svg", "small", "aspect", "oversize"])
def test_what_is_not_a_usable_picture_is_refused(body, code):
    with pytest.raises(ImageRefused) as refusal:
        fetch_image(IMAGE_URL, fetcher=Fetcher(body))
    assert refusal.value.code == code


@pytest.mark.parametrize("message,code", [
    ("This media file is too large.", "image_too_large"),
    ("This media type is not supported.", "image_unsupported_type"),
    ("This media address is not allowed.", "image_unsafe_url"),
    ("The media address could not be fetched.", "image_fetch_failed"),
])
def test_the_guard_refusals_become_image_refusals(message, code):
    with pytest.raises(ImageRefused) as refusal:
        fetch_image(IMAGE_URL, fetcher=Fetcher(error=UnsafeMediaFetch(message)))
    assert refusal.value.code == code


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.org/a.png", "javascript:alert(1)", "//example.org/a.png", ""])
def test_only_http_and_https_addresses_are_fetched(url):
    fetcher = Fetcher()
    with pytest.raises(ImageRefused):
        fetch_image(url, fetcher=fetcher)
    assert fetcher.calls == []


@pytest.mark.parametrize("address", [
    "127.0.0.1", "10.0.0.5", "172.16.3.4", "192.168.1.9", "169.254.169.254", "100.64.0.1", "0.0.0.0", "::1", "fe80::1", "fd00::1",
])
def test_private_loopback_link_local_and_metadata_addresses_are_refused_with_the_real_guard(monkeypatch, address):
    """Not the injected fetcher: the default one, with only the resolver replaced."""
    family = 10 if ":" in address else 2
    monkeypatch.setattr(media_safe_fetch.socket, "getaddrinfo", lambda *a, **k: [(family, 1, 6, "", (address, 443))])
    with pytest.raises(ImageRefused) as refusal:
        fetch_image("https://photos.example.org/a.png")
    assert refusal.value.code == "image_unsafe_url"


def test_a_name_that_resolves_to_both_a_public_and_a_private_address_is_refused(monkeypatch):
    monkeypatch.setattr(media_safe_fetch.socket, "getaddrinfo",
                        lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443)), (2, 1, 6, "", ("10.0.0.1", 443))])
    with pytest.raises(ImageRefused) as refusal:
        fetch_image("https://photos.example.org/a.png")
    assert refusal.value.code == "image_unsafe_url"


def test_a_redirect_to_a_private_host_is_refused_on_each_hop(monkeypatch):
    """The redirect handler re-validates every target with the same resolver."""
    answers = {"photos.example.org": "93.184.216.34", "internal.example.org": "10.1.2.3"}

    def resolve(host, port, **kwargs):
        return [(2, 1, 6, "", (answers.get(host, host), port))]

    monkeypatch.setattr(media_safe_fetch.socket, "getaddrinfo", resolve)
    handler = media_safe_fetch._CheckedRedirects(max_redirects=3)
    request = media_safe_fetch.Request("https://photos.example.org/a.png")
    with pytest.raises(UnsafeMediaFetch):
        handler.redirect_request(request, None, 302, "Found", {}, "https://internal.example.org/secret.png")
    with pytest.raises(UnsafeMediaFetch):
        handler.redirect_request(request, None, 302, "Found", {}, "http://169.254.169.254/latest/meta-data")


def test_the_fetch_sends_no_cookies_or_credentials():
    import inspect

    source = inspect.getsource(media_safe_fetch._open)
    assert "HTTPCookieProcessor" not in source and "Authorization" not in source


# ---- the routes ---------------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _fresh_preview_cache():
    """The admin preview cache is module state; no test may see another's fetched picture."""
    admin_api._preview_cache.clear()
    yield
    admin_api._preview_cache.clear()


@pytest.fixture()
def images(setup):  # noqa: F811
    store, fetcher = MemoryStore(), Fetcher()
    engine_service, content = setup["engine"], setup["content"]
    admin_api.configure_reading_admin(
        admin_guard=admin_api._state.admin_guard, content=content, jobs=setup["jobs"], engine=engine_service,
        audit=admin_api._state.audit, asset_store=store, image_fetcher=fetcher,
    )
    learner_api.configure_reading_articles(content, language_supported=lambda code: code in {"en", "zh"}, asset_store=store)
    # The credit fallback is the learner-facing name (D-192); the built-in "Manual paste" is not one.
    content.set_source_public_name(content.built_in_source_id("manual"), "Orena Reading Desk")
    setup.update(store=store, fetcher=fetcher)
    return setup


def _article_with_candidates(parts, media=None):
    article_id = _publish_one(parts)
    item_id = parts["content"].get_article(article_id)["source"]["id"]
    media = media if media is not None else [
        {"role": "og", "url": IMAGE_URL, "alt": "A flooded field", "caption": "", "credit": "",
         "width": 0, "height": 0, "source": "meta:og:image"},
        {"role": "inline", "url": OTHER_URL, "alt": "", "caption": "", "credit": "Photo: R. Tran",
         "width": 900, "height": 600, "source": "article:img"},
    ]
    with parts["content"].engine.begin() as connection:
        connection.execute(update(ReadingSourceItem).where(ReadingSourceItem.id == uuid.UUID(item_id))
                           .values(metadata_json={"extraction": {"media": media}}))
    return article_id


def _source_id(parts, article_id):
    return parts["content"].get_article(article_id)["source"]["source_id"]


def _policy(parts, article_id, allowed):
    return call(parts["admin"], "POST", f"{ADMIN_BASE}/sources/{_source_id(parts, article_id)}/image-policy",
                json={"allowed": allowed})


def _approve(parts, article_id, index=0, **body):
    return call(parts["admin"], "POST", f"{ADMIN_BASE}/articles/{article_id}/images/{index}/approve", json=body)


def _learner(parts, article_id):
    return call(parts["learner"], "GET", f"/api/reading/articles/{article_id}", admin=False)


def test_every_source_starts_with_images_off(images):
    sources = call(images["admin"], "GET", f"{ADMIN_BASE}/sources").json()["items"]
    assert sources and all(source["image_policy"] == {"allowed": False} for source in sources)


def test_nothing_is_fetched_or_shown_while_the_source_policy_is_off(images):
    article_id = _article_with_candidates(images)
    refused = _approve(images, article_id)
    assert refused.status_code == 409 and refused.json()["detail"]["category"] == "reading_image_policy_off"
    assert images["fetcher"].calls == [] and images["store"].files == {}
    detail = _learner(images, article_id).json()
    assert detail["image"] is None


def test_an_approved_picture_reaches_the_learner_only_as_a_same_origin_copy(images):
    article_id = _article_with_candidates(images)
    before = _learner(images, article_id).json()["content_revision"]
    assert _policy(images, article_id, True).json()["image_policy"] == {"allowed": True}
    approved = _approve(images, article_id, 0)
    assert approved.status_code == 200, approved.text
    assert approved.json()["shown_to_learners"] is True
    assert images["fetcher"].calls[0][0] == IMAGE_URL
    assert len(images["store"].files) == 1

    listed = call(images["learner"], "GET", "/api/reading/articles?language=en", admin=False)
    detail = _learner(images, article_id)
    for response in (listed, detail):
        text = response.text
        assert IMAGE_URL not in text and OTHER_URL not in text and "media.example.org" not in text
        assert "asset_key" not in text and "reading-images" not in text
    card = listed.json()["items"][0]["image"]
    assert card == detail.json()["image"]
    assert urlsplit(card["url"]).netloc == "" and card["url"].startswith(f"/api/reading/articles/{article_id}/image?v=")
    assert card["credit"] == "Orena Reading Desk", "no candidate credit: the learner-facing publisher"
    assert card["alt"] == "A flooded field"
    assert detail.json()["content_revision"] > before

    served = call(images["learner"], "GET", card["url"], admin=False)
    assert served.status_code == 200 and served.headers["content-type"] == "image/png"
    assert served.headers["x-content-type-options"] == "nosniff"
    assert served.headers["content-security-policy"] == "default-src 'none'; sandbox"
    assert served.content == png()


def test_an_explicit_or_candidate_credit_wins_over_the_publisher(images):
    article_id = _article_with_candidates(images)
    _policy(images, article_id, True)
    assert _approve(images, article_id, 1).status_code == 200
    assert _learner(images, article_id).json()["image"]["credit"] == "Photo: R. Tran"
    assert _approve(images, article_id, 1, credit="Photo: NASA/JPL").status_code == 200
    assert _learner(images, article_id).json()["image"]["credit"] == "Photo: NASA/JPL"


def test_turning_the_source_off_hides_the_picture_at_once_and_the_validator_changes(images):
    article_id = _article_with_candidates(images)
    _policy(images, article_id, True)
    _approve(images, article_id)
    first = _learner(images, article_id)
    url = first.json()["image"]["url"]
    _policy(images, article_id, False)
    second = _learner(images, article_id)
    assert second.json()["image"] is None
    assert second.headers["etag"] != first.headers["etag"]
    assert call(images["learner"], "GET", url, admin=False).status_code == 404


def test_a_picture_of_an_unpublished_article_is_not_served(images):
    article_id = _article_with_candidates(images)
    _policy(images, article_id, True)
    _approve(images, article_id)
    url = _learner(images, article_id).json()["image"]["url"]
    call(images["admin"], "POST", f"{ADMIN_BASE}/articles/{article_id}/status", json={"status": "unpublished"})
    assert call(images["learner"], "GET", url, admin=False).status_code == 404
    assert call(images["learner"], "GET", f"/api/reading/articles/{article_id}", admin=False).status_code == 404


def test_reject_and_clear_return_the_card_to_its_tile_and_are_recorded(images):
    article_id = _article_with_candidates(images)
    _policy(images, article_id, True)
    _approve(images, article_id, 0)
    review = call(images["admin"], "POST", f"{ADMIN_BASE}/articles/{article_id}/images/0/reject", json={"reason": "wrong"})
    assert review.status_code == 200
    body = review.json()
    assert body["shown_to_learners"] is False and body["approved"] is None
    assert {row["index"]: row["reason"] for row in body["candidates"]}[0] == "rejected"
    assert _learner(images, article_id).json()["image"] is None
    assert _approve(images, article_id, 0).status_code == 200, "a rejection can be reversed by approving again"
    cleared = call(images["admin"], "POST", f"{ADMIN_BASE}/articles/{article_id}/image/clear", json={})
    assert cleared.json()["shown_to_learners"] is False
    actions = [event["action"] for event in call(images["admin"], "GET", f"{ADMIN_BASE}/articles/{article_id}").json()["events"]]
    assert actions.count("image_set") == 3 and actions.count("image_rejected") == 1


def test_the_review_lists_candidates_by_index_and_never_by_address(images):
    article_id = _article_with_candidates(images)
    review = call(images["admin"], "GET", f"{ADMIN_BASE}/articles/{article_id}/images").json()
    assert review["policy_allowed"] is False
    assert [row["index"] for row in review["candidates"]] == [0, 1]
    assert IMAGE_URL not in str(review)
    assert call(images["admin"], "GET", f"{ADMIN_BASE}/articles/{article_id}/images", admin=False).status_code == 403


def test_a_candidate_shared_with_other_items_of_the_source_cannot_be_approved(images):
    first = _article_with_candidates(images)
    manual = images["content"].built_in_source_id("manual")
    for number in range(2):
        images["content"].record_source_item(
            source_id=manual, source_native_id=f"other-{number}", canonical_url="", title="Other", author="",
            published_at=None, language="en", body=f"Another text {number}. " * 20, content_hash=f"{number + 1:064x}",
            metadata={"extraction": {"media": [{"role": "og", "url": IMAGE_URL, "source": "meta:og:image"}]}},
            rights={"can_republish": True},
        )
    _policy(images, first, True)
    refused = _approve(images, first, 0)
    assert refused.status_code == 409 and refused.json()["detail"]["category"] == "reading_image_not_eligible"
    assert images["fetcher"].calls == []


def test_a_failed_fetch_stores_and_records_nothing(images):
    article_id = _article_with_candidates(images)
    _policy(images, article_id, True)
    images["fetcher"].error = UnsafeMediaFetch("This media address is not allowed.")
    refused = _approve(images, article_id)
    assert refused.status_code == 422 and refused.json()["detail"]["category"] == "image_unsafe_url"
    assert images["store"].files == {}
    assert _learner(images, article_id).json()["image"] is None
    images["fetcher"].error = None
    images["fetcher"].body = b"<svg></svg>"
    assert _approve(images, article_id).json()["detail"]["category"] == "image_unsupported_type"


def test_the_requested_index_is_checked_and_an_address_in_the_request_is_not_accepted(images):
    article_id = _article_with_candidates(images)
    _policy(images, article_id, True)
    assert _approve(images, article_id, 7).status_code == 404
    forbidden = call(images["admin"], "POST", f"{ADMIN_BASE}/articles/{article_id}/images/0/approve",
                     json={"url": "http://169.254.169.254/latest"})
    assert forbidden.status_code == 422
    assert images["fetcher"].calls == []


def test_every_image_change_must_come_from_the_console_and_an_administrator(images):
    article_id = _article_with_candidates(images)
    _policy(images, article_id, True)
    path = f"{ADMIN_BASE}/articles/{article_id}/images/0/approve"
    assert call(images["admin"], "POST", path, json={}, admin=False).status_code == 403
    assert call(images["admin"], "POST", path, json={}, origin="https://evil.example").status_code == 403
    assert call(images["admin"], "POST", f"{ADMIN_BASE}/sources/{_source_id(images, article_id)}/image-policy",
                json={"allowed": True}, origin=None).status_code == 403
    assert call(images["admin"], "GET", f"{ADMIN_BASE}/articles/{article_id}/images/0/preview", admin=False).status_code == 403


def test_the_preview_is_fetched_by_the_server_and_never_stored(images):
    article_id = _article_with_candidates(images)
    response = call(images["admin"], "GET", f"{ADMIN_BASE}/articles/{article_id}/images/0/preview")
    assert response.status_code == 200 and response.content == png()
    assert response.headers["cache-control"] == "private, max-age=60"
    assert images["store"].files == {}


def test_a_picture_does_not_change_automatic_admission(images):
    article_id = _article_with_candidates(images)
    source = {"state": "active", "languages": ["en"], "name": "S", "base_url": "",
              "rights": {"automation_allowed": True, "can_republish": True}}
    snapshot = {"rights": {"can_republish": True, "attribution_required": False}, "body": "b", "language": "en",
                "canonical_url": ""}
    plain = automatic_admission(source=source, snapshot=snapshot, language="en", body="b", analysis={},
                                targets=[], min_targets=1, max_targets=2)
    with_policy = automatic_admission(source={**source, "image_policy": {"allowed": True}}, snapshot={
        **snapshot, "metadata": {"extraction": {"media": [{"url": IMAGE_URL}]}}}, language="en", body="b",
        analysis={}, targets=[], min_targets=1, max_targets=2)
    assert plain == with_policy
    assert article_id


def test_a_decision_on_an_unpublished_article_does_not_move_the_cache_revision(images):
    article_id = _article_with_candidates(images)
    _policy(images, article_id, True)
    call(images["admin"], "POST", f"{ADMIN_BASE}/articles/{article_id}/status", json={"status": "unpublished"})
    before = images["content"].get_article(article_id)["content_revision"]
    assert _approve(images, article_id).status_code == 200
    assert images["content"].get_article(article_id)["content_revision"] == before


# ---- review conditions (PR #168) -----------------------------------------------------------------

def test_the_image_credit_fallback_is_the_learner_facing_publisher_never_the_internal_name(images):
    article_id = _article_with_candidates(images)
    manual = images["content"].built_in_source_id("manual")
    images["content"].set_source_public_name(manual, "Registry Desk")
    _policy(images, article_id, True)
    review = _approve(images, article_id, 0).json()
    assert review["shown_to_learners"] is True
    credit = _learner(images, article_id).json()["image"]["credit"]
    assert credit == "Registry Desk" and "Manual paste" not in credit
    listed = call(images["learner"], "GET", "/api/reading/articles?language=en", admin=False).json()["items"][0]
    assert listed["image"]["credit"] == "Registry Desk"
    # no public name, no site name, no address: the internal "Manual paste" is not a credit, so no picture
    images["content"].set_source_public_name(manual, "")
    assert _learner(images, article_id).json()["image"] is None


@pytest.mark.parametrize("first", ["name", "image"])
def test_the_two_policy_keys_survive_each_other_in_either_order(images, first):
    content = images["content"]
    manual = content.built_in_source_id("manual")
    steps = {"name": lambda: content.set_source_public_name(manual, "Orena Reading Desk"),
             "image": lambda: content.set_image_policy(manual, True, actor="admin")}
    for key in (first, "image" if first == "name" else "name"):
        steps[key]()
    source = content.get_source(manual)
    assert source["public_name"] == "Orena Reading Desk" and source["image_policy"] == {"allowed": True}
    content.set_source_public_name(manual, "")
    source = content.get_source(manual)
    assert source["public_name"] == "" and source["image_policy"] == {"allowed": True}, "clearing one key keeps the other"


def test_changing_the_image_policy_moves_the_revision_of_published_articles(images):
    article_id = _article_with_candidates(images)
    before = images["content"].get_article(article_id)["content_revision"]
    _policy(images, article_id, True)
    mid = images["content"].get_article(article_id)["content_revision"]
    assert mid > before
    _policy(images, article_id, True)
    assert images["content"].get_article(article_id)["content_revision"] == mid, "no change, no bump"
    _policy(images, article_id, False)
    assert images["content"].get_article(article_id)["content_revision"] > mid


def test_the_image_route_is_private_no_cache_with_an_etag_and_withdrawal_is_immediate(images):
    article_id = _article_with_candidates(images)
    _policy(images, article_id, True)
    _approve(images, article_id, credit="Photo: A")
    url = _learner(images, article_id).json()["image"]["url"]
    served = call(images["learner"], "GET", url, admin=False)
    assert served.headers["cache-control"] == "private, no-cache" and served.headers["etag"]
    again = call(images["learner"], "GET", url, admin=False, headers={"if-none-match": served.headers["etag"]})
    assert again.status_code == 304
    call(images["admin"], "POST", f"{ADMIN_BASE}/articles/{article_id}/images/0/reject", json={})
    assert call(images["learner"], "GET", url, admin=False).status_code == 404
    assert _learner(images, article_id).json()["image"] is None
    _approve(images, article_id, credit="Photo: A")
    call(images["admin"], "POST", f"{ADMIN_BASE}/articles/{article_id}/image/clear", json={})
    assert call(images["learner"], "GET", url, admin=False).status_code == 404


def test_a_failed_recording_removes_only_a_file_this_call_created(images, monkeypatch):
    article_id = _article_with_candidates(images)
    _policy(images, article_id, True)

    def broken(*args, **kwargs):
        raise RuntimeError("database down")

    real = images["content"].approve_image
    monkeypatch.setattr(images["content"], "approve_image", broken)
    with pytest.raises(RuntimeError):
        _approve(images, article_id, credit="Photo: A")
    assert images["store"].files == {}, "a file this call created is removed"
    monkeypatch.setattr(images["content"], "approve_image", real)
    assert _approve(images, article_id, credit="Photo: A").status_code == 200
    (key,) = images["store"].files
    monkeypatch.setattr(images["content"], "approve_image", broken)
    with pytest.raises(RuntimeError):
        _approve(images, article_id, credit="Photo: A")
    assert key in images["store"].files, "the picture that is live is not deleted by a failed re-approval"


def test_previews_are_kept_briefly_so_a_page_view_does_not_refetch(images):
    article_id = _article_with_candidates(images)
    admin_api._preview_cache.clear()
    for _ in range(3):
        assert call(images["admin"], "GET", f"{ADMIN_BASE}/articles/{article_id}/images/0/preview").status_code == 200
    assert len(images["fetcher"].calls) == 1


def test_a_drip_feeding_server_is_cut_off_by_the_total_deadline(monkeypatch):
    import time

    class Slow:
        headers = type("H", (), {"get_content_type": staticmethod(lambda: "image/png")})()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, size):
            """Like a socket: blocks until `size` bytes have arrived (one byte per 30 ms), capped at 50 bytes
            so a regression finishes slowly rather than never."""
            time.sleep(0.03 * min(size, 50))
            return b"x" * min(size, 50)

        def read1(self, size):
            time.sleep(0.03)
            return b"x"

    monkeypatch.setattr(media_safe_fetch, "_open", lambda *a, **k: Slow())
    started = time.monotonic()
    with pytest.raises(UnsafeMediaFetch):
        media_safe_fetch.fetch_bounded("https://photos.example.org/a.png", total_timeout=0.1)
    assert time.monotonic() - started < 0.5, "cut off by the deadline, not after a whole blocking read"
    # without a deadline nothing changes: the one-megabyte read is used, as before
    import inspect

    assert inspect.signature(media_safe_fetch.fetch_bounded).parameters["total_timeout"].default is None


def test_an_ipv4_mapped_loopback_is_refused_with_the_real_guard(monkeypatch):
    monkeypatch.setattr(media_safe_fetch.socket, "getaddrinfo",
                        lambda *a, **k: [(10, 1, 6, "", ("::ffff:127.0.0.1", 443, 0, 0))])
    with pytest.raises(ImageRefused) as refusal:
        fetch_image("https://photos.example.org/a.png")
    assert refusal.value.code == "image_unsafe_url"


@pytest.mark.parametrize("url", ["https://photos.example.org:8443/a.png", "http://photos.example.org:8080/a.png"])
def test_a_non_default_port_is_refused_before_any_connection(monkeypatch, url):
    monkeypatch.setattr(media_safe_fetch.socket, "getaddrinfo", lambda *a, **k: pytest.fail("resolved"))
    with pytest.raises(ImageRefused) as refusal:
        fetch_image(url)
    assert refusal.value.code == "image_unsafe_url"


def test_a_redirect_to_a_non_default_port_is_refused(monkeypatch):
    monkeypatch.setattr(media_safe_fetch.socket, "getaddrinfo", lambda host, port, **k: [(2, 1, 6, "", ("93.184.216.34", port))])
    handler = media_safe_fetch._CheckedRedirects(max_redirects=3)
    request = media_safe_fetch.Request("https://photos.example.org/a.png")
    with pytest.raises(UnsafeMediaFetch):
        handler.redirect_request(request, None, 302, "Found", {}, "https://photos.example.org:8443/b.png")


def test_a_peer_that_turns_private_after_the_name_was_checked_is_refused_at_connect(monkeypatch):
    """DNS rebinding: the lookup was public, the connection lands on a private address."""
    closed = []

    class Peer:
        def getpeername(self):
            return ("10.0.0.7", 443)

        def close(self):
            closed.append(True)

    monkeypatch.setattr(media_safe_fetch.socket, "create_connection", lambda *a, **k: Peer())
    with pytest.raises(UnsafeMediaFetch):
        media_safe_fetch._connect_public(("photos.example.org", 443), 5)
    assert closed == [True]
