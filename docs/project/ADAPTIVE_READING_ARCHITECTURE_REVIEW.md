# Adaptive Reading schema — architecture review

**Integration note (2026-09-26):** These verdicts reviewed the Admin-lane
`20260924_0014` revision. The integration renumbers it to `20260924_0016` and
changes its parent. Independent delta review is required before this new
revision is applied to a shared runtime. Historical identifiers below remain
as the reviewers recorded them.

**Integration delta review (2026-09-26):** Independent Delegated Architecture
Reviewer GPT-6/Codex (`/root/architecture_review`) reviewed merge commit
`ec7ac2897fb103a9f4a7898a6e256f351719e028` and returned **PASS** for
proceeding with Speaking integration: 16 unique revisions, one linear chain
ending at `20260924_0016`, no P0/P1 findings, and Reading DDL semantics
unchanged from the Admin parent except revision/parent and explanatory labels.
The reviewer found two P2 runbook gaps (the separate `0014`→`0015` preparation
and historical rehearsal IDs); both were corrected after the reviewed commit.
This review is not authorization to apply migrations to a shared runtime;
the human's explicit runtime authorization gate still applies.

| Round | Reviewed | Verdict |
| --- | --- | --- |
| 1 | `00dcf18` (prose only) | REQUEST CHANGES — 5 blockers, 21 required changes, 6 factual errors |
| 2 | `4563908` (proposal + DDL + two-dialect proof) | REQUEST CHANGES — 1 blocker, 11 required changes, 6 factual errors |
| 3 | `c7050d6` (delta: the round-2 answers) | APPROVED WITH REQUIRED CHANGES — no blockers; RC1, RC2 made in `0d6efda`, RC3 apply-time |
| 3, confirmation | `0d6efda` (delta: RC1, RC2, search_path) | **APPROVED** — no new findings |
| — | **superseded 2026-09-24 by D-075** | the reviewed design kept `generated_session` as a second attempt subject; the human rejected keeping the legacy shape as a formal contract. **This approval does not carry to the canonical model.** |
| C1 | `5e4e4c3` — canonical model (D-075), reviewed from the start | APPROVED WITH REQUIRED CHANGES — no blockers |
| C1, confirmation | `fdf198f` (delta: every C1 required change) | **APPROVED** — schema-review gate passed for the canonical model |

Nothing is applied in any round. Rounds 1-3 reviewed the `generated_session`
design, which D-075 superseded; their approval at `0d6efda` is void for the
canonical model, which is reviewed from round C1. Applying needs an APPROVED
review of the canonical model and the human's schema/runtime authorization.

---

# Round 1

    VERDICT:         REQUEST CHANGES
    REVIEWER:        Delegated Architecture Reviewer (Claude Opus 5)
    REVIEWED COMMIT: 00dcf183960e6969816e9f17d62b288f6a25c501
    PROPOSAL:        docs/project/ADAPTIVE_READING_SCHEMA_PROPOSAL.md
    DATE:            2026-09-24
    APPLIED:         no — the migration may not be written or applied until a
                     later round passes

Recorded under `AGENTS.md`, "Architecture review authority": the reviewer's
identity, the reviewed commit and the outcome live in Git, and the implementer
did not approve its own work.

**Scope note the reviewer put first, and it changes what this verdict means:**
`git show --stat 00dcf18` is one file, the document. No migration, no model, no
DDL exists yet. Much of this is a review of prose describing constraints, and
**it must be repeated against the DDL** when that is written.

---

## Blockers

1. **The set table's partial unique index forbids the workflow the table exists
   for.** The proposal justifies a separate table with "an article can have a
   set that was rejected and a new one being prepared", then constrains it
   `UNIQUE (article_id) WHERE status <> 'archived'`. `rejected` is not
   `archived`, so a rejected set and a new draft collide. Preparing a
   replacement would force archiving the rejection — destroying the history the
   table exists to keep. Same defect class as round-1 P1-1/P1-3 of the Reading
   Content Engine review. The predicate matching the real rule is
   `WHERE status = 'approved'`.

