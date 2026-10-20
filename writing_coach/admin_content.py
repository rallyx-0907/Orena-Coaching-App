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


def book_status(book: Mapping[str, Any]) -> str:
    """`archived`, `published` (learners can read it) or `draft` (ready, but its rights are not attested yet, D-251).
    Before migration 0037 a book has no `rights_status` and a ready book is published, as it always was."""
    if book.get("status") != "ready":
        return "archived"
    rights = book.get("rights_status")
    return "published" if rights is None or rights in ("cleared", "grandfathered") else "draft"


def book_record(book: Mapping[str, Any]) -> dict[str, Any]:
    ready = book_status(book) == "published"
    identifier = _text(book.get("id"))
    return {
        "kind": "book",
        "id": identifier,
        "title": _text(book.get("title")),
        "subtitle": _text(book.get("author")),
        "language": _text(book.get("language")),
        "status": book_status(book),
        "origin": "imported",
        "created_at": book.get("created_at"),
        "updated_at": book.get("updated_at"),
        # The cover route answers only for a book learners can still open.
        "image": f"/api/reading/library/books/{identifier}/cover" if ready and book.get("has_cover") else "",
        "facts": {
            "chapter_count": int(book.get("chapter_count") or 0),
            "word_count": int(book.get("word_count") or 0),
            "source_kind": _text(book.get("source_kind")),
            "rights_status": book.get("rights_status"),  # D-251; None before migration 0037
        },
        "issues": [],
        # Archiving was the only recovery path and it was one-way. Both
        # directions are offered now, and neither destroys anything.
        "actions": ["preview", "archive"] if ready else ["preview", "restore"],
    }


def _segments(entry: Any) -> list[Any]:
    lesson = entry.lesson if isinstance(entry.lesson, Mapping) else {}
    payload = lesson.get("payload") if isinstance(lesson.get("payload"), Mapping) else {}
    transcript = payload.get("transcript") if isinstance(payload.get("transcript"), Mapping) else {}
    segments = transcript.get("segments")
    return list(segments) if isinstance(segments, list) else []


def media_outcome(entry: Any) -> dict[str, Any]:
    """Where an imported item is, in the four words an operator needs: processing, held (waiting for a person),
    failed (no usable transcript), ready. `reason` is the stable code stored on the item and `message` its English
    sentence (rows written before the message was stored get it from the code). Translation is reported beside, as
    `ready | partial | failed | deferred` with counts (`deferred` with a `continuation` is a rate-limited rest being asked for again): a partial translation is not a failure and never moves the state."""
    from writing_coach.media_transcript_pipeline import REASON_YOUTUBE_NO_CAPTIONS, reason_message, transcript_provenance

    processing = dict(getattr(entry, "processing", None) or {})
    raw = str(processing.get("state") or "")
    state = {"queued": "processing", "running": "processing", "failed": "failed", "held": "held", "ready": "ready"}.get(raw, raw)
    reason = str(processing.get("reason") or "")
    translation = str(processing.get("translation") or "")
    counts = processing.get("translation_counts") if isinstance(processing.get("translation_counts"), Mapping) else {}
    continuation = processing.get("translation_continuation")
    reprocess_reason = str(processing.get("reprocess_reason") or "")
    fallback = str(processing.get("caption_fallback") or "")
    return {
        "state": state,
        # Where the transcript came from (D-213): the provider's captions (manual or auto) or speech recognition, why
        # recognition ran where captions were the first choice, and why the last re-run kept the stored item instead.
        "transcript": {
            "origin": str(processing.get("origin") or ""),
            "caption_kind": str(processing.get("caption_kind") or ""),
            # Channel captions, machine captions or Orena's recognition (D-244); derived for an item stored before it.
            "provenance": str(processing.get("transcript_provenance") or "")
            or transcript_provenance(str(processing.get("origin") or ""), str(processing.get("caption_kind") or "")),
            "caption_provider": str(processing.get("caption_provider") or ""),
            "caption_language": str(processing.get("caption_language") or ""),
            "caption_fallback": fallback,
            "caption_fallback_message": reason_message(fallback),
            "caption_fallback_detail": str(processing.get("caption_fallback_detail") or ""),
            "reprocess_reason": reprocess_reason,
            "reprocess_message": str(processing.get("reprocess_message") or "") or reason_message(reprocess_reason),
        },
        "stage": str(processing.get("stage") or ""),
        "reason": reason,
        "message": str(processing.get("message") or "") or reason_message(reason),
        # The failing check and its counts for a reason that has one (`captions_unusable`), ids and numbers only (D-218).
        "detail": str(processing.get("detail") or "") if reason in {"captions_unusable", REASON_YOUTUBE_NO_CAPTIONS} else "",
        # Model clips not cut, and why: a YouTube item never is (`youtube_no_audio_download`, D-244). A skip, not an error.
        "model_clips_skipped": str(processing.get("model_clips_skipped") or ""),
        "translation": {
            "state": translation, "reason": str(processing.get("translation_reason") or ""),
            "counts": {str(key): dict(value) for key, value in counts.items() if isinstance(value, Mapping)},
            # A deferred translation says when it asks again and how many tries it has (D-211); absent otherwise.
            **({"continuation": {key: continuation[key] for key in ("attempt", "max_attempts", "next_at", "deadline") if key in continuation}}
               if isinstance(continuation, Mapping) and continuation else {}),
        },
    }


