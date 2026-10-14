# PR-MON-4 Architecture Review (design)

The reviewer's verdicts are recorded verbatim, as the human relayed them on 2026-10-14. The design is
`docs/billing/PR-MON-4_DESIGN.md`. The human's product decisions C1-C7 are D-MON-019; they were frozen on
`43a3dedf` and are not part of the review.

---

# Review of design revision 2 (`e5ccc1149dbb2984ed3a31d3f7876d34fdb69380`)

## VERDICT

**REQUEST CHANGES**

C1–C7 are accepted as frozen. Do NOT reopen the human product decisions.

There are three architecture blockers to fix in the design before implementation.

### P1-1 — 0032 has a real dependency on 0031

The design currently says 0032 has no FK to 0027/0031 and could be re-parented onto the current head under H1 if promoted independently.

That is not true at the schema level.

0032 extends the `billing_reconciliation_items` schema created by 0031, including its kind CHECK and the new credit reconciliation kinds.

Therefore:

- `0032` MUST come after `0031`.
- 0032 must not be promoted before 0031.
- H1 must not re-parent 0032 around or ahead of 0031.
- It is fine that there is no FK to 0027/0031, but document the schema dependency explicitly.
- If another migration enters the real chain between promotion steps, preserve 0031 → 0032 ordering while applying the normal promotion/re-parent procedure.

Update §1 and §15.5 accordingly.

### P1-2 — Do not use `pg_trigger_depth() > 1` as the sole snapshot write boundary

`pg_trigger_depth()` describes trigger nesting. It is not an authorization boundary.

For a financial snapshot, protect `credit_accounts.posted`, `reserved`, `entry_count` and `last_entry_id` using database privileges.

Required design:

- runtime/application role cannot directly UPDATE the protected snapshot fields;
- the controlled ledger-application trigger/function is the permitted write path;
- prefer a `SECURITY DEFINER` function owned by a non-runtime role with a fixed safe `search_path`;
- keep the guard trigger / trigger-depth check only as defense-in-depth if useful;
- tests must prove a direct UPDATE from the normal runtime role is refused.

Do not weaken append-only ledger semantics.

### P1-3 — Complete reversal cap and idempotency semantics

Current formula:

`amount = min(requested, available)`

is incomplete when the same top-up has already been partially reversed.

Define:

`remaining_reversible = original_topup.amount - SUM(previous reversal.amount)`

`applied = min(requested, available, remaining_reversible)`

`shortfall = requested - applied`

The same transaction must:
- write the applied reversal when `applied > 0`;
- write/update the durable shortfall outcome when `shortfall > 0`;
- never touch reserved credit;
- never exceed the original top-up;
- never produce a negative balance.

#### Zero-available reversal

When `applied = 0`, no fake zero-value ledger entry is required, but the request still needs a durable idempotency receipt.

The `credit_reversal_shortfall` record may serve this role if designed explicitly.

It must have a stable dedupe/idempotency identity derived from the money-side event/request and preserve enough request digest data so that:

- exact replay returns the original zero/partial outcome;
- same key with changed request content is a conflict;
- a later retry after the account obtains new credit MUST NOT re-evaluate the request and suddenly reverse newly available credit.

#### Request digest

Define `request_digest` over request intent, not derived result.

For reversal it must include at least:
- kind;
- account;
- original top-up reference;
- `requested`;
- money-side source/event identity;
- other semantic request inputs.

Do not use the derived `applied amount` as the primary idempotency input.

Review the digest definitions for reserve/adjustment as well so all semantically relevant caller inputs are either included or explicitly declared non-semantic.

Add tests for:

1. top-up 100, previous reversal 80, available >= 30, new requested 30 → reversal 20 + shortfall 10;
2. reversal with available 0 → no ledger reversal + durable shortfall;
3. retry case 2 after later top-up/available balance appears → exact duplicate, no new reversal;
4. same reversal idempotency key with changed requested amount → conflict;
5. concurrent reversals cannot exceed remaining reversible amount.

