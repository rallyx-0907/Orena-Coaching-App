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
carry their own ink in both themes, including secondary text on them - the
recurring defect is an ambient colour outranking a component's own pairing.
ORENA_WEB_EXTENSION_GUIDE.md records what a surface inherits.

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

Opus application evidence below is preserved, not rerun by Codex.
Local execution only; no CI claim.
- 32 CI Node gates PASS. ESM graph 51. Both validators OK. Four stdlib
  contract gates PASS.
- Full Python in the app image: 799 passed / 20 failed (see below). The rich
  provider paths run against an injected provider, mutation-checked.
- Browser at 390/800/1440/1920, EN and ZH, all themes: no overflow, no room
  repeating the practice map, no dead controls.
- Journeys: see the ledger's "Functional core" and "Reference architecture
  packages" for what is real, what is provider-held, and the evidence.

## Runtime / safety

Only operate isolated `orena-foundation-web` at 127.0.0.1:8011 and its own
`orena-foundation-postgres` / network; its database is temporary. Restart it
after Python changes - the worktree is mounted, uvicorn does not reload. Do not
operate production 8000, preview 8010, Cloudflare or volumes. No provider keys:
the AI surfaces return 503 honestly. Pronunciation may be demo-labelled. No
microphone acceptance has run; do not claim it.

Dependency-heavy tests: `ai-writing-coach:local`, read-only repo, tmpfs /rundata,
four *_DB vars there; command in AGENTS.md. SQLite is test-only, never runtime.
Switch learning language in-page. Stage task files only, never visual references.

## NEXT EXACT TASK

Continue the ORENA GOLDEN STAR reference under principal-architect ownership.
Read `docs/product/ORENA_REFERENCE_ARCHITECTURE.md` and
`docs/project/ORENA_BACKBONE_EXECUTION.md`; implementation order/acceptance lives
in `docs/project/ORENA_BACKBONE_INTEGRATION_GATES.md` (I1-I7).
The backbone covers account/profile, commerce/quotas, Collection, content/jobs,
Growth/achievements and cross-domain migration. It is not merely Package E.
Codex owns contracts and integration decisions; Opus owns feature/UI execution.
Backbone design is 8/8 with independent technical review and 18 local contract
tests; it does not claim I1-I7 runtime implementation or human product approval.
Start with I1 scoped profile/account adapters; schema/paid activation is gated.
Preserve A-D, eleven destinations and deferred Collection presentation.
Inspect live HEAD and WIP every cycle; all active Opus files/domains are reserved.

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
colour owned solely by `theme.css`. The first two are unchanged and no
component was touched. Ember deferred. The brand asset set was replaced and the
runtime library remapped to it.

Backbone implementation runs against the locked GPT-6 architecture at `27edeb0`
in the order `ORENA_BACKBONE_INTEGRATION_GATES.md` sets. I1 is done: server-owned
scope with an incarnation, settings as `{value, source, version}`, and a patch
changing only what it names against the version it read. I2 landed its
startup-schema fix. Its proposal at `69ceb53` was reviewed outside the
repository by a Delegated Independent Architecture Reviewer (ChatGPT GPT-5.6
Sol): APPROVED WITH REQUIRED CHANGES, nine recorded verbatim in
`I2_SCHEMA_REVIEW_REQUEST.md`. The migration stays in `migrations/proposed/`,
outside the live chain. Evidence: `ORENA_IMPLEMENTATION_LEDGER.md`.

## PENDING

Microphone hardware and live-provider validation remain pending; injected
provider coverage does not establish live prompt quality.

## BLOCKED

I2 §6 step 3 (apply the proposal to a throwaway database and run the
concurrency proof) until the revised proposal is re-reviewed.

## OPEN P0

None identified.

## OPEN P1

- `#/language` renders "temporarily unavailable" only inside a long multi-room
  sweep at short dwell (4/4 at 700ms/14 routes; 2/2 at 750ms/13 rooms). Never
  in isolation, from a single predecessor, or at 300-2600ms dwells; did not
  reproduce at all before or after Package D (0/130 twice). Self-recovers, no
  error captured. Needs a dedicated slice, not a speculative rewrite.
- Platform Admin lost its host when templates/index.html was removed; its APIs
  and static/admin.js remain but admin.js bails at its #page-admin guard.
- Grammar breadth: authored patterns joined by stable Concept ID, extended by
  `grammar-shelf.js`, not a second syllabus.
- Cross-device continuity: device memory remains current; account design is now
  specified, but schema/sync activation and policy inputs remain gated.
- Reading library breadth: contract, rights fields and admission gate exist;
  growing it is a rights decision per text. Without a provider the API returns
  one built-in passage per language, labelled.
- Non-CI r8/r10/r11 matrices refer to deleted wrappers; r20 is frozen native.

## Baseline test evidence

The 20 Python failures are inherited: baselines 5827f6a and f966b28 show the
same ones in test_governance_contract.py, test_media_ingestion.py and
test_media_learning.py (historical prose/source-format assertions). Never claim
an all-green suite.

## HUMAN GATES

Final browser review; production, data, migration, provider, credential,
OAuth/DNS/Cloudflare, billing and release operations; destructive history.
Local web iteration and checkpoint commits are authorized. Only the human
approves product direction.
