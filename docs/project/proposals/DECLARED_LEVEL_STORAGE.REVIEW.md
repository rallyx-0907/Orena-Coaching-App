# Review: `DECLARED_LEVEL_STORAGE.md` (declared level per learning language)

- **Reviewer role:** Delegated Architecture Reviewer, independent of the implementer
  (`AGENTS.md` §1 "Architecture review authority"). I did not write the proposal.
- **Reviewed commit:** `ecec28ad5d688316c3b611438c34cd864070f89d` (`codex/work`). The proposal
  says it was verified at `748a22a`. The only code changes between the two are in
  `static/orena/screens/writing/*` and `scripts/test_orena_shell.mjs`, and none of the proposal's
  citations point there.
- **Reviewed file:** `docs/project/proposals/DECLARED_LEVEL_STORAGE.md` (untracked, 236 lines).
- **Scope:** the proposal document only. No code, migration or runtime exists yet. Nothing was run
  against a database. All evidence below comes from reading code at the reviewed commit. No tests
  were executed, so no PASS is claimed.
- **Policy:** `docs/project/REVIEW_POLICY.md` (verdicts, P0/P1/P2).

## Verdict: **REQUEST CHANGES**

There is no P0. Three P1s remain open, and all three are fixes to the proposal text and the test
plan. None of them changes the chosen design. The storage decision itself is sound: one additive
`declared_level VARCHAR(20) NOT NULL DEFAULT ''` column on the existing per-(account, language)
row, validated in the application against the language registry, with no DB enum or CHECK, served
through the existing `/api/learner-profile` PATCH. It follows
`ORENA_ACCOUNT_DATA_ARCHITECTURE.md` §1 ("Existing `UserLanguageProfile` … remain the starting
point") and §3 ("Reuse equivalent existing records"). Once the P1s are addressed, this proposal can
be approved without another design round.

## Factual claims checked

| Claim (proposal §) | Result | Evidence |
| --- | --- | --- |
| `declared_level` is `stored=False` with CEFR-only `allowed` values; PATCH is refused with `not_yet_stored` → 501 (§0) | Correct | `writing_coach/account_profile.py:94-96, 224-225`; `writing_coach/becoming_memory.py:139` |
| One row per (user, language), `UNIQUE(user_id, language_code)`, `ON DELETE CASCADE` (§0) | Correct | `writing_coach/persistence/models.py:45-62`; `migrations/versions/20260811_0001_postgres_foundation.py:37-50` |
| The PG repository reads and writes by `(stable_uuid(user_key), current language)` (§0) | Correct (lines are 935-967) | `specialized_repository.py:935-936, 949-967` |
| SQLite keeps a single `learner_profile` row in a DB file scoped per user and language (§0) | Correct | `specialized_repository.py:284-309, 401-425`; `auth_support.py:69-90` |
| PATCH merges named fields against `expected_version` = `updated_at`; PUT replaces the whole record for native (§0) | Correct | `becoming_memory.py:83-91, 142-198`; `app.py:2770-2787` |
| The registry has `en` A1..C2 and `zh` HSK1..HSK6 plus `HSK7-9`, with no `ja` (§0) | Correct | `languages/english/profile.py:12`; `languages/chinese/profile.py:12`; `core/language_registry.py:9-12` |
| Alembic head is `20260924_0016`, startup refuses a mismatch, migrations run only through the bootstrap command (§0, §3) | Correct | `20260924_0016_adaptive_reading.py:89-90`; `persistence/runtime.py:85-113`; `scripts/bootstrap_runtime_schema.py:103-184` |
| Onboarding sends only CEFR, swallows the 501 and offers HSK1-6; `entryRoute` ignores the level (§0) | Correct | `onboarding/model.js:150-199`; `onboarding/screen.js:384-406`; `shell/routes.js:76-87` |
| There is no runtime account-deletion path (§0, §6) | Correct | `persistence/incarnation_repository.py:7`; D-055 |
| A constant default makes the column add metadata-only (§3) | Correct for the runtime in use (PG 17) | `compose.yaml:115` (`postgres:17-alpine`) |
| Old UI reads `declared_level` behind CEFR regexes (§4) | Correct but incomplete | also `static/orena/ui/profile.js:90` (raw value), `writing_coach/persistence/admin_repository.py:318-321` (hard-coded `None`), and the Writing target in `static/orena/ui/expression.js:186-187` (P2-7) |
| Sandbox applies with `--upgrade --from 20260924_0016` (§3) | **Not true today** | The sandbox DB is at `20260923_0014` (`CURRENT_HANDOFF.md:104-108`). See P2-1 |

## Findings

### P1-1: What the stored value means is not reconciled with the architecture

**Evidence.**
- `ORENA_ACCOUNT_DATA_ARCHITECTURE.md:49-52` calls it the "declared **target** level … a goal".
- `account_profile.py:92-93` says "what the learner is **aiming at**".
- The Welcome step that will write the value asks for the learner's current self-assessed level:
  "Choose your level … Pick the one that sounds most like you" (`onboarding/copy.js:46`). The
  shell shows it as the level next to the language (`UI_BACKEND_GAPS.md:950`, SH-2).
- The Writing room uses it as the **target** level of the review (`static/orena/ui/expression.js:183-187`).
- Proposal §1 repeats "a goal … Unchanged" and does not notice the mismatch.

**Why it is P1.** This is the meaning of a durable learner-owned field for about 100k accounts.
Once rows hold "the level I think I am", nothing can later reinterpret them as "the level I aim
for". Leaving that choice to whichever consumer reads the field first is exactly the kind of
silent architecture decision `AGENTS.md` §7 reserves.

**Required change.**
- The proposal states the meaning explicitly. Recommended: "the learner's self-declared level for
  this learning language; a statement by the learner, never measured, inferred or projected".
  That is what D-098 point 8 and D-099 point 4 ("self-chosen level") describe.
- The human confirms the meaning at approval. The Decision Log entry that approves the proposal
  amends the "target level" wording in `ORENA_ACCOUNT_DATA_ARCHITECTURE.md` §1 and
  `account_profile.py`.
- The "never overwritten by a projection" rule stays.

### P1-2: The allowed set must come from the same language the row is scoped by, not from `active_profile()`

**Evidence.**
- The repository scopes the row by `current_language_code()` (`specialized_repository.py:935-936`).
  The middleware sets that to `enabled_language(session.language).code`, which can be any enabled
  registry code (`auth_support.py:409-411, 428, 455`).
- `active_profile()` and `active_levels()` only distinguish two cases: anything that is not `zh`
  resolves to **English** (`languages/runtime.py:23-36`).
- The GET payload also reports `"language": active_profile().code` (`becoming_memory.py:100`).

**Why it is P1.** Proposal §4 says "`registry.language(active).levels`", which is ambiguous. The
natural implementation, `active_levels()`, is already how Writing validates levels
(`app.py:908`). With that implementation, the day `ja` joins the registry a `ja` row would be
validated against CEFR and store `B1`. GET would also report `language: "en"` for a `ja` learner,
so the new entry rule would be judging the wrong language. The proposal's central claim, room for
`ja` with no schema change, holds for the schema but fails in this code path.

**Required change.**
- Specify the allowed set as `('',) + language_registry.language(current_language_code()).levels`.
  This is the same key the repository writes under.
- Fail closed when that lookup returns nothing or an empty `levels`: only `''` is accepted, and a
  code is refused with `invalid_value`. Never fall back to English.
- Apply the same resolution to session overrides in `effective_settings`, and to read-back, where
  a stored code outside the current list reads as `''` with `source: default`.
- Test it with a stub third registry entry (a monkeypatched `_REGISTRY` with its own `levels`). The
  test proves a CEFR code is refused for it and its own code is accepted.
- The GET `language` field is a pre-existing bug. Fixing it to report the scope code is
  recommended, but it may stay out of scope if recorded as a gap.

### P1-3: The test plan does not test the persistence guarantees the design relies on

**Evidence.**
- The proposal's key compatibility guarantee is that the native PUT and the PATCH of other fields
  leave `declared_level` untouched (§4). That is a property of each repository's
  `upsert_profile_record`:
  - SQLite writes an explicit column list with `ON CONFLICT DO UPDATE` (`specialized_repository.py:411-425`);
  - PostgreSQL assigns fields one by one (`:957-967`).
- The runtime test the proposal plans to extend uses `FakeProfileRepository`, whose upsert
  **replaces the whole record** (`tests/test_orena_account_profile_runtime.py:19-31`). A
  "PUT preserves the level" test against that fake would either fail or prove nothing about
  either real repository.
- "en and zh rows are independent" is likewise a property of the real scoping, not of the fake.
- The proposal does not mention that `scripts/test_orena_shell.mjs:75` currently asserts the
  opposite of the new entry rule.

**Required change.** Add to §8:
- **CI tests against the real `SQLiteSpecializedLearningRepository`**, run through the route or
  service:
  - PATCH level, then GET returns it with `source: saved`;
  - PUT (native payload) preserves it;
  - PATCH `goal` preserves it;
  - PATCH `''` clears it;
  - en and zh scopes stay independent;
  - an existing SQLite file without the column is upgraded by `initialize()` and reads `''`.
- **The fake's upsert gets merge semantics**, or a second fake models them.
- **A PostgreSQL rehearsal**, recorded before the `git mv` into `versions/`:
  - up/down/up of `0017` on a throwaway PG 17;
  - pre-existing rows read `''`;
  - the PG repository's PUT and PATCH preserve the level;
  - ORM matches the migrated schema (the `test_reading_evidence_schema_parity.py` pattern).
  - `ORENA_ACCOUNT_DATA_ARCHITECTURE.md` §6 step 3 requires this: "SQLite tests alone are
    insufficient".
- **`test_orena_shell.mjs:75` changes as a named contract change**, not a weakened assertion.
- **The whole suite runs green with the new head**, because head-sensitive tests exist
  (`tests/test_adaptive_reading_schema.py`, `tests/test_reading_canonical_cutover_scripts.py`).

### P2-1: The sandbox precondition is not stated

`CURRENT_HANDOFF.md:104-108` says the 8011 database is at `20260923_0014`, and `0016` is a gated,
non-additive revision (`bootstrap_runtime_schema.py:55-58, 155-162`). The proposal's apply command
(`--from 20260924_0016`) will refuse until 0015 and 0016 have been applied through their own
route. The refusal is safe.

**Required change.** State the precondition: the sandbox is verified at `20260924_0016`
(`scripts/start_orena_sandbox.ps1` reports it) before `0017` is moved into `versions/`, and a
`runtime_backup.py` backup is taken immediately before the upgrade.

### P2-2: Lock behaviour on a large table

Even a metadata-only `ADD COLUMN` takes a brief `ACCESS EXCLUSIVE` lock. If a long transaction is
open, the lock waits behind it, and every reader of `user_language_profiles` then queues behind
the lock. At about 100k users this is a real stall.

**Recommended.** Add `SET LOCAL lock_timeout = '5s'` in `upgrade()` and `downgrade()`, with the
operator retrying on timeout. This is not blocking for the sandbox but is required before any
production use. The `downgrade()` docstring must say it drops learner data and exists for
rehearsal only, as §3 already says.

### P2-3: Leave the legacy importer untouched

`importer.py:276-290` re-sets **every** field on an existing row. The proposal's "reads the column
if present, else `''`" would erase a stored PG level whenever an import re-runs from a SQLite
source that lacks the column. A frozen SQLite runtime never has that column.

**Required change.** Do not add `declared_level` to the importer's `values`. `server_default`
covers inserts, and updates leave the column alone.

### P2-4: Optimistic concurrency is not transactional (pre-existing, flag only)

`patch_learner_profile` reads the row in one session and upserts it in another
(`becoming_memory.py:146, 170`; `specialized_repository.py:949-967`). Two concurrent PATCHes with
the same `expected_version` therefore both succeed. On top of that:
- the version token has one-second resolution (`becoming_memory.py:152`);
- onboarding re-sends the same change automatically after a 409 (`onboarding/screen.js:303-319`),
  which is last-writer-wins by design.

The proposal is right that an integer version column is not authorized here (§9). A conditional
write (`UPDATE … WHERE updated_at = :expected`, 0 rows → 409) needs no schema change and may be
added. If it is not added, record the risk as the proposal does.

### P2-5: The native client's strict schema

`mobile/src/api/contracts/learning.ts:21-27` parses the profile with `.strict()`. GET already
carries keys outside that schema (`declared_level`, `settings`, `version`). This is pre-existing
and native is frozen.

**Required change.** The PUT response (`becoming_memory.py:191-198`) must **not** gain
`declared_level`. Assert this in the PUT test.

### P2-6: Status code for an invalid level

Keep **400 `invalid_value`**. Every other profile field uses it (`becoming_memory.py:139, 161-169`),
and FastAPI already uses 422 for body-shape errors, so a registry refusal answering 422 would be
indistinguishable from a malformed request.

### P2-7: Other consumers the proposal does not list

- `admin_repository.py:318-321` hard-codes `"level": None` with a comment that becomes false.
  Keep the value `None`, since surfacing learner data to admins needs an explicit use case
  (architecture §1), and correct the comment.
- `static/orena/ui/expression.js:186` accepts only CEFR, so a Chinese learner's stored HSK level
  never reaches the Writing review's target. That is an EN/ZH parity gap in a consumer, surfaced
  rather than caused by this change. Record it in `UI_BACKEND_GAPS.md` as a follow-up; it is not
  part of this slice.

### P2-8: "HSK 1-9" in D-099 against the registry's seven codes

The proposal is right to follow the registry. `HSK7-9` is one band in HSK 3.0, and codes
`HSK7`/`HSK8`/`HSK9` should not be added.

**Required change.** The human confirms at approval that the registry's list satisfies "HSK 1-9".
The onboarding cell for `HSK7-9` stays a design question, as §9 says.

### P2-9: The row is keyed by account, not incarnation (acknowledged)

Architecture §1 keys the learning profile by incarnation and language. The row is keyed by
`user_id`. Proposal §6 acknowledges this and D-055 covers it (no deletion or re-registration path
until the owner-table workflow exists). No change is needed.

**Required change.** The approval entry notes that `user_language_profiles`, now holding a
learner-stated datum, is part of the owner-table deletion enumeration that D-055 precondition (b)
requires.

## Specific questions from the brief

- **Storage location and per-language semantics:** correct. It uses the existing
  (account, language) row and adds no parallel owner (architecture §3).
- **Migration safety:**
  - additive, with a constant default and a linear chain `0016 → 0017`;
  - lands first in `migrations/proposed/`;
  - no startup Alembic (D-002; `runtime.py:90-113` only verifies);
  - not added to `GATED_REVISIONS`, which is correct for an additive change;
  - the downgrade is for rehearsal only;
  - locking: P2-2; precondition: P2-1.
- **API compatibility:**
  - old UI: CEFR regexes, no change needed;
  - new UI: onboarding plus `entryRoute`;
  - native: PUT leaves the column untouched and its response is unchanged (P2-5; tests in P1-3);
  - optimistic concurrency: unchanged and pre-existing (P2-4).
- **Registry validation and future `ja`:** the schema is ready. The code path must follow P1-2.
- **Deletion and export:** the cascade already covers the column. The architecture defines no
  export contract. `runtime_backup.py:96-110` compares row counts and is unaffected.
- **§7 holds:** the column itself is authorized by D-099 point 4 through exactly this process. The
  proposal adds no sync cursor, receipt, incarnation key or integer version (§9). The only point
  where it silently decides reserved architecture wording is the meaning of the value (P1-1).
- **"Existing accounts see Welcome once":** the consequence is correctly identified. It is the
  literal result of the human's rule in D-098 point 9 and D-099 point 4.
- **SQLite parity (§2):** confirmed as test parity, not deepening SQLite as a runtime. It uses the
  existing guarded `ALTER TABLE` pattern (`specialized_repository.py:296-309`) so CI exercises the
  route. The conditions are no sync to or from SQLite and no importer change (P2-3).
- **Length CHECK:** none. `String(20)` already bounds the value, and values belong to the registry.
- **Rollback:** sound. Before writes, revert the code and keep the column. After writes, keep the
  column and revert the UI rule or ship a forward fix. Never downgrade and never return to SQLite
  authority (architecture §6).

## Recommendations on the proposal's open questions (§9)

| Question | Recommendation |
| --- | --- |
| Existing accounts (§5) | **(A)**, unless the pinned design draws an entry at the Level step, in which case (B) is acceptable. Reject **(C)**: a backfill would store an inferred value in a stated field. When the level save fails, Welcome appears again on the next visit. That is correct, and the flow must never claim the save happened. Add it to the `entryRoute` truth table. |
| 400 vs 422 | **400 `invalid_value`** (P2-6). |
| Integer version column | **No, not in this revision.** It belongs to the canonical account architecture (AGENTS §7). An optional conditional write is described in P2-4. |
| `support_language` stored per row; `interface_language` storage | Out of scope. Keep them held as §9 says. |
| Deletion or re-registration runtime | Out of scope (D-055). |
| `ja` level list, `HSK7-9` cell | `ja` gets its list when it joins the registry, with no schema change (conditional on P1-2). `HSK7-9` is a design question. The human confirms the band reading (P2-8). |
| Length CHECK (§2) | Not added. |
| SQLite column (§2) | Confirmed as test parity. |

## To reach APPROVE

1. P1-1: state the value's meaning and have the human confirm it in the approving decision.
2. P1-2: specify the allowed set as the registry entry for `current_language_code()`, fail closed,
   and add the stub-language test.
3. P1-3: add the repository-level SQLite tests, the fake with merge semantics, the PostgreSQL
   rehearsal record, and the named `test_orena_shell.mjs:75` contract change to §8.

The P2s should be folded in while editing, but they do not block. Human approval remains required
after this review (D-099 point 4). This review is not product approval and not authorization to
apply the migration.

## Re-check of revision 2

- **Reviewer:** the same Delegated Architecture Reviewer, independent of the implementer.
- **Reviewed HEAD:** `6c0db16194684045337592543e840447209f1539` (`codex/work`).
- **File:** `docs/project/proposals/DECLARED_LEVEL_STORAGE.md`, revision 2 (271 lines).
- **Scope:**
  - whether each P1 and P2 above is resolved in the text;
  - spot-checks against the code for the claims that changed.
  - This is not a second design review. Nothing was run, and no test PASS is claimed.
- **Code changes since the first review** (`ecec28a..6c0db16`): only Writing evaluation, its tests
  and `CURRENT_HANDOFF.md`. None of the paths the proposal cites for profiles, registry,
  migrations or onboarding changed. The handoff's sandbox lines moved to `CURRENT_HANDOFF.md:101-104`;
  the content is the same (still `20260923_0014`).

### Per finding

| Finding | Status | Evidence |
| --- | --- | --- |
| P1-1 meaning | **RESOLVED** (text); human confirmation still required at approval | §1 L54-63 states "self-declared current level … never measured, inferred or projected". §5.1 L162-163 makes it a human decision. The approval entry amends `ORENA_ACCOUNT_DATA_ARCHITECTURE.md:49-52` and `account_profile.py:92-93`. The "no projection writes it" rule is kept. |
| P1-2 allowed set | **RESOLVED** | §4 L111-121 says `('',) + language_registry.language(current_language_code()).levels`. It fails closed, with no `active_profile()`/`active_levels()` and no English fallback, and applies to PATCH, overrides and read-back. Checked against code: `language_registry.language()` casefolds and returns `None` for an unknown code (`core/language_registry.py:19-20`). The scope code is always an enabled registry code (`auth_support.py:409-411`). The repository keys by the same `current_language_code()` (`specialized_repository.py:935-936`). GET `language` → `current_language_code()` (L126-129) is identical for en/zh today and fixes the non-en/zh case. The native `z.enum(['en','zh'])` (`mobile/src/api/contracts/learning.ts:25`) is unaffected while only en/zh exist. The stub third-language test and the empty-`levels` test are at §8 L198-199. |
| P1-3 test plan | **RESOLVED** | §8 L201-208 adds tests against the real `SQLiteSpecializedLearningRepository`: PATCH/GET, PUT preserves the level and its response has no field, PATCH `goal` preserves it, `''` clears it, en/zh stay independent, 409/400, and `initialize()` upgrades an old file. L210-212: the fake gets merge semantics. L214-217: `test_orena_shell.mjs:75` becomes a named contract change, plus a truth table that includes a failed save. L219-226: a recorded throwaway-PG 17 up/down/up, including concurrent PATCHes and ORM/migration parity, before the `git mv`. L228-229: the whole suite runs at the new head. |
| P2-1 sandbox precondition | RESOLVED | §0 L44-45; §3 L103-107 (reach 0016 first, verify, back up, then `--from 20260924_0016`). |
| P2-2 lock | RESOLVED, with one new detail (N2) | §3 L96-101: `SET LOCAL lock_timeout = '5s'` in upgrade and downgrade, and the downgrade docstring says it drops learner data. `migrations/env.py:36-55` runs migrations inside `context.begin_transaction()`, so `SET LOCAL` takes effect on PostgreSQL. |
| P2-3 importer | RESOLVED | §2 L87-89. `importer.py:276-290` re-sets only the keys in `values`, so leaving `declared_level` out preserves it. |
| P2-4 concurrency | RESOLVED for update, with one new detail (N1) | §4 L138-142: `UPDATE … WHERE updated_at = :expected`, 0 rows → 409, no schema change. The remaining same-second race and onboarding's single retry are recorded (L233-235). |
| P2-5 native strict schema | RESOLVED | §4 L144-147. The PUT response stays as it is (`becoming_memory.py:191-198`), asserted in §8 L203. |
| P2-6 status | RESOLVED | §4 L132-134: 400 `invalid_value`. |
| P2-7 other consumers | RESOLVED | §4 L153-158: the admin comment is corrected with the value kept `None`, and the `expression.js` HSK gap goes to `UI_BACKEND_GAPS.md`. |
| P2-8 HSK 1-9 | RESOLVED (human confirms) | §5.3 L170-172. |
| P2-9 account-keyed row | RESOLVED | §6 L176-179. |

### New issues introduced by revision 2 (all P2, non-blocking)

- **N1 (P2): the conditional write needs an interface and a creation path.**
  - **Interface.** `SpecializedLearningRepository.upsert_profile_record(values)`
    (`specialized_repository.py:195`) has no way to carry the expected version, and PUT must stay
    unconditional. The implementation should add an explicit parameter (for example
    `expected_updated_at: str | None`, where `None` means unconditional for PUT) rather than a
    magic key inside `values`.
  - **Creation race on PostgreSQL.** The insert path's "existing unique key" guard
    (§4 L141) raises `IntegrityError` on PostgreSQL (`:961-964`, `s.get` then `s.add`). That error
    must map to 409 `version_conflict`, not a 500.
  - **Creation race on SQLite.** The insert is `INSERT … ON CONFLICT(id) DO UPDATE`
    (`:415-421`), which would silently overwrite a concurrently created row instead of relying on
    the unique key. Creation should use a plain insert, or `DO NOTHING` with a rowcount check.
  - **Tests.** The SQLite and PG tests in §8 should include "create-while-created → 409".
- **N2 (P2): guard the lock setting on PostgreSQL.** Put `SET LOCAL lock_timeout` behind
  `if op.get_bind().dialect.name == "postgresql"`, as earlier migrations already do
  (`20260911_0006_commerce_subscription_inbox.py:242`, `20260924_0015_reading_content_engine.py:493`).
  That way offline or non-PG runs of the chain do not emit or fail on PG-only SQL. Because
  `env.py` runs the chain in one transaction, the setting then also applies to anything after it
  in that run. That is harmless while 0017 is the last revision, and worth a one-line comment in
  the migration.
- **N3 (P2, cosmetic):** the legend says "verified at `871e2b9`", and the table row for P2-3 cites
  `importer.py:286-290` where the loop is 276-290. Neither affects correctness.

### Verdict: **APPROVE**

Every P1 and P2 from the first review is resolved in the text and consistent with the code at
`6c0db16`. The three new items are P2 and can be carried into implementation. Per `REVIEW_POLICY.md`,
with no unresolved P0 or P1 the verdict is APPROVE. This approves the **architecture proposal
only**. It is not product approval and not authorization to apply the migration:
- P1-1's meaning, the §5 existing-accounts option and the P2-8 HSK reading still need the human's
  confirmation (D-099 point 4);
- the migration stays in `migrations/proposed/` until the recorded PostgreSQL rehearsal (§8) and
  human authorization.
