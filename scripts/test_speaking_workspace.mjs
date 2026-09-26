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

const s = speakCopy('vi', 'vi');
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
assert.match(empty, /data-sp-hear-take[^>]* disabled/);
assert.match(empty, /data-sp-compare[^>]* disabled/);
// One row of actions (D-078): recording again lives with the microphone, next is the primary.
assert.equal(empty.includes('data-sp-again'), false, 'no second "record again" in the result panel');
assert.match(empty, /class="sp-btn sp-btn--accent sp-btn--next" data-sp-next/);
assert.equal((empty.match(/class="sp-btn[ "]/g) || []).length, 3, 'three actions: hear yours, compare, next');

// A synthetic demo result draws nothing measured.
const demo = resultHtml({ s, view: pronunciationView({ score_kind: 'synthetic_demo', pron_score: 76, words: [{ word: 'x', accuracy_score: 84 }] }), language: 'en' });
assert.equal(/\b(76|84)\b/.test(demo.replace(/<svg[\s\S]*?<\/svg>/g, '')), false, 'demo values are never drawn');

// The phone card keeps only the flagged words.
const card = cardHtml({ s, view: zh, language: 'zh' });
assert.equal((card.match(/sp-mrow"/g) || []).length, 1);
const clean = cardHtml({ s, view: pronunciationView({ ...zhResult, words: zhResult.words.map((word) => ({ ...word, error_type: 'None' })) }, { language: 'zh', readings }), language: 'zh' });
assert.equal(clean.includes(s.subTap), false, 'no "tap a row" on a card with no rows');

// Word detail, Chinese: the model's tones from the reading; "yours" is not measured and has no curve.
const detail = detailHtml({ s, c: {}, word: zh.words[3], language: 'zh' });
assert.match(detail, new RegExp(s.toneUnmeasured));
const panels = detail.split('sp-tone sp-tone--yours');
assert.equal((panels[0].match(/<polyline/g) || []).length, 3, 'three syllables, three model curves');
assert.equal((panels[1].match(/<polyline/g) || []).length, 0, 'no curve is drawn for an unmeasured tone');
assert.match(detail, /mei3/, 'the provider’s units are listed as sounds, not as tones');
assert.equal(toneSvg([]), '<svg viewBox="0 0 120 60" aria-hidden="true"></svg>');
// The sheet's sentence is punctuated in the interface language, not with a hard-coded ". ".
const zhDetail = detailHtml({ s: speakCopy('zh', 'zh'), c: {}, word: zh.words[3], language: 'zh' });
assert.match(zhDetail, /读错了。得分 58。|。得分 58。/);
assert.equal(/[^.]\. 得分/.test(zhDetail), false, 'no Latin full stop inside Chinese');
assert.equal(/。 /.test(zhDetail), false, 'no Latin space between Chinese sentences');

// Word detail, English: no tone panels; the phoneme that lost is shown with its own score.
const en = pronunciationView({ score_kind: 'measured', reference_text: 'Two cats.', pron_score: 70, accuracy_score: 72, words: [{ word: 'cats', accuracy_score: 61, error_type: 'None', phonemes: [{ phoneme: 'k', accuracy_score: 95 }, { phoneme: 's', accuracy_score: 4 }] }] }, { language: 'en' });
const enDetail = detailHtml({ s: speakCopy('en', 'en'), c: {}, word: en.words[0], language: 'en' });
assert.equal(enDetail.includes('sp-tones'), false);
assert.match(enDetail, /sp-sound sp-sound--low"><b>s<\/b><small>4<\/small>/);
assert.equal(wordNote(speakCopy('en', 'en'), en.words[0]), 'Passed', 'passed is the provider’s flag, and the phoneme evidence is one tap away');

// Every interface language owns every string (Design Contract rule 26).
for (const ui of ['vi', 'zh'])
  for (const key of Object.keys(speakingCopy.en)) assert.ok(String(speakingCopy[ui][key] || '').trim(), `${ui}.${key}`);
assert.equal(speakCopy('vi', 'vi').room, 'Nói');

// The room reads the result only through the projection, and never talks to a provider.
const workspace = readFileSync(new URL('../static/orena/ui/speaking-workspace.js', import.meta.url), 'utf8');
assert.match(workspace, /pronunciationView\(/);
assert.equal(/fetch\(|XMLHttpRequest|azure/i.test(workspace), false);
assert.equal(/NBest|PronScore|AccuracyScore/.test(workspace), false, 'no provider schema in the browser');

// Free talk (frame "Speaking · free talk"): the topic, what was said and for how long, one comment,
// and the three ways on. It is not pronunciation: no score is drawn there.
const { freeTalkHtml, saidHtml } = await import('../static/orena/ui/speaking-free.js');
const free = freeTalkHtml({ s, title: 'Nói tự do', topic: '带一个人认识你的城市', cue: '想象一个具体的人。', language: 'zh' });
assert.match(free, /class="sp-label">CHỦ ĐỀ</);
assert.match(free, /<h1 lang="zh">带一个人认识你的城市<\/h1>/);
assert.match(free, /data-sp-deeper disabled/, 'deeper suggestions wait for something to be deeper about');
assert.match(free, new RegExp(s.otherTopic));
assert.equal(/sp-ring|ĐẠT|PHÁT ÂM/.test(free), false, 'free talk draws no pronunciation score');
const said = saidHtml({ s, heard: '我觉得靠窗的位子很好。', ms: 26_400, comment: 'Có thể thêm 而且.', language: 'zh' });
assert.match(said, /BẠN VỪA NÓI · 00:26/);
assert.match(said, /sp-said__comment/);
assert.equal(saidHtml({ s, heard: 'x', ms: 1000, comment: '', language: 'en' }).includes('sp-said__comment'), false, 'no comment line until the coaching gives one');
const freeSource = readFileSync(new URL('../static/orena/ui/speaking-free.js', import.meta.url), 'utf8');
assert.match(freeSource, /evaluateVoice\(/, 'free talk reuses the existing recognition and evidence plumbing');
// Free talk is scored only by the provider's free-speech (unscripted) measurement (D-076).
assert.deepEqual([...freeSource.matchAll(/assessPronunciation\(([^)]*)\)/g)].map((m) => m[1]), ["take.blob, language, '', 'unscripted'"]);

// 04 · the free talk result: only measured criteria carry a number; no overall; no "last time".
const { freeResultHtml, fixesOf, markedTranscript } = await import('../static/orena/ui/speaking-free.js');
const coaching = { available: true, landed_differently: [{ quote: '很好', instead: '不错', why: 'Tự nhiên hơn.', judgement: 'unnatural' }], another_way: 'Bạn có thể nói ...', say_again: '我觉得靠窗的位子不错。' };
const result = freeResultHtml({ s, c: { coachingWorking: '…', lookCloser: 'x', develop: 'y', conversationStart: 'z' }, title: 'Nói tự do', topic: '带一个人认识你的城市', language: 'zh', ms: 26000, heard: '我觉得靠窗的位子很好。', coaching, scores: { pron: 83.8, fluency: 79 }, bars: [0.2, 0.9] });
assert.match(result, /Lưu loát<\/span><span class="sp-bar"><i style="width:79%">/);
assert.match(result, /Phát âm<\/span><span class="sp-bar"><i style="width:84%">/);
assert.match(result, /Ngữ pháp<\/span><span class="sp-bar"><i style="width:0%">/, 'no approved evaluator: 0');
assert.match(result, /Từ vựng<\/span><span class="sp-bar"><i style="width:0%">/);
assert.match(result, /--score:0%/, 'no overall while a component is missing');
assert.equal(/Lần trước|Last time/.test(result), false);
assert.match(result, /<mark class="sp-fix-mark">很好<\/mark>/);
assert.match(result, /data-sp-ftr-fixed/, 'the corrected line can be said, as pronunciation of a given line');
assert.match(result, /<p lang="zh">我觉得靠窗的位子不错。<\/p>/, 'the line to say again is the learning-language line');
assert.equal(result.includes('Bạn có thể nói'), false, 'advice in the support language is never offered as a line to say');
assert.equal(/Lưu vào Thư viện|data-sp-ftr-save/.test(result), false, 'no saving to the library (D-076)');
// Free talk's older ways on are kept one step in, behind "⋯" (S14): not a row on the result.
assert.match(result, /data-sp-ftr-more aria-haspopup="dialog" aria-label="Làm thêm với câu vừa nói"/);
assert.equal(/data-free-understand|data-free-develop|data-free-talk|sp-ftr__more"/.test(result), false, 'no row of old actions on the result');
const { moreSheetHtml, MORE_WAYS } = await import('../static/orena/ui/speaking-free.js');
assert.deepEqual(MORE_WAYS.map((way) => way.name), ['understand', 'develop', 'talk']);
const more = moreSheetHtml({ s, c: { lookCloser: 'Xem kỹ hơn', develop: 'Phát triển', conversationStart: 'Trò chuyện', quickClose: 'Đóng' }, heard: '我觉得很好。', language: 'zh' });
assert.equal((more.match(/class="ls-way"/g) || []).length, 3, 'the three ways, in the shared deep-sheet rows');
assert.match(more, /<p class="ls-line" lang="zh">我觉得很好。<\/p>/, 'the sheet shows what it acts on');
assert.equal(fixesOf({ landed_differently: [1, 2, 3, 4].map((n) => ({ quote: String(n) })) }).length, 3);
assert.equal(markedTranscript('a <b>', [], 'en'), '<span lang="en">a &lt;b&gt;</span>');
const unmeasured = freeResultHtml({ s, c: { coachingWorking: 'Đang xem…' }, title: 't', topic: 'x', language: 'en', ms: 1000, heard: 'hi', coaching: undefined, scores: null, bars: [] });
assert.match(unmeasured, /Lưu loát<\/span><span class="sp-bar"><i style="width:0%">/, 'an unmeasured fluency is 0, never a guess');

console.log('Speaking workspace and free talk markup (PronunciationResult, EN/VI/ZH): PASS');
