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

## Delta check (a13e0a3)

- **Reviewer:** Claude Opus 5.5, independent reviewer subagent, not the implementer. **Date:** 2026-10-01.
- **Reviewed:** `git show a13e0a3` (20 files) against the findings above. Read-only, static; no Docker or PostgreSQL. The
  implementer's new results (121/121 node gates; SQLite 2690 passed / 330 skipped; PostgreSQL 3011 passed / 9 skipped) are
  local execution and were not reproduced by me.

### Verdict: APPROVE WITH CONDITIONS, for enabling `ORENA_ACCOUNT_BACKBONE` on the :8021 lane only

Both P1s are fixed at the root and the regression tests exercise the failure. No new P0/P1 found. Not approved for
:8000/:8010 (see conditions 4-5).

### P1-1 (place read as saved): fixed
- `lookup` now excludes place-only rows in SQL (`started`, no word, not pinned, no state, empty note) and orders `kept`
  first; Reader and Content Detail take only `relationship === 'kept'`; `forget` of a marked `started` row clears the
  mark and keeps the place. Tests: lookup after a place is `[]`; keep-after-place returns exactly the kept row; forgetting
  the bookmark leaves the place; un-marking a read item keeps the place; the `/api/library/items` route never returns a
  place-only row; a node gate pins the client rule.
- Paths I looked for and did not find: a place-only row is reachable only by its item id, which no listing returns
  (`list_places` returns content ids), so PATCH/DELETE/collection-add of it is not reachable from the UI; `review_queue`
  lists pinned rows only; a pinned `started` row is deliberately visible to `lookup` but ignored by the client as a
  bookmark. Residual P3: the client now treats only `kept` as saved, so a row with relationship `imported` no longer
  shows as saved in Reader/Content Detail; confirm that is intended.

### P1-2 (deleted import): fixed
- Delete commits a content-free tombstone (`{id, form}`), `GET /api/works/{id}` is 404 for deleted works, the test reads
  the stored row (`payload::text`) and asserts neither text nor title remain, and a replay of the delete is idempotent.
- Other routes serving deleted works: `GET /api/works` and `GET /api/imports` exclude them in SQL; `get_import`,
  `get_annotations`, `get_response`, `get_conversation`, `get_draft` all 404 on `deleted`; the changes feed and receipts
  carry ids, versions and kinds, not payloads; a stale write to a deleted import gets the tombstone, not the text.
  Residual: a conversation's `work_turns` rows outlive a `deleted` conversation (unreachable through any route; relevant
  to the D-055(b) workflow). **Imports deleted before a13e0a3 still hold their text in `works.payload` on any runtime
  that ran 5bdd2ab/a4390b5** (the lane holds test data only); the human should know, and a reviewed scrub is preferable
  to hand-editing.

### P2 fixes
- **P2-1 dictation:** `INSERT ... ON CONFLICT (uq_listening_progress_scope_segment) DO NOTHING`, then `SELECT ... FOR
  UPDATE`, then merge. Constraint name matches the model and migration 0003; the row id is a function of the scope tuple,
  so the primary key cannot conflict without the arbiter also conflicting. Correct.
- **P2-2:** `timespec="microseconds"` in both PATCH and PUT; token still echoed verbatim and compared by equality. Correct.
- **P2-3 session flag:** cost fixed (one lookup per session). **New defect, P2:** `language_checked` is set whenever the
  account had no stored language, and is never cleared. A session opened before the account's first choice (device B,
  while device A then chooses Chinese) keeps the default `en` for the life of its cookie, although bootstrap already
  reports `language.stored: true`, so the client sees "stored" with active `en`. The flag therefore can hide a later-stored
  language. **Fix:** have `api_session_bootstrap` (once per page load) re-seed a session that has no language from the
  stored value, ignoring the flag, or clear the flag when bootstrap reads a stored value.
- **P2-4:** the import bound is counted in `create_guard`, which runs inside `load`, i.e. after the account stream lock,
  only for a creation; a barrier test expects exactly 20. Correct. The other unbounded creators (`started` rows,
  responses, annotations, conversations) are still uncapped and listed for the human; still a prerequisite for :8000.
- **P2-5:** the Writing room draws the stored review at once and refreshes a Chinese review in the background, replacing
  only the review on screen after a `refreshed` status and only if the same essay is still current. Acceptable; it
  replaces the whole `essay` object, so check in the browser that an in-progress revision text is not reset.
