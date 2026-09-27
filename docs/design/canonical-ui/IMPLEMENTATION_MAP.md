# Implementation map — design revision 1790473816124946

Where every frame of the pinned design lives in the new learner UI (D-091), so a
later design revision can be applied surface by surface: find the frames the
revision changed, follow this table to their code and gates, change only those.

**Status values:** `planned` (not built) · `building` · `reviewable` (built with
real data, gated, browser-verified in en/vi/zh, both themes, desktop and phone)
· `coming-soon` (the design's Coming soon screen stands in because the backend
cannot serve it; see `docs/project/UI_BACKEND_GAPS.md`) · `approved` (only the
human sets it).

**Shell** = rail/top bar (desktop) and header/tab bar (phone) are drawn. **Focus**
= a learning workspace from the design script's focus list (Design Contract
rules 47, 49).

Routes are hash routes of the new entry (`/next#/…` until the cutover, then
`/#/…`). Agent intents (`docs/project/AGENT_CONTRACT.md` §6) map to routes in
`static/orena/shell/intents.js`.

## Shell, primitives and overlays

| Design element | Code | Gate | Status |
| --- | --- | --- | --- |
| Tokens (light, dark), device variables | `static/orena/kit/tokens.css`, `kit/device.css`, `kit/device.js` | `scripts/test_orena_kit.mjs` | planned |
| Icons (Lucide, pinned release) | `kit/icons.js` | `scripts/test_orena_kit.mjs` | planned |
| Brand marks (`ol-mark`, `ol-intel*`) | `kit/brand.js` ← `assets/brand/orena/logo/` | `scripts/test_orena_kit.mjs` | planned |
| Desktop rail, top bar, phone header, phone bar, focus mode | `shell/frame.js`, `shell/shell.css` | `scripts/test_orena_shell.mjs` | planned |
| Router, back stack, breadcrumb, nav origin | `shell/router.js`, `shell/routes.js` | `scripts/test_orena_shell.mjs` | planned |
| Banner · Loading · Load error | `kit/states.js` | `scripts/test_orena_kit.mjs` | planned |
| Toast | `kit/toast.js` | `scripts/test_orena_kit.mjs` | planned |
| Sheet host (desk panel / phone bottom sheet, scrim) | `kit/sheet.js` | `scripts/test_orena_kit.mjs` | planned |
| Filter Sheet | `screens/discover/filter-sheet.js` | | planned |
| Word Quick Sheet · Sentence Quick Sheet | `screens/quick-sheet/` | | planned |
| Vocabulary Focus | `screens/listening/vocabulary-focus.js` | | planned |
| Contextual Orena · Orena Voice | `agent/panel.js`, `agent/voice.js` | `scripts/test_orena_agent.mjs` | planned |
| Import | `screens/import/` | | planned |
| Notifications | `screens/notifications/` | | planned |
| Stroke Practice | `screens/word/stroke-practice.js` | | planned |
| Prompt Setup (writing setup) | `screens/writing/setup-sheet.js` | | planned |
| Mic state | `kit/mic-sheet.js` | | planned |
| Lesson complete | `kit/lesson-complete.js` | | planned |

## Screens

