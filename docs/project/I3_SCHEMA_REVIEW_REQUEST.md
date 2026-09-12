# I3 schema proposal — architecture review request for Codex/GPT-6

This document now covers two independent proposals under I3 ("Plans,
subscription and quota", `ORENA_BACKBONE_INTEGRATION_GATES.md`):

1. **Subscription state and the provider-event inbox** — submitted, reviewed
   once (CHANGES REQUESTED), revised, **awaiting re-review**. Unchanged since
   that revision. See the section immediately below.
2. **Quota buckets and reservations** — new in this revision, **first
   submission**, not yet reviewed at all. See "New: I3 quota buckets and
   reservations" further down. It has no foreign key into either table from
   proposal 1 — the two are reviewable independently — but its migration
   chains on top of proposal 1's (named as an open question in its own
   section, not hidden).

## Response to review of `2a7484d9ed3408b19adb0e083d7e5844e4b645bf`: CHANGES REQUESTED, addressed

| | |
| --- | --- |
| Reviewer role | Delegated Independent Architecture Reviewer |
| Reviewed commit | `2a7484d9ed3408b19adb0e083d7e5844e4b645bf` |
| Verdict | CHANGES REQUESTED — 3×P1, 1×P2, required regression coverage |
| Migration | Stays in `migrations/proposed/`, unmoved, unapplied. No caller wired. Commerce not activated. |

All four findings addressed below, each with what changed and the test
proving it. Nothing in "Deliberately narrow scope" or "What Opus is not
deciding" changed — no quotas, pricing, provider credentials or activation
were added while fixing these.

### P1 — `unknown` no longer poisons its own reconciliation retry

Confirmed: `record_event()` wrote every non-`'apply'` receipt as terminal,
so a `'unknown'` outcome (unverifiable event, decided by
`subscription_event_decision()`) became indistinguishable from a resolved
one — the same `(provider, external_event_id)` could never become `'apply'`
once its receipt existed, exactly as reported.

**Fix:** `processing_state` is now two-tier — `'received'` (non-terminal;
written for `'unknown'`) and terminal `'applied'`/`'ignored'` (written for
`'apply'`/everything else). `already_processed` — the input
`subscription_event_decision()` treats as `'duplicate'` — is now `receipt
exists AND its state is terminal`, not `receipt exists`. Calling
`record_event()` again with the same event id *is* the reconciliation
operation: with a non-terminal receipt, it re-decides fresh; with a terminal
one, it correctly reports `'duplicate'` without re-evaluating anything.
Migration: `RECEIPT_PROCESSING_STATES` narrowed to
`('received', 'applied', 'ignored')` — the review's suggested vocabulary,
not an invented third state, and `'failed'` (never actually distinct from
`'ignored'` in the first submission) is gone.

**Test**, all six required steps, one function:
`test_unknown_event_reconciles_to_apply_then_further_retries_are_duplicate`
— unverifiable event → `'unknown'`, receipt `'received'`, subscription
stays at the neutral placeholder (`state='none'`, never a known-good fact) →
same event id redelivered with a real version → `'apply'`, receipt now
`'applied'` → same event id again → `'duplicate'`.

### P1 — Billing callbacks now serialize with incarnation deletion

Confirmed: `record_event()` read `account_incarnations.status` with a plain
`SELECT`, which does not wait on `incarnation_repository.mark_deleted()`'s
in-flight `UPDATE` under READ COMMITTED — the exact race described was real.

**Fix:** that read is now `SELECT ... FOR UPDATE`. Both transactions now
lock the same row, so one fully precedes the other rather than interleaving;
`mark_deleted()`'s own `UPDATE` participates in that lock automatically,
unchanged.

**Test:** `test_billing_callback_serializes_with_incarnation_deletion` races
`record_event()` against `mark_deleted()` on a real connection pool. Whichever
transaction's lock is granted first fully completes before the other's
decision-relevant read happens (verified as two mutually-exclusive, each
individually consistent outcomes — never a hybrid where a callback observes
`active`, deletion commits, and the callback still applies past it). The
proposal does not decide whether a payment that lands before deletion should
be honored or reversed after — that is a policy question
`ARCHITECTURE_INVARIANTS.md` §7 reserves as a human gate, not one this
schema proposal can answer; the test asserts both individually-consistent
orderings are possible and neither is the reported inconsistent one.

### P1 — Deleted-incarnation callbacks now get durable inbox handling

