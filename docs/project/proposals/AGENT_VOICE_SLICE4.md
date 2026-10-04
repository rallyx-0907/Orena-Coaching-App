# Orena Intelligence - Slice 4 (Voice) design proposal

Status: PROPOSAL for human review. Lane: `feature/orena-intelligence`. Date: 2026-10-04.
Scope of this document: design only. No code, no provider call, no Docker, nothing committed.
Voice is `[PROVIDER]` and a credential gate (AGENT_SPEC R6, ARCHITECTURE_INVARIANTS human gates): nothing here
is authorised by being written.

Labels used for every figure: **MEASURED** (a repo artifact, path given), **PROVIDER-LIST-PRICE** (a vendor's
published or quoted rate; I could not re-verify any of them from this repo, so each is "unverified"),
**ASSUMPTION** (mine, to be replaced by a test). "unknown - needs test X" means no number exists.

## 0. What the repo already holds (evidence)

| Fact | Where |
| --- | --- |
| Voice interfaces only, no vendor wired: `ConversationalSpeechSession` (open / push_text_segments / interrupt / close), `PrerenderedSpeechCache`, `SessionHandle`, `VoiceUsage(audio_seconds_in, audio_seconds_out, interruptions)`, `AudioChunk` (`pcm16_24k` only) | `writing_coach/agent/voice.py`, `tests/test_agent_voice.py` |
| A failed voice session ends as `error{voice_unavailable, fallback: text_only}`; never another vendor | `voice.py` docstring, `AGENT_SPEC.md` R2, §37, `AGENT_CONTRACT.md` §4.1 |
| Contract §9 `POST /api/agent/voice/session` is provisional: returns `voice_session_id`, `mode s2s\|cascade`, `transport webrtc\|websocket`, `connect{url, ephemeral_token, expires_at}`; tool calls and actions still arrive as §4 events; sessions capped 15 min; raw audio not stored | `AGENT_CONTRACT.md` §9; `limits.py` `voice_session_cap_seconds = 900` |
| Events `voice_state{listening,thinking,speaking,interrupted}` and `audio_chunk{pcm16_24k}` ("voice cascade only") exist | `AGENT_CONTRACT.md` §4 |
| `voice_style` closed enum: `neutral_explain \| encouraging \| gentle_correction \| celebrate \| brief_ack \| reference` | `AGENT_CONTRACT.md` §5.2 |
| Capability keys `conversational_speech` (CONVERSATIONAL_SPEECH) and `text_to_speech` (TEXT_TO_SPEECH) are defined inert: `configurable=False, implemented=False`. So are `speech_asr` and `pronunciation_evaluator` | `writing_coach/ai/capabilities.py` (the `_definition(...)` entries) |
| `pricing.py` is token-only (`TokenPricing`), exact-match, one Gemini entry (`gemini-3.5-flash-lite` 0.30 / 2.50 USD per M tokens, "read 2026-09-27"). No audio, per-minute or Live pricing exists | `writing_coach/ai/pricing.py` |
| Track 0 spike (Gemini Live, local page, ephemeral tokens, compares `gemini-3.8-live` and `gemini-2.5-flash-native-audio-preview-12-2025`, measures time-to-first-audio, barge-in, language mix, a 1-5 quality score). Nothing imports it | `scripts/voice_spike/{README.md,server.py,app.js,capture.js}`, `tests/test_voice_spike.py`; commits `d37d8b3`, `297036b` |
| **No spike results are in the repo.** The human's first session export (2026-09-28) lives outside it. The only findings that reached Git are defects in the measuring page and one pronunciation defect (below). AGENT_SPEC Track 0 names an output `docs/operations/AGENT_VOICE_SPIKE_<date>.md` and a bake-off set `docs/agent/BAKEOFF_SET.md`: neither exists (`docs/agent/` is absent) | `AGENT_SPEC.md` §26; `ls docs/operations` |
| From the first session (commit message `297036b`): a Chinese word inside a Vietnamese sentence (学) was read "xã", i.e. Hán-Việt, not Mandarin `xué`. The persona was then changed to demand pinyin readings. **Whether the fix works is not measured in the repo** | `git show 297036b`; `scripts/voice_spike/app.js` `PERSONA` |
| Live locks: Gemini Live has its own quota-group lock `live-gemini-live.lock`, separate from text | `scripts/agent_live/README.md` |
| Text-agent latency, MEASURED: time to first segment, median 3.99 s, slowest 5.94 s (gemini-3.5-flash-lite, 2026-10-04, 11 turns); earlier median 2.96 s over 82 turns; 17.6 s / 19.1 s on gemini-3.8-flash | `AGENT_SPEC.md` §0 (Live 2026-09-28 and 2026-10-04 rows, Slice 3 row) |
| Text-agent cost, MEASURED: 9 agent rounds, 24,487 prompt + 259 completion tokens = USD 0.008 (telemetry); about USD 0.0009 per round | `docs/reviews/ORENA_AGENT_LIVE_8021_CHECKPOINT.md`. Cross-check with `pricing.py`: 24,487 x 0.30/1M + 259 x 2.50/1M = 0.0080 |
| Azure Pronunciation Assessment through Orena's route: latency 0.45-1.2 s; **its own tone labels can be wrong** (任 labelled `ren 2`, particle 吗 as `ma 2`), so tone errors can read as passed | `docs/operations/SPEAKING_AZURE_E2E_2026-09-23.md` |
| Spec cost guesses (unverified, "re-measure in Track 0"): Gemini Live ~0.036 USD/min; Azure Voice Live Standard (gpt-realtime-mini) ~0.02-0.03; GPT-Live 1 0.05 + backend tokens; cascade (Groq ASR + Gemini TTS) ~0.02-0.05; default metering proposal 30 voice min/user/day | `AGENT_SPEC.md` §41 |
| Per-process limiter is explicitly not a quota; an authoritative per-account quota is required before multi-worker or public rollout; staging runs one worker; counting would start from the existing `usage_events` table | `writing_coach/agent/ratelimit.py` docstring; `AGENT_SPEC.md` R26 |
| Agent is off by default (`AGENT_ENABLED`); production never serves it | `AGENT_SPEC.md` R9 |

