# PR-MON-4 Prepaid Credit Ledger — implementation review request

This change is payment code with a financial schema, so `AGENTS.md` §1 requires an independent architecture review;
the implementer may not approve it. The design is `docs/billing/PR-MON-4_DESIGN.md` revision 4, APPROVED FOR
IMPLEMENTATION on `48e1bf2e`. The review trail is in
`docs/reviews/architecture/PR_MON_4_CREDIT_LEDGER_REVIEW_2026-10-14.md`; record this verdict in the same file. The
human product decisions C1-C7 are D-MON-019.

| | |
| --- | --- |
| Branch | `feature/monetization-billing-v1` |
| Base | `main` `ceaaa9e2`. The topology was re-checked before 0032 and is unchanged: head `20261005_0026`. |
| Schema | New **proposed** `migrations/proposed/20261014_0032_credit_ledger.py`, on `20261014_0031`. The order 0027 → 0031 → 0032 is kept. Nothing is promoted or applied. |
| Runtime effect today | None. Credits exist only where billing does and `CREDITS_ENABLED` is on. Even then every operation is refused while `credit_runtime_privileges` fails, and it fails for today's runtime role. |

## What was built

1. **0032** (design §2, §2.1, §9):
   - `credit_accounts`, with the CHECK `0 <= reserved <= posted`.
   - `credit_ledger`, with eight kinds and an effect CHECK per kind:
     - `expires_at` only on `reserve` (C6);
     - `reversal_request_id` exactly on `reversal`;
     - a source only on `topup`;
     - a reference exactly on the offset kinds.
   - `credit_reversal_requests`, with the global UNIQUE (`source_type`, `source_ref`) and `applied + shortfall = requested`.
   - Unique indexes:
     - one top-up per money source;
     - one close per hold;
     - at most one reversal entry per request;
     - (account, kind, key);
     - (account, seq).
   - `credit_apply_entry()`, a `SECURITY DEFINER` trigger owned by `orena_credit_owner`, with
     `search_path = <schema>, pg_catalog, pg_temp`. It is the only snapshot writer. It:
     - locks the account;
     - refuses `topup`, `reserve` and `settle` on a deleted account;
     - validates that each offset names the right kind in the same account;
     - enforces the exact hold release, the settle cap (C3), the refund cap and the reversal cap;
     - checks that a reversal entry applies exactly its request;
     - assigns `seq` and applies both deltas.
   - `credit_check_reversal_request()`, also `SECURITY DEFINER`, requires
     `applied = min(requested, available, remaining_reversible)` under the account lock.
   - Append-only and no-truncate triggers. A guard on `credit_accounts` refuses `DELETE`, an owner change, and any
     snapshot change unless `current_user = orena_credit_owner`.
   - The two roles are created when absent. If the executor is neither a superuser nor `CREATEROLE`, the migration
     fails clearly before any DDL.
   - Privileges:
     - `REVOKE CREATE ON SCHEMA` from `PUBLIC` and from the runtime role;
     - the credit tables and functions are owned by `orena_credit_owner`;
     - `EXECUTE` is revoked from `PUBLIC`;
     - the runtime group gets only the grants in design §2.1, plus `SELECT, INSERT, UPDATE` on
       `billing_reconciliation_items`.
   - `billing_reconciliation_items` gains 16 `credit_*` columns, 7 credit CHECKs, the extended class lists and the
     `balance_consistent` outcome. The replaced guard function freezes the credit facts and makes
     `credit_balance_drift` reopenable.
   - `downgrade()` refuses while any credit row or credit item exists. Otherwise it restores 0031's guard and CHECKs
     exactly (tested by comparing `prosrc` and `pg_get_constraintdef`).
2. **`persistence/credit_repository.py`**:
   - Each operation is one transaction in the §4.1 lock order: the incarnation `FOR SHARE`, then the account
     `FOR UPDATE`.
   - It looks up idempotency with the §6 intent digests, refuses an account under drift review, decides, and inserts.
   - A database refusal becomes `conflict`, with nothing written.
   - Operations: `topup`, `reserve`, `settle`, `release`, `expire_reserve`, `refund`, `adjust` and `reverse` (with
     the receipt, the optional entry and the shortfall item in one transaction).
   - Reads for the reconciler.
   - `runtime_privilege_violations()`, which checks every privilege the review listed.
