"""Adaptive Reading - one canonical Reading flow, one canonical evidence model.

AUTHORIZED FOR THE ADMIN SANDBOX ONLY (`DECISION_LOG.md` D-076, 2026-09-24).
Written for the human direction of 2026-09-24 (D-075): Reading has one flow -
Admin import -> review -> publish into the Reading Corpus -> comprehension set
-> Admin review -> learner attempt -> ability/progression -> next passage. The
AI-generated passage flow retires. Independent architecture review APPROVED at
`fdf198f` (round C1, `docs/project/ADAPTIVE_READING_ARCHITECTURE_REVIEW.md`);
the earlier `generated_session` proposal of the same revision id and its
approval (`0d6efda`) are superseded.

This is a **deliberate non-additive cutover** (D-076): the legacy
generated-reading tables are renamed into a read-only archive rather than kept
as a compatibility model, and the code that retires the generated flow ships in
the same deploy. Apply it only after a backup, with that code. Production and
preview keep every gate: this authorization is for the admin sandbox alone.

Revision ID: 20260924_0014
Revises: 20260923_0013

## What it changes

- **The legacy generated-passage tables become a read-only archive.**
  `reading_sessions` -> `reading_legacy_sessions`, `reading_attempts` ->
  `reading_legacy_attempts`, renamed with every row intact and frozen by
  trigger: no insert, no update. Deletion stays possible, because the account
  deletion workflow needs it and because resetting sandbox-only test data is a
  human decision taken with evidence (the proposal gives the query), never
  something a migration does. Their shape decides nothing below.
- **`reading_attempts` is the one canonical Reading evidence model** - a new
  table under the canonical name, with one shape: a learner's submitted answers
  to one approved comprehension set of one published article, with its
  idempotency receipt, evaluator version and (when measurable) the ability
  measurement. There is no subject discriminator and no second shape.
- `reading_comprehension_sets` / `reading_comprehension_questions` - the
  reviewed questions for one published article, in one support language,
  grounded in one exact body of that article. Platform content.
- `reading_ability_projections` - a discardable, rebuildable projection of the
  attempts: account + language + policy version, checkpointed by ordinal.
- `reading_articles.content_kind` (`article`, `news`) and a unique index
  `(id, language)` so the set's language is bound to its article's.

## Not compatible with the code that runs today - by design

Old code reads and writes `reading_sessions`/`reading_attempts` in their legacy
shape. After this migration the first name is gone and the second names the
canonical table, so an old write fails loudly (missing NOT NULL columns, an
unknown `session_id`) instead of landing anywhere. The migration therefore
applies together with the code that retires the generated flow and reads the
archive under its new name; there is no mixed period.

## Parity: one semantics on PostgreSQL and SQLite

- The one partial index carries both `postgresql_where` and `sqlite_where`.
- Idempotency and ordinal uniqueness are plain unique constraints.
- JSON bounds use `json_array_length`, spans `length()`, hashes `ltrim` - all
  present on both dialects with the same meaning.
- Lifecycle rules a CHECK cannot express are triggers, written once per
  dialect. SQLite's `INSERT/UPDATE OR REPLACE` (deletes a conflicting row
  without a DELETE trigger) is closed by conflict guards; PostgreSQL's
  `TRUNCATE ... CASCADE` (no row trigger, ignores RESTRICT) by statement guards.
  `tests/test_adaptive_reading_schema_proposed.py` runs one scenario list on
  both and requires one outcome.

## Deletes - RESTRICT upward from evidence

attempt -> set and set -> article are `RESTRICT`; a set that reached learners
is never deleted (archived, and restorable); question -> set `CASCADE`;
attempt/projection -> user `CASCADE`. `ACCOUNT_OWNED` below enumerates every
Reading row an account owns, archive included.

## Downgrade never removes learner data

`downgrade()` takes the write lock first (PostgreSQL `LOCK TABLE ... SHARE ROW
EXCLUSIVE`, SQLite a no-op write), then refuses if any canonical attempt, set,
projection or non-default `content_kind` exists. With none, it drops the new
objects, unfreezes the archive and gives it its old names back, every legacy
row intact. Once the canonical model holds data, the rollback is a reviewed
forward repair (`ORENA_ACCOUNT_DATA_ARCHITECTURE.md` SS6).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260924_0014"
down_revision = "20260923_0013"
branch_labels = None
depends_on = None

# Literal lists, never imported from application code: a migration must not
# change meaning after it has been applied because application code moved.
CONTENT_KINDS = ("article", "news")
SET_STATUSES = ("draft", "needs_review", "approved", "rejected", "stale", "archived")
# A set can be edited, and its questions changed, only while nobody has
# decided it yet. From `approved` on it has reached learners; from `rejected`
# on it is review history. Either way it is frozen.
EDITABLE_SET_STATUSES = ("draft", "needs_review")
# A set nobody ever served may be deleted; one that reached learners is
# archived instead, so `archived` is reachable only from `approved`/`stale`.
# Reversible without a delete: `archived -> approved` restores, `stale ->
# approved` re-approves. A rejected set stays frozen as review history; to try
# again, its questions are copied into a new draft set (a service act).
DELETABLE_SET_STATUSES = ("draft", "needs_review", "rejected")
QUESTION_TYPES = (
    "main_idea",
    "detail",
    "inference",
    "vocabulary_in_context",
    "cause_effect",
    "sequence",
    "authors_purpose",
    "reference",
)
# The two types whose answer rests on the whole passage rather than a span.
# Every other type must carry its evidence.
SPANLESS_QUESTION_TYPES = ("main_idea", "authors_purpose")
# The legacy generated-passage tables, archived under these names.
LEGACY_RENAMES = (
    ("reading_attempts", "reading_legacy_attempts"),
    ("reading_sessions", "reading_legacy_sessions"),
)

# Every Reading row owned by an account, and the predicate that finds a
# learner's rows in each, in deletion order - the enumeration the
# account-deletion workflow must consume (D-054, `ORENA_ACCOUNT_DATA_
# ARCHITECTURE.md` SS5). The archive is the learner's too. Here for review and
# for the proof; at apply it moves into application code the deletion workflow
# imports, because the application never imports a migration.
ACCOUNT_OWNED = (
    ("reading_ability_projections", "user_id = :user_id"),
    ("reading_attempts", "user_id = :user_id"),
    ("reading_legacy_attempts",
     "session_id IN (SELECT id FROM reading_legacy_sessions WHERE user_id = :user_id)"),
    ("reading_legacy_sessions", "user_id = :user_id"),
)

# Finite and wide. `ability` is whatever scale the policy version uses - a
# logit, an IRT theta, an Elo rating in the thousands - so the bound excludes
# only non-numbers: on PostgreSQL `NaN` compares greater than every number and
# fails `<=`, and both infinities fail one side (SQLite stores NaN as NULL, which
# NOT NULL refuses). A bound this wide chooses no algorithm.
_FINITE = "BETWEEN -1000000 AND 1000000"


def _hex64(column: str) -> str:
    """64 lowercase hex characters, written with functions both dialects have:
    `ltrim(x, chars)` strips every leading character in `chars`, so the result
    is empty exactly when every character is a lowercase hex digit."""
    return f"length({column}) = 64 AND ltrim({column}, '0123456789abcdef') = ''"


def _in_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _dialect() -> str:
    # `get_context()`, not `get_bind()`: offline rendering has no bind.
    return op.get_context().dialect.name



# ---------------------------------------------------------------------------
# Triggers. Each function pins the `search_path` it was created under
# (`SET search_path FROM CURRENT`), so a table name in its body resolves the
# same way under a restore tool's empty search_path as at runtime.
# No `:` anywhere in these bodies - Alembic wraps `op.execute` text
# in `text()`, which reads `:word` as a bind parameter. ERRCODE 23514
# (check_violation), as the engine's immutability trigger uses, so a
# repository can tell this refusal from any other error.
# ---------------------------------------------------------------------------

_PG_SET_GUARD = f"""
CREATE OR REPLACE FUNCTION reading_comprehension_set_guard() RETURNS trigger AS $func$
DECLARE
    approved_count integer;
    undecided_count integer;
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.status NOT IN ({_in_list(EDITABLE_SET_STATUSES)}) THEN
            RAISE EXCEPTION 'a comprehension set is created undecided and reaches a decision through review'
                USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END IF;
    IF TG_OP = 'DELETE' THEN
        IF OLD.status NOT IN ({_in_list(DELETABLE_SET_STATUSES)}) THEN
            RAISE EXCEPTION 'a comprehension set that reached learners is archived, never deleted'
                USING ERRCODE = '23514';
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.status NOT IN ({_in_list(EDITABLE_SET_STATUSES)}) AND (
           NEW.article_id IS DISTINCT FROM OLD.article_id
        OR NEW.language_code IS DISTINCT FROM OLD.language_code
        OR NEW.support_language IS DISTINCT FROM OLD.support_language
        OR NEW.article_body_sha256 IS DISTINCT FROM OLD.article_body_sha256
        OR NEW.generator_version IS DISTINCT FROM OLD.generator_version
        OR NEW.model IS DISTINCT FROM OLD.model
        OR NEW.created_at IS DISTINCT FROM OLD.created_at
        OR CAST(NEW.validation_json AS text) IS DISTINCT FROM CAST(OLD.validation_json AS text)
        OR ((NEW.status IS NOT DISTINCT FROM OLD.status
             OR NEW.status NOT IN ('approved', 'rejected')) AND (
               NEW.reviewed_by IS DISTINCT FROM OLD.reviewed_by
            OR NEW.reviewed_at IS DISTINCT FROM OLD.reviewed_at
            OR NEW.review_reason IS DISTINCT FROM OLD.review_reason)))
    THEN
        RAISE EXCEPTION 'a decided comprehension set is frozen: build a new set instead'
            USING ERRCODE = '23514';
    END IF;
    IF NEW.status IS DISTINCT FROM OLD.status AND NOT (
           (OLD.status = 'draft' AND NEW.status = 'needs_review')
        OR (OLD.status = 'needs_review' AND NEW.status IN ('draft', 'approved', 'rejected'))
        OR (OLD.status = 'approved' AND NEW.status IN ('stale', 'archived'))
        OR (OLD.status = 'stale' AND NEW.status IN ('approved', 'archived'))
        OR (OLD.status = 'archived' AND NEW.status = 'approved'))
    THEN
        RAISE EXCEPTION 'that comprehension set status change is not a review transition'
            USING ERRCODE = '23514';
    END IF;
    -- Every decision is a new decision: entering `approved` or `rejected`
    -- records its own moment, so a restore or re-approval can never carry an
    -- earlier decision's reviewer forward unnoticed.
    IF NEW.status IS DISTINCT FROM OLD.status AND NEW.status IN ('approved', 'rejected')
       AND NEW.reviewed_at IS NOT DISTINCT FROM OLD.reviewed_at
    THEN
        RAISE EXCEPTION 'a decision records its own moment and reviewer'
            USING ERRCODE = '23514';
    END IF;
    IF NEW.status = 'approved' AND OLD.status IS DISTINCT FROM 'approved' THEN
        SELECT count(*) FILTER (WHERE admin_approved),
               count(*) FILTER (WHERE NOT admin_approved AND NOT admin_rejected)
          INTO approved_count, undecided_count
          FROM reading_comprehension_questions
         WHERE set_id = NEW.id;
        IF approved_count < 1 OR undecided_count > 0 THEN
            RAISE EXCEPTION 'an approved set needs an approved question and no undecided one'
                USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$func$ LANGUAGE plpgsql SET search_path FROM CURRENT;
