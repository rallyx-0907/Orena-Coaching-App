# PR-MON-5 payOS Credit Top-up — design

**State: DESIGN, stopped at the architecture review checkpoint.** There is no code, no new migration file, and
nothing is promoted (0027, 0031 and 0032 stay proposed). The schema change this design needs is specified in §8 as
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
`topup` (credit ledger, its own locks). Recovery mirrors PR-MON-3's prepaid gap:

- **Detection is derived:** a paid credit order (state `paid`, not refunded) with no ledger `topup` whose source is
  `payos:<order_code>`.
- **Repair:** the reconciler runs `apply_credit_topup(order)`, which is idempotent, in its own short transaction.
- **Escalation:** a gap that survives its repair opens a new critical item, **`credit_topup_unapplied`**:
  - money was taken and credit not given;
  - `gateway = 'credits'`; it closes **credit-pack checkouts**, not plan checkouts;
  - it is resolved only by the reconciler (`credit_applied`) once the top-up exists, so an administrator cannot
    dismiss it;
  - if the account was deleted meanwhile, it becomes `paid_deleted_account` instead.
- **HTTP:** a top-up that raises (a database error) makes the webhook answer **503**, so the provider redelivers.
  The redelivery is `duplicate` → top-up again. A business refusal (credits not ready, account deleted) is recorded
  as an item and answered 200, because the paid order is already durable.

## 7. Contract 8: refund and chargeback after a top-up

- **payOS has no refund API.** An operator returns the money by bank transfer and records it with the existing
  `record_refund` (`mark_refunded`, `refunded_by = 'operator'`).
- For a credit order, the access sync is replaced by a **ledger reversal**. The balance is never edited:
  - `credits.reverse(topup_entry = the order's topup, requested = order.credit_units,
    source = ('payos_refund', 'payos:<order_code>'))`;
  - per C5: `applied = min(requested, available, remaining_reversible)`;
  - the shortfall (credits already spent or reserved) becomes `credit_reversal_shortfall`;
  - a replay returns the stored receipt and is never re-evaluated.
- **Ordering.** `mark_refunded` commits first, and the reversal is its own transaction. A crash between them is
  repaired by the same reconciler rule: a refunded credit order with a top-up and no reversal request for
  `payos:<order_code>` gets `reverse(...)` again (idempotent through the global money-event key).
- **Refunding a credit order whose credits were spent** is a money decision: the operator refunds less, or waives
  (K2). The ledger records whatever it can reverse and the shortfall. It never goes negative.
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
- New CHECKs:
  - `(product_kind = 'plan') = (plan_id IS NOT NULL AND period IS NOT NULL)`;
  - `(product_kind = 'credit_pack') = (credit_pack_id IS NOT NULL AND credit_units > 0)`;
  - `product_kind = 'plan' OR (paid_sequence IS NULL AND period_end IS NULL)`. This is the hard constraint of §1,
    in the database.
- `+ index ix_billing_orders_credit_paid` on `(state)`, where `product_kind = 'credit_pack' AND state IN ('paid',
  'refunded')`. It serves the gap scans.

`billing_reconciliation_items`:
- The kind `credit_topup_unapplied` is added (critical, reconciler-only, outcome `credit_applied`, reopenable).
- Per-kind CHECK: `billing_order_id IS NOT NULL AND credit_account_id IS NOT NULL AND gateway = 'credits'`.
- The kind/outcome/critical lists and the guard function are replaced as in 0032, so every existing rule is kept.

No change to the credit ledger tables: the top-up and the reversal already carry the needed sources.

**Downgrade:** it refuses while any `credit_pack` order or `credit_topup_unapplied` item exists, and otherwise
restores 0032's lists, guard and CHECKs exactly.

## 9. Code changes (after APPROVE, for the record)

- **`persistence/billing_repository.py`:**
  - `create_order` gains `product_kind`, `credit_pack_id` and `credit_units`;
  - `mark_paid` assigns `paid_sequence` and `period_end` **only for plan orders**;
  - `_chain`, `prepaid_gaps` and `prepaid_state` read only `product_kind = 'plan'`;
  - new `credit_topup_gaps()` and `credit_reversal_gaps()`.
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

| # | Decision | Owner | Lane recommendation |
| --- | --- | --- | --- |
| K1 | The packs on sale (`credit_units` ↔ `amount_minor` VND), i.e. the conversion | **human (product)** | Not decided here. With no packs file, nothing is sold. |
| K2 | The money refunded for a credit order whose credits were partly spent | **human (product/legal)** | The operator decides per case. The ledger reverses what it can and records the shortfall (C5). |
| K3 | Sell credits only when credits are ready (§5) | architecture | Yes. Money must never arrive where credit cannot be applied. |
| K4 | A follow-up 0033 rather than editing the approved 0027/0032 before promotion | architecture + human migration gate | 0033 as a follow-up, promoted together: 0027 → 0031 → 0032 → 0033. |
| K5 | Ship the pack-checkout API now (gated), or wait for the UI (PR-MON-9) | human | Ship it gated by `CREDITS_ENABLED`. It is not reachable from any screen. |
| K6 | Purchase limits per account or day (fraud, mistakes) | human | None in v1 beyond price confirmation, unless asked for. |

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
- **Contract 8:**
  - full and partial reversal after a refund;
  - a crash between refund and reversal is repaired;
  - a replay is a duplicate.
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
  - the 0033 CHECKs;
  - the downgrade guard.
- **Regression:** every PR-MON-1..4 Billing and credit test, and every `tests/*_postgres.py`. #160 is inherited.

## 13. Questions for the reviewer

1. Is the paid order (not the event) as the source of truth, with the top-up derived and keyed on
   `payos:<order_code>`, sound under PR-MON-3's one-payment-per-order model?
2. A follow-up 0033 versus amending 0032 before its first promotion (K4).
3. Answering 503 for a top-up database error and 200 for a business refusal (§6). Is that the right split, given
   that the paid order is already durable?
4. Should `credit_topup_unapplied` also block **plan** checkouts on payOS, or only credit checkouts (as proposed)?
5. Is limiting the D-MON-014 guard to plan orders (in `product_repository`, a shared file) acceptable as a
   one-line filter?