2. **A path exists from an admin article purge to destroyed learner evidence.**
   `reading_comprehension_sets.article_id` is `ON DELETE CASCADE`;
   `reading_practice_attempts` names no `ON DELETE` at all. Deleting an article
   cascades the sets away and then either takes the attempts with them or
   silently breaks the documented purge path. The engine's rule is the
   opposite and written down: `RESTRICT` upward for anything that is evidence
   behind something a learner read.

3. **This is learner-owned schema authored without the specification it is
   required to be authored against.** `CURRENT_HANDOFF.md` (BLOCKED) requires a
   learner-owned schema to be authored against
   `ORENA_ACCOUNT_DATA_ARCHITECTURE.md`. The proposal never names it, and four
   of its requirements are missing: an evaluator/rule version on the attempt; a
   projection policy version, checkpoint and "discardable" declaration on
   `reading_ability`; an idempotency key so a retried submit does not apply the
   ability step twice; and enumeration of the two new account-keyed owner
   tables in the deletion workflow (D-054). Not "these tables may not exist" —
   the design has not been done against the contract that governs it.

4. **`evidence_start`/`evidence_end` point into a column an Admin edits**, with
   nothing recording which revision they were computed against. `update_article`
   accepts a new `body`, bumps `content_revision`, and nothing invalidates the
   offsets. The failure is silent and lands on published learner content.

5. **Partial indexes are declared for one dialect**, against a rule this
   repository already wrote down: `postgresql_where` alone becomes a full index
   on SQLite, so the hermetic suite would enforce a constraint the runtime does
   not have — and here it would make the "rejected set plus replacement"
   scenario untestable.

## Required changes (21)

Uniqueness and keys: the approved-only predicate (1); explicit `ON DELETE` on
every FK, `RESTRICT` upward (2); `user_id` as a real FK (3); uuid surrogate plus
`UniqueConstraint(user_id, language_code)` on `reading_ability`, matching every
other learner table (4).

Versions and idempotency: rule/evaluator version on the attempt and projection
policy version on ability, declared rebuildable (5); an idempotency key in the
shape `TextDiscussionTurn.request_id` already uses (6).

Minimality: drop `recent_json` — the index already answers it (7); partial
progression index on `completed_at IS NOT NULL` (8).

Constraints: `NOT (admin_approved AND admin_rejected)` plus `machine_suggested`
(9); `rank >= 0`, and reconsider unique rank (10); bound `correct_index` above
(11); an approved set must have at least one question (12); bound `score`, or
say what else goes into it (13).

Types: `Float`, not `Numeric` — `Numeric` appears nowhere in this repository and
round-trips differently on SQLite (14); widen `ability` — `numeric(5,3)`
silently excludes an Elo-style model (15); state the `completed_at` rule (16).

Integration: add `content_kind` to `LEARNER_VISIBLE_FIELDS` and the learner list
projection (17); decide the explanation's language — the existing surface reads
`explanation_vi` only (18); commit to the PostgreSQL constraint proof (19); name
the three other readers of `reading_sessions` (20); correct the six factual
errors (21).

## Six factual errors in the proposal

1. The engine's partial unique on `request_hash` is an **inclusion** predicate,
   not the exclusion shape the proposal claims to copy.
2. **`CHECK (evidence_text <> '')` does not enforce grounding.** A CHECK cannot
   reach `reading_articles.body`; it forbids the empty string and nothing else.
   The proposal's headline claim, and the commit message that carried it, are
   false. The only real grounding check is in application code.
3. The targets' `(article_id, rank)` index is **not** unique and does carry
   `rank >= 0`; the proposal is stricter one way and weaker the other.
4. Targets also carry `machine_suggested` and the mutual-exclusion CHECK; the
   proposal copies neither.
5. "The generation logic is reused" is not true as written: the generator is
   hard-wired to four questions and four options, produces no `question_type`,
   no offsets, and a Vietnamese-only explanation. The eight-type enum and the
   3-6 rule require rewriting it.
