# Proposal (D-101 D4): the learner records D3 found missing on the server

Status: **PROPOSED, revision 3, with the delta-review changes of section 16** (2026-09-30, `codex/work` at `80a7fb8`), matching the human's decisions in
**D-104** (`DECISION_LOG.md:3604`; AGENTS §7 is amended accordingly). Revision 2 answered the independent review
`LEARNER_RECORDS_D4.REVIEW.md` (REQUEST CHANGES at rev 1; the reviewer's APPROVE is recorded at rev 2 in Git); the
finding-by-finding mapping is section 12 and what D-104 changed is section 14. The proposed migrations now exist as
files in `migrations/proposed/` (not `versions/`) and the rehearsal script is
`scripts/rehearse_learner_records_schema.py` (section 6). Document only: no code,
schema or migration is changed by this file. Process (AGENTS §1 "Architecture review authority", §7,
D-054 workflow, D-102): proposal -> independent architecture review -> human approval -> code +
migration + tests -> rehearsal on a throwaway PostgreSQL -> the human applies migrations to a runtime.
The implementer of this proposal may not self-approve it (AGENTS §1). Production (:8000) and preview
(:8010) are never touched by it.

**H2 is merged into this proposal.** `DECLARED_LEVEL_STORAGE.md` rev 2 (APPROVED by independent
review, `DECLARED_LEVEL_STORAGE.REVIEW.md`) is item I1 below, unchanged in design; only its
revision number moves (0017 stays 0017). Its review items N1-N3 are copied into I1 and section 9. Nothing
in it is re-litigated.

**D-103 is folded in** (the human's answers on D3, `DECISION_LOG.md:3544-3611`): Dictation is
server-authoritative (I18), the Chinese evaluator refresh keeps the previous review as immutable history
(I19), Profile/Progress metrics are "a real metric or no metric" (I14), retirements touch UI and routes only
(I4, I11, I13), books and pasted texts have no comprehension persistence (I12), curated Writing prompts move
to a Prompt Bank that is content, not learner data (I5). Point 5 (speech providers) has no persistence
impact.

Legend: **[V]** read in code or the docs at `1bd21e7` (plus D-103 as recorded in the Decision Log);
**[I]** inferred, to verify at implementation.
`D3` = `docs/project/D3_PRODUCT_MATRIX.md`; `ADA` = `docs/product/ORENA_ACCOUNT_DATA_ARCHITECTURE.md`;
`EA` = `docs/product/ORENA_EVIDENCE_ARCHITECTURE.md`.

## 0. The rule applied, and the finding that shapes everything

D-101 "Persistence" (`DECISION_LOG.md:3414-3419`) [V]: server storage is required for learner-owned
state with learning meaning or that must survive across devices or sessions; pure presentation
(theme, text size, an open sheet, hover, a transient) need not be stored; no ad-hoc tables. ADA §3
(`:93-96`) [V]: "Reuse equivalent existing records rather than adding parallel ones." ADA §2 (`:89-91`)
[V]: "No generic JSON learner document becomes the source of truth for all domains."

**Finding.** Most of D3's device-only state already has a target record in the schema that shipped in
`20260908_0005` (eight backbone tables, `migrations/versions/20260908_0005_account_work_backbone.py`),
with a working repository and routes, and it is **switched off**:
- `works` (kind, source ref, version, lifecycle, JSON payload, per-account change sequence) with
  `work_turns`, `language_provenance`, `mutation_receipts`, `change_records` [V];
- `WORK_KINDS = ('draft','response','conversation')` and `MUTATION_DOMAINS` are string registries in
  code, not DB enums: `works.kind` has no CHECK, so a new kind is a code change and not a migration
  (`work_contract.py:21,25`; migration 0005 comment "Strings so that registering a new kind ... is a code
  change and not a migration") [V];
- `GET /api/account-backbone` reports `disabled` because `ORENA_ACCOUNT_BACKBONE` is unset
  (`account_backbone.py:30,48-56`) [V]. `compose.yaml` does not pass the variable at all (grep finds no
  occurrence) [V].

**Why it is disabled.** Not a defect: activation is deliberately its own human gate, separate from the
schema (`I2_ACTIVATION_RUNBOOK.md:278-285` "A separate decision from the schema ... A human gate everywhere
except the sandbox, where D-054 delegates it"; `ARCHITECTURE_INVARIANTS.md:195-199`) [V]. D-055 adds
that no runtime path may delete or re-register an account until an out-of-database deletion journal and the
owner-table deletion workflow exist (`DECISION_LOG.md:1571-1585`) [V]. So the questions the human must answer
to enable it are (a) is the flag turned on for the lane runtime and for :8000 after the merge (D-102 point 7),
and (b) are the D-055 preconditions still the reason to hold. This proposal recommends **on** (section 2),
as a human-gated configuration change, not a schema change.

Consequence: the proposal needs **seven additive migrations (0017-0023, all required by D-104)**, and **one new table**
(an append-only review history, I19, justified there), not one table per gap (section 5). Everything else is
registry entries, routes and repositories over existing tables.

## 1. Summary table

Class: **S** server-required; **P** presentation, no server; **D** device by contract or by design;
**H** human decision before classification.

| # | Item | Class | Target store | New table? | Migration | D7 consumer |
| --- | --- | --- | --- | --- | --- | --- |
| I1 | `declared_level` (H2) | S | `user_language_profiles.declared_level` | column | 0017 | Welcome level step, `entryRoute`, Today |
| I2 | Learning language on the account | S | `users.learning_language` | column | 0018 | Welcome languages step, Settings, session bootstrap |
| I3 | Interface language | S (H) | `users.interface_language` | column | 0018 | Settings, first paint |
| I3b | Weekly goal (days per week) | S | `users.weekly_goal_days` (+ `users.settings_updated_at`, the version token) | column | 0018 | Profile weekly-goal bar |
| I4 | Reading/listening position and completion ("continue") | S (D-104 H-12: Design B) | `library_items` (`started` relationship) + `place`, `place_at` columns | columns | 0022 | Today, Discover, Content Detail, Practice Hub, My Library, Reading Complete |
| I5 | Writing drafts (+ register, target length) | S | `works` kind `draft` (exists) | none | none (flag on) | Writing |
| I6 | Conversation records | S | `works` kind `conversation` + `work_turns` | none | none (code + flag) | Conversation |
| I7 | Speaking Summary | derived | `speaking_attempts` + `works` `response` reads | none | none | Speaking Summary |
| I8 | Free Talk / Situation / React results | S | audio-free `speaking_attempts` when spoken; `works` `response` when typed | none | none | Free Talk, Situation, React |
| I9 | Reading Transfer results | S (H) | `works` kind `response` (not evidence) | none | none | Reading Transfer, Reading Complete |
| I10 | Sentence notes and highlights | S | `works` kind `annotation` | none | none | Reader, Quick Sheet, Reading Complete |
| I11 | Grammar progress per Grammar Lab point | S | `grammar_progress` + `last_quiz_*` columns | columns | 0023 | Grammar Library, Grammar Concept |
| I12 | Imported texts, kept texts, `url:` media, kept-language provenance | S | `works` kind `imported`; `library_items`; `language_provenance` | none | none | Import, Discover, Content Detail, Quick Sheet |
| I13 | Review modes and limits | S | `user_language_profiles` named columns | columns | 0019 | Settings Review tab, Review Session |
| I14 | Profile/Progress metrics: real streak, weekly-goal days, activity counts; the rest hidden | derived (D-104 H-5) | derived read over existing server records (+ I3b); no streak table | none | none | Profile, Today, Progress |
| I15 | Orena history and coach notes | D (flag) | device, per AGENT_CONTRACT:383 | none | none | Orena |
| I16 | Listening/shadowing progress language check; Shadowing read-back | S (fix) | `listening_progress`, `shadowing_progress` (exist) | none | none | Listening, Dictation, Shadowing |
| I17 | Theme, text size, transcript prefs, search recents, step/nav state | P | device | none | none | - |
| I18 | Dictation: server recomputes the score (D-103.2) | S | `listening_progress` (exists) + `score_source` | column | 0020 | Dictation |
| I19 | Chinese evaluator refresh: previous review kept as immutable history (D-103.7) | S | `essays` (current review) + new `essay_review_history` | **new table** | 0021 | Writing review (reopen an old essay) |

New tables: **one** (`essay_review_history`, I19). New columns: 0017: 1; 0018: 4 (three settings + `settings_updated_at`); 0019: 3 named review
columns; 0020: 1; 0022 (I4): 2; 0023 (I11): 3.

## 2. Cross-cutting design

**2.1 The account-work backbone (D-104 H-11: approved, default off).** Items I5, I6, I8-I10 and I12 need
`ORENA_ACCOUNT_BACKBONE=on`. The gate order is fixed by D-104: (1) the D4 migrations pass the PostgreSQL up/down/up
rehearsal (section 6); (2) they are applied to the lane runtime under its gate; (3) **only then** the flag is set on
the lane runtime. The flag's **default stays off** (`compose.yaml` passes `ORENA_ACCOUNT_BACKBONE:
${ORENA_ACCOUNT_BACKBONE:-off}`, a config diff in the implementation). **:8000 is enabled only after the merge, a
backup, the migration human gate and smoke verification** (D-102 point 7). Every client already asks
`GET /api/account-backbone` first and falls back to device when `disabled` (`draft-sync.js`;
`infrastructure/api.js:485`) [V]. The room says "kept with your account" only for a server-acknowledged save, so
turning the flag off later degrades to device honestly. I4 does **not** depend on the backbone (Design B).

**2.2 Mutation contract for new kinds.** Same as drafts (`work_api.py:156-205, 234-260`) [V]: client
`operationId` + `expectedVersion`; `committed`/`replay` 200; `conflict` 409 with server payload, nothing merged
(ADA §4, `:138-143`); payload bounded by `MAX_PAYLOAD_CHARS = 200_000` (`work_api.py:56,163`). Each new kind is a
deterministic work id per (account, incarnation, language, kind, key) like `_draft_work_id` (`work_api.py:218-219`),
so a re-open finds the same row and no list-then-find race exists.

**2.3 One new read: a bounded list.** The stream (`GET /api/works/changes`) is for sync, not for "the 20 most
recent". Add `GET /api/works?kind=&source_kind=&limit=` (limit <= 50), scope-checked, ordered by
`updated_sequence desc` using `ix_works_scope_sequence (incarnation_id, language_code, updated_sequence, id)`
(migration 0005) [V]. No schema change. `kind` narrows after the index range, acceptable at learner scale [I].

**2.4 Conflict rules, one per kind of record, and what this proposal does not decide.** ADA §4 forbids
last-write-wins by client timestamp and forbids automatic prose merges [V]. The rules used here:
- **Text and structured work (drafts, imported text, conversations, annotations):** `expectedVersion`; a stale write
  gets 409 with the server copy and nothing is merged. Annotations are a set: on a 409 the client unions by id and
  re-PUTs (a client action, not a server merge of prose).
- **Profile row fields (`user_language_profiles`: declared level, review settings, per-language settings):**
  `expected_updated_at`, the H2 conditional write (I1, N1).
- **Account scalars on `users` (learning language, interface language, weekly goal): server-owned conditional
  update, D-104 H-17.** `users.settings_updated_at` (migration 0018) is the version token of the three scalars. A
  write carries the token it read (`NULL` = never written); the server updates `WHERE id = :id AND
  settings_updated_at IS NOT DISTINCT FROM :expected` and sets `settings_updated_at` to the **server** time in the
  same statement. Zero rows means 409 `version_conflict` carrying the current token, so a stale device learns it is
  stale. **A client timestamp is never a token and never resolves a conflict**, and there is **no blind
  arrival-order last write** (the exception revision 2 proposed is withdrawn). TIMESTAMPTZ has microsecond
  resolution, which avoids the one-second token collisions of the profile row; the residual is two writes committed in
  the same microsecond, which the row lock serialises anyway. Onboarding or Settings that gets a 409 re-reads and
  re-applies once (H2's precedent). **The API serves the token as an opaque string** (`settings_version`): the
  timestamp text exactly as the database renders it, microseconds included, set only by the server. Clients echo it
  verbatim and never parse it (a JavaScript `Date` truncates to milliseconds, so a client that round-tripped it through
  `Date` would turn every write into a conflict). The token is shared by the three scalars, so two unrelated scalar
  edits from stale devices conflict; the 409 re-read-and-reapply covers that. The plan tests it across the API (section 9).
- **Positions (I4):** single-valued, on `library_items`, updated in place; the newest write wins. The place is
  navigation state and not learning evidence, so it deliberately has no version check (see I4).
Nothing here defines cross-device sync, cursors, tombstone horizons or receipt compaction (AGENTS §7, ADA §5).

**2.5 No bulk device migration (D-104 H-6).** There is no "bring this device's work into your account" flow and no
silent bulk upload; nothing is imported at startup (D-002). **Legacy device values stay readable where a
compatibility path already reads them** (for example `orena.encounters.v1` for a learner's existing continuation,
notes and highlights while the device holds them; the client shows the device value when the server has none). New
learner state from the finished `/next` flows is written to the server. The existing draft sync
(`draft-sync.js` sends a device draft when the server holds none, per piece) may remain as it is. ADA §6 step 6
(explicit learner import with preview) is therefore **not** implemented by this proposal; if it is wanted later it is
its own slice.

**2.6 Deletion, incarnation and export (all items) - corrected by review P1-1.** There are two kinds of row and
they behave differently, because the `users` row **survives** account deletion: `account_incarnations.user_id ->
users ON DELETE RESTRICT` and the deletion journal anchor on it, and the barrier is kept for the life of the
deployment (ADA §1 `:41-44`; D-055) [V].
- **Incarnation-keyed rows** (`works`, `work_turns`, `mutation_receipts`, `change_records`,
  `language_provenance`): the cascade hangs off the `account_incarnations` row, which is *kept* as the barrier, so
  it does **not** fire. The D-055(b) workflow must delete these rows explicitly.
- **Account-keyed rows** (owner tables keyed by `users.id`, which a re-registered account with a new incarnation
  would otherwise read): `user_language_profiles` (declared level, review settings, goal, style, support language),
  `grammar_progress`, `listening_progress`, `shadowing_progress`, `speaking_attempts`, `essays` (+ `essay_revisions`), `library_items`, `saved_words`. The workflow must delete these. (`essay_review_history`
  has no scope columns of its own; it follows the account's `essays` through its cascade, section I19.)
- **New columns on `users` itself** (`learning_language`, `interface_language`, `weekly_goal_days`) live on the row
  that is kept. The workflow must **reset them to their defaults** (`''`, `''`, `NULL`); nothing else removes them.
  This is the reset D-055(b) must perform for this proposal; without it a re-registered account would inherit the
  deleted account's language choices.
- The approval entry records every table and column above in the D-055(b) enumeration. No runtime deletion path
  exists yet (D-055); this proposal adds none. The section 9 enumeration test asserts each one (see there).
- Export: ADA defines no export contract and this proposal adds none. Each kind is readable through its own GET.
  Not decided.

## 3. Items

Each item: state; D3 evidence; class; store; API; migration; default/import; deletion/export; tests; consumer.
Sections repeat only what is not already in section 2.

### I1. `declared_level` (H2, merged, unchanged)

- **State.** The learner's self-declared current level for a learning language, never measured or inferred.
- **D3.** Onboarding/Profile row "level step": store MISSING, return MISSING (O7-O9); `PATCH /api/learner-profile
  {declared_level}` -> 501 [V] (`account_profile.py:92-96`).
- **Class.** S. **Store.** `user_language_profiles.declared_level VARCHAR(20) NOT NULL DEFAULT ''`.
  **API.** existing `/api/learner-profile` (GET/PATCH/PUT), allowed set from the registry per scope language, fails
  closed, conditional `UPDATE ... WHERE updated_at = :expected`.
- **Migration.** `20260930_0017_declared_level` chained on `20260924_0016`; `SET LOCAL lock_timeout = '5s'`;
  add column; downgrade drops it (rehearsal only). Written in `migrations/proposed/`, `git mv` after review,
  rehearsal and authorization. Full design: `DECLARED_LEVEL_STORAGE.md` sections 1-9.
- **Existing accounts (D-104 H-1).** Default `''`; the backfill from evidence is rejected. **Welcome/setup is required
  once per learning language whose learner-language profile does not exist yet, without replaying the whole
  onboarding.** So the entry rule is keyed on the absence of the `user_language_profiles` row for the language, not on
  an empty level (this narrows H2's "row without a level opens Welcome", section 4 of the H2 proposal; see section 14
  for what stays open). A language with a profile row and `declared_level = ''` is not sent to Welcome by this rule.
- **H2 review N1 (copied, P2-1).** The conditional write needs an interface and a creation path. (a) Add an
  explicit parameter to `SpecializedLearningRepository.upsert_profile_record` (for example
  `expected_updated_at: str | None`, where `None` means unconditional, which PUT keeps) rather than a magic key
  in `values`. (b) PostgreSQL creation race: the `s.get` then `s.add` insert raises `IntegrityError` under a
  race; it must map to 409 `version_conflict`, not a 500. (c) SQLite creation race: the insert is
  `INSERT ... ON CONFLICT(id) DO UPDATE`, which would silently overwrite a concurrently created row; creation
  uses a plain insert, or `DO NOTHING` with a rowcount check. (d) Tests: "create-while-created -> 409" on both
  backends. This path is shared by every field PATCHed on the profile row (I1, I13), so it is fixed once.
  **N2** is satisfied by the dialect guard in section 5 (plus the one-line comment, P2-10). **N3** (legend
  wording) is cosmetic.
- **Consumer.** Welcome level step (`onboarding/model.js:188-199`), `entryRoute` (`shell/routes.js:77-87`),
  `scripts/test_orena_shell.mjs:75` as a named contract change.

### I2. The learning language on the account

- **State.** Which language the learner is learning now (`en`, `zh`, later `ja`).
- **D3.** O4 [V]: the value lives only in the session cookie: `POST /api/platform/language` sets
  `request.session["language"]` (`core/platform_api.py:37-43`); the middleware defaults to `en` without it
  (`auth_support.py:409-411`); a new login or device lands in English. The lead re-checked on :8021.
  It also breaks H2's rule "open `#/welcome` when there is no learning language": there is always one.
- **Class.** S (survives sessions and devices; a ZH learner must not restart in English).
- **Store.** New column `users.learning_language VARCHAR(20) NOT NULL DEFAULT ''` (`''` = never chosen).
  Justification: the value is account-wide, not per-language, so it cannot live on the per-language
  `user_language_profiles` row (ADA §1 `:53-54`: "Account-wide settings must not be accidentally keyed by the
  current learning language" [V]). `users` is the account row and the only existing account-keyed identity table.
  The auth `users` table in the SQLite auth repository is a different, test-only table; it gets the same guarded
  `ALTER` if a test needs it [I].
- **Semantics.** The stored value **seeds a session that has none**; it does not override a session that already
  chose (a second device may be in the other language). `POST /api/platform/language` writes the session and the
  column, under the server-owned expected-version rule of section 2.4 (`users.settings_updated_at`). Seeding point: `session/bootstrap`
  (`auth_support.py:376-401`) and the middleware read `request.session.get("language")`; when absent and the
  column is non-empty, use it [I: exact seeding site to be verified]. **No per-request database read (P2-9):** the
  stored value is read only when the session has no language, and is then written into the session, so every
  later request reads the cookie as today (the middleware runs on every request, `auth_support.py:409-455`).
  In non-authenticated (`legacy`) mode there is no `users` row: nothing is stored or read, and the session and the
  default behave as today.
- **API.** Existing `POST /api/platform/language` (extended, same body) and `GET /api/session/bootstrap`, which
  gains `language.stored: bool` (additive, so the entry rule can tell "never chosen" from the default).
- **Migration.** 0018 (with I3, I3b and `settings_updated_at`). Default `''` for all accounts; no backfill (a guess from `user_language_profiles`
  recency would store an inferred value in a stated field, the same reason H2 rejected it).
- **Deletion/export.** Column on the surviving `users` row: **reset by the D-055(b) workflow** (section 2.6), not
  removed with anything.
- **Tests.** Section 9. **Consumer.** Welcome languages step, Settings target-language pick, bootstrap.

### I3. Interface language

- **State.** Language of the app's own text (`en`, `zh`, `vi`), independent of support and learning language.
- **D3.** S3 [V]: `orena.interface` in localStorage (`kit/boot.js:19`); `interface_language` is `stored=False`
  (`account_profile.py:80-83`); ADA §1 calls it an explicit account-wide value (`:49-51`).
- **Class.** S, but low-risk and reversible: classified **H** (H-2) because it is also first-paint presentation.
  Recommended S: a learner who set Vietnamese on one device should not see English on the next.
- **Store.** `users.interface_language VARCHAR(8) NOT NULL DEFAULT ''` in 0018, next to I2 (both account-wide, both
  on the account row), instead of repeating the per-language-row wart that `support_language` has
  (`becoming_memory.py:64-68`, H2 section 9) [V]. The wart is not touched.
- **API.** `interface_language` flips to `stored=True` in `account_profile.ACCOUNT_SETTINGS`, but its column is on
  `users`, so `becoming_memory` needs an account-level write path beside the language-row one [I]. Device
  `orena.interface` stays as the first-paint cache; the server value reconciles at bootstrap. Conflict rule:
  the `settings_updated_at` expected-version update of section 2.4. Deletion: reset on the `users` row.
- **Default.** `''` = follow the device/OS as today. No import needed. **Consumer.** Settings, `kit/boot.js`.

### I3b. Weekly goal (target days per week)

- **State.** How many days a week the learner aims to study. D-103.4: "persisted learner goals where they apply".
- **D3.** P3 / `UI_BACKEND_GAPS` N-32 item 3 [V]: the weekly-goal bar's segment count (5) is a design constant and
  "no configurable weekly-goal-in-days feature exists to measure a real done-count against it".
- **Class.** S: a learner's stated goal, cross-device. It applies because a defensible done-count exists (distinct
  active days, I14). A **daily goal in minutes does not apply**: nothing measures duration (D-103.4), so no setting is
  stored for it.
- **Store.** `users.weekly_goal_days SMALLINT NULL` (`NULL` = not set; 1-7 validated by the application), in 0018
  beside I2/I3, account-wide for the same reason as I2. **API.** Account-level PATCH beside `/api/learner-profile`
  (the `settings_updated_at` expected-version update of section 2.4; deletion: reset on the `users` row). **Default.** `NULL`: Profile shows the count of active days without a target
  (D7/design decision whether the bar is drawn; not decided here). **Deletion.** Column on the account row.

### I4. Reading and listening position and completion (D-104 H-12: Design B, migration 0022)

- **State.** Per content item and learning language: where the learner is (paragraph/segment index of total,
  furthest percent, chapter), when last, and whether they finished (Reading Complete's "Finished").
- **D3.** Reading R4/R5/K3 (MISSING store/return), Listening L1.s/L1.r, Navigation N-st/N-rt [V]. Device key
  `orena.encounters.v1:<owner>:<lang>` `.continuation[]`, up to 20 (`product/memory.js:49-50,276`; `readPlace` :26-37).
- **Class.** S. **Navigation and progress state, not learning evidence** (D-104 H-12; EA §1 "Continue ... excluded
  claim: unfinished thread is a recommendation backed by mastery", `EA:16`; "reading time alone proves understanding",
  `EA:11`) [V]. A finished flag is a continuation marker only.
- **Store (decided).** `library_items`, the "ContentMembership ... a relationship, never a copy"
  (`models.py:565-570`), on its already-allowed `started` relationship (`models.py:577`). Migration **0022** adds
  `place JSON NULL` and `place_at TIMESTAMPTZ NULL` and a partial index `(user_id, language_code, place_at) WHERE place
  IS NOT NULL`. The `works` continuation design with high-volume receipts is **not used** (D-104): a position write
  produces no mutation receipt, no change record and no stream lock, so it adds nothing to the reserved receipt
  stream (ADA `:199-203`).
- **Rows and writes.** One row per (learner, language, kind, content id), kind `reading`, `listening` or `book`,
  relationship `started`; `source_id` is at most 255 characters, so a `url:` id is its digest and the URL lives in the
  imported record of I12. The row is created on first open and **updated in place**; its count is bounded by the
  content the learner opens, not by time spent. The place write does **not** touch `library_items.version` or
  `updated_at`, so it can never make a learner's pin, note or state PATCH (`expected_version`,
  `library_repository.py`) conflict; `place_at` is the server-set time of the last place write and orders the list. The
  server may cap the UPDATE rate per row (a write under 30 s old that crosses no boundary is answered `coalesced`
  without an UPDATE); volume is about 0.5 M in-place UPDATEs per day at 20,000 daily-active learners x 25 writes,
  with no row growth.
- **Payload.** `place` = `{index, total, within, finished, cleared, title, intent}` (bounded, validated like
  `readPlace`); "clear" is `cleared: true`, never deleting the relationship the learner may also have kept or pinned.
- **API.** New `PUT /api/continue/{content_id}` (server-set `place_at`; unconditional, newest wins) and `GET
  /api/continue?limit=` (<= 50, ordered by `place_at`). PostgreSQL runtime only; device memory stays the cache and the
  fallback.
- **Departure from ADA §2 (recorded).** ADA §2 names Continue an "account work-derived index". This decision stores it
  on the relationship record instead, for the reason above; D-104 accepts it.
- **Default and legacy.** Empty for existing accounts; the device's continuation list stays readable through the
  existing compatibility path (section 2.5) and is not uploaded.
- **Deletion/export.** `library_items` rows are keyed by account (the `users` row survives), so the D-055(b) workflow
  deletes them explicitly (section 2.6). A source removed makes the item "unavailable".
- **Retirement (D-103.1).** The old `#/continue` room retires (UI and route only); its data was device memory.
- **Consumers.** Today (`today/model.js:134-190`), Discover (`discover/model.js:31-112`), Content Detail
  (`content/screen.js:150-153`), Practice Hub continue row (`practice/model.js:207-233`), My Library progress
  (`library/model.js:31-36`, `pct` currently always 0), Reading Complete (`reader-complete/screen.js:80`) [V].

### I5. Writing drafts

- **State.** The unsubmitted text and task per piece (`essay:<series>`, `expression:free`, `::task`), and the
  per-visit register and target length.
- **D3.** W1s2 [V]: device memory `expressions{}`; server path `GET/PUT /api/drafts/{key}` exists
  (`work_api.py:222,234`) and is used by `product/draft-sync.js`, but only when the backbone is `active`, and it
  answers `disabled` on :8021.
- **Class.** S. **Why it is off:** section 0 (activation gate, D-054/D-055), not a defect.
- **Decision: enable, do not replace.** The path is complete and tested (`tests/test_work_api.py`,
  `tests/test_orena_work_persistence_postgres.py`) [V]: versions, operation ids, conflict with both branches
  kept, the device copy always kept. An alternative store would duplicate it (ADA §3). Action: section 2.1 only.
  No migration.
- **Register and target length.** Today a per-visit `Map` (`screens/writing/screen.js:70`); `EssayIn.writing_context`
  is ignored by `evaluate_with_ai` (`model.js:163-167`) [V]. Two options, **H-7**: (a) store them in the draft
  payload (`DraftSave` gains two bounded fields; no migration) and make the evaluator read them; (b) retire the
  controls because nothing consumes them (rule 43). Not decided here.
- **Curated prompts (D-103.6).** The prompt catalogue is content (Writing Prompt Bank under the content
  architecture), not learner data, and is out of D4. The only learner-side record needed is *which prompt a piece
  answers*: an optional `promptRef {source, id}` in the draft payload (`DraftSave` gains one bounded field) and,
  on submit, `prompt_ref` in the essay's `module_data`, written by `create_essay` beside `practice_context` and
  `review_identity` (`app.py:2555`) [V]. Code only, no migration; the essay's own `prompt` text stays the
  evaluator's input. Custom/free writing sends no ref.
- **Default/import.** Existing behaviour: a device draft is sent when the server has none.
- **Consumer.** Writing compose. **Tests.** The existing work-API tests plus the section 9 rows.

### I6. Conversation records

- **State.** A conversation: ordered learner/partner turns, coaching, ended flag, scenario.
- **D3.** P6.s/P6.r [V]: `memory.conversation()` -> `.conversations` in device memory
  (`screens/conversation/screen.js:71-74`); a reload returns to the scenario picker. ADA §2 row:
  "Conversation | device sequence | account work with ordered immutable turns and versioned head" (`:81`).
- **Class.** S. **Store.** `works` kind `conversation` (registered) + `work_turns` (ordinal, author_role
  `learner|partner`, content, immutable) (migration 0005) [V]. **Gap [V]:** no repository code or route appends
  turns today (`grep work_turns` finds only the table list); `PUT /api/works/{id}` writes a whole payload.
- **API.** New `POST /api/works/{id}/turns` with `{operationId, expectedHead, role, text, replyTo}`: an append at an
  expected head, retry returns the same turn, a simultaneous different append conflicts (ADA §4, `:141-142`);
  role alternation and `reply_to` rules from `restoreConversation` (`product/conversation.js:20-60`) enforced
  server-side. `GET /api/works/{id}` returns the head; a list via section 2.3. Coaching
  ("how did it land") is not a turn: it is derived from the turn and is regenerated or kept in the turn payload,
  **H-8**.
- **Migration.** None (tables exist). **Default.** None; the device's conversations are not uploaded (H-6).
- **Consumer.** Conversation room: restore on reload, scenario picker shows resumable conversations.

### I7. Speaking Summary

- **State.** "This session": what the learner did while speaking.
- **D3.** P4.s/P4.r [V]: `sessionStorage` `orena.speaking.session.v1` (`product/speaking-session.js`); a new
  context shows nothing though the server holds attempts.
- **Class.** Derived, no store. The summary is a **read** of what I8 and existing scripted takes write:
  `GET /api/speech/attempts` and the `response` works of I8, plus `learner-summary` speaking domain
  (`learner_summary.py:194`) [V]. `api.speakingAttempts(limit, assetId, segmentId)` exists
  (`infrastructure/api.js:441`).
- **Change.** `GET /api/speech/attempts` gains an optional `since` (ISO instant, server-clamped) so "this session"
  is a window, not a client list. The list route today has only `limit/asset_id/segment_id`
  (`speech_api.py:437-455`) [V]. `sessionStorage` stays only as the window's start marker (presentation).
- **Migration.** None. **Consumer.** Speaking Summary; Attempt History and Compare read the same route (D3 P3.u,
  P2.u), which is D7 reuse, not persistence.

### I8. Free Talk, Situation and React results

- **State.** What the learner said/typed in an open-ended speaking task and the coaching returned.
- **D3.** P5.s, P7.s, L2.s [V]: nothing reaches the server; only `logSpeakingTask` writes `sessionStorage`.
  `POST /api/speech/attempts` already accepts a free-expression attempt: reference optional, alignment
  unmeasured (`speech_api.py:134-135`) [V].
- **Class.** S, with two cases that must not be conflated (EA §1 Speaking, `EA:15`: "typed coaching measured
  pronunciation" is an excluded claim [V]):
  - **Spoken take.** An audio-free `speaking_attempts` row with `reference_text=''` and `pronunciation: null`.
    Constraints found [V]: `segment_id` is **required** (`speech_api.py:_normalize_speaking_attempt`), so a task
    without a segment must send a stable synthetic one (e.g. the invitation id); the language check is hard-coded
    `{"en","zh"}` (`:126-130`), an existing gap for `ja` that this proposal does not widen. An unmeasured score
    must not be shown as 0 (D3 wrong-data risk 2): the read side (Progress) must skip `null` dimensions, a
    D7/read-model fix, no storage change.
  - **Typed answer.** Not a speaking attempt. Stored as `works` kind `response` with source
    `{kind:'invitation'|'media', id}` and payload `{answer, coaching, mode:'free_talk'|'situation'|'react'}`. It is
    a learner record (history, "what I said"), not evidence; Progress does not score it (H-9 asks whether
    History lists it).
- **API.** Spoken: existing `POST /api/speech/attempts`. Typed: `PUT /api/works/{id}` (kind `response`, already
  registered) with a deterministic id per (source, take). **Migration.** None.
- **Consumer.** Free Talk, Situation, React (`capabilities/voice-feedback.js#evaluateVoice` is the reuse, D3 part 2).

### I9. Reading Transfer results

- **State.** The learner's paraphrase/inference/context-shift answer for one sentence, and the coaching.
- **D3.** T3 [V]: nothing is written; the screen says there is "no Reading Transfer evidence contract".
- **Which domain owns it (H-3).** Options and analysis:
  1. **Reading evidence** (`reading_attempts`): rejected. It is keyed to comprehension sets and questions with
     foreign keys (`models.py:1271-1330`) and the endpoint is coaching, "not measurement"
     (`media_interaction.py:716-724`) [V]; storing it there would let it read as comprehension evidence.
  2. **Speaking** (`speaking_attempts`): only for a spoken answer, and then it is the same record as I8.
  3. **Writing** (`essays`): would require an evaluator run; Transfer is not evaluated writing.
  4. **`works` kind `response`** (recommended): ADA §2 lists "Draft/reading response" under account work (`:79`).
     Payload `{mode, sentenceRef, answer, coaching}`; source = the text. Not evidence, not scored.
- **Recommendation:** option 4; Reading Complete may count "responses written" as activity, never as
  "understood". A Transfer *evidence* contract (if the human wants a score) is a separate producer row in EA §1
  and is out of scope (H-3).
- **Migration.** None. **Consumer.** Reading Transfer (Finish now saves), Reading Complete.

### I10. Sentence Quick Sheet notes and highlights

- **State.** Sentence notes (type factual/reflection/question, <= 600 chars) and highlighted sentences, per content.
- **D3.** V2s/V2r, R4 [V]: `orena.quicksheet.notes.v1:<owner>` (`quick-sheet/model.js:223-224`) and
  `orena.reader.highlights.v1:<owner>` (`reader/highlights.js:16-18`); the Quick Sheet "Save highlight" is
  not built because no endpoint exists (`quick-sheet/sheet.js:14-19`).
- **Class.** S (learner-owned annotation, lost with the device).
- **Store.** `works` kind `annotation`, one work per (content id): payload `{highlights:[{id,segment,sentence,at}],
  notes:[{id,key,type,text,at}]}`; source = the content. Bounds must fit `MAX_PAYLOAD_CHARS = 200_000`
  (`work_api.py:56`): 300 highlights x 1200 chars is 360 KB [V, `highlights.js:23,60`], so the server bound is lower:
  **at most 80 highlights x 400 characters and 120 notes x 600 characters, about 104 KB worst case** (typical < 10 KB),
  and the client bound follows it. `works.payload` is rewritten whole on every commit (`work_repository.py`), so the
  bound matters; annotation writes are user-initiated, not continuous. Clearing is `{cleared:true}` in the payload,
  never lifecycle `deleted` (a deterministic id cannot be reused, P2-7). Rejected: `library_items kind='note'`
  (`LIBRARY_KINDS`, `models.py:575`): one row per (kind, source_id, relationship), so several notes per sentence
  and a note type do not fit without a JSON column.
- **API.** `GET/PUT /api/annotations/{content_id}` (deterministic work id). On 409 the client unions by id and
  re-PUTs (section 2.4).
- **Migration.** None. **Default/import.** Empty; device notes and highlights stay readable through their existing
  compatibility path and are not uploaded (H-6). **Consumer.** Reader, Quick Sheet Note tab,
  Reading Complete ("notes & highlights" count, currently device, `reader-complete/screen.js:59-68`).

### I11. Grammar progress per Grammar Lab point

- **State.** Which Grammar Lab points the learner has completed, and (optionally) the last quiz result.
- **D3.** G4/G7/G8 (MISSING), G5, G11 [V]: no per-point progress; `POST /api/library/grammar/{id}/complete`
  404s any id that is not an R5 lesson (`app.py:2157-2177`); `grammar_progress` is unique on
  `(user, language, lesson_id VARCHAR(255))` (`models.py:214-226`) [V].
- **Class.** S for completion. The new grammar is not R5: ids are Grammar Lab point ids (`en.present_perfect`);
  R5 ids resolve through each point's `aliases` (D-101 F; `GRAMMAR_CONTENT_CONTRACT.md` §9 rule 2).
  **D-103.1:** learner-facing R5 routes and the presentation of R5 `grammar_links` retire (UI and routes only).
  The `grammar_progress` table, its historical R5 rows and the `grammar_links` stored in each essay's
  `module_data` are **kept**: they stay readable, and R5 ids redirect through Grammar Lab provenance and aliases
  once that mapping exists. Retirement deletes no learner data.
- **Store (completion).** Reuse `grammar_progress` as is: `lesson_id` holds the Grammar Lab point id; R5 rows
  already written keep their R5 id. **Alias provenance without rewriting data:** the *read* joins a point to
  completions under its own id **or any id in its `aliases`**, and marks the row `via: 'alias'` in the response.
  Nothing is migrated or rewritten, so provenance stays in the row's own `lesson_id`.
- **Store (quiz result, decided: D-104 H-4; Try-it stays in Writing).** Migration **0023** adds `last_quiz_correct`,
  `last_quiz_total` (SMALLINT) and `last_quiz_at` (TIMESTAMPTZ) to `grammar_progress`, all NULL until a result is
  stored, "beside the existing completion state" (`completed_at` stays `NOT NULL`). On PostgreSQL a CHECK keeps the
  three together and `0 <= correct <= total`, `total >= 1`. A quiz result is written **with** the completion upsert, one statement in one route (one row per point per learner); a
  retake updates `last_quiz_*` and **keeps the first `completed_at`**; the stored number is client-reported, labelled so
  and never read as evidence (`EA:14`); a quiz abandoned before completion is not stored. **Try-it-yourself results belong
  to the Writing/evaluator record (`essays`) and are not duplicated here**: the quiz key ships in the content and is
  graded in the browser, so the stored number is client-reported (the same trade-off as the pre-D-103 Dictation; a
  future Grammar API that holds the published key may regrade). EA §1 Grammar: "canonical Concept ID, actual response
  and existing domain judgment"; "concept visit equals mastery" excluded (`EA:14`) [V].
- **Dependency (D-104 H-4).** A future Grammar API validates the published point before accepting progress; R5 is not
  revived as learner authority. The new route that accepts a point id must validate it against the
  **published** catalogue, whose serving API is held for its own architecture review (D-100 point 4).
  Until then this item is design-only; the completion route is named `PUT /api/learner/grammar/{point_id}/completion`
  (placeholder) and lands with that review or after it. The R5 `completeGrammar` route and the R5 table remain
  until the old-path retirement (`LEGACY_TOMBSTONES.md` entry on the human's instruction, D-100 point 5).
- **Migration.** 0023 (three nullable columns and the PostgreSQL CHECK, under lock_timeout).
- **Default/import.** Existing R5 completions count via aliases; no data moves. **Consumer.** Grammar Library
  ("recent/saved/suggested" needs the same table plus `library_items kind='grammar'` for "saved"), Grammar Concept.

### I12. Imported texts, kept texts, `url:` media, kept-language provenance

- **State.** (a) the learner's pasted texts (`imports[]`, <= 20 x 12 000 chars); (b) their bookmarks (`kept[]`);
  (c) `url:` media memberships (`mediaImports[]`); (d) why/where a word was kept (`keptLanguage{}`).
- **D3.** R9, D-s, C-s, Device table [V]. `upload:` media is already server-side (`media_id`); only the
  membership is device.
- **Class.** S for all four. **Stores.**
  - (a) and (c): `works` kind `imported` (register), source `{kind:'imported', id:<local import id>}`, payload
    `{form:'text'|'url', title, text|url}`; ids become `text:<work uuid>` / `url:<...>`. ADA §2:
    "account-owned content access record and versioned body/reference" (`:78`). A `url:` is a reference the app
    fetches through its safe-fetch path; the body is not stored.
  - (b): `library_items kind='reading'` (or `listening`), `relationship='kept'`, `source_id=text:<id>` - exactly what
    article bookmarks already do (`reader/source.js:108-114`); nothing new [V].
  - (d): `language_provenance` (migration 0005) with `provenance_repository.attach_occurrence` existing
    (`provenance_repository.py:125`) [V]; **no HTTP route exists**, so a route (`POST /api/library/vocabulary/{word}/provenance`,
    placeholder) is new. The saved word itself is already server (`saved_words`).
- **Migration.** None. **Default/import.** Empty; no bulk upload (H-6); a text the learner imports from now on is
  stored on the server (imports carry learner text, so the preview step
  is mandatory). `text:` ids change on import, so device references (continuation, kept) are remapped in the same
  operation.
- **Deletion.** A learner-imported text is private and deletable; deleting it marks dependent continuation
  "unavailable" (ADA `:178-180`).
- **Comprehension assessment (D-103.3).** Books and pasted texts are `N/A_BY_CONTRACT`: no Check Understanding
  record is ever created for a `book:` or `text:` source, so no storage is designed for one. The article contract
  (approved sets, `reading_attempts`) is unchanged. A source with no contract shows no Check entry that only
  reaches an unavailable state, a D7 rule; the server side is unchanged because `reading_attempts` is already keyed
  to a set and question (`models.py:1276-1330`) [V].
- **Consumers.** Import sheet, Discover, Content Detail, Search (media imports), Quick Sheet keep.

### I13. Review modes and limits

- **State.** New words per day, review limit per day, which recall modes are on (`newPerDay`, `limitPerDay`,
  `modes{}`; `recall-modes.js:46-64`).
- **D3.** S2 (Part 1) [V]: device `reviewSettings`. **D3 is inconsistent:** Part 3's device table says "old UI
  only (not read by /next)", but `/next` Settings reads and writes it (`settings/screen.js:186-191,333`) [V]. The
  Part 1 reading is correct.
- **Class.** S: a preference that shapes what the review scheduler shows, and a learner expects it on the next
  device. Per-language (`memory` is per owner+language).
- **Store.** Named columns on `user_language_profiles` (ADA §1: "Profile updates patch named supported fields",
  `:62-63`): `review_new_per_day SMALLINT NULL`, `review_limit_per_day SMALLINT NULL`, `review_modes JSON NULL`
  (`NULL` = default). Values clamped by the same bounds the client uses. They follow I1's pattern (`account_profile`
  `LANGUAGE_SETTINGS`, `stored=True`, allowed/validator from the registry).
  **D-103.1:** recall modes with no staging frame retire. The stored `review_modes` map therefore holds only the
  modes `/next` Review draws (`target`, `cloze`: `screens/review/model.js:152` [V per D3]); any other key is dropped
  on write and ignored on read, so a retired mode can never be stored or resurrected.
- **Migration.** 0019, own revision so it can be dropped from the batch. **API.** `/api/learner-profile` PATCH.
- **Consumer.** Settings Review tab, Review Session limits.

### I14. Profile/Progress metrics: a real metric or no metric (D-103.4, D-104 H-5)

- **State.** Streak, weekly done-count, activity counts; minutes, daily goal, achievements, trends, skill %, level/XP.
- **D3.** P3, T-s, Q3, `UI_BACKEND_GAPS` N-21/N-32 [V]: no backend measure; an unmeasured value must never render
  as 0 (D-103.4). `learner_summary` says growth is unavailable per domain (`learner_summary.py:47-55`).
- **Built in D4 (derived, no new table): a real streak.** D-104 H-5: **no streak table**; the streak is derived from
  **meaningful, timestamped server-side learning activity**. **Page visits do not count.** It is **not permanently
  limited** to Reading, Writing and Speaking: **every staging skill counts once it has equally valid server-side
  completed records**, using the domain records available after D4 and D7.
  1. **Definition.** A *day* is a calendar day in the learner's timezone on which at least one such record exists; the
     streak is consecutive days ending today or yesterday (the rule `GET /api/dashboard` already uses for writing,
     `app.py:2713-2725` [V], now cross-skill). Week = ISO week, Monday start. A new read `GET
     /api/learner-activity?tz=<IANA>&days=` computes it; the timezone is a validated per-request parameter (zoneinfo),
     not stored, and the server clock never decides a day boundary.
  2. **A registry, not a table.** Each skill contributes one *activity source*: a function that, for the scope, yields
     the timestamps of its valid completed records. The set grows as records become valid; **a source counts only
     when its record is completed, server-written and its timestamp survives** (below). At D4 the sources are
     `essays.created_at` (each submission; a revision on another day is another active day), `speaking_attempts.created_at`
     and `reading_attempts.created_at` [V]. D7 adds a source when a flow writes a qualifying record: for example a
     server-verified Dictation check (I18) once its timestamp is kept per event (see below), Shadowing rounds and
     vocabulary reviews once each keeps an event time rather than a last-update time, Grammar completions
     (`grammar_progress.completed_at`) and Reading Transfer/typed responses (`works` `response`, `created_at`).
  3. **What survives.** Listening, Dictation, Shadowing and review rows carry only a last-update time today
     (`listening_progress.updated_at`, `shadowing_progress.updated_at`, `saved_words.last_reviewed_at`, overwritten
     on the next write; `models.py:277-336`) [V], so a *past* day cannot be proved from them, and counting them by
     last-update would let a later write erase a day and falsely break a streak. Those skills therefore enter the streak
     **when their domain records keep a per-event timestamp** (a D7 change to the domain owner, not a streak table);
     until then their days are not counted, and the approval entry says so. This is the honest reading of "every
     staging skill with equally valid server-side completed activity".
  4. **Weekly done-count** = distinct active days this week against the persisted target of I3b. **Activity counts**:
     the existing `GET /api/learner-summary`, unchanged.
- **Hidden until a contract exists (no storage designed):** weekly minutes (shown only if duration is genuinely
  measured; nothing measures it, and client time is contextual, `EA:35-36`), the daily-goal ring and its minutes setting,
  achievements (`no_approved_policy`), trends, skill percentages, level/XP. The API returns these as absent and the
  client hides them; it never returns 0 for an unmeasured value (D3 wrong-data risk 2 is fixed in the read model, I8).
- **Migration.** None. **Consumers.** Profile (streak, week done-count), Today (streak card; the goal ring stays
  hidden), Progress (counts).

### I15. Orena history and coach notes (flag, do not decide)

- **State.** The Orena thread and coach notes (`orena.agent.v1:<owner>`).
- **D3.** O-st [V]: `AGENT_CONTRACT.md:383` "Conversation history and coach notes are device memory; the account
  store is out of scope until an architecture review under ORENA_ACCOUNT_DATA_ARCHITECTURE.md"; line 26 gives the
  device memory to the UI lane.
- **Class.** **D** by contract; **flag for the human (H-10):** this proposal *is* an architecture review under that
  document, so the condition on line 383 could be met. If reopened, the natural store is `works` kind
  `conversation` (I6) with source `{kind:'orena'}`. Reasons to leave it closed for now: the contract may be
  changed only by `codex/work` and only as its ownership table says (`AGENT_CONTRACT.md:28`); coach notes carry
  the privacy exit `preferences.agent_memory` and the address terms must never be stored (§5.6, §10) [V]; the
  Intelligence lane builds against contract v5 and is not to see it move (D-086). **Recommendation:** leave device
  until G lands, then reopen deliberately.

### I16. Wrong-data check on listening/shadowing progress; Shadowing read-back

- **Risk (D3 part 2, "Problems", 1).** `POST /api/listening/progress` and `/shadowing-progress` accept an asset of
  any language: a ZH asset stored under `language='en'` showed as EN Progress (`listening_api.py:586-625`)
  while `speech_api.py:128-130` rejects the analogous mismatch [V].
- **Proposed check (server, no schema).** Before saving, resolve the asset in the catalogue
  (`listening_catalog.catalog_lessons`, the resolver pattern of `collection_api.catalog_lesson_resolver`,
  `collection_api.py:62-83`) or in the learner's own media library for `upload:`/`url:` ids, read its
  `source_language`, and compare its language family to `current_language_code()`. Mismatch -> **422**
  `asset_language_mismatch`; unresolvable asset -> **404** `asset_not_found` (fail closed; never store a row for an
  asset nothing serves). The same helper covers both routes. `ListeningProgressIn` carries no language field, so
  the scope language is the only reference [V].
- **Existing bad rows.** Not deleted or migrated (learner-owned data is never rewritten by cleanup). Readers already
  filter by scope language; one wrong-language row like the bench probe is data noise, listed in the rehearsal as a
  pre-existing case.
- **Shadowing read-back.** `shadowing_progress` is stored and never read (S.r); the fix is D7 (`api.shadowingProgress`
  on open, as old `ui/speaking-workspace.js:622` does). No storage change.
- **Related, not storage:** a speaking attempt with `pronunciation: null` renders 0 (read-model fix in I8). The
  Dictation write path shares this check and adds server-side scoring (I18, D-103.2).

### I17. Presentation and device-only by design (not stored)

`orena.reader` (text size), `orena.stage` (transcript prefs), `orena.appearance`, `orena.next.search.recent.v1`,
`orena.speaking.keepRecent`, `sessionStorage orena.onboarding.step`, `orena.next.navOrigin/depth`, the take store
(`take-store.js`) and IndexedDB audio (ADA §2 "Microphone raw audio ... transient", `:87`), the offline
`reviewQueue[]` (unsent work that flushes to the server), unsent Dictation `answers{}` (a checked answer is
already `listening_progress.last_answer`), and `revisions{}` (server `essay_revisions` exist). All stay on the
device; D-101 "Persistence" makes none of them required.

### I18. Dictation: the server is authoritative for persisted evidence (D-103.2)

- **State.** The score stored for a checked Dictation segment: `best_accuracy_percent`, `best_exact`, the attempt
  count, the last answer.
- **D3.** D.a [V]: the browser grades (`capabilities/dictation-evaluator.js`: NFKC, quote and hyphen mapping,
  language-aware units, edit distance, `accuracy = round(100 * (1 - distance / max(expected, answer)))`) and
  `POST /api/listening/progress` stores the client's number. The PostgreSQL repository even replaces every field
  with the client's value, so a client can also lower a best (`specialized_repository.py:1297-1316`) [V]. Assess
  and store stay `MISSING` until this lands (D-103.2).
- **Class.** S, evidence. Deterministic, no AI.
- **Contract change (no new store).** On a checked write (`presentation == 'checked'` with a non-empty
  `last_answer`) the server:
  1. resolves the canonical line from `(asset_id, segment_id)` in the catalogue
     (`listening_catalog.catalog_lessons`, the `collection_api.catalog_lesson_resolver` pattern,
     `collection_api.py:62-83`) or the learner's own media library for `upload:`/`url:` ids; an unresolvable pair is
     **404 `asset_not_found`** and a language that does not match the scope is **422 `asset_language_mismatch`**
     (this is the I16 check, one shared helper);
  2. recomputes `accuracy_percent`, `exact` and unit counts with a Python port of
     `evaluateListeningReconstruction` (`writing_coach/dictation_evaluator.py`, new), with the same limits
     (2000 chars, 500 units) and the same errors mapped to 422 (`answer_empty`, `answer_too_large`,
     `evaluation_too_large`, `canonical_empty`);
  3. stores the best as follows: **if the stored row is `score_source = 'client'` (or absent), `best_accuracy_percent =
     computed` and `best_exact = computed.exact`** (the unverifiable client number is superseded, never kept by `max`);
     **afterwards (`server` row) `best = max(stored, computed)`**, `best_exact = stored or computed`; **the
     `best_*` fields sent by the client are ignored** (they stay in the request body for compatibility, so the
     frozen native client and the current UI keep working) and the response returns the server's values, which the
     UI shows in place of its own number once acknowledged (the browser score remains the instant feedback);
  4. sets `checked_attempt_count = max(stored, min(client, stored + 1))`: never lowered, at most +1 per write. It is
     a residual trust in the client (it can still claim up to +1 per write) that is not evidence of anything but
     activity. It is also not idempotent under a lost-response retry; that needs the operation identity ADA §4 (`:145-149`) reserves
     for a later package and is a hold, not a claim;
  5. writes `score_source = 'server'`.

  A `revealed` or `prompt` write changes no score.
- **Parity, the risk of a port.** The JS units use `\p{L}`, `\p{N}` and `Script=Han`; Python's `re` has no `\p`,
  so the port classifies with `unicodedata` (categories `L*`/`N*`) and explicit Han ranges [I]. Parity is proved by
  **one golden-vector file generated by running the JS module** (en/zh, apostrophes, hyphens, full-width forms,
  mixed script, punctuation-only, empty, oversize), committed under `tests/fixtures/`, consumed by a Python test
  and by an `.mjs` gate that re-runs the JS against the same file, so drift in either side fails CI.
- **Existing rows.** Historical numbers were client-reported. Migration 0020 adds
  `listening_progress.score_source VARCHAR(12) NOT NULL DEFAULT 'client'` (values `client|server`); no row is
  recomputed (only the last answer is kept, so the best cannot be re-derived) and none is deleted. The next
  verified check on a `client` row **supersedes** its best with the computed value (H-14 asks the human to
  confirm this, versus keeping the older number labelled). Read models may mark `client` rows as unverified.
- **Old-UI compatibility (P2-2).** The 404 `asset_not_found` and 422 `asset_language_mismatch` are a behaviour
  change for the old UI at `/`: a save for an asset outside the catalogue and outside the learner's own media now
  fails where it used to succeed. This is intended (fail closed: no row is stored for an asset nothing serves) and
  ends at the cutover. The rehearsal must confirm that `url:` and `upload:` ids of the learner's own media resolve,
  so the new UI's imported-media dictation is not refused.
- **Related.** Shadowing progress keeps its rules (D-103 does not change them) but takes the same language check.
- **Test-backend note.** The SQLite repository refuses listening progress ("requires the PostgreSQL runtime",
  `specialized_repository.py:855-856`) [V], so the route tests against the real repository run under
  `ORENA_TEST_POSTGRES_URL` and in the rehearsal; the evaluator port and the golden vectors are pure and run in CI.
- **Consumer.** Dictation (`screens/dictation/screen.js:389` sends; it reads the returned item), Progress
  History/Evidence (`dictation_best_match`).

### I19. Chinese evaluator refresh: retaining the previous review (D-103.7)

- **State.** When an old Chinese essay is reopened, one re-grade of exactly that submission, and the review it
  replaces kept as immutable history and audit evidence. No learner revision, no claim the learner rewrote it.
- **Affected pair (P2-5, P2-6): already in code.** `c2e4e63` made the identity per pair: `v27_affects(learning,
  support)` is `primary_subtag(learning) == 'zh' and primary_subtag(support) != 'zh'` after normalising case and
  `_`/`-` (`writing_review_identity.py:60-68`), and `contract_version_for` gives v2.7 to that pair and v2.6 to all
  others [V]. So D-103's literal rule holds: **any support language other than Chinese is affected, including a
  CJK one such as `ja`** ("not `zh`", not "non-CJK"); a variant tag such as `zh-CN` compares by its primary
  subtag. `same_review` needs **no change**: the fingerprint embeds the pair-effective contract version, so
  unaffected pairs match their v2.6 reviews again. Reviews written between `871e2b9` and `c2e4e63` under v2.7 for an
  unaffected pair (a window of hours on a development lane) do not match and would be re-earned on a normal
  resubmission; they are never touched by the refresh, which only runs for the affected pair. Test both.
- **Endpoint.** `POST /api/essays/{id}/review/refresh`, idempotent, no body. The exact contract:
  1. **Stored inputs only.** The essay's text, prompt and target level come from the stored row, and the learning
     and support languages from the **stored** review identity (`module_data.review`). The current profile's support
     language is never consulted and there is **no fallback to it** (`evaluate()` resolves the support language from
     the current profile at `app.py:917-932`; the warning at `writing_review_identity.py:24-27` is exactly this
     failure). `evaluate` is refactored to take explicit support language and target level, and the refresh passes
     them; a stored identity that lacks a resolvable support language is **not refreshed**.
  2. **Verify** the pair is affected and the recomputed fingerprint under the pair-effective contract differs from the
     stored one. If not affected or already current: return the stored review, `status: 'current'`, no provider work.
  3. **Provider only.** The refresh runs `evaluate` with fallback disabled (an explicit parameter, so the
     `ALLOW_FALLBACK` heuristic path, `app.py:1052-1072`, cannot run). Any result that is not from a real provider
     (evaluator `fallback-demo`, or a failure) is `status: 'unavailable'`, **writes nothing** and never overwrites a
     real review.
  4. **One transactional repository method, on both backends** (new):
     `refresh_essay_review(essay_id, expected_prior_fingerprint, new_review, new_identity)`. In one transaction it
     locks the essay row (PostgreSQL `SELECT ... FOR UPDATE`; SQLite `BEGIN IMMEDIATE`), re-checks that the stored
     fingerprint still equals `expected_prior_fingerprint` (otherwise returns `already_current` and discards the
     result), inserts the history snapshot, updates the review columns, and **merges** `module_data.review` by key
     (all other keys, such as `practice_context`, `grammar_links`, `prompt_ref`, are preserved). The other writer of
     `module_data`, `becoming_linguistics.py:152` (read-modify-write, then the whole-dict
     `update_essay_module_data`), must move to a key-level merge under the same lock, or a refresh and a linguistic
     cache write can erase each other; that change is part of this item.
  5. **Single-flight, honestly.** `_review_gate` is a process-local `threading.Lock` (`app.py:2409-2415`) and holds
     for the single uvicorn worker in `Dockerfile:34`, not across processes. The `UNIQUE (essay_id, prior_fingerprint)`
     and the fingerprint re-check under the row lock make the **write** idempotent across processes: a second
     process discards its result. It may still have paid for a second provider call. This proposal does not add a
     cross-process lock (holding a database transaction across a provider call is worse); the rehearsal asserts one
     history row, and "one provider call" only in a single process.
  A provider failure writes nothing and returns the stored review with `status: 'unavailable'` (retryable). No batch
  path exists.
- **Essays with no stored identity** (`identity_of_stored` returns `{}`) have an unverifiable pair; D-103 says the
  server "verifies the pair", so they are **not** refreshed (H-15).
- **Where the previous review is kept (chosen, with the alternative rejected).**
  - **Chosen: one new append-only table `essay_review_history`** (0021): `id`, `essay_id -> essays.id ON DELETE
    CASCADE`, `superseded_at`, `reason` (`evaluator_refresh`), `prior_fingerprint`, `prior_contract`,
    `replaced_by_fingerprint`, `review JSON NOT NULL` (the whole prior review: five dimension scores, overall, level
    estimate, evaluator, `summary_vi`, strengths, strength evidence, priorities, errors, and the stored
    `grammar_links`). `UNIQUE (essay_id, prior_fingerprint)`, `INDEX (essay_id, superseded_at)`.
  - **Parent scope by construction (delta review P2-4: the scope copies are dropped).** Revision 3 copied `user_id` and
    `language_code` from the essay. A copy can disagree with its parent, ADA §3 asks that a child verify its parent's
    scope, and a composite foreign key would need a new unique key on `essays`, which this proposal should not add. So
    the table has **no** `user_id` or `language_code`: every read is `GET /api/essays/{id}/review/history`, which loads
    the essay first through the scope-checked `get_essay`, then reads its history by `essay_id`. There is nothing to
    keep equal and nothing for a repository test to bind. The account-wide reads the copies would have served (a list of
    a learner's refreshes) are not needed by any consumer; if one appears it joins `essays`, whose
    `ix_essays_user_language_created` already serves the scope.
  - **Immutability (P2-4): a `BEFORE UPDATE` trigger raising an exception, in 0021, on PostgreSQL** (precedent: 0016
    makes the legacy reading archive read-only by trigger). **UPDATE only**: a `DELETE` trigger would block the
    `ON DELETE CASCADE` on essay or account deletion. A learner deleting an essay therefore also deletes its history;
    that is intended (the history is the learner's own record of that essay). The repository additionally exposes
    insert and read only (a test asserts it).
  - **SQLite (P2-3).** The hermetic backend needs the table too: `CREATE TABLE IF NOT EXISTS essay_review_history`
    in `SQLiteSpecializedLearningRepository.initialize()` with an integer `essay_id` (its `essays` table has integer
    ids and `module_data_json`) and the same unique key; no trigger (test backend only). This lets the I19 cases run
    in CI.
  - **Rejected: a list inside `essays.module_data`.** `update_essay_module_data` replaces the whole dict
    (`specialized_repository.py:884-886` SQLite, `:1478-1483` PostgreSQL) [V], so history could be erased by an
    unrelated write, and it cannot be unique per prior fingerprint.
  - It is the only new table; it reuses no `works` row because an evaluated review is evidence owned by `essays`
    (ADA §2 "Evaluations/attempts ... immutable attempt and evaluator version", `:85`), not learner work.
- **API for the audit read.** `GET /api/essays/{id}/review/history` (learner-scoped, read-only, newest first). No
  learner-facing UI is drawn for it (rule 43).
- **Effects to state.** Progress and `learner_summary` read the essay's *current* review, so an old essay's score can
  change once. `revision_delta` between a refreshed and an unrefreshed neighbour mixes evaluator contracts; the read
  model already refuses a trend across evaluator versions (`learner_summary.py:47-55`).
- **Deletion/export.** `essay_review_history` is keyed through its essay: removed with the essay (cascade) and, because the `users`
  row survives, with the account's `essays` that the D-055(b) workflow deletes explicitly (section 2.6). **Default.** Empty
  table.
- **Tests.** Section 9.

## 4. Existing accounts: defaults and import (one place)

| Item | Default for an existing account | Device import |
| --- | --- | --- |
| I1 declared_level | `''`; Welcome only for a language with no profile row (D-104 H-1) | none |
| I2 learning_language | `''` -> session default `en`; Welcome for a language with no profile row | none |
| I3 interface_language | `''` -> device/OS | none (device value seeds the first save) |
| I4, I6, I10, I12 | empty; device values stay readable where a compatibility path reads them | none (no bulk migration, D-104 H-6) |
| I5 drafts | empty | existing automatic per-piece send |
| I11 grammar | R5 completions count via aliases | none |
| I13 review settings | `NULL` = client defaults | the device value seeds the first save [I] |
| I3b weekly goal | `NULL` (not set) | none |
| I18 Dictation | existing rows `score_source='client'`, kept, superseded by the next verified check (H-14) | none |
| I19 Chinese review history | empty table; no essay is re-graded until reopened | none |

## 5. Migration plan (ordered)

Head today: `20260924_0016` (repo). Sandbox database is at `20260923_0014` (H2 section 3, `CURRENT_HANDOFF.md`);
the lane runtime is on PostgreSQL 17 [V per D3]. All revisions are additive, live in `migrations/proposed/` until
reviewed, rehearsed and authorized, then `git mv`'d to `versions/` one at a time and **applied one revision per
invocation** (section 5.1). No startup Alembic (D-002);
only `scripts/bootstrap_runtime_schema.py` applies them. None is added to `GATED_REVISIONS`
(`bootstrap_runtime_schema.py:62-65`; that set is for non-mechanical revisions like the 0016 cutover).

| Rev | File | Adds | Guard |
| --- | --- | --- | --- |
| 0017 | `20260930_0017_declared_level.py` | `user_language_profiles.declared_level` | H2 section 3 verbatim |
| 0018 | `20260930_0018_account_settings.py` | `users.learning_language`, `users.interface_language` (`NOT NULL DEFAULT ''`), `users.weekly_goal_days` (`SMALLINT NULL`), `users.settings_updated_at` (`TIMESTAMPTZ NULL`, the version token) | `users` is hot: lock_timeout matters most here; own operator step after a backup |
| 0019 | `20260930_0019_review_settings.py` | `user_language_profiles.review_new_per_day`, `review_limit_per_day`, `review_modes` (nullable) | - |
| 0020 | `20260930_0020_listening_score_source.py` | `listening_progress.score_source VARCHAR(12) NOT NULL DEFAULT 'client'` | `listening_progress` is written on every check; a constant default is metadata-only |
| 0021 | `20260930_0021_essay_review_history.py` | **new table** `essay_review_history` (I19): one FK to `essays` `ON DELETE CASCADE` (no scope copies), `UNIQUE (essay_id, prior_fingerprint)`, one index, PostgreSQL `BEFORE UPDATE` immutability trigger | `CREATE TABLE` locks no existing table |
| 0022 | `20260930_0022_library_items_place.py` (required, D-104 H-12) | `library_items.place JSON NULL`, `library_items.place_at TIMESTAMPTZ NULL`, partial index | `library_items` is written by keeps; nullable columns, no default |
| 0023 | `20260930_0023_grammar_quiz_result.py` (required, D-104 H-4) | `grammar_progress.last_quiz_correct/total/at` (nullable) + PostgreSQL CHECK `ck_grammar_progress_quiz` | - |

The files are in `migrations/proposed/` (not `versions/`), each with the review and gate in its docstring; the
`git mv` to `versions/` happens one revision at a time, in chain order, only after the recorded rehearsal and the
human's authorization (D-104 next steps 2 and 3). No `learning_days` table is proposed (D-104 H-5).

Rules for every revision:
- `upgrade()` and `downgrade()` first run `SET LOCAL lock_timeout = '5s'` **guarded by dialect**:
  `if op.get_context().dialect.name == "postgresql": op.execute("SET LOCAL lock_timeout = '5s'")` (`get_context`, not
  `get_bind`, so an offline SQL-rendering run works, as in `20260924_0015`). (H2 wrote it
  unguarded; the guard is added so a hermetic SQLite migration test does not fail. [V: 0017's text in
  `DECLARED_LEVEL_STORAGE.md:96-99`.])
- `op.add_column` with a constant `server_default` (metadata-only on PG 11+; runtime is PG 17). Nullable columns
  need no default. No backfill. No index, no CHECK (application validates against the registry, so `ja` needs no
  schema change).
- The migration chain runs in one transaction (`env.py`), so `SET LOCAL lock_timeout` also applies to every later
  revision in the same run; each file carries a one-line comment saying so (H2 review N2, P2-10). 0018 (`users`) is
  its own operator step after a fresh `runtime_backup.py` backup. PostgreSQL cases skip in CI, so the recorded
  rehearsal is the only PostgreSQL evidence and is attached to the approval.
- `downgrade()` drops columns (0021: the table and its trigger); its docstring says it drops learner data and exists for rehearsal only
  (ADA §6 `:227-228`: never down-migrate away learner data).
- ORM mirror in `models.py` with the same defaults; SQLite (CI only) gets the guarded `ALTER TABLE` in
  `SQLiteSpecializedLearningRepository.initialize()` (and, for `users`, in the auth repository [I]) and, for the new
  table, a `CREATE TABLE IF NOT EXISTS` there too (I19).
- `persistence/importer.py` is not changed: it must not reset these columns on re-import (H2 P2-3 [V]).
- Head-sensitive tests move to the new head in the same commit: `tests/test_adaptive_reading_schema.py`,
  `tests/test_reading_canonical_cutover_scripts.py`.
- **Sandbox precondition** (H2 P2-1): a runtime must reach `0016` by its authorized route before any of these;
  the human takes `scripts/runtime_backup.py` immediately before
  `python scripts/bootstrap_runtime_schema.py --upgrade --from <head> --confirm`.

Non-migration changes, in order of dependence: registry entries (`WORK_KINDS`: `annotation`,
`imported`; `MUTATION_DOMAINS` likewise); `GET /api/works` list; `PUT/GET /api/continue` (on `library_items`, I4),
`/api/annotations`; turn append; provenance route; profile settings; language endpoints; `since` on speech
attempts; listening language check and server-side Dictation scoring (`writing_coach/dictation_evaluator.py`);
`GET /api/learner-activity`; `POST /api/essays/{id}/review/refresh` and `GET .../review/history`;
pair-aware `effective_contract_version`; flag in `compose.yaml`.

### 5.1 Applying the revisions: one per invocation, 0018 alone after a backup (delta review P2-1)

`migrations/env.py` runs an `alembic` invocation in **one transaction** (`begin_transaction()`, lines 28, 39, 53), and
`SET LOCAL lock_timeout` and every `ACCESS EXCLUSIVE` lock last until it commits. Applying 0017 to 0023 with one
`--upgrade` would therefore keep 0018's lock on `users` (written on every sign-in) through 0022's index build on
`library_items` and 0023's CHECK validation on `grammar_progress`, so logins would queue for the whole run. So:
- Each revision is its **own** invocation of `bootstrap_runtime_schema.py --upgrade --from <rev> --to <rev> --confirm`
  (`--to` exists since `788a54e`; `--plan` lists what is pending). The rehearsal script applies them the same way and
  records the order.
- **0018 is applied alone, immediately after a fresh `scripts/runtime_backup.py` backup**, because `users` is the hot,
  account-critical table; 0017 and 0019 to 0023 follow, one invocation each, with the smoke test of login between 0018
  and the rest.
- The staging/lane runbook (D-102 point 7: backup, migration gate, smoke) says the same: it names the seven
  invocations in order and does not offer a single `--upgrade` to head for this set. Reviewed and authorized first,
  then applied; a failed revision (`lock_timeout` 55P03) leaves the database at the previous revision and is retried.

### 5.2 Maintenance window for :8000 (delta review P2-2)

`lock_timeout` bounds how long a revision *waits* for a lock, not how long a *granted* lock is held, and the rehearsal
with two or three rows proves the shape only. The window is therefore set from the **measured** hold times of
`scripts/rehearse_learner_records_schema.py --volume N` (the lead runs it at the size of :8000's tables and again at
the ~100,000-account target, N of about 100,000 and 3,000,000), which prints the seconds each revision's invocation
took (an upper bound of its lock hold). The rule, fixed now and filled with the measured numbers before the first
`git mv`:
- **Expected shape [I], to be replaced by the measurement:** 0017, 0018, 0019, 0020, 0022's column adds and 0021's
  `CREATE TABLE` are metadata-only (well under a second); 0022's `CREATE INDEX` scans `library_items` under a `SHARE`
  lock (blocks writes to it, and so keeps/pins, for the scan); 0023's `ADD CONSTRAINT ... CHECK` scans
  `grammar_progress` under `ACCESS EXCLUSIVE`.
- **Window = the slowest measured revision x 3, and never less than 15 minutes for the whole sequence including the
  backup and the smoke of login and the key learner E2E** (D-102 point 7). It is announced as a maintenance window; the
  human's migration gate, backup and smoke are unchanged.
- **If 0022 or 0023 measures over 10 s at the target volume,** that revision changes before promotion: `CREATE INDEX
  CONCURRENTLY` in an autocommit block for 0022, and `ADD CONSTRAINT ... NOT VALID` then a separate `VALIDATE
  CONSTRAINT` for 0023. That is a migration change and returns to the reviewer.
- Measured values (2026-09-30, `--volume 100000`, postgres:17, one invocation per revision): every revision held its locks under 0.33 s; slowest 0020 at 0.321 s (`LEARNER_RECORDS_D4.REHEARSAL.md` run 3). The window rule gives the 15-minute floor. A run at the full target volume (about 3M rows) is still worth recording before :8000.

## 6. Rehearsal (D-102 point 7; ADA §6 step 3)

Run by the lead with `scripts/rehearse_learner_records_schema.py <throwaway URL>`: it refuses a URL that is not clearly
throwaway (database name contains `rehears`, `throwaway` or `scratch`, local or rehearsal host, not the configured
runtime, not a runtime port) and a database that is not empty; builds the chain to `20260924_0016` from `versions/`;
seeds pre-existing rows; adds `migrations/proposed/` to `version_locations`; upgrades to head; probes every new column,
table, constraint, index and trigger; proves `lock_timeout` by holding a lock on `users` during a downgrade and an
upgrade (SQLSTATE 55P03 after about 5 s, nothing half-applied); runs up -> down to 0016 -> up and compares the two
schemas; races two writers on the history key; prints a PASS/FAIL table and exits non-zero on any FAIL. The steps below
state the intent it implements.

Hardening after the delta review (P2-2 and the probe list): `--volume N` seeds N rows in each hot table before the
migrations and the timing table is printed (5.2); revisions are applied one per invocation (5.1); the unknown-essay
probe asserts the foreign-key constraint name (`essay_review_history_essay_id_fkey`); the `library_items` place probe
exercises the conditional upsert of I4 (coalesced within 30 s unless a boundary, `version` and `updated_at`
untouched, a concurrent pin at version 1 still lands) instead of a plain UPDATE, and a further probe shows a JSON
`null` satisfies `place IS NOT NULL` (the hazard behind `none_as_null`, section 15); the schema after the downgrade is
compared with the schema captured at `20260924_0016` (all public tables); and old-code inserts naming none of the new
columns are probed for `users`, `user_language_profiles` and `listening_progress`. The 48 PASS in
`LEARNER_RECORDS_D4.REHEARSAL.md` is the run of revision 3 before these changes and before 0021 lost its scope columns; it
is re-run and re-recorded.

On a throwaway PostgreSQL 17 (`docker run` with a random port and no shared volume), never a shared runtime or
volume; heavy Docker work does not overlap another lane's (D-101 working rules). CI has no PostgreSQL service
(`.github/workflows/ci.yml` has no postgres) [V], so PG cases skip there via `ORENA_TEST_POSTGRES_URL`
(`tests/test_orena_work_persistence_postgres.py:1-15`); the rehearsal is a recorded local run, like
`scripts/rehearse_my_library_schema.py`. Sequence:
1. Create at `0016`, seed rows: profiles for two accounts x en/zh, `users` rows, `grammar_progress` R5 rows, works,
   `listening_progress` rows (one with a wrong-language asset, like the bench probe), essays with and without a
   stored review identity.
2. `upgrade` 0017 -> 0018 -> 0019 -> 0020 -> 0021 -> 0022 -> 0023, asserting per revision: pre-existing rows read the default, no lock
   wait beyond 5 s while a concurrent transaction holds a row lock on `users`/`user_language_profiles`.
3. `downgrade` to `0016`, then `upgrade` again (up/down/up), asserting the schema after the second upgrade equals the
   first. The ORM-equals-migrated-schema check (`tests/test_reading_evidence_schema_parity.py` pattern) belongs to the
   implementation, because the models change only after authorization (section 15).
4. Concurrency (the script covers the history key; the rest is the implementation's PostgreSQL tests): two PATCHes with one `expected_version` give one 200 and one 409; two
   account-setting writes with one `settings_updated_at` give one 200 and one 409; two turn appends at one head give
   one turn and one conflict; two simultaneous refreshes of one essay give one provider call, one history row and
   one `refreshed` (the other `current`); a forged Dictation `best_accuracy_percent` of 100 with a wrong answer is
   stored as the computed value.
5. Record the output in the review request file, not in this proposal.

## 7. Rollback

- **Before writes:** revert code, keep the additive columns (older code selects only mapped columns; server
  defaults cover its inserts).
- **After writes:** keep columns and rows; disable the writing feature or ship a reviewed forward fix. Never
  downgrade a runtime holding learner data. Never return to SQLite authority (ADA §6 `:225-229`).
- **Backbone flag:** `ORENA_ACCOUNT_BACKBONE=off` returns clients to device memory; account rows stay and are not
  served. Rows written while on are not lost; they reappear when it is turned on again. The room says "kept with
  your account" only for acknowledged saves.
- **Order of rollback for migrations:** newest revision first, on a throwaway copy only; a live runtime is restored
  from the backup taken before the upgrade, as an authorized incident operation (ADA `:227-229`).

## 8. Holds (AGENTS §7): what this proposal does not decide

- The canonical multi-user / account-sync architecture: no sync cursor, tombstone horizon, snapshot token or
  receipt compaction is designed; conflict handling is the per-record rule in section 2.4 only.
- Receipt compaction and cursors (I4 avoids them by storing position on `library_items`).
- The general multi-device sync protocol, the account-deletion runtime, the export format, and Orena
  conversation/history persistence (D-104 H-18 leaves these deferred).
- Native mobile (frozen). Platform Admin. Reading library breadth.
- Account deletion and re-registration runtime (D-055 preconditions); export format (none exists).
- `support_language` stored per language row; `ja` level list and the `HSK7-9` onboarding cell (H2 section 9).
- The Grammar Lab serving API (`/api/grammar/v1`, D-100 point 4) and its catalogue validation (I11).
- Orena history (I15) and a Reading Transfer *evidence* producer (I9).
- Whether a speech provider is added to the lane runtime (paid, human gate).
- The Writing target's HSK parity gap (`expression.js:186`), H2 P2-7.
- Idempotent Dictation attempt counts under a lost-response retry (ADA §4 operation identity, `:145-149`).
- The Chinese evaluator's own fix (prompt, benchmark, option 4): only the storage of a refresh is here.
- Writing Prompt Bank content and Admin (E); achievements, trends, skill %, level/XP and minutes (no contract).

## 9. Test plan

Rule: real repositories, real SQL, no fakes standing in for a store. Fakes are allowed only for the network
providers (AI, speech). The hermetic suite (`pytest -q test_app.py tests`, SQLite) runs everything that does not
need PostgreSQL; PG-only behaviour (receipts, stream lock, `speaking_attempts`, whose SQLite repository raises
"Durable Speaking attempts require the PostgreSQL runtime", `specialized_repository.py:873-874`) runs under
`ORENA_TEST_POSTGRES_URL` and in the rehearsal.

Per item (two accounts x en/zh; cross-account and cross-language reads return not-found; every mutation retried
with the same `operationId` returns the same result):
- **I1:** the H2 plan verbatim (`DECLARED_LEVEL_STORAGE.md` section 8), including the stub third language and
  the named `test_orena_shell.mjs:75` change, plus N1: PUT (unconditional) still works; a stale
  `expected_updated_at` -> 409; **create-while-created -> 409** on both backends (PostgreSQL `IntegrityError` mapped,
  SQLite plain insert or `DO NOTHING` with a rowcount check).
- **I2:** POST language then a fresh session (new cookie jar) for the same account reads the stored language;
  a session that already chose keeps its own; `''` yields `stored:false` and Welcome; two accounts do not leak.
- **I3, I3b (API level, delta review P2-5):** the response carries `settings_version` as an opaque string; a request
  that echoes it verbatim succeeds and returns a new one; a request that echoes a stale one (another writer moved it) gets
  409 `version_conflict` with the current string; a value that was parsed and re-serialised by a client (milliseconds only)
  is refused as stale; the client never sends a timestamp of its own that the server accepts.
- **I3, I3b (SQL level):** the `settings_updated_at` update: a `NULL` token writes and sets a server time; the same stale token ->
  409 with the current token; a client-supplied timestamp is ignored; two concurrent writers with one token give one
  200 and one 409; the three scalars share one token.
- **I13:** patch, read-back, clamp, PUT does not erase, stale `expected_updated_at` -> 409, `NULL` defaults.
- **I4 (JSON null versus SQL NULL, delta review P2-3):** a real-repository test writes a place, clears it and asserts
  the column is SQL `NULL` (`place IS NULL`, absent from `ix_library_items_place`), that `place` is never the JSON
  literal `null`, and does the same for `review_modes`; it fails if either column is declared without
  `none_as_null=True`.
- **I4:** PUT place then GET on a new session returns it; the list is ordered by `place_at` and bounded; a place write
  leaves `library_items.version` and `updated_at` unchanged and never makes a concurrent pin/note PATCH conflict; the
  30 s coalescing answers `coalesced` without an UPDATE; finished/cleared round-trip; `text:`/`url:`/`book:` ids
  round-trip; the `started` row of one item is one row (unique key); a source removed reads "unavailable".
- **I5:** the existing work-API and PG tests, plus register/target length if H-7(a).
- **I6:** append at head, replay returns the same turn, two appends at one head give one turn + 409, role
  alternation and `reply_to` enforced, ordinals contiguous (`uq_work_turn_ordinal`), cross-scope turn refused
  (`fk_work_turn_parent_scope`).
- **I8:** a spoken free-expression attempt with an empty reference and a synthetic `segment_id` saves and reads
  back; `null` pronunciation is not returned as 0 by Progress; a typed answer becomes a `response` work and never
  appears as a speaking attempt; scope mismatch -> 422.
- **I7:** `since` window returns only newer attempts; the summary equals the server's rows after a new context.
- **I9:** Finish saves a `response`; Progress evidence is unchanged (no score).
- **I10:** notes and highlights round-trip; concurrent add from two clients -> 409 -> union -> both present;
  over-bound payload refused.
- **I11:** completion under a Grammar Lab id; an R5 completion is returned for the aliased point with `via:alias`
  and nothing is rewritten; unknown/unpublished id refused; the quiz columns round-trip with the completion; the CHECK
  refuses `correct > total` and a partial result; Try-it writes nothing to `grammar_progress`.
- **I12:** import text -> `text:<uuid>` opens on a "new device"; kept mapping; provenance attach and read;
  deletion marks dependents unavailable.
- **I16:** listening/shadowing save with a ZH asset under an EN scope -> 422; unknown asset -> 404; valid -> 200;
  existing rows still listed.
- **I18:** the Python evaluator against the golden vectors (en/zh); a forged client `best_*` is ignored; a wrong
  answer with a client-claimed 100 stores the computed value; best is never lowered by a worse later answer; the
  count is never lowered and rises by at most 1 per write; `revealed` writes change no score; a `client` row is
  superseded by the first verified check; answer too long -> 422; canonical line unresolvable -> 404; the `.mjs`
  gate runs the JS evaluator on the same vectors.
- **I19 (history scope):** the history is only reachable through `GET /api/essays/{id}/review/history`, which refuses another
  account's or another language's essay (404) before reading; the table has no `user_id`/`language_code`, and a test asserts
  the repository exposes no method that reads history without an essay id.
- **I19 (additions):** a refresh after the learner changed their support language still uses the **stored** pair and
  stores under it; a refresh where the provider path yields `fallback-demo` (`ALLOW_FALLBACK` on) writes nothing and
  leaves the real review; two concurrent refreshes in one process give one history row; the row-lock method returns
  `already_current` when the fingerprint moved; a concurrent `becoming_linguistics` key write and a refresh both
  survive; the `BEFORE UPDATE` trigger rejects an UPDATE and permits the cascade delete; the SQLite history table
  passes the same repository cases; a `zh`+`ja` pair is affected, `zh`+`zh-CN` is not; a review written under v2.7
  for an unaffected pair is re-earned on resubmission only.
- **I19:** unaffected pair (`zh`+`zh`, `en`+`vi`, or an already-current review) -> `current`, no provider call;
  affected + stale -> one provider call, one history row equal to the prior review, essay updated, series and
  revision numbers unchanged; repeat -> `current`, no second call; provider failure -> no row, no essay change,
  `unavailable`; essay without stored identity -> not refreshed; another account's essay -> not found; the history
  repository has no update or delete method; essay deletion cascades; `module_data` keys other than `review` (for
  example `practice_context`, `grammar_links`, `prompt_ref`) survive a refresh.
- **I14:** no streak table exists; a page visit adds nothing; a source is counted only from a completed server-written
  record; streak over a hand-built set of essays and attempts across days and two timezones (a day boundary in
  `Asia/Ho_Chi_Minh` differs from UTC); a gap breaks it; the today-or-yesterday rule; weekly done-count against
  `weekly_goal_days`; nothing unmeasured is returned as 0 (fields absent).
- **Backbone off:** every new route answers `503 account_backbone_disabled` and clients fall back to device
  without claiming a save.
- **Deletion enumeration (P1-1):** a test lists every table and column this proposal touches and fails if one is
  missing from the D-055(b) enumeration: the **`users` columns to reset** (`learning_language`, `interface_language`,
  `weekly_goal_days`), and the rows to delete in `user_language_profiles`, `grammar_progress`, `listening_progress`,
  `shadowing_progress`, `speaking_attempts`, `essays` (and through them `essay_review_history`), `library_items` (incl. `place`),
  `saved_words`, and the incarnation-keyed `works`, `work_turns`, `mutation_receipts`, `change_records`,
  `language_provenance`. The D-055 gate test that no runtime path deletes stays.
- **Generic work route (P1-5):** `PUT /api/works/{id}` with kind `annotation`, `imported` is
  refused 422 `work_kind_invalid`; the dedicated routes accept them.
- **Browser (D-102 point 5, real backend, PostgreSQL):** EN and ZH, a new browser context reads back position,
  draft, conversation, note, level and language; results recorded in D3.

## 10. Human decisions: settled by D-104, and what remains

**Settled by D-104 (`DECISION_LOG.md:3604`):** H-18 (storage ownership; AGENTS §7 amended), H-12 (Design B, 0022
required), H-17 (`users.settings_updated_at`, conditional update, no blind last write), H-11 (backbone: lane after
rehearsal and apply, default off, :8000 after merge), H-6 (no bulk device migration), H-1 (Welcome once per language with
no profile row), H-5 (derived real streak, no table), H-4 (0023 quiz columns), H-14 (legacy Dictation numbers
superseded, never rewritten as verified), H-15 (old Chinese essays with an unproven pair are not refreshed), H-3 (Reading
Transfer stored as learner work, not evidence).

**Previously recommended and not contradicted by D-104 (this proposal keeps them):** H-2 interface language stored on
the account (`users.interface_language`, D-104 lists it); H-10 Orena history stays device memory (deferred by D-104
unless the Agent Contract changes); H-13 the two D3 corrections stand.

**Still open (product or design calls with no storage impact, or not answered by D-104):**
- **H-7** Writing register and target length: store in the draft and make the evaluator read them, or retire the
  controls.
- **H-8** Conversation coaching: part of the turn, or regenerated on demand (reviewer: regenerate).
- **H-9** Whether Progress > History lists typed Free Talk/Situation/React responses.
- **H-16** Whether the Profile weekly-goal bar is drawn when no target is set.
- **H-19 (new, from D-104 H-1)** What opens the level question for a language whose profile row exists with
  `declared_level = ''`. D-104 keys Welcome on a missing profile row only, while H2's proposal opened Welcome on a row
  without a level. **Proposed answer (the reviewer's recommendation, for the human to accept or change; not decided
  here):** keep the literal rule for entry routing (a missing row opens setup, nothing is replayed); verify that the
  onboarding flow writes the profile row only at its final step, or only after the level answer (a `GET` does not create
  a row, but any PATCH or PUT of another field does, so an earlier step or an abandoned onboarding can leave
  `declared_level = ''` for good); and ask for a level for an existing row with `''` through a **non-blocking,
  dismissible prompt** on Profile or Today, not a forced route. A forced route would need a stored "dismissed" marker,
  which is another persistence decision this proposal does not have and should not invent. `entryRoute` and Today treat
  `''` as "not declared".
- **H-20 (new, from D-104 H-4)** Whether a grammar quiz result is stored only when the learner completes the point.
  **Proposed answer (the reviewer's recommendation; not decided here): accept this proposal's reading,** because
  `completed_at` is the owner table's `NOT NULL` completion fact and relaxing it would change what a `grammar_progress`
  row means for R5 history and the alias reads; a quiz abandoned before completion is not a result. Conditions, now in
  I11 and section 9: (a) the completion write and the quiz fields are one upsert in one route; (b) a retake updates
  `last_quiz_*` and keeps the first `completed_at`; (c) the number is browser-graded, labelled client-reported and never
  read as evidence (`EA:14`); (d) the future route validates the published point id before accepting anything (D-104).

## 11. Consumers: which D7 change uses which item

| D7 change | Items |
| --- | --- |
| Welcome: languages + level, `entryRoute`, bootstrap `stored` | I1, I2 |
| Settings: interface language, review tab, target language | I2, I3, I13 |
| Today / Discover / Content Detail / Practice Hub / My Library "continue", Reading Complete | I4, I10 |
| Reader save/restore, Listening Workspace place | I4, I10, I16 |
| Writing draft (kept with account), register/length | I5 |
| Conversation restore | I6 |
| Speaking Summary, Attempt History, Compare, Shadowing read-back | I7, I16 (reads) |
| Free Talk / Situation / React save | I8 |
| Reading Transfer Finish | I9 |
| Quick Sheet notes and highlights | I10 |
| Grammar Library / Concept progress | I11 |
| Import sheet, `url:`/`upload:` open in Listening | I12 |
| Profile / Today / Progress: streak, week done-count, goal target | I14, I3b |
| Dictation shows the server's acknowledged score | I18, I16 |
| Writing review: reopening an old Chinese essay | I19 |
| Writing Setup prompt choice (records which prompt a piece answered) | I5 |

## 12. Review response (`LEARNER_RECORDS_D4.REVIEW.md`, REQUEST CHANGES)

_Revision 2 wording. Where D-104 later chose differently (I4 Design A is dropped, the arrival-order exception is withdrawn, the device import is dropped), section 14 states the final position._

| Finding | Resolution |
| --- | --- |
| P1-1 deletion/incarnation | Section 2.6 rewritten: the `users` row survives (RESTRICT); incarnation-keyed rows need explicit deletion because the kept incarnation row's cascade does not fire; account-keyed rows and the new `users` columns are deleted or **reset** by the D-055(b) workflow. I2/I3/I3b corrected; the section 9 enumeration test lists them. |
| P1-2 receipt growth | I4 gives Design A (server-enforced coalescing: no-op under 60 s unless a boundary, 200/day cap, volume estimate about 0.5 M rows/day per table, 4 M ceiling) and Design B (`library_items` place columns, migration 0022) as H-12. **Recommendation: B.** Not chosen silently; I4 is not approved until H-12. |
| P1-3 refresh contract | I19 specifies: stored pair, no current-profile fallback; provider-only (fallback disabled, `fallback-demo` never overwrites); one transactional `refresh_essay_review` on both backends with a row lock and fingerprint re-check; the `module_data` writer at `becoming_linguistics.py:152` moves to a locked key merge; single-flight limit stated (process-local gate; write idempotent, second provider call possible across processes). |
| P1-4 account scalars | Section 2.4: arrival-order last write, server-ordered, no token, with its consequence, as a recorded exception to ADA §1. "Same expected-version rule" removed from I3/I3b. H-17. |
| P1-5 AGENTS §7 / generic PUT / `users` | Section 13 requests the amendment and the `users` decision (H-18). The generic `PUT /api/works/{id}` refuses the new kinds; dedicated routes only (test added). |
| P2-1 N1 | Copied into I1 and the test plan (interface, PG and SQLite creation race, create-while-created). |
| P2-2 Dictation | I18: a `client` row's best := computed, then `max`; count residual stated; old-UI 404/422 change stated and checked in the rehearsal. |
| P2-3 SQLite table | `CREATE TABLE IF NOT EXISTS` in `initialize()` (I19, section 5). |
| P2-4 trigger | `BEFORE UPDATE` only, in 0021 (I19); learner deleting an essay deletes its history, intended. |
| P2-5 pair predicate | I19: primary subtag, literal `support != zh` (CJK non-zh included), the code already in `v27_affects`. |
| P2-6 same_review | Already resolved by `c2e4e63` (per-pair effective contract in the fingerprint); no comparator change; window of v2.7-for-all reviews noted and tested. |
| P2-7 deleted terminal | I4 Design A and I10: clear is a payload flag, never lifecycle `deleted`. |
| P2-8 payload size | I10: 80 x 400 + 120 x 600, about 104 KB worst case. |
| P2-9 language seeding | I2: read only when the session has none, then written into the session; legacy mode stated. |
| P2-10 migration mechanics | Section 5: lock_timeout comment per file, 0018 its own step after backup, rehearsal record attached. |
| P2-11 streak | Recorded: `essays.created_at` is per submission, so each revision day counts as an active day. |
| P2-12 export | Unchanged: not decided. |

## 13. Amendments and decisions (all decided by D-104)

1. **AGENTS §7 (H-18): amended by D-104.** These learner-owned records live on the server: drafts, conversations,
   continuation/place, notes, highlights and annotations, learner-imported private content, and the provenance needed
   to keep where learner content and actions came from. Still deferred: the general multi-device sync protocol, receipt
   compaction, the account-deletion runtime, the export format, and Orena conversation/history persistence (unless the
   Agent Contract changes it).
2. **Storage ownership (H-18).** `users`: `learning_language`, `interface_language`, `weekly_goal_days`,
   `settings_updated_at`. `user_language_profiles`: `declared_level`, review settings, and settings that belong to one
   learning language. **There is no generic account-settings table.**
3. **Generic work route.** `PUT /api/works/{id}` refuses the kinds added by this proposal (`annotation`, `imported`);
   they are reachable only through their dedicated routes, which define deterministic ids, payload bounds and, for
   turns, the role-alternation and `reply_to` rules copied from `restoreConversation`. (`continuation` is no longer a
   work kind: I4 is on `library_items`.) The pre-existing kinds keep their behaviour.

## 14. D-104 changes (revision 2 -> 3)

| Area | Revision 2 | Revision 3 (D-104) |
| --- | --- | --- |
| Storage ownership (H-18) | `users` placement was a request | Decided: `users` = the four account settings; `user_language_profiles` = declared level, review settings, per-language settings; no settings table |
| Continuation (H-12) | Design A (`works`, coalescing) or Design B, recommended B | **Design B only**; migration 0022 required; the `works` continuation design, its coalescing and volume section are removed |
| Account scalars (H-17) | Arrival-order last write as a recorded exception | **Withdrawn.** `users.settings_updated_at` (0018), server-owned expected-version update, 409 on stale, never a client timestamp |
| Backbone (H-11) | Recommended on for the lane runtime | On the lane only **after** the rehearsal and applying the migrations; default off; :8000 after merge, backup, gate, smoke |
| Device data (H-6) | Optional explicit import (recommended none) | **No bulk migration** and no import flow; legacy values stay readable through existing compatibility paths; new state goes to the server |
| Welcome (H-1) | Everyone sees Welcome once per language | Setup once per language **whose profile row does not exist**, without replaying onboarding (see H-19) |
| Streak (H-5) | Options (a)/(b)/(c); (a) three immutable sources recommended | **Real streak derived from server records; no table; every staging skill counts once it has valid completed records with surviving timestamps**; page visits never count |
| Quiz (H-4) | Recommended completion only | **Stored** (0023), beside completion; Try-it stays in Writing; a future Grammar API validates the published point |
| H-14, H-15, H-3 | Recommended | Approved as recommended |
| Migrations | Numbered and described | Written as real revision files `20260930_0017`-`0023` in `migrations/proposed/`; rehearsal script written |

**Open by this revision, not decided by D-104:** H-19 (what asks for the level when a profile row exists with an empty
level) and H-20 (quiz stored only with completion). I took the literal D-104 reading in both cases; the reviewer's
recommendations are recorded in section 10 as **proposed answers for the human**, not as decisions.

## 15. Model and code changes the implementation makes after authorization

None of these is in this change: the ORM models and application code stay as they are so that runtimes whose schema is
at `20260924_0016` keep working. After the human authorizes the migrations (and only then):
- `writing_coach/persistence/models.py`: `User` (4 columns), `UserLanguageProfile` (1 + 3), `ListeningProgress`
  (`score_source`), `LibraryItem` (`place`, `place_at`, the partial index), `GrammarProgress` (3 columns **and the CHECK
  `ck_grammar_progress_quiz` declared in the ORM `__table_args__`**, so the PostgreSQL schema-parity test
  (`tests/test_reading_evidence_schema_parity.py` pattern) passes; a fresh `create_all` can create it, while the SQLite
  `initialize()` `ALTER` path cannot add a CHECK to an existing table, so there it is a repository invariant), and a new
  `EssayReviewHistory` (no scope columns); SQLite `initialize()` mirrors (guarded `ALTER TABLE`, and
  `CREATE TABLE IF NOT EXISTS essay_review_history`). Head-sensitive tests move to `20260930_0023`
  (`tests/test_adaptive_reading_schema.py`, `tests/test_reading_canonical_cutover_scripts.py`).
- **JSON columns (delta review P2-3):** `LibraryItem.place` and `UserLanguageProfile.review_modes` are declared
  `JSON(none_as_null=True)`. A SQLAlchemy `JSON` column persists Python `None` as the JSON literal `null`, which satisfies
  `place IS NOT NULL` and would enter the partial index (the rehearsal shows the hazard on raw SQL); with
  `none_as_null=True` `None` is SQL `NULL`. A real-repository test writes and clears a place and asserts SQL `NULL`
  (section 9). `EssayReviewHistory.review` is `NOT NULL` and never `None`.
- `account_profile.py` / `becoming_memory.py`: `declared_level` and the review settings `stored=True`; the H2 conditional
  write with `expected_updated_at` and its creation-race handling (N1); an account-level settings path on `users` with
  the `settings_updated_at` conditional update, serving the token as the opaque string `settings_version` and never
  parsing a client's; `interface_language` moves to `users`.
- `core/platform_api.py`, `auth_support.py`: learning-language seeding into the session and `language.stored` on
  bootstrap.
- `library_api.py` and the library repository: `PUT/GET /api/continue` writing `place`/`place_at` without touching
  `version` or `updated_at`.
- `work_contract.py`, `work_api.py`, `work_repository.py`: kinds `annotation` and `imported`, dedicated routes, the
  generic route refusing them, `GET /api/works` (bounded list), turn append, the provenance route.
- `listening_api.py` and the specialized repository: language and asset check, server-side Dictation scoring
  (`writing_coach/dictation_evaluator.py`, golden vectors), `score_source`.
- `app.py`, `writing_review_identity.py`, the specialized repository: the refresh contract of I19
  (`refresh_essay_review`, row lock, provider-only `evaluate`, the `becoming_linguistics` key-level merge); the history
  read is by essay id only, after the scope-checked essay load.
- `speech_api.py`: `since` on the attempts list; the grammar progress route (when the Grammar API exists);
  `GET /api/learner-activity`; `compose.yaml` passes `ORENA_ACCOUNT_BACKBONE` with default `off`.
- Front end (D7): the consumers in section 11.

## 16. Delta-review response (`LEARNER_RECORDS_D4.REVIEW.md`, "Delta review of revision 3", APPROVE with six P2s)

| Finding | Resolution |
| --- | --- |
| P2-1 one transaction, locks accumulate | Section 5.1 and `migrations/proposed/README.md`: each revision is its own `bootstrap_runtime_schema.py --upgrade --from <rev> --to <rev>` invocation; 0018 alone after a fresh backup; the staging/lane runbook says the same; the rehearsal applies them one by one |
| P2-2 rehearsal proves shape, not scale | Rehearsal script `--volume N` and a per-revision timing table; section 5.2 fixes the maintenance-window rule from the measured numbers (pending the lead's run) and the `CONCURRENTLY` / `NOT VALID` fallback |
| P2-3 JSON null vs SQL NULL | Section 15: `place` and `review_modes` declared `JSON(none_as_null=True)`; section 9: a real-repository test of write, clear and index membership; the rehearsal shows the hazard on raw SQL |
| P2-4 child scope on the history table | Chosen: **drop `user_id` and `language_code`** (migration 0021 edited, rehearsal updated). Justification in I19: a copy can disagree with its parent, a composite FK needs a new key on `essays`, every read already goes through the scope-checked essay, and no consumer needs an account-wide history list |
| P2-5 opaque settings token | Section 2.4: served as the opaque string `settings_version`, server-set, echoed verbatim, never parsed; section 9: API-level stale-token tests |
| P2-6 drafting | Section 5 uses `op.get_context()`; section 15: the ORM declares the 0023 CHECK, SQLite `initialize()` cannot add it |
| Probes | FK constraint name asserted; the place probe runs the conditional upsert of I4 (coalescing, version and `updated_at` untouched, pin unaffected); the downgrade schema is compared with the schema captured at 0016; old-code inserts into `users` and `user_language_profiles`; a JSON-null hazard probe |
| H-19, H-20 | Section 10 records the reviewer's recommendations as **proposed answers for the human**; nothing is decided here |

## 17. Corrections recorded after the implementation review (2026-09-30, `LEARNER_RECORDS_D4_IMPLEMENTATION_REVIEW.md`)

The migrations 0017-0023 are applied revisions in `migrations/versions/`; their files are not edited. Where a docstring
there still reads "PROPOSAL ... lives in `migrations/proposed/`" or names review modes `target`/`cloze`, **this section
is the correction**: the files are the applied revisions, and the modes are `typing`/`cloze`/`dictation` (below).

Deviations from the sections above, accepted by the review and by the human where noted:

- **I4 place payload** is `{index, total, within, finished, cleared, title, intent, segment, context}`; `segment`
  (at most 255) and `context` (at most 240) are bounded strings the Reader and the shelf need to restore a position. The
  request model refuses any other key.
- **I4 saved-ness.** A row that exists only to hold a place (a `started` row that is not a word, not marked, not filed,
  no note) is never returned by the library lookup and never counts as a bookmark; where several rows name one source the
  `kept` row comes first. Forgetting a marked row that also holds a place clears the mark and keeps the place. Consumers
  read saved-ness as the `kept` relationship.
- **I6 turn content.** `work_turns.content` holds the turn as JSON `{id, text, origin, reply_to, meaning, support}`; the
  order and role stay in the constrained columns. Coaching is not stored (H-8 stays open).
- **I13 modes.** The canonical keys are `typing`, `cloze`, `dictation` (D-104 follow-up, `a4390b5`); an unknown key or a
  non-boolean is refused with 400 `invalid_value`, not dropped. Stored `review_modes` replaces the map wholesale (the
  client always sends all three).
- **I1 levels.** `HSK7-9` is one band in the registry and one cell after HSK 6.
- **I12 deletion.** Deleting a private import commits a tombstone without title, text or link, and a deleted work is not
  served by `GET /api/works/{id}`.
- **I2 / P2-3.** An account that never chose a language costs one settings lookup per session (a session flag), not one
  per request.
- **Profile token.** The profile row's version is a microsecond server-clock ISO string (opaque to clients), not a
  one-second stamp.
- **Authentication-disabled development.** The one local account (`legacy`) has its `users` row created by the first
  settings write; any other account without a row stays 503 `account_settings_unavailable`.
- **Dictation first write.** The row is created (`INSERT ... ON CONFLICT DO NOTHING`) and then locked, so two first checks
  of a segment both succeed.

Held for the human (not decided by an agent): per-account caps for `started` place rows, responses, annotations and
conversations, and a compaction owner for the receipt stream (P2-4; the only bounds the proposal states are the 20
imports, the annotation sizes and the 24-turn conversation, which are enforced).

Deployment. Code and migrations 0017-0023 are one deployment unit: the ORM selects the new columns, so this code on a
database still at `20260924_0016` fails at sign-in. Order: backup, 0017 to 0023 one invocation each (0018 alone), then
the code. The PostgreSQL-only proofs (settings token race, turn and dictation races, the history trigger, ORM/migration
parity, `none_as_null`) run only with `ORENA_TEST_POSTGRES_URL`; CI has no PostgreSQL service, so they are local
execution, not CI evidence, until a PostgreSQL job is added.
