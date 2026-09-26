# Speaking — pronunciation vertical slice (plan and architecture note)

> **For agentic workers:** executed inline on `feature/speaking` (human instruction, 2026-09-23).
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Speaking becomes a working vertical slice on its canonical frames — library, workspace,
recording, word detail, free talk — with pronunciation assessed through a provider seam whose first
implementation is Azure Speech Pronunciation Assessment.

**Architecture:** the browser records (existing recorder), sends audio + reference text + language to
`POST /api/speech/pronunciation`; the server validates, calls the configured
`SpeechPronunciationProvider`, and returns one provider-neutral result. The browser projects that
result onto the canonical `PronunciationResult` contract (`capabilities/pronunciation-result.js`) and
never reads a provider's own schema. Raw audio is transient: nothing but the normalized assessment is
kept (`speaking_attempts`, existing, no audio column).

**Tech stack:** FastAPI, `requests` (Azure REST short-audio endpoint), ffmpeg (existing PCM
normalizer), vanilla ES modules under `static/orena`, Node `.mjs` contract gates, pytest.

**Authorities read:** `AGENTS.md`, `CLAUDE.md`, `DESIGN_CONTRACT.md` (rules 30-48, 9, 26-29),
`CURRENT_HANDOFF.md`, `CURRENT_PRODUCT_STATE.yaml`, `UI_BACKEND_GAPS.md` (Speaking SP-1..11),
`docs/design/canonical-ui/screens/Orena-Speaking.dc.html` (frames: Speaking library, … mobile,
Speaking workspace, … mobile, Speaking · recording, Speaking · char detail, Speaking · free talk),
`data-contracts/PronunciationResult.json`. The design project itself could not be read
(`DesignSync` not authorized in this session); the cache was used, as the human's brief names it.

## Human decisions taken for this slice (2026-09-23)

1. **"Đạt" follows the provider's own miscue flag.** A reference word is *not passed* when the
   provider marks it (Azure `ErrorType` other than `None`: Mispronunciation, Omission, …).
   `passedCount` = reference words not flagged; `totalCount` = reference words. Orena sets no
   numeric threshold; raw scores are shown as numbers. The amber bar and the headline follow the
   same flag.
2. **Library content:** a dedicated Speaking catalogue (own file, empty until content is supplied)
   *and* a flow from Listening (published lessons with the `shadowing` mode). Chips exist only for a
   practice type some real item has.
3. **Review sandbox:** a separate container on **8013** mounting this worktree, with its own
   throwaway Postgres. 8000, 8010, 8011, 8012 and the shared volumes are not touched.
4. **Free talk** is rebuilt on its frame after the pronunciation flow, keeping the existing ASR and
   coaching plumbing.

## Audit summary (what exists, what is stale)

| Piece | State | Action |
| --- | --- | --- |
| `writing_coach/speech_pronunciation.py` | Provider protocol, Azure REST adapter, ffmpeg normalizer, demo provider | Keep; extend normalization (offset/duration, syllables, no-speech); `score_kind` `provider` → `measured`; default mode no longer `demo` |
| `writing_coach/speech_api.py` `/pronunciation` | Works, error mapping, bounded upload | Keep; add latency + operational log (no audio, no secret), `no_speech` category, `/status.pronunciation` |
| `speaking_attempts` (`/api/speech/attempts`) | Audio-free evidence store | Reuse for the assessment record |
| `capabilities/audio-recorder.js`, `mic-readiness.js` | Recorder with RNNoise, permission/level watch | Reuse unchanged |
| `ui/pronunciation-report.js` | D-065 "no score" renderer; refuses `score_kind: provider` (Azure could never render) | Retire; replaced by the canonical projection + workspace |
| `encounter.js` shadowing / read-aloud branch | Legacy practice panel | Delete; the line sheet opens the Speaking workspace at that line |
| `ui/speaking.js` landing + `voice-response.js` | Legacy (D-065) landing and free-response room | Landing → canonical library; free talk → canonical frame (task 7). `voice-response.js` stays for its other caller (Listening "speak about this moment" was the only one — removed with the shadowing branch; conversation keeps its own) |
| `scripts/test_m3_pronunciation_contract.mjs` | Stale: asserts the D-065 "sentence, not a scorecard" report and `score_kind === 'measured'`-only against a renderer the canonical frame replaced | Rewritten against `PronunciationResult` + provider seam (task 3) |
| `speaking_evaluator.py` thresholds (85/90/80) | Pre-existing, unapproved; feeds `highlights`/`next_steps` only | Left as is; the new UI does not read them; recorded as a gap |

