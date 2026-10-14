# PR-MON-5 Architecture Review (design)

Recorded from the reviewer's verdict (relayed by the human, 2026-10-14). The design is
`docs/billing/PR-MON-5_DESIGN.md`.

---

# Review of design revision 1 (`5a5c40530f5e2eb76d87f24258cfd6be2d7187c5`)

## VERDICT

**REQUEST CHANGES**

The main architecture is accepted.

Do NOT redesign the payment → credit model and do NOT implement yet.

The following are accepted:

- paid `billing_order` as the source of truth;
- payOS webhook and reconciler converging on the same top-up operation;
- global top-up identity `billing_order / payos:<order_code>`;
- `product_kind` separating plan orders from credit-pack orders;
- credit orders never receiving `paid_sequence`;
- every plan-entitlement read filtering to plan orders;
- credit pack snapshots on the order;
- no provider call inside a credit-lock transaction;
- proposed `0033` after `0032`;
- gated pack checkout API;
- no production credit packs yet.

Fix only the following three lifecycle blockers.

### P1-1 — A top-up gap is satisfied only by the exact expected top-up

Do not define fulfillment as merely:

"a ledger top-up with source `payos:<order_code>` exists."

The reconciler must verify that the existing ledger entry matches the paid order's expected intent:

- `kind = topup`;
- source type/reference match the order;
- it belongs to the expected account/incarnation;
- credited amount equals the order's snapshotted `credit_units`;
- the idempotency/request intent is consistent.

If the global source already exists but belongs to another account or carries different units, that order is NOT fulfilled.

`apply_credit_topup()` should return conflict and the gap must remain/escalate to `credit_topup_unapplied`.

Add tests for wrong-account and wrong-amount source conflicts.

### P1-2 — Add durable escalation for refund → reversal gaps

A refunded credit order can be durable while its ledger reversal is still missing because of a crash or persistent failure.

Define a critical reconciliation condition:

`credit_reversal_unapplied`

or an equivalent explicit kind.

It represents:

money has been refunded but the corresponding credit reversal request has not been durably applied.

The reconciler:

- derives the gap from the refunded credit order + original top-up;
- retries the same idempotent reversal;
- opens the critical item if repair does not succeed;
- resolves it only after the exact reversal receipt exists.

The fulfillment check must verify the reversal receipt belongs to:

- the expected credit account;
- the expected original top-up;
- the expected order/refund source;
- the expected requested `credit_units`.

A conflicting receipt must never count as repaired.

This item should block new credit-pack checkouts, not plan checkout.

### P1-3 — Define the terminal lifecycle of `credit_topup_unapplied`

`credit_topup_unapplied` cannot have only one terminal outcome (`credit_applied`).

A paid credit order may legitimately end without a top-up when the money is returned.

Define reconciler-only terminal outcomes at least equivalent to:

`credit_applied`

and

`payment_refunded`

If the account is deleted after payment but before top-up and the obligation is moved to the existing refund/liability path, the old top-up-gap item must not remain permanently open.

The reconciler must close/transition the top-up-gap item once either:

- the exact expected top-up exists; or
- the payment obligation has been durably refunded/resolved under the allowed money path.

An administrator must still not be able to dismiss the item manually.

### Schema hardening

Make order payload columns strictly mutually exclusive.

For a plan order:

- `plan_id IS NOT NULL`
- `period IS NOT NULL`
- `credit_pack_id IS NULL`
- `credit_units IS NULL`

For a credit-pack order:

- `plan_id IS NULL`
- `period IS NULL`
- `credit_pack_id IS NOT NULL`
- `credit_units > 0`

Keep the hard DB invariant that a credit-pack order has:

`paid_sequence IS NULL`
and
`period_end IS NULL`

## Human decisions frozen for this revision

### K1 — Commercial packs

Do not choose production credit/VND values in PR-MON-5.

Implement the configuration contract, but production has no configured credit packs yet.

Actual pack sizes and prices will be decided with the PR-MON-6 meter/cost model.

No packs file = no credit products offered.

### K2 — Refund policy

V1 does NOT support partial monetary refunds of one credit-pack order.

