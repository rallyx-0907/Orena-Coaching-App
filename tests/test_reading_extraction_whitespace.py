"""D1 (glued words at inline boundaries) and D2 (`<br><br>` is a paragraph break).

Fixtures are synthetic, modelled on the shapes seen in the 2026-10-13 trial.
"""
from __future__ import annotations

from writing_coach.reading_article_extraction import extract_article

BASE = "https://news.example.org/a/1"
EN = "A full sentence of real article prose goes here today, and it keeps going for a while. "
ZH = "这是一段足够长的真实新闻正文，用来确保提取器把它当作文章的主体内容来处理。"


def _page(inner: str) -> str:
    return f"<html><body><article>{inner}</article></body></html>"


def _body(inner: str) -> str:
    return extract_article(_page(inner), BASE).body


def _paras(body: str) -> list[str]:
    return [p for p in body.split("\n\n") if p]


def test_space_between_inline_elements_still_separates_words():
    body = _body(f"<p>{EN}It was first <em>published</em> by <a href='/x'><em>Engage</em></a> Media.</p>")
    assert "first published by Engage Media." in body


def test_whitespace_moved_inside_the_inline_tag_is_kept():
    body = _body(f"<p>{EN}It was <em>first </em><a href='/x'><em>published</em></a><em> by</em> EngageMedia today.</p>")
    assert "first published by EngageMedia" in body
    assert "firstpublished" not in body and "publishedby" not in body


def test_newline_and_nbsp_at_inline_boundaries():
    body = _body(f"<p>{EN}agreement.\n<strong>It is also</strong>\n<span>part</span>&nbsp;of it.</p>")
    assert "agreement. It is also part of it." in body


def test_nested_inline_elements_and_no_source_whitespace_stay_joined():
    body = _body(f"<p>{EN}He saw <b><i>the </i></b><u>sea</u>, and un<em>believ</em>able things.</p>")
    assert "the sea," in body
    assert "unbelievable" in body  # no whitespace in the source, none invented


def test_cjk_is_not_given_spaces_at_inline_or_newline_boundaries():
    body = _body(f"<p>{ZH}他说<em>这件事</em>\n很重要，<a href='/x'>大家</a>\n都同意。</p>")
    assert "他说这件事很重要，大家都同意。" in body


def test_mixed_script_keeps_the_space_between_latin_words():
    body = _body(f"<p>{ZH}他在 <em>Global</em> <em>Voices</em> 工作。</p>")
    assert "Global Voices" in body


def test_single_br_is_a_line_break_inside_one_paragraph():
    paras = _paras(_body(f"<p>{EN}first line<br>second line of the same paragraph.</p>"))
    assert len(paras) == 1
    assert "first line second line" in paras[0]


def test_double_br_splits_paragraphs_english():
    paras = _paras(_body(f"<p>{EN}End of one.<br><br>{EN}End of two.<br /> \n <br/>{EN}End of three.</p>"))
    assert len(paras) == 3
    assert paras[0].endswith("End of one.") and paras[2].endswith("End of three.")


def test_double_br_splits_paragraphs_chinese():
    paras = _paras(_body(f"<p>{ZH}第一段。<br /><br />{ZH}第二段。<br>\n<br>{ZH}第三段。</p>"))
    assert len(paras) == 3
    assert paras[1].endswith("第二段。")


def test_double_br_in_a_bare_div_run_splits_too():
    paras = _paras(_body(f"<div>{EN}One.<br><br>{EN}Two.</div>"))
    assert len(paras) == 2


def test_br_split_chinese_report_counts_its_paragraphs():
    result = extract_article(_page(f"<p>{ZH * 3}<br><br>{ZH * 3}<br><br>{ZH * 3}</p>"), BASE)
    assert result.prose_paragraphs >= 3
