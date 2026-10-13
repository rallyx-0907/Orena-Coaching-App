# PR-MON-1 Architecture Review

Recorded verbatim from the reviewer's verdict (relayed by the human, 2026-10-13). The fix response is at the end.

Reviewer: ChatGPT — independent reviewer
Reviewed branch: `feature/monetization-billing-v1`
Reviewed HEAD: `c70032a00c91390b0d3e24968218b52b638e8694`
Baseline: `172ae216397e6dfaa1f74aa32417f48b7c2365fd`

## Verdict

**REQUEST CHANGES**

No P0.

Two P1 findings must be fixed before merge.

### P1-1 — Live billing state incorrectly falls through to manual entitlement

The approved D-MON-011 policy says that after Polar `past_due` exceeds the grace window, the effective entitlement becomes Free while the account remains billing-owned.

Current resolver instead falls through to an active manual/legacy subscription whenever the billing row does not grant.

This means:

`Polar past_due > 48h + old manual Pro → effective Pro`

rather than:

`Polar past_due > 48h → Free, billing_owned=true`.

Required invariant:

**A billing relationship that is still LIVE but temporarily/non-permanently grants no entitlement must suppress manual/legacy fallback.**

Manual/legacy may become effective again only when the billing relationship is genuinely ended/absent according to the billing state model.

Update tests accordingly, including:
- past_due outside grace + active manual → Free
- paused/pending billing-owned account + active manual → Free unless product policy explicitly defines otherwise
- ended billing + active manual → manual may resume according to the existing policy
- billing_owned remains true while the live billing state suppresses manual.

### P1-2 — Admin/manual grant has a TOCTOU race with billing ownership

`billing_aware_membership` performs the commerce billing ownership check before the membership write transaction.

The underlying PostgreSQL `apply_membership()` locks/rechecks the legacy `subscriptions` row but does not atomically re-check the commerce billing subscription.

Therefore:

1. Admin reads no billing ownership.
2. Payment/webhook activates billing.
3. Admin write still creates a manual subscription.
4. Billing currently shadows it.
5. When billing eventually ends, that stale manual grant can become effective without a new Admin decision.

This is not an acceptable harmless shadow row.

Required invariant:

**If billing acquires ownership before the manual membership write commits, the manual plan mutation must be rejected and no manual subscription row may be created/updated.**

Implement the transactional ownership re-check using the existing PostgreSQL/account/incarnation locking model.

Add a PostgreSQL regression test proving this race cannot produce a latent manual grant.

## P2 — Startup billing-source discovery can silently fall back to legacy

An unreadable table inspection currently results in no billing source being installed, which is indistinguishable from an intentionally billing-less deployment.

This can make an already-paid account read from legacy state for the process lifetime.

Accepted for PR-MON-1 while real billing remains disabled, but must be resolved as part of PR-MON-2 runtime readiness before production billing activation.

Production must distinguish:

`commerce intentionally unavailable/not deployed`

from

`commerce expected but unreadable`

and fail safely in the latter case.

## P2 — Polar past-due payload field needs sandbox confirmation

The current public Polar subscription webhook contract exposes `current_period_start/current_period_end`; the reviewed adapter additionally accepts `past_due_at`.

The fallback to `current_period_start` makes this non-blocking.

Keep R-MON-009 and verify the real Polar sandbox payload before production activation.

## Approved portions

No blocker found in:

- canonical `EffectiveEntitlement` abstraction;
- billing > manual precedence for a valid granting billing entitlement;
- payOS prepaid entitlement;
- refund → Free path;
- account-incarnation scoped commerce lookup;
- billing entitlement surviving `BILLING_ENABLED=off`;
- quota and language-limit consumption of the canonical plan resolver;
- Polar 48-hour grace as configurable policy;
- provider event stale/out-of-order protection through object versioning;
- derived `ended` state after an active grant passes `paid_through`.

## Re-review requirement

Do **not** repeat the entire architecture review.

Fix P1-1 and P1-2, add the required regression tests, then return only:

- the fixing commit SHA(s);
- diff for the two findings;
- relevant PostgreSQL/test results.

A focused verification of those two findings is sufficient before approval.

---

## Fix response (implementer, 2026-10-13) — for focused re-verification

The fixing commit SHA is in `docs/billing/BILLING_STATUS.md` and the lane's `git log`. The commit is titled
"fix(billing): PR-MON-1 review P1-1 and P1-2".

**P1-1** (`writing_coach/product/entitlement.py`):
- Billing releases the account only when its effective state is `ended` (including a granting state past
  `paid_through`) or the row is absent (no row, or the `none` placeholder).
- Every other state is billing-owned: `past_due` outside its grace, `paused`, `pending`, `unknown` and any
  unrecognised value. In those states the result is Free, `source="billing"`, `billing_live=True`, and the
  manual/legacy row is **not consulted**.
- The rule is one predicate, `billing_owns(state)`, which the Admin pre-check and the transactional re-check also
  use, through `resolve(...).billing_live`.

**P1-2** (`writing_coach/persistence/product_repository.py`, `apply_membership`):
- For any plan change, inside the membership transaction, `users` is locked `FOR UPDATE`. Then the account's
  active `account_incarnations` row is locked `FOR NO KEY UPDATE`, and `commerce_subscriptions` is read and decided
  with the same predicate.
- A billing owner means `MembershipConflict` and a rollback: no subscription row and no audit row.
- `FOR NO KEY UPDATE` conflicts with `record_event`'s `FOR SHARE`, held for the whole event, and with `mark_paid`'s
  `FOR NO KEY UPDATE`. So a payment either committed first and is seen, or waits for this commit; in the second
  case the Admin decision predates billing, and the existing policy applies when billing ends.
- Lock order is users → incarnation, and no billing path locks `users`.
- Non-PostgreSQL engines have no billing owner, because billing exists only on PostgreSQL.

**Tests:**
- Unit:
  - owned billing suppresses manual, legacy and an unended manual grant for `past_due` after grace,
    `past_due` without anchor, `paused`, `pending`, `unknown` and an unrecognised state;
  - ended billing and a lapsed prepaid row release the manual grant;
  - the Admin guard refuses for `unknown` too.
- PostgreSQL:
  - `test_a_live_billing_relationship_suppresses_an_existing_manual_grant`: active → past_due beyond grace gives
    Free and billing-owned; ended gives manual again.
  - `test_a_manual_write_after_billing_took_ownership_is_refused_inside_its_transaction`: step 3 of the race, with
    no row and no audit row.
  - `test_a_payment_in_flight_serializes_the_manual_write_and_leaves_no_latent_grant`: an uncommitted event holds
    the incarnation `FOR SHARE`. The Admin write blocks, then refuses after the commit. When billing later ends the
    account reads Free, not a stale Pro.
  - `test_a_manual_write_that_commits_first_is_not_blocked_by_a_later_payment`: the opposite order.

**Results (local, not CI):**
- Throwaway PostgreSQL 16: the targeted batch gives 700 passed, 0 skipped.
- `tests/test_effective_entitlement_postgres.py` run twice on the same database: 11 passed both times.
- Mutation checks:
  - Removing the P1-1 suppression fails 14 tests, including the PostgreSQL one.
  - Removing the P1-2 transactional re-check fails 2 tests: the two PostgreSQL race tests.
