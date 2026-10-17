# PR-MON-10: Polar card subscriptions, the launch path for plans (design)

**Status: DESIGNING, revision 3 (docs only), for a targeted delta re-review of §4.8.** Revision 2 answered the review of `6396fef3` (4 P1) and recorded the owner's answers to Q1-Q4 (§0). Revision 3 answers the review of `29ef5a4e` (1 P1): the Polar customer clean-up is an obligation of the deleted incarnation, with its own durable marker (§4.8). Base: `main` `2dc57aa3`. Owner decision: D-MON-032 (plans
are auto-renewing card subscriptions through Polar; SePay only tops up Credits). This is a payment and entitlement
change, so it needs independent review before code. Nothing is enabled. `BILLING_ENABLED` stays off on every shared
runtime, and Polar Live is a human gate.

## 0. Revision 2: the owner's answers and the review of `6396fef3`

**Owner decisions (2026-10-17):**
- **Q1:** yes, accept the renewal window of §4.3.
- **Q2:** yes. The plan comes from the subscription's `product_id`, and portal changes use `proration_behavior=invoice`.
- **Q3:** no discounts at launch. Checkout sends `allow_discount_codes=false` **and** `allow_trial=false`.
- **Q4:** yes. `external_customer_id` is the incarnation id, **with Polar customer clean-up when the account is
  deleted**.

| Finding | Revision 2 |
| --- | --- |
| **P1-1:** `unpaid` mapped to `past_due` | Polar's `past_due` is recoverable. When retries run out the subscription is revoked and its status becomes `unpaid`: access must end. `unpaid` (and `revoked` / `canceled` without `cancel_at_period_end`) now map to `ended` (§4.2). |
| **P1-2:** Q2 not a concrete contract | §4.5: Polar portal settings are `allow_customer_updates=true`, `update_plan=true`, `proration_behavior=invoice`. `product_id` is the source of truth. An unknown product id gives `event_undecided`, never a fallback to the old plan. |
| **P1-3:** the checkout's trial and discount defaults | §4.1: checkout always sends `allow_discount_codes=false` and `allow_trial=false` (both default to true on Polar). |
| **Rev 3 / P1 (review of `29ef5a4e`):** the clean-up was found through subscription mappings and confirmed by the commerce state `ended`, which proves nothing (a subscription can end before the deletion) | §4.8 rewritten. The obligation belongs to the **deleted incarnation**, found from the incarnation itself, including incarnations whose subscription already ended. Completion is a **separate durable marker**, never inferred from `ended`. The obligation survives restart and restore. A new incarnation's checkout waits for its predecessor's clean-up. `ACCOUNT_DELETION_RUNBOOK.md` gains the step. |
| **P1-4:** deletion lifecycle for `external_customer_id` | §4.8: when an incarnation is deleted, Orena calls `DELETE /v1/customers/external/{incarnation}` (scope `customers:write`). This immediately cancels active subscriptions and revokes benefits, with `anonymize=true`. It is retried until done, and recorded. |

## 1. Goal

A signed-in learner chooses Plus or Pro, monthly or yearly, and pays by card on Polar's hosted checkout.

- **Renewal:** Polar charges the card every period, and Orena keeps the plan active while Polar reports the
  subscription active.
