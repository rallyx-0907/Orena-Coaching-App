# Billing / Monetization lane — status

Context and rules: `BILLING_LANE.md`. This file holds the lane's live state only; verified facts carry a file
reference. Last verified: 2026-10-13 on `feature/monetization-billing-v1` at `172ae216` (code reading; nothing run).

State: **PLANNED** — inventory done; waiting for the Monetization/Billing Master Brief before the gap comparison
is final.

## What exists (all off by default)

- **Gateway layer** (`writing_coach/billing/`): `Price` in integer minor units; payOS (VietQR, VND only, prepaid,
  HMAC-SHA256 over sorted `data`, no refund API) and Polar (merchant of record, Standard Webhooks with a 5-minute
  tolerance, explicit state map). Signatures were cross-checked against the official SDKs (`BILLING_GATEWAYS.md` §1).
- **`BillingService`** (`billing/service.py`): idempotent checkout per `operation_id`; one live subscription per
  account; a first Polar event attaches only to an Orena order for that account; payOS payment marked paid under the
  account lock with amount/currency/link checks; prepaid access replayed from paid, unrefunded orders as subscription
  `prepaid:<incarnation>`; admin-recorded payOS refund recomputes access.
- **HTTP** (`billing_api.py`): `GET /api/billing/offers`, `POST /api/billing/checkout`,
  `POST /api/billing/webhooks/{gateway}` (no session, 256 KiB), `POST /api/admin/billing/orders/{code}/refund`.
  503 `billing_off` unless `BILLING_ENABLED` + PostgreSQL + account backbone (`app.py:1215-1235`).
- **Schema**: 0006 commerce tables (subscriptions, provider mapping, immutable event receipts) and 0007 quota buckets
  are in `versions/`. `billing_orders` (0027) is **proposed only**.
- **Plans** (`product/catalog.py`): Free / Plus / Pro, USD and VND, monthly and yearly, Admin-editable (D-153). The
  numbers are the design's sample values, not an approved pricing decision. `billing_ready` is hardcoded `False`
  (`product/service.py:146,170`, `product/api.py:98,120`).
- **Quota**: the four bucket meters (`orena.message`, `writing.review`, `pronunciation.audio`, `media.import`) plus
  `languages.target`, enforced server-side and failing closed; the switch is off by default (D-161..D-171, all
  reviews APPROVE).
- **Manual grant**: Admin sets the plan by hand, `provider="manual"`, with an optional end date (D-154).
- **Learner UI**: `#/plan` and `#/plan/pricing` (`static/orena/screens/plan/`), display only; `sheet.js` is the
  Billing Sheet. No checkout or billing endpoint is called anywhere in `static/orena`. The design draws "Plan & usage",
  "Pricing" and "Billing Sheet" (simulated payment steps: form / change / cancel / card / processing / done).
- **Tests**: `tests/test_billing.py`, unit tests with fakes. One PostgreSQL integration test is skipped unless
  `ORENA_TEST_POSTGRES_URL` is set.
- **Review**: delegated review APPROVE WITH CONDITIONS on 2026-10-05, conditions marked met (`BILLING_GATEWAYS.md`
  §6). The independent review of the slice as a whole is still open (§7).

## Gaps (pre-brief)

1. **P0 for activation: payment grants nothing.** Billing writes only `commerce_subscriptions`
   (`commerce_repository.record_event`). The effective plan (`product/service.py:70` →
   `persistence/product_repository.py:45`) and quota (`product/quota.py:640`) read the legacy `subscriptions` table.
   No code bridges them, so a paid order changes no plan. The manual-grant guard (`membership.py:111`) also checks
   only the legacy row, so it cannot see a billing-owned subscription.
2. **Two price sources.** The catalogue (Admin-edited, shown) and `BILLING_PRICES_FILE` (charged) are independent,
   and nothing checks that they agree. `billing_ready` is a constant, not derived.
3. **Silent webhook failures.** `mismatch`, `not_payable`, `unknown_order` and `paid_deleted_account` all answer
   200, leaving only a log line. There is no reconciliation job, alert or Admin view.
4. **Order lifecycle.** `expired`, `cancelled` and `failed` are never written. An abandoned checkout can still be
   paid later. Polar refunds are only logged and never matched to an order. A payOS refund is all-or-nothing.
