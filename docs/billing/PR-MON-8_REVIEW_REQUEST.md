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

## Evidence: current, for code head `ac174ad5`

The latest code head is `ac174ad5`, synced with `main` `4ee804d0`. The evidence commit that follows changes docs only.

- **CI:** [run 38829616460](https://github.com/rallyx-0907/Orena-Coaching-App/actions/runs/38829616460) on
  `ac174ad5`. Every job passed: `changes`, `python-gates`, `node-gates`, `pytest`, `docker-build` and `test`.
- **Local** (not CI):
  - full SQLite gate: 7287 passed;
  - every PostgreSQL file: 445 passed, plus 1 inherited failure (#160);
  - `tests/test_billing_sepay.py`: **74** passed;
  - `tests/test_billing_sepay_postgres.py`: **19** passed;
  - all Node gates passed.

The lists below describe what the two SePay files cover. The counts above are the current ones.

### Coverage (the first implementation, `20fff517`)

- **`tests/test_billing_sepay.py`** (hermetic):
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
- **`tests/test_billing_sepay_postgres.py`** (PostgreSQL):
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
- **Full gate at `20fff517`** (history): SQLite 7183 passed. Every PostgreSQL file: 442 passed plus 1 inherited
  failure (#160).

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

## Implementation review of `10471923` (ChatGPT / GPT-5.6 Sol): REQUEST CHANGES (3 P1, 2 P2), and the fixes

| Finding | Fix |
| --- | --- |
| **P1-1:** the order code was not exact; `int(digits)` turned `ORN0100001` into order 100001 | `order_code` returns an order only when the suffix is canonical: `str(int(digits)) == digits` and the number is positive. `ORN0100001`, `ORN000100001` and `ORN0` name no order. Tests: hermetic mapping, plus PostgreSQL via both the webhook and the feed. All give `payment_unknown_order`, no top-up, and the order stays pending. |
| **P1-2:** an unapproved "international-only" exception | Removed. In production, no `BILLING_DOMESTIC_GATEWAY` means `domestic_gateway_unset` whatever is configured. A configured choice that is not configured as a gateway means `domestic_gateway_unconfigured`. Inference applies only outside production with one domestic gateway. Readiness test: a production runtime with Polar ready and no domestic choice is not billing-ready. |
| **P1-3A:** the first run fell back to `now()` | The first run starts at the oldest open SePay order; when none is open, at the gateway's first order of any state (when SePay sales began). Before SePay ever sold, the cursor is not started (`sepay_feed_no_orders`), never "now". |
| **P1-3B:** no operator date-range backfill | `SePayFeed.backfill(date_from, date_to)` uses the same §6.3 rules and the same `handle_fact` path. It runs with `page=1`, `transaction_date_to` and a local `since_id`, and **never reads or writes the cursor**. It needs only the token, so it also works while the feed is off. The range is positive and at most 31 days, with at most 50 pages. It is exposed as admin-only `POST /api/admin/billing/sepay/backfill`, recorded in the authorization matrix. Tests: same handling, cursor untouched, works with the feed off, needs the token, range bounds, and an idempotent replay on PostgreSQL (one top-up). |
| **P2-1:** `Retry-After` was discarded | A 429 writes `not_before = now + Retry-After` into the cursor document (compare-and-set), default 60 s. Every tick before then, in any worker, makes no request (`sepay_feed_waiting`). Test: with a 600 s wait and 60 s ticks there is exactly one request until the wait ends. |
| **P2-2:** VietQR tests were self-consistency only | Two complete published vectors from independent implementations, matched exactly. One is from `xuannghia/vietnam-qr-pay` (ACB 970416, 10,000 VND, "Chuyen tien"). The other is from `subiz/vietqr` (VietinBank 970415, 120,000 VND, "ung ho lu lut"). A real banking-app scan remains activation gate 8. |

## Implementation re-review of `851f4bb9` (ChatGPT / GPT-5.6 Sol): REQUEST CHANGES (2 P1), and the fixes

All 5 findings of the review of `10471923` were confirmed closed, with no new issue in the payment, locking,
exactly-once, reconciliation, feed-cursor, secret or schema areas. CI run 38826615961 passed on `851f4bb9`.

| Finding | Fix |
| --- | --- |
| **P1-1:** an operator backfill could finish incomplete and still answer `ok: true` (the 50-page cap, a 429) | `backfill()` returns `{complete, reason, resume_after, retry_after, counts}`. `complete` is true only when SePay returned the range's last page. A page cap gives `page_cap`, a 429 gives `rate_limited` (with `retry_after`), and rows still in the settle window give `settle_delay`. Each comes with the last handled row as `resume_after`. The admin route answers **409 / 429 `backfill_incomplete`** with that context, never `ok: true`, and accepts `resume_after` to continue. The authoritative feed cursor is still never read or written. Tests: more rows than the cap is incomplete and the tail is recovered on resume; a 429 after several pages is incomplete and resumes exactly once; the settle delay leaves the range incomplete; the route is never ok for a partial run; on PostgreSQL a capped run resumes and a full replay stays exactly once on the real ledger (top-ups 2, then 2). |
| **P1-2:** stale evidence and resume point | The "Evidence" section above now carries the current head, CI run and counts. `BILLING_STATUS.md` now records `main` `4ee804d0` and the current PR-MON-8 evidence. Historical review outcomes are unchanged. |


## Final implementation re-review of `c3140740` (ChatGPT / GPT-5.6 Sol): APPROVED

**P0 0, P1 0, blocking P2 0.** CI run 38830077460 passed. The code fix head is `ac174ad5` and the base is `main`
`4ee804d0`. The two blockers of the `851f4bb9` review are closed, and every earlier area remains accepted.

The implementation is approved to proceed to its merge gate. The merge itself is the owner's decision. Not authorized
by this review:
- production activation;
- any shared-runtime migration;
- the live-money transfer;
- public tunnel/DNS;
- production credentials.

After the merge, the remaining design §12 gates still apply, each separately:
1. SePay test mode;
2. real cursor semantics;
3. bank-reference equality;
4. `webhook_success` behaviour;
5. a real banking-app QR scan;
6. the human-approved small-value live transfer and its refund;
7. the runtime, configuration and production activation gates.
