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
| Filter Sheet | `screens/discover/screen.js` (`paintSheetBody`), `screens/discover/model.js` (`filterOptions`, topic vocabulary) | `scripts/test_orena_screen_discover.mjs` | reviewable |
| Word Quick Sheet · Sentence Quick Sheet | `screens/quick-sheet/` | `scripts/test_orena_screen_quick-sheet.mjs` | reviewable |
| Vocabulary Focus | `screens/listening/vocab-sheet.js` | `scripts/test_orena_screen_listening.mjs` | reviewable |
| Contextual Orena · Orena Voice | `screens/orena/panel.js`, `screens/orena/voice.js` | `scripts/test_orena_screen_orena.mjs`, `scripts/test_orena_agent.mjs` | reviewable |
| Import | `screens/import/` (opened from Discover's "+ Import") | `scripts/test_orena_screen_sheets.mjs` | reviewable |
| Notifications | `screens/notifications/` (opened from the shell bell, `shell/router.js`) | `scripts/test_orena_screen_sheets.mjs` | reviewable |
| Stroke Practice | `screens/word/stroke-sheet.js`, `screens/word/stroke-tiles.js` | `scripts/test_orena_screen_word.mjs` | reviewable (styled from Word and Review, browser-checked in the Vocabulary batch 1ce3b816) |
| Prompt Setup (writing setup) | `screens/writing/` (its setup sheet) | `scripts/test_orena_screen_writing.mjs` | reviewable |
| Mic state | `screens/mic/` | `scripts/test_orena_screen_mic.mjs` | reviewable |
| Lesson complete | `screens/lesson-complete/` | `scripts/test_orena_screen_lesson-complete.mjs` | reviewable |

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
| 11 | Orena Home | `#/orena` | shell | `screens/orena/` | reviewable |
| 08 | Practice Hub | `#/practice` | shell | `screens/practice/` | reviewable |
| 09 | Skill Hub | `#/practice/:skill` | shell | `screens/practice/` | reviewable |
| 12 | My Library | `#/library` | shell | `screens/library/` | reviewable |
| 21 | Collection Detail | `#/collection/:id` | shell | `screens/collection/` | reviewable |
| 22 | Word Detail | `#/word/:id` | shell | `screens/word/` | reviewable |
| 44 | Grammar Library | `#/grammar` | shell | `screens/grammar/` (data: `product/grammar-source.js`) | building (2026-09-29: rebuilt on `GRAMMAR_CONTENT_CONTRACT.md` §9, D-100; no R5 read; no content is served yet, so it draws the empty state; verified with the test-only fixture `scripts/fixtures/grammar/`; waits for Grammar Lab PR B) |
| 17 | Progress | `#/progress` (`?tab=` per Profile's own links) | shell | `screens/progress/` | reviewable |
| 24–25 | Profile, Today's progress | `#/profile` | shell | `screens/profile/` | reviewable |
| 51 | Coming soon | `#/coming/:key` | shell | `screens/coming/` | reviewable |
| 26 | Settings | `#/settings` (`?tab=` per Profile's own links) | focus | `screens/settings/` | reviewable |
| 27 | Search | `#/search` | focus | `screens/search/` | reviewable |
| 14 | Reader | `#/read/:id` | focus | `screens/reader/` | reviewable |
| 20 | Check Understanding | `#/read/:id/check` | focus | `screens/check/` | reviewable |
| 40 | Reading Complete | `#/read/:id/done` | focus | `screens/reader-complete/` | reviewable |
| 39 | Reading Transfer | `#/read/:id/transfer` | focus | `screens/reading-transfer/` | reviewable |
| 46 | Discussion | `#/read/:id/discuss` | focus | `screens/discussion/` | reviewable |
| 06 | Listening Workspace | `#/listen/:id` | focus | `screens/listening/` | reviewable |
| 07 | Dictation | `#/listen/:id/dictation` | focus | `screens/dictation/` | reviewable |
| 28 | Shadowing / Pronunciation (D-119) | `#/listen/:id/shadow` | focus | `screens/compare/` | reviewable; shared recorder |
| 33 | React / Reuse | `#/listen/:id/react` | focus | `screens/react/` | reviewable |
| 45 | Respond to Content | `#/respond/:id` | focus | `screens/respond/` | reviewable |
| 15 | Scripted Pronunciation (D-119) | `#/speak/:id` | focus | `screens/compare/` | reviewable; shared recorder |
| 16 | Compare With Model | `#/speak/:id/compare` | focus | `screens/compare/` | reviewable |
| 41 | Attempt History | `#/speak/:id/attempts` | focus | `screens/attempts/` | reviewable |
| 42 | Speaking Summary | `#/speak-summary` | focus | `screens/speak-summary/` | reviewable |
| 29 | Free Talk | `#/free-talk` | focus | `screens/free-talk/` | reviewable |
| 30 | Conversation | `#/conversation` | focus | `screens/conversation/` | reviewable |
| 31 | Situation Reaction | `#/situation` | focus | `screens/situation/` | reviewable |
| 32 | Retell | `#/retell/:id` | focus | `screens/coming/` | coming-soon (no backend or content) |
| 43 | Timed Reaction | `#/timed-reaction` | focus | `screens/coming/` | coming-soon (no backend or content) |
| 48 | Mock Interview | `#/interview` | focus | `screens/coming/` | coming-soon (no backend or content) |
| 49 | Sound / Tone | `#/sounds` | focus | `screens/coming/` | coming-soon (no backend or content) |
| 18 | Writing | `#/write` · `#/write/:id` | focus | `screens/writing/` | reviewable |
| 19 | Compare Versions | `#/write/:id/compare` | focus | `screens/writing-compare/` | reviewable |
| 37 | Context Rewrite | `#/rewrite` | focus | `screens/coming/` | coming-soon (no backend or content) |
| 38 | Timed Writing | `#/timed-writing` | focus | `screens/coming/` | coming-soon (no backend or content) |
| 13 | Review Session | `#/review` | focus | `screens/review/` | reviewable |
| 34 | Timed Recall | `#/timed-recall` | focus | `screens/coming/` | coming-soon (no backend or content) |
| 35 | Context Transfer | `#/transfer` | focus | `screens/coming/` | coming-soon (no backend or content) |
| 36 | Vocabulary Daily Feed | `#/feed` | focus | `screens/feed/` | reviewable |
| 50 | From Your Errors | `#/from-your-errors` | focus | `screens/errors/` | reviewable |
| 47 (canonical, H1 2026-09-29; 23 is not built) | Grammar Concept | `#/grammar/:id` | focus | `screens/grammar-concept/` (data: `product/grammar-source.js`) | building (2026-09-29: rebuilt on `GRAMMAR_CONTENT_CONTRACT.md` §0-§8, D-100; no R5 read or write; an R5 id resolves through `aliases`; with no content served every point draws "not available"; verified with the test-only fixture `scripts/fixtures/grammar/`; waits for Grammar Lab PR B) |
| Onboarding 01–05 | Welcome, Account, Languages, Level, Meet Orena | `#/welcome` | none | `screens/onboarding/` | reviewable |

## Platform Admin (D-101 E)

`Orena-Admin.dc.html` (pinned 2026-09-29, `SYNC_2026-09-29.md`) inside this UI, on the existing Admin
backend (`/api/admin/*`, `require_admin`) and its client, moved to shared modules the old console
also imports: `capabilities/admin-api.js` (client), `capabilities/admin-format.js` (formatters),
`capabilities/admin-ai.js` (AI control-plane rules and the session controller), `admin-reading.js`
(Reading rules and requests), `admin-imports.js` (importer rules and flows), `admin-content.js`
(catalogue lifecycle and publish admission), `admin-tray.js` (the progress tray's memory and clock). Routes are `bare`
(no learner frame): the Admin draws its own shell (`screens/admin/frame.js`).
Product Completion supersedes the earlier staging-only scope: Overview, AI & Models,
Users, Content (including Reading), Imports and Operations are connected to the
existing backend. The Practice generator still has no working backend and is unavailable. The old console stays at `/#/admin` until the cutover.

| Frame | Screen | Route | Shell | Code | Gate | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Admin shell (rail, header, phone chips) | Platform Admin | `#/admin` (opens `#/admin/overview`) | Admin's own | `screens/admin/{screen,frame,model,blocks}.js`, `admin.css` | `scripts/test_orena_screen_admin.mjs` | building (2026-09-30, slice 1) |
| No access | Admin access required | any `#/admin/...` for a non-admin | Admin's own | `screens/admin/no-access.js`; `main.js` (internal-review gate) | `test_orena_screen_admin.mjs` (zero requests) | building |
| A2 AI & Models | Providers, Capability routing | `#/admin/ai` (`?tab=route`) | Admin's own | `screens/admin/ai-pages.js` `listPage`, `ai.js` | `test_orena_screen_admin.mjs` | building |
| A3 Provider configure | Write-only key, endpoint | `#/admin/ai/provider/:id/key` | Admin's own | `ai-pages.js` `keyPage` | same | building |
| A4 Provider detail | Credential, test, models, used by, usage | `#/admin/ai/provider/:id` | Admin's own | `ai-pages.js` `providerPage` | same | building |
| A5 Capability routing | Primary, standby, availability | `#/admin/ai/capability/:id` | Admin's own | `ai-pages.js` `capabilityPage` | same | building |
| Profile entry "Platform admin" | Profile action row | `#/profile` (admin only) | learner | `screens/profile/{model,screen}.js` | `test_orena_screen_profile.mjs`, `test_orena_screen_admin.mjs` | building |
| A8 Content | Content home | `#/admin/content` | Admin's own | `screens/admin/content-pages.js` `homePage`, `content.js` | `scripts/test_orena_screen_admin_areas.mjs` | building (2026-09-30, slice 2) |
| A9 Books, A10 Book detail | Books, book lifecycle | `#/admin/content/books`, `#/admin/content/books/:id` | Admin's own | `content-pages.js` `listPage`/`bookPage` | `test_orena_screen_admin_areas.mjs` | building |
| A11 Media, A12 Media detail | Media, reprocess, lifecycle | `#/admin/content/media`, `#/admin/content/media/:id` | Admin's own | `content-pages.js` `mediaPage` | same | building |
| A13 Vocabulary, A14 Vocabulary detail | Collections, publish admission | `#/admin/content/vocabulary`, `#/admin/content/vocabulary/:id` | Admin's own | `content-pages.js` `collectionPage` | same | building |
| A15 Reading overview | Reading | `#/admin/reading` | Admin's own | `screens/admin/reading-pages.js` `overviewPage`, `reading.js` | same | building |
| A16 Reading queue | Review queue (Article, Level, Targets, Rights; source in the row meta - D-105), Published, Rejected, Archived | `#/admin/reading/queue` | Admin's own | `reading-pages.js` `queuePage` | same | building |
| A17 Reading review detail | Article, targets, original, evidence, sets; rights editor and the hard copyright gate at Publish (D-105) | `#/admin/reading/article/:id` | Admin's own | `reading-pages.js` `articlePage` | same | building |
| Comprehension set review | Question review, set lifecycle | `#/admin/reading/set/:id` | Admin's own | `reading-pages.js` `setPage` | same | building |
| A21 Add reading content | URL / text / file, rights, progress tray | `#/admin/reading/add` | Admin's own | `reading-pages.js` `addPage`; `screens/admin/tray.js` | same | building |
| A22 Reading sources, A23 Source detail | Sources | `#/admin/reading/sources`, `#/admin/reading/source/:id` | Admin's own | `reading-pages.js` `sourcesPage`/`sourcePage` | same | building |
| A28 Imports | Imports hub | `#/admin/imports` | Admin's own | `screens/admin/imports-pages.js` `hubPage`, `imports.js` | same | building |
| Import books / media / vocabulary | The three importers | `#/admin/imports/books`, `#/admin/imports/media`, `#/admin/imports/vocabulary` | Admin's own | `imports-pages.js` | same | building |
| Register source | Register a source | `#/admin/imports/sources` | Admin's own | `imports-pages.js` `sourceFormPage` | same | building |
| Reading jobs, A29 Job detail, A30 History | Jobs, retry, history | `#/admin/imports/jobs`, `#/admin/imports/jobs/:id`, `#/admin/imports/history` | Admin's own | `imports-pages.js` | same | building |
| Progress tray | Global tray | every Admin place | Admin's own | `screens/admin/tray.js`, `capabilities/admin-tray.js` | same | building |
| Grammar Lab package import | not drawn by the Admin design | - | - | not built: no grammar store or `/api/grammar/v1/*` (D-100) | - | blocked (see `UI_BACKEND_GAPS.md`) |
| A1 Overview, A6-A7 Users, A31-A34 Operations | Overview, accounts, runtime, workers, polling, errors | `#/admin/overview`, `#/admin/users`, `#/admin/users/:id`, `#/admin/operations` and children | Admin's own | `screens/admin/control{,-pages}.js` | `test_orena_admin_control.mjs`, `test_orena_screen_admin_areas.mjs`; ADMIN_BASIC_CONTROL_BROWSER_CHECKPOINT.md | REVIEWABLE (2026-10-03) |
| A24-A27 Practice generator | unavailable: no generation backend | - | - | - | - | not built |

## Retired by the cutover

Filled in by the cutover slice: every old address, the surface that replaced it,
and its `LEGACY_TOMBSTONES.md` entry.
