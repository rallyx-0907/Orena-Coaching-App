"""The evaluator contract version is effective per language pair (D-103 point 7).

v2.7 changed the answer only for Chinese writing explained in a language other than Chinese, so
only that pair moves; every other pair keeps the identity its stored reviews carry and is never
re-graded (and never charged) for a change that cannot touch it.
"""
from __future__ import annotations

import pytest

from writing_coach.writing_review_identity import (
    EVALUATOR_CONTRACT_VERSION,
    PREVIOUS_EVALUATOR_CONTRACT_VERSION,
    contract_version_for,
    review_identity,
    v27_affects,
)


@pytest.mark.parametrize(
    ("learning", "support", "affected"),
    [
        ("zh", "vi", True),
        ("zh", "en", True),
        ("zh", "ja", True),
        ("zh-CN", "vi", True),
        ("zh", "zh", False),
        ("zh", "zh-TW", False),
        ("en", "vi", False),
        ("en", "zh", False),
        ("en", "en", False),
    ],
)
def test_only_chinese_explained_in_another_language_is_affected(learning, support, affected):
    assert v27_affects(learning, support) is affected
    expected = EVALUATOR_CONTRACT_VERSION if affected else PREVIOUS_EVALUATOR_CONTRACT_VERSION
    assert contract_version_for(learning, support) == expected


def test_an_unaffected_pair_keeps_the_identity_its_stored_reviews_carry():
    kw = {"text": "I has a dog.", "learning_language": "en", "support_language": "vi", "prompt": "p"}
    assert review_identity(**kw) == review_identity(**kw, contract_version=PREVIOUS_EVALUATOR_CONTRACT_VERSION)
    assert review_identity(**kw)["contract"] == PREVIOUS_EVALUATOR_CONTRACT_VERSION


def test_the_affected_pair_moves_to_the_new_identity():
    kw = {"text": "我有三个书。", "learning_language": "zh", "support_language": "vi", "prompt": "p"}
    old = review_identity(**kw, contract_version=PREVIOUS_EVALUATOR_CONTRACT_VERSION)
    new = review_identity(**kw)
    assert new["contract"] == EVALUATOR_CONTRACT_VERSION
    assert new["fingerprint"] != old["fingerprint"], "a stored v2.6 Chinese review is no longer reused"
