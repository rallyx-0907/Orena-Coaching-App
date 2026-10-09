# Architecture review: plan quota enforcement core (D-160)

Recorded in Git as AGENTS.md "Architecture review authority" requires. PR #116, branch `feat/quota-core`.

| | |
|---|---|
| Reviewer | claude-opus-5-5, Delegated Architecture Reviewer (independent of the implementer) |
| Reviewed commits | `4fbd15a2`, `85444275`, `40443ed1` (on `daf2deea`) |
| Verdict | **REQUEST CHANGES** (one P1; expected APPROVE WITH REQUIRED CHANGES once P1-1 is fixed with a regression test) |
| Fixes | see "Fixes" at the end; the fixes themselves are not yet re-reviewed |

The review text follows as the reviewer wrote it.

- **Reviewer:** claude-opus-5-5, acting as the **Delegated Architecture Reviewer** (AGENTS.md, "Architecture review authority"). I did not write this change. The review was read-only: I made no edits, commits or pushes, and changed no runtime. I used one throwaway `postgres:17-alpine` container on its own private network, then stopped it and removed the network.
- **Reviewed:** branch `feat/quota-core` in worktree `agent-a05cad179be992b82`, commits `4fbd15a2`, `85444275` and `40443ed1` on top of `daf2deea` (`git diff daf2deea..HEAD`, 30 files).
- **Inputs:** the approved contract `scratchpad/QUOTA_CONTRACT.md`, the implementer's `qp/PR_BODY.md`, and the human decisions from 2026-10-09:
  - the design's Pricing frame is the plan source of truth;
  - each AI evaluate or improve that actually runs counts as one review, and a cached identical evaluation is free;
  - windows follow the learner's timezone, and a zone change never resets or reopens the current window;
  - Free to Plus applies immediately and keeps usage;
  - costly metered operations fail closed;
  - nothing is enforced on the client.

## VERDICT: REQUEST CHANGES

There is one P1. Concurrent requests that name different timezones each create their own window, and each window has a full allowance. I reproduced this on real PostgreSQL. Everything else holds or is P2/P3. Once P1-1 is fixed and has a regression test, I expect to give **APPROVE WITH REQUIRED CHANGES**, with the P2s as the required changes.

## Evidence (local runs, not CI)

All runs used an ephemeral `ai-writing-coach:local` container with the worktree mounted read-only.

- **PostgreSQL proofs** on a throwaway `postgres:17-alpine`: `tests/test_orena_quota_persistence_postgres.py` and `tests/test_quota_gate_postgres.py` gave **47 passed** (the 28 existing, 6 new repository tests and 13 gate tests).
- **Hermetic tests:** `tests/test_quota_gate.py` together with the product and admin tests gave **349 passed**.
- **Reviewer reproduction** (`qp/review_tests/test_review_zone_race.py`, not part of the change):
  - Setup: a Free account (2 reviews a month) with no bucket yet, and 10 threads calling `quota.admit("writing.review")`, each with a different `X-Orena-Timezone`.
  - Result: **10 of 10 admitted, with 10 overlapping buckets** (`M:2026-10@UTC`, `M:2026-10@Asia/Tokyo`, ...).
  - Without any injected delay, the result was `[10, 10, 10, 10, 10]` over 5 rounds.

## Findings

### P1-1: Concurrent requests with distinct timezones create overlapping windows and multiply the allowance

- **Where:**
  - `writing_coach/product/quota.py:519-529`: `latest_buckets()` is read with no lock, `window_for()` runs, then `reserve()`.
  - `writing_coach/persistence/quota_repository.py:288-316`: the bucket is looked up and inserted by `window_id` only. Nothing checks for another bucket of the same `(incarnation, meter)` whose time range overlaps.
