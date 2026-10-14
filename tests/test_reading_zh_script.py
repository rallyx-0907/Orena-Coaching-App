"""Chinese script detection and its Reading wiring (D-197, PROPOSED).

Simplified is the default and is never labelled; Traditional is labelled; the two are never silently mixed.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from reading_quality_fixtures import VOA_ZH_ARTICLE
from writing_coach.languages.chinese.script_detection import (
    MIN_EVIDENCE,
    MIXED,
    SIMPLIFIED,
    TRADITIONAL,
    UNKNOWN,
    detect_script,
    script_counts,
)
from writing_coach.reading_article_extraction import extract_article
from writing_coach.reading_page_quality import SOFT_ISSUES, hard_issues, quality_flags

ROOT = Path(__file__).resolve().parents[1]

# Analects 1.1-1.4 (public domain, Traditional).
ANALECTS_TRADITIONAL = (
    "學而時習之，不亦說乎？有朋自遠方來，不亦樂乎？人不知而不慍，不亦君子乎？有子曰：其為人也孝弟，而好犯上者，鮮矣；"
    "不好犯上，而好作亂者，未之有也。君子務本，本立而道生。孝弟也者，其為仁之本與！子曰：巧言令色，鮮矣仁！"
    "曾子曰：吾日三省吾身：為人謀而不忠乎？與朋友交而不信乎？傳不習乎？"
)
SIMPLIFIED_NEWS = (
    "历史学者在雅典的演说中谈到了西方文明与现代政治之间的关系。他认为，民主制度的根基来自公民对公共事务的长期参与和讨论。"
    "听众提出了许多问题，包括欧洲与美国之间的合作应该如何继续。会后，主办方表示将把整场讨论整理成文字，供更多读者阅读。"
)
TRADITIONAL_NEWS = (
    "歷史學者在雅典的演說中談到了西方文明與現代政治之間的關係。他認為，民主制度的根基來自公民對公共事務的長期參與和討論。"
    "聽眾提出了許多問題，包括歐洲與美國之間的合作應該如何繼續。會後，主辦方表示將把整場討論整理成文字，供更多讀者閱讀。"
)


def test_a_simplified_voa_article_is_simplified():
    page = extract_article(VOA_ZH_ARTICLE, "https://www.voachinese.com/a/1.html")
    simplified, traditional = script_counts(page.body)
    assert traditional == 0 and simplified > 100
    assert detect_script(page.body) == SIMPLIFIED


@pytest.mark.parametrize("name", ["voa_zh_article_8208799.html", "voa_zh_article_8210116.html"])
def test_real_voa_zh_pages_are_simplified(name):
    html = (ROOT / "tests" / "fixtures" / "reading_quality" / name).read_text(encoding="utf-8")
    assert detect_script(extract_article(html, "https://www.voachinese.com/a/1.html").body) == SIMPLIFIED


def test_traditional_text_is_traditional():
    assert detect_script(ANALECTS_TRADITIONAL) == TRADITIONAL
    assert detect_script(TRADITIONAL_NEWS) == TRADITIONAL


def test_the_same_news_in_both_scripts_is_told_apart():
    assert detect_script(SIMPLIFIED_NEWS) == SIMPLIFIED
    assert detect_script(TRADITIONAL_NEWS) == TRADITIONAL


def test_half_and_half_is_mixed():
    assert detect_script(SIMPLIFIED_NEWS + TRADITIONAL_NEWS) == MIXED


def test_a_few_quoted_characters_of_the_other_script_do_not_make_a_text_mixed():
    assert detect_script(SIMPLIFIED_NEWS * 3 + "他提到《學而》。") == SIMPLIFIED
    assert detect_script(TRADITIONAL_NEWS * 3 + "他提到《学而》。") == TRADITIONAL


def test_short_or_script_neutral_text_is_unknown():
    assert detect_script("") == UNKNOWN
    assert detect_script(None) == UNKNOWN
    assert detect_script("今天天气很好。") == UNKNOWN  # a headline: too little evidence
    assert detect_script("人山大小上下人口手日月水火") == UNKNOWN  # only characters both scripts share
    assert detect_script("The quick brown fox" * 50) == UNKNOWN
    assert sum(script_counts("今天天气很好。")) < MIN_EVIDENCE


def test_characters_both_scripts_use_are_not_evidence():
    # 后 / 台 / 干 are simplified forms and also Traditional characters; they must not vote.
    assert script_counts("后台干") == (0, 0)


def test_the_derived_table_is_current():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_chinese_script_table.py"), "--check"],
        capture_output=True, text=True, cwd=ROOT, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


# ---- the soft quality code ---------------------------------------------------

def _flags(body: str, language: str = "zh") -> list[str]:
    return quality_flags(body=body, language=language, title="标题", confidence="high", facts={})


def test_a_mixed_chinese_text_gets_the_soft_code_only():
    flags = _flags((SIMPLIFIED_NEWS + TRADITIONAL_NEWS) * 2)
    assert "script_mixed" in flags
    assert "script_mixed" in SOFT_ISSUES
    assert hard_issues(flags) == []


def test_traditional_or_simplified_alone_is_not_flagged():
    assert "script_mixed" not in _flags(TRADITIONAL_NEWS * 3)
    assert "script_mixed" not in _flags(SIMPLIFIED_NEWS * 3)


def test_english_is_never_checked_for_script():
    assert "script_mixed" not in _flags((SIMPLIFIED_NEWS + TRADITIONAL_NEWS) * 2, language="en")
