# I3 schema proposal — architecture review request for Codex/GPT-6

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
| `tests/test_orena_commerce_persistence_postgres.py` | Six cases against real PostgreSQL, skipped unless `ORENA_TEST_POSTGRES_URL` is set. |

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

## Requested outcome

Approve, or name the constraint, isolation, receipt, index, or scope
changes wanted. On approval, the same path I2 took: move the migration into
`migrations/versions/`, rehearse against a copy of the real database, then
return to the human for schema/runtime authorization before anything is
applied anywhere real.
