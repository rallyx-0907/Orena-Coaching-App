"""Offline quality benchmark contracts for normalized Writing evaluations.

This module is deliberately independent of HTTP, persistence, provider clients,
and environment configuration.  It evaluates already-normalized Writing results
against curated, tolerant quality constraints.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
import math
import re
from typing import Any, Mapping, Sequence

from writing_coach.writing_evaluation import CONFIDENCE_THRESHOLD


WRITING_BENCHMARK_VERSION = 1
PAIRWISE_SCORE_TOLERANCE = 1.0
TARGET_LEVEL_SCORE_TOLERANCE = 5.0

RUBRIC_DIMENSIONS = (
    "grammar",
    "vocabulary",
    "coherence",
    "task_achievement",
    "naturalness",
)


class BenchmarkKind(str, Enum):
    CLEAN = "clean"
    OBVIOUS_ERROR = "obvious_error"
    NATURALNESS = "naturalness"
    TASK_ACHIEVEMENT = "task_achievement"
    COHERENCE = "coherence"
    EVIDENCE_INTEGRITY = "evidence_integrity"
    FALSE_POSITIVE_TRAP = "false_positive_trap"
    TARGET_LEVEL_BIAS = "target_level_bias"
    STRONG_TEXT = "strong_text"
    BEGINNER_TEXT = "beginner_text"


@dataclass(frozen=True)
class ScoreBand:
    dimension: str
    minimum: float
    maximum: float


@dataclass(frozen=True)
class BenchmarkConstraints:
    required_error_categories: frozenset[str] = frozenset()
    protected_correct_fragments: tuple[str, ...] = ()
    score_bands: tuple[ScoreBand, ...] = ()
    expected_demonstrated_levels: tuple[str, ...] = ()
    max_error_count: int | None = None


@dataclass(frozen=True)
class WritingBenchmarkCase:
    case_id: str
    language: str
    kind: BenchmarkKind
    target_level: str
    task_prompt: str
    learner_text: str
    constraints: BenchmarkConstraints
    rationale: str
    comparison_id: str | None = None
    comparison_role: str | None = None
    comparison_dimensions: tuple[str, ...] = ()
    target_pair_id: str | None = None


@dataclass(frozen=True)
class BenchmarkFinding:
    check: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"check": self.check, "message": self.message}


@dataclass(frozen=True)
class BenchmarkEvaluation:
    case_id: str
    passed: bool
    failed_checks: tuple[BenchmarkFinding, ...]
    warnings: tuple[BenchmarkFinding, ...]
    metrics: tuple[tuple[str, int | float | str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "passed": self.passed,
            "failed_checks": [item.to_dict() for item in self.failed_checks],
            "warnings": [item.to_dict() for item in self.warnings],
            "metrics": dict(self.metrics),
        }


@dataclass(frozen=True)
class BenchmarkComparison:
    comparison_id: str
    passed: bool
    failed_checks: tuple[BenchmarkFinding, ...]
    metrics: tuple[tuple[str, int | float | str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "comparison_id": self.comparison_id,
            "passed": self.passed,
            "failed_checks": [item.to_dict() for item in self.failed_checks],
            "metrics": dict(self.metrics),
        }


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _literal_fragment(source: str, fragment: Any) -> bool:
    return isinstance(fragment, str) and bool(fragment.strip()) and fragment in source


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def _is_material_correction(fragment: Any, suggestion: Any) -> bool:
    if not isinstance(fragment, str) or not isinstance(suggestion, str) or not suggestion.strip():
        return False
    normalized_fragment = _normalized_text(fragment)
    normalized_suggestion = _normalized_text(suggestion)
    if normalized_suggestion == normalized_fragment:
        return False
    without_label = re.sub(
        r"^(?:revised|corrected|correction)\s*:\s*",
        "",
        normalized_suggestion,
        flags=re.IGNORECASE,
    )
    return without_label != normalized_fragment


def _result_scores(result: Mapping[str, Any]) -> Mapping[str, Any]:
    # Normalized Writing results expose rubric dimensions at the top level.
    return result


def evaluate_benchmark_result(
    case: WritingBenchmarkCase,
    normalized_result: Mapping[str, Any],
    *,
    allowed_error_categories: Sequence[str],
) -> BenchmarkEvaluation:
    """Evaluate one normalized result against a benchmark case."""

    failures: list[BenchmarkFinding] = []
    warnings: list[BenchmarkFinding] = []
    scores = _result_scores(normalized_result)

    for dimension in RUBRIC_DIMENSIONS:
        score = scores.get(dimension)
        if not _is_number(score) or not 0 <= float(score) <= 100:
            failures.append(
                BenchmarkFinding(
                    "score_bounds",
                    f"{dimension} must be a finite score between 0 and 100",
                )
            )

    for band in case.constraints.score_bands:
        score = scores.get(band.dimension)
        if _is_number(score) and not band.minimum <= float(score) <= band.maximum:
            failures.append(
                BenchmarkFinding(
                    "score_band",
                    f"{band.dimension} must be between {band.minimum:g} and {band.maximum:g}",
                )
            )

    strength_evidence = normalized_result.get("strength_evidence")
    if not isinstance(strength_evidence, list):
        failures.append(BenchmarkFinding("evidence_precision", "strength_evidence must be a list"))
        strength_evidence = []
    for item in strength_evidence:
        if not isinstance(item, Mapping):
            failures.append(BenchmarkFinding("evidence_precision", "strength evidence must be an object"))
            continue
        fragment = item.get("fragment")
        if not _literal_fragment(case.learner_text, fragment):
            failures.append(
                BenchmarkFinding("evidence_precision", "strength evidence is not literal learner text")
            )
        if item.get("category") not in RUBRIC_DIMENSIONS:
            failures.append(
                BenchmarkFinding("category_validity", "strength evidence uses an unknown rubric category")
            )
        if not isinstance(item.get("explanation_vi"), str) or not item["explanation_vi"].strip():
            failures.append(
                BenchmarkFinding(
                    "actionable_feedback",
                    "strength evidence must explain what the learner did well",
                )
            )
        confidence = item.get("confidence")
        if not _is_number(confidence) or not CONFIDENCE_THRESHOLD <= float(confidence) <= 1:
            failures.append(
                BenchmarkFinding(
                    "confidence_threshold",
                    f"strength evidence confidence must be between {CONFIDENCE_THRESHOLD:g} and 1",
                )
            )

    errors = normalized_result.get("errors")
    if not isinstance(errors, list):
        failures.append(BenchmarkFinding("evidence_precision", "errors must be a list"))
        errors = []

    allowed_categories = frozenset(allowed_error_categories)
    observed_categories: set[str] = set()
    false_positive_count = 0
    for item in errors:
        if not isinstance(item, Mapping):
            failures.append(BenchmarkFinding("evidence_precision", "error evidence must be an object"))
            continue
        fragment = item.get("fragment")
        if not _literal_fragment(case.learner_text, fragment):
            failures.append(
                BenchmarkFinding("evidence_precision", "error evidence is not literal learner text")
            )
        category = item.get("category")
        if category not in allowed_categories:
            failures.append(BenchmarkFinding("category_validity", "error uses an undeclared category"))
        elif isinstance(category, str):
            observed_categories.add(category)

        confidence = item.get("confidence")
        if not _is_number(confidence) or not CONFIDENCE_THRESHOLD <= float(confidence) <= 1:
            failures.append(
                BenchmarkFinding(
                    "confidence_threshold",
                    f"error confidence must be between {CONFIDENCE_THRESHOLD:g} and 1",
                )
            )

        suggestion = item.get("suggestion")
        if not _is_material_correction(fragment, suggestion):
            failures.append(
                BenchmarkFinding(
                    "correction_usefulness",
                    "correction must be non-empty and materially differ from evidence",
                )
            )
        if not isinstance(item.get("explanation_vi"), str) or not item["explanation_vi"].strip():
            failures.append(
                BenchmarkFinding(
                    "actionable_feedback",
                    "error evidence must explain the problem",
                )
            )
        if not isinstance(item.get("mini_rule_vi"), str) or not item["mini_rule_vi"].strip():
            failures.append(
                BenchmarkFinding(
                    "actionable_feedback",
                    "error evidence must include a reusable rule",
                )
            )

        if isinstance(fragment, str) and any(
            fragment in protected or protected in fragment
            for protected in case.constraints.protected_correct_fragments
        ):
            false_positive_count += 1
            failures.append(
                BenchmarkFinding("false_positive", "protected correct text was marked as an error")
            )

    required_categories = case.constraints.required_error_categories
    if required_categories and not observed_categories.intersection(required_categories):
        failures.append(
            BenchmarkFinding(
                "required_error_recall",
                "no required error category was identified with literal evidence",
            )
        )

    if case.constraints.max_error_count is not None and len(errors) > case.constraints.max_error_count:
        failures.append(
            BenchmarkFinding(
                "false_positive",
                f"error count exceeds the case limit of {case.constraints.max_error_count}",
            )
        )

    demonstrated_level = normalized_result.get("cefr_estimate")
    expected_levels = case.constraints.expected_demonstrated_levels
    if expected_levels and demonstrated_level not in expected_levels:
        failures.append(
            BenchmarkFinding(
                "target_level_stability",
                "demonstrated level falls outside the case's stable expected band",
            )
        )

    metrics: tuple[tuple[str, int | float | str], ...] = (
        ("strength_evidence_count", len(strength_evidence)),
        ("error_count", len(errors)),
        ("false_positive_count", false_positive_count),
    )
    return BenchmarkEvaluation(
        case_id=case.case_id,
        passed=not failures,
        failed_checks=tuple(failures),
        warnings=tuple(warnings),
        metrics=metrics,
    )


def compare_pairwise_results(
    stronger_case: WritingBenchmarkCase,
    stronger_result: Mapping[str, Any],
    weaker_case: WritingBenchmarkCase,
    weaker_result: Mapping[str, Any],
    *,
    tolerance: float = PAIRWISE_SCORE_TOLERANCE,
) -> BenchmarkComparison:
    """Require a minimally edited broken text not to outscore its clean pair."""

    if (
        not stronger_case.comparison_id
        or stronger_case.comparison_id != weaker_case.comparison_id
        or stronger_case.comparison_role != "stronger"
        or weaker_case.comparison_role != "weaker"
    ):
        raise ValueError("cases do not form a stronger/weaker comparison pair")

    dimensions = stronger_case.comparison_dimensions
    if not dimensions or dimensions != weaker_case.comparison_dimensions:
        raise ValueError("comparison dimensions must be identical and non-empty")

    stronger_scores = _result_scores(stronger_result)
    weaker_scores = _result_scores(weaker_result)
    failures: list[BenchmarkFinding] = []
    metrics: list[tuple[str, int | float | str]] = []
    for dimension in dimensions:
        stronger_score = stronger_scores.get(dimension)
        weaker_score = weaker_scores.get(dimension)
        if not _is_number(stronger_score) or not _is_number(weaker_score):
            failures.append(BenchmarkFinding("pairwise_scoring", f"{dimension} scores must be numeric"))
            continue
        delta = float(stronger_score) - float(weaker_score)
        metrics.append((f"{dimension}_stronger_minus_weaker", delta))
        if float(weaker_score) > float(stronger_score) + tolerance:
            failures.append(
                BenchmarkFinding(
                    "pairwise_scoring",
                    f"weaker text exceeds stronger text in {dimension} beyond tolerance {tolerance:g}",
                )
            )

    return BenchmarkComparison(
        comparison_id=stronger_case.comparison_id,
        passed=not failures,
        failed_checks=tuple(failures),
        metrics=tuple(metrics),
    )


def compare_target_level_results(
    first_case: WritingBenchmarkCase,
    first_result: Mapping[str, Any],
    second_case: WritingBenchmarkCase,
    second_result: Mapping[str, Any],
    *,
    declared_levels: Sequence[str],
    tolerance: float = TARGET_LEVEL_SCORE_TOLERANCE,
    maximum_level_drift: int = 1,
) -> BenchmarkComparison:
    """Check that a target-level change does not rewrite demonstrated ability.

    ``declared_levels`` supplies the language profile's proficiency ordering so
    this shared comparison does not embed CEFR, HSK, or other language rules.
    """

    if (
        not first_case.target_pair_id
        or first_case.target_pair_id != second_case.target_pair_id
        or first_case.learner_text != second_case.learner_text
        or first_case.task_prompt != second_case.task_prompt
        or first_case.target_level == second_case.target_level
    ):
        raise ValueError("cases do not form a valid target-level comparison pair")

    level_order = tuple(declared_levels)
    if not level_order or len(set(level_order)) != len(level_order):
        raise ValueError("declared_levels must be a non-empty unique ordered sequence")
    if not isinstance(maximum_level_drift, int) or maximum_level_drift < 0:
        raise ValueError("maximum_level_drift must be a non-negative integer")

    first_band = first_case.constraints.expected_demonstrated_levels
    second_band = second_case.constraints.expected_demonstrated_levels
    if not first_band or first_band != second_band:
        raise ValueError("target-level pair must share one non-empty plausible demonstrated band")
    if any(level not in level_order for level in first_band):
        raise ValueError("plausible demonstrated levels must belong to declared_levels")

    first_scores = _result_scores(first_result)
    second_scores = _result_scores(second_result)
    failures: list[BenchmarkFinding] = []
    metrics: list[tuple[str, int | float | str]] = []
    for dimension in RUBRIC_DIMENSIONS:
        first_score = first_scores.get(dimension)
        second_score = second_scores.get(dimension)
        if not _is_number(first_score) or not _is_number(second_score):
            failures.append(BenchmarkFinding("target_level_stability", f"{dimension} scores must be numeric"))
            continue
        drift = abs(float(first_score) - float(second_score))
        metrics.append((f"{dimension}_absolute_drift", drift))
        if drift > tolerance:
            failures.append(
                BenchmarkFinding(
                    "target_level_stability",
                    f"{dimension} changed by {drift:g}, exceeding tolerance {tolerance:g}",
                )
            )

    first_level = first_result.get("cefr_estimate")
    second_level = second_result.get("cefr_estimate")
    if first_level == first_case.target_level and second_level == second_case.target_level:
        failures.append(
            BenchmarkFinding(
                "target_level_echo",
                "demonstrated level echoes each requested target for identical learner text",
            )
        )

    if first_level in level_order and second_level in level_order:
        demonstrated_level_drift = abs(level_order.index(first_level) - level_order.index(second_level))
        metrics.append(("demonstrated_level_drift", demonstrated_level_drift))
        if demonstrated_level_drift > maximum_level_drift:
            failures.append(
                BenchmarkFinding(
                    "demonstrated_level_drift",
                    "demonstrated levels changed by "
                    f"{demonstrated_level_drift} bands, exceeding tolerance {maximum_level_drift}",
                )
            )
    else:
        failures.append(
            BenchmarkFinding(
                "target_level_stability",
                "demonstrated levels must belong to the supplied language-level sequence",
            )
        )

    for case, level in ((first_case, first_level), (second_case, second_level)):
        expected = case.constraints.expected_demonstrated_levels
        if expected and level not in expected:
            failures.append(
                BenchmarkFinding(
                    "target_level_stability",
                    f"{case.case_id} demonstrated level falls outside its stable expected band",
                )
            )

    return BenchmarkComparison(
        comparison_id=first_case.target_pair_id,
        passed=not failures,
        failed_checks=tuple(failures),
        metrics=tuple(metrics),
    )


_SAFE_EVALUATOR_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_REPORT_RESULT_FIELDS = (
    "summary_vi",
    "strengths_vi",
    "priorities_vi",
    "strength_evidence",
    "errors",
    "cefr_estimate",
) + RUBRIC_DIMENSIONS


def validate_evaluator_label(evaluator_label: str) -> str:
    """Return a safe operator-facing evaluator identifier or fail closed."""

    if not isinstance(evaluator_label, str) or not _SAFE_EVALUATOR_LABEL.fullmatch(evaluator_label):
        raise ValueError("evaluator_label must be a harmless identifier")
    return evaluator_label


def build_benchmark_report(
    *,
    timestamp: str,
    evaluator_label: str,
    case: WritingBenchmarkCase,
    normalized_result: Mapping[str, Any],
    evaluation: BenchmarkEvaluation,
) -> dict[str, Any]:
    """Build a JSON-safe report while excluding arbitrary provider/secret fields."""

    if not isinstance(timestamp, str) or not timestamp.strip():
        raise ValueError("timestamp is required")
    validate_evaluator_label(evaluator_label)
    if evaluation.case_id != case.case_id:
        raise ValueError("evaluation does not belong to the benchmark case")

    safe_result = {
        key: deepcopy(normalized_result[key])
        for key in _REPORT_RESULT_FIELDS
        if key in normalized_result
    }
    return {
        "benchmark_version": WRITING_BENCHMARK_VERSION,
        "timestamp": timestamp,
        "evaluator_label": evaluator_label,
        "case": {
            "case_id": case.case_id,
            "language": case.language,
            "kind": case.kind.value,
            "target_level": case.target_level,
        },
        "normalized_result": safe_result,
        "findings": evaluation.to_dict(),
    }
