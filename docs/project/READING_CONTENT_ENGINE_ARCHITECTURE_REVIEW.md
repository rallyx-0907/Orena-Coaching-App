# Reading Content Engine — independent architecture review

Status: `CHANGES REQUIRED` for the reviewed commit — seven P1 findings.
Recorded here verbatim; the revision answering it is a separate commit and is
summarised under "Resolution" at the end of this file.

## Review record

- Reviewer role: Delegated Architecture Reviewer (`AGENTS.md`, "Architecture
  review authority"). GPT-6/Codex, the preferred Principal Architect, was not
  available for this round.
- Reviewer identity: independent Claude review session, dispatched read-only
  with no authority to edit, commit or implement.
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

## Resolution

Recorded when the revision answering this review lands; see the commit that
follows this one and the re-review appended below it.
