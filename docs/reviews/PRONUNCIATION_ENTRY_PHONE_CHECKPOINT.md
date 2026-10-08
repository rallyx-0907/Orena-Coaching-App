# Pronunciation entry and phone practice correction

Date: 2026-10-04. Lane: `codex/work`. Local execution, not CI or human approval.
Implementation: `096240da824897893387cf749b426da2cb6605be`.

## Cause and scope

Practice Hub assigned Pronunciation the first `sentences`/`clip` item. The generic
entry therefore repeatedly opened the same Chinese dialogue. Compare's Choose
media opened ordinary Discover; its cards took the learner to Content Detail and
Listening, losing pronunciation intent. Private imports are account memberships,
not all present in the public Listening library, so the chooser must also resolve
their persisted records rather than silently omit them.

On phones, wrapped header/source controls and a permanently visible 200px embed
left the sentence only a small scrolling area. This correction deliberately
touches the protected shared media/Compare presentation to fix that reported flow;
it adds no ingestion, storage, native implementation or design system.

Two playback regressions were reproduced during verification: initial YouTube
seek could autoplay and move the selected Listening line; an asynchronous seek
could report the previous paused endpoint and prematurely resolve a new model
playback. Initial positioning now pauses before readiness, and segment completion
requires actual playback within the requested range. Both have red/green tests.

## Experience and design provenance

The current human instruction authorizes this bounded flow correction. D-122
records it; D-119 shared Speaking and D-121 source readiness remain unchanged.
Pinned design revision `1790473816124946` supplies the reusable patterns:

- `Orena.dc.html`: Discover cards, search/filter/import; Practice Hub mode rows;
  Scripted Pronunciation sentence/model/recorder anatomy.
- `Compare With Model.dc.html` and its parent Compare frame: source recorder,
  72px microphone, comparison/history and playback controls.
- Visual Skin EN/ZH: existing semantic palette and language treatment.

Generic Pronunciation opens `#/discover?tab=listen&practice=pronunciation`, even
when the public Speaking catalogue is empty. Ready curated/shared media and
read-only resolved private imports enter shared `shadow` directly; authored
sentence items remain addressable. Selecting the current media keeps its segment,
including legacy membership aliases. Different media starts at its first line.
Specific recommendations/resume links retain their named lesson.

Import invoked here retains practice intent, admits only usable original playback
and a transcript in the learning language, and otherwise keeps the learner at the
content boundary with a truthful message. Ordinary Discover/import is unchanged.

Phone adaptation retains canonical components/tokens: one compact heading row,
media identity/change row, line selector/previous/next row, sentence/readings/
meaning region, and recording footer. History has a labelled 44px icon target;
model/speed/change controls are 44px. The already connected original embed is
revealed while playing and collapses after playback, keeping Record in view.
No source-preparation state is hidden: D-121 already removed that work boundary.
Desktop retains the visible original embed and full history label.

Design Contract now names responsive phone web as the review reference for future
native layout/flow. Native remains frozen. Only our appended four-line rule was
committed; the human's existing Design Contract changes remain unstaged.

## Browser evidence on :8021

- Practice -> Pronunciation displayed choices, rather than opening the fixed
  `这是什么？` dialogue. ZH chooser showed four curated and five admitted personal
  media items; EN chooser showed two curated and two personal media items.
- Selecting the affected imported YouTube `NkYwdZhkHF0` opened practice directly,
  with its title and all 26 segment choices. Choosing line2, Choose media, then
  the same item retained line2 and normalized to its canonical media id.
- Original Hear model used the existing YouTube embed. Slow playback visibly
  showed the original video; no synthetic model or source-processing progress.
- After the autoplay correction, Listening stood at `0:19`; returning to
  Shadowing retained the exact line6 segment id. Reopen/reload retained the
  selected segment. The previously completed D-121 report owns initial-import
  evidence; this batch reused the already imported source without a new import.
- 360x740 idle: sentence region 375px; Record y636..708; page exactly 360x740.
  While the original video played: preview 200px, sentence region 163px, Record
  still y636..708; no page/horizontal overflow and zero `progress` elements.
