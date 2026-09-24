# Adaptive Reading Practice — schema proposal

    STATUS: PROPOSED, NOT APPLIED. Round 1 (prose) and round 2 (DDL,
            4563908) REQUEST CHANGES; round 3 (c7050d6) APPROVED WITH REQUIRED
            CHANGES, no blockers. The two schema-level required changes are
            made here (RC1, RC2); RC3 is apply-time. See
            docs/project/ADAPTIVE_READING_ARCHITECTURE_REVIEW.md.
    DDL:    migrations/proposed/20260924_0014_adaptive_reading.py
    PROOF:  tests/test_adaptive_reading_schema_proposed.py
    LANE:   admin/control-center
    DATES:  round 1 2026-09-23, rounds 2 and 3 2026-09-24

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
| `article_id` | uuid; `(article_id, language_code)` → `reading_articles (id, language)` **ON DELETE RESTRICT** | §7 |
| `language_code` | varchar(20) | the article's language, **bound to it** by that composite FK (round-2 R11), and the parent key of the attempts' composite FK — so article → set → attempt cannot change language anywhere |
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
  parent key the attempts reference. `uq_reading_article_language_scope` —
  a unique **index** on `reading_articles (id, language)`, the parent key the
  set references: an index, not a constraint, so SQLite need not rebuild
  `reading_articles` (which other tables reference) to add it; `id` is already
  unique, so it adds no rule to the article.
- CHECKs: status enum; the hash is 64 characters that are **all lowercase hex**
  (`ltrim(x, '0123456789abcdef') = ''`, portable to both dialects — round 2
  found the round-2 CHECK accepted `'g' * 64`); identity fields non-empty; a
  decided set has `reviewed_at` **and a non-empty `reviewed_by`**.
- `reading_comprehension_set_guard` (trigger): a set is **created** undecided;
  status moves only along review transitions (`draft→needs_review`,
  `needs_review→draft|approved|rejected`, `approved→stale|archived`,
  `stale→approved|archived`); **entering `approved` requires at least one
  approved question and no undecided one** (required change 12); once decided
  its article, languages, anchor, generator and model are **frozen**, and its
  reviewer fields change only on a transition **into** `approved` or
  `rejected` — a new decision names its own reviewer; staling and archiving
  keep the decision's, and nobody rewrites an earlier one (round-3 RC2); a set that reached
  learners (`approved`, `stale`, `archived`) **cannot be deleted**. Every set
  decision is also written to `reading_review_events` on its article by the
  service, so the history of decisions survives a re-approval.
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
| `evaluator_version`, `passage_level` | NULL | NOT NULL |
| `ability_policy_version`, `passage_difficulty`, `ability_before`, `ability_after` | NULL | **all four or none** (B1): NULL means "not measured" |
| `answers`, `correct_count`, `total`, `created_at` | as today | reused: `[{question_id, selected_index, correct}]`, bounded |

- `ck_reading_attempt_generated_shape` and `ck_reading_attempt_set_shape` make
  the two shapes **exclusive and complete**.
