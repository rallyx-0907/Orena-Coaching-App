"""The canonical Reading policies are deterministic functions of their inputs.

Judging, ability and selection are versioned rules (D-075): the same inputs
always give the same outputs, so each is proved by fixing its inputs.
"""
from __future__ import annotations

import pytest

from writing_coach import reading_policy as policy


def _judged(*correct: bool, qtype: str = "detail") -> list[policy.Judged]:
    return [policy.Judged(f"q{index}", qtype, 0, value) for index, value in enumerate(correct)]


def test_levels_share_one_axis_across_languages():
    assert policy.passage_difficulty("b1") == policy.passage_difficulty("HSK3") == 3.0
    assert policy.passage_difficulty("HSK7-9") == 7.0
    assert policy.passage_difficulty("") is None
    assert policy.passage_difficulty("unknown") is None


def test_judging_names_the_correct_option_only():
    questions = [{"id": "a", "question_type": "detail", "correct_index": 2},
                 {"id": "b", "question_type": "inference", "correct_index": 0}]
    judged = policy.judge(questions, {"a": 2, "b": 1})
    assert [(item.question_id, item.correct) for item in judged] == [("a", True), ("b", False)]


def test_the_digest_is_order_free_and_bound_to_its_set():
    one = policy.request_digest("set-1", {"a": 1, "b": 2})
    assert one == policy.request_digest("set-1", {"b": 2, "a": 1})
    assert one != policy.request_digest("set-2", {"a": 1, "b": 2})
    assert one != policy.request_digest("set-1", {"a": 2, "b": 2})
    assert len(one) == 64


def test_ability_moves_toward_the_evidence_by_a_shrinking_step():
    state = policy.AbilityState()
    first = policy.apply(state, ordinal=1, passage_level="B1", judged=_judged(True, True, True))
    assert first.ability_before == policy.INITIAL_ABILITY
    assert first.ability_after > first.ability_before
    step_one = first.ability_after - first.ability_before
    second = policy.apply(state, ordinal=2, passage_level="B1", judged=_judged(True, True, True))
    assert second.ability_after > second.ability_before
    assert second.ability_after - second.ability_before < step_one
    wrong = policy.apply(state, ordinal=3, passage_level="A1", judged=_judged(False, False))
    assert wrong.ability_after < wrong.ability_before
    assert state.by_question_type["detail"] == [6, 8]


def test_an_unmeasurable_attempt_still_advances_the_checkpoint():
    state = policy.AbilityState()
    assert policy.apply(state, ordinal=1, passage_level="", judged=_judged(True)) is None
    assert (state.ability, state.consumed_through_ordinal) == (policy.INITIAL_ABILITY, 1)


def test_an_attempt_is_applied_once_and_in_order():
    state = policy.AbilityState()
    policy.apply(state, ordinal=1, passage_level="B1", judged=_judged(True))
    with pytest.raises(ValueError):
        policy.apply(state, ordinal=1, passage_level="B1", judged=_judged(True))
    with pytest.raises(ValueError):
        policy.apply(state, ordinal=3, passage_level="B1", judged=_judged(True))


def test_ability_stays_within_its_bounds():
    state = policy.AbilityState(ability=7.4)
    for ordinal in range(1, 40):
        policy.apply(state, ordinal=ordinal, passage_level="HSK7-9", judged=_judged(True, True))
    assert state.ability <= 7.5
    low = policy.AbilityState(ability=0.6)
    for ordinal in range(1, 40):
        policy.apply(low, ordinal=ordinal, passage_level="A1", judged=_judged(False, False))
    assert low.ability >= 0.5


def test_weak_types_need_evidence_and_rank_weakest_first():
    assert policy.weak_types({"detail": [0, 1]}) == ()
    assert policy.weak_types({"detail": [1, 4], "inference": [0, 2], "main_idea": [3, 3]}) == (
        "inference", "detail")


def _candidate(article: str, level: str, published: str = "2026-09-01", types=()):
    return policy.Candidate(article, f"set-{article}", level, published, frozenset(types))


def _choose(**overrides):
    values = dict(ability=2.0, by_question_type={}, recent_accuracy=[], next_ordinal=1,
                  candidates=[], attempted_article_ids=[])
    values.update(overrides)
    return policy.choose(**values)


def test_selection_follows_ability_recent_performance_and_probes():
    pool = [_candidate("a1", "A1"), _candidate("a2", "A2"), _candidate("b1", "B1"), _candidate("c1", "C1")]
    assert _choose(candidates=pool).article_id == "a2"
    # Recent success moves the target up half a level; A2 and B1 tie on
    # distance, so the most recently published wins, then the smallest id.
    assert _choose(candidates=pool, recent_accuracy=[1.0, 0.9, 0.8]).target_difficulty == 2.5
    # Recent struggle moves it down.
    assert _choose(candidates=pool, recent_accuracy=[0.0, 0.2]).target_difficulty == 1.5
    probe = _choose(candidates=pool, next_ordinal=5)
    assert probe.probe and probe.article_id == "b1"


def test_selection_prefers_weak_types_then_nearness_then_newest():
    pool = [_candidate("x", "A2", "2026-09-01", ["detail"]),
            _candidate("y", "A2", "2026-09-05", ["detail"]),
            _candidate("z", "B1", "2026-09-01", ["inference"])]
    assert _choose(candidates=pool).article_id == "y"
    weak = {"inference": [0, 3]}
    assert _choose(candidates=pool, by_question_type=weak).article_id == "z"


def test_selection_never_repeats_and_is_none_when_nothing_is_left():
    pool = [_candidate("a", "A2"), _candidate("b", "B2")]
    assert _choose(candidates=pool, attempted_article_ids=["a"]).article_id == "b"
    assert _choose(candidates=pool, attempted_article_ids=["a", "b"]) is None
    assert _choose(candidates=[_candidate("u", "unknown")]) is None
    # Out of band, the nearest is taken.
    assert _choose(candidates=[_candidate("far", "C2")]).article_id == "far"
