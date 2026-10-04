# Independent review: ACCOUNT_RECORD_LIMITS (PROPOSED rev 1)

- **Reviewer:** Claude Opus 5.5, independent reviewer subagent, not the author (Delegated Architecture Reviewer, AGENTS §1).
- **Reviewed:** `docs/project/proposals/ACCOUNT_RECORD_LIMITS.md` at commit `a9dc2a9`, against HEAD `a9dc2a9` and the
  code it cites (`mutation_commit.py`, `work_repository.py`, `work_api.py`, `work_contract.py`, `account_records_api.py`,
  `library_repository.py`). The uncommitted working-tree edits of another agent were ignored.
- **Date:** 2026-10-01. Read-only, no Docker. I re-ran the arithmetic of Appendix A on the host.

## Verdict: REQUEST CHANGES (one P1, text-level; no redesign)

The approach is sound and honest: the numbers are safety rails with stated derivations, evict-vs-reject is right for
every kind, enforcement in the creating transaction after the account stream lock is the correct place, receipt
compaction is correctly left reserved, and no schema change is needed. One design gap lets the central guarantee
("bounded rows per account") be bypassed, and two creators are left unguarded. Fix the proposal text for P1-1 and
P2-1/P2-2, and I would approve with the remaining conditions without another full review.

| Severity | Count |
| --- | --- |
| P0 | 0 |
| P1 | 1 |
| P2 | 4 |
| P3 | 5 |

## What I verified

- **Rails, not quotas.** Nothing is shown to a learner; no counter, copy or upgrade path; values live in configuration
  and operator logs; startup refuses non-integers and values under a floor equal to the heavy 1-year volume, so a
  misconfiguration cannot become a quota. Defaults sit at 1.5x (evictable) to 2.3x (authored) of the heavy 3-year
  volume. This satisfies "do not invent arbitrary learner-facing quotas". The human's instruction asks for volume
  reasoning, and every default has one.
- **Arithmetic is traceable and reproduces.** Appendix A gives 338.8 M mutations/year, 93.5 M for the four kinds, 10.74/s
  average (2.97/s four kinds), 5,000/1,095 = 4.6 years, 25,000/10,950 = 2.3x, 2,500/1,095 = 2.3x; per-profile yearly
  counts (3,650 responses, 365 annotated texts, 3,285 pushes, 365 conversations, 5,840 turns, 12,775 and 45,625
  mutations) match. Receipts plus change records come to 210-213 GB depending on rounding of the per-row constants
  (document says 212 GB); immaterial. The unmeasured inputs are A2-A5 and the row sizes of §2.2, and the document labels
  them [A]/[I] and schedules their replacement by measurement. That is the right posture; I only ask that the numbers not
  be read as measurements (condition C5).
- **Evict versus reject.** Places are derived navigation state, so evicting least-recently-used place-only rows is right,
  with F5 (add `NOT EXISTS` over `library_collection_members`; confirmed `_place_only()` omits it) a real and necessary
  correction. Responses, annotations and conversations are learner-authored and are never evicted, only refused for a
  new key, while existing rows keep updating and a replay of a committed creation never meets a guard (the receipt
  lookup and the existing-row branch of `load` precede `create_guard`). Correct.
- **Where enforced.** Inside the creating transaction after the `account_streams ... FOR UPDATE` lock, exactly like the
  import bound, so two creations at N-1 cannot both pass. F1 (a `place: null` write inserts a row; confirmed in
  `set_place`), F2 (generic `PUT /api/works/{id}` still accepts `draft`/`response`/`conversation` under client UUIDs) and
  F3 (`MAX_PAYLOAD_CHARS` only on the generic route; worst annotation payload far above the "104 KB" of I10) are genuine
  and correctly diagnosed.
- **Receipts.** Correctly framed as a reserved decision: no deletion proposed, owner named, options A-D with numbers,
  the dependencies on a snapshot endpoint, an operation-age epoch and the sync protocol stated accurately (no client calls
  the change feed; ids are `op-<uuid4>` and carry no age). Nothing in the proposal decides compaction, cursors, tombstone
  horizon or retention days.
