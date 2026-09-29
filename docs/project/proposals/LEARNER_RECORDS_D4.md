# Proposal (D-101 D4): the learner records D3 found missing on the server

Status: **PROPOSED, revision 2** (2026-09-30, `codex/work` at `c2e4e63`), answering the independent review
`LEARNER_RECORDS_D4.REVIEW.md` (REQUEST CHANGES; P1-1..P1-5, P2-1..P2-12; the mapping is section 12). Document only: no code,
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

Consequence: the proposal needs **five additive migrations and one conditional one**, and **one new table**
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
| I3b | Weekly goal (days per week) | S | `users.weekly_goal_days` | column | 0018 | Profile weekly-goal bar |
| I4 | Reading/listening position and completion ("continue") | S (H-12) | **recommended:** `library_items` (`started`) + `place` columns; alternative: `works` kind `continuation` with server coalescing | columns (recommended) / none | 0022 (conditional on H-12) / none | Today, Discover, Content Detail, Practice Hub, My Library, Reading Complete |
| I5 | Writing drafts (+ register, target length) | S | `works` kind `draft` (exists) | none | none (flag on) | Writing |
| I6 | Conversation records | S | `works` kind `conversation` + `work_turns` | none | none (code + flag) | Conversation |
| I7 | Speaking Summary | derived | `speaking_attempts` + `works` `response` reads | none | none | Speaking Summary |
| I8 | Free Talk / Situation / React results | S | audio-free `speaking_attempts` when spoken; `works` `response` when typed | none | none | Free Talk, Situation, React |
| I9 | Reading Transfer results | S (H) | `works` kind `response` (not evidence) | none | none | Reading Transfer, Reading Complete |
| I10 | Sentence notes and highlights | S | `works` kind `annotation` | none | none | Reader, Quick Sheet, Reading Complete |
| I11 | Grammar progress per Grammar Lab point | S | `grammar_progress` (+ optional quiz columns) | columns (H) | 0023 (conditional) | Grammar Library, Grammar Concept |
| I12 | Imported texts, kept texts, `url:` media, kept-language provenance | S | `works` kind `imported`; `library_items`; `language_provenance` | none | none | Import, Discover, Content Detail, Quick Sheet |
| I13 | Review modes and limits | S | `user_language_profiles` named columns | columns | 0019 | Settings Review tab, Review Session |
| I14 | Profile/Progress metrics: real streak, weekly-goal days, activity counts; the rest hidden | derived (H for the streak policy) | derived read over existing rows (+ I3b) | none (option: 1 small table, H-5) | none | Profile, Today, Progress |
| I15 | Orena history and coach notes | D (flag) | device, per AGENT_CONTRACT:383 | none | none | Orena |
| I16 | Listening/shadowing progress language check; Shadowing read-back | S (fix) | `listening_progress`, `shadowing_progress` (exist) | none | none | Listening, Dictation, Shadowing |
| I17 | Theme, text size, transcript prefs, search recents, step/nav state | P | device | none | none | - |
| I18 | Dictation: server recomputes the score (D-103.2) | S | `listening_progress` (exists) + `score_source` | column | 0020 | Dictation |
| I19 | Chinese evaluator refresh: previous review kept as immutable history (D-103.7) | S | `essays` (current review) + new `essay_review_history` | **new table** | 0021 | Writing review (reopen an old essay) |

New tables: **one** (`essay_review_history`, I19). New columns: 0017: 1; 0018: 3; 0019: 3 named review
columns; 0020: 1; 0022 (conditional, I4 Design B): 2; 0023 (conditional, I11): up to 3.

## 2. Cross-cutting design

**2.1 Activate the backbone (recommended; a human gate, not a migration).** Items I4-I6, I8-I10, I12 need
`ORENA_ACCOUNT_BACKBONE=on`. Steps: the lane runtime :8021 sets it (lane decision, sandbox-class per D-054);
`compose.yaml` passes `ORENA_ACCOUNT_BACKBONE: ${ORENA_ACCOUNT_BACKBONE:-off}` (a config diff, default stays off);
:8000 sets it after the merge under the D-102 point 7 gate, after backup and smoke. Every client already asks
`GET /api/account-backbone` first and falls back to device when `disabled` (`draft-sync.js`;
`infrastructure/api.js:485`) [V]. The room says "kept with your account" only for a server-acknowledged save, so
turning the flag off later degrades to device honestly.

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
  re-PUTs (a client action the learner did not have to resolve, not a server merge of prose).
