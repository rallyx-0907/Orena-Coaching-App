from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field
from writing_coach.core.request_context import current_language_code
from writing_coach.orthography import orthography_for_word
from writing_coach.persistence.specialized_repository import (
    LIBRARY_PAGE_DEFAULT,
    SpecializedLearningRepository,
)
from writing_coach.product.rank_ladder import ladder as rank_ladder
from writing_coach.product.rank_ladder import rank_state
from writing_coach.persistence.vocabulary_repository import VocabularyRepository, VocabularyContentUnavailable
from writing_coach.vocabulary_library import normalize_vocabulary_word, vocabulary_entry_for


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


CATALOG_INDEX_LIMIT = 5000


def _catalog_entry_for(word: str, resolve: Any = None) -> dict[str, Any] | None:
    normalized = normalize_vocabulary_word(word)
    if not normalized:
        return None
    language = current_language_code().strip().casefold()
    if resolve is not None:
        persisted = resolve(normalized)
    elif _content_repository is not None:
        try:
            persisted = _content_repository.find_entry(language, normalized)
        except (VocabularyContentUnavailable, RuntimeError, OSError):
            persisted = None
    else:
        persisted = None
    if persisted is not None:
        return persisted
    return vocabulary_entry_for(language, normalized)


def _catalog_resolver(language: str):
    """How to find one word's curated entry while listing many of them.

    Listing a learner's saved words used to ask the content repository about
    each word on its own, and every one of those calls re-checks that the
    shared schema is there - an inspector pass, and until it was cached, a
    rebuild of Alembic's revision map. A learner with sixteen hundred saved
    words waited minutes for their own vocabulary, and Hồ sơ and Tiến độ, which
    read the same list, waited with them.

    So the decision is made once, for the whole list:

    - the repository cannot answer at all - ask it nothing, and let the static
      catalogue answer;
    - it can, and the language fits one page - read that page once and look
      each word up in it;
    - it can, but the language has more entries than a page - keep the per-word
      call, because a partial index would quietly stop finding words the old
      path found.
    """

    if _content_repository is None:
        return lambda normalized: None
    try:
        entries = _content_repository.list_entries_for_language(language, limit=CATALOG_INDEX_LIMIT)
    except (VocabularyContentUnavailable, RuntimeError, OSError):
        return lambda normalized: None
    if len(entries) >= CATALOG_INDEX_LIMIT:
        repository = _content_repository

        def by_word(normalized: str) -> dict[str, Any] | None:
            try:
                return repository.find_entry(language, normalized)
            except (VocabularyContentUnavailable, RuntimeError, OSError):
                return None

        return by_word
    index: dict[str, dict[str, Any]] = {}
    for entry in entries:
        key = str(entry.get("normalized_term") or entry.get("normalized_word") or "")
        if key:
            index.setdefault(key, entry)
    return index.get


def _row_to_item(row: dict[str, Any], resolve: Any = None) -> dict[str, Any]:
    stage = int(row["review_stage"] or 0)
    word = str(row["word"])
    language = current_language_code().strip().casefold()
    catalog_entry = _catalog_entry_for(word, resolve)
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


def library_summary() -> dict[str, Any]:
    """The learner's vocabulary as numbers, counted in the database.

    Every count is one aggregate query. No surface reads the words to count
    them: a summary must not cost what the whole vocabulary costs, or Hồ sơ and
    Tiến độ get slower every time the learner saves a word.

    The rank comes from the mastered count through
    `writing_coach.product.rank_ladder`, so the two screens that show a rank
    cannot disagree about it, and neither has to know the thresholds.
    """

    counts = _repo().library_counts(now=_iso(_now()))
    saved = int(counts.get("saved", 0))
    mastered = int(counts.get("mastered", 0))
    summary = {
        "total": saved,
        "saved": saved,
        "due": int(counts.get("due", 0)),
        "learning": int(counts.get("learning", max(0, saved - mastered))),
        "mastered": mastered,
        # The older name for the same number, kept so existing callers of this
        # payload do not break.
        "available": mastered,
    }
    # The ladder travels with the summary: it is thirty-two short entries, it
    # is the same for everyone, and sending it means Tiến độ draws the rungs
    # the product defines rather than keeping its own copy of them.
    return {"summary": summary, "ladder": rank_ladder(), **rank_state(mastered)}


