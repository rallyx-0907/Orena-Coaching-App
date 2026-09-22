"""What the discussion endpoint owes a learner who asks about a text.

The persistence itself is PostgreSQL-only, so these tests drive the endpoint
against a fake repository that keeps the same contract - the reservation, the
dedup lookup and the three-step write - and assert the behaviour the endpoint
is responsible for rather than the storage:

- an accepted turn is metered exactly once, and a refused, deduplicated or
  failed one is not metered at all;
- a repeated `request_id` returns the existing exchange and never asks a
  provider twice;
- the cap answers 409, a foreign or missing thread answers 404, and neither
  reaches a provider;
- when no provider can answer, the learner's question is not stored as half an
  exchange and no answer is invented;
- after a fallback, the turn records the provider that actually answered.

The SQLite refusal is asserted directly: CI's backend must never quietly become
a second store for a learner's conversation.
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from writing_coach.ai.base import AIProviderUnavailable, AIResult  # noqa: E402
from writing_coach.persistence.discussion_repository import (  # noqa: E402
    MAX_TURNS,
    Reservation,
    SQLiteTextDiscussionRepository,
)
from writing_coach.text_discussion import install_text_discussion  # noqa: E402

THREAD_ID = uuid.uuid4()


class _FakeRepository:
    """The same contract the PostgreSQL repository implements, in memory."""

    def __init__(self) -> None:
        self.turn_count = 0
        self.turns: list[dict[str, Any]] = []
        self.session_exists = True
        self.append_conflicts = False
        self.reservations: list[Reservation] = []

    def resolve_reading_session(self, source_id: str) -> uuid.UUID | None:
        return uuid.uuid4() if self.session_exists else None

    def _thread(self) -> dict[str, Any]:
        return {
            "id": str(THREAD_ID),
            "source_kind": "story",
            "source_id": "story:borrowed-table",
            "language_code": "en",
            "reading_session_id": None,
            "turn_count": self.turn_count,
            "created_at": "2026-09-22T00:00:00+00:00",
            "updated_at": "2026-09-22T00:00:00+00:00",
        }

    def get_or_create_discussion(self, **_: Any) -> dict[str, Any]:
        return self._thread()

    def find_discussion(self, **_: Any) -> dict[str, Any] | None:
        return self._thread() if self.turns else None

    def list_turns(self, discussion_id: uuid.UUID, *, after_ordinal: int = 0, limit: int = 100):
        return [t for t in self.turns if t["ordinal"] > after_ordinal][:limit]

    def find_turns_by_request(self, discussion_id: uuid.UUID, request_id: str):
        if not request_id:
            return []
        learner = next((t for t in self.turns if t.get("request_id") == request_id), None)
        if learner is None:
            return []
        return [
            t
            for t in self.turns
            if learner["ordinal"] <= t["ordinal"] <= learner["ordinal"] + 1
        ]

    def reserve_turns(self, discussion_id: uuid.UUID) -> Reservation:
        if self.turn_count > MAX_TURNS - 2:
            reservation = Reservation("cap_reached")
        else:
            self.turn_count += 2
            reservation = Reservation(
                "granted", discussion_id, self.turn_count - 1, self.turn_count
            )
        self.reservations.append(reservation)
        return reservation

    def append_turns(self, discussion_id, reservation, turns):
        if self.append_conflicts:
            return None
        written = []
        for turn in turns:
            row = {
                "ordinal": turn["ordinal"],
                "role": turn["role"],
                "body": turn["body"],
                "context": turn.get("context", ""),
                "provider": turn.get("provider", ""),
                "model": turn.get("model", ""),
                "request_id": turn.get("request_id", ""),
                "created_at": "2026-09-22T00:00:00+00:00",
            }
            self.turns.append(row)
            written.append(row)
        return written

    def delete_discussion(self, **_: Any) -> bool:
        deleted = bool(self.turns)
        self.turns.clear()
        self.turn_count = 0
        return deleted

    def export_discussions(self):
        return [{**self._thread(), "turns": list(self.turns)}]


class _MissingThreadRepository(_FakeRepository):
    def reserve_turns(self, discussion_id: uuid.UUID) -> Reservation:
        return Reservation("missing")


class _CountingMeter:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def record_usage(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


def _answering(text: str = "The narrator is remembering, not describing.", provider="gemini"):
    def generate(**_: Any) -> AIResult:
        return AIResult(data={"answer": text}, provider=provider, model="gemini-3.5-flash-lite", runtime={})

    return generate


def _failing(**_: Any) -> AIResult:
    raise AIProviderUnavailable("every provider is down")


@pytest.fixture()
def harness():
    repository = _FakeRepository()
    meter = _CountingMeter()

    def build(generate=None, repo=None):
        app = FastAPI()
        app.include_router(
            install_text_discussion(
                repository=repo or repository,
                generate_structured=generate or _answering(),
                product_repository=meter,
                learner_profile=lambda *a, **k: {"support_language": "vi"},
            )
        )
        return TestClient(app)

    return build, repository, meter


def _ask(client: TestClient, **extra: Any):
    body = {
        "source_kind": "story",
        "source_id": "story:borrowed-table",
        "body": "Why is this sentence in the past perfect?",
    }
    body.update(extra)
    return client.post("/api/texts/discussion/turns", json=body)


# --- The exchange -------------------------------------------------------


def test_an_answered_question_stores_both_turns_in_order(harness) -> None:
    build, repository, _ = harness
    response = _ask(build())
    assert response.status_code == 200
    turns = response.json()["turns"]
    assert [t["role"] for t in turns] == ["learner", "assistant"]
    assert [t["ordinal"] for t in turns] == [1, 2]


def test_the_turn_records_the_provider_that_actually_answered(harness) -> None:
    """After a fallback that is not the configured primary."""
    build, _, _ = harness
    response = _ask(build(generate=_answering(provider="ollama")))
    assistant = response.json()["turns"][1]
    assert assistant["provider"] == "ollama"
    assert assistant["model"] == "gemini-3.5-flash-lite"


def test_an_empty_thread_reads_back_as_empty_not_as_an_error(harness) -> None:
    build, _, _ = harness
    response = build().get(
        "/api/texts/discussion",
        params={"source_kind": "story", "source_id": "story:borrowed-table"},
    )
    assert response.status_code == 200
    assert response.json()["turns"] == []
    assert response.json()["turn_count"] == 0


# --- Metering -----------------------------------------------------------


def test_an_accepted_turn_is_metered_exactly_once(harness) -> None:
    build, _, meter = harness
    _ask(build())
    assert len(meter.calls) == 1
    assert meter.calls[0]["feature"] == "reading.discussion_turn"
    assert meter.calls[0]["amount"] == 1


def test_nothing_is_metered_when_no_provider_answers(harness) -> None:
    build, _, meter = harness
    response = _ask(build(generate=_failing))
    assert response.status_code == 503
    assert meter.calls == []


def test_nothing_is_metered_when_the_cap_refuses(harness) -> None:
    build, repository, meter = harness
    repository.turn_count = MAX_TURNS
    response = _ask(build())
    assert response.status_code == 409
    assert meter.calls == []


def test_a_repeated_request_is_not_metered_again(harness) -> None:
    build, _, meter = harness
    client = build()
    _ask(client, request_id="abc-123")
    _ask(client, request_id="abc-123")
    assert len(meter.calls) == 1


# --- Idempotency --------------------------------------------------------


def test_a_repeated_request_id_returns_the_same_exchange(harness) -> None:
    build, _, _ = harness
    client = build()
    first = _ask(client, request_id="abc-123").json()
    second = _ask(client, request_id="abc-123").json()
    assert second["reused"] is True
    assert second["turns"] == first["turns"]


def test_a_repeated_request_id_never_asks_a_provider_twice(harness) -> None:
    build, _, _ = harness
    calls: list[int] = []

    def generate(**_: Any) -> AIResult:
        calls.append(1)
        return AIResult(data={"answer": "once"}, provider="gemini", model="m", runtime={})

    client = build(generate=generate)
    _ask(client, request_id="abc-123")
    _ask(client, request_id="abc-123")
    assert len(calls) == 1


def test_a_duplicate_that_was_still_in_flight_returns_the_committed_exchange(harness) -> None:
    """The loser of the partial unique index reads the winner's turns back."""
    build, repository, _ = harness
    client = build()
    _ask(client, request_id="abc-123")
    repository.append_conflicts = True
    response = _ask(client, request_id="abc-123")
    assert response.status_code == 200
    assert response.json()["reused"] is True


