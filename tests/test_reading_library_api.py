"""FastAPI TestClient coverage for writing_coach/reading_library_api.py.

Uses in-memory fakes for the repository and asset store (matching this
codebase's convention of testing a router against a fresh, minimal FastAPI
app - see tests/test_work_api.py) rather than a real PostgreSQL connection,
so admin-gating, batch partial-failure and not-found handling are provable
without a database. Real persistence is proven separately in
tests/test_reading_library_persistence_postgres.py.
"""
from __future__ import annotations

import io
import json
import uuid
import zipfile

import pytest

pytest.importorskip('fastapi')
from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from writing_coach import reading_library_api  # noqa: E402
from writing_coach.book_asset_store import AssetNotFound  # noqa: E402
from writing_coach.persistence.reading_library_repository import InvalidCursor  # noqa: E402


def _minimal_epub_bytes(title: str = "Fixture Book") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" '
            'version="1.0"><rootfiles><rootfile full-path="OEBPS/content.opf" '
            'media-type="application/oebps-package+xml"/></rootfiles></container>',
        )
        zf.writestr(
            "OEBPS/content.opf",
            '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
            '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
            f"<dc:title>{title}</dc:title><dc:language>en</dc:language></metadata>"
            '<manifest><item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/></manifest>'
            '<spine><itemref idref="c1"/></spine></package>',
        )
        zf.writestr(
            "OEBPS/c1.xhtml",
            '<html xmlns="http://www.w3.org/1999/xhtml"><body><p>Hello world.</p></body></html>',
        )
    return buffer.getvalue()


class FakeAssetStore:
    def __init__(self):
        self.data: dict[str, bytes] = {}

    def put(self, key, data):
        self.data[key] = data

    def get(self, key):
        if key not in self.data:
            raise AssetNotFound(key)
        return self.data[key]

    def exists(self, key):
        return key in self.data

    def delete(self, key):
        self.data.pop(key, None)


class FakeRepository:
    def __init__(self):
        self.books: dict[str, dict] = {}
        self.chapters: dict[tuple[str, str], dict] = {}
        self._by_hash: dict[str, str] = {}
        self.fail_create = False

    def get_book_by_hash(self, source_hash):
        book_id = self._by_hash.get(source_hash)
        if book_id is None:
            return None
        book = self.books.get(book_id)
        if book is None or book.get("status") == "archived":
            return None
        return {"id": book["id"], "title": book["title"], "chapter_count": book["chapter_count"]}

    def create_book(self, *, book_id, title, author, description, learning_language,
                    source_kind, source_hash, cover_asset_key, original_asset_key, imported_by, chapters):
        if self.fail_create:
            raise RuntimeError("simulated repository failure")
        existing = self._by_hash.get(source_hash)
        if existing is not None and self.books.get(existing, {}).get("status") != "archived":
            book = self.books[existing]
            return {"duplicate": True, "id": book["id"], "title": book["title"], "chapter_count": book["chapter_count"]}

        book_id_str = str(book_id)
        chapter_rows = []
        for position, chapter in enumerate(chapters):
            chapter_id = str(uuid.uuid4())
            row = {"id": chapter_id, "position": position, "title": chapter.title, "word_count": chapter.word_count}
            chapter_rows.append(row)
            self.chapters[(book_id_str, chapter_id)] = {
                **row, "content_asset_key": chapter.content_asset_key, "book_title": title,
                "author": author, "learning_language": learning_language, "content_revision": 1,
            }
        self.books[book_id_str] = {
            "id": book_id_str, "title": title, "author": author, "description": description,
            "learning_language": learning_language, "cover_asset_key": cover_asset_key,
            "chapter_count": len(chapters), "word_count": sum(c.word_count for c in chapters),
            "content_revision": 1, "chapters": chapter_rows, "status": "ready",
        }
        self._by_hash[source_hash] = book_id_str
        return {"duplicate": False, "id": book_id_str, "title": title, "chapter_count": len(chapters)}

    def list_books(self, *, learning_language, cursor=None, limit=24):
        if cursor == "broken":
            raise InvalidCursor(cursor)
        items = [
            b for b in self.books.values()
            if b["learning_language"] == learning_language and b.get("status") != "archived"
        ]
        return {"items": [{k: v for k, v in b.items() if k != "chapters"} for b in items], "next_cursor": None}

    def get_book(self, book_id):
        book = self.books.get(book_id)
        if book is None or book.get("status") == "archived":
            return None
        return book

    def get_chapter(self, book_id, chapter_id):
        return self.chapters.get((book_id, chapter_id))

    def archive_book(self, book_id):
        book = self.books.get(book_id)
        if book is None or book.get("status") == "archived":
            return False
        book["status"] = "archived"
        return True


