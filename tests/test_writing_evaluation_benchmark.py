from __future__ import annotations

from dataclasses import FrozenInstanceError
import json

import pytest

from writing_coach.languages.chinese.profile import (
    ERROR_CATEGORIES as CHINESE_ERROR_CATEGORIES,
    PROFILE as CHINESE_PROFILE,
    RUBRIC_WEIGHTS as CHINESE_RUBRIC_WEIGHTS,
    score_to_level as chinese_score_to_level,
)
from writing_coach.languages.english.profile import (
    ERROR_CATEGORIES as ENGLISH_ERROR_CATEGORIES,
    PROFILE as ENGLISH_PROFILE,
    RUBRIC_WEIGHTS as ENGLISH_RUBRIC_WEIGHTS,
    score_to_level as english_score_to_level,
)
from writing_coach.writing_evaluation import normalize_writing_evaluation
from writing_coach.writing_evaluation_benchmark import (
    RUBRIC_DIMENSIONS,
    WRITING_BENCHMARK_VERSION,
    BenchmarkKind,
    build_benchmark_report,
    compare_pairwise_results,
    compare_target_level_results,
    evaluate_benchmark_result,
)
from writing_coach.writing_evaluation_benchmark_fixtures import (
    CHINESE_BENCHMARK_CASES,
    ENGLISH_BENCHMARK_CASES,
    WRITING_BENCHMARK_CASES,
    benchmark_case,
    known_failing_result,
    known_passing_result,
)


def _categories(language: str) -> tuple[str, ...]:
    return ENGLISH_ERROR_CATEGORIES if language == "en" else CHINESE_ERROR_CATEGORIES


def _evaluate(case, result):
    return evaluate_benchmark_result(
        case,
        result,
        allowed_error_categories=_categories(case.language),
    )


def _checks(evaluation) -> set[str]:
    return {finding.check for finding in evaluation.failed_checks}


def test_corpus_contract_is_versioned_immutable_balanced_and_complete():
    assert WRITING_BENCHMARK_VERSION == 1
    assert len(ENGLISH_BENCHMARK_CASES) == 12
    assert len(CHINESE_BENCHMARK_CASES) == 12
    assert len({case.case_id for case in WRITING_BENCHMARK_CASES}) == len(WRITING_BENCHMARK_CASES)
    assert {case.kind for case in WRITING_BENCHMARK_CASES} == set(BenchmarkKind)

    levels = {"en": set(ENGLISH_PROFILE.levels), "zh": set(CHINESE_PROFILE.levels)}
    categories = {"en": set(ENGLISH_ERROR_CATEGORIES), "zh": set(CHINESE_ERROR_CATEGORIES)}
    for case in WRITING_BENCHMARK_CASES:
        assert case.language in {"en", "zh"}
        assert case.target_level in levels[case.language]
        assert set(case.constraints.expected_demonstrated_levels) <= levels[case.language]
        assert case.task_prompt.strip()
        assert case.learner_text.strip()
        assert case.rationale.strip()
        assert case.constraints.required_error_categories <= categories[case.language]
        assert all(band.dimension in RUBRIC_DIMENSIONS for band in case.constraints.score_bands)
        assert all(0 <= band.minimum <= band.maximum <= 100 for band in case.constraints.score_bands)

    with pytest.raises(FrozenInstanceError):
        ENGLISH_BENCHMARK_CASES[0].target_level = "C2"


def test_corpus_contains_required_english_and_chinese_quality_traps():
    english_required = set().union(
        *(case.constraints.required_error_categories for case in ENGLISH_BENCHMARK_CASES)
    )
    chinese_required = set().union(
        *(case.constraints.required_error_categories for case in CHINESE_BENCHMARK_CASES)
    )
    assert {"article", "agreement", "preposition", "word_form"} <= english_required
    assert {"word_order", "aspect", "particle", "measure_word", "collocation"} <= chinese_required
    assert any("I care about fashion" in case.constraints.protected_correct_fragments for case in ENGLISH_BENCHMARK_CASES)
    assert any(case.constraints.protected_correct_fragments for case in CHINESE_BENCHMARK_CASES)
    assert {case.target_pair_id for case in ENGLISH_BENCHMARK_CASES if case.target_pair_id} == {"en-target-stability"}
    assert {case.target_pair_id for case in CHINESE_BENCHMARK_CASES if case.target_pair_id} == {"zh-target-stability"}


