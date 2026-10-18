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

## 2. End-to-end (UI)

To follow once the UI slice is built: the first purchase through the embed, the upgrade, cancel and resume, an
invoice download, Update opening the portal, in EN/VI/ZH, light and dark, on desktop and phone.
