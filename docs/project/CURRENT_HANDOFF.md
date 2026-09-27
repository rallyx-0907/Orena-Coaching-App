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
and local verification are complete. Integration HEAD
`7565f6d921b22fe5562c963ce2f4f18b3e6deccf` was externally reviewed and merged
into `codex/work` through PR #63 at
`9c0fe315601877b43ac23aaffec915628635f9ae`.

## IN PROGRESS

`codex/work` is the unified baseline. D-085 opens the separate Orena
Intelligence lane; no Agent Intelligence implementation has been integrated
back into the baseline yet.

## PENDING

Create or fast-forward `feature/orena-intelligence` from the latest
`codex/work`, then develop and verify Agent Intelligence in that isolated
lane before any later integration review.

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

Start `feature/orena-intelligence` from the latest `codex/work` unified
baseline and keep Agent Intelligence work isolated there. Follow D-085: build
orchestration above existing domain services, expose only explicit allowlisted
capabilities, do not duplicate Reading/Listening/Speaking/Writing/Vocabulary/
Grammar/Progress backends, and do not redesign learner UI in this lane.
