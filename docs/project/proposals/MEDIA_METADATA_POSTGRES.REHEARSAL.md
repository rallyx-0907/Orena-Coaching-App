# Media metadata migration 0024: rehearsal record (PARKED per D-109)

**Status: PARKED per D-109** (2026-10-01): "infrastructure hardening ... secondary unless it causes data loss, a security/ownership
problem, failure of a normal learning journey or failure of the content publishing journey." The work below stopped at a
coherent point. Nothing is wired: `app.py` still constructs `FileMediaLibraryStore`, the migration is in `migrations/proposed/`
(not `versions/`), the ORM mirror is on its own inert base. The proposal (`MEDIA_METADATA_POSTGRES.md` rev 2, approved with
conditions) and its conditions stand; the cutover, the human's Q4/Q7 decisions and the `git mv` remain gated.

Throwaway `postgres:17-alpine` on its own Docker network (`media-rehearsal-net`, containers `media-rehearsal-pg-1` and
`media-rehearsal-run-*`, all removed afterwards with their anonymous volume); `scripts/rehearse_media_metadata_schema.py` run in
the application image (`ai-writing-coach:local`) with the repository mounted read-only. The lane (`orena-next-verify-*`, :8021),
:8000, :8010 and every named volume were not touched. Local execution, not CI evidence.

## Runs

| Run | Date | State | Result |
| --- | --- | --- | --- |
| smoke | 2026-10-01 | empty database; runs 1, 5, 5b, 6 and the small import (run 4) | **43 PASS, 0 FAIL** |
| volume | 2026-10-01 | `--volume 100000 --shared 5000 --import-volume 100000` (105,000 rows; 5,000 shared payloads of 4-150 KB; a 130 MiB generated `index.json`) | **58 PASS, 0 FAIL** |

## Done, mapped to proposal section 12

| Proposal run | Status | Evidence |
| --- | --- | --- |
| 1. `0023 -> 0024 -> 0023 -> 0024` | **DONE** (empty, and again at 105,000 rows) | versions-only head is still `0023`; with `migrations/proposed/` the single head is `0024`; the full public schema after the downgrade equals the schema captured at `0023`; the new tables' schema after the second upgrade equals the first; no pre-existing table, column, index or constraint changed |
| 2. `--volume 100000` | **DONE** | tables below |
| 3. `--volume 2000000` (planning volume) | **NOT DONE** (parked) | the driver supports it (`--volume 2000000`); not run |
| 4. import tool | **DONE** small (6 entries, every case) and at 100,000 entries; at 2 M **not applicable**: the legacy file cannot reach 2 M entries, the old store rewrites it whole per write (a 100 k index is already 130 MiB) |
| 5. probes | **DONE** | every CHECK refuses its bad row (13 cases); owner/`source.owner` agreement; negative `stored_bytes`; `lesson_meta`/`has_lesson`; upsert cannot flip `library` or `owner_token` and never moves `created_at`; a NULL-size re-upsert keeps `stored_bytes`; head-only `get` issued 0 payload queries; FK cascade; a lesson without topic/tags comes back unchanged; shared `lesson_id` unique; `set_status` is a status-only UPDATE; keyset paging under concurrent inserts (63 rows, pages of 7: no duplicate, no skip) |
| 5b. planner, locks, JSONB | **DONE** | `ANALYZE` after load; advisory-lock quota race: 8 workers, one owner, limit for 4 -> exactly 4 admitted, 4 refused, sum exact; 8 different owners in parallel all admitted (worst 10 ms); Chinese + emoji title and a 167 KB payload round-trip exactly; **jsonb refuses `\u0000`** (the import aborts such an entry) |
| 6. old-code compatibility | **DONE** | an old-code `users` insert before and after `0024`; the pre-existing schema is byte-identical after `0024` |

## Measurements

**Migration timing** (seconds; one revision per invocation): 0024 upgrade 0.22-0.39 on an empty database; downgrade 0.25-0.49;
re-upgrade 0.19-0.74; **downgrade at 105,000 rows 0.41 s (drops both tables)**, re-upgrade 0.27 s. `0024` creates two tables and
touches no existing one.

