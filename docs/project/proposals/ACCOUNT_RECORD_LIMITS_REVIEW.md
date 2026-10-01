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
