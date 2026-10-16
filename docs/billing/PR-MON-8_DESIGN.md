# PR-MON-8: SePay domestic gateway, Billing sandbox and E2E (design)

**Status: DESIGN APPROVED FOR IMPLEMENTATION: revision 5 at `c3af9154` + revision 6 delta at `1fe4568e`** (independent architecture delta re-review, P0 0 / P1 0 / blocking P2 0; the first delta review of `ab353b57` found 1 P1, fixed in `1fe4568e`). Implementation only; merge, activation, runtime migrations, tunnel/DNS and the live transfer remain gates. Revision 5 was APPROVED FOR IMPLEMENTATION at `c3af9154`; revision 6 changes only the persistence taxonomy of three reconciliation cases and states the grace sentinel (§0, revision 6). Revision 5's approval: Independent architecture review (the reviewer of the r3/r4 rounds, ChatGPT / GPT-5.6 Sol): P0 0, P1 0, blocking P2 0. It authorizes implementation only; merge, production activation, shared-runtime migration, the live transfer and any tunnel/DNS change remain separate gates. Revision 2 answered the review of revision 1 (`b01e2f5f`: 2 P1, Q1-Q5). Revision 3 answers the owner's review of revision 2 (`c5d2ed47`): the cursor loop, cancelled orders, the feed's fail-safe, secrets, the late-payment grace (1 hour) and the activation gates. Revision 4 answers the independent architecture review of revision 3 (`d4b66c01`, 1 P1): late-payment eligibility no longer depends on the expiry reconciler. Revision 5 answers the re-review of revision 4 (`b5248b69`, 1 P1): the SePay eligibility decision and the transition to `paid` happen atomically under the order's row lock. See §0. Billing / Commerce scope (D-MON-029). Base: `main` `d42c9261`. Input:
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

**Revision 3 (owner review of `c5d2ed47`):**

| Finding | Revision 3 |
| --- | --- |
| **P1, cursor loop.** Advancing `since_id` and then asking `page=2` can skip rows, because the set after the cursor has changed. | **§6.2:** always `page=1&since_id=<cursor>`. Process that one page in order, commit the cursor to its last handled row, then ask `page=1` again with the new cursor, until no rows remain or the tick limit is reached. `page` never increases. |
| **P1/P2, late payment for a closed order.** | **§4.1:** only an order that **expired by checkout timeout** may be paid inside the grace. `cancelled`, `refunded` (or any state an operator or the system ended on purpose) is never auto-granted: the transfer is recorded as a `payment_order_closed` item for the operator to refund or honour. There is no blanket "expired or cancelled + grace" rule. |
| **Cross-source dedupe** | Approved as in revision 2, on condition of real verification (§3.1, §12). |
| **Feed fail-safe.** `webhook_success = 1` must not be read as "Orena processed it" until proven. | **§6.3:** the feed ships **disabled** (`SEPAY_FEED_ENABLED` off). It is enabled only after test mode proves the cursor order and `webhook_success` semantics in the production configuration. A behaviour that differs keeps it off (fail closed). |
| **Secrets** | **§3.2**, a production gate. |
| **Gateway selection, VietQR** | Approved (§5, §4, §8). |
| **Grace: owner decision** | `billing.domestic_late_payment_grace_hours = 1`, an explicit configuration with no implicit default (§4.1). |
| **Activation gates** | **§12**, all thirteen. |

**Revision 4: independent architecture review of `d4b66c01`.** Reviewer: ChatGPT / GPT-5.6 Sol (independent
architecture review). Verdict: REQUEST CHANGES, 1 P1. The earlier P2 fixes were confirmed, and no new issue was found
in the cursor loop, cross-source dedupe, secrets or gates.

| Finding | Revision 4 |
| --- | --- |
| **P1: late-payment eligibility depended on the order's state being updated on time.** `created` / `pending` were paid unconditionally, and only `expired` compared against `expires_at` + grace. The expiry reconciler may run late, stop or be down, so an order past `expires_at` + 1 h could still read `pending`, and an old QR paid then would be granted on old terms. | **§4.1 rewritten.** First, closed states (`cancelled`, `refunded`, or ended on purpose) give `payment_order_closed`. Then, for every payable state (`created`, `pending`, timeout-`expired`), the transfer is compared directly: `transactionDate <= expires_at + grace` is paid; anything later is `payment_late`, **whatever the stored state**. Time eligibility is independent of whether the expiry reconciler has run. Tests are added for each case (§9). |

