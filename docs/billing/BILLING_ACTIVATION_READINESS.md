# Billing: ready-to-enable list (PRE-406)

**Purpose.** For the pilot, billing stays **off**. It must be ready so that turning it on (gate 7b,
`RUNBOOK_POLAR_ACTIVATION.md`) works the first time. This list says, item by item, what has evidence and what does
not. Plans only: Polar card subscriptions for Plus and Pro. Credits, SePay and payOS (gate 7a) are not part of it.

**Status legend:**
- **proven**: run on the Polar sandbox with evidence;
- **tested**: hermetic or PostgreSQL tests only;
- **observing**: a sandbox run is in progress;
- **open**: not yet done;
- **human**: a human gate.

Updated 2026-10-19.

## 1. Money and access lifecycle

| # | Item | State | Evidence |
| --- | --- | --- | --- |
| 1 | Checkout, Polar hosted page | proven | `PR-MON-10_E2E_EVIDENCE.md` step 1 |
| 2 | Checkout, embedded in the app | proven | `PR-MON-9_E2E_EVIDENCE.md` §2 (first purchase through the embed) |
| 3 | Webhook signature: unsigned or bad signature, stale timestamp, oversize | proven + tested | unsigned POST through the tunnel answered 401 (PR-MON-10); `tests/test_billing.py` (`test_polar_an_unsigned_stale_or_altered_webhook_is_rejected`) |
| 4 | Purchase → plan granted only by the webhook (the return page grants nothing) | proven | PR-MON-10 step 1; PR-MON-9 §2 ("You're on Plus" only once the server showed `plus · active`) |
| 5 | Upgrade, immediate (`invoice` proration) | proven | PR-MON-9 §1 step A (in-app); PR-MON-10 step 3 (portal) |
| 6 | Downgrade **in the app** = cancel at period end (scheduled downgrade off) | proven | PR-MON-9 §1 and §2 |
| 7 | Downgrade **in Polar's portal** (Pro → Plus, applied at once with `invoice`) | proven | sandbox subscription D, 2026-10-18 (owner run): Polar applied Plus at once and Orena followed it (`plus · active`). Its renewal on Plus is observed in §3. |
| 8 | Cancel at period end: the plan stays until the end | proven | PR-MON-10 step 3; PR-MON-9 §2 |
| 9 | Cancel at period end: the plan **ends** at the period end | proven | sandbox A, 2026-10-19: `canceled` at the period end, no charge, even with a pending change (`PR-MON-9_E2E_EVIDENCE.md` §3) |
| 10 | Renewal: `paid_through` moves to the next period | proven | sandbox D, 2026-10-19: Orena `paid_through` moved one day; the renewal receipt `applied` (R1 closed) |
| 11 | Failed renewal → `past_due` → grace → `ended` | `past_due` + grace **proven**; the end tested | hermetic (`unpaid` → `ended`, `past_due` keeps the grace). Sandbox subscription F (owner-approved 2026-10-18): its card was changed to a test card that declines, renewal on 2026-10-19 (§3). |
| 12 | Refund | proven | PR-MON-10 step 6 (recorded, matched, auto-resolved; access follows the subscription) |
| 13 | Immediate revocation → `ended` | proven | PR-MON-10 step 4 |
| 14 | Deleted account: Polar customer clean-up; events after deletion rejected | proven | PR-MON-10 steps 7, 7b and 7c |
| 15 | Price mismatch with Polar closes sales | proven | PR-MON-10 step 8 |

## 2. Failure cases

| # | Item | State | Evidence |
| --- | --- | --- | --- |
| 16 | Duplicate and out-of-order webhooks | proven + tested | PR-MON-10 step 1 (two `stale` receipts with the same `modified_at`); `reference_backbone.subscription_event_decision` |
| 17 | In-app change, cancel or resume where Polar's answer is lost | tested | `tests/test_billing_polar_subscription.py` and `tests/test_billing_polar_postgres.py` (journal, per-subscription fence, `modified_at` rule, one PATCH under real CAS races) |
| 18 | Polar's `modified_at` is empty after a scheduled change | **closed 2026-10-19** | risk R1: renewal sets it |

**Risk R1 (closed 2026-10-19, no code change).**
- Orena orders a subscription's webhooks by Polar's `modified_at`, falling back to `created_at`
  (`writing_coach/billing/polar.py`). Equal or older events are `stale`.
- On 2026-10-18, a scheduled change left `modified_at` empty, while a cancel set it. A renewal with an empty
  `modified_at` would have been dropped as `stale`, and a paying learner would have lost the plan after the first
  period.
- On 2026-10-19, Polar set `modified_at` at renewal (sandbox B), and Orena applied D's renewal: `paid_through`
  moved one day (`PR-MON-9_E2E_EVIDENCE.md` §3).

## 3. The period-end run (owner-approved 2026-10-18)

Two **test** daily products exist on the Polar sandbox: "TEST Daily High" ($2/day) and "TEST Daily Low" ($1/day).
The four real products are untouched.

