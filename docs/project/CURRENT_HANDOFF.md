# Current Handoff

## Governance

Purpose: current execution state only. Change when the active lane, verified
batch, gates or next task changes. Do not store secrets, product philosophy or
unverified claims. Product intent and technical authority follow
`PROJECT_MEMORY.md`; local verification does not imply CI pass, human product
approval, or production readiness.

## Current branch / lane

`codex/integrate-admin-speaking` in the existing `-codex` worktree, by explicit
human instruction. It integrates `admin/control-center@e9a2219` and
`feature/speaking@d006383` over Codex `8557b0e`. Push only this integration
branch for external review. Do not merge it into `codex/work` or `main`.

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

The Claude Design source is unavailable. By explicit human instruction, the
visual-source gate is **UNVERIFIED** and does not block branch integration;
final visual fidelity review is separate. Do not redesign the existing UI to
compensate for that unavailable source.

## DONE

Admin/canonical Reading merge checkpoint `ec7ac2897fb103a9f4a7898a6e256f351719e028`
received a PASS independent architecture delta review from GPT-6/Codex
(`/root/architecture_review`), with no P0/P1 findings. Reviewer identity,
commit and verdict are recorded in `ADAPTIVE_READING_ARCHITECTURE_REVIEW.md`.
The unified Speaking merge `5e3d53aa1ff6442ccf8ae0c21f84d9221116c339`
and local verification are complete; remote ref verification is the remaining
checkpoint step.

## IN PROGRESS

Checkpoint current memory, confirm ancestry and clean working tree, and push
only `codex/integrate-admin-speaking` after final gates remain green.

## PENDING

Human review of the pushed integration HEAD. Human approval is required before
any merge into `codex/work` or `main`.

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

Push the integration branch only, read back its exact remote HEAD, and present
the branch for external human review.