**Lock evidence.** A reader hammering `users` and `works` during every 0024 step saw a worst latency of 1.7-3.6 ms (empty) and
**13.2 ms during the downgrade at volume**: no existing table is locked by the revision.

**Size at 105,000 rows** (100,000 personal, 5,000 shared with payloads):

| Item | Bytes |
| --- | --- |
| `media_entries` total (heap + indexes + TOAST) | 130,031,616 (about 1,300 B per personal row all-in; the proposal estimated 1.2 KB) |
| heap | 71,991,296 |
| `media_entry_payloads` total | 105,963,520 (5,000 payloads, 99,045,145 B stored: about 19.8 KB each, 4-150 KB range) |
| `media_entries_pkey` / `ix_media_entries_browse` / `ix_media_entries_library_created` / `ix_media_entries_owner` / `ix_media_entries_lesson_id` | 7.9 MB / 17.9 MB / 16.0 MB / 15.9 MB / 0.35 MB |

At the planning volume (about 2 M personal rows in three years) the linear extrapolation is about 2.6 GB for the entry table and
its indexes [I; run 3 not done].

**Queries at 105,000 rows** (`EXPLAIN (ANALYZE, BUFFERS)` and 200 timed executions; none used a Seq Scan on `media_entries`):

| Query | Plan | p50 / p95 ms |
| --- | --- | --- |
| get by `media_id`, head-only (R1/R2) | Index Scan `media_entries_pkey` | 0.20 / 0.41 |
| get shared + payload | Index Scan pkey + payload pkey | 0.60 / 1.11 |
| shared browse page 1 (en, published, 24) | Index Scan `ix_media_entries_browse` | 0.19 / 0.32 |
| shared browse keyset page | Index Scan `ix_media_entries_browse` | 0.14 / 0.25 |
| operator listing (all statuses) | Index Scan `ix_media_entries_library_created` | 0.13 / 0.22 |
| `lesson_id` probe (R6) | Index Scan `ix_media_entries_lesson_id` | 0.12 / 0.19 |
| owner byte sum, typical owner | **Index Only Scan** `ix_media_entries_owner` | 0.12 / 0.23 |
| owner byte sum, **heavy owner (10,054 rows)** | **Index Only Scan**, **Heap Fetches 0** | 0.68 / 0.81 |
| owner page (24, all languages) | Index Only Scan `ix_media_entries_owner` | 0.13 / 0.21 |
| delete-all: ids of one owner | Index Only Scan `ix_media_entries_owner` | 0.14 / 0.22 |

**Index-only proof for the quota sum.** On a vacuumed table the heavy-owner sum is an Index Only Scan with 0 heap fetches. After an
UPDATE touching the owner's 10,054 rows **without** VACUUM the same plan needed **20,108 heap fetches** (p95 2.05 ms, still
index-driven); after `VACUUM` it returned to **0**. The sum is always index-served; it is heap-free only while the visibility map
is current (autovacuum keeps it so in practice). Walking the heavy owner's 10,054 rows with `list_owned_page(50)` took 0.73 s and
returned every row once.

**Import tool.**

| Case | Result |
| --- | --- |
| dry-run | writes 0 rows; reports counts, the legacy-owner rows, missing assets, upload bytes |
| apply | inserts all, verifies field-for-field and by canonical hash; the legacy personal row is under the explicit legacy token; `stored_bytes` 1,800 measured by `stat` (1,500 + 300); an upload with a missing asset gets NULL |
| second `--apply` | **REFUSED** (table not empty) |
| re-run after a learner deleted an upload | **REFUSED** and nothing resurrected; on an emptied table the single-use marker refuses |
| `--verify-only` | passes on an exact import, writes nothing, **detects a tampered row** |
| hash-mismatched index | aborts, 0 rows written |
| one invalid entry | aborts the whole import, 0 rows |
| a writer touching `index.json` during the run | detected (`index_unchanged` false, `ok` false), no marker |
| **100,000 entries (130 MiB index)** | dry-run 36 s; **apply (insert + verify + ANALYZE) 131 s**; second apply refused; **verify-only 111 s**; exact verification. Generating the file and assets took 65 s (not part of the import) |

