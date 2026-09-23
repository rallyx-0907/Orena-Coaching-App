# Adaptive Reading Practice — schema proposal

    STATUS: PROPOSED — needs independent architecture review before it is applied
    LANE:   admin/control-center
    DATE:   2026-09-23

This proposes the persistence Adaptive Reading Practice needs, and nothing
else. It is written to be reviewed and refused in parts: each table stands on
its own reason.

Nothing here is applied. The migration lands in `migrations/proposed/`, which
Alembic does not read, exactly as the Reading Content Engine's did.

---

## What this is for

The human settled the product rule on 2026-09-23:

> Every passage must come from content an Admin deliberately brought in. The
> system does not write source passages with AI. AI is a processor that runs
> *after* the source exists — level, vocabulary, grammar, classification,
> comprehension questions, explanation, evidence.

So Adaptive Reading reads the published Reading corpus and adds three things
the corpus does not have: a reviewed set of comprehension questions per
article, a record of what a learner did with it, and a reading ability that
those records move.

## What already exists and is not rebuilt

| Capability | Where it lives |
| --- | --- |
| Generating comprehension questions with evidence and explanation | `becoming_reading.py` — the generation prompt, the schema validation and the evidence fragment |
| Scoring a set of answers and returning per-question evidence | `submit_reading_answers()` |
| The learner surface for answering and reviewing | `ui/comprehension.js`, mounted by `encounter.js` |
| Published passages with level, topic, word count and learning targets | `reading_articles` (migration `20260923_0013`) |
| Vocabulary from a passage | `openUnderstanding` → the existing Vocabulary flow |

The generation, validation, scoring and evidence logic is reused. What changes
is **where the passage comes from** and **what is remembered afterwards**.

---

## 1. `reading_comprehension_sets`

One reviewed set of questions for one published article.

| Column | Type | Why |
| --- | --- | --- |
| `id` | uuid pk | |
| `article_id` | uuid → `reading_articles(id)` ON DELETE CASCADE | the set has no meaning without its passage |
| `status` | text | `draft` → `needs_review` → `approved` / `rejected` → `archived`. A learner may only meet `approved` |
| `question_count` | int | denormalised for the Admin list, which must not load every question to draw a row |
| `generated_by` | text | which processor version produced it, so a bad batch can be found |
| `model` | text | the model that generated it, for the same reason |
| `analysis_json` | json | validation issues, coverage by question type, grounding failures |
| `reviewed_by`, `reviewed_at`, `review_reason` | text / timestamptz / text | who approved it and why |
| `created_at`, `updated_at` | timestamptz | |

Constraints:

- `UNIQUE (article_id)` where `status <> 'archived'` — one live set per article,
  the same partial-unique shape the engine already uses for `request_hash`.
- `CHECK (status IN (...))`.
- `CHECK (question_count BETWEEN 0 AND 12)` — the product rule is 3–6; the
  bound is wider so a regenerate that produced more is stored and refused by
  review rather than lost by the database.

**Why a set and not a flag on the article:** an article can have a set that was
rejected and a new one being prepared, and the review history of the questions
is not the review history of the passage.

## 2. `reading_comprehension_questions`

| Column | Type | Why |
| --- | --- | --- |
| `id` | uuid pk | |
| `set_id` | uuid → `reading_comprehension_sets(id)` ON DELETE CASCADE | |
| `rank` | int | the order a learner meets them in, the same `rank` idea the learning targets use |
| `question_type` | text | `main_idea`, `detail`, `inference`, `vocabulary_in_context`, `cause_effect`, `sequence`, `authors_purpose`, `reference` |
| `prompt` | text | |
| `options_json` | json | the choices |
| `correct_index` | int | |
| `explanation` | text | |
| `evidence_text` | text | the words from the passage that settle it |
| `evidence_start`, `evidence_end` | int | character offsets into `reading_articles.body`, so the reader can highlight rather than search |
| `admin_approved`, `admin_rejected` | bool | a reviewer may keep a set and drop one question, exactly as they do with learning targets |
| `created_at`, `updated_at` | timestamptz | |

Constraints:

- `CHECK (question_type IN (...))`.
- `CHECK (correct_index >= 0)`.
- `CHECK (evidence_text <> '')` — **the grounding rule, in the database.** A
  question whose answer is not in the passage cannot be stored, so it cannot be
  approved by accident.
- `UNIQUE (set_id, rank)`.

## 3. `reading_practice_attempts`

