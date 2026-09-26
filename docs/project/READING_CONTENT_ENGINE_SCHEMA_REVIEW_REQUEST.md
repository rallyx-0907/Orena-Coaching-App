# Reading Content Engine — schema and worker review request

**Integration note (2026-09-26):** This request and its verdicts describe the
Admin-lane revision. The integrated `20260924_0015` has a new parent and needs
independent delta review before any shared-runtime apply. Historical revision
references below remain as reviewed.

Status: **`INDEPENDENT ARCHITECTURE REVIEW: APPROVED` — awaiting human
schema/runtime authorization.**

Four rounds: `CHANGES REQUIRED` (seven P1, `5eeaac7`) → `REQUEST CHANGES` (two
new P1, `e375ad3`) → `REQUEST CHANGES` (one P1 in the worker implementation,
`a785216`) → **`APPROVE`** (`e09c6ce`, three non-blocking P2s, all since
resolved). Every round and its resolution is recorded in
`docs/project/READING_CONTENT_ENGINE_ARCHITECTURE_REVIEW.md`; §10 below maps
the round-1 findings to the code.

The approval is an architecture-review verdict on the design and its
implementation. It does not authorize schema activation, deployment or product
approval — §11 below is what remains, and step 3 belongs to the human.

Proposed migration: `migrations/proposed/20260923_0013_reading_content_engine.py`
(additive; six new tables; no existing table altered). Alembic does not read
that directory, so committing it applies nothing.

This request exists because the Admin Reading Content Engine cannot be built
without persistence and without a durable job queue, and `AGENTS.md`
("Architecture review authority") reserves both: schema/migration changes
require independent architecture review recorded in Git, and
`ARCHITECTURE_INVARIANTS.md` § Human gates stops unapproved schema or Alembic
work. The specification this implements says the same thing in its own words:
*"when repo governance mandates human approval for migration/worker
architecture, stop at that specific gate with a concrete proposal, not a
generic question."* This is that concrete proposal.

---

## 1. What the engine is

One pipeline that turns an admin-supplied text — pasted, fetched from a URL,
or uploaded as a file today; polled from an RSS/API source later — into a
reviewed, published Reading article every learner can read. Manual and
automated inputs share one adapter boundary, one normalization pipeline, one
review lifecycle and one publication contract, so adding recurring sources
later adds an adapter, not a second engine.

**No learner-facing UI changes.** The learner sees more published articles and
nothing else: no new learner screen, no new learner navigation, no redesign.
Admin work stays inside the existing control center (`#/admin`), under
Content → Reading, with the existing Imports and Operations sections extended.

## 2. Phase A audit — what already exists and is reused

Read on `admin/control-center` at `82d7077`:

| Existing | Verdict |
| --- | --- |
| `writing_coach/admin_console_api.py` (14 routes), `_same_origin()`, audit-on-mutation, upload dedup | Reused as-is; the new routes join this router's conventions. |
| `writing_coach/admin_content.py` | Reused: the "list projection without payload" principle this engine's list endpoints must follow. |
| `writing_coach/persistence/admin_repository.py` | Reused; portable SQLAlchemy so the hermetic SQLite suite runs the same SQL. |
| `audit_logs` + `AuditLog` model | Reused for every privileged mutation. No second audit system. |
| `writing_coach/ai/platform.py` control plane | Reused for the optional AI stage; no new provider, no new key path. |
| `writing_coach/media_safe_fetch.py` (SSRF guard, peer-address check, redirect policy) | Reused verbatim for URL ingestion — this is why URL fetch needs no new network code. |
| `writing_coach/epub_import.py` limits, `read_source_upload` bounds | Reused as the model for file-input limits. |
| `reading_books` / `reading_book_chapters` + `BookAssetStore` | **Not** reused for articles — see §3. Untouched by this migration. |
| `writing_coach/media_fallback.py` in-memory job registry | **Not** reused: it loses every job on restart, which is exactly what §13 of the spec forbids. |
| `tests/test_admin_authorization_matrix.py` (36 routes) | Extended, not replaced: every new endpoint joins the existing matrix. |

## 3. Why the existing catalogs are not enough