**Revision 5: independent architecture re-review of `b5248b69`.** Reviewer: ChatGPT / GPT-5.6 Sol. Verdict: REQUEST
CHANGES, 1 P1 (plus a P2 wording fix). The previous P1 was confirmed fixed, and nothing new was found in the cursor
loop, dedupe, feed gating, secrets or gates.

| Finding | Revision 5 |
| --- | --- |
| **P1, TOCTOU between the SePay pre-check and `mark_paid`.** The design checked duplicate, closed state and time in the SePay path *before* `record_payment`, in another transaction. Today's `mark_paid` takes its own lock and still accepts `cancelled`. An order read as `pending`, then cancelled by an operator before the lock, would be paid and granted. | **§4.2:** one locked repository operation, `mark_paid_domestic(..., policy=SePayPaymentPolicy)`, decides eligibility **and** makes the transition under the `billing_orders` row lock (and the account lock `mark_paid` already takes). It runs these steps in order: duplicate → deletion safety → current state → closed (`order_closed`, no mutation) → time against `expires_at + grace` read under the lock (`late`, no mutation) → `source_ambiguous` → amount, currency and reference → `paid`. There is no pre-check outside the lock. payOS keeps today's `mark_paid` unchanged. The service records `payment_order_closed` / `payment_late` / `payment_source_ambiguous` before the webhook is acknowledged. A real concurrency test is added (§9). |
| **P2** | The mapping test wording now reads "expired payment within grace (paid)". |

**Revision 6: targeted delta (owner decision, 2026-10-15).** Found while preparing the implementation: `ck_billing_item_kind` admits only the existing kinds, so the three new kind names of revisions 3-5 would be refused by the database. Revision 6 records the owner's choice (option a, no schema change):

1. `payment_order_closed`, `payment_late` and `payment_source_ambiguous` are removed as database kinds;
2. all three map to the existing `payment_not_payable`;
3. they are told apart by the stable `reason` values `order_closed`, `late_payment` and `source_ambiguous` (§4.3);
4. the test expectations are updated (§9);
5. the grace policy's default `0` is an UNCONFIGURED sentinel, not a real grace (§4.1);
6. "no schema change" still holds.

Payment behaviour, atomic locking, dedupe, the cursor, security and the activation gates are unchanged.

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

`PaymentFact`, `billing_orders`' schema and today's `mark_paid` (used by payOS) stay exactly as they are, as do
commerce access, the credit ledger and 0033's top-up source, reconciliation items, refunds and reversals, and
deleted-account obligations. The payOS and Polar adapters keep their behaviour. SePay payments go through one new
locked repository operation (§4.2) beside `mark_paid`, sharing its row and account locks, its deletion safety and its
amount/currency checks. No schema change is proposed (§6).

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
| `SEPAY_FEED_ENABLED` | turns the feed on; off by default, and required together with the token (§6.3) |
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

### 3.2 Secrets (production gate)

`SEPAY_API_TOKEN` has the largest blast radius, and `SEPAY_WEBHOOK_SECRET` is handled the same way:
- held server-side only: never sent to the frontend, never in a response, readiness or report (only `configured:
  true/false`);
- never logged. The `Authorization` header and the token are excluded from every log and error message, and the
  feed's HTTP errors carry the status code only;
- never committed (`.env` is git-ignored; `.env.example` lists names only);
- **separate credentials** for sandbox/test mode and production;
- a token **dedicated to Orena production**, so it can be revoked on its own;
- if SePay offers an IP allowlist for the webhook or the API, it is enabled **in addition to** HMAC, never instead of
  it.

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

### 4.1 Late payments (review Q5, owner decision)

A static QR can be paid long after checkout, after a price or promotion has changed. For SePay, the decision is
made **inside the locked payment operation of §4.2**, in this order, never in a separate pre-check. payOS keeps today's
`mark_paid`.

1. **A repeat of a payment already recorded.** The order is `paid` by this payment event: `duplicate`, as today. The
   order is `paid` by another event: as today, plus the §6.3 `source_ambiguous` rule.
2. **A closed order.** The order is `cancelled`, `refunded`, or in any state an operator or the system ended on
   purpose: `payment_not_payable` reconciliation item with `reason = order_closed`. Never auto-granted, whatever the time.
3. **A payable order** (`created`, `pending`, or `expired` by checkout timeout). Compare the transfer directly with the
   order:

   | Transfer time (`transactionDate`) | Result, **whatever the stored state** |
   | --- | --- |
   | `<= expires_at + grace` | Paid and granted. |
   | `> expires_at + grace` | `payment_not_payable` reconciliation item with `reason = late_payment`. The money is recorded, nothing is granted, and the operator refunds or honours it by hand. |

   **Time eligibility never depends on whether the expiry reconciler has already moved the order to `expired`.** A
   `pending` order past `expires_at` + grace is late, exactly as an `expired` one is.
