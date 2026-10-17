# PR-MON-9: Plan & usage, Pricing, Billing Sheet and Credits Payment on the real backend (design)

**Status: DESIGNING (docs only), for independent review.** Base: `main` `75e65863`. Owner decisions: D-MON-033
(2026-10-17). This PR changes learner-facing UI and adds payment-changing backend routes, so it needs independent
review before code. Nothing is enabled. Gate 7b stays the activation.

## 1. Source

The design at its source (D-067, D-088): `Orena.dc.html`, pinned in `docs/design/canonical-ui/screens/`.

| Frame | Line | Notes |
| --- | --- | --- |
| Plan & usage | 1079 | |
| Credits | 1138 | |
| Pricing | 1205 | |
| Billing Sheet | 1865 | steps `form` (kinds `change` / `cancel` / `card`), `processing`, `done` |
| Credits Payment | 1894 | steps `confirm`, `qr`, `received`, `done`, `expired` |

The state-script handlers are `openSheet`, `proc`, `setBill`, `resumePlan`, `openCard`, `crPay`, `crDetect` and
`crContinue` (lines 3047-3170).

**The design draws every payment step inside the app:**
- a card form ("Card number" / "Expiry" / "CVC");
- in-app plan changes with "Pay {due}";
- an in-app cancel with reasons;
- a Resume control;
- invoices with "Download PDF";
- a VietQR sheet.

It draws no external page and no portal.

**What exists today** (`static/orena/screens/plan/`): the frames are drawn read-only while `billing_ready` is false.
- The Billing Sheet shows only the change summary, with Confirm `disabled`.
- Payment method shows its empty state, and Update is `disabled`.
- Invoices reads "No invoices yet".
- Banner, Cancel plan, the Cancel sheet and the Card sheet are not drawn.

Gaps PLN-4, PLN-5, PLN-6 and PLN-7 (`UI_BACKEND_GAPS.md`) track these.

## 2. The constraint, and the owner's decisions (D-MON-033)

Polar is the merchant of record. **Orena never collects, sends or stores card data.** The design's in-app card form
therefore cannot be built as drawn. On 2026-10-17 the owner chose:

| Decision | Choice |
| --- | --- |
| **First purchase** (Free → Plus/Pro) | **Polar embedded checkout.** "Pay" in the Billing Sheet opens Polar's own card form as an overlay inside the app. |
| **An existing subscriber** changes plan, cancels with a reason, or resumes | **In the app, through Polar's API**, as the design draws it. |
| **Payment method "Update"** | Opens **Polar's customer portal** (`POST /api/billing/portal`, built in PR-MON-10). |
| **Invoices** | **In the app**: the list and "Download PDF" through Polar's API. |

## 3. Frame by frame: what each control does

### 3.1 Pricing (`#/plan/pricing`)
- The tiers, the Monthly/Yearly switch and the comparison table stay as they are (real catalogue, D-153).
- A plan's button opens the Billing Sheet (`change`), as drawn.
- The "Most popular" / "Most capable" tags and the FAQ stay undrawn (PLN-1, PLN-7: no measure, no policy).

### 3.2 Billing Sheet, kind `change`

**Free → paid (first purchase):**
- Rows: Plan, Price and "Due today" come from the server price (`GET /api/billing/offers`). "Starts: Today".
- No Payment row: there is no card yet.
- The primary "Pay {due}" calls `POST /api/billing/checkout` with `embed: true`. The server adds
  `embed_origin = PUBLIC_BASE_URL` to the Polar checkout and returns its URL.
- The app opens it with Polar's embed (`@polar-sh/checkout` at a pinned version, loaded from the allowed CDN). The
  sheet shows `processing` ("Confirming with your bank…") while the embed is open.
- On the embed's `success`, the sheet stays in `processing` until the account's plan reads active
  (`GET /api/product/commerce`, polled every 2 s for at most 60 s). Then it shows `done`: "You're on {T}" / "New
  limits are active now." The receipt sentence names no email we do not hold.
- If the webhook is late, the sheet says the payment is confirmed and the plan will appear shortly. **Access always
  comes from the webhook, never from the embed's event.**
- On the embed's `close`, the sheet returns to `form`.

