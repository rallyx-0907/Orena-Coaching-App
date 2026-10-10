# Architecture review: target-language count entitlement (PR #125)

| | |
|---|---|
| Reviewer | claude-opus-5-5, Delegated Architecture Reviewer (independent of the implementer) |
| Reviewed commits | First review `bd6c01fa5d5f9e145cfb3817380346ddb67dc059` (base `2c04fc1e`); re-review `bd6c01fa..f817b37371247ee1d28ed6c9f87a8c6a23d15cc1`; re-review 2 `f817b373..34f275e6dea71f429c370ae610269c1c112db2a4` |
| Final verdict | **APPROVE** at exact reviewed SHA `34f275e6dea71f429c370ae610269c1c112db2a4`. Earlier: REQUEST CHANGES at bd6c01fa (F1 first-choice race, F2 never-chosen session), REQUEST CHANGES at f817b373 (F8 default-language writes) — superseded. |
| After the reviewed SHA | Documentation only: this record; decision number assigned (D-170). Not product approval; not activation. Activating languages.target with only en/zh needs the human's GO and the D-161 points 6-8 review; an adopted-languages record (schema, human gate) is required only before a third target language. |

# Architecture review — PR #125 `languages.target` count entitlement (D-170)

- Reviewer: claude-opus-5-5, acting as **Delegated Architecture Reviewer** (AGENTS.md "Architecture review authority"); independent of the implementer (Claude Sonnet 5.5).
- Reviewed: branch `feat/entitlement-languages`, commit **bd6c01fa5d5f9e145cfb3817380346ddb67dc059**, base `origin/main` 2c04fc1e (`git diff 2c04fc1e..bd6c01fa`, `gh pr view 125`).
- Mode: read-only. Nothing in the repository was edited, committed or pushed. No shared runtime was touched.
- Date: 2026-10-10

## VERDICT: REQUEST CHANGES

There are two P1 findings, F1 and F2. In each one, a direct API client puts a Free (limit 1) account into two target languages with only `en`/`zh` enabled. That breaks the binding requirements "direct API can't bypass" and "client state can never bypass". Both fixes are small and stay inside the PR's design: no schema change and no redesign. With F1 and F2 fixed and tested, I expect to re-review this as APPROVE (F3–F5 are P2). The rest of the design is sound: the count model, the guard inside the transaction under `users FOR UPDATE`, the fail-closed split, the switch wiring, `admit()` refusing the entitlement, the client being display-only, and tests 1–7.

## Evidence (local execution, not CI)

