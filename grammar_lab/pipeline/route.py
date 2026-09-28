"""``route`` step (SPEC §5.4): confidence score, auto_ok/flagged routing, 10% sampling.

The formula and threshold are SPEC's *starting* numbers, calibrated later
against a human-reviewed gold set (SPEC §5.4 point 3-4) -- that calibration
is a project-owner-and-AI review pass, not something this module decides on
its own. What this module owns is applying the stated formula faithfully and
routing on it, so there is something concrete to calibrate against.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from grammar_lab.pipeline.verify import VerifyReport

FLAG_PREFIX = "route:"

DEFAULT_THRESHOLD_BY_LANG = {"en": 0.8}  # SPEC §5.4 point 3: 0.8 for English before a gold set exists.
SAMPLE_RATE = 0.10

# SPEC §5.4: "Bắt đầu từ 1,0; trừ theo từng kiểm tra thất bại": one deduction per
# *category* of check that failed at least once, not per failing instance --
# SPEC lists exactly five weighted categories, not a per-occurrence penalty.
PENALTY_PITFALL_MATCH = 0.4
PENALTY_CLEAN_EXAMPLE = 0.3
PENALTY_BLIND_SOLVE = 0.3
# Vocabulary-level (-0.1) and back-translation (-0.2) checks are deferred to
# phase 3 (verify.py docstring); their penalties do not apply here.

_PITFALL_CODES = {"pitfall_not_caught", "pitfall_right_flagged"}
_EXAMPLE_CODES = {"example_not_clean"}
_BLIND_SOLVE_CODES = {"blind_solve_wrong", "blind_solve_ambiguous"}
_UNVERIFIABLE_CODES = {"evaluator_error", "blind_solve_error"}


@dataclass
class RouteOutcome:
    point_id: str
    score: float
    status: str  # "flagged" | "auto_ok"
    flags: list[str] = field(default_factory=list)
    sampled: bool = False


def score_point(verify_codes: set[str]) -> float:
    score = 1.0
    if verify_codes & _PITFALL_CODES:
        score -= PENALTY_PITFALL_MATCH
    if verify_codes & _EXAMPLE_CODES:
        score -= PENALTY_CLEAN_EXAMPLE
    if verify_codes & _BLIND_SOLVE_CODES:
        score -= PENALTY_BLIND_SOLVE
    return max(0.0, round(score, 4))


def _sampled_for_review(point_id: str) -> bool:
    """Deterministic ~10% sample: a hash of the id, not real randomness, so
    a re-run of the same content picks the same sample (SPEC's idempotency
    principle, §5)."""
    digest = hashlib.sha256(point_id.encode("utf-8")).hexdigest()
    return (int(digest, 16) % 100) < round(SAMPLE_RATE * 100)


def route_point(
    point_id: str,
    *,
    validate_issue_codes: set[str],
    verify_report: VerifyReport | None,
    threshold: float,
    gold_set_passed: bool,
    target_lang: str | None = None,
    has_story: bool = False,
) -> RouteOutcome:
    """SPEC §5.4 routing rules, in order:

    1. Any validate issue, or any verify flag (including one meaning the
       point could not be checked at all) -> flagged.
    2. A Chinese point with a story block -> always flagged, regardless of
       score or gold-set status (STORY_SPEC.md §6: "Tiếng Trung: luôn vào
       hàng đợi duyệt" -- stronger than rule 3 below, which a passed gold
       set can clear).
    3. The language/L1 pair has not been through a gold set -> flagged.
    4. Otherwise: score >= threshold -> auto_ok (a random 10% still sampled
       into the review queue); below threshold -> flagged.
    """
    verify_codes = verify_report.codes() if verify_report is not None else {"not_verified"}
    all_flags = sorted(f"validate:{code}" for code in validate_issue_codes) + \
        sorted(f"verify:{code}" for code in verify_codes)

    if validate_issue_codes or verify_codes:
        return RouteOutcome(point_id, score_point(verify_codes), "flagged", all_flags)
    if target_lang == "zh-Hans" and has_story:
        return RouteOutcome(point_id, score_point(verify_codes), "flagged", ["route:zh_story_always_reviewed"])
    if not gold_set_passed:
        return RouteOutcome(point_id, 1.0, "flagged", ["route:gold_set_not_passed"])

    score = score_point(verify_codes)
    if score < threshold:
        return RouteOutcome(point_id, score, "flagged", [f"route:below_threshold:{threshold}"])
    sampled = _sampled_for_review(point_id)
    flags = ["route:sampled_for_review"] if sampled else []
    return RouteOutcome(point_id, score, "auto_ok", flags, sampled=sampled)


def apply_route(point: dict[str, Any], outcome: RouteOutcome) -> dict[str, Any]:
    """A copy of ``point`` with ``status``/``flags`` set from ``outcome``.
    Never touches ``review`` -- routing is machine scoring, not approval."""
    return {**point, "status": outcome.status, "flags": outcome.flags}