Confirmed: the first submission treated "grant nothing" as "write nothing,"
returning before any receipt existed — repeat delivery of the same event to
a deleted incarnation would have been re-evaluated as brand new every time.

**Fix:** the receipt placeholder-insert now runs before the deletion check,
so every event — deleted-incarnation ones included — gets a durable,
eventually-terminal receipt. `subscription_event_decision()` was also
reordered: `already_processed` is now checked *before*
`incarnation_deleted`, so once a receipt is terminal, a redelivery is always
`'duplicate'` — one consistent answer regardless of what happened to the
incarnation since, with the original reason preserved in
`sanitized_failure_reason` rather than recomputed differently each time.
`commerce_subscriptions` still gets no row at all for a deleted incarnation
— a receipt is idempotency/audit state, never a grant. No raw payload or PII
is retained; `external_object_reference`/`payload_digest` are opaque
identifiers/hashes, per the review's own caution.

**Test:**
`test_deleted_incarnation_gets_a_durable_receipt_but_no_subscription_row` —
first delivery: `'deleted_incarnation_rejected'`, no subscription row, a
retained receipt (`processing_state='ignored'`,
`sanitized_failure_reason='deleted_incarnation_rejected'`); second delivery
of the same event id: `'duplicate'`, still no subscription row.

### P2 — External subscription mapping now has a database invariant

**Fix:** `commerce_subscriptions` gains a partial unique index —
`UNIQUE (provider, external_subscription_id) WHERE external_subscription_id
IS NOT NULL` — so one provider subscription can never map to more than one
incarnation; NULL rows (no external subscription yet) never collide with
each other. This is the lookup index a future webhook resolver needs, not a
separate one deferred until duplicates could already exist.

