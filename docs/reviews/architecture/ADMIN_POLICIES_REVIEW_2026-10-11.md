# Architecture review: b962e957 (D-172, operational policies in Admin)

- Reviewer role: Delegated Architecture Reviewer (AGENTS.md "Architecture review authority"); independent of the implementer
- Reviewer model: Claude Opus 5.5
- Reviewed SHA: b962e957 on `feat/admin-policies` (base `main` a514dba9), read-only diff and file reads; no Docker, no tests run by the reviewer
- Outcome: **APPROVE WITH CONDITIONS**. Fix P1-1 and P1-2 before merge. Each fix is a few lines. The P2s may land in a follow-up but must be recorded (UI_BACKEND_GAPS "ADM-POL").

Summary: the registry, precedence (env > admin > default), strict typing and ranges, unknown-key rejection, `require_admin` on both new routes, origin protection (the global middleware covers PUT) and audit-in-transaction are sound. Every default equals the constant or environment default it replaces, and a test pins each one. An empty document behaves as before. None of the edited existing tests is weakened: `test_agent_retention` and `test_feedback` now assert the new wiring and still check that nothing is deleted when the switch is off, `test_quota_pronunciation` makes the same assertion through the policy, and the matrix count goes up by exactly the 2 new routes. The quota switch keeps its D-161 fail-closed read. Two defects break guarantees the change itself claims. Several class-A choices touch human-decided charging, activation or legal facts without the confirmation the change applies elsewhere.

---

## P1 (conditions for merge)

### P1-1 An Admin-set agent spend cap fails open: "no cap" on a cold worker or an invalid stored value
- `writing_coach/policies.py:261-286` (`_loaded`: never read before → `_Loaded(state="unreadable")`, values empty), `:289-301` (`value()` swallows everything and returns the default), `:128` (`agent.daily_spend_cap_usd` default `None` = no cap). `:242-258` (`_parse` drops an invalid stored value, so it falls back to the default `None`).
- `writing_coach/agent/budget.py:81-104` (`LiveSpendGuard`): the `except` branch meant to fail closed (`:96`) is dead code, because `policies.value` never raises. `cap is None` → `return None` → the turn is allowed.
- Failure scenario: an operator sets the cap in Admin (not in env), which is the purpose of this change. A worker restarts or deploys during a DB or connection-pool blip. Its first `platform.policies` read fails, so the cap is `None` and every agent turn and voice extend runs uncapped for as long as reads fail. The 5-second failure cache repeats this each window. With the quota switch off, nothing else stops spend. The same happens if a later build tightens the range so the stored cap no longer validates. This contradicts the `DailySpendGuard` contract ("It fails closed") and D-172 point 6 ("a blip must not lift an Admin-set spend cap back to none"). Point 6 holds only for a worker that has already read once.
- Minimal fix: add `policies.value_strict(key)`, which raises `PolicyUnavailable` when the key is not env-pinned and `_loaded().state == "unreadable"`, or when a stored value for that key was present but rejected. Call it from the `LiveSpendGuard` cap lambda in `app.py:917-926`, so the existing `except` returns 3600 (fail closed). Add a test: a store that fails on first read plus a stored cap must refuse the turn.

### P1-2 Compare-and-set is optional on a merging write: a lost update can silently revert a deletion switch or spend cap, unconfirmed and unaudited
- `writing_coach/product/api.py:218` passes `expected_updated_at=change.get("expected_updated_at", ...)`. `...` means "no check" (`platform_repository.py:50-53`).
- `writing_coach/policies.py:391-418`: `save()` reads `base` outside the write transaction, merges `{**base_values, **clean}` and writes the whole document. With `...` the write is unconditional.
- Failure scenario: admin B turns `feedback.retention_sweep` OFF (confirmed, audited). Admin A's client (a script, a retry, or any caller that omits the field; the API documents it as optional) read the base before B's commit and saves an unrelated key. A's document carries `retention_sweep: true` again, so deletion resumes. No confirmation was asked, because only A's keys are diffed, and A's audit row does not mention the sweep. The same path reverts a lowered spend cap. The plan catalogue (D-153) can tolerate optional CAS because it writes the whole document the caller sent. This route merges server-side, so it cannot.
- Minimal fix: in `save()`, when `expected_updated_at is ...`, use the version just read, `base["updated_at"] if base else None`. The read-modify-write then becomes a real compare-and-set (409 on a race). Alternatively, make the field required on the route (422 when absent). Add a test for the interleaving.