- **Failure scenario:**
  1. A learner's first use, or the first request after their previous window closed, has no open bucket to reuse.
  2. N concurrent requests each send a different valid zone. The header is client-controlled, and about 600 IANA names are accepted.
  3. Each request computes a different `window_id`. Each inserts its own bucket and is admitted against that bucket's full limit.
  4. Afterwards only the bucket with the latest `window_end` is "current", so the orphan buckets' usage disappears from both the 429 body and the Plan screen.
- **Impact:**
  - The only cap is the per-process brake: `writing_ai` allows 30 requests per 600 s per worker. A Free account gets about 30 AI reviews per worker each month instead of 2, and can repeat this at every window transition.
  - This breaks the human's rule that a zone change must never reopen a window.
  - It makes D-160's claim that "zone hopping cannot multiply windows" untrue under concurrency.
  - The approved Free → Plus → Free test and the "5 concurrent → 1 provider call" proof both start from an existing open bucket with no zone header, so neither covers this case.
- **Required fix (no schema change):**
  1. In `reserve(limit_policy='current')`, after the incarnation `FOR SHARE` and before the bucket lookup or insert, take `pg_advisory_xact_lock` keyed on `(incarnation_id, meter)`.
  2. Under that lock, look for any bucket of `(incarnation_id, meter)` with a different `window_id` that is open at `now` or overlaps `[window_start, window_end)`. If one exists, return a new no-write status such as `window_superseded`.
  3. In the service loop (`quota.py:519-537`), treat that status like `window_closed`: read `latest_buckets` again and recompute.
  4. The resulting lock order (incarnation → advisory → bucket → reservation) still has no cycle with settle/release (bucket → reservation), dispatch (incarnation → reservation) or `mark_deleted`.
- **Required tests (PostgreSQL):**
  - N concurrent first uses in N zones.
  - N concurrent requests in N zones just after a closed window.
  - Both must admit no more than the limit and leave exactly one bucket open at `now`.
  - Correct the D-160 wording until the fix is in.

### P2-1: The switch fails open when its value lives in the admin setting

- **Where:** `quota.py:186-207` and `quota.py:215-237`.
- **Failure scenario:**
  - With compose's default, both environment variables are empty and the admin setting `product.quota_enforcement` decides.
  - In a fresh worker, if the first `get_setting` fails, `_switch_last_good` is `None`. That gives `enabled=False` and `meters=[]`, so the state is `off`, `NullTicket` is used, and the AI runs unmetered.
  - The same happens when `ORENA_QUOTA_ENFORCEMENT=on` is set but `ORENA_QUOTA_METERS` is empty and the setting cannot be read or is absent. Enforcement silently does nothing even though the operator said "on".
- **Required fix:**
  - When the setting cannot be read and there is no last good value, answer `unavailable` (503) for `WIRED_METERS`, unless the environment explicitly says `off`.
  - When the environment says `on` and no meter resolves, also answer `unavailable` and log an error. Do not answer `off`.
  - For :8000, pin both environment variables so the setting is never the authority there.
  - Add a test for each case.

### P2-2: `/api/improve` turns quota and deletion refusals at dispatch into a 502

- **Where:** `app.py:2505-2512`. `ticket.dispatch("improve")` sits inside `try`, so `except Exception` converts its `HTTPException` (503 `quota_unavailable` or 403 `account_deleted`) into a 502 "invalid structured output".
- **Impact:** it still fails closed (the provider is not called and the reservation is released), but the status and category are wrong.
- **Fix:** call `dispatch` before `try`, or add `except HTTPException: raise` first. Add a test.

### P2-3: Provider work that was billed is settled at 0 when its output is unusable (decision record, not a code defect)

- **Where:** `app.py:1533-1541` and `app.py:3048`. `AIProviderError` (the provider answered but the output could not be used) leads to `fallback-demo` or a 502, and the ticket settles 0.
- **Assessment:** this is consistent with the approved contract ("learner got nothing"). However, provider spend that ends this way is bounded only by the per-process brake.
- **Action:** record it as an explicit human decision in D-160, and keep the brake.

### P3 findings

