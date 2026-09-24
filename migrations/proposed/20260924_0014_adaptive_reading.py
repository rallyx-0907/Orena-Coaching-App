"""Adaptive Reading Practice - reviewed questions, learner evidence, ability.

PROPOSED - NOT APPLIED. Round 2 of the independent architecture review
(`docs/project/ADAPTIVE_READING_ARCHITECTURE_REVIEW.md`) returned REQUEST
CHANGES on this file; round 3 reviews the revision against the round-2
findings, together with `docs/project/ADAPTIVE_READING_SCHEMA_PROPOSAL.md`. It sits
in `migrations/proposed/`, which Alembic's default `version_locations` never
reads, so no environment's startup check can meet it. Moving it into
`versions/` is the apply step and needs the human's schema/runtime
authorization after an APPROVED review; this docstring authorizes nothing.

Revision ID: 20260924_0014
Revises: 20260923_0013

## What it changes

Two new platform-content tables, one new learner projection, and two additive
changes to existing tables:

- `reading_comprehension_sets` / `reading_comprehension_questions` - a
  reviewed set of questions for one published article, in one support
  language, grounded in one exact body of that article. Platform content: no
  learner key, no `users` foreign key.
- `reading_attempts` is **extended, not paralleled**. It is already the Reading
  domain's comprehension-attempt owner (submitted answers, correct count,
  total). A second attempts table for the same evidence kind is exactly the
  "parallel authoritative store" `ORENA_ACCOUNT_DATA_ARCHITECTURE.md` SS3/SS6.7
  forbids, so an attempt now has one of two subjects, named by
  `subject_kind`: a `generated_session` (the existing rows, unchanged) or a
  `comprehension_set` (Adaptive Reading). Two CHECKs make the two shapes
  exclusive and complete.
- `reading_ability_projections` - a discardable, rebuildable projection of the
  set attempts: account + language + policy version, with the ordinal it has
  consumed through as its checkpoint.
- `reading_articles.content_kind` - what form a learner sees (`article`,
  `news`). Default `article`, which every existing row is.

## Parity: one semantics on PostgreSQL and SQLite

Every constraint here is chosen so the hermetic SQLite path enforces the same
rule the PostgreSQL runtime does, and `tests/test_adaptive_reading_schema_
proposed.py` runs one scenario list against both and requires one outcome:

- The only partial index is declared with **both** `postgresql_where` and
  `sqlite_where` - never one alone, which on SQLite silently becomes a full
  index.
- Idempotency and ordinal uniqueness are **plain** unique constraints over
  nullable columns, not partial indexes: legacy rows carry NULL there, and both
  dialects treat NULLs as distinct in a unique constraint, so the legacy rows
  are outside the rule without a predicate to drift.
- The JSON bounds use `json_array_length`, which both dialects have; the
  evidence span uses `length()`, which counts characters on both.
- The lifecycle rules a CHECK cannot express (a decided set is frozen; an
  approved set has an approved question and no undecided one; an attempt meets
  only an approved set; a set attempt is immutable) are triggers, written once
  per dialect below and proved by the same scenarios.
- The two dialects each have one write the other lacks, and each is closed:
  SQLite's `INSERT/UPDATE OR REPLACE` deletes a conflicting row without firing
  a DELETE trigger, so SQLite also gets conflict guards; PostgreSQL's
  `TRUNCATE ... CASCADE` fires no row trigger and ignores RESTRICT, so
  PostgreSQL also gets statement-level truncate guards.

## Deletes - RESTRICT upward from evidence

- attempt -> set: `RESTRICT`. Learner evidence can never be taken by a content
  delete; the delete fails instead.
- set -> article `(article_id, language_code)` -> `(id, language)`: `RESTRICT`,
  not CASCADE, and the set's language is the article's by construction. An article purge must delete its
  evidence-free sets explicitly first, and a set that ever reached learners
  (`approved`, `stale`, `archived`) refuses deletion outright - that article
  is archived, never purged. Nothing is taken silently and nothing blocks
  silently: both refusals raise.
- question -> set: `CASCADE` downward - a question has no meaning without its
  set, and only an undecided or rejected set can be deleted at all.
- attempt -> user, projection -> user: `CASCADE`, as every learner owner table.
  The account-deletion workflow (D-054/D-055, not yet built and gated by
  `tests/test_deletion_journal.py`) deletes them explicitly; the enumeration is
  `ACCOUNT_OWNED` below and is exercised by the proof.

## Downgrade never removes learner data

`downgrade()` first locks every table it would change against writers
(PostgreSQL, `SHARE ROW EXCLUSIVE`), then runs a guard *in the same
transaction*: if any set attempt, any comprehension set, any ability projection
row, or any `content_kind` other than `article` exists, it raises and nothing
is dropped. The lock is what makes that true under a concurrent writer - one
that commits while the downgrade waits is seen by the guard, not dropped by the
DDL. Both are SQL on PostgreSQL, so an offline-rendered (`--sql`) downgrade
carries them too. Once the feature has written anything, the rollback is the one
`ORENA_ACCOUNT_DATA_ARCHITECTURE.md` SS6 names - roll the *code* back and keep
the additive schema (old code reads and writes this schema unchanged: the new
columns are nullable or defaulted, which the proof also shows), or apply a
reviewed forward repair.
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
SUBJECT_KINDS = ("generated_session", "comprehension_set")

# Every Reading row owned by an account, and the predicate that finds a
# learner's rows in each, in deletion order - the enumeration the
# account-deletion workflow must consume (D-054, `ORENA_ACCOUNT_DATA_
# ARCHITECTURE.md` SS5). It covers the whole Reading owner, not only what this
# migration adds: the generated sessions (passage, goal) and their attempts are
# the learner's too. The set attempts are keyed to the account directly; the
# projection is discardable. Here for review and for the proof; at apply it
# moves into application code the deletion workflow imports, because the
# application never imports a migration.
ACCOUNT_OWNED = (
    ("reading_ability_projections", "user_id = :user_id"),
    ("reading_attempts", "subject_kind = 'comprehension_set' AND user_id = :user_id"),
    ("reading_attempts", "session_id IN (SELECT id FROM reading_sessions WHERE user_id = :user_id)"),
    ("reading_sessions", "user_id = :user_id"),
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
        OR (OLD.status = 'stale' AND NEW.status IN ('approved', 'archived')))
    THEN
        RAISE EXCEPTION 'that comprehension set status change is not a review transition'
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

# An attempt meets only an approved set, and a set attempt is immutable
# evidence. Generated-session rows are untouched: the legacy importer upserts
# them, and this migration changes nothing about how they are written.
_PG_ATTEMPT_GUARD = """
CREATE OR REPLACE FUNCTION reading_attempt_guard() RETURNS trigger AS $func$
DECLARE
    parent_status text;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF OLD.subject_kind = 'comprehension_set' THEN
            RAISE EXCEPTION 'a comprehension attempt is immutable evidence'
                USING ERRCODE = '23514';
        END IF;
        IF NEW.subject_kind = 'comprehension_set' THEN
            RAISE EXCEPTION 'an existing attempt cannot become a comprehension attempt'
                USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.set_id IS NOT NULL THEN
        SELECT status INTO parent_status FROM reading_comprehension_sets
         WHERE id = NEW.set_id FOR SHARE;
        IF FOUND AND parent_status <> 'approved' THEN
            RAISE EXCEPTION 'a learner meets only an approved comprehension set'
                USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$func$ LANGUAGE plpgsql SET search_path FROM CURRENT;
