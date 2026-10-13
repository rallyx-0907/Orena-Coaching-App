"""P0-D: press blocks, editorial prefaces, author bios and player text leave the body.

Fixtures are modelled on the shapes of the 2026-10-13 trial pages (NASA news
releases, Global Voices EN, VOA 中文, VOA Learning English), written for this
test: no network, no real page. Every positive case has a negative twin: prose
that merely mentions "contact", "media" or "author" must survive.
"""
from __future__ import annotations

from writing_coach.reading_article_extraction import EXTRACTOR_VERSION, extract_article
from writing_coach.reading_source_cleanup import Item, cleanup, rules_for

EN = (
    "The agency said the spacecraft completed a long series of tests at the laboratory in Southern California, "
    "and engineers described the results as a major step before the launch later this year."
)
EN2 = (
    "After the tests, the team returned the lander to the factory for final assembly, where technicians will "
    "prepare it for shipment and for the long trip to its launch site on the coast."
)
EN3 = (
    "Officials said the next phase will focus on integration, and that the schedule remains on track "
    "unless the weather or the range delays the attempt in the coming weeks."
)
ZH = "这是一段足够长的真实新闻正文，用来确保提取器把它当作文章的主体内容来处理，并且包含完整的句子。"


def _page(inner: str) -> str:
    return f"<html><head><title>Story</title></head><body><article><h1>Story</h1>{inner}</article></body></html>"


def _extract(inner: str, url: str):
    return extract_article(_page(inner), url)


def _paras(article) -> list[str]:
    return [p for p in article.body.split("\n\n") if p]


def _kinds(article) -> list[str]:
    return [item["kind"] for item in article.removed]


NASA = "https://www.nasa.gov/news-release/some-release/"
GV = "https://globalvoices.org/2026/10/12/some-post/"
VOA_ZH = "https://www.voachinese.com/a/some-report-20261012/8210546.html"
VOA_LE = "https://learningenglish.voanews.com/a/some-story/7997495.html"


# ---- 1. press and contact blocks -------------------------------------------


NASA_CONTACTS = (
    "<p>Learn more about the International Space Station, its research, and crew, at:</p>"
    '<p class="has-text-align-center"><a href="https://www.nasa.gov/station"><strong>https://www.nasa.gov/station</strong></a></p>'
    '<p class="has-text-align-center">-end-</p>'
    "<p>Joshua Finch / Jimi Russell<br />Headquarters, Washington<br />202-358-1100<br />"
    '<a href="mailto:joshua.a.finch@nasa.gov">joshua.a.finch@nasa.gov</a> / '
    '<a href="mailto:james.j.russell@nasa.gov">james.j.russell@nasa.gov</a></p>'
    "<p>Steven Siceloff<br />Kennedy Space Center, Fla.<br />321-876-2468<br />"
    '<a href="mailto:steven.p.siceloff@nasa.gov">steven.p.siceloff@nasa.gov</a></p>'
)


def test_nasa_release_loses_the_contact_block_and_the_dangling_lead_in():
    article = _extract(f"<p>{EN}</p><p>{EN2}</p><p>{EN3}</p>{NASA_CONTACTS}", NASA)
    assert _paras(article) == [EN, EN2, EN3]
    assert "202-358-1100" not in article.body and "@nasa.gov" not in article.body
    assert "Learn more about" not in article.body
    assert _kinds(article).count("contact") == 2 and "dangling_leadin" in _kinds(article)


def test_media_contact_label_and_one_line_contact_block():
    html = f"<p>{EN}</p><p>{EN2}</p><p>{EN3}</p><p>Media Contact Melissa Pamer Jet Propulsion Laboratory, Pasadena, Calif. 626-314-4928 melissa.pamer@jpl.nasa.gov</p>"
    assert _paras(_extract(html, NASA)) == [EN, EN2, EN3]
    labelled = f"<p>{EN}</p><p>{EN2}</p><p>{EN3}</p><p>Media Contacts</p><p>Jane Roe<br/>Washington<br/>202-555-0100<br/>jane.roe@agency.gov</p>"
    assert _paras(_extract(labelled, "https://news.example.org/a/1")) == [EN, EN2, EN3]


def test_leading_for_more_information_contact_line_is_removed():
    html = f"<p>For more information, contact Joel W. Sills, Langley Research Center, joel.w.sills@nasa.gov</p><p>{EN}</p><p>{EN2}</p><p>{EN3}</p>"
    article = _extract(html, NASA)
    assert _paras(article) == [EN, EN2, EN3]