def _admin_guard(request: Request):
    if request.headers.get("x-test-admin") != "1":
        raise HTTPException(403, "admin required")
    return {"email": "admin@test", "google_sub": "admin-sub"}


def _client(*, configured=True):
    repository = FakeRepository()
    asset_store = FakeAssetStore()
    reading_library_api.configure_reading_library(
        repository if configured else None,
        asset_store if configured else None,
        admin_guard=_admin_guard,
        language_supported=lambda code: code in {"en", "zh"},
    )
    app = FastAPI()
    app.include_router(reading_library_api.router)
    return TestClient(app), repository, asset_store


@pytest.fixture(autouse=True)
def _reset():
    yield
    reading_library_api.configure_reading_library(
        None, None, admin_guard=_admin_guard, language_supported=lambda code: False
    )


def test_import_requires_admin():
    client, _repo, _store = _client()
    response = client.post(
        "/api/reading/library/import",
        files=[("files", ("book.epub", _minimal_epub_bytes(), "application/epub+zip"))],
        data={"learning_language": "en"},
    )
    assert response.status_code == 403


def test_import_rejects_unsupported_language():
    client, _repo, _store = _client()
    response = client.post(
        "/api/reading/library/import",
        files=[("files", ("book.epub", _minimal_epub_bytes(), "application/epub+zip"))],
        data={"learning_language": "fr"},
        headers={"x-test-admin": "1"},
    )
    assert response.status_code == 422