`reading_books` models a whole work: one EPUB, many chapters, admitted the
moment the import succeeds, with no review state and no per-item rights. An
engine article is a different object with a different lifecycle — one short
text, an immutable source snapshot behind it, a machine level estimate an
admin may override, 3–8 learning targets an admin approves individually, and
a review queue that can reject a candidate permanently. Forcing that into
`reading_books` would mean adding a review lifecycle, a rights snapshot, a
targets child table and a job queue to a table whose reviewed design
deliberately states it "never represents a processing or failed import" — a
larger and riskier change than adding a separate, additive catalog beside it.
Both catalogs then publish through their own learner-facing reads and share no
foreign key.

Platform settings are not a content store, and the static listening/reading
catalogs in code cannot retain an admin submission or serve content
independently of a deployed release — the same argument
`VOCABULARY_SOURCE_SCHEMA_REVIEW_REQUEST.md` already made.

## 4. The six proposed tables

All shared, platform-owned content. No learner-owned column, no account
foreign key, no per-learner state anywhere in this proposal.

| Table | Holds | Why separate |
| --- | --- | --- |
| `reading_sources` | where content comes from: type, rights answers, approval state, polling state | mutable registry; polling can only be enabled for an approved source with `automation_allowed` (a CHECK constraint, not just application code) |
| `reading_source_items` | the immutable original snapshot + `content_hash` | never rewritten; a changed source inserts a new row that points back with `supersedes_id` while the old row is stamped `superseded_at`, so drift is detectable instead of silent |
| `reading_articles` | the learner-oriented processed version and its lifecycle | edited and published by admins while the snapshot stays untouched; `estimated_level` is never overwritten, `reviewed_level` is separate, `effective_level` is the stored column the learner list filters on |
| `reading_article_targets` | 3–8 learning targets | the admin approves/rejects/reorders them one by one, and `machine_suggested` vs `admin_approved` must both survive a processor re-run |
| `reading_review_events` | the article's own decision history | see below |
| `reading_ingestion_jobs` | the durable queue | restart-safe job state; an in-memory registry cannot satisfy "process restart does not lose a job" |

**Why review events are not folded into `audit_logs`** (the reviewer's
argument, which is stronger than the one this document made first):
`audit_logs` is indexed only on `created_at`, so rendering one article's
history from it would be a full scan, and indexing a shared platform table
would destroy this migration's purely-additive property. `audit_logs.user_id`
is also a foreign key into `users`, so reusing it for a product surface would
couple the engine to the very account table `AGENTS.md` §7 reserves.
`audit_logs` remains the platform audit trail, still receives every mutation,
and is therefore the *retention authority* — which is what makes it acceptable
for `reading_review_events` to cascade with its article.

**Immutability is enforced, not asserted.** On PostgreSQL a `BEFORE UPDATE`
trigger rejects any change to the snapshot's content (`original_content`,
`content_hash`), its provenance (`source_id`, `source_native_id`,
`canonical_url`, `fetched_at`, `revision`, `supersedes_id`) and its rights
evidence (`rights_snapshot_json`) — a mutable rights snapshot is not a
snapshot, and the two identity columns are what the partial dedupe index is
built on. `superseded_at` is the one column left writable, because marking a
snapshot superseded is the one legitimate update; the descriptive columns an
admin may correct after a mis-parse (`original_title`, `original_author`,
`original_published_at`, `original_language`, `metadata_json`) stay writable
deliberately. On any other dialect the same rule is a repository invariant with
a test proving no `UPDATE` is issued against those columns.

**A source that reverts to earlier bytes** does not create a third snapshot:
those bytes already have a row, so the engine clears `superseded_at` on it and
stamps the row that had been current, in one transaction. `revision` is
therefore a creation-order counter, not a currency rank —
`superseded_at IS NULL` is the only test for "current", everywhere. Supersede
order is forced and must be one transaction: stamp the old row, then insert the
new one; the reverse collides on the partial index, which is also what
serializes two workers racing to supersede the same item.

Article lifecycle: `draft → processing → needs_review → ready → published ⇄
unpublished`, plus terminal `rejected` and `archived`. `rejected` retains the
source and hash so the same content cannot be re-proposed as new. Nothing is
hard-deleted in normal workflow; a purge is an explicit admin action that must
write its audit row *before* the delete, because review events cascade with the
article.

## 5. Worker architecture (the second gated decision)

