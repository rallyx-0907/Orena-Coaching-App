# Production migration pack: :8000 from its current revision to the chain head (D-143)

Status: **IMPLEMENTED ON BRANCH, AWAITING HUMAN REVIEW.** Nothing has been applied to :8000 and nothing on :8000 has
been read. Author: Claude lane, 2026-10-08. Decision: D-143 (2, 3, 5).

## 1. What it is

One tool and one procedure take the product runtime from the revision its backup recorded to this checkout's head,
the same steps on a disposable restored copy and on :8000:

| Piece | File | Change |
| --- | --- | --- |
| Backup (reads only) | `scripts/product_backup.ps1` | Manifest v3 records the PostgreSQL cluster's `system_identifier`, each table's columns and a content fingerprint per table (below). |
| Rehearsal on a copy | `scripts/product_migration_rehearsal.ps1` | Runs the chain through the pack (was: one `upgrade head`, which skipped 0016's gate, timed nothing, and would have reported 0016's renames as lost rows). Waits for the image's init server to finish before restoring (a restore into the init server was silently lost) and checks `pg_restore`'s exit code. |
| Chain runner and gates | `scripts/product_migration_pack.py` (new) | `digest`, `rehearse`, `plan`, `apply`. |
| Gate tests | `tests/test_product_migration_pack.py` (new) | 14 cases, no database. |

No migration file changed. `bootstrap_runtime_schema.py` and `reading_canonical_cutover.py` are unchanged: the sandbox
cutover command keeps refusing ports 8000/8010 and the production database name; the pack calls its reviewed
`apply()` function for 0016 behind the pack's own gates instead.

## 2. How a step runs

The chain, oldest first, **one revision per step and one transaction per step**: a step's locks are released before
the next starts, and a failed step leaves the database at the revision before it. On each step's own connection:

1. the server is the confirmed database in the pinned cluster (`identity_on`, `identity_refusal`);
2. an advisory lock keeps a second migrator out;
3. the revision is the expected one;
4. `alembic upgrade <revision>` on that connection; the revision afterwards is the step's, or it rolls back.

`20260924_0016` runs through `reading_canonical_cutover.apply` (same checks, its own lock). It **renames**
`reading_sessions` / `reading_attempts` to `reading_legacy_*`, freezes them with triggers, and creates the canonical
tables. Nothing is converted or backfilled (D-143 2).

After the chain: the revision is the head and `readiness()` says ready; **every row the backup counted is still
there**, table by table, under the names the steps gave it; the legacy archive has its freeze triggers.

## 3. The gates of `apply` (all must hold before anything is written)

- The backup's files match their recorded sizes and SHA-256, and the backup is younger than `--max-age-hours`
  (default 12).
- `rehearsal.json` beside the backup **passed**, was made from **this dump** (SHA-256), with **this chain** (digest
  over `migrations/versions/*.py`, line endings normalised, and head) and with **this migration-execution code**:
  `execution_digest` over `alembic.ini`, `migrations/env.py`, `migrations/versions/*.py`, the pack, the Reading cutover
  and bootstrap commands, `writing_coach/runtime_schema.py`, `persistence/runtime.py`, `config.py`, `models.py` and
  `requirements.txt` (35 files today; the list is in `rehearsal.json`). Any change to that surface means rehearse again.
  The rehearsal must also have verified table contents (`fingerprints_checked`).
- The server is the database and the cluster the backup recorded, and both equal `--confirm-production` and
  `--expect-cluster`. A rehearsal refuses the reverse: a server in the backup's own cluster is the source, not a copy.
- **No learner wrote since the backup**: the database is at the backup's revision (or one the chain passed, when a
  stopped run is resumed), every table holds exactly the backed-up row count, **and every table's content
  fingerprint equals the backup's**: md5 over the sorted md5 of each row, over the columns the table had at backup
  time, with TimeZone, DateStyle, IntervalStyle, extra_float_digits and bytea_output pinned so a value renders the same
  in `psql` at backup time and in the pack. An UPDATE, or a delete and insert that leave the count unchanged, is
  refused. A resumed run compares under the renames over the backed-up columns only (a revision that rewrote existing
  values would make a resume refuse: restore and start again). A backup without fingerprints (manifest v2) cannot be
  applied. So a restore of that backup loses nothing, which is what makes it the rollback.
- Cost: one full read of every table at backup and at apply; seconds at :8000's size.
- `--authorization` names the human's decision record; it is printed in the log and in `RESULT=`.

## 4. Evidence so far (local, synthetic; not :8000)

A disposable PostgreSQL 17 at `20260908_0005` with 2 users, 2 legacy Reading sessions and 3 attempts, backed up with
`product_backup.ps1`, then (2026-10-08, all containers and networks removed afterwards):

- rehearsal: `REHEARSAL=PASS`, 20 steps `0005 -> 20261007_0029`, rows kept, legacy archive 2 / 3 with 4 triggers;
- `plan` on the source: 20 steps listed, 0016 marked, nothing changed;
- `apply` with a wrong `--expect-cluster`: refused; after one extra `users` row: refused (`users: backup 2, now 3`);
- `apply` with the right identity: 20 steps, about 0.25 s each, `ready`, rows kept; an `UPDATE` on
  `reading_legacy_sessions` afterwards fails with "the legacy Reading archive is read-only".

Step times on real data come from the rehearsal of :8000's backup, not from this.

