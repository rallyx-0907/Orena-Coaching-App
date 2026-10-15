# PR-MON-7D2: speech and TTS meter plumbing (review request)

**Status: IMPLEMENTING, draft PR for CI and independent review.** Branched from `main` `4327250d`. Owner decisions:
H7-3 (D-MON-025: units frozen, no invented speech/TTS limits, enforcement off) and the no-double-charge matrix of the
PR-MON-7 design (recorded in the Billing decision log on PR #231/#233).

## Pending meters

`quota.PENDING_METERS` holds three meters with their frozen D-MON-023 H-2 units:
- `speech.transcribe`: seconds;
- `speech.evaluate`: seconds;
- `audio.tts`: characters.

**Wired, never enforceable:**
- They are not in the catalogue (no window, no Free/Plus/Pro limit), not in `WIRED_METERS`, and not credit-eligible.
- `require_feature`, `require_ready`, `begin` and `admit` accept them and always take the no-op path, even when the
  environment lists them.
- Nothing is reserved or written, and no learner request changes.
- Enforcing one later means moving it into the catalogue and `WIRED_METERS` with its approved window and limits.

## Call sites

| Path | Meter | How |
| --- | --- | --- |
| `POST /api/speech/transcribe`, standalone (`purpose` empty) | `speech.transcribe` | 1. Feature/readiness first.<br>2. The take is measured locally (ffmpeg).<br>3. Admitted at `ceil(seconds)` before the Groq call (digest: audio + language).<br>4. Settle the seconds the provider heard, never more than admitted; 0 after a provider failure (admit's failure path). A refusal at admission calls no provider.<br>The `speech_asr` cost telemetry is unchanged. |
| `POST /api/speech/transcribe`, `purpose=orena_voice` | none here | Push-to-talk is part of an Orena message: only the existing read-only `orena.message` availability check runs; the agent turn charges its message. |
| `POST /api/speech/pronunciation` | `pronunciation.audio` | Unchanged. |
| `POST /api/speech/evaluation` | none | Deterministic normalization and no provider. `speech.evaluate` is a contract only until a remote evaluator exists; none is added. |
| Fresh learner word TTS, inside `AzureVoice.speak` | `audio.tts` | Admitted only when the paid voice actually synthesizes: after the audio cache and the free voices missed, after the spend cap. `billed_characters(term)` units. Settles the units on audio and 0 on failure. Cached, stored and catalogue audio is never charged. |
| Orena conversational voice (live) | `orena.message` only | Unchanged (`begin_voice`). There is no server ASR or TTS to charge. |

## Not changed, noted

- **Funding:** the ASR and word-TTS paths still get no `FundingContext` while the meter is pending (the no-op ticket
  carries none). Under `FUNDING_ENFORCEMENT=enforce` they would still be refused as before. This is unchanged
  behaviour and off by default; it closes when the meters are enforced with an admission.
- **System callers:** a non-learner caller of `AzureVoice.speak` (a coverage or backfill script) would need
  `system_funding` once `audio.tts` is enforced. Today the admission is the no-op.

## Tests

`tests/test_speech_meters.py` (13 cases) freezes:
- the units;
- "never enforceable, even when listed";
- "not a plan entitlement, not credit-eligible";
- standalone ASR admitted in measured seconds before the provider, settled with the heard seconds, 0 on a provider
  failure, no provider call on a refusal;
- push-to-talk never charged as a transcription;
- speaking evaluation admits nothing;
- fresh TTS admitted in billed characters, 0 on failure, nothing when the paid voice is not asked, nothing for cached
  audio;
- conversational voice only `orena.message`.
