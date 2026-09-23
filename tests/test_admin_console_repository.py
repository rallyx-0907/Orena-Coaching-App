"""Reads behind the Platform Admin control center, against the real models.

SQLite stands in for PostgreSQL here only so the suite stays hermetic; the
repository speaks portable SQL, and the runtime reads PostgreSQL.
"""
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from writing_coach.persistence.admin_repository import AdminConsoleRepository
from writing_coach.persistence.models import (
    AuditLog,
    Base,
    Essay,
    GrammarProgress,
    ListeningProgress,
    ReadingAttempt,
    ReadingSession,
    SavedWord,
    ShadowingProgress,
    SpeakingAttempt,
    User,
    UserLanguageProfile,
    VocabularyCollection,
    VocabularyCollectionMembership,
    VocabularyEntry,
    VocabularySourceImport,
)

NOW = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)


def _uid(name):
    return uuid.uuid5(uuid.NAMESPACE_DNS, name)


@pytest.fixture()
def engine():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE reading_books (id CHAR(32) PRIMARY KEY, title VARCHAR(240) NOT NULL, "
            "author VARCHAR(240) NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '', "
            "learning_language VARCHAR(8) NOT NULL, source_kind VARCHAR(20) NOT NULL, "
            "source_hash VARCHAR(64) NOT NULL, status VARCHAR(20) NOT NULL DEFAULT 'ready', "
            "chapter_count INTEGER NOT NULL, content_revision INTEGER NOT NULL DEFAULT 1, "
            "cover_asset_key VARCHAR(400), original_asset_key VARCHAR(400) NOT NULL, "
            "word_count INTEGER NOT NULL DEFAULT 0, imported_by VARCHAR(200) NOT NULL DEFAULT '', "
            "created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL)"
        ))
        connection.execute(text(
            "CREATE TABLE reading_book_chapters (id CHAR(32) PRIMARY KEY, book_id CHAR(32) NOT NULL, "
            "position INTEGER NOT NULL, chapter_key VARCHAR(200) NOT NULL DEFAULT '', title VARCHAR(240) NOT NULL, "
            "content_asset_key VARCHAR(400) NOT NULL, word_count INTEGER NOT NULL DEFAULT 0, created_at DATETIME NOT NULL)"
        ))
    return engine


def _seed_people(engine):
    with Session(engine) as session, session.begin():
        session.add_all([
            User(id=_uid("ana"), user_key="sub-ana", email="ana.nguyen@example.com", name="Ana Nguyen", role="user",
                 created_at=NOW - timedelta(days=60), last_login=NOW - timedelta(days=1)),
            User(id=_uid("bo"), user_key="sub-bo", email="bo@example.com", name="Bo Li", role="user",
                 created_at=NOW - timedelta(days=3), last_login=NOW - timedelta(days=3)),
            User(id=_uid("cy"), user_key="sub-cy", email="cy@example.com", name="", role="admin",
                 created_at=NOW - timedelta(days=200), last_login=None),
        ])
        session.add_all([
            UserLanguageProfile(id=uuid.uuid4(), user_id=_uid("ana"), language_code="en", native_language="vi",
                                created_at=NOW - timedelta(days=60), updated_at=NOW - timedelta(days=60)),
            UserLanguageProfile(id=uuid.uuid4(), user_id=_uid("ana"), language_code="zh", native_language="vi",
                                created_at=NOW - timedelta(days=30), updated_at=NOW - timedelta(days=30)),
            UserLanguageProfile(id=uuid.uuid4(), user_id=_uid("bo"), language_code="zh", native_language="en",
                                created_at=NOW - timedelta(days=3), updated_at=NOW - timedelta(days=3)),
        ])
        session.add_all([
            Essay(id=uuid.uuid4(), user_id=_uid("ana"), language_code="en", legacy_id=1,
                  created_at=NOW - timedelta(days=40), text="private essay text that must never leave"),
            Essay(id=uuid.uuid4(), user_id=_uid("ana"), language_code="en", legacy_id=2,
                  created_at=NOW - timedelta(days=2), text="another private essay"),
            ReadingSession(id=_uid("rs1"), user_id=_uid("bo"), language_code="zh", legacy_id=1,
                           created_at=NOW - timedelta(days=2), passage="private passage"),
            ListeningProgress(id=uuid.uuid4(), user_id=_uid("bo"), language_code="zh", asset_id="a1",
                              segment_id="s1", updated_at=NOW - timedelta(days=1)),
            SavedWord(id=uuid.uuid4(), user_id=_uid("ana"), language_code="zh", word="学习", normalized_word="学习",
                      added_at=NOW - timedelta(days=5), updated_at=NOW - timedelta(days=5),
                      last_reviewed_at=NOW - timedelta(hours=3)),
        ])
    with Session(engine) as session, session.begin():
        session.add(ReadingAttempt(id=uuid.uuid4(), session_id=_uid("rs1"), legacy_id=1,
                                   created_at=NOW - timedelta(days=1), total=3, correct_count=2))
        session.add(SpeakingAttempt(id=uuid.uuid4(), user_id=_uid("bo"), language_code="zh", take_id="t1",
                                    reference_text="private", transcript_text="private", created_at=NOW - timedelta(hours=5)))
        session.add(ShadowingProgress(id=uuid.uuid4(), user_id=_uid("ana"), language_code="en", asset_id="a2",
                                      segment_id="s2", updated_at=NOW - timedelta(days=10)))
        session.add(GrammarProgress(id=uuid.uuid4(), user_id=_uid("ana"), language_code="en", lesson_id="g1",
                                    completed_at=NOW - timedelta(days=20)))


