# Proposal: store the learner's declared level per learning language

Status: **PROPOSED, revision 2** (2026-09-29), answering the independent review
`DECLARED_LEVEL_STORAGE.REVIEW.md` (REQUEST CHANGES). Document only: no code,
schema or migration is changed by this file. Process (AGENTS.md §7, D-054
workflow, D-099 point 4): proposal → independent architecture review → human
approval → code + migration + tests → the human applies the migration to the
sandbox (8011). Production (8000) and preview (8010) are never touched.

Origin: human decision "H2" (D-099 point 4; D-098 point 9). The new UI's entry
rule opens `#/welcome` when the profile has no learning language **or** no
declared level for that language, and Today otherwise (`UI_BACKEND_GAPS.md`
"Entry routing and the declared level", option (a); gap SH-2).

Legend: **[V]** verified in code at `871e2b9` (unchanged from `748a22a` for every
cited path except `scripts/test_orena_shell.mjs`, re-checked); **[I]** inferred.

## 0. What exists today

- `declared_level` is a language-scoped `Setting`, `allowed=('', 'A1'..'C2')`,
  `stored=False` (`writing_coach/account_profile.py:92-96`). PATCH refuses it with
  `not_yet_stored` → 501 (`:224-225`; `becoming_memory.py:139`). Every learner reads `''`. [V]
- The profile is **already one row per (user, learning language)**:
  `user_language_profiles`, `UNIQUE(user_id, language_code)`, `user_id → users.id
  ON DELETE CASCADE` (`persistence/models.py:45-62`; `migrations/versions/20260811_0001_postgres_foundation.py:37-50`).
  The PostgreSQL repository keys it by `(stable_uuid(user_key), current_language_code())`
  (`specialized_repository.py:935-936, 949-967`). [V]
- SQLite test backend: one `learner_profile` row (`id=1`) in a database file scoped
  per user + language (`specialized_repository.py:284-309, 401-425`; `app.py:398`;
  `auth_support.py:85-90`). [V]
- Routes `GET/PUT/PATCH /api/learner-profile` (`app.py:2770-2787`). PATCH merges named
  fields and compares `expected_version` with the row's `updated_at` (`becoming_memory.py:83-91, 142-180`).
  PUT is the frozen native client's whole-record replace (`:182-198`). [V]
- Scope language vs `active_profile()`: the middleware sets the scope to any enabled
  registry code (`auth_support.py:409-411`), but `active_profile()`/`active_levels()`
  resolve everything that is not `zh` to **English** (`languages/runtime.py:23-36`).
  GET reports `"language": active_profile().code` (`becoming_memory.py:100`). [V]
- Level lists live in the language registry: `en` `A1..C2` (`languages/english/profile.py:12`);
  `zh` `HSK1..HSK6, HSK7-9`, seven codes (`languages/chinese/profile.py:12`). They are served by
  `GET /api/platform/languages` (`core/platform_api.py:23-33`). No `ja` entry
  (`core/language_registry.py:9-12`). [V]
- Alembic head `20260924_0016` (`20260924_0016_adaptive_reading.py:89-90`). Startup
  verifies and refuses a mismatch. Only `scripts/bootstrap_runtime_schema.py` applies
  migrations (D-002; `migrations/proposed/README.md`). The **sandbox database is at
  `20260923_0014`**; 0015/0016 are authorized but not applied (`CURRENT_HANDOFF.md:104-108`). [V]
- Onboarding sends CEFR only and swallows the 501 (`onboarding/model.js:188-199`, `screen.js:384-406`).
  It retries a 409 once with the same change (`screen.js:303-319`). The grid offers HSK1-6 (`model.js:150-170`).
  `entryRoute` ignores the level (`shell/routes.js:77-87`); `scripts/test_orena_shell.mjs:75`
  asserts that. [V]
- No runtime account-deletion path exists (D-055; `incarnation_repository.py:7`). [V]

## 1. Meaning and shape