## Normalized result (server → browser), additive

```text
provider            "azure-speech" | …        infrastructure; never drawn
score_kind          "measured" | "synthetic_demo"
language, locale    "en"|"zh", provider locale
reference_text      as assessed
recognized_text     what the provider heard (never used as a score)
pron_score, accuracy_score, fluency_score, completeness_score, prosody_score   0-100 | null
words[]             word, accuracy_score, error_type, offset_ms, duration_ms,
                    syllables[] {syllable, accuracy_score}, phonemes[] {phoneme, accuracy_score}
latency_ms          provider round trip
```

`capabilities/pronunciation-result.js` projects it onto `PronunciationResult`:
`overall = pron_score`, `accuracy`, `fluency`, `passedCount`/`totalCount` (decision 1),
`timingNote` (learner's speech span from word offsets vs the model line's span, only when both are
measured), `words[] {text, pinyin (from the lesson's own reading, never from the provider), score,
note (from the provider flag + weakest phoneme), toneTarget (tone numbers of the reference reading),
toneActual: []}`. `toneActual` stays empty: no provider in this slice measures pitch; a phoneme or
syllable score is never presented as a tone score.

## File map

- Modify `writing_coach/speech_pronunciation.py`, `writing_coach/speech_api.py`, `app.py` (router),
  `.env.example`, `compose.yaml` (default provider mode only).
- Create `writing_coach/speaking_library.py` + `writing_coach/content/speaking_catalog.v1.json`
  (empty catalogue, schema-checked) and route `GET /api/speaking/library`.
- Create `static/orena/capabilities/pronunciation-result.js` (projection),
  `static/orena/capabilities/speaking-take.js` (record → assess → keep lifecycle, stale guard),
  `static/orena/ui/speaking-workspace.js`, `static/orena/ui/speaking-library.js`,
  `static/orena/speaking.css`.
- Modify `static/orena/ui/speaking.js` (library + free talk), `static/orena/ui/encounter.js`
  (delete shadowing/read-aloud branch; route to the workspace), `static/orena/app.js`
  (route, shell), `static/orena/product/intent.js` (`line` param), `static/orena/infrastructure/api.js`,
  `static/orena/ui/reference.js` (copy, en/vi/zh), `templates/orena/index.html` (stylesheet).
- Delete `static/orena/ui/pronunciation-report.js` once nothing imports it.
- Tests: `tests/test_speech_pronunciation.py`, `tests/test_speech_pronunciation_api.py` (new),
  `tests/test_speaking_library.py` (new), `scripts/test_m3_pronunciation_contract.mjs` (rewritten),
  `scripts/test_speaking_workspace.mjs` (new).

## Tasks (each ends with tests, `git status`, a commit)

- [ ] **1. Architecture note + audit** — this file.
- [ ] **2. Provider seam + Azure adapter** — normalization of offsets/durations/syllables, no-speech
      category, `measured` kind, default mode (`azure` when key+region are set, else none; `demo`
      only when asked for, never in production), latency + log, `/status.pronunciation`. Tests:
      success EN, success ZH (syllables, no tone field), omission word, malformed, no-speech,
      timeout, 401 without leaking the key, invalid language/reference/empty audio, route returns
      no Azure keys.
- [ ] **3. Canonical projection** — `pronunciation-result.js` + rewritten `test_m3` gate: provider
      flag → passed, `-s` dropped visible through phonemes, missing optional fields, synthetic demo
      refused, EN and ZH, `toneActual` always empty.
- [ ] **4. Take lifecycle** — `speaking-take.js`: idle → recording → processing → result | error;
      too-short take refused before upload; cancel; a newer take or navigation discards an older
      answer; double-submit impossible; the assessment kept through `/api/speech/attempts`.
- [ ] **5. Workspace on its frame** — desktop two panes, phone single column, recording state,
      word detail (popover on a desk, sheet on a phone), in EN/VI/ZH; Listening's line sheet opens it.
- [ ] **6. Library** — `/api/speaking/library` (dedicated catalogue + Listening shadowing lessons) and
      the canonical library with the rail.
- [ ] **7. Free talk on its frame** — existing ASR/coaching, new composition.
- [ ] **8. Verification** — full CI-equivalent gate, browser on :8013 at 1920x1080 and 390x844 with
      touch, EN/VI/ZH, gaps and handoff updated.