- **P3-1: the reconciler is not scoped by meter.**
  - `reconcile_once` (`quota.py:625-641`) settles or releases any open reservation older than 15 min.
  - Before an async meter is wired (media import, where the worker settles), filter it by meter (join the bucket).
  - `stale_dispatched` has no `(state, updated_at)` index, so it scans the whole table every 10 min in every worker as reservations grow. A partial index belongs in a later reviewed migration.
- **P3-2: plan and revision label can come from different catalogue reads.** `quota.py:505-506` reads the plan and the revision label through two separate cache lookups, so the plan's limit and the stored `policy_version` can disagree across an admin save. Take both from one `current_catalog(strict=True)`.
- **P3-3: the `BucketWindow` docstring is now false in `'current'` mode.** `quota_repository.py:85-94` says the stored limit and policy are "never overwritten", but `'current'` mode overwrites both.
- **P3-4: the display catalogue read is lenient while enforcement is strict.** `service.account_state` uses lenient `plan_by_id`. When the catalogue is unreadable, the Plan screen shows the built-in limits as `known` while enforcement answers 503. The contract asks for `unavailable`.
- **P3-5: the quota store is resolved once, at import.** `_quota_store()` runs once (`app.py:1074-1104`). If the database is unreachable at startup, enforcement stays 503 until a restart. This fails closed, but never recovers on its own.
- **P3-6: deleting and re-registering an account resets quota.** `register_new` creates a new incarnation, which gets fresh buckets. Note this for the account-deletion runtime, which is reserved to the human.
- **P3-7: every refusal writes to the bucket.** The exhausted path issues an `UPDATE` on each refusal, which multiplies writes under a 429 storm. Skip it when `unit_limit` and `policy_version` are unchanged.
- **P3-8: a fixture still uses v1 keys.** `scripts/fixtures/api/product_commerce.json` still carries the v1 keys.

## Verified as sound

- **Lock order is unchanged.** Incarnation `FOR SHARE` → bucket `FOR UPDATE` → reservation, and `'current'` mode adds no lock.
- **The bucket's CHECK holds.** On admit, `unit_limit = limit`, which is at least the new `consumed + reserved`. On exhausted, `GREATEST(limit, consumed + reserved)`, so a downgrade cannot break it. This is tested.
- **Frozen mode is unchanged.** The code path is the same and the 28 existing PostgreSQL tests pass.
- **Idempotency works.** A replay with the same `operation_id` is recognised by its whole identity, and a different payload under that id is a `payload_conflict`. The concurrent same-key proof passes.
- **The reconciler and a slow live request cannot double-count.** The state machine under the bucket lock prevents it:
  - If the reconciler settles first, the live request's later settle gets `payload_conflict` or `duplicate` and writes nothing.
  - If the reconciler releases a stale `reserved` row, a later live `dispatch` gets `already_released`, which leads to a 503, and the provider is not called.
  - Counts cannot go negative: the state machine settles or releases each reservation only once, and the table's `reserved >= 0` CHECK backs this up.
- **Sequential timezone changes give no meaningful gain.**
  - An open latest bucket is always reused, so a change never reopens or resets the current window.
  - A new window starts at or after the previous end and lasts at least 23 h for a day or 27 days for a month.
  - The best attack, hopping one hour east each day, yields about 24/23 of the allowance and is bounded by the range of zones.
  - DST days of 23–25 h and 30-minute zones are handled.
  - `window_id` is at most 60 characters, which fits `String(60)`.
  - Invalid zones fall back to the zone of the last window, then to UTC.
- **Identity fails closed.**
  - SQLite, missing tables or the backbone being off → 503 when enforcement is on.
  - Deleted account → 403.
  - No `users` row → 409.
  - Local mode is metered as "legacy", and the Plan screen now reads the same account.