---

## P2 (record and fix in a follow-up; none blocks merge on its own)

### P2-1 `voice.enabled` is a human-gated paid activation, but it is classified A (Admin-editable) with no confirmation
- `writing_coach/policies.py:96`, `app.py:991-1000`, `agent/api.py:182-186`. D-169 point 11: enabling voice is "a paid Gemini Live call: the human's gate". ADM-POL's own class C keeps "the activation gates tied to ... human approval" in the environment, so the change contradicts its own audit. :8000 is safe only because `staging_8000_deploy.ps1` pins `AGENT_VOICE_ENABLED=false`. On any runtime where it is unset, one click turns on paid live voice.
- Fix: either move it back to C (env-only), or keep it in A with `danger="activation"` (confirmation and audit) plus a human acknowledgement in D-172 that Admin is now the gate.

### P2-2 Charging rules decided by the human can be switched with no confirmation
- `policies.py:86` `quota.abandoned_settles` (`zero` = a dispatched, abandoned reservation is free; "[HUMAN, pending]", human default 2026-10-09). `:106` `speech.no_speech_charged` (D-165, "[HUMAN, decided ... True for the beta]"). `:99` `voice.chunk_units` (the up-front, non-refundable charge per chunk; 10 means 10 messages charged even if the learner ends after 5 s).
- Scenario: one save, unconfirmed, makes silent pronunciation takes free (a learner can loop silent takes at provider cost, limited only by route rate and concurrency), or makes abandoned dispatched work free. Each is an entitlement decision under D-161..D-165/D-169.
- Fix: mark them `danger="charging"`, which `_needs_confirmation` already honours for any non-empty `danger`. Also label the confirmation dialog for this kind, not only for "deletes".

### P2-3 The voice session cap and chunk size drift from the published Agent Contract v8
- `AGENT_CONTRACT.md:11, 419-428` states "at most 900 seconds" and "2 x `voice_seconds_per_message`" as literal contract values. `voice.session_cap_seconds` (60-3600) and `voice.chunk_units` (1-10) now change them at runtime. Clients read `session_max_seconds`, so nothing breaks, but the contract the Intelligence lane builds against (D-086) is no longer true.
- Fix: a contract revision that says "the server's policy (default 900; default 2 units)". The implementer must not edit the contract itself (D-086), so route the revision to the owner.

### P2-4 Setting a media price estimate to 0 silently disables the media spend caps, without the confirmation required for removing a cap
- `policies.py:136-139` (`media.asr_usd_per_hour`, `media.ai_usd_per_million_tokens`, `low=0`, no `confirm_*`). `media_spend.py:101-103,138-151`: every check compares `spent + estimate` against the caps, and spend is recorded from the estimate. The pipeline also serves learners' own imports (`media_transcript_pipeline.py` header), so the platform daily cap is a backstop for learner traffic.
- Fix: `low` > 0 (for example 0.001), or confirm any decrease below the default (`confirm_below`). A legitimately free provider should be modelled as a deliberate, confirmed choice.

### P2-5 Retention periods are Admin-editable beyond the published legal facts; the :8000 activation step moves from deploy to Admin
- `policies.py:122-126`. `docs/legal/public/facts.json` publishes `agent_turn_days: 90` and `feedback_months: 24`. `privacy.en.json:91` publishes "AI use and cost ... after 13 months", and `GOOGLE_PLAY_DATA_SAFETY.md` makes the same statements. `high=3650` lets Admin keep personal data up to 10 years, against the published policy. D-159 says switching the feedback sweep on, ":8000 included, is the human's activation". Today :8000 leaves both sweep variables unset, so Admin can now switch on deletion there. This is confirmed and audited, which is acceptable if the human accepts that Admin is the gate. The confirmations themselves are correct: every set or reset of a danger key needs `confirm[key] is True` on the server, turning a sweep off included, and the floors (7/30/90 days) are reasonable.
- Fix: set `high` to the published value (90 / 730 / 396), so Admin can only shorten, until the legal facts are generated from the effective policy. Record in D-172 that Admin is now the activation point for the sweeps, or have the :8000 deploy pin both sweep variables explicitly.