"""

# TRUNCATE fires no row trigger and ignores RESTRICT under CASCADE, so
# `TRUNCATE reading_articles CASCADE` would otherwise take sets and learner
# evidence in one statement. Statement triggers close it. SQLite has no
# TRUNCATE.
_PG_TRUNCATE_GUARD = """
CREATE OR REPLACE FUNCTION reading_comprehension_truncate_guard() RETURNS trigger AS $func$
BEGIN
    IF TG_TABLE_NAME <> 'reading_attempts'
       OR EXISTS (SELECT 1 FROM reading_attempts WHERE subject_kind = 'comprehension_set')
    THEN
        RAISE EXCEPTION 'reviewed comprehension content and learner evidence are never truncated'
            USING ERRCODE = '23514';
    END IF;
    RETURN NULL;
END;
$func$ LANGUAGE plpgsql SET search_path FROM CURRENT;
"""

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
        " FOR EACH STATEMENT EXECUTE FUNCTION reading_comprehension_truncate_guard()"
        for table in ("reading_comprehension_sets", "reading_comprehension_questions", "reading_attempts")
    ),
)

_PG_DROP = (
    "DROP TRIGGER IF EXISTS reading_attempts_truncate_guard ON reading_attempts",
    "DROP TRIGGER IF EXISTS reading_comprehension_questions_truncate_guard ON reading_comprehension_questions",
    "DROP TRIGGER IF EXISTS reading_comprehension_sets_truncate_guard ON reading_comprehension_sets",
    "DROP FUNCTION IF EXISTS reading_comprehension_truncate_guard()",
    "DROP TRIGGER IF EXISTS reading_attempt_guard ON reading_attempts",
    "DROP TRIGGER IF EXISTS reading_comprehension_question_guard ON reading_comprehension_questions",
    "DROP TRIGGER IF EXISTS reading_comprehension_set_guard ON reading_comprehension_sets",
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
# DELETE trigger doing it - which would forge a set attempt or turn an approved
# set back into a draft past every guard above. The `*_conflict_guard`
# triggers refuse any write that would collide with a protected row, *before*
# conflict resolution runs. A plain write that collides fails on the unique
# constraint anyway, so the outcome is the same refusal PostgreSQL gives
# (where `ON CONFLICT DO UPDATE` goes through the UPDATE guards).
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
        OR (OLD.status = 'stale' AND NEW.status IN ('approved', 'archived')))
    BEGIN SELECT RAISE(ABORT, 'that comprehension set status change is not a review transition'); END""",
    """CREATE TRIGGER reading_comprehension_set_approval_guard
    BEFORE UPDATE OF status ON reading_comprehension_sets
    WHEN NEW.status = 'approved' AND OLD.status IS NOT 'approved' AND (
           (SELECT count(*) FROM reading_comprehension_questions
             WHERE set_id = NEW.id AND admin_approved) < 1
        OR (SELECT count(*) FROM reading_comprehension_questions
             WHERE set_id = NEW.id AND NOT admin_approved AND NOT admin_rejected) > 0)
    BEGIN SELECT RAISE(ABORT, 'an approved set needs an approved question and no undecided one'); END""",
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
    """CREATE TRIGGER reading_attempt_insert_guard
    BEFORE INSERT ON reading_attempts
    WHEN NEW.set_id IS NOT NULL
     AND (SELECT status FROM reading_comprehension_sets WHERE id = NEW.set_id) <> 'approved'
    BEGIN SELECT RAISE(ABORT, 'a learner meets only an approved comprehension set'); END""",
    """CREATE TRIGGER reading_attempt_update_guard
    BEFORE UPDATE ON reading_attempts
    WHEN OLD.subject_kind = 'comprehension_set' OR NEW.subject_kind = 'comprehension_set'
    BEGIN SELECT RAISE(ABORT, 'a comprehension attempt is immutable evidence'); END""",
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
    """CREATE TRIGGER reading_attempt_insert_conflict_guard
    BEFORE INSERT ON reading_attempts
    WHEN EXISTS (SELECT 1 FROM reading_attempts
                  WHERE subject_kind = 'comprehension_set' AND (
                        id = NEW.id
                     OR (user_id = NEW.user_id AND operation_id = NEW.operation_id)
                     OR (user_id = NEW.user_id AND language_code = NEW.language_code
                         AND ordinal = NEW.ordinal)))
    BEGIN SELECT RAISE(ABORT, 'a comprehension attempt is never replaced'); END""",
    """CREATE TRIGGER reading_attempt_update_conflict_guard
    BEFORE UPDATE ON reading_attempts
    WHEN EXISTS (SELECT 1 FROM reading_attempts
                  WHERE subject_kind = 'comprehension_set' AND id <> OLD.id AND id = NEW.id)
    BEGIN SELECT RAISE(ABORT, 'a comprehension attempt is never replaced'); END""",
)

