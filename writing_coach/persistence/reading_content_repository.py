"""Sources, snapshots, articles, targets and the review trail.

Schema: `migrations/proposed/20260922_0010_reading_content_engine.py` -
proposed, reviewed, rehearsed, not yet applied to any runtime. See
`docs/project/READING_CONTENT_ENGINE_SCHEMA_REVIEW_REQUEST.md`.

Three rules this module exists to keep, each of which a learner would feel if
it broke:

- **A snapshot is never rewritten.** The only `UPDATE` this module issues
  against `reading_source_items` sets `superseded_at`, and it names that one
  column. On PostgreSQL a trigger enforces the rule; here it is a design
  constraint with a test that watches the SQL actually issued. The targeting
  matters as much as the rule: the trigger compares `rights_snapshot_json` by
  its stored bytes, so a whole-row write - or an ORM `merge()` that
  re-serialises that JSON with a different key order - would be refused even
  though nothing about it changed.
- **`estimated_level` is the machine's and stays the machine's.** An admin
  correction writes `reviewed_level`; `effective_level` - the column the
  learner list filters on - is maintained here as `reviewed_level` when set,
  else `estimated_level`, and is the only one a query ever reads.
- **A list is a list.** The learner list and the admin queue return
  projections without bodies, source payloads, analysis or review history; the
  detail reads fetch those. That is what keeps a learner's request the same
  size whether the corpus holds 500 articles or 500,000.

Portable SQLAlchemy, like `admin_repository.py`: the hermetic suite runs this
same SQL on SQLite while the runtime reads PostgreSQL.
"""
from __future__ import annotations

import base64
import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.engine import Engine

from writing_coach.persistence.models import (
    ReadingArticle,
    ReadingArticleTarget,
    ReadingReviewEvent,
    ReadingSource,
    ReadingSourceItem,
)

DEFAULT_ARTICLE_PAGE = 24
MAX_ARTICLE_PAGE = 60
MIN_TARGETS = 3
MAX_TARGETS = 8

# The three built-in input paths, with the ids the migration seeds. Kept here
# as well because the hermetic suite creates its tables from metadata and has
# no migration to seed them - `ensure_built_in_sources()` is the idempotent
# bridge, and both sides must agree or manual dedupe silently stops working.
BUILT_IN_SOURCES: dict[str, tuple[str, str, str]] = {
    "manual": ("0a52e5d0-0000-4000-8000-000000000001", "orena-manual", "Manual paste"),
    "direct_url": ("0a52e5d0-0000-4000-8000-000000000002", "orena-direct-url", "Direct URL"),
    "file": ("0a52e5d0-0000-4000-8000-000000000003", "orena-file-upload", "File upload"),
}

LEARNER_VISIBLE_STATUS = "published"
QUEUE_STATUSES = ("draft", "processing", "needs_review", "ready")


class InvalidCursor(ValueError):
    """A `cursor` value that does not decode to this query's own shape."""


@dataclass(frozen=True)
class TargetInput:
    text: str
    canonical_form: str
    target_type: str
    context: str
    estimated_level: str
    rank: int
    meaning: str = ""
    machine_suggested: bool = True


def _now(value: datetime | None) -> datetime:
    return value or datetime.now(UTC)


def _aware(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)


def _iso(value: Any) -> str | None:
    moment = _aware(value)
    return moment.isoformat() if moment else None


def _uuid(value: Any) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _encode_cursor(moment: datetime, row_id: str) -> str:
    payload = json.dumps({"at": moment.isoformat(), "id": row_id}).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii")


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")))
        return datetime.fromisoformat(payload["at"]), uuid.UUID(payload["id"])
    except Exception as exc:  # noqa: BLE001 - any malformed cursor is the same outcome
        raise InvalidCursor(cursor) from exc


def _effective(estimated: str, reviewed: str | None) -> str:
    return reviewed if reviewed else estimated


