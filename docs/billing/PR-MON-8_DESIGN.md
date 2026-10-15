# PR-MON-8: SePay domestic gateway, Billing sandbox and E2E (design)

**Status: DESIGNING (docs only).** Billing / Commerce scope (D-MON-029). Base: `main` `d42c9261`. Input:
`DOMESTIC_GATEWAY_SEPAY_ASSESSMENT.md` (D-MON-024). This is a payment change, so it needs independent review
before code, and again before merge. Nothing is enabled: `BILLING_ENABLED` stays off, no credential is configured, and
SePay is not approved for production.

**SePay facts re-checked on 2026-10-15** against the live developer pages (sources in the assessment):
- `X-SePay-Signature: sha256=<hex>` = HMAC-SHA256 over `{X-SePay-Timestamp}.{raw body}`. The timestamp is Unix
  seconds; SePay's sample rejects more than 300 s of skew and compares in constant time.
- `id` (integer) is the same across retries and replays: it is the dedupe key.
- `code` may be `null`, which is different from an empty string.
- `transferAmount` is an integer; `transactionDate` is `YYYY-MM-DD HH:mm:ss` in Vietnam time.
- Success means HTTP 200/201 with exactly `{"success": true}` within 30 s; anything else is a failure and is retried.

## 1. Goal and definition of done

A learner pays a domestic order by bank transfer to the owner's VietinBank account. The flow is:

```text
learner scans VietQR -> VietinBank books the transfer -> SePay detects it -> signed webhook
  -> Orena matches exactly one order (exact amount, VND) -> order paid
  -> prepaid period granted once | credit top-up exactly once
```

A missed webhook is recovered by the reconciler. Every unmatched or ambiguous transfer becomes a reconciliation item.
A refund is the operator's own outgoing transfer, recorded as today (K2: full refund or none).

## 2. What does not change

`PaymentFact`, `BillingService.record_payment`, `billing_orders` and its `mark_paid` rules stay exactly as they are,
as do commerce access, the credit ledger and 0033's top-up source, reconciliation items, refunds and reversals, and
deleted-account obligations. The payOS and Polar adapters keep their behaviour. No schema change is proposed (§6).

## 3. The adapter: `writing_coach/billing/sepay.py`

`SePayGateway`, `name = "sepay"`, `kind = "domestic"`, built from the environment by `from_env`. Only variable names
are listed here; their values are a human gate:

| Variable | Use |
| --- | --- |
| `SEPAY_WEBHOOK_SECRET` | HMAC key (shown once by SePay) |
| `SEPAY_ACCOUNT_NUMBER` | the receiving VietinBank account: the QR target, and the only `accountNumber` accepted |
| `SEPAY_ACCOUNT_NAME` | the account holder shown on the QR |
| `SEPAY_BANK_BIN` | VietinBank `970415`; configurable, never inferred |
| `SEPAY_PAYMENT_PREFIX` | the payment-code prefix configured in SePay (Company → General settings), e.g. `ORN` |
| `SEPAY_API_TOKEN` | the v2 transactions feed (reconciler only); optional, and without it there is no feed |
| `SEPAY_API_BASE` | `https://userapi.sepay.vn/v2`, or the sandbox base in test mode |

It is configured only when the secret, account number, account name, BIN and prefix are all present
(`GatewayNotConfigured` otherwise).

**`verify(headers, body, now)`**, in this order:
1. **Headers.** Both are required. The timestamp is an integer within ±300 s of server time
   (`WebhookRejected("stale_timestamp")`).
2. **Signature.** Constant-time `same("sha256=" + hmac(secret, f"{ts}.".encode() + body), header)` against the raw
   bytes, before any parsing (`bad_signature`).
