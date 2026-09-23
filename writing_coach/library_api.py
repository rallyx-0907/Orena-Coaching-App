"""`/api/library/items` and `/api/library/collections` - the learner's own library.

The read side of Thư viện của tôi is `/api/collection`, the typed query over
the owners that already exist. This is the write side and the learner's own
state on top of it: keeping, marking, filing, and the review queue the design
orders "marked first, then whatever is due".

It is available only on the PostgreSQL runtime, because `library_items` lives
there (`20260923_0013`, D-074). On any other backend every route answers 503
`library_unavailable` rather than pretending: a surface that cannot pin should
say so, not silently drop the pin.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from writing_coach.core.errors import orena_http_error
from writing_coach.persistence.library_repository import LibraryConflict, LibraryRepository

router = APIRouter(prefix="/api/library", tags=["library"])

# The queue the room draws is a sitting, not the whole library.
QUEUE_LIMIT = 60
# A listing asks about the rows it is drawing, and a page is 24.
LOOKUP_LIMIT = 200

_repository: Callable[[], LibraryRepository | None] | None = None

# Which refusal is which. A version conflict is the learner's two tabs
# disagreeing, not a bad request; a kind mismatch is a request that cannot be
# satisfied as written.
_STATUS = {
    "version_conflict": 409,
    "kind_mismatch": 422,
    "duplicate_title": 409,
    "unknown_item": 404,
    "unknown_collection": 404,
}


def configure_library(factory: Callable[[], LibraryRepository | None] | None) -> None:
    global _repository
    _repository = factory


def _library() -> LibraryRepository:
    repository = _repository() if _repository is not None else None
    if repository is None:
        raise orena_http_error(
            503, "library_unavailable", "The learner's library needs the PostgreSQL runtime."
        )
    return repository


def _refuse(error: LibraryConflict):
    return orena_http_error(
        _STATUS.get(error.reason, 422), error.reason, "The library refused that change."
    )


class KeepIn(BaseModel):
    """What to keep. A word is named; everything else carries its routing id."""

    kind: str = Field(max_length=32)
    word: str = Field(default="", max_length=180)
    source_id: str = Field(default="", max_length=255)
    relationship: str = Field(default="kept", max_length=32)


class ItemPatchIn(BaseModel):
    """What the learner changed, and the version they changed it from."""

    expected_version: int = Field(ge=1)
    pinned: bool | None = None
    state: str | None = Field(default=None, max_length=16)
    clear_state: bool = False
    note: str | None = Field(default=None, max_length=2000)


class CollectionIn(BaseModel):
    kind: str = Field(max_length=32)
    title: str = Field(min_length=1, max_length=120)


class CollectionItemIn(BaseModel):
    item_id: str = Field(max_length=64)


@router.get("/items", name="orena_library_items")
def library_items(
    kind: str = Query("", max_length=32),
    words: str = Query("", max_length=4000),
    sources: str = Query("", max_length=4000),
) -> dict[str, Any]:
    """The learner's own state for rows a listing is already drawing."""

    wanted_words = tuple(w for w in words.split(",") if w)[:LOOKUP_LIMIT]
    wanted_sources = tuple(s for s in sources.split(",") if s)[:LOOKUP_LIMIT]
    return {
        "items": _library().lookup(kind=kind, words=wanted_words, source_ids=wanted_sources)
    }


@router.post("/items", name="orena_library_keep")
def library_keep(payload: KeepIn) -> dict[str, Any]:
    try:
        return {"item": _library().keep(
            kind=payload.kind, word=payload.word,
            source_id=payload.source_id, relationship=payload.relationship,
        )}
    except LibraryConflict as error:
        raise _refuse(error) from error


@router.get("/items/{item_id}", name="orena_library_item")
def library_item(item_id: str) -> dict[str, Any]:
    item = _library().get(item_id)
    if item is None:
        raise orena_http_error(404, "unknown_item", "No such item in this library.")
    return {"item": item}


@router.patch("/items/{item_id}", name="orena_library_item_patch")
def library_item_patch(item_id: str, payload: ItemPatchIn) -> dict[str, Any]:
    try:
        return {"item": _library().update(
            item_id,
            expected_version=payload.expected_version,
            pinned=payload.pinned,
            state=payload.state,
            clear_state=payload.clear_state,
            note=payload.note,
        )}
    except LibraryConflict as error:
        raise _refuse(error) from error


@router.delete("/items/{item_id}", name="orena_library_item_delete")
def library_item_delete(item_id: str) -> dict[str, Any]:
    """Remove the relationship. The source, the word and its review evidence
    stay exactly as they were - Collection Architecture §4."""

    return {"removed": _library().forget(item_id)}


@router.get("/review-queue", name="orena_library_review_queue")
def library_review_queue() -> dict[str, Any]:
    return _library().review_queue(limit=QUEUE_LIMIT)


@router.get("/collections", name="orena_library_collections")
def library_collections(kind: str = Query("", max_length=32)) -> dict[str, Any]:
    return {"collections": _library().collections(kind=kind)}


@router.post("/collections", name="orena_library_collection_create")
def library_collection_create(payload: CollectionIn) -> dict[str, Any]:
    try:
        return {"collection": _library().create_collection(kind=payload.kind, title=payload.title)}
    except LibraryConflict as error:
        raise _refuse(error) from error


@router.get("/collections/{collection_id}/items", name="orena_library_collection_items")
def library_collection_items(collection_id: str) -> dict[str, Any]:
    return {"items": _library().collection_items(collection_id)}


@router.post("/collections/{collection_id}/items", name="orena_library_collection_add")
def library_collection_add(collection_id: str, payload: CollectionItemIn) -> dict[str, Any]:
    try:
        return _library().add_to_collection(collection_id, payload.item_id)
    except LibraryConflict as error:
        raise _refuse(error) from error


@router.delete(
    "/collections/{collection_id}/items/{item_id}", name="orena_library_collection_remove"
)
def library_collection_remove(collection_id: str, item_id: str) -> dict[str, Any]:
    return {"removed": _library().remove_from_collection(collection_id, item_id)}