**A database-backed queue, no new infrastructure.** No Kafka, RabbitMQ,
Celery or Redis is added; the runtime keeps `orena-web` + `postgres`, with the
worker as a separate execution path that a deployment may run as its own
process (`python -m writing_coach.reading_worker`) or, in the sandbox, inside
the application container. Either way it is never on the learner request path.

**Claiming** is one atomic statement, never read-then-write. The outer `WHERE`
repeats the status so correctness does not rest on the subquery alone:

```sql
UPDATE reading_ingestion_jobs
   SET status       = 'running',
       stage        = 'fetching',
       attempt      = attempt + 1,
       claimed_by   = :worker_id,
       started_at   = now(),
       heartbeat_at = now()
 WHERE status = 'queued'
   AND id = (SELECT id FROM reading_ingestion_jobs
              WHERE status = 'queued' AND next_retry_at <= now()
                AND attempt < max_attempts
              ORDER BY created_at, id
              FOR UPDATE SKIP LOCKED LIMIT 1)
RETURNING id
```

`attempt < max_attempts` belongs in the claim's own predicate, not only in
the retry path: the claim is what increments `attempt`, so without it a job on
its last allowed attempt would be claimed once more and violate
`ck_reading_job_attempt_bound` instead of failing cleanly.

Two workers never take the same job — under READ COMMITTED the locking
subquery re-evaluates its predicate after taking the lock — and `SKIP LOCKED`
stops one poisoned job blocking the queue behind it.

**Crash recovery** is a heartbeat the claim itself sets. `heartbeat_at` is
`NOT NULL`, so a job cannot exist in `running` without one and the reaper
cannot miss a stranded row to a NULL. The reaper consumes an attempt, so a job
that reliably kills its worker fails rather than cycling forever:

```sql
UPDATE reading_ingestion_jobs
   SET status          = CASE WHEN attempt >= max_attempts THEN 'failed' ELSE 'queued' END,
       stage           = CASE WHEN attempt >= max_attempts THEN 'done' ELSE 'queued' END,
       claimed_by      = '',
       last_error_code = 'worker_lost',
       next_retry_at   = now(),
       finished_at     = CASE WHEN attempt >= max_attempts THEN now() ELSE NULL END
 WHERE status = 'running' AND heartbeat_at < now() - :stale_after
```

- **Retry** is bounded by `max_attempts` (default 3, and
  `CHECK (attempt <= max_attempts)`) with exponential `next_retry_at`;
  exhausted jobs end `failed` with `last_error_code`, visible in Admin →
  Imports. Admin **Retry inserts a new job row**; the failed attempt keeps its
  error and its history rather than being mutated.
- **Idempotency** is `request_hash`, unique over **live** submissions only
  (`WHERE status IN ('queued','running')`). It is SHA-256 over the canonical
  submission: **source id**, kind, canonical URL, text fingerprint, file digest
  and declared language. A double-submitted form returns the first job; a text
  whose earlier job failed can be submitted again; and the same text offered to
  two sources — which have different rights answers — is two submissions, not
  one that locks the other out.
- **Concurrency** is configurable (`READING_WORKER_CONCURRENCY`, default 1)
  and the abstraction is a small queue port, so a different backend can
  replace the table later without touching the pipeline.
- **Known, bounded property:** `ORDER BY created_at, id` means a retried job is
  claimed ahead of newer work once its backoff expires. Harmless at
  concurrency 1 and bounded by `max_attempts`; recorded for whenever
  concurrency rises.

The alternative considered and rejected: running the pipeline inside the admin
HTTP request. It is simpler, and it fails the spec's own requirement (fetch +
extraction + AI inside a request), makes retry impossible after a 502, and puts
parser work on the same event loop as learner traffic.

## 6. Performance invariants this schema is shaped by

Every index maps to one real query; the migration's docstring carries the full
table, and every index it creates appears there exactly once. The load-bearing
ones:

- learner list: `WHERE status='published' AND language=? ORDER BY
  published_at DESC, id DESC LIMIT ?` → partial index
  `ix_reading_articles_published (language, published_at, id)`; level and topic
  filters get their own partial compound indexes, each ending in `id` so the
  keyset tiebreak is an index bound rather than a filter. Filtering happens in
  the database, never in Python.
