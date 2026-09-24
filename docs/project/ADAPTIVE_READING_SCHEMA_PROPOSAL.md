# Adaptive Reading — canonical Reading model, schema proposal

    STATUS: PROPOSED, NOT APPLIED — to be reviewed from the start.
            Written for the human direction of 2026-09-24 (D-075): one Reading
            flow, one canonical evidence model. It replaces the earlier
            proposal of the same revision id, whose design kept
            `generated_session` as a second attempt subject; that design and
            its review approval (0d6efda) are superseded and do not carry over.
    DDL:    migrations/proposed/20260924_0014_adaptive_reading.py
    PROOF:  tests/test_adaptive_reading_schema_proposed.py
    REVIEW: docs/project/ADAPTIVE_READING_ARCHITECTURE_REVIEW.md
    LANE:   admin/control-center

The DDL sits in `migrations/proposed/`, which Alembic's default
`version_locations` never reads. Applying it (one `git mv` into `versions/`)
needs an APPROVED independent review **of this schema** and the human's
schema/runtime authorization. No Adaptive Reading UI or runtime is built first.

---

## The flow this schema serves (D-075)

```
Admin import ─► review ─► publish to the Reading Corpus ─► comprehension set
   ─► Admin review ─► learner attempt ─► attempt persisted
   ─► ability / progression ─► next passage chosen
```

No internal AI writes a source passage. AI processes content that already
exists — level, vocabulary, grammar, questions, explanations, evidence — and
every processed result an Admin has not reviewed stays invisible to learners.

## What D-075 asks, and where each part stands

| Requirement | Where it is met |
| --- | --- |
| One Reading flow; AI never writes a source passage | this schema has no generated-passage path; the generator retires at apply (§9) |
| Imports: Reading, Books, Media, Vocabulary, Sources | **already built** (`5f62174`); unchanged here |
| Registered internet sources; automatic fetch makes candidates only | **already built**: the engine never publishes (`reading_content_engine.py`: "Nothing here publishes"); polling needs `state = 'active' AND automation_allowed` (`ck_reading_source_polling_requires_approval`); publication is an Admin act |
| Ingestion method, source kind, content kind kept apart; source category deferred | §8 |
| Reversible lifecycles, no hard delete in normal flow | Books restore and the vocabulary lifecycle are **already built** (`02e8aa6`: `pending_review → published ↔ unpublished → archived → unpublished`); comprehension sets here are reversible too (§2) |
| Rights and completeness are warnings; override is audited | **already built** for vocabulary (`ba931ba`: `warnings_at_publication`, `published_over_warnings`, audit entry with the warnings overridden) |
| Adaptive Reading uses only the published corpus | §2, §4: a set belongs to a corpus article; selection reads published articles only |
| A set has type, answer, explanation, evidence grounded in the exact passage version, and passes Admin review | §2, §6 |
| One canonical attempt model; no parallel store | §1, §3 |
| Idempotent submit; a retry creates no second attempt and moves ability once | §5.1 |
| Evidence never cascades away with a content edit, archive or delete | §6, §7 |
| Ability is a rebuildable projection with policy version and checkpoint, deterministic | §4, §5.3 |
| Next article by ability, recent performance and skill weakness | §4.1 |
| Five consumers read canonical evidence before learner submit is enabled | §9 |
| Generated flow retires; test data reset, real history archived read-only; legacy decides nothing | §1, §9 |
| Text Discussion on a corpus article deferred | §9 |
| READY only after a live end-to-end run | §12 |

---

## 1. The legacy generated-passage tables become a read-only archive

`reading_sessions` and `reading_attempts` hold the AI-generated passages and the
answers to their questions. D-075 retires that flow, and the legacy shape must
not decide the new architecture. It cannot be *migrated into* the canonical
model either: a canonical attempt is an answer to an Admin-reviewed set of a
published corpus article, and a generated passage is neither — turning one into
a corpus article would be exactly the AI-authored source passage D-075 forbids,
and fabricating sets for it would invent evidence
(`ORENA_EVIDENCE_ARCHITECTURE.md` §2: "do not synthesize constituent events").

So the migration **archives** them:

- `reading_attempts` → `reading_legacy_attempts`, `reading_sessions` →
  `reading_legacy_sessions`. A rename: every row, constraint and foreign key
  stays. `text_discussions.reading_session_id` follows the rename on both
  dialects (proved). On PostgreSQL each primary-key constraint is renamed with
  its table, because `reading_attempts_pkey` would otherwise collide with the
  canonical table's own key.
