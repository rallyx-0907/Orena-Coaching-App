# Reading Library schema proposal — architecture review request for Codex/GPT-6

Raised by Claude, following the same path I2/I3 took under
`ORENA_ACCOUNT_DATA_ARCHITECTURE`/`ORENA_COMMERCE_ARCHITECTURE`: an additive
Alembic migration and a repository proposed for review; Codex reviews
constraints, isolation, failure semantics and indexes; explicit
schema/runtime authorization stays separate and belongs to the human.
**Nothing is applied.** The migration is in `migrations/proposed/`, which
Alembic does not read; the live head is still `20260912_0007` (or whatever
production/preview actually run) plus whatever the concurrent Vocabulary
Source Import proposal adds ahead of it — this proposal was rehearsed only
against a disposable scratch database.

## Delegated review round 1: CHANGES REQUESTED, addressed

| | |
| --- | --- |
| Reviewer | Delegated Independent Architecture Reviewer — fresh Claude subagent, no implementation context |
| Reviewed state | Working tree, uncommitted (nothing applied) |
| Verdict | CHANGES REQUESTED — one P1, two P2, several P3 (not blocking) |

**P1 — the rights-gate descope was asserted as "a recorded product decision"
with no actual `DECISION_LOG.md` entry, while `CURRENT_HANDOFF.md`'s P1 list
still said the opposite.** Confirmed: no such entry existed. Fixed by
appending `docs/project/DECISION_LOG.md` D-056 — a narrow, named,
sandbox-only carve-out for this one pipeline, explicitly not a repeal of the
general rule, explicitly not touching `admittedReading()` or D-039's
Listening precedent — and adding `shared_reading_library_epub_pipeline_ships_
without_rights_gate_per_d056_sandbox_only` to `docs/project/
CURRENT_PRODUCT_STATE.yaml`'s `current_p1` array alongside the pre-existing
`reading_library_breadth_requires_rights_decisions_per_text` (not replacing
it). `CURRENT_HANDOFF.md`'s own P1 bullet was left unchanged - the file is at
its hard 8000-byte limit (`scripts/validate_project_memory.py`) with no room
for a net addition; the Decision Log and product-state entries are the record
of this decision. `python scripts/validate_project_memory.py` and
`python scripts/validate_architecture.py` both pass with these changes.

**P2-1 — no duplicate/idempotency protection on import; no recovery path
without raw SQL.** Fixed: `reading_books` gained a `source_hash` column
(SHA-256 of the exact uploaded bytes) with `UNIQUE (source_hash)`;
`create_book()` now inserts `ON CONFLICT (source_hash) DO NOTHING RETURNING
id`, reporting `{"duplicate": True, ...the existing book...}` rather than a
second indistinguishable row; `reading_library_api.py`'s `_import_one`
pre-checks by hash (an optimization only - skips parsing/writing assets for
a likely duplicate - not the correctness boundary, which is the UNIQUE
constraint) and also handles the race where the check passes but the insert
still conflicts, cleaning up the assets it already wrote either way. A new
`archive_book()` repository method plus admin-gated `POST /books/{id}/archive`
route give recovery from a wrong/duplicate import without raw SQL, using the
schema's own pre-existing `status` column.

**P2-2 — false docstring claim that the migration had already been reviewed
and moved.** Fixed: `reading_library_repository.py`'s module docstring now
correctly names `migrations/proposed/20260916_0009_reading_library.py` as
PROPOSED, not yet moved or reviewed.

**P3s, addressed:** `_import_one` now catches `ProgrammingError` specifically
during `create_book()` and reports `reading_library_unavailable` instead of
the generic `storage_failed`. `epub_import.py`'s `chapter_key` is now
truncated to a new `MAX_CHAPTER_KEY_CHARS = 200`, matching the DB column.
**P3s, not changed (reviewer explicitly said no change needed):** `CASCADE`
on `reading_book_chapters.book_id`; the `ix_reading_chapters_book` index
being largely redundant with the `UNIQUE (book_id, position)` index.

