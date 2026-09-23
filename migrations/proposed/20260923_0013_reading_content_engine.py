"""Reading Content Engine - six tables behind Admin -> Content -> Reading.

PROPOSED - reviewed once (`CHANGES REQUIRED`, commit `5eeaac7`), revised, and
awaiting re-review then human schema/runtime authorization. Additive only; no
existing table is altered and no existing row is rewritten. Alembic does not
read this directory (see its `README.md`), so nothing here is applied by being
committed: it becomes real by one `git mv` into `versions/`, after the
re-review and the authorization this docstring names.

Chain position: revises `20260922_0012` (`text_discussions`), the head of
`migrations/versions/` on `admin/control-center` after `codex/work` was merged
into this lane on 2026-09-23. The proposal was first written against
`20260916_0009`, when that was this lane's head and the other lane's `0010`,
`0011` and `0012` were an unmerged dependency; it was rebased rather than
merged with an Alembic merge revision, so the chain stays linear and one
`git mv` still applies it. Nothing in this migration depends on what those
three added - the rebase is chain linearity only, the same reasoning
`20260912_0007` recorded for its own position.

Revision ID: 20260923_0013
Revises: 20260916_0009

## What this is, and what it is not

This is shared, platform-owned *content* persistence - an admin ingests a
text, an admin reviews it, every learner reads the published result. It is
not learner-owned data: no reading position, no highlight, no per-learner
progress, no account relationship, and no foreign key into `users`. The
persistence hold `AGENTS.md` SS7 reserves for learner/account architecture is
therefore untouched, the same reasoning `20260916_0008`/`20260916_0009`
already recorded for their own catalogs.

It also does not replace `reading_books`/`reading_book_chapters`. A book is a
whole work the learner reads chapter by chapter; an article is one short text
admitted through a review queue. They are two catalogs with two lifecycles
and no foreign key between them, and this migration adds nothing to either
existing table.

## Why six tables rather than one

- `reading_sources` is where content comes from, including its rights and
  polling state. One row per source, edited over time - mutable.
- `reading_source_items` is the immutable original snapshot. Never rewritten;
  a changed source supersedes the previous row and points back at it, so
  "the source changed under us" is detectable instead of silent.
- `reading_articles` is the learner-oriented processed version, which an
  admin edits and publishes. Separating it from the snapshot is what lets the
  original stay immutable while the article is corrected.
- `reading_article_targets` is 3-8 learning targets per article, machine
  suggested and admin approved separately. A child table rather than JSON
  because the admin reviews, reorders, approves and rejects them one by one,
  and because a future "which articles teach this collocation" query is a
  join, not a JSON scan.
- `reading_review_events` is the admin's own decision history, rendered as the
  Review Queue's "what happened to this article". It is not folded into
  `audit_logs` for two structural reasons: that table is indexed only on
  `created_at`, so one article's history would be a full scan, and fixing that
  would mean adding an index to a shared platform table - destroying this
  migration's purely-additive property; and `audit_logs.user_id` is a foreign
  key into `users`, so reusing it for a product surface would couple this
  engine to the very account table SS7 reserves. `audit_logs` remains the
  platform audit trail and still receives every mutation - it, not this table,
  is the retention authority, which is why this table may cascade with its
  article (see "Deletes" below).
- `reading_ingestion_jobs` is the durable queue. It is a table because the
  requirement is that a restart loses nothing - an in-memory registry (what
  `media_fallback.py` uses today) cannot satisfy that.

## Job claiming and crash recovery, written out in full

The worker claims work with one atomic statement, never read-then-write. The
outer `WHERE` repeats `status = 'queued'` as defense in depth, so correctness
does not rest on the subquery alone:

    UPDATE reading_ingestion_jobs
       SET status       = 'running',
           stage        = 'fetching',
           attempt      = attempt + 1,
           claimed_by   = :worker_id,
           started_at   = now(),
           heartbeat_at = now()
     WHERE status = 'queued'
       AND id = (SELECT id FROM reading_ingestion_jobs
                  WHERE status = 'queued' AND next_retry_at <= now()
                    AND attempt < max_attempts
                  ORDER BY created_at, id
                  FOR UPDATE SKIP LOCKED LIMIT 1)
    RETURNING id

`attempt < max_attempts` is in the claim's own predicate, not only in the
retry path: the claim is what increments `attempt`, so without it a job on its
last allowed attempt would be claimed once more and violate
`ck_reading_job_attempt_bound` instead of failing cleanly.

The claim sets `heartbeat_at` itself, and `heartbeat_at` is `NOT NULL`, so
there is no window in which a claimed job has no heartbeat and no NULL for a
reaper predicate to miss (the reviewer's P1-4 asked for `COALESCE`; making the
column `NOT NULL` at claim time removes the NULL rather than coalescing it).
A live worker refreshes it as it works.

The reaper returns stranded work and consumes an attempt, so a job that
reliably kills its worker fails instead of cycling forever (P2-10):

    UPDATE reading_ingestion_jobs
       SET status        = CASE WHEN attempt >= max_attempts THEN 'failed' ELSE 'queued' END,
           stage         = CASE WHEN attempt >= max_attempts THEN 'done' ELSE 'queued' END,
           claimed_by    = '',
           last_error_code = 'worker_lost',
           next_retry_at = now(),
           finished_at   = CASE WHEN attempt >= max_attempts THEN now() ELSE NULL END
     WHERE status = 'running' AND heartbeat_at < now() - :stale_after

Retry after an ordinary failure is the same shape with an exponential
`next_retry_at`. `ORDER BY created_at, id` means a retried job is claimed
ahead of newer work once its backoff expires (P2-11): bounded by
`max_attempts` and harmless at `READING_WORKER_CONCURRENCY=1`, recorded here
for whenever concurrency rises.

Admin "Retry" on a `failed` job inserts a **new** job row rather than mutating
the old one, which is why `request_hash` is unique only over live submissions
(see below): the failed attempt keeps its error and its history.

## Immutability, enforced rather than asserted

`reading_source_items` is the evidence behind a published article, so on
PostgreSQL a `BEFORE UPDATE` trigger rejects any change to the snapshot's
content (`original_content`, `content_hash`), its provenance (`source_id`,
`source_native_id`, `canonical_url`, `fetched_at`, `revision`,
`supersedes_id`) and its **rights evidence** (`rights_snapshot_json`) - a
mutable rights snapshot is not a snapshot, and `source_native_id` /
`canonical_url` are part of the dedupe identity, so rewriting one would move a
row into or out of the partial unique index the supersede rule depends on.

`superseded_at` is the one column the trigger leaves writable, because marking
a snapshot superseded is the one legitimate update to it. The descriptive
columns an admin may correct after a mis-parse - `original_title`,
`original_author`, `original_published_at`, `original_language`,
`metadata_json` - stay writable deliberately: "immutable snapshot" here means
content, identity and rights, not every column, and that distinction is
stated rather than left to be discovered.

On any other dialect the same rule is a repository invariant with a test that
proves no `UPDATE` is issued against those columns; the runtime is PostgreSQL,
so the enforcement is real where it matters.

## Supersede, and what happens when a source reverts

The order is forced by the partial unique index and must be one transaction:
**stamp the old row's `superseded_at` first, then insert the new row.** The
reverse collides, because two rows with `superseded_at IS NULL` for one
`(source_id, source_native_id)` is exactly what that index forbids. That is
also what makes two workers racing to supersede the same item safe without
application locking: both try to insert a current row, and the index rejects
the loser.

If a source reverts to bytes it published before, the engine does **not**
insert a third row - `uq_reading_source_items_hash` is `(source_id,
content_hash)` over all rows, so those bytes already have a row. It clears
`superseded_at` on that earlier row and stamps the row that had been current,
in one transaction. The consequence, stated plainly rather than discovered:
`revision` is a **creation-order counter, not a currency rank**, so after a
revert the current row can carry a lower `revision` than a superseded one, and
`supersedes_id` records what a row was created after - never which row is live.
`superseded_at IS NULL` is the only test for "current", everywhere.

One consequence of that, for whoever renders a history: after a revert followed
by a further change, two rows can share one `supersedes_id`, because each
records the row that was current when it was created and the reverted-to row
was current twice. `ck_reading_source_item_chain` permits it deliberately - the
chain is a tree, not a list, and a renderer that walks it expecting a list will
be wrong.

## Deletes

`RESTRICT` upward (item -> source, article -> item, job -> source, item ->
superseded item): nothing may delete the evidence behind something a learner
is reading, and a source with history is archived rather than deleted.
`CASCADE` downward (targets and review events with their article): a target
has no meaning without its article, and `audit_logs` - not
`reading_review_events` - is the retention authority for what an admin did.
Nothing in normal workflow hard-deletes an article; a purge is an explicit
admin action that must write its audit row *before* the delete, because the
review events go with it.

## Index rationale - one query each, no speculative indexes

| Index | The query it exists for |
| --- | --- |
| `ix_reading_sources_state` | admin Sources list: `WHERE state = ? ORDER BY name`, and the worker's "which sources may poll" sweep |
| `uq_reading_source_items_native` | dedupe by `(source_id, source_native_id)` over current (non-superseded) rows |
| `uq_reading_source_items_hash` | dedupe by exact content hash within a source |
| `ix_reading_source_items_canonical` | dedupe by canonical URL, and revision lookup |
| `ix_reading_source_items_hash_any` | review-time "this content already exists, under another source" |
| `ix_reading_articles_published` | learner list: `status='published' AND language=? ORDER BY published_at DESC, id DESC` |
| `ix_reading_articles_published_level` | the same list filtered by effective level |
| `ix_reading_articles_published_topic` | the same list filtered by topic |
| `ix_reading_articles_queue` | admin Review Queue: `status IN (...) ORDER BY created_at DESC` (a multi-value `IN` still sorts; the index bounds the scan, it does not remove the sort) |
| `ix_reading_targets_article` | targets of one article, in rank order |
| `ix_reading_review_events_article` | one article's decision history |
| `ix_reading_jobs_claim` | the claim above: walks `created_at` order *inside* the queued set, stops at the first row passing `next_retry_at` as a filter |
| `ix_reading_jobs_stale` | the reaper above, over `running` rows only |
| `ix_reading_jobs_recent` | admin Imports list, newest first |

"Which article came from this snapshot" needs no index of its own: the
`UNIQUE (source_item_id)` constraint already creates a unique btree on exactly
that column (the reviewer's P2-3; the redundant index is gone).

`effective_level` is deliberately a stored column maintained by the repository
(`reviewed_level` when an admin set one, else `estimated_level`), not a view or
an expression index: the learner list filters on it, and `estimated_level` must
stay exactly as the processor computed it (spec SS17). A CHECK now ties the
three together, so a repository bug or a one-off SQL fix cannot silently
misfile an article at a level nothing can detect.

## Seeded sources

The three built-in input paths are not a source registry entry an admin
creates - they are how manual ingestion reaches the same pipeline as a feed.
This migration therefore seeds exactly three rows with fixed UUIDs, `state =
'active'`, `automation_allowed = false` and polling off. Fixed ids matter:
`uq_reading_source_items_hash` is `(source_id, content_hash)`, so manual
dedupe works only because every manual paste shares one source id. Nothing
else is seeded, and an external recurring source is still created by an admin
and still starts at `needs_review`.

## Rollback

`downgrade()` drops six tables that may by then hold published, learner-visible
content. Its order is correct (jobs -> review events -> targets -> articles ->
source items -> sources), but it is a development-time reversal only: it must
never be run against a runtime with published articles. Unpublish and export
first, or do not run it.
"""
from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa

