"""`/api/vocabulary/decks` - the learner's own study sets.

A **Deck** is a learning/review set that belongs to Vocabulary. A **My Library
Collection** organises items inside My Library. The human settled on
2026-09-23 that these are two different things, and this module is the
Vocabulary one.

Until `migrations/proposed/20260923_0014_vocabulary_decks.py` has passed
independent architecture review and been applied, the tables do not exist and
every route here answers `503 decks_unavailable`. That is deliberate: the
screens are **not** wired back to `library_collections`, because shipping the
wrong domain again to keep a screen green would be the worse failure.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

from writing_coach.core.errors import orena_http_error
from writing_coach.persistence.deck_repository import DeckConflict, DeckRepository
from writing_coach.persistence.models import DECK_COVERS

router = APIRouter(prefix="/api/vocabulary", tags=["vocabulary-decks"])

_decks: Callable[[], DeckRepository | None] | None = None


def configure_decks(factory: Callable[[], DeckRepository | None] | None) -> None:
    global _decks
    _decks = factory


def _repo() -> DeckRepository:
    found = _decks() if _decks is not None else None
    if found is None or not found.available():
        raise orena_http_error(
            503,
            "decks_unavailable",
            "Study sets are not available on this server yet.",
        )
    return found


class DeckIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    cover: str = Field(default="violet")

    @field_validator("title")
    @classmethod
    def _trim(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("A set needs a name.")
        return trimmed

    @field_validator("cover")
    @classmethod
    def _known_cover(cls, value: str) -> str:
        # The palette is the theme's. A cover this server does not know is a
        # refusal, not a silent default - a learner would otherwise pick a
        # colour and be given another.
        if value not in DECK_COVERS:
            raise ValueError(f"Unknown cover: {value!r}")
        return value


class DeckPatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    title: str | None = Field(default=None, max_length=120)
    cover: str | None = Field(default=None)

    @field_validator("cover")
    @classmethod
    def _known_cover(cls, value: str | None) -> str | None:
        if value is not None and value not in DECK_COVERS:
            raise ValueError(f"Unknown cover: {value!r}")
        return value


class DeckWordIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    word: str = Field(min_length=1, max_length=180)


def _conflict(error: DeckConflict) -> None:
    status = 409 if error.reason in {"stale", "duplicate_title"} else 404
    raise orena_http_error(status, error.reason, str(error))


@router.get("/decks", name="orena_vocabulary_decks")
def list_decks() -> dict[str, Any]:
    """The learner's sets in the language they are learning, with their sizes."""

    return {"items": _repo().list_decks(), "covers": list(DECK_COVERS)}


@router.post("/decks", name="orena_vocabulary_deck_create", status_code=201)
def create_deck(payload: DeckIn) -> dict[str, Any]:
    try:
        return {"deck": _repo().create(title=payload.title, cover=payload.cover)}
    except DeckConflict as error:
        _conflict(error)


@router.patch("/decks/{deck_id}", name="orena_vocabulary_deck_patch")
def patch_deck(deck_id: str, payload: DeckPatchIn) -> dict[str, Any]:
    """Rename a set or change its cover, against the version it was read at."""

    try:
        return {
            "deck": _repo().update(
                deck_id,
                expected_version=payload.expected_version,
                title=payload.title,
                cover=payload.cover,
            )
        }
    except DeckConflict as error:
        _conflict(error)


@router.delete("/decks/{deck_id}", name="orena_vocabulary_deck_delete")
def delete_deck(deck_id: str) -> dict[str, Any]:
    """Forget a set. The words in it are the learner's and stay theirs."""

    return {"deleted": _repo().delete(deck_id)}


@router.get("/decks/{deck_id}/words", name="orena_vocabulary_deck_words")
def deck_words(deck_id: str, limit: int = Query(default=200, ge=1, le=500)) -> dict[str, Any]:
    try:
        return {"items": _repo().words(deck_id, limit=limit)}
    except DeckConflict as error:
        _conflict(error)


@router.post("/decks/{deck_id}/words", name="orena_vocabulary_deck_add")
def add_word(deck_id: str, payload: DeckWordIn) -> dict[str, Any]:
    """Put one of the learner's saved words into a set.

    The word must already be saved: a set is a set of the learner's words, and
    this route does not save one as a side effect - the surface saves, then
    files, so a failure to file never leaves a word half-kept.
    """

    try:
        return {"added": _repo().add_word(deck_id, payload.word)}
    except DeckConflict as error:
        _conflict(error)


@router.delete("/decks/{deck_id}/words/{word}", name="orena_vocabulary_deck_remove")
def remove_word(deck_id: str, word: str) -> dict[str, Any]:
    try:
        return {"removed": _repo().remove_word(deck_id, word)}
    except DeckConflict as error:
        _conflict(error)
