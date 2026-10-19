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


# -- regenerating typographic covers ----------------------------------------------------------------------------------


def _reading_rows(sources: Sources, include_unpublished: bool, ids: tuple[str, ...]) -> list[dict[str, Any]]:
    """Every published Reading article (and, with `include_unpublished`, every one in review), or the named ones."""
    from writing_coach.persistence.reading_content_repository import MAX_ARTICLE_PAGE, QUEUE_STATUSES

    rows: list[dict[str, Any]] = []
    if ids:
        for article_id in dict.fromkeys(ids):
            article = sources.reading.get_article(article_id)
            rows.append(_reading_row(article) if article is not None else {"kind": "reading", "id": article_id, "missing": True})
        return rows
    for language in LANGUAGES:
        cursor = None
        while True:
            page = sources.reading.list_published(language=language, cursor=cursor, limit=MAX_ARTICLE_PAGE)
            rows.extend({"kind": "reading", "id": row["id"], "title": row["title"], "language": row["language"],
                         "topic": row.get("topic") or ""} for row in page["items"])
            cursor = page.get("next_cursor")
            if not cursor:
                break
    if include_unpublished:
        cursor = None
        while True:
            page = sources.reading.list_queue(statuses=QUEUE_STATUSES, cursor=cursor, limit=MAX_ARTICLE_PAGE)
            rows.extend(_reading_row(row) for row in page["items"])
            cursor = page.get("next_cursor")
            if not cursor:
                break
    return rows


def _book_cover(store: Any, row: dict[str, Any]) -> tuple[str | None, str]:
    """(provenance kind or None, sha256 of the stored bytes) of a book's cover. A book's provenance sits beside its
    cover (`cover.provenance.json`); a cover the backfill made before that record existed is recognised as Orena's
    own by its key and its generator's opening bytes. Anything else is a real picture."""
    import hashlib
    import json

    key = row["key"]
    if not key:
        return None, ""
    kind = ""
    record_key = f"books/{row['id']}/cover.provenance.json"
    try:
        if store.exists(record_key):
            kind = str(json.loads(store.get(record_key)).get("kind") or "")
    except (ValueError, OSError, AttributeError):
        kind = ""
    if not kind:
        own = (key == f"books/{row['id']}/cover.svg" and store.exists(key)
               and store.get(key).startswith(thumbnails._OWN_COVER_HEAD))
        kind = thumbnails.KIND_TYPOGRAPHIC if own else thumbnails.KIND_SOURCE_IMAGE
    if kind != thumbnails.KIND_TYPOGRAPHIC:
        return kind, ""
    return kind, hashlib.sha256(store.get(key)).hexdigest() if store.exists(key) else ""


def _typographic_targets(sources: Sources, include_unpublished: bool, ids: tuple[str, ...]):
    """(row, current sha256, reason) for every item a learner may be shown; `reason` is '' for a typographic cover.

    Only a cover whose recorded provenance kind is typographic is a target. A real picture (a source or library image,
    an EPUB's own cover, a provider-hosted thumbnail) is reported as kept; an item with no thumbnail is `backfill`'s."""
    def classify(row: dict[str, Any], stored: Any) -> tuple[dict[str, Any], str, str]:
        if not stored:
            return row, "", "no_thumbnail"
        if stored.get("kind") != thumbnails.KIND_TYPOGRAPHIC:
            return row, "", "kept_real_image"
        return row, str(stored.get("sha256") or ""), ""

    if sources.reading is not None:
        for row in _reading_rows(sources, include_unpublished, ids):
            if row.get("missing"):
                yield {"kind": "reading", "id": row["id"], "title": ""}, "", "not_found"
            else:
                yield classify(row, sources.reading.published_thumbnail(row["id"]))
    if ids:
        return  # `--id` names Reading articles only
    if sources.vocabulary is not None and sources.vocabulary.available():
        for language in LANGUAGES:
            for collection in sources.vocabulary.list_collections(language) or []:
                row = {"kind": "vocabulary", "id": collection["id"], "title": collection.get("title", ""),
                       "language": collection.get("language_code", language),
                       "topic": collection.get("topic") or collection.get("framework") or ""}
                yield classify(row, thumbnails.stored_thumbnail(collection.get("provenance")))
    if sources.books is not None:
        for language in LANGUAGES:
            cursor = None
            while True:
                page = sources.books.list_books(learning_language=language, cursor=cursor, limit=50)
                for book in page["items"]:
                    row = {"kind": "book", "id": book["id"], "title": book["title"], "language": book["learning_language"],
                           "topic": book.get("author") or "", "key": book.get("cover_asset_key") or ""}
                    kind, digest = _book_cover(sources.reading_assets, row)
                    yield classify(row, {"kind": kind, "sha256": digest} if kind else None)
                cursor = page.get("next_cursor")
                if not cursor:
                    break
    if sources.media is not None:
        for entry in sources.media.list(library="shared", status=None):
            if entry.status != "published" and not include_unpublished:
                continue
            row = {"kind": "media", "id": entry.media_id, "title": entry.title, "language": entry.language,
                   "topic": str((entry.lesson or {}).get("topic") or "") if isinstance(entry.lesson, dict) else ""}
            if not thumbnails.has_media_thumbnail(entry.thumbnail):
                yield row, "", "no_thumbnail"
                continue
            provenance = thumbnails.media_thumbnail_provenance(entry.source) or {}
            if entry.thumbnail.get("kind") != "asset" or provenance.get("kind") != thumbnails.KIND_TYPOGRAPHIC:
                yield row, "", "kept_real_image"
                continue
            # A media cover's key carries the first 24 hex digits of its hash (`media_cover_key`).
            yield row, str(entry.thumbnail.get("ref") or "").rsplit("thumb-", 1)[-1].split(".", 1)[0], ""


