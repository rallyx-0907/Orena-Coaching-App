# Current Handoff

## Governance

Purpose: execution position. Change when work/gates change. Do not store secrets or unverified claims.
Authority: `PROJECT_MEMORY.md`. Local checks are not CI/product approval.

Product completion covers the full approved UI/spec capability and flow inventory.

Program: `ROADMAP.md` (D-113); R21/mobile/skill releases are historical.

## Current branch / lane

`codex/work` is the baseline/UI lane (D-066, D-098) for either agent. `feature/orena-intelligence`
builds Agent Intelligence (D-085) against `AGENT_CONTRACT.md` v5 (D-092, D-094,
D-095, D-096), which is edited only on `codex/work`. Verified history:
`PROJECT_STATE.md` "New learner UI migration".

Release (D-143): one UI; cutover done (`/` = learner UI, old UI deleted); schema via
`proposals/PRODUCTION_MIGRATION_PACK.md`; backbone off, invite-only; no new runtime.
:8000 staging (D-146): 0029, main-a2342e62.
Agent stays on the contract mock until Intelligence integration is authorized.
Frame/route/code/status: `docs/design/canonical-ui/IMPLEMENTATION_MAP.md`.

- Foundation/Wave A/B: REVIEWABLE; inventory in IMPLEMENTATION_MAP.md.
- QA :8021: durable PG volume `orena-next-verify-postgres`, schema `20261007_0029`. Media volume `orena-next-verify-media` at `/lanedata`; `/rundata` SQLite scratch
  only. Worker stopped. `ORENA_ACCOUNT_BACKBONE=on` here only. Recreate copies env by name.
- Wave B (`161d917`): REVIEWABLE; backend-less routes stay Coming soon,
  Orena uses the mock; Grammar waits for its canonical runtime.
- Orena agent LIVE on :8021 only (D-125, `AGENT_ENABLED=true`, Gemini flash-lite legacy
  selection); the client follows capabilities (404 hides Orena). ORENA_AGENT_LIVE_8021_CHECKPOINT.md.