- learner list projection excludes `body`, `original_content`,
  `rights_snapshot_json`, `analysis_json`, targets, review events and job
  state; the body is fetched only by article detail, which carries
  `content_revision` so an ETag can revalidate cheaply.
- admin Review Queue paginates and returns metadata only; the source snapshot
  and processing evidence load on Preview. Its index bounds the scan; a
  multi-value `IN` on `status` still sorts, which is acceptable for an admin
  surface off the hot path.
- worker claim is served by a partial index on the queued set ordered
  `(created_at, id)`, so it walks in claim order and stops at the first due
  row. `next_retry_at` is a filter there, never an index bound — a range
  predicate before the sort column would destroy the ordering the claim needs.
- **Duplicate content across sources is possible by design**: the hash key is
  `(source_id, content_hash)`, because rights differ per source. A non-unique
  index on `content_hash` alone exists so the review UI can tell an admin
  "this text already exists as article X" before they publish a second copy.
- corpus growth changes database/worker capacity, never learner request size.

## 7. The three built-in sources are seeded by the migration

Manual paste, direct URL and file upload are not registry entries an admin
creates — they are how manual ingestion reaches the same pipeline as a feed.
The migration seeds exactly three rows with fixed UUIDs, `state = 'active'`,
`automation_allowed = false` and polling off. Fixed ids are load-bearing:
`uq_reading_source_items_hash` is `(source_id, content_hash)`, so manual dedupe
works only because every manual paste shares one source id. An external
recurring source is still created by an admin and still starts at
`needs_review`.

## 8. Deliberately out of scope

No learner-owned table, no reading position/highlight/progress, no account
sync, no auto-publish, no source discovery, no Elasticsearch, no scheduler
turned on, no replacement of the Book Library, no Media rewrite, no video
extractor, no new AI provider or credential path, no change to any learner
route or learner UI file.

## 9. Migration / branch position (resolved)

`codex/work` was merged into `admin/control-center` on 2026-09-23 (merge
commit `61e9668`), which brought `20260921_0010` (listening hint state),
`20260922_0011` (essay review kept) and `20260922_0012` (text discussions).
This proposal was **rebased onto that head rather than merged into it**: it is
now `20260923_0013`, revising `20260922_0012`, so `migrations/versions/` keeps
one linear chain and no Alembic merge revision is needed. One `git mv` still
applies it.

The rebase is chain linearity only. The engine has no foreign key into, and no
dependency on, anything those three migrations added; the rehearsal in §11.1
was re-run against this chain to prove it, not assumed.

**Until the `git mv`, `alembic revision --autogenerate` on this lane will
propose creating all six tables again.** `migrations/env.py` compares the
database against `Base.metadata`, and the six models are in it while the
revision that creates them is not in `versions/`. That is expected, not a
defect to fix by deleting the models; anyone autogenerating a revision here
must discard those six `create_table` calls. The state ends the moment the
migration moves.

Two more consequences of the models existing, stated so nobody assumes
otherwise: `Base.metadata.create_all()` creates the six tables in a SQLite
fixture but creates **neither the trigger nor the seed rows**, so a hermetic
test seeds its own source through
`ReadingContentRepository.ensure_built_in_sources()`; and the partial indexes
are declared for both dialects in `models.py` and for PostgreSQL in the
migration, which §11.4's proof is what keeps honest.

## 10. What changed in response to the independent review

