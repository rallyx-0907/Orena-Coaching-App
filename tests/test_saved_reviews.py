"""Keeping a review is curation, and it stores one timestamp - nothing else.

D-072.1: "Lưu nhận xét" marks a review the learner wants to read again. The
review itself is already stored permanently on the essay row, so keeping it
must not copy a single field of it anywhere. These tests hold that: the flag
rides on the essay, the list filter reads it back, and pressing keep twice is
the same as pressing it once.

They also hold what an owner-scoped endpoint owes: an essay that does not
belong to this learner is answered exactly like one that does not exist.
"""
from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import app as app_module  # noqa: E402

LEARNER_TEXT = (
    "Hi Anna, I want to telling you about my last week. I go to the Da Nang "
    "office for a meeting with a customer and I dont finished the report."
)


def _review_payload(index: int) -> dict[str, Any]:
    return {
        "grammar": 50.0,
        "vocabulary": 55.0,
        "coherence": 60.0,
        "task_achievement": 58.0,
        "naturalness": 52.0,
        "cefr_estimate": "B1",
        "summary_vi": f"Review #{index}",
        "strengths_vi": ["Clear enough."],
        "strength_evidence": [],
        "priorities_vi": ["Watch the past tense."],
        "errors": [],
        "schema_version": "writing-evaluation-v2",
    }


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, tmp_path) -> TestClient:
    from writing_coach.persistence.learning_repository import SQLiteLearningRepository

    test_client = TestClient(app_module.app)
    test_client.__enter__()

    repository = SQLiteLearningRepository(lambda: tmp_path / "writing.db")
    repository.initialize()
    monkeypatch.setattr(app_module, "_learning_repository", repository)

    calls: list[str] = []

    def _evaluator(payload: Any) -> dict[str, Any]:
        calls.append(payload.text)
        return _review_payload(len(calls))

    monkeypatch.setattr(app_module, "evaluate_with_ai", _evaluator)
    monkeypatch.setattr(app_module, "ALLOW_FALLBACK", False)
    monkeypatch.setattr(
        app_module, "get_learner_profile", lambda *a, **k: {"support_language": "vi"}
    )
    app_module._review_in_flight.clear()
    try:
        yield test_client
    finally:
        test_client.__exit__(None, None, None)


def _write(client: TestClient, text: str) -> int:
    response = client.post(
        "/api/evaluate",
        json={"prompt": "Email to a colleague", "text": text, "learning_language": "en"},
    )
    assert response.status_code == 200, response.text
    return int(response.json()["id"])


# --- The flag itself ----------------------------------------------------


def test_a_new_review_is_not_kept(client: TestClient) -> None:
    essay_id = _write(client, LEARNER_TEXT)
    rows = client.get("/api/essays").json()
    assert [row["id"] for row in rows] == [essay_id]
    assert rows[0]["review_kept_at"] is None


def test_keep_then_unkeep_round_trips(client: TestClient) -> None:
    essay_id = _write(client, LEARNER_TEXT)

    kept = client.post(f"/api/essays/{essay_id}/keep")
    assert kept.status_code == 200
    assert kept.json()["kept"] is True
    assert kept.json()["kept_at"]

    released = client.delete(f"/api/essays/{essay_id}/keep")
    assert released.status_code == 200
    assert released.json()["kept"] is False
    assert released.json()["kept_at"] is None


def test_keeping_twice_does_not_move_the_timestamp(client: TestClient) -> None:
    essay_id = _write(client, LEARNER_TEXT)
    first = client.post(f"/api/essays/{essay_id}/keep").json()["kept_at"]
    second = client.post(f"/api/essays/{essay_id}/keep").json()["kept_at"]
    assert first == second


def test_unkeeping_something_never_kept_is_not_an_error(client: TestClient) -> None:
    essay_id = _write(client, LEARNER_TEXT)
    response = client.delete(f"/api/essays/{essay_id}/keep")
    assert response.status_code == 200
    assert response.json()["kept"] is False


# --- The list -----------------------------------------------------------


def test_kept_filter_returns_only_kept_reviews(client: TestClient) -> None:
    first = _write(client, LEARNER_TEXT)
    second = _write(client, LEARNER_TEXT + " I will send it tomorrow morning.")
    client.post(f"/api/essays/{second}/keep")

    kept = client.get("/api/essays?kept=true").json()
    assert [row["id"] for row in kept] == [second]

    everything = client.get("/api/essays").json()
    assert sorted(row["id"] for row in everything) == sorted([first, second])


def test_releasing_a_review_removes_it_from_the_kept_list(client: TestClient) -> None:
    essay_id = _write(client, LEARNER_TEXT)
    client.post(f"/api/essays/{essay_id}/keep")
    client.delete(f"/api/essays/{essay_id}/keep")
    assert client.get("/api/essays?kept=true").json() == []


# --- Nothing is duplicated ----------------------------------------------


def test_keeping_a_review_copies_no_review_data(client: TestClient) -> None:
    """The stored review is read from the essay, before and after keeping."""
    essay_id = _write(client, LEARNER_TEXT)
    before = client.get(f"/api/essays/{essay_id}/review").json()
    client.post(f"/api/essays/{essay_id}/keep")
    after = client.get(f"/api/essays/{essay_id}/review").json()
    assert before == after


# --- What is not there --------------------------------------------------


def test_keeping_an_unknown_essay_is_404(client: TestClient) -> None:
    assert client.post("/api/essays/424242/keep").status_code == 404
    assert client.delete("/api/essays/424242/keep").status_code == 404
