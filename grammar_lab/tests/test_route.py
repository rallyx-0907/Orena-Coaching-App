from __future__ import annotations

from grammar_lab.pipeline.route import RouteOutcome, apply_route, route_point, score_point
from grammar_lab.pipeline.verify import VerifyFlag, VerifyReport


def clean_verify() -> VerifyReport:
    return VerifyReport(point_id="en.alpha", flags=[])


def test_clean_point_past_gold_set_and_threshold_is_auto_ok() -> None:
    outcome = route_point(
        "en.alpha", validate_issue_codes=set(), verify_report=clean_verify(),
        threshold=0.8, gold_set_passed=True,
    )
    assert outcome.status in {"auto_ok"}
    assert outcome.score == 1.0


def test_validate_issue_always_flags_even_with_clean_verify() -> None:
    outcome = route_point(
        "en.alpha", validate_issue_codes={"schema.invalid"}, verify_report=clean_verify(),
        threshold=0.8, gold_set_passed=True,
    )
    assert outcome.status == "flagged"
    assert "validate:schema.invalid" in outcome.flags


def test_verify_flag_flags_the_point() -> None:
    verify = VerifyReport(point_id="en.alpha", flags=[VerifyFlag("pitfall_not_caught", "detail")])
    outcome = route_point(
        "en.alpha", validate_issue_codes=set(), verify_report=verify, threshold=0.8, gold_set_passed=True,
    )
    assert outcome.status == "flagged"
    assert "verify:pitfall_not_caught" in outcome.flags


def test_gold_set_not_passed_flags_everything_even_when_perfectly_clean() -> None:
    outcome = route_point(
        "en.alpha", validate_issue_codes=set(), verify_report=clean_verify(),
        threshold=0.8, gold_set_passed=False,
    )
    assert outcome.status == "flagged"
    assert outcome.flags == ["route:gold_set_not_passed"]


def test_score_below_threshold_is_flagged() -> None:
    outcome = route_point(
        "en.alpha", validate_issue_codes=set(), verify_report=clean_verify(),
        threshold=1.1, gold_set_passed=True,  # impossible threshold forces below-threshold
    )
    assert outcome.status == "flagged"
    assert outcome.flags == ["route:below_threshold:1.1"]


def test_score_point_deducts_once_per_failing_category_not_per_instance() -> None:
    # Two different pitfall-category codes both present -> still one 0.4 deduction.
    score = score_point({"pitfall_not_caught", "pitfall_right_flagged"})
    assert score == 0.6


def test_score_point_combines_categories() -> None:
    score = score_point({"pitfall_not_caught", "example_not_clean", "blind_solve_wrong"})
    assert score == 0.0  # 1.0 - 0.4 - 0.3 - 0.3, clamped at 0


def test_score_point_clean_is_one() -> None:
    assert score_point(set()) == 1.0


def test_sampled_points_are_deterministic_across_calls() -> None:
    outcome_a = route_point("en.past_simple", validate_issue_codes=set(), verify_report=clean_verify(),
                             threshold=0.8, gold_set_passed=True)
    outcome_b = route_point("en.past_simple", validate_issue_codes=set(), verify_report=clean_verify(),
                             threshold=0.8, gold_set_passed=True)
    assert outcome_a.sampled == outcome_b.sampled


def test_zh_point_with_story_is_always_flagged_even_with_gold_set_passed() -> None:
    outcome = route_point(
        "zh.le_completion", validate_issue_codes=set(), verify_report=clean_verify(),
        threshold=0.8, gold_set_passed=True, target_lang="zh-Hans", has_story=True,
    )
    assert outcome.status == "flagged"
    assert outcome.flags == ["route:zh_story_always_reviewed"]


def test_zh_point_without_story_follows_the_normal_rules() -> None:
    outcome = route_point(
        "zh.le_completion", validate_issue_codes=set(), verify_report=clean_verify(),
        threshold=0.8, gold_set_passed=True, target_lang="zh-Hans", has_story=False,
    )
    assert outcome.status == "auto_ok"


def test_en_point_with_story_is_unaffected_by_the_zh_rule() -> None:
    outcome = route_point(
        "en.alpha", validate_issue_codes=set(), verify_report=clean_verify(),
        threshold=0.8, gold_set_passed=True, target_lang="en", has_story=True,
    )
    assert outcome.status == "auto_ok"


def test_apply_route_updates_status_and_flags_without_touching_review() -> None:
    point = {"id": "en.alpha", "status": "draft_ai", "flags": [], "review": None, "version": 1}
    outcome = RouteOutcome("en.alpha", 1.0, "auto_ok", ["route:sampled_for_review"], sampled=True)
    updated = apply_route(point, outcome)
    assert updated["status"] == "auto_ok"
    assert updated["flags"] == ["route:sampled_for_review"]
    assert updated["review"] is None
    assert updated["version"] == 1


def test_engine_unverified_text_keeps_the_point_out_of_auto_ok_without_counting_as_an_error() -> None:
    report = VerifyReport("en.alpha", unverified=["examples[0] 'She works'"])
    outcome = route_point("en.alpha", validate_issue_codes=set(), verify_report=report,
                          threshold=0.8, gold_set_passed=True)
    assert outcome.status == "flagged"
    assert outcome.flags == ["route:engine_unverified:1"]
    assert outcome.score == 1.0
