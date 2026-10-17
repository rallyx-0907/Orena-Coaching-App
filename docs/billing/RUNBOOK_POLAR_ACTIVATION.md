# Runbook: gate 7b, Polar card subscriptions for Plus and Pro (operator task)

**Status: prepared, not executed.** Plans are auto-renewing card subscriptions sold by Polar only (D-MON-032;
`PR-MON-10_DESIGN.md`). SePay never sells a plan, and this gate does not need Credits or SePay (revision 8.2).

**Who.** The owner/operator runs every step. No agent runs it, and no agent uses a production Polar token.

**Where.** The production host is chosen after the app is deployed to the VPS. This runbook never applies to `:8000`,
`:8010` or `:8021` unless the owner names one of them as production.

**What it enables:** Plus and Pro, monthly and yearly, paid by card on Polar's hosted checkout. Renewal is
automatic. Learners cancel, change plan or card, and read invoices in Polar's customer portal, opened from Plan &
usage.

**What stays off:** Credits, quota and funding enforcement, migration 0034, discounts and trials (owner Q3).

## 0. Preconditions

- The code is merged: revision 8.2 (#254) and PR-MON-10.
- The sandbox end-to-end run (`PR-MON-10_DESIGN.md` §6) passed and its payloads were captured.
- PostgreSQL is the runtime, with the account backbone on (`ORENA_ACCOUNT_BACKBONE=on`).
- `APP_ENV=production`, with Google sign-in configured.
- A public **HTTPS** `PUBLIC_BASE_URL`.
- Migrations up to `20261015_0033` are applied (`RUNBOOK_MIGRATION_0027_0033.md`), after a fresh, verified backup.

## 1. Polar dashboard (production organization)

1. **Products.** Create four recurring products, each with exactly **one** fixed USD price, equal to the catalogue:

   | Product | Interval | Price |
   | --- | --- | --- |
   | Plus monthly | month | 9.99 |
   | Plus yearly | year | 79.99 |
   | Pro monthly | month | 19.99 |
   | Pro yearly | year | 159.99 |

   No trial on any of them. An archived product, a second live price, or a different amount closes plan sales: the
   Polar-side check (R-MON-011) reports `polar_price_mismatch`.
2. **Customer portal** (owner Q2):
   - customers may update their subscription: `allow_customer_updates` on;
   - plan changes are allowed between the four products: `update_plan` on;
   - proration is **invoice** (`proration_behavior=invoice`): the difference is charged at once.
3. **Organization access token** with the scopes:
   - `checkouts:write`;
   - `products:read`;
   - `customer_sessions:write`;
   - `customers:write`, for the deleted-account clean-up (§4.8);
   - `subscriptions:read`, for diagnostics.
4. **Webhook**:
   - URL `https://<production domain>/api/billing/webhooks/polar`;
   - format **Raw**;
   - events: every `subscription.*`, plus `order.paid`, `refund.created` and `refund.updated`.

   Copy its `whsec_…` secret.

## 2. Environment (names here; the values stay on the host, never in Git or chat)

| Variable | Value |
| --- | --- |
| `BILLING_ENABLED` | `on` |
| `BILLING_PRICES_FILE` | the prices file (step 3) |
| `POLAR_ACCESS_TOKEN` | the production token (step 1.3) |
| `POLAR_WEBHOOK_SECRET` | the webhook secret (step 1.4) |
| `POLAR_ENVIRONMENT` | `production` |
| `BILLING_DOMESTIC_GATEWAY` | empty, unless Credits is also being enabled (gate 7a) |

## 3. Prices file

Four entries in USD minor units, each naming its Polar **product id**. Product ids are configuration, not secrets:

```json
[{"plan_id": "plus", "period": "month", "currency": "USD", "amount_minor": 999,   "gateway": "polar", "external_price_id": "<product id>"},
 {"plan_id": "plus", "period": "year",  "currency": "USD", "amount_minor": 7999,  "gateway": "polar", "external_price_id": "<product id>"},
 {"plan_id": "pro",  "period": "month", "currency": "USD", "amount_minor": 1999,  "gateway": "polar", "external_price_id": "<product id>"},
 {"plan_id": "pro",  "period": "year",  "currency": "USD", "amount_minor": 15999, "gateway": "polar", "external_price_id": "<product id>"}]
```

A plan price on `sepay` or `payos` is refused at startup (D-MON-032).

## 4. Restart and verify readiness

Restart the application, then open `GET /api/admin/billing/readiness` as an administrator. It must show:
- `ready: true` and `blockers: []`;
- `capabilities.plans`: `{"ready": true, "blockers": []}`. Credits may show its own blockers (for example
  `credits_not_configured`): that is expected, and it never blocks plans;
- `gateways.polar`: `configured: true`, `environment: "production"`, every price `match`,
  `provider_prices: "match"`.

Any blocker names what is missing: fix it and recheck. Never work around a blocker.

## 5. First real subscription (owner, recommended)

1. As a signed-in test learner, subscribe to Plus monthly with a real card.
2. Confirm:
   - the plan is active in Plan & usage after the webhook (the return page itself grants nothing);
   - `GET /api/admin/billing/reconciliation` has no new item.
3. From Plan & usage, open "manage" (`POST /api/billing/portal`) and cancel at period end. Access must stay until
   the period ends.
4. Refund from Polar's dashboard if wanted. The refund is recorded, and access follows Polar's subscription events.

## Rollback

Set `BILLING_ENABLED=off` and restart. New checkouts close, existing subscriptions keep renewing on Polar, and their
webhooks are still received and recorded. To stop renewals, cancel the subscriptions on Polar.
