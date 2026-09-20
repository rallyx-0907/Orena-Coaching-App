# Current Handoff

## Governance

Purpose: compact recovery context. Change when the active stage or verified
facts change. Do not store secrets or unverified claims. Authority: current
human instruction, Orena Constitution, Content Architecture, approved brand,
D-046. No human approval or production readiness is implied.

## Current branch / lane

`codex/work`, Orena WEB Golden Star plus real learning capabilities. Do not
restore the deleted learner product.
Human instruction authorizes full-stack WEB work on the capabilities
themselves, not only on the foundation.

## DONE

D-046 and the product reset are committed; the shared media, transcript,
dictation, recording, provider and evidence primitives survive, and the learner
surfaces converge on `static/orena`. PostgreSQL APIs remain.

## Learning capabilities

Preserved Opus implementation; ORENA_STATUS and GOLDEN_STAR_COMPLETION hold
behavior and evidence. Current invariants/owners:

- Listening: ui/encounter.js; pure Follow, synchronized excerpt, pause on inquiry.
- Reading: content/reading.js readable contract; reading-library.js rights
  gate; ui/reader.js adds paragraph meaning and never-AI word lookup.
- Writing: ui/writing-review.js; exact snapshot, grounded revision; T12 `c71c644`.
- Speaking: product/conversation.js; own turns, no absent-reference alignment.
- Grammar/Vocabulary: canonical Concept IDs and shared contextual explanation.
- Kept language: product/memory.js; provenance device sidecar after account save.
- Recall: product/recall.js; hidden answer, explicit reveal/self-assessment.
- Continue: ui/patterns.js and product/intent.js; actual work type and intention.
- Understanding: ui/understanding.js; exact context and stale-answer rejection.
- Presentation/brand: ORENA_WEB_EXTENSION_GUIDE; Opus owns theme/brand.

## Last verified batch

D-057 and the surfaces under it. `ui/lexical.js` is the shared interaction
layer for reader, transcript and practised line. Listening is two panes, the
spoken line IS the active row. Speaking is a composed module. A synthetic
result is never a pronunciation score.

My Language opens on the language, not a count of it: what is due, what was
kept with the sentence it came from, collections, then the tally in one line.
Recall is the loop over that same contract and scheduler - a landing, one item,
real counts only. Writing's rubric is one row per dimension (label, bar, score,
change), the bar showing where the learner was and is now.

A review is earned once (D-051 rules 28-29): each evaluation carries its
identity - text, both languages, level, task, evaluator contract - in the
`module_data` both backends persist, so no migration. Reload 0 calls, unchanged
0, edited revision 1, eight concurrent identical 1. Editing marks the previous
version rather than deleting it.

A review also keeps what it found. Only an untrustworthy finding is dropped; a
quote occurring literally sets `anchored` and a span, and only an anchored one
offers "find it in my text" - the rest still reads under deeper improvement.
Top 3 is presentation; one call returns both, `errors` being what can be
pointed at and `priorities_vi` only what to carry forward.

Dictation's live reveal is positional: N units written reaches N units of the
line, and no further. Typing is not a hint.
Writing is bounded by one shared contract (`writing_coach/writing_limits.py` +
`capabilities/writing-limits.js`, gated): 12,000 code points / 60,000 bytes /
1,000 lines, refused whole, never truncated, before any prompt or provider
call. Dictation: Previous, position, Next, nothing else.

Writing is a workspace (rule 27): intention in the heading, full width until a
review exists, one primary action in one word, quotes located by selection.
Rules 23-26: a transcript row keeps its geometry; its actions live in
`ui/learning-toolbar.js`; Dictation binds the player to the line; en/zh/vi each
own every interface string.

Verified: pytest `1136 passed, 118 skipped`, all 50 CI `.mjs` gates, ESM graph,
both validators, the Python CI validators. Browser pass on
`orena-foundation-web`:8011 for vi/en, zh/en and vi/zh at desktop and 390px,
including real Gemini review, revision and re-review; the error-heavy essay
returns three located corrections in one call, reload still 0. No CI claim.

