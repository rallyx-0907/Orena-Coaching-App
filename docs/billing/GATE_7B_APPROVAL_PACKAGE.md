# Gate 7b: the one-approval package for the owner (`:8000`, `https://orena.chillpickle.org`)

**Status: prepared, nothing executed.** The owner approves this list once and runs every Polar production step
in Polar's dashboard. No agent writes to Polar production or holds its token. Secret values go straight into
`runtime.env`, never into chat or Git.

The procedure is `RUNBOOK_POLAR_ACTIVATION.md`; this file orders it as a checklist. Each step has a check and a
rollback, and no step is started before the previous one's check passes.

## 0. Before step 1 (all must hold)

| # | Precondition | Owner of it | How it is checked |
| --- | --- | --- | --- |
| C1 | R1 resolved (renewal is not dropped as `stale`) | Billing lane | **done 2026-10-19**: B and D renewed, and Orena applied D's renewal (`PR-MON-9_E2E_EVIDENCE.md` §3); no code change |
| C2 | `:8000` runs a build from `main` (**done**: `9952152a`, PRE-401 closed) | UI lane, deploy is an owner gate | PRE-401 re-read: USD in every language, the assist and `orena.voice` limits present |
| C3 | Migrations `0027` → `0033` applied | owner | **done**: `:8000` is at `20261018_0035`, read 2026-10-19. `billing_orders`, `billing_reconciliation_items`, `commerce_subscriptions`, `commerce_billing_event_receipts` and `account_incarnations` are present, so readiness raises no `*_schema_absent`. Nothing to approve |
| C4 | The paid-plan Terms published in English | owner: the text is approved (D-MON-037) except the downgrade sentence; UI lane publishes at R4 | `/terms` shows the section 3 of `PAID_PLANS_TERMS_INSERT.md`, with the downgrade sentence if approved, **before** `BILLING_NEW_SALES` is opened |
| C5 | Final prices confirmed | owner: **one yes** | Plus 9.99/79.99, Pro 19.99/159.99 USD, the same in `catalog.py` (no stored catalogue on `:8000`), the P1 products and the approved Terms |
| C6 | The plan limits a paying learner buys are enforced | **done, nothing to approve** | On `:8000` (2026-10-19): `ORENA_QUOTA_ENFORCEMENT=on`, and `ORENA_QUOTA_METERS` lists every meter this build can enforce (`quota.ENFORCEABLE`: `writing.review`, `orena.message`, `pronunciation.audio`, `media.import`, `languages.target`). `word.assist`, `reading.assist` and `writing.task` are in the catalogue only and cannot be enforced until 7B2 (`catalog.py`, `quota.WIRED_METERS`). Voice chat's plan check and daily cap hold whatever the switch says (`plan_features.py`, D-237) |

**What the owner approves in one yes (2026-10-19):**
- C5: the prices.
- P1-P5, done by the owner in Polar's dashboard.
- R1-R5 on `:8000`, each with its check.
- C4: the UI lane publishes the approved Terms just before R4.

C1, C2, C3 and C6 are done. The downgrade sentence for the Terms is a separate yes.

**`APP_ENV` stays `staging` on `:8000`** (read 2026-10-19).
- Plan billing does not need `production`. In the billing code, `production` only adds the https check on
  `PUBLIC_BASE_URL`, which `:8000` already passes, and stops inferring a domestic gateway, which plans never use.
- Moving `:8000` to `production` would change every lane's runtime, so it is a separate owner decision, not
  part of this gate.

## 1. Polar production (owner, in Polar's dashboard, in this order)

