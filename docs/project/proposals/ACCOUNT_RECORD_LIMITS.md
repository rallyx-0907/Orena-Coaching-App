# Proposal: server-side safety limits and retention/rejection behaviour for account records

Status: **APPROVED WITH CONDITIONS (rev 4 re-check, 2026-10-01); implementation not started.** Revision 5 (2026-10-01) applies
the re-check's conditions (section "Rev 5 changes"). History: rev 1 (`codex/work` at `8481e33`) was reviewed in
`ACCOUNT_RECORD_LIMITS_REVIEW.md` (REQUEST CHANGES, P1 1, P2 4, P3 5, C1-C5); rev 2 answered it and rev 3 applied the re-check
of rev 2 (APPROVE WITH CONDITIONS); rev 4 changed the proposal for human decision **D-107** (separate media-import limits, an
uploaded-media byte limit, a quota-refused import never shown as saved) and replaced the draft assumption with a measurement;
the re-check of rev 4 is APPROVE WITH CONDITIONS. Document only: no code, schema, migration, Docker or runtime is changed by
this file. Enabling the backbone beyond :8021 remains the human gate of D-107 point 5, which also requires the gates G1 and G2
(section 8) and rollout steps 0b and 0c.

Human instruction (verbatim): "Before enabling the backbone beyond `:8021`, propose configurable server-side safety
limits and retention/rejection behavior for: reading positions, typed responses, notes, conversations. Do not invent
arbitrary learner-facing quotas. Provide size/volume reasoning for the proposed defaults and send that policy for review."

Origin: implementation review `LEARNER_RECORDS_D4_IMPLEMENTATION_REVIEW.md`, finding **P2-4** ("Unbounded server rows and
receipts per account") and its delta check (condition 4: per-account caps for `started` rows, responses, annotations and
conversations, **and a receipt-growth owner**, before :8000/:8010). `LEARNER_RECORDS_D4.md` section 17 ("Held for the
human") records the same hold. This file answers it.

Process (AGENTS sections 1, 7, 10): proposal -> independent review -> human approval -> code + tests in the lane -> the
human's gate for :8000/:8010. The author of this proposal may not review it. **Nothing here authorizes enabling the backbone
on :8000 or :8010**, and nothing here decides the items AGENTS section 7 reserves (receipt compaction, the sync protocol,
the account-deletion runtime, the export format). Those appear only as options, marked **DECISION FOR THE HUMAN/ARCHITECT**.

Legend: **[V]** read in code at the stated path and line in this working tree; **[I]** inferred or estimated, to be
replaced by a measurement; **[A]** a stated assumption. Line numbers were taken on 2026-10-01 at HEAD `8481e33` plus another session's uncommitted edits (since committed; rev 5 re-read the facts of 4.5 at HEAD `83a6037` and the lines of the older sections may have drifted; the symbol names are the anchor). The earlier note read: HEAD `8481e33`
plus another session's uncommitted edits to `writing_coach/account_records_api.py`, `static/orena/product/account-records.js`
and `static/orena/screens/reader/annotations-sync.js`); they drift, so each reference also names the symbol.

---

## 1. Summary

**What is unbounded today [V].** Every record below is created under a *client-chosen key*, so one authenticated account can
create rows without limit. Only two bounds exist that count rows: 20 private imports per (account, language)
(`account_records_api.py:40,230-248`) and 24 turns per conversation (`work_repository.py:229,336`). Everything else is a
per-request size bound (Pydantic `max_length`), not a per-account one. There is **no rate limiter of any kind** on these
routes (`grep` for rate limiting in `writing_coach/` finds only AI-provider telemetry).

| Kind | Client-chosen key | Rows a runaway client can add |
| --- | --- | --- |
| Reading position | `PUT /api/continue/{content_id}` (`library_api.py:247`), any string up to 255 | one `library_items` row per distinct id; **also a row with `place: null`** (finding F1) |
| Typed response | `PUT /api/responses/{key}` (`account_records_api.py:305`), key up to 255; the client mints `randomUUID()` per take (`account-records.js:227`) | one `works` row + receipt + change record per key |
| Note / highlight | `PUT /api/annotations/{content_id}` (`:139`), id up to 255 | one `works` row per id; every push rewrites the whole payload and adds a receipt + change record |
| Conversation | `POST /api/conversations/{key}/turns` (`work_api.py:234`), key up to 200; **creation has no guard** (`work_repository.py:322-323`) | one `works` row per key, up to 24 turns each |
| Receipts / change records | (every mutation) | 2 rows per mutation, for ever; nothing reads the change feed (no client calls `/api/works/changes`) and nothing deletes either table |

**Findings beyond P2-4** (each fixed by the limits below or flagged):

- **F1.** `set_place` with `place: null` on an absent row **inserts a row** (`library_repository.py:312-317`). Such a row has
  `place IS NULL`, so it is invisible to the partial index `ix_library_items_place` and to any cap counted on it. A cap
  must count `started` rows, not rows with a place, and a null place on an absent row should insert nothing.
- **F2.** The generic `PUT /api/works/{id}` (`work_api.py:268`) still accepts kinds `draft`, `response`, `conversation`
  (`work_contract.py:27`) under **client-minted UUIDs**, bypassing the deterministic-key routes. No client calls it (no
  `api/works/` writer in `static/orena`); only tests do. Rev 2 **refuses those kinds on it** (section 3.3b) rather than guarding them.
- **F3.** `MAX_PAYLOAD_CHARS = 200_000` (`work_api.py:56`) is checked only on the generic route (`:276`). The dedicated
  routes rely on Pydantic bounds. The annotation worst case is **191,307 characters** (measured with the field maxima:
  80 highlights x {id 80, segment 255, sentence 400, at 40} + 120 notes x {id 80, key 255, text 600, at 40}), not the
  "about 104 KB" of proposal I10, which counted only the free text. With the uncommitted `MAX_TOMBSTONES = 500` ids
  (`account_records_api.py:38`) it is **233,323 characters**, above `MAX_PAYLOAD_CHARS`, and about **441 KB** as UTF-8 when the
  text is Chinese. Not dangerous; the proposal text should be corrected.
- **F4.** Draft autosave is a receipt producer the four named kinds are dwarfed by (section 2.3). It is outside the four
  kinds, but it shares the stream and therefore the rate rail.
