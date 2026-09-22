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

---

## (b), revised against the required changes (2026-09-22) — for re-review

This replaces the shape proposed above for (b). Numbers match the reviewer's required changes.

### Tables

`text_discussions`
- `id UUID PK`, `user_id UUID NOT NULL FK users(id) ON DELETE CASCADE`, `language_code VARCHAR(20) NOT NULL`
- `source_kind VARCHAR(32) NOT NULL`, `source_id VARCHAR(255) NOT NULL`
- `reading_session_id UUID NULL FK reading_sessions(id) ON DELETE SET NULL` — **(5)** a real FK for the one
  kind the app owns a typed row for. It is set when and only when `source_kind='reading_session'`; the other
  kinds (`story`, `media`, `book_chapter`) are catalogue content the app owns no row for, so they keep the
  free-form identity string and nothing more. `SET NULL` rather than `CASCADE`: losing the session must not
  delete the learner's words.
- `turn_count INTEGER NOT NULL DEFAULT 0` — **(3)** maintained in the same transaction as a turn insert, so
  the cap is enforced with one read of the thread row rather than a count over turns.
- `created_at`, `updated_at TIMESTAMPTZ NOT NULL`
- `UNIQUE (user_id, language_code, source_kind, source_id)` — one thread per learner per text
- `CHECK (source_kind IN ('story','media','reading_session','book_chapter'))` — **(4)**
- `CHECK ((source_kind = 'reading_session') = (reading_session_id IS NOT NULL))` — the FK and the kind agree
- `CHECK (turn_count >= 0 AND turn_count <= 200)` — **(3)**

`text_discussion_turns`
- `id UUID PK`, `discussion_id UUID NOT NULL FK text_discussions(id) ON DELETE CASCADE`
- `ordinal INTEGER NOT NULL` — **(2)** assigned server-side as `turn_count + 1`, `+2` for the pair written in
  one request, so replay order is deterministic and cannot tie
- `role VARCHAR(16) NOT NULL`, `body TEXT NOT NULL`, `context TEXT NOT NULL DEFAULT ''`
- `provider VARCHAR(64) NOT NULL DEFAULT ''`, `model VARCHAR(128) NOT NULL DEFAULT ''` (empty for a learner turn)
- `created_at TIMESTAMPTZ NOT NULL`
- `UNIQUE (discussion_id, ordinal)` — **(2)**, the `WritingError` precedent
- `CHECK (role IN ('learner','assistant'))` — **(4)**
- `CHECK (char_length(body) <= 4000)` — **(3)** one turn is bounded too, not only the thread

### API

- `GET /api/texts/discussion?source_kind=&source_id=` — the thread for this learner and language, or an empty
  one. **(6)** It reads `text_discussions` and `text_discussion_turns` **only** — it never joins to the
  source table and never resolves `source_id` against the catalogue, so a withdrawn or unknown source cannot
  fail the read. The response carries `source_kind`/`source_id` back unresolved and the room decides what to
  show; `reading_session_id` is returned as `null` when the session was deleted. Turns come back in
  `ordinal` order, newest page last, `limit` ≤ 100 with an `ordinal` cursor — **(3)** the stated pagination
  contract.
- `POST /api/texts/discussion/turns` — the learner's message; the assistant's answer is produced and both
  rows are written in one transaction with `ordinal` `n+1`, `n+2`, and `turn_count` updated. Refused with
  `409` once `turn_count` would exceed 200, naming the cap.
  **(1)** The handler itself calls
  `ProductRepository.record_usage(user_key=..., feature="reading.discussion_turn", amount=1, request_id=...)`
  after the provider answers and before the commit. This is **new integration, not a copy of an existing
  call site**: `record_usage` is today called only from `writing_coach/persistence/selftest.py` and tests, and
  no live AI endpoint meters itself. A test asserts exactly one `usage_events` row per accepted turn, and
  none when the turn is refused by the cap or the provider fails. Entitlement is checked before the provider
  is called, by the same path the other AI features use.
- `DELETE /api/texts/discussion` — the learner clears their own thread (rows deleted, not flagged).
- Export: the thread is included in whatever the account export produces, as `source_kind`, `source_id`, and
  the turns in `ordinal` order with their roles and timestamps.

### Backend shape

- Repository methods live beside the other specialized ones; the SQLite backend raises
  `RuntimeError("… requires the PostgreSQL runtime.")` rather than no-op, as `save_listening_progress_record`
  already does, so CI's SQLite never becomes a second persistence path.
- **(7)** and for (a): `POST/DELETE /api/essays/{id}/keep` go through `PostgresLearningRepository`'s existing
  `(user_id, language_code, legacy_id)` scoped lookup, not a new query.

