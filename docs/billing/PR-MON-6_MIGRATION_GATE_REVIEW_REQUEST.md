# PR-MON-6 migration gate: review request for the proposed 0034

**Status: PROPOSED.** Not promoted and not applied to any runtime. Credits, quota enforcement and funding stay off.
R-MON-014 has not been run. Promoting, applying and enabling are human gates.

## What is under review

| | |
| --- | --- |
| Design | `docs/billing/PR-MON-6_DESIGN.md` revision 2. APPROVED FOR IMPLEMENTATION / MIGRATION GATE on `418e937e` (2026-10-15). |
| Proposal | `migrations/proposed/20261015_0034_funding_admissions.py` |
| Tests | `tests/test_funding_admission_migration_postgres.py` (throwaway PostgreSQL 16) |
| Other changes | `tests/test_credit_ledger_postgres.py`: the shared fixture's blanket grant now leaves out the two new tables. `RUNBOOK_R-MON-014_RUNTIME_ROLE.md` §2 has the same change. |

The feature implementation (admission service, `FundingContext`, backstop, meters, cost report) does not start until
this gate closes.

## 1. Topology and the current Alembic head

- **Chain.** The `main` head is `20261015_0033`, and no branch claims a revision 0034. The proposal is
  `20261015_0034` with `down_revision = "20261015_0033"`, so the chain stays linear.
- **0024 and 0028.** The open proposals `20261001_0024` and `20261005_0028` are untouched. Whoever promotes one of
  them re-parents it on the head of that day.
- **One database for the §5.6 transaction.** The design needs `funding_admissions`, the quota tables and the credit
  tables in one database. The upgrade checks that all eight required tables are in the current schema and stops
  before any DDL if one is missing. The foreign keys
  (`commerce_quota_reservations`, `credit_ledger`, `account_incarnations`) then make this structural: neither a
  separate database nor the two-phase variant can be deployed by accident.
- **Roles.** 0032's `_prerequisites` runs again (the roles must be NOLOGIN, NOSUPERUSER and NOBYPASSRLS, and the
  executor mode is checked), all before any DDL.

## 2. Schema

**`funding_admissions`.** One row per admitted learner operation. It is the durable half of I-1.

- **Identity and intent** (never change): `operation_id` (unique, at most 190 characters, so that `fund:<op>` fits
  0007's 200 and the ledger's 250), `incarnation_id`, `meter`, `units > 0`, `operation_ref`, `feature`,
  `unit_granularity > 0`, `request_digest` (64 hex characters), `created_at`.
- **Snapshot** (written once, by `admitting → funded`): `source` (`allowance` / `promotional` / `credits`),
  `price_per_unit`, `amount_reserved`, `policy_version`, `cost_gate_id`, exactly one of `quota_reservation_id` and
  `credit_reserve_entry_id`, and `funded_at`.
- **Lifecycle:** `state`, `dispatched_at`, `settled_units`, `settled_amount`, `refusal_reason`, `closed_at`.
- **CHECKs** on the shape of state × snapshot:
  - `admitting` and `refused` carry no snapshot.
  - `funded` and later carry the snapshot. Credits need a price above 0, `amount_reserved = price × units` and a cost
    gate. The allowance has neither.
  - `refused` carries a reason. `closed_at` is set exactly when the state is terminal.
  - `settled` has `1 ≤ settled_units ≤ units`. For credits, `settled_amount = price × settled_units`.
- **Indexes:**
  - partial unique on each backing id, so one reservation backs one admission;
  - the open admissions, for the reconciler;
  - the incarnation.

**`promotional_grants`.** The claimed instance of a configured grant. H-8: no grant is configured.

- `grant_id`, `user_id`, `incarnation_id`, `policy_version`, `claimed_at`, `expires_at`.
- Unique `(grant_id, user_id)`.
- It is immutable and never deleted.

**The grant's usage is 0007's quota bucket, not a new table.**