- **Read-only by trigger:** no insert, no update, on either dialect (proved).
  Delete stays possible — the account-deletion workflow needs it, and so does a
  reset.
- **Nothing reads the archive as evidence.** The canonical consumers (§9) read
  the canonical model only. The archive is kept for the learner's own record,
  for account deletion, and so that a human decides its fate with evidence.

**Reset or keep — the human's call, with evidence.** D-075: sandbox/test-only
legacy data is reset or reseeded; real learner history is archived read-only.
The migration cannot know which it meets, so it always archives, which is safe
for both; it never deletes. Whether to empty the archive is then an authorized
operator act, decided by this query on the runtime in question:

```sql
SELECT u.user_key, s.language_code, count(DISTINCT s.id) AS sessions,
       count(a.id) AS attempts, min(s.created_at), max(s.created_at)
  FROM reading_legacy_sessions s
  JOIN users u ON u.id = s.user_id
  LEFT JOIN reading_legacy_attempts a ON a.session_id = s.id
 GROUP BY u.user_key, s.language_code
 ORDER BY max(s.created_at) DESC;
```

If every row belongs to test or development accounts, the human may authorize
`DELETE FROM reading_legacy_sessions` (attempts cascade) — or leave it; an
empty or populated archive changes nothing about the canonical model.

## 2. `reading_comprehension_sets` and `reading_comprehension_questions` — platform content

One reviewed set of questions for one published article, in one support
language, grounded in one exact body.

| Column | Why |
| --- | --- |
| `article_id`, `language_code` → `reading_articles (id, language)` **RESTRICT** | the set's language is its article's by construction; an article cannot take its sets with it |
| `support_language` | the language the explanations are written in; a learner meets the set in their support-language setting, or reads the article freely |
| `article_body_sha256` | the grounding anchor: the exact body every offset indexes (§6) |
| `status` | `draft`, `needs_review`, `approved`, `rejected`, `stale`, `archived` |
| `generator_version`, `model` | which processor and model produced it |
| `validation_json` | validation issues, type coverage, grounding failures |
| `reviewed_by`, `reviewed_at`, `review_reason` | who decided, when, why |

