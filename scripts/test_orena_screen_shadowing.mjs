/* Gate for Shadowing's pure data mapping (static/orena/screens/shadowing/model.js). Imports only
   the DOM-free module, plus the shared, already-tested `pronunciationView` it wraps, to prove the
   two agree on shape.

   Loads the real captured payloads (scripts/fixtures/api/listening_library_lesson.en(.zh).json -
   `GET /api/listening/library/{id}?target_language=...`), so a screen model that reads a field
   these payloads do not carry fails this gate. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { pronunciationView } from '../static/orena/capabilities/pronunciation-result.js';
import {
  mapLesson,
  startIndex,
  rateLabel,
  nextRate,
  SHADOW_RATES,
  COUNTDOWN,
  WAVE_BARS,
  clock,
  lagMs,
  matchPercent,
  lagSeconds,
  elapsedSeconds,
  percentLabel,
  issueWord,
  errorLabelKey,
  phaseLabelKey,
  phaseTone,
  waveState,
  waveBars,
  levelHeights,
  roundsBySegment,
  nextRounds,
  MAX_ROUNDS,
} from '../static/orena/screens/shadowing/model.js';

function fixture(name) {
  return JSON.parse(readFileSync(new URL(`./fixtures/api/${name}`, import.meta.url)));
}

/* --- clock --- */
assert.equal(clock(0), '0:00');
assert.equal(clock(65000), '1:05');

/* --- mapLesson against the real captured lessons (same shape Dictation reads) --- */
{
  const lesson = mapLesson(fixture('listening_library_lesson.en.json'));
  assert.equal(lesson.id, 'en-science-cosmic-calendar');
  assert.equal(lesson.assetId, 'commons-royalsociety-cosmic-calendar');
  assert.equal(lesson.language, 'en');
  assert.equal(lesson.segments.length, 3);
  assert.equal(lesson.segments[1].text, 'Using this scale the universe slowed and cooled for the first few days of January');
  assert.equal(lesson.segments[1].startMs, 7500);
  assert.equal(lesson.segments[1].endMs, 12500);
}
{
  const lesson = mapLesson(fixture('listening_library_lesson.zh.json'));
  assert.equal(lesson.language, 'zh');
  assert.equal(lesson.segments[0].text, '现在看到的是中文维基百科的首页(Vector版)');
}

/* --- startIndex --- */
{
  const segments = [{ id: 'a' }, { id: 'b' }];
  assert.equal(startIndex(segments, 'b'), 1);
  assert.equal(startIndex(segments, 'nope'), 0);
  assert.equal(startIndex(segments, ''), 0);
}

/* --- rate cycling: the design's shared speed ladder, every step one the player accepts --- */
assert.deepEqual(SHADOW_RATES, [1, 0.75, 0.5, 1.25]);
assert.ok(SHADOW_RATES.every((rate) => [0.5, 0.75, 1, 1.25, 1.5, 2].includes(rate)), 'capabilities/media-player.js#setPlaybackRate refuses any other rate');
assert.equal(rateLabel(1), '1×');
assert.equal(rateLabel(0.75), '0.75×');
assert.equal(rateLabel(1.25), '1.25×');
assert.equal(nextRate(1), 0.75);
assert.equal(nextRate(0.75), 0.5);
assert.equal(nextRate(0.5), 1.25);
assert.equal(nextRate(1.25), 1);

/* --- the countdown and the decorative bars are the frame's own --- */
assert.deepEqual([...COUNTDOWN], [3, 2, 1]);
{
  const bars = waveBars();
  assert.equal(bars.length, WAVE_BARS);
  assert.equal(WAVE_BARS, 40, "the design's own bar count");
  assert.ok(bars.every((bar) => bar.height >= 25 && bar.height <= 100 && bar.delay >= 0 && bar.delay < 700));
  assert.deepEqual(waveBars(), bars, 'deterministic - a shape, never a measurement');
}
{
  // While speaking the bars are the microphone's level: real, floored, clamped.
  const flat = levelHeights([]);
  assert.equal(flat.length, WAVE_BARS);
  assert.ok(flat.every((h) => h === 6), 'silence is a flat row, not a fabricated shape');
  const live = levelHeights([0, 0.5, 1, 2, -1, 'x', null]);
  assert.deepEqual(live.slice(0, 7), [6, 50, 100, 100, 6, 6, 6], 'a level is clamped to 0-1 and floored at 6%');
}
assert.deepEqual(waveState('model'), { active: true, speaking: false });
assert.deepEqual(waveState('speak'), { active: true, speaking: true });
for (const phase of ['idle', 'count', 'processing', 'result']) assert.deepEqual(waveState(phase), { active: false, speaking: false }, `${phase}: the frame dims the bars`);

