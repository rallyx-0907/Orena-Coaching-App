# PR-MON-10: Polar card subscriptions, the launch path for plans (design)

**Status: DESIGNING (docs only), for independent review.** Base: `main` `2dc57aa3`. Owner decision: D-MON-032 (plans
are auto-renewing card subscriptions through Polar; SePay only tops up Credits). This is a payment and entitlement
change, so it needs independent review before code. Nothing is enabled. `BILLING_ENABLED` stays off on every shared
runtime, and Polar Live is a human gate.

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
  - the status map `active` / `trialing` / `past_due` / `unpaid` / `canceled` / `incomplete*`;
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
  - `customer_email`: the signed-in learner's email.

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
| `.past_due` (status `past_due` / `unpaid`) | `past_due`, `paid_through` = failure moment | The billing grace (D-MON-011), then Free unless paid |
| `.revoked`, or `.canceled` status `canceled` | `ended` | Free |
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

### 4.5 Upgrade, downgrade and changing the period (v1)

- A learner with a live Polar subscription cannot start a second checkout (`_refuse_second_subscription`, as today).
- **v1:** changing between Plus and Pro, or between monthly and yearly, happens in Polar's portal if Polar allows
  product changes there. The resulting `.updated` event carries the new product. Orena must then take the plan from
  the subscription's **product id**, mapped back through the prices file, not from the first checkout's metadata.
  - This is a change to `_subscription`'s plan source.
  - **Review question Q2:** enable portal product changes in v1, or disable them on Polar and defer?

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
| `POLAR_ACCESS_TOKEN` | scopes `checkouts:write`, `products:read`, `customer_sessions:write` (plus `subscriptions:read` for diagnostics) |
| `POLAR_WEBHOOK_SECRET` | the `whsec_` secret |
| `POLAR_ENVIRONMENT` | `sandbox` / `production` |

The prices file has four Polar entries in USD minor units (999, 7999, 1999, 15999), each with `external_price_id` set
to its product id. Polar's dashboard webhook subscribes to `subscription.*`, `order.paid` and `refund.*`.

## 5. Tests

**Hermetic:**
- the checkout body (`products`, `metadata`, `external_customer_id`, `customer_email`, `success_url` with
  `{CHECKOUT_ID}`, `return_url`);
- every row of §4.2, from signed fixture webhooks shaped like the captured sandbox payloads (§6);
- the plan read from the product id after a portal change (if Q2 says v1);
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
3. cancel at period end from the portal: access stays, `cancel_at_period_end` is set;
4. revoke or let the subscription end: access ends;
5. a failing renewal (a Stripe test card that fails after attaching), if the sandbox allows it: `past_due`, then the
   grace;
6. a refund from Polar's dashboard: recorded;
7. the Polar-side price check: ready with matching prices, not ready after an edited price.

Polar **Live** (production token, real card) is a later human gate, together with gate 7b.

## 7. Out of scope

- The learner UI. The Billing Sheet's "Subscribe" and "Manage subscription" buttons and their states are PR-MON-9,
  from the design, with the UI lane. This PR supplies the APIs only.
- Credits, quota and funding enforcement, migration 0034.
- A domestic recurring-card gateway (D-MON-032).
- Trials and discounts: off in v1 unless the owner decides (`allow_discount_codes=false` proposed, review question Q3).

## 8. Review questions

- **Q1:** accept §4.3's renewal window (an `active` event before the renewal is paid, bounded by `.past_due` and the
  grace)? Proposed: yes.
- **Q2:** portal plan and period changes in v1 (plan taken from the product id), or disabled on Polar and deferred?
  Proposed: v1, with the plan from the product id.
- **Q3:** discount codes off at launch (`allow_discount_codes=false`)? Proposed: off until a promotion is decided.
- **Q4:** `external_customer_id` = the account incarnation (a deleted, re-registered account becomes a new Polar
  customer)? Proposed: yes.
