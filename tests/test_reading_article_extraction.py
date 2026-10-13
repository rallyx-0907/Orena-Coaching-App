"""A fetched page yields its article, not the page.

Every fixture is a realistic page shape written for this test (no network, no
real site's markup). The assertions are about the generic contract - main
content found by structure and density, boilerplate removed by what it *is* -
so none of them may be satisfied by a rule that knows a site.
"""
from __future__ import annotations

import pytest

from reading_article_fixtures import BLOG_LIKE, CHINESE_NEWS, NASA_LIKE, NOAA_LIKE, VOA_LIKE
from writing_coach.reading_article_extraction import extract_article
from writing_coach.reading_processing import analyze_article, content_fingerprint
from writing_coach.reading_source_import import (
    DirectUrlAdapter,
    FileAdapter,
    ManualTextAdapter,
    SubmittedInput,
)


def _item(html: str, url: str = "https://news.example.org/a/1"):
    def fetch(url, *, max_bytes, timeout, content_types):
        return html.encode("utf-8"), "text/html"

    adapter = DirectUrlAdapter(fetcher=fetch)
    submitted = SubmittedInput(kind="url", url=url)
    return adapter.normalize(adapter.fetch(submitted))


def _paragraphs(body: str) -> list[str]:
    return [part for part in body.split("\n\n") if part]


def _in_order(body: str, *snippets: str) -> None:
    positions = [body.index(snippet) for snippet in snippets]
    assert positions == sorted(positions)


# ---- VOA-like news page -----------------------------------------------------


def test_voa_like_page_keeps_only_the_article():
    item = _item(VOA_LIKE)
    body = item.body
    for junk in (
        "See comments", "Your browser doesn't support HTML5", "Related", "About Learning English",
        "Beginning Level", "Intermediate Level", "Close", "Words in This Story", "FILE -", "Reuters",
        "I'm Andrew Smith", "wrote this story", "Fish Disappear From Warm Lakes", "Copyright",
        "really good report",
    ):
        assert junk not in body, junk
    _in_order(
        body,
        "Scientists say rivers around the world",
        "Warmer water holds less oxygen",
        "What researchers found",
        "The team measured temperatures",
        "Cities and farms make the problem worse",
        "Local governments are now asking engineers",
    )
    assert len(_paragraphs(body)) == 6


def test_voa_like_title_is_metadata_and_not_repeated_in_the_body():
    item = _item(VOA_LIKE)
    assert item.title == "Scientists Warn Rivers Are Warming Faster"
    assert "Scientists Warn Rivers Are Warming Faster" not in item.body


def test_voa_like_author_date_canonical_and_glossary_are_metadata_not_passage():
    item = _item(VOA_LIKE)
    assert item.author == "Andrew Smith"
    assert item.published_at is not None and item.published_at.year == 2026
    assert item.metadata["page_canonical_url"] == "https://news.example.org/a/rivers-warming/7001.html"
    terms = {entry["term"] for entry in item.metadata["glossary"]}
    assert terms == {"runoff", "species", "threatened"}
    assert item.metadata["extraction_confidence"] == "high"
    assert "I'm Andrew Smith." in item.metadata["extraction"]["attribution_lines"]


def test_boilerplate_does_not_change_the_dedupe_hash_or_the_analysis():
    clean = _item(VOA_LIKE)
    noisier = _item(VOA_LIKE.replace("<p>Local governments", "<div class='share'>Share this story now</div><p>Local governments"))
    assert clean.content_hash == noisier.content_hash == content_fingerprint(clean.body)
    analysis = analyze_article(clean.body, "en")
    assert analysis.word_count == len(clean.body.split())


# ---- other article shapes ---------------------------------------------------


