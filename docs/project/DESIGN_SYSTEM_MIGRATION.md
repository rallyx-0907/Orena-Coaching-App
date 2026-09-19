# Orena Design System migration (D-059)

## Governance

Purpose: the working tracker for moving the existing learner web onto the
approved Orena Design System. Authority: D-059 and the Design Contract section
it created; this file records progress, it makes no rule. Update when a phase or
a screen changes state. Do not store secrets, screenshots or unverified claims.

Status values: `Not started`, `In progress`, `Visual complete`, `Integrated`,
`QA passed`. A screen that still shows mock data is never past `In progress`.
`QA passed` needs 1440 / 1024 / 390, Ink and Paper, keyboard and focus, and
real data, verified in a browser - not a screenshot alone. Human product
approval is separate and is not recorded here.

Source: claude.ai design project `7a5604ca-1e11-4d8e-8305-7d0cb32d552d`.

## Integration map

| Design surface | Route | Owning module | Real data | Mock in the prototype that is not shown |
| --- | --- | --- | --- | --- |
| Home: continue, rails, today's words | `#/`, `#/continue` | `ui/world.js`, `ui/discovery.js`, `ui/content-rail.js`, `ui/reference.js` | `memory.continuation`, `libraryBooks`, `listeningLibrary`, `dailyVocabularyFeed` | due count unless the review queue reports one |
| Library: facets, grid, filter sheet | `#/practice?intent=reading`, `?intent=follow`, `#/content` | `ui/library.js`, `ui/media-library.js` | `libraryBooks` (cursor), `listeningLibrary` | "248 titles" - count only what the API returns |
| Reader, word panel, paper | `#/encounter?id=…` | `ui/reader.js`, `ui/reading-room.js`, `ui/lexical.js` | `libraryBookChapter`, `readingLookup`, `saveLibraryVocabulary` | - |
| Listening player, synced transcript | `#/encounter?id=media:…` | `ui/encounter.js`, `capabilities/media-player.js` | `listeningLibraryLesson`, `listeningProgress` | - |
| Dictation typing, inline diff | `#/encounter?…&intent=dictation` | `capabilities/dictation-evaluator.js` | `practiceOutcome` | - |
| Speaking recording, result | `#/practice?intent=speaking`, `#/conversation` | `ui/speaking.js`, `ui/voice-response.js` | `assessPronunciation`, `evaluateSpeaking` | a score where no recogniser is configured |
| Writing editor, evaluation, history | `#/expression` | `ui/expression.js`, `ui/writing-review.js` | `evaluate`, `improve`, `essays`, `saveDraft` | - |
| Vocabulary, collection, flashcard, review | `#/language`, `#/collection`, `intent=recall` | `ui/vocabulary-experience.js`, `ui/collection.js`, `product/recall.js` | `vocabularyLibraryCollections`, `reviewLibraryVocabulary`, `dailyVocabularyFeed` | - |
| Progress | `#/progress` (added) | `ui/progress.js`, `ui/growth-summary.js` | `learnerSummary` | streak, weekly minutes, hours: no backend measure exists |
| Profile, settings | preferences sheet | `app.js` | `learnerProfile`, `patchLearnerProfile`, `productCommerce` | HSK level (declared level is CEFR and not stored) |
| Onboarding | first-run preferences sheet | `app.js` | profile | email/password and Apple sign-in: Google OAuth only |
| Empty, loading, error | every room | `ui/html.js`, `app.js` | - | - |

Existing capabilities the mockup does not draw, and where they live (D-059 §3):
Continue on Home; Recall and collections in Vocabulary; Bring (text or video) in
Library; Grammar/Understanding as a Practice entry; Shadowing and Conversation
inside Listening and Speaking; support language, pinyin, plan usage and growth
in Profile; Admin for admins only; the learning toolbar and the Understanding
surface unchanged.

## Matrix

