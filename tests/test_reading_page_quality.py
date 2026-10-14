"""Quality admission (D-191, PROPOSED): a page that is not an article never reaches a publish.

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


def test_a_dated_listing_body_is_hard_only_with_a_structural_signal():
    assert "index_page" in quality_flags(
        body=LISTING_BODY, language="zh", title="本周新闻", facts={"no_article_structure": True})
    soft = quality_flags(body=LISTING_BODY, language="zh", title="本周新闻", facts={"no_article_structure": False})
    assert "index_like" in soft and "index_page" not in soft


def test_a_section_page_of_dated_entries_is_an_index():
    assert "index_page" in quality_flags(body=SECTION_BODY, language="zh", title="", facts={"no_article_structure": True})


def test_an_archive_address_is_an_index():
    page = extract_article(NASA_ARTICLE, "https://example.org/news/archive")
    assert "index_page" in quality_flags(body=page.body, language="en", title=page.title, facts=page.page_facts)


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


# ---- negatives: legitimate pages that must not be hard-flagged -------------------

_EN_SENTENCE = "The council approved the new bridge budget after a long public hearing on Tuesday evening. "
_ZH_SENTENCE = "市政府周二宣布，新的跨河大桥将在明年春天开工，预计两年内完成，沿线居民可以获得补偿。"


def _article_html(paragraphs: str, title: str = "Bridge budget approved", extra: str = "") -> str:
    return (f"<html><head><title>{title}</title></head><body><main><article><h1>{title}</h1>{extra}"
            f"{paragraphs}</article></main></body></html>")


def test_a_short_english_and_a_short_chinese_article_are_not_hard_flagged():
    en = _flags(_article_html(f"<p>{_EN_SENTENCE * 3}</p><p>{_EN_SENTENCE * 3}</p>"), "https://example.org/a/1", "en")
    zh = _flags(_article_html(f"<p>{_ZH_SENTENCE * 3}</p><p>{_ZH_SENTENCE * 3}</p>", title="大桥预算获批"),
                "https://example.org/a/2", "zh")
    assert not HARD_ISSUES & set(en) and not HARD_ISSUES & set(zh)


def test_a_300_hanzi_chinese_article_with_a_video_is_not_a_media_page():
    video = '<video src="/v.mp4" controls></video>'
    html = _article_html(f"<p>{_ZH_SENTENCE * 5}</p><p>{_ZH_SENTENCE * 5}</p>", title="大桥预算获批", extra=video)
    page = extract_article(html, "https://example.org/a/3")
    assert page.page_facts["media_player"] and 280 <= page.units < 400
    assert "media_page" not in quality_flags(
        body=page.body, language="zh", title=page.title, facts=page.page_facts)


@pytest.mark.parametrize("title", [
    "Just a moment of silence for the flood victims", "Access denied to journalists at the border",
    "Attention required: why sleep matters",
])
def test_a_headline_that_starts_like_a_challenge_phrase_is_not_a_bot_challenge(title):
    html = _article_html(f"<p>{_EN_SENTENCE * 4}</p><p>{_EN_SENTENCE * 4}</p>", title=title)
    assert "bot_challenge" not in _flags(html, "https://example.org/a/4", "en")


def test_a_short_page_titled_like_a_headline_is_not_a_bot_challenge():
    html = _article_html(f"<p>{_EN_SENTENCE * 4}</p>", title="Just a moment of silence for the victims")
    assert "bot_challenge" not in _flags(html, "https://example.org/a/5", "en")


def test_a_dated_timeline_and_a_poem_are_not_hard_flagged_as_an_index():
    timeline = "\n\n".join(f"{1990 + n}-05-0{n % 9 + 1} The treaty was signed in the capital" for n in range(10))
    poem = "\n\n".join(f"In 19{50 + n} the river ran on" for n in range(12))
    for body in (timeline, poem):
        flags = quality_flags(body=body, language="en", title="A history", facts={"no_article_structure": False})
        assert "index_page" not in flags and not HARD_ISSUES & set(flags)


# ---- 2026-10-14 tightening: real pages from the live dry run (extractor article-extract/4) -------------------
from pathlib import Path  # noqa: E402

_LIVE = Path(__file__).parent / "fixtures" / "reading_quality"


def _live(name: str, url: str, language: str) -> list[str]:
    return _flags((_LIVE / name).read_text(encoding="utf-8"), url, language)


def test_voa_topic_page_is_a_hard_index_page():
    flags = _live("voa_zh_topic_page_p6197.html", "https://www.voachinese.com/p/6197.html", "zh")
    assert "index_page" in flags


def test_voa_player_page_without_an_article_is_a_hard_media_page():
    flags = _live("voa_zh_player_page_p9647.html", "https://www.voachinese.com/p/9647.html", "zh")
    assert "media_page" in flags


def test_voa_section_page_is_still_a_hard_index_page():
    assert "index_page" in _live("voa_zh_section_z1741.html", "https://www.voachinese.com/z/1741", "zh")


@pytest.mark.parametrize(
    ("name", "url", "language"),
    [
        ("voa_zh_article_8210116.html", "https://www.voachinese.com/a/x/8210116.html", "zh"),
        ("voa_zh_article_8208799.html", "https://www.voachinese.com/a/y/8208799.html", "zh"),
        ("nasa_news_release.html", "https://www.nasa.gov/news-release/nuclear/", "en"),
        ("global_voices_article.html", "https://globalvoices.org/2026/09/28/calypso/", "en"),
    ],
)
def test_real_articles_stay_clean_under_the_tightened_rules(name, url, language):
    assert _live(name, url, language) == []


def test_the_tightened_rules_read_structure_and_size_only():
    # A short player page that has an article element keeps the older, lower media limit.
    assert "media_page" not in quality_flags(
        body="字" * 400, language="zh", facts={"media_player": True, "no_semantic_container": False})
    assert "media_page" in quality_flags(
        body="字" * 400, language="zh", facts={"media_player": True, "no_semantic_container": True})
    # A long body on a structureless page is never an index by size alone.
    assert "index_page" not in quality_flags(body="字" * 900, language="zh", facts={"no_article_structure": True})
    assert "index_page" in quality_flags(body="字" * 200, language="zh", facts={"no_article_structure": True})