- **The routes are wired correctly.**
  - `/api/evaluate` admits only after both cache checks, so a cached identical review is free.
  - Fallback and provider errors settle 0, and `/api/improve` admits before its `try`.
  - No other caller of `evaluate_with_ai` or `improve_with_ai` exists. The agent only reads stored evaluations.
  - The refresh route is unmetered (the default pending the human). It is bounded by the stored language pair and a contract change, and rate-limited under `essay_ai`.
- **The catalogue fails closed.**
  - The strict read raises on a store error or an invalid document, and a failed read is never cached.
  - A v1 document keeps its prices.
  - A save must be v2 and is validated.
  - The mobile `/me` projection keeps the frozen strict schema.
- **There is no client enforcement.** The client only sends `Idempotency-Key` and `X-Orena-Timezone` and renders the server's 429.
- **Usage display matches enforcement.** Both read the same latest bucket and catalogue limit (the P1-1 orphans aside). A store error shows `unavailable`, never "0 used", and an unenforced meter shows `not_metered`.

## Missing tests to add

- The P1-1 races: first use, and a closed-window transition.
- Switch read failure → fail closed (P2-1).
- `/api/improve` dispatch failure status (P2-2).
- In `'current'` mode, the reconciler settles first, then a late live settle writes nothing and nothing is double-counted.

## Fixes (implementer, after this review; awaiting re-review)

| Finding | Fix | Commit |
|---|---|---|
| P1-1 concurrent distinct-zone windows | `reserve(limit_policy='current')`: `pg_advisory_xact_lock(hashtextextended('quota:<incarnation>:<meter>', 0))` after the incarnation `FOR SHARE`, before any bucket; a window another bucket of the meter is open in at `now` or overlaps is refused as `window_superseded` (nothing written); the service treats it like `window_closed` (re-read the latest bucket, recompute, at most `WINDOW_RETRIES = 4`). Lock order incarnation -> advisory -> bucket -> reservation; settle/release (bucket -> reservation), dispatch (incarnation -> reservation), `mark_deleted` and frozen mode never take the advisory lock, so no cycle. D-160 wording corrected. | `fef64cd5` |
| P1-1 tests | PostgreSQL: the reviewer's reproduction (both variants, also run unmodified from the review's file), 10 zones at first use and 10 zones just after a closed window: admitted <= 2 and exactly one bucket open at `now`; a covered window is `window_superseded` with no bucket written. | `fef64cd5` |
| P2-1 switch fails open | `=off` -> off; `=on` with no wired meter -> 503 `no_meters` (error logged); unset + setting unreadable in a process that never read it -> 503 `switch_unreadable`; a failure after a good read keeps the last value; nothing stored -> off. D-160 says :8000 must pin both environment variables. Hermetic tests for each case. | `e919a6c6` |
| P2-2 improve 502 | `ticket.dispatch("improve")` before the `try`; tests: dispatch `denied` -> 403 `account_deleted`, dispatch store error -> 503 `quota_unavailable`, provider not called, reservation released. | `e919a6c6` |
| P2-3 unusable output settles 0 | Behaviour kept; recorded as a human decision to confirm in D-160 point 10 and `UI_BACKEND_GAPS.md` QTA-10. | docs commit |
| P3-1 reconciler scope / index | `stale_dispatched(..., meters=)` joins the bucket; the reconciler passes `SYNC_METERS`. The `(state, updated_at)` index needs a migration: recorded (QTA-11a), not added. | `fef64cd5` |
| P3-2 plan vs revision | Plan limits and `policy_version` come from one `current_catalog(strict=True)` snapshot; the subscription read only names the plan. | `fef64cd5` |
| P3-3 docstring | `BucketWindow` docstring describes both modes. | `fef64cd5` |
| P3-4 display strict | `usage_for` answers `unavailable` when the strict catalogue read or the switch fails. | `fef64cd5` |
| P3-5, P3-6 | Recorded (QTA-11b, QTA-11c). | docs commit |
| P3-7 refusal writes | The exhausted `UPDATE` is skipped when the stored limit and policy are already the computed ones. | `fef64cd5` |
| P3-8 fixture | `scripts/fixtures/api/product_commerce.json` in catalogue v2. | `9d014ba5` |
| Missing test: reconciler first, late live settle | PostgreSQL test: the reconciler settles a stale dispatched current-mode reservation; the live repository settle answers `payload_conflict` and the live ticket's settle writes nothing; the bucket is unchanged (consumed 1, reserved 0). | `fef64cd5` |

