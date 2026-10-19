# Architecture review: PR #309, consent evidence and voice consent (migration 20261019_0036, proposed)

- Reviewer: Delegated Architecture Reviewer (Claude Opus 5.5, independent subagent)
- Reviewed commit: 90ddd7671e7e0d2149d1d5b802ee02d97b79ff67 (`origin/claude/consent-evidence`)
- Date: 2026-10-19
- Scope: `migrations/proposed/20261019_0036_consent_evidence.py`, `writing_coach/persistence/consent_store.py`,
  `writing_coach/consent.py`, `account_settings.py`, `speech_api.py`, `auth_support.py`, `auth_repository.py`,
  `deletion_enumeration.py`, D-233, tests. Read from the PR diff and `git show`; nothing was run (no Docker, no
  Postgres). Learner UI was read for copy and pattern reuse only, not measured in a browser; that is the design reviewer's job.
- Not an approval of promotion or application to any runtime (human gates).

## Verdict: CHANGES REQUESTED

No P0. The schema change itself is sound. The four P1s below are about evidence integrity and promotion
preconditions, not about the DDL.

## 1. Migration safety

- Five `ADD COLUMN`s on `users`. Four are nullable with no default. One is `boolean NOT NULL DEFAULT false`, a constant
  default. On PostgreSQL 11+ that is metadata-only (no table rewrite); the repo runs `postgres:17-alpine`
  (`compose.yaml:169`). Fine.
- Locking: each `ADD COLUMN` takes ACCESS EXCLUSIVE, and the locks are held until the single transactional DDL commits.
  Each statement is metadata-only, so the hold is short. `SET LOCAL lock_timeout = '5s'` bounds the wait. The pattern
  matches 0017 and 0018. If the timeout fires, the transaction rolls back whole (transactional DDL), so there is no
  partial state, and the presence check requires all five anyway.
- Downgrade drops the five columns in reverse order. Correct, and honestly documented as destructive. Not idempotent
  (no IF EXISTS), which matches repo convention.
- Naming matches 0018.
- Unconfirmed: whether any schema-drift or ORM-vs-migration test flags columns that exist in the DB but not in the ORM.
  Check in the rehearsal.
- Chain: Billing's proposed 0034 and this 0036 both parent on 0035. Alembic uses `down_revision`, not filename numbers.
  Promoting both unmodified makes two heads, and `scripts/bootstrap_runtime_schema.py --upgrade --from/--to` assumes a
  linear chain.
  Promotion order: one at a time, whichever is approved first. The second must edit `down_revision` (and its docstring)
  to the new head, then redo its own up/down/up rehearsal on the updated chain. Never merge heads. Record the
  re-parenting in D-233 or Billing's decision.

## 2. Absence guard

- Logic is correct. "Present" is cached for the process lifetime. "Absent" is re-probed at most every 30 s. A probe
  error counts as absent. A runtime migrated while running starts recording within 30 s.
- Thread safety: `_Presence` is unlocked. The races are benign: the probe is idempotent and monotonic
  (False to True only), and the worst case is a duplicate probe.
- Cached "present" after a downgrade on a live runtime: reads and writes raise, are caught, and answer "no record".
  Acceptable, because downgrade is documented as rehearsal-only. However, the consent warning with traceback is logged on
  every request until restart (log noise).
- Performance: the probe is at most one information_schema query per 30 s per process when absent. When present, `get`
  is a unique-index lookup on `users.user_key`, one extra query per bootstrap and per speech call. Fine.
- All reads and writes go through the store. I found no unguarded query touching the columns.
- Schema detail: the probe uses `current_schema()`. If the app's search_path differs from the migrating role's, the
  probe could answer wrongly. Rehearse with the real DSN.

## 3. Data semantics

- Accept-Language first tag as the consent language is weak evidence. `consent_language` is documented as "the
  interface language the learner saw it in", which is not true for sign-up consent. See P2-3.
- `unstamped`: see P1-1.
- Reset on deletion: see P2-1 (not wired, and a retention question for counsel).

## 4. Privacy and security

- Endpoints take the user from the session (`_user_key()`); the body carries only `language` and `granted`. No spoofing
  of another user.
- The 403 gate in `speech_api.py` (transcribe and assess) is applied before any provider work, inside the same handler,
  so no code path skips it once the columns exist.
- Not confirmed: whether the global same-origin/CSRF guard covers the two new POSTs. I did not verify, and no per-route
  rate limit was added. Both should be confirmed (cheap writes, but each hits the DB).
- No `/api/agent/*` files are touched. `consent.py` explicitly leaves the Intelligence voice routes to that lane.
- Side effect to confirm: `voice_consent` defaults to false for every existing user. On application, all existing
  learners get 403 `voice_consent_required` on transcribe and assess until they opt in. This is by design, but the
  client's 403 handling (mic sheet) and release communication must be verified (P1-4).

## 5. Tests

- `tests/test_consent_evidence.py` covers the SQLite backend and the logic.
- `tests/test_consent_evidence_postgres.py` is skipped unless `ORENA_TEST_POSTGRES_URL` is set. CI does not provide one,
  so the only PostgreSQL proof of up/down/up is not part of the gate.

## 6. Learner UI