revision = "20260923_0013"
down_revision = "20260922_0012"
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

# The three built-in input paths, seeded below. Fixed so the dedupe key
# `(source_id, content_hash)` is deterministic across environments.
BUILT_IN_SOURCES = (
    (uuid.UUID("0a52e5d0-0000-4000-8000-000000000001"), "orena-manual", "Manual paste", "manual"),
    (uuid.UUID("0a52e5d0-0000-4000-8000-000000000002"), "orena-direct-url", "Direct URL", "direct_url"),
    (uuid.UUID("0a52e5d0-0000-4000-8000-000000000003"), "orena-file-upload", "File upload", "file"),
)

# OR REPLACE so a re-run after a partially failed migration is not blocked by
# the function it created last time. ERRCODE 23514 (check_violation) rather
# than plpgsql's default P0001, so the repository can recognise *this*
# refusal and turn it into a clear admin message instead of a generic error.
# No `:` appears anywhere in the body: Alembic wraps this in `text()`, which
# would otherwise read `:name` as a bind parameter - which is also why the
# rights comparison is written `CAST(x AS text)` rather than `x::text`.
#
# That comparison is a cast, not an oversight: PostgreSQL's `json` type has no
# equality operator, so `NEW.rights_snapshot_json IS DISTINCT FROM OLD...`
# raises `operator does not exist: json = json` at *runtime* - which would have
# made this trigger reject every update to the table, including the one legal
# `superseded_at` stamp. The rehearsal caught it.
#
# The textual comparison is the right semantics, not a tolerated side effect,
# so do not "fix" this to `jsonb` for its native `=`. `json` stores the exact
# input text - whitespace, key order and duplicate keys preserved - so
# `CAST(json AS text)` compares the bytes as stored, and byte-identity is what
# "unchanged" has to mean for a column whose whole purpose is evidence. It
# fails closed: the cost is that a writer which re-serialises the value with a
# different key order is refused although the meaning did not change, which is
# why every write to this table must be a targeted `UPDATE ... SET
# superseded_at = ...` and never a whole-row write or an ORM merge.
_IMMUTABLE_SNAPSHOT_FUNCTION = """
CREATE OR REPLACE FUNCTION reading_source_item_is_immutable() RETURNS trigger AS $func$
BEGIN
    IF NEW.source_id IS DISTINCT FROM OLD.source_id
       OR NEW.original_content IS DISTINCT FROM OLD.original_content
       OR NEW.content_hash IS DISTINCT FROM OLD.content_hash
       OR NEW.fetched_at IS DISTINCT FROM OLD.fetched_at
       OR NEW.revision IS DISTINCT FROM OLD.revision
       OR CAST(NEW.rights_snapshot_json AS text)
          IS DISTINCT FROM CAST(OLD.rights_snapshot_json AS text)
       OR NEW.source_native_id IS DISTINCT FROM OLD.source_native_id
       OR NEW.canonical_url IS DISTINCT FROM OLD.canonical_url
       OR NEW.supersedes_id IS DISTINCT FROM OLD.supersedes_id
    THEN
        RAISE EXCEPTION
            'reading_source_items is an immutable snapshot: supersede it instead of rewriting it'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$func$ LANGUAGE plpgsql;
"""