Evidence after the fixes (local execution, not CI):

- PostgreSQL, on a throwaway `postgres:17-alpine` that was removed afterwards:
  - `tests/test_orena_quota_persistence_postgres.py`: 34 passed
  - `tests/test_quota_gate_postgres.py`: 18 passed
  - the reviewer's `test_review_zone_race.py`, unmodified: 2 passed
- Hermetic `tests/test_quota_gate.py`: 37 passed.
- Full suite (`ai-writing-coach:local`, SQLite): 5206 tests, 0 failures, 0 errors, 409 skipped.
- Node gates from ci.yml: 124/124 passed. The ten Python CI scripts are OK.

## Re-review (2026-10-09)

- **Reviewer:** claude-opus-5-5, still acting as the independent Delegated Architecture Reviewer. Read-only; one throwaway `postgres:17-alpine` container on a private network, removed afterwards.
- **Reviewed HEAD:** `524a03df` on `feat/quota-core`. The fix commits are `fef64cd5`, `e919a6c6`, `9d014ba5` and `524a03df`; I reviewed `git diff 40443ed1..524a03df`.

### VERDICT: APPROVE

The P1 is fixed and proven on PostgreSQL. Both code P2s are fixed with tests, and P2-3 is recorded as a human decision (D-160 point 10, QTA-10). No P0, P1 or P2 remains. Three P3 notes follow below; none blocks.

### Evidence (local runs, not CI)

All runs used an ephemeral `ai-writing-coach:local` container with the worktree mounted read-only.

- **My original reproduction, unmodified** (`qp/review_tests/test_review_zone_race.py`):
  - The no-delay variant now admits **[2, 2, 2, 2, 2]** over 5 rounds, which is exactly the Free limit. It admitted [10, 10, 10, 10, 10] before the fix.
  - The variant with my injected barrier now leaves **1 bucket and 1 admission**. Its other 9 calls answer 503, but only because of my test harness: my barrier waits for all 10 threads, and the retry re-reads fewer than 10, so it times out. The property under test holds.
- **PostgreSQL and hermetic tests:** `tests/test_quota_gate_postgres.py`, `tests/test_orena_quota_persistence_postgres.py`, `tests/test_quota_gate.py` and the product and admin tests gave **409 passed**.
- **Race tests repeated:** the race, transition, superseded and reconciler tests passed 3 times in a row (6 passed each time).

### Each finding, verified

**P1-1 is fixed.**

What the fix does:
- In `reserve(limit_policy='current')`, after the incarnation `FOR SHARE`, it takes `pg_advisory_xact_lock(hashtextextended('quota:<incarnation>:<meter>', 0))`.
- Under that lock, it looks for any bucket of the same (incarnation, meter) with a different `window_id` that is open now or overlaps the requested window. If it finds one, it returns `window_superseded` and writes nothing.
- The service then re-reads the latest bucket and retries, up to `WINDOW_RETRIES = 4` times.

Why it is correct:
- **The rival is always visible.** The rival query runs only after the advisory lock is granted, which happens after the bucket's creator has committed. So the loser always sees the winner's committed bucket, and its re-read finds that bucket open and reuses it. One retry is enough.
- **Normal transitions are not affected.** A new window starts at or after the previous `window_end`, so the overlap test, `start < prev_end AND prev_start < end`, is false for a closed previous window. The closed-window transition race test passes.