Gap noticed: the spike persona's style names (`warm_encourage`, `gentle_correct`, `slow_model`) are not the
contract's enum (`encouraging`, `gentle_correction`; no `slow_model`). The persona is spike-only, but Slice 4
must map to the contract enum, and `slow_model` has no contract home (open question Q6).

## 1. Interaction flow (6.1)

### 1.1 One pipeline, two mouths

There is no "Voice Agent". Voice is a transport around the turn pipeline in `writing_coach/agent/turn.py`,
exactly as `voice.py` already says ("a voice session delegates to the same turn and tools"). Everything the
text turn does runs unchanged for a spoken turn, because the spoken utterance becomes the same
`TurnInput` a typed message would:

- the same learner scope, `context` (3 language layers, `address`, `screen`, `capabilities_here`), tool
  registry and READ_ONLY gateway;
- the same decision gates before the model: identity question (`identity.py`), screen help (`screen_help.py`,
  tools withheld), authorization pre-check (another user's data is refused);
- the same server claim gate (`honesty.py`): "I saved/did X" claims and invitation sentences are the
  server's, not the model's (R18, R23);
- the same memory authorization: `remember_note` / `forget_note` only on the learner's explicit request;
  a note is "saved" only after the `memory_update` event; the claim "Mình lưu ... cho bạn" is a claim;
- the same target-language reset: `409 target_language_mismatch` (contract §2.1) when `context.locale.target`
  is not the learner's learning language on the server;
- the same rate limit, metering (`metered`) and error classes.

### 1.2 Recommended topology: server-brain, vendor as ears and mouth

```text
mic -> capture (16 kHz PCM, client) -> vendor live session (input only: VAD + input transcription)
    -> partial transcript (UI shows it, never acted on) -> final transcript
    -> server: the same turn pipeline (tools, evidence, claim gate)  -> segments {lang, text, voice_style}
    -> gate-cleared sentence -> speech synthesis (same vendor voice) -> audio_chunk / playback
    -> transcript + evidence + actions land in the thread (same events as text)
```

Why not a delegating speech-to-speech model that speaks for itself: a vendor model that generates its own
audio can say "your tone was wrong" or "I saved it" before any tool ran, and server-side claim gating cannot
unsay audio. The claim gate and R26's "text written in the same round as a read tool never reaches the
learner" are text-stage controls. So the primary Slice 4 mode is **mode B: server-brain** (contract
`mode: "cascade"` shape, with the vendor session doing recognition and speech but never composing content).
The spike already shows a read-verbatim mode is feasible with Gemini Live (`READ_MODE` in `app.js`: it
reads tagged sentences without adding anything); whether it holds across languages is test T1 below.

Mode A (delegating S2S, the model speaks and calls one `ask_orena` tool) stays an experiment: it may be
measured in the test matrix but is not shipped unless a test shows it cannot speak a claim ahead of the
gate. It would need contract wording (the contract's `mode: s2s` already exists).

Cost of mode B: latency. The text agent's measured time to first segment is a median 3.99 s (section 0),
well over the spec's E2E 10 target "TTFA < 1 s". Section 6.5 proposes how to reconcile this (a
non-claim acknowledgement within 1 s, substantive audio when the gate releases it); that target change is a
human decision (Q1).

### 1.3 Evidence-before-claim (R26 area, contract §5.3) with streamed audio

Rule: **no audio is synthesised for a sentence until the sentence has been cleared**, and a sentence that
states an error about the learner is cleared only when the `evidence` event it cites has already been sent.

1. The turn streams `segment_delta` text as today. `honesty.py` holds the stream "from its first possible
   claim or button offer on" and drops what it must; only released sentences enter the speech queue.
2. Contract ordering already says an `evidence` event precedes any `segment_end` that cites it. For voice,
   the speech queue additionally never starts a sentence of a segment that cites evidence before that
   evidence is emitted. Evidence is read by a tool in the same turn, and R26's rule applies: the text
   the model wrote alongside the tool call is discarded; only the answer written after the tool result is
   spoken.
3. Tool-backed error statements ("Âm 是 bị đánh dấu là phát âm sai, 6/100", contract §5.1 example) are
   spoken from the segment text the server cleared, i.e. text written after the read. "No error marked" is
   never spoken as "no error" (R18b).
4. Spoken sentences are the cleared text byte for byte; the synthesiser gets the text, not a prompt to
   paraphrase. A test (section 5, "tool-backed answer") asserts the output transcript equals the cleared text.
5. Failure: if evidence cannot be read (tool error), the turn speaks the server's fixed unavailable line
   (existing `_unavailable` path), never a model guess.

### 1.4 Step by step