6. `migrations/proposed/` is no longer where the engine's migration sits.

## Answers to the six questions the human asked

- **Minimal / ownership:** the four-way split is right and should not be merged.
  `recent_json`, `question_count` and `score` are the non-minimal parts.
- **Duplication:** none with `reading_articles`, `reading_article_targets` or
  `reading_source_items`, checked field by field. `analysis_json` is a name
  collision, not a duplication. Missing for review: the mutual-exclusion CHECK,
  `machine_suggested`, and the `content_revision` the set was built against.
- **Ability without hard-coding an algorithm:** the shape is model-agnostic; the
  precision, the missing rule version and storing only `passage_level` rather
  than the difficulty actually consumed are what hard-code it.
- **Evidence invariant:** reasonable for every type because it does not do what
  was claimed. Grounding belongs in the repository and at review; `main_idea`
  and `authors_purpose` need either a paragraph span or a nullable evidence with
  a rule saying which types may omit it.
- **Deprecation:** sound, but `reading_sessions` has four readers, not one —
  the cross-skill cue and the learner summary would quietly regress. Also
  `text_discussions.source_kind` has no value for a corpus article, so Text
  Discussion could not attach to one; and `reading_practice_attempts` sits one
  word from the existing `reading_attempts`, which is the parallel-evidence
  pattern `ORENA_ACCOUNT_DATA_ARCHITECTURE.md` forbids.
- **`content_kind` / source category:** correctly scoped, and **defer source
  category entirely** — the reviewer's judgement is that deferring is better
  than acceptable: it has zero occurrences anywhere, and the work it would do is
  already done by the source's rights columns. Two enum collisions to resolve
  (`book_excerpt` vs the book catalog, `story` vs `text_discussions.source_kind`)
  and a fourth vocabulary for the same axis in `ReadingGenerateIn.material`.

## What the reviewer said not to change

The four-table split; `options_json` as JSON; `content_kind` on the article
rather than the immutable snapshot; the three axes kept separate;
`passage_level` as a point-in-time snapshot; both `ability_before` and
`ability_after` on the attempt; the three-step deprecation with step 3 gated
separately; and no ML, no second vocabulary store, no change to Free Reading.

## Next round must include

The DDL itself, the four `ORENA_ACCOUNT_DATA_ARCHITECTURE.md` requirements, a
downgrade story (learner evidence must not be down-migrated away), and the
PostgreSQL constraint proof. Then this review is repeated against the migration
rather than against prose.


---

# Round 2

    VERDICT:         REQUEST CHANGES (one blocker; small, delta-reviewable)
    REVIEWER:        Delegated Architecture Reviewer - an independent agent
                     with a fresh context that did not write this work; read-
                     only, left `git status` clean and no proof schemas behind
    REVIEWED COMMIT: 456390829c7fad39f5e518cd7ab21411050865cd
    REVIEWED:        docs/project/ADAPTIVE_READING_SCHEMA_PROPOSAL.md,
                     migrations/proposed/20260924_0014_adaptive_reading.py,
                     tests/test_adaptive_reading_schema_proposed.py
    DATE:            2026-09-24
    APPLIED:         no

Recorded under `AGENTS.md`, "Architecture review authority". The implementer
did not approve its own work.

**Round-1 disposition.** Blockers 1, 2, 4 and 5 resolved (2 with two non-schema
bypasses, R4); blocker 3 partially (B1, R2, R9). Required changes 1-19 resolved
(17 deferred to apply, acceptable), 20 partially (F3), 21 resolved. All six
round-1 factual errors resolved.

**Human decisions 1-16.** Satisfied: 1, 2, 4, 5, 7, 9, 10, 12, 14, 15 (with
R1), 16. Not or partially: 3 (B1, R2, R9), 6 (SQLite `OR REPLACE`, R4), 8 (the
projection's justification, R8), 11 (two client vocabularies uninventoried,
R6), 13 (step 1 wrote set attempts before consumers moved, R5).

## Blocker

