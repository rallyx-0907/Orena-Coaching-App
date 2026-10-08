# Vocabulary Card Browse Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> or superpowers:subagent-driven-development to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the rejected stretched browse rows with one compact, balanced
Vocabulary browse card shared by curated Library and Daily Feed while keeping
Saved Vocabulary dense and Study mode focused.

**Architecture:** Add a presentation-only `renderVocabularyBrowseCard()` beside
the existing canonical card renderers. Collection and Feed surfaces use that
one vertical card template and the existing vocabulary identity, save payload,
and review state; Saved management continues to use `renderVocabularyRow()`.
Rank, mastery, and review state remain separate attributes rendered through
semantic theme tokens, with no schema or persistence change.

**Tech Stack:** Browser-native ES modules, existing Orena semantic CSS tokens,
Node ESM contract tests, existing Docker-backed Python/pytest gate.

**Spec:** User-provided `VOCABULARY CARD + BROWSE UX CORRECTION`,
`docs/product/ORENA_VOCABULARY_ARCHITECTURE.md`, and
`docs/project/DESIGN_CONTRACT.md` §Learner-facing experience rules.

## Global Constraints

- Browse cards are compact, vertical, and use a 3–4 column desktop grid, 2 columns at tablet width, and 1 column on mobile.
- The target word is the strongest browse-card element; support meaning, pronunciation, metadata, mastery, state, and actions follow in that order.
- Rank is intrinsic presentation metadata (`A1 · D` through `C2 · S+`); mastery stars and review state remain independent and text-visible.
- Library, Daily Feed, Saved Vocabulary, and Study reuse the existing vocabulary identity, save path, review state, and card projection; no duplicate table, scheduler, or saved-word object is introduced.
- New UI copy remains interface-localized through `copy.js`; support meaning is selected through the existing support-language boundary and target content keeps its target-language `lang` attribute.
- The existing multi-theme semantic token owner remains `static/orena/theme.css`; no component-local palette or new theme is added.
- Do not touch `.env.example`, `mobile/`, production/preview services, or the `main` branch.

---

### Task 1: Lock the compact browse-card contract with failing tests

**Files:**
- Modify: `scripts/test_orena_vocabulary_experience.mjs`
- Modify: `scripts/test_orena_vocabulary_library.mjs`
- Modify: `scripts/test_orena_vocabulary_feed.mjs`

**Interfaces:**
- Consumes: the existing vocabulary fixture and copy objects.
- Produces: assertions for `renderVocabularyBrowseCard()` and the collection/feed section wiring.

- [x] **Step 1: Add the failing renderer assertions.** Import
  `renderVocabularyBrowseCard` and assert that an unsaved B1 card contains a
  vertical browse-card root, target word, support meaning, pronunciation,
  visible `B1 · B`, `★★☆`, `Study`, `+ Save`, and indexed study/save hooks.
  Assert that a saved card emits `Saved ✓` with `aria-pressed="true"` and
  does not emit the old feed-item root class.

- [x] **Step 2: Add the failing surface assertions.** Change the Library
  detail assertion to require `vocabulary-browse-card` and retain the save
  hook. Change the Feed assertion to require `vocabulary-browse-card` and
  retain the feed save hook. Assert that `world.js` imports and uses the
  shared browse renderer for collection detail.

- [x] **Step 3: Run the focused tests and confirm the failure is the missing
  structural renderer/wiring, not a test syntax error.**

  ```powershell
  node scripts/test_orena_vocabulary_experience.mjs
  node scripts/test_orena_vocabulary_library.mjs
  node scripts/test_orena_vocabulary_feed.mjs
  ```

  Expected: failure because `renderVocabularyBrowseCard` is not yet exported
  and the current surfaces still emit the old horizontal classes.

---

### Task 2: Implement one shared browse-card renderer and improve collection affordances

**Files:**
- Modify: `static/orena/ui/vocabulary-experience.js`
- Modify: `static/orena/ui/copy.js` only if a missing interface label is required by the renderer

**Interfaces:**
- Consumes: `copy`, projected Vocabulary Card objects, `index`, and the
  existing save-attribute option.
- Produces: `renderVocabularyBrowseCard(copy, card, { index, saveAttribute,
  source }) -> string`, preserving `data-vocabulary-study` and the caller's
  save hook.

- [x] **Step 1: Add `renderVocabularyBrowseCard()` with one stable hierarchy.**
  Render a `vocabulary-browse-card` article with rank data, level/rank label,
  rank badge, mastery stars, target-language headword, support-language short
  meaning, pronunciation when authored, optional part of speech/topic, a
  readable review-state label, and integrated Study / Save buttons. Use
  `compactSupportMeaning()` and `supportMeaning()` rather than adding a new
  translation or review path. Saved cards say `Saved ✓`, expose
  `aria-pressed="true"`, and keep the semantic state visible.

- [x] **Step 2: Keep `renderVocabularyRow()` as the dense management renderer.**
  Do not change its save payload or review semantics; only adjust its saved
  button text to the same explicit `Saved ✓` contract if needed for parity.

- [x] **Step 3: Make collection cards explicitly communicate their action.**
  Retain the collection-specific template and progress/stat hierarchy, and
  add a visible localized `Open →` affordance inside the existing full-card
  button without creating a word-card layout.

- [x] **Step 4: Run the Task 1 focused tests and confirm they pass.**

---

### Task 3: Recompose Library, Feed, and Discover around compact grids

**Files:**
- Modify: `static/orena/ui/expression.js`
- Modify: `static/orena/ui/world.js`