- Grammar Lab replaces R5 (D-100, PR#66 `f86a2bf`); screens44/47 (`b83142d`)
  wait for canonical fixtures behind grammar-source.js. G-1..G-9: UI_BACKEND_GAPS.
  No false pattern-used claim. Store/API waits for architecture review.

## Last verified batch

D-124 vocabulary localization: CC-CEDICT+Unihan vendored (cost plan P1); ZH imports gain
pinyin/`en` meaning; read path by support language; source registry; zero provider calls.
Design/review: `proposals/VOCABULARY_LOCALIZATION.md` (+ .REVIEW); gaps VL-1..5.
S1 source admission (e74735b): READING_SOURCE_ADMISSION_CHECKPOINT.md; level/source breadth,
enrichment/questions/fidelity open. Preserve S3 a8e7914: VOCABULARY_COLLECTION_CHECKPOINT.md. Grammar deferred.

Grammar Store (#99): 0030 promoted (applied nowhere); backend+API in its own PR, real
595-point import rehearsed; UI wiring awaits the human. GRAMMAR_CONTENT_STORE.IMPLEMENTATION.md.

Admin REVIEWABLE: six areas, sandbox routing, imports/EN/ZH lookup (`2931823`);
Azure/Skin (`7857d43`) local125/Node/review pass. Azure browser evidence/limits:
AZURE_VISUAL_SKIN_BROWSER_CHECKPOINT.md. Existing EPUB evidence unchanged.

S6 (`71ddcd4`): REVIEWABLE; EN/ZH rights/publish/lifecycle and390x844 evidence:
S6_ADMIN_MEDIA_BROWSER_CHECKPOINT.md. QA archived; preserve this accepted slice.

S2 (`637d0b2`, D-116): EN/ZH desktop/390x844, translation and skill returns verified;
evidence/limits: S2_MEDIA_BASIC_BROWSER_CHECKPOINT.md. Listening `cab4773` preserved.

## DONE

Foundation/Wave A/B REVIEWABLE; history: PROJECT_STATE.md "New learner UI migration".

## IN PROGRESS

- Product completion (D-110–D-113): `ROADMAP.md` owns order; `PRODUCT_COMPLETION_PLAN.md` supplies
  audit/slice detail. S4 (`a15d3c2`) has testable server-backed Progress/Attempts/Summary/
  Errors; evidence and remaining fidelity gates: `docs/reviews/S4_PROGRESS_BROWSER_CHECKPOINT.md`.
  S2 media work is preserved. Full UI/spec + Intelligence (D-112) remain required.
- Books storage: resolved by shared :8021 volume; old Alice assets lost.
  S8a (`b7380b1`): body/count/Admin-link fixes; evidence: S8_BOOKS_BROWSER_CHECKPOINT.md.
  Finish EN/ZH continuity/fidelity; no full Books completion claim.
- Human review: Wave A/B.
- Chinese writing evaluator recall (`ZH_WRITING_EVALUATOR_RECALL.md`): fix (1) landed
  (`871e2b9`, v2.7), benchmark measures recall (`fa93601`); live run for (4) waits for the
  human's go (provider cost).
- H2 declared level: `proposals/DECLARED_LEVEL_STORAGE.md` reviewed APPROVE (`6c0db16`);
  waits for the human's approval and three confirmations. No code or migration yet.
- D4 (D-104/D-105): migrations 0017-0023, :8021 only; review APPROVE WITH CONDITIONS
  (`f30044a`); flag-on QA round 2 (`9a7b190`) six flows PASS. Open for the human: delete for
  an imported text, media-import bound. Before public release (D-143): ACCOUNT_RECORD_LIMITS, upload deletion/limits.

## PENDING

Human: none for :8011 (deferred, D-102);
PR67/68 independently reviewed and integrated; Grammar Store/API built, UI pending
(D-111.4). Upstream GitHub PR state is unverified; integration is local only.
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

D-129: Reading APPROVED; Listening VERIFIED (461d471). Speaking, Writing, Vocabulary, places, cross-skill: audited,
fixed, Reviewer-verified; human recording/AI/device check OK. Next: Onboarding (D-129 §2).

D-124: → vi policy open-dsl → vi.wiktionary (strict) → English labelled; built, NOT enabled
until the human grades docs/reviews/evidence/d124-vi. Licences page + THIRD_PARTY_NOTICES done.
S1 loaded on :8021: 30 EN + 22 ZH published, per-text credits on Licences (7cab797/f6c0724).
Next: comprehension sets (reading_generator unconfigured on :8021, needs human OK); S2 sources proposed.

Grammar remains deferred. Human2026-10-04 accepts Reading -> vocabulary
enrichment -> practice on publish -> Agent; Grammar later. Review bounded S1
source admission, then S3 vocabulary/context enrichment through existing owners.
Source/level breadth and S7 persisted questions remain open; no new learner schema.

Preserve Admin/Azure (`2931823`/`7857d43`); OpenAI operator acceptance remains.

Current phase: basic functional coverage first (human instruction, 2026-10-02).
Preserve accepted Books/Progress; do not reopen them or restart a full-app audit.
S2 basic Listening and S6 Admin media rights/publish are REVIEWABLE; stop deepening
those paths. My Library accepted. D-119 shared Compare and D-121 readiness repair:
retain their checkpoints. Prior EN86/ZH75 assessment retained; fresh take/full
fidelity/model pitch remain open: COMPARE_MODEL_BROWSER_CHECKPOINT.md.
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
DEFERRED by human2026-10-04 (D-111.4): Store migration proposal/review/rehearsal, then Store/API
and canonical HSK/GF generation/validation. Resolve proposed revision slot against
media metadata 0024 before promotion. Legacy R5 is reference, never a fallback.
