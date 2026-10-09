# Architecture review: pronunciation minutes quota (PR #119)

| | |
|---|---|
| Reviewer | claude-opus-5-5, Delegated Architecture Reviewer (independent of the implementer) |
| Reviewed commits | First review: `8ff561b86b988f6e6b2cd9ed614c1be9ad7181a5` (base `5e02173e`). Re-review: `8ff561b8..fb61ce626f4fd8dc062811ca4671f305fff82ba8` |
| Final verdict | **APPROVE** at exact reviewed SHA `fb61ce626f4fd8dc062811ca4671f305fff82ba8`. First review: APPROVE WITH REQUIRED CHANGES (P2-1), superseded. |
| After the reviewed SHA | Documentation and comments only: this record; P3-11 (the human's NO_SPEECH_CHARGED=True and "record again" decisions recorded, "pending" labels removed); decision number assigned (D-165); merge of main. Not product approval; not activation authorization. |

# Architecture review - PR #119 "Quota: pronunciation minutes enforced (pronunciation.audio)"

- Reviewer: claude-opus-5-5, acting as **Delegated Architecture Reviewer** (AGENTS.md "Architecture review authority"). Independent: did not write this change.
- Reviewed commit: `8ff561b86b988f6e6b2cd9ed614c1be9ad7181a5` (branch `feat/quota-pronunciation`), diff `5e02173e..8ff561b8` (one commit), PR body of #119 (DRAFT).
- Context read: `writing_coach/product/quota.py` (whole admission core), `speech_api.py`, `speech_pronunciation.py`, `ai/audio_telemetry.py`, `ai/platform._persist_operation_telemetry`, `core/http_security.py` rate groups, `speaking_library.py` (model-reference path), client `capabilities/speaking-take.js`, `infrastructure/api.js`, `quota-headers.js`, `screens/plan/*`, Speak/Compare/Shadowing changes, D-161/D-163 and the new D-165 text, the new tests.
- Mode: read-only. No edits, commits or pushes; no project runtime touched.

## VERDICT: APPROVE WITH REQUIRED CHANGES

No P0 or P1. The server-side design is sound: every paid Azure pronunciation call is behind admission when the meter is enforced, the reserved and settled seconds are measured from the exact PCM bytes the server itself sends to Azure (no client claim, no second decoder), the ticket is resolved inside the worker thread on every exit, and the PostgreSQL proofs hold under repetition. One P2 is **required before merge** (a learner dead-end on the client, masked by the PR's own gate, small and client-only). One product default needs the human's explicit answer **before activation on :8000** (`NO_SPEECH_CHARGED`). The rest are P3.

## Evidence (local execution, not CI)

All runs in an ephemeral `ai-writing-coach:local` container, worktree mounted read-only, `PERSISTENCE_BACKEND=sqlite`, Google vars cleared, `APP_ENV=development`; PostgreSQL proofs against my own throwaway `postgres:17-alpine` (`quota-d-review-pg-15093`, 127.0.0.1:55437).

- `tests/test_quota_pronunciation.py tests/test_quota_pronunciation_postgres.py tests/test_quota_gate.py tests/test_quota_gate_postgres.py tests/test_quota_orena_message_postgres.py tests/test_speech_pronunciation.py tests/test_speech_pronunciation_api.py tests/test_audio_cost.py` with `ORENA_TEST_POSTGRES_URL` set: **162 passed, 0 skipped**.
- `tests/test_quota_pronunciation_postgres.py tests/test_orena_quota_persistence_postgres.py` repeated 5 times: **45 passed** each run (concurrency proofs stable: 20 x 20 s takes -> exactly 15 admitted / 15 provider posts; 5 takes on the last 10 s -> exactly 1; same take x4 concurrently -> 1 post, 1 charge of 8 s).
- Full `pytest -q test_app.py tests` (sqlite): **4877 passed, 429 skipped** (matches the PR body; skips include the PostgreSQL proofs, run separately above).
- JS gates: `test_speaking_take.mjs`, `test_orena_screen_speak.mjs`, `test_orena_screen_plan.mjs` PASS; `validate_browser_esm_graph.mjs` OK (271 modules).
- Reviewer probe with the **real ffmpeg 7.1.5 in the app image** (`normalize_audio_to_pcm16_wav` + `wav_seconds`, compared with `ffprobe` sample counts of the bytes that would be sent):

| Client input | Sent to Azure (ffprobe) | `wav_seconds` | Reserved units |
| --- | --- | --- | --- |
| Opus 48 kHz stereo 7.4 s | 118400 samples @16k mono = 7.4 s | 7.4000 | 8 |
| MP3 8 kHz 7.4 s | 7.4 s | 7.4000 | 8 |
| WAV 3 s with 65 KB of injected metadata (`comment`, `title=data...`) | 3.0 s; output has a 65050-byte `LIST` chunk before `data` | 3.0000 | 3 |
| WAV 75 s @22.05 kHz | 60.0 s (cut by `-t 60`) | 60.0000 | 60 |
| MKV with two audio streams (2 s and 50 s) | 2.0 s (ffmpeg picks one stream) | 2.0000 | 2 |
| WAV 0.3 s | 0.3 s | 0.3000 | 1 |
| WAV whose header lies: `data` size = 1 s, payload 20 s | 1.0 s | 1.0 | 1 |
| Same, `data` size 0xFFFFFFFF | 20.0 s | 20.0 | 20 |
| Same, header claims 4 kHz (payload "plays" 80 s) | 60.0 s (capped) | 60.0 | 60 |

In every case the measured length equals what Azure would receive, because ffmpeg's output - not the client's file - is both measured and sent.

## Answers to the review focus

1. **Every paid path.** `AzureSpeechPronunciationProvider._assess` (`speech_pronunciation.py:433`) is the only Azure pronunciation request in the tree; its only caller is `speech_api._call_provider` (`speech_api.py:723`), reached only from `POST /api/speech/pronunciation` (router mounted once, `app.py:670`). With the meter enforced, both scripted and unscripted go through `_assess_metered` (`:760`). `speaking_library.py:693` resolves the provider but never calls it on a cache miss (returns `reference_available: False`). Demo provider: `build_speech_pronunciation_provider` returns None outside `development`/`test` (`speech_pronunciation.py:701`); in development it reserves 60 s and settles 0 (`score_kind != measured`). A provider without `prepare_audio` reserves `MAX_ASSESSED_SECONDS`. Retries are idempotent (operation id = incarnation, meter, key, digest(audio SHA-256, language, line, mode)). No unmetered paid pronunciation path found. `/api/speech/transcribe` (Groq) remains an unmetered paid path by recorded decision (QTA-14) - see P3-7.
2. **Duration truth.** Holds (probe above). Reserve = `min(ceil(round(seconds, 3)), 60)` of `prepared.seconds`; Azure is called with `prepared.data` (`speech_pronunciation.py:399`), so there is no second decoder and no client-declared duration anywhere; the 60 s cap is applied once, by ffmpeg, and the same bytes are measured and sent. Settle uses `meter["seconds"] = wav_seconds(normalized)` of the same bytes (`:452`), clamped to the reservation by both `_assess_metered` and `Ticket.settle`. `wav_seconds` walks RIFF chunks by size (handles ffmpeg's `LIST` chunk and odd padding; `min(chunk_size, remaining)` cannot over-read). Rounding (ceil per take after ms rounding; up to one second per take lost to rounding; sub-ms under-charge possible) is documented in D-165 points 2 and 12.
3. **Ticket lifecycle in the thread pool.** The whole admit -> dispatch -> provider -> settle sequence runs inside `_assess_metered` in the worker thread. `starlette.run_in_threadpool` -> `anyio.to_thread.run_sync(abandon_on_cancel=False)` (anyio 4.15.1 in the image): cancelling the awaiting task does not stop the thread, the cancellation is delayed until the thread returns, so a disconnect cannot leave a dispatched ticket behind; the ticket is settled on the real outcome (the answer is simply dropped). Exceptions: `SpeechPronunciationError` -> explicit settle; any other exception after dispatch -> `admit()`'s `except BaseException` settles 0; before dispatch -> release; `Ticket.finished` prevents double settle (explicit settle, then the `with` exit is a no-op). Settle/release failures are swallowed and left to the reconciler (`pronunciation.audio` in `SYNC_METERS`; `RECONCILE_AFTER` 15 min far exceeds decode 20 s + Azure timeout). Contextvars (`USER_KEY_CTX`, quota `_REQUEST` facts, `_TICKET`) travel with the copied context; `_TICKET` is set and reset in the same thread context.
4. **Concurrency / idempotency.** Re-run on PostgreSQL (above). Same key + same audio concurrently -> one provider call, others `409 operation_in_progress`; same key after completion -> `409 operation_finished`, no call; same audio + new key -> new operation and a new real Azure call (intended). Digest collision: SHA-256 of a canonical JSON, operation id truncated to 160 bits - negligible. Note: since the digest is in the operation id, "same key, other payload" is a new operation, never `operation_conflict` (tested and documented).
5. **Off the event loop.** Production builds a fresh provider (and `requests.Session`) per request through the resolver (`app.py:664`), so no Session is shared across threads; ffmpeg runs in a per-call temp dir; the quota core uses its lock and a thread-safe SQLAlchemy engine; telemetry persistence is best-effort and context-based. See P3-3 (shared thread-pool limiter) and P3-4 (provider resolution still on the loop).
6. **Client.** No client enforcement; the 429 is told apart (`failureOf` kind `quota`), shown from the server's own `used`/`limit`/`scale` with the Plan & usage rounding (`displayAmount`). Key: new per take, rotated after an answer with a category except `operation_in_progress`/`operation_finished`, kept on no answer. **Defect: P2-1.**
7. **Telemetry.** One row per Azure request on every path: success rows with seconds and USD; a 200 that then fails (no speech, malformed) is a success row with billed seconds; non-200/timeout/transport failure a failure row with no amount; a local decode failure a failure row. The allowance never reads the ledger and vice versa. See P3-5.
8. **Tests.** Strong hermetic + PostgreSQL coverage of the server semantics, and the HTTP path really exercises `run_in_threadpool`. Gaps listed under P3-6; the JS gate masks P2-1.

## Findings

### P2-1 (required before merge) - A lost answer becomes a permanent "retry" loop that can never succeed

- Where: `static/orena/capabilities/speaking-take.js:45` (`failureOf` falls through to `{ kind: 'service', retry: true }` for `409 operation_finished`), `:148` (the key is deliberately kept for `operation_finished`), `:187` (`retry` resends the same take with the same key); gate `scripts/test_speaking_take.mjs` (new block, "the server already had the take: the same key").
- Failure scenario: the learner's network drops while Azure is assessing (common on mobile; the request takes seconds). The server finishes and settles (charged the take's seconds if Azure scored it; 0 if it failed). Client: `offline`, retry offered, key kept - correct so far. The learner taps retry: same key + same digest -> `409 operation_finished` -> `failureOf` says `service`, `retry: true`, key still kept -> every further retry returns the same 409 forever. The learner is told it is a service failure and offered a retry that cannot succeed, and (if charged) never sees the result they paid for. The same loop follows any answer without a category (proxy 5xx page, a generic 500 after dispatch). D-165 point 5 says "the retry is refused instead of charged", but nothing tells the learner that.
- The gate hides it: its script returns `409 operation_finished` and then, **for the same key**, `504` and then a measured result. The server can never answer anything but `409 operation_finished` for that key again (`quota._reserve` duplicate branch, `quota.py:610-616`), so the tested sequence is unreachable.
- Required fix: give `operation_finished` (and `operation_conflict`) its own non-retryable failure kind, rendered with an existing pattern of the design for "this take cannot be assessed again - record it again" (no invented UI; if the design has no such state, record it in `UI_BACKEND_GAPS.md` and use the nearest existing mic-sheet state), and make the gate model server truth (after `operation_finished` the same key never succeeds). Whether a lost-and-charged take may be re-sent under a new key (a second real Azure charge) or should be replayed from a short-lived server result store is a product/persistence decision for the human; do not decide it in code.

### Human decision required before activation on :8000 - `NO_SPEECH_CHARGED` (`speech_api.py:663`, default `True`)

Assessment of both options (the reviewer does not decide product direction):
- `True` (charge the seconds Azure processed for a "no speech" answer): provider spend stays bounded by the allowance. Learner risk: a muted or broken microphone burns allowance silently - on Free (300 s) five 60 s silent takes exhaust the month; `BabbleTimeout` (noise only) is charged too. Mitigations already present: `MIN_TAKE_MS`, mic readiness, the "not heard" sheet. It is arguably consistent with D-161 point 10 (a "no speech" answer is a usable provider outcome, not an unusable one), but that reading must be the human's.
- `False` (charge nothing): matches "the learner got nothing", but makes silent/noise clips free Azure spend bounded only by the per-process, per-account `speech_ai` brake (`core/http_security.py:76`, 60 requests / 600 s, shared with transcribe and evaluation): up to ~60 min of billed Azure audio per 10 min per account per process - a material cost-abuse vector for a scripted client.
- Either way, the client comment at `speaking-take.js:144-147` ("a refusal or a failure charged nothing") is false for `pronunciation_no_speech` under `True` (P3-1). Reviewer recommendation if the human wants a middle ground: keep `True` for beta and record the learner-risk in Plan copy decisions later; do not ship `False` without a per-account cap on zero-charged billed takes.

### P3 findings (non-blocking)

- **P3-1 Client comment / rotation accuracy** - `speaking-take.js:144-148`: rotation after `pronunciation_no_speech` is harmless today (no-speech is `retry: false`, so the same take is not resent), but the comment's premise is wrong under `NO_SPEECH_CHARGED=True`. Fix the comment.
- **P3-2 Decode before admission for refusals** - `speech_api.py:778-790`: `require_ready` only avoids decoding when enforcement is unavailable (503). An exhausted learner (429) or a duplicate (409) still costs an ffmpeg decode of up to 8 MiB / 20 s CPU each time. D-165 point 3 ("a request about to be refused does no ffmpeg work") overstates it - correct the text; optionally add a cheap "remaining <= 0 -> 429" read before decoding.
- **P3-3 Shared thread-pool limiter** - `speech_api.py:601`: the work now holds an anyio default-limiter token (40, shared with every sync route) for decode + Azure (requests' timeout is per socket operation, so it can exceed 30 s). A burst of ~40 assessments can starve all sync endpoints. Strictly better than blocking the event loop as before; consider a dedicated `CapacityLimiter` for pronunciation.
- **P3-4 Provider resolution still on the event loop** - `speech_api.py:567` -> `_pronunciation_provider()` -> resolver `build_speech_pronunciation_provider` reads/decrypts stored credentials and builds a new `requests.Session` per request inside the `async` handler (pre-existing; the PR's "no longer blocks the event loop" is true for decode/quota/provider only).
- **P3-5 Telemetry label for a local decode failure** - `speech_pronunciation.py:331-345`: a failed ffmpeg decode is recorded as `pronunciation_evaluator` / `azure-speech` outcome `failure`, cost reason `request_failed`, although no Azure request was made. Pre-existing semantics (and asserted by `test_a_local_decode_failure_is_still_a_ledger_row`), but it inflates provider failure rates; consider a distinct error class or provider label when the ledger fields are next revised (schema/allow-list is the human's).
- **P3-6 Missing tests** - (a) a real-ffmpeg test of `wav_seconds` on the normalizer's output including a client-injected metadata `LIST` chunk (skip when ffmpeg is absent) - the hermetic suite uses a fake decoder, so the "data chunk, not len-44" claim is proven only by the reviewer probe and the implementer's manual check; (b) a cancellation test: cancel the awaiting handler during the provider call and assert the ticket is settled on the provider's outcome after the thread returns; (c) the P2-1 client sequence.
- **P3-7 Unmetered paid Groq path** - `/api/speech/transcribe` is unmetered by recorded decision (QTA-14); it remains paid provider spend bounded only by the `speech_ai` brake. Keep QTA-14 open as a precondition before any claim that all paid AI is plan-bounded.
- **P3-8 Client metadata forwarded to Azure** - `normalize_audio_to_pcm16_wav` (`speech_pronunciation.py:142-182`) copies the input's tags into the output `LIST INFO` chunk (probe: 65 KB of client-chosen text sent to Azure). Not a metering issue (`wav_seconds` skips it correctly), but sending client-controlled bytes to a third party is unnecessary; add `-map_metadata -1` (and `-fflags +bitexact`) so the sent bytes are audio only.
- **P3-9 Display rounding near the limit** - `displayAmount` rounds to one decimal, so 299 of 300 s shows "5 of 5" minutes while a short take is still admitted. Shared with Plan & usage by design; note for the Plan copy owner.

## Required before merge

1. Fix P2-1 (client failure kind for `operation_finished` / `operation_conflict` + a gate that models server truth); record the replay-vs-recharge question for the human.

## Required before activation on :8000 (human gates, unchanged)

1. The human's explicit answer on `NO_SPEECH_CHARGED`.
2. The existing D-161 activation gates (points 6-8) and the human GO for :8000. Enabling on :8021 for the live E2E is fine after P2-1.

## Cleanup

Throwaway PostgreSQL container `quota-d-review-pg-15093` (127.0.0.1:55437): stopped (started with `--rm`, so removed).

---

## Re-review (2026-10-09)

- Reviewer: claude-opus-5-5, Delegated Architecture Reviewer (independent; did not write the fix).
- Reviewed commit: `fb61ce626f4fd8dc062811ca4671f305fff82ba8` (fix commit on top of `8ff561b8`), diff `8ff561b8..fb61ce62`. Worktree clean at that SHA.
- Human decisions relayed by the coordinator and taken as given: a lost answer -> "record again" under a new key (a new real charge), no stored-result replay; `NO_SPEECH_CHARGED` stays `True` for the beta.

### VERDICT: APPROVE

P2-1 is fixed. No P0/P1/P2 remains. The remaining items are P3 (below) and the existing activation gates.

### Verification of the claimed fixes

- **P2-1 - fixed.** `failureOf` maps `409 operation_finished` / `operation_conflict` to `{ kind: 'already_assessed', retry: false }` (`speaking-take.js:42`), so `retry()` can no longer resend that key; `operation_in_progress` still falls to `service` / retry with the same key. A new recording always takes a new key (`stop()`). The Speak, Compare and Shadowing rooms route `quota` and `already_assessed` through `showAssessmentRefusal` (a toast, no action; the missing design state is recorded as QTA-15), with EN/VI/ZH copy `recordAgain`. The gate now uses a model server that can only answer what the real core can (`operation_in_progress` while running, `operation_finished` for ever after, whatever the outcome), and proves: lost answer -> same key -> `already_assessed`, nothing resent, a new take gets a new key and a result; still running -> retryable with the same key, then `already_assessed`; an answered failure -> new key -> result. This matches the human's decision.
- **P3-1 - fixed.** The rotation comment is now correct (no speech is charged and never resent).
- **P3-2 - fixed as documentation.** D-165 point 3 now says that 429/409 still cost one local decode, bounded by `speech_ai` (QTA-16 f). This is acceptable.
- **P3-3 - fixed.** There is now a dedicated `anyio.CapacityLimiter` per running event loop (`speech_api._pronunciation_limiter`, `PRONUNCIATION_MAX_CONCURRENT`, default 8, a bad value falls back to 8, min 1). Reviewer probe in the app image (uvloop **is** installed, and uvicorn's default `--loop auto` will use it):
  - Under asyncio and uvloop, one limiter per loop, reused within a loop: 20 workers -> peak exactly 8.
  - The `WeakKeyDictionary` accepts uvloop loops (no `TypeError`) and drops entries when a loop dies (cache size 0 after the runs), so there is no leak and no cross-loop reuse.
  - `test_assessments_hold_at_most_the_configured_worker_threads` proves peak = 2 through the real route.
- **P3-8 - fixed, measurement unchanged.** `-map_metadata -1 -fflags +bitexact`. The reviewer's real-ffmpeg probe was re-run on all nine inputs. The output is now `fmt ` + `data` only, a 44-byte header (no `LIST`, no client text). `wav_seconds` and reserved units are identical to the first review: 7.4/8, 7.4/8, 3.0/3, 60/60, 2.0/2, 0.3/1, lying headers 1.0 / 20.0 / 60.0. The `data` sizes are byte-identical to before (236800, 96000, 1920000, 64000, 9600), so stripping metadata removed only header bytes. The new skip-if-no-ffmpeg test proves the same on the real decoder.
- **P3-4/5/7/9 and the human items** are recorded in `UI_BACKEND_GAPS.md` QTA-16 and D-165. Accepted.

### Evidence (local execution, not CI)

- JS gates `test_speaking_take`, `test_orena_screen_speak`, `test_orena_screen_plan`: PASS. ESM graph: OK (271 modules).
- With my throwaway PostgreSQL (`quota-d-review-pg-12227`, now stopped): quota, pronunciation, persistence and audio-cost suites **199 passed** (includes all PostgreSQL proofs and the 3 new tests). Concurrency, worker-limit and real-ffmpeg subset ×3: 7 passed each run.
- Full `pytest -q test_app.py tests`, CI configuration (no PostgreSQL URL): **4880 passed, 429 skipped** (+3 new tests over the first review's 4877).
- Non-CI run of the whole suite with `ORENA_TEST_POSTGRES_URL` pointed at one shared, already-used database: 27-31 failures in `test_writing_minimum`, `test_writing_review_reuse`, `test_saved_reviews`, `test_writing_evaluation`, `test_media_status_compact` and `test_reading_content_engine`. None of these modules is touched by the PR. Those six modules **pass in isolation at both base `5e02173e` and `fb61ce62` (248 passed each)** against the same database. So this is cross-module state in a shared-database configuration CI does not use, not a regression of #119.

### Correction to the first review (focus point 3)

The first review said a cancelled request "waits for the thread". A probe in the app image shows that this is **not** true for native asyncio `Task.cancel()` (asyncio and uvloop):
- the awaiting coroutine returns `CancelledError` while the worker thread is still running;
- the thread then runs to completion;
- the limiter token is released at cancellation, not when the thread ends.

The conclusion that matters still holds: admit, dispatch, provider call and settle all live inside the thread, so a cancelled request still settles its ticket on the provider's real outcome, never leaves it dispatched, and never double-settles.

New **P3-10**: a cancelled request's thread no longer counts against `PRONUNCIATION_MAX_CONCURRENT`, so cancellations can briefly push concurrency above the bound.
- This was the same under the previous default limiter, so it is not a regression.
- The app has no `BaseHTTPMiddleware`, and uvicorn does not cancel a handler on client disconnect, so it is reachable mainly at shutdown.
- No change required; worth a line in QTA-16.

### Remaining P3 (non-blocking)

- **P3-11 Stale "pending" markers.** `speech_api.py` still labels `NO_SPEECH_CHARGED` `[HUMAN, pending]`, and QTA-16 (a) still says the answer is required. The human has now decided `True` for the beta: record the decision (D-165 point 4 / QTA-16 a) and drop "pending" when the PR is finalised.
- P3-4, P3-5, P3-7 and P3-9 stay open as recorded in QTA-16.

### Gates (unchanged)

Activation on :8000 still needs the human GO and the D-161 points 6-8 gates. Enabling `pronunciation.audio` on :8021 for the live E2E is fine.

Cleanup: both throwaway PostgreSQL containers (`quota-d-review-pg-15093`, `quota-d-review-pg-12227`) stopped (`--rm`); the scratch extract of the base tree is removed.