### What is still true

One Alembic revision, two new tables, nothing to backfill, reversible by dropping them; account deletion
cascades from `users`. Risk is unchanged in kind — this is still the first learner-owned conversational
content to leave the device — and the migration is applied to the sandbox only, after re-review.

**Status: awaiting re-review of this revision.** No migration is written until it passes.

---

## (b), second correction (2026-09-22) — the two changes the re-review required

The re-review (commit `ba64504`) found all six earlier changes closed and raised two more. Both are corrected
here; they replace the sentences they name.

**1. Entitlement gating is new integration too — the earlier sentence was wrong.**
The revision said the turn handler checks entitlement "by the same path the other AI features use". That is
false and is withdrawn: `resolve_entitlement` (`writing_coach/product/commerce.py`) is called only from
`tests/test_product_commerce.py`, `app.py` does not import it at all (verified: zero occurrences), and
`product/api.py`'s `account_state` only surfaces plan and usage to the interface — it gates nothing. **No live
AI endpoint in this repository gates on entitlement today.**

So, exactly like `record_usage`, this is **new integration with no call site to copy**. The handler calls
`resolve_entitlement(user_key=..., feature="reading.discussion_turn", service=product_service)` before the
provider, and answers:
- decision *allowed* → proceed;
- decision *denied* (the plan does not include the feature) → `403` with the feature name and the plan's own
  label, no provider call, no `usage_events` row;
- decision *exhausted* (included but over the monthly limit) → `429` with the limit and what it resets on,
  no provider call, no `usage_events` row;
- decision *unknown* / commerce unavailable → the request proceeds and is metered, which is the behaviour the
  rest of the product already has while `billing_ready` is false everywhere upstream
  (`docs/product/ORENA_COMMERCE_ARCHITECTURE.md`); it must not become a silent denial of a learner's work.

Because this is the first endpoint to gate at all, the same test file asserts each of the four decisions, and
that a refused request writes no `usage_events` row.

**2. `turn_count` and `ordinal` are taken atomically, not read-then-written.**
The two ordinals and the permission to write come from one statement, so two concurrent submits to the same
thread cannot compute the same ordinals:

```sql
UPDATE text_discussions
   SET turn_count = turn_count + 2, updated_at = now()
 WHERE id = :discussion_id AND turn_count <= 198
RETURNING turn_count;      -- the new count; the pair takes ordinals (count - 1) and count
```

No row returned means the cap was reached: the request answers `409` naming the cap, before any provider
call. The `UNIQUE (discussion_id, ordinal)` constraint and the `turn_count <= 200` CHECK stay as the hard
backstops they were, but under this statement a raced double-submit serialises on the thread row and answers
cleanly rather than surfacing a constraint violation as a 500.

**3. Noted, not changed.** 200 turns / 4000 characters is a product-tunable bound, deliberately expressed as a
CHECK so a future change is an `ALTER … CHECK` swap and not a redesign. A retry after a timed-out but
committed `POST` can still double-answer and double-meter: the endpoint accepts a client `request_id` and
returns the existing turns unchanged when it repeats, which is the dedup contract this endpoint owns; the
general idempotency weakness of `record_usage` is older than this proposal and is not solved here.

**Status: superseded by the third correction below.**

---

## (b), third correction (2026-09-22) — the ten blockers of the second re-review

The re-review of `3deab1e` found all ten items below and returned `CHANGES REQUIRED`, with the migration
withheld. Every one was re-verified against the tree before writing this; none is disputed. Blockers 1-6 are
answered by **withdrawing the gate**, blockers 7-10 by naming the mechanisms that were missing. Numbering
matches the review.

### Blockers 1-3, 6 — the entitlement gate is withdrawn from this proposal

The second correction's 403/429 gate is **withdrawn in full**. It was wrong three ways at once, and each
would have been enough on its own:

- **It is forbidden today.** `writing_coach/product/commerce.py:1-8` — "it enforces nothing: `billing_ready`
  stays `False` and no route may deny a request from `resolveEntitlement` yet."
  `ORENA_COMMERCE_ARCHITECTURE.md:113` — "Existing non-enforced behavior remains until the explicit
  activation gate. Do not quietly enable billing during account or UI implementation." Making a learner-facing
  feature proposal the product's first enforcing route is an activation decision, and it is not this lane's.
- **As specified it denied every learner.** `reading.discussion_turn` is in neither plan
  (`product/catalog.py:42-76`), so `ProductService._feature_access_for_plan` (`service.py:60-63`) answers
  `entitlement_state="unavailable"`, `enabled=False`, and `resolveEntitlement` turns that into
  `allowed=False, reason="not_in_plan"` — a 403 for Free *and* Premium. The "unknown → proceed" escape never
  fires for an unlisted feature: `allowed=None` is reached only when `monthly_usage` itself raises
  (`reason="usage_unavailable"`). `tests/test_product_commerce.py:121` locks that behaviour deliberately.