A credit-pack order's monetary refund is full-order only.

The operator decides whether to approve the refund.

Once a full refund is recorded:

- attempt reversal for the full original `credit_units`;
- reverse only what C5 allows;
- record any unavailable/spent portion as `credit_reversal_shortfall`;
- never make the balance negative.

Do not invent a partial-VND-refund model in PR-MON-5.

### K5 — API timing

Ship the credit-pack checkout API in PR-MON-5 behind the existing gates.

No UI is required.

It remains unavailable while:
- `CREDITS_ENABLED` is off;
- runtime credit privileges are not ready;
- or no credit-pack configuration exists.

### K6 — Purchase limits

No per-account or per-day purchase-count limit in v1.

Keep normal:
- operation idempotency;
- server-side pack validation;
- confirmed amount/currency/units;
- provider/payment safety gates.

Fraud/purchase limits may be added later based on real usage.

## Reviewer questions

1. Paid order as source of truth: **APPROVED**, subject to exact-match fulfillment in P1-1.
2. New `0033` after `0032`: **APPROVED**.
3. HTTP split: **APPROVED WITH CLARIFICATION**:
   - transient/system failure before fulfillment completes → 503;
   - business refusal → 200 only once the money fact and the unresolved obligation are durable/derivable.
4. `credit_topup_unapplied`: block **credit-pack checkout only**, not plan checkout.
5. D-MON-014 plan-only filter: **APPROVED and required**.

Update only the design/status/decision documents.

Do not:
- implement PR-MON-5;
- create 0033;
- promote/apply 0027/0031/0032;
- enable credits;
- execute the R-MON-014 runbook.

Return the new design commit for focused re-review.

The next review is limited to P1-1, P1-2, P1-3 and the schema exclusivity checks.

## Design response (implementer, 2026-10-14)

Design revision 2 is in `PR-MON-5_DESIGN.md`. Documents only: there is no code, 0033 is not created, nothing is
promoted, and the runbook is not executed.

- **P1-1.** §6.1 defines fulfillment as the exact match: kind, source, the account of the order's incarnation, the
  snapshot units, and the intent digest. A taken but conflicting source gives `conflict`, the order stays
  unfulfilled, and the conflicting entry is recorded on the item. Wrong-account and wrong-units tests are in §12.
- **P1-2.** §7.1 adds `credit_reversal_unapplied`:
  - the gap is derived (a refunded order with its exact top-up and no exact reversal receipt);
  - the exact receipt is defined by account, top-up, source, requested units and digest;
  - a conflicting receipt never counts as repaired;
  - the item is critical, closes credit-pack checkouts only, and is resolved only as `credit_reversed`, which the
    trigger verifies.
- **P1-3.** §6.2 gives `credit_topup_unapplied` three reconciler-only outcomes, each fact-checked by the trigger:
  - `credit_applied`;
  - `payment_refunded`, after which no top-up follows;
  - `refund_obligation_recorded`, for a deletion before the top-up, with the `paid_deleted_account` item for the
    order.
  An administrator can resolve none of them.
- **Schema exclusivity.** `ck_billing_order_payload` makes the payloads mutually exclusive.
  `ck_billing_order_credit_no_access` (no `paid_sequence`, no `period_end`) is kept (§8).
- **K1, K2, K5 and K6** are recorded as frozen (D-MON-022, §10). The HTTP clarification is in §6.2.

---

# Focused review of design revision 2 (`f70ab37557cb0e0c707ebb0b5c48c758616920a5`)

## VERDICT

**REQUEST CHANGES**

This remains a focused design revision. Do not reopen the accepted architecture or frozen K decisions.

### CLOSED

- P1-1 exact top-up fulfillment: **CLOSED**
- mutually exclusive plan / credit-pack payload schema: **CLOSED**

Two narrow blockers remain inside P1-2 and P1-3.

## P1-2 — Define reversal fulfillment as the complete durable result

An exact `credit_reversal_requests` row alone must not be sufficient to close `credit_reversal_unapplied`.

Define an exact completed reversal as:

1. the exact reversal request exists:
   - expected credit account;
   - expected original top-up;
   - `payos_refund / payos:<order_code>`;
   - `requested = order.credit_units`;
   - exact request digest;