"""

# `FOR SHARE` on the parent is what serializes a question write against the
# set's approval: the approval's UPDATE needs a lock that conflicts with it, so
# either the question lands first and the approval's count sees it, or the
# approval lands first and the question write sees `approved` and refuses.
# `FOUND` is false inside the cascade of a set delete - the parent row is
# already gone to the cascading statement - which is what lets an undecided or
# rejected set be deleted with its questions.
_PG_QUESTION_GUARD = f"""
CREATE OR REPLACE FUNCTION reading_comprehension_question_guard() RETURNS trigger AS $func$
DECLARE
    parent_status text;
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        SELECT status INTO parent_status FROM reading_comprehension_sets
         WHERE id = OLD.set_id FOR SHARE;
        IF FOUND AND parent_status NOT IN ({_in_list(EDITABLE_SET_STATUSES)}) THEN
            RAISE EXCEPTION 'the questions of a decided comprehension set are frozen'
                USING ERRCODE = '23514';
        END IF;
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        SELECT status INTO parent_status FROM reading_comprehension_sets
         WHERE id = NEW.set_id FOR SHARE;
        IF FOUND AND parent_status NOT IN ({_in_list(EDITABLE_SET_STATUSES)}) THEN
            RAISE EXCEPTION 'the questions of a decided comprehension set are frozen'
                USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END IF;
    RETURN OLD;
