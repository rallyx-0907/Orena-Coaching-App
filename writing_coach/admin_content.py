"""One admin content library over the catalogs that already exist.

Reading owns books (`reading_books`), Listening owns media (the curated catalog
manifest and the shared media library index), Vocabulary owns collections
(`vocabulary_collections`). This module does not merge those domains into one
schema and does not copy them anywhere: it projects each record into the small
set of fields an operator scans - title, type, language, state, issues - while
keeping the domain's own identity, so every action goes back to the owner.

Actions are listed only where a backend contract exists. A book can be
archived (the reading library's recovery path); a pending vocabulary
collection can be published through the repository's admission-checked
finalisation; a URL-sourced media import can be run again through the same
importer. Nothing offers delete, unpublish or edit, because nothing implements
them.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

KINDS = ("book", "media", "vocabulary")

# Curated catalog states (listening_catalog.CONTENT_STATUSES plus the dev
# overlay state) in the console's vocabulary. A development candidate is only
# learner-visible when its overlay is explicitly enabled, so it is a draft.
_CURATED_STATUS = {
    "PUBLISHED": "published",
    "READY": "ready",
    "PROCESSING": "processing",
    "NEEDS_REVIEW": "draft",
    "DRAFT": "draft",
    "DEV_CANDIDATE": "draft",
    "ARCHIVED": "archived",
}
_REPROCESSABLE_PROVIDERS = frozenset({"youtube", "direct"})

# Where a book import stopped, by the category the importer reports.
_BOOK_STAGES = {
    "archive_too_large": "upload",
    "malformed_archive": "archive",
    "unsafe_archive_entry": "archive",
    "malformed_epub": "parse",
    "malformed_xml": "parse",
    "unsafe_xml_content": "parse",
    "import_failed": "parse",
    "no_readable_content": "content",
    "missing_title": "content",
    "storage_failed": "storage",
    "reading_library_unavailable": "catalog",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def book_error_stage(category: str) -> str:
    """Where a book import stopped, from the category the importer reported."""
    return _BOOK_STAGES.get(_text(category), "parse")


def book_record(book: Mapping[str, Any]) -> dict[str, Any]:
    ready = book.get("status") == "ready"
    identifier = _text(book.get("id"))
    return {
        "kind": "book",
        "id": identifier,
        "title": _text(book.get("title")),
        "subtitle": _text(book.get("author")),
        "language": _text(book.get("language")),
        "status": "published" if ready else "archived",
        "origin": "imported",
        "created_at": book.get("created_at"),
        "updated_at": book.get("updated_at"),
        # The cover route answers only for a book learners can still open.
        "image": f"/api/reading/library/books/{identifier}/cover" if ready and book.get("has_cover") else "",
        "facts": {
            "chapter_count": int(book.get("chapter_count") or 0),
            "word_count": int(book.get("word_count") or 0),
            "source_kind": _text(book.get("source_kind")),
        },
        "issues": [],
        "actions": ["preview", "archive"] if ready else ["preview"],
    }


def _segments(entry: Any) -> list[Any]:
    lesson = entry.lesson if isinstance(entry.lesson, Mapping) else {}
    payload = lesson.get("payload") if isinstance(lesson.get("payload"), Mapping) else {}
    transcript = payload.get("transcript") if isinstance(payload.get("transcript"), Mapping) else {}
    segments = transcript.get("segments")
    return list(segments) if isinstance(segments, list) else []


def media_record(entry: Any) -> dict[str, Any]:
    """A media source an administrator imported into the shared library."""
    from writing_coach.media_source_import import public_thumbnail_url, source_label

    segments = _segments(entry)
    lesson = entry.lesson if isinstance(entry.lesson, Mapping) else {}
    reprocessable = bool(entry.canonical_url) and entry.provider in _REPROCESSABLE_PROVIDERS
    return {
        "kind": "media",
        "id": entry.media_id,
        "title": entry.title,
        "subtitle": " · ".join(part for part in (source_label(entry), _text(entry.creator)) if part),
        "language": entry.language,
        # Imported shared media is served to learners the moment it is stored.
        "status": "published",
        "origin": "imported",
        "created_at": entry.created_at,
        "updated_at": entry.created_at,
        "image": public_thumbnail_url(entry),
        "facts": {
            "duration_ms": int(entry.duration_ms or 0),
            "media_type": entry.media_type,
            "provider": entry.provider,
            "level": entry.level,
            "topic": _text(lesson.get("topic")),
            "segment_count": len(segments),
            "transcript": "available" if segments else "missing",
        },
        "issues": [] if segments else ["transcript_missing"],
        "actions": ["preview", "reprocess"] if reprocessable else ["preview"],
    }


def curated_media_record(lesson: Any) -> dict[str, Any]:
    """A lesson from the code-owned curated catalog. Edited by review, not here."""
    source = lesson.source
    transcript = getattr(lesson.media_object, "transcript", None)
    segments = [
        segment
        for segment in (transcript.segments if transcript is not None else ())
        if lesson.excerpt_start_ms <= segment.start_ms < lesson.excerpt_end_ms
    ]
    return {
        "kind": "media",
        "id": lesson.lesson_id,
        "title": lesson.media_object.asset.title,
        "subtitle": " · ".join(part for part in (_text(source.source_provider), _text(source.source_creator)) if part),
        "language": source.language,
        "status": _CURATED_STATUS.get(str(lesson.content_status), "draft"),
        "origin": "curated",
        "created_at": None,
        "updated_at": None,
        "image": _text(source.poster_url),
        "facts": {
            "duration_ms": int(lesson.duration_ms or 0),
            "media_type": "audio" if source.playback.kind == "audio" else "video",
            "provider": source.source_provider,
            "level": lesson.level,
            "topic": lesson.topic,
            "segment_count": len(segments),
            "transcript": "available" if segments else "missing",
            "content_status": str(lesson.content_status),
        },
        "issues": [] if segments else ["transcript_missing"],
        "actions": ["preview"],
    }


def vocabulary_record(collection: Mapping[str, Any]) -> dict[str, Any]:
    pending = collection.get("status") != "published"
    level = _text(collection.get("level_range")) or _text(collection.get("level"))
    return {
        "kind": "vocabulary",
        "id": _text(collection.get("id")),
        "title": _text(collection.get("title")),
        "subtitle": " · ".join(part for part in (_text(collection.get("framework")), level, _text(collection.get("topic"))) if part),
        "language": _text(collection.get("language")),
        "status": "draft" if pending else "published",
        "origin": _text(collection.get("origin")) or "imported",
        "created_at": collection.get("created_at"),
        "updated_at": collection.get("updated_at"),
        "image": "",
        "facts": {
            "item_count": int(collection.get("item_count") or 0),
            "framework": _text(collection.get("framework")),
            "level": level,
            "topic": _text(collection.get("topic")),
            "rights_status": _text(collection.get("rights_status")),
            "completeness": _text(collection.get("completeness")),
        },
        "issues": ["pending_review"] if pending else [],
        "actions": ["preview", "publish"] if pending else ["preview"],
    }


def transcript_attention_count(records: Iterable[Mapping[str, Any]]) -> int:
    """Missing transcripts an operator can do something about (a URL source)."""
    return sum(
        1
        for record in records
        if "transcript_missing" in record.get("issues", ()) and "reprocess" in record.get("actions", ())
    )


def content_counts(records: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts = {"all": 0, **{kind: 0 for kind in KINDS}}
    for record in records:
        counts["all"] += 1
        if record.get("kind") in counts:
            counts[record["kind"]] += 1
    return counts


def status_counts(records: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {"issues": 0}
    for record in records:
        counts[record.get("status", "")] = counts.get(record.get("status", ""), 0) + 1
        if record.get("issues"):
            counts["issues"] += 1
    return counts


def _stamp(record: Mapping[str, Any]) -> str:
    return str(record.get("updated_at") or record.get("created_at") or "")


def filter_records(
    records: Iterable[Mapping[str, Any]],
    *,
    kind: str = "",
    query: str = "",
    language: str = "",
    status: str = "",
    sort: str = "updated",
) -> list[Mapping[str, Any]]:
    needle = _text(query).casefold()
    selected = []
    for record in records:
        if kind and kind != "all" and record.get("kind") != kind:
            continue
        if language and record.get("language") != language:
            continue
        if status == "issues":
            if not record.get("issues"):
                continue
        elif status and record.get("status") != status:
            continue
        if needle and needle not in f"{record.get('title', '')} {record.get('subtitle', '')} {record.get('id', '')}".casefold():
            continue
        selected.append(record)
    if sort == "title":
        return sorted(selected, key=lambda record: _text(record.get("title")).casefold())
    if sort == "created":
        dated = sorted(selected, key=lambda record: str(record.get("created_at") or ""), reverse=True)
        return [r for r in dated if r.get("created_at")] + [r for r in dated if not r.get("created_at")]
    # Most recently changed first; code-owned catalog lessons carry no dates
    # and follow in their catalog order.
    dated = [record for record in selected if _stamp(record)]
    undated = [record for record in selected if not _stamp(record)]
    return sorted(dated, key=_stamp, reverse=True) + undated


def paginate(records: list[Any], *, offset: int = 0, limit: int = 25) -> tuple[list[Any], int]:
    start = max(0, int(offset or 0))
    size = max(1, min(int(limit or 25), 100))
    return records[start:start + size], len(records)


def _receipt_row(receipt: Mapping[str, Any], books: Mapping[str, Mapping[str, Any]],
                 media: Mapping[str, Any]) -> dict[str, Any]:
    payload = receipt.get("payload") if isinstance(receipt.get("payload"), Mapping) else {}
    kind = _text(payload.get("kind")) or _text(receipt.get("entity_type"))
    content_id = _text(receipt.get("entity_id")) or _text(payload.get("content_id"))
    outcome = _text(payload.get("status"))
    result: dict[str, Any] = {"content_id": content_id, "title": _text(payload.get("title"))}
    error = None
    if outcome == "error":
        status = "failed"
        code = _text(payload.get("category")) or f"{kind}_import_failed"
        stage = book_error_stage(code) if kind == "book" else "source"
        error = {"stage": stage, "code": code, "message": _text(payload.get("detail"))}
    elif outcome == "duplicate":
        status = "duplicate"
    else:
        status = "published"
        if kind == "book" and books.get(content_id, {}).get("status") == "archived":
            status = "archived"
    if kind == "book":
        result["chapter_count"] = int(payload.get("chapter_count") or 0)
    elif kind == "media":
        entry = media.get(content_id)
        segments = _segments(entry) if entry is not None else []
        result["transcript"] = "available" if segments or payload.get("has_transcript") else "missing"
    return {
        "id": _text(receipt.get("id")),
        "kind": kind,
        "source": _text(payload.get("source")),
        "language": _text(payload.get("language")),
        "created_at": receipt.get("created_at"),
        "status": status,
        "result": result,
        "error": error,
        "origin": "receipt",
    }


def history_rows(
    *,
    receipts: Iterable[Mapping[str, Any]],
    vocabulary_imports: Iterable[Mapping[str, Any]],
    books: Iterable[Mapping[str, Any]] | None,
    media_entries: Iterable[Any],
) -> list[dict[str, Any]]:
    """Every import this deployment can account for, newest first.

    Book and media attempts are recorded as audit receipts when they run
    through the console, failures included. Books and media imported before
    receipts existed still appear, from their catalog rows, as the successes
    they were - their original file name was never stored, so the title stands
    in for it. Vocabulary sources carry their own receipt table already.
    """
    book_index = {_text(book.get("id")): book for book in books or []}
    media_index = {entry.media_id: entry for entry in media_entries or []}
    rows = [_receipt_row(receipt, book_index, media_index) for receipt in receipts]
    seen = {(row["kind"], row["result"]["content_id"]) for row in rows if row["result"]["content_id"]}

    for identifier, book in book_index.items():
        if ("book", identifier) in seen:
            continue
        rows.append({
            "id": f"book:{identifier}",
            "kind": "book",
            "source": _text(book.get("title")),
            "language": _text(book.get("language")),
            "created_at": book.get("created_at"),
            "status": "archived" if book.get("status") == "archived" else "published",
            "result": {"content_id": identifier, "title": _text(book.get("title")),
                       "chapter_count": int(book.get("chapter_count") or 0)},
            "error": None,
            "origin": "catalog",
        })
    for identifier, entry in media_index.items():
        if ("media", identifier) in seen:
            continue
        rows.append({
            "id": f"media:{identifier}",
            "kind": "media",
            "source": entry.canonical_url or entry.title,
            "language": entry.language,
            "created_at": entry.created_at,
            "status": "published",
            "result": {"content_id": identifier, "title": entry.title,
                       "transcript": "available" if _segments(entry) else "missing"},
            "error": None,
            "origin": "catalog",
        })
    for receipt in vocabulary_imports:
        failed = receipt.get("status") == "failed"
        message = _text(receipt.get("error"))
        if failed:
            status = "failed"
        elif receipt.get("status") == "skipped":
            status = "skipped"
        else:
            status = "published" if receipt.get("collection_status") == "published" else "ready"
        rows.append({
            "id": _text(receipt.get("id")),
            "kind": "vocabulary",
            "source": _text(receipt.get("filename")),
            "language": "",
            "created_at": receipt.get("created_at"),
            "status": status,
            "result": {
                "content_id": _text(receipt.get("collection_id")),
                "title": _text(receipt.get("collection_title")),
                "imported": int(receipt.get("imported") or 0),
                "duplicates": int(receipt.get("duplicates") or 0),
                "skipped": int(receipt.get("skipped") or 0),
            },
            "error": {
                "stage": "persistence" if message.startswith("persistence unavailable") else "validation",
                "code": "vocabulary_import_failed",
                "message": message,
            } if failed else None,
            "origin": "receipt",
        })
    return sorted(rows, key=lambda row: str(row.get("created_at") or ""), reverse=True)


def filter_history(rows: Iterable[Mapping[str, Any]], *, kind: str = "", status: str = "") -> list[Mapping[str, Any]]:
    return [
        row
        for row in rows
        if (not kind or kind == "all" or row.get("kind") == kind)
        and (not status or status == "all" or row.get("status") == status)
    ]


def recent_failures(rows: Iterable[Mapping[str, Any]], *, since: str) -> int:
    return sum(1 for row in rows if row.get("status") == "failed" and str(row.get("created_at") or "") >= since)
