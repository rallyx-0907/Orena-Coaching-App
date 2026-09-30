# Independent implementation review: learner records D4

- **Reviewer:** Claude Opus 5.5, independent reviewer subagent, not the implementer (Delegated Architecture Reviewer,
  AGENTS §1 "Architecture review authority").
- **Reviewed commits:** `5bdd2ab` (feat(d4): learner records on the server, 84 files) and, at the lead's scope
  addition, `a4390b5` (one HSK 7-9 band, canonical review modes `typing`/`cloze`/`dictation`, unknown modes refused).
  Branch `codex/work`.
- **Date:** 2026-09-30.
- **Against:** `LEARNER_RECORDS_D4.md` rev 3 + section 16, `LEARNER_RECORDS_D4.REVIEW.md`, D-103, D-104, D-105,
  migrations 0017-0023, `UI_BACKEND_GAPS.md` D4 sections, `REVIEW_POLICY.md`.
- **Method and limits.** Read-only static review of the two diffs and of the code they call (mutation commit,
  work/library/auth repositories, front-end consumers). No Docker, no PostgreSQL, no :8000/:8010, no secrets read.
  Run on the host: `node scripts/test_orena_account_settings.mjs`, `test_orena_continue_sync.mjs`,
  `test_orena_account_records.mjs`, `test_dictation_golden.mjs` (all PASS, 74 golden vectors), and
  `python scripts/validate_project_memory.py` (passes). **The implementer's pytest numbers (2984 passed / 9 skipped on
  PostgreSQL 17; 2678 passed / 315 skipped on SQLite) were not reproduced by me and are local execution, not CI.**
  CI has no PostgreSQL service, so every PostgreSQL-only proof in this change (settings token race, turn append race,
  dictation lock, history trigger, ORM/migration parity, `none_as_null`) is skipped in CI and rests on the implementer's
  local run.

## Verdict: REQUEST CHANGES

Two P1 findings (REVIEW_POLICY: unresolved P1 requires REQUEST CHANGES). Both are small, local fixes. Everything else
in the change is sound, and several parts are notably careful (server-clock token, conditional UPDATEs, per-account
stream lock for every account mutation, scope by construction on the history table, golden-vector port proof). I do not
expect a second full review: once P1-1 and P1-2 are fixed with regression tests, **the flag may go on for the lane
runtime as APPROVE WITH CONDITIONS**, the conditions being section "Conditions" below (a delta check by me or any
independent reviewer of those two fixes is enough).

| Severity | Count |
| --- | --- |
| P0 | 0 |
| P1 | 2 |
| P2 | 9 |
| P3 | 7 |

## What I verified as correct (so the lead need not re-derive it)

1. **Isolation, scope.** Every new route scopes by the authenticated account and the request's learning language:
   account records go through `work_api._scope()` (account = `stable_uuid('user', key)`, incarnation from
   `ensure_active`, language from the request) and the work id is a deterministic uuid5 over
   (account, incarnation, language, kind, key); `commit_mutation` compares the stored row's owner scope with the
   request's, so another account's or language's id is `scope_denied` (404). `set_place`/`list_places` filter
   `user_id`+`language_code`; `activity_timestamps`, `list_essay_review_history`, `refresh_essay_review`,
   `merge_essay_module_data` filter `Essay.user_id/language_code/legacy_id`; the history table has no scope columns and
   is reachable only through the scope-checked essay (test asserts no id-less reader). Provenance resolves the saved
   word by (account, language, word) and `attach_occurrence` refuses cross-account words. No IDOR found.
2. **Backbone off.** `_scope()` raises 503 `account_backbone_<state>` before any read/write on every backbone route;
   settings, `/api/continue`, `/api/learner-activity` deliberately do not depend on the flag (Design B, H-5). The
   client (`account-records.js`) writes nowhere unless `accountWorkState` is `active` and claims nothing on any error.
