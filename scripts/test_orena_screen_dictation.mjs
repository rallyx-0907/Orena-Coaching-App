/* Gate for Dictation's pure data mapping (static/orena/screens/dictation/model.js). Imports only
   the DOM-free module, plus the shared capabilities it wraps (unchanged, already covered by their
   own gates elsewhere) to prove the two agree.

   Loads the real captured payloads (scripts/fixtures/api/listening_library_lesson.en(.zh).json -
   `GET /api/listening/library/{id}?target_language=...`), so a screen model that reads a field
   these payloads do not carry fails this gate. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  mapLesson,
  startIndex,
  rateLabel,
  nextRate,
  DICTATION_RATES,
  waveBars,
  WAVE_BARS,
  segmentState,
  dotStates,
  doneCount,
  progressBySegment,
  previousEvidence,
  checkAnswer,
  chipsFor,
  scoreOf,
  scoreNoteKey,
  verdictOf,
  hintNoteKey,
  hintButton,
  liveView,
  MAX_HINT_LEVEL,
  clock,
} from '../static/orena/screens/dictation/model.js';

function fixture(name) {
  return JSON.parse(readFileSync(new URL(`./fixtures/api/${name}`, import.meta.url)));
}

/* --- clock --- */
assert.equal(clock(0), '0:00');
assert.equal(clock(7500), '0:07');
assert.equal(clock(65000), '1:05');

/* --- mapLesson against the real captured English lesson --- */
{
  const payload = fixture('listening_library_lesson.en.json');
  const lesson = mapLesson(payload);
  assert.equal(lesson.id, 'en-science-cosmic-calendar');
  assert.equal(lesson.assetId, 'commons-royalsociety-cosmic-calendar');
  assert.equal(lesson.title, 'The cosmic calendar');
  assert.equal(lesson.language, 'en');
  assert.ok(lesson.playback && lesson.playback.kind === 'video');
  assert.equal(lesson.segments.length, 3, 'every real segment with text becomes a dictation line');
  assert.equal(lesson.segments[0].id, 'commons-royalsociety-cosmic-calendar:000');
  assert.equal(lesson.segments[0].startMs, 1000);
  assert.equal(lesson.segments[0].endMs, 6500);
  assert.equal(
    lesson.segments[0].text,
    "With the big bang starting the year and as cheering new year's eve one year later",
    'catalog.spoken_text_by_segment is empty in this capture, so the real fallback (original_text) is used - never invented',
  );
  assert.equal(lesson.segments[0].support, '', 'no translation entry for this capture (target_language=en, status not_required) - never a guessed meaning');
}

/* --- mapLesson against the real captured Chinese lesson (with real translations) --- */
{
  const payload = fixture('listening_library_lesson.zh.json');
  const lesson = mapLesson(payload);
  assert.equal(lesson.id, 'zh-technology-search-wikipedia');
  assert.equal(lesson.language, 'zh');
  assert.equal(lesson.segments.length, 3);
  assert.equal(lesson.segments[0].text, '现在看到的是中文维基百科的首页(Vector版)');
  assert.equal(lesson.segments[0].support, 'What you see now is the Chinese Wikipedia home page (Vector skin).');
  assert.equal(lesson.segments[1].support, 'You can type in what you are looking for.');
}

/* --- startIndex: a real `seg` query param wins, else the first segment --- */
{
  const segments = [{ id: 'a' }, { id: 'b' }, { id: 'c' }];
  assert.equal(startIndex(segments, 'b'), 1);
  assert.equal(startIndex(segments, 'nope'), 0, 'an unknown id is never a guess at some other segment');
  assert.equal(startIndex(segments, ''), 0);
  assert.equal(startIndex(segments, null), 0);
}

/* --- rate cycling --- */
assert.deepEqual(DICTATION_RATES, [1, 0.75, 0.5, 1.25], "the design's own shared speed ladder (cycleSpeed)");
assert.equal(rateLabel(1), '1×');
assert.equal(rateLabel(0.75), '0.75×');
assert.equal(rateLabel(1.25), '1.25×');
assert.equal(nextRate(1), 0.75);
assert.equal(nextRate(0.75), 0.5);
assert.equal(nextRate(0.5), 1.25);
assert.equal(nextRate(1.25), 1, 'cycles back to the start');
assert.equal(nextRate(9), 1, 'an unknown rate restarts the ladder at 1x, never a guess');
{
  // Every rate in the ladder is one the shared player accepts (capabilities/media-player.js#setPlaybackRate).
  const accepted = [0.5, 0.75, 1, 1.25, 1.5, 2];
  assert.ok(DICTATION_RATES.every((rate) => accepted.includes(rate)));
}

