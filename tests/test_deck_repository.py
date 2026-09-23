"""A learner's study sets: Vocabulary's own, not My Library's collections.

The suite builds its schema from `models.py`, so these run even though the
migration is still a proposal. What they hold is the domain boundary and the
two promises a set makes: it stores a reference to the learner's word and never
a copy, and it never touches a review schedule.
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from writing_coach.persistence.deck_repository import DeckConflict, DeckRepository
from writing_coach.persistence.ids import stable_uuid
from writing_coach.persistence.models import Base, SavedWord, User, VocabularyDeckMember

USER_KEY = "deck-tester"
LANGUAGE = "en"


@pytest.fixture()
def repo(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'decks.db'}")
    Base.metadata.create_all(engine)
    uid = stable_uuid("user", USER_KEY)
    now = datetime.now(UTC)
    with Session(engine) as session:
        session.add(User(id=uid, user_key=USER_KEY, email=f"{USER_KEY}@test", created_at=now))
        session.flush()
        for word in ("harbour", "lantern", "quay"):
            session.add(
                SavedWord(
                    id=uuid.uuid4(),
                    user_id=uid,
                    language_code=LANGUAGE,
                    word=word,
                    normalized_word=word,
                    added_at=now,
                    updated_at=now,
                    review_stage=3,
                    successful_recalls=2,
                )
            )
        session.commit()
    return DeckRepository(
        engine, user_key_provider=lambda: USER_KEY, language_provider=lambda: LANGUAGE
    )


def test_a_server_without_the_tables_says_so(tmp_path):
    """The whole reason the API can answer 503 instead of using another domain."""

    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'bare.db'}")
    assert DeckRepository(engine).available() is False


def test_the_tables_are_vocabularys_own(repo):
    names = set(inspect(repo.engine).get_table_names())
    assert {"vocabulary_decks", "vocabulary_deck_members"} <= names
    assert repo.available() is True


def test_a_set_is_made_with_the_cover_the_learner_chose(repo):
    deck = repo.create(title="Harbour words", cover="moss")
    assert deck["title"] == "Harbour words"
    assert deck["cover"] == "moss"
    assert deck["size"] == 0
    assert deck["version"] == 1


def test_a_cover_outside_the_palette_is_refused(repo):
    with pytest.raises(DeckConflict) as raised:
        repo.create(title="Nope", cover="#ff0000")
    assert raised.value.reason == "unknown_cover"


def test_two_sets_of_one_name_in_one_language_is_refused(repo):
    repo.create(title="Reise")
    with pytest.raises(DeckConflict) as raised:
        repo.create(title="Reise")
    assert raised.value.reason == "duplicate_title"


def test_a_word_joins_a_set_by_reference(repo):
    deck = repo.create(title="Sea")
    assert repo.add_word(deck["id"], "harbour") is True
    words = repo.words(deck["id"])
    assert [row["word"] for row in words] == ["harbour"]
    # By reference: the set holds a row id, not a second copy of the word.
    with Session(repo.engine) as session:
        member = session.scalar(select(VocabularyDeckMember))
        saved = session.get(SavedWord, member.saved_word_id)
        assert saved.word == "harbour"


def test_filing_a_word_twice_is_not_an_error(repo):
    deck = repo.create(title="Sea")
    assert repo.add_word(deck["id"], "harbour") is True
    assert repo.add_word(deck["id"], "harbour") is False
    assert len(repo.words(deck["id"])) == 1


def test_a_word_the_learner_does_not_have_cannot_be_filed(repo):
    deck = repo.create(title="Sea")
    with pytest.raises(DeckConflict) as raised:
        repo.add_word(deck["id"], "never-saved")
    assert raised.value.reason == "unknown_word"


def test_words_keep_the_order_they_were_filed_in(repo):
    deck = repo.create(title="Sea")
    for word in ("quay", "harbour", "lantern"):
        repo.add_word(deck["id"], word)
    assert [row["word"] for row in repo.words(deck["id"])] == ["quay", "harbour", "lantern"]


def test_sizes_are_counted_for_the_whole_listing(repo):
    one = repo.create(title="One")
    two = repo.create(title="Two")
    repo.add_word(one["id"], "harbour")
    repo.add_word(one["id"], "quay")
    repo.add_word(two["id"], "lantern")
    sizes = {deck["title"]: deck["size"] for deck in repo.list_decks()}
    assert sizes == {"One": 2, "Two": 1}


def test_renaming_carries_the_version_it_read(repo):
    deck = repo.create(title="Sea")
    changed = repo.update(deck["id"], expected_version=deck["version"], title="Harbour")
    assert changed["title"] == "Harbour"
    assert changed["version"] == deck["version"] + 1
    with pytest.raises(DeckConflict) as raised:
        repo.update(deck["id"], expected_version=deck["version"], title="Too late")
    assert raised.value.reason == "stale"


def test_the_cover_can_be_changed_and_persists(repo):
    deck = repo.create(title="Sea", cover="sea")
    changed = repo.update(deck["id"], expected_version=deck["version"], cover="amber")
    assert changed["cover"] == "amber"
    assert [item["cover"] for item in repo.list_decks()] == ["amber"]


def test_forgetting_a_set_keeps_the_learners_words(repo):
    deck = repo.create(title="Sea")
    repo.add_word(deck["id"], "harbour")
    assert repo.delete(deck["id"]) is True
    assert repo.list_decks() == []
    with Session(repo.engine) as session:
        assert session.scalar(select(SavedWord).where(SavedWord.word == "harbour")) is not None


def test_deleting_a_word_takes_it_out_of_its_sets(repo):
    deck = repo.create(title="Sea")
    repo.add_word(deck["id"], "harbour")
    with Session(repo.engine) as session:
        session.execute(__import__("sqlalchemy").text("PRAGMA foreign_keys=ON"))
        saved = session.scalar(select(SavedWord).where(SavedWord.word == "harbour"))
        session.delete(saved)
        session.commit()
    assert repo.words(deck["id"]) == []


def test_another_learners_set_is_not_found(repo):
    deck = repo.create(title="Sea")
    other = DeckRepository(
        repo.engine, user_key_provider=lambda: "somebody-else", language_provider=lambda: LANGUAGE
    )
    assert other.list_decks() == []
    with pytest.raises(DeckConflict) as raised:
        other.words(deck["id"])
    assert raised.value.reason == "unknown_deck"


def test_another_languages_set_is_not_found(repo):
    deck = repo.create(title="Sea")
    other = DeckRepository(
        repo.engine, user_key_provider=lambda: USER_KEY, language_provider=lambda: "zh"
    )
    assert other.list_decks() == []
    with pytest.raises(DeckConflict):
        other.words(deck["id"])


def test_nothing_here_reads_or_writes_a_schedule():
    """A set is what a session is drawn from; the scheduler owns when a card
    comes back, and this module must not learn to."""

    source = (
        __import__("pathlib")
        .Path(__file__)
        .resolve()
        .parents[1]
        .joinpath("writing_coach/persistence/deck_repository.py")
        .read_text(encoding="utf-8")
    )
    for field in ("next_review_at", "review_stage", "last_reviewed_at", "lapse_count"):
        assert field not in source, f"the deck repository touches {field}"
