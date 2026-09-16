from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field
from writing_coach.core.request_context import current_language_code
from writing_coach.orthography import orthography_for_word
from writing_coach.persistence.specialized_repository import SpecializedLearningRepository
from writing_coach.persistence.vocabulary_repository import VocabularyRepository, VocabularyContentUnavailable
from writing_coach.vocabulary_library import all_vocabulary_entries, normalize_vocabulary_word


_repository: SpecializedLearningRepository | None = None
_content_repository: VocabularyRepository | None = None

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


def configure_becoming_library_content(repository: VocabularyRepository | None) -> None:
    """Install the shared content read-through without changing learner state."""

    global _content_repository
    _content_repository = repository


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


def _catalog_entry_for(word: str) -> dict[str, Any] | None:
    normalized = normalize_vocabulary_word(word)
    if not normalized:
        return None
    language = current_language_code().strip().casefold()
    if _content_repository is not None:
        try:
            persisted = _content_repository.find_entry(language, normalized)
        except (VocabularyContentUnavailable, RuntimeError, OSError):
            persisted = None
        if persisted is not None:
            return persisted
    return next(
        (
            entry
            for entry in all_vocabulary_entries(language)
            if entry.get("normalized_word") == normalized
        ),
        None,
    )


def _row_to_item(row: dict[str, Any]) -> dict[str, Any]:
    stage = int(row["review_stage"] or 0)
    word = str(row["word"])
    language = current_language_code().strip().casefold()
    catalog_entry = _catalog_entry_for(word)
    orthography = None
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
    if catalog_entry is not None:
        for field in ("level", "framework", "topic"):
            if catalog_entry.get(field):
                item[field] = catalog_entry[field]
        if not item["phonetic"] and catalog_entry.get("phonetic"):
            item["phonetic"] = str(catalog_entry["phonetic"])
        for field in (
            "short_meanings", "detailed_definitions", "readings", "pronunciations",
            "usage_notes", "content_origins", "provenance",
        ):
            if catalog_entry.get(field):
                item[field] = catalog_entry[field]
        if catalog_entry.get("support_translations"):
            item["support_translations"] = dict(catalog_entry["support_translations"])
        examples = catalog_entry.get("examples")
        if isinstance(examples, list) and examples:
            item["examples"] = [dict(example) for example in examples if isinstance(example, dict)]
        if isinstance(catalog_entry.get("orthography"), dict) and catalog_entry["orthography"]:
            orthography = dict(catalog_entry["orthography"])
    if orthography is None:
        orthography = orthography_for_word(word, language)
    if orthography is not None:
        item["orthography"] = orthography
    return item


def list_library_vocabulary() -> dict[str, Any]:
    items = [_row_to_item(row) for row in _repo().list_library_records()]
    items.sort(key=lambda item: (0 if item["due"] else 1, item["next_review_at"] or item["added_at"], item["word"].casefold()))
    return {
        "items": items,
        "summary": {
            "total": len(items),
            "saved": len(items),
            "due": sum(1 for item in items if item["due"]),
            "learning": sum(1 for item in items if item["review_stage"] < 3),
            "mastered": sum(1 for item in items if item["review_stage"] >= 3),
            "available": sum(1 for item in items if item["review_stage"] >= 3),
        },
    }


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
