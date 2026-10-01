# Current Handoff

## Governance

Purpose: current execution state only. Change when the active lane, verified
batch, gates or next task changes. Do not store secrets, product philosophy or
unverified claims. Product intent and technical authority follow
`PROJECT_MEMORY.md`; local verification does not imply CI pass, human product
approval, or production readiness.

## Current branch / lane

`codex/work` is the baseline/UI lane (D-066, D-098) for either agent. `feature/orena-intelligence`
builds Agent Intelligence (D-085) against `AGENT_CONTRACT.md` v5 (D-092, D-094,
D-095, D-096), which is edited only on `codex/work`. Verified history:
`PROJECT_STATE.md` "New learner UI migration".

New learner UI (D-088 - D-091): the pinned design is built at `/next` and
replaces the old UI at `/` in one cutover. Between slices `/` is the old UI,
unchanged; `/next` holds the built surfaces; both share one domain layer; no
learner-data schema changes; the agent runs on the contract mock and nothing
calls `/api/agent/*` until the human says the intelligence lane is integrated.
The intelligence lane integrates against `/next`. Frame → route → code →
status: `docs/design/canonical-ui/IMPLEMENTATION_MAP.md`.

- Foundation: REVIEWABLE.
- Wave A destinations: REVIEWABLE (`f13c542`) - built, reviewed, integrated,
  re-checked in the browser, language layer finished, every API reader checked
  against captured real payloads (`scripts/fixtures/api/`). Reviewable at
  http://127.0.0.1:8021/next (isolated stack) until the 8011 sandbox is migrated.
- Lane runtime :8021 (D-111.7, durable QA store): `orena-next-verify-web` and `-worker` share the named
  volume `orena-next-verify-media` at `/lanedata` (media, reading assets, word audio/deep roots); `/rundata` is
  tmpfs for SQLite scratch only; `ORENA_ACCOUNT_BACKBONE=on` here only. Recreate copies env by name only.
- Wave B workspaces: REVIEWABLE (`161d917`), independently reviewed/fixed;
  route inventory in `IMPLEMENTATION_MAP.md`. Backend-less routes remain Coming
  soon; Orena uses the mock and Grammar waits for its canonical runtime.
- Agent UI side: contract v5 on the mock; Orena's entry points hide when the
  agent is absent.
- Grammar: Grammar Lab replaces R5 (D-100; PR #66 merged at `f86a2bf`). The two
  Grammar screens (frames 44 and 47) are built on the merged contract (`b83142d`,
  status building: no content until the lane's 13-point fixture, its PR B, is
  placed behind `product/grammar-source.js`; open items G-1..G-9 in
  UI_BACKEND_GAPS); its PR A
  patches the contract and adds the "Try it yourself" rule, and until then the
  card never concludes the pattern was used. `/api/grammar/v1/*` waits for its
  own architecture review.

## Last verified batch

2026-09-29, the D-098 batch (`5d9d64c`..`3f2cc23`), local: every node gate in
ci.yml (114), the browser ESM graph and the memory validator pass; each learner
change was checked in the browser on the isolated stack (en/vi/zh, both themes,
desktop and phone touch; the Settings picker at all four rule-49 sizes). Full
pytest on a clean export of `3f2cc23` (SQLite, CI backend): `2450 passed, 195 skipped`. The isolated stack
mounts the checkout read-only, so a real upload cannot be stored there; the
upload route is covered by `tests/test_media_learner_upload.py` (real WAV,
ffprobe) instead.

## DONE

Design pinned and governed (D-088 - D-093); foundation at `/next`; agent
contract v4 (D-095); copy engine fixes; Wave A destinations and Wave B
workspaces (REVIEWABLE); the Writing request minimum per learning language.
The D-098 and D-099 items (2026-09-29, `5d9d64c`..`b83142d`); commit list in
`PROJECT_STATE.md` "New learner UI migration".

## IN PROGRESS

- Product completion (D-110/D-111): `PRODUCT_COMPLETION_PLAN.md` owns the audit
  and slice order. At `88b1c81`, S4 Progress, S8a Books and S2 media have partial
  uncommitted work, not yet verified or REVIEWABLE.
- Books storage is resolved by the shared :8021 volume, without a code change.
  Old Alice assets are lost. Real rights-cleared EN/ZH book reimports still need
  chapter, lookup/save, notes, restart and cross-device resume verification.
- Human review of Wave A and Wave B.
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

Resume S4 Progress from the working tree: verify History, Speaking
Attempts/Summary, Overview, Rank and From Your Errors against server records,
EN/ZH and a fresh browser; checkpoint for human review. Activity counts do not
prove scores/mastery/ranks/awards. Finish S8a Books and S2 media as bounded
reviewable slices; no usable transcript means draft/processing, captions first,
ASR fallback within D-111.6 caps.

Then follow `PRODUCT_COMPLETION_PLAN.md` "Decisions applied": QA archive,
Admin Overview, canonical Grammar, validated Reading supply, Vocabulary/practice,
EN/ZH library bootstrap and ZH books. Agent remains gated; Grammar-specific
capability needs its runtime, but Grammar does not block the whole Agent.

D-110/D-111 supersede the older execution order. Edge hardening is secondary
unless data loss, security/ownership or normal journeys are affected. Local-only
imports are incomplete with account sync active. Client Dictation scores are
unverified. Preserve appropriate deleted-import history without source/annotations.

QA: :8021, exclusive Docker use. :8011 deferred; :8000 human-gated. No auto-merge
to main; tests/records alone do not prove public readiness.

Intelligence lane: D-085 against `AGENT_CONTRACT.md` v5; merge `codex/work` forward; its merged PR
is what switches `AGENT_LIVE` on :8011 (D-101 G).

## Grammar Lab (merged from `feature/grammar-lab`)

Offline Phase 0: `docs/grammar_lab/SPEC.md`, `grammar_lab/` (separate tests).
NEXT (D-111.4): review PR #67/#68/gates, build the approved Store/API and canonical
HSK/GF-based ZH generation/validation. Legacy R5 is reference, never a fallback.
