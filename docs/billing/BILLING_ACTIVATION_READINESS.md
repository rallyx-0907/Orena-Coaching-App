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

Updated 2026-10-18.

## 1. Money and access lifecycle

| # | Item | State | Evidence |
| --- | --- | --- | --- |
| 1 | Checkout, Polar hosted page | proven | `PR-MON-10_E2E_EVIDENCE.md` step 1 |
| 2 | Checkout, embedded in the app | proven | `PR-MON-9_E2E_EVIDENCE.md` §2 (first purchase through the embed) |
| 3 | Webhook signature: unsigned or bad signature, stale timestamp, oversize | proven + tested | unsigned POST through the tunnel answered 401 (PR-MON-10); `tests/test_billing.py` (`test_polar_an_unsigned_stale_or_altered_webhook_is_rejected`) |
| 4 | Purchase → plan granted only by the webhook (the return page grants nothing) | proven | PR-MON-10 step 1; PR-MON-9 §2 ("You're on Plus" only once the server showed `plus · active`) |
| 5 | Upgrade, immediate (`invoice` proration) | proven | PR-MON-9 §1 step A (in-app); PR-MON-10 step 3 (portal) |
| 6 | Downgrade **in the app** = cancel at period end (scheduled downgrade off) | proven | PR-MON-9 §1 and §2 |
| 7 | Downgrade **in Polar's portal** (Pro → Plus, applied at once with `invoice`) | **open** | the portal allows plan changes between the four products; only an upgrade has been observed. Needs an owner run on the sandbox. |
| 8 | Cancel at period end: the plan stays until the end | proven | PR-MON-10 step 3; PR-MON-9 §2 |
| 9 | Cancel at period end: the plan **ends** at the period end | **observing** | daily test subscription A (§3), period end 2026-10-19 18:32 (UTC+7) |
| 10 | Renewal: `paid_through` moves to the next period | **observing** | daily test subscription B (§3); see risk R1 |
| 11 | Failed renewal → `past_due` → grace → `ended` | tested, **open** on the sandbox | hermetic (`unpaid` → `ended`, `past_due` keeps the grace). Sandbox run needs owner approval (a test card that attaches but fails later). |
| 12 | Refund | proven | PR-MON-10 step 6 (recorded, matched, auto-resolved; access follows the subscription) |
| 13 | Immediate revocation → `ended` | proven | PR-MON-10 step 4 |
| 14 | Deleted account: Polar customer clean-up; events after deletion rejected | proven | PR-MON-10 steps 7, 7b and 7c |
| 15 | Price mismatch with Polar closes sales | proven | PR-MON-10 step 8 |

## 2. Failure cases

| # | Item | State | Evidence |
| --- | --- | --- | --- |
| 16 | Duplicate and out-of-order webhooks | proven + tested | PR-MON-10 step 1 (two `stale` receipts with the same `modified_at`); `reference_backbone.subscription_event_decision` |
| 17 | In-app change, cancel or resume where Polar's answer is lost | tested | `tests/test_billing_polar_subscription.py` and `tests/test_billing_polar_postgres.py` (journal, per-subscription fence, `modified_at` rule, one PATCH under real CAS races) |
| 18 | Polar's `modified_at` is empty after a scheduled change | **found 2026-10-18** | risk R1 |

**Risk R1 (open, being observed).** Orena orders a subscription's webhooks by Polar's `modified_at`, falling back to
`created_at` (`billing/polar.py`). Equal or older events are `stale`.
- The daily test showed that a scheduled change leaves `modified_at` empty, while a cancel sets it.
- If a **renewal** also left `modified_at` empty, the renewal event would carry the same version as the creation
  event and be dropped as `stale`. `paid_through` would not move, and a paying learner would lose the plan after the
  first period.
- Subscription B's renewal on 2026-10-19 shows whether Polar sets `modified_at` on renewal. If it does not, the
  version must be fixed (for example, from the current period start) before gate 7b, with independent review.

## 3. The period-end run (owner-approved 2026-10-18)

Two **test** daily products exist on the Polar sandbox: "TEST Daily High" ($2/day) and "TEST Daily Low" ($1/day).
The four real products are untouched.

| Subscription | What was done | Expected reading at the period end |
| --- | --- | --- |
| A | downgrade to Low scheduled (`next_period`), then cancel at period end | ends: cancel wins. Switched to Low and charged $1: the pending change wins. |
| B | downgrade to Low scheduled only | renews on Low and is charged $1. Its `modified_at` answers R1. |

The result goes into `PR-MON-9_E2E_EVIDENCE.md`. It decides `SCHEDULED_CHANGES`, which stays off until then.

## 4. Screens

| # | Item | State | Evidence |
| --- | --- | --- | --- |
| 19 | Plan & usage and Pricing with billing **on** | proven | PR-MON-9 §2 (desktop, phone, EN/VI/ZH, light and dark) |
| 20 | Plan & usage and Pricing with billing **off** (offers empty, `billing_ready: false`) | tested; browser **open** | `scripts/test_orena_screen_plan.mjs`. Browser check on the pilot build (`:8000`) by the UI lane. |

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
| `APP_ENV` | `production` |
| `PUBLIC_BASE_URL` | the public HTTPS origin |
| Google sign-in | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `SESSION_SECRET` |

**Must stay off:** `CREDITS_ENABLED`, `BILLING_CREDIT_PACKS_FILE`, every `SEPAY_*` and `PAYOS_*` variable, quota and
funding enforcement.

**Fixed 2026-10-18.** `compose.yaml` did not pass any `BILLING_*` or `POLAR_*` variable to the web container, so
setting them in the host's `.env` changed nothing. They are now passed through, empty by default (test:
`test_the_web_service_receives_the_plans_billing_configuration_off_by_default`).

## 6. Human gates before billing can be turned on

1. **Migrations.** Apply `0027` → `0033` on the pilot's PostgreSQL after a verified backup
   (`RUNBOOK_MIGRATION_0027_0033.md`). Without them readiness reports `orders_schema_absent`, and nothing can be
   sold. This can be done while billing stays off.
2. **Production host.** The host is named as production for gate 7b, on a public HTTPS origin (the runbook does not
   apply to `:8000` unless the owner names it).
3. **Polar production setup:**
   - the four products, the customer portal settings, and a token with the 8 scopes;
   - the webhook with its events;
   - the Embedding allowlist, which must hold the production origin.
4. **Commercial and legal:**
   - final prices;
   - the refund, renewal and grace policy;
   - tax.
5. **Gate 7b itself.** Readiness `ready: true`, then the owner's first real subscription (runbook §4-§5).
