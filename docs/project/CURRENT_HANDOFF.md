# Current Handoff

## Governance

Purpose: current execution state only. Change when the active lane, verified
batch, gates or next task changes. Do not store secrets, product philosophy or
unverified claims. Product intent and technical authority follow
`PROJECT_MEMORY.md`; no human product approval or production readiness is implied.

## Current branch / lane

`codex/integrate-admin-speaking` in the existing `-codex` worktree, by
explicit human instruction. Base `codex/work@8557b0e`; integrate
`admin/control-center@e9a2219`, then `feature/speaking@d006383`.
Do not merge into `codex/work` or `main` before human review.
This task preserves the existing learner UI and does not start the new Orena UI,
a Grammar engine, native mobile work, or a product-direction change.

## Last verified batch

Phase 1 Admin/canonical Reading is implemented in the integration working
tree. The linear Alembic chain runs through My Library `20260923_0013`,
Vocabulary Decks `20260923_0014`, Reading Content Engine
`20260924_0015`, and Adaptive Reading `20260924_0016`.
Admin decision IDs are D-081–D-083; Speaking retains D-075–D-080.
Codex learner Reading keeps its per-question feedback UI and library
capabilities on the canonical Reading backend. The duplicate generated
Reading engine is removed.

Phase 2 local evidence on this working tree: full Linux pytest using an
isolated PostgreSQL 16 container `2411 passed, 3 skipped, 0 failed`;
focused PostgreSQL Reading rehearsal `120 passed, 2 skipped`;
browser ESM graph passed. The CI .mjs sweep has one inherited failure:
`test_m3_pronunciation_contract.mjs` at its first `/82/` assertion,
reproduced on clean `8557b0e`. Memory and architecture validators passed
before checkpoint commit. No CI pass is
claimed. The Claude Design source is unavailable; by explicit human
instruction its visual-source gate is UNVERIFIED and does not block branch
integration. Final visual verification is separate; do not redesign the UI.

## DONE

Admin/canonical Reading integration and Phase 2 local verification above.
The checkpoint merge `ec7ac2897fb103a9f4a7898a6e256f351719e028`
received a PASS independent architecture delta review from GPT-6/Codex
(`/root/architecture_review`), with no P0/P1 findings. Reviewer identity,
commit and verdict are recorded in `ADAPTIVE_READING_ARCHITECTURE_REVIEW.md`.
Two P2 runbook corrections followed review.

## IN PROGRESS

Integrate Speaking and run the full unified gates. Applying new migrations
to a shared runtime still needs explicit human authorization. The PostgreSQL
rehearsal used throwaway containers and no product volumes.

## PENDING

Human review of the final integration branch after unified verification.

## BLOCKED

Shared-runtime application of the new Reading migrations pending explicit
human authorization.

## OPEN P0

None identified in this integration batch.

## OPEN P1

See `ORENA_STATUS.md` and `UI_BACKEND_GAPS.md`; this integration does not change
product scope. The inherited pronunciation contract gate remains red.

## HUMAN GATES

Web is active; native mobile is frozen. PostgreSQL is the authoritative
runtime, SQLite only an isolated test or frozen rollback/archive backend.
My Library `20260923_0013` and Vocabulary Decks `20260923_0014` were
previously reviewed and applied to dev/sandbox only; that authorization
does not transfer to the renumbered Reading revisions. Production,
preview, provider credentials, OAuth/DNS/Cloudflare, billing, deployment,
and destructive lifecycle remain human gates. Never touch persistent
volumes as cleanup. Open product P1s remain in `ORENA_STATUS.md` and
`UI_BACKEND_GAPS.md`; do not resolve them as part of this integration.

## NEXT EXACT TASK

Integrate Speaking and run all unified gates. Stop on any
architecture blocker; do not merge into `codex/work` before human review.
