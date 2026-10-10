# Architecture review: voice charged by duration (PR #123)

| | |
|---|---|
| Reviewer | claude-opus-5-5, Delegated Architecture Reviewer (independent of the implementer) |
| Reviewed commits | First review `337823565c8b3686a9a1dfe8750a3349a23d5885` (base `b93b2388`); re-review `33782356..eb005a6adbf874e44480d58c04954f3f5359f482`; re-review 2 `eb005a6a..7d990ae4` and the merge with main `ef5f96e09f4f40dca536587998624c0f3f9169bb` |
| Final verdict | **APPROVE** at exact reviewed SHA `ef5f96e09f4f40dca536587998624c0f3f9169bb`. Earlier: REQUEST CHANGES at 33782356 (P1-1 early end undercharges), APPROVE for merge at eb005a6a with P2-R1/P2-R2 required before merge — superseded. |
| After the reviewed SHA | This record and `scripts/agent_live/check_token_expiry.py` (the live check D-169 names, P3-R4); no product code. Not product approval; NOT activation: voice with enforcement stays testers-only until the live expiry and sessionResumption checks pass (D-169 point 5). |

# Architecture review - Voice charged by duration (D-169, AGENT_CONTRACT v8)

- Reviewer: claude-opus-5-5, acting as **Delegated Architecture Reviewer** (AGENTS.md "Architecture review authority"). I did not write this change.
- Reviewed: branch `feat/quota-voice`, commit `337823565c8b3686a9a1dfe8750a3349a23d5885`, diff `b93b2388..33782356` (21 files, +906/-104).
- Date: 2026-10-10. Read-only review; nothing edited, committed or pushed. No shared runtime touched.

## VERDICT: REQUEST CHANGES

One P1 is open: the server cannot see the vendor socket, so ending a session early lets a learner keep Live time they were not charged for. REVIEW_POLICY says an unresolved P1 means REQUEST CHANGES. The rest of the slice is sound: admission under the bucket lock, the 429/503 fail-closed paths, idempotency, settlement without double counting, contract v8 and the tests. The verdict becomes APPROVE when **either** path below is done:

- **(A) Fix it.** Mint tokens per chunk (see P1-1).
- **(B) The human accepts the risk.** The human records in DECISION_LOG that the early-end undercharge is accepted for QA-only activation, and records a gate: `AGENT_VOICE_ENABLED` together with `orena.message` enforcement stays off for real learners and production until (A) lands. The P2-1 fix and the wording corrections in P2-3 are still required.

## Evidence (local execution, not CI)

- **Targeted suites against a throwaway PostgreSQL 17** (`postgres:17-alpine`, own container, now stopped). Files: `test_quota_voice.py`, `test_quota_voice_postgres.py`, `test_quota_orena_message{,_postgres}.py`, `test_quota_gate{,_postgres}.py`, `test_agent_voice_session.py`, `test_agent_contract_tables.py` and `test_product_foundation.py`. Result: **190 passed, 0 skipped**, so the PG proofs ran, including the six-concurrent-opens proof and the same-key-concurrent proof.
- **Full suite in CI mode** (`PERSISTENCE_BACKEND=sqlite`, no PG URL, `pip install pytest jsonschema`): `pytest -q test_app.py tests` gave **4902 passed, 437 skipped, 0 failed**. No failure is voice-related. The implementer's 74/78 count came from running with the PG URL set and from the missing `jsonschema`, not from this change.
- **Node gates on the host:** `test_orena_live_voice.mjs`, `test_orena_agent.mjs`, `test_orena_surfaces.mjs`, `test_orena_free_voice.mjs` and `test_orena_screen_orena.mjs` all exit 0. `validate_project_memory.py` exits 0.
- **Reviewer probes** (`scratchpad/qv/probe/test_review_probe.py`, not in the branch):
  1. Open, wait 1 s, end, repeat. That gave 12 sessions whose tokens totalled **9,900 s of Live time for 12 messages** (token lives 900 x6, then 840 down to 540). It stopped only at the agent's own turn window (`429 rate_limited`), not at the quota.
  2. Open then end with no time passing: **0 messages charged**.
  3. With 15 messages left, an open 900 s session holds the whole day, and a text message during it is refused `429`.

## Findings

