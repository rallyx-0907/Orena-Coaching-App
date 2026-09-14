# Orena Vocabulary Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> or superpowers:subagent-driven-development to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Task 0 is a
> **documentation-only** deliverable and is the hard stop for this plan's own
> authorization: no task after it may begin until Task 0's proposal has been
> through the independent architecture-review gate `AGENTS.md` §1 names and
> received explicit human schema/runtime authorization, exactly as I2 and I3
> did (`docs/project/I2_SCHEMA_REVIEW_REQUEST.md`,
> `docs/project/I3_SCHEMA_REVIEW_REQUEST.md`).

**Goal:** Sequence the two approved learner-facing Vocabulary surfaces —
**Vocabulary Library** (a real curated library the learner browses and owns)
and **Daily Vocabulary Feed** (a small distribution surface that offers new
candidate words and hands them into the same save/review path) — on top of
one shared vocabulary/review foundation, per
`docs/product/ORENA_VOCABULARY_ARCHITECTURE.md` and the Golden Star content
sequence in `docs/project/ROADMAP.md`. This plan is the deliverable; it does
not implement either surface.

**Architecture:** Both surfaces read and write through the existing saved-word
seam — `writing_coach/persistence/models.py:SavedWord`,
`writing_coach/persistence/specialized_repository.py`'s
`list_library_records`/`save_library_record`/`get_library_progress`/
`update_library_review`/`delete_library_record`, and
`writing_coach/becoming_library.py`'s service functions
(`list_library_vocabulary`, `save_library_vocabulary`,
`review_library_vocabulary`, `delete_library_vocabulary`) — exposed at
`/api/library/vocabulary` in `app.py`. `writing_coach/vocabulary_cards.py`
already projects one saved-word row into an Orena Vocabulary Card without a
second persistence path; `static/orena/ui/vocabulary-card.js` already renders
that projection. Neither surface gets a private save path, a private review
scheduler, or a private card shape:

```text
                 saved_words (+ vocabulary_learning on SQLite)
                              |
                 becoming_library.py (save / review / delete)
                              |
                 vocabulary_cards.py (pure card projection)
                              |
              --------------------------------------
              |                                      |
   Vocabulary Library (#/language)      Daily Vocabulary Feed (Discover)
   existing renderLanguage() surface    new read-only candidate surface;
   in static/orena/ui/expression.js     "keep" action calls the *same*
                                        save_library_vocabulary path
```

Curated named topic collections (Airport English, HSK sets, and so on, per
`ORENA_VOCABULARY_ARCHITECTURE.md` §1) and orthography's static reference data
are the two places this sequence needs something the current schema does not
have. Task 0 proposes that persistence; every other task in this plan is
scoped to run **without** it, using only what `saved_words` and the existing
static-asset pattern (the closed R5 Grammar KB) already support.

**Tech stack:** FastAPI/Pydantic (`app.py`,
`writing_coach/becoming_library.py`), the existing
`SpecializedLearningRepository` PostgreSQL/SQLite dual implementation
(`writing_coach/persistence/specialized_repository.py`), browser-native ES
modules (`static/orena/ui/*.js`), Node ESM contract tests
(`scripts/test_orena_*.mjs`), pytest.

**Spec paths:**
- `docs/product/ORENA_VOCABULARY_ARCHITECTURE.md` (card shape, orthography,
  identity seam, scale)
- `docs/product/ORENA_CONTENT_ARCHITECTURE.md` §3-4, §9, §17 (Discover as a
  distribution surface, shared infrastructure, scale philosophy)
- `docs/product/ORENA_COLLECTION_ARCHITECTURE.md` (`LanguageItemRef`,
  `CollectionEntry`, retrieval seam)
- `docs/product/ORENA_EVIDENCE_ARCHITECTURE.md` §1, §4 (My Language evidence
  claims, Discover ranking boundary)
- `docs/product/ORENA_CONTENT_EXECUTION_ARCHITECTURE.md` §1, §3 (admission,
  expensive-operation/job contract for anything generated)
- `docs/project/ROADMAP.md` "Golden Star / Content Domain program" §Sequence
  items 3-4 (Vocabulary Card, then orthography, Chinese first)
- `docs/product/ORENA_UNDERSTANDING_ENGINE.md` §2, §4 (AI-first, the
  mental-model/mnemonic/etymology accuracy rule orthography inherits)

**Global constraints:**
- No new table, column, or migration ships in this plan. `Task 0` is a
  proposal document only; nothing after it may add schema before that
  proposal clears independent architecture review and explicit human
  authorization (`AGENTS.md` §1).