`commerce_billing_event_receipts` gained the two fields the canonical
`BillingEventReceipt` contract (§2) names and the first submission omitted:
`external_object_reference` (the provider object — subscription/customer id
— the event concerns, distinct from the event's own id) and `payload_digest`
(a caller-computed hash of normalized, sanitized event content — never raw
payload). Both are stored for audit/correlation and as the seam a future
digest-mismatch check would use; this proposal does not add that check
itself, staying inside the findings actually raised rather than
volunteering new behavior.

**Test:**
`test_duplicate_external_subscription_mapping_is_rejected_by_the_database`
— two different incarnations, same `external_subscription_id`; the second
`record_event()` raises `IntegrityError` from the database itself, not from
application logic that could be bypassed.

### Required regression coverage — six added, six kept

All ten now pass together (`test_orena_commerce_persistence_postgres.py`,
10/10). The four review named plus the fixture bug they surfaced:

- `test_unknown_event_reconciles_to_apply_then_further_retries_are_duplicate` (P1 finding 1)
- `test_billing_callback_serializes_with_incarnation_deletion` (P1 finding 2)
- `test_deleted_incarnation_gets_a_durable_receipt_but_no_subscription_row` (P1 finding 3; replaces the narrower prior version of this test)
- `test_duplicate_external_subscription_mapping_is_rejected_by_the_database` (P2 finding 4)
- `test_same_event_id_under_concurrent_processing_is_exactly_once` (required regression coverage: same event, concurrent delivery, exactly one `'apply'` and one `'duplicate'`, never two `'apply'`s)
- Migration up/down/up: rehearsed again against a fresh scratch database with the revised migration; both new tables present after re-upgrade, gone after downgrade, chain otherwise unaffected

One test-fixture bug this revision's own rehearsal found, unrelated to any
finding: the shared `_UPDATE` constant used a fixed
`external_subscription_id` across tests that each create their own
incarnation — harmless before the new uniqueness invariant existed, a
collision after. Fixed by leaving it `None` in the shared fixture; the one
test that exercises the invariant sets its own explicit values.

**Rehearsed, this revision:** full chain applies clean; the ten-case suite
passed 5/5 repeated clean-database runs (50 executions, checking specifically
for flakiness in the new race tests) plus one further clean run (60/60
total); up/down/up repeatable. Full existing suite
(`test_app.py` + `tests`, `PERSISTENCE_BACKEND=sqlite`): 824 passed / 20
failed (unchanged documented inherited baseline) / 52 skipped. `ruff` clean
on every touched file. `python scripts/test_orena_backbone.py`: 27/27 (one
new case for the `already_processed`-before-`incarnation_deleted` reorder).

---

Raised by Opus, following the same path I2 took under
`ORENA_ACCOUNT_DATA_ARCHITECTURE` §6: Opus proposes additive Alembic changes
and adapters against `ORENA_COMMERCE_ARCHITECTURE.md`; Codex reviews
constraints, parent isolation, transactional receipts and indexes; explicit
schema/runtime authorization stays separate and belongs to the human.

**Nothing is applied.** The migration is in `migrations/proposed/`, which
Alembic does not read; the live head is still `20260908_0005` (or whatever
production/preview actually run — this proposal was never rehearsed against
either, only a disposable scratch database). Approving it is a `git mv` into
`migrations/versions/`, same mechanism `migrations/proposed/README.md`
documents and I2 already used.

## What is being proposed

| File | What it is |
| --- | --- |
| `migrations/proposed/20260911_0006_commerce_subscription_inbox.py` | Two new tables. Additive only; no existing table is altered. |
| `writing_coach/reference_backbone.py` | `ProviderEvent` + `subscription_event_decision()` — already committed (`8cbdcf5`, corrected `1a2b3c4`-equivalent for the "no prior state" case), 26 stdlib counterexamples. Not new in this request; named here because the migration exists to give it a caller. |
| `writing_coach/persistence/commerce_repository.py` | The transactional seam. No caller is wired to it. |
| `tests/test_orena_commerce_persistence_postgres.py` | Ten cases against real PostgreSQL (six from the original submission, four added responding to review), skipped unless `ORENA_TEST_POSTGRES_URL` is set. |

Tables: `commerce_subscriptions`, `commerce_billing_event_receipts`.

## Deliberately narrow scope

This covers only §3's subscription state and inbound-event reconciliation —
the two tables `subscription_event_decision()` needs a caller to read and
write. It does **not** propose:

- `PlanVersion` / `PriceReference` (§2) — plan identity stays the existing
  `writing_coach/product/catalog.py` static `PLANS` dict, per §1: "Existing
  catalog numbers are current configuration, not a new pricing decision."
- `QuotaBucket` / `Reservation` (§2, §4) — `reserve_decision()`'s admission
  logic has no persistence yet either; that is a separate, later proposal.
- Any provider adapter, live credential, or enforcement. `billing_ready`
  stays `False` everywhere upstream regardless of this proposal's outcome.

## Rehearsed, not just written

Against a disposable scratch database (`orena_i3_scratch` /
`orena_i3_rollback` inside the sandbox's own PostgreSQL, both dropped after —
the runtime database was never touched):

| Check | Result |
| --- | --- |
| Full chain from `20260811_0001` through `20260911_0006` | Applies clean, 29 tables total |
| `test_orena_commerce_persistence_postgres.py`, fresh database | 6/6 passed |
| Same file, 5 repeated fresh-database runs (flakiness check on the race case) | 5/5 passed each time |
| Downgrade `20260911_0006 -> 20260908_0005` | Both new tables dropped; rest of the chain untouched |
| Up / down / up | Repeatable |

**One defect found and fixed during this rehearsal, in the migration
fixture, not the schema:** Alembic's `path_separator=os` splits
`version_locations` on `os.pathsep` (`:` on Linux), not on whitespace —
joining the two directories with a plain space silently produced a
one-element, nonexistent path and `ScriptDirectory.get_heads()` returned
`[]` with no error. Exactly the class of defect
`I2_SCHEMA_REVIEW_REQUEST.md` already recorded once for the same option
under its old name (`version_path_separator`). Not a defect in the
migration or the repository.

**Two real logic defects found and fixed by writing this proof, both
described here rather than silently corrected:**

1. `subscription_event_decision()`'s `current_object_version=None` branch
   originally returned `'unknown'` unconditionally — collapsing "no
   subscription has ever existed for this incarnation" into the same
   outcome as "one exists but its version could not be read." The first
   case is the ordinary shape of a brand-new subscription and must be able
   to `'apply'`; only the second is the outcome §3 means by "a
   pending/unverifiable fetch." Fixed in `reference_backbone.py`, with the
   distinguishing test (`test_first_ever_verified_event_applies_with_
   nothing_to_be_stale_against`) replacing the incorrect prior assertion.
2. `record_event()`'s placeholder-row insert (needed so the very first
   event for an incarnation has a row to lock at all — "concurrent first
   use," the same problem I2's stream head solves) ran unconditionally,
   including on the `deleted_incarnation_rejected` path, which would have
   left a commerce row behind for a deleted incarnation despite "no
   new-account grant." Moved the deletion check before any write.

## The four things review is asked to check

### 1. Constraints

- `commerce_subscriptions.state` / `commerce_billing_event_receipts.
  processing_state`: `CHECK IN (...)` against the exact literal lists in the
  migration, not an import from application code (a migration must not
  depend on code that can change under it after being applied — same
  reasoning `20260908_0005` already established).
- `object_version >= 0` on both tables (nullable is still allowed — see
  below).
- `commerce_subscriptions`: `UNIQUE (incarnation_id)` — one current-state row
  per incarnation, matching §2's "Subscription: account incarnation..." 1:1.
- `commerce_billing_event_receipts`: `UNIQUE (provider, external_event_id)`
  — global, not scoped to incarnation, because a provider's event id is a
  global identifier.
- Both tables: `incarnation_id` is `ON DELETE RESTRICT` into
  `account_incarnations`, matching the deletion-barrier pattern
  `20260908_0005` established — a deleted incarnation's commerce history
  must keep denying reactivation, not disappear with it.

**Question for review:** `commerce_subscriptions.plan_id` is an
unconstrained string against `catalog.py`'s two current values (`free`,
`premium`), not a foreign key or enum — deliberately, since the catalog is
still explicitly "current configuration, not a pricing decision" per §1.
Should it be constrained anyway, or does that make an ordinary catalog
change (adding a third plan) require a migration it should not need?