- **Profile row fields (`user_language_profiles`: declared level, review settings):** `expected_updated_at`, the H2
  conditional write (I1, N1).
- **Account scalars on `users` (learning language, interface language, weekly goal): arrival-order last write.**
  `users` has no version or `updated_at` column (`models.py:32-42`) [V], and the H2 review did not authorise an
  integer version column (H2 review P2-4: it belongs to the canonical account architecture). So there is no
  token and no 409: the request the server commits last wins, ordered by the database transaction, never by a
  client clock. **Consequence:** two devices changing the same scalar within moments silently keep the later one; a
  device that was offline and writes an old choice later overwrites a newer one. For single scalars a learner
  can see and re-set, this is judged acceptable, and it is a **recorded exception to ADA §1 `:62-63`** ("expected
  profile version"), for the human to accept (H-17). If the human wants a token, the cost is one column
  (`users.settings_updated_at`) added to 0018 and the expected-version rule for these three fields.
- **Positions (I4):** see I4; a position is single-valued and the newest arrival wins.
Nothing here defines cross-device sync, cursors, tombstone horizons or receipt compaction (AGENTS §7, ADA §5).

**2.5 Device import is a human decision.** ADA §6 step 6 (`:216-219`) [V] allows only an *explicit learner
import with preview, per-item validation, deterministic operation ids, and originals kept until acknowledged*;
D-002 forbids startup or hidden import. Precedent: `draft-sync.js` already sends a device draft when the server
holds none (automatic, per piece) [V]. The proposal's default is **no import** for every item except drafts
(existing behaviour); a single explicit "Bring this device's work into your account" action for I4, I6, I10,
I12 is offered as human decision H-6 (section 8). It is never done at startup.

**2.6 Deletion, incarnation and export (all items) - corrected by review P1-1.** There are two kinds of row and
they behave differently, because the `users` row **survives** account deletion: `account_incarnations.user_id ->
users ON DELETE RESTRICT` and the deletion journal anchor on it, and the barrier is kept for the life of the
deployment (ADA §1 `:41-44`; D-055) [V].
- **Incarnation-keyed rows** (`works`, `work_turns`, `mutation_receipts`, `change_records`,
  `language_provenance`): the cascade hangs off the `account_incarnations` row, which is *kept* as the barrier, so
  it does **not** fire. The D-055(b) workflow must delete these rows explicitly.
- **Account-keyed rows** (owner tables keyed by `users.id`, which a re-registered account with a new incarnation
  would otherwise read): `user_language_profiles` (declared level, review settings, goal, style, support language),
  `grammar_progress`, `listening_progress`, `shadowing_progress`, `speaking_attempts`, `essays` (+ `essay_revisions`,
  `essay_review_history`), `library_items`, `saved_words`. The workflow must delete these.
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
- **Migration.** `20260929_0017_declared_level` chained on `20260924_0016`; `SET LOCAL lock_timeout = '5s'`;
  add column; downgrade drops it (rehearsal only). Written in `migrations/proposed/`, `git mv` after review,
  rehearsal and authorization. Full design: `DECLARED_LEVEL_STORAGE.md` sections 1-9.
- **Existing accounts.** Default `''`: everyone sees Welcome once per learning language (H2 section 5.2 option A);
  the backfill from evidence is rejected. Extended to I2 in H-1.
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
  column (arrival-order last write, section 2.4 and H-17). Seeding point: `session/bootstrap`
  (`auth_support.py:376-401`) and the middleware read `request.session.get("language")`; when absent and the
  column is non-empty, use it [I: exact seeding site to be verified]. **No per-request database read (P2-9):** the
  stored value is read only when the session has no language, and is then written into the session, so every
  later request reads the cookie as today (the middleware runs on every request, `auth_support.py:409-455`).
  In non-authenticated (`legacy`) mode there is no `users` row: nothing is stored or read, and the session and the
  default behave as today.
- **API.** Existing `POST /api/platform/language` (extended, same body) and `GET /api/session/bootstrap`, which
  gains `language.stored: bool` (additive, so the entry rule can tell "never chosen" from the default).
- **Migration.** 0018 (with I3). Default `''` for all accounts; no backfill (a guess from `user_language_profiles`
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
  arrival-order last write (section 2.4, H-17); no expected version. Deletion: reset on the `users` row.
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
  (arrival-order last write like I3, section 2.4; deletion: reset on the `users` row). **Default.** `NULL`: Profile shows the count of active days without a target
  (D7/design decision whether the bar is drawn; not decided here). **Deletion.** Column on the account row.

### I4. Reading and listening position and completion (decision H-12, both designs given)

- **State.** Per content item and learning language: where the learner is (paragraph/segment index of total,
  furthest percent, chapter), when last, and whether they finished (Reading Complete's "Finished").
- **D3.** Reading R4/R5/K3 (MISSING store/return), Listening L1.s/L1.r, Navigation N-st/N-rt [V]. Device key
  `orena.encounters.v1:<owner>:<lang>` `.continuation[]`, up to 20 (`product/memory.js:49-50,276`; `readPlace` :26-37).
- **Class.** S. **Not evidence:** EA §1 "Continue: work/source reference and actual lifecycle; excluded claim:
  unfinished thread is a recommendation backed by mastery" (`EA:16`), and "reading time alone proves understanding"
  (`EA:11`) [V]. A finished flag is a continuation marker only.
- **Why this is the one item that needs a real decision (review P1-2).** It is the highest-frequency learner write.
  On the backbone every commit writes a `mutation_receipts` row and a `change_records` row and takes the per-account
  stream lock (`work_repository.py:87-`) [V]; receipt compaction is unspecified and reserved (ADA `:199-203`). A
  client throttle cannot be enforced against the old UI or the frozen native client. Two designs follow.

**Design A - `works` kind `continuation` with server-enforced coalescing.** One work per content id (deterministic
id, drafts pattern), payload `{title, intent, place, finished, cleared, at}`; ADA §2's own row ("Continue | account
work-derived index", `:84`).
- *Coalescing, enforced in the route, not the client.* `PUT /api/continue/{content_id}` first reads the work. It
  **no-ops (200 `status:'coalesced'`, no receipt, no change record, no stream lock)** when the place is unchanged,
  or when the last commit is under 60 s old and the write is not a boundary. A **boundary** always commits: first
  write for the item, the `finished` transition, or a change of chapter. A per-account cap of 200 committed
  continuation writes per day answers 429 `Retry-After` beyond it. The device copy remains the cache, so a coalesced
  write loses at most 60 s of position.
- *Volume estimate.* Committed writes per active learner-day <= min(cap 200, one per 60 s of activity + boundaries);
  a realistic 30-45 min of reading and listening is 15-40 commits. At the ~100,000-account target with an assumed 20%
  daily active (20,000 x 25 = 0.5 M) that is about **0.5 M receipt rows plus 0.5 M change rows per day, about 180 M
  of each per year**; the hard ceiling (cap 200 x 20,000) is 4 M per day. The reviewer's unbounded estimate was
  2-3 M per day; coalescing lowers it by roughly a factor of 4-5 but does **not** make it bounded by data volume.
- *Terminal `deleted` (P2-7).* `lifecycle_change` makes `deleted` terminal and ids are not reused
  (`work_contract.py`), and the id is deterministic, so "clear" is `{cleared:true}` in the payload, **never**
  lifecycle `deleted`.

**Design B - position on `library_items` (no receipt, no stream).** `library_items` already has the
`started` relationship (`models.py:577`) and is the "ContentMembership ... a relationship, never a copy"
(`models.py:565-570`). Migration 0022 adds `place JSON NULL` and `place_at TIMESTAMPTZ NULL` (plus a partial index
`(user_id, language_code, place_at DESC) WHERE place IS NOT NULL`).
- One row per (learner, language, kind, content id) is created on first open (`kind` reading/listening/book,
  `relationship='started'`; `source_id` <= 255, so a `url:` id is its digest and the URL lives in the imported work of
  I12) and **updated in place**. Row count is bounded by the content the learner opens, not by time spent; there
  is no receipt, no change record and no stream lock.
- The place write does **not** touch `library_items.version` or `updated_at`, so it cannot make a learner's pin,
  note or state PATCH (`expected_version`, `library_repository.py`) conflict; it is arrival-order last write
  ordered by the server (`place_at`). The same 30 s server coalescing may apply to cap UPDATE rate; volume is about
  0.5 M in-place UPDATEs per day at the same assumptions, with no row growth (hot-update friendly).
- Costs: it departs from ADA §2's "work-derived index" wording (Continue would live on the relationship record, and
  needs the reviewer's and human's acceptance of that departure); it is a migration; the finished flag lives in the
  place JSON.

**Recommendation: Design B.** Position is high-frequency, single-valued, last-write and not evidence, so the
receipt/version/stream machinery buys nothing, and B avoids growth in a reserved area (receipt compaction). If the
human prefers to follow ADA §2 literally, Design A with the coalescing above is the fallback, with growth of about
0.5 M rows per day per table accepted explicitly until the sync/compaction package. **I4 is not approved by this
proposal until the human chooses (H-12)**; the other items do not depend on it.
- **API (either design).** `PUT /api/continue/{content_id}` and `GET /api/continue?limit=` (<= 50, ordered by recency).
  Both refuse unless the store is available (A: backbone `active`; B: PostgreSQL runtime); device memory stays the
  fallback and cache.
- **Default for existing accounts.** Empty; device list imported only via H-6.
- **Deletion/export.** A: incarnation-keyed work rows, deleted explicitly by the workflow (2.6). B: `library_items`
  rows keyed by account, deleted explicitly by the workflow. A source removed makes the item "unavailable".
- **Retirement (D-103.1).** The old `#/continue` room retires (UI and route only). Its data was device memory, so
  nothing server-side is deleted; the store above replaces its function in Today "For you", the Practice Hub row
  and Content Detail. No consumer is built for the retired room.
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
- **Migration.** None (tables exist). **Default.** None; the device's 12 conversations import only via H-6.
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
- **Migration.** None. **Default/import.** Empty; import via H-6. **Consumer.** Reader, Quick Sheet Note tab,
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
- **Store (quiz/try-it results).** EA §1 Grammar: "canonical Concept ID, actual response and existing domain
  judgment"; "concept visit equals mastery" excluded (`EA:14`) [V]. The quiz key ships in the content and is graded
  in the browser (G6); Try-it is graded by the Writing engine and lands in `essays` (G8/G9), so *Try-it needs no
  new store*. For the quiz there are two options (**H-4**): (a) store nothing beyond completion, the honest
  reading of D-098 point 7 (only backend-measured numbers are shown); (b) additive nullable columns on
  `grammar_progress` (`last_quiz_correct`, `last_quiz_total`, `last_quiz_at`), migration 0023, stored alongside
  completion (`completed_at` is `NOT NULL`, so a result without completion is not representable without
  relaxing it, which this proposal does not do). (b) records a client-reported number, the same trade-off as the
  Dictation decision (D3 decision 2).
- **Dependency, not decided here.** The new route that accepts a point id must validate it against the
  **published** catalogue, whose serving API is held for its own architecture review (D-100 point 4).
  Until then this item is design-only; the completion route is named `PUT /api/learner/grammar/{point_id}/completion`
  (placeholder) and lands with that review or after it. The R5 `completeGrammar` route and the R5 table remain
  until the old-path retirement (`LEGACY_TOMBSTONES.md` entry on the human's instruction, D-100 point 5).
- **Migration.** None for (a). 0023 (three nullable columns, lock_timeout) for (b).
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
- **Migration.** None. **Default/import.** Empty; import via H-6 (imports carry learner text, so the preview step
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

### I14. Profile/Progress metrics: a real metric or no metric (D-103.4)

- **State.** Streak, weekly done-count, activity counts; minutes, daily goal, achievements, trends, skill %, level/XP.
- **D3.** P3, T-s, Q3, `UI_BACKEND_GAPS` N-21/N-32 [V]: no backend measure; an unmeasured value must never render
  as 0 (D-103.4). `learner_summary` says growth is unavailable per domain (`learner_summary.py:47-55`).
- **Built in D4 (defensible semantics, real server evidence, derived before persisted):**
  1. **Active days and streak.** A *day* is a calendar day in the learner's timezone on which at least one
     acknowledged learning event exists. The streak is consecutive days ending today or yesterday (the rule
     `GET /api/dashboard` already uses for writing, `app.py:2713-2725` [V], now cross-skill). **No storage:** a new
     read `GET /api/learner-activity?tz=<IANA>&days=` computes from rows that already carry an immutable
     per-event timestamp: `essays.created_at`, `speaking_attempts.created_at`, `reading_attempts.created_at`
     (`models.py:66,347,1276`) [V]. The timezone is a validated per-request parameter (zoneinfo), not stored; the
     server clock never decides a day boundary. Week = ISO week, Monday start [H-5].
  2. **Weekly-goal done-count** = distinct active days this week, against the persisted target of I3b.
  3. **Activity counts**: the existing `GET /api/learner-summary` (`window=`), unchanged.
- **The limit that must be decided (H-5).** Listening, Dictation, Shadowing and review carry only a
  last-update timestamp: `listening_progress.updated_at`, `shadowing_progress.updated_at`,
  `saved_words.last_reviewed_at` are overwritten on the next write (`models.py:277-336`) [V], so a *past* day whose
  only activity was a dictation cannot be proved, and counting it "best effort" would let a later write erase the
  day and falsely break a streak. Options: **(a, recommended)** count only the three immutable sources above and
  say in the approval entry that dictation-only days do not extend the streak (derivation first, no new
  persistence); **(b)** add an append-only per-day marker (`learning_days`: account, language, local date, skill;
  unique on those four, upserted by the domain owner in the same transaction as its write) so every skill counts,
  at the cost of one small new table and the tz being fixed at write time; **(c)** include the last-update
  timestamps and document the undercount (not recommended: a headline number that can be wrong). (b) is a new
  revision (0024) and needs its own review.
- **Hidden until a contract exists (no storage designed):** weekly minutes (no genuine duration is measured;
  client time is contextual, `EA:35-36`), the daily-goal ring and its minutes setting, achievements
  (`no_approved_policy`), trends, skill percentages, level/XP. The API returns these as absent, and the client
  hides them; it never returns 0 for an unmeasured value (D3 wrong-data risk 2 is fixed in the read model, I8).
- **Migration.** None for (a). **Consumers.** Profile (streak, week done-count), Today (streak card; the goal ring
  stays hidden), Progress (counts).

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
    CASCADE`, `user_id -> users.id ON DELETE CASCADE`, `language_code`, `superseded_at`, `reason`
    (`evaluator_refresh`), `prior_fingerprint`, `prior_contract`, `replaced_by_fingerprint`, `review JSON NOT NULL`
    (the whole prior review: five dimension scores, overall, level estimate, evaluator, `summary_vi`, strengths,
    strength evidence, priorities, errors, and the stored `grammar_links`). `UNIQUE (essay_id, prior_fingerprint)`,
    `INDEX (user_id, language_code, essay_id, superseded_at)`.
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
- **Deletion/export.** `essay_review_history` is account-keyed: removed with the essay (cascade) and explicitly by
  the D-055(b) workflow (section 2.6). **Default.** Empty table.
- **Tests.** Section 9.

## 4. Existing accounts: defaults and import (one place)

| Item | Default for an existing account | Device import |
| --- | --- | --- |
| I1 declared_level | `''` -> Welcome once (H2 5.2 A) | none |
| I2 learning_language | `''` -> session default `en`, Welcome once | none |
| I3 interface_language | `''` -> device/OS | none (device value seeds the first save) |
| I4, I6, I10, I12 | empty | only via H-6 (explicit, preview) |
| I5 drafts | empty | existing automatic per-piece send |
| I11 grammar | R5 completions count via aliases | none |
| I13 review settings | `NULL` = client defaults | the device value seeds the first save [I] |
| I3b weekly goal | `NULL` (not set) | none |
| I18 Dictation | existing rows `score_source='client'`, kept, superseded by the next verified check (H-14) | none |
| I19 Chinese review history | empty table; no essay is re-graded until reopened | none |

## 5. Migration plan (ordered)

Head today: `20260924_0016` (repo). Sandbox database is at `20260923_0014` (H2 section 3, `CURRENT_HANDOFF.md`);
the lane runtime is on PostgreSQL 17 [V per D3]. All revisions are additive, live in `migrations/proposed/` until
reviewed, rehearsed and authorized, then `git mv`'d to `versions/` one at a time. No startup Alembic (D-002);
only `scripts/bootstrap_runtime_schema.py` applies them. None is added to `GATED_REVISIONS`
(`bootstrap_runtime_schema.py:62-65`; that set is for non-mechanical revisions like the 0016 cutover).

| Rev | File | Adds | Guard |
| --- | --- | --- | --- |
| 0017 | `20260929_0017_declared_level.py` | `user_language_profiles.declared_level` | H2 section 3 verbatim |
| 0018 | `20260929_0018_account_settings.py` | `users.learning_language`, `users.interface_language` (`NOT NULL DEFAULT ''`), `users.weekly_goal_days` (`SMALLINT NULL`) | `users` is hot: lock_timeout matters most here |
| 0019 | `20260929_0019_review_settings.py` | `user_language_profiles.review_new_per_day`, `review_limit_per_day`, `review_modes` (nullable) | - |
| 0020 | `20260929_0020_listening_score_source.py` | `listening_progress.score_source VARCHAR(12) NOT NULL DEFAULT 'client'` | `listening_progress` is written on every check; a constant default is metadata-only |
| 0021 | `20260929_0021_essay_review_history.py` | **new table** `essay_review_history` (I19): FKs to `essays`/`users` `ON DELETE CASCADE`, `UNIQUE (essay_id, prior_fingerprint)`, one index | `CREATE TABLE` locks no existing table |
| 0022 | `20260929_0022_library_items_place.py` (conditional on H-12 = Design B, recommended) | `library_items.place JSON NULL`, `library_items.place_at TIMESTAMPTZ NULL`, partial index | `library_items` is written by keeps; nullable columns, no default |
| 0023 | `20260929_0023_grammar_quiz_result.py` (conditional on H-4b) | `grammar_progress.last_quiz_correct/total/at` (nullable) | - |
| 0024 | (conditional on H-5b, **not** proposed) | append-only per-day marker (I14 option b) | own review |

Rules for every revision:
- `upgrade()` and `downgrade()` first run `SET LOCAL lock_timeout = '5s'` **guarded by dialect**:
  `if op.get_bind().dialect.name == "postgresql": op.execute("SET LOCAL lock_timeout = '5s'")`. (H2 wrote it
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

Non-migration changes, in order of dependence: registry entries (`WORK_KINDS`: `continuation`, `annotation`,
`imported`; `MUTATION_DOMAINS` likewise); `GET /api/works` list; `PUT/GET /api/continue`,
`/api/annotations`; turn append; provenance route; profile settings; language endpoints; `since` on speech
attempts; listening language check and server-side Dictation scoring (`writing_coach/dictation_evaluator.py`);
`GET /api/learner-activity`; `POST /api/essays/{id}/review/refresh` and `GET .../review/history`;
pair-aware `effective_contract_version`; flag in `compose.yaml`.

## 6. Rehearsal (D-102 point 7; ADA §6 step 3)

On a throwaway PostgreSQL 17 (`docker run` with a random port and no shared volume), never a shared runtime or
volume; heavy Docker work does not overlap another lane's (D-101 working rules). CI has no PostgreSQL service
(`.github/workflows/ci.yml` has no postgres) [V], so PG cases skip there via `ORENA_TEST_POSTGRES_URL`
(`tests/test_orena_work_persistence_postgres.py:1-15`); the rehearsal is a recorded local run, like
`scripts/rehearse_my_library_schema.py`. Sequence:
1. Create at `0016`, seed rows: profiles for two accounts x en/zh, `users` rows, `grammar_progress` R5 rows, works,
   `listening_progress` rows (one with a wrong-language asset, like the bench probe), essays with and without a
   stored review identity.
2. `upgrade` 0017 -> 0018 -> 0019 -> 0020 -> 0021 (-> 0022, 0023), asserting per revision: pre-existing rows read the default, no lock
   wait beyond 5 s while a concurrent transaction holds a row lock on `users`/`user_language_profiles`.
3. `downgrade` to `0016`, then `upgrade` again (up/down/up), asserting the ORM equals the migrated schema
   (`tests/test_reading_evidence_schema_parity.py` pattern) at each head.
4. Concurrency on the real repositories: two PATCHes with one `expected_version` give one 200 and one 409; two
   position writes with one `expectedVersion` give one commit and one conflict; two turn appends at one head give
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
- Receipt compaction and cursors (I4 Design B avoids them; Design A coalesces but does not remove the growth).
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
- **I3, I13:** patch, read-back, clamp, PUT does not erase, stale `expected_version` -> 409, `''`/`NULL` defaults.
- **I4:** PUT position then GET on a new session returns it; list ordered by recency and bounded; a stale version
  conflicts and the client's re-apply wins by version; finished flag round-trips; `text:`/`url:`/`book:` ids
  round-trip; a source removed reads "unavailable". Front end: throttling test with an injected clock.
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
  and nothing is rewritten; unknown/unpublished id refused; (b) quiz columns round-trip.
- **I12:** import text -> `text:<uuid>` opens on a "new device"; kept mapping; provenance attach and read;
  deletion marks dependents unavailable.
- **I16:** listening/shadowing save with a ZH asset under an EN scope -> 422; unknown asset -> 404; valid -> 200;
  existing rows still listed.
- **I18:** the Python evaluator against the golden vectors (en/zh); a forged client `best_*` is ignored; a wrong
  answer with a client-claimed 100 stores the computed value; best is never lowered by a worse later answer; the
  count is never lowered and rises by at most 1 per write; `revealed` writes change no score; a `client` row is
  superseded by the first verified check; answer too long -> 422; canonical line unresolvable -> 404; the `.mjs`
  gate runs the JS evaluator on the same vectors.
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
- **I14:** streak over a hand-built set of essays and attempts across days and two timezones (a day boundary in
  `Asia/Ho_Chi_Minh` differs from UTC); a gap breaks it; the today-or-yesterday rule; weekly done-count against
  `weekly_goal_days`; nothing unmeasured is returned as 0 (fields absent).
- **Backbone off:** every new route answers `503 account_backbone_disabled` and clients fall back to device
  without claiming a save.
- **Deletion enumeration (P1-1):** a test lists every table and column this proposal touches and fails if one is
  missing from the D-055(b) enumeration: the **`users` columns to reset** (`learning_language`, `interface_language`,
  `weekly_goal_days`), and the rows to delete in `user_language_profiles`, `grammar_progress`, `listening_progress`,
  `shadowing_progress`, `speaking_attempts`, `essays`, `essay_review_history`, `library_items` (incl. `place`),
  `saved_words`, and the incarnation-keyed `works`, `work_turns`, `mutation_receipts`, `change_records`,
  `language_provenance`. The D-055 gate test that no runtime path deletes stays.
- **Generic work route (P1-5):** `PUT /api/works/{id}` with kind `annotation`, `imported` (or `continuation`) is
  refused 422 `work_kind_invalid`; the dedicated routes accept them.
- **Browser (D-102 point 5, real backend, PostgreSQL):** EN and ZH, a new browser context reads back position,
  draft, conversation, note, level and language; results recorded in D3.

## 10. Open human decisions

- **H-1 Existing accounts.** H2 5.2 option A (everyone sees Welcome once per language they use) extended to I2
  (learning language). Recommended: yes.
- **H-2 Interface language (I3):** server-stored account setting (recommended), or device only.
- **H-3 Reading Transfer (I9):** store as a non-evidence `response` (recommended), or define a Transfer evidence
  producer, or store nothing.
- **H-4 Grammar quiz result (I11):** completion only (a, recommended), or nullable quiz columns (b, migration 0023).
- **H-5 Streak policy (I14, D-103.4):** (a, recommended) days from the three immutable sources, accepting that
  dictation, shadowing and review-only days do not extend the streak; (b) a small append-only per-day marker so
  every skill counts (new table, own review); (c) not recommended. Also: the learner timezone is a per-request
  parameter (not stored) and the week starts on Monday.
- **H-6 Device import:** none (default), or one explicit "Bring this device's work into your account" action for
  positions, conversations, annotations, imports; never at startup. It moves device data to the server.
- **H-7 Writing register and target length:** store in the draft and make the evaluator read them, or retire the
  controls.
- **H-8 Conversation coaching:** part of the turn, or regenerated on demand.
- **H-9 History:** whether Progress > History lists typed Free Talk/Situation/React responses.
- **H-10 Orena history:** keep device by AGENT_CONTRACT:383 (recommended until G), or reopen the review.
- **H-11 Activate the backbone:** turn `ORENA_ACCOUNT_BACKBONE` on for the lane runtime and for :8000 after the
  merge (recommended), given D-055's open deletion preconditions.
- **H-12 Continuation store (I4), a real decision:** Design B, `place` columns on `library_items` (recommended: no
  receipts, no growth in a reserved area; departs from ADA §2's wording), or Design A, `works` `continuation` with
  server coalescing and an accepted ~0.5 M rows/day in each of two tables until the compaction package.
- **H-14 Old Dictation numbers (I18):** superseded by the next verified check (recommended), or kept and labelled.
- **H-15 Old Chinese essays with no stored review identity (I19):** not refreshed because their pair cannot be
  verified (recommended), or refreshed on a stated assumption.
- **H-16 Weekly goal display (I3b):** whether the Profile bar is drawn when no target is set (a design question).
- **H-17 Account scalars (P1-4):** accept arrival-order last write for `users.learning_language`,
  `interface_language` and `weekly_goal_days` as a recorded exception to ADA §1 (recommended), or add
  `users.settings_updated_at` and the expected-version rule.
- **H-18 AGENTS §7 amendment and `users` placement (P1-5), see section 13.**
- **H-13 Data-model corrections in D3** (no decision, please confirm): Part 3's `reviewSettings` "not read by /next"
  is wrong (I13); Speaking attempts require a `segment_id` even for free expression (I8).

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

## 13. Requested amendments and decisions that go to the human

1. **AGENTS §7 amendment (H-18).** §7 says kept-language provenance, conversations, drafts and continuation are
   device memory "by design" and forbids new learner-data persistence decisions. D-101 "Persistence" and D-103 are
   explicit current human instructions to store learning records, and ADA §2 already names the targets. The approval
   entry should amend §7 to say: **drafts, conversations, continuation, annotations, imported texts, provenance, the
   listed account settings and the evidence records in this proposal are server-owned records**; and that the
   **holds remaining** are sync cursors and multi-device conflict design, tombstone horizon, receipt compaction,
   account deletion and re-registration runtime (D-055), export format, native mobile, and Orena history
   (`AGENT_CONTRACT.md:383`, I15). This proposal changes no other reserved matter.
2. **`users` placement (H-18).** Account-wide settings on `users` (`learning_language`, `interface_language`,
   `weekly_goal_days`) extend the identity-mapping table with learner preferences. Alternative: a per-account settings
   table (a new table, against "no ad-hoc tables" unless the human accepts it). Recommended: columns on `users`,
   with the D-055(b) reset in section 2.6.
3. **Generic work route.** New kinds are reachable only through their dedicated routes; the pre-existing kinds keep
   their behaviour. Dedicated routes define server-side rules (deterministic ids, payload bounds, and for turns the
   role alternation and `reply_to` rules copied from `restoreConversation`), which the human approves with this
   proposal.
4. **Decisions for the human now:** H-12 (continuation store), H-17 (account-scalar conflict rule), H-18 (AGENTS §7
   and `users`), H-11 (activate the backbone), H-6 (device import), H-1 (Welcome once), H-5 (streak policy), H-3,
   H-4, H-2, H-14, H-15. H-7, H-8, H-9, H-16 are product or design calls with no storage impact.
