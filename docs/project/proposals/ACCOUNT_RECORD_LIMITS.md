# Proposal: server-side safety limits and retention/rejection behaviour for account records

Status: **PROPOSED, revision 1** (2026-10-01, `codex/work` at `8481e33`). Document only: no code, schema, migration, Docker
or runtime is changed by this file. Not reviewed, not approved.

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
replaced by a measurement; **[A]** a stated assumption. Line numbers are the working tree on 2026-10-01 (HEAD `8481e33`
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
  (`work_contract.py:27`) under **client-minted UUIDs**, bypassing the deterministic-key routes. Any per-kind guard must also
  run there.
- **F3.** `MAX_PAYLOAD_CHARS = 200_000` (`work_api.py:56`) is checked only on the generic route (`:276`). The dedicated
  routes rely on Pydantic bounds. The annotation worst case is **191,307 characters** (measured with the field maxima:
  80 highlights x {id 80, segment 255, sentence 400, at 40} + 120 notes x {id 80, key 255, text 600, at 40}), not the
  "about 104 KB" of proposal I10, which counted only the free text. With the uncommitted `MAX_TOMBSTONES = 500` ids
  (`account_records_api.py:38`) it is **233,323 characters**, above `MAX_PAYLOAD_CHARS`, and about **441 KB** as UTF-8 when the
  text is Chinese. Not dangerous; the proposal text should be corrected.
- **F4.** Draft autosave is a receipt producer the four named kinds are dwarfed by (section 2.3). It is outside the four
  kinds, but it shares the stream and therefore the rate rail.
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
| Record payload bytes (`works.payload`) | `ORENA_LIMIT_RECORD_BYTES` | 134,217,728 (128 MiB) | per (account, language) | **reject** new row, or a growth past 32 KB: 422 `record_bytes_limit` |
| Mutations per minute | `ORENA_LIMIT_WRITES_PER_MINUTE` | 240 | per account | 429 `write_rate_limited`, retryable |
| Mutations per hour | `ORENA_LIMIT_WRITES_PER_HOUR` | 3,600 | per account | 429 `write_rate_limited`, retryable |
| Place writes per minute | `ORENA_LIMIT_PLACE_WRITES_PER_MINUTE` | 120 | per account, per process | 429 `write_rate_limited` |
| Place minimum interval, same row | `ORENA_PLACE_MIN_INTERVAL_SECONDS` | 1 | per row | answered `coalesced` (existing status), no error |

**Receipts and change records** (section 5): the growth is the real scale problem (about **212 GB/year** of receipts and
change records at the 100k-account target under the stated assumptions, of which autosave drafts are about 70%).
This proposal names an **owner** (the Principal Architect role, AGENTS section 1) and lays out options, but **proposes no
deletion**. Until a versioned policy exists nothing is purged (ADA section 5: "missing policy disables destructive purge").

---

## 2. Method: assumptions, cost constants, volumes

### 2.1 Assumptions [A]

The repository holds no usage telemetry, so these are assumptions, stated so a reviewer can change them and re-run the
arithmetic (appendix A).

| # | Assumption | Basis |
| --- | --- | --- |
| A1 | 100,000 accounts; 20,000 daily-active | target scale, AGENTS section 7; 20,000 DAU is the figure `LEARNER_RECORDS_D4.md` I4 already uses |
| A2 | Of the DAU, **25% heavy** (5,000) and 75% typical (15,000). Non-daily accounts add a tail that is **not** estimated, so totals are a floor | [A] |
| A3 | Heavy learner: 2 sessions/day, 365 days/year. Typical: 1 session/day, 208 days/year (4 days a week) | [A] |
| A4 | Per session, heavy / typical: 1.5 / 1.0 new content opened (reading positions); 5 / 3 typed takes; 0.5 / 0.3 annotated texts at 9 / 5 pushes each; 0.5 conversations at 16 / 10 turns | [A]; Free Talk and Reading Transfer produce a take each (`free-talk/screen.js`, `saveResponse`); conversations are scenario-shaped (I6) |
| A5 | Autosave drafts: 90 saves per writing session (15 minutes at about 6 saves a minute; a save follows a 1.2 s pause, `draft-sync.js:127`); heavy 1 session/day, typical 60/year | **[A], unmeasured**; the debounce only bounds it to about 50 a minute |
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
| Autosave drafts (mutations), A5 | 32,850 | 5,400 |
| **Mutations, all** | **45,625** | **7,376** |
| Storage, the four kinds (rows + their receipts/change records) | 19.4 MB | 3.3 MB |
| Storage, all mutations' receipts/change records | 29.3 MB | 4.7 MB |

At the target, 5,000 heavy + 15,000 typical accounts, **per year**:

| | Four kinds | Including drafts |
| --- | --- | --- |
| `library_items` place rows | 8.6 M (5.7 GB) | same |
| `works` rows (responses 27.6 M, annotated texts 2.8 M, conversations 3.4 M) | 33.8 M | same |
| `work_turns` rows | 44.8 M | same |
| Mutations | 93.5 M | **338.8 M** |
| Receipt + change-record rows | 187 M | **678 M** |
| Receipts + change records, storage | 58 GB | **212 GB** |
| All storage (content + receipts + change records) | 139.5 GB | **about 293 GB** |
| Average mutation rate | 3.0 / s | 10.7 / s (peak of the order of 100 / s across all accounts; per account the stream lock serialises, `mutation_commit.py:106-112`) |

Reading of the table: **the receipt and change-record tables, not the learner's words, are the growth**: 42% of the
four-kind storage and 72% once autosave is counted. That is why section 5 exists. A heavy learner's own words are about
11 MB a year.

---

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
responses 3,650, annotated texts 365, conversations 365, bytes 16 MiB, writes per minute 60, writes per hour 600). A floor
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
  `SELECT kind, count(*), coalesce(sum(pg_column_size(payload)), 0) FROM works WHERE incarnation_id = :inc AND language_code
  = :lang AND lifecycle <> 'deleted' GROUP BY kind`, and compares each kind to its limit. It uses `ix_works_scope_sequence`
  for the range and reads the heap for `kind`; for the heaviest account at cap (about 30,000 rows) that is one scan of about
  10-20 ms [I], paid only on **creation**, which is 0.1 a second at the target. `pg_column_size` of a TOASTed value reads the
  pointer, not the value.
