"""Pure normalization contract for learner-facing Writing evaluations."""

from __future__ import annotations

import math
import re
import hashlib
from collections.abc import Callable, Mapping, Sequence
from typing import Any


_CJK_RE = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF]")
CONFIDENCE_THRESHOLD = 0.75
MAX_LEARNER_LIST_ITEMS = 6
MAX_STRENGTH_EVIDENCE_ITEMS = 6
MAX_ERROR_ITEMS = 20
EVALUATION_SCHEMA_VERSION = "writing-evaluation-v2"


def contains_cjk(text: str) -> bool:
    """Return whether learner-facing text contains CJK writing systems."""
    return bool(_CJK_RE.search(text or ""))


def calculate_weighted_overall(
    result: Mapping[str, Any],
    rubric_weights: Mapping[str, float],
) -> float:
    """Calculate the bounded, one-decimal overall score for supplied rubric data."""
    applicable = [(key, weight) for key, weight in rubric_weights.items() if key in result]
    total_weight = sum(weight for _, weight in applicable)
    if total_weight <= 0:
        return 0.0
    score = sum(float(result[key]) * weight for key, weight in applicable) / total_weight
    return round(max(0.0, min(100.0, score)), 1)


def normalize_writing_evaluation(
    raw: Mapping[str, Any],
    *,
    rubric_weights: Mapping[str, float],
    allowed_levels: Sequence[str],
    score_to_level: Callable[[float], str],
    error_categories: Sequence[str],
    allow_cjk: bool,
    learner_text: str,
    applicable_dimensions: Sequence[str] | None = None,
    allow_explanation_cjk: bool | None = None,
) -> dict[str, Any]:
    """Normalize untrusted evaluator output using supplied language policy.

    This function deliberately owns no language selection, request state, AI
    routing, persistence, or web-framework behavior.  The caller supplies the
    current rubric, proficiency policy, and learner text explicitly.
    """
    explanation_allow_cjk = allow_cjk if allow_explanation_cjk is None else allow_explanation_cjk
    text_hash = hashlib.sha256((learner_text or "").encode("utf-8")).hexdigest()
    dimension_keys = tuple(
        key for key in rubric_weights
        if applicable_dimensions is None or key in set(applicable_dimensions)
    )
    result: dict[str, Any] = {"schema_version": EVALUATION_SCHEMA_VERSION, "text_hash": text_hash}
    for key in dimension_keys:
        result[key] = _normalized_score(raw.get(key, 0))

    overall = calculate_weighted_overall(result, rubric_weights)
    allowed_level_set = set(allowed_levels)
    default_level = allowed_levels[0] if allowed_levels else ""
    band_status = str(raw.get("band_status", "estimated"))
    if band_status not in {"estimated", "insufficient_evidence"}:
        band_status = "estimated"
    result["band_status"] = band_status
    estimate = str(raw.get("cefr_estimate", default_level))
    if band_status == "insufficient_evidence":
        result["cefr_estimate"] = ""
    else:
        result["cefr_estimate"] = estimate if estimate in allowed_level_set else score_to_level(overall)
    if "band_confidence" in raw:
        result["band_confidence"] = round(_normalized_confidence(raw["band_confidence"]), 2)

    summary = _bounded_text(raw.get("summary_vi", ""), 4000)
    result["summary_vi"] = summary if explanation_allow_cjk or not contains_cjk(summary) else ""
    result["strengths_vi"] = _clean_learner_list(raw.get("strengths_vi", []), allow_cjk=explanation_allow_cjk)
    result["priorities_vi"] = _clean_learner_list(raw.get("priorities_vi", []), allow_cjk=explanation_allow_cjk)
    result["strength_evidence"] = _normalize_strength_evidence(
        raw.get("strength_evidence", []),
        rubric_categories=set(dimension_keys),
        allow_cjk=allow_cjk,
        allow_explanation_cjk=explanation_allow_cjk,
        learner_text=learner_text,
    )
    result["errors"] = _normalize_errors(
        raw.get("errors", []),
        error_categories=set(error_categories),
        allow_cjk=allow_cjk,
        allow_explanation_cjk=explanation_allow_cjk,
        learner_text=learner_text,
    )
    result["summary"] = {
        "headline": result["strengths_vi"][0] if result["strengths_vi"] else "",
        "interpretation": result["summary_vi"],
    }
    result["dimensions"] = {key: result[key] for key in dimension_keys}
    result["issues"] = [_issue_envelope(item, index) for index, item in enumerate(result["errors"])]
    result["strengths"] = [
        {
            "id": f"strength-{index + 1}",
            "category": item["category"],
            "span": item["span"],
            "quote": item["fragment"],
            "why": item["explanation_vi"],
        }
        for index, item in enumerate(result["strength_evidence"])
    ]
    result["next_actions"] = result["priorities_vi"]
    return result


def _issue_envelope(item: Mapping[str, Any], index: int) -> dict[str, Any]:
    return {
        "id": item["id"],
        "category": item["category"],
        "priority": "high" if index == 0 else "medium",
        "span": item["span"],
        "quote": item["fragment"],
        "why": item["explanation_vi"],
        "how": item["mini_rule_vi"],
        "suggestion": item["suggestion"],
        "examples": [],
    }


