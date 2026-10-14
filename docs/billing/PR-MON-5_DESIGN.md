# PR-MON-5 payOS Credit Top-up — design

**State: DESIGN revision 3, awaiting the focused re-review.** Revision 3 answers the review of `f70ab375`, in which
P1-1 and the payload exclusivity are CLOSED:
- P1-2: a reversal is fulfilled only by its complete durable result, §7.1;
- P1-3: refund and top-up are serialized by one lock contract, §6.3, and the `payment_refunded` guard also requires
  that no exact top-up exists, §6.2.

Earlier, in revision 2:

- Revision 1 (`5a5c4053`) got REQUEST CHANGES. Its architecture was accepted, and three lifecycle P1s plus schema
  exclusivity are closed here:
  - P1-1: exact-match fulfillment, §6.1;
  - P1-2: `credit_reversal_unapplied`, §7.1;
  - P1-3: the terminal outcomes of `credit_topup_unapplied`, §6.2;
  - mutually exclusive order payload, §8.
- The human froze K1, K2, K5 and K6 (D-MON-022, §10).
- There is no code, no new migration file, and nothing is promoted (0027, 0031 and 0032 stay proposed). The schema change this design needs is specified in §8 as
a future proposed revision. It is created only after the design is APPROVED, and it is promoted with the others
under the human's migration gate.