- A **replay never hits a guard.** A retry of a committed creation finds the row, so `load` does not call `create_guard`
  (`work_repository.py:135-140`), and the receipt lookup precedes the decision (`mutation_commit.py:132-140,171-179`). The
  rate rail (section 6) must be evaluated after the receipt lookup and skipped on a receipt match, for the same reason.
- A **growth guard** for updates: `load` already holds the old payload; when the new payload would exceed 32 KB and is
  larger than the old, the same aggregate runs with the delta. Typical payloads are 1-3 KB, so the aggregate almost never
  runs on an update.

**3.4 Scope.** Counts are per (incarnation, language), the same scope as the import bound and as every `works` row
(`work_repository.py:256-257`). Library rows (`library_items`) are per (user, language). Switching language does not reset a
limit and does not share one. A re-registered account (new incarnation) starts at zero, as its data does.

**3.5 Error contract.** Stable machine codes in `detail.category`, `retryable: false` for counts, `true` for rate; a
`context` of `{limit: N}` only (no learner data, no other account). HTTP: 422 for a count or byte limit (the status
`import_limit` already answers, `tests/test_d4_account_records.py:367`), 429 for rate, 413 `work_too_large` unchanged. The
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
**128 MiB = 4.8x that.** Conversation turn content lives in `work_turns` and is not in this budget; it is bounded by
conversations x 24 x the per-turn cap instead (4.4).

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

**5.2 Growth (section 2.3).** 93.5 M mutations a year from the four kinds, **338.8 M** with autosave drafts (A5):
receipts 144 GB, change records 68 GB, **212 GB a year** at the target, for ever.

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
| **A. Keep everything for now** | 212 GB/year, 678 M rows/year; a few years of runway on one PostgreSQL instance | nothing; revisit at a fixed trigger (for instance receipts > 100 M rows or 100 GB) |
| **B. Receipt time window W** | steady-state receipts: W = 30 d 11.8 GB, 90 d 35.4 GB, 180 d 70.9 GB (vs 144 GB a year) | an expiry epoch for operation ids (client contract or schema), a policy value **supplied by the human**, an operator job under a human gate |
| **C. Keep-latest-per-object change records** | about 34 M rows a year (the number of `works` created), 6.8 GB, instead of 339 M | sync protocol: sequence gaps legal, consumers re-read an object by id; reserved |
| **D. Partition `mutation_receipts`/`change_records` by month and detach old partitions to cold storage** | removes growth from the hot table without deleting; dedup for old ops then needs the archive or an epoch | schema decision (section 7), reserved |

**Recommendation (non-binding).** A for the lane and for :8021; the limits of section 4 and the rate rail of section 6 cap
what one account can add to the stream; **the receipt-growth owner is the Principal Architect role** (AGENTS section 1),
who defines the versioned retention policy and horizon (ADA section 5); the operator executes it under the human gate; the
trigger above goes in `CURRENT_HANDOFF.md`. The IMPLEMENTATION_REVIEW P2-4 condition asks for an owner, not for compaction,
before :8000. Autosave (A5) should be **measured** on the lane first, because it is about 70% of the mutations and is the
cheapest to reduce at the client (the serialised sender in `draft-sync.js:147-200` already keeps one request in flight).

