# Current Handoff

## Governance

Purpose: execution position. Change when work/gates change. Do not store secrets or unverified claims.
Authority: `PROJECT_MEMORY.md`. Local checks are not CI/product approval.

Product completion is judged against the full new Orena UI/spec capability and flow inventory, not only currently implemented backend features or the next active slices.

Current program: `ROADMAP.md` (D-113). R21/mobile and separate skill releases are historical.

## Current branch / lane

`codex/work` is the baseline/UI lane (D-066, D-098) for either agent. `feature/orena-intelligence`
builds Agent Intelligence (D-085) against `AGENT_CONTRACT.md` v5 (D-092, D-094,
D-095, D-096), which is edited only on `codex/work`. Verified history:
`PROJECT_STATE.md` "New learner UI migration".

New UI (D-088..D-091): `/next` replaces `/` in one cutover; both share domains.
Agent stays on the contract mock until Intelligence integration is authorized.
Frame/route/code/status: `docs/design/canonical-ui/IMPLEMENTATION_MAP.md`.

- Foundation/Wave A/B: REVIEWABLE; inventory in IMPLEMENTATION_MAP.md.
- QA :8021: web uses durable PG volume `orena-next-verify-postgres` (schema0023); old
  ephemeral PG retained, old QA records lost. Media volume `orena-next-verify-media` at
  `/lanedata`; `/rundata` SQLite scratch only. Worker stopped. `ORENA_ACCOUNT_BACKBONE=on`
  here only. Recreate copies env by name only. Recovery authorized 2026-10-03.
- Wave B (`161d917`): REVIEWABLE; backend-less routes stay Coming soon,
  Orena uses the mock; Grammar waits for its canonical runtime.
- Agent UI side: contract v5 on the mock; Orena's entry points hide when the
  agent is absent.
