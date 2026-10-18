"""Orena Memory, M2: learner memories, suppression keys and the memory state (ORENA_MEMORY.md rev 4.1 §4.1, §4.4,
§9; D-222). M2b (`memory_signals`) and M3 (`orena_session_summaries`) are their own revisions, so each can be rolled
back alone.

- `learner_memories`: one row per explicit, inferred or continuity item of a learner, in one learning language
  (`'*'` for every language). `text` is what the item says: the learner's words (explicit), the rule's template
  (inferred), the code's template key (continuity). `code` is the slot's closed code (agent/memory_slots.py): required
  on continuity, kept when a continuity item is pinned or promoted to explicit - the explicit item then holds the
  learner's latest verbatim words in `text` and the slot and code in `slot`, `code` (rev 4.1 §3.4, F8; review of PR
  #269) - and null on an explicit note with no slot. `value_key` is HMAC-SHA256, as lowercase hex, of the normalised
  slot and value under the memory key `key_version` (agent/memory_keys.py), the value being `code` when there is one,
  else `text`; a key rotation re-keys a live row from the same column. Uniqueness: a single-valued slot once per (incarnation,
  language, class); a multi-valued slot once per value; an explicit item with no slot once per value (a retried
  `remember_note` does not duplicate). CHECKs bound the text (200 characters) and provenance (2 KB), require
  `expires_at` for inferred and continuity, require the rule's evidence (count, window, confidence) on inferred items
  and keep it to them, and require `code` on continuity.
- `learner_memory_suppressions`: what a deleted continuity or inferred item leaves - the HMAC of its slot and value,
  no text, until its former expiry. A separate table, so a suppression never collides with a live item's key. Kept by
  a bulk delete; listed in the deletion enumeration; never exported.
- `learner_memory_state`: one row per incarnation - the switch (`enabled`) and `version`, bumped with every memory
  write, delete and switch change (§4.4, F6). Not a column on `users` (D-104 H-17).

Scope (F11): `incarnation_id` FK `account_incarnations(id)` ON DELETE CASCADE and `user_id` FK `users(id)` ON
DELETE RESTRICT, as 0005 scopes its tables, plus a composite FK `(incarnation_id, user_id)` to
`account_incarnations(id, user_id)` so an incarnation belongs to the user; the unique key that FK needs is added on
`account_incarnations`. The cascade never fires in practice (account deletion keeps the incarnation row as a barrier);
the D-055 deletion runtime removes these rows explicitly. Memory fails closed without an active incarnation - in code,
not here.

Built with this revision (PR M2.1): the repository `writing_coach/persistence/memory_repository.py` and the tables in
`deletion_enumeration.py` and its test. No ORM model, like every incarnation-keyed table of 0005: `account_incarnations`
has none, so a model with this FK would break CI's `create_all` (ORENA_MEMORY.md §9, "As built at M2 promotion").
Expiry is filtered on read and swept in bounded batches by the repository; nothing runs at startup (D-002).

Promotion (2026-10-18). The owner authorised promoting this revision on issue #256, after its draft review and
a PostgreSQL up/down/up rehearsal (`scripts/rehearse_orena_memory_schema.py`). It is parented on 20261015_0033,
the head of that day. Merging it moves the head: every PostgreSQL runtime that takes this code must apply it
(operator step, after a backup) before it starts, starting with :8021, which the UI lane applies. Billing's
proposed 0034 re-parents on it when promoted. `downgrade()` refuses while any memory row exists; it exists for
rehearsal only.

Revision ID: 20261018_0035
Revises: 20261015_0033
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261018_0035"
down_revision = "20261015_0033"
branch_labels = None
depends_on = None

CLASSES = ("explicit", "inferred", "continuity")
KINDS = ("preference", "goal", "plan", "interest", "context", "address")
# ORENA_MEMORY.md §4.1: one value per learner, language and class.
SINGLE_VALUED_SLOTS = ("explanation_length", "support_language", "correction_timing", "occupation", "learning_purpose")
MAX_TEXT = 200
HEX64 = "^[0-9a-f]{64}$"  # agent/memory_keys.py: lowercase SHA-256 hex
CODE = "^[a-z_]{1,40}$"  # a closed code of agent/memory_slots.py
MAX_PROVENANCE_BYTES = 2048

_INCARNATION_OWNER = "uq_account_incarnation_id_user"
_TABLES = ("learner_memory_state", "learner_memory_suppressions", "learner_memories")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _scope() -> list[sa.Column]:
    return [
        sa.Column("incarnation_id", sa.Uuid(), sa.ForeignKey("account_incarnations.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
    ]


def _owner(name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(["incarnation_id", "user_id"], ["account_incarnations.id", "account_incarnations.user_id"],
                                   name=name, ondelete="CASCADE")


def upgrade() -> None:
    op.create_unique_constraint(_INCARNATION_OWNER, "account_incarnations", ["id", "user_id"])

    op.create_table(
        "learner_memories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        *_scope(),
        sa.Column("language_code", sa.String(20), nullable=False),
        sa.Column("class", sa.String(16), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("slot", sa.String(40), nullable=True),
        sa.Column("text", sa.String(MAX_TEXT), nullable=False),
        sa.Column("code", sa.String(40), nullable=True),
        sa.Column("value_key", sa.String(64), nullable=False),
        sa.Column("key_version", sa.SmallInteger(), nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=True),
        sa.Column("evidence_window_days", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("provenance", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("weight", sa.Float(), nullable=True),
        sa.Column("last_reinforced", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        _owner("fk_learner_memories_owner"),
        sa.CheckConstraint(_in('"class"', CLASSES), name="ck_learner_memories_class"),
        sa.CheckConstraint(_in("kind", KINDS), name="ck_learner_memories_kind"),
        sa.CheckConstraint(f"char_length(text) BETWEEN 1 AND {MAX_TEXT}", name="ck_learner_memories_text"),
        sa.CheckConstraint(f"value_key ~ '{HEX64}'", name="ck_learner_memories_value_key"),
        sa.CheckConstraint(f"code IS NULL OR (code ~ '{CODE}' AND slot IS NOT NULL)", name="ck_learner_memories_code"),
        sa.CheckConstraint("\"class\" <> 'continuity' OR code IS NOT NULL", name="ck_learner_memories_continuity_code"),
        sa.CheckConstraint("key_version >= 1", name="ck_learner_memories_key_version"),
        sa.CheckConstraint(f"octet_length(provenance::text) <= {MAX_PROVENANCE_BYTES}",
                           name="ck_learner_memories_provenance"),
        sa.CheckConstraint("\"class\" = 'explicit' OR expires_at IS NOT NULL", name="ck_learner_memories_expiry"),
        sa.CheckConstraint(
            "CASE WHEN \"class\" = 'inferred'"
            " THEN evidence_count IS NOT NULL AND evidence_count >= 1 AND evidence_window_days IS NOT NULL"
            " AND evidence_window_days >= 1 AND confidence IS NOT NULL"
            " ELSE evidence_count IS NULL AND evidence_window_days IS NULL AND confidence IS NULL END",
            name="ck_learner_memories_evidence"),
        sa.CheckConstraint("\"class\" = 'explicit' OR slot IS NOT NULL", name="ck_learner_memories_slot"),
        sa.CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
                           name="ck_learner_memories_confidence"),
    )
    single = _in("slot", SINGLE_VALUED_SLOTS)
    op.create_index("uq_learner_memories_single_slot", "learner_memories",
                    ["incarnation_id", "language_code", "class", "slot"], unique=True,
                    postgresql_where=sa.text(single))
    op.create_index("uq_learner_memories_multi_slot", "learner_memories",
                    ["incarnation_id", "language_code", "class", "slot", "value_key"], unique=True,
                    postgresql_where=sa.text(f"slot IS NOT NULL AND NOT ({single})"))
    op.create_index("uq_learner_memories_explicit_text", "learner_memories",
                    ["incarnation_id", "language_code", "value_key"], unique=True,
                    postgresql_where=sa.text("slot IS NULL AND \"class\" = 'explicit'"))
    op.create_index("ix_learner_memories_pack", "learner_memories",
                    ["incarnation_id", "language_code", "class", "expires_at"])
    op.create_index("ix_learner_memories_expiry", "learner_memories", ["expires_at"],
                    postgresql_where=sa.text("expires_at IS NOT NULL"))

    op.create_table(
        "learner_memory_suppressions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        *_scope(),
        sa.Column("language_code", sa.String(20), nullable=False),
        sa.Column("class", sa.String(16), nullable=False),
        sa.Column("slot", sa.String(40), nullable=False),
        sa.Column("value_key", sa.String(64), nullable=False),
        sa.Column("key_version", sa.SmallInteger(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        _owner("fk_learner_memory_suppressions_owner"),
        sa.CheckConstraint("\"class\" IN ('inferred', 'continuity')", name="ck_learner_memory_suppressions_class"),
        sa.CheckConstraint(f"value_key ~ '{HEX64}'", name="ck_learner_memory_suppressions_value_key"),
        sa.CheckConstraint("key_version >= 1", name="ck_learner_memory_suppressions_key_version"),
        sa.UniqueConstraint("incarnation_id", "language_code", "class", "slot", "value_key", "key_version",
                            name="uq_learner_memory_suppressions_key"),
    )
    op.create_index("ix_learner_memory_suppressions_expiry", "learner_memory_suppressions", ["expires_at"])

    op.create_table(
        "learner_memory_state",
        sa.Column("incarnation_id", sa.Uuid(), sa.ForeignKey("account_incarnations.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        _owner("fk_learner_memory_state_owner"),
        sa.CheckConstraint("version >= 0", name="ck_learner_memory_state_version"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    for table in _TABLES:
        if bind.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM {table})")).scalar():
            raise RuntimeError(f"{table} holds learner data: downgrade is for rehearsal only and refuses")
    for table in _TABLES:
        op.drop_table(table)
    op.drop_constraint(_INCARNATION_OWNER, "account_incarnations", type_="unique")