### P1-1 - An early `/voice/end` undercharges against the token's life; no server-side control exists
- **Where:** `writing_coach/agent/voice_session.py:801-805` (`_bill` settles `ceil(elapsed/spm)` and releases the rest), `:450` (token minted with `expireTime = cap`) and `:376` (`get()` refuses only the server's own routes).
- **Scenario:**
  - The browser holds the ephemeral token. Any learner can call `POST /api/agent/voice/end` from devtools one second after opening, while their socket to Gemini stays open.
  - The server charges 1 message, releases 14, and has no way to stop the socket. Ephemeral tokens cannot be revoked, and the server is never on the socket.
  - `/voice/tool` and `/voice/turn` are refused after the end, so Orena's actions stop. The paid speech-to-speech conversation goes on until the vendor ends it: at `expireTime` if Gemini enforces it on an open socket (not verified), otherwise at the vendor's own connection or session limit (~10-15 min).
  - Repeating this over a Free day of 20 messages gives up to Σ min(900, 60k) for k = 20..1 = **11,700 s (195 min) of Live time for 20 messages**, about 10x the allowance (probe 1). Ending each session after 0.04 s costs nothing at all (see P2-1).
- **Why it matters:**
  - The human asked for no client enforcement. Here the charge rests entirely on the client's own report of when the session ended.
  - Decision-log entry D-169 point 4(b) covers a client that *ignores* the cap. It does not cover a client that *ends early and keeps talking*.
  - The ledger row (`record_audio`) and the daily AI spend brake use the same early `seconds`, so they are undercounted as well.
  - Severity: P1, not P0, because voice is off on :8000. It must be closed, or explicitly accepted by the human, before voice and enforcement are on for anyone but testers.
- **Required fix** (contract v9, client and server):
  - Mint **per-chunk tokens**: token life = k x `voice_seconds_per_message` (k = 1-3, the human picks).
  - Reserve and settle each chunk **whole at mint**.
  - The client renews before expiry through a new `POST /api/agent/voice/extend`, which re-admits and returns a new token. It carries on the same conversation with Gemini Live `sessionResumption` (the vendor doc already requires a reconnect about every 10 minutes within `expire_time`).
  - An early end then forfeits at most the current chunk, which is what `ceil` already charges, so "settle the actual elapsed time" holds and the server enforces it.
  - This also fixes P2-2 (the session holds only one chunk, not 15 messages).
  - **Precondition:** verify live that Gemini closes an already-open socket at `expireTime`. That is a paid-provider call, so it needs the human's go-ahead. If Gemini does not close it, no token-based scheme bounds usage, and only a server-proxied socket can.

### P2-1 - A session ended at once is charged 0, contradicting the contract and the decision log
- **Where:** `writing_coach/product/quota.py:475` (`seconds <= 0` returns 0) combined with `voice_session.py:801` (`round(..., 1)`, so an elapsed time under 0.05 s becomes 0.0). AGENT_CONTRACT.md:505 says "a session that ended at once is still one started unit", and DECISION_LOG D-169 4(a) says "charged one message".
- **Scenario:** a token was minted and handed to the learner, the work was dispatched, and the settlement is 0 (probe 2). The human's rule says model execution that has started counts.
- **Required fix:** once a token is minted, settle at least 1, for example `max(1, ticket.units_for(seconds))` when `ticket.dispatched`. Add a test that ends with zero elapsed.

### P2-2 - An open session holds the learner's whole day; typed messages are refused while it lasts
- **Where:** `quota.py:648`. Recorded in D-169 4(e) and confirmed by probe 3.
- **Scenario:** Free with 15 or fewer messages left: a voice session reserves all of them, and every typed message gets `429 quota_exhausted` until the session ends. The learner sees an "exhausted" figure (`used` includes `reserved`) for messages they have not spent.
- **Status:** a UX/product decision for the human; it should not be silently accepted. The chunked tokens in P1-1 remove it.

### P2-3 - Corrections to the record and the contract text (required with either path)
- DECISION_LOG D-169 4(b) reads as if the cap bounds a dishonest client. It must also state the early-end exposure, or the human's acceptance of it.
- 4(a) and the contract's §9.6 sentence must match the code once P2-1 is fixed.

### P2-4 - `/api/speech/transcribe` is paid work with no quota
- **Where:** `writing_coach/speech_api.py:352`; brake at `core/http_security.py:76`.
- **Why the slice's argument holds:**
  - Push-to-talk feeds a turn that is already charged, so charging the transcription too would count one message twice.
  - Charging the drafts in the rooms against `pronunciation.audio` would misuse that meter.
- **What remains:**
  - The route is still paid provider work without any per-account allowance, which conflicts with the human's "no paid work without quota" principle.
  - The bound is 60 requests per 10 minutes per account per process (shared with pronunciation), with up to 24 MiB per take (roughly 100 min of opus). A script can push hundreds of audio-hours a day through one account.
  - With enforcement on and voice off, an exhausted learner's push-to-talk still pays for the transcription and is then refused at the turn.
- **Rating:** P2, not introduced by this slice; the human decides.
- **Proposed minimal guard:**
  1. **Per-take duration cap:** reject a take over N s (for example 120 s for push-to-talk, 300 s for free talk) before calling Groq. Read the duration with ffprobe, or as a cheap proxy lower `GROQ_ASR_MAX_BYTES` to about 2-4 MiB.
  2. **Per-account daily seconds brake:** sum `speech_asr` ledger `audio_seconds` per account per day and refuse `429` past a ceiling (for example 60 min/day).
  3. **Orena push-to-talk only:** a read-only check that `orena.message` has at least 1 left (a peek, no reservation) before transcribing, so an exhausted learner does not pay for a transcription that is then refused.

### P3-1 - Six lost races give 503, not 429
- **Where:** `quota.py:665-670`.
- **Detail:** under heavy concurrent text and voice on one account, six straight `exhausted` races end in `_unavailable("window")` (503) instead of the exhausted 429. It fails closed and is rare. Add a test, or fall through to 429 on the last attempt.

### P3-2 - Any 409 triggers a learning-language refresh
- **Where:** `static/orena/screens/orena/voice.js:186`.
- **Detail:** every 409 still calls `refreshLearningLanguage()`, including the new `operation_*` 409s, which §2.1 says are never a language change. The shipped client mints a fresh key per open, so this is unreachable today. Test `error.category`.

### P3-3 - The unlimited plan branch is untested
- **Where:** `quota.py:648`, where `entitlement.limit is None`. There is also no test that a stored catalogue missing `voice_seconds_per_message` fails closed (it does: 503).
- **Before QA:** check that the catalogue stored on :8021 has the parameter.

### P3-4 - Mint latency is charged; registry is per process
- `opened` is taken before the mint (`voice_session.py:447`), so the vendor's mint latency is charged. This can tip a session that ends exactly on a unit boundary into the next unit. Acceptable, but say so in the contract.
- The session registry is per process. With more than one worker, `/voice/end` can land on another worker (404), and the reservation is then charged in full by the sweep or the reconciler. That overcharges and never undercharges, and it is recorded (R26). Keep one worker until this is shared.

## Reviewed and found correct

- **Admission:** reserves `min(ceil(900/spm), remaining)` under the bucket lock and re-counts after a lost race. On PG, six concurrent opens on a 20-message day give exactly 15+5 reserved and 2 tokens. Text turns go through the same locked `reserve`, so there is no overspend across text and voice.
- **Idempotency:** the pre-read of `operation_id` (key + digest) answers 409 `in_progress`/`finished`. A same-key twin of a different size goes `payload_conflict`, then re-read, then 409. There is never a second reservation, and the PG same-key-concurrent test passes. This is consistent with the core, where `operation_id` includes the digest.
- **Lifecycle:** `close()` and `expired()` remove a session under the lock, so each session is billed once. The repository's `settle` is row-locked and terminal, so the 15-min reconciler (which runs on `updated_at` from the dispatch) and a late `/voice/end` cannot double count; the loser is a no-op. A session at its cap is charged its full reservation either way. A process restart leaves the reservation to the reconciler at full units (overcharge, recorded).
- **Mint failure:** dispatch then mint failure gives `settle(0)`. A dispatch denied (403) releases the reservation.
- **Fail closed:** an unreadable switch, store or catalogue, or an invalid conversion, gives 503 and no token (tested). Switch off, or `orena.message` not listed, gives `NULL_TICKET`: 900 s, unchanged behaviour (tested). The setup token's `newSessionExpireTime = min(60, cap)` is correct.
- **Contract v8:** consistent across `AGENT_CONTRACT.md`, `contract.py`, `contract.js`, `surfaces.json`, the surfaces pin, `test_orena_agent.mjs` and `test_agent_contract_tables.py`.
  - A v7 browser client still works: its 30 s floor can outlive a sub-30 s token, and the server caps the charge.
  - The Intelligence lane's `scripts/agent_live/voice_client.py` sends `contract_version: 5` and no key. It is unaffected apart from consuming the test account's messages when enforcement is on, and it records a 429 as a scenario error.
- **Browser:** a 429 shows the toast and does not start the cascade. Other failures fall back to the cascade as before.

---

# Re-review - chunked tokens, renewal route, transcribe guard

- Reviewer: claude-opus-5-5, Delegated Architecture Reviewer. I did not write this change.
- Reviewed: `eb005a6adbf874e44480d58c04954f3f5359f482` (parent `33782356`), diff `33782356..eb005a6a` (17 files, +1500/-407), PR #123.
- Date: 2026-10-10. Read-only review; nothing edited, committed or pushed. No shared runtime touched; my own PostgreSQL container is stopped.

## VERDICT: APPROVE for merge, with conditions on turning voice on (they do not block the merge)

P1-1 is fixed in code:
- A chunk's token never lives longer than the messages it charges pay for (`quota.py` `_reserve`: `ticket.max_seconds = min(chunk_seconds, units x spm)`).
- Each chunk is charged in full when its token is minted (`voice_session.py` `_mint_chunk`), and `/voice/end` gives nothing back.
- A session can never mint more than 900 s of tokens in total, and every renewal is a fresh quota check.

The design also removes P2-1 (an instant end cost 0) and P2-2 (one session held the whole day). No P0 or P1 is left in the code, provided Gemini behaves the way the design assumes. The two vendor behaviours nobody has checked yet are recorded as conditions for turning voice on (D-169 points 5 and 11); the additions this review asks for are below.

## Evidence (local runs, not CI)

**My original probes, re-run unchanged.** They now fail exactly where they asserted the old behaviour, which shows the fix:
1. Open, wait 1 s, end, repeat: 10 sessions, each token lives 120 s, and the learner is charged **20 of 20**. That is 1,200 s of token for 20 messages (before: 9,900 s for 12). The loop stopped on `429 quota_exhausted`.
2. Open and end with no time passing: charged **2** (before: 0).
3. A session no longer holds the day: the first chunk is 120 s and is charged when minted, so nothing stays reserved.

**PostgreSQL proofs** on a throwaway PostgreSQL 17 (`-m 1g`, stopped afterwards): **223 passed, 0 skipped**. Files run: `test_quota_voice{,_postgres}`, `test_quota_orena_message{,_postgres}`, `test_quota_gate{,_postgres}`, `test_agent_voice_session`, `test_agent_contract_tables`, `test_speech_transcribe_guard`, `test_product_foundation`. They include:
- two renewals of the same chunk at once are charged once;
- six concurrent sessions on 3 messages hold exactly 3;
- the same key sent concurrently is one session.

**Full suite in CI mode, run once** (sqlite, no PostgreSQL URL; ffmpeg is in the image, so the transcribe-guard tests ran): **4932 passed, 440 skipped, 0 failed**. This run includes the late `api.py` change to the renewal route.

**Node gates:** `test_orena_live_voice`, `test_orena_agent`, `test_orena_surfaces`, `test_orena_free_voice`, `test_orena_screen_orena`, `validate_browser_esm_graph` (with its flag) and `validate_project_memory` all exit 0.

**New probe** `probe2/test_take_formats_probe.py` feeds 10 s recordings through the guard's `take_seconds` (ffmpeg reading from a pipe):
- webm/opus, ogg/opus, faststart MP4 and fragmented MP4 all measure 10.0 s;
- **an MP4 with its index (`moov`) at the end cannot be read: `TakeUnreadable`, so the route answers 422.**

## Is it safe under each outcome of the two vendor checks?

**Check 1: does Gemini close an already-open socket when the token reaches `expireTime`?**

- **Yes:** usage is bounded. A learner's Live time is at most the token life they were charged for (units x spm), plus at most one chunk of overlap, which they also pay for. The design works as intended.
- **No:** usage is **not** bounded by the allowance.
  - A client that never renews keeps a 120 s, 2-message token's socket open until Gemini ends it itself: about 10 minutes per connection (with a GoAway warning), 15 minutes per audio session. That is about 5x per open.
  - Opening again costs another 2 each time, so a Free day comes to roughly 100 min of voice for 20 messages.
  - D-169 point 5 says the code is "safe either way". That overstates it. The point's own last sentence (only a server-proxied socket could bound usage) is the real consequence.
  - Enforced voice must then stay off for real learners until the human chooses a server-proxied socket, or a per-open charge equal to Gemini's connection life.

**Check 2: does Gemini accept `sessionResumption` inside the token's locked setup?**

- **Accepted at mint and at connect:** safe. The conversation carries across chunks.
- **Refused at mint:** safe. The mint fails, nothing is charged, the route answers 503 and the client falls back to its cascade. Voice is simply unavailable.
- **Refused at connect** (the mint succeeds, then the socket's setup fails): **the learner is overcharged.**
  - Chunk 0 is charged 2 messages and its socket closes during setup.
  - On a renewal, the new socket fails and the token already held plays out.
  - Net effect: every voice open costs 2 messages for nothing.
  - `resumption={}` is now in **every** first-chunk setup (`voice_session.py` `open`), **including when enforcement is off**. So "switch off = unchanged" is true for the quota but not for what is sent to Gemini.
- **Handle ignored:** safe. The new socket starts with the same instruction but a fresh context, a UX loss only.

## Conditions before turning voice on

These apply before voice with enforcement reaches anyone. Condition 2 also applies before this code is deployed to any runtime where `AGENT_VOICE_ENABLED` is on, even with enforcement off.

1. **Run the bounded `expireTime` check** (D-169 point 5) under the Gemini Live lock and record the result in DECISION_LOG. If the socket is not closed within about 30 s of `expires_at`: no enforced voice for real learners (testers only), and the human chooses between a proxied socket and a per-open charge.
2. **Extend that live check to the connect step, not just the mint:** connect with `sessionResumption: {}` in the locked setup, and do one renewal that carries a handle. If connect rejects it, remove `resumption` from the setup (or put it behind a flag that is set only once verified) before any voice-enabled deploy. Otherwise unmetered voice breaks, and metered voice charges for tokens that cannot connect.
3. **The :8021 catalogue has `voice_seconds_per_message`.** This is already in D-169 point 11.

## Findings (re-review)

**P2-R1: recordings from iPhone/Safari may fail the new 300 s guard.**
- `take_seconds` in `writing_coach/speech_api.py` decodes from `pipe:0`. An MP4 with its index at the end cannot be read from a pipe (probe above), so every transcription from such a device would get `422 speech_asr_unprocessable_audio`.
- That would break push-to-talk and all five speaking rooms (`conversation`, `free-talk`, `react`, `reading-transfer`, `situation`).
- Safari's MediaRecorder is believed to record fragmented MP4, which passes, but nobody has verified it.
- Required before QA on iOS: decode from a temp file, which can be seeked (the pronunciation normalizer already does this in `speech_pronunciation.py`), or verify a real iPhone Safari take. The temp-file change is small and removes the risk entirely.

**P2-R2: the AI cost ledger now records each token's full life at mint; on :8021's 1 USD/day spend cap this matters.**
- `_record_chunk` writes `audio_seconds = token life`.
- With enforcement off, one open records 900 s, about 0.54 USD at 2.16 USD/h. Two opens use up :8021's whole daily cap, and every agent turn is then refused until UTC midnight.
- With enforcement on, each 120 s chunk records about 0.072 USD, so the whole sandbox gets roughly 14 chunks a day.
- This is conservative and deliberate (D-169 point 6), but it changes the unmetered path and will surprise QA. The human chooses one:
  - accept it;
  - raise :8021's cap for voice QA;
  - record the wall-clock time at `/voice/end` for the unmetered path only.

**P3-R1: the learner pays for the renewal overlap.**
- The client renews 12 s before the token expires (`RENEW_LEAD_SECONDS`), so about 12 s of every chunk except the last is paid twice.
- Over a 900 s session that is about 7 x 12 s: roughly 816 s usable for 15 messages, about 10% less than one minute per message.
- Acceptable. Say it in §3.3: a message buys a minute of token, not a minute of talk.

**P3-R2: fix the wording of D-169 point 5.**
- Replace "The code is safe either way" with the real exposure if Gemini does not close the socket: about 5x per open, bounded only by Gemini itself.
- Add the case where `sessionResumption` is rejected at connect time (condition 2 above).

**P3-R3: the transcribe guard's limits are per process, and the purpose label comes from the client.**
- The daily-seconds brake lives in memory: a restart resets it, and N workers each keep their own.
- The client sets `purpose=orena_voice` itself. Leaving it out only skips the advance check; the turn is still charged and the brake still applies.
- Both are recorded. They are adequate as a bound on abuse, not as a plan limit.

**Earlier P3s: all fixed.**
- Six lost races now give 429, not 503.
- The voice screen refreshes the learning language only on the `target_language_mismatch` 409.
- The unlimited-plan branch is tested.
- A missing catalogue parameter is tested to fail closed.
- `quota.refuse_unmetered` stays as a generic helper (tested) for the media-import slice.

## Reviewed and found correct

**Renewal route (`extend`):**
- It needs the learner's own live session (`get` refuses after `valid_until`) and runs one request at a time per session (`session.lock`).
- Repeating the last chunk index returns the same token without a charge.
- A chunk index out of order gives 409 `voice_chunk_mismatch`; reaching 900 s gives 409 `voice_session_over`.
- A refused or failed attempt bumps `attempts`, so the next try is a new quota operation.
- The resumption handle is validated (`RESUMPTION_HANDLE_PATTERN`) and locked into the token's setup, never the client's own setup.
- It is limited by the spend guard and the read limiter. Every renewal is charged, so spamming it only costs the learner.

**End racing a renewal:** `close()` removes the session and marks it ended under the registry lock, and `extend` re-checks `ended` under the session lock. No chunk is minted after an end that won the race.

**Reconciler:** nothing stays reserved after a successful mint. If the settle itself fails, the reservation stays dispatched and is settled at its admitted units after 15 min: charged, never lost.

**Fail closed:**
- An unreadable switch, store, catalogue or conversion gives 503 on open and on renewal; no token is minted and nothing is charged.
- With the switch off or the meter not listed, the session gets one 900 s token with `renew_in: null`, and a renewal answers `voice_session_over`.

**Client:**
- A renewal opens the next socket beside the old one and moves the microphone and tool answers only after `setupComplete`; the old socket closes when the new one takes over.
- If the new socket fails, the token already held plays out.
- A GoAway from Gemini triggers a renewal.
- `end()` clears the renewal timer and closes both sockets.
- A 404 ends the session; 5xx is retried twice; a quota 429 on renewal is told to the learner once (`onLimit`).

**Contract and other clients:**
- The contract v8 text, `contract.py`, `contract.js`, `surfaces.json` and the table tests agree.
- The Intelligence lane's `voice_client.py` (contract v5, a single token, no renewal) keeps working for scenarios under 120 s when enforcement is on. With enforcement off it still gets the 900 s token.

---

# Re-review 2 - fixes after APPROVE, and the merge of main (#124 media.import)

- Reviewer: claude-opus-5-5, Delegated Architecture Reviewer. I did not write this change.
- Reviewed:
  - `7d990ae44b53adb52f1a4e1fc98cd99d02424ac3` (the follow-up fixes; diff `eb005a6a..7d990ae4`, 10 files);
  - the merge `ef5f96e09f4f40dca536587998624c0f3f9169bb` (parents `7d990ae4` and `37261a6b` = main with #124; merge base `b93b2388`). The worktree HEAD is `ef5f96e0` and the tree is clean.
- Date: 2026-10-10. Read-only review; no shared runtime touched; my own PostgreSQL container is stopped.

## VERDICT: APPROVE at `ef5f96e09f4f40dca536587998624c0f3f9169bb`

The activation conditions from Re-review 1 still stand, and D-169 point 5 now records them correctly: voice together with `orena.message` enforcement stays testers-only until the live checks pass. They do not block the merge.

## The follow-up fixes (`eb005a6a..7d990ae4`)

**P2-R1 is fixed.** `take_seconds` (`writing_coach/speech_api.py`) now writes the take to a temporary directory that is deleted right after, then decodes it with `-protocol_whitelist file`. The route has already capped the upload at 12 MiB. A new test covers an MP4 with its index at the end. My probe now measures that format at 10.01 s; before the fix it was unreadable. webm, ogg, faststart MP4 and fragmented MP4 still measure 10.0 s.

**P2-R2 is fixed: with enforcement off, the code behaves exactly as before.**
- `_mint_chunk` adds `sessionResumption` only when `ticket.enforced` is true and `VoiceService.resumption` is on. The setup sent to Gemini for an unmetered session is therefore the original one.
- An unmetered session is no longer recorded at mint. `_bill` records the wall-clock time, at most 900 s, at `/voice/end` or when the sweep finds it expired. That is the formula from before this slice.
- A metered session still has every chunk recorded when it is minted.
- `AGENT_VOICE_RESUMPTION=false` (`api.voice_resumption`, read in `app.py` `_with_voice`) removes resumption from the metered path as well. This is the switch to use if Gemini accepts the token but refuses the socket at connect.
- No double billing: `close()` and `expired()` each take a session out of the registry under its lock, so a session is billed once.

**P3-R1 and P3-R2 are fixed.** D-169 point 5 now says "NOT safe either way" and names the connect-time `sessionResumption` failure and the switch. Point 7(c) records the cost of the renewal overlap.

## The merge (`ef5f96e0`): did `quota.py` keep both sides?

I compared each side's changes from the merge base with what the merge actually applied (the `+/-` lines). For `quota.py`, `app.py`, `api.js`, `test_quota_gate.py` and `UI_BACKEND_GAPS.md`, the only differences are the `D-169` to `D-169` renames. Both sides are carried over unchanged, and nothing was dropped or duplicated.

In the merged `quota.py`:

- **Meter lists:** `WIRED_METERS` includes `media.import`. `SYNC_METERS` is `("writing.review", "orena.message", "pronunciation.audio")`. `ASYNC_METERS` is `("media.import",)`. Voice uses `orena.message`, which is a sync meter and **not** in `ASYNC_METERS`.
- **`reconcile_once`:** it sweeps each group with its own threshold, and the async decision hook only runs for the `ASYNC_METERS` group. Voice chunks are settled when they are minted, so normally there is nothing to sweep. A chunk whose settle failed is still settled at its admitted units after 15 minutes by the sync sweep. That is the correct charge. The async media hook never sees a voice row.
- **Voice functions** (`_context`, `check_available`, `_reserve(voice=...)` with the lost-race 429, `begin_voice`) sit alongside media's `configure_async_decision`, `dispatch_operation`, `settle_operation` and `release_operation` without conflict.
- **`refuse_unmetered`** is defined once. The file parses.
- **D-number:** `D-169` follows `D-168` in DECISION_LOG. `D-169` no longer appears in the code, the contract or the log.

## Evidence (local runs, not CI)

- **Combined PostgreSQL proofs** on a throwaway PostgreSQL 17 (`-m 1g`, stopped afterwards), in one test container (`-m 2g`): **317 passed, 0 skipped.** The files cover voice, media import, the quota gate, Orena messages, voice sessions, the contract tables, the transcribe guard, product foundation and HTTP security: `test_quota_voice{,_postgres}`, `test_quota_media_import`, `test_quota_media_import_lifecycle`, `test_quota_media_import_postgres`, `test_media_import_telemetry`, `test_quota_gate{,_postgres}`, `test_quota_orena_message{,_postgres}`, `test_agent_voice_session`, `test_agent_contract_tables`, `test_speech_transcribe_guard`, `test_product_foundation`, `test_http_security`.
- **My probes, re-run unchanged:**
  - open, wait 1 s, end, repeat: 10 × 120 s tokens for 20 of 20 messages;
  - an instant end costs 2;
  - all five recording formats decode.
- **Node gates on the host:** `test_orena_live_voice`, `test_orena_agent`, `test_orena_surfaces`, `test_media_import_quota`, `test_orena_screen_plan`, `test_orena_screen_orena` and `validate_browser_esm_graph` (with its flag) all exit 0. `validate_project_memory` also exits 0.
- **Full suite:** not run here, as the coordinator asked (memory is tight). CI must show it green on the PR.

## Findings (Re-review 2)

**P3-R4: the live-check script is not in the repository.** D-169 point 5 names `check_token_expiry.py`, the bounded check (one session, one renewal carrying a handle) that decides whether voice can be turned on. `git grep` finds the name only in DECISION_LOG, and the file is not under `scripts/agent_live/`. Commit it next to `voice_check.py` (it uses the existing `lock.py`), or say where it lives, so the human can run the precondition from the repository. This is non-blocking because the check is a human gate, not a CI step.

No other findings. Conditions 1–3 from Re-review 1 are unchanged. Condition 2 now has its escape route in code (`AGENT_VOICE_RESUMPTION=false`), and condition 2's deploy note no longer applies to unmetered runtimes, because their setup is the original one.