- **The symbol and the decision shape were wrong.** It is `resolveEntitlement(user_key, feature, *,
  service=None)`, not `resolve_entitlement`, and `EntitlementDecision` carries
  `allowed: bool | None, reason, entitlement_state, quota` — there is no `exhausted` decision to switch on.

**What the handler does instead:** it resolves nothing and denies nothing. It meters
(`record_usage`, below) and answers the learner. This keeps the endpoint exactly as
non-enforcing as every other AI surface in the product, which is the state the commerce architecture
requires until its own gate.

**Escalated to the human as an activation gate, not decided here** (`AGENTS.md`, "Safety" → human gates;
`ORENA_COMMERCE_ARCHITECTURE.md` §5):

> Should `reading.discussion_turn` become the product's **first entitlement-enforcing route**? That requires
> (i) authorization to switch enforcement on at all, (ii) the feature key and its per-plan monthly limits
> added to `FREE` and `PREMIUM` as policy values, and (iii) the admission ledger named in blocker 4. Until
> the human answers, the endpoint meters and does not deny, and this proposal assumes no denial path exists.

**Which identity is metered (blocker 6).** One key, the learner's: `current_user_key()` from
`writing_coach/core/request_context.py` — the same `USER_KEY_CTX` value the thread's `user_id` resolves from,
so the metered row and the learner's rows can never belong to different accounts. The handler does **not**
call `product/api.py:current_user_key`, which answers `"local-development"` while `AUTH_ENABLED` is false and
would meter the sandbox's turns against an account that owns no threads. With auth on, both are `user_sub`
and the distinction disappears. Recorded, not resolved: while auth is off, `/api/product/me` reads
`"local-development"` and will therefore not show usage recorded under `"legacy"` — a local-development
reporting discrepancy that exists already and that only the account architecture should close.

### Blocker 4 — the quota ledger seam, and why this proposal does not meter into it

`writing_coach/persistence/quota_repository.py` ("DEPLOYED, INACTIVE") implements
reserve / dispatch / settle / release over migration `20260912_0007`, exactly-once by `operation_id`, and is
the sanctioned atomic admission path. `ORENA_COMMERCE_ARCHITECTURE.md:98` says plainly that
"existing monthly_usage is a reporting read; it does not make parallel admission atomic."

This proposal writes to `usage_events` and **not** to the quota ledger, for one reason: the ledger keys every
bucket, reservation and lock off an **account incarnation** (`reference_backbone.Scope`), and nothing in this
codebase resolves a live incarnation from a request — `commerce.py:9-14` says so, and `account_profile.scope_of()`
has no production caller. Wiring incarnation resolution into a request path is learner-account architecture,
which is a reserved hold (`AGENTS.md`, "Architecture holds").

That is also the honest argument against the withdrawn gate: a feature that cannot reach the atomic ledger has
no business being the first one to deny. `usage_events` is adequate for a reporting count and inadequate for
admission; since nothing is admitted or refused on it, the weakness costs nothing. **If the human activates
enforcement, it must go through `PostgresQuotaRepository`, and incarnation resolution becomes a prerequisite
of that gate — not of this feature.**

### Blocker 5 — where `record_usage` runs

`PostgresProductRepository.record_usage` opens `Session(self.engine) … session.begin()`
(`persistence/product_repository.py:70`): its own transaction. It cannot run "before the commit" and cannot be
rolled back with the turn. The contract is therefore **ordering**, stated as such:

`record_usage` is called **after** the transaction that stores the two turn rows has committed, and only then.
One accepted turn writes exactly one `usage_events` row; a turn refused by the cap, refused by ownership,
rejected as a duplicate `request_id`, or lost to a provider or storage failure writes none. The tests assert
the ordering (no usage row when the turn is absent), not an atomicity the call cannot offer. A crash between
the two commits under-counts by one turn; under-counting a reporting read that gates nothing is the cheaper
error, and the alternative — metering before the turn is durable — over-counts against a learner.

### Blocker 7 — the reservation is owner-scoped, and its zero-row case is disambiguated

```sql
UPDATE text_discussions
   SET turn_count = turn_count + 2, updated_at = now()
 WHERE id = :discussion_id AND user_id = :user_id AND turn_count <= 198
RETURNING turn_count;      -- the pair takes ordinals (count - 1) and count
```

