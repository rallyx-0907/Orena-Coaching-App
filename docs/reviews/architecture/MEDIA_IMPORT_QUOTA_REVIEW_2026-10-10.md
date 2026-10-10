# Architecture review: media import minutes quota (PR #124)

| | |
|---|---|
| Reviewer | claude-opus-5-5, Delegated Architecture Reviewer (independent of the implementer) |
| Reviewed commits | First review `5ce3567e60532a493f1203f89b94ae0c5cff205e` (base `b93b2388`); re-review `5ce3567e..a9388c3d2a7b233dc440bfe0d9d29395516ecb21`; re-review 2 `a9388c3d..8b25f1d5a609bd18b19d7881f15432e41e95efef` |
| Final verdict | **APPROVE** at exact reviewed SHA `8b25f1d5a609bd18b19d7881f15432e41e95efef`. Earlier: REQUEST CHANGES at 5ce3567e (P1-1 recover before quota wiring, P1-2 backstop overriding deferred settlements), APPROVE at a9388c3d with recommended P2-R1 — all superseded. |
| After the reviewed SHA | Documentation only: this record; decision number assigned (D-168); merge of main if any. Not product approval; not activation authorization. |

# Architecture review: media import minutes quota (`media.import`, D-168)

| | |
|---|---|
| Reviewer | claude-opus-5-5, **Delegated Architecture Reviewer** (AGENTS.md "Architecture review authority"); independent, did not write this change |
| Reviewed commit | `5ce3567e60532a493f1203f89b94ae0c5cff205e` (branch `feat/quota-media-import`), diff `b93b2388..5ce3567e` |
| Context read | `media_quota.py` (new, whole), `product/quota.py` (diff + admission core, `Ticket`, `begin`, `_reserve`, reconciler), `persistence/quota_repository.py` (`dispatch/settle/release/stale_dispatched`), `reference_backbone.py` decisions, `media_source_import.py`, `media_transcript_pipeline.py` (enqueue/retry/recover/_job/_run/_transcript/_speech/_audio_source/audio_chunks), `media_library_api.py`, `media_api.py` (`/import`, `/import/status`, `/translate`), `listening_api.stored_media_payload/prepare_media_meanings`, `admin_console_api` reprocess, `app.py` wiring order, client `api.js`, `screens/import/sheet.js`, `plan/quota-notice.js`, `plan/copy.js`, D-168 text, QTA-17, the PR body, new tests; `feat/quota-voice` (`33782356`) for overlap |
| Mode | Read-only. No edits/commits/pushes; no project runtime touched. Own throwaway `postgres:17-alpine` (`quota-m-review-pg-22130`, 127.0.0.1:55441), stopped. |

## VERDICT: REQUEST CHANGES

The request-side design is sound: every learner paid path of the two metered routes is behind an all-or-nothing reservation
taken before anything is fetched/stored/heard, the length is the server's, Whisper input is bounded by the reservation, the
core changes are minimal and keep the lock order, and the PostgreSQL proofs hold. But the **restart / deferred-settlement
lifecycle does not work in the production wiring**, and its backstop then charges the full reservation for imports the human
decided must settle 0. Two P1, reproduced below. Not product approval; not activation authorization.

## Evidence (local execution, not CI)

- Targeted, with `ORENA_TEST_POSTGRES_URL` on my throwaway PG: `test_quota_media_import.py`, `test_quota_media_import_postgres.py`,
  `test_media_import_telemetry.py`, `test_quota_gate.py`, `test_quota_gate_postgres.py`, `test_quota_orena_message_postgres.py`,
  `test_quota_pronunciation_postgres.py`, `test_admin_authorization_matrix.py`: **401 passed, 0 skipped**.
