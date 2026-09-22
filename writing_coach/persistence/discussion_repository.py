"""A learner's discussion about a whole text (D-072.2), approved 2026-09-22.

The proposal and the four review rounds behind every decision here are in
`docs/project/PROPOSAL_SAVED_REVIEWS_AND_TEXT_DISCUSSION.md`. The parts that
look unusual are the parts a reviewer required:

- The write is three transactions, not one. `reserve_turns` takes both ordinals
  and the permission to write in a single owner-scoped
  `UPDATE ... WHERE turn_count <= 198 RETURNING turn_count` and commits, the
  caller runs the provider with no lock held, and `append_turns` writes the
  pair afterwards. Holding one transaction across a provider call would hold
  the thread row's lock for the whole provider latency.
- A failed provider call therefore leaks its reserved ordinal pair. That is
  deliberate: decrementing `turn_count` would re-issue ordinals a concurrent
  submit may already hold. Ordinals are ordered, never contiguous.
- Zero rows from the reservation means cap *or* deleted *or* not yours, so it
  is never answered blind - the thread is re-read in the same transaction and
  the caller is told which.
- `source_id` is the routing identity string; `reading_session_id` is the
  internal UUID of a `reading_sessions` row. Different id spaces.

SQLite refuses, as `save_listening_progress_record` already does, so the test
backend never becomes a second persistence path for learner conversation.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from sqlalchemy import Engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from writing_coach.core.request_context import current_language_code, current_user_key
from writing_coach.persistence.ids import stable_uuid
from writing_coach.persistence.models import ReadingSession, TextDiscussion, TextDiscussionTurn

SOURCE_KINDS = ("story", "media", "reading_session", "book_chapter")
MAX_TURNS = 200
MAX_BODY_CHARACTERS = 4000
TURNS_PER_EXCHANGE = 2
PAGE_LIMIT = 100

_SQLITE_REFUSAL = "Durable text discussion requires the PostgreSQL runtime."


@dataclass(frozen=True)
class Reservation:
    """What one exchange was granted, or why it was not.

    `status` is `granted`, `cap_reached` or `missing`. The last two are told
    apart on purpose: a thread that is full and a thread that is not yours are
    different answers to the learner.
    """

    status: str
    discussion_id: uuid.UUID | None = None
    learner_ordinal: int = 0
    assistant_ordinal: int = 0


class TextDiscussionRepository(Protocol):
    def get_or_create_discussion(
        self, *, source_kind: str, source_id: str, reading_session_id: uuid.UUID | None = None
    ) -> dict[str, Any]: ...
    def find_discussion(self, *, source_kind: str, source_id: str) -> dict[str, Any] | None: ...
    def list_turns(
        self, discussion_id: uuid.UUID, *, after_ordinal: int = 0, limit: int = PAGE_LIMIT
    ) -> list[dict[str, Any]]: ...
    def find_turns_by_request(
        self, discussion_id: uuid.UUID, request_id: str
    ) -> list[dict[str, Any]]: ...
    def reserve_turns(self, discussion_id: uuid.UUID) -> Reservation: ...
    def append_turns(
        self, discussion_id: uuid.UUID, reservation: Reservation, turns: list[dict[str, Any]]
    ) -> list[dict[str, Any]] | None: ...
    def delete_discussion(self, *, source_kind: str, source_id: str) -> bool: ...
    def export_discussions(self) -> list[dict[str, Any]]: ...
    def resolve_reading_session(self, source_id: str) -> uuid.UUID | None: ...


class SQLiteTextDiscussionRepository:
    """Refuses rather than no-ops, so CI's SQLite never stores learner words."""

    def get_or_create_discussion(self, **_: Any) -> dict[str, Any]:
        raise RuntimeError(_SQLITE_REFUSAL)

    def find_discussion(self, **_: Any) -> dict[str, Any] | None:
        raise RuntimeError(_SQLITE_REFUSAL)

    def list_turns(self, *_: Any, **__: Any) -> list[dict[str, Any]]:
        raise RuntimeError(_SQLITE_REFUSAL)

    def find_turns_by_request(self, *_: Any, **__: Any) -> list[dict[str, Any]]:
        raise RuntimeError(_SQLITE_REFUSAL)

    def reserve_turns(self, *_: Any, **__: Any) -> Reservation:
        raise RuntimeError(_SQLITE_REFUSAL)

    def append_turns(self, *_: Any, **__: Any) -> list[dict[str, Any]] | None:
        raise RuntimeError(_SQLITE_REFUSAL)

    def delete_discussion(self, **_: Any) -> bool:
        raise RuntimeError(_SQLITE_REFUSAL)

    def export_discussions(self) -> list[dict[str, Any]]:
        raise RuntimeError(_SQLITE_REFUSAL)

    def resolve_reading_session(self, source_id: str) -> uuid.UUID | None:
        raise RuntimeError(_SQLITE_REFUSAL)