---

## 6. Rate limiting is a separate rail from counts

Counts bound *how much is kept*; they do not bound *how often a row is rewritten*. A loop that re-PUTs one annotation
document or one draft with a new operation id creates no new row and passes every count, yet adds 0.65 KB of receipts per
request and rewrites a payload. So a rate rail is required, and for the same reason it must **not** reuse the counts.

**Stream mutations** (everything through `commit_mutation`): per **account**, `ORENA_LIMIT_WRITES_PER_MINUTE` = **240**
and `ORENA_LIMIT_WRITES_PER_HOUR` = **3,600**, evaluated in the same transaction, after the stream lock and the receipt
lookup, skipped on a replay. No schema and no counter table: the account's recent mutations are its newest `change_records`,
read through the existing unique index `(incarnation_id, sequence)`:
`SELECT created_at FROM change_records WHERE incarnation_id = :inc ORDER BY sequence DESC OFFSET 239 LIMIT 1`; if that time
is within 60 seconds, 240 mutations landed in the last minute. The hour check is the same with `OFFSET 3599`. Cost: one
index walk of at most 3,600 entries per mutation, about 1 ms [I], about 0.014 cores at the average 10.7 mutations/s of the
all-mutations volume. A later compaction must keep at least the newest 3,600 change records per account. The refusal is
**429 `write_rate_limited`**, `retryable: true`, `context: {retryAfterSeconds}`.

