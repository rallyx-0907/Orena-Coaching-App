# Review: `LEARNER_RECORDS_D4.md` (the learner records D3 found missing on the server)

- **Role:** Delegated Architecture Reviewer, independent of the implementer (`AGENTS.md` §1
  "Architecture review authority"). I did not write the proposal and did not assume it is right.
- **Reviewed commit:** `9b239304a208d4bcc49ba1c232c93046f3c284d2` (`codex/work`). The proposal says
  it was verified at `1bd21e7`; the intervening commits are unrelated (Gemini catalogue, D-103 entry).
- **Reviewed file:** `docs/project/proposals/LEARNER_RECORDS_D4.md` (untracked, revision 1, 833 lines).
- **Scope and limits:** the proposal only. All evidence comes from reading code and documents at the
  reviewed commit. Nothing was run, no test was executed, no database was touched, so no PASS is claimed.
  Policy: `docs/project/REVIEW_POLICY.md`.

## Verdict: **REQUEST CHANGES**

There is no P0. Five P1s remain. The overall design direction is sound and mostly reuses existing
records as ADA §3 requires: the backbone tables, `user_language_profiles`, `listening_progress`,
`grammar_progress`, one new table only where immutability is required. Four P1s are corrections to
the proposal text or missing specification; one (P1-2, receipt growth for reading positions) needs
a design change or an explicit human acceptance with numbers. H2/I1 is carried faithfully. The D-103
items are matched to the human's words, with the defects listed below.

## Factual claims checked

| Claim (section) | Result | Evidence |
| --- | --- | --- |
| Eight backbone tables exist from `20260908_0005`; `works.kind` has no CHECK; kinds and domains are code registries (§0) | Correct | `migrations/versions/20260908_0005_account_work_backbone.py` (works: no kind CHECK); `writing_coach/work_contract.py:21,25` |
| `GET /api/account-backbone` reports `disabled` unless `ORENA_ACCOUNT_BACKBONE` is on; compose does not pass it (§0) | Correct | `writing_coach/account_backbone.py:31-56`; grep finds no occurrence in `compose.yaml` or `scripts/` |
| Draft path: deterministic work id, `operationId`/`expectedVersion`, 409 with server payload, `MAX_PAYLOAD_CHARS = 200_000` (§2.2) | Correct | `writing_coach/work_api.py:56,159-205,218-260` |
| `ix_works_scope_sequence (incarnation_id, language_code, updated_sequence, id)` (§2.3) | Correct | migration 0005 |
| No repository code or route appends `work_turns` (I6) | Correct | grep: only the table list and a raw INSERT in `tests/test_orena_work_persistence_postgres.py:346`; `append_decision` exists only as a pure function, `work_contract.py:~90` |
| No HTTP route for provenance; `attach_occurrence` exists (I12) | Correct | `provenance_repository.py:125` |
| `users` is the account row; `account_incarnations.user_id -> users ON DELETE RESTRICT`; `user_language_profiles.user_id` cascades (§2.6) | Schema correct, **conclusion wrong** | see P1-1 |
| `users` has no version/updated_at column | Correct (missing from the proposal) | `models.py:32-42` has `created_at`, `last_login` only; see P1-4 |
| `POST /api/platform/language` writes only the session (I2) | Correct | `core/platform_api.py:37-43`; middleware reads `request.session.get("language")` at `auth_support.py:410-411` |
| `interface_language` is `stored=False` (I3) | Correct | `account_profile.py:80-83` |
| `update_essay_module_data` replaces the whole dict (I19) | Correct | `specialized_repository.py:884-886` (SQLite), `:1478-1483` (PG) |
| Review identity carries `learning_language`, `support_language`, `contract`, `fingerprint` in `module_data.review`; missing identity returns `{}` (I19) | Correct | `writing_review_identity.py:62-100`; `app.py:2555` |
| PG listening save replaces every field with the client's value (I18) | Correct | `specialized_repository.py:1297-1316` |
| SQLite repository refuses listening progress and speaking attempts (I18, §9) | Correct | `specialized_repository.py:855-856, 873-874` |
| H2 wrote `lock_timeout` unguarded; D4 adds the dialect guard (§5) | Correct, and it satisfies review item N2 | `DECLARED_LEVEL_STORAGE.md:96-99` |
| Head is `20260924_0016` | Correct | `migrations/versions/` listing |

## Findings

### P1-1: The deletion and incarnation obligations are misstated for columns on `users` and `user_language_profiles`

**Evidence.** Proposal §2.6 and I2/I3/I3b say columns on `users` and `user_language_profiles` are
"removed with the row" / "removed with the account". But `account_incarnations.user_id -> users ON
DELETE RESTRICT` (migration 0005) and the deletion journal both anchor on the `users` row
(`persistence/deletion_journal.py:~192`, "the account row is the lock every epoch allocation takes").
The barrier requires the `users` row to survive deletion, for the life of the deployment (ADA §1
`:41-44`). So a re-registered account (new incarnation, same `users.id`) would read the deleted
account's `learning_language`, `interface_language`, `weekly_goal_days`, `declared_level`, review
settings, and every `user_language_profiles` row, unless the D-055(b) owner-table workflow clears
them. That is the exact leak D-055 names for owner tables keyed by account. The proposal does this
correctly for `works` (incarnation-keyed) and wrongly for the columns it adds.

