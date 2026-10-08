# Vocabulary Progressive Disclosure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recompose Vocabulary so its home is a compact summary, Library/Feed/Saved open deliberate browsing surfaces, and Study remains the only full-detail card experience.

**Architecture:** Keep the existing canonical vocabulary card, save path, and learner review state. Add a `library` UI view and a reusable horizontal Feed carousel renderer/binder; the Overview renders bounded previews only, while collection detail and Saved remain dense management views. Responsive behavior changes the carousel interaction model (four cards desktop, two tablet, one mobile) instead of collapsing all cards into a vertical page.

**Tech Stack:** Existing browser ESM modules, template-string renderers, CSS scroll-snap, current Orena theme tokens, Node contract tests, browser ESM validation, and the sandbox browser at port 8011.

**Spec:** Current human instruction “VOCABULARY LAYOUT CORRECTION — USE PROGRESSIVE DISCLOSURE”, `docs/product/ORENA_VOCABULARY_ARCHITECTURE.md`, `docs/project/DESIGN_CONTRACT.md`.

## Global Constraints

- `Library`, `Daily Feed`, `Saved Vocabulary`, and `Study` must reuse the existing canonical vocabulary identity, save path, progress/review foundation, and card projection.
- The Overview must render bounded previews: three collection tiles, up to five feed cards in one horizontal track, and a small saved/review preview.
- The Overview `View all collections` control must open a Library browsing view; it must not scroll to an in-page copy of the full catalog.
- Daily Feed must never wrap into multiple rows; use keyboard-accessible controls plus native horizontal scroll/swipe, with no autoplay.
- Desktop, tablet, and mobile must use deliberate carousel widths; mobile shows one feed card at a time and does not stack the feed vertically.
- No persistence, schema, migration, native/mobile, theme-token ownership, or unrelated Discover architecture changes.

---

### Task 1: Lock the progressive-disclosure contract with tests

**Files:**
- Modify: `scripts/test_orena_vocabulary_experience.mjs`
- Modify: `scripts/test_orena_vocabulary_library.mjs`
- Modify: `scripts/test_orena_vocabulary_feed.mjs`

**Interfaces:**
- Consumes the existing `renderVocabularyCollectionCard`, `renderVocabularyFeedPreview`, and `copy` contracts.
- Produces assertions for `renderVocabularyFeedCarousel(copy, cards, options)` and the Overview/Library/Feed source wiring used by later tasks.

- [ ] **Step 1: Write failing assertions** for a carousel track, bounded feed limit, dot/count controls, a `library` view, and a navigation handler that opens Library rather than calling `scrollIntoView`.
- [ ] **Step 2: Run the focused Node tests** and verify they fail because the carousel helper and Library view contract do not yet exist.
- [ ] **Step 3: Keep the assertions semantic**: one feed track, no grid requirement, no more than five Overview cards, and no rank labels; do not assert implementation-only whitespace.
- [ ] **Step 4: Run the focused tests again after implementation** and then run the existing vocabulary renderer/library/feed tests together.
- [ ] **Step 5: Commit** the test contract with `git add scripts/test_orena_vocabulary_experience.mjs scripts/test_orena_vocabulary_library.mjs scripts/test_orena_vocabulary_feed.mjs && git commit -m "test(vocabulary): define progressive disclosure layout contract"`.

### Task 2: Add reusable Feed carousel and separate Library view

**Files:**
- Modify: `static/orena/ui/vocabulary-experience.js`
- Modify: `static/orena/ui/expression.js`

**Interfaces:**
- `renderVocabularyFeedCarousel(copy, cards, { limit = 5, full = false } = {})` returns one `data-vocabulary-feed-carousel` wrapper with one `data-vocabulary-feed-track`, accessible previous/next controls, a position label, and dots.
- `bindVocabularyFeedCarousel(root)` binds controls to the nearest track, scrolls by one card, updates the position label/dots, and remains safe when no carousel exists.
- `renderLanguage()` adds `view === 'library'` and a `libraryView()` that renders all collection tiles in the expanded browsing surface.

- [ ] **Step 1: Implement the helper** with `cards.slice(0, limit)`, the existing `renderVocabularyFeedPreview` card renderer, stable indices, no autoplay, and a truthful empty state supplied by the caller.
- [ ] **Step 2: Implement the Library view** by reusing `renderVocabularyCollectionCard`; change Overview Library navigation to set `view = 'library'` and repaint.
- [ ] **Step 3: Change Overview output** to use `collections.slice(0, 3)`, `renderVocabularyFeedCarousel(copy, feedCards, { limit: 5 })`, and at most three recent saved rows; preserve Continue Review and the canonical save/review handlers.
- [ ] **Step 4: Bind the carousel and preserve interaction indices** for Overview and full Feed views; make Back from Library/Feed/Collection return to Overview and Back from Study return to the originating view.
- [ ] **Step 5: Run the focused Node tests** and verify the renderer/controller assertions pass.
- [ ] **Step 6: Commit** with `git add static/orena/ui/vocabulary-experience.js static/orena/ui/expression.js && git commit -m "feat(vocabulary): add compact overview and library view"`.

