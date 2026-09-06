# Current Handoff

## Governance

Current execution state on `codex/work`; durable product authority is the
Product Constitution, Content Architecture, approved brand, and D-046.

## Current branch / lane

`codex/work` / Orena product-layer reset and experience foundation.
Starting integrated HEAD: 5827f6a1c72213aa41c2d4ba2c684711aec24ee6.
Do not restore deliberately removed learner implementations. Git is the archive.

## Last verified batch

Extracted primitives pass `node scripts/test_orena_primitives.mjs`.
New browser graph passes `node --experimental-vm-modules scripts/validate_browser_esm_graph.mjs` (20 modules).
The new real app renders at http://localhost:8011/#/ . English audio and
Vietnamese meaning follow the same segment during real playback and selection.
These are partial execution checks; full mission acceptance remains pending.

## DONE

- Human-authorized Constitution / Content Architecture clarification and D-046.
- Independent extraction: Dictation comparison/alignment, transcript timeline,
  media player, recorder, speech comparison, grammar pedagogy, API adapter.
- Old web product tree and seven obsolete product specifications physically
  deleted in the working tree; no legacy directory.
- New web product model: encounter, practice intention, owner-scoped content
  relationships/continuation/drafts, adapters to existing evidence APIs.
- New Explore, Practice, collections, Follow, contextual Dictation/voice,
  expression, saved-language/recall and grammar surfaces coded.

## IN PROGRESS

Browser refinement and full removal/regression completion. Latest code adds
seek control, pronunciation presentation, recording cancellation guards, and
next-segment practice; these latest refinements still need browser validation.

## PENDING / NEXT EXACT TASK

1. Check current diff; continue without recreating old product code.
2. Finish native learner wrapper / route / shell removal, retaining auth,
   secure sessions, API contracts, recording and linguistic primitives.
3. Remove remaining obsolete original web product files and old product-only
   tests; migrate primitive tests and validators to the new product boundary.
4. Fix outstanding new-layer issues: continuation routes for free Writing and
   Grammar, direct practice lifecycle, degraded save/feedback states, Pinyin,
   translation recovery, keyboard focus and EN/ZH mobile presentation.
5. Run real browser journeys, regression suites and project-memory validators.
6. Update verified state and final status; commit; stop once for human review.

## Runtime / safety

Isolated `orena-foundation-web` on 127.0.0.1:8011; separate
`orena-foundation-postgres` and `orena-foundation-review` network. Database is
temporary, no production volumes or credentials. Mount is this workspace, read
only. Restart only this review web container after Python/asset-route changes.
Production on 8000 and prior preview on 8010 were not operated. No provider
activation, production deployment, schema migration or data mutation.

## BLOCKED

No current tool blocker. A browser quota interruption cleared and browser use
resumed. Do not treat partial checks as REVIEWABLE.

## OPEN P0

None identified.

## OPEN P1

Reset is incomplete until native/remaining wrappers and obsolete tests are
removed and full EN/ZH browser acceptance passes.

## HUMAN GATES

Production operations, data, credentials, paid providers, migrations, release,
billing, OAuth/DNS/Cloudflare, destructive history and store publishing remain
gated. Ordinary local reset/deletion and recovery commits are authorized.

## Baseline test evidence

Before reset, the full Python run and pristine starting HEAD both produced
753 passed / the same 20 failed governance or source-format assertions. Those
are inherited baseline failures; do not weaken assertions to hide them.
The reset intentionally retires tests tied only to removed product behavior.
Do not claim current full-suite results until the test migration is finished.
