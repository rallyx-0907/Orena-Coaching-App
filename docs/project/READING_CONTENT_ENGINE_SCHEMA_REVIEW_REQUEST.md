# Reading Content Engine — schema and worker review request

Status: `PROPOSED — awaiting independent architecture review, then human
schema/runtime authorization`.

Proposed migration: `migrations/proposed/20260922_0010_reading_content_engine.py`
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
| `reading_source_items` | the immutable original snapshot + `content_hash` | never overwritten; changed source content creates a new `revision` row pointing at `supersedes_id`, so drift is detectable instead of silent |
| `reading_articles` | the learner-oriented processed version and its lifecycle | edited and published by admins while the snapshot stays untouched; `estimated_level` is never overwritten, `reviewed_level` is separate, `effective_level` is the stored column the learner list filters on |
| `reading_article_targets` | 3–8 learning targets | the admin approves/rejects/reorders them one by one, and `machine_suggested` vs `admin_approved` must both survive a processor re-run |
| `reading_review_events` | the article's own decision history | what the Review Queue renders; `audit_logs` remains the platform audit trail and still receives every mutation |
| `reading_ingestion_jobs` | the durable queue | restart-safe job state; an in-memory registry cannot satisfy "process restart does not lose a job" |

Article lifecycle: `draft → processing → needs_review → ready → published ⇄
unpublished`, plus terminal `rejected` and `archived`. `rejected` retains the
source and hash so the same content cannot be re-proposed as new. Nothing is
hard-deleted in normal workflow.

## 5. Worker architecture (the second gated decision)

**A database-backed queue, no new infrastructure.** No Kafka, RabbitMQ,
Celery or Redis is added; the runtime keeps `orena-web` + `postgres`, with the
worker as a separate execution path that a deployment may run as its own
process (`python -m writing_coach.reading_worker`) or, in the sandbox, inside
the application container. Either way it is never on the learner request path.

- **Claiming** is one atomic statement — `UPDATE … WHERE id = (SELECT … WHERE
  status='queued' AND next_retry_at <= now() ORDER BY created_at, id FOR
  UPDATE SKIP LOCKED LIMIT 1) RETURNING id`. Two workers never take the same
  job, and one poisoned job never blocks the queue behind it.
- **Crash recovery** is a heartbeat: a claimed job whose `heartbeat_at` stops
  advancing is returned to `queued` by the same worker loop after a bounded
  stale interval. A killed process therefore costs one retry, not one lost
  job.
- **Retry** is bounded by `max_attempts` (default 3) with exponential
  `next_retry_at`; exhausted jobs end `failed` with `last_error_code`,
  visible in Admin → Imports, retryable by an explicit admin action.
- **Idempotency** is the `request_hash` unique constraint: a double-submitted
  form returns the first job rather than queueing a second, enforced in the
  database, not by a disabled button.
- **Concurrency** is configurable (`READING_WORKER_CONCURRENCY`, default 1)
  and the abstraction is a small queue port, so a different backend can
  replace the table later without touching the pipeline.

The alternative considered and rejected: running the pipeline inside the admin
HTTP request. It is simpler, and it fails the spec's own requirement (fetch +
extraction + AI inside a request), makes retry impossible after a 502, and puts
parser work on the same event loop as learner traffic.

## 6. Performance invariants this schema is shaped by

Every index maps to one real query; the migration's docstring carries the
table. The load-bearing ones:

- learner list: `WHERE status='published' AND language=? ORDER BY
  published_at DESC, id DESC LIMIT ?` → partial index
  `ix_reading_articles_published`; level and topic filters get their own
  partial compound indexes. Filtering happens in the database, never in Python.
- learner list projection excludes `body`, `original_content`,
  `rights_snapshot_json`, `analysis_json`, targets, review events and job
  state; the body is fetched only by article detail, which carries
  `content_revision` so an ETag can revalidate cheaply.
- admin Review Queue paginates and returns metadata only; the source snapshot
  and processing evidence load on Preview.
- worker claim is served by `ix_reading_jobs_claim` and does not get slower as
  the queue grows.
- corpus growth changes database/worker capacity, never learner request size.

## 7. Deliberately out of scope

No learner-owned table, no reading position/highlight/progress, no account
sync, no auto-publish, no source discovery, no Elasticsearch, no scheduler
turned on, no replacement of the Book Library, no Media rewrite, no video
extractor, no new AI provider or credential path, no change to any learner
route or learner UI file.

## 8. Migration / branch dependency (recorded, not resolved here)

`admin/control-center`'s migration head is `20260916_0009` (`reading_library`).
`codex/work` has since added `20260916_0010`, `0011` and `0012`. This proposal
is therefore numbered by date — `20260922_0010`, revising `20260916_0009` —
and integrating the two lanes will need either one Alembic merge revision or a
mechanical rebase of this revision onto that lane's head. Nothing from
`codex/work` is merged into this lane to "clean it up", and this engine
depends on no code that exists only there.

## 9. Required gate before the schema is applied

1. **Independent architecture review** of the six tables, the immutability and
   revision rule, the dedupe/idempotency constraints, the job-claim and
   crash-recovery design, the delete/cascade behaviour and the PostgreSQL
   indexes. An implementer may not self-approve this.
2. **Human schema/runtime authorization**, then rehearsal against a throwaway
   PostgreSQL database, then one `git mv` into `migrations/versions/` and
   application to the named sandbox runtime only.

Until then the engine ships with its schema inactive: every Reading engine
route answers an explicit `503 reading_engine_schema_unavailable`, exactly as
Vocabulary import does today. Nothing is silently written to platform
settings, static files or an in-memory registry instead.