### P2-6 Synchronous settings reads on the event loop
- `app.py:246` → `http_security.py:97-103` (async middleware), `speech_api.py:496` (async `transcribe_speech`), `speech_api.py:819` (`_pronunciation_limiter`, on the loop). On a cache miss, `policies._loaded()` runs a blocking DB query on the event loop. Before this change the middleware did no I/O.
- Scenario: the SQLAlchemy pool is exhausted (the 40 threadpool workers are busy). The cache expires and the next state-changing request blocks the loop for up to the pool timeout, which freezes every request in that worker, health checks included.
- Fix: refresh the cache off the loop. Either a small background refresher thread, with `value()` only reading the in-memory snapshot, or `await anyio.to_thread.run_sync` around the read in async paths.

### P2-7 Switching voice off mid-session strands in-flight sessions and under-records voice spend
- `agent/api.py:182-186,299-305`: `/voice/end`, `/voice/tool`, `/voice/turn` and `/voice/context` all go through `_voice()`, which now returns 404 when `voice.enabled` is false. An unmetered session's wall-clock is billed to the AI ledger and the `agent.voice_seconds` meter only in `end()` and `_sweep()` (`voice_session.py:922-948`), and `_sweep()` runs only from `open`/`end`. Turning voice off leaves vendor tokens alive (up to 900 s) while their cost is never recorded. That also starves the daily spend guard, which reads the same ledger.
- `voice_session.py:950-954`: `_bill` caps at the *current* `voice.session_cap_seconds`. A cap lowered mid-session under-records a session whose token was minted for the old cap.
- Fix: gate only `/voice/session` (and `/voice/voices`) on `is_enabled()`. Let `end`, `tool`, `turn`, `context` and the refusal of `extend` act on existing sessions. In `_bill`, cap at `session.minted_seconds`, the seconds actually granted, not the live policy.

---

## P3 (notes)
- `policies.save()` (`:391`): a store read error is not `RuntimeError`, so the admin gets a 500, not a 503. Stored values that no longer validate are dropped on the next rewrite with no audit entry.
- `voice_session.py` `extend`: the cap is read twice (the check and `_mint_chunk`). Crossing a cache boundary can make `cap - minted < 1`, so `begin_voice` raises `ValueError` and the learner gets a 500 (no charge).
- Removing an env pin at a later deploy resurrects a previously stored Admin value (for example a sweep switched on earlier) without a fresh confirmation. Worth one line in the ADM-POL notes.
- Multi-worker: the 5 s cache, per-process limiters, per-process voice sessions and per-worker retention threads are all as before or as documented; the sweeps are idempotent. No further issue found.

## Class B/C audit (ADM-POL)
- No secret, key, URL, OAuth value or provider wiring is exposed in Admin, and `snapshot()` returns only env variable names, never values. `AGENT_ENABLED`, `BILLING_ENABLED`, rights clearances and migration-tied activations correctly stay in C.
- Wrongly in A: `voice.enabled` (P2-1). Borderline A, needing confirmation: the charging rules (P2-2) and the contract-stated voice shape (P2-3).
- Nothing an operator must tune appears wrongly kept in B. `AGENT_ENABLED` as a kill switch and the model names are correctly deferred.

## Out of scope for this review (route to design-reviewer)
- The pinned `Orena-Admin.dc.html` draws no Policies page (no match for policy, limit or spend-cap text). Under Design Contract rule 43 the page's composition needs a recorded human decision or a design frame. This review does not judge it.

---

## Re-review at 567fec42 (parent b962e957)

- Reviewer: Claude Opus 5.5, Delegated Architecture Reviewer (independent; did not write either commit)
- Reviewed SHA: 567fec42 on `feat/admin-policies`. Read-only `git diff b962e957..567fec42` and file reads. The new pytest and .mjs tests were judged by reading only; neither the reviewer nor the implementer ran them (Docker wedged). They must pass in the gate/CI before merge.
- **Outcome: APPROVE.** Both P1s are fixed correctly. P2-1, P2-2, P2-4, P2-5, P2-7 and the 503 P3 are fixed. P2-3, P2-6 and the remaining P3s are recorded in UI_BACKEND_GAPS "ADM-POL". This is architecture review, not product approval or activation authorization; the human gates are unchanged.

