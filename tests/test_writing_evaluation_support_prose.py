"""A Chinese finding explained in Vietnamese may quote the Chinese it teaches.

The recall loss this holds shut (`docs/project/ZH_WRITING_EVALUATOR_RECALL.md`,
cause 1, since c71c644): with a non-CJK support language the normalizer dropped
every finding whose explanation or rule held one Han character, so a measure
word, a particle or 了 - the errors that most need the character quoted - were
the ones a Chinese learner with Vietnamese support never saw. The rule is one
for every language pair (`support_prose_admits`): support-language prose may
quote a CJK learning language; what is refused is an explanation that is not
support-language prose at all, and CJK in an explanation for a learning
language that is not written in it.
"""
from __future__ import annotations

from typing import Any

import pytest

from writing_coach.languages.chinese.profile import ERROR_CATEGORIES as CHINESE_ERROR_CATEGORIES
from writing_coach.languages.english.profile import ERROR_CATEGORIES as ENGLISH_ERROR_CATEGORIES
from writing_coach.writing_evaluation import normalize_writing_evaluation, support_prose_admits

RUBRIC_WEIGHTS = {"grammar": 0.6, "vocabulary": 0.4}
ZH_TEXT = "我有三个书。我昨天去了北京。"


def _zh(raw: dict[str, Any], *, support_cjk: bool = False) -> dict[str, Any]:
    """Chinese learning language; the support language's script is the caller's (vi: not CJK)."""
    return normalize_writing_evaluation(
        raw,
        rubric_weights=RUBRIC_WEIGHTS,
        allowed_levels=("HSK1", "HSK2"),
        score_to_level=lambda _score: "HSK1",
        error_categories=CHINESE_ERROR_CATEGORIES,
        allow_cjk=True,
        learner_text=ZH_TEXT,
        allow_explanation_cjk=support_cjk,
    )


def _measure_word(**overrides: Any) -> dict[str, Any]:
    item = {
        "category": "measure_word",
        "fragment": "三个书",
        "explanation_vi": "Sách dùng lượng từ 本, không dùng 个.",
        "suggestion": "三本书",
        "mini_rule_vi": "Danh từ chỉ sách, vở đi với lượng từ 本.",
        "confidence": 0.9,
    }
    item.update(overrides)
    return item


def test_the_measure_word_finding_that_was_dropped_is_kept() -> None:
    result = _zh({"errors": [_measure_word()]})
    assert [error["fragment"] for error in result["errors"]] == ["三个书"]
    assert "本" in result["errors"][0]["explanation_vi"]


def test_an_explanation_that_is_not_vietnamese_prose_is_still_refused() -> None:
    result = _zh({"errors": [_measure_word(explanation_vi="书要用量词本，不用个。")]})
    assert result["errors"] == []
    result = _zh({"errors": [_measure_word(mini_rule_vi="书的量词是本。")]})
    assert result["errors"] == [], "the rule is held to the same test as the explanation"


def test_summary_lists_and_strength_evidence_may_quote_the_character_too() -> None:
    result = _zh(
        {
            "summary_vi": "Bạn dùng 了 đúng chỗ khi kể việc đã xong.",
            "strengths_vi": ["Dùng 了 đúng sau động từ."],
            "priorities_vi": ["Ôn lượng từ 本 và 个."],
            "strength_evidence": [
                {
                    "category": "grammar",
                    "fragment": "我昨天去了北京",
                    "explanation_vi": "Bạn đặt 了 ngay sau động từ 去 để nói việc đã xảy ra.",
                    "confidence": 0.9,
                }
            ],
        }
    )
    assert result["summary_vi"].startswith("Bạn dùng 了")
    assert result["strengths_vi"] == ["Dùng 了 đúng sau động từ."]
    assert result["priorities_vi"] == ["Ôn lượng từ 本 và 个."]
    assert len(result["strength_evidence"]) == 1


def test_a_summary_written_in_chinese_for_a_vietnamese_reader_is_still_emptied() -> None:
    result = _zh({"summary_vi": "你的文章结构清楚，但是量词用错了。", "strengths_vi": ["结构清楚。"]})
    assert result["summary_vi"] == ""
    assert result["strengths_vi"] == []


def test_a_cjk_support_language_explains_in_its_own_script() -> None:
    result = _zh({"errors": [_measure_word(explanation_vi="书的量词是本，不是个。")]}, support_cjk=True)
    assert len(result["errors"]) == 1


def test_english_learning_language_still_refuses_cjk_in_a_vietnamese_explanation() -> None:
    result = normalize_writing_evaluation(
        {"errors": [{
            "category": "agreement",
            "fragment": "I has a dog.",
            "explanation_vi": "Động từ phải hợp chủ ngữ, như 我有.",
            "suggestion": "I have a dog.",
            "mini_rule_vi": "I đi với have.",
            "confidence": 0.9,
        }]},
        rubric_weights=RUBRIC_WEIGHTS,
        allowed_levels=("A1", "B2"),
        score_to_level=lambda _score: "A1",
        error_categories=ENGLISH_ERROR_CATEGORIES,
        allow_cjk=False,
        learner_text="I has a dog.",
        allow_explanation_cjk=False,
    )
    assert result["errors"] == [], "English is not written in CJK: there is nothing to quote"


@pytest.mark.parametrize(
    ("text", "support_cjk", "target_cjk", "admitted"),
    [
        ("Không có chữ Hán ở đây.", False, False, True),
        ("Sách dùng lượng từ 本.", False, True, True),
        ("Sách dùng lượng từ 本.", False, False, False),
        ("书要用量词本。", False, True, False),
        ("书要用量词本。", True, True, True),
        ("本", False, True, False),
        ("Use 本 for books.", False, True, True),
        ("", False, True, True),
    ],
)
def test_the_one_rule(text: str, support_cjk: bool, target_cjk: bool, admitted: bool) -> None:
    assert support_prose_admits(text, support_cjk=support_cjk, target_cjk=target_cjk) is admitted
