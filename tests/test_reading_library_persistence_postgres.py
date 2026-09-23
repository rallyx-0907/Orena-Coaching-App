"""Reading Library catalog persistence proof. Real PostgreSQL.

Skips unless `ORENA_TEST_POSTGRES_URL` names a throwaway database. This file
follows the same shape as `tests/test_orena_quota_persistence_postgres.py`:
the module-scoped `engine` fixture runs the *applied* migration chain
(`migrations/versions/`) to head, so it only exercises `reading_books`/
`reading_book_chapters` once `migrations/proposed/20260916_0009_reading_
library.py` has been reviewed and moved there - the same "not runnable to
success until moved" state I3's own persistence test was in before its
review completed. The standalone rehearsal against both `versions/` and
`proposed/` (up/down/up, proving the migration itself is sound before it is
moved) is reported separately, not duplicated as a second test file here.

    ORENA_TEST_POSTGRES_URL=postgresql+psycopg://user:pw@host/orena_reading_test \\
        python -m pytest tests/test_reading_library_persistence_postgres.py
"""
from __future__ import annotations

import hashlib
import os
import uuid

import pytest

sqlalchemy = pytest.importorskip('sqlalchemy')
from sqlalchemy import create_engine, text  # noqa: E402

from writing_coach.persistence.reading_library_repository import (  # noqa: E402
    ChapterInput,
    InvalidCursor,
    PostgresReadingLibraryRepository,
)

URL = os.getenv('ORENA_TEST_POSTGRES_URL', '')
pytestmark = pytest.mark.skipif(
    not URL, reason='ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run'
)


@pytest.fixture(scope='module')
def engine():
    from alembic import command
    from writing_coach.persistence.runtime import _runtime_alembic_config

    cfg = _runtime_alembic_config()
    cfg.set_main_option('sqlalchemy.url', URL.replace('%', '%%'))
    command.upgrade(cfg, 'head')
    engine = create_engine(URL, future=True)
    yield engine
    engine.dispose()


def _has_reading_tables(engine) -> bool:
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT to_regclass('reading_books') IS NOT NULL")
        ).scalar_one()


@pytest.fixture(autouse=True)
def _require_schema(engine):
    if not _has_reading_tables(engine):
        pytest.skip(
            'reading_books is not in the applied migration chain yet - '
            'migrations/proposed/20260916_0009_reading_library.py has not been '
            'reviewed and moved into migrations/versions/.'
        )


def _sample_chapters() -> list[ChapterInput]:
    return [
        ChapterInput(chapter_key='c1', title='Chapter One', content_asset_key='books/x/chapters/0.json', word_count=100),
        ChapterInput(chapter_key='c2', title='Chapter Two', content_asset_key='books/x/chapters/1.json', word_count=80),
    ]


def _hash_for(label: str) -> str:
    """A distinct, deterministic fake source_hash per test - the UNIQUE
    constraint means every book in this file needs its own to avoid
    colliding with an unrelated test's row."""
    return hashlib.sha256(f'{label}-{uuid.uuid4()}'.encode()).hexdigest()


def test_create_book_then_get_book_returns_it_with_ordered_chapters(engine):
    repository = PostgresReadingLibraryRepository(engine)
    book_id = uuid.uuid4()
    created = repository.create_book(
        book_id=book_id, title='A Test Book', author='Tester', description='desc',
        learning_language='en', source_kind='epub', source_hash=_hash_for('roundtrip'),
        cover_asset_key=None,
        original_asset_key=f'books/{book_id}/original.epub', imported_by='admin@test',
        chapters=_sample_chapters(),
    )
    assert created['duplicate'] is False
    assert created['id'] == str(book_id)
    assert created['chapter_count'] == 2

    fetched = repository.get_book(str(book_id))
    assert fetched is not None
    assert fetched['title'] == 'A Test Book'
    assert [c['title'] for c in fetched['chapters']] == ['Chapter One', 'Chapter Two']
    assert [c['position'] for c in fetched['chapters']] == [0, 1]


def test_get_chapter_returns_its_own_book_metadata(engine):
    repository = PostgresReadingLibraryRepository(engine)
    book_id = uuid.uuid4()
    repository.create_book(
        book_id=book_id, title='Chapter Lookup', author='', description='',
        learning_language='en', source_kind='epub', source_hash=_hash_for('chapter-lookup'),
        cover_asset_key=None,
        original_asset_key=f'books/{book_id}/original.epub', imported_by='admin@test',
        chapters=_sample_chapters(),
    )
    book = repository.get_book(str(book_id))
    first_chapter_id = book['chapters'][0]['id']
    chapter = repository.get_chapter(str(book_id), first_chapter_id)
    assert chapter is not None
    assert chapter['book_title'] == 'Chapter Lookup'
    assert chapter['content_asset_key'] == 'books/x/chapters/0.json'

    assert repository.get_chapter(str(book_id), str(uuid.uuid4())) is None
    assert repository.get_chapter(str(uuid.uuid4()), first_chapter_id) is None


