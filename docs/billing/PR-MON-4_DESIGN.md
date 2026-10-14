# PR-MON-4 Prepaid Credit Ledger — design and migration plan

**State: DESIGN revision 4, APPROVED FOR IMPLEMENTATION** (focused re-review of `48e1bf2e`, 2026-10-14; record:
`docs/reviews/architecture/PR_MON_4_CREDIT_LEDGER_REVIEW_2026-10-14.md`). The contract is frozen.

- The human froze decisions C1-C7 on 2026-10-14, on `43a3dedf`.
- Revision 4 is a narrow revision for the review of `2b6da4a7`:
  - P1-4, the circular reference between reversal requests and ledger entries, in §2 and I13;
  - P1-5, global uniqueness of a money event, in §2 and §6;
  - P1-6, the reconciliation schema 0032 adds, in §9;
  - two privilege clarifications, in §2.1.
- Revision 3 closed the three blockers raised in the review of `e5ccc114`:
  - P1-1, the 0031 dependency, in §1;
  - P1-2, the privilege boundary, in §2.1;
  - P1-3, the reversal cap and idempotency, in §5 and §6.
- There is no code yet, and nothing is promoted or applied. Migration 0032 is created only after **APPROVE FOR
  IMPLEMENTATION**.

Two meanings of "expiry" are kept apart throughout this document (C6):

- **Purchased credit never expires in v1.** No ledger kind, column or job makes a top-up decay or lapse.
- **A reservation (hold) expires after its TTL** (C7). Closing it is the ledger kind `reserve_expire`, which releases
  the hold and nothing else.

Inspected on `main` `1a9e010d` on 2026-10-14. PR-MON-3 was merged as #178.

Implements D-MON-002 (prepaid credits: top up, consume, stop at zero; no auto-recharge, no negative balance, no
surprise charge; retries never double-debit; replays never double-credit; refunds and reversals stay auditable).

**Out of scope:**
- any conversion from credits to VND, meter prices and Free allowances (human gates);
- top-up through a gateway (PR-MON-5);
- admission and provider dispatch (PR-MON-6);
- UI;
- any change to PR-MON-3 semantics;
- issue #160.

## 1. Migration topology, verified on `main`

The applied chain in `migrations/versions/` is linear. Its single head is `20261005_0026`:

```text
… → 0023 → 0025 → 0029 → 0030 → 0026   (head)
```

Proposals, which Alembic does not read:

| Proposal | `down_revision` | Owner |
| --- | --- | --- |
| `20261001_0024_media_entries` | `20260930_0023` (stale, so it must be re-parented) | media |
| `20261005_0027_billing_orders` | `20261005_0026` | Billing |
| `20261005_0028_reading_derived_texts` | `20261005_0027` (by linearity only) | Reading |
| `20261014_0031_billing_reconciliation` | `20261005_0027` | Billing |

0028 and 0031 both name 0027. Promoting both as they stand would fork the chain. H1, as decided in PR-MON-3,
already resolves this: at promotion, read the real head and parent onto it, put one financial or content migration
into the chain at a time, and the lane that promotes later re-parents its own revision.

**Proposed new revision:** `migrations/proposed/20261014_0032_credit_ledger.py`.

- `down_revision = "20261014_0031"`, **required** (review P1-1). 0032 has a real schema dependency on 0031: it
  **extends the schema of `billing_reconciliation_items`**, the table 0031 creates. It adds credit-reference
  columns and replaces the kind and resolution CHECKs and the guard trigger (§9). 0032 therefore cannot run without
  0031.
- No foreign key points at 0027/0031 tables. A top-up names its source by an opaque reference. That only means 0032
  needs no 0027 row; it does not make 0032 independent of 0031's schema.
- **Ordering rule:** 0027 → 0031 → 0032.
  - 0032 is never promoted before 0031.
  - H1 never re-parents 0032 around or ahead of 0031.
  - If another lane's migration enters the real chain between promotion steps, the normal H1 procedure re-parents
    the Billing revisions onto the head of the day and keeps their relative order: 0031 directly under 0032, and
    0027 under 0031.
- Nothing is promoted, and 0027/0031 are not edited.

## 2. Data model

Credits are an **integer count of credit units** (`BIGINT`). What a unit is worth in money is a human decision, and
it is never coded.

### `credit_accounts`: one per account incarnation

| Column | Type | Rule |
| --- | --- | --- |
| `id` | UUID PK | |
| `incarnation_id` | UUID, UNIQUE, FK `account_incarnations` **RESTRICT** | A deletion never removes it. |
| `posted` | BIGINT, NOT NULL, default 0 | The posted balance. |
| `reserved` | BIGINT, NOT NULL, default 0 | Credits held by open reservations. |
| `entry_count` | BIGINT, NOT NULL, default 0 | The number of ledger entries applied. |
| `last_entry_id` | UUID NULL | |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

CHECK: `posted >= 0 AND reserved >= 0 AND reserved <= posted`. The available balance is `posted - reserved`, so it
is never negative.

### `credit_ledger`: append-only, one row per financial event

| Column | Type | Rule |
| --- | --- | --- |
| `id` | UUID PK | |
| `credit_account_id` | UUID, FK `credit_accounts` **RESTRICT** | |
| `seq` | BIGINT, NOT NULL | Per account, gapless, UNIQUE (`credit_account_id`, `seq`). |
| `kind` | VARCHAR(20) | One of `topup`, `reserve`, `settle`, `release`, `reserve_expire`, `refund`, `reversal`, `adjustment` (CHECK). |
| `posted_delta` | BIGINT | The change to `posted`. |
| `reserved_delta` | BIGINT | The change to `reserved`. |
| `amount` | BIGINT, > 0 | The magnitude the kind is about (see §4). |
| `ref_entry_id` | UUID NULL, FK `credit_ledger(id)` RESTRICT | The entry this one offsets (§5). |
| `idempotency_key` | VARCHAR(200), NOT NULL | §6 |
| `request_digest` | VARCHAR(64), NOT NULL | sha256 of the request's canonical parameters (§6). |
| `source_type`, `source_ref` | VARCHAR(40) / VARCHAR(200), NULL | For `topup`/`reversal`: the money event, e.g. (`billing_order`, `payos:100123`). |
| `meter`, `operation_ref` | VARCHAR(80) / VARCHAR(200), NULL | For `reserve`: what the hold is for (PR-MON-6 fills it). |
| `expires_at` | TIMESTAMPTZ NULL | For `reserve` only (CHECK: NOT NULL exactly when `kind = 'reserve'`). It is a hold's TTL and never appears on purchased credit (C6). |
| `uncharged` | BIGINT NULL, >= 0 | For `settle` only: actual usage beyond the hold, never charged (§4.3, C3). |
| `reversal_request_id` | UUID NULL, FK `credit_reversal_requests` RESTRICT | Exactly for `kind = 'reversal'` (CHECK); partial UNIQUE, so there is at most one entry per request (P1-4). |
| `actor` | VARCHAR(200), NOT NULL | `system`, `reconciler`, or an administrator's id. |
| `reason` | VARCHAR(400) NULL | Required for `adjustment`, `refund` and `reversal`. |
| `created_at` | TIMESTAMPTZ, NOT NULL | |