Lock order is now incarnation (SHARE) → advisory → bucket → reservation. I checked for cycles:
- Only current-mode `reserve` takes the advisory lock, and it takes it before any bucket or reservation lock.
- A transaction that is waiting for the advisory lock holds only a SHARE lock on the incarnation. SHARE locks are compatible with each other, and `mark_deleted` simply waits behind them.
- `settle` and `release` take bucket → reservation, and `dispatch` takes incarnation → reservation. None of them takes the advisory lock.
- Each transaction takes at most one advisory key, so a hash collision between two keys only serialises unrelated work; it cannot form a cycle.
- A wait on the reservation's unique `operation_id` index is a wait on a transaction that is already past its advisory step and never waits on an advisory lock again.

So there is no deadlock path. Frozen mode does not take the lock and is unchanged; its 28 existing tests pass.

**P2-1 is fixed, and the switch no longer fails open anywhere I can find.** I traced every combination:

| Environment | Meters | Setting read | Result |
|---|---|---|---|
| `off` | any | not consulted | off |
| `on` | in the environment | not read | enforced, or 503 if there is no store |
| `on` | not in the environment | succeeds, lists meters | enforced |
| `on` | not in the environment | fails or lists none | 503 (`no_meters` or `switch_unreadable`) |
| unset | any | fails, never read in this process | 503 for every wired meter |
| unset | any | nothing stored | off |
| unset | any | fails after an earlier good read | the last good value (the accepted default) |

- `admit()` raises 503 before the store path whenever the state is `unavailable`.
- `configure_quota` now resets the "ever read" state.
- Six hermetic tests cover these cases.

**P2-2 is fixed.** `ticket.dispatch("improve")` now runs before the `try`. A parametrized test proves the 503 and 403 refusals keep their own status and category.

**P2-3 is recorded** as a human decision in D-160 point 10 and in `UI_BACKEND_GAPS.md` QTA-10.

**P3-1 is fixed.** The reconciler is limited to `SYNC_METERS` through a bucket join. A new test shows that when the reconciler settles first, a late live settle writes nothing and nothing is double-counted. The missing index is documented.

**P3-2 is fixed.** The limit and the policy label now come from one strict catalogue snapshot. A legacy "premium" plan id still resolves through `plan_by_id`'s alias.

**P3-3 is fixed.** The `BucketWindow` docstring now describes both modes.

**P3-4 is fixed.** `usage_for` reports `unavailable` when the strict catalogue read fails, or when the switch is `unavailable`.

**P3-7 is fixed.** The exhausted path's `UPDATE` is skipped when nothing changed.

**P3-8 is fixed.** The API fixture is on catalogue v2.

**P3-5 and P3-6 are recorded** (QTA-11b and QTA-11c).

### Remaining notes (P3, none blocking)

- **R-1, pre-fix orphan buckets.** A runtime that ran `85444275` or `40443ed1` with enforcement on may hold overlapping buckets for some learner. The new rival check would then answer `window_superseded` on every retry, and that learner would get a 503 (`window`) until the orphan window closes. Before enabling enforcement on such a runtime, check that this query returns no rows:
  `SELECT a.incarnation_id, a.meter FROM commerce_quota_buckets a JOIN commerce_quota_buckets b ON a.incarnation_id = b.incarnation_id AND a.meter = b.meter AND a.id < b.id AND a.window_start < b.window_end AND b.window_start < a.window_end`
- **R-2, compose default.** Compose leaves `ORENA_QUOTA_ENFORCEMENT` empty. On a deployment that never meant to enforce, a settings read that fails in a fresh worker now answers 503 for `writing.review`. The impact is small because the setting lives in the same PostgreSQL store that `/api/evaluate` reads first. Still, until the human's GO, :8000 should pin `ORENA_QUOTA_ENFORCEMENT=off`, as D-160 already says it must.
- **R-3, stale last good value.** After a good read, a failing setting store keeps the last value indefinitely, which may be off. This is the accepted human default. It is not fail-open in the "never known" sense.

**Unchanged:** this review is not product approval and not an activation authorization. :8000 still needs the human's explicit GO.
