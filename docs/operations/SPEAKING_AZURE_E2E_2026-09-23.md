# Speaking — Azure Pronunciation Assessment, measured end to end (2026-09-23)

## Governance

Purpose: the evidence behind the Speaking lane's provider decisions: what Azure actually returns
through Orena's own route, and how far it goes for Mandarin tones. Authority: measurement only; the
decisions it informs are the human's (D-084, and the SpeechSuper question below). Change when the
provider, its configuration or the measurement is redone. Never store a key, a region value, raw
provider JSON or learner audio here.

## How it was run

- Sandbox `orena-speaking-web` on :8013 (branch `feature/speaking`), its own throwaway Postgres.
- Credentials: the repository's convention - `AZURE_SPEECH_KEY` / `AZURE_SPEECH_REGION` in the main
  checkout's `.env`, the file `compose.yaml` reads. Only the speech variables were passed into the
  sandbox's environment; nothing was printed or copied. `PRONUNCIATION_PROVIDER` is unset there, so
  the provider is chosen by the auto rule (Azure when its key and region exist).
- Audio: real human speech, lines cut from the published Listening clips (Wikimedia Commons,
  public domain / CC) with ffmpeg and encoded as Opus/WebM, the browser's own format. Each case was
  posted to `POST /api/speech/pronunciation` exactly as the browser posts it; only the normalized
  answer was read.
- Locales: `en-US`, `zh-CN`. Prosody off (the separately charged add-on).

## English

| Case | Overall | Accuracy | Fluency | Completeness | What the words said |
| --- | --- | --- | --- | --- | --- |
| Native line, reference as said ("Anna, do you have a pen?") | 98.6 | 98 | 99 | 100 | every word 94-100, none flagged; offsets and durations present |
| Native line with the next speaker's start caught in the cut | 73.2 | 98 | 56 | 100 | the extra words came back as `Insertion`; fluency fell, accuracy did not |
| Audio of line 2 against the text of line 1 | 36.2 | 50 | 27 | 50 | `Omission` for the unsaid words, `Mispronunciation` for "you" (11) |
| Reference says "two **pens**", audio says "a pen" | 66.4 | 85 | 53 | 88 | "pens" flagged `Mispronunciation` 18, phonemes /n/ 0 and /z/ 0; "two" was **not** flagged (80) though never said |

Latency (provider round trip) 1.0-1.4 s for a 2-4 s line.

## Mandarin

Native lines, reference as said: 98.8, 92.4, 96.4 (lines cut cleanly); 85.4 and 75.8 where the
clip's segment ended before the last character (that character came back `Omission`). zh-CN
returns no `Syllables`; each word carries one `Phonemes` entry per syllable labelled with the
**reference** pinyin and tone digit (`shi 4`, `mei 3`), scored 0-100. Latency 0.45-1.2 s.

### Tone probe

One native take of 你也是美国人吗 (and one of 他们是谁), assessed against a reference with one
character swapped for another of the same syllable and a different tone. The audio's tone then
disagrees with the reference's, which is what a learner's wrong tone produces.

| Swap (said → expected) | That syllable's score | Flagged by Azure |
| --- | --- | --- |
| 是 shì → 时 shí (4 → 2) | 6 | yes, `Mispronunciation` |
| 也 yě → 叶 yè (3 → 4) | 28 | yes, `Mispronunciation` |
| 国 guó → 过 guò (2 → 4) | 53 | no |
| 你 nǐ → 泥 ní (3 → 2) | 60 | no |
| 美 měi → 没 méi (3 → 2) | 71 | no |
| 吗 ma → 妈 mā (neutral → 1) | 76 | no |
| 人 rén → 任 rèn (2 → 4) | 100 | no - Azure labelled 任 as `ren 2`, so it expected the tone that was said |

**What this measures.** A tone that disagrees with the reference lowers that syllable's score in 6
of 7 cases, but Azure flags it in only 2 of 7; the commonest learner confusion (3 ↔ 2) is scored
60-71 and not flagged. Its own tone labels can be wrong (任 as `ren 2`, the particle 吗 as `ma 2`
rather than neutral). Azure returns no pitch contour. So, under D-084 ("passed" is the provider's
flag), most tone errors would read as passed with a lowered score; the lowered syllable is visible
in the word detail. Whether that is enough, or a Mandarin tone provider (SpeechSuper) is needed, is
the human's decision; nothing was added.

## Silence

0.8 s of silence came back `Success` with every reference word `Omission` and every score 0. The
adapter now treats "every reference word omitted" as no speech (`pronunciation_no_speech`), so the
learner is asked to say it again instead of being shown a score of 0.

## Unscripted (free talk)

The same REST endpoint with no `ReferenceText` and `EnableMiscue` off assesses free speech: a
Mandarin take returned pronunciation 83.8, accuracy 91, fluency 79, and no completeness (there is
nothing to be complete against; the adapter returns it as absent). Through the browser, free talk
ran six times (desk and phone; zh/en, zh/vi, en/zh): Groq transcription, Azure unscripted
(fluency 77-89, pronunciation 81-92) and Gemini coaching, every call 200. Grammar and vocabulary are
0 and there is no overall (D-076).

## Through the browser

The Speaking workspace was driven in Chrome with the fake microphone fed with native speech cut from
the published Listening clips, nothing intercepted: six scripted runs (desk 1920 and phone 390 with
touch, three language pairs) scored 96-99 with 6/6 passed, reached the word detail, the comparison
with the model (measured waveforms and contours), shadowing (lag 0.5-0.6 s) and the lesson summary.
A shadow take restarted twice mid-way sent one assessment, not three. The results and the frame
measurements are in `docs/project/UI_BACKEND_GAPS.md`, "Speaking, the re-pinned frames measured and
run against Azure".

## Not measured here

Prosody (off), long takes near the 60 s limit, noisy rooms, and real learners' non-native speech:
every take above is a native speaker.