4. **Fail closed.** An order with no `expires_at`, an unreadable or unset grace when the payment arrives, or an
   unparseable `transactionDate` all produce `payment_not_payable` with `reason = late_payment`: recorded, nothing
   granted, and the operator decides.

"Within the grace" is judged on the transfer's own `transactionDate` (Vietnam time, converted to UTC), not on Orena's
arrival time. A delayed webhook therefore does not turn an on-time transfer into a late one.

**Grace (owner decision):** `billing.domestic_late_payment_grace_hours`, operated at `1`, set explicitly on each
runtime. It is an Admin-editable policy. Because the policy framework requires a default, the default is **`0`, an
internal sentinel meaning UNCONFIGURED** (revision 6):
- `0` (or any value `<= 0`) is **not** a grace of zero hours and is never a valid grace;
- SePay checkout is not ready, and readiness names `late_payment_grace_unset`;
- a payment arriving in this state fails closed: `payment_not_payable` with `reason = late_payment`, nothing granted;
- a valid operating value is `>= 1`.

There is no implicit grace that can grant access. The value may be tuned later from real data. payOS is unchanged:
its link has its own expiry.

### 4.2 One locked operation decides and transitions (review P1, TOCTOU)

`BillingOrderRepository.mark_paid_domestic(order_code, event_id, amount_minor, currency, transaction_at, policy, now)`
runs in **one transaction**. It takes the same locks as `mark_paid`: the account incarnation `FOR NO KEY UPDATE`,
then the `billing_orders` row `FOR UPDATE`. Every step reads the order **under that lock**:

1. **Idempotency.** `paid_event_id == event_id` gives `duplicate` (no mutation).
2. **Deletion safety.** The existing `paid_deleted_account` rule, unchanged.
3. **Current state**, as locked.
4. **Closed** (`cancelled`, `refunded`, or any state ended on purpose) gives `order_closed`. No mutation.
5. **Payable** (`created`, `pending`, timeout-`expired`): `transaction_at <= locked expires_at + policy.grace`.
   Otherwise, or with a missing `expires_at`, grace or `transaction_at`, it gives `late`. No mutation.
6. **Already paid by another event** without a shared bank reference gives `source_ambiguous`. No mutation.
7. **Amount and currency** exact, else `mismatch` (no mutation), as today.
8. Only then the transition to `paid` (`paid_event_id`, `paid_at`, `paid_sequence`), exactly as `mark_paid` writes it.

The grace is read once by the service and passed in as `policy`. An unset grace is refused before the call (`late`).
The time comparison uses the `expires_at` read under the lock, never a snapshot taken earlier.

`BillingService` records each of `order_closed` / `late` / `source_ambiguous` as **one existing reconciliation
kind**, `payment_not_payable`, with the stable `reason` of §4.3. It records them **before** the webhook route returns
`ack()`. If
recording fails, the route answers 503 and SePay retries. A transition to `paid` continues to the grant or top-up as
`record_payment` does today.

`mark_paid` itself, and so payOS, is not changed. Its acceptance of `cancelled` remains a payOS behaviour outside this
PR's scope, recorded as residual risk RR-8.1.

### 4.3 Persistence taxonomy: one existing kind, stable reasons (revision 6)

`billing_reconciliation_items.kind` is constrained in the database (`ck_billing_item_kind`, 0031 / 0032). The three
SePay cases therefore use the **existing** kind `payment_not_payable`, so there is **no schema change and no
migration**:

| Locked outcome (§4.2) | `kind` | `reason` (machine-stable constant) |
| --- | --- | --- |
| `order_closed` | `payment_not_payable` | `order_closed` |
| `late` | `payment_not_payable` | `late_payment` |
| `source_ambiguous` | `payment_not_payable` | `source_ambiguous` |

- What is persisted, exactly the columns the existing `billing_reconciliation_items` schema has (no schema change):

  | Column | Value |
  | --- | --- |
  | `kind` | `payment_not_payable` |
  | `reason` | the stable constant |
  | `dedupe_key` | the payment event id of the event being processed (§3.1) |
  | `external_event_id` | the source event id (`sepay:wh:<id>` or `sepay:v2:<uuid>`) |
  | `reported_order_code`, `reported_amount_minor`, `reported_currency` | as reported |
  | `provider_state` | as reported |
  | `payload_digest` | the webhook body's digest (for the feed, the row's digest) |
  | `billing_order_id`, `incarnation_id` | when known |