- **F6 (rev 2, review P1-1). Delete bypasses every count, and the live 20-import cap already has this defect.** Counting
  `lifecycle <> 'deleted'` (the shipped `at_most_the_limit`, `account_records_api.py:230-241`, and rev 1's aggregate) lets a
  loop create, mark deleted, repeat: a tombstone is terminal and ids are not reused, so every cycle leaves a row, a receipt
  and a change record while the counted total never rises. Generic `PUT /api/works/{id}` accepts `lifecycle: deleted`
  (`work_api.py:274-285`) and a creation may start deleted; the import route allows create, delete, create.
  **This is an existing defect in code, to be fixed independently of the rest of this proposal** (section 3.3a).
- **F5.** The eviction predicate `_place_only()` (`library_repository.py:66-76`) says "not filed" in its docstring but does not
  check collection membership. An eviction built on it must add `NOT EXISTS (library_collection_members ...)`.

**Proposed defaults** (every one configurable; all are safety rails at 2x-7x the heavy-learner 3-year volume, none is shown to
a learner; derivations in sections 2 and 4):

| Rail | Env name | Default | Scope | At the limit |
| --- | --- | --- | --- | --- |
| Reading-position rows (`started`, reading/listening/book) | `ORENA_LIMIT_PLACES` | 5,000 | per (account, language) | **evict** least-recently-used place-only rows; never an error |
| Typed responses | `ORENA_LIMIT_RESPONSES` | 25,000 | per (account, language) | **reject** new key: 422 `response_limit`; never evict |
| Annotated texts (notes + highlights documents) | `ORENA_LIMIT_ANNOTATED_TEXTS` | 2,500 | per (account, language) | **reject** new text: 422 `annotation_limit`; existing texts still update |
| Conversations | `ORENA_LIMIT_CONVERSATIONS` | 2,500 | per (account, language) | **reject** new conversation: 422 `conversation_limit` |
| Turns per conversation (existing) | `ORENA_LIMIT_CONVERSATION_TURNS` | 24 | per conversation | 422 `turn_limit` (exists today) |
| Record **stored** bytes (`works.payload` as stored, tombstones included) | `ORENA_LIMIT_RECORD_BYTES` | 134,217,728 (128 MiB) | per (account, language) | **reject** new row, or a growth past 32 KB: 422 `record_bytes_limit` |
| Drafts (rev 2) | `ORENA_LIMIT_DRAFTS` | 2,500 | per (account, language) | **reject** new key: 422 `draft_limit` |
| **Text-import pool**: live (existing) / total with tombstones | (code constant `MAX_IMPORTS`) / `ORENA_LIMIT_IMPORT_TOMBSTONES` | 20 / 360 | per (account, language) | **reject** a new text import: 422 `import_limit` |
| **Media-import pool** (rev 4, D-107): live items, URL/YouTube and uploads share it | `ORENA_LIMIT_MEDIA_IMPORTS` | 1,250 | per (account, language) | **reject** a new media import: 422 `media_import_limit` |
| Media-import pool, total with tombstones | `ORENA_LIMIT_MEDIA_IMPORTS_TOTAL` | 2,500 | per (account, language) | **reject**: 422 `media_import_limit` |
| **Uploaded-media storage bytes** (original + thumbnail, live uploads only) | `ORENA_LIMIT_MEDIA_UPLOAD_BYTES` | 10 GiB (10,737,418,240) | **per account, all languages** | **reject** the upload: 422 `media_bytes_limit`; nothing stored |
| Uploads per hour | `ORENA_LIMIT_UPLOADS_PER_HOUR` | 30 | per account | 429 `write_rate_limited`, retryable |
| Mutations per minute | `ORENA_LIMIT_WRITES_PER_MINUTE` | **120** (rev 4; was 240) | per account | 429 `write_rate_limited`, retryable |
| Mutations per hour | `ORENA_LIMIT_WRITES_PER_HOUR` | 3,600 | per account | 429 `write_rate_limited`, retryable |
| Place writes per minute | `ORENA_LIMIT_PLACE_WRITES_PER_MINUTE` | 120 | per account, per process | 429 `write_rate_limited` |
| Place minimum interval, same row | `ORENA_PLACE_MIN_INTERVAL_SECONDS` | 1 | per row | answered `coalesced` (existing status), no error |

**Receipts and change records** (section 5): the growth is the real scale problem (about **244 GB/year** of receipts and
change records at the 100k-account target under the stated assumptions, of which autosave drafts are about 76%, using the
rev 4 measured cadence).
This proposal names an **owner** (the Principal Architect role, AGENTS section 1) and lays out options, but **proposes no
deletion**. Until a versioned policy exists nothing is purged (ADA section 5: "missing policy disables destructive purge").

---

## 2. Method: assumptions, cost constants, volumes

### 2.1 Assumptions [A]

The repository holds no usage telemetry, so these are assumptions, stated so a reviewer can change them and re-run the
arithmetic (appendix A). **A2-A4, A5's session length and frequency, A10-A12 and every size in section 2.2 are UNMEASURED.** A5's *cadence* (saves per
active writing minute) was **measured on the lane in rev 4** (section 2.4). Nothing else below is a measurement and the defaults
are not to be read as one. Rev 2 made measuring the draft cadence on the lane a precondition of fixing the rate defaults
(section 9, rollout step 0); rev 4 does it and records the result in section 2.4.

| # | Assumption | Basis |
| --- | --- | --- |
| A1 | 100,000 accounts; 20,000 daily-active | target scale, AGENTS section 7; 20,000 DAU is the figure `LEARNER_RECORDS_D4.md` I4 already uses |
| A2 | Of the DAU, **25% heavy** (5,000) and 75% typical (15,000). Non-daily accounts add a tail that is **not** estimated, so totals are a floor | **[A], unmeasured** |
| A3 | Heavy learner: 2 sessions/day, 365 days/year. Typical: 1 session/day, 208 days/year (4 days a week) | **[A], unmeasured** |
| A4 | Per session, heavy / typical: 1.5 / 1.0 new content opened (reading positions); 5 / 3 typed takes; 0.5 / 0.3 annotated texts at 9 / 5 pushes each; 0.5 conversations at 16 / 10 turns | **[A], unmeasured**; Free Talk and Reading Transfer produce a take each (`free-talk/screen.js`, `saveResponse`); conversations are scenario-shaped (I6) |
| A5 | Autosave drafts: **cadence measured** (section 2.4): 9.0 saves per active writing minute for heavy (the measured mix of ordinary, fast and pathological typing) and 3.7 for typical (ordinary typing); a 15-minute writing session; heavy 1 session/day (365/year), typical 60/year | cadence **[M] measured on the lane with scripted typing**, not by real learners; session length and frequency **[A], unmeasured** |
| A10 | Media imports (rev 4): heavy 100 uploads and 260 URL/YouTube imports a year; typical 12 and 24 | **[A], unmeasured** |
| A11 | Upload size: mean 15 MiB, median 10 MiB, p95 60 MiB, hard cap 64 MiB; thumbnail about 40 KB (video frame) to 100 KB (embedded audio artwork); index metadata about 1.5 KB plus about 2.5 KB per minute of transcript | cap **[V]** (`MAX_UPLOAD_BYTES = 64 * 1024 * 1024`, `media_thumbnail.py:31`); the rest **[A], unmeasured**. 128 kbps audio is about 1 MB a minute, so 64 MiB is about 70 minutes of audio; 720p video at 2.5 Mbps is about 19 MB a minute, so the cap is about 3-4 minutes of it |
| A12 | A heavy sitting imports at most 10 files | **[A], unmeasured** |
| A6 | A learner works mostly in one learning language, so per-(account, language) limits are sized against one language's volume | [A]; conservative |
| A7 | "Heavy 3-year volume" is the yardstick for default sizing: evictable derived state gets >= 1.5x it, learner-authored records >= 2x it | design rule of this proposal |
| A8 | A heavy learner's typical row: response answer about 150 characters and compact coaching about 800 (`compactCoaching` caps at 4,000, `account-records.js`); annotation text 6 highlights + 3 notes (2,436 characters measured); conversation turn about 0.5 KB of content | [A] / measured for the annotation |
| A9 | The client only writes while `ORENA_ACCOUNT_BACKBONE` is `active`, and every write is best effort and silent on failure (`account-records.js` header; `catch {}` blocks at `:136,157,179,193,205,237`) | [V] |

### 2.2 Row-size constants [I]

PostgreSQL 17 layout estimates (heap tuple header 24 B, varlena headers, btree tuples at 90% fill). To be replaced by
`pg_total_relation_size` on the rehearsal database at volume (section 9).

| Row | Heap | Indexes | Total, excluding variable content |
| --- | --- | --- | --- |
| `works` (`0005`: PK, `ix_works_scope_sequence`, `uq_work_scope_identity`) | about 128 B | about 156 B | **0.30 KB** + `source_id` + payload |
| `change_records` (PK, `uq_change_record_sequence`) | about 140 B | about 72 B | **0.21 KB** |
| `mutation_receipts` (PK, `uq_mutation_receipt_operation`, `ix_mutation_receipts_stream`) | about 280 B (64-char digest, two 36-char ids, 39-char operation id) | about 165 B | **0.45 KB** |
| receipt + change record, per mutation | | | **0.65 KB** |
| `work_turns` (PK, `uq_work_turn_ordinal`) | about 110 B | about 72 B | **0.18 KB** + content JSON |
| `library_items` place row (PK, `uq_library_items_id_kind`, `ux_library_items_source`, `ix_library_items_shelf`, `ix_library_items_place`) | about 110 B + `source_id` + place JSON | about 243 B + `source_id` | **0.35 KB + 2 x len(`source_id`) + place JSON**; typical **0.7 KB**, hostile **3 KB** |

Variable content, in **bytes**: every character bound in the code is a character bound, and Chinese text is 3 bytes a
character in UTF-8 (`json.dumps(..., ensure_ascii=False)`, `work_repository.py:167`), so a byte worst case is up to 3x the
character worst case.

### 2.3 Volumes derived from A1-A9

Per account per year. Mutations are what write receipts and change records (0.65 KB each); place writes write none.

| | Heavy | Typical |
| --- | --- | --- |
| Reading-position rows created | 1,095 | 208 |
| Typed responses (rows, mutations) | 3,650 | 624 |
| Annotated texts (rows) / pushes (mutations) | 365 / 3,285 | 62 / 312 |
| Conversations (rows) / turns (mutations and `work_turns` rows) | 365 / 5,840 | 104 / 1,040 |
| **Mutations, the four kinds** | **12,775** | **1,976** |
| Autosave drafts (mutations), A5 measured cadence | 49,275 | 3,330 |
| **Mutations, all** | **62,050** | **5,306** |
| Storage, the four kinds (rows + their receipts/change records) | 19.4 MB | 3.3 MB |
| Storage, all mutations' receipts/change records | 39.8 MB | 3.4 MB |

At the target, 5,000 heavy + 15,000 typical accounts, **per year**:

| | Four kinds | Including drafts |
| --- | --- | --- |
| `library_items` place rows | 8.6 M (5.7 GB) | same |
| `works` rows (responses 27.6 M, annotated texts 2.8 M, conversations 3.4 M) | 33.8 M | same |
| `work_turns` rows | 44.8 M | same |
| Mutations | 93.5 M | **389.8 M** |
| Receipt + change-record rows | 187 M | **780 M** |
| Receipts + change records, storage | 58 GB | **244 GB** |
| All storage (content + receipts + change records) | 139.5 GB | **about 326 GB** |
| Average mutation rate | 3.0 / s | 12.4 / s (peak of the order of 100 / s across all accounts; per account the stream lock serialises, `mutation_commit.py:106-112`) |

Reading of the table: **the receipt and change-record tables, not the learner's words, are the growth**: 42% of the
four-kind storage and 75% once autosave is counted. That is why section 5 exists. A heavy learner's own words are about
11 MB a year.

---

### 2.4 Measurement: the autosave cadence on the lane (rev 4; rollout step 0 for drafts)

Run on the lane runtime `http://127.0.0.1:8021/next` (backbone `active`), 2026-10-01, with Playwright driving the Writing room
(`#/write`, draft key `expression:free`, the same `draftSync` path as every Writing and free-expression draft) and typing in real
time at human cadences; the network log counted every non-GET `/api` request. No source was edited, no Docker command other than
`docker ps`; learning language `en` and interface `vi` verified afterwards. Raw data and the scripts are in the author's
scratchpad (`autosave_measure.md`, `cadence.cjs`, `cadence2.cjs`); the numbers are reproduced here.

| Session | Typing model | Active min | Keystrokes | Saves | **Saves per active minute** | Max in any minute | Gap between saves, min / median |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A ordinary | about 40 wpm, phrases of 3-8 words, 1.5-5 s thinking, a 10-20 s stop every 5th phrase | 6.26 | 853 | 23 | **3.7** | 5 | 6.9 / 14.8 s |
| B fast | about 70 wpm, phrases of 1-3 words, 1.3-3 s pauses | 3.03 | 476 | 37 | **12.2** | 13 | 2.3 / 4.4 s |
| C pathological | a 1.3-1.5 s pause after every word | 2.03 | 304 | 42 | **20.7** | 21 | 1.7 / 2.8 s |
| All | the mix above | 11.3 | 1,633 | 102 | **9.0** | 21 | |

- All 102 mutation requests were `PUT /api/drafts/expression%3Afree`, all HTTP 200; no other mutation request, no 409, no 429.
- **Mutations per active writing minute: 3.7 (ordinary), 12.2 (fast), 20.7 (pathological, the observed ceiling), 9.0 (mix).**
  A5 had assumed 6; ordinary typing is 1.6x below it, fast 2x above. The **observed** ceiling is 21 a minute, one save per about 2.9 s,
  because typing a word itself takes time (about 1.5 s at 5 characters a second) on top of the 1.2 s debounce and the round trip.
  The **46 a minute** used for sizing is a different thing: a bound computed from the 1.2 s debounce plus about 0.1 s round trip
  with zero typing time (1 / 1.3 s). No typist can sustain it; it exists so that the rail does not depend on how fast the
  measured typist was. Both numbers are used below and neither contradicts the other.
- **Notes and highlights** (the real debounced `annotations-sync.js` path, with a synthetic highlight every 3-9 s for 3.12
  minutes, not the Reader UI): 29 changes produced 29 `PUT /api/annotations/...`, i.e. **9.3 pushes per minute**, one per
  change whenever changes are more than 1.2 s apart.
- **Other rooms**: the conversation composer does not autosave (one `POST /turns` per sent turn, `account-records.js`
  `appendConversationTurn`); typed responses are one `PUT` per take; both are bounded by human turn-taking and were not driven.
- **Limits of the measurement.** Scripted typing at assumed speeds on one device, 11 minutes, not real learners, not a whole
  session; it supports the cadence per active minute, not A2-A4 or the session length. Test data left on the lane: the draft
  `expression:free` and the annotation `qa-cadence-text` (29 highlights).

**Consequence for the model.** Heavy drafts per year = 9.0 x 15 minutes x 365 = 49,275; typical = 3.7 x 15 x 60 = 3,330 (was
32,850 and 5,400). Drafts are 296 M of the 390 M mutations a year (76%).

## 3. Cross-cutting design

**3.1 A safety rail is not a quota.** No number is shown to a learner, no counter, no "x of N", no upgrade path, no copy.
Each default sits above any use the assumptions describe: the place cap is 4.6 years of the heavy profile, the others 6.8
years. A learner who reaches one is a bug, a test account or an abuser, and is told nothing new (section 4 says what the
existing client does). Numbers live only in configuration and in the operator's logs. Free-tier or entitlement limits, if
the business wants them, are a separate product decision (I3 quota tables exist, `0006`/`0007`) and are **not** proposed
here.

**3.2 One module, one validation.** A new `writing_coach/account_limits.py` (implementation, after approval) reads each
`ORENA_LIMIT_*` variable once at startup, through the same `os.getenv` convention the repository already uses, and fails
startup on a non-integer, a non-positive value, or a value **below a floor** (the heavy 1-year volume: places 1,095,
responses 3,650, annotated texts 365, conversations 365, bytes 16 MiB, writes per minute 60, writes per hour 600, import tombstones 52, drafts 365, media imports 360, media upload bytes 1.5 GiB, uploads per hour 10). A floor
stops a misconfiguration from becoming a quota. There is no value that means "unlimited" (a very large integer does) and no
per-account override in this proposal. `compose.yaml` passes the variables through with the defaults, like
`ORENA_ACCOUNT_BACKBONE: ${ORENA_ACCOUNT_BACKBONE:-off}`.

**3.3 Where enforced: inside the creating transaction, after the account stream lock.** Exactly the pattern of the import
bound (`account_records_api.py:230-248`, `work_repository.py:103-105,138-139`): `commit_mutation` takes the lock on
`account_streams` first (`mutation_commit.py:106-112`), so two creations at N-1 cannot both pass. The guard raises
`MutationRefused(<code>)`, the envelope rolls back and answers `rejected`, and the route maps it to 422 with the code as
`detail.category` (`account_records_api.py:77-82`). Three additions to the envelope, all code, no schema:

- `create_guard` is passed by **every** creator, including `put_response`, the generic `PUT /api/works/{id}` (F2) and the
  conversation's first turn (`_append_turn.load`, `work_repository.py:322-323`). One helper runs a single aggregate,
  `SELECT kind, count(*) FILTER (WHERE lifecycle <> 'deleted') AS live, count(*) AS total, coalesce(sum(pg_column_size(payload)), 0)
  FROM works WHERE incarnation_id = :inc AND language_code = :lang GROUP BY kind` (**all rows, tombstones included**, review
  P1-1), and compares each kind to its limit. It uses `ix_works_scope_sequence`
  for the range and reads the heap for `kind`; for the heaviest account at cap (about 30,000 rows) that is one scan of about
  10-20 ms [I], paid only on **creation**, which is 0.1 a second at the target. `pg_column_size` of a TOASTed value reads the
  pointer, not the value. **It is therefore the stored (possibly compressed) size**, not the logical size (review P2-4):
  prose compresses about 2-3x, so the 128 MiB budget is a *stored-size* budget and admits more logical bytes than its
  number. It is a rail; the true ceiling is stated in 4.3.
- A **replay never hits a guard.** A retry of a committed creation finds the row, so `load` does not call `create_guard`
  (`work_repository.py:135-140`), and the receipt lookup precedes the decision (`mutation_commit.py:132-140,171-179`). The
  rate rail (section 6) must be evaluated after the receipt lookup and skipped on a receipt match, for the same reason.
- A **growth guard** for updates: `load` already holds the old payload; when the new payload would exceed 32 KB and is
  larger than the old, the same aggregate runs with the delta. Typical payloads are 1-3 KB, so the aggregate almost never
  runs on an update.

**3.3a Tombstones count (review P1-1, C1).** Row-count rails count every row of a kind whatever its lifecycle, and the byte
budget includes tombstones. Per kind:
- `response`, `conversation`, `annotation` and `draft` have **no delete route** (clearing an annotation is `{cleared: true}`
  on the same row; the others are never deleted). Creation with `lifecycle = 'deleted'` is **refused** (422
  `lifecycle_invalid`) on every path; the dedicated routes already write only `active`. With deletion impossible, "all rows"
  equals "live rows" and nothing can be recycled.
- `imported` is the one kind with a delete route, and delete-and-recreate is legitimate. The live bound stays 20
  (`account_records_api.py:40`), and the guard must count **live** rows against 20 **and total rows (live + tombstones)**
  against a separate larger bound, `ORENA_LIMIT_IMPORT_TOMBSTONES` = **360** (floor **52**, the heavy 1-year volume): heavy import use is of the order of one a
  week (52 a year, [A] unmeasured), 156 in three years x 2.3 (A7, learner-authored) = about 360. It is a **lifetime** count
  per (account, language): tombstones are terminal and cannot be recycled, so only a reviewed tombstone-retention decision
  (reserved with deletion and export) could ever reclaim it; at the heavy rate it is reached in about 7 years. Beyond it a new import is refused with the existing
  422 `import_limit`. A tombstone carries no text (`delete_import`), so 360 of them are small; the rail stops the loop, it
  does not bound bytes.
- **Rev 4 (D-107): the two pools.** The tombstone rule above is the *text-import pool*'s. Media imports have a pool of their own
  (4.5) with its own live and total bounds, so a URL, YouTube or uploaded import never consumes the 20 / 360 of the text pool.
- **Existing defect, fix in code now, independent of this proposal's other rails:** the shipped import guard counts only
  `lifecycle <> 'deleted'`, so create / delete / create is unbounded today against the live 20-import cap. It should be
  fixed and tested (section 9) before :8021 holds anything but test data, and it needs only the tombstone bound as new
  configuration.

**3.3b The generic route is closed, not guarded (review P2-1, C2).** `PUT /api/works/{id}` stops accepting `draft`,
`response` and `conversation`: `GENERIC_WORK_KINDS` (`work_contract.py:27`) becomes empty for writes and the route answers
422 `work_kind_invalid`, the answer it already gives `annotation` and `imported`. Each has a dedicated route that derives a
deterministic id from account, incarnation, language and key. No client uses the generic writer, so the only breakage is
tests (`tests/test_work_api.py`), which move to the dedicated routes (**the implementation commit lists each `tests/test_work_api.py` assertion that moves, so none is dropped**, review P3-8). The reads stay. This removes the client-UUID creator
for all three kinds, **drafts included**, and `MAX_PAYLOAD_CHARS` (`work_api.py:56`) then bounds nothing writable. Drafts
still need a count rail, because `PUT /api/drafts/{key}` creates a row per key (<= 200): `ORENA_LIMIT_DRAFTS` = **2,500**
per (account, language), derived under A7 as heavy about one piece a day = 365 a year, 1,095 in three years, x 2.3 (A3, [A]
unmeasured); rejected with 422 `draft_limit`, never evicted (it is the learner's text). **The draft sender treats 422 `draft_limit` as
terminal for that piece** (review P3-7): it stops sending, does not retry on later autosave pauses, and keeps saying "on this
device" (`draft-sync.js` catch); only a retryable 429 is retried. Drafts are a fifth guarded kind in
the shared helper.

**3.4 Scope.** Counts are per (incarnation, language), the same scope as the import bound and as every `works` row
(`work_repository.py:256-257`). Library rows (`library_items`) are per (user, language). Switching language does not reset a
limit and does not share one, so **the account-wide ceiling is the per-language ceiling times the number of enabled
languages** (review P3-2): two languages (en, zh) double every figure in 4.1-4.4, three triple it. The sizing in section 2 is
per language on purpose (A6). A re-registered account (new incarnation) starts at zero, as its data does.

**3.5 Error contract.** Stable machine codes in `detail.category`, `retryable: false` for counts, `true` for rate; a
`context` of `{limit: N}` only (no learner data, no other account). A 429 carries `retryAfterSeconds` and the **name of the
rail that fired, and no counts or limits of any other rail** (review P3-4), so the response is not a probing oracle for the
others. HTTP: 422 for a count or byte limit (the status
`import_limit` already answers, `tests/test_d4_account_records.py:367`), 429 for rate, 413 `work_too_large` unchanged. **The 429 needs an explicit branch in every route** (review P2-2): `_commit` (`account_records_api.py`), `put_work`
(`work_api.py`), `put_draft`, and `append_conversation_turn` each map every `rejected` outcome to 422 today. A `rate_limited`
reason must be tested for before that line and raised as `orena_http_error(429, 'write_rate_limited', ..., retryable=True,
context={'rail': ..., 'retryAfterSeconds': ...})`; `/api/continue` raises it from its own bucket. The
human-readable `message` is the envelope's existing English developer string ("This change was not accepted."); no new
learner copy is written.

**3.6 Observability, read-only.** One structured log line per refusal: incarnation id, rail name, limit, observed value.
No text, no title, no key. A read-only operator query lists accounts above 80% of any count rail. Both ship with the code;
neither deletes anything.

---

## 4. Per record kind

### 4.1 Reading positions (`library_items`, relationship `started`)

**What exists [V].**
- Payload bounds: `PlaceIn` (`library_api.py:201-216`): `index`/`total` <= 100,000, `title` <= 240, `intent` <= 40 and a
  slug pattern, `segment` <= 255, `context` <= 240, unknown keys refused (`extra="forbid"`). `content_id` <= 255
  (`:247-251`). Kind must be `reading`, `listening` or `book` (`PLACE_KINDS`, `library_repository.py:62`).
- Volume bounds: client throttle 30 s per id unless a boundary is crossed (`continue-sync.js:55-67`); server coalescing
  30 s under the same rule (`PLACE_COALESCE_SECONDS`, `library_repository.py:60`, `:328-335`). `GET /api/continue` returns
  at most 50 (`:61,347`). **No per-account row count. No rate bound on boundary-crossing writes.**
- No receipt, no change record, no stream lock (`0022` docstring; I4). The cost is rows and in-place updates only.

**Failure modes.**
1. *Row creation without limit*: a loop over distinct ids, or F1 (`place: null` on an absent row creates a row no place
   index sees).
2. *Storage channel*: each row carries up to 255 + 240 + 255 + 240 characters of free text (about 3 KB hostile, about 1 KB
   typical with the row's indexes); 5,000 of them is 15 MB per (account, language) at most.
3. *Index bloat*: `place_at` is the key of the partial index `ix_library_items_place`, so every place UPDATE is not HOT,
   writes a new heap tuple and a new index entry. The 30 s coalescing exempts writes that cross a boundary, so a client
   that alternates `index` values writes on every request. The volume assumed in I4 (about 0.5 M updates a day at 20,000
   DAU x 25 writes) is benign; a loop is not.

**Arithmetic.** Heavy: 1.5 new contents a session x 2 x 365 = **1,095 rows a year**, 3,285 in three years (A3, A4); typical
208 a year. At 0.7 KB: 0.77 MB a year heavy, 146 KB typical; 8.6 M rows and 5.7 GB a year at the target. Cap 5,000 =
**1.5 x the heavy 3-year volume, 4.6 years of heavy use** (A7).

**Proposed.**
- `ORENA_LIMIT_PLACES` = **5,000** per (account, language), counted on `started` non-word rows of the three kinds (use
  `ix_library_items_shelf (user_id, language_code, kind, updated_at)` or `ux_library_items_source`; no new index), **checked
  only when `set_place` would insert**.
- **F1 fix as part of the rail:** a `place: null` write to an absent row inserts nothing (it has nothing to unset).
- `ORENA_PLACE_MIN_INTERVAL_SECONDS` = **1**: a write to the same row under 1 s after its last, crossing a boundary or not,
  is answered `coalesced` (an existing status the client already ignores). Legitimate maximum is a paragraph a second.
- `ORENA_LIMIT_PLACE_WRITES_PER_MINUTE` = **120** per account, a token bucket **in process**. Approximate by design: with
  N processes the ceiling is N x 120, which still defeats a loop, and a place write takes no stream lock so there is no
  database counter to read. (The default deployment is one uvicorn process, `Dockerfile:34`.) Legitimate maximum is about 20
  a minute (a fast skim of a listening transcript); 120 = 6x.

**At the limit: evict, never reject.** A place is derived navigation state (D-104 H-12; I4), recoverable by opening the
text again, so the creating transaction makes room rather than refusing: delete the **least-recently-used place-only rows**
in a batch of 100 (hysteresis, so this is one DELETE per 100 creations), ordered by `coalesce(place_at, created_at)`
ascending. "Place-only" is `_place_only()` **plus** `NOT EXISTS (SELECT 1 FROM library_collection_members WHERE item_id =
library_items.id)` (F5). A row that is kept, marked, noted, given a state, or filed is **never deleted**; if the oldest rows
are all saved (a pathological account), clear their `place` and `place_at` instead (the `forget` precedent,
`library_repository.py:489-511`). The response is the ordinary `written`. No error code exists for this rail.

**Concurrency (review P2-3).** Place writes take no stream lock, so two creators at the cap may both evict and both insert;
the overshoot is bounded by the number of concurrent creators and is harmless. The eviction is one statement,
`DELETE FROM library_items WHERE id IN (<ids>) AND <place-only predicate> AND NOT EXISTS (<membership>)`, re-checking the
predicate in the statement itself so a row saved between the select and the delete survives. A concurrent
`PUT /api/continue` for a row that has just been evicted must not fail: `set_place` does `session.get(...)` after its UPDATE
and calls `_place_dict` on the result (`library_repository.py` around `:341-345`), which is `None` for a deleted row (a 500).
The update path therefore treats a vanished row (zero rows updated, or a `None` re-read) as an absent row, takes the insert
branch and answers `written`. A test forces the interleaving (section 9).

**Recorded consequence (review P3-1).** Eviction deletes the oldest place rows, including ones carrying `finished` (Reading
Complete's "Finished"). Acceptable for navigation state, and written down so that a five-year account that no longer shows
an old text as finished is not read as a defect.

**What the client shows.** Nothing new. `sendPlace` and `clearPlace` swallow every failure (`continue-sync.js:69,79`), the
device still holds its continuation list of 20, and no surface claims a place is saved. A 429 from the place bucket is the
same.

### 4.2 Typed responses (`works` kind `response`)

**What exists [V].** `ResponseSave` (`account_records_api.py:278-286`): `answer` and `coaching` <= 4,000 characters each,
`mode` <= 40 with a slug pattern, `sentenceRef` <= 255, `sourceId` <= 200, key <= 255 (`_key`, `:50-53`). Deterministic work
id from the key (`:56`). Worst case per row about 25.5 KB (two 4,000-character fields at 3 bytes, plus `sentenceRef`,
source, row overhead and receipt). The generic route also accepts the kind under a client UUID up to `MAX_PAYLOAD_CHARS`
(200,000 characters, `work_api.py:56,276`). **No count, no rate.**

**Failure modes.** The client mints a fresh key per take (`account-records.js:227`), so a buggy retry loop or a hostile
client creates a row per request, each with a receipt and a change record. Storage channel: 25.5 KB a row; at 25,000 rows
623 MB per (account, language). Note what the receipts add: they are the same 0.65 KB whether the row is 1 KB or 25 KB.

**Arithmetic.** Heavy: 5 takes a session x 2 x 365 = **3,650 a year**, 10,950 in three years; typical 624. Typical row =
0.30 (works) + 0.03 (source) + 1.05 (payload, A8) + 0.65 (receipt + change) = **2.03 KB**: heavy 7.2 MB a year, typical
1.2 MB; 27.6 M rows and 36 GB a year at the target (plus their receipts, already in section 2.3's 58 GB). Cap 25,000 =
**2.3x the heavy 3-year volume, 6.8 years of heavy use**; at typical row size 50 MB per account at cap.

**Proposed.** `ORENA_LIMIT_RESPONSES` = **25,000** per (account, language) via the shared `create_guard`, on `put_response`
**and** on the generic route for kind `response` (F2). `ORENA_LIMIT_RECORD_BYTES` = **128 MiB** of `works.payload` per
(account, language) across all kinds (derivation in 4.3), which binds a hostile account long before 25,000 maximal rows
(128 MiB / 24 KB = about 5,400 rows).

**At the limit: reject, never evict.** A response is the learner's own work (D-104 H-3: learner work, not evidence). It is
never silently dropped to make room. A new key is refused with **422 `response_limit`** (or `record_bytes_limit`),
`retryable: false`; a replay of a committed creation still answers `replay`; updating an existing response is unaffected.

**What the client shows.** `saveResponse` returns `false` and nothing else (`account-records.js:237-239`); the room has
already drawn the coaching and never claimed "kept with your account" for a response (only Writing drafts say that,
`draft-sync.js:10-13`). So no untruthful message exists to correct. The fact that a learner who is at the cap is no longer
kept has **no drawn surface** in the design; per `CLAUDE.md` rule 7 this is recorded in `docs/project/UI_BACKEND_GAPS.md`
when the code lands, not resolved by inventing a notice.

### 4.3 Notes and highlights (`works` kind `annotation`; and the library item note)

**What exists [V].** Per document: `AnnotationSave` (`account_records_api.py:108-115`): <= 80 highlights and <= 120 notes,
highlight sentence <= 400, note text <= 600, ids <= 80, `segment` and `key` <= 255, `at` <= 40; duplicate ids refused
(`:139-146`); one work per content id (<= 255). Uncommitted: <= 500 remembered removed ids (`MAX_TOMBSTONES`, `:38,163`).
Worst payload **191,307 characters, 233,323 with tombstones, about 441 KB in UTF-8** (F3); typical **2,436 characters**
(6 highlights + 3 notes, measured). `clear` is `{cleared: true}` on the same row. The client pushes once the learner stops
changing a text for 1.2 s (`annotations-sync.js:17,47`). The library row's own `note` is <= 2,000 characters
(`library_api.py:82`) on a row that already exists; the **count** of library rows is unbounded (section 8).
**No count of documents, no rate.**

**Failure modes.** A row per content id; and because `works.payload` is rewritten whole on every commit
(`work_repository.py:190-198`) and each commit adds a receipt and a change record, a loop that re-PUTs one document with a
new operation id grows the receipt stream by 0.65 KB and leaves a dead 2 to 233 KB heap tuple per request for vacuum. That
second mode is an update loop on existing rows, which no row-count cap catches; only the rate rail (section 6) does.

**Arithmetic.** Heavy: 0.5 annotated texts a session x 2 x 365 = **365 documents a year** (1,095 in three years), 9
pushes each = 3,285 mutations; typical 62 documents, 312 pushes. Typical document row 0.30 + 0.03 + 2.4 = **2.7 KB**, plus
9 x 0.65 KB of receipts. Cap 2,500 = **2.3x the heavy 3-year volume, 6.8 years**. At cap: 6.7 MB typical; hostile 2,500 x
441 KB = **1.1 GB**, which is why the byte budget exists and why it must also guard growth (3.3).

**Byte budget derivation.** Heavy `works.payload` per year: responses 3,650 x 1.05 KB = 3.7 MB, annotations 365 x 2.4 KB =
0.9 MB, conversation headers 365 x 0.4 KB = 0.15 MB, drafts about 0.6 MB [A] = **5.3 MB a year, 26.6 MB in five years**.
**128 MiB = 4.8x that.** It is a **stored-size** budget (`pg_column_size`, section 3.3: compressed, so it admits roughly 2-3x
its number in logical prose bytes) and it includes tombstones. **`work_turns` content is not in it** (the table has no
account-scoped index and the content is a plain `text` column, so summing it is a scan, not a probe).

**True ceiling per (account, language), all rails at their defaults, hostile content** (review P2-4): `works.payload` stops at
128 MiB stored in total (responses alone could otherwise reach 25,000 x 24 KB = 600 MB logical); conversation turns up to
2,500 x 24 turns x 14.6 KB = about **0.9 GB, outside the budget**; places 5,000 x 3 KB = 15 MB; receipts and change records at
0.65 KB per mutation, bounded by the rate rail rather than a count. The operator-facing ceiling is therefore **about 1 GB of
content plus the stream, per language**, times the enabled languages (3.4). Closing the turns half exactly needs counters
(S2), which the review judges not worth a schema decision before :8000.

**Proposed.** `ORENA_LIMIT_ANNOTATED_TEXTS` = **2,500** per (account, language), via `create_guard` on
`put_annotations`; `ORENA_LIMIT_RECORD_BYTES` as in 4.2, checked on creation and on growth past 32 KB. A `cleared`
document stays a row (its id cannot be reused, `account_records_api.py:13`); it counts toward the 2,500. The document's own
bounds (80/120/500) are unchanged and are the per-document rail.

**At the limit: reject, never evict.** A *new* text is refused with **422 `annotation_limit`**; every text already kept
still updates. Notes are learner-authored; nothing is removed to make room.

**What the client shows.** `pushAnnotations` returns `false` (`account-records.js:91-109`); the highlights and notes stay in
the device's own store, which the Reader and Quick Sheet read first, and no surface claims an annotation is on the account.
No new UI; the same `UI_BACKEND_GAPS.md` entry as 4.2 covers it.

### 4.4 Conversations (`works` kind `conversation` + `work_turns`)

**What exists [V].** Per turn: `text` and `meaning` <= 2,400 characters each, ids <= 80, `origin` <= 40, `support` <= 32,
`expectedHead` <= 24 (`work_api.py:191-204`); the same limits again in the transaction (`work_repository.py:230,343,362-364`).
Per conversation: **24 turns** (`MAX_CONVERSATION_TURNS`, `work_repository.py:229`; refused `turn_limit` at `:336`), role
alternation, unique turn ids, a `title` <= 240 and `situation` <= 1,200 at creation. Key <= 200 (`work_api.py:207-210`).
**No count of conversations; creation has no guard** (`_append_turn.load` returns an empty state when the row is absent,
`work_repository.py:322-323`, with no `create_guard`). Each turn is a mutation: a receipt and a change record.

**Failure modes.** A conversation per key; 24 receipts + change records per conversation; and the worst turn is about
14.6 KB (2,400 + 2,400 Chinese characters at 3 bytes + JSON), so a maximal conversation is about 350 KB of turns + 16 KB of
receipts. 2,500 of them is 0.9 GB.

**Arithmetic.** Heavy: 0.5 conversations a session x 2 x 365 = **365 a year** (1,095 in three years) at 16 turns =
5,840 turns. Typical turn 0.18 + 0.5 = 0.68 KB plus 0.65 KB of receipts = **1.33 KB**; a 16-turn conversation =
16 x 1.33 + 1.0 (header row) = **22 KB**, a 24-turn one 33 KB. Heavy 8 MB a year, typical 1.4 MB; 3.4 M conversations and
44.8 M turns a year at the target (32 GB). Cap 2,500 = **2.3x the heavy 3-year volume**; at cap 54 MB at 16 turns, 80 MB at
24, hostile 0.9 GB.

**Proposed.** `ORENA_LIMIT_CONVERSATIONS` = **2,500** per (account, language), via a `create_guard` on the first turn
(`expectedHead` 0, `work_repository.py:322-323`) and on the generic route (F2). `ORENA_LIMIT_CONVERSATION_TURNS` = **24**:
the existing bound becomes configuration; `TurnAppend.expectedHead`'s hard-coded `le=24` (`work_api.py:193`) follows the
constant. It is not a new quota: it is the product's existing conversation shape (I6).

**At the limit.** A *new* conversation is refused with **422 `conversation_limit`**; existing ones continue to their turn
cap. A conversation at its turn cap answers 422 `turn_limit` as it does today. Nothing is evicted: the learner's words.

**What the client shows.** `appendConversationTurn` stops its queue on any failure ("Stops for good on anything but
success", `account-records.js:118-121,136-138`) and the device keeps the whole conversation, so the room is unaffected. No
new UI; `UI_BACKEND_GAPS.md` entry as above.

### 4.5 Media imports: a pool of their own (rev 4, D-107)

**Decision this implements.** D-107 point 3: media imports use a pool separate from text imports; three rails: the text-import
limits, a media-import item count shared by URL/YouTube and uploads, and an uploaded-media storage-byte limit; defaults from
measurements and storage estimates; an import that cannot sync because of a quota is never shown as saved to the account.

**What exists [V] (re-read at HEAD `83a6037`, rev 5).**
- Text imports are `works` kind `imported`, form `text`, <= 12,000 characters, 20 live (`account_records_api.py` `MAX_IMPORTS`,
  `at_most_the_limit`). `ImportSave.form` is already `text|url|upload` with the media fields `mediaId` (<= 200), `kind`,
  `durationMs`, `thumbnailUrl`, `provider`: a media import is kept as the reference the Listening room opens plus the display
  fields of its library card, never the bytes or a transcript. A tombstone drops title, text and link.
- On the device a media import is a `mediaImports` record, `url:<link>` or `upload:<id>`, capped at 100 (`memory.js`
  `addMedia`), pushed best effort through `placeSink.addImport` -> `pushImport`, which already sends media records through
  `mediaBody` (`account-records.js`).
- An upload is `POST /api/media-learning/upload` (`import/sheet.js`; `media_library_api.py`), streamed with
  `MAX_UPLOAD_BYTES = 64 MiB` enforced per chunk (`_stream_upload`), stored by `import_upload` (`media_source_import.py`): the
  original at `media/<token>/original<ext>` in the asset store, a thumbnail at `media/<token>/thumbnail.jpg` (a 640 px video
  frame, or the audio file's embedded artwork, **which the code does not cap**), and an entry in the media library. **No
  per-account count and no per-account byte limit exist.** Uploads stored before the import record existed have an entry and
  no record.
- **The media library is one `index.json`** (`FileMediaLibraryStore`, `media_library_store.py`). See G1 (section 8): it is a
  gate, not a side note.

**Failure modes.** A loop of uploads fills the asset store (64 MiB a request; at the 120/min rail, 7.5 GiB a minute without a
byte rail); a loop of URL imports adds index entries and works rows; create-delete-create repeats either.

**Arithmetic (A10-A12, all unmeasured except the 64 MiB cap).**

| | Heavy | Typical |
| --- | --- | --- |
| Uploads a year | 100 | 12 |
| URL/YouTube imports a year | 260 | 24 |
| Media items a year (the shared count) | **360** | **36** |
| Upload bytes a year (15 MiB mean + about 0.07 MiB thumbnail) | **1.47 GiB** | **0.18 GiB** |
| Index entries (about 2 KB without transcript) | 0.7 MB | 0.07 MB |

- **Count.** Heavy 3-year volume 1,080 items; x 2.3 (A7) = 2,484, so the **total with tombstones is 2,500**. The **live** bound
  is **1,250**. It is below the 2x of A7 (2,500) on purpose: it is the heavy 3-year volume with not one deletion (1.16x), and a
  live set is something a surface has to show and a store has to hold, so the 2x allowance is given to the *total* (which also
  carries the delete-and-recreate churn), not to the live count. If the reviewer prefers the plain A7 rule, set both to 2,500.
  (The text pool's 20 live is a product bound; its 360 total is the same derivation from 52 imports a year.) Both values are
  provisional until upload frequency is measured (rollout step 0b).
- **Bytes.** Heavy 3-year volume 4.4 GiB; x 2.3 = 10.1, so **10 GiB per account**. It counts the **live** uploads' original and
  thumbnail; a tombstone carries no bytes (D-107 point 2 deletes the owned files). It is per account across languages, not per
  language: bytes are a storage cost, not a language-scoped record, and a bilingual learner should not get two ceilings of the
  most expensive resource. Floors: 1.5 GiB (heavy 1-year volume).
- **Rate.** `ORENA_LIMIT_UPLOADS_PER_HOUR` = **30**: a heavy sitting imports at most 10 files (A12), x 3. At 30 x 64 MiB the
  ceiling per account is 1.9 GiB an hour.
- **Aggregate at the target**, expected use and no deletions: 5,000 x 1.47 GiB + 15,000 x 0.18 GiB = **about 9.7 TiB of uploaded
  media a year**, about 29 TiB in three. The *worst case* of every account at its cap (100,000 x 10 GiB = 1 PiB) is not the
  planning number. **The capacity of the asset store (today a filesystem store, `FilesystemBookAssetStore`, with an S3-compatible
  backend named as a future seam) is an infrastructure and cost decision for the human**; the byte rail is the per-account
  bound inside it, and a lower value (for instance 2 GiB) is a configuration change, not a code change. Whether a lower value is
  a product allowance is not decided here and is not shown to learners.

**Proposed.**
- The pool is chosen by the record's `form`: `text` -> text pool; `url` and `upload` -> media pool. (`ImportSave.form` gains
  `upload` in the implementation; today `form: url` is used for media links, so no article-URL form is affected unless one is
  added; question Q13.)
- `ORENA_LIMIT_MEDIA_IMPORTS` = **1,250** live and `ORENA_LIMIT_MEDIA_IMPORTS_TOTAL` = **2,500** per (account, language), counted in
  the shared create guard (3.3) with the same all-rows aggregate; reject with 422 `media_import_limit`.
- `ORENA_LIMIT_MEDIA_UPLOAD_BYTES` = **10 GiB** per account. **Enforcement is two-stage** (review P2-6):
  1. *Pre-check before the body is accepted.* The upload route reads, from the account's records and without touching the
     stream lock, (a) the **hourly rail**, counted from the account's upload records' `created_at` **including tombstones**, so
     delete-and-retry does not reset it; (b) the **live count** against the pool bound; (c) **live bytes plus the declared
     `Content-Length`** against the byte rail (a missing or understated length does not skip the check: the per-chunk 64 MiB
     bound still applies and stage 2 decides). A pre-check refusal answers 422 or 429 **before any of the body is read or
     stored**, so an account at its limit cannot make the server receive, store, reject and delete 64 MiB bodies, and a
     refusal does not rewrite the media index (G1).
  2. *The authority, inside the creating transaction.* After the stream, the account's import record is committed in
     `commit_mutation` with a `create_guard` that sums the live uploads' recorded bytes and refuses when the sum plus the
     new file exceeds the limit. A refusal there deletes the just-stored files and the library entry before answering 422
     `media_bytes_limit`. Stage 1 is advisory; stage 2 is the rule.
  The stream lock is taken at commit, so it bounds nothing *during* an upload. The overshoot of concurrent uploads that pass
  stage 1 together is bounded by **HTTP concurrency times 64 MiB** (review P3-7), not by the lock; the hourly rail (counted from
  records, stage 1) and the per-connection limits bound the concurrency. Files orphaned by a crash between the store and the
  commit need a sweeper (code, not designed here).
- **Bytes and ownership come from the stored entry, never from the client** (review P3-2). For form `upload` the server resolves
  `mediaId` to the stored media-library entry, requires that it be **visible to this account** (its personal owner) and refuses an
  unknown or foreign id (404 `work_not_found`-style, no oracle), and takes `bytes` (original plus thumbnail) and the asset keys
  from that entry; the client's body carries no size. Otherwise the byte sum could be forged downward or another account's
  file claimed.
- **Uploads stored before an import record existed** (review P3-3) have an entry and no record, so they are not in the byte
  sum. **Proposed: ignored, not back-filled.** They are lane-era test data; a back-fill would be a bulk device-to-account
  migration of the kind D-104 H-6 forbids, and the next upload of that file by the learner creates its record. Stated so the
  sum is not read as complete for such files.
- **The embedded-artwork thumbnail is capped** (review P3-4): audio artwork is resized to the same 640 px JPEG bound as a video
  frame (code change in `_persist_thumbnail`/`embedded_audio_artwork`), so one request costs at most 64 MiB plus a fixed
  thumbnail (about 100 KB at the A11 estimate; a hard 512 KB limit in code).
- Each pool has its own tombstone bound (text 360 total, media 2,500 total). **Deleting a media import deletes its files on the
  last live reference** (review P3-6): two import records, for instance from two devices, may name one `mediaId`, so deleting
  one record must not delete a file another live record uses; the file is removed when the last live record naming it is
  deleted.
- **Removal-pending bytes stay in the sum** (review P3-5): a deleted record's bytes leave the live sum only when the file removal
  is **confirmed**. A removal that fails is retried and, until it succeeds, the bytes still count, so the retry window cannot
  let disk grow beyond the rail. The worst case is bounded by 2,500 total rows x 64 MiB, and a pending removal is logged for the
  operator.

**At the limit: reject, never evict, and never show it as saved (D-107 point 3).** A learner's import is theirs; nothing is
removed to make room. The rule: **an import the account refused for quota is never presented as saved to the account.** Two
cases:
1. *Upload* (the upload route is the creator): a refusal stores nothing, and nothing is added to the device library. The sheet
   already reports upload failures by category in the learner's language (`import/sheet.js:236-263`: `media_upload_invalid`,
   `media_upload_unavailable`); a refused upload is one more category through the same pattern. **No copy for it is drawn in the
   design: that copy (en, vi, zh) is a design gap for the human** (`CLAUDE.md` rule 7), recorded in `UI_BACKEND_GAPS.md` when the
   code lands.
2. *URL/YouTube and text imports*: today the device record is created first and the account push is best effort and silent, so a
   quota refusal would leave a device-only item that looks like every other. Recommended: **account first, device second** while
   the backbone is `active` (the import is added to the device library only after the account accepted it, or when the backbone
   is `disabled`, where nothing claims an account copy), and a refusal is shown through the same sheet error pattern. If the
   human prefers to keep a **local-only fallback**, the learner must be told explicitly that the item is on this device only;
   **no drawn pattern exists for that on an import** (the only one is the Writing draft's "on this device" status,
   `draft-sync.js`), so this too is a design gap for the human and not something to invent.

**Transient failures are not refusals (review P2-7).** Only a **definitive 422 `*_limit`** (`import_limit`,
`media_import_limit`, `media_bytes_limit`) blocks an import and shows the category error. **Offline, a 5xx, a timeout or a 429
are not quota refusals**: they use the sheet's same failure pattern ("could not import, try again") and **create no
device-only item while the backbone is `active`**, so a retry is possible and nothing is half-saved. A 429 is retryable by
definition (`retryAfterSeconds`). A device-only item created *before* this rule (or while the backbone was `disabled`) remains
readable and is **not claimed as saved to the account**; no sweep converts it (D-104 H-6). A local-only fallback stays a human
design decision with an explicit label (above).

---

## 5. Receipts and change records: the growth, and who owns it

**DECISION FOR THE HUMAN/ARCHITECT.** AGENTS section 7 reserves "receipt compaction"; ADA section 5 requires a versioned
retention policy and forbids inventing retention days. This section gives the numbers and the options. It does **not**
select a window and proposes **no deletion code**.

**5.1 What exists [V].** Every committed mutation inserts one `change_records` row and one `mutation_receipts` row in its
own transaction (`mutation_commit.py:196-225`). Nothing deletes from either (no `DELETE`/`DROP` over them in
`writing_coach/` or `scripts/`). Indexes exist for oldest-first compaction: `ix_mutation_receipts_stream (incarnation_id,
sequence)` was created for it ("Compaction reads oldest-first", `0005:126-132`), and `uq_change_record_sequence` orders the
stream. The change feed `GET /api/works/changes` (`work_api.py:127`) has **no client** (tests only).

**5.2 Growth (section 2.3).** 93.5 M mutations a year from the four kinds, **389.8 M** with autosave drafts (A5, measured
cadence): receipts 165 GB, change records 79 GB, **244 GB a year** at the target, for ever.

**5.3 What must be kept.**
- *Receipts*: deduplication of every operation that can still be retried. ADA section 5: "never forget a receipt and then
  accept its old ID as a new write": retain a minimal marker or **reject expired operation epochs**. The second needs an
  operation id that encodes or implies its age (for instance UUIDv7), or a per-incarnation floor the server can compare
  against; today ids are `op-<uuid4>` (`account-records.js:19`, `draft-sync.js:150`), which carry no time. That is a client
  contract change and possibly a schema one.
- *Change records*: the pull cursor (ADA section 5) and the **tombstone** of a deleted object, so an older client cannot
  resurrect it. "A client older than retained change history must fetch a fresh snapshot": **no snapshot endpoint exists**
  (`GET /api/works` is a bounded list of 50). So change records cannot be compacted before the sync protocol (reserved)
  defines a snapshot and a horizon.
- *Audit*: the receipts are not the audit of record for learner content; deletion has its own journal (D-055). A receipt's
  `request_digest` is a SHA-256 of the operation's text (`semantic_digest`, `work_repository.py:33-46`), which survives the
  deletion of the content; the D-055(b) enumeration should decide whether that digest is "content".

**5.4 Options** (for the reviewer to rank; the arithmetic uses the all-mutations volume):

| Option | Effect | Needs |
| --- | --- | --- |
| **A. Keep everything for now** | 244 GB/year, 780 M rows/year; a few years of runway on one PostgreSQL instance | nothing; revisit at a fixed trigger (for instance receipts > 100 M rows or 100 GB) |
| **B. Receipt time window W** | steady-state receipts: W = 30 d 13.6 GB, 90 d 40.8 GB, 180 d 81.6 GB (vs 165 GB a year) | an expiry epoch for operation ids (client contract or schema), a policy value **supplied by the human**, an operator job under a human gate |
| **C. Keep-latest-per-object change records** | about 34 M rows a year (the number of `works` created), 6.8 GB, instead of 390 M | sync protocol: sequence gaps legal, consumers re-read an object by id; reserved |
| **D. Partition `mutation_receipts`/`change_records` by month and detach old partitions to cold storage** | removes growth from the hot table without deleting; dedup for old ops then needs the archive or an epoch | schema decision (section 7), reserved |

**Recommendation (non-binding).** A for the lane and for :8021; the limits of section 4 and the rate rail of section 6 cap
what one account can add to the stream; **the receipt-growth owner is the Principal Architect role** (AGENTS section 1),
who defines the versioned retention policy and horizon (ADA section 5); the operator executes it under the human gate; the
trigger above goes in `CURRENT_HANDOFF.md`. The IMPLEMENTATION_REVIEW P2-4 condition asks for an owner, not for compaction,
before :8000. Autosave is **76% of the mutations** (measured cadence, 2.4) and is the
cheapest to reduce at the client (the serialised sender in `draft-sync.js:147-200` already keeps one request in flight).

---

## 6. Rate limiting is a separate rail from counts

Counts bound *how much is kept*; they do not bound *how often a row is rewritten*. A loop that re-PUTs one annotation
document or one draft with a new operation id creates no new row and passes every count, yet adds 0.65 KB of receipts per
request and rewrites a payload. So a rate rail is required, and for the same reason it must **not** reuse the counts.

**Stream mutations** (everything through `commit_mutation`): per **account**, `ORENA_LIMIT_WRITES_PER_MINUTE` = **120**
and `ORENA_LIMIT_WRITES_PER_HOUR` = **3,600**, evaluated in the same transaction, after the stream lock and the receipt
lookup, skipped on a replay. No schema and no counter table, and **an O(1) lookup, not a walk** (review P2-2, C3):
sequences are gap-free per incarnation (allocated from `account_streams.next_sequence` under the lock and rolled back with
the transaction, `mutation_commit.py:106-112,187-194`) and the head `H` is already read. The record at sequence `H - 120` is the
first of the 120 previous mutations, so if it is under 60 seconds old, 120 mutations have already landed in the last
minute and the **new one would be the 121st, which is refused** (the 120th is admitted):
`SELECT created_at FROM change_records WHERE incarnation_id = :inc AND sequence = :h_minus_n`, a probe of the unique index
`uq_change_record_sequence (incarnation_id, sequence)` plus one heap fetch, once per rail (two probes per mutation). The
walk of rev 1 (`OFFSET 239`) is dropped: it fetched the heap for every skipped row. **Fallback only if a later compaction
creates gaps** (reserved, section 5): a missing sequence at `H - N` reads as "not enough history", i.e. under the rail, and
compaction must then keep a floor of the newest 3,600 change records per account. The refusal is **429
`write_rate_limited`**, `retryable: true`, `context: {rail, retryAfterSeconds}`, raised through the explicit per-route
branch of section 3.5.

**Why these numbers (re-derived in rev 4 from the measured cadence, 2.4).** Measured single-device ceilings: drafts 20.7 saves a
minute at the pathological worst (1,242 an hour if sustained), 12.2 for a fast typist; notes 9.3 a minute; conversation turn
about 12 a minute and response about 4 a minute by human turn-taking [A]. The theoretical maximum of the draft path is one save
per about 1.3 s, **about 46 a minute**. A learner can have two devices open, so the minute rail is sized as **two devices at the
theoretical maximum plus 30% headroom: 2 x 46 x 1.3 = 120 a minute** (rev 3's 240 was sized against an unmeasured cadence; it is
now 5.8x the worst measured single-device minute and 2.6x the theoretical one-device maximum). The hour rail keeps **3,600**: it
is 2.9x the worst measured single-device hour (1,242), 1.4x two devices doing that for a whole hour (2,484), and 1 a second; the
average heavy learner needs 62,050 mutations a year, about 170 a day (7 an hour on average). A runaway at 10 requests a second is held to 1 a second, a
10x reduction, and to at most 86,400 a day per account. If the lane or production telemetry shows more headroom is needed, raise
the hour, not the minute.

**Place writes** take no stream lock and write no change record, so the query above cannot see them. Two complementary
rails (4.1): the per-row interval (exact, from the row's own `place_at`) and the in-process per-account bucket
(approximate). A per-account place counter table would make the second exact; it is a schema decision (section 7) not
justified by a rail whose purpose is to stop a loop.

The place bucket is per process, so with N workers the ceiling is N x 120 (review P3-3); a change of worker count is
recorded as a deployment note in `CURRENT_HANDOFF.md`.

**What this does not defend against.** Many accounts. Per-account rails cannot stop an actor who creates accounts; that is
sign-up abuse control (Cloudflare, OAuth, the human gates in AGENTS section 10) and out of scope here.

---

## 7. Migration and index needs

**None for the recommended design.** Every check uses an existing index:

| Check | Index | Schema change |
| --- | --- | --- |
| Count and bytes of `works` by kind | `ix_works_scope_sequence (incarnation_id, language_code, updated_sequence, id)` (`0005:217-222`), `kind` and `payload` from the heap | none |
| Count of `started` place rows | `ix_library_items_shelf (user_id, language_code, kind, updated_at)` or `ux_library_items_source` (`models.py:688-698`) | none |
| Eviction order | sort of at most 5,000 rows in one account | none |
| Stream rate | `uq_change_record_sequence (incarnation_id, sequence)` (`0005:164`) | none |

**Optional, each a schema decision needing the AGENTS section 7 process** (proposal -> independent architecture review ->
human approval -> rehearsal on a throwaway PostgreSQL -> the human applies; the implementer may not self-approve):

- **S1.** A partial index `works (incarnation_id, language_code, kind) WHERE lifecycle <> 'deleted'`, **only if** the
  rehearsal at cap shows the creation guard costing more than about 50 ms. Expectation [I]: not needed.
- **S2.** A usage-counter table or columns (rows and bytes per account, language and kind) maintained in the stream
  transaction, for an exact byte bound on every write rather than on creation and growth. The stream row is already
  locked, so it adds no contention. Worth it only if the reviewer wants the hostile case in 4.3 closed exactly.
- **S3.** Anything for section 5's options B-D.

---

## 8. Adjacent creators this proposal does not size, and gaps

- **G1 (restated in rev 5, review P2-8): a GATE for enabling anything beyond :8021.** The media library is one `index.json` for
  every account (`FileMediaLibraryStore`, `media_library_store.py`). (a) `get()` reads and integrity-hashes the **entire**
  file on every call, and every personal-media read goes through it (the media file and thumbnail route once per image request,
  `visible_to` resolution, dictation and shadowing progress, `/api/media/my`), so at about 2.3 M entries a year
  (A10; 360 x 5,000 + 36 x 15,000; about 4.7 GB of JSON a year before transcripts) a request would parse a multi-GB file. (b)
  `upsert` and `delete` rewrite the whole file. (c) **Hazard:** `_read` returns an empty map when the index is corrupt or
  unreadable, and `upsert` then writes only the new entry, so one failed read followed by any upload erases every other
  account's entries. (d) The lock is a per-process threading lock. Per-account limits bound one account, not this file, so they
  are not sufficient. **Gate:** before enabling beyond :8021, personal media entries leave `index.json` (PostgreSQL, a schema
  decision reserved by AGENTS section 7, through the proposal -> independent architecture review -> human approval ->
  rehearsal process, owner the Principal Architect with the media owner) **or, at minimum,** the store refuses to write after a
  failed read. Recorded here, not decided. **Correction (2026-10-01):** only uploads and admin imports create index entries (a learner's link import does not), so the growth is about 680 k personal entries a year, about 1.4 GB of JSON, not the 2.3 M entries counted above; the conclusion stands. The move is proposed in `MEDIA_METADATA_POSTGRES.md` (D-108.5).
- **G2 (restated in rev 5, review P2-9): a GATE for enabling anything beyond :8021.** `GET /api/imports` is bounded at 50
  (`work_api.LIST_LIMIT`) and the device keeps 100 media records, so a new device sees at most the 50 newest imports of an
  account although the pool admits 1,250: **from the 51st import, "opens on a new device" is silently false.** Until the list
  is paged (a cursor), **the effective product bound is 50** and the pool numbers must not be treated as usable. Gate: page
  the list (or raise the limit with a cursor) before enabling beyond :8021.
- **Library items** (`POST /api/library/items`, `library_api.py:69-72,116`): a row per (kind, `source_id` <= 255,
  relationship); the row's note is <= 2,000 characters. The count of **kept/marked** rows is unbounded. Saved words
  (`saved_words`) are owned by the vocabulary domain.
- **Collections**: `COLLECTION_LIMIT = 200` (`library_repository.py:54`) limits a *read*, not creation (`:545-562`).
- **Kept-word provenance** (`POST /api/library/vocabulary/{word}/provenance`, `account_records_api.py`): a
  `language_provenance` row and a receipt per operation, `focus` <= 1,200; no count.
- **Drafts** are no longer adjacent: a guarded kind (3.3b), and they pass through the rate rail.
- **Speech attempts** (`speaking_attempts`): bounded by the speech domain, not by this proposal.

---

## 9. Test plan

Unit and API tests with the limits set small through the environment (the module reads them once, so the test sets them
before import or uses a config seam), then the full suite. **PostgreSQL-only proofs are LOCAL EXECUTION, not CI evidence**, and the completion report must say so
(`ORENA_TEST_POSTGRES_URL`; CI has no PostgreSQL service, IMPLEMENTATION_REVIEW P2-7). Everything that touches `FOR UPDATE`, the
stream lock, `pg_column_size`, TOAST, races and concurrency in the rows above is in that class (review C5).

| Area | Test |
| --- | --- |
| Each count rail (responses, annotated texts, conversations) | N-1 succeeds, N succeeds, N+1 refused with the exact code and HTTP status; `retryable: false`; `context.limit` equals the setting |
| Race | N+1 concurrent creations at N-1 admit exactly one (mirror the import barrier test, `tests/test_d4_account_records.py` near `:367`) |
| Replay | a committed creation retried at the limit answers `replay`, not a refusal; an update of an existing row at the limit succeeds |
| Scope | another language and another account are unaffected; a re-registered account starts at zero |
| F2 / C2 | the generic `PUT /api/works/{id}` answers 422 `work_kind_invalid` for `draft`, `response`, `conversation`; the dedicated routes still work; the draft rail refuses the 2,501st key |
| F6 / C1 | a create-then-delete loop on the import route stops at the tombstone bound; creation with `lifecycle: deleted` is refused for every non-import kind; the 20-live-import behaviour is otherwise unchanged. **This test and its fix land first, alone.** |
| Eviction race (P2-3) | a place PUT interleaved with the eviction of its row answers `written`, never a 500; the eviction statement does not delete a row that became saved between select and delete |
| Rate boundary (P3-6) | exactly 120 mutations in 60 s are admitted; the **121st** is 429; likewise 3,600 admitted and the 3,601st refused in the hour |
| Draft terminal (P3-7) | after a 422 `draft_limit` the draft sender stops for that piece: no retry on later autosave pauses, state stays "on this device"; a 429 (retryable) is retried on the next pause |
| 429 mapping (P2-2) | `_commit`, `put_work`, `put_draft`, turn append and `/api/continue` each return 429 with `rail` and `retryAfterSeconds` and no other rail's numbers |
| Rate lookup (P2-2) | the guard issues point probes at `H - 120` and `H - 3600` (assert the SQL, not a walk); a gap at `H - N` reads as under the rail |
| Stored vs logical (P2-4) | a compressible payload counts as its `pg_column_size`; the budget test uses incompressible text so compression does not defeat it |
| F1 | `PUT /api/continue/{id}` with `place: null` on an absent row inserts nothing |
| Place eviction | at 5,000, the next insert evicts the 100 oldest place-only rows; kept, pinned, noted, stated and **filed** rows are never deleted; saved rows lose only `place`; the written status is `written` |
| Place rate | same-row writes under 1 s answer `coalesced`; the per-account bucket returns 429 after 120 in a minute, recovers after it |
| Byte budget | a response of maximal size stops being accepted near 128 MiB; an annotation growing past 32 KB is checked; a growth under 32 KB runs no aggregate (assert query count) |
| Stream rate | the 241st mutation in 60 s is 429; a replay in the same window is not; the hour rail likewise; 429 is retryable and a retry after the window commits |
| Config | non-integer, zero, negative and below-floor values fail startup with the variable named; defaults load |
| Client | node gates: a 422 or 429 leaves `saveResponse`, `pushAnnotations`, `appendConversationTurn` and `sendPlace` silent, never sets the draft state to `account`, and the draft sender still says "on this device" on a 429 (`draft-sync.js` catch) |
| Size at cap | extend `scripts/rehearse_learner_records_schema.py --volume` (or a sibling) to load one account to every cap and record guard latency, `pg_total_relation_size` per table (replacing section 2.2), and the TOAST behaviour of `pg_column_size` |
| Media pool (rev 4) | text and media imports do not consume each other's bounds (20 text imports leave room for media, and conversely); the media live, total and tombstone bounds each refuse with `media_import_limit`; create-delete-create on the media pool stops at the total |
| Upload bytes (rev 4) | the upload that would cross 10 GiB (set small in the test) is refused with `media_bytes_limit`, its files and library entry are removed, nothing is added to the device library; deleting an upload frees its bytes; concurrent uploads overshoot by no more than one file each |
| Upload pre-check (P2-6) | at the byte, count or hourly limit the upload is refused **before the body is read** (assert zero bytes stored and no index write); the hourly count includes tombstones, so delete-and-retry does not reset it |
| Transient (P2-7) | offline, 5xx and 429 on an import create no device item while `active` and show the retry failure pattern; only a 422 `*_limit` shows the category error |
| Ownership (P3-2) | an upload record naming an unknown or another account's `mediaId` is refused; the byte sum uses the stored entry's size, not a client field |
| Shared file (P3-6) | deleting one of two records naming one `mediaId` keeps the file; deleting the last removes it; a failed removal keeps its bytes in the sum until confirmed |
| Artwork cap (P3-4) | an audio file with oversized embedded artwork stores a thumbnail within the cap |
| Not shown as saved (D-107.3) | a refused import leaves no device-library item while the backbone is `active`; with the backbone `disabled` behaviour is unchanged; node gate on the sheet error category |
| Rate re-derivation | 120 admitted and the 121st refused per minute; 3,600 / 3,601st per hour; uploads 30 / 31st per hour |
| Regression | the existing bounds (20 imports, 24 turns, annotation and response field maxima, `work_too_large`) unchanged |

**Rollout.**
0. **Precondition (review P3-5, C5), draft cadence DONE in rev 4 (2.4)**: scripted typing on :8021 measured 3.7-20.7
   saves per active minute. What remains is observation on real use: log mutations per account per minute and hour from
   `change_records` on :8021 for a fixed period and compare with 2.4 and with the A2-A4 shape. If the observed maximum
   approaches 3,600 an hour, raise the hour rail, not the minute. Record in `CURRENT_HANDOFF.md` that A2-A4, A10-A12 and
   section 2.2 are unmeasured, that the rate numbers rest on a scripted measurement, and the per-process place-bucket note.
0a. Fix the existing import tombstone defect (3.3a) first and alone.
0b. **Measure upload size and frequency on the lane before the byte and count defaults are fixed** (review condition 5; not done
   in this revision): record, per account over a fixed period on :8021, the size of each upload (original and thumbnail), uploads
   and URL/YouTube imports per week, and deletions, and compare them with A10-A12 (mean 15 MiB, 100 uploads and 260 links a year
   for heavy). The 10 GiB, 1,250 / 2,500 and 30-an-hour defaults are provisional until then. PostgreSQL-only results are local
   execution, not CI evidence.
0c. **Gates before enabling anything beyond :8021 (D-107 point 5, review P2-8 and P2-9):** G1 (personal media entries out of
   `index.json`, or a no-write-after-failed-read guard at the least) and G2 (paged imports list).
1. Independent review of this document (AGENTS section 1). Nothing else is implemented before it.
2. Implement in the lane `codex/work`, limits **on by default** (they are rails, not features), one commit per rail.
3. Run the section 9 tests on the lane sandbox with low limits and again with the defaults; record local-execution
   evidence; add the PostgreSQL service job when CI gets one.
4. Independent code review of the implementation. Report `UI_BACKEND_GAPS.md` entries (4.2-4.4).
5. **The human's gate** for :8000/:8010 is unchanged and separate: this proposal removes P2-4's "caps" condition, names the
   receipt-growth owner, and supplies the decision list below; it does not enable anything.

---

## 10. Questions for the reviewer

Rev 2: the reviewer's answers to the twelve questions (`ACCOUNT_RECORD_LIMITS_REVIEW.md`) are adopted as written: sizing rule kept
and labelled an assumption; per (account, language); evict places; creation plus growth is enough for the byte rail and
counters (S2) are deferred; 422 with `<kind>_limit`, 429 for rate, no 507; cleared annotations count; 240/min adopted then (120/min from rev 4), raise the
hour first if needed; in-process place bucket accepted; Principal Architect owns receipts with option A and a written trigger
(receipts above 100 M rows or 100 GB, or one year from first production enablement, whichever first, in
`CURRENT_HANDOFF.md`); the digest in a deleted import's receipt is learner-derived data, covered by the D-055(b) enumeration
of `mutation_receipts`; residual accepted once F6 is closed; this round is the four kinds plus drafts, with library rows,
collections and provenance next; no learner notice. Questions 1-12 below are kept for the record; the ones rev 2 still
leaves open are Q7 (hour rail, pending measurement) and Q9 (the trigger value, for the human).

1. **Sizing rule (A7).** Is "evictable state >= 1.5x, learner-authored >= 2x the heavy 3-year volume" the right yardstick,
   and is the heavy profile (A3-A5) plausible? The defaults move linearly with it; appendix A reruns it.
2. **Place cap scope.** Per (account, language) or per account across languages? A bilingual learner has two scopes here.
3. **Eviction versus reject for places.** Agree that a place is derived and evictable, and that the eviction predicate adds
   collection membership (F5)? Is clearing `place` on a saved row acceptable in the pathological case?
4. **Byte budget.** Is checking on creation and on growth past 32 KB enough (the residual is rows that grow after creation,
   bounded by their per-row maxima), or is exactness (S2, counters) worth a schema decision before :8000?
5. **Reject code and status.** Keep 422 with `<kind>_limit` as `import_limit` does, or use 409 or 507 for capacity? The
   client ignores the difference today.
6. **Annotation cleared rows.** A cleared document stays a row and counts. Acceptable, or exclude `cleared` rows from the
   count (a JSON predicate on a non-indexed column, evaluated only on creation)?
7. **Rate rail numbers.** (Rev 4: now 120 a minute and 3,600 an hour, re-derived from the measured cadence, section 2.4.) Rev 3 sized 240 and 3,600 against A5, which was a guess. Is the hour rail too tight
   for a long writing session? The draft cadence should be measured on the lane before this is fixed.
8. **Place bucket in process.** Is an approximate per-process bucket acceptable for a navigation write, given one uvicorn
   process today and a possible Redis or database counter later?
9. **Receipts (DECISION FOR THE HUMAN/ARCHITECT).** Is the Principal Architect role the right owner, is option A acceptable
   as the lane and :8021 posture, what trigger should force the decision (size, row count, date), and does the digest in a
   deleted import's receipt count as content for D-055(b)?
10. **Creating the row is the gate.** The guards run at creation; a hostile account can still fill its cap and then grow
    each row to its maximum. Is that residual acceptable given the rate rail?
11. **Adjacent creators (section 8).** Include library rows, collections and provenance in this round, or keep the round to
    the four kinds the human named?
Rev 5: the re-check's answers to Q13-Q16 are adopted. Q13: an explicit table `text -> text pool; url, upload -> media pool` in
code, and any future form (for instance an article URL that stores fetched text) names its pool when it is added; the pool is
never inferred from the presence of a link. Q14: 10 GiB per account is acceptable as a safety rail across languages, kept as a
configuration value with capacity and any lower product allowance the human's decision, and the default is fixed only after
upload size and frequency are measured on the lane. Q15: account first, device second for definitive refusals, with the
transient rule above; a local-only fallback only with a human-chosen explicit label. Q16: the Principal Architect with the
media owner, through the AGENTS section 7 schema process, **before** enabling beyond :8021.

13. **Pools (rev 4).** Is `form` the right discriminator, and is a URL import of an article (if one is added) text or media?
14. **Byte default.** Is 10 GiB (A7 on the heavy 3-year volume) acceptable as a safety rail, with the asset-store capacity and any
    lower product allowance left to the human? Should it be per language instead of per account?
15. **Account first, device second** for URL/YouTube and text imports (recommended), or keep a local-only fallback with an
    explicit label (a design gap)?
16. **G1.** Who takes the media index move to PostgreSQL, and before or after :8000?
12. **Learner surface.** Confirm that no notice is drawn for a rail (4.2-4.4) and that recording the gap in
    `UI_BACKEND_GAPS.md` is the right outlet.

---

## Appendix A. Reproducing the arithmetic

The figures in sections 2-5 come from the following model; the profile dictionary is the only input.

```python
KB = 1024
RC, WK = 0.657, 0.30                      # receipt+change per mutation, works row overhead (KB)
PLACE, RESP, ANN, TURN, HDR = 0.70, 1.05, 2.4, 0.68, 0.7   # KB per place row / response payload / annotation payload / turn / conversation header
P = {  # n accounts, active days, sessions/day, places, responses, annotated texts, pushes, conversations, turns, draft saves/yr
  "heavy":   dict(n=5000,  days=365, sess=2, place=1.5, resp=5, annot=0.5, pushes=9, conv=0.5, turns=16, drafts=9.0 * 15 * 365),
  "typical": dict(n=15000, days=208, sess=1, place=1.0, resp=3, annot=0.3, pushes=5, conv=0.5, turns=10, drafts=3.7 * 15 * 60),
}
for p in P.values():
    s = p["days"] * p["sess"]
    p["mut4"] = s * p["resp"] + s * p["annot"] * p["pushes"] + s * p["conv"] * p["turns"]
    p["mutall"] = p["mut4"] + p["drafts"]
print(sum(p["n"] * p["mutall"] for p in P.values()) / 1e6)        # 389.8 (M mutations a year; 338.8 in rev 3 with the unmeasured A5)
print(sum(p["n"] * p["mutall"] for p in P.values()) * RC / KB**2) # 244 (GB of receipts + change records)
```

Sizes measured rather than estimated: annotation payloads (2,436 characters typical; 191,307 worst without and 233,323
with tombstones; about 441 KB in UTF-8 with Chinese text) come from `json.dumps` over payloads built with the field maxima in
`account_records_api.py:94-106`. Everything marked [I] in section 2.2 is to be replaced by `pg_total_relation_size` at
volume.

---

## Rev 2 changes (answering `ACCOUNT_RECORD_LIMITS_REVIEW.md`)

| Finding / condition | Edit |
| --- | --- |
| **P1-1 / C1** delete bypasses every count | New F6 (Summary); 3.3 aggregate counts all rows incl. tombstones; new 3.3a (no `deleted` on creation for kinds without a delete route; imports: live 20 plus `ORENA_LIMIT_IMPORT_TOMBSTONES` (200 in rev 2, 360 from rev 3) with derivation); states that the **live 20-import cap already has this defect, to be fixed in code first and alone**; byte budget includes tombstones; defaults table; test row F6 |
| **P2-1 / C2** `draft` uncapped via the generic route | F2 reworded; new 3.3b closes the generic writer for `draft`/`response`/`conversation` (no client uses it; tests move) and adds `ORENA_LIMIT_DRAFTS` = 2,500 with derivation; section 8 drops drafts; test row F2 |
| **P2-2 / C3** rate lookup not O(1); 429 mapping | Section 6 rewritten: point probe at `head - N` on `uq_change_record_sequence`, gap fallback, compaction floor; 3.5 adds the explicit per-route 429 branch (`_commit`, `put_work`, `put_draft`, turn append, `/api/continue`); test rows |
| **P2-3 / C4** eviction DELETE vs place UPDATE race | 4.1 Concurrency paragraph: single re-checked DELETE; vanished row in `set_place` takes the insert branch and answers `written`; test row |
| **P2-4 / C4** stored vs logical size; `work_turns` | 3.3 and 4.3: budget is a stored-size (`pg_column_size`) budget; `work_turns` excluded and why; true per-language ceiling (about 1 GB plus the stream) stated |
| **C5** unmeasured inputs; PG-only tests | A2-A5 and 2.2 labelled UNMEASURED; rollout step 0 (measure draft cadence on the lane before fixing rate defaults, record in `CURRENT_HANDOFF.md`); PostgreSQL-only proofs labelled local execution in section 9 |
| P3-1 eviction deletes `finished` | 4.1 recorded consequence |
| P3-2 languages multiply the ceiling | 3.4 states the account-wide ceiling as per-language x enabled languages |
| P3-3 place bucket per process | Section 6 note; deployment note in `CURRENT_HANDOFF.md` (rollout step 0) |
| P3-4 probing oracle | 3.5: 429 `context` names only the fired rail |
| P3-5 hour rail precondition | Rollout step 0 makes measurement a precondition, raise the hour not the minute |
| Reviewer's answers Q1-Q12 | Adopted; recorded at the head of section 10 |

Not changed: the defaults for places, responses, annotated texts, conversations and bytes; evict-versus-reject; the
receipts section (still reserved, option A, Principal Architect as owner); the no-schema conclusion.

---

## Rev 3 changes (answering "Re-check (rev 2)", APPROVE WITH CONDITIONS)

| Item | Edit |
| --- | --- |
| **P2-5** import tombstone default | `ORENA_LIMIT_IMPORT_TOMBSTONES` raised 200 -> **360** (156 in three years x 2.3, A7), floor **52** (heavy 1-year volume) added to 3.2; stated as a lifetime count reclaimable only by a reviewed retention decision; defaults table and 3.3a updated |
| **P3-6** off-by-one | Section 6: the record at `H - 240` is the first of the 240 previous mutations, so the new mutation is the **241st** and is refused; boundary test row added (240 admitted, 241st refused; 3,600 / 3,601st) |
| **P3-7** draft_limit retry | 3.3b: the draft sender treats 422 `draft_limit` as terminal for that piece (no retry per autosave pause, stays "on this device"); test row added |
| **P3-8** moved assertions | 3.3b: the implementation commit lists every `tests/test_work_api.py` assertion that moves to a dedicated route |
| Status | Header: APPROVED WITH CONDITIONS (review re-check 2026-10-01); implementation not started |

Re-check conditions 1-3 stand: the import-tombstone fix lands first and alone with the create/delete/create test; the draft
cadence is measured on the lane before the rate defaults are fixed; PostgreSQL-only results are labelled local execution.

---

## Rev 4 changes (human decision D-107 and the autosave measurement)

| Item | Edit |
| --- | --- |
| Status | Back to PROPOSED, revision 4, pending independent re-check; rev 3's approval does not carry over |
| Rollout step 0: measure the draft cadence (D-107 point 5) | New 2.4: scripted typing on :8021, 102 saves in 11.3 active minutes; **3.7 / 12.2 / 20.7 saves per active minute** (ordinary / fast / pathological), 9.0 mixed; notes 9.3 pushes a minute; other rooms by code. A5 replaced (cadence measured, session length still unmeasured); A2-A4 stay UNMEASURED |
| Volumes | 2.3, 5.2, options table, summary and appendix recomputed: drafts 49,275 (heavy) and 3,330 (typical) a year; 389.8 M mutations, 780 M rows, 244 GB of receipts and change records, about 326 GB in all; drafts 76% |
| Rate defaults re-derived | Minute rail 240 -> **120** (2 devices x theoretical 46 a minute x 1.3); hour rail kept at 3,600 (2.9x the worst measured hour); rate-boundary tests now 120 / 121st |
| D-107.3 media pool | New 4.5 and defaults rows: media live 1,250 / total 2,500 per (account, language); uploaded bytes 10 GiB per account; uploads 30 an hour; text pool unchanged (20 live / 360 total); tombstone bound per pool; derivations from A10-A12 and `MAX_UPLOAD_BYTES` (64 MiB) |
| D-107.3 "never shown as saved" | 4.5: uploads store nothing and add nothing to the device on refusal; account first, device second for URL/text imports; a local-only fallback needs an explicit label and **no drawn pattern exists: design gap for the human**; new-category copy is also a gap |
| D-107.2 deletion | 4.5: deleting a media import removes its files, frees its bytes, keeps a tombstone counted against the pool's total |
| New findings | G1 (media library is one `index.json` for all accounts), G2 (listing shows 50, device keeps 100), `pushImport` maps non-`url` media as empty text (other session's edit) |
| Questions | Q13-Q16 added |

---

## Rev 5 changes (answering "Re-check (rev 4)", APPROVE WITH CONDITIONS)

| Item | Edit |
| --- | --- |
| Status | APPROVED WITH CONDITIONS (rev 4 re-check); implementation not started |
| **P2-6** checks after the body is streamed | 4.5: two-stage enforcement; a pre-check (hourly rail from upload records' `created_at` including tombstones, live count, live bytes plus declared `Content-Length`) before the body is accepted; the in-transaction guard stays the authority; test row |
| **P2-7** transient failures | 4.5: only a definitive 422 `*_limit` blocks; offline, 5xx, timeout and 429 use the failure pattern and create no device-only item while `active`; earlier device-only items remain and are not claimed as saved; test row |
| **P2-8** G1 | Section 8: restated as a gate (whole-file parse per read, whole-file rewrite, corrupt-index-empties-map overwrite hazard, per-process lock); rollout step 0c |
| **P2-9** G2 | Section 8: restated as a gate (imports list bounded at 50 makes "opens on a new device" false from the 51st; effective bound 50 until paged); rollout step 0c |
| P3-1 stale facts | 4.5 "What exists" rewritten at HEAD `83a6037` (`ImportSave` has `upload` and the media fields; `pushImport` uses `mediaBody`); legend note |
| P3-2 bytes and ownership | 4.5: taken from the stored entry visible to the account, unknown or foreign `mediaId` refused; test row |
| P3-3 unrecorded uploads | 4.5: ignored, not back-filled (D-104 H-6) |
| P3-4 artwork thumbnail | 4.5: capped and resized to the 640 px bound (512 KB hard limit); test row |
| P3-5 removal-pending bytes | 4.5: stay in the sum until removal is confirmed; bounded by 2,500 x 64 MiB |
| P3-6 shared file | 4.5: delete the file on the last live reference; test row |
| P3-7 overshoot | 4.5: bounded by HTTP concurrency x 64 MiB, not by the stream lock |
| P3-8 live 1,250 vs the 2x rule | 4.5: stated as a deliberate exception (heavy 3-year volume with no deletions, 1.16x), alternative of 2,500 offered |
| P3-9 wording | 2.4 reconciles 21 a minute observed with 46 a minute sizing bound; "7 a day" corrected to about 170 a day, 7 an hour |
| Condition 5 | Rollout step 0b: measure upload size and frequency on the lane before the byte and count defaults are fixed (not measured now) |
| Q13-Q16 | Answers adopted at the head of section 10 |