**Required change.** Restate §2.6: `users` new columns and `user_language_profiles` rows are
account-keyed owner data that the deletion workflow must **reset or delete explicitly**, not rows that
disappear. The approval entry records them in the D-055(b) enumeration. The deletion-enumeration test
in §9 must assert this for `users.*`, `user_language_profiles.*`, `grammar_progress`,
`listening_progress`, `essays`, and the new `essay_review_history`.

### P1-2: I4 makes the highest-frequency learner write ride the receipt and change stream, with only an unenforceable client throttle

**Evidence.** Every `commit_mutation` writes a `mutation_receipts` row (unique operation, digest,
result ref, 10+ columns) and a `change_records` row, and takes the per-incarnation stream lock
(`persistence/work_repository.py:87-`; migration 0005). Proposal §2.4 admits compaction is
unspecified and makes client-side throttling "a condition of approval". The server cannot enforce
what a client does, and the frozen native client and the old UI are not bound by it. At the stated
target (~100k accounts), 20-30 position writes per active learner per day is 2-3 M receipt rows and
2-3 M change rows per day, about 1 B of each per year, with the pull stream (`changes_after`) reading
them. ADA §5 `:199-203` and AGENTS §7 reserve receipt compaction and say a missing policy "blocks sync
activation if replay safety cannot be maintained". The proposal therefore makes a growth decision inside
a reserved area.

**Required change.** One of, recorded in the approval entry:
1. Server-enforced write coalescing for `continuation`: refuse (429) or no-op a write when the work's
   `updated_at` is under a stated interval and the place has not crossed a segment or chapter boundary,
   plus a written per-learner-per-day row estimate; or
2. Take H-12's alternative seriously (position on `library_items`, which has no receipt) or a third
   option the human prefers, with ADA §2's "Continue is a work-derived index, not evidence" reconciled; or
3. The human explicitly accepts unbounded receipt growth for I4 until the sync/compaction package.
Until one is chosen, I4 is not approved. I5, I6, I8-I10, I12 write far less often and are not blocked by this.

### P1-3: The I19 refresh contract is unsafe as written

**Evidence and required change.**
1. **Wrong support language.** `evaluate()` resolves the support language from the *current* profile
   (`app.py:917-928, 930-932`). The proposal verifies the pair from the *stored* identity but never says the
   re-grade runs under it. A learner who changed support language since would get a review explained in the
   new language, stored under an identity that claims the old pair. `writing_review_identity.py:24-27` warns
   about this exact failure. The refresh must pass the stored support language and target level into the
   evaluator explicitly (an `evaluate` refactor), and a test must cover a changed profile.
2. **Fallback overwrite.** `evaluate()` returns `heuristic_fallback(...)` labelled `fallback-demo` when
   `ALLOW_FALLBACK` is true (`app.py:1052-1072`, default false but configurable). "Provider failure writes
   nothing" does not cover it. A refresh must treat any non-provider result as `unavailable` and write nothing.
3. **No transactional write path exists.** The repositories have `create_essay` and a whole-dict
   `update_essay_module_data`; there is no method that updates an existing essay's review columns. The
   proposal's "one transaction inserts the snapshot and overwrites the essay" needs a new repository method on
   both backends that locks the essay row (`SELECT ... FOR UPDATE`), re-checks the fingerprint, inserts the
   history row and updates the columns and `module_data.review` by key. Otherwise a concurrent
   `becoming_linguistics` read-modify-write (`becoming_linguistics.py:152`) can erase the refresh or vice versa.
   The SQLite backend needs the history table too (see P2-3).
4. **"One provider call under concurrency."** `_review_gate` is a process-local `threading.Lock`
   (`app.py:2409-2415`). It holds for the single uvicorn worker in `Dockerfile:34` and not across processes.
   The `UNIQUE (essay_id, prior_fingerprint)` makes the *write* idempotent but a second process would still pay
   for a second call. State this limit; do not claim one call in the rehearsal beyond the single-process case.

### P1-4: Account-wide settings on `users` have no conflict token, and the proposal says they do

**Evidence.** I3/I3b: "same expected-version rule". `users` has no `updated_at` or version column
(`models.py:32-42`), and 0018 adds none. I2 says "last write wins". ADA §1 `:62-63` requires patches with an
expected version; ADA §4 forbids last-write-wins by client timestamp. The H2 review (`P2-4`, question table)
said an integer version column belongs to the canonical account architecture and is not authorised. So either
the settings are last-write-by-arrival (defensible for single scalars, as the proposal argues for I2) or they
need a token that the proposal does not create.

**Required change.** State one rule for all three account-wide columns and say honestly which it is. Recommended:
arrival-order last-write for scalar account settings (server ordering, never the client clock), stated as an
explicit, recorded exception to ADA §1 for scalars, and remove "same expected-version rule" from I3/I3b. If the
human wants a token, that is a column (`settings_updated_at`) and belongs in 0018 with the human's approval.

### P1-5: The proposal does not ask for the amendment that its own premise requires (AGENTS §7)

