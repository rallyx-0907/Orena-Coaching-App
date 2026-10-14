# PR-MON-4 Prepaid Credit Ledger — design and migration plan

**State: DESIGN, stopped at the review checkpoint.** There is no code. Nothing is promoted or applied. The plan
proposes a new financial schema, so an independent architecture review (`AGENTS.md` §1, payment and schema) and the
human decisions in §13 come before any implementation.

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

- `down_revision = "20261014_0031"`. This keeps the Billing financial revisions in one line: 0027 → 0031 → 0032.
- It has **no foreign key to 0027 or 0031 tables**. A top-up names its source (a billing order) by an opaque
  reference, so the ledger depends only on `account_incarnations` (0005), which is applied.
- Under H1, if 0032 were ever promoted before 0027/0031, it would be re-parented onto the head of the day. Its tables
  stand alone.
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
| `kind` | VARCHAR(20) | One of `topup`, `reserve`, `settle`, `release`, `expire`, `refund`, `reversal`, `adjustment` (CHECK). |
| `posted_delta` | BIGINT | The change to `posted`. |
| `reserved_delta` | BIGINT | The change to `reserved`. |
| `amount` | BIGINT, > 0 | The magnitude the kind is about (see §4). |
| `ref_entry_id` | UUID NULL, FK `credit_ledger(id)` RESTRICT | The entry this one offsets (§5). |
| `idempotency_key` | VARCHAR(200), NOT NULL | §6 |
| `request_digest` | VARCHAR(64), NOT NULL | sha256 of the request's canonical parameters (§6). |
| `source_type`, `source_ref` | VARCHAR(40) / VARCHAR(200), NULL | For `topup`/`reversal`: the money event, e.g. (`billing_order`, `payos:100123`). |
| `meter`, `operation_ref` | VARCHAR(80) / VARCHAR(200), NULL | For `reserve`: what the hold is for (PR-MON-6 fills it). |
| `expires_at` | TIMESTAMPTZ NULL | For `reserve` only. |
| `uncharged` | BIGINT NULL, >= 0 | For `settle` only: actual usage beyond the hold, never charged (§4.3). |
| `actor` | VARCHAR(200), NOT NULL | `system`, `reconciler`, or an administrator's id. |
| `reason` | VARCHAR(400) NULL | Required for `adjustment`, `refund` and `reversal`. |
| `created_at` | TIMESTAMPTZ, NOT NULL | |

Per-kind sign rules are CHECK constraints (§4). There is no `UPDATE` and no `DELETE`.

### Why snapshot + ledger, and how it is rebuilt

The balance is the **result of the ledger**. `credit_accounts.posted` and `reserved` are a cache of `SUM(posted_delta)`
and `SUM(reserved_delta)` over that account's entries. They are maintained **by the database, in the same
statement**:

- An `AFTER INSERT` trigger on `credit_ledger` adds both deltas to the account row, sets `entry_count` and
  `last_entry_id`, and checks `NEW.seq = old entry_count + 1`. The account CHECK then refuses a result below zero,
  so the inserting transaction aborts and nothing is recorded.
- A guard trigger on `credit_accounts` refuses any `UPDATE` of `posted`, `reserved`, `entry_count` or
  `last_entry_id` unless it comes from the ledger trigger (`pg_trigger_depth() > 1`). No application code, and no
  operator's hand-written `UPDATE`, can set a balance.
- **Rebuild and verify.** `credit_balance_drift()` is a read-only query that compares every snapshot with
  `SUM(...)` over its ledger. The test suite asserts zero drift after every concurrency test. The PR-MON-3
  reconciler tick runs the same check and opens a critical `credit_balance_drift` item if it ever finds drift
  (§9, §10). A rebuild is never an `UPDATE` of the snapshot: drift is an incident, not something fixed by hand.

Pure-ledger reads would cost `O(entries)` and still need the same per-account lock. The snapshot gives O(1) reads,
and a CHECK constraint can express "never negative".