| Screen | Desktop Ink | Desktop Paper | Mobile Ink | Mobile Paper | Real data | Interactions | States | QA | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Foundation: tokens, themes, type, primitives | yes | yes | yes | yes | n/a | theme switch | skeleton, degraded panel | gates, AA contrast | Integrated |
| App shell and navigation | yes | yes | yes | yes | due count, language pair | rail, top bar search, tab bar, practice sheet, compact on scroll | n/a | 1440/1024/390 browser, gates | Integrated |
| Home | yes | yes | yes | yes | continuation, catalogues, daily feed | Continue cards, rails, words stack (flip, step, swipe) | begin, empty catalogue, loading skeleton | 1440/1024/390 browser, gates | Integrated |
| Progress | yes | yes | yes | yes | saved vocabulary, LearnerSummary | domain links | skeleton, unmeasured, degraded panel | 1440/1024/390 browser | Integrated (gaps tracked) |
| Library, search, saved, history | yes | yes | yes | yes | books (paged), passages, media, collections, saved vocabulary, kept phrases, essays, reading sessions, speaking takes | facets, filter sheet, library search, sort, grid/list, grouped global search, saved tabs, history | loading skeletons, empty, degraded panels | 1440/390 browser, gates | Integrated |
| Reading | - | - | - | - | - | - | - | - | Not started |
| Vocabulary, recall | - | - | - | - | - | - | - | - | Not started |
| Listening, dictation | - | - | - | - | - | - | - | - | Not started |
| Speaking | - | - | - | - | - | - | - | - | Not started |
| Writing | - | - | - | - | - | - | - | - | Not started |
| Profile, settings, onboarding | - | - | - | - | - | - | - | - | Not started |

## Parity audit (D-060), Phase 1-3

Compared directly with Home · desktop 1280, Home · 390 (Visual Direction),
Home · paper (Part 6), Progress · learner-facing (Part 2), Progress dashboard
· mobile (Part 5), Progress · paper (Part 6), and the Visual Grammar rules.
Values: EXACT, MINOR_DRIFT, MAJOR_DRIFT, NOT_IMPLEMENTED.

| Surface | Desktop 1440 Ink | Desktop 1440 Paper | Tablet 1024 | Mobile 390 Ink | Mobile 390 Paper | Remaining difference |
| --- | --- | --- | --- | --- | --- | --- |
| Shell rail | EXACT | EXACT | MINOR_DRIFT | n/a | n/a | Tablet is not drawn by the mockup; the rail keeps its icons (open design decision) |
| Top bar | EXACT | EXACT | EXACT | n/a | n/a | Search results are the reading library's until Phase 4 (GAP-011) |
| Phone bar and tab bar | n/a | n/a | n/a | MINOR_DRIFT | MINOR_DRIFT | A practice-sheet control sits beside the avatar; the mockup's phone has none. It is the phone's only way to Speaking, Dictation, Writing and Grammar until Library gives Practice a phone home (Phase 4) |
| Home · Continue | EXACT | EXACT | EXACT | EXACT | EXACT | Progress rail is the unmeasured track where a thread records no position (GAP-006) |
| Home · Listening shelf | EXACT | EXACT | EXACT | EXACT | EXACT | Rail meta shows the item count; the level half ("HSK 2") waits on GAP-004 |
| Home · Reading + Today's words | EXACT | EXACT | EXACT | EXACT | EXACT | Small step buttons under the stack for pointer and keyboard users (the mockup relies on swipe) - MINOR |
| Home · Speaking and writing shelf | MINOR_DRIFT | MINOR_DRIFT | MINOR_DRIFT | MINOR_DRIFT | MINOR_DRIFT | Not drawn on Home; the design checklist lists it as a Home rail not yet drawn. Kept in the approved shelf shape because it is the phone's only door to those prompts |
| Progress | EXACT | EXACT | EXACT | EXACT | EXACT | Figures the backend lacks show the unmeasured state in their approved place (GAP-001..003, 007..010) |
| Artwork | EXACT | EXACT | EXACT | EXACT | EXACT | The design's artwork slot until real art exists (GAP-012) |

Typography follows the mockup (D-061). One deliberate difference remains,
chosen by the human: the approved Orena mark instead of the violet square, to
be revisited with the logo.

## Legacy audit (D-060), Phase 1-3

