"""Reading Library catalog - `reading_books` and `reading_book_chapters`.

PROPOSED - not yet reviewed. Additive only; no existing table is altered.
Two tables, both new. Deliberately narrow scope, matching the pattern
`I3_SCHEMA_REVIEW_REQUEST.md` already established for `20260911_0006`/
`20260912_0007`: Opus proposes an additive migration here for architecture
review; explicit schema/runtime authorization stays separate and belongs to
the human. Nothing here is applied by moving this file - Alembic does not
read `migrations/proposed/` (see its `README.md`).

Chain position, named rather than hidden: this migration revises
`20260916_0008` (`vocabulary_content_catalog`), a second, independent
proposal that landed in `migrations/proposed/` concurrently and happened to
claim the same next sequential number first. There is no data dependency -
`reading_books`/`reading_book_chapters` have no foreign key into anything
that migration adds - this is a chain-linearity choice only, the same
reasoning `20260912_0007`'s own docstring already used for its position on
top of `20260911_0006`: a single linear head keeps the "point
`version_locations` at both `versions/` and `proposed/`" rehearsal technique
working. If that proposal is revised or renumbered before this one is
approved, rebasing onto its new revision id is a mechanical follow-up, not a
redesign.

Revision ID: 20260916_0009
Revises: 20260916_0008

## Scope and what this explicitly does NOT propose

This is shared, platform-owned content (curated by an admin, read by every
learner) - not learner-owned data, so it does not touch the persistence hold
`ARCHITECTURE_INVARIANTS.md`/`AGENTS.md` reserve for account/multi-user
architecture. It does **not** propose:

- any per-learner relationship to a book (reading position, highlight, note,
  saved vocabulary, spaced repetition). That is `ORENA_COLLECTION_ARCHITECTURE.md`
  §2's `ContentMembership` (I4's package), a separate, already-named owner -
  this proposal only makes sure its own identities (`reading_books.id`,
  `reading_book_chapters.id`) are stable enough for a future `sourceRef` to
  point at without being invalidated by an unrelated change here (see below).
- rights/licensing workflow. Product direction for this round (explicit
  current human instruction, which `docs/project/PROJECT_MEMORY.md`'s
  precedence model places above the written architecture contract) descopes
  rights investigation, approval queues and legal verification entirely for
  this catalog; `reading_books` therefore carries no `rights` column at all -
  a book is admitted the moment its import succeeds. This is a deliberate,
  recorded product decision (`docs/project/DECISION_LOG.md`), not an
  oversight, and it does not touch or weaken the *existing*
  `admittedReading()` rights gate in `static/orena/content/reading-library.js`,
  which continues to govern its own, separate hand-curated catalog exactly as
  before - this schema and that gate are two different code paths that do not
  call each other.
- any object-storage credential or provider. `cover_asset_key`/
  `original_asset_key`/`content_asset_key` are opaque strings a
  `writing_coach.book_asset_store.BookAssetStore` resolves; this migration
  does not know or care whether that is today's filesystem implementation or
  a future S3-compatible one.

## Design decisions this schema exists to serve

**Stable locators, not position.** `id` on both tables is the identity a
future learner-facing reference is meant to point at; `position` is display
order only, and is free to be recomputed by a future re-import without
invalidating anything that recorded a chapter `id`. `reading_books.
content_revision` (default 1, unused by anything in this round's scope) is
reserved so a future locator can detect "captured against an older revision"
instead of silently resolving to replaced content - re-import itself is out
of scope; this column only keeps the door open for it.

**Chapters cascade with their book; accounts do not.** Every other reviewed
migration in this chain scopes a table to `incarnation_id` with
`ON DELETE RESTRICT`, because a deleted *account* must keep denying
reactivation rather than silently losing its history. A book chapter has no
existence independent of its book - deleting a book is expected to delete
its chapters outright, so `reading_book_chapters.book_id` is
`ON DELETE CASCADE`, deliberately not the RESTRICT pattern used elsewhere in
this chain. `imported_by` is a plain string (an admin identity), not a
foreign key - there is no admin-account table this schema should couple
itself to.

**Lifecycle stays a single state, not an import-job tracker.** A
`reading_books` row is written only once its book is fully parsed and every
one of its assets is already stored (`writing_coach/reading_library_api.py`
writes assets, then calls this migration's tables in one transaction) - so
this schema never represents a "processing" or "failed" import; those never
reach the database at all. `status` exists only for a book already fully
imported and later hidden by an admin (`CHECK IN ('ready', 'archived')`);
nothing in this round's scope writes `'archived'` yet.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260916_0009"
down_revision = "20260916_0008"
branch_labels = None
depends_on = None

# Kept as a literal list, not imported from application code - the same
# reasoning every migration in this chain already applies: a migration must
# not depend on code that can change under it after being applied.
BOOK_STATUSES = ("ready", "archived")
SOURCE_KINDS = ("epub",)


def _in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    # ---- 1. One row per fully-imported book -------------------------------
    op.create_table(
        "reading_books",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("author", sa.String(240), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("learning_language", sa.String(8), nullable=False),
        sa.Column("source_kind", sa.String(20), nullable=False),
        # SHA-256 of the exact uploaded file bytes. Reviewer-requested (P2-1):
        # without this, two concurrent or repeated uploads of the same EPUB
        # produce two indistinguishable catalog entries. The UNIQUE constraint
        # is the actual enforcement; the repository's pre-check is only an
        # optimization to skip parsing/asset-writing for the common case.
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="ready"),
        sa.Column("chapter_count", sa.Integer(), nullable=False),
        # Reserved for a future re-import; nothing in this proposal's scope
        # ever writes a value other than the default.
        sa.Column("content_revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("cover_asset_key", sa.String(400), nullable=True),
        sa.Column("original_asset_key", sa.String(400), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported_by", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"status IN ({_in_list(BOOK_STATUSES)})", name="ck_reading_book_status"
        ),
        sa.CheckConstraint(
            f"source_kind IN ({_in_list(SOURCE_KINDS)})", name="ck_reading_book_source_kind"
        ),
        sa.CheckConstraint("chapter_count >= 1", name="ck_reading_book_chapter_count"),
        sa.CheckConstraint("content_revision >= 1", name="ck_reading_book_content_revision"),
        sa.CheckConstraint("word_count >= 0", name="ck_reading_book_word_count"),
    )
    # Partial, not a table-level UniqueConstraint: only a 'ready' row blocks a
    # re-upload of the same bytes. An archived book's hash must be reusable,
    # or archiving (the documented recovery path for a wrong/duplicate
    # import) would permanently block ever re-importing that exact file -
    # reviewer-requested (round 2, P3).
    op.create_index(
        "uq_reading_book_source_hash_ready",
        "reading_books",
        ["source_hash"],
        unique=True,
        postgresql_where=sa.text("status = 'ready'"),
    )
    # Library grid pagination: newest-first within one learning language,
    # only ever over 'ready' rows - the query this proposal's repository
    # actually issues (`reading_library_repository.py:list_books`).
    op.create_index(
        "ix_reading_books_language_status_created",
        "reading_books",
        ["learning_language", "status", "created_at"],
    )

    # ---- 2. One row per chapter, ordered within its book -------------------
    op.create_table(
        "reading_book_chapters",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "book_id",
            sa.Uuid(),
            sa.ForeignKey("reading_books.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        # Best-effort source-derived stability (the EPUB spine itemref's
        # idref) for a future re-import to re-match chapters against -
        # unused by anything in this round's scope; empty string when the
        # source gives nothing usable, never invented.
        sa.Column("chapter_key", sa.String(200), nullable=False, server_default=""),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("content_asset_key", sa.String(400), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("position >= 0", name="ck_reading_chapter_position"),
        sa.CheckConstraint("word_count >= 0", name="ck_reading_chapter_word_count"),
        sa.UniqueConstraint("book_id", "position", name="uq_reading_chapter_position"),
    )
    # Chapter list for Book Detail, in reading order - the unique constraint
    # above already covers (book_id, position); a plain book_id index serves
    # `get_chapter`'s (book_id, id) lookup and any future chapter count query
    # that does not also filter on position.
    op.create_index("ix_reading_chapters_book", "reading_book_chapters", ["book_id"])


def downgrade() -> None:
    op.drop_index("ix_reading_chapters_book", table_name="reading_book_chapters")
    op.drop_table("reading_book_chapters")
    op.drop_index("ix_reading_books_language_status_created", table_name="reading_books")
    op.drop_index("uq_reading_book_source_hash_ready", table_name="reading_books")
    op.drop_table("reading_books")