- **P2-8:** auto-create applies only when the request key equals `"legacy"` and the row is missing; it then calls
  `upsert_user`, which is idempotent, and a concurrent first sign-in retries once on `IntegrityError`. Outside
  auth-disabled development it cannot be reached today: in authentication-enabled mode the key is the Google `sub`, and the
  only requests that run under the default `"legacy"` context are the public paths, none of which call
  `write_account_settings`. **P3:** the guard is on the key alone; add `not AUTH_ENABLED` so the invariant does not depend
  on route inventory.
- **P2-9:** proposal section 17 records the corrections; applied migration files are deliberately not edited, which is
  acceptable (their docstrings stay stale; section 17 says so).

### Conditions for enabling the flag on :8021
1. Re-seed on bootstrap (or clear `language_checked`) so a stored language is never hidden from an older session.
2. Add `not AUTH_ENABLED` to the `"legacy"` auto-create guard.
3. Report every PostgreSQL-only result as local execution, and check the Writing room in a browser for the in-progress
   revision case.
4. Before :8000/:8010: per-account caps for `started` rows, responses, annotations and conversations with a receipt
   growth owner (P2-4), code and migrations deployed as one unit after a backup (P2-6), and a decision on pre-fix deleted
   import payloads.
5. The :8000/:8010 enablement stays a human gate.

## Delta review (8c84100, 39b9f12, 9a7b190)

- **Reviewer:** Claude Opus 5.5, independent reviewer subagent, not the implementer. **Date:** 2026-10-01.
- **Reviewed:** `git show` of the three commits and the code they call. Read-only and static; no Docker or PostgreSQL.
  The implementer's results (PostgreSQL 3036 passed / 9 skipped; SQLite 2703 / 342; 123/123 node gates) are local
  execution and were not reproduced by me.

### Verdict: APPROVE WITH CONDITIONS, for D4 runtime acceptance on :8021

No P0 or P1. Isolation holds on every new read and write, tombstones prevent resurrection under concurrency (with one
documented bound), the review-mode merge never drops server data or writes device defaults, and the import bound matches
ACCOUNT_RECORD_LIMITS rev 3 C1. Two P2s and five P3s below; the conditions are decisions and records, not code
blockers.

