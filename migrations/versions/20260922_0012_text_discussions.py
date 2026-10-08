"""A learner's discussion about a whole text, kept with the account (D-072.2).

Approved by delegated architecture review on 2026-09-22 over four rounds; the
record, and everything the rounds changed, is in
`docs/project/PROPOSAL_SAVED_REVIEWS_AND_TEXT_DISCUSSION.md`. Sandbox only.

Two tables. `text_discussions` is one thread per learner per text, keyed to the
content identity the app already routes on rather than to a catalogue row,
because Orena owns no table for every kind of text. `text_discussion_turns` is
the words, ordered by an explicit `ordinal` rather than by `created_at`, which
can tie when both turns of an exchange are written in one request.

Four things in here are load-bearing and are not style:

- `UNIQUE (discussion_id, ordinal)` and `turn_count` together make the write
  atomic. A turn pair takes its ordinals from one
  `UPDATE ... WHERE turn_count <= 198 RETURNING turn_count`, so two concurrent
  submits serialise on the thread row instead of computing the same ordinals.
  The CHECK and the unique index are the hard backstops behind that statement.

- `CHECK (source_kind = 'reading_session' OR reading_session_id IS NULL)` is a
  one-directional implication on purpose. The biconditional it replaced
  contradicted `ON DELETE SET NULL`: that FK action runs an UPDATE which is
  itself checked, `source_kind` is untouched by it, so deleting a reading
  session would have failed outright rather than nulling the column. This form
  still forbids a `story`, `media` or `book_chapter` thread from carrying a
  session id, and permits the one state the FK action produces.

- `SET NULL` rather than `CASCADE` on that FK: losing the session must not
  delete the learner's own words. Account deletion still removes everything,
  cascading from `users`.

- The partial unique index on `(discussion_id, request_id)` is the endpoint's
  dedup contract, so a retried POST cannot double-answer. It is partial because
  `''` is the default for every turn that carries no client key - including
  every assistant turn, which never carries one.

Two turns of the cap are consumed permanently whenever a provider call fails or
a raced duplicate loses the unique index: the reservation commits before the
provider is called, and it is deliberately not decremented, because a decrement
would re-issue ordinals a concurrent submit may already hold. Ordinal gaps are
therefore expected and are not a defect; the read path orders by `ordinal` and
never assumes it is contiguous.

`source_id` is the routing identity string (for a reading session, that is the
per-user `legacy_id`), while `reading_session_id` is the internal UUID primary
key. They are different id spaces and are not interchangeable.

Downgrade drops both tables and the learner's words with them. It exists for a
rehearsal, not for a live account.

Revision ID: 20260922_0012
Revises: 20260922_0011
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260922_0012"
down_revision = "20260922_0011"
branch_labels = None
depends_on = None

SOURCE_KINDS = ("story", "media", "reading_session", "book_chapter")
ROLES = ("learner", "assistant")


def upgrade() -> None:
    op.create_table(
        "text_discussions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language_code", sa.String(20), nullable=False),
        sa.Column("source_kind", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=False),
        sa.Column(
            "reading_session_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("reading_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("turn_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "user_id", "language_code", "source_kind", "source_id", name="uq_text_discussion_scope"
        ),
        sa.CheckConstraint(
            "source_kind IN ('story','media','reading_session','book_chapter')",
            name="ck_text_discussion_source_kind",
        ),
        sa.CheckConstraint(
            "source_kind = 'reading_session' OR reading_session_id IS NULL",
            name="ck_text_discussion_session_kind",
        ),
        sa.CheckConstraint(
            "turn_count >= 0 AND turn_count <= 200", name="ck_text_discussion_turn_cap"
        ),
    )

    op.create_table(
        "text_discussion_turns",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "discussion_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("text_discussions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("context", sa.Text(), nullable=False, server_default=""),
        sa.Column("provider", sa.String(64), nullable=False, server_default=""),
        sa.Column("model", sa.String(128), nullable=False, server_default=""),
        sa.Column("request_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("discussion_id", "ordinal", name="uq_text_discussion_turn_ordinal"),
        sa.CheckConstraint("role IN ('learner','assistant')", name="ck_text_discussion_turn_role"),
        sa.CheckConstraint("length(body) <= 4000", name="ck_text_discussion_turn_body"),
        sa.CheckConstraint("ordinal >= 1", name="ck_text_discussion_turn_ordinal_positive"),
    )
    # The read path: this thread's turns in order, paged by an ordinal cursor.
    op.create_index(
        "ix_text_discussion_turns_order", "text_discussion_turns", ["discussion_id", "ordinal"]
    )
    # The dedup contract. Partial: '' is every turn that carries no client key.
    op.create_index(
        "ux_text_discussion_turns_request",
        "text_discussion_turns",
        ["discussion_id", "request_id"],
        unique=True,
        postgresql_where=sa.text("request_id <> ''"),
    )


def downgrade() -> None:
    op.drop_index("ux_text_discussion_turns_request", table_name="text_discussion_turns")
    op.drop_index("ix_text_discussion_turns_order", table_name="text_discussion_turns")
    op.drop_table("text_discussion_turns")
    op.drop_table("text_discussions")
