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
| Reading: entry, book page, reader workspace | yes | yes | yes | yes | shared library books and chapters, passages, device continuation, saved vocabulary, support-language translation | library facets and search, chapter list with unread-only and show-all, tap a word for the panel, support layer, type size | loading skeletons, unavailable tiles and layers, error panels, check unavailable | 1440/390 browser, gates | UI migrated; Reading not feature complete (GAP-028..045) |
| Vocabulary, recall | yes | yes | yes | yes | saved vocabulary and its summary, collections and their progress, the daily feed, the review scheduler | due review, collection tiles, not-mastered filter, show all, flip, shuffle, grading | loading, empty, all-done, unavailable tier and grades, error panels | 1440/390 browser, gates | UI migrated; four-grade review and tiers are gaps (GAP-019, GAP-020) |
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

Phase 5 notes (parity): the Reading room is the approved library scoped to
books and texts - one library (`ui/library-browse.js`), not a second one - so
the retired cover grid, its shelves and its inline detail state are gone. A
book card leads to the book page (`#/book`), rebuilt to Part 4 section 16:
overview first, chapters below, side column last. The reader follows Part 1
section 04: a compact bar (back, place, progress rail, reading layers, type
size), the text beside a word panel on a desk and as an anchored sheet on a
phone, and a tapped word answers itself in the dictionary rather than opening
a toolbar. Every figure the design draws that nothing measures keeps its place
with a dash and a reason (GAP-028 to GAP-036).

Two deviations, both recorded: a chapter row shows the chapter's real word
count where the mockup draws minutes (GAP-029), and the phone keeps the primary
action inline in the hero rather than in a fixed bottom bar, because Orena's
phone shell already owns the bottom of the screen with its tab bar.

The check and the end of a chapter follow Part 3 section 13. The check is one
question at a time - rail, question, lettered options - and stays optional: it
opens from an invitation after the text. The API scores a whole set, so the
answers are collected first and the same rail walks back through them with the
real results; no per-question verdict is invented on the client, and the answer
panel names the paragraph the evidence came from when the text contains it.
The end of a chapter says what was finished, what it left behind (new words
kept since the chapter opened, counted for real) and the one way on; the quiz
and time figures keep their tiles with a dash (GAP-031, GAP-030).

## Reading: approved scope versus what Phase 5 migrated

Phase 5 is the **Reading UI and reader migration**, not the Reading capability.
The approved Reading scope is wider than Book -> Reader -> dictionary -> a
multiple-choice check, and it stays recorded here so nothing in it is lost by
being absent from the migrated screens (human instruction, 2026-09-20; D-063).

Reading content is **not books-only**: it is books, articles, stories, news,
essays, dialogues and the learner's own imported reading. The library already
carries all of them and every one is reachable; what is missing is a content
kind and metadata of their own, so they can be named, filtered and counted as
what they are (GAP-044).

| Capability | State | Where it is, or why not |
| --- | --- | --- |
| Word lookup, dictionary, never AI | Supported | `ui/lexical.js` panel; tap answers |
| Save vocabulary from the reader | Supported | `saveLibraryVocabulary`, real; counted on the book page and at the end of a chapter |
| Translation of a selection, contextual explanation | Supported | panel translation; "explain" opens the shared contextual explanation |
| Support-language layer over paragraphs | Partial | first twelve paragraphs per text (GAP-045) |
| Pronunciation of a word or phrase | Partial | the device's own speech synthesis, no provider voice; sentence, paragraph and chapter audio: GAP-038, audiobooks GAP-032 |
| Chinese Pinyin layer | NOT_STARTED | GAP-028 |
| Highlight a word, sentence or paragraph, durably | NOT_STARTED | GAP-037 |
| Grammar notes and pattern explanation in the text | NOT_STARTED | GAP-039 |
| Contextual learner notes | NOT_STARTED | GAP-036 |
| Bookmark a book or a place | NOT_STARTED | GAP-034 |
| Exact resume position inside a chapter | NOT_STARTED | GAP-040 |
| Multiple-choice comprehension | Supported | `submitReadingAnswers`, scored server-side |
| Open-answer comprehension | NOT_STARTED | GAP-041 |
| Review of saved highlights and notes | NOT_STARTED | GAP-042 |
| SRS / review linkage from what a text taught | Partial | saving is real and lands in review; four-grade scheduling is GAP-019, linkage GAP-043 |
| Chapter completion state | NOT_STARTED | GAP-035 (what is shown is derived from the current place) |
| Reading time, quiz average per book | NOT_STARTED | GAP-030, GAP-031 |
| Content kinds: articles, news, essays, dialogues, imports | NOT_STARTED | GAP-044 |

Phase 6 notes (parity): Vocabulary home follows Part 4 section 18 - the domain
tile, what was kept and mastered, what is due, the learner's collections and
the way to everything saved; the daily feed keeps its row because it is a real
destination the mockup's smaller panel does not draw. A collection follows Part
1 section 05: its artwork, what it is, how far through it the learner is, one
way in, then a compact two-column overview of its words with the design's one
filter - the full list, with search, level, status and sort, is behind "show
all". The flashcard and the review session follow the same section: the card is
card-sized with the amber rim of an earned mark, and the session shows what is
due, the word, and - after the learner commits - how well they knew it.

Three honest states, all tracked: a collection's tier reads as a dash
(GAP-020); Hard and Easy keep their place in the approved four-grade panel and
say they are not available yet, because the scheduler accepts two answers
(GAP-019); and no interval is printed next to a grade, because nothing previews
one.

The card is the mockup's 232x306 in every language: a long Latin headword is
handled by the type inside it - the word's size follows the card's own width
and wraps - never by a bigger card. What the mockup does not draw is gone from
these surfaces: the daily feed's second copy in the Vocabulary room (its home
is Home, where the design draws it), the retired Discover-side feed and library
sections and their controllers, the study card's flip-back button and state
chip, and the recall card's duplicated truth line. A saved word's card offers
the two answers; an unsaved one offers keeping it.

Next: Phase 7, Listening and dictation. Backend gaps: `UI_BACKEND_GAPS.md`.

Open design gaps the prototype names itself: the 1024 tablet breakpoint (the
shell collapses to an icon sidebar), the processing state after submit, and
motion timing for flip, sheet entry, score count-up and feed swipe (tokens in
`foundation.css`).