3. **H-17 settings token.** Server clock only. PostgreSQL: `UPDATE users ... WHERE id=:id AND settings_updated_at IS
   NULL/=:expected`, new value `clock_timestamp()` in the same statement; under READ COMMITTED a second writer holding
   the same token re-evaluates the WHERE after the first commits and gets 0 rows, so one 200 and one 409. Microsecond
   ISO token echoed verbatim; a re-serialised (millisecond) token is not equal and is refused; a malformed token is
   409 with the current one. Client timestamps never enter. SQLite (test backend only) uses the Python server clock.
   `platform_api` changes session and stored value together or not at all (409 leaves the session untouched).
4. **Turn append.** `commit_mutation` takes `account_streams ... FOR UPDATE` first, so all mutations of an account
   serialise, including the first turn of a new conversation (no INSERT race). `load` re-locks the work row, `write`
   checks role alternation, `reply_to`, duplicate client id, ended and the 24-turn limit under that lock; a replay
   returns the turn at the committed ordinal. Correct.
5. **Grammar completion.** One `INSERT ... ON CONFLICT (uq_grammar_progress_scope)`; a retake updates `last_quiz_*` and
   keeps the first `completed_at`; a completion without a quiz leaves an earlier result; `clean_quiz_result` mirrors the
   CHECK. Repository only, no route (D-105 point 4): nothing to abuse.
6. **History append-only.** Repository exposes insert (inside `refresh_essay_review`) and read only; `UNIQUE (essay_id,
   prior_fingerprint)` plus the fingerprint re-check under `FOR UPDATE` (PG) / `BEGIN IMMEDIATE` (SQLite) make the
   write idempotent across processes; a provider failure or `fallback-demo` writes nothing (`allow_fallback=False`
   plus an explicit `fallback-demo` guard); the stored pair is used, never the current profile's; `module_data` is
   merged by key. The `BEFORE UPDATE` trigger permits the cascade.
7. **Dictation port.** `dictation_evaluator.py` matches the JS line by line: NFKC, quote/hyphen mapping, whitespace
   collapse, unit regex reproduced with `unicodedata` L*/N* and Han ranges, `zh` per-Han-character units and lowercase
   on the rest, edit distance, `floor(x*100+0.5)` for `Math.round`, UTF-16 length for the 2000-char limit, same error
   codes. 74 vectors (42 en, 31 zh, 1 other) generated from the JS module, consumed by both a pytest and an `.mjs`
   gate wired into CI. **Client `best_*` is ignored**: the route overwrites `values["score"]` after `model_dump()`, the
   repository takes evidence only from `merge_progress`, `checked_attempt_count` is bounded to +1, a `client` row is
   superseded by the first verified check, and revealed/prompt writes move nothing. Unserved pair is 404, wrong
   language is 422, nothing stored on either.
8. **Nothing runs Alembic at startup; no dual write.** Not touched by this diff. SQLite `ALTER`s are in the frozen
   test backend's `initialize()` only. PostgreSQL remains authoritative.
9. **ORM vs migration.** Column names, types, lengths, nullability, the partial index `ix_library_items_place`, the
   history table (no scope columns, unique key, index) and `ck_grammar_progress_quiz` match 0017-0023;
   `place`/`review_modes` are `JSON(none_as_null=True)`. Parity test is PostgreSQL-only and compares type kind, length
   and nullability (not server defaults; see P3-6).
10. **Front end.** No mock data. Every sync helper is best effort, returns a boolean, and no copy claims "kept with
    your account" for an unacknowledged write; the device copy is retained on 503/409/failure (conversation queue stops
    on the first failure and never blocks the room; annotations union once on 409; imports/responses silent). Dictation
    replaces the browser score only when `saved.item` is acknowledged. Level and language saves never claim success on
    failure. EN/VI/ZH present for every new string (Today prompt, onboarding HSK 7-9, profile). The removed Profile/Today
    tiles (minutes, daily-goal ring, skill rings, level card) follow D-103.4 "a real metric or no metric".

