"""One admin content library over three existing catalogs, and one import history.

Records keep each domain's own identity (a book id, a media id, a collection id)
and only project the fields an operator scans; nothing is copied into a new
store. Actions are offered only where a backend contract exists.
"""
from writing_coach import admin_content as content
from writing_coach.listening_catalog import CATALOG
from writing_coach.media_library_store import MediaLibraryEntry


def _book(**overrides):
    base = {
        "id": "b1", "title": "The Last Train", "author": "A. Writer", "language": "en", "status": "ready",
        "chapter_count": 12, "word_count": 30000, "has_cover": True, "source_kind": "epub",
        "imported_by": "admin@example.com", "created_at": "2026-09-10T10:00:00+00:00",
        "updated_at": "2026-09-10T10:00:00+00:00",
    }
    return {**base, **overrides}


def _entry(media_id="youtube-abc", *, provider="youtube", url="https://www.youtube.com/watch?v=abcdefghijk",
           segments=2, created_at="2026-09-12T08:00:00Z", library="shared", language="en"):
    lesson = None
    if segments is not None:
        lesson = {
            "lesson_id": media_id,
            "payload": {"asset": {"asset_id": media_id}, "transcript": {"segments": [
                {"segment_id": f"s{i}", "order": i, "start_ms": i * 1000, "end_ms": i * 1000 + 900, "original_text": f"line {i}"}
                for i in range(segments)
            ]}, "translations": []},
            "topic": "travel", "tags": ["city"],
        }
    return MediaLibraryEntry(
        media_id=media_id, media_type="video", provider=provider, provider_media_id="abc", canonical_url=url,
        playback={"provider": provider, "kind": "embed", "url": "https://www.youtube-nocookie.com/embed/abc"},
        title="City walk", thumbnail={"kind": "provider-url", "ref": "https://i.ytimg.com/vi/abc/hqdefault.jpg"},
        duration_ms=61000, language=language, level="A2", creator="",
        source={"provider": provider, "type": "admin-import", "provenance_url": url, "license": "x",
                "review_status": "checked", "imported_by": "admin@example.com"},
        library=library, created_at=created_at, lesson=lesson,
    )


def _collection(**overrides):
    base = {
        "id": "toeic-core", "title": "TOEIC core", "language": "en", "framework": "TOEIC", "level": "B1",
        "level_range": "A2–B1", "topic": "work", "status": "pending_review", "origin": "imported", "item_count": 40,
        "rights_status": "licensed", "completeness": "complete",
        "created_at": "2026-09-11T00:00:00+00:00", "updated_at": "2026-09-14T00:00:00+00:00",
    }
    return {**base, **overrides}


def test_book_records_keep_identity_and_offer_the_way_back_when_archived():
    ready = content.book_record(_book())
    assert ready["kind"] == "book" and ready["id"] == "b1"
    assert ready["status"] == "published"
    assert ready["image"] == "/api/reading/library/books/b1/cover"
    assert ready["facts"]["chapter_count"] == 12
    assert ready["actions"] == ["preview", "archive"]
    archived = content.book_record(_book(status="archived"))
    assert archived["status"] == "archived"
    assert archived["image"] == ""
    # Archiving is a recovery path, so it has a way back; nothing was deleted.
    assert archived["actions"] == ["preview", "restore"]


def test_imported_media_reports_transcript_state_and_reprocess_only_for_url_sources():
    with_transcript = content.media_record(_entry())
    assert with_transcript["status"] == "published"
    assert with_transcript["origin"] == "imported"
    assert with_transcript["facts"]["transcript"] == "available"
    assert with_transcript["facts"]["segment_count"] == 2
    assert with_transcript["issues"] == []
    # Published, so the two ways off the shelf are offered beside reprocess.
    assert with_transcript["actions"] == ["preview", "reprocess", "unpublish", "archive"]

    captionless = content.media_record(_entry(segments=None))
    assert captionless["facts"]["transcript"] == "missing"
    assert captionless["issues"] == ["transcript_missing"]

    upload = content.media_record(_entry("upload-1", provider="upload", url="", segments=None))
    # An upload cannot be read again, but it can still be taken off the shelf.
    assert upload["actions"] == ["preview", "unpublish", "archive"]
    assert upload["issues"] == ["transcript_missing"]


def test_only_actionable_missing_transcripts_need_attention():
    records = [
        content.media_record(_entry("youtube-a", segments=None)),
        content.media_record(_entry("upload-b", provider="upload", url="", segments=None)),
        content.media_record(_entry("youtube-c")),
    ]
    assert content.transcript_attention_count(records) == 1


def test_curated_media_comes_from_the_code_owned_catalog_and_is_read_only():
    lesson = CATALOG[0]
    record = content.curated_media_record(lesson)
    assert record["id"] == lesson.lesson_id
    assert record["origin"] == "curated"
    assert record["language"] == lesson.source.language
    assert record["actions"] == ["preview"]
    assert record["facts"]["transcript"] == "available"
    assert record["facts"]["segment_count"] > 0
    expected = "published" if lesson.content_status == "PUBLISHED" else record["status"]
    assert record["status"] == expected


