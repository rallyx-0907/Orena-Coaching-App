"""The learner's side of canonical Reading: adaptive practice on the corpus.

`/api/reading/practice/*`, over `ReadingEvidenceRepository`. The learner's
scope - account and learning language - comes from the request context the
app installs, never from the body.

* `GET  /next`               the next article, chosen by the selection policy
* `GET  /articles/{id}`      the approved set for one published article,
                             without its answers (404 when it is Free Reading)
* `POST /attempts`           submit answers - idempotent by `operation_id`;
                             answers with each question's key once saved
* `GET  /evidence`           the learner's canonical attempts, newest first
* `GET  /ability`            the ability projection under the current policy

**Learner submit is off until the complete live E2E has passed (D-076).**
`ORENA_READING_PRACTICE_SUBMIT=on` turns it on; anything else answers `503
reading_submit_disabled` and writes nothing. The reads work either way, so the
consumers can be verified against canonical evidence before any learner writes
it.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError

from writing_coach.core.errors import orena_http_error
from writing_coach.persistence.reading_evidence_repository import ReadingEvidenceRepository

router = APIRouter(prefix="/api/reading/practice", tags=["reading-practice"])
_logger = logging.getLogger(__name__)

SUBMIT_FLAG = "ORENA_READING_PRACTICE_SUBMIT"

_repository: ReadingEvidenceRepository | None = None
_support_language: Callable[[], str] | None = None
_submit_enabled: Callable[[], bool] = lambda: os.getenv(SUBMIT_FLAG, "").strip().casefold() == "on"  # noqa: E731


def configure_reading_practice(
    repository: ReadingEvidenceRepository | None,
    *,
    support_language: Callable[[], str] | None,
    submit_enabled: Callable[[], bool] | None = None,
) -> None:
    global _repository, _support_language, _submit_enabled
    _repository = repository
    _support_language = support_language
    if submit_enabled is not None:
        _submit_enabled = submit_enabled


def submit_enabled() -> bool:
    return bool(_submit_enabled())


def _repo() -> ReadingEvidenceRepository:
    if _repository is None:
        raise orena_http_error(503, "reading_practice_unavailable", "Reading practice is not available yet.")
    return _repository


def _support() -> str:
    return (_support_language() if _support_language else "").strip().casefold()


def _guarded(call: Callable[[], Any]) -> Any:
    try:
        return call()
    except SQLAlchemyError as exc:
        _logger.warning("reading practice: persistence unavailable", exc_info=True)
        raise orena_http_error(503, "reading_practice_unavailable", "Reading practice is not available yet.") from exc


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


class AttemptBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    set_id: str = Field(min_length=1, max_length=64)
    # One logical submit, reused by every retry of it - not one per HTTP try.
    operation_id: str = Field(min_length=1, max_length=120)
    # question id -> the chosen option index
    answers: dict[str, int] = Field(min_length=1, max_length=12)
    selection_policy_version: str | None = Field(default=None, max_length=40)


@router.get("/next")
def next_article(response: Response) -> dict[str, Any]:
    _no_store(response)
    choice = _guarded(lambda: _repo().next_article(support_language=_support()))
    return {"available": choice is not None, "next": choice, "submit_enabled": submit_enabled(),
            "support_language": _support()}


@router.get("/articles/{article_id}")
def article_set(article_id: str, response: Response) -> dict[str, Any]:
    _no_store(response)
    served = _guarded(lambda: _repo().served_set(article_id, support_language=_support()))
    if served is None:
        raise orena_http_error(404, "reading_set_not_available", "This article has no practice for you yet.")
    return {"set": served, "submit_enabled": submit_enabled(), "support_language": _support()}


@router.post("/attempts")
def submit_attempt(payload: AttemptBody, response: Response) -> dict[str, Any]:
    _no_store(response)
    if not submit_enabled():
        raise orena_http_error(
            503, "reading_submit_disabled",
            "Reading practice answers are not being saved yet.",
        )
    result = _guarded(lambda: _repo().submit_attempt(
        set_id=payload.set_id,
        operation_id=payload.operation_id,
        answers=payload.answers,
        support_language=_support(),
        selection_policy_version=payload.selection_policy_version,
    ))
    if result.status != "committed":
        status = 409 if result.reason == "operation_reused" else 422
        raise orena_http_error(status, f"reading_{result.reason}", "That answer sheet could not be saved.")
    attempt = result.attempt or {}
    key = _guarded(lambda: _repo().answer_key(str(attempt.get("set_id") or payload.set_id)))
    return {"status": "committed", "replayed": result.replayed, "attempt": attempt,
            "results": _results(attempt, key)}


def _results(attempt: dict[str, Any], key: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """One result per answered question, in the set's order: whether it was
    right, the correct option, the explanation (in the support language the set
    was written for) and the words of the passage that settle it."""
    out = []
    for answer in attempt.get("answers") or []:
        found = key.get(str(answer.get("question_id"))) or {}
        out.append({
            "question_id": answer.get("question_id"),
            "selected_index": answer.get("selected_index"),
            "correct": bool(answer.get("correct")),
            "correct_index": found.get("correct_index"),
            "explanation": found.get("explanation") or "",
            "evidence_fragment": found.get("evidence_text") or "",
        })
    return out


@router.get("/evidence")
def evidence(response: Response, limit: int = 20) -> dict[str, Any]:
    _no_store(response)
    return {"items": _guarded(lambda: _repo().list_evidence(limit))}


@router.get("/ability")
def ability(response: Response) -> dict[str, Any]:
    _no_store(response)
    return _guarded(lambda: _repo().ability())
