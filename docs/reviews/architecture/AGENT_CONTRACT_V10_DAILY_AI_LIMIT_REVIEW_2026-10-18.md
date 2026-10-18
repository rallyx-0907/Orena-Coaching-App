# Agent Contract v10, server side: `daily_ai_limit` (PR #304), independent review (2026-10-18)

- **Reviewer:** Claude (Opus 5.5), independent and read-only. It did not write this code.
- **Reviewed commit:** `0981ee7e`.
- **Outcome:** **CHANGES REQUIRED** (one P1).

| ID | Finding | Disposition |
| --- | --- | --- |
| P1-1 | The spend check moved into `async` dependencies, which ran the guard's database reads (the ledger and the settings store) on the event loop. | **Fixed.** `await run_in_threadpool(check)`. |
| P2-1 | The voice test accepted 404, so it could pass without testing anything. | **Fixed.** A stub `VoiceService`, exact 429s on v10 and v9, nothing minted, and the turn window left unused. |
| P2-2 | An absent voice route answered 429, or counted against the window, before its 404. | **Fixed.** `_voice_present` answers 404 before any limit. |
| P2-3 | A cap or ledger that cannot be read was told as "AI paused until midnight" (`retryable: false`). | **Fixed.** `check()` now marks faults. A fault is answered `rate_limited` with `Retry-After: 60` (it fails closed, then retries soon), never `daily_ai_limit`. |
| P2-4 | `contract_version: 10.0` was read as 0. | **Fixed.** An integral float is accepted and a boolean is not. The gate keys on the declared version until `CONTRACT_VERSION` becomes 10 with the UI lane's contract text. |
| P2-5 | No test exercised the real `LiveSpendGuard.check()`. | **Fixed.** `test_check_says_which_limit_refused_and_whether_it_is_a_fault`, plus a v10 refusal of a schema-invalid body (429, not 422). |
| Note | Invalid JSON is answered 422 before the dependencies run. | **Pre-existing**, recorded here and unchanged. |
