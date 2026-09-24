# Adaptive Reading Practice — schema proposal

    STATUS: ROUND 2 — PROPOSED, NOT APPLIED. Revised against every finding of
            round 1 (docs/project/ADAPTIVE_READING_ARCHITECTURE_REVIEW.md).
            Round 2 is reviewed against the DDL, not prose.
    DDL:    migrations/proposed/20260924_0014_adaptive_reading.py
    PROOF:  tests/test_adaptive_reading_schema_proposed.py
    LANE:   admin/control-center
    DATES:  round 1 2026-09-23, round 2 2026-09-24

This proposes the persistence Adaptive Reading Practice needs, and nothing
else. The DDL sits in `migrations/proposed/`, which Alembic's default
`version_locations` never reads, so no environment can apply it by accident.
Applying it (one `git mv` into `versions/`) needs an APPROVED review **and**
the human's schema/runtime authorization. No Adaptive Reading UI or runtime is
built before the review passes.

---

## What this is for

The human settled the product rule on 2026-09-23:

> Every passage must come from content an Admin deliberately brought in. The
> system does not write source passages with AI. AI is a processor that runs
> *after* the source exists — level, vocabulary, grammar, classification,
> comprehension questions, explanation, evidence.

So Adaptive Reading reads the published Reading corpus and adds three things
the corpus does not have: a reviewed set of comprehension questions per
article, a record of what a learner did with it, and a reading ability that
those records move.

The round-2 decisions the human recorded on 2026-09-24, and where each lands:

| Decision | Where |
| --- | --- |
| Unique active set only when `status = 'approved'`; history never has to be archived to make room | §2, `uq_reading_comprehension_set_approved` |
| RESTRICT upward from learner evidence, never a cascade that loses it | §7 |
| Full account-data contract: idempotency, evaluator/rule version, projection policy/checkpoint/discardable, deletion workflow | §5 |
| Grounding is validated by the service against a specific article body, not assumed of a CHECK | §6 |
| Evidence offsets know which body they index; an article edit cannot silently make them wrong | §6 |
| Every partial index and constraint means the same on PostgreSQL and SQLite | §10 |
| No ability range or datatype that chooses an algorithm | §4, `_FINITE` |
| No cache or state the source data already answers | §3, §4 |
| Source category deferred, no schema | §8 |
| Ingestion method, content kind and source metadata stay separate; enum collisions resolved; no fourth vocabulary | §8 |
| No parallel learner evidence store | §3 |
| Deprecation covers every consumer, not only the learner UI | §9 |
| Text Discussion on a corpus article: explicitly deferred | §9 |
| Downgrade never deletes learner data | §11 |
| A real PostgreSQL constraint proof | §10 |

---

## 1. What exists and is reused, stated accurately this time

| Capability | Where it lives | Reused how |
| --- | --- | --- |
| Published passages with level, topic, word count, targets | `reading_articles` (`20260923_0013`) | read as-is; gains `content_kind` |
| The comprehension-attempt owner | `reading_attempts` (`20260811_0001`) | **extended** with a second subject (§3) |
| Grounding check `evidence not in passage` | `becoming_reading._validate_generated` | the rule is kept; the check moves to the corpus body and becomes offset-exact (§6) |
| Scoring a set of answers | `submit_reading_answers()` | the rule (selected index equals correct index) is kept; it is versioned as `evaluator_version` |
| The learner answering/review surface | `ui/comprehension.js` via `encounter.js` | unchanged by this proposal |

**Correction to round 1 (factual error 5):** the *generator* is **not** reused
as written. `becoming_reading._schema` hard-wires exactly four questions of
exactly four options, produces no `question_type`, no offsets, and a
Vietnamese-only `explanation_vi`. The eight-type enum, the 3–6 rule, 2–6
options, offsets and a declared explanation language require a new prompt and
validator. What is reused is the idea and the grounding test, not the code.

---

## 2. `reading_comprehension_sets` — platform content

One reviewed set of questions for one article, in one support language,
grounded in one exact body.