**Evidence.** `AGENTS.md` §7 (current text) still says "Kept-language provenance, conversations, drafts and
continuation are device memory *by design*" and forbids new learner-data persistence decisions until GPT-6's
architecture. D-101 "Persistence" and D-103 are explicit current human instructions to store learning records,
and ADA §2 already names the target authority for continuation, conversation, draft and provenance. So the
direction is authorised, but the proposal does not say that AGENTS §7 and `AGENT_CONTRACT.md:383` (I15) now
disagree with what it builds, nor list which reserved matters it still leaves open. Silent decisions found:
- registering three new work kinds (`continuation`, `annotation`, `imported`) also opens them on the generic
  `PUT /api/works/{id}`, which takes any client-chosen UUID and payload (`work_api.py:151-205`). The deterministic
  id per key is a convention of the new routes only; the generic route can create duplicates for a key.
- `users` as the home of account-wide learner preferences (ADA §1 keeps `users` as the identity mapping);
- server-defined role/`reply_to` rules for turns.

**Required change.** The approval entry must (a) amend AGENTS §7 to say which of drafts, conversations,
continuation and provenance are now server-owned and which holds remain (sync cursors, tombstone horizon,
receipt compaction, native), and (b) either restrict the generic `PUT /api/works/{id}` to the pre-existing kinds
or state that arbitrary client ids for the new kinds are accepted. The human approves the `users` placement
(alternative: a per-account settings row, which is a new table and needs the human under D-101 "no ad-hoc tables").

### P2 findings (non-blocking, fold in while editing)

- **P2-1 N1 not carried.** I1 says N1-N3 "travel with" the proposal by pointer. N1 (an explicit
  `expected_updated_at` parameter on `upsert_profile_record`, `IntegrityError` mapped to 409, a plain insert on
  the SQLite creation path, and a create-while-created test) is a design requirement, and I3/I13 also PATCH the
  profile row. Copy N1 into I1 and the test plan; N2 is satisfied (the dialect guard) and N3 is cosmetic.
- **P2-2 Dictation internal inconsistency.** I18 step 3 says `best = max(stored, computed)`; the `client` row
  rule says the first verified check *supersedes* the stored best. For a `client` row with an inflated best,
  `max` keeps the forgery. Specify: on a `client` row, best = computed; afterwards `max`. `checked_attempt_count`
  still trusts the client up to +1 per write; say so as a residual. The 404 `asset_not_found` for an unresolvable
  asset can break saves that the old UI makes today for assets outside the catalogue and outside the learner's
  media; list this old-UI behaviour change and confirm against `url:`/`upload:` ids in the rehearsal.
- **P2-3 SQLite schema for the new table.** §5 only mentions a guarded `ALTER TABLE`. `essay_review_history`
  needs a `CREATE TABLE IF NOT EXISTS` in `SQLiteSpecializedLearningRepository.initialize()` (its `essays` table
  uses integer ids and `module_data_json`), so the hermetic tests in §9 can run the I19 repository cases.
- **P2-4 Immutability trigger.** The migration chain already has a PostgreSQL trigger precedent (0016 makes the
  legacy reading archive read-only by trigger). A `BEFORE UPDATE` trigger on `essay_review_history` is cheap and
  is the structural guarantee D-103 asks for ("immutable history and audit evidence"). Recommend adding it
  (UPDATE only; a DELETE trigger would block the `ON DELETE CASCADE` on essay/account deletion). Note that a
  learner deleting an essay also deletes its history; state that as intended.
