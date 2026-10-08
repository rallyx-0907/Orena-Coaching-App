# D-121 — Content readiness repair

2026-10-03–04, Codex lane `codex/work`; baseline
`ecf4c19f93f78ad8efbaf0f0eb481ab9123f7992`.

## Outcome and scope

The reported ready-import defect is corrected in `/next`: media Shadowing and
Scripted Pronunciation play the selected original source using Listening's
canonical playback adapter. They do not download/extract a model clip, assess
the source, request dictionary/annotation preparation, or synthesize substitute
speech. Missing original playback rejects a media practice deep link before
opening a workspace; Listening already gates its Shadowing action on playback.

The old boundary was capability-owned: Compare fetched model audio and paid
source alignment, a five-minute temporary YouTube cache could download again,
and uncached lesson GETs could translate source text. Old saved `url:` entries
also invoked import again. The correction removes those entry-time operations,
rather than suppressing their progress bar.

Media pipeline preparation now warms configured support-language meanings for
private as well as shared imports, persists Chinese readings, and persists
optional English IPA positions. IPA preparation can use the free English
dictionary but cannot use AI fallback or retain a new full dictionary result.
Learner reads only consume stored/editorial translation and language artifacts;
legacy IPA may reuse an already persisted dictionary fact. Legacy Chinese
readings retain deterministic local compatibility projection with no provider.

Listening, Dictation and Respond-to-Content consume the same `openMedia` read
boundary. Vocabulary/context **explicit learner requests** and new learner
recordings/writing/questions retain their own legitimate evaluation/model work.
No other capability prepares a source merely because navigation opens it.

## Real browser evidence

Sandbox only: `http://127.0.0.1:8021/next`. The actual affected previously imported
Chinese item is `source-01637ff733db4cd8a52ede9a15cdff2f`, YouTube `NkYwdZhkHF0`,
26 stored segments. This was an existing ready record, not a newly paid import.

Observed in the browser:

1. Open the existing media's Shadowing route. Hanzi/Pinyin/English meaning and
   enabled Hear model/Record are present; source progress elements: **0**.
2. Select line2 (original range5–10s), Hear model plays the same YouTube source.
3. Listening → select/pause line2 → Shadowing preserves the exact segment ID
   ending `:64d0f9cd0fc56f5a800388d434a4ab56eb51c218620eb1dd5e69e8d73b40e8fb:000000`.
4. Hear model → Today → reopen the exact line → refresh → sandbox restart:
   same stored text/meaning/Pinyin, Hear enabled, no source-processing state.
5. English `en-science-cosmic-calendar` in Vietnamese UI: Hear plays the canonical
   Wikimedia **VIDEO**, observed `paused=false`, playbackRate1, currentTime1s.
   No extraction endpoint or synthesized model voice.

The original embed URL observed is
`https://www.youtube-nocookie.com/embed/NkYwdZhkHF0?enablejsapi=1&origin=http%3A%2F%2F127.0.0.1%3A8021&controls=0`.
The player has its ordinary network/media startup, not a content preparation job.

Server route instrumentation for the final20-minute browser window: **7 lesson
GETs;0 source acquisition POSTs;0 speaking model-audio/model-reference requests**.
Read-path provider spies additionally prove zero source translation/ASR/reference/
annotation/acquisition work on opening/reopening in EN and ZH. Preparation's
translation spy records1 initial call,1 total after repeated preparation and
Listening/Dictation/Shadowing/Respond/reopen reads. This does not assert a provider
count for the historical import, or for unrelated runtime activity.

Desktop,390×844 and360×740/1366×768: no horizontal or page overflow; Hear/Record
remain inside the viewport. Long sentence/meaning scroll only inside the card.
At390×844 Record was y740–812. UI settings and viewport were restored after QA.
No live learner assessment was submitted in this batch; previous EN/ZH assessment
evidence and recorder regression tests remain the evidence for that boundary.

## Local validation, not CI

- Final full Python gate: **2805 passed,3 failed,370 skipped,19 warnings**.
- Clean baseline full gate: **2798 passed,3 failed,370 skipped,19 warnings**.
  Both failure sets contain the same three inherited failures:
  `test_ai_capabilities::test_static_text_provider_definitions_need_no_credentials_or_network`,
  `test_ai_capability_config::test_static_validation_and_provider_id_parity_require_no_network`,
  `test_media_lifecycle::test_the_console_reports_the_state_and_the_actions_that_fit_it`.
- Bounded final media/readiness/Speaking/D4 regression run: **82 passed,22 skipped**.
  Ruff on touched Python: PASS. Initial optional legacy-dictionary read failure was
  corrected and this subset rerun; assertions were not weakened.
- All CI-listed Node gates executed locally: **124 passed,2 failed** in the working
  tree. Word-detail due-date fixture fails on clean HEAD too. Writing workspace's
  numbered-rule assertion fails only with the user's pre-existing Design Contract
  formatting/renumbering edit; that edit is excluded from this checkpoint.
  The exact committed implementation was archived and all Node gates rerun:
  **125 passed,1 failed** (the same inherited Word-detail due-date fixture).
  Writing workspace passes in that clean checkpoint, confirming partial staging
  excluded the unrelated numbered-rule edit.
- Readiness/Compare reference/media Speaking/Compare/Scripted Pronunciation/Listening
  mapping/removal/foundation and browser ESM gates PASS; ESM **335 modules linked**.