| Finding | Status | Evidence |
| --- | --- | --- |
| P1-1 spend cap fails open | **Fixed** | `policies.value_strict` (`policies.py`) raises `PolicyUnavailable` when the key is not env-pinned and either the store has never been read in this process (`state == "unreadable"`) or the stored value was rejected (`_Loaded.rejected`, carried into `stale` by `replace`). `app.py` `_agent_spend_guard` now uses it, so `LiveSpendGuard`'s `except` returns 3600 (fail closed). An env pin needs no store, and a process with no store at all gets the default. Tests read correct: a cold worker with a failing store refuses, recovers, keeps the cap through a later blip, and a cap invalid under a tightened range refuses. |
| P1-2 optional CAS on merge | **Fixed** | `save()` sets `expected_updated_at` to the version it just read (`None` when nothing is stored) whenever the caller omitted it, so the merge is always a compare-and-set (409). The racing-store test covers both interleavings (an existing row, and a first save) and that a refused save leaves no audit row. |
| P2-1 `voice.enabled` in Admin | **Fixed** | Removed from the registry (a save naming it is 422 "Unknown policy"). `VoiceService.enabled = lambda: voice_enabled(os.environ)`. The copy (EN/VI/ZH), the .mjs gate and ADM-POL class C are updated. A stored `voice.enabled` from the sandbox is ignored and logged, and dropped at the next save. |
| P2-2 charging rules unconfirmed | **Fixed** | `danger="charging"` on `quota.abandoned_settles`, `speech.no_speech_charged` and `voice.chunk_units`. The server confirms any change (`_needs_confirmation` honours any `danger`). The page mirrors this and has its own dialog body (EN/VI/ZH). |
| P2-3 Agent Contract v8 drift | Recorded | ADM-POL follow-up, routed to the contract owner (D-086). Still open, and must not be lost. |
| P2-4 media price 0 disables caps | **Fixed** | `low=0.001` on both estimates (Admin). The env may still pin 0, which is a deploy-level human act, as before. |
| P2-5 retention vs published legal facts | **Fixed** | Maxima 730 / 90 / 396 match `facts.json` (`feedback_months: 24`, `agent_turn_days: 90`) and the privacy text's "13 months". A test pins `high == default` for every deleting `*_days` policy. D-172 point 9 records that Admin is now the activation point for the sweeps, and recommends pinning both variables in the :8000 deploy. |
| P2-6 sync read on event loop | Recorded | ADM-POL follow-up. Still open. |
| P2-7 voice off strands sessions / under-bills | **Fixed** | Only `/voice/session` and `/voice/voices` require `is_enabled()`. `end`, `tool`, `turn`, `context` and `extend` act on existing sessions. `_bill` caps at `session.minted_seconds`. Both behaviours are tested. |
| P3 500 on save read error | **Fixed** | Wrapped as `RuntimeError` → 503, tested through the route. Remaining P3s are recorded in ADM-POL. |

### Regressions looked for: none blocking
- **Default parity:** every remaining default is unchanged and `voice.resumption` is still pinned by its test. The policy count is now 37 (decision log and ADM-POL updated).
- **Voice routes:** no existing test relies on `runtime.voice is None` or on a bare "Not Found" from `end`/`tool`/`turn`/`context`. With voice off, those routes now answer 404 `voice_session_not_found` from the service, which is the same status. `extend` is no longer refused by the switch, but the switch is an env value fixed for the process's life and voice sessions live in process memory, so no session can outlive a switch-off. Moot today; if the switch ever becomes runtime-editable again, refuse `extend` too.
- **Test isolation:** `monkeypatch.setattr(policies.time, "monotonic", ...)` patches the global `time.monotonic` for one test. `DailySpendGuard`'s default bound the original function at class definition, and monkeypatch restores it, so this is harmless.

### New P3 notes (no action required before merge)
- The strict read also fails closed on a deployment that never set a cap: a cold worker whose settings store is unreadable refuses agent turns until the first good read. Before D-172, no cap meant never refused. This is the intended safe direction, but it is a behaviour change; worth one line in D-172.
- When a dialog confirms both deleting and charging changes, the body shows only the "deletes" sentence. The list still names every change.
- Only the feedback retention help text names its published maximum. The agent-turn and AI-cost periods show their range but not the reason. Copy only.