| Column | Type | Why |
| --- | --- | --- |
| `id` | uuid pk | |
| `article_id` | uuid → `reading_articles` **ON DELETE RESTRICT** | §7 |
| `language_code` | varchar(20) | the article's language; the parent key of the attempts' composite FK, so a zh attempt cannot attach to an en set |
| `support_language` | varchar(20) | the language the explanations are written in (required change 18) |
| `article_body_sha256` | varchar(64) | the grounding anchor: the exact body every offset indexes (§6) |
| `status` | varchar(20) | `draft`, `needs_review`, `approved`, `rejected`, `stale`, `archived` |
| `generator_version`, `model` | varchar | which processor and model produced it, so a bad batch can be found |
| `validation_json` | json | validation issues, type coverage, grounding failures — renamed from `analysis_json` so it cannot be read as the article's column of that name |
| `reviewed_by`, `reviewed_at`, `review_reason` | | |
| `created_at`, `updated_at` | timestamptz | |

Constraints and triggers (all in the DDL):

- `uq_reading_comprehension_set_approved` — **`UNIQUE (article_id, support_language) WHERE status = 'approved'`**,
  declared with both `postgresql_where` and `sqlite_where`. An inclusion
  predicate (factual error 1 corrected). A rejected set, a stale set and an
  archived set never block a replacement; nothing is archived to make room
  (blocker 1).
- `uq_reading_comprehension_set_scope` — `UNIQUE (id, language_code)`, the
  parent key the attempts reference.
- CHECKs: status enum; hash is 64 lowercase hex; identity fields non-empty; a
  decided set has `reviewed_at`.
- `reading_comprehension_set_guard` (trigger): a set is **created** undecided;
  status moves only along review transitions (`draft→needs_review`,
  `needs_review→draft|approved|rejected`, `approved→stale|archived`,
  `stale→approved|archived`); **entering `approved` requires at least one
  approved question and no undecided one** (required change 12); once decided
  its article, languages, anchor, generator and model are **frozen**; a set
  that reached learners (`approved`, `stale`, `archived`) **cannot be deleted**.
- `question_count` is gone (reviewer: non-minimal): the Admin list counts over
  `ix_reading_comprehension_questions_set`.

**Why a set and not a flag on the article** (kept): an article can have a
rejected set and a new one being prepared, in more than one support language,
and the review history of the questions is not the review history of the
passage.

## 3. The evidence store: `reading_attempts` is extended, not paralleled

Round 1 proposed `reading_practice_attempts`. The reviewer's out-of-scope
finding was right: it sat one word away from `reading_attempts`, and
`ORENA_ACCOUNT_DATA_ARCHITECTURE.md` says "Reuse equivalent existing records
rather than adding parallel ones" (§3) and "Existing evidence remains owned by
existing repositories; no parallel authoritative store" (§6.7). The records
*are* equivalent: both are "a learner's submitted answers to the comprehension
questions of a reading passage, with how many were right". Two tables would be
two authorities for one evidence kind, and every reader of reading evidence
would have to know both.

So the round-2 answer is the first option the human named: **the existing
attempt is extended.** `reading_attempts` gains a discriminator and the facts a
set attempt needs; every existing row and every write from today's code stays
exactly what it is.

| Column | Generated-session attempt (existing) | Set attempt (new) |
| --- | --- | --- |
| `subject_kind` | `generated_session` (server default) | `comprehension_set` |
| `session_id`, `legacy_id` | NOT NULL (now nullable columns) | NULL |
| `user_id` → `users` CASCADE, `language_code` | NULL (scoped through the session) | NOT NULL |
| `set_id` + `language_code` → sets `(id, language_code)` **RESTRICT** | NULL | NOT NULL |
| `ordinal` | NULL | 1, 2, 3 … per account and language |
| `operation_id`, `request_digest` | NULL | NOT NULL (§5.1) |
| `evaluator_version`, `ability_policy_version` | NULL | NOT NULL (§5.2) |
| `passage_level`, `passage_difficulty` | NULL | NOT NULL |
| `ability_before`, `ability_after` | NULL | NOT NULL |
| `answers`, `correct_count`, `total`, `created_at` | as today | reused: `[{question_id, selected_index, correct}]`, bounded |

- `ck_reading_attempt_generated_shape` and `ck_reading_attempt_set_shape` make
  the two shapes **exclusive and complete**.
- `ck_reading_attempt_set_counts` bounds set attempts only: `total > 0`,
  `0 <= correct_count <= total`, `json_array_length(answers) = total`. Legacy
  rows keep whatever the old writer and the importer produced; they are not
  re-judged by a constraint added after the fact.