Zero rows now means cap **or** deleted **or** not yours, so it is never answered blind: in the same
transaction the handler re-reads `SELECT turn_count FROM text_discussions WHERE id = :discussion_id AND
user_id = :user_id`. A row → the cap was reached → `409` naming the cap. No row → `404`. A thread belonging to
another learner is indistinguishable from a missing one, deliberately.

### Blocker 8 — the first turn, and two concurrent first submits

The thread is get-or-created before the reservation, in one statement pair that cannot raise on the race the
`UNIQUE (user_id, language_code, source_kind, source_id)` constraint creates:

```sql
INSERT INTO text_discussions (id, user_id, language_code, source_kind, source_id,
                              reading_session_id, turn_count, created_at, updated_at)
VALUES (:id, :user_id, :language_code, :source_kind, :source_id, :reading_session_id, 0, now(), now())
ON CONFLICT (user_id, language_code, source_kind, source_id) DO NOTHING;

SELECT id, turn_count FROM text_discussions
 WHERE user_id = :user_id AND language_code = :language_code
   AND source_kind = :source_kind AND source_id = :source_id;
```

The loser of the race inserts nothing and selects the winner's row; both then contend on the reservation
`UPDATE` above, which serialises them on that row. No unique violation reaches the learner as a 500.

`reading_session_id` is resolved here and nowhere else: when `source_kind='reading_session'`, `source_id` is
the session id, and the handler looks it up through the existing learner-scoped reading-session lookup before
the insert — not found, or not this learner's, is `404` and no thread is created. For the other three kinds it
is `NULL`, which is what the `CHECK ((source_kind = 'reading_session') = (reading_session_id IS NOT NULL))`
already requires.

### Blocker 9 — the transaction boundary, named

**The reservation commits before the provider is called.** Three transactions, in this order:

1. **T1** — get-or-create (blocker 8) and the owner-scoped reservation (blocker 7). Commits. No lock is held
   after it.
2. **the provider call** — outside any transaction.
3. **T2** — insert the learner turn and the assistant turn at the reserved ordinals. Commits.
4. **`record_usage`** — its own transaction, after T2 (blocker 5).

**The compensating behaviour is deliberately none, and the cost is a gap.** If the provider fails, the
reserved ordinal pair is never written: `ordinal` stays unique and monotonic with a hole in it, which the read
path does not care about because it orders by `ordinal` and never assumes contiguity. `turn_count` is *not*
decremented — a decrement would re-issue ordinals that a concurrent submit may already hold, turning a failed
call into a `UNIQUE (discussion_id, ordinal)` violation for an unrelated learner request. A failed attempt
therefore consumes two of the thread's 200 turns permanently.

The alternative — holding T1 open across the provider call — was rejected: the thread row's lock would be held
for the whole provider latency (17-54 s on the sandbox's Ollama default, `CLAUDE.md`), so every concurrent
submit to that thread would block for it, and a provider timeout would hold it longer still. Leaking cap on
failure is bounded, visible and recoverable by a future `ALTER … CHECK`; blocking a learner's thread for a
minute is not.

### Blocker 10 — the dedup column, which is schema

`text_discussion_turns` gains:

- `request_id VARCHAR(64) NOT NULL DEFAULT ''` — the client's idempotency key, stored on the **learner** turn
  only; the assistant turn of the pair keeps `''`.
- `CREATE UNIQUE INDEX … ON text_discussion_turns (discussion_id, request_id) WHERE request_id <> ''` — a
  partial unique index, so the empty default and every pre-existing row are unconstrained.

The contract: `POST` accepts an optional `request_id`. Before reserving, the handler selects the learner turn
with that `(discussion_id, request_id)`; found → it returns that turn and the one at the next ordinal
unchanged, with **no** reservation, no provider call and no `usage_events` row. A repeat that arrives while
the original is still in flight loses the partial unique index at T2 instead: the handler catches that one
violation, re-reads the committed pair and returns it the same way (its own reserved ordinals become a gap,
exactly as in blocker 9). A `POST` with no `request_id` is not deduplicated and says so.

`request_id` is also what is passed to `record_usage(request_id=...)`, so a usage row can be traced back to
the turn that caused it.

### What this changes about the migration

The migration is still one Alembic revision creating two tables, but its text now differs from the second
correction in three places: `text_discussion_turns.request_id` and its partial unique index (blocker 10), and
no entitlement-related column or constraint anywhere (blockers 1-3). Nothing in `usage_events`, `quota_*` or
`commerce_*` is touched. The ledger question (blocker 4) does not change which tables this creates — it
changes what a future activation gate must do, and is recorded above rather than resolved.

**Status: awaiting re-review of this correction, and a human answer on the activation gate raised under
blockers 1-3.** No migration is written until the re-review passes; nothing gates on entitlement in any case
until the human opens that gate.