@pytest.mark.parametrize(
    ("html", "title", "first", "last", "junk"),
    [
        (
            NASA_LIKE, "New Telescope Finds Water Vapor on Distant Planet",
            "A new space telescope has found water vapor", "Observations like these prepare",
            ("Share on Facebook", "You May Also Like", "Probe Reaches Icy Moon", "Sponsored", "Credit:",
             "Latest", "Page last updated", "Feb 11, 2026"),
        ),
        (
            NOAA_LIKE, "How Tides Work",
            "Tides are the daily rise and fall", "Knowing the tides helps sailors",
            ("Skip to main content", "Home", "newsletter", "Subscribe", "Last updated", "Privacy Policy", "Tides >"),
        ),
        (
            BLOG_LIKE, "Why I Started Baking Bread",
            "Last winter I decided to bake", "Now the whole house smells wonderful",
            ("Kitchen Notes", "Posted on", "Tags:", "Responses", "Great post", "Related Posts",
             "Five Easy Soups", "Archives", "Powered by", "About Me"),
        ),
    ],
)
def test_article_pages_keep_the_article_and_drop_the_page(html, title, first, last, junk):
    item = _item(html)
    assert item.title == title
    assert item.body.startswith(first)
    assert item.body.rstrip().endswith(last.split(" ")[-1]) or last in item.body
    assert last in item.body
    for text in junk:
        assert text not in item.body, text
    assert title not in item.body
    assert len(_paragraphs(item.body)) >= 4


def test_body_is_not_over_trimmed():
    # Every sentence of every article paragraph survives, not just the first.
    item = _item(NOAA_LIKE)
    assert "so most coasts see two high tides a day." in item.body
    assert "Spring and neap tides" in item.body  # a real sub-heading is article structure
    assert "they happen twice every month." in item.body


def test_nasa_like_author_and_date_come_from_meta():
    item = _item(NASA_LIKE)
    assert item.author == "Mia Torres"
    assert item.published_at is not None and item.published_at.month == 2


def test_chinese_page_is_extracted_the_same_way():
    item = _item(CHINESE_NEWS)
    assert item.title == "河流水温上升"
    assert item.body.startswith("科学家说")
    assert "相关新闻" not in item.body and "版权所有" not in item.body and "首页" not in item.body
    assert len(_paragraphs(item.body)) == 4
    assert item.metadata["extraction_confidence"] == "high"


# ---- link-heavy and wrapper traps -------------------------------------------


def test_link_heavy_unrelated_blocks_are_not_body():
    html = NOAA_LIKE.replace(
        "<div class=\"newsletter-signup\">",
        "<div class=\"links\"><p><a href=\"/1\">Ocean currents explained for everyone in plain words</a> "
        "<a href=\"/2\">Why the sea is salty and what that means for ships</a></p></div>"
        "<div class=\"newsletter-signup\">",
    )
    item = _item(html)
    assert "Ocean currents explained" not in item.body
    assert "Why the sea is salty" not in item.body


def test_a_layout_wrapper_named_like_boilerplate_does_not_delete_the_article():
    html = (
        "<html><body><div class='page-with-sidebar'><div class='content-comments-enabled'>"
        + "".join(f"<p>Paragraph number {n} says something complete and useful about rivers, tides and the weather today.</p>" for n in range(6))
        + "</div></div></body></html>"
    )
    item = _item(html)
    assert item.body.count("Paragraph number") == 6


def test_unclosed_paragraphs_and_hostile_markup_still_extract():
    html = (
        "<html><body><article><h1>T</h1>"
        "<p>First paragraph is long enough to count as a real sentence of article prose here.<br>"
        "<p>Second paragraph is also long enough to count as a real sentence of article prose here."
        "<script>alert(1)</script><p>Third paragraph stays complete and readable for the learner who opens it."
        "<img src=x onerror=alert(1)></article></body></html>"
    )
    item = _item(html)
    assert "alert" not in item.body and "<" not in item.body
    assert len(_paragraphs(item.body)) == 3


# ---- confidence -------------------------------------------------------------


def test_a_link_farm_is_low_confidence_and_flagged_for_the_admin():
    html = (
        "<html><head><title>Front page</title></head><body>"
        + "".join(
            f"<article><h2><a href='/s{n}'>Story headline number {n}</a></h2>"
            f"<p>Short teaser {n} about something that happened today.</p></article>"
            for n in range(6)
        )
        + "</body></html>"
    )
    extracted = extract_article(html)
    assert extracted.confidence == "low"
    assert extracted.reasons
    item = _item(html)
    assert item.metadata["extraction_confidence"] == "low"
    assert item.metadata["extraction"]["reasons"]


def test_confidence_levels_follow_the_evidence():
    assert extract_article(VOA_LIKE).confidence == "high"
    assert extract_article(NOAA_LIKE).confidence == "high"
    # No article/main element: still extracted, but not as sure.
    assert extract_article(BLOG_LIKE).confidence == "medium"
    assert extract_article("<html><body><p>Hi there.</p></body></html>").confidence == "low"


# ---- other ingestion routes are untouched -----------------------------------