_IMMUTABLE_SNAPSHOT_TRIGGER = """
CREATE TRIGGER reading_source_item_immutable
    BEFORE UPDATE ON reading_source_items
    FOR EACH ROW EXECUTE FUNCTION reading_source_item_is_immutable();
"""


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
        # Consequence, named rather than discovered later: pausing a source
        # (state -> 'paused') forces `polling_enabled` false, so resuming is an
        # explicit re-enable, not an automatic resumption of a remembered
        # intent. That is the safer default for something that fetches.
        sa.CheckConstraint(
            "NOT polling_enabled OR (state = 'active' AND automation_allowed)",
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
        # A changed source never overwrites. The new snapshot points back with
        # `supersedes_id`, and the old one is stamped `superseded_at` - which
        # is what keeps the "one current item per native id" index enforceable
        # while the history stays readable.
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "supersedes_id",
            sa.Uuid(),
            sa.ForeignKey("reading_source_items.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("revision >= 1", name="ck_reading_source_item_revision"),
        # A later revision always records what it was created after; the
        # first never does. Without this, revision 5 with a NULL
        # `supersedes_id` is a chain with no way back.
        sa.CheckConstraint(
            "(revision > 1) = (supersedes_id IS NOT NULL)",
            name="ck_reading_source_item_chain",
        ),
        # Length *and* case: an uppercase SHA-256 of identical bytes is a
        # different value under the dedupe key, which would silently defeat it.
        sa.CheckConstraint(
            "length(content_hash) = 64 AND content_hash = lower(content_hash)",
            name="ck_reading_source_item_hash",
        ),
    )
    # Dedupe key 1: the source's own id for the item, over *current* rows only,
    # so revision 2 can exist while "one live item per native id" still holds.
    # Partial on `source_native_id <> ''` as well, because an empty native id
    # (a manual paste) is not an identity - two pasted texts are not the same
    # item. A re-fetch resolves to the row with `superseded_at IS NULL`.
    op.create_index(
        "uq_reading_source_items_native",
        "reading_source_items",
        ["source_id", "source_native_id"],
        unique=True,
        postgresql_where=sa.text("source_native_id <> '' AND superseded_at IS NULL"),
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
    # Not unique, and deliberately not scoped to a source: identical bytes
    # ingested under two sources are two legitimate snapshots (rights differ
    # per source), but the review UI has to be able to say so before an admin
    # publishes the second one.
    op.create_index("ix_reading_source_items_hash_any", "reading_source_items", ["content_hash"])
    # `get_context()`, not `get_bind()`: offline mode (`alembic upgrade --sql`,
    # the natural way for a human to read this DDL before authorizing it) has
    # no bind at all, and `get_bind().dialect` would raise before rendering a
    # single statement.
    if op.get_context().dialect.name == "postgresql":
        op.execute(_IMMUTABLE_SNAPSHOT_FUNCTION)
        op.execute(_IMMUTABLE_SNAPSHOT_TRIGGER)

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
        # The learner list filters on `effective_level`, so it may not drift
        # from the two columns it is derived from, and an unset reviewed level
        # is NULL - never the empty string, which would be a second sentinel.
        sa.CheckConstraint(
            "effective_level = COALESCE(reviewed_level, estimated_level)",
            name="ck_reading_article_effective_level",
        ),
        sa.CheckConstraint(
            "reviewed_level IS NULL OR reviewed_level <> ''",
            name="ck_reading_article_reviewed_level",
        ),
        # One article per snapshot: re-running the same input cannot produce a
        # second candidate *for that snapshot* (SS16 idempotency), enforced in
        # the database rather than by the pipeline remembering to check. This
        # constraint's unique btree is also the "which article came from this
        # snapshot" index, so no second index exists for it.
        sa.UniqueConstraint("source_item_id", name="uq_reading_article_source_item"),
    )
    # `id` is the third column in each of the three published indexes because
    # the learner list paginates on the keyset `(published_at, id)` - without
    # it the tiebreak falls to a filter instead of an index bound.
    op.create_index(
        "ix_reading_articles_published",
        "reading_articles",
        ["language", "published_at", "id"],
        postgresql_where=sa.text("status = 'published'"),
    )
    op.create_index(
        "ix_reading_articles_published_level",
        "reading_articles",
        ["language", "effective_level", "published_at", "id"],
        postgresql_where=sa.text("status = 'published'"),
    )
    op.create_index(
        "ix_reading_articles_published_topic",
        "reading_articles",
        ["language", "topic", "published_at", "id"],
        postgresql_where=sa.text("status = 'published'"),
    )
    op.create_index("ix_reading_articles_queue", "reading_articles", ["status", "created_at"])

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
    )
    # Partial, for the same reason the native-id index is: an empty canonical
    # form is not an identity. A full unique constraint here would cap an
    # article at one uncanonicalized target and break the 3-8 target workflow
    # the first time the processor could not canonicalize two of them.
    op.create_index(
        "uq_reading_target_form",
        "reading_article_targets",
        ["article_id", "canonical_form"],
        unique=True,
        postgresql_where=sa.text("canonical_form <> ''"),
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
        # binary never lands in a row (SS46.10). The JSON columns in this
        # migration are deliberately NOT NULL with no server default: a writer
        # must say what it means, and `{}` is a statement, not a default.
        sa.Column("input_json", sa.JSON(), nullable=False),
        sa.Column("input_asset_key", sa.String(400), nullable=False, server_default=""),
        # The idempotency key of the submission: SHA-256 over the *canonical*
        # input - source id, kind, canonical URL, text fingerprint, file
        # digest and declared language. Unique only over live submissions, so
        # a double-submitted form returns the first job while a text whose
        # earlier job failed or was cancelled can be submitted again; admin
        # Retry inserts a new row and the failed one keeps its history.
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("stage", sa.String(30), nullable=False, server_default="queued"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("last_error", sa.Text(), nullable=False, server_default=""),
        sa.Column("last_error_code", sa.String(80), nullable=False, server_default=""),
        sa.Column(
            "next_retry_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        # NOT NULL with a default, and set again by the claim: there is no
        # window in which a running job has no heartbeat, so the reaper needs
        # no COALESCE and cannot miss a stranded row to a NULL.
        sa.Column(
            "heartbeat_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
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
        # A job may never be claimed more times than it is allowed to be: the
        # reaper and the retry path both consume an attempt, and this is what
        # makes "a job that kills its worker fails" a fact rather than a hope.
        sa.CheckConstraint("attempt <= max_attempts", name="ck_reading_job_attempt_bound"),
    )
    op.create_index(
        "uq_reading_job_request_hash",
        "reading_ingestion_jobs",
        ["request_hash"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )
    # The claim query, and only it. Partial on the queued set so the scan
    # walks `created_at` order directly and stops at the first due row -
    # `next_retry_at` is a *filter* here, never an index bound, because a
    # range predicate before the sort column would destroy that ordering.
    op.create_index(
        "ix_reading_jobs_claim",
        "reading_ingestion_jobs",
        ["created_at", "id"],
        postgresql_where=sa.text("status = 'queued'"),
    )
    # The reaper, over running rows only.
    op.create_index(
        "ix_reading_jobs_stale",
        "reading_ingestion_jobs",
        ["heartbeat_at"],
        postgresql_where=sa.text("status = 'running'"),
    )
    op.create_index("ix_reading_jobs_recent", "reading_ingestion_jobs", ["created_at"])

    # ---- 7. The three built-in input paths --------------------------------
    # Three notes for whoever edits these, none of them obvious:
    #
    # * `CURRENT_TIMESTAMP`, not `now()`: standard SQL, valid on every dialect
    #   this repository might rehearse on, still the server's clock.
    # * `created_by` reads `migration 20260923_0013` with a space, not a colon.
    #   Alembic wraps `op.execute` strings in `text()`, and SQLAlchemy reads
    #   `:` followed by word characters - digits included - as a bind parameter.
    # * The ids render in their dashed form, which is what PostgreSQL's `uuid`
    #   type expects. On a non-native backend `sa.Uuid()` stores `value.hex`
    #   instead, so these literals would not match what the ORM writes; that is
    #   another reason this migration targets the PostgreSQL runtime it names.
    #   `BUILT_IN_SOURCES` names must also stay apostrophe-free.
    #
    # Written as literal statements rather than `op.bulk_insert`: offline mode
    # (`alembic upgrade --sql`, the natural way for a human to read this DDL
    # before authorizing it) renders parameters as literals, and SQLAlchemy has
    # no literal renderer for a JSON value - `bulk_insert` with a JSON column
    # therefore fails to render at all. Literal SQL renders identically in both
    # modes, and `now()` is the server's clock rather than the client's.
    #
    # 'active' because an admin submitting a text through the console *is* the
    # approval for these three; an external recurring source still starts at
    # 'needs_review'. Polling stays off and `automation_allowed` keeps its
    # false default, so `ck_reading_source_polling_requires_approval` holds.
    for source_id, slug, name, source_type in BUILT_IN_SOURCES:
        op.execute(
            "INSERT INTO reading_sources "
            "(id, slug, name, source_type, state, languages, topic_hints, polling_policy, "
            " created_by, created_at, updated_at) VALUES "
            f"('{source_id}', '{slug}', '{name}', '{source_type}', 'active', "
            """'["en", "zh"]', '[]', '{}', 'migration 20260923_0013',
             CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"""
        )


def downgrade() -> None:
    """Development-time reversal only - see "Rollback" in the module docstring."""
    op.drop_index("ix_reading_jobs_recent", table_name="reading_ingestion_jobs")
    op.drop_index("ix_reading_jobs_stale", table_name="reading_ingestion_jobs")
    op.drop_index("ix_reading_jobs_claim", table_name="reading_ingestion_jobs")
    op.drop_index("uq_reading_job_request_hash", table_name="reading_ingestion_jobs")
    op.drop_table("reading_ingestion_jobs")
    op.drop_index("ix_reading_review_events_article", table_name="reading_review_events")
    op.drop_table("reading_review_events")
    op.drop_index("ix_reading_targets_article", table_name="reading_article_targets")
    op.drop_index("uq_reading_target_form", table_name="reading_article_targets")
    op.drop_table("reading_article_targets")
    op.drop_index("ix_reading_articles_queue", table_name="reading_articles")
    op.drop_index("ix_reading_articles_published_topic", table_name="reading_articles")
    op.drop_index("ix_reading_articles_published_level", table_name="reading_articles")
    op.drop_index("ix_reading_articles_published", table_name="reading_articles")
    op.drop_table("reading_articles")
    if op.get_context().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS reading_source_item_immutable ON reading_source_items")
        op.execute("DROP FUNCTION IF EXISTS reading_source_item_is_immutable()")
    op.drop_index("ix_reading_source_items_hash_any", table_name="reading_source_items")
    op.drop_index("ix_reading_source_items_canonical", table_name="reading_source_items")
    op.drop_index("uq_reading_source_items_hash", table_name="reading_source_items")
    op.drop_index("uq_reading_source_items_native", table_name="reading_source_items")
    op.drop_table("reading_source_items")
    op.drop_index("ix_reading_sources_state", table_name="reading_sources")
    op.drop_table("reading_sources")