- `commerce_quota_buckets.promotional_grant_id` (a nullable foreign key) marks a promotional bucket.
- A CHECK ties `window_id = 'promo:<grant>'` and a finite limit to that marker, and keeps `promo:` out of plan
  buckets.
- A guard makes the bucket's owner and window equal to the grant's, and freezes them.
- Reservations against the bucket are ordinary 0007 reservations.
- This follows the design's rule that the quota system is extended, not replaced. The design's
  `promotional_grant_usage` therefore has no table of its own (deviation 1).

**`ai_cost_records`.** New nullable columns `operation_id` and `meter`, set both or neither (CHECK), and a partial
index on them.
- There is no foreign key. The 13-month sweep and the deletion of the account's records keep working, and a
  system-funded call has no admission.

**`billing_reconciliation_items`.** A new kind `funding_admission_conflict` and its column `funding_admission_id`.
- It is critical: never dismissed, closed by the reconciler only.
- It closes only as `stray_released`.
- Its facts are frozen. The guard recomputes the outcome's fact: the admission is `refused`, and nothing keyed
  `fund:<op>` is still open in either store.

## 3. Database guards: immutability and forward-only states

`funding_admission_guard()` is a `SECURITY DEFINER` trigger owned by `orena_credit_owner`, with a fixed
`search_path`. It runs before INSERT, UPDATE and DELETE.

- **Insert:** the row must be `admitting`, on an active incarnation.
- **Update:**
  - identity and intent never change;
  - a row whose state is unchanged does not change at all;
  - only the transitions of §5.6 are allowed;
  - the snapshot never changes after `admitting`;
  - `dispatched_at` is written only by `funded → dispatched`.
- **Delete** is refused. TRUNCATE is refused through 0032's `credit_refuse_change`.

Each transition is checked against its backing reservation:

| Transition | Credits (hold) | Allowance / promotional (quota reservation) |
| --- | --- | --- |
| `→ funded` | The incarnation is taken FOR SHARE and must be active. The hold must be exact (`fund:<op>`, this incarnation's account, meter, `operation_ref`, `amount = amount_reserved`), unexpired and not closed. | The incarnation is taken FOR SHARE and must be active. The reservation must be exact (`fund:<op>`, `admitted_units = units`, `reserved`, the bucket's incarnation and meter), and `promotional` exactly when the bucket is a grant's. |
| `→ dispatched` | The hold is still unexpired and open. | The reservation is still `reserved` or `dispatched`. |
| `→ settled` | The hold's settle charged exactly `settled_amount`. | The reservation is settled with `actual_units = settled_units`. |
| `→ released` | The hold's release or expiry exists (or a settle that charged 0). | The reservation is released, or settled at 0. |
| `→ refused` | No open, exact hold keyed `fund:<op>` exists. | No open, exact reservation keyed `fund:<op>` exists. |

- A non-exact stray does not block a refusal. It becomes a `funding_admission_conflict` item.
- An exact backing must be adopted, never orphaned. This is the crash table of §5.6.
- A two-phase deployment is impossible here (§1), so the guard is the single-transaction contract enforced by the
  database.

## 4. Ownership and privileges

- **Owner.** `funding_admissions`, `promotional_grants` and the three new functions belong to `orena_credit_owner`.
  The runtime therefore cannot disable or drop the guards.
  - The owner gets `SELECT` on the two quota tables, which the guard reads.
  - It already has its incarnation row-lock grant from 0032.
- **Runtime** (`orena_credit_runtime`):
  - `funding_admissions`: SELECT; INSERT on the identity columns and `state`; UPDATE on the snapshot and lifecycle
    columns only; no DELETE and no TRUNCATE.
  - `promotional_grants`: SELECT and INSERT only.
- **R-MON-014 §2** leaves both tables out of the blanket grant, as it already does for the three credit tables.
- **Before R-MON-014.** The runtime connects as the executor (a superuser, or a member of `orena_credit_owner`), so it
  can write admissions and the allowance path does not wait for R-MON-014.
  - In that mode the privilege boundary is not in force, exactly as for the credit ledger today.
  - The triggers apply in every mode. Only a superuser could disable them.

