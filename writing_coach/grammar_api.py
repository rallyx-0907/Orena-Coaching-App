"""Learner routes of the grammar content store (`/api/grammar/v1/*`, GRAMMAR_CONTENT_STORE.md rev 3a sections 7-11).

Published content only, in the session's language, through the whitelist of `contract.served_point`. Progress reuses
`grammar_progress` through the learning repository (no new learner table): completion and the quiz result are one
statement, the server re-checks the posted picks against the published key and stores its own arithmetic, and an old
R5 completion counts for a point only through the R5 map's primary rows (a merged point needs ALL its R5 ids).

Until the migration is applied, every route answers `503 grammar_store_unavailable`.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from writing_coach.core.errors import orena_http_error
from writing_coach.core.request_context import current_language_code
from writing_coach.grammar_store import contract
from writing_coach.persistence.grammar_store_repository import (
    GrammarStoreRefusal,
    GrammarStoreRepository,
    parse_r5_key,
)

router = APIRouter(prefix="/api/grammar/v1", tags=["grammar"])
_logger = logging.getLogger(__name__)
UNAVAILABLE = "grammar_store_unavailable"
CLAIM = "activity_evidence_not_mastery"


@dataclass
class _Learner:
    store: GrammarStoreRepository | None = None
    progress: Any = None  # the learning repository (completed_grammar_ids / get / record / unset)
    language: Callable[[], str] = current_language_code


_state = _Learner()


def configure_grammar_api(store: GrammarStoreRepository | None, progress: Any = None, *,
                          language: Callable[[], str] = current_language_code) -> None:
    global _state
    _state = _Learner(store=store, progress=progress, language=language)


def _store() -> GrammarStoreRepository:
    if _state.store is None:
        raise orena_http_error(503, UNAVAILABLE, "Grammar is not available yet.")
    return _state.store


def _language() -> str:
    language = str(_state.language() or "").casefold()
    if language not in contract.APP_LANGUAGES:
        raise orena_http_error(404, "grammar_language_unsupported", "Grammar is not available for this language yet.")
    return language


def _guarded(call: Callable[[], Any]) -> Any:
    try:
        return call()
    except HTTPException:
        raise
    except GrammarStoreRefusal as refusal:
        raise orena_http_error(refusal.status, refusal.code, refusal.message, context=refusal.context) from refusal
    except SQLAlchemyError as exc:
        _logger.warning("grammar api: store not ready", exc_info=True)
        raise orena_http_error(503, UNAVAILABLE, "Grammar is not available yet.") from exc


def _cache(response: Response, etag: str) -> None:
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "private, no-cache"


def _not_modified(request: Request, etag: str) -> bool:
    sent = request.headers.get("if-none-match", "")
    return any(tag.strip() == etag for tag in sent.split(",")) if sent else False


def _check_language(point_id: str, language: str) -> None:
    head = point_id.split(".", 1)[0] if "." in point_id else ""
    if head in contract.APP_LANGUAGES and head != language:
        raise orena_http_error(404, "grammar_language_mismatch", "That grammar point is in another language.")


# -- content ------------------------------------------------------------------------------------------------------------


@router.get("/points")
def points(request: Request, response: Response, level: str | None = Query(None, max_length=20)):
    language = _language()
    catalog = _guarded(lambda: _store().catalog(language, level=level))
    etag = f'W/"{language}-{catalog["catalog_revision"]}{"-" + level if level else ""}"'
    if _not_modified(request, etag):
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": "private, no-cache"})
    _cache(response, etag)
    return catalog


@router.get("/points/{point_id}")
def point(point_id: str, request: Request, response: Response):
    language = _language()
    _check_language(point_id, language)
    store = _store()
    published = _guarded(lambda: store.published(language, point_id))
    if published is not None:
        etag = f'"{published["content_hash"]}"'
        if _not_modified(request, etag):
            return Response(status_code=304, headers={"ETag": etag, "Cache-Control": "private, no-cache"})
        _cache(response, etag)
        return {"language": language, **published}
    resolved = _guarded(lambda: store.resolve_r5(language, point_id))
    if resolved is not None:
        response.headers["Cache-Control"] = "private, no-cache"
        return {"language": language, **resolved}
    raise orena_http_error(404, "grammar_point_not_found", "No published grammar point has that id.")


@router.get("/by-error")
def by_error(
    error_tag: str = Query(..., min_length=1, max_length=80),
    level: str | None = Query(None, max_length=20),
    limit: int = Query(3, ge=1, le=20),
) -> dict:
    language = _language()
    store = _store()

    def run() -> list[dict]:
        rank = None
        if level:
            levels = {row["value"]: row["rank"] for row in store.catalog(language)["levels"]}
            rank = levels.get(level)
        return store.by_error(language, error_tag, level_rank=rank, limit=limit)

    return {"language": language, "error_tag": error_tag, "points": _guarded(run)}


# -- progress (section 8) -----------------------------------------------------------------------------------------------


def _progress_repo():
    if _state.progress is None:
        raise orena_http_error(503, UNAVAILABLE, "Grammar progress is not available yet.")
    return _state.progress


def _quiz(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row or row.get("last_quiz_total") is None:
        return None
    return {"correct": row["last_quiz_correct"], "total": row["last_quiz_total"], "at": row["last_quiz_at"]}


def _r5_keys(completed: set[str], language: str) -> dict[str, list[str]]:
    """bare R5 id -> the stored keys (bare or composite) that complete it."""
    out: dict[str, list[str]] = {}
    for key in sorted(completed):
        r5_id = parse_r5_key(key, language)
        if r5_id:
            out.setdefault(r5_id, []).append(key)
    return out


def _completion(point_id: str, completed: set[str], r5_keys: dict[str, list[str]],
                primaries: list[str]) -> tuple[str, list[str]] | None:
    """('own', [point_id]) or ('r5', stored keys) or None. A merged point needs all its R5 ids (D-106.4)."""
    if point_id in completed:
        return "own", [point_id]
    if primaries and all(r5 in r5_keys for r5 in primaries):
        return "r5", [key for r5 in primaries for key in r5_keys[r5]]
    return None


def _entry(repo, point_id: str, via: str, keys: list[str], primaries: list[str]) -> dict[str, Any]:
    rows = [row for row in (repo.get_grammar_progress(key) for key in keys) if row]
    first = min((row["completed_at"] for row in rows), default=None)
    latest_quiz = max((row for row in rows if row.get("last_quiz_at")), key=lambda r: r["last_quiz_at"], default=None)
    entry = {"point_id": point_id, "completed_at": first, "last_quiz": _quiz(latest_quiz), "via": via}
    if via == "r5":
        entry["r5_ids"] = primaries
    return entry


@router.get("/progress")
def progress() -> dict:
    language = _language()
    store, repo = _store(), _progress_repo()

    def run() -> list[dict[str, Any]]:
        completed = set(repo.completed_grammar_ids())
        r5_keys = _r5_keys(completed, language)
        primaries = store.progress_map(language)
        out = []
        for point_id in sorted(store.published_ids(language)):
            hit = _completion(point_id, completed, r5_keys, primaries.get(point_id, []))
            if hit:
                out.append(_entry(repo, point_id, hit[0], hit[1], primaries.get(point_id, [])))
        return out

    return {"language": language, "progress": _guarded(run), "claim": CLAIM}


class ProgressBody(BaseModel):
    answers: list[int | None] | None = Field(None, max_length=20)


def _published_or_refuse(store: GrammarStoreRepository, language: str, point_id: str) -> dict[str, Any]:
    _check_language(point_id, language)
    published = store.published(language, point_id)
    if published is not None:
        return published
    resolved = store.resolve_r5(language, point_id)
    if resolved is not None:  # writes never target an alias: answer where the point lives now
        raise orena_http_error(409, "grammar_point_moved", "Progress is recorded on the current point.",
                               context=resolved)
    raise orena_http_error(404, "grammar_point_not_found", "No published grammar point has that id.")


@router.put("/progress/{point_id}")
def record_progress(point_id: str, body: ProgressBody | None = None) -> dict:
    language = _language()
    store, repo = _store(), _progress_repo()
    published = _guarded(lambda: _published_or_refuse(store, language, point_id))
    quiz = None
    answers = body.answers if body is not None else None
    if answers is not None:
        items = published["point"]["quick_practice"]
        if len(answers) != len(items):
            raise orena_http_error(422, "grammar_answers_invalid", f"Expected {len(items)} answers.")
        for pick, item in zip(answers, items, strict=True):
            if pick is not None and not 0 <= pick < len(item["options"]):
                raise orena_http_error(422, "grammar_answers_invalid", "An answer names no option.")
        # The server's own arithmetic from the published key; a client-supplied score is never accepted.
        quiz = {"correct": sum(1 for pick, item in zip(answers, items, strict=True) if pick == item["answer"]),
                "total": len(items)}
    now = datetime.now(UTC).isoformat()
    saved = repo.record_grammar_completion(point_id, now, quiz)
    return {"point_id": point_id, "completed": True, "completed_at": saved.get("completed_at", now),
            "last_quiz": _quiz(saved), "claim": CLAIM}


@router.delete("/progress/{point_id}")
def delete_progress(point_id: str) -> dict:
    """The learner's own un-completion: the point-id row and the R5 rows that make it read as completed."""
    language = _language()
    store, repo = _store(), _progress_repo()
    _check_language(point_id, language)

    def run() -> bool:
        completed = set(repo.completed_grammar_ids())
        primaries = store.progress_map(language, [point_id]).get(point_id, [])
        keys = [point_id] if point_id in completed else []
        r5_keys = _r5_keys(completed, language)
        keys += [key for r5 in primaries for key in r5_keys.get(r5, [])]
        changed = False
        for key in keys:
            changed = repo.unset_grammar_completed(key) or changed
        return changed

    return {"point_id": point_id, "changed": _guarded(run)}