def test_manual_text_and_plain_text_files_are_not_run_through_html_extraction():
    text = "Related\n\nA plain paragraph that talks about rivers.\n\nShare"
    manual = ManualTextAdapter()
    item = manual.normalize(manual.fetch(SubmittedInput(kind="text", text=text)))
    assert item.body == text
    assert "extraction" not in item.metadata

    files = FileAdapter()
    item = files.normalize(files.fetch(SubmittedInput(kind="file", filename="a.txt", payload=text.encode())))
    assert item.body == text


def test_a_plain_text_url_is_cleaned_like_before():
    def fetch(url, *, max_bytes, timeout, content_types):
        return b"Related\n\nA plain paragraph.", "text/plain"

    adapter = DirectUrlAdapter(fetcher=fetch)
    item = adapter.normalize(adapter.fetch(SubmittedInput(kind="url", url="https://x.example.org/a.txt")))
    assert item.body == "Related\n\nA plain paragraph."


# ---- media candidates: provenance only --------------------------------------

VOA_URL = "https://news.example.org/a/rivers?utm_source=x"


def _voa_media():
    item = _item(VOA_LIKE, VOA_URL)
    return item, item.metadata["extraction"]["media"]


def test_media_candidates_roles_order_and_absolute_original_urls():
    _, media = _voa_media()
    assert [(m["role"], m["url"]) for m in media] == [
        ("og", "https://cdn.example.org/img/river-1280.jpg?v=2"),
        ("twitter", "https://cdn.example.org/img/river-twitter.jpg"),
        ("hero", "https://news.example.org/img/river-1280.jpg"),  # largest srcset entry, resolved
        ("inline", "https://news.example.org/img/stations-1600.webp"),  # <picture> source, largest
    ]
    assert [m["position"] for m in media if m["source"] == "article:img"] == [1, 2]


def test_media_candidates_keep_alt_caption_credit_and_declared_size():
    _, media = _voa_media()
    hero, inline = media[2], media[3]
    assert hero["alt"] == "A river in a valley"
    assert hero["caption"] == "FILE - A river flows through a valley, April 1, 2026."
    assert hero["credit"] == "Reuters/Jane Doe"
    assert (hero["width"], hero["height"]) == (1280, 720)
    assert inline["caption"] == "Sensors measure the water." and inline["credit"] == "Photo: Lee Park"
    assert media[0]["alt"] == "A river in a valley"


def test_decorative_and_tracking_images_are_not_candidates():
    _, media = _voa_media()
    urls = " ".join(m["url"] for m in media)
    for decorative in ("andrew.jpg", "t.gif", "site-logo", "mark.svg", "data:"):
        assert decorative not in urls
    assert extract_article('<body><article><img src="/a.png" width="32" height="32"></article></body>').media == []


def test_every_candidate_is_rights_unreviewed_whatever_the_text_rights_say():
    submitted = SubmittedInput(kind="url", url=VOA_URL, rights={"can_republish": True})
    adapter = DirectUrlAdapter(fetcher=lambda *a, **k: (VOA_LIKE.encode(), "text/html"))
    result = adapter.normalize(adapter.fetch(submitted))
    assert result.rights["can_republish"] is True
    for candidate in result.metadata["extraction"]["media"]:
        assert candidate["rights"] == {"status": "unreviewed", "cleared": False}


def test_a_meta_image_also_in_the_article_is_one_candidate_with_the_article_details():
    html = VOA_LIKE.replace(
        "https://cdn.example.org/img/river-1280.jpg?v=2#top", "https://news.example.org/img/river-1280.jpg"
    )
    media = _item(html, VOA_URL).metadata["extraction"]["media"]
    same = [m for m in media if m["url"] == "https://news.example.org/img/river-1280.jpg"]
    assert len(same) == 1 and same[0]["role"] == "hero" and same[0]["credit"] == "Reuters/Jane Doe"
    assert same[0]["also_declared_as"] == ["og"]
    assert len(media) == 3


def test_nasa_like_images_resolve_against_the_page_and_credit_is_split_from_caption():
    item = _item(NASA_LIKE, "https://space.example.gov/news/telescope")
    media = item.metadata["extraction"]["media"]
    assert media[0]["url"] == "https://space.example.gov/images/planet.jpg" and media[0]["role"] == "og"
    assert media[1]["caption"] == "An artist's idea of the planet."
    assert media[1]["credit"] == "Space Agency/Art Team"


