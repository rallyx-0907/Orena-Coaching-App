"""Book rights and the learner shelf (D-251; PRE-203 part 2): a book is on the learner shelf only when its rights are
attested (`cleared`) or it was there before migration 0037 (`grandfathered`); an imported book starts `unknown`. Like
Media, `cleared` needs an attestation and a licence note. The gate is dormant until a runtime applies 0037.

Hermetic part (always): the admin route over a repository double, the admin status, the dormant gate on a database
without the columns. PostgreSQL part (when `ORENA_TEST_POSTGRES_URL` names a throwaway database): the proposed revision
is applied from migrations/proposed/ for this module and removed again, and the repository runs for real - local
execution, not CI evidence (CI has no PostgreSQL service)."""

from __future__ import annotations

import hashlib
import importlib.util
import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from tests.test_admin_console_routes import ReadingRepo, call, setup  # noqa: F401 - the console fixture
from writing_coach.admin_content import book_status
from writing_coach.persistence import reading_library_repository as library
from writing_coach.persistence.reading_library_repository import BookRightsUnavailable

ROOT = Path(__file__).resolve().parents[1]
PG_URL = os.getenv("ORENA_TEST_POSTGRES_URL", "")
BOOK = "00000000-0000-4000-8000-000000000001"
URL = f"/api/admin/console/content/book/{BOOK}/rights"


class RightsRepo(ReadingRepo):
    def __init__(self, *, columns=True, present=True):
        super().__init__()
        self.columns, self.present, self.calls = columns, present, []

    def set_rights(self, book_id, *, status, license_note, source_url, actor):
        if not self.columns:
            raise BookRightsUnavailable("no columns")
        self.calls.append((book_id, status, license_note, source_url, actor))
        if not self.present:
            return None
        return {"id": book_id, "status": "ready", "rights_status": status, "license_note": license_note,
                "source_url": source_url, "rights_attested_by": actor if status == "cleared" else None,
                "rights_attested_at": None, "learner_visible": status == "cleared"}  # fmt: skip


def _use(setup, repo):  # noqa: F811
    from writing_coach import admin_console_api as console

    console._state.reading_repository = repo
    return repo


def test_cleared_rights_need_an_attestation_and_a_licence_note(setup):  # noqa: F811
    repo = _use(setup, RightsRepo())
    assert call(setup["app"], "POST", URL, json={"rights": "cleared", "license": "CC0"}).status_code == 422
    assert call(setup["app"], "POST", URL, json={"rights": "cleared", "attested": True}).status_code == 422
    assert call(setup["app"], "POST", URL, json={"rights": "grandfathered"}).status_code == 422  # not an admin's to set
    assert repo.calls == []
    done = call(setup["app"], "POST", URL, json={"rights": "cleared", "license": "Public domain (1912)",
                                                  "source_url": "https://www.gutenberg.org/ebooks/1", "attested": True})
    assert done.status_code == 200 and done.json()["book"]["learner_visible"] is True
    assert repo.calls[0][1:4] == ("cleared", "Public domain (1912)", "https://www.gutenberg.org/ebooks/1")


def test_denied_rights_take_a_book_off_the_shelf(setup):  # noqa: F811
    _use(setup, RightsRepo())
    answered = call(setup["app"], "POST", URL, json={"rights": "denied"})
    assert answered.status_code == 200 and answered.json()["book"]["learner_visible"] is False


def test_the_route_is_admin_only_and_same_origin(setup):  # noqa: F811
    repo = _use(setup, RightsRepo())
    assert call(setup["app"], "POST", URL, admin=False, json={"rights": "unknown"}).status_code in {401, 403}
    assert call(setup["app"], "POST", URL, origin="https://evil.example", json={"rights": "unknown"}).status_code == 403
    assert repo.calls == []


def test_before_migration_0037_the_route_says_so_and_an_unknown_book_is_404(setup):  # noqa: F811
    _use(setup, RightsRepo(columns=False))
    refused = call(setup["app"], "POST", URL, json={"rights": "unknown"})
    assert refused.status_code == 503 and refused.json()["detail"]["category"] == "book_rights_unavailable"
    _use(setup, RightsRepo(present=False))
    assert call(setup["app"], "POST", URL, json={"rights": "unknown"}).status_code == 404


@pytest.mark.parametrize(("status", "rights", "shown"), [
    ("ready", None, "published"),  # before 0037: as it always was
    ("ready", "grandfathered", "published"),
    ("ready", "cleared", "published"),
    ("ready", "unknown", "draft"),  # imported after 0037, not attested yet
    ("ready", "denied", "draft"),
    ("archived", "cleared", "archived"),
])
def test_the_admin_status_says_whether_learners_can_read_it(status, rights, shown):
    assert book_status({"status": status, "rights_status": rights}) == shown