3. **`billing/credits.py`** (`CreditService`): gated by `credit_runtime_privileges` (cached 60 s; a check that cannot
   run counts as unsafe). Its reconciler step closes holds past `expires_at`, and every hold of a deleted account,
   with `reserve_expire`. It also records `credit_balance_on_deletion` (C1) and detects drift, opening the critical
   item and auto-resolving it once the balances agree.
4. **The reconciler** (PR-MON-3) runs the credit step under its session lock when credits are configured.
5. **Admin API**:
   - `GET /api/admin/billing/credits/{incarnation}` returns the status, the balance and a ledger page.
   - `POST …/adjustments` takes `delta ≠ 0`, `operation_id` and `reason`, with the administrator as actor (C4).
6. **Wiring** in `app.py`: `_credits` is created only when billing exists and `CREDITS_ENABLED` is on.

## Where the implementation goes beyond the approved text (please confirm)

1. The snapshot is applied in a **BEFORE INSERT** trigger that also **assigns `seq`** (`entry_count + 1` under the
   account lock). The design said an AFTER INSERT trigger that checks `seq`. Both keep the snapshot and the row in one
   statement; assigning `seq` in the trigger removes a race window.
2. `expires_at` is computed in the reserve's own transaction from the application clock at the start of that
   transaction, not from the database's `now()`.
3. A `settle` with `actual = 0` is refused (`invalid`, release instead), because `amount > 0` holds for every entry.
4. The dedicated-schema fallback (`orena_credit`) is documented, not coded. 0032 uses the migration's schema, revokes
   `CREATE` there, and readiness verifies that the runtime has none.
5. The runtime still needs the application's ordinary privileges on `account_incarnations` (the `FOR SHARE` lock
   needs `UPDATE` on some column), and those are outside 0032. The owner role is granted `SELECT` on
   `account_incarnations` so the trigger can refuse a new charge on a deleted account (an extra backstop).
6. The request trigger recomputes `min(requested, available, remaining_reversible)`, a database backstop for
   `applied`.
7. The PR-MON-3 admin reconciliation listing does not show the `credit_*` columns. Selecting them would break a
   deployment that has 0031 but not 0032. Credit items are visible through their kind and the credit route.
8. Dedupe keys:
   - `credit_late_settle` uses `<reserve id>:<operation id>`;
   - `credit_balance_drift` uses the account id and reopens on recurrence;
   - `credit_balance_on_deletion` uses the account id;
   - `credit_reversal_shortfall` uses the request id.
9. The adjustment route creates the empty account when it is absent (`ensure_account`), then adjusts.
10. `CREDITS_ENABLED` is a new switch, off by default.

## Questions for the reviewer

1. Is (1) acceptable as the implementation of I2/I11?
2. Is (5) the right split? 0032 grants only credit-table and reconciliation privileges; the application's other
   grants belong to the runtime-role separation the operator configures.
3. Should drift (`account_under_review`) also block `release`/`reserve_expire`? Today it blocks every credit
   operation of that account, including the reconciler's expiry.

## Mutation results (local execution, throwaway PostgreSQL 16, on `dc193265`)

Each guard was removed in a throwaway copy, and `tests/test_credit_ledger.py` plus `tests/test_credit_ledger_postgres.py` (34 tests, none skipped) were run. **25/25 caught**, each by a test of the guard it broke.