# --- Refusals -----------------------------------------------------------


def test_the_cap_answers_409_and_names_the_limit(harness) -> None:
    build, repository, _ = harness
    repository.turn_count = MAX_TURNS
    response = _ask(build())
    assert response.status_code == 409
    assert str(MAX_TURNS) in response.json()["detail"]


def test_a_thread_that_is_not_this_learners_is_404(harness) -> None:
    build, _, _ = harness
    response = _ask(build(repo=_MissingThreadRepository()))
    assert response.status_code == 404


def test_a_reading_session_that_is_not_this_learners_is_404(harness) -> None:
    build, repository, meter = harness
    repository.session_exists = False
    response = _ask(build(), source_kind="reading_session", source_id="7")
    assert response.status_code == 404
    assert meter.calls == []


def test_an_unknown_source_kind_is_refused_before_anything_is_written(harness) -> None:
    build, repository, _ = harness
    response = _ask(build(), source_kind="podcast")
    assert response.status_code == 400
    assert repository.turns == []


def test_an_empty_question_is_refused_by_validation(harness) -> None:
    build, _, meter = harness
    response = _ask(build(), body="")
    assert response.status_code == 422
    assert meter.calls == []


# --- When nobody can answer ---------------------------------------------


def test_no_answer_is_invented_and_no_half_exchange_is_stored(harness) -> None:
    build, repository, _ = harness
    response = _ask(build(generate=_failing))
    assert response.status_code == 503
    assert repository.turns == []


