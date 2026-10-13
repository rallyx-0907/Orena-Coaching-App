# PR-MON-1 Canonical Effective Entitlement — independent architecture review request

The change is payment/entitlement, so `AGENTS.md` §1 requires independent architecture review: the implementer
may not approve it. Record the reviewer, the reviewed commit and the verdict in Git, in
`docs/reviews/architecture/PR_MON_1_ENTITLEMENT_REVIEW_<date>.md`.

| | |
| --- | --- |
| Branch | `feature/monetization-billing-v1` |
| Base | `main` `172ae216` |
| Change | commit `0a440695` (code and tests); lane docs `b161c74f`, `c804600d` |
| Decision under review | D-MON-006, as amended by D-MON-010 (billing over manual, confirmed) and D-MON-011 (Polar past-due grace, 2 days) |
| Schema | none |
| Runtime effect with no commerce rows | none (proved by the regression oracle, below) |

## Problem

`BillingService` writes access only to `commerce_subscriptions` (`persistence/commerce_repository.record_event`).
Before this change, every plan reader used the legacy `subscriptions` row instead:
`ProductService.plan_for_user` (`product/service.py`), `account_state`, quota (`product/quota.py:640`), the
language limit (`product/language_limit.py:108`) and the D-154 Admin guard (`membership.py:111`). A verified
payment therefore changed no plan, and the manual-grant guard could not see billing ownership.

## Change

1. `writing_coach/product/entitlement.py` (new):
   - **`resolve(legacy, billing, now)`**: pure, with the precedence in the module docstring.
   - **`EffectiveEntitlement`**: the decision.
   - **`CommerceEntitlementSource`**: the PostgreSQL billing read.
2. `ProductService.entitlement(user_key)` does the two reads and calls `resolve`. `plan_for_user` and
   `account_state` derive from it, and the duplicated status/plan logic is removed. Response shapes are unchanged.
3. `PostgresCommerceRepository.subscription_for_account(account_id)` is one query: `commerce_subscriptions`
   joined to the account's **active** `account_incarnations` row. It never creates an incarnation, and a deleted
   incarnation's subscription is not the account's.
4. `app.py` installs the source (`configure_product_billing`) when the runtime has PostgreSQL, an active account
   backbone and the tables `commerce_subscriptions`, `commerce_billing_event_receipts` and `account_incarnations`.
5. Admin membership: `product/api.py` adds `billing_aware_membership`, which overlays the billing plan, status and
   provider plus `billing_owned`. The guard in `membership.apply_change` refuses a hand-set plan when
   `billing_owned` is true (409).

## Semantics to review

| Case | Effective | Status reported |
| --- | --- | --- |
| billing `active`/`trialing`, `paid_through` absent or > now | billing plan | billing state |
| billing granting state, `paid_through` ≤ now | falls through | `ended` |
| Polar `past_due`, now < `paid_through` + 48 h (policy) | billing plan | `past_due` |
| Polar `past_due` past the grace, or with no `paid_through` | falls through (manual/legacy, else Free); still billing-owned | `past_due` |
| billing `paused`/`pending`/`unknown`/`ended`, or `past_due` on a provider without grace | falls through | billing state |
| billing placeholder `state='none'` | treated as absent | legacy rule |
| valid billing **and** valid manual grant | **billing** (even if manual ranks higher) | billing state |
| manual grant, end date passed | Free | `active` (as before) |
| unknown plan id on a granting record | admits as Free, `plan_state: unknown` (as before for legacy) | |

## Questions for the reviewer

1. **Billing outranks manual.** The human settled this (D-MON-010); no override is built. Review only that the
   implementation matches it.
