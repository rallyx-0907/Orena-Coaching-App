"""A Chinese chapter is counted in characters, not in whitespace-split tokens.

`reading_seconds` divides the stored count by a characters-per-minute pace for
Chinese, so a count taken with `str.split()` (one token per unspaced paragraph)
made a long Chinese chapter read as a minute or two.
"""
from __future__ import annotations

from writing_coach.epub_import import ParsedChapter


def _chapter(*paragraphs: str) -> ParsedChapter:
    return ParsedChapter(
        chapter_key="c",
        title="t",
        blocks=tuple({"type": "paragraph", "text": p} for p in paragraphs),
        paragraphs=tuple(paragraphs),
    )


def test_chinese_paragraphs_count_characters():
    assert _chapter("我在朝花夕拾里读书。", "第二段文字").word_count == 9 + 5


def test_english_paragraphs_still_count_words():
    assert _chapter("Down the rabbit hole", "she fell").word_count == 6


def test_mixed_text_counts_both():
    assert _chapter("读 the book 吧").word_count == 2 + 2


def test_fullwidth_latin_words_are_not_discarded_as_punctuation():
    assert _chapter("读 ＥＰＵＢ ｂｏｏｋ 吧！").word_count == 4