2. when `request.applied > 0`:
   - exactly one ledger `reversal` entry exists for that request;
   - same account and original top-up;
   - `entry.amount = request.applied`;

3. when `request.shortfall > 0`:
   - the corresponding `credit_reversal_shortfall` reconciliation item exists;
   - its requested/applied/shortfall facts match the request.

The normal PR-MON-4 repository already writes these in one transaction, so this does not require a new financial model.

Use this complete predicate for:
- `credit_reversal_gaps()`;
- reconciler repair success;
- the `credit_reversed` terminal guard.

A request row without its required durable effects never counts as repaired.

## P1-3 — Serialize refund against top-up

The design must close the concurrent race between:

`apply_credit_topup(order)`

and

`mark_refunded(order)`.

Required invariant:

### If top-up wins first

The refund waits/serializes behind it.

After the top-up commits, the refund is recorded and the normal reversal lifecycle applies.

### If refund wins first

The top-up must re-read the order after acquiring the serialization lock, observe:

`state = refunded`

and must not write a credit top-up.

It is not sufficient to read `state = paid` before entering the separate credit transaction and then call `credits.topup()` later.

Define a lock/transaction contract that keeps the order/incarnation eligibility stable until the ledger top-up commits.

Keep the existing global lock-order rules and do not make any payOS/provider call while these locks are held.

Add a concurrency regression for both orderings.

### `payment_refunded` terminal outcome

The database guard for:

`credit_topup_unapplied → payment_refunded`

must verify BOTH:

- the billing order is `refunded`;
- no exact top-up exists for that order.

If a top-up exists, the refunded order belongs to the reversal lifecycle and cannot close the top-up obligation merely as `payment_refunded`.

## Still accepted

Keep unchanged:

- paid order as source of truth;
- exact top-up predicate from §6.1;
- `credit_reversal_unapplied`;
- three top-up-gap terminal outcomes;
- credit issues block credit-pack checkout only;
- `0033` after `0032`;
- plan-only entitlement filters;
- K1/K2/K5/K6 / D-MON-022;
- HTTP 503/200 split;
- no provider call inside credit-lock transactions.

Update design/tests/mutation plan only.

Do not:
- implement PR-MON-5;
- create 0033;
- promote/apply migrations;
- run the runtime-role runbook;
- enable credits.

Return the next docs-only commit for a focused re-review of only these two points.

## Design response (implementer, 2026-10-14)

Design revision 3 (docs only).

- **P1-2.** §7.1 defines an exact **completed** reversal as three parts:
  - (1) the exact request;
  - (2) when `applied > 0`, exactly one `reversal` entry for that request, in the same account, with the same top-up
    and `amount = applied`;
  - (3) when `shortfall > 0`, the `credit_reversal_shortfall` item, whose facts match the request.

  The one predicate serves `credit_reversal_gaps()`, the repair success and the `credit_reversed` guard. Tests and
  mutations cover each part.
- **P1-3.** §6.3 sets the lock contract.
  - **The canonical order:** `account_incarnations` → `billing_orders` → `credit_accounts`.
  - **`apply_credit_topup`** is one transaction: the incarnation `FOR SHARE`, then the order `FOR SHARE`, where it
    re-reads `state = 'paid'` (and the kind, the active incarnation and the units), then the account `FOR UPDATE`
    and the top-up insert.
  - **`mark_refunded`** takes the incarnation `FOR NO KEY UPDATE`, then the order `FOR UPDATE`. Its locks conflict
    with the top-up's, so the two serialize in both orderings.
  - **Database backstop:** in 0033 the ledger trigger also checks a `billing_order` top-up (`credit_pack`, `paid`,
    the units, the incarnation) under the order's lock, in the canonical order. For that row lock the owner role
    gets `SELECT, UPDATE (updated_at)` on `billing_orders`.
  - No provider call happens while the locks are held.
  - Concurrency regressions cover both orderings, plus the backstop.
- **`payment_refunded`.** The guard verifies the order is `refunded` **and** that no exact top-up exists (§6.2, §8).