## 5. Concurrency and lock order

- **Serialization.** `uq_funding_admission_operation` plus `INSERT … ON CONFLICT (operation_id) DO NOTHING` and
  `SELECT … FOR UPDATE`. Six concurrent racers for one operation id produce one admission, one hold and one snapshot
  (tested).
- **Lock order.** The admission row first. On `→ funded`, the guard then takes the incarnation FOR SHARE. The bucket
  or credit account comes last (the ledger trigger already uses incarnation → account).
  - Top-up, refund and deletion never touch admissions, so no cycle exists.
  - A funding attempt that races an uncommitted deletion waits on the incarnation lock, then fails with
    `deleted account is never admitted` (tested).
- **Foreign-key locks.** The new foreign keys take KEY SHARE on the reservation, the ledger entry and the incarnation.
  These locks are compatible with the quota settle, the append-only ledger and the incarnation's status update, none
  of which changes a key.

## 6. Upgrade, downgrade, rehearsal

- **Downgrade** refuses while any admission, grant, attributed cost record or conflict item exists (a promotional
  bucket cannot exist without a grant).
- **Exact restore.** Otherwise the downgrade restores 0033 exactly. The test compares, before 0034 and after its
  downgrade:
  - every function (source and SECURITY DEFINER), table and owner;
  - every constraint, column, trigger and index in the schema;
  - the grants on the five touched tables.
- **Up / down / up** runs in a fresh schema.

## 7. Evidence (local execution, throwaway PostgreSQL 16, not CI)

- `tests/test_funding_admission_migration_postgres.py`: **18 passed**. Mutants: §9.

## 8. Decisions for the reviewer or the human

1. **Deviation 1:** promotional usage is 0007's bucket and reservations, marked with `promotional_grant_id`, rather
   than a separate `promotional_grant_usage` table.
2. **Deviation 2:** the source is `promotional` plus the bucket's grant, not the string `promotional:<grant>`. The
   grant is reached through the backing bucket, and the guard checks the match.
3. **Grant identity (human gate, account deletion).**
   - The anti-reclaim key is `users.id`. That is the account row the incarnation barrier keeps through deletion and
     re-registration (`account_incarnations.user_id` is RESTRICT), so no hash and no new personal data is stored.
   - If `users` rows are ever purged, the claims would block the purge (RESTRICT). They would then need to become a
     keyed digest of the sign-in subject. That change belongs to whoever decides the purge.
4. **Two-phase topology.** It is excluded structurally, not by a runtime switch.

## 9. Mutation results

**36/36 caught** (local execution, throwaway PostgreSQL 16). Each mutant removes one database guard, CHECK, grant or ownership step from the proposal, and at least one 0034 test fails:

`forward_transition`, `snapshot_immutable`, `identity_immutable`, `same_state_frozen`, `hold_key`, `hold_open`, `hold_expiry`, `dispatch_open`, `quota_units`, `quota_meter`, `quota_promotional`, `funded_deleted`, `funded_lock`, `settle_charge`, `quota_settle_units`, `credit_release_close`, `quota_release`, `refused_credit`, `refused_quota`, `insert_admitting`, `insert_deleted`, `never_deleted`, `grant_unique`, `grant_owner`, `grant_immutable`, `bucket_window`, `bucket_frozen`, `bucket_check`, `attribution_check`, `stray_released_fact`, `conflict_scope`, `runtime_column_grants`, `owner_transfer`, `downgrade_guard`, `zero_settle_check`, `refused_reason_check`.

A first run left four survivors: `snapshot_immutable`, `hold_open`, `quota_units` and `quota_meter`. Each wrong-backing case had also carried a wrong key, so the key clause masked the others. The tests now give each case its own admission, with an exact key and one wrong attribute. They also cover a hold that is closed but unexpired, and a snapshot change made together with a transition. All 36 are caught on the re-run.
