/* Gate for Compare With Model's pure data mapping (static/orena/screens/compare/model.js).
   Imports only DOM-free modules. The same real (built-from-serializer, no speech provider in this
   sandbox) `score_kind:"measured"` shape `scripts/test_orena_screen_speak.mjs` uses, and the real
   pitch pipeline (`capabilities/audio-analysis.js`) fed a synthetic tone - a measurement of a
   signal made here, never a canned contour. */
import assert from 'node:assert/strict';
import { wordPitchLines, wordPages } from '../static/orena/screens/compare/model.js';

// Pitch is scoped to the provider's real word interval, never apportioned by word length.
const pitch = { contour: [{ t: 0, st: 1 }, { t: .2, st: 2 }, { t: .4, st: 3 }, { t: .6, st: 4 }] };
assert.deepEqual(wordPitchLines(pitch, { offsetKnown: false }), []);
assert.deepEqual(wordPitchLines(null, { offsetKnown: true, offsetMs: 100, durationMs: 300 }), []);
assert.ok(wordPitchLines(pitch, { offsetKnown: true, offsetMs: 100, durationMs: 300 }).length);
const pageWords = ['one', 'two', 'three', 'four', 'five'].map((text, index) => ({text, index}));
assert.deepEqual(wordPages(pageWords, 250, 'en').map(page => page.map(word => word.index)), [[0,1],[2,3],[4]]);
assert.deepEqual(wordPages(pageWords, 80, 'zh').map(page => page.length), [1,1,1,1,1]);
import {
  ringColor, scoreLabelKey, headlineKey, wordStatus, statusTone, tileMinWidth, wordDetailFor, defaultWordIndex,
  chipsFor, metricLineFor, axisFor, CHART, chartLines, hasVoice, wordBands, PLAYBACK_MODES, PLAYBACK_SPEEDS, nextSpeed, playPlan, pillsFor, toneKey,
} from '../static/orena/screens/compare/model.js';
import { pronunciationView } from '../static/orena/capabilities/pronunciation-result.js';
import { pitchTrack, contour } from '../static/orena/capabilities/audio-analysis.js';
import { viewOfTake } from '../static/orena/product/take-store.js';

const RESULT = {
  score_kind: 'measured', mode: 'scripted', reference_text: 'Could I get a coffee, please?',
  recognized_text: 'Could I get a coffee please',
  pron_score: 82, accuracy_score: 80, fluency_score: 88, completeness_score: 95, prosody_score: null,
  words: [
    { word: 'Could', accuracy_score: 92, error_type: 'None', offset_ms: 0, duration_ms: 300, phonemes: [], syllables: [] },
    { word: 'coffee', accuracy_score: 52, error_type: 'Mispronunciation', offset_ms: 780, duration_ms: 420, phonemes: [{ phoneme: 'k', accuracy_score: 80 }, { phoneme: 'f', accuracy_score: 40 }], syllables: [] },
    { word: 'please', accuracy_score: 88, error_type: 'None', offset_ms: 1220, duration_ms: 300, phonemes: [], syllables: [] },
  ],
};
const view = pronunciationView(RESULT, { language: 'en', readings: [], modelSpanMs: 1600 });
const rich = (result, options = {}) => ({ ...pronunciationView(result, { language: 'en', ...options }), reduced: false, words: pronunciationView(result, { language: 'en', ...options }).words.map((w) => ({ ...w, scoreKnown: true })) });

/* --- The component's own colour rules: the ring (80 / 60), the label (90 / 80 / 65) --- */
assert.equal(ringColor(80), 'var(--green)');
assert.equal(ringColor(79), 'var(--amber)');
assert.equal(ringColor(60), 'var(--amber)');
assert.equal(ringColor(59), 'var(--red)');
assert.equal(scoreLabelKey(90), 'labelExcellent');
assert.equal(scoreLabelKey(89), 'labelVeryGood');
assert.equal(scoreLabelKey(80), 'labelVeryGood');
assert.equal(scoreLabelKey(65), 'labelGood');
assert.equal(scoreLabelKey(64), 'labelKeepGoing');
assert.equal(headlineKey(95), 'headlineNatural');
assert.equal(headlineKey(85), 'headlineClear');
assert.equal(headlineKey(70), 'headlineUnderstandable');
assert.equal(headlineKey(10), 'headlineKeepPractising');