2. **Grace anchor** (D-MON-011, human: 2 days).
   - Polar advances the cycle before charging, so the adapter (`billing/polar.py`, `_paid_through`) records a
     past-due event's `paid_through` as `past_due_at`, else `current_period_start`, else none. With none, the
     commerce record keeps the last paid end.
   - The grace is `paid_through` + `BILLING_PAST_DUE_GRACE_HOURS` (`product/billing_grace.py`). The resolver only
     takes the policy as an input.
   - `subscription.past_due` is now a handled event.
   - Is the anchor right, given Polar's docs (public failed-payments page)? Is "environment, not Admin" acceptable
     for v1 (R-MON-008)?
3. **Install by store presence, not by `BILLING_ENABLED`.** A recorded paid entitlement keeps applying when
   checkout is switched off. If `BILLING_ENABLED` should also act as a kill switch for entitlements, say so.
4. **Startup table read.** If the table listing fails at startup, no source is installed. Paid accounts would then
   read the legacy row (Free) rather than 503. The quota store uses the same startup pattern; should this one fail
   closed instead?
5. **Guard race.** The billing-ownership check is a pre-check outside the membership transaction. A payment landing
   between check and write leaves a shadowed manual row, which is harmless under the precedence. Is that
   acceptable, or should `apply_membership` take the incarnation lock?
6. **Status for a lapsed grant.** `active` with `paid_through` passed reports `ended`, a derived state rather
   than the stored one. Acceptable for the Plan screen and `accountCommerce`?

## Change (amendment, D-MON-011)

6. `writing_coach/product/billing_grace.py` (new) holds `GracePolicy`, `current(env)` and the range-checked
   environment hours. The default is 48; 0 means no grace; an invalid value falls back to 48 and is logged.
7. `entitlement.resolve(..., grace=)`: a recoverable state grants until `paid_through` + its window. A live
   non-granting state past `paid_through` is no longer turned into `ended`, because Polar is still retrying.
8. `ProductService(grace=...)` and the Admin wrapper pass the policy.
9. `billing/polar.py`: handles the `subscription.past_due` event and the past-due `paid_through` rule above.

## Evidence (local execution, not CI)

- `tests/test_effective_entitlement.py`, 37 tests. They cover:
  - payOS prepaid, Polar, trialing, no boundary, manual valid and expired, ended and placeholder billing rows;
  - a lapsed `paid_through`, a fully refunded prepaid account, the four no-grace states, an unknown plan id;
  - precedence in four directions, and the pure resolver;
  - the Plan screen reading billing, one read per record;
  - **plan, quota (429 context `plan`) and language limit agreeing on a paid plan**;
  - billing store failure failing closed;
  - a **billing-off regression oracle**: without a source, or with an empty one, answers equal the pre-change rule,
    restated independently, and `account_state` is identical;
  - the app installing no source on SQLite;
  - the Admin guard refusing for all five live states, the Admin read showing the billing plan, and Admin still
    allowed when billing owns nothing.
- **Mutation checks:**
  - With the billing read disabled (today's P0), 17 tests fail.
  - With the precedence flipped (manual before billing), 3 tests fail: both precedence tests and the agreement test.
- **Targeted regression:** the product, commerce, membership, plans-transaction, quota-gate, language-limit,
  billing, persistence-runtime, admin-policies and product-foundation suites. Result: 314 passed, 7 skipped
  (PostgreSQL), with the `ai-writing-coach:local` image on SQLite.
- **PostgreSQL proof**: a throwaway PostgreSQL 16 (tmpfs, private network, no published port, removed
  afterwards), upgraded to head. 432 passed, 0 skipped. That run covers:
  - `tests/test_effective_entitlement_postgres.py`: prepaid, refund, Polar, a deleted incarnation, the Admin guard;
  - the existing `test_quota_gate_postgres.py`, `test_language_limit_postgres.py`,
    `test_orena_commerce_persistence_postgres.py` and `test_billing.py` (including its PostgreSQL test);
  - `test_admin_authorization_matrix.py`, and the unit file again.
- Ruff is clean on the new code. Four UP017 findings in `membership.py` predate this change.
