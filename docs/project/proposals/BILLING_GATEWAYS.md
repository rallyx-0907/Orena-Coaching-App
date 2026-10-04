# Billing: gateways, common layer, plans and quota (completion plan item 4) — proposal

Status: PROPOSED, built in isolated fixtures, **off**. Nothing takes money until the human passes the gates
listed at the end. Architecture: `docs/product/ORENA_COMMERCE_ARCHITECTURE.md` (§3 lifecycle, §5 order: "provider
integration in isolated fixtures" is this step).

## 1. Which gateways (research 2026-10-05, sources fetched that day)

| | Domestic: **payOS** (recommended) | Merchant of record: **Polar** (recommended) |
| --- | --- | --- |
| Who may sign up | an individual with a CCCD and a bank account in their own name; no business licence (payos.vn) | Vietnam is a supported country; payouts through Stripe Connect Express, which has an "individual" type (polar.sh/docs) |
| Payment | one-off VietQR link, paid straight into the linked bank account (Napas 24/7) | card checkout; Polar is the seller of record and handles sales tax |
| Recurring | **none**: Orena sells a prepaid month or year; renewal is a reminder and a new QR | native subscriptions (renew, cancel at period end, refunds) |
| Refund | **no refund API**: money goes back by bank transfer; an administrator records it in Orena | API and dashboard |
| Webhook proof | HMAC-SHA256 hex of the `data` object's sorted `key=value&...` with the Checksum Key | Standard Webhooks: `webhook-id`, `webhook-timestamp`, `webhook-signature` = base64 HMAC-SHA256 of `id.timestamp.body` |
| Fees | promo tier seen; general price list **unconfirmed** | about 4% + $0.40, **unconfirmed** |

Both signature schemes are implemented and **cross-checked against the official SDKs** (`payos` 1.1.0,
`standardwebhooks`) in a throwaway container: identical results.

Alternatives, if a condition fails: **SePay** (watches your own bank account; HMAC webhooks with timestamp) for
domestic; **Paddle** (best subscription API, Vietnam supported by omission only; likely wants a business) or
**Dodo Payments** for cards. **MoMo, VNPay, ZaloPay** need a business licence (GPKD); not for an individual.

### Business-registration conditions (the human checks; not legal advice)

1. **Legal status.** payOS and Polar accept an individual. MoMo, VNPay, ZaloPay and probably Paddle need a
   household business or a company, a tax code and a business bank account.
2. **Website notification.** Decree 52/2013, amended by Decree 85/2021, requires a selling website to be notified
   on online.gov.vn to the Ministry of Industry and Trade, and it applies to individuals too. The fine is 10–20
   million VND. Whether gateways ask for it at go-live is unconfirmed.
3. **Tax.** Ask an accountant about subscription revenue, foreign MoR payouts, and Decree 68/2026 reporting of
   business bank accounts and e-wallets.
4. **Published policies.** Terms, privacy and refund pages (item 5, at `/next#/legal/*`) plus contact details are
   reviewed by MoRs before approval.
5. **Confirm with the vendors.** payOS fees, Polar fees, and whether payOS sandbox needs verification first.

## 2. The common layer (built, `writing_coach/billing/`)

- `gateway.py`: what every adapter returns. `PaymentFact` is a verified event normalized to `subscription`,
  `payment`, `refund` or `ignored`. `Price` holds integer minor units and is never a float. `WebhookRejected`
  means 401 and nothing stored.
- `payos.py`, `polar.py`: each adapter verifies, normalizes and builds the checkout request. An adapter decides
  nothing about access.
- `service.py` (`BillingService`):
  - **Checkout** binds the signed-in account incarnation, an approved price and the client's operation id to a
    `billing_orders` row. A retry reuses the order; the same operation id with another price is a conflict. A
    return URL grants nothing.
  - **Merchant-of-record events** go to the commerce repository's `record_event()` with the subscription's own
    `modified_at` as its revision, as §3 requires. A first event attaches to an account only when Orena's own
    order for that account and operation exists. Signed metadata alone is not enough. After that, the stored
    provider-subscription mapping decides.
  - **Domestic payments**: the order is marked paid under the account's lock, after checking amount and currency
    against the order. A mismatch changes nothing and is logged. The account's prepaid state is then replayed
    from its orders. Each unrefunded paid order extends access from its own payment time, so periods are never
    lost. This state is recorded as subscription `prepaid:<incarnation>`, and its version is the count of paid
    orders plus refunds, so it only grows. A redelivery, a crash between the two writes, or an out-of-order
    apply resolves to `duplicate` or `stale`, or to the same state.
  - **Domestic refund**: an administrator records it (`POST /api/admin/billing/orders/{code}/refund`) after
    returning the money. Access is recomputed from the remaining orders.
- `billing_api.py`: `GET /api/billing/offers`, `POST /api/billing/checkout`, `POST /api/billing/webhooks/{gateway}`
  (256 KiB limit; no session, the signature is the proof) and the admin refund route. All are off unless
  `BILLING_ENABLED` is on with PostgreSQL and the account backbone.
- **Plans and prices** come from the JSON file named by `BILLING_PRICES_FILE`: `plan_id`, `period`, `currency`,
  `amount_minor`, `gateway`, and `external_price_id` for Polar. There is no default in code.
- **Cancel**: Polar cancels at period end through its customer portal or API. payOS has nothing to cancel:
  prepaid access simply ends.
- **Quota**: the plan entitlements (`product/catalog.py`, monthly limits per feature) and the quota buckets
  (migration 0007, deployed inactive) exist. Enforcement turns on with billing, per feature, across every entry
  path at once (§4). The AI cost record (AC-2) is the spend evidence behind those limits.

## 3. Schema (proposal, needs review and authorization)

`migrations/proposed/20261005_0027_billing_orders.py` creates one table, `billing_orders`, and an order-code
sequence. Money is stored as integer minor units. The table has unique `operation_id`, unique
`(gateway, external_reference)`, and unique `(incarnation, paid_sequence)`. RESTRICT on the incarnation, as
`commerce_subscriptions` does. It is parented on 0026, the AI cost record.

## 4. Pricing input: AI cost per feature

Measured costs come from the :8021 ledger (90 days, Gemini 3.5 flash-lite at $0.30/$2.50 per million tokens):

| Feature | Measured | Unit cost |
| --- | --- | --- |
| Orena turn round (`agent_turn_fast`) | 39 calls, ~3,078 in / 37 out tokens | **$0.0010** per round (a turn is 1–4 rounds) |
| Dictionary explanation | 14 calls, ~204 / 82 tokens | **$0.00027** per lookup |
| Reading generation (admin) | 10 calls | $0.0017 per call |

Writing review and improve have no :8021 sample yet. At about 3,000 in and 1,500 out tokens they would be
about **$0.0047** per call. Audio is priced at list rates: speech recognition is $0.04 per hour ($0.0007 per
minute), and pronunciation scoring is $1.32 per hour (**$0.022 per minute**, the most expensive unit).

A Premium learner who hits every current monthly limit (`catalog.py`) would cost:

| Use | Monthly cost |
| --- | --- |
| 500 reviews | $2.33 |
| 250 improvements | $1.16 |
| 2,000 lookups | $0.53 |
| 300 Orena turns of 2 rounds | $0.60 |
| 60 minutes of pronunciation scoring | $1.32 |
| 60 minutes of recognition | $0.04 |
| **Worst case** | **about $6 per month** |

Typical use is a fraction of that. Hosting is not measured (AC-4). Pronunciation minutes are the lever that
needs a limit of their own before pricing.

## 5. Test mode on :8000 (the human's steps, after the gates)

1. Create the payOS and Polar **sandbox** accounts and keys. Put them only in :8000's `.env`: `PAYOS_CLIENT_ID`,
   `PAYOS_API_KEY`, `PAYOS_CHECKSUM_KEY`, `POLAR_ACCESS_TOKEN`, `POLAR_WEBHOOK_SECRET`,
   `POLAR_ENVIRONMENT=sandbox`.
2. Write the prices file and set `BILLING_PRICES_FILE`. Set `ORENA_ACCOUNT_BACKBONE` on, if it is not already.
3. Promote migrations 0026 and 0027 after the rehearsal (`docs/operations/PRODUCT_8000_UPDATE.md`), then set
   `BILLING_ENABLED=1`.
4. In each gateway's dashboard, register the webhook URLs:
   - `https://<domain>/api/billing/webhooks/payos`
   - `https://<domain>/api/billing/webhooks/polar`
5. Pay one sandbox order of each kind. Check: Admin sees the order, the subscription turns active, a redelivery
   changes nothing, a Polar cancel ends access at period end, and a payOS refund record shortens it.

## 6. Independent review

Delegated Architecture Reviewer (an independent Claude agent, read-only), 2026-10-05, on codex/work `31a3dfb`
plus the uncommitted billing files: **APPROVE WITH CONDITIONS**. All conditions are met in the same change:

- **P1-1** The webhook path is public; it was behind the sign-in wall.
- **P1-2** Recording a refund again repairs a crash between the refund and the access record.
- **P1-3** One live subscription per account. A second checkout is refused (`subscription_live`), except
  renewing prepaid access with the same gateway. An undecided event is logged for an operator.
- **P1-4** A payment for a deleted account is recorded as paid and grants nothing
  (`paid_deleted_account`), with an error log so an operator refunds it.
- **P2-5** An order already started or closed never gets a second link.
- **P2-6** Periods are counted in UTC.
- **P2-7** A full refund ends access now.
- **P2-8** A malformed signature or timestamp is a rejection, not a crash.
- **P2-9** The payOS payment link must match the order.
- **P3, applied**: amounts are bounded; the body is streamed under a size limit; the handler runs off the event
  loop; the lock is `FOR NO KEY UPDATE`; prices are checked per gateway; the plan comes from Orena's own
  order; `period_end` is documented as an audit fact.

Tests: `tests/test_billing.py`, including the PostgreSQL proof of orders, prepaid access, refund repair and a
deleted account. Full suite: 4002 passed.

## 7. Gates (stop here)

- Choosing the gateways, and the legal status and registration conditions in §1.
- Creating the gateway accounts and keys.
- The prices file: plans, amounts and periods. Also the trial, grace, proration and refund policies the
  architecture §3 lists.
- Independent review of this slice (payment/entitlement, AGENTS.md §1), and authorization of migrations 0026 and
  0027.
- A learner screen for plans and checkout. The design draws none (UI_BACKEND_GAPS BL-1); it needs a design
  frame or the human's decision under D-128.
- Turning billing and quota enforcement on, on :8000.
