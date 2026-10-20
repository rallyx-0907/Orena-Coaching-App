"""Sources, snapshots, articles, targets and the review trail.

Schema: `migrations/proposed/20260924_0015_reading_content_engine.py` -
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
import logging
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.engine import Engine

from writing_coach.persistence.reading_evidence_repository import stale_sets_for_body
from writing_coach.reading_processing import EN_LEVEL_BANDS, ZH_LEVEL_BANDS, analyze_article, quality_issues
from writing_coach.reading_page_quality import QUALITY_VERSION, QualityRefused, hard_issues
from writing_coach.languages.chinese.script_detection import SCRIPTS, UNKNOWN, detect_script
from writing_coach.reading_admission import auto_publish_enabled, with_auto_publish
from writing_coach.thumbnails import ThumbnailRequired
from writing_coach.reading_images import (
    SHARED_URL_THRESHOLD,
    assess_candidates,
    candidate_url,
    image_policy_allowed,
    learner_image,
    shared_url_counts,
    with_image_policy,
)
from writing_coach.reading_provenance import (
    PUBLIC_NAME_KEY, build_provenance, provenance_blockers, public_name_of, resolve_publisher,
)
from writing_coach.reading_rights_gate import RightsRefused, rights_blockers
from writing_coach.reading_rights_refinement import refine_item_rights
from writing_coach.persistence.models import (
    ReadingArticle,
    ReadingArticleTarget,
    ReadingReviewEvent,
    ReadingSource,
    ReadingSourceItem,
)

_logger = logging.getLogger(__name__)

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

BUILT_IN_SLUGS = frozenset(slug for _, slug, _ in BUILT_IN_SOURCES.values())

LEARNER_VISIBLE_STATUS = "published"
# Exactly what the learner routes return, and therefore exactly what must move
# `content_revision` when it changes: the list projection's fields plus the
# body and the approved targets the detail adds. `subtopic`, the analysis and
# the review trail are admin-only, so changing one of those does not make every
# cached copy refetch.
LEARNER_VISIBLE_FIELDS = ("title", "body", "excerpt", "topic", "reviewed_level", "content_kind")
# What the learner is reading - the learner-facing content type (D-083). Not a
# source's feed mechanism (`reading_sources.source_type`) and not an editorial
# category of the publisher, which stays deferred.
CONTENT_KINDS = ("article", "news")
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


def _lookup_uuid(value: Any) -> uuid.UUID | None:
    """The id of a row that could exist, or None for a string that never can.

    A route path is a string, so `/articles/queue` arrives here as an id. That
    names no row - which is absence, the same answer as a well-formed id
    nobody used, and not a 500.
    """
    try:
        return _uuid(value)
    except (ValueError, AttributeError, TypeError):
        return None


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
        "public_name": public_name_of(row.polling_policy),
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
        # D-194: whether learner thumbnails from this source are permitted. Off until the owner turns it on.
        "image_policy": {"allowed": image_policy_allowed(row.polling_policy)},
        # #352: whether cleared items publish without a person. Off until an administrator turns it on.
        "auto_publish": {"enabled": auto_publish_enabled(row.polling_policy)},
        "last_checked_at": _iso(row.last_checked_at),
        "last_success_at": _iso(row.last_success_at),
        "last_error": row.last_error,
        "polling_cursor": row.polling_cursor,
        "created_at": _iso(row.created_at),
    }


def _policy_with_public_name(policy: Any, public_name: str) -> dict[str, Any]:
    """The source's `polling_policy` JSON with the learner-facing name set (or cleared)."""
    merged = {key: value for key, value in (policy.items() if isinstance(policy, dict) else []) if key != PUBLIC_NAME_KEY}
    name = public_name_of({PUBLIC_NAME_KEY: public_name})
    if name:
        merged[PUBLIC_NAME_KEY] = name
    return merged


def _update_source_policy(
    connection: Any, source_id: Any, mutate: Callable[[dict[str, Any]], dict[str, Any]], *, now: datetime
) -> bool | None:
    """The one writer of a source's `polling_policy` JSON (public name, image policy).

    Reads the row under a lock, applies `mutate` to a copy of the stored dict and writes back only on a
    change, so two administrators saving different keys cannot lose each other's key. Returns None when
    the source does not exist, else whether anything changed. A change on a source moves every published
    article's `content_revision` in the same transaction: the public name and the image policy are in the learner
    payload (auto-publish is not, and only costs a refetch).
    """
    row = connection.execute(
        select(ReadingSource.polling_policy).where(ReadingSource.id == source_id).with_for_update()
    ).first()
    if row is None:
        return None
    current = dict(row.polling_policy) if isinstance(row.polling_policy, dict) else {}
    updated = mutate(dict(current))
    if updated == current:
        return False
    connection.execute(
        update(ReadingSource).where(ReadingSource.id == source_id).values(polling_policy=updated, updated_at=now)
    )
    connection.execute(
        update(ReadingArticle)
        .where(
            ReadingArticle.status == LEARNER_VISIBLE_STATUS,
            ReadingArticle.source_item_id.in_(select(ReadingSourceItem.id).where(ReadingSourceItem.source_id == source_id)),
        )
        .values(content_revision=ReadingArticle.content_revision + 1, updated_at=now)
    )
    return True


def _learner_credit(row: Any, effective: dict[str, Any]) -> dict[str, Any]:
    """The credit of one article from a row carrying the source (`slug`,
    `polling_policy`), the item (`metadata`, `canonical_url`, `original_author`)
    and the effective rights. The internal source name is deliberately not read."""
    metadata = row.item_metadata if isinstance(row.item_metadata, dict) else {}
    publisher, via = resolve_publisher(
        extraction=metadata.get("extraction"),
        public_name=public_name_of(row.source_policy),
        entered_name=metadata.get("source_name"),
        built_in=row.source_slug in BUILT_IN_SLUGS,
        url=row.canonical_url,
    )
    return build_provenance(
        publisher=publisher, via=via, url=row.canonical_url,
        author=row.original_author, rights=effective,
    )


PERMISSIONS = ("automation_allowed", "can_republish", "can_adapt")


def rights_state(rights: Any) -> dict[str, str]:
    """A rights question has three answers, and `False` is only one of them.

    The snapshot stores exactly what the submitter asserted, so a key that is
    absent means nobody answered - not that the answer was no. Flattening the
    two together is how a manual paste with no rights information ends up
    looking identical to content a publisher explicitly refused, and an admin
    cannot tell which decision they are about to make.

    Permissions read `allowed` / `denied` / `unknown`. Attribution is an
    obligation rather than a permission, so it answers in its own words -
    calling a required attribution "allowed" would be a sentence nobody means.
    """
    answered = rights if isinstance(rights, dict) else {}
    state = {
        key: ("allowed" if answered[key] else "denied") if key in answered else "unknown"
        for key in PERMISSIONS
    }
    state["attribution_required"] = (
        ("required" if answered["attribution_required"] else "not_required")
        if "attribution_required" in answered
        else "unknown"
    )
    return state


RIGHTS_EVENT = "rights_set"
# D-194: a thumbnail decision is a recorded review event, folded oldest first like a rights answer.
IMAGE_SET_EVENT = "image_set"
IMAGE_REJECTED_EVENT = "image_rejected"
IMAGE_EVENTS = (IMAGE_SET_EVENT, IMAGE_REJECTED_EVENT)
RIGHTS_QUESTIONS = ("can_republish", "can_adapt", "attribution_required")


def automation_override(decisions: Sequence[Mapping[str, Any]]) -> bool | None:
    """The article-level automation answer, when a reviewer recorded one.

    A source's `automation_allowed` is a default (D-106 READING-2). The last
    recorded answer wins, and `None` clears the override back to the default.
    """
    override: bool | None = None
    for answers in decisions:
        if "automation_allowed" in answers:
            value = answers["automation_allowed"]
            override = None if value is None else bool(value)
    return override


def effective_automation(decisions: Sequence[Mapping[str, Any]], source_default: Any) -> dict[str, Any]:
    """The one computation of an article's automation permission: the article's
    override when present, else the source default. Every surface that shows or
    uses it reads this."""
    override = automation_override(decisions)
    default = bool(source_default)
    return {
        "allowed": default if override is None else override,
        "override": override,
        "source_default": default,
        "origin": "source" if override is None else "article",
    }


def overlay_rights(
    snapshot: Any, decisions: Sequence[Mapping[str, Any]], source_default: Any = None
) -> dict[str, Any]:
    """The rights that govern publication: the immutable snapshot, then every
    answer an administrator recorded afterwards, oldest first.

    The snapshot is never rewritten (the trigger refuses it), so a correction
    is a review event and the effective answer is the fold of the two. A
    decision that leaves a question out leaves the earlier answer standing.
    """
    effective = dict(snapshot) if isinstance(snapshot, dict) else {}
    # Automation is not the snapshot's to answer: it is the source's default
    # unless the article carries a reviewed override.
    effective.pop("automation_allowed", None)
    if source_default is not None:
        effective["automation_allowed"] = effective_automation(decisions, source_default)["allowed"]
    for answers in decisions:
        for key in (*RIGHTS_QUESTIONS, "license_note"):
            if key in answers:
                if answers[key] is None:
                    effective.pop(key, None)
                else:
                    effective[key] = answers[key]
    return effective


OWN_RIGHTS_KEYS = (*RIGHTS_QUESTIONS, "license_note")


