# S4 truthful Progress — browser checkpoint, 2026-10-02

MILESTONE=S4 truthful server-backed Progress
STATUS=IMPLEMENTING (browser-testable; full fidelity gate still open)
COMMIT=a15d3c2d2346051b933ee95a32b3764137d8d01e
WEB_URL=http://127.0.0.1:8021/next
WEB_ROUTE=#/progress
HOW_TO_REACH_IT=Profile → Progress; Practice Hub → From Your Errors; Speaking → Attempt History/Summary
EN_PARITY=real EN server records browser-checked
ZH_PARITY=real ZH server records browser-checked at 390×844
CROSS_CAPABILITY_STATUS=Reading/Dictation/Speaking/Writing return links; Writing-derived correction drill → Practice Hub

## Actual browser journeys

Brave, :8021 existing PostgreSQL sandbox, 1280×800 desktop and 390×844 phone viewport. No mock API responses,
no containers operated, no new assessment/provider action submitted for this slice. EN interface restored, learning EN, support VI.

- Progress Overview: actual streak and latest verified Reading 25, Writing 69, Speaking 71.
  Listening accuracy is unavailable, not client-reported 100. Earlier active-day/count Story additions were removed
  after independent fidelity review; the final card retains the frame's measured streak/declared-level shape.
  Recalled `526+` is self-assessed lifetime recall count, not proficiency. Trends, transfer stages, milestones,
  dated Recall history and personalized next steps show explicit unavailable states.
- Evidence → recorded Dictation → “A pen in my bag”, segment 1: working workspace with Play/Hint/Check/Next.
  Browser found and verified repair of asset-ID/lesson-ID mismatch.
- Evidence → recorded Reading → “PC-AUDIT The Morning Market”: article renders with appearance/aids,
  lookup text and Check understanding/Mark finished. Browser found and verified `article:` identity repair.
- Evidence → recorded Speaking → Cosmic calendar Attempt History: real server attempts, verified best 80,
  change −9 over displayed verified attempts; stub rows show dashes. Server-only recordings have no Compare
  action; retained local audio still routes to Compare. Counts reaching the bounded limit show `+`.
- Fresh-page Speaking Summary restores recent server attempts. Each attempt is one task in fresh and recording
  tabs; exact persisted IDs deduplicate local/server rows. Server verification controls score facts.
  With `100+` EN tasks, desktop buttons measured within 704–752 px of an 800 px viewport; phone buttons
  within 694–796 px of an 844 px viewport. The task list scrolls internally; page height equals viewport height.
- History → Writing restores the actual 70-word draft, v1 review 69/100, issue explanations and revision actions.
- From Your Errors EN: actual “many peoples” Writing issue → incorrect Check → explanation → Try again →
  “many people” → Correct → Next → Show answer on remaining items → summary (0/8 first try) → Finish → Practice Hub.
  The drill result is session-local; it is not claimed as a new durable weakness/review record.
- Learning/interface ZH on phone: Overview showed ZH counts (Listening 3, Recall 2, Reading 1, Speaking 9,
  Writing 14, observed before the final Story-card simplification) and verified Reading 100/Writing 88/Speaking 1; Attempt History restored a ZH attempt;
  Summary restored ZH server attempts; Errors showed actual Chinese sentence/correction with VI support
  explanation and visible action controls. VI interface was also checked. Screenshot artifacts are under
  `evidence/s4-progress-2026-10-02/`; earlier mobile Progress screenshot includes the active-day strip
  subsequently removed by independent review and is historical, not final visual evidence.

## Verification and review limits

Local execution: all 124 Node commands in CI were run: 123 pass, 1 fail, 0 skipped. The failing
`scripts/test_orena_screen_word.mjs:110` assumes its fixed 2026-10-02 due date is still in the future.
It fails identically on a clean git archive of HEAD `50751946c6389bd483718be3584eb7c4a072309f`.
Meaningful red→green tests cover unverified Dictation suppression, distinct quick takes, server score precedence,
local/account/language isolation, bounded counts, live media identity mapping and repeated Summary attempts.
Project-memory/architecture validators and diff hygiene were run. No CI run or pytest is claimed.
Independent code review: `S4_PROGRESS_CODE_REVIEW.md`; review findings were corrected before checkpoint.

