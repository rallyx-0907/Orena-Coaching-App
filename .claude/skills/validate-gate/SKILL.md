---
name: validate-gate
description: Run the Orena validation gate — project-memory and architecture validators, Node contract tests, and pytest — and report exact results.
disable-model-invocation: true
---

Reproduce the CI gate (`.github/workflows/ci.yml`) locally. CI runs its jobs concurrently, the Node gates come
from `scripts/node_gates.txt` (`sh scripts/run_node_gates.sh`) and pytest runs under pytest-xdist; see
`docs/project/CI_FAST_PATH.md`. Optional argument
`$ARGUMENTS` narrows scope (e.g. a single test path); with no argument, run the
full sequence.

## Before running

The Docker runtime and its named volumes are shared by three worktrees
(`git worktree list`). Confirm no other lane is running a batch before starting.
Never use `docker compose down -v`. An existing-volume warning is not a failure.

## Sequence

**1. Project-memory and architecture validators** (host, stdlib only):

```powershell
python scripts/validate_project_memory.py
python scripts/validate_architecture.py
```

**2. Node contract tests** (host, bare `node`, no package.json):

```powershell
node scripts/test_interactive_transcript_contract.mjs
node scripts/test_listening_player_lifecycle_contract.mjs
node scripts/test_listening_smart_follow_contract.mjs
node scripts/test_listening_ui.mjs
node scripts/test_transcript_display_units.mjs
node scripts/test_transcript_playback.mjs
node scripts/test_active_listening.mjs
node scripts/test_shadowing_practice.mjs
node scripts/test_media_learning_quality.mjs
```

**3. Python tests** — the operator Python has no project dependencies, so run in
the container:

```powershell
MSYS_NO_PATHCONV=1 docker compose run --rm --no-deps \n  -e PERSISTENCE_BACKEND=sqlite -e POSTGRES_RUNTIME_URL= \n  -v "<abs-windows-path>:/workspace:ro" -w /workspace writing-coach \n  sh -lc "pip install -q pytest; python -m pytest -q -p no:cacheprovider test_app.py tests"
```

Use `CURRENT_HANDOFF.md` for the current verified baseline rather than a
hardcoded historical count. `POSTGRES_RUNTIME_URL` must be cleared or
`test_invalid_and_postgres_fail_without_bundle` fails on the environment, not
on the code. pytest is not in the image, so install it in the run.

If step 1 or 2 fails, still run the remaining steps so the report is complete —
but do not start fixing anything from inside this skill.

## Report

- Each step: command, exit status, exact passed / failed / skipped counts.
- Label everything **local execution**. Never claim CI PASS without CI evidence.
- Classify any failure as: source failure, packaging failure,
  execution-environment failure, data-compatibility failure, or real
  application regression (AGENTS.md §12). Do not patch application logic to hide
  an environment problem.
- On a regression, stop and follow AGENTS.md §3 — isolate the root cause; do not
  chain compensating patches, and never weaken a validator to make a batch pass.

## Validator tiers

`scripts/` used to hold 42 validators, 35 of them permanently red because each
one-shot release gate hard-pinned the version it shipped with. Those are now in
`scripts/archive/release-gates/` (read its README before adding anything there).
The 10 that remain fall into three tiers — only tier 1 is a build signal:

**Tier 1 — code contracts. Must pass on the host. A failure is a real defect.**
`validate_project_memory`, `validate_architecture`,
`validate_ui02_compact_headers`,
`validate_learning_repository_boundary`,
`validate_specialized_persistence_boundary`,
`validate_postgres_cutover_readiness`, `validate_powershell_*`.

**Tier 2 — needs project dependencies.** Run in the container, per the pytest
recipe above.

**Tier 3 — operational preflight. Checks a deployment, not the code.**
`validate_public_staging_readiness` needs the staging environment variables;
`validate_ai_capability_control_plane` and `validate_ai_runtime_activation` need
a live PostgreSQL runtime with AI capability settings configured. These failing
on a developer machine means nothing — do not report them as defects, and do
not "fix" the code to make them pass.

When adding a validator, assert the *contract* — a module boundary, route
ownership, an invariant — never a version string or an exact content count.
That is the mistake that made 35 of them worthless.
