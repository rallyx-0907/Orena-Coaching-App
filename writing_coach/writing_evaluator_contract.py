"""Shared request, schema, and policy contract for Writing evaluation."""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Mapping, Sequence
from numbers import Real
from typing import Any

from writing_coach.writing_evaluation import (
    CONFIDENCE_THRESHOLD,
    MAX_ERROR_ITEMS,
    MAX_LEARNER_LIST_ITEMS,
    MAX_STRENGTH_EVIDENCE_ITEMS,
)


class WritingEvaluatorContractInvalid(ValueError):
    """Raised when a language's Writing evaluator policy is inconsistent."""


SHARED_RESULT_FIELDS = (
    "cefr_estimate",
    "summary_vi",
    "strengths_vi",
    "strength_evidence",
    "priorities_vi",
    "errors",
)
STRENGTH_EVIDENCE_FIELDS = ("category", "fragment", "explanation_vi", "confidence")
ERROR_FIELDS = (
    "category",
    "fragment",
    "explanation_vi",
    "suggestion",
    "mini_rule_vi",
    "confidence",
)
_STABLE_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*$")
_REPRESENTATIVE_SCORES = (
    0.0, 24.9, 25.0, 29.9, 30.0, 39.9, 40.0, 44.9, 45.0, 54.9, 55.0,
    59.9, 60.0, 67.9, 68.0, 74.9, 75.0, 79.9, 80.0, 89.9, 90.0, 100.0,
)


