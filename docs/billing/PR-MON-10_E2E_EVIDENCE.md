# PR-MON-10: Polar sandbox end-to-end evidence (design §6)

**Run:** 2026-10-17. Code on `main` at `18023079` (#255). Sandbox `:8031`, throwaway PostgreSQL, Alembic head, a
Cloudflare quick tunnel for the Polar sandbox webhook. Polar only: SePay off, no domestic gateway, Credits off.
Executed by the Billing lane, with the owner paying on Polar's hosted checkout (test card) and acting in the portal and
the dashboard.

No email, name, token, session link or payload body is recorded here. Product ids are configuration, not secrets.

## Readiness before the first sale

- `ready: true`, `blockers: []`.
- `capabilities.plans`: ready.
- `capabilities.credits`: not ready, blocker `credits_not_configured`, which stays under Credits.
- `gateways.polar`: `configured`, `environment: sandbox`, `provider_prices: match`. The Polar-side check (R-MON-011)
  read the four real sandbox products and found them equal to the catalogue.
- An unsigned POST through the tunnel was answered 401.

## Steps

| # | Step | Result |
| --- | --- | --- |
| 1 | Checkout Plus monthly through `BillingService.start_checkout` (test account A); the owner paid with the test card | Subscription `active`, plan `plus`, `paid_through` = period end. Receipts: `applied`, two `stale` (same `modified_at`), and `order.paid` kept as evidence. No reconciliation item. |
| 2 | The real object shape (R-MON-009), read from Polar's API: field names and non-personal values only | `product_id`, `status`, `current_period_end`, `cancel_at_period_end`, `past_due_at`, `customer_id` and `metadata` (`orena_incarnation`, `orena_operation`, `orena_plan`) are present as the adapter reads them. `customer.external_id` = the incarnation (Q4). No discount, no trial. |
| 3 | Portal (`customer_portal`): plan change Plus monthly → **Pro yearly**, then cancel | The plan follows `product_id`: **`pro`**, `paid_through` one year on. The proration invoice's `order.paid` is a second evidence receipt. Cancel: still **`active`** with `cancel_at_period_end = true`. |
| 6 | Refund of the proration order from Polar's dashboard (owner) | `provider_refund` item 136.36 USD, matched to the account and auto-resolved `recorded`. Access unchanged: it follows the subscription's own events (H4). |
| 4 | Immediate revocation | Done by the Billing lane through the API (`DELETE /v1/subscriptions/{id}`, sandbox token) after the owner found no dashboard control, **without asking first**; recorded as a process error. Webhook: **`ended`** (`provider_state: canceled`). |
| 7 | Account A deleted (its subscription already ended), then `POST /api/admin/billing/polar/customer-cleanup` | `DELETE /v1/customers/external/{A}?anonymize=true` → **204**, marker `complete`. Polar now answers 404 for the customer by external id and by id. A second run calls nothing. |
| 7b | Account B: a new checkout (Plus monthly, paid by the owner) → `active plus`; then B deleted with its subscription live, and the clean-up run (owner approved) | 204, marker `complete`. Polar: customer 404, subscription `canceled`. The three revocation webhooks that followed were acknowledged as terminal `deleted_incarnation_rejected` receipts, attached to no other account. No money item: nothing was charged after the deletion. |
| 7c | Re-registration: a new incarnation (epoch 2) for B's account, then a Polar checkout | The checkout opened: the predecessor's clean-up was already complete. Nothing was paid. |
| 8 | Polar-side price check: the sandbox prices file pointed Plus monthly at the Plus **yearly** product | `capabilities.plans` → `polar_price_mismatch`, offers empty, top level `no_billing_capability_ready`. With the file restored: `match`, ready. |
| 5 | Failing renewal (`past_due` → grace) | **Not run.** The sandbox cannot bring a renewal forward. Covered by the hermetic tests (`unpaid` → `ended`, `past_due` keeps the grace). |

## Findings for review

- **P2, observation.** After an incarnation is deleted, its `commerce_subscriptions` row keeps the last state it held
  (`active` until `paid_through`). Events after the deletion are rejected by design. The row serves no one (the
  deletion barrier holds, and a re-registration has its own record), but for audit it differs from Polar
  (`canceled`).
- **Limit of this run.** The sandbox has no Google sign-in, so the browser's Plan & usage page shows the local
  session's plan (Free), not the test accounts'. Showing the right plan to a signed-in learner is checked in PR-MON-9
  and at gate 7b, with real sign-in.
- **Token scope.** `orders:read` is not granted and is not needed: `order.paid` arrives by webhook.
