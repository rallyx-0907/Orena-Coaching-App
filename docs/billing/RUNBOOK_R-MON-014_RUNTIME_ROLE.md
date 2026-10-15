# Runbook R-MON-014: a non-superuser runtime role for credits (DRAFT, not executed)

**Status: DRAFT.** Nothing in this runbook has been run on any shared environment. It is preparation for the
human's step 6: apply the migrations, change the runtime database role, check that `credit_runtime_privileges` is
ready, and only then consider `CREDITS_ENABLED`.

- Each step is an operator action on a runtime the human names.
- Take a backup first.
- Never run it on :8000, :8010 or :8021 without the human's explicit authorization for that runtime.

Why: today the runtime URL (`POSTGRES_RUNTIME_URL`) connects as the database's owner role. Credits refuse every
operation on such a connection (`credits_runtime_privileged`, PR-MON-4, D-MON-020). The ledger's write boundary
holds only for a non-superuser member of `orena_credit_runtime` that owns neither the credit tables nor their schema.

## 0. Preconditions (checked, not assumed)

- [ ] The human has authorized this runtime and this window.
- [ ] A fresh `pg_dump` of the runtime exists, and a restore check has passed (`scripts/runtime_backup.py` /
      `product_restore_rehearsal.ps1`).
- [ ] The migrations 0027 → 0031 → 0032 (→ 0033 after PR-MON-5) were promoted under their own gate and applied with
      the **owner/migration role**, which stays the migration executor.
  - Applying them as a superuser creates `orena_credit_owner` and `orena_credit_runtime`.
  - A non-superuser executor needs them provisioned first: both `NOLOGIN NOSUPERUSER NOBYPASSRLS`, and the executor
    a member of `orena_credit_owner` WITH SET (0032 refuses otherwise).
- [ ] The runtime does no DDL on PostgreSQL. The `CREATE TABLE IF NOT EXISTS` statements in
      `platform_repository.py`, `product/repository.py` and `auth_repository.py` target the SQLite archive only;
      re-verify this on the commit being deployed.

## 1. Create the runtime login role (an owner/superuser session)

```sql
CREATE ROLE orena_runtime LOGIN PASSWORD '<from the secret store, never typed into a doc or log>'
    NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE INHERIT;
GRANT orena_credit_runtime TO orena_runtime;          -- the credit boundary (0032)
GRANT CONNECT ON DATABASE <db> TO orena_runtime;
GRANT USAGE ON SCHEMA <schema> TO orena_runtime;
```

## 2. Grant the application's ordinary privileges (everything except the credit tables)

The application reads and writes its own tables. Grant DML on every table **except** `credit_accounts`,
`credit_ledger` and `credit_reversal_requests` (and, once 0034 is applied, `funding_admissions` and
`promotional_grants`), whose privileges come only through `orena_credit_runtime`:

```sql
-- generate the list from the catalog on the deployed schema; review it before running
SELECT format('GRANT SELECT, INSERT, UPDATE, DELETE ON %I.%I TO orena_runtime;', schemaname, tablename)
  FROM pg_tables
 WHERE schemaname = '<schema>'
   AND tablename NOT IN ('credit_accounts', 'credit_ledger', 'credit_reversal_requests', 'funding_admissions',
                         'promotional_grants', 'alembic_version');
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA <schema> TO orena_runtime;
```

Then **revoke** what the financial tables must never allow (the triggers refuse these too):

```sql
REVOKE DELETE, TRUNCATE ON billing_orders, billing_reconciliation_items,
       commerce_billing_event_receipts FROM orena_runtime;
```

- `TRUNCATE` is never granted on any table.
- `alembic_version` stays read-only for the runtime (`GRANT SELECT` only), because the startup schema check reads it.
- Before this step goes beyond DRAFT, review whether any other table needs a narrower grant (for example
  `account_incarnations`, `commerce_*`).

## 3. Verify before switching anything

Connect **as `orena_runtime`** and run the readiness checks (the admin route `GET /api/admin/billing/readiness`, or
directly):

- `credit_runtime_privileges` returns **no violations**.
  - None of the boundary-defeating privileges are held: `superuser`, `bypassrls`, `member_of_owner`,
    `owns_*`, `create_on_schema`, `update_credit_accounts_*`, `delete_*`, `truncate_*`.
  - None of the required ones are missing: `missing_runtime_membership`, `missing_*`.
- A read-only smoke test of the application as `orena_runtime` on a staging copy: sign-in, a plan read, a quota
  admission, the admin readiness report.

## 4. Switch the runtime connection

- Set `POSTGRES_RUNTIME_URL` to the `orena_runtime` login (the secret comes from the secret store and is never
  printed).
- Restart the application through the deployment's normal procedure. This is a human-operated step; agents never
  restart shared runtimes.
- Re-check readiness: `credit_runtime_privileges = ready`.
- **`CREDITS_ENABLED` stays off.** Turning it on is a separate human decision (step 6 of the order of work), after
  the packs (PR-MON-5, K1) exist.

## 5. Rollback

- Point `POSTGRES_RUNTIME_URL` back to the previous role and restart. Credits are refused again, which is the safe
  side.
- Nothing in this runbook changes data. Roles and grants can stay in place, or be revoked with
  `REVOKE … FROM orena_runtime; DROP ROLE orena_runtime;`.

## 6. Open items before this leaves DRAFT

- A rehearsal of steps 1-4 on a throwaway copy of the runtime, recording the exact grant list.
- A narrower grant review (§2).
- Where the password is stored and how it is rotated (the operator's secret store).