/* --- previousEvidence / progressBySegment against a real captured save (a live Check ->
   `POST /api/listening/progress` -> `GET .../progress`, scripts/fixtures/api/listening_progress.json) --- */
{
  const real = fixture('listening_progress.json');
  const byId = progressBySegment(real.items);
  const record = byId.get('commons-royalsociety-cosmic-calendar:000');
  assert.ok(record);
  const previous = previousEvidence(record);
  assert.equal(previous.checked_attempt_count, 1);
  assert.equal(previous.best_accuracy_percent, 44);
  assert.equal(previous.last_answer, 'With the big bang starting the year');
  assert.equal(segmentState(record), 'partial', 'a real, non-exact check lights the amber dot');
}

/* --- segmentState / dotStates / doneCount: the frame's four dot colours, from real records only --- */
{
  const segments = [{ id: 'a' }, { id: 'b' }, { id: 'c' }, { id: 'd' }];
  const byId = progressBySegment([
    { segment_id: 'a', checked_attempt_count: 2, best_exact: true },
    { segment_id: 'b', checked_attempt_count: 1, best_exact: false },
    { segment_id: 'c', checked_attempt_count: 0 },
  ]);
  assert.equal(segmentState(byId.get('a')), 'exact');
  assert.equal(segmentState(byId.get('b')), 'partial');
  assert.equal(segmentState(byId.get('c')), 'none', 'checked_attempt_count 0 is not a real check yet');
  assert.equal(segmentState(undefined), 'none');
  assert.equal(segmentState(byId.get('b'), { exact: true }), 'exact', "this session's own latest check wins over the stored best");
  assert.equal(segmentState(null, { exact: false }), 'partial');
  assert.deepEqual(dotStates(segments, byId, new Map(), 3), ['exact', 'partial', 'none', 'current'], 'the current segment is the accent dot, whatever its record says');
  assert.deepEqual(dotStates(segments, byId, new Map(), 0), ['current', 'partial', 'none', 'none']);
  assert.equal(doneCount(segments, byId, new Map()), 2);
  assert.equal(doneCount(segments, byId, new Map([['d', { exact: false }]])), 3, 'a check made this session counts before it is re-read');
  assert.deepEqual(dotStates(segments, progressBySegment([]), new Map(), 1), ['none', 'current', 'none', 'none'], 'no records at all: nothing lit but the current dot');
  assert.equal(doneCount(segments, progressBySegment([]), new Map()), 0);
}

/* --- waveBars: the frame's decoration, deterministic, never a measurement --- */
{
  const bars = waveBars(3);
  assert.equal(bars.length, WAVE_BARS);
  assert.equal(WAVE_BARS, 32, "the design's own bar count");
  assert.ok(bars.every((bar) => bar.height >= 30 && bar.height <= 100 && bar.delay >= 0 && bar.delay < 600));
  assert.deepEqual(waveBars(3), bars, 'same segment, same bars');
  assert.notDeepEqual(waveBars(4).map((bar) => bar.height), bars.map((bar) => bar.height), 'each segment has its own shape');
}

/* --- previousEvidence: rule 40, a fresh segment carries no invented history --- */
assert.deepEqual(previousEvidence(null), {});
assert.deepEqual(previousEvidence({ checked_attempt_count: 3, best_accuracy_percent: 80, best_exact: false, last_answer: 'x', last_used_hint: true, last_hint_level: 1, revealed: false }), {
  revealed: false,
  checked_attempt_count: 3,
  best_accuracy_percent: 80,
  best_exact: false,
  last_answer: 'x',
  last_used_hint: true,
  last_hint_level: 1,
});