- `reading_attempt_guard` (trigger): an attempt meets **only an approved set**,
  and a set attempt is **immutable** evidence. Legacy rows are untouched — the
  importer's upsert of them keeps working.
- `score` is gone (required change 13): it is `correct_count / total`, and a
  later change to scoring is captured by `evaluator_version` plus the per-answer
  `correct` flags, which are the facts.
- `article_id` on the attempt is gone: sets are never deleted once they have
  attempts (RESTRICT) or once they reached learners (trigger), so the set's own
  `article_id` is always there.
- `completed_at` is gone (required change 16): **an attempt row exists only once
  it is submitted.** An in-progress answer sheet is device work, not evidence
  (`ORENA_ACCOUNT_DATA_ARCHITECTURE.md` §2, "Draft/reading response"), so there
  is no half-written evidence row, no NULL state and no partial index for it.
- `passage_difficulty` is new: the number the ability policy actually consumed.
  `passage_level` alone would leave `ability_before → ability_after`
  unexplainable after the level-to-number mapping changes (the reviewer's
  "storing only `passage_level` hard-codes the algorithm").

**What this costs, stated rather than discovered:** one table carries two row
shapes, and the old shape is scoped through `reading_sessions` while the new one
is scoped directly. The account-deletion enumeration therefore names two
predicates for this table (§5.4), and a reader that inner-joins attempts to
sessions sees only the old shape — which is exactly the consumer work §9 makes a
precondition of moving any learner to the new route.

## 4. `reading_ability_projections` — a discardable learner projection

| Column | Type | Why |
| --- | --- | --- |
| `id` | uuid pk | surrogate key, as every learner table in this repository |
| `user_id` | uuid → `users` CASCADE | a real FK (required change 3) |
| `language_code` | varchar(20) | ability is per language |
| `policy_version` | varchar(40) | the ability policy this row was built under |
| `ability` | **Float**, `BETWEEN -1000000 AND 1000000` | wide and finite: a logit, an IRT theta and an Elo rating all fit; `NaN` and infinities are refused on both dialects (required changes 14, 15) |
| `consumed_through_ordinal` | int ≥ 0 | the checkpoint |
| `by_question_type_json` | json | accuracy per type, which steers coverage in selection |
| `updated_at` | timestamptz | |

`UNIQUE (user_id, language_code, policy_version)`. The reviewer asked for
`UNIQUE (user_id, language_code)`; the policy version is added because
`ORENA_EVIDENCE_ARCHITECTURE.md` §3 defines projection identity as
"account + learning language + projection-policy version", and it lets a new
policy build beside the old one and selection switch when it is complete.

`recent_json` is gone (required change 7): `uq_reading_attempt_ordinal`
answers "the last N outcomes" with an index-only walk. `attempts` is gone:
ordinals are contiguous, so `consumed_through_ordinal` *is* how much evidence
the estimate rests on.

**Why a table and not a derived read** (kept): selection runs on every passage
request and must not replay a learner's history to answer. The evidence
architecture allows exactly this — "if a materialized projection is needed" —
on the condition that it is rebuildable, which §5.3 makes true.

## 5. The account-data contract — the four missing requirements

### 5.1 Idempotency (`ORENA_ACCOUNT_DATA_ARCHITECTURE.md` §4)

A submit carries an `operationId` chosen by the client for **one logical
submit**, reused on every retry of it. The set attempt row is its own receipt:
the committed result the contract asks a receipt to point at *is* that row, and
it is immutable. `uq_reading_attempt_operation` =
`UNIQUE (user_id, language_code, operation_id)` — a plain unique constraint:
legacy rows hold NULL there and NULLs are distinct on both dialects, so no
partial predicate is needed.

The submit transaction (PostgreSQL; the SQLite backend refuses the write, as
`save_listening_progress_record` and the Text Discussion repository already
do):

1. Scope comes from the server, never the body.
2. Look up `(user, language, operation_id)`. Found with an equal
   `request_digest` → return that row: `committed`, and **the ability step is
   not applied again**. Found with a different digest → `rejected
   {operation_reused}`.
3. `INSERT … ON CONFLICT DO NOTHING` the projection row for the active policy,
   then `SELECT … FOR UPDATE` it. This lock serializes every set-attempt write
   for one learner and language. If its checkpoint is behind the attempts (it
   was discarded), rebuild it here first.