### Isolation (account and language)
- **Personal media (39b9f12).** One rule, `visible_to`: shared for everyone; a personal entry only for the account whose
  `owner_token` (SHA-256 of the account key) it carries and only in its own language; refusals are 404. It is applied at
  every learner path that resolves a media id: `stored_media_entry` (listening library, dictation/shadowing progress
  resolution, `stored_media_payload`), `find_entry` (`/api/media/my/{id}`, library payloads), and the file route, which
  maps `media/<token>/...` (original and thumbnail) to the `upload-<token>` entry before serving and sends
  `Cache-Control: private` for personal files. The learner listings (`_shared_entries`, the library browse) list
  `library == "shared"` only, so personal entries are never enumerated. Only `learner_upload` creates personal entries, and
  it now refuses a personal file without an owner. Owner-less legacy uploads are visible to the local `legacy` account
  only (fail closed). The owner token is an unsalted hash of a non-secret account key; it grants nothing (access is
  decided by the server comparing the requester's own key).
- **Media import records (9a7b190).** Stored as `works` kind `imported`, forms `url`/`upload`, so they inherit the account,
  incarnation and language scope of every import route; `mediaId` is only a reference, and opening it goes through
  `visible_to`, so referencing someone else's upload yields 404, not content.
- **Provenance, review settings, language adoption.** Provenance still resolves the saved word by (account, language);
  `adoptLearningLanguage` reloads profile, places, imports and review overlay for the new language before repaint (no
  cross-language write: each write goes through the scoped route).

### Tombstones
- The pre-check reads the current version and applies tombstones only when the writer's `expectedVersion` equals it; the
  commit is version-conditional, so a writer that loses a race gets 409 and never lands stale tombstones; a replay finds
  its receipt first. A write at the current version that brings back a remembered id is 422 `annotation_tombstoned`;
  `cleared` records all previous ids as tombstones; the client re-reads on 409/422 and re-merges server-first, excluding
  tombstones and locally removed ids, then calls `onMerged` so the device store drops removals made elsewhere. The merge
  never drops a server item (it unions server-first and removes only ids the learner removed or the server remembers).
- **Eviction of the oldest tombstone (cap 500).** The newest 500 ids are kept, so after more than 500 further removals in
  one text the oldest removed id is forgotten and a device that still holds it could write it back. This needs over 500
  removals in a single text (a text holds at most 80 highlights and 120 notes) and a long-offline device; P3-1, record it
  as the accepted bound.

### Review-mode merge
Server-side merge of stored and patched modes over validated keys; the toggle sends only the changed key; limits are sent
only when changed; a stale write is re-applied once to the fresh profile. Nothing writes defaults. Residual P3-4: an empty
map no longer resets modes to defaults (it merges to nothing), and a single mode cannot be reset to "unset"; acceptable.

### Import bound (matches ACCOUNT_RECORD_LIMITS rev 3 C1)
`create_guard` counts live and total import rows in the creating transaction: live < 20 and total < 360
(`ORENA_LIMIT_IMPORT_TOMBSTONES`, floor 52, invalid values refuse startup); creating a work already `deleted` is 422
`lifecycle_invalid`; replays never meet the guard. Matches rev 3.

### Scrub script
Dry run by default; one transaction; touches only rows with `kind = 'imported' AND lifecycle = 'deleted'` whose payload has
keys beyond `{id, form}`; rewrites the payload to exactly `{id, form}` and keeps version, sequence and timestamps;
idempotent (a clean row is skipped); prints counts only; reports derived records and receipt columns without changing
them. Safe. P3-3: the backup precondition is documentation only and `--url` puts a connection string on the command line;
add a required `--confirm-backup` flag and prefer the environment variable.

### Client-supplied media fields
`thumbnailUrl` is kept only if it starts with `https://` and contains no `@`; the server never fetches it, so there is no
SSRF; it is rendered as an image source, so there is no script injection or redirect; the only effect is a third-party
image request when the learner's own card is drawn. `url` for form `url` is `http(s)` checked and, when the Listening room
re-acquires it, goes through the existing safe-fetch (`validate_public_http_url`). `kind`, `provider`, `title` are bounded
free text rendered escaped. P3-2: for form `upload` the server stores whatever `url` the client sends, unvalidated (the
client sends an empty string); drop it or validate it, and check that `mediaId` is a stored media the account can see at
import time.

### Findings
- **P2-1. Media imports share the 20-live / 360-total import bound without a volume basis, and failure is silent.** The
  bound was derived for texts at about 52 a year. Pasted links and uploads are likely more frequent; every keep after a
  removal mints a new record, so churn consumes tombstone slots; the 21st live import (links, uploads and texts together)
  is refused and stays on the device only, with no drawn surface. In effect this is a small learner-facing limit that the
  human did not choose. **Required (decision):** either count per form with a derivation, or confirm in writing that 20
  live and 360 lifetime are the intended rails for all forms; record it in `UI_BACKEND_GAPS.md`.
- **P2-2. Deleting an upload import leaves the personal media itself.** The delete tombstones the account record, but the
  stored original, thumbnail, transcript and library entry stay in the media store (the store has a `delete` method but no
  learner route calls it). The learner's "delete" does not erase the file. **Required (before :8000):** a learner delete of a
  personal media entry (store entry, original, thumbnail) when its import is deleted, or an explicit decision that it
  stays; include the media store in the D-055(b) enumeration either way, since it is outside the database.
- **P3-1..P3-5:** tombstone bound; `upload` `url`; scrub flags; mode reset; and owner-less legacy uploads become invisible
  to their signed-in owners (confirm how many exist on :8021 and that the lane's sign-in mode is as expected).

### Named contract changes in tests (checked)
`test_d4_listening_authority.py` stamps the upload's owner (legitimate: owner-less personal media is now the local
account's only); `test_d4_account_records.py` changes "a cleared record is written again" to 422 for the cleared id plus 200
for a new id (legitimate and stronger: the tombstone contract); `test_orena_account_settings.mjs` now asserts only the
toggled mode is sent, that no default limits leave the device and that a stale write re-applies the same single change
(legitimate and stronger); `test_d4_profile_account.py` adds the partial-merge test; the learner-memory gate adds the
`upload:` reload and language-isolation cases. No assertion was weakened.

### Conditions for :8021 runtime acceptance
1. Decide and record the media-import bound (P2-1).
2. Record P2-2 and the media store in the D-055(b) enumeration and as a before-:8000 item.
3. Confirm the count of owner-less personal uploads and the lane's sign-in mode (P3-5).
4. Report PostgreSQL-only results as local execution; :8000/:8010 stay a human gate with the earlier prerequisites.

## Review (f8f5c91)

- **Reviewer:** Claude Opus 5.5, independent reviewer subagent, not the implementer. **Date:** 2026-10-01.
- **Reviewed:** `git show f8f5c91` (33 files) against D-107 points 2 and 4. Read-only and static; no Docker or
  PostgreSQL. The implementer's results (SQLite 2709, PostgreSQL 3049, 124/124 node gates) are local execution and were
  not reproduced by me.

### Verdict: APPROVE WITH CONDITIONS (acceptable on :8021; the conditions are prerequisites for anything beyond it)

No P0 or P1. The lifecycle is well built: the tombstone is content-free, recreate and revive are refused by the terminal
`deleted` state, owner and language gate every file deletion, the last-live-reference rule is correct under concurrency,
an untrusted media index refuses writes, and a link import never touches its external source. Five P2s concern
recoverability and convergence at the edges; they are small.

### What I verified
- **Tombstone and audit metadata.** Delete commits `{id, form, ref}` (nothing else) and the scrub script now writes the same
  shape. For an upload, `ref` is SHA-256 of the form and a random media id: it reveals nothing and cannot be guessed. For
  a link, `ref` is SHA-256 of the form and the link: a link is a low-entropy value, so anyone with database access can
  test whether a known URL was imported (P3-1). That is not content, but it is a fingerprint, and it is needed so a device
  can match its local `url:<link>` to the tombstone. Receipts and change records keep ids, versions, timestamps and
  `request_digest`, a SHA-256 over the original create request: that digest is derived from the text, title and link of
  the deleted import (a guess can be confirmed; long text cannot be recovered). It is already deleted by the D-055(b)
  enumeration; record that it is retained until then (P3-2). No plaintext content survives in the row, receipts or
  change records.
- **Recreate and revive.** A write to a deleted work is refused by the existing terminal lifecycle; a re-import mints a
  new record id, so a stale device cannot revive an old one, and the server never reuses an id.
- **File deletion.** `delete_owned_media` requires an entry with `library == personal`, `provider == upload`, and
  `visible_to` (owner token and language); a client-supplied `mediaId` naming another account's, another language's,
  shared or provider media changes nothing. `DELETE /api/media/my/{id}` answers 404 for all of those. The files removed are
  `media/<provider_media_id>/` (the token the server generated; `provider_media_id` is a required, non-empty field) and
  the thumbnail the entry names, validated by the asset store. The last-live-reference check runs after the tombstone
  commits and counts live upload imports of the account in any language, so two concurrent deletes cannot both keep
  the file and cannot delete it while another live import names it. A link import deletes only its record.
- **`delete_all_owned_media`.** Matches every personal upload of one account in all languages by owner token, and
  `deletion_enumeration.FILE_STORES` names the store and both removers. No workflow calls it yet, correctly (D-055).
- **Index fail-closed.** `upsert` and `delete` raise `MediaIndexUnavailable` on a corrupt or unreadable index; reads
  still answer not found. This closes the empty-map rewrite I recorded as G1.
- **Cached copies.** `openMedia` (the one resolver), Content Detail, My Library, Discover and the shell sync all consult
  the removed set (`product/import-removed.js`) and refuse with the same 404 an unknown id gets; `mergeImports` never
  re-adds a removed id; a delete made offline is recorded on the device and resent at the next sync.
- **Listening provenance.** Keeping a word or phrase from Listening now records kind `listening`, id `media:<id>`, the
  segment in `source.revision` (<= 120 characters) and the sentence; ids longer than 200 characters are dropped rather
  than cut. `POST /api/library/vocabulary` accepts `listening`, `writing`, `speaking` as `source_kind` (the column is a
  plain 40-character string with no CHECK; the named contract change in `test_becoming_library_source_kind.py` is
  legitimate). Provenance rows are read through the account and language scoped routes, so a `media:upload-<token>` id
  stored by one learner is never visible to another, and opening it still goes through `visible_to` (404 for others).
- **`kit/overflow`.** Two new files, no existing shared code changed; the 34 px control, radius 10, 32 px pill actions and
  trailing close mirror the Reader's `rdMore` and menu rows, and the gap that the design draws a "⋯" only in the Reader is
  recorded. Minimal and additive. P3-5 notes the Reader still carries its own copy of the same styles.

### Findings
- **P2-1. A failed file removal cannot be retried.** `delete_import` commits the tombstone first and then removes files from
  the id read *before* the commit. If removal fails or `MediaIndexUnavailable` is raised, the route returns
  `mediaDeleted: false` and the import is gone, but on any retry or replay the stored payload is the tombstone, which no
  longer holds `mediaId`, so the files are unreachable. Worse, `_remove_personal_entry` removes the index entry first: if
  the file removal then fails, the entry is gone and the bytes are orphaned with no index record, and
  `DELETE /api/media/my/{id}` now answers 404. The learner believes the upload was deleted (D-107.2). **Required:** make
  removal retryable: keep the media id in the tombstone until removal is confirmed (or write a pending-removal marker) and
  re-run it on replay and from a sweeper; or order the work files first, index second, after a cheap check that the index
  is writable. Log and surface `mediaDeleted: false` to the client for a retry.
- **P2-2. The deleted list covers only the 50 newest tombstones.** `GET /api/imports` returns `deleted` through
  `list_works(..., limit=LIST_LIMIT)` (the 50 cap). A device that has been away while more than 50 later deletions were made
  never learns of the older ones and keeps and opens a cached copy, which D-107.2 forbids. The pool bounds are 360 and
  2,500 total. **Required:** return all tombstones (ids and refs are about 150 bytes each, at most the total bound), or a
  cursor with a `since`; and a stale device with a gap should reconcile by comparing its whole local set to the list.
- **P2-3. A stale device can delete another device's legitimate re-import.** The offline-resend rule in `syncImports` is
  "for every live account item whose id this device has marked removed, send the delete". If device A deleted
  `url:<link>` and device B later re-imported the same link (a new record), A's next sync sees the live record with the
  same membership id, treats it as its own pending deletion and deletes the new record; `mergeImports` also hides the
  re-import on A for ever. **Required:** resend only the record uuids this device knew when it deleted (track pending
  deletes by record uuid with their versions), and let a new live record with a version greater than the deletion clear the
  device's removed marker for that id.
- **P2-4. Device-only uploads are never deleted from the server.** `removeImport` returns false when the device holds no
  account record for the membership, and then nothing calls `DELETE /api/media/my/{id}`; the file, thumbnail and index entry
  of an upload that never synced (backbone disabled, or the push failed) stay for ever after the learner "deletes" it.
  **Required:** for an `upload:` membership, always call the owner-scoped media delete (idempotent, 404 for others) in
  addition to the record delete.
- **P2-5. Derived content of a deleted import is left, and part of it is a copy of the import.** The commit records
  that notes and highlights on a deleted text stay in the device store and the account's annotations row, and that
  dictation and shadowing history for an upload is not erased. D-107.2 requires removal of the import from the library, a
  tombstone, no resurrection, deletion of owned media, and "only integrity/audit metadata" kept *of the import*; it does
  not name derived learner records, and recording the gap is therefore correct, not a defect. But some of what is left is
  a verbatim copy of the deleted import: a highlight's `sentence` (<= 400 characters of the text), the `focus` sentence of a
  word provenance, a dictation `last_answer` typed from the upload's transcript, and the annotations row is still readable
  through `GET /api/annotations/<content id>`. After P1-2 of the first review ("deleted means erased") this is
  inconsistent. **Required (human decision, recorded):** either erase highlight excerpts, provenance focus sentences and
  progress answers that were taken from the deleted import (keeping learner-written notes), or state in D-107 that derived
  learner records outlive the import. The `GET` route should at least 404 for annotations of a deleted import.

### P3 findings
- **P3-1.** A link's `ref` is a guessable fingerprint (above); acceptable, document it. Using a per-incarnation salt returned
  in the list would stop precomputed tables but not a targeted guess.
- **P3-2.** Receipts keep a content-derived digest until account deletion; record this retention.
- **P3-3.** Tombstones made before `f8f5c91` (and already scrubbed) carry no `ref`; a device cannot match them, so a link or
  file deleted earlier stays on devices that held it. Lane only (two such imports); note it.
- **P3-4.** `import-removed.js` keeps one module-level set replaced whenever any `learnerMemory` is constructed (for example
  for another language); the active room's set can be overwritten. Key the set by owner and language.
- **P3-5.** The Reader still has its own copy of the overflow styles; migrate it to `kit/overflow` so the pattern has one owner.
- **P3-6.** The upload route stores the original and thumbnail before the index write; with `MediaIndexUnavailable` the
  request fails with 500 and the files are orphaned. Delete them on failure and answer 503.
- **P3-7.** The delete acts on tap with no confirmation and no undo, and an uploaded file's deletion is irreversible. The
  design draws neither; it is correctly recorded for the human (a drawn confirmation or an Undo window).
- **P3-8.** The library "kept" mark on the server (`library_items`, relationship `kept`) for a deleted import is not removed
  with it; it holds no content, but the item can show as saved.

### Conditions
1. P2-1 (retryable file removal) and P2-4 (device-only uploads) before the delete flow is relied on beyond :8021.
2. P2-2 and P2-3 (tombstone list completeness; pending-delete by record uuid) before multi-device use beyond the lane.
3. P2-5: a recorded human decision on derived records of a deleted import.
4. P3-3, P3-6 and the others as follow-ups. Enabling beyond :8021 remains the D-107.5 gate.
