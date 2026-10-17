# Runbook: gate 7a, SePay production activation for Credits top-up (operator task)

**Status: prepared, not executed.** This is gate 7 of PR-MON-8 (`PR-MON-8_DESIGN.md` §12). Gates 1-6 and 8 passed on
the `:8031` sandbox on 2026-10-17.

**Who.** The owner/operator runs every step: the migration, the environment and the restart (owner decision,
2026-10-17). No agent runs it.

**Where.** The production host is chosen after the app is deployed to the VPS. Run this runbook once, on that host
only. It never applies to `:8000`, `:8010` or `:8021` unless the owner names one of them as production.

> **Revised by D-MON-032 (2026-10-17).** Plans are card subscriptions through Polar (gate 7b, after PR-MON-9 and
> PR-MON-10). SePay only tops up Credits. **This runbook cannot run yet**: Credits must be enabled first, and that
> needs three human gates (step 0).

**What it enables:** Credits top-up by VietQR bank transfer through SePay + VPBank, with the QR naming the VA
(D-MON-030).

**What stays off:**
- plans through any domestic gateway (refused by code, `PR-MON-8_DESIGN.md` §14.2); plans are Polar's (gate 7b);
- quota and funding enforcement unless separately decided;
- migration 0034 unless separately decided;
- the SePay recovery feed (`SEPAY_FEED_ENABLED`; it needs its own proof before it is turned on).

## 0. Preconditions

- **Credits gates (human), all three before this runbook:**
  - R-MON-014: the runtime connects as a role that cannot bypass the credit ledger (`RUNBOOK_R-MON-014_RUNTIME_ROLE.md`);
  - approved credit packs and prices (`BILLING_CREDIT_PACKS_FILE`; K1 and H-1, none set yet);
  - `CREDITS_ENABLED=on`.
- **The revision 8.1 code is merged** (§14: only Polar sells plans; readiness per capability).

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

## 2. Credit packs file (owner decision pending: K1 / H-1)

A JSON list of packs for `BILLING_CREDIT_PACKS_FILE`, each with `gateway: "sepay"` and `currency: "VND"`. For example
(the numbers are placeholders, **not** decided):

```json
[{"pack_id": "<id>", "credit_units": <units>, "currency": "VND", "amount_minor": <whole dong>, "gateway": "sepay"}]
```

**No plan price is listed for SePay** (D-MON-032; the code refuses one). Plan prices belong to Polar (gate 7b).

## 3. Environment (names here; the values stay on the host, never in Git or chat)

| Variable | Value |
| --- | --- |
| `BILLING_ENABLED` | `on` |
| `BILLING_DOMESTIC_GATEWAY` | `sepay` |
| `BILLING_CREDIT_PACKS_FILE` | the path from step 2 |
| `SEPAY_WEBHOOK_SECRET` | the **Live** webhook's HMAC secret (step 4) |
| `SEPAY_ACCOUNT_NUMBER` | the linked VPBank main account (receiving and matching only) |
| `SEPAY_ACCOUNT_NAME` | the account holder |
| `SEPAY_BANK_BIN` | `970432` (VPBank) |
| `SEPAY_PAYMENT_PREFIX` | `ORN` |
| `SEPAY_VA_NUMBER` | the **Live** VPBank VA; production refuses SePay checkout without it (`sepay_va_unset`) |
| `SEPAY_API_TOKEN` | a token created in **Live** (not Test Mode), dedicated to production; used by the operator backfill |
| `SEPAY_API_BASE` | `https://userapi.sepay.vn/v2` |
| `SEPAY_FEED_ENABLED` | empty (off) |
| `CREDITS_ENABLED` | `on` (only after its gates, step 0) |

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
  `feed: "disabled"`;
- credits ready, and the configured packs offered by `GET /api/billing/offers` (`credit_packs`).

Any blocker names what is missing: fix it and recheck. Never work around a blocker.

## 7. First real purchase (owner, optional but recommended)

1. As a signed-in test learner, buy the smallest credit pack.
2. Pay the QR. The banking app must show the VA, the amount and `SEVQR ORN<code>`.
3. Confirm:
   - the order is `paid`;
   - the credits are posted once;
   - `GET /api/admin/billing/reconciliation` has no new item.
4. Refund it by your own transfer back, then `POST /api/admin/billing/orders/<code>/refund`. The credits are
   reversed.

## Rollback

Set `BILLING_ENABLED=off` and restart: checkout closes, and access already recorded stays. The migrations are not
rolled back: the downgrade guard refuses while rows exist, and they are additive. Remove or disable the SePay Live
webhook if payments must stop arriving. A transfer made while the webhook is off waits in SePay → Incidents; replay it
later, or use the operator backfill (`POST /api/admin/billing/sepay/backfill`, admin-only, needs `SEPAY_API_TOKEN`).
