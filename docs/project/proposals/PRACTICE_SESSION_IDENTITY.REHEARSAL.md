# Practice session identity rehearsal (0029), recorded

Throwaway `postgres:16` container (PostgreSQL 16.15), started with `--rm`, no named volume, no `-v`, published only on
`127.0.0.1:55436`, stopped (so removed) after the run. `scripts/rehearse_practice_session_identity.py` ran in the
application image with the repository mounted read-only. No existing container or volume was touched; no provider was
called. Local execution, 2026-10-07, branch `claude/practice-session-identity`. The password is generated into an
environment variable and never printed (the script's output is filtered through `sed` for it as well).

| Run | State | Result |
| --- | --- | --- |
| 1 | `20261007_0029` over the chain 0001 -> 0025 | **16 PASS, 0 FAIL** |
| 2 | same, repeated on a fresh container | **16 PASS, 0 FAIL** |

## Commands

```bash
REHEARSAL_PW=$(head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n'); export REHEARSAL_PW     # never echoed
NAME=orena-pg-rehearsal-$RANDOM
docker run --rm -d --name "$NAME" -e POSTGRES_PASSWORD="$REHEARSAL_PW" -e POSTGRES_DB=orena_rehearsal \
  -p 127.0.0.1:55436:5432 postgres:16
until docker exec "$NAME" pg_isready -U postgres -d orena_rehearsal; do sleep 1; done
MSYS_NO_PATHCONV=1 docker run --rm -e REHEARSAL_PW -e PERSISTENCE_BACKEND=sqlite -e POSTGRES_RUNTIME_URL= \
  -e APP_ENV=development -e GOOGLE_CLIENT_ID= -e GOOGLE_CLIENT_SECRET= -e GOOGLE_REDIRECT_URI= \
  -e PUBLIC_BASE_URL=http://localhost:8000 -e WRITING_DB=/rundata/w.db -e AUTH_DB=/rundata/a.db \
  -e PLATFORM_DB=/rundata/p.db -e PRODUCT_DB=/rundata/pr.db --tmpfs /rundata \
  -v "<abs-windows-path-of-the-worktree>:/workspace:ro" -w /workspace ai-writing-coach:local \
  sh -c 'python scripts/rehearse_practice_session_identity.py "postgresql+psycopg://postgres:${REHEARSAL_PW}@host.docker.internal:55436/orena_rehearsal"'
docker stop "$NAME"          # --rm removes it; `docker ps -a | grep orena-pg-rehearsal` then shows nothing
```

The script refuses a database that is not clearly throwaway (name must contain `rehears`, host local, not a runtime port,
not `POSTGRES_RUNTIME_URL`) or not empty. Revisions are applied through the repository's own Alembic configuration
(`_runtime_alembic_config`, `migrations/versions/` only; the proposed 0026 is not in the chain).

## Output (run 2)

```text
PostgreSQL 16.15 (Debian 16.15-1.pgdg13+2) on x86_64-pc-linux-gnu
Running upgrade  -> 20260811_0001 ... Running upgrade 20260930_0023 -> 20261004_0025
PASS  chain applied to 0025                                      20261004_0025
PASS  0025 has neither the column nor the index
Running upgrade 20261004_0025 -> 20261007_0029, Practice session identity on Speaking attempts
PASS  up to 0029: nullable uuid column, no default               type=UUID
PASS  up to 0029: the index exists
PASS  legacy row untouched, no backfill                          [('legacy-take', None)]
Running downgrade 20261007_0029 -> 20261004_0025
PASS  down to 0025: column and index gone, the attempt stays     attempts=1
Running upgrade 20261004_0025 -> 20261007_0029
PASS  up again to 0029
PASS  a writer WAITS while the advisory lock is held             ungranted advisory locks=1
PASS  the writer completes once it is released
PASS  12 concurrent first attempts mint exactly one session id (repository)   returned ids=1 stored rows=12 distinct ids=1 errors=[]
PASS  a later attempt within 30 minutes reuses the id
PASS  an attempt after more than 30 idle minutes starts a new session
PASS  another account never shares the session
PASS  another language never shares the session
PASS  12 concurrent POSTs through the route: one session holding all of them   statuses ok=12 count=12
PASS  flag off: the read route answers the explicit 404 practice_session_disabled

16 PASS, 0 FAIL
```

## What it proves, and what it does not

- Revisions: `20261004_0025` -> `20261007_0029` -> `20261004_0025` -> `20261007_0029`. The column is a nullable `uuid` with
  no default, the index `ix_speaking_attempts_session` exists after each upgrade and is gone after the downgrade, and the
  one pre-existing attempt row survives untouched with NULL (no backfill, D-142.4).
- The lock is the real PostgreSQL one: while another connection holds `pg_advisory_xact_lock` for the account + language
  key, the writer is observed waiting (an ungranted advisory lock in `pg_locks`) and completes only after release.
- Twelve simultaneous first attempts of one account + language, released together by a barrier on separate pooled
  connections, mint exactly one id, both through the repository and through `POST /api/speech/attempts` with
  `ORENA_PRACTICE_SESSION=on`; `GET /api/speech/attempts?session=current` then returns that one session with all twelve.
- Not shown: lock behaviour across two application nodes (one PostgreSQL, so the same lock; not exercised with two
  processes), behaviour at production volume, and any production or sandbox database. Migration 0029 was applied to this
  disposable database only.