**Meaning (P1-1; the human confirms at approval).** `declared_level` is *the learner's
self-declared current level for this learning language: a statement by the learner,
never measured, inferred or projected*. This matches what Welcome asks ("Choose your
level … Pick the one that sounds most like you", `onboarding/copy.js:46`), the level shown
next to the language (SH-2), and D-098/D-099's "self-chosen level". It contradicts the
"declared **target** level … a goal" wording in `ORENA_ACCOUNT_DATA_ARCHITECTURE.md:49-52` and
`account_profile.py:92-93`. The Decision Log entry that approves this proposal amends both
to the meaning above. The rule stays: no projection ever writes it. Consumers that treat it
as a target (the Writing review, `static/orena/ui/expression.js:183-187`) read it as a
starting level; that is a consumer's choice and needs no change.

**Shape: one new column on the existing per-language row.**
- Architecture §1: "Existing `UserLanguageProfile` … remain the starting point". §3: "Reuse
  equivalent existing records". The row is already the (account, language) unit, so a column
  is per-language by construction. A new table would be a second owner of one profile. [V/I]
- Value: a level code from the registry list of the row's language, or `''` meaning "not
  declared". Validation lives in the application against the registry, with no DB enum or
  CHECK, so a future `ja` needs **no schema change** (the code path is in §4).

## 2. Storage

PostgreSQL (authoritative): `user_language_profiles.declared_level VARCHAR(20) NOT NULL
DEFAULT ''` (server default). ORM: `mapped_column(String(20), default="", server_default="",
nullable=False)`.
- `String(20)` bounds the value (longest code today: `HSK7-9`). No length CHECK, no index:
  reads use the existing unique `(user_id, language_code)`.
- The server default lets code that predates the column insert validly (rollback, importer).

SQLite (CI/test backend only; the reviewer confirmed this is test parity, not deepening SQLite
as a runtime): `SQLiteSpecializedLearningRepository.initialize()` adds `declared_level TEXT NOT
NULL DEFAULT ''` with the existing guarded `ALTER TABLE` pattern (`specialized_repository.py:296-309`).
There is no sync to or from SQLite.

**Importer untouched (P2-3).** `persistence/importer.py:276-290` re-sets every field in its `values`
on an existing row. `declared_level` is **not** added there: inserts get the server default and
updates leave the column alone, so re-running an import never erases a stored PG level. [V]

## 3. Migration

- `20260929_0017_declared_level.py`: `revision = "20260929_0017"`, `down_revision = "20260924_0016"`.
  It is written first in `migrations/proposed/` (not a head, so it triggers no startup refusal) and is
  `git mv`'d into `versions/` only after review, a recorded PostgreSQL rehearsal (§8) and human authorization.
- `upgrade()`: `SET LOCAL lock_timeout = '5s'` (P2-2), then `op.add_column("user_language_profiles",
  sa.Column("declared_level", sa.String(20), nullable=False, server_default=""))`. With a constant
  default this is metadata-only on PostgreSQL 11+ (the runtime is PG 17, `compose.yaml:115`). It
  still takes a brief `ACCESS EXCLUSIVE` lock. On timeout the operator retries, and nothing is half-applied.
- `downgrade()`: the same `lock_timeout`, then `op.drop_column(...)`. Its docstring says it **drops
  learner data and exists for rehearsal only**. Architecture §6 forbids down-migrating learner data away.
- No backfill. No startup Alembic (D-002). Not in `GATED_REVISIONS` (additive).
- **Sandbox precondition (P2-1):** the sandbox must first reach `20260924_0016` through 0015 and 0016's
  own authorized route, verified with `scripts/start_orena_sandbox.ps1`, before 0017 moves into `versions/`.
  Then the human takes a `scripts/runtime_backup.py` backup immediately before
  `python scripts/bootstrap_runtime_schema.py --upgrade --from 20260924_0016 --confirm`.
  After the move, any runtime not at 0017 refuses to start. That is the intended guard.

## 4. API: the existing `/api/learner-profile`

**Allowed set (P1-2).** `allowed_levels = ('',) + language_registry.language(current_language_code()).levels`.
This is the same key the repository writes under. It **fails closed**: if the lookup returns
`None` or an empty `levels`, only `''` is accepted and any code is refused with `invalid_value`.
There is never an English fallback, and neither `active_profile()` nor `active_levels()` is used.
`account_profile.py` stays free of request context: `patch_profile` and `effective_settings` take
`allowed_levels` from the caller (`becoming_memory.py`). `declared_level` becomes `stored=True` with
its allowed set supplied that way. The same set applies to:
- PATCH validation;
- session overrides in `effective_settings`;
- read-back: a stored code outside the current list reads as `''`, `source: default` (the
  module's existing rule for retired values, `account_profile.py:150-154`).

**GET:** the flat shape is unchanged. `declared_level` is the value for the scope's learning
language, `''` when not declared or when no row exists (`exists: false`). `settings.declared_level`
is `{value, source, version}`. There is no per-language map, because other languages are other scopes
(§1 "A language switch loads that language's profile"). The `language` field changes to report
`current_language_code()`, the scope code (P1-2). This is identical output for `en`/`zh` today; it
only differs for a future third language, where it is currently wrong. The native schema's
`z.enum(['en','zh'])` (`mobile/src/api/contracts/learning.ts:26`) is unaffected while only en/zh exist.

**PATCH** `{expected_version, declared_level}` sets the scope language's level, and `''` clears it.
- An invalid code (e.g. `HSK3` while learning `en`) gets **400 `invalid_value`** `{reason, field,
  current_version}` (P2-6). That is the status every other profile field uses. FastAPI's 422
  stays reserved for body-shape errors.
- A version mismatch gets 409 `version_conflict`. Creation uses `''`.
- `patch_learner_profile` includes `declared_level` in its upsert (`becoming_memory.py:170-179`).

**Conditional write (P2-4, adopted).** Today PATCH reads and upserts in two sessions, so two
concurrent PATCHes with the same `expected_version` both succeed. Both repositories make the update
conditional (`UPDATE … WHERE updated_at = :expected`; 0 rows → `version_conflict` → 409), and the
insert path relies on the existing unique key. No schema change. The one-second token resolution
(`becoming_memory.py:152`) and onboarding's deliberate single 409 retry remain. Both are recorded in §8.

**PUT (native, frozen; P2-5):** `LearnerProfileIn` has no `declared_level`. The repositories update the
column **only when the key is present** in `values`, so PUT preserves it. The PUT response
(`becoming_memory.py:191-198`) does **not** gain `declared_level`, because the native schema is `.strict()`
(`learning.ts:21-27`).

**Unchanged:** `interface_language` stays `stored=False` (501). Old UI (`/`) readers keep their
CEFR regexes (`ui/home.js:96`, `reference.js:1222`, `writing-entry.js:80`); `ui/profile.js:90` shows
the raw value.

**Other consumers (P2-7):**
- `persistence/admin_repository.py:318-321` keeps `"level": None`, because surfacing learner data to
  admins needs an explicit use case (architecture §1). Its comment is corrected to say that.
- `static/orena/ui/expression.js:186` accepts CEFR only, so a stored HSK level never reaches a Chinese
  learner's Writing target. That is an EN/ZH parity gap, recorded in `UI_BACKEND_GAPS.md` as a
  follow-up and not part of this slice.

## 5. Human decisions (confirmed at approval)

1. **Meaning (P1-1):** "self-declared current level, never measured or inferred" (§1), with the
   architecture and `account_profile.py` wording amended.
2. **Existing accounts:** with default `''`, every existing learner who has a profile row opens
   `#/welcome` once on `/next` per learning language they use, until they pick a level.
   **(A) recommended:** accept that; completing Welcome stores the level.
   (B) is possible only if the pinned design draws an entry at the Level step.
   (C), a backfill from evidence, is **rejected**: it would store an inferred value in a stated field.
   If the level save fails, Welcome appears again next visit and the flow never claims the save happened.
3. **HSK "1-9" (P2-8):** D-099's "HSK 1-9" is satisfied by the registry's seven codes, with `HSK7-9`
   as one HSK 3.0 band. `HSK7`/`HSK8`/`HSK9` are not added. Whether onboarding draws a cell for
   `HSK7-9` stays a design question.

## 6. Deletion and export

- The column sits on a row already removed by `users.id ON DELETE CASCADE`. No runtime deletion path
  exists (D-055). **The approval entry records (P2-9)** that `user_language_profiles`, now holding a
  learner-stated datum, is part of the owner-table deletion enumeration that D-055 precondition (b)
  requires. The row is keyed by account, not incarnation, like every owner table; D-055 covers that.
- Export: the architecture defines no export contract, so none is added.
- Backups: `runtime_backup.py:96-110` compares row counts and is unaffected.

## 7. UI (brief; after approval; no design invention)

- Onboarding: `declaredLevelPatch` accepts the active language's registry codes (HSK too) instead of
  the CEFR-only constant (`model.js:188-199`). The "not yet stored" comments go. A failure never blocks the flow.
- `entryRoute` also returns `welcome` for `profile.exists && !profile.declared_level`
  (`routes.js:83-87`). An unreadable profile (`null`) still opens Today.
- Today and the shell already read `profile.declared_level` (`today/screen.js:32`, `shell/context.js:65`).
- Settings: unchanged. Showing a level there is a design question.

## 8. Tests, rehearsal, risks, rollback

**CI tests, pure contract** (`scripts/test_orena_account_profile.py`):
- The "declared_level is unstored" assertions (`:164-177`) move to `interface_language`. That is a
  named contract change, not a weakened assertion.
- New tests: allowed set from `allowed_levels`; `''` clears; `HSK7-9` accepted for zh.
- **Stub third language (P1-2):** a monkeypatched `language_registry._REGISTRY` entry with its own
  `levels`. `B1` is refused and its own code accepted. An entry with empty `levels` accepts only `''`.

**CI tests against the real `SQLiteSpecializedLearningRepository` (P1-3),** through the route or service:
- PATCH a level, then GET returns it with `source: saved`;
- PUT (native payload) preserves it, and the PUT response has no `declared_level`;
- PATCH `goal` preserves it;
- PATCH `''` clears it;
- `en` and `zh` scopes stay independent;
- stale `expected_version` → 409; invalid code → 400 `invalid_value`;
- an existing SQLite file without the column is upgraded by `initialize()` and reads `''`.

**Fake repository (P1-3):** `FakeProfileRepository.upsert_profile_record`
(`tests/test_orena_account_profile_runtime.py:19-31`) gets merge semantics, because it currently
replaces the record. The existing tests are kept.

**Frontend (P1-3):** `scripts/test_orena_shell.mjs:75` ("a level the backend cannot store is not asked
for" → `today`) changes, as a **named contract change**, to expect `welcome`. The `entryRoute` truth
table covers: no row → welcome; row without level → welcome; row with level → today; unreadable → today;
failed save (still `''`) → welcome. The onboarding `.mjs` test sends HSK codes.

**PostgreSQL rehearsal (P1-3; architecture §6 step 3, "SQLite tests alone are insufficient"):**
recorded before the `git mv`, on a throwaway PG 17 and never a shared runtime. It needs Docker, which
the owning lane or the human runs. It covers:
- up/down/up of 0017;
- pre-existing rows read `''`;
- the PG repository's PUT and PATCH-`goal` preserve the level;
- two concurrent PATCHes with the same version give one 200 and one 409;
- ORM equals the migrated schema (the `tests/test_reading_evidence_schema_parity.py` pattern).

**Whole suite:** green at the new head. The head-sensitive tests
(`tests/test_adaptive_reading_schema.py`, `tests/test_reading_canonical_cutover_scripts.py`) are included.

**Risks:**
- Every existing learner sees Welcome once (§5).
- The version token has one-second resolution. The conditional write narrows the race but does not
  remove it within the same second. An integer version column is not authorized (§9).
- Onboarding's single 409 retry is last-writer-wins by design.
- The migration's lock wait is bounded by `lock_timeout`.

**Rollback:**
- Before writes: revert the code and keep the additive column. Older code selects only mapped
  columns, and the server default covers its inserts.
- After writes: keep the column, then either revert the entry rule (levels stay stored and unused) or
  ship a reviewed forward fix.
- Never downgrade a runtime holding learner levels. Never return to SQLite authority.

## 9. Not decided here (holds, AGENTS §7)

- The canonical multi-user / account-sync architecture: no sync cursor, change record, operation
  receipt or incarnation key is added to profiles.
- An integer profile version column.
- `support_language` stored per language row though architecture §1 calls it account-wide
  (`becoming_memory.py:64-68`); `interface_language` storage.
- Account deletion and re-registration runtime (D-055 preconditions).
- `ja`'s level list (it arrives with its registry entry, no schema change); the `HSK7-9` onboarding cell.
- The Writing target's HSK parity gap (P2-7), recorded as a follow-up.

## 10. Review response (`DECLARED_LEVEL_STORAGE.REVIEW.md`)

| Finding | Resolution |
| --- | --- |
| P1-1 meaning | §1 states "self-declared current level, never measured, inferred or projected". §5.1 makes it a human confirmation. The approval entry amends architecture §1 and `account_profile.py`. |
| P1-2 allowed set | §4: `('',) + language_registry.language(current_language_code()).levels`. It fails closed with no English fallback, and applies to PATCH, overrides and read-back. GET `language` reports the scope code. §8 adds the stub third-language test. |
| P1-3 test plan | §8: real SQLite repository tests, a merge-semantics fake, a recorded PG 17 up/down/up rehearsal, the named `test_orena_shell.mjs:75` change, and the whole suite at the new head. |
| P2-1 sandbox precondition | §3: sandbox verified at 0016 first (currently 0014), then backup, then upgrade. |
| P2-2 lock | §3: `SET LOCAL lock_timeout = '5s'` in upgrade and downgrade; the downgrade docstring says it drops data. |
| P2-3 importer | §2: importer untouched (verified at `importer.py:286-290`). |
| P2-4 concurrency | §4: conditional write adopted (no schema change). The remaining same-second race is recorded in §8. |
| P2-5 native strict schema | §4: PUT preserves the column and its response gains no field. Asserted in §8. |
| P2-6 status code | §4: 400 `invalid_value` kept. |
| P2-7 other consumers | §4: admin comment corrected with the value kept `None`. The `expression.js` HSK gap goes to `UI_BACKEND_GAPS.md`. |
| P2-8 HSK 1-9 | §5.3: registry codes, `HSK7-9` as one band; human confirms. |
| P2-9 account-keyed row | §6: the approval entry lists `user_language_profiles` in D-055 (b)'s enumeration. |