## P1 findings (blocking)

### P1-1. Design B makes every opened article/lesson read as "saved", and the bookmark toggle can hit the place row

- **Where.** `writing_coach/persistence/library_repository.py:176-205` (`lookup`, unfiltered by relationship) in
  `5bdd2ab`; `set_place` creates a `started` row for every opened reading/listening/book item
  (`library_repository.py:275-331`). Consumers: `static/orena/screens/reader/source.js:108-113` and
  `static/orena/screens/content/screen.js:69-75` (`saved: Boolean(items[0])`, `itemId: items[0].id`),
  `static/orena/ui/collection.js:842-843`.
- **Failure scenario.** A learner opens an article. `memory.enter` -> `sendPlace` -> `PUT /api/continue/...` inserts a
  `library_items` row (relationship `started`, kind `reading`, no `state`, not pinned). The Reader and Content Detail then
  call `GET /api/library/items?kind=reading&sources=<id>`, which returns that row (there is no relationship filter and no
  `ORDER BY`, so `items[0]` may be the `started` row even when a `kept` row also exists). The bookmark shows as saved
  though the learner never saved it. Tapping it to un-save calls `DELETE /api/library/items/{id}` (`forget`) or PATCHes
  it with the started row's id, destroying the learner's place, or leaving the real `kept` row in place. Because the
  place is written automatically on open, this affects essentially every piece of content on the lane runtime today, not
  only when the backbone flag is on. `test_d4_continue.py` never exercises `lookup` after a place write, so nothing
  catches it.
- **Required fix.** `lookup` (and any other listing that means "the learner's library": shelf, collection items, `get`
  by id for PATCH/forget) must exclude `relationship_kind = 'started'` unless the caller asks for it; or return
  `relationship` and make both consumers filter to `kept`. Reject PATCH/DELETE of a `started` row through the library
  item routes. Add regression tests: place write then `lookup` returns nothing for that source; keep after place returns
  exactly the kept row; forget of the kept row leaves the place; place write does not create a saved state in Reader/
  Content Detail models.

### P1-2. A deleted private import keeps its full text and stays readable

- **Where.** `writing_coach/account_records_api.py:184-197` (`delete_import` re-commits with `payload=row['payload']`
  and lifecycle `deleted`); `writing_coach/work_api.py` `get_work` and `persistence/work_repository.py:55-65` (`get_work`
  has no lifecycle filter, `_shape` returns `payload`).
- **Failure scenario.** The learner deletes an imported text ("private and deletable", proposal I12). The route answers
  200 and `GET /api/imports/{id}` answers 404, but the `works` row still holds the whole pasted text (up to 12,000
  characters) and `GET /api/works/{work_id}` returns it, payload included, because it does not hide `deleted` works.
  Deleting content that the learner intended to erase leaves it stored and retrievable until an account-deletion workflow
  that does not exist yet (D-055 hold) runs. It also contradicts the documented "unavailable" semantics (ADA section 7).
- **Required fix.** On delete, commit a minimal payload (`{'id': client, 'form': form}`; no title, text or url); make
  the generic `GET /api/works/{id}` answer 404 (or an empty payload) for lifecycle `deleted`, as `get_draft` already does.
  Test: after delete, `GET /api/works/{id}` and any listing contain none of the text; a replay of the delete is idempotent.
  Because imports only exist when the flag is on, this must land before the flag goes on.

## P2 findings

### P2-1. First Dictation write races (FOR UPDATE locks nothing that does not exist)
`specialized_repository.py` `save_listening_progress_record` (~1562-1590): `SELECT ... FOR UPDATE` on a not-yet-existing
row locks nothing. Two simultaneous first checks of one segment (double tap, two tabs) both take `row is None` and both
INSERT the same deterministic primary key; one raises `IntegrityError` -> HTTP 500 and that check's score is lost (the
client toasts "save failed"). The proposal specified a FOR UPDATE policy; the test
`test_two_simultaneous_checks_are_both_kept_under_the_row_lock` seeds the row first. **Fix:** `INSERT ... ON CONFLICT DO
NOTHING` then `SELECT ... FOR UPDATE`, or catch the conflict and re-run once; add a barrier test that starts from no row.

