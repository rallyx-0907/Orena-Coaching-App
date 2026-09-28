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

## Quota-group locks

`docker ps` only catches another lane mid-*container*-run. It says nothing about a lane
that is live against a paid provider without a sandbox container. Every live run --
including a smoke test -- takes a lock per **quota group** it draws on, via
`grammar_lab/sandbox/live_provider_lock.py`, and releases them in the same `finally` that
tears the sandbox down. This is the format shared with the Orena Intelligence lane; the
old single `live-provider.lock` is retired.

One file per quota group, in `%USERPROFILE%\.orena\` (all lanes run under the same Windows
user account on this machine):

| File | Quota group |
| --- | --- |
| `live-gemini-text.lock` | Gemini text models -- the evaluator engine in this sandbox |
| `live-gemini-live.lock` | Gemini Live |
| `live-deepseek.lock` | DeepSeek |

Groq has no lock yet. Each file is one JSON object:

```json
{"lane": "grammar-lab", "pid": 12345, "acquired_at": "2026-09-28T06:15:00+00:00",
 "cost_ceiling_usd": 0.05}
```

A lane holds only the groups it uses. Grammar Lab uses **gemini-text** (always -- the
sandbox engine) and **deepseek** (when DeepSeek generates or blind-solves); `run_smoke.py`
derives the set from `--generate-provider`/`--blind-provider`. The module makes no
subprocess/`docker` call at all, so it structurally cannot stop another lane's container.

```bash
# acquire before bringing the sandbox up; $$ is the runner script's own pid,
# not the short-lived python helper's -- the lock must name the long-lived holder
python grammar_lab/sandbox/live_provider_lock.py acquire \
  --lane grammar-lab --pid $$ --groups gemini-text,deepseek --cost-ceiling-usd 0.05

# release in the same trap/finally that tears the sandbox down
python grammar_lab/sandbox/live_provider_lock.py release \
  --lane grammar-lab --pid $$ --groups gemini-text,deepseek
```

Behaviour:

- **Order:** always taken gemini-text -> gemini-live -> deepseek (whatever order you list
  them), released in reverse, so two lanes can never each hold a lock the other waits on.
  Failing to take one gives back every lock already taken in that attempt.
- **Created atomically** (`O_CREAT|O_EXCL`).
- **Held by a live lane:** waits, re-checking every 30s (`--poll-seconds`), up to 30 minutes
  total across all groups (`--wait-max-seconds`); past that, `acquire` exits 1 and prints
  the lock file and the holder's lane/PID. It never kills or waits on that lane's container
  -- only on the lock file.
- **Orphaned lock** (its PID is no longer running, or `acquired_at` is more than 60 minutes
  old, `--stale-seconds`): removed, printed as
  `orphan lock removed: lane=... reason=dead-pid|stale` (followed by `pid=`/`lock=` detail),
  and acquisition retries immediately.
- **Release** only deletes a file whose `lane` and `pid` still match what this process
  wrote; a lock that changed hands underneath it is left untouched.

## Why `PUT /api/admin/ai/config` works here with no login

`APP_ENV=development` and empty `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` make
`AUTH_ENABLED` false and `DEPLOYMENT.production` false. `auth_support.py`'s
`require_admin()` grants a synthetic local-admin identity in exactly that
combination -- no login, no bootstrap user needed. This is the same path
CLAUDE.md already documents for `orena-foundation-web`; it is not a bypass
this sandbox invented.

## Running a live smoke test (`run_smoke.py`)

`run_smoke.py` is the one entry point for a live run against this sandbox -- it holds the
quota-group locks the run uses, brings the sandbox up, runs `generate` -> `validate` ->
`verify`, and guarantees teardown (`docker compose down`, then the lock release) even on failure. Nothing
else should re-implement this sequence by hand; a one-off script in a scratchpad cannot be
trusted to keep the lock and the sandbox in sync the way this one is tested to.

```bash
python grammar_lab/sandbox/run_smoke.py \
  --dotenv "<path to the .env holding the provider keys>" \
  --ids en.plural_nouns.regular,en.there_is_are \
  --generate-provider deepseek --generate-model deepseek-flash --deepseek-thinking off \
  --blind-provider groq --blind-model openai/gpt-oss-120b \
  --cost-ceiling-usd 0.05
```

(That run takes `gemini-text` and `deepseek`; Groq has no lock. `--with-story` only
applies to schema v0.2/v0.3 points -- story is paused, and v0.4 generation rejects it.)

Before bringing the sandbox up it also checks `docker ps` itself for another lane's
`orena-agent-live-*` container. If one is running: release the locks, wait, retry, up to 30
minutes, without prompting anyone; only giving up after the full 30 minutes raises and is
reported. See "Quota-group locks" above for the lock behaviour underneath this.

The rest of this section explains what `run_smoke.py` does step by step, for debugging it
or for following along by hand.

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
