"""Which items have no thumbnail, and giving each a typographic cover (D-240).

The logic behind `scripts/audit_thumbnails.py` (read-only) and `scripts/backfill_typographic_covers.py` (dry run by
default). Kept here, with its stores passed in, so the same code is tested without a database or a container.

A published item "has a thumbnail" when a learner is shown one:
  * a Reading article - `ReadingContentRepository.list_published` carries a learner `image` for it,
  * a vocabulary collection - a thumbnail is stored in its `provenance` (a static, repository-less collection is served
    its typographic cover on request and is counted apart, never as missing),
  * a book - the ready book has a `cover_asset_key`,
  * a media item - its `thumbnail` is a provider-hosted address or a stored asset.

The backfill only ever adds Orena's own typographic cover (source 3 of the D-240 order). Real pictures are attached
by an administrator with their licence; this never touches an item that already has one.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from writing_coach import thumbnails

LANGUAGES = ("en", "zh")
KINDS = ("reading", "vocabulary", "book", "media")
BACKFILL_ACTOR = "orena:thumbnail-backfill"


@dataclass
class Sources:
    """The stores to read. Any may be None (that kind is then skipped and said so)."""

    reading: Any = None  # ReadingContentRepository
    reading_assets: Any = None  # BookAssetStore under READING_LIBRARY_ASSET_ROOT (articles, vocabulary, books)
    vocabulary: Any = None  # SQLAlchemyVocabularyRepository
    books: Any = None  # PostgresReadingLibraryRepository
    media: Any = None  # a MediaLibraryStore
    media_assets: Any = None  # BookAssetStore under MEDIA_LIBRARY_ASSET_ROOT


def _reading_missing(sources: Sources, include_unpublished: bool = False) -> list[dict[str, Any]]:
    from writing_coach.persistence.reading_content_repository import MAX_ARTICLE_PAGE

    found: list[dict[str, Any]] = []
    for language in LANGUAGES:
        cursor = None
        while True:
            page = sources.reading.list_published(language=language, cursor=cursor, limit=MAX_ARTICLE_PAGE)
            for row in page["items"]:
                if row.get("image") is None:
                    found.append({"kind": "reading", "id": row["id"], "title": row["title"], "language": row["language"],
                                  "topic": row.get("topic") or "", "published": True})
            cursor = page.get("next_cursor")
            if not cursor:
                break
    if include_unpublished:
        found.extend(_reading_unpublished_missing(sources))
    return found


def _reading_unpublished_missing(sources: Sources) -> list[dict[str, Any]]:
    """Articles still in review (draft, processing, needs_review, ready) with no thumbnail: the publish gate would
    refuse them with ThumbnailRequired (D-240)."""
    from writing_coach.persistence.reading_content_repository import MAX_ARTICLE_PAGE, QUEUE_STATUSES

    found: list[dict[str, Any]] = []
    cursor = None
    while True:
        page = sources.reading.list_queue(statuses=QUEUE_STATUSES, cursor=cursor, limit=MAX_ARTICLE_PAGE)
        for row in page["items"]:
            if not sources.reading.has_thumbnail(row["id"]):
                found.append(_reading_row(row))
        cursor = page.get("next_cursor")
        if not cursor:
            break
    return found


def _reading_row(row: dict[str, Any]) -> dict[str, Any]:
    status = str(row.get("status") or "")
    return {"kind": "reading", "id": str(row["id"]), "title": row.get("title") or "", "language": row.get("language") or "",
            "topic": row.get("topic") or "", "published": status == "published", "status": status}


def _vocabulary_missing(sources: Sources) -> tuple[list[dict[str, Any]], int]:
    found: list[dict[str, Any]] = []
    on_demand = 0
    from writing_coach.vocabulary_library import list_vocabulary_collections

    for language in LANGUAGES:
        on_demand += len(list_vocabulary_collections(language))
        if not sources.vocabulary.available():
            continue
        for collection in sources.vocabulary.list_collections(language) or []:
            if thumbnails.stored_thumbnail(collection.get("provenance")) is None:
                found.append({"kind": "vocabulary", "id": collection["id"], "title": collection.get("title", ""),
                              "language": collection.get("language_code", language),
                              "topic": collection.get("topic") or collection.get("framework") or "", "published": True})
    return found, on_demand


def _books_missing(sources: Sources) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for language in LANGUAGES:
        cursor = None
        while True:
            page = sources.books.list_books(learning_language=language, cursor=cursor, limit=50)
            for row in page["items"]:
                if not row.get("cover_asset_key"):
                    found.append({"kind": "book", "id": row["id"], "title": row["title"], "language": row["learning_language"],
                                  "topic": row.get("author") or "", "published": True})
            cursor = page.get("next_cursor")
            if not cursor:
                break
    return found


def _media_missing(sources: Sources, include_unpublished: bool) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for entry in sources.media.list(library="shared", status=None):
        published = entry.status == "published"
        if (published or include_unpublished) and not thumbnails.has_media_thumbnail(entry.thumbnail):
            found.append({"kind": "media", "id": entry.media_id, "title": entry.title, "language": entry.language,
                          "topic": str((entry.lesson or {}).get("topic") or "") if isinstance(entry.lesson, dict) else "",
                          "published": published, "status": entry.status})
    return found


def audit(sources: Sources, *, include_unpublished: bool = False) -> dict[str, Any]:
    """{kind: [missing rows]} for every kind that has a source, plus `skipped` kinds and counts. Read-only."""
    report: dict[str, Any] = {"missing": {}, "skipped": [], "static_vocabulary_served_on_demand": 0}
    for kind in KINDS:
        try:
            if kind == "reading" and sources.reading is not None:
                report["missing"]["reading"] = _reading_missing(sources, include_unpublished)
            elif kind == "vocabulary" and sources.vocabulary is not None:
                rows, on_demand = _vocabulary_missing(sources)
                report["missing"]["vocabulary"], report["static_vocabulary_served_on_demand"] = rows, on_demand
            elif kind == "book" and sources.books is not None:
                report["missing"]["book"] = _books_missing(sources)
            elif kind == "media" and sources.media is not None:
                report["missing"]["media"] = _media_missing(sources, include_unpublished)
            else:
                report["skipped"].append(kind)
        except Exception as exc:  # noqa: BLE001 - one unreadable store never hides the others
            report["skipped"].append(f"{kind}:{type(exc).__name__}")
    report["total_missing"] = sum(len(rows) for rows in report["missing"].values())
    return report


def _named_articles(sources: Sources, ids: tuple[str, ...]) -> tuple[list[dict[str, Any]], list[dict[str, Any]],
                                                                         list[dict[str, Any]]]:
    """(missing, already covered, not found) among the named Reading articles, whatever their status."""
    missing: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    for article_id in dict.fromkeys(ids):
        article = sources.reading.get_article(article_id)
        if article is None:
            unknown.append({"kind": "reading", "id": article_id, "title": "", "error": "not_found"})
        elif sources.reading.has_thumbnail(article_id):
            kept.append({"kind": "reading", "id": article_id, "title": article.get("title") or "",
                         "action": "kept_existing_thumbnail"})
        else:
            missing.append(_reading_row(article))
    return missing, kept, unknown


def backfill(sources: Sources, *, apply: bool = False, include_unpublished: bool = False,
             ids: tuple[str, ...] = ()) -> dict[str, Any]:
    """Give every published item without a thumbnail a typographic cover. Dry run unless `apply`.

    `include_unpublished` also covers items still in review (Reading articles and media). `ids` names Reading
    articles instead of sweeping: only those, whatever their status. An item that has any thumbnail is never touched,
    so running it twice adds nothing the second time."""
    done: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    if ids:
        if sources.reading is None:
            return {"dry_run": not apply, "skipped": ["reading"], "items": [],
                    "failed": [{"kind": "reading", "id": i, "title": "", "error": "no_store"} for i in ids]}
        missing, kept, unknown = _named_articles(sources, tuple(ids))
        found = {"missing": {"reading": missing}, "skipped": []}
        done.extend(kept)
        failed.extend(unknown)
    else:
        found = audit(sources, include_unpublished=include_unpublished)
    for kind, rows in found["missing"].items():
        for row in rows:
            outcome = {"kind": kind, "id": row["id"], "title": row["title"]}
            if not apply:
                done.append({**outcome, "action": "would_add_typographic_cover"})
                continue
            try:
                _add_cover(sources, kind, row)
                done.append({**outcome, "action": "typographic_cover_added"})
            except Exception as exc:  # noqa: BLE001 - one item never stops the others; its failure is reported
                failed.append({**outcome, "error": type(exc).__name__})
    return {"dry_run": not apply, "skipped": found["skipped"], "items": done, "failed": failed}


def _add_cover(sources: Sources, kind: str, row: dict[str, Any]) -> None:
    store = sources.reading_assets
    if kind == "reading":
        article = sources.reading.get_article(row["id"])
        stored = thumbnails.make_reading_cover(store, article_id=row["id"], title=article["title"],
                                               language=article["language"], topic=article.get("topic") or "")
        if not sources.reading.approve_image(row["id"], stored, actor=BACKFILL_ACTOR, reason="D-240 backfill"):
            raise LookupError(row["id"])
    elif kind == "vocabulary":
        stored = thumbnails.make_cover(store, "vocabulary", row["id"], title=row["title"], language=row["language"],
                                       topic=row["topic"], kind="vocabulary")
        sources.vocabulary.set_collection_thumbnail(row["id"], stored)
    elif kind == "book":
        record = thumbnails.typographic_record(row["title"], language=row["language"], topic=row["topic"], kind="book")
        key = f"books/{row['id']}/cover.svg"
        store.put(key, record["data"])
        if not sources.books.set_cover_key(row["id"], key):
            store.delete(key)
            raise LookupError(row["id"])
    elif kind == "media":
        entry = sources.media.get(row["id"])
        sources.media.upsert(thumbnails.media_entry_with_cover(entry, sources.media_assets))
    else:  # pragma: no cover - audit only yields the kinds above
        raise ValueError(kind)


def sources_from_environment(root: Any, url: str = "") -> Sources:
    """The stores the running product uses, found the way `app.py` finds them: `POSTGRES_RUNTIME_URL` (or `url`) for
    Reading, vocabulary and books, and the library/asset roots for media and every asset. A kind whose store cannot
    be opened is left out and reported as skipped."""
    import os
    from pathlib import Path

    from sqlalchemy import create_engine

    from writing_coach.book_asset_store import FilesystemBookAssetStore
    from writing_coach.media_library_store import FileMediaLibraryStore

    root = Path(root)
    reading_root = Path(os.getenv("READING_LIBRARY_ASSET_ROOT", str(root / "data" / "reading_library_assets")))
    media_root = Path(os.getenv("MEDIA_LIBRARY_ROOT", str(root / "data" / "media_library")))
    media_assets = Path(os.getenv("MEDIA_LIBRARY_ASSET_ROOT", str(root / "data" / "media_library_assets")))
    sources = Sources(reading_assets=FilesystemBookAssetStore(reading_root))
    if media_root.exists():
        sources.media = FileMediaLibraryStore(media_root)
        sources.media_assets = FilesystemBookAssetStore(media_assets)
    database = url or os.getenv("POSTGRES_RUNTIME_URL", "")
    if database:
        from writing_coach.persistence.reading_content_repository import ReadingContentRepository
        from writing_coach.persistence.reading_library_repository import PostgresReadingLibraryRepository
        from writing_coach.persistence.vocabulary_repository import SQLAlchemyVocabularyRepository

        engine = create_engine(database)
        sources.reading = ReadingContentRepository(engine)
        sources.vocabulary = SQLAlchemyVocabularyRepository(engine)
        sources.books = PostgresReadingLibraryRepository(engine)
    return sources