| Step | Behaviour |
| --- | --- |
| Mic | The client reuses the app's mic-readiness and recorder (contract §9). Permission denied or no input: the voice affordance is hidden or shows the existing mic state; text works. |
| Capture | 16 kHz mono PCM chunks from an AudioWorklet (spike: `capture.js`, `audio/pcm;rate=16000`). No audio is kept anywhere; the client discards after send. |
| Live input | Client opens the vendor WebSocket with the one-use ephemeral token minted by the server (spike pattern: token must open within 60 s, valid 30 min). The provider key never leaves the server. |
| Partial transcript | Shown greyed in the composer as the learner talks. Not sent to the agent, not stored. |
| Final transcript | At end of utterance (vendor VAD), the final transcript is posted as a turn by the client with `trigger: "voice"` (proposed v6 field; it is a normal message turn otherwise). It lands in the thread as the learner's message, editable only before send in a "review transcript" mode (Q4). |
| Reasoning and tools | The server runs the turn. `voice_state: thinking`; `tool_call.label` shown on screen while a tool runs (contract §4, already live in text). |
| Spoken response | Cleared sentences are synthesised and streamed as `audio_chunk` (pcm16_24k) with `voice_state: speaking`. Segments of `voice_style: reference` are played from reference audio (`word_audio` / `play_model`), not the conversational voice. |
| Thread sync | The same events build the thread as in text: `segment_delta/_end`, `evidence`, `action`, `memory_update`, `done`. The spoken and written words are the same string. |

### 1.5 Interrupt, barge-in, cancel, turn boundary

- **Barge-in**: the vendor signals interruption (spike records Gemini's `interrupted` and the time from
  speech onset to it). The client stops playback at once, sends `abort` on the turn (the same abort a
  text learner has, contract §2.1), and the server cancels generation and the speech queue.
- **What counts as spoken**: the thread keeps the full written reply, but marks the segment where audio was
  cut (`voice_state: interrupted` plus the index). The server records only what was synthesised and played
  up to the cut as "said", so a later turn's context never claims the learner heard a sentence they did not.
  Today's contract has no "spoken-until" field: a v6 candidate (Q5), with a client-only fallback.
- **Cancel** (button or "stop"): same path as barge-in without a new utterance.
- **Turn boundary**: a turn ends at the vendor's end-of-speech plus a server-side settle window (value
  unknown - needs test T2, silence and long-pause cases). A learner talking again inside the window extends
  the same utterance. A voice turn counts against the same per-learner limiter (12 turns/60 s in
  `limits.py`) and the same `turn_ordinal`.
- **Silence**: no speech for a configured idle time closes the session politely with a non-claim line and
  returns to text; it is not an error.

### 1.6 Reconnect and text fallback

- Sessions are capped at 15 min (`limits.py`). At the cap, or on a dropped socket, the client asks the
  server for a new `voice_session_id`; the server reloads layer 1 and layer 3 (device memory notes) exactly
  as `AGENT_SPEC` §33.5 says. **No audio history is carried** and none is stored.
- If a drop happens mid-turn the server still finishes the turn (the text is complete in the thread); the
  unspoken remainder is not replayed as audio, it is shown as text. The client may offer replay by tap.
- Reconnect budget (ASSUMPTION): 2 automatic attempts, then `error{voice_unavailable, text_only}`; voice mode
  closes and the conversation continues in text. It never moves to another vendor (R2, ARCHITECTURE_INVARIANTS:
  no provider-to-provider fallback). Mode choice (s2s vs cascade) is made when a session opens, never to
  rescue a failed one (`voice.py` docstring).