Questions: `rank` (≥ 0, not unique), `question_type` (eight types),
`prompt`, `options_json` (2–6), `correct_index` (< option count), `explanation`
(in the set's support language), `evidence_text` / `evidence_start` /
`evidence_end` (all or none, required except for `main_idea` and
`authors_purpose`), `machine_suggested`, `admin_approved`, `admin_rejected`
(never both).

Rules the database enforces (CHECKs, the partial index, triggers on both
dialects):

- **One approved set per article and support language** —
  `UNIQUE (article_id, support_language) WHERE status = 'approved'`, with both
  `postgresql_where` and `sqlite_where`. Rejected, stale and archived sets are
  history and never block a replacement.
- A set is **created undecided** and moves only along review transitions:
  `draft → needs_review`; `needs_review → draft | approved | rejected`;
  `approved → stale | archived`; `stale → approved | archived`;
  **`archived → approved` (restore)**; **`rejected → needs_review` (reopen)**.
  Every state is reversible without a delete (D-075).
- **Entering `approved` requires at least one approved question and no
  undecided one** — also on a restore.
- A decided set is **frozen**: its article, languages, anchor, generator and
  model never change, and neither do its questions. Reviewer fields change only
  on a transition into `approved` or `rejected` — a new decision names its own
  reviewer; staling and archiving keep the decision's.
- A set that reached learners (`approved`, `stale`, `archived`) is **never
  deleted**. Only `draft`, `needs_review` and `rejected` sets can be, and
  deleting one cascades its questions.
- The anchor and every digest are 64 **hex** characters
  (`ltrim(x, '0123456789abcdef') = ''`, portable).

## 3. `reading_attempts` — the one canonical Reading evidence model

A new table under the canonical name, with **one shape** and no discriminator:
a learner's submitted answers to one approved set of one published article.

| Column | Null | Why |
| --- | --- | --- |
| `id` | | |
| `user_id` → `users` CASCADE | NOT NULL | the owner |
| `language_code` | NOT NULL | ability is per language |
| `set_id` + `language_code` → sets `(id, language_code)` **RESTRICT** | NOT NULL | the evidence's subject, in the attempt's own language |
| `ordinal` | NOT NULL | 1, 2, 3 … per account and language: replay order and checkpoint |
| `operation_id`, `request_digest` | NOT NULL | the idempotency receipt (§5.1) |
| `evaluator_version` | NOT NULL | how the answers were judged |
| `passage_level` | NOT NULL | the difficulty faced, as the level was then |
| `ability_policy_version`, `passage_difficulty`, `ability_before`, `ability_after` | **all four or none** | the ability measurement; NULL is "not measured", never zero |
| `answers` | NOT NULL | `[{question_id, selected_index, correct}]`, one per approved question |
| `correct_count`, `total` | NOT NULL | `total > 0`, `0 ≤ correct_count ≤ total`, `json_array_length(answers) = total` |
| `created_at` | NOT NULL | when it was submitted |

- **A row exists only once submitted.** An unfinished answer sheet is device
  work, not evidence (`ORENA_ACCOUNT_DATA_ARCHITECTURE.md` §2).
- **Immutable:** every UPDATE is refused, on both dialects.
- **Only an approved set** can receive an attempt (trigger; `FOR SHARE` on the
  set on PostgreSQL, so a submit serializes against the set being staled or
  archived).
- **The measurement never gates the evidence.** If the active policy cannot
  measure an attempt — no mapping for its level, an out-of-range value, a
  failed replay — the attempt commits with the four ability columns NULL
  (`ORENA_EVIDENCE_ARCHITECTURE.md` §3: "Projection failure preserves source
  evidence and ordinary practice access").
- `passage_difficulty` is stored beside `passage_level` so `ability_before →
  ability_after` stays explainable after the level-to-number mapping changes.
- `answers` holds one element shape; the database bounds its length and the
  service validates each element before it writes.
- No `score` (derivable), no `completed_at` (a row is always complete), no
  `article_id` (the set's is permanent: a set with attempts cannot be deleted).
- Code written for the legacy shape **fails loudly** against this table rather
  than writing a half-row (proved with today's ORM model): there is no mixed
  period.

## 4. `reading_ability_projections` — a discardable learner projection

`id`; `user_id` → `users` CASCADE; `language_code`; `policy_version`;
`ability` (**Float**, finite, ±1,000,000 — a logit, an IRT theta and an Elo
rating all fit; NaN and infinities refused); `consumed_through_ordinal` (the
checkpoint); `by_question_type_json` (accuracy per question type);
`updated_at`. `UNIQUE (user_id, language_code, policy_version)`.

**The attempts are authoritative.** The current ability under a policy is the
latest measured attempt's `ability_after` — one bounded read. The projection
exists for what is *not* one read: accuracy **per question type** (an aggregate
over every attempt joined to its questions), the ability across **unmeasured**
attempts, and **policy transitions** (a new policy's row is built beside the old
one, and no attempt is rewritten). Where the projection and a replay disagree,
the projection is wrong and is rebuilt.

### 4.1 Choosing the next article — deterministic and testable

A pure function, versioned as `selection_policy_version` in code, of: the
projection (ability, per-type accuracy), the learner's recent attempts
(`uq_reading_attempt_ordinal`, walked backwards a bounded N), and the candidate
pool — **published** articles in the learner's language with an **approved,
still-anchored** set in their support language, not attempted recently.

1. **Ability** sets a target difficulty band around the current estimate.
2. **Recent performance** moves the band: a run of high accuracy moves it up, a
   run of low accuracy moves it down, before the projection itself has moved.
3. **Skill weakness** ranks the candidates inside the band: a set whose
   approved questions cover the learner's weakest question types ranks first.
4. **A probe** — a passage one band above — is served at a fixed cadence (every
   k-th passage by ordinal), never by chance, so the rule stays deterministic.
5. Ties break on `(published_at, id)`.

Given the same inputs it returns the same article; tests fix the inputs. No
schema is needed for it beyond what is here: the pool is served by the engine's
`ix_reading_articles_published_level` and this schema's
`uq_reading_comprehension_set_approved`.

## 5. The account-data contract

### 5.1 Idempotency (`ORENA_ACCOUNT_DATA_ARCHITECTURE.md` §4)

The client chooses an `operationId` for **one logical submit** and reuses it on
every retry. The attempt row is its own receipt. `UNIQUE (user_id,
operation_id)` — account-scoped, not language-scoped, so an id replayed under
another language is refused.

The submit transaction (PostgreSQL; the SQLite backend refuses the write, as it
refuses Listening progress and Text Discussion turns):

1. Scope comes from the server, never the body.
2. Look up `(user, operation_id)`. Found with an equal `request_digest` →
   return that row, `committed`; **ability is not moved again**. Found with a
   different digest → `rejected {operation_reused}`.
3. `pg_advisory_xact_lock` on `(account, language)`, keyed in a Reading
   namespace (e.g. `hashtextextended(user_id::text || ':' || language, <reading
   namespace>)`). Not the projection row: that would make evidence depend on the
   projection existing.
4. Re-check the operation under the lock.
5. Validate under `SELECT … FOR SHARE` of the article row: the set is approved,
   in the learner's language and support language, and still anchored (§6); the
   answers name exactly the set's approved questions, each element well formed.
6. Score under `evaluator_version`; `ordinal = max(ordinal) + 1`.
7. The measurement, best-effort in a savepoint: bring the projection up to
   date, compute `ability_after`; on failure roll back to the savepoint and
   write the four ability columns NULL.
8. Insert the attempt; advance the projection if measured. Commit.

A raced duplicate past step 4 hits the unique constraint, rolls back with no
success receipt, and re-reads step 2. `request_digest` is SHA-256 over the
canonical command (`reading.attempt.submit`, set id, sorted `question_id →
selected_index`); it guards reuse and is **not** the identity — two distinct
attempts with the same answers are two attempts.

### 5.2 Versions

`evaluator_version` on every attempt; `ability_policy_version` whenever a
measurement is present; `policy_version` on the projection;
`selection_policy_version` in code (§4.1).

### 5.3 Projection: policy version, checkpoint, discardable

An attempt applies to the projection only as `consumed_through_ordinal + 1`,
so a re-delivery is a no-op and an out-of-order one cannot apply. Every value is
recomputed by replaying the account's attempts in ordinal order under the policy
version, from facts the attempts hold (`passage_level`, per-answer correctness,
each question's type from its frozen set). Deleting a row costs a rebuild,
never evidence (proved). An unmeasured attempt is replayed like any other, so a
later policy can measure what an earlier one could not.

### 5.4 Deletion enumeration (D-054, D-055)

The account-deletion workflow is not built, and D-055's gate keeps any runtime
path from deleting an account until it is. `ACCOUNT_OWNED` enumerates, in
deletion order, every Reading row an account owns:

| Table | Predicate |
| --- | --- |
| `reading_ability_projections` | `user_id = :user_id` |
| `reading_attempts` | `user_id = :user_id` |
| `reading_legacy_attempts` | `session_id IN (SELECT id FROM reading_legacy_sessions WHERE user_id = :user_id)` |
| `reading_legacy_sessions` | `user_id = :user_id` |

Proved on both dialects: the enumeration removes one of two learners and
nothing else; the `users` foreign keys cascade too. At apply it moves into the
application code the deletion workflow imports.

### 5.5 What the account backbone will add

The contract's account incarnation, change records and stream sequence (§§1,
3–5) live in the I2 backbone (`mutation_receipts`, `change_records`,
`account_streams`, `projection_checkpoints`, `20260908_0005`), keyed by
incarnation and active only where `ORENA_ACCOUNT_BACKBONE` is on. Keying new
learner evidence to the incarnation is the decision `AGENTS.md` §7 reserves, so
this schema keys by `user_id`, like every existing domain owner. When Reading
activates on the backbone, the submit also writes a `mutation_receipts` row
(`result_ref` = the attempt id) and a `change_records` row in the same
transaction; the projection checkpoint can move to `projection_checkpoints`.
Additive, and nothing here depends on it.

## 6. Revision and grounding

No CHECK proves that evidence is in the passage — a CHECK cannot read
`reading_articles.body`. The database enforces the **structure** of a span:
all or none; non-empty; start ≥ 0; `evidence_end - evidence_start =
length(evidence_text)` (catches offsets counted in bytes or UTF-16 units;
proved with a Chinese span). **Grounding is the service's check, against one
exact body:**

- **The anchor** is `article_body_sha256`: SHA-256 over the UTF-8 bytes of
  `reading_articles.body` as stored, no normalization, 64 lowercase hex. Not
  `content_revision`, which also moves on a title, level or target change and on
  every publish. Offsets are Unicode code points into that same string.
- **Generation** computes offsets from the body, never from the model, and
  requires `body[start:end] == evidence_text`.
- **Approval** takes `SELECT … FOR UPDATE` on the article, recomputes the hash,
  requires the anchor, re-verifies every span.
- **A body edit** takes the same row lock, reads the body inside its own
  transaction, and moves every approved set whose anchor no longer matches to
  `stale`, with a review event — visible, never silent.
- **Serving and submitting** re-check the hash; a mismatch is Free Reading for
  the learner and `rejected {set_stale}` for a submit.
- **`stale → approved`** only when the hash matches again.

**Old evidence stays true.** An attempt names its set; the set's questions,
options, answer, explanation and literal `evidence_text` are frozen, and its
hash names the exact body the learner read. Editing, archiving or deleting the
article cannot change any of that (RESTRICT, frozen sets, immutable attempts).
The whole text of a superseded body is not retained — retaining article
revisions would be an engine change, not proposed here.

## 7. Deletes — RESTRICT upward from evidence

| Foreign key | ON DELETE |
| --- | --- |
| attempt `(set_id, language_code)` → set | **RESTRICT** |
| set `(article_id, language_code)` → article `(id, language)` | **RESTRICT** |
| question → set | CASCADE (only a deletable set can be deleted) |
| attempt → user, projection → user | CASCADE (owner) |
| legacy attempt → legacy session (existing) | CASCADE |

Plus: a set that reached learners is never deleted; attempts are never updated;
and each dialect's extra write is closed — SQLite `INSERT/UPDATE OR REPLACE`
(conflict guards) and PostgreSQL `TRUNCATE … CASCADE` (statement guards, so even
`TRUNCATE users CASCADE` cannot take evidence). An Admin purge of an article
deletes its undecided or rejected sets explicitly first; an article whose set
reached learners is archived, never purged.

## 8. Three concepts, three columns

| Concept | Column | Values |
| --- | --- | --- |
| How content enters | `reading_sources.source_type` | `manual, direct_url, file, rss, api, feed` |
| What kind of source it is | — | **deferred** (D-075: not needed yet; the rights columns do its work) |
| What kind of content a learner sees | `reading_articles.content_kind` | `article, news` |

`source_type` names the ingestion method despite its name; renaming it is an
engine change and not proposed. `content_kind` defaults to `article`, which
every existing row is, and reuses the Library's own chip words
(`static/orena/ui/library-browse.js`), so no new vocabulary appears. A book is
its own catalog (`reading_books`); `essay` and `story` are Library chips that
may be added later with the same words, by a CHECK change. The generator's
`material` / `READING_FORMS` vocabulary leaves with the generator.

## 9. Retiring the generated flow and moving every consumer

Every current reader of Reading evidence reads the legacy tables:

| # | Consumer | Today | At apply |
| --- | --- | --- | --- |
| 1 | Reading studio | `/api/reading/*` → `becoming_reading`, the AI generator | the generator route and prompts are **removed**; the learner Reading entry is the corpus flow |
| 2 | `/api/cross-skill-cue` | `list_reading_sessions(20)` | reads `list_reading_evidence` |
| 3 | Collection (I4) | `list_reading_sessions` → `reading_entries` | reads `list_reading_evidence`, routes to the article |
| 4 | Learner Summary (I6) | `list_reading_sessions` | reads `list_reading_evidence` |
| 5 | Admin Activity | `admin_repository` joins attempts to sessions | counts canonical attempts |
| 6 | Analytics | `list_product_activity_events`, same join | reads canonical attempts |
| 7 | Text Discussion | resolves a `reading_session` | existing threads keep pointing at the archive; no new legacy threads |
| 8 | Import / shadow tooling | `importer.py`, `verification.py` over the legacy tables | retired with the legacy SQLite import path, or pointed at the archive names |

`list_reading_evidence` is the one Reading-domain read contract: canonical
attempts only, newest first, each with its article, set, time and result.

**Order at apply — one change, no mixed period:** the migration lands together
with the code that removes the generator, maps the archive under its new names,
and moves consumers 2–6 to `list_reading_evidence`. **Learner submit stays
disabled** until those five consumers each have a test showing a canonical
attempt appears in them and the live run of §12 passes; only then is it turned
on.

**Text Discussion on a corpus article stays deferred** to its own proposal: it
changes the D-072.2 contract (`text_discussions.source_kind` has no value for a
corpus article).

## 10. Parity and the proof

- The one partial index carries both `postgresql_where` and `sqlite_where`.
- Idempotency and ordinal uniqueness are plain unique constraints.
- `json_array_length`, `length()` and `ltrim` mean the same on both dialects.
- Lifecycle rules are triggers written once per dialect; SQLite `OR REPLACE`
  and PostgreSQL `TRUNCATE` are each closed.
- Every PostgreSQL trigger function pins its `search_path`.

`tests/test_adaptive_reading_schema_proposed.py` runs **one scenario list on
both dialects**, one outcome required: SQLite always (the ORM schema built as
the hermetic suite builds it, legacy rows seeded, then the proposal's
`upgrade()`), PostgreSQL under `ORENA_TEST_POSTGRES_URL` (the real chain to
`20260923_0013` in a fresh schema, legacy rows seeded, then the proposal). It
writes the row each rule must refuse, reads the partial predicate and every
`ON DELETE` back from the catalogue, rehearses up → down → up with legacy and
canonical data present, races a writer against the downgrade on both dialects,
and checks the refusal and the lock are in the offline (`--sql`) downgrade.

**Local execution, 2026-09-24 — not CI:** PostgreSQL 16.13, 63 passed, 2
skipped (PostgreSQL-only cases on their SQLite run); SQLite alone, 31 passed.

## 11. Migration, rollback and downgrade

**Upgrade:** transactional on PostgreSQL. Two renames (with their primary-key
constraints), read-only triggers on the archive, `content_kind` and the unique
index `(id, language)` on `reading_articles`, sets, questions, canonical
attempts, projections, and the lifecycle triggers. No row is rewritten; no row
is deleted.

**Not old-code compatible, by design** (§3, §9): the migration and the code
that retires the generated flow land together.

**Downgrade never removes learner data.** It takes the write lock first
(PostgreSQL `LOCK TABLE … IN SHARE ROW EXCLUSIVE MODE` over every table it
changes; SQLite a no-op write), then refuses if any canonical attempt, set,
projection or non-default `content_kind` exists. With none, it drops the new
objects, lifts the archive's read-only triggers and gives the legacy tables
their names back with every row. Proved on both dialects, including a writer
racing the downgrade. Once the canonical model holds data, rollback is a
reviewed forward repair.

## 12. READY — only after a live end-to-end run (D-075)

Not before the schema is approved and authorized, and then only when this runs
live on the sandbox:

1. Admin imports an article → reviews → publishes it to the corpus.
2. A comprehension set is generated, reviewed and approved in the console.
3. A learner reads it and submits; the attempt persists.
4. Ability updates; the next passage is chosen by §4.1, not at random.
5. Reload: the attempt, the ability and the next choice are still there.
6. A retried submit (same `operationId`) returns the same attempt; ability
   moved once.
7. Editing the article body stales the set; the old attempt still shows the
   frozen questions and evidence it was made against.
8. The runtime is recreated (containers down and up, volumes kept) and all of
   the above still holds.
9. Cross-skill cue, Collection, Learner Summary, Admin Activity and Analytics
   show the canonical attempt.

Apply-time work the reviewer can check now: `models.py` declarations (including
`uq_reading_article_language_scope` with the composite set→article FK — without
it SQLite reports "foreign key mismatch") and triggers on the `create_all` path
with a parity test; the submit transaction (§5.1), the rebuild (§5.3) and the
selection policy (§4.1) with deterministic tests; `list_reading_evidence` and
the five consumers; the generator's removal and a `LEGACY_TOMBSTONES.md` entry;
the article row lock, stale transition and exact hash in the engine (§6); set
decisions written to `reading_review_events`; `ACCOUNT_OWNED` moved into
application code; `content_kind` in `LEARNER_VISIBLE_FIELDS` and the publish
contract; the learner surface reading `explanation` in `support_language`
(`comprehension.js` reads `explanation_vi` today); `reading_attempts` in
`runtime_backup.COMPARED`.

## 13. Not proposed

No ML; no second vocabulary store; no change to Free Reading; no source
category; no Text Discussion on corpus articles; no retention of whole article
revisions; no automatic deletion of the legacy archive.

## Review questions

1. Is archiving the legacy tables by rename + read-only trigger the right
   reading of D-075 ("archive read-only; the legacy shape decides nothing"),
   against a dump-and-drop or a copy into a separate archive schema?
2. Is it right that nothing reads the archive as evidence — so a learner with
   real legacy history starts the canonical model with no Reading evidence —
   or should the Learner Summary carry a labeled legacy baseline
   (`ORENA_EVIDENCE_ARCHITECTURE.md` §2 allows one)?
3. Is a migration that is deliberately not old-code-compatible acceptable,
   given that its downgrade restores the legacy tables exactly while the
   canonical model is empty?
4. Does §4.1's selection need anything stored — for example, the
   `selection_policy_version` that chose a passage — for it to be testable and
   explainable after the fact?
