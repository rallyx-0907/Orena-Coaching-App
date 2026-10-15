# Billing / Monetization lane — status

**Single resume point for the lane.** Stable direction: `BILLING_LANE.md`. Decisions: `DECISION_LOG.md`. Risks:
`RISK_REGISTER.md`. Facts carry file references.

| | |
| --- | --- |
| Branch | `feature/monetization-billing-v1` |
| Main | PR-MON-5 merged by the human as #207 (`2aa3bd04`, 2026-10-14); the lane branch fast-forwarded onto `origin/main` |
| Last completed slice | PR-MON-5 payOS Credit Top-up: design APPROVED FOR IMPLEMENTATION, migration gate closed, implementation APPROVED (final review on head `c61020d8`, no P0/P1), CI green, merged to `main` as #207 (`2aa3bd04`, 2026-10-14), with the promotion of 0027 -> 0031 -> 0032 -> 0033 (chain head `20261015_0033`) |
| Active PR | none |
| Current slice | **PR-MON-6 migration gate** (`docs/billing/PR-MON-6_MIGRATION_GATE_REVIEW_REQUEST.md`): proposed `migrations/proposed/20261015_0034_funding_admissions.py` on head `20261015_0033` - `funding_admissions` (immutable identity/snapshot, forward-only states checked against the backing reservation, refusal only without an open exact backing), `promotional_grants` (once per `users.id`, ever) with 0007 buckets as their usage, `ai_cost_records.operation_id`/`meter`, the `funding_admission_conflict` item. Design revision 2 APPROVED FOR IMPLEMENTATION / MIGRATION GATE on `418e937e` (2026-10-15). Not promoted, not applied; no feature code before the gate closes |
| Exact next action | independent review of the 0034 migration gate. Separately, operator gate before the next restart of each PostgreSQL runtime: backup -> apply 0027 -> 0031 -> 0032 -> 0033 -> confirm head `20261015_0033` -> smoke/readiness -> restart (runbook, PR #212). Credits stay OFF; R-MON-014 is its own gate |
| Blockers | none for the gate. 0034 is a proposal: promotion and application are human gates. Every PostgreSQL runtime is still at its old head until the operator applies 0027 -> 0033 (no agent applies it). `CREDITS_ENABLED` off; quota/funding enforcement off; R-MON-014 not run (human gates) |
| Test status | PR-MON-6 migration gate, local (not CI): throwaway PostgreSQL 16 - 0034 tests 18 passed; billing PG suites together 165 passed; 0034 mutants 36/36 caught. Last CI: PR #207 head `c61020d8`, all PASS |
| Next human checkpoint | PR-MON-2 architecture-review-ready report. Separate issue #160 (quota PG test order dependence) belongs to the quota/test-infra lane, P2, not a Billing blocker |

## Revised sequence (human, 2026-10-13)

| PR | Scope | State |
| --- | --- | --- |
| PR-MON-1 | **Canonical Effective Entitlement**. One resolver with explicit precedence; Product UI, quota admission and entitlement checks all derive from it. No migration, no checkout UI, no provider config, no credits. | MERGED (#153, `aa016dc1`) |
| PR-MON-2 | **Price Integrity + Runtime Readiness.** One server-side price truth or a strict consistency gate; checkout only at a server-offered price that exactly matches the effective catalogue entry (a mismatch blocks checkout); browser amounts never trusted; `billing_ready` reflects real capability. Closes R-MON-010. | MERGED (#162, `ea68f8a8`) |
| PR-MON-3 | **Billing Orders + Reconciliation Safety.** Re-review/promote 0027; settle 0028's parent explicitly; abandoned-order expiry; durable payment anomaly/reconciliation state; Polar refund matching where safe; payment-without-entitlement detection. Exact webhook HTTP/retry semantics are designed here, per provider. | MERGED (#178, `1a9e010d`) |
| PR-MON-4 | **Prepaid Credit Ledger.** Credit account, append-only ledger, idempotent credit/debit/reversal, deterministic balance, never negative. No commercial credit prices. | MERGED (#193, `985691c7`) |
| PR-MON-5 | **payOS Credit Top-up.** Configured top-up products, checkout, verified webhook, credit exactly once, balance and recent-transactions API. | MERGED (#207, `2aa3bd04`); runtimes await the 0027 -> 0033 operator step |
| PR-MON-6 | **Cost-aware entitlement / Free trial / credits fallback.** `included allowance → prepaid credits → refuse`; reserve → dispatch → settle/release for expensive work; no funded entitlement means no paid provider call; configurable new-user promotional allowances (quantities not invented). | DESIGN APPROVED FOR IMPLEMENTATION / MIGRATION GATE (`418e937e`); migration gate (proposed 0034) in review |
| PR-MON-7 | **Free AI cost routing.** `deterministic/cache/local/free/cheap → premium` for word meaning, contextual Reading explanation, Writing evaluation and Orena Intelligence. Free stays quota-controlled at zero provider price. | PLANNED |
| PR-MON-8 | **Billing runtime / sandbox / E2E.** Separate Billing sandbox (`:8031` if free), env/compose, E2E in gateway test modes. | PLANNED |
| PR-MON-9 | **Learner Billing UI integration.** Wire the existing Billing Sheet, no redesign; coordinated with the UI lane. | PLANNED |
| PR-MON-10 | **Polar lifecycle completion.** Launch-critical gaps only. | PLANNED |
| — | Admin Orders UI | DEFERRED unless launch safety requires it; an auditable API/operator workflow comes first |

Order holds unless a discovered dependency proves it unsafe; record any such change here.

## PR-MON-2 — design (pinned before code)

**Inspected.** The catalogue (`product/catalog.py`) holds the shown price per plan, `monthly`/`yearly` and currency as
a decimal, Admin-editable. The prices file (`BILLING_PRICES_FILE`, `billing/service.load_prices`) holds the charged
price per `plan:period:gateway` in minor units, plus Polar's own price id. Nothing compared them. `billing_ready` was
the constant `False` in `product/service.py` (twice), `product/api.py` (twice), and `admin_console_api.py` said
`"billing": "not_active"`. The frozen mobile contract pins `billing_ready: z.literal(false)`. Startup discovery
(`app._billing_entitlement_source`) returned None both when commerce was not deployed and when the table listing failed.

**Price gate** (`billing/price_integrity.py`, D-MON-015). Exact integer comparison against the strict catalogue read;
one mismatch blocks the whole gateway (offers empty, checkout `price_mismatch` 409); an unreadable catalogue offers
nothing (`catalog_unavailable` 503). The checkout body carries the confirmed `amount_minor` and `currency`
(`price_unconfirmed` 422, `price_changed` 409); they are optional in the schema so the route's 503 off-answer is
unchanged. The prices file is validated harder (paid catalogue plan id, catalogue currency, known gateway, no
duplicates).

**Readiness** (`billing/readiness.py`). `report()` names each blocker; `billing_ready()` is the cached, never-raising
read wired into `ProductService.billing_ready`, `/api/product/plans`, the Admin plan editor and the admin console's
`billing`. `mobile_account_state` pins `false`. `GET /api/admin/billing/readiness` (admin) returns the report: states,
booleans and price checks, no secret.

**Discovery** (`product/entitlement.DiscoveringCommerceSource`, D-MON-016). Present / absent / unreadable, the last
failing closed with a 5 s retry.

**Not in this PR:** migrations (0027 stays proposed, so every runtime reports `orders_schema_absent` and stays not
ready), UI, provider credentials, Polar-side price verification (R-MON-011), credits.

**Tests:** `tests/test_billing_price_integrity.py`; `tests/test_billing.py` moved to canonical plan ids and catalogue
prices.

## PR-MON-1 — design (pinned before code)

**Inspected semantics.**
- The effective plan today is `ProductService.plan_for_user` (`product/service.py:70`), reading the legacy
  `subscriptions` row (`persistence/product_repository.py:45`).
- `account_state` (`service.py:137`) re-derives the same answer with its own copy of the rules.
- Quota (`quota.py:640`) and the language limit (`language_limit.py:108`) call `plan_for_user` through
  `QuotaRuntime.plan_for` (`app.py:1188`).
- Billing writes only `commerce_subscriptions`, through `commerce_repository.record_event`.
- Manual grants (D-154, `membership.py`) live on the legacy row, as `provider="manual"`. Their documented intent is
  that "a subscription another provider owns (billing) is never overwritten by hand" (`membership.py:7`): **billing
  outranks manual**, and an Admin cannot override a paid entitlement. That guard (`membership.py:111`) reads only the
  legacy row, so today it never sees billing. No support/testing override of billing exists or is documented; none is
  added.

**Resolver** (`writing_coach/product/entitlement.py`): `resolve(user_key) -> EffectiveEntitlement`. The fields are
plan id, source, status, active, plan known, valid-until and reconciliation. Precedence:

1. **Billing**: the account's active incarnation's `commerce_subscriptions` row, when its state is `active` or
   `trialing` and its `paid_through` is absent or in the future. An expired `paid_through` reads as `ended`. The
   commerce architecture (§3) says a verified grant is "usable only until its explicit validity boundary".
2. **Manual / legacy**: the legacy row, when active or trialing and not a lapsed manual grant. This is today's rule,
   unchanged.
3. **Free.**

A billing row in `past_due`, `paused`, `pending`, `unknown` or `ended` grants nothing. Grace is unset commercial policy
(architecture §3), so the resolver falls through to 2, then 3. The reported status is the billing state, so the UI
does not show "no subscription". The placeholder row `state='none'` counts as absent.

**One path.** `plan_for_user`, `feature_access`, `account_state`, quota and the language limit all derive from
`resolve()`. The membership guard asks the resolver whether billing owns the account. The read is one query
(`commerce_subscriptions` joined to the active `account_incarnations` row) and never creates an incarnation.

**Wiring.** The billing source is installed when the runtime has PostgreSQL, an active account backbone and the 0006
tables. It is **not** tied to `BILLING_ENABLED`: a recorded paid entitlement must not disappear when checkout is
switched off. With no commerce rows, the answer and the response shapes are identical to today. SQLite and a runtime
without the backbone get no billing source at all. A failing billing read raises, as the legacy read does today:
quota fails closed with 503 and `account_state` reports `available: false`.

**Tests**: `tests/test_effective_entitlement.py`. They cover precedence, the Polar and payOS prepaid cases, lapsed
and refunded cases, manual grants, Free, plan and quota agreement, and billing off. Against PostgreSQL:
`tests/test_effective_entitlement_postgres.py`, which skips without `ORENA_TEST_POSTGRES_URL`.

## What exists (all off by default)

- **Gateway layer** (`writing_coach/billing/`): `Price` in integer minor units. payOS: VietQR, VND, prepaid,
  HMAC-SHA256 over sorted `data`, no refund API. Polar: merchant of record, Standard Webhooks with a 5-minute
  tolerance. Both were cross-checked against the official SDKs (`BILLING_GATEWAYS.md` §1).
- **`BillingService`** (`billing/service.py`):
  - idempotent checkout per `operation_id`, and one live subscription per account;
  - a first Polar event attaches only to an Orena order for that account;
  - a payOS payment is marked paid under the account lock, after checking amount, currency and payment link;
  - prepaid access is replayed from orders as `prepaid:<incarnation>`;
  - an admin-recorded payOS refund recomputes access.
- **HTTP** (`billing_api.py`): offers, checkout, webhooks (no session, 256 KiB) and admin refund. They answer 503
  `billing_off` unless `BILLING_ENABLED` is on with PostgreSQL and the account backbone (`app.py:1215-1235`).
- **Schema**: 0006 (commerce subscriptions, provider mapping, immutable receipts) and 0007 (quota buckets) are in
  `versions/`. `billing_orders` (0027) is proposed only.
- **Plans** (`product/catalog.py`): Free, Plus and Pro in USD and VND, monthly and yearly, Admin-editable (D-153).
  The numbers are the design's sample values. `billing_ready` is hardcoded `False` (`service.py:146,170`,
  `api.py:98,120`).
- **Quota**: four bucket meters plus `languages.target`, enforced server-side, failing closed. Off by default
  (D-161..D-171, all reviews APPROVE).
- **Learner UI**: `#/plan` and `#/plan/pricing` (`static/orena/screens/plan/`) are display only, and `sheet.js` is
  the Billing Sheet. No checkout endpoint is called from `static/orena`. The design draws "Plan & usage", "Pricing"
  and "Billing Sheet".
- **Tests**: `tests/test_billing.py` uses fakes. Its PostgreSQL test skips without `ORENA_TEST_POSTGRES_URL`, and CI
  has no PostgreSQL service.

## Gaps (open)

1. **P0, being fixed by PR-MON-1: a payment grants nothing.** Billing writes `commerce_subscriptions`; the plan and
   quota read the legacy `subscriptions` table.
2. **PR-MON-2: two price sources.** The catalogue (shown) and `BILLING_PRICES_FILE` (charged) are independent.
   `billing_ready` is a constant.
3. **PR-MON-3: verified-but-unapplied money events are only logged.** `mismatch`, `not_payable`, `unknown_order` and
   `paid_deleted_account` all answer 200. Required direction: a durable record, a reconciliation/incident state and
   operator visibility. Transport and security failures (signature, malformed, oversize) are already rejected.
4. **PR-MON-3: order lifecycle.** `expired`, `cancelled` and `failed` are never written. A Polar refund is only
   logged. A payOS refund is all-or-nothing.
5. **PR-MON-3: payOS has no timestamp**, so event-id idempotency is the only protection against replay.
6. **PR-MON-10: cancel / manage.** No endpoint; return URLs are fixed to `/#/profile`.
7. **PR-MON-8: billing env names** are missing from `.env.example` and `compose.yaml`.
8. **PR-MON-4..6: no credits, no trial or promo allowance, no grace.**
9. **Human/accountant: tax, VAT and invoices** for domestic sales.
10. **Stale docs.** `ORENA_COMMERCE_ARCHITECTURE.md` says Free/Premium, and `UI_BACKEND_GAPS.md` BL-1 says no plans
    frame is drawn. Fix proposed at merge.
11. **Deferred: Admin orders / refunds UI.** The design draws no frame.

## Cross-lane conflicts (known)

| Area | Risk | Handling |
| --- | --- | --- |
| `static/orena/screens/plan/*`, `screens/admin/plans.js` | owned by the UI lane | no edits until PR-MON-9; this lane supplies APIs and a truthful `billing_ready` |
| `product/service.py` (`plan_for_user`, `account_state`) | read by Plan, Profile, quota, Agent, language limit | PR-MON-1 changes the resolution path, not response shapes |
| `product/membership.py` guard | Admin plans/accounts screen behaviour | the guard sees billing ownership: an Admin set-plan on a billing-owned account becomes 409, as D-154 intends |
| `product/quota.py`, `language_limit.py` | reviewed, protected | unchanged; they consume `plan_for_user` |
| `app.py` | high-churn shared file | PR-MON-1 adds one wiring call next to the quota block |
| `migrations/` | 0026 deployment sequencing on `main`; proposed 0028 is parented on 0027 | nothing promoted until PR-MON-3 review, rehearsal and human approval |
| `CURRENT_HANDOFF.md`, `UI_BACKEND_GAPS.md` BL-1, `AGENTS.md` §3 | shared governance | edits proposed here, applied at merge |

## Migration dependency

The head is `20261005_0026`, parented on 0030. Proposed `0027_billing_orders` is parented on 0026, and proposed
`0028_reading_derived_texts` is parented on 0027. If 0027 is promoted, 0028 must either be re-parented on 0027 in
`versions/` (and that 0027 promotion goes first), or 0028 is promoted first and 0027 is re-parented on it. PR-MON-3
decides this with the Reading owner. PR-MON-1 to PR-MON-2 need no migration. PR-MON-4/5 (credit ledger) will need
one: it is proposed, reviewed and human-approved like 0027.

## Human gates (open; engineering does not wait on them)

- Final Plus and Pro prices; credit conversion; credit cost per meter; exact Free and trial allowances.
- Refund, renewal and grace policy (the `docs/legal` `[DECISION]` placeholders).
- Production provider credentials; business registration, online.gov.vn notification, tax and legal.
- Applying any migration (0026, 0027, the credit ledger) to any runtime; production billing activation.
- Billing sandbox allocation, if `:8031` collides.
- `quota.abandoned_settles` default (`quota.py:108`, still pending).

## Lane decisions

Recorded append-only in `DECISION_LOG.md` (D-MON-001..D-MON-009). Residual risks: `RISK_REGISTER.md`.