def test_list_books_only_returns_the_requested_language(engine):
    repository = PostgresReadingLibraryRepository(engine)
    en_id, zh_id = uuid.uuid4(), uuid.uuid4()
    repository.create_book(
        book_id=en_id, title='English Book', author='', description='',
        learning_language='en', source_kind='epub', source_hash=_hash_for('en-book'),
        cover_asset_key=None,
        original_asset_key=f'books/{en_id}/original.epub', imported_by='admin@test',
        chapters=_sample_chapters(),
    )
    repository.create_book(
        book_id=zh_id, title='Chinese Book', author='', description='',
        learning_language='zh', source_kind='epub', source_hash=_hash_for('zh-book'),
        cover_asset_key=None,
        original_asset_key=f'books/{zh_id}/original.epub', imported_by='admin@test',
        chapters=_sample_chapters(),
    )
    en_page = repository.list_books(learning_language='en', limit=50)
    assert any(item['id'] == str(en_id) for item in en_page['items'])
    assert not any(item['id'] == str(zh_id) for item in en_page['items'])


def test_list_books_pagination_covers_every_item_exactly_once(engine):
    repository = PostgresReadingLibraryRepository(engine)
    language = f'pg-{uuid.uuid4().hex[:8]}'
    created_ids = set()
    for index in range(5):
        book_id = uuid.uuid4()
        created_ids.add(str(book_id))
        repository.create_book(
            book_id=book_id, title=f'Book {index}', author='', description='',
            learning_language=language, source_kind='epub', source_hash=_hash_for(f'page-{index}'),
            cover_asset_key=None,
            original_asset_key=f'books/{book_id}/original.epub', imported_by='admin@test',
            chapters=_sample_chapters(),
        )
    seen_ids = set()
    cursor = None
    pages = 0
    while True:
        page = repository.list_books(learning_language=language, cursor=cursor, limit=2)
        seen_ids.update(item['id'] for item in page['items'])
        pages += 1
        cursor = page['next_cursor']
        if not cursor:
            break
        assert pages < 10  # guard against an infinite loop if pagination regresses
    assert seen_ids == created_ids
    assert pages >= 3  # 5 items at 2/page: at least 3 pages


def test_invalid_cursor_is_a_named_error(engine):
    repository = PostgresReadingLibraryRepository(engine)
    with pytest.raises(InvalidCursor):
        repository.list_books(learning_language='en', cursor='not-a-real-cursor')


def test_deleting_a_book_cascades_its_chapters(engine):
    repository = PostgresReadingLibraryRepository(engine)
    book_id = uuid.uuid4()
    repository.create_book(
        book_id=book_id, title='To Delete', author='', description='',
        learning_language='en', source_kind='epub', source_hash=_hash_for('to-delete'),
        cover_asset_key=None,
        original_asset_key=f'books/{book_id}/original.epub', imported_by='admin@test',
        chapters=_sample_chapters(),
    )
    with engine.begin() as connection:
        connection.execute(text('DELETE FROM reading_books WHERE id = :id'), {'id': book_id})
        remaining = connection.execute(
            text('SELECT count(*) FROM reading_book_chapters WHERE book_id = :id'), {'id': book_id}
        ).scalar_one()
    assert remaining == 0


def test_duplicate_source_hash_is_reported_not_inserted_twice(engine):
    repository = PostgresReadingLibraryRepository(engine)
    shared_hash = _hash_for('duplicate')
    first_id = uuid.uuid4()
    first = repository.create_book(
        book_id=first_id, title='Original Import', author='', description='',
        learning_language='en', source_kind='epub', source_hash=shared_hash,
        cover_asset_key=None,
        original_asset_key=f'books/{first_id}/original.epub', imported_by='admin@test',
        chapters=_sample_chapters(),
    )
    assert first['duplicate'] is False

    second_id = uuid.uuid4()
    second = repository.create_book(
        book_id=second_id, title='Re-upload Of The Same File', author='', description='',
        learning_language='en', source_kind='epub', source_hash=shared_hash,
        cover_asset_key=None,
        original_asset_key=f'books/{second_id}/original.epub', imported_by='admin@test',
        chapters=_sample_chapters(),
    )
    assert second['duplicate'] is True
    assert second['id'] == str(first_id)
    assert second['title'] == 'Original Import'
    assert repository.get_book(str(second_id)) is None  # no second row was created

    found = repository.get_book_by_hash(shared_hash)
    assert found is not None and found['id'] == str(first_id)


