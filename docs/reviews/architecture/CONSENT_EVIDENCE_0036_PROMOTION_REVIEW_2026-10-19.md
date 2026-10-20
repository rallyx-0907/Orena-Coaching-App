# Architecture review: PR #402, promotion of migration 20261019_0036 (consent evidence)

- Reviewer: Delegated Architecture Reviewer (Claude Opus 5.5, independent subagent)
- Reviewed commit: 55b8326b9d18bc56b85d371a1c448d552a171448 (PR #402)
- Date: 2026-10-19
- Scope: the move of `migrations/proposed/20261019_0036_consent_evidence.py` into `migrations/versions/` (parent
  `20261018_0035`, new single head), D-233 / README / `RELEASE_8000_READINESS.md` s14 wording, the updated tests,
  `REHEARSAL_0036_2026-10-19.md`, `account_deletion.py` and `consent_store.py` as they stand at that commit. Read from the
  PR diff and `git show`; nothing was run. The schema review of the content is
  `CONSENT_EVIDENCE_0036_REVIEW_2026-10-19.md` (PR #309, APPROVE for promotion).
- Not an approval to apply the migration to any runtime (human gate).

## Verdict: APPROVE WITH CONDITIONS

No P0, no P1. Conditions are about deploy order and documentation.

## Findings

- Additive only: five `ADD COLUMN` on `users`; four nullable with no default, one `boolean NOT NULL DEFAULT false`
  (constant default, metadata-only on PG 11+, no rewrite). `SET LOCAL lock_timeout = '5s'`, one transaction, so a timeout
  rolls back whole. At ~100k users the lock is brief, but `users` is hot (every request reads it): apply in a quiet window
  after a backup. The rehearsal (PG17.10, 7 users) proves correctness, not lock behaviour under load.
- Downgrade drops all five columns (destroys consent evidence). Documented in the docstring as rehearsal only; a runtime
  with records is restored from backup. Acceptable.
- Privacy: stores version, time, language and a voice boolean/time only. No IP, no user agent. Minimal.
- Account deletion: the P2 raised in #309 is closed. `account_deletion._reset_user` merges `CONSENT_COLUMNS_TO_RESET`
  and filters on columns present, so it is safe on a 0035 database. Counsel's question (retain consent proof after
  deletion?) stays open and tracked in D-233.
- Chain: single head `20261019_0036`; the tests assert one head and parentage. Billing's proposed 0034 must re-parent
  on 0036 and re-rehearse; README and D-233 say so.
- Postgres test now drives Alembic itself (down to 0035, then up) and leaves the DB at head. Not in CI (needs
  `ORENA_TEST_POSTGRES_URL`), as before.
- The absence guard remains meaningful after promotion: it no longer protects a code-before-schema deploy (startup refuses
  actual != head), but it still keeps the code dormant, instead of erroring, on databases lacking the columns (restored
  backups, SQLite tests) and deletion filters by column presence. The docstring says this. Keep it.

## Operational consequence

`runtime_schema` refuses to start when actual != head. After merge, an image built from `main` cannot start on :8000
(0035) or :8021 until 0036 is applied there. The PR documents this (README, s14, migration docstring). Merging is source
control only; nothing deploys on merge, and running containers are unaffected until rebuilt.

## Conditions

1. No image from `main` may be built or started on :8021 or :8000 before the owner authorises the migration for that
   runtime; :8021 needs its own authorisation, then :8000. Order: backup (`scripts/runtime_backup.py`), `bootstrap_runtime_schema.py --upgrade`, then start the image.
2. Apply in a quiet window and watch for the 5 s lock timeout; a retry is safe.
3. Any other lane merging a migration after this one parents on 0036 (Billing 0034 first).
4. On application, every existing account has `voice_consent = false` and gets 403 until it opts in; ship the release note.

## P2 (non-blocking)

- The Postgres proof is manual; consider a CI job with a throwaway PG.
- Rehearsal source was PG16 with 7 users; no concurrent-load test.

This record is not product approval and does not authorise applying the migration.
