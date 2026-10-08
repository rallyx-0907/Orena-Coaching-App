# Updating the product on :8000 safely (D-127, completion plan item 1)

:8000 is the product, run on this machine (D-127). Only the human updates it, through a merged PR
`codex/work` -> `main`. No lane runs any command on :8000. This page gives the human the commands, in order, and
says what each one checks. Every command only reads :8000 until step 5.

## What lives where (volume check, 2026-10-04)

| Data | Where on :8000 | Persistent? |
| --- | --- | --- |
| PostgreSQL (learners, content, telemetry) | named volume `ai-writing-coach-postgres-data` | yes |
| Imported media, media assets, Reading/Books assets | `ai-writing-coach-data` at `/data` (`MEDIA_LIBRARY_ROOT`, `MEDIA_LIBRARY_ASSET_ROOT`, `READING_LIBRARY_ASSET_ROOT`) | yes |
| Word recordings and explained words (`WORD_AUDIO_ASSET_ROOT`, `WORD_DEEP_ASSET_ROOT`) | **before this change: `/app/data/...` inside the container, lost on every recreate** | fixed in `compose.yaml`: now `/data/word_audio`, `/data/word_deep` |
| Frozen SQLite archives (`WRITING_DB`, `AUTH_DB`, ...) | `/data/*.db` | yes (archive only) |
| Temporary media work | `/app/data/media_temp` | no, and need not be |

`tests/test_deployment_config.py` now fails if an asset root the app writes is not on the volume, and checks
that the Reading worker runs as its own service (`reading-worker`, added to `compose.yaml`).

## Steps

0. **Check the settings the new version requires** (security review, 2026-10-04):
   - with `APP_ENV=production`, `SESSION_SECRET` must be at least 32 characters, or the app refuses to start.
     Check only its length, never print it:
     `docker exec ai-writing-coach-writing-coach-1 python -c "import os; print(len(os.environ.get('SESSION_SECRET','')) >= 32)"`.
     Changing it signs everyone out once;
   - with authentication off, the signed-out "local developer" admin now exists only when `PUBLIC_BASE_URL` is
     this machine's own address (`localhost`, `127.0.0.1`), or with `ALLOW_LOCAL_ADMIN=1` set on purpose.

1. **Back up :8000 (reads only).**

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\product_backup.ps1 `
     -Postgres ai-writing-coach-postgres-1 -DbUser becoming -DbName becoming -DataVolume ai-writing-coach-data
   ```

   Output: `database.dump`, `files.tar.gz`, `manifest.json` (SHA-256, revision, exact row count of every table)
   under `%LOCALAPPDATA%\orena-product\backups\<stamp>-...`, and a last line `BACKUP=<folder>`.

2. **Rehearse the update on a copy (throwaway containers only).**

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\product_migration_rehearsal.ps1 -Backup <folder>
   ```

   It restores the dump into an ephemeral PostgreSQL, checks it reproduces the manifest exactly, runs this
   checkout's migration chain to head, checks no table lost a row, and reads the files archive end to end.
   **Go on only with `REHEARSAL=PASS`.** The report is `rehearsal.json` beside the backup.

3. **Keep the word recordings across the recreate** (once, before the first update with the new `compose.yaml`):

   ```powershell
   docker exec ai-writing-coach-writing-coach-1 sh -c "mkdir -p /data/word_audio /data/word_deep; cp -a /app/data/word_audio/. /data/word_audio/ 2>/dev/null; cp -a /app/data/word_deep/. /data/word_deep/ 2>/dev/null; true"
   ```

4. **Merge** the reviewed PR `codex/work` -> `main` and update the checkout that runs :8000 to `main`.

5. **Migrate, then start** (the human's gate; never `down -v`):

   ```powershell
   docker compose build writing-coach
   docker compose run --rm --no-deps writing-coach python scripts/bootstrap_runtime_schema.py --upgrade --from <current> --to <head> --confirm
   docker compose up -d writing-coach reading-worker
   ```

   `<current>` and `<head>` are the two revisions the rehearsal printed. Then open :8000 and check sign-in, one
   Reading text, one Listening item and Admin > Overview.

6. **If anything is wrong**: stop the web and worker containers, restore the database from the step-1 dump into
   the same PostgreSQL (`pg_restore --clean --if-exists`), put the previous `main` back, start again. The
   step-1 folder is the only rollback point: keep it until the new version has run for a few days.

Not covered here, by design: deployment to a VPS (item 6, its own runbook and rehearsal), and the media
metadata move to PostgreSQL (needs migration `20261001_0024`, which is not on `codex/work`; a human gate).