Per-kind sign rules are CHECK constraints (§4). There is no `UPDATE` and no `DELETE`.

### `credit_reversal_requests`: the durable receipt of every reversal request (P1-3)

A reversal can apply nothing (C5), and still its outcome must be final. So every reversal request gets one
immutable row, whatever it applied:

| Column | Type | Rule |
| --- | --- | --- |
| `id` | UUID PK | |
| `credit_account_id` | UUID, FK `credit_accounts` RESTRICT | |
| `topup_entry_id` | UUID, FK `credit_ledger(id)` RESTRICT | It must be a `topup` of the same account (trigger). |
| `idempotency_key` | VARCHAR(200) | `<source_type>:<source_ref>`; UNIQUE (`credit_account_id`, `idempotency_key`); see §6. |
| `request_digest` | VARCHAR(64) | Over the request's intent (§6). |
| `requested` | BIGINT > 0 | |
| `applied` | BIGINT >= 0 | `min(requested, available, remaining_reversible)` at decision time. |
| `shortfall` | BIGINT >= 0 | CHECK `applied + shortfall = requested`. |
| `source_type`, `source_ref` | VARCHAR(40) / VARCHAR(200), NOT NULL | The money-side event (a payOS refund, a Polar chargeback). **UNIQUE (`source_type`, `source_ref`), global** (P1-5): one external refund or chargeback event is attached to one reversal request in one account, and reverses credit at most once. |
| `actor`, `reason` | VARCHAR | Required. |
| `created_at` | TIMESTAMPTZ | |

There is no `UPDATE` and no `DELETE` (trigger, plus no privilege for the runtime).

**There is no back-reference from the request to the ledger** (P1-4). The link runs one way only, so the request
stays immutable and no constraint has to be deferred:

- `credit_ledger.reversal_request_id` is the reference. CHECK: `(kind = 'reversal') = (reversal_request_id IS NOT NULL)`.
- Partial UNIQUE (`reversal_request_id`) WHERE `reversal_request_id IS NOT NULL` means a request has at most one
  reversal entry.
- The trigger on a `reversal` entry checks that the request exists, belongs to the same account, names the same
  top-up (`ref_entry_id = request.topup_entry_id`), and has `applied = amount > 0`.
- A request with `applied = 0` has, by design, no entry.
- The reverse link ("which entry applied this request?") is derived by querying `credit_ledger` by
  `reversal_request_id`.
- **Insert order** within the reversal's single transaction: (1) the request row, then (2) the `reversal` entry
  that references it, only when `applied > 0`, then (3) the shortfall item when `shortfall > 0`. Every foreign key
  points at a row inserted earlier in the same transaction, so all constraints are immediate.

### Why snapshot + ledger, and how it is rebuilt

The balance is the **result of the ledger**. `credit_accounts.posted` and `reserved` are a cache of `SUM(posted_delta)`
and `SUM(reserved_delta)` over that account's entries. They are maintained **by the database, in the same
statement**:

- An `AFTER INSERT` trigger on `credit_ledger` adds both deltas to the account row, sets `entry_count` and
  `last_entry_id`, and checks `NEW.seq = old entry_count + 1`. The account CHECK then refuses a result below zero,
  so the inserting transaction aborts and nothing is recorded.
- The snapshot's write boundary is a **database privilege**, not trigger nesting (§2.1, review P1-2).
- **Rebuild and verify.** `credit_balance_drift()` is a read-only query that compares every snapshot with
  `SUM(...)` over its ledger. The test suite asserts zero drift after every concurrency test. The PR-MON-3
  reconciler tick runs the same check and opens a critical `credit_balance_drift` item if it ever finds drift
  (§9, §10). A rebuild is never an `UPDATE` of the snapshot: drift is an incident, not something fixed by hand.

Pure-ledger reads would cost `O(entries)` and still need the same per-account lock. The snapshot gives O(1) reads,
and a CHECK constraint can express "never negative".

### 2.1 Who may write the snapshot: database privileges (review P1-2)

**Roles**: two NOLOGIN roles. Roles are cluster-wide, so creating them is idempotent.

- **Who may create them** (as implemented after the implementation review, P1-1):
  - Only a **superuser** executor creates the roles, and only when they are absent.
  - A **non-superuser** executor requires the operator to provision both roles out of band, and must itself be a
    member of `orena_credit_owner` **WITH SET** so that it can transfer ownership. `orena_credit_owner` needs CREATE on
    the schema, which 0032 grants when the executor owns the schema.
  - CREATEROLE alone is not a supported mode.
- **Existing roles are validated:** both NOLOGIN, NOSUPERUSER and NOBYPASSRLS, and the runtime group is not a member
  of the owner.
- Anything else fails clearly **before any credit DDL**. The migration never silently skips the roles.

The two roles:

- `orena_credit_owner`, NOLOGIN, not a superuser. It owns `credit_accounts`, `credit_ledger`,
  `credit_reversal_requests` and the ledger functions.
- `orena_credit_runtime`, NOLOGIN. A group role that carries the runtime's credit privileges. The deployment's
  runtime login role is made a member of it.

**Grants to `orena_credit_runtime`** (nothing more):

