# Vocabulary UX Redesign Implementation Plan

> **For agentic workers:** This plan is executed inline in the assigned
> `codex/work` lane. It ends at `READY_FOR_HUMAN_UX_REVIEW` and never claims
> human product approval.

**Goal:** Turn the existing Vocabulary surfaces into one learner experience
with three density levels: overview, compact browse/manage, and focused study.

**Architecture:** Keep `#/language`, the static curated catalog, the existing
SavedWord/review path, and the canonical Vocabulary Card projection. Add one
front-end vocabulary experience layer that renders overview summaries,
collection/feed previews, compact rows, and the study card; Discover reuses
the same renderers as a preview. Add only derived response metadata needed to
show truthful learner state; add no vocabulary tables, memberships, or second
review scheduler.

**Tech Stack:** Existing Orena browser ESM modules, `copy.js`, semantic theme
tokens, FastAPI/Python catalog routes, existing Node gates and pytest suite.

**Spec:** User-provided `VOCABULARY UX REDESIGN — CONSOLIDATED PRODUCT + VISUAL DIRECTION`.

## Global Constraints

- Vocabulary Library remains the curated catalog; saved vocabulary remains learner state.
- Library, Daily Feed, Saved Vocabulary, and Study reuse one identity/save/review/card foundation.
- Interface, support/native, and target language stay separate; no new canonical `translation_vi` contract.
- Real proficiency and visual rank are separate; mastery is derived from existing review evidence.
- No new persistence/schema for curated collections or UI state.
- EN/ZH parity, semantic theme tokens, reduced motion, keyboard access, and no horizontal overflow are required.
- Stop learner-facing work at `READY_FOR_HUMAN_UX_REVIEW` after automated and independent review.

## File Map

- Modify `writing_coach/becoming_library.py`: expose truthful saved-state summary counts.
- Modify `app.py`: attach derived collection progress and learner review metadata to catalog responses.
- Create `static/orena/ui/vocabulary-experience.js`: shared rank, mastery, state, compact row, collection, feed, overview, and study rendering helpers.
- Modify `static/orena/ui/vocabulary-card.js`: add the canonical focused study-card front/back projection.
- Modify `static/orena/ui/expression.js`: route `#/language` through the overview/manage/study controller.
- Modify `static/orena/ui/world.js`: make Discover Library/Feed previews compact and route to the shared workspace.
- Modify `static/orena/ui/copy.js`: add EN/ZH copy for overview, states, controls, filters, study, and rank metadata.
- Modify `static/orena/world.css`: add scoped vocabulary density, list, overview, feed, and study styles using existing tokens.
- Add `scripts/test_orena_vocabulary_experience.mjs`; extend vocabulary route tests for progress metadata.

## Ordered Tasks

### Task 1: Truthful state contract

- Add `learning`, `mastered`, and `saved` summary counts derived from existing rows.
- Enrich curated collection summaries/items with matching saved/review state without persisting collection membership.
- Add failing pytest assertions first, run them red, implement the smallest response change, then run the focused vocabulary suite.

### Task 2: Shared visual/domain helpers

- Add configurable level→rank mapping (`A1/D` through `C2/S+`, with HSK fallback) and `masteryStars` derived from `review_stage`.
- Add state labels (`New`, `Learning`, `Due`, `Mastered`) that remain readable without color.
- Add compact list row and study front/back renderers over the existing card projection.
- Add EN/ZH copy and Node tests for rank, stars, support-language meaning, state text, and escaping.

### Task 3: Vocabulary workspace vertical slice

- Replace the large saved-word grid with an overview containing summary metrics, Continue Review, compact library cards, feed preview, and recent saved words.
- Add compact saved/library management with search, state filters, level/framework metadata, stars, and Save/Open actions.
- Add focused study mode with front/back flip, audio hook where available, Save, Previous/Next, and existing Again/I remembered review actions.
- Keep all views in one controller/state model and preserve the existing API paths.

### Task 4: Discover parity

- Replace Discover's full card grids with compact curated collection and discovery previews.
- Reuse the same helper output and save payload; link “Open vocabulary” to `#/language`.
- Keep loading/error/empty states truthful and preserve independent repaint behavior.

### Task 5: Responsive and regression verification

- Add Node contract coverage and run the browser ESM/foundation/product/vocabulary gates.
- Run focused backend tests and the canonical local suite in the application image.
- Verify 1440/1024/800/390/360, EN/ZH, light/dark and at least two named themes; verify keyboard/focus/reduced-motion behavior.
- Perform independent diff review, fix findings, update handoff/status, and mark `READY_FOR_HUMAN_UX_REVIEW`.

## Human Review Checkpoint

Present these flows only after verification: Overview, curated collection,
search/filter/manage, Word Detail/Study, Save→My Language, continuous review,
Daily Feed, rank/mastery comprehension, EN/ZH/support-language separation, and
responsive mobile study controls.