- **P2-5 Pair predicate.** D-103 says `support != zh`. Stored `support_language` is normalised but may be a
  variant tag. Compare the primary subtag after the registry's normalisation, use the same predicate as the
  evaluator fix (`writing_evaluation.py:28`, keyed on `support_cjk`), and say what happens for a CJK support
  language other than `zh` (the human's literal rule includes it).
- **P2-6 Contract-version tolerance needs code.** "A stored v2.6 or v2.7 both count as current for an
  unaffected pair" is marked [I]. `same_review` compares fingerprints that embed the contract version
  (`writing_review_identity.py:96-100`), so accepting both requires a changed comparator or recomputing the
  fingerprint under the stored contract. Specify which, and test that reviews written since today's v2.7 bump
  are not re-earned for unaffected pairs.
- **P2-7 Terminal `deleted`.** `lifecycle_change` makes `deleted` terminal (`work_contract.py:~75`), and ids are
  not reused. Deterministic-id kinds (continuation, annotation) therefore must model "clear" or "reset" in the
  payload, never as `deleted`, or the key is dead for that learner.
- **P2-8 Payload size on a hot row.** `works.payload` is rewritten whole per commit (`work_repository.py`,
  UPDATE). Annotation payloads near 200 KB updated per highlight are write-amplifying. The proposal's lower server
  bound (120 highlights, 200 notes) is right; state the byte estimate.
- **P2-9 Learning language seeding (I2).** The middleware sits on every request
  (`auth_support.py:409-455`). State that the stored value is read only when the session has none and is then
  written into the session, so no per-request database read is added. Also state the non-auth (`legacy` identity)
  behaviour.
- **P2-10 Migration mechanics.** `SET LOCAL lock_timeout` in `env.py`'s single transaction applies to every later
  revision in the same run; harmless for 0017-0021 but add the one-line comment N2 asked for. The `users`
  migration (0018) should be its own operator step after a fresh backup, as the proposal says. The "PG cases skip
  in CI" is correctly disclosed; the rehearsal record is therefore the only PG evidence and must be attached to the
  approval.
- **P2-11 Streak (I14).** Fine as derived. Say that `essays.created_at` is per submission, so revisions of one
  piece each count as an active day, which matches "acknowledged learning event".
- **P2-12 Export.** Correctly flagged as not decided (ADA defines none).

## Judgement on the specific questions

- **§7 holds versus proposal scope.** No sync cursor, tombstone horizon, snapshot token or compaction is designed
  (good), except that I4 leans on compaction being deferred (P1-2). The wider point is P1-5.
- **Migration safety.** Additive, linear chain 0017-0021 (0022 conditional), constant `server_default`, dialect-guarded
  `lock_timeout`, downgrade documented as rehearsal-only, none in `GATED_REVISIONS`, `importer.py` untouched, head
  tests named. Sound. The one new table is justified against the rejected `module_data` list (correct: the dict is
  replaced whole by other writers). Missing items are P1-3(3), P2-3, P2-4.
- **API compatibility.** Old UI: additive, except the I16/I18 language and asset checks (P2-2). New UI: intended
  consumers. Frozen native client: the profile PUT response must not gain fields (carried from H2 P2-5); the
  listening POST keeps its body and ignores `best_*`; `/api/session/bootstrap` gains an additive field. Sound.
- **Conflict semantics.** No client-clock last-write-wins: drafts conflict-and-retain; annotations union by id;
  positions by server version. Account scalars are the gap (P1-4).
- **Deletion, export, incarnation (D-054/D-055).** Work rows correct (incarnation-keyed, cascade); account-keyed
  columns wrong (P1-1).
- **D-103 items.** (2) Dictation: server recomputes from the canonical line, no AI, browser score remains instant
  feedback, assess/store remain `MISSING` until it lands. Matches, with P2-2. (4) Real metric or none: matches;
  minutes, achievements, trends, skill %, level/XP hidden, unmeasured never 0. (3) Books/pasted texts have no
  comprehension record: matches. (1) Retirements touch UI and routes, no data deleted: matches. (6) Prompt Bank is
  content, only `promptRef` is learner-side: matches. (7) Evaluator: affected identity, idempotent POST, stored
  review returned first, one re-grade, previous review kept immutable, no learner revision, no batch, stale-only:
  matches in intent, with P1-3 and P2-4..P2-6.
- **Tests.** Real repositories and real SQL, fakes only for providers, PG up/down/up rehearsal, two accounts x
  en/zh, concurrency cases. Good. Add: changed-support-language refresh, `fallback-demo` refresh, N1 create race,
  users-column reset in the deletion enumeration.
- **Rollback.** Sound and consistent with ADA §6 (no downgrade with learner data; flag off degrades to device).
- **Activating `ORENA_ACCOUNT_BACKBONE`.** Correctly left as a human gate (H-11), separate from schema; compose
  default stays off; production only after backup and smoke. I agree with the recommendation with one condition:
  D-055's two preconditions concern deletion, and turning the flag on neither deletes nor re-registers, so they do
  not block activation; P1-1 must still be fixed before any account-keyed column ships.

## Recommendations on the open decisions

| # | Recommendation |
| --- | --- |
| H-1 | Yes (Welcome once per language; no inferred backfill). Human confirms, as in the H2 review. |
| H-2 | Server-stored, on the same rule as P1-4. |
| H-3 | Option 4, non-evidence `response` work. Agree. |
| H-4 | (a) completion only; a client-reported quiz number is weak evidence and D-098.7 prefers measured numbers. |
| H-5 | (a) derived from the three immutable sources; document that dictation, shadowing and review-only days do not extend the streak. Do not add 0023 now. |
| H-6 | Default none. If offered, one explicit import with preview per ADA §6.6, never at startup; separate slice. |
| H-7 | Design/product question. If kept, store in the draft payload and have the evaluator read them; otherwise retire (rule 43). Not an architecture matter. |
| H-8 | Regenerate on demand; do not put derived coaching in immutable turns. |
| H-9 | Product call; storage is unaffected. |
| H-10 | Keep device until the Intelligence lane's contract moves; do not reopen here. |
| H-11 | Yes, lane runtime now; :8000 after merge under D-102.7, with the P1-1 condition above. |
| H-12 | Not decidable until P1-2 is resolved; if the human accepts the receipt growth, `works` `continuation`; otherwise a `place` column on `library_items`. |
| H-13 | Confirm the two D3 corrections; no decision. |
| H-14 | Superseded by the next verified check, and fix the formula (P2-2). |
| H-15 | Not refreshed (pair unverifiable). Agree. |
| H-16 | Design question; no storage impact. |

## To reach APPROVE

1. P1-1: correct §2.6, I2/I3/I3b, and the deletion-enumeration test for account-keyed columns.
2. P1-2: choose a server-enforced mitigation or an alternative store, or record explicit human acceptance, for I4.
3. P1-3: specify the stored-pair, no-fallback, transactional repository method and process-local gate limit.
4. P1-4: state the conflict rule for account scalars honestly.
5. P1-5: request the AGENTS §7 amendment and settle the generic `PUT /api/works/{id}` and `users` placement.

The P2s should be folded in but do not block. This review is not product approval and not authorization to add or
apply any migration, and it does not activate `ORENA_ACCOUNT_BACKBONE`; the human still decides each of those.

## Re-check of revision 2

- **Reviewer:** the same Delegated Architecture Reviewer, independent of the implementer.
- **Reviewed HEAD:** `c2e4e6348535cbf493058e24032da5ef4bd42722` (`codex/work`). The first review was at `9b23930`;
  the only commits between are `e9bdf31` (benchmark doc) and `c2e4e63` (per-pair evaluator contract).
- **File:** `docs/project/proposals/LEARNER_RECORDS_D4.md`, revision 2 (1006 lines, untracked), sections 2.4, 2.6,
  I2-I4, I10, I18, I19, 5, 9, 10, 12, 13.
- **Scope:** whether each P1 and P2 is resolved in the text and consistent with the code. Not a second design review.
  Nothing was run and no test PASS is claimed. Items presented as human decisions (H-11, H-12, H-17, H-18) count as
  resolved when options and consequences are stated honestly.

### Per finding

| Finding | Status | Evidence |
| --- | --- | --- |
| P1-1 deletion and incarnation | **RESOLVED** | Section 2.6 now separates incarnation-keyed rows (the kept incarnation row's cascade does not fire, so the D-055(b) workflow deletes them explicitly, a sharper point than my finding) from account-keyed owner tables and from the new `users` columns, which are reset to `''`/`''`/`NULL`. I2/I3/I3b say "reset on the surviving row". The section 9 enumeration test lists them. Consistent with migration 0005 (RESTRICT) and `deletion_journal.py`. |
| P1-2 I4 receipt growth | **RESOLVED** (as a human decision, H-12) | I4 gives Design A (route-enforced coalescing: no-op with no receipt or stream lock under 60 s unless a boundary, 200/day cap, estimate 0.5 M rows/day per table, 4 M ceiling, honestly "not bounded by data volume") and Design B (`library_items.place`, migration 0022, no receipt, no stream). I checked B against `models.py:565-660`: `kind` allows reading/listening/book, `relationship` allows `started`, `source_id` is 255, and `version`/`updated_at` are separate, so a place write that skips them cannot conflict a pin or note PATCH. The proposal states B departs from ADA section 2 wording and that I4 is not approved until H-12. Recommending B is reasonable. |
| P1-3 I19 refresh contract | **RESOLVED** | I19: stored pair only, no fallback to the current profile, and no refresh when the stored identity lacks a resolvable support language; `evaluate` refactored to take explicit support language and target; fallback disabled by parameter and any non-provider result is `unavailable` with no write; one transactional `refresh_essay_review` on both backends with row lock (PG `FOR UPDATE`, SQLite `BEGIN IMMEDIATE`) and fingerprint re-check; key-level merge of `module_data.review`; the `becoming_linguistics.py:152` writer moves to a locked merge; the process-local `_review_gate` limit is stated (`app.py:2409-2415`, `Dockerfile:34`) and "one provider call" is claimed only for a single process. Consistent with the code read in the first review. |
| P1-4 account scalars | **RESOLVED** | Section 2.4 states arrival-order last write ordered by the database transaction, never a client clock, with its consequence, as a recorded exception to ADA section 1 `:62-63`, plus the cost of the alternative (`users.settings_updated_at` in 0018). "Same expected-version rule" is gone from I3/I3b. H-17. |
| P1-5 AGENTS section 7 / generic PUT / `users` | **RESOLVED** | Section 13 gives the proposed amendment text (server-owned records, and the holds that remain: sync, tombstone horizon, compaction, D-055 runtime, export, native, Orena history) and the `users` placement with its alternative (H-18). The generic `PUT /api/works/{id}` refuses the new kinds with 422 `work_kind_invalid`; consistent with `work_api.py:159`. Dedicated-route rules (turn role and `reply_to`) are listed for approval. |
| P2-1 N1 | RESOLVED | Copied into I1 and the test plan (stale token 409; create-while-created 409 on both backends). |
| P2-2 Dictation | RESOLVED | I18 step 3: a `client` or absent row's best is set to the computed value, then `max`; the +1 count residual is stated; the old-UI 404/422 change and the rehearsal check are stated. |
| P2-3 SQLite table | RESOLVED | `CREATE TABLE IF NOT EXISTS essay_review_history` in `initialize()`, integer `essay_id`. |
| P2-4 trigger | RESOLVED | UPDATE-only `BEFORE UPDATE` in 0021; delete cascade intentionally allowed; a learner-deleted essay deletes its history, stated. |
| P2-5 pair predicate | RESOLVED, consistent with code | `writing_review_identity.py:66-68` (`v27_affects`: primary subtag of learning is `zh` and of support is not `zh`), including CJK non-zh support, as D-103 says. |
| P2-6 `same_review` | RESOLVED | `review_identity()` now defaults the contract per pair (`contract_version_for`, lines 71-75 and 92-125), so no comparator change is needed; the v2.7-for-all window is disclosed and tested. |
| P2-7 terminal `deleted` | RESOLVED | "Clear" is `{cleared:true}` in the payload for I4 Design A and I10. |
| P2-8 payload size | RESOLVED | I10: 80x400 + 120x600, about 104 KB, under the 200,000 bound. |
| P2-9 seeding | RESOLVED | Read only when the session has none, then written to the session; `legacy` mode stated. The exact seeding site is still marked [I] for implementation. |
| P2-10 migration mechanics | RESOLVED | Section 5: comment per file, 0018 as its own step after backup, rehearsal record attached; conditional numbering renumbered to 0022 (place), 0023 (quiz), 0024 (not proposed). |
| P2-11 streak | RESOLVED | Recorded in section 12. |
| P2-12 export | RESOLVED | Unchanged and undecided, stated. |

### New issues (all P2, non-blocking; carry into implementation)

- **N-1 Design A cap counting.** The 200/day per-account cap needs a counter, and nothing in the schema gives one
  cheaply (`change_records` has no `created_at` index; `works.updated_at` holds only the last write). If A is chosen,
  specify the counter (for example `{day, count}` in the work payload) before I4 is implemented.
- **N-2 Protected areas.** Design B touches `library_items` (Library) and I19 changes the `becoming_linguistics`
  `module_data` writer. Both are cross-domain; the implementation report must state why, keep the change minimal and
  attach regression evidence (`REVIEW_POLICY.md`, "Unexpected cross-domain changes").
- **N-3 Design B index.** The partial index on `library_items` is created on a live table in 0022; record its lock
  behaviour in the rehearsal, or defer the index until measured. The nullable columns need no rewrite.
- **N-4 Conditional migration numbering.** State that revisions are promoted one at a time in order and that a skipped
  conditional number leaves no gap: each `down_revision` is the previous promoted revision, and the operator `--from`
  value follows the subset actually promoted.

### Final verdict: **APPROVE** (architecture proposal only)

Every P1 and P2 from the first review is resolved in the text and consistent with the code at `c2e4e63`. The four
new items are P2. Under `REVIEW_POLICY.md`, with no unresolved P0 or P1, the verdict is APPROVE. Conditions that
remain outside this review, all the human's:
- H-12 must be chosen before I4 is implemented (and N-1 answered if Design A);
- H-17, H-18 (the AGENTS section 7 amendment and the `users` placement), H-1 to H-6, H-14 and H-15 are decisions in
  section 13;
- the migrations stay in `migrations/proposed/` until a recorded throwaway PostgreSQL 17 up/down/up rehearsal and
  human authorization;
- activating `ORENA_ACCOUNT_BACKBONE` (H-11) is not authorised by this review; it remains a human gate. The
  proposal's statement that D-055's deletion preconditions are open, and that turning the flag on neither deletes nor
  re-registers, is accepted.

This review is not product approval and does not authorise applying any migration.

## Delta review of revision 3 and the migration code

- **Reviewer:** the same Delegated Architecture Reviewer, independent of the implementer.
- **Reviewed HEAD:** `0706e36585637abbb4ffd57c58e9d667e7f4fce9` (`codex/work`), which contains D-104 (`aafe968`),
  proposal revision 3, `migrations/proposed/20260930_0017..0023_*.py`, `scripts/rehearse_learner_records_schema.py` and
  `LEARNER_RECORDS_D4.REHEARSAL.md`.
- **Scope:** the delta only. Read: D-104, AGENTS section 7 as amended, proposal sections 2.4, I1, I2, I4, I11, 5, 10, 13-15,
  the seven revision files, the rehearsal script and its recorded output. Nothing was run; the 48 PASS is the
  implementer's recorded local run on a throwaway PostgreSQL 17, and I do not restate it as my own result.

### Verdict: **APPROVE** (revision 3 and the seven proposed revisions, for promotion review)

There is no P0 and no P1. Revision 3 matches D-104, and the migrations are additive, correctly chained and symmetric.
Six P2 items are conditions to close before the first `git mv` into `versions/`. Human authorization, the backbone
gate and the `git mv` remain the human's; this is not authorization to apply anything.

### 1. Revision 3 against D-104 and AGENTS section 7

| D-104 point | Revision 3 | Result |
| --- | --- | --- |
| H-18 storage ownership (`users` four columns; profile row for per-language; no settings table) | Sections 13-14, I2/I3/I3b, 0018/0019 | Matches |
| H-12 Design B, 0022 required | I4 is Design B only; `works` continuation removed; generic PUT refuses `annotation`/`imported` | Matches |
| H-17 server-owned expected-version on `users.settings_updated_at`; no blind LWW; never a client timestamp | Section 2.4 (L127-136), 0018 | Matches; the arrival-order exception is withdrawn |
| H-11 flag on the lane only after rehearsal and apply; default off; :8000 after merge, backup, gate, smoke | Section 14 | Matches |
| H-6 no bulk migration, no import flow | Section 14 | Matches |
| H-1 Welcome once per language whose profile row does not exist | I1 (L187-190) | Matches literally; see H-19 below |
| H-5 real derived streak, no table, every staging skill with valid records, page visits never count | Section 14 | Matches |
| H-4 quiz stored; 0023 required; Try-it stays in Writing | I11, 0023 | Matches; see H-20 below |
| H-14, H-15, H-3 | Section 14 | Match |

AGENTS section 7 as amended lists drafts, conversations, continuation/place, notes/highlights/annotations, learner-imported
private content and provenance as server records, and keeps sync protocol, receipt compaction, the deletion runtime,
export and Orena history reserved. The proposal adds nothing to the reserved list: no cursor, tombstone horizon or
compaction; account settings and evidence records (Dictation, refresh history, quiz) are covered by D-104's own
ownership statement rather than section 7's list, which is acceptable because D-104 is the explicit instruction.
One drafting drift (P2-6): proposal section 5 still shows `op.get_bind().dialect.name` while the files correctly use
`op.get_context().dialect.name`.

### 2. The migration code

Verified against the files and the code they touch:

- **Chain.** `20260930_0017.down_revision = 20260924_0016`, then 0018...0023 each revise the previous one; `20260924_0016`
  is the current head (`migrations/versions/20260924_0016_adaptive_reading.py:89`). Alembic does not read `proposed/`, so
  no startup check is affected; `GATED_REVISIONS` is not touched (all additive).
- **Additive only.** Only `ADD COLUMN`, one `CREATE TABLE`, indexes, a trigger, and one CHECK. No type change, no
  backfill, no drop. Existing rows: `NOT NULL DEFAULT ''` / `'client'` are constant defaults (metadata-only on PG 11+;
  runtime is PG 17); every other new column is nullable with no default. Column types fit their values:
  `essay_review_history.prior_fingerprint`/`replaced_by_fingerprint` String(64) equals a SHA-256 hex digest
  (`writing_review_identity.py:_digest`), `prior_contract` String(40) fits `writing-evaluation-v2.6`.
- **Dialect guards and lock_timeout.** Every file sets `SET LOCAL lock_timeout = '5s'` behind
  `op.get_context().dialect.name == "postgresql"` in both directions (the offline-safe form, as in
  `20260924_0015`). 0021's trigger and function, and 0023's CHECK, are PostgreSQL-only and guarded in both
  directions. This matches the precedent (0015 creates its snapshot trigger the same way).
- **Downgrade symmetry.** Each `downgrade()` drops exactly what `upgrade()` added, in reverse order, indexes and
  constraints before columns (0022 drops the index before the columns it covers, which matters on SQLite), and each
  docstring says it drops learner data and is for rehearsal only.
- **SQLite test backend.** The Alembic chain is not run on SQLite by the suite (`migrations/env.py` has no SQLite path and
  the earlier revisions are PostgreSQL-oriented); the SQLite backend gets its schema from ORM metadata and
  `initialize()`. The guards make the files inert for PG-only objects on another dialect, as the precedent revisions do.
  The ORM models are intentionally unchanged, so the hermetic suite is unaffected until promotion.
- **`essay_review_history`.** Unique `(essay_id, prior_fingerprint)` and the scope index are right. The UPDATE-only
  `BEFORE UPDATE` trigger raises `integrity_constraint_violation`; DELETE is not trapped, so the two `ON DELETE CASCADE`
  paths work (the rehearsal deletes an essay and a user and finds no history left).
- **`library_items` place.** Two nullable columns and a partial index `(user_id, language_code, place_at) WHERE place IS
  NOT NULL`. Consistent with `LibraryItem` (`models.py:583-665`): `kind` allows reading/listening/book, `relationship`
  allows `started`, `source_id` is 255, and `version`/`updated_at` are separate columns the place write does not touch.
- **`grammar_progress`.** Three nullable columns; the CHECK ties them together and bounds the score. `completed_at` stays
  NOT NULL, unchanged.

Findings (all P2, non-blocking; close before the first `git mv`):

- **P2-1 The whole chain is one transaction, so locks accumulate.** `migrations/env.py:28,39,53` runs the run in a single
  `begin_transaction()`, and `SET LOCAL` and every ACCESS EXCLUSIVE lock last to commit. Applied as one
  `--upgrade` to head, the `users` lock taken by 0018 is held through 0022's index build (a SHARE lock and a scan of
  `library_items`) and 0023's CHECK validation (an ACCESS EXCLUSIVE scan of `grammar_progress`). `users` is written on
  every sign-in, so logins would queue for the whole run. `bootstrap_runtime_schema.py` has `--to-revision`
  (`:205`). **Required change:** the operator runbook and approval entry apply the revisions in separate invocations, with
  0018 alone after a fresh backup, and the rehearsal records the order used. The proposal text ("promoted one at a time")
  should say "applied one at a time with `--to-revision`".
- **P2-2 The rehearsal proves shape, not scale.** Every table holds one or two seed rows. Nothing measures how long 0022's
  `CREATE INDEX` (non-concurrent) or 0023's `ADD CONSTRAINT ... CHECK` hold their locks on realistic row counts, and
  `lock_timeout` only bounds waiting for a lock, not how long a granted one is held. **Required change:** either run
  the same script with a volume seed (order of 100k `users`, a few million `library_items` and `grammar_progress`) and
  record the two durations, or state in the approval entry that the operator applies 0022 and 0023 in a maintenance
  window with an expected duration. Consider `ADD CONSTRAINT ... NOT VALID` then a separate `VALIDATE CONSTRAINT`.
- **P2-3 JSON `null` versus SQL `NULL` in the new JSON columns.** The partial index and the "no place" semantics depend on
  `place IS NOT NULL`. A SQLAlchemy `JSON` column persists Python `None` as the JSON literal `null`, not SQL `NULL`,
  unless declared `JSON(none_as_null=True)`; a JSON `null` row would satisfy `place IS NOT NULL` and enter the index.
  The same applies to `review_modes`. The rehearsal cannot see this (it writes with raw SQL). **Required change:** section
  15's model changes declare `place` and `review_modes` with `none_as_null=True`, and a real-repository test writes and
  clears a place and asserts SQL `NULL`.
- **P2-4 Parent scope on `essay_review_history`.** `user_id` and `language_code` are copied from the essay with no
  constraint tying them to it; ADA section 3 asks that child rows verify parent scope. **Required change:** either drop
  the redundant columns and read scope through the essay, or keep them and add a repository test that refuses a row whose
  scope differs from the essay's (a composite FK would need a new unique key on `essays`, which this proposal should
  not add).