END;
$func$ LANGUAGE plpgsql SET search_path FROM CURRENT;
"""

# An attempt meets only an approved set of a published article, and is
# immutable evidence: no UPDATE at all. `FOR SHARE` on the set and its article
# serializes a submit against the set being staled or archived and the article
# being unpublished or archived.
_PG_ATTEMPT_GUARD = """
CREATE OR REPLACE FUNCTION reading_attempt_guard() RETURNS trigger AS $func$
DECLARE
    parent_status text;
    article_status text;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'a reading attempt is immutable evidence'
            USING ERRCODE = '23514';
    END IF;
    SELECT s.status, a.status INTO parent_status, article_status
      FROM reading_comprehension_sets s
      JOIN reading_articles a ON a.id = s.article_id
     WHERE s.id = NEW.set_id
       FOR SHARE;
    IF FOUND AND parent_status <> 'approved' THEN
        RAISE EXCEPTION 'a learner meets only an approved comprehension set'
            USING ERRCODE = '23514';
    END IF;
    IF FOUND AND article_status <> 'published' THEN
        RAISE EXCEPTION 'a learner meets only the published Reading Corpus'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$func$ LANGUAGE plpgsql SET search_path FROM CURRENT;
"""

# The archive is read-only: history, not a store anyone writes to.
_PG_ARCHIVE_GUARD = """
CREATE OR REPLACE FUNCTION reading_legacy_archive_guard() RETURNS trigger AS $func$
BEGIN
    RAISE EXCEPTION 'the legacy Reading archive is read-only'
        USING ERRCODE = '23514';
END;
$func$ LANGUAGE plpgsql SET search_path FROM CURRENT;
"""

# TRUNCATE fires no row trigger and ignores RESTRICT under CASCADE, so
# `TRUNCATE reading_articles CASCADE` or `TRUNCATE users CASCADE` would
# otherwise take sets and learner evidence in one statement. SQLite has no
# TRUNCATE. The archive is guarded too: `TRUNCATE reading_legacy_sessions
# CASCADE` would also truncate every learner's `text_discussions` of every
# kind. A reset of sandbox-only legacy data is a `DELETE`, which sets a
# discussion's `reading_session_id` to NULL and touches nothing else.
_PG_TRUNCATE_GUARD = """
CREATE OR REPLACE FUNCTION reading_evidence_truncate_guard() RETURNS trigger AS $func$
BEGIN
    RAISE EXCEPTION 'reviewed comprehension content and learner evidence are never truncated'
        USING ERRCODE = '23514';