**B1 - learner evidence could not commit unless the projection succeeded.**
`ck_reading_attempt_set_shape` made `ability_policy_version`,
`passage_difficulty`, `ability_before`, `ability_after` NOT NULL, and §5.1
allocated the ordinal from, and rebuilt, the discardable projection row inside
the submit. A policy with no mapping for a level, an out-of-range value or a
failed replay would roll back every submit. Contradicts
`ORENA_EVIDENCE_ARCHITECTURE.md` ("Projection failure preserves source
evidence", "Unknown is not zero"). Fix: the four all-or-none; ordinal under a
lock that is not the projection row; measurement best-effort; a proof that an
attempt commits with the projection missing.

## Required changes

- **R1** Downgrade guard read without a lock: with an uncommitted draft set and
  `content_kind='news'` in another transaction, the downgrade waited, then
  succeeded and dropped both. Lock the tables before the guard.
- **R2** `ACCOUNT_OWNED` omitted `reading_sessions`; move it into app code at apply.
- **R3** Approval can race a body edit (`update_article` reads outside its
  transaction); lock the article row in both, fix the hash input.
- **R4** SQLite `INSERT OR REPLACE` forged a set attempt and reset an approved
  set to a draft past the guards; PostgreSQL `TRUNCATE ... CASCADE` takes set
  attempts with no trigger.
- **R5** Step 1 must not write set attempts until consumers 2-6 have moved.
- **R6** Inventory the Library's `TYPE_ORDER`/`READING_MATERIALS` and
  `READING_FORMS`; `story`/`essay` are Library chips, not inventions.
- **R7** `language_code` in the operation key let one `operationId` commit twice
  under two languages.
- **R8** The projection's "must not replay history" justification is false for
  the ability itself; state that the attempt is authoritative.
- **R9** Incarnation, change records, stream sequence and the unused backbone
  tables: defer explicitly, with the path.
- **R10** Hash/digest CHECKs accepted `'g' * 64`; a set attempt accepts
  legacy-shaped `answers`; a decided set accepted an empty `reviewed_by` and
  later rewrites of its reviewer fields.
- **R11** Nothing bound a set's language to its article's: a zh set on an en
  article was accepted.

## Factual errors

F1 the projection-identity quote dropped "incarnation"; F2 "64 lowercase hex"
was length and case only; F3 consumer 8 (`importer.target_counts` counts
unjoined, so shadow verification would fail); F4 "index-only walk" and
database-enforced contiguity; F5 "the same rules" on both dialects under
`OR REPLACE`; F6 "nothing is dropped" under a concurrent writer.

## Reviewer's own checks (local execution, not CI)

Implementer's proof reproduced (PostgreSQL 16: 46 passed, 1 skipped; SQLite 23
passed). CI validators pass. `0013 -> 0014 -> 0013` catalogue-identical on
PostgreSQL, re-upgrade identical; SQLite batch rebuild keeps the legacy unique
and the session CASCADE; offline `--sql` upgrade and downgrade ran with
`psql -v ON_ERROR_STOP=1`. Every accepted-but-wrong case above was
demonstrated, not inferred.

## Kept

The approved-only inclusion predicate with both `where` clauses; plain uniques
over nullable columns; RESTRICT attempt->set and set->article with the
reached-learners delete guard; CASCADE to questions; the composite attempt->set
FK; the exclusive-and-complete shape CHECKs; a row only once submitted; the
frozen body-hash anchor; the honest structural span CHECK; the spanless
`main_idea`/`authors_purpose` rule; `content_kind` `article|news`; source
category and Text Discussion deferred; the refusing downgrade in the offline
script; an upgrade old code can use; `FOR SHARE` serialization; one scenario
list on both dialects; Float +/-1e6 with NaN and infinity refused;
`passage_difficulty` beside `passage_level`.

The answers to every item are in `ADAPTIVE_READING_SCHEMA_PROPOSAL.md`,
"Answers to round 2, item by item".


---

