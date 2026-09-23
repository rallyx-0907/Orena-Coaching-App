"""What a learner kept, pinned and collected - `library_items` and its sets.

Schema `migrations/versions/20260923_0013_my_library_and_entry_identity.py`,
approved by independent architecture review round 1 and authorized for dev and
sandbox on 2026-09-23 (D-074). The contract it serves is
`docs/product/ORENA_COLLECTION_ARCHITECTURE.md` §2.

This repository writes relationships and nothing else. It stores no title, no
body and no snippet - reading a kept thing means going to its owner through
`source_id`, or through the saved word for a word - and it holds no review
schedule: words are scheduled in `saved_words` and stay there. What it adds to
the review queue is `pinned_at`, which is the order the design asks for,
"marked first, then whatever is due".

One implementation over SQLAlchemy, so the runtime's PostgreSQL and the
hermetic suite's SQLite exercise the same code. The suite builds its schema
from `models.py`, which mirrors the migration; the migration remains the
authority for the runtime.

Two rules the callers rely on:

- **A word is linked by row, everything else by routing identity.** The check
  constraint makes that a database guarantee, so `keep()` takes one or the
  other and never both.
- **A write carries the version it read.** `update()` fails rather than
  overwriting a change it did not see, the way `patch_learner_profile` already
  does for the profile - and the architecture review verified that this
  behaves under a real race.
"""
from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from writing_coach.core.request_context import current_language_code, current_user_key
from writing_coach.persistence.ids import stable_uuid
from writing_coach.persistence.models import (
    LIBRARY_KINDS,
    LIBRARY_RELATIONSHIPS,
    LIBRARY_STATES,
    LibraryCollection,
    LibraryCollectionMember,
    LibraryItem,
    SavedWord,
)

# A learner's own set is small by design, and the room draws it as a list.
COLLECTION_LIMIT = 200
ITEM_LOOKUP_LIMIT = 200


class LibraryConflict(RuntimeError):
    """A write that lost a race, or asked for something that is already there.

    `reason` is a stable key a surface can say: `version_conflict`,
    `kind_mismatch`, `unknown_item`, `unknown_collection`, `duplicate_title`.
    """

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value else ""


