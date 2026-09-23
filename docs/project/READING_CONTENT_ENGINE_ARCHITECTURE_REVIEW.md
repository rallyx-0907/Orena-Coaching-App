# Reading Content Engine — independent architecture review

Status: **round 4 `APPROVE`** — no P0 and no P1 remain. Round 1 `CHANGES
REQUIRED` (seven P1), round 2 `REQUEST CHANGES` (two new P1, six P2), round 3
`REQUEST CHANGES` (one P1 in the worker implementation, four P2; the schema
itself carried none), round 4 `APPROVE` with three non-blocking P2s, all since
resolved. The approval is an architecture-review verdict only: human
schema/runtime authorization is still required before anything is applied. Each round is recorded in full below, condensed without loss
of substance — the verdict, every finding, every required change and the
authorization boundary are the reviewer's own. What each round changed is under
"Resolution" at the end of this file.

**Note added 2026-09-23, after rounds 1–4 below.** `codex/work` was merged
into this lane at `61e9668`, so the proposed migration was rebased in commit
`fbe6fec`: revision `20260922_0010` (parent `20260916_0009`) became revision
`20260923_0013` (parent `20260922_0012`), and the file was renamed from
`migrations/proposed/20260922_0010_reading_content_engine.py` to
`migrations/proposed/20260923_0013_reading_content_engine.py`. Rounds 1–4
reviewed that same file under its former name, and the text below is left
exactly as each reviewer wrote it — the identifier in their words is
historical, not stale. Round 5 reviewed the rebase itself and confirmed the
schema is byte-identical apart from those identifiers and two audit strings. The rebase changed `revision`, `down_revision`, the chain paragraph
and the seed `created_by` string, and nothing else; the delta is being
re-reviewed separately.

## Review record

