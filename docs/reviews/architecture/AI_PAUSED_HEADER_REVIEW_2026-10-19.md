# `X-Orena-AI-Paused` (PR #315): independent review (2026-10-19)

- **Reviewer:** Claude (Opus 5.5), independent and read-only.
- **Reviewed commit:** `0bfb1ea0`.
- **Outcome:** **APPROVE**, with no P0 or P1.

The reviewer confirmed four things:
- The request-scoped mark reaches the middleware from both the threadpool and `call_next`.
- Marks cannot leak between requests.
- Background jobs see no mark and do not crash.
- The middleware sits outside the security and body-size middlewares, so their refusals are never marked.

| ID | Finding | Disposition |
| --- | --- | --- |
| P2-a | `resets_at` was `now + wait`, which can be a few seconds off and differ from the 429 body. | **Fixed.** It is the ceiling guard's own `resets_at`, as `ceiling_status()` reports it. |
| P2-b | A fallback that still answers the learner, such as word audio's next voice, marked the response as paused. | **Fixed.** `ceiling_reached(mark=False)` lets a working fallback leave the response unmarked, and word audio uses it. Test: `test_a_working_fallback_is_not_marked_and_resets_at_is_the_ceilings_own_midnight`. |
| P2-c | A refusal inside a streaming body comes after the headers are sent, so it cannot be marked. | **Accepted and recorded.** The agent's ceiling check runs before its stream starts, and a later round reaches the client as an SSE frame. There is no CORS middleware, so the app is same-origin and the header reaches the browser with no expose list. |
