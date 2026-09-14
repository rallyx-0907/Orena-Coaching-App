from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field
from writing_coach.core.request_context import current_language_code
from writing_coach.orthography import orthography_for_word
from writing_coach.persistence.specialized_repository import SpecializedLearningRepository


_repository: SpecializedLearningRepository | None = None

STAGE_LABELS = {
    0: "New",
    1: "Learning",
    2: "Reinforcing",
    3: "Available",
    4: "Available",
}


class LibraryVocabularyIn(BaseModel):
    word: str = Field(min_length=1, max_length=180)
    phonetic: str = Field(default="", max_length=180)
    part_of_speech: str = Field(default="", max_length=120)
    definition: str = Field(default="", max_length=2400)
    translation_vi: str = Field(default="", max_length=2400)
    source_essay_id: int | None = Field(default=None, ge=1)
    source_fragment: str = Field(default="", max_length=1200)
    source_kind: str = Field(
        default="manual",
        pattern=r"^(manual|dictionary|feedback|strength|reading|feed|collection)$",
    )
    focus_note: str = Field(default="", max_length=2400)


class VocabularyReviewIn(BaseModel):
    result: str = Field(pattern=r"^(again|got_it)$")


def configure_becoming_library(repository: SpecializedLearningRepository) -> None:
    global _repository
    _repository = repository


def _repo() -> SpecializedLearningRepository:
    if _repository is None:
        raise RuntimeError("BECOMING library repository is not installed")
    return _repository

def _now() -> datetime:
    return datetime.now().astimezone()


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _clean_term(value: str) -> str:
    return " ".join(str(value or "").strip().split())


def _parse_time(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value or ""))
    except Exception:
        return None


def _due(value: str) -> bool:
    parsed = _parse_time(value)
    return parsed is None or parsed <= _now()


def _stage_label(stage: int) -> str:
    return STAGE_LABELS.get(max(0, min(4, int(stage or 0))), "New")


def _row_to_item(row: dict[str, Any]) -> dict[str, Any]:
    stage = int(row["review_stage"] or 0)
    word = str(row["word"])
    orthography = orthography_for_word(word, current_language_code())
    item = {
        "word": word,
        "phonetic": str(row["phonetic"] or ""),
        "part_of_speech": str(row["part_of_speech"] or ""),
        "definition": str(row["definition"] or ""),
        "translation_vi": str(row["translation_vi"] or ""),
        "added_at": str(row["added_at"] or ""),
        "source_essay_id": row["source_essay_id"],
        "source_fragment": str(row["source_fragment"] or ""),
        "source_kind": str(row["source_kind"] or "manual"),
        "focus_note": str(row["focus_note"] or ""),
        "review_stage": stage,
        "stage_label": _stage_label(stage),
        "successful_recalls": int(row["successful_recalls"] or 0),
        "lapse_count": int(row["lapse_count"] or 0),
        "last_reviewed_at": str(row["last_reviewed_at"] or ""),
        "next_review_at": str(row["next_review_at"] or ""),
        "due": _due(str(row["next_review_at"] or "")),
    }
    if orthography is not None:
        item["orthography"] = orthography
    return item


def list_library_vocabulary() -> dict[str, Any]:
    items = [_row_to_item(row) for row in _repo().list_library_records()]
    items.sort(key=lambda item: (0 if item["due"] else 1, item["next_review_at"] or item["added_at"], item["word"].casefold()))
    return {"items": items, "summary": {"total": len(items), "due": sum(1 for item in items if item["due"]), "available": sum(1 for item in items if item["review_stage"] >= 3)}}


def save_library_vocabulary(payload: LibraryVocabularyIn) -> dict[str, Any]:
    term = _clean_term(payload.word)
    if not term:
        raise ValueError("Vocabulary item cannot be empty.")
    row = _repo().save_library_record({
        "word": term, "phonetic": payload.phonetic, "part_of_speech": payload.part_of_speech,
        "definition": payload.definition, "translation_vi": payload.translation_vi,
        "source_essay_id": payload.source_essay_id, "source_fragment": payload.source_fragment,
        "source_kind": payload.source_kind, "focus_note": payload.focus_note, "now": _iso(_now()),
    })
    return {"saved": True, "item": _row_to_item(row)}


def review_library_vocabulary(word: str, payload: VocabularyReviewIn) -> dict[str, Any]:
    clean = _clean_term(word); now_dt = _now(); now = _iso(now_dt)
    row = _repo().get_library_progress(clean)
    if not row:
        return {"found": False}
    stage=int(row["review_stage"] or 0); success=int(row["successful_recalls"] or 0); lapses=int(row["lapse_count"] or 0)
    if payload.result == "got_it":
        next_stage=min(4,stage+1); success+=1; intervals={1:1,2:3,3:7,4:21}; next_dt=now_dt+timedelta(days=intervals[next_stage])
    else:
        next_stage=max(0,stage-1); lapses+=1; next_dt=now_dt+timedelta(minutes=10)
    updated=_repo().update_library_review(clean,{"review_stage":next_stage,"successful_recalls":success,"lapse_count":lapses,
        "last_reviewed_at":now,"next_review_at":_iso(next_dt),"updated_at":now})
    return {"found": updated is not None, "item": _row_to_item(updated) if updated else None}


def delete_library_vocabulary(word: str) -> dict[str, Any]:
    return {"deleted": _repo().delete_library_record(_clean_term(word))}