def library_page(
    *,
    limit: int = LIBRARY_PAGE_DEFAULT,
    cursor: str = "",
    search: str = "",
    status: str = "",
    order: str = "recent",
    focus: tuple[str, ...] = (),
) -> dict[str, Any]:
    """One page of the learner's saved words, with the counts beside it.

    Ordering, filtering and searching happen in the database; this only turns
    the rows it is given into items. The default order is the newest first;
    `order="due"` puts what is waiting for review at the front, which is the
    order the review panel and the recall queue want.

    **What the cursor promises**: a word whose sort key does not change while
    the learner pages is seen exactly once - never twice, never skipped. A word
    that is saved, rescheduled or graded mid-walk moves to where its new key
    belongs and is met there, which is the ordering telling the truth rather
    than a page being wrong. A cursor is only read for the question it came
    from: change the search, the status, the order or the focus and it is
    ignored, so the caller gets that question's first page.

    **What a search matches**: the word, the definition and the translation the
    learner kept with it - every field the learner's own database holds. Not
    the curated catalogue's `support_translations`, which are attached when a
    word is read, not stored with it. This costs nothing in practice, because
    every way of keeping a word writes the meaning the learner was looking at
    into `definition` or `translation_vi` (see `vocabularyKeepPayload` and the
    reader's and Quick Sheet's keep actions). The alternative - searching the
    shared catalogue and intersecting - would be a second store in the search
    path for a case the keep paths already cover.
    """

    resolve = _catalog_resolver(current_language_code().strip().casefold())
    page = _repo().list_library_page(
        limit=limit, cursor=cursor, search=search, status=status,
        order=order, focus=tuple(focus or ()), now=_iso(_now()),
    )
    items = [_row_to_item(row, resolve) for row in page["rows"]]
    counts = library_summary()
    return {
        "items": items,
        "next_cursor": page.get("next_cursor"),
        "has_more": bool(page.get("next_cursor")),
        "total": int(page.get("total", len(items))),
        **counts,
    }


def list_library_vocabulary(
    *,
    limit: int = LIBRARY_PAGE_DEFAULT,
    cursor: str = "",
    search: str = "",
    status: str = "",
    order: str = "recent",
    focus: tuple[str, ...] = (),
) -> dict[str, Any]:
    """The saved-vocabulary listing, one page at a time.

    This used to answer with every word the learner had ever saved. It cannot:
    a learner with ten thousand words would have that whole library read,
    built, serialised, sent, parsed and rendered every time any screen asked
    a question about their vocabulary. Callers now ask for what they need -
    a page, a count, the few due words - and page on with `next_cursor`.
    """

    return library_page(
        limit=limit, cursor=cursor, search=search, status=status, order=order, focus=focus,
    )


def saved_vocabulary_words(candidates: tuple[str, ...] = ()) -> set[str]:
    """Which of these words the learner has saved, folded for comparison.

    Membership, asked as membership. Callers used to read the whole listing -
    items, review state, catalogue and all - to answer it.
    """

    return {
        normalize_vocabulary_word(word) or str(word).casefold()
        for word in _repo().list_saved_words(words=tuple(candidates or ()))
    }


def saved_vocabulary_state(candidates: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    """The learner's saved items for these words, by normalized word.

    What a collection's cards and its progress need: which of the words on the
    page are kept, and how far along each one is. The cost is the page's, not
    the library's.
    """

    resolve = _catalog_resolver(current_language_code().strip().casefold())
    return {
        normalize_vocabulary_word(row.get("word")) or str(row.get("word") or "").casefold():
            _row_to_item(row, resolve)
        for row in _repo().list_saved_rows(tuple(candidates or ()))
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