def _evidence_span(learner_text: str, fragment: str) -> dict[str, int]:
    start = learner_text.find(fragment)
    if start < 0:
        return {"start": 0, "end": 0}
    return {"start": start, "end": start + len(fragment)}


def _evidence_id(category: str, fragment: str, span: Mapping[str, int]) -> str:
    raw = f"{category}|{span['start']}|{span['end']}|{fragment}"
    return "issue-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _normalized_score(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(score):
        return 0.0
    return round(max(0.0, min(100.0, score)), 1)


def _normalized_confidence(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.0
    if not math.isfinite(confidence):
        confidence = 0.0
    return max(0.0, min(1.0, confidence))


def _bounded_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return value[:limit].strip()


def _clean_learner_list(
    items: Any,
    *,
    limit: int = MAX_LEARNER_LIST_ITEMS,
    allow_cjk: bool,
) -> list[str]:
    if not isinstance(items, list):
        return []
    output: list[str] = []
    for item in items:
        value = _bounded_text(item, 1000)
        if value and (allow_cjk or not contains_cjk(value)):
            output.append(value)
        if len(output) >= limit:
            break
    return output


def _normalize_strength_evidence(
    items: Any,
    *,
    rubric_categories: set[str],
    allow_cjk: bool,
    learner_text: str,
    allow_explanation_cjk: bool | None = None,
) -> list[dict[str, Any]]:
    explanation_allow_cjk = allow_cjk if allow_explanation_cjk is None else allow_explanation_cjk
    if not isinstance(items, list):
        return []
    output: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in items[:MAX_STRENGTH_EVIDENCE_ITEMS]:
        if not isinstance(item, Mapping):
            continue
        category = _bounded_text(item.get("category", ""), 1000)
        fragment = _bounded_text(item.get("fragment", ""), 500)
        explanation = _bounded_text(item.get("explanation_vi", ""), 1500)
        confidence = _normalized_confidence(item.get("confidence", 1.0))
        if category not in rubric_categories or confidence < CONFIDENCE_THRESHOLD:
            continue
        if not fragment or fragment not in learner_text or not explanation:
            continue
        if not explanation_allow_cjk and contains_cjk(explanation):
            continue
        identity = (category, fragment)
        if identity in seen:
            continue
        seen.add(identity)
        span = _evidence_span(learner_text, fragment)
        output.append(
            {
                "id": f"strength-{len(output) + 1}",
                "category": category,
                "fragment": fragment,
                "quote": fragment,
                "span": span,
                "explanation_vi": explanation,
                "confidence": round(confidence, 2),
            }
        )
    return output


def _normalize_errors(
    items: Any,
    *,
    error_categories: set[str],
    allow_cjk: bool,
    learner_text: str,
    allow_explanation_cjk: bool | None = None,
) -> list[dict[str, Any]]:
    explanation_allow_cjk = allow_cjk if allow_explanation_cjk is None else allow_explanation_cjk
    if not isinstance(items, list):
        return []
    output: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in items[:MAX_ERROR_ITEMS]:
        if not isinstance(item, Mapping):
            continue
        category = item.get("category")
        if not isinstance(category, str) or category not in error_categories:
            continue
        fragment = _bounded_text(item.get("fragment", ""), 500)
        explanation = _bounded_text(item.get("explanation_vi", ""), 2000)
        suggestion = _bounded_text(item.get("suggestion", ""), 1000)
        rule = _bounded_text(item.get("mini_rule_vi", ""), 1500)
        confidence = _normalized_confidence(item.get("confidence", 1.0))
        # A finding that cannot be pointed at is still a finding.
        #
        # This used to drop any error whose fragment was not verbatim in the
        # learner text, which is right for *highlighting* - pointing at the
        # wrong words is worse than pointing at nothing - and wrong for
        # keeping it: an evaluator that normalised an apostrophe or trimmed a
        # word lost the whole correction, and the learner never heard that the
        # verb form was wrong at all.
        #
        # So the two questions are separated. Is it trustworthy: confidence,
        # explanation, rule, a suggestion that differs. Can it be anchored:
        # whether the fragment occurs literally. An unanchored finding keeps
        # everything except the span, and the surface shows it as guidance
        # without offering to find it in the text.
        anchored = bool(fragment) and fragment in learner_text
        if (
            confidence < CONFIDENCE_THRESHOLD
            or not fragment
            or not explanation
            or not rule
        ):
            continue
        if not explanation_allow_cjk and (contains_cjk(explanation) or contains_cjk(rule)):
            continue
        if not allow_cjk and contains_cjk(suggestion):
            continue
        if not suggestion or _normalize_text(suggestion) == _normalize_text(fragment):
            continue
        identity = (category, fragment)
        if identity in seen:
            continue
        seen.add(identity)
        span = _evidence_span(learner_text, fragment)
        output.append(
            {
                "id": _evidence_id(category, fragment, span),
                "category": category,
                "fragment": fragment,
                "quote": fragment,
                "span": span,
                "anchored": anchored,
                "explanation_vi": explanation,
                "suggestion": suggestion,
                "mini_rule_vi": rule,
                "confidence": round(confidence, 2),
            }
        )
    # Review presents issues as confidence-prioritized feedback. Python's
    # stable sort keeps provider order for equal-confidence findings while
    # ensuring the learner sees the strongest evidence first.
    output.sort(key=lambda item: item["confidence"], reverse=True)
    return output


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()
