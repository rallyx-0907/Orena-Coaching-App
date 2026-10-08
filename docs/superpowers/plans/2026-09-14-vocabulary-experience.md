# Orena Vocabulary Experience Implementation Plan

> **Revision note:** this replaces the version first committed at `4f90e73`.
> That version modeled **Vocabulary Library** as the learner's saved-word list
> (`renderLanguage()`/`#/language`) and put a `VocabularyCollection` schema
> proposal in front of everything else. Both were product-direction errors,
> corrected here: Library is a curated catalog the learner browses, distinct
> from the saved/review state they already have; and the curated catalog does
> not need new schema to ship. See "What changed from the first version" near
> the end of this document for the itemized diff and why.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> or superpowers:subagent-driven-development to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Tasks are
> lettered A-H and **must run in that order** — each depends on the static
> content or interfaces the previous one ships. No task in this plan requires
> the independent architecture-review schema gate `AGENTS.md` §1 names, because
> no task in this plan adds a table, column or migration (see "Static catalog,
> not schema" below). Ordinary independent review still applies per task, per
> "Review states used in this plan."

**Goal:** Sequence the two approved learner-facing Vocabulary surfaces —
**Vocabulary Library** (a browsable curated catalog of named collections:
`600 TOEIC Essential`, `3000 Common Words`, `HSK 1`, `HSK 2`, and future
topic/level collections) and **Daily Vocabulary Feed** (a small distribution
surface that offers candidate words drawn from that same catalog and hands
them into the save/review path the learner already has) — on top of one
shared vocabulary/review foundation, per
`docs/product/ORENA_VOCABULARY_ARCHITECTURE.md`,
`docs/product/ORENA_CONTENT_ARCHITECTURE.md` §9, and the Golden Star content
sequence in `docs/project/ROADMAP.md`. This plan is the deliverable; it does
not implement either surface.

---

## 1. Vocabulary Library is a catalog. My Language is the learner's state. These are not the same surface.

`ORENA_CONTENT_ARCHITECTURE.md` §12 is explicit that **My Content**, **My
Language** and **Explore** "must remain distinct," and §3 that "Discover and
Home must surface publishable content from the domain libraries... They must
not own hard-coded canonical content of their own" — the domain library is the
canonical content owner, Discover/Home distribute from it. §9 names Vocabulary
as one of those domain libraries: "a real curated library... not only a flat
word list."

Concretely, in the code that exists today:

- `#/language` (`static/orena/ui/expression.js:350`, `renderLanguage()`,
  backed by `GET /api/library/vocabulary`) is **My Language** — the learner's
  own saved words and their review state. It has never carried a learner-facing
  "Library" label (checked: no such string exists in
  `static/orena/ui/copy.js`). This plan does not rename it, does not move it,
  and does not repurpose it as the curated-catalog surface. It remains exactly
  what it is: the account's saved/review state, per
  `ORENA_CONTENT_ARCHITECTURE.md` §12's "My Language."
- **Vocabulary Library**, as this plan defines it, does not exist in the
  product yet. It is a new browsable section — named collections the learner
  can open and read before ever saving anything, the same way
  `static/orena/content/reading-library.js`'s curated `catalog` is browsable
  inside the existing `discover`/`world` destination
  (`static/orena/ui/world.js:renderWorld`) before a learner saves or imports
  anything. Task E places it there for the same reason: Reading's domain
  library is already surfaced through Discover, not through a new destination,
  and the "eleven destinations remain intact" rule
  (`docs/product/ORENA_REFERENCE_ARCHITECTURE.md` §2) forbids inventing a
  twelfth one for Vocabulary Library either.
- The two surfaces still share one foundation, because a save is a save
  regardless of where the learner opened the word: `becoming_library.py` (save
  / review / delete), `vocabulary_cards.py` (card projection),
  `SpecializedLearningRepository` (`SavedWord` persistence). Browsing a
  collection or a Feed candidate never creates a second `SavedWord`-equivalent
  row, a second review scheduler, or a second card shape — the same rule the
  first version of this plan already got right, kept unchanged here.
- Displaying curated-collection membership *inside* My Language (e.g., a badge
  showing a saved word came from `HSK 1`) is a deliberate future UI decision,
  not something this plan authorizes by implication. Task B's design keeps
  that possible (see "Deriving membership without schema" below) without
  building it.

---

## 2. Static catalog, not schema

`ORENA_VOCABULARY_ARCHITECTURE.md` §1 requires curated named collections.
Nothing about serving them requires a `VocabularyCollection` table or a
membership join. The repository already has exactly this pattern, closed and
proven, for another content domain:

```text
writing_coach/languages/english/grammar_curriculum.json   (content)
writing_coach/languages/english/grammar_curriculum.py     (loader: reads the
                                                            JSON at import time,
                                                            exposes GRAMMAR_COURSE)
writing_coach/grammar_catalog.py                          (cross-language
                                                            aggregation/validation)
```

(verified: `writing_coach/languages/english/grammar_curriculum.py:5-6` is
`_PATH = Path(__file__).with_name("grammar_curriculum.json")` /
`GRAMMAR_COURSE = json.loads(_PATH.read_text(encoding="utf-8"))`; the JSON
already carries a `"level": "A1"`-style field per entry.) This plan reuses that
exact shape for Vocabulary — a JSON file colocated with each language module,
loaded by a two-line Python module, aggregated by one small cross-language
module — rather than inventing a new asset pipeline.

**No schema task is authorized or needed for this plan's MVP.** The two things
that might seem to need a table do not:

- **Collection content itself** — static JSON, per above.
- **"Which collections is this saved word part of?"** — computed, not stored.
  Because the catalog is a small, in-memory, load-time-indexed set (hundreds to
  low thousands of entries per `ORENA_CONTENT_ARCHITECTURE.md` §17, not
  millions), Task B builds a `normalized_word -> [collection_id, ...]` index at
  import time and looks it up live against the learner's existing saved rows
  (`list_library_records()`) whenever a membership view is needed. No join
  table, no migration. This is the concrete answer to Task 0's open question
  in the first version of this plan ("does orthography... or collection
  membership need any database row at all") for the collection half of that
  question; Task G answers it for orthography, reusing the same static-asset
  answer the existing stroke-order capability already committed to.

**What genuinely would need schema, and is explicitly not in this plan:**
learner-created collections and imported collections
(`ORENA_VOCABULARY_ARCHITECTURE.md` §1 lists both as required *eventually*).
Those need a durable, learner-owned, mutable collection object a static JSON
file cannot represent. Task H names the trigger and the gate for that later
proposal; it is not drafted here because it is not needed to ship the first
curated Library.

---

## 3. Language coherence contract for this plan

Per `docs/product/ORENA_LANGUAGE_COHERENCE.md` §1 and
`writing_coach/core/support_languages.py`, every learner-facing string belongs
to exactly one of three independent layers:

- **Interface language** — section headings, buttons, empty states this plan
  adds to `static/orena/ui/copy.js` (`en`/`zh` only today, indexed by `ctx.ui`).
- **Support/native language** — a collection entry's translation/explanation.
  `writing_coach/core/support_languages.py` names 12 supported codes; a card
  must not assume the learner's support language is Vietnamese.
- **Target learning language** — the headword, phonetic, definition, and (for
  Chinese) orthography. This is `language_code` on every catalog entry.

**`translation_vi` is not made a new canonical contract by this plan.**
`writing_coach/becoming_library.py:26` (`LibraryVocabularyIn.translation_vi`)
and `writing_coach/vocabulary_cards.py:22,27` (`_meanings`, which hardcodes the
translation's language tag to `"vi"`) already exist and already ship — this
plan does not touch what `SavedWord` stores. But every **new** interface this
plan defines uses a support-language-neutral shape:

- Catalog/candidate entries (Task B, reused by Task C) carry
  `support_translations: Mapping[str, str]` (e.g. `{"vi": "...", "en": "..."}`),
  keyed by a `support_languages.py` code, never a single hardcoded field.
- `vocabulary_cards.py`'s `_meanings` helper (Task A) is generalized to accept
  that mapping directly; the existing `SavedWord` path keeps working by
  wrapping its one `translation_vi` field as `{"vi": translation_vi}` at the
  call site — a boundary mapping, stated here explicitly rather than left
  implicit, per this plan's instruction to name compatibility boundaries
  instead of silently extending them.
- Saving a catalog/candidate item through the existing
  `POST /api/library/vocabulary` (Task D/E's "keep"/"save" actions) maps
  `support_translations` down to that endpoint's existing `translation_vi`
  field at the call site (client-side, in `static/orena/infrastructure/api.js`):
  `translation_vi: entry.support_translations[supportLanguage] ||
  entry.support_translations.vi || ''`. This is a compatibility shim scoped to
  the one existing column that accepts it; it is not evidence that `vi` is the
  target support language for any learner whose stored support preference is
  something else — that gap is `ORENA_LANGUAGE_COHERENCE.md`'s AUDIT-2/AUDIT-3
  territory, already tracked, not something this plan resolves or worsens.

No task in this plan hardcodes a support language into a prompt, a system
message, or a stored default. Catalog authoring (Task B Step 3) provides at
least a Vietnamese and an English `support_translations` entry per item, since
those are the two the sandbox profile currently exercises end-to-end — adding
more support languages to existing entries is additive content work, not an
architecture change, and is not blocked by anything in this plan.

---

## 4. Level, framework and topic metadata

Every catalog entry and every collection (Task B) carries:

- `level`: a framework-appropriate value — CEFR-shaped (`A1`-`C2`, matching the
  existing `account_profile.py:93` `declared_level` enum) for English
  general-vocabulary collections, `HSK1`-`HSK6` for Chinese HSK collections.
  There is no cross-framework equivalence table in this plan (e.g. "HSK 2 ≈
  B1") — inventing one would be a content/pedagogy decision this plan does not
  make; `level` values are compared only within their own `framework`.
- `framework`: one of `"cefr-internal"` (general graded vocabulary, no external
  test body), `"toeic"`, `"hsk"` — open to more values later, never a
  hardcoded two-value enum.
- `topic`: free-form string (`"travel"`, `"workplace"`, `"technology"`, ...),
  matching the example list already named in
  `ORENA_VOCABULARY_ARCHITECTURE.md` §1.

**Declared vs. measured, per `ORENA_ACCOUNT_DATA_ARCHITECTURE.md` §"Learner
profile, preferences and state":** "A declared level is a goal, never measured
proficiency; projections cannot overwrite it as inferred fact." This plan
never infers a learner's level from their saves, review outcomes, or Feed
keeps and writes it back as fact. Where a task reads a level to filter or rank
(Task C's selector), it reads only an explicitly declared/requested value,
never a computed one.

**Known limitation, stated rather than worked around:**
`account_profile.py:93` defines `declared_level` with `stored=False` — it is
not currently durably persisted per learner. This plan does not add that
persistence (it would be exactly the kind of account/schema decision §7's
architecture hold reserves). Task C's and Task D's interfaces accept an
explicit `target_level: str | None` parameter so the *code* is not
level-blind; until a durable declared-level store exists, callers pass
`None` or a value sourced from an explicit request parameter, not a fabricated
default.

---

## 5. Daily Feed selector contract — learner/context-aware, still deterministic

The first version of this plan keyed the selector as `(language_code, date)`
only, which would serve every learner of a language the identical feed
forever. The corrected contract:

```python
@dataclass(frozen=True)
class LearnerFeedContext:
    learner_key: str            # opaque stable identity, see limitation below
    target_level: str | None = None
    framework: str | None = None

def daily_feed_candidates(
    language_code: str,
    *,
    learner_context: LearnerFeedContext,
    exclude_normalized: set[str],
    count: int = 5,
    on_date: date | None = None,
) -> list[dict]: ...
```

Determinism is keyed on `(learner_context.learner_key, language_code,
learner_context.target_level, on_date or today)` — the same learner sees the
same feed within a day, but two different `learner_key`s are not forced onto
the same ordering, and a `target_level` changes the pool that is sampled
before determinism is applied (candidates are filtered to matching
`level`/`framework` when `target_level`/`framework` are given, else drawn from
the full per-language pool). This satisfies "must not force every learner of a
language to receive the same feed forever" without requiring the selector to
actually know who is different today.

**Known limitation, stated rather than worked around:** this codebase has no
per-request account/session identity threaded into any `/api/library/*` or
future `/api/vocabulary/*` route today (checked: no `Depends(get_current...)`,
no `request.cookies`/session lookup, no account id parameter anywhere in
`app.py`'s vocabulary-adjacent routes — the whole surface is currently
single-tenant sandbox). Task D's route therefore passes a single fixed
`learner_key` constant (documented in code as the sandbox's implicit learner,
not a design choice about multi-user architecture) until the account backbone
architecture hold (`AGENTS.md` §7) is resolved elsewhere. The interface is
already shaped to take a real key the day one exists; nothing about the
selector's contract needs to change when it does. This is not a persistence
decision — `learner_key` is a request-scoped Python value, never stored.

---

## 6. Review states used in this plan

This plan does not apply a blanket "every task stops at `REVIEWABLE`; only the
human sets `APPROVED`" rule. Per task:

- **Backend/technical tasks (A, B, C, D, G):**
  `IMPLEMENTING → automated verification (tests pass) → independent review (a
  reviewer other than the implementer) → fix/re-review if needed → DONE`,
  autonomously. "DONE" here means merged into the lane branch with review
  recorded in Git (commit trailer or adjacent note naming reviewer and
  outcome) — it is not human product approval and is not a claim that the
  feature is user-visible yet.
- **Learner-facing UI/UX task (E):**
  `IMPLEMENTING → automated verification → independent review →
  READY_FOR_HUMAN_UX_REVIEW`. It stops there. Task F is the explicit wait for
  the human's visual/usage acceptance; nothing after Task F may claim
  `APPROVED` on the human's behalf.
- **No task in this plan is schema, irreversible, production, or credential
  work**, so none needs the explicit human gate `AGENTS.md` §10 reserves for
  those — Task H names the one future task that would.

`REVIEWABLE` and `APPROVED` (`AGENTS.md` §9) remain the correct vocabulary for
milestones that *are* schema/production/credential-gated; this plan has none,
so it does not use them as a blanket label.

---

## 7. Architecture, unchanged from the working parts of the first version

Both surfaces still read and write through the existing saved-word seam —
`writing_coach/persistence/models.py:SavedWord`,
`writing_coach/persistence/specialized_repository.py`'s
`list_library_records`/`save_library_record`/`get_library_progress`/
`update_library_review`/`delete_library_record`, and
`writing_coach/becoming_library.py`'s service functions — exposed at
`/api/library/vocabulary` in `app.py`. `writing_coach/vocabulary_cards.py`
already projects one saved-word row into an Orena Vocabulary Card; Task A
generalizes its meanings helper, it does not replace it.

```text
                 saved_words (+ vocabulary_learning on SQLite)
                              |
                 becoming_library.py (save / review / delete)
                              |
                 vocabulary_cards.py (card projection: saved word OR
                                       catalog/candidate entry, same shape)
                              |
        -----------------------------------------------------------
        |                       |                                  |
  My Language           Vocabulary Library                Daily Vocabulary Feed
  (#/language,          (new: Discover section,            (new: Discover section,
   existing, unchanged  browses static collections         reads the same static
   saved/review state)  from writing_coach/                collections, filtered by
                         vocabulary_library.py)             exclusion + level; "keep"
                                                             calls the *same* save path
                                                             Library browsing uses)
```

`writing_coach/vocabulary_library.py` (Task B) is the one new static-content
aggregation module both Library browsing and Feed selection sit on top of —
this is what makes "one canonical card/save/progress foundation" concrete
rather than aspirational: Feed is not a second content set, it is a filtered,
day-seeded view over the same collections a learner can also browse directly.

**Tech stack:** FastAPI/Pydantic (`app.py`, `writing_coach/becoming_library.py`,
new `writing_coach/vocabulary_library.py`/`vocabulary_feed.py`), the existing
`SpecializedLearningRepository` PostgreSQL/SQLite dual implementation, static
JSON content colocated with language modules (the R5/Grammar KB pattern),
browser-native ES modules (`static/orena/ui/*.js`), Node ESM contract tests
(`scripts/test_orena_*.mjs`), pytest.

**Spec paths:** unchanged from the first version —
`ORENA_VOCABULARY_ARCHITECTURE.md`, `ORENA_CONTENT_ARCHITECTURE.md` §3-4, §9,
§16-17, `ORENA_COLLECTION_ARCHITECTURE.md`, `ORENA_EVIDENCE_ARCHITECTURE.md`
§1, §4, `ORENA_CONTENT_EXECUTION_ARCHITECTURE.md` §1, §3,
`docs/project/ROADMAP.md` "Golden Star" §Sequence items 3-4,
`ORENA_UNDERSTANDING_ENGINE.md` §2, §4, plus (new to this revision)
`ORENA_LANGUAGE_COHERENCE.md` and `ORENA_ACCOUNT_DATA_ARCHITECTURE.md`
"Learner profile, preferences and state."

**Global constraints:**
- No new table, column, or migration ships in this plan (§2 above). No task
  is blocked on independent architecture review for schema, because none
  proposes any.
- No provider/credential activation. This plan's content is static/curated;
  no generation step (example sentence, core-semantic image) is added here.
- One shared save/review path. Neither Library browsing nor Feed may create a
  second `SavedWord`-equivalent row, a second review scheduler, or a second
  card shape. `vocabulary_card_from_saved_word` and the new
  `vocabulary_card_from_catalog_entry` (Task A) are the only two card
  projections, and they share their meanings/orthography logic.
- EN/ZH ship together in every task; no English-first task followed by a
  promised Chinese follow-up.
- Reuse the closed R5/Grammar-KB static-content pattern (§2 above) for catalog
  data; do not invent a new asset pipeline.
- Stage only the files each task names.
- Review states per §6 above, not a blanket rule.

---

## What this plan explicitly does not authorize

- No learner-created or imported vocabulary collections (Task H names the
  trigger for that later proposal).
- No handwriting-scoring extension to orthography (explicitly deferred as "not
  a commitment to ship" in `ORENA_VOCABULARY_ARCHITECTURE.md` §4).
- No Reading/Listening rights or library-content expansion. Feed/Library
  content in this plan is Orena-curated with truthful `origin: "curated"`
  provenance (`ORENA_CONTENT_ARCHITECTURE.md` §16), never presented as sourced
  from a specific external copyrighted text.
- No new destination. Vocabulary Library and Daily Vocabulary Feed are two
  sections inside the existing `discover` destination group
  (`static/orena/ui/world.js:renderWorld`), per the eleven-destination map.
- No claim that `600 TOEIC Essential` or `HSK 1`/`HSK 2` are licensed,
  endorsed, or sourced from ETS or China's HSK test administrator. "TOEIC" and
  "HSK" name the well-known proficiency frameworks a learner recognizes;
  content under those collection titles is Orena's own curated vocabulary
  organized to match each framework's publicly known scope/level bands, not
  reproduced test material. Task B's provenance metadata must say this
  explicitly per entry/collection, per `ORENA_CONTENT_ARCHITECTURE.md` §16's
  "do not fabricate attribution."
- No durable declared-level persistence and no measured-proficiency inference
  (§4 above).
- No per-account Feed personalization beyond the deterministic, level-aware
  selection in §5 — no recommendation model, no evidence-weighted ranking.
  `ORENA_EVIDENCE_ARCHITECTURE.md` §4's Discover-ranking boundary is not
  touched by this plan.

---

### Task A: Foundation compatibility fixes

**Why first:** two small, real gaps block every later task, both found by
reading the current code rather than assumed.

**A1 — `source_kind` is narrower than the values the system already needs.**
`LibraryVocabularyIn.source_kind` in `writing_coach/becoming_library.py:29-32`
only accepts `manual|dictionary|feedback|strength`.
`tests/test_collection_query.py:60` and `tests/test_vocabulary_cards.py:16`
already exercise `source_kind: "reading"` against the repository/card layer
directly, bypassing this Pydantic gate. This plan needs two more truthful
values: `"feed"` (Task D's Daily Feed keep) and `"collection"` (Task E's
Library-browsing save) — a learner and any future audit should be able to see
*how* a word entered their library, per `ORENA_COLLECTION_ARCHITECTURE.md`
§2's "Reason is the shared KEEP_REASONS vocabulary, not fabricated evidence,"
the same reasoning that already justifies `"reading"` existing.

**A2 — `vocabulary_cards.py`'s meanings helper hardcodes one support
language.** `_meanings` (`writing_coach/vocabulary_cards.py:19-28`) always
tags the translation `"vi"`. Task B and Task C need a card projection that
carries `support_translations: Mapping[str, str]` for entries that were never
a `SavedWord` row (§3 above). Generalize the helper so both callers share it,
instead of writing a second meanings builder next to the first.

**Files:**
- Modify: `writing_coach/becoming_library.py`
  (`LibraryVocabularyIn.source_kind` pattern only)
- Modify: `writing_coach/becoming_library_selftest.py` if it asserts the old
  pattern literal
- Modify: `writing_coach/vocabulary_cards.py` (`_meanings` generalization,
  `vocabulary_card_from_saved_word` unchanged in signature/output for existing
  callers; add `vocabulary_card_from_catalog_entry`)
- Test: `tests/test_becoming_library_source_kind.py` (new)
- Test: `tests/test_vocabulary_cards.py` (extend: existing tests must keep
  passing unmodified; add coverage for the new `support_translations` path and
  for `vocabulary_card_from_catalog_entry`)

**Interfaces:**
- `LibraryVocabularyIn.source_kind: str` pattern becomes
  `^(manual|dictionary|feedback|strength|reading|feed|collection)$`. No other
  field of `LibraryVocabularyIn` or `_row_to_item` changes.
- `vocabulary_cards.py` internal helper becomes
  `_meanings_from(definition: str, definition_language: str,
  support_translations: Mapping[str, str]) -> list[dict[str, str]]`, called by
  `vocabulary_card_from_saved_word` as
  `_meanings_from(definition, language, {"vi": translation_vi} if
  translation_vi else {})` (preserves exact current output — same order, same
  `"vi"` key, same omission when `translation_vi` is empty) and by the new
  `vocabulary_card_from_catalog_entry(entry: Mapping[str, Any], *,
  orthography: Mapping[str, Any] | None = None) -> dict[str, Any]` as
  `_meanings_from(entry["definition"], entry["language_code"],
  entry.get("support_translations") or {})`. `vocabulary_card_from_catalog_entry`
  returns the same card shape as `vocabulary_card_from_saved_word` minus
  `memory` (no review state exists yet for an unsaved entry) and minus
  `source_encounters` (a catalog/candidate entry has no learner encounter),
  plus `level`, `framework`, `topic` passthrough fields when present on the
  entry (Task B/C need these to render/filter; `vocabulary_card_from_saved_word`
  does not gain these fields, since a `SavedWord` row has none today).

- [ ] **Step 1: Write failing tests.**
  - `test_becoming_library_source_kind.py`: `POST /api/library/vocabulary`
    accepts `source_kind="feed"`, `source_kind="collection"` and
    `source_kind="reading"`; rejects an unrecognized value (e.g.
    `"listening"` still 422).
  - `test_vocabulary_cards.py`: the three existing tests pass with zero
    changes to their assertions; a new test builds a card via
    `vocabulary_card_from_catalog_entry` from an entry with `support_translations
    = {"vi": "...", "en": "..."}` and asserts `meanings` contains both, in
    stable key order; a new test asserts the catalog-entry card has no
    `memory` key and no `source_encounters` key (not empty lists standing in
    for absence — genuinely absent, matching the existing "does not invent
    empty fields" test's spirit).
- [ ] **Step 2: Run and confirm failure** inside the canonical Docker test
  recipe (`AGENTS.md` §9):
  `python -m pytest -q tests/test_becoming_library_source_kind.py tests/test_vocabulary_cards.py`
- [ ] **Step 3: Implement.** Widen the pattern (one line); generalize
  `_meanings` into `_meanings_from` and add
  `vocabulary_card_from_catalog_entry`. No behavior change to
  `vocabulary_card_from_saved_word`'s output.
- [ ] **Step 4: Run the full existing vocabulary suite** to confirm no
  regression:
  `python -m pytest -q tests/test_becoming_library_source_kind.py tests/test_vocabulary_cards.py tests/test_collection_query.py`
- [ ] **Step 5: Independent review**, per §6. On a clean pass, commit
  `fix(vocabulary): accept feed/collection source kinds and generalize card
  meanings for support-language entries` and mark **DONE**.

---

### Task B: Static curated Vocabulary Library catalog, with level/framework metadata

**Files:**
- Create: `writing_coach/languages/english/vocabulary_collections.json`
  (seed: `toeic-600-essential`, `common-3000` — see Step 3 for seed size)
- Create: `writing_coach/languages/english/vocabulary_collections.py` (loader,
  same shape as `writing_coach/languages/english/grammar_curriculum.py`:
  `_PATH = Path(__file__).with_name("vocabulary_collections.json")`,
  `VOCABULARY_COLLECTIONS = json.loads(_PATH.read_text(encoding="utf-8"))`)
- Create: `writing_coach/languages/chinese/vocabulary_collections.json`
  (seed: `hsk-1`, `hsk-2`)
- Create: `writing_coach/languages/chinese/vocabulary_collections.py` (same
  loader shape)
- Create: `writing_coach/vocabulary_library.py` (cross-language aggregation +
  validation, mirroring `writing_coach/grammar_catalog.py`'s role over
  `GRAMMAR_COURSE`/`GRAMMAR_BY_ID`)
- Test: `tests/test_vocabulary_library.py` (new)

**Collection JSON shape** (one object per collection, in a top-level array):
```json
{
  "id": "hsk-1",
  "language_code": "zh",
  "framework": "hsk",
  "level": "HSK1",
  "topic": null,
  "title": "HSK 1",
  "provenance": {
    "origin": "curated",
    "note": "Orena-curated vocabulary organized to HSK 1's publicly known scope; not licensed or sourced HSK test material."
  },
  "entries": [
    {
      "word": "你好",
      "phonetic": "nǐ hǎo",
      "part_of_speech": "phrase",
      "definition": "hello",
      "support_translations": {"vi": "xin chào", "en": "hello"},
      "level": "HSK1",
      "topic": "greetings"
    }
  ]
}
```
Every entry inherits `language_code`/`framework` from its collection at load
time (Task B Step 3 denormalizes this into each in-memory entry dict so
`vocabulary_card_from_catalog_entry` never needs the parent collection object)
and gets `origin: "curated"` and `collection_id` set to the parent's `id`.

**Interfaces (`writing_coach/vocabulary_library.py`):**
- `list_vocabulary_collections(language_code: str) -> list[dict]` → summaries
  `{id, language_code, framework, level, topic, title, item_count, provenance}`,
  sorted by `framework`, then `level`, then `title`.
- `get_vocabulary_collection(collection_id: str) -> dict | None` → the
  collection summary plus `"entries": [...]` (raw entry dicts, ready for
  `vocabulary_card_from_catalog_entry`).
- `all_vocabulary_entries(language_code: str) -> list[dict]` → every entry
  across every collection for that language, each carrying `collection_id`
  (used by Task C's Feed pool — Feed is a filtered view over this, not a
  separate dataset).
- `collection_ids_for_word(language_code: str, normalized_word: str) ->
  list[str]` → built from a load-time index
  (`{(language_code, normalized_word): [collection_id, ...]}`); this is the
  "deriving membership without schema" mechanism named in §2. A saved word
  that also happens to be in `hsk-1` gets `["hsk-1"]` back; a saved word that
  is not in any curated collection gets `[]`, truthfully, not an invented
  match.
- `validate_vocabulary_collections(collections: Sequence[Mapping]) -> None`,
  mirroring `writing_coach/grammar_catalog.py`'s
  `validate_grammar_catalog` — checks unique `id`s across all loaded
  collections, non-empty `entries`, required fields present, `framework`/
  `level` non-empty strings, no duplicate `word` within one collection.

- [ ] **Step 1: Write failing tests.** Assert `list_vocabulary_collections("zh")`
  returns `hsk-1` and `hsk-2` with correct `item_count`; assert
  `get_vocabulary_collection("toeic-600-essential")["entries"]` all carry
  `language_code == "en"`, `framework == "toeic"`, and a non-empty
  `support_translations`; assert `collection_ids_for_word("zh", "你好")`
  returns `["hsk-1"]` (or wherever the seed places it) and
  `collection_ids_for_word("zh", "some-word-not-in-any-seed")` returns `[]`;
  assert `validate_vocabulary_collections` raises on a duplicate collection
  `id` and on an entry missing `support_translations`; assert every entry from
  `all_vocabulary_entries` round-trips cleanly through
  `vocabulary_card_from_catalog_entry` (Task A) with no missing-field
  exception.
- [ ] **Step 2: Run and confirm failure**:
  `python -m pytest -q tests/test_vocabulary_library.py`
- [ ] **Step 3: Author the seed content and implement the loaders/aggregator.**
  Seed size is a real, checkable, non-placeholder batch per collection — not a
  future full 600/3000/HSK-official-list count. `ORENA_CONTENT_ARCHITECTURE.md`
  §17 requires "batch ingestion; incremental publishing," so this task ships a
  first verified batch (at minimum 30 entries per collection, real headword +
  real definition + real `vi`/`en` translations, correctly leveled) and states
  explicitly, in the module docstring and in this plan's completion report,
  that growing each collection toward its full named breadth (600 TOEIC words,
  3000 common words, full HSK 1/2 vocabulary lists) is incremental content
  authoring against this same JSON file, not a later code task.
- [ ] **Step 4: Pass the new tests, then the full existing vocabulary suite**:
  `python -m pytest -q tests/test_vocabulary_library.py tests/test_vocabulary_cards.py tests/test_becoming_library_source_kind.py`
- [ ] **Step 5: Independent review**, per §6. Commit
  `feat(vocabulary): add the static curated Vocabulary Library catalog` and
  mark **DONE**.

---

### Task C: Daily Feed candidate/selection foundation

**Depends on:** Task B's catalog — Feed draws its candidate pool from
`all_vocabulary_entries`, it does not maintain a separate seed file. This is a
deliberate simplification over the first version of this plan (which proposed
`data/vocabulary_feed_seed.json` as a second content set); one static catalog
now serves both Library browsing and Feed, matching the "one canonical
card/save/progress foundation" requirement more literally than two datasets
projected through the same function ever could.

**Files:**
- Create: `writing_coach/vocabulary_feed.py`
- Test: `tests/test_vocabulary_feed.py`

**Interfaces:**
- `LearnerFeedContext` (§5 above), defined in this module.
- `daily_feed_candidates(language_code: str, *, learner_context:
  LearnerFeedContext, exclude_normalized: set[str], count: int = 5, on_date:
  date | None = None) -> list[dict]` (§5's contract). Filters
  `all_vocabulary_entries(language_code)` to `learner_context.target_level`/
  `framework` when given (falls back to the full pool when no entries match,
  rather than returning empty — a level filter narrows, it does not starve the
  feed); excludes any entry whose normalized word is in `exclude_normalized`;
  orders deterministically by a stable hash of
  `(learner_context.learner_key, language_code,
  learner_context.target_level, on_date or date.today().isoformat())`; returns
  the first `count`.
- `vocabulary_card_from_feed_candidate(entry: dict) -> dict`: calls
  `vocabulary_cards.vocabulary_card_from_catalog_entry` directly — no
  duplicate card-shaping logic. (This makes the function a one-line wrapper;
  it exists so call sites read `vocabulary_card_from_feed_candidate`, keeping
  Feed's own vocabulary distinct in code from generic catalog browsing, per
  the same "visibly distinct as surfaces" reasoning the first version of this
  plan already used for its route comments.)

- [ ] **Step 1: Write failing tests.** Assert candidates exclude any
  normalized word already in `exclude_normalized`; assert the same
  `(learner_key, language_code, target_level, date)` tuple returns the same
  ordered candidates (determinism), and a *different* `learner_key` with
  everything else equal can return a different order (proving the selector is
  not secretly still keyed on date alone); assert a `target_level` that
  matches no entries falls back to the full pool rather than returning `[]`;
  assert a candidate card built via `vocabulary_card_from_feed_candidate` has
  no `memory` field and no `source_encounters` field; assert EN and ZH both
  produce valid candidates from Task B's seed, including a ZH candidate with
  `orthography` absent (Task G supplies real orthography later — this task
  must not fabricate it, and `vocabulary_card_from_catalog_entry` already
  omits the key rather than inventing `None`... verify against Task A's actual
  contract, adjusting the assertion if it stores an explicit `None`).
- [ ] **Step 2: Run and confirm failure**:
  `python -m pytest -q tests/test_vocabulary_feed.py`
- [ ] **Step 3: Implement** the selector and wrapper.
- [ ] **Step 4: Pass the new tests, then the growing vocabulary suite**:
  `python -m pytest -q tests/test_vocabulary_feed.py tests/test_vocabulary_library.py tests/test_vocabulary_cards.py`
- [ ] **Step 5: Independent review**, per §6. Commit `feat(vocabulary): add a
  learner/level-aware deterministic Daily Feed selector over the curated
  catalog` and mark **DONE**.

---

### Task D: Vocabulary Library and Feed API surface, and the save handoff

**Files:**
- Modify: `app.py` (new routes, in their own clearly labeled blocks)
- Test: `tests/test_vocabulary_library_route.py` (new)
- Test: `tests/test_vocabulary_feed_route.py` (new)

**Interfaces:**
- `GET /api/vocabulary/library/collections?language_code=en|zh` (name:
  `becoming_vocabulary_library_collections`) →
  `{items: [<collection summary>, ...]}` via
  `vocabulary_library.list_vocabulary_collections`.
- `GET /api/vocabulary/library/collections/{collection_id}` (name:
  `becoming_vocabulary_library_collection_detail`) → the collection summary
  plus `{"items": [<card>, ...]}`, each card built via
  `vocabulary_card_from_catalog_entry` and annotated with `"saved": bool`
  (cross-referenced against `list_library_records()`'s normalized words for
  that language — this is the schema-free membership/saved-status view named
  in §2, computed per request, not stored). 404s on an unknown
  `collection_id`.
- `GET /api/vocabulary/feed?language_code=en|zh&target_level=` (name:
  `becoming_vocabulary_feed`, path unchanged from the first version of this
  plan) → `{items: [<card>, ...], date: "YYYY-MM-DD"}`. Builds
  `LearnerFeedContext(learner_key=<sandbox constant, see §5>,
  target_level=target_level or None)` from the optional query parameter (a
  client-supplied, explicitly-declared value — never inferred), reads
  `list_library_vocabulary()`'s existing repository read to build the
  exclusion set, then calls `daily_feed_candidates` +
  `vocabulary_card_from_feed_candidate`. `language_code` is required; an
  unsupported value is a clean 4xx, not a silent empty list.
- **"Keep"/"save" reuse the existing save route unmodified.** Both Library
  browsing and Feed call `POST /api/library/vocabulary` (already exists) with
  `source_kind="collection"` (Library) or `source_kind="feed"` (Feed) — both
  now valid per Task A — and the entry's own
  word/phonetic/part_of_speech/definition/mapped-`translation_vi` fields (§3's
  boundary mapping, done client-side in Task E). This task adds no new save
  endpoint.

- [ ] **Step 1: Write failing route tests.**
  - Collections list/detail: assert language filtering; assert a saved word's
    card comes back with `"saved": true`, an unsaved one `"saved": false`;
    assert an unknown `collection_id` is a clean 404; assert the response
    never leaks an internal file path.
  - Feed: assert the route excludes an already-saved word (seed the test DB
    with one saved word matching a known seed entry); assert `language_code`
    is required and an unsupported value is a clean 4xx; assert passing
    `target_level` narrows the pool (assert on the returned `level`s) without
    ever returning an empty list because of it; assert the response never
    includes a `memory` claim or an internal seed-file path.
- [ ] **Step 2: Run and confirm failure**:
  `python -m pytest -q tests/test_vocabulary_library_route.py tests/test_vocabulary_feed_route.py`
- [ ] **Step 3: Implement the routes** in `app.py`, in two new blocks —
  `# === BECOMING VOCABULARY LIBRARY CATALOG ROUTES ===` and
  `# === BECOMING VOCABULARY FEED ROUTES ===` — kept visibly distinct from the
  existing `# === BECOMING VOCABULARY LIBRARY ROUTES ===` block (which is the
  saved-state routes at `/api/library/vocabulary` and must not be renamed or
  merged with these).
- [ ] **Step 4: Pass these tests plus the full vocabulary suite**:
  `python -m pytest -q tests/test_vocabulary_library_route.py tests/test_vocabulary_feed_route.py tests/test_vocabulary_feed.py tests/test_vocabulary_library.py tests/test_becoming_library_source_kind.py tests/test_vocabulary_cards.py`
- [ ] **Step 5: Independent review**, per §6. Commit `feat(vocabulary): add
  the Vocabulary Library catalog and Daily Feed read routes` and mark **DONE**.

---

### Task E: Vocabulary Library and Daily Feed UI (Discover surface)

**Files:**
- Modify: `static/orena/infrastructure/api.js` (new client calls:
  `vocabularyLibraryCollections(languageCode)`,
  `vocabularyLibraryCollection(collectionId)`,
  `dailyVocabularyFeed(languageCode, targetLevel)`, mirroring the existing
  `libraryVocabulary()`/`saveLibraryVocabulary()` pattern at
  `static/orena/infrastructure/api.js:105-118`)
- Modify: `static/orena/ui/world.js` (`renderWorld`'s `discover` branch gains
  two sections — Vocabulary Library and Daily Feed; no new destination, no new
  top-level route, following the same pattern
  `../content/reading-library.js` already uses to surface a curated catalog
  inside this same destination)
- Modify: `static/orena/ui/copy.js` (EN/ZH strings for both sections' headings,
  empty states, and "keep"/"save" actions — reuse existing naming conventions
  already in that file rather than inventing new ones)
- Test: `scripts/test_orena_vocabulary_library.mjs` (new, Node ESM, same style
  as `scripts/test_orena_vocabulary_card.mjs`)
- Test: `scripts/test_orena_vocabulary_feed.mjs` (new, same style)

**Interfaces:**
- Both sections render each item through the *existing* `renderVocabularyCard`
  from `static/orena/ui/vocabulary-card.js` — the same function My Language
  already uses — with a `slots.after` action button. In the Library section,
  an already-`saved` card (per Task D's `"saved"` flag) shows a disabled/label
  "already in My Language" state instead of a save button, so the two surfaces
  never imply a duplicate save is possible. In the Feed section, "keep" calls
  `api.saveLibraryVocabulary({..., source_kind: 'feed', translation_vi:
  mapSupportTranslation(item, ctx.support)})` (§3's boundary mapping,
  implemented once as a small shared helper both sections call, not
  duplicated) then removes that card from the in-memory list — no full
  reload, matching the existing optimistic-update pattern already used in
  `expression.js`'s recall grading.
- No orthography rendering claim yet for ZH cards until Task G ships;
  `vocabulary-card.js`'s existing `orthographyMarkup` already no-ops safely
  when `card.orthography` is absent (verified at
  `static/orena/ui/vocabulary-card.js:27-38`), so this task requires no
  defensive change there.
- Vocabulary Library section: list collections (grouped by `framework`, e.g.
  a "TOEIC" group and a "Common Vocabulary" group for English, an "HSK" group
  for Chinese), open one to see its cards. This is the first genuinely
  browsable curated catalog for Vocabulary — distinct on screen, in its own
  labeled section, from the Feed section beneath or beside it.

- [ ] **Step 1: Write the failing Node contract tests.** Library: assert the
  rendered section reuses `renderVocabularyCard`; assert an already-saved
  item's action differs from an unsaved item's (no duplicate "save"); assert
  collections group by framework. Feed: assert the rendered section reuses
  `renderVocabularyCard`; assert the empty state (no candidates left today)
  renders a truthful message, not a spinner or silent blank.
- [ ] **Step 2: Run and confirm failure**:
  `node scripts/test_orena_vocabulary_library.mjs && node scripts/test_orena_vocabulary_feed.mjs`
- [ ] **Step 3: Implement.** Keep each section small: fetch, render cards,
  wire the keep/save action, EN/ZH copy, the shared support-translation
  mapping helper.
- [ ] **Step 4: Add both new tests to `.github/workflows/ci.yml`'s Node
  block**, in the same edit noting that `scripts/test_orena_vocabulary_card.mjs`
  itself is not currently listed there either — add all three in this task
  rather than leaving the pre-existing gap for a future worker to rediscover.
- [ ] **Step 5: Pass locally**:
  `node scripts/test_orena_vocabulary_card.mjs && node scripts/test_orena_vocabulary_library.mjs && node scripts/test_orena_vocabulary_feed.mjs`
- [ ] **Step 6: Responsive/accessibility checkpoint** (manual, browser-based):
  1024px, 800px, 390px and 360px widths, EN and ZH, light and dark appearance
  in at least two registered themes, keyboard reachability of "keep"/"save"
  actions, and screen-reader label parity with My Language's existing
  provenance/"look closer" pattern (`static/orena/ui/expression.js:386-389`).
- [ ] **Step 7: Independent review**, per §6. Commit `feat(vocabulary): add
  the Vocabulary Library catalog and Daily Feed to Discover` and mark
  **READY_FOR_HUMAN_UX_REVIEW**. Do not mark `DONE` or claim approval.

---

### Task F: Human UX review checkpoint

This is the first learner-reachable vertical slice of this plan — Vocabulary
Library and Daily Feed both become visible and usable in a browser. Per
`AGENTS.md` §8's "prefer coherent vertical slices... present it to the human
before starting another major learner-facing milestone," stop here and wait
for the human's visual/usage acceptance before starting Task G. No agent may
set `APPROVED` on Task E's behalf; this task's only action is presenting the
`READY_FOR_HUMAN_UX_REVIEW` state and waiting.

---

### Task G: Chinese orthography — projection over the existing stroke-order capability

Unchanged in substance from the first version of this plan's Task 5, with two
additions: it now wires into catalog/candidate cards (Task B/C) as well as
saved-word cards, and it explicitly answers the "does orthography need a
database row" question this plan's §2 already answered "no" for collections —
consistently, since the existing capability already proves a static answer
works.

**The repository already has the canonical Chinese stroke-order capability.**
`writing_coach/languages/chinese/stroke_order.py`'s `stroke_order_for`/
`character_strokes`, the vendored Make Me a Hanzi pack at
`writing_coach/languages/chinese/stroke_data/` (provenance/license already
recorded in that directory's `README.md`), the route
`GET /api/chinese/stroke-order` in `app.py`, its client stub
`chineseStrokeOrder(word)` in `static/orena/infrastructure/api.js:104`, and
`tests/test_chinese_stroke_order.py` are that capability, already shipped and
tested. This task does not vendor a second copy and does not build a parallel
adapter — per `ORENA_VOCABULARY_ARCHITECTURE.md` §4, "the internal capability
name is the general `orthography`... a script-specific renderer is a language
adapter over this one capability." This task is that generalization: a thin
projection from the existing capability's output into the card `orthography`
shape.

**Files:**
- Modify: `writing_coach/vocabulary_cards.py` — no signature change to
  `vocabulary_card_from_saved_word`'s or `vocabulary_card_from_catalog_entry`'s
  existing `orthography` parameter (see
  `tests/test_vocabulary_cards.py:53-75`, which already asserts the
  `{script, characters, source, source_version}` shape sourced from
  `"make-me-a-hanzi"`/`"hanzi-writer-data-2.0.1"` — this task fulfills that
  contract, it does not invent one)
- Modify: `writing_coach/languages/chinese/stroke_order.py` only if Step 1's
  tests show the projection needs a return value it does not already expose;
  otherwise read-only for this task
- Create: `orthography_for_word(word: str, language_code: str) -> dict | None`
  (placed in `vocabulary_cards.py` next to the card functions, or as the
  one-function `writing_coach/orthography.py` module
  `ORENA_VOCABULARY_ARCHITECTURE.md` §4 names as the general capability seam —
  decide in Step 3) — it **imports and calls**
  `writing_coach.languages.chinese.stroke_order.stroke_order_for`, never
  reimplements stroke lookup or pack decoding
- Test: `tests/test_orthography_projection.py` (new, scoped to the projection
  only — stroke-data correctness stays covered by
  `tests/test_chinese_stroke_order.py`)

**Interfaces:**
- `orthography_for_word(word: str, language_code: str) -> dict | None`: for
  `language_code == "zh"`, calls `stroke_order.stroke_order_for(word)` and
  projects into `{script: "han", characters: [...], source, source_version}`,
  using `stroke_order.SOURCE_VERSION` and its existing `"make-me-a-hanzi"`
  literal by reference, not restatement. Returns `None` for any
  `language_code != "zh"`, and `None` (not `characters: []`) when every
  character comes back `unavailable`, per
  `ORENA_VOCABULARY_ARCHITECTURE.md` §2's "must not invent a value merely to
  fill an unused field."
- No new stroke lookup, index, pack file, or dataset directory.
- Wire into `becoming_library.py`'s `_row_to_item` path (saved words),
  `writing_coach/vocabulary_library.py`'s collection-detail path, and
  `writing_coach/vocabulary_feed.py`'s candidate path — three call sites, one
  projection function, ZH only (do not compute for English rows/entries).

- [ ] **Step 1: Write failing tests.** Assert a known multi-character ZH word
  (e.g. `休息`, matching `ORENA_VOCABULARY_ARCHITECTURE.md` §4's illustrative
  shape) returns per-character radical/stroke data with `script: "han"`;
  assert an EN word returns `None`; assert a ZH word entirely absent from the
  vendored dataset returns `None` rather than a partially fabricated entry;
  assert `source`/`source_version` match exactly what
  `GET /api/chinese/stroke-order` already returns for the same word (no
  independent literal to drift); assert the projection calls into
  `stroke_order.stroke_order_for`/`character_strokes` rather than reading
  `writing_coach/languages/chinese/stroke_data/` itself (monkeypatch and
  confirm the call).
- [ ] **Step 2: Run and confirm failure**:
  `python -m pytest -q tests/test_orthography_projection.py`
- [ ] **Step 3: Implement the projection function only.** No dataset
  vendoring, no new file tree: reuse `writing_coach/languages/chinese/stroke_data/`
  exactly as it stands, its `README.md` provenance record unmodified. Decide
  the function's final home here.
- [ ] **Step 4: Wire all three card-response call sites** (My Language, Task
  B's collection detail, Task C's feed candidates) to include orthography for
  ZH rows/entries only, reusing the existing `orthography=...` parameter — no
  change to either card function's contract.
- [ ] **Step 5: Pass the full vocabulary suite plus the existing stroke-order
  suite** (confirming the existing capability is untouched):
  `python -m pytest -q tests/test_orthography_projection.py tests/test_chinese_stroke_order.py tests/test_vocabulary_cards.py tests/test_vocabulary_library.py tests/test_vocabulary_feed.py tests/test_becoming_library_source_kind.py`
- [ ] **Step 6: Verify `static/orena/ui/vocabulary-card.js`'s existing
  `orthographyMarkup`** renders the projected real data correctly in the
  browser (My Language, Vocabulary Library's HSK collections, and Feed; ZH
  profile; both themes) — this function already exists and is already tested
  against a synthetic fixture (`scripts/test_orena_vocabulary_card.mjs`); this
  step is verification, not new implementation. Confirm the card response and
  `GET /api/chinese/stroke-order` remain the same underlying data, not two
  divergent contracts.
- [ ] **Step 7: Chinese-first validation checkpoint.** Confirm stroke order
  sequencing (not just stroke count) renders correctly for at least one
  compound character with a non-obvious stroke order, and that
  `ORENA_UNDERSTANDING_ENGINE.md` §4's accuracy rule is respected: this task
  ships verified structural data only, no mnemonic or etymology text — record
  that explicitly in the commit message so a later task adding mnemonics knows
  this task's data is not itself a mnemonic source.
- [ ] **Step 8: Independent review**, per §6. Commit `feat(vocabulary):
  project the existing Chinese stroke-order capability into orthography cards
  across My Language, the curated catalog, and Daily Feed` and mark **DONE**.
  This is backend/data work reaching all three surfaces; if Step 6's browser
  verification surfaces a UI regression, fix it as part of this task before
  marking DONE, and separately confirm Task E's `READY_FOR_HUMAN_UX_REVIEW`
  state still holds (re-flag for human review only if the visible behavior in
  the two Discover sections materially changed).

---

### Task H: Persistence proposal — conditional, not authorized now

**No schema task is needed or authorized for this plan's MVP.** Tasks A-G ship
a real curated multi-collection Vocabulary Library, a learner/level-aware
Daily Feed, and Chinese orthography, entirely on the existing `saved_words`
table plus static JSON content (§2 above). This section exists only to name,
explicitly, the one trigger that would justify opening a real schema proposal
later, so a future worker does not have to rediscover it:

- **Trigger:** a human product decision to ship learner-created vocabulary
  collections or learner-imported vocabulary collections
  (`ORENA_VOCABULARY_ARCHITECTURE.md` §1's "imported collections where
  supported" and "learner-created collections"). Those need a durable,
  learner-owned, mutable collection object — membership that changes at
  runtime, ownership scoped to an account, and (for imports) rights/provenance
  captured per learner action — none of which a static JSON file can
  represent, and none of which this plan's read-only curated catalog needs.
- **Gate, when that trigger occurs:** follow the same reviewed-schema pattern
  I2 and I3 already used in practice (`docs/project/I2_SCHEMA_REVIEW_REQUEST.md`,
  `docs/project/I3_SCHEMA_REVIEW_REQUEST.md`) — proposal document, delegated
  independent architecture review recorded in Git per `AGENTS.md` §1
  "Architecture review authority" (an implementer may not self-approve its own
  schema change), sandbox-only application after a verified backup/restore
  rehearsal, explicit human authorization before activation. Nothing in Tasks
  A-G may be treated as pre-authorizing any part of that proposal.
- **Not proposed here:** this plan does not draft that document, because the
  trigger has not occurred. Drafting it now, unrequested, would be exactly the
  "schema-authorized-in-passing" pattern this plan's global constraints
  forbid.

---

## Rights and provenance boundaries (applies to Tasks B, C, D, G)

- Every catalog collection and entry (Task B) carries `provenance` stating
  `origin: "curated"` and, for `toeic`/`hsk` framework collections, the
  explicit non-endorsement note from "What this plan explicitly does not
  authorize" above.
- The orthography data Task G projects is the already-vendored external
  reference data at `writing_coach/languages/chinese/stroke_data/`, license
  and provenance already recorded in that directory's `README.md`; cited by
  name/version on every card that uses it, per §16's "preserve appropriate
  source and provenance information."
- Neither surface acquires Reading/Listening rights. A future task connecting
  Feed/Library candidates to real Reading/Listening encounters is out of scope
  here and would need its own rights review under
  `ORENA_CONTENT_EXECUTION_ARCHITECTURE.md` §1.

## Provider/ingestion dependencies

Tasks A-D, G need no provider activation: Task B's catalog and Task G's
stroke dataset are both static, and Task D composes only existing,
already-deployed routes and functions plus the two new read-only ones this
plan adds. A future capability-generated field (an example sentence, a
core-semantic image per `ORENA_VOCABULARY_ARCHITECTURE.md` §2) would go
through the existing expensive-operation contract
(`ORENA_CONTENT_EXECUTION_ARCHITECTURE.md` §3); this plan does not add such a
field.

## EN/ZH and support-language parity

- Every task's seed data, tests and UI copy ship EN and ZH together (Task B
  Step 3, Task E's `copy.js` change).
- Support-language behavior is governed by §3 above: new interfaces carry
  `support_translations`, never a hardcoded language; the existing
  `translation_vi`/My Language path is unchanged and explicitly boundary-mapped
  where the two meet.
- Task G is explicitly "Chinese first" per the Roadmap sequence; it does not
  block Tasks B-E's EN/ZH parity, since ZH cards render correctly with
  `orthography` absent until Task G lands (verified by Task A/C's explicit
  assertion of that case).

## Responsive UX checkpoints

Task E Step 6 is the concrete checkpoint: 1024/800/390/360px widths, EN/ZH,
light/dark, at least two registered themes, keyboard reachability, and
screen-reader label parity with My Language's existing card actions. No task
in this plan touches shared layout primitives, `theme.css`, or global
navigation (all protected areas per `AGENTS.md` §6) — both new sections reuse
`vocabulary-card.js` and Discover's existing section pattern.

## Focused verification commands per task

| Task | Command |
| --- | --- |
| A | `python -m pytest -q tests/test_becoming_library_source_kind.py tests/test_vocabulary_cards.py tests/test_collection_query.py` |
| B | `python -m pytest -q tests/test_vocabulary_library.py tests/test_vocabulary_cards.py tests/test_becoming_library_source_kind.py` |
| C | `python -m pytest -q tests/test_vocabulary_feed.py tests/test_vocabulary_library.py tests/test_vocabulary_cards.py` |
| D | `python -m pytest -q tests/test_vocabulary_library_route.py tests/test_vocabulary_feed_route.py tests/test_vocabulary_feed.py tests/test_vocabulary_library.py tests/test_becoming_library_source_kind.py tests/test_vocabulary_cards.py` |
| E | `node scripts/test_orena_vocabulary_card.mjs && node scripts/test_orena_vocabulary_library.mjs && node scripts/test_orena_vocabulary_feed.mjs` |
| G | `python -m pytest -q tests/test_orthography_projection.py tests/test_chinese_stroke_order.py tests/test_vocabulary_cards.py tests/test_vocabulary_library.py tests/test_vocabulary_feed.py tests/test_becoming_library_source_kind.py` |

Every Python row runs inside the canonical hermetic Docker recipe in
`AGENTS.md` §9; the Node row runs under bare `node` per that same section
("There is no `package.json`; `.mjs` gates run under bare `node`"). Before any
task's completion report claims a result, run the full local suite once per
`AGENTS.md` §9's local recipe and compare the failure count against
`CURRENT_HANDOFF.md`'s current baseline, not a historical number — and label
every such run "local execution," never a CI claim.

## Commit checkpoints and review

Each task above ends its own commit. Tasks A-D end **DONE** after independent
review (§6); Task E ends **READY_FOR_HUMAN_UX_REVIEW** and Task F is the wait
for the human's acceptance before Task G starts; Task G ends **DONE** after
independent review, with its own re-verification of Task E's UI per Task G
Step 8. Task H is documentation only and authorizes nothing.

## Self-review: contradictions and missing requirements checked

- Searched this document for every old "Vocabulary Library = saved words"
  framing from the first version and replaced it; §1 states the corrected
  model and names the exact file/line evidence for why `#/language` was never
  labeled "Library" to begin with.
- Searched for "every task stops at REVIEWABLE" / "only the human sets
  APPROVED" as a blanket line — removed; §6 states the per-task policy the
  task brief requires, with Task F as the one explicit human-wait checkpoint.
- Searched for `translation_vi` as a proposed new canonical field — none;
  §3 states the compatibility boundary explicitly and every new interface
  (Task B's `support_translations`, Task C/D's card shapes) uses the
  support-language-neutral form instead.
- Searched for an unconditional `VocabularyCollection`/membership schema
  assumption — none; §2 states no schema is authorized or needed for the
  MVP, and Task H isolates the one real future trigger and gate instead of a
  false hard stop in front of every other task.
- Confirmed explicit level/framework/topic metadata on every catalog entry and
  collection (Task B), and a learner/context-aware deterministic Feed selector
  contract (§5, Task C) that does not force one shared feed per language
  forever.
- Confirmed the task sequence is A→B→C→D→E→F→G→H and each dependency is real:
  A's card-projection generalization is required before B/C can produce
  catalog/candidate cards; B's catalog is required before C's selector has a
  pool; B+C are required before D's routes; D is required before E's UI; E is
  required before F's human checkpoint; G depends on A's card contract and
  wires into all three surfaces B/C created; H is conditional on none of the
  above and blocks nothing.
- Confirmed existing Chinese stroke-order reuse remains intact end to end:
  Task G still imports `stroke_order.stroke_order_for`, still reuses
  `writing_coach/languages/chinese/stroke_data/` unmodified, and now wires
  into three call sites instead of one without duplicating the dataset.
- Confirmed `git diff --check` reports no whitespace-conflict issues in this
  file (run as part of this revision's self-review).
- Remaining human gates in this plan: only Task F (human UX
  acceptance of the first learner-reachable slice) and Task H's conditional
  future schema gate (not triggered by anything in this plan). No task claims
  human product approval on the human's behalf.
- Known limitations carried forward explicitly rather than silently worked
  around: `declared_level` is `stored=False` today (§4); there is no
  per-request account/session identity in this route family yet (§5); the
  writing evaluator/grammar generation's hardcoded-Vietnamese gap
  (`ORENA_LANGUAGE_COHERENCE.md` AUDIT-2/AUDIT-3) is unrelated to and
  unmodified by this plan.

## What changed from the first version

| First version | This revision | Why |
| --- | --- | --- |
| Library = `renderLanguage()`/My Language, enriched later | Library = new curated catalog section; My Language unchanged | §1 — product-model correction from the task brief |
| Task 0: `VocabularyCollection` schema proposal, hard-blocks Task 6 | No schema task; Task H names a conditional future trigger only | §2 — static catalog fully represents the MVP |
| Feed candidates: separate `data/vocabulary_feed_seed.json` | Feed reads Task B's catalog directly, filtered | One dataset instead of two, truer to "one shared foundation" |
| Card/save fields: `translation_vi` used directly on new shapes | New shapes use `support_translations`; `translation_vi` stays a boundary-mapped compatibility field | §3 — task brief's language-coherence requirement |
| No `level`/`framework` on vocabulary content | Every collection/entry carries `level`, `framework`, `topic` | §4 — breadth metadata requirement |
| Feed selector keyed on `(language_code, date)` only | Selector keyed on `(learner_key, language_code, target_level, date)` | §5 — learner/context-aware requirement |
| Blanket "every task stops at REVIEWABLE; only human sets APPROVED" | Per-task states: backend DONE after independent review; UI READY_FOR_HUMAN_UX_REVIEW then human wait | §6 — task brief's autonomous-approval correction |