| Table | Granted | Not granted |
| --- | --- | --- |
| `credit_accounts` | `SELECT`; `INSERT (id, incarnation_id, created_at, updated_at)` (column-level, so `posted`/`reserved`/`entry_count`/`last_entry_id` take their zero defaults); `UPDATE (updated_at)` only, which `SELECT … FOR UPDATE` needs for the row lock | `UPDATE` of `posted`, `reserved`, `entry_count`, `last_entry_id`; `DELETE`; `TRUNCATE` |
| `credit_ledger` | `SELECT`, `INSERT` | `UPDATE`, `DELETE`, `TRUNCATE` |
| `credit_reversal_requests` | `SELECT`, `INSERT` | `UPDATE`, `DELETE`, `TRUNCATE` |

**The only write path to the snapshot** is `credit_apply_entry()`, the `AFTER INSERT` trigger function on
`credit_ledger`:

- It is `SECURITY DEFINER` and owned by `orena_credit_owner`, so it runs with the owner's rights while the inserting
  runtime role has none.
- Its `search_path` is fixed by `SET search_path = <the migration's schema>, pg_catalog, pg_temp`, with `pg_temp`
  **last**. Every table it touches is also schema-qualified.
- **The schema on that path must be trusted.** 0032 runs `REVOKE CREATE ON SCHEMA <schema> FROM PUBLIC` and from
  `orena_credit_runtime`. The runtime login role must not own the schema or hold `CREATE` on it, which the readiness
  check verifies.
- If a deployment cannot revoke `CREATE` on the application schema, the credit tables and functions go in a
  dedicated schema `orena_credit`, owned by `orena_credit_owner` with `CREATE` granted to no one else. That schema is
  then the one on the function's path. This is the fallback, and the choice is recorded in the migration.
- So no object an untrusted role creates can be found ahead of the real one.
- `EXECUTE` is revoked from `PUBLIC`. Only the trigger calls it.
- **Lock order** (implementation review P1-3): the function takes the account incarnation `FOR SHARE` first, then the
  credit account `FOR UPDATE`, which is the repository's order. A direct insert therefore waits for a concurrent
  deletion and then sees it. For that row lock, `orena_credit_owner` holds `SELECT, UPDATE (created_at)` on
  `account_incarnations`, and no function of the owner updates an incarnation.

**Defense in depth**, which does not replace the privileges:

- A guard trigger on `credit_accounts` refuses an `UPDATE` of the protected columns unless
  `current_user = 'orena_credit_owner'`. That is true only inside the definer function, and the check holds even
  for a role that would otherwise have the privilege.
- `credit_ledger` and `credit_reversal_requests` keep their immutability triggers.

**Deployment prerequisite** (an operator/human gate, not a product decision):

- The boundary holds only if the runtime connects as a **non-superuser** that does not own the credit tables and
  is a member of `orena_credit_runtime`. Today the runtime URL uses the database's owner role.
- Readiness therefore gets a check `credit_runtime_privileges`. For `current_user`, it verifies every privilege
  whose accidental grant would defeat the boundary is **absent**:
  - not a superuser (`rolsuper`), no `BYPASSRLS`, and not a member of `orena_credit_owner`;
  - not the owner of `credit_accounts`, `credit_ledger`, `credit_reversal_requests` or their schema;
  - `credit_accounts`: no `UPDATE` on `posted`, `reserved`, `entry_count` or `last_entry_id`; no `DELETE`; no
    `TRUNCATE`;
  - `credit_ledger` and `credit_reversal_requests`: no `UPDATE`, no `DELETE`, no `TRUNCATE`;
  - `billing_reconciliation_items`: no `DELETE`, no `TRUNCATE`;
  - the schema on the definer function's `search_path`: no `CREATE`;
  - the definer function itself: `EXECUTE` not granted to `PUBLIC` or to the runtime;
  - **and positively** (implementation review P1-2): it is a member of `orena_credit_runtime`
    (`missing_runtime_membership` otherwise), and it holds the effective privileges a credit transaction uses
    (`missing_*` otherwise). So `ready` means both safe and able.

  The check uses `has_column_privilege`, `has_table_privilege`, `has_schema_privilege`, `has_function_privilege` and
  `pg_has_role`.
- When the check fails, every credit operation is refused, `credits_runtime_privileged` is reported, and nothing is
  written.
- The migration itself runs as the owner or a superuser, as it does today. The runtime-role separation is
  configured by the operator before credits are ever enabled.

## 3. Invariants (each with its DB backstop)

| # | Invariant | Backstop beyond repository logic |
| --- | --- | --- |
| I1 | `posted >= 0`, `reserved >= 0`, `reserved <= posted`: available is never negative | CHECK on `credit_accounts`; the ledger insert aborts |
| I2 | The snapshot equals the ledger sums | **Privileges**: the runtime role cannot `UPDATE` the snapshot columns, and only the `SECURITY DEFINER` ledger function (owner role) writes them (§2.1). Guard trigger as defense in depth. Drift check in tests and the reconciler |
| I3 | Ledger rows are never updated or deleted | No `UPDATE`/`DELETE`/`TRUNCATE` privilege for the runtime role; a trigger refuses `UPDATE`/`DELETE` on `credit_ledger`; RESTRICT foreign keys |
| I4 | Accounts are never deleted, and a deletion never cascades | Trigger refuses `DELETE` on `credit_accounts`; RESTRICT foreign key to `account_incarnations` |
| I5 | Each operation applies at most once | UNIQUE (`credit_account_id`, `kind`, `idempotency_key`); UNIQUE (`source_type`, `source_ref`) for `topup` |
| I6 | A reservation closes exactly once (settle, release or reserve_expire) | Partial UNIQUE (`ref_entry_id`) where `kind IN ('settle','release','reserve_expire')`; trigger: the referenced row is a `reserve` of the same account |
| I7 | A closing entry releases exactly the hold; a settle charges at most the hold and records the rest as uncharged (C3) | Trigger: `reserved_delta = -ref.amount`; for `settle`, `charged = -posted_delta`, `0 <= charged <= ref.amount`, `amount = charged + uncharged`, and `uncharged > 0` only when `charged = ref.amount` |
| I8 | Refunds of a debit total at most what that settle charged | Trigger: `SUM(refund.amount for ref) <= -ref.posted_delta`, with the referenced settle locked |
| I9 | Reversals of a top-up total at most that top-up, and a reversal never takes reserved credits (C5) | Trigger: `SUM(reversal.amount for ref) <= ref.amount`, with the account row locked (every reversal of the account is serialized); the reversal's `amount` equals its request's `applied`; the account CHECK `reserved <= posted` refuses touching holds |
| I13 | A reversal request is decided once and never re-evaluated, and a money event reverses credit at most once (P1-3, P1-5) | `credit_reversal_requests` UNIQUE (`source_type`, `source_ref`) **globally**, plus UNIQUE (`credit_account_id`, `idempotency_key`), immutable (trigger), CHECK `applied + shortfall = requested`, `applied >= 0`. On the ledger: `(kind = 'reversal') = (reversal_request_id IS NOT NULL)`, partial UNIQUE (`reversal_request_id`), and the trigger requires `amount = request.applied > 0`, the same account and the same top-up (P1-4) |
| I10 | An offset references only its own kind | Trigger: refund→settle, reversal→topup, settle/release/reserve_expire→reserve, all in the same account; `topup`, `reserve` and `adjustment` reference nothing |
| I12 | Purchased credit carries no expiry (C6) | CHECK: `expires_at IS NULL` unless `kind = 'reserve'`; no kind decays a top-up |
| I11 | Ledger order per account is total and gapless | UNIQUE (`credit_account_id`, `seq`), and the trigger checks `seq = entry_count + 1` |