- **Schema.** "None needed" holds: the count queries use `ix_works_scope_sequence` and `ix_library_items_shelf`; the
  stream-rate query uses `uq_change_record_sequence`. S1-S3 are correctly marked as separate reviewed decisions.
- **Client behaviour.** Every client writer is best effort and returns `false`/swallows; nothing claims a save it did not
  get, and no notice is invented; the gap is recorded in `UI_BACKEND_GAPS.md` (rule 7), which is the right outlet.

## Findings

### P1-1. Counting only non-deleted rows lets a client create unbounded rows (the cap is bypassed by delete)
- **Where.** §3.3 aggregate: `... WHERE ... lifecycle <> 'deleted' GROUP BY kind`; the shipped import guard counts the
  same way (`account_records_api.py` `at_most_the_limit`, `lifecycle <> 'deleted'`).
- **Failure scenario.** The generic `PUT /api/works/{id}` accepts client-minted UUIDs and `lifecycle = 'deleted'`
  (`work_api.py:274-285`; `lifecycle_change` allows `active -> deleted`, and a creation may start at `deleted`). A loop of
  "create a `response` (or `conversation`/`draft`), mark it `deleted`, repeat" never raises the counted total, so the
  25,000 / 2,500 caps and the 128 MiB budget (which also excludes deleted rows) never trip; every cycle still leaves a row
  (a tombstone is terminal, ids are not reused), a receipt and a change record. Only the rate rail (3,600/hour, i.e. 1,800
  rows/hour, 15 M rows/year per account) stands in the way, which is not a bound. The same loop works today against the
  20-import cap through the dedicated import route (create, delete, create).
- **Required change.** Count all rows of a kind regardless of lifecycle for the row-count rails, or cap tombstones
  separately (for example total rows <= 1.25x the live limit); for kinds with no dedicated delete route (`response`,
  `conversation`, `annotation`, `draft`) refuse `lifecycle = 'deleted'` on creation and on the generic route unless it
  goes through a dedicated route. For imports (where delete-and-recreate is legitimate) count tombstones against a
  separate, larger bound. State the byte budget as including tombstones.

### P2-1. F2 is guarded for two kinds only; `draft` remains an uncapped creator through the generic route
§4 adds `create_guard` to `response` and `conversation` on the generic route, but `draft` is "outside the four kinds"
(§8). It is a `works` row per client UUID with no count, and the byte budget counts payload bytes only, so rows with
near-empty payloads evade it. **Required:** either refuse `draft`, `response`, `conversation` on the generic route
altogether once dedicated routes exist (preferred; the dedicated routes derive deterministic ids), or give drafts a count
rail with a derivation under the same A7 rule (heavy: about one piece a day, about 1,100 in three years, so about 2,500).

### P2-2. The stream-rate query is not O(1) as stated and is avoidable
`SELECT created_at FROM change_records ... ORDER BY sequence DESC OFFSET 239/3599 LIMIT 1` walks the index and must fetch
the heap for `created_at` for each skipped row (`created_at` is not in the index), up to 3,600 tuples per mutation, not
about 1 ms, and it runs under the account stream lock on every mutation of a chatty draft stream. **Required:** use a
point lookup. Sequences are gap-free per incarnation (allocated under the lock, rolled back with the transaction), and the
head is already read: `SELECT created_at FROM change_records WHERE incarnation_id=:inc AND sequence = :head - N` (a
unique-index probe). Fall back to the walk only when a later compaction creates gaps, and say that compaction must then
keep a floor. Also state that the 429 must be mapped explicitly: every route maps a `rejected` outcome to 422
(`_commit`, `put_work`, `put_draft`, turns), so a `rate_limited` reason needs its own branch to become 429 with
`retryAfterSeconds`.

### P2-3. Eviction concurrency and the "never an error" promise
Place writes take no stream lock, so two creators at the cap can both evict and both insert; the overshoot is bounded by
concurrency and harmless. But an eviction `DELETE` racing a `PUT /api/continue` `UPDATE` of the same (oldest) row makes
`set_place` read `session.get(...)` of a deleted row and fail (`_place_dict(None)`), a 500 where the document promises no
error. **Required:** specify that the update path handles a vanished row by re-inserting (or answering `written` after a
re-read), and that eviction runs `DELETE ... WHERE id IN (...)` re-checking the place-only predicate in the same statement.

