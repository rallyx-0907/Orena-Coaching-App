from __future__ import annotations

from app import revision_delta


def _issue(category: str, fragment: str, suggestion: str = "fixed") -> dict[str, object]:
    return {
        "id": f"{category}-{fragment}",
        "category": category,
        "fragment": fragment,
        "suggestion": suggestion,
        "span": {"start": 0, "end": len(fragment)},
    }


def test_revision_delta_reports_removed_persistent_new_and_changed_issues() -> None:
    previous = {
        "grammar": 60,
        "vocabulary": 70,
        "coherence": 65,
        "task_achievement": 70,
        "naturalness": 62,
        "overall": 65,
        "errors": [_issue("agreement", "I has"), _issue("article", "a dog")],
    }
    current = {
        "grammar": 72,
        "vocabulary": 70,
        "coherence": 65,
        "task_achievement": 70,
        "naturalness": 62,
        "overall": 69,
        "errors": [_issue("agreement", "I have"), _issue("word_order", "dog a")],
    }

    delta = revision_delta(current, previous)

    assert delta["overall"] == 4.0
    assert delta["issues"]["changed"][0]["before"]["fragment"] == "I has"
    assert delta["issues"]["changed"][0]["after"]["fragment"] == "I have"
    assert [item["fragment"] for item in delta["issues"]["removed"]] == ["a dog"]
    assert [item["fragment"] for item in delta["issues"]["new"]] == ["dog a"]
    assert delta["issues"]["persistent"] == []


def _draft(errors: list[dict[str, object]], overall: int = 65) -> dict[str, object]:
    return {
        "grammar": 60,
        "vocabulary": 70,
        "coherence": 65,
        "task_achievement": 70,
        "naturalness": 62,
        "overall": overall,
        "errors": errors,
    }


def test_an_unchanged_issue_stays_persistent_beside_a_real_revision() -> None:
    """An issue in both drafts is the same issue.

    Pairing by category alone used to pick an arbitrary member of each side, so
    a learner who fixed one grammar problem and kept another could be told the
    kept one was removed and simultaneously new. Exact matches are settled
    before any correspondence is inferred.
    """
    previous = _draft([_issue("grammar", "I has"), _issue("grammar", "a dog")])
    current = _draft([_issue("grammar", "I has"), _issue("grammar", "the dog")])

    issues = revision_delta(current, previous)["issues"]

    assert [item["fragment"] for item in issues["persistent"]] == ["I has"]
    assert issues["removed"] == []
    assert issues["new"] == []
    assert [
        (pair["before"]["fragment"], pair["after"]["fragment"]) for pair in issues["changed"]
    ] == [("a dog", "the dog")]


def test_ambiguous_correspondence_is_reported_rather_than_guessed() -> None:
    """Two unmatched issues on each side: which became which is not knowable.

    Reporting them as gone and arrived is true. Inventing a pairing would tell
    the learner something about their own writing that the data cannot support.
    """
    previous = _draft([_issue("grammar", "I has"), _issue("grammar", "he go")])
    current = _draft([_issue("grammar", "a dog"), _issue("grammar", "the cat")])

    issues = revision_delta(current, previous)["issues"]

    assert issues["changed"] == []
    assert sorted(item["fragment"] for item in issues["removed"]) == ["I has", "he go"]
    assert sorted(item["fragment"] for item in issues["new"]) == ["a dog", "the cat"]


def test_chinese_issues_follow_the_same_rule() -> None:
    previous = _draft([_issue("grammar", "我是学生的"), _issue("grammar", "他去了没有")])
    current = _draft([_issue("grammar", "我是学生的"), _issue("grammar", "他没有去")])

    issues = revision_delta(current, previous)["issues"]

    assert [item["fragment"] for item in issues["persistent"]] == ["我是学生的"]
    assert [
        (pair["before"]["fragment"], pair["after"]["fragment"]) for pair in issues["changed"]
    ] == [("他去了没有", "他没有去")]