## 4. Entry kinds and their effect

`amount` is always positive, and the deltas are fixed by the kind (CHECK):

| Kind | `posted_delta` | `reserved_delta` | References | Notes |
| --- | --- | --- | --- | --- |
| `topup` | `+amount` | 0 | none | `source_type`/`source_ref` required, globally unique. PR-MON-5 writes it from a verified payment. |
| `reserve` | 0 | `+amount` | none | Needs available ≥ amount. `expires_at` is set in the reserve's own transaction (C7). |
| `settle` | `-charged`, with `charged = min(actual, hold)` | `-hold` | its `reserve` | `amount` = actual usage; `uncharged = actual - charged` (C3). |
| `release` | 0 | `-hold` | its `reserve` | The caller did not use the hold (provider failed or not dispatched). |
| `reserve_expire` | 0 | `-hold` | its `reserve` | Written by the reconciler for a hold past its `expires_at` (§7). It closes a reservation and has nothing to do with purchased credit (C6). |
| `refund` | `+amount` | 0 | a `settle` | Credits returned for a charge, for example a provider failure found after settle. `reason` is required. |
| `reversal` | `-applied` | 0 | a `topup` (and its request) | The top-up's money went back (payment refunded or charged back). Written only when `applied > 0`. The request row records `requested`, `applied` and `shortfall` (§5, C5, P1-3). |
| `adjustment` | `±amount` (sign in `posted_delta`) | 0 | none | Administrator only: a **delta** with mandatory reason, actor, idempotency key and digest. There is no "set balance" operation (C4). |

### 4.1 Reserve atomicity under concurrency

Every mutation is one transaction:

1. `SELECT … FROM account_incarnations WHERE id = :inc FOR SHARE`. This serializes against deletion and is the same
   lock order PR-MON-3 uses: the incarnation, then the money row.
2. `SELECT … FROM credit_accounts WHERE incarnation_id = :inc FOR UPDATE`. This lock serializes every credit
   mutation of the account.
3. The idempotency lookup (§6). An existing entry with the same key and digest is returned as it is. The same key
   with a different digest is a conflict.
4. The decision: is available ≥ amount, is the hold still open, and so on.
5. `INSERT` into the ledger. The trigger applies the deltas. If the CHECK fails, the transaction aborts.
6. `COMMIT`.

Two concurrent reserves for the same account queue on step 2. The second sees the first's hold in `reserved` and is
refused `insufficient_credits` if the two together exceed `posted`. If the repository's check were ever wrong, the
CHECK in step 5 still aborts the insert. Neither the database nor the repository can produce a negative balance.

No transaction is held across any provider call. PR-MON-6's dispatch happens **between** a committed reserve and a
later settle or release, in separate transactions.

### 4.2 Reserve state machine

```text
            reserve (hold = amount, expires_at)
                 │
     ┌───────────┼─────────────────┐
     ▼           ▼                 ▼
  settle      release        reserve_expire  (reconciler, past expires_at)
 (charge ≤ hold)  (charge 0)      (charge 0)
```

There is exactly one closing entry per reserve (I6). A reserve is open while no closing entry references it; that
state is derived, never stored. A closing entry on an already-closed reserve is refused. When it is the same request
replayed (same key and digest) it is a duplicate and returns the original.

**Races between settle, release and reserve_expire (C7)** are serialized by the account row lock. The close-once
index is the backstop. Whichever commits first is the reservation's outcome:

- if `settle` commits first, it is valid, and a later `reserve_expire` finds the hold closed and writes nothing;
- if `release` or `reserve_expire` commits first, a later settle is refused (`reservation_closed`), nothing is
  charged, and `credit_late_settle` is recorded (§4.4);
- a reconciler retry of `reserve_expire` is a duplicate. Its key is the reserve entry's id, so it never writes a
  second expiration.

### 4.3 Settle with actual usage greater than the hold

**Decided (C3): the reserve is a hard upper bound.** Orena charges `charged = min(actual, hold)`. The excess is
recorded as `uncharged = actual - charged` on the settle entry. It is never taken from the available balance, never
turned into an implicit debit and never collected later. The trigger enforces this (I7), not only the repository.

PR-MON-6 sizes holds so that this is rare, and `uncharged` makes it measurable.

### 4.4 Late settle after expiry

If the reconciler has closed a hold with `reserve_expire` (or the caller released it) and the provider's result
arrives later, the settle is refused `reservation_closed`.
The usage is recorded as a reconciliation item `credit_late_settle` (dismissable: no money is owed by the learner;
Orena absorbed the cost). It is never charged after the fact.

**Decided (C7):** `expires_at` is written on the reserve entry in the reserve's own transaction, as
`transaction time + TTL`. The default TTL is **30 minutes** (`CREDIT_HOLD_TTL`), and a caller may ask for less.

- The time when a worker or the reconciler first sees the hold has no effect.
- The stored `expires_at` is authoritative. A later change of the default never alters an existing reservation.
- The reserve transaction is short, so its time is the commit time to within milliseconds.

## 5. Refund and reversal semantics

- **`refund`** names one `settle` (`ref_entry_id`) and returns up to what that settle charged, in one or more partial
  refunds (I8). It is the credit-side correction of a consume. It never names a top-up.
