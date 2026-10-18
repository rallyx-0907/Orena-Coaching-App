# Runbook: gate 7b, Polar card subscriptions for Plus and Pro (operator task)

**Status: prepared, not executed.** Plans are auto-renewing card subscriptions sold by Polar only (D-MON-032;
`PR-MON-10_DESIGN.md`). SePay never sells a plan, and this gate does not need Credits or SePay (revision 8.2).

**Who.** The owner/operator runs every step. No agent runs it, and no agent uses a production Polar token.

**Where.** The owner named `:8000` as the production host for this gate (2026-10-18), served at
`https://orena.chillpickle.org`. A later move to the VPS follows "Moving the production host" below. This runbook
never applies to `:8010` or `:8021`.

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
3. **Organization access token** with exactly these scopes (each proved on the sandbox token, 2026-10-18; PR-MON-9
   review P1-4):
   - `checkouts:write`: the embedded and hosted checkout;
   - `products:read`: the Polar-side price check (R-MON-011);
   - `customer_sessions:write`: the customer portal (Update card, manage);
   - `customers:write`: the deleted-account clean-up (PR-MON-10 §4.8);
   - `customers:read`: the customer by external id and its payment methods (the card summary, PR-MON-9 §4.4);
   - `subscriptions:read`: the subscription view and the operation reconcile;
   - `subscriptions:write`: in-app plan change, cancel and resume (PR-MON-9 §4.2-§4.3);
   - `orders:read`: invoices (list, generate, download; PR-MON-9 §4.3).

   Missing any of the last four, the in-app management routes answer 502 or 503 at gate 7b: check them before the
   first real subscription.
4. **Webhook**:
   - URL `https://<production domain>/api/billing/webhooks/polar`;
   - format **Raw**;
   - events: every `subscription.*`, plus `order.paid`, `refund.created` and `refund.updated`.

   Copy its `whsec_…` secret.
5. **Embedding allowlist**: add the production origin. Without it the embedded checkout (PR-MON-9) does not open
   inside the app.

## 2. Environment (names here; the values stay on the host, never in Git or chat)

| Variable | Value |
| --- | --- |
| `BILLING_ENABLED` | `on` |
| `BILLING_PRICES_FILE` | the prices file (step 3), as a path inside the container on the data volume: `/data/billing/prices.json` |
| `POLAR_ACCESS_TOKEN` | the production token (step 1.3) |
| `POLAR_WEBHOOK_SECRET` | the webhook secret (step 1.4) |
| `POLAR_ENVIRONMENT` | `production` |
| `BILLING_DOMESTIC_GATEWAY` | empty, unless Credits is also being enabled (gate 7a) |

**Where the values go on `:8000`.** `:8000` is not started by compose: `scripts/staging_8000_deploy.ps1` runs
`docker run --env-file %LOCALAPPDATA%\orena-product\staging-8000\runtime.env` with the volume `ai-writing-coach-data`
at `/data`. So the values go in **`runtime.env`**, at step R6 of the `:8000` package, and the web container is
recreated by that script. The prices file goes into the volume, at `/data/billing/prices.json` (for example,
`docker cp prices.json <web container>:/data/billing/prices.json`, after creating the directory).

On a compose host, `compose.yaml` passes the same names (and `BILLING_NEW_SALES`) from `.env`, empty by default
(#295). Empty means off: `BILLING_ENABLED` empty is off. An empty `POLAR_ENVIRONMENT` means **sandbox**, so it must
be set to `production` explicitly. The ready list for this gate is `BILLING_ACTIVATION_READINESS.md`.

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

## Moving the production host (for example, from a staging host to the VPS)

Products, prices, the token's scopes, the portal settings and every subscription stay on Polar as they are. Only
the host-specific parts change:

1. **Prepare the new host.**
   - Same image, same environment.
   - A restored database: the subscriptions, receipts and `platform_settings` rows travel with it.
   - Migrations at the same head.
   - The prices file in its data volume.
   - `BILLING_NEW_SALES=off` until step 4.
2. **Change the public origin.** Point the new host's `PUBLIC_BASE_URL` at its HTTPS origin, and add the Google
   OAuth redirect `https://<new origin>/auth/google/callback`.
3. **Polar (production writes, owner).**
   - Webhook endpoint URL → `https://<new origin>/api/billing/webhooks/polar`. Editing the existing endpoint keeps
     its secret. A new endpoint needs its new `POLAR_WEBHOOK_SECRET`.
   - Embedding allowlist: add the new origin; remove the old one after the switch.
4. **Switch.**
   - Stop the old host's web service before the database is copied for the last time. Polar retries webhooks
     that fail meanwhile.
   - Start the new host and check readiness (§4).
   - Then `BILLING_NEW_SALES` empty, if sales were open.
5. **Check.**
   - Polar's dashboard shows the endpoint enabled and recent deliveries succeeding. Polar disables an endpoint
     after repeated failures: re-enable it if needed.
   - `GET /api/admin/billing/reconciliation` has no new item.

## Rollback

**Pause new sales (the safe rollback).** Set `BILLING_NEW_SALES=off` and restart.
- Readiness then reports `new_sales_paused`: no offer, and every new checkout **and every in-app plan change** (an
  upgrade charges like a sale) answers `503 billing_not_ready`.
- Everything a live subscription needs keeps running:
  - Polar webhooks are verified, recorded and applied (renewals, cancellations, `past_due`, revocations,
    `order.paid` receipts);
  - learners can still open the customer portal from Plan & usage to cancel or change their card;
  - the reconciler and the deleted-account clean-up keep running.
- Undo: `BILLING_NEW_SALES=on` (or empty) and restart.

**Full stop (`BILLING_ENABLED=off`) is not a rollback for live subscriptions.** With billing off the application
builds no billing service:
- webhooks answer `503 billing_off`, and Polar retries them and may disable the endpoint;
- the portal and the clean-up stop;
- subscriptions keep renewing on Polar while Orena stops following them.

Use it only after every subscription is cancelled on Polar, or for a short outage measured against Polar's webhook
retry window, then replay the failed deliveries from Polar's dashboard.