# Round 3

    VERDICT:         APPROVED WITH REQUIRED CHANGES - no blockers
    REVIEWER:        the same Delegated Architecture Reviewer as round 2
                     (independent; did not write this work); read-only; three
                     scratch databases created and dropped, no proof schemas left
    REVIEWED COMMIT: c7050d688bcdfacb1152daa9881c71d6b18ba7f6 (delta from 4563908)
    DATE:            2026-09-24
    APPLIED:         no. Applying needs the human's schema/runtime
                     authorization; this verdict is not product approval.

**Round-2 disposition.** B1 resolved (all-or-none ability group; an attempt
with all four NULL accepted, half a group, `''`, NaN, -inf and 1e6+1 refused on
PostgreSQL). R1 resolved on PostgreSQL (race re-run with a draft set +
`content_kind`, and with an approved set + attempt: blocked, then refused).
R2-R9 and R11 resolved. R10 mostly resolved (RC2 remained). F1-F5 corrected;
F6 corrected for PostgreSQL, not SQLite (RC1). The round-2 record above is
faithful. Human decisions 1-16 all satisfied (15 on PostgreSQL; SQLite is the
test path, RC1).

**Required changes.**

- **RC1** The SQLite downgrade claim was false: under pysqlite defaults a SELECT
  opens no transaction, and a second connection committed a draft set after
  the guard; the downgrade then dropped it. Take the write lock before the
  guard, or state a single-writer assumption.
- **RC2** Reviewer fields were frozen only when the status did not change, so
  `approved->archived` accepted `reviewed_by='someone-else'`. Allow them to
  change only on a transition into `approved` or `rejected`.
- **RC3 (apply)** `models.py` must declare `uq_reading_article_language_scope`
  with the composite FK; on SQLite a composite FK without a unique parent index
  raises "foreign key mismatch". Cover it in the ORM parity test.
- Notes: pin `search_path` on the trigger functions (a `--data-only`
  restore fails under an empty search_path - not new breakage in this repo);
  SQLite `INSERT OR REPLACE INTO users` cascades every owner table - not this
  proposal's.

**Reviewer's checks (local execution, not CI).** Proof reproduced (PostgreSQL
60 passed, 2 skipped; SQLite 29 passed). Validators pass. `0013 -> 0014 -> 0013
-> 0014` catalogue-identical. Offline `--sql` up and down ran under `psql -v
ON_ERROR_STOP=1`; the offline downgrade against a schema holding a set refused
(rc 3) and the set remained. Every TRUNCATE, upsert and REPLACE path tried
against the protected tables refused (`TRUNCATE reading_ability_projections` is
allowed by design - the projection is discardable); a full `pg_dump`/`pg_restore` with approved and
stale sets and an attempt restored cleanly. The engine's SQLite suites pass on
a schema upgraded through the proposal (102 passed, as unpatched) and
`test_reading_engine_persistence_postgres` passes at the proposed head (32
passed).

**Answers to the round-3 questions.** (1) The advisory transaction lock, not a
`users` row lock - that would conflict with every FK insert's `FOR KEY SHARE` on
the user and serialize across languages; pin the key namespace at apply.
(2) The conflict guards are sufficient; a static `OR REPLACE` test is optional.
(3) The anchor check stays in the service; a PostgreSQL-only hashing trigger
would break parity.

**Resolution.** RC1 and RC2 are made in the commit that records this round,
each with a proof (the RC1 proof fails if the fix is removed), and every
PostgreSQL trigger function now carries `SET search_path FROM CURRENT`. RC3 is
on the proposal's apply-time list.


---

# Round 3 confirmation

    FINAL VERDICT:   APPROVED - the schema-review gate is passed
    REVIEWER:        the same Delegated Architecture Reviewer; read-only;
                     scratch databases and dump dropped
    REVIEWED COMMIT: 0d6efda74d7d29146283a7f331d9765d7533ccdd (delta from c7050d6)
    DATE:            2026-09-24
    APPLIED:         no. Applying needs the human's schema/runtime
                     authorization; this is not product approval.