- `ck_reading_attempt_ability_group` makes the ability measurement all-or-none
  (round-2 blocker B1). The answers are the evidence; the measurement is what a
  policy made of them. If the active policy cannot measure an attempt — it has
  no difficulty mapping for this level, it produces a value out of range, a
  replay fails — the attempt still commits with the four columns NULL,
  "not measured, not zero" (`ORENA_EVIDENCE_ARCHITECTURE.md` §2: "Unknown is not
  zero"; §3: "Projection failure preserves source evidence and ordinary
  practice access"). Round 2 made them NOT NULL, which made evidence depend on
  the projection succeeding.
- `ck_reading_attempt_set_counts` bounds set attempts only: `total > 0`,
  `0 <= correct_count <= total`, `json_array_length(answers) = total`. Legacy
  rows keep whatever the old writer and the importer produced; they are not
  re-judged by a constraint added after the fact.
- `reading_attempt_guard` (trigger): an attempt meets **only an approved set**,
  and a set attempt is **immutable** evidence. Legacy rows are untouched — the
  importer's upsert of them keeps working.
- `answers` is one JSON column holding two element shapes: legacy rows hold
  option indexes (`[0, 2, 1]`), set attempts hold
  `[{question_id, selected_index, correct}]`. No portable CHECK can test the
  element shape (PostgreSQL and SQLite path syntax differ), so the database
  bounds only the length, and **the service validates every element** before
  it writes. The proof shows the database alone accepts `[0]` on a set attempt
  (round-2 R10).
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
precondition of the first set-attempt write. A later, separately authorized
backfill of `user_id`/`language_code` onto legacy rows would give deletion one
predicate; it is not proposed now.

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
"account **incarnation** + learning language + projection-policy version" — this
schema keys the account by `user_id`, not the incarnation, for the reason in
§5.5 — and it lets a new policy build beside the old one and selection switch
when it is complete.

`recent_json` is gone (required change 7): "the last N outcomes" is a backward
walk of `uq_reading_attempt_ordinal` that stops after N rows — bounded, though
not index-only, since `correct_count`/`total` are read from the rows (round 2
F4 corrected the round-2 wording). `attempts` is gone: the service allocates
ordinals contiguously, so `consumed_through_ordinal` is how much evidence the
estimate rests on. Contiguity is the service's invariant, not the database's:
the database refuses a duplicate ordinal, not a gap.

**Why a table and not a derived read — corrected (round-2 R8).** Round 2 said
selection "must not replay a learner's history". That was wrong for the
ability itself: the current ability under a policy is the latest measured
attempt's `ability_after`, one bounded read. The table is kept for what is
**not** one read: accuracy **per question type**, which is an aggregate over
every attempt's answers joined to their questions' types; the ability when
recent attempts were **not measured** (B1), which the projection carries
through; and **policy transitions**, where a new policy's row is built beside
the old one without rewriting any attempt. **The attempts are authoritative**:
where the projection and a replay of the attempts disagree, the projection is
wrong and is rebuilt.

## 5. The account-data contract — the four missing requirements

### 5.1 Idempotency (`ORENA_ACCOUNT_DATA_ARCHITECTURE.md` §4)

A submit carries an `operationId` chosen by the client for **one logical
submit**, reused on every retry of it. The set attempt row is its own receipt:
the committed result the contract asks a receipt to point at *is* that row, and
it is immutable. `uq_reading_attempt_operation` =
`UNIQUE (user_id, operation_id)` — scoped to the account, **not** to the
language (round-2 R7: with the language in the key, the same `operationId`
replayed under another language committed a second attempt; the backbone's
`mutation_receipts` scopes by `(incarnation, domain, operation_id)` for the same
reason). A plain unique constraint: legacy rows hold NULL there and NULLs are
distinct on both dialects, so no partial predicate is needed.

The submit transaction (PostgreSQL; the SQLite backend refuses the write, as
`save_listening_progress_record` and the Text Discussion repository already
do):

1. Scope comes from the server, never the body.
2. Look up `(user, operation_id)`. Found with an equal `request_digest` →
   return that row: `committed`, and **the ability step is not applied again**.
   Found with a different digest → `rejected {operation_reused}`.
3. Take `pg_advisory_xact_lock` on the pair `(account, language)`. This lock —
   **not** the discardable projection row, which round 2 used and which made
   every submit depend on the projection existing — serializes every
   set-attempt write for one learner and language, and is released at commit
   or rollback.
4. Re-check the operation under the lock (a duplicate may have committed while
   this one waited).
5. Validate, under `SELECT … FOR SHARE` of the article row (§6): the set is
   approved, in the learner's language and support language, and still
   grounded; the answers name exactly the set's approved questions, each
   element well-formed.
6. Score under `evaluator_version`. Allocate
   `ordinal = max(ordinal) + 1` for the pair — one backward step of
   `uq_reading_attempt_ordinal`.
7. **The measurement, best-effort, inside a savepoint:** bring the active
   policy's projection up to date (it may be missing or behind), compute
   `ability_after`. If that fails, roll back to the savepoint and write the
   four ability columns NULL; the projection is left behind its checkpoint,
   which is exactly what "stale" means, and the next rebuild catches it up.
8. Insert the attempt, advance the projection if it was measured. Commit.

The evidence therefore commits whether or not the projection can be built —
proved: an attempt commits with the measurement NULL and no projection row at
all. A raced duplicate that slips past step 4 hits the unique constraint, rolls
back with no success receipt, and re-reads step 2. `uq_reading_attempt_ordinal`
is the backstop that two different attempts can never claim one ordinal. `request_digest` is SHA-256 over the canonical command
(`reading.comprehension_attempt.submit`, set id, sorted
`question_id → selected_index`); it is the guard against reuse, **not** the
identity — two distinct attempts with the same answers are two attempts.

### 5.2 Evaluator and rule versions

`evaluator_version` records how the answers were judged: NOT NULL on every set
attempt (`ck_reading_attempt_set_shape`), non-empty
(`ck_reading_attempt_set_values`). `ability_policy_version` records which rule
moved `ability_before` to `ability_after`: present whenever a measurement is,
absent together with it (B1).

### 5.3 Projection: policy version, checkpoint, discardable

- **Policy version** — part of the projection's identity (§4).
- **Checkpoint** — `consumed_through_ordinal`. An attempt applies only as
  `checkpoint + 1`, so a re-delivery is a no-op and an out-of-order one cannot
  apply (`ORENA_EVIDENCE_ARCHITECTURE.md` §3, "Apply an evidence version once").
- **Discardable** — every value is recomputed by replaying the account's set
  attempts in ordinal order under the policy version, from facts the attempts
  hold (`passage_level`, per-answer correctness, and each question's type from
  its frozen set; the replay maps level to difficulty under its own policy).
  An unmeasured attempt is replayed like any other, so a later policy can
  measure what an earlier one could not. Deleting a row costs a rebuild, never evidence; the
  proof deletes one and shows the attempts untouched. The attempts' own
  `ability_before/after` are the historical record of what the policy said *at
  the time*; a rebuild under a new policy writes a new projection row and never
  rewrites them.

### 5.4 Deletion workflow enumeration (D-054, D-055)

The account-deletion workflow is not built, and D-055's gate
(`tests/test_deletion_journal.py::test_no_runtime_code_deletes_or_re_registers_an_account_yet`)
keeps any runtime path from deleting an account until it is. What it must
delete for Reading — the whole Reading owner, not only what this migration
adds — is enumerated, in deletion order, as `ACCOUNT_OWNED`:

| Table | Predicate | Kind |
| --- | --- | --- |
| `reading_ability_projections` | `user_id = :user_id` | projection — discardable |
| `reading_attempts` | `subject_kind = 'comprehension_set' AND user_id = :user_id` | evidence, keyed to the account |
| `reading_attempts` | `session_id IN (SELECT id FROM reading_sessions WHERE user_id = :user_id)` | evidence, keyed through the session |
| `reading_sessions` | `user_id = :user_id` | the learner's generated passages and goals — round 2 found the round-2 list omitted them (R2) |

`text_discussions.reading_session_id` is `ON DELETE SET NULL`; the discussions
themselves are an existing owner table of their own contract, deleted by the
same workflow under that contract, and are not re-enumerated here.

`ACCOUNT_OWNED` is in the migration only so the reviewer and the proof can
read it. **At apply it moves into application code the deletion workflow
imports** — the application never imports a migration.

The proof runs that enumeration for one of two learners and shows the other
learner and every platform row untouched, and separately that the `users`
foreign keys cascade. Deleting a learner's attempts never meets a RESTRICT: the
attempts are the children. On restore, the workflow's replay (D-054) applies
the same predicates. At apply time the enumeration also joins the owner-table
list the deletion workflow will consume, and `reading_attempts` joins
`runtime_backup.COMPARED` (it is missing today).

### 5.5 What the backbone will add, and why it is not reused now (round-2 R9)

`ORENA_ACCOUNT_DATA_ARCHITECTURE.md` asks, beyond the four items above, for
receipts that carry the **account incarnation** (§1), a **change record**
written atomically with the receipt (§3, §4), and a per-incarnation **stream
sequence** (§5). The I2 backbone built exactly those —
`mutation_receipts`, `change_records`, `account_streams`,
`projection_checkpoints` (`20260908_0005`) — and this proposal **does not
write to them**, deliberately:

- they are keyed by `account_incarnations.id`, and an incarnation row exists
  only where the backbone is active (`ORENA_ACCOUNT_BACKBONE`, on in one lane
  sandbox, off everywhere else); a Reading submit that required one would stop
  working wherever the flag is off;
- keying new learner evidence to the incarnation, rather than to `user_id` as
  every existing domain owner is keyed (`saved_words`, `speaking_attempts`,
  `listening_progress`), is the account-architecture decision `AGENTS.md` §7
  reserves. This proposal does not make it.

So those three items are **deferred to backbone activation**, and the path is
additive: when Reading activates on the backbone, the submit transaction also
writes a `mutation_receipts` row (domain `reading.comprehension_attempt`,
`result_ref` = the attempt id) and a `change_records` row under the stream
lock, in the same transaction as the attempt; the attempt's own
`(user_id, operation_id)` receipt stays as the domain's dedupe. The projection
checkpoint can then move to `projection_checkpoints`, keyed by stream sequence
— which is why this one is kept discardable and nothing depends on it.

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
2. **Approval** takes `SELECT … FOR UPDATE` on the article row, then recomputes
   SHA-256 of the current body, requires it to equal the anchor, and re-verifies
   every span, all in the transaction that moves the set to `approved`. A draft
   whose article changed is re-anchored while still undecided (allowed by the
   trigger); a decided set's anchor is frozen.
3. **An article body edit** takes the same `SELECT … FOR UPDATE` on the article
   row, reads the current body **inside** that transaction, and moves every
   approved set of that article whose anchor no longer matches to `stale`, in
   the same transaction, with a review event. It is visible to the Admin, never
   silent. The shared row lock is what closes the race round 2 found (R3):
   `update_article` today reads the article outside its transaction, and rule 3
   alone stales only sets that are already approved, so an approval racing a
   body edit could land on a stale anchor. With both taking the lock, either
   the edit lands first and the approval's hash check fails, or the approval
   lands first and the edit stales it. The database itself accepts approving a
   set whose anchor no longer matches — the proof does not claim otherwise; the
   lock and the hash check are the service's.
4. **Serving and submitting** re-check the hash. A mismatch means the set is not
   served — the article is Free Reading for that learner — and a submit is
   `rejected {set_stale}`. This holds even if rule 3 were ever skipped.
5. **`stale → approved`** is allowed only when the hash matches again.

**The hash input, exactly:** SHA-256 over the UTF-8 encoding of
`reading_articles.body` as stored, with no normalization of any kind (no
Unicode normalization, no trimming, no line-ending change), rendered as 64
lowercase hex digits. Offsets are Unicode code points into that same string
(Python string indices); the browser converts to UTF-16 for highlighting.

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

Round 1 proposed five values. Every vocabulary for these axes, server and
client — round 2 found two client ones the round-2 inventory missed (R6):

| Axis | Where | Values | Meaning |
| --- | --- | --- | --- |
| How content arrives | `reading_sources.source_type` | `manual, direct_url, file, rss, api, feed` | ingestion method |
| What form a learner sees | `reading_articles.content_kind` | **`article, news`** | editorial form of a corpus article |
| What form a learner sees, in the Library | `static/orena/ui/library-browse.js` `TYPE_ORDER` / `READING_MATERIALS` | `book, excerpt, article, news, essay, story, dialogue, quote, …` | the Library's material chips, across every catalog |
| (retired) form requested of the AI generator | `ReadingGenerateIn.material`, mirrored by `static/orena/content/reading.js` `READING_FORMS` | `article, book, news, quote` | never stored; both leave with the generator (§9 step 3) |
| Which id space a discussion keys to | `text_discussions.source_kind` | `story, media, reading_session, book_chapter` | routing identity, not a form |

The Library's chip vocabulary is the one that already exists for this axis, so
`content_kind` is **a subset of it with the same meanings**: `article` renders
as the Library's `article` chip, `news` as its `news` chip. No new word, and no
word with a second meaning.

- **`book_excerpt` is not added.** A book is its own catalog (`reading_books`,
  `20260916_0009`), which the Library renders as `book`; the Library's own word
  for a part of one is `excerpt`, not `book_excerpt`.
- **`essay` and `story` are not added now** — and, correcting round 2, not
  because they are invented: the Library already renders both as material
  chips. They are left out because the learner lane asked to tell Book, Article
  and News apart and nothing else, and adding a value later is a CHECK change.
  If added, they take the Library's words. (`story` as a form and `story` as a
  `text_discussions.source_kind` routing value are different axes; the second
  names an id space, not what a text is.)