### P2-2. Profile row token has one-second resolution and is now written by every review toggle
`becoming_memory.patch_learner_profile` (`datetime.now().astimezone().isoformat(timespec="seconds")`,
`_profile_version`) with the conditional `WHERE updated_at = :expected`. A write made in the same second as the previous
version leaves the token unchanged, so a stale writer holding it passes silently (lost update). Known and accepted for
H2, but D4 adds high-frequency writers (Settings review toggles, `saveReviewSettings` retries). **Fix:** microsecond
token (server clock) like `settings_version`; keep the string opaque.

### P2-3. `_seeded_language` reads the database on every API request for accounts that never chose a language
`auth_support.py` `UserIsolationMiddleware._seeded_language`: it sets `session["language"]` only when a stored language
exists, so an account with `learning_language = ''` (every existing account until it chooses) costs one `users` lookup
per `/api/` request. This contradicts the approved "no per-request database read" (proposal I2, P2-9). **Fix:** record
"checked" in the session (a flag, not a language) so the lookup runs once per session.

### P2-4. Unbounded server rows and receipts per account
`PUT /api/continue/{any id}` creates a `library_items` row per distinct content id with no per-account cap;
`PUT /api/responses/{key}` (client mints a new key per take), `PUT /api/annotations/{content_id}` (any string up to 255)
and `POST /api/conversations/{key}/turns` create a `works` row per key, and each mutation also writes a receipt and a
change record (annotation pushes are debounced but per change). The 20-import cap is checked outside the mutation lock
(P3-4) and no other kind has one. A buggy or hostile authenticated client can grow rows and the reserved receipt stream
without bound. **Fix (before :8000):** per-account caps per kind (recycle the oldest `started` rows beyond N; cap
responses/annotations/conversations), and record the receipt-growth exposure as an open hold with a compaction owner.

### P2-5. Opening an old Chinese essay blocks on a provider call
`static/orena/screens/writing/screen.js` `fetchEssay` awaits `refreshIfStale` before `api.essay`/`api.essayReview`;
`app.py` `essay_review_refresh` runs the provider synchronously under `_review_gate`. On the Ollama default (17-54 s per
call, timeout up to 180 s) the learner cannot read a review they already have, contradicting the comment "never blocked
from reading". **Fix:** render the stored review first, fire the refresh in the background, repaint on `refreshed`; or
give the client call a short timeout.

