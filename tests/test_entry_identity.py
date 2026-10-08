"""A saved word records which catalogue entry it is - and never guesses.

The invariant the schema cannot hold (`20260923_0013`, architecture review
round 1): a link to an entry whose `readings` holds more than one reading must
carry a non-empty `reading_key`. No portable constraint can read a JSON list,
so this is where it lives, and these are the cases it has to get right.

行 is xíng or háng. A word saved by tapping it in a passage knows neither, and
the honest record of that is **no link at all** - not a link to whichever
reading happened to be first, which would key the wrong pronunciation audio to
it for as long as the row exists.
"""
from __future__ import annotations

import sqlite3

import pytest

from writing_coach.becoming_library import (
    LibraryVocabularyIn,
    configure_becoming_library,
    configure_becoming_library_content,
    entry_identity_for,
    save_library_vocabulary,
)
from writing_coach.persistence.specialized_repository import SQLiteSpecializedLearningRepository


class FakeCatalogue:
    """The catalogue read, shaped like `VocabularyRepository.find_entry`."""

    def __init__(self, entries: dict[str, dict]):
        self.entries = entries
        self.asked: list[str] = []

    def find_entry(self, language: str, normalized: str) -> dict | None:
        self.asked.append(normalized)
        return self.entries.get(normalized)

    def list_entries_for_language(self, language: str, limit: int = 0) -> list[dict]:
        return list(self.entries.values())


AMBIGUOUS = {
    "id": "0f3d2a1c-0000-4000-8000-000000000001",
    "identity_key": "zh:行",
    "term": "行",
    "readings": [{"text": "xíng"}, {"text": "háng"}],
}
PLAIN = {
    "id": "0f3d2a1c-0000-4000-8000-000000000002",
    "identity_key": "en:harbour",
    "term": "harbour",
    "readings": [{"text": "ˈhɑːbə"}],
}
NO_READINGS = {
    "id": "0f3d2a1c-0000-4000-8000-000000000003",
    "identity_key": "en:quay",
    "term": "quay",
    "readings": [],
}
NO_IDENTITY = {"id": "0f3d2a1c-0000-4000-8000-000000000004", "identity_key": "", "term": "pier"}


@pytest.fixture()
def learner(tmp_path):
    """A learner's own language database, and a catalogue beside it."""

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
    catalogue = FakeCatalogue({
        "行": AMBIGUOUS, "harbour": PLAIN, "quay": NO_READINGS, "pier": NO_IDENTITY,
    })
    configure_becoming_library(repository)
    configure_becoming_library_content(catalogue)
    yield repository
    configure_becoming_library(previous_repository)
    configure_becoming_library_content(previous_content)


def saved_row(repository, word: str) -> dict:
    with repository._db() as connection:  # noqa: SLF001
        row = connection.execute(
            "SELECT entry_id, entry_identity_key, reading_key FROM saved_words"
            " WHERE lower(word) = lower(?)",
            (word,),
        ).fetchone()
    assert row is not None, f"{word} was not saved at all"
    return dict(row)


# --- The decision -------------------------------------------------------

def test_one_reading_is_not_a_choice(learner):
    assert entry_identity_for("harbour") == {
        "entry_id": PLAIN["id"], "entry_identity_key": "en:harbour", "reading_key": "ˈhɑːbə",
    }


def test_no_readings_links_without_one(learner):
    assert entry_identity_for("quay") == {
        "entry_id": NO_READINGS["id"], "entry_identity_key": "en:quay", "reading_key": "",
    }


def test_an_ambiguous_entry_with_no_reading_is_not_linked(learner):
    """The case this whole column exists for. Saying nothing beats saying
    'xíng' about a word the learner may have meant as 'háng'."""

    assert entry_identity_for("行") == {
        "entry_id": "", "entry_identity_key": "", "reading_key": "",
    }


def test_an_ambiguous_entry_with_its_reading_is_linked(learner):
    assert entry_identity_for("行", "háng") == {
        "entry_id": AMBIGUOUS["id"], "entry_identity_key": "zh:行", "reading_key": "háng",
    }


def test_a_reading_the_entry_does_not_have_is_refused(learner):
    """A caller that names a reading this entry has never had is describing
    some other entry, so this one is not linked."""

    assert entry_identity_for("行", "xing") == {
        "entry_id": "", "entry_identity_key": "", "reading_key": "",
    }


def test_an_entry_without_a_durable_identity_is_not_linked(learner):
    assert entry_identity_for("pier")["entry_identity_key"] == ""


def test_a_word_the_catalogue_does_not_have_is_not_linked(learner):
    assert entry_identity_for("lighthouse")["entry_identity_key"] == ""


# --- What is stored -----------------------------------------------------

def test_saving_stores_the_identity_and_the_reading(learner):
    save_library_vocabulary(LibraryVocabularyIn(word="行", reading="háng"))
    row = saved_row(learner, "行")
    assert row["entry_identity_key"] == "zh:行"
    assert row["reading_key"] == "háng"
    assert row["entry_id"] == AMBIGUOUS["id"]


def test_saving_an_ambiguous_word_without_its_reading_stores_the_word_and_no_link(learner):
    save_library_vocabulary(LibraryVocabularyIn(word="行"))
    row = saved_row(learner, "行")
    assert row["entry_identity_key"] == ""
    assert row["reading_key"] == ""
    assert not row["entry_id"]


def test_a_later_save_that_knows_less_does_not_unlink_the_word(learner):
    """Saving the same word again from a passage must not throw away the
    reading a dictionary save already recorded."""

    save_library_vocabulary(LibraryVocabularyIn(word="行", reading="háng"))
    save_library_vocabulary(LibraryVocabularyIn(word="行", source_kind="reading"))
    row = saved_row(learner, "行")
    assert row["entry_identity_key"] == "zh:行"
    assert row["reading_key"] == "háng"


def test_the_word_is_saved_whether_or_not_it_could_be_linked(learner):
    save_library_vocabulary(LibraryVocabularyIn(word="lighthouse", definition="a tower with a light"))
    row = saved_row(learner, "lighthouse")
    assert row["entry_identity_key"] == ""
