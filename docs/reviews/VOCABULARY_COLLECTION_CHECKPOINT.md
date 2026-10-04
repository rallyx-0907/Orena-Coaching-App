# Vocabulary collection learner checkpoint — 2026-10-04

MILESTONE=ORENA_PRODUCT_COMPLETION / S3 learner actions
STATUS=IMPLEMENTING (functional browser review available; full fidelity open)
Implementation commit and exact independent review are recorded below after checkpoint.
Base: d94715c29a6400d897134ac8e968bfb523ba5cac, codex/work.
WEB_URL=http://127.0.0.1:8021/next
WEB_ROUTE=#/collection/qa-collection-practice-20261004-zh
HOW_TO_REACH_IT=Choose Chinese in Settings -> Discover -> Collections -> QA Collection practice ZH.

## Result and cause

The existing Collection Save control only showed an unavailable toast. Start
review counted every catalog card but intersected membership with the first200
unrelated saved words, so unsaved packs opened empty and larger libraries lost
eligible words. The existing collection endpoint already resolved the learner's
saved rows by collection candidates, then discarded those rows from its payload.

Add all now explicitly saves only missing normalized words through the existing
saved-vocabulary endpoint. Partial successes remain saved; retry skips them.
Leaving stops subsequent writes. Existing saved words and their schedules are
not rewritten. Same-headword catalog senses share the existing learner word
identity; saves, action counts and review pages deduplicate that identity.

Start review counts actual saved words. An optional include_review projection on
the existing detail GET returns those already-resolved own saved rows. The shared
reader follows all collection pages; review no longer scans the first200 words of
the learner's library. Language is checked before saving or presenting collection
review. No new route, schema, collection bookmark store, dictionary pipeline or SRS.

## Browser evidence

Only :8021 was operated. Its catalog initially contained no published collection.
Created two internally authored, sandbox-only CSV fixtures through the existing
Admin import endpoint: qa-collection-practice-20261004-en and -zh, two entries each,
rights internal_curated, complete, explicit QA publication attestation. Both
returned200/published/imported2. These are QA examples, not production library
breadth or evidence that enrichment is implemented. Kept available for review.

EN_PARITY=Browser verified copper/marble: new collection review0 disabled -> Add all
-> saved2/review2 -> Reveal shows persisted meaning/example -> Got it200 -> second
card -> collection shows copper1/4 -> reload -> review reopens with two scoped cards.
ZH_PARITY=Same flow for 松树/竹林; revealed 松树 includes sōng shù, original definition,
sentence and existing stroke presentation. Grade advances it to1/4, next day;
reload retains it. Reopening reads persisted words.
CROSS_CAPABILITY_STATUS=Collection -> existing saved vocabulary/SRS -> Review;
ordinary due review, word detail and existing Library owners preserved.

360x740 responsive browser: document width360, no horizontal overflow. Collection
primary action ends y379; saved action y439. Revealed ZH review grading controls
are y587..647 within viewport740. Content, reading, meaning and example remain
visible with the existing inner scroll region. EN reveal also verified at360x740.
Desktop ZH collection and initial review verified. Screenshots visually inspected.

## Source work and cost evidence

Sandbox HTTP log records two explicit learner save POSTs per language, scoped
collection GETs with include_review=true, and one grade POST per language.
Returning/reloading/reopening issues reads; no repeated save or source-preparation
route. Existing code path reads catalog/saved rows and calls no provider.
GET /api/admin/ai/operations?limit=200 after both flows: available=true, sample10,
sample_truncated=false; newest event2026-10-03T12:15:14.879733+00:00; zero events
since2026-10-04. No new AI operation was recorded during these flows. This is
application instrumentation, not an external provider billing audit.

Save and SRS grading are ordinary persisted learner actions. This batch invokes
no ASR/LLM/TTS/translation generation. Authored fixture fields arrive at import;
provider-backed enrichment, if later authorized, belongs to preparation and must
reuse the durable readiness contract. Word pronunciation playback and dictionary
lookup are outside this tested sequence; no new behavior was added to them.

## Local verification

- Red/green: action gate initially failed because actions.js did not exist;
  implemented orchestration and passed. Tests cover EN/ZH provenance, schedule
  preservation, partial failure/retry, language guard, leaving, duplicate words,
  actual string readings, pagination and deduplicated scoped review rows.
