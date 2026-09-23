"""A learner's own study set, in the domain that owns studying.

PROPOSED. Not applied anywhere. Independent architecture review is required
before this moves into `migrations/versions/`
(`AGENTS.md`, "Architecture review authority"); the request is
`docs/project/VOCABULARY_DECK_SCHEMA_REVIEW_REQUEST.md`.

--- Why this is not `library_collections` -----------------------------------

The human's decision of 2026-09-23: **a Deck and a My Library Collection are
two different things.** A Deck is a learning/review set that belongs to
Vocabulary; a Collection only organises items inside My Library.

The implementation shipped on 2026-09-23 (`4f7b197`) used
`library_collections` with `kind='word'` as the deck store. That was the wrong
domain, and the two contracts say so independently:

- `ORENA_COLLECTION_ARCHITECTURE.md` §1: "Collection is a query/projection
  across those owners and work, not a new authoritative copy of everything the
  learner has done." A study set is not a projection of anything - it is a
  thing the learner made, and it is authoritative about its own membership.
- `ORENA_VOCABULARY_ARCHITECTURE.md` §1 lists "learner-created collections"
  among what **Vocabulary** must support, beside curated and imported ones.

And the third table nearby is not a candidate either: `vocabulary_collections`
says in its own docstring that "Collections are content, not learner state. A
collection can be imported once and read by many learners" - it has no owner
column and cannot have one.

So a Deck has no home today, and the smallest honest schema is its own pair of
tables in the Vocabulary domain.

--- What the tables are ------------------------------------------------------

`vocabulary_decks` - one row per set the learner made.

- `user_id` + `language_code`: the same ownership scope every learner-owned
  Vocabulary table already uses, so switching language shows that language's
  sets and never copies one into another.
- `title` unique per (user, language): two sets called "Reise" in one language
  is a mistake, not a feature; the same name in two languages is fine.
- `cover`: the frame "Create deck mobile" (25) draws a cover-colour chooser and
  a learner's choice must survive the device. This is a **token**, not a hex
  value - one of a small named set the theme owns - so the palette stays with
  `theme.css` and a stored value can never introduce a colour outside it. A
  check constraint holds the set, which is also how a later palette change is
  forced to be a migration rather than a silent drift.
- `version`: optimistic concurrency, as `library_items` already carries, so two
  tabs renaming one set cannot overwrite each other silently.

`vocabulary_deck_members` - which of the learner's words are in the set.

- `saved_word_id` references `saved_words`, `CASCADE`: a word the learner
  deletes leaves the sets it was in. That is the true relationship - a set is a
  set *of the learner's words*, and there is no membership without the word.
  The undo path (`restore_library_record`) restores the word; restoring its
  memberships is deliberately **not** in this migration, and is named as an
  open question in the review request rather than decided here.
- `(deck_id, saved_word_id)` unique: a word is in a set once.
- `position`: the learner's own order inside a set, which a study session walks.
  Default 0, so an implementation that does not order yet is not lying about
  one.

--- What this migration does not do ------------------------------------------

It does not move, copy or delete anything in `library_collections`. Those rows
are My Library's collections and remain exactly what that domain says they are.
Whether the word-kind collections created by `4f7b197` in dev should be carried
over is a **data** question for the review, not a schema one; the sandbox has a
handful and the honest default is to leave them where they are.

Revision ID: 20260923_0014
Revises: 20260923_0013
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260923_0014"
down_revision = "20260923_0013"
branch_labels = None
depends_on = None

# The covers a learner may choose. Names, not colours: `theme.css` owns what
# each one looks like, and this column only records which one was picked.
COVERS = ("sea", "violet", "ember", "moss", "amber", "rose")
_COVER_LIST = ", ".join(f"'{name}'" for name in COVERS)


def upgrade() -> None:
    op.create_table(
        "vocabulary_decks",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language_code", sa.String(20), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("cover", sa.String(24), nullable=False, server_default="violet"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("title <> ''", name="ck_vocabulary_decks_title"),
        sa.CheckConstraint(f"cover IN ({_COVER_LIST})", name="ck_vocabulary_decks_cover"),
        sa.UniqueConstraint(
            "user_id", "language_code", "title", name="uq_vocabulary_deck_title"
        ),
    )
    op.create_index(
        "ix_vocabulary_decks_scope", "vocabulary_decks", ["user_id", "language_code"]
    )

    op.create_table(
        "vocabulary_deck_members",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "deck_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("vocabulary_decks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "saved_word_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("saved_words.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("deck_id", "saved_word_id", name="uq_vocabulary_deck_member"),
    )
    op.create_index(
        "ix_vocabulary_deck_members_deck",
        "vocabulary_deck_members",
        ["deck_id", "position"],
    )


def downgrade() -> None:
    op.drop_index("ix_vocabulary_deck_members_deck", table_name="vocabulary_deck_members")
    op.drop_table("vocabulary_deck_members")
    op.drop_index("ix_vocabulary_decks_scope", table_name="vocabulary_decks")
    op.drop_table("vocabulary_decks")