END;
$func$ LANGUAGE plpgsql SET search_path FROM CURRENT;
"""

_PROTECTED = ("reading_comprehension_sets", "reading_comprehension_questions", "reading_attempts")
_ARCHIVE = ("reading_legacy_sessions", "reading_legacy_attempts")

_PG_TRIGGERS = (
    "CREATE TRIGGER reading_comprehension_set_guard"
    " BEFORE INSERT OR UPDATE OR DELETE ON reading_comprehension_sets"
    " FOR EACH ROW EXECUTE FUNCTION reading_comprehension_set_guard()",
    "CREATE TRIGGER reading_comprehension_question_guard"
    " BEFORE INSERT OR UPDATE OR DELETE ON reading_comprehension_questions"
    " FOR EACH ROW EXECUTE FUNCTION reading_comprehension_question_guard()",
    "CREATE TRIGGER reading_attempt_guard"
    " BEFORE INSERT OR UPDATE ON reading_attempts"
    " FOR EACH ROW EXECUTE FUNCTION reading_attempt_guard()",
    *(
        f"CREATE TRIGGER {table}_truncate_guard BEFORE TRUNCATE ON {table}"
        " FOR EACH STATEMENT EXECUTE FUNCTION reading_evidence_truncate_guard()"
        for table in (*_PROTECTED, *_ARCHIVE)
    ),
    *(
        f"CREATE TRIGGER {table}_read_only BEFORE INSERT OR UPDATE ON {table}"
        " FOR EACH ROW EXECUTE FUNCTION reading_legacy_archive_guard()"
        for table in _ARCHIVE
    ),
)

_PG_DROP = (
    *(f"DROP TRIGGER IF EXISTS {table}_read_only ON {table}" for table in _ARCHIVE),
    *(f"DROP TRIGGER IF EXISTS {table}_truncate_guard ON {table}" for table in (*_PROTECTED, *_ARCHIVE)),
    "DROP TRIGGER IF EXISTS reading_attempt_guard ON reading_attempts",
    "DROP TRIGGER IF EXISTS reading_comprehension_question_guard ON reading_comprehension_questions",
    "DROP TRIGGER IF EXISTS reading_comprehension_set_guard ON reading_comprehension_sets",
    "DROP FUNCTION IF EXISTS reading_legacy_archive_guard()",
    "DROP FUNCTION IF EXISTS reading_evidence_truncate_guard()",
    "DROP FUNCTION IF EXISTS reading_attempt_guard()",
    "DROP FUNCTION IF EXISTS reading_comprehension_question_guard()",
    "DROP FUNCTION IF EXISTS reading_comprehension_set_guard()",
)

# The same rules for SQLite, one trigger per event: SQLite has no trigger
# functions and no `TG_OP`. `RAISE(ABORT, ...)` surfaces as a constraint
# failure, and its message must be a literal. SQLite serializes writers on the
# whole database, so it needs no `FOR SHARE`.
#
# SQLite also has a write PostgreSQL does not: `INSERT OR REPLACE` / `UPDATE OR
# REPLACE` resolve a uniqueness conflict by deleting the other row, and fire no
# DELETE trigger doing it. The `*_conflict_guard` triggers refuse any write that
# would collide with a protected row *before* conflict resolution runs. A plain
# write that collides fails on the unique constraint anyway, so the outcome is
# the refusal PostgreSQL gives (where `ON CONFLICT DO UPDATE` goes through the
# UPDATE guards).
_SQLITE_EDITABLE = _in_list(EDITABLE_SET_STATUSES)
_SQLITE_TRIGGERS = (
    f"""CREATE TRIGGER reading_comprehension_set_insert_guard
    BEFORE INSERT ON reading_comprehension_sets
    WHEN NEW.status NOT IN ({_SQLITE_EDITABLE})
    BEGIN SELECT RAISE(ABORT, 'a comprehension set is created undecided and reaches a decision through review'); END""",
    f"""CREATE TRIGGER reading_comprehension_set_delete_guard
    BEFORE DELETE ON reading_comprehension_sets
    WHEN OLD.status NOT IN ({_in_list(DELETABLE_SET_STATUSES)})
    BEGIN SELECT RAISE(ABORT, 'a comprehension set that reached learners is archived, never deleted'); END""",
    f"""CREATE TRIGGER reading_comprehension_set_frozen_guard
    BEFORE UPDATE ON reading_comprehension_sets
    WHEN OLD.status NOT IN ({_SQLITE_EDITABLE}) AND (
           NEW.article_id IS NOT OLD.article_id
        OR NEW.language_code IS NOT OLD.language_code
        OR NEW.support_language IS NOT OLD.support_language
        OR NEW.article_body_sha256 IS NOT OLD.article_body_sha256
        OR NEW.generator_version IS NOT OLD.generator_version
        OR NEW.model IS NOT OLD.model
        OR NEW.created_at IS NOT OLD.created_at
        OR NEW.validation_json IS NOT OLD.validation_json
        OR ((NEW.status IS OLD.status OR NEW.status NOT IN ('approved', 'rejected')) AND (
               NEW.reviewed_by IS NOT OLD.reviewed_by
            OR NEW.reviewed_at IS NOT OLD.reviewed_at
            OR NEW.review_reason IS NOT OLD.review_reason)))
    BEGIN SELECT RAISE(ABORT, 'a decided comprehension set is frozen: build a new set instead'); END""",
    """CREATE TRIGGER reading_comprehension_set_transition_guard
    BEFORE UPDATE OF status ON reading_comprehension_sets
    WHEN NEW.status IS NOT OLD.status AND NOT (
           (OLD.status = 'draft' AND NEW.status = 'needs_review')
        OR (OLD.status = 'needs_review' AND NEW.status IN ('draft', 'approved', 'rejected'))
        OR (OLD.status = 'approved' AND NEW.status IN ('stale', 'archived'))
        OR (OLD.status = 'stale' AND NEW.status IN ('approved', 'archived'))
        OR (OLD.status = 'archived' AND NEW.status = 'approved'))
    BEGIN SELECT RAISE(ABORT, 'that comprehension set status change is not a review transition'); END""",
    """CREATE TRIGGER reading_comprehension_set_approval_guard
    BEFORE UPDATE OF status ON reading_comprehension_sets
    WHEN NEW.status = 'approved' AND OLD.status IS NOT 'approved' AND (
           (SELECT count(*) FROM reading_comprehension_questions
             WHERE set_id = NEW.id AND admin_approved) < 1
        OR (SELECT count(*) FROM reading_comprehension_questions
             WHERE set_id = NEW.id AND NOT admin_approved AND NOT admin_rejected) > 0)
    BEGIN SELECT RAISE(ABORT, 'an approved set needs an approved question and no undecided one'); END""",
    """CREATE TRIGGER reading_comprehension_set_decision_guard
    BEFORE UPDATE OF status ON reading_comprehension_sets
    WHEN NEW.status IS NOT OLD.status AND NEW.status IN ('approved', 'rejected')
     AND NEW.reviewed_at IS OLD.reviewed_at
    BEGIN SELECT RAISE(ABORT, 'a decision records its own moment and reviewer'); END""",
    f"""CREATE TRIGGER reading_comprehension_question_insert_guard
    BEFORE INSERT ON reading_comprehension_questions
    WHEN (SELECT status FROM reading_comprehension_sets WHERE id = NEW.set_id) NOT IN ({_SQLITE_EDITABLE})
    BEGIN SELECT RAISE(ABORT, 'the questions of a decided comprehension set are frozen'); END""",
    f"""CREATE TRIGGER reading_comprehension_question_update_guard
    BEFORE UPDATE ON reading_comprehension_questions
    WHEN (SELECT status FROM reading_comprehension_sets WHERE id = OLD.set_id) NOT IN ({_SQLITE_EDITABLE})
      OR (SELECT status FROM reading_comprehension_sets WHERE id = NEW.set_id) NOT IN ({_SQLITE_EDITABLE})
    BEGIN SELECT RAISE(ABORT, 'the questions of a decided comprehension set are frozen'); END""",
    f"""CREATE TRIGGER reading_comprehension_question_delete_guard
    BEFORE DELETE ON reading_comprehension_questions
    WHEN (SELECT status FROM reading_comprehension_sets WHERE id = OLD.set_id) NOT IN ({_SQLITE_EDITABLE})
    BEGIN SELECT RAISE(ABORT, 'the questions of a decided comprehension set are frozen'); END""",
    """CREATE TRIGGER reading_comprehension_set_insert_conflict_guard
    BEFORE INSERT ON reading_comprehension_sets
    WHEN EXISTS (SELECT 1 FROM reading_comprehension_sets WHERE id = NEW.id)
    BEGIN SELECT RAISE(ABORT, 'a comprehension set is never replaced'); END""",
    """CREATE TRIGGER reading_comprehension_set_update_conflict_guard
    BEFORE UPDATE ON reading_comprehension_sets
    WHEN EXISTS (SELECT 1 FROM reading_comprehension_sets
                  WHERE id <> OLD.id AND (id = NEW.id OR (
                        status = 'approved' AND NEW.status = 'approved'
                    AND article_id = NEW.article_id AND support_language = NEW.support_language)))
    BEGIN SELECT RAISE(ABORT, 'a comprehension set is never replaced'); END""",
    """CREATE TRIGGER reading_comprehension_question_insert_conflict_guard
    BEFORE INSERT ON reading_comprehension_questions
    WHEN EXISTS (SELECT 1 FROM reading_comprehension_questions WHERE id = NEW.id)
    BEGIN SELECT RAISE(ABORT, 'a comprehension question is never replaced'); END""",
    """CREATE TRIGGER reading_comprehension_question_update_conflict_guard
    BEFORE UPDATE ON reading_comprehension_questions
    WHEN NEW.id IS NOT OLD.id
     AND EXISTS (SELECT 1 FROM reading_comprehension_questions WHERE id = NEW.id)
    BEGIN SELECT RAISE(ABORT, 'a comprehension question is never replaced'); END""",
    """CREATE TRIGGER reading_attempt_insert_guard
    BEFORE INSERT ON reading_attempts
    WHEN (SELECT status FROM reading_comprehension_sets WHERE id = NEW.set_id) <> 'approved'
    BEGIN SELECT RAISE(ABORT, 'a learner meets only an approved comprehension set'); END""",
    """CREATE TRIGGER reading_attempt_published_guard
    BEFORE INSERT ON reading_attempts
    WHEN (SELECT a.status FROM reading_comprehension_sets s
            JOIN reading_articles a ON a.id = s.article_id
           WHERE s.id = NEW.set_id) <> 'published'
    BEGIN SELECT RAISE(ABORT, 'a learner meets only the published Reading Corpus'); END""",
    """CREATE TRIGGER reading_attempt_update_guard
    BEFORE UPDATE ON reading_attempts
    BEGIN SELECT RAISE(ABORT, 'a reading attempt is immutable evidence'); END""",
    """CREATE TRIGGER reading_attempt_insert_conflict_guard
    BEFORE INSERT ON reading_attempts
    WHEN EXISTS (SELECT 1 FROM reading_attempts
                  WHERE id = NEW.id
                     OR (user_id = NEW.user_id AND operation_id = NEW.operation_id)
                     OR (user_id = NEW.user_id AND language_code = NEW.language_code
                         AND ordinal = NEW.ordinal))
    BEGIN SELECT RAISE(ABORT, 'a reading attempt is never replaced'); END""",
    *(
        f"""CREATE TRIGGER {table}_read_only_{event.lower()}
    BEFORE {event} ON {table}
    BEGIN SELECT RAISE(ABORT, 'the legacy Reading archive is read-only'); END"""
        for table in _ARCHIVE
        for event in ("INSERT", "UPDATE")
    ),
)

_SQLITE_TRIGGER_NAMES = (
    *(f"{table}_read_only_{event}" for table in _ARCHIVE for event in ("insert", "update")),
    "reading_attempt_insert_conflict_guard",
    "reading_attempt_update_guard",
    "reading_attempt_published_guard",
    "reading_attempt_insert_guard",
    "reading_comprehension_question_update_conflict_guard",
    "reading_comprehension_question_insert_conflict_guard",
    "reading_comprehension_set_update_conflict_guard",
    "reading_comprehension_set_insert_conflict_guard",
    "reading_comprehension_question_delete_guard",
    "reading_comprehension_question_update_guard",
    "reading_comprehension_question_insert_guard",
    "reading_comprehension_set_decision_guard",
    "reading_comprehension_set_approval_guard",
    "reading_comprehension_set_transition_guard",
    "reading_comprehension_set_frozen_guard",
    "reading_comprehension_set_delete_guard",
    "reading_comprehension_set_insert_guard",
)


def upgrade() -> None:
    # ---- 1. Archive the legacy generated-passage tables ---------------------
    # A rename keeps every row, every constraint and every foreign key pointing
    # at them (`text_discussions.reading_session_id` follows on both dialects;
    # SQLite rewrites the reference since 3.26). Attempts first, so the session
    # table they reference is renamed under them rather than before them.
    for old, new in LEGACY_RENAMES:
        op.rename_table(old, new)
        # PostgreSQL names a primary key's index after its table, and a table
        # rename keeps it: `reading_attempts_pkey` would still exist and collide
        # with the canonical table's own primary key below. SQLite renames its
        # automatic indexes with the table.
        if _dialect() == "postgresql":
            op.execute(f"ALTER TABLE {new} RENAME CONSTRAINT {old}_pkey TO {new}_pkey")

    # ---- 2. What form a learner sees ---------------------------------------
    # One statement valid on both dialects: a column constraint inside ADD
    # COLUMN. On SQLite this avoids a batch rebuild of `reading_articles`, which
    # other tables reference and which a rebuild would drop and recreate.
    op.execute(
        "ALTER TABLE reading_articles ADD COLUMN content_kind VARCHAR(20)"
        " DEFAULT 'article' NOT NULL"
        f" CONSTRAINT ck_reading_article_content_kind CHECK (content_kind IN ({_in_list(CONTENT_KINDS)}))"
    )

    # The parent key a set's (article, language) references. A unique *index*,
    # not a constraint: SQLite accepts a unique index as a foreign-key parent
    # and can create one without rebuilding `reading_articles`, which other
    # tables reference; PostgreSQL accepts it too. `id` alone is already
    # unique, so this adds no rule to the article - it only makes the pair
    # referenceable.
    op.create_index(
        "uq_reading_article_language_scope", "reading_articles", ["id", "language"], unique=True
    )

    # ---- 3. A reviewed set of questions for one article ---------------------
    op.create_table(
        "reading_comprehension_sets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        # The article's language, bound to it by the composite foreign key
        # below and carried so an attempt's (set, language) is a composite
        # foreign key too: the chain article -> set -> attempt cannot change
        # language anywhere, by construction rather than by a repository
        # remembering.
        sa.Column("language_code", sa.String(20), nullable=False),
        # The language the explanations are written in. A learner meets the
        # set written in their support language; with none, the article is
        # Free Reading for them - nothing is translated at read time.
        sa.Column("support_language", sa.String(20), nullable=False),
        # The grounding anchor: SHA-256 of the exact `reading_articles.body`
        # every evidence offset below indexes into. `content_revision` cannot
        # be the anchor - it also moves on a title, topic, level or target
        # change and on every publish. The service compares this hash with the
        # current body before it serves the set or accepts an attempt.
        sa.Column("article_body_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("generator_version", sa.String(40), nullable=False),
        sa.Column("model", sa.String(128), nullable=False, server_default=""),
        # Validation issues, type coverage, grounding failures found at
        # generation. Named so it cannot be mistaken for the article's own
        # `analysis_json`.
        sa.Column("validation_json", sa.JSON(), nullable=False),
        sa.Column("reviewed_by", sa.String(255), nullable=False, server_default=""),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"status IN ({_in_list(SET_STATUSES)})", name="ck_reading_comprehension_set_status"
        ),
        sa.CheckConstraint(
            _hex64("article_body_sha256"), name="ck_reading_comprehension_set_body_hash"
        ),
        sa.CheckConstraint(
            "language_code <> '' AND support_language <> '' AND generator_version <> ''",
            name="ck_reading_comprehension_set_identity",
        ),
        # A decision has a moment and someone who made it. Staleness and
        # archiving are later facts about an already-decided set, so they keep
        # the decision's: the trigger lets the three change only on a
        # transition *into* `approved` or `rejected` - a new decision, naming
        # its own reviewer - and freezes them on every other update.
        sa.CheckConstraint(
            "status IN ('draft', 'needs_review') OR (reviewed_at IS NOT NULL AND reviewed_by <> '')",
            name="ck_reading_comprehension_set_reviewed",
        ),
        # RESTRICT, not CASCADE: an article no longer takes its sets with it.
        sa.ForeignKeyConstraint(
            ["article_id", "language_code"],
            ["reading_articles.id", "reading_articles.language"],
            name="fk_reading_comprehension_set_article_scope",
            ondelete="RESTRICT",
        ),
        # The parent key of the attempts' composite foreign key.
        sa.UniqueConstraint("id", "language_code", name="uq_reading_comprehension_set_scope"),
    )
    # One approved set per article and support language. Inclusion, not
    # exclusion: `rejected`, `stale` and `archived` sets stay as history and
    # never block a replacement. Both dialects' predicates, always.
    op.create_index(
        "uq_reading_comprehension_set_approved",
        "reading_comprehension_sets",
        ["article_id", "support_language"],
        unique=True,
        postgresql_where=sa.text("status = 'approved'"),
        sqlite_where=sa.text("status = 'approved'"),
    )
    # An article's sets, newest first, for the Admin review pane - and the
    # index the RESTRICT check needs when an article is purged.
    op.create_index(
        "ix_reading_comprehension_sets_article",
        "reading_comprehension_sets",
        ["article_id", "created_at"],
    )

    # ---- 4. The questions ---------------------------------------------------
    op.create_table(
        "reading_comprehension_questions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "set_id",
            sa.Uuid(),
            sa.ForeignKey("reading_comprehension_sets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Order, not identity: not unique, like the article targets. A unique
        # rank would make an in-place reorder need a deferrable constraint,
        # which SQLite does not have. Ties break on `id`; the approval service
        # renumbers ranks contiguously before a set can be approved.
        sa.Column("rank", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("question_type", sa.String(30), nullable=False),
        # In the passage's language. The explanation is in the set's
        # `support_language`.
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("options_json", sa.JSON(), nullable=False),
        sa.Column("correct_index", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        # The words from the body that settle the question, and where they
        # are: character (code point) offsets into the body whose hash the set
        # carries. NULL together, and only for a type that may omit evidence.
        sa.Column("evidence_text", sa.Text(), nullable=True),
        sa.Column("evidence_start", sa.Integer(), nullable=True),
        sa.Column("evidence_end", sa.Integer(), nullable=True),
        sa.Column("machine_suggested", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("admin_approved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("admin_rejected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"question_type IN ({_in_list(QUESTION_TYPES)})",
            name="ck_reading_comprehension_question_type",
        ),
        sa.CheckConstraint("rank >= 0", name="ck_reading_comprehension_question_rank"),
        sa.CheckConstraint(
            "prompt <> '' AND explanation <> ''", name="ck_reading_comprehension_question_text"
        ),
        # Two to six choices, and the answer is one of them. `json_array_length`
        # exists on both dialects; a non-array is refused on both (PostgreSQL
        # raises, SQLite returns 0).
        sa.CheckConstraint(
            "json_array_length(options_json) BETWEEN 2 AND 6",
            name="ck_reading_comprehension_question_options",
        ),
        sa.CheckConstraint(
            "correct_index >= 0 AND correct_index < json_array_length(options_json)",
            name="ck_reading_comprehension_question_answer",
        ),
        sa.CheckConstraint(
            "(evidence_text IS NULL) = (evidence_start IS NULL)"
            " AND (evidence_start IS NULL) = (evidence_end IS NULL)",
            name="ck_reading_comprehension_question_evidence_complete",
        ),
        # Structural only. This does NOT prove the words are in the passage -
        # a CHECK cannot read `reading_articles.body`. It proves the span is a
        # real, non-empty range whose length is the evidence's length, which is
        # what catches offsets counted in bytes or UTF-16 units. Grounding
        # itself - `body[start:end] == evidence_text` against the body whose
        # hash the set carries - is the service's check, at generation, at
        # approval and before serving.
        sa.CheckConstraint(
            "evidence_text IS NULL OR (evidence_text <> '' AND evidence_start >= 0"
            " AND evidence_end - evidence_start = length(evidence_text))",
            name="ck_reading_comprehension_question_evidence_span",
        ),
        sa.CheckConstraint(
            f"question_type IN ({_in_list(SPANLESS_QUESTION_TYPES)}) OR evidence_text IS NOT NULL",
            name="ck_reading_comprehension_question_evidence_required",
        ),
        sa.CheckConstraint(
            "NOT (admin_approved AND admin_rejected)",
            name="ck_reading_comprehension_question_decision",
        ),
    )
    op.create_index(
        "ix_reading_comprehension_questions_set",
        "reading_comprehension_questions",
        ["set_id", "rank"],
    )

    # ---- 5. The one canonical Reading evidence model -----------------------
    op.create_table(
        "reading_attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language_code", sa.String(20), nullable=False),
        sa.Column("set_id", sa.Uuid(), nullable=False),
        # Per account and language, max + 1, allocated under a per-(account,
        # language) advisory transaction lock - not the discardable projection
        # row. The replay order and the projection's checkpoint: server order,
        # never the client's clock. Contiguity is the service's invariant; the
        # database refuses a duplicate, not a gap.
        sa.Column("ordinal", sa.Integer(), nullable=False),
        # Idempotency (`ORENA_ACCOUNT_DATA_ARCHITECTURE.md` SS4): one logical
        # submit, not one HTTP try. The row is its own receipt; the digest is
        # the guard against the same id reused with different input.
        sa.Column("operation_id", sa.String(120), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        # How the answers were judged.
        sa.Column("evaluator_version", sa.String(40), nullable=False),
        # The difficulty faced, as the article's level was then.
        sa.Column("passage_level", sa.String(20), nullable=False),
        # The ability measurement: which policy moved it, the difficulty number
        # that policy consumed, before and after. All four or none: the answers
        # are the evidence and commit even when no policy can measure them -
        # NULL is "not measured", never zero (`ORENA_EVIDENCE_ARCHITECTURE.md`
        # SS2, SS3).
        sa.Column("ability_policy_version", sa.String(40), nullable=True),
        sa.Column("passage_difficulty", sa.Float(), nullable=True),
        sa.Column("ability_before", sa.Float(), nullable=True),
        sa.Column("ability_after", sa.Float(), nullable=True),
        # Which selection policy served this passage; NULL when the learner
        # chose it. Captured at submit because an immutable attempt can never
        # gain it later, and it is what explains a choice after the fact.
        sa.Column("selection_policy_version", sa.String(40), nullable=True),
        # `[{question_id, selected_index, correct}]`, one per approved question
        # of the set. The database bounds the length; the service validates
        # every element before it writes.
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("correct_count", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        # The moment the answers were submitted. A row exists only once
        # submitted: an unfinished answer sheet is device work, not evidence.
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        # The set, in the attempt's own language. RESTRICT: no content delete
        # can take learner evidence with it.
        sa.ForeignKeyConstraint(
            ["set_id", "language_code"],
            ["reading_comprehension_sets.id", "reading_comprehension_sets.language_code"],
            name="fk_reading_attempt_set_scope",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "language_code <> '' AND ordinal >= 1 AND operation_id <> ''"
            " AND evaluator_version <> '' AND passage_level <> ''"
            " AND (selection_policy_version IS NULL OR selection_policy_version <> '')",
            name="ck_reading_attempt_identity",
        ),
        sa.CheckConstraint(_hex64("request_digest"), name="ck_reading_attempt_digest"),
        sa.CheckConstraint(
            "total > 0 AND correct_count >= 0 AND correct_count <= total"
            " AND json_array_length(answers) = total",
            name="ck_reading_attempt_counts",
        ),
        sa.CheckConstraint(
            "(ability_policy_version IS NULL) = (passage_difficulty IS NULL)"
            " AND (passage_difficulty IS NULL) = (ability_before IS NULL)"
            " AND (ability_before IS NULL) = (ability_after IS NULL)",
            name="ck_reading_attempt_ability_group",
        ),
        # `x IS NULL OR (...)` so no comparison with a NULL can pass the CHECK
        # by evaluating to unknown.
        sa.CheckConstraint(
            "ability_policy_version IS NULL OR ("
            f"ability_policy_version <> '' AND passage_difficulty {_FINITE}"
            f" AND ability_before {_FINITE} AND ability_after {_FINITE})",
            name="ck_reading_attempt_ability_values",
        ),
        # Scoped to the account, not the language: an id replayed under another
        # language is the same logical action reused, and is refused - the
        # backbone's receipts are `(incarnation, domain, operation_id)`.
        sa.UniqueConstraint("user_id", "operation_id", name="uq_reading_attempt_operation"),
        # The progression read (`ORDER BY ordinal DESC`), the replay order, and
        # how account deletion finds a learner's rows.
        sa.UniqueConstraint("user_id", "language_code", "ordinal", name="uq_reading_attempt_ordinal"),
    )
    # What the RESTRICT check reads when a set is deleted, and "has anyone
    # attempted this set" for the Admin pane.
    op.create_index("ix_reading_attempts_set", "reading_attempts", ["set_id", "language_code"])

    # ---- 6. The ability projection -----------------------------------------
    # Discardable by definition (`ORENA_EVIDENCE_ARCHITECTURE.md` SS3): every
    # value here is recomputed by replaying the account's set attempts in
    # ordinal order under `policy_version`, and deleting a row costs a rebuild,
    # never evidence. Identity is account + language + policy version, so a new
    # policy builds beside the old one and selection switches when it is
    # complete.
    op.create_table(
        "reading_ability_projections",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language_code", sa.String(20), nullable=False),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("ability", sa.Float(), nullable=False),
        # The checkpoint: the last attempt ordinal applied. An attempt applies
        # only as `consumed_through_ordinal + 1`, so a re-delivery is a no-op
        # and an out-of-order one cannot apply. Ordinals are contiguous, so it
        # is also how much evidence the estimate rests on.
        sa.Column("consumed_through_ordinal", sa.Integer(), nullable=False, server_default="0"),
        # Accuracy per question type, which steers type coverage in selection.
        sa.Column("by_question_type_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(f"ability {_FINITE}", name="ck_reading_ability_finite"),
        sa.CheckConstraint(
            "consumed_through_ordinal >= 0", name="ck_reading_ability_checkpoint"
        ),
        sa.CheckConstraint(
            "language_code <> '' AND policy_version <> ''", name="ck_reading_ability_identity"
        ),
        sa.UniqueConstraint(
            "user_id", "language_code", "policy_version", name="uq_reading_ability_scope"
        ),
    )

    # ---- 7. The lifecycle rules a CHECK cannot express ----------------------
    if _dialect() == "postgresql":
        for function in (_PG_SET_GUARD, _PG_QUESTION_GUARD, _PG_ATTEMPT_GUARD,
                         _PG_ARCHIVE_GUARD, _PG_TRUNCATE_GUARD):
            op.execute(function)
        for statement in _PG_TRIGGERS:
            op.execute(statement)
    elif _dialect() == "sqlite":
        for statement in _SQLITE_TRIGGERS:
            op.execute(statement)
    else:  # pragma: no cover - the runtime is PostgreSQL, the test path SQLite
        raise NotImplementedError(f"no lifecycle triggers written for {_dialect()}")


# The footprint a downgrade would destroy. Any of it present means the canonical
# flow has recorded something a learner did or an admin decided.
_FOOTPRINT = (
    "SELECT 1 FROM reading_attempts",
    "SELECT 1 FROM reading_comprehension_sets",
    "SELECT 1 FROM reading_ability_projections",
    "SELECT 1 FROM reading_articles WHERE content_kind <> 'article'",
)
_REFUSAL = (
    "20260924_0014 downgrade refused - canonical Reading data exists. Downgrade never"
    " removes learner evidence or reviewed content. Write a reviewed forward repair."
)


def _guard_downgrade() -> None:
    if _dialect() == "postgresql":
        # Lock first, then look: a writer that commits while the downgrade
        # waits is seen by the guard, not dropped by the DDL. SHARE ROW
        # EXCLUSIVE blocks every writer and any second downgrade until this
        # transaction ends. SQL, so an offline-rendered downgrade carries it.
        op.execute(
            "LOCK TABLE reading_articles, reading_comprehension_sets,"
            " reading_comprehension_questions, reading_attempts, reading_ability_projections,"
            " reading_legacy_sessions, reading_legacy_attempts IN SHARE ROW EXCLUSIVE MODE"
        )
        conditions = " OR ".join(f"EXISTS ({query})" for query in _FOOTPRINT)
        op.execute(
            f"DO $guard$ BEGIN IF {conditions} THEN"
            f" RAISE EXCEPTION '{_REFUSAL}' USING ERRCODE = '55000'; END IF; END $guard$"
        )
        return
    # SQLite: a SELECT alone opens no transaction under pysqlite's defaults, so
    # a write that changes nothing takes the database's write lock first; no
    # other connection can write until the downgrade ends.
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE reading_articles SET content_kind = content_kind WHERE 1 = 0"))
    for query in _FOOTPRINT:
        if bind.execute(sa.text(query)).first() is not None:
            raise RuntimeError(_REFUSAL)


def downgrade() -> None:
    _guard_downgrade()
    if _dialect() == "postgresql":
        for statement in _PG_DROP:
            op.execute(statement)
    else:
        for name in _SQLITE_TRIGGER_NAMES:
            op.execute(f"DROP TRIGGER IF EXISTS {name}")

    op.drop_table("reading_ability_projections")
    op.drop_index("ix_reading_attempts_set", table_name="reading_attempts")
    op.drop_table("reading_attempts")
    op.drop_index("ix_reading_comprehension_questions_set", table_name="reading_comprehension_questions")
    op.drop_table("reading_comprehension_questions")
    op.drop_index("ix_reading_comprehension_sets_article", table_name="reading_comprehension_sets")
    op.drop_index("uq_reading_comprehension_set_approved", table_name="reading_comprehension_sets")
    op.drop_table("reading_comprehension_sets")
    op.drop_index("uq_reading_article_language_scope", table_name="reading_articles")
    op.execute("ALTER TABLE reading_articles DROP COLUMN content_kind")
    # The archive gets its names back, every row intact.
    for old, new in reversed(LEGACY_RENAMES):
        if _dialect() == "postgresql":
            op.execute(f"ALTER TABLE {new} RENAME CONSTRAINT {new}_pkey TO {old}_pkey")
        op.rename_table(new, old)
