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
| Words (en / vi / zh, by language layer) | `copy/index.js`, `copy/shell.js`, `screens/<name>/copy.js` | `scripts/test_orena_copy.mjs` | reviewable |
| Shared list/card/progress primitives (`listRow`, `mediaCard`, `progressRing`, `segmentedControl`, `pageHeader`, `sectionHead`, `heroMedia`, `masteryBars`, `rowThumb`) | `kit/components.js`, `kit/components.css` | `scripts/test_orena_components.mjs` | reviewable |
| Tokens (light, dark), device variables | `static/orena/kit/tokens.css`, `kit/device.css`, `kit/boot.js`, `kit/device.js` | `scripts/test_orena_kit.mjs` | reviewable (AA: N-8 awaits the human) |
| Icons (Lucide, pinned release) | `kit/icons.js` ← `scripts/sync_lucide_icons.py` (lucide-static@0.525.0) | `scripts/test_orena_kit.mjs` | reviewable |
| Brand marks (`ol-mark`, `ol-intel*`) | `kit/brand.js` ← `assets/brand/orena/logo/` | `tests/test_orena_routes.py` | reviewable |
| Desktop rail, top bar, phone header, phone bar, focus mode | `shell/frame.js`, `shell/shell.css`, `shell/context.js` | `scripts/test_orena_shell.mjs` | reviewable |
| Router, back stack, breadcrumb, nav origin | `shell/router.js`, `shell/routes.js`, `shell/screens.js` | `scripts/test_orena_shell.mjs` | reviewable |
| Banner · Loading · Load error | `kit/states.js` (offline banner in `main.js`) | `scripts/test_orena_kit.mjs` | reviewable |
| Toast | `kit/toast.js` | `scripts/test_orena_kit.mjs` | building |
| Sheet host (desk panel / phone bottom sheet, scrim) | `kit/overlay.js` | `scripts/test_orena_kit.mjs` | building |
| Filter Sheet | `screens/discover/filter-sheet.js` | | planned |
| Word Quick Sheet · Sentence Quick Sheet | `screens/quick-sheet/` | | planned |
| Vocabulary Focus | `screens/listening/vocabulary-focus.js` | | planned |
| Contextual Orena · Orena Voice | `agent/panel.js`, `agent/voice.js` | `scripts/test_orena_agent.mjs` | planned |
| Import | `screens/import/` (opened from Discover's "+ Import") | `scripts/test_orena_screen_sheets.mjs` | reviewable |
| Notifications | `screens/notifications/` (opened from the shell bell, `shell/router.js`) | `scripts/test_orena_screen_sheets.mjs` | reviewable |
| Stroke Practice | `screens/word/stroke-practice.js` | | planned |
| Prompt Setup (writing setup) | `screens/writing/setup-sheet.js` | | planned |
| Mic state | `kit/mic-sheet.js` | | planned |
| Lesson complete | `kit/lesson-complete.js` | | planned |

## Screens

Each screen's gate is `scripts/test_orena_screen_<folder>.mjs` (the last segment
of its Code column), e.g. `screens/today/` → `scripts/test_orena_screen_today.mjs`;
one gate can cover more than one folder — Practice Hub and Skill Hub share
`screens/practice/` and its one gate, and Grammar Library and Grammar Concept
each have their own folder but share one gate,
`scripts/test_orena_screen_grammar.mjs`. All are also walked by
`scripts/validate_browser_esm_graph.mjs` (every `screen.js` `shell/
screens.js` registers) and `scripts/test_orena_shell.mjs` (routing/focus/intent
shape).

| # | Frame | Route | Shell | Code | Status |
| --- | --- | --- | --- | --- | --- |
| 10 | Today | `#/today` | shell | `screens/today/` | reviewable |
| 04 | Discover | `#/discover` | shell | `screens/discover/` | reviewable |
| 05 | Content Detail | `#/content/:id` | shell | `screens/content/` | reviewable |
| 11 | Orena Home | `#/orena` | shell | `agent/home.js` | planned |
| 08 | Practice Hub | `#/practice` | shell | `screens/practice/` | reviewable |
| 09 | Skill Hub | `#/practice/:skill` | shell | `screens/practice/` | reviewable |
| 12 | My Library | `#/library` | shell | `screens/library/` | reviewable |
| 21 | Collection Detail | `#/collection/:id` | shell | `screens/collection/` | reviewable |
| 22 | Word Detail | `#/word/:id` | shell | `screens/word/` | reviewable |
| 44 | Grammar Library | `#/grammar` | shell | `screens/grammar/` | reviewable |
| 17 | Progress | `#/progress` (`?tab=` per Profile's own links) | shell | `screens/progress/` | reviewable |
| 24–25 | Profile, Today's progress | `#/profile` | shell | `screens/profile/` | reviewable |
| 51 | Coming soon | `#/coming/:key` | shell | `screens/coming/` | reviewable |
| 26 | Settings | `#/settings` (`?tab=` per Profile's own links) | focus | `screens/settings/` | reviewable |
| 27 | Search | `#/search` | focus | `screens/search/` | reviewable |
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
| 23, 47 | Grammar Concept | `#/grammar/:id` | focus | `screens/grammar-concept/` | reviewable |
| Onboarding 01–05 | Welcome, Account, Languages, Level, Meet Orena | `#/welcome` | none | `screens/onboarding/` | planned |

## Retired by the cutover

Filled in by the cutover slice: every old address, the surface that replaced it,
and its `LEGACY_TOMBSTONES.md` entry.