def test_import_batch_one_bad_file_does_not_block_the_good_one():
    client, repo, _store = _client()
    response = client.post(
        "/api/reading/library/import",
        files=[
            ("files", ("good.epub", _minimal_epub_bytes("Good Book"), "application/epub+zip")),
            ("files", ("bad.epub", b"not an epub at all", "application/epub+zip")),
        ],
        data={"learning_language": "en"},
        headers={"x-test-admin": "1"},
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 2
    good, bad = results
    assert good["status"] == "ok" and good["title"] == "Good Book"
    assert bad["status"] == "error" and bad["category"] == "malformed_archive"
    # The good book actually landed in the repository.
    assert repo.get_book(good["book_id"]) is not None


def test_list_and_get_book_and_chapter_happy_path():
    client, repo, store = _client()
    upload = client.post(
        "/api/reading/library/import",
        files=[("files", ("book.epub", _minimal_epub_bytes("Listable"), "application/epub+zip"))],
        data={"learning_language": "en"},
        headers={"x-test-admin": "1"},
    )
    book_id = upload.json()["results"][0]["book_id"]

    listing = client.get("/api/reading/library/books", params={"learning_language": "en"})
    assert listing.status_code == 200
    assert any(item["id"] == book_id for item in listing.json()["items"])

    detail = client.get(f"/api/reading/library/books/{book_id}")
    assert detail.status_code == 200
    assert detail.json()["title"] == "Listable"
    assert detail.json()["provenance"] == {"source_url": "", "publisher": "", "rights": "", "date": ""}
    chapter_id = detail.json()["chapters"][0]["id"]

    chapter = client.get(f"/api/reading/library/books/{book_id}/chapters/{chapter_id}")
    assert chapter.status_code == 200
    assert chapter.json()["paragraphs"] == ["Hello world."]
    assert chapter.json()["blocks"] == [{"type": "paragraph", "text": "Hello world."}]
    chapter_key = repo.get_chapter(book_id, chapter_id)["content_asset_key"]
    assert json.loads(store.data[chapter_key]) == {
        "format": 2,
        "blocks": [{"type": "paragraph", "text": "Hello world."}],
        "paragraphs": ["Hello world."],
    }
    assert json.loads(store.data[f"books/{book_id}/manifest.json"]) == {
        "format": 2,
        "provenance": {"source_url": "", "publisher": "", "rights": "", "date": ""},
    }


def test_chapter_api_derives_blocks_for_a_format_one_asset():
    client, repo, store = _client()
    upload = client.post(
        "/api/reading/library/import",
        files=[("files", ("book.epub", _minimal_epub_bytes("Legacy"), "application/epub+zip"))],
        data={"learning_language": "en"},
        headers={"x-test-admin": "1"},
    )
    book_id = upload.json()["results"][0]["book_id"]
    chapter_id = repo.get_book(book_id)["chapters"][0]["id"]
    key = repo.get_chapter(book_id, chapter_id)["content_asset_key"]
    store.data[key] = b'{"paragraphs":["old one", "old two"]}'

    response = client.get(f"/api/reading/library/books/{book_id}/chapters/{chapter_id}")
    assert response.status_code == 200
    assert response.json()["blocks"] == [
        {"type": "paragraph", "text": "old one"}, {"type": "paragraph", "text": "old two"}
    ]


def test_book_api_returns_null_provenance_when_manifest_is_missing_or_unreadable():
    client, _repo, store = _client()
    upload = client.post(
        "/api/reading/library/import",
        files=[("files", ("book.epub", _minimal_epub_bytes("No Manifest"), "application/epub+zip"))],
        data={"learning_language": "en"},
        headers={"x-test-admin": "1"},
    )
    book_id = upload.json()["results"][0]["book_id"]
    store.data[f"books/{book_id}/manifest.json"] = b"not json"
    response = client.get(f"/api/reading/library/books/{book_id}")
    assert response.status_code == 200
    assert response.json()["provenance"] is None


def test_import_writes_manifest_and_rolls_it_back_with_other_assets_on_failure():
    client, repo, store = _client()
    repo.fail_create = True
    response = client.post(
        "/api/reading/library/import",
        files=[("files", ("book.epub", _minimal_epub_bytes("Rollback"), "application/epub+zip"))],
        data={"learning_language": "en"},
        headers={"x-test-admin": "1"},
    )
    assert response.json()["results"][0]["category"] == "storage_failed"
    assert not store.data


def test_reimporting_the_same_bytes_is_reported_as_duplicate_not_a_second_book():
    client, repo, _store = _client()
    same_bytes = _minimal_epub_bytes("Once Only")
    first = client.post(
        "/api/reading/library/import",
        files=[("files", ("book.epub", same_bytes, "application/epub+zip"))],
        data={"learning_language": "en"},
        headers={"x-test-admin": "1"},
    )
    first_result = first.json()["results"][0]
    assert first_result["status"] == "ok"

    second = client.post(
        "/api/reading/library/import",
        files=[("files", ("book-again.epub", same_bytes, "application/epub+zip"))],
        data={"learning_language": "en"},
        headers={"x-test-admin": "1"},
    )
    second_result = second.json()["results"][0]
    assert second_result["status"] == "duplicate"
    assert second_result["book_id"] == first_result["book_id"]
    assert second_result["title"] == "Once Only"
    # Only one book actually exists.
    listing = client.get("/api/reading/library/books", params={"learning_language": "en"})
    assert len(listing.json()["items"]) == 1


def test_archive_book_requires_admin_and_then_hides_it():
    client, repo, _store = _client()
    upload = client.post(
        "/api/reading/library/import",
        files=[("files", ("book.epub", _minimal_epub_bytes("Archive Me"), "application/epub+zip"))],
        data={"learning_language": "en"},
        headers={"x-test-admin": "1"},
    )
    book_id = upload.json()["results"][0]["book_id"]

    denied = client.post(f"/api/reading/library/books/{book_id}/archive")
    assert denied.status_code == 403

    archived = client.post(
        f"/api/reading/library/books/{book_id}/archive", headers={"x-test-admin": "1"}
    )
    assert archived.status_code == 200
    assert archived.json() == {"archived": True, "id": book_id}
    assert client.get(f"/api/reading/library/books/{book_id}").status_code == 404

    again = client.post(
        f"/api/reading/library/books/{book_id}/archive", headers={"x-test-admin": "1"}
    )
    assert again.status_code == 404


def test_reimporting_the_same_bytes_after_archiving_succeeds():
    """The duplicate guard is scoped to 'ready' rows only (a partial unique
    index in the real schema - see migrations/proposed/20260916_0009_
    reading_library.py) - archiving (the documented wrong-import recovery
    path) must not permanently block ever re-importing that exact file."""
    client, repo, _store = _client()
    same_bytes = _minimal_epub_bytes("Reimportable")
    first = client.post(
        "/api/reading/library/import",
        files=[("files", ("book.epub", same_bytes, "application/epub+zip"))],
        data={"learning_language": "en"},
        headers={"x-test-admin": "1"},
    )
    first_id = first.json()["results"][0]["book_id"]
    client.post(f"/api/reading/library/books/{first_id}/archive", headers={"x-test-admin": "1"})

    second = client.post(
        "/api/reading/library/import",
        files=[("files", ("book-again.epub", same_bytes, "application/epub+zip"))],
        data={"learning_language": "en"},
        headers={"x-test-admin": "1"},
    )
    second_result = second.json()["results"][0]
    assert second_result["status"] == "ok"
    assert second_result["book_id"] != first_id
    assert client.get(f"/api/reading/library/books/{second_result['book_id']}").status_code == 200


def test_get_book_not_found_is_404():
    client, _repo, _store = _client()
    response = client.get(f"/api/reading/library/books/{uuid.uuid4()}")
    assert response.status_code == 404


def test_get_cover_not_found_is_404():
    client, _repo, _store = _client()
    response = client.get(f"/api/reading/library/books/{uuid.uuid4()}/cover")
    assert response.status_code == 404


def test_invalid_cursor_is_422():
    client, _repo, _store = _client()
    response = client.get(
        "/api/reading/library/books", params={"learning_language": "en", "cursor": "broken"}
    )
    assert response.status_code == 422


def test_unconfigured_backend_is_503():
    client, _repo, _store = _client(configured=False)
    response = client.get("/api/reading/library/books", params={"learning_language": "en"})
    assert response.status_code == 503


def test_schema_not_applied_yet_is_503_not_a_raw_500():
    """The repository is configured (PostgreSQL backend selected) but the
    reviewed migration has not been applied yet - a real, expected state
    between this proposal shipping and it being approved. A learner must see
    the same truthful "unavailable" a fully-unconfigured deployment shows,
    never a raw database traceback."""
    from sqlalchemy.exc import ProgrammingError

    from writing_coach.reading_library_api import _call_repository

    def _boom():
        raise ProgrammingError("SELECT 1 FROM reading_books", {}, Exception('relation "reading_books" does not exist'))

    with pytest.raises(HTTPException) as excinfo:
        _call_repository(_boom)
    assert excinfo.value.status_code == 503


def test_an_id_that_is_not_a_uuid_is_not_found_rather_than_a_server_error():
    """The Library's own cards carry ids like `text:book-probe`, so a reader can
    arrive here with one. A string that cannot name a row is a miss, not a
    failure: PostgreSQL raises InvalidTextRepresentation when a non-UUID reaches
    a uuid column, which surfaced as a 500 on `#/book`."""
    client, _repo, _store = _client()
    for book_id in ("text:book-probe", "not-a-uuid", "12345"):
        response = client.get(f"/api/reading/library/books/{book_id}")
        assert response.status_code == 404, (book_id, response.status_code)
        chapter = client.get(f"/api/reading/library/books/{book_id}/chapters/{book_id}")
        assert chapter.status_code == 404, (book_id, chapter.status_code)


def test_a_malformed_id_never_reaches_the_database():
    """The guard has to be in the PostgreSQL repository, not only in the route:
    the 500 came from the driver casting the string to `uuid`. An engine that
    raises if it is touched proves the query is never built."""
    from writing_coach.persistence.reading_library_repository import (
        PostgresReadingLibraryRepository,
        _as_uuid,
    )

    class _ExplodingEngine:
        def connect(self):
            raise AssertionError("the database was queried with a malformed id")

        def begin(self):
            raise AssertionError("the database was queried with a malformed id")

    repository = PostgresReadingLibraryRepository(_ExplodingEngine())
    assert repository.get_book("text:book-probe") is None
    assert repository.get_chapter("text:book-probe", "also-not-a-uuid") is None
    assert repository.archive_book("text:book-probe") is False

    # A well-formed id is not swallowed: it reaches the engine.
    valid = "6f1b2c3d-4e5f-4a6b-8c9d-0e1f2a3b4c5d"
    assert _as_uuid(valid) is not None
    with pytest.raises(AssertionError, match="the database was queried"):
        repository.get_book(valid)