## 3. Invariants (each with its DB backstop)

| # | Invariant | Backstop beyond repository logic |
| --- | --- | --- |
| I1 | `posted >= 0`, `reserved >= 0`, `reserved <= posted`: available is never negative | CHECK on `credit_accounts`; the ledger insert aborts |
| I2 | The snapshot equals the ledger sums | The ledger trigger is the only writer (guard trigger); a drift check in tests and the reconciler |
| I3 | Ledger rows are never updated or deleted | Trigger refuses `UPDATE`/`DELETE` on `credit_ledger`; RESTRICT foreign keys |
| I4 | Accounts are never deleted, and a deletion never cascades | Trigger refuses `DELETE` on `credit_accounts`; RESTRICT foreign key to `account_incarnations` |
| I5 | Each operation applies at most once | UNIQUE (`credit_account_id`, `kind`, `idempotency_key`); UNIQUE (`source_type`, `source_ref`) for `topup` |
| I6 | A reservation closes exactly once (settle, release or expire) | Partial UNIQUE (`ref_entry_id`) where `kind IN ('settle','release','expire')`; trigger: the referenced row is a `reserve` of the same account |
| I7 | A closing entry releases exactly the hold, and a settle charges at most the hold | Trigger: `reserved_delta = -ref.amount`, and `-posted_delta <= ref.amount` for `settle` |
| I8 | Refunds of a debit total at most what that settle charged | Trigger: `SUM(refund.amount for ref) <= -ref.posted_delta`, with the referenced settle locked |
| I9 | Reversals of a top-up total at most that top-up | Trigger: `SUM(reversal.amount for ref) <= ref.amount`, with the referenced top-up locked |
| I10 | An offset references only its own kind | Trigger: refund→settle, reversal→topup, settle/release/expire→reserve, all in the same account; `topup`, `reserve` and `adjustment` reference nothing |
| I11 | Ledger order per account is total and gapless | UNIQUE (`credit_account_id`, `seq`), and the trigger checks `seq = entry_count + 1` |

## 4. Entry kinds and their effect

`amount` is always positive, and the deltas are fixed by the kind (CHECK):

| Kind | `posted_delta` | `reserved_delta` | References | Notes |
| --- | --- | --- | --- | --- |
| `topup` | `+amount` | 0 | none | `source_type`/`source_ref` required, globally unique. PR-MON-5 writes it from a verified payment. |
| `reserve` | 0 | `+amount` | none | Needs available ≥ amount. `expires_at` is required. |
| `settle` | `-charged` (0 ≤ charged ≤ hold) | `-hold` | its `reserve` | `amount` = actual usage; `uncharged = max(0, actual - hold)`. |
| `release` | 0 | `-hold` | its `reserve` | The caller did not use the hold (provider failed or not dispatched). |
| `expire` | 0 | `-hold` | its `reserve` | Written by the sweeper for an orphaned hold (§7). |
| `refund` | `+amount` | 0 | a `settle` | Credits returned for a charge, for example a provider failure found after settle. `reason` is required. |
| `reversal` | `-amount` | 0 | a `topup` | The top-up's money went back (payment refunded or charged back). `reason` is required. Needs available ≥ amount (§5). |
| `adjustment` | `±amount` (sign in `posted_delta`) | 0 | none | Administrator only, `reason` required (H-decision C4). |

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
  settle      release            expire  (sweeper, past expires_at)
 (charge ≤ hold)  (charge 0)      (charge 0)
