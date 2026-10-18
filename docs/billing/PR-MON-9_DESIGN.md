# PR-MON-9: Plan & usage, Pricing, Billing Sheet and Credits Payment on the real backend (design)

**Status: DESIGNING, revision 3.1 (docs only), for a targeted re-review of §4.2.1.** Revision 3 answered the review of `8d6f2985`. Revision 3.1 answers the review of `eb86c1a2` (1 P1, 1 P2): the journal's crash recovery (leases, stale `pending` and `sent`), an explicit operation id on every write route, and the journal's retention. Base: `main` `75e65863`. Owner decisions:
D-MON-033. Revision 2 answers the review of `4e4da27b` (4 P1, 2 P2) and records the answers to Q1-Q4 (§0). This PR
changes learner-facing UI and adds payment-changing backend routes. No code until the design is approved; nothing is
enabled; gate 7b stays the activation.

## 0. Revision 2: the review of `4e4da27b`

| Finding | Revision 2 |
| --- | --- |
| **P1-1** "Due today" not truthful; the change contract asks for a confirmed amount while the UI may not have one | §3.2: a first purchase shows the **base price** only, and the CTA is "Continue to payment". Polar's checkout is the authority on the total, tax and card. A plan change shows an exact "Due today" **only** from a Polar preview (case A). Otherwise it shows no number, and the route takes no confirmed amount (case B, §4.2). |
| **P1-2** upgrade/downgrade rule ambiguous | §3.5: a canonical matrix where **the feature tier wins over the billing period**. One function serves both backend and UI, with a test table. |
| **P1-3** pending-change state machine incomplete; Cancel hidden during a pending change | §3.6: transitions for pending downgrade → cancel, pending downgrade → upgrade, and keep current. **Cancel is always available on a live paid plan.** Webhook reordering is handled by Polar's own revision. |
| **P1-4** invoice download treated as synchronous; ownership checked through a paginated list | §3.4 and §4.3: GET first; if missing, generate (asynchronous) and answer 202 "preparing"; the client polls within a bound, then redirects. **Ownership is checked by fetching the order by id** and comparing its customer with the incarnation's Polar customer. |
| **P2-1** checkout state machine | §3.2: summary → embed → "Processing payment…" (on `confirmed`) → overlay closed on `success` (embed told not to redirect) → "Activating your plan…" → `done` on the webhook. Closing the overlay after `confirmed` never reads as a failure. |
| **Rev 3 / P1-1 (review of `8d6f2985`)** plan-change idempotency not durable | §4.2.1: an operation journal persisted **before** the Polar PATCH, keyed by `operation_id` with a request digest. Same operation and request → the original answer or a reconcile; different request → 409 `operation_conflict`. An ambiguous PATCH outcome (timeout, 5xx, broken connection) → `provider_unknown` → reconciled only by **reading** the Polar subscription, **never a second PATCH**. |
| **Rev 3 / P1-2** pending downgrade without a fail-closed fallback | §3.6.1: `next_period` changes (downgrade, period down) **ship only if the sandbox proves** that cancel and upgrade while a change is pending are safe on Polar. If not, v1 does not offer a scheduled change: a downgrade is offered only as "cancel at period end, then choose a plan", and a period-down is not offered. No account is put into `active+pending` before the exits are proven. |
| **Rev 3.1 / P1 (review of `eb86c1a2`)** `pending` and `sent` could stay forever after a crash; the operation identity of cancel, resume and keep was implicit | §4.2.1, "Ownership and crash recovery": a `pending` operation carries a lease. A **stale `pending`** (never sent) may be claimed by CAS and sends the **first** PATCH, within 10 minutes of its creation; after that it becomes `not_applied`. A **stale `sent`** is ambiguous and is reconciled by GET only. The same operation is never PATCHed twice. **Every write route takes a client `operation_id`**. Crash and concurrency tests are added. |
| **Rev 3.1 / P2** the journal's keyspace grows without bound | §4.2.1, "Retention": terminal documents are deleted by the reconciler after 90 days. Unresolved ones are kept and counted. |
| **Rev 3 / P2** a 30 s cache of the whole subscription answer | §4.1: the commerce and access state is read **fresh from the local record on every request**. Only the Polar enrichment (`pending_update`, payment method, billing email) is cached, 30 s per account. |
| **P2-2** origins | §4.5: the sandbox gets a stable HTTPS hostname, a Google OAuth client and redirect for it, and that origin in Polar's Embedding allowlist. Production origin likewise. |

