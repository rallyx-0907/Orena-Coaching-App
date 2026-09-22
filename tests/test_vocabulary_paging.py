"""The learner's vocabulary is counted and paged in the database.

The screens that show a number ask for the number; the screens that show a few
words ask for a few words; the library itself arrives a page at a time. These
tests hold that, at the sizes it actually matters at - an empty learner, a
small one, one with sixteen hundred words, and one with ten thousand.

They also hold the shape of the fix that got us here: the summary must not read
the words, and the listing must not ask the content repository about each word
on its own.
"""
from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timedelta

import pytest

from writing_coach.becoming_library import (
    LibraryVocabularyIn,
    configure_becoming_library,
    configure_becoming_library_content,
    library_summary,
    list_library_vocabulary,
    save_library_vocabulary,
)
from writing_coach.persistence.specialized_repository import (
    LIBRARY_PAGE_MAX,
    SQLiteSpecializedLearningRepository,
)
from writing_coach.product.rank_ladder import RANK_TOTAL, rank_state, tier_of


def _iso(moment: datetime) -> str:
    return moment.astimezone().isoformat(timespec="seconds")


@pytest.fixture()
def library(tmp_path, monkeypatch):
    """A learner's own language database, with nothing else installed."""

    database = tmp_path / "language.db"

    def connect():
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        return connection

    repository = SQLiteSpecializedLearningRepository(connect)
    with repository._db() as connection:  # noqa: SLF001 - the schema is this test's subject
        connection.execute(
            "CREATE TABLE saved_words (word TEXT PRIMARY KEY, phonetic TEXT, part_of_speech TEXT,"
            " definition TEXT, translation_vi TEXT, added_at TEXT)"
        )
        connection.commit()
    # The real schema, indexes and all - the timings below are only meaningful
    # against what the runtime actually creates.
    repository.initialize()
    # Whatever the suite had installed is put back: these tests own the
    # learner's language database, not the process.
    import writing_coach.becoming_library as module

    previous_repository = module._repository  # noqa: SLF001
    previous_content = module._content_repository  # noqa: SLF001
    configure_becoming_library(repository)
    configure_becoming_library_content(None)
    yield repository
    configure_becoming_library(previous_repository)
    configure_becoming_library_content(previous_content)


def seed(repository, count: int, *, mastered: int = 0, due: int = 0, prefix: str = "word") -> None:
    """`count` saved words, of which `mastered` are held and `due` are waiting."""

    now = datetime.now().astimezone()
    rows = []
    for index in range(count):
        word = f"{prefix}-{index:05d}"
        stage = 3 if index < mastered else 0
        # Due words are scheduled in the past; the rest are scheduled ahead.
        offset = timedelta(days=-1) if index < due else timedelta(days=30)
        rows.append((word, _iso(now - timedelta(minutes=index)), stage, _iso(now + offset)))
    with repository._db() as connection:  # noqa: SLF001
        connection.executemany(
            "INSERT INTO saved_words (word, phonetic, part_of_speech, definition, translation_vi, added_at)"
            " VALUES (?,'','','','', ?)",
            [(row[0], row[1]) for row in rows],
        )
        connection.executemany(
            "INSERT INTO vocabulary_learning (word, source_essay_id, source_fragment, source_kind,"
            " focus_note, review_stage, successful_recalls, lapse_count, last_reviewed_at,"
            " next_review_at, updated_at) VALUES (?, NULL, '', 'manual', '', ?, 0, 0, '', ?, ?)",
            [(row[0], row[2], row[3], row[1]) for row in rows],
        )
        connection.commit()


def walk(**params) -> list[str]:
    """Every word, page by page, the way a screen would read them."""

    words: list[str] = []
    cursor = ""
    for _ in range(2000):
        page = list_library_vocabulary(cursor=cursor, **params)
        words.extend(item["word"] for item in page["items"])
        cursor = page["next_cursor"] or ""
        if not cursor:
            return words
    raise AssertionError("the cursor never ended")


# --- The counts ---------------------------------------------------------

@pytest.mark.parametrize("count,mastered,due", [(0, 0, 0), (12, 4, 3), (1600, 1500, 40)])
def test_summary_counts_without_reading_the_words(library, count, mastered, due):
    seed(library, count, mastered=mastered, due=due)
    answer = library_summary()
    assert answer["summary"] == {
        "total": count,
        "saved": count,
        "due": due,
        "learning": count - mastered,
        "mastered": mastered,
        "available": mastered,
    }
    # The rank travels with the counts, so no screen has to work it out.
    assert answer["rank"] == tier_of(mastered)
    assert answer["rank_total"] == RANK_TOTAL
    assert len(answer["ladder"]) == RANK_TOTAL


def test_summary_never_lists_the_library(library, monkeypatch):
    seed(library, 300, mastered=200)

    def refuse():
        raise AssertionError("the summary read the whole library")

    monkeypatch.setattr(library, "list_library_records", refuse)
    assert library_summary()["summary"]["saved"] == 300


