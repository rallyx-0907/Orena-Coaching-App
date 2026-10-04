# Listening entries and comprehension checkpoint

MILESTONE=Listening practice correction; STATUS=IMPLEMENTING (functional browser
review available; full fidelity open).
COMMIT=cab47730922405ce5c118c3067d3e47bcd26437c
WEB_URL=http://127.0.0.1:8021/next#/practice
WEB_ROUTE=practice -> Listen -> Listening comprehension / Dictation -> choose lesson
HOW_TO_REACH_IT=Open Listen in Practice Hub. Speaking has one Pronunciation card.
EN_PARITY=Two ready curated question lessons; original audio and checked answer
browser verified. ZH_PARITY=Four ready curated question lessons; original excerpt,
wrong/right answers, evidence and 1/2 result browser verified.
CROSS_CAPABILITY_STATUS=Same shared media owner; Follow preserved, Dictation and
Pronunciation choose content. Questionless imports do not promise comprehension.

## What changed and why

Dictation previously selected the first catalog lesson. Listen also duplicated
Shadowing, and Speaking exposed two cards to the same pronunciation route.
Both listening intents now use the approved Discover selection composition.
Comprehension has a real original-audio -> question -> answer/evidence -> next
flow with twelve admitted questions across six existing curated lessons.
Answers/results are session-only and make no account mastery claim. Source
evidence is checked against canonical transcript at admission. No AI generation
or source job is dispatched on workspace entry or reopen.

Exact implementation files (git show --name-only of the commit):

- .github/workflows/ci.yml
- scripts/test_orena_listening_entries.mjs
- scripts/test_orena_listening_questions.mjs
- scripts/test_orena_screen_practice.mjs
- static/orena/copy/shell.js
- static/orena/screens/dictation/copy.js
- static/orena/screens/dictation/screen.js
- static/orena/screens/discover/copy.js
- static/orena/screens/discover/model.js
- static/orena/screens/discover/screen.js
- static/orena/screens/import/sheet.js
- static/orena/screens/listening/screen.js
- static/orena/screens/practice/model.js
- static/orena/shell/routes.js
- static/orena/shell/screens.js
- static/orena/screens/listening-questions/copy.js
- static/orena/screens/listening-questions/model.js
- static/orena/screens/listening-questions/screen.js
- static/orena/screens/listening-questions/questions.css
- writing_coach/content/listening_catalog.v1.json
- writing_coach/listening_catalog.py
- tests/test_listening_comprehension.py

## Verification (local execution, not CI)

Full Python: 2810 passed, 3 failed, 370 skipped, 19 warnings. The three failures
match inherited provider-definition/config and unpublished-admin-media baselines.
Final focused comprehension suite: 6 passed. EN/ZH reopen instrumentation checks
four meaning reads all with translate=None; existing admitted questions unchanged.
This is a provider-negative contract check, not a production billing audit.
CI-listed Node matrix: 127 passed, 2 failed, zero skipped. Inherited failures:
writing workspace assertion against human-edited Design Contract numbering;
word dueInDays date-sensitive baseline. Validators were not weakened.
Browser ESM graph: PASS, 339 modules. Ruff touched Python files: PASS (--no-cache).
Architecture validator: PASS 1.4.0. Listening dev catalog check: SKIP (no snapshot).
Project-memory validator: PASS; git diff --check: PASS.

Real browser: ZH chose a non-first lesson, original audio started at 10.038s;
incorrect and correct responses yielded truthful 1/2 result. English chose
A pen in my bag; original audio played to 8.55s and correct answer showed source
evidence. Dictation chose an existing private video (26 segments), then changed
to another curated lesson (2 segments), with correct titles and workspace each
time. No source-preparation screen appeared. No fresh paid import/provider call
was used in this checkpoint. Existing D-121 import/readiness evidence is retained.

Phone web 360x740: primary Listen 44px high; question card x20/y163/w320/h507
scrolls internally; next footer y684/h56 stays inside viewport. Canonical Practice,
Discover, Dictation and Check Understanding patterns used, shared semantic tokens
retained. No new artwork. Functional navigation/readiness and viewport checks
PASS; exhaustive frame measurements, all themes/locales and physical phone
touch fidelity remain OPEN. Therefore no full REVIEWABLE/APPROVED claim.

Independent reviewer /root/readiness_review: APPROVE at exact implementation
commit above, no P0/P1/P2. Reviewer ran entry/questions/shell gates and ESM graph;
did not run Docker and relied on implementer Python/Ruff evidence.

## Boundaries and review

Protected areas intentionally changed: shared media catalog admission/metadata,
Practice/Discover navigation and capability handoffs. No parallel content model,
schema/migration, new learner persistence, payment or entitlement change.
Sandbox web only restarted to load catalog; PostgreSQL and volumes preserved.
Application/frontend version unchanged; no production/preview/deployment action.
Native untouched. PROJECT_STATE.md unchanged. CURRENT_HANDOFF.md and ORENA_STATUS.md
updated. D-123 required by explicit human direction; content contract amended.
Human-owned DESIGN_CONTRACT.md remains modified and unstaged.
Implementation checkpoint status: that file modified plus the untracked plan;
documentation checkpoint stages only this report/plan, handoff/status/content
contract and Decision Log. Remaining blocker: full fidelity/human browser review.
WHAT_THE_HUMAN_SHOULD_REVIEW=Listen group, both lesson choosers, question pacing,
answer/evidence clarity, phone viewport, and single Pronunciation entry.
