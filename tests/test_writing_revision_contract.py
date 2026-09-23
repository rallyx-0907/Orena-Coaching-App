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


def _with_text(review: dict[str, object], text: str) -> dict[str, object]:
    return {**review, "text": text}


def test_a_finding_is_fixed_when_its_words_are_gone_and_not_when_they_are_still_there() -> None:
    """The evaluator words a finding differently each time; the words decide.

    Reviewed again, the same untouched sentence came back with its fragment cut
    differently. Matching on identical wording called that a new problem and the
    original a fixed one - and told a learner who had changed one thing that they
    had fixed everything.
    """
    before = _with_text(
        _draft([_issue("tense", "I go to the shop"), _issue("word_form", "I buyed some bread")]),
        "Yesterday I go to the shop and I buyed some bread.",
    )
    after = _with_text(
        # The learner fixed the first sentence and left the second alone; this time
        # the evaluator names the untouched one by a shorter stretch of it.
        _draft([_issue("word_form", "buyed")]),
        "Yesterday I went to the shop and I buyed some bread.",
    )

    issues = revision_delta(after, before)["issues"]

    assert [item["fragment"] for item in issues["removed"]] == ["I go to the shop"]
    assert [item["fragment"] for item in issues["persistent"]] == ["buyed"]
    assert issues["new"] == [] and issues["changed"] == []


def test_words_left_untouched_and_not_flagged_again_are_not_called_fixed() -> None:
    before = _with_text(_draft([_issue("tense", "I go to the shop")]), "Yesterday I go to the shop.")
    after = _with_text(_draft([]), "Yesterday I go to the shop.")

    issues = revision_delta(after, before)["issues"]

    assert issues["removed"] == [], "the learner changed nothing, so nothing was fixed"
    assert issues["persistent"] == [] and issues["new"] == []


def test_a_finding_on_words_that_were_already_there_is_not_a_new_problem() -> None:
    before = _with_text(_draft([]), "I dont finished my homework.")
    after = _with_text(_draft([_issue("tense", "dont finished")]), "I dont finished my homework.")

    issues = revision_delta(after, before)["issues"]

    assert [item["fragment"] for item in issues["persistent"]] == ["dont finished"]
    assert issues["new"] == []


def test_words_the_revision_introduced_are_new() -> None:
    before = _with_text(_draft([]), "I have a dog.")
    after = _with_text(_draft([_issue("word_order", "dog a")]), "I have dog a.")

    assert [item["fragment"] for item in revision_delta(after, before)["issues"]["new"]] == ["dog a"]