- **RC1 resolved.** The reviewer's original race re-run: a second connection's
  real INSERT of a draft set right after the guard now gets "database is
  locked"; the downgrade completes on a database with no feature data.
- **RC2 resolved on both dialects.** Rewrites refused on approved->archived,
  approved->stale (`review_reason`, `reviewed_at`), stale->archived, a no-op or
  self status change on an approved set, and a rejected set; allowed are a
  plain approved->stale, stale->approved with a new reviewer, and
  needs_review->rejected naming its reviewer.
- **RC3** correctly on the apply-time list, with the advisory-lock namespace.
- **search_path resolved.** All four functions carry the pinned search_path;
  statements firing the triggers under `SET LOCAL search_path = ''` work; a
  `--data-only` restore no longer fails on "relation does not exist" (with
  `--disable-triggers` it restores the set and the attempt); a full restore is
  clean.
- **No new findings; no regression.** Proof reproduced (PostgreSQL 61 passed,
  2 skipped; SQLite 30 passed); validators pass; `0013 -> 0014 -> 0013 -> 0014`
  catalogue-identical; offline `--sql` up and down clean, offline downgrade
  refuses against a schema holding a set; the round-3 adversarial suite
  re-run with the same outcomes. Local execution, not CI.


---

# Canonical model (D-075) — round C1

    VERDICT:         APPROVED WITH REQUIRED CHANGES - no blockers
    REVIEWER:        Delegated Architecture Reviewer - a new independent agent
                     with a fresh context, not the reviewer of rounds 1-3; did
                     not write this work; read-only; scratch databases dropped
    REVIEWED COMMIT: 5e4e4c39a098accb82fef665df9858645b9f3500
    DATE:            2026-09-24
    APPLIED:         no; not product approval; not authorization

**D-075 conformance.** Satisfied: one flow with no generated-passage path;
Imports' five groups (`imports.js` `FLOWS`, `5f62174`); candidates only, never
auto-published; reversible lifecycles, book restore, the vocabulary lifecycle;
sets grounded and Admin-reviewed; one canonical attempt model; idempotent
submit; no evidence cascade; rebuildable projection; the legacy flow retired
without a `generated_session` contract; Text Discussion deferred; the READY
run. Deferred appropriately: selection (§4.1), the consumer move. Partial: the
three concepts (F3); rights warnings with an audited override are built for
vocabulary, not for Reading article publish; published-only corpus (an attempt
on an approved set of an archived article was accepted, RC4).

**Regression check.** Every finding of the superseded rounds (B1, R1-R11,
RC1-RC3, search_path) still resolved; none regressed.

**Required changes.** RC1 (DDL) re-decisions need not name a new reviewer, and
a reopened rejected set carried the rejection's reviewer into an approval -
demonstrated on both dialects; recommended fix: drop `rejected ->
needs_review` and make a retry a new draft set. RC2 (DDL) `TRUNCATE
reading_legacy_sessions CASCADE` truncated every learner's `text_discussions`
of every kind; guard the archive. RC3 record the departure from
`ORENA_ACCOUNT_DATA_ARCHITECTURE.md` §6 steps 2 and 5 and the I2 additive gate
for the human, with an apply runbook. RC4 require a published article at
submit; state unpublish/archive semantics; run the approval check on every
entry into `approved`. RC5 complete the consumer inventory; the importer
cannot be pointed at a read-only archive. RC6 factual errors F1-F7. RC7 the
ORM parity test and the archive's legacy constraint names.

**Factual errors.** F1 "batch rebuild" in the proof docstring; F2 superseded
bodies are retained in review events; F3 D-075 defers source category, not
source kind; F4 importer "pointed at the archive"; F5 "names its own reviewer"
was not enforced; F6 "rejected ... frozen" vs the reopen transition, and
"archive left truncatable"; F7 two definitions of current ability.