def _source(row: Any) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "slug": row.slug,
        "name": row.name,
        "source_type": row.source_type,
        "base_url": row.base_url,
        "state": row.state,
        "languages": list(row.languages or []),
        "rights": {
            "automation_allowed": bool(row.automation_allowed),
            "can_republish": bool(row.can_republish),
            "can_adapt": bool(row.can_adapt),
            "attribution_required": bool(row.attribution_required),
            "license_note": row.license_note,
        },
        "polling_enabled": bool(row.polling_enabled),
        "last_checked_at": _iso(row.last_checked_at),
        "last_success_at": _iso(row.last_success_at),
        "last_error": row.last_error,
        "created_at": _iso(row.created_at),
    }


def _item(row: Any) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "source_id": str(row.source_id),
        "source_native_id": row.source_native_id,
        "canonical_url": row.canonical_url,
        "title": row.original_title,
        "author": row.original_author,
        "published_at": _iso(row.original_published_at),
        "language": row.original_language,
        "body": row.original_content,
        "content_hash": row.content_hash,
        "metadata": dict(row.metadata_json or {}),
        "rights": dict(row.rights_snapshot_json or {}),
        "revision": row.revision,
        "supersedes_id": str(row.supersedes_id) if row.supersedes_id else None,
        "superseded_at": _iso(row.superseded_at),
        "fetched_at": _iso(row.fetched_at),
    }


def _target(row: Any) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "text": row.text,
        "canonical_form": row.canonical_form,
        "target_type": row.target_type,
        "context": row.context,
        "meaning": row.meaning,
        "estimated_level": row.estimated_level,
        "rank": row.rank,
        "machine_suggested": bool(row.machine_suggested),
        "admin_approved": bool(row.admin_approved),
        "admin_rejected": bool(row.admin_rejected),
    }


def _article(row: Any) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "source_item_id": str(row.source_item_id),
        "title": row.title,
        "body": row.body,
        "excerpt": row.excerpt,
        "language": row.language,
        "topic": row.topic,
        "subtopic": row.subtopic,
        "estimated_level": row.estimated_level,
        "estimated_level_confidence": row.estimated_level_confidence,
        "reviewed_level": row.reviewed_level,
        "effective_level": row.effective_level,
        "word_count": row.word_count,
        "reading_time_seconds": row.reading_time_seconds,
        "is_adapted": bool(row.is_adapted),
        "adaptation": dict(row.adaptation_json or {}),
        "analysis": dict(row.analysis_json or {}),
        "status": row.status,
        "rejection_reason": row.rejection_reason,
        "content_revision": row.content_revision,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
        "published_at": _iso(row.published_at),
        "unpublished_at": _iso(row.unpublished_at),
    }


def _queue_row(row: Any) -> dict[str, Any]:
    """Admin Review Queue: enough to decide what to open, never the article."""
    return {
        "id": str(row.id),
        "title": row.title,
        "language": row.language,
        "topic": row.topic,
        "level": row.effective_level,
        "estimated_level": row.estimated_level,
        "reviewed_level": row.reviewed_level,
        "word_count": row.word_count,
        "reading_time_seconds": row.reading_time_seconds,
        "status": row.status,
        "created_at": _iso(row.created_at),
    }


def _learner_row(row: Any) -> dict[str, Any]:
    """The learner list projection. Every field here is one a card draws."""
    return {
        "id": str(row.id),
        "title": row.title,
        "language": row.language,
        "level": row.effective_level,
        "topic": row.topic,
        "reading_time_seconds": row.reading_time_seconds,
        "word_count": row.word_count,
        "excerpt": row.excerpt,
        "published_at": _iso(row.published_at),
        "content_revision": row.content_revision,
    }


class ReadingContentRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    # ---- sources ---------------------------------------------------------
    def ensure_built_in_sources(self, *, now: datetime | None = None) -> None:
        """Insert the three built-in sources if they are absent.

        Idempotent, and it agrees with the migration's seed rows down to the
        ids: the runtime gets them from the migration, the hermetic suite from
        here, and manual dedupe (`(source_id, content_hash)`) only works while
        both spell the same id.
        """
        moment = _now(now)
        with self.engine.begin() as connection:
            present = {
                str(row.id)
                for row in connection.execute(select(ReadingSource.id)).all()
            }
            for source_type, (source_id, slug, name) in BUILT_IN_SOURCES.items():
                if source_id in present:
                    continue
                connection.execute(
                    insert(ReadingSource).values(
                        id=_uuid(source_id),
                        slug=slug,
                        name=name,
                        source_type=source_type,
                        state="active",
                        languages=["en", "zh"],
                        topic_hints=[],
                        polling_policy={},
                        created_by="orena:reading-engine",
                        created_at=moment,
                        updated_at=moment,
                    )
                )

    def built_in_source_id(self, kind: str) -> str:
        try:
            return BUILT_IN_SOURCES[kind][0]
        except KeyError as exc:
            raise ValueError(f"unknown built-in source: {kind}") from exc

    def create_source(
        self,
        *,
        slug: str,
        name: str,
        source_type: str,
        base_url: str,
        languages: Sequence[str],
        rights: dict[str, Any],
        created_by: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """A source an admin adds. It starts unapproved, whatever it claims.

        `state` is `needs_review` and polling is off, so nothing an admin types
        into this form can begin fetching on its own - approval is a separate,
        deliberate act (spec SS9).
        """
        moment = _now(now)
        source_id = uuid.uuid4()
        with self.engine.begin() as connection:
            connection.execute(
                insert(ReadingSource).values(
                    id=source_id,
                    slug=slug,
                    name=name,
                    source_type=source_type,
                    base_url=base_url,
                    state="needs_review",
                    languages=list(languages),
                    topic_hints=[],
                    automation_allowed=bool(rights.get("automation_allowed")),
                    can_republish=bool(rights.get("can_republish")),
                    can_adapt=bool(rights.get("can_adapt")),
                    attribution_required=bool(rights.get("attribution_required", True)),
                    license_note=str(rights.get("license_note", "")),
                    polling_enabled=False,
                    polling_policy={},
                    created_by=created_by,
                    created_at=moment,
                    updated_at=moment,
                )
            )
            row = connection.execute(
                select(ReadingSource).where(ReadingSource.id == source_id)
            ).first()
        return _source(row)

    def get_source(self, source_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(ReadingSource).where(ReadingSource.id == _uuid(source_id))
            ).first()
        return _source(row) if row else None

    def list_sources(self) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(ReadingSource).order_by(ReadingSource.state, ReadingSource.name)
            ).all()
        return [_source(row) for row in rows]

    def set_source_state(
        self, source_id: str, state: str, *, actor: str, now: datetime | None = None
    ) -> dict[str, Any] | None:
        moment = _now(now)
        values: dict[str, Any] = {"state": state, "updated_at": moment}
        if state == "active":
            values |= {"approved_by": actor, "approved_at": moment}
        if state != "active":
            # The database says the same thing; setting it here keeps the row
            # consistent rather than relying on a constraint to refuse later.
            values["polling_enabled"] = False
        with self.engine.begin() as connection:
            updated = connection.execute(
                update(ReadingSource)
                .where(ReadingSource.id == _uuid(source_id))
                .values(**values)
            ).rowcount
        return self.get_source(source_id) if updated else None

    def set_polling(
        self, source_id: str, *, enabled: bool, actor: str, now: datetime | None = None
    ) -> dict[str, Any] | None:
        """Turn polling on only where the rights and the approval both allow it.

        Returns None when they do not - the refusal is a normal outcome an
        admin sees as a message, not an exception, and the CHECK constraint
        behind it is the backstop rather than the first line.
        """
        source = self.get_source(source_id)
        if source is None:
            return None
        if enabled and not (source["state"] == "active" and source["rights"]["automation_allowed"]):
            return None
        with self.engine.begin() as connection:
            connection.execute(
                update(ReadingSource)
                .where(ReadingSource.id == _uuid(source_id))
                .values(polling_enabled=bool(enabled), updated_at=_now(now))
            )
        return self.get_source(source_id)

    # ---- snapshots -------------------------------------------------------
    def record_source_item(
        self,
        *,
        source_id: str,
        source_native_id: str,
        canonical_url: str,
        title: str,
        author: str,
        published_at: datetime | None,
        language: str,
        body: str,
        content_hash: str,
        metadata: dict[str, Any],
        rights: dict[str, Any],
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Store one original snapshot, or recognise it as one already held.

        Three outcomes, in order:

        1. These exact bytes already exist for this source - return that row
           with `duplicate: True`. Running the same input twice never produces
           a second candidate.
        2. This source's own id for the item exists with *different* bytes -
           the source changed. Stamp the current row `superseded_at`, then
           insert the new one pointing back at it. That order is forced: two
           rows with `superseded_at IS NULL` for one native id is exactly what
           the partial unique index forbids, which is also what makes two
           workers racing here safe.
        3. Otherwise it is new.
        """
        moment = _now(now)
        with self.engine.begin() as connection:
            existing = connection.execute(
                select(ReadingSourceItem).where(
                    ReadingSourceItem.source_id == _uuid(source_id),
                    ReadingSourceItem.content_hash == content_hash,
                )
            ).first()
            if existing is not None:
                # A revert: these bytes are on file but were superseded. The
                # row that holds them becomes current again and the one that
                # replaced it is stamped - `revision` is a creation-order
                # counter, so it does not move.
                if existing.superseded_at is not None:
                    connection.execute(
                        update(ReadingSourceItem)
                        .where(
                            ReadingSourceItem.source_id == _uuid(source_id),
                            ReadingSourceItem.source_native_id == existing.source_native_id,
                            ReadingSourceItem.superseded_at.is_(None),
                            ReadingSourceItem.source_native_id != "",
                        )
                        .values(superseded_at=moment)
                    )
                    connection.execute(
                        update(ReadingSourceItem)
                        .where(ReadingSourceItem.id == existing.id)
                        .values(superseded_at=None)
                    )
                    existing = connection.execute(
                        select(ReadingSourceItem).where(ReadingSourceItem.id == existing.id)
                    ).first()
                return {**_item(existing), "duplicate": True}

            revision = 1
            supersedes: uuid.UUID | None = None
            if source_native_id:
                current = connection.execute(
                    select(ReadingSourceItem).where(
                        ReadingSourceItem.source_id == _uuid(source_id),
                        ReadingSourceItem.source_native_id == source_native_id,
                        ReadingSourceItem.superseded_at.is_(None),
                    )
                ).first()
                if current is not None:
                    connection.execute(
                        update(ReadingSourceItem)
                        .where(ReadingSourceItem.id == current.id)
                        .values(superseded_at=moment)
                    )
                    revision = current.revision + 1
                    supersedes = current.id

            item_id = uuid.uuid4()
            connection.execute(
                insert(ReadingSourceItem).values(
                    id=item_id,
                    source_id=_uuid(source_id),
                    source_native_id=source_native_id,
                    canonical_url=canonical_url,
                    original_title=title,
                    original_author=author,
                    original_published_at=published_at,
                    original_language=language,
                    original_content=body,
                    content_hash=content_hash,
                    metadata_json=dict(metadata or {}),
                    rights_snapshot_json=dict(rights or {}),
                    revision=revision,
                    supersedes_id=supersedes,
                    fetched_at=moment,
                    created_at=moment,
                )
            )
            row = connection.execute(
                select(ReadingSourceItem).where(ReadingSourceItem.id == item_id)
            ).first()
        return {**_item(row), "duplicate": False}

    def get_source_item(self, item_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(ReadingSourceItem).where(ReadingSourceItem.id == _uuid(item_id))
            ).first()
        return _item(row) if row else None

    def find_duplicate_content(
        self, content_hash: str, *, exclude_source_id: str
    ) -> list[dict[str, Any]]:
        """The same bytes under a *different* source.

        Legitimate - rights differ per source - but an admin about to publish
        a second copy should be told, which is why this exists and why the
        hash has a non-unique index of its own.
        """
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(
                    ReadingSourceItem.id,
                    ReadingSourceItem.source_id,
                    ReadingSourceItem.original_title,
                ).where(
                    ReadingSourceItem.content_hash == content_hash,
                    ReadingSourceItem.source_id != _uuid(exclude_source_id),
                )
            ).all()
        return [
            {"id": str(row.id), "source_id": str(row.source_id), "title": row.original_title}
            for row in rows
        ]

    # ---- articles --------------------------------------------------------
    def create_article(
        self,
        *,
        source_item_id: str,
        title: str,
        body: str,
        excerpt: str,
        language: str,
        topic: str,
        estimated_level: str,
        estimated_confidence: float,
        word_count: int,
        reading_time_seconds: int,
        analysis: dict[str, Any],
        targets: Sequence[TargetInput],
        subtopic: str = "",
        status: str = "needs_review",
        actor: str = "orena:reading-engine",
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """One candidate article and its targets, in one transaction.

        `status` is `needs_review`: the engine proposes, an admin publishes.
        Nothing here can make an article learner-visible.
        """
        moment = _now(now)
        article_id = uuid.uuid4()
        with self.engine.begin() as connection:
            connection.execute(
                insert(ReadingArticle).values(
                    id=article_id,
                    source_item_id=_uuid(source_item_id),
                    title=title,
                    body=body,
                    excerpt=excerpt,
                    language=language,
                    topic=topic,
                    subtopic=subtopic,
                    estimated_level=estimated_level,
                    estimated_level_confidence=float(estimated_confidence),
                    reviewed_level=None,
                    effective_level=estimated_level,
                    word_count=int(word_count),
                    reading_time_seconds=int(reading_time_seconds),
                    is_adapted=False,
                    adaptation_json={},
                    analysis_json=dict(analysis or {}),
                    status=status,
                    content_revision=1,
                    created_at=moment,
                    updated_at=moment,
                )
            )
            for target in targets:
                connection.execute(
                    insert(ReadingArticleTarget).values(
                        id=uuid.uuid4(),
                        article_id=article_id,
                        text=target.text,
                        canonical_form=target.canonical_form,
                        target_type=target.target_type,
                        context=target.context,
                        meaning=target.meaning,
                        estimated_level=target.estimated_level,
                        rank=target.rank,
                        machine_suggested=target.machine_suggested,
                        created_at=moment,
                        updated_at=moment,
                    )
                )
            self._record_event(
                connection,
                article_id=article_id,
                actor=actor,
                action="created",
                reason="",
                changes={"targets": len(targets), "estimated_level": estimated_level},
                now=moment,
            )
            row = connection.execute(
                select(ReadingArticle).where(ReadingArticle.id == article_id)
            ).first()
        return _article(row)

    def get_article(self, article_id: str) -> dict[str, Any] | None:
        """Everything review needs: the body, the targets, the snapshot, the
        analysis. Not what a list returns - this is the Preview read."""
        with self.engine.connect() as connection:
            row = connection.execute(
                select(ReadingArticle).where(ReadingArticle.id == _uuid(article_id))
            ).first()
            if row is None:
                return None
            targets = connection.execute(
                select(ReadingArticleTarget)
                .where(ReadingArticleTarget.article_id == row.id)
                .order_by(ReadingArticleTarget.rank, ReadingArticleTarget.id)
            ).all()
            source_item = connection.execute(
                select(ReadingSourceItem).where(ReadingSourceItem.id == row.source_item_id)
            ).first()
        article = _article(row)
        article["targets"] = [_target(target) for target in targets]
        article["source"] = _item(source_item) if source_item else None
        return article

    def article_for_source_item(self, source_item_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                select(ReadingArticle).where(
                    ReadingArticle.source_item_id == _uuid(source_item_id)
                )
            ).first()
        return _article(row) if row else None

    def update_article(
        self,
        article_id: str,
        *,
        actor: str,
        title: str | None = None,
        body: str | None = None,
        excerpt: str | None = None,
        topic: str | None = None,
        subtopic: str | None = None,
        reviewed_level: str | None = "",
        reason: str = "",
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        """An admin's correction. `estimated_level` is never among the changes.

        `reviewed_level` uses `""` as "not supplied" and `None` as "clear the
        override", because those are genuinely different requests and a single
        sentinel would make one of them unexpressable.
        """
        current = self.get_article(article_id)
        if current is None:
            return None
        moment = _now(now)
        values: dict[str, Any] = {"updated_at": moment}
        changes: dict[str, Any] = {}
        for field, value in (
            ("title", title),
            ("body", body),
            ("excerpt", excerpt),
            ("topic", topic),
            ("subtopic", subtopic),
        ):
            if value is not None and value != current[field]:
                values[field] = value
                changes[field] = {"from": current[field], "to": value}
        level_changed = reviewed_level != ""
        if level_changed:
            values["reviewed_level"] = reviewed_level or None
            values["effective_level"] = _effective(
                current["estimated_level"], reviewed_level or None
            )
            changes["reviewed_level"] = {"from": current["reviewed_level"], "to": reviewed_level}
        if len(values) == 1:
            return current
        # Any change to what a learner reads invalidates a cached copy.
        if {"title", "body", "excerpt"} & set(changes):
            values["content_revision"] = current["content_revision"] + 1
        with self.engine.begin() as connection:
            connection.execute(
                update(ReadingArticle)
                .where(ReadingArticle.id == _uuid(article_id))
                .values(**values)
            )
            self._record_event(
                connection,
                article_id=_uuid(article_id),
                actor=actor,
                action="level_override" if level_changed and len(changes) == 1 else "edited",
                reason=reason,
                changes=changes,
                now=moment,
            )
        return self.get_article(article_id)

    def set_status(
        self,
        article_id: str,
        status: str,
        *,
        actor: str,
        reason: str = "",
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        """Move an article through its lifecycle, recording who and why.

        Publication is the only transition that makes anything learner-visible,
        and it is always an admin's act: nothing in the pipeline calls this.
        """
        current = self.get_article(article_id)
        if current is None:
            return None
        moment = _now(now)
        values: dict[str, Any] = {"status": status, "updated_at": moment}
        if status == LEARNER_VISIBLE_STATUS:
            values |= {"published_at": moment, "unpublished_at": None}
            values["content_revision"] = current["content_revision"] + 1
        elif current["status"] == LEARNER_VISIBLE_STATUS:
            values["unpublished_at"] = moment
        if status == "rejected":
            values["rejection_reason"] = reason
        with self.engine.begin() as connection:
            connection.execute(
                update(ReadingArticle)
                .where(ReadingArticle.id == _uuid(article_id))
                .values(**values)
            )
            self._record_event(
                connection,
                article_id=_uuid(article_id),
                actor=actor,
                action=status,
                reason=reason,
                changes={"status": {"from": current["status"], "to": status}},
                now=moment,
            )
        return self.get_article(article_id)

    def list_queue(
        self,
        *,
        statuses: Sequence[str] = QUEUE_STATUSES,
        cursor: str | None = None,
        limit: int = DEFAULT_ARTICLE_PAGE,
    ) -> dict[str, Any]:
        bounded = max(1, min(int(limit), MAX_ARTICLE_PAGE))
        query = select(ReadingArticle).where(ReadingArticle.status.in_(tuple(statuses)))
        if cursor:
            after_at, after_id = _decode_cursor(cursor)
            query = query.where(
                (ReadingArticle.created_at < after_at)
                | ((ReadingArticle.created_at == after_at) & (ReadingArticle.id < after_id))
            )
        query = query.order_by(
            ReadingArticle.created_at.desc(), ReadingArticle.id.desc()
        ).limit(bounded + 1)
        with self.engine.connect() as connection:
            rows = connection.execute(query).all()
        page = rows[:bounded]
        next_cursor = (
            _encode_cursor(_aware(page[-1].created_at), str(page[-1].id))
            if len(rows) > bounded and page
            else None
        )
        return {"items": [_queue_row(row) for row in page], "next_cursor": next_cursor}

    def list_published(
        self,
        *,
        language: str,
        level: str | None = None,
        topic: str | None = None,
        cursor: str | None = None,
        limit: int = DEFAULT_ARTICLE_PAGE,
    ) -> dict[str, Any]:
        """The learner list. Filtered and ordered in the database, bounded, and
        without a body - the one query whose cost must not grow with the
        corpus."""
        bounded = max(1, min(int(limit), MAX_ARTICLE_PAGE))
        query = select(ReadingArticle).where(
            ReadingArticle.status == LEARNER_VISIBLE_STATUS,
            ReadingArticle.language == language,
        )
        if level:
            query = query.where(ReadingArticle.effective_level == level)
        if topic:
            query = query.where(ReadingArticle.topic == topic)
        if cursor:
            after_at, after_id = _decode_cursor(cursor)
            query = query.where(
                (ReadingArticle.published_at < after_at)
                | ((ReadingArticle.published_at == after_at) & (ReadingArticle.id < after_id))
            )
        query = query.order_by(
            ReadingArticle.published_at.desc(), ReadingArticle.id.desc()
        ).limit(bounded + 1)
        with self.engine.connect() as connection:
            rows = connection.execute(query).all()
        page = rows[:bounded]
        next_cursor = (
            _encode_cursor(_aware(page[-1].published_at), str(page[-1].id))
            if len(rows) > bounded and page
            else None
        )
        return {"items": [_learner_row(row) for row in page], "next_cursor": next_cursor}

    def get_published_article(self, article_id: str) -> dict[str, Any] | None:
        """What a learner opens: the text, the targets an admin approved, and
        the attribution the rights require. No analysis, no review history, no
        rights payload, no job state."""
        with self.engine.connect() as connection:
            row = connection.execute(
                select(ReadingArticle).where(
                    ReadingArticle.id == _uuid(article_id),
                    ReadingArticle.status == LEARNER_VISIBLE_STATUS,
                )
            ).first()
            if row is None:
                return None
            targets = connection.execute(
                select(ReadingArticleTarget)
                .where(
                    ReadingArticleTarget.article_id == row.id,
                    ReadingArticleTarget.admin_approved.is_(True),
                )
                .order_by(ReadingArticleTarget.rank, ReadingArticleTarget.id)
            ).all()
            source_item = connection.execute(
                select(
                    ReadingSourceItem.original_author,
                    ReadingSourceItem.canonical_url,
                    ReadingSourceItem.original_published_at,
                    ReadingSourceItem.source_id,
                ).where(ReadingSourceItem.id == row.source_item_id)
            ).first()
        return {
            "id": str(row.id),
            "title": row.title,
            "body": row.body,
            "language": row.language,
            "level": row.effective_level,
            "topic": row.topic,
            "reading_time_seconds": row.reading_time_seconds,
            "word_count": row.word_count,
            "content_revision": row.content_revision,
            "published_at": _iso(row.published_at),
            "targets": [
                {
                    "text": target.text,
                    "canonical_form": target.canonical_form,
                    "target_type": target.target_type,
                    "context": target.context,
                    "meaning": target.meaning,
                }
                for target in targets
            ],
            "attribution": {
                "author": source_item.original_author if source_item else "",
                "source_url": source_item.canonical_url if source_item else "",
                "published_at": _iso(source_item.original_published_at) if source_item else None,
            },
        }

    def published_count(self, *, language: str | None = None) -> int:
        query = select(func.count()).select_from(ReadingArticle).where(
            ReadingArticle.status == LEARNER_VISIBLE_STATUS
        )
        if language:
            query = query.where(ReadingArticle.language == language)
        with self.engine.connect() as connection:
            return int(connection.execute(query).scalar_one())

    def counts_by_status(self) -> dict[str, int]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(ReadingArticle.status, func.count()).group_by(ReadingArticle.status)
            ).all()
        return {status: int(total) for status, total in rows}

    # ---- targets ---------------------------------------------------------
    def decide_target(
        self, target_id: str, *, approved: bool, actor: str, now: datetime | None = None
    ) -> dict[str, Any] | None:
        """The admin's decision, kept separate from the machine's suggestion.

        `machine_suggested` is never cleared: "the machine proposed this and a
        human approved it" and "a human added this" are different facts, and a
        future processor re-run has to be able to tell them apart.
        """
        moment = _now(now)
        with self.engine.begin() as connection:
            row = connection.execute(
                select(ReadingArticleTarget).where(ReadingArticleTarget.id == _uuid(target_id))
            ).first()
            if row is None:
                return None
            connection.execute(
                update(ReadingArticleTarget)
                .where(ReadingArticleTarget.id == _uuid(target_id))
                .values(
                    admin_approved=bool(approved),
                    admin_rejected=not approved,
                    updated_at=moment,
                )
            )
            self._record_event(
                connection,
                article_id=row.article_id,
                actor=actor,
                action="target_approved" if approved else "target_rejected",
                reason="",
                changes={"target": row.text},
                now=moment,
            )
            updated = connection.execute(
                select(ReadingArticleTarget).where(ReadingArticleTarget.id == _uuid(target_id))
            ).first()
        return _target(updated)

    def add_target(
        self,
        article_id: str,
        *,
        target: TargetInput,
        actor: str,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        moment = _now(now)
        target_id = uuid.uuid4()
        with self.engine.begin() as connection:
            connection.execute(
                insert(ReadingArticleTarget).values(
                    id=target_id,
                    article_id=_uuid(article_id),
                    text=target.text,
                    canonical_form=target.canonical_form,
                    target_type=target.target_type,
                    context=target.context,
                    meaning=target.meaning,
                    estimated_level=target.estimated_level,
                    rank=target.rank,
                    machine_suggested=False,
                    admin_approved=True,
                    created_at=moment,
                    updated_at=moment,
                )
            )
            self._record_event(
                connection,
                article_id=_uuid(article_id),
                actor=actor,
                action="target_added",
                reason="",
                changes={"target": target.text},
                now=moment,
            )
            row = connection.execute(
                select(ReadingArticleTarget).where(ReadingArticleTarget.id == target_id)
            ).first()
        return _target(row)

    def remove_target(self, target_id: str, *, actor: str, now: datetime | None = None) -> bool:
        with self.engine.begin() as connection:
            row = connection.execute(
                select(ReadingArticleTarget).where(ReadingArticleTarget.id == _uuid(target_id))
            ).first()
            if row is None:
                return False
            connection.execute(
                delete(ReadingArticleTarget).where(ReadingArticleTarget.id == _uuid(target_id))
            )
            self._record_event(
                connection,
                article_id=row.article_id,
                actor=actor,
                action="target_removed",
                reason="",
                changes={"target": row.text},
                now=_now(now),
            )
        return True

    # ---- the review trail ------------------------------------------------
    def list_review_events(self, article_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(ReadingReviewEvent)
                .where(ReadingReviewEvent.article_id == _uuid(article_id))
                .order_by(ReadingReviewEvent.created_at, ReadingReviewEvent.id)
                .limit(max(1, min(int(limit), 200)))
            ).all()
        return [
            {
                "id": str(row.id),
                "actor": row.actor,
                "action": row.action,
                "reason": row.reason,
                "changes": dict(row.changes_json or {}),
                "created_at": _iso(row.created_at),
            }
            for row in rows
        ]

    def _record_event(
        self,
        connection: Any,
        *,
        article_id: uuid.UUID,
        actor: str,
        action: str,
        reason: str,
        changes: dict[str, Any],
        now: datetime,
    ) -> None:
        """Written inside the caller's transaction, so a decision and its
        record land together or not at all. `audit_logs` receives the same
        mutation separately and remains the retention authority."""
        connection.execute(
            insert(ReadingReviewEvent).values(
                id=uuid.uuid4(),
                article_id=article_id,
                actor=actor,
                action=action,
                reason=reason,
                changes_json=changes,
                created_at=now,
            )
        )