### 2. Parent isolation

Both tables scope to `incarnation_id`, never `user_id` — a recreated
account inherits no subscription state and no receipt history, same
reasoning `20260908_0005` applied. Nothing here introduces a second
account-identity path.

### 3. Transactional receipts / idempotency

`record_event()`'s order: verify the incarnation is active (reject
outright, write nothing, if not) → placeholder-insert the subscription row
if absent (`ON CONFLICT (incarnation_id) DO NOTHING`, safe because the
unique constraint lets exactly one concurrent attempt win) → lock that row
`FOR UPDATE` → check the receipt table for this exact `(provider,
external_event_id)` → decide with `subscription_event_decision()` → write
the receipt (skipped only for `'duplicate'`, where one already exists) and,
on `'apply'` only, update the now-locked subscription row.

**Question for review, named rather than resolved:** `record_event()` takes
`incarnation_id` as a trusted input. A real provider webhook names an
external customer/subscription id, not an incarnation id — resolving which
incarnation a webhook belongs to is a lookup this proposal does not
perform, the same gap I1's incarnation resolution already has (no
production caller resolves one from a request yet). Until that lookup
exists, `subscription_event_decision()`'s `foreign_incarnation` branch is
reachable only when a caller passes a stale/cached incarnation, never from
a genuinely misrouted webhook. Is that gap acceptable to carry into this
proposal, or does identity resolution need to land first?

### 4. Indexes

- `ix_commerce_receipts_incarnation_received (incarnation_id, received_at)`
  — reading one account's billing history in order. Not yet needed for
  anything else in this proposal's scope; no other query pattern exists
  yet to index for.

### 5. Concurrency and migration safety

Rehearsed above. The acceptance-matrix rows this covers: duplicate/reversed
provider subscription events (`'duplicate'` / `'stale'`, proven under a real
thread race, 5/5 repeated clean runs); checkout/callback for a deleted
incarnation (`'deleted_incarnation_rejected'`, and confirmed no row is left
behind); delete-and-re-register rejecting the old incarnation's callback
(`'foreign_incarnation'`, proven at the pure-decision level only — see the
identity-resolution question above). Migration safety: additive only,
single linear head once moved, `downgrade()` drops both tables in dependency
order, rehearsed up/down/up.

## What Opus is not deciding

Which provider(s) to integrate, any price or plan value, retention for
`commerce_billing_event_receipts`, or whether/when
`ORENA_ACCOUNT_BACKBONE`-style activation applies to commerce. Absent policy
leaves enforcement disabled, as the architecture requires — `billing_ready`
stays `False`.

Also explicitly not decided here, and named as follow-on proposals rather
than silently deferred: `PlanVersion`/`PriceReference` persistence, and
`QuotaBucket`/`Reservation` persistence for `reserve_decision()`.

## A pre-existing table worth naming, not proposing to touch

`writing_coach/persistence/models.py` already has a `Subscription` ORM
table (backing `writing_coach/product/repository.py`'s
`SQLiteProductRepository` / `PostgresProductRepository`, the legacy
pre-Orena read path `/api/product/me` still serves for the frozen mobile
contract — see `06c482b` and `25df84d`). It coexists with
`commerce_subscriptions` in this proposal rather than being unified with
it: reconciling the two is a real question, but not one this narrow
proposal should decide by quietly renaming or dropping either. Flagging it
here so it is a decision, not a surprise found later.

