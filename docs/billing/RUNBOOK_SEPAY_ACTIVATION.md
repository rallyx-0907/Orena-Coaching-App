# Runbook: gate 7, SePay production activation (operator task)

**Status: prepared, not executed.** This is gate 7 of PR-MON-8 (`PR-MON-8_DESIGN.md` §12). Gates 1-6 and 8 passed on
the `:8031` sandbox on 2026-10-17.

**Who.** The owner/operator runs every step: the migration, the environment and the restart (owner decision,
2026-10-17). No agent runs it.

**Where.** The production host is chosen after the app is deployed to the VPS. Run this runbook once, on that host
only. It never applies to `:8000`, `:8010` or `:8021` unless the owner names one of them as production.

**What it enables:**
- domestic bank-transfer payments for Plus/Pro through SePay + VPBank, with the QR naming the VA (D-MON-030);
- one-time prepaid periods (a month or a year).

**What stays off:**
- Credits (`CREDITS_ENABLED`; R-MON-014 is only needed before Credits);
- quota and funding enforcement;
- migration 0034;
- the SePay recovery feed (`SEPAY_FEED_ENABLED`; it needs its own proof before it is turned on).

## 0. Preconditions

- **Code.** The host runs `main` at or after `2dc57aa3` (PR-MON-8 with #249 and #250).
- **Host and URL.** PostgreSQL is the runtime backend, and the account backbone is on (`ORENA_ACCOUNT_BACKBONE=on`). A
  public **HTTPS** base URL exists (`PUBLIC_BASE_URL=https://...`).
- **Production mode.** `APP_ENV=production`, with Google sign-in configured: checkout needs a signed-in learner.
- **Backup.** A fresh, verified backup of the host's database exists. No backup, no migration.

## 1. Migrations 0027 -> 0033

Follow `RUNBOOK_MIGRATION_0027_0033.md` exactly:
1. back up;
2. provision the roles;
3. run `alembic upgrade 20261015_0033`;
4. confirm the head is `20261015_0033`;
5. run its smoke checks.

**Do this before the restart on the new code.** Migration 0034 is **not** applied: it stays proposed.

## 2. Prices file (owner decision 2026-10-17: the catalogue's prices)

A JSON file on the host, for example `/etc/orena/billing_prices.json`, with amounts in whole dong:

```json
[
  {"plan_id": "plus", "period": "month", "currency": "VND", "amount_minor": 199000, "gateway": "sepay"},
  {"plan_id": "plus", "period": "year",  "currency": "VND", "amount_minor": 1590000, "gateway": "sepay"},
  {"plan_id": "pro",  "period": "month", "currency": "VND", "amount_minor": 399000, "gateway": "sepay"},
  {"plan_id": "pro",  "period": "year",  "currency": "VND", "amount_minor": 3190000, "gateway": "sepay"}
]
```

Every amount must equal the plan catalogue **in force** on that host: Admin → Plans & pricing, where an Admin edit
overrides the built-in values. A single mismatch closes the gateway (`price_mismatch`). Readiness (step 6) shows the
comparison for each price.

## 3. Environment (names here; the values stay on the host, never in Git or chat)

| Variable | Value |
| --- | --- |
| `BILLING_ENABLED` | `on` |
| `BILLING_DOMESTIC_GATEWAY` | `sepay` |
| `BILLING_PRICES_FILE` | the path from step 2 |
| `SEPAY_WEBHOOK_SECRET` | the **Live** webhook's HMAC secret (step 4) |
| `SEPAY_ACCOUNT_NUMBER` | the linked VPBank main account (receiving and matching only) |
| `SEPAY_ACCOUNT_NAME` | the account holder |
| `SEPAY_BANK_BIN` | `970432` (VPBank) |
| `SEPAY_PAYMENT_PREFIX` | `ORN` |
| `SEPAY_VA_NUMBER` | the **Live** VPBank VA; production refuses SePay checkout without it (`sepay_va_unset`) |
| `SEPAY_API_TOKEN` | a token created in **Live** (not Test Mode), dedicated to production; used by the operator backfill |
| `SEPAY_API_BASE` | `https://userapi.sepay.vn/v2` |
| `SEPAY_FEED_ENABLED` | empty (off) |
| `CREDITS_ENABLED` | empty (off) |

Use separate credentials for test and production. Revoke the token and rotate the webhook secret if either is exposed.

## 4. SePay dashboard (Live, Test Mode off)

1. **Webhook.** Webhooks → add a webhook:
   - URL `https://<production domain>/api/billing/webhooks/sepay`;
   - authentication **HMAC-SHA256**;
   - the VPBank account;
   - incoming transactions.

   Copy the secret into `SEPAY_WEBHOOK_SECRET`. Remove the old webhook that pointed at the sandbox's trycloudflare
   URL.
2. **Payment code structure.** Prefix `ORN`, then **6-12 digits**: order codes grow past six digits. A transfer whose
   code SePay does not parse is recorded as `payment_unknown_order`, never granted.
3. **IP allowlist.** If SePay offers one, enable it **in addition to** HMAC.

## 5. Restart and the grace policy

1. Restart the application on the new environment.
2. In Admin → Policies & limits → Billing, set **Late bank-transfer grace = 1** hour and confirm. The default `0`
   means unconfigured, and SePay checkout stays closed (`late_payment_grace_unset`).

## 6. Verify readiness

Open `GET /api/admin/billing/readiness` as an administrator. It must show:
- `ready: true` and `blockers: []`;
- `gateways.sepay`: `configured: true`, `active_domestic: true`, `virtual_account: "set"`, `late_payment_grace: "set"`,
  `feed: "disabled"`, `ready: true`;
- each price `matches: true`.

Any blocker names what is missing: fix it and recheck. Never work around a blocker.

## 7. First real purchase (owner, optional but recommended)

1. As a signed-in test learner, buy Plus monthly.
2. Pay the QR. The banking app must show the VA, the amount and `SEVQR ORN<code>`.
3. Confirm:
   - the order is `paid`;
   - the plan is active;
   - `GET /api/admin/billing/reconciliation` has no new item.
4. Refund it by your own transfer back, then `POST /api/admin/billing/orders/<code>/refund`. Access ends.

## Rollback

Set `BILLING_ENABLED=off` and restart: checkout closes, and access already recorded stays. The migrations are not
rolled back: the downgrade guard refuses while rows exist, and they are additive. Remove or disable the SePay Live
webhook if payments must stop arriving. A transfer made while the webhook is off waits in SePay → Incidents; replay it
later, or use the operator backfill (`POST /api/admin/billing/sepay/backfill`, admin-only, needs `SEPAY_API_TOKEN`).
