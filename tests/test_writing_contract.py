"""The Writing room contracts (D-066): WritingReview and RevisionCompare.

The shapes come from the pinned canonical baseline; these tests hold the backend
to those files and check the two things that are not a projection: the kind table
is complete, and a comparison sees the earlier review's findings.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app import revision_delta, row_to_dict
from writing_coach import writing_contract as wc
from writing_coach.languages.chinese.profile import ERROR_CATEGORIES as ZH
from writing_coach.languages.english.profile import ERROR_CATEGORIES as EN

CONTRACTS = Path(__file__).resolve().parents[1] / "docs" / "design" / "canonical-ui" / "data-contracts"


def contract(name: str) -> dict[str, Any]:
    return json.loads((CONTRACTS / f"{name}.json").read_text(encoding="utf-8"))


def assert_covers(template: Any, value: Any, path: str = "$") -> None:
    if isinstance(template, dict):
        assert isinstance(value, dict), f"{path} should be an object"
        for key, inner in template.items():
            if key.startswith("_"):
                continue
            assert key in value, f"{path}.{key} is missing"
            assert_covers(inner, value[key], f"{path}.{key}")
    elif isinstance(template, list) and template and isinstance(template[0], dict) and value:
        assert_covers(template[0], value[0], f"{path}[0]")


def error(category: str, fragment: str, suggestion: str, **more: Any) -> dict[str, Any]:
    return {
        "id": f"{category}-{fragment}",
        "category": category,
        "fragment": fragment,
        "suggestion": suggestion,
        "explanation_vi": f"why {fragment}",
        "mini_rule_vi": f"rule {fragment}",
        "anchored": True,
        "span": {"start": 0, "end": len(fragment)},
        **more,
    }


V1 = {
    "id": 1, "series_id": 1, "revision_no": 1, "word_count": 142, "text": "Jeg ønsker å informere deg om noe. På et kafé, han hjelper meg.",
    "grammar": 84.0, "vocabulary": 80.0, "coherence": 88.0, "naturalness": 72.0, "task_achievement": 70.0, "overall": 79.0,
    "summary_vi": "Thư đủ ý.", "strengths_vi": ["Mở thư đúng kiểu.", "Câu hỏi cuối giữ mạch."],
    "errors": [
        error("register", "ønsker å informere deg om", "må bare fortelle deg", example="Jeg må bare fortelle deg at jeg har ny jobb."),
        error("article", "et kafé", "en kafé"),
        error("punctuation", ", han hjelper meg", ", og han hjelper meg"),
    ],
    "grammar_links": [{"issue_id": "article-et kafé", "grammar_id": "no-gender", "title": "Gender"}],
}
V2 = {
    **V1, "id": 2, "revision_no": 2, "word_count": 151, "text": "Jeg må bare fortelle deg noe. På en kafé, han hjelper meg. Det er veldig masse.",
    "naturalness": 88.0, "grammar": 90.0, "vocabulary": 78.0, "coherence": 88.0,
    "errors": [
        error("punctuation", ", han hjelper meg", ", og han hjelper meg"),
        error("word_choice", "veldig masse", "veldig mye"),
    ],
    "grammar_links": [],
}


def test_every_category_of_both_languages_has_exactly_one_kind() -> None:
    for category in {*EN, *ZH}:
        assert wc.KIND_OF_CATEGORY[category] in wc.KINDS, category
    assert set(wc.KINDS) == {"register", "grammar", "punctuation", "vocabulary", "naturalness"}
    documented = set(contract("WritingReview")["issues"][0]["kind"].split(" | "))
    assert documented == set(wc.KINDS), "the kinds are the baseline's"


def test_a_review_matches_the_canonical_contract() -> None:
    review = wc.project_review(V1)
    assert_covers(contract("WritingReview"), review)
    assert review["version"] == 1 and review["wordCount"] == 142
    assert review["strengths"] == "Mở thư đúng kiểu. Câu hỏi cuối giữ mạch."
    assert [issue["kind"] for issue in review["issues"]] == ["register", "grammar", "punctuation"]
    first, second, _third = review["issues"]
    assert first["examples"] == ["Jeg må bare fortelle deg at jeg har ny jobb."]
    assert first["correction"] == "må bare fortelle deg" and first["rule"] == "rule ønsker å informere deg om"
    assert second["examples"] == [] and second["grammarRef"] == "no-gender"
    assert first["grammarRef"] is None
    assert first["anchored"] is True
    # Four dimensions, by stable key, in the baseline's order; task_achievement stays out.
    assert [d["name"] for d in review["dimensions"]] == ["naturalness", "grammar", "vocabulary", "coherence"]
    assert review["dimensions"][0]["value"] == 72.0


def test_a_dimension_the_review_does_not_carry_is_left_out_not_zeroed() -> None:
    thin = {**V1}
    del thin["vocabulary"]
    names = [d["name"] for d in wc.project_review(thin)["dimensions"]]
    assert "vocabulary" not in names and len(names) == 3


def test_a_revision_matches_the_canonical_contract_and_uses_the_real_delta() -> None:
    current = {**V2, "delta": revision_delta(V2, V1)}
    revision = wc.project_revision(current, V1)
    assert_covers(contract("RevisionCompare"), revision)
    assert revision["previous"]["version"] == 1 and revision["current"]["version"] == 2
    assert revision["previous"]["wordCount"] == 142 and revision["current"]["wordCount"] == 151
    fixed = {item["title"] for item in revision["fixed"]}
    assert fixed == {"ønsker å informere deg om", "et kafé"}
    assert [item["title"] for item in revision["remaining"]] == [", han hjelper meg"]
    assert [item["title"] for item in revision["added"]] == ["veldig masse"]
    assert revision["added"][0]["kind"] == "vocabulary"
    assert revision["added"][0]["detail"] == "veldig mye - why veldig masse"
    assert next(i for i in revision["fixed"] if i["title"] == "et kafé")["detail"] == "et kafé → en kafé"
    assert revision["dimensionDeltas"][0] == {"name": "naturalness", "from": 72.0, "to": 88.0}
    # A drop is reported as a drop, not smoothed.
    assert {"name": "vocabulary", "from": 80.0, "to": 78.0} in revision["dimensionDeltas"]


def test_a_comparison_sees_the_earlier_reviews_findings_when_given_the_stored_row() -> None:
    """The repository returns a stored row whose findings are still JSON text.

    Given that row unparsed the comparison read no earlier findings at all, so
    every current issue looked new and nothing looked fixed. Hydrated the way the
    review endpoints now do it, the comparison is right.
    """
    stored = {k: v for k, v in V1.items() if k not in {"errors", "grammar_links", "strengths_vi"}}
    stored.update(
        strengths_json=json.dumps(V1["strengths_vi"]), priorities_json="[]", errors_json=json.dumps(V1["errors"]),
        module_data_json="{}", strength_evidence_json="[]",
    )
    blind = revision_delta(V2, stored)["issues"]
    assert blind["removed"] == [], "the unparsed row hides the earlier findings"
    seen = revision_delta(V2, row_to_dict(stored, detail=True))["issues"]
    assert {item["fragment"] for item in seen["removed"]} == {"ønsker å informere deg om", "et kafé"}
    assert [item["fragment"] for item in seen["persistent"]] == [", han hjelper meg"]