- No provider/credential activation. Any generation (an example sentence, a
  core-semantic image) already goes through the existing capability/provider
  control plane; this plan does not add a new provider integration.
- One shared save/review path. Neither surface may create a second
  `SavedWord`-equivalent row, a second review scheduler, or a second card
  shape. `vocabulary_card_from_saved_word` remains the only card projection.
- EN/ZH ship together in every task; no English-first task followed by a
  promised Chinese follow-up.
- Reuse the closed R5 pattern (static Grammar KB, no runtime AI, no DB) for
  any static reference dataset a task needs; do not invent a new asset
  pipeline.
- Every task stops at `REVIEWABLE`; only the human sets `APPROVED`
  (`AGENTS.md` §9).
- Stage only the files each task names.

---

## Why one foundation, two surfaces, and not three vocabulary systems

`ORENA_VOCABULARY_ARCHITECTURE.md` §3 is explicit that a Vocabulary Card is
"the canonical library object" and the saved relationship is "the existing
`LanguageItemRef`/`SavedWord` object" — enriching the card "does not change
that a save is a relationship, not a new origin." That rule is what keeps
Library and Feed from becoming two products:

- **Vocabulary Library** is the learner's own durable collection: every word
  they have ever saved, grouped and reviewable, rendered today by
  `renderLanguage()` in `static/orena/ui/expression.js:350` against
  `GET /api/library/vocabulary`. This plan's Library tasks make that existing
  surface explicitly the Library destination and prepare it to display
  curated-collection membership once Task 0's schema is authorized — they do
  not rebuild it.
- **Daily Vocabulary Feed** is a *Discover*-style distribution surface per
  `ORENA_CONTENT_ARCHITECTURE.md` §3: "Discover and Home must surface
  publishable content from the domain libraries... They must not own
  hard-coded canonical content of their own." A Feed candidate is not yet a
  `SavedWord`; it becomes one, through the *same* `save_library_vocabulary`
  call Library already uses, the moment the learner keeps it. There is no
  Feed-only save table.
- The **shared foundation** is `becoming_library.py` + `vocabulary_cards.py` +
  `SpecializedLearningRepository`. Both surfaces read a Vocabulary Card
  through `vocabulary_card_from_saved_word`; only Library reads it from a row
  that already exists, and only Feed reads it from a row that does not exist
  yet (§ Task 2 defines that candidate shape honestly, as `generated` origin,
  never as a disguised `SavedWord`).

This produces two surfaces and one save/review/card system, matching the
"separate learning domains, shared platform infrastructure" rule in
`ORENA_CONTENT_ARCHITECTURE.md` §1 applied one level down, inside Vocabulary
itself.

## What this plan explicitly does not authorize

- No curated named topic collection (Airport English, HSK sets, imported
  collections) ships as real persisted data. `ORENA_VOCABULARY_ARCHITECTURE.md`
  §1 requires them; `ORENA_COLLECTION_ARCHITECTURE.md` has no
  `CollectionEntry`-equivalent concept for "named curated set membership"
  today, and inventing one is schema work. Task 0 proposes it; nothing
  implements it here.
