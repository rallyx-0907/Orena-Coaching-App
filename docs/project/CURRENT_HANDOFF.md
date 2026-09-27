# Current Handoff

## Governance

Purpose: current execution state only. Change when the active lane, verified
batch, gates or next task changes. Do not store secrets, product philosophy or
unverified claims. Product intent and technical authority follow
`PROJECT_MEMORY.md`; local verification does not imply CI pass, human product
approval, or production readiness.

## Current branch / lane

`codex/work` is the unified baseline (Admin + Speaking merged by PR #63 at
`9c0fe31`, integration HEAD `7565f6d`). D-085: Agent Intelligence develops on
`feature/orena-intelligence`. D-086: the new learner UI replaces the old one on
`codex/work` and is the only UI that carries the agent; both lanes build
against `docs/project/AGENT_CONTRACT.md` (contract_version 2, D-092), edited
only on `codex/work`.

**New learner UI migration (D-088 - D-091), in progress on `codex/work`.** The
design is Claude Design project `e6dc1cb2`, revision `1790473816124946`, pinned
in `docs/design/canonical-ui/screens/` (`SYNC_2026-09-27.md`). Strategy (D-091):
the new UI is built beside the old one and replaces it in one cutover. Between
slices `codex/work` is always in this state:

- `/` serves the **old** UI (Dark Glass), unchanged;
- `/next` serves the **new** UI (`templates/orena/next.html`,
  `static/orena/main.js`, `shell/`, `kit/`, `screens/`, `copy/`, `agent/`),
  holding the surfaces under "New UI coverage";
- both import one domain layer (`product/`, `capabilities/`, `content/`,
  `infrastructure/`); no learner-data schema has changed;
- the agent panel exists only in the new UI, on the contract mock
  (AGENT_CONTRACT §11-12); nothing calls `/api/agent/*` until the human says the
  intelligence lane is integrated.

The intelligence lane integrates against `/next`. Frame → route → code → status:
`docs/design/canonical-ui/IMPLEMENTATION_MAP.md`.

### New UI coverage

- **Foundation (reviewable):** tokens for both themes and the device variables
  equal the pin (gated); Lucide icons at `lucide-static@0.525.0`; the brand
  marks from `assets/brand/orena/logo/`; kit primitives; the shell (rail, top
  bar, phone header and bar, focus mode, breadcrumb, nav origin), measured equal
  to the design's shell; the router with all 47 routes (unbuilt ones show the
  design's Coming soon); copy in en / vi / zh by layer. Gates
  `test_orena_kit`, `test_orena_shell`, `test_orena_copy`. Open: colour
  contrast N-8 (`UI_BACKEND_GAPS.md`) awaits the human.
- **Surfaces:** none yet.

## Last verified batch

2026-09-27, new UI foundation, local: the three new gates, 66 of the 68 other
CI `.mjs` gates, the browser ESM graph (138 modules), route tests and the
memory/architecture validators pass; the shell measured against the pinned
frame at 1440x900, checked at 390x844, in en / vi / zh and both themes. The two
failing gates, `test_orena_reading_library` and `test_orena_writing_workspace`,
fail identically on the reviewed commit `7565f6d` - inherited, old-UI surfaces
the cutover replaces. No CI pass is claimed.

2026-09-26, unified baseline: full Linux pytest with PostgreSQL 16
`2472 passed, 3 skipped`; all 16 Alembic revisions reach head `20260924_0016`
on a throwaway database.

Visual-source gate: **PINNED** (2026-09-27). The source was read in full -
DesignSync for files under 256 KiB, the human's export for `Orena.dc.html`
(first 256 KiB byte-identical to the DesignSync read) - and pinned; fidelity is
judged per new-UI surface against that pin. The old UI is not redesigned.

## DONE

Unified baseline reviewed and merged (PR #63). New learner design pinned and
governed (D-088 - D-091, `e3f8ba2`); new UI foundation at `/next`.

## IN PROGRESS

New learner UI surface slices (`IMPLEMENTATION_MAP.md`), then the cutover.
No Agent Intelligence implementation is integrated into `codex/work` yet.

`feature/orena-intelligence`: Slice 1a is REVIEWABLE (local verification,
2026-09-27) - `writing_coach/agent/` contracts, registries, fake provider and
voice interfaces, three `AIOperation` values; no router, no persistence, no
provider call. Human rulings R1-R7 are in `AGENT_SPEC.md` §0; the lane's gaps
are `UI_BACKEND_GAPS.md` I-1..I-21.

## PENDING

Human action: the sandbox migration (BLOCKED below).

Intelligence lane: Slice 1b in progress; the Admin labels for the four agent
capability keys are on codex/work (71e84a0), so the keys land in 1b as inert
definitions (I-17).

## BLOCKED

- The 8011 sandbox refuses to start: its database is at `20260923_0014`,
  `codex/work` expects `20260924_0016`. The human authorised applying 0015/0016
  to the sandbox database only; the harness would not let the agent run it, so
  the human runs the commands given in the session. Until then the new UI is
  verified on an isolated throwaway stack (`orena-next-verify-*`,
  127.0.0.1:8021, PostgreSQL on tmpfs, no provider keys).
- Every other shared runtime's Reading migration still needs explicit human
  authorization.

## OPEN P0

None.

## OPEN P1

See `ORENA_STATUS.md` and `UI_BACKEND_GAPS.md` (N-8 contrast decision).

## HUMAN GATES

Web is active; native mobile is frozen. PostgreSQL is the authoritative
runtime, SQLite only an isolated test or frozen rollback/archive backend.
Production, preview, provider credentials, OAuth/DNS/Cloudflare, billing,
deployment, destructive lifecycle, and new learner-owned persistence (e.g.
onboarding state beyond the device) remain human gates. Never touch persistent
volumes as cleanup.

## Agent lane

Owned by `feature/orena-intelligence` (D-085); the only part of this file that
lane edits. Slices 1a and 1b REVIEWABLE (local verification, 2026-09-27), not
integrated into `codex/work`: `/api/agent/turn` (SSE) and
`/api/agent/capabilities` behind `AGENT_ENABLED` (off by default, never in
production), the legacy AI selection (never a local model), Vocabulary and
Writing read tools in EN and ZH, contract streams S1, S5, S8, S9, the four agent
capability keys inert; no schema change. Rulings, progress and the next slice:
`AGENT_SPEC.md` §0; gaps: `UI_BACKEND_GAPS.md` I-1..I-25.

## NEXT EXACT TASK

UI lane (`codex/work`): build the surface slices of `IMPLEMENTATION_MAP.md` on
the foundation - destinations (Today, Discover, Content Detail, Practice Hub, My
Library, Collection, Word, Grammar Library, Progress, Profile, Settings, Search,
sheets), then the workspaces (Reader, Listening, Dictation, Speaking, Writing,
Review), the agent panel on the mock, onboarding, then the cutover.

Intelligence lane (`feature/orena-intelligence`): Slice 1b under D-085 against
`AGENT_CONTRACT.md` - router behind AGENT_ENABLED (off by default), turn SSE and
capabilities, Vocabulary and Writing read tools in EN and ZH, contract tests
S1, S5, S8, S9; no learner-UI redesign there.