def test_account_totals_and_registrations_by_day(engine):
    _seed_people(engine)
    repo = AdminConsoleRepository(engine)
    totals = repo.account_totals(now=NOW)
    assert totals == {"total": 3, "admins": 1, "new_7d": 1, "new_30d": 1}
    by_day = repo.registrations_by_day(NOW - timedelta(days=30))
    assert by_day == {(NOW - timedelta(days=3)).date().isoformat(): 1}


def test_language_profiles_count_learners_per_learning_language(engine):
    _seed_people(engine)
    assert AdminConsoleRepository(engine).language_profiles() == [
        {"language": "zh", "learners": 2},
        {"language": "en", "learners": 1},
    ]


def test_activity_rows_group_every_domain_by_learner_day_domain_and_language(engine):
    _seed_people(engine)
    rows = AdminConsoleRepository(engine).activity_rows(NOW - timedelta(days=7))
    simplified = sorted((row["user_id"], row["domain"], row["language"], row["events"]) for row in rows)
    assert simplified == sorted([
        (str(_uid("ana")), "writing", "en", 1),
        (str(_uid("ana")), "vocabulary", "zh", 1),
        (str(_uid("ana")), "vocabulary", "zh", 1),
        (str(_uid("bo")), "reading", "zh", 1),
        (str(_uid("bo")), "reading", "zh", 1),
        (str(_uid("bo")), "listening", "zh", 1),
        (str(_uid("bo")), "speaking", "zh", 1),
    ])
    assert all(len(str(row["day"])) >= 10 for row in rows)
    assert "private" not in repr(rows)


def test_first_activity_by_user_covers_all_time(engine):
    _seed_people(engine)
    first = AdminConsoleRepository(engine).first_activity_by_user()
    assert set(first) == {str(_uid("ana")), str(_uid("bo"))}
    assert first[str(_uid("ana"))].date() == (NOW - timedelta(days=40)).date()


def test_list_accounts_masks_identity_filters_and_paginates(engine):
    _seed_people(engine)
    repo = AdminConsoleRepository(engine)
    page = repo.list_accounts(now=NOW, limit=2, offset=0)
    assert page["total"] == 3
    assert [item["display_name"] for item in page["items"]] == ["Bo Li", "Ana Nguyen"]
    first = page["items"][0]
    # A two-letter local part would be shown whole by a "first two" rule; the
    # mask never reveals the entire local part.
    assert first["email_masked"] == "b•••@example.com"
    assert "email" not in first
    assert first["languages"] == ["zh"]
    assert first["level"] is None
    assert first["status"] == "active"
    assert first["last_active_at"].startswith((NOW - timedelta(hours=5)).date().isoformat())

    never = repo.list_accounts(now=NOW, activity="never")
    assert [item["role"] for item in never["items"]] == ["admin"]
    assert never["items"][0]["status"] == "no_activity"

    zh = repo.list_accounts(now=NOW, language="zh", sort="name")
    assert [item["display_name"] for item in zh["items"]] == ["Ana Nguyen", "Bo Li"]

    search = repo.list_accounts(now=NOW, query="ANA.NG")
    assert [item["display_name"] for item in search["items"]] == ["Ana Nguyen"]

    active_order = repo.list_accounts(now=NOW, sort="active")
    assert [item["display_name"] for item in active_order["items"]][:2] == ["Ana Nguyen", "Bo Li"]


def test_account_detail_reports_counts_by_domain_and_language_without_content(engine):
    _seed_people(engine)
    detail = AdminConsoleRepository(engine).account_detail(str(_uid("ana")), now=NOW)
    assert detail["email"] == "ana.nguyen@example.com"
    assert [profile["language"] for profile in detail["profiles"]] == ["en", "zh"]
    assert detail["profiles"][0]["support_language"] == "vi"
    counts = {(row["measure"], row["language"]): row["count"] for row in detail["activity"]}
    assert counts[("writing_submissions", "en")] == 2
    assert counts[("words_kept", "zh")] == 1
    assert counts[("words_reviewed", "zh")] == 1
    assert counts[("shadowing_segments", "en")] == 1
    assert counts[("grammar_lessons", "en")] == 1
    assert "private" not in repr(detail)
    assert AdminConsoleRepository(engine).account_detail(str(uuid.uuid4()), now=NOW) is None
    assert AdminConsoleRepository(engine).account_detail("not-a-uuid", now=NOW) is None


