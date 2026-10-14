"""D-198: the interim automatic level estimate (reading-level/2).

The expected bands are PROVISIONAL JUDGEMENTS of the author, not calibrated truth: the repository
has no CEFR/HSK list and no graded text to calibrate against (calibration is option A of D-198).
These tests guard the saturation defect D6 (a press release rated C2, every Chinese news article
HSK6), not the accuracy of a band. The reviewer override (D-196) is covered by
test_reading_content_repository.py and is untouched: the estimator never sees `reviewed_level`.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from writing_coach.reading_article_extraction import extract_article
from writing_coach.reading_processing import (
    EN_LEVEL_BANDS,
    LEVEL_VERSION,
    LOW_CONFIDENCE,
    _en_level_words,
    analyze_article,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _body(relative: str) -> str:
    html = (FIXTURES / relative).read_text(encoding="utf-8")
    return extract_article(html, "https://example.org/a/1").body


@pytest.mark.parametrize(
    ("fixture", "provisional"),
    [
        ("reading_quality/nasa_news_release.html", {"B2", "C1"}),
        ("reading_quality/global_voices_article.html", {"B2", "C1"}),
        ("voa_en/wire_adapted_article.html", {"B1", "B2"}),
    ],
)
def test_english_news_fixtures_no_longer_saturate_at_c2(fixture, provisional):
    analysis = analyze_article(_body(fixture), "en")
    assert analysis.estimated_level in provisional
    assert analysis.level_version == LEVEL_VERSION == "reading-level/2"


@pytest.mark.parametrize(
    "fixture",
    [
        "voa_zh/staff_article.html",
        "voa_zh/wire_derived_article.html",
        "voa_zh/wire_derived_article_ap.html",
        "reading_quality/voa_zh_article_8208799.html",
        "reading_quality/voa_zh_article_8210116.html",
    ],
)
def test_chinese_news_fixtures_no_longer_saturate_at_hsk6(fixture):
    assert analyze_article(_body(fixture), "zh").estimated_level in {"HSK4", "HSK5"}


def test_the_estimate_still_separates_simple_from_dense_text_in_both_languages():
    simple_en = analyze_article("The dog runs. The cat sits. A bird sings. " * 10, "en")
    dense_en = analyze_article(_body("reading_quality/nasa_news_release.html"), "en")
    assert EN_LEVEL_BANDS.index(dense_en.estimated_level) > EN_LEVEL_BANDS.index(simple_en.estimated_level)
    simple_zh = analyze_article("我有一只猫。它很小。我们在家。我爱它。他是我的好朋友。" * 8, "zh")
    news_zh = analyze_article(_body("voa_zh/wire_derived_article.html"), "zh")
    assert simple_zh.estimated_level < news_zh.estimated_level


def test_names_acronyms_numbers_and_hyphen_halves_leave_the_english_signals():
    words = _en_level_words("Yesterday Johnson and NASA flew 10km in a nuclear-powered craft.")
    assert words == ["yesterday", "and", "flew", "in", "a", "nuclear", "powered", "craft"]
    plain = "The team went to the lake. It was a warm day. We saw the boat. " * 6
    loaded = "The team went to NASA headquarters. It was a warm day in Washington. We saw the Constellation-class boat. " * 6
    levels = EN_LEVEL_BANDS
    assert levels.index(analyze_article(loaded, "en").estimated_level) <= levels.index(
        analyze_article(plain, "en").estimated_level
    ) + 1


def test_a_sentence_initial_capital_is_still_counted():
    assert _en_level_words('Exploration begins. "Discovery" follows.\n\nSpace waits.') == [
        "exploration", "begins", "discovery", "follows", "space", "waits",
    ]


def test_chinese_clauses_not_comma_joined_sentences_set_the_length_signal():
    clause = "我们今天去公园散步看花"
    comma_joined = "，".join([clause] * 8) + "。"
    full_stops = "。".join([clause] * 8) + "。"
    assert analyze_article(comma_joined, "zh").average_sentence_length > analyze_article(full_stops, "zh").average_sentence_length
    assert analyze_article(comma_joined, "zh").estimated_level == analyze_article(full_stops, "zh").estimated_level


def test_a_low_confidence_estimate_is_capped_at_c1_and_hsk5():
    dense_en = analyze_article(
        "Notwithstanding the committee's preliminary determination, the subsequent reassessment "
        "demonstrated that institutional accountability mechanisms had systematically underestimated "
        "the environmental consequences of the proposed infrastructural redevelopment programme "
        "notwithstanding considerable organisational counterarguments.",
        "en",
    )
    assert dense_en.confidence < LOW_CONFIDENCE
    assert dense_en.estimated_level != "C2"
    dense_zh = analyze_article("国际社会对于经济发展与环境保护之间的复杂关系进行了深入讨论并提出了许多不同意见" * 2, "zh")
    assert dense_zh.confidence < LOW_CONFIDENCE
    assert dense_zh.estimated_level != "HSK6"


def test_en_zh_parity_each_language_stays_on_its_own_scale_and_carries_the_version():
    en = analyze_article("The cat sat on the mat. " * 40, "en")
    zh = analyze_article("今天天气很好，我们去公园散步。" * 40, "zh")
    assert en.estimated_level in EN_LEVEL_BANDS and zh.estimated_level.startswith("HSK")
    assert en.level_version == zh.level_version == LEVEL_VERSION


def test_contractions_keep_their_stem_and_drop_one_and_two_letter_fragments():
    assert _en_level_words("It's what they're doing, isn't it? The boy's kite.") == [
        "what", "they", "doing", "isn", "it", "the", "boy", "kite",
    ]