- **Cancellation and card changes:** the learner manages or cancels from a link in the app (Polar's customer portal),
  and updates the card there.
- **Merchant of record:** Polar is the seller of record: tax, invoices and card data are Polar's. Orena never sees a
  card.

## 2. What exists (PR-MON-1..3) and is kept

- `PolarGateway` (`writing_coach/billing/polar.py`):
  - Standard Webhooks verification: HMAC over `{id}.{timestamp}.{body}`, a 5-minute window, `whsec_` keys;
  - the status map `active` / `trialing` / `past_due` / `unpaid` / `canceled` / `incomplete*` (revision 2 corrects
  `unpaid` to `ended`, §4.2);
  - `paid_through`: `current_period_end`, or for `past_due` the failure moment (`past_due_at`, else
    `current_period_start`);
  - `cancel_at_period_end`;
  - refund events.
- `BillingService._subscription`:
  - the first event attaches only to Orena's own checkout order for that account;
  - the stored provider-subscription mapping wins afterwards;
  - the plan comes from Orena's order;
  - events are ordered by Polar's own `modified_at` (`object_version`);
  - an undecidable event becomes `event_undecided`.
- The effective entitlement (PR-MON-1) puts billing ahead of manual, ahead of Free. `past_due` keeps access for the
  billing grace (D-MON-011, `BILLING_PAST_DUE_GRACE_HOURS`). An expired `paid_through` reads as ended.
- Price integrity (PR-MON-2): each `plan:period:polar` price in `BILLING_PRICES_FILE` must equal the catalogue in force.
- One live subscription per account (`_refuse_second_subscription`).

## 3. Polar facts (re-checked 2026-10-17 against polar.sh/docs)

- **Checkout:** `POST /v1/checkouts/` (scope `checkouts:write`):
  - body: `products: [<product id>]`, `success_url` (may carry `checkout_id={CHECKOUT_ID}`), `return_url` (a back
    button), `metadata` (copied to the subscription), `customer_email`, `external_customer_id` (links to or creates a
    Polar customer with Orena's id);
  - the response's `url` is where the learner pays.
- **Events:**
  - `subscription.created`, `.active` and `.updated` (`.updated` is a catch-all, including cycled / canceled /
    uncanceled / past_due / revoked);
  - `subscription.canceled`: with `cancel_at_period_end=true` the status stays `active` until the period ends;
  - `subscription.revoked`: the subscription has ended and benefits are revoked;
  - `subscription.past_due`: the renewal payment failed, and the customer can recover by updating the card;
  - `subscription.cycled`: a new period starts, before its renewal order exists, whatever the payment outcome;
  - `order.paid`: the renewal payment succeeded.
- **Customer portal:** `POST /v1/customer-sessions/` (scope `customer_sessions:write`) with `external_customer_id`
  returns a pre-authenticated `customer_portal_url` that expires (`expires_at`). Card updates exist only in the
  hosted portal.
- **Sandbox:** `https://sandbox-api.polar.sh`, with its own token. Test card `4242 4242 4242 4242`.
- **The owner's sandbox (read-only check, 2026-10-17):** four recurring products, each with one fixed USD price,
  matching the catalogue:
  - Plus monthly 9.99 / yearly 79.99;
  - Pro monthly 19.99 / yearly 159.99.

  Product ids are configuration, not secrets.

## 4. The changes

### 4.1 Checkout

- `PolarGateway.checkout_request` also sends:
  - `external_customer_id`: the account's incarnation id;
  - `return_url`;
  - `customer_email`: the signed-in learner's email;
  - **`allow_discount_codes=false` and `allow_trial=false`, always** (owner Q3). Both default to true on Polar, and
    `allow_trial=false` disables a trial even on a product that has one. A later promotion or trial is its own
    decision.

  It keeps `products: [<product id>]` and Orena's `metadata` (`orena_incarnation`, `orena_plan`, `orena_operation`).
  The prices file keeps `external_price_id = <Polar product id>`.
- **Return pages:** `success_url` is the plan screen with `checkout_id={CHECKOUT_ID}` (`/#/plan?checkout=done&...`);
  `return_url` is the plan screen. They replace today's fixed `/#/profile` (gap 6). **A return page never grants**:
  access changes only from a verified webhook.
- **Gateway selection:** a learner checkout for a plan goes to Polar, the only gateway allowed to sell plans
  (D-MON-032; revision 8 refuses domestic plan prices).

### 4.2 Lifecycle: the events handled, and the access they give

| Polar event / status | Orena commerce state | Access |
| --- | --- | --- |
| `subscription.created` / `.active`, status `active` | `active`, `paid_through = current_period_end` | Paid plan until `paid_through` |
| `.updated` / `.canceled` with `cancel_at_period_end=true`, status `active` | `active`, `cancel_at_period_end` | Until the period ends, then `.revoked` |
| `.uncanceled` | `active`, `cancel_at_period_end=false` | Unchanged |
| `.past_due`, status `past_due` (recoverable: the learner can update the card) | `past_due`, `paid_through` = failure moment | The billing grace (D-MON-011), then Free unless paid |
| status `unpaid` (retries exhausted; Polar revokes) | `ended` | Free, at once: no grace |
| `.revoked`, or status `canceled` without `cancel_at_period_end` | `ended` | Free |
| `.cycled` | as its status says | See §4.3 |
| `order.paid` (renewal) | evidence only (§4.3) | No change by itself |

### 4.3 Renewal before payment

Polar moves a renewing subscription into its next period (`.cycled`, a new `current_period_end`) before the renewal is
charged. An `active` event in that window would extend `paid_through` ahead of the payment.

- **Risk:** a short window of access the renewal may not pay for. If the payment fails, `.past_due` cuts
  `paid_through` back to the failure moment, so the exposure is that window plus the D-MON-011 grace. This is the
  card industry's normal behaviour.
- **Decision proposed:** accept it, as it is today. `order.paid` is recorded as evidence (logged, receipted). No
  separate payment ledger is added for subscriptions: Polar is the merchant of record and owns the money.
- **Review question Q1.**

### 4.4 Manage and cancel from the app

- New route `POST /api/billing/portal` (signed-in learner only): it asks Polar for a customer session with
  `external_customer_id = <the learner's incarnation>` and `return_url = <plan screen>`, then returns
  `{url, expires_at}`.
  - With no Polar subscription on the account, it answers 404 `no_subscription`.
  - When Polar fails, it answers 502, retryable.
  - The session URL is never logged and never stored.
- Cancellation, card changes and invoices all happen in Polar's portal. Orena learns the result from the webhooks of
  §4.2.

### 4.5 Upgrade, downgrade and changing the period (v1, owner Q2)

- A learner with a live Polar subscription cannot start a second checkout (`_refuse_second_subscription`, as today).
- **Polar configuration**, verified in sandbox E2E (§6) and pinned in the activation runbook:
  - the customer portal has `allow_customer_updates=true` and `update_plan=true`;
  - plan changes use `proration_behavior=invoice` (the difference is invoiced at once).
- **`product_id` is the source of truth for the plan**, on every subscription event, not the first checkout's
  metadata. The event's product id is mapped back through the configured prices (`external_price_id` → `plan:period`).
  - `_subscription` takes `plan_id` from that mapping. The order's plan and `orena_plan` metadata are only
    cross-checks on the first event.
  - An **unknown or unpriced product id** is recorded as `event_undecided` (an operator item). The commerce record is
    **not** changed, and there is **never** a fallback to the previous plan or to metadata.
  - A product that maps to a different period than before (monthly → yearly) is the same subscription. Only the plan
    and period change, and `paid_through` follows the event's `current_period_end`.

### 4.6 Price check on Polar's side (R-MON-011)

Readiness gains a cached, read-only Polar check. For each `plan:period:polar` price it reads the product by id
(`GET /v1/products/{id}`) and compares `price_amount` and `price_currency` with the prices file, plus the recurring
interval with the period.

- A mismatch, an archived product or an unreadable answer makes Polar not ready (`polar_price_mismatch` /
  `polar_unreadable`).
- No checkout starts while Polar is not ready.

### 4.7 Configuration (names only)

| Variable | Use |
| --- | --- |
| `POLAR_ACCESS_TOKEN` | scopes `checkouts:write`, `products:read`, `customer_sessions:write`, `customers:write` (deletion clean-up, §4.8), plus `subscriptions:read` for diagnostics |
| `POLAR_WEBHOOK_SECRET` | the `whsec_` secret |
| `POLAR_ENVIRONMENT` | `sandbox` / `production` |

The prices file has four Polar entries in USD minor units (999, 7999, 1999, 15999), each with `external_price_id` set
to its product id. Polar's dashboard webhook subscribes to `subscription.*`, `order.paid` and `refund.*`.

### 4.8 Account deletion: Polar customer clean-up (owner Q4, revision 3)

`external_customer_id` is the account incarnation. When an incarnation is deleted, its Polar customer must be deleted
and anonymized: no further charge, no benefit, no personal data. The clean-up is an obligation **of the deleted
incarnation**, not of a subscription. Orena's commerce mapping deliberately outlives the deletion, so that a late
webhook still resolves to the old incarnation. That mapping is audit and routing state, never a clean-up receipt.

```text
incarnation deleted (account_incarnations.status = 'deleted')
      |
      v
obligation: the incarnation had a Polar customer (discovery below) and has no completion marker
      |
      v
DELETE /v1/customers/external/{incarnation}?anonymize=true      (scope customers:write)
      |
      +-- 204 / 404  -> marker COMPLETE (204: deleted now; 404: none, or already deleted)
      +-- other / timeout -> marker PENDING, attempts + 1, next_attempt_at with back-off; retried
      +-- PENDING past the bound (24 h from the first attempt) -> operator item, retries continue
```

**Discovery: derived, so it cannot be lost.**
- Pending clean-up is computed, not queued: every incarnation with `status = 'deleted'` that ever started a Polar
  checkout (a `billing_orders` row with `gateway = 'polar'`) or has a Polar subscription mapping, **whatever that
  subscription's state**, and that has no `complete` marker.
- An incarnation whose subscription ended long before the deletion is therefore still cleaned up: its Polar customer
  exists and holds personal data.
- It over-approximates: a checkout that was never paid may have created no customer. The answer is then 404, which is
  complete.
- Because the obligation is derived from the deleted incarnation, it survives a restart. It also survives a restore:
  the deletion journal reapplies the deletion before anything is served (`deletion_journal.py`, D-054), and the
  derivation finds the obligation again.

**The durable marker: an existing primitive, no schema change.**
- One `platform_settings` row per cleaned incarnation, key `billing.polar.customer_cleanup.<incarnation id>`, written
  with the same CAS (`expected_updated_at`) the SePay feed cursor uses (`billing.sepay.feed_cursor`).
- Value: `{"state": "pending" | "complete", "attempts", "first_attempt_at", "next_attempt_at", "last_status",
  "completed_at"}`. No personal data, no Polar response body.
- **A lost marker is safe.** A restore to before a completion, or a removed row, only re-runs the DELETE. That answers
  404, and the marker is written `complete` again. A marker can never mark something complete that was not deleted,
  because only a 204 or 404 writes `complete`.
- **Reviewer choice.** If a per-incarnation key in `platform_settings` is judged the wrong home at scale, the
  alternative is a dedicated table, which is a schema change and needs its own review. The derivation above is
  unchanged either way.

**Who runs it.**
- The billing reconciler tick works through pending clean-ups oldest first, a bounded number per tick, honouring
  `next_attempt_at`.
- An admin route `POST /api/admin/billing/polar/customer-cleanup` runs the same step on demand. It is admin-only,
  returns counts (`complete`, `pending`, `escalated`) and never Polar data.
- Readiness reports `polar_customer_cleanup_pending` (a count) and `..._escalated`. Neither blocks checkout for other
  accounts.

**Escalation.** Past the bound, the step raises one operator item (kind `event_undecided`, reason
`polar_customer_cleanup_failed`, `incarnation_id` set) and keeps retrying. The item is resolved when the marker
becomes complete.

**Re-registration.** The same person re-registering is a new incarnation B, with its own `external_customer_id`.
- Before a Polar checkout for B, the service checks whether any deleted incarnation of the **same account** has a
  pending clean-up. If so, it runs that clean-up inline once:
  - complete: the checkout continues;
  - still pending: the checkout is refused, 503 `previous_customer_cleanup_pending`, retryable.
- This keeps A's customer, which holds the same email, from colliding with B's, and guarantees that A is gone before
  B pays.
- **Late webhooks of A never attach to B.** A's subscription mapping names incarnation A. A deleted incarnation's
  event takes the existing deleted-account path (`paid_deleted_account` / `rejected`, an operator item) and never
  reaches B: checkout attachment requires the order's own incarnation, and B's orders name B.

**Money.**
- Deleting the Polar customer cancels any live subscription at once.
- Whether a refund is owed follows the existing deleted-account rules (the `paid_deleted_account` item and the
  operator's refund path). Polar, as merchant of record, issues any refund from its dashboard.

**Order of operations.** Account deletion is never blocked by Polar. The incarnation is marked deleted first, and the
clean-up follows durably.

**Runbook.** `docs/project/ACCOUNT_DELETION_RUNBOOK.md` gains a "Billing: Polar customer" row and a verification
step:
- after the incarnation is marked deleted, run the clean-up route (or wait for a tick);
- confirm the marker is `complete` and no `polar_customer_cleanup_failed` item is open;
- do not close the request while it is pending.

The runbook stays DRAFT and keeps its own independent-review gate.

## 5. Tests

**Hermetic:**
- the checkout body (`products`, `metadata`, `external_customer_id`, `customer_email`, `success_url` with
  `{CHECKOUT_ID}`, `return_url`, `allow_discount_codes=false`, `allow_trial=false`);
- `unpaid` ends access at once (no grace), while `past_due` keeps the grace;
- the plan comes from the product id; an unknown product id gives `event_undecided` and leaves the record unchanged;
  a monthly → yearly change keeps the subscription;
- deletion clean-up (§4.8):
  - a subscription already `ended` before the account is deleted: the Polar customer is still deleted;
  - a deleted incarnation, then a restart: the clean-up is still pending and continues;
  - a lost marker (row removed, or a restore to before completion): the DELETE re-runs, gets 404 and completes;
  - 204 completes; 404 completes and repeating is harmless;
  - a failure retries with back-off, then escalates to one operator item, which resolves on completion;
  - `complete` is written only on 204 or 404, never inferred from a commerce state;
  - delete A, then register B with the same identity and email: B's checkout runs A's pending clean-up first, then
    proceeds; with A still failing, B is refused (503 `previous_customer_cleanup_pending`);
  - a late webhook of A never attaches to B;
  - the account deletion itself is never blocked;
- every row of §4.2, from signed fixture webhooks shaped like the captured sandbox payloads (§6);

- the portal route: ok, no subscription, Polar failure, and no URL in the logs;
- the price check: match, mismatch, archived product, unreadable answer;
- a return page grants nothing.

**PostgreSQL:**
- the commerce record's ordering under out-of-order `.updated` / `.past_due` / `.revoked`;
- one live subscription per account;
- the grace and the end of access.

## 6. Sandbox E2E (gates)

On the `:8031` sandbox, with a quick tunnel for the Polar sandbox webhook and the owner's sandbox token and products:
1. checkout with the test card: subscription active, plan granted;
2. **capture the real payloads** of each event (R-MON-009), with no customer data kept in Git, and replace the
   documented-shape fixtures with them;
3. cancel at period end from the portal: access stays, `cancel_at_period_end` is set; then a plan change in the
   portal (Plus → Pro, monthly → yearly) with an invoiced proration: the plan follows the product id;
4. revoke or let the subscription end: access ends;
5. a failing renewal (a Stripe test card that fails after attaching), if the sandbox allows it: `past_due`, then the
   grace;
6. a refund from Polar's dashboard: recorded;
7. delete a test account (with an already-ended subscription too): the Polar customer is deleted (anonymized), a
   live subscription revoked, and the marker `complete`; a re-registration's checkout then works;
8. the Polar-side price check: ready with matching prices, not ready after an edited price.

Polar **Live** (production token, real card) is a later human gate, together with gate 7b.

## 7. Out of scope

- The learner UI. The Billing Sheet's "Subscribe" and "Manage subscription" buttons and their states are PR-MON-9,
  from the design, with the UI lane. This PR supplies the APIs only.
- Credits, quota and funding enforcement, migration 0034.
- A domestic recurring-card gateway (D-MON-032).
- Trials and discounts: off at launch (owner Q3). Turning either on is a later decision.

## 8. Review questions (answered by the owner, 2026-10-17)

- **Q1:** accept the renewal window of §4.3. **Yes.**
- **Q2:** portal plan and period changes in v1. **Yes:** the plan comes from `product_id`, with
  `proration_behavior=invoice` (§4.5).
- **Q3:** **no discount and no trial at launch:** `allow_discount_codes=false`, `allow_trial=false` (§4.1).
- **Q4:** `external_customer_id` = the incarnation. **Yes, with the deletion clean-up of §4.8.**