def test_deterministic_fake_fixtures_produce_known_pass_and_fail_outcomes():
    for case in WRITING_BENCHMARK_CASES:
        passing = _evaluate(case, known_passing_result(case))
        failing = _evaluate(case, known_failing_result(case))
        assert passing.passed, (case.case_id, passing.to_dict())
        assert not failing.passed
        assert "evidence_precision" in _checks(failing)


@pytest.mark.parametrize("case_id", ["en-evidence-integrity", "zh-evidence-integrity"])
def test_evidence_must_be_nonempty_literal_learner_text(case_id):
    case = benchmark_case(case_id)
    result = known_passing_result(case)
    result["strength_evidence"] = [
        {
            "category": "grammar",
            "fragment": case.learner_text,
            "explanation_vi": "Bằng chứng chính xác.",
            "confidence": 0.9,
        }
    ]
    assert _evaluate(case, result).passed

    result["strength_evidence"][0]["fragment"] = ""
    evaluation = _evaluate(case, result)
    assert not evaluation.passed
    assert "evidence_precision" in _checks(evaluation)


@pytest.mark.parametrize(
    ("case_id", "fragment"),
    [
        ("en-fashion-false-positive", "I care about fashion"),
        ("zh-transit-false-positive", "我每天坐地铁去上班"),
    ],
)
def test_protected_correct_fragments_fail_false_positive_gate(case_id, fragment):
    case = benchmark_case(case_id)
    result = known_passing_result(case)
    result["errors"] = [
        {
            "category": "other",
            "fragment": fragment,
            "explanation_vi": "Đánh dấu sai.",
            "suggestion": f"Revised: {fragment}",
            "mini_rule_vi": "Không sửa cấu trúc đúng.",
            "confidence": 0.9,
        }
    ]
    evaluation = _evaluate(case, result)
    assert not evaluation.passed
    assert "false_positive" in _checks(evaluation)
    assert dict(evaluation.metrics)["false_positive_count"] == 1


@pytest.mark.parametrize("case_id", ["en-obvious-agreement", "zh-obvious-word-order"])
def test_required_errors_need_literal_evidence_and_expected_category(case_id):
    case = benchmark_case(case_id)
    assert _evaluate(case, known_passing_result(case)).passed

    result = known_passing_result(case)
    result["errors"] = []
    missing = _evaluate(case, result)
    assert not missing.passed
    assert "required_error_recall" in _checks(missing)

    result = known_passing_result(case)
    result["errors"][0]["category"] = "other"
    wrong_category = _evaluate(case, result)
    assert not wrong_category.passed
    assert "required_error_recall" in _checks(wrong_category)


def test_low_confidence_error_cannot_survive_normalization_and_then_fails_recall():
    case = benchmark_case("en-obvious-agreement")
    raw = {
        **{dimension: 70 for dimension in ENGLISH_RUBRIC_WEIGHTS},
        "cefr_estimate": "B1",
        "errors": [
            {
                "category": "agreement",
                "fragment": "brother work",
                "explanation_vi": "Thiếu chia động từ.",
                "suggestion": "brother works",
                "mini_rule_vi": "Chia động từ ngôi thứ ba.",
                "confidence": 0.4,
            }
        ],
    }
    normalized = normalize_writing_evaluation(
        raw,
        rubric_weights=ENGLISH_RUBRIC_WEIGHTS,
        allowed_levels=ENGLISH_PROFILE.levels,
        score_to_level=english_score_to_level,
        allow_cjk=False,
        learner_text=case.learner_text,
        error_categories=ENGLISH_ERROR_CATEGORIES,
    )
    assert normalized["errors"] == []
    evaluation = _evaluate(case, normalized)
    assert not evaluation.passed
    assert "required_error_recall" in _checks(evaluation)


def test_benchmark_rejects_low_confidence_and_unknown_categories_defensively():
    case = benchmark_case("zh-obvious-word-order")
    result = known_passing_result(case)
    result["errors"][0]["confidence"] = 0.5
    result["errors"][0]["category"] = "invented_category"
    evaluation = _evaluate(case, result)
    assert not evaluation.passed
    assert {"confidence_threshold", "category_validity"} <= _checks(evaluation)