### Task 3: Reuse the carousel on Discover Feed

**Files:**
- Modify: `static/orena/ui/world.js`

**Interfaces:**
- `vocabularyFeedSection()` consumes `renderVocabularyFeedCarousel()` and exposes the same `data-vocabulary-feed-carousel` track/control contract.
- Discover's existing `paintVocabularyFeed()` calls `bindVocabularyFeedCarousel()` after repaint and retains `source_kind: 'feed'` save behavior.

- [ ] **Step 1: Replace the direct Feed card map** with the shared carousel helper while retaining loading, error, empty, and keep actions.
- [ ] **Step 2: Bind the shared carousel** in the Discover controller without changing the existing save endpoint or optimistic removal behavior.
- [ ] **Step 3: Run the Library and Feed Node tests** and verify EN/ZH wiring, save payloads, and truthful states remain green.
- [ ] **Step 4: Commit** with `git add static/orena/ui/world.js && git commit -m "refactor(vocabulary): share feed carousel on discover"`.

### Task 4: Implement responsive progressive-disclosure CSS

**Files:**
- Modify: `static/orena/world.css`

**Interfaces:**
- `.vocabulary-collection-grid` renders compact fixed-width tiles with no full-width desktop card.
- `.vocabulary-feed-carousel` contains one non-wrapping `.vocabulary-feed-preview` track; track children have stable widths for desktop, tablet, and mobile scroll-snap.
- `.vocabulary-feed-carousel__control`, position label, and dots retain Orena theme tokens, visible focus, and reduced-motion behavior.

- [ ] **Step 1: Write CSS assertions** for compact collection columns, horizontal overflow/snap, no wrapping, desktop four-card sizing, tablet two-card sizing, and mobile one-card sizing.
- [ ] **Step 2: Replace the feed grid rules** with a flex track and bounded card basis; keep `vocabulary-browse-grid` as the collection-detail management grid.
- [ ] **Step 3: Add responsive rules** at the existing Orena breakpoints: 3 collection tiles on wide desktop, 2 on tablet, 1 compact tile on mobile; feed track at 4/2/1 cards; overview hides extra collection preview tiles only as a visual fallback while Library still contains all collections.
- [ ] **Step 4: Add carousel control and dot styles** with theme-safe contrast, focus-visible outlines, touch scrolling, and reduced-motion scroll behavior.
- [ ] **Step 5: Run CSS/renderer tests and `git diff --check`**.
- [ ] **Step 6: Commit** with `git add static/orena/world.css scripts/test_orena_vocabulary_experience.mjs && git commit -m "style(vocabulary): make overview and feed progressively disclosed"`.

### Task 5: Browser verification and checkpoint

**Files:**
- Modify: `docs/project/CURRENT_HANDOFF.md`

**Interfaces:**
- No new application interface; verification covers the existing `#/language` route and the LAN-published sandbox.

- [ ] **Step 1: Run focused Node gates**, browser ESM validation, foundation/product gates, memory/architecture validation, Ruff, and the canonical Docker pytest command.
- [ ] **Step 2: Inspect the running route** at 1920px, 1024px, 800px, 390px, and 360px; verify Overview is bounded, Feed is one row, mobile shows one card, and Library opens as a separate view.
- [ ] **Step 3: Verify interaction flows**: open collection, browse/search, Study/flip, save, Saved management, Continue Review, Feed arrows/swipe/keyboard, EN/ZH, Paper/Night Ink, and reduced-motion-safe layout.
- [ ] **Step 4: Run independent review against the committed diff**; fix any Important findings and re-run affected tests.
- [ ] **Step 5: Update `CURRENT_HANDOFF.md`** with verified commit, tests, URLs, and `READY_FOR_HUMAN_UX_REVIEW`; do not record human approval.
- [ ] **Step 6: Commit** the handoff update with `git add docs/project/CURRENT_HANDOFF.md && git commit -m "docs(project): checkpoint vocabulary progressive disclosure"`.

## Self-review checklist

- Coverage: bounded Overview, separate Library, one-row Feed, desktop/tablet/mobile widths, saved/review continuity, EN/ZH, theme and accessibility checks are assigned above.
- Placeholder scan: no step depends on an unspecified function, dependency, schema, or future decision.
- Interface consistency: the carousel helper is defined once in `vocabulary-experience.js`; controllers only bind it and keep their existing save contracts.
- Architecture safety: no new persistence, duplicate vocabulary objects, duplicate scheduler, or new theme palette is introduced.
