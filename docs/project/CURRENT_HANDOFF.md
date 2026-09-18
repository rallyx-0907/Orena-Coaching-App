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

Platform Admin has a host via `#/admin` (`04a56c4`), human-reviewed.

## Learning capabilities

Preserved Opus implementation; ORENA_STATUS and GOLDEN_STAR_COMPLETION hold
behavior and evidence. Current invariants/owners:

- Listening: ui/encounter.js; pure Follow, synchronized excerpt, pause on inquiry.
- Reading: content/reading.js readable contract; reading-library.js rights
  gate; ui/reader.js adds paragraph meaning and never-AI word lookup.
- Writing: ui/writing-review.js; exact snapshot and grounded revision; T12 evaluator in `c71c644`.
- Speaking: product/conversation.js; own turns, no absent-reference alignment.
- Grammar/Vocabulary: canonical Concept IDs and shared contextual explanation.
- Kept language: product/memory.js; provenance device sidecar after account save.
- Recall: product/recall.js; hidden answer, explicit reveal/self-assessment.
- Continue: ui/patterns.js and product/intent.js; actual work type and intention.
- Understanding: ui/understanding.js; exact context and stale-answer rejection.
- Presentation/brand: ORENA_WEB_EXTENSION_GUIDE; Opus owns theme/brand execution.

## Last verified batch

D-057, then the surfaces under it. `ART_BIBLE.md` joins `assets/brand/orena/`;
`ui/cover.js` draws one deterministic cover per item, retiring the letter and
waveform placeholders product-wide. Discover opens on one action, shelved by
content. Continue reads as continuity: a chapter shown as a chapter of its
book, place and percent carried on the memory entry. Reading opens on the
library, cover-first, with a Continue reading shelf and search folded into a
utility; book detail leads with cover, one action and the current chapter.
Reader: `reader.css` exists (the room had none), so text keeps a measure and
the shell recedes. Its interaction layer is `ui/lexical.js`, shared with the
Listening transcript and the practised line. Listening opens on covers, shelves
from real data, place in the shared continuation field.
Listening opens on a learning stage: spoken line first, three toggles, one POS
legend on request, Replay/Practice/More, transcript as context. Dictation hides
the writing response. Speaking is a module with its own landing. Mic readiness
shows the real device and level. A synthetic or recogniser result is never
rendered as a pronunciation score. Fixed: the library rendered raw catalogue rows, so every
card linked to an encounter with no id and the room fell back to Reading. `listeningItem()` is the
one identity boundary now, an unclassifiable encounter keeps the learner's
domain, and the failure state is compact and domain-aware.

Verified: pytest `1109 passed, 118 skipped`, all 45 CI `.mjs` gates, ESM graph,
both validators, EN/ZH browser pass on `orena-foundation-web`:8011 at desktop
and 390px. No CI claim.

## Runtime / safety

Operate only isolated `orena-foundation-web`:8011 with its PG/network,
published on `0.0.0.0:8011` for private-LAN review via Ethernet IPv4.
PGDATA is tmpfs; the start script restores it. Restart after Python
changes; uvicorn does not reload. Do not operate production 8000/preview
8010/Cloudflare/volumes. Loopback/LAN checks pass; if a peer cannot reach it,
open TCP 8011 to `LocalSubnet` from an elevated shell. AI eval uses selected
local/provider credentials; ASR unconfigured.

Dependency-heavy tests use the read-only `ai-writing-coach:local` recipe in
AGENTS.md; SQLite is test-only. Switch language in-page.

## NEXT EXACT TASK

Core: R3/T15 Card human PASS. Vocabulary foundation/catalog/feed/save and
Chinese orthography are schema-free. Vocabulary Source Import is E2E through
Admin preview/mapping/import and learner collection/card projections. Review
approved; remaining Vocabulary gate is human schema/runtime authorization for
`20260916_0008`, then PostgreSQL rehearsal. Browser review at
`:8011/#/language`; check EN/ZH and Chinese orthography.

Backbone lane (Opus), D-054 delegation: D-054, 0006 (+`6c4131a`), 0007 approved
by delegated review (`I3_SCHEMA_REVIEW_REQUEST.md`). Sandbox only: chain
`20260912_0007`, flag on, backbone `active` (runbook §7). Writing drafts kept
with the account there, human-approved (`4e1f0a5`); billing/quota off. "Your
growth" glance in preferences (I6, REVIEWABLE, not human-reviewed). Deletion
gated (D-055). I4 `/api/collection`. Keep A-D, 11 destinations, Opus WIP; no
I1-I7 claim implies human approval.

## IN PROGRESS

Golden Star findings closed; Packages A-D of `ORENA_REFERENCE_ARCHITECTURE.md`
done. Backbone I1-I7 remains Opus work; F is human review.

Multi-theme awaiting visual review: Paper, Night Ink, Deep Forest, Sage Field;
colour owned by `theme.css`. Ember deferred.

Backbone runs against locked GPT-6 architecture at `27edeb0`, in
`ORENA_BACKBONE_INTEGRATION_GATES.md` order. I1 done. I2 schema approved,
sandbox only at `20260908_0005`, flag `off` (`I2_ACTIVATION_RUNBOOK.md` §6).

Source Import: UTF-8 mapping, normalization, identity, provenance, batch
results, shared repository, Admin UI, learner cards; APPROVED (`a1a90b7b`).
Schema auth pending; import fail-closed.

## PENDING

R3 Gemini live gate passed 4/4 EN/ZH/support with native structured output,
grounded evidence and script separation. Ollama stays a lower-quality local
option: `qwen3:8b` leaks target script in nested support explanations.

## BLOCKED

I2 §6 step 9 (`ORENA_ACCOUNT_BACKBONE=on`) is done, sandbox only (chain
`20260912_0007`, runbook §7). Production/preview deploy and activation past
sandbox stay blocked: separate human gate, not authorized, not asked for.

## OPEN P0

None identified.

## OPEN P1

- `#/language` renders "temporarily unavailable" only in long multi-room sweeps
  at short dwell (4/4@700ms; 2/2@750ms); never isolated (0/130). Self-recovers.
- Grammar breadth: patterns joined by stable Concept ID, extended by
  `grammar-shelf.js`, not a second syllabus.
- Cross-device continuity: device memory current; I2 schema/sync activation
  remains gated.
- Reading breadth: rights gate. Vocabulary Library content is gated until a
  complete pack is authored/published; Feed and Chinese orthography remain
  technically reviewable. Human UX acceptance is still pending.
- Non-CI r8/r10/r11 pre-public matrices were retired per product decision;
  r20 remains frozen native.
- Language coherence: interface is en/zh; evaluator/grammar explanations follow
  the support language (12; sandbox vi) - EN/ZH labels over VI text is a product
  decision (more interface locales, or explain in UI language).

## Baseline test evidence

Baseline suite now passes locally with `1109 passed, 118 skipped, 4 warnings`;
this is not a CI claim. Inherited governance/media failures were reconciled
against the current architecture; retired legacy matrix tests are not regressions.

## HUMAN GATES

Final browser review; production, data, migration, provider, credential,
OAuth/DNS/Cloudflare, billing and release operations; destructive history.
Local web iteration and checkpoint commits are authorized. Only the human
approves product direction.