def publication_rights(
    snapshot: Any, decisions: Sequence[Mapping[str, Any]], source_policy: Mapping[str, Any] | None, *,
    built_in: bool,
) -> dict[str, Any]:
    """The rights the publish confirmation reads, and where they came from (`basis`).

    The article's own snapshot is authoritative for that article (the per-item
    snapshot model, D-111): when it, or an administrator's recorded answer,
    carries any rights answer, the source's policy is not consulted at all - a
    text imported through the "Direct URL" input path keeps the public-domain
    answer it was imported with, and a snapshot that says no, or leaves the
    republish question unanswered, still asks for the confirmation.

    Only an article with no rights of its own falls back to its registered
    source's policy (`basis: "source"`). A built-in input path (manual paste,
    direct URL, file upload) has no reviewed policy to fall back to - its
    columns are defaults nobody answered - so there the answers stay unknown
    (`basis: "none"`).
    """
    own = dict(snapshot) if isinstance(snapshot, dict) else {}
    answered = any(key in own for key in OWN_RIGHTS_KEYS) or any(
        any(key in answers for key in OWN_RIGHTS_KEYS) for answers in decisions
    )
    if answered:
        return {"basis": "snapshot", "state": rights_state(overlay_rights(own, decisions))}
    if built_in or not source_policy:
        return {"basis": "none", "state": rights_state({})}
    fallback = {key: source_policy[key] for key in RIGHTS_QUESTIONS if key in source_policy}
    return {"basis": "source", "state": rights_state(fallback)}


