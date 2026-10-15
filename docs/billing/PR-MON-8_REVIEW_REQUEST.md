# PR-MON-8: SePay domestic gateway (implementation review request)

**Status: IMPLEMENTING, for independent implementation review.** It implements design revision 5 (approved at
`c3af9154`) plus the revision 6 delta (approved at `1fe4568e`), in `PR-MON-8_DESIGN.md`. Nothing is enabled:
- `BILLING_ENABLED` stays off;
- no SePay credential is configured;
- the feed is off;
- there is no schema change or migration;
- the shared runtimes, tunnel/DNS and the live transfer are untouched.

Merge and every activation gate (design §12) remain separate.

## What changed

| File | Change |
| --- | --- |
| `writing_coach/billing/sepay.py` (new) | `SePayGateway`. **Webhook:** HMAC over `{ts}.{raw body}`, 300 s window, constant-time compare, all before parsing. **Normalization (§3):** outgoing transfers and other accounts are ignored; a missing or foreign code is a payment with no order. **Identity (§3.1):** source ids `sepay:wh:<int>` / `sepay:v2:<uuid>`; the payment event id is `sepay:ref:<account>:<reference>` when there is a reference. **Checkout:** server-built VietQR (EMVCo, CRC-16/CCITT-FALSE, `SEVQR <PREFIX><code>`, 25-character cap). **Ack:** `{"success": true}`. **Secrets:** a `repr` without them. **Feed:** request (always `page=1`) and row parsing. |
| `writing_coach/persistence/billing_repository.py` | `mark_paid_domestic`: one transaction under the incarnation `FOR NO KEY UPDATE` and the order `FOR UPDATE`. Steps 1-8 of §4.2 run on the locked row; `transaction_at` is compared with the locked `expires_at` + grace. Also `mark_started` (pending, no link), `oldest_open_created_at`, and a test-only `pause_before_lock` hook. `mark_paid` (payOS) is unchanged. |
| `writing_coach/billing/service.py` | **Gateway selection:** `sepay` in the gateway rules. `domestic_state` / `active_domestic` / `domestic_blockers` (§5): explicit `BILLING_DOMESTIC_GATEWAY`, inferred only outside production with one domestic gateway. Offers, credit packs and checkout go only through the active domestic gateway. **Grace:** `late_payment_grace()` treats `<= 0` or an unreadable value as unconfigured. **Payment path:** `_domestic_payment` records `order_closed` / `late` / `source_ambiguous` as `payment_not_payable` with the stable reasons `order_closed` / `late_payment` / `source_ambiguous`, using only the supported columns, before returning. `handle_fact` is the feed's entry to the same path. **Checkout:** a SePay checkout returns the QR and the transfer fields, with no provider call. |
| `writing_coach/billing/sepay_feed.py` (new) | **Gating:** runs only with token **and** `SEPAY_FEED_ENABLED`. **Loop:** `page=1&since_id` with a 45-minute settle delay and a compare-and-set cursor in `platform_settings` (`billing.sepay.feed_cursor`); the cursor advances only after the rows are handled; the first run backfills from the oldest open order; a 429 or a lost compare-and-set stops the step. **Errors:** by status only. |
| `writing_coach/billing/reconciler.py`, `app.py` | The feed step is added only when enabled. The service is built with the domestic choice and the production flag. |
| `writing_coach/billing_api.py` | The webhook answers in the gateway's own success shape. A failed item write still answers 503 (unchanged path). |
| `writing_coach/billing/readiness.py` | Blockers `domestic_gateway_unset` / `domestic_gateway_unconfigured` / `late_payment_grace_unset`. |
| `writing_coach/policies.py`, Admin copy/page/gate | Policy `billing.domestic_late_payment_grace_hours`: int, hours, default `0` = UNCONFIGURED, range 0-168, confirmation required (charging). Group `billing`, with EN/VI/ZH copy. |
| `.env.example` | Billing, payOS, Polar and SePay variable **names** (gap 7). |

## Evidence (local, not CI)

- **`tests/test_billing_sepay.py`** (56, hermetic):
  - signature cases, and the ±300 s boundary;
  - normalization and identity;
  - webhook and feed agree with a bank reference, and never without one;
  - CRC check value 0x29B1 and VietQR field structure;
  - bad input refused;
  - feed needs token and switch, and a token alone adds no reconciler step;
  - no secret in a `repr`, error or log;
  - explicit domestic selection, and the grace sentinel;
  - each locked refusal is `payment_not_payable` with its stable reason and only the supported columns, and no
    bank-reference or time column;
  - the late decision is given the provider's `transaction_at` (not the arrival time);
  - SePay's ack shape, and 503 with no ack on a failed item write;
  - feed cursor loop: never `page=2`, a full multi-page run without a skip, the settle stop, a failure mid-page keeps
    the cursor, a lost compare-and-set writes nothing, skipped rows are counted, first-run backfill, 429.
- **`tests/test_billing_sepay_postgres.py`** (16, PostgreSQL):
  - **Exactly once:** one top-up across the webhook, its replay and the feed, with a reference. Without a reference,
    the second source is `source_ambiguous` and never a second payment. Two different references are a real second
    transfer (`not_payable`). A timely plan payment grants once.
  - **Late (7 cases):** pending, created or expired past `expires_at` + grace is `late_payment`; a late webhook for a
    timely transfer is paid; timeout-expired within the grace is paid; cancelled is `order_closed` both inside and
    outside the grace. A refunded order is `order_closed`. An unconfigured grace fails closed.
  - **Race (required):** a cancellation that holds the order's lock while the payment waits for it, then commits,
    gives `payment_not_payable` / `order_closed`: not paid, no grant, no top-up, balance 0.
  - **Race, second form:** the payment paused before the lock while a cancellation commits.
  - **Locked snapshot:** an `expires_at` moved before the lock decides the outcome.
- **Full gate:** SQLite 7183 passed. Every PostgreSQL file: 442 passed plus 1 inherited failure (#160). All Node gates
  passed.

## Notes for the reviewer

- **RR-8.1 (design §11a).** payOS `mark_paid` still accepts `cancelled`. It is unchanged and out of scope.
- **Ledger naming.** A refund of a SePay credit pack reverses through the ledger source type `payos_refund`, with
  `source_ref = sepay:<code>`. The type name predates SePay; the reference and the 0033 trigger are generic, so no
  schema change was made. Recorded as a naming residual.
- **Item kinds.** `payment_not_payable` items for SePay keep `reason = not_payable` for a real second transfer (two
  different bank references), separate from the three stable SePay reasons.
- **FundingContext:** not involved (payments are not provider calls).

## Still gated (design §12)

- SePay test mode;
- cursor, bank-reference and `webhook_success` verification;
- a QR scan in a banking app;
- the live small-value transfer and its refund;
- secret and configuration readiness on the runtime;
- runtime migrations (0027 -> 0033);
- production activation.