def test_archive_book_hides_it_from_list_and_get_but_not_the_row(engine):
    repository = PostgresReadingLibraryRepository(engine)
    book_id = uuid.uuid4()
    language = f'pg-archive-{uuid.uuid4().hex[:8]}'
    repository.create_book(
        book_id=book_id, title='To Archive', author='', description='',
        learning_language=language, source_kind='epub', source_hash=_hash_for('to-archive'),
        cover_asset_key=None,
        original_asset_key=f'books/{book_id}/original.epub', imported_by='admin@test',
        chapters=_sample_chapters(),
    )
    assert repository.archive_book(str(book_id)) is True
    assert repository.get_book(str(book_id)) is None
    assert not repository.list_books(learning_language=language, limit=50)['items']
    # Archiving again finds nothing left in 'ready' to archive.
    assert repository.archive_book(str(book_id)) is False
    # The row itself, and its chapters, still exist - archive is not delete.
    with engine.connect() as connection:
        status = connection.execute(
            text('SELECT status FROM reading_books WHERE id = :id'), {'id': book_id}
        ).scalar_one()
        chapter_count = connection.execute(
            text('SELECT count(*) FROM reading_book_chapters WHERE book_id = :id'), {'id': book_id}
        ).scalar_one()
    assert status == 'archived'
    assert chapter_count == 2


def test_archive_unknown_book_id_returns_false(engine):
    repository = PostgresReadingLibraryRepository(engine)
    assert repository.archive_book(str(uuid.uuid4())) is False


def test_reimporting_the_same_hash_after_archiving_succeeds(engine):
    """The UNIQUE constraint is a partial index (status = 'ready' only) -
    reviewer-requested (round 2, P3): archiving must not permanently block
    re-importing that exact file, since archive is the documented recovery
    path for a wrong/duplicate import."""
    repository = PostgresReadingLibraryRepository(engine)
    shared_hash = _hash_for('reimport-after-archive')
    first_id = uuid.uuid4()
    repository.create_book(
        book_id=first_id, title='First Import', author='', description='',
        learning_language='en', source_kind='epub', source_hash=shared_hash,
        cover_asset_key=None,
        original_asset_key=f'books/{first_id}/original.epub', imported_by='admin@test',
        chapters=_sample_chapters(),
    )
    assert repository.archive_book(str(first_id)) is True

    second_id = uuid.uuid4()
    second = repository.create_book(
        book_id=second_id, title='Reimport After Archive', author='', description='',
        learning_language='en', source_kind='epub', source_hash=shared_hash,
        cover_asset_key=None,
        original_asset_key=f'books/{second_id}/original.epub', imported_by='admin@test',
        chapters=_sample_chapters(),
    )
    assert second['duplicate'] is False
    assert second['id'] == str(second_id)
    assert repository.get_book(str(second_id)) is not None
    # The hash now points at the fresh 'ready' book, not the archived one.
    found = repository.get_book_by_hash(shared_hash)
    assert found is not None and found['id'] == str(second_id)


def test_archiving_a_book_is_a_door_that_opens_both_ways(engine):
    """`archive_book` was the only recovery path an operator had for a wrong
    import, and it was irreversible - which makes it a path nobody presses.
    Restoring returns the book and everything under it; nothing was removed."""
    repository = PostgresReadingLibraryRepository(engine)
    book_id = uuid.uuid4()
    repository.create_book(
        book_id=book_id, title='Reversible', author='Tester', description='',
        learning_language='en', source_kind='epub', source_hash=_hash_for('reversible'),
        cover_asset_key=None, original_asset_key=f'books/{book_id}/original.epub',
        imported_by='admin@test', chapters=_sample_chapters(),
    )
    assert repository.get_book(str(book_id)) is not None

    assert repository.archive_book(str(book_id)) is True
    assert repository.get_book(str(book_id)) is None, 'a learner cannot reach an archived book'

    assert repository.restore_book(str(book_id)) is True
    restored = repository.get_book(str(book_id))
    assert restored is not None and restored['title'] == 'Reversible'
    assert [c['title'] for c in restored['chapters']] == ['Chapter One', 'Chapter Two']

    # Restoring something that is not archived changes nothing and says so.
    assert repository.restore_book(str(book_id)) is False