| Guard removed | Where | Failing tests | Guard's own test |
| --- | --- | --- | --- |
| the account CHECK `0 <= reserved <= posted` | 0032 | 1 | `test_the_balance_check_refuses_an_overdraw_the_repository_did_not_stop` |
| the trigger applies both deltas | 0032 | 18 | `test_the_runtime_role_cannot_write_a_balance_or_rewrite_history`, `test_reserve_settle_release_and_the_hard_cap` (+16) |
| no runtime `UPDATE` of a snapshot column | 0032 | 24 | `test_0032_goes_down_only_while_empty_and_restores_0031_exactly`, `test_the_runtime_role_cannot_write_a_balance_or_rewrite_history` (+22) |
| ledger rows are never deleted | 0032 | 1 | `test_the_guard_trigger_refuses_even_a_superuser_and_the_check_names_each_privilege` |
| a credit account is never deleted | 0032 | 1 | `test_an_empty_credit_account_is_still_never_deleted` |
| one close per hold | 0032 | 1 | `test_a_hold_closes_once_and_offsets_name_their_own_kind_even_inserted_directly` |
| a refund names a settle | 0032 | 1 | `test_a_hold_closes_once_and_offsets_name_their_own_kind_even_inserted_directly` |
| refunds never exceed their charge | 0032 | 1 | `test_a_hold_closes_once_and_offsets_name_their_own_kind_even_inserted_directly` |
| a settle charges at most its hold (C3) | 0032 | 1 | `test_the_database_refuses_a_settle_beyond_its_hold_and_an_expiry_on_purchased_credit` |
| `applied = min(requested, available, remaining)` in the database | 0032 | 1 | `test_p1_4_a_reversal_entry_applies_exactly_its_own_request` |
| the repository's available check | repository | 2 | `test_reserve_settle_release_and_the_hard_cap`, `test_concurrent_reserves_never_overdraw` |
| the same key with another intent is a conflict | repository | 2 | `test_reserve_settle_release_and_the_hard_cap`, `test_an_adjustment_is_an_audited_delta_never_below_zero` |
| one top-up per money source | 0032 | 1 | `test_one_money_event_credits_once_even_inserted_directly` |
| no new charge on a deleted account (repository) | repository | 1 | `test_a_deleted_account_keeps_its_credit_as_a_liability_and_takes_no_new_charge` |
| the reconciler closes expired holds | service | 2 | `test_a_late_settle_after_expiry_is_never_charged_and_is_recorded`, `test_a_deleted_account_keeps_its_credit_as_a_liability_and_takes_no_new_charge` |
| no downgrade over financial rows | 0032 | 1 | `test_0032_goes_down_only_while_empty_and_restores_0031_exactly` |
| the definer function's fixed `search_path` | 0032 | 1 | `test_the_snapshot_function_is_security_definer_with_a_fixed_search_path` |
| `remaining_reversible` in the reversal | repository | 2 | `test_case_1_a_partly_reversed_topup_reverses_only_what_remains`, `test_case_5_concurrent_reversals_never_exceed_the_topup` |
| a reversal replay returns the stored receipt | repository | 1 | `test_case_2_and_3_a_reversal_with_nothing_available_is_final` |
| `credit_runtime_privileges` sees owner membership | repository | 1 | `test_the_guard_trigger_refuses_even_a_superuser_and_the_check_names_each_privilege` |
| one reversal per money event, globally (P1-5) | 0032 | 1 | `test_case_4_and_p1_5_one_money_event_reverses_once_in_one_account` |
| at most one reversal entry per request (P1-4) | 0032 | 1 | `test_p1_4_a_reversal_entry_applies_exactly_its_own_request` |
| credit facts frozen by the replaced guard (P1-6) | 0032 | 2 | `test_0032_goes_down_only_while_empty_and_restores_0031_exactly`, `test_credit_items_need_their_references_and_their_facts_never_change` |
| the shortfall item's per-kind CHECK (P1-6) | 0032 | 1 | `test_credit_items_need_their_references_and_their_facts_never_change` |
| no new charge on a deleted account (trigger) | 0032 | 1 | `test_a_deleted_account_keeps_its_credit_as_a_liability_and_takes_no_new_charge` |

## Evidence

See `BILLING_STATUS.md` ("Test status") and the mutation table below:
- `tests/test_credit_ledger.py` (no database);
- `tests/test_credit_ledger_postgres.py`: 26 tests on a throwaway PostgreSQL 16, run as a non-superuser member of
  `orena_credit_runtime`;
- `tests/test_admin_authorization_matrix.py` (two routes classified).