**Paid → another plan or period (existing subscriber):**
- Rows: Plan, Price, Starts, Payment (brand •••• last4 when Polar exposes it; §4.4), Due today.
- **Upgrade** (more expensive, or monthly → yearly): `POST /api/billing/subscription/change` with
  `proration_behavior=invoice`. Polar charges the difference to the saved card at once.
  - "Due today" is Polar's proration preview if the API offers one. Otherwise the row reads "Charged now: the
    difference" without a number. **Never an amount computed by Orena.**
- **Downgrade** (cheaper, or yearly → monthly): the same route with `proration_behavior=next_period`. The change takes
  effect at renewal, and the sheet says "Nothing is charged today. You keep {cur} limits until {renews}." — the
  design's own sentence. *Review question Q1.*
- `processing` lasts until the webhook moves the record (`product_id` → plan, PR-MON-10 §4.5), then `done`.

### 3.3 Billing Sheet, kind `cancel`, and the amber banner

**"Cancel plan"** (drawn only for a paid, live plan with no cancel and no pending change):
- The sheet draws "You keep {cur} until {renews}", the limits lost (from the catalogue's Free limits) and the reason
  chips.
- **"Cancel plan"** calls `POST /api/billing/subscription/cancel` with the chip as Polar's
  `customer_cancellation_reason`:

  | Chip | Polar reason |
  | --- | --- |
  | Too expensive | `too_expensive` |
  | Not using it enough | `unused` |
  | Missing a feature | `missing_features` |
  | Taking a break | `other` |

  No free-text comment is sent: Polar's field is customer feedback, not internal notes, and the design has none.
- `processing` lasts until the webhook shows `cancel_at_period_end`, then `done` ("Plan cancelled" / "You keep
  {cur} until {renews}…").

**The amber banner and "Resume {cur}"** are shown while `cancel_at_period_end` is true:
- Resume calls `POST /api/billing/subscription/resume` (Polar `cancel_at_period_end=false`). The toast "You're
  staying on {cur}" appears after the webhook confirms.
- "Keep {cur}" for a pending downgrade: see Q2.

### 3.4 Plan & usage (`#/plan`)
- **The plan card:**
  - status pill: Active / Cancels {date} / Changes {date};
  - "Renews {date}" from `paid_through`;
  - "Change plan" / "Upgrade".
- **Payment method** shows brand •••• last4 and expiry when available (§4.4). **"Update" opens the portal** in a new
  tab. The card sheet (`card` kind) is **not built**: Orena never takes card data.
- **Billing email:** the subscription's Polar customer email, read-only. Not drawn if absent.
- **Invoices:**
  - each row from `GET /api/billing/invoices`: date, plan · period, amount, status;
  - "Download PDF" calls `GET /api/billing/invoices/{order}/pdf`, which generates the invoice if needed and redirects
    to Polar's invoice URL;
  - empty state: "No invoices yet".
- **The footer** "Payments are simulated in this prototype." is prototype copy and is **not drawn** (rule 43).
- The usage chart stays undrawn (PLN-3).

### 3.5 Credits and Credits Payment (`#/credits`)
- These stay shown only while the backend offers packs. Credits is off until gate 7a.
- With packs on, the `qr` step draws the server's VietQR payload (SePay, PR-MON-8): the VA account, the amount, the
  transfer note `ORN…` with Copy, and the 15:00 countdown from `expires_at`.
  - "Waiting for your transfer" polls the order until `paid`, then shows `received` and `done`, with the balance from
    the credit ledger.
  - `expired` comes from the order's expiry.
- The prototype controls ("Let this QR expire", the 8-second detection) are **not drawn**.
- The words "via payOS" are sample copy (D-068). The line names the gateway that is actually configured.

## 4. Backend (Billing lane) — payment-changing, needs independent review

All routes are for the signed-in learner, act only on their own incarnation's Polar subscription (the stored
mapping), and are refused while billing is off. Every change is applied by the webhook; a route only asks Polar.

| Route | Polar call | Notes |
| --- | --- | --- |
| `GET /api/billing/subscription` | (none: the commerce record, plus §4.4) | plan, period, status, `renews_at` (`paid_through`), `cancel_at_period_end`, `pending_change` (Polar `pending_update`, if present), payment method summary, billing email |
| `POST /api/billing/subscription/change` `{price_key, operation_id, confirmed_amount_minor, confirmed_currency}` | `PATCH /v1/subscriptions/{id}` `{product_id, proration_behavior}` | the price must be offered and confirmed, as checkout requires; upgrade → `invoice`, downgrade → `next_period` (Q1); a 402 from Polar (card declined) → 402 `payment_failed` |
| `POST /api/billing/subscription/cancel` `{reason}` | `PATCH` `{cancel_at_period_end: true, customer_cancellation_reason}` | the reason comes from the closed list of §3.3 |
| `POST /api/billing/subscription/resume` | `PATCH` `{cancel_at_period_end: false}` | |
| `GET /api/billing/invoices` | `GET /v1/orders/?customer_id=…` | only this account's orders |
| `GET /api/billing/invoices/{order_id}/pdf` | `POST`, then `GET /v1/orders/{id}/invoice` | ownership checked against the list first; 302 to Polar's URL |
| `POST /api/billing/checkout` (exists) | + `embed_origin` when `embed: true` | |

- **Idempotency:** `change` takes the client's `operation_id`. A repeat answers the first result and never sends a
  second PATCH.
- **Token scopes** added to `RUNBOOK_POLAR_ACTIVATION.md`: `subscriptions:write`, `orders:read`. The scopes of §4.7
  remain.
- **§4.4 Payment method summary.** The customer object carries only `default_payment_method_id`. Whether an
  organization token can read the method's brand, last4 and expiry is **verified on the sandbox first**. If it cannot,
  the row reads "Card on file", Update still opens the portal, and the gap is recorded.
- **Embed allowlist:** the production host and `localhost` are added under Polar → Settings → Embedding (a runbook
  step).
- **The browser** never sees the Polar token. The embed script is the only Polar code that runs in the page.

## 5. UI rules applied (Design Contract 42-50, CLAUDE.md)

- Measured against the frames, not eyeballed:
  - desktop 1920×1080 and phone 390×844 (touch);
  - EN / VI / ZH;
  - light / dark.
- Plan & usage, Pricing and Credits are focus routes and are checked against rule 49 (the viewport).
- Every label is translated (EN/VI/ZH). Lucide icons come from the pinned package.
- Nothing the frames do not draw is added, except:
  - the "plan will appear shortly" fallback (§3.2), which is a behaviour without a frame, reported here for decision
    (Q3);
  - the portal opening in a new tab.

## 6. Tests

**Backend (hermetic + PostgreSQL):**
- each route's Polar request body;
- ownership (no other account's subscription or order);
- the reason mapping;
- the 402 decline;
- an idempotent `change`;
- the invoice ownership check;
- `embed_origin`;
- refusals while billing is off or the learner is signed out;
- no Polar token or card data in any response or log.

**UI:**
- the model functions (sheet step machine, banner and pill rules, the reason mapping);
- a browser run on the `:8031` sandbox with a signed-in test learner (see Q4).

**Sandbox E2E:**
- an embedded first purchase;
- an upgrade charged to the saved card;
- a downgrade scheduled;
- cancel with a reason, then resume;
- invoice download;
- Update opening the portal.

## 7. Review questions

- **Q1.** Downgrade with `proration_behavior=next_period` (no charge now, change at renewal, as the design's
  downgrade copy says), upgrade with `invoice`? The owner's Q2 of PR-MON-10 fixed `invoice` for portal changes.
- **Q2.** "Keep {cur}" for a pending downgrade: revert by PATCHing the current product back, or leave it out of v1
  if Polar does not support undoing a scheduled change?
- **Q3.** When the webhook is slower than 60 s after a successful embed, the sheet says "Payment confirmed — your new
  plan will appear in a moment" and closes. This sentence is not in the design: accept it, or keep `processing` up
  with a Close button?
- **Q4.** The browser E2E needs a signed-in learner on the sandbox. The `:8031` sandbox has no Google sign-in, and
  public exposure without it is refused. Run the UI check with Google sign-in configured on the sandbox, or defer the
  signed-in UI proof to the VPS gate 7b?