def media_record(entry: Any) -> dict[str, Any]:
    """A media source an administrator imported into the shared library."""
    from writing_coach.media_source_import import public_thumbnail_url, source_label

    segments = _segments(entry)
    lesson = entry.lesson if isinstance(entry.lesson, Mapping) else {}
    reprocessable = entry.provider == "upload" or (bool(entry.canonical_url) and entry.provider in _REPROCESSABLE_PROVIDERS)
    actions = _media_actions(getattr(entry, "status", "published"), reprocessable)
    if entry.status == "unpublished":
        actions.remove("republish")
    if entry.status in {"review", "unpublished"} and entry.source.get("rights") == "cleared":
        from writing_coach.media_transcript_pipeline import caption_timing_gate, usable_transcript
        if ((entry.processing or {}).get("state", "ready") in {"ready", "held"} and usable_transcript(entry)[0]
                and caption_timing_gate(entry)[0]):
            actions.append("republish" if entry.status == "unpublished" else "publish")
    return {
        "kind": "media",
        "id": entry.media_id,
        "title": entry.title,
        "subtitle": " · ".join(part for part in (source_label(entry), _text(entry.creator)) if part),
        "language": entry.language,
        "status": getattr(entry, "status", "published"),
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
        "processing": dict(getattr(entry, "processing", None) or {}),
        "outcome": media_outcome(entry),
        "actions": actions,
    }


def _media_actions(status: str, reprocessable: bool) -> list[str]:
    """What can be done from where this item is.

    A drawer that always offers the same pair asks an operator to work out
    which of them does anything; the states are the vocabulary, so the actions
    follow them. `delete` is deliberately absent: taking an item off the shelf
    must not destroy its transcript, its provenance or its audit trail, and a
    genuine mistake is a separate, deliberate path.
    """
    actions = ["preview"]
    if reprocessable and status != "archived":
        actions.append("reprocess")
    if status == "published":
        actions += ["unpublish", "archive"]
    elif status == "unpublished":
        actions += ["republish", "archive"]
    elif status in {"processing", "review"}:
        actions.append("archive")
    else:
        actions.append("restore")
    return actions


def curated_media_record(lesson: Any, *, hidden: bool = False) -> dict[str, Any]:
    """A lesson from the code-owned curated catalog. Edited by review, not here.

    Its text, rights and timing are the repository's. Whether learners see it is the one thing an administrator
    decides here (D-203): `hidden` shows it as unpublished and offers the existing unpublish / republish pair, which
    write the visibility switch and never the catalogue. Only a published lesson can be hidden or shown again.
    """
    status = _CURATED_STATUS.get(str(lesson.content_status), "draft")
    actions = ["preview"]
    if str(lesson.content_status) == "PUBLISHED":
        if hidden:
            status = "unpublished"
            actions.append("republish")
        else:
            actions.append("unpublish")
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
        "status": status,
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
        "actions": actions,
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
        "status": _collection_status(collection),
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
        "actions": _collection_actions(_collection_status(collection)),
    }


def _collection_status(collection: Mapping[str, Any]) -> str:
    """The editorial state, in the console's own vocabulary.

    `pending_review` reads as a draft to an operator scanning a mixed list;
    the other three are already the words the console uses everywhere else.
    """
    # The admin repository projects `catalog_status` under `status`; a caller
    # that hands the raw row keeps its own name. Both are read so neither
    # caller has to know which one it is.
    status = _text(collection.get("status")) or _text(collection.get("catalog_status")) or "pending_review"
    return "draft" if status == "pending_review" else status


def _collection_actions(status: str) -> list[str]:
    """What can be done from where this collection is.

    Restore from archived returns it to the shelf as `unpublished`, never
    straight to learners - so an archived collection offers restore and not
    publish, and the operator publishes again deliberately afterwards.
    """
    if status == "draft":
        return ["preview", "publish"]
    if status == "published":
        return ["preview", "unpublish", "archive"]
    if status == "unpublished":
        return ["preview", "publish", "archive"]
    return ["preview", "restore"]


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
            "status": book_status(book),
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