| Step | Write | Exact values | Check after it | Rollback |
| --- | --- | --- | --- | --- |
| P1 | Create 4 products | Plus monthly `month` 9.99 USD; Plus yearly `year` 79.99; Pro monthly `month` 19.99; Pro yearly `year` 159.99. One fixed price each, no trial, no benefits. Description of each says "Voice chat with Orena is included." | 4 product ids noted (configuration, not secrets) | archive the product: nothing is sold yet |
| P2 | Customer portal | customer updates on, plan change between the four products, proration **invoice** | the dashboard shows the settings | turn customer updates off |
| P3 | Organization access token | scopes exactly: `checkouts:write`, `products:read`, `customer_sessions:write`, `customers:write`, `customers:read`, `subscriptions:read`, `subscriptions:write`, `orders:read` | pasted into `runtime.env` only; verified at step R3 | revoke the token in the dashboard |
| P4 | Webhook endpoint | URL `https://orena.chillpickle.org/api/billing/webhooks/polar`, format **Raw**, events: every `subscription.*`, `order.paid`, `refund.created`, `refund.updated` | the `whsec_…` secret is pasted into `runtime.env` only; verified at step R3 | disable the endpoint |
| P5 | Embedding allowlist | add `https://orena.chillpickle.org` | verified at the first purchase (step R5) | remove the origin |

## 2. `:8000` (owner gate: deploy)

| Step | Action | Exact values | Check after it | Rollback |
| --- | --- | --- | --- | --- |
| R1 | Prices file on the data volume | `/data/billing/prices.json`: the 4 entries of the runbook §3, with the P1 product ids (`amount_minor` 999, 7999, 1999, 15999; `currency` `USD`; `gateway` `polar`) | the file is valid JSON (`python -m json.tool`) | delete the file; billing stays off |
| R2 | `runtime.env` (`%LOCALAPPDATA%\orena-product\staging-8000\runtime.env`) | `BILLING_ENABLED=on`, `BILLING_NEW_SALES=off`, `BILLING_PRICES_FILE=/data/billing/prices.json`, `POLAR_ENVIRONMENT=production`, `POLAR_ACCESS_TOKEN` (P3), `POLAR_WEBHOOK_SECRET` (P4), `PUBLIC_BASE_URL=https://orena.chillpickle.org` (already set), `ORENA_ACCOUNT_BACKBONE=on`. Leave empty: `BILLING_DOMESTIC_GATEWAY`, `CREDITS_ENABLED`, every `SEPAY_*` and `PAYOS_*` | presence only: `findstr /c:"BILLING_ENABLED=on" runtime.env` (never print the file) | restore the previous `runtime.env` |
| R3 | Redeploy with `scripts/staging_8000_deploy.ps1` | — | (a) `GET /api/admin/billing/readiness` as an administrator: `capabilities.plans` is `{"ready": true, "blockers": []}`, and the top-level `ready` is false with `blockers` exactly `["new_sales_paused"]`; `gateways.polar` `configured: true`, `environment: "production"`, `provider_prices: "match"`, every price `match`. (b) An unsigned `POST /api/billing/webhooks/polar` answers **401** (not 503). (c) Polar's dashboard lists the endpoint as enabled | set `BILLING_ENABLED` empty and redeploy. With no subscription yet, this is safe |
| R4 | Open sales | `BILLING_NEW_SALES` empty, redeploy | readiness `ready: true`, `blockers: []`; Pricing offers Plus and Pro in USD | `BILLING_NEW_SALES=off` and redeploy: the safe rollback, which keeps live subscriptions followed |
| R5 | First real subscription (owner) | runbook §5: Plus monthly with a real card | plan active after the webhook; `GET /api/admin/billing/reconciliation` no new item; the portal opens; cancel at period end keeps access; a refund is made with an immediate revoke in Polar's dashboard (D-MON-035) | `BILLING_NEW_SALES=off`; refund and revoke at once in the dashboard |

**Never** use `BILLING_ENABLED=off` as a rollback after R5, while a subscription is live. Webhooks would answer 503,
and Polar can disable the endpoint (runbook "Rollback").

## 3. What this package does not do

It does not enable Credits, SePay, payOS, quota or funding enforcement, migration `0034`, scheduled downgrades
(`SCHEDULED_CHANGES` stays off until the owner asks for scheduled downgrades; the 2026-10-19 runs answered which change wins), discounts or trials.
