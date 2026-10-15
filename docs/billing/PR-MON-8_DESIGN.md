# PR-MON-8: SePay domestic gateway, Billing sandbox and E2E (design)

**Status: DESIGNING, revision 2 (docs only).** Revision 2 answers the review of revision 1 (`b01e2f5f`: 2 P1, Q1-Q5); see §0. Billing / Commerce scope (D-MON-029). Base: `main` `d42c9261`. Input:
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

## 0. How revision 2 answers the review

| Finding | Revision 2 |
| --- | --- |
| **P1, cross-source identity.** Webhook `id` is an integer; Transactions API v2 `id` is a UUID, and v1 numeric ids do not work with v2 (upgrade guide). "`sepay:<id>` makes webhook and feed duplicates" was wrong. | **§3.1.** Source ids stay separate (`sepay:wh:<int>`, `sepay:v2:<uuid>`), kept for audit. The **payment event id** that `mark_paid` and the receipt dedupe on is the bank reference when there is one: `sepay:ref:<account>:<reference>` (webhook `referenceCode` = v2 `reference_number`). Without a bank reference, two source events are **never** assumed to be the same transfer: the feed applies only a transaction SePay reports as not webhook-delivered and old enough to be past the webhook retry window, and any remaining collision becomes a reconciliation item (§6.3). Business-level exactly-once stays with the order (`paid_event_id`) and the ledger's unique top-up source. |
| **P1, cursor algorithm.** | **§6 is rewritten.** `since_id` (UUID) is the one authoritative cursor; a page is processed in order and the cursor advances only after every transaction on it is applied; it stops at the first transaction still inside the settle delay; the first run backfills with `transaction_date_from`; there is no overlap sweep in the cursor. Recovery is a separate, operator-run backfill by date range. The undocumented points (order, inclusive or exclusive `since_id`) are made safe by idempotency and verified in test mode. |
| **Q1** VietQR in Orena | Approved. Known-answer vectors plus a real scan in SePay test mode (§4, §8). |
| **Q2** cursor in `platform_settings` | Approved on condition. One logical writer: the reconciler tick already holds the advisory lock, and the cursor write is a compare-and-set on the setting's `updated_at` (§6.2). |
| **Q3** explicit domestic gateway | Yes. With `BILLING_ENABLED=on`, `BILLING_DOMESTIC_GATEWAY` is required; development and test may infer it when exactly one domestic gateway is configured (§5). |
| **Q4** no amount matching | Approved, unchanged. |
| **Q5** late payments | **Bounded.** A transfer after the order's `expires_at` plus a configurable grace is recorded as a `payment_late` reconciliation item: the money is recorded, nothing is granted on old terms, and the operator refunds or honours it by hand. The grace value is a human decision (§4.1). |