| # | Frame | Route | Shell | Code | Status |
| --- | --- | --- | --- | --- | --- |
| 10 | Today | `#/today` | shell | `screens/today/` | planned |
| 04 | Discover | `#/discover` | shell | `screens/discover/` | planned |
| 05 | Content Detail | `#/content/:id` | shell | `screens/content/` | planned |
| 11 | Orena Home | `#/orena` | shell | `agent/home.js` | planned |
| 08 | Practice Hub | `#/practice` | shell | `screens/practice/` | planned |
| 09 | Skill Hub | `#/practice/:skill` | shell | `screens/practice/` | planned |
| 12 | My Library | `#/library` | shell | `screens/library/` | planned |
| 21 | Collection Detail | `#/collection/:id` | shell | `screens/collection/` | planned |
| 22 | Word Detail | `#/word/:id` | shell | `screens/word/` | planned |
| 44 | Grammar Library | `#/grammar` | shell | `screens/grammar/` | planned |
| 17 | Progress | `#/progress` | shell | `screens/progress/` | planned |
| 24–25 | Profile, Today's progress | `#/profile` | shell | `screens/profile/` | planned |
| 51 | Coming soon | `#/coming/:key` | shell | `screens/coming/` | planned |
| 26 | Settings | `#/settings` | focus | `screens/settings/` | planned |
| 27 | Search | `#/search` | focus | `screens/search/` | planned |
| 14 | Reader | `#/read/:id` | focus | `screens/reader/` | planned |
| 20 | Check Understanding | `#/read/:id/check` | focus | `screens/check/` | planned |
| 40 | Reading Complete | `#/read/:id/done` | focus | `screens/reader/` | planned |
| 39 | Reading Transfer | `#/read/:id/transfer` | focus | `screens/reading-transfer/` | planned |
| 46 | Discussion | `#/read/:id/discuss` | focus | `screens/discussion/` | planned |
| 06 | Listening Workspace | `#/listen/:id` | focus | `screens/listening/` | planned |
| 07 | Dictation | `#/listen/:id/dictation` | focus | `screens/dictation/` | planned |
| 28 | Shadowing | `#/listen/:id/shadow` | focus | `screens/shadowing/` | planned |
| 33 | React / Reuse | `#/listen/:id/react` | focus | `screens/react/` | planned |
| 45 | Respond to Content | `#/respond/:id` | focus | `screens/respond/` | planned |
| 15 | Scripted Pronunciation | `#/speak/:id` | focus | `screens/speak/` | planned |
| 16 | Compare With Model | `#/speak/:id/compare` | focus | `screens/compare/` | planned |
| 41 | Attempt History | `#/speak/:id/attempts` | focus | `screens/compare/` | planned |
| 42 | Speaking Summary | `#/speak/summary` | focus | `screens/speak/` | planned |
| 29 | Free Talk | `#/speak/free` | focus | `screens/free-talk/` | planned |
| 30 | Conversation | `#/speak/conversation` | focus | `screens/conversation/` | planned |
| 31 | Situation Reaction | `#/speak/situation` | focus | `screens/situation/` | planned |
| 32 | Retell | `#/speak/retell/:id` | focus | `screens/retell/` | planned |
| 43 | Timed Reaction | `#/speak/timed` | focus | `screens/timed-reaction/` | planned |
| 48 | Mock Interview | `#/speak/interview` | focus | `screens/interview/` | planned |
| 49 | Sound / Tone | `#/speak/sounds` | focus | `screens/sounds/` | planned |
| 18 | Writing | `#/write` · `#/write/:id` | focus | `screens/writing/` | planned |
| 19 | Compare Versions | `#/write/:id/compare` | focus | `screens/writing/` | planned |
| 37 | Context Rewrite | `#/write/rewrite` | focus | `screens/rewrite/` | planned |
| 38 | Timed Writing | `#/write/timed` | focus | `screens/timed-writing/` | planned |
| 13 | Review Session | `#/review` | focus | `screens/review/` | planned |
| 34 | Timed Recall | `#/review/timed` | focus | `screens/timed-recall/` | planned |
| 35 | Context Transfer | `#/review/transfer` | focus | `screens/transfer/` | planned |
| 36 | Vocabulary Daily Feed | `#/feed` | focus | `screens/feed/` | planned |
| 50 | From Your Errors | `#/errors` | focus | `screens/errors/` | planned |
| 23, 47 | Grammar Concept | `#/grammar/:id` | focus | `screens/grammar/` | planned |
| Onboarding 01–05 | Welcome, Account, Languages, Level, Meet Orena | `#/welcome` | none | `screens/onboarding/` | planned |

## Retired by the cutover

Filled in by the cutover slice: every old address, the surface that replaced it,
and its `LEGACY_TOMBSTONES.md` entry.
