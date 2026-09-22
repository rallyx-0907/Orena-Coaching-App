"""Reading Content Engine - six tables behind Admin -> Content -> Reading.

PROPOSED - not yet reviewed. Additive only; no existing table is altered and
no existing row is rewritten. Alembic does not read this directory (see its
`README.md`), so nothing here is applied by being committed: it becomes real
by one `git mv` into `versions/`, after the independent architecture review
and the human schema/runtime authorization this docstring names.

Chain position: revises `20260916_0009` (`reading_library`), the head of
`migrations/versions/` on `admin/control-center`. `codex/work` has since
added `0010`, `0011` and `0012` of its own; this file is deliberately
numbered `20260922_0010` by date rather than by sequence, and integrating the
two lanes will need one Alembic merge or a rebase of this revision onto that
lane's head. That is a recorded integration dependency
(`docs/project/READING_CONTENT_ENGINE_SCHEMA_REVIEW_REQUEST.md` SS8), not a
reason to merge the other lane into this one.

Revision ID: 20260922_0010
Revises: 20260916_0009

## What this is, and what it is not

This is shared, platform-owned *content* persistence - an admin ingests a
text, an admin reviews it, every learner reads the published result. It is
not learner-owned data: no reading position, no highlight, no per-learner
progress, no account relationship. The persistence hold `AGENTS.md` SS7
reserves for learner/account architecture is therefore untouched, the same
reasoning `20260916_0008`/`20260916_0009` already recorded for their own
catalogs.

It also does not replace `reading_books`/`reading_book_chapters`. A book is a
whole work the learner reads chapter by chapter; an article is one short text
admitted through a review queue. They are two catalogs with two lifecycles
and no foreign key between them, and this migration adds nothing to either
existing table.

## Why six tables rather than one

- `reading_sources` is where content comes from, including its rights and
  polling state. One row per source, edited over time - mutable.
- `reading_source_items` is the immutable original snapshot. Never rewritten;
  a changed source produces a new revision row pointing back at the previous
  one, so "the source changed under us" is detectable instead of silent.
- `reading_articles` is the learner-oriented processed version, which an
  admin edits and publishes. Separating it from the snapshot is what lets the
  original stay immutable while the article is corrected.
- `reading_article_targets` is 3-8 learning targets per article, machine
  suggested and admin approved separately. A child table rather than JSON
  because the admin reviews, reorders, approves and rejects them one by one,
  and because a future "which articles teach this collocation" query is a
  join, not a JSON scan.
- `reading_review_events` is the admin's own decision history, kept next to
  the article it belongs to. `audit_logs` remains the platform audit trail
  and every mutation still writes there; this table is what the Review Queue
  renders as "what happened to this article", which is a product surface, not
  an audit export.
- `reading_ingestion_jobs` is the durable queue. It is a table because the
  requirement is that a restart loses nothing - an in-memory registry (what
  `media_fallback.py` uses today) cannot satisfy that.

## Job claiming, stated explicitly

The worker claims work with a single atomic statement, never read-then-write:

    UPDATE reading_ingestion_jobs SET status='running', ...
    WHERE id = (SELECT id FROM reading_ingestion_jobs
                WHERE status='queued' AND next_retry_at <= now()
                ORDER BY created_at, id
                FOR UPDATE SKIP LOCKED LIMIT 1)
    RETURNING id

`FOR UPDATE SKIP LOCKED` is why `ix_reading_jobs_claim` exists and why it is
ordered `(status, next_retry_at, created_at)`: the claim query filters on the
first two and orders by the third, so one index serves it whatever the queue
depth. A crashed worker leaves a row in `running` with a `heartbeat_at` that
stops advancing; the reaper returns those to `queued` after
`stale_after`, which is why `heartbeat_at` is a column and not a log line.

## Index rationale - one endpoint each, no speculative indexes

| Index | The query it exists for |
| --- | --- |
| `ix_reading_articles_published` | learner list: `status='published' AND language=? ORDER BY published_at DESC, id DESC` |
| `ix_reading_articles_published_level` | learner list filtered by effective level |
| `ix_reading_articles_published_topic` | learner list filtered by topic |
| `ix_reading_articles_queue` | admin Review Queue: `status IN (...) ORDER BY created_at DESC` |
| `ix_reading_articles_source_item` | "which article came from this snapshot" |
| `uq_reading_source_items_native` | dedupe by `(source_id, source_native_id)` |
| `uq_reading_source_items_hash` | dedupe by exact content hash within a source |
| `ix_reading_source_items_canonical` | dedupe by canonical URL, and revision lookup |
| `ix_reading_jobs_claim` | the worker claim above |
| `ix_reading_jobs_recent` | admin Imports list, newest first |
| `ix_reading_targets_article` | targets of one article, in rank order |
| `ix_reading_review_events_article` | one article's decision history |

`effective_level` is deliberately a stored column maintained by the
repository (`reviewed_level` when an admin set one, else `estimated_level`),
not a view or an expression index: the learner list filters on it, and
`estimated_level` must stay exactly as the processor computed it
(spec SS17). Nothing overwrites `estimated_level` after insert.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260922_0010"
down_revision = "20260916_0009"
branch_labels = None
depends_on = None

# Literal lists, never imported from application code: a migration must not
# depend on code that can change under it after it has been applied - the
# same rule every migration in this chain already follows.
SOURCE_TYPES = ("manual", "direct_url", "file", "rss", "api", "feed")
SOURCE_STATES = (
    "discovered",
    "needs_review",
    "approved",
    "active",
    "paused",
    "blocked",
    "rejected",
    "archived",
)
ARTICLE_STATUSES = (
    "draft",
    "processing",
    "needs_review",
    "ready",
    "published",
    "unpublished",
    "rejected",
    "archived",
)
JOB_STATUSES = ("queued", "running", "completed", "failed", "cancelled")
JOB_STAGES = (
    "queued",
    "fetching",
    "normalizing",
    "deduplicating",
    "analyzing",
    "building_candidate",
    "done",
)
TARGET_TYPES = (
    "word",
    "phrase",
    "phrasal_verb",
    "collocation",
    "expression",
    "grammar_pattern",
    "topic_term",
)


def _in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    # ---- 1. Where content comes from --------------------------------------
    op.create_table(
        "reading_sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("base_url", sa.String(600), nullable=False, server_default=""),
        sa.Column("state", sa.String(20), nullable=False, server_default="needs_review"),
        # Languages a source is expected to produce. A list, because one feed
        # can carry both of Orena's first-class languages; the article's own
        # `language` is what the learner list filters on, never this.
        sa.Column("languages", sa.JSON(), nullable=False),
        sa.Column("topic_hints", sa.JSON(), nullable=False),
        # Rights are columns, not JSON: the admission gate reads them one by
        # one and a future rights report has to be able to filter on them.
        sa.Column("automation_allowed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("can_republish", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("can_adapt", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("attribution_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("license_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("polling_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("polling_policy", sa.JSON(), nullable=False),
        sa.Column("polling_cursor", sa.String(600), nullable=False, server_default=""),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=False, server_default=""),
        sa.Column("approved_by", sa.String(255), nullable=False, server_default=""),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"source_type IN ({_in_list(SOURCE_TYPES)})", name="ck_reading_source_type"
        ),
        sa.CheckConstraint(f"state IN ({_in_list(SOURCE_STATES)})", name="ck_reading_source_state"),
        # A source may not poll unless an admin approved it and the rights
        # answer says automation is allowed. The application checks this too;
        # this constraint is what makes the check impossible to forget.
        sa.CheckConstraint(
            "polling_enabled = false OR (state = 'active' AND automation_allowed = true)",
            name="ck_reading_source_polling_requires_approval",
        ),
        sa.UniqueConstraint("slug", name="uq_reading_source_slug"),
    )
    op.create_index("ix_reading_sources_state", "reading_sources", ["state", "source_type"])

    # ---- 2. The immutable original snapshot -------------------------------
    op.create_table(
        "reading_source_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "source_id",
            sa.Uuid(),
            sa.ForeignKey("reading_sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # RESTRICT, not CASCADE: a snapshot is the evidence behind a published
        # article. Deleting a source must not be able to erase what a learner
        # is currently reading - the source is archived instead.
        sa.Column("source_native_id", sa.String(400), nullable=False, server_default=""),
        sa.Column("canonical_url", sa.String(1000), nullable=False, server_default=""),
        sa.Column("original_title", sa.String(500), nullable=False, server_default=""),
        sa.Column("original_author", sa.String(300), nullable=False, server_default=""),
        sa.Column("original_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("original_language", sa.String(20), nullable=False, server_default=""),
        # The extracted plain text, kept in the row rather than the asset
        # store: it is bounded (SS33's fetch limit), it is what dedupe and the
        # processor read, and it must be in the same transaction as its hash.
        # It is never part of a list projection - see SS46.2.
        sa.Column("original_content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("rights_snapshot_json", sa.JSON(), nullable=False),
        # A changed source never overwrites: revision 2 points at revision 1.
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "supersedes_id",
            sa.Uuid(),
            sa.ForeignKey("reading_source_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("revision >= 1", name="ck_reading_source_item_revision"),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_reading_source_item_hash"),
    )
    # Dedupe key 1: the source's own id for the item. Partial, because
    # `source_native_id` is empty for a manual paste and empty is not an
    # identity - two pasted texts are not "the same item".
    op.create_index(
        "uq_reading_source_items_native",
        "reading_source_items",
        ["source_id", "source_native_id"],
        unique=True,
        postgresql_where=sa.text("source_native_id <> ''"),
    )
    # Dedupe key 2: exact content within one source. If a source later
    # reverts to bytes it published before, that is the same item and
    # resolves to the existing row rather than a third revision - which is
    # what "idempotent" has to mean for content that moves back and forth.
    op.create_index(
        "uq_reading_source_items_hash",
        "reading_source_items",
        ["source_id", "content_hash"],
        unique=True,
    )
    op.create_index(
        "ix_reading_source_items_canonical",
        "reading_source_items",
        ["canonical_url"],
        postgresql_where=sa.text("canonical_url <> ''"),
    )

    # ---- 3. The learner-oriented article ----------------------------------
    op.create_table(
        "reading_articles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "source_item_id",
            sa.Uuid(),
            sa.ForeignKey("reading_source_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("excerpt", sa.String(400), nullable=False, server_default=""),
        sa.Column("language", sa.String(20), nullable=False),
        sa.Column("topic", sa.String(120), nullable=False, server_default=""),
        sa.Column("subtopic", sa.String(120), nullable=False, server_default=""),
        # Never overwritten after insert (SS17). An admin correction writes
        # `reviewed_level`; `effective_level` is what the learner list reads.
        sa.Column("estimated_level", sa.String(20), nullable=False, server_default=""),
        sa.Column("estimated_level_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("reviewed_level", sa.String(20), nullable=True),
        sa.Column("effective_level", sa.String(20), nullable=False, server_default=""),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reading_time_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_adapted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("adaptation_json", sa.JSON(), nullable=False),
        sa.Column("analysis_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("rejection_reason", sa.Text(), nullable=False, server_default=""),
        # Bumped on every published-content change so an ETag can revalidate
        # cheaply (SS46.9).
        sa.Column("content_revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unpublished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            f"status IN ({_in_list(ARTICLE_STATUSES)})", name="ck_reading_article_status"
        ),
        sa.CheckConstraint("word_count >= 0", name="ck_reading_article_word_count"),
        sa.CheckConstraint("content_revision >= 1", name="ck_reading_article_revision"),
        sa.CheckConstraint(
            "estimated_level_confidence >= 0 AND estimated_level_confidence <= 1",
            name="ck_reading_article_confidence",
        ),
        # A published article must carry the timestamp the learner list orders
        # by. Without this, one bad write silently produces an article that
        # can never appear in a cursor-paginated page.
        sa.CheckConstraint(
            "status <> 'published' OR published_at IS NOT NULL",
            name="ck_reading_article_published_at",
        ),
        # One article per snapshot: re-running the same input cannot produce a
        # second candidate (SS16 idempotency), enforced in the database rather
        # than by the pipeline remembering to check.
        sa.UniqueConstraint("source_item_id", name="uq_reading_article_source_item"),
    )
    op.create_index(
        "ix_reading_articles_published",
        "reading_articles",
        ["language", "published_at"],
        postgresql_where=sa.text("status = 'published'"),
    )
    op.create_index(
        "ix_reading_articles_published_level",
        "reading_articles",
        ["language", "effective_level", "published_at"],
        postgresql_where=sa.text("status = 'published'"),
    )
    op.create_index(
        "ix_reading_articles_published_topic",
        "reading_articles",
        ["language", "topic", "published_at"],
        postgresql_where=sa.text("status = 'published'"),
    )
    op.create_index("ix_reading_articles_queue", "reading_articles", ["status", "created_at"])
    op.create_index("ix_reading_articles_source_item", "reading_articles", ["source_item_id"])

    # ---- 4. Learning targets ----------------------------------------------
    op.create_table(
        "reading_article_targets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "article_id",
            sa.Uuid(),
            sa.ForeignKey("reading_articles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # CASCADE, unlike the snapshot: a target has no meaning without its
        # article, and an article is never hard-deleted in normal workflow
        # (SS21) - this only matters for an admin-initiated purge.
        sa.Column("text", sa.String(300), nullable=False),
        sa.Column("canonical_form", sa.String(300), nullable=False, server_default=""),
        sa.Column("target_type", sa.String(30), nullable=False),
        sa.Column("context", sa.Text(), nullable=False, server_default=""),
        sa.Column("meaning", sa.Text(), nullable=False, server_default=""),
        sa.Column("estimated_level", sa.String(20), nullable=False, server_default=""),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="0"),
        # Suggestion and approval are separate facts, never one flag: the
        # admin's decision has to survive a re-run of the processor (SS19).
        sa.Column("machine_suggested", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("admin_approved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("admin_rejected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"target_type IN ({_in_list(TARGET_TYPES)})", name="ck_reading_target_type"
        ),
        sa.CheckConstraint("rank >= 0", name="ck_reading_target_rank"),
        sa.CheckConstraint(
            "NOT (admin_approved AND admin_rejected)", name="ck_reading_target_decision"
        ),
        sa.UniqueConstraint("article_id", "canonical_form", name="uq_reading_target_form"),
    )
    op.create_index(
        "ix_reading_targets_article", "reading_article_targets", ["article_id", "rank"]
    )

    # ---- 5. The admin's decision history ----------------------------------
    op.create_table(
        "reading_review_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "article_id",
            sa.Uuid(),
            sa.ForeignKey("reading_articles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("actor", sa.String(255), nullable=False, server_default=""),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("changes_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_reading_review_events_article", "reading_review_events", ["article_id", "created_at"]
    )

    # ---- 6. The durable queue ---------------------------------------------
    op.create_table(
        "reading_ingestion_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_type", sa.String(40), nullable=False),
        sa.Column(
            "source_id",
            sa.Uuid(),
            sa.ForeignKey("reading_sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # The submitted input. Text and URL are bounded by SS33's limits; a
        # file upload is stored by `BookAssetStore` and referenced by key, so
        # binary never lands in a row (SS46.10).
        sa.Column("input_json", sa.JSON(), nullable=False),
        sa.Column("input_asset_key", sa.String(400), nullable=False, server_default=""),
        # The idempotency key of the submission itself: SHA-256 of the
        # normalized input. A double-submitted form returns the first job
        # instead of queueing a second one, at the database rather than in the
        # browser's disabled button.
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("stage", sa.String(30), nullable=False, server_default="queued"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("last_error", sa.Text(), nullable=False, server_default=""),
        sa.Column("last_error_code", sa.String(80), nullable=False, server_default=""),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_by", sa.String(120), nullable=False, server_default=""),
        sa.Column(
            "result_source_item_id",
            sa.Uuid(),
            sa.ForeignKey("reading_source_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "result_article_id",
            sa.Uuid(),
            sa.ForeignKey("reading_articles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("result_kind", sa.String(30), nullable=False, server_default=""),
        sa.Column("submitted_by", sa.String(255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(f"status IN ({_in_list(JOB_STATUSES)})", name="ck_reading_job_status"),
        sa.CheckConstraint(f"stage IN ({_in_list(JOB_STAGES)})", name="ck_reading_job_stage"),
        sa.CheckConstraint("attempt >= 0", name="ck_reading_job_attempt"),
        sa.CheckConstraint("max_attempts >= 1", name="ck_reading_job_max_attempts"),
        sa.UniqueConstraint("request_hash", name="uq_reading_job_request_hash"),
    )
    # The claim query, and only it: filter on status + next_retry_at, order by
    # created_at. Queue depth does not change its cost.
    op.create_index(
        "ix_reading_jobs_claim",
        "reading_ingestion_jobs",
        ["status", "next_retry_at", "created_at"],
    )
    op.create_index("ix_reading_jobs_recent", "reading_ingestion_jobs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_reading_jobs_recent", table_name="reading_ingestion_jobs")
    op.drop_index("ix_reading_jobs_claim", table_name="reading_ingestion_jobs")
    op.drop_table("reading_ingestion_jobs")
    op.drop_index("ix_reading_review_events_article", table_name="reading_review_events")
    op.drop_table("reading_review_events")
    op.drop_index("ix_reading_targets_article", table_name="reading_article_targets")
    op.drop_table("reading_article_targets")
    op.drop_index("ix_reading_articles_source_item", table_name="reading_articles")
    op.drop_index("ix_reading_articles_queue", table_name="reading_articles")
    op.drop_index("ix_reading_articles_published_topic", table_name="reading_articles")
    op.drop_index("ix_reading_articles_published_level", table_name="reading_articles")
    op.drop_index("ix_reading_articles_published", table_name="reading_articles")
    op.drop_table("reading_articles")
    op.drop_index("ix_reading_source_items_canonical", table_name="reading_source_items")
    op.drop_index("uq_reading_source_items_hash", table_name="reading_source_items")
    op.drop_index("uq_reading_source_items_native", table_name="reading_source_items")
    op.drop_table("reading_source_items")
    op.drop_index("ix_reading_sources_state", table_name="reading_sources")
    op.drop_table("reading_sources")