The file count of revision 1 was two docs files (`PR-MON-8_DESIGN.md`, `BILLING_STATUS.md`), not one.

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
   - `event_id`: the payment event id of §3.1;
   - `amount_minor = transferAmount`, `currency = "VND"`;
   - `provider_state = "paid"`;
   - `payload_digest = digest(body)`;
   - `extra = {source_id: "sepay:wh:<id>", account_number, bank_reference: referenceCode, transaction_date}`, for
     audit only.

   The kind follows the payment code:

   | Case | `kind` | `external_reference` | Result downstream |
   | --- | --- | --- | --- |
   | `transferType != "in"` | `ignored` | — | outgoing money (including the operator's own refund transfer) |
   | `accountNumber` is not the configured account | `ignored` | — | another account the owner linked |
   | `code` is `null`, or does not start with the prefix | `payment` | None | existing path: `payment_unknown_order`, a reconciliation item (money moved) |
   | `code` = prefix + digits | `payment` | the integer order code | `record_payment` decides `applied` / `duplicate` / `mismatch` / `not_payable` / `paid_deleted_account`, as today |

   The digits are matched exactly. There is no fuzzy match, no amount-based guess and no memo search beyond `code`.

### 3.1 Event identity across the webhook and the feed

| Source | Source id (audit, receipts) | Bank reference |
| --- | --- | --- |
| Webhook | `sepay:wh:<id>` (integer, the same across retries and manual replays) | `referenceCode` (may be empty) |
| Transactions API v2 | `sepay:v2:<uuid>` | `reference_number` (may be empty) |

The **payment event id**, used by `mark_paid` (`paid_event_id`) and the receipt key, is chosen this way:
- **bank reference present:** `sepay:ref:<accountNumber>:<reference>`. The same transfer from either source, any
  number of times, is one event: a redelivery is `duplicate`, never a second payment;
- **bank reference empty:** the source id. A reference-less webhook and a reference-less feed row are **never**
  equated, by amount, order, time or anything else. The feed's eligibility rule (§6.3) keeps them from both applying,
  and a remaining collision is a reconciliation item.

Whether VietinBank always fills the reference, and whether it is identical in both sources, is checked in SePay test
mode before activation (§8). Until then the design does not rely on it: the reference-less path is the safe one.

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

### 4.1 Late payments (review Q5)

A static QR can be paid weeks later, after a price or promotion has changed. So for SePay:
- **within the order's `expires_at` plus the grace:** the order is paid and granted. `mark_paid` already accepts an
  `expired` / `cancelled` order;
- **after it:** nothing is granted. The money is recorded as a `payment_late` reconciliation item (order, amount,
  source ids, bank reference), and the operator refunds it or honours it by hand (an operator action with an audit
  row).

The grace is a policy, `billing.domestic_late_payment_grace_hours`, Admin-editable. **Its value is a human decision**
(not chosen here); until it is set, SePay checkout is not ready (`readiness` names `late_payment_grace_unset`). payOS
is unchanged: its link has its own expiry.

## 5. Gateway selection becomes data (G2)

- `_GATEWAY_RULES` gains `"sepay": ({"VND"}, False)`.
- The **active domestic gateway** is `BILLING_DOMESTIC_GATEWAY` (`payos` | `sepay`), and it must name a configured
  domestic gateway. **With `BILLING_ENABLED=on` it is required**: an unset value, or one naming an unconfigured gateway,
  makes the domestic side not ready (`domestic_gateway_unset` / `domestic_gateway_unconfigured`). A credential that
  appears or disappears never changes the gateway. Only in development and test (`APP_ENV` not production), and only
  when exactly one domestic gateway is configured, may it be inferred.
- Credit packs, `credit_offers`, the `credits:<pack>:<gateway>` key and the critical-reconciliation check use the
  active domestic gateway instead of the literal `"payos"`. An existing payOS deployment keeps working with
  `BILLING_DOMESTIC_GATEWAY=payos`, or with payOS as the only configured domestic gateway.
- The prices file may list `sepay` prices (VND, no external price id). Price integrity against the catalogue is
  unchanged.

## 6. Missed webhooks: the reconciler feed (G3)

A reconciler step, `sepay_feed`, runs when `SEPAY_API_TOKEN` is set. It is read-only towards SePay, never runs on
the learner path, and its failure never stops the tick's other steps (the existing per-step isolation).

### 6.1 Request

`GET {SEPAY_API_BASE}/transactions` with:
- `transfer_type=in`;
- `transaction_date_sort=asc`;
- `per_page=100`;
- the cursor (§6.2).

Rows are kept only for the configured `account_number`; every other row is skipped and still counts for cursor
advance. A `429` honours `Retry-After` and ends the step for this tick.

### 6.2 Cursor

`billing.sepay.feed_cursor` in `platform_settings`:
- `{since_id: <uuid> | null, backfill_from: <date> | null, updated_at}`;
- written only by the reconciler tick, under its advisory lock;
- updated with a compare-and-set on `updated_at`. A lost compare-and-set means another writer: the step stops and
  writes nothing.

| State | Query |
| --- | --- |
| **First run** (`since_id` null) | `transaction_date_from = backfill_from`. That is the oldest open SePay order's `created_at`, or the order-start date when none is open. |
| **Afterwards** | `since_id = <cursor>` only. `since_id` is the one authoritative cursor; there is no date overlap mixed into it. |

Each tick reads up to `N` pages (bounded, default 5). For each page, in the order returned:
1. **Settle delay.** Stop at the first row whose `transaction_date` is newer than `now - settle_delay`. The delay is
   45 min, longer than SePay's ~33-minute webhook retry window. The cursor is not advanced past it.
2. **Apply** each eligible row (§6.3) through `handle_fact`. Any row that raises stops the page **without** advancing
   the cursor; the next tick retries from the same cursor, and idempotency absorbs the rows already applied.
3. **Advance.** When every row up to the stop point is applied (or skipped), the cursor becomes the `id` of the last
   such row.

`has_more` continues on the next page within the tick, then the next tick.

The documentation does not say whether `since_id` is exclusive or what the default order is. Re-reading the cursor
row is a duplicate (safe). The order is verified in SePay test mode before activation: if the feed is not ascending
under `transaction_date_sort=asc` with `since_id`, the feed stays off.

### 6.3 Which feed rows are applied

A feed row is a **recovery** path only. It is applied when:
- `webhook_success` is `0` or `null` (SePay did not deliver the webhook successfully). Orena acknowledges only after
  durably recording the fact, so `1` means Orena already has it, and the row is skipped;
- it is past the settle delay (§6.2).

The applied row's payment event id follows §3.1. With a bank reference, a later manual replay of the webhook is a
`duplicate`. Without one, a later webhook (only a manual replay can arrive after the settle delay) for an order the
feed already paid is **not** a second payment and is **not** applied. It becomes a `payment_source_ambiguous`
reconciliation item (both source ids, amount, order) for the operator. The same holds the other way round. The
pre-check sits in the SePay path ahead of `record_payment`; `mark_paid` is unchanged.

### 6.4 Recovery outside the cursor

There is no automatic overlap sweep. A missed window, for example a token outage longer than retention, is recovered
in one of two ways:
- SePay's own Incidents → Replay (webhook path);
- an **operator-run backfill** by date range (`transaction_date_from` / `_to`) through the same §6.3 rules. It does
  not move the cursor.

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
- Idempotency:
  - webhook redelivery and manual replay;
  - the same transfer from webhook and feed with a bank reference: one credit and one grant;
  - without a reference: the feed skips `webhook_success = 1`, and a late replay becomes `payment_source_ambiguous`,
    never a second payment.
- Feed cursor:
  - advance only after a fully applied page;
  - stop at the settle delay;
  - a failure mid-page keeps the cursor;
  - a lost compare-and-set writes nothing;
  - a first-run backfill;
  - a 429 back-off;
  - rows for another account skipped but counted.
- Late payment: inside the grace it is paid; after it, `payment_late` and nothing granted; with the grace unset,
  checkout is not ready.
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

## 11. Review answers (revision 1 questions)

- **Q1:** approved. Orena builds the VietQR, with known-answer vectors and a real scan in test mode.
- **Q2:** approved. Single writer under the advisory lock, plus a compare-and-set.
- **Q3:** yes. The domestic gateway is required when billing is on; it is inferred only in development or test with
  one domestic gateway configured.
- **Q4:** approved.
- **Q5:** a bounded grace, then `payment_late`; the grace value is a human decision.

**Verified in SePay test mode before activation (H):** whether VietinBank fills the bank reference and whether it is
the same in both sources; the order of `since_id` and whether it is exclusive; `webhook_success` timing; a real scan of
the generated QR.

## Human gates

- SePay account, plan (STARTUP or above for volume), VietinBank linking, the payment-code prefix, the HMAC secret and
  the API token.
- The public URL for test mode, and the live small-value transfer.
- The late-payment grace (`billing.domestic_late_payment_grace_hours`).
- Production activation and every runtime migration.