- **`reversal`** names one `topup` and removes up to its amount (I9). It is the credit-side consequence of money that
  went back: a payOS refund or a Polar chargeback (PR-MON-5 decides when to write it).
  - **Decided (C5): reverse only what can be reversed now, and record the shortfall.** It is computed under the
    account lock, in one transaction (P1-3):

    ```text
    available            = posted - reserved                       (never touches active reservations)
    remaining_reversible = topup.amount - SUM(earlier reversals of that topup)
    applied              = min(requested, available, remaining_reversible)
    shortfall            = requested - applied
    ```

  - In that same transaction:
    1. **Always** insert the `credit_reversal_requests` row (`requested`, `applied`, `shortfall`, digest, source).
       It is the durable, final outcome of the request.
    2. If `applied > 0`, insert the `reversal` ledger entry for `applied`. It references the top-up
       (`ref_entry_id`) and the request (`reversal_request_id`). This is the only link between the two (P1-4).
    3. If `shortfall > 0`, record the `credit_reversal_shortfall` item with its structured credit references (§9):
       the account, the top-up, the request, the reversal entry if one was written, `requested`/`applied`/
       `shortfall`, and the money-side source. Its dedupe key is the request's id.
  - **One money event, one reversal (P1-5).** A second request naming the same (`source_type`, `source_ref`):
    - with the same intent (same account, top-up and `requested`) returns the original receipt;
    - with any other account, top-up or amount is a conflict, and nothing is written. The global UNIQUE is the
      backstop even if the repository's lookup missed it.
  - `applied = 0` writes no zero-value ledger entry, and nothing is ever faked as a full reversal. The request row is
    still the receipt.
  - **Never re-evaluated.** A retry of the same request returns the stored request row, with its original `applied`
    and `shortfall`, even if the account has since gained credit. A new reversal of newly available credit needs a
    new money-side event, with a new key.
  - The cap holds under concurrency. Every reversal of the account is serialized by the account row lock, and the
    trigger checks `SUM(reversals of the top-up) <= topup.amount` (I9). Two concurrent requests can never together
    exceed `remaining_reversible`.
  - The shortfall is a money kind and cannot be dismissed (§9). The balance is never driven negative to "claw back"
    spent credits.
- An offset always lives in the same account as the entry it names (I10). There is no cross-account transfer.
- **Decided (C4):** `adjustment` is the only entry without a source, and it exists only as a ledger delta.
  - It is administrator-only. A reason, the actor, an idempotency key and a request digest are mandatory, and a
    reused key with other content is a conflict.
  - A negative adjustment is limited by available (I1).
  - There is no "force balance" and no "set balance = X". The snapshot is never written outside the ledger trigger.

## 6. Idempotency keys

| Operation | Key | Scope | Replay |
| --- | --- | --- | --- |
| `topup` | `source_type` + `source_ref`, e.g. `billing_order:payos:100123` | **global**: one money event can never credit two accounts | The same source returns the original entry; a different account or amount is a conflict |
| `reserve` | the caller's `operation_id` (PR-MON-6: one per admitted operation) | per account and kind | The same key and digest returns the hold; a different amount or meter is a conflict |
| `settle` / `release` / `reserve_expire` | the reserve entry's id (via the I6 index), plus the caller's key | per reservation | Closing twice returns the first close if the digest matches, otherwise `reservation_closed` |
| `refund` / `adjustment` | the caller's operation id (an operator action or a PR-MON-5 refund event id) | per account and kind | The same key and digest returns the original; a different digest is a conflict |
| `reversal` | derived from the money-side event: `<source_type>:<source_ref>` (one reversal request per refund or chargeback event) | **global** for the money event: UNIQUE (`source_type`, `source_ref`) (P1-5); also per account (`credit_account_id`, `idempotency_key`) | The same event with the same digest returns the stored request row, with its original `applied`/`shortfall` and no re-evaluation. The same event with any other account, top-up or `requested` is a conflict |

**`request_digest` is the sha256 of the request's intent**: the caller's semantic inputs in a canonical order. It
never includes a derived result. Values the server derives (`charged`, `uncharged`, `applied`, `shortfall`,
`expires_at`, `seq`, timestamps) are never digest inputs.

| Operation | Digest inputs (semantic) | Declared non-semantic (stored, not compared) |
| --- | --- | --- |
| `topup` | kind, account, `amount`, `source_type`, `source_ref` | actor |
| `reserve` | kind, account, `amount`, `meter`, `operation_ref`, the requested TTL (seconds, or the default marker) | actor; the derived `expires_at` |
| `settle` | kind, reserve entry id, actual `amount` | actor; the derived `charged`/`uncharged` |
| `release` | kind, reserve entry id | actor, reason |
| `reserve_expire` | kind, reserve entry id | actor (always `reconciler`) |
| `refund` | kind, account, settle entry id, `amount` | actor, reason |
| `reversal` | kind, account, top-up entry id, `requested`, `source_type`, `source_ref` | actor, reason; the derived `applied`/`shortfall` |
| `adjustment` | kind, account, signed `amount` (the delta) | actor, reason |

A retried request is therefore recognized as the same. A reused key with other intent is a conflict and writes
nothing. A free-text reason or the caller's identity never turns a genuine replay into a conflict: the first
request's values are the ones kept.

## 7. Orphaned holds

- The reserve's `expires_at` is set at reserve time (§4.4).
- The PR-MON-3 reconciler, under its session advisory lock, gets one more step: close the holds past their
  `expires_at`, in pages, one short transaction per hold. It writes a `reserve_expire` entry with actor `reconciler`.
  This step only closes reservations. Purchased credit has no expiry (C6).
- A deleted account's open holds are expired at once by the same step, whatever their `expires_at`.
- No provider is called, and no transaction is held across anything external.

## 8. Account deletion

- `credit_accounts` and `credit_ledger` use RESTRICT foreign keys and refuse `DELETE` (I3, I4). History and
  obligations survive deletion.
- After deletion (incarnation `status = 'deleted'`, checked under its `FOR SHARE` lock):
  - refused: `topup`, `reserve` and `settle`, and any new spend;
  - allowed: `release` and `reserve_expire` of open holds, which only free credits;
  - allowed: `refund`, `reversal` and a controlled `adjustment`, which are the operations needed to finish a
    financial obligation that still exists.