| Subscription | What was done | Expected reading at the period end |
| --- | --- | --- |
| A | downgrade to Low scheduled (`next_period`), then cancel at period end | ends: cancel wins. Switched to Low and charged $1: the pending change wins. |
| B | downgrade to Low scheduled only | renews on Low and is charged $1. Its `modified_at` answers R1. |
| D | Pro → Plus in Polar's portal (daily test products, through the `:8031` sandbox) | renews on Plus. Orena's `paid_through` moves: R1 in Orena itself. |
| F | card changed to a declining test card | renewal fails: `past_due` on Polar, grace in Orena (item 11). |

**Results (2026-10-19), detailed in `PR-MON-9_E2E_EVIDENCE.md` §3:**
- A ended at the period end: cancel wins over a pending change.
- B renewed on Low and was charged $1, with `modified_at` set.
- D renewed on Plus for $0.11: the unused Pro part was credited, and Orena's `paid_through` moved.
- F is `past_due` on both sides, with Orena's grace counted from the failed charge.

`SCHEDULED_CHANGES` stays off until the owner asks for scheduled downgrades. The blocker that kept it off (which change wins) is now answered.

## 4. Screens

| # | Item | State | Evidence |
| --- | --- | --- | --- |
| 19 | Plan & usage and Pricing with billing **on** | proven | PR-MON-9 §2 (desktop, phone, EN/VI/ZH, light and dark) |
| 20 | Plan & usage and Pricing with billing **off** (offers empty, `billing_ready: false`) | tested; browser **open** | `scripts/test_orena_screen_plan.mjs`. Browser check on the pilot build (`:8000`) by the UI lane. |
| 21 | Prices and limits shown = the approved catalogue (PRE-401) | **checked on `:8000`** (2026-10-19, image `orena:main-9952152a`) | see below |

**PRE-401, read 2026-10-19 (read only, no sign-in).** The approved catalogue is
`writing_coach/product/catalog.py`:
- prices: D-MON-032, USD Plus 9.99/79.99 and Pro 19.99/159.99;
- assist limits: D-MON-025;
- the other meters: catalogue v2 (D-161).

`:8000` stores no `product.plan_catalog` row in `platform_settings`, so it shows the code's defaults.