## §15 answers

1. Snapshot trigger guard: **change required** as P1-2.
2. Derived reserve state from closing entries: **APPROVED**. No extra holds table required.
3. Late settle refused and recorded as `credit_late_settle`: **APPROVED**.
4. Extend the PR-MON-3 CHECK in 0032 instead of editing 0031: **APPROVED**.
5. Parent 0032 on 0031: **APPROVED AND REQUIRED** because 0032 depends on 0031's reconciliation schema.

## Non-blocking

The following are accepted:
- C1–C7 as currently frozen;
- `reserve_expire` naming;
- close-once reservation state model;
- account-level mutation serialization;
- no provider call inside a financial transaction;
- append-only ledger;
- drift detection as incident rather than manual snapshot repair;
- no purchased-credit expiry in v1;
- 30-minute reservation TTL.

Do not create migration `20261014_0032_credit_ledger.py` yet.

Update only the design/decision/status documents and return the new design commit for focused re-review.

Required next verdict remains:

`APPROVE FOR IMPLEMENTATION`

Response: design revision 3, `2b6da4a7`, and D-MON-020.

---

# Review of design revision 3 (`2b6da4a7b7f2278880b3b7af330fa80bfeea4637`)

## VERDICT

`REQUEST CHANGES`

The three blockers from the review of `e5ccc114` are substantially resolved. C1-C7 remain frozen and MUST NOT be reopened.

Do one narrow design revision only. No implementation and no migration 0032 yet.

### P1-4 — Remove or explicitly resolve the reversal-request circular FK

Current design has both:

`credit_reversal_requests.reversal_entry_id -> credit_ledger.id`

and:

`credit_ledger.reversal_request_id -> credit_reversal_requests.id`

while `credit_reversal_requests` is immutable.

The documented transaction inserts the request first and then the reversal ledger entry. For `applied > 0`, that cannot satisfy an immediate FK plus the CHECK requiring `reversal_entry_id IS NOT NULL`.

Preferred fix:

- remove `reversal_entry_id` from `credit_reversal_requests`;
- keep `credit_ledger.reversal_request_id`;
- require `reversal_request_id` exactly for `kind = 'reversal'`;
- add a UNIQUE/partial UNIQUE constraint so one request can have at most one reversal ledger entry;
- derive the reverse link by querying the ledger by `reversal_request_id`.

This keeps the request immutable and removes unnecessary circular dependency.

If the circular FK is intentionally retained instead, the design must explicitly define deferred constraints and the insert order. Do not leave this to implementation guesswork.

### P1-5 — A money-side reversal event must be globally unique

The reversal key is derived from:

`<source_type>:<source_ref>`

That represents one refund/chargeback event.

The current per-account uniqueness is insufficient because the same external money event could otherwise be attached to two credit accounts.

Require a global uniqueness constraint:

`UNIQUE(source_type, source_ref)`

on `credit_reversal_requests`.

Behavior:

- same event + same request intent → return original receipt;
- same event + different account/top-up/requested amount → conflict;
- one external refund/chargeback event can never reverse credit twice.

Keep the per-account idempotency key if useful, but global money-event uniqueness is the financial backstop.

### P1-6 — Define the reconciliation schema added by 0032

0031's `billing_reconciliation_items` table does not currently contain the credit-specific references described in revision 3.

0032 must explicitly define the columns it adds for the new credit reconciliation kinds.

At minimum, specify the structured references required for:

- credit account / incarnation;
- top-up entry;
- reversal request;
- reversal ledger entry when present;
- requested;
- applied;
- shortfall;
- any reserve/ledger reference needed by `credit_late_settle`;
- expected/actual balance data required by `credit_balance_drift`, if stored structurally.

Use nullable columns because the table serves multiple reconciliation kinds, but add per-kind CHECKs where useful.

0032 must also update/replace the 0031 reconciliation guard so these newly added factual credit fields cannot be silently rewritten after creation.