- Voice off, token mint failing, or capability off: Orena's text panel is unaffected; the mic is absent
  (the UI's existing 404-hides-Orena convention applies to the voice route).

### 1.7 Tools, action confirmation and error recovery in a voice turn

- Tools are the same READ_ONLY registry. The learner hears at most one short non-claim filler
  (`brief_ack`, pre-rendered, "Để mình xem nhé" in their language) when a tool round runs longer than the
  acknowledgement threshold; the on-screen `tool_call.label` carries the detail.
- Actions are **invitations, never done by voice**. Contract §7 and R18/R23: an action is a button the
  learner taps; the server writes one standard invitation sentence per action. In voice that sentence is
  spoken, the card appears, and the learner taps. A spoken "ok" is never a mutation. Whether a spoken
  "yes" may press the pending card is a UI/contract decision (Q3) and is not assumed.
- Memory: a spoken "nhớ giúp mình rằng..." is the same explicit request as typed; the saved note is shown
  in the `memory_update` card and quoted back from the saved record, because recognition errors can change
  a name or a word.
- Recoverable errors: `rate_limited` (429) -> Orena waits, the mic shows a wait state, retry after
  `Retry-After`; `target_language_mismatch` (409) -> close the voice session, refresh locale, reopen
  (this is also the language-switch path); recognition produced nothing -> ask once, in the learner's
  language, then offer text; an unknown error class acts by its `fallback` (contract §4.1).

## 2. Model and provider recommendation (6.2)

### 2.1 Candidates

Only Gemini Live was reached in the repo, and only by the spike, with no committed results. Everything else
is listed on the spec's say-so and is unverified. Cells say "unknown - needs test X" where nothing is known
(tests are section 2.3).

| Candidate | Latency | Naturalness / prosody | EN / ZH / VI | Tool calling | Interruption | Streaming | Price (unverified) | Ops complexity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Gemini Live, `gemini-3.8-live` (spike's preferred) | unknown - T2 | unknown - T1 rubric | unknown - T1; Mandarin-in-Vietnamese defect seen once (`297036b`) | exists in the API; not needed in mode B | yes (`interrupted` signal; spike measures it) | WebSocket, ephemeral token | ~0.036 USD/min, PROVIDER-LIST-PRICE (`AGENT_SPEC` §41, unverified) | lowest: key already in sandbox, ephemeral-token pattern built in the spike, own quota lock |
| Gemini Live, `gemini-2.5-flash-native-audio-preview-12-2025` | unknown - T2 | unknown - T1 | unknown - T1 | as above | as above | as above | same rate assumed, unverified | same; "preview" model id, deprecation risk (ASSUMPTION) |
| OpenAI realtime / "GPT-Live 1" | unknown - T2 | unknown - T1 | unknown - T1 | native; delegation=client in the spec | native | WebRTC/WS | ~0.05 USD/min + backend tokens, PROVIDER-LIST-PRICE (`AGENT_SPEC` §41, unverified) | credential gate, new provider, no adapter, `pricing.py` has no entry |
| Azure Voice Live Standard (gpt-realtime-mini) | unknown - T2 | unknown - T1 | unknown - T1; Azure speech already used for pronunciation (zh-CN, EN) | native | native | WS | ~0.02-0.03 USD/min, PROVIDER-LIST-PRICE (`AGENT_SPEC` §41, unverified) | new resource, credential gate; `ai/azure.py` exists for speech assessment only |
| Pipeline: Groq ASR -> agent text turn -> TTS (Gemini TTS or other) | ASR + the text TTFS (median 3.99 s MEASURED) + TTS first chunk (unknown - T2) | depends on the TTS model; per-sentence synthesis can lose cross-sentence prosody (ASSUMPTION) | ASR exists (`speech_asr.py`, Groq whisper); TTS ZH/VI unknown - T1 | the text agent's own, unchanged | by cancelling the queue; no vendor VAD (client VAD needed) | sentence-level only | ~0.02-0.05 USD/min, PROVIDER-LIST-PRICE (`AGENT_SPEC` §41, unverified) | existing `speech_asr` and `Voice` adapters; most moving parts |

Note on fit. Mode B uses a Live model only for recognition and for speaking supplied text. That favours a
provider that can (a) transcribe input with VAD and partial results and (b) speak supplied text verbatim,
in multiple languages inside one sentence. Those two properties are what T1 and T2 test; the "smartness"
of the live model is not used.

### 2.2 Recommendation

1. **Default to Gemini Live for Slice 4 testing**, because it is the only candidate with a working harness,
   a credential already in the sandbox, an ephemeral-token minter and its own quota lock, and because the
   text agent already runs on Gemini (`agent_turn_*` pinned to gemini-3.5-flash-lite). This is a pragmatic
   reason, not a quality finding: no quality finding exists in the repo.
2. **Do not switch provider because a model is newer.** Choosing between `gemini-3.8-live` and the
   `2.5-flash-native-audio` model is decided by T1 and T2, not by version number. A different vendor is
   tried only if Gemini Live fails the code-switch gate (section 3) or the latency gate (section 5); trying one
   needs its own credential gate.
3. **Per-language routing is a config question** (AGENT_SPEC §33.2: "each language has one main path;
   change vendor = change the capability key"). If one vendor is best at ZH and another at VI, that is
   two keys' worth of routing and two rhythms of risk, so it is accepted only with evidence.
4. The Gemini TTS and Live model ids need exact-match entries in a future audio pricing catalog; `pricing.py`
   reports unknown models as unpriced, which is the right default until a rate is verified.

### 2.3 Live test matrix and budget (NOT RUN)

Budget rule: <= USD 1.00 per staging day, hard stop in the runner at USD 0.80, reserve 0.20 for retries
(R25's retry rule: bound computed before each send, retries included). Lock: `live-gemini-live.lock` for the
Gemini Live group (`scripts/agent_live/README.md`). Rate used for estimates is 0.036 USD/min = 0.0006 USD/s
(PROVIDER-LIST-PRICE, unverified); every estimate must be recomputed from the vendor's actual `usage` (the
spike's measures) after the first run. No raw audio is kept outside the reviewers' working set (Q7).

| Test | What | Items | Audio estimate (ASSUMPTION) | Cost estimate |
| --- | --- | --- | --- | --- |
| T1 code-switch | read-verbatim of the 22 sentences in section 3.3, `gemini-3.8-live` and the 2.5 native-audio model, once each | 22 x 2 | 22 x 10 s x 2 = 440 s | 0.26 USD |
| T1b repeat | the same set on the leading model only, to see variance | 22 | 220 s | 0.13 USD |
| T2 interaction | barge-in x5, silence x3, noisy x3, long utterance x3, reconnect x3, language-switch x2 on the leading model | 19 | 19 x 30 s = 570 s | 0.34 USD |
| **Day 1 total** | | | 1230 s (20.5 min) | **0.73 USD** (reserve 0.27) |
| T3 comparator (only after a credential gate) | T1 once on GPT-Live 1: 220 s x 0.05/60 = 0.18 USD; on Azure Voice Live: 220 s x 0.025/60 = 0.09 USD | 22 each | 220 s each | separate day, <= 0.20 each |
| T4 cascade comparator | Groq ASR + a TTS for T1 | 22 | audio-seconds as above | unknown - needs the ASR and TTS rate sheets; not estimable from the repo |

Pass thresholds for choosing a provider are the section 3.5 and section 5 criteria. Output goes to
`docs/operations/AGENT_VOICE_SPIKE_<date>.md` (the Track 0 template: no key, no region, no raw JSON, no
learner audio).

## 3. Code-switch pronunciation (6.3)

### 3.1 Requirement

A Vietnamese sentence with English and/or Chinese words must speak each foreign span in its own language:
English words in English phonology (not Vietnamese-accented, no added tone marks), Chinese words in
Mandarin with correct tones (not Vietnamese-accented, **not Hán-Việt**). The rule is language-neutral
("each span in its own language's pronunciation"); Orena is multilingual, not Vietnamese-centred, so the same
set is reused with English or Chinese as the carrier language where useful. **Not designed here: any Hán-Việt
feature.** The observed bug (学 -> "xã", `297036b`) is the failure this section tests for; a Hán-Việt gloss
after a Mandarin reading ("xué, học") is the learner's own content, not a mode.

### 3.2 Mechanism (what the server controls)

Segments already carry `lang` and `text` (contract §5.1: a mixed reply is a list of segments precisely "so
mixed-language speech and reference audio can be routed"). Proposal:

1. The server splits a reply into **language spans** deterministically (script detection: Han vs Latin;
   Latin-script span language from the turn's target/support pair and the segment's declared `lang`),
   rather than asking the voice model to guess. A span is `{lang, text}`.
2. If the provider supports it, each span is sent with explicit language markup: SSML `<lang xml:lang="en-US">`
   / `<lang xml:lang="zh-CN">` (Azure's neural voices document `<lang>`; not verified here, test T1 on Azure only if
   Azure is opened), or per-span synthesis calls with per-span voice/locale, concatenated by the speech queue.
   Whether Gemini Live honours any language markup in read-verbatim mode is **unknown - needs test T1 (with
   and without a per-span instruction)**.
3. For Chinese spans, the server may pass pinyin with tones as a pronunciation hint (e.g. `行(háng)`) when the
   segment text is ambiguous. Polyphonic resolution is the model's job; the hint is a tool for the test
   failures, and its use is only adopted if T1 shows the model errs.
4. `reference` segments keep playing reference audio (`word_audio`), unchanged.

### 3.3 Test set (22 sentences, to be recorded as real audio)

Expected: carrier language Vietnamese unless marked. Phonemic notes are IPA-light on purpose; the rater
judges against native speakers, not against this table alone.

**A. VI + EN**

| # | Sentence | Expected |
| --- | --- | --- |
| 1 | Hôm nay mình học từ "comfortable" nhé. | English /ˈkʌmftəbəl/ (about three syllables, stress on COM); no "com-pho-ta-bồ", no Vietnamese tone on any English syllable. |
| 2 | Bạn thử nói "I'd like a cup of coffee, please" xem. | English sentence in English rhythm and intonation; /aɪd/, /ˈkɔːfi/, /pliːz/; no syllable-timed Vietnamese cadence. |
| 3 | "Thorough" và "through" khác nhau ở âm cuối. | /ˈθʌrə/ (UK) or /ˈθɜːroʊ/ (US) vs /θruː/; both with /θ/ (not /t/ or /th/ as Vietnamese "th"). |
| 4 | Mình gửi bạn file qua email nhé. | "email" in the voice's chosen reading consistently (Vietnamese or English); recorded as ambiguous loanword, rated for consistency only. |

**B. VI + ZH**

| # | Sentence | Expected |
| --- | --- | --- |
| 5 | Từ 学习 đọc là xuéxí. | xué (tone 2, rising) xí (tone 2). **Not** "học tập", not "xã", not Vietnamese "xuế". |
| 6 | Cảm ơn trong tiếng Trung là 谢谢. | xièxie: xiè tone 4 (falling), second syllable neutral and short. Not "tạ tạ". |
| 7 | Xin chào là 你好 nhé. | Pronounced ní hǎo (third-tone sandhi: 3+3 -> 2+3). A flat or double-falling reading is wrong. |
| 8 | Câu "我不是老师" nghĩa là mình không phải giáo viên. | wǒ bú shì lǎoshī: 不 sandhi to bú before a fourth tone; 老师 lǎo(3) shī(1). |

**C. VI + EN + ZH**

| # | Sentence | Expected |
| --- | --- | --- |
| 9 | "Friend" là 朋友 péngyou, còn "teacher" là 老师 lǎoshī. | friend /frend/ in English; péng (2) you (neutral); teacher /ˈtiːtʃər/; lǎoshī. Three accents, each clean, with no bleed. |
| 10 | Hôm nay mình ôn "coffee" là 咖啡 kāfēi, và "tea" là 茶 chá. | coffee English; kāfēi (1, 1); tea English; chá (2). |
| 11 | Nói "Hello" rồi 你好吗? Trả lời "I'm fine, 谢谢". | Hello and I'm fine in English intonation; nǐ hǎo ma (ní hǎo ma); xièxie as in #6. The switch back to Vietnamese resumes Vietnamese tones. |

**D. Proper nouns and ambiguous words**

| # | Sentence | Expected |
| --- | --- | --- |
| 12 | Bạn đã từng đến Beijing chưa? Người Trung Quốc viết là 北京. | "Beijing" as English /ˌbeɪˈdʒɪŋ/; 北京 Běijīng (3, 1; 北 half-third before tone 1). Not "Bắc Kinh". |
| 13 | Anh ấy tên Nguyễn, đồng nghiệp tên Smith, bạn học tên 王伟. | Nguyễn in Vietnamese with its tone; Smith English /smɪθ/; 王伟 Wáng Wěi (2, 3). Vietnamese proper noun must not be anglicised. |
| 14 | Mình dùng "pin" hay "battery" cho điện thoại? Còn 拼音 là pīnyīn. | "pin" as a Vietnamese word /pin/; battery English; 拼音 pīnyīn (1, 1). The Latin-looking "pin" and "pinyin" must not collapse into one reading. |
| 15 | Từ "ma" có nhiều nghĩa; 妈 mā, 麻 má, 马 mǎ, 骂 mà. | Vietnamese "ma" (/ma/ ghost) first; then four Mandarin tones 1, 2, 3, 4, audibly distinct. |

**E. Chinese polyphonic characters in context (Vietnamese carrier)**

| # | Sentence | Expected |
| --- | --- | --- |
| 16 | Mình đến 银行 để đổi tiền. | 银行 yín**háng** (行 = háng, "bank"). |
| 17 | Chúng ta cùng 行走 trong công viên. | 行走 **xíng**zǒu (行 = xíng, "walk"). |
| 18 | Em bé 长大 rồi. | 长大 **zhǎng**dà (长 = zhǎng, grow). |
| 19 | Sợi dây này 长度 hai mét. | 长度 **cháng**dù (长 = cháng, length). |
| 20 | 重要 là quan trọng, còn 重新 là làm lại. | 重要 **zhòng**yào (zhòng); 重新 **chóng**xīn (chóng). |
| 21 | 好学 là thích học, còn 好看 là đẹp. | 好学 **hào**xué (hào, 4th); 好看 **hǎo**kàn (hǎo, 3rd). |
| 22 | 还书 là trả sách, còn 还有 là vẫn còn. | 还书 **huán**shū (huán); 还有 **hái**yǒu (hái). |

Additional cases are added when a rater's note finds a hole (e.g. 了 le vs liǎo in 了解, 都 dōu vs dū).

### 3.4 Evaluation: real audio, not transcripts

A transcript compares text; it cannot show "xuế" versus "xué" or a háng/xíng swap. All items are recorded as
real audio per model and judged by listeners.

**Primary: human rating.** At least 3 raters per language span type: one Mandarin-proficient listener for
every ZH span, one fluent-English listener for every EN span, one native Vietnamese listener for carrier
language. Blind to model, items shuffled. Per item, per foreign span, score 0-2 on each:

| Criterion | 0 | 1 | 2 |
| --- | --- | --- | --- |
| Correct language / phonemes (EN segmental, ZH initials-finals) | wrong language or substituted sound | mostly right, one audible slip | native-like |
| Tone / stress (ZH tone, EN word stress) | wrong tone or stress | one tone slightly off (incl. sandhi) | correct |
| No Vietnamese accent bleed (no added Vietnamese tone, syllable-timed rhythm) | strong | mild | none |
| No Hán-Việt substitution (ZH spans only) | span read as Hán-Việt | n/a | read as Mandarin |
| Polyphonic reading right (set E) | wrong reading | n/a | right reading |
| Join smoothness (the switch in and out, carrier tones resume) | stumble or restart | slight pause | smooth |

Also record the vendor's reported voice and style, and whether the style name was spoken aloud (the persona
forbids it).

**Secondary, optional (screening only): ASR-back per span.** Cut each foreign span by the transcript timing
and run recognition with that span's language fixed (Groq whisper via the existing `speech_asr` adapter, or
Azure). It reliably catches whole-word substitution (Hán-Việt reading transcribes to Vietnamese words,
"học tập" instead of "学习"), wrong-language synthesis and dropped words. **It cannot be the gate for tone
or polyphones**: ASR returns characters, not pinyin, and a háng/xíng swap can still transcribe to 银行 from
context. The repo's own Azure measurement also shows its Mandarin tone labels can be wrong
(`SPEAKING_AZURE_E2E_2026-09-23.md`: 任 as `ren 2`, 吗 as `ma 2`), so a reference-pinyin pronunciation
assessment is a hint (a lowered per-syllable score), not a verdict. Human rating wins any disagreement.

### 3.5 Pass gate

For the provider/model that proceeds: mean >= 1.7 of 2 on "language/phonemes", "tone/stress" and "no Hán-Việt"
over ZH spans; zero items with a Hán-Việt substitution; set E at least 5 of 7 polyphonic words right
(ASSUMPTION: thresholds proposed for the human to set); no item with a stumble on the join in more than 3 of
22. A model that fails after the per-span markup and pinyin hint of 3.2 is not adopted for ZH-in-VI.

## 4. Voice cost model (6.4)

### 4.1 Inputs and what is known

| Input | Value | Label |
| --- | --- | --- |
| Voice session rate, Gemini Live | ~0.036 USD per minute | PROVIDER-LIST-PRICE, unverified (`AGENT_SPEC` §41; source not given there) |
| Split into learner audio (input) and model audio (output) | unknown - needs test: the vendor's `usage` per modality from T1/T2. Do not invent a split | unknown |
| Text agent round | ~0.0009 USD per round (0.008 / 9) | MEASURED (`ORENA_AGENT_LIVE_8021_CHECKPOINT.md`) |
| Rounds per tool-backed voice turn | 2 | ASSUMPTION (one tool round + one answer round) |
| Share of voice minutes that carry a tool-backed turn (delegations per minute) | 0.3 / 0.5 / 0.8 (light / normal / heavy) | ASSUMPTION |
| Reconnect / retry overhead (re-sent context, replayed audio, re-asked turns) | 3% / 8% / 15% extra audio minutes | ASSUMPTION |
| Minutes per learner per day | 5 / 15 / 30 (30 is the spec's proposed daily cap) | ASSUMPTION (the cap is `AGENT_SPEC` §41) |
| TTS pre-render cache (`brief_ack` etc.) | cost unknown - needs test (TTS rate sheet); assumed ~0 per play | unknown |

"Per minute of learner audio" and "per minute of model audio" cannot be separately priced from the repo. The
single quoted rate is applied to wall-clock session minutes as an ASSUMPTION; section 4.3 says how to measure
the two (the spike records `audio_seconds_in/out`, the shape `VoiceUsage` already has).

### 4.2 Scenarios (computed on the table above)

Cost per session-minute = 0.036 x (1 + reconnect overhead) + delegations/min x 2 rounds x 0.00089 (rounded to
4 decimals).

| Scenario | Minutes/day | Voice rate incl. reconnect | Tool/text overhead per min | Total per min | Per learner-day | Per 30-day month |
| --- | --- | --- | --- | --- | --- | --- |
| Light | 5 | 0.0371 | 0.0005 | 0.0376 | 0.19 USD | 5.6 USD |
| Normal | 15 | 0.0389 | 0.0009 | 0.0398 | 0.60 USD | 17.9 USD |
| Heavy | 30 | 0.0414 | 0.0014 | 0.0428 | 1.28 USD | 38.5 USD |

All three rows are ASSUMPTION built on an unverified list price. Two cross-checks, both unverified: the spec's own
guess of 20 voice min/user/month at ~0.036 USD is 0.72 USD/month, one order below the "normal" row because
this proposal assumes daily use; and mode B adds the text-agent cost already measured above. The cost of
speech synthesis for supplied text in mode B (TTS rather than S2S) may differ from the S2S rate: unknown -
needs test T1 usage readout.

### 4.3 What turns this into MEASURED

- T1/T2 exports must keep the vendor `usageMetadata` per modality and per response; the runner converts to USD
  with a catalog entry added in a later slice (`pricing.py` has none: audio, per-minute and Live rates do not
  exist and an unknown model is "unpriced" by design).
- The average conversational minute is measured as: learner-speech seconds, model-speech seconds, silence
  seconds and tool rounds per minute, from T2 scripted dialogues; the 0.3/0.5/0.8 rates above are replaced by it.
- A voice session's reconnect overhead is measured from the T2 reconnect trials.

## 5. Slice 4 acceptance plan (6.5)

Each row is tested with real audio on the staging sandbox (the :8011 sandbox the lane may operate, or a
throwaway sandbox like `scripts/agent_live`), one worker, agent and voice flags on, production off. "Live"
rows need the credential gate and a per-run cost ceiling. Contract and unit tests run with the fake provider and
golden audio (spec D14: no real provider in CI).

| Area | Scenario | Pass criterion |
| --- | --- | --- |
| EN | English learner target, spoken questions (word meaning, a coaching question) | final transcript word error rate <= 10% on the scripted set (ASSUMPTION threshold); reply spoken in English; same segments as the typed twin of the question |
| ZH | Mandarin target, spoken questions | as above with character error rate <= 10%; Mandarin replies with correct tones on the section 3.3 ZH spans (3.5 gate) |
| Vietnamese interface | support language Vietnamese, Vietnamese speech | Vietnamese reply with address pair kept (`context.address`, e.g. chị/em), no style name spoken, no model/provider named (contract §10) |
| Code-switch | section 3.3 set | section 3.5 gate, rated on real audio |
| Interruption | barge-in 5 times mid-sentence | playback stops <= 400 ms after speech onset (ASSUMPTION; spike measures it); turn aborted server-side (no further tokens, no meter after abort beyond the tokens already issued); thread marks the cut; next turn does not assume the cut sentence was heard |
| Silence | no speech for the idle limit; and 6 s of silence mid-turn | no spurious turn from noise; the idle close is a non-claim line then text; a pause shorter than the settle window does not split the utterance |
| Noisy audio | recorded café/street noise at 3 levels | no turn started by noise alone in 3 of 3 noise-only clips; transcript error reported to the learner on low confidence rather than answering a hallucinated question (the agent asks to repeat) |
| Long utterance | 45 s learner utterance | not cut off; transcript complete; the turn fits `max_input_tokens_per_turn` (12,000) or is refused with a message, never silently truncated |
| Tool-backed answer | "Mình sai gì ở bài viết gần nhất?" / the pronunciation case | an `evidence` event precedes the cited segment; the spoken text equals the cleared text; no sentence claiming an error is audible before its evidence event; with the tool failing, the fixed unavailable line is spoken |
| Action confirmation | agent offers an action (e.g. save word) | the server's invitation sentence is spoken; the card appears; no mutation until the learner taps; the spoken "yes" does not mutate (unless Q3 is decided otherwise); no "I saved it" without `memory_update` |
| Language switch | learner changes learning language between turns | `409 target_language_mismatch` -> voice session closed, locale refreshed, new session opened in the new language; no reply in the stale language; a mid-sentence EN->ZH switch by the learner is transcribed correctly |
| Reconnect | kill the socket mid-turn, then at the 15-minute cap | text of the interrupted turn is complete in the thread; a new session opens within the reconnect budget (<= 2 automatic attempts); layer 1 + layer 3 reloaded, no audio history; after the budget, `voice_unavailable` and text only; never another vendor |
| Mobile | phone context with `hasTouch`/`isMobile`, EN/VI/ZH, light and dark (CLAUDE.md rule 6) | mic permission flow works; audio plays after a user gesture (autoplay policy); backgrounding the tab suspends cleanly and resumes or falls to text; the workspace is the viewport (rule 6b). UI belongs to the UI lane; this row verifies the contract works with it |
| Cost ceiling | a metered day | a live run stops at the human-approved ceiling (the bound computed before each send, retries included, R25); soft-limited account gets text, not voice; observed cost per minute is within 25% of the section 4 estimate or the estimate is replaced (ASSUMPTION threshold) |
| Latency | TTFA measured from end of speech | acknowledgement audio <= 1 s at the 90th percentile; first substantive audio <= text TTFS + first TTS chunk (the text median is 3.99 s MEASURED); both reported with median and 90th percentile over >= 20 turns per language. Whether 1 s must hold for substantive audio is Q1 |
| Privacy | one full session | zero audio bytes in logs, DB, files; no key or token in any log line or `repr` (existing test pattern: `test_the_ephemeral_token_never_prints`); the transcript is stored only where text turns are stored |
| Failure | vendor error mid-session | `error{voice_unavailable, text_only}`, the conversation continues in text; no other vendor called (E2E 11) |

Contract tests added in the slice (fake provider and golden WAV, no network): the voice session response
shape; `voice_state` ordering; evidence-before-audio ordering; abort cancels the speech queue; 404 when voice
is off; 409 on a language mismatch at session open; text parity (same utterance as text and as final
transcript yields the same events).

## 6. Production constraints

1. **Production stays hard-off.** `AGENT_ENABLED` already makes production never serve `/api/agent/*`
   (R9). Voice adds its own server flag, default off, which is also off whenever the agent is off, and the
   voice route returns 404 (the client treats absence as "no mic", as it treats an absent Orena). No voice
   code path is reachable on :8000 or :8010. The flag may be turned on only on the staging sandbox
   after the human's activation approval.
2. **An authoritative per-account quota is required before any public use.** `ratelimit.py` says plainly it is
   per process and best effort; with N workers a learner gets N times the limit and a restart forgets every
   window. For voice it is not a spending limit. Required before public voice: a per-account, cross-worker
   minute/turn quota read from durable state. R26 already says to propose counting from `usage_events`
   (`agent.turn`, `agent.tokens` per account and time window) before inventing storage; voice adds
   `agent.voice_seconds_in/out` there. The proposal for that counter is its own reviewed step (usage-event
   schema is not mine to extend silently). Until it exists, staging runs one worker and a human-set total.
3. **Budget is enforced by a counter, not by the limiter.** `budget_state: soft_limited` (contract §4) is for a
   learner over their quota: they get a short text reply and no voice vendor call (E2E 12).
4. **No raw audio stored** anywhere (contract §9, AGENT_SPEC §33.5). Durable learner audio needs its own privacy
   review (handoff). Vendor-side retention and training terms for the live API are unknown - needs a
   check by the human before any real learner uses it.
5. **Key never reaches the client**: one-use ephemeral tokens through `writing_coach/ai/credentials.py` and
   `platform.py` (AGENT_SPEC §33 / R6). Token and `connect` are never in a log line, error, or `repr`.
6. **No cross-vendor fallback** (R2); capability key change in Admin is the only way to change the vendor,
   and the activation of `conversational_speech` / `text_to_speech` (inert today) is itself a reviewed step.
7. **Independent architecture review** before any activation, per AGENTS.md section 1: a schema or usage-event change and
   the quota are the high-risk parts; the implementer does not self-approve.
8. **Provider calls** only under the live lock and a human-approved ceiling; never `docker compose down -v`,
   never 8000/8010/8011 volumes touched by a spike.

## 7. Open questions for the human

1. **Latency target.** E2E 10 says TTFA < 1 s. With the text agent's measured median of 3.99 s to first segment,
   mode B cannot meet that for substantive audio. Accept "acknowledgement < 1 s, answer when released"? Or
   require mode A (vendor model speaks) for tool-less turns, which weakens the claim gate on those turns?
2. **Mode.** Approve mode B (server-brain) as the Slice 4 default, with mode A only as a measured experiment?
3. **Can a spoken "yes" press a pending action card?** If yes, the UI lane and a contract version must say how
   (an explicit confirmation intent bound to the pending card id).
4. **Transcript review before send.** Send the final transcript automatically, or let the learner confirm or
   edit it first? (Affects latency and misrecognition errors in names, notes and writing claims.)
5. **Spoken-until marker.** Add to the contract (v6 candidate, from this slice) a way to say how far audio
   played when interrupted, or keep it client-only?
6. **`voice_style` set.** Map the spike's `warm_encourage` / `gentle_correct` / `slow_model` to the contract's
   enum, and decide whether a `slow_model` style (slow, precise model reading) is added to the enum.
7. **Test audio handling.** Where may the reviewers' recordings live during the matrix (outside the repo, deleted
   after rating)? Do the human and any listeners consent to being recorded for the test set?
8. **Credential gates.** Open Gemini Live for staging? Open OpenAI/Azure only if the Gemini Live result misses
   the section 3.5 gate? Who rates ZH and EN items (a native Mandarin listener is needed)?
9. **Budget.** Approve the 0.80 USD stop / 1.00 USD day ceiling for the first run, and the 30 minutes/user/day
   metering default (`AGENT_SPEC` §41) for staging.
10. **Voice identity.** Orena's one voice per vendor (`SpeakerProfile`, spike lists Gemini prebuilt voices such as
   Sulafat/Achird); who picks it, by listening to which languages?
11. **Pricing facts.** Who verifies the quoted per-minute rates (`AGENT_SPEC` §41 gives no source) before they
   become a catalog entry?

## 8. Not in this slice

- Any production enablement, any public or multi-worker rollout, any change to `docker-compose`, `.env.example`,
  CI, or shared files beyond what the lane already edits.
- The per-account quota implementation and any schema or `usage_events` change (a reviewed proposal comes first).
- Storing raw audio, durable learner audio, voice cloning, speaker identification, wake words, background listening.
- A separate "Voice Agent", a voice-only tool set, voice-only memory, or voice-only prompts.
- Mutating tools or any action executed by voice alone (contract: actions are taps; D6 backend mutation tools
  are out of scope).
- Pronunciation scoring through the agent (that is the Speaking lane's `pronunciation_evaluator` /
  `speech_asr`, reused as evidence only), and role-play/free-conversation content generation.
- Any Hán-Việt feature, Vietnamese-only pronunciation logic, or accent-conversion; a language-neutral span
  contract only.
- Switching provider because of a newer model; any automatic provider/vendor fallback.
- UI work (panel, mic states, dispatcher): UI lane on `codex/work`; this lane verifies the contract with its mock.
- Native mobile (`mobile/` is frozen).
- Running any live test: the section 2.3 matrix is a plan and waits for the human's credential gate and cost ceiling.