def test_the_learner_is_not_shown_the_provider_error(harness) -> None:
    build, _, _ = harness
    response = _ask(build(generate=_failing))
    assert "provider" not in response.json()["detail"].casefold()
    assert "429" not in response.json()["detail"]


def test_an_empty_answer_is_treated_as_no_answer(harness) -> None:
    build, repository, meter = harness
    response = _ask(build(generate=_answering(text="   ")))
    assert response.status_code == 503
    assert repository.turns == []
    assert meter.calls == []


# --- Clearing and export ------------------------------------------------


def test_the_learner_can_clear_their_own_thread(harness) -> None:
    build, repository, _ = harness
    client = build()
    _ask(client)
    response = client.request(
        "DELETE",
        "/api/texts/discussion",
        params={"source_kind": "story", "source_id": "story:borrowed-table"},
    )
    assert response.json() == {"deleted": True}
    assert repository.turns == []


def test_the_export_carries_the_turns_in_order(harness) -> None:
    build, _, _ = harness
    client = build()
    _ask(client)
    exported = client.get("/api/texts/discussion/export").json()["discussions"]
    assert [t["ordinal"] for t in exported[0]["turns"]] == [1, 2]


# --- The test backend stores nothing ------------------------------------


def test_sqlite_refuses_rather_than_storing_learner_conversation() -> None:
    repository = SQLiteTextDiscussionRepository()
    with pytest.raises(RuntimeError, match="PostgreSQL runtime"):
        repository.get_or_create_discussion(source_kind="story", source_id="x")
    with pytest.raises(RuntimeError, match="PostgreSQL runtime"):
        repository.export_discussions()