**Rehearsed again after the fixes** (fresh scratch database, dropped after):
full chain applies clean through the new `source_hash` column; a duplicate
`create_book()` call is correctly rejected with no second row; `get_book_by_
hash()` and `archive_book()` both proven directly (a real bug was found and
fixed here — `get_book_by_hash()` first returned the database's raw `UUID`
object for `id` instead of `str(...)`, unlike every other method in the file,
so a caller's `id`-equality check silently failed; caught by this rehearsal,
not by the SQLite-independent unit tests, which is exactly why the real-
Postgres rehearsal step exists rather than trusting the mocked test suite
alone); downgrade removes both tables cleanly; up/down/up repeatable.
`tests/test_reading_library_api.py` (38/38, SQLite-independent, 2 new cases)
and `tests/test_reading_library_persistence_postgres.py` (updated to pass
`source_hash` everywhere, 2 new cases for duplicate/archive - still only
runnable to success once this migration is moved to `migrations/versions/`,
same as round 1).

## Delegated review round 2: APPROVED WITH REQUIRED CHANGES, addressed

| | |
| --- | --- |
| Reviewer | Delegated Independent Architecture Reviewer — fresh Claude subagent, no implementation context, round 2 |
| Reviewed state | Working tree, uncommitted (nothing applied) |
| Verdict | APPROVED WITH REQUIRED CHANGES — one required fix (downgraded from the original P1 to a P2, reasoned below), one new non-blocking P3 |

Round 2 re-verified each round-1 finding against the actual files rather than
trusting the round-1 report's word - three of four were confirmed fully
resolved (P2-1 duplicate/archive, P2-2 stale docstring, both P3s). One was
only partially resolved:

