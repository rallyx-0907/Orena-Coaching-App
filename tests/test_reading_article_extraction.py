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