3. **Body.** JSON with the documented field types (`unreadable_body` otherwise).
4. **Normalize** to `PaymentFact`:
   - `event_id = "sepay:<id>"`;
   - `amount_minor = transferAmount`, `currency = "VND"`;
   - `provider_state = "paid"`;
   - `payload_digest = digest(body)`;
   - `extra = {account_number, bank_reference: referenceCode, transaction_date}`, for audit only.

   The kind follows the payment code:

   | Case | `kind` | `external_reference` | Result downstream |
   | --- | --- | --- | --- |
   | `transferType != "in"` | `ignored` | — | outgoing money (including the operator's own refund transfer) |
   | `accountNumber` is not the configured account | `ignored` | — | another account the owner linked |
   | `code` is `null`, or does not start with the prefix | `payment` | None | existing path: `payment_unknown_order`, a reconciliation item (money moved) |
   | `code` = prefix + digits | `payment` | the integer order code | `record_payment` decides `applied` / `duplicate` / `mismatch` / `not_payable` / `paid_deleted_account`, as today |

   The digits are matched exactly. There is no fuzzy match, no amount-based guess and no memo search beyond `code`.

**`ack()`** returns `{"success": true}` (G4). Every other gateway answers its existing body.

## 4. Checkout without a provider call (G1)

SePay has no payment link. For a committed order, the adapter returns a `CheckoutStart` with no redirect:
- `qr_payload` is an EMVCo VietQR string built on the server:
  - merchant account information: NAPAS GUID `A000000727`, BIN, account number, service `QRIBFTTA`;
  - currency 704, the exact `amount_minor`, country VN;
  - purpose (tag 62/08) = `SEVQR <PREFIX><order_code>`;
  - a CRC-16/CCITT-FALSE checksum.

  It is pure and deterministic, tested against published VietQR examples, and calls no third-party QR image service.
- The response also carries the bank, account number, account name, amount and memo as plain fields, so a learner can
  transfer by hand.

`SEVQR` is mandatory for a VietinBank personal account through API banking. The memo stays within the 25-character
purpose limit: the design caps the prefix plus order-code length and refuses a configuration that would exceed it.

`BillingService._open_domestic_link` asks the gateway for its start (`gateway.start_checkout(intent, order)`). payOS
keeps its network call and parsing behind the same method, unchanged in behaviour. The order is set to `pending` as
today. No external reference is stored for SePay (there is no link id), so `mark_paid`'s same-link check does not
apply.

The order's `expires_at` still governs offers and the reconciler's expiry. A transfer that arrives after expiry is
still paid, because `mark_paid` already accepts `expired` / `cancelled` orders. Money that moved is honoured or
becomes a reconciliation item; it is never silently dropped.

## 5. Gateway selection becomes data (G2)

- `_GATEWAY_RULES` gains `"sepay": ({"VND"}, False)`.
- The **active domestic gateway** is `BILLING_DOMESTIC_GATEWAY` (`payos` | `sepay`), and it must name a configured
  domestic gateway. If both are configured and the variable is unset, the domestic side is **not ready**
  (`readiness` names `domestic_gateway_ambiguous`): never a silent pick.
- Credit packs, `credit_offers`, the `credits:<pack>:<gateway>` key and the critical-reconciliation check use the
  active domestic gateway instead of the literal `"payos"`. An existing payOS deployment keeps working with
  `BILLING_DOMESTIC_GATEWAY=payos`, or with payOS as the only configured domestic gateway.
- The prices file may list `sepay` prices (VND, no external price id). Price integrity against the catalogue is
  unchanged.

## 6. Missed webhooks: the reconciler feed (G3)

A new reconciler step, `sepay_feed`, runs when `SEPAY_API_TOKEN` is set:
1. Read the v2 transactions list for the configured account, incoming only, from the cursor minus a 2-hour overlap,
   one page per tick (`per_page` ≤ 100), honouring `429 Retry-After`.
2. Normalize each transaction through the **same** mapping as the webhook (§3), skipping the signature, which a feed
   answer does not carry.
3. Apply it through `handle_fact`.

`event_id = "sepay:<id>"` makes a transaction already received by webhook a `duplicate`, so the overlap is safe.

**Cursor storage: a platform setting, not a migration.** `billing.sepay.feed_cursor` =
`{transaction_date, last_id}` lives in `platform_settings` and is written after a page is applied. A lost or reset
cursor only re-reads, and the idempotent receipts absorb the repeat. A first run starts from the oldest pending SePay
order's `created_at`. This choice is a review question (Q2).

The feed is read-only. It never runs on the learner path, and a feed failure never fails a tick's other steps (the
existing per-step isolation).