Do not claim that 0032 only extends the kind CHECK if it also extends the reconciliation table schema.

### P1-2 hardening clarification

Keep the current database-role design, with two clarifications:

1. The schema used in the `SECURITY DEFINER` function's `search_path` must not be writable by the runtime or other untrusted roles. Explicitly revoke/deny CREATE there or use another trusted schema. Keep `pg_temp` last.

2. If 0032 itself creates `orena_credit_owner` and `orena_credit_runtime`, document that the migration executor must be a superuser or have `CREATEROLE`. A database owner without CREATEROLE is not sufficient. Alternatively provision the roles out-of-band and make the migration assert they exist.

Expand `credit_runtime_privileges` so it checks all privileges whose accidental grant would defeat the financial boundary, especially UPDATE/DELETE/TRUNCATE on ledger/request tables and DELETE/TRUNCATE on credit accounts.

### Baseline refresh

Before creating migration 0032, sync/rebase onto the latest `main` and re-run the migration-topology check.

Do not change the frozen order:

`0027 -> 0031 -> 0032`

## Everything else remains accepted

Do not redesign:
- C1-C7;
- reserve hard cap;
- 30-minute reserve TTL;
- no purchased-credit expiry;
- partial reversal semantics;
- no re-evaluation of reversal receipts;
- reserve close-once model;
- late-settle absorption;
- snapshot + append-only ledger architecture.

Return only the focused documentation diff.

The next review should be limited to P1-4, P1-5 and P1-6 plus the two privilege clarifications above.

Response: design revision 4, `48e1bf2e`, and D-MON-021.

---

# Focused re-review of design revision 4 (`48e1bf2e6f7bcac964bf7b60942ea684203842cd`)

## VERDICT

**APPROVE FOR IMPLEMENTATION**

The design contract for PR-MON-4 is now frozen.

### Review closure

- P1-1: CLOSED — 0032 has a required schema dependency on 0031.
- P1-2: CLOSED — financial snapshot write boundary is enforced by database privileges and a controlled SECURITY DEFINER path.
- P1-3: CLOSED — reversal uses `min(requested, available, remaining_reversible)` and durable no-re-evaluation receipts.
- P1-4: CLOSED — circular reversal FK removed; request → ledger relation is one-way with at most one reversal entry per request.
- P1-5: CLOSED — money-side reversal events are globally unique by `(source_type, source_ref)`.
- P1-6: CLOSED — 0032 explicitly defines the credit reconciliation schema, per-kind checks and replacement immutable-fact guard.
- Privilege hardening: ACCEPTED.
- C1–C7 remain frozen and must not be reopened.

## Authorized next step

Proceed with implementation, but in this exact order:

1. Rebase/sync the Billing lane onto the latest `main`.
2. Re-run the migration-topology check.
3. Preserve the required Billing ordering:

`0027 → 0031 → 0032`

4. Only then create:

`migrations/proposed/20261014_0032_credit_ledger.py`

5. Implement PR-MON-4 according to the approved design.
6. Run the planned throwaway PostgreSQL migration, privilege, concurrency, idempotency, reconciliation and mutation tests.
7. Keep 0032 in `migrations/proposed/`.
8. Do NOT promote or apply 0032 to any shared/runtime environment without the separate human migration authorization.

## Runtime deployment gate

Credits must remain disabled until the runtime database connection:

- is not superuser;
- has no BYPASSRLS;
- is not the credit-table/schema owner;
- is not a member of `orena_credit_owner`;
- uses the approved `orena_credit_runtime` privilege boundary;
- passes `credit_runtime_privileges`.

The currently privileged runtime DB role must therefore be replaced/configured before credits are enabled.

## Minor non-blocking documentation cleanup

The design header still says:

`State: DESIGN revision 3`

Update it to revision 4 / implementation-approved when updating status. This does not block implementation.

**PR-MON-4 design is approved for implementation.**

---

## Baseline refresh before 0032 (implementer, 2026-10-14)