## Runtime / safety

Operate only isolated `orena-foundation-web`:8011 with its PG/network,
published on `0.0.0.0:8011` for private-LAN review. PGDATA is tmpfs; the start
script restores it. Restart after Python changes; uvicorn does not reload. Do
not operate production 8000/preview 8010/Cloudflare/volumes. A peer that cannot
reach it needs TCP 8011 open to `LocalSubnet`. AI eval uses selected
local/provider credentials; ASR unconfigured.

## NEXT EXACT TASK

Core: R3/T15 Card human PASS. Vocabulary foundation/catalog/feed/save and
Chinese orthography are schema-free; Source Import is E2E through Admin and
learner projections. The remaining Vocabulary gate is human schema/runtime
authorization for `20260916_0008`, then PostgreSQL rehearsal. Review at
`:8011/#/language`.

Backbone lane (Opus), D-054 delegation: D-054, 0006, 0007 approved by delegated
review (`I3_SCHEMA_REVIEW_REQUEST.md`). Sandbox only: chain `20260912_0007`,
flag on, backbone `active` (runbook §7). Writing drafts kept with the account
there, human-approved (`4e1f0a5`); billing/quota off. "Your growth" in
preferences (I6, REVIEWABLE). Deletion gated (D-055). I4 `/api/collection`.
No I1-I7 claim implies human approval.

## IN PROGRESS

Golden Star findings closed; Packages A-D of `ORENA_REFERENCE_ARCHITECTURE.md`
done. Backbone I1-I7 is Opus work; F is human review.

Design System migration (D-059..D-063): Phases 1-5 done, through the Reading
UI. Reading is NOT feature complete, not books-only (D-063). Scope, next
phase, gaps GAP-001..045: `DESIGN_SYSTEM_MIGRATION.md`.

Backbone runs against locked GPT-6 architecture at `27edeb0`, in
`ORENA_BACKBONE_INTEGRATION_GATES.md` order. I1 done; I2 schema approved,
sandbox only at `20260908_0005`, flag `off` (runbook §6).

Source Import: mapping, normalization, identity, provenance, batch results,
shared repository, Admin UI, learner cards; APPROVED (`a1a90b7b`). Schema auth
pending; import fail-closed.

Writing keeps no per-review record of its support language; the device covers
its own reviews only (a schema question, gated).

## PENDING

R3 Gemini live gate passed 4/4 EN/ZH/support. Ollama stays a lower-quality
local option: `qwen3:8b` leaks target script in nested support answers.

## BLOCKED

I2 §6 step 9 (`ORENA_ACCOUNT_BACKBONE=on`) is done, sandbox only (chain
`20260912_0007`, runbook §7). Production/preview deploy and activation past
sandbox stay blocked: separate human gate, not authorized, not asked for.

## OPEN P0

None identified.

## OPEN P1

- `#/language` renders "temporarily unavailable" only in long multi-room sweeps
  at short dwell; never isolated (0/130). Self-recovers.
- Grammar breadth: patterns joined by stable Concept ID, extended by
  `grammar-shelf.js`, never a second syllabus.
- Cross-device continuity: device memory current; I2 schema/sync gated.
- Reading breadth: rights gate per text. Vocabulary Library content is gated
  until a complete pack is published; Feed and Chinese orthography are
  technically reviewable. Human UX acceptance pending.
- Non-CI r8/r10/r11 matrices retired; r20 frozen native.
- Language coherence: closed for en/zh/vi (D-051 rule 26); the other stored
  support locales fall back to English until given a pack. Admin copy is out
  of scope.

## Baseline test evidence

Baseline passes locally with `1109 passed, 118 skipped`; not a CI claim.
Retired legacy matrix tests are not regressions.

## HUMAN GATES

Final browser review; production, data, migration, provider, credential,
OAuth/DNS/Cloudflare, billing and release operations; destructive history.
Local web iteration and checkpoint commits are authorized. Only the human
approves product direction.