/* --- lagMs / matchPercent, against a real POST /api/speech/pronunciation shape
   (writing_coach's own provider-neutral envelope; `capabilities/pronunciation-result.js` already
   covers the envelope itself, including each word's own offsetMs/durationMs - this gate proves
   Shadowing's own two additions read straight off that, with no re-derivation) --- */
{
  const measured = {
    score_kind: 'measured',
    pron_score: 88,
    accuracy_score: 90,
    fluency_score: 84,
    completeness_score: 92,
    reference_text: 'the quick brown fox',
    words: [
      { word: 'the', accuracy_score: 95, error_type: 'None', offset_ms: 120, duration_ms: 180 },
      { word: 'quick', accuracy_score: 60, error_type: 'Mispronunciation', offset_ms: 320, duration_ms: 260 },
      { word: 'brown', accuracy_score: 91, error_type: 'None', offset_ms: 610, duration_ms: 240 },
      { word: 'fox', accuracy_score: 93, error_type: 'None', offset_ms: 880, duration_ms: 300 },
    ],
  };
  const view = pronunciationView(measured, { language: 'en', modelSpanMs: 1300 });
  assert.equal(view.measured, true);
  assert.equal(lagMs(view), 120, 'the first assessed word\'s own offset - real, not a retry-count formula');
  assert.ok(view.timing, 'both the learner span and the model span are known, so a real timing delta exists');
  const pct = matchPercent(view.timing);
  assert.ok(pct != null && pct >= 0 && pct <= 100);
  assert.equal(percentLabel(pct), `${pct}%`);
  assert.equal(lagSeconds(lagMs(view)), '+0.12', "the frame's signed seconds, two decimals");

  const issue = issueWord(view);
  assert.equal(issue.text, 'quick', 'the single lowest-scored flagged word, real from the same assessment the ring shows');
  assert.equal(errorLabelKey('Mispronunciation'), 'errorMispronunciation');
  assert.equal(errorLabelKey('Omission'), 'errorOmission');
  assert.equal(errorLabelKey('SomethingNew'), 'errorOther', 'an unrecognised provider label is never a guessed one');
}

/* --- rule 40: nothing measured, nothing shown as if it were --- */
{
  const view = pronunciationView(null);
  assert.equal(view.measured, false);
  assert.equal(lagMs(view), null);
  assert.equal(matchPercent(view.timing), null);
  assert.equal(lagSeconds(null), null, 'the screen renders the dash for a lag nobody measured');
  assert.equal(percentLabel(null), '—');
  assert.equal(issueWord(view), null, 'nothing measured means no flagged word to report either');
}
{
  // Measured, but nothing flagged: no invented "thing to fix".
  const clean = {
    score_kind: 'measured',
    pron_score: 100,
    accuracy_score: 100,
    fluency_score: 100,
    reference_text: 'hi',
    words: [{ word: 'hi', accuracy_score: 100, error_type: 'None', offset_ms: 50, duration_ms: 200 }],
  };
  const view = pronunciationView(clean, { language: 'en' });
  assert.equal(issueWord(view), null);
}

/* --- roundsBySegment / nextRounds against the real captured shadowing-progress rows --- */
{
  const real = fixture('listening_shadowing_progress.json');
  assert.ok(real.items.length >= 1, 'a populated real capture');
  assert.ok(real.items.every((row) => typeof row.segment_id === 'string' && Number.isInteger(row.completed_rounds)), 'the fields the screen reads are the API own');
  const rounds = roundsBySegment(real.items);
  const row = real.items[0];
  assert.equal(rounds.get(row.segment_id), row.completed_rounds);
  assert.equal(nextRounds(rounds, row.segment_id), row.completed_rounds + 1, 'a finished round adds one to the running total');
  assert.equal(nextRounds(rounds, 'never-shadowed'), 1, 'an unseen segment starts at its first round');
  assert.equal(nextRounds(new Map([['a', MAX_ROUNDS]]), 'a'), MAX_ROUNDS, 'clamped to what the API accepts');
  assert.equal(roundsBySegment(null).size, 0);
  assert.equal(roundsBySegment([{ segment_id: '', completed_rounds: 3 }, { segment_id: 'x', completed_rounds: 'nope' }]).get('x'), 0, 'nothing invented from a bad row');
}

/* --- elapsed: one decimal, never negative --- */
assert.equal(elapsedSeconds(0), '0.0');
assert.equal(elapsedSeconds(2340), '2.3');
assert.equal(elapsedSeconds(-5), '0.0');
assert.equal(elapsedSeconds(undefined), '0.0');
assert.equal(lagSeconds(480), '+0.48');
assert.equal(lagSeconds(0), '+0.00');

/* --- phase label/tone: the design's five-state map (`shPhase`), every phase resolves --- */
for (const phase of ['idle', 'model', 'count', 'speak', 'processing', 'result']) {
  assert.ok(phaseLabelKey(phase));
  assert.ok(['muted', 'accent', 'amber', 'red', 'green'].includes(phaseTone(phase)));
}
assert.deepEqual(
  ['idle', 'model', 'count', 'speak', 'result'].map(phaseTone),
  ['muted', 'accent', 'amber', 'red', 'green'],
  "the frame's own phase colours",
);
assert.equal(phaseLabelKey('nonsense'), phaseLabelKey('idle'), 'an unknown phase is never a blank label');
assert.equal(phaseTone('nonsense'), 'muted');

console.log('test_orena_screen_shadowing.mjs: Shadowing data mapping - real listening-lesson captures, real pronunciationView envelope, rule 40 throughout: PASS');
