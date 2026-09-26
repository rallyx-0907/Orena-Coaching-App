/* Pronunciation, provider to screen (rewritten 2026-09-23).

   The gate this replaces asserted the D-065 report: "a sentence, not a scorecard" - no number, no
   dimension bars - and a renderer that accepted only `score_kind: 'measured'` while the Azure
   adapter said `provider`, so a real result could never be drawn. D-066 made the Canonical UI
   Baseline the authority, and its Speaking workspace draws a score ring, the pronunciation and
   fluency figures, a passed count and one row per word (`PronunciationResult`). The test now holds
   that contract and the rules around it: the provider's own miscue flag decides "passed" (human
   decision 2026-09-23), a phoneme-level loss stays visible when the word reads whole, nothing
   unmeasured becomes a figure, a synthetic demo is never a measurement, and no tone is invented. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const api = read('static/orena/infrastructure/api.js');
const speechApi = read('writing_coach/speech_api.py');
const provider = read('writing_coach/speech_pronunciation.py');
const dockerfile = read('Dockerfile');

// The browser talks to Orena's route only; the provider is the server's.
assert.match(api, /assessPronunciation:/);
assert.match(api, /\/api\/speech\/pronunciation/);
assert.match(speechApi, /@router\.post\("\/pronunciation"\)/);
assert.match(provider, /class SpeechPronunciationProvider\(Protocol\)/);
assert.match(provider, /class AzureSpeechPronunciationProvider/);
assert.match(provider, /Pronunciation-Assessment/);
assert.match(provider, /pcm_s16le/);
assert.match(provider, /zh-CN/);
assert.match(provider, /en-US/);
assert.match(provider, /AZURE_PRONUNCIATION_ENABLE_PROSODY/);
assert.match(provider, /score_kind="measured"/);
assert.match(provider, /mode = configured or \("azure" if azure_ready else "none"\)/, 'no synthetic scores by default');
assert.match(dockerfile, /ffmpeg/);

const { pronunciationView, isMeasurement, toneOf, isFlagged } = await import('../static/orena/capabilities/pronunciation-result.js');

/* English: the provider flags one word and omits another; "cats" reads whole and is not flagged,
   but its final /s/ scored 4. */
const english = {
  score_kind: 'measured',
  language: 'en',
  reference_text: 'Two cats slept.',
  pron_score: 70.4,
  accuracy_score: 72,
  fluency_score: 80,
  completeness_score: 67,
  prosody_score: null,
  words: [
    { word: 'Two', accuracy_score: 98, error_type: 'None', offset_ms: 500, duration_ms: 300, phonemes: [{ phoneme: 't', accuracy_score: 99 }] },
    { word: 'cats', accuracy_score: 61, error_type: 'None', offset_ms: 820, duration_ms: 400, phonemes: [{ phoneme: 'k', accuracy_score: 95 }, { phoneme: 's', accuracy_score: 4 }] },
    { word: 'slept', accuracy_score: 0, error_type: 'Omission', offset_ms: null, duration_ms: null },
    { word: 'um', accuracy_score: null, error_type: 'Insertion' },
  ],
};
assert.equal(isMeasurement(english), true);
const en = pronunciationView(english, { language: 'en', modelSpanMs: 1000 });
assert.equal(en.overall, 70);
assert.equal(en.accuracy, 72);
assert.equal(en.fluency, 80);
assert.equal(en.prosody, null, 'an unmeasured dimension is not a figure');
assert.equal(en.totalCount, 3, 'an inserted word is not a reference word');
assert.equal(en.passedCount, 2, 'passed = reference words the provider did not flag');
const cats = en.words.find((word) => word.text === 'cats');
assert.equal(cats.flagged, false);
assert.deepEqual(cats.weakest, { label: 's', score: 4 }, 'the phoneme loss survives when the word reads whole');
assert.equal(en.words.find((word) => word.text === 'slept').flagged, true);
assert.deepEqual(en.timing, { learnerMs: 720, modelMs: 1000, deltaMs: -300 });
assert.equal(en.words[0].pinyin, '', 'an English word has no invented reading');

/* Chinese: readings come from the lesson, tones from those readings; nothing measured a tone. */
const chinese = {
  score_kind: 'measured',
  language: 'zh',
  reference_text: '我们想要。',
  pron_score: 81,
  accuracy_score: 80,
  fluency_score: 78,
  completeness_score: 100,
  words: [
    { word: '我们', accuracy_score: 96, error_type: 'None', syllables: [{ syllable: 'wo3', accuracy_score: 96 }, { syllable: 'men5', accuracy_score: 94 }] },
    { word: '想', accuracy_score: 52, error_type: 'Mispronunciation', syllables: [{ syllable: 'xiang3', accuracy_score: 52 }] },
    { word: '要', accuracy_score: 94, error_type: 'None' },
  ],
};
const readings = [{ char: '我', pinyin: 'wǒ' }, { char: '们', pinyin: 'men' }, { char: '想', pinyin: 'xiǎng' }, { char: '要', pinyin: 'yào' }];
const zh = pronunciationView(chinese, { language: 'zh', readings });
assert.deepEqual(zh.words.map((word) => word.pinyin), ['wǒ men', 'xiǎng', 'yào']);
assert.deepEqual(zh.words.map((word) => word.toneTarget), [[3, 5], [3], [4]]);
assert.ok(zh.words.every((word) => Array.isArray(word.toneActual) && word.toneActual.length === 0), 'no tone is measured, so none is shown');
assert.deepEqual(zh.words[1].weakest, { label: 'xiang3', score: 52 });
assert.equal(zh.passedCount, 2);
assert.equal(zh.timing, null, 'no word timing, no timing note');
assert.deepEqual(pronunciationView(chinese, { language: 'zh', readings: readings.slice(1) }).words.map((w) => w.pinyin), ['', '', ''], 'a reading that does not align is not used');
assert.equal(toneOf('lǜ'), 4);
assert.equal(toneOf('de'), 5);

/* Not a measurement: demo, transcript only, missing fields, nothing at all. */
const demo = { provider: 'demo-synthetic', score_kind: 'synthetic_demo', pron_score: 76, accuracy_score: 74, words: [{ word: 'hello', accuracy_score: 84, error_type: 'SyntheticDemo' }] };
const demoView = pronunciationView(demo);
assert.equal(demoView.measured, false);
assert.equal(demoView.synthetic, true);
assert.equal(demoView.overall, 0, 'demo values are never shown');
assert.deepEqual(demoView.words, []);
assert.equal(isMeasurement({ recognized_text: 'hello' }), false, 'a transcript is not a score');
assert.equal(isMeasurement({ score_kind: 'measured' }), false, 'no dimension, no measurement');
assert.equal(isMeasurement(null), false);
const sparse = pronunciationView({ score_kind: 'measured', accuracy_score: 55, words: [{ word: 'hi' }] });
assert.equal(sparse.overall, 55, 'the overall falls back to accuracy when the provider gave no overall');
assert.equal(sparse.fluency, 0);
assert.equal(sparse.fluencyMeasured, false);
assert.equal(sparse.words[0].scoreMeasured, false);
assert.equal(isFlagged({ error_type: 'None' }), false);
assert.equal(isFlagged({}), false);

console.log('M3 pronunciation contract (PronunciationResult): PASS');
