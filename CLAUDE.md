# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Restore Orena project memory first

@AGENTS.md is the binding engineering contract. Start with
`docs/project/PROJECT_MEMORY.md` and its bounded startup order.
`/resume-orena` restores the current context without loading the historical
repository.

Always verify branch, HEAD, working tree, and recent commits. Chat history is
not authoritative. Orena is the active product, `/` is canonical, and
`/becoming` plus BECOMING-named paths/symbols are legacy compatibility—not
current product direction. Follow `PROJECT_MEMORY.md`'s separate product-intent
and implementation-fact precedence models.

### Orena learner UI startup

For learner-facing Web or native UI work, read `docs/project/DESIGN_CONTRACT.md`
and then:

```text
docs/ORENA_PRODUCT_DNA.md
docs/ORENA_DESIGN_TOKENS.json
docs/ORENA_COMPONENT_CONTRACT.md
docs/ORENA_RESPONSIVE_COMPOSITION.md
the relevant docs/ORENA_*_GOLDEN_SPEC.md
```

Do not redesign a migrated screen from a blank canvas. Use approved Orena
product components and composition recipes first. For migrated screens, the
ORENA_* UI/product grammar supersedes legacy BECOMING visual direction; legacy
release, persistence, security and functional contracts remain binding.

## Test and validation runtime

The operator's Python 3.11 has **no project dependencies** (no pytest,
SQLAlchemy, Alembic, psycopg). Run dependency-heavy tests and validators inside
the app container:

```powershell
MSYS_NO_PATHCONV=1 docker compose run --rm --no-deps \n  -e PERSISTENCE_BACKEND=sqlite -e POSTGRES_RUNTIME_URL= \n  -e GOOGLE_CLIENT_ID= -e GOOGLE_CLIENT_SECRET= \n  -e APP_ENV=development -e PUBLIC_BASE_URL=http://localhost:8000 \n  -e GOOGLE_REDIRECT_URI= \n  -v "<abs-windows-path>:/workspace:ro" -w /workspace writing-coach \n  sh -lc "pip install -q pytest; python -m pytest -q -p no:cacheprovider test_app.py tests"
```

Four things that will otherwise cost you an hour:

- The image does **not** ship pytest (`requirements.txt` omits it) — install it in
  the ephemeral container, as above.
- Git Bash rewrites `-w /workspace` into `C:/Program Files/Git/workspace`. Prefix
  with `MSYS_NO_PATHCONV=1` and pass the volume source as a Windows path.
- Compose may inject `POSTGRES_RUNTIME_URL`, which makes
  `test_invalid_and_postgres_fail_without_bundle` fail inside the container while
  passing in CI. Clear it with `-e POSTGRES_RUNTIME_URL=`. Use the current
  handoff for the latest verified count instead of hardcoding a historical one.
- Compose also injects the Google OAuth pair, which turns `AUTH_ENABLED` on and
  makes unauthenticated route tests answer 401 where CI sees 200/503. Clearing
  the pair alone then trips the `APP_ENV=production` guard, so clear
  `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` and `GOOGLE_REDIRECT_URI` **and**
  set `APP_ENV=development` with a local `PUBLIC_BASE_URL`, as above. Without
  it, `tests/test_r17_admin_routes.py` and `tests/test_reference_data_cache.py`
  fail locally for environment reasons only.

Pure-stdlib validators (`scripts/validate_*.py` that only read files) and the
Node contract tests run on the host:

```powershell
python scripts/validate_project_memory.py
python scripts/validate_architecture.py
node scripts/test_listening_ui.mjs
```

CI (`.github/workflows/ci.yml`) runs the project-memory validator,
`validate_architecture.py`, the current `.mjs` contract gate, then
`pytest -q test_app.py tests` with `PERSISTENCE_BACKEND=sqlite`. `/validate-gate`
reproduces that sequence.

Linting is ruff, **lint-only** (`ruff.toml`) — no formatter is configured, since
reformatting would produce large diffs across protected areas. Ruff is not in
`requirements.txt`; install it separately (`pip install ruff`) and lint the files
you touched: `ruff check <path>`. There is no `package.json` — `.mjs` tests run
under bare `node`.

## Branching

Work on `claude/<task>` branches, mirroring the `codex/*` lane convention. Never
develop directly on `main`; never auto-merge to `main`. Stage only files
belonging to the current coherent change — `git add -A` is forbidden.

## Shared Docker runtime — three worktrees

`git worktree list` shows three lanes (`...-v030`, `...-claudecode`,
`...-codex`) sharing one Docker runtime and one set of named volumes
(`ai-writing-coach-data`, `ai-writing-coach-postgres-data`). Only one lane may
operate Docker at a time — confirm no other lane is running a batch first.

Never `docker compose down -v`. Never delete persistent volumes as cleanup.

## Persistence invariants

PostgreSQL is the authoritative runtime; SQLite is frozen rollback/archive
only. No dual-write, no reverse sync, no silent SQLite fallback, no startup
auto-import, no startup automatic Alembic.

## Environment

Copy `.env.example` to `.env` (`start_docker.ps1` does this). Never print,
commit, or document secret **values** — variable names are fine.

## Protected areas

Do not opportunistically refactor Journey, Review, Library / Active Recall UI,
shared layout primitives, the shared CSS/JS design system, R5 Grammar contracts
and Concept IDs, or `docs/visual-references/**`. If a task requires touching
one, state why, make the minimum change, verify immediately.

## Reporting

Do not report success because code was written — success requires validating the
changed flow. Label local runs as local execution; never claim CI PASS without
CI evidence. `/completion-report` emits the required §17 report.

<!-- The Codex import appended a full copy of AGENTS.md here. Removed: it is
     already pulled in by the @AGENTS.md import above, and duplicating it
     loaded the contract twice into every session. -->