---

## New: I3 quota buckets and reservations (first submission)

Raised by Opus, same path as the subscription-inbox proposal above and I2
before it: additive Alembic changes and a repository against
`ORENA_COMMERCE_ARCHITECTURE.md`; Codex reviews constraints, parent isolation,
transactional idempotency and indexes; explicit schema/runtime authorization
stays separate and belongs to the human. **Nothing is applied.** The migration
is in `migrations/proposed/`, which Alembic does not read.

### What is being proposed

| File | What it is |
| --- | --- |
| `migrations/proposed/20260912_0007_commerce_quota_buckets.py` | Two new tables. Additive only; no existing table is altered. |
| `writing_coach/reference_backbone.py` | Two new pure decisions: `settle_decision()` and `release_decision()`, alongside the existing `reserve_decision()` (already reviewed as part of the executable backbone contract). 7 new stdlib counterexamples in `scripts/test_orena_backbone.py` (34/34 total). |
| `writing_coach/persistence/quota_repository.py` | The transactional seam: `reserve()`, `settle()`, `release()`. No caller is wired to it. |
| `tests/test_orena_quota_persistence_postgres.py` | Fourteen cases against real PostgreSQL, skipped unless `ORENA_TEST_POSTGRES_URL` is set. |

Tables: `commerce_quota_buckets`, `commerce_quota_reservations`.

### Deliberately narrow scope

This covers only §2/§4's `QuotaBucket` and `Reservation` records — the two
tables `reserve_decision()`, `settle_decision()` and `release_decision()` need
a caller to read and write. It does **not** propose:

- `PlanVersion` / `PriceReference` (§2) — plan identity stays the existing
  `writing_coach/product/catalog.py` static `PLANS` dict, the same reasoning
  the subscription-inbox proposal already applied to
  `commerce_subscriptions.plan_id`; `meter` is likewise an unconstrained
  string against `catalog.py`'s entitlement keys (`writing.evaluate`,
  `dictionary.lookup`, ...), not a foreign key or enum.
- Any provider adapter, live credential, or enforcement caller. `billing_ready`
  stays `False` everywhere upstream regardless of this proposal's outcome.
- A resolver from a real request to `(incarnation_id, meter, window)` — the
  same "no production caller resolves identity from a raw request yet" gap
  the subscription-inbox proposal already named for incarnation resolution.

### Rehearsed, not just written

Against disposable scratch databases (`orena_i3quota_scratch` /
`orena_i3quota_rollback` inside the sandbox's own PostgreSQL, both dropped
after — the runtime database was never touched):

| Check | Result |
| --- | --- |
| Full chain from `20260811_0001` through `20260912_0007` | Applies clean |
| `test_orena_quota_persistence_postgres.py`, fresh database | 14/14 passed |
| The two concurrency cases, 5 repeated fresh-database runs each (flakiness check) | 5/5 passed each time (10/10) |
| Downgrade `20260912_0007 -> 20260911_0006` | Both new tables dropped; rest of the chain untouched |
| Up / down / up | Repeatable |
| Full existing suite (`test_app.py` + `tests`, `PERSISTENCE_BACKEND=sqlite`) | 824 passed / 20 failed (unchanged documented inherited baseline) / 66 skipped (52 + 14 new Postgres-only cases) |
| `ruff` | clean on every touched file |
| `python scripts/test_orena_backbone.py` | 34/34 (7 new cases for `settle_decision()`/`release_decision()`) |

No defect was found while writing this proof — unlike both prior proposals,
which each surfaced at least one real bug during rehearsal. Named here so
that absence itself is visible, not silently assumed.

### The four things review is asked to check

#### 1. Constraints

- `commerce_quota_buckets.unit_limit`: nullable, `None` = explicitly
  unlimited (never a guessed number), `CHECK (unit_limit IS NULL OR
  unit_limit >= 0)`.
- `commerce_quota_buckets`: `CHECK (window_end > window_start)`,
  `UNIQUE (incarnation_id, meter, window_id)` — one bucket per account per
  meter per window, matching §2's bucket identity exactly.
- `commerce_quota_reservations.state`: `CHECK IN ('reserved','settled',
  'released')` against the exact literal list in the migration, not an
  import from application code — same reasoning `20260908_0005` and
  `20260911_0006` already established.