What a learner did, and what it moved.

| Column | Type | Why |
| --- | --- | --- |
| `id` | uuid pk | |
| `user_id` | uuid | the learner |
| `set_id` | uuid → `reading_comprehension_sets(id)` | |
| `article_id` | uuid → `reading_articles(id)` | denormalised: an attempt must still be readable if a set is archived |
| `language_code` | text | ability is per language |
| `answers_json` | json | `[{question_id, selected_index, correct, question_type}]` |
| `correct_count`, `total` | int | |
| `score` | numeric(5,4) | accuracy, stored rather than recomputed so a later change to scoring does not rewrite history |
| `passage_level` | text | the difficulty faced, at the time faced |
| `ability_before`, `ability_after` | numeric(5,3) | **both**, so progression is readable without replaying every attempt |
| `completed_at` | timestamptz | null until submitted — an unfinished attempt must not move ability |
| `created_at` | timestamptz | |

Constraints:

- `CHECK (correct_count BETWEEN 0 AND total)`.
- `CHECK (total > 0)`.
- Index on `(user_id, language_code, completed_at DESC)` — the progression read.

## 4. `reading_ability`

One row per learner per language.

| Column | Type | Why |
| --- | --- | --- |
| `user_id` + `language_code` | composite pk | |
| `ability` | numeric(5,3) | the current estimate |
| `attempts` | int | how much evidence it rests on |
| `by_question_type_json` | json | accuracy per type, which drives coverage in selection |
| `recent_json` | json | a bounded window of the last N outcomes, so the rule is deterministic without a table scan |
| `updated_at` | timestamptz | |

**Why a table and not a derived read:** selection happens on every passage
request and must not re-read a learner's whole history to answer.

---

## 5. A learner-facing content kind — requested by the learner lane

The canonical Reading Library needs to tell a **Book**, an **Article** and
**News** apart, and `reading_sources.source_type` cannot carry it:
`ck_reading_source_type` allows `manual, direct_url, file, rss, api, feed`,
which is *how content arrives*, not *what a learner is looking at*. The human
settled on 2026-09-23 that these stay separate axes and that an editorial axis
needs its own review — this is that proposal.

Add to `reading_articles`:

| Column | Type | Why |
| --- | --- | --- |
| `content_kind` | text, default `'article'`, NOT NULL | what a learner sees it as |

`CHECK (content_kind IN ('article', 'news', 'book_excerpt', 'essay', 'story'))`.

Default `'article'` because every row that exists today is one, so the backfill
is the default and no data migration runs. The Admin publish contract gains the
field; the learner lane needs no change until it chooses to read it.

---

## 6. Deprecating the AI-generated passage flow

`becoming_reading.create_reading_session` writes a passage with AI, which the
settled rule forbids. It is a **live learner surface**, so it is not deleted in
the same change that replaces it.

1. **Now (no schema):** Adaptive Reading reads published articles. The
   AI-generated route keeps working and is marked deprecated in code and in
   `LEGACY_TOMBSTONES.md`.
2. **After Adaptive Reading is live:** the learner entry points move to the
   corpus-backed route. The old route stays reachable only by an existing
   session id, so an attempt in flight is not lost.
3. **Then:** the route and its generation prompts are removed.
   `reading_sessions`/`reading_attempts` are kept read-only until their history
   has been carried over or deliberately retired, because they are learner
   evidence.

No step deletes learner evidence. Step 3 needs its own authorization.

---

## What is deliberately not proposed

- **No ML.** The first ability rule is deterministic, explainable and testable:
  ability moves by a bounded step scaled by the gap between passage difficulty
  and current ability, damped by how much evidence exists. Selection prefers
  passages near ability, with a periodic deliberate probe. Both live in code
  with tests, not in the schema.
- **No new vocabulary storage.** Words from a passage go to the existing flow.
- **No change to Free Reading.** An article without an approved set is read and
  nothing else, which is most of the corpus.
- **No cross-container locking or media-storage migration.** Unchanged and
  still recorded in `ADMIN_DESIGN_ALIGNMENT.md`.

## Review questions

1. Is `reading_ability` as a maintained table the right call against deriving
   it from attempts on read?
2. Should `content_kind` live on the article or on the source item snapshot?
3. Is storing `ability_before`/`ability_after` on the attempt the right way to
   make progression readable, or should it be an event log?
4. Does the `evidence_text <> ''` CHECK belong in the database, or is grounding
   a review-time rule only?
