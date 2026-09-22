# Proposal — saved reviews (D-072.1) and discussion over a text (D-072.2)

Status: **AWAITING ARCHITECTURE REVIEW / HUMAN APPROVAL.** Nothing here is implemented.
Written 2026-09-22 after reading the current data model, for the two decisions the human made in D-072.
Learner-owned persistence is a reserved hold (`AGENTS.md`, "Architecture holds"), so this stops at the gate.

---

## What the backend already holds

| Thing | Where it lives today | Verdict |
| --- | --- | --- |
| A review of a piece of writing | `essays` — `summary_vi`, `strengths`, `priorities`, `errors`, `module_data`, the five rubric scores, `level_estimate`, `evaluator` | **Already stored, permanently, per user and language.** |
| The chain of versions | `essay_revisions` (`series_legacy_id`, `revision_no`, `parent_essay_id`) | Already stored. |
| Listing a learner's graded pieces | `GET /api/essays` (limit ≤ 500) → full rows; `GET /api/essays/{id}/review` → `WritingReview` | Already served. |
| Which review the learner chose to keep | — | **Missing.** |
| A discussion about a whole text | — (`conversations` exist only in device memory, `product/memory.js`) | **Missing.** |

**So:** reading a past review back needs no schema at all. Curating *which* reviews are kept, and any
discussion that survives the device, do.

---

## (a) Saved reviews of graded work

### What can ship with no schema change

A "graded work" list in the Writing room, read from `GET /api/essays`: each piece with its date, level
estimate, overall score and version number, opening the piece with its stored review replayed (the room
already does this — `reviewSpeaksTo` in `ui/expression.js`). This makes every review re-readable, which is
most of what D-072.1 asks for, and can be built immediately on request.

### What needs a decision

The frame's **"Lưu nhận xét"** is a *curation* action: the learner marks this review as one to keep. Nothing
records that choice.

- **Data to store:** per essay, whether the learner kept its review, and when.
- **Entity / field:** one nullable timestamp on the existing `essays` row —
  `review_kept_at TIMESTAMPTZ NULL`. No new table: a review has exactly one essay, and the essay is already
  the learner-scoped, language-scoped record. (A boolean would answer "kept"; a timestamp also answers
  "since when", which a list orders by.)
- **API:** `POST /api/essays/{id}/keep` and `DELETE /api/essays/{id}/keep` (idempotent, owner-scoped, echoing
  the new state); `GET /api/essays?kept=true` to list only kept ones. No new response contract — the flag
  rides on the existing essay row, and `WritingReview.json` is unchanged.
- **Relation to user / lesson:** none new. `essays.user_id` and `essays.language_code` already scope it;
  deleting the user cascades (`ondelete="CASCADE"`), so account deletion needs no new path.
- **Migration:** one Alembic revision, `ADD COLUMN review_kept_at TIMESTAMPTZ NULL` — additive, nullable, no
  backfill, no lock of consequence on a table this size, and reversible by dropping the column.
- **Risk:** low. Nothing reads the column until the UI does; an unset column means "not kept", which is the
  truth for every existing row. The only real question is whether learner *curation* belongs on the
  evaluation row at all, or in whatever the account architecture will define for kept things generally —
  that is the reviewer's call, not this lane's.

### Alternative that needs nothing

Treat every stored review as kept (it is), drop the curation button, and ship only the list. The design
draws the button; the human asked for saved reviews. If the reviewer prefers this, say so and the button
leaves the design with a recorded deviation.

---

## (b) Discussion over a whole text

Today a learner can ask about a *selection* (`openUnderstanding`, `/api/sentence-sheet`), and the answer is
kept only in the page. There is no thread about a text, and no conversation table at all.

- **Data to store:** a thread belonging to (learner, text), and its turns: who spoke, the words, when, and —
  for an assistant turn — which provider/model answered, so an answer can be told apart from the learner's
  own words later.
- **Entities / tables:**
  - `text_discussions` — `id`, `user_id` (FK users, CASCADE), `language_code`, `source_kind`
    (`story` | `media` | `reading_session` | `book_chapter`), `source_id` (the same identity string the app
    already routes on, e.g. `story:borrowed-table`), `created_at`, `updated_at`.
    Unique on (`user_id`, `language_code`, `source_kind`, `source_id`) — one thread per learner per text.
  - `text_discussion_turns` — `id`, `discussion_id` (FK, CASCADE), `role` (`learner` | `assistant`),
    `body`, `created_at`, `provider` / `model` (empty for a learner turn), `context` (the passage quoted, if
    any). Index on (`discussion_id`, `created_at`).