- Final focused Node: collection_actions, screen_collection, screen_review,
  language_layers pass; browser ESM graph340 modules linked.
- All CI Node commands locally:128 pass/130 total,2 fail. screen_word's dated
  dueInDays fixture also fails on a clean d94715c archive. writing_workspace's
  literal Design Contract rule27 assertion passes on clean HEAD and fails only
  with the pre-existing human-owned Design Contract edit. That edit is preserved
  and excluded from this commit; neither assertion was weakened.
- Focused Python:106 passed,0 failed,0 skipped,2 warnings across vocabulary
  library routes/catalog/cards, review grades, paging and bounded library reads.
- Full local Python:2814 passed,3 failed,370 skipped,19 warnings in218.83s.
  All three failures reproduced on a clean d94715c archive: provider definitions
  expectation predates Azure; structured-text-only operation expectation predates
  speech; media lifecycle expects republish. Exact tests:
  test_ai_capabilities::test_static_text_provider_definitions_need_no_credentials_or_network;
  test_ai_capability_config::test_static_validation_and_provider_id_parity_require_no_network;
  test_media_lifecycle::test_the_console_reports_the_state_and_the_actions_that_fit_it.
- Ruff --no-cache app.py tests/test_vocabulary_library_route.py: pass.
- Project-memory and architecture validators, diff hygiene: see final checkpoint
  validation below. No CI execution or CI PASS claim.

Python ran in a disposable image with repository read-only, SQLite isolated CI
backend, tmpfs databases and PG/OAuth cleared. Sandbox runtime remains PostgreSQL.
One preliminary targeted command used a nonexistent test filename and ran no
tests; corrected discovery produced the106-pass run above.

## Review, scope and fidelity

Independent reviewer: Codex agent /root/collection_review. Working-diff review
APPROVE; no P0/P1. Its duplicate-headword P2 was fixed and independently confirmed,
including the later string-reading/page-dedup changes; final bounded findings0.
Exact-commit review is recorded below. This is code review, not human approval.

Provenance: pinned Orena.dc.html revision1790473816124946 frame21 Collection Detail
and frame13 Review Session. Existing two actions/rows/session are reused; approved
S3 intent changes Save to Add all, with truthful counts. No new geometry, CSS,
tokens, artwork or navigation architecture. Protected Collection/Review changed
deliberately to connect this same approved learner journey; dependent gates passed.

Fidelity: functional EN/ZH and360x740 checks PASS; scope/composition reuse checked.
Pixel comparison, all interface locales, both OS themes and physical touch are
NOT VERIFIED in this batch. Full fidelity remains OPEN, so do not promote the
milestone to REVIEWABLE/APPROVED. Existing missing collection cover/description
and source-encounter aggregate remain gaps. S3 enrichment/generation/publication
breadth is not complete. Grammar explicitly deferred by the human2026-10-04.

Changed files: .github/workflows/ci.yml; app.py;
static/orena/infrastructure/api.js; static/orena/screens/collection/actions.js,
copy.js, model.js, screen.js; static/orena/screens/review/screen.js;
scripts/test_orena_collection_actions.mjs; tests/test_vocabulary_library_route.py;
docs/reviews/VOCABULARY_COLLECTION_PLAN.md and this checkpoint;
docs/project/CURRENT_HANDOFF.md, CURRENT_PRODUCT_STATE.yaml, ROADMAP.md;
docs/product/ORENA_STATUS.md.

Persistence/schema: no change. Runtime: restarted only orena-next-verify-web to
load its mounted source; four saved QA learner words/two review grades and two
QA content collections through existing APIs. No migration, production/preview,
provider activation, volume deletion or native edits. Application1.4.0/frontend
version unchanged. PROJECT_STATE.md unchanged; CURRENT_HANDOFF.md and machine
current execution state updated. No Decision Log entry required: existing S3
intent/owners remain; deferring Grammar is recorded as human execution sequencing.
Human review: verify Add all wording/state, collection-scoped review and phone
learning controls. Full app completion is not claimed.

## Exact checkpoint

Pending exact commit binding and final memory-validator/Git status evidence.