5. **payOS replay.** There is no timestamp in the signature, so event-id idempotency is the only protection against
   replay.
6. **Cancel / manage.** There is no endpoint. Polar uses its portal; payOS access simply lapses. Return URLs are fixed
   to `/#/profile`.
7. **Activation plumbing.** Billing env names are missing from `.env.example` and `compose.yaml`.
8. **No trial, promo or grace mechanism.** Only the `trialing` status is recognised.
9. **Tax / VAT / invoices for domestic sales.** None in code; this is a human and accountant question.
10. **Stale docs.** `ORENA_COMMERCE_ARCHITECTURE.md` still says Free/Premium. `UI_BACKEND_GAPS.md` BL-1 says the
    design draws no plans, but the 2026-10-08 export draws them.
11. **Admin orders / refunds UI.** The Admin design has no orders frame, so refunds are API only.

## Cross-lane conflicts

| Area | Risk | Handling |
| --- | --- | --- |
| `static/orena/screens/plan/*`, `screens/admin/plans.js` | UI lane owns the learner and Admin surfaces | Billing lane supplies APIs and a `billing_ready` truth; UI wiring of the Billing Sheet is coordinated, not done unilaterally |
| `product/service.py`, `product/api.py` (`billing_ready`, plan resolution) | read by Plan, Profile, quota, Agent | minimal change behind a function; no change to response shapes the UI reads, except `billing_ready` becoming truthful |
| `product/quota.py` | reviewed, protected | consumes the plan resolver unchanged; no quota edits planned |
| `app.py` billing wiring | high-churn shared file | touch only the `_billing` block |
| `migrations/` | 0026 deployment sequencing on `main`; 0028 parented on 0027 | no promotion without review, rehearsal and human approval |
| `CURRENT_HANDOFF.md`, `UI_BACKEND_GAPS.md` BL-1, `AGENTS.md` §3 | shared governance | proposed edits listed here, applied at merge |

## Proposed PR boundaries (pre-brief)

1. **PR-MON-1: entitlement bridge (no schema, no UI).** The effective plan resolves from `commerce_subscriptions`
   by account incarnation when a billing-owned row exists, and from the legacy row (manual grant) otherwise. The
   manual-grant guard sees billing ownership. Off unless billing is on. Needs independent payment/entitlement review.
2. **PR-MON-2: one price truth.** Charged offers are derived from, or validated against, the catalogue at startup;
   `billing_ready` becomes derived (billing on, gateway configured, prices aligned).
3. **PR-MON-3: 0027 and order lifecycle.** Re-review 0027 on the current head; expiry of abandoned orders; Polar
   refund matching; reconciliation and an operator alert for paid-but-not-granted. Schema change goes through review,
   rehearsal and human approval.
4. **PR-MON-4: activation plumbing and Billing sandbox.** Env names in `.env.example` and `compose.yaml`; a
   `:8031` Billing sandbox; end-to-end in gateway test modes. Credentials are a human gate.
5. **PR-MON-5: learner checkout wiring.** Billing Sheet to `/api/billing/checkout` per the design. Coordinated with
   the UI lane; design-fidelity gate.
6. **PR-MON-6: Admin orders / refunds.** Blocked: the design draws no frame. Recorded as a gap.

## First implementation slice (proposed, pending the brief)

PR-MON-1, test first. It is pure code: the bridge, unit tests (billing-owned, manual, expired manual, refunded
prepaid → Free), and a PostgreSQL test in the Billing sandbox when Docker is free. No migration and no UI.

## Human gates (open)

- Approved prices per plan, currency and gateway, and the gateway choice (payOS + Polar, `BILLING_GATEWAYS.md` §1).
- Gateway accounts and credentials; business registration, online.gov.vn notification and tax (§1 conditions).
- Refund, renewal, grace and trial policy text (the `docs/legal` `[DECISION]` placeholders).
- Applying 0026 and 0027 to any runtime; Billing sandbox allocation, if `:8031` conflicts with a plan of yours.
- `quota.abandoned_settles` default (still marked pending in `quota.py:108`).

## Lane decisions

None yet (`D-MON-001` is the next free lane ID).