4. Re-check the operation under the lock (a duplicate may have committed while
   this one waited).
5. Validate: the set is approved, in the learner's language and support
   language, and still grounded (§6); the answers name exactly the set's
   approved questions.
6. Score under `evaluator_version`; compute `ability_after` under the active
   `ability_policy_version`; insert the attempt with
   `ordinal = consumed_through_ordinal + 1`; advance the projection. Commit.

A raced duplicate that slips past step 4 hits the unique constraint, rolls back
with no success receipt, and re-reads step 2. `uq_reading_attempt_ordinal`
is the backstop that two different attempts can never claim one checkpoint
slot. `request_digest` is SHA-256 over the canonical command
(`reading.comprehension_attempt.submit`, set id, sorted
`question_id → selected_index`); it is the guard against reuse, **not** the
identity — two distinct attempts with the same answers are two attempts.

### 5.2 Evaluator and rule versions

`evaluator_version` records how the answers were judged; `ability_policy_version`
records which rule moved `ability_before` to `ability_after`. Both NOT NULL on
every set attempt (`ck_reading_attempt_set_shape`), non-empty
(`ck_reading_attempt_set_values`).

### 5.3 Projection: policy version, checkpoint, discardable

- **Policy version** — part of the projection's identity (§4).
- **Checkpoint** — `consumed_through_ordinal`. An attempt applies only as
  `checkpoint + 1`, so a re-delivery is a no-op and an out-of-order one cannot
  apply (`ORENA_EVIDENCE_ARCHITECTURE.md` §3, "Apply an evidence version once").
- **Discardable** — every value is recomputed by replaying the account's set
  attempts in ordinal order under the policy version, from facts the attempts
  hold (`passage_difficulty`, per-answer correctness, and each question's type
  from its frozen set). Deleting a row costs a rebuild, never evidence; the
  proof deletes one and shows the attempts untouched. The attempts' own
  `ability_before/after` are the historical record of what the policy said *at
  the time*; a rebuild under a new policy writes a new projection row and never
  rewrites them.

### 5.4 Deletion workflow enumeration (D-054, D-055)

The account-deletion workflow is not built, and D-055's gate
(`tests/test_deletion_journal.py::test_no_runtime_code_deletes_or_re_registers_an_account_yet`)
keeps any runtime path from deleting an account until it is. What it must
delete for Reading is now enumerated in the migration as `ACCOUNT_OWNED`:

| Table | Predicate | Kind |
| --- | --- | --- |
| `reading_attempts` | `subject_kind = 'comprehension_set' AND user_id = :user_id` | evidence, keyed to the account |
| `reading_attempts` | `session_id IN (SELECT id FROM reading_sessions WHERE user_id = :user_id)` | evidence, keyed through the session (already `ON DELETE CASCADE` from the session) |
| `reading_ability_projections` | `user_id = :user_id` | projection — discardable, so deleting it first or last is equally safe |

The proof runs that enumeration for one of two learners and shows the other
learner and every platform row untouched, and separately that the `users`
foreign keys cascade. Deleting a learner's attempts never meets a RESTRICT: the
attempts are the children. On restore, the workflow's replay (D-054) applies
the same predicates. At apply time the enumeration also joins the owner-table
list the deletion workflow will consume, and `reading_attempts` joins
`runtime_backup.COMPARED` (it is missing today).

**Incarnation keying:** these rows are keyed by `user_id`, as every existing
domain owner is (`saved_words`, `speaking_attempts`, `listening_progress`),
not by the gated backbone's account incarnation. Keying new learner evidence to
the incarnation is the account-architecture decision `AGENTS.md` §7 reserves;
this proposal does not make it.

## 6. Revision and grounding

**Correction to round 1 (factual error 2), restated:** no CHECK in this schema
proves that evidence is in the passage. A CHECK cannot read
`reading_articles.body`. The database enforces only the *structure* of a span;
**grounding is the service's check, against one exact body.**

What the database enforces, on both dialects:

- evidence is all-or-nothing (`evidence_text`, `evidence_start`, `evidence_end`);
- a present span is non-empty, starts at ≥ 0, and
  `evidence_end - evidence_start = length(evidence_text)` — which is what catches
  offsets counted in bytes or UTF-16 units instead of characters (proved with a
  Chinese span);