_SQLITE_TRIGGER_NAMES = (
    "reading_attempt_update_conflict_guard",
    "reading_attempt_insert_conflict_guard",
    "reading_comprehension_question_update_conflict_guard",
    "reading_comprehension_question_insert_conflict_guard",
    "reading_comprehension_set_update_conflict_guard",
    "reading_comprehension_set_insert_conflict_guard",
    "reading_attempt_update_guard",
    "reading_attempt_insert_guard",
    "reading_comprehension_question_delete_guard",
    "reading_comprehension_question_update_guard",
    "reading_comprehension_question_insert_guard",
    "reading_comprehension_set_approval_guard",
    "reading_comprehension_set_transition_guard",
    "reading_comprehension_set_frozen_guard",
    "reading_comprehension_set_delete_guard",
    "reading_comprehension_set_insert_guard",
)


def upgrade() -> None:
    # ---- 1. What form a learner sees ---------------------------------------
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

    # ---- 2. A reviewed set of questions for one article ---------------------
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

    # ---- 3. The questions ---------------------------------------------------
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

    # ---- 4. The existing attempt owner, given a second subject --------------
    # `batch_alter_table` emits plain ALTERs on PostgreSQL (DROP NOT NULL and
    # ADD COLUMN without a volatile default are catalogue-only there) and
    # rebuilds the table on SQLite, which cannot relax NOT NULL in place.
    # Nothing references `reading_attempts`, so the rebuild drops no child.
    with op.batch_alter_table("reading_attempts") as batch:
        batch.alter_column("session_id", existing_type=sa.Uuid(), nullable=True)
        batch.alter_column("legacy_id", existing_type=sa.Integer(), nullable=True)
        # Server default = the existing shape, so every existing row and every
        # write from code that has never heard of this column is a
        # generated-session attempt, exactly as it is today.
        batch.add_column(
            sa.Column(
                "subject_kind", sa.String(20), nullable=False, server_default="generated_session"
            )
        )
        batch.add_column(sa.Column("user_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("language_code", sa.String(20), nullable=True))
        batch.add_column(sa.Column("set_id", sa.Uuid(), nullable=True))
        # Per account and language, max + 1, allocated under a per-(account,
        # language) transaction lock that is not the discardable projection
        # row. The replay order and the projection's checkpoint - server order,
        # never the client's clock. Contiguity is the service's invariant: the
        # database refuses a duplicate, not a gap.
        batch.add_column(sa.Column("ordinal", sa.Integer(), nullable=True))
        # Idempotency (SS4): one logical submit, not one HTTP try. The row is
        # its own receipt - a retry finds it and returns it. The digest is the
        # guard against the same id reused with different input.
        batch.add_column(sa.Column("operation_id", sa.String(120), nullable=True))
        batch.add_column(sa.Column("request_digest", sa.String(64), nullable=True))
        # How the answers were judged.
        batch.add_column(sa.Column("evaluator_version", sa.String(40), nullable=True))
        # The difficulty faced, as the level was then.
        batch.add_column(sa.Column("passage_level", sa.String(20), nullable=True))
        # The ability measurement: which policy moved it, the difficulty
        # number that policy actually consumed (so before -> after stays
        # explainable after the level-to-number mapping changes), and the
        # before and after. **All four or none** (`ck_reading_attempt_ability_
        # group`): the evidence is the answers, and it commits even when the
        # projection cannot measure it - a policy with no mapping for this
        # level, a replay that fails. NULL is "not measured", never zero
        # (`ORENA_EVIDENCE_ARCHITECTURE.md` SS2, SS3: "Projection failure
        # preserves source evidence").
        batch.add_column(sa.Column("ability_policy_version", sa.String(40), nullable=True))
        batch.add_column(sa.Column("passage_difficulty", sa.Float(), nullable=True))
        batch.add_column(sa.Column("ability_before", sa.Float(), nullable=True))
        batch.add_column(sa.Column("ability_after", sa.Float(), nullable=True))

        batch.create_foreign_key(
            "fk_reading_attempt_user", "users", ["user_id"], ["id"], ondelete="CASCADE"
        )
        # Composite: the set, in the attempt's own language. RESTRICT - a
        # content delete can never take learner evidence with it.
        batch.create_foreign_key(
            "fk_reading_attempt_set_scope",
            "reading_comprehension_sets",
            ["set_id", "language_code"],
            ["id", "language_code"],
            ondelete="RESTRICT",
        )
        batch.create_check_constraint(
            "ck_reading_attempt_subject_kind", f"subject_kind IN ({_in_list(SUBJECT_KINDS)})"
        )
        # The two shapes, each exclusive and complete. A generated-session
        # attempt is exactly what it is today, scoped through its session; a
        # set attempt is scoped to the account directly and carries every
        # fact the evidence contract requires.
        batch.create_check_constraint(
            "ck_reading_attempt_generated_shape",
            "subject_kind <> 'generated_session' OR ("
            "session_id IS NOT NULL AND legacy_id IS NOT NULL"
            " AND user_id IS NULL AND language_code IS NULL AND set_id IS NULL"
            " AND ordinal IS NULL AND operation_id IS NULL AND request_digest IS NULL"
            " AND evaluator_version IS NULL AND ability_policy_version IS NULL"
            " AND passage_level IS NULL AND passage_difficulty IS NULL"
            " AND ability_before IS NULL AND ability_after IS NULL)",
        )
        batch.create_check_constraint(
            "ck_reading_attempt_set_shape",
            "subject_kind <> 'comprehension_set' OR ("
            "session_id IS NULL AND legacy_id IS NULL"
            " AND user_id IS NOT NULL AND language_code IS NOT NULL AND set_id IS NOT NULL"
            " AND ordinal IS NOT NULL AND operation_id IS NOT NULL AND request_digest IS NOT NULL"
            " AND evaluator_version IS NOT NULL AND passage_level IS NOT NULL)",
        )
        batch.create_check_constraint(
            "ck_reading_attempt_ability_group",
            "(ability_policy_version IS NULL) = (passage_difficulty IS NULL)"
            " AND (passage_difficulty IS NULL) = (ability_before IS NULL)"
            " AND (ability_before IS NULL) = (ability_after IS NULL)",
        )
        # Counts are bounded for set attempts only: legacy rows keep whatever
        # the old writer and the importer produced, and are not re-judged.
        batch.create_check_constraint(
            "ck_reading_attempt_set_counts",
            "subject_kind <> 'comprehension_set' OR ("
            "total > 0 AND correct_count >= 0 AND correct_count <= total"
            " AND json_array_length(answers) = total)",
        )
        # Each branch is written `x IS NULL OR (...)` so no comparison with a
        # NULL can make the whole CHECK pass by evaluating to unknown.
        batch.create_check_constraint(
            "ck_reading_attempt_set_values",
            "(ordinal IS NULL OR ("
            f"ordinal >= 1 AND operation_id <> '' AND {_hex64('request_digest')}"
            " AND evaluator_version <> '' AND passage_level <> ''))"
            " AND (ability_policy_version IS NULL OR ("
            f"ability_policy_version <> '' AND passage_difficulty {_FINITE}"
            f" AND ability_before {_FINITE} AND ability_after {_FINITE}))",
        )
        # Plain unique constraints over nullable columns: generated-session rows
        # hold NULL here, and NULLs are distinct in a unique constraint on both
        # dialects, so no partial predicate is needed - or can drift. The
        # operation is scoped to the account, not to a language: an id replayed
        # under another language is the same logical action reused, and must be
        # refused, as the backbone's `(incarnation, domain, operation_id)` does.
        batch.create_unique_constraint(
            "uq_reading_attempt_operation", ["user_id", "operation_id"]
        )
        # Also the progression read (`ORDER BY ordinal DESC`), the replay
        # order, and the index account deletion finds a learner's rows by.
        batch.create_unique_constraint(
            "uq_reading_attempt_ordinal", ["user_id", "language_code", "ordinal"]
        )
    # What the RESTRICT check reads when a set is deleted, and "has anyone
    # attempted this set" for the Admin pane.
    op.create_index("ix_reading_attempts_set", "reading_attempts", ["set_id", "language_code"])

    # ---- 5. The ability projection -----------------------------------------
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

    # ---- 6. The lifecycle rules a CHECK cannot express ----------------------
    if _dialect() == "postgresql":
        op.execute(_PG_SET_GUARD)
        op.execute(_PG_QUESTION_GUARD)
        op.execute(_PG_ATTEMPT_GUARD)
        op.execute(_PG_TRUNCATE_GUARD)
        for statement in _PG_TRIGGERS:
            op.execute(statement)
    elif _dialect() == "sqlite":
        for statement in _SQLITE_TRIGGERS:
            op.execute(statement)
    else:  # pragma: no cover - the runtime is PostgreSQL, the test path SQLite
        raise NotImplementedError(f"no lifecycle triggers written for {_dialect()}")


# The footprint a downgrade would destroy. Any of it present means the feature
# has written something a learner did or an admin decided.
_FOOTPRINT = (
    "SELECT 1 FROM reading_attempts WHERE subject_kind = 'comprehension_set'",
    "SELECT 1 FROM reading_comprehension_sets",
    "SELECT 1 FROM reading_ability_projections",
    "SELECT 1 FROM reading_articles WHERE content_kind <> 'article'",
)
_REFUSAL = (
    "20260924_0014 downgrade refused - Adaptive Reading data exists. Downgrade never"
    " removes learner evidence or reviewed content. Roll the code back and keep this"
    " additive schema, or write a reviewed forward repair."
)


def _guard_downgrade() -> None:
    if _dialect() == "postgresql":
        # Lock first, then look. Without the lock a writer that committed
        # while the guard was reading - a draft set, a `content_kind` - would
        # be dropped by the DDL that follows. SHARE ROW EXCLUSIVE blocks every
        # writer and every second downgrade until this transaction ends. SQL,
        # so an offline-rendered downgrade carries the lock and the refusal.
        op.execute(
            "LOCK TABLE reading_articles, reading_comprehension_sets,"
            " reading_comprehension_questions, reading_attempts, reading_ability_projections"
            " IN SHARE ROW EXCLUSIVE MODE"
        )
        conditions = " OR ".join(f"EXISTS ({query})" for query in _FOOTPRINT)
        op.execute(
            f"DO $guard$ BEGIN IF {conditions} THEN"
            f" RAISE EXCEPTION '{_REFUSAL}' USING ERRCODE = '55000'; END IF; END $guard$"
        )
        return
    # SQLite: a SELECT alone opens no transaction under pysqlite's defaults, so
    # a writer could commit between the guard and the DDL and be dropped
    # unseen. A write that changes nothing takes the database's write lock
    # first - no other connection can write until this transaction ends - and
    # only then does the guard look.
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
    with op.batch_alter_table("reading_attempts") as batch:
        batch.drop_constraint("uq_reading_attempt_ordinal", type_="unique")
        batch.drop_constraint("uq_reading_attempt_operation", type_="unique")
        batch.drop_constraint("ck_reading_attempt_set_values", type_="check")
        batch.drop_constraint("ck_reading_attempt_ability_group", type_="check")
        batch.drop_constraint("ck_reading_attempt_set_counts", type_="check")
        batch.drop_constraint("ck_reading_attempt_set_shape", type_="check")
        batch.drop_constraint("ck_reading_attempt_generated_shape", type_="check")
        batch.drop_constraint("ck_reading_attempt_subject_kind", type_="check")
        batch.drop_constraint("fk_reading_attempt_set_scope", type_="foreignkey")
        batch.drop_constraint("fk_reading_attempt_user", type_="foreignkey")
        for column in (
            "ability_after",
            "ability_before",
            "passage_difficulty",
            "passage_level",
            "ability_policy_version",
            "evaluator_version",
            "request_digest",
            "operation_id",
            "ordinal",
            "set_id",
            "language_code",
            "user_id",
            "subject_kind",
        ):
            batch.drop_column(column)
        # Every remaining row is a generated-session attempt (the guard saw no
        # other kind), and the shape CHECK held both columns NOT NULL for it,
        # so restoring NOT NULL rewrites nothing and cannot fail.
        batch.alter_column("legacy_id", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("session_id", existing_type=sa.Uuid(), nullable=False)

    op.drop_index("ix_reading_comprehension_questions_set", table_name="reading_comprehension_questions")
    op.drop_table("reading_comprehension_questions")
    op.drop_index("ix_reading_comprehension_sets_article", table_name="reading_comprehension_sets")
    op.drop_index("uq_reading_comprehension_set_approved", table_name="reading_comprehension_sets")
    op.drop_table("reading_comprehension_sets")

    op.drop_index("uq_reading_article_language_scope", table_name="reading_articles")
    op.execute("ALTER TABLE reading_articles DROP COLUMN content_kind")