- Grammar Lab replaces R5 (D-100, PR#66 `f86a2bf`); screens44/47 (`b83142d`)
  wait for canonical fixtures behind grammar-source.js. G-1..G-9: UI_BACKEND_GAPS.
  No false pattern-used claim. Store/API waits for architecture review.

## Last verified batch

Pronunciation entry/phone correction (D-122): ready content chooser, direct practice,
source/segment reuse, readable sentence and Hear/Record within phone viewport.
EN/ZH/VI and zero preparation POSTs verified; D-121 preserved.
Evidence: docs/reviews/PRONUNCIATION_ENTRY_PHONE_CHECKPOINT.md.
Next: human review, then Product Completion; native remains frozen.

Admin REVIEWABLE: six areas, sandbox routing, imports/EN/ZH lookup (`2931823`);
Azure/Skin (`7857d43`) local125/Node/review pass. Azure browser evidence/limits:
AZURE_VISUAL_SKIN_BROWSER_CHECKPOINT.md. Existing EPUB evidence unchanged.

S6 (`71ddcd4`): REVIEWABLE. EN/ZH rights review -> Publish -> Listening with VI
meanings; reload/restart, withdrawal/Archive/Restore, 390x844 verified. Atomic
rights gates and held-transcript resolver fixed. Local Python260, Ruff/Node/ESM,
independent review pass. QA archived. Evidence: S6_ADMIN_MEDIA_BROWSER_CHECKPOINT.md.

S2 corrections (`637d0b2`, D-116): EN/ZH desktop/390x844, ZH 89/89 VI meanings
after reload/restart, Dictation/Shadowing return, playback chrome, word audio and
directional strokes verified on :8021. Orena AI copy supersedes paid-resource wording.
Prior tests/timing/level limitations: S2_MEDIA_BASIC_BROWSER_CHECKPOINT.md.

## DONE

Design pinned and governed (D-088 - D-093); foundation at `/next`; agent
contract v4 (D-095); copy engine fixes; Wave A destinations and Wave B
workspaces (REVIEWABLE); the Writing request minimum per learning language.
Historical D-098/D-099 commits: `PROJECT_STATE.md` "New learner UI migration".

## IN PROGRESS

- Product completion (D-110–D-113): `ROADMAP.md` owns order; `PRODUCT_COMPLETION_PLAN.md` supplies
  audit/slice detail. S4 (`a15d3c2`) has testable server-backed Progress/Attempts/Summary/
  Errors; evidence and remaining fidelity gates: `docs/reviews/S4_PROGRESS_BROWSER_CHECKPOINT.md`.
  S2 media work is preserved. Full UI/spec + Intelligence (D-112) remain required.
- Books storage: resolved by shared :8021 volume; old Alice assets lost.
  S8a (`b7380b1`): EPUB body/count and Admin learner-link fixes; local Python
  2726 pass/370 skip, independent code APPROVE. Browser evidence: `S8_BOOKS_BROWSER_CHECKPOINT.md`.
  Finish EN/ZH continuity/fidelity; no full Books completion claim.
- Human review: Wave A/B.
- Chinese writing evaluator recall: causes and fix options in
  `ZH_WRITING_EVALUATOR_RECALL.md`; no change until the human chooses a fix.
- H2, the declared level: `proposals/DECLARED_LEVEL_STORAGE.md`, independently
  reviewed (APPROVE at `6c0db16`, review in the same folder); waits for the
  human's approval and three confirmations. No code or migration yet.
- Chinese evaluator: fix (1) landed (`871e2b9`, contract v2.7) and the benchmark
  measures recall (`fa93601`, v2); the live run that gives (4) its numbers waits
  for the human's go (provider cost).
- D4 (D-104/D-105): code and migrations 0017-0023 on `codex/work`, applied to :8021 only; independently reviewed (LEARNER_RECORDS_D4_IMPLEMENTATION_REVIEW.md: delta APPROVE WITH CONDITIONS, `f30044a`). `ORENA_ACCOUNT_BACKBONE` on at :8021 only; flag-on browser QA round 2 at `9a7b190`: all six flows PASS. Open for the human: delete for an imported text (design draws none), media-import bound. Before :8000: ACCOUNT_RECORD_LIMITS rev 3 (approved with conditions, not built), upload media deletion (D-055(b)), code+schema one deployment unit. Admin slices 1-4 in /next; Grammar store waits for PR #67.

## PENDING

Human: none for :8011 (deferred, D-102);
Independent review/gates for PR #67 (`pattern_rule`) and #68 (fixtures) from
the Grammar Lab lane, then the approved canonical Grammar Store/API (D-111.4).
Architecture approval is not evidence that the runtime already exists.

## BLOCKED

- None for the UI lane. (:8011 stays at `20260923_0014`, deployment deferred by D-102.)
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

Preserve Admin/Azure (`2931823`/`7857d43`); OpenAI operator acceptance remains.

Current phase: basic functional coverage first (human instruction, 2026-10-02).
Preserve accepted Books/Progress; do not reopen them or restart a full-app audit.
S2 basic Listening and S6 Admin media rights/publish are REVIEWABLE; stop deepening
those paths. My Library accepted. D-119 shared Compare and D-121 readiness repair:
review the bounded correction above, then resume basic coverage. Prior EN86/ZH75
assessment retained; fresh take/full fidelity and optional model pitch remain open.
Historical evidence: COMPARE_MODEL_BROWSER_CHECKPOINT.md.
Preserve S6/control plane. Azure review passes; mobile unverified.
Basic coverage first; ASR within D-111.6 caps.

Follow `ROADMAP.md` and D-110..D-114 for remaining coverage, evidence and gates.
Agent remains gated; Grammar-specific capability needs its canonical runtime.

QA: :8021 only. :8011 deferred; :8000 human-gated. No auto-merge
to main; tests/records alone do not prove public readiness.

Intelligence lane: D-085 against `AGENT_CONTRACT.md` v5; merge `codex/work` forward; its merged PR
is what switches `AGENT_LIVE` on :8011 (D-101 G).

## Grammar Lab (merged from `feature/grammar-lab`)

Offline Phase 0: `docs/grammar_lab/SPEC.md`, `grammar_lab/` (separate tests).
NEXT (D-111.4): review PR #67/#68/gates, build the approved Store/API and canonical
HSK/GF-based ZH generation/validation. Legacy R5 is reference, never a fallback.