### P2-4. Annotation and conversation rails leave one growth path unspecified: payload bytes are measured compressed
`pg_column_size(payload)` returns the stored (possibly compressed) size for a TOASTed `json` value, so the 128 MiB budget
undercounts text-heavy payloads by the compression ratio (commonly 2-3x for prose). That is acceptable for a rail but the
document describes it as "payload bytes" and uses 3x-UTF-8 worst cases elsewhere. **Required:** say it is a stored-size
budget, or measure `octet_length(payload::text)` on creation only; and state the combined worst case per (account,
language) including `work_turns` (up to about 0.9 GB for 2,500 maximal conversations, outside the budget) so the operator
knows the true ceiling.

### P3 findings
- **P3-1.** Eviction deletes place rows that carry `finished` (Reading Complete's "Finished"); acceptable for navigation
  state, but record it so a reader of a 5-year account is not surprised.
- **P3-2.** Per-(account, language) scope multiplies the ceiling by the number of enabled languages; state the total.
- **P3-3.** `ORENA_LIMIT_PLACE_WRITES_PER_MINUTE` is per process; with more than one worker it is N x 120. The document says
  so; add it to `CURRENT_HANDOFF.md` as a deployment note when workers change.
- **P3-4.** The operator query "accounts above 80%" and the refusal log are good; add the rail name to the 429 response
  `context` only (no counts of other rails) to avoid a probing oracle.
- **P3-5.** The §6 hour rail (3,600) is 1.2x the theoretical ceiling and about 10x A5's cadence; since A5 is a guess, the
  document's own advice (measure drafts on the lane first, raise the hour not the minute) should be a stated rollout
  precondition, not a suggestion.

## Answers to "Questions for the reviewer"

1. **Sizing rule (A7).** Yes: 1.5x for evictable and 2x for authored state over a heavy 3-year volume is a reasonable
   rail rule, and the heavy profile (2 sessions/day, 365 days, 5 takes) is deliberately pessimistic. Keep, label as
   assumption, replace A5 by measurement.
2. **Place cap scope.** Per (account, language): the rows are language-scoped and the code already works that way. State
   that the account-wide ceiling is the product with the enabled languages (P3-2).
3. **Evict versus reject for places.** Agree it is derived and evictable, and that F5 must be added. Clearing `place` on a
   saved row in the pathological case is acceptable (it is the `forget` precedent and loses no learner-authored text).
4. **Byte budget.** Creation plus growth past 32 KB is enough for a rail; the residual is rows growing under 32 KB, bounded
   by count x 32 KB. Counters (S2) are not worth a schema decision before :8000. Fix P2-4's description and P1-1's
   tombstones.
5. **Reject code and status.** Keep 422 with `<kind>_limit`, consistent with `import_limit`; 429 for rate; do not use 507.
6. **Cleared annotation rows.** Count them. A cleared document keeps its id and row, so excluding it reopens the P1-1
   loop; a JSON predicate adds cost for no benefit.
7. **Rate numbers.** 240/min is fine. The hour rail may be tight for a very long writing session on two devices; measure
   draft cadence on the lane first (P3-5), and prefer raising the hour value to touching the minute.
8. **In-process place bucket.** Acceptable for a navigation write that creates no receipt, together with the exact per-row
   minimum interval.
9. **Receipts.** The Principal Architect role as owner is right; Option A is acceptable for the lane and :8021; set a
   written trigger (suggest receipts above 100 M rows or 100 GB, as the document does, or one year from first production
   enablement, whichever first) in `CURRENT_HANDOFF.md`. The receipt digest of a deleted import is a hash of private text:
   treat it as learner-derived data. The D-055(b) enumeration already deletes `mutation_receipts` explicitly, so the
   question is covered once the workflow exists. Nothing in this proposal decides compaction, which stays reserved.
10. **Hostile fill-then-grow residual.** Acceptable with the rate rail and the byte budget, once P1-1 is closed.
11. **Adjacent creators.** Keep this round to the four named kinds plus drafts (P2-1, because the generic route reaches
    them); log library rows, collections and provenance as the next round, since no volume basis exists yet.
12. **Learner surface.** Confirm: no notice is drawn for a rail; record the gap in `UI_BACKEND_GAPS.md` when the code lands.

## Conditions to reach APPROVE

- C1. P1-1: tombstones counted or capped; no delete-based bypass for any kind, including the existing import bound.
- C2. P2-1: refuse `draft`/`response`/`conversation` on the generic route or cap drafts.
- C3. P2-2: O(1) rate lookup by `head - N`; explicit 429 mapping in every route.
- C4. P2-3 and P2-4: eviction race and the stored-size description corrected.
- C5. State in the document and in `CURRENT_HANDOFF.md` that A2-A5 and §2.2 are unmeasured and that the draft cadence
  must be measured on the lane before the rate defaults are fixed; PostgreSQL-only tests are local execution.
- Not a condition: the P3 items. Enabling the backbone on :8000/:8010 remains a separate human gate.

## Re-check (rev 2)

- **Reviewer:** Claude Opus 5.5, independent reviewer subagent, not the author. **Date:** 2026-10-01.
- **Reviewed:** `ACCOUNT_RECORD_LIMITS.md` rev 2 at `40396ae` (diff against `a9dc2a9`, section "Rev 2 changes"). Document
  review only; I also confirmed by search that no `static/orena` code calls `/api/works` (only two test files do).

### Verdict: APPROVE WITH CONDITIONS

Rev 2 closes C1-C5 and every P2/P3 of the first review. One new P2 (the import-tombstone default) and three P3 wording
points remain; none needs another full review.

| Item | Result |
| --- | --- |
| P1-1 / C1 delete bypass | **Closed.** The aggregate counts all rows (live and total, tombstones in the byte budget); creation with `lifecycle: deleted` is refused for `response`, `conversation`, `annotation`, `draft` (none has a delete route, clearing is `{cleared:true}`); imports keep 20 live plus a separate tombstone bound. The proposal also correctly records that the shipped import guard has the same defect today and must be fixed in code first and alone, with a test. |
| P2-1 / C2 generic route | **Closed, better than asked.** The generic writer is closed for `draft`/`response`/`conversation` (422 `work_kind_invalid`), so there is no client-UUID creator left; `MAX_PAYLOAD_CHARS` then bounds nothing writable. Verified no client uses it. Drafts get `ORENA_LIMIT_DRAFTS` = 2,500 (heavy 1,095 in three years x 2.3, consistent with A7), reject-not-evict. |
| P2-2 / C3 rate lookup, 429 | **Closed.** Point probe at sequence `H - N` on `uq_change_record_sequence` (sequences are gap-free per incarnation and `H` is already read); gap reads as under the rail; compaction floor stated; explicit 429 branch in `_commit`, `put_work`, `put_draft`, turn append and `/api/continue`, tested. |
| P2-3 eviction race | **Closed.** Single `DELETE ... WHERE id IN (...)` re-checking the place-only predicate and membership in the statement; a vanished row in `set_place` takes the insert branch and answers `written`; interleaving test listed. |
| P2-4 stored size, `work_turns` | **Closed.** Stated as a stored-size budget; `work_turns` excluded with the reason; honest per-language ceiling (about 1 GB plus the stream, times enabled languages). |
| C5 unmeasured inputs | **Closed.** A2-A5 and §2.2 labelled UNMEASURED; rollout step 0 makes the lane measurement a precondition of fixing the rate defaults and records it in `CURRENT_HANDOFF.md`; PostgreSQL-only proofs labelled local execution. |
| P3-1..P3-5 | **All adopted** (finished flag, languages multiply the ceiling, per-process bucket note, 429 context names only its own rail, hour-rail precondition). |
| Q1-Q12 | Adopted as answered; Q7 (hour rail) and Q9 (trigger value) correctly left open for measurement and the human. |
| Receipts / reserved items | Unchanged and correct: option A, Principal Architect as owner, no deletion, compaction/cursors/horizon still reserved (AGENTS §7). |

### New findings

- **P2-5. Import tombstone bound is derived with a 1.25x margin, not the A7 rule, and is a lifetime ceiling.**
  `ORENA_LIMIT_IMPORT_TOMBSTONES` = 200 counts *total* import rows (live plus deleted) per (account, language) for ever,
  because tombstones are terminal and cannot be recycled. At the document's own heavy figure (52 imports a year) that is
  reached in about 3.8 years, and a refused import then silently stays device-only. Imports are learner-authored, so A7
  says at least 2x the heavy 3-year volume (156 x 2.3 = about 360). **Required:** set the default to about 360 (and the
  floor to the heavy 1-year volume, 52), or state why imports are exempt from A7. Note it is a lifetime count, so only a
  reviewed tombstone-retention decision (reserved with deletion/export) could ever reclaim it.
- **P3-6.** The rate probe text says the mutation about to take sequence `H` is "the 240th" if `H - 240` is under 60 s old; that
  record is the first of the 240 *previous* mutations, so the new one is the 241st. Harmless (the rail trips one request
  earlier or later), but fix the wording and the test boundary so the 241st-in-60s test in §9 matches.
- **P3-7.** Specify that the draft sender treats 422 `draft_limit` as terminal for that piece (no retry loop on every
  autosave pause) and keeps saying "on this device"; the test row only covers 429.
- **P3-8.** Closing the generic writer is a behaviour change for `tests/test_work_api.py`; list in the implementation commit
  which assertions move to the dedicated routes so none is dropped.

### Conditions (to start implementation; each is small)

1. Land the import-tombstone fix first and alone, with the create/delete/create test (as the document already says), using
   the P2-5 default.
2. Apply P2-5, P3-6, P3-7 and P3-8 in the implementation or a one-line text edit.
3. Measure the draft cadence on the lane (rollout step 0) before the rate defaults are fixed; label PostgreSQL-only results
   as local execution.

Enabling the backbone on :8000/:8010 remains a separate human gate; this proposal, once implemented and independently code
reviewed, removes the P2-4 caps condition.

## Re-check (rev 4)

- **Reviewer:** Claude Opus 5.5, independent reviewer subagent, not the author. **Date:** 2026-10-01.
- **Reviewed:** `ACCOUNT_RECORD_LIMITS.md` rev 4 at `91842bf` against D-107 (`DECISION_LOG.md`), the code it cites at HEAD
  (`media_library_store.py`, `account_records_api.py`, `media_library_api.py`) and my own recomputation of its arithmetic.
  I did not have the author's scratchpad (`autosave_measure.md`, `cadence*.cjs`), so the measurement is judged from the table
  and method text in section 2.4 only. Document review; no Docker.

### Verdict: APPROVE WITH CONDITIONS

The rate re-derivation, the media pool, the byte rail and the refusal rule are sound in design, and the figures reproduce.
Four P2s and several P3s need text edits before implementation starts; two of them (G1, G2) are larger than the
document says and must be gates for anything beyond :8021, not "next round" items. No P0/P1.

### Arithmetic, recomputed
Drafts 9.0 x 15 x 365 = 49,275 and 3.7 x 15 x 60 = 3,330; mutations 93.5 M + 246.4 M + 49.95 M = 389.8 M, drafts 76%;
receipts and change records about 242-245 GB (document: 244 GB). Media: 100 + 260 = 360 items and 1.47 GiB a year heavy,
1,080 items and 4.4 GiB in three years, x 2.3 = 2,484 items and 10.1 GiB; typical 36 items and 0.18 GiB; aggregate about
9.8 TiB a year at the target (document 9.7); 30 uploads x 64 MiB = 1.9 GiB an hour; index 2.34 M entries a year, about
4.7 GB. All reproduce. Two wording errors: the rate section says the average heavy learner needs 62,050 mutations a year,
"about 7 a day" (it is about 170 a day, 7 an hour); and section 2.4 says "the hard ceiling is one save per about 2.9 s"
(about 21 a minute) and in the same paragraph a theoretical maximum of about 46 a minute (1.3 s). One of the two is wrong;
see P3-9.

### Are the defaults traceable safety rails, not learner-facing quotas?
Yes for the rate, byte and tombstone rails: each states its derivation, floors exist, nothing is drawn to a learner. Two
qualifications. (a) Only the draft cadence is measured; A2-A4 and the new A10-A12 (uploads and links per year, mean
upload size 15 MiB) are labelled unmeasured, so D-107's "from measurements and storage estimates" is met as "estimates",
openly. Upload size and frequency should be measured on the lane the same way before the byte and count defaults are
fixed (condition 5). (b) The media **live** bound of 1,250 is 1.16x the heavy 3-year volume, below the document's own A7
rule for learner-authored records (2x); only the 2,500 total meets it. Use 2,500 for both, or justify (P3-8).

### Measurement validity and the 120 a minute rail
The method is acceptable for a cadence bound: the real `draftSync` path on :8021, counted at the network layer, three
typing models, 102 saves in 11.3 active minutes, all PUTs 200, no 409/429. It is scripted, one device, 11 minutes, so it
supports a cadence per active minute, not A2-A4 or session length (the document says so). The pathological case (a
pause after every word) is the right ceiling to test. The re-derivation holds: 120 a minute is 5.8x the worst measured
minute (21), 2.9x two devices at the measured worst (42), 2.6x the one-device theoretical (46) and 1.3x two devices at the
theoretical (92). The 3,600 an hour is 2.9x the worst measured hour (1,242). The worst measured cases are admitted with
margin, including two devices. One check I would add: other mutation producers can add to a typing minute (annotation
pushes at 9.3 a minute, a conversation turn, a provenance write); even stacked on a one-device theoretical maximum (46 +
9 + 12 + 4 = 71) the rail admits them.

### Media pool, byte accounting, tombstones, scope
- **What counts.** Pool by `form`: `text` to the text pool (20 live, 360 total), `url` and `upload` to the media pool (1,250
  live, 2,500 total, per account and language, all rows counted, tombstones included). Bytes: live uploads' original plus
  thumbnail, per **account across languages** (right: bytes are a storage cost and a bilingual learner should not get two
  ceilings of the expensive resource; the guard can sum by incarnation under the stream lock). Counts stay per language,
  consistent with every other row rail.
- **Freed.** Delete removes the files and the bytes leave the live sum. See P3-5: bytes should stay in the sum until the
  removal is confirmed.
- **Tombstones.** Each pool has its own total bound; a media tombstone carries no bytes. Correct.

### Findings
- **P2-6. Rate and byte checks run after the body is streamed.** 4.5 streams up to 64 MiB, then checks inside
  `commit_mutation`, and "the uploads-per-hour rail and the stream lock bound it". The stream lock is taken at commit, so it
  bounds nothing during the upload; an account at its byte or hourly limit can keep sending 64 MiB bodies that are stored,
  rejected and deleted, which is bandwidth and disk churn bounded only by HTTP concurrency (and each refusal also rewrites
  the whole media index, G1). **Required:** a cheap pre-check before accepting the body (rate window from the account's
  recent upload records, live bytes plus declared `Content-Length` against the byte rail, live count), keeping the
  in-transaction guard as the authority; and specify how `ORENA_LIMIT_UPLOADS_PER_HOUR` is counted (from `works.created_at`
  of upload records, tombstones included, so delete-and-retry does not reset it).
- **P2-7. Behaviour on a transient failure is unspecified for "account first, device second".** The rule that a quota
  refusal is never presented as saved is right and matches D-107.3. But offline, a 5xx or a 429 are not quota refusals;
  the document says only that a refusal "is shown through the sheet error pattern". **Required:** state that only a
  definitive 422 `*_limit` blocks the import and shows the existing category error; a transient failure uses the same
  failure pattern ("could not import, try again") and creates no device-only item while the backbone is `active`; a
  local-only fallback stays a design gap for the human with an explicit label, as the document says. Also note that
  device-only items created before this rule remain and are not claimed as saved.
- **P2-8. G1 is larger than recorded and is a gate for anything beyond :8021.** `FileMediaLibraryStore.get()` reads and
  integrity-hashes the **entire** `index.json` on every call, and every personal-media read goes through it: the file and
  thumbnail route (once per image request), `visible_to` resolution, dictation/shadowing progress, `/api/media/my`. At about
  2.3 M entries a year that is a multi-GB parse per request, not just a big file. `upsert` and `delete` rewrite the whole
  file, and `_read` returns an empty map on a corrupt or unreadable index, after which `upsert` writes only the new entry:
  a single failed read followed by any upload would erase every other account's entries. The lock is a per-process
  threading lock. **Required:** record these three facts in G1 and make "personal media entries leave `index.json`"
  (PostgreSQL, a schema decision reserved by AGENTS §7) a prerequisite for enabling beyond :8021, or at minimum a
  guard that refuses to write after a failed read; do not present the per-account rails as sufficient.
- **P2-9. G2 is a correctness gap well below the pool size.** `GET /api/imports` returns at most 50 and the device keeps 100
  media records, so a new device sees at most the 50 newest imports of an account even though the pool admits 1,250; from
  the 51st import "opens on a new device" is silently false. **Required:** page the list (or raise the limit with a cursor)
  before the pool numbers are treated as usable; until then the effective product bound is 50 and should be stated.
- **P3-1..P3-9:**
  - **P3-1.** Section 4.5 "what exists" is stale at HEAD: `ImportSave` already has form `upload` and the media fields, and
    `pushImport` already sends media records through `mediaBody`; the legend still cites HEAD `8481e33` and "uncommitted
    edits". Refresh the facts.
  - **P3-2.** For form `upload` the server must take `bytes` and ownership from the stored media entry (visible to the
    account) and refuse an unknown or foreign `mediaId`, never from the client body, or the byte sum can be forged.
  - **P3-3.** Uploads already stored without an import record (made before 39b9f12/9a7b190) are not in the byte sum; state
    whether they are back-filled or ignored.
  - **P3-4.** The embedded-artwork thumbnail is uncapped by the code (up to the file size); cap or resize it so a request
    is bounded by 64 MiB plus a fixed thumbnail size.
  - **P3-5.** Count removal-pending bytes (files not yet confirmed deleted) in the sum, or the retry window lets disk grow
    beyond the rail; bound it by the 2,500 total rows x 64 MiB at worst.
  - **P3-6.** Two import records can name one `mediaId` (two devices); deleting one record must not delete a file another live
    record uses (delete on the last live reference).
  - **P3-7.** Overshoot by concurrent uploads is bounded by concurrency, not by the stream lock; say so.
  - **P3-8.** See above: live 1,250 versus the 2x rule.
  - **P3-9.** Reconcile the 2.9 s ceiling with the 46 a minute theoretical and fix "7 a day" (conservative either way).

### Refusal behaviour against D-107.3
Uploads: a refusal stores nothing and adds nothing to the device, reported by category in the existing sheet error pattern.
URL, YouTube and text imports: account first, device second while the backbone is `active` (a refused import is not
shown as saved to the account); a local-only fallback is recognised as needing an explicit label and, correctly, **no
drawn pattern exists, so both that label and the new refusal-category copy (en, vi, zh) are left as design gaps for the
human and recorded in `UI_BACKEND_GAPS.md`** (CLAUDE.md rule 7). Nothing is invented. P2-7 closes the transient case.

### Answers to Q13-Q16
- **Q13 (pools by `form`).** Yes, with an explicit table `text -> text pool; url, upload -> media pool` in code, and a
  rule that any future form (an article URL that stores fetched text) names its pool when added; do not infer the pool
  from the presence of a link.
- **Q14 (10 GiB, per account).** Acceptable as a safety rail and correctly per account across languages. Keep it a
  configuration value, keep the capacity and any lower product allowance as the human's decision, and measure upload size
  and frequency on the lane before fixing the default (condition 5).
- **Q15 (account first, device second).** Yes for definitive refusals, with P2-7 for transient failures; a local-only
  fallback only with a human-chosen explicit label.
- **Q16 (G1).** The Principal Architect with the media owner, through the AGENTS §7 schema process; **before** enabling
  beyond :8021, not after (P2-8).

### Conditions to start implementation
1. P2-6: pre-stream rate and size checks, hourly rail counted from upload records including tombstones.
2. P2-7: transient-failure behaviour stated; no device-only item while `active`.
3. P2-8 and P2-9: G1 and G2 restated as gates for anything beyond :8021 (index store move; paged imports list).
4. P3-1..P3-9 applied in the text, notably P3-2 and P3-6.
5. Measure upload size and frequency on the lane before the byte and count defaults are fixed; label PostgreSQL-only
   results as local execution.

Enabling the backbone beyond :8021 remains the human gate of D-107.5, which also requires the limits implemented and
independently approved, delete-import and uploaded-file deletion implemented, and code and migrations deployed together
after a backup.
