# Proposal: a server-side practice session identity for Speaking Summary

Status: **IMPLEMENTED ON BRANCH `claude/practice-session-identity`, AWAITING HUMAN REVIEW** (2026-10-07). Product
decisions: D-142 (they override this text where they differ; section 9 records the answers). The revision
`20261007_0029` is written but **NOT applied to any database** (only an ephemeral test database); nothing runs it at
startup (D-002). The code is behind `ORENA_PRACTICE_SESSION`, default off, so merging it changes nothing until the
human applies the migration to a lane runtime and turns the flag on. Review is the human's, directly on the branch
(D-142); production (8000) and preview (8010) are never touched.

Origin: D-141 (proposal approved, schema waits for the human), UI_BACKEND_GAPS S-15a, D-139 HD-8 ("this session while
it has tasks; the last 7 days when the session is empty"), D-104 D4 item I7 (Summary is a read, "this session" is a
window the server keeps).

Legend: **[V]** verified in code at `7faf3ca`; **[I]** inferred.

## 0. What exists today

- **Client ledger.** `static/orena/product/speaking-session.js` keeps `{kind, contentId, takeRef, facts, at}` in
  `sessionStorage`, scoped by account+language, max 50 entries. Writers: the recorder (scripted takes),
  Conversation (`screens/conversation/screen.js:261`), Free Talk (`free-talk/screen.js:227`), Situation
  (`situation/screen.js:133`). A new tab, reload-after-close or another device starts an empty ledger. [V]
- **Attempt rows.** `POST /api/speech/attempts` (`speech_api.py:426`) writes `speaking_attempts`
  (`persistence/models.py:408-433`, migration `20260828_0002`): `id uuid`, `user_id -> users.id ON DELETE CASCADE`,
  `language_code`, `take_id` (client token), `asset_id`, `segment_id`, `reference_text`, `transcript_text`,
  `dimensions`, `provenance`, `evidence` (JSON, no audio), `created_at`.
  `UNIQUE(user_id, language_code, take_id)` makes a retry idempotent; index
  `(user_id, language_code, created_at)`. [V] PostgreSQL only: the SQLite repository raises "Durable Speaking attempts
  require the PostgreSQL runtime" (`specialized_repository.py:992-996`). [V]
- **Window read.** `GET /api/speech/attempts?since=` already returns the learner's attempts newer than an instant,
  clamped to 7 days and never the future (`speech_api.py:443-480`, tested in `tests/test_d4_learner_activity.py:150`). [V]
  Today the client could pass its tab-start time; a tab that opens later still cannot name a session another tab began.
- **Owner resolution.** The repository scopes by `(stable_uuid("user", current_user_key()), current_language_code())`
  (`specialized_repository.py:1182-1189`). Account-keyed tables hang off `users.id`; account deletion is the
  D-055(b) workflow, which already lists `speaking_attempts` (D4 §2.6). [V]
- **What tasks write.** Scripted takes and the spoken `voice-feedback`/`voice-response` paths post
  `speaking_attempts` rows. Conversation turns are `works` kind `conversation` + `work_turns` (D4 I6, behind
  `ORENA_ACCOUNT_BACKBONE`). A typed Free Talk or Situation answer is a `works` `response` (D4 I8). A conversation
  that was only spoken, or a Situation reaction with no recording, creates **no** attempt row. [V/I]
- Alembic head in the tree `20261004_0025`; `0024`, `0026`-`0028` sit in `migrations/proposed/`. [V]

## 1. Definition of a practice session

A **practice session** is a run of the learner's completed speaking tasks, for one account and one learning
language, in which no two consecutive tasks are **30 minutes or more** apart (active while elapsed < 30:00; expired at exactly 30:00) (server constant, one named value,
not per-user).