| Finding | Change |
| --- | --- |
| P1-1 revision rule unexecutable | `superseded_at` column added; `uq_reading_source_items_native` is now partial on `source_native_id <> '' AND superseded_at IS NULL`. A re-fetch resolves to the row with `superseded_at IS NULL`. |
| P1-2 immutability unenforced | PostgreSQL `BEFORE UPDATE` trigger rejecting changes to `source_id`, `original_content`, `content_hash`, `fetched_at`, `revision`; repository invariant + test elsewhere. |
| P1-3 targets capped at one blank form | `uq_reading_target_form` is now partial on `canonical_form <> ''`. |
| P1-4 stranded job on a NULL heartbeat | `heartbeat_at` is `NOT NULL` with a default and is set by the claim itself, so there is no NULL to miss; claim and reaper statements written out in full above; outer `WHERE status = 'queued'` added. |
| P1-5 claim index order | Replaced with a partial index on `(created_at, id) WHERE status = 'queued'`, plus `ix_reading_jobs_stale` for the reaper. Docstring table corrected. |
| P1-6 permanent request hash | Unique only over `status IN ('queued','running')`; the hash now includes `source_id`; admin Retry inserts a new row. |
| P1-7 no source row to point at | Three built-in sources seeded in the migration with fixed UUIDs and `state = 'active'`. |
| P2-1 CI exercises no constraint | Committed below: a PostgreSQL proof under `ORENA_TEST_POSTGRES_URL` asserting each named constraint rejects its violation; any SQLite fixture table must mirror this DDL. |
| P2-2 `effective_level` drift | `CHECK (effective_level = COALESCE(reviewed_level, estimated_level))` and `CHECK (reviewed_level IS NULL OR reviewed_level <> '')`. |
| P2-3 redundant index | `ix_reading_articles_source_item` removed; the unique constraint's btree serves that lookup. |
| P2-4 undocumented index | `ix_reading_sources_state` now named in the rationale table with its query. |
| P2-5 overstated index claims | `id` added to the three published indexes; the Review Queue claim softened to "bounds the scan, does not remove the sort". |
| P2-6 cross-source duplicates | Claim softened to per-source, and `ix_reading_source_items_hash_any` added so review can surface an existing copy. |
| P2-7 delete asymmetry | `supersedes_id` changed `SET NULL` → `RESTRICT`; `audit_logs` named as the retention authority; a purge must write its audit row before the delete. |
| P2-8 case-variant hash | `CHECK (content_hash = lower(content_hash))` added. |
| P2-9 constraint/DDL notes | Predicate rewritten as `NOT polling_enabled OR (...)`; the pause consequence named; `next_retry_at` given a `now()` default; the JSON NOT-NULL-without-default choice stated as deliberate. |
| P2-10 reaper must consume an attempt | Reaper statement increments nothing implicitly — the claim already incremented `attempt` — and fails the job at `attempt >= max_attempts`; `CHECK (attempt <= max_attempts)` added. |
| P2-11 retry preempts new work | Recorded as a known bounded property in §5. |
| Rollback note | `downgrade()` documented as a development-time reversal that must never run against a runtime with published articles. |

## 11. Required gate before the schema is applied

The order matters, and round 2 corrected it: nobody should be asked to
authorize DDL that has never been executed.

1. **Rehearsal against a throwaway PostgreSQL — done.** Executed 2026-09-22 on
   a disposable PostgreSQL 16 container (tmpfs, no named volume, removed
   afterwards; no shared runtime touched): `upgrade head` → `downgrade
   20260916_0009` → `upgrade head`, clean in both directions, six engine tables
   created and dropped, the immutability function and trigger created and
   dropped, three seed rows landing with their fixed ids at `state=active
   automation=False polling=False`. Proven in the same run: the trigger refuses
   a rewrite of `original_content`, `content_hash`, `rights_snapshot_json`,
   `source_native_id` and `canonical_url` (SQLSTATE 23514 each), permits the
   `superseded_at` stamp and a descriptive title correction, the polling CHECK
   refuses `polling_enabled` without `automation_allowed`, and the partial
   native-id index refuses two current rows for one native id. `alembic upgrade
   --sql` also renders offline: 6 tables, 3 seed inserts, the function, the
   trigger and 10 partial indexes.

   The rehearsal earned its place: it caught a defect no reading would have
   found — `IS DISTINCT FROM` on a `json` column raises `operator does not
   exist: json = json`, so the trigger would have rejected *every* update to
   `reading_source_items`, including the one legitimate one. Fixed with
   `CAST(... AS text)` and re-proven.

   This is local execution evidence, not a CI claim.
2. **Independent architecture review — done, `APPROVE`** for commit
   `e09c6ce`, covering the six tables, the supersede and revert rules and their
   trigger, the dedupe and idempotency constraints, the claim/reaper design and
   its implementation, the delete behaviour and the indexes. The implementer
   did not approve it; `AGENTS.md` forbids that.
3. **Human schema/runtime authorization**, then one `git mv` into
   `migrations/versions/` and application to the named sandbox runtime only.
