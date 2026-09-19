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
| Progress | no route yet; "Your growth" in preferences | `ui/growth-summary.js` | `learnerSummary` | streak, weekly minutes, hours: no backend measure exists |
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
| Foundation: tokens, themes, type, primitives | yes | yes | yes | yes | n/a | theme switch | n/a | gates | Integrated |
| App shell and navigation | - | - | - | - | yes | - | - | - | Not started |
| Home | - | - | - | - | - | - | - | - | Not started |
| Library, search | - | - | - | - | - | - | - | - | Not started |
| Reading | - | - | - | - | - | - | - | - | Not started |
| Vocabulary, recall | - | - | - | - | - | - | - | - | Not started |
| Listening, dictation | - | - | - | - | - | - | - | - | Not started |
| Speaking | - | - | - | - | - | - | - | - | Not started |
| Writing | - | - | - | - | - | - | - | - | Not started |
| Progress | - | - | - | - | - | - | - | - | Not started |
| Profile, settings, onboarding | - | - | - | - | - | - | - | - | Not started |

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

Open design gaps the prototype names itself: the 1024 tablet breakpoint (the
shell collapses to an icon sidebar), the processing state after submit, and
motion timing for flip, sheet entry, score count-up and feed swipe (tokens in
`foundation.css`).