def fold_image_events(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The thumbnail state of an article from its image events, oldest first.

    `approved` is the last approval that was not cleared or rejected since; `rejected` is every candidate
    address a reviewer turned down. An approval of an address that was rejected earlier stands: the later
    decision wins.
    """
    approved: dict[str, Any] | None = None
    rejected: set[str] = set()
    for event in events:
        answers = event["answers"]
        if event["action"] == IMAGE_SET_EVENT:
            image = answers.get("image")
            approved = dict(image) if isinstance(image, dict) else None
            if approved:
                rejected.discard(str(approved.get("candidate_url") or ""))
        elif event["action"] == IMAGE_REJECTED_EVENT:
            url = str(answers.get("rejected_url") or "")
            if url:
                rejected.add(url)
                if approved and approved.get("candidate_url") == url:
                    approved = None
    return {"approved": approved, "rejected": frozenset(rejected)}


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
        "rights_state": rights_state(row.rights_snapshot_json),
        "revision": row.revision,
        "supersedes_id": str(row.supersedes_id) if row.supersedes_id else None,
        "superseded_at": _iso(row.superseded_at),
        "fetched_at": _iso(row.fetched_at),
    }


RECOUNT_BATCH_SIZE = 100
SIZE_ISSUE_CODES = frozenset({"too_short", "too_long"})


def body_derived_values(body: str, language: str, analysis: Mapping[str, Any] | None) -> dict[str, Any]:
    """What admission measures from a body, recomputed with the same function (`analyze_article`).

    Word count (characters for Chinese), reading time and the counted analysis facts. The level,
    the quality codes and the targets are not touched: they are decisions or extraction facts,
    not counts, and targets are text phrases, not offsets into the body.
    """
    measured = analyze_article(body, language)
    merged = dict(analysis or {})
    merged.update(
        sentence_count=measured.sentence_count,
        average_sentence_length=measured.average_sentence_length,
        distinct_word_ratio=measured.distinct_word_ratio,
        long_word_ratio=measured.long_word_ratio,
    )
    return {
        "word_count": measured.word_count,
        "reading_time_seconds": measured.reading_time_seconds,
        "analysis_json": merged,
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
        "content_kind": row.content_kind,
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
        "source_name": getattr(row, "source_name", "") or "",
        "target_count": int(getattr(row, "target_count", 0) or 0),
    }


def _level_source(row: Any) -> str:
    """Whether the level a learner reads was reviewed by a person or is only the machine's estimate (PRE-204).
    A plain read of the two columns; `effective_level` is `reviewed_level` when set, else `estimated_level`."""
    return "editorial-review" if getattr(row, "reviewed_level", None) else "deterministic-estimate"


def _learner_row(row: Any) -> dict[str, Any]:
    """The learner list projection. Every field here is one a card draws."""
    return {
        "id": str(row.id),
        "title": row.title,
        "language": row.language,
        "level": row.effective_level,
        "level_source": _level_source(row),
        "topic": row.topic,
        "reading_time_seconds": row.reading_time_seconds,
        "word_count": row.word_count,
        "excerpt": row.excerpt,
        "published_at": _iso(row.published_at),
        "content_revision": row.content_revision,
    }


def _script_field(language: str, stored: Any) -> dict[str, Any]:
    """`script` for a Chinese article only (zh-Hans / zh-Hant / mixed / unknown, D-197); other languages omit it.
    An article ingested before the field existed has none stored: it reads as `unknown`, which is never labelled."""
    if language != "zh":
        return {}
    return {"script": stored if stored in SCRIPTS else UNKNOWN}


class ReadingContentRepository:
    # D-240: every learner-visible article has a thumbnail. The application turns this on at wiring; a bare
    # repository (a script, a unit test) stays permissive so it can set up content without art.
    require_thumbnail = False
    # Set at wiring: makes and stores a typographic cover for {article_id, title, language, topic} and returns the
    # stored-image dict an `image_set` event carries, or None. Every article the engine creates gets one (D-240).
    cover_factory: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def _make_cover(self, article_id: str, *, title: str, language: str, topic: str) -> dict[str, Any] | None:
        """The typographic cover `cover_factory` makes for a new article, or None (no factory, or it failed: the
        article is still created, and waits for review without a thumbnail rather than being lost)."""
        if self.cover_factory is None:
            return None
        try:
            return self.cover_factory({"article_id": article_id, "title": title, "language": language, "topic": topic})
        except Exception:  # noqa: BLE001 - a cover that cannot be stored never loses the article
            _logger.exception("reading: typographic cover could not be made for a new article")
            return None

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
        public_name: str = "",
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
                    polling_policy=_policy_with_public_name({}, public_name),
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
        if _lookup_uuid(source_id) is None:
            return None
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

    def set_source_public_name(
        self, source_id: str, public_name: str, *, now: datetime | None = None
    ) -> dict[str, Any] | None:
        """Set the name learners see as the publisher of this source's texts.

        Published texts of the source change what a learner reads (the credit is in
        the list and the detail), so each one's `content_revision` moves in the same
        transaction and cached copies refetch (D-190 follow-up P2-2). Nothing moves
        when the name is unchanged.
        """
        if _lookup_uuid(source_id) is None:
            return None
        moment = _now(now)
        with self.engine.begin() as connection:
            changed = _update_source_policy(
                connection, _uuid(source_id), lambda policy: _policy_with_public_name(policy, public_name), now=moment
            )
            if changed is None:
                return None
        return self.get_source(source_id)

    def set_source_rights(
        self, source_id: str, rights: dict[str, Any], *, actor: str, now: datetime | None = None
    ) -> dict[str, Any] | None:
        """Correct the rights recorded on an existing source (the columns `create_source` writes).

        Only the source row changes. Texts already ingested keep the rights snapshot taken on their
        source item; the new answers reach texts ingested afterwards. A source whose rights no longer
        allow automation stops polling in the same transaction (the invariant `set_polling` enforces
        and the CHECK constraint backs). No article status moves. Returns None for an unknown source.
        """
        if _lookup_uuid(source_id) is None:
            return None
        values: dict[str, Any] = {
            "automation_allowed": bool(rights.get("automation_allowed")),
            "can_republish": bool(rights.get("can_republish")),
            "can_adapt": bool(rights.get("can_adapt")),
            "attribution_required": bool(rights.get("attribution_required", True)),
            "license_note": str(rights.get("license_note", "")),
            "updated_at": _now(now),
        }
        if not values["automation_allowed"]:
            values["polling_enabled"] = False
        with self.engine.begin() as connection:
            updated = connection.execute(
                update(ReadingSource).where(ReadingSource.id == _uuid(source_id)).values(**values)
            ).rowcount
        return self.get_source(source_id) if updated else None

    def set_source_state(
        self, source_id: str, state: str, *, actor: str, now: datetime | None = None
    ) -> dict[str, Any] | None:
        if _lookup_uuid(source_id) is None:
            return None
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

    def record_poll(
        self,
        source_id: str,
        *,
        error: str,
        state: dict[str, Any],
        now: datetime | None = None,
    ) -> None:
        """Store one poll's outcome on the existing source columns (no schema change).

        `last_checked_at` always moves; `last_success_at` only on success. The
        poller's backoff bookkeeping (`failures`, `next_retry_at`) is a small
        JSON document in `polling_cursor`, the column reserved for "where the
        poller got to".
        """
        if _lookup_uuid(source_id) is None:
            return
        moment = _now(now)
        values: dict[str, Any] = {
            "last_checked_at": moment,
            "last_error": (error or "")[:2000],
            "polling_cursor": json.dumps(state, separators=(",", ":"))[:600],
        }
        if not error:
            values["last_success_at"] = moment
        with self.engine.begin() as connection:
            connection.execute(
                update(ReadingSource).where(ReadingSource.id == _uuid(source_id)).values(**values)
            )

    def known_source_urls(self, source_id: str, urls: Sequence[str]) -> set[str]:
        """Which of these canonical URLs this source already holds a snapshot of."""
        wanted = [url for url in urls if url]
        if not wanted or _lookup_uuid(source_id) is None:
            return set()
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(ReadingSourceItem.canonical_url).where(
                    ReadingSourceItem.source_id == _uuid(source_id),
                    ReadingSourceItem.canonical_url.in_(wanted),
                )
            ).all()
        return {row[0] for row in rows}

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
                #
                # Only for the *same* native item, though. A feed that
                # regenerates its guids can offer bytes we already hold under a
                # new id; that is a plain content duplicate, and treating it as
                # a revert would flip the currency of an item the incoming
                # fetch never named.
                if (
                    existing.superseded_at is not None
                    and existing.source_native_id == source_native_id
                ):
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
        if _lookup_uuid(item_id) is None:
            return None
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

        The source is named, not just identified. "Also under 2 other sources"
        is not something anyone can decide with; "also under Manual paste" is,
        because the rights that make a second copy legitimate are the source's.
        """
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(
                    ReadingSourceItem.id,
                    ReadingSourceItem.source_id,
                    ReadingSourceItem.original_title,
                    ReadingSource.name.label("source_name"),
                    ReadingSource.slug.label("source_slug"),
                )
                .join(ReadingSource, ReadingSource.id == ReadingSourceItem.source_id)
                .where(
                    ReadingSourceItem.content_hash == content_hash,
                    ReadingSourceItem.source_id != _uuid(exclude_source_id),
                )
            ).all()
        return [
            {
                "id": str(row.id),
                "source_id": str(row.source_id),
                "source_name": row.source_name,
                "source_slug": row.source_slug,
                "title": row.original_title,
            }
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
        automatic_admission: bool = False,
        actor: str = "orena:reading-engine",
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """One candidate article and its targets, in one transaction.

        Default candidates await review. The engine may request deterministic
        admission under an active source's reviewed rights and automation policy.
        The decision, targets and publication are committed together.
        """
        moment = _now(now)
        article_id = uuid.uuid4()
        with self.engine.begin() as connection:
            admitted = False
            cover = None
            prepared_analysis = dict(analysis or {})
            if automatic_admission:
                from writing_coach.reading_admission import automatic_admission as check_admission

                snapshot_row = connection.execute(select(ReadingSourceItem).where(
                    ReadingSourceItem.id == _uuid(source_item_id)).with_for_update()).first()
                if snapshot_row is None:
                    raise ValueError("Source snapshot not found")
                existing = connection.execute(select(ReadingArticle).where(
                    ReadingArticle.source_item_id == snapshot_row.id)).first()
                if existing is not None:
                    return {**_article(existing), "duplicate": True}
                source_row = connection.execute(select(ReadingSource).where(
                    ReadingSource.id == snapshot_row.source_id).with_for_update()).first()
                decision = check_admission(source=_source(source_row), snapshot=_item(snapshot_row),
                    language=language, body=body, analysis=prepared_analysis, targets=targets,
                    min_targets=MIN_TARGETS, max_targets=MAX_TARGETS)
                prepared_analysis["admission"] = decision
                admitted = decision["decision"] == "published" and status == "needs_review"
            if self.require_thumbnail:
                # D-240: every admitted article gets its typographic cover here, whether the engine publishes it or
                # it waits for review - a held article must not reach the publish gate without one. An automatic
                # admission publishes with nobody looking; without a cover it waits for review instead.
                cover = self._make_cover(str(article_id), title=title, language=language, topic=topic)
                if cover is None:
                    admitted = False
            if admitted:
                status = LEARNER_VISIBLE_STATUS
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
                    analysis_json=prepared_analysis,
                    status=status,
                    published_at=moment if admitted else None,
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
                        admin_approved=admitted,
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
                changes={"targets": len(targets), "estimated_level": estimated_level,
                         **({"admission": decision} if automatic_admission else {})},
                now=moment,
            )
            if cover is not None:
                self._record_event(connection, article_id=article_id, actor=actor, action=IMAGE_SET_EVENT, reason="",
                    changes={"from": None, "to": {"image": dict(cover)}}, now=moment)
            if admitted:
                self._record_event(connection, article_id=article_id, actor=actor,
                    action="auto_published", reason="",
                    changes={"admission": decision, "automatically_approved_targets": len(targets)}, now=moment)
            row = connection.execute(
                select(ReadingArticle).where(ReadingArticle.id == article_id)
            ).first()
        return _article(row)

    def get_article(self, article_id: str) -> dict[str, Any] | None:
        """Everything review needs: the body, the targets, the snapshot, the
        analysis. Not what a list returns - this is the Preview read."""
        if _lookup_uuid(article_id) is None:
            return None
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
            source_head = (
                connection.execute(
                    select(
                        ReadingSource.automation_allowed, ReadingSource.name,
                        ReadingSource.slug, ReadingSource.polling_policy,
                        ReadingSource.can_republish, ReadingSource.can_adapt, ReadingSource.attribution_required,
                    ).where(
                        ReadingSource.id == source_item.source_id
                    )
                ).first()
                if source_item
                else None
            )
            source_default = source_head.automation_allowed if source_head else None
            decisions = self._rights_decisions(connection, [row.id]).get(row.id, [])
        article = _article(row)
        article["targets"] = [_target(target) for target in targets]
        article["source"] = _item(source_item) if source_item else None
        article["rights_review"] = None
        article["automation"] = None
        article["provenance"] = None
        if article["source"] is not None:
            # `source.rights` stays the snapshot as ingested; the state the gate
            # and the review page read is the snapshot with the recorded answers.
            answered = [entry["answers"] for entry in decisions]
            effective = overlay_rights(article["source"]["rights"], answered, source_default)
            article["automation"] = effective_automation(answered, source_default)
            article["source"]["rights_state"] = rights_state(effective)
            article["source"]["rights_effective"] = effective
            # What the publish confirmation reads: the article's own snapshot when it has one, else its source.
            article["source"]["publication_rights"] = publication_rights(
                article["source"]["rights"], answered,
                {
                    "can_republish": bool(source_head.can_republish),
                    "can_adapt": bool(source_head.can_adapt),
                    "attribution_required": bool(source_head.attribution_required),
                } if source_head else None,
                built_in=bool(source_head) and source_head.slug in BUILT_IN_SLUGS,
            )
            article["source"]["source_name"] = source_head.name if source_head else ""
            article["source"]["public_name"] = public_name_of(source_head.polling_policy) if source_head else ""
            article["provenance"] = _learner_credit(SimpleNamespace(
                item_metadata=article["source"].get("metadata"),
                source_policy=source_head.polling_policy if source_head else {},
                source_slug=source_head.slug if source_head else "",
                canonical_url=article["source"]["canonical_url"],
                original_author=article["source"]["author"],
            ), effective)
            if decisions:
                article["rights_review"] = {
                    "actor": decisions[-1]["actor"],
                    "at": decisions[-1]["at"],
                    "count": len(decisions),
                }
        return article

    def _decision_events(
        self, connection: Any, article_ids: Sequence[Any]
    ) -> dict[Any, list[dict[str, Any]]]:
        """Recorded rights answers and thumbnail decisions per article, oldest first, in one read."""
        if not article_ids:
            return {}
        rows = connection.execute(
            select(ReadingReviewEvent)
            .where(
                ReadingReviewEvent.article_id.in_(list(article_ids)),
                ReadingReviewEvent.action.in_((RIGHTS_EVENT, *IMAGE_EVENTS)),
            )
            .order_by(ReadingReviewEvent.created_at, ReadingReviewEvent.id)
        ).all()
        found: dict[Any, list[dict[str, Any]]] = {}
        for event in rows:
            answers = (event.changes_json or {}).get("to") or {}
            found.setdefault(event.article_id, []).append(
                {"action": event.action, "answers": dict(answers), "actor": event.actor, "at": _iso(event.created_at)}
            )
        return found

    def _review_marks(self, connection: Any, article_ids: Sequence[Any]) -> dict[Any, dict[str, str]]:
        """When an administrator last reviewed each article's level and its topic, read from its review trail in one
        query: `{"level_at": ..., "topic_at": ...}`, each key only when that review happened. An override cleared again
        is a review too - the article's own decision to read at its estimate."""
        if not article_ids:
            return {}
        rows = connection.execute(
            select(ReadingReviewEvent.article_id, ReadingReviewEvent.changes_json, ReadingReviewEvent.created_at)
            .where(
                ReadingReviewEvent.article_id.in_(list(article_ids)),
                ReadingReviewEvent.action.in_(("level_override", "edited")),
            )
            .order_by(ReadingReviewEvent.created_at, ReadingReviewEvent.id)
        ).all()
        found: dict[Any, dict[str, str]] = {}
        for row in rows:
            changes = row.changes_json or {}
            if "reviewed_level" in changes:
                found.setdefault(row.article_id, {})["level_at"] = _iso(row.created_at)
            if "topic" in changes or "subtopic" in changes:
                found.setdefault(row.article_id, {})["topic_at"] = _iso(row.created_at)
        return found

    def review_marks(self, article_id: str) -> dict[str, str]:
        """`_review_marks` for one article: the content-pack importer's check for a review of this environment's own."""
        if _lookup_uuid(article_id) is None:
            return {}
        with self.engine.connect() as connection:
            return self._review_marks(connection, [_uuid(article_id)]).get(_uuid(article_id), {})

    def _rights_decisions(
        self, connection: Any, article_ids: Sequence[Any]
    ) -> dict[Any, list[dict[str, Any]]]:
        """Recorded rights answers per article, oldest first."""
        events = self._decision_events(connection, article_ids)
        return {
            key: [entry for entry in entries if entry["action"] == RIGHTS_EVENT]
            for key, entries in events.items()
        }

    def set_rights(
        self,
        article_id: str,
        answers: Mapping[str, Any],
        *,
        actor: str,
        reason: str = "",
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        """Record an administrator's answers to the rights questions.

        Append-only: the source snapshot is evidence and stays as ingested, so
        this writes a review event carrying the before and after, and the
        effective rights are the snapshot with those events folded over it.
        A value of `None` clears an earlier answer back to unanswered.
        """
        current = self.get_article(article_id)
        if current is None or current["source"] is None:
            return None
        chosen = {
            key: answers[key]
            for key in (*RIGHTS_QUESTIONS, "license_note", "automation_allowed")
            if key in answers
        }
        before = {
            key: (
                (current["automation"] or {}).get("override")
                if key == "automation_allowed"
                else current["source"]["rights_effective"].get(key)
            )
            for key in chosen
        }
        with self.engine.begin() as connection:
            # The events are folded oldest first and ties fall back to a random id, so a later
            # answer recorded in the same instant as an earlier one could lose. Each rights event
            # is stamped strictly after the article's previous one instead.
            moment = _now(now)
            last = connection.execute(
                select(func.max(ReadingReviewEvent.created_at)).where(
                    ReadingReviewEvent.article_id == _uuid(article_id),
                    ReadingReviewEvent.action == RIGHTS_EVENT,
                )
            ).scalar()
            last = _aware(last)
            if last is not None and moment <= last:
                moment = last + timedelta(microseconds=1)
            self._record_event(
                connection,
                article_id=_uuid(article_id),
                actor=actor,
                action=RIGHTS_EVENT,
                reason=reason,
                changes={"from": before, "to": chosen},
                now=moment,
            )
            if current["status"] == LEARNER_VISIBLE_STATUS:
                # The credit a learner reads is derived from these answers.
                self._bump_revision(connection, _uuid(article_id), moment)
        return self.get_article(article_id)

    # ---- thumbnails (D-194) -------------------------------------------------
    def set_image_policy(
        self, source_id: str, allowed: bool, *, actor: str, now: datetime | None = None
    ) -> dict[str, Any] | None:
        """Turn learner thumbnails from a source on or off. Stored in the source's existing config JSON; a change
        moves the revision of its published articles, so the withdrawal reaches cached copies."""
        if _lookup_uuid(source_id) is None:
            return None
        moment = _now(now)
        with self.engine.begin() as connection:
            changed = _update_source_policy(
                connection, _uuid(source_id), lambda policy: with_image_policy(policy, allowed), now=moment
            )
            if changed is None:
                return None
            row = connection.execute(select(ReadingSource).where(ReadingSource.id == _uuid(source_id))).first()
        return _source(row)

    def set_auto_publish(
        self, source_id: str, enabled: bool, *, actor: str, now: datetime | None = None
    ) -> dict[str, Any] | None:
        """Let a source's cleared items publish without a person, or stop it (#352). Stored in the source's config
        JSON beside the image policy; what was already published stays as it is."""
        if _lookup_uuid(source_id) is None:
            return None
        moment = _now(now)
        with self.engine.begin() as connection:
            changed = _update_source_policy(
                connection, _uuid(source_id), lambda policy: with_auto_publish(policy, enabled), now=moment
            )
            if changed is None:
                return None
            row = connection.execute(select(ReadingSource).where(ReadingSource.id == _uuid(source_id))).first()
        return _source(row)

    def _image_context(self, article_id: str) -> dict[str, Any] | None:
        if _lookup_uuid(article_id) is None:
            return None
        with self.engine.connect() as connection:
            article = connection.execute(
                select(ReadingArticle).where(ReadingArticle.id == _uuid(article_id))
            ).first()
            if article is None:
                return None
            item = connection.execute(
                select(ReadingSourceItem).where(ReadingSourceItem.id == article.source_item_id)
            ).first()
            if item is None:
                return None
            source = connection.execute(
                select(ReadingSource).where(ReadingSource.id == item.source_id)
            ).first()
            others = connection.execute(
                select(ReadingSourceItem.metadata_json)
                .where(ReadingSourceItem.source_id == item.source_id, ReadingSourceItem.id != item.id)
                .order_by(ReadingSourceItem.fetched_at.desc())
                .limit(300)
            ).all()
            events = self._decision_events(connection, [article.id]).get(article.id, [])
        return {"article": article, "item": item, "source": source, "others": others, "events": events}

    def image_review(self, article_id: str) -> dict[str, Any] | None:
        """What an administrator reviews for one article's thumbnail: the candidates, their eligibility,
        the approved picture and whether the source allows learners to see one. Admin only - it names
        no candidate address, only the index the admin routes take."""
        context = self._image_context(article_id)
        if context is None:
            return None
        article, item, source = context["article"], context["item"], context["source"]
        media = list(((item.metadata_json or {}).get("extraction") or {}).get("media") or [])
        folded = fold_image_events([e for e in context["events"] if e["action"] in IMAGE_EVENTS])
        approved = folded["approved"]
        counts = shared_url_counts(
            [list(((meta or {}).get("extraction") or {}).get("media") or []) for (meta,) in context["others"]]
        )
        policy_allowed = image_policy_allowed(source.polling_policy if source else None)
        publisher = _learner_credit(SimpleNamespace(
            item_metadata=item.metadata_json, source_policy=source.polling_policy if source else {},
            source_slug=source.slug if source else "", canonical_url=item.canonical_url,
            original_author=item.original_author,
        ), {})["publisher"]
        shown = learner_image(
            article_id=str(article.id), revision=article.content_revision, policy_allowed=policy_allowed,
            approved=approved, publisher=publisher,
        )
        return {
            "article_id": str(article.id),
            "source_id": str(item.source_id),
            "policy_allowed": policy_allowed,
            "candidates": assess_candidates(
                media, shared_counts=counts, rejected=folded["rejected"],
                approved_url=str((approved or {}).get("candidate_url") or ""),
            ),
            "approved": (
                {key: approved.get(key) for key in ("width", "height", "content_type", "credit", "alt", "kind")}
                if approved else None
            ),
            "shown_to_learners": shown is not None,
            "shared_threshold": SHARED_URL_THRESHOLD,
        }

    def image_candidate(self, article_id: str, index: int) -> dict[str, Any] | None:
        """The stored candidate at `index` for the admin routes, with the source policy and whether it is
        eligible. The request carries an index, never an address."""
        context = self._image_context(article_id)
        if context is None or isinstance(index, bool) or not isinstance(index, int):
            return None
        media = list(((context["item"].metadata_json or {}).get("extraction") or {}).get("media") or [])
        if not (0 <= index < len(media)):
            return None
        url = candidate_url(media[index])
        review = self.image_review(article_id)
        row = next((c for c in (review or {}).get("candidates", []) if c["index"] == index), None)
        if not url or row is None:
            return None
        return {"url": url, "candidate": row, "policy_allowed": review["policy_allowed"], "entry": dict(media[index])}

    def _record_image_event(
        self, article_id: str, action: str, changes: dict[str, Any], *, actor: str, reason: str,
        now: datetime | None,
    ) -> bool:
        if _lookup_uuid(article_id) is None:
            return False
        with self.engine.begin() as connection:
            article = connection.execute(
                select(ReadingArticle.status).where(ReadingArticle.id == _uuid(article_id))
            ).first()
            if article is None:
                return False
            moment = _now(now)
            last = connection.execute(
                select(func.max(ReadingReviewEvent.created_at)).where(
                    ReadingReviewEvent.article_id == _uuid(article_id),
                    ReadingReviewEvent.action.in_((RIGHTS_EVENT, *IMAGE_EVENTS)),
                )
            ).scalar()
            last = _aware(last)
            if last is not None and moment <= last:
                moment = last + timedelta(microseconds=1)
            self._record_event(
                connection, article_id=_uuid(article_id), actor=actor, action=action, reason=reason,
                changes=changes, now=moment,
            )
            # The thumbnail is in the learner payload, so a change moves the revision a cached copy checks.
            if article.status == LEARNER_VISIBLE_STATUS:
                self._bump_revision(connection, _uuid(article_id), moment)
        return True

    def approve_image(
        self, article_id: str, stored: Mapping[str, Any], *, actor: str, reason: str = "",
        now: datetime | None = None,
    ) -> bool:
        """Record the approval of one fetched and stored candidate (the bytes are already in the asset store)."""
        return self._record_image_event(
            article_id, IMAGE_SET_EVENT, {"from": None, "to": {"image": dict(stored)}},
            actor=actor, reason=reason, now=now,
        )

    def reject_image(
        self, article_id: str, url: str, *, actor: str, reason: str = "", now: datetime | None = None
    ) -> bool:
        return self._record_image_event(
            article_id, IMAGE_REJECTED_EVENT, {"from": None, "to": {"rejected_url": url}},
            actor=actor, reason=reason, now=now,
        )

    def clear_image(
        self, article_id: str, *, actor: str, reason: str = "", now: datetime | None = None
    ) -> bool:
        return self._record_image_event(
            article_id, IMAGE_SET_EVENT, {"from": None, "to": {"image": None}},
            actor=actor, reason=reason, now=now,
        )

    def has_thumbnail(self, article_id: str) -> bool:
        """Whether a learner would be shown a picture for this article (a typographic cover, a licensed image or an
        approved source image the source's policy allows). The publish gate asks this (D-240)."""
        if _lookup_uuid(article_id) is None:
            return False
        with self.engine.connect() as connection:
            row = connection.execute(
                select(ReadingArticle.id, ReadingArticle.content_revision).where(ReadingArticle.id == _uuid(article_id))
            ).first()
            if row is None:
                return False
            _, images = self._credits_and_images(connection, [row.id], revisions={row.id: row.content_revision})
        return images.get(row.id) is not None

    def published_thumbnail(self, article_id: str) -> dict[str, Any] | None:
        """The stored thumbnail (asset key, type, hash and provenance) a learner is shown for this article, or None.
        Content packs carry it with the article (D-240)."""
        if not self.has_thumbnail(article_id):
            return None
        with self.engine.connect() as connection:
            events = self._decision_events(connection, [_uuid(article_id)]).get(_uuid(article_id), [])
        approved = fold_image_events([e for e in events if e["action"] in IMAGE_EVENTS])["approved"] or {}
        return dict(approved) if approved.get("asset_key") else None

    def approved_image_asset(self, article_id: str) -> dict[str, Any] | None:
        """The stored picture a learner may be served for a published article, or None. Re-checks the
        whole rule at serve time, so turning a source's policy off hides its pictures at once."""
        if _lookup_uuid(article_id) is None:
            return None
        with self.engine.connect() as connection:
            row = connection.execute(
                select(ReadingArticle.id, ReadingArticle.content_revision).where(
                    ReadingArticle.id == _uuid(article_id), ReadingArticle.status == LEARNER_VISIBLE_STATUS
                )
            ).first()
            if row is None:
                return None
            _, images = self._credits_and_images(connection, [row.id], revisions={row.id: row.content_revision})
            if images.get(row.id) is None:
                return None
            events = self._decision_events(connection, [row.id]).get(row.id, [])
        approved = fold_image_events([e for e in events if e["action"] in IMAGE_EVENTS])["approved"] or {}
        key, content_type = approved.get("asset_key"), approved.get("content_type")
        return (
            {"asset_key": key, "content_type": content_type, "sha256": str(approved.get("sha256") or "")}
            if key and content_type else None
        )

    def article_for_source_item(self, source_item_id: str) -> dict[str, Any] | None:
        if _lookup_uuid(source_item_id) is None:
            return None
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
        content_kind: str | None = None,
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
            ("content_kind", content_kind),
        ):
            if value is not None and value != current[field]:
                values[field] = value
                changes[field] = {"from": current[field], "to": value}
        level_changed = reviewed_level != "" and (reviewed_level or None) != current["reviewed_level"]
        if reviewed_level:
            bands = ZH_LEVEL_BANDS if current["language"] == "zh" else EN_LEVEL_BANDS
            if reviewed_level not in bands:
                raise ValueError(f"{reviewed_level!r} is not a level on this article's scale")
        if level_changed:
            values["reviewed_level"] = reviewed_level or None
            values["effective_level"] = _effective(
                current["estimated_level"], reviewed_level or None
            )
            changes["reviewed_level"] = {"from": current["reviewed_level"], "to": reviewed_level}
        if len(values) == 1:
            return current
        # Any change to what a learner reads invalidates a cached copy. The
        # level and the topic are on the card, not only in the article, so a
        # correction to either has to move the revision an ETag is built from.
        if set(LEARNER_VISIBLE_FIELDS) & set(changes):
            values["content_revision"] = current["content_revision"] + 1
        with self.engine.begin() as connection:
            # The article row first, `FOR UPDATE`, and its body read again
            # inside this transaction: the same lock a comprehension set's
            # approval and a learner's submit take, so a body edit and either
            # of them serialize instead of racing (canonical Reading, §5.1/§6).
            locked = select(ReadingArticle.body).where(ReadingArticle.id == _uuid(article_id))
            if connection.dialect.name == "postgresql":
                locked = locked.with_for_update()
            stored_body = connection.execute(locked).scalar_one()
            if "body" in values and values["body"] == stored_body:
                values.pop("body")
                changes.pop("body", None)
            if "body" in values:
                # The counts a card shows are facts about the body: measured again, by the
                # function admission uses, so a cut never leaves the old length behind.
                stored = connection.execute(
                    select(ReadingArticle.analysis_json).where(ReadingArticle.id == _uuid(article_id))
                ).scalar_one()
                derived = body_derived_values(values["body"], current["language"], stored)
                values |= derived
                changes["recounted"] = {
                    "word_count": {"from": current["word_count"], "to": derived["word_count"]},
                    "reading_time_seconds": {
                        "from": current["reading_time_seconds"], "to": derived["reading_time_seconds"]},
                }
                values["content_revision"] = current["content_revision"] + 1
                changes.update(self._body_follow_ups(
                    connection, _uuid(article_id), values["body"], current["language"], stored))
            connection.execute(
                update(ReadingArticle)
                .where(ReadingArticle.id == _uuid(article_id))
                .values(**values)
            )
            if "body" in values:
                # Every approved comprehension set whose anchor no longer
                # matches becomes `stale`, in this same transaction.
                changes["stale_comprehension_sets"] = stale_sets_for_body(
                    connection, _uuid(article_id), values["body"], actor=actor, now=moment
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

    def reestimate_level(
        self, article_id: str, *, actor: str, reason: str = "reestimate", now: datetime | None = None,
    ) -> dict[str, Any] | None:
        """Re-estimate one article's automatic level with the current estimator (`LEVEL_VERSION`).

        The machine's own column, written by the machine's own function (`analyze_article`) over the body read
        inside this transaction, `FOR UPDATE`: `estimated_level`, its confidence, and the analysis's
        `level_version`, `level_confidence` and `level_evidence`. `reviewed_level` is never touched; the learner's
        `effective_level` moves only when no reviewer override exists (D-196). Re-estimating is an owner decision
        (D-198): this method is called only by `scripts/reading_relevel.py`. None when the article does not exist,
        else `{"id", "from", "to", "level_version", "changed"}`; an unchanged level writes nothing.
        """
        moment = _now(now)
        with self.engine.begin() as connection:
            query = select(ReadingArticle.id, ReadingArticle.body, ReadingArticle.language,
                           ReadingArticle.estimated_level, ReadingArticle.reviewed_level,
                           ReadingArticle.effective_level, ReadingArticle.analysis_json,
                           ReadingArticle.content_revision).where(ReadingArticle.id == _uuid(article_id))
            if connection.dialect.name == "postgresql":
                query = query.with_for_update()
            row = connection.execute(query).first()
            if row is None:
                return None
            measured = analyze_article(row.body or "", row.language or "en")
            stored = dict(row.analysis_json or {}) if isinstance(row.analysis_json, Mapping) else {}
            old_version = str(stored.get("level_version") or "")
            result = {"id": str(row.id), "from": row.estimated_level or "", "to": measured.estimated_level,
                      "level_version": measured.level_version, "changed": measured.estimated_level != (row.estimated_level or "")}
            if not result["changed"]:
                return result
            stored.update(level_confidence=measured.confidence, level_version=measured.level_version,
                          level_evidence=measured.evidence)
            effective = _effective(measured.estimated_level, row.reviewed_level)
            values: dict[str, Any] = {
                "estimated_level": measured.estimated_level,
                "estimated_level_confidence": float(measured.confidence),
                "effective_level": effective,
                "analysis_json": stored,
                "updated_at": moment,
            }
            if effective != row.effective_level:
                # The level is on the learner's card: a cached copy must refetch.
                values["content_revision"] = row.content_revision + 1
            connection.execute(update(ReadingArticle).where(ReadingArticle.id == row.id).values(**values))
            self._record_event(connection, article_id=row.id, actor=actor, action="level_reestimated", reason=reason,
                               changes={"estimated_level": {"from": result["from"], "to": result["to"]},
                                        "level_version": {"from": old_version, "to": measured.level_version},
                                        "effective_level": {"from": row.effective_level, "to": effective}},
                               now=moment)
        return result

    def recount_articles(
        self, *, apply: bool = False, article_id: str | None = None, actor: str = "recount",
        now: datetime | None = None, batch_size: int = RECOUNT_BATCH_SIZE,
    ) -> list[dict[str, Any]]:
        """Articles whose stored counts differ from their body; with `apply`, fix them (idempotent).

        Ids are paged in batches (keyset) and each article is read, locked `FOR UPDATE`, corrected
        and committed in its own transaction, so memory stays bounded to one body and a failure
        part-way leaves every earlier row fixed. Stale size issues and orphan targets are
        reported, never auto-cleared.
        """
        moment = _now(now)
        found: list[dict[str, Any]] = []
        for row_id in self._recount_ids(article_id, batch_size):
            with self.engine.begin() as connection:
                query = select(ReadingArticle.id, ReadingArticle.body, ReadingArticle.language,
                               ReadingArticle.word_count, ReadingArticle.reading_time_seconds,
                               ReadingArticle.analysis_json, ReadingArticle.content_revision
                               ).where(ReadingArticle.id == row_id)
                if connection.dialect.name == "postgresql":
                    query = query.with_for_update()
                row = connection.execute(query).first()
                if row is None:
                    continue
                derived = body_derived_values(row.body, row.language, row.analysis_json)
                if (derived["word_count"], derived["reading_time_seconds"]) == (row.word_count, row.reading_time_seconds):
                    continue
                item = {
                    "id": str(row.id), "language": row.language,
                    "word_count": {"from": row.word_count, "to": derived["word_count"]},
                    "reading_time_seconds": {"from": row.reading_time_seconds, "to": derived["reading_time_seconds"]},
                }
                item.update(self._body_follow_ups(connection, row.id, row.body, row.language, row.analysis_json))
                found.append(item)
                if apply:
                    connection.execute(update(ReadingArticle).where(ReadingArticle.id == row.id).values(
                        **derived, content_revision=row.content_revision + 1, updated_at=moment))
                    self._record_event(connection, article_id=row.id, actor=actor, action="edited",
                                       reason="recount", changes={"recounted": item}, now=moment)
        return found

    def _recount_ids(self, article_id: str | None, batch_size: int) -> Iterator[uuid.UUID]:
        if article_id:
            yield _uuid(article_id)
            return
        last: uuid.UUID | None = None
        while True:
            query = select(ReadingArticle.id).order_by(ReadingArticle.id).limit(max(1, batch_size))
            if last is not None:
                query = query.where(ReadingArticle.id > last)
            with self.engine.connect() as connection:
                ids = list(connection.execute(query).scalars())
            if not ids:
                return
            yield from ids
            last = ids[-1]

    @staticmethod
    def _body_follow_ups(
        connection: Any, article_id: uuid.UUID, body: str, language: str, analysis: Mapping[str, Any] | None
    ) -> dict[str, Any]:
        """What a changed body leaves for an admin to decide: reported, never cleared."""
        out: dict[str, Any] = {}
        stored = [code for code in ((analysis or {}).get("quality_issues") or []) if code in SIZE_ISSUE_CODES]
        current = [code for code in quality_issues(body, language) if code in SIZE_ISSUE_CODES]
        if sorted(stored) != sorted(current):
            out["stale_quality_issues"] = {"stored": stored, "now": current}
        folded = body.casefold()
        targets = connection.execute(
            select(ReadingArticleTarget.text).where(
                ReadingArticleTarget.article_id == article_id, ReadingArticleTarget.admin_rejected.is_(False))
        ).scalars()
        orphans = [text for text in targets if text.strip() and text.casefold() not in folded]
        if orphans:
            out["orphan_targets"] = orphans
        return out

    def set_status(
        self,
        article_id: str,
        status: str,
        *,
        actor: str,
        reason: str = "",
        quality_override: bool = False,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        """Move an article through its lifecycle, recording who and why.

        Publishing an article with a hard quality failure (`reading_page_quality`) is refused
        here, not only in the route, so a script that calls this directly is stopped too.
        `quality_override` publishes anyway; it needs a reason and is recorded on the event.

        Publication is the only transition that makes anything learner-visible,
        and it is always an admin's act: nothing in the pipeline calls this.
        Rights and attribution refuse here too (D-250, amends D-190): an article
        whose rights are not clear (`reading_rights_gate.rights_blockers`) is not
        published, and there is no override.
        """
        current = self.get_article(article_id)
        if current is None:
            return None
        moment = _now(now)
        values: dict[str, Any] = {"status": status, "updated_at": moment}
        overridden: list[str] = []
        if status == LEARNER_VISIBLE_STATUS:
            if self.require_thumbnail and current["status"] != LEARNER_VISIBLE_STATUS and not self.has_thumbnail(article_id):
                raise ThumbnailRequired("reading article")
            overridden = hard_issues((current.get("analysis") or {}).get("quality_issues"))
            if overridden and not quality_override:
                raise QualityRefused(overridden)
            if overridden and not reason.strip():
                raise QualityRefused(overridden, reason_missing=True)
            blockers = rights_blockers(current)
            if blockers:
                raise RightsRefused(blockers)
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
                changes={
                    "status": {"from": current["status"], "to": status},
                    **({"quality_override": True, "quality_codes": overridden,
                        "quality_version": QUALITY_VERSION} if overridden else {}),
                },
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
        # The columns the queue draws, named for the same reason the learner
        # list names its own: a reviewer scanning twenty-five candidates should
        # not pull twenty-five article bodies across the connection to read
        # their titles.
        query = select(
            ReadingArticle.id,
            ReadingArticle.title,
            ReadingArticle.language,
            ReadingArticle.topic,
            ReadingArticle.effective_level,
            ReadingArticle.estimated_level,
            ReadingArticle.reviewed_level,
            ReadingArticle.word_count,
            ReadingArticle.reading_time_seconds,
            ReadingArticle.status,
            ReadingArticle.created_at,
            ReadingSource.name.label("source_name"),
            ReadingSourceItem.rights_snapshot_json.label("rights_snapshot"),
            ReadingSource.automation_allowed.label("source_automation"),
            (
                select(func.count())
                .select_from(ReadingArticleTarget)
                .where(
                    ReadingArticleTarget.article_id == ReadingArticle.id,
                    ReadingArticleTarget.admin_rejected.is_(False),
                )
                .scalar_subquery()
            ).label("target_count"),
        )
        query = query.join(
            ReadingSourceItem, ReadingSourceItem.id == ReadingArticle.source_item_id
        ).join(ReadingSource, ReadingSource.id == ReadingSourceItem.source_id)
        query = query.where(ReadingArticle.status.in_(tuple(statuses)))
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
            decisions = self._rights_decisions(connection, [row.id for row in page])
        next_cursor = (
            _encode_cursor(_aware(page[-1].created_at), str(page[-1].id))
            if len(rows) > bounded and page
            else None
        )
        items = []
        for row in page:
            item = _queue_row(row)
            answered = [entry["answers"] for entry in decisions.get(row.id, [])]
            effective = overlay_rights(row.rights_snapshot, answered, row.source_automation)
            item["automation_allowed"] = effective_automation(answered, row.source_automation)["allowed"]
            # The one answer the publication gate turns on, in the same three
            # words the review page uses.
            item["rights_level"] = rights_state(effective)["can_republish"]
            items.append(item)
        return {"items": items, "next_cursor": next_cursor}

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
        # The ten columns a card draws, named rather than `select(Article)`:
        # the entity form reads every body from disk and transfers it for up to
        # sixty rows before Python throws them away, which is the cost the
        # whole partial-index design exists to avoid.
        query = select(
            ReadingArticle.id,
            ReadingArticle.title,
            ReadingArticle.language,
            ReadingArticle.effective_level,
            ReadingArticle.reviewed_level,
            ReadingArticle.topic,
            ReadingArticle.reading_time_seconds,
            ReadingArticle.word_count,
            ReadingArticle.excerpt,
            ReadingArticle.published_at,
            ReadingArticle.content_revision,
        ).where(
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
            scripts: dict[Any, Any] = {}
            credits, images = self._credits_and_images(
                connection, [row.id for row in page], revisions={row.id: row.content_revision for row in page},
                scripts=scripts,
            )
        return {
            "items": [
                {**_learner_row(row), **_script_field(row.language, scripts.get(row.id)),
                 "provenance": credits.get(row.id) or build_provenance(
                    publisher="", url="", author="", rights=None), "image": images.get(row.id)}
                for row in page
            ],
            "next_cursor": next_cursor,
        }

    def published_pool(self, *, language: str, level: str | None, limit: int = 20_000) -> list[tuple[str, Any]]:
        """`(id, published_at)` of every published article of one (language, level): the pool content access tiers
        (D-248 §4, `product/content_access.py`). Two narrow columns, bounded; the caller caches it."""
        query = select(ReadingArticle.id, ReadingArticle.published_at).where(
            ReadingArticle.status == LEARNER_VISIBLE_STATUS,
            ReadingArticle.language == language,
        )
        query = query.where(ReadingArticle.effective_level == level) if level else query.where(
            ReadingArticle.effective_level.is_(None) | (ReadingArticle.effective_level == ""))
        query = query.order_by(ReadingArticle.published_at, ReadingArticle.id).limit(max(1, int(limit)))
        with self.engine.connect() as connection:
            return [(str(row.id), _aware(row.published_at) if row.published_at else None)
                    for row in connection.execute(query).all()]

    def get_published_article(self, article_id: str) -> dict[str, Any] | None:
        """What a learner opens: the text, the targets an admin approved, and
        the attribution the rights require. No analysis, no review history, no
        rights payload, no job state."""
        if _lookup_uuid(article_id) is None:
            return None
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
            credits, images = self._credits_and_images(
                connection, [row.id], revisions={row.id: row.content_revision}
            )
            credit = credits.get(row.id)
        return {
            "id": str(row.id),
            "title": row.title,
            "body": row.body,
            "language": row.language,
            "level": row.effective_level,
            "level_source": _level_source(row),
            "topic": row.topic,
            "reading_time_seconds": row.reading_time_seconds,
            "word_count": row.word_count,
            "content_revision": row.content_revision,
            "published_at": _iso(row.published_at),
            **_script_field(row.language, (row.analysis_json or {}).get("script") or detect_script(row.body)),
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
            "provenance": credit or build_provenance(publisher="", url="", author="", rights=None),
            "image": images.get(row.id),
            "attribution": {
                "author": source_item.original_author if source_item else "",
                "source_url": source_item.canonical_url if source_item else "",
                "published_at": _iso(source_item.original_published_at) if source_item else None,
            },
        }

    def article_for_content(
        self, source_slug: str, content_hash: str, *, fingerprint: Callable[[str], str] | None = None
    ) -> dict[str, Any] | None:
        """The article this environment already holds with this text under that source, if any (pack dedupe).

        A pack carries the article's text, which an editor may have changed after import, so the match is on the
        text of each current article under the source (with the caller's `fingerprint`), and only falls back to
        the snapshot hash. Bounded: one source's articles."""

        with self.engine.connect() as connection:
            rows = connection.execute(
                select(ReadingArticle.id, ReadingArticle.status, ReadingArticle.body, ReadingArticle.title,
                       ReadingArticle.language, ReadingArticle.topic, ReadingSourceItem.content_hash)
                .join(ReadingSourceItem, ReadingSourceItem.id == ReadingArticle.source_item_id)
                .join(ReadingSource, ReadingSource.id == ReadingSourceItem.source_id)
                # Not only current snapshots: texts that share one address (a collection on one page) supersede
                # each other's snapshot while every article stays live.
                .where(ReadingSource.slug == source_slug)
                .limit(5000)
            ).all()
        for row in rows:
            if row.content_hash == content_hash or (fingerprint is not None and fingerprint(row.body) == content_hash):
                # What the importer needs to finish a present article (its typographic cover is made from these).
                return {"id": str(row.id), "status": row.status, "title": row.title, "language": row.language,
                        "topic": row.topic or ""}
        return None

    def published_for_export(
        self, *, source_slug_prefix: str = "", languages: Sequence[str] = (), limit: int = 5000
    ) -> list[dict[str, Any]]:
        """Published articles as a content pack carries them (proposals/CONTENT_PACKS.md): the text a learner reads,
        where it came from, and the rights as the gate reads them - the snapshot with the recorded answers laid
        over it. No ids leave with them except as `origin_id`, and nothing about learners or review history."""

        query = (
            select(
                ReadingArticle.id, ReadingArticle.title, ReadingArticle.body, ReadingArticle.language,
                ReadingArticle.topic, ReadingArticle.subtopic, ReadingArticle.content_kind, ReadingArticle.reviewed_level,
                ReadingSourceItem.canonical_url, ReadingSourceItem.original_author,
                ReadingSourceItem.original_published_at, ReadingSourceItem.rights_snapshot_json.label("rights_snapshot"),
                ReadingSource.slug.label("source_slug"), ReadingSource.automation_allowed.label("source_automation"),
            )
            .join(ReadingSourceItem, ReadingSourceItem.id == ReadingArticle.source_item_id)
            .join(ReadingSource, ReadingSource.id == ReadingSourceItem.source_id)
            .where(ReadingArticle.status == LEARNER_VISIBLE_STATUS)
            .order_by(ReadingSource.slug, ReadingArticle.published_at, ReadingArticle.id)
            .limit(max(1, min(int(limit), 5000)))
        )
        if source_slug_prefix:
            query = query.where(ReadingSource.slug.startswith(source_slug_prefix))
        if languages:
            query = query.where(ReadingArticle.language.in_(tuple(languages)))
        with self.engine.connect() as connection:
            rows = connection.execute(query).all()
            decisions = self._rights_decisions(connection, [row.id for row in rows])
            marks = self._review_marks(connection, [row.id for row in rows])
        exported = []
        for row in rows:
            answered = [entry["answers"] for entry in decisions.get(row.id, [])]
            effective = overlay_rights(row.rights_snapshot, answered, row.source_automation)
            mark = marks.get(row.id, {})
            exported.append({
                "origin_id": str(row.id), "title": row.title, "body": row.body, "language": row.language,
                "topic": row.topic, "subtopic": row.subtopic, "content_kind": row.content_kind,
                "canonical_url": row.canonical_url, "author": row.original_author,
                "published_at": _iso(row.original_published_at), "source_slug": row.source_slug,
                "rights": {key: effective.get(key) for key in ("can_republish", "can_adapt", "attribution_required",
                                                                  "license_note") if key in effective},
                # An administrator's review travels with the text (#411): the reviewed level, and when the level and
                # the topic were reviewed - never who reviewed them (a pack carries no personal data).
                "reviewed_level": row.reviewed_level,
                "review": {key: {"by": "administrator", "at": mark[f"{key}_at"]}
                           for key in ("level", "topic") if f"{key}_at" in mark},
            })
        return exported

    def published_credits(self, *, limit: int = 5000) -> list[dict[str, Any]]:
        """Each learner-visible text with the credit its rights record: title,
        author, source address and licence note, read from the snapshot with the
        recorded rights answers laid over it - the same rights the gate reads.
        No body."""
        query = (
            select(
                ReadingArticle.id,
                ReadingArticle.title,
                ReadingArticle.language,
                ReadingSourceItem.original_author,
                ReadingSourceItem.canonical_url,
                ReadingSourceItem.rights_snapshot_json.label("rights_snapshot"),
                ReadingSourceItem.metadata_json.label("item_metadata"),
                ReadingSource.slug.label("source_slug"),
                ReadingSource.polling_policy.label("source_policy"),
                ReadingSource.automation_allowed.label("source_automation"),
            )
            .join(ReadingSourceItem, ReadingSourceItem.id == ReadingArticle.source_item_id)
            .join(ReadingSource, ReadingSource.id == ReadingSourceItem.source_id)
            .where(ReadingArticle.status == LEARNER_VISIBLE_STATUS)
            .order_by(ReadingArticle.language, ReadingArticle.title, ReadingArticle.id)
            .limit(max(1, int(limit)))
        )
        with self.engine.connect() as connection:
            rows = connection.execute(query).all()
            decisions = self._rights_decisions(connection, [row.id for row in rows])
        credits = []
        for row in rows:
            answered = [entry["answers"] for entry in decisions.get(row.id, [])]
            effective = overlay_rights(row.rights_snapshot, answered, row.source_automation)
            credit = _learner_credit(row, effective)
            credits.append({
                "title": row.title,
                "language": row.language,
                "author": row.original_author,
                "source_url": row.canonical_url,
                "source_name": credit["publisher"],
                "license_note": str(effective.get("license_note") or ""),
            })
        return credits

    def _provenance_map(self, connection: Any, article_ids: Sequence[Any]) -> dict[Any, dict[str, Any]]:
        """The learner-visible credit of each article: its source's name, the
        item's address and author, and the effective rights (snapshot with the
        recorded answers folded over it). One set-wise query for the ids given,
        so a list page costs two reads whatever its size."""
        return self._credits_and_images(connection, article_ids, revisions=None)[0]

    def _credits_and_images(
        self, connection: Any, article_ids: Sequence[Any], *, revisions: Mapping[Any, int] | None,
        scripts: dict[Any, Any] | None = None,
    ) -> tuple[dict[Any, dict[str, Any]], dict[Any, dict[str, str] | None]]:
        """The credit of each article and, when `revisions` is given, its learner `image` (or None).

        The same two reads whatever the page size: the thumbnail rule (policy on, a candidate approved, a
        credit) needs only columns of rows already read and the review events already read for the rights
        answers."""
        if not article_ids:
            return {}, {}
        rows = connection.execute(
            select(
                ReadingArticle.id,
                ReadingSourceItem.original_author,
                ReadingSourceItem.canonical_url,
                ReadingSourceItem.rights_snapshot_json.label("rights_snapshot"),
                ReadingSourceItem.metadata_json.label("item_metadata"),
                ReadingSource.slug.label("source_slug"),
                ReadingSource.polling_policy.label("source_policy"),
                ReadingSource.automation_allowed.label("source_automation"),
            )
            .join(ReadingSourceItem, ReadingSourceItem.id == ReadingArticle.source_item_id)
            .join(ReadingSource, ReadingSource.id == ReadingSourceItem.source_id)
            .where(ReadingArticle.id.in_(list(article_ids)))
        ).all()
        events = self._decision_events(connection, [row.id for row in rows])
        credits: dict[Any, dict[str, Any]] = {}
        images: dict[Any, dict[str, str] | None] = {}
        for row in rows:
            entries = events.get(row.id, [])
            answered = [entry["answers"] for entry in entries if entry["action"] == RIGHTS_EVENT]
            effective = overlay_rights(row.rights_snapshot, answered, row.source_automation)
            credits[row.id] = _learner_credit(row, effective)
            if scripts is not None:
                # The Chinese script was measured at ingest and kept with the snapshot's metadata, which this
                # read already holds; the list never touches the article analysis (D-197).
                scripts[row.id] = (row.item_metadata or {}).get("script")
            if revisions is not None:
                images[row.id] = learner_image(
                    article_id=str(row.id),
                    revision=revisions.get(row.id, 0),
                    policy_allowed=image_policy_allowed(row.source_policy),
                    approved=fold_image_events([e for e in entries if e["action"] in IMAGE_EVENTS])["approved"],
                    # The fallback credit is the learner-facing publisher (D-192 resolver), never the
                    # registry name.
                    publisher=credits[row.id]["publisher"],
                )
        return credits, images

    def published_missing_provenance(self, *, limit: int = 5000) -> list[dict[str, Any]]:
        """Published articles whose required attribution is incomplete (D-189),
        each with `overridden`: whether the latest publish decision recorded an
        explicit, reasoned override of the warnings. Read-only: nothing is
        unpublished by this."""
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(ReadingArticle.id, ReadingArticle.title, ReadingArticle.language)
                .where(ReadingArticle.status == LEARNER_VISIBLE_STATUS)
                .order_by(ReadingArticle.language, ReadingArticle.title, ReadingArticle.id)
                .limit(max(1, int(limit)))
            ).all()
            credits = self._provenance_map(connection, [row.id for row in rows])
            flagged = [row for row in rows if provenance_blockers(credits.get(row.id) or {})]
            overridden: set[Any] = set()
            if flagged:
                events = connection.execute(
                    select(ReadingReviewEvent.article_id, ReadingReviewEvent.reason, ReadingReviewEvent.changes_json)
                    .where(ReadingReviewEvent.article_id.in_([row.id for row in flagged]),
                           ReadingReviewEvent.action == LEARNER_VISIBLE_STATUS)
                    .order_by(ReadingReviewEvent.created_at, ReadingReviewEvent.id)
                ).all()
                latest: dict[Any, bool] = {}
                for event in events:  # oldest first: the last one wins
                    latest[event.article_id] = bool(
                        (event.changes_json or {}).get("published_over_warnings") and str(event.reason or "").strip())
                overridden = {key for key, value in latest.items() if value}
        found = []
        for row in flagged:
            found.append({
                "id": str(row.id), "title": row.title, "language": row.language,
                "missing": [item["field"] for item in provenance_blockers(credits.get(row.id) or {})],
                "overridden": row.id in overridden,
            })
        return found

    def published_rights_violations(self, *, limit: int = 5000) -> list[dict[str, Any]]:
        """Published articles the D-250 gate would refuse now: each with its `blockers` and `overridden`, whether its
        latest publish went over D-190's warnings. Read-only - nothing is unpublished by this (Hermes for the owner,
        2026-10-21: re-check, never remove on its own)."""
        with self.engine.connect() as connection:
            ids = connection.execute(
                select(ReadingArticle.id)
                .where(ReadingArticle.status == LEARNER_VISIBLE_STATUS)
                .order_by(ReadingArticle.language, ReadingArticle.title, ReadingArticle.id)
                .limit(max(1, int(limit)))
            ).scalars().all()
        found = []
        for article_id in ids:
            article = self.get_article(str(article_id))
            blockers = rights_blockers(article) if article is not None else []
            if not blockers:
                continue
            published = [event for event in self.list_review_events(str(article_id), limit=200)
                         if event["action"] == LEARNER_VISIBLE_STATUS]  # fmt: skip
            found.append({
                "id": str(article_id), "title": article["title"], "language": article["language"],
                "blockers": [item["code"] for item in blockers],
                "overridden": bool(published and (published[-1].get("changes") or {}).get("published_over_warnings")),
            })
        return found

    def published_staff_only_rights_candidates(self, *, limit: int = 5000) -> list[dict[str, Any]]:
        """Published articles from a source whose public-domain status holds only for its own staff
        output (D-193), that show wire copy or no byline - judged now, from the stored snapshot,
        because items ingested before the refinement carry no record of it. `asserted` says the
        article's effective rights still answer "can republish" yes. Read-only."""
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(
                    ReadingArticle.id, ReadingArticle.title, ReadingArticle.language,
                    ReadingSourceItem.original_author, ReadingSourceItem.canonical_url,
                    ReadingSourceItem.original_content.label("body"),
                    ReadingSourceItem.metadata_json.label("item_metadata"),
                    ReadingSourceItem.rights_snapshot_json.label("rights_snapshot"),
                    ReadingSource.base_url.label("source_base_url"),
                    ReadingSource.automation_allowed.label("source_automation"),
                )
                .join(ReadingSourceItem, ReadingSourceItem.id == ReadingArticle.source_item_id)
                .join(ReadingSource, ReadingSource.id == ReadingSourceItem.source_id)
                .where(ReadingArticle.status == LEARNER_VISIBLE_STATUS)
                .order_by(ReadingArticle.language, ReadingArticle.title, ReadingArticle.id)
                .limit(max(1, int(limit)))
            ).all()
            decisions = self._rights_decisions(connection, [row.id for row in rows])
        found = []
        for row in rows:
            refinement = refine_item_rights(
                source_base_url=row.source_base_url, canonical_url=row.canonical_url,
                author=row.original_author, body=row.body, metadata=row.item_metadata or {})
            if not refinement or refinement["outcome"] != "withheld":
                continue
            answered = [entry["answers"] for entry in decisions.get(row.id, [])]
            effective = overlay_rights(row.rights_snapshot, answered, row.source_automation)
            found.append({
                "id": str(row.id), "title": row.title, "language": row.language,
                "reasons": refinement["reasons"], "evidence": refinement["evidence"],
                "asserted": rights_state(effective)["can_republish"] == "allowed",
                "licence": build_provenance(publisher="", url="", author="", rights=effective)["license"]["name"],
            })
        return found

    def published_count(self, *, language: str | None = None) -> int:
        query = select(func.count()).select_from(ReadingArticle).where(
            ReadingArticle.status == LEARNER_VISIBLE_STATUS
        )
        if language:
            query = query.where(ReadingArticle.language == language)
        with self.engine.connect() as connection:
            return int(connection.execute(query).scalar_one())

    # Admission reasons that are about rights and source policy; any other reason is a validator that failed.
    RIGHTS_REASONS = frozenset({"source_not_active", "automation_not_allowed", "rights_not_cleared",
                                "attribution_unknown", "attribution_missing", "source_origin_mismatch",
                                "auto_publish_off"})  # #352: the source waits for a person - policy, not a failure

    def review_reasons_summary(self, *, limit: int = 5000) -> dict[str, int]:
        """Articles waiting in review, split by why: a rights or source-policy question, or a failed validator
        ("invalid" on Admin's overview). An article an editor submitted by hand has no admission at all."""

        with self.engine.connect() as connection:
            rows = connection.execute(
                select(ReadingArticle.analysis_json).where(ReadingArticle.status == "needs_review").limit(limit)
            ).all()
        summary = {"rights": 0, "invalid": 0, "unscreened": 0}
        for (analysis,) in rows:
            admission = (analysis or {}).get("admission") if isinstance(analysis, Mapping) else None
            reasons = set((admission or {}).get("reasons") or [])
            if not admission:
                summary["unscreened"] += 1
            elif reasons - self.RIGHTS_REASONS:
                summary["invalid"] += 1
            else:
                summary["rights"] += 1
        return summary

    def counts_by_status(self) -> dict[str, int]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                select(ReadingArticle.status, func.count()).group_by(ReadingArticle.status)
            ).all()
        return {status: int(total) for status, total in rows}

    # ---- targets ---------------------------------------------------------
    def reorder_targets(
        self, article_id: str, *, order: list[str], actor: str, now: datetime | None = None
    ) -> list[dict[str, Any]] | None:
        """The order a learner meets these targets in, set by the reviewer.

        `rank` already decides the order everything reads them in, so this
        writes that column rather than inventing a second notion of order.

        The whole list is sent, not a move: an "up one" endpoint has to be
        replayed in sequence to be correct, and two reviewers dragging at the
        same time would interleave into an order neither of them chose. Sending
        the order means the last write is a complete intention.

        Refused as a whole - returning None and moving nothing - when the list
        is not exactly this article's targets. A partial order would silently
        renumber the rest, which is a worse outcome than a rejected request.
        """
        if _lookup_uuid(article_id) is None:
            return None
        moment = _now(now)
        with self.engine.begin() as connection:
            existing = connection.execute(
                select(ReadingArticleTarget.id).where(
                    ReadingArticleTarget.article_id == _uuid(article_id)
                )
            ).all()
            mine = {str(row.id) for row in existing}
            wanted = [str(target_id) for target_id in order]
            if len(wanted) != len(set(wanted)) or set(wanted) != mine:
                return None
            for rank, target_id in enumerate(wanted):
                connection.execute(
                    update(ReadingArticleTarget)
                    .where(ReadingArticleTarget.id == _uuid(target_id))
                    .values(rank=rank, updated_at=moment)
                )
            self._bump_revision(connection, _uuid(article_id), moment)
            self._record_event(
                connection,
                article_id=_uuid(article_id),
                actor=actor,
                action="targets_reordered",
                reason="",
                changes={"count": len(wanted)},
                now=moment,
            )
            rows = connection.execute(
                select(ReadingArticleTarget)
                .where(ReadingArticleTarget.article_id == _uuid(article_id))
                .order_by(ReadingArticleTarget.rank, ReadingArticleTarget.id)
            ).all()
        return [_target(row) for row in rows]

    def decide_target(
        self,
        target_id: str,
        *,
        article_id: str,
        approved: bool,
        actor: str,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        """The admin's decision, kept separate from the machine's suggestion.

        `machine_suggested` is never cleared: "the machine proposed this and a
        human approved it" and "a human added this" are different facts, and a
        future processor re-run has to be able to tell them apart.

        The article is part of the identity, not context. The route names both,
        and a target id taken from one article and posted under another's URL
        would otherwise decide the first article's target while the audit entry
        and the revision bump landed on the second - a decision recorded
        against content it was never made about.
        """
        if _lookup_uuid(target_id) is None or _lookup_uuid(article_id) is None:
            return None
        owned = (ReadingArticleTarget.id == _uuid(target_id)) & (
            ReadingArticleTarget.article_id == _uuid(article_id)
        )
        moment = _now(now)
        with self.engine.begin() as connection:
            row = connection.execute(select(ReadingArticleTarget).where(owned)).first()
            if row is None:
                return None
            connection.execute(
                update(ReadingArticleTarget)
                .where(owned)
                .values(
                    admin_approved=bool(approved),
                    admin_rejected=not approved,
                    updated_at=moment,
                )
            )
            self._bump_revision(connection, row.article_id, moment)
            self._record_event(
                connection,
                article_id=row.article_id,
                actor=actor,
                action="target_approved" if approved else "target_rejected",
                reason="",
                changes={"target": row.text},
                now=moment,
            )
            updated = connection.execute(select(ReadingArticleTarget).where(owned)).first()
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
            self._bump_revision(connection, _uuid(article_id), moment)
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
            self._bump_revision(connection, row.article_id, _now(now))
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
        if _lookup_uuid(article_id) is None:
            return []
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

    def _bump_revision(self, connection: Any, article_id: uuid.UUID, now: datetime) -> None:
        """Move the number a learner's cached copy revalidates against.

        Written inside the caller's transaction, so the change and the reason
        to refetch it land together. An approved target is learner-visible -
        it is in the detail read - which is why a decision about one counts as
        a content change and not only as review bookkeeping.
        """
        connection.execute(
            update(ReadingArticle)
            .where(ReadingArticle.id == article_id)
            .values(
                content_revision=ReadingArticle.content_revision + 1,
                updated_at=now,
            )
        )

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
