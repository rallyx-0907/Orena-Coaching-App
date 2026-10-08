# Production migration pack: :8000 from its current revision to the chain head (D-143)

Status: **IMPLEMENTED ON BRANCH, AWAITING HUMAN REVIEW.** Nothing has been applied to :8000 and nothing on :8000 has
been read. Author: Claude lane, 2026-10-08. Decision: D-143 (2, 3, 5).

## 1. What it is

One tool and one procedure take the product runtime from the revision its backup recorded to this checkout's head,
the same steps on a disposable restored copy and on :8000:

| Piece | File | Change |
| --- | --- | --- |
| Backup (reads only) | `scripts/product_backup.ps1` | Manifest v2 also records the PostgreSQL cluster's `system_identifier`. |
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
- `rehearsal.json` beside the backup **passed**, was made from **this dump** (SHA-256) and with **this chain**
  (digest over `migrations/versions/*.py`, line endings normalised, and head). What runs on :8000 is what was rehearsed.
- The server is the database and the cluster the backup recorded, and both equal `--confirm-production` and
  `--expect-cluster`. A rehearsal refuses the reverse: a server in the backup's own cluster is the source, not a copy.
- **No learner wrote since the backup**: the database is at the backup's revision (or one the chain passed, when a
  stopped run is resumed) and every table holds exactly the backed-up row count. So a restore of that backup loses
  nothing, which is what makes it the rollback.
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

## 5. Revisions that need their own attention (D-143 3)

| Rev | Why | What the reviewer checks in the rehearsal report |
| --- | --- | --- |
| 0015 reading content engine | Integration revision; its predecessor was authorized for the 8012 sandbox only, and it asks for an independent delta review before a shared runtime. | The 6 new tables appear empty; no existing table's count changes; step time. |
| 0016 adaptive reading | Non-additive. Renames the legacy tables and freezes them; old code writing them fails, so code and schema ship as one unit. | `legacy_reading.sessions/attempts` equal the backup's `reading_sessions/attempts`; `freeze_triggers` > 0; the canonical `reading_attempts` is new and empty. |
| 0029 practice session id | Approved for :8021 only (D-142). Adds a nullable column and an index on `speaking_attempts`. | Step time against the real `speaking_attempts` size (the index build holds its lock for that long); no backfill. |
| 0018 account settings | Adds 4 columns to `users`, the hottest table. | Step time; with writes stopped for the window there is no contention. |

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