- Reviewer role: Delegated Architecture Reviewer (`AGENTS.md`, "Architecture
  review authority").
- Reviewer identity: independent Claude review session, dispatched read-only
  with no authority to edit, commit or implement.
- Fallback justification (recorded by the implementer who dispatched the
  review, not by the reviewer): GPT-6/Codex, the preferred Principal
  Architect, was not reachable from this lane, so `AGENTS.md`'s delegated
  reviewer role was used.
- Reviewer model: Claude Opus 5
- Reviewed commit: `5eeaac72d37f2c9d1a1460da248c21e2f99e9957`
- Branch / worktree: `admin/control-center`, working tree clean at review time
- Review date: 2026-09-22
- Scope: the six proposed tables, their constraints and indexes, the durable
  job queue's claim and crash-recovery design, and the proposal document's
  claims against the code.
- The implementer of this schema did not approve it; `AGENTS.md` forbids that.

---

## Verdict

**CHANGES REQUIRED** — in `REVIEW_POLICY.md`'s own vocabulary, **REQUEST
CHANGES**: seven P1 findings remain, and "Unresolved P0 or P1 findings require
REQUEST CHANGES."

Two vocabulary notes from the reviewer, since this is recorded verbatim:
`REVIEW_POLICY.md` defines only P0 / P1 / P2 (there is no P3) and only APPROVE
/ REQUEST CHANGES. `migrations/proposed/README.md` shows "APPROVED WITH
REQUIRED CHANGES" used historically for 0005 and 0006; the reviewer did not use
it here because the required changes are to the schema itself, not to code
around an approved schema.

No P0. Nothing is applied — `alembic.ini` points at `migrations/versions/` only
— so there is no immediate persistence risk.

## The design is sound in its foundations

Stated by the reviewer before the defects, so the load-bearing decisions are
not relitigated in a revision:

- **Genuinely additive.** `upgrade()` contains exactly 6 `op.create_table` and
  13 `op.create_index` calls and nothing else — no `alter_column`,
  `add_column`, `drop_*`, `execute`, `bulk_insert` or `rename`. No foreign key
  points into any pre-existing table. All six names are new.
- **It does not encroach on the `AGENTS.md` §7 hold, and is more careful than
  the baseline.** Zero occurrences of `user_id`, `account_`, `learner_` or
  `incarnation`. No reading position, highlight or progress. Admin identities
  are plain `String` rather than foreign keys — avoiding the coupling
  `audit_logs.user_id → users.id` already has. "The proposal's strongest
  property."
- **The job-claim statement is correct under concurrency** (see P1-4).
- **The three-way sources / source_items / articles split is right**, and so is
  keeping targets as a table rather than JSON.
- **Its factual claims about existing code check out** —
  `media_fallback.py` is genuinely a process-local in-memory registry,
  `admin_console_api.py:1009` does raise `503 vocabulary_schema_unavailable`,
  and `versions/` head is `20260916_0009`.

## Findings, most severe first

### P1-1 — `uq_reading_source_items_native` makes the documented revision rule impossible to execute

The index is `UNIQUE (source_id, source_native_id) WHERE source_native_id <> ''`.
`revision` is not in the key. For any item carrying a native id — every
RSS/API item, precisely the case the revision mechanism exists for — inserting
revision 2 violates the index, so the only way to record a changed source is to
`UPDATE` `original_content`/`content_hash` in place: exactly the silent
overwrite the docstring says is impossible, destroying the snapshot evidence
behind an already-published article. `revision` and `supersedes_id` are
unreachable for every case they were designed for.

**Required:** put `revision` in the key, or add a currency marker
(`superseded_at`) and make it
`UNIQUE (source_id, source_native_id) WHERE source_native_id <> '' AND superseded_at IS NULL`.
The second is better: it still enforces "one current item per native id" while
permitting the history. State which row a re-fetch resolves to.

### P1-2 — Immutability is asserted but nothing enforces it; `content_hash` is not tied to `original_content`

No trigger, no revoke, no generated column, no constraint relating the hash to
the content. Any `UPDATE` rewrites the snapshot and a mismatch is undetectable,
while the proposal uses immutability as the entire safety argument for keeping
the original behind an editable article.

**Required:** pick one and write it down — (a) a `BEFORE UPDATE` trigger
rejecting changes to `source_id`, `original_content`, `content_hash`,
`fetched_at`; or (b) an explicit statement that immutability is a repository
invariant, plus a test proving the repository issues no `UPDATE` against those
columns, plus a hash-verification path. Not prose alone.

### P1-3 — `uq_reading_target_form` caps an article at one target without a canonical form

`UNIQUE (article_id, canonical_form)` is a full unique constraint and
`canonical_form` defaults to `''`. An article carries 3–8 targets; the moment
the processor cannot canonicalize two of them, the second insert fails — on the
primary workflow. The same reasoning was applied correctly one table earlier
("empty is not an identity") and not carried here.

**Required:** make it partial (`WHERE canonical_form <> ''`), or make
`canonical_form` NOT NULL with no default. State which.

### P1-4 — A job whose worker dies before its first heartbeat is stuck in `running` forever

The claim statement itself is safe under concurrency: under READ COMMITTED the
locking subquery re-evaluates its predicate against the latest row version
after taking the lock, so a row another worker just moved out of `queued` is
filtered rather than double-claimed; `SKIP LOCKED` stops one poisoned row
serializing the queue. No lost update, no double-processing.

The stuck-job case is real. `WHERE status='running' AND heartbeat_at < now() - :stale`
never matches a NULL — three-valued logic returns UNKNOWN — and the documented
claim statement never states that it sets `heartbeat_at`. A worker killed
between claiming and its first heartbeat leaves a permanently stuck row, and
`attempt` is not advanced either, so nothing notices.

**Required:** the claim must set `heartbeat_at = now()` with `started_at`,
`claimed_by` and `attempt = attempt + 1` in the same `UPDATE`; the reaper
predicate must be written against `COALESCE(heartbeat_at, started_at,
created_at)`. Write both statements out in full. Add `AND status = 'queued'` to
the outer `UPDATE` as defense-in-depth.

### P1-5 — `ix_reading_jobs_claim`'s column order does not serve the claim query, and the docstring says it does

The index is `(status, next_retry_at, created_at)`; the query is
`WHERE status='queued' AND next_retry_at <= now() ORDER BY created_at, id LIMIT 1`.
`next_retry_at` is a range predicate, and a range on a preceding column
destroys the index's ordering on the following one, so PostgreSQL must read
every due row and sort. Cost grows with queue depth — the exact property the
document claims it does not have.

**Required:** order it `(status, created_at, id)`, or better a partial index on
`(created_at, id) WHERE status = 'queued'`, so the scan walks in `created_at`
order inside the queued set and stops at the first row passing
`next_retry_at <= now()` as a filter. Correct the docstring table and §6.

### P1-6 — `uq_reading_job_request_hash` is global and permanent, so a text can never be re-ingested

`UNIQUE (request_hash)` across the whole table with no scope and no expiry.
(a) Once a job ends `failed` or `cancelled`, that input can never be submitted
again, so "retryable by an explicit admin action" must mean mutating the
existing row — never stated, and it loses the attempt history. (b) What goes
into the hash is never specified; if `source_id` is not part of it, the same
text offered to two sources collides and the second can never ingest it.

**Required:** scope uniqueness to live submissions (partial unique
`WHERE status IN ('queued','running')`) or add an explicit discriminator. State
exactly what is hashed (it must include `source_id`) and what admin "Retry"
does: new row or mutated row.

### P1-7 — `reading_ingestion_jobs.source_id` is NOT NULL and no source row exists to point at

`SOURCE_TYPES` includes `manual`, `direct_url` and `file`, so the manual path
needs a `reading_sources` row, and both the job and the snapshot require one.
The migration seeds none, and neither document says whether the migration
seeds them, the repository lazily creates one per type, or one is created per
submission. This is load-bearing: `uq_reading_source_items_hash` is
`(source_id, content_hash)`, so dedupe on the manual path works only if all
manual pastes share one `source_id`. `reading_sources.state` also defaults to
`needs_review`, so a seeded manual source needs a state that permits
submission and satisfies `ck_reading_source_polling_requires_approval`.

**Required:** state the rule; if it is seeding, put the seed rows in this
migration with fixed UUIDs and an explicit state.

### P2-1 — No constraint in this migration is exercised by CI

`.github/workflows/ci.yml` runs pytest with `PERSISTENCE_BACKEND: sqlite` and
never sets `ORENA_TEST_POSTGRES_URL`; every `command.upgrade(cfg, 'head')` in
the suite is gated behind that variable; the hermetic SQLite path hand-writes
its own DDL without CHECK constraints or unique indexes. So the CHECKs do not
fail on SQLite — they never run on SQLite, or in CI, at all. Each is valid
PostgreSQL, but "a CHECK constraint, not just application code" is true only on
a runtime CI never builds.

**Required:** commit to a PostgreSQL proof under `ORENA_TEST_POSTGRES_URL`
asserting that each named constraint rejects its violation, following the
0008/0009 pattern; state that any SQLite fixture table must mirror this DDL.

**Recorded latent property:** `sqlite_where` appears nowhere in this
repository. If this DDL is ever executed on SQLite, all four `postgresql_where`
partial indexes silently become full indexes.

### P2-2 — `effective_level` is a stored column with nothing tying it to its inputs

A stored column is the right choice — it is what the compound partial index can
be built on — but leaving it unconstrained is an avoidable hazard when the rule
is one portable CHECK.

**Required:** add `CHECK (effective_level = COALESCE(reviewed_level, estimated_level))`
and `CHECK (reviewed_level IS NULL OR reviewed_level <> '')`, now rather than
later against a populated table.

### P2-3 — `ix_reading_articles_source_item` is strictly redundant

`UniqueConstraint("source_item_id")` already creates a unique btree on exactly
that column. Duplicate index paying write cost on every insert and update. Drop
it.

### P2-4 — The index rationale table omits an index the migration creates

`ix_reading_sources_state` is created but absent from the table and has no
stated query. Name its query or drop it.

### P2-5 — Two further index claims are overstated

(a) `ix_reading_articles_published` is `(language, published_at)` while the
query is `ORDER BY published_at DESC, id DESC` with keyset pagination. The
partial-index + cursor combination does work in PostgreSQL — the planner can
use a partial index when the query's `WHERE` implies its predicate, btree scans
run backwards, and `(published_at, id) < (?, ?)` is a supported row comparison —
but only the `id` tiebreak falls to a filter. Adding `id` as the third column
makes it exact. The approved `ix_reading_books_language_status_created` has the
same shape, so this is a small pre-existing pattern, not a new defect; fix it
here while it is free.

(b) `ix_reading_articles_queue` is `(status, created_at)` for
`status IN (...) ORDER BY created_at DESC`. A multi-value `IN` on the leading
column does not reliably yield one globally ordered stream; expect a sort.
Acceptable for a review queue — soften the blanket claim.

### P2-6 — Cross-source duplicates are possible and the proposal says they are not

`uq_reading_source_items_hash` is `(source_id, content_hash)`; the same text
under two sources produces two snapshots and two published articles.
Per-source scoping is defensible — rights differ per source — but learners
would see duplicates.

**Required:** soften the claim to "per source", and/or add a non-unique index
on `content_hash` alone so review can surface "this content already exists as
article X" before publish.

On "source reverts to earlier bytes": the stated behaviour — resolving to the
existing row rather than a third revision — is defensible and should be kept.

### P2-7 — Delete/cascade asymmetry is right in direction but incomplete at the published article

The RESTRICT choices are correct. The gap: `reading_articles` itself — the only
row a learner reads — has the weakest protection. One `DELETE` removes the
article, its approved targets, its entire decision history, and the link from
the job that produced it. CASCADE on targets is right; CASCADE on
`reading_review_events` is defensible only because `audit_logs` receives every
mutation independently — say that explicitly as the retention authority, and
require that a purge writes an audit entry before the delete.
`supersedes_id → SET NULL` silently breaks a revision chain; RESTRICT would be
consistent, or at minimum make the broken-chain state detectable.

### P2-8 — `ck_reading_source_item_hash` does not stop a case-variant hash defeating dedupe

`length(content_hash) = 64` permits uppercase and non-hex; an uppercase SHA-256
of identical bytes is a distinct value under the dedupe key. Add the portable
`CHECK (content_hash = lower(content_hash))`.

### P2-9 — Two smaller constraint/DDL notes

(a) `ck_reading_source_polling_requires_approval` is "the strongest constraint
in the file" and is endorsed. One consequence to name: it forces
`polling_enabled = false` whenever `state` leaves `'active'`, so pausing erases
the intent to poll. If pause is meant to be reversible, hold the intent
separately or state that resume re-enables explicitly. Prefer
`NOT polling_enabled OR (...)` over `polling_enabled = false`.

(b) `next_retry_at` is NOT NULL with no `server_default` in a file that
otherwise defaults every NOT NULL column; a job inserted with a future value
never runs and nothing flags it. The same applies to the nine `sa.JSON()` NOT
NULL columns — defensible, but state it as deliberate rather than drift.

### P2-10 — The reaper must consume an attempt, or a worker-killing job loops forever

Nothing in the schema or the documented statements says the reaper increments
`attempt`, and there is no `CHECK (attempt <= max_attempts)`. A job that
reliably kills its worker cycles `running → queued` indefinitely.

### P2-11 — Retry ordering lets a failing job preempt new work (informational)

`ORDER BY created_at, id` uses the original `created_at`, so a retried job is
claimed ahead of every newer job the moment its backoff expires. Bounded by
`max_attempts` and harmless at concurrency 1; named for when concurrency rises.

## Question answered directly: six tables is right

- `reading_review_events` should **not** fold into `audit_logs`: that table is
  indexed only on `created_at`, so rendering one article's history would be a
  full scan, and fixing it means indexing a shared platform table — destroying
  the purely-additive property. `audit_logs.user_id` is also a foreign key to
  `users.id`, so reusing it would couple the engine to the account table
  `AGENTS.md` §7 reserves. Both arguments are stronger than the one the
  proposal made, and should be written into it.
- `reading_article_targets` should **not** be JSON: per-row approval must
  survive a processor re-run, the admin reorders by `rank`, and the future
  "which articles teach this collocation" query is a join.
- The sources / source_items / articles split is correct; the job table is
  necessary.

## Required before a human is asked to authorize this

1. Resolve P1-1 … P1-7 in the migration and re-state the affected paragraphs so
   prose and constraints agree.
2. Write the claim statement and the reaper statement out in full.
3. Commit to the PostgreSQL constraint proof under `ORENA_TEST_POSTGRES_URL`.
4. State the `reading_sources` seeding / creation rule and, if seeding, put it
   in the migration.
5. Correct the index rationale table so every created index appears exactly
   once with a query it actually serves.
6. Re-review after revision. An implementer may not self-approve this.
7. `downgrade()` drops six tables that may by then hold published,
   learner-visible content. Its drop order is correct, but it must never be run
   against a runtime with published articles; say so where the rollback path is
   described.

## What the reviewer verified, and how

Live Git state verified by the reviewer itself (`git rev-parse HEAD` →
`5eeaac72d37f2c9d1a1460da248c21e2f99e9957`, clean tree, `git show --stat` → 3
files, +672/−2; no git state mutated, review entirely read-only). Governance:
`AGENTS.md`, `ARCHITECTURE_INVARIANTS.md`, `REVIEW_POLICY.md`,
`CURRENT_HANDOFF.md`. Under review in full: the migration (497 lines) and the
request (173 lines). Precedent in full: `20260916_0009_reading_library.py`,
`migrations/proposed/README.md`, `VOCABULARY_SOURCE_ARCHITECTURE_REVIEW.md`,
the 0008 constraint inventory, `reading_library_repository.py`'s keyset SQL,
`admin_repository.py`'s portable-SQL style, `models.py`'s index inventory and a
table-name collision check. Additivity checked mechanically by grep.
Test/CI reality checked against `.github/workflows/ci.yml` and every
`command.upgrade` call site. SQL semantics were reasoned through, not executed:
no PostgreSQL runtime was started, per the shared-runtime rule, and no test
suite, validator or CI run was executed as part of this review — no PASS of any
kind is claimed.

## Authorization boundary

This review does not authorize schema activation, deployment, or product
approval. The migration remains in `migrations/proposed/`, where Alembic does
not read it, and still requires — after the required changes and a re-review —
explicit human schema/runtime authorization, then the documented rehearsal
against a throwaway PostgreSQL database, then one `git mv` into
`migrations/versions/`, then application to the named sandbox runtime only.
Production (8000) and preview (8010) retain every gate in
`ARCHITECTURE_INVARIANTS.md § Human gates`.

---

## Round 1 resolution

Answered in commit `e375ad3`. Every one of the seven P1s and eleven P2s was
changed in the migration rather than argued with; §10 of
`READING_CONTENT_ENGINE_SCHEMA_REVIEW_REQUEST.md` maps each finding to what
changed, and the round-2 reviewer verified each against the code (table below).

---

# Round 2 — the revision reviewed

- Reviewed commit: `e375ad3f164f1344b9635d41acdf4908369934d2`
- Same reviewer role, model and read-only constraints as round 1.
- Review date: 2026-09-22

## Verdict

**REQUEST CHANGES** — two new P1 and six P2. `REVIEW_POLICY.md`: "at least one
P0 or P1 remains, **or required evidence is missing**" — both limbs applied.

All seven round-1 P1s and all eleven round-1 P2s were verified fixed **against
the code, not the summary**, with two fixes judged better than what was asked
for (P1-4 removing the NULL rather than coalescing it; P1-5 taking the stronger
of the two offered index shapes). Still purely additive, still no `users`
foreign key, still no learner-owned column.

## New findings

### P1-A — The revert case is now reachable, and the two dedupe indexes disagree about it

Round 1 called "a source reverts to earlier bytes" defensible but *unreachable*;
P1-1's fix made it reachable. `uq_reading_source_items_hash` stayed a full
`UNIQUE (source_id, content_hash)` while its sibling became scoped to current
rows, so the three possible revert behaviours disagree: resolving to the
existing row leaves a superseded row as the truth, inserting a fresh row is
blocked by the unscoped hash index, and clearing `superseded_at` makes
`revision` run backwards. Nothing stated which the repository does.

**Required:** state the revert algorithm, or scope the hash index.
Documentation-only is an acceptable resolution. Not reachable in Phase A —
manual, URL and file sources all carry an empty `source_native_id` and never
supersede — but the index scoping is being locked in now.

### P1-B — Nothing had ever executed this DDL, and the revision added the constructs most likely to fail on first execution

The revision introduced a plpgsql function, a trigger and a `bulk_insert` —
the first `bulk_insert` anywhere in the repository. §11 ordered the gate
re-review → human authorization → rehearsal, which asks a human to authorize
DDL nobody has run. The 0009 precedent runs the other way: the standalone
up/down/up rehearsal proves the migration sound *before* it is moved.

**Required:** run the rehearsal against a throwaway PostgreSQL before the human
gate and report that the function and trigger are created, that the trigger
rejects a snapshot rewrite and permits a `superseded_at` stamp, and that the
seed rows land satisfying the polling CHECK. The written commitment *is*
sufficient for the PostgreSQL constraint test not yet existing (it cannot pass
before the `git mv`); it is **not** sufficient for the rehearsal.

### P2-C — The trigger protected content but not provenance or rights

`rights_snapshot_json` (the whole point of snapshotting rights),
`source_native_id` and `canonical_url` (the dedupe identity, and the partial
index the supersede rule depends on) were left rewritable. **Required:** add
them, and `supersedes_id`; say which descriptive columns stay writable.

### P2-D — The `attempt < max_attempts` guard is correct, and leaves an unswept terminal state

The guard is right and should stay: with it the claim can never violate
`ck_reading_job_attempt_bound`. But a `queued` row with no attempts left is now
invisible to the claim and to the reaper, so it sits in Admin → Imports forever
as pending work that can never run. **Required:** the worker loop must also
fail out `status = 'queued' AND attempt >= max_attempts`.

### P2-E — Not offline-mode safe, and `--sql` is how a human would read it

`op.get_bind().dialect.name` raises in offline mode (the context has no bind),
and `op.bulk_insert` without `multiinsert=False` silently omits the seed rows
from a `--sql` script. **Required:** use `op.get_context().dialect.name`; make
the seeds render offline.

### P2-F — `CREATE FUNCTION` without `OR REPLACE`; the exception carries no SQLSTATE

A re-run after a partially failed migration is blocked, and plpgsql's default
`P0001` is indistinguishable from any other raise, so the repository cannot
recognise this refusal. Verified positively: the body contains no colon, so
Alembic's `text()` cannot misparse it as a bind parameter.

### P2-G — Supersede ordering is now load-bearing and unstated

The partial index forces "stamp the old row, then insert the new one", in one
transaction; the reverse collides. Recorded positive: that same index
serializes two workers racing to supersede the same item, so the application
does not have to. Optional: `CHECK ((revision > 1) = (supersedes_id IS NOT
NULL))`.

### P2-H — The recorded round-1 review is faithful in substance; three accuracy points

Verdict, SHA, all findings, every "Required:", the six-tables answer and the
authorization boundary are intact and unsoftened. But "verbatim" overstated a
condensed record; the GPT-6 availability note was attributed to the reviewer
rather than the implementer who dispatched it; and "Resolution" was still a
placeholder.

## Round 2 resolution

| Finding | Change |
| --- | --- |
| P1-A | Revert algorithm stated in the migration docstring ("Supersede, and what happens when a source reverts"): the revert clears `superseded_at` on the earlier row and stamps the row that had been current, in one transaction; `revision` is documented as a creation-order counter, not a currency rank, and `superseded_at IS NULL` is the only test for "current". Documentation-only, as the reviewer allowed — the hash index keeps its shape. |
| P1-B | **Rehearsal executed** against a throwaway PostgreSQL 16 (tmpfs, no named volume, removed afterwards): up → down → up, clean both ways. It found a real defect (see below). §11 of the request reordered so the rehearsal precedes the human gate, with its result reported. |
| P2-C | Trigger now also refuses `rights_snapshot_json`, `source_native_id`, `canonical_url` and `supersedes_id`; the writable descriptive columns are named. |
| P2-D | `reap_stale()` sweeps `queued` rows with no attempts left, failing them `attempts_exhausted`; proved by a test that was red first. |
| P2-E | `op.get_context().dialect.name`; seeding rewritten as literal `op.execute` statements, because SQLAlchemy has **no literal renderer for a JSON value** — `bulk_insert` with a JSON column fails to render offline even with `multiinsert=False`. Offline `--sql` now renders 6 tables, 3 seed inserts, the function, the trigger and 10 partial indexes. |
| P2-F | `CREATE OR REPLACE FUNCTION`; `USING ERRCODE = '23514'`. |
| P2-G | Supersede ordering and the index-serializes-the-race property written into the docstring; `CHECK ((revision > 1) = (supersedes_id IS NOT NULL))` added. |
| P2-H | "Verbatim" corrected to "recorded in full, condensed without loss of substance"; the GPT-6 note moved to an implementer-attributed line; this Resolution written. |

**What the rehearsal caught, which is why the reviewer required it:** the
trigger's `NEW.rights_snapshot_json IS DISTINCT FROM OLD.rights_snapshot_json`
raised `operator does not exist: json = json` — PostgreSQL's `json` type has no
equality operator. The trigger would have rejected **every** update to
`reading_source_items`, including the one legitimate `superseded_at` stamp, and
no amount of reading would have shown it. The comparison is now
`CAST(... AS text)`, and the rehearsal proves the trigger refuses a rewrite of
content, hash, rights, native id and canonical URL (SQLSTATE 23514 in each
case), permits the `superseded_at` stamp and a descriptive correction, and that
the partial index refuses two current rows for one native id.

Rehearsal evidence (local execution, not CI): `[up] chain applied to head`,
head `20260922_0010`, six engine tables, `reading_source_item_immutable`
trigger and its function present, three seed rows with the fixed ids at
`state=active automation=False polling=False`, five trigger refusals, two
permitted updates, the polling CHECK refusing `polling_enabled` without
`automation_allowed`, `[down] reading engine tables left=0 function left=0`,
`[up-again] seed rows=3`.

---

# Round 3 — the revision and the worker implementation reviewed

- Reviewed commit: `a78521653d09edc4fb2100de342f24db0b1c7aec`
- Same reviewer role, model and read-only constraints as rounds 1 and 2.
- Review date: 2026-09-22

## Verdict

**REQUEST CHANGES** — one P1 and four P2. Every round-2 finding verified fixed,
and **the block was not in the schema**: the migration carried no outstanding
P1. The P1 was in `writing_coach/persistence/reading_job_repository.py`, which
did not hold the exclusion property the proposal claims for it.

## The two direct questions, answered

**Is the textual rights comparison the right call?** Yes, and stronger than
claimed: `json` stores the exact input text, so `CAST(json AS text)` compares
the bytes as stored, and byte-identity is the correct definition of
"unchanged" for a column whose purpose is evidence. Switching to `jsonb` for a
native `=` would make the guard semantic rather than byte-exact — weaker for
evidence. Residual to write down: the guard's freedom from false positives
depends on every write being a targeted `UPDATE ... SET superseded_at = ...`;
a whole-row write or an ORM `merge()` that re-serialises the JSON would be
refused although nothing changed.

**Does anything else in the trigger have the same problem?** No — verified
column by column. `json` was the only protected type without an equality
operator; `metadata_json`, the other `json` column, is deliberately writable
and never reaches the comparison.

## P1 — The queue's state transitions did not verify the job was still the worker's

`heartbeat()` guarded on `status='running' AND claimed_by=:worker`, proving the
design intent that a worker can lose its job. No other mutating path acted on
it: `complete()` and `fail()` filtered on `id` alone, `advance_stage()` on `id`
and status, and the reaper's per-row `UPDATE` on `id` alone after an unlocked
`SELECT`.

The deterministic sequence: worker A claims J; A stalls past the stale window;
the reaper returns J to `queued`; worker B claims it; A wakes and calls
`complete()`, which lands unconditionally — finishing a job B is in the middle
of and overwriting the result with A's stale one. The two-reaper variant
re-queues a running job and produces genuine double processing, which §5 of the
request states flatly cannot happen.

P1 rather than P0 because concurrency defaults to 1, the schema is not applied
and nothing runs anywhere; it becomes live the moment a second worker process
runs, which §5 explicitly contemplates.

**Required:** ownership guards on `complete`, `fail` and `advance_stage`,
reported to the caller the way `heartbeat()` already does; the reaper's write
carrying `status = 'running' AND heartbeat_at < cutoff`, preferably as the
single set-based statement the migration docstring already specifies; and the
step-by-step regression test, which is fully deterministic with the injectable
`now=`.

## P2-A — The documented claim was one statement; the implementation was read-then-write

Safe as written — all three statements ran inside one transaction and the
`UPDATE` re-checked `status='queued'` — but the proposal asserts a property of
a statement that was not the statement being run, on the one design point the
review exists to approve. Either implement the single statement or document
the two-statement form and why it is equivalent.

## P2-B — The seed statements were PostgreSQL-only SQL in an otherwise portable migration

`now()` does not exist on SQLite; the UUID literal renders in the dashed form
while `sa.Uuid()` stores `value.hex` on a non-native backend; and `name` is
interpolated unescaped, so a future source called `Reader's Digest` would break
the statement. Nothing breaks today. Verified positively, and worth a comment
so nobody "fixes" it back: `created_by` had to become `migration 20260922_0010`
with a space, because Alembic wraps `op.execute` in `text()` and SQLAlchemy
reads `:` followed by word characters — digits included — as a bind parameter.

## P2-C — Six models now sit in `Base.metadata` with no revision in `versions/`

`alembic revision --autogenerate` on this lane will propose creating all six
tables until the `git mv`. The more serious version of the risk is **absent**:
`readiness()` classifies on the Alembic revision and the emptiness of the table
set, never on `Base.metadata`, so startup does not refuse a database that lacks
these tables. Two consequences to state once: `create_all()` creates the tables
but neither the trigger nor the seeds, so hermetic tests seed their own source;
and the partial indexes are now declared twice, which only the PostgreSQL proof
can keep from drifting.

## P2-D — The revision chain is a tree after a revert

After a revert followed by a further change, two rows can share one
`supersedes_id`. `ck_reading_source_item_chain` permits it and the docstring is
consistent with it, but a history renderer that walks the chain expecting a
list will be wrong.

## Round 3 resolution

| Finding | Change |
| --- | --- |
| P1 | `_owned_by(job, worker)` — still running, still this worker's — now guards `complete()`, `fail()`, `advance_stage()` and `heartbeat()`, each returning whether the write landed; the engine threads the claiming worker's id through every report. The reaper is two set-based `UPDATE`s with their predicates built in (`status='running' AND heartbeat_at < cutoff`, and the exhausted-queue sweep), so there is no read to overtake. Two regression tests, written red first: a late worker cannot finish, fail or advance a job that was taken from it, and a heartbeat landing inside the reaper's window keeps the job with its worker. |
| P2-A | `claim()` is now the single `UPDATE ... WHERE status='queued' AND id = (SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING id` the proposal describes. Verified rendering on both dialects: PostgreSQL emits `FOR UPDATE SKIP LOCKED`, SQLite emits the subquery without it, and `RETURNING` is supported by both (SQLite 3.46 in the image). The module docstring now describes what the code does. |
| P2-B | `CURRENT_TIMESTAMP` instead of `now()`; the UUID-literal and apostrophe constraints, and the colon/bind-parameter reason for `migration 20260922_0010`, written as comments at the seeding block. Re-rehearsed after the change: up/down/up clean, three seeds landing, all five trigger refusals at SQLSTATE 23514, offline `--sql` rendering 3 inserts with `CURRENT_TIMESTAMP`. |
| P2-C | §9 of the request now states the autogenerate consequence, that it ends at the `git mv`, that `create_all()` creates neither trigger nor seeds (so hermetic tests seed their own source), and that the doubly-declared partial indexes are what §11.4's proof must check with `pg_indexes.indexdef`. |
| P2-D | The tree consequence written into the migration docstring's revert section. |
| Trigger residual | The `CAST` rationale ("do not fix this to jsonb") written into the migration, and the targeted-`UPDATE` requirement into `reading_content_repository.py`'s module docstring, where the code that must honour it lives. |

---

# Round 4 — APPROVE

- Reviewed commit: `e09c6ce6fa42604cd0850075f2f0dda02160b922`
- Same reviewer role, model and read-only constraints as rounds 1–3.
- Review date: 2026-09-22

## Verdict

**APPROVE.** No P0 and no P1 remain. Three P2 findings, none elevated:
`REVIEW_POLICY.md` makes P2 "non-blocking improvement unless the task or
reviewer explicitly elevates it", and two of the three are unreachable in the
authorized Phase A scope.

Scope of the approval, in the reviewer's words: "the six-table schema, the
supersede and revert rules and their immutability trigger, the dedupe and
idempotency constraints, the claim/reaper design *and its implementation*, the
delete behaviour, and the indexes". Not reviewed and not covered: the content
repository's other tests, `reading_worker.py`'s loop structure, and any admin
API route or authorization-matrix entry.

## The round-3 P1 is properly fixed

Checked by predicate rather than by description: `_owned_by()` guards
`heartbeat`, `advance_stage`, `complete` and `fail`, including `fail()`'s
attempt/max_attempts *decision* read — "that was the subtle half and it is
closed". The reaper is two set-based `UPDATE`s with the predicate in the write
and `case()` evaluated per row in the database, so a stranded job with no
attempts left goes straight to `failed` without transiting `queued`. `claim()`
is the single locking statement §5 has claimed since round 1. Both regression
tests walk the sequences the reviewer specified.

## The three questions, answered

**Does the revert path match the documented algorithm?** Yes in mechanism —
stamp-then-clear, `revision` and `supersedes_id` untouched, both statements
writing only `superseded_at` (the targeted-`UPDATE` discipline the trigger
requires), and a concurrent insert between the two statements rolls the
transaction back rather than leaving two current rows. One keying defect,
P2-B.

**Can `process()` still write after losing its job?** Yes, to the content
tables — P2-A.

**Do the learner projections leak?** No, checked field by field. The list
returns ten card fields; `estimated_level`, its confidence, `status`,
`analysis_json`, `rejection_reason` and the rest are absent. The detail filters
targets to `admin_approved`, projects them to five fields, and reads four
columns of the source item — no `original_content`, no rights payload, no
review events, no job state. Both entry points filter on `published`. "That is
a clean boundary."

## Findings

### P2-A — `process()` threaded the worker id but ignored the signal it got back

`advance_stage()` returns whether the write landed; `process()` discarded it,
so a worker that had already lost its job continued through fetch, normalize,
`record_source_item()` and `create_article()`. Content-addressing and
`uq_reading_article_source_item` prevent a duplicate article, but the revert
branch toggles `superseded_at` on two rows — a zombie worker reaching it
changes which snapshot is current on behalf of a job it no longer owns.

### P2-B — The revert branch keyed on the content hash alone

The lookup is `(source_id, content_hash)` and the revert action was scoped by
the *stored* row's native id, ignoring the incoming one. A feed that
regenerates its guids can offer bytes already held under a new id; that fired
the revert branch and flipped the currency of an item the fetch never named.
Not reachable in Phase A — manual, URL and file sources all carry an empty
native id and never supersede — but it must be closed before the RSS/API
adapter ships.

### P2-C — The learner list read every body it then threw away

`select(ReadingArticle)` reads `body`, `analysis_json`, `adaptation_json` and
`rejection_reason` from disk for up to sixty rows per page before `_learner_row()`
discards them. The filtering and pagination were genuinely in the database; the
projection was not.

## Round 4 resolution

| Finding | Change |
| --- | --- |
| P2-A | `process()` returns `{"result_kind": "job_lost"}` at each stage boundary whose `advance_stage()` says the job is no longer this worker's — including the one immediately before `record_source_item()`, which is the last point before anything is written to the content tables. The comment now promises what it delivers. |
| P2-B | The revert branch requires `existing.source_native_id == source_native_id`; bytes arriving under a different native id are a plain content duplicate and touch no currency state. |
| P2-C | `list_published()` names the ten columns a card draws. `_learner_row()` was unchanged. |
| (found by a route test) | A path segment that is not an id — `/articles/queue` reaching the article route — is now absence rather than a cast error: `_lookup_uuid()` in both repositories answers `None`, and the routes turn that into 404. |

Also landed alongside, outside the reviewer's scope but required by the
specification: the admin and learner HTTP boundaries
(`writing_coach/reading_admin_api.py`, `writing_coach/reading_articles_api.py`),
34 route tests, and the authorization matrix extended from 36 routes to 50 so
every new endpoint is proved anonymous-401 / learner-403 / admin-reached.

## Authorization boundary (the reviewer's, unchanged)

This review does not authorize schema activation, deployment, or product
approval. `APPROVE` here is an architecture-review verdict on the design and
its implementation, nothing else. The migration remains in
`migrations/proposed/`; it still requires explicit **human schema/runtime
authorization**, then one `git mv` into `migrations/versions/`, then
application to the named sandbox runtime only, followed by the PostgreSQL
constraint proof in §11.4. Production (8000) and preview (8010) retain every
gate in `ARCHITECTURE_INVARIANTS.md § Human gates`. `APPROVED` as a product
state remains the human's alone.