def test_summary_of_an_empty_learner_holds_no_rank(library):
    answer = library_summary()
    assert answer["summary"]["saved"] == 0
    assert answer["rank"] == 0
    assert answer["rank_name"] == ""
    assert answer["next_rank_name"] == "Initiate"


# --- The page -----------------------------------------------------------

def test_a_page_is_a_page(library):
    seed(library, 1600)
    page = list_library_vocabulary(limit=50)
    assert len(page["items"]) == 50
    assert page["total"] == 1600
    assert page["has_more"] is True
    assert page["next_cursor"]


def test_the_limit_is_bounded(library):
    seed(library, 500)
    page = list_library_vocabulary(limit=LIBRARY_PAGE_MAX + 5000)
    assert len(page["items"]) <= LIBRARY_PAGE_MAX


@pytest.mark.parametrize("order", ["recent", "due", "word"])
def test_paging_neither_repeats_nor_skips(library, order):
    seed(library, 1600, mastered=900, due=120)
    words = walk(limit=50, order=order)
    assert len(words) == 1600
    assert len(set(words)) == 1600


def test_the_page_size_does_not_change_the_order(library):
    seed(library, 300, mastered=100, due=20)
    assert walk(limit=7) == walk(limit=200)


def test_recent_is_newest_first_and_recent_three_are_three(library):
    seed(library, 400)
    page = list_library_vocabulary(limit=3, order="recent")
    assert [item["word"] for item in page["items"]] == ["word-00000", "word-00001", "word-00002"]


def test_alphabetical_is_alphabetical(library):
    seed(library, 60)
    words = walk(limit=11, order="word")
    assert words == sorted(words, key=str.casefold)


# --- The filters --------------------------------------------------------

def test_due_is_queried_not_filtered_in_the_browser(library):
    seed(library, 500, mastered=300, due=37)
    page = list_library_vocabulary(status="due", order="due", limit=100)
    assert page["total"] == 37
    assert len(page["items"]) == 37
    assert all(item["due"] for item in page["items"])
    assert page["summary"]["due"] == 37


def test_mastered_and_learning_split_the_library(library):
    seed(library, 240, mastered=90)
    mastered = list_library_vocabulary(status="mastered", limit=1)
    learning = list_library_vocabulary(status="learning", limit=1)
    assert mastered["total"] == 90
    assert learning["total"] == 150
    assert mastered["total"] + learning["total"] == mastered["summary"]["saved"]


def test_search_runs_in_the_database(library):
    seed(library, 100, prefix="harbour")
    seed(library, 100, prefix="meadow")
    page = list_library_vocabulary(search="meadow", limit=20)
    assert page["total"] == 100
    assert len(page["items"]) == 20
    assert all(item["word"].startswith("meadow") for item in page["items"])


def test_search_and_paging_work_together(library):
    seed(library, 300, prefix="river")
    seed(library, 300, prefix="forest")
    words = walk(limit=40, search="river")
    assert len(words) == 300
    assert len(set(words)) == 300
    assert all(word.startswith("river") for word in words)


def test_focus_selects_the_words_kept_from_one_book(library):
    seed(library, 40)
    with library._db() as connection:  # noqa: SLF001
        connection.execute(
            "UPDATE vocabulary_learning SET focus_note = 'Chapter One' WHERE word < 'word-00005'"
        )
        connection.commit()
    page = list_library_vocabulary(focus=("Chapter One",), limit=50)
    assert page["total"] == 5
    assert {item["word"] for item in page["items"]} == {f"word-{index:05d}" for index in range(5)}


# --- The size it has to survive -----------------------------------------

def test_ten_thousand_words_cost_a_page_not_a_library(library):
    seed(library, 10000, mastered=9000, due=25)

    started = time.perf_counter()
    counts = library_summary()
    summary_seconds = time.perf_counter() - started

    started = time.perf_counter()
    first = list_library_vocabulary(limit=50)
    page_seconds = time.perf_counter() - started

    started = time.perf_counter()
    queue = list_library_vocabulary(status="due", order="due", limit=25)
    due_seconds = time.perf_counter() - started

    assert counts["summary"]["saved"] == 10000
    assert counts["summary"]["mastered"] == 9000
    assert counts["rank"] == rank_state(9000)["rank"]
    assert len(first["items"]) == 50
    assert len(queue["items"]) == 25
    # Generous bounds: the point is that none of these grows with the library,
    # not that a particular machine is fast.
    assert summary_seconds < 1.0, summary_seconds
    assert page_seconds < 1.0, page_seconds
    assert due_seconds < 1.0, due_seconds


def test_a_saved_word_is_still_saved_and_counted(library):
    seed(library, 5)
    save_library_vocabulary(LibraryVocabularyIn(word="kestrel", definition="a small falcon"))
    counts = library_summary()
    assert counts["summary"]["saved"] == 6
    found = list_library_vocabulary(search="kestrel", limit=5)
    assert [item["word"] for item in found["items"]] == ["kestrel"]
