"""The learner's own library, and the identity a saved word points at.

PROPOSED. Not reviewed, not authorized, not applied. This file sits in
`migrations/proposed/`, which Alembic does not read; the live head on this lane
is `20260922_0012`. The review request is
`docs/project/MY_LIBRARY_SCHEMA_REVIEW_REQUEST.md`; the design it serves is
`docs/product/ORENA_COLLECTION_ARCHITECTURE.md` §2 and the audit
`docs/project/MY_LIBRARY_DATA_CONTRACT_AUDIT.md`.

Two things are blocked today and this is the smallest schema that unblocks
them.

--- A. A saved word does not know which catalogue entry it is -----------------

`saved_words` copies the catalogue's fields and is re-joined to it at read time
by normalised text. Text is not identity: `vocabulary_entries` distinguishes
senses and readings (`identity_key`, `sense_key`, `readings`) and the text join
throws that away. For Chinese this is not a refinement - 行 is xíng or háng,
重 is zhòng or chóng, and a saved word joined by characters alone cannot say
which one the learner kept. Per-word pronunciation audio has to be keyed to a
reading, so it cannot be built on top of the text join either.

Three columns, all nullable-by-default and additive:

- `entry_id` is the live link, `SET NULL` so re-importing or retiring a
  catalogue entry never deletes a learner's word;
- `entry_identity_key` is the durable one. The catalogue is re-importable, so
  the row that `entry_id` points at can be replaced by an equal one with a new
  UUID; the identity key is what survives that, and what a later audio record
  is keyed by. It is kept denormalised on purpose: it is a learner-facing
  identity, not a foreign key;
- `reading_key` is which reading of that entry the learner kept - the one thing
  the text join can never recover.

`ck_saved_words_entry_identity` holds that a row with a live link always
carries the durable key, so nothing can arrive linked but unidentifiable. The
reverse is allowed: a word saved before the catalogue had it, or saved by hand,
carries a key with no `entry_id`, and a word that is in no catalogue at all
carries neither. Nothing is backfilled here (see the review request, "What this
migration does not do").

`reading_key` is not constrained against `vocabulary_entries.readings`: that
column is JSON and no portable constraint can read it. It is an application
invariant, and the review request says where it is enforced.

--- B. Nothing records that a learner kept something ------------------------

Thư viện của tôi is one library over eight kinds. Only saved words have any
record of being kept; a passage, a take, an essay, a book has none, and there
is nowhere to pin an item, note it, or put it in a collection.

`library_items` is `ContentMembership` from the Collection Architecture: the
learner's *relationship* to a thing, never a copy of it. There is no body, no
title and no snippet in it - those stay with the owner and are read through
`source_id`, or through `saved_word_id` for a word.

It deliberately holds **no review schedule**. Words are scheduled in
`saved_words` and that stays true; inventing a second scheduler here is exactly
the duplication this table exists to avoid, and what a schedule would even mean
for a passage or a recording is a product question nobody has answered. What
this round gives the merged queue the frame draws is `pinned_at` - "mục bạn
đánh dấu lên trước, sau đó theo hạn SRS" - which is the ordering the design
asks for, over the schedules that already exist.

`state` is a nullable override, not a duplicate: NULL means "whatever the owner
says", which for a word is its `review_stage`. A learner who marks something
learned or still-learning writes it here, and only then does it differ.

Two shapes are load-bearing:

- **A word is linked, not named.** `saved_word_id` with `ON DELETE CASCADE`,
  under a biconditional check with `kind = 'word'`: deleting the word removes
  the relationship with it, and no word row can drift to a `source_id` string
  that means nothing. Every other kind carries `source_id`, the same routing
  identity the app already opens things with, and `ck_library_items_source`
  holds that it is non-empty.
- **One collection, one kind, in the database.** The frame says "mỗi bộ một
  loại". `library_collections` and `library_items` each carry a redundant
  `UNIQUE (id, kind)`, and `library_collection_members` carries `kind` and
  references both by `(id, kind)`. A membership whose collection and item
  disagree about the kind cannot be written at all, rather than being caught by
  whichever code path remembers to check.

Uniqueness is split because words are keyed differently from everything else:
one partial unique index per case, rather than one constraint over a column
that is empty for a whole kind.

Downgrade drops the three tables and the three columns. It exists for a
rehearsal, not for a live account: it destroys every kept relationship and
every collection, and it forgets which entry each saved word pointed at.

Revision ID: 20260923_0013
Revises: 20260922_0012
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260923_0013"
down_revision = "20260922_0012"
branch_labels = None
depends_on = None

# The eight kinds Thư viện của tôi draws. `word` is the only one whose owner
# already exists with a schedule; `note` has no owner at all yet, and is listed
# here so that adding one later is a code change, not a schema change.
KINDS = ("word", "grammar", "reading", "listening", "note", "writing", "speaking", "book")
KIND_LIST = ", ".join(f"'{kind}'" for kind in KINDS)
# What the learner did, from the Collection Architecture §2: starting work does
# not imply saving, and saving does not imply acquiring.
RELATIONSHIPS = ("kept", "started", "imported")
RELATIONSHIP_LIST = ", ".join(f"'{value}'" for value in RELATIONSHIPS)
STATES = ("learning", "mastered")
STATE_LIST = ", ".join(f"'{value}'" for value in STATES)


def upgrade() -> None:
    # --- A. Which entry, and which reading of it ----------------------------
    op.add_column(
        "saved_words",
        sa.Column(
            "entry_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("vocabulary_entries.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "saved_words",
        sa.Column("entry_identity_key", sa.String(900), nullable=False, server_default=""),
    )
    op.add_column(
        "saved_words",
        sa.Column("reading_key", sa.String(240), nullable=False, server_default=""),
    )
    op.create_check_constraint(
        "ck_saved_words_entry_identity",
        "saved_words",
        "entry_id IS NULL OR entry_identity_key <> ''",
    )
    # Reading one learner's words by the entry they point at, and finding every
    # learner who kept a given entry. Partial: most rows carry neither today.
    op.create_index(
        "ix_saved_words_entry",
        "saved_words",
        ["entry_id"],
        postgresql_where=sa.text("entry_id IS NOT NULL"),
        sqlite_where=sa.text("entry_id IS NOT NULL"),
    )
    op.create_index(
        "ix_saved_words_entry_identity",
        "saved_words",
        ["user_id", "language_code", "entry_identity_key"],
        postgresql_where=sa.text("entry_identity_key <> ''"),
        sqlite_where=sa.text("entry_identity_key <> ''"),
    )

    # --- B. The kept-item relation ------------------------------------------
    op.create_table(
        "library_items",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language_code", sa.String(20), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        # A word is a row in `saved_words`; everything else is the routing
        # identity the app already opens it with.
        sa.Column(
            "saved_word_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("saved_words.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("source_id", sa.String(255), nullable=False, server_default=""),
        sa.Column("relationship", sa.String(32), nullable=False, server_default="kept"),
        # NULL means "whatever the owner says". Only a learner's own override
        # is stored, so this can never silently disagree with a word's stage.
        sa.Column("state", sa.String(16), nullable=True),
        # The frame's "đánh dấu cần ôn": pinned items lead the review queue,
        # then whatever is due. No schedule lives in this table.
        sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # The optimistic-concurrency counter the Collection Architecture's
        # `ContentMembership` names; a write that read version N updates N.
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint(f"kind IN ({KIND_LIST})", name="ck_library_items_kind"),
        sa.CheckConstraint(
            f"relationship IN ({RELATIONSHIP_LIST})", name="ck_library_items_relationship"
        ),
        sa.CheckConstraint(
            f"state IS NULL OR state IN ({STATE_LIST})", name="ck_library_items_state"
        ),
        sa.CheckConstraint(
            "(kind = 'word' AND saved_word_id IS NOT NULL)"
            " OR (kind <> 'word' AND saved_word_id IS NULL)",
            name="ck_library_items_word_link",
        ),
        sa.CheckConstraint(
            "kind = 'word' OR source_id <> ''", name="ck_library_items_source"
        ),
        sa.CheckConstraint("version >= 1", name="ck_library_items_version"),
        # What `library_collection_members` references, so a membership cannot
        # put an item of one kind in a collection of another.
        sa.UniqueConstraint("id", "kind", name="uq_library_items_id_kind"),
    )
    # One relationship of one kind to one thing, per learner. Two indexes
    # rather than one constraint, because a word is identified by its row and
    # everything else by its routing id.
    op.create_index(
        "ux_library_items_word",
        "library_items",
        ["user_id", "saved_word_id", "relationship"],
        unique=True,
        postgresql_where=sa.text("saved_word_id IS NOT NULL"),
        sqlite_where=sa.text("saved_word_id IS NOT NULL"),
    )
    op.create_index(
        "ux_library_items_source",
        "library_items",
        ["user_id", "language_code", "kind", "source_id", "relationship"],
        unique=True,
        postgresql_where=sa.text("saved_word_id IS NULL"),
        sqlite_where=sa.text("saved_word_id IS NULL"),
    )
    # The room's own read: one kind of one learner's library, newest first.
    op.create_index(
        "ix_library_items_shelf",
        "library_items",
        ["user_id", "language_code", "kind", "updated_at"],
    )
    # The head of the review queue: what the learner marked, across kinds.
    op.create_index(
        "ix_library_items_pinned",
        "library_items",
        ["user_id", "language_code", "pinned_at"],
        postgresql_where=sa.text("pinned_at IS NOT NULL"),
        sqlite_where=sa.text("pinned_at IS NOT NULL"),
    )

    op.create_table(
        "library_collections",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language_code", sa.String(20), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(f"kind IN ({KIND_LIST})", name="ck_library_collections_kind"),
        sa.CheckConstraint("title <> ''", name="ck_library_collections_title"),
        sa.UniqueConstraint(
            "user_id", "language_code", "kind", "title", name="uq_library_collection_title"
        ),
        sa.UniqueConstraint("id", "kind", name="uq_library_collections_id_kind"),
    )

    op.create_table(
        "library_collection_members",
        sa.Column("collection_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("item_id", sa.Uuid(as_uuid=True), nullable=False),
        # Carried so both references can be by (id, kind): this is what makes
        # "one collection, one kind" a database guarantee rather than a rule
        # every caller has to remember.
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("collection_id", "item_id", name="pk_library_collection_members"),
        sa.ForeignKeyConstraint(
            ["collection_id", "kind"],
            ["library_collections.id", "library_collections.kind"],
            ondelete="CASCADE",
            name="fk_library_member_collection",
        ),
        sa.ForeignKeyConstraint(
            ["item_id", "kind"],
            ["library_items.id", "library_items.kind"],
            ondelete="CASCADE",
            name="fk_library_member_item",
        ),
    )
    op.create_index(
        "ix_library_collection_members_order",
        "library_collection_members",
        ["collection_id", "position"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_library_collection_members_order", table_name="library_collection_members"
    )
    op.drop_table("library_collection_members")
    op.drop_table("library_collections")
    op.drop_index("ix_library_items_pinned", table_name="library_items")
    op.drop_index("ix_library_items_shelf", table_name="library_items")
    op.drop_index("ux_library_items_source", table_name="library_items")
    op.drop_index("ux_library_items_word", table_name="library_items")
    op.drop_table("library_items")
    op.drop_index("ix_saved_words_entry_identity", table_name="saved_words")
    op.drop_index("ix_saved_words_entry", table_name="saved_words")
    op.drop_constraint("ck_saved_words_entry_identity", "saved_words", type_="check")
    op.drop_column("saved_words", "reading_key")
    op.drop_column("saved_words", "entry_identity_key")
    op.drop_column("saved_words", "entry_id")