/* --- wordStatus: the assessment's own score and flag, never a verdict about the audio --- */
assert.equal(wordStatus({ score: 92, scoreKnown: true, flagged: false }), 'ok');
assert.equal(wordStatus({ score: 92, scoreKnown: true, flagged: true }), 'weak', 'a flagged word is never better than "close"');
assert.equal(wordStatus({ score: 70, scoreKnown: true, flagged: false }), 'weak');
assert.equal(wordStatus({ score: 52, scoreKnown: true, flagged: true }), 'wrong');
assert.equal(wordStatus({ score: 0, scoreKnown: true, flagged: true, errorType: 'Omission' }), 'unclear', 'the provider heard nothing there');
assert.equal(wordStatus({ score: null, scoreKnown: false, flagged: true }), 'weak', 'a reopened word has only the flag');
assert.equal(wordStatus({ score: null, scoreKnown: false, flagged: false }), 'ok');
assert.equal(statusTone('wrong').pillKey, 'statusNeedsWork');
assert.equal(statusTone('unclear').pillKey, 'statusUnclear');
assert.equal(statusTone('nope').pillKey, 'statusGood', 'an unknown status reads as the plain one');

/* --- tileMinWidth: the component's own `minW`, wider for Han characters, never under 116 --- */
assert.equal(tileMinWidth('I', 'en'), 116);
assert.equal(tileMinWidth('extraordinarily', 'en'), 15 * 9 + 26);
assert.equal(tileMinWidth('我', 'zh'), 116);
assert.equal(tileMinWidth('你好吗你好吗', 'zh'), 6 * 24 + 26);

/* --- chipsFor: rule 40 - prosody was not returned (null), so no prosody chip is fabricated --- */
{
  assert.deepEqual(chipsFor(pronunciationView(null)), [], 'nothing measured yet: no chips at all');
  const chips = chipsFor(view);
  assert.ok(!chips.some((chip) => chip.key === 'chipProsody'), 'prosody_score was null - never a fabricated chip');
  const clear = chips.find((chip) => chip.key === 'chipUnclear');
  assert.deepEqual(clear.params, { n: 1 });
  assert.equal(clear.kind, 'bad');
  const pace = chips.find((chip) => chip.key.startsWith('chipPace'));
  assert.ok(pace, 'the line has real word timings, so a pace chip is built from them');
  assert.equal(pace.key, 'chipPaceFaster', 'the learner spoke for 1.52 s against the model line: 0.1 s faster');
  assert.equal(pace.kind, 'ok', 'within half a second of the model is not a warning');
  const clean = chipsFor(pronunciationView({ ...RESULT, words: RESULT.words.map((w) => ({ ...w, error_type: 'None' })), prosody_score: 64 }, { language: 'en', modelSpanMs: 1520 }));
  assert.equal(clean[0].key, 'chipClear');
  assert.equal(clean[0].kind, 'ok');
  assert.ok(clean.some((chip) => chip.key === 'chipPaceSame'), 'the same span reads as the same pace');
  assert.deepEqual(clean.find((chip) => chip.key === 'chipProsody'), { kind: 'bad', key: 'chipProsody', params: { n: 64 } }, 'a measured prosody under 70 is flagged');
}

/* --- metricLineFor / axisFor: each number only when it is known --- */
{
  const line = metricLineFor(view);
  assert.deepEqual(line.parts.map((part) => `${part.key}:${part.value}`), ['metricAccuracy:80', 'metricFluency:88', 'metricCompleteness:95']);
  assert.equal(line.speechS, 1.5);
  const unmeasured = metricLineFor(pronunciationView({ ...RESULT, fluency_score: null }, { language: 'en' }));
  assert.ok(!unmeasured.parts.some((part) => part.key === 'metricFluency'), 'an unmeasured metric is left out of the line, not shown as 0');
  assert.equal(unmeasured.speechS, null, 'no model span, no speech seconds');
  assert.deepEqual(metricLineFor(pronunciationView(null)), { parts: [], speechS: null });
  assert.deepEqual(axisFor(view), { modelS: '1.6', youS: '1.5' });
  assert.equal(axisFor(pronunciationView(RESULT, { language: 'en' })), null, 'no model span: no "Model x s" claim');
}

