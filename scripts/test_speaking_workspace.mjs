/* The Speaking data under the learner UI: PronunciationResult projected to a view
   (capabilities/pronunciation-result.js), and the line segmented into units and word spans
   (product/speaking-line.js) that the Speak, Shadowing and Compare screens place marks on.
   What is drawn is held by test_orena_screen_speak/shadowing/compare.mjs. */
import assert from 'node:assert/strict';
import { pronunciationView } from '../static/orena/capabilities/pronunciation-result.js';
import { lineUnits, placeWords } from '../static/orena/product/speaking-line.js';

const zhResult = {
  score_kind: 'measured',
  reference_text: '你也是美国人吗？',
  pron_score: 81,
  accuracy_score: 83,
  fluency_score: 76,
  words: [
    { word: '你', accuracy_score: 95, error_type: 'None' },
    { word: '也', accuracy_score: 94, error_type: 'None' },
    { word: '是', accuracy_score: 90, error_type: 'None' },
    { word: '美国人', accuracy_score: 58, error_type: 'Mispronunciation', syllables: [{ syllable: 'mei3', accuracy_score: 40 }, { syllable: 'guo2', accuracy_score: 70 }, { syllable: 'ren2', accuracy_score: 64 }] },
    { word: '吗', accuracy_score: 92, error_type: 'None' },
  ],
};
const readings = ['nǐ', 'yě', 'shì', 'měi', 'guó', 'rén', 'ma'].map((pinyin, at) => ({ char: [...'你也是美国人吗'][at], pinyin }));
const zh = pronunciationView(zhResult, { language: 'zh', readings });

// The line: a unit per character; the flagged word is one mark over its three characters.
assert.equal(lineUnits('你也是美国人吗？', 'zh').filter((unit) => unit.unit).length, 7);
assert.deepEqual(placeWords('你也是美国人吗？', zh.words, 'zh')[3], { start: 3, end: 6 });
// An English word is never found inside a longer one.
assert.deepEqual(placeWords('Is it a cat or a cattle?', [{ text: 'cat' }, { text: 'cattle' }], 'en'), [{ start: 8, end: 11 }, { start: 17, end: 23 }]);

// A synthetic demo result is not a measurement, so nothing of it is read as one.
const demoView = pronunciationView({ score_kind: 'synthetic_demo', pron_score: 76, words: [{ word: 'x', accuracy_score: 84 }] });
assert.equal(demoView.measured, false, 'a demo result is never a measurement');
assert.equal(pronunciationView(null).measured, false, 'nothing is measured before a take');
assert.equal(zh.measured, true);
assert.equal(zh.words.filter((word) => word.flagged).length, 1, 'one flagged word');

console.log('Speaking data: PronunciationResult view and line units: PASS');

// L-03: a Latin word inside a Chinese line is one word, not one cell per letter.
{
  const { lineUnits: units } = await import('../static/orena/product/speaking-line.js');
  const zh = units('打开维基百科(Vector版)。', 'zh');
  assert.deepEqual(zh.map((u) => u.text), ['打', '开', '维', '基', '百', '科', '(', 'Vector', '版', ')', '。']);
  assert.equal(zh.find((u) => u.text === 'Vector').unit, true);
  assert.deepEqual(zh.find((u) => u.text === 'Vector'), { text: 'Vector', start: 7, end: 13, unit: true });
}

