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
reproduced on clean `8557b0e`. Memory and architecture validators must
pass again after this handoff update before checkpoint commit. No CI pass is
claimed. The Claude Design source is unavailable; by explicit human
instruction its visual-source gate is UNVERIFIED and does not block branch
integration. Final visual verification is separate; do not redesign the UI.

## DONE

Admin/canonical Reading integration and Phase 2 local verification above.

## IN PROGRESS

Checkpoint this merge, obtain an independent architecture review of
the renumbered migrations against that commit, and record reviewer identity,
reviewed commit, and outcome in Git. Then integrate Speaking and run the full
unified gates. Do not apply new migrations to a shared runtime without
separate review and human authorization. The PostgreSQL rehearsal used
throwaway containers and no product volumes.

## PENDING

Speaking integration and unified branch verification after architecture review.

## BLOCKED

Shared-runtime application of the new Reading migrations pending independent
architecture review and explicit human authorization.

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

Commit the verified Admin merge, record an independent architecture review of
that commit, then integrate Speaking and run all unified gates. Stop on any
architecture blocker; do not merge into `codex/work` before human review.
