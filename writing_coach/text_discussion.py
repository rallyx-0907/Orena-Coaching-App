"""The learner's questions about a whole text, and the tutor's answers (D-072.2).

The shape here is the one four rounds of architecture review settled; the
reasoning lives in `docs/project/PROPOSAL_SAVED_REVIEWS_AND_TEXT_DISCUSSION.md`
and is not repeated. What a reader of this file needs to know:

- **Three transactions, not one.** Reserve the two ordinals and commit, ask the
  provider with no lock held, then write the pair. Holding the reservation open
  across a provider call would block every other submit on that thread for the
  whole provider latency.
- **Nothing gates on entitlement.** The turn is metered and never denied. Making
  this the product's first enforcing route is an activation decision the human
  has not taken, so `record_usage` runs and no plan is consulted.
- **Metering is ordered, not atomic.** `record_usage` owns its own transaction,
  so it runs after the turns are committed. An accepted turn writes one usage
  row; a refused, deduplicated or failed one writes none.
- **The answer is a tutor's answer.** The schema is one free-text field on
  purpose: a template ("You are asking about...") is not an answer to the
  question the learner asked. The passage is context the tutor may use, never a
  frame to fill in.
"""
from __future__ import annotations

import uuid
from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from writing_coach.ai.base import AICapabilityError, AIProviderError
from writing_coach.core.request_context import current_language_code, current_user_key
from writing_coach.persistence.discussion_repository import (
    MAX_BODY_CHARACTERS,
    MAX_TURNS,
    PAGE_LIMIT,
    SOURCE_KINDS,
    TextDiscussionRepository,
)

router = APIRouter(prefix="/api/texts", tags=["discussion"])

CAPABILITY = "text_discussion"
FEATURE = "reading.discussion_turn"

_repository: TextDiscussionRepository | None = None
_generate: Callable[..., Any] | None = None
_product_repository: Any | None = None
_profile: Callable[..., dict[str, Any]] | None = None


def install_text_discussion(
    *,
    repository: TextDiscussionRepository,
    generate_structured: Callable[..., Any],
    product_repository: Any,
    learner_profile: Callable[..., dict[str, Any]],
) -> APIRouter:
    global _repository, _generate, _product_repository, _profile
    _repository = repository
    _generate = generate_structured
    _product_repository = product_repository
    _profile = learner_profile
    return router


class TurnIn(BaseModel):
    source_kind: str
    source_id: str
    body: str = Field(min_length=1, max_length=MAX_BODY_CHARACTERS)
    context: str = Field(default="", max_length=MAX_BODY_CHARACTERS)
    request_id: str = Field(default="", max_length=64)


ANSWER_SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
}


def _support_language() -> str:
    profile = _profile() if _profile else {}
    return str((profile or {}).get("support_language") or "vi")


def _system_prompt(support_language: str, learning_language: str) -> str:
    return (
        "You are a patient language tutor helping a learner understand a text they are reading. "
        f"The learner is studying {learning_language} and you answer in {support_language}. "
        "Answer the question the learner actually asked, directly and in your own words. "
        "Use the passage only as evidence for your answer - never restate the question, never "
        "announce what the learner is asking about, and never answer with a fixed template. "
        f"Quote the {learning_language} exactly when you quote it. Be concise: a learner reads "
        "an answer, not an essay."
    )


def _user_prompt(question: str, passage: str, history: list[dict[str, Any]]) -> str:
    parts = []
    if passage.strip():
        parts.append(f"The passage the learner is looking at:\n{passage.strip()}")
    if history:
        earlier = "\n".join(
            f"{turn['role']}: {turn['body']}" for turn in history[-6:]
        )
        parts.append(f"Earlier in this conversation:\n{earlier}")
    parts.append(f"The learner asks:\n{question.strip()}")
    return "\n\n".join(parts)


def _require_repository() -> TextDiscussionRepository:
    if _repository is None:  # pragma: no cover - installed at startup
        raise HTTPException(503, "Text discussion is not available.")
    return _repository


def _validate_source(source_kind: str, source_id: str) -> None:
    if source_kind not in SOURCE_KINDS:
        raise HTTPException(400, "Unknown source kind.")
    if not str(source_id or "").strip():
        raise HTTPException(400, "A source id is required.")