- **Start.** The first completed task when none exists inside the idle window. There is no "start session" action.
- **End.** Implicit: the window lapses at exactly 30:00 after the last task. There is no stored end, no "End session"
  button (HD-11 "End" is the conversation's end, unrelated).
- **Cross-device / cross-tab.** The session belongs to (account, language), not to a device: a take on the phone
  five minutes after one on the laptop is the same session. Switching learning language is a different session.
- **A task** is one completed spoken task that already writes a `speaking_attempts` row (scripted take, Free Talk
  spoken answer, Situation reaction that is recorded, Conversation spoken turn once I8 writes it). **Typed answers
  and unrecorded Conversation turns are not tasks in v1** (no row to count; see Q2).
- **Summary scope (HD-8, unchanged).** "This session" is the current session while it is inside its idle window and
  has tasks; otherwise the last 7 days. The Summary never shows a session older than its idle window as "this
  session".

## 2. Smallest data shape

**Chosen: one nullable column on the existing row, no sessions table.**

```text
speaking_attempts.practice_session_id  UUID NULL        -- minted by the server, never by the client
INDEX ix_speaking_attempts_session (user_id, language_code, practice_session_id, created_at)
```

- The session is identified by the id its member rows share; its start is the member's minimum `created_at`, its
  last activity the maximum. Both are derivable, so nothing can drift out of step (a sessions table would be a second
  owner of "when did it start"). [I]
- **Why not a table.** The session carries no data of its own in v1 (no title, goal, end reason). A table adds a
  second row to write per task, a second lifecycle for D-055(b) to enumerate, and a race on its own update. If a
  later feature needs session-level data, the column is the foreign key a table would adopt (additive).
- **Old rows** keep `NULL`; there is no backfill (D4 §2.5: no bulk rewrite). They are served by the 7-day fallback.
- **Retention and deletion.** The column lives on a row already in the D-055(b) enumeration and already
  `ON DELETE CASCADE`; no new table, no new destructive path, no retention rule beyond the attempt's. Deleting the
  account's attempts removes the session. [V/I]
- **Scale (~100k users).** One 16-byte column. Finding the live session reads one row through the existing
  `(user_id, language_code, created_at)` index (`ORDER BY created_at DESC LIMIT 1`); reading a session is a
  range scan on the new index bounded by one account's attempts in a few hours. No cross-account query, no hot row.
  The new index adds about one index entry per attempt; if the human prefers, it can be partial
  (`WHERE practice_session_id IS NOT NULL`). [I]

## 3. API changes

All additive; absent fields keep today's behaviour.

- **`POST /api/speech/attempts`** (server decides, client sends nothing new). Inside the existing transaction:
  take a transaction-scoped advisory lock on `(user_id, language_code)`, read the latest row's
  `created_at` and `practice_session_id`; if `now - created_at < 30 min` and it has an id, join it, otherwise mint a
  new UUID; insert. Response `item` gains `practice_session_id`. The lock serialises two devices finishing at once so
  they cannot mint two sessions. [I]
- **Idempotency.** A replay of the same `take_id` returns the stored row and its original `practice_session_id`; the
  session is assigned once, at first write, and never re-derived. The client never needs to remember or send an id,
  so a retry after an offline gap cannot split or merge sessions.
- **Offline / tab behaviour.** A take queued offline and sent later joins whatever session is current when it is
  *written* (server time), not when it was recorded. Accepted: the server owns time, and a client clock is never a
  token (D4 §2.4). Closing a tab ends nothing; the idle window does.
- **`GET /api/speech/attempts?session=current`** (new optional param, mutually exclusive with `since`; 422 if
  both). Returns the items of the live session (the latest attempt's session if elapsed < 30 min, else empty), newest
  first, bounded by `limit`, plus
  `session: {id, started_at, last_activity_at, expires_at, count}` or `session: null`. `?session=<uuid>` for the
  learner's own past session is out of scope (Q3).
- **Summary.** `speak-summary/model.js` calls `session=current`; if `session` is null or `count` is 0 it calls
  `since=<now-7d>` exactly as it can today (HD-8). Facts that have no row (typed tasks, the in-tab ledger) are not
  merged server-side. `speaking-session.js` is then reduced to presentation (`facts` labels for the current tab's
  just-finished task) or deleted once every writer posts a row; either way it stops being the count's source.

## 4. Migration plan

1. One additive Alembic revision (next free number after the proposed `0028`, rebased at implementation): add the
   nullable column and the index. No default, no backfill, no constraint, no rewrite. On PostgreSQL a nullable column
   without a default is a metadata-only change; the index build locks `speaking_attempts` writes briefly, so the
   revision states a measured duration at the rehearsal volume (the D4 §5 rule: over 10 s changes the plan, e.g.
   `CREATE INDEX CONCURRENTLY` outside the transaction).
2. **Reversible:** `downgrade` drops the index then the column. Up/down/up is rehearsed on a restored PostgreSQL copy
   before any apply (D4 §6 pattern). Old code ignores the column; new code tolerates `NULL`.
3. **No automatic startup Alembic** (D-002): the revision is applied only by `scripts/bootstrap_runtime_schema.py`
   under the human's gate, one revision per invocation, after a backup. PostgreSQL is authoritative; SQLite is test
   only. The SQLite test backend has no durable attempts, so the session logic is tested against the PostgreSQL
   repository (as `test_d4_learner_activity.py` already does) and the SQLite path keeps raising as it does today.
4. Order: review -> human authorizes -> revision + code behind the flag -> rehearsal -> human applies to the lane
   runtime -> flag on there -> merge -> a later human gate for :8000. Nothing here touches production or preview.

## 5. Rollout flag

`ORENA_PRACTICE_SESSION=off|on`, default **off**, passed from `compose.yaml` like `ORENA_ACCOUNT_BACKBONE`. Off:
the POST writes `NULL`, `session=current` answers 404 `practice_session_disabled`, and Summary keeps the client
ledger plus the 7-day fallback (today's behaviour, S-15a stays a documented gap). On: the behaviour above. A
schema-present, flag-off runtime is therefore always safe, and turning the flag off degrades honestly.

## 6. Tests

- Two POSTs 10 minutes apart share an id; 31 minutes apart differ; a replay of one `take_id` returns the original id.
- Two simultaneous POSTs from a fresh account (threads) produce one id (advisory lock).
- Two accounts and two languages never share a session; `session=current` is scoped by the request owner.
- `session=current` returns only the live session, `session: null` once the window lapses, 422 with `since`.
- Old `NULL` rows are never returned by `session=current` and still by `since`.
- Flag off: column stays `NULL`, route 404, no behaviour change in the existing attempt tests.
- Migration up/down/up on PostgreSQL; downgrade with populated rows loses only the column.
- D-055(b) enumeration test unchanged (no new table); a deletion test asserts the session vanishes with its rows.
- `.mjs` gate: Summary uses `session=current`, then the 7-day fallback when empty, in EN/VI/ZH; no client count source.

## 7. Risks

- **Session splitting by the idle rule.** A learner who pauses 31 minutes gets two sessions; Summary then shows the
  newer. Accepted by definition; the constant is one place to change.
- **Server time vs. recording time** for offline takes (section 3). Accepted; documented.
- **Advisory lock** adds a short per-account serialisation on attempt writes; bounded by one tiny read. [I]
- **Count gaps.** Typed and unrecorded tasks are not counted (Q2); the Summary must not claim they are.
- **Index cost** on a growing `speaking_attempts`; mitigated by the partial-index option.

## 8. Alternatives considered

1. **Keep the client notion (status quo).** Zero schema; wrong across tabs, reloads and devices by construction;
   S-15a stays open. Rejected as the goal, kept as the flag-off behaviour.
2. **Derive sessions at read time from `created_at` gaps, no column.** No schema at all and no write-time lock.
   Cost: every read scans and clusters the learner's recent attempts, the "current" session is recomputed on each
   call, and a later change of the idle constant silently rewrites history. A viable fallback if the human declines
   any schema change; it needs no migration and no flag. [I]
3. **A `practice_sessions` table** (start, last activity, optional end) with a FK on attempts. Allows session-level
   data and an explicit End; costs a second write per task, a second D-055(b) entry and an update race. Not needed
   by any drawn design.
4. **Client-minted session id sent on every write.** Splits across devices, trusts a client token, no server idle
   rule. Rejected.
5. **Reuse `works` (kind `session`).** Works are incarnation-keyed and backbone-gated; Speaking attempts are
   account-keyed and not. Mixing two owners for one concept. Rejected.

## 9. Open questions, resolved by D-142 (2026-10-07)

- **Q1 (timeout).** 30 minutes of inactivity; qualifying activity refreshes the window; time is the server's. Done:
  one constant, `PRACTICE_SESSION_IDLE_MINUTES`.
- **Q2 (typed / unrecorded tasks).** No new learner persistence to count them. They count only if an existing durable
  server-side record already represents them, and never as pronunciation/audio attempts. Implementation finding: no
  durable record carries a session identity today (typed answers are `works` rows behind `ORENA_ACCOUNT_BACKBONE`,
  unrecorded conversation turns and Situation reactions leave nothing), so in this slice they are **left out** and the
  Summary must not claim them. A later slice may link `works` rows to the session id without new persistence.
- **Q3 (past sessions).** Only the current session is needed; no history browsing, no `?session=<id>`.
- **Q4 (backfill).** None: legacy rows keep `NULL` and are served by the 7-day fallback.
- **Q5 (read-time clustering).** Not the canonical model for new activity (persisted identity chosen); it may later be
  a read-only legacy approximation.
- **Q6 (reviewer).** The human, directly on the branch; no other reviewer unless asked.

Nothing in this proposal decides the D-104 holds (general sync protocol, export format, deletion runtime).

## 10. Implementation notes (branch)

- Revision `20261007_0029_practice_session_id`, `down_revision = 20261004_0025` (the head in `migrations/versions/`;
  the proposed 0024/0026-0028 sit outside the chain and are re-parented when promoted).
- `POST /api/speech/attempts`: flag on -> the repository assigns the id under a per-(account, language) lock
  (`pg_advisory_xact_lock` on PostgreSQL, a process lock on the SQLite test engine); a replay keeps the stored id.
- `GET /api/speech/attempts?session=current` -> `{items, session, progress}`; `session` is null when idle >= 30 minutes;
  404 `practice_session_disabled` with the flag off; 422 when combined with `since`, `asset_id` or `segment_id`.
- Client: Summary asks the server once; a 404 or a null session keeps today's client ledger and 7-day fallback.