- **P2-5 Settings token handling.** The token has microsecond resolution (good, and better than the profile row's
  one-second `updated_at`, `becoming_memory.py:83-91`). **Required change:** state that the API serves it as an opaque
  string (a JavaScript `Date` truncates to milliseconds), that the server sets it, and test a stale token across the API,
  not only the SQL. The shared token also makes two unrelated scalar edits conflict; the 409 re-read-and-reapply covers it.
- **P2-6 Small drafting points.** Section 5's guard text (`get_bind`) versus the files (`get_context`); the ORM should
  declare the 0023 CHECK so the PostgreSQL schema-parity test passes, while the SQLite `initialize()` ALTER path cannot
  add it (a fresh `create_all` can); and promotion moves `tests/test_adaptive_reading_schema.py` and
  `tests/test_reading_canonical_cutover_scripts.py` to the new head in the same commit (already in section 15).

### 3. Does the rehearsal prove what it claims?

It proves the DDL: the chain builds to 0016 from `versions/`, one head after 0016 with `proposed/`, upgrade, downgrade,
upgrade, identical schema signature, columns and defaults per column, defaults read by pre-existing rows (seeded before the
upgrade and checked after both upgrades), the CHECK's accepted and refused shapes with the constraint name asserted, the
UPDATE trigger (asserted on the message), both cascades, the unique key and a two-thread race that produced one row and one
refusal, and `lock_timeout` behaviour (55P03 after about 5.2 s, atomic rollback, both directions). The lock probes are not
vacuous: they assert a failure occurred, the SQLSTATE, the elapsed window 3-20 s, an unchanged revision and the state of a
`0018` column. I found no probe that can pass with nothing there, but several are weaker than their labels:

- **"an unknown essay" is refused** matches only the substring `essay_review_history` (`:605`), which appears in any error
  naming the table; assert `foreign key` or the constraint name.
- **"place is writable ... leaves version 1"** runs a plain `UPDATE` that never touches `version`, so it would pass for any
  schema with the column; it proves nothing about the application. Keep as a smoke line, do not cite it as evidence.
- **"conditional update"** exercises the probe's own SQL, which shows `IS NOT DISTINCT FROM` and microsecond round-trip work
  on the column; the application's statement does not exist yet (P2-5 covers the API).
- **"schema after up-down-up equals the first upgrade"** compares two heads, not the schema at 0016 before the upgrade with
  the schema after the downgrade. `everything_removed` checks the added objects but would miss a downgrade that altered
  something else. Capture the `schema_signature` of the touched tables at 0016 before upgrading and compare after
  downgrading.
- **"every revision sets lock_timeout"** is a source grep; the behavioural probes cover only `users`, so a missing guard in
  a later revision is caught only by the grep.
- **Old-code compatibility** is probed for `listening_progress` only. Add an insert into `users` and
  `user_language_profiles` that names none of the new columns (what a runtime at 0016 does after a code rollback).

None changes the verdict; the first two and the last two are cheap and I recommend adding them with P2-2.