| Legacy element | Where | State |
| --- | --- | --- |
| Colour aliases (`--paper`, `--ink`, `--muted`, `--line`, `--accent`, tinted-panel pairs) | foundation.css (53 uses) | Fixed - every base primitive reads the semantic tokens |
| Colour aliases | shell.css, components.css, Home section of reference.css, Progress section of rooms.css | None |
| Colour aliases | world.css, experiences.css, rooms.css, reader.css, media-library.css, the rest of reference.css | Remain for rooms not yet migrated (Phases 4-10); removed from each room as it migrates |
| Art Bible motif covers (orange/navy leaf, arc, wave) and the `rotate(undefined)` SVG error | ui/cover.js | Fixed - replaced by the artwork slot; the unsigned hash removes the error |
| Old shell: 11-link rail, "Bring" in the rail, footer, `＋` on the phone bar | app.js, reference.js, shell.css | Fixed - the approved rail, top bar and phone bar; Bring lives in Library |
| Old Home: start hero, doors row, "five minutes" and continuation shelves, 3:4 covers with a spine, poetic shelf titles, rail header icons, `←`/`→` text arrows | discovery.js, reference.css, content-rail.js | Fixed |
| Old Progress (list of domain rows with a window switcher) | progress.js, rooms.css | Fixed - the approved week panel, chart and domain cards |
| Text loading line and page-sized failure heading | app.js | Fixed - skeleton at the page's geometry; degraded panel with two ways forward |
| Hard-coded colours | shell.css, Home, Progress | None; artwork overlay colours are tokens; the artwork recipe keeps its own palette (artwork licence, rule 16) |
| Legacy `entryIcon` stroke icons | practice map, Continue room, rooms | Remain outside Phase 1-3; replaced per room |
| Preferences dialog | app.js | Phase 10 (Profile, settings) |

## Backlog from the later design parts

Parts 3-6 and the checklist add surfaces beyond the first two parts. Each joins
the phase that owns its domain, and each is built only over data that exists:

- Global search, grouped (Library phase) - over the existing library, media and
  vocabulary reads; no new search API unless one is authorised.
- Saved content, four kinds kept apart, and history / recently viewed (Library
  phase) - over device memory and saved vocabulary.
- Book detail and listening detail at 21:9 (Reading, Listening phases).
- Reading quiz and chapter complete (Reading phase) - over `readingSessions`.
- Listening quiz, replay-limited (Listening phase).
- One practice index shape for Dictation, Speaking, Writing and Vocabulary
  (their phases) - header with aggregate, optional chips, stateful rows.
- Progress domain detail (Progress phase) - `learnerSummary` only.
- Content interests and first-time home in onboarding (Profile phase).
- Toast and tooltip (shell phase), the offline strip (shell phase).
- Admin overview and content import styling (last; Admin stays admin-only).

Phase 4 notes (parity): Library, Search, Saved and History follow Parts 1, 3, 5
and 6, and the Library toolbar carries only what the mockup draws (search,
filters, sort, view). Saved and History are reached from the settings sheet -
the IA's "secondary, reached from anywhere" - until Vocabulary's "Saved words"
row (Phase 6) and the profile sheet (Phase 10) draw their homes; bringing
content in lives in Saved's Content tab, where brought-in content is listed.
Topic facets show only topics the support language can name.

One temporary entry remains, with its removal condition: the phone's practice
sheet. Its rooms reach the phone as their indexes land - Reading in Phase 5,
Listening and Dictation in Phase 7, Speaking in Phase 8, Writing in Phase 9 -
and Grammar rides with the practice map. **The sheet control is removed in
Phase 7**, when every practice room has a drawn phone entry; nothing else may
be added to it in the meantime.

Next: Phase 5, Reading (reading library, book detail, reader workspace, quiz and chapter complete). Backend gaps: `UI_BACKEND_GAPS.md`.

Open design gaps the prototype names itself: the 1024 tablet breakpoint (the
shell collapses to an icon sidebar), the processing state after submit, and
motion timing for flip, sheet entry, score count-up and feed swipe (tokens in
`foundation.css`).