class LibraryRepository:
    """The learner's kept items and their sets, scoped by account and language."""

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

    # --- scope ------------------------------------------------------------

    def _scope(self) -> tuple[uuid.UUID, str]:
        return stable_uuid("user", self._user_key_provider()), self._language_provider().casefold()

    def _saved_word(self, session: Session, word: str) -> SavedWord | None:
        uid, lang = self._scope()
        return session.scalar(
            select(SavedWord).where(
                SavedWord.user_id == uid,
                SavedWord.language_code == lang,
                SavedWord.normalized_word == word.casefold(),
            )
        )

    # --- reading ----------------------------------------------------------

    @staticmethod
    def _item_dict(item: LibraryItem, *, word: str = "") -> dict[str, Any]:
        return {
            "id": str(item.id),
            "kind": item.kind,
            "source_id": item.source_id,
            "word": word,
            "relationship": item.relationship_kind,
            "state": item.state,
            "pinned": item.pinned_at is not None,
            "pinned_at": _iso(item.pinned_at),
            "note": item.note,
            "created_at": _iso(item.created_at),
            "updated_at": _iso(item.updated_at),
            "version": item.version,
        }

    def get(self, item_id: str) -> dict[str, Any] | None:
        uid, lang = self._scope()
        try:
            wanted = uuid.UUID(str(item_id))
        except (ValueError, AttributeError, TypeError):
            return None
        with Session(self.engine) as session:
            item = session.get(LibraryItem, wanted)
            if item is None or item.user_id != uid or item.language_code != lang:
                return None
            word = ""
            if item.saved_word_id is not None:
                saved = session.get(SavedWord, item.saved_word_id)
                word = saved.word if saved else ""
            payload = self._item_dict(item, word=word)
            payload["collections"] = [
                {"id": str(row.id), "title": row.title, "kind": row.kind}
                for row in session.scalars(
                    select(LibraryCollection)
                    .join(
                        LibraryCollectionMember,
                        LibraryCollectionMember.collection_id == LibraryCollection.id,
                    )
                    .where(LibraryCollectionMember.item_id == item.id)
                    .order_by(LibraryCollection.title)
                ).all()
            ]
            return payload

    def lookup(self, *, kind: str = "", source_ids: tuple[str, ...] = (), words: tuple[str, ...] = ()) -> list[dict[str, Any]]:
        """The learner's own state for things a listing is already drawing.

        A listing reads its rows from their owners; this says which of them the
        learner has kept, pinned or filed, in one query rather than one per row.
        """

        uid, lang = self._scope()
        with Session(self.engine) as session:
            query = select(LibraryItem).where(
                LibraryItem.user_id == uid, LibraryItem.language_code == lang
            )
            if kind:
                query = query.where(LibraryItem.kind == kind)
            words_by_id: dict[uuid.UUID, str] = {}
            if words:
                saved = session.scalars(
                    select(SavedWord).where(
                        SavedWord.user_id == uid,
                        SavedWord.language_code == lang,
                        SavedWord.normalized_word.in_([w.casefold() for w in words[:ITEM_LOOKUP_LIMIT]]),
                    )
                ).all()
                words_by_id = {row.id: row.word for row in saved}
                query = query.where(LibraryItem.saved_word_id.in_(list(words_by_id) or [uuid.uuid4()]))
            elif source_ids:
                query = query.where(LibraryItem.source_id.in_(list(source_ids[:ITEM_LOOKUP_LIMIT])))
            return [
                self._item_dict(item, word=words_by_id.get(item.saved_word_id or uuid.uuid4(), ""))
                for item in session.scalars(query.limit(ITEM_LOOKUP_LIMIT)).all()
            ]

    def review_queue(self, *, limit: int = 60, now: datetime | None = None) -> dict[str, Any]:
        """What to review, in the order the design asks for.

        "Marked first, then by SRS due date": every pinned item of any kind,
        oldest pin first, then the words that are due. Nothing here invents a
        schedule for a kind that has none - an unpinned passage is simply not
        in the queue.
        """

        uid, lang = self._scope()
        moment = now or _now()
        with Session(self.engine) as session:
            pinned = session.scalars(
                select(LibraryItem)
                .where(
                    LibraryItem.user_id == uid,
                    LibraryItem.language_code == lang,
                    LibraryItem.pinned_at.is_not(None),
                )
                .order_by(LibraryItem.pinned_at)
                .limit(limit)
            ).all()
            words = {
                row.id: row
                for row in session.scalars(
                    select(SavedWord).where(
                        SavedWord.id.in_([i.saved_word_id for i in pinned if i.saved_word_id])
                    )
                ).all()
            }
            entries = [
                self._item_dict(item, word=words[item.saved_word_id].word if item.saved_word_id in words else "")
                for item in pinned
            ]
            due = session.scalar(
                select(SavedWord)
                .where(
                    SavedWord.user_id == uid,
                    SavedWord.language_code == lang,
                    (SavedWord.next_review_at.is_(None)) | (SavedWord.next_review_at <= moment),
                )
                .limit(1)
            )
            due_count = session.query(SavedWord).where(
                SavedWord.user_id == uid,
                SavedWord.language_code == lang,
                (SavedWord.next_review_at.is_(None)) | (SavedWord.next_review_at <= moment),
            ).count()
        return {
            "pinned": entries,
            "pinned_count": len(entries),
            "due_count": int(due_count),
            "first_due_word": due.word if due is not None else "",
            "total": len(entries) + int(due_count),
        }

    # --- writing ----------------------------------------------------------

    def keep(
        self,
        *,
        kind: str,
        word: str = "",
        source_id: str = "",
        relationship: str = "kept",
    ) -> dict[str, Any]:
        """Record that the learner kept this, or return what is already there.

        Idempotent by the same key the database is unique on, so a second tap
        on "keep" is the same relationship rather than a second row.
        """

        if kind not in LIBRARY_KINDS:
            raise LibraryConflict("kind_mismatch")
        if relationship not in LIBRARY_RELATIONSHIPS:
            raise LibraryConflict("kind_mismatch")
        uid, lang = self._scope()
        moment = _now()
        with Session(self.engine) as session, session.begin():
            saved_id = None
            saved_word = ""
            if kind == "word":
                saved = self._saved_word(session, word)
                if saved is None:
                    raise LibraryConflict("unknown_item")
                saved_id, saved_word = saved.id, saved.word
                source_id = ""
                existing = session.scalar(
                    select(LibraryItem).where(
                        LibraryItem.user_id == uid,
                        LibraryItem.saved_word_id == saved_id,
                        LibraryItem.relationship_kind == relationship,
                    )
                )
            else:
                if not str(source_id or "").strip():
                    raise LibraryConflict("unknown_item")
                existing = session.scalar(
                    select(LibraryItem).where(
                        LibraryItem.user_id == uid,
                        LibraryItem.language_code == lang,
                        LibraryItem.kind == kind,
                        LibraryItem.source_id == source_id,
                        LibraryItem.relationship_kind == relationship,
                    )
                )
            if existing is not None:
                return self._item_dict(existing, word=saved_word)
            item = LibraryItem(
                id=uuid.uuid4(),
                user_id=uid,
                language_code=lang,
                kind=kind,
                saved_word_id=saved_id,
                source_id=source_id,
                relationship_kind=relationship,
                state=None,
                pinned_at=None,
                note="",
                created_at=moment,
                updated_at=moment,
                version=1,
            )
            session.add(item)
            try:
                session.flush()
            except IntegrityError as error:
                # Lost the insert race; the row the winner wrote is the answer.
                session.rollback()
                raise LibraryConflict("version_conflict") from error
            return self._item_dict(item, word=saved_word)

    def update(
        self,
        item_id: str,
        *,
        expected_version: int,
        pinned: bool | None = None,
        state: str | None = None,
        clear_state: bool = False,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Change what the learner said about a kept thing.

        The version is checked in the UPDATE itself, so two writers that both
        read version N produce one change and one refusal, never a silent
        overwrite.
        """

        if state is not None and state not in LIBRARY_STATES:
            raise LibraryConflict("kind_mismatch")
        uid, lang = self._scope()
        moment = _now()
        try:
            wanted = uuid.UUID(str(item_id))
        except (ValueError, AttributeError, TypeError):
            raise LibraryConflict("unknown_item") from None
        with Session(self.engine) as session, session.begin():
            item = session.get(LibraryItem, wanted)
            if item is None or item.user_id != uid or item.language_code != lang:
                raise LibraryConflict("unknown_item")
            if int(item.version) != int(expected_version):
                raise LibraryConflict("version_conflict")
            if pinned is not None:
                item.pinned_at = moment if pinned else None
            if clear_state:
                item.state = None
            elif state is not None:
                item.state = state
            if note is not None:
                item.note = note
            item.version = int(item.version) + 1
            item.updated_at = moment
            session.flush()
            word = ""
            if item.saved_word_id is not None:
                saved = session.get(SavedWord, item.saved_word_id)
                word = saved.word if saved else ""
            return self._item_dict(item, word=word)

    def forget(self, item_id: str) -> bool:
        """Remove the relationship. The source, the word and its review
        evidence are untouched - that is the Collection Architecture's rule,
        and it is why this deletes a `library_items` row and nothing else."""

        uid, lang = self._scope()
        try:
            wanted = uuid.UUID(str(item_id))
        except (ValueError, AttributeError, TypeError):
            return False
        with Session(self.engine) as session, session.begin():
            item = session.get(LibraryItem, wanted)
            if item is None or item.user_id != uid or item.language_code != lang:
                return False
            session.delete(item)
            return True

    # --- collections ------------------------------------------------------

    @staticmethod
    def _collection_dict(row: LibraryCollection, *, size: int = 0) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "kind": row.kind,
            "title": row.title,
            "size": size,
            "created_at": _iso(row.created_at),
            "updated_at": _iso(row.updated_at),
        }

    def collections(self, *, kind: str = "") -> list[dict[str, Any]]:
        uid, lang = self._scope()
        with Session(self.engine) as session:
            query = select(LibraryCollection).where(
                LibraryCollection.user_id == uid, LibraryCollection.language_code == lang
            )
            if kind:
                query = query.where(LibraryCollection.kind == kind)
            rows = session.scalars(query.order_by(LibraryCollection.title).limit(COLLECTION_LIMIT)).all()
            sizes = {
                row.id: session.query(LibraryCollectionMember)
                .where(LibraryCollectionMember.collection_id == row.id)
                .count()
                for row in rows
            }
            return [self._collection_dict(row, size=sizes.get(row.id, 0)) for row in rows]

    def create_collection(self, *, kind: str, title: str) -> dict[str, Any]:
        if kind not in LIBRARY_KINDS:
            raise LibraryConflict("kind_mismatch")
        clean = str(title or "").strip()
        if not clean:
            raise LibraryConflict("unknown_collection")
        uid, lang = self._scope()
        moment = _now()
        with Session(self.engine) as session, session.begin():
            row = LibraryCollection(
                id=uuid.uuid4(), user_id=uid, language_code=lang, kind=kind,
                title=clean[:120], created_at=moment, updated_at=moment,
            )
            session.add(row)
            try:
                session.flush()
            except IntegrityError as error:
                session.rollback()
                raise LibraryConflict("duplicate_title") from error
            return self._collection_dict(row)

    def add_to_collection(self, collection_id: str, item_id: str) -> dict[str, Any]:
        """Put an item in a set of the same kind.

        The database refuses a cross-kind membership through the composite
        (id, kind) references, so this reports `kind_mismatch` rather than
        re-checking what the schema already guarantees.
        """

        uid, lang = self._scope()
        moment = _now()
        try:
            collection_uuid = uuid.UUID(str(collection_id))
            item_uuid = uuid.UUID(str(item_id))
        except (ValueError, AttributeError, TypeError):
            raise LibraryConflict("unknown_collection") from None
        with Session(self.engine) as session, session.begin():
            collection = session.get(LibraryCollection, collection_uuid)
            if collection is None or collection.user_id != uid or collection.language_code != lang:
                raise LibraryConflict("unknown_collection")
            item = session.get(LibraryItem, item_uuid)
            if item is None or item.user_id != uid or item.language_code != lang:
                raise LibraryConflict("unknown_item")
            if item.kind != collection.kind:
                raise LibraryConflict("kind_mismatch")
            existing = session.get(LibraryCollectionMember, (collection_uuid, item_uuid))
            if existing is not None:
                return {"added": False, "collection_id": str(collection_uuid), "item_id": str(item_uuid)}
            last = session.query(LibraryCollectionMember).where(
                LibraryCollectionMember.collection_id == collection_uuid
            ).count()
            session.add(
                LibraryCollectionMember(
                    collection_id=collection_uuid, item_id=item_uuid, kind=item.kind,
                    position=last, created_at=moment,
                )
            )
            collection.updated_at = moment
            session.flush()
            return {"added": True, "collection_id": str(collection_uuid), "item_id": str(item_uuid)}

    def remove_from_collection(self, collection_id: str, item_id: str) -> bool:
        uid, lang = self._scope()
        try:
            collection_uuid = uuid.UUID(str(collection_id))
            item_uuid = uuid.UUID(str(item_id))
        except (ValueError, AttributeError, TypeError):
            return False
        with Session(self.engine) as session, session.begin():
            collection = session.get(LibraryCollection, collection_uuid)
            if collection is None or collection.user_id != uid or collection.language_code != lang:
                return False
            member = session.get(LibraryCollectionMember, (collection_uuid, item_uuid))
            if member is None:
                return False
            session.delete(member)
            return True

    def collection_items(self, collection_id: str) -> list[dict[str, Any]]:
        """What is in a set, in the order it was filed.

        Ordered by (position, created_at): `position` has no unique constraint,
        so ties are possible and the read is what makes the order stable -
        architecture review round 1, P3-4.
        """

        uid, lang = self._scope()
        try:
            collection_uuid = uuid.UUID(str(collection_id))
        except (ValueError, AttributeError, TypeError):
            return []
        with Session(self.engine) as session:
            collection = session.get(LibraryCollection, collection_uuid)
            if collection is None or collection.user_id != uid or collection.language_code != lang:
                return []
            rows = session.execute(
                select(LibraryItem, LibraryCollectionMember)
                .join(LibraryCollectionMember, LibraryCollectionMember.item_id == LibraryItem.id)
                .where(LibraryCollectionMember.collection_id == collection_uuid)
                .order_by(LibraryCollectionMember.position, LibraryCollectionMember.created_at)
                .limit(COLLECTION_LIMIT)
            ).all()
            words = {
                row.id: row.word
                for row in session.scalars(
                    select(SavedWord).where(
                        SavedWord.id.in_([item.saved_word_id for item, _ in rows if item.saved_word_id])
                    )
                ).all()
            }
            return [
                self._item_dict(item, word=words.get(item.saved_word_id or uuid.uuid4(), ""))
                for item, _ in rows
            ]
