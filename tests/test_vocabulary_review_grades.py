"""The review has three grades, and each one says what it will do.

The source has always drawn three - Quên, Chưa chắc, Nhớ rồi - while the API
accepted two, so the middle button sat on the screen disabled. These hold the
third one's behaviour and the schedule the buttons print, which must come from
the scheduler rather than from the button.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

import pytest

from writing_coach.becoming_library import (
    AGAIN_MINUTES,
    LibraryVocabularyIn,
    REVIEW_STAGE_DAYS,
    UNSURE_DAYS,
    VocabularyReviewIn,
    configure_becoming_library,
    configure_becoming_library_content,
    list_library_vocabulary,
    review_library_vocabulary,
    review_schedule,
    save_library_vocabulary,
)
from writing_coach.persistence.specialized_repository import (
    SQLiteSpecializedLearningRepository,
)


@pytest.fixture()
def library(tmp_path):
    database = tmp_path / "language.db"

    def connect():
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        return connection

    repository = SQLiteSpecializedLearningRepository(connect)
    with repository._db() as connection:  # noqa: SLF001
        connection.execute(
            "CREATE TABLE saved_words (word TEXT PRIMARY KEY, phonetic TEXT, part_of_speech TEXT,"
            " definition TEXT, translation_vi TEXT, added_at TEXT)"
        )
        connection.commit()
    repository.initialize()

    import writing_coach.becoming_library as module

    previous_repository = module._repository  # noqa: SLF001
    previous_content = module._content_repository  # noqa: SLF001
    configure_becoming_library(repository)
    configure_becoming_library_content(None)
    yield repository
    configure_becoming_library(previous_repository)
    configure_becoming_library_content(previous_content)


def keep(word: str) -> None:
    save_library_vocabulary(LibraryVocabularyIn(word=word, definition="kept for a review"))


def state(word: str) -> dict:
    page = list_library_vocabulary(search=word, limit=5)
    return next(item for item in page["items"] if item["word"] == word)


def grade(word: str, result: str) -> dict:
    return review_library_vocabulary(word, VocabularyReviewIn(result=result))["item"]


def when(value: str) -> datetime:
    return datetime.fromisoformat(value)


# --- The three grades ---------------------------------------------------

def test_the_api_takes_three_grades(library):
    for result in ("again", "unsure", "got_it"):
        assert VocabularyReviewIn(result=result).result == result
    with pytest.raises(ValueError):
        VocabularyReviewIn(result="easy")


def test_unsure_holds_the_card_where_it_is(library):
    keep("kestrel")
    grade("kestrel", "got_it")
    before = state("kestrel")

    after = grade("kestrel", "unsure")

    assert after["review_stage"] == before["review_stage"], "unsure neither promotes"
    assert after["successful_recalls"] == before["successful_recalls"], "nor counts a recall"
    assert after["lapse_count"] == before["lapse_count"], "nor a lapse"
    gap = when(after["next_review_at"]) - when(after["last_reviewed_at"])
    assert abs(gap - timedelta(days=UNSURE_DAYS)) < timedelta(minutes=1)


def test_again_sends_the_card_back_and_got_it_moves_it_on(library):
    keep("petrichor")
    first = grade("petrichor", "got_it")
    assert first["review_stage"] == 1
    assert first["successful_recalls"] == 1

    lapsed = grade("petrichor", "again")
    assert lapsed["review_stage"] == 0
    assert lapsed["lapse_count"] == 1
    gap = when(lapsed["next_review_at"]) - when(lapsed["last_reviewed_at"])
    assert abs(gap - timedelta(minutes=AGAIN_MINUTES)) < timedelta(seconds=30)


def test_a_card_climbs_the_stages_it_has(library):
    keep("halcyon")
    stages = [grade("halcyon", "got_it")["review_stage"] for _ in range(6)]
    assert stages == [1, 2, 3, 4, 4, 4], "four is the top, and it stays there"


# --- What the buttons print --------------------------------------------

def test_the_card_carries_the_schedule_the_scheduler_will_use(library):
    keep("kestrel")
    card = state("kestrel")
    assert card["schedule"] == {
        "again": {"minutes": AGAIN_MINUTES},
        "unsure": {"days": UNSURE_DAYS},
        "got_it": {"days": REVIEW_STAGE_DAYS[1]},
    }

    graded = grade("kestrel", "got_it")
    assert graded["schedule"]["got_it"] == {"days": REVIEW_STAGE_DAYS[2]}, (
        "the next step moves with the card"
    )


def test_the_schedule_is_read_from_the_stage_not_written_on_the_button(library):
    for stage, days in REVIEW_STAGE_DAYS.items():
        assert review_schedule(stage - 1)["got_it"] == {"days": days}
    assert review_schedule(4)["got_it"] == {"days": REVIEW_STAGE_DAYS[4]}, "the top stays the top"
    assert review_schedule(-5)["again"] == {"minutes": AGAIN_MINUTES}


def test_a_word_that_is_not_kept_cannot_be_graded(library):
    assert review_library_vocabulary("nothing-here", VocabularyReviewIn(result="unsure")) == {
        "found": False
    }
