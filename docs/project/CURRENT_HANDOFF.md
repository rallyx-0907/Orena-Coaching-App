# Current Handoff

## Governance

Purpose: compact recovery context. Change when the active stage or verified
facts change. Do not store secrets or unverified claims. Authority: current
human instruction, Orena Constitution, Content Architecture, approved brand,
D-046. No human approval or production readiness is implied.

## Current branch / lane

`codex/work`, Orena WEB Golden Star plus real learning capabilities. Do not
restore the deleted learner product. Native mobile / Expo / React Native is
frozen. Human instruction authorizes full-stack WEB work on the capabilities
themselves, not only on the foundation.

## DONE

D-046 and the product reset are committed; the shared media, transcript,
dictation, recording, provider and evidence primitives survive, and the learner
surfaces converge on static/orena. PostgreSQL APIs remain.

Golden Star foundation: shared page intro, intention navigation, response
composer, continuation shelf, draft status, progressReporter(). Tinted panels
carry their own ink in both themes - the recurring defect is an ambient
colour outranking a component's own pairing. ORENA_WEB_EXTENSION_GUIDE.md
records what a surface inherits. `/orena-assets/*` revalidates by ETag; never
`no-store`, which re-downloaded 3.2 MB per refresh.

## Learning capabilities

Preserved Opus implementation; ORENA_STATUS and GOLDEN_STAR_COMPLETION hold
behavior and evidence. Current invariants/owners:

- Listening: ui/encounter.js; pure Follow, synchronized excerpt, pause on inquiry.
- Reading: content/reading.js readable contract; reading-library.js rights gate.
- Writing: ui/writing-review.js; exact submitted snapshot and grounded revision.
- Speaking: product/conversation.js; own turns, no absent-reference alignment.
- Grammar/Vocabulary: canonical Concept IDs and shared contextual explanation.
- Kept language: product/memory.js; provenance device sidecar after account save.
- Recall: product/recall.js; hidden answer, explicit reveal/self-assessment.
- Continue: ui/patterns.js and product/intent.js; actual work type and intention.
- Understanding: ui/understanding.js; exact context and stale-answer rejection.
- Presentation/brand: ORENA_WEB_EXTENSION_GUIDE; Opus owns theme/brand execution.

## Last verified batch

No CI/live-provider claim. R3 evidence hardening requires actionable evaluator
findings, exact strength/error quotes and readable EN/ZH categories. The 8011
browser now verifies EN and ZH Write → Evaluate degraded paths: the draft,
target and task remain intact, transient 503 feedback offers a working retry,
and each retry resubmits. Writing regression: 123 pytest; Writing Review,
Foundation and 51-module ESM gates passed. Prior Opus batch remains 799 passed /
20 inherited failures; its journey evidence lives in ORENA_STATUS and
GOLDEN_STAR_COMPLETION.

## Runtime / safety

Only operate isolated `orena-foundation-web` at 127.0.0.1:8011 and its own
`orena-foundation-postgres` / network. PGDATA is tmpfs: a reboot empties it;
`scripts/start_orena_sandbox.ps1` restores it. Restart after Python changes -
uvicorn does not reload. Do not operate production 8000, preview 8010,
Cloudflare or volumes. No provider keys: AI surfaces return 503 honestly.
Pronunciation may be demo-labelled. No microphone acceptance has run.

Dependency-heavy tests: `ai-writing-coach:local`, read-only repo, tmpfs /rundata,
four *_DB vars there; command in AGENTS.md. SQLite is test-only, never runtime.
Switch learning language in-page. Stage task files only, never visual references.

## NEXT EXACT TASK

Core lane (Codex scheduled R3): supplemental EN/ZH evaluator and degraded-state
checkpoint is REVIEWABLE. Representative live-provider quality and the final
Write → Evaluate → Review browser result require the provider/credential human
gate; deterministic fixtures must not be presented as that evidence.