- **Bank reference.** It has no column of its own. When one exists, the payment event id is
  `sepay:ref:<account>:<reference>`, so the reference is preserved through `dedupe_key`.
- **Transaction time.** `transaction_at` is parsed and used inside `mark_paid_domestic` for the locked late-payment
  decision. It is **not** stored in `billing_reconciliation_items`; the operator finds the provider transaction by
  `external_event_id`.
- A locally persisted bank transaction timestamp or bank-reference column, if Orena ever needs one for audit, is a
  separate schema proposal with its own migration review, outside PR-MON-8.
- The three `reason` values are code constants. Business logic branches on the locked outcome and on these constants,
  never on free text.
- Admin may show a friendly label from `reason`; the database kind stays `payment_not_payable`.
- The financial behaviour is unchanged:
  - `order_closed` and `late_payment`: the order is not moved to `paid`, and there is no grant and no top-up;
  - `source_ambiguous`: no second payment, no grant, no top-up;
  - the item is durable before `ack()`, and a failed write answers 503 so SePay retries;
  - the operator then refunds, matches or waives through the existing reconciliation workflow.

The names `payment_order_closed`, `payment_late` and `payment_source_ambiguous` in §0's history rows are superseded:
they are not database kinds.

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

A reconciler step, `sepay_feed`, runs only when `SEPAY_API_TOKEN` is configured **and** `SEPAY_FEED_ENABLED` is true. A token alone never starts the feed (§6.3). It is read-only towards SePay, never runs on
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

**The loop.** Each tick runs up to `N` iterations (bounded, default 5):
1. ask `page=1` with the current cursor (`since_id`, or `transaction_date_from` on the first run);
2. handle that page's rows in order, as below;
3. commit the cursor (compare-and-set) to the `id` of the last row handled;
4. repeat from step 1 with the new cursor.

It stops when the page is empty, when the settle delay is reached, or at `N`. **`page` never increases.** Asking
`page=2` after the cursor moved could skip rows, because the set after `since_id` has changed.

Within one page, in the order returned:
1. **Settle delay.** Stop at the first row whose `transaction_date` is newer than `now - settle_delay`. The delay is
   45 min, longer than SePay's ~33-minute webhook retry window. The cursor is not advanced past it.
2. **Apply** each eligible row (§6.3) through `handle_fact`. Any row that raises stops the page **without** advancing
   the cursor; the next tick retries from the same cursor, and idempotency absorbs the rows already applied.
3. **Advance.** When every row up to the stop point is applied (or skipped), the cursor becomes the `id` of the last
   such row.

SePay documents `since_id` as cursor-based polling that returns the transactions created after the given id.
Implementation still verifies the real behaviour in test mode before activation: the order under
`transaction_date_sort=asc`, and whether the boundary row is excluded. A re-read boundary row is a duplicate (safe).
If the real behaviour differs from these assumptions, the feed fails closed and stays disabled (§6.3).

### 6.3 Which feed rows are applied

A feed row is a **recovery** path only, never a parallel payment source.