def test_the_gate_is_dormant_on_a_database_without_the_columns():
    engine = create_engine("sqlite://")
    assert library.has_rights_columns(engine) is False and library._learner_rights(engine) == ""
    with pytest.raises(BookRightsUnavailable):
        library.PostgresReadingLibraryRepository(engine).set_rights(BOOK, status="unknown", license_note="",
                                                                    source_url="", actor="a")  # fmt: skip
    assert library.PostgresReadingLibraryRepository(engine).rights_review() == []


def test_the_migration_is_proposed_not_in_versions():
    assert (ROOT / "migrations" / "proposed" / "20261021_0037_reading_book_rights.py").exists()
    assert not list((ROOT / "migrations" / "versions").glob("*_0037_*")), "promotion is the owner's (human gate)"


def test_the_checker_is_read_only(monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location("check_books_rights", ROOT / "scripts" / "check_books_rights.py")
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    monkeypatch.setattr(checker, "find_books_needing_rights", lambda engine: [
        {"id": BOOK, "title": "Old Book", "language": "en", "status": "ready", "rights_status": "grandfathered",
         "learner_visible": True}])
    monkeypatch.setattr(checker, "create_engine", lambda url: object())
    assert checker.main(["--url", "postgresql://x"]) == 1
    out = capsys.readouterr().out
    assert "Old Book" in out and "grandfathered" in out and "postgresql://x" not in out


# --------------------------------------------------------------------------------------------- PostgreSQL
@pytest.fixture(scope="module")
def pg():
    if not PG_URL:
        pytest.skip("ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")
    from alembic import command

    from writing_coach.persistence.runtime import _runtime_alembic_config

    base = _runtime_alembic_config()
    base.set_main_option("sqlalchemy.url", PG_URL.replace("%", "%%"))
    command.upgrade(base, "head")
    engine = create_engine(PG_URL, future=True)
    old = _book(engine, "before-0037")  # on the shelf before the revision
    proposed = _runtime_alembic_config()
    proposed.set_main_option("sqlalchemy.url", PG_URL.replace("%", "%%"))
    locations = proposed.get_main_option("version_locations") or str(ROOT / "migrations" / "versions")
    proposed.set_main_option("version_locations", f"{locations} {ROOT / 'migrations' / 'proposed'}")
    proposed.set_main_option("path_separator", "space")
    command.upgrade(proposed, "20261021_0037")
    library._RIGHTS_COLUMNS.clear()
    yield engine, old
    command.downgrade(proposed, "20261019_0036")  # leave the shared test database at the versions/ head
    library._RIGHTS_COLUMNS.clear()
    engine.dispose()


def _book(engine, label):
    book_id = uuid.uuid4()
    library.PostgresReadingLibraryRepository(engine).create_book(
        book_id=book_id, title=f"Book {label}", author="A", description="", learning_language="en",
        source_kind="epub", source_hash=hashlib.sha256(f"{label}-{book_id}".encode()).hexdigest(),
        cover_asset_key=f"books/{book_id}/cover.svg", original_asset_key=f"books/{book_id}/original.epub",
        imported_by="admin@test",
        chapters=[library.ChapterInput(chapter_key="c1", title="One", content_asset_key=f"books/{book_id}/0.json",
                                       word_count=10)],
    )  # fmt: skip
    return str(book_id)


def test_pg_a_book_on_the_shelf_before_0037_stays_and_is_listed_for_review(pg):
    engine, old = pg
    repository = library.PostgresReadingLibraryRepository(engine)
    assert repository.get_book(old) is not None  # grandfathered: not taken down
    review = {item["id"]: item for item in repository.rights_review()}
    assert review[old]["rights_status"] == "grandfathered" and review[old]["learner_visible"] is True


def test_pg_a_new_import_waits_for_cleared_rights_and_denial_takes_it_down(pg):
    engine, _old = pg
    repository = library.PostgresReadingLibraryRepository(engine)
    new = _book(engine, "after-0037")
    assert repository.get_book(new) is None  # unknown: not on the learner shelf
    assert new not in {item["id"] for item in repository.list_books(learning_language="en")["items"]}
    cleared = repository.set_rights(new, status="cleared", license_note="CC0", source_url="", actor="admin@test")
    assert cleared["learner_visible"] is True and cleared["rights_attested_by"] == "admin@test"
    assert repository.get_book(new) is not None
    denied = repository.set_rights(new, status="denied", license_note="", source_url="", actor="admin@test")
    assert denied["learner_visible"] is False and denied["rights_attested_by"] is None
    assert repository.get_book(new) is None


def test_pg_the_check_constraint_refuses_an_unknown_status(pg):
    engine, old = pg
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text("UPDATE reading_books SET rights_status = 'maybe' WHERE id = :id"),
                           {"id": uuid.UUID(old)})  # fmt: skip
