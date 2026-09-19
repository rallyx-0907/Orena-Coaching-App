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
    "band_status",
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
    support_language_name: str | None = None,
    target_level: str | None,
    task_prompt: str,
    learner_text: str,
    free_writing_context: str,
    writing_mode: str = "guided",
    writing_context: Mapping[str, Any] | None = None,
) -> str:
    """Build the language-neutral evaluator request from explicit learner context."""
    if writing_mode not in {"guided", "journal"}:
        raise WritingEvaluatorContractInvalid("Writing mode must be 'guided' or 'journal'.")
    context = writing_context or {}
    parts = [f"TARGET LANGUAGE: {language_name}\n", f"SUBMISSION MODE: {writing_mode}\n"]
    if support_language_name:
        parts.extend(
            [
                f"SUPPORT LANGUAGE: {support_language_name}\n",
                "SUPPORT LANGUAGE POLICY:\n",
                f"Write explanations, summaries, strengths, priorities and reusable rules in {support_language_name}.\n",
                "Keep learner fragments, corrections and target-language examples in the TARGET LANGUAGE.\n",
            ]
        )
    if target_level:
        parts.extend(
            [
                f"TARGET LEVEL (LEARNING CONTEXT ONLY): {target_level}\n",
                "TARGET LEVEL POLICY:\n",
                "The target level guides pedagogical relevance and expected sophistication. ",
                "Estimate the learner's actual demonstrated performance. Do not force the proficiency ",
                "estimate upward, inflate scores, or deflate scores merely to match the target level.\n",
            ]
        )
    parts.extend(
        [
            "DEMONSTRATED BAND POLICY:\n",
            "Infer only the band demonstrated by this sample. Requested length must not affect scores ",
            "or the demonstrated band. If the sample is too short, repetitive, or otherwise too limited ",
            "for a defensible estimate, return band_status='insufficient_evidence' and an empty ",
            "cefr_estimate while retaining only grounded language feedback.\n",
        ]
    )
    if writing_mode == "guided":
        task_context = task_prompt or free_writing_context
        length_id = str(context.get("length_id", "")).strip()
        parts.extend(
            [
                "TASK ACHIEVEMENT: applicable\n",
                *( [f"REQUESTED LENGTH (INVITATION ONLY): {length_id}\n"] if length_id else [] ),
                "<WRITING_TASK>\n",
                f"{task_context}\n",
                "</WRITING_TASK>\n",
            ]
        )
    else:
        journal_context = str(context.get("journal_context") or free_writing_context).strip()
        parts.extend(
            [
                "TASK ACHIEVEMENT: not applicable\n",
                "Do not score prompt adherence or task achievement for reflective/free writing.\n",
                "<JOURNAL_CONTEXT>\n",
                f"{journal_context}\n",
                "</JOURNAL_CONTEXT>\n",
            ]
        )
    parts.extend(
        [
            "\n<LEARNER_TEXT>\n",
            f"{learner_text}\n",
            "</LEARNER_TEXT>\n\n",
            "EVALUATION AND EVIDENCE CONTRACT:\n",
            "- Evaluate the ORIGINAL learner text, not a rewritten version.\n",
            "- Never invent learner evidence. Every returned `fragment` must occur literally in ",
            "LEARNER_TEXT.\n",
            "- Every strength_evidence item must describe a genuine strength visible in its exact fragment.\n",
            "- Identify 1-3 exact learner fragments that demonstrate genuine strengths.\n",
            "- Every errors item must describe a genuine problem visible in its exact fragment.\n",
            "- Every error suggestion must meaningfully differ from the erroneous fragment.\n",
            # Report every genuine error, and rank them - do not report only a few.
            #
            # This used to read "fewer high-confidence findings are preferable
            # to many doubtful findings", which a small model obeys by saying
            # almost nothing: an essay with a wrong verb form, a wrong
            # infinitive, a missing article and a wrong fixed expression came
            # back with one structured error and the rest as general advice.
            # Advice a learner cannot find in their own sentence is not a
            # correction.
            #
            # Precision is still the rule: an uncertain finding is still
            # omitted and nothing may be invented. What changed is that being
            # the fifth true thing is no longer a reason to leave it out. The
            # surface decides what a learner meets first; the evaluator
            # decides what is true.
            "- Report EVERY genuine error you are confident about, not only the most important ",
            "ones. A clear verb-form, agreement, article, tense, word-choice or fixed-expression ",
            "mistake is worth returning even when the text already contains other mistakes.\n",
            "- Rank them: give the highest `confidence` to the errors that matter most for this ",
            "learner's next revision. The surface shows the strongest few first and keeps the ",
            "rest, so leaving a real error out does not simplify anything - it loses it.\n",
            "- If uncertain whether something is wrong, still omit it: never invent a problem, ",
            "and never mark a wording wrong when another reading of it is correct.\n",
            f"- Return evidence only when confidence >= {CONFIDENCE_THRESHOLD:.2f}.\n",
            "- Recurring, reusable learning points matter most, but a one-off mistake the learner ",
            "can see and fix is also worth returning.\n",
            # Which of the two outlets a mistake belongs in.
            #
            # The instruction above was not enough on its own. `errors` and
            # `priorities_vi` were both described, and neither was described
            # in terms of the other, so a model with four mistakes to report
            # returned one error and put the rest in priorities: "revise the
            # fixed expression 'in time'", "watch verb forms". Every one of
            # them was true, and not one could be found in the sentence it
            # came from. Advice is what a learner is left with once the
            # correction has been made; it is not a cheaper way to mention a
            # correction.
            #
            # So the boundary is stated, not implied: pointable goes in
            # `errors`, carried-forward goes in `priorities_vi`, and nothing
            # appears in the second that has not earned its place in the first.
            "- `errors` and `priorities_vi` are not two places to put the same thing. If a ",
            "mistake can be pointed at in LEARNER_TEXT, it belongs in `errors`, with its exact ",
            "fragment - always, and no matter how many errors are already there.\n",
            "- `priorities_vi` is what the learner should carry into their next piece of ",
            "writing, drawn from the errors you returned. Do not name a mistake there that you ",
            "did not return as an error: the learner cannot find it, and it reads as a ",
            "correction they were refused.\n",
            "Return one complete JSON object matching the supplied structured schema.",
        ]
    )
    if support_language_name:
        # The last word on which language to answer in, after the learner's own
        # material rather than only before it.
        #
        # A learner states what they are writing for in their own words, and
        # those words are in whatever language they think in. A Vietnamese task
        # line ahead of an English text pulled the model into answering in
        # Vietnamese even though the policy at the top said Chinese: the task is
        # the most recent natural language the model has read, and it follows
        # it. Saying the output language once more, at the end, removes the
        # ambiguity and changes nothing else about the request.
        #
        # EVALUATOR_CONTRACT_VERSION moves with this. It changes the answer, so
        # it must retire the reviews produced under the version before it.
        parts.extend(
            [
                "\n\nOUTPUT LANGUAGE (OVERRIDES ANY LANGUAGE USED IN THE TASK):\n",
                "Write every explanation, summary, strength, priority and reusable rule in "
                f"{support_language_name}, whatever language the task description or the learner "
                "text happens to be written in.\n",
                "Keep learner fragments, corrections and target-language examples in the TARGET "
                "LANGUAGE.\n",
            ]
        )
    # Keep construction explicit so learner text and authored context are never
    # interpolated into evaluator policy statements.
    return "".join(parts)


def build_writing_evaluator_schema(
    *,
    rubric_weights: Mapping[str, Any],
    allowed_levels: Sequence[str],
    score_to_level: Callable[[float], str],
    error_categories: Sequence[str],
    writing_mode: str = "guided",
) -> dict[str, Any]:
    """Build the one authoritative structured response schema for a language policy."""
    validate_writing_evaluator_policy(
        rubric_weights=rubric_weights,
        allowed_levels=allowed_levels,
        score_to_level=score_to_level,
        error_categories=error_categories,
    )
    if writing_mode not in {"guided", "journal"}:
        raise WritingEvaluatorContractInvalid("Writing mode must be 'guided' or 'journal'.")
    rubric_keys = tuple(
        key for key in rubric_weights if writing_mode == "guided" or key != "task_achievement"
    )
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
            "band_status": {
                "type": "string",
                "enum": ["estimated", "insufficient_evidence"],
            },
            "cefr_estimate": {"type": "string", "enum": ["", *allowed_levels]},
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