### 4. The two open points

- **H-19 (a profile row with empty `declared_level` never reaches Welcome).** The literal D-104 H-1 rule is followed; the
  consequences are real. `GET /api/learner-profile` does not create a row (`becoming_memory.py:130`, `exists` flag), but
  any PATCH or PUT of another field (goal, style, support language, review settings) does. Any earlier onboarding step
  that writes the row, an abandoned onboarding, and every existing account that already has a row leave
  `declared_level = ''` for good, so the level that H2 exists to store is never asked of them, and `entryRoute` and Today
  must treat `''` as "not declared". **Recommendation:** keep the literal rule for entry routing (missing row opens
  setup, nothing is replayed), verify that the onboarding flow writes the row only at its final step or only after the
  level answer, and ask for a level for an existing row with `''` through a non-blocking, dismissible prompt on Profile
  or Today rather than a forced route. A forced route needs a stored "dismissed" marker, which is another persistence
  decision the proposal does not have and should not invent. Record the choice in the human's answer to H-19.
- **H-20 (quiz result stored only with completion).** **Accept the proposal's reading.** `completed_at` is the owner
  table's NOT NULL completion fact (`models.py:214-226`); relaxing it would change what a `grammar_progress` row means for
  R5 history and for the alias reads, which this proposal rightly avoids. A quiz abandoned before completion is not a
  result. Conditions: (a) the completion write and the quiz fields are one upsert in one route; (b) a retake updates
  `last_quiz_*` and leaves the first `completed_at` (say which); (c) the number is browser-graded and therefore labelled
  client-reported and never read as evidence (`EA:14`); (d) the future route validates the published point id before
  accepting anything, as D-104 says.

### Required before the first `git mv`

1. P2-1 (apply one revision per invocation, 0018 alone) and P2-2 (a volume run, or a stated maintenance window).
2. P2-3 (`none_as_null`), P2-4 (child scope), P2-5 (opaque token) recorded in section 15 with their tests.
3. The rehearsal strengthened as listed in section 3, then re-recorded.
4. The human's answers to H-19 and H-20.

This delta review approves the revision-3 text and the migration files as proposals. It is not product approval, it does
not authorise moving any file into `versions/` or applying any migration, and it does not enable
`ORENA_ACCOUNT_BACKBONE`.