- The lane was rebased onto `main` `ceaaa9e2` (PR #181).
- `migrations/` is unchanged since `1a9e010d`.
- The applied chain is `… 0023 → 0025 → 0029 → 0030 → 0026`, with the single head `20261005_0026`. No revision
  names 0026 as its parent.
- Proposals: `0024 → 0023`, `0027 → 0026`, `0028 → 0027`, `0031 → 0027`.
- 0032 is created on `20261014_0031`, so the order 0027 → 0031 → 0032 is kept.

---

# Implementation review (`2f52279be4ebc69a415e18c887b63bcbc8aecb86`, code `dc193265db007549a2cad488f6db8bc4f1c2d0e5`)

Recorded verbatim from the reviewer's verdict (relayed by the human, 2026-10-14).

## VERDICT

**REQUEST CHANGES**

The core ledger implementation is accepted in direction. Do not reopen C1-C7 or redesign the ledger.

Fix only the following three P1 implementation blockers before re-review.

### P1-1 — Make the database-role provisioning path valid and fail closed

The migration currently accepts `superuser OR CREATEROLE`, but later transfers ownership of the credit tables and functions to `orena_credit_owner`.

A non-superuser CREATEROLE executor is not automatically guaranteed to be able to `SET ROLE orena_credit_owner`, so CREATEROLE alone is not a sufficient precondition for the ownership transfer.

Also, when `orena_credit_owner` / `orena_credit_runtime` already exist, the migration currently checks only that their names exist.

Required:

- Validate existing roles before any credit DDL.
- `orena_credit_owner` must at minimum be:
  - NOLOGIN;
  - NOSUPERUSER;
  - NOBYPASSRLS.
- Validate the runtime group role is also suitable for use as a NOLOGIN privilege role.
- Validate that the migration path can actually transfer ownership to `orena_credit_owner`.
- Do not claim CREATEROLE-only support unless the migration explicitly arranges the required SET-role capability and schema privilege safely.
- Simpler acceptable solution: self-create roles only when the migration executor is superuser. Otherwise require correctly provisioned roles and fail before DDL if the ownership prerequisites are not met.
- Ensure the empty-schema downgrade also works under every migration-executor mode that upgrade officially supports.

Add PostgreSQL tests for the supported non-superuser/provisioned path, not only a mocked `_roles()` precondition.

### P1-2 — Readiness must require membership in `orena_credit_runtime`

`credit_runtime_privileges` currently checks dangerous privileges that must be absent, but it does not verify the positive deployment requirement:

`current_user must be a member of orena_credit_runtime`

Add a fail-closed violation such as:

`missing_runtime_membership`

when:

`pg_has_role(current_user, 'orena_credit_runtime', 'MEMBER') = false`

Prefer also checking the minimum effective privileges required by the credit repository so `ready=true` means the runtime can actually perform a credit transaction.

Add a test using a non-superuser login with no dangerous privileges but without `orena_credit_runtime` membership:

- status must be `ready=false`;
- credit operation must be refused before repository mutation;
- after the correct membership/grants are present, readiness becomes true.

### P1-3 — The trigger backstop must serialize against account deletion

The repository uses the approved lock order:

`account_incarnations FOR SHARE`
→ `credit_accounts FOR UPDATE`

But `credit_apply_entry()` currently locks the credit account first and reads incarnation status without a row lock.

That leaves a direct-ledger-insert race where the trigger can read `active`, a concurrent deletion can commit, and the new topup/reserve/settle can still commit afterward.

The database backstop must follow the same deletion serialization contract as the repository.

Required:

- acquire the incarnation protection before the credit-account mutation lock;
- preserve one global lock order;
- then check `status = active`;
- only then apply a new `topup`, `reserve`, or `settle`.

If the SECURITY DEFINER owner needs a minimal extra privilege on `account_incarnations` to take the row lock, grant only what is required and include it in the privilege design/tests.

Add a PostgreSQL concurrency test:

1. deletion transaction changes/locks the incarnation but does not commit yet;
2. a runtime direct `INSERT credit_ledger` attempts a topup/reserve;
3. it must wait behind the incarnation lock;
4. after deletion commits, the insert must fail;
5. final ledger/snapshot contain no new charge.

## Reviewer answers to the three implementation questions

1. BEFORE INSERT trigger assigning `seq = entry_count + 1`: **APPROVED**.
2. Ordinary application privileges on `account_incarnations` staying outside 0032: **APPROVED**, subject to P1-1/P1-2 above.
3. Drift blocking `release` and `reserve_expire`: **KEEP IT BLOCKED**. A drift means the snapshot is not trusted; no snapshot mutation should continue until the incident is resolved.

## Accepted implementation differences

Accepted without further design changes:

- application-clock reserve expiry computed in the reserve transaction;
- zero-usage settle refused in favor of release;
- no coded dedicated-schema fallback, provided the supported schema path fails closed;
- database recomputation of reversal `applied`;
- PR-MON-3 generic reconciliation listing not selecting 0032-only columns;
- current credit reconciliation dedupe keys;
- admin adjustment may create an empty credit account first;
- `CREDITS_ENABLED` remains off by default.

## Non-blocking follow-up

Record a P2 for a deleted account whose `credit_balance_on_deletion` item was already resolved and later receives new positive credit through an allowed refund/adjustment. The current one-item-per-account lookup does not reopen/create a new liability item.

Do not expand scope beyond this in the repair.

After these fixes:
- rerun the targeted PostgreSQL credit tests;
- rerun the mutation suite;
- return the new HEAD for focused re-review.

Do not promote/apply 0027, 0031 or 0032.
Do not enable credits.
Do not open/merge the PR until this implementation review is approved.

## Fix response (implementer, 2026-10-14)

The code fix is in `b4cc46ff`. C1-C7 are unchanged and the ledger is not redesigned. Nothing is promoted or
applied, and credits stay off.

- **P1-1. Roles: fail closed, two supported modes**, all checked by `_prerequisites()` before any credit DDL.
  - **Superuser executor:** it creates the roles when they are absent (`CREATE ROLE … NOLOGIN NOSUPERUSER
    NOBYPASSRLS …`).
  - **Non-superuser executor:** the roles must be provisioned out of band, and the executor must pass
    `pg_has_role(current_user, 'orena_credit_owner', 'SET')`. `orena_credit_owner` must hold CREATE on the schema,
    which 0032 grants only when the executor owns the schema, and otherwise fails. CREATEROLE alone is not
    supported, and the error says so.
  - **Existing roles are validated:** both must be NOLOGIN, NOSUPERUSER and NOBYPASSRLS, and
    `orena_credit_runtime` must not be a member of `orena_credit_owner`.
  - **Downgrade:** it works in both modes. A non-superuser's downgrade leaves the provisioned roles in place.
  - **PostgreSQL tests:**
    - `test_p1_1_a_non_superuser_executor_with_provisioned_roles_runs_0032_and_its_downgrade`: the whole chain runs
      as a non-superuser schema owner. The upgrade is refused before any DDL until the executor is a member WITH SET;
      after that the credit tables are owned by `orena_credit_owner`, and down and up both work.
    - `test_p1_1_an_existing_role_that_is_not_safe_is_refused_before_any_ddl`: refused for LOGIN, for BYPASSRLS, and
      for a runtime group that is a member of the owner.
- **P1-2. Readiness requires the runtime membership and the effective privileges.**
  `runtime_privilege_violations()` now also reports these when they are missing:
  - `missing_runtime_membership`;
  - SELECT on `credit_accounts`, INSERT on its `incarnation_id`, and UPDATE on its `updated_at` (the row lock);
  - SELECT and INSERT on `credit_ledger` and `credit_reversal_requests`;
  - SELECT, INSERT and UPDATE on `billing_reconciliation_items`;
  - SELECT on `account_incarnations`, plus UPDATE on some column of it (its `FOR SHARE` lock).

  `ready = true` therefore means the role is both safe and able. Test:
  `test_p1_2_a_harmless_role_without_runtime_membership_is_not_ready_until_it_is_a_member`. Without the membership
  the role is not ready, has no dangerous privilege, and a top-up is refused with no ledger row written. After the
  GRANT, a fresh check reports ready and the top-up applies.
- **P1-3. One lock order, in the trigger too.**
  - `credit_apply_entry()` reads the account's (immutable) incarnation id, takes
    `account_incarnations … FOR SHARE`, then `credit_accounts … FOR UPDATE`, and only then checks `status = active`
    for `topup`, `reserve` and `settle`.
  - `credit_check_reversal_request()` takes the same two locks in the same order.
  - The owner role is granted `SELECT, UPDATE (created_at)` on `account_incarnations`. A row lock needs UPDATE on at
    least one column, and no owner function updates an incarnation.
  - Test: `test_p1_3_a_direct_insert_waits_for_a_deletion_and_then_fails[topup|reserve]`. A deletion holds the
    incarnation uncommitted. The runtime's direct ledger insert waits behind it, and fails after the commit. The
    ledger, the snapshot and the drift are unchanged.
- **Reviewer answer 3** is kept: drift blocks `release` and `reserve_expire` too.
- **Non-blocking P2** is recorded as R-MON-015.


---

# Focused implementation re-review — verdict

Recorded verbatim from the reviewer's verdict (relayed by the human, 2026-10-14), in summary of its decisive lines:

Focused implementation re-review completed for: `HEAD 53eb5cba4cc210a0921416a40c0c9f472501ea28`
Fix commits: `b4cc46ffd4b66514f9546396fafb132f1ab3969b`, `90bb3b1cfd8b7a1fc9fa22b47861df93af17ba7e`

## VERDICT

**APPROVE**

The three P1 blockers from the implementation review are closed.

- P1-1 — CLOSED: the database-role provisioning and ownership path now fails closed (superuser-only self-creation; provisioned roles and SET on `orena_credit_owner` for a non-superuser executor; existing roles validated before credit DDL; unsafe LOGIN / SUPERUSER / BYPASSRLS refused; `orena_credit_runtime` may not inherit the owner role; the non-superuser upgrade/downgrade path exercised by a real database test).
- P1-2 — CLOSED: `credit_runtime_privileges` checks both privileges that must NOT exist and privileges/membership that MUST exist; `ready=true` means sufficiently restricted and sufficiently privileged.
- P1-3 — CLOSED: the trigger follows the repository lock order (`account_incarnations FOR SHARE` → `credit_accounts FOR UPDATE`); the topup/reserve race regressions prove the insert waits, is rejected after the deletion commits, and leaves no ledger row or balance change; the cleanup closes its transaction in `finally`.

Evidence accepted: targeted SQLite `636 passed, 1 skipped`; throwaway PostgreSQL batch `533 passed, 1 inherited #160 failure`; focused credit suite `39 passed`; mutation suite `29/29 caught`. Issue #160 remains inherited test infrastructure and is not a PR-MON-4 blocker.

Residual risks / gates: `R-MON-014` remains a mandatory deployment gate — do not enable credits until the runtime database connection is a non-superuser runtime login using the approved `orena_credit_runtime` boundary. `R-MON-015` is accepted as P2 follow-up and does not block this PR.

Authorized next step: rebase onto latest `main`; re-run migration topology verification; open the PR; run required CI; if rebase/CI fixes materially change the ledger, migration, privilege boundary, locking, idempotency or reconciliation semantics, return for focused re-review; otherwise merge after CI/repository gates pass. The migration sequence remains `0027 → 0031 → 0032`; all three remain proposed.

This approval does **not** authorize: promotion/application of 0027, 0031 or 0032; enabling `CREDITS_ENABLED`; bypassing the runtime-role deployment gate.

**PR-MON-4 implementation is APPROVED for PR/CI.**