## 7. Webhook route (G4)

`POST /api/billing/webhooks/sepay` reuses `billing_webhook`:
- 256 KiB limit, no session, `WebhookRejected` → 401, nothing stored;
- on any applied, duplicate, ignored or recorded-anomaly outcome it answers `gateway.ack()` with 200, so SePay stops
  retrying once Orena has durably recorded the fact (including an anomaly item);
- a transient server failure (database unavailable) answers 503, so SePay retries; this is unchanged behaviour.

## 8. Billing sandbox and E2E

- **Sandbox:** a separate container on `:8031` (if free; never `:8000` / `:8010` / `:8021`), with its own throwaway
  PostgreSQL migrated to head (0027 → 0033 applied **there only**), `BILLING_ENABLED=on`, and SePay **test-mode**
  credentials. Starting it is lane work; any shared-runtime or tunnel change is a human gate.
- **E2E, three levels:**
  1. **Hermetic** (CI): signed fixture webhooks for every row of §3, the feed with a fake transport, and exactly-once
     credit and prepaid grants.
  2. **SePay test mode** (operator-run): SePay's test webhook fired at the sandbox through a public URL. **(H)** The
     tunnel or public URL is a human gate (Cloudflare and DNS).
  3. **One live small-value transfer** **(H)** to the owner's real account, then refunded by the operator's own
     transfer, recorded as a refund.

## 9. Tests

- Signature: valid, wrong secret, tampered body, missing or garbled header, timestamp skew at ±300 s.
- Mapping: incoming and outgoing, wrong account, `code` null / empty / foreign prefix / non-digit, exact amount, wrong
  amount (`mismatch`), unknown order, a second payment of a paid order (`not_payable`), a late payment of an expired
  order (paid), a deleted account (`paid_deleted_account`).
- Idempotency: webhook redelivery, manual replay, and the same transaction from webhook and feed: one credit and one
  grant.
- The credit top-up through `sepay:<code>` (G5) and a full operator refund reversing it.
- Selection: payOS-only, SePay-only, both configured without a choice (not ready), the choice made.
- VietQR: known-answer vectors, the CRC and the length cap.
- Readiness and the `gateway_report` show SePay states with no secret.
- PostgreSQL: the paths above against the real `billing_orders`, receipts and ledger.

## 10. Out of scope

- PR-MON-9: the learner Billing Sheet UI, which renders the QR and the manual-transfer fields.
- PR-MON-10: Polar lifecycle.
- SePay refund API (enterprise only), virtual accounts and order-VA.
- Any Casso adapter.
- Plan & Entitlements and AI Economics work (D-MON-029).

## 11. Questions for review

- **Q1.** VietQR is built in Orena (EMVCo + CRC, no third party) rather than linking SePay's `qr.sepay.vn` image.
  Proposed: build in Orena.
- **Q2.** The feed cursor lives in a platform setting, not a migration. Proposed: a platform setting.
- **Q3.** The domestic gateway is an explicit `BILLING_DOMESTIC_GATEWAY`, and "both configured, none chosen" is not
  ready. Proposed: yes.
- **Q4.** A transfer whose `code` is missing or foreign is recorded as `payment_unknown_order`, never matched by amount.
  Proposed: yes.
- **Q5.** A late transfer for an expired order is honoured (today's `mark_paid` rule). Proposed: yes.

## Human gates (unchanged by this design)

- SePay account, plan (STARTUP or above for volume), VietinBank linking, the payment-code prefix, the HMAC secret and
  the API token.
- The public URL for test mode, and the live small-value transfer.
- Production activation and every runtime migration.