- `commerce_quota_reservations`: `UNIQUE (operation_id)` — global, not scoped
  to a bucket, because an operation identifies one specific attempted unit of
  work regardless of which bucket it belongs to (same reasoning
  `commerce_billing_event_receipts.external_event_id` already uses for a
  provider's event id).
- Both tables: `incarnation_id`/`bucket_id` are `ON DELETE RESTRICT`, matching
  the deletion-barrier pattern both prior migrations established.

**Question for review:** a rejected `reserve()` attempt (`denied`,
`exhausted`, `unknown`) writes no reservation row at all — see "Deliberately
narrow scope" reasoning in the migration's own docstring: nothing was
admitted, so a later retry of the same `operation_id` must be free to
succeed once capacity exists, and there is no double-charge risk to guard
against. Is that the right call, or does a rejected attempt need its own
durable audit row for observability, the way a genuinely undecided
(`'unknown'`) billing event does?

#### 2. Parent isolation

Both tables scope to `incarnation_id` (`commerce_quota_reservations`
transitively, through `bucket_id`), never `user_id` — a recreated account
inherits no quota history, same reasoning both prior migrations applied.

#### 3. Transactional idempotency

`reserve()`'s order: lock the incarnation (deleted -> `entitlement='denied'`,
reusing `reserve_decision()`'s existing vocabulary rather than a second one)
-> placeholder-insert and lock the reservation row for this exact
`operation_id` (`ON CONFLICT (operation_id) DO NOTHING`) so a concurrent
retry of the same operation is exactly-once even the first time it is ever
seen -> if found, compare `requested_units` and return `'duplicate'` or
`'payload_conflict'` without touching any bucket -> otherwise
placeholder-insert and lock the bucket row (same "concurrent first use"
pattern) -> decide with `reserve_decision()` -> on `'admit'` only, write the
reservation and update the bucket in the same transaction.

`settle()`/`release()`: lock the reservation row by `operation_id`, decide
with `settle_decision()`/`release_decision()`, write nothing at all unless
the verdict is `'settle'`/`'release'`.

**Question for review, named rather than resolved:** like the subscription
proposal's `foreign_incarnation` gap, `reserve()` takes `incarnation_id` as a
trusted input — resolving which incarnation and which bucket window a real
request belongs to is a lookup this proposal does not perform. Is that
acceptable to carry forward, or does identity/window resolution need to land
before either I3 proposal is approved?

#### 4. Indexes

- `ix_commerce_reservations_bucket (bucket_id)` — reading one bucket's
  reservation history in order. No other query pattern exists yet in this
  proposal's scope to index for.

#### 5. Concurrency and migration safety

Rehearsed above. The acceptance-matrix row this covers: "Quota has one unit,
EN and ZH submit concurrently -> one reservation, one exhausted; same shared
bucket" (`ORENA_BACKBONE_INTEGRATION_GATES.md`), proven under a real thread
race, 5/5 repeated clean runs. Migration safety: additive only, single
linear head once moved, `downgrade()` drops both tables in dependency order,
rehearsed up/down/up.

### Chain position, named rather than hidden

This migration's `down_revision` is `20260911_0006` (still awaiting
re-review), not `20260908_0005` directly — a chain-linearity choice so the
"point `version_locations` at both `versions/` and `proposed/`" testing
technique keeps working with a single head, not a data dependency: neither
new table has any foreign key into `commerce_subscriptions` or
`commerce_billing_event_receipts`. If the subscription-inbox proposal is
revised again before this one is approved, rebasing this migration onto its
new revision id is a mechanical follow-up, not a redesign.

### What Opus is not deciding

Which meters actually enforce a limit versus stay diagnostic-only, any
specific `unit_limit` value, retention for settled/released reservations, or
whether/when `ORENA_ACCOUNT_BACKBONE`-style activation applies to quota.
Absent policy leaves enforcement disabled, as the architecture requires.

### A pre-existing table worth naming, not proposing to touch

`writing_coach/persistence/models.py` already has a `UsageEvent` ORM table
(`user_id`-scoped, backing the same legacy `/api/product/me` read path named
above for `Subscription`). It coexists with `commerce_quota_buckets` /
`commerce_quota_reservations` in this proposal rather than being unified
with it, for the same reason: reconciling the two is a real question, not
one this narrow proposal should decide by quietly renaming or dropping
either.

## Requested outcome

Approve each proposal independently, or name the constraint, isolation,
receipt, index, or scope changes wanted for either. On approval, the same
path I2 took: move the approved migration(s) into `migrations/versions/`,
rehearse against a copy of the real database, then return to the human for
schema/runtime authorization before anything is applied anywhere real.