```

There is exactly one closing entry per reserve (I6). A reserve is open while no closing entry references it; that
state is derived, never stored. A closing entry on an already-closed reserve is refused. When it is the same request
replayed (same key and digest) it is a duplicate and returns the original.

### 4.3 Settle with actual usage greater than the hold

Orena charges **at most the hold** (`charged = min(actual, hold)`). The excess is recorded as `uncharged` on the
settle entry and never charged later, because D-MON-002 forbids "charge later" and a negative balance.

PR-MON-6 sizes holds so that this is rare, and `uncharged` makes it measurable. An alternative, which the lane does
not recommend, is to also debit the excess from available credits in the same transaction (decision C3).

### 4.4 Late settle after expiry

If the sweeper has expired a hold and the provider's result arrives later, the settle is refused `reservation_closed`.
The usage is recorded as a reconciliation item `credit_late_settle` (dismissable: no money is owed by the learner;
Orena absorbed the cost). It is never charged after the fact.

`expires_at` is set by the caller from the meter's maximum dispatch time, with an operational default
(`CREDIT_HOLD_TTL`, 30 min) longer than any provider timeout. This makes a late settle rare.

## 5. Refund and reversal semantics

- **`refund`** names one `settle` (`ref_entry_id`) and returns up to what that settle charged, in one or more partial
  refunds (I8). It is the credit-side correction of a consume. It never names a top-up.
- **`reversal`** names one `topup` and removes up to its amount (I9). It is the credit-side consequence of money that
  went back: a payOS refund or a Polar chargeback (PR-MON-5 decides when to write it).
  - It also needs available ≥ amount. If the credits from that top-up were already spent, the reversal is refused
    `insufficient_available` and **nothing is written**.
  - The money-side caller then records a `credit_reversal_shortfall` reconciliation item, which is a money kind and
    cannot be dismissed (§9).
  - The balance is never driven negative to "claw back" spent credits (decision C5).
- An offset always lives in the same account as the entry it names (I10). There is no cross-account transfer.
- `adjustment` is the only entry without a source. It is administrator-only, with a mandatory reason and the actor
  recorded. A negative adjustment is limited by available (I1).

## 6. Idempotency keys

| Operation | Key | Scope | Replay |
| --- | --- | --- | --- |
| `topup` | `source_type` + `source_ref`, e.g. `billing_order:payos:100123` | **global**: one money event can never credit two accounts | The same source returns the original entry; a different account or amount is a conflict |
| `reserve` | the caller's `operation_id` (PR-MON-6: one per admitted operation) | per account and kind | The same key and digest returns the hold; a different amount or meter is a conflict |
| `settle` / `release` / `expire` | the reserve entry's id (via the I6 index), plus the caller's key | per reservation | Closing twice returns the first close if the digest matches, otherwise `reservation_closed` |
| `refund` / `reversal` / `adjustment` | the caller's operation id (an operator action or a PR-MON-5 refund event id) | per account and kind | The same key and digest returns the original; a different digest is a conflict |

`request_digest` is the sha256 of the canonical parameters: kind, account, amount, `ref_entry_id`, meter, source.
A retried request is therefore recognized as the same, and a reused key with other content cannot apply a second,
different effect.

## 7. Orphaned holds

- The reserve's `expires_at` is set at reserve time (§4.4).
- The PR-MON-3 reconciler, under its session advisory lock, gets one more step: expire holds past `expires_at`, in
  pages, one short transaction per hold. It writes an `expire` entry with actor `reconciler`.
- A deleted account's open holds are expired at once by the same step, whatever their `expires_at`.
- No provider is called, and no transaction is held across anything external.

## 8. Account deletion

- `credit_accounts` and `credit_ledger` use RESTRICT foreign keys and refuse `DELETE` (I3, I4). History and
  obligations survive deletion.
- After deletion (incarnation `status = 'deleted'`, checked under its `FOR SHARE` lock):
  - refused: `topup`, `reserve` and `settle` of a new charge;
  - allowed: `release` and `expire` of open holds, which only free credits;
  - allowed: `refund`, `reversal` and `adjustment`, which are financial corrections an operator may still owe.
- **The unused balance of a deleted account** (forfeit, refund in money, or kept as a liability) is a human/legal
  decision (C1). Until it is decided, the balance stays recorded and untouched, and the deletion records a
  `credit_balance_on_deletion` reconciliation item (a money kind) for the operator. The deletion runtime is an
  architecture hold (`AGENTS.md` §7); PR-MON-4 only provides the item and the ledger rules.
- Credits are bound to the incarnation that paid for them. A new incarnation after re-registration starts with no
  credits (decision C2: no carry-over).

## 9. Reconciliation items added (PR-MON-3 table, new kinds)

The 0032 migration extends the `billing_reconciliation_items` kind CHECK (0031) with three kinds. That CHECK is
replaced in 0032; 0031 itself is not edited. Their rules follow PR-MON-3's classes:

| Kind | Class | Closed by |
| --- | --- | --- |
| `credit_balance_drift` | **critical** (closes credit operations on that account, not checkouts) | the reconciler only, once the drift check is clean |
| `credit_reversal_shortfall` | money | `refund_confirmed` or `obligation_waived` with an audited reason; never dismissed |
| `credit_balance_on_deletion` | money | `refund_confirmed` or `obligation_waived` (the C1 decision); never dismissed |
| `credit_late_settle` | review (dismissable) | `recorded`, or dismissed with a note |

## 10. Failure modes

| # | Failure | Result |
| --- | --- | --- |
| C-F1 | Two reserves race on one account | Serialized by the account row lock. The second is refused when it would exceed `posted`; the CHECK is the backstop. |
| C-F2 | A retried reserve, settle, topup or refund | The same key and digest returns the original entry, with no second effect. |
| C-F3 | A reused key with different content | Conflict. Nothing is written. |
| C-F4 | A crash after the reserve commits, before dispatch | The hold stays open until `expires_at`, then is expired. No charge. |
| C-F5 | A crash after dispatch, before settle | The caller retries the settle with the same key. If it never settles, the hold expires uncharged: Orena absorbs the cost (`credit_late_settle` if a result arrives late). |
| C-F6 | A settle with actual > hold | Charged up to the hold, with the rest in `uncharged` (§4.3). |
| C-F7 | A double close (settle, then release) | Refused by the I6 unique index; a replay of the same close is a duplicate. |
| C-F8 | A refund larger than the debit, or two refunds racing | Trigger I8 under the referenced row's lock; the second over-refund aborts. |
| C-F9 | A reversal of spent credits | Refused, nothing written, then a `credit_reversal_shortfall` item (money). |
| C-F10 | The same payment credits twice, or credits two accounts | Global UNIQUE on (`source_type`, `source_ref`). |
| C-F11 | A hand-written `UPDATE` of a balance, or a `DELETE` of history | Refused by the guard triggers. |
| C-F12 | The snapshot drifts from the ledger (should be impossible) | Drift check, then a critical item; credit operations on the account stop. |
| C-F13 | The account is deleted while holds are open | Holds are expired by the reconciler; new charges refused; history kept; `credit_balance_on_deletion` item. |
| C-F14 | The database errors mid-operation | Single transaction: all or nothing. The caller retries with the same key. |

## 11. Implementation slices (after design APPROVE)

1. 0032 proposed migration: tables, CHECKs, ledger trigger, guard triggers, offset/limit trigger, downgrade guard,
   item kinds.
2. `persistence/credit_repository.py`: `ensure_account`, `topup`, `reserve`, `settle`, `release`, `refund`,
   `reversal`, `adjust`, `balance`, `entries`, `open_holds`, `drift`. Each operation is one transaction with the
   §4.1 lock order.
3. `billing/credits.py`: a service façade with typed results (`applied`, `duplicate`, `conflict`,
   `insufficient_credits`, `reservation_closed`, `account_deleted`). No provider calls. No prices.
4. A reconciler step that expires holds and checks drift (on PR-MON-3's lock, with short transactions).
5. Admin API, read-only (balance and ledger page), plus an adjustment route only if C4 says yes. There is no learner
   route: PR-MON-5 adds top-up and PR-MON-6 adds consumption.

Everything stays in Billing files. `app.py` changes only in start-up wiring.

## 12. Test and mutation plan (throwaway PostgreSQL 16 only)

- **Migration:**
  - upgrade, downgrade while empty, upgrade again;
  - downgrade refused once a row exists;
  - every CHECK and trigger probed: negative balance, direct snapshot `UPDATE`, ledger `UPDATE`/`DELETE`, account
    `DELETE`, wrong-kind reference, cross-account reference, over-refund, over-reversal, a second close, a seq gap;
  - 0032 applies on 0027 + 0031;
  - topology documented.
- **Concurrency:**
  - N threads reserve against one account with a total above the balance: exactly ⌊balance/amount⌋ succeed, the
    rest get `insufficient_credits`, and drift is 0;
  - concurrent refunds of one settle never exceed it;
  - concurrent closes of one hold give exactly one close;
  - a reserve racing a deletion is refused, or expired at once.
- **Idempotency:** every operation replayed (duplicate, one entry) and replayed with altered content (conflict,
  nothing written); a top-up source used on a second account is refused.
- **Semantics:**
  - settle under, at and above the hold (`uncharged`);
  - release and expire;
  - late settle is refused and creates a `credit_late_settle` item;
  - reversal with spent credits is refused and leaves the balance unchanged;
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
  - the hold expiry step;
  - the downgrade guard.
- **Regression:** every PR-MON-1..3 Billing test and every `tests/*_postgres.py`. #160 is inherited.

## 13. Human decisions (not decided by the lane)

| # | Decision | Lane recommendation |
| --- | --- | --- |
| C1 | The unused balance of a deleted account: forfeit, refund in money, or kept as a liability | Keep it recorded and untouched, and open `credit_balance_on_deletion` for the operator, until legal/terms decides. |
| C2 | Credits carried to a new incarnation after re-registration | No. Credits are bound to the paying incarnation. |
| C3 | Settle beyond the hold: cap at the hold (record `uncharged`), or also debit the excess from available | Cap at the hold (no charge later). |
| C4 | Administrator `adjustment` entries allowed in v1 | Yes: admin-only, mandatory reason, actor recorded, never below zero. Otherwise, defer the route. |
| C5 | A reversal of a top-up whose credits are partly spent | Reverse only what is available, never go negative, and record the shortfall as a money item. |
| C6 | Purchased credits expire | Not decided by the lane (legal/terms). The schema allows a later `expiry` kind without changing existing rows. |
| C7 | `CREDIT_HOLD_TTL` default | 30 min, operational. |
| — | Credit ↔ VND conversion, meter credit prices, Free allowance, auto top-up, activation | **Not decided** (human gates). There is no auto top-up in any design. |

## 14. Rollback policy

- **Before any real credit exists** (rehearsal only): `downgrade()` drops the tables, triggers and the added
  item kinds. It first **refuses** if `credit_ledger` or `credit_accounts` holds a row, or if any item of the new
  kinds exists.
- **After real credits exist:** the schema is never downgraded. Rollback means rolling back the code, with billing
  off. The tables are additive and earlier code ignores them.
- No startup migration, no automatic apply, and no shared-runtime apply. Promotion follows H1 and its own human
  authorization, after 0027 and 0031.

## 15. Questions for the reviewer

1. A snapshot maintained by a DB trigger, with an update guard (`pg_trigger_depth() > 1`), against pure-ledger sums
   under the same row lock. Is the trigger guard sound, or would you prefer a `SECURITY DEFINER` function as the only
   write path?
2. Is it acceptable for the reserve state (open or closed) to be derived from closing entries, rather than kept in a
   separate holds table?
3. Is a late settle, refused and absorbed as `credit_late_settle`, the right default against charging after expiry?
4. Extending the PR-MON-3 item kind CHECK from 0032, rather than editing 0031.
5. Parenting 0032 on 0031 (one Billing line) while it has no foreign key to 0027/0031 tables.