### P2-6. Code and schema are coupled: this code on an unmigrated database fails at login
`User`, `UserLanguageProfile`, `ListeningProgress`, `LibraryItem`, `GrammarProgress` ORM classes now select the D4
columns, and `api_session_bootstrap` reads account settings without a guard. On a runtime still at `20260924_0016` (the
proposal's own section 15 premise) `upsert_user` and `session.get(User, ...)` fail with an undefined column. Acceptable
on the lane runtime (0017-0023 applied by `72cd4cd`), fatal if this commit reaches :8000/:8010 first. **Fix/condition:**
record in the handoff that code and migrations are one deployment unit, order = backup, 0017-0023 one invocation each,
then code; the human gate already covers it, this makes it explicit.

### P2-7. PostgreSQL-only proofs never run in CI
Settings-token race, turn race, dictation lock, refresh race, trigger, parity and the `none_as_null` checks skip
without `ORENA_TEST_POSTGRES_URL`. Accepted by the proposal, but the completion report must label them local execution
and CI must not be claimed for them. **Fix:** report exactly as local; add a PostgreSQL service job in a follow-up.

### P2-8. Concurrency: settings scalar creation for a missing `users` row
`update_account_settings` raises `AccountRowMissing` -> 503 `account_settings_unavailable` in authentication-disabled
mode, and `platform_api.api_platform_language` swallows the `HTTPException` only in the first-choice branch. In legacy
mode `GET /api/account-settings` reports `stored:false`, so entry rules that key on `language.stored` will always ask
for Welcome. Not a production path (dev only); document it in `UI_BACKEND_GAPS.md`.

### P2-9. Stale canonical documents after the transition
`migrations/versions/20260930_0017..0023*.py` docstrings still say "This file is a PROPOSAL ... lives in
`migrations/proposed/`" although they are in `versions/` and applied; `0019` still names the modes `target`/`cloze`
(decided `typing`/`cloze`/`dictation` in `a4390b5`); proposal I4 payload lacks `segment`/`context`, I6 lacks
`meaning`/`support`/`origin`, I13 still says `target`/`cloze` and "dropped on write". REVIEW_POLICY requires stale
canonical documentation to be corrected before the stage closes. **Fix:** edit the docstrings and record the deviations
below in the proposal/Decision Log; update `CURRENT_HANDOFF.md` if the flag state changes.

## P3 findings

- **P3-1.** `PATCH review_modes` replaces the stored map wholesale, so `{"typing": false}` alone erases stored
  `cloze`/`dictation` (they read back as defaults). The client always sends all three; make the server merge, or require
  all three. The 400 body carries `current_version: null` where other rejections carry a string.
- **P3-2.** `list_places` fetches `PLACE_LIST_LIMIT * 4` rows then drops `cleared` ones in Python: a learner with more
  than 200 newer cleared places hides older live ones. Filter in SQL.
- **P3-3.** The generic `PUT /api/works/{id}` still accepts `conversation` and `response`, so a client can create a
  conversation-shaped work that bypasses the turn rules (own scope only). Consider refusing `conversation` there too.
- **P3-4.** `put_import` counts imports before `commit_mutation` takes the account lock, so two concurrent creations at
  19 can produce 21. Count inside the write.
- **P3-5.** Streak/`activity_timestamps` are per learning language, so a bilingual learner has two streaks. Consistent
  with "for the scope" in I14 but a product call worth recording.
- **P3-6.** `test_d4_schema_parity.py` compares type kind/length/nullability only, not server defaults, the trigger's
  existence or the CHECK expression; the deletion-enumeration test checks the constants against themselves and the ORM
  (there is no runtime path yet to test). Acceptable now; strengthen when the D-055(b) workflow lands.
- **P3-7.** `--hero-day-done: #A99BFF` is a single token value used on both themes; the AA gate passed locally, confirm
  in dark mode when the design's dark value is pinned.

## Deviations from the proposal, judged

1. **Place payload gains `segment` (<=255) and `context` (<=240).** ACCEPT. Both bounded, `PlaceIn` is
   `extra=forbid`, they carry only what the device's continuation entry already holds (sentence id, book title), and
   they are stored on the same row the learner owns. Record in proposal I4 (P2-9).
2. **Turn content stored as JSON in `work_turns.content` (Text), with `meaning`, `support`, `origin` beyond the
   proposal.** ACCEPT. Order and role stay in constrained columns (`uq_work_turn_ordinal`, role check); the JSON only
   carries client id, text, reply_to and the two display fields `restoreConversation` needs; duplicate-id and
   reply_to rules are enforced under the stream lock. Coaching is still not stored (H-8 consistent). Record it.
3. **Review toggles `typing`/`cloze`/`dictation` instead of the proposal's `target`/`cloze`.** ACCEPT as settled by
   the human decision in `a4390b5`: canonical keys `typing`, `cloze`, `dictation`, Review's `target` mode renamed
   `typing`, unknown keys and non-booleans refused with 400 `invalid_value` (stronger than the proposal's "dropped on
   write"). The device-side rename touches only `review/model.js` and `screen.js`; I found no other `'target'` mode
   consumer. Residual: P3-1 and stale docs (P2-9).
4. **HSK 7-9 as one cell (a4390b5).** ACCEPT as a recorded human decision; the design frame draws six cells, so the
   seventh is a decision, not an invention. Default stays the middle of the frame's six; EN/VI/ZH names exist; the
   server registry lists `HSK7-9` as one band and validation is per scope language.

## Tests: are they real, and were existing assertions weakened?

The D4 suites are real: they use the actual SQLite and PostgreSQL repositories (only network providers are faked),
include genuine thread-barrier races for the settings token, turn append, refresh, grammar upsert, first place open and
a dictation stored-row race, assert SQL NULL versus JSON null, and drive the real app for language seeding. Gaps: the
untested `lookup`/saved interplay (P1-1), delete-retention (P1-2), the first-insert dictation race (P2-1).

Named contract changes, each checked:

- `scripts/test_orena_account_profile.py`: `declared_level` and `interface_language` become stored; the old "not yet
  stored" assertions are replaced by tests that `interface_language` is refused on the profile PATCH (`wrong_scope`),
  that levels come from the caller's list, fail closed and clear with `''`. Legitimate and stronger.
- `tests/test_orena_account_profile_runtime.py`: fake repository gains `expected_updated_at` and merge semantics that mirror
  the real repositories. Legitimate.
- `tests/test_listening_progress.py`: autouse fixture monkeypatches the resolver and language so route-shape tests do not
  need the catalogue; the 80 -> 100 change asserts the server score replaced the client's. Legitimate (the real
  resolver is proven in `test_d4_listening_authority.py`), though it is a broad patch to keep an eye on.
- `tests/test_ai_runtime.py`: fake repository gains `merge_essay_module_data` because the linguistic cache moved to it.
  Legitimate.
- `tests/test_reading_evidence_postgres.py`: upgrades to `head` instead of `0016` because the ORM now writes D4 columns.
  Legitimate; it now tracks every future migration.
- Screen gates onboarding, today, practice, profile: the old "HSK cannot be sent", "day streak is 0", "four hero tiles"
  and "Daily goal at honest zero" assertions are replaced by their D4 equivalents (HSK is sent, streak comes from the
  activity read, only measured tiles are drawn, the weekly bar exists only against a target). Consistent with D-103.4
  and D-104 H-5; no assertion was loosened to pass.
- `a4390b5`: the "unregistered modes must be dropped" assertion was replaced by "refused with 400 and nothing
  changes", parametrised over five bad shapes. Stronger.

## Conditions (to reach APPROVE WITH CONDITIONS and switch `ORENA_ACCOUNT_BACKBONE` on for the lane runtime)

Must be fixed and re-verified first:

1. **P1-1** started rows never read as saved; regression tests.
2. **P1-2** delete blanks the payload and deleted works are not served; regression tests.

Then the flag may go on for the lane runtime, with these conditions carried in the handoff:

3. **P2-1** first-write dictation race, before Dictation is used by more than one tab.
4. **P2-5** background the Chinese essay refresh, before Writing is reviewed by the human.
5. **P2-9** correct the migration docstrings and the proposal/Decision Log for the accepted deviations.
6. **P2-2, P2-3, P2-4, P2-6** recorded as open items with owners; P2-4 and P2-6 are hard prerequisites for :8000.
7. Report every PostgreSQL-only result as local execution (P2-7); CI evidence exists for the node gates and the SQLite
   suite only.

Not a condition: P3 items and the accepted deviations.

## Scope notes

Protected areas touched: Journey/Review (Review mode rename), Library (`library_items`), shared CSS token
(`--hero-day-done`). Each change is minimal and covered by a gate that passed on the host. No native (`mobile/`) file,
no production or preview operation, no secret, and no schema change beyond the already-applied 0017-0023 is in either
commit. `docs/visual-references/**` untouched.