**Answers (review and owner, 2026-10-17):**
- **Q1:** the matrix of §3.5.
- **Q2:** "Keep {cur}" ships only if the sandbox proves an official, idempotent way to cancel a pending update.
  Otherwise it is left out of v1 and the scheduled change is only shown. Never a re-PATCH of the current product
  without proven semantics.
- **Q3:** the fallback copy of §3.2.
- **Q4:** the signed-in UI proof runs on the sandbox, with Google sign-in (§4.5). It is not deferred to gate 7b.

## 1. Source

The design at its source (D-067, D-088): `Orena.dc.html`, pinned in `docs/design/canonical-ui/screens/`.

| Frame | Line | Notes |
| --- | --- | --- |
| Plan & usage | 1079 | |
| Credits | 1138 | |
| Pricing | 1205 | |
| Billing Sheet | 1865 | steps `form` (kinds `change` / `cancel` / `card`), `processing`, `done` |
| Credits Payment | 1894 | steps `confirm`, `qr`, `received`, `done`, `expired` |

The state-script handlers are at lines 3047-3170. The design draws every payment step in the app (a card form, "Pay
{due}", in-app cancel and Resume, invoices, VietQR) and no external page.

**Today** (`static/orena/screens/plan/`) the frames are read-only: the Billing Sheet's Confirm is disabled, Update is
disabled, and Invoices is empty. Gaps PLN-4 to PLN-7 track this.

## 2. The constraint and the owner's decisions (D-MON-033)

Polar is the merchant of record. **Orena never collects, sends or stores card data.**

| Decision | Choice |
| --- | --- |
| **First purchase** | Polar embedded checkout, opened from the Billing Sheet. |
| **An existing subscriber** changes plan, cancels with a reason, or resumes | In the app, through Polar's subscription API. |
| **Payment method "Update"** | Polar's customer portal (`POST /api/billing/portal`). The design's card sheet is not built. |
| **Invoices** | In the app, through Polar's API. |

**Truth sources, never mixed:**
- **Polar** is the truth for payment: the total, tax, the card and whether a charge succeeded.
- **Orena's webhook-fed commerce record** is the truth for access.
- No embed event, return page or route answer ever grants access.

## 3. Frame by frame

### 3.1 Pricing (`#/plan/pricing`)
- Unchanged: the real catalogue (D-153), the Monthly/Yearly switch, the comparison table.
- A plan's button opens the Billing Sheet (`change`).
- The tags and the FAQ stay undrawn (PLN-1, PLN-7).

### 3.2 Billing Sheet, `change`: first purchase (Free → paid)

**Rows:**
- Plan.
- **Base price** "$X / month" (or "/ year"), from the server's offer.
- "Starts: Today".

There is no "Due today" and no Payment row: the final total (tax, billing details) is Polar's to show.

**The primary button** reads **"Continue to payment"** (localized). It calls `POST /api/billing/checkout` with
`embed: true`. The server sets `embed_origin` to the request's allowed origin (§4.5) and returns the checkout URL. The
app opens it with Polar's embed (`@polar-sh/checkout`, a pinned version from the allowed CDN), with the theme following
the app's light/dark. The embed is told not to redirect on success.

**States:**
1. **Summary** (`form`).
2. **Embed open:** the overlay is Polar's.
   - Embed `close` **before** `confirmed` → back to the summary. Nothing was submitted.
   - Embed `confirmed` → the sheet underneath shows `processing` "Processing payment…".
   - Embed `success` → the overlay closes and the sheet shows `processing` "Activating your plan…".
   - The overlay closed **after** `confirmed` is never read as a failure. The sheet goes to "Activating your plan…"
     and waits for the record.
3. **Activation:** the app polls `GET /api/billing/subscription` every 2 s for at most 60 s. When the record shows the
   bought plan active → `done`: "You're on {T}" / "New limits are active now."
4. **Fallback after 60 s** (Q3, the review's copy). The sheet shows the text below with a Done button; Plan & usage
   keeps refreshing on its next load.

   | Language | Title | Text |
   | --- | --- | --- |
   | EN | Payment completed | We're activating your plan. You can close this window — your plan will update automatically. |
   | VI | Thanh toán đã hoàn tất | Orena đang kích hoạt gói của bạn. Bạn có thể đóng cửa sổ này — gói sẽ tự cập nhật. |
   | ZH | 付款已完成 | Orena 正在为你激活套餐。你可以关闭此窗口——套餐会自动更新。 |

### 3.3 Billing Sheet, `change`: existing subscriber

**Rows:**
- Plan.
- Base price.
- **Starts:** Today for an immediate change; "{renews}" for a scheduled one (§3.5).
- **Payment:** brand •••• last4 when Polar exposes it (§4.4); otherwise "Card on file".

**Due today, two cases, decided by the sandbox (§4.2):**
- **Case A, Polar offers an authoritative proration preview:** the server fetches it. The sheet shows the exact "Due
  today", and the change is bound to that preview (§4.2).
- **Case B, no preview:** the sheet shows "Charged now: the prorated difference, calculated by Polar" with no number,
  and the route takes no amount. Orena never computes a proration.
- For a scheduled change (§3.5): "Nothing is charged today. You keep {cur} limits until {renews}." — the design's
  sentence.

**Button and outcome:**
- The primary button: "Confirm change". It reads "Pay {due}" only in case A, for an immediate change.
- `processing` lasts until the webhook moves the record (`product_id` → plan, PR-MON-10 §4.5), or until the record
  shows the scheduled change. Then `done`, with the design's texts.
- A declined card (Polar 402) → back to the form with "Your bank declined this card. Update your card and try again."
  and the Update link (portal).

### 3.4 Plan & usage (`#/plan`)

**The plan card:**
- Status pill: Active / Cancels {date} / Changes {date}.
- "Renews {date}" from `paid_through`.
- "Change plan".
- **"Cancel plan" on every live paid plan that is not already cancelling, including while a change is pending**
  (§3.6).

**The amber banner:**
- **cancelling:** "You keep {cur} until {renews}, then move to Free…" with **Resume {cur}**.
- **pending change:** "Switches to {pend} on {renews}…" with **Keep {cur}**, only if Q2's proof passes (§3.6).
  Otherwise the banner has no button.

**Payment method:**
- brand •••• last4 and expiry, or "Card on file";
- **Update** opens the portal in a new tab;
- no card sheet.

**Billing email:** the Polar customer's email, read-only. Not drawn if absent.

**Invoices:**
- Each row comes from `GET /api/billing/invoices` (paginated, newest first): date, plan · period, amount, status.
- **Download** calls `GET /api/billing/invoices/{order_id}`:
  - `200 {url}`: the browser opens it;
  - `202 {state: "preparing"}`: the row shows "Preparing invoice…" and the client retries every 2 s, for at most
    30 s;
  - still not ready: "The invoice is still being prepared. Try again in a minute."
- Empty state: "No invoices yet".

**Not drawn:** the prototype footer "Payments are simulated…" (rule 43) and the usage chart (PLN-3).

### 3.5 The canonical change matrix (one function, backend and UI)

`classify(current, target)` where each side is (tier, period), with tier order Free < Plus < Pro. **The feature tier
wins over the billing period.**

| From → to | Kind | `proration_behavior` | Takes effect |
| --- | --- | --- | --- |
| Plus → Pro (any periods) | upgrade | `invoice` | now |
| Pro → Plus (any periods), e.g. Pro monthly → Plus yearly | downgrade | `next_period` | at renewal (keeps Pro until then) |
| Same tier, monthly → yearly | period up | `invoice` | now |
| Same tier, yearly → monthly | period down | `next_period` | at renewal |
| Same tier, same period | none | (refused: `no_change`) | |
| Paid → Free | cancel | the cancel flow (§3.6), never a product change | at period end |
| Free → paid | first purchase | checkout (§3.2) | after payment |

The server computes the kind from its own record and the target price. It never takes the client's word. The UI uses
the same rule (a shared table of the five rows) only to choose copy, and the server's answer wins.

### 3.6 Pending changes: the state machine

**States:**
- `active`;
- `active+pending` (a scheduled downgrade or period-down, Polar `pending_update`);
- `cancelling` (`cancel_at_period_end`);
- `ended`.

| From | Action | Rule | Result |
| --- | --- | --- | --- |
| active | downgrade / period down | `next_period` | active+pending |
| active+pending | **Cancel plan** | allowed; `cancel_at_period_end=true` | cancelling. **Cancellation wins**: at period end the plan ends and the pending change never applies. Polar's resulting state is read back by the webhook, and the sandbox proves Polar clears or supersedes the pending update. |
| active+pending | upgrade now (matrix: immediate) | allowed; `invoice` | active on the new plan. The sandbox proves the pending update is superseded. If Polar refuses a change while one is pending, the route answers 409 `change_pending` and the UI offers only Cancel or (if proven) Keep. |
| active+pending | another scheduled change | refused, 409 `change_pending` (one scheduled change at a time) | unchanged |
| active+pending | Keep {cur} | **only if the sandbox proves an official, idempotent cancel of the pending update** (Q2); otherwise not drawn | active |
| cancelling | Resume | `cancel_at_period_end=false` | active (or active+pending, if Polar kept the pending update: read back) |
| cancelling | any plan change | refused, 409 `cancelling`: Resume first | unchanged |

- **No state traps the learner:** from every live state, Cancel or Resume is available.

#### 3.6.1 Fail-closed: scheduled changes ship only once their exits are proven

The `active+pending` rows above depend on Polar's behaviour while a change is pending. **Before any account can enter
`active+pending`**, the first implementation slice proves on the sandbox:

1. a `next_period` change creates a `pending_update`, and the subscription keeps its plan until renewal;
2. **pending → cancel at period end** is accepted, and at period end the subscription ends (the pending change does
   not apply);
3. **pending → an immediate upgrade** is accepted and supersedes the pending update;
4. (optional) an official, idempotent removal of the pending update, for "Keep {cur}" (Q2).

**The contract:**
- **1-3 proven:** `next_period` downgrades and period-downs ship, and Keep ships only if 4 is proven too.
- **1-3 not all proven:** v1 ships **no scheduled change**:
  - a downgrade (Pro → Plus) is offered as **"Cancel at period end"**, after which the learner chooses Plus once the
    plan has ended, through a new checkout;
  - a period-down (yearly → monthly) is not offered, and the gap is recorded;
  - the server refuses `next_period` (409 `change_unavailable`), whatever the client sends;
  - no account is ever put into `active+pending`.
- **The switch is a server constant set from the proof, not a client flag.** The proof is recorded in
  `PR-MON-9_E2E_EVIDENCE.md`.
- **Webhook reordering and redelivery:** each event carries Polar's own `modified_at` revision (PR-MON-10). An older
  event never overwrites a newer state, and a redelivery is a duplicate.
- The `pending_change` the UI shows is read from Polar's `pending_update` on the latest applied event, or from the
  subscription the server reads (§4.1). It is never remembered by the client.

### 3.7 Credits and Credits Payment (`#/credits`)
- Shown only while the backend offers packs (off until gate 7a).
- The `qr` step uses the server's SePay VietQR payload:
  - VA, amount, the `ORN…` transfer note with Copy;
  - the countdown from `expires_at`;
  - polling the order until `paid` → `received` → `done` (balance from the ledger);
  - `expired` from the order.
- The prototype controls are not drawn. "via payOS" is sample copy (D-068): the configured gateway is named.

## 4. Backend (Billing lane): payment-changing, needs independent review

All routes:
- are for the signed-in learner;
- act only on their own incarnation's Polar subscription (the stored mapping) and Polar customer
  (`external_customer_id` = incarnation);
- are refused while billing is off;
- never grant: every access change comes from the webhook.

### 4.1 `GET /api/billing/subscription`

From the commerce record, plus one read of the Polar subscription for its live fields.

Fields:
- `plan`, `period`, `status`;
- `renews_at` (`paid_through`);
- `cancel_at_period_end`;
- `pending_change` (from `pending_update`: target plan and period, effective date);
- `payment_method` (§4.4);
- `billing_email`.

**Freshness.**
- **The commerce and access fields** (`plan`, `period`, `status`, `renews_at`, `cancel_at_period_end`) are read
  **fresh from the local commerce record on every request**, never cached. The embedded checkout's 2 s activation poll
  (§3.2) and every sheet's `processing` wait therefore see the webhook's write at once.
- **Only the Polar enrichment** (`pending_change` from `pending_update`, `payment_method`, `billing_email`) is cached,
  30 s per account. It is dropped as soon as a route of this account changes the subscription, or a webhook for it
  arrives.
- A Polar read that fails returns the local fields with `enrichment: "unavailable"`.

### 4.2 Plan change

- **`POST /api/billing/subscription/change/preview`** `{price_key}` → `{kind, takes_effect, due_today?}`:
  - the kind comes from §3.5;
  - `due_today` is present only when Polar returns an authoritative proration preview for that change (**case A,
    proven on the sandbox first**), together with an opaque `preview_token`, the server's signed hash of
    (subscription, target product, amount, currency, a 10-minute expiry).
- **`POST /api/billing/subscription/change`** `{price_key, operation_id, preview_token?}`:
  - **Case A:** the `preview_token` is required and must still match a fresh preview; a changed amount →
    409 `price_changed`.
  - **Case B:** no amount is taken or checked.
  - It sends `PATCH /v1/subscriptions/{id}` `{product_id, proration_behavior}` from §3.5.
  - Idempotent by `operation_id`, durably (§4.2.1).
  - Polar 402 → 402 `payment_failed`. The state rules of §3.6 → 409 `change_pending` / `cancelling` / `no_change`.

### 4.2.1 The operation journal (durable idempotency)

Every Polar write of §4.2 and §4.3 (`change`, `cancel`, `resume`, `keep`) goes through one journal. It uses an
existing primitive: one `platform_settings` document per operation, key `billing.polar.op.<operation_id>`, written
with compare-and-set as the clean-up marker is (PR-MON-10 §4.8). No schema change. If the reviewer wants a table at
scale, that is a separate schema review; the contract is the same.

**The document** holds no card data and no Polar body:
- `incarnation`, `action`;
- `request_digest`: a SHA-256 of the canonical request (action, subscription id, target product, proration
  behaviour, reason);
- `state`: `pending` | `sent` | `done` | `refused` | `provider_unknown` | `not_applied`;
- the Polar status code, and the times.

**Operation identity.** **Every write route** (`change`, `cancel`, `resume`, `keep`) **requires a client-generated
`operation_id`** (a UUID; a retry of the same click reuses it). There is no implicit or derived key: a route without
one answers 422.

**The sequence:**

1. **Before any Polar call**, the operation is written `pending` with CAS on a missing key, together with its
   **lease**: `owner` (a random token of this request) and `lease_until` = now + 30 s.
   - The key already exists, for the same incarnation and the same `request_digest` → **no Polar call**. Answer from
     its state:
     - `done` / `refused`: the original answer;
     - `pending` / `sent`: 202 "in progress";
     - `provider_unknown`: run the reconcile below;
     - `not_applied`: the original "not applied" answer.
   - The key exists with a **different** digest or incarnation → **409 `operation_conflict`**, and nothing is sent.
2. Its owner marks it `sent`, by CAS on the document's version **and** its own `owner` token, and only then
   sends the PATCH. A CAS that fails means another worker owns it, and this worker sends nothing. **This is the only
   PATCH an operation ever sends.**
3. On Polar's answer:
   - 2xx → `done`;
   - a definite 4xx (402 declined, 409, 422) → `refused`, with the code;
   - **a timeout, a 5xx or a broken connection** → **`provider_unknown`**.
4. **Reconciling `provider_unknown`**, by reads only, both inline when the client asks again and in the billing
   reconciler: `GET /v1/subscriptions/{id}`.
   - If the subscription shows the operation's effect, the operation is `done`. The effects:
     - the target product is current or is the `pending_update` (change);
     - `cancel_at_period_end` is as asked (cancel / resume).
   - If it does not, and Polar's `modified_at` has not moved past the operation's `sent` time for **15 minutes**, the
     operation is `not_applied` and the learner may start over **with a new operation id**.
   - **The same operation is never PATCHed again.**
   - Money taken by an ambiguous change is Polar's to report: its `order.paid` arrives as evidence (PR-MON-10), and
     access follows the subscription webhook.
5. The UI keeps `processing` while an operation is `pending` / `sent` / `provider_unknown`, and polls the local record
   (§4.1) and the operation.

**Ownership and crash recovery.** A process can die between any two steps. Each state that can be left behind has
one rule:

| Left behind | What it means | Who may act | What they do |
| --- | --- | --- | --- |
| `pending`, lease live | its owner is working | nobody else | a repeat of the same request answers 202 "in progress" |
| `pending`, lease expired, created **< 10 min** ago | **no PATCH was ever sent**, because `sent` is written before the PATCH | the client's repeat request, or the reconciler | **claim** it by CAS (version, expired lease → new `owner`, new lease), then step 2: mark `sent`, send the **first** PATCH |
| `pending`, lease expired, created **≥ 10 min** ago | the learner has long left | the reconciler | `not_applied` by CAS; **no PATCH**; a new click is a new operation |
| `sent` (any age, no answer recorded) | **ambiguous**: the PATCH may or may not have reached Polar | the reconciler, or a repeat request | treated as `provider_unknown`: **reconciled by GET only (step 4), never resent** |
| `provider_unknown` | ambiguous | the same | step 4 |

**Per-subscription fence (implementation review P1-1 of `4a3b0438`).** At most one unresolved Polar write per
subscription, whatever the operation ids:
- a new operation first claims `billing.polar.op_fence.<subscription>` by CAS;
- while the fence names an operation that is not terminal (`pending`, `sent`, `provider_unknown`), another
  operation is refused with `409 operation_in_progress` and nothing is sent;
- a fence whose operation was never written (a crash between claim and journal) frees after `LEASE`;
- an exit always remains: Polar's customer portal (Update) is not fenced, and a fenced operation resolves (or reaches
  an operator) through the reconcile below.

**`not_applied` only when Polar did not move (implementation review P1-2).** The reconcile reads Polar's
`modified_at`. If the operation's effect is not visible but the subscription changed after the send, or the revision
cannot be read, the operation stays `provider_unknown`, is marked `moved`, and is escalated to an operator at once.
It is never presented as one that did not happen.

**Concurrency:** two workers that both see an expired lease race on CAS. Exactly one claims it; the other's CAS fails
and it sends nothing. A claimed operation's `sent` CAS still requires the claimer's own `owner` token. **At most one
PATCH per operation, ever.**

**Retention.** The keyspace is bounded by the reconciler:
- terminal documents (`done`, `refused`, `not_applied`) are deleted **90 days** after their last write;
- `pending`, `sent` and `provider_unknown` are never deleted while unresolved;
- readiness reports their counts (`polar_ops_unresolved`), and one older than 24 h raises one `event_undecided`
  operator item, as the clean-up does.

The table alternative stays a separate schema review.

### 4.3 Cancel, resume, invoices

- **`POST /api/billing/subscription/cancel`** `{operation_id, reason}` → `PATCH {cancel_at_period_end: true,
  customer_cancellation_reason}`, with the closed mapping:

  | Chip | Polar reason |
  | --- | --- |
  | Too expensive | `too_expensive` |
  | Not using it enough | `unused` |
  | Missing a feature | `missing_features` |
  | Taking a break | `other` |

  No comment field is sent.
- **`POST /api/billing/subscription/resume`** `{operation_id}` → `PATCH {cancel_at_period_end: false}`.
- **`POST /api/billing/subscription/keep`** `{operation_id}`: only if Q2's proof passes, with the proven operation.
- **`GET /api/billing/invoices?page=`** → `GET /v1/orders/?customer_id=<the incarnation's Polar customer>`, paginated.
- **`GET /api/billing/invoices/{order_id}`:**
  1. `GET /v1/orders/{order_id}`; 404 unless `order.customer_id` is this incarnation's Polar customer. **A direct
     ownership check, never a list search.**
  2. `GET /v1/orders/{id}/invoice` → `200 {url}` when it exists.
  3. On 404 there: `POST /v1/orders/{id}/invoice` (it generates asynchronously) → `202 {state: "preparing"}`.
  4. Repeated calls repeat step 2 and generate at most once a minute per order. A redirect only ever goes to a URL
     Polar returned for an order this account owns.

### 4.4 Payment method summary

The customer object carries only `default_payment_method_id`. **The sandbox proves first** whether an organization
token can read the method's brand, last4 and expiry. If not, the row reads "Card on file" and the gap is recorded.

### 4.5 Origins, OAuth and embedding (sandbox and production)

- **Sandbox, chosen until a deploy host exists (owner, 2026-10-17): `http://localhost:8031` as the stable browser
  origin.**
  - Google OAuth accepts a loopback redirect: a sandbox-only OAuth client with origin `http://localhost:8031` and
    redirect `http://localhost:8031/auth/google/callback`.
  - Polar's Embedding allowlist accepts HTTP for local hosts (`localhost:8031`, the port included).
  - The deployment guard accepts loopback with sign-in on.
  - Only Polar's webhook needs a public URL: a quick tunnel carries `/api/billing/webhooks/polar` alone. Its URL is
    updated in Polar's sandbox webhook settings per test session, and it never touches OAuth or embedding.
- **Sandbox, alternative once a host exists:** a **stable HTTPS hostname** (a named tunnel or the VPS's sandbox subdomain, owner's choice), with:
  - a Google OAuth client whose redirect URI is that hostname's `/auth/callback`;
  - `PUBLIC_BASE_URL` set to it, so the deployment guard accepts public exposure with sign-in;
  - the hostname listed in Polar's sandbox **Settings → Preferences → Embedding**.

  A random quick-tunnel URL is not used for this proof.
- **Production:** the production host in Polar's production Embedding allowlist; OAuth as already configured. Both
  are runbook steps.
- **`embed_origin`** is set only to a configured, allowed origin (`PUBLIC_BASE_URL`), never to a client-supplied
  value.
- **Token scopes** added to `RUNBOOK_POLAR_ACTIVATION.md`: `subscriptions:write`, `orders:read`, plus the payment
  methods scope if §4.4 needs it.
- The browser never sees the Polar token. The embed script is the only Polar code in the page.

## 5. UI rules (Design Contract 42-50, CLAUDE.md)

- Measured against the frames, not eyeballed:
  - desktop 1920×1080 and phone 390×844 (touch);
  - EN / VI / ZH;
  - light / dark.
- Focus routes are checked against rule 49. Every label is translated. Lucide icons come from the pinned package.
- Additions beyond the frames, each decided here:
  - the activation fallback (Q3);
  - "Preparing invoice…";
  - the decline message;
  - the portal opening in a new tab.

## 6. Tests

**Backend (hermetic + PostgreSQL):**
- every Polar request body;
- **the §3.5 matrix as a table test**, including Pro monthly → Plus yearly = downgrade;
- the §3.6 transitions:
  - no pending → schedule;
  - pending → cancel;
  - pending → upgrade;
  - pending → another schedule (409);
  - cancelling → change (409);
  - keep (if built);
- webhook reorder and redelivery for each;
- preview binding (case A) or no amount (case B);
- idempotent change;
- the reason mapping;
- 402;
- invoice: ready / preparing / generated once a minute / another account's order → 404;
- `embed_origin` only from configuration;
- refusals while off or signed out;
- no token or card data in a response or a log.

**UI:**
- the model (sheet step machine, matrix copy, banner and pill rules);
- a browser run on the sandbox's stable hostname **signed in with Google** (Q4), in the matrix of §5.

**Sandbox E2E:**
- a first purchase through the embed;
- upgrade (charged to the saved card);
- a downgrade scheduled, then cancelled while pending;
- a downgrade scheduled, then an upgrade while pending;
- keep (if proven);
- cancel with a reason, then resume;
- an invoice prepared and downloaded;
- Update opening the portal;
- the §4.4 proof;
- the case A/B proof.

## 7. Open before code

Revision 3 adds to the tests of §6:
- the operation journal:
  - **crash recovery:**
    - a crash after `pending` (before `sent`) → a claim within 10 min sends exactly one PATCH; after 10 min →
      `not_applied`, no PATCH;
    - a crash after `sent` → GET-only reconcile, never resent;
    - a crash after the PATCH, before `done` → GET-only reconcile → `done`;
  - **concurrency:** two claimers on one expired lease → exactly one PATCH (PostgreSQL CAS, real threads); a request
    and the reconciler racing on the same stale operation → one PATCH or none;
  - a write route without `operation_id` → 422;
  - retention: terminal documents older than 90 days deleted; unresolved ones kept, counted, and escalated after 24 h;
  - same operation and request → no second PATCH;
  - different request → 409;
  - timeout → `provider_unknown` → reconciled `done` or `not_applied` by reads only;
  - redelivery and reconciler races;
- the fail-closed switch: with scheduled changes off, `next_period` is refused and the downgrade offer is
  cancel-at-period-end;
- §4.1: an activation poll sees the webhook's write immediately (no cache on the local fields).


Proven on the sandbox in the first implementation slice; each changes a §3/§4 branch, not the shape:
- case A or B (proration preview);
- Q2 keep;
- pending-update supersede and clear semantics;
- §4.4 payment method;
- the stable sandbox hostname and its OAuth client (owner).