- **No fourth vocabulary.** `content_kind` reuses the Library's words, and
  `material`/`READING_FORMS` leave with the generator.

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
| 8 | Import / shadow-verification tooling | `importer.target_counts` counts **all** of `reading_attempts`, unjoined; `verification.verify_shadow` compares it exactly with the legacy SQLite source; `read_compare.py` counts through the session join | round 2 found this row mis-described (F3): once one set attempt exists, `scripts/postgres_shadow.py` would report "Shadow verification FAILED" (measured: 3 unjoined vs 2 joined). At apply, `target_counts` counts `subject_kind = 'generated_session'` rows only — the only kind a legacy source can hold |

The three steps, with the gates they now carry:

1. **Now (this schema, once approved and authorized):** Admin authoring only —
   sets are generated, reviewed and approved. **No learner runtime writes a set
   attempt.** The generated route keeps working, and is marked deprecated in
   code and in `LEGACY_TOMBSTONES.md`.
2. **Before the first set-attempt write** — not merely before an entry point
   moves (round-2 R5: writing set attempts while consumers still read only
   sessions is itself the silent loss): consumers 2–6 read through one
   Reading-domain read contract, `list_reading_evidence`, returning both
   subject kinds in one item shape
   (`subject: {kind: 'generated_session', id} | {kind: 'comprehension_set', article_id, set_id}`,
   title, time, latest result), each with a test that a set attempt appears in
   it, and consumer 8 counts only generated-session rows. Only then does the
   corpus route accept a submit and the learner entry points move. The old
   route stays reachable by an existing session id, so an attempt in flight is
   not lost.
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
- **Each dialect's extra write is closed (round-2 R4, F5).** SQLite's
  `INSERT OR REPLACE` / `UPDATE OR REPLACE` resolve a conflict by deleting the
  other row and fire no DELETE trigger doing it — round 2 used it to forge a
  set attempt and to turn an approved set back into a draft. SQLite now has
  `*_conflict_guard` triggers that refuse, before conflict resolution, any
  write colliding with a set, a question or a set attempt (by id, by
  `(user, operation)`, by `(user, language, ordinal)`, or by the approved-set
  key). A plain colliding write fails on the unique constraint anyway, so the
  outcome is the refusal PostgreSQL gives — where `ON CONFLICT DO UPDATE` goes
  through the UPDATE guards. PostgreSQL's `TRUNCATE … CASCADE` fires no row
  trigger and ignores RESTRICT; statement-level `BEFORE TRUNCATE` guards now
  refuse it on the sets and questions always, and on `reading_attempts`
  whenever it holds a set attempt — so `TRUNCATE reading_articles CASCADE` or
  `TRUNCATE users CASCADE` cannot take evidence either. The same scenario runs
  on both dialects in each dialect's own syntax.
