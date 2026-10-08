# Independent architecture review: MEDIA_METADATA_POSTGRES (PROPOSED rev 1)

- **Reviewer:** Claude Opus 5.5, independent reviewer subagent, not the author (Delegated Architecture Reviewer,
  AGENTS §1; schema and migration decisions require independent review).
- **Reviewed:** `docs/project/proposals/MEDIA_METADATA_POSTGRES.md` at commit `205377c`, against D-108.5
  (`DECISION_LOG.md`), `ARCHITECTURE_INVARIANTS.md`, and the code it cites (`media_library_store.py`,
  `media_library_api.py`, `listening_api.py`, `account_records_api.py`, `deletion_enumeration.py`).
- **Date:** 2026-10-01. Read-only and static; no Docker or PostgreSQL. Nothing was run.

## Verdict: APPROVE WITH CONDITIONS

The design is right and conservative: two additive tables, no change to any existing table, asset bytes stay where they
are, a repository with the existing surface, an operator-run import (not startup, not Alembic), no dual write, no reverse
sync, no read of `index.json` after cutover. It honours every invariant. I found no P0 or P1. Five P2s need text changes
before the code is written (they are about the quota index, the import being re-runnable, rollback wording, backend
selection and the archive's retention); the P3s are hardening.

| Severity | Count |
| --- | --- |
| P0 | 0 |
| P1 | 0 |
| P2 | 5 |
| P3 | 9 |

## Invariants

- **No dual-write.** One authority at a time: before step 5 of the cutover the old code runs on the file and the new tables
  are empty and unread; after it the new code runs and the file is an archive. The import script is the only other writer
  and runs in the window. Correct.
- **No reverse sync.** A reverse export to `index.json` is explicitly not proposed. Correct.
- **No silent fallback.** The repository never opens the file; on a database error it raises `MediaStoreUnavailable`.
  Qualification: selection between the PostgreSQL repository and the file store for the hermetic test backend must be
  by `PERSISTENCE_BACKEND` only, never by failure (P2-4).
- **No startup import / no startup Alembic.** The import is `scripts/import_media_index.py` under a human gate and the
  revision is applied by `bootstrap_runtime_schema.py`. Correct, and the "no startup import" test (empty table, populated
  archive, nothing imported) is the right proof.
- **Protected contracts.** The M1 transcript/segment contract is not remodelled (payload kept whole as JSONB). Correct.

## Schema (0024)

Sound: `media_id` PK with the code's pattern as a CHECK; CHECKs for library, status, media type, thumbnail kind/ref
agreement, `duration_ms >= 0`, `playback` object, `tags` array; the `owner_token` CHECKs
(`library = 'shared' OR owner_token IS NOT NULL`; `source->>'owner'` agrees with the column when present); `language`
deliberately unchecked (a registry, as for `works`); the payload in a 1:1 side table with `ON DELETE CASCADE`; no FK to
`users`, with the right reason (`owner_token` is a digest of the account key and neither `users.id` nor the key is
derivable from it).

Required tightening (P3-1): add the converse CHECK so a shared row cannot carry an owner token
(`(library = 'personal') = (owner_token IS NOT NULL)`), bound every VARCHAR the import can overflow
(`topic` 64, `level` 16, `language` 20, `provider*` 256) by **validating lengths in the import before any write**, and
assert in the import that `lesson` has no keys beyond `lesson_id`, `topic`, `tags`, `payload` (anything else would be lost
by the reconstruct). `created_at` must be immutable on conflict (set on insert only), or a re-import by an admin moves a
row and breaks keyset paging (P3-2). `version` has no consumer (Q5).

## Indexes against queries

- Point reads R1-R3, R7, R10-R14: PK. R2 (once per image request) is a PK probe. **`get` must not join the payload**
  unless asked (R2 needs only visibility; otherwise each image request detoasts up to 150 KB): give the repository a
  head-only read (P3-3).
- Shared browse R4/R5: `ix_media_entries_browse (library, language, status, created_at DESC, media_id DESC)` serves
  library = shared, language = L, status = published with keyset order. Level/topic/tag filtered over the range is
  acceptable at thousands of rows. The operator listing with a language but **no** status cannot use that index's order
  (status sits between language and created_at); it falls back to `ix_media_entries_library_created` with a filter, which is
  fine at admin scale, but say so.
- Operator listings R8/R9: `ix_media_entries_library_created`. Good.
- R6 by `lesson_id`: partial index. See Q1.
- Owner index `(owner_token, language, created_at DESC, media_id DESC) INCLUDE (stored_bytes) WHERE library = 'personal'`
  serves the per-language listing and the sum. **The proposal's index-only sum is not index-only as written** (P2-1).
- R15 `delete_all_owned_media` walks "every language" by `list_owned_page(owner_token)` keyset on
  `(created_at, media_id)`, but the index orders by `language` first: either page by `(language, created_at, media_id)` or
  by `media_id`, otherwise the cursor does not match the index order (P3-4).

## Quota sum and advisory lock (D-108.7)

The shape is correct: size measured server-side at upload (`stored_bytes`), never from the client; one transaction takes
`pg_advisory_xact_lock(hashtextextended(owner_token, 0))`, sums, compares, inserts; refusals roll back and the importer deletes
the files it just stored; different accounts do not contend; removal-pending bytes stay counted because the row is deleted
last. Two remarks. (a) The lock is separate from the account stream lock; there is no ordering problem because the media
transaction does not touch `works`, and the later account-record commit is a different transaction. The cost is that an
upload which passes the byte rail can still fail the count rail and then needs the compensating delete: specify that
compensation (entry, then files) as a single retried routine with the same marker semantics as `mediaPending`, so a crash
leaves a reconcilable orphan, not a leak. (b) The sum counts entries, so an orphan counts against the owner until the
reconciler (report-only) and a human act; acceptable and stated.

## Deletion, `mediaPending`, D-055(b)

Order of removal is unchanged (files first, row last), so a failed file removal leaves the row and its bytes in the sum
and the marker logic keeps working. Two points. (a) The repository must **raise** on a database error in the delete and
sweep paths, distinct from "not found"; only learner readers (R3, R4) swallow, as the file store's fix did. Say it
(P3-5). (b) Enumeration: the existing test requires every `ACCOUNT_KEYED_TABLES` entry to have `user_id`;
`media_entries` has none, so it needs its own category (for example `OWNER_TOKEN_KEYED_TABLES`) with the account's token
deletion in every language, the payload by cascade, and the file half in `FILE_STORES`. Note that `owner_token` is
derived from the account key, which survives re-registration (the `users` row is kept), so an uploaded file of a deleted
account would reappear to a re-registered account unless the D-055(b) workflow deleted it; the workflow must run before
re-registration and a test should say so (P3-6).

## Import script, cutover, rollback

- **P2-2. The import is not safe to re-run after cutover.** "Idempotent: a second run inserts nothing" holds only while the
  database is untouched. After cutover, learners delete uploads (rows disappear) and the archive still holds them; a second
  `--apply` with `ON CONFLICT DO NOTHING` re-inserts every deleted personal entry (metadata of content the learner
  erased, with `stored_bytes` for files that no longer exist, counted against their quota). **Required:** refuse `--apply`
  unless `media_entries` is empty or an explicit single-use marker is absent; provide `--verify-only` for later checks; and
  record the archive's SHA-256 so the verification of a later date compares against the archive without writing.
- **Concurrent writer.** The window is stop-the-app by procedure only; nothing stops the old process writing to
  `index.json` during the import. Record the file's size and SHA-256 at the start, re-check at the end and at cutover step
  5 before renaming, and abort if it changed (P3-7). The script also needs a size lookup on the asset store (`stat`, not
  `get`) and should take the original's key from `playback.url` (the suffix is not otherwise known); neither exists on
  `BookAssetStore` today (P3-8). Run `ANALYZE media_entries` after the bulk insert, or the first plans at volume are made
  on default statistics.
- **Validation / legacy owners / verification.** Abort-on-any-invalid-entry before writing is right (the file is evidence).
  Legacy personal rows without an owner become the explicit `owner_token('legacy')`, visible only to the local account:
  faithful to today's rule. The read-back equality and canonical hash are the right verification.
- **P2-3. Rollback after writes resumed is stated as "restore the pre-cutover backup".** Step 1's backup is taken **before**
  the schema, so restoring it removes `0024` and every learner record (works, drafts, imports, progress) written since
  cutover: a whole-database loss to undo a media-metadata change. The D4 precedent for this situation is a reviewed
  forward fix, never a downgrade. **Required:** say that after writes resume the rollback is a forward fix; a restore is an
  authorized incident operation that loses everything since the backup and is not a routine option; and keep the real
  safety net where it is cheap: the window rollback (before writes) and the rehearsal. Also decide in advance who restores
  `index.json` if the previous code must run in the window (the rename in step 5 is the undo).
- **Cutover table.** Order is correct (backup, schema, stop, import, deploy, smoke). Add a gate that the application is
  confirmed stopped (no listener) before the import, and a post-import hash check as above.

## Backend selection, tests, rehearsal

- **P2-4. How the hermetic backend is chosen is unspecified.** CI runs with `PERSISTENCE_BACKEND=sqlite` and no PostgreSQL;
  the new repository uses JSONB, a regex CHECK and advisory locks, none of which SQLite has. Say explicitly that with
  `PERSISTENCE_BACKEND=sqlite` (the test backend only, as everywhere else) `app.py` keeps constructing the file store, that
  with PostgreSQL it never does, and that the choice is by that setting alone and never by a connection failure. State the
  consequence honestly: media contract parity, concurrency, EXPLAIN and import proofs are PostgreSQL-only and **local
  execution**, not CI evidence.
- **Test matrix.** Comprehensive (parity across both implementations before cutover, CHECK probes, extracted-column
  agreement, import abort/idempotency/tamper, quota race at the edge, no-dual-write with a poisoned file, keyset stability,
  admin golden JSON, enumeration, regression). Add: import re-run after a delete (P2-2); the delete/sweep path raises on a
  database error rather than treating it as "not found"; a re-registered account does not see a deleted account's
  uploads; head-only `get` does not read the payload table; the schema-parity test and the ORM mirror in `models.py` (the
  proposal does not mention an ORM model for the new tables, which D4 required for parity); head-sensitive tests move to the
  new head (`tests/test_adaptive_reading_schema.py`, cutover script tests).
- **Rehearsal plan.** Good (up/down/up, 100 k and 2 M rows, EXPLAIN per query, import at volume, probes, old-code
  compatibility). Add `ANALYZE` after bulk load, p95 for the heavy-owner sum (including the heap-fetch cost if the index is
  not covering), the advisory lock under 8 workers, and JSONB behaviour for NUL, very large payloads and key order.
- **Window.** A stop-the-app window is acceptable on the lane; the estimate (minutes, under an hour at 2 M) is an
  assumption to be replaced by run 4.

## Findings (P2)

### P2-1. The quota sum is not index-only, and its predicate is not in the index
The query is `sum(stored_bytes) WHERE library = 'personal' AND owner_token = :t AND provider = 'upload'`. The index carries
`stored_bytes` in `INCLUDE` but not `provider`, so PostgreSQL must visit the heap for every row to test `provider`; an
index-only scan also needs a current visibility map. Either drop `provider = 'upload'` from the predicate and add a CHECK
that a personal row's provider is `upload` (the only writer today), or put `provider` in the INCLUDE list. The claim "O(that
account's uploads), independent of the total" stays true (hundreds of rows), but the rehearsal must measure the real plan.

### P2-2. The one-time import can resurrect deleted uploads if run again
See above. Required guard and a `--verify-only` mode.

### P2-3. Post-resume rollback by restoring the backup is disproportionate
See above. Rewrite as forward fix; the restore is an incident operation with named data loss.

### P2-4. Backend selection for the hermetic suite and the "no silent fallback" statement
See above. Select by `PERSISTENCE_BACKEND` only; label PostgreSQL-only evidence as local.

### P2-5. The archive outlives the learner's deletion
`index.json.pre-postgres` keeps every personal entry's title, language, provenance and owner digest after learners delete
their uploads or their account, and the deletion enumeration cannot reach it. Q7 asks how long it is kept: **at most until the
verification is signed off and a short fixed period passes (for example 30 days), then it is deleted; before that,
scrub the personal entries from the archive copy once the import is verified** (the shared entries are the only ones
worth keeping). Record the retention in the Decision Log. This is the same principle as the deleted-import scrub.

## P3 findings
- **P3-1.** Converse owner CHECK; length validation and `lesson` key-set validation in the import.
- **P3-2.** `created_at` immutable on conflict; `upsert` must not flip `library` or `owner_token` of an existing row
  (`ON CONFLICT ... DO UPDATE ... WHERE library = EXCLUDED.library`).
- **P3-3.** Head-only `get` for R2.
- **P3-4.** Cursor order for all-language owner paging; opaque cursors must carry position only, never scope (owner, library
  and language come from the request).
- **P3-5.** Database errors raise in delete/sweep/quota paths; readers degrade.
- **P3-6.** Re-registration and `owner_token`; enumeration category for token-keyed rows.
- **P3-7.** Guard against a concurrent writer to `index.json` during the window.
- **P3-8.** Asset-store `stat`/size and key-from-`playback.url`; `ANALYZE` after load.
- **P3-9.** Learner browse routes should answer 503 on a database outage rather than an empty library (an empty shared
  library with no signal is the silent degradation the proposal elsewhere avoids); at least expose it in readiness.

## Answers to Q1-Q8
1. **`lesson_id` uniqueness.** Decide on the import report: if there are no duplicates, make the index **unique** on shared
   rows (`WHERE library = 'shared' AND lesson_id IS NOT NULL`) so the "first match wins" ambiguity in R6 cannot return; the
   admin import then reports a conflict instead of silently shadowing. If duplicates exist, non-unique with the tie-break
   "newest published shared".
2. **Owner column.** Keep `owner_token` only. A nullable `user_id` for new rows gives two mechanisms and still cannot cover
   legacy rows, so the deletion workflow would need both anyway.
3. **Orphan policy.** Report only; a human-gated cleanup. Auto-deleting a learner's file on a timer is a destructive
   decision about learner data that should not be automatic.
4. **Legacy owner rows.** Import them faithfully under the explicit legacy token and report the count; deleting them in the
   import is a destructive data decision and not needed.
5. **`updated_at` and `version`.** Keep `updated_at`. Drop `version` until a caller passes an expected version (nothing
   in the proposal does: `set_status` and `upsert` ignore it), or wire it into admin status/reprocess now.
6. **One table or two.** One table with the discriminator, with the stricter CHECKs above; two tables would duplicate the
   resolver and the indexes for no isolation gain, since every learner read already goes through `visible_to`.
7. **Window and archive.** A stop-the-app window is acceptable on the lane. Archive retention: short and fixed with the
   personal entries scrubbed after verification (P2-5).
8. **Order with the limits.** Before: the byte rail should ship on `stored_bytes`, not on a file scan, and it removes the
   limits proposal's G1 gate.

## Conditions
1. P2-1 to P2-5 applied in the proposal text (and the P3s as listed).
2. The ORM mirror, schema-parity test and head-sensitive test updates added to the plan.
3. The PostgreSQL rehearsal (runs 1-6) recorded before the migration is moved to `versions/`, and the human's gate for
   applying it unchanged. Nothing here enables the backbone beyond :8021.
