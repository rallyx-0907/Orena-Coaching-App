# Track 0 voice spike: Gemini Live

A spike, kept apart from the agent: nothing in `writing_coach/` imports it. It is a
local page for talking to Orena through the Gemini Live API and listening to the
result. It compares two models:

- `gemini-3.8-live`
- `gemini-2.5-flash-native-audio-preview-12-2025`

The page lists every Live model the key can open.

```bash
python scripts/voice_spike/server.py --gemini-env <.env holding GEMINI_API_KEY>
```

Then open <http://127.0.0.1:8790>, preferably wearing headphones.

**The key.** Only `GEMINI_API_KEY` is read from the env file. It stays in the server
process and goes to Google in a header. It is never sent to the page, printed or
logged. For each session the server mints a one-use ephemeral token (`v1beta/auth_tokens`),
which must open its session within 60 s and lasts 30 min. The page opens
`BidiGenerateContentConstrained?access_token=<token>`.

**The lock.** The server holds only the Gemini Live quota group's lock
(`live-gemini-live.lock`, see `scripts/agent_live/README.md`) while it runs. Text runs, which use a different
quota, do not wait for it. Stop the server with Ctrl+C when you are done.

**Nothing is stored.** No audio is kept: the microphone is streamed and playback is
dropped as it ends. The page keeps only numbers and transcripts in memory, and
exports them as JSON when you ask it to.

**Persona.** The system instruction sets up Orena as a warm, clever friend: xưng
mình–bạn in Vietnamese, I/you in English and 我/你 in Chinese, answering in the
learner's language with short turns. It chooses a `voice_style` for each sentence
from `neutral_explain`, `warm_encourage`, `gentle_correct`, `celebrate` and
`slow_model`, without saying the style's name. In the "Đọc theo voice_style" mode
you type tagged sentences, such as `[gentle_correct] Chỗ này đọc là xué nhé.`, and
the model reads each one in its style.

**What the page measures for each model turn.**

| Measure | How it is taken |
| --- | --- |
| Time to first audio | From the last loud moment of your speech (the page's own mic level), or from Send for a typed line, to the first audio chunk. |
| Interruption | Whether the server sent `interrupted`, and the time from when you started speaking over Orena to that signal, when playback stops. |
| Languages | The languages in Orena's output transcript (`vi`, `en`, `zh`, or a mix such as `en·zh`). |
| Quality | A 1-5 score and a note that you enter per turn, e.g. pronunciation, tone, voice. |
