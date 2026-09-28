# Current Handoff

## Governance

Purpose: current execution state only. Change when the active lane, verified
batch, gates or next task changes. Do not store secrets, product philosophy or
unverified claims. Product intent and technical authority follow
`PROJECT_MEMORY.md`; local verification does not imply CI pass, human product
approval, or production readiness.

## Current branch / lane

`codex/work` is the baseline and the UI lane. `feature/orena-intelligence`
builds Agent Intelligence (D-085) against `AGENT_CONTRACT.md` v4 (D-092, D-094,
D-095), which is edited only on `codex/work`. Verified history:
`PROJECT_STATE.md` "New learner UI migration".

New learner UI (D-088 - D-091): the pinned design is built at `/next` and
replaces the old UI at `/` in one cutover. Between slices `/` is the old UI,
unchanged; `/next` holds the built surfaces; both share one domain layer; no
learner-data schema changes; the agent runs on the contract mock and nothing
calls `/api/agent/*` until the human says the intelligence lane is integrated.
The intelligence lane integrates against `/next`. Frame → route → code →
status: `docs/design/canonical-ui/IMPLEMENTATION_MAP.md`.

- Foundation: REVIEWABLE.
- Wave A destinations (`c922e37`): IMPLEMENTING - built, reviewed, integrated;
  browser re-check running.
- Agent UI side: contract v4 on the mock; hiding Orena's entry points when the
  agent is absent comes with the Orena panel (Wave B).

## Last verified batch

2026-09-27, `c922e37`, local: all 85 CI `.mjs` gates, the browser ESM graph
(188 modules) and the memory/architecture validators pass. Browser re-check of
the integrated tree pending. Last full pytest: 2026-09-26, PostgreSQL 16,
`2472 passed, 3 skipped`. No CI pass is claimed. Visual-source gate: PINNED.

## DONE

Design pinned and governed (D-088 - D-093); foundation at `/next`; agent
contract v4 (D-095); copy engine fixes; Wave A destinations checkpoint.

## IN PROGRESS

- Wave A browser re-check on the isolated stack (`orena-next-verify-*`,
  127.0.0.1:8021, tmpfs, no provider keys, seeded learner).
- Chinese writing evaluator recall: investigation only; findings go to the
  human before any change.

## PENDING

Human: the 8011 sandbox migration (BLOCKED); the open design questions in
`UI_BACKEND_GAPS.md` section N.

## BLOCKED

- The 8011 sandbox refuses to start: its database (named volume
  `orena-foundation-sandbox-data`, data intact) is at `20260923_0014`, the code
  expects `20260924_0016`. The human authorised 0015/0016 on it; the harness
  blocks the agent, so the human runs them (`scripts/start_orena_sandbox.ps1`
  reports the state).
- Every other shared runtime's Reading migration needs explicit human
  authorization.

## OPEN P0

None.

## OPEN P1

See `ORENA_STATUS.md` and `UI_BACKEND_GAPS.md` section N.

## HUMAN GATES

Web is active; native mobile is frozen. PostgreSQL is the authoritative
runtime, SQLite only an isolated test or frozen rollback/archive backend.
Production, preview, provider credentials, OAuth/DNS/Cloudflare, billing,
deployment, destructive lifecycle, and new learner-owned persistence remain
human gates. Never touch persistent volumes as cleanup.

## NEXT EXACT TASK

UI lane: Wave A to REVIEWABLE and presented; then Wave B (the reading,
listening, dictation, speaking, writing and review workspaces, the Orena panel
on the mock, onboarding); then the cutover (tombstones, legacy redirects, the
old UI and its gates replaced).

Intelligence lane: D-085 against `AGENT_CONTRACT.md` v4; merging `codex/work`
forward brings the version bump its contract test checks.

## Grammar Lab (merged from `feature/grammar-lab`)

Phase 0 of `docs/grammar_lab/SPEC.md`: an isolated, offline, file-based content
pipeline in `grammar_lab/` (own `pyproject.toml`, own tests) and
`docs/grammar_lab/`. It does not import app code, the app does not import it,
and app CI does not collect its tests; no app code, router, engine, migration or
runtime is involved. NEXT: human review of `docs/grammar_lab/PHASE0_DECISIONS.md`
(including how lab point IDs join the R5 Concept IDs, SPEC §8); phase 1 waits.
