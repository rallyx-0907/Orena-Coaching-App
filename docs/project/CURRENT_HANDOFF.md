# Current Handoff

## Governance

Purpose: current execution state only. Change when the active lane, verified
batch, gates or next task changes. Do not store secrets, product philosophy or
unverified claims. Product intent and technical authority follow
`PROJECT_MEMORY.md`; local verification does not imply CI pass, human product
approval, or production readiness.

## Current branch / lane

`codex/work` is the unified development baseline. The Admin + Speaking
integration was externally reviewed and merged by PR #63 at
`9c0fe315601877b43ac23aaffec915628635f9ae`, incorporating integration HEAD
`7565f6d921b22fe5562c963ce2f4f18b3e6deccf` over Codex `8557b0e`, with
`admin/control-center@e9a2219` and `feature/speaking@d006383` in its ancestry.

D-085 authorizes Orena Intelligence as a separate development lane from this
unified baseline. Agent Intelligence implementation belongs on
`feature/orena-intelligence`, not directly on `codex/work`.

D-086: the new learner UI replaces the old one on codex/work and is the only UI that carries the agent.
Both lanes build against `docs/project/AGENT_CONTRACT.md` (contract_version 1), edited only on `codex/work`.

**New learner UI migration (D-088 - D-091), in progress on `codex/work`.** The
design is Claude Design project `e6dc1cb2`, revision `1790473816124946`, pinned
in `docs/design/canonical-ui/screens/` (`SYNC_2026-09-27.md`). Strategy (D-091):
the new UI is built beside the old one and replaces it in one cutover. Between
slices `codex/work` is always in this state:

- `/` serves the **old** UI (Dark Glass), unchanged, with all its gates green;
- `/next` serves the **new** UI (`templates/orena/next.html`,
  `static/orena/main.js`, `shell/`, `kit/`, `screens/`, `copy/`, `agent/`),
  holding the surfaces listed under "New UI coverage" below;
- both import one domain layer (`product/`, `capabilities/`, `content/`,
  `infrastructure/`); no learner-data schema has changed;
- the agent panel exists only in the new UI and runs on the contract mock
  (AGENT_CONTRACT §11-12); nothing calls `/api/agent/*` until the human says the
  intelligence lane is integrated. A contract v2 proposal (Orena destination
  surface id, opening turn without a learner message) is awaiting the human's
  approval: `docs/project/AGENT_CONTRACT_V2_PROPOSAL.md`.

The intelligence lane integrates against `/next`. Frame → route → code → status
is in `docs/design/canonical-ui/IMPLEMENTATION_MAP.md`.

### New UI coverage

None yet: the design is pinned and the governance for it is recorded; the
foundation slice (tokens for both themes, icons, brand marks, primitives, shell,
router, copy mechanism, `/next`) is being built.

## Last verified batch

The unified local tree preserves Codex learner Reading and My Library on the
canonical Reading backend, Admin, Speaking, and D-079/D-080 language layers.
The duplicate generated Reading engine is removed. Decision IDs are Codex My
Library D-074, Speaking D-075–D-080 and D-084, and Admin D-081–D-083.

Local unified verification on 2026-09-26: full Linux pytest with isolated
PostgreSQL 16 `2472 passed, 3 skipped, 0 failed`; all 66 CI `.mjs` gates
passed; browser ESM graph passed with 121 modules; project-memory and
architecture validators passed. The listening catalog check skipped as
specified because its development snapshot is not committed. All 16 Alembic
revisions upgraded a fresh throwaway PostgreSQL database to sole head
`20260924_0016`. Browser checks on an isolated local app covered Reading,
Admin routes, Vocabulary, My Library, Speaking library, shadowing, free talk
error state, old practice route, language combinations A/B/C, and long content
at 390×844 and 1920×1080 without horizontal overflow. Live speech and AI
provider acceptance remains a separate human gate. No CI pass is claimed.

Visual-source gate: **PINNED** (2026-09-27). The design source (project
`e6dc1cb2`, revision `1790473816124946`) was read in full - through DesignSync
for every file under 256 KiB and from the human's export for `Orena.dc.html`,
whose first 256 KiB match the DesignSync read byte for byte - and pinned in
`docs/design/canonical-ui/`. Fidelity is judged per surface of the new UI
against that pin (`IMPLEMENTATION_MAP.md`); the old UI at `/` is not redesigned.

## DONE

Admin/canonical Reading merge checkpoint `ec7ac2897fb103a9f4a7898a6e256f351719e028`
received a PASS independent architecture delta review from GPT-6/Codex
(`/root/architecture_review`), with no P0/P1 findings. Reviewer identity,
commit and verdict are recorded in `ADAPTIVE_READING_ARCHITECTURE_REVIEW.md`.
The unified Speaking merge `5e3d53aa1ff6442ccf8ae0c21f84d9221116c339`
and local verification are complete. Integration HEAD
`7565f6d921b22fe5562c963ce2f4f18b3e6deccf` was externally reviewed and merged
into `codex/work` through PR #63 at
`9c0fe315601877b43ac23aaffec915628635f9ae`.

## IN PROGRESS

`codex/work` is the unified baseline. D-085 opens the separate Orena
Intelligence lane; no Agent Intelligence implementation has been integrated
back into the baseline yet.

`feature/orena-intelligence`: Slice 1a is REVIEWABLE (local verification,
2026-09-27) - `writing_coach/agent/` contracts, registries, fake provider and
voice interfaces, three `AIOperation` values; no router, no persistence, no
provider call. Human rulings R1-R7 are in `AGENT_SPEC.md` §0; the lane's gaps
are `UI_BACKEND_GAPS.md` I-1..I-21.

## PENDING

The four agent capability keys wait for their Admin console labels on
`codex/work` (I-17). Contract v2 (`AGENT_CONTRACT_V2_PROPOSAL.md`) awaits the
human; the intelligence lane adds it only after it merges forward.

## BLOCKED

Shared-runtime application of the new Reading migrations requires explicit
human authorization. The PostgreSQL rehearsal used throwaway containers and
no product volumes.

## OPEN P0

None identified in this integration batch.

## OPEN P1

See `ORENA_STATUS.md` and `UI_BACKEND_GAPS.md`; this integration does not
change product scope. No unified local verification gate is red.

## HUMAN GATES

Web is active; native mobile is frozen. PostgreSQL is the authoritative
runtime, SQLite only an isolated test or frozen rollback/archive backend.
My Library `20260923_0013` and Vocabulary Decks `20260923_0014` were
previously reviewed and applied to dev/sandbox only; that authorization
does not transfer to the renumbered Reading revisions. Production,
preview, provider credentials, OAuth/DNS/Cloudflare, billing, deployment,
and destructive lifecycle remain human gates. Never touch persistent
volumes as cleanup.

## NEXT EXACT TASK

On `codex/work` (UI lane): build the new UI's foundation slice under D-091 -
`kit/tokens.css` with both themes and the device variables, Lucide icons at the
pinned release, the brand marks, the primitives, the shell (rail, top bar, phone
header and bar, focus mode), the router with the design's routes, the copy
mechanism for en / vi / zh, and `/next` - then the surface slices listed in
`IMPLEMENTATION_MAP.md`, then the cutover.

On `feature/orena-intelligence`: human review of Slice 1a, then Slice 1b
(`AGENT_SPEC.md` §26): the agent router, `POST /api/agent/turn` (SSE) and
`GET /api/agent/capabilities`, two or three Vocabulary and Writing read tools
in EN and ZH, streaming and tool calls on the existing OpenAI-compatible
provider, contract tests S1, S5, S8, S9. No learner UI there.