def test_candidate_list_is_capped():
    imgs = "".join(f'<figure><img src="/i/{n}.jpg" width="800" height="600" alt="a"></figure>' for n in range(30))
    prose = "A full sentence of real article prose goes here today. " * 6
    html = f"<html><body><article><p>{prose}</p>{imgs}</article></body></html>"
    assert len(extract_article(html, "https://x.example.org/").media) == 12


def test_media_text_never_reaches_the_passage():
    item, media = _voa_media()
    for candidate in media:
        assert candidate["url"] not in item.body
        assert not candidate["caption"] or candidate["caption"] not in item.body
    assert "Reuters" not in item.body and "Lee Park" not in item.body


# ---- candidate URLs and text are bounded and sanitized; never fetched ------------

BASE = "https://news.example.org/a/1"


@pytest.mark.parametrize(
    "url",
    [
        "https://user:pw@cdn.example.org/a.jpg",
        "https://user@cdn.example.org/a.jpg",
        "https://cdn.example.org/" + "a" * 2100 + ".jpg",
        "https://cdn.example.org/a b.jpg",
        "https://cdn.example.org/a\n.jpg",
        "https://cdn.example.org/a\x00.jpg",
        "javascript:alert(1)",
        "ftp://cdn.example.org/a.jpg",
        "data:image/png;base64,AAAA",
    ],
)
def test_unsafe_image_urls_are_rejected_not_rewritten(url):
    from writing_coach.reading_article_extraction import _normalized_image_url

    assert _normalized_image_url(url, BASE) == ""


def test_a_clean_relative_image_url_is_resolved():
    from writing_coach.reading_article_extraction import _normalized_image_url

    assert _normalized_image_url("/i/a.jpg#x", BASE) == "https://news.example.org/i/a.jpg"


def test_candidate_text_is_whitespace_normalised_and_bounded():
    long_text = "word " * 400
    html = (
        "<html><body><article><p>" + "A full sentence of real article prose goes here today. " * 6 + "</p>"
        f'<figure><img src="/i/a.jpg" width="800" height="600" alt="{long_text}">'
        f"<figcaption>{long_text} <small>{long_text}</small></figcaption></figure></article></body></html>"
    )
    (candidate,) = extract_article(html, BASE).media
    for field in ("alt", "caption", "credit"):
        assert len(candidate[field]) <= 500
        assert "  " not in candidate[field]


def test_an_image_with_credentials_in_its_url_is_not_a_candidate():
    html = (
        "<html><body><article><p>" + "A full sentence of real article prose goes here today. " * 6 + "</p>"
        '<img src="https://u:p@cdn.example.org/a.jpg" width="800" height="600"></article></body></html>'
    )
    assert extract_article(html, BASE).media == []


def test_the_extractor_version_is_recorded_with_the_method():
    from writing_coach.reading_article_extraction import EXTRACTOR_VERSION

    item = _item(VOA_LIKE)
    assert EXTRACTOR_VERSION == "article-extract/4"
    assert item.metadata["extraction"]["extractor_version"] == EXTRACTOR_VERSION
    assert item.metadata["extraction"]["method"] == "dominant_container"


def test_the_extraction_module_never_fetches_anything():
    import inspect

    from writing_coach import reading_article_extraction as module

    source = inspect.getsource(module)
    for fetcher in ("urlopen", "fetch_bounded", "requests", "httpx", "socket", "urllib.request"):
        assert fetcher not in source


# ---- review fixes: resolution base, article-local header, structured author -----

_PROSE = "".join(
    f"<p>Paragraph {n} is a full sentence of real article prose about rivers, tides and the weather today.</p>"
    for n in range(5)
)


def test_relative_media_urls_resolve_against_the_fetched_url_not_the_canonical_link():
    html = (
        '<html><head><link rel="canonical" href="https://news.example.org/story/rivers">'
        '<meta property="og:image" content="images/og.jpg"></head><body><article><h1>T</h1>'
        '<figure><img src="images/hero.jpg" width="800" height="600" alt="h"></figure>'
        + _PROSE
        + '<figure><img src="../img/x.jpg" srcset="../img/x-640.jpg 640w, ../img/x-1280.jpg 1280w" '
        'width="640" height="480" alt="x"></figure></article></body></html>'
    )
    item = _item(html, "https://news.example.org/a/2026/rivers.html")
    urls = [m["url"] for m in item.metadata["extraction"]["media"]]
    assert urls == [
        "https://news.example.org/a/2026/images/og.jpg",
        "https://news.example.org/a/2026/images/hero.jpg",
        "https://news.example.org/a/img/x-1280.jpg",
    ]
    assert item.metadata["page_canonical_url"] == "https://news.example.org/story/rivers"


