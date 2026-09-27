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
against `docs/project/AGENT_CONTRACT.md` (contract_version 4, D-092, D-094, D-095),
edited only on `codex/work`.

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
  to the design's shell; the router with all 48 routes (unbuilt ones show the
  design's Coming soon); copy in en / vi / zh by layer, one copy engine
  (placeholders and plural forms, `test_orena_copy_engine`). Gates
  `test_orena_kit`, `test_orena_shell`, `test_orena_copy`. Colour contrast N-8
  is settled by D-093.
- **Wave A destinations (IMPLEMENTING - built, reviewed, integrated; browser
  re-check pending):** Today, Discover, Content Detail, Practice Hub, My
  Library, Collection Detail, Word Detail (with the stroke sheet), Grammar
  Library, Grammar Concept, Progress, Profile, Settings, Search, and the Import
  and Notifications sheets (the bell opens Notifications), on shared components
  (`kit/components.js`). Each surface was built from its frame, measured,
  verified in the browser against the isolated app on :8021 in en / vi / zh and
  both themes, and reviewed by an independent agent whose findings were fixed;
  an integration pass then removed the per-screen copy workarounds, closed the
  shared-kit fidelity gaps and wired the shell, CI and docs. Gates
  `test_orena_screen_*`, `test_orena_components`. The browser re-check of the
  integrated tree is pending: Docker stopped during the integration pass and
  the isolated app could not run. Backend gaps and the open design questions:
  `UI_BACKEND_GAPS.md` section N.
- **Agent (contract v4, D-095):** the transport answers every §2.1 status;
  hiding the shell's Orena entry points when the agent is absent is not wired
  yet (with the Orena panel, Wave B).
- **Next:** Wave B - the learning workspaces (reading, listening, dictation,
  speaking, writing, review), the Orena panel on the mock, onboarding.

## Last verified batch

2026-09-27, Wave A destinations integrated, local: all 85 CI `.mjs` gates and
the browser ESM graph (188 modules) pass on the working tree, with the
memory/architecture validators. `test_orena_vocabulary_theme_tokens.mjs`, which
CI does not run, fails identically on a clean `HEAD` (an old-UI gate for a
retired vocabulary CSS scope; to be replaced at the cutover, not deleted). The
integrated tree's browser re-check is pending (Docker down). No CI pass is
claimed.

2026-09-27, new UI foundation, local: all 69 CI `.mjs` gates, the browser ESM
graph, route tests and the memory/architecture validators pass; the shell
measured against the pinned frame at 1440x900, checked at 390x844, in en / vi /
zh and both themes. `test_orena_reading_library` and
`test_orena_writing_workspace` used to fail on Windows checkouts: the cause was
CRLF in the working tree against line-oriented gate patterns, fixed at the
repository level by `.gitattributes` (source text LF in every checkout); the
gates are unchanged. No CI pass is claimed.

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

## PENDING

Human action: the sandbox migration (BLOCKED below).

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

See `AGENT_SPEC.md` §0 (D-085).

## NEXT EXACT TASK

UI lane (`codex/work`): build the surface slices of `IMPLEMENTATION_MAP.md` on
the foundation - destinations (Today, Discover, Content Detail, Practice Hub, My
Library, Collection, Word, Grammar Library, Progress, Profile, Settings, Search,
sheets), then the workspaces (Reader, Listening, Dictation, Speaking, Writing,
Review), the agent panel on the mock, onboarding, then the cutover.

Intelligence lane (`feature/orena-intelligence`): Agent Intelligence under
D-085 against `AGENT_CONTRACT.md`; no learner-UI redesign there.

## Grammar Lab (merged from `feature/grammar-lab`)

Phase 0 of `docs/grammar_lab/SPEC.md`: an isolated, offline, file-based content
pipeline in `grammar_lab/` (own `pyproject.toml`, own tests) and
`docs/grammar_lab/`. It does not import app code, the app does not import it,
and app CI does not collect its tests; no app code, router, engine, migration or
runtime is involved. NEXT: human review of `docs/grammar_lab/PHASE0_DECISIONS.md`
(including how lab point IDs join the R5 Concept IDs, SPEC §8); phase 1 waits.
