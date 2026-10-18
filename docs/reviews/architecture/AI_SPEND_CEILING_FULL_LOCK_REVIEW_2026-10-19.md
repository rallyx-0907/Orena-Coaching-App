# The system AI spend ceiling locks every paid call (PR #308): independent review (2026-10-19)

- **Reviewer:** Claude (Opus 5.5), independent and read-only. It did not write this code.

## Round 1: reviewed commit `4a570e21`, outcome **CHANGES REQUIRED**

| ID | Finding | Disposition |
| --- | --- | --- |
| P1-1 | Media ASR was counted twice. Its priced `speech_asr` rows are already in the AI ledger, written through `audio_telemetry`. | **Fixed.** The extra count (`asr_spent_since`) is removed. |
| P1-2 | Some paid calls passed neither gate: Groq translation for Listening and Reading, Speaking recognition, pronunciation scoring and word audio. The docs called these not counted, but they are recorded. | **Fixed.** `require_below_ceiling()` runs before each funding backstop, and Groq translation raises `TranslationProviderError(reason="system_ceiling")`. A `SpendCeilingReached` that no caller handles becomes a plain `429 daily_ai_limit`. The docs are corrected. |
| P2 | `AllProvidersUnavailable.reason`, a distinct media code, end-to-end `generate_structured` tests, and the Admin provider-test bypass. | **Deferred.** The bypass is now documented as not stopped. |

## Round 2: reviewed commit `eb7817af` (fix `6acac173`), outcome **APPROVE**

- The reviewer checked three things:
  - The word-audio admission is released on a refusal, so the learner is not charged.
  - Listening and Reading refuse locally, with no cache entry and no loop.
  - The 429 handler can be reached.
- P2 follow-ups:
  - Word audio should fall back to the local voice at the ceiling, not answer 429. Taken next.
  - Learners are told different things on different surfaces.
  - The handler and placement tests are structural, not end-to-end.
  - The Speaking day brake still counts a take that the ceiling refuses.
