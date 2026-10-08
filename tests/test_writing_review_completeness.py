"""An essay with five mistakes must come back with five findings.

A learner wrote this, deliberately, to see what Orena would say:

    I wanna to telling you about the Da Nang trip last Tuesday.
    I went to the office for meetings with customer
    and I didn't finished the report in times.
    Could you help me tomorrow morning?

It came back with one structured correction - "in times" - and the rest as
general advice: "watch the structure after a modal", "avoid informal
contractions". Advice a learner cannot find in their own sentence is not a
correction, and "I didn't finished" simply went unmentioned.

Two layers were losing findings, and these tests hold both of them open.

The evaluator was told that "fewer high-confidence findings are preferable to
many doubtful findings", which a small model obeys by saying almost nothing.
That is a prompt property, so it is asserted against the prompt itself: a live
model's recall cannot be pinned by a test, but what we ask it for can.

The normalization layer then dropped any finding whose fragment was not
verbatim in the learner's text. That is right for pointing at words and wrong
for keeping the finding, and it is exercised here with a real payload.
"""
from __future__ import annotations

from typing import Any

import pytest

from writing_coach.languages.english.profile import ERROR_CATEGORIES, PROFILE as EN_PROFILE
from writing_coach.writing_evaluation import (
    CONFIDENCE_THRESHOLD,
    normalize_writing_evaluation,
)
from writing_coach.writing_evaluator_contract import build_writing_evaluator_request

RUBRIC_WEIGHTS = {
    "grammar": 0.3,
    "vocabulary": 0.2,
    "coherence": 0.2,
    "task_achievement": 0.2,
    "naturalness": 0.1,
}