/* --- wordDetailFor: the full shape carries a real score, the sounds and the timing --- */
{
  const detail = wordDetailFor(rich(RESULT, { modelSpanMs: 1600 }), 1);
  assert.equal(detail.text, 'coffee');
  assert.equal(detail.scoreKnown, true);
  assert.equal(detail.score, 52);
  assert.equal(detail.status, 'wrong');
  assert.equal(detail.tone.ink, 'var(--red)');
  assert.deepEqual(detail.weakest, { label: 'f', score: 40 });
  assert.deepEqual(detail.sounds, [{ label: 'k', score: 80 }, { label: 'f', score: 40 }]);
  assert.equal(detail.offsetKnown, true);
  assert.equal(detail.offsetMs, 780);
  assert.equal(detail.toneTarget, null, 'an English word has no tone');
}
assert.equal(wordDetailFor(view, 99), null);

/* --- wordDetailFor for a Chinese word: the tone of the lesson's own reading --- */
{
  const zh = pronunciationView(
    { score_kind: 'measured', reference_text: '我很好', pron_score: 90, accuracy_score: 90, fluency_score: 90, completeness_score: 100, words: [{ word: '我', accuracy_score: 80, error_type: 'None', offset_ms: 0, duration_ms: 300 }] },
    { language: 'zh', readings: [{ pinyin: 'wǒ' }, { pinyin: 'hěn' }] },
  );
  // Three characters but two readings: the lesson's reading cannot be aligned to the line, so the
  // word gets no reading - never somebody else's.
  assert.equal(wordDetailFor(zh, 0).pinyin, '');
  const placed = pronunciationView(
    { score_kind: 'measured', reference_text: '我', pron_score: 90, accuracy_score: 90, fluency_score: 90, completeness_score: 100, words: [{ word: '我', accuracy_score: 80, error_type: 'None', offset_ms: 0, duration_ms: 300 }] },
    { language: 'zh', readings: [{ pinyin: 'wǒ' }] },
  );
  const detail = wordDetailFor(placed, 0);
  assert.equal(detail.pinyin, 'wǒ');
  assert.equal(detail.toneTarget, 3);
  assert.equal(toneKey(detail.toneTarget), 'tone3');
  assert.equal(toneKey(5), 'tone5');
  assert.equal(toneKey(0), 'tone5', 'an unmarked syllable reads as neutral');
}

/* --- A reopened older attempt (D-076's own reduction) never fabricates a numeric score --- */
{
  const reopened = viewOfTake({ id: 'old', overall: 82, words: [{ text: 'Could', flagged: false, offsetMs: 0, durationMs: 300 }, { text: 'coffee', flagged: true, offsetMs: 780, durationMs: 420 }] });
  const passed = wordDetailFor(reopened, 0);
  assert.equal(passed.scoreKnown, false);
  assert.equal(passed.score, null, 'never a guessed number standing in for the lost score');
  assert.equal(passed.status, 'ok');
  assert.equal(wordDetailFor(reopened, 1).status, 'weak');
  assert.deepEqual(wordDetailFor(reopened, 1).sounds, [], 'no sound scores were kept');
  const chips = chipsFor(reopened);
  assert.equal(chips[0].key, 'chipUnclear', 'one of two words was flagged');
  assert.ok(!chips.some((chip) => chip.key.startsWith('chipPace')), 'no timing was kept, so no pace chip');
  assert.equal(metricLineFor(reopened).parts.length, 0 + (reopened.fluencyMeasured ? 1 : 0), 'no accuracy, fluency or completeness survived');
}

/* --- defaultWordIndex: the first word that is not fine opens; nothing wrong opens the first --- */
{
  assert.equal(defaultWordIndex(pronunciationView(null)), null);
  assert.equal(defaultWordIndex(rich(RESULT)), 1, '"coffee" is the first word that is not fine');
  const clean = rich({ ...RESULT, words: RESULT.words.map((word) => ({ ...word, error_type: 'None', accuracy_score: 95 })) });
  assert.equal(defaultWordIndex(clean), 0, 'nothing wrong: the first word is opened, as the component\'s own defSel does');
}

/* --- pillsFor: oldest first, the crown only when there is more than one attempt --- */
{
  const takes = [{ id: 'c', overall: 91 }, { id: 'b', overall: 68 }, { id: 'a', overall: 60 }];
  const pills = pillsFor(takes, 'b');
  assert.deepEqual(pills.map((p) => p.id), ['a', 'b', 'c']);
  assert.deepEqual(pills.map((p) => p.n), [1, 2, 3]);
  assert.deepEqual(pills.map((p) => p.crown), [false, false, true]);
  assert.deepEqual(pills.map((p) => p.active), [false, true, false]);
  assert.equal(pillsFor([{ id: 'x', overall: 50 }], 'x')[0].crown, false, 'a lone attempt is not best of anything');
  assert.equal(pillsFor([{ id: 'x' }], 'x')[0].score, null, 'an unknown score is not drawn as 0');
}