**Why these numbers.** Legitimate ceilings (one device): annotation push <= 1 per 1.2 s quiet; draft save <= 1 per 1.2 s
pause (`draft-sync.js:127`), realistically about 6 a minute and at most about 50; conversation turn <= about 12 a minute;
response <= about 4 a minute. The highest sustained legitimate rate is therefore about **50 a minute, about 3,000 an hour**
(an hour of continuous drafting at A5's cadence of about 6 a minute is about 360). **240 a minute is about 5x the single-device ceiling and
3,600 an hour (1 a second) is 1.2x the absolute ceiling of 50 a minute held for a full hour and 10x A5's drafting cadence**; a runaway at 10 requests a second is held to
1 a second, a 10x reduction, and to at most 86,400 a day per account, against 7,376 (typical) to 45,625 (heavy) legitimate
a year. The hour rail is deliberately close to the ceiling because drafts are chatty; if measurement (A5) shows more
headroom is needed, raise the hour, not the minute.

**Place writes** take no stream lock and write no change record, so the query above cannot see them. Two complementary
rails (4.1): the per-row interval (exact, from the row's own `place_at`) and the in-process per-account bucket
(approximate). A per-account place counter table would make the second exact; it is a schema decision (section 7) not
justified by a rail whose purpose is to stop a loop.

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

## 8. Adjacent creators this proposal does not size

Found while tracing; each is the same kind of unbounded creator and each is left to a follow-up so that no number here is
invented without a volume basis:

- **Library items** (`POST /api/library/items`, `library_api.py:69-72,116`): a row per (kind, `source_id` <= 255,
  relationship); the row's note is <= 2,000 characters. The count of **kept/marked** rows is unbounded. Saved words
  (`saved_words`) are owned by the vocabulary domain.
- **Collections**: `COLLECTION_LIMIT = 200` (`library_repository.py:54`) limits a *read*, not creation (`:545-562`).
- **Kept-word provenance** (`POST /api/library/vocabulary/{word}/provenance`, `account_records_api.py`): a
  `language_provenance` row and a receipt per operation, `focus` <= 1,200; no count.
- **Drafts** (`PUT /api/drafts/{key}`, `work_api.py:357`): a row per key <= 200; bounded per row at 12,000 characters; the
  dominant receipt producer (A5). They pass through the rate rail.
- **Speech attempts** (`speaking_attempts`): bounded by the speech domain, not by this proposal.

---

## 9. Test plan

Unit and API tests with the limits set small through the environment (the module reads them once, so the test sets them
before import or uses a config seam), then the full suite. PostgreSQL-only proofs are **local execution** and must say so
(`ORENA_TEST_POSTGRES_URL`; CI has no PostgreSQL service, IMPLEMENTATION_REVIEW P2-7).

| Area | Test |
| --- | --- |
| Each count rail (responses, annotated texts, conversations) | N-1 succeeds, N succeeds, N+1 refused with the exact code and HTTP status; `retryable: false`; `context.limit` equals the setting |
| Race | N+1 concurrent creations at N-1 admit exactly one (mirror the import barrier test, `tests/test_d4_account_records.py` near `:367`) |
| Replay | a committed creation retried at the limit answers `replay`, not a refusal; an update of an existing row at the limit succeeds |
| Scope | another language and another account are unaffected; a re-registered account starts at zero |
| F2 | the generic `PUT /api/works/{id}` is refused for kinds `response` and `conversation` at the limit |
| F1 | `PUT /api/continue/{id}` with `place: null` on an absent row inserts nothing |
| Place eviction | at 5,000, the next insert evicts the 100 oldest place-only rows; kept, pinned, noted, stated and **filed** rows are never deleted; saved rows lose only `place`; the written status is `written` |
| Place rate | same-row writes under 1 s answer `coalesced`; the per-account bucket returns 429 after 120 in a minute, recovers after it |
| Byte budget | a response of maximal size stops being accepted near 128 MiB; an annotation growing past 32 KB is checked; a growth under 32 KB runs no aggregate (assert query count) |
| Stream rate | the 241st mutation in 60 s is 429; a replay in the same window is not; the hour rail likewise; 429 is retryable and a retry after the window commits |
| Config | non-integer, zero, negative and below-floor values fail startup with the variable named; defaults load |
| Client | node gates: a 422 or 429 leaves `saveResponse`, `pushAnnotations`, `appendConversationTurn` and `sendPlace` silent, never sets the draft state to `account`, and the draft sender still says "on this device" on a 429 (`draft-sync.js` catch) |
| Size at cap | extend `scripts/rehearse_learner_records_schema.py --volume` (or a sibling) to load one account to every cap and record guard latency, `pg_total_relation_size` per table (replacing section 2.2), and the TOAST behaviour of `pg_column_size` |
| Regression | the existing bounds (20 imports, 24 turns, annotation and response field maxima, `work_too_large`) unchanged |

**Rollout.**
1. Independent review of this document (AGENTS section 1). Nothing is implemented before it.
2. Implement in the lane `codex/work`, limits **on by default** (they are rails, not features), one commit per rail.
3. Run the section 9 tests on the lane sandbox with low limits and again with the defaults; record local-execution
   evidence; add the PostgreSQL service job when CI gets one.
4. Independent code review of the implementation. Report `UI_BACKEND_GAPS.md` entries (4.2-4.4).
5. **The human's gate** for :8000/:8010 is unchanged and separate: this proposal removes P2-4's "caps" condition, names the
   receipt-growth owner, and supplies the decision list below; it does not enable anything.

---

## 10. Questions for the reviewer

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
7. **Rate rail numbers.** 240 a minute and 3,600 an hour are sized against A5, which is a guess. Is the hour rail too tight
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
12. **Learner surface.** Confirm that no notice is drawn for a rail (4.2-4.4) and that recording the gap in
    `UI_BACKEND_GAPS.md` is the right outlet.

---

## Appendix A. Reproducing the arithmetic

The figures in sections 2-5 come from the following model; the profile dictionary is the only input.

```python
KB = 1024
RC, WK = 0.65, 0.30                      # receipt+change per mutation, works row overhead (KB)
PLACE, RESP, ANN, TURN, HDR = 0.70, 1.05, 2.4, 0.68, 0.7   # KB per place row / response payload / annotation payload / turn / conversation header
P = {  # n accounts, active days, sessions/day, places, responses, annotated texts, pushes, conversations, turns, draft saves/yr
  "heavy":   dict(n=5000,  days=365, sess=2, place=1.5, resp=5, annot=0.5, pushes=9, conv=0.5, turns=16, drafts=365 * 90),
  "typical": dict(n=15000, days=208, sess=1, place=1.0, resp=3, annot=0.3, pushes=5, conv=0.5, turns=10, drafts=60 * 90),
}
for p in P.values():
    s = p["days"] * p["sess"]
    p["mut4"] = s * p["resp"] + s * p["annot"] * p["pushes"] + s * p["conv"] * p["turns"]
    p["mutall"] = p["mut4"] + p["drafts"]
print(sum(p["n"] * p["mutall"] for p in P.values()) / 1e6)        # 338.8 (M mutations a year)
print(sum(p["n"] * p["mutall"] for p in P.values()) * RC / KB**2) # 212 (GB of receipts + change records)
```

Sizes measured rather than estimated: annotation payloads (2,436 characters typical; 191,307 worst without and 233,323
with tombstones; about 441 KB in UTF-8 with Chinese text) come from `json.dumps` over payloads built with the field maxima in
`account_records_api.py:94-106`. Everything marked [I] in section 2.2 is to be replaced by `pg_total_relation_size` at
volume.
