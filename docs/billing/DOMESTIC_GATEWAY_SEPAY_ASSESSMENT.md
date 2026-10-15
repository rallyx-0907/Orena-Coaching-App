# Domestic gateway: SePay + VietinBank assessment (PR-MON-8 input)

**Status: ASSESSMENT.** It records the owner's decision (D-MON-024) and the adapter contract PR-MON-8 must build. No
code, no credentials, nothing enabled. Final provider activation is a human gate. SePay is **not** approved for
production by this document.

Researched 2026-10-15 from SePay's public developer documentation (sources at the end). Every number SePay publishes
can change, so PR-MON-8 re-checks each one against the live portal before relying on it.

## 1. The decision (D-MON-024)

- **The owner's bank accounts are not supported by payOS.** payOS is therefore no longer the preferred production
  domestic gateway.
- **The payOS adapter stays.** `writing_coach/billing/payos.py` and everything built on it in PR-MON-3/5 remain in the
  repository as an existing adapter. Nothing is removed.
- **Primary candidate:** SePay + VietinBank (personal account).
- **Existing alternative:** payOS. payOS is a product of the Casso ecosystem, not a provider separate from Casso. It
  is used only if the owner later has a bank and account path payOS supports.
- **No separate Casso fallback.** No "Casso + VietinBank" fallback, and no `CassoGateway`, is recorded or planned. A
  genuinely separate Casso product or API that supports VietinBank through a different integration path would first
  be documented as research evidence, then reviewed, before anything is built (correction by the owner,
  2026-10-15).
- **International:** unchanged. Polar stays; PayPal may be evaluated later, outside this work.
- **Ownership of the switch.** Replacing the domestic gateway belongs to PR-MON-8 (Billing runtime / E2E). PR-MON-6
  continues unchanged.

## 2. What SePay is, and what it is not

**SePay does not move money.** It observes the owner's own bank account:
1. the learner transfers to the owner's VietinBank account, usually by scanning a VietQR code;
2. VietinBank books the credit;
3. SePay learns of it, through API banking with VietinBank or through SMS banking;
4. SePay posts a webhook to Orena.

So:
- there is no hosted checkout, no payment link and no SePay-held balance;
- there is no settlement delay or payout from SePay;
- **SePay cannot refund a personal account.** Its refund API exists only for VietinBank *enterprise* accounts. A
  refund is the operator's own outgoing bank transfer. That matches PR-MON-5's operator-recorded refund
  (`refunded_by = 'operator'`) and K2, a full refund or none.

## 3. Facts the adapter depends on