- every type except `main_idea` and `authors_purpose` must carry evidence;
  those two may rest on the whole passage (the reviewer's open question,
  answered).

What anchors the offsets: `article_body_sha256` on the set.
`content_revision` **cannot** be the anchor — `update_article` bumps it for a
title, excerpt, topic or level change, `set_status` bumps it on every publish,
and a target decision bumps it too, so a set keyed to it would go stale on
events that do not move a single character of the body. The hash moves exactly
when the offsets could become wrong, and a body reverted to the anchored text
is correctly valid again.

The service's rules (built after approval, specified now):

1. **Generation** computes offsets from the body itself — never taken from the
   model — and requires `body[start:end] == evidence_text`.
2. **Approval** recomputes SHA-256 of the current body, requires it to equal the
   anchor, and re-verifies every span. A draft whose article changed is
   re-anchored while still undecided (allowed by the trigger); a decided set's
   anchor is frozen.
3. **An article body edit** (`update_article` with `body` among the changes)
   moves every approved set of that article whose anchor no longer matches to
   `stale`, **in the same transaction**, with a review event. It is visible to
   the Admin, never silent.
4. **Serving and submitting** re-check the hash. A mismatch means the set is not
   served — the article is Free Reading for that learner — and a submit is
   `rejected {set_stale}`. This holds even if rule 3 were ever skipped.
5. **`stale → approved`** is allowed only when the hash matches again.

Offsets are Unicode code points into the body (Python string indices); the
browser converts to UTF-16 for highlighting.

**Stated limit:** the exact text of an article body that has since been edited
is not retained. Attempts on it stay interpretable — each names its frozen set,
whose questions keep their prompt, options, answer, explanation and the literal
`evidence_text` — and the hash identifies which body it was. Retaining whole
article revisions would be a change to the engine's article model, not to this
feature, and is not proposed.

**Explanation language (required change 18):** questions and options are in the
passage's language; the explanation is in the set's `support_language`. A
learner meets the approved set in their support-language setting. With none,
the article is Free Reading for them: nothing is machine-translated at read
time, and no Vietnamese is assumed.

## 7. Deletes — RESTRICT upward from evidence (blocker 2)

| Foreign key | ON DELETE | Why |
| --- | --- | --- |
| attempt `(set_id, language_code)` → set | **RESTRICT** | no content delete can take learner evidence |
| set → article | **RESTRICT** | an article no longer takes its sets with it |
| question → set | CASCADE | downward; only a deletable set can be deleted at all |
| attempt → user, projection → user | CASCADE | owner, as every learner table |
| attempt → session (existing) | CASCADE | unchanged |

Plus the set trigger: a set that reached learners (`approved`, `stale`,
`archived`) is never deleted, whether or not anyone attempted it yet. An
Admin purge of an article therefore deletes its `draft`, `needs_review` and
`rejected` sets explicitly first, then the article; an article whose set ever
reached learners is archived, never purged. Both refusals raise — nothing is
taken silently and nothing blocks silently. All proved.

## 8. `content_kind` and the vocabularies

`reading_articles.content_kind varchar(20) NOT NULL DEFAULT 'article'`,
`CHECK (content_kind IN ('article', 'news'))`.

Round 1 proposed five values. Three collided or were invented:

| Axis | Column | Values | Meaning |
| --- | --- | --- | --- |
| How content arrives | `reading_sources.source_type` | `manual, direct_url, file, rss, api, feed` | ingestion method |
| What form a learner sees | `reading_articles.content_kind` | **`article, news`** | editorial form |
| Which id space a discussion keys to | `text_discussions.source_kind` | `story, media, reading_session, book_chapter` | routing identity, not a form |
| (retired) form requested of the AI generator | `ReadingGenerateIn.material` | `article, book, news, quote` | never stored; removed with the generator (§9 step 3) |

- **`book_excerpt` is dropped.** A book is its own catalog (`reading_books`,
  `20260916_0009`), which the Library already renders as Book. A second "book"
  inside the article catalog would be two answers to one question.
- **`story` is dropped.** It is a `text_discussions.source_kind` routing value;
  as a content form it would read as the same word meaning something else.
- **`essay` is dropped.** Nobody asked for it — the learner lane asked to tell
  Book, Article and News apart — and adding a value later is a CHECK change.