- **Decided (C1): the remaining purchased credit is a financial liability.** It is not forfeited and not refunded
  automatically.
  - It stays recorded and untouched, and stays visible in the reconciliation and accounting state through an open
    `credit_balance_on_deletion` item (a money kind), until a valid operation resolves it.
  - PR-MON-4 has no auto-refund. The deletion runtime is an architecture hold (`AGENTS.md` §7); PR-MON-4 provides
    the item and the ledger rules only.
  - Deleting an account never deletes or rewrites financial history.
- **Decided (C2): no automatic transfer.** Every incarnation has its own credit account.
  - A new incarnation never takes the old one's balance, is never matched by email or identity, never reuses the
    old account, and never "resurrects" credits on re-registration.
  - Any future verified recovery or refund flow would be a separate, explicit, auditable operation. It is out of
    scope here.

## 9. Reconciliation items added (PR-MON-3 table, new kinds)

0032 **extends the schema** of `billing_reconciliation_items`, the table 0031 creates. 0031 itself is not edited.
The extension is more than the kind CHECK: it adds four kinds, structured credit-reference columns, per-kind CHECKs,
and a replacement of 0031's guard trigger. Credit items use `gateway = 'credits'`. That is not a payment gateway, so
the PR-MON-3 checkout block (`critical_by_gateway` for `payos`/`polar`) is unaffected.

Their rules follow PR-MON-3's classes:

