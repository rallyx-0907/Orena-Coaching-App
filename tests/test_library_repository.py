"""Keeping, pinning and filing - the relationships, and nothing else.

The schema these run against is `models.py`'s mirror of
`20260923_0013`, created here in memory, so the repository is exercised through
the same ORM the PostgreSQL runtime uses. Foreign keys are switched on,
because two of the guarantees under test - a word's relationship disappearing
with the word, and a cross-kind membership being impossible - are foreign keys.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from writing_coach.persistence.ids import stable_uuid
from writing_coach.persistence.library_repository import LibraryConflict, LibraryRepository
from writing_coach.persistence.models import (
    Base,
    LibraryCollectionMember,
    LibraryItem,
    SavedWord,
    User,
)

LEARNER = "learner-a"
LANGUAGE = "en"


@pytest.fixture()
def library(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'library.db'}")

    @event.listens_for(engine, "connect")
    def _foreign_keys(connection, _record):  # noqa: ANN001 - SQLAlchemy's signature
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    with Session(engine) as session, session.begin():
        session.add(
            User(
                id=stable_uuid("user", LEARNER), user_key=LEARNER, email="", name="",
                picture="", role="user", created_at=now,
            )
        )
        # Written before the words: in one flush SQLAlchemy does not order
        # these two tables for us, and SQLite is enforcing the foreign key.
        session.flush()
        for index, word in enumerate(("harbour", "lantern", "quay")):
            session.add(
                SavedWord(
                    id=uuid.uuid4(), user_id=stable_uuid("user", LEARNER), language_code=LANGUAGE,
                    word=word, normalized_word=word, phonetic="", part_of_speech="", definition="",
                    translation_vi="", added_at=now, source_fragment="", source_kind="manual",
                    focus_note="", review_stage=0, successful_recalls=0, lapse_count=0,
                    # One word is due now, the others in a month.
                    next_review_at=now if index == 0 else now + timedelta(days=30),
                    updated_at=now, entry_identity_key="", reading_key="",
                )
            )
    return LibraryRepository(
        engine, user_key_provider=lambda: LEARNER, language_provider=lambda: LANGUAGE
    )


# --- Keeping ------------------------------------------------------------

def test_keeping_a_word_twice_is_one_relationship(library):
    first = library.keep(kind="word", word="harbour")
    again = library.keep(kind="word", word="harbour")
    assert first["id"] == again["id"]
    assert first["word"] == "harbour"
    assert first["pinned"] is False and first["state"] is None


def test_keeping_a_passage_uses_its_routing_identity(library):
    item = library.keep(kind="reading", source_id="reading:14", relationship="started")
    assert item["kind"] == "reading" and item["source_id"] == "reading:14"
    assert library.keep(kind="reading", source_id="reading:14", relationship="started")["id"] == item["id"]
    # A different relationship to the same passage is a different row: starting
    # something is not keeping it (Collection Architecture §2).
    kept = library.keep(kind="reading", source_id="reading:14", relationship="kept")
    assert kept["id"] != item["id"]


def test_a_word_nobody_saved_cannot_be_kept(library):
    with pytest.raises(LibraryConflict) as refused:
        library.keep(kind="word", word="zeppelin")
    assert refused.value.reason == "unknown_item"


def test_a_kind_nobody_draws_is_refused(library):
    with pytest.raises(LibraryConflict) as refused:
        library.keep(kind="podcast", source_id="p1")
    assert refused.value.reason == "kind_mismatch"


# --- Pinning ------------------------------------------------------------

def test_pinning_and_unpinning_moves_only_the_pin(library):
    item = library.keep(kind="word", word="harbour")
    pinned = library.update(item["id"], expected_version=item["version"], pinned=True)
    assert pinned["pinned"] is True and pinned["pinned_at"]
    assert pinned["version"] == item["version"] + 1
    assert pinned["state"] is None, "pinning says nothing about how well it is known"
    loose = library.update(pinned["id"], expected_version=pinned["version"], pinned=False)
    assert loose["pinned"] is False and loose["pinned_at"] == ""


def test_a_write_against_a_version_it_did_not_read_is_refused(library):
    item = library.keep(kind="word", word="harbour")
    library.update(item["id"], expected_version=item["version"], pinned=True)
    with pytest.raises(LibraryConflict) as refused:
        library.update(item["id"], expected_version=item["version"], note="mine")
    assert refused.value.reason == "version_conflict"


def test_state_is_an_override_and_can_be_taken_back(library):
    item = library.keep(kind="word", word="harbour")
    marked = library.update(item["id"], expected_version=item["version"], state="mastered")
    assert marked["state"] == "mastered"
    cleared = library.update(marked["id"], expected_version=marked["version"], clear_state=True)
    assert cleared["state"] is None, "cleared means 'ask the owner', not 'learning'"


def test_a_state_nobody_defined_is_refused(library):
    item = library.keep(kind="word", word="harbour")
    with pytest.raises(LibraryConflict) as refused:
        library.update(item["id"], expected_version=item["version"], state="brilliant")
    assert refused.value.reason == "kind_mismatch"


# --- The queue ----------------------------------------------------------

def test_the_queue_is_what_is_marked_then_what_is_due(library):
    """"Marked first, then by SRS due date" - and nothing invents a schedule
    for a kind that has none."""

    passage = library.keep(kind="reading", source_id="reading:14", relationship="started")
    word = library.keep(kind="word", word="lantern")
    library.update(passage["id"], expected_version=passage["version"], pinned=True)
    library.update(word["id"], expected_version=word["version"], pinned=True)
    queue = library.review_queue()
    assert [entry["kind"] for entry in queue["pinned"]] == ["reading", "word"], "oldest pin leads"
    assert queue["pinned_count"] == 2
    # One saved word is due now; the other two are a month out.
    assert queue["due_count"] == 1 and queue["first_due_word"] == "harbour"
    assert queue["total"] == 3


def test_an_unpinned_passage_is_not_in_the_queue(library):
    library.keep(kind="reading", source_id="reading:14", relationship="started")
    assert library.review_queue()["pinned"] == []


# --- Sets ---------------------------------------------------------------

def test_a_set_holds_one_kind_and_says_how_many(library):
    words = library.create_collection(kind="word", title="Harbour words")
    item = library.keep(kind="word", word="harbour")
    assert library.add_to_collection(words["id"], item["id"])["added"] is True
    assert library.add_to_collection(words["id"], item["id"])["added"] is False, "filing twice is once"
    listed = library.collections()
    assert [(row["title"], row["size"], row["kind"]) for row in listed] == [("Harbour words", 1, "word")]
    assert [row["word"] for row in library.collection_items(words["id"])] == ["harbour"]


def test_a_passage_cannot_go_in_a_set_of_words(library):
    words = library.create_collection(kind="word", title="Harbour words")
    passage = library.keep(kind="reading", source_id="reading:14", relationship="started")
    with pytest.raises(LibraryConflict) as refused:
        library.add_to_collection(words["id"], passage["id"])
    assert refused.value.reason == "kind_mismatch"


def test_two_sets_of_one_kind_cannot_share_a_name(library):
    library.create_collection(kind="word", title="Harbour words")
    with pytest.raises(LibraryConflict) as refused:
        library.create_collection(kind="word", title="Harbour words")
    assert refused.value.reason == "duplicate_title"
    # The same name for another kind is a different set, and is allowed.
    assert library.create_collection(kind="reading", title="Harbour words")["kind"] == "reading"


def test_a_set_with_no_name_is_refused(library):
    with pytest.raises(LibraryConflict) as refused:
        library.create_collection(kind="word", title="   ")
    assert refused.value.reason == "unknown_collection"


def test_removing_from_a_set_leaves_the_item(library):
    words = library.create_collection(kind="word", title="Harbour words")
    item = library.keep(kind="word", word="harbour")
    library.add_to_collection(words["id"], item["id"])
    assert library.remove_from_collection(words["id"], item["id"]) is True
    assert library.collection_items(words["id"]) == []
    assert library.get(item["id"]) is not None, "the thing kept is not the filing of it"


# --- What forgetting means ----------------------------------------------

def test_forgetting_removes_the_relationship_and_nothing_else(library, tmp_path):
    words = library.create_collection(kind="word", title="Harbour words")
    item = library.keep(kind="word", word="harbour")
    library.add_to_collection(words["id"], item["id"])
    assert library.forget(item["id"]) is True
    assert library.get(item["id"]) is None
    with Session(library.engine) as session:
        assert session.query(SavedWord).where(SavedWord.normalized_word == "harbour").count() == 1
        assert session.query(LibraryCollectionMember).count() == 0
    assert [row["title"] for row in library.collections()] == ["Harbour words"]


def test_deleting_the_word_takes_its_relationship_with_it(library):
    item = library.keep(kind="word", word="harbour")
    with Session(library.engine) as session, session.begin():
        saved = session.query(SavedWord).where(SavedWord.normalized_word == "harbour").one()
        session.delete(saved)
    assert library.get(item["id"]) is None
    with Session(library.engine) as session:
        assert session.query(LibraryItem).count() == 0


# --- Reading a listing's own state --------------------------------------

def test_a_listing_asks_once_for_every_row_it_draws(library):
    kept = library.keep(kind="word", word="harbour")
    library.update(kept["id"], expected_version=kept["version"], pinned=True)
    library.keep(kind="word", word="lantern")
    found = library.lookup(kind="word", words=("harbour", "lantern", "quay"))
    assert {row["word"]: row["pinned"] for row in found} == {"harbour": True, "lantern": False}


def test_another_learner_sees_none_of_it(library):
    library.keep(kind="word", word="harbour")
    other = LibraryRepository(
        library.engine, user_key_provider=lambda: "learner-b", language_provider=lambda: LANGUAGE
    )
    assert other.lookup(kind="word", words=("harbour",)) == []
    assert other.review_queue()["pinned"] == []
    assert other.collections() == []