- **No fourth vocabulary.** `content_kind` uses `material`'s own words for the
  same meanings (`article`, `news`), and `material` leaves with the generator.

Default `'article'` because every existing row is one: `ADD COLUMN … DEFAULT`
backfills in the catalogue and no data migration runs. At apply,
`content_kind` joins `LEARNER_VISIBLE_FIELDS` and the learner list projection
(required change 17), so changing it moves `content_revision` like any other
card field.

**Source category: deferred entirely, no schema.** The reviewer's judgement
stands — it has zero occurrences in the repository and the work it would do is
done by the source's rights columns.

## 9. Deprecating the AI-generated passage flow — every consumer

`becoming_reading.create_reading_session` writes a passage with AI, which the
settled rule forbids. It is a live learner surface, so it is not removed in the
change that replaces it. **Nothing in this proposal changes its behaviour.**

**Correction to round 1 (required change 20):** the reading evidence has more
readers than the learner UI. Every one of them reads through
`list_reading_sessions()` or joins `reading_attempts` to `reading_sessions`,
so none of them would see a set attempt:

| # | Consumer | How it reads today | What would happen at step 2 |
| --- | --- | --- | --- |
| 1 | Reading studio | `/api/reading/*` → `becoming_reading` | keeps working for sessions; the corpus route is new |
| 2 | `/api/cross-skill-cue` | `app.py` → `list_reading_sessions(20)` → `cross_skill_transfer._reading` | would stop seeing new reading — cue silently degrades |
| 3 | I4 collection registry | `configure_collection(reading=list_reading_sessions)` → `collection_query.reading_entries` | same; and `int(row['id'])` would raise on a uuid-keyed item, which the owner catches as "no entries" |
| 4 | I6 learner summary | `configure_learner_summary(reading=list_reading_sessions)` | same — summary silently degrades |
| 5 | Admin learner activity | `admin_repository` inner-joins attempts to sessions | set attempts invisible to the Admin |
| 6 | Product activity events | `specialized_repository.list_product_activity_events`, same join | reading funnel undercounts |
| 7 | Text Discussion | `discussion_repository` resolves a `reading_session` | unaffected; corpus articles are not a source kind yet (below) |
| 8 | Import / read-compare tooling | `importer.py`, `read_compare.py` count through the session join | legacy tooling; unaffected, counts legacy rows only |

The three steps, with the gates they now carry:

1. **Now (this schema, once approved and authorized):** set attempts start
   being written by the corpus route. The generated route keeps working. It is
   marked deprecated in code and in `LEGACY_TOMBSTONES.md`.
2. **Before any learner entry point moves to the corpus route:** consumers 2–6
   read through one Reading-domain read contract, `list_reading_evidence`,
   returning both subject kinds in one item shape
   (`subject: {kind: 'generated_session', id} | {kind: 'comprehension_set', article_id, set_id}`,
   title, time, latest result), each with a test that a set attempt appears in
   it. This is a hard precondition: moving the entry points first is exactly
   the silent regression the reviewer found. The old route stays reachable by
   an existing session id, so an attempt in flight is not lost.
3. **Then, under its own authorization:** the generator and its prompts are
   removed. `reading_sessions` and the generated-session rows of
   `reading_attempts` stay, read-only, because they are learner evidence; they
   are never down-migrated.

**Text Discussion on a corpus article: deferred, not in this milestone.**
`text_discussions.source_kind` allows `story, media, reading_session,
book_chapter` and has no value for a corpus article, so a discussion cannot
attach to one. Adding `reading_article` changes the D-072.2 contract that its
own four review rounds approved, and belongs in a proposal to that table, not
to this one. Until then a corpus article offers no discussion. `content_kind`
was chosen so that proposal will not collide with it (§8).

## 10. Parity and the PostgreSQL constraint proof (blocker 5, required change 19)

The rule is written into the DDL, not into prose:

- The one partial index, `uq_reading_comprehension_set_approved`, carries both
  `postgresql_where` and `sqlite_where`.
- The two uniqueness rules over legacy-shaped rows (operation, ordinal) are
  **plain** unique constraints over nullable columns: NULLs are distinct in a
  unique constraint on both dialects, so there is no predicate to drift.
