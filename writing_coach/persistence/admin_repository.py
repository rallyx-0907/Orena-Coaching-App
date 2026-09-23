"""Read-mostly queries behind the Platform Admin control center.

Everything read here already exists in the runtime schema: accounts, learning
profiles, the learner-evidence tables each capability owns, the shared content
catalogs and `audit_logs`. Nothing here adds a table or a column, and nothing
here selects learner-authored content: essays, passages, transcripts and saved
words are counted and dated, never read back.

The one write is an audit row (`audit_logs`, the table AI operation telemetry
already uses): an administrator viewing account metadata, acting on content, or
running an import leaves a record, which is what
`ORENA_ACCOUNT_DATA_ARCHITECTURE.md` §1 asks of any admin access to account data.

The SQL is deliberately portable so the hermetic suite can run it on SQLite; the
runtime reads PostgreSQL, and the only dialect branch is the UTC day boundary.
"""
from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import String, bindparam, func, inspect, literal, or_, select, text, union_all
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.types import Uuid

from writing_coach.admin_metrics import mask_email
from writing_coach.persistence.models import (
    AuditLog,
    Essay,
    GrammarProgress,
    ListeningProgress,
    ReadingAttempt,
    ReadingSession,
    SavedWord,
    ShadowingProgress,
    SpeakingAttempt,
    User,
    UserLanguageProfile,
    VocabularyCollection,
    VocabularyCollectionMembership,
    VocabularySourceImport,
)

# "Active" on the account list means a learning event within this many days.
ACTIVE_DAYS = 7
MAX_PAGE = 100
MAX_CATALOG_ROWS = 5000


def _utc(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)


def _iso(value: Any) -> str | None:
    stamp = _utc(value)
    return stamp.isoformat() if stamp else None


def _day(value: Any) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)[:10]


def _uuid(value: Any) -> uuid.UUID | None:
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _text_id(value: Any) -> str:
    parsed = _uuid(value)
    return str(parsed) if parsed else str(value)


class AdminConsoleRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self._tables: set[str] | None = None

    # -- shape helpers ------------------------------------------------------

    def _has_table(self, name: str) -> bool:
        if self._tables is None:
            try:
                self._tables = set(inspect(self.engine).get_table_names())
            except SQLAlchemyError:
                self._tables = set()
        return name in self._tables

    def _utc_day(self, column):
        # The day a learner did something is a UTC day on every chart, stated
        # as such, rather than whatever the database session happens to use.
        if self.engine.dialect.name == "postgresql":
            return func.date(func.timezone("UTC", column))
        return func.date(column)

    def _activity(self):
        """Every learning event the evidence tables already record, as one shape.

        `(user_id, at, domain, language)`; one row per stored event. Shadowing
        is speaking practice (the learner imitates aloud), and a reviewed word
        counts on the day of its most recent review because that is the only
        review date the schema keeps.
        """
        def part(user_id, at, domain, language, *where, source=None):
            statement = select(
                user_id.label("user_id"),
                at.label("at"),
                literal(domain, String).label("domain"),
                language.label("language"),
            )
            if source is not None:
                statement = statement.select_from(source)
            return statement.where(*where) if where else statement

        return union_all(
            part(Essay.user_id, Essay.created_at, "writing", Essay.language_code),
            part(ReadingSession.user_id, ReadingSession.created_at, "reading", ReadingSession.language_code),
            part(
                ReadingSession.user_id, ReadingAttempt.created_at, "reading", ReadingSession.language_code,
                source=ReadingAttempt.__table__.join(ReadingSession.__table__, ReadingAttempt.session_id == ReadingSession.id),
            ),
            part(ListeningProgress.user_id, ListeningProgress.updated_at, "listening", ListeningProgress.language_code),
            part(ShadowingProgress.user_id, ShadowingProgress.updated_at, "speaking", ShadowingProgress.language_code),
            part(SpeakingAttempt.user_id, SpeakingAttempt.created_at, "speaking", SpeakingAttempt.language_code),
            part(SavedWord.user_id, SavedWord.added_at, "vocabulary", SavedWord.language_code),
            part(
                SavedWord.user_id, SavedWord.last_reviewed_at, "vocabulary", SavedWord.language_code,
                SavedWord.last_reviewed_at.is_not(None),
            ),
            part(GrammarProgress.user_id, GrammarProgress.completed_at, "grammar", GrammarProgress.language_code),
        ).subquery("activity")

    # -- accounts -----------------------------------------------------------

    def account_totals(self, *, now: datetime) -> dict[str, int]:
        with Session(self.engine) as session:
            def count(*where):
                return int(session.scalar(select(func.count(User.id)).where(*where)) or 0)

            return {
                "total": count(),
                "admins": count(User.role == "admin"),
                "new_7d": count(User.created_at >= now - timedelta(days=7)),
                "new_30d": count(User.created_at >= now - timedelta(days=30)),
            }

    def registrations_by_day(self, since: datetime) -> dict[str, int]:
        day = self._utc_day(User.created_at)
        with Session(self.engine) as session:
            rows = session.execute(
                select(day.label("day"), func.count(User.id)).where(User.created_at >= since).group_by(day)
            ).all()
        return {_day(value): int(count) for value, count in rows}

    def language_profiles(self) -> list[dict[str, Any]]:
        learners = func.count(func.distinct(UserLanguageProfile.user_id))
        with Session(self.engine) as session:
            rows = session.execute(
                select(UserLanguageProfile.language_code, learners)
                .group_by(UserLanguageProfile.language_code)
                .order_by(learners.desc(), UserLanguageProfile.language_code)
            ).all()
        return [{"language": language, "learners": int(count)} for language, count in rows]

    # -- activity -------------------------------------------------------------

    def activity_rows(self, since: datetime) -> list[dict[str, Any]]:
        activity = self._activity()
        day = self._utc_day(activity.c.at)
        statement = (
            select(activity.c.user_id, day.label("day"), activity.c.domain, activity.c.language, func.count().label("events"))
            .where(activity.c.at >= since)
            .group_by(activity.c.user_id, day, activity.c.domain, activity.c.language)
        )
        with Session(self.engine) as session:
            rows = session.execute(statement).all()
        return [
            {"user_id": _text_id(user_id), "day": _day(value), "domain": domain, "language": language, "events": int(events)}
            for user_id, value, domain, language, events in rows
        ]

    def first_activity_by_user(self) -> dict[str, datetime]:
        activity = self._activity()
        with Session(self.engine) as session:
            rows = session.execute(select(activity.c.user_id, func.min(activity.c.at)).group_by(activity.c.user_id)).all()
        return {_text_id(user_id): _utc(first) for user_id, first in rows if _utc(first) is not None}

    # -- account list and detail ----------------------------------------------

    def _incarnation_states(self, session: Session, user_ids: list[uuid.UUID]) -> dict[str, str]:
        """Whether an account is deleted, where the backbone schema exists.

        Deletion has no runtime caller yet (D-055), so in practice this only
        ever answers `active`; it is read so that the day it does not, the list
        says so rather than showing a deleted account as a live one.
        """
        if not user_ids or not self._has_table("account_incarnations"):
            return {}
        statement = text(
            "SELECT user_id, status FROM account_incarnations WHERE user_id IN :ids"
        ).bindparams(bindparam("ids", expanding=True, type_=Uuid(as_uuid=True)))
        states: dict[str, set[str]] = {}
        for user_id, status in session.execute(statement, {"ids": user_ids}).all():
            states.setdefault(_text_id(user_id), set()).add(str(status))
        return {key: "deleted" if "active" not in value and "deleted" in value else "active" for key, value in states.items()}

    @staticmethod
    def _status(last_active: datetime | None, now: datetime, incarnation: str | None) -> str:
        if incarnation == "deleted":
            return "deleted"
        if last_active is None:
            return "no_activity"
        return "active" if last_active >= now - timedelta(days=ACTIVE_DAYS) else "idle"

    def list_accounts(
        self,
        *,
        now: datetime,
        query: str = "",
        language: str = "",
        role: str = "",
        activity: str = "",
        sort: str = "joined",
        limit: int = 25,
        offset: int = 0,
    ) -> dict[str, Any]:
        events = self._activity()
        # Filtering or ordering by activity needs every account's latest event.
        # Otherwise the page is chosen from the accounts alone, and only the
        # latest events of the accounts on it are read: the default list costs
        # one page, not the whole learning history.
        by_activity = activity in {"active", "idle", "never"} or sort == "active"
        columns = (User.id, User.name, User.email, User.role, User.created_at, User.last_login)
        last = None
        if by_activity:
            last = (
                select(events.c.user_id.label("user_id"), func.max(events.c.at).label("last_active"))
                .group_by(events.c.user_id)
                .subquery("last_activity")
            )
            statement = select(*columns, last.c.last_active).outerjoin(last, last.c.user_id == User.id)
        else:
            statement = select(*columns)

        needle = str(query or "").strip()
        if needle:
            escaped = needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"
            statement = statement.where(or_(User.name.ilike(pattern, escape="\\"), User.email.ilike(pattern, escape="\\")))
        if language:
            statement = statement.where(
                User.id.in_(select(UserLanguageProfile.user_id).where(UserLanguageProfile.language_code == language))
            )
        if role in {"admin", "user"}:
            statement = statement.where(User.role == role)
        recent = now - timedelta(days=ACTIVE_DAYS)
        if last is not None:
            if activity == "active":
                statement = statement.where(last.c.last_active >= recent)
            elif activity == "idle":
                statement = statement.where(last.c.last_active < recent)
            elif activity == "never":
                statement = statement.where(last.c.last_active.is_(None))

        orderings = {
            "joined": (User.created_at.desc(), User.id),
            "joined_asc": (User.created_at.asc(), User.id),
            "name": (func.lower(User.name).asc(), func.lower(User.email).asc()),
        }
        if last is not None:
            orderings["active"] = (last.c.last_active.desc().nulls_last(), User.created_at.desc())
        ordering = orderings.get(sort, (User.created_at.desc(), User.id))
        bounded = max(1, min(int(limit or 25), MAX_PAGE))
        start = max(0, int(offset or 0))

        with Session(self.engine) as session:
            total = int(session.scalar(select(func.count()).select_from(statement.subquery())) or 0)
            rows = session.execute(statement.order_by(*ordering).limit(bounded).offset(start)).all()
            ids = [row.id for row in rows]
            latest: dict[str, Any] = {}
            if last is None and ids:
                latest = {
                    _text_id(user_id): at
                    for user_id, at in session.execute(
                        select(events.c.user_id, func.max(events.c.at))
                        .where(events.c.user_id.in_(ids))
                        .group_by(events.c.user_id)
                    ).all()
                }
            languages: dict[str, list[str]] = {}
            if ids:
                for user_id, code in session.execute(
                    select(UserLanguageProfile.user_id, UserLanguageProfile.language_code)
                    .where(UserLanguageProfile.user_id.in_(ids))
                    .order_by(UserLanguageProfile.created_at)
                ).all():
                    languages.setdefault(_text_id(user_id), []).append(code)
            incarnations = self._incarnation_states(session, ids)

        items = []
        for row in rows:
            key = _text_id(row.id)
            last_active = _utc(row.last_active if last is not None else latest.get(key))
            items.append({
                "id": key,
                "display_name": row.name or "",
                "email_masked": mask_email(row.email),
                "role": row.role or "user",
                "joined_at": _iso(row.created_at),
                "last_login_at": _iso(row.last_login),
                "last_active_at": _iso(last_active),
                "languages": languages.get(key, []),
                # A declared level has no stored field yet (account_profile.py:
                # `declared_level` is `stored=False`), and measured proficiency
                # is not something the product claims. So there is none to show.
                "level": None,
                "status": self._status(last_active, now, incarnations.get(key)),
            })
        return {"items": items, "total": total, "limit": bounded, "offset": start}

    def account_detail(self, user_id: str, *, now: datetime) -> dict[str, Any] | None:
        identifier = _uuid(user_id)
        if identifier is None:
            return None
        with Session(self.engine) as session:
            user = session.get(User, identifier)
            if user is None:
                return None
            profiles = session.scalars(
                select(UserLanguageProfile).where(UserLanguageProfile.user_id == identifier).order_by(UserLanguageProfile.created_at)
            ).all()
            measures = (
                ("writing_submissions", Essay, Essay.language_code, Essay.created_at, ()),
                ("reading_sessions", ReadingSession, ReadingSession.language_code, ReadingSession.created_at, ()),
                ("listening_segments", ListeningProgress, ListeningProgress.language_code, ListeningProgress.updated_at, ()),
                ("shadowing_segments", ShadowingProgress, ShadowingProgress.language_code, ShadowingProgress.updated_at, ()),
                ("speaking_takes", SpeakingAttempt, SpeakingAttempt.language_code, SpeakingAttempt.created_at, ()),
                ("words_kept", SavedWord, SavedWord.language_code, SavedWord.added_at, ()),
                ("words_reviewed", SavedWord, SavedWord.language_code, SavedWord.last_reviewed_at, (SavedWord.last_reviewed_at.is_not(None),)),
                ("grammar_lessons", GrammarProgress, GrammarProgress.language_code, GrammarProgress.completed_at, ()),
            )
            activity: list[dict[str, Any]] = []
            for name, model, language, stamp, extra in measures:
                rows = session.execute(
                    select(language, func.count(), func.max(stamp))
                    .where(model.user_id == identifier, *extra)
                    .group_by(language)
                    .order_by(language)
                ).all()
                activity.extend(
                    {"measure": name, "language": code, "count": int(count), "last_at": _iso(latest)}
                    for code, count, latest in rows
                )
            checks = session.execute(
                select(ReadingSession.language_code, func.count(ReadingAttempt.id), func.max(ReadingAttempt.created_at))
                .select_from(ReadingAttempt.__table__.join(ReadingSession.__table__, ReadingAttempt.session_id == ReadingSession.id))
                .where(ReadingSession.user_id == identifier)
                .group_by(ReadingSession.language_code)
            ).all()
            activity.extend(
                {"measure": "reading_checks", "language": code, "count": int(count), "last_at": _iso(latest)}
                for code, count, latest in checks
            )
            incarnation = self._incarnation_states(session, [identifier]).get(str(identifier))
            events = self._activity()
            last_active = _utc(session.scalar(select(func.max(events.c.at)).where(events.c.user_id == identifier)))
            detail = {
                "id": str(identifier),
                "display_name": user.name or "",
                "email": user.email or "",
                "role": user.role or "user",
                "joined_at": _iso(user.created_at),
                "last_login_at": _iso(user.last_login),
                "last_active_at": _iso(last_active),
                "level": None,
                "status": self._status(last_active, now, incarnation),
                "account_state": incarnation or ("none" if self._has_table("account_incarnations") else "unavailable"),
                "profiles": [
                    {
                        "language": profile.language_code,
                        "goal": profile.goal,
                        "style": profile.style,
                        "support_language": profile.native_language,
                        "created_at": _iso(profile.created_at),
                        "updated_at": _iso(profile.updated_at),
                    }
                    for profile in profiles
                ],
                "activity": activity,
            }
        return detail

    # -- shared content catalogs --------------------------------------------

    def list_books(self, *, limit: int = MAX_CATALOG_ROWS) -> list[dict[str, Any]] | None:
        """Every book in every status, or None when the catalog schema is absent."""
        statement = text(
            "SELECT id, title, author, learning_language, status, chapter_count, word_count, "
            "cover_asset_key, source_kind, imported_by, created_at, updated_at "
            "FROM reading_books ORDER BY updated_at DESC LIMIT :limit"
        )
        try:
            with self.engine.connect() as connection:
                rows = connection.execute(statement, {"limit": max(1, min(int(limit), MAX_CATALOG_ROWS))}).mappings().all()
        except SQLAlchemyError:
            return None
        return [self._book(row) for row in rows]

    @staticmethod
    def _book(row: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "id": _text_id(row["id"]),
            "title": row["title"],
            "author": row["author"] or "",
            "language": row["learning_language"],
            "status": row["status"],
            "chapter_count": int(row["chapter_count"] or 0),
            "word_count": int(row["word_count"] or 0),
            "has_cover": bool(row["cover_asset_key"]),
            "source_kind": row["source_kind"],
            "imported_by": row["imported_by"] or "",
            "created_at": _iso(row["created_at"]) or str(row["created_at"] or ""),
            "updated_at": _iso(row["updated_at"]) or str(row["updated_at"] or ""),
        }

    def get_book(self, book_id: str) -> dict[str, Any] | None:
        identifier = _uuid(book_id)
        if identifier is None:
            return None
        typed = bindparam("id", type_=Uuid(as_uuid=True))
        try:
            with self.engine.connect() as connection:
                row = connection.execute(
                    text(
                        "SELECT id, title, author, description, learning_language, status, chapter_count, word_count, "
                        "cover_asset_key, source_kind, imported_by, created_at, updated_at FROM reading_books WHERE id = :id"
                    ).bindparams(typed),
                    {"id": identifier},
                ).mappings().first()
                if row is None:
                    return None
                chapters = connection.execute(
                    text(
                        "SELECT id, position, title, word_count FROM reading_book_chapters WHERE book_id = :id ORDER BY position"
                    ).bindparams(bindparam("id", type_=Uuid(as_uuid=True))),
                    {"id": identifier},
                ).mappings().all()
        except SQLAlchemyError:
            return None
        book = self._book(row)
        book["description"] = row["description"] or ""
        book["chapters"] = [
            {"id": _text_id(chapter["id"]), "position": int(chapter["position"]), "title": chapter["title"],
             "word_count": int(chapter["word_count"] or 0)}
            for chapter in chapters
        ]
        return book

    def list_vocabulary_collections(self) -> list[dict[str, Any]]:
        counts = (
            select(
                VocabularyCollectionMembership.collection_id.label("collection_id"),
                func.count(VocabularyCollectionMembership.id).label("member_count"),
            )
            .group_by(VocabularyCollectionMembership.collection_id)
            .subquery("membership_counts")
        )
        with Session(self.engine) as session:
            rows = session.execute(
                select(VocabularyCollection, counts.c.member_count)
                .outerjoin(counts, counts.c.collection_id == VocabularyCollection.id)
                .order_by(VocabularyCollection.updated_at.desc())
                .limit(MAX_CATALOG_ROWS)
            ).all()
        result = []
        for collection, count in rows:
            provenance = collection.provenance if isinstance(collection.provenance, Mapping) else {}
            admission = provenance.get("admission") if isinstance(provenance.get("admission"), Mapping) else {}
            result.append({
                "id": collection.id,
                "title": collection.title,
                "language": collection.language_code,
                "framework": collection.framework or "",
                "level": collection.level or "",
                "level_range": collection.level_range or "",
                "topic": collection.topic or "",
                "status": collection.catalog_status,
                "origin": collection.origin,
                "item_count": int(count or 0),
                "rights_status": str(admission.get("rights_status") or ""),
                "completeness": str(admission.get("completeness") or ""),
                "created_at": _iso(collection.created_at),
                "updated_at": _iso(collection.updated_at),
            })
        return result

    def list_vocabulary_imports(self, *, limit: int = 500) -> list[dict[str, Any]]:
        with Session(self.engine) as session:
            rows = session.execute(
                select(VocabularySourceImport, VocabularyCollection.title, VocabularyCollection.catalog_status)
                .outerjoin(VocabularyCollection, VocabularyCollection.id == VocabularySourceImport.collection_id)
                .order_by(VocabularySourceImport.created_at.desc())
                .limit(max(1, min(int(limit), MAX_CATALOG_ROWS)))
            ).all()
        result = []
        for receipt, title, status in rows:
            errors = receipt.errors if isinstance(receipt.errors, list) else []
            first_error = next((str(item.get("reason") or "") for item in errors if isinstance(item, Mapping)), "")
            result.append({
                "id": str(receipt.id),
                "filename": receipt.filename,
                "format": receipt.source_format,
                "status": receipt.status,
                "imported": int(receipt.imported_count or 0),
                "skipped": int(receipt.skipped_count or 0),
                "duplicates": int(receipt.duplicate_count or 0),
                "warnings": int(receipt.warning_count or 0),
                "failed": int(receipt.failed_count or 0),
                "error": first_error,
                "collection_id": receipt.collection_id or "",
                "collection_title": title or "",
                "collection_status": status or "",
                "imported_by": receipt.imported_by or "",
                "created_at": _iso(receipt.created_at),
            })
        return result

    # -- admin audit -------------------------------------------------------------

    def record_event(
        self,
        action: str,
        *,
        actor_key: str,
        entity_type: str = "",
        entity_id: str = "",
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        body = dict(payload or {})
        with Session(self.engine) as session, session.begin():
            actor = session.scalar(select(User.id).where(User.user_key == actor_key)) if actor_key else None
            if actor is None:
                # The local development administrator has no account row; its
                # key is kept in the record instead so the event still names
                # who acted.
                body["actor"] = str(actor_key or "unknown")
            session.add(
                AuditLog(
                    id=uuid.uuid4(),
                    user_id=actor,
                    action=str(action)[:160],
                    entity_type=str(entity_type)[:120],
                    entity_id=str(entity_id)[:255],
                    payload=body,
                    created_at=datetime.now(UTC),
                )
            )

    def find_import(self, *, kind: str, content_hash: str) -> str:
        """The content an earlier successful import of these bytes became, or ''.

        Read from the import receipts, which carry the SHA-256 of an uploaded
        file; the newest success wins, so a file imported again after its first
        copy was removed points at the copy that exists.
        """
        if not content_hash:
            return ""
        statement = (
            select(AuditLog.entity_id)
            .where(
                AuditLog.action == "admin.import",
                AuditLog.entity_type == kind,
                AuditLog.payload["content_hash"].as_string() == content_hash,
                AuditLog.payload["status"].as_string() == "ok",
            )
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        )
        with Session(self.engine) as session:
            return str(session.scalar(statement) or "")

    def list_events(
        self, actions: Iterable[str], *, limit: int = 500, since: datetime | None = None
    ) -> list[dict[str, Any]]:
        statement = select(AuditLog).where(AuditLog.action.in_(list(actions)))
        if since is not None:
            statement = statement.where(AuditLog.created_at >= since)
        with Session(self.engine) as session:
            rows = session.scalars(
                statement.order_by(AuditLog.created_at.desc()).limit(max(1, min(int(limit), MAX_CATALOG_ROWS)))
            ).all()
            return [
                {
                    "id": str(row.id),
                    "action": row.action,
                    "entity_type": row.entity_type,
                    "entity_id": row.entity_id,
                    "payload": dict(row.payload) if isinstance(row.payload, Mapping) else {},
                    "created_at": _iso(row.created_at),
                    "user_id": str(row.user_id) if row.user_id else None,
                }
                for row in rows
            ]