**Interfaces:**
- Consumes: `renderVocabularyBrowseCard()` and the existing `visibleItems`,
  `feedCards`, and `data-vocabulary-*` interaction pools.
- Produces: collection detail and Feed views whose card indices still map to
  the same save/study arrays, plus Discover’s catalog section using the same
  browse component.

- [x] **Step 1: Render collection management results as a browse-card grid.**
  Keep the existing search, filter, and sort toolbar. When `view ===
  'collection'`, map `visibleItems` through `renderVocabularyBrowseCard()`;
  when `view === 'saved'`, continue mapping through `renderVocabularyRow()`.

- [x] **Step 2: Render overview and full Feed through the same browse card.**
  Preserve the Feed’s stable/personalized API data and its existing save
  source kind. Do not add a second feed data set or change optimistic save
  behavior.

- [x] **Step 3: Update Discover’s open-collection section.**
  Import the shared browse renderer in `world.js` and render a compact grid
  with `data-library-keep` hooks. Keep the existing `vocabularyKeepPayload()`
  and API calls intact.

- [x] **Step 4: Run all Vocabulary Node gates.**

  ```powershell
  node scripts/test_orena_vocabulary_experience.mjs
  node scripts/test_orena_vocabulary_card.mjs
  node scripts/test_orena_vocabulary_library.mjs
  node scripts/test_orena_vocabulary_feed.mjs
  node scripts/test_orena_vocabulary_saved_card.mjs
  ```

---

### Task 4: Replace stretched visual geometry with semantic rank skins and responsive density

**Files:**
- Modify: `static/orena/world.css`

**Interfaces:**
- Consumes: existing `data-vocabulary-rank`, theme semantic tokens, and
  reduced-motion behavior.
- Produces: balanced browse cards, compact collection cards, 4/3-column wide
  grids, 2-column tablet grids, 1-column mobile grids, and a focused Study
  surface that remains visually distinct from browse.

- [x] **Step 1: Add the browse-card layout rules.** Use a consistent minimum
  height, internal padding, vertical flex layout, target-word emphasis,
  meaning/pronunciation metadata grouping, a bottom action row, and a
  restrained rank frame/background treatment. Keep action buttons at the
  existing Orena touch sizes and add visible focus states.

- [x] **Step 2: Map every rank to the existing semantic tokens.** Apply the
  D/C/B/A/S/S+ rank mapping to collection, browse, and Study surfaces. Keep
  rank text and mastery stars visible so color is never the only signal. Use a
  subtle S+ accent treatment and no new arbitrary color variables.

- [x] **Step 3: Set responsive grids and management behavior.** Use four browse
  columns at wide desktop where space permits, three or two through the
  existing breakpoints, and one on mobile. Keep Saved rows dense and let
  compact card actions stay side-by-side without horizontal overflow.

- [x] **Step 4: Preserve reduced-motion behavior.** Any hover lift or transition
  must be disabled by the existing `prefers-reduced-motion: reduce` rules;
  Study flip remains understandable without animation.

- [x] **Step 5: Run the foundation and product CSS gates.**

  ```powershell
  node scripts/test_orena_foundation.mjs
  node scripts/test_orena_product.mjs
  node --experimental-vm-modules scripts/validate_browser_esm_graph.mjs
  ```

---

### Task 5: Independent verification, browser review checkpoint, and handoff

**Files:**
- Modify: `docs/project/CURRENT_HANDOFF.md` only if verified milestone text,
  route, or evidence changes
- Modify: no unrelated files

- [x] **Step 1: Run `git diff --check` and inspect the final diff.** Confirm
  `.env.example` remains the only pre-existing unrelated working-tree edit.

- [x] **Step 2: Run the canonical local test recipe in the application image.**
  Compare the failure set with the handoff baseline and label the result
  local execution, not CI.

- [x] **Step 3: Independently review the implementation against this plan.**
  Verify the browse/management/study separation, rank/mastery/state
  independence, save hooks, EN/ZH copy, support/target language boundaries,
  and absence of schema or duplicate learning infrastructure. Fix and rerun
  any Important finding before handoff.

- [x] **Step 4: Verify the running LAN sandbox at
  `http://127.0.0.1:8011/#/language` and the LAN address on port `8011`.**
  Check Overview → collection → compact card grid → Study/flip → Save state →
  Saved management → Feed, in EN and ZH where available; inspect desktop,
  tablet, mobile, Paper, and Night Ink behavior and keyboard focus.

- [x] **Step 5: Commit only the coherent task files with message**
  `feat(vocabulary): replace stretched browse rows with compact cards`.

- [x] **Step 6: Leave the learner-facing milestone at
  `READY_FOR_HUMAN_UX_REVIEW`.** Human review covers the specified learner
  flows and visual quality only; do not claim `APPROVED`.

---

## Self-review checklist

- [x] The plan does not introduce a new vocabulary object, SavedWord table,
  review scheduler, or persistence decision.
- [x] Collection detail no longer renders 600/3000 words as stretched rows;
  Saved management alone keeps dense rows.
- [x] Feed and Library share the browse renderer and existing save hooks.
- [x] Study retains the canonical full card and continuous review controls.
- [x] All rank labels and 1–3 mastery stars remain readable without color.
- [x] EN/ZH interface copy and support/target `lang` boundaries remain intact.
- [x] Responsive and reduced-motion requirements have explicit verification.
- [x] Human UX review is the final checkpoint, not an agent approval.