def test_prose_that_mentions_contact_media_or_author_stays():
    contact = "Reporters who want to contact the press office should do so before Friday, because the media schedule fills quickly."
    media = "Local media reported that the author of the study had contacted several agencies before publishing the findings."
    mid_email = "Questions about the program can be sent to the office at info@example.org, which answers within two days of receipt."
    html = f"<p>{EN}</p><p>{contact}</p><p>{media}</p><p>{mid_email}</p><p>{EN2}</p><p>{EN3}</p>"
    article = _extract(html, NASA)
    assert _paras(article) == [EN, contact, media, mid_email, EN2, EN3]
    assert article.removed == []


def test_contact_block_in_the_middle_of_an_article_stays():
    block = "Jane Roe, Washington, 202-555-0100, jane.roe@agency.gov"
    html = f"<p>{EN}</p><p>{block}</p><p>{EN2}</p><p>{EN3}</p>"
    assert block in _extract(html, NASA).body


def test_a_closing_paragraph_with_an_address_inside_a_sentence_stays():
    last = "Anyone who saw the event is asked to call 202-555-0100 or write to tips@example.org and describe what they saw that evening."
    article = _extract(f"<p>{EN}</p><p>{EN2}</p><p>{EN3}</p><p>{last}</p>", "https://news.example.org/a/1")
    assert _paras(article)[-1] == last


# ---- 2. editorial preface -> provenance ------------------------------------

GV_PREFACE = (
    '<p><em>This <a href="https://peacenews.com/what-african-elections-can-learn/">article</a> by '
    '<a href="https://peacenews.com/author/diba/">Diba Kosi Bilinga</a>\xa0was originally published by '
    '<a href="https://peacenews.com/">Peace News Network</a> on July 20, 2026. An edited version is being '
    "republished on Global Voices under a content partnership agreement.</em></p>"
)


def test_global_voices_preface_leaves_the_body_and_becomes_provenance():
    article = _extract(f"{GV_PREFACE}<p>{EN}</p><p>{EN2}</p><p>{EN3}</p>", GV)
    assert _paras(article) == [EN, EN2, EN3]
    (entry,) = article.provenance
    assert entry["kind"] == "republication"
    assert entry["original_publisher"] == "Peace News Network"
    assert entry["original_url"] == "https://peacenews.com/what-african-elections-can-learn/"
    assert "republished on Global Voices" in entry["text"]
    info = article.metadata()["extraction"]
    assert info["provenance"] == article.provenance
    assert info["removed_blocks"][0]["kind"] == "preface"


def test_spotlight_series_note_and_grant_note_are_prefaces_too():
    series = (
        "This post is part of Global Voices’ October 2026 Spotlight series, “Big Tech and Authoritarianism.” "
        "In this Spotlight, we explore how Big Tech facilitates and hinders authoritarian governments. You can support this coverage by donating here."
    )
    grant = (
        "This article was produced by Jane Roe from a local radio through a grant scheme, as part of a regional support project. "
        "It is being published on Global Voices as part of a content-sharing agreement."
    )
    for note in (series, grant):
        article = _extract(f"<p>{note}</p><p>{EN}</p><p>{EN2}</p><p>{EN3}</p>", GV)
        assert _paras(article) == [EN, EN2, EN3]
        assert article.provenance[0]["kind"] == "editorial_note"
        assert article.provenance[0]["text"].startswith("This ")


def test_a_lead_that_mentions_publication_in_passing_stays():
    lead = "The novel, originally published in 1950 by a small press, has been republished many times and still sells."
    article = _extract(f"<p>{lead}</p><p>{EN}</p><p>{EN2}</p><p>{EN3}</p>", GV)
    assert _paras(article)[0] == lead
    assert article.provenance == []


def test_originally_published_deep_in_the_body_stays():
    deep = "This article was originally published by a regional paper in 1998, and the quotation below comes from that edition."
    article = _extract(f"<p>{EN}</p><p>{EN2}</p><p>{EN3}</p><p>{EN}</p><p>{deep}</p><p>{EN2}</p>", GV)
    assert deep in article.body


# ---- 3. author biography ---------------------------------------------------


def test_trailing_about_the_author_section_is_removed():
    html = (
        f"<p>{EN}</p><p>{EN2}</p><p>{EN3}</p>"
        "<h3>About the author</h3><p>Alli Armijo is an artist, writer, and journalist based in New York. Her work appears in several outlets.</p>"
    )
    article = _extract(html, GV)
    assert _paras(article) == [EN, EN2, EN3]
    assert _kinds(article) == ["author_bio", "author_bio"]


def test_trailing_bio_paragraph_without_a_heading_is_removed():
    bio = "Ephraim Percy Kenyanito is an international lawyer working in trade, technology and media law. He has published a monthly roundup since 2014."
    article = _extract(f"<p>{EN}</p><p>{EN2}</p><p>{EN3}</p><p>{EN}</p><p>{bio}</p>", GV)
    assert bio not in article.body and _paras(article)[-1] == EN