- Full `pytest -q test_app.py tests` (sqlite, app image, `-m 2g`): **4920 passed, 441 skipped, 0 failed**.
- Host: `test_media_import_quota.mjs` PASS, `test_orena_screen_plan.mjs` PASS, `validate_browser_esm_graph.mjs` OK (276 modules).
- Reviewer probes (scratchpad `qm/probe/test_reviewer_probe_media.py`, on the PR's own `World` harness): 5/5 reproduce the
  scenarios below (A, B = P1; C = older route unchanged when off; D = `/translate` open while enforced; E = `retry()` unmetered).
- Groq price checked at console.groq.com/docs/model/openai/gpt-oss-120b: input $0.15, cached $0.075, output $0.60 per M - matches.
- `git merge-tree 5ce3567e 33782356` (voice): only `DECISION_LOG.md` conflicts textually; `quota.py` auto-merges - but see P2-2.

## Findings

### P1-1 `recover()` runs before the quota runtime exists: restart semantics are false in production
`app.py:732` calls `_media_pipeline.recover(...)` at import time; `_quota.configure_quota(...)` runs at `app.py:1099`. Until
then `quota._runtime.repository is None`, so `dispatch_operation/settle_operation` raise (`quota.py:639 _store_repository`).
- Deferred intents (`media_transcript_pipeline.py:350`): `settle()` fails every time at startup, after sleeping 0.5 s + 1 s
  per pending entry (`media_quota.py:259`) - startup is slowed 1.5 s per pending entry and the intent is never written.
- Re-queued jobs (`:358` -> pool): the job's `_dispatch_quota` races configuration; losing it stops the import with
  `quota_unavailable` (the learner's import fails after a restart), and its own settle may fail the same way.
- Probe B (reproduced): job dispatched, process dies, restart -> entry `failed / quota_unavailable`, intent `0|failed:...`,
  0 ASR calls; 6 h later the reconciler settles **60 of 60 s** (`quota.py:797`, ABANDONED_SETTLES="admitted").
- The PR's restart tests call `wire(engine)`/`enforced_runtime` **before** `recover()`, so they cannot see this.
**Required fix:** run media recovery after quota wiring (move `recover` below `configure_quota`, or call it from the startup
hook after the reconciler starts); never sleep on an unconfigured store; add a test that asserts the app's order (e.g. import
`app` and check `quota.runtime().repository` is set, or that recover is invoked from startup), and a restart test that runs
recover with the runtime unconfigured and then configured.

### P1-2 A deferred settlement is retried only at the next restart; the reconciler overrides it with the full reservation
`_settle_quota` keeps `quota_settle=<actual>|<ref>` when the store blips (3 tries, 1.5 s), and only `recover()` (startup)
retries it. A process that stays up past `ASYNC_RECONCILE_AFTER` (6 h) lets `reconcile_once` settle the still-`dispatched`
row at `admitted_units` (`quota.py:794-797`). Probe A (reproduced): ASR fails -> intent 0; store healthy again; reconciler ->
**consumed 60**. This contradicts the human decision "failures settle 0" and the D-168 text ("written by the next recover()").
**Required fix:** retry pending intents periodically in-process (e.g. the pipeline sweeps entries with an undecided
`quota_settle` on a timer well under 6 h), and/or have the async backstop not charge `admitted` for an operation whose entry
records an intent (or settle async abandons at 0 - a human default; D-168 point 4 must then say which). Add tests for both.

### P2-1 `POST /api/media-learning/translate` is a learner-reachable paid Groq path left open while enforced
`media_api.py:415` translates an arbitrary client-supplied transcript (no cap on segment count, 20 000 chars each) with the
media translation provider (Groq `gpt-oss-120b` by default). Probe D: reaches the provider with `media.import` enforced. The
QTA-17 audit omits it, though the PR's own reasoning for refusing `/import` applies equally. **Fix:** `refuse_unmetered`
it like `/import` (the UI does not need it: `translateMedia` has no caller in `static/orena` besides `api.js`), or record it
as a human-decided exception in QTA-17/D-168. Non-blocking for this meter, but required before :8000 activation.

### P2-2 Semantic merge conflict with `feat/quota-voice`
Voice (`33782356`) deletes `quota.refuse_unmetered` (its only previous caller became metered); this branch adds a new caller
(`media_api.py:265`). The merge is textually clean in `quota.py`, and the result raises `AttributeError` on every
`/api/media-learning/import` call, enforced or not. Whichever merges second must keep the helper (CI's
`test_the_older_import_route_is_refused...` will catch it). Also renumber D-168/D-16T in `DECISION_LOG.md`.

### P3 (record or fix when convenient)
1. `pipeline.retry()` (`:326`) re-runs a settled entry with no hold -> unmetered Whisper (probe E). Only the admin reprocess
   of shared media calls it today; guard it (personal + settled -> refuse) before any learner retry exists.
2. `existing_import` treats `state is None` as live (`media_quota.py:165`): an entry stored but never queued (crash between
   put and enqueue) is settled 0 by recover yet answered forever as "already imported" for free, never processed.
3. `existing_import` scans every personal entry per request (O(N) over all learners); `source_lock` is process-local (correct
   only while the JSON index is single-process - say so where workers are configured).
4. Core: `dispatch` returns `duplicate` without the incarnation check, so a re-queued job of a deleted account proceeds
   (pre-existing core behaviour; account deletion removes personal entries, so low exposure).
5. Telemetry: `record_token_operation` labels every pipeline translation `origin: "learner"`, including admin shared imports.
6. Client: 503 `quota_unavailable` / `media_duration_unavailable` and 403 `feature_not_in_plan` show the generic import error
   (recorded QTA-17 e5); acceptable, honest.
7. A removed unfinished import is free even after providers ran (accepted, D-168 9); the transcript is not readable before
   `ready` (`stored_media_payload` gates on ready/held), so there is no read-then-delete exploit.

## Answers to the focus questions
1. **Paid paths.** `/source` and `/upload`: admitted before work (incl. direct-URL download, YouTube page/captions). `/import`:
   503 while enforced, unchanged when off (probe C). Admin imports: unmetered by design. `recover()`: see P1-1. Supadata only
   via the refused `/import`. Translation re-runs: learner GETs never translate (`translate=None`); `/translate` is P2-1.
   No learner re-transcribe endpoint; admin `reprocess` is shared-only (P3-1).
2. **Duration truth.** File: ffprobe declared length reserved; Whisper input = re-encoded mp3 chunks probed after decode
   (`audio_chunks` + `_probe_seconds`), checked `total > reserved + 2` before the ledger and the first ASR call
   (`_speech`) - a header that under-declares is stopped (`duration_mismatch`, settles 0); one that over-declares is charged
   `min(reserved, ceil(decoded))`. YouTube: yt-dlp metadata (not learner-controllable); captions-end fallback only feeds the
   free captions path, and if captions are unusable the ASR check stops longer audio. >5400 s file: 422; YouTube capped at
   5400 (accepted). Holds.
3. **Core changes.** `dispatch/settle/release_operation` are thin wrappers over the reviewed repository verdicts; no new SQL,
   lock order unchanged (incarnation -> reservation; bucket -> reservation); settle is idempotent (`duplicate` /
   `payload_conflict`), no double settle observed. `reconcile_once` per-meter groups correct and tested on PG. The defects are
   in the wiring/backstop interplay (P1-1, P1-2), not the core.
4. **Idempotency.** Proven (any link form, file sha256, concurrent same-file on PG -> 1 import / 1 charge); failed -> new charge.
5. **Persistence.** `quota_op/quota_units/quota_settle/source_key` are strings in the existing entry's `source` map, no schema,
   no new record type, removed with the entry and by `delete_all_owned_media`. Not a §7 human gate in my judgement (P3,
   record-only); D-168 should state that a file's sha256 is now kept as a dedupe fingerprint.
6. **Telemetry.** Rows separate from quota; Whisper unchanged; `media_translation` priced correctly; Supadata unpriced, never 0.
7. **Client.** 429 shown truthfully EN/VI/ZH with the server's figures; no client enforcement; no idempotency key sent.
8. **Tests.** Strong on the request side. Missing: app-order restart (P1-1), long-running process deferred-intent vs
   reconciler (P1-2), `/translate` while enforced, `retry()` of a settled entry.

## Required before merge
P1-1 and P1-2 fixed with tests; P2-2 handled at merge. P2-1 before :8000 activation (or a recorded human exception).

---

# Re-review

| | |
|---|---|
| Reviewer | claude-opus-5-5, Delegated Architecture Reviewer (independent; did not write the fixes) |
| Reviewed | `5ce3567e..a9388c3d2a7b233dc440bfe0d9d29395516ecb21` (one commit on the reviewed SHA) |
| Verdict | **APPROVE** at exact SHA `a9388c3d2a7b233dc440bfe0d9d29395516ecb21` - no P0/P1 remains. One P2 recommended (not blocking), P3s below. Not product approval; not activation authorization (:8000 stays a human GO). |

## Evidence (local execution, not CI)

- Own throwaway `postgres:17-alpine` (`quota-m-review-pg-28719`, `-m 1g`, 127.0.0.1:55441), stopped afterwards. One test container at a time, `-m 2g`.
- Targeted with PostgreSQL: `test_quota_media_import.py`, new `test_quota_media_import_lifecycle.py`, `test_quota_media_import_postgres.py` (14, incl. the two new PG proofs), `test_media_import_telemetry.py`, `test_quota_gate.py`, `test_quota_gate_postgres.py`, `test_quota_orena_message_postgres.py`, `test_quota_pronunciation_postgres.py`, `test_admin_authorization_matrix.py`: **415 passed, 0 skipped**.
- Full `pytest -q test_app.py tests` (sqlite): first run **2 failed / 4930 passed / 443 skipped** (574 s, host under load, failure names not captured); rerun **4932 passed, 443 skipped, 0 failed** (453 s). I read the 2 as load-timing flakes, not regressions of this diff; not reproduced.
- Host: `test_media_import_quota.mjs` PASS; `validate_browser_esm_graph.mjs` OK (276 modules).
- My probes, **v1 unmodified** (`qm/probe/test_reviewer_probe_media.py`; each asserts the defect, so a failing assertion = fixed):
  - A: still "passes", but only because the probe calls `reconcile_once` with no decision hook and no intent timer, i.e. not the production wiring. Under the production wiring (v2 probes A2/A3, below) the charge is 0. **Fixed.**
  - B: now fails its assertion. The early recover leaves the import `running`, untouched, not failed with `quota_unavailable`. **Fixed.**
  - D: now fails its assertion (`/translate` never reaches the provider while enforced). **Fixed.**
  - E: `retry()` of a settled personal import is refused (state stays failed, 0 ASR calls, 0 charge). **Fixed.**
- **Probes v2** (`qm/probe/test_reviewer_probe_media_v2.py`, production order: `configure_quota` -> `configure_async_decision` -> `recover` -> timer/reconciler):
  - A2: a deferred failure intent is written by one `IntentSchedule` tick, so consumed is 0.
  - A3: with the timer never run, the backstop settles `0, reconciled:failed:pipeline_error`.
  - B2: a job that had dispatched before a crash is re-queued after configuration, re-dispatches as `duplicate` and settles 60 on success.
  - F: see P2-R1.

## Core hook in `reconcile_once` (lock order, double settle, sync meters)

- **Lock order unchanged.** `stale_dispatched` returns a materialised list and its connection is closed before the callback. `media_quota.decide` reads only the JSON index (no DB connection, no quota call). The repository `settle`/`release` keep the reviewed order (bucket -> reservation). The pipeline never calls quota while holding the index's update lock (`_mark_quota` only rewrites `source`), so there is no inversion between the index lock and DB locks.
- **No double settle.**
  - When the reconciler and the job/timer race, the second one gets `duplicate` (same units and ref) or `payload_conflict`. The reconciler's ref is prefixed `reconciled:`; the job's is not.
  - The store writes nothing on a conflict, and `_settle_quota` then marks the entry `done`.
  - The amounts agree whenever both sides read the same intent or outcome.
- **Sync meters unaffected.** The hook applies only to the `ASYNC_METERS` group (identity check). The sync group's behaviour and thresholds are unchanged, and the voice merge only touches admission (`_reserve`/`begin_voice`), not `reconcile_once`.
- An exception from the hook leaves the row for the next tick, never guessed. An unreadable index (`last_read_issue`) is a raise, not "gone".

## Findings

**P2-R1 (recommended, not blocking): a re-queued job "in play" after more than 6 h of downtime is charged the full reservation even if it then fails.**
- Scenario: the job dispatched, the process died mid-job, and the server stayed down for more than 6 h.
- At restart, the startup reconciler tick sees the row (`updated_at` is the original dispatch; the re-dispatch answers `duplicate` and writes nothing) and the entry `queued/running`. `decide` returns None, so the row is settled as admitted.
- If the re-run then fails, its 0 is refused as `payload_conflict`. Probe F: `failed / pipeline_error`, consumed 60.
- This is rare (a crash mid-job plus 6 h down) and is documented in D-168 point 4 as a deliberate choice, but it conflicts with "failures settle 0".
- Suggested fix: when the owner reports the job in play, skip the row (`continue`) up to a hard ceiling (e.g. 24 h), or have a `duplicate` re-dispatch touch `updated_at`.

**P3**
1. `decide` returns None, which means settle as admitted, for an entry whose marker is `done` while its row is still `dispatched`. With the current code paths this looks unreachable (the marker is written after the store answered), but the fail direction is "charge"; prefer `continue`.
2. `decide` scans the whole index once per stale row: up to 200 × N reads per tick. Acceptable now; worth an index later.
3. Where the quota store disappears after admissions (tables missing), `recover()` skips metered entries indefinitely. They stay `queued`, and `existing_import` answers them as already imported. This is an operational edge, since enforcement is 503 in that state anyway.
4. An index that reads as empty without setting `last_read_issue` (for example a mis-mounted volume) makes every stale import `no-entry`, which settles 0. It fails toward undercharge, never toward paid work.
5. P2-2 (the voice merge) is resolved by agreement: the voice branch keeps `quota.refuse_unmetered`. Renumber D-168/D-16T at merge.

## Original findings, status

| Finding | Status |
|---|---|
| P1-1 recover before configure | **Fixed.** `app.py` calls `recover` after `configure_quota`; recover skips metered entries with no store; `settle` never sleeps on an unconfigured store; the order is pinned by a test |
| P1-2 deferred intent vs backstop | **Fixed.** `IntentSchedule` runs `settle_pending` every 5 min (≤200 per tick); the backstop asks `media_quota.decide` (intent / outcome / 0 when gone); PG proofs |
| P2-1 `/translate` open | **Fixed.** 503 `quota_media_import_not_metered` while enforced; unchanged when off |
| P2-2 voice merge | Resolved by agreement (helper kept) |
| P3 retry / never-queued / telemetry origin / sheet copy / sha256 note | **Fixed.** Copy in EN/VI/ZH; the shared-import origin is None; D-168 point 5 notes the sha256 |

---

# Re-review 2

| | |
|---|---|
| Reviewer | claude-opus-5-5, Delegated Architecture Reviewer (independent) |
| Reviewed | `a9388c3d..8b25f1d5a609bd18b19d7881f15432e41e95efef` (core `quota.py` +5 lines, `media_quota.decide`, tests, D-168 text) |
| Verdict | **APPROVE** at exact SHA `8b25f1d5a609bd18b19d7881f15432e41e95efef`. No P0/P1/P2. Not product approval; not activation authorization. |

**Evidence (local execution, not CI).**
- Own throwaway `postgres:17-alpine` (`quota-m-review-pg-6993`, `-m 1g`), stopped afterwards. One test container at a time (`-m 2g`).
- Media suites (hermetic, lifecycle, postgres, telemetry) plus the quota gate, gate PG, orena-message PG, pronunciation PG, `test_orena_quota_persistence_postgres.py` and the admin matrix: **451 passed, 0 skipped**.
- Probe F, unmodified: after the startup tick the row is still `dispatched` and consumed is 0; the re-run then fails and **consumed stays 0** (before: 60). **P2-R1 fixed.**
- Probes A2/A3/B2 are unchanged: 0 / 0 / 60.
- P3-1 fixed: `decide` now returns the recorded outcome for an entry marked settled whose row is still open, never the full reservation (new test).

**Core change.**
- The new `elif` sits inside the `meters is ASYNC_METERS and _async_decision is not None` branch.
  - Sync meters are untouched.
  - An async meter with no hook keeps the old 6 h admitted behaviour.
- It only adds a `continue`: no new repository call, no transaction open across the hook, so the lock order is unchanged.
- Double settle stays impossible: repository idempotency is unchanged, and a later settle by the job gets `settle` (the row is still open) or `duplicate`/`payload_conflict`.
- `updated_at` is `DateTime(timezone=True) NOT NULL` (migration 0007).
  - PG rows are tz-aware and never None, so the aware/aware comparison cannot raise.
  - The "no updated_at, leave" branch is reachable only from a test double.

**Can a row be left open forever?**
- **Entry deleted while in play:** `cancel_entry` settles 0. If that fails, `decide` answers `0, no-entry`. Settled.
- **Hook keeps returning None:** a `duplicate` re-dispatch writes nothing, so `updated_at` keeps aging. At 24 h the row is settled as admitted. Bounded.
- **Malformed units on the entry:** None, then the ceiling. Bounded.
- **Index unreadable:** the hook raises and the row waits. It is open only while the index stays unreadable; that is intentional, pre-existing, and an operational alarm rather than a quota decision.
- **Never-dispatched (`reserved`) rows:** still released at 6 h, as before. A job re-queued after a long outage then fails closed at dispatch (`already_released`), with 0 charge and no paid work. Acceptable.

**Remaining P3 (unchanged, non-blocking).** Earlier P3-2..4: `decide` scans the whole index once per stale row; `recover()` skips metered entries indefinitely if the quota store disappears; an index that reads empty without flagging an error settles at 0. Also renumber D-168/D-16T at merge.