def test_correction_must_be_nonempty_and_materially_different():
    case = benchmark_case("en-obvious-agreement")
    result = known_passing_result(case)
    result["errors"][0]["suggestion"] = case.learner_text
    same = _evaluate(case, result)
    assert not same.passed
    assert "correction_usefulness" in _checks(same)

    result["errors"][0]["suggestion"] = "My brother works from home every Friday."
    assert _evaluate(case, result).passed


def test_feedback_must_explain_the_evidence_and_the_reusable_rule():
    case = benchmark_case("en-obvious-agreement")
    result = known_passing_result(case)
    result["errors"][0]["explanation_vi"] = ""
    result["errors"][0]["mini_rule_vi"] = ""

    evaluation = _evaluate(case, result)

    assert not evaluation.passed
    assert "actionable_feedback" in _checks(evaluation)


def test_rubric_scores_are_complete_bounded_and_respect_broad_case_bands():
    case = benchmark_case("en-task-one-reason")
    result = known_passing_result(case)
    assert _evaluate(case, result).passed

    result["grammar"] = 101
    result["task_achievement"] = 90
    evaluation = _evaluate(case, result)
    assert not evaluation.passed
    assert {"score_bounds", "score_band"} <= _checks(evaluation)


@pytest.mark.parametrize(
    ("stronger_id", "weaker_id"),
    [
        ("en-clean-agreement", "en-obvious-agreement"),
        ("zh-clean-word-order", "zh-obvious-word-order"),
    ],
)
def test_pairwise_clean_text_cannot_score_below_broken_text_beyond_tolerance(stronger_id, weaker_id):
    stronger = benchmark_case(stronger_id)
    weaker = benchmark_case(weaker_id)
    stronger_result = known_passing_result(stronger)
    weaker_result = known_passing_result(weaker)
    stronger_result["grammar"] = 82
    weaker_result["grammar"] = 62
    assert compare_pairwise_results(stronger, stronger_result, weaker, weaker_result).passed

    weaker_result["grammar"] = 84
    comparison = compare_pairwise_results(stronger, stronger_result, weaker, weaker_result)
    assert not comparison.passed
    assert comparison.failed_checks[0].check == "pairwise_scoring"


@pytest.mark.parametrize(
    ("first_id", "second_id", "first_level", "second_level", "declared_levels"),
    [
        ("en-target-a2", "en-target-c1", "B1", "B2", ENGLISH_PROFILE.levels),
        ("zh-target-hsk2", "zh-target-hsk7-9", "HSK4", "HSK5", CHINESE_PROFILE.levels),
    ],
)
def test_target_level_pairs_allow_adjacent_levels_and_small_score_drift_but_reject_score_drift_and_echo(
    first_id, second_id, first_level, second_level, declared_levels
):
    first = benchmark_case(first_id)
    second = benchmark_case(second_id)
    first_result = known_passing_result(first)
    second_result = known_passing_result(second)
    second_result["grammar"] = first_result["grammar"] + 5
    first_result["cefr_estimate"] = first_level
    second_result["cefr_estimate"] = second_level
    comparison = compare_target_level_results(
        first,
        first_result,
        second,
        second_result,
        declared_levels=declared_levels,
    )
    assert comparison.passed
    assert dict(comparison.metrics)["demonstrated_level_drift"] == 1

    second_result["grammar"] = first_result["grammar"] + 6
    drift = compare_target_level_results(
        first,
        first_result,
        second,
        second_result,
        declared_levels=declared_levels,
    )
    assert not drift.passed
    assert "target_level_stability" in {item.check for item in drift.failed_checks}

    second_result["grammar"] = first_result["grammar"]
    first_result["cefr_estimate"] = first.target_level
    second_result["cefr_estimate"] = second.target_level
    echo = compare_target_level_results(
        first,
        first_result,
        second,
        second_result,
        declared_levels=declared_levels,
    )
    assert not echo.passed
    assert "target_level_echo" in {item.check for item in echo.failed_checks}