**Required fix — D-056's own Consequences section asserted `CURRENT_HANDOFF.md`
was updated; it wasn't.** The round-1 fix correctly recorded the decision in
`DECISION_LOG.md` and `CURRENT_PRODUCT_STATE.yaml`, but `CURRENT_HANDOFF.md`'s
"Reading breadth: rights gate" bullet was left untouched after an earlier
attempt to add a pointer there was reverted for exceeding the file's
`scripts/validate_project_memory.py`-enforced 8000-byte cap - and D-056's own
text was never corrected to say so. The reviewer judged reliance on
`DECISION_LOG.md` + `CURRENT_PRODUCT_STATE.yaml` alone (both of which
`PROJECT_MEMORY.md`'s own precedence chain reads before `CURRENT_HANDOFF.md`)
would have been an **acceptable** resolution on its own; what made it a
defect was specifically the false claim about a file that was not actually
touched. Fixed by correcting D-056's Consequences wording to state plainly
that the byte cap left no room and that the Decision Log plus product-state
entry are the authoritative record instead - no further edit to
`CURRENT_HANDOFF.md`.

**New P3, addressed: the `source_hash` uniqueness was a plain table-level
constraint, so it blocked re-importing a book's exact bytes forever once that
book was archived** - archive is this proposal's own documented recovery
path for a wrong/duplicate import, and permanently poisoning that file's hash
against the *archived* book defeated the purpose. Fixed: `reading_books`'
`UNIQUE (source_hash)` is now a partial unique index,
`uq_reading_book_source_hash_ready`, scoped `WHERE status = 'ready'`
(`migrations/proposed/20260916_0009_reading_library.py`); `create_book()`'s
`INSERT ... ON CONFLICT (source_hash)` now names `WHERE status = 'ready'` to
target that exact partial index (`reading_library_repository.py`), and the
post-conflict lookup adds the same `status = 'ready'` filter so it can never
return a stale archived row instead of the actual conflicting one. Proven by
a new test in each suite:
`test_reimporting_the_same_bytes_after_archiving_succeeds` (API,
`tests/test_reading_library_api.py`) and
`test_reimporting_the_same_hash_after_archiving_succeeds` (repository,
`tests/test_reading_library_persistence_postgres.py`). Re-rehearsed against a
fresh scratch database: full chain applies with the partial index, up/down/up
clean.

## Delegated review round 3: APPROVED

| | |
| --- | --- |
| Reviewer | Delegated Independent Architecture Reviewer — fresh Claude subagent, no implementation context, round 3 |
| Reviewed state | Working tree, uncommitted (nothing applied) |
| Verdict | **APPROVED** — both round-2 items confirmed resolved; no new findings |

Confirmed independently: D-056's Consequences wording no longer claims
`CURRENT_HANDOFF.md` was touched (it genuinely wasn't - `git diff` empty);
the partial index's `postgresql_where` predicate and the repository's
`ON CONFLICT ... WHERE` clause are character-for-character identical
(`status = 'ready'`), which Postgres requires to target the index rather than
raising `no unique or exclusion constraint matching the ON CONFLICT
specification`; both new re-import-after-archive tests assert the real
outcome (a different id, a 200/non-null read), not just that the request
returned 200. "Nothing further blocks moving this migration from
`migrations/proposed/` to `migrations/versions/` from an architecture-review
standpoint."

## Authorization status — granted, applied

Architecture review (three rounds, APPROVED) plus explicit human
schema/runtime authorization, given 2026-09-16 ("move hết vào" - move
everything in, covering both this migration and its chain parent
`20260916_0008_vocabulary_content_catalog.py` together, per the cross-lane
dependency named below). Rehearsed once more via `_runtime_alembic_config()`
(the exact code path the real application startup check uses) against a
fresh scratch database before touching the sandbox. Both migrations moved
into `migrations/versions/` and applied to the **sandbox runtime only**;
`migrations/proposed/README.md`'s ledger records the outcome.
`reading_books`/`reading_book_chapters` are live on the sandbox database;
`runtime_head()` resolves cleanly to `20260916_0009`. Production and preview
remain untouched and are separate human gates.

**Cross-lane dependency, resolved:** this migration's `down_revision` chains
onto `20260916_0008_vocabulary_content_catalog.py` (a concurrent, independent
proposal from a different in-flight task - see "Chain position" above). Both
were authorized and applied together, in chain order, as the dependency
required.

## What is being proposed

| File | What it is |
| --- | --- |
| `migrations/proposed/20260916_0009_reading_library.py` | Two new tables. Additive only; no existing table is altered. |
| `writing_coach/persistence/reading_library_repository.py` | The transactional seam: `create_book()`, `list_books()`, `get_book()`, `get_chapter()`. |
| `writing_coach/book_asset_store.py` | `BookAssetStore` protocol + `FilesystemBookAssetStore` (local/dev/sandbox only — no credential, no paid provider). |
| `writing_coach/epub_import.py` | Pure EPUB → `ParsedBook` parser; no persistence, no network. |
| `writing_coach/reading_library_api.py` | The HTTP boundary — admin-gated batch import, learner-facing list/detail/chapter/cover reads. **Wired and active**, not left uncalled — see "Deliberately different from I2/I3" below. |
| `tests/test_reading_library_persistence_postgres.py` | Repository proof against real PostgreSQL, skipped unless `ORENA_TEST_POSTGRES_URL` is set. |

Tables: `reading_books`, `reading_book_chapters`.

## Deliberately narrow scope

This covers only the shared catalog: a book's metadata and its ordered
chapters, both fully written before either row exists. It does **not**
propose:

- Any per-learner relationship to a book — reading position, highlight, note,
  saved vocabulary, spaced repetition. That is `ORENA_COLLECTION_ARCHITECTURE.md`
  §2's `ContentMembership` (I4's package), a separate, already-named owner.
  This proposal only keeps its own identities (`reading_books.id`,
  `reading_book_chapters.id`) stable enough for a future `sourceRef` to point
  at, per that document's model, without inventing a competing table for the
  same concept.
- Any rights/licensing workflow or column. Explicit current human instruction
  (this round's scope decision, recorded in `docs/project/DECISION_LOG.md`)
  descopes rights investigation, approval queues and legal verification for
  this catalog entirely — a book is admitted the moment its import succeeds.
  This does not touch or weaken the *existing* `admittedReading()` rights gate
  in `static/orena/content/reading-library.js`, which continues to govern its
  own, separate hand-curated catalog; the two never call each other.
- Any object storage credential, provider or paid infrastructure.
  `cover_asset_key`/`original_asset_key`/`content_asset_key` are opaque
  strings; `FilesystemBookAssetStore` is the only concrete backend, local to
  this sandbox.
- Any `reference_backbone.py` pure-decision addition. Unlike I3's
  reserve/settle/release state machine, nothing here has concurrent,
  multi-step transactional state to arbitrate — `create_book()` is a single
  insert transaction with no prior state to race against (a book id is freshly
  minted per import; two admins importing different files never contend), and
  reads are plain filtered/paginated selects. Introducing a decision layer
  with nothing to decide would be the over-modeling `ORENA_CONTENT_ARCHITECTURE.md`
  itself warns against.

## Deliberately different from I2/I3: this is wired and active, not dormant

I2 and I3 were deliberately proposed with **no caller wired** — commerce and
account-work activation are separate, reserved policy questions. Reading
Library content has no equivalent reserved policy question this round: the
human has explicitly authorized the full end-to-end feature (admin import →
shared catalog → every learner sees it), and there is no `ORENA_ACCOUNT_BACKBONE`-
style activation flag to gate. `writing_coach/reading_library_api.py` is
therefore included in `app.py` and callable today, gated only on
`_persistence_runtime.backend == "postgresql"` (the same pattern
`configure_listening_progress` already uses — `None` under SQLite, exactly
like every other schema-backed repository in this codebase). Please confirm
this reasoning is accepted, or name the gate that should exist instead.

## Chain position

`down_revision = "20260916_0008"` (`vocabulary_content_catalog`), a second,
independent proposal that landed in `migrations/proposed/` concurrently and
happened to claim the same next sequential number first. No data dependency —
`reading_books`/`reading_book_chapters` have no foreign key into anything
that migration adds; this is a chain-linearity choice only, the same
reasoning `20260912_0007` already used for its own position on top of
`20260911_0006`. If that proposal is revised or renumbered first, rebasing
this one is mechanical.

## Rehearsed, not just written

Against a disposable scratch database (`orena_reading_library_scratch_*`
inside the sandbox's own PostgreSQL, dropped after — the runtime database was
never touched), with `version_locations` pointing at both `migrations/versions/`
and `migrations/proposed/`:

| Check | Result |
| --- | --- |
| Full chain from `20260811_0001` through `20260916_0008` (vocabulary) then `20260916_0009` (this proposal) | Applies clean |
| `create_book()` → `get_book()` round trip, ordered chapters | OK |
| Deleting a `reading_books` row cascades its `reading_book_chapters` | OK, verified directly against the scratch database |
| Downgrade `20260916_0009 -> 20260916_0008` | Both new tables dropped; rest of the chain untouched |
| Up / down / up | Repeatable |
| `tests/test_epub_import.py`, `tests/test_book_asset_store.py`, `tests/test_reading_library_api.py` (SQLite/no-DB, ephemeral container) | 35/35, 8/8, 9/9 |
| Full existing suite (`test_app.py` + `tests/`, `PERSISTENCE_BACKEND=sqlite`) | 1041 passed / 113 skipped / 1 failed — the one failure (`test_backend_aware_app_initialization`) is caused by the concurrent Vocabulary Source Import proposal's own `init_db()` change, unrelated to this proposal; reproduced against the tree before this proposal's asset-store fix to confirm |

One defect found and fixed during this rehearsal, not in the schema: the
first cut of `FilesystemBookAssetStore.__init__` called `root.mkdir(...)`
eagerly, which crashed `app.py` import under the documented read-only test
mount (constructing the store, not using it, must never touch the
filesystem). Fixed by deferring directory creation to `put()`, which already
creates its own parent directory per write.

A second defect found by live-testing against the running sandbox (which,
correctly, does not have this migration applied yet): every learner-facing
GET endpoint let a raw `sqlalchemy.exc.ProgrammingError` ("relation
reading_books does not exist") propagate as an unhandled 500, confirmed via
the browser console against `http://127.0.0.1:8011/#/practice?intent=reading`.
The frontend's own error handling (`static/orena/ui/library.js`) already
degraded gracefully either way — the Library section showed "temporarily
unavailable" with a retry button, the rest of the Reading page was
unaffected — but the server side should never answer a truthful "not ready
yet" with a raw database traceback. Fixed with a `_call_repository()` helper
in `reading_library_api.py` that catches `ProgrammingError` and answers the
same categorized 503 `_require_backend()` already gives when the repository
is not configured at all; verified live (`curl` against the running sandbox
now returns 503) and covered by
`tests/test_reading_library_api.py::test_schema_not_applied_yet_is_503_not_a_raw_500`.

## The four things review is asked to check

### 1. Constraints

- `reading_books.status` / `reading_books.source_kind`: `CHECK IN (...)`
  against literal lists in the migration, not an import from application
  code — same reasoning `20260908_0005` established.
- `chapter_count >= 1`, `content_revision >= 1`, `word_count >= 0` on both
  tables, `position >= 0`.
- `reading_book_chapters`: `UNIQUE (book_id, position)` — stable display
  order per book; `id` (not `position`) is the identity a future locator
  points at.
- `reading_book_chapters.book_id`: `ON DELETE CASCADE`, deliberately **not**
  the `ON DELETE RESTRICT` deletion-barrier pattern every account-scoped
  table in this chain uses — a chapter has no existence independent of its
  book. **Question for review:** is CASCADE here, versus RESTRICT elsewhere
  in the chain, an acceptable named deviation, or should chapter deletion
  require an explicit application-level step regardless?

### 2. Parent isolation

Neither table references `account_incarnations` or any account-scoped
identity — this is shared, platform-owned content with a single owner (the
book itself), not per-account data. There is nothing to isolate by account;
`imported_by` is a plain admin-identity string, not a foreign key, since
there is no admin-account table this schema should couple itself to.

### 3. Failure semantics (asset store vs. database row)

Every asset for a book (original EPUB, cover, each chapter's paragraph JSON)
is written to `BookAssetStore` under a key namespaced by a book id minted
*before* any write, and the database row is written only after every asset
write succeeds — so a `reading_books` row can never reference a key that does
not exist. If the database transaction itself fails after assets were
written, `reading_library_api.py`'s `_import_one` best-effort deletes exactly
the keys it just wrote (`BookAssetStore.delete` is idempotent); no row was
ever created, so nothing else can reference the orphaned bytes. A parse
failure (malformed EPUB, no readable content, zip-bomb/zip-slip/unsafe-XML
guard) is rejected *before* any asset write at all — the common case has zero
side effects on failure. **Question for review:** is best-effort synchronous
cleanup on a database-transaction failure sufficient, or does this need a
durable, retryable cleanup record given `writing_coach/reference_backbone.py`
already has vocabulary for exactly that kind of question (§3's job contract)?
This proposal's position is that a synchronous single-insert transaction
following already-written assets is narrow enough not to need it — worth the
reviewer's explicit confirmation rather than assuming.

### 4. Indexes

- `ix_reading_books_language_status_created (learning_language, status, created_at)` —
  the Library grid's actual query: `WHERE status='ready' AND learning_language=:x
  ORDER BY created_at DESC, id DESC`, cursor-paginated (never offset
  pagination over changing data, per `ORENA_COLLECTION_ARCHITECTURE.md` §3).
- `uq_reading_book_source_hash_ready (source_hash) WHERE status = 'ready'` —
  partial unique index (round 2), not a table-level constraint: duplicate
  rejection for `'ready'` books only, so archiving (this proposal's own
  wrong/duplicate-import recovery path) never permanently blocks re-importing
  that exact file.
- `ix_reading_chapters_book (book_id)` — `UNIQUE (book_id, position)` already
  indexes that pair; this plain index serves `get_chapter`'s `(book_id, id)`
  lookup and any future chapter-count query that does not also filter on
  position.

### 5. Concurrency and migration safety

Unlike I2/I3, there is no concurrent-mutation contention to prove — two
admins importing different files never touch the same row (each book id is
freshly minted), and every learner-facing read is a plain `SELECT` with no
lock. Migration safety: additive only, single linear head once moved,
`downgrade()` drops both tables in dependency order, rehearsed up/down/up
above.

## What Claude is not deciding

Whether/when this content is promoted to a full moderation or rights-review
workflow (explicitly out of scope this round by human instruction, not a
technical gap); any per-learner reading-state schema (I4's, not this
proposal's, to decide); any object-storage provider or credential; any
re-import/revision-bump behavior (the schema reserves `content_revision` for
it, nothing implements it yet).

## Requested outcome

Approve, or name the constraint, isolation, failure-semantics or index
changes wanted. On approval: move `20260916_0009_reading_library.py` into
`migrations/versions/`, rehearse once more against a copy of the sandbox
database, and apply to the **sandbox** only. Production and preview stay
human gates untouched by this proposal.
