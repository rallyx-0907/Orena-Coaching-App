# Runbook: apply the Billing migrations 0027 → 0033 to a PostgreSQL runtime (operator task)

Status: **authoritative on `main` when PR #212 is merged**. Not executed on any runtime.

`main` now carries the Billing chain `20261005_0027 → 20261014_0031 → 20261014_0032 → 20261015_0033`. A runtime that
restarts on the new `main` before its database has these revisions runs code that reads columns and tables it does not
have. So the migration comes **before** the restart, for every PostgreSQL runtime.

## Who and when

- An **operator task**, never an autonomous feature-agent task.
- **One runtime at a time**, each under its own explicit human authorization (which runtime, which window).
- No agent applies these revisions to `:8000`, `:8010`, `:8021` or any other runtime on its own initiative.

## Per runtime

1. **Backup, verified.** A fresh `pg_dump` of the runtime (`scripts/runtime_backup.py` / `product_backup.ps1` /
   `staging_backup.ps1`), and a restore check that passed (`product_restore_rehearsal.ps1`). No backup, no migration.
2. **Roles.** Applied as a superuser, 0032 creates `orena_credit_owner` and `orena_credit_runtime`. A non-superuser
   executor needs both provisioned first (`NOLOGIN NOSUPERUSER NOBYPASSRLS`) and must be a member of
   `orena_credit_owner WITH SET`; 0032 refuses otherwise and changes nothing.
3. **Apply** with the owner/migration role: `alembic upgrade 20261015_0033` (it passes 0027, 0031, 0032, 0033 in order).
   Never automatic at startup.
4. **Verify the head** is exactly `20261015_0033` (`alembic current`; one row in `alembic_version`).
5. **Smoke checks** (read-only), all must pass:
   - the tables exist: `billing_orders` (with `product_kind`, `credit_pack_id`, `credit_units`),
     `billing_reconciliation_items`, `credit_accounts`, `credit_ledger`, `credit_reversal_requests`;
   - `credit_apply_entry()` is owned by `orena_credit_owner` and is `SECURITY DEFINER`;
   - every existing order reads `product_kind = 'plan'`; the D-MON-014 guard and prepaid replay still answer;
   - `GET /api/admin/billing/readiness` answers as it did before the migration (with credits off it says nothing about
     credits);
   - optional: `PostgresCreditRepository(engine).runtime_privilege_violations()` under the runtime's own connection
     lists violations until R-MON-014 is done - expected, and the reason credits stay off.
6. **Only then restart** that runtime on the new `main`, and repeat the readiness check after the restart.

If any step fails: stop, do not restart on the new `main`, keep the old process running; restore from the step-1
backup only if the database is left inconsistent (the migrations are transactional, so a failed upgrade normally rolls
back).

## After the migration

- `CREDITS_ENABLED` stays **OFF**.
- No production credit packs (`BILLING_CREDIT_PACKS_FILE` unset, K1).
- R-MON-014 (`RUNBOOK_R-MON-014_RUNTIME_ROLE.md`) is **not** run unless separately authorized.
- A migrated database is not permission to sell or consume credits.