- **Triggers on the ORM path, and after a rebuild.** At apply, `models.py`
  attaches the same trigger DDL with `DDL(...).execute_if(dialect=...)`, and a
  test asserts every trigger named in the migration exists on a
  `create_all`-built database. Any future migration that batch-rebuilds one of
  these tables on SQLite drops its triggers and must recreate them; the same
  test catches one that does not.

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

**Local execution, 2026-09-24 — not CI (after round 3's required changes):**
PostgreSQL 16.13, 61 passed, 2 skipped (the SQLite halves of the two-connection serialization case
and the TRUNCATE case, which are PostgreSQL-only by design); SQLite alone, 30
passed. The SQLite downgrade-lock case was mutation-checked the same way. The downgrade-race case was checked against a mutation: weakening the
lock to `ACCESS SHARE` makes it fail. CI will run the SQLite half on every push; the
PostgreSQL half runs wherever `ORENA_TEST_POSTGRES_URL` is set.

At apply, `models.py` gains the same declarations (both `where` clauses, the
CHECKs, the unique index on `reading_articles`, and the triggers as above),
and a parity test compares the ORM-built schema with the migrated one.

## 11. Migration, rollback and downgrade

**Upgrade** is additive and transactional on PostgreSQL (all or nothing): two
new tables, one new projection table, one defaulted column and one unique index
`(id, language)` on `reading_articles`, and on `reading_attempts` two `DROP NOT
NULL`s, thirteen nullable-or-defaulted columns, two FKs, six CHECKs and two
unique constraints. No existing row is rewritten. `ADD CONSTRAINT` validates by
scanning `reading_attempts` and `reading_articles`, which are small today; if
either were large at apply time the constraints would be added `NOT VALID` and
validated separately.

**Old code on the new schema** — the real rollback path — keeps working: every
new column is nullable or has a server default, so today's writer and the
importer, which name none of them, write valid generated-session rows. The
proof inserts and reads through the unchanged `ReadingAttempt` model after the
upgrade.

**Downgrade never removes learner data.** On PostgreSQL its first statement
locks every table it would change — `reading_articles`,
`reading_comprehension_sets`, `reading_comprehension_questions`,
`reading_attempts`, `reading_ability_projections` — `IN SHARE ROW EXCLUSIVE
MODE`, which blocks every writer and any second downgrade until it ends. Then a
guard, in the same transaction: if any set attempt, any set, any projection
row, or any `content_kind` other than `article` exists, it raises and nothing is
dropped. Round 2 found the guard without the lock was a race (R1, F6): a
downgrade waiting on a writer's uncommitted draft set and `content_kind='news'`
proceeded after the commit and dropped both. With the lock, the guard runs only
after that writer commits, and sees it — proved with two connections, and the
proof fails if the lock is weakened. On SQLite a `SELECT` alone opens no
transaction under pysqlite's defaults — round 3 found the round-3 text claiming
otherwise false (RC1) — so the downgrade first runs a write that changes
nothing (`UPDATE reading_articles SET content_kind = content_kind WHERE 1 = 0`),
which takes the database's write lock; no other connection can write until the
downgrade ends, and only then does the guard look. Proved: a writer attempted
right after the guard is locked out, and the proof fails without that write.
On PostgreSQL the lock and the guard are both SQL (`LOCK TABLE`, a `DO` block),
so an offline-rendered downgrade script carries them too. With no footprint, the
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

- `models.py` declarations, the triggers on the `create_all` path, and the ORM
  parity test (§10);
- the Reading repository's submit transaction with the advisory lock and the
  best-effort measurement (§5.1), the ability rebuild (§5.3), and
  `list_reading_evidence` with consumers 2–6 moved onto it (§9 step 2);
- the element-shape validation of `answers` (§3);
- the article row lock and the in-transaction body read in approval and in
  `update_article`, the staleness transition, and the exact hash input (§6);
- set decisions written to `reading_review_events` (§2);
- `ACCOUNT_OWNED` moved into application code for the deletion workflow (§5.4);
- `importer.target_counts` counting generated-session rows only (§9, #8);
- `content_kind` in `LEARNER_VISIBLE_FIELDS` and the publish contract (§8);
- the learner surface reading the set's `explanation` in its
  `support_language`: `static/orena/ui/comprehension.js` reads only
  `explanation_vi` today, so the corpus path maps it there (§6);
- `reading_attempts` in `runtime_backup.COMPARED`; the deprecation marker;
- `models.py` declares `uq_reading_article_language_scope` together with the
  composite set→article FK, and the ORM parity test covers it: on SQLite a
  composite FK whose parent columns have no unique index fails every child
  insert and parent delete with "foreign key mismatch" (round-3 RC3);
- the advisory-lock key is pinned to a Reading namespace (for example
  `hashtextextended(user_id::text || ':' || language, <reading namespace>)`) so
  it cannot collide with another advisory-lock user (round-3 answer 1).

The SQLite runtime repository refuses the set-attempt write, as it refuses
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
| 6 | idempotency key | done, `(user, operation_id)` + digest (§5.1; the language left the key in round 3) |
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

## Answers to round 2, item by item

Round 2 reviewed `4563908`: REQUEST CHANGES, one blocker. Its answers to the
round-2 review questions are kept: extending `reading_attempts` is the right
reading of §3/§6.7; the body hash is the right anchor; the triggers stay.

| Finding | Answer | Where / proof |
| --- | --- | --- |
| **B1** evidence could not commit unless the projection succeeded | ability group all-or-none (`ck_reading_attempt_ability_group`); ordinal under an advisory lock, not the projection row; measurement best-effort in a savepoint | §3, §5.1; attempt commits unmeasured with no projection row; half a measurement refused |
| R1 downgrade guard race | `LOCK TABLE … IN SHARE ROW EXCLUSIVE MODE` before the guard, in the offline script too | §11; two-connection race refused; mutation check |
| R2 `ACCOUNT_OWNED` incomplete, wrong home | `reading_sessions` added; moves into app code at apply | §5.4; deletion proof counts sessions |
| R3 approval races a body edit | both take the article row `FOR UPDATE` and read the body in-transaction; hash input specified | §6 (service rule; the DB is stated not to enforce it) |
| R4 SQLite REPLACE bypass; PG TRUNCATE | SQLite conflict guards; PG `BEFORE TRUNCATE` guards | §10; replace/upsert refused on both; TRUNCATE refused |
| R5 step 1 wrote set attempts before consumers moved | precondition is the first write | §9 |
| R6 client vocabularies missing | Library `TYPE_ORDER` and `READING_FORMS` inventoried, `content_kind` a subset of the Library's words | §8 |
| R7 operation id per language | `UNIQUE (user_id, operation_id)` | §5.1; replay under another language refused |
| R8 projection justification wrong | corrected; attempts authoritative | §4 |
| R9 incarnation, change records, stream, backbone tables | deferred to backbone activation, with the additive path and why not now | §5.5 |
| R10 lookalike CHECKs | hex-only hash and digest; decided set names a non-empty reviewer; reviewer fields frozen outside a status change; `answers` element shape is the service's, stated | §2, §3; `'g' * 64` refused; rewrite refused |
| R11 set language not bound to article | unique index `(id, language)` on articles + composite FK from the set | §2; zh set on en article refused |
| F1 misquoted projection identity | quote corrected ("account incarnation"), keying explained | §4, §5.5 |
| F2 "64 lowercase hex" was only length+lowercase | now true | §2 |
| F3 consumer 8 mis-described | corrected, apply-time fix named | §9 |
| F4 "index-only walk", contiguity | corrected; contiguity is the service's invariant | §4 |
| F5 "the same rules" on both dialects | now true, with each dialect's extra write closed | §10 |
| F6 "nothing is dropped" under a concurrent writer | now true, with the lock | §11 |

## Answers to round 3

Round 3 reviewed `c7050d6`: **APPROVED WITH REQUIRED CHANGES**, no blockers.

| Finding | Answer |
| --- | --- |
| RC1 SQLite downgrade guard opened no transaction | a no-op write takes the write lock before the guard; proved with a second connection, mutation-checked |
| RC2 reviewer fields rewritable on `approved→stale/archived`, `stale→archived` | they change only on a transition into `approved` or `rejected`, both dialects; proved |
| RC3 ORM must declare the articles unique index with the composite FK | apply-time list (§12) |
| Note: trigger functions depend on `search_path` | each PostgreSQL function now carries `SET search_path FROM CURRENT` |
| Note: SQLite `INSERT OR REPLACE INTO users` cascades every owner table | a hazard for every learner table, not this proposal's; no code does it; recorded, not changed |
| Q1 advisory lock | kept; key namespace pinned at apply |
| Q2 conflict guards | sufficient; the static `OR REPLACE` test is optional and not added |
| Q3 anchor check in the service | kept |

## Review questions for round 3 (answered above)

1. Is the advisory transaction lock on `(account, language)` the right
   serialization for ordinal allocation, against locking the `users` row?
2. Are the SQLite conflict guards a sufficient answer to `OR REPLACE`, or should
   a test also forbid `OR REPLACE` / `prefix_with("OR REPLACE")` on these tables
   in application code?
3. Is leaving "approval requires a matching anchor" to the service (row lock +
   hash check), rather than a PostgreSQL-only trigger that hashes the body, the
   right side of the parity rule?