Parallel Backbone lane (Opus): I2 write-path is BLOCKED (see below). I3
schema **proposed** (not applied): `migrations/proposed/20260911_0006` +
`commerce_repository.py`. Round 1 reviewed: CHANGES REQUESTED (3xP1, 1xP2),
all addressed (10/10 postgres cases, 60/60 flakiness runs) - see
`I3_SCHEMA_REVIEW_REQUEST.md`. Next: re-review; not self-approved/moved/
activated (AGENTS.md §1). Meanwhile started the next-named track (learner-
facing content/UI/EN-ZH parity): Discover's generated-fiction catalog grew
3 -> 4 with a new parity+schema gate (`test_orena_discover_texts.mjs`),
verified live. UI swept across 6+ rooms - clean; Platform Admin left alone
(architecture hold, not a bug). Also fixed: mobile nav dropdown was
unscrollable (`.nav-backdrop` z-index tied #shell's). I1's `Scope` still has
no production caller. Preserve A-D, eleven destinations and all active Opus
WIP; no I1-I7 claim implies human approval.

## IN PROGRESS

Golden Star is IMPLEMENTING. The three capability findings are closed.
The Encounter close-look WIP is finished and human-approved.

Packages A-D of `ORENA_REFERENCE_ARCHITECTURE.md` are done: late-answer
rejection, truthful capability outcomes, ten canonical journeys walked, and
continuation that keeps the learner's intention and stays device-honest.
Backbone contracts/pure policies are specified; runtime integration I1-I7 remains
Opus implementation work. F is human review, not architecture completion.

Multi-theme system implemented, awaiting visual review: Paper, Night Ink, Deep
Forest and Sage Field from a registry; identity separate from appearance;
colour owned solely by `theme.css`. Ember deferred. The brand asset set was
replaced and the runtime library remapped to it.

Backbone runs against locked GPT-6 architecture at `27edeb0`, in
`ORENA_BACKBONE_INTEGRATION_GATES.md` order. I1 done. I2's schema reviewed,
approved, applied to the **sandbox only** at `20260908_0005`, flag `off`
(trail: `I2_ACTIVATION_RUNBOOK.md` §6). Production/preview untouched.

D-049 (2026-09-12): Content Architecture amended - six canonical domains,
Understanding Engine, Language Knowledge Graph, Vocabulary Card + orthography.
New: `ORENA_UNDERSTANDING_ENGINE.md`, `ORENA_VOCABULARY_ARCHITECTURE.md`;
sequence in `ROADMAP.md`. Parallel to I1-I7, not a stage of it; any schema
still needs the I2/I3 review gate. Docs-only.

## PENDING

Microphone hardware and live-provider validation remain pending; injected
provider coverage does not establish live prompt quality.

## BLOCKED

I2 §6 step 9 (`ORENA_ACCOUNT_BACKBONE=on`) and every activation beyond it. Any
deploy to production 8000 or preview 8010 is a separate human gate, was not
authorized, and has not been asked for.

## OPEN P0

None identified.

## OPEN P1

- `#/language` renders "temporarily unavailable" only in long multi-room
  sweeps at short dwell (4/4@700ms/14 routes; 2/2@750ms/13 rooms); never
  isolated or at 300-2600ms; 0/130 before/after Package D. Self-recovers.
- Platform Admin lost its host when templates/index.html was removed; its APIs
  and static/admin.js remain but admin.js bails at its #page-admin guard.
  Preserve it without restoring the historical shell.
- Grammar breadth: authored patterns joined by stable Concept ID, extended by
  `grammar-shelf.js`, not a second syllabus.
- Cross-device continuity: device memory current; I2 schema/sync activation
  and its policy inputs remain gated.
- Reading/Vocabulary library breadth: rights gate per text (Reading); D-049
  content-domain sequence (Vocabulary Card, orthography) not yet implemented.
- Non-CI r8/r10/r11 matrices refer to deleted wrappers; r20 is frozen native.

## Baseline test evidence

20 Python failures are inherited (baselines 5827f6a, f966b28): same ones in
test_governance_contract.py, test_media_ingestion.py, test_media_learning.py.
Never claim an all-green suite.

## HUMAN GATES

Final browser review; production, data, migration, provider, credential,
OAuth/DNS/Cloudflare, billing and release operations; destructive history.
Local web iteration and checkpoint commits are authorized. Only the human
approves product direction.