def test_a_final_paragraph_about_a_person_in_the_story_stays():
    final = "Maria Lopez is a journalist who said the ministry never answered, and she told reporters the story would continue next week."
    article = _extract(f"<p>{EN}</p><p>{EN2}</p><p>{EN3}</p><p>{EN}</p><p>{final}</p>", GV)
    assert _paras(article)[-1] == final


def test_an_author_discussed_in_the_middle_stays():
    middle = "Priya Nair is a journalist based in Delhi who wrote the original report, and her editor confirmed the dates."
    article = _extract(f"<p>{EN}</p><p>{middle}</p><p>{EN2}</p><p>{EN3}</p><p>{EN}</p>", GV)
    assert middle in article.body


# ---- 4. media-player boilerplate -------------------------------------------


def test_voa_learning_english_player_placeholder_is_removed():
    html = (
        '<div class="c-mmp__overlay-body"><p class="ta-c"><span class="ico"></span>No media source currently available</p></div>'
        f"<p>Accessibility links</p><p>No media source currently available</p><p>{EN}</p><p>{EN2}</p><p>{EN3}</p>"
    )
    article = _extract(html, VOA_LE)
    assert _paras(article) == [EN, EN2, EN3]


def test_player_text_is_removed_without_knowing_the_host():
    html = f"<p>No media source currently available</p><p>{EN}</p><p>Download</p><p>{EN2}</p><p>Embed</p><p>{EN3}</p>"
    article = _extract(html, "https://news.example.org/a/1")
    assert _paras(article) == [EN, EN2, EN3]
    assert "player" in _kinds(article)


def test_voa_zhongwen_player_text_and_embed_widget_leave_the_body():
    html = (
        '<div class="c-mmp__player"><div class="c-mmp__overlay"><p>没有媒体可用资源</p></div>'
        '<div class="c-mmp__overlay-actions"><a class="share">分享</a><a>嵌入</a></div></div>'
        f"<p>{ZH}</p><p>{ZH}</p><p>{ZH}</p>"
    )
    article = _extract(html, VOA_ZH)
    assert _paras(article) == [ZH, ZH, ZH]


def test_voa_zhongwen_player_text_is_dropped_by_the_host_table_alone():
    html = f"<p>没有媒体可用资源</p><p>{ZH}</p><p>{ZH}</p><p>{ZH}</p>"
    assert _paras(_extract(html, VOA_ZH)) == [ZH, ZH, ZH]
    assert rules_for("www.voachinese.com")["player_text"] == ("没有媒体可用资源",)


def test_a_sentence_about_media_or_download_is_not_player_text():
    keep = "You can download the full report from the agency, and the media office will share the embed code on request."
    article = _extract(f"<p>{EN}</p><p>{keep}</p><p>{EN2}</p><p>{EN3}</p>", "https://news.example.org/a/1")
    assert keep in article.body


def test_file_download_labels_leave_the_body():
    article = _extract(f"<p>{EN}</p><p>JPEG (23.76 MB)</p><p>{EN2}</p><p>{EN3}</p>", "https://science.nasa.gov/x")
    assert _paras(article) == [EN, EN2, EN3]


# ---- references, version, plumbing -----------------------------------------


def test_trailing_reference_list_is_removed_but_a_cited_paragraph_stays():
    refs = (
        "<p>Abels, A. (2005) Spider impact structure, Kimberley Plateau, Western Australia. Australian Journal of Earth Sciences, 52(4-5), 653-664.</p>"
        "<p>Lunar and Planetary Institute, Shaping the Planets: Impact Cratering. Accessed October 8, 2026.</p>"
    )
    article = _extract(f"<p>{EN}</p><p>{EN2}</p><p>{EN3}</p>{refs}", "https://science.nasa.gov/x")
    assert _paras(article) == [EN, EN2, EN3]
    cited = "Researchers reported the crater was formed long ago (2005), and the study was accessed widely by other teams in the field today."
    assert cited in _extract(f"<p>{EN}</p><p>{cited}</p><p>{EN2}</p><p>{EN3}</p>", "https://science.nasa.gov/x").body


def test_cleanup_is_position_bound_and_extractor_version_is_bumped():
    items = [Item("Media Contact A. Person 202-555-0100 a@b.gov"), Item(EN), Item(EN2), Item(EN3)]
    assert cleanup(items, "https://x.org/a").removed == {}  # contact text up front, no label match for a leading block
    assert EXTRACTOR_VERSION == "article-extract/4"


def test_clean_article_has_no_cleanup_metadata():
    article = _extract(f"<p>{EN}</p><p>{EN2}</p><p>{EN3}</p>", NASA)
    info = article.metadata()["extraction"]
    assert "removed_blocks" not in info and "provenance" not in info