| Kind | Class | Closed by |
| --- | --- | --- |
| `credit_balance_drift` | **critical** (closes credit operations on that account, not checkouts) | the reconciler only, once the drift check is clean |
| `credit_reversal_shortfall` | money: one per reversal request (dedupe key = the request's id), and it links the top-up, the request (`requested`/`applied`/`shortfall`), the reversal entry if any, and the money-side source | `refund_confirmed` or `obligation_waived` with an audited reason; never dismissed |
| `credit_balance_on_deletion` | money | `refund_confirmed` or `obligation_waived` (the C1 decision); never dismissed |
| `credit_late_settle` | review (dismissable) | `recorded`, or dismissed with a note |

### 9.1 Columns added to `billing_reconciliation_items` (all nullable, because the table serves every kind)

| Column | Type | Used by |
| --- | --- | --- |
| `credit_account_id` | UUID, FK `credit_accounts` RESTRICT | every credit kind (the incarnation is the existing `incarnation_id`) |
| `credit_topup_entry_id` | UUID, FK `credit_ledger(id)` RESTRICT | `credit_reversal_shortfall` |
| `credit_reversal_request_id` | UUID, FK `credit_reversal_requests` RESTRICT | `credit_reversal_shortfall` |
| `credit_reversal_entry_id` | UUID, FK `credit_ledger(id)` RESTRICT | `credit_reversal_shortfall`, when a partial reversal was written |
| `credit_reserve_entry_id` | UUID, FK `credit_ledger(id)` RESTRICT | `credit_late_settle` (the closed reserve) |
| `credit_closing_entry_id` | UUID, FK `credit_ledger(id)` RESTRICT | `credit_late_settle` (the release or `reserve_expire` that closed it) |
| `credit_requested`, `credit_applied`, `credit_shortfall` | BIGINT | `credit_reversal_shortfall` |
| `credit_actual` | BIGINT | `credit_late_settle` (the usage that arrived late, never charged) |
| `credit_expected_posted`, `credit_expected_reserved`, `credit_snapshot_posted`, `credit_snapshot_reserved` | BIGINT | `credit_balance_drift` (the ledger sums against the snapshot) |
| `credit_balance_posted`, `credit_balance_reserved` | BIGINT | `credit_balance_on_deletion` (the liability at deletion) |

The existing `reported_*`, `external_event_id` and `provider_state` keep their PR-MON-3 meaning. The money-side
source of a shortfall is in `external_event_id` (`<source_type>:<source_ref>`).

### 9.2 Per-kind CHECKs added by 0032

- `credit_reversal_shortfall`:
  - `credit_account_id`, `credit_topup_entry_id`, `credit_reversal_request_id`, `credit_requested`,
    `credit_applied` and `credit_shortfall` are NOT NULL;
  - `credit_applied + credit_shortfall = credit_requested`, `credit_shortfall > 0`;
  - `(credit_applied > 0) = (credit_reversal_entry_id IS NOT NULL)`.
- `credit_late_settle`: `credit_account_id`, `credit_reserve_entry_id`, `credit_closing_entry_id` and
  `credit_actual >= 0` are NOT NULL.
- `credit_balance_drift`: `credit_account_id` and the four expected/snapshot values are NOT NULL; the pair differs
  (`expected_* IS DISTINCT FROM snapshot_*` for at least one).
- `credit_balance_on_deletion`: `credit_account_id`, `incarnation_id` and both balance values are NOT NULL, and
  `credit_balance_posted > 0`.
- A non-credit kind has every `credit_*` column NULL. A credit kind has `gateway = 'credits'`.
- The kind CHECK, the dismissable list (`credit_late_settle` joins it), the outcome-required list (the three money
  and critical credit kinds join it) and the reconciler-only rule (`credit_balance_drift` joins
  `entitlement_unsynced`) are **replaced** with the extended lists. The PR-MON-3 kinds keep their exact rules.

### 9.3 The guard trigger is replaced, not weakened

0032 replaces `billing_reconciliation_items_guard()` (0031) with a version that:

- adds **every new `credit_*` column to the immutable facts**: after insert, none can change;
- keeps every 0031 rule as it is: no `DELETE`; provider facts and matched links never rewritten; a terminal row
  changes only its counters; only a critical kind reopens; `payment_recorded` only for a paid order;
- makes `credit_balance_drift` a critical kind that may reopen.

`downgrade()` restores 0031's function and CHECKs exactly, and refuses while any credit-kind item exists (§14).

## 10. Failure modes

| # | Failure | Result |
| --- | --- | --- |
| C-F1 | Two reserves race on one account | Serialized by the account row lock. The second is refused when it would exceed `posted`; the CHECK is the backstop. |
| C-F2 | A retried reserve, settle, topup or refund | The same key and digest returns the original entry, with no second effect. |
| C-F3 | A reused key with different content | Conflict. Nothing is written. |
| C-F4 | A crash after the reserve commits, before dispatch | The hold stays open until `expires_at`, then is closed with `reserve_expire`. No charge. |
| C-F5 | A crash after dispatch, before settle | The caller retries the settle with the same key. If it never settles, the hold expires uncharged: Orena absorbs the cost (`credit_late_settle` if a result arrives late). |
| C-F6 | A settle with actual > hold | Charged up to the hold, with the rest in `uncharged`, enforced by the trigger (§4.3, C3). |
| C-F15 | A settle racing `release` or `reserve_expire` | The account lock serializes them and the close-once index decides: the first to commit wins, and a late settle is refused and recorded (`credit_late_settle`). |
| C-F7 | A double close (settle, then release) | Refused by the I6 unique index; a replay of the same close is a duplicate. |
| C-F8 | A refund larger than the debit, or two refunds racing | Trigger I8 under the referenced row's lock; the second over-refund aborts. |
| C-F9 | A reversal of partly or fully spent credits | Only the available part is reversed (never reserved credits, never negative); the shortfall becomes a `credit_reversal_shortfall` item in the same transaction (C5). |
| C-F10 | The same payment credits twice, or credits two accounts | Global UNIQUE on (`source_type`, `source_ref`). |
| C-F11 | A hand-written `UPDATE` of a balance, or a `DELETE` of history | Refused by privileges for the runtime role (§2.1), and by the guard triggers for any role. |
| C-F16 | A reversal of a partly reversed top-up, or two concurrent reversals | `applied = min(requested, available, remaining_reversible)` under the account lock; the trigger cap (I9) is the backstop. |
| C-F17 | A retried zero-applied reversal after new credit arrived | Returns the stored request (`applied = 0`). It is never re-evaluated, so new credit is never reversed by a replay. |
| C-F18 | The runtime connects as a superuser or table owner | `credit_runtime_privileges` fails, every credit operation is refused, and readiness names it. |
| C-F12 | The snapshot drifts from the ledger (should be impossible) | Drift check, then a critical item; credit operations on the account stop. |
| C-F13 | The account is deleted while holds are open | Holds are closed by the reconciler with `reserve_expire`; new spend refused; history kept; the balance stays a liability with a `credit_balance_on_deletion` item (C1). |
| C-F14 | The database errors mid-operation | Single transaction: all or nothing. The caller retries with the same key. |

## 11. Implementation slices (after design APPROVE)

1. 0032 proposed migration: tables, CHECKs, ledger trigger, guard triggers, offset/limit trigger, downgrade guard,
   item kinds.
2. `persistence/credit_repository.py`: `ensure_account`, `topup`, `reserve`, `settle`, `release`, `refund`,
   `reversal`, `adjust`, `balance`, `entries`, `open_holds`, `drift`. Each operation is one transaction with the
   §4.1 lock order.
3. `billing/credits.py`: a service façade with typed results (`applied`, `duplicate`, `conflict`,
   `insufficient_credits`, `reservation_closed`, `account_deleted`). No provider calls. No prices.
4. A reconciler step that closes expired holds (`reserve_expire`) and checks drift (on PR-MON-3's lock, with short
   transactions).
5. Admin API: read-only (balance and ledger page), plus the adjustment route (C4: a delta with reason and an
   idempotency key). There is no learner route: PR-MON-5 adds top-up and PR-MON-6 adds consumption.

Everything stays in Billing files. `app.py` changes only in start-up wiring.

## 12. Test and mutation plan (throwaway PostgreSQL 16 only)

- **Migration:**
  - upgrade, downgrade while empty, upgrade again;
  - downgrade refused once a row exists;
  - every CHECK and trigger probed: negative balance, direct snapshot `UPDATE`, ledger `UPDATE`/`DELETE`, account
    `DELETE`, wrong-kind reference, cross-account reference, over-refund, over-reversal, a second close, a seq gap;
  - 0032 applies on 0027 + 0031;
  - topology documented.
- **Privileges (P1-2)**, on a throwaway database with a dedicated non-superuser login role that is a member of
  `orena_credit_runtime`:
  - a direct `UPDATE credit_accounts SET posted = …` (and `reserved`, `entry_count`, `last_entry_id`) is refused
    with a permission error;
  - `UPDATE`/`DELETE`/`TRUNCATE` on `credit_ledger` and `credit_reversal_requests` are refused;
  - an `INSERT` into `credit_ledger` by that role does update the snapshot (through the definer function);
  - an `INSERT` into `credit_accounts` with a non-zero `posted` is refused (column privilege);
  - the guard trigger refuses a protected-column `UPDATE` from the owner's session outside the function;
  - the function's `search_path` is fixed, so a shadowing object in another schema is not used;
  - `credit_runtime_privileges` fails for a superuser, for a role holding any one of the listed privileges (each
    granted in turn), and for a role with `CREATE` on the function's schema;
  - with `CREATE` revoked, an object created by an untrusted role in another schema is not resolved by the
    function;
  - 0032 fails clearly when run by a role without `CREATEROLE` and the roles are not provisioned, and succeeds
    when they are provisioned out of band.
- **Reversal (P1-3):**
  1. top-up 100, an earlier reversal of 80, available ≥ 30, a new request for 30: a reversal of 20 and a shortfall
     of 10;
  2. a reversal with available 0: no ledger reversal, a request row with `applied = 0`, and a durable shortfall
     item;
  3. case 2 retried after a later top-up made credit available: an exact duplicate (the stored request), with no new
     reversal;
  4. the same reversal key with a changed `requested`: a conflict, and nothing written;
  5. concurrent reversals of one top-up never exceed its remaining reversible amount;
  - and the derived `applied` is not a digest input: the same request replayed after the balance changed is still a
    duplicate;
  - P1-5: the same (`source_type`, `source_ref`) used for a second account, top-up or amount is a conflict;
    replaying it with the same intent returns the original; a direct insert of a second request for that event is
    refused by the global UNIQUE;
  - P1-4: a `reversal` entry without a request, with a request of another account or top-up, or with
    `amount ≠ applied` is refused; a second reversal entry for one request is refused by the partial UNIQUE; a
    request with `applied = 0` has no entry.
- **Reconciliation schema (P1-6):** each credit kind refused without its required references, or with mismatched
  amounts; a non-credit kind refused with a `credit_*` value; every `credit_*` column immutable after insert (the
  replaced guard trigger); and every PR-MON-3 rule still enforced after 0032 (the 0031 tests re-run on 0031 + 0032).
- **Concurrency:**
  - N threads reserve against one account with a total above the balance: exactly ⌊balance/amount⌋ succeed, the
    rest get `insufficient_credits`, and drift is 0;
  - concurrent refunds of one settle never exceed it;
  - concurrent closes of one hold give exactly one close;
  - a reserve racing a deletion is refused, or expired at once.
- **Idempotency:** every operation replayed (duplicate, one entry) and replayed with altered content (conflict,
  nothing written); a top-up source used on a second account is refused.
- **Semantics:**
  - settle under, at and above the hold (`uncharged`), and a direct insert charging beyond the hold refused by the
    trigger (C3);
  - release and reserve_expire;
  - late settle is refused and creates a `credit_late_settle` item;
  - a partial reversal (some credits spent, some reserved) reverses only the available part, with the shortfall item
    referencing the top-up and the reversal; a reversal with nothing available writes no entry and records the whole
    shortfall (C5);
  - a settle / release / reserve_expire race: exactly one closes, a late settle is refused and recorded, and a
    reconciler retry writes no second `reserve_expire` (C7);
  - `expires_at` comes from the reserve's transaction, and a later default change leaves existing holds alone (C7);
  - no `expires_at` on any non-reserve entry (C6);
  - an adjustment without reason or key is refused, a replay is a duplicate, and a negative adjustment beyond
    available is refused (C4);
  - deletion rules (§8);
  - the drift check is clean after every test.
- **Mutations**, each of which must fail at least one guard's test:
  - the account CHECK;
  - the ledger insert trigger;
  - the snapshot guard;
  - the ledger immutability trigger;
  - the account no-delete trigger;
  - the close-once index;
  - the offset-kind check;
  - the refund cap;
  - the reversal cap;
  - the repository's available check (the DB must still abort);
  - the idempotency digest comparison;
  - the global top-up uniqueness;
  - the deleted-account refusal;
  - the `reserve_expire` step;
  - the C3 settle cap in the trigger;
  - the C5 partial reversal and shortfall item;
  - the C6 `expires_at`-only-on-reserve CHECK;
  - the downgrade guard;
  - the snapshot column privileges (granting `UPDATE (posted)` to the runtime role must fail a test);
  - the definer function's fixed `search_path`;
  - `remaining_reversible` in the reversal computation;
  - the reversal request's no-re-evaluation replay;
  - `applied` used as a digest input (must fail the replay-after-new-credit test);
  - the `credit_runtime_privileges` readiness check (each listed privilege);
  - the global (`source_type`, `source_ref`) UNIQUE on reversal requests;
  - the one-entry-per-request partial UNIQUE;
  - the credit columns in the replaced guard trigger;
  - each per-kind credit CHECK.
- **Regression:** every PR-MON-1..3 Billing test and every `tests/*_postgres.py`. #160 is inherited.

## 13. Human decisions (frozen 2026-10-14 on `43a3dedf`)

| # | Decision |
| --- | --- |
| C1 | **Keep the remaining credit as a financial liability.** Do not forfeit it and do not auto-refund it. History is kept and not cascaded. No new topup, reserve, settle or spend. Release, reserve_expire, refund, reversal and a controlled adjustment are still allowed. The value stays visible through `credit_balance_on_deletion` until a valid operation resolves it. (§8) |
| C2 | **No automatic transfer** to a new incarnation: no inheritance, no identity or email lookup, no reuse, no resurrection. Any future recovery is a separate explicit flow, out of scope. (§8) |
| C3 | **The reserve is a hard upper bound.** `charged = min(actual, hold)`, `uncharged = actual - charged`, enforced in the database. A late settle after release or reserve_expire is not charged and is recorded as `credit_late_settle`. (§4.3, §4.4) |
| C4 | **Adjustments are allowed in v1, only through the ledger.** A delta with mandatory reason, actor, idempotency key and digest. Never below zero. No "set balance". (§5) |
| C5 | **Reverse only what is available; record the shortfall.** Never negative, never from active reservations, never faked as a full reversal. `credit_reversal_shortfall` keeps the top-up and reversal context. (§5) |
| C6 | **Purchased credit does not expire in v1.** No decay, no hidden forfeiture, and no expiry timestamp on purchased credit. `reserve_expire` closes a reservation only. A future credit expiry would be its own explicit ledger event, reviewed separately. |
| C7 | **The reserve TTL default is 30 minutes.** `expires_at` is stored on the reserve, computed in its own transaction, and authoritative. Expire, release and settle are idempotent. One closing outcome per reserve. Races are serialized by the account lock and the database. (§4.2, §4.4) |

Still not decided, and not implemented in PR-MON-4: the credit ↔ VND conversion rate, meter pricing, the Free
allowance, auto top-up, payment provider activation, subscriptions, promotions, and any transfer between
incarnations.

## 14. Rollback policy

- **Before any real credit exists** (rehearsal only): `downgrade()` drops the tables, triggers and functions,
  removes the `credit_*` columns, restores 0031's CHECKs and guard function exactly, and revokes the grants.
  - It first **refuses** if `credit_ledger`, `credit_accounts` or `credit_reversal_requests` holds a row, or if any
    item of the new kinds exists.
  - It drops the two roles only when they own nothing and hold no privileges anywhere else in the cluster. Otherwise
    it leaves them in place, because roles are cluster-wide.
- **After real credits exist:** the schema is never downgraded. Rollback means rolling back the code, with billing
  off. The tables are additive and earlier code ignores them.
- No startup migration, no automatic apply, and no shared-runtime apply. Promotion follows H1 and its own human
  authorization, after 0027 and 0031.

## 15. Reviewer answers (review of `e5ccc114`)

1. Snapshot guard: **change required**, done in §2.1. A database-privilege boundary with a `SECURITY DEFINER`
   function (owner role, fixed `search_path`). The guard trigger stays as defense in depth only.
2. A reserve's state derived from its closing entries: **approved**. There is no holds table.
3. A late settle refused and recorded as `credit_late_settle`: **approved**.
4. 0032 extends the PR-MON-3 reconciliation schema instead of editing 0031: **approved**. The extension is
   specified in §9.1-§9.3 (P1-6).
5. 0032 parented on 0031: **approved and required**, because 0032 depends on 0031's reconciliation schema (§1).

## 16. Before migration 0032 is created

- Rebase onto the latest `main` and re-run the migration-topology check.
- The order **0027 → 0031 → 0032** is frozen. It is only re-parented under H1 if a migration of another lane
  entered the real chain.