- JSON bounds use `json_array_length`, span length uses `length()`: both exist
  on both dialects and count the same way.
- The lifecycle rules a CHECK cannot express are triggers, written once per
  dialect in the migration. SQLite serializes writers on the whole database,
  so it needs no `FOR SHARE`; on PostgreSQL the question and attempt guards
  take `FOR SHARE` on the set, which is what serializes a question write
  against the set's approval (proved with two connections and a lock timeout).

`tests/test_adaptive_reading_schema_proposed.py` runs **one scenario list on
both dialects** and requires one outcome:

- **SQLite, always (including CI):** the current ORM schema built as the
  hermetic suite builds it (`create_all`, foreign keys on), then the proposal's
  `upgrade()` through Alembic's own operations.
- **PostgreSQL, under `ORENA_TEST_POSTGRES_URL`:** the real chain
  `20260811_0001 → 20260923_0013`, then the proposal, in a fresh schema per run
  that is dropped afterwards.

It writes the row each constraint and trigger must refuse, reads the partial
predicate back from `pg_indexes` / `sqlite_master`, reads every `ON DELETE`
back from `pg_constraint` / `PRAGMA foreign_key_list`, rehearses up → down → up
with data present, proves the downgrade refusal, and checks the refusal is in
the offline-rendered (`--sql`) downgrade.

**Local execution, 2026-09-24 — not CI:** PostgreSQL 16.13, 46 passed, 1
skipped (the two-connection serialization case is PostgreSQL-only by design);
SQLite alone, 23 passed. CI will run the SQLite half on every push; the
PostgreSQL half runs wherever `ORENA_TEST_POSTGRES_URL` is set.

At apply, `models.py` gains the same declarations (both `where` clauses, the
CHECKs, and the SQLite triggers attached with `DDL(...).execute_if(dialect='sqlite')`),
and a parity test compares the ORM-built schema with the migrated one.

## 11. Migration, rollback and downgrade

**Upgrade** is additive and transactional on PostgreSQL (all or nothing): two
new tables, one new projection table, one defaulted column on
`reading_articles`, and on `reading_attempts` two `DROP NOT NULL`s, thirteen
nullable-or-defaulted columns, two FKs, five CHECKs and two unique
constraints. No existing row is rewritten. `ADD CONSTRAINT` validates by
scanning `reading_attempts` and `reading_articles`, which are small today; if
either were large at apply time the constraints would be added `NOT VALID` and
validated separately.

**Old code on the new schema** — the real rollback path — keeps working: every
new column is nullable or has a server default, so today's writer and the
importer, which name none of them, write valid generated-session rows. The
proof inserts and reads through the unchanged `ReadingAttempt` model after the
upgrade.

**Downgrade never removes learner data.** Its first statement is a guard that
runs in the database's own transaction: if any set attempt, any set, any
projection row, or any `content_kind` other than `article` exists, it raises
and nothing is dropped. On PostgreSQL the guard is a `DO` block, so an
offline-rendered downgrade script carries it too. With no footprint, the
downgrade drops the new objects and restores `NOT NULL` on `session_id` and
`legacy_id` — which rewrites nothing, because the shape CHECK held both non-null
for every remaining row. Proved on both dialects: a legacy attempt survives a
downgrade intact; after the feature writes one attempt, the downgrade refuses
and the schema is unchanged.

Once the feature has written anything, rollback is what
`ORENA_ACCOUNT_DATA_ARCHITECTURE.md` §6 names: roll the code back and keep the
additive schema, or apply a reviewed forward repair.

**Chain position:** revises `20260923_0013`, today's head on this lane. If
another lane lands a `0014` first, this file is rebased the way the engine's
was, so the chain stays linear.

## 12. Apply-time work (not in this change)

Specified so the reviewer can check it; none of it is built before approval:
`models.py` declarations and the ORM parity test; the Reading repository's
submit transaction (§5.1), ability rebuild (§5.3) and `list_reading_evidence`
(§9); the engine's `update_article` staleness transition (§6 rule 3);
`content_kind` in `LEARNER_VISIBLE_FIELDS` and the publish contract;
`reading_attempts` in `runtime_backup.COMPARED`; the deprecation marker. The
SQLite runtime repository refuses the set-attempt write, as it refuses
Listening progress and Text Discussion turns today.

## 13. What is deliberately not proposed (unchanged)