/* --- playback: the four modes, the speed cycle, and what plays when a part is missing --- */
assert.deepEqual([...PLAYBACK_MODES], ['model_then_you', 'word_by_word', 'model_only', 'you_only']);
assert.deepEqual([...PLAYBACK_SPEEDS], [0.75, 1, 1.25]);
assert.equal(nextSpeed(0.75), 1);
assert.equal(nextSpeed(1), 1.25);
assert.equal(nextSpeed(1.25), 0.75);
assert.deepEqual(playPlan('model_then_you', { hasTake: true, hasWords: true }), ['model', 'you']);
assert.deepEqual(playPlan('model_then_you', { hasTake: false, hasWords: true }), ['model'], 'no recording of this attempt: only the model plays');
assert.deepEqual(playPlan('you_only', { hasTake: false, hasWords: true }), [], 'nothing of yours to play');
assert.deepEqual(playPlan('model_only', { hasTake: false, hasWords: false }), ['model']);
assert.deepEqual(playPlan('word_by_word', { hasTake: true, hasWords: true }), ['words']);
assert.deepEqual(playPlan('word_by_word', { hasTake: true, hasWords: false }), ['model', 'you'], 'no word timing: the whole line, not a guess at boundaries');

/* --- The chart: a real pitch track of a real (synthetic) signal, drawn as polylines --- */
{
  const rate = 16_000;
  const seconds = 1.2;
  const samples = new Float32Array(rate * seconds);
  for (let i = 0; i < samples.length; i++) {
    const t = i / rate;
    // 0.2 s of silence, then a glide from 150 Hz to 220 Hz.
    samples[i] = t < 0.2 ? 0 : 0.5 * Math.sin(2 * Math.PI * (150 + ((t - 0.2) / 1.0) * 70) * t);
  }
  const points = contour(pitchTrack(samples, rate));
  assert.equal(hasVoice({ contour: points }), true, 'a voiced signal has voiced frames');
  assert.equal(hasVoice({ contour: points.map((p) => ({ t: p.t, st: null })) }), false, 'a take of silence draws no line');
  assert.equal(hasVoice(null), false);
  const whole = chartLines(points, { to: seconds });
  assert.ok(whole.length >= 1, 'one polyline per voiced run');
  const xs = whole.flatMap((run) => run.split(' ').map((pair) => Number(pair.split(',')[0])));
  assert.ok(Math.min(...xs) >= 0 && Math.max(...xs) <= CHART.width, 'inside the plot area');
  const wide = chartLines(points, { to: seconds, width: 680 });
  assert.ok(Math.max(...wide.flatMap((run) => run.split(' ').map((pair) => Number(pair.split(',')[0])))) > CHART.width, 'a wider plot scales the same contour');
  const word = chartLines(points, { from: 0.3, to: 0.7 });
  assert.ok(word.length >= 1, 'a word\'s own window of the take');
  assert.deepEqual(chartLines([], {}), []);
}

/* --- wordBands: where the words the provider did not pass sit in the take --- */
{
  const bands = wordBands(rich(RESULT), 2);
  assert.equal(bands.length, 1, 'only "coffee" is not fine');
  assert.equal(bands[0].status, 'wrong');
  assert.ok(Math.abs(bands[0].from - 0.39) < 1e-9 && Math.abs(bands[0].to - 0.6) < 1e-9, 'offset and duration over the take\'s length');
  assert.deepEqual(wordBands(rich(RESULT), 0), [], 'no audio length, no bands');
}

console.log('test_orena_screen_compare.mjs: Compare With Model data mapping - real audio-analysis pipeline, rule 40 throughout (no invented prosody chip, no invented reduced-attempt score, no unmeasured model timing): PASS');

