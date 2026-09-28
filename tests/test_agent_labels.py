"""The learner-facing names of internal labels a tool hands the model (human review 2026-09-28)."""

from __future__ import annotations

import pytest

from writing_coach.agent.labels import (
    ERROR_CATEGORY,
    ISSUE_KIND,
    PRONUNCIATION_ERROR,
    REVIEW_MEANING,
    REVIEW_STATUS,
    category_label,
    review_state,
)
from writing_coach.agent.read_tools import ISSUE_KINDS
from writing_coach.languages.chinese.profile import ERROR_CATEGORIES as ZH_CATEGORIES
from writing_coach.languages.english.profile import ERROR_CATEGORIES as EN_CATEGORIES


@pytest.mark.parametrize("table", [REVIEW_STATUS, REVIEW_MEANING, ERROR_CATEGORY, ISSUE_KIND, PRONUNCIATION_ERROR])
def test_every_label_is_in_every_interface_language(table):
    for key, names in table.items():
        assert set(names) == {"en", "vi", "zh-CN"} and all(names.values()), key


def test_every_category_either_evaluator_writes_has_a_name():
    assert set(EN_CATEGORIES) | set(ZH_CATEGORIES) <= set(ERROR_CATEGORY)
    assert set(ISSUE_KINDS) <= set(ISSUE_KIND)


@pytest.mark.parametrize(
    ("stage", "due", "interface", "expected"),
    [
        (0, False, "vi", {"status": "Chưa học", "status_meaning": "đã lưu, chưa ôn lần nào", "due": False}),
        (1, True, "vi", {"status": "Đang học", "status_meaning": "đã ôn vài lần, chưa nhớ chắc", "due": True, "due_label": "Đến hạn ôn"}),
        (4, False, "zh-CN", {"status": "已掌握", "status_meaning": "记得牢，偶尔复习", "due": False}),
        (2, False, "en", {"status": "Learning", "status_meaning": "reviewed a few times, not yet secure", "due": False}),
    ],
)  # fmt: skip
def test_the_review_state_is_a_name_and_a_meaning_never_the_internal_label(stage, due, interface, expected):
    state = review_state(stage, due, interface)
    assert state == expected
    assert not {"New", "Learning", "Reinforcing", "Available"} & set(state.values()) or interface == "en"


def test_an_unknown_category_is_named_other_not_passed_through():
    assert category_label("made_up_key", "vi") == "Khác"