- 390x844 idle: sentence region 479px; recording row y727..812; page 390x844.
  Screenshots checked Hanzi/Pinyin/meaning and balanced header/source controls.
- EN learning/VI interface and ZH learning/ZH interface were checked on phones.
UI EN and original learning ZH/support EN settings were restored afterward.

Server log read for the final 40-minute navigation window found **zero POSTs**
under `/api/media*`, `/api/media-learning*`, `/api/speaking/model*` or
`/api/speaking/source*`. It contained only saved-media/source GETs (including one
missing stale membership, excluded from choices). This is route instrumentation,
not a paid-provider dashboard claim. EN/ZH read-path provider spies in
`test_orena_content_readiness.mjs` also assert zero source preparation on reopen.
Preparation may compute configured artifacts once at import; new learner
recordings, submitted writing and Agent questions retain legitimate new compute.

No fresh microphone recording/provider assessment was submitted in this batch.
Existing recorder/take/result contracts remain covered by the Speaking/Compare
gates; historical real assessments remain in the previous evidence. Full result
fidelity, light-theme visual review and all-device coverage remain separate work.

## Required checkpoint fields

MILESTONE=Pronunciation entry and phone practice correction
STATUS=REVIEWABLE (bounded correction; whole Product Completion IMPLEMENTING)
COMMIT=096240da824897893387cf749b426da2cb6605be
WEB_URL=http://127.0.0.1:8021/next
WEB_ROUTE=#/discover?tab=listen&practice=pronunciation
HOW_TO_REACH_IT=Practice -> Pronunciation -> select ready media -> Hear model/Record
EN_PARITY=ready EN choices/direct practice, VI labels and phone viewport verified
ZH_PARITY=actual imported source, choices, Pinyin/meaning, segment/reopen verified
CROSS_CAPABILITY_STATUS=shared media/segment across chooser, Listening and Speaking; D121 preserved
WHAT_CHANGED=content choice and practice intent, compact phone composition, paused initial seek and correct segment completion
WHAT_THE_HUMAN_SHOULD_REVIEW=choose another lesson; change media within practice; long sentence/meaning scroll; Hear/Record on phone; original video during Hear; Listening return

## Local checks and review

Targeted Practice/Discover/Sheets/Speak/Compare/content-readiness/media-playback
gates pass. Browser ESM graph passes: 335 linked modules. Project-memory and
architecture validators pass. The full CI-listed Node matrix: 124/126 pass;
the same two pre-existing failures remain: dated Word fixture `dueInDays`, and
Writing Workspace's rule27 comparison against the human's unstaged renumbering.
Neither assertion was weakened. Clean committed Design Contract retains rule27.

Exact implementation commit exported with `git archive` and the full Node matrix
rerun: **125/126 pass**, only the same dated Word fixture fails. Writing Workspace
passes with the committed Design Contract. Desktop 1910x855 also has no page or
horizontal overflow; Record y743..815, selected line6 retained, zero progress.

Independent reviewer: Codex (GPT-6), `/root/readiness_review`, reviewed exact
`096240da824897893387cf749b426da2cb6605be` against `3889c7f75bf50b1043b3dfcd9f04a9cbcc3df889`.
Verdict **APPROVE**, no P0/P1/P2; host targeted gates and ESM verified, no Docker.
This is code review, not human product approval.

Fresh full Python gate in the isolated application image, repository read-only
and throwaway SQLite test databases: **2805 passed, 3 failed, 370 skipped,
19 warnings**, 337.01s. The same inherited failures recorded in the D-121 baseline:
`test_ai_capabilities::test_static_text_provider_definitions_need_no_credentials_or_network`,
`test_ai_capability_config::test_static_validation_and_provider_id_parity_require_no_network`,
`test_media_lifecycle::test_the_console_reports_the_state_and_the_actions_that_fit_it`.
No Python/backend implementation changed in this slice. The running product's
PostgreSQL authority and persistent volumes were untouched. Host Python is absent;
the memory/architecture validators ran read-only in the existing :8021 image.

No merge to main, production/provider activation, schema change or native code
change. This records a locally verified bounded correction, not CI PASS or
whole-product visual approval.
