"""A review is earned once, and every identical ask is free.

A writing review costs tokens on every call. Nothing about it is random: the
same words, judged against the same task at the same level, in the same two
languages, by the same evaluator contract, are the same review. So the only
honest number of provider calls for a given piece of writing is one - and a
reload, a second press, a second tab or twenty concurrent clients must all be
answered from what that one call produced.

These tests count provider calls. Claims about saving tokens are worth nothing
without that count, so the evaluator is replaced by a counter and the number is
asserted directly rather than inferred from a cache's existence.

They also hold the other half of the bargain: what must never reach a provider
at all. An oversized request is refused before a prompt is built, before a row
is written, and without the learner's writing appearing in the refusal.
"""
from __future__ import annotations

import concurrent.futures
import json
from typing import Any

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import app as app_module  # noqa: E402
from writing_coach.writing_limits import (  # noqa: E402
    MAX_BYTES,
    MAX_CHARACTERS,
    MAX_LINES,
)

LEARNER_TEXT = (
    "Hi Anna, I want to telling you about my last week. I go to the Da Nang "
    "office for a meeting with a customer and I dont finished the report."
)


class _CountingEvaluator:
    """Stands in for the provider, and remembers how often it was asked.

    Deliberately not a stub that returns a constant: each answer quotes the
    text it was given, so a reused answer can be told apart from a fresh one
    for different writing.
    """

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, payload: Any) -> dict[str, Any]:
        self.calls.append(payload.text)
        return {
            "grammar": 50.0,
            "vocabulary": 55.0,
            "coherence": 60.0,
            "task_achievement": 58.0,
            "naturalness": 52.0,
            "cefr_estimate": "B1",
            "summary_vi": f"Review #{len(self.calls)}",
            "strengths_vi": ["Clear enough."],
            "strength_evidence": [],
            "priorities_vi": ["Watch the past tense."],
            "errors": [
                {
                    "category": "tense",
                    "fragment": "I go to",
                    "correction": "I went to",
                    "explanation_vi": "Past event.",
                    "mini_rule_vi": "Use the past simple.",
                }
            ],
            "schema_version": "writing-evaluation-v2",
        }


@pytest.fixture()
def review(monkeypatch: pytest.MonkeyPatch, tmp_path) -> tuple[TestClient, _CountingEvaluator]:
    """A client whose evaluator is counted and whose essays are this test's own.

    The client is started before the essay store is swapped, so the
    application's own startup initializes the databases it expects; only the
    essays - what these tests count - are then redirected to a fresh file, so
    one test's stored reviews can never answer another test's request.
    """
    from writing_coach.persistence.learning_repository import SQLiteLearningRepository

    client = TestClient(app_module.app)
    client.__enter__()

    repository = SQLiteLearningRepository(lambda: tmp_path / "writing.db")
    repository.initialize()
    monkeypatch.setattr(app_module, "_learning_repository", repository)

    evaluator = _CountingEvaluator()
    monkeypatch.setattr(app_module, "evaluate_with_ai", evaluator)
    monkeypatch.setattr(app_module, "ALLOW_FALLBACK", False)
    monkeypatch.setattr(
        app_module, "get_learner_profile", lambda *a, **k: {"support_language": "vi"}
    )
    # Nothing may be left holding an identity from an earlier test.
    app_module._review_in_flight.clear()
    try:
        yield client, evaluator
    finally:
        client.__exit__(None, None, None)


def _ask(client: TestClient, text: str = LEARNER_TEXT, **extra: Any):
    body = {"prompt": "Email to a colleague", "text": text, "learning_language": "en"}
    body.update(extra)
    return client.post("/api/evaluate", json=body)


# --- One call, and then none --------------------------------------------


def test_the_first_review_calls_the_provider_once(review) -> None:
    client, evaluator = review
    answer = _ask(client)
    assert answer.status_code == 200
    assert len(evaluator.calls) == 1
    assert answer.json()["summary_vi"] == "Review #1"


def test_asking_for_the_same_review_again_costs_nothing(review) -> None:
    """The learner presses Review again without changing a word."""
    client, evaluator = review
    first = _ask(client).json()
    second = _ask(client).json()
    assert len(evaluator.calls) == 1, "a second identical ask must not reach the provider"
    assert second["id"] == first["id"], "it is the same evaluation, not a new row"
    assert second["reused"] is True
    assert second["summary_vi"] == first["summary_vi"]


def test_reopening_the_piece_costs_nothing(review) -> None:
    """What a reload does: read the series, find the review, render it."""
    client, evaluator = review
    created = _ask(client).json()
    reopened = client.get(f"/api/essays/{created['id']}")
    assert reopened.status_code == 200
    assert len(evaluator.calls) == 1, "reading a stored review must not evaluate anything"
    assert reopened.json()["summary_vi"] == created["summary_vi"]


def test_a_changed_revision_is_a_new_review(review) -> None:
    client, evaluator = review
    first = _ask(client).json()
    edited = _ask(client, text=LEARNER_TEXT + " Thank you, Linh.").json()
    assert len(evaluator.calls) == 2, "different words are a different review"
    assert edited["id"] != first["id"]
    assert edited["summary_vi"] == "Review #2"
    # And that new revision is itself reusable.
    again = _ask(client, text=LEARNER_TEXT + " Thank you, Linh.").json()
    assert len(evaluator.calls) == 2
    assert again["id"] == edited["id"]


# --- What counts as a different review ----------------------------------


