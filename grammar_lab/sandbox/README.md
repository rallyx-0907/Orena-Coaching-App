# Evaluator sandbox

A disposable writing-evaluator instance for `grammar_lab verify --evaluator-url`
(SPEC §5.3). Not the app's real deployment, not any other lane's sandbox --
its own compose project, its own image tag, its own port, no persistent volume.

**Never point `--evaluator-url` at `https://orena.chillpickle.org`.** That
tunnels into the production container (`writing-coach:8000`), which
`CLAUDE.md` lists as off-limits and `AGENTS.md`'s Safety section treats as a
human gate. This sandbox exists so `verify` never has to.

## Isolation from other lanes

- Compose project name `grammar-lab-eval` (`docker compose -p grammar-lab-eval`,
  matching this file's top-level `name:`) -- distinct containers, network and
  project from `ai-writing-coach`, `orena-foundation-web`, or any other lane's
  compose project.
- Image tag `orena-grammar-eval:local`, built fresh from this checkout's
  `Dockerfile`. Never overwrites `ai-writing-coach:local`. Built fresh (not
  reused) so the evaluator's error-label set always matches whatever
  `schema/error_tags.json` was last exported from (SPEC's export-error-tags
  reads the same `writing_coach/languages/*/profile.py` this image bakes in).
- Port 8020 (checked free on this host before use), never 8000/8010/8011.
- `PERSISTENCE_BACKEND=sqlite` on `tmpfs`: no named volume at all, so it can
  never touch `ai-writing-coach-data` / `ai-writing-coach-postgres-data`.
  `docker compose down` leaves nothing behind.
- Before starting: `docker ps` and confirm nothing else is mid-run that this
  would disturb (the three worktrees share one Docker daemon, AGENTS.md §10).

## The live-provider lock

`docker ps` only catches another lane mid-*container*-run. It says nothing
about a lane that is live against a paid provider without a sandbox
container (or about a container that hasn't started yet). Every live run --
including a smoke test -- acquires `%USERPROFILE%\.orena\live-provider.lock`
first, via `grammar_lab/sandbox/live_provider_lock.py`, and releases it in
the same trap that tears down the sandbox.

This is a plain JSON file at a path every lane's process can reach (all
lanes run under the same Windows user account on this machine), never a
Docker construct -- the module makes no subprocess/`docker` call at all, so
it structurally cannot stop another lane's container:

```json
{"lane": "grammar-lab", "pid": 12345, "acquired_at": "2026-09-28T06:15:00+00:00",
 "cost_ceiling_usd": 0.05}
```

Every lane should read and write exactly this shape so the lock means the
same thing everywhere. This checkout cannot see the Orena Intelligence
lane's own implementation (a different worktree/branch, AGENTS.md §3) --
if that lane's lock code was written independently, confirm the field names
and path match before relying on it across lanes.

```bash
# acquire before bringing the sandbox up; $$ is the runner script's own pid,
# not the short-lived python helper's -- the lock must name the long-lived holder
python grammar_lab/sandbox/live_provider_lock.py acquire \
  --lane grammar-lab --pid $$ --cost-ceiling-usd 0.05

# release in the same trap/finally that tears the sandbox down
python grammar_lab/sandbox/live_provider_lock.py release --lane grammar-lab --pid $$
```

Behaviour:

- **Held by a live lane:** waits, re-checking every 30s (`--poll-seconds`),
  up to 30 minutes total (`--wait-max-seconds`); past that, `acquire` exits 1
  and prints who holds it. It never kills or waits on that lane's container
  -- only on the lock file.
- **Orphaned lock** (its PID is no longer running, or `acquired_at` is more
  than 60 minutes old, `--stale-seconds`): removed automatically, printed as
  `orphan lock removed: lane=... pid=... reason=dead-pid|stale`, and
  acquisition retries immediately.
- **Release** only deletes the file when its `lane` and `pid` still match
  what this process wrote; a lock that changed hands underneath it (e.g.
  reaped as an orphan, then re-acquired by someone else) is left untouched.

## Why `PUT /api/admin/ai/config` works here with no login

`APP_ENV=development` and empty `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` make
`AUTH_ENABLED` false and `DEPLOYMENT.production` false. `auth_support.py`'s
`require_admin()` grants a synthetic local-admin identity in exactly that
combination -- no login, no bootstrap user needed. This is the same path
CLAUDE.md already documents for `orena-foundation-web`; it is not a bypass
this sandbox invented.

## Bring it up

`GEMINI_API_KEY` is a bare pass-through in `docker-compose.yml` (`- GEMINI_API_KEY`,
no value): compose reads it from whatever environment invokes `docker compose`,
and the literal value never appears in this file, in `git`, or in this
session's own transcript. In practice: a short-lived script reads only that
one variable's value from wherever it is kept (e.g. another checkout's
`.env`) into the invoking process's environment and immediately calls
`docker compose up` in the same process -- never `cat`/`type`/`echo`ed,
never on a command line, never copied into a file here.

```bash
docker compose -p grammar-lab-eval -f grammar_lab/sandbox/docker-compose.yml up -d
```

Wait for it to be healthy, then select Gemini as the active provider (legacy
AI routing mode, the app's default -- see `writing_coach/ai/platform.py`).
**Never `docker compose config` or `docker inspect` this container** once a
real key is loaded -- both print the fully resolved environment, including
the key value. Use `GET /api/admin/ai/config` (below) to check state instead;
it never echoes credential values, only whether one is configured.

```bash
curl -s http://localhost:8020/api/health
curl -s -X PUT http://localhost:8020/api/admin/ai/config \
  -H 'content-type: application/json' \
  -d '{"provider": "gemini", "model": "gemini-3.5-flash-lite"}'
curl -s http://localhost:8020/api/health   # ai_ready should now be true
```

Then point `grammar_lab verify` at it. `--evaluator-rate-limit-key gemini`
(the default) shares one rate limiter between the sandbox's own Gemini calls
and a Gemini blind-solve model; drop it (pass `''`) if the blind-solve model
is not also drawing on the Gemini quota:

```bash
python -m grammar_lab.pipeline.cli verify --lang en --evaluator-url http://localhost:8020 \
  --blind-provider <family different from generate's --provider> --blind-model <its model>
```

## Cost

Every call `verify` makes to `/api/evaluate` here has the sandbox's own
Gemini call behind it (the engine grading a pitfall/example sentence), on top
of whichever calls `llm_client.py` makes for `generate` and blind-solve --
all belong in the same run's cost estimate. `GET
http://localhost:8020/api/admin/ai/operations` (open under the same dev-mode
admin bypass) returns the app's own recorded per-call cost telemetry after a
run -- read that for the engine side's real figure rather than re-deriving
it from prompt lengths.

## Tear down

```bash
docker compose -p grammar-lab-eval -f grammar_lab/sandbox/docker-compose.yml down
```

Nothing to lose: no named volume, no bind-mounted data directory.