**Shipped disabled.** `SEPAY_FEED_ENABLED` is off by default. It is turned on only after SePay test mode, in the
production configuration (one webhook, Orena's endpoint), proves both:
- the cursor behaviour of §6.2;
- what `webhook_success` means: when it becomes `1`, and how it behaves with several webhooks or configurations.

Until then, `webhook_success = 1` is **not** read as "Orena processed this transaction". With the feed off, missed
webhooks are recovered by SePay's Incidents → Replay and the operator backfill (§6.4).

When enabled, a row is applied only when:
- `webhook_success` is `0` or `null`. This skip is valid only because the semantics were proven; if a later SePay
  change breaks it, the feed is turned off again;
- it is past the settle delay (§6.2).

The applied row's payment event id follows §3.1. With a bank reference, a later manual replay of the webhook is a
`duplicate`. Without one, a later webhook (only a manual replay can arrive after the settle delay) for an order the
feed already paid is **not** a second payment and is **not** applied. It becomes a `payment_not_payable`
(`reason = source_ambiguous`) reconciliation item for the operator. It holds this event's source id in
`external_event_id`; the order's existing `paid_event_id` names the other. The same holds the other way round. This
decision is step 6 of the locked operation (§4.2), not a pre-check.

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
  amount (`mismatch`), unknown order, a second payment of a paid order (`not_payable`), an expired payment within grace (paid), a deleted account (`paid_deleted_account`).
- Idempotency:
  - webhook redelivery and manual replay;
  - the same transfer from webhook and feed with a bank reference: one credit and one grant;
  - without a reference: the feed skips `webhook_success = 1`, and a late replay becomes `payment_not_payable`
    (`reason = source_ambiguous`),
    never a second payment.
- Feed cursor:
  - advance only after a fully applied page;
  - stop at the settle delay;
  - a failure mid-page keeps the cursor;
  - a lost compare-and-set writes nothing;
  - a first-run backfill;
  - a 429 back-off;
  - rows for another account skipped but counted.
- Late payment:
  - `pending` with `transactionDate > expires_at + grace`: `payment_not_payable` / `late_payment`, nothing granted;
  - `created` with `transactionDate > expires_at + grace`: `payment_not_payable` / `late_payment`, nothing granted;
  - `pending`, webhook arriving late, `transactionDate <= expires_at + grace`: paid and granted;
  - `expired` by timeout with the transfer inside the grace: paid and granted;
  - `expired` with the transfer after the grace: `payment_not_payable` / `late_payment`;
  - `cancelled` / `refunded`: always `payment_not_payable` / `order_closed`, inside or outside the grace;
  - no `expires_at`, the grace unset (`<= 0`) when the payment arrives, or an unparseable `transactionDate`:
    `payment_not_payable` / `late_payment`;
  - the grace judged on `transactionDate`;
  - grace unset: checkout not ready.
- Cursor loop:
  - always `page=1` with the committed cursor; `page` never increases;
  - more rows than one page are processed across iterations without a skip;
  - feed disabled by default: a token present with `SEPAY_FEED_ENABLED` absent or false never runs the feed.
- Secrets: no token or `Authorization` in logs, errors, readiness or reports.
- **Concurrency (PostgreSQL, a real race), review P1:**
  - a SePay payment starts while the order is `pending`, and pauses just before the locked operation takes the row
    lock (a test hook);
  - a second transaction moves the order to `cancelled` and commits;
  - the payment resumes;
  - the result is `payment_not_payable` with `reason = order_closed`, the order is not `paid`, there is no plan grant and no credit top-up.
- **Locked snapshot:** a second transaction changes `expires_at` (or expires the order) between the service's read and
  the locked operation. The grace decision follows the value read under the lock, never the earlier snapshot.
- **Recorded before acknowledging:** when recording the item fails, the webhook answers 503 and no `ack()` is sent.
- **Item contents (revision 6):** every SePay item asserts exactly the supported columns: `kind =
  payment_not_payable`, the correct stable `reason`, `dedupe_key` = the payment event id (`sepay:ref:...` when a bank
  reference exists), `external_event_id` = the source id, order code, amount, currency, provider state, payload digest,
  and order/incarnation when known. No test asserts a transaction-time or bank-reference column.
- **The late decision uses the provider time:** a separate test proves the locked late decision compares the provider's
  `transaction_at` (not the arrival time) with the locked `expires_at` + grace.
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
- **Q5:** a bounded grace, then `payment_not_payable` / `late_payment`; the owner decided the grace: 1 hour (§4.1).

**Verified in SePay test mode before activation (H):** whether VietinBank fills the bank reference and whether it is
the same in both sources; the order of `since_id` and whether it is exclusive; `webhook_success` timing; a real scan of
the generated QR.

## 11a. Residual risks

- **RR-8.1.** Today's `mark_paid` (payOS) still accepts a `cancelled` order. That is outside PR-MON-8's scope, and
  SePay does not use it. It is recorded here so a later payOS review can decide it.

## 12. Activation gates (owner, all required)

Production stays off until every one of these passes:
1. Independent review of revision 5 (APPROVED at `c3af9154`) and of the revision 6 delta: APPROVED.
2. Hermetic tests pass.
3. PostgreSQL integration tests pass.
4. SePay test mode passes.
5. The real cursor behaviour is verified.
6. The real bank-reference behaviour is verified (always present? `referenceCode` = `reference_number`?).
7. The `webhook_success` behaviour is verified.
8. The generated QR scans correctly in a banking app.
9. One live small-value transfer E2E passes, then is refunded by the operator: QR -> VietinBank -> SePay -> signed
   webhook -> Orena -> order paid -> grant/top-up exactly once.
10. Exactly-once grant/top-up is proven.
11. Secret and configuration readiness passes (§3.2, §4.1, §5).
12. The runtime migration is approved by the operator.
13. Production activation, as its own human gate.

An approved design authorizes implementation only, never a merge or an activation.

## Human gates

- SePay account, plan (STARTUP or above for volume), VietinBank linking, the payment-code prefix, the HMAC secret and
  the API token.
- The public URL for test mode, and the live small-value transfer.
- The late-payment grace: decided as 1 hour, to be configured explicitly on each runtime.
- Production activation and every runtime migration.