Gate demonstration after the 2026-10-08 review (synthetic, disposable, removed afterwards): a v3 backup at 0004 with a
`timestamptz` written at +07:00; rehearsal `REHEARSAL=PASS` with `contents match the backup` and the execution digest
recorded; then on the source:
1. `UPDATE users SET name = ...` (count unchanged): refused, `users`.
2. delete one `reading_attempts` row and insert another (count unchanged): refused, `reading_attempts`.
3. `apply` from a tree whose `reading_canonical_cutover.py` differs by one comment: refused, "different
   migration-execution code".
4. data put back exactly: `rows and contents match the backup`, 21 steps, PASS.
Regression tests: `tests/test_product_migration_pack.py` (`test_an_update_with_unchanged_row_counts_is_refused`,
`test_a_resumed_run_compares_contents_under_the_renames_over_the_backed_up_columns`,
`test_the_execution_digest_covers_every_file_that_runs_a_migration`, and the rehearsal-binding cases).

## 4b. Rehearsal of :8000 (2026-10-08, for human review; nothing applied to :8000)

- Release candidate: `codex/work` `328e49ef6cc3e8f2c2e694c3e0d20fcd441d746a`, rehearsed from a `git archive` of that
  commit. Chain digest `65044f6e470807106a5a892461c56342cdf8717ddbe2fc04203b5bbf85883ea3`, head `20261007_0029`.
- Backup (read-only, `product_backup.ps1`): database `becoming`, cluster `7672581591402848290`, taken
  2026-10-08T01:17:40Z; `database.dump` 115,913 bytes, SHA-256 `b1b2b6c9...398bedf`; `files.tar.gz` (volume
  `ai-writing-coach-data`) 66,835 bytes, 32 entries. Kept outside the repository under
  `%LOCALAPPDATA%\orena-productackups61008T011737Z-ai-writing-coach-postgres-1\` with `rehearsal.json`.
- **:8000 is at `20260828_0004`, not 0005**: the chain is **21 steps** (0005 ... 0029).
- Rows before (non-empty tables): users 5, user_language_profiles 5, essays 25, essay_revisions 25, writing_errors 89,
  saved_words 5, grammar_progress 2, reading_sessions 14, reading_attempts 1, audit_logs 22, plans 2,
  plan_entitlements 18.
- Result: `REHEARSAL=PASS`. Restore reproduced the backup (19 tables, revision 0004); 21 steps, 6.1 s in total, the
  longest 0.37 s (0023); every backed-up row kept; 38 new tables; legacy Reading archive 14 sessions / 1 attempt with
  4 freeze triggers; files archive reads end to end. The disposable PostgreSQL and its network were removed.
- This rehearsal used a v2 backup (counts only) and predates the execution digest. It stays valid evidence for the
  candidate (human review 2026-10-08); it cannot itself authorize an apply: the final backup is v3 and is rehearsed
  with the merged code.
- For the real apply (D-144 6-7): the pack requires a passed rehearsal of **the same dump**, so the final production
  backup is rehearsed the same way (minutes) before `apply`; and the chain digest above must equal the one computed
  on the merged `main` SHA (`python scripts/product_migration_pack.py digest`), else rehearse again.

## 5. Revisions that need their own attention (D-143 3)

| Rev | Why | What the reviewer checks in the rehearsal report |
| --- | --- | --- |
| 0015 reading content engine | Integration revision; its predecessor was authorized for the 8012 sandbox only, and it asks for an independent delta review before a shared runtime. | The 6 new tables appear empty; no existing table's count changes; step time. |
| 0016 adaptive reading | Non-additive. Renames the legacy tables and freezes them; old code writing them fails, so code and schema ship as one unit. | `legacy_reading.sessions/attempts` equal the backup's `reading_sessions/attempts`; `freeze_triggers` > 0; the canonical `reading_attempts` is new and empty. |
| 0029 practice session id | Approved for :8021 only (D-142). Adds a nullable column and an index on `speaking_attempts`. | Step time against the real `speaking_attempts` size (the index build holds its lock for that long); no backfill. |
| 0018 account settings | Adds 4 columns to `users`, the hottest table. | Step time; with writes stopped for the window there is no contention. |
| 0005 account work backbone | :8000 is still at 0004, so this backbone revision is applied too (flag stays off, D-143 4). | Its tables appear empty; step time. |

## 6. The human's procedure for :8000 (none of it is run by a lane)

Preconditions: D-143 release shape done (the cutover), CI green, `codex/work -> main` merged by the human, new image
built, maintenance window, no other lane on Docker.

1. Stop the :8000 web and worker (writes stop; the pack refuses otherwise).
2. `scripts\product_backup.ps1 -Postgres ai-writing-coach-postgres-1 -DbUser <user> -DbName <db> -DataVolume ai-writing-coach-data`
   then `scripts\product_migration_rehearsal.ps1 -Backup <folder>`: `REHEARSAL=PASS` and `rehearsal.json` beside it.
   **The human reviews `rehearsal.json` (step times, rows, legacy archive) and records the authorization.**
3. `plan`, then `apply`, from an ephemeral container of the new image on :8000's network, the backup mounted
   read-only and the database URL passed through a temporary env-file that is deleted afterwards:
   `python scripts/product_migration_pack.py apply --backup /backup --confirm-production <db> --expect-cluster <id from the manifest> --authorization D-1xx`
4. Start the new image; `GET /api/readiness`; smoke (D-143 release checklist in `RELEASE_8000_READINESS.md`).
5. Rollback inside the window: restore the step-2 backup (it is exact, because the pack proved no write happened since)
   and start the old image. After writes resume: forward-fix only.