- **No ML.** The first ability rule is deterministic, explainable and testable,
  in code with tests, versioned by `ability_policy_version`.
- **No new vocabulary storage.** Words from a passage go to the existing flow.
- **No change to Free Reading.** An article without an approved set in the
  learner's support language is read and nothing else.
- **No source category.** Deferred.
- **No cross-container locking or media-storage migration.** Unchanged and
  recorded in `ADMIN_DESIGN_ALIGNMENT.md`.

## Answers to round 1, item by item

### Blockers

| # | Finding | Answer | Proof |
| --- | --- | --- | --- |
| 1 | Partial unique forbade the workflow | `WHERE status = 'approved'`, on `(article_id, support_language)` | rejected + replacement coexist; second approved refused; stale blocks nothing |
| 2 | Article purge → lost evidence | RESTRICT on attempt→set and set→article; decided sets undeletable | purge refused with evidence; purge path for undecided/rejected sets works |
| 3 | Written without the account-data spec | §5: operation id + digest, evaluator and policy versions, checkpoint + discardable projection, `ACCOUNT_OWNED` | retry refused; missing facts refused; enumeration deletes one learner only |
| 4 | Offsets into an editable body | `article_body_sha256` anchor + staleness + serve/submit re-check | anchor frozen once decided; stale → re-approve / archive |
| 5 | One-dialect partial index | both `where` clauses; plain uniques where a predicate is not needed; same scenarios on both | catalogue read-back on both |

### Required changes

| # | Change | Answer |
| --- | --- | --- |
| 1 | approved-only predicate | done (§2) |
| 2 | explicit ON DELETE, RESTRICT upward | done (§7) |
| 3 | `user_id` a real FK | done, on the attempt and the projection |
| 4 | uuid surrogate + unique on ability | done, `(user_id, language_code, policy_version)` (§4) |
| 5 | rule/evaluator + projection policy version, rebuildable | done (§5.2, §5.3) |
| 6 | idempotency key | done, `(user, language, operation_id)` + digest (§5.1) |
| 7 | drop `recent_json` | done |
| 8 | partial progression index | superseded: no incomplete rows exist, so `uq_reading_attempt_ordinal` is the progression index, with no predicate |
| 9 | mutual-exclusion CHECK + `machine_suggested` | done, on questions |
| 10 | `rank >= 0`, reconsider unique rank | `rank >= 0`; rank **not** unique, as the targets — a unique rank would need a deferrable constraint SQLite lacks; the approval service renumbers ranks |
| 11 | bound `correct_index` above | `correct_index < json_array_length(options_json)`, options 2–6 |
| 12 | approved set has ≥ 1 question | trigger: ≥ 1 approved question and 0 undecided |
| 13 | bound `score` | dropped; derivable |
| 14 | Float, not Numeric | done |
| 15 | widen ability | ±1,000,000, finite (§4) |
| 16 | state the `completed_at` rule | dropped: a row exists only once submitted (§3) |
| 17 | `content_kind` in the learner projection | apply-time, specified (§8, §12) |
| 18 | explanation language | `support_language` on the set (§6) |
| 19 | PostgreSQL constraint proof | done, both dialects (§10) |
| 20 | name the other readers | eight consumers (§9) |
| 21 | correct the six factual errors | below |

### Factual errors

1. The engine's `request_hash` index is an **inclusion** predicate. This
   proposal's is one too, and does not claim to copy anything.
2. No CHECK proves grounding (§6).
3. The targets' `(article_id, rank)` index is not unique and does carry
   `rank >= 0`. The questions now match that shape exactly.
4. The targets' `machine_suggested` and mutual-exclusion CHECK are copied.
5. The generator is not reusable as written (§1).
6. The engine's migration is in `migrations/versions/`, applied to the lane
   sandbox under the 2026-09-23 authorization; this proposal is the only file
   in `migrations/proposed/`.

## Review questions for round 2

1. Is extending `reading_attempts` with a discriminator the right reading of
   "reuse equivalent existing records", against a new table plus a shared read
   contract?
2. Is the body hash, rather than a body revision counter on the article, the
   right grounding anchor?
3. Are the triggers the right place for the lifecycle rules, given that they
   are written twice, or should any of them be repository-only?
4. Is anything in the apply-time list (§12) something the schema should carry
   now instead?