**Reviewer's checks (local execution, not CI).** Proof reproduced (PostgreSQL
63 passed, 2 skipped; SQLite 31 passed); validators pass. PostgreSQL `0013 ->
0014 -> 0013` and `0014 -> 0013 -> 0014` catalogue-identical (`pg_dump
--schema-only` and catalogue queries), legacy rows seeded; SQLite identical up
to identifier quoting, `integrity_check` ok, `foreign_key_check` empty. Offline
`--sql` up/down/up under `psql -v ON_ERROR_STOP=1`; offline downgrade over a
draft set refused. Archive bypasses refused (PostgreSQL `ON CONFLICT`, `MERGE`,
CTE update; SQLite `OR REPLACE`/`OR IGNORE` on insert and update). A submit
racing a stale update serializes both ways. Full `pg_dump`/`pg_restore
--exit-on-error` with archive rows, stale and archived sets, attempts and a
projection: identical counts.

**Answers.** Rename archive: right. Nothing reads the archive as evidence:
right; a labeled legacy baseline is the human's product decision. The
non-compatible migration: acceptable on engineering risk, but the human must
confirm the departure. Selection: nothing needs storing; a nullable
`selection_policy_version` strongly recommended before apply.

**Kept.** The rename archive with pkey renames; one attempt shape; RESTRICT and
the composite language FKs; the approved-only partial index on both dialects;
the all-or-none ability group; the account-scoped operation key and advisory
lock; the body-hash anchor with a structural span CHECK; the SQLite conflict and
PostgreSQL TRUNCATE guards; the lock-then-check downgrade in the offline script;
pinned search_path; `content_kind` `article|news`; source category and corpus
Text Discussion deferred; submit off until the consumers move; the READY gate.

The answers are in `ADAPTIVE_READING_SCHEMA_PROPOSAL.md`, "Answers to round C1".


---

# Canonical model — round C1 confirmation

    FINAL VERDICT:   APPROVED - the schema-review gate is passed for the
                     canonical model
    REVIEWER:        the round-C1 Delegated Architecture Reviewer; read-only;
                     scratch databases dropped
    REVIEWED COMMIT: fdf198f458a4c7bc16ee970a4cb8703c1a2ed3dc (delta from 5e4e4c3)
    DATE:            2026-09-24
    APPLIED:         no. Applying needs the human's schema/runtime
                     authorization, including confirmation of the deviation
                     from `ORENA_ACCOUNT_DATA_ARCHITECTURE.md` §6 steps 2 and 5
                     and the I2 additive gate recorded in the proposal's §11.
                     Not product approval.

- **RC1 resolved, both dialects:** `rejected -> needs_review` refused; a
  restore or re-approval keeping the same `reviewed_at` refused; with a new one
  accepted; a draft with NULL `reviewed_at` approvable once one is supplied.
- **RC2 resolved:** `TRUNCATE` of either archive table refused; the `DELETE`
  reset works.
- **RC3-RC7 resolved** (deviation and runbook, published-only attempts - also
  under an empty search_path -, the consumer inventory, F1-F7, the apply list).
  The §8 three-concept mapping checks out and is flagged for the human.
- **Minor and Q4 resolved:** `validation_json`, `created_at` frozen;
  `selection_policy_version` nullable, empty refused.
- **Review record faithful.**
- **New finding, not blocking:** the attempt guard takes `FOR SHARE` on set and
  article; the body-edit path takes the article `FOR UPDATE` then updates the
  set. An attempt inserted without the service's article lock first can
  deadlock with it (reproduced; no data lost, a same-`operationId` retry safe).
  With the §5.1 order there is no deadlock. Answered: the lock order is written
  into §5.1 and a test for it is on the apply list.
- **Checks (local execution, not CI):** proof 67 passed, 2 skipped (PostgreSQL
  16.13), 33 passed (SQLite); validators pass; `0013 -> 0014 -> 0013` and `0014
  -> 0013 -> 0014` catalogue-identical on PostgreSQL with legacy rows; SQLite
  identical up to quoting, integrity and foreign-key checks clean; offline
  `--sql` up/down/up clean, offline downgrade over a draft set refused; full
  `pg_dump`/`pg_restore` identical; submit vs stale serialized both ways.