4. **PostgreSQL constraint proof** (`tests/test_reading_engine_persistence_postgres.py`,
   skipped unless `ORENA_TEST_POSTGRES_URL` is set), asserting that each of
   `ck_reading_source_polling_requires_approval`,
   `ck_reading_article_published_at`, `ck_reading_article_effective_level`,
   `ck_reading_target_decision`, `ck_reading_job_attempt_bound`,
   `uq_reading_source_items_native`, `uq_reading_source_items_hash`,
   `uq_reading_article_source_item` and `uq_reading_job_request_hash` rejects
   its violation, and that the immutability trigger refuses a snapshot
   rewrite. It must also assert that each partial index carries its predicate
   on the applied schema (`pg_indexes.indexdef`): the same indexes are declared
   twice — in the migration for the runtime and in `models.py` for the hermetic
   suite — and this is the only place that can catch the two drifting apart.
   CI runs on SQLite and exercises none of these, which is exactly why the
   proof is named here rather than assumed.

Until then the engine ships with its schema inactive: every Reading engine
route answers an explicit `503 reading_engine_schema_unavailable`, exactly as
Vocabulary import does today. Nothing is silently written to platform
settings, static files or an in-memory registry instead.

## 12. Review-edit features deliberately deferred

What an administrator can do to a candidate today: correct its level, its
topic, its title, its excerpt and its body; approve or reject each suggested
learning target; add a target of their own; publish, unpublish, reject with a
reason, or archive it; and read the whole decision history. Everything below
is deliberately not built yet, with the reason, because "not there" and "not
wanted" are different states and an operator should not have to guess which.

**Server contract exists, console does not expose it.** These are one form
away and were left out to keep the first review surface small:

| Deferred | Where it already works |
| --- | --- |
| Editing the article body in the console | `POST /api/admin/reading/articles/{id}` accepts `body`; the review form offers level, topic and reason only |
| Editing the excerpt and subtopic | same route accepts both |
| Adding a learning target from the UI | `POST …/targets` exists and is tested; nothing in the section calls it |
| Editing a source's rights or languages after creation | only `state` and `polling_enabled` are exposed; the rest is a create-time answer |

**Correcting a mis-parsed byline or publication date.** The immutability
trigger deliberately leaves `original_title`, `original_author`,
`original_published_at`, `original_language` and `metadata_json` writable, so
an admin *could* be given a form for a mis-parse — and no repository method
writes them today, which is why there is no such form yet. One rule comes with
it when it ships, recorded here so it is not rediscovered through a stale
byline on a learner's screen: `attribution.author` and
`attribution.published_at` are in the learner's detail read, so correcting
either must bump the owning article's `content_revision`
(`article_for_source_item()` reaches it). `LEARNER_VISIBLE_FIELDS` covers only
`reading_articles` columns and cannot see this on its own.

**Not built, and waiting on a later phase.**

- *Target meanings and reordering.* `meaning` and `rank` are columns the
  processor fills with a rank and an empty gloss. Writing a good gloss is an
  AI task (Phase H), and reordering only matters once there is something worth
  reordering.
- *Adaptation.* `is_adapted` and `adaptation_json` exist and nothing writes
  them: adapting a text to a level is the optional, source-grounded AI step in
  Phase H, and an adapted text must carry its provenance, which is why the
  columns are there and the feature is not.
- *Comprehension questions.* Out of scope for this round by the
  specification's own ordering; no column claims otherwise.
- *Re-running the processor on an existing article.* A snapshot is immutable
  and an article already carries its analysis, so a re-run is only useful once
  the AI stage exists to produce something different.
- *Recurring source polling.* The registry, the rights gate and the CHECK
  constraint that stops an unapproved source from polling are all in place;
  the poller itself is Phase I.

**Not built, and deliberately not planned.**

- *Bulk publish.* Publishing is one admin's decision about one text, recorded
  with their name on it. A "publish all" button is how a review queue becomes
  a formality.
- *Hard delete.* Rejection and archiving keep the row, the reason and the
  hash — which is what stops a rejected text being re-proposed as new. A purge
  remains an explicit, audited admin action with no button.
- *Search across the corpus.* The lists filter by status, language, level and
  topic in the database. Free-text search has to be server-side, paginated and
  indexed (§46.11); adding an application-layer scan now would be the
  performance mistake this engine's design exists to avoid.
