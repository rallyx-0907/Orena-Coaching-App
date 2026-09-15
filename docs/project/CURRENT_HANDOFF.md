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

Platform Admin has a host again via `#/admin` (`04a56c4`); human review
confirmed the UI matches Orena's design, resolving the "lost its host" P1.
APIs and `static/admin.js` stay preserved.

## Learning capabilities

Preserved Opus implementation; ORENA_STATUS and GOLDEN_STAR_COMPLETION hold
behavior and evidence. Current invariants/owners:

- Listening: ui/encounter.js; pure Follow, synchronized excerpt, pause on inquiry.
- Reading: content/reading.js readable contract; reading-library.js rights gate.
- Writing: ui/writing-review.js; exact snapshot and grounded revision; T12 evaluator in `c71c644`.
- Speaking: product/conversation.js; own turns, no absent-reference alignment.
- Grammar/Vocabulary: canonical Concept IDs and shared contextual explanation.
- Kept language: product/memory.js; provenance device sidecar after account save.
- Recall: product/recall.js; hidden answer, explicit reveal/self-assessment.
- Continue: ui/patterns.js and product/intent.js; actual work type and intention.
- Understanding: ui/understanding.js; exact context and stale-answer rejection.
- Presentation/brand: ORENA_WEB_EXTENSION_GUIDE; Opus owns theme/brand execution.

## Last verified batch

Gemini R3 4/4 EN/ZH/support pass; one transient miss passed on rerun. No CI claim.

## Runtime / safety

Operate only isolated `orena-foundation-web` at 8011 with its PG/network. It is
published on `0.0.0.0:8011` for private-LAN review; use Ethernet IPv4.
PGDATA is tmpfs; the start script restores it. Restart after
Python changes; uvicorn does not reload. Do not operate production 8000/preview
8010/Cloudflare/volumes. Loopback and LAN self-checks pass. Firewall was not
added from this non-elevated shell; if peer access is blocked, add TCP 8011
scoped to `LocalSubnet` from Administrator PowerShell. AI eval uses selected
local/provider credentials; ASR remains unconfigured.

Dependency-heavy tests: `ai-writing-coach:local`, read-only repo, tmpfs /rundata,
four *_DB vars there; command in AGENTS.md. SQLite is test-only, never runtime.
Runner note: app cwd is `/app` (not `/workspace`); image lacks pytest, so install
it only in the ephemeral gate. Switch learning language in-page; stage task files.

## NEXT EXACT TASK

Core: R3 + T15 Card human PASS. Vocabulary foundation/catalog/feed/save
handoff and Chinese orthography projection are implemented without a schema
change. The consolidated Vocabulary UX redesign is now
`READY_FOR_HUMAN_UX_REVIEW`: Overview, compact Library management, Daily Feed
discovery and focused Study share the canonical card/save/review path. Review
at `http://127.0.0.1:8011/#/language` or the machine LAN address on port 8011;
check EN/ZH and Chinese orthography across Discover/My Language.
D-051/D-052 UI and phone-density foundations are implemented and verified at
1024-1920/800/390/360 in EN/ZH; human review remains pending.

Backbone lane (Opus), D-054 delegation: D-054, 0006 (+`6c4131a`), 0007
approved by delegated review (`I3_SCHEMA_REVIEW_REQUEST.md`). Sandbox only:
chain `20260912_0007`, flag on, backbone `active` (runbook §7). Writing
drafts kept with the account there, human-approved by browser review
(`4e1f0a5`); billing/quota off. "Your growth" read glance in preferences
(I6, REVIEWABLE, not yet human-reviewed). Deletion gated (D-055). I4
`/api/collection`. Keep A-D, 11 destinations, Opus WIP; no I1-I7 claim
implies human approval.

## IN PROGRESS

Golden Star capability findings are closed; Packages A-D of
`ORENA_REFERENCE_ARCHITECTURE.md` are done. Backbone runtime integration I1-I7
remains Opus implementation work; F is human review, not architecture completion.

Multi-theme system implemented, awaiting visual review: Paper, Night Ink,
Deep Forest, Sage Field; identity separate from appearance; colour owned
solely by `theme.css`. Ember deferred; brand assets replaced, runtime remapped.

Backbone runs against locked GPT-6 architecture at `27edeb0`, in
`ORENA_BACKBONE_INTEGRATION_GATES.md` order. I1 done. I2's schema reviewed,
approved, applied to the **sandbox only** at `20260908_0005`, flag `off`
(trail: `I2_ACTIVATION_RUNBOOK.md` §6). Production/preview untouched.

D-049/D-050 (2026-09-12): Content Architecture amended to five domains, a
horizontal Understanding Engine (AI-first, context-grounded, optional support
layer), Vocabulary Card + orthography. New: `ORENA_UNDERSTANDING_ENGINE.md`,
`ORENA_VOCABULARY_ARCHITECTURE.md`; sequence in `ROADMAP.md`. Docs-only.

Vocabulary UX `639b03d`: EN/ZH cards show real proficiency levels only; CEFR
B2/C1/C2 and HSK3–HSK7-9 cover high-level skins. Pronunciation/examples,
contained review status, and metallic frame verified. Human UX pending; no
schema change.

## PENDING

R3 Gemini live gate verified 4/4 representative EN/ZH/support-language cases
with native structured output, grounded evidence, valid levels and script
separation. The Ollama fallback remains a lower-quality local option: `qwen3:8b`
intermittently leaks target script in nested support explanations.

## BLOCKED

I2 §6 step 9 (`ORENA_ACCOUNT_BACKBONE=on`) is done, sandbox only (chain
`20260912_0007`, runbook §7). Production/preview deploy and activation past
sandbox stay blocked: separate human gate, not authorized, not asked for.

## OPEN P0

None identified.

## OPEN P1

- `#/language` renders "temporarily unavailable" only in long multi-room
  sweeps at short dwell (4/4@700ms; 2/2@750ms); never isolated (0/130).
  Self-recovers.
- Grammar breadth: patterns joined by stable Concept ID, extended by
  `grammar-shelf.js`, not a second syllabus.
- Cross-device continuity: device memory current; I2 schema/sync activation
  remains gated.
- Reading breadth: rights gate. Vocabulary Library/Feed and Chinese orthography
  are technically reviewable at the checkpoint above; human UX acceptance is
  still pending.
- Non-CI r8/r10/r11 pre-public matrices were retired per product decision;
  r20 remains frozen native.
- Language coherence: interface is en/zh; evaluator/grammar explanations follow
  the support language (12; sandbox profile vi) - EN/ZH labels over VI text is a
  product decision (more interface locales, or explain in UI language).

## Baseline test evidence

Baseline suite now passes locally with `997 passed, 107 skipped, 4 warnings`;
this is not a CI claim. Inherited governance/media failures were reconciled
against the current architecture; retired legacy matrix tests are not regressions.

## HUMAN GATES

Final browser review; production, data, migration, provider, credential,
OAuth/DNS/Cloudflare, billing and release operations; destructive history.
Local web iteration and checkpoint commits are authorized. Only the human
approves product direction.