- Throwaway `postgres:17-alpine` (`ent-lang-review-pg-24241`, 127.0.0.1:5554, stopped afterwards). One ephemeral `ai-writing-coach:local` container (`-m 2g`, worktree mounted `:ro`, sharing the PG container's network namespace).
- `pytest tests/test_language_limit_postgres.py tests/test_language_limit.py tests/test_quota_gate.py` with `ORENA_TEST_POSTGRES_URL`: **77 passed**, 0 skipped. The 19 PG proofs ran.
- Reviewer probe `scratchpad/ql/probe/test_review_probe_lang.py` (not in the repo): **F1 reproduced on real PostgreSQL**. Output:
  `RESULTS [('en', 200, {'stored': False, 'active': 'en'}), ('zh', 200, {'stored': True, 'active': 'zh'})]`,
  `ACTIVES {'zh': 'zh', 'en': 'en'} STORED zh HELD {'zh'}`; after one learner row from the `en` session, `held == {'en','zh'}` on Free.
- Schema sweep on the head-migrated database: every table with a learner key and a language column is either among the 15 ORM tables or is incarnation-keyed (`works`, `work_turns`, `change_records`, `mutation_receipts`, `language_provenance`, `projection_checkpoints`). `works` is counted. The others are derived from works. **The ownership read is complete.**
- Row-creating APIs (focus 1): every learner-row writer scopes by the request language `LANGUAGE_CODE_CTX`, which `UserIsolationMiddleware` sets from the signed session cookie (`auth_support.py:543-546`). No learner write takes its language from the body:
  - `/api/evaluate` `learning_language` must match the session (409 `language_scope_mismatch`, `app.py:2981`).
  - `/api/agent/turn` and voice reject `context.locale.target != learner.language` (409, `agent/api.py:122,216`).
  - Works use `Scope(..., _language())` (`work_api.py:106`).
  - `media_api` / `media_interaction` `target_language` is the translation/support language.
  - Admin media import writes the shared library, not learner rows.

  So the cap's integrity reduces to one question: **can a session's language be one the account was never admitted to?** F1 and F2 are the two answers that are yes.

## Findings

### F1 — P1 — Race on a fresh account's first choice moves the session past the guard
- **Where:** `writing_coach/core/platform_api.py:64-71` and `:82`. Root cause is `persistence/auth_repository.py:334`.
- **Scenario (Free, account never chose, no token):** two token-less `POST /api/platform/language` arrive in parallel, `zh` and `en`. One cookie is enough, because the client keeps whichever `Set-Cookie` it likes.
  1. Both read the row (`learning_language == ''`, token `''`) and take the "first choice" branch.
  2. `zh` locks `users`, its guard passes, it commits.
  3. `en` then gets the lock. `expected` (None) no longer equals `settings_updated_at`, so **the guard is skipped** (line 334). The conditional UPDATE matches 0 rows, giving `SettingsVersionConflict` → 409 `HTTPException`.
  4. Line 70 `except HTTPException: stored = False` swallows the 409 (it only re-raises `EntitlementRefusal`). Line 82 then sets `session["language"] = "en"` and answers 200.
  5. Any learner write from that session creates `en` rows. The Free account now holds `{en, zh}`, and both stay "held", and therefore switchable, forever.
- **Proved** on PostgreSQL by the probe above.
- **Required fix:**
  - When `adoption is not None`, the first-choice branch must not swallow a failed guarded write. Either write with `expected_token=None` (the server-read token under the lock, so the guard always judges, as in the third branch), or re-raise any `HTTPException` when `adoption is not None`.
  - The session may be set only after a write that the guard judged, or when the language is held.
  - Add a PG test for this race and a hermetic twin. The existing concurrency tests cover only the stored-language and `holds()` branches.

### F2 — P1 — A session that never chose keeps running in `DEFAULT_LANGUAGE` after the account stores another
- **Where:** `auth_support.py:524` (the `language_checked` short-circuit), `:531` (`except Exception: return ""`) and `:545` (`... or seeded or DEFAULT_LANGUAGE`).
- **Scenario (Free, two sessions, e.g. two devices or two logins):**
  1. Session A makes its first `/api/` request before any choice. The middleware finds nothing stored and sets `language_checked = True`, so A runs in `en`, the default, and is never re-seeded. Only `/api/session/bootstrap` re-seeds it, and a direct client never calls that.
  2. Session B chooses `zh`, which is stored, so held is `{zh}`.
  3. Session A writes any learner row (grammar progress, saved word, profile PUT, essay…). That row is in `en`, the guard is never consulted, and held becomes `{en, zh}` on Free.

  The same happens on a transient failure of the stored-language read (line 531): the request silently runs in `en`.
- **Required fix (minimal, no schema):** while `languages.target` is enforced, the request language for a session with no explicit language must come from the account, not from a cached "never chose" flag. Either:
  - (a) ignore `language_checked` under enforcement, so a never-chosen session re-reads the stored language (one PK read, only for sessions that have not chosen; it stops once the session is seeded); or
  - (b) have `language_checked` record the account's `settings_version`, and re-read when bootstrap or any write sees a newer one.

  A failed read under enforcement should answer 503 for mutating requests rather than fall back to the default. Add a test: account stores `zh`, session flagged `language_checked`, a write route runs in `zh` (or is refused), never `en`.

### F3 — P2 — Stale session on a language that has dropped out of "held" (the implementer's self-declared risk)
- **Where:** `platform_api.py:72` (`holds()` is read unlocked; a held switch is session-only), and the derived-held model.
- **Severity:** with only `en`/`zh` enabled, this cannot take an account above what it legitimately held before. Dropping out of "held" needs the language to have been held (stored, no rows) and then for the stored language to move to another held language. The stale session's later writes restore a language the account held at that limit or above it (downgrade or catalogue edit), which the human rule "downgrade keeps both" already allows. It becomes a real bypass with **three or more enabled languages**, which is the implementer's 3-step. There is a related pre-activation variant: a token-less session-only switch made before the switch is turned on survives up to 14 days (cookie `max_age`). That is P3.
- **Required:** record it as an activation precondition in D-170 and QTA-7/QTA-18: "before a third target language is enabled, close the stale-session path". The path is closed by the explicit adopted-languages record (a schema change, a human gate) **plus** a per-request check that the session language is adopted, or by binding the session language to the settings version (F2 option b). No code change is needed for this merge once F1 and F2 are fixed.

### F4 — P2 — `deletion_enumeration.ACCOUNT_KEYED_TABLES` misses 7 of the 15 tables that now carry the entitlement
- **Where:** `writing_coach/persistence/deletion_enumeration.py:19-28` against `language_ownership.language_scoped_tables()`.
- **Failure:** `users.id = stable_uuid("user", user_key)` survives re-registration, and those rows are keyed by `user_id`, not by incarnation. If the D-055 workflow is built from this enumeration, a recreated account still "holds" the languages of:
  - `essay_revisions`
  - `library_collections`
  - `reading_ability_projections`
  - `reading_attempts`
  - `reading_legacy_sessions`
  - `text_discussions`
  - `vocabulary_decks`

  The PR's "recreated account starts empty" test simulates deletion by hand and does not catch this. The gap is pre-existing, but this PR makes it load-bearing.
- **Required (cheap, this PR or a follow-up before the deletion runtime):** add the 7 tables to `ACCOUNT_KEYED_TABLES`, or to `CASCADED_TABLES` where an FK cascade really covers them. Add a drift test asserting `{t.name for t in language_scoped_tables()} <= set(ACCOUNT_KEYED_TABLES) | set(CASCADED_TABLES)`.

### F5 — P2 — The tests do not cover the paths where the bypasses live
- The hermetic and PG tests prove cases 1–7 well. I checked each:
  - (1) `test_1_*`
  - (2) `test_2_*`: context, nothing written, session unmoved
  - (3) `test_3_*`
  - (4) `test_4_*`: both switchable, rows kept, third refused, also via PATCH
  - (5) `test_5_*`: PATCH, token-less, stale token, never-chose
  - (6) `test_6_*`: catalogue and subscription 503 for adding only, held switch OK
  - (7) `test_7_*` plus the stored-catalogue test
- **Missing:** the F1 race; the middleware or session path (F2); a PG test proving that removing the lock fails the test (the claim is in D-170, and the repository-level serialisation test does exercise the lock); `feature_not_in_plan` on PG.
- `scripts/test_language_limit_notice.mjs` checks the screens with regexes over the source. That is acceptable for a toast, but it is not a behaviour test.

### F6 — P3 — Nested pool connections while the `users` row is locked
- **Where:** `language_limit.py:83` `_limit()` runs inside the locked transaction (`auth_repository.py:338`). It opens a second and third pooled connection: the catalogue setting read and `get_subscription`. Both are plain MVCC reads, so there is no lock wait and no undetected self-deadlock. I checked the lock order: `apply_membership` locks `users` then `subscriptions`, `_allocate` locks `users`, quota and commerce lock `account_incarnations`, so there is no cycle with the guard.
- Under about 15 or more simultaneous adoptions (pool 5 + overflow 10), the inner checkouts can starve the pool until the 30 s timeout. Each failure would then read as a 503 "subscription".
- **Suggested:** read the limit (catalogue and plan) **before** taking the lock and pass it into the guard. A plan change still serialises, because `apply_membership` takes the same `users` lock, so re-check the plan id under the lock only if strictness requires it. Alternatively, reuse the locked session for the subscription read.

### F7 — P3 — Notes
- `FOR UPDATE` (not `FOR NO KEY UPDATE`) blocks FK inserts into the 15 tables for that account during the guard (milliseconds). That is acceptable, and it helps consistency: an in-flight insert in a new language commits before the guard reads.
- A plan whose catalogue *disables* `languages.target` (or sets limit 0) refuses even a new account's first language, so onboarding cannot complete. The behaviour is consistent but worth a line in D-170 for administrators.
- `held_by` is an unlocked union over 15 tables plus works on every commerce (Plan & usage) read when enforced. That is fine at current scale, and each per-table `DISTINCT` relies on the existing `user_id`-leading indexes.
- Catalogue edits reach other workers within `CACHE_SECONDS` (5 s). Plan changes are immediate. This meets "admin plan change applies immediately".

## Focus-area conclusions

1. **Mutation paths.** The two routes are the only writers of `users.learning_language`, and both go through one guard. No row-creating API accepts an arbitrary target language: all are scoped to the session. The completeness hole is how the session language is obtained (F1, F2), not some other API.
2. **Stale session.** The F3 severity is P2 with two languages and becomes P1 before a third language is enabled. The minimal fix is session-language admission (F2 option b) or the adopted record (human schema gate).
3. **Concurrency.** The PG proofs pass (77/77). `FOR UPDATE` on `users` serialises the adoptions correctly. There is no deadlock cycle with incarnation, quota, commerce or billing locks. The one serialisation defect is the swallowed 409 in F1.
4. **Fail-closed and switch.** This is consistent with D-161:
   - adding fails closed on an unreadable catalogue or plan (503 `quota_unavailable`, retryable);
   - a missing store or an unreadable switch answers 503 for every selection, never "unlimited";
   - `WIRED_ENTITLEMENTS`/`ENFORCEABLE` are wired into the switch, the validation and the admin report;
   - `_require_bucket_meter` makes `begin`/`admit`/`check_available`/`require_ready`/`begin_voice` refuse `languages.target`;
   - the admin plan and catalogue changes are read per mutation.
5. **Recreated account.** The semantics are defined and correct *if* the deletion workflow deletes every `user_id` table. It does not list 7 of them (F4).
6. **Client.** It renders the server's 403 truthfully: the server's `limit`/`owned` figures, EN/VI/ZH, plural-aware, and "See all plans". It changes nothing locally before or after a refusal (`settings/screen.js` `onTargetPick` returns before `adoptLearningLanguage`; onboarding the same). A 503 shows the generic save error. There is no client enforcement or counting.
7. **Tests.** Cases 1–7 are proven, hermetically and on PG. The missing tests are listed in F5.

## Required before merge
1. F1 fix plus PG and hermetic race tests.
2. F2 fix plus a test.

## Required before activating on :8000
3. F3 recorded as a precondition for a third language.
4. F4 enumeration completed or explicitly tracked against the D-055 build.

---

# Re-review — PR #125 at f817b37371247ee1d28ed6c9f87a8c6a23d15cc1 (on bd6c01fa)

- Reviewer: claude-opus-5-5, Delegated Architecture Reviewer (independent). Read-only.
- Reviewed: `git diff bd6c01fa..f817b373`.
- Date: 2026-10-10.

## VERDICT: REQUEST CHANGES (one P1: F8)

F1, F2 (as specified), F4, F5 and F6 are fixed. F8 is new: it is the remaining part of F2's root cause. It needs no schema change.

## Evidence (local execution, not CI)

- Throwaway `postgres:17-alpine` `ent-lang-review-pg-18777` (`-m 1g`), stopped afterwards. One `ai-writing-coach:local` container (`-m 2g`, worktree mounted `:ro`).
- `tests/test_language_limit_postgres.py`, `tests/test_language_limit.py`, `tests/test_quota_gate.py` and `tests/test_d4_deletion_enumeration.py` with PostgreSQL: **93 passed**.
- `node scripts/test_language_limit_notice.mjs` on the host: PASS.
- **Original probe, re-run unmodified**, now FAILS its bypass assertion, as intended:
  `RESULTS [('en', 403, language_limit_reached {limit 1, owned 1, languages ['zh']}), ('zh', 200, stored)]`, `ACTIVES {'zh': 'zh', 'en': None}`, `HELD {'zh'}`.
  F1 is closed: the loser is judged, refused, and its session is not moved.
- **New probe** `probe/test_review_probe_lang_inflight.py` uses the real `UserIsolationMiddleware`, the real routers and PostgreSQL, with one cookie. It PASSES, which means the bypass works:
  `WROTE {'language': 'en'} CHOSE (200, stored zh) STORED zh HELD {'en','zh'}` on Free.

## Fix check

- **F1 fixed.** `platform_api.py` 63-67: while enforced, the first choice is written with `expected_token=None`, so the guard always judges it. The non-enforced path is unchanged.
- **F2 fixed as specified.** `auth_support.py` 528-545: while enforced, `language_checked` is not trusted. A failed read answers 503 `quota_unavailable` (`reason: language`) for non-GET/HEAD/OPTIONS requests; a read carries on. When not enforced, the behaviour is the old one apart from the `enforced()` call.
- **F4 fixed.** The 7 tables were added to `ACCOUNT_KEYED_TABLES`, with a subset drift test. The runbook was updated.
- **F6 fixed.** The limit is read in `Adoption.__init__`, before the lock, and the failure is raised only when the write adds a language. This leaves a residual TOCTOU, see F9.
- **F5 fixed.** There is a PostgreSQL race test, the middleware tests, `feature_not_in_plan` on PostgreSQL, and a behavioural `.mjs` notice test.
- **F3/F7 recorded** as D-170 points 14-15.

## New findings

### F8 — P1 — An account that never chose still writes learner rows in the unadmitted default language
- **Where:** `auth_support.py:575-577`. For a never-chosen account the request language is `DEFAULT_LANGUAGE`, decided at request start and never judged. The guard only judges `users.learning_language` writes.
- **(a) Bypass (proved on PostgreSQL, one cookie).**
  1. A never-chosen Free account starts a slow write. Any provider-backed route works, e.g. `POST /api/evaluate` or `/api/agent/turn`; the language is fixed as `en` when the request starts.
  2. During it, the same cookie sends `POST /api/platform/language {zh}`. Held is `{}`, so it is admitted and stored.
  3. The slow request then inserts its `en` row. Free now holds `{en, zh}`, and both stay switchable.

  F2's per-request re-read does not help, because the decision was made before the adoption.
- **(b) Learner-facing regression (code-evident, not browser-verified; verify on :8021).**
  1. On the onboarding Languages step, the target and support pills are both live (`onboarding/screen.js` ~200-221). The bootstrap reports `active: en` for a never-chosen account.
  2. A Free learner who taps a support language first sends `PATCH /api/learner-profile` (`pickSupport` → `patchProfile`, `becoming_memory.patch_learner_profile`). That upserts a `user_language_profiles` row for the session language, `en`. `en` is now held.
  3. Tapping Chinese then answers 403 `language_limit_reached`. A Free learner cannot start Chinese, which is a P1 because it breaks EN/ZH parity.

  PR test `test_5 (e)` codifies this server behaviour; onboarding walks into it.
- **Required fix (no schema).** While `languages.target` is enforced, an account with no stored learning language must not write language-scoped learner data in the default language:
  - **Server:** in the middleware, a mutating `/api/` request from a never-chosen account (stored `''` after the per-request re-read) answers 409 with a stable category, e.g. `learning_language_required`. The exceptions are routes that write no learner rows: `/api/platform/language`, `/api/account-settings`, `/api/auth/*`, `/api/session/*`, logout, and any feedback-type route the implementer enumerates.
  - **Client:** onboarding stores the target before any profile write. Either `pickSupport` and the level step first call `selectLearningLanguage(context.language)` when the account has none stored, or the support pills stay disabled until a target is stored.
  - **Tests:**
    - The in-flight probe above (the slow write is refused, or held stays `{zh}`).
    - A Free never-chosen account: support pick, then Chinese, gives 200 and held `{zh}`.
    - A never-chosen English learner: support pick, then level, stores `en` and works.

### F9 — P3 — The limit is read before the lock
An admin downgrade that commits between `Adoption.__init__` and the `users` lock is not seen by that one in-flight adoption. The window is milliseconds, and the next mutation sees the new plan, so "admin change applies immediately" still holds in practice. Accept and record. Optionally, re-read only the subscription plan id inside the locked session.

### F10 — P3 — `_language_count_enforced()` runs before the cheap short-circuits
- **Where:** `auth_support.py:532`.
- `quota.switch()` is called on every request, including static paths and sessions that already have a language. It is cached (`SWITCH_CACHE_SECONDS`), but on a cache miss it does a synchronous settings read inside async `dispatch`.
- **Fix:** compute it only when the session has no language and the path is `/api/`.
- The PK read per request for never-chosen sessions is acceptable: it is a transient pre-choice state, and it stops once the session is seeded.
- `except Exception: return False` falls back to the old behaviour (not enforced). That is tolerable, because `switch()` already maps an unreadable store to the `unavailable` state.

## The coordinator's question: is the adopted-languages record required for activating `languages.target` on :8000 with only en/zh?

**No. Architecturally it is required before a third target language is enabled, not for activation with English and Chinese only.**

D-170 point 15 and QTA-18(4) currently say "before ANY third language is enabled ... **or the entitlement is activated on :8000**". The second clause over-states the requirement and should be removed. Reasoning:

- With two languages and a limit of 1, a session language comes from one of these sources:
  - (i) a judged write, which leaves it held;
  - (ii) a switch to a held language;
  - (iii) seeding from the stored language, which is held;
  - (iv) the default for a never-chosen account. This is F8, and it is fixable without schema.
- A language L leaves "held" only if the stored language moves from L to another held language M. On limit 1 that requires `{L, M}` to have been held already, which only happens through a legitimate downgrade, a catalogue reduction, or pre-activation use. So a stale session's later writes only restore what was legitimately held. They never exceed it.
- Deleting all data in a language cannot free a slot on Free, because the stored language is always held. Plus and Pro (limit 2) already allow both languages.
- What remains is a pre-activation session-only switch that survives up to 14 days (cookie `max_age`). That is P3: a bounded, one-time grandfathering.
  - It can be closed without schema: while enforced, check once per session that an explicit session language is the stored or a held one, and cache the result in the session.
  - Or the human can simply accept it.

**What :8000 activation with en/zh needs:**
1. F8 fixed (P1).
2. This review's re-check.
3. The human's explicit GO.
4. The D-161 points 6-8 review that D-170 point 13 names.

**What it does not need:** the schema record. The adopted-languages record together with per-request admission becomes mandatory the moment a third language is enabled in the registry.

---

# Re-review 2 — PR #125 at 34f275e6dea71f429c370ae610269c1c112db2a4 (on f817b373)

- Reviewer: claude-opus-5-5, Delegated Architecture Reviewer (independent). Read-only.
- Reviewed: `git diff f817b373..34f275e6`.
- Date: 2026-10-10.

## VERDICT: APPROVE

No P0, P1 or P2 remains. F8 is closed on the server and in onboarding. The remaining items are P3 and are recorded below. This is architecture approval only. It is not product approval and not activation: :8000 still needs the human's GO and the D-161 points 6-8 review (D-170 point 13).

## Evidence (local execution, not CI)

- Throwaway `postgres:17-alpine` `ent-lang-review-pg-1646` (`-m 1g`), stopped afterwards. One `ai-writing-coach:local` container at a time (`-m 2g`, worktree mounted `:ro`). Nothing left running.
- PostgreSQL proofs plus hermetic tests: `tests/test_language_limit_postgres.py`, `tests/test_language_limit.py`, `tests/test_quota_gate.py` and `tests/test_d4_deletion_enumeration.py`: **103 passed**.
- On the host:
  - `node scripts/test_language_limit_notice.mjs`: PASS.
  - `node scripts/test_orena_screen_onboarding.mjs`: PASS.
  - `validate_browser_esm_graph.mjs`: OK, 277 modules.
- **Probe 1, unmodified** (F1 race): its bypass assertion still fails, as intended. The loser gets 403 `language_limit_reached` and held stays `{zh}`.
- **Probe 2, unmodified** (`test_review_probe_lang_inflight.py`): it still "passes", but that is an artefact of my probe. Its slow route is `/_slow_write`, outside `/api/`, and the gate is scoped to `/api/`. Every learner-row writer lives under `/api/`; the only mutating route outside it is `POST /auth/logout`, from my route walk below.
- **The same probe with only the path changed** to `/api/_slow_write` (`test_review_probe_lang_inflight_api.py`): the slow write is refused at request start with 409 `learning_language_required`, the zh choice stores, and **held = `{zh}`**. The F8 bypass is closed.
- **Route walk.** I walked the real app's routes, including FastAPI's `_IncludedRouter` objects, and found 137 mutating routes:
  - 57 under `/api/` are exempt;
  - the only non-`/api/` mutating route is `/auth/logout`;
  - none are hidden from OpenAPI, so the PR's OpenAPI-based coverage test sees the same set.

## The coordinator's scrutiny points

1. **The "any path with an `admin` segment" exemption.**
   - Every exempt `admin` route is an operator route: AI config and credentials, admin console, content packs, grammar, reading and vocabulary admin, media admin import/upload/preview, billing refund, product admin plans/quota/membership.
   - Each is admin-guarded (`_require_admin`/`require_admin`, or under `/api/admin/*` routers).
   - All of them write shared content or platform state, never the 15 language-scoped learner tables or `works`.
   - No learner route has an `admin` segment, so a learner cannot reach a learner-row writer through this exemption.
   - Residual P3: a future learner route with an `admin` segment would be exempt silently, because the coverage test pins only the non-admin exempt set. Optional hardening: pin the admin-exempt set too, or require that each exempt `admin` route depends on `require_admin`.
2. **`/api/product/` and `/api/feedback`.**
   - The only mutating `/api/product/` routes are the three admin ones (`PUT .../admin/plans`, `.../admin/quota`, `.../admin/accounts/{id}/membership`). None writes learner rows.
   - `POST /api/feedback` stores through the platform repository's `record_feedback`, an audit-style row with a `language` field. That row is not among the tables `language_ownership` counts, so it cannot grow "held".
   - `/api/billing/checkout` writes billing orders, and `/api/auth/native/exchange` creates the session.
   - The non-admin exempt set is pinned exactly by `test_f8_the_exempt_routes_are_exactly_the_ones_that_write_no_learner_rows`, so a new learner writer under these prefixes would fail CI.
3. **"`en` already held" passes the gate. Can a Free account holding `en` write `zh` rows?** **No (confirmed).**
   - Learner rows take the request language `LANGUAGE_CODE_CTX`. For a session with no language of its own, that is `DEFAULT_LANGUAGE` (`auth_support.py` `requested_language`).
   - No learner writer takes its language from the request:
     - `/api/evaluate` 409s on a mismatch;
     - agent turn and voice 409 when `locale.target` differs from the session language;
     - works are scoped to the session language;
     - media `target_language` is the translation language.
   - So a session that passes the gate on "`en` held" can only add `en` rows, which are already held. Adding `zh` still needs the guarded `POST /api/platform/language` or `PATCH /api/account-settings`, which refuses it on Free.
   - It also correctly keeps pre-count English learners who never stored a choice working.

## The rest of the diff

- **F10.** `enforced` is computed only for `/api/` requests whose session has no language. The PK read and the held read happen only for never-chosen sessions, and only on mutating requests. When not enforced, the middleware behaves as before.
- **Client.**
  - `target-first.js` stages a support pick until a learning language is stored, then flushes it after `adoptLearningLanguage`.
  - "Continue" on the Languages step stores the language the screen shows, and the level step stores the target first.
  - 409 `learning_language_required` is told in EN/VI/ZH.
  - No client enforcement or counting was introduced.
  - I did not verify this in a browser. The UI lane should walk on :8021: Free → support pick → Chinese → level. The expected outcome is held `{zh}` and onboarding completes.
- **Docs.** D-170 points 13, 15 and 16 and QTA-18(4) now state that the adopted-languages record is required before a third language, not for activation with en/zh. The pre-activation 14-day session is recorded as an accepted P3.

## Remaining P3 (record; not blocking)

- **Admin-segment exemption** is not pinned: see point 1.
- **GET handlers are not gated.** A GET that lazily inserted a language-scoped row in the default language would bypass the gate. I found none: `get_profile_record` on PostgreSQL is read-only, for example. A comment or test asserting that GET handlers never write learner rows would make this durable.
- **Enforcement in local development without a `users` row.** If enforcement is on locally, profile writes are refused with 409 until a language is chosen. The client's `needsTarget` waits only when an account row exists. This is development-only.
- **Carried from earlier rounds.** F9 is accepted. The pre-activation session-only switch can last up to 14 days and is accepted.