def test_vocabulary_collections_waiting_for_review_are_drafts_that_can_be_published():
    pending = content.vocabulary_record(_collection())
    assert pending["status"] == "draft"
    assert pending["issues"] == ["pending_review"]
    assert pending["actions"] == ["preview", "publish"]
    assert pending["subtitle"] == "TOEIC · A2–B1 · work"
    # A published collection can now be taken back or retired, reversibly.
    published = content.vocabulary_record(_collection(status="published"))
    assert published["status"] == "published"
    assert published["actions"] == ["preview", "unpublish", "archive"]
    taken = content.vocabulary_record(_collection(status="unpublished"))
    assert taken["actions"] == ["preview", "publish", "archive"]
    # Restore returns it to the shelf, so an archived collection offers no
    # publish: putting it back in front of learners is a separate decision.
    retired = content.vocabulary_record(_collection(status="archived"))
    assert retired["actions"] == ["preview", "restore"]


def test_filter_search_sort_and_paginate_across_kinds():
    records = [
        content.book_record(_book()),
        content.book_record(_book(id="b2", title="Beijing Nights", language="zh", status="archived",
                                  updated_at="2026-09-16T00:00:00+00:00")),
        content.media_record(_entry(segments=None)),
        content.vocabulary_record(_collection()),
    ]
    assert content.content_counts(records) == {"all": 4, "book": 2, "media": 1, "vocabulary": 1}
    assert [r["id"] for r in content.filter_records(records, kind="book")] == ["b2", "b1"]
    assert [r["id"] for r in content.filter_records(records, language="zh")] == ["b2"]
    assert [r["id"] for r in content.filter_records(records, query="train")] == ["b1"]
    assert [r["id"] for r in content.filter_records(records, status="issues")] == ["toeic-core", "youtube-abc"]
    assert [r["id"] for r in content.filter_records(records, status="archived")] == ["b2"]
    assert [r["title"] for r in content.filter_records(records, sort="title")][:2] == ["Beijing Nights", "City walk"]
    items, total = content.paginate(content.filter_records(records), offset=1, limit=2)
    assert total == 4 and len(items) == 2


def test_history_merges_receipts_with_catalog_rows_and_reports_where_a_failure_happened():
    receipts = [
        {"id": "r1", "entity_type": "book", "entity_id": "", "created_at": "2026-09-17T09:00:00+00:00",
         "payload": {"kind": "book", "source": "broken.epub", "language": "en", "status": "error", "category": "malformed_epub"}},
        {"id": "r2", "entity_type": "book", "entity_id": "b1", "created_at": "2026-09-10T10:00:00+00:00",
         "payload": {"kind": "book", "source": "last-train.epub", "language": "en", "status": "ok", "title": "The Last Train",
                     "chapter_count": 12}},
        {"id": "r3", "entity_type": "media", "entity_id": "", "created_at": "2026-09-17T10:00:00+00:00",
         "payload": {"kind": "media", "source": "https://example.com/x.txt", "language": "en", "status": "error",
                     "detail": "This address is not a supported media file."}},
    ]
    vocabulary = [
        {"id": "v1", "filename": "core.csv", "status": "imported", "imported": 40, "skipped": 0, "duplicates": 2,
         "failed": 0, "error": "", "collection_id": "toeic-core", "collection_title": "TOEIC core",
         "collection_status": "pending_review", "created_at": "2026-09-11T00:00:00+00:00", "format": "csv"},
        {"id": "v2", "filename": "bad.csv", "status": "failed", "imported": 0, "skipped": 0, "duplicates": 0, "failed": 1,
         "error": "persistence unavailable: database down", "collection_id": "", "collection_title": "",
         "collection_status": "", "created_at": "2026-09-16T00:00:00+00:00", "format": "csv"},
    ]
    books = [_book(status="archived"), _book(id="b-old", title="Older", created_at="2026-09-01T00:00:00+00:00")]
    media = [_entry()]
    rows = content.history_rows(receipts=receipts, vocabulary_imports=vocabulary, books=books, media_entries=media)

    by_source = {row["source"]: row for row in rows}
    walk = "https://www.youtube.com/watch?v=abcdefghijk"
    assert [row["source"] for row in rows] == [
        "https://example.com/x.txt", "broken.epub", "bad.csv", walk, "core.csv", "last-train.epub", "Older",
    ]
    assert by_source["broken.epub"]["status"] == "failed"
    assert by_source["broken.epub"]["error"] == {"stage": "parse", "code": "malformed_epub", "message": ""}
    assert by_source["https://example.com/x.txt"]["error"]["stage"] == "source"
    assert by_source["bad.csv"]["error"] == {"stage": "persistence", "code": "vocabulary_import_failed",
                                             "message": "persistence unavailable: database down"}
    # The receipt says the import succeeded; the catalog says it was archived since.
    assert by_source["last-train.epub"]["status"] == "archived"
    assert by_source["Older"]["status"] == "published"
    assert by_source["Older"]["origin"] == "catalog"
    assert by_source["core.csv"]["status"] == "ready"
    assert by_source["core.csv"]["result"]["imported"] == 40
    assert by_source[walk]["status"] == "published"
    assert by_source[walk]["kind"] == "media"
    assert by_source[walk]["result"]["title"] == "City walk"
    assert [row["source"] for row in content.filter_history(rows, status="failed")] == [
        "https://example.com/x.txt", "broken.epub", "bad.csv",
    ]
    assert [row["source"] for row in content.filter_history(rows, kind="vocabulary")] == ["bad.csv", "core.csv"]


def test_recent_failures_count_only_failed_rows_inside_the_window():
    rows = [
        {"status": "failed", "created_at": "2026-09-17T00:00:00+00:00"},
        {"status": "failed", "created_at": "2026-08-01T00:00:00+00:00"},
        {"status": "published", "created_at": "2026-09-17T00:00:00+00:00"},
    ]
    assert content.recent_failures(rows, since="2026-09-11T00:00:00+00:00") == 1