def validate_writing_evaluator_policy(
    *,
    rubric_weights: Mapping[str, Any],
    allowed_levels: Sequence[str],
    score_to_level: Callable[[float], str],
    error_categories: Sequence[str],
) -> None:
    """Fail closed when rubric, proficiency, or category policy can drift."""
    rubric_keys = tuple(rubric_weights)
    if not rubric_keys:
        raise WritingEvaluatorContractInvalid("Writing evaluator rubric must not be empty.")
    if len(rubric_keys) != len(set(rubric_keys)):
        raise WritingEvaluatorContractInvalid("Writing evaluator rubric keys must be unique.")

    total_weight = 0.0
    for key in rubric_keys:
        if not isinstance(key, str) or not _STABLE_IDENTIFIER.fullmatch(key):
            raise WritingEvaluatorContractInvalid(
                "Writing evaluator rubric keys must be stable identifiers."
            )
        weight = rubric_weights[key]
        if isinstance(weight, bool) or not isinstance(weight, Real):
            raise WritingEvaluatorContractInvalid(
                f"Writing evaluator rubric weight for '{key}' must be numeric."
            )
        numeric_weight = float(weight)
        if not math.isfinite(numeric_weight) or numeric_weight <= 0:
            raise WritingEvaluatorContractInvalid(
                f"Writing evaluator rubric weight for '{key}' must be positive."
            )
        total_weight += numeric_weight

    if not math.isclose(total_weight, 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise WritingEvaluatorContractInvalid("Writing evaluator rubric weights must total 1.0.")

    levels = tuple(allowed_levels)
    if not levels or len(levels) != len(set(levels)):
        raise WritingEvaluatorContractInvalid(
            "Writing evaluator proficiency levels must be non-empty and unique."
        )
    if any(not isinstance(level, str) or not level.strip() or level != level.strip() for level in levels):
        raise WritingEvaluatorContractInvalid(
            "Writing evaluator proficiency levels must be stable non-empty strings."
        )

    categories = tuple(error_categories)
    if not categories or len(categories) != len(set(categories)):
        raise WritingEvaluatorContractInvalid(
            "Writing evaluator error categories must be non-empty and unique."
        )
    if any(not isinstance(category, str) or not _STABLE_IDENTIFIER.fullmatch(category) for category in categories):
        raise WritingEvaluatorContractInvalid(
            "Writing evaluator error categories must be stable identifiers."
        )
    if "other" not in categories:
        raise WritingEvaluatorContractInvalid(
            "Writing evaluator error categories must include 'other'."
        )

    for score in _REPRESENTATIVE_SCORES:
        level = score_to_level(score)
        if level not in levels:
            raise WritingEvaluatorContractInvalid(
                f"Writing evaluator score-to-level policy returned an undeclared level at score {score}."
            )


def build_writing_evaluator_request(
    *,
    language_name: str,
    target_level: str,
    task_prompt: str,
    learner_text: str,
    free_writing_context: str,
) -> str:
    """Build the language-neutral evaluator request from explicit learner context."""
    task_context = task_prompt or free_writing_context
    return (
        f"TARGET LANGUAGE: {language_name}\n"
        f"TARGET LEVEL (LEARNING CONTEXT ONLY): {target_level}\n"
        "TARGET LEVEL POLICY:\n"
        "The target level guides pedagogical relevance and expected sophistication. "
        "Estimate the learner's actual demonstrated performance. Do not force the proficiency "
        "estimate upward, inflate scores, or deflate scores merely to match the target level.\n\n"
        "<WRITING_TASK>\n"
        f"{task_context}\n"
        "</WRITING_TASK>\n\n"
        "<LEARNER_TEXT>\n"
        f"{learner_text}\n"
        "</LEARNER_TEXT>\n\n"
        "EVALUATION AND EVIDENCE CONTRACT:\n"
        "- Evaluate the ORIGINAL learner text, not a rewritten version.\n"
        "- Never invent learner evidence. Every returned `fragment` must occur literally in "
        "LEARNER_TEXT.\n"
        "- Every strength_evidence item must describe a genuine strength visible in its exact fragment.\n"
        "- Identify 1-3 exact learner fragments that demonstrate genuine strengths.\n"
        "- Every errors item must describe a genuine problem visible in its exact fragment.\n"
        "- Every error suggestion must meaningfully differ from the erroneous fragment.\n"
        "- If uncertain whether something is wrong, omit it. Fewer high-confidence findings are "
        "preferable to many doubtful findings.\n"
        f"- Return evidence only when confidence >= {CONFIDENCE_THRESHOLD:.2f}.\n"
        "- Focus on recurring or reusable learning points, not only isolated typos.\n"
        "Return one complete JSON object matching the supplied structured schema."
    )


def build_writing_evaluator_schema(
    *,
    rubric_weights: Mapping[str, Any],
    allowed_levels: Sequence[str],
    score_to_level: Callable[[float], str],
    error_categories: Sequence[str],
) -> dict[str, Any]:
    """Build the one authoritative structured response schema for a language policy."""
    validate_writing_evaluator_policy(
        rubric_weights=rubric_weights,
        allowed_levels=allowed_levels,
        score_to_level=score_to_level,
        error_categories=error_categories,
    )
    rubric_keys = tuple(rubric_weights)
    strength_schema = {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": list(rubric_keys)},
            "fragment": {"type": "string", "minLength": 1},
            "explanation_vi": {"type": "string", "minLength": 1},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": list(STRENGTH_EVIDENCE_FIELDS),
    }
    error_schema = {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": list(error_categories)},
            "fragment": {"type": "string", "minLength": 1},
            "explanation_vi": {"type": "string", "minLength": 1},
            "suggestion": {"type": "string", "minLength": 1},
            "mini_rule_vi": {"type": "string", "minLength": 1},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": list(ERROR_FIELDS),
    }
    properties: dict[str, Any] = {
        key: {"type": "number", "minimum": 0, "maximum": 100}
        for key in rubric_keys
    }
    properties.update(
        {
            "cefr_estimate": {"type": "string", "enum": list(allowed_levels)},
            "summary_vi": {"type": "string"},
            "strengths_vi": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": MAX_LEARNER_LIST_ITEMS,
            },
            "strength_evidence": {
                "type": "array",
                "items": strength_schema,
                "maxItems": MAX_STRENGTH_EVIDENCE_ITEMS,
            },
            "priorities_vi": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": MAX_LEARNER_LIST_ITEMS,
            },
            "errors": {"type": "array", "items": error_schema, "maxItems": MAX_ERROR_ITEMS},
        }
    )
    return {
        "type": "object",
        "properties": properties,
        "required": [*rubric_keys, *SHARED_RESULT_FIELDS],
    }
