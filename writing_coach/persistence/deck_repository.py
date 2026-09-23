"""A learner's study sets - `vocabulary_decks` and their members.

Schema: `migrations/proposed/20260923_0014_vocabulary_decks.py`, **proposed and
not applied**. Independent architecture review is required before it moves into
`migrations/versions/`; the request is
`docs/project/VOCABULARY_DECK_SCHEMA_REVIEW_REQUEST.md`. `available()` is what
lets the app run without the tables: every route answers 503 until they exist.

A Deck belongs to Vocabulary and is a set the learner *made*. It is not a My
Library Collection, which organises items the learner already has and which
`ORENA_COLLECTION_ARCHITECTURE.md` §1 calls a projection.

What this repository does not own:

- **the words**. A member is a reference to a row in `saved_words`; the word,
  its meaning and its review schedule stay there. Putting a set's own copy of a
  word here would fork the library.
- **the schedule**. Nothing in this module reads or writes a review field. A
  set is what a session is drawn *from*; the scheduler remains the one owner of
  when a card comes back.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, func, inspect, select
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from writing_coach.core.request_context import current_language_code, current_user_key
from writing_coach.persistence.ids import stable_uuid
from writing_coach.persistence.models import (
    DECK_COVERS,
    SavedWord,
    VocabularyDeck,
    VocabularyDeckMember,
)
from writing_coach.vocabulary_library import normalize_vocabulary_word

# A learner's set is small by design and the room draws it as a list.
DECK_LIMIT = 100
WORD_LIMIT = 500


class DeckConflict(RuntimeError):
    """A write that lost a race, or asked for something that is not there.

    `reason` is one of: `stale`, `duplicate_title`, `unknown_deck`,
    `unknown_word`.
    """

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value else ""


class DeckRepository:
    """The learner's study sets, scoped by account and learning language."""

    def __init__(
        self,
        engine: Engine,
        *,
        user_key_provider: Callable[[], str] = current_user_key,
        language_provider: Callable[[], str] = current_language_code,
    ) -> None:
        self.engine = engine
        self._user_key_provider = user_key_provider
        self._language_provider = language_provider

    # --- is there a schema to talk to ------------------------------------

    def available(self) -> bool:
        """Whether the tables exist. Asked once per request, cheaply.

        Until the migration is reviewed and applied this is False everywhere,
        and the API says so rather than falling back to another domain's
        tables.
        """

        try:
            names = set(inspect(self.engine).get_table_names())
        except (OperationalError, ProgrammingError, AttributeError):
            return False
        return {"vocabulary_decks", "vocabulary_deck_members"} <= names

    # --- scope ------------------------------------------------------------

    def _scope(self) -> tuple[uuid.UUID, str]:
        return stable_uuid("user", self._user_key_provider()), self._language_provider().casefold()

    def _deck(self, session: Session, deck_id: str) -> VocabularyDeck:
        uid, lang = self._scope()
        try:
            wanted = uuid.UUID(str(deck_id))
        except (ValueError, AttributeError, TypeError) as error:
            raise DeckConflict("unknown_deck") from error
        deck = session.get(VocabularyDeck, wanted)
        if deck is None or deck.user_id != uid or deck.language_code != lang:
            raise DeckConflict("unknown_deck")
        return deck

    def _saved_word(self, session: Session, word: str) -> SavedWord:
        uid, lang = self._scope()
        normalized = normalize_vocabulary_word(word) or str(word).casefold()
        found = session.scalar(
            select(SavedWord).where(
                SavedWord.user_id == uid,
                SavedWord.language_code == lang,
                SavedWord.normalized_word == normalized,
            )
        )
        if found is None:
            raise DeckConflict("unknown_word")
        return found

    @staticmethod
    def _dict(deck: VocabularyDeck, *, size: int = 0) -> dict[str, Any]:
        return {
            "id": str(deck.id),
            "title": deck.title,
            "cover": deck.cover,
            "size": size,
            "version": deck.version,
            "created_at": _iso(deck.created_at),
            "updated_at": _iso(deck.updated_at),
        }

    # --- reading ----------------------------------------------------------

    def list_decks(self) -> list[dict[str, Any]]:
        """Every set in this language, with how many words is in each.

        The sizes are counted in the database, in one grouped read, rather than
        by listing each set's members - a room that draws ten sets must not
        make eleven queries.
        """

        uid, lang = self._scope()
        with Session(self.engine) as session:
            decks = list(
                session.scalars(
                    select(VocabularyDeck)
                    .where(VocabularyDeck.user_id == uid, VocabularyDeck.language_code == lang)
                    .order_by(VocabularyDeck.created_at)
                    .limit(DECK_LIMIT)
                )
            )
            if not decks:
                return []
            counts = dict(
                session.execute(
                    select(
                        VocabularyDeckMember.deck_id,
                        func.count(VocabularyDeckMember.id),
                    )
                    .where(VocabularyDeckMember.deck_id.in_([deck.id for deck in decks]))
                    .group_by(VocabularyDeckMember.deck_id)
                ).all()
            )
            return [self._dict(deck, size=int(counts.get(deck.id, 0))) for deck in decks]

    def words(self, deck_id: str, *, limit: int = WORD_LIMIT) -> list[dict[str, Any]]:
        """The words in a set, in the learner's own order.

        Only the word and where it sits: the meaning and the schedule are the
        library's, and a caller that needs them asks the library.
        """

        with Session(self.engine) as session:
            deck = self._deck(session, deck_id)
            rows = session.execute(
                select(SavedWord.word, VocabularyDeckMember.position, VocabularyDeckMember.added_at)
                .join(VocabularyDeckMember, VocabularyDeckMember.saved_word_id == SavedWord.id)
                .where(VocabularyDeckMember.deck_id == deck.id)
                .order_by(VocabularyDeckMember.position, VocabularyDeckMember.added_at)
                .limit(max(1, min(limit, WORD_LIMIT)))
            ).all()
            return [
                {"word": row[0], "position": int(row[1] or 0), "added_at": _iso(row[2])}
                for row in rows
            ]

    # --- writing ----------------------------------------------------------

    def create(self, *, title: str, cover: str = "violet") -> dict[str, Any]:
        uid, lang = self._scope()
        if cover not in DECK_COVERS:
            raise DeckConflict("unknown_cover")
        now = _now()
        deck = VocabularyDeck(
            id=uuid.uuid4(),
            user_id=uid,
            language_code=lang,
            title=title.strip(),
            cover=cover,
            version=1,
            created_at=now,
            updated_at=now,
        )
        with Session(self.engine) as session:
            session.add(deck)
            try:
                session.commit()
            except IntegrityError as error:
                session.rollback()
                # Two sets of one name in one language is the mistake the
                # unique constraint exists for; say which it was.
                raise DeckConflict("duplicate_title") from error
            session.refresh(deck)
            return self._dict(deck)

    def update(
        self,
        deck_id: str,
        *,
        expected_version: int,
        title: str | None = None,
        cover: str | None = None,
    ) -> dict[str, Any]:
        """Rename a set or change its cover, against the version it was read at."""

        with Session(self.engine) as session:
            deck = self._deck(session, deck_id)
            if deck.version != int(expected_version):
                raise DeckConflict("stale")
            if title is not None:
                trimmed = title.strip()
                if not trimmed:
                    raise DeckConflict("unknown_deck")
                deck.title = trimmed
            if cover is not None:
                if cover not in DECK_COVERS:
                    raise DeckConflict("unknown_cover")
                deck.cover = cover
            deck.version += 1
            deck.updated_at = _now()
            try:
                session.commit()
            except IntegrityError as error:
                session.rollback()
                raise DeckConflict("duplicate_title") from error
            session.refresh(deck)
            return self._dict(deck)

    def delete(self, deck_id: str) -> bool:
        """Forget a set. Its members go with it; the learner's words do not."""

        with Session(self.engine) as session:
            try:
                deck = self._deck(session, deck_id)
            except DeckConflict:
                return False
            session.delete(deck)
            session.commit()
            return True

    def add_word(self, deck_id: str, word: str) -> bool:
        """Put a word the learner already has into a set.

        Returns False when it was already in - filing a word twice is not an
        error, and the surface should not have to tell the two apart.
        """

        with Session(self.engine) as session:
            deck = self._deck(session, deck_id)
            saved = self._saved_word(session, word)
            existing = session.scalar(
                select(VocabularyDeckMember).where(
                    VocabularyDeckMember.deck_id == deck.id,
                    VocabularyDeckMember.saved_word_id == saved.id,
                )
            )
            if existing is not None:
                return False
            last = session.scalar(
                select(func.max(VocabularyDeckMember.position)).where(
                    VocabularyDeckMember.deck_id == deck.id
                )
            )
            session.add(
                VocabularyDeckMember(
                    id=uuid.uuid4(),
                    deck_id=deck.id,
                    saved_word_id=saved.id,
                    position=int(last or 0) + 1,
                    added_at=_now(),
                )
            )
            deck.updated_at = _now()
            try:
                session.commit()
            except IntegrityError:
                # Someone filed the same word at the same moment. The learner's
                # intent is satisfied either way.
                session.rollback()
                return False
            return True

    def remove_word(self, deck_id: str, word: str) -> bool:
        with Session(self.engine) as session:
            deck = self._deck(session, deck_id)
            saved = self._saved_word(session, word)
            member = session.scalar(
                select(VocabularyDeckMember).where(
                    VocabularyDeckMember.deck_id == deck.id,
                    VocabularyDeckMember.saved_word_id == saved.id,
                )
            )
            if member is None:
                return False
            session.delete(member)
            deck.updated_at = _now()
            session.commit()
            return True