## Findings that change the proposal (not yet applied to `MEDIA_METADATA_POSTGRES.md`)

1. **A real `lesson` has keys beyond `lesson_id`, `topic`, `tags`, `payload`.** `_lesson_projection` writes `lesson_id`, `payload`,
   `sections`, `status`, `curation`, `language` and the admin overrides add `topic`/`tags` only sometimes. Rev 2's "assert no
   other keys" would have aborted every YouTube entry. Implemented instead: a `lesson_meta JSONB` column holding the lesson
   **without** its payload, verbatim, with `lesson_id`/`topic`/`tags` derived from it for queries, `CHECK ((lesson_meta IS NOT
   NULL) = has_lesson)`, and a round-trip test that proves a lesson with no topic/tags comes back unchanged. Rev 3 of the
   proposal should replace section 3.2's extracted-column description and section 5 step 3's key-set validation accordingly.
2. **`get` is head-only by default** (`with_payload=False`), as rev 2 says; the cutover must pass `with_payload=True` at the call
   sites that read the transcript (`resolve_learner_payload`, the admin `media_record`/receipt), or a lesson will silently have
   no payload. A head-only entry's `lesson` has no `payload` key.
3. **jsonb cannot store `\u0000`**; the import should abort an entry containing it (not yet added to `load_index`).
4. **`BookAssetStore` has no size lookup**; the import script stats the file itself (same key validation). The cutover should add
   a `size(key)` method.
5. The earlier estimate of 1.2 KB per entry was close: **1,300 B** all-in.
6. In the limits proposal's terms, the import of a 100 k-entry file is minutes, not seconds: the maintenance window is dominated
   by `verify` (reads every row back), which could be made optional/sampled for a large file.

## What is built (all uncommitted at the time of writing)

| File | What |
| --- | --- |
| `migrations/proposed/20261001_0024_media_entries.py` | the revision (two tables, CHECKs, four indexes; PostgreSQL-only CHECKs conditional) |
| `writing_coach/persistence/media_models.py` | the ORM mirror on its **own** `MediaBase` (inert: not on `models.Base`, so no `create_all` or parity test elsewhere sees it) |
| `writing_coach/persistence/media_library_repository.py` | `PostgresMediaLibraryRepository` (not wired) |
| `scripts/import_media_index.py` | the one-time import (dry-run default, refuse unless empty, single-use marker, `--verify-only`) |
| `scripts/rehearse_media_metadata_schema.py` | the rehearsal driver |
| `tests/test_media_metadata_postgres.py` | hermetic tests (8 pass without PostgreSQL; the 7 PostgreSQL tests skip) and PostgreSQL tests that **skip cleanly** without `ORENA_TEST_POSTGRES_URL` |

`writing_coach/persistence/models.py` was restored to HEAD (the first mirror lived there; it would have made the SQLite
`create_all` build tables with no migration in `versions/`).

## Not done (parked)

- Run 3 (`--volume 2000000`).
- The PostgreSQL half of `tests/test_media_metadata_postgres.py` (the ORM-vs-migrated-schema parity test, repository and import
  tests) has **never been executed against PostgreSQL**; the driver covers the same behaviours and passed, but the pytest versions
  are unverified. Run with `ORENA_TEST_POSTGRES_URL` set to a throwaway database before relying on them.
- Head-sensitive test updates (they apply only when the migration moves to `versions/`).
- Not wired: `app.py`, the Listening/admin/file-route call sites, the quota rail, deletion-enumeration category, `size(key)` on the
  asset store, the proposal's rev 3 corrections above.
- The human's decisions: Q4 (legacy-owner rows; the rehearsal used the **explicit legacy token**, pending the human), Q7 (window
  and archive retention), and the gate to move the migration to `versions/` and apply it.

To resume: start a throwaway `postgres:17-alpine` (name containing `rehears`), run the driver in the application image as in its
docstring, then run the module's PostgreSQL tests; record run 3 here and apply the findings to the proposal as rev 3.