- No handwriting-scoring extension to orthography (explicitly deferred as "not
  a commitment to ship" in `ORENA_VOCABULARY_ARCHITECTURE.md` §4).
- No Reading/Listening rights or library-content expansion. Feed candidates in
  this plan are Orena-generated or hand-curated seed cards with truthful
  `origin: generated` provenance (`ORENA_CONTENT_ARCHITECTURE.md` §2), never a
  claim of sourcing from a specific copyrighted Reading/Listening item.
- No new destination. Per the eleven-destination map in
  `ORENA_REFERENCE_ARCHITECTURE.md` and the "no folders implicitly" rule in
  `ORENA_COLLECTION_ARCHITECTURE.md` §2, Daily Vocabulary Feed is a page
  inside the existing `discover` destination group
  (`static/orena/ui/world.js:renderWorld`), not a twelfth destination.

---

### Task 0: Architecture proposal — curated collection and orthography persistence

**Status: documentation only. Stops before implementation. Requires
independent architecture review and explicit human authorization before any
later task in this plan that depends on it may begin.**

**Files:**
- Create: `docs/project/VOCABULARY_SCHEMA_REVIEW_REQUEST.md` (follow the exact
  shape of `docs/project/I3_SCHEMA_REVIEW_REQUEST.md`: proposed tables,
  migration plan, rollback, independent reviewer sign-off block)

**Scope of the proposal (not authorized by writing it):**
- A `VocabularyCollection` identity (curated/imported/learner-created origin,
  title, topic, learning language, rights/provenance per
  `ORENA_CONTENT_ARCHITECTURE.md` §16) and a membership row joining a
  `SavedWord`/future Vocabulary Card identity to zero or more collections —
  additive to `SavedWord`, not a replacement, per
  `ORENA_COLLECTION_ARCHITECTURE.md` §2's "one membership identity per
  relationship/scope."
- Whether orthography's stroke/animation data needs *any* database row at all,
  or stays a static bundled asset keyed by character (recommended finding,
  see Task 5) — the proposal must answer this explicitly rather than defaulting
  to a table out of habit.
- Explicit non-goals: no Reading/Listening rights expansion, no account/schema
  changes outside Vocabulary, no activation of I2's account backbone.

- [ ] **Step 1:** Draft the proposal following the same reviewed-schema
  pattern I2 and I3 already used in practice — proposal document, delegated
  independent architecture review round(s) recorded in Git, sandbox-only
  application after a verified backup and restore rehearsal, explicit human
  authorization before any further activation
  (`docs/project/I2_SCHEMA_REVIEW_REQUEST.md`,
  `docs/project/I3_SCHEMA_REVIEW_REQUEST.md`,
  `docs/project/I2_ACTIVATION_RUNBOOK.md` §7) — consistent with, but not a
  quotation of, `ORENA_BACKBONE_INTEGRATION_GATES.md`'s "reviewed additive
  migrations" discipline in its migration/activation order and its D-054
  independent-review hard gate.
- [ ] **Step 2:** Request delegated architecture review (`AGENTS.md`
  "Architecture review authority") from GPT-6/Codex, or a delegated reviewer
  if unavailable, recording reviewer identity, reviewed commit and outcome in
  Git per that section's requirement.
- [ ] **Step 3:** Commit `docs(vocabulary): propose collection/orthography schema`
  only after the document is complete; this commit does not touch
  `CURRENT_HANDOFF.md` (a later, separate governance-update commit records the
  outcome once reviewed, per `PROJECT_MEMORY.md`).

**Acceptance criteria:** proposal exists, is independently reviewed, and its
outcome (approved / changes requested / rejected) is recorded in Git before
Task 3b or Task 6 (below) starts implementation.

---

### Task 1: Shared source-kind vocabulary fix (prerequisite for Task 3)

**Why first:** `LibraryVocabularyIn.source_kind` in
`writing_coach/becoming_library.py:29-32` only accepts
`manual|dictionary|feedback|strength`. `tests/test_collection_query.py:60` and
`tests/test_vocabulary_cards.py:16` already exercise `source_kind: "reading"`
against the repository/card-projection layer directly, bypassing that
Pydantic gate — the public save endpoint's contract is already narrower than
values the system truthfully produces. Daily Feed needs a fifth truthful
value (`feed`) for the same reason `reading` already exists: so a learner and
any future audit can see *how* a word entered their library, per
`ORENA_COLLECTION_ARCHITECTURE.md` §2's "Reason is the shared KEEP_REASONS
vocabulary, not fabricated evidence."

**Files:**
- Modify: `writing_coach/becoming_library.py`
  (`LibraryVocabularyIn.source_kind` pattern)
- Modify: `writing_coach/becoming_library_selftest.py` if it asserts the old
  pattern literal
- Test: `tests/test_becoming_library_source_kind.py` (new)

**Interfaces:**
- `LibraryVocabularyIn.source_kind: str` pattern becomes
  `^(manual|dictionary|feedback|strength|reading|feed)$`. No other field of
  `LibraryVocabularyIn` or `_row_to_item` changes.

- [ ] **Step 1: Write failing tests.** Assert `POST /api/library/vocabulary`
  accepts `source_kind="feed"` and `source_kind="reading"` and rejects an
  unrecognized value (e.g. `"listening"` should still 422 until a later,
  explicit task adds it — no silent wildcard).
- [ ] **Step 2: Run and confirm failure** inside the canonical Docker test
  recipe (`AGENTS.md` §9):
  `python -m pytest -q tests/test_becoming_library_source_kind.py`
- [ ] **Step 3: Widen the pattern.** One-line change; no other behavior.
- [ ] **Step 4: Run the full existing vocabulary suite** to confirm no
  regression: `python -m pytest -q tests/test_becoming_library_source_kind.py
  tests/test_vocabulary_cards.py tests/test_collection_query.py`
- [ ] **Step 5: Commit** `fix(vocabulary): accept the reading and feed source
  kinds the system already produces`

---

### Task 2: Feed candidate card — pure, unsaved, truthfully generated

**Files:**
- Create: `writing_coach/vocabulary_feed.py`
- Create: `data/vocabulary_feed_seed.json` (hand-authored seed set; explicitly
  the "starting seam" `ORENA_CONTENT_ARCHITECTURE.md` §17 allows, not the
  target end-state — flag this in the module docstring so no later worker
  mistakes it for the curated-library pipeline)
- Test: `tests/test_vocabulary_feed.py`

**Interfaces:**
- `FeedCandidateIn`/seed row shape:
  `{word, language_code, phonetic, part_of_speech, definition, translation_vi,
  topic, origin: "generated"}` — no `source_essay_id` (a Feed candidate has no
  learner encounter yet; `source_kind` for the resulting save is `"feed"` from
  Task 1, set only at save time, not stored on the seed row).
- `daily_feed_candidates(language_code: str, exclude_normalized: set[str],
  count: int = 5) -> list[dict]`: deterministic selection (date-seeded, not
  random-per-request, so the same learner sees the same feed within a day),
  filtered to exclude words already in `exclude_normalized` (today's saved
  set) so Feed never re-offers a word the learner already keeps.
- `vocabulary_card_from_feed_candidate(row) -> dict`: thin wrapper around the
  existing `vocabulary_card_from_saved_word` in `writing_coach/vocabulary_cards.py`
  — build the same `Mapping[str, Any]` shape with `review_stage` absent
  (candidate has no memory state yet) rather than duplicating card-shaping
  logic.

- [ ] **Step 1: Write failing tests.** Assert: candidates exclude any
  normalized word already present in the learner's saved set; the same
  `(language_code, date)` pair returns the same ordered candidates
  (determinism); a candidate card built via
  `vocabulary_card_from_feed_candidate` has no `memory` field claiming review
  history that does not exist yet (compare against
  `vocabulary_card_from_saved_word`'s existing "does not invent empty fields"
  test in `tests/test_vocabulary_cards.py`); EN and ZH seed rows both exist
  and both produce valid cards, including a ZH row with `orthography=None`
  (Task 5 supplies real orthography later — this task must not fabricate it).
- [ ] **Step 2: Run and confirm failure**:
  `python -m pytest -q tests/test_vocabulary_feed.py`
- [ ] **Step 3: Author the seed data.** At least 20 EN and 20 ZH rows, each
  with a real, checkable definition/translation (no placeholder text) and a
  `topic` value drawn from `ORENA_VOCABULARY_ARCHITECTURE.md` §1's example
  list (Airport English, Workplace English, Technology, Emotions, Phrasal
  Verbs, HSK topic sets). Implement the selector and wrapper.
- [ ] **Step 4: Pass the new tests, then the existing card-projection suite**:
  `python -m pytest -q tests/test_vocabulary_feed.py tests/test_vocabulary_cards.py`
- [ ] **Step 5: Commit** `feat(vocabulary): add a deterministic Daily Feed
  candidate source`

---

### Task 3: Feed API surface and the "keep" handoff into Library

**Files:**
- Modify: `app.py` (one new route)
- Modify: `writing_coach/vocabulary_feed.py` (repository-scoped wrapper reading
  the learner's current saved set for exclusion)
- Test: `tests/test_vocabulary_feed_route.py`

**Interfaces:**
- `GET /api/vocabulary/feed?language_code=en|zh` (name:
  `becoming_vocabulary_feed`) → `{items: [<card>, ...], date: "YYYY-MM-DD"}`
  using `list_library_vocabulary()`'s existing repository read to build the
  exclusion set, then `daily_feed_candidates` + `vocabulary_card_from_feed_candidate`.
  No new repository method: this route composes two already-tested functions.
- **"Keep" reuses the existing save route unmodified.** The client calls
  `POST /api/library/vocabulary` (already exists) with
  `source_kind="feed"` (now valid per Task 1) and the candidate's own
  word/phonetic/part_of_speech/definition/translation_vi fields. This task
  adds no new save endpoint.

- [ ] **Step 1: Write failing route test.** Assert the route excludes an
  already-saved word (seed the test DB with one saved word matching a known
  seed entry, confirm it is absent from the response); assert
  `language_code` is required and an unsupported value is a clean 4xx, not a
  silent empty list; assert the response never includes a `memory` claim (see
  Task 2's determinism/no-invented-field test) and never includes an internal
  seed-file path or identifier a learner should not see.
- [ ] **Step 2: Run and confirm failure**:
  `python -m pytest -q tests/test_vocabulary_feed_route.py`
- [ ] **Step 3: Implement the route** in `app.py`, next to the existing
  `# === BECOMING VOCABULARY LIBRARY ROUTES ===` block but in its own
  `# === BECOMING VOCABULARY FEED ROUTES ===` block so the two stay visibly
  distinct in code the way they are distinct as surfaces.
- [ ] **Step 4: Pass this test plus the full vocabulary suite**:
  `python -m pytest -q tests/test_vocabulary_feed_route.py tests/test_vocabulary_feed.py tests/test_becoming_library_source_kind.py tests/test_vocabulary_cards.py`
- [ ] **Step 5: Commit** `feat(vocabulary): add the Daily Feed read route`

---

### Task 4: Daily Vocabulary Feed UI (Discover surface)

**Files:**
- Modify: `static/orena/infrastructure/api.js` (one client call:
  `dailyVocabularyFeed(languageCode)`, mirroring the existing
  `libraryVocabulary()`/`saveLibraryVocabulary()` pattern at
  `static/orena/infrastructure/api.js:105-118`)
- Modify: `static/orena/ui/world.js` (`renderWorld`'s `discover` branch gains
  a Feed section; no new destination, no new top-level route)
- Modify: `static/orena/ui/copy.js` (EN/ZH strings for the Feed section
  heading, empty state, and "keep" action — reuse existing `c.keep`-style
  naming conventions already in that file rather than inventing new ones)
- Test: `scripts/test_orena_vocabulary_feed.mjs` (new, Node ESM, same style as
  `scripts/test_orena_vocabulary_card.mjs`)

**Interfaces:**
- `renderWorld` discover branch renders each candidate through the *existing*
  `renderVocabularyCard` from `static/orena/ui/vocabulary-card.js` — same
  function Library already uses — with a `slots.after` action button that
  calls `api.saveLibraryVocabulary({..., source_kind: 'feed'})` (Task 1/3),
  then removes that card from the in-memory feed list (no full reload needed,
  matching the existing optimistic-update pattern already used elsewhere in
  `expression.js`'s recall grading).
- No orthography rendering claim yet for Feed ZH candidates until Task 5
  ships; `vocabulary-card.js`'s existing `orthographyMarkup` already
  no-ops safely when `card.orthography` is absent (verified in
  `static/orena/ui/vocabulary-card.js:27-38`), so this task requires no
  defensive change there.

- [ ] **Step 1: Write the failing Node contract test.** Assert the rendered
  Feed section reuses `renderVocabularyCard` (not a parallel markup builder);
  assert the empty state (no candidates left today) renders a truthful
  message, not a spinner or silent blank.
- [ ] **Step 2: Run and confirm failure**: `node scripts/test_orena_vocabulary_feed.mjs`
- [ ] **Step 3: Implement.** Keep the branch small: fetch, render cards,
  wire the keep action, EN/ZH copy.
- [ ] **Step 4: Add this test to `.github/workflows/ci.yml`'s Node block**,
  in the same edit noting that `scripts/test_orena_vocabulary_card.mjs`
  itself is not currently listed there either — add both in this task rather
  than leaving the pre-existing gap for a future worker to rediscover.
- [ ] **Step 5: Pass locally**:
  `node scripts/test_orena_vocabulary_card.mjs && node scripts/test_orena_vocabulary_feed.mjs`
- [ ] **Step 6: Responsive/accessibility checkpoint** (manual, browser-based,
  before marking `REVIEWABLE`): 1024px, 800px, 390px and 360px widths, EN and
  ZH, light and dark appearance in at least two registered themes, keyboard
  reachability of the "keep" action, and screen-reader label parity with the
  existing Library card's provenance/"look closer" pattern
  (`static/orena/ui/expression.js:386-389`).
- [ ] **Step 7: Commit** `feat(vocabulary): add the Daily Vocabulary Feed to
  Discover`

---

### Task 5: Chinese orthography — projection over the existing stroke-order capability (no new dataset, no schema)

**The repository already has the canonical Chinese stroke-order capability.**
`writing_coach/languages/chinese/stroke_order.py`'s `stroke_order_for`/
`character_strokes`, the vendored Make Me a Hanzi pack at
`writing_coach/languages/chinese/stroke_data/` (provenance and license already
recorded in `writing_coach/languages/chinese/stroke_data/README.md`), the
route `GET /api/chinese/stroke-order` in `app.py`, its client stub
`chineseStrokeOrder(word)` in `static/orena/infrastructure/api.js:104`, and
`tests/test_chinese_stroke_order.py` are that capability, already shipped and
already tested. This task does not vendor a second copy of that dataset and
does not build a parallel adapter next to it — per
`ORENA_VOCABULARY_ARCHITECTURE.md` §4, "the internal capability name is the
general `orthography`, never a language-hardcoded name such as
`chinese_stroke_order`... a script-specific renderer is a language adapter
over this one capability." This task is that generalization step: a thin
projection from the existing capability's output shape into the card
`orthography` shape, not a new implementation of stroke lookup.

**Depends on:** Task 0's finding that orthography data does not require a
database row (expected outcome, per the recommendation in Task 0's scope, and
consistent with the fact that the existing stroke-order capability already
works entirely off a bundled static pack with no table); if Task 0's review
instead concludes a row is required, this task is blocked until that schema
is authorized, and must not proceed on the static-asset assumption below.

**Files:**
- Modify: `writing_coach/vocabulary_cards.py` — no signature change; the
  existing `orthography: Mapping[str, Any] | None = None` parameter to
  `vocabulary_card_from_saved_word` already accepts exactly the projected
  shape (see `tests/test_vocabulary_cards.py:53-75`, which already asserts a
  `{script, characters, source, source_version}` shape sourced from
  `"make-me-a-hanzi"` / `"hanzi-writer-data-2.0.1"` — this task fulfills a
  contract the test suite already committed to, it does not invent one)
- Modify: `writing_coach/languages/chinese/stroke_order.py` only if Step 1's
  tests show the projection needs a return value `stroke_order_for` does not
  already expose (e.g. a `script` tag) — prefer adding that at the source over
  reshaping it twice; otherwise this file is read-only for this task
- Create: a single small projection function, `orthography_for_word(word: str,
  language_code: str) -> dict | None`, placed either as a function in
  `writing_coach/vocabulary_cards.py` next to `vocabulary_card_from_saved_word`
  or as the one-function module `writing_coach/orthography.py` that
  `ORENA_VOCABULARY_ARCHITECTURE.md` §4 names as the general capability seam
  (decide in Step 3) — either way it **imports and calls**
  `writing_coach.languages.chinese.stroke_order.stroke_order_for`, it does not
  reimplement stroke lookup, index reads, or pack decompression
- Test: `tests/test_orthography_projection.py` (new, scoped to the projection
  only — stroke-data correctness itself stays covered by the existing
  `tests/test_chinese_stroke_order.py`, which this task does not duplicate)

**Interfaces:**
- `orthography_for_word(word: str, language_code: str) -> dict | None`: for
  `language_code == "zh"`, calls the existing
  `stroke_order.stroke_order_for(word)` and projects its result into the card
  shape `{script: "han", characters: [...], source, source_version}`, using
  `stroke_order.SOURCE_VERSION` and the same `"make-me-a-hanzi"` literal
  `stroke_order_for` already returns (imported/referenced, not restated, so
  the two cannot drift). Returns `None` for any `language_code != "zh"`, and
  `None` (not an empty `characters: []`) when every character in `word` comes
  back in `stroke_order_for`'s `unavailable` list, per
  `ORENA_VOCABULARY_ARCHITECTURE.md` §2's "a card must not invent a value
  merely to fill an unused field."
- No new stroke lookup, no new index, no new pack file, no
  `character_strokes`/`stroke_order_for` reimplementation, and no new
  `data/orthography/han/` (or similar) dataset directory. This function only
  reshapes output already produced by the existing module.
- Wire into `becoming_library.py`'s `_row_to_item` or a dedicated card-fetch
  route (decide during Step 3 based on where the ZH-only cost belongs — do not
  compute orthography for English rows).

- [ ] **Step 1: Write failing tests.** Assert a known multi-character ZH word
  (e.g. `休息`, matching the illustrative shape in
  `ORENA_VOCABULARY_ARCHITECTURE.md` §4) returns per-character radical/stroke
  data with `script: "han"`; assert an EN word returns `None`; assert a ZH
  word entirely absent from the vendored dataset returns `None` for the whole
  card's orthography rather than a partially fabricated entry; assert
  `source`/`source_version` come from `stroke_order.SOURCE_VERSION` and match
  exactly what `GET /api/chinese/stroke-order` already returns for the same
  word (no independent literal to drift); assert the projection calls into
  `stroke_order.stroke_order_for`/`character_strokes` rather than reading
  `writing_coach/languages/chinese/stroke_data/` itself (monkeypatch the
  existing module's function and confirm the projection calls it).
- [ ] **Step 2: Run and confirm failure**:
  `python -m pytest -q tests/test_orthography_projection.py`
- [ ] **Step 3: Implement the projection function only.** No dataset
  vendoring, no new file tree: reuse
  `writing_coach/languages/chinese/stroke_data/` exactly as it stands, with
  its existing `README.md` provenance record unmodified. Decide the function's
  final home (`vocabulary_cards.py` vs. a one-function
  `writing_coach/orthography.py`) here, not before.
- [ ] **Step 4: Wire the Vocabulary Library and Feed card responses** to
  include orthography for ZH rows only, reusing the existing
  `vocabulary_card_from_saved_word(row, orthography=...)` parameter — no
  change to that function's contract.
- [ ] **Step 5: Pass the full vocabulary suite plus the existing stroke-order
  suite** (confirming the existing capability is untouched, not just the new
  wrapper):
  `python -m pytest -q tests/test_orthography_projection.py tests/test_chinese_stroke_order.py tests/test_vocabulary_cards.py tests/test_vocabulary_feed.py tests/test_becoming_library_source_kind.py`
- [ ] **Step 6: Verify `static/orena/ui/vocabulary-card.js`'s existing
  `orthographyMarkup`** renders the projected real data correctly in the
  browser (Library and Feed, ZH profile, both themes) — this function already
  exists and is already tested against a synthetic fixture
  (`scripts/test_orena_vocabulary_card.mjs`); this step is verification, not
  new implementation. Confirm the card response and the existing
  `chineseStrokeOrder` client stub are not now two divergent contracts for the
  same data — the card embeds the projection server-side; nothing in this
  task changes what `GET /api/chinese/stroke-order` itself returns.
- [ ] **Step 7: Chinese-first validation checkpoint.** Confirm stroke order
  sequencing (not just stroke count) renders correctly for at least one
  compound character with a non-obvious stroke order, and that the accuracy
  rule in `ORENA_UNDERSTANDING_ENGINE.md` §4 is respected: this task ships
  verified structural data only, no mnemonic or etymology text, so there is
  nothing here to mislabel — record that explicitly in the commit message so
  a later task adding mnemonics knows this task's data is not itself a
  mnemonic source.
- [ ] **Step 8: Commit** `feat(vocabulary): project the existing Chinese
  stroke-order capability into orthography cards`

---

### Task 6: Curated named collections (implementation) — blocked on Task 0

**Do not start this task until Task 0's proposal is independently reviewed
and explicitly human-authorized.** Listed here only to preserve sequencing
and prevent a later worker from starting curated-collection implementation
without that gate. Its own files, interfaces, migration plan and acceptance
criteria are defined by whatever Task 0's approved proposal specifies — this
plan does not pre-author them, since doing so would be exactly the kind of
schema-authorized-in-passing this plan's global constraints forbid.

---

## Rights and provenance boundaries (applies to Tasks 2-5)

- Feed seed cards (Task 2) are `origin: generated` — hand-authored by this
  plan's implementer, truthfully labeled, never presented as sourced from a
  specific external text (`ORENA_CONTENT_ARCHITECTURE.md` §2, §16).
- The orthography data Task 5 projects (Task 5 adds no new dataset of its own)
  is the already-vendored external reference data at
  `writing_coach/languages/chinese/stroke_data/`, with its license and
  provenance already recorded in that directory's `README.md`; it is cited by
  name/version on every card that uses it (already the shape
  `tests/test_vocabulary_cards.py` expects), per §16's "preserve appropriate
  source and provenance information."
- Neither surface acquires Reading/Listening rights. A future Task 9 (not in
  this plan) connecting Feed candidates to real Reading/Listening encounters
  is out of scope here and would need its own rights review under
  `ORENA_CONTENT_EXECUTION_ARCHITECTURE.md` §1.

## Provider/ingestion dependencies

- Tasks 1-5 need no provider activation: Task 2's seed data and Task 5's
  stroke dataset are both static, and Task 3/4 compose only existing,
  already-deployed routes and functions.
- A future capability-generated field (an example sentence, a core-semantic
  image per `ORENA_VOCABULARY_ARCHITECTURE.md` §2) would go through the
  existing expensive-operation contract
  (`ORENA_CONTENT_EXECUTION_ARCHITECTURE.md` §3) and the R2 capability control
  plane already governing Writing/Grammar generation — not a new pipeline.
  This plan does not add such a field; it is a candidate later task, not
  authorized here.

## EN/ZH parity and support-language behavior

- Every task's seed data, tests and UI copy ship EN and ZH together (Task 2
  Step 3, Task 4's `copy.js` change).
- Support-language meaning display (Vietnamese, per the existing
  `translation_vi` field and `ctx.support` usage in `expression.js`) is
  unchanged by this plan: Feed candidates carry the same
  `definition`/`translation_vi` fields Library cards already carry, rendered
  through the same `renderVocabularyCard`, so no new support-language branch
  is introduced.
- Task 5 is explicitly "Chinese first" per the Roadmap sequence; it does not
  block Task 2-4's EN/ZH Feed parity, since Feed cards render correctly with
  `orthography: None` until Task 5 lands (verified by Task 2 Step 1's
  explicit assertion of that case).

## Responsive UX checkpoints

Task 4 Step 6 is the concrete checkpoint: 1024/800/390/360px widths, EN/ZH,
light/dark, at least two registered themes, keyboard reachability, and
screen-reader label parity with Library's existing card actions. No task in
this plan touches shared layout primitives, `theme.css`, or global navigation
(all protected areas per `AGENTS.md` §6) — Feed reuses Library's card markup
and Discover's existing section pattern rather than introducing new layout
rules.

## Focused verification commands per task

| Task | Command |
| --- | --- |
| 1 | `python -m pytest -q tests/test_becoming_library_source_kind.py tests/test_vocabulary_cards.py tests/test_collection_query.py` |
| 2 | `python -m pytest -q tests/test_vocabulary_feed.py tests/test_vocabulary_cards.py` |
| 3 | `python -m pytest -q tests/test_vocabulary_feed_route.py tests/test_vocabulary_feed.py tests/test_becoming_library_source_kind.py tests/test_vocabulary_cards.py` |
| 4 | `node scripts/test_orena_vocabulary_card.mjs && node scripts/test_orena_vocabulary_feed.mjs` |
| 5 | `python -m pytest -q tests/test_orthography_projection.py tests/test_chinese_stroke_order.py tests/test_vocabulary_cards.py tests/test_vocabulary_feed.py tests/test_becoming_library_source_kind.py` |

Every command above runs inside the canonical hermetic Docker recipe in
`AGENTS.md` §9 for the Python rows; the Node rows run under bare `node` per
that same section ("There is no `package.json`; `.mjs` gates run under bare
`node`"). Before any task's completion report claims a result, run the full
local suite once per `AGENTS.md` §9's local recipe and compare the failure
count against `CURRENT_HANDOFF.md`'s current baseline, not a historical
number — and label every such run "local execution," never a CI claim.

## Commit checkpoints and review

Each task above ends its own commit (Steps marked "Commit"). After Task 4
(the first learner-reachable slice — Feed becomes visible in a browser), stop
and present it for human review before starting Task 5, per
`AGENTS.md` §8's "Prefer coherent vertical slices... present it to the human
before starting another major learner-facing milestone." Task 0 additionally
requires the independent architecture review named in its own steps before
any of Task 6 begins; Tasks 1-5 do not require that specific review (they add
no schema) but remain subject to this plan's own required review by
`claude-2` before implementation starts, per this task's routing metadata.

## Self-review: contradictions and missing requirements checked

- Confirmed no task authorizes schema: Tasks 1-5 touch only existing tables
  (`saved_words`, its SQLite-side `vocabulary_learning` join) or static files.
- Confirmed Library and Feed share one save call, one review scheduler, one
  card projection, one renderer — verified against the actual current code at
  `becoming_library.py`, `vocabulary_cards.py`, and `vocabulary-card.js`
  rather than assumed.
- Confirmed the `source_kind` gap (Task 1) is real, not invented, by finding
  the actual test files that already exercise the value the API layer
  currently rejects.
- Confirmed orthography's existing test fixture (`hanzi-writer-data`
  provenance labels) already commits the codebase to a specific shape, so
  Task 5 fulfills rather than invents that contract.
- Confirmed Task 5 reuses the canonical, already-shipped Chinese stroke-order
  capability (`writing_coach/languages/chinese/stroke_order.py`, its
  `stroke_data/`, `GET /api/chinese/stroke-order`,
  `tests/test_chinese_stroke_order.py`) rather than proposing a second vendored
  copy or a parallel adapter — checked against the actual module and route,
  not assumed from the architecture doc alone.
- Confirmed Daily Feed's Discover placement against the actual eleven
  destinations and `renderWorld`'s existing per-page branching, rather than
  assuming a new destination was available.
- No `TBD` remains: every task names its exact files, interfaces, and test
  commands. Task 6 is deliberately unspecified beyond "blocked on Task 0" —
  that is a sequencing gate stated as a gate, not a placeholder for content
  this plan skipped.