| Topic | SePay behaviour | Orena consequence |
| --- | --- | --- |
| **Webhook authentication** | HMAC-SHA256 (SePay's recommendation). Header `X-SePay-Signature: sha256=<hex>` over `"{X-SePay-Timestamp}.{raw body}"`, keyed with a secret shown once. API-key and OAuth2 modes also exist. | Use HMAC only. Verify against the raw bytes with a constant-time compare, and reject a timestamp more than 300 s from server time. The API-key mode authenticates the sender but not the body, so it is not accepted. |
| **Payload** | JSON: `id` (integer, stable across retries and replays), `gateway` (bank name), `transactionDate` (`YYYY-MM-DD HH:mm:ss`, Vietnam time), `accountNumber`, `code` (payment code parsed from the memo by the configured prefix; `null` when none matches), `content` (raw memo), `transferType` (`in` / `out`), `transferAmount` (positive integer VND), `accumulated`, `subAccount`, `referenceCode`, `description`. | See the field-to-fact mapping in §4. |
| **Transaction identifier** | `id`, SePay's own id. The bank's `referenceCode` can be empty. | `PaymentFact.event_id = "sepay:" + id`. `referenceCode` is kept as an extra for audit only. |
| **Amount and currency** | `transferAmount` is always VND and always positive. There is no currency field. | `amount_minor = transferAmount`, `currency = "VND"`, fixed by the adapter. The existing rule stays: the amount must equal the server-side order exactly, or the payment becomes `payment_mismatch`. |
| **Matching a transfer to an order** | `code` comes from the memo by a prefix the owner configures (Company → General settings → payment code structure). A VietinBank personal account linked through API banking needs every payment memo to begin with `SEVQR`. | The checkout puts `SEVQR <PREFIX><order_code>` in the VietQR `addInfo`, so `code` = `<PREFIX><order_code>` and maps to exactly one `billing_orders.order_code`. A `null` code, an unknown order or a second match becomes `payment_unknown_order`; an order that is not payable becomes `payment_not_payable`. None of these is guessed. |
| **Response SePay requires** | HTTP 200 or 201 with the body exactly `{"success": true}`, within 30 s. Anything else counts as a failure. | Gap G4: the webhook route must answer in each gateway's own success shape. |
| **Retries** | 8 attempts (the first plus 7 retries) over about 33 minutes, Fibonacci-spaced. The owner can also replay manually, even a log that already succeeded. A delivery can repeat. | Idempotent per `id`, through the existing receipt and the unique order fulfillment. A redelivery is a duplicate and never credits twice. |
| **Missed webhook** | After the retry window, SePay offers Monitoring → Incidents → Replay (manual), plus the transactions API: v2 `https://userapi.sepay.vn/v2` with Bearer API token, transaction list and detail, filters by date, account and amount, `page`/`per_page` up to 100. | The PR-MON-8 reconciler pulls the transaction feed since a cursor and passes every incoming transaction through the same normalize-and-apply path. See gap G3. |
| **Rate limits** | v2: 3 requests/s per IP, then HTTP 429 with `Retry-After`. Legacy v1: 2–3 requests/s (the pages disagree). | The reconciler pulls one page per tick and backs off on 429. Lookups are never made on the learner path. |
| **Test environment** | Sandbox API (`userapi-sandbox.sepay.vn/v2`), webhook test mode (a webhook can be created and fired in test mode) and a "Compare Test mode with Live" page. | E2E in test mode first. Then one live small-value transfer on the owner's real account, as a human-gated step. |
| **VietinBank personal** | Linked in my.sepay.vn → Ngân hàng → VietinBank (Cá nhân): account number, holder name, ID card number and phone, confirmed by OTP. API banking or SMS banking (SMS needs a supporting plan). Incoming and outgoing transactions both arrive by default. | Filter on `transferType = 'in'` and on the configured receiving `accountNumber`. The `SEVQR` memo rule is mandatory. SePay's VietinBank refund and order-VA features are enterprise-only and are not used. |
| **Fees** | Plans are priced by transaction count, not by a percentage of money received. FREE: 0 đ, 50 transactions a month. STARTUP: from 120,000 đ a month, tiered. SHOP has no API. Prices exclude 8% VAT. Bank transfer fees, if any, are the bank's. | Commercial choice for the owner (a human gate). STARTUP or above is needed for volume. Fees never change Orena's price, which comes from the catalogue. |

## 4. Fit with the current abstraction

The core path stays:

```
BillingService -> PaymentFact (normalized) -> billing_orders state -> commerce access | credit_ledger top-up
```

No SePay field reaches the core credit logic. A `SePayGateway` maps an incoming transaction to the existing
`PaymentFact(kind="payment")`:

| `PaymentFact` field | Source |
| --- | --- |
| `gateway` | `"sepay"` |
| `event_id` | `"sepay:<id>"` |
| `external_reference` | the order code parsed from `code` (None when there is no code) |
| `amount_minor` | `transferAmount` |
| `currency` | `"VND"` |
| `provider_state` | `"paid"` |
| `payload_digest` | `digest(body)` |
| `extra` | `account_number`, `bank_reference`, `transaction_date` (audit only, never decisions) |

These cases become `kind="ignored"`:
- an outgoing transfer (`transferType = 'out'`);
- a transfer to another account the owner linked.

The money-side invariants are unchanged and mandatory:
- **No browser proof.** The browser or return URL never proves a payment; only the verified webhook or the pulled
  provider transaction does.
- **Exact match.** The amount and currency equal the order exactly.
- **Idempotent.** A redelivery changes nothing, and one payment never credits twice.
- **Unmatched or ambiguous payments** become reconciliation items.
- **Deleted-account obligations** stay durable.
- **Refunds and reversals** keep PR-MON-5's semantics.

### Compatibility gaps

| # | Gap | Where | Size |
| --- | --- | --- | --- |
| G1 | **Checkout has no provider call.** `_open_domestic_link` sends payOS's `checkout_request` and parses payOS's `checkoutUrl` / `qrCode` / `paymentLinkId`. SePay needs Orena to build the VietQR itself: VietinBank BIN 970415, account number, the exact amount, and `addInfo = "SEVQR <PREFIX><order_code>"`. | `service.py` `_open_domestic_link`; the `Gateway` protocol | A gateway method that returns a `CheckoutStart` (`qr_payload` already exists), with payOS's network call moved behind it. |
| G2 | **The domestic gateway is hard-coded to payOS.** `_GATEWAY_RULES` lists only `payos` (VND); credit packs require `gateway == "payos"`; `credit_offers` requires `"payos"` in the gateways; the description prefix is `OR<code>`. | `service.py` | Make it data: the domestic gateway is whichever configured gateway has `kind == "domestic"`, with its currency rules on the adapter. |
| G3 | **Reconciliation lookup is per order.** The reconciler's `_pull` asks payOS for one order's state (`lookup_request(order_code)`). SePay offers a transaction *feed* (list since a date or cursor), not an order lookup. | `reconciler.py` `build_lookups` / `_pull` | A feed step: scan new incoming transactions since a stored cursor, and normalize each through the adapter into the same fact path. The cursor needs durable storage (a reviewed migration or a platform setting; decided in PR-MON-8). |
| G4 | **Webhook acknowledgement shape.** The route answers `{"ok": true}`; SePay counts only `{"success": true}` with 200/201 as delivered. | `billing_api.py` `billing_webhook` | An acknowledgement body per gateway, from the adapter. |
| G5 | **The credit top-up source names the gateway.** `billing_order / <gateway>:<code>` is already generic in SQL (`o.gateway || ':' || o.order_code`), and the 0033 trigger reads the gateway from the source. | none | Already generic. A test with `sepay:<code>` is enough. |
| G6 | **No provider refund event.** A refund is the operator's own transfer. | none | It fits the existing operator-recorded refund. Outgoing transfers are ignored, not matched. |

None of these touches PR-MON-6, the ledger, funding admissions or 0034. Each change sits behind the adapter or in
`BillingService`'s gateway selection.

## 5. Proposed PR-MON-8 work, domestic part

1. **`SePayGateway`** (`writing_coach/billing/sepay.py`), `kind = "domestic"`, from the environment.
   - Variable names only; values are a human gate: `SEPAY_WEBHOOK_SECRET`, `SEPAY_ACCOUNT_NUMBER`,
     `SEPAY_BANK_BIN`, `SEPAY_ACCOUNT_NAME`, `SEPAY_PAYMENT_PREFIX`, `SEPAY_API_TOKEN` (the reconciliation feed
     only), `SEPAY_API_BASE`.
   - `verify()`: HMAC, timestamp window, raw body, then the normalized `PaymentFact`.
   - A VietQR builder for checkout (G1).
   - `ack()`: `{"success": true}` (G4).
   - The feed reader (G3).
2. **Gateway selection made data (G2).** Domestic currency rules and pack gateway come from the configured domestic
   adapter. payOS keeps working unchanged when it is the configured one.
3. **Reconciler feed step (G3)**, with a durable cursor. Unmatched transactions become reconciliation items.
4. **Tests:**
   - signature, timestamp, tamper and replay;
   - mapping, including `null` code, outgoing, wrong account, wrong amount, unknown order, late payment and double
     payment;
   - exact-once credit through the existing top-up path with `sepay:<code>`;
   - a missed webhook recovered by the feed;
   - redelivery and manual replay idempotent.
5. **E2E** on the separate Billing sandbox (`:8031` if free):

   ```
   learner transfer -> VietinBank -> SePay detects it -> signed webhook -> Orena matches the order
     -> exact amount and order -> paid -> credit top-up exactly once
   ```

   First in SePay test mode, then one live small-value transfer as a human-gated step.
6. **Runbook:** the owner's SePay setup, payment-code prefix, HMAC secret rotation, the webhook URL and the
   "Incidents → Replay" procedure.
7. **No Casso adapter.** payOS (Casso ecosystem) remains the existing alternative adapter, untouched. Any other
   provider is research evidence first, review second.

## 6. Is code needed before PR-MON-8?

**No.** The normalized `PaymentFact` already carries everything a SePay payment needs, and gaps G1–G4 are confined to
the adapter and to `BillingService`'s gateway selection. Building them now would add an unreviewed, inactive payment
path ahead of PR-MON-8's E2E and the human gates. The domestic gateway stays switched off, as today (`BILLING_ENABLED`
off; no credentials configured).

## Sources

- [SePay webhooks: overview](https://developer.sepay.vn/en/sepay-webhooks)
- [Integrate webhook: payload, response, idempotency](https://developer.sepay.vn/en/sepay-webhooks/tich-hop-webhook)
- [Webhook authentication: HMAC, API key, OAuth2](https://developer.sepay.vn/en/sepay-webhooks/xac-thuc)
- [Webhook error handling: retries, replay](https://developer.sepay.vn/en/sepay-webhooks/xu-ly-loi)
- [Webhook test mode](https://developer.sepay.vn/en/tien-ich-khac/test-mode/tao-webhook)
- [SePay API v2 overview](https://developer.sepay.vn/en/sepay-api/v2/gioi-thieu) and
  [v2 authentication and rate limits](https://developer.sepay.vn/en/sepay-api/v2/xac-thuc)
- [Legacy transactions API (v1)](https://docs.sepay.vn/api-giao-dich.html)
- [Connecting a VietinBank personal account](https://docs.sepay.vn/ket-noi-vietinbank.html)
- [SePay pricing](https://sepay.vn/bang-gia.html)
- [SePay Bank Hub overview](https://developer.sepay.vn/en/bankhub/tong-quan)