/* --- checkAnswer / chipsFor / scoreOf: the real comparison, never reimplemented here --- */
{
  const args = { expected: 'The quick brown fox', answer: 'The quick brown fox', language: 'en' };
  const result = checkAnswer(args);
  assert.equal(result.score, 100);
  assert.equal(verdictOf(result).key, 'exact');
  const score = scoreOf(result);
  assert.deepEqual([score.correct, score.total, score.tier], [4, 4, 'exact'], "the frame's matched/total score");
  assert.equal(scoreNoteKey(score.tier), 'scoreNoteExact');
  const chips = chipsFor(result, args);
  assert.equal(chips.mine.length, 4);
  assert.ok(chips.mine.every((chip) => chip.kind === 'correct'));
  assert.deepEqual(chips.src.map((chip) => chip.text), ['The', 'quick', 'brown', 'fox'], "the transcript chips keep the line's own spelling and case");
  assert.equal(chips.mineEmpty, false);
}
{
  const args = { expected: 'the quick brown fox', answer: 'The quik Brown', language: 'en' };
  const result = checkAnswer(args);
  assert.ok(result.score < 100);
  const verdict = verdictOf(result);
  assert.notEqual(verdict.key, 'exact');
  assert.ok(verdict.places > 0);
  const chips = chipsFor(result, args);
  assert.deepEqual(chips.mine.map((chip) => chip.text), ['The', 'quik', 'Brown'], 'what the learner wrote is shown as they wrote it');
  assert.deepEqual(chips.mine.map((chip) => chip.kind), ['correct', 'bad', 'correct'], 'a mistyped word is marked, not shown as correct');
  assert.ok(chips.src.some((chip) => chip.kind === 'fix'), 'the missing word shows on the transcript side as something to fix');
  const score = scoreOf(result);
  assert.equal(score.total, 4);
  assert.equal(score.correct, 2);
  assert.equal(score.tier, 'again', '2 of 4 is below the 0.7 line');
}
{
  const result = checkAnswer({ expected: 'one two three four five six seven eight nine ten', answer: 'one two three four five six seven eight nine tin', language: 'en' });
  assert.equal(scoreOf(result).tier, 'close', '9 of 10 is close');
  assert.equal(scoreNoteKey('close'), 'scoreNoteClose');
  assert.equal(scoreNoteKey('again'), 'scoreNoteAgain');
  assert.equal(scoreNoteKey('bogus'), 'scoreNoteAgain');
}
{
  // An extra word makes the check inexact even when every transcript word matched.
  const result = checkAnswer({ expected: 'good morning', answer: 'good good morning', language: 'en' });
  const score = scoreOf(result);
  assert.equal(score.correct, score.total);
  assert.notEqual(score.tier, 'exact', 'an extra word is not "every word matched"');
}
{
  const result = checkAnswer({ expected: 'the quick brown fox', answer: '', language: 'en' });
  const chips = chipsFor(result, { expected: 'the quick brown fox', answer: '', language: 'en' });
  assert.equal(chips.mine.length, 0);
  assert.equal(chips.mineEmpty, true, 'an empty answer shows the frame\'s own "(nothing)" fallback, not a fabricated chip');
  const score = scoreOf(result);
  assert.deepEqual([score.correct, score.total, score.tier], [0, 4, 'again']);
}
{
  // Chinese: each Han character its own comparable unit (capabilities/dictation-evaluator.js).
  const args = { expected: '你好世界', answer: '你好', language: 'zh' };
  const result = checkAnswer(args);
  assert.ok(result.score > 0 && result.score < 100);
  const chips = chipsFor(result, args);
  assert.equal(chips.mine.length, 2);
  assert.equal(chips.src.length, 4);
  assert.deepEqual(chips.src.map((chip) => chip.text), ['你', '好', '世', '界']);
  assert.equal(scoreOf(result).correct, 2);
}

/* --- hint: the button's label ladder and the fixed category note beside it --- */
{
  assert.equal(MAX_HINT_LEVEL, 3);
  assert.deepEqual(hintButton(0), { key: 'hintGive', values: {}, disabled: false });
  assert.deepEqual(hintButton(1), { key: 'hintMore', values: { n: 2, total: 3 }, disabled: false }, '"More hint (2/3)"');
  assert.deepEqual(hintButton(2), { key: 'hintMore', values: { n: 3, total: 3 }, disabled: false }, '"More hint (3/3)"');
  assert.deepEqual(hintButton(3), { key: 'hintMaxed', values: { n: 3, total: 3 }, disabled: true }, '"Hint 3/3 used"');
  assert.equal(hintButton(9).disabled, true, 'never past the last hint');
  assert.equal(hintNoteKey(0), 'hintNoteStart', 'before any hint is asked for, the progressive-ladder note');
  assert.equal(hintNoteKey(1), 'hintNoteShapes');
  assert.equal(hintNoteKey(2), 'hintNoteLetters');
  assert.equal(hintNoteKey(3), 'hintNoteWords', 'the max level (MAX_HINT_LEVEL)');
  assert.equal(hintNoteKey(4), 'hintNoteWords', 'never past the last category, whatever level is passed in');
  // L-05: a Chinese lesson's ladder names characters, not letters.
  assert.equal(hintNoteKey(0, 'zh'), 'hintNoteStartHan');
  assert.equal(hintNoteKey(2, 'zh'), 'hintNoteLettersHan');
  assert.equal(hintNoteKey(1, 'zh'), 'hintNoteShapes');
}

