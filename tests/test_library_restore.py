"""Undo puts back what was deleted, schedule and all.

The design's delete names what is lost - "the review progress of these items" -
and then offers Hoàn tác for ten seconds. Undo that re-saved the word would
hand back a new card due today: the same spelling, none of the history. These
hold the difference.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

import pytest

from writing_coach.becoming_library import (
    LibraryVocabularyIn,
    RestoreVocabularyIn,
    configure_becoming_library,
    configure_becoming_library_content,
    delete_library_vocabulary,
    list_library_vocabulary,
    restore_library_vocabulary,
    save_library_vocabulary,
)
from writing_coach.persistence.specialized_repository import SQLiteSpecializedLearningRepository


@pytest.fixture()
def library(tmp_path):
    database = tmp_path / "language.db"

    def connect():
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        return connection

    repository = SQLiteSpecializedLearningRepository(connect)
    with repository._db() as connection:  # noqa: SLF001 - the schema is this test's subject
        connection.execute(
            "CREATE TABLE saved_words (word TEXT PRIMARY KEY, phonetic TEXT, part_of_speech TEXT,"
            " definition TEXT, translation_vi TEXT, added_at TEXT, entry_id TEXT,"
            " entry_identity_key TEXT NOT NULL DEFAULT '', reading_key TEXT NOT NULL DEFAULT '')"
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


def only(word: str) -> dict:
    page = list_library_vocabulary(limit=50, search=word)
    found = [item for item in page["items"] if item["word"].casefold() == word.casefold()]
    return found[0] if found else {}


def test_a_restored_word_keeps_the_schedule_it_had(library):
    """The whole point: a word four days into its schedule comes back four days
    in, not due today."""

    save_library_vocabulary(LibraryVocabularyIn(word="harbour", definition="a sheltered place"))
    later = (datetime.now().astimezone() + timedelta(days=4)).isoformat(timespec="seconds")
    library.update_library_review("harbour", {
        "review_stage": 2, "successful_recalls": 3, "lapse_count": 1,
        "last_reviewed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "next_review_at": later, "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    })
    before = only("harbour")
    assert before["review_stage"] == 2 and before["successful_recalls"] == 3

    delete_library_vocabulary("harbour")
    assert only("harbour") == {}, "it really is gone"

    restore_library_vocabulary(RestoreVocabularyIn(**{
        key: before[key] for key in (
            "word", "phonetic", "part_of_speech", "definition", "translation_vi", "added_at",
            "source_fragment", "source_kind", "focus_note", "review_stage",
            "successful_recalls", "lapse_count", "last_reviewed_at", "next_review_at",
        )
    }))
    after = only("harbour")
    assert after["review_stage"] == 2
    assert after["successful_recalls"] == 3
    assert after["lapse_count"] == 1
    assert after["next_review_at"][:10] == later[:10], "and it is still due when it was"


def test_saving_the_same_word_again_is_not_a_restore(library):
    """Saving is what a learner does when they meet a word, and it starts the
    schedule. The two must not be confused."""

    save_library_vocabulary(LibraryVocabularyIn(word="lantern"))
    library.update_library_review("lantern", {
        "review_stage": 3, "successful_recalls": 5, "lapse_count": 0,
        "last_reviewed_at": "", "next_review_at": (datetime.now().astimezone() + timedelta(days=7)).isoformat(),
        "updated_at": datetime.now().astimezone().isoformat(),
    })
    delete_library_vocabulary("lantern")
    save_library_vocabulary(LibraryVocabularyIn(word="lantern"))
    assert only("lantern")["review_stage"] == 0, "a re-saved word starts again"


def test_restoring_a_word_that_is_already_there_leaves_one(library):
    """Undo pressed twice, or pressed after the word came back another way."""

    save_library_vocabulary(LibraryVocabularyIn(word="quay", definition="a landing place"))
    item = only("quay")
    for _ in range(2):
        restore_library_vocabulary(RestoreVocabularyIn(word="quay", definition=item["definition"]))
    page = list_library_vocabulary(limit=50, search="quay")
    assert len([row for row in page["items"] if row["word"] == "quay"]) == 1


def test_a_restore_carries_where_the_word_was_met(library):
    save_library_vocabulary(LibraryVocabularyIn(
        word="beacon", definition="a light", source_fragment="a beacon on the cliff",
        source_kind="reading", focus_note="Harbour notes",
    ))
    before = only("beacon")
    delete_library_vocabulary("beacon")
    restore_library_vocabulary(RestoreVocabularyIn(
        word="beacon", definition=before["definition"], source_fragment=before["source_fragment"],
        source_kind=before["source_kind"], focus_note=before["focus_note"],
    ))
    after = only("beacon")
    assert after["source_fragment"] == "a beacon on the cliff"
    assert after["source_kind"] == "reading"
    assert after["focus_note"] == "Harbour notes"