- **API:** `GET /api/texts/{source_kind}/{source_id}/discussion` (the thread, or empty),
  `POST …/discussion/turns` (the learner's message; the answer is produced and appended in the same request,
  as the sentence sheet already does), `DELETE …/discussion` (the learner clears their own thread).
- **Relation to user / lesson:** scoped by `user_id` + `language_code`, keyed to the *content identity*
  rather than to a lesson row, because the catalogue is not a table the app owns for every kind of text.
- **Migration:** one Alembic revision creating two tables. Additive, nothing to backfill, reversible by
  dropping them. Account deletion cascades from `users`.
- **Risk:** medium, and higher than (a).
  - It is the first learner-owned *conversational* content to leave the device, which is exactly the
    territory the hold reserves — including what account sync and export owe it later.
  - It is free text a learner writes: retention, deletion and export policy apply to it.
  - Each turn spends a provider call, so the usage/entitlement path (`usage_events`) must cover it before it
    ships, or it is an unmetered AI surface.
  - A thread keyed to a content identity outlives the content if a text is withdrawn; the read path must
    tolerate a thread whose source no longer exists rather than 500.

### Alternative that needs nothing

Keep the discussion in device memory, as conversations already are (that is a design decision, not an
omission — `AGENTS.md`, holds). The pill works, the thread does not follow the learner to another device,
and the UI says so. This ships now and does not pre-empt the account architecture.

---

## What this lane asks for

1. A verdict on (a): the `review_kept_at` column, or the no-curation alternative.
2. A verdict on (b): the two tables now, or device memory until the account architecture lands.
3. If either is approved: an independent architecture reviewer, recorded in Git with the reviewed commit,
   before the migration is written (`AGENTS.md`, "Architecture review authority"; the pattern DC-5 followed
   in D-069).

Until then the Reading bar draws no "Thảo luận" pill and the Writing top bar draws no "Lưu nhận xét", which
is what `UI_BACKEND_GAPS.md` already records.

---

## Architecture review record (2026-09-22)

- **Reviewer role:** Delegated Architecture Reviewer (`AGENTS.md`, "Architecture review authority")
- **Reviewer identity:** an independent Claude subagent, not the implementer's context
- **Reviewed commit:** `6e9774a92074ed8135ff6822aa56170c600371e3`
- **Outcome (a) `essays.review_kept_at`:** `APPROVED` — additive, nullable, no backfill, the same shape as
  D-069's additive columns on `listening_progress`; inherits the essay's `(user_id, language_code)` scoping
  and its cascade from `users`. One required check at implementation: the `keep`/`unkeep` endpoints must
  reuse the existing scoped lookup in `PostgresLearningRepository` so an owner check cannot be skipped.
- **Outcome (b) `text_discussions` + `text_discussion_turns`:** `CHANGES REQUIRED`. The two-table shape is
  right and correctly identified as the first learner-owned conversational content to leave the device, but
  three code-level gaps must close before any migration:
  1. **Metering is new integration, not a copy.** `ProductRepository.record_usage` is called today only from
     `persistence/selftest.py` and tests — no live AI endpoint calls it, including the sentence-sheet surface
     this proposal cited. The turn-creation handler must call it itself
     (`feature="reading.discussion_turn"`), with a test asserting one `usage_events` row per turn.
  2. **Turn order is not deterministic.** Both turns are inserted in one request; `created_at` can tie and
     UUID keys cannot break it. `text_discussion_turns` needs an explicit `ordinal INTEGER NOT NULL`, unique
     with `discussion_id`, as `WritingError` already does.
  3. **Growth is unbounded.** A concrete bound must be stated and enforced: a maximum number of turns per
     thread, or a pagination/truncation contract on `GET …/discussion`.
  Also required: DB-level `CHECK` constraints on `source_kind` and `role` (the `listening_progress` house
  style); a real FK, or a documented reason not to, for `source_kind='reading_session'`, which the app
  already owns a typed row for; and the named mechanism by which a withdrawn source cannot 500 the read.
  Noted with no change required: no EN/ZH parity problem, and the SQLite backend should raise
  `RuntimeError("… requires the PostgreSQL runtime.")` rather than silently no-op, as it already does.

**Where this leaves the work.** (a) may be implemented. (b) is not migrated: the proposal is revised against
the six required changes, then re-reviewed, then the migration is written and applied to the sandbox only -
the pattern D-069 followed.