@pytest.mark.parametrize(
    ("first_id", "second_id", "first_level", "second_level", "declared_levels"),
    [
        ("en-target-a2", "en-target-c1", "A1", "C2", ENGLISH_PROFILE.levels),
        ("zh-target-hsk2", "zh-target-hsk7-9", "HSK1", "HSK6", CHINESE_PROFILE.levels),
    ],
)
def test_target_level_pair_rejects_unreasonable_ordered_band_jump_without_language_branching(
    first_id, second_id, first_level, second_level, declared_levels
):
    first = benchmark_case(first_id)
    second = benchmark_case(second_id)
    first_result = known_passing_result(first)
    second_result = known_passing_result(second)
    first_result["cefr_estimate"] = first_level
    second_result["cefr_estimate"] = second_level

    comparison = compare_target_level_results(
        first,
        first_result,
        second,
        second_result,
        declared_levels=declared_levels,
    )

    assert not comparison.passed
    assert "demonstrated_level_drift" in {item.check for item in comparison.failed_checks}


@pytest.mark.parametrize(
    ("first_id", "second_id", "alternative_level", "declared_levels"),
    [
        ("en-target-a2", "en-target-c1", "B2", ENGLISH_PROFILE.levels),
        ("zh-target-hsk2", "zh-target-hsk7-9", "HSK4", CHINESE_PROFILE.levels),
    ],
)
def test_target_pair_does_not_require_fixture_authors_single_preferred_label(
    first_id, second_id, alternative_level, declared_levels
):
    first = benchmark_case(first_id)
    second = benchmark_case(second_id)
    first_result = known_passing_result(first)
    second_result = known_passing_result(second)
    first_result["cefr_estimate"] = alternative_level
    second_result["cefr_estimate"] = alternative_level

    assert compare_target_level_results(
        first,
        first_result,
        second,
        second_result,
        declared_levels=declared_levels,
    ).passed


def test_chinese_normalized_result_is_accepted_without_provider_or_runtime_dependencies():
    case = benchmark_case("zh-clean-word-order")
    raw = {
        **{dimension: 80 for dimension in CHINESE_RUBRIC_WEIGHTS},
        "cefr_estimate": "HSK2",
        "summary_vi": "Câu rõ ràng.",
        "strength_evidence": [
            {
                "category": "grammar",
                "fragment": "我每天学习汉语",
                "explanation_vi": "Trật tự từ tự nhiên.",
                "confidence": 0.9,
            }
        ],
    }
    normalized = normalize_writing_evaluation(
        raw,
        rubric_weights=CHINESE_RUBRIC_WEIGHTS,
        allowed_levels=CHINESE_PROFILE.levels,
        score_to_level=chinese_score_to_level,
        allow_cjk=True,
        learner_text=case.learner_text,
        error_categories=CHINESE_ERROR_CATEGORIES,
    )
    assert _evaluate(case, normalized).passed


def test_report_is_json_serializable_versioned_reproducible_and_secret_field_safe():
    case = benchmark_case("en-evidence-integrity")
    result = known_passing_result(case)
    result["api_key"] = "super-secret"
    evaluation = _evaluate(case, result)
    report = build_benchmark_report(
        timestamp="2026-08-13T10:00:00Z",
        evaluator_label="fixture:known-pass-v1",
        case=case,
        normalized_result=result,
        evaluation=evaluation,
    )
    encoded = json.dumps(report, ensure_ascii=False, sort_keys=True)
    assert report["benchmark_version"] == 1
    assert report["timestamp"] == "2026-08-13T10:00:00Z"
    assert report["evaluator_label"] == "fixture:known-pass-v1"
    assert report["case"]["case_id"] == case.case_id
    assert report["findings"]["passed"] is True
    assert "api_key" not in report["normalized_result"]
    assert "super-secret" not in encoded
    assert json.loads(encoded) == report

    failing_evaluation = _evaluate(case, known_failing_result(case))
    failing_report = build_benchmark_report(
        timestamp="2026-08-13T10:00:00Z",
        evaluator_label="fixture:known-fail-v1",
        case=case,
        normalized_result=known_failing_result(case),
        evaluation=failing_evaluation,
    )
    assert failing_report["findings"]["passed"] is False
    assert failing_report["findings"]["failed_checks"][0]["check"] == "evidence_precision"
    json.dumps(failing_report, ensure_ascii=False)


def test_report_rejects_credential_shaped_evaluator_label():
    case = benchmark_case("en-evidence-integrity")
    result = known_passing_result(case)
    evaluation = _evaluate(case, result)
    with pytest.raises(ValueError, match="harmless identifier"):
        build_benchmark_report(
            timestamp="2026-08-13T10:00:00Z",
            evaluator_label="https://user:secret@example.invalid/model?api_key=secret",
            case=case,
            normalized_result=result,
            evaluation=evaluation,
        )