class PostgresTextDiscussionRepository:
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

    # --- scope and shape ------------------------------------------------

    def _scope(self) -> tuple[Any, str]:
        return stable_uuid("user", self._user_key_provider()), self._language_provider().casefold()

    @staticmethod
    def _iso(value: datetime | None) -> str | None:
        return value.isoformat() if value else None

    def _discussion_payload(self, row: TextDiscussion) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "source_kind": row.source_kind,
            "source_id": row.source_id,
            "language_code": row.language_code,
            # Null once the session is gone; the room decides what to show.
            "reading_session_id": str(row.reading_session_id) if row.reading_session_id else None,
            "turn_count": row.turn_count,
            "created_at": self._iso(row.created_at),
            "updated_at": self._iso(row.updated_at),
        }

    @staticmethod
    def _turn_payload(row: TextDiscussionTurn) -> dict[str, Any]:
        return {
            "ordinal": row.ordinal,
            "role": row.role,
            "body": row.body,
            "context": row.context,
            "provider": row.provider,
            "model": row.model,
            "created_at": row.created_at.isoformat(),
        }

    # --- reading --------------------------------------------------------

    def resolve_reading_session(self, source_id: str) -> uuid.UUID | None:
        """The learner's own session, by the `legacy_id` the app routes on.

        Returns the internal UUID the foreign key needs - the two ids are not
        interchangeable.
        """
        try:
            legacy_id = int(str(source_id).strip())
        except (TypeError, ValueError):
            return None
        uid, lang = self._scope()
        with Session(self.engine) as session:
            row = session.scalar(
                select(ReadingSession).where(
                    ReadingSession.user_id == uid,
                    ReadingSession.language_code == lang,
                    ReadingSession.legacy_id == legacy_id,
                )
            )
            return row.id if row else None

    def find_discussion(self, *, source_kind: str, source_id: str) -> dict[str, Any] | None:
        uid, lang = self._scope()
        with Session(self.engine) as session:
            row = self._select_discussion(session, uid, lang, source_kind, source_id)
            return self._discussion_payload(row) if row else None

    @staticmethod
    def _select_discussion(
        session: Session, uid: Any, lang: str, source_kind: str, source_id: str
    ) -> TextDiscussion | None:
        return session.scalar(
            select(TextDiscussion).where(
                TextDiscussion.user_id == uid,
                TextDiscussion.language_code == lang,
                TextDiscussion.source_kind == source_kind,
                TextDiscussion.source_id == source_id,
            )
        )

    def list_turns(
        self, discussion_id: uuid.UUID, *, after_ordinal: int = 0, limit: int = PAGE_LIMIT
    ) -> list[dict[str, Any]]:
        """Turns in `ordinal` order after a cursor. Never joins to the source,
        so a withdrawn text cannot fail the read."""
        bounded = min(max(1, int(limit)), PAGE_LIMIT)
        with Session(self.engine) as session:
            rows = session.scalars(
                select(TextDiscussionTurn)
                .where(
                    TextDiscussionTurn.discussion_id == discussion_id,
                    TextDiscussionTurn.ordinal > int(after_ordinal),
                )
                .order_by(TextDiscussionTurn.ordinal.asc())
                .limit(bounded)
            ).all()
            return [self._turn_payload(row) for row in rows]

    def find_turns_by_request(
        self, discussion_id: uuid.UUID, request_id: str
    ) -> list[dict[str, Any]]:
        """The exchange a repeated `request_id` already produced, if any."""
        if not request_id:
            return []
        with Session(self.engine) as session:
            learner = session.scalar(
                select(TextDiscussionTurn).where(
                    TextDiscussionTurn.discussion_id == discussion_id,
                    TextDiscussionTurn.request_id == request_id,
                )
            )
            if learner is None:
                return []
            rows = session.scalars(
                select(TextDiscussionTurn)
                .where(
                    TextDiscussionTurn.discussion_id == discussion_id,
                    TextDiscussionTurn.ordinal >= learner.ordinal,
                    TextDiscussionTurn.ordinal <= learner.ordinal + 1,
                )
                .order_by(TextDiscussionTurn.ordinal.asc())
            ).all()
            return [self._turn_payload(row) for row in rows]

    # --- writing --------------------------------------------------------

    def get_or_create_discussion(
        self, *, source_kind: str, source_id: str, reading_session_id: uuid.UUID | None = None
    ) -> dict[str, Any]:
        """Two concurrent first submits cannot raise: the loser inserts nothing
        and reads the winner's row."""
        if source_kind not in SOURCE_KINDS:
            raise ValueError(f"Unknown source kind: {source_kind!r}")
        uid, lang = self._scope()
        now = datetime.now(timezone.utc)
        with Session(self.engine) as session, session.begin():
            session.execute(
                text(
                    """
                    INSERT INTO text_discussions
                        (id, user_id, language_code, source_kind, source_id,
                         reading_session_id, turn_count, created_at, updated_at)
                    VALUES
                        (:id, :user_id, :language_code, :source_kind, :source_id,
                         :reading_session_id, 0, :now, :now)
                    ON CONFLICT (user_id, language_code, source_kind, source_id) DO NOTHING
                    """
                ),
                {
                    "id": stable_uuid(
                        "text-discussion", self._user_key_provider(), lang, source_kind, source_id
                    ),
                    "user_id": uid,
                    "language_code": lang,
                    "source_kind": source_kind,
                    "source_id": source_id,
                    "reading_session_id": reading_session_id,
                    "now": now,
                },
            )
            row = self._select_discussion(session, uid, lang, source_kind, source_id)
            if row is None:  # pragma: no cover - the insert just guaranteed it
                raise RuntimeError("The discussion could not be created.")
            return self._discussion_payload(row)

    def reserve_turns(self, discussion_id: uuid.UUID) -> Reservation:
        """One statement takes both ordinals and the permission to write."""
        uid, _ = self._scope()
        with Session(self.engine) as session, session.begin():
            granted = session.execute(
                text(
                    """
                    UPDATE text_discussions
                       SET turn_count = turn_count + :step, updated_at = :now
                     WHERE id = :discussion_id
                       AND user_id = :user_id
                       AND turn_count <= :ceiling
                    RETURNING turn_count
                    """
                ),
                {
                    "step": TURNS_PER_EXCHANGE,
                    "now": datetime.now(timezone.utc),
                    "discussion_id": discussion_id,
                    "user_id": uid,
                    "ceiling": MAX_TURNS - TURNS_PER_EXCHANGE,
                },
            ).scalar()
            if granted is not None:
                count = int(granted)
                return Reservation("granted", discussion_id, count - 1, count)
            # Zero rows is cap, deleted, or not yours. Say which.
            still_there = session.scalar(
                select(TextDiscussion.id).where(
                    TextDiscussion.id == discussion_id, TextDiscussion.user_id == uid
                )
            )
            return Reservation("cap_reached" if still_there else "missing")

    def append_turns(
        self, discussion_id: uuid.UUID, reservation: Reservation, turns: list[dict[str, Any]]
    ) -> list[dict[str, Any]] | None:
        """Both turns, at their reserved ordinals, in one transaction.

        Returns None when a repeated `request_id` lost the partial unique index
        - the caller reads the committed exchange back instead. The reserved
        ordinals are then a permanent gap, which the read path tolerates.
        """
        now = datetime.now(timezone.utc)
        try:
            with Session(self.engine) as session, session.begin():
                written = []
                for turn in turns:
                    row = TextDiscussionTurn(
                        id=stable_uuid(
                            "text-discussion-turn", str(discussion_id), str(turn["ordinal"])
                        ),
                        discussion_id=discussion_id,
                        ordinal=int(turn["ordinal"]),
                        role=turn["role"],
                        body=turn["body"],
                        context=turn.get("context", ""),
                        provider=turn.get("provider", ""),
                        model=turn.get("model", ""),
                        request_id=turn.get("request_id", ""),
                        created_at=now,
                    )
                    session.add(row)
                    written.append(row)
                session.flush()
                return [self._turn_payload(row) for row in written]
        except IntegrityError:
            return None

    def delete_discussion(self, *, source_kind: str, source_id: str) -> bool:
        """The learner clears their own thread. Rows go, nothing is flagged."""
        uid, lang = self._scope()
        with Session(self.engine) as session, session.begin():
            row = self._select_discussion(session, uid, lang, source_kind, source_id)
            if row is None:
                return False
            session.delete(row)
            return True

    def export_discussions(self) -> list[dict[str, Any]]:
        """Every thread of this learner and language, turns in `ordinal` order,
        for whatever the account export produces."""
        uid, lang = self._scope()
        with Session(self.engine) as session:
            threads = session.scalars(
                select(TextDiscussion)
                .where(TextDiscussion.user_id == uid, TextDiscussion.language_code == lang)
                .order_by(TextDiscussion.created_at.asc())
            ).all()
            out = []
            for thread in threads:
                rows = session.scalars(
                    select(TextDiscussionTurn)
                    .where(TextDiscussionTurn.discussion_id == thread.id)
                    .order_by(TextDiscussionTurn.ordinal.asc())
                ).all()
                out.append(
                    {
                        **self._discussion_payload(thread),
                        "turns": [self._turn_payload(row) for row in rows],
                    }
                )
            return out
