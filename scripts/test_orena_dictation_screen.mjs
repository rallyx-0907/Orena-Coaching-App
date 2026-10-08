/* The Dictation result contract (D-066): `DictationResult` from the Canonical UI Baseline,
   held to the pinned JSON and to the baseline's own worked example.

   The numbers (capabilities/dictation-result.js, used by screens/dictation/model.js) add nothing
   to the comparison: the score, the units and the words the learner has earned are the
   evaluator's and the hint module's. What is held here is the shape, and the promises the
   baseline makes: a hint never shows the whole line, a reading sits under each character, and a
   substitution is one mistake. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  HINT_LEVELS,
  dictationHintView,
  dictationResult,
  diffMarks,
  readingLineFor,
  readingsFor,
  revealedCount,
  verdictOf,
} from '../static/orena/capabilities/dictation-result.js';

const contract = JSON.parse(
  readFileSync(new URL('../docs/design/canonical-ui/data-contracts/DictationResult.json', import.meta.url), 'utf8'),
);
const covers = (template, value, path = '$') => {
  if (Array.isArray(template)) return template.length && value.length ? covers(template[0], value[0], `${path}[0]`) : undefined;
  if (template && typeof template === 'object') {
    assert.ok(value && typeof value === 'object', `${path} should be an object`);
    for (const [key, inner] of Object.entries(template)) {
      if (key.startsWith('_')) continue;
      assert.ok(key in value, `${path}.${key} is missing`);
      covers(inner, value[key], `${path}.${key}`);
    }
  }
};

/* The baseline's own example: 我们想要一张靠窗的桌子。 typed as 我们相要一张靠窗桌子吗。 */
const LINE = '我们想要一张靠窗的桌子。';
const READINGS = '我们想要一张靠窗的桌子'.split('').map((char, i) => ({ char, pinyin: `p${i}` }));
const result = dictationResult({
  lineIndex: 2,
  lineTotal: 5,
  expected: LINE,
  answer: '我们相要一张靠窗桌子吗。',
  language: 'zh',
  reading: 'Wǒmen xiǎng yào yì zhāng kào chuāng de zhuōzi.',
  readings: READINGS,
  level: 2,
});
covers(contract, result);
assert.equal(result.score, 73, 'the score is the evaluator\'s');
assert.equal(`${result.correctCount} / ${result.totalCount}`, '8 / 11', 'the count the score is made of');
assert.deepEqual(result.diffs.map((d) => d.kind), ['wrong', 'missing', 'extra'], 'a substitution is one wrong place, not a missing and an extra');
assert.deepEqual(
  [result.diffs[0].from, result.diffs[0].to, result.diffs[1].to, result.diffs[2].from],
  ['相', '想', '的', '吗'],
);
for (const diff of result.diffs) assert.ok(['wrong', 'missing', 'extra'].includes(diff.kind) && typeof diff.note === 'string');
assert.deepEqual(result.hint.revealed, ['我', '们', '想', '要', '一'], 'level 2 of 3 shows the leading characters');
assert.equal(`${result.hint.charRevealed} / ${result.hint.charTotal}`, '5 / 11');
assert.deepEqual(verdictOf(result), { key: 'close', places: 3, counts: { wrong: 1, missing: 1, extra: 1 } });
assert.equal(verdictOf(dictationResult({ lineIndex: 1, lineTotal: 1, expected: LINE, answer: LINE, language: 'zh' })).key, 'exact');

/* A hint never shows the whole line, whatever the level and however short the line. */
assert.equal(revealedCount(0, 11), 0, 'level 0 is no hint');
for (const count of [2, 3, 5, 11, 40]) {
  let last = 0;
  for (let level = 0; level <= HINT_LEVELS; level += 1) {
    const shown = revealedCount(level, count);
    assert.ok(shown < count, `level ${level} of ${count} units leaves at least one hidden`);
    assert.ok(shown >= last, 'a deeper level never shows less');
    if (level > 0) assert.ok(shown >= 1, 'a hint that is asked for shows something');
    last = shown;
  }
}
assert.equal(revealedCount(3, 1), 0, 'a one-unit line is never given away');

/* A reading sits under each character; a hidden one keeps the place with a dot. */
const view = dictationHintView({ expected: LINE, answer: '', language: 'zh', level: 2, readings: READINGS });
assert.deepEqual(view.cells.slice(0, 5).map((cell) => cell.reading), ['p0', 'p1', 'p2', 'p3', 'p4']);
assert.ok(view.cells.slice(5).every((cell) => cell.kind === 'hidden' && cell.text === '＊' && cell.reading === ''));
assert.equal(view.charTotal, 11, 'punctuation is the shape of the line, not a character to find');

/* What the learner has earned by typing is shown at level 0, and only what they have earned. */
const earned = dictationHintView({ expected: 'I have a pen.', answer: 'I have', language: 'en', level: 0 });
assert.deepEqual(earned.cells.map((cell) => cell.kind), ['shown', 'shown', 'hidden', 'hidden']);
assert.equal(earned.cells[3].text, '***');
assert.equal(earned.cells[3].after, '.', 'punctuation trails its word');
assert.equal(earned.charTotal, 9);

/* A line said with a label that is not spoken keeps its readings. */
const LABELLED = '金妮：他们是谁？';
const labelled = '金妮他们是谁'.split('').map((char, i) => ({ char, pinyin: `q${i}` }));
assert.deepEqual(readingsFor('他们是谁？', LABELLED, labelled).map((x) => x.pinyin), ['q2', 'q3', 'q4', 'q5']);
assert.equal(readingLineFor('他们是谁？', LABELLED, 'Jīnní: Tāmen shì shéi?'), 'Tāmen shì shéi?');
assert.deepEqual(readingsFor('别的话', LABELLED, labelled), [], 'a reading that is not this line is not shown');

/* The marks. */
const marks = diffMarks([
  { status: 'correct', expected: 'a', actual: 'a' },
  { status: 'missing', expected: 'b', actual: '' },
  { status: 'extra', expected: '', actual: 'x' },
  { status: 'extra', expected: '', actual: 'y' },
  { status: 'missing', expected: 'c', actual: '' },
]);
assert.deepEqual(marks.map((m) => m.kind), ['correct', 'wrong', 'wrong'], 'each adjacent missing and extra pair is one wrong place');

console.log('Dictation screen: DictationResult contract, hint bounds, readings and marks: PASS');