- Project-memory and architecture validators PASS; architecture version1.4.0.
  Listening catalog check reported SKIP: no committed development catalog, unchanged.
- An initial full run had an additional D4 retry failure; it passed standalone and
  both later full runs. It is not represented as a final regression or silently fixed.

Python ran in the application image with a read-only repository mount, cleared
OAuth/PG runtime variables and throwaway SQLite databases. Runtime remained PG;
SQLite was only the isolated test backend. No validator weakened. No CI claim.

## Review and limitations

Independent reviewer: `/root/readiness_review` (Codex), final **code APPROVE**;
no remaining P0/P1 in the reviewed correction. Reviewer did not run tests/Docker.
The reviewed implementation commit and final Git state are recorded below at checkpoint.

Missing optional source word intervals/model contours remain unavailable, rather
than calling speech assessment on the original source from Compare. Legacy IPA
not already persisted remains unavailable until an explicit content preparation
repair. Additional language layers do not trigger provider work on reads. No
blanket import-time provider fan-out or new persistence/retention model was added.

Fidelity evidence for the bounded correction: canonical Compare/Listening player
contracts inspected; original voice/segment interaction follows explicit D-121;
EN/ZH content and VI interface checked; existing token colours untouched; no new
art or copy invented; primary controls/inner scroll/overflow checked at the sizes
above. Light/dark use the existing token owner and foundation gates, without new
colour values. Full source-frame/whole-product fidelity and fresh merged-entry
assessment remain open: this is not a whole Speaking/product APPROVED claim.

Protected changes: Shared Media Learning read projection, shared source player,
Speaking/Compare and Listening resolver, concise Design Contract rule. Dependent
Listening/Dictation/Respond/removal/recorder mappings checked. No Journey/Review/
Grammar IDs/admin API/brand/visual-reference changes.

Persistence/schema/retention: none. Runtime: :8021 sandbox web restarts only,
no volume deletion or migration. Application/frontend versions unchanged.
Deployment/production/Cloudflare/OAuth/provider activation: none.
PROJECT_STATE.md unchanged. CURRENT_HANDOFF.md/CURRENT_PRODUCT_STATE.yaml and
ORENA_STATUS.md updated. Decision Log required: D-121. Other user changes preserved.

MILESTONE=Content readiness lifecycle repair
STATUS=IMPLEMENTING (defect corrected and browser-verifiable; full product fidelity open)
WEB_URL=http://127.0.0.1:8021/next
WEB_ROUTE=#/listen/source-01637ff733db4cd8a52ede9a15cdff2f/shadow
HOW_TO_REACH_IT=Open the ready imported Chinese media in Listening, choose line2, Shadowing
EN_PARITY=canonical original VIDEO playback and no preparation verified
ZH_PARITY=actual affected imported YouTube, Pinyin/meaning/selected line/reopen verified
CROSS_CAPABILITY_STATUS=shared read boundary for Listening/Dictation/Shadowing/Respond; contextual requests remain learner actions
WHAT_CHANGED=content materialization before readiness; navigation reads; original segment playback
WHAT_THE_HUMAN_SHOULD_REVIEW=Hear model immediately; switch back and forth at line2; leave/reopen; long line on phone; optional measurements truthfully absent

## Git checkpoint and exact change inventory

COMMIT=3aa577b73b743568ede2645dbc9402ccc344cc08

Exact-commit independent code review: Codex (GPT-6), `/root/readiness_review`,
**APPROVE** for the SHA above on `codex/work`; no P0/P1. This is code review,
not human product approval or production activation.

Implementation checkpoint files:

```text
.github/workflows/ci.yml
app.py
docs/product/ORENA_CONTENT_ARCHITECTURE.md
docs/product/ORENA_CONTENT_EXECUTION_ARCHITECTURE.md
docs/product/ORENA_STATUS.md
docs/project/CURRENT_HANDOFF.md
docs/project/CURRENT_PRODUCT_STATE.yaml
docs/project/DECISION_LOG.md
docs/project/DESIGN_CONTRACT.md (D-121 paragraph only)
docs/project/plans/CONTENT_READINESS_REPAIR.md
docs/reviews/CONTENT_READINESS_BROWSER_CHECKPOINT.md
scripts/test_orena_compare_reference.mjs
scripts/test_orena_content_readiness.mjs
scripts/test_orena_screen_listening.mjs
static/orena/capabilities/original-segment-player.css
static/orena/infrastructure/api.js
static/orena/product/compare-reference.js
static/orena/product/media-source.js
static/orena/product/original-segment-player.js
static/orena/product/speaking-source.js
static/orena/screens/compare/compare.css
static/orena/screens/compare/screen.js
static/orena/screens/speak/screen.js
tests/test_content_readiness_navigation.py
tests/test_speaking_library.py
writing_coach/listening_api.py
writing_coach/media_library_api.py
writing_coach/media_transcript_pipeline.py
writing_coach/speaking_library.py
```

Documentation follow-up records this reviewed SHA and sets
CURRENT_PRODUCT_STATE.last_verified_application_commit to it. No subsequent code
change. Git status after the implementation checkpoint and final documentation
checkpoint: ` M docs/project/DESIGN_CONTRACT.md`; no staged code, no other edits.
This is the pre-existing user edit, preserved, not discarded or committed.
No push/merge to main.