def _level(score: float) -> str:
    order = list(EN_PROFILE.levels)
    return order[min(len(order) - 1, int(score // (100 / len(order))))]


def validate_result(raw: dict[str, Any]) -> dict[str, Any]:
    """The route's own normalization, with English policy supplied explicitly."""
    return normalize_writing_evaluation(
        raw,
        rubric_weights=RUBRIC_WEIGHTS,
        allowed_levels=EN_PROFILE.levels,
        score_to_level=_level,
        error_categories=ERROR_CATEGORIES,
        allow_cjk=False,
        learner_text=str(raw.get("__learner_text", "")),
        allow_explanation_cjk=False,
    )

LEARNER_TEXT = (
    "I wanna to telling you about the Da Nang trip last Tuesday. "
    "I went to the office for meetings with customer "
    "and I didn't finished the report in times. "
    "Could you help me tomorrow morning?"
)


def _finding(category: str, fragment: str, suggestion: str, confidence: float = 0.9) -> dict[str, Any]:
    return {
        "category": category,
        "fragment": fragment,
        "suggestion": suggestion,
        "explanation_vi": f"Giải thích cho {fragment}.",
        "mini_rule_vi": f"Quy tắc cho {category}.",
        "confidence": confidence,
    }


def _result(errors: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "grammar": 40.0,
        "vocabulary": 50.0,
        "coherence": 60.0,
        "task_achievement": 58.0,
        "naturalness": 45.0,
        "cefr_estimate": "B1",
        "summary_vi": "Tóm tắt.",
        "strengths_vi": ["Ý chính rõ."],
        "strength_evidence": [],
        "priorities_vi": ["Chú ý thì quá khứ."],
        "errors": errors,
        "__learner_text": LEARNER_TEXT,
        "__support_language": "vi",
    }


# --- What the evaluator is asked for ------------------------------------


def test_the_evaluator_is_asked_for_every_genuine_error() -> None:
    """The instruction that produced one finding for five mistakes is gone.

    Precision is still required - nothing invented, nothing uncertain - but
    being the fifth true thing is no longer a reason to be left out.
    """
    request = build_writing_evaluator_request(
        language_name="English",
        support_language_name="Vietnamese",
        target_level="B1",
        task_prompt="An email to a colleague",
        learner_text=LEARNER_TEXT,
        free_writing_context="(free writing)",
    )
    assert "Fewer high-confidence findings are preferable" not in request
    assert "EVERY genuine error" in request
    assert "verb-form, agreement, article, tense, word-choice" in request
    # And ranking, so the surface can show a few first without the rest being lost.
    assert "highest `confidence` to the errors that matter most" in request
    # Precision is not traded away for it.
    assert "never invent a problem" in request
    assert "never mark a wording wrong when another reading of it is correct" in request
    assert f"confidence >= {CONFIDENCE_THRESHOLD:.2f}" in request


# --- What survives normalization ----------------------------------------


def test_every_trustworthy_finding_survives() -> None:
    """Five independent mistakes, five findings - not the first one only."""
    result = validate_result(
        _result(
            [
                _finding("word_form", "wanna to telling", "want to tell", 0.95),
                _finding("tense", "didn't finished", "didn't finish", 0.93),
                _finding("preposition", "in times", "in time", 0.90),
                _finding("article", "meetings with customer", "meetings with a customer", 0.82),
                _finding("naturalness", "wanna", "want to", 0.80),
            ]
        )
    )
    quotes = [issue["fragment"] for issue in result["errors"]]
    assert len(quotes) == 5, f"a finding was lost: {quotes}"
    # The one that used to disappear entirely.
    assert "didn't finished" in quotes
    # Ranked by confidence, so the surface can lead with the strongest.
    confidences = [issue["confidence"] for issue in result["errors"]]
    assert confidences == sorted(confidences, reverse=True)
    assert result["errors"][0]["fragment"] == "wanna to telling"


def test_a_finding_that_cannot_be_located_is_kept_without_a_span() -> None:
    """An evaluator that reworded its own quote loses the span, not the point.

    This is the second half of the bug: a finding whose fragment is not
    verbatim used to be discarded, so a real mistake went unmentioned because
    a quote lost an apostrophe.
    """
    result = validate_result(
        _result(
            [
                _finding("tense", "didn't finished", "didn't finish"),
                # The same mistake, quoted with a typographic apostrophe.
                _finding("tense", "didn’t finished", "didn’t finish"),
            ]
        )
    )
    by_fragment = {issue["fragment"]: issue for issue in result["errors"]}
    assert len(by_fragment) == 2, "both findings are kept"
    verbatim = by_fragment["didn't finished"]
    reworded = by_fragment["didn’t finished"]
    assert verbatim["anchored"] is True
    assert verbatim["span"]["end"] > verbatim["span"]["start"], "a located finding has a real span"
    assert reworded["anchored"] is False
    assert reworded["span"] == {"start": 0, "end": 0}, "and an unlocated one claims none"


def test_nothing_untrustworthy_is_kept() -> None:
    """Keeping more findings must not mean keeping worse ones."""
    result = validate_result(
        _result(
            [
                _finding("tense", "didn't finished", "didn't finish", 0.95),
                # Below the confidence bar.
                _finding("tense", "in times", "in time", CONFIDENCE_THRESHOLD - 0.01),
                # A suggestion that changes nothing.
                _finding("article", "the report", "the report", 0.95),
                # No explanation to act on.
                {
                    "category": "tense",
                    "fragment": "Could you help me",
                    "suggestion": "Would you help me",
                    "explanation_vi": "",
                    "mini_rule_vi": "r",
                    "confidence": 0.95,
                },
                # A category the language profile does not define.
                _finding("vibes", "the Da Nang trip", "the trip to Da Nang", 0.95),
            ]
        )
    )
    quotes = [issue["fragment"] for issue in result["errors"]]
    assert quotes == ["didn't finished"], f"only the trustworthy one survives: {quotes}"


def test_the_learner_can_still_be_told_nothing_is_wrong() -> None:
    result = validate_result(_result([]))
    assert result["errors"] == []


@pytest.mark.parametrize(
    ("fragment", "expected"),
    (
        ("wanna to telling", True),
        ("in times", True),
        ("wholly absent phrase", False),
    ),
)
def test_anchoring_is_literal_occurrence(fragment: str, expected: bool) -> None:
    """Anchoring is exact-occurrence, never a fuzzy guess at where to point."""
    result = validate_result(_result([_finding("word_form", fragment, "something else")]))
    assert len(result["errors"]) == 1, "the finding is kept either way"
    assert result["errors"][0]["anchored"] is expected
