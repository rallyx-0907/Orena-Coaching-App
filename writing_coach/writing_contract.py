"""The Writing room's two contracts: WritingReview and RevisionCompare (D-066).

The canonical UI (`docs/design/canonical-ui/data-contracts/WritingReview.json`
and `RevisionCompare.json`) decides these shapes. This module projects a stored
review - and, for a revision, the review before it - into them. It is pure: it
reads two dicts the review endpoints already produce, and invents nothing.

What it does not do is judge. Which issues a revision fixed, left or introduced
is `revision_delta`'s answer (an exact match is the same issue, and a category
guess is only made where it is unambiguous); this only names them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from writing_coach.languages.chinese.profile import ERROR_CATEGORIES as ZH_CATEGORIES
from writing_coach.languages.english.profile import ERROR_CATEGORIES as EN_CATEGORIES

KINDS = ("register", "grammar", "punctuation", "vocabulary", "naturalness")

# The evaluator names findings finely (an article, a measure word); the baseline
# draws five kinds. Every category of both languages lands on exactly one, and a
# test holds the table complete. `coherence` and `task` are not sentence-level
# findings the baseline has a kind for; they read as naturalness, the nearest.
KIND_OF_CATEGORY: Mapping[str, str] = {
    # English
    "article": "grammar",
    "tense": "grammar",
    "agreement": "grammar",
    "word_form": "grammar",
    "preposition": "grammar",
    "sentence_structure": "grammar",
    "spelling": "grammar",
    # Chinese
    "word_order": "grammar",
    "particle": "grammar",
    "aspect": "grammar",
    "complement": "grammar",
    "measure_word": "grammar",
    "ba_sentence": "grammar",
    "bei_sentence": "grammar",
    "conjunction": "grammar",
    "character_choice": "vocabulary",
    "collocation": "vocabulary",
    "redundancy": "naturalness",
    # Both
    "word_choice": "vocabulary",
    "punctuation": "punctuation",
    "register": "register",
    "naturalness": "naturalness",
    "coherence": "naturalness",
    "task": "naturalness",
    "other": "grammar",
}
assert set(KIND_OF_CATEGORY.values()) <= set(KINDS)
assert set(EN_CATEGORIES) | set(ZH_CATEGORIES) <= set(KIND_OF_CATEGORY)

# The four dimensions the baseline draws, in its order. `task_achievement` is
# scored by the evaluator and kept in the stored review; the baseline does not
# draw it.
DIMENSIONS = ("naturalness", "grammar", "vocabulary", "coherence")


def _text(value: object) -> str:
    return str(value or "").strip()


def kind_of(category: object) -> str:
    return KIND_OF_CATEGORY.get(_text(category).casefold(), "grammar")


def _score(review: Mapping[str, Any], key: str) -> float | None:
    value = review.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return round(float(value), 1)


def _grammar_ref(review: Mapping[str, Any], issue_id: object) -> str | None:
    for link in review.get("grammar_links") or ():
        if isinstance(link, Mapping) and link.get("issue_id") == issue_id and link.get("grammar_id"):
            return str(link["grammar_id"])
    return None


def project_issue(review: Mapping[str, Any], error: Mapping[str, Any], index: int) -> dict[str, Any]:
    example = _text(error.get("example"))
    identifier = error.get("id") or f"issue-{index + 1}"
    return {
        "id": identifier,
        "fragment": _text(error.get("fragment") or error.get("quote")),
        "correction": _text(error.get("suggestion")),
        "why": _text(error.get("explanation_vi") or error.get("why")),
        "rule": _text(error.get("mini_rule_vi") or error.get("how")),
        "grammarRef": _grammar_ref(review, identifier),
        "examples": [example] if example else [],
        "kind": kind_of(error.get("category")),
        # What the surface needs to point at the words, when they can be found.
        "anchored": bool(error.get("anchored")),
        "span": error.get("span") if isinstance(error.get("span"), Mapping) else {"start": 0, "end": 0},
    }


def project_dimensions(review: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The four dimensions, by stable key; the interface names them in its language.

    A dimension the review does not carry is left out rather than shown as 0.
    """
    return [{"name": key, "value": score} for key in DIMENSIONS if (score := _score(review, key)) is not None]


def project_review(review: Mapping[str, Any]) -> dict[str, Any]:
    """WritingReview.json from a stored review (the detailed row shape)."""
    errors = [item for item in review.get("errors") or () if isinstance(item, Mapping)]
    strengths = [_text(item) for item in review.get("strengths_vi") or () if _text(item)]
    return {
        "draftId": str(review.get("series_id") or review.get("id") or ""),
        "version": int(review.get("revision_no") or 1),
        "wordCount": int(review.get("word_count") or 0),
        "summary": _text(review.get("summary_vi")),
        "strengths": " ".join(strengths),
        "issues": [project_issue(review, item, index) for index, item in enumerate(errors)],
        "dimensions": project_dimensions(review),
    }


def _change(item: Mapping[str, Any], *, fixed: bool = False) -> dict[str, str]:
    """A change: the words concerned, and what to do with them.

    The title is the learner's own fragment and the detail is the finding's own
    correction and reason, so no sentence about the learner is written here that
    the evaluator did not say. What kind of thing it was rides along as `kind`,
    and the interface names it in its own language.
    """
    fragment = _text(item.get("fragment") or item.get("quote"))
    suggestion = _text(item.get("suggestion"))
    why = _text(item.get("explanation_vi") or item.get("why"))
    if fixed:
        detail = f"{fragment} → {suggestion}" if fragment and suggestion else fragment or suggestion
    else:
        detail = f"{suggestion} - {why}" if suggestion and why else suggestion or why
    return {"title": fragment, "kind": kind_of(item.get("category")), "detail": detail}


def project_revision(current: Mapping[str, Any], previous: Mapping[str, Any]) -> dict[str, Any]:
    """RevisionCompare.json from a review and the one before it.

    `current["delta"]["issues"]` is `revision_delta`'s verdict; it is not
    recomputed here. `removed` were fixed, `persistent` remain and `new` are new;
    a `changed` pair is the same problem in new words, so it counts as remaining.
    """
    delta_issues = ((current.get("delta") or {}).get("issues")) or {}
    removed: Sequence[Mapping[str, Any]] = delta_issues.get("removed") or ()
    persistent: Sequence[Mapping[str, Any]] = delta_issues.get("persistent") or ()
    fresh: Sequence[Mapping[str, Any]] = delta_issues.get("new") or ()
    changed: Sequence[Mapping[str, Any]] = delta_issues.get("changed") or ()
    return {
        "previous": {
            "version": int(previous.get("revision_no") or 1),
            "wordCount": int(previous.get("word_count") or 0),
            "text": str(previous.get("text") or ""),
        },
        "current": {
            "version": int(current.get("revision_no") or 1),
            "wordCount": int(current.get("word_count") or 0),
            "text": str(current.get("text") or ""),
        },
        "fixed": [_change(item, fixed=True) for item in removed],
        "remaining": [_change(item) for item in persistent]
        + [_change(pair.get("after") or {}) for pair in changed if isinstance(pair, Mapping)],
        "added": [_change(item) for item in fresh],
        "dimensionDeltas": [
            {"name": key, "from": before, "to": after}
            for key in DIMENSIONS
            if (before := _score(previous, key)) is not None and (after := _score(current, key)) is not None
        ],
    }
