"""Quality admission (D-18X, PROPOSED): a page that is not an article never reaches a publish.

Fixtures are modelled on the pages of the 2026-10-13 trial (reading_quality_fixtures).
Hard codes refuse a reviewer's publish; every code, hard or soft, holds D-111
automatic admission.
"""
from __future__ import annotations

import pytest

from reading_quality_fixtures import (
    ACCESS_DENIED,
    BOT_CHALLENGE,
    GLOBAL_VOICES_EN,
    LISTING_BODY,
    SECTION_BODY,
    NASA_ARTICLE,
    VOA_LE_AUDIO,
    VOA_ZH_ARTICLE,
    VOA_ZH_INDEX,
    VOA_ZH_VIDEO,
    WIKI_FEEDITEM,
    WIKI_FEEDITEM_URL,
)
from writing_coach.reading_article_extraction import extract_article
from writing_coach.reading_page_quality import HARD_ISSUES, SOFT_ISSUES, hard_issues, quality_flags
from writing_coach.reading_source_import import DirectUrlAdapter, ReadingSourceError, SubmittedInput


def _flags(html: str, url: str, language: str) -> list[str]:
    page = extract_article(html, url)
    return quality_flags(
        body=page.body, language=language, title=page.title, confidence=page.confidence, facts=page.page_facts
    )


# ---- pages that are not articles --------------------------------------------


def test_voa_zh_video_page_is_a_hard_media_page():
    flags = _flags(VOA_ZH_VIDEO, "https://www.voachinese.com/a/8208887.html", "zh")
    assert "media_page" in flags and "media_page" in HARD_ISSUES


def test_voa_zh_index_page_is_flagged_hard():
    flags = _flags(VOA_ZH_INDEX, "https://www.voachinese.com/z/1234", "zh")
    assert "index_page" in flags and "index_page" in HARD_ISSUES


def test_a_dated_listing_body_is_an_index_even_without_a_telling_title():
    assert "index_page" in quality_flags(body=LISTING_BODY, language="zh", title="本周新闻")


def test_a_section_page_of_dated_entries_is_an_index():
    assert "index_page" in quality_flags(body=SECTION_BODY, language="zh", title="")


def test_voa_le_audio_page_has_no_body_and_is_flagged():
    flags = _flags(VOA_LE_AUDIO, "https://learningenglish.voanews.com/a/8010810.html", "en")
    assert "empty_body" in flags and "media_page" in flags


def test_voa_le_audio_page_is_refused_by_the_engine_as_no_readable_article():
    adapter = DirectUrlAdapter(fetcher=lambda url, **_: (VOA_LE_AUDIO.encode(), "text/html"))
    submitted = SubmittedInput(kind="url", url="https://learningenglish.voanews.com/a/8010810.html")
    with pytest.raises(ReadingSourceError) as caught:
        adapter.normalize(adapter.fetch(submitted))
    assert caught.value.code == "empty_source"


def test_wikipedia_feed_item_stub_is_a_hard_special_page():
    flags = _flags(WIKI_FEEDITEM, WIKI_FEEDITEM_URL, "zh")
    assert "special_page" in flags and "special_page" in HARD_ISSUES


@pytest.mark.parametrize("page", [BOT_CHALLENGE, ACCESS_DENIED])
def test_bot_challenge_and_403_pages_are_hard(page):
    assert "bot_challenge" in _flags(page, "https://example.org/a/1", "en")
    assert "bot_challenge" in HARD_ISSUES


def test_a_long_article_that_mentions_access_denied_is_not_a_challenge():
    html = GLOBAL_VOICES_EN.replace("<h1>", "<h1>Access denied: ", 1)
    html = html.replace("<title>", "<title>Reporting on ", 1)
    assert "bot_challenge" not in _flags(html, "https://globalvoices.org/a", "en")


def test_an_empty_body_is_hard():
    assert "empty_body" in quality_flags(body="  ", language="en") and "empty_body" in HARD_ISSUES


# ---- soft signals ------------------------------------------------------------


def test_soft_signals_do_not_reach_the_hard_set():
    assert HARD_ISSUES.isdisjoint(SOFT_ISSUES)
    short_en = "word " * 70
    assert quality_flags(body=short_en, language="en") == ["body_below_minimum"]
    assert quality_flags(body="字" * 100, language="zh") == ["body_below_minimum"]
    assert quality_flags(body="word " * 400, language="en", confidence="medium") == ["extraction_medium_confidence"]
    assert quality_flags(body="word " * 400, language="en", title="Home") == ["generic_title"]
    assert quality_flags(
        body="word " * 400, language="en", title="Global Voices", facts={"site_name": "Global Voices"}
    ) == ["generic_title"]
    assert hard_issues(["too_short", "media_page", "generic_title", "bot_challenge"]) == ["media_page", "bot_challenge"]


def test_a_missing_title_is_not_a_generic_one():
    assert quality_flags(body="word " * 400, language="en", title="") == []


# ---- ordinary articles still pass --------------------------------------------


@pytest.mark.parametrize("html,url,language", [
    (NASA_ARTICLE, "https://www.nasa.gov/news-release/heat-shield/", "en"),
    (GLOBAL_VOICES_EN, "https://globalvoices.org/2026/10/09/ecuador/", "en"),
    (VOA_ZH_ARTICLE, "https://www.voachinese.com/a/lai-ching-te-8210000.html", "zh"),
])
def test_ordinary_articles_get_no_quality_flag(html, url, language):
    assert _flags(html, url, language) == []


# ---- D-111: any flag holds automatic admission --------------------------------


@pytest.mark.parametrize("code", sorted(HARD_ISSUES | SOFT_ISSUES))
def test_a_flagged_item_cannot_be_automatically_admitted(code):
    from test_reading_admission import decision

    outcome = decision(analysis={"quality_issues": [code]})
    assert outcome["decision"] == "review" and code in outcome["reasons"]
    assert decision(analysis={"quality_issues": []})["decision"] == "published"
