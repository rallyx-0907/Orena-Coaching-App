"""The Python Dictation evaluator is held to the browser's, vector for vector (D4 I18, D-103.2)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from writing_coach.dictation_evaluator import (
    ListeningPracticeError,
    evaluate_listening_reconstruction,
    listening_units,
)

GOLDEN = json.loads(
    (Path(__file__).parent / "fixtures" / "dictation_golden.json").read_text(encoding="utf-8")
)["cases"]


@pytest.mark.parametrize("case", GOLDEN, ids=lambda case: json.dumps(case["input"], ensure_ascii=True)[:70])
def test_the_port_matches_the_browser_on_every_golden_vector(case):
    if "error" in case:
        with pytest.raises(ListeningPracticeError) as caught:
            evaluate_listening_reconstruction(**case["input"])
        assert caught.value.code == case["error"]
    else:
        assert evaluate_listening_reconstruction(**case["input"]) == case["result"]


def test_the_vector_file_covers_both_languages_and_every_refusal():
    languages = {case["input"]["source_language"] for case in GOLDEN}
    assert {"en", "zh"} <= languages
    refusals = {case.get("error") for case in GOLDEN} - {None}
    assert {"answer_empty", "answer_too_large", "evaluation_too_large", "canonical_empty"} <= refusals


def test_units_split_han_by_character_and_words_by_run():
    assert listening_units("我用 GPT-4 学习 123", "zh") == ["我", "用", "gpt-4", "学", "习", "123"]
    assert listening_units("Don\u2019t stop", "en") == ["don't", "stop"]


def test_the_percentage_rounds_half_up_like_math_round():
    # 1 - 1/8 = 0.875 -> 87.5 -> 88 (half up); banker's rounding would give 88 too, so pin 0.5 cases:
    # 1 - 1/40 = 0.975 -> 97.5 -> 98 under Math.round.
    result = evaluate_listening_reconstruction(
        source_language="en", expected=" ".join(["a"] * 40), answer=" ".join(["a"] * 39 + ["b"])
    )
    assert result["accuracy_percent"] == 98