- Copy exists for EN/VI/ZH (`screens/consent/copy.js`) and the PR reuses sheet patterns (`screens/mic/sheet.js`,
  settings). Design fidelity is out of scope here.
- The sentence in the Privacy Policy saying no separate consent step exists: I could not locate it by search in
  `docs/legal/public/*` or `DRAFT_*.md`, and I cannot confirm where it lives. Per the coordinator's note it is now
  inconsistent and must change before or with promotion (P1-3). The only related line I found is in
  `docs/project/UI_BACKEND_GAPS.md:6404`, which this PR updates.

## Findings

### P1

1. **`unstamped` consent version in production** (`writing_coach/consent.py:current_legal_version`, `.env.example:113`).
   An unset or malformed `LEGAL_EFFECTIVE_DATE` silently records `unstamped`, which is useless as evidence and cannot be
   corrected later. Fix: under `APP_ENV=production`, refuse to start (or at minimum fail the readiness check and log an
   error) when the date is unset or malformed. Add a deploy checklist item that the same date is passed to
   `build_public_pages.mjs`.
2. **Sign-up consent is recorded without proof the clickwrap was shown** (`auth_support.py` callback,
   `record_sign_up_consent`). Any first OAuth callback for a new account is recorded as accepted: direct visits to the
   login URL, the native redirect path, or any non-web client never saw the Account step. Fix: record only when the login
   start carried a flag set by the Account step's button (session value set at `/auth/google/login?...`), otherwise leave
   the account unrecorded so the one-time sheet asks.
3. **Privacy Policy and Terms text must be updated and the date re-stamped before or with promotion.** The statement that
   there is no separate consent step is now false, and voice consent is a new permission. Update the public legal JSON
   (EN/VI/ZH) and bump `LEGAL_EFFECTIVE_DATE`. D-233 says a changed date does not re-ask, so decide whether existing
   accounts being asked once is enough.
4. **Rehearsal evidence required before promotion.** Run up/down/up on a throwaway copy of the populated PostgreSQL
   (PG 17), with the real role and search_path. Record: row count unchanged, ADD COLUMN timing, `lock_timeout`
   behaviour, `ORENA_TEST_POSTGRES_URL` test passing, no ORM drift test failure. Also verify the 403
   `voice_consent_required` path in the mic sheet for existing learners, and plan the release note, since every existing
   account is gated until opt-in.

### P2

1. Deletion reset is declared but not wired: `reset_consent` has no caller outside tests, and
   `deletion_enumeration.CONSENT_COLUMNS_TO_RESET` is used only by a test. The migration docstring cites the wrong
   constant (`USER_COLUMNS_TO_RESET`, line 14). Fix the docstring, and add the call to the deletion-workflow task when
   that runtime is built. Also ask counsel whether consent evidence must be retained after deletion; resetting erases
   the proof.
2. The voice gate fails open on any read error (`consent_state` answers `available: False`, the request passes). For a
   privacy gate, when the columns are known present and the read raised, prefer fail-closed (503/403).
3. `consent_language` for sign-up consent is the browser Accept-Language, not the language the learner saw. Document that,
   or rename the semantics ("language hint").
4. Unrelated churn in `auth_repository.py` (`timezone.utc` to `UTC`). Revert or note it.
5. Confirm same-origin/CSRF coverage and add a rate limit for the two new POSTs.
6. Log a single warning for the failed probe rather than a traceback every 30 s.

## Outcome

CHANGES REQUESTED. After the P1s are addressed (code for 1 and 2, text for 3, rehearsal evidence for 4) a re-review of
the delta can APPROVE for promotion. Promotion and application remain human gates. This record is not product approval.

## Outcome (re-review)

- Reviewer: Delegated Architecture Reviewer (Claude Opus 5.5, independent subagent)
- Reviewed commit: 486905ea34614a93fbc5b795da5233d8286771b4 (delta from 90ddd767 read for the consent files; CI green per coordinator, not independently verified)
- Verdict: APPROVE for promotion, subject to the human gates (promotion and application are not authorised by this record).

Verified in the delta: P1-1 `core/deployment.py` refuses production start without a YYYY-MM-DD `LEGAL_EFFECTIVE_DATE`. P1-2 sign-up consent is recorded only when the session carries `account_step=1` and not on a native start; other logins get the one-time sheet. P2 fail-closed: `ConsentUnreadable` becomes 503 `consent_unavailable`. P2 docstring constant fixed. P1-3 (EN/VI legal templates changed) and P1-4 (release note, D-233) were reported by the coordinator; I did not review those texts.
P1-4 rehearsal: `REHEARSAL_0036_2026-10-19.md` shows up/down/up on a populated PG17.10 copy (3.7/2.5/3.6 s, row counts unchanged, columns and defaults correct, Postgres test passed).

Residual conditions (not blocking):
1. The legal text is EN+VI only; ZH was not in the changed templates. Confirm whether a ZH public page exists and needs the same sentence before promotion.
2. Rehearsal source DB was PG16 and was not run under concurrent load; the lock risk is low (metadata-only) but apply in a quiet window after `scripts/runtime_backup.py`.
3. Chain: re-parent whichever of Billing 0034 / this 0036 is promoted second, and re-rehearse.
4. Deletion reset stays unwired until the deletion runtime exists; the D-233 note and the counsel question must be tracked.
