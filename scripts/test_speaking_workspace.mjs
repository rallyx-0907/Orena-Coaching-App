/* The Speaking workspace's markup (ui/speaking-workspace.js) against PronunciationResult and the
   Orena Speaking frames: what is drawn for a measured result, what is never drawn, and that every
   interface language owns every string the room asks for. Behaviour in a browser is checked on the
   sandbox (docs/project/UI_BACKEND_GAPS.md, Speaking log). */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { pronunciationView } from '../static/orena/capabilities/pronunciation-result.js';
import { speakingCopy, speakCopy } from '../static/orena/ui/speaking-copy.js';
import {
  lineUnits,
  placeWords,
  sentenceHtml,
  resultHtml,
  cardHtml,
  detailHtml,
  wordNote,
  toneSvg,
} from '../static/orena/ui/speaking-workspace.js';

const s = speakCopy('vi');
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
const line = sentenceHtml('你也是美国人吗？', 'zh', zh);
assert.equal((line.match(/sp-tok--flag/g) || []).length, 1, 'one mark per flagged word');
assert.match(line, /<span class="sp-tok--flag"><span class="sp-tok" data-sp-tok="3">美<\/span><span class="sp-tok" data-sp-tok="4">国<\/span><span class="sp-tok" data-sp-tok="5">人<\/span><\/span>/);
assert.equal(sentenceHtml('你也是美国人吗？', 'zh', pronunciationView(null)).includes('sp-tok--flag'), false, 'nothing is marked before a measurement');
// An English word is never found inside a longer one.
assert.deepEqual(placeWords('Is it a cat or a cattle?', [{ text: 'cat' }, { text: 'cattle' }], 'en'), [{ start: 8, end: 11 }, { start: 17, end: 23 }]);

// The panel: the ring, the provider's flags as the passed count, one row per word.
const panel = resultHtml({ s, view: zh, language: 'zh' });
assert.match(panel, /--score:81%/);
assert.match(panel, /4 \/ 5 ĐẠT/);
assert.match(panel, /PHÁT ÂM <b>81<\/b>/);
assert.match(panel, /LƯU LOÁT <b>76<\/b>/);
assert.equal((panel.match(/class="sp-row /g) || []).length + (panel.match(/class="sp-row"/g) || []).length, 5);
assert.match(panel, /sp-row sp-row--flag" data-sp-word="3"/);
assert.match(panel, /<small>měi guó rén<\/small>/, 'the lesson reading, grouped by word');
assert.match(panel, new RegExp(s.error_mispronunciation));
assert.equal(/azure|provider|stand-in/i.test(panel), false, 'no provider in the learner UI');
assert.equal(panel.includes(s.metricPace), false, 'no pace without word timing');

// Before a take: 0 in the canonical component, the plain sentence, no rows, and no take to hear.
const empty = resultHtml({ s, view: pronunciationView(null), language: 'zh' });
assert.match(empty, /--score:0%/);
assert.match(empty, new RegExp(s.noResult));
assert.match(empty, /data-sp-hear-take disabled/);
assert.match(empty, /data-sp-compare disabled/);

// A synthetic demo result draws nothing measured.
const demo = resultHtml({ s, view: pronunciationView({ score_kind: 'synthetic_demo', pron_score: 76, words: [{ word: 'x', accuracy_score: 84 }] }), language: 'en' });
assert.equal(/\b(76|84)\b/.test(demo.replace(/<svg[\s\S]*?<\/svg>/g, '')), false, 'demo values are never drawn');

// The phone card keeps only the flagged words.
const card = cardHtml({ s, view: zh, language: 'zh' });
assert.equal((card.match(/sp-mrow"/g) || []).length, 1);

// Word detail, Chinese: the model's tones from the reading; "yours" is not measured and has no curve.
const detail = detailHtml({ s, c: {}, word: zh.words[3], language: 'zh' });
assert.match(detail, new RegExp(s.toneUnmeasured));
const panels = detail.split('sp-tone sp-tone--yours');
assert.equal((panels[0].match(/<polyline/g) || []).length, 3, 'three syllables, three model curves');
assert.equal((panels[1].match(/<polyline/g) || []).length, 0, 'no curve is drawn for an unmeasured tone');
assert.match(detail, /mei3/, 'the provider’s units are listed as sounds, not as tones');
assert.equal(toneSvg([]), '<svg viewBox="0 0 120 60" aria-hidden="true"></svg>');

// Word detail, English: no tone panels; the phoneme that lost is shown with its own score.
const en = pronunciationView({ score_kind: 'measured', reference_text: 'Two cats.', pron_score: 70, accuracy_score: 72, words: [{ word: 'cats', accuracy_score: 61, error_type: 'None', phonemes: [{ phoneme: 'k', accuracy_score: 95 }, { phoneme: 's', accuracy_score: 4 }] }] }, { language: 'en' });
const enDetail = detailHtml({ s: speakCopy('en'), c: {}, word: en.words[0], language: 'en' });
assert.equal(enDetail.includes('sp-tones'), false);
assert.match(enDetail, /sp-sound sp-sound--low"><b>s<\/b><small>4<\/small>/);
assert.equal(wordNote(speakCopy('en'), en.words[0]), 'Passed', 'passed is the provider’s flag, and the phoneme evidence is one tap away');

// Every interface language owns every string (Design Contract rule 26).
for (const ui of ['vi', 'zh'])
  for (const key of Object.keys(speakingCopy.en)) assert.ok(String(speakingCopy[ui][key] || '').trim(), `${ui}.${key}`);
assert.equal(speakCopy('vi').room, 'Nói');

// The room reads the result only through the projection, and never talks to a provider.
const workspace = readFileSync(new URL('../static/orena/ui/speaking-workspace.js', import.meta.url), 'utf8');
assert.match(workspace, /pronunciationView\(/);
assert.equal(/fetch\(|XMLHttpRequest|azure/i.test(workspace), false);
assert.equal(/NBest|PronScore|AccuracyScore/.test(workspace), false, 'no provider schema in the browser');

console.log('Speaking workspace markup (PronunciationResult, EN/VI/ZH): PASS');