def test_books_are_listed_in_every_status_and_detailed_with_chapters(engine):
    book_id = uuid.uuid4()
    with engine.begin() as connection:
        for identifier, status, updated in ((book_id, "ready", NOW), (uuid.uuid4(), "archived", NOW - timedelta(days=1))):
            connection.execute(text(
                "INSERT INTO reading_books (id, title, author, learning_language, source_kind, source_hash, status, "
                "chapter_count, original_asset_key, word_count, imported_by, created_at, updated_at) VALUES "
                "(:id, :title, 'Author', 'en', 'epub', :hash, :status, 2, 'k', 900, 'admin@example.com', :created, :updated)"
            ), {"id": identifier.hex, "title": f"Book {status}", "hash": identifier.hex, "status": status,
                "created": (NOW - timedelta(days=4)).isoformat(), "updated": updated.isoformat()})
        connection.execute(text(
            "INSERT INTO reading_book_chapters (id, book_id, position, title, content_asset_key, word_count, created_at) "
            "VALUES (:id, :book, 0, 'One', 'c', 400, :now)"
        ), {"id": uuid.uuid4().hex, "book": book_id.hex, "now": NOW.isoformat()})
    repo = AdminConsoleRepository(engine)
    books = repo.list_books()
    assert [book["status"] for book in books] == ["ready", "archived"]
    assert books[0]["chapter_count"] == 2
    detail = repo.get_book(str(book_id))
    assert detail["title"] == "Book ready"
    assert [chapter["title"] for chapter in detail["chapters"]] == ["One"]
    assert repo.get_book(str(uuid.uuid4())) is None


def test_books_are_unavailable_when_the_catalog_schema_is_absent():
    bare = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bare)
    assert AdminConsoleRepository(bare).list_books() is None


def test_vocabulary_collections_and_import_receipts(engine):
    entry_id, receipt_id = uuid.uuid4(), uuid.uuid4()
    with Session(engine) as session, session.begin():
        session.add(VocabularyCollection(id="toeic-core", language_code="en", title="TOEIC core", framework="TOEIC",
                                         level="B1", catalog_status="pending_review", origin="imported",
                                         provenance={"admission": {"rights_status": "licensed", "completeness": "complete"}},
                                         created_at=NOW - timedelta(days=2), updated_at=NOW - timedelta(days=1)))
        session.add(VocabularyEntry(id=entry_id, language_code="en", term="agenda", normalized_term="agenda",
                                    identity_key="en:agenda", created_at=NOW, updated_at=NOW))
    with Session(engine) as session, session.begin():
        receipt = VocabularySourceImport(id=receipt_id, collection_id="toeic-core", filename="core.csv", source_format="csv",
                                         content_hash="h", status="imported", imported_count=1, created_at=NOW - timedelta(days=2),
                                         updated_at=NOW - timedelta(days=2))
        failed = VocabularySourceImport(id=uuid.uuid4(), collection_id=None, filename="bad.csv", source_format="csv",
                                        content_hash="h2", status="failed", failed_count=1,
                                        errors=[{"reason": "The source has no valid vocabulary rows to import."}],
                                        created_at=NOW - timedelta(days=1), updated_at=NOW - timedelta(days=1))
        session.add_all([receipt, failed])
    with Session(engine) as session, session.begin():
        session.add(VocabularyCollectionMembership(id=uuid.uuid4(), collection_id="toeic-core", entry_id=entry_id,
                                                   source_import_id=receipt_id, position=0))
    repo = AdminConsoleRepository(engine)
    collections = repo.list_vocabulary_collections()
    assert collections == [{
        "id": "toeic-core", "title": "TOEIC core", "language": "en", "framework": "TOEIC", "level": "B1",
        "level_range": "", "topic": "", "status": "pending_review", "origin": "imported", "item_count": 1,
        "rights_status": "licensed", "completeness": "complete",
        "created_at": collections[0]["created_at"], "updated_at": collections[0]["updated_at"],
    }]
    receipts = repo.list_vocabulary_imports()
    assert [row["filename"] for row in receipts] == ["bad.csv", "core.csv"]
    assert receipts[0]["error"] == "The source has no valid vocabulary rows to import."
    assert receipts[1]["collection_title"] == "TOEIC core"
    assert receipts[1]["collection_status"] == "pending_review"


def test_admin_events_are_recorded_against_the_acting_account_and_read_back(engine):
    _seed_people(engine)
    repo = AdminConsoleRepository(engine)
    repo.record_event("admin.account.view", actor_key="sub-cy", entity_type="account", entity_id=str(_uid("ana")),
                      payload={"fields": "operational"})
    repo.record_event("admin.import", actor_key="local-admin", entity_type="book", entity_id="",
                      payload={"status": "error", "source": "broken.epub"})
    with Session(engine) as session:
        rows = session.query(AuditLog).order_by(AuditLog.created_at).all()
    assert rows[0].user_id == _uid("cy")
    assert rows[0].payload == {"fields": "operational"}
    assert rows[1].user_id is None
    assert rows[1].payload["actor"] == "local-admin"
    imports = repo.list_events(("admin.import",), limit=10)
    assert [event["payload"]["source"] for event in imports] == ["broken.epub"]
    assert imports[0]["entity_type"] == "book"