def test_the_support_language_is_part_of_the_review(review, monkeypatch) -> None:
    """A Vietnamese review is not the answer for a learner reading Chinese.

    This is the failure a device-side guess could not prevent: every other
    field matches, so without the support language in the identity the stored
    Vietnamese answer would be served as current.
    """
    client, evaluator = review
    vietnamese = _ask(client).json()
    assert len(evaluator.calls) == 1

    monkeypatch.setattr(
        app_module, "get_learner_profile", lambda *a, **k: {"support_language": "zh"}
    )
    chinese = _ask(client).json()
    assert len(evaluator.calls) == 2, "the same words in another support language are a new review"
    assert chinese["id"] != vietnamese["id"]

    # And switching back reuses the Vietnamese one rather than buying it twice.
    monkeypatch.setattr(
        app_module, "get_learner_profile", lambda *a, **k: {"support_language": "vi"}
    )
    back = _ask(client).json()
    assert len(evaluator.calls) == 2
    assert back["id"] == vietnamese["id"]


def test_the_task_and_the_level_are_part_of_the_review(review) -> None:
    client, evaluator = review
    _ask(client)
    _ask(client, prompt="A lab report")
    assert len(evaluator.calls) == 2, "the same words written for a different task are judged again"
    _ask(client, target_cefr="C1")
    assert len(evaluator.calls) == 3, "and so is a different level"


def test_a_changed_evaluator_contract_retires_stored_reviews(review, monkeypatch) -> None:
    """A stored answer must not outlive the agreement that produced it.

    When the schema, the rubric or the prompt builder changes in a way that
    would produce a different answer, the contract version changes with it -
    and every stored identity stops matching, so reviews are earned again
    rather than served stale.
    """
    from writing_coach import writing_review_identity

    client, evaluator = review
    _ask(client)
    assert len(evaluator.calls) == 1

    monkeypatch.setattr(
        app_module,
        "review_identity",
        lambda **kw: writing_review_identity.review_identity(
            **{**kw, "contract_version": "writing-evaluation-v-next"}
        ),
    )
    assert _ask(client).status_code == 200
    assert len(evaluator.calls) == 2, "a new contract cannot reuse an old contract's answer"


# --- Twenty clients, one call -------------------------------------------


def test_concurrent_identical_reviews_make_one_provider_call(review) -> None:
    """Disabling a button stops one double-click and nothing else.

    Two tabs, a retry, a reload mid-flight or a direct client can all ask at
    once, and every one of them used to be a separate paid call.
    """
    client, evaluator = review
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        answers = [future.result() for future in [pool.submit(_ask, client) for _ in range(8)]]
    assert all(answer.status_code == 200 for answer in answers)
    assert len(evaluator.calls) == 1, f"one evaluation for one identity, got {len(evaluator.calls)}"
    identifiers = {answer.json()["id"] for answer in answers}
    assert len(identifiers) == 1, "and every caller is answered from it"


# --- What never reaches a provider at all -------------------------------


@pytest.mark.parametrize(
    ("label", "text"),
    (
        ("one character over", "a" * (MAX_CHARACTERS + 1)),
        ("one enormous line", "x" * (MAX_CHARACTERS + 5_000)),
        ("newline heavy", "\n" * (MAX_LINES + 10)),
        ("chinese over the character bound", "漢" * (MAX_CHARACTERS + 1)),
        ("vietnamese over the character bound", "ề" * (MAX_CHARACTERS + 1)),
        ("emoji over the character bound", "🙂" * (MAX_CHARACTERS + 1)),
    ),
)
def test_oversized_writing_never_reaches_the_provider_or_the_store(review, label, text) -> None:
    client, evaluator = review
    before = len(app_module._learning_repository.list_essays(500))
    answer = _ask(client, text=text)
    assert answer.status_code in (413, 422), f"{label}: expected a refusal"
    assert evaluator.calls == [], f"{label}: nothing may be spent on it"
    after = len(app_module._learning_repository.list_essays(500))
    assert after == before, f"{label}: nothing may be written for it"


def test_a_refusal_does_not_carry_the_learners_writing(review) -> None:
    """An over-long essay must not be echoed back, or into a log through it."""
    client, _ = review
    distinctive = "Xin chào, đây là bài viết rất dài của tôi. " * 400
    answer = _ask(client, text=distinctive)
    assert answer.status_code in (413, 422)
    body = answer.text
    assert "Xin chào, đây là bài viết" not in body, "the refusal is a measurement, not a copy"
    assert len(body) < 2_000, "and it is small whatever was sent"


def test_a_body_larger_than_writing_is_refused_before_it_is_parsed(review) -> None:
    client, _ = review
    oversized = json.dumps(
        {"prompt": "note", "text": "a" * (4 * MAX_BYTES), "learning_language": "en"}
    )
    answer = client.post(
        "/api/evaluate",
        content=oversized.encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    assert answer.status_code == 413
    assert answer.json()["detail"]["category"] == "writing_too_large"


def test_writing_at_the_limit_is_accepted(review) -> None:
    """The bound is a bound, not a margin: what fits must work."""
    client, evaluator = review
    at_the_limit = "a" * MAX_CHARACTERS
    answer = _ask(client, text=at_the_limit)
    assert answer.status_code == 200
    assert len(evaluator.calls) == 1


def test_multibyte_writing_is_measured_by_what_it_is_not_by_its_bytes(review) -> None:
    """A Chinese essay is not three times shorter than an English one."""
    client, evaluator = review
    chinese = "漢" * (MAX_CHARACTERS // 2)
    assert len(chinese.encode("utf-8")) > MAX_CHARACTERS
    answer = _ask(client, text=chinese)
    assert answer.status_code == 200, "half the character bound fits, whatever it costs in bytes"
    assert len(evaluator.calls) == 1