def regenerate(sources: Sources, *, apply: bool = False, include_unpublished: bool = False,
               ids: tuple[str, ...] = ()) -> dict[str, Any]:
    """Remake every typographic cover with the current generator. Dry run unless `apply`.

    Only a cover whose provenance kind is typographic is replaced: a real picture is never touched, and an item with
    no thumbnail is left to `backfill`. A cover the current generator draws identically is left as it is, so a second
    run changes nothing. The new cover is stored under its own content-addressed key (a book's in place, with its
    provenance record) and recorded as the backfill records one; the old file stays in the asset store."""
    done: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    skipped = [kind for kind, store in (("reading", sources.reading), ("vocabulary", sources.vocabulary),
                                         ("book", sources.books), ("media", sources.media)) if store is None]
    for row, current, reason in _typographic_targets(sources, include_unpublished, tuple(ids)):
        outcome = {"kind": row["kind"], "id": row["id"], "title": row.get("title", "")}
        if reason == "not_found":
            failed.append({**outcome, "error": "not_found"})
            continue
        if reason:
            done.append({**outcome, "action": reason})
            continue
        fresh = thumbnails.typographic_record(row["title"], language=row.get("language", ""), topic=row.get("topic", ""),
                                              kind=row["kind"])["sha256"]
        if current and fresh.startswith(current):
            done.append({**outcome, "action": "typographic_cover_current"})
        elif not apply:
            done.append({**outcome, "action": "would_regenerate_typographic_cover"})
        else:
            try:
                _replace_cover(sources, row)
                done.append({**outcome, "action": "typographic_cover_regenerated"})
            except Exception as exc:  # noqa: BLE001 - one item never stops the others; its failure is reported
                failed.append({**outcome, "error": type(exc).__name__})
    return {"dry_run": not apply, "skipped": skipped, "items": done, "failed": failed}


def _replace_cover(sources: Sources, row: dict[str, Any]) -> None:
    import json

    kind = row["kind"]
    if kind == "book":
        record = thumbnails.typographic_record(row["title"], language=row["language"], topic=row["topic"], kind="book")
        provenance = {**thumbnails.normalize_provenance({}, kind=thumbnails.KIND_TYPOGRAPHIC), "sha256": record["sha256"]}
        sources.reading_assets.put(row["key"], record["data"])
        sources.reading_assets.put(f"books/{row['id']}/cover.provenance.json", json.dumps(provenance).encode("utf-8"))
    elif kind == "reading":
        article = sources.reading.get_article(row["id"])
        stored = thumbnails.make_reading_cover(sources.reading_assets, article_id=row["id"], title=article["title"],
                                               language=article["language"], topic=article.get("topic") or "")
        if not sources.reading.approve_image(row["id"], stored, actor=BACKFILL_ACTOR,
                                             reason="D-240 typographic cover regenerated"):
            raise LookupError(row["id"])
    else:
        _add_cover(sources, kind, row)  # vocabulary and media: the same cover maker, which replaces what is recorded


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