def test_a_base_href_is_followed_after_resolving_it_against_the_fetched_url():
    html = (
        '<html><head><base href="/assets/"><link rel="canonical" href="https://other.example.org/x/"></head>'
        '<body><article>' + _PROSE + '<figure><img src="p.jpg" width="800" height="600"></figure>'
        "</article></body></html>"
    )
    media = _item(html, "https://news.example.org/a/2026/rivers.html").metadata["extraction"]["media"]
    assert [m["url"] for m in media] == ["https://news.example.org/assets/p.jpg"]


def test_an_unusable_base_href_falls_back_to_the_fetched_url():
    html = (
        '<html><head><base href="javascript:alert(1)"></head><body><article>' + _PROSE
        + '<figure><img src="p.jpg" width="800" height="600"></figure></article></body></html>'
    )
    media = _item(html, "https://news.example.org/a/2026/rivers.html").metadata["extraction"]["media"]
    assert [m["url"] for m in media] == ["https://news.example.org/a/2026/p.jpg"]


ARTICLE_HEADER_PAGE = (
    '<html><head><title>River Report - News</title></head><body>'
    '<header class="site-header"><img src="/logo.png" alt="News logo" width="200" height="60">'
    '<nav><a href="/">Home</a><a href="/world">World</a></nav></header>'
    '<article><header><h1>River Report</h1>'
    '<p class="dek">Scientists say the rivers of the north are warming faster than anyone expected.</p>'
    '<figure class="hero"><img src="hero.jpg" width="1200" height="800" alt="A river">'
    '<figcaption>A river in spring. <span class="credit">Photo: Lee Park</span></figcaption></figure></header>'
    + _PROSE
    + "</article><footer><p>Copyright 2026 News Media</p></footer></body></html>"
)


def test_an_article_local_header_keeps_its_dek_and_hero_but_the_site_header_is_removed():
    item = _item(ARTICLE_HEADER_PAGE, "https://news.example.org/a/river.html")
    assert item.body.startswith("Scientists say the rivers of the north are warming")
    assert "Paragraph 4" in item.body
    assert "River Report" not in item.body  # the title is metadata, not passage
    for chrome in ("Home", "World", "News logo", "Copyright", "Photo: Lee Park"):
        assert chrome not in item.body
    hero = next(m for m in item.metadata["extraction"]["media"] if m["role"] == "hero")
    assert hero["url"] == "https://news.example.org/a/hero.jpg"
    assert hero["credit"] == "Photo: Lee Park" and hero["caption"] == "A river in spring."
    assert all("logo" not in m["url"] for m in item.metadata["extraction"]["media"])


def test_a_dek_that_repeats_the_title_is_not_kept():
    html = ARTICLE_HEADER_PAGE.replace(
        "Scientists say the rivers of the north are warming faster than anyone expected.", "River Report"
    )
    assert not _item(html, "https://news.example.org/a/river.html").body.startswith("River Report")


def test_a_banner_header_inside_main_is_still_site_chrome():
    html = (
        '<html><body><main><header role="banner"><p>Site navigation words go here for everyone today.</p></header>'
        + _PROSE + "</main></body></html>"
    )
    assert "Site navigation" not in _item(html, "https://news.example.org/a/r.html").body


def test_a_structured_author_wins_over_a_generic_meta_author():
    html = (
        '<html><head><meta name="author" content="Site Staff"></head><body><article>'
        '<p class="byline">By Jane Writer</p>' + _PROSE + "</article></body></html>"
    )
    assert _item(html, "https://news.example.org/a/r.html").author == "Jane Writer"
    ld = (
        '<html><head><meta name="author" content="Site Staff">'
        '<script type="application/ld+json">{"@type":"NewsArticle","author":{"name":"Ana Reporter"}}</script>'
        "</head><body><article>" + _PROSE + "</article></body></html>"
    )
    assert _item(ld, "https://news.example.org/a/r.html").author == "Ana Reporter"
    meta_only = html.replace('<p class="byline">By Jane Writer</p>', "")
    assert _item(meta_only, "https://news.example.org/a/r.html").author == "Site Staff"