/* D-139 HD-5 / HD-7 / Attempt History review: IPA only from provider sounds, the embedded history card's
   figures, and an attempt only the account remembers reviewed from what it kept. */
{
  const { ipaByStart, historyFor, deltaOf } = await import('../static/orena/screens/compare/model.js');
  const { placeWords } = await import('../static/orena/product/speaking-line.js');
  const { attemptRow, viewOfEvidence, reviewableAttempts } = await import('../static/orena/product/speaking-history.js');
  const assert = (await import('node:assert/strict')).default;
  const view = { words: [{ text: 'big', phonemes: [{ label: 'b' }, { label: 'ɪ' }, { label: 'ɡ' }] }, { text: 'bang', phonemes: [] }] };
  assert.deepEqual([...ipaByStart([view], 'big bang', 'en', placeWords)], [[0, 'bɪɡ']], 'only words the provider gave sounds for');
  assert.equal(ipaByStart([view], 'big bang', 'zh', placeWords).size, 0, 'Chinese keeps pinyin, never provider sounds');
  assert.equal(ipaByStart([{ words: [{ text: 'big', phonemes: [] }] }], 'big', 'en', placeWords).size, 0, 'no sounds anywhere: no IPA row');
  assert.deepEqual(deltaOf(90, 86), { text: '+4', tone: 'var(--green)', zero: false });
  assert.equal(deltaOf(null, 86).text, '');
  const row = attemptRow({ id: 'a1', created_at: '2026-10-01T10:00:00Z', dimensions: { pronunciation: 80, fluency: 90 }, provenance: { pronunciation: 'azure', fluency: 'azure' },
    transcript_text: 'big bang', evidence: { pronunciation: { score_kind: 'measured', accuracy_score: 82, completeness_score: 100, words: [
      { word: 'big', accuracy_score: 70, error_type: 'Mispronunciation', phonemes: [{ phoneme: 'b', accuracy_score: 90 }, { phoneme: 'ɪ', accuracy_score: 50 }] },
      { word: 'bang', accuracy_score: 95, error_type: 'None', phonemes: [] }] } } });
  const kept = viewOfEvidence(row);
  assert.equal(kept.words[0].flagged, true);
  assert.deepEqual(kept.words[0].weakest, { label: 'ɪ', score: 50 });
  assert.equal(kept.words[0].offsetKnown, false, 'word timing was never stored');
  assert.equal(kept.heard, 'big bang');
  assert.equal(attemptRow({ id: 'x', provenance: { pronunciation: 'stub-for-verification' }, evidence: { pronunciation: { score_kind: 'measured' } } }).evidence, null);
  const list = reviewableAttempts([{ id: 't1', at: 5, attemptId: 'a1', overall: 80 }], [row, { ...row, id: 'a2', at: 3 }, attemptRow({ id: 'u', created_at: '2026-10-02T00:00:00Z' })]);
  assert.deepEqual(list.map((item) => item.id).sort(), ['a2', 't1'], 'the tab take stands once; the other verified attempt follows');
  assert.ok(list.find((item) => item.id === 't1').evidence, 'the tab take carries what the account kept of it');
  assert.ok(!list.some((item) => item.id === 'u'), 'an unverified attempt has nothing to review');
  const card = historyFor([{ id: 'b', at: 2, overall: 90, accuracy: 88 }, { id: 'a', at: 1, overall: 80, accuracy: 80 }], 'b', () => kept);
  assert.equal(card.count, 2);
  assert.equal(card.best, 90);
  assert.equal(card.bestN, 2);
  assert.equal(card.rows[0].id, 'b', 'newest on top');
  assert.equal(card.rows[0].metrics[0].delta.text, '+10');
  assert.equal(card.rows[0].focus, 'big');
  assert.deepEqual(card.rows[0].metrics.map((m) => m.key), ['histPron', 'metricAccuracy', 'metricFluency'], 'nothing measured against the model: the assessment numbers stay');
  const measured = historyFor([{ id: 'b', at: 2, overall: 90 }, { id: 'a', at: 1, overall: 80 }], 'b', () => kept, (item) => (item.id === 'b' ? { similarity: 72, intonation: 80 } : item.id === 'a' ? { similarity: 60, intonation: null } : null));
  assert.deepEqual(measured.rows[0].metrics.map((m) => [m.key, m.value]), [['histSimilarity', 72], ['metricIntonation', 80], ['histPron', 90]]);
  assert.equal(measured.rows[0].metrics[0].delta.text, '+12');
  assert.equal(measured.rows[1].metrics[1].value, null, 'an attempt without a measured intonation shows none');
  assert.deepEqual(metricLineFor(pronunciationView(RESULT, { language: 'en' }), { similarity: 70, intonation: 81 }).parts.slice(0, 2), [{ key: 'metricSimilarity', value: 70 }, { key: 'metricIntonation', value: 81 }]);
  assert.ok(!metricLineFor(pronunciationView(RESULT, { language: 'en' }), { similarity: null, intonation: null }).parts.some((p) => /Similarity|Intonation/.test(p.key)));
}
