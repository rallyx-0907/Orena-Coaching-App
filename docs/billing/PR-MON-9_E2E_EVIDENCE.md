# PR-MON-9: sandbox proofs (design §3.6.1, §3.3, §4.4) and end-to-end evidence

## 1. Proofs of 2026-10-18

**Setup:** run on the `:8031` sandbox (signed in with Google on `http://localhost:8031`), on the owner's own test
subscription, bought with the test card. Owner approval for the writes was given on 2026-10-17. The calls went through
`PolarSubscriptions` itself; `scheduled_changes=True` was set **for the proof run only**. The record shows plan names,
states and HTTP codes only.

| Step | Polar after the step | Orena record | Proves |
| --- | --- | --- | --- |
| A. Plus monthly → Pro monthly (`invoice`) | product Pro monthly | `pro`, by the webhook | an immediate upgrade |
| B. Pro monthly → Plus monthly (`next_period`) | product **still Pro monthly**; `pending_update` = Plus monthly, `applies_at` the period end | `pro` | **(1)** a scheduled change keeps the plan until renewal |
| B2. A second scheduled change | unchanged | unchanged | refused by Orena, `change_pending` |
| C. Cancel at period end while pending | `cancel_at_period_end = true` **and the `pending_update` is kept** | `cancel_at_period_end = true` | **(2) not proven** (below) |
| C2. A change while cancelling | unchanged | unchanged | refused by Orena, `cancelling` |
| D. Resume | `cancel_at_period_end = false`, the pending update still kept | resumed | the pending change survives a cancel and resume |
| E. Pro monthly → Pro yearly (`invoice`) while pending | product Pro yearly; **`pending_update` gone** | `pro` | **(3)** an immediate change supersedes the pending update (also stated in Polar's proration docs) |

**Decision under §3.6.1: scheduled changes stay off in v1** (`SCHEDULED_CHANGES = False`).
- (1) and (3) are proven. (2) is not.
- After a cancellation, Polar keeps both the cancellation and the pending switch to Plus at the same period end, and
  which one wins can only be seen at the period end. The sandbox cannot advance time.
- So a downgrade is offered as "Cancel at period end", a period-down is not offered, and no account enters
  `active+pending`. This can be revisited once (2) is observed: a sandbox subscription reaching its period end, or
  Polar support confirming.

**Other results:**
- **Q2, "Keep {cur}": not shipped.** Polar documents no operation that removes a pending update without replacing it
  ([proration docs](https://polar.sh/docs/features/subscriptions/proration)). Re-sending the current product is not
  used (review condition).
- **§3.3 proration preview: case B.** Polar documents no preview endpoint, so the change sheet shows no amount and the
  route takes none.
- **§4.4 payment method: proven.** An organization token reads `GET /v1/customers/{id}/payment-methods`, whose
  `method_metadata` carries `brand`, `last4`, `exp_month` and `exp_year`. Only those four are kept. (The customer
  object's own `default_payment_method_id` was empty, so the first method or the `is_default` one is used.)

## 2. End-to-end (UI), 2026-10-18

**Setup:** run on the `:8031` sandbox at `0c791767`, signed in with Google on `http://localhost:8031` in the owner's
Chrome, driven through Claude in Chrome. The owner approved every write. The owner paid in Polar's form; Orena never
received card data.

| Check | Result |
| --- | --- |
| Plan & usage, desktop (VI / EN / ZH) | Pro, "Yearly · $159.99 / year" (USD in every language, D-MON-034); "Renews {date} · charged to Visa •••• 4242"; card brand, last4 and expiry; billing email; real invoices; Cancel plan. Dates and money formatted per language. |
| Light theme (contrast) | secondary text 6.54:1, the "Paid" pill 4.55:1, primary text 17.82:1: all AA |
| Phone (360×740, touch) | no page scroll, no horizontal overflow; the cards scroll in their own region |
| Billing Sheet footer | measured against the frame (line 1890) and corrected: two equal 48px buttons, radius 14, 15px/600, gap 10, padding 16 24 22 (scoped) |
| Pricing on Pro yearly | Pro shows "Current plan"; Plus → the fail-closed sheet ("not available yet…", "Cancel Pro"); Free → the cancel sheet (a browser finding, fixed) |
| **Cancel** (phone, reason "Taking a break") | "Cancelling…" → "All set / Plan cancelled", only after the server showed `cancel_at_period_end`; then the amber banner with "Resume Pro", the pill "Cancels Oct 18", and Cancel plan hidden |
| **Resume** | banner gone, pill "Active", Cancel plan back. *The "You're staying on Pro" toast was not captured: unverified.* |
| **Invoice download** | 202 `preparing`, then 200 `ready` with a URL on Polar's invoice store |
| **First purchase through the embed** (after revoking the Pro subscription through the sandbox API) | "Continue to payment" opened Polar's form **inside the app** (the Embedding allowlist holds `localhost:8031`), with no discount field and no trial, $9.99/mo. After the owner subscribed: the overlay closed, the app did not navigate, and "All set / You're on Plus / New limits are active now" appeared only once the server showed `plus · active · month`. Done → Plan & usage, which showed Plus, "Monthly · $9.99 / month" and a fourth invoice. |
| **Update card → portal** | `POST /api/billing/portal` answered 200 to a scripted click; a scripted click is not a user gesture, so the new tab may have been blocked. The real click timed out in the browser tool. **Confirmed by the owner by hand (2026-10-18): Polar's customer portal opened in a new tab.** |

**Notes:**
- The page header's title wraps on a phone next to "See all plans". The shared header predates this PR.
- Step 5 of PR-MON-10 (a failing renewal) and the period-end outcome of cancel-while-pending were proven on
  2026-10-19 (§3).

## 3. Period ends on the Polar sandbox, 2026-10-19 (owner-approved test subscriptions)

Daily test products were used (1-day period). A and B ran on the Polar API only; D and F ran through the `:8031`
sandbox, with Orena receiving webhooks. All times are UTC. Every payment was test money.

| Run | Setup | At the period end | Reading |
| --- | --- | --- | --- |
| **A** | High ($2/day): downgrade to Low scheduled (`next_period`), then cancel at period end | `canceled`, `ended_at` 11:31:54 = the period end. No Low order; the only order is the $2.00 creation. The pending Low stays listed but never applied | **Cancel wins over a pending change.** §1 (2) is now proven |
| **B** | High: downgrade to Low scheduled only | Low, `active`, the next period started at 11:33:05. Order `subscription_cycle` $1.00 `paid`, created 15 min after the cycle. `modified_at` 11:33:06 (set) | the pending change applies at the period end. **R1 on Polar: `modified_at` IS set at renewal** |
| **D** | Daily Pro ($19.99), downgraded to Daily Plus ($9.99) in Polar's portal on 2026-10-18 (applied at once, proration `invoice`) | Plus, `active`, period 14:03:16 → +1 day. Renewal order `subscription_cycle` **$0.11** `paid` | **The unused Pro part was credited**: the renewal charged $0.11 instead of $9.99. Polar carried the credit from the immediate downgrade to the next invoice |
| | Orena (`commerce_subscriptions`) | `active · plus`, `paid_through` 2026-10-20 14:03:16 (moved one day), `object_version` = the renewal's `modified_at`. The renewal receipt `applied`; its duplicate delivery `ignored · stale` | **R1 in Orena: the renewal was applied, not dropped** |
| **F** | Daily Pro, card changed to the declining test card | Polar `past_due`; renewal order $19.99 `pending`; `modified_at` 14:19:40 | the failed renewal is `past_due` |
| | Orena | `past_due · pro`, `paid_through` 14:19:40 (Polar's `past_due_at`, `polar._paid_through`), receipt `applied` | grace (48 h, D-MON-011) counts from the failed charge, 15 min after the period end, so it is slightly more generous than "2 days after the end of the period" |

**Consequences:**
- **R1 is closed: no code change is needed.** Polar sets `modified_at` at renewal, and Orena applied the renewal.
- **`SCHEDULED_CHANGES` can be reconsidered:** cancel wins over a pending change. It stays off until the owner asks
  for scheduled downgrades; the in-app downgrade is still a cancel at the period end.
- **Downgrade in the portal:** proration `invoice` applies the downgrade at once and credits the unused part to the
  next invoice. This matches the owner's rule (D-MON-035), so the portal setting stays `invoice`.
- Still not observed: F's end after Polar's retries (`unpaid` → `ended`), and whether the grace then ends access.
  Hermetic tests cover both.