@router.get("/discussion")
def read_discussion(
    source_kind: str, source_id: str, after_ordinal: int = 0, limit: int = PAGE_LIMIT
) -> dict[str, Any]:
    """The thread, or an empty one.

    Reads the two discussion tables only: it never joins to the source and never
    resolves the id against a catalogue, so a text that was withdrawn cannot
    fail a learner's own words.
    """
    _validate_source(source_kind, source_id)
    repository = _require_repository()
    thread = repository.find_discussion(source_kind=source_kind, source_id=source_id)
    if thread is None:
        return {
            "source_kind": source_kind,
            "source_id": source_id,
            "turns": [],
            "turn_count": 0,
            "max_turns": MAX_TURNS,
            "next_cursor": None,
        }
    turns = repository.list_turns(
        uuid.UUID(thread["id"]), after_ordinal=after_ordinal, limit=limit
    )
    return {
        **thread,
        "turns": turns,
        "max_turns": MAX_TURNS,
        "next_cursor": turns[-1]["ordinal"] if len(turns) >= min(limit, PAGE_LIMIT) else None,
    }


@router.post("/discussion/turns")
def add_turn(payload: TurnIn) -> dict[str, Any]:
    _validate_source(payload.source_kind, payload.source_id)
    repository = _require_repository()

    reading_session_id = None
    if payload.source_kind == "reading_session":
        # The routing identity is the per-user legacy id; the foreign key needs
        # the internal UUID. Not this learner's session is not found.
        reading_session_id = repository.resolve_reading_session(payload.source_id)
        if reading_session_id is None:
            raise HTTPException(404, "Reading session not found.")

    thread = repository.get_or_create_discussion(
        source_kind=payload.source_kind,
        source_id=payload.source_id,
        reading_session_id=reading_session_id,
    )
    discussion_id = uuid.UUID(thread["id"])

    if payload.request_id:
        repeated = repository.find_turns_by_request(discussion_id, payload.request_id)
        if repeated:
            # The same submission again: the existing exchange, unchanged. No
            # provider call and no usage row.
            return {**thread, "turns": repeated, "reused": True}

    reservation = repository.reserve_turns(discussion_id)
    if reservation.status == "missing":
        raise HTTPException(404, "Discussion not found.")
    if reservation.status == "cap_reached":
        raise HTTPException(
            409, f"This conversation has reached its limit of {MAX_TURNS} turns."
        )

    history = repository.list_turns(discussion_id, limit=PAGE_LIMIT)
    try:
        result = _generate(
            messages=[
                {
                    "role": "system",
                    "content": _system_prompt(_support_language(), current_language_code()),
                },
                {
                    "role": "user",
                    "content": _user_prompt(payload.body, payload.context, history),
                },
            ],
            schema=ANSWER_SCHEMA,
            max_output_tokens=800,
            temperature=0.3,
            capability_key=CAPABILITY,
        )
    except (AICapabilityError, AIProviderError):
        # Every provider was asked and none answered. The learner's question is
        # not stored as half an exchange and no answer is invented; the room
        # keeps the question and offers a retry. The reserved ordinals stay
        # unused, which the read path tolerates.
        raise HTTPException(
            503, "The tutor could not answer just now. Please try again."
        ) from None

    answer = str((result.data or {}).get("answer") or "").strip()
    if not answer:
        raise HTTPException(503, "The tutor could not answer just now. Please try again.")

    written = repository.append_turns(
        discussion_id,
        reservation,
        [
            {
                "ordinal": reservation.learner_ordinal,
                "role": "learner",
                "body": payload.body,
                "context": payload.context,
                "request_id": payload.request_id,
            },
            {
                "ordinal": reservation.assistant_ordinal,
                "role": "assistant",
                "body": answer[:MAX_BODY_CHARACTERS],
                # The provider that actually answered, which after a fallback is
                # not the configured primary.
                "provider": str(result.provider or ""),
                "model": str(result.model or ""),
            },
        ],
    )
    if written is None:
        # A repeat that was still in flight when this one started lost the
        # partial unique index. Its exchange is committed; return that.
        existing = repository.find_turns_by_request(discussion_id, payload.request_id)
        return {**thread, "turns": existing, "reused": True}

    _meter(payload.request_id)
    return {**thread, "turns": written, "reused": False}


def _meter(request_id: str) -> None:
    """After the turns are committed, never before.

    `record_usage` opens its own transaction, so it cannot be rolled back with
    the turn. Under-counting a reporting read that gates nothing is the cheaper
    error; over-counting would charge a learner for writing that was lost.
    """
    if _product_repository is None:  # pragma: no cover - installed at startup
        return
    try:
        _product_repository.record_usage(
            user_key=current_user_key(), feature=FEATURE, amount=1, request_id=request_id
        )
    except Exception:
        # Metering must never cost a learner their answer.
        return


@router.delete("/discussion")
def delete_discussion(source_kind: str, source_id: str) -> dict[str, bool]:
    _validate_source(source_kind, source_id)
    return {"deleted": _require_repository().delete_discussion(
        source_kind=source_kind, source_id=source_id
    )}


@router.get("/discussion/export")
def export_discussions() -> dict[str, Any]:
    """Every thread of this learner and language, for the account export."""
    return {"discussions": _require_repository().export_discussions()}
