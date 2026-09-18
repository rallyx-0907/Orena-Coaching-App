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
surfaces converge on `static/orena`. PostgreSQL APIs remain.

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

D-057 and the surfaces under it: `ART_BIBLE.md` in `assets/brand/orena/`;
`ui/cover.js` draws one deterministic cover per item. Discover opens on one
action; Continue reads as continuity, place and percent on the memory entry.
Reading opens on the library, cover-first; `reader.css` gives the text a
measure and `ui/lexical.js` is its interaction layer, shared with the transcript
and the practised line. Listening is a two-pane workspace: media
left, transcript right, the spoken line IS the active row - no duplicated stage.
Dictation hides the writing response. Speaking is a composed module, not a card
wall. Mic readiness shows the real device; a synthetic or recogniser result is
never a pronunciation score.

Correction batch on it (D-051 rules 23-26): the active row no longer
restructures. Every row carries when/line/reading/meaning; which show is a
panel preference, so a change of line alters only what a row says and how it is
drawn - verified by real playback of a whole lesson, row heights, offsets, list
height and controls per row constant. The row's actions moved to
`ui/learning-toolbar.js`: a shared icon-first bar whose menus are placed by
measurement and become a sheet on a phone. Dictation binds the player to the
line being written (`holdSegment`), so every way of starting playback stops at
that line; leaving is a cross in the chrome, and Previous/Next plus a segment
strip stay inside the mode. A supported locale owns every string its surfaces
ask for: `copy.vi` and `referenceCopy.vi` are complete for en/zh/vi,
`untranslated()` records a shortfall, the shell warns on the console, and the
gate fails on silent English, families composed at the point of use
(`topic_`, `pos_`, `rubric_`) included.

Verified: pytest `1109 passed, 118 skipped`, all 48 CI `.mjs` gates, ESM graph,
both validators, and the Python CI validators. Browser pass on
`orena-foundation-web`:8011 for vi/en, zh/en and vi/zh at desktop and 390px. No
CI claim.

## Runtime / safety

Operate only isolated `orena-foundation-web`:8011 with its PG/network,
published on `0.0.0.0:8011` for private-LAN review. PGDATA is tmpfs; the start
script restores it. Restart after Python changes; uvicorn does not reload. Do
not operate production 8000/preview 8010/Cloudflare/volumes. If a peer cannot
reach it, open TCP 8011 to `LocalSubnet` from an elevated shell. AI eval uses
selected local/provider credentials; ASR unconfigured.

Dependency-heavy tests use the read-only `ai-writing-coach:local` recipe in
AGENTS.md; SQLite is test-only. Switch language in preferences.

## NEXT EXACT TASK

Core: R3/T15 Card human PASS. Vocabulary foundation/catalog/feed/save and
Chinese orthography are schema-free. Vocabulary Source Import is E2E through
Admin preview/mapping/import and learner collection/card projections. Review
approved; the remaining Vocabulary gate is human schema/runtime authorization
for `20260916_0008`, then PostgreSQL rehearsal. Browser review at
`:8011/#/language`.

Backbone lane (Opus), D-054 delegation: D-054, 0006 (+`6c4131a`), 0007 approved
by delegated review (`I3_SCHEMA_REVIEW_REQUEST.md`). Sandbox only: chain
`20260912_0007`, flag on, backbone `active` (runbook §7). Writing drafts kept
with the account there, human-approved (`4e1f0a5`); billing/quota off. "Your
growth" in preferences (I6, REVIEWABLE, not human-reviewed). Deletion gated
(D-055). I4 `/api/collection`. No I1-I7 claim implies human approval.

## IN PROGRESS

Golden Star findings closed; Packages A-D of `ORENA_REFERENCE_ARCHITECTURE.md`
done. Backbone I1-I7 remains Opus work; F is human review.

Multi-theme awaiting visual review: Paper, Night Ink, Deep Forest, Sage Field;
colour owned by `theme.css`. Ember deferred.

Backbone runs against locked GPT-6 architecture at `27edeb0`, in
`ORENA_BACKBONE_INTEGRATION_GATES.md` order. I1 done. I2 schema approved,
sandbox only at `20260908_0005`, flag `off` (runbook §6).

Source Import: mapping, normalization, identity, provenance, batch results,
shared repository, Admin UI, learner cards; APPROVED (`a1a90b7b`). Schema auth
pending; import fail-closed.

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
  `grammar-shelf.js`, never a second syllabus.
- Cross-device continuity: device memory current; I2 schema/sync gated.
- Reading breadth: rights gate. Vocabulary Library content is gated until a
  complete pack is published; Feed and Chinese orthography are technically
  reviewable. Human UX acceptance is pending.
- Non-CI r8/r10/r11 matrices retired per product decision; r20 frozen native.
- Language coherence: closed for en/zh/vi (D-051 rule 26). The other stored
  support locales (ja, ko, es, fr, de, pt, ru, id, th) still fall back to
  English until given a pack. Platform Admin copy is out of scope.

## Baseline test evidence

Baseline suite now passes locally with `1109 passed, 118 skipped, 4 warnings`;
this is not a CI claim. Inherited governance/media failures were reconciled
against the current architecture; retired legacy matrix tests are not regressions.

## HUMAN GATES

Final browser review; production, data, migration, provider, credential,
OAuth/DNS/Cloudflare, billing and release operations; destructive history.
Local web iteration and checkpoint commits are authorized. Only the human
approves product direction.