Fidelity items: pinned frame/brief/state logic inspected; existing semantic tokens retained; foundation contrast gate
covers both token themes; EN/VI/ZH copy has complete layers/placeholders. Desktop and phone viewport browser journeys
checked in dark mode. Time is unmeasured: no replacement activity chart is invented. Still open: live DesignSync
source recheck (connector unavailable), measured full frame comparison, physical phone touch and light-theme browser
verification. Old `/` UI remains until the existing authorized cutover. **Full fidelity gate is not claimed PASS.**

No new schema, persistence authority, migration, runtime restart, volume change, version bump, deployment or
production operation. Protected changes: intentional Progress/History, shared speaking take/session namespace and
recorder correlation; existing account/language scope reused. EPUB/media unfinished files are preserved outside this slice.

## Whole-product work still open

S4 is a functional checkpoint, not Product Completion. Intelligence recommendations/WHY/HOW/action routing,
Agent integration/reconciliation, Books durable learner loop, transcript-backed imports, canonical EN/ZH Grammar,
Admin Overview/operations, full screen/element/state/flow inventory and substantial real content remain open.
No fake personalization or retired Grammar fallback was added. Next implementation remains Books learner verification,
then Media, after the S4 verification checkpoint. Human product approval and public/provider gates are separate.

PROJECT_STATE.md unchanged; CURRENT_HANDOFF.md and CURRENT_PRODUCT_STATE.yaml updated; D-112 records the explicit
human full-inventory/Intelligence direction. Exact committed file list and remaining Git status follow below.

## Exact application files

Documentation/evidence checkpoint files:

- `docs/product/ORENA_STATUS.md`
- `docs/project/CURRENT_HANDOFF.md`
- `docs/project/CURRENT_PRODUCT_STATE.yaml`
- `docs/project/DECISION_LOG.md`
- `docs/project/PRODUCT_COMPLETION_PLAN.md`
- `docs/reviews/S4_PROGRESS_BROWSER_CHECKPOINT.md`
- `docs/reviews/S4_PROGRESS_CODE_REVIEW.md`
- `docs/reviews/evidence/s4-progress-2026-10-02/en-desktop-progress.jpg`
- `docs/reviews/evidence/s4-progress-2026-10-02/en-desktop-summary.jpg`
- `docs/reviews/evidence/s4-progress-2026-10-02/en-mobile-summary.jpg`
- `docs/reviews/evidence/s4-progress-2026-10-02/zh-mobile-errors.jpg`
- `docs/reviews/evidence/s4-progress-2026-10-02/zh-mobile-progress.jpg` (historical intermediate)

P0/P1 code findings: none after independent fixes/re-review. Open milestone gate: full design fidelity
verification listed above. Inherited Word-detail gate failure remains outside this diff. No CI/full pytest result.
Human browser review: real activity/verified scores and unavailable states, source return links, restored Attempt
History/Summary, Writing-error corrections/retry/reveal/finish, Chinese scope and phone controls. This checkpoint
does not award human product approval.

Remaining Git status after the S4 documentation checkpoint (unfinished Books/media deliberately preserved):

```text
 M writing_coach/epub_import.py
 M writing_coach/media_library_store.py
?? tests/test_epub_import_zh_word_count.py
?? writing_coach/media_segmentation.py
?? writing_coach/media_spend.py
?? writing_coach/media_transcript_pipeline.py
```

Application commit files:

```text
scripts/test_orena_screen_attempts.mjs
scripts/test_orena_screen_errors.mjs
scripts/test_orena_screen_progress.mjs
scripts/test_orena_screen_speak-summary.mjs
scripts/test_orena_screen_speak.mjs
static/orena/infrastructure/api.js
static/orena/product/speaking-history.js
static/orena/product/speaking-recorder.js
static/orena/product/speaking-session.js
static/orena/product/take-store.js
static/orena/screens/attempts/copy.js
static/orena/screens/attempts/model.js
static/orena/screens/attempts/screen.js
static/orena/screens/errors/model.js
static/orena/screens/errors/screen.js
static/orena/screens/progress/copy.js
static/orena/screens/progress/model.js
static/orena/screens/progress/screen.js
static/orena/screens/speak-summary/copy.js
static/orena/screens/speak-summary/model.js
static/orena/screens/speak-summary/screen.js
static/orena/screens/speak-summary/speak-summary.css
static/orena/shell/context.js
```