| | `main` (this lane's sandbox) | `:8000` (image `orena:main-9bf88666`, built 2026-10-11) |
| --- | --- | --- |
| Prices | USD as above | the same numbers |
| Currency shown | USD in every interface language (`PLAN_CURRENCY`, `screens/plan/model.js`): the amount Polar charges | **dong to a Vietnamese interface** (199,000 ₫ for Plus), dollars otherwise |
| Messages, reviews, pronunciation, import, languages | Free / Plus / Pro: 20/200/1000, 2/10/50, 5/30/120 min, 15/120/600 min, 1/2/2 | the same |
| Word, reading and writing assist (per day) | 30/300/1500, 10/100/500, 5/30/100 | **absent** (the build predates D-MON-025) |

Billing is off on `:8000`, so nobody is charged there. Even so, gate 7b must run on a build from `main`. On the
current `:8000` build, a Vietnamese learner would see a dong price and be charged dollars by Polar. The next `:8000`
deploy fixes both. Re-read the table after that deploy.

**Re-read after the deploy (2026-10-19; `:8000` on `orena:main-9952152a`, schema `20261018_0035`; read only).**
- No `product.plan_catalog` row is stored, so the code's catalogue applies. Its prices and every limit above match
  `main`, including the assist limits.
- `orena.voice` is 900 s (15 min) a day for Plus and Pro, and off for Free (D-235 to D-237).
- `PLAN_CURRENCY` is USD in every language.
- `BILLING_ENABLED` is unset.
- `ORENA_QUOTA_ENFORCEMENT=on`, with `ORENA_QUOTA_METERS` = `writing.review`, `orena.message`, `pronunciation.audio`, `media.import`, `languages.target`, the same list as gate 7b C6; the assist meters are not in the list (gate 7b C6).

PRE-401 is closed.

The owner decided on 2026-10-19 that voice chat with Orena is for Plus and Pro only, not Free (D-235 to D-237).
The re-read above checks it on `:8000`.

## 5. Configuration for the pilot host (names only)

The pilot host keeps billing **off**: every variable below is empty, or not set.

| Variable | At gate 7b |
| --- | --- |
| `BILLING_ENABLED` | `on` |
| `BILLING_NEW_SALES` | empty (on); `off` is the safe rollback |
| `BILLING_PRICES_FILE` | `/data/billing/prices.json` (the four Polar product ids; runbook §3) |
| `BILLING_DOMESTIC_GATEWAY` | empty |
| `POLAR_ACCESS_TOKEN` | the production token (8 scopes) |
| `POLAR_WEBHOOK_SECRET` | the production webhook secret |
| `POLAR_ENVIRONMENT` | `production` |
| `ORENA_ACCOUNT_BACKBONE` | `on` |
| `APP_ENV` | unchanged: a public value, not `development` (`staging` on `:8000`; plans need no `production`) |
| `PUBLIC_BASE_URL` | the public HTTPS origin |
| Google sign-in | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `SESSION_SECRET` |

**Must stay off:** `CREDITS_ENABLED`, `BILLING_CREDIT_PACKS_FILE`, every `SEPAY_*` and `PAYOS_*` variable, quota and
funding enforcement.

**Where they go.**
- **`:8000`:** `runtime.env`, read by `scripts/staging_8000_deploy.ps1` (`docker run --env-file`), at step R6
  of the `:8000` package. `:8000` is not started by compose.
- **Compose hosts:** `compose.yaml` did not pass them. It does now, empty by default (#295, test
  `test_the_web_service_receives_the_plans_billing_configuration_off_by_default`).
- **`POLAR_ENVIRONMENT`:** empty means sandbox, so it must be set to `production` explicitly.

## 6. Human gates before billing can be turned on

1. **Migrations.** Apply `0027` → `0033` on the pilot's PostgreSQL after a verified backup
   (`RUNBOOK_MIGRATION_0027_0033.md`). Without them readiness reports `orders_schema_absent`, and nothing can be
   sold. This can be done while billing stays off.
2. **Production host: decided.** On 2026-10-18 the owner named `:8000` as the host for gate 7b, at
   `https://orena.chillpickle.org`. On the same day, with billing off, `/api/health` answered 200 there and
   the Polar webhook route answered 503 `billing_off`, as expected.
3. **Polar production setup:**
   - the four products, the customer portal settings, and a token with the 8 scopes;
   - the webhook with its events;
   - the Embedding allowlist, which must hold the production origin.
4. **Commercial and legal:**
   - final prices;
   - the refund, renewal and grace policy, **in the public English Terms before any charge**. The current Terms promise
     this. `PAID_PLANS_TERMS_DRAFT.md` is the draft. Legal text is English only (owner, 2026-10-19); no vi/zh
     version is required;
   - tax: Polar is the merchant of record (D-MON-032);
   - **open, before real sales:** what counts as "data that only a paid plan provides". The Terms say it may be deleted
     3 months after a paid plan ends (D-MON-035). A deletion job also needs approval, since deletion is a human gate.
     Until both exist, nothing is deleted, so "kept for at least 3 months" already holds.
5. **Gate 7b itself.** Readiness `ready: true`, then the owner's first real subscription (runbook §4-§5).

## 7. One approval for gate 7b (prepared; waits for the owner)

The owner approves every write to Polar **production** in one list. Nothing on it has been done. The ordered
checklist, with a check and a rollback per step, is `GATE_7B_APPROVAL_PACKAGE.md`.

**Precondition:** R1 is resolved: done 2026-10-19, no code change (§2-§3). (Had Polar left `modified_at` empty at
renewal, a reviewed code fix would have landed first.) `:8000` runs a build from `main`: done, `9952152a` (item 21).

**Polar production (owner).**

| # | Write | Value |
| --- | --- | --- |
| P1 | Create 4 products, one fixed USD price each, no trial, no Polar benefits | Plus 9.99/month, Plus 79.99/year, Pro 19.99/month, Pro 159.99/year (the catalogue; final prices are the owner's call). Each description says **voice chat with Orena is included** (runbook §1.1); Orena grants it from its own catalogue |
| P2 | Customer portal | customer updates on; plan change between the four; proration `invoice` |
| P3 | Organization access token | exactly the 8 scopes in the runbook §1.3. The owner creates it and pastes it into `runtime.env`; it never goes through chat |
| P4 | Webhook endpoint | `https://orena.chillpickle.org/api/billing/webhooks/polar`, Raw. Events: `subscription.*`, `order.paid`, `refund.created`, `refund.updated` |
| P5 | Embedding allowlist | `https://orena.chillpickle.org` |

**`:8000`.** Step R6 of the package: `runtime.env` and the prices file. A deploy is an owner gate.

| Name | Value |
| --- | --- |
| `BILLING_ENABLED` | `on` |
| `BILLING_NEW_SALES` | `off` first: everything runs, nothing is sold. Empty when the owner opens sales |
| `BILLING_PRICES_FILE` | `/data/billing/prices.json`, with the four P1 product ids |
| `POLAR_ENVIRONMENT` | `production` |
| `POLAR_ACCESS_TOKEN` / `POLAR_WEBHOOK_SECRET` | from P3 and P4 |
| `APP_ENV` | unchanged: a public value, not `development` (`staging` on `:8000`; plans need no `production`) |
| `PUBLIC_BASE_URL` | `https://orena.chillpickle.org` |
| `ORENA_ACCOUNT_BACKBONE` | `on` |

**Verified with no money taken** (sales paused):
- readiness shows `capabilities.plans` ready with no blockers, and the top level blocked only by `new_sales_paused`;
- `provider_prices: match` against the P1 products;
- an unsigned POST to the webhook answers 401.

**Verified only by a real purchase** (the owner's first subscription, runbook §5):
- the customer portal (it needs a subscription);
- Plan & usage and Pricing with sales open (sales cannot be opened for one account only).