Inspected on `main` `985691c7` (PR-MON-4 merged as #193), 2026-10-14.

The order of work, fixed by the human: design and review → migration gate (recheck topology, promote 0027 → 0031 →
0032 (→ 0033), throwaway/staging smoke tests) → implementation, CI, review, merge → production last (apply, change
the runtime role, `credit_runtime_privileges = ready`, and only then consider `CREDITS_ENABLED`).

**Out of scope, and decided by no one here:**
- the credit ↔ VND rate and the packs on sale (§10, K1);
- meter prices and the Free allowance;
- auto top-up;
- Polar credit sales (D-MON-002: payOS first);
- UI (PR-MON-9);
- consumption (PR-MON-6).

## 1. What exists, and the one hard constraint

- **PR-MON-3:**
  - A payOS order row (`billing_orders`) is the unit of payment.
  - A verified payment reaches it through `BillingService.record_payment → mark_paid` from **either** the webhook
    or the reconciler's lookup. The order is paid once (one payment per order); a later fact is a `duplicate`, or an
    anomaly item.
  - Anomalies (unknown order, mismatch, not payable, paid for a deleted account) become reconciliation items, never
    access.
- **PR-MON-4:** the credit ledger.
  - A `topup` is idempotent on a **global** (`source_type`, `source_ref`).
  - A `reversal` is decided once per money event (`credit_reversal_requests`, globally unique).
  - Every operation is refused until `credit_runtime_privileges` is ready.
- **The hard constraint.** `mark_paid` assigns `paid_sequence`. Every order with a `paid_sequence` feeds plan access:
  - `_chain` and `prepaid_state`;
  - `prepaid_gaps`;
  - the D-MON-014 manual-grant guard in `product_repository` (`paid_sequence IS NOT NULL`).

  **A credit order must never get a `paid_sequence`.** Otherwise a credit purchase would extend a plan. Every
  plan-access read must be limited to plan orders.

## 2. Contract 1: which payment may create a top-up

A top-up comes only from **a paid payOS `billing_orders` row whose `product_kind = 'credit_pack'`**:

- The order is created by a credit-pack checkout (§5) and **snapshots** its `credit_pack_id`, `credit_units` and
  price at creation. The credited amount is the order's `credit_units`, never re-read from configuration later.
- It is paid by a verified payOS payment through the existing `record_payment` path (webhook or lookup).
- Its account incarnation was active when the payment was recorded (`mark_paid` returns `applied`, not
  `paid_deleted_account`).
- Nothing else creates a top-up:
  - not a plan order;
  - not a Polar event (Polar sells no credits in v1);
  - not an admin action (that is a C4 `adjustment`);
  - not a return URL.

## 3. Contract 2: the source of truth

- **The paid order is the source of truth**, not the event that reported it. Both the webhook and the lookup only
  *record the payment* (PR-MON-3's one-payment-per-order model). The top-up is **derived from the paid order**.
- The top-up's source is `('billing_order', 'payos:<order_code>')`. It is globally unique in the ledger, so a
  payment can credit exactly one account exactly once, whichever path recorded it, however often, and in whatever
  order.
- After `record_payment` returns `applied` or `duplicate` for a credit order, the caller runs
  `apply_credit_topup(order)`. That is the same function the reconciler uses (§6), so there is one code path.

## 4. Contracts 3 and 4: mapping and duplicates

| Situation | Result |
| --- | --- |
| A first verified payment of a credit order | `mark_paid` (no `paid_sequence`), then `topup(units = order.credit_units, source = payos:<code>)`, giving `applied` |
| A webhook repeat, or a lookup after the webhook (or the reverse) | `mark_paid` gives `duplicate`, then `topup` gives `duplicate` (same source, same digest); no second credit |
| A webhook and a lookup racing | `mark_paid` serializes them on the order row; the topup's global UNIQUE and the account lock are the backstop; exactly one ledger entry |
| A second payment of a paid order (different transaction reference) | `payment_not_payable` item (PR-MON-3); no second top-up |
| A replay that reaches the ledger with another amount for the same source | `conflict` (the digest differs), nothing written, `credit_topup_unapplied` item (§6) |

## 5. Contract 5: checkout of a credit pack (no prices decided here)

- **Packs are configuration, a human gate (K1).** `BILLING_CREDIT_PACKS_FILE` lists packs:
  `{pack_id, credit_units, currency: "VND", amount_minor, gateway: "payos"}`.
  - With no file, nothing is sold.
  - `load_credit_packs` validates them the way `load_prices` validates prices: integers, a positive number of
    units, VND, a known gateway, and no duplicates.
- **Price integrity** (the D-MON-015 analogue):
  - A pack is sold only at its configured amount.
  - The learner confirms `amount_minor`, `currency` **and `credit_units`**. Any difference is `price_changed`.
  - The browser's numbers are never charged or credited.
  - There is no catalogue to compare with: the packs file is the only source, and it is a human decision.
- **Credits must be ready to sell.** A credit-pack checkout is refused (`credits_not_ready`, 503) unless:
  - `CREDITS_ENABLED` is on;
  - `CreditService.status().ready`;
  - the account is active and its credit account exists (`ensure_account`);
  - the PR-MON-2 checkout readiness passes (D-MON-017);
  - the PR-MON-3 critical gate passes for `payos` and for `credits` (§6).

  This keeps money from arriving where credit cannot be applied.
- `_refuse_second_subscription` does not apply. A credit pack is not a subscription, and buying credits while a plan
  is active is allowed.
- **The route.** The existing `POST /api/billing/checkout` accepts a pack key `credits:<pack_id>:payos` with
  `credit_units` in the confirmation. There is no learner screen: the UI is PR-MON-9, so the API ships gated (K5).

## 6. Contracts 6 and 7: anomalies and crash recovery

**Anomalies never top up.** They take the PR-MON-3 path unchanged:

- unknown order: `payment_unknown_order`;
- amount, currency or link mismatch, or an overpayment: `payment_mismatch`;
- not payable: `payment_not_payable`;
- **paid for a deleted account:** `paid_deleted_account` (money, a refund is owed). The top-up is never attempted.
  If the account is deleted **after** the payment was recorded but **before** the top-up, the ledger refuses the
  top-up (C1: no top-up on a deleted account). That is recorded as `paid_deleted_account` for the order too, and the
  money is owed back.

**A crash between recording the payment and the top-up.** These are two transactions: `mark_paid` (orders), then
`topup` (credit ledger, its own locks). Recovery mirrors PR-MON-3's prepaid gap. It rests on one precise definition of
"fulfilled".

### 6.1 Fulfillment is an exact match, never "a source exists" (review P1-1)

A paid credit order is **fulfilled** only when the ledger holds **the exact expected top-up**, that is, one entry
with all of:

- `kind = 'topup'`;
- `source_type = 'billing_order'` and `source_ref = 'payos:<order_code>'`;
- `credit_account_id` equal to the credit account of **the order's incarnation**;
- `amount = order.credit_units`, the snapshot;
- `request_digest` equal to the intent digest of exactly that top-up (kind, account, amount, source).

The rules that follow from this:

- `apply_credit_topup(order)` writes the top-up when none exists. It returns `duplicate` only for the exact match.
- If the global source `payos:<order_code>` is already taken by an entry that is **not** the exact match (another
  account, other units, another intent), the result is **`conflict`**. Nothing is written, and the order stays
  **unfulfilled**.
- A conflicting source is never counted as repaired. The gap stays and escalates (§6.2), and the item records the
  conflicting entry (`credit_topup_entry_id`) for the operator.
- The reconciler's gap scan uses the same predicate: a paid credit order **without** an exact match is a gap,
  whether or not some entry carries its source.

### 6.2 `credit_topup_unapplied`: detection, repair, and its terminal outcomes (review P1-3)

- **Detection** (derived): a credit order in state `paid` without its exact top-up (§6.1).
- **Repair:** the reconciler runs `apply_credit_topup(order)`. It is idempotent and runs in its own short
  transaction.
- **Escalation:** a gap that survives its repair opens or reopens the critical item **`credit_topup_unapplied`**:
  - money was taken and credit not given;
  - `gateway = 'credits'`, so it closes **credit-pack checkouts only**, never plan checkouts;
  - a conflicting source (§6.1) is recorded on it.
- **Terminal outcomes**, all reconciler-only. An administrator can never resolve or dismiss this item. Each outcome
  is backed by the database: a CHECK limits the outcome and the actor, and the guard trigger verifies the fact named
  below.

| Outcome | When the reconciler closes it | Fact the trigger verifies |
| --- | --- | --- |
| `credit_applied` | the exact expected top-up now exists | an exact top-up row (§6.1) for the item's order |
| `payment_refunded` | the operator recorded the full refund (K2) before any credit was given | the order is `refunded` **and no exact top-up exists for it** (§6.1). If a top-up exists, the refunded order belongs to the reversal lifecycle (§7.1), and `payment_refunded` is refused |
| `refund_obligation_recorded` | the account was deleted before the top-up; the ledger refused it, and the money is owed back through the existing path | an open or resolved `paid_deleted_account` item for the same order |

  - A **refunded** order is never topped up afterwards. This holds under concurrency through the lock contract of
    §6.3, not through a read taken before the credit transaction. A refund before the top-up ends the obligation as
    `payment_refunded`.
  - On **deletion before the top-up**, the reconciler records `paid_deleted_account` for the order (dedupe: the
    order code). It closes the top-up gap with `refund_obligation_recorded`. The obligation then lives on that money
    item, which is never dismissable, so nothing stays open twice and nothing is forgotten.
### 6.3 Refund and top-up are serialized (review P1-3)

**The canonical lock order** extends the global order of PR-MON-3 and PR-MON-4. Every transaction that touches more
than one of these takes them in this order:

```text
account_incarnations  →  billing_orders (the order row)  →  credit_accounts
```

- **`apply_credit_topup(order)`** is **one transaction** across the order and the ledger. It is a new repository
  method that does not call `credits.topup()` after a separate read:
  1. `account_incarnations … FOR SHARE` (the order's incarnation);
  2. `billing_orders … WHERE order_code = :code FOR SHARE`, then **re-read** the order under that lock and require
     all of the following, otherwise write nothing:
     - `product_kind = 'credit_pack'`;
     - `state = 'paid'`;
     - the incarnation `active`;
     - `credit_units` is the snapshot to credit.
  3. `credit_accounts … FOR UPDATE`, then the exact-match idempotency check (§6.1), then the `topup` INSERT. The
     ledger trigger re-takes the incarnation and the account in the same order;
  4. commit. Eligibility stays fixed by the order's `FOR SHARE` lock until the top-up commits.
- **`mark_refunded(order)`** (unchanged order of locks): `account_incarnations … FOR NO KEY UPDATE`, then
  `billing_orders … FOR UPDATE`.
  - Its incarnation lock conflicts with the top-up's `FOR SHARE`, and its order lock conflicts with the top-up's
    order `FOR SHARE`. The two transactions therefore never overlap.
- **Top-up commits first:** the refund waits behind the incarnation lock, then records `refunded`. The order now has
  its exact top-up, so the normal reversal lifecycle (§7.1) applies.
- **Refund commits first:** the top-up waits behind the incarnation lock. After acquiring it, it re-reads
  `state = 'refunded'` under the order lock and writes **no** top-up. The gap ends as `payment_refunded` (§6.2).
- **Database backstop (0033).** The ledger trigger `credit_apply_entry()` is replaced so that, for a `topup` whose
  `source_type = 'billing_order'`, it also:
  - takes the order row `FOR SHARE`, between the incarnation and the account locks (the canonical order);
  - requires `product_kind = 'credit_pack'`, `state = 'paid'`, `credit_units = NEW.amount`, and the order's
    incarnation equal to the account's.

  A writer that skips the repository still cannot credit a refunded, unpaid or mismatched order. For that row lock,
  `orena_credit_owner` gets `SELECT, UPDATE (updated_at)` on `billing_orders`; no function of the owner updates an
  order.
- **No provider call** is made while any of these locks is held. The payOS request of a checkout and the
  reconciler's lookup run with no transaction open (PR-MON-3 P1-4).
- **Runtime readiness.** `credit_runtime_privileges` also requires the row-lock privilege on `billing_orders`
  (`missing_lock_billing_orders`). The application's runtime already holds DML on it (runbook §2).

- **HTTP** (review answer 3):
  - A transient or system failure **before fulfillment completes** (a database error during the top-up) answers
    **503**. The provider redelivers, the redelivery is `duplicate`, and the top-up runs again.
  - A **business refusal** (credits not ready, the account deleted, a conflicting source) answers **200 only once**
    the money fact (the paid order) and the unresolved obligation (the gap, derivable by §6.1, plus its item where
    one was written) are durable. If writing that item fails, the answer is 503.

## 7. Contract 8: refund and chargeback after a top-up

- **payOS has no refund API.** An operator returns the money by bank transfer and records it with the existing
  `record_refund` (`mark_refunded`, `refunded_by = 'operator'`).
- For a credit order, the access sync is replaced by a **ledger reversal**. The balance is never edited:
  - `credits.reverse(topup_entry = the order's topup, requested = order.credit_units,
    source = ('payos_refund', 'payos:<order_code>'))`;
  - per C5: `applied = min(requested, available, remaining_reversible)`;
  - the shortfall (credits already spent or reserved) becomes `credit_reversal_shortfall`;
  - a replay returns the stored receipt and is never re-evaluated.
- **Ordering.** `mark_refunded` commits first, and the reversal is its own transaction. A crash between them, or a
  persistent failure, is handled durably (§7.1).
- **A refund is for the full order only (K2, frozen).**
  - V1 has no partial monetary refund of a credit-pack order. The operator decides whether to approve the refund.
  - Once a full refund is recorded, the reversal is attempted for the **full original `credit_units`**.
  - C5 reverses what it can, and the unavailable or spent part becomes `credit_reversal_shortfall`.
  - The balance never goes negative.

### 7.1 `credit_reversal_unapplied`: the refund → reversal gap (review P1-2)

- **Meaning:** money has been refunded, but the corresponding credit reversal request has not been durably applied.
- **An exact completed reversal** (review P1-2) is the complete durable result. A request row alone never counts.
  It needs all three of the following:
  1. **The exact request:** a `credit_reversal_requests` row with:
     - `source_type = 'payos_refund'` and `source_ref = 'payos:<order_code>'`;
     - `credit_account_id` equal to the order's credit account;
     - `topup_entry_id` equal to **the order's exact top-up** (§6.1);
     - `requested = order.credit_units`;
     - `request_digest` equal to the intent digest of exactly that reversal.
  2. **When `request.applied > 0`:** **exactly one** ledger `reversal` entry with
     `reversal_request_id = request.id`, in the same account, with `ref_entry_id` equal to the same top-up and
     `amount = request.applied`.
  3. **When `request.shortfall > 0`:** the `credit_reversal_shortfall` item with `dedupe_key = request.id`, whose
     `credit_reversal_request_id`, `credit_topup_entry_id`, `credit_requested`, `credit_applied` and
     `credit_shortfall` equal the request's. Its `credit_reversal_entry_id` is the entry of (2), or NULL when
     `applied = 0`.

  Its `applied` and `shortfall` are whatever C5 decided; the predicate checks that their effects exist.
  PR-MON-4's repository writes all three in one transaction, so the normal path always satisfies it, and no new
  financial model is involved.
- **One predicate, used three times:**
  - `credit_reversal_gaps()` (detection);
  - the reconciler's repair success (a retry counts only if the predicate then holds);
  - the `credit_reversed` terminal guard in the database.
- **Detection** (derived): a credit order in state `refunded` whose exact top-up exists and which has **no exact
  reversal receipt**. A refunded order that never got its top-up has nothing to reverse. That case is the
  `payment_refunded` end of §6.2.
- **Repair:** the reconciler retries the same idempotent `reverse(...)`.
  - A receipt already stored under the same money event but **not** the exact one (another account, top-up, amount
    or intent) is a `conflict`. It never counts as repaired.
- **Escalation:** a gap that survives its repair opens or reopens the critical item **`credit_reversal_unapplied`**:
  - `gateway = 'credits'`;
  - it blocks **credit-pack checkouts only**, never plan checkouts;
  - it records the order, the account, the top-up and `credit_requested`, plus the conflicting receipt, if any.
- **Terminal outcome:** `credit_reversed`, reconciler-only. The guard trigger verifies the **complete** predicate:
  request, entry when `applied > 0`, and shortfall item when `shortfall > 0`. An administrator can never resolve or
  dismiss this item.
- **Chargeback.** payOS VietQR is a bank transfer, so there is no card chargeback. A bank dispute that ends in a
  refund is recorded as an operator refund, as above.

## 8. Schema the design needs (a future proposed revision; not created now)

A follow-up revision **`20261015_0033_credit_topup_orders`** on `20261014_0032`. The approved revisions are not
edited, and the order becomes 0027 → 0031 → 0032 → 0033 (K4).

`billing_orders`:
- `+ product_kind VARCHAR(20) NOT NULL DEFAULT 'plan'`, CHECK `IN ('plan', 'credit_pack')`. Every existing row is a
  plan order.
- `+ credit_pack_id VARCHAR(40) NULL` and `+ credit_units BIGINT NULL`.
- `plan_id` and `period` become nullable. `ck_billing_order_period` becomes `period IS NULL OR period IN (…)`.
- New CHECKs. The payloads are **mutually exclusive** (schema hardening from the review):
  - `ck_billing_order_payload`:

    ```text
    (product_kind = 'plan' AND plan_id IS NOT NULL AND period IS NOT NULL
         AND credit_pack_id IS NULL AND credit_units IS NULL)
    OR (product_kind = 'credit_pack' AND plan_id IS NULL AND period IS NULL
         AND credit_pack_id IS NOT NULL AND credit_units > 0)
    ```

  - `ck_billing_order_credit_no_access`: `product_kind = 'plan' OR (paid_sequence IS NULL AND period_end IS NULL)`.
    This is the hard constraint of §1, in the database.
- `+ index ix_billing_orders_credit_paid` on `(state)`, where `product_kind = 'credit_pack' AND state IN ('paid',
  'refunded')`. It serves the gap scans.

`billing_reconciliation_items`:
- Two critical, reopenable, reconciler-only kinds are added:
  - `credit_topup_unapplied`, with outcomes `credit_applied`, `payment_refunded` and `refund_obligation_recorded`;
  - `credit_reversal_unapplied`, with outcome `credit_reversed`.
- Per-kind CHECKs, both requiring `gateway = 'credits'`:
  - `credit_topup_unapplied`: `billing_order_id`, `credit_account_id` and `credit_requested` (the units owed) are
    NOT NULL;
  - `credit_reversal_unapplied`: `billing_order_id`, `credit_account_id`, `credit_topup_entry_id` and
    `credit_requested` are NOT NULL.
- The outcome CHECK for each: `state = 'open'` OR (`resolved_by = 'reconciler'` AND the outcome is one of that
  kind's own).
- The guard function is extended. When a row moves to `resolved`, it verifies the outcome's fact (§6.2, §7.1):
  - `credit_applied`: an exact top-up row;
  - `payment_refunded`: the order `refunded` **and no exact top-up**;
  - `refund_obligation_recorded`: a `paid_deleted_account` item for the order;
  - `credit_reversed`: the complete reversal predicate.
- `credit_apply_entry()` is replaced. It keeps everything 0032 does, plus the billing-order check of §6.3 in the
  canonical lock order. The owner role gets `SELECT, UPDATE (updated_at)` on `billing_orders`, for the row lock
  only.
- The kind, outcome and critical lists and the guard function are replaced as in 0032, so every existing rule is
  kept and the new facts are frozen.

No change to the credit ledger tables: the top-up and the reversal already carry the needed sources.

**Downgrade:** it refuses while any `credit_pack` order, `credit_topup_unapplied` item or `credit_reversal_unapplied`
item exists. Otherwise it restores 0032's lists, guard and CHECKs exactly.

## 9. Code changes (after APPROVE, for the record)

- **`persistence/billing_repository.py`:**
  - `create_order` gains `product_kind`, `credit_pack_id` and `credit_units`;
  - `mark_paid` assigns `paid_sequence` and `period_end` **only for plan orders**;
  - `_chain`, `prepaid_gaps` and `prepaid_state` read only `product_kind = 'plan'`;
  - new `credit_topup_gaps()` and `credit_reversal_gaps()`, both on the exact-match predicates (§6.1, §7.1).
- **`persistence/credit_repository.py`:** new `apply_credit_topup(order_code)`. It is one transaction across
  the order and the ledger, in the canonical lock order, and re-reads the order under its lock (§6.3). The
  readiness check gains `missing_lock_billing_orders`.
- **`persistence/product_repository.py`:** the D-MON-014 guard reads only plan orders. This is a one-line filter in
  a shared file: minimal, stated, and tested.
- **`billing/service.py`:**
  - `load_credit_packs`;
  - checkout of a pack (§5);
  - `record_payment` → `apply_credit_topup` for credit orders, instead of `sync_prepaid`;
  - `record_refund` → `reverse_credit_topup` for credit orders.
- **`billing/reconciler.py`:** the steps for top-up gaps and reversal gaps. They use the PR-MON-3 lock, short
  transactions, and no payOS call inside any lock.
- **`billing/credits.py`:** nothing new beyond calling `topup` and `reverse`. The privilege gate already applies.

## 10. Contract 9 and the remaining decisions

| # | Decision | Status |
| --- | --- | --- |
| K1 | The packs on sale (the credit ↔ VND conversion) | **Frozen (human, D-MON-022):** PR-MON-5 implements the configuration contract only. Production has no packs yet. Sizes and prices are decided with the PR-MON-6 meter and cost model. No packs file means no credit products. |
| K2 | The refund of a credit-pack order | **Frozen:** full-order refunds only, and no partial monetary refund in v1. The operator approves or declines. A recorded full refund attempts the reversal of the full `credit_units`; C5 reverses what it can, the rest is `credit_reversal_shortfall`, and the balance is never negative. |
| K3 | Sell credits only when credits are ready (§5) | **Approved** (architecture). |
| K4 | A follow-up 0033 after 0032 | **Approved** (architecture). Order: 0027 → 0031 → 0032 → 0033. |
| K5 | Ship the pack-checkout API now | **Frozen:** shipped in PR-MON-5 behind the existing gates, with no UI. It is unavailable while `CREDITS_ENABLED` is off, while the runtime credit privileges are not ready, or while no packs are configured. |
| K6 | Purchase limits | **Frozen:** no per-account or per-day purchase-count limit in v1. The normal safeguards apply: idempotency, server-side pack validation, confirmed amount, currency and units, and the payment safety gates. |

**Contract 9.** There is no payOS call inside any credit-lock transaction:

- The checkout's payOS request happens after the order commits, outside any lock (as today).
- The lookup runs with no transaction open (PR-MON-3 P1-4).
- `topup` and `reverse` are their own short ledger transactions, and they never call a provider.

## 11. Failure matrix

| # | Failure | Result |
| --- | --- | --- |
| T-F1 | A webhook delivered twice | One payment, one top-up (duplicate on both). |
| T-F2 | A webhook and a lookup in parallel | The order row serializes `mark_paid`; the global topup source is the backstop; one credit. |
| T-F3 | A crash after `mark_paid`, before the top-up | The webhook answers 503 or the provider redelivers; the reconciler repairs; a gap that persists is critical (`credit_topup_unapplied`). |
| T-F4 | Credits disabled or privileged when payment arrives | Prevented by §5. If it happens anyway, the payment is recorded, the gap becomes critical and closes credit checkouts, and the reconciler applies the top-up once credits are ready. |
| T-F5 | The account is deleted between payment and top-up | The ledger refuses the top-up; `paid_deleted_account`; a refund is owed. |
| T-F6 | Mismatch, unknown order or overpayment | The PR-MON-3 items; no top-up. |
| T-F7 | A refund after the top-up, credits partly spent | A partial reversal plus `credit_reversal_shortfall`; never negative. |
| T-F8 | A crash between the refund record and the reversal | The reconciler re-runs `reverse` (idempotent). |
| T-F9 | A credit order mistakenly feeding plan access | Impossible: no `paid_sequence` (DB CHECK), and plan reads are limited to `product_kind = 'plan'`. |
| T-F10 | The pack configuration changes after checkout | The order's snapshot (`credit_units`, amount) is what is paid and credited. |
| T-F11 | The top-up source is already taken by another account or other units | `conflict`, nothing written; the order stays unfulfilled; `credit_topup_unapplied` records the conflicting entry (§6.1). |
| T-F12 | Refund recorded, reversal missing (crash or persistent failure) | The reconciler retries the exact reversal; if it persists, the critical `credit_reversal_unapplied` blocks credit-pack checkouts until the exact receipt exists (§7.1). |
| T-F13 | Refund recorded before any credit was given | `credit_topup_unapplied` closes as `payment_refunded`; no top-up, no reversal (§6.2). |
| T-F15 | `apply_credit_topup` and `mark_refunded` race | Serialized by the canonical lock order (§6.3). If the top-up wins, the refund follows, then the reversal lifecycle. If the refund wins, the top-up re-reads `refunded` and writes nothing, and the gap ends as `payment_refunded`. |
| T-F16 | A reversal request without its entry or its shortfall item | Not fulfilled. The gap stays, the repair counts only if the complete predicate then holds, and `credit_reversed` is refused (§7.1). |
| T-F14 | Account deleted before the top-up | The ledger refuses the top-up; `paid_deleted_account` is recorded for the order; the top-up gap closes as `refund_obligation_recorded` (§6.2). |

## 12. Test and mutation plan (throwaway PostgreSQL 16; the credit tests as the runtime role)

- **Contracts 1-4:**
  - webhook-only, lookup-only, webhook then lookup, lookup then webhook, and a concurrent race: one top-up each
    time;
  - a second payment with another reference gives an item and no top-up;
  - the credited units equal the order's snapshot after the pack file changes.
- **Contract 5:**
  - no packs file, no sale;
  - a changed amount, currency or units gives `price_changed`;
  - credits not enabled, not ready (privileged) or the account deleted give `credits_not_ready` before any order or
    payOS call;
  - buying credits with an active plan is allowed.
- **Contracts 6-7:**
  - each anomaly gives its item and no ledger row;
  - a crash injected between `mark_paid` and `topup` is repaired by the tick alone;
  - a persistent gap opens `credit_topup_unapplied`, which blocks credit checkouts only and is resolved only by the
    reconciler;
  - a deletion before the top-up gives `paid_deleted_account`.
- **Exact fulfillment (P1-1):**
  - a top-up source taken by **another account** gives `conflict`, the order is not fulfilled, and the item records
    the entry;
  - a source carrying **other units** gives the same;
  - neither ever counts as repaired;
  - a direct insert with the expected values is fulfilled.
- **Contract 8 and P1-2:**
  - a full refund leads to the reversal of the full `credit_units`, with a shortfall when they were spent;
  - a crash between refund and reversal is repaired by the tick alone;
  - a persistent failure opens `credit_reversal_unapplied`, which blocks credit-pack checkouts only;
  - a conflicting receipt (another account, top-up or amount) is never counted as repaired;
  - the item is resolved only as `credit_reversed`, with the exact receipt (an administrator's resolve is refused by
    the route, the CHECK and the trigger);
  - a replay is a duplicate.
- **Refund vs top-up serialization (review P1-3 of `f70ab375`)**, both orderings, with real concurrent
  transactions:
  - **top-up first:** a transaction holding the top-up's locks (incarnation `FOR SHARE`, order `FOR SHARE`, account,
    ledger insert), uncommitted. A concurrent `mark_refunded` must wait. After the top-up commits, the refund
    commits, and the reconciler applies the reversal (full, or partial with a shortfall);
  - **refund first:** an uncommitted `mark_refunded`. A concurrent `apply_credit_topup` must wait. After the refund
    commits, it writes no top-up, and the gap closes as `payment_refunded`;
  - **backstop:** a direct ledger insert of a `billing_order` top-up for a refunded order, an unpaid order, a plan
    order, or with other units is refused by the trigger.
- **Complete reversal predicate (review P1-2):**
  - a request row without its entry (with `applied > 0`) is not fulfilled;
  - without its shortfall item (with `shortfall > 0`) it is not fulfilled;
  - a shortfall item with mismatched facts is not fulfilled;
  - each is refused for `credit_reversed`;
  - the normal path is fulfilled.
- **`payment_refunded` guard:** refused while an exact top-up exists for the order.
- **Terminal lifecycle (P1-3):**
  - `credit_applied` once the exact top-up exists;
  - `payment_refunded` when the refund comes first (and no top-up afterwards);
  - `refund_obligation_recorded` after a deletion, with the `paid_deleted_account` item present;
  - each outcome refused by the trigger without its fact;
  - an administrator cannot close the item.
- **Schema exclusivity:** a plan order with a pack column, and a pack order with `plan_id` or `period`, are each
  refused.
- **The hard constraint:**
  - a paid credit order has `paid_sequence IS NULL` (the DB refuses otherwise);
  - plan access, `prepaid_gaps` and the D-MON-014 guard ignore credit orders;
  - plan purchase tests are unchanged.
- **Mutations**, each must fail its guard's test:
  - `paid_sequence` assigned to a credit order;
  - the plan-only filter in each of the three plan reads;
  - the topup source key;
  - the snapshot read;
  - the credits-ready checkout gate;
  - the gap repair;
  - the critical item and its checkout block;
  - the refund → reversal path;
  - the 0033 CHECKs (payload exclusivity, no access for credit orders, per-kind item CHECKs);
  - the exact-match predicates (top-up, and each of the three parts of the complete reversal);
  - the order re-read under lock in `apply_credit_topup`;
  - the order lock in the ledger trigger's billing-order check;
  - the "no exact top-up" clause of the `payment_refunded` guard;
  - each terminal outcome's trigger fact;
  - the downgrade guard.
- **Regression:** every PR-MON-1..4 Billing and credit test, and every `tests/*_postgres.py`. #160 is inherited.

## 13. Reviewer answers (review of `5a5c4053`)

1. The paid order as the source of truth: **approved**, subject to exact-match fulfillment (§6.1).
2. A new 0033 after 0032: **approved**.
3. The HTTP split: **approved with a clarification**, now written into §6.2:
   - a transient or system failure before fulfillment completes answers 503;
   - a business refusal answers 200 only once the money fact and the unresolved obligation are durable or
     derivable.
4. `credit_topup_unapplied` blocks **credit-pack checkout only**. `credit_reversal_unapplied` does too.
5. The plan-only filter for D-MON-014: **approved and required**.