/* --- liveView: the frame's "Live check" strip (design `dLive`), reach-limited, never the answer --- */
{
  const expected = 'With the big bang starting the year';
  const shapes = liveView({ expected, answer: '', language: 'en', level: 1 });
  assert.equal(shapes.total, 7);
  assert.equal(shapes.found, 0);
  assert.deepEqual(
    shapes.chips.map((chip) => chip.text),
    ['····', '···', '···', '····', '········', '···', '····'],
    'level 1 is the word shapes: one mark per letter, nothing of the answer itself',
  );
  assert.ok(shapes.chips.every((chip) => chip.kind === 'blank'));

  const letters = liveView({ expected, answer: '', language: 'en', level: 2 });
  assert.deepEqual(
    letters.chips.map((chip) => chip.text),
    ['W···', 't··', 'b··', 'b···', 's·······', 't··', 'y···'],
    "level 2 adds the first letter of each word, keeping the line's own case",
  );

  const some = liveView({ expected, answer: '', language: 'en', level: 3 });
  assert.deepEqual(
    some.chips.map((chip) => chip.text),
    ['W···', 'the', 'b··', 'b···', 'starting', 't··', 'y···'],
    'level 3 reveals some words (every third), never all of them',
  );
  assert.ok(some.chips.some((chip) => chip.text.includes('·')), 'the line is never handed over whole');

  // Words the learner has typed correctly are found (green); the rest keep their shape.
  const typed = liveView({ expected, answer: 'With the big bang', language: 'en', level: 1 });
  assert.equal(typed.found, 4);
  assert.deepEqual(typed.chips.map((chip) => chip.kind).slice(0, 5), ['ok', 'ok', 'ok', 'ok', 'blank']);
  assert.deepEqual(typed.chips.map((chip) => chip.text).slice(0, 4), ['With', 'the', 'big', 'bang']);

  // Reach: typing "the" must not confirm the LATER "the" (dictation-hints.js's own principle).
  const reach = liveView({ expected, answer: 'the', language: 'en', level: 1 });
  assert.equal(reach.chips[5].kind, 'blank', 'a word not yet reached is never confirmed');

  // A word in progress: a correct prefix is partial, a wrong one is marked and never handed back.
  const partial = liveView({ expected: 'the quick brown fox', answer: 'the qui', language: 'en', level: 1 });
  assert.equal(partial.chips[1].kind, 'partial');
  assert.equal(partial.chips[1].text, 'qui··', 'what the learner has typed correctly stays visible in the shape');
  const wrong = liveView({ expected: 'the quick brown fox', answer: 'the quack', language: 'en', level: 3 });
  assert.equal(wrong.chips[1].kind, 'wrong');
  assert.ok(wrong.chips[1].text.includes('·'), 'level 3 does not hand back a word the learner got wrong');

  // Level 0 never reveals more than the shapes.
  assert.deepEqual(liveView({ expected: 'go now', answer: '', language: 'en', level: 0 }).chips.map((chip) => chip.text), ['··', '···']);
}
{
  // Chinese: characters are the units; words (Intl.Segmenter) are the strip's slots, so level 2
  // gives the first character of a word, never a lone character whole.
  const expected = '你可以输入你找的内容';
  const shapes = liveView({ expected, answer: '', language: 'zh', level: 1 });
  assert.ok(shapes.chips.length < [...expected].length, 'characters are grouped into words');
  assert.equal(shapes.chips.map((chip) => chip.text).join('').replace(/·/g, '').length, 0, 'level 1 shows only shapes');
  assert.equal(shapes.chips.map((chip) => [...chip.text].length).reduce((a, b) => a + b, 0), [...expected].length, 'one mark per character');
  const found = liveView({ expected, answer: '你可以', language: 'zh', level: 1 });
  assert.ok(found.found >= 1, 'typed characters are confirmed word by word');
  const letters = liveView({ expected, answer: '', language: 'zh', level: 2 });
  assert.ok(letters.chips.every((chip) => [...chip.text].length < 2 || chip.text.includes('·')), 'no multi-character word is shown whole at level 2');
}

console.log('test_orena_screen_dictation.mjs: Dictation data mapping - real listening-lesson captures, real comparison/hint capabilities, rule 40 throughout: PASS');
