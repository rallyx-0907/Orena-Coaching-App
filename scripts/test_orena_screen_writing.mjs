// Writing (frame 18, `#/write`, `#/write/:id`): data-mapping assertions over payloads captured from
// the real routes (scripts/fixtures/api/writing_essay_*.json, README there), so a field the model
// reads that the backend does not send fails here. Imports only DOM-free modules (model.js).
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {
  CATEGORY_IDS,
  NEW_DRAFT_KEY,
  SETUP_REGISTERS,
  SETUP_TARGETS,
  allIssues,
  buildSegments,
  charCountOf,
  dimensionRows,
  draftKeyFor,
  findingIsOpen,
  firstPriority,
  firstSentence,
  latestRevisionId,
  levelCode,
  levelLabel,
  mapEssay,
  mapIssues,
  mapStrengths,
  parsePiece,
  reviewGate,
  reviewPayload,
  saveTone,
  setupLevels,
  tooShortNotice,
  reviewCountdown,
  whenLabel,
  wordCountOf,
} from '../static/orena/screens/writing/model.js';
import { applyFix } from '../static/orena/product/revision.js';

const load = (name) => JSON.parse(fs.readFileSync(new URL(`./fixtures/api/${name}`, import.meta.url), 'utf8'));
const detail = load('writing_essay_detail.json');
const review = load('writing_essay_review.json');
const detailV1 = load('writing_essay_detail_v1.json');
const reviewV1 = load('writing_essay_review_v1.json');
const detailZh = load('writing_essay_detail.zh.json');
const reviewZh = load('writing_essay_review.zh.json');
const evaluated = load('writing_evaluate.json');
const keep = load('writing_essay_keep.json');

// --- the model reads only fields the real routes send ---
for (const field of ['id', 'series_id', 'revision_no', 'prompt', 'target_cefr', 'text', 'overall', 'cefr_estimate', 'created_at', 'summary', 'strengths', 'issues', 'dimensions', 'review_kept_at', 'revisions']) {
  assert.ok(field in detail, `GET /api/essays/{id} carries "${field}"`);
}
assert.ok('interpretation' in detail.summary, 'summary.interpretation');
for (const field of ['id', 'priority', 'quote', 'suggestion', 'why', 'how', 'examples', 'category']) {
  assert.ok(field in detail.issues[0], `issues[].${field}`);
}
for (const field of ['id', 'quote', 'why']) assert.ok(field in detail.strengths[0], `strengths[].${field}`);
for (const field of ['id', 'revision_no', 'created_at']) assert.ok(field in detail.revisions[0], `revisions[].${field}`);
for (const field of ['id', 'kind']) assert.ok(field in review.issues[0], `GET /api/essays/{id}/review issues[].${field}`);
for (const field of ['id', 'series_id', 'revision_no', 'overall', 'app_cefr']) assert.ok(field in evaluated, `POST /api/evaluate answers "${field}"`);
assert.equal(keep.kept, true, 'POST /api/essays/{id}/keep answers {id, kept, kept_at}');
assert.ok('kept_at' in keep && keep.id === detail.id);

// --- counts: the unit the language is written in ---
assert.equal(wordCountOf('hello world', 'en'), 2);
assert.equal(wordCountOf('', 'en'), 0);
assert.equal(wordCountOf("don't stop", 'en'), 2, 'an apostrophe joins a word');
assert.equal(wordCountOf('你好世界', 'zh'), 4, 'Chinese counts Han characters');
assert.equal(wordCountOf('你好，世界。', 'zh-CN'), 4, 'ideographic punctuation is not a character of writing');
assert.equal(wordCountOf('我喜欢 iPhone 手机', 'zh'), 6, 'Chinese: Han characters plus Latin words, as the server counts (writing_unit_count)');
assert.equal(wordCountOf('3 cats and a well-known dog', 'en'), 6, 'a number is a word and a hyphenated compound is one, as the server counts');
assert.equal(wordCountOf('Tôi thích học tiếng Anh', 'en'), 5, 'accented letters are letters');
assert.equal(wordCountOf(detail.text, 'en'), 49, 'the live count of a stored essay is the count the server stored');
assert.equal(wordCountOf(detail.text, 'en'), detail.word_count);
assert.equal(charCountOf('hello'), 5);
assert.equal(charCountOf('😀'), 1, 'a surrogate-pair emoji is one character, not two');

// --- review gate: the server's own floor and ceiling, read once ---
assert.deepEqual(reviewGate('short'), { canReview: false, reason: 'tooShort' });
assert.equal(reviewGate('this is a long enough draft to review').canReview, true);
assert.equal(reviewGate('x'.repeat(12001)).reason, 'characters', 'too large is refused before too small, as the server does');

// The floor is the learning language's own, not ten code points: an HSK 1 sentence is an attempt.
for (const [draft, language, ok] of [
  ['我是学生。', 'zh', true], // five characters, the sentence the old floor refused
  ['你好。', 'zh', true],
  ['你好', 'zh-CN', true],
  ['好', 'zh', false],
  ['好。', 'zh', false],
  ['。。。。。。。。。。', 'zh', false],
  ['Hello world, how are you', 'zh', false], // Latin words are not Han characters
  ['Hi Bob.', 'en', true], // seven characters, two words
  ['I agree.', 'en', true],
  ['Hello', 'en', false],
  ['Hello.', 'en', false],
  ['   ', 'en', false],
  ['          ', 'en', false], // ten spaces are not writing
  ['...........', 'en', false],
  ['😀😀😀😀😀😀😀😀😀😀', 'en', false],
  ['Hi Bob.', undefined, true], // no language: the stated default, words
  ['Hi Bob.', 'xx', true],
  ['Hello', 'xx', false],
]) {
  assert.deepEqual(
    reviewGate(draft, language),
    ok ? { canReview: true, reason: '' } : { canReview: false, reason: 'tooShort' },
    `${language} ${JSON.stringify(draft)}`,
  );
}
// Nothing is bought back by padding with whitespace, and nothing is refused for having it.
assert.equal(reviewGate('   我是学生。   ', 'zh').canReview, true);

// What the refusal says is the unit that language writes in, with the number that is enough.
assert.deepEqual(tooShortNotice('zh'), { key: 'tooShortHan', n: 2 });
assert.deepEqual(tooShortNotice('zh-CN'), { key: 'tooShortHan', n: 2 });
assert.deepEqual(tooShortNotice('en'), { key: 'tooShortWords', n: 2 });
/* The countdown (D-098) counts as the gate counts and reaches 0 when Review turns on. */
assert.deepEqual(reviewCountdown('', 'en'), { key: 'moreWords', n: 2 });
assert.deepEqual(reviewCountdown('Hello', 'en'), { key: 'moreWords', n: 1 });
assert.deepEqual(reviewCountdown('Hello there', 'en'), { key: 'moreWords', n: 0 });
assert.deepEqual(reviewCountdown('好。', 'zh'), { key: 'moreHan', n: 1 });
assert.deepEqual(reviewCountdown('はい', 'ja'), { key: 'moreKanaHan', n: 0 });
for (const [draft, language] of [['', 'en'], ['Hello', 'en'], ['Hello there', 'en'], ['好', 'zh'], ['我是学生', 'zh'], ['は', 'ja']]) {
  assert.equal(reviewCountdown(draft, language).n === 0, reviewGate(draft, language).canReview, `${language} ${draft}: countdown and gate agree`);
}
assert.deepEqual(tooShortNotice('xx'), { key: 'tooShortWords', n: 2 });
assert.deepEqual(tooShortNotice(), { key: 'tooShortWords', n: 2 });

// --- which piece a route names, and where its draft lives (the old room's own keys) ---
assert.deepEqual(parsePiece(undefined), { kind: 'new' });
assert.deepEqual(parsePiece('12'), { kind: 'essay', id: 12 });
assert.deepEqual(parsePiece('essay:12'), { kind: 'essay', id: 12 }, 'a continuation entry names its series');
assert.deepEqual(parsePiece('expression:free'), { kind: 'new' });
assert.deepEqual(parsePiece('nonsense'), { kind: 'unknown' });
assert.equal(draftKeyFor(null), NEW_DRAFT_KEY);
assert.equal(NEW_DRAFT_KEY, 'expression:free');
assert.equal(draftKeyFor({ seriesId: 7 }), 'essay:7');
assert.equal(latestRevisionId(detailV1), detail.id, 'the first version of a two-version series opens on the latest');
assert.equal(latestRevisionId(detail), detail.id);
assert.equal(latestRevisionId({ id: 5 }), 5, 'no series list: the essay itself');

// --- levels: CEFR for English, HSK for Chinese; the request carries the evaluator's own code ---
assert.deepEqual(setupLevels('en').map((l) => l.id), ['B1', 'B2', 'C1']);
assert.deepEqual(setupLevels('zh').map((l) => l.label), ['HSK 3', 'HSK 4', 'HSK 5']);
assert.deepEqual(setupLevels('zh').map((l) => l.id), ['HSK3', 'HSK4', 'HSK5']);
assert.equal(levelCode('HSK 3', 'zh'), 'HSK3');
assert.equal(levelCode(' b2 ', 'en'), 'B2');
assert.equal(levelCode('B2', 'zh'), '', 'a CEFR level is not a Chinese level');
assert.equal(levelCode('', 'en'), '');
assert.equal(levelCode('HSK7-9', 'zh'), 'HSK7-9');
assert.equal(levelLabel('HSK3'), 'HSK 3');
assert.equal(levelLabel('B2'), 'B2');
assert.deepEqual(SETUP_REGISTERS, ['informal', 'neutral', 'formal']);
assert.deepEqual(SETUP_TARGETS, [100, 150, 250]);

// --- the review request: only what the evaluator reads (register and length have no field) ---
assert.deepEqual(reviewPayload({ prompt: ' Last weekend ', text: 'Some words here.', level: 'B1', parentId: 3, language: 'en' }), {
  prompt: 'Last weekend',
  text: 'Some words here.',
  learning_language: 'en',
  target_cefr: 'B1',
  parent_essay_id: 3,
});
assert.deepEqual(reviewPayload({ prompt: '', text: '我是学生。', level: '', parentId: null, language: 'zh-CN' }), { prompt: '', text: '我是学生。', learning_language: 'zh' });
assert.equal('writing_context' in reviewPayload({ prompt: 'p', text: 'a b', level: 'B1', language: 'en' }), false);

// --- issues: priority is the backend's own real flag; kind comes from the review; category is finer ---
const essay = mapEssay(detail, review);
assert.equal(essay.id, 2);
assert.equal(essay.seriesId, 1);
assert.equal(essay.revisionNo, 2);
assert.equal(essay.latestId, 2);
assert.equal(essay.overall, 69, 'overall rounds to a whole number');
assert.equal(essay.level, 'B1');
assert.equal(essay.range, 'B1', 'the range is the evaluator\'s own demonstrated band, not the score-derived app level');
assert.notEqual(essay.range, detail.app_cefr);
assert.equal(essay.canCompare, true, 'a second revision exists');
assert.equal(essay.kept, false);
assert.equal(essay.priorityIssues.length, 1, 'the backend marks only the first-listed finding "high"');
assert.equal(essay.otherIssues.length, 1);
assert.equal(essay.hasOther, true);
assert.equal(essay.priorityIssues[0].fragment, 'I like swim in the sea');
assert.equal(essay.priorityIssues[0].correction, 'I like swimming in the sea');
assert.equal(essay.priorityIssues[0].kind, 'grammar');
assert.equal(essay.priorityIssues[0].kindKey, 'kindGrammar');
assert.equal(essay.priorityIssues[0].categoryKey, 'cat_word_form');
assert.equal(essay.otherIssues[0].kind, 'vocabulary', 'the kind is read off the review by the issue\'s id');
assert.equal(essay.otherIssues[0].categoryKey, 'cat_word_choice');
assert.ok(essay.priorityIssues[0].why && essay.priorityIssues[0].how && essay.priorityIssues[0].examples.length === 1);
assert.deepEqual(essay.strengths.map((s) => s.span), ['In the evening, we watched the sunset together']);
assert.equal(essay.summary, detail.summary.interpretation);
assert.equal(mapEssay(detailV1, reviewV1).canCompare, false, 'the first version has nothing to compare with');
assert.equal(mapEssay(detailV1, reviewV1).latestId, 2, 'the first version knows the series\' latest');
assert.equal(mapEssay(null, review), null);
// Without the review answer a finding has no kind: no chip is invented (the screen refuses to load without it).
assert.equal(mapEssay(detail, null).priorityIssues[0].kindKey, '');
// An issue with no fragment (nothing to anchor) is dropped, not shown as a blank row.
assert.equal(mapIssues([{ id: 'x', quote: '', priority: 'high' }], new Map()).priority.length, 0);
assert.deepEqual(mapStrengths([{ id: '1', quote: 'a clear opener', why: 'sets up the story well' }, { id: '2', quote: '', why: 'x' }]), [
  { id: '1', span: 'a clear opener', note: 'sets up the story well' },
]);
assert.equal(firstPriority(essay).id, essay.priorityIssues[0].id);
assert.equal(firstPriority(mapEssay({ ...detail, issues: [] }, review)), null, 'no finding, no "Next"');

// Chinese: the same shape through the same code, with the finer category and an HSK-shaped level.
const zh = mapEssay(detailZh, reviewZh);
assert.equal(zh.priorityIssues[0].fragment, '做完了在回家');
assert.equal(zh.priorityIssues[0].kind, 'grammar');
assert.equal(zh.priorityIssues[0].categoryKey, 'cat_conjunction');
assert.equal(zh.range, 'HSK3');
assert.equal(levelLabel(zh.range), 'HSK 3');
assert.equal(wordCountOf(zh.text, 'zh'), detailZh.word_count, 'the live Han count is the count the server stored for the draft');
assert.equal(zh.canCompare, false);

// --- dimensions: the frame's four, its order, its colours, and a note that is real ---
const rows = dimensionRows(essay.dimensions, allIssues(essay), essay.text);
assert.deepEqual(rows.map((r) => r.key), ['grammar', 'vocabulary', 'coherence', 'naturalness'], 'the frame\'s order; task_achievement is scored but not drawn');
assert.equal(rows[0].color, 'var(--amber)', 'grammar 71: amber (65-79)');
assert.equal(rows[1].color, 'var(--red)', 'vocabulary 64 is below 65: red');
assert.equal(rows[2].color, 'var(--amber)', 'coherence 72: amber');
assert.deepEqual(
  rows.map((r) => r.pct),
  ['71%', '64%', '72%', '66%'],
);
assert.deepEqual(rows[0].note, { key: 'dimFixes', n: 1 }, 'the grammar finding is still in the draft: one fix');
assert.deepEqual(rows[1].note, { key: 'dimFixes', n: 1 }, 'the word-choice finding counts against vocabulary');
assert.equal(rows[2].note, null, 'coherence has no findings and is below 80: nothing is invented ("1 tip")');
assert.equal(rows[3].note, null);
assert.deepEqual(dimensionRows({ grammar: 91 }, [], '')[0].note, { key: 'dimStrong', n: 0 });
assert.equal(dimensionRows({ grammar: 91 }, [], '')[0].color, 'var(--green)');
assert.deepEqual(dimensionRows(null, [], ''), [], 'a dimension the review does not carry is left out, never shown as 0');
assert.equal(dimensionRows({ grammar: 40 }, [], '')[0].color, 'var(--red)');

// --- findings follow the live draft: open while their words stand, fixed once they are gone ---
const first = essay.priorityIssues[0];
assert.equal(findingIsOpen(first, essay.text), true);
const applied = applyFix(essay.text, first);
assert.ok(applied, 'the fragment occurs once: the fix applies');
assert.equal(findingIsOpen(first, applied.text), false, 'applied: fixed');
assert.match(applied.text, /I like swimming in the sea/);
assert.deepEqual(dimensionRows(essay.dimensions, allIssues(essay), applied.text)[0].note, null, 'the fix moves the grammar note back to none (71 < 80)');
assert.equal(applyFix('x go x go', { fragment: 'go', correction: 'goes' }), null, 'a repeated quotation leaves the learner to choose');

// --- segments: findings and strengths, anchored once each on the LIVE draft, never overlapping ---
const segments = buildSegments(essay, essay.text);
assert.equal(segments.map((s) => s.text).join(''), essay.text, 'segments reconstruct the exact text, nothing dropped or duplicated');
assert.deepEqual(segments.filter((s) => s.kind !== 'plain').map((s) => [s.kind, s.text]), [
  ['priority', 'I like swim in the sea'],
  ['strength', 'In the evening, we watched the sunset together'],
  ['other', 'go their again'],
]);
assert.equal(segments.find((s) => s.kind === 'priority').issue.id, first.id);
// A dismissed finding is no longer marked.
assert.equal(buildSegments(essay, essay.text, new Set([first.id])).some((s) => s.kind === 'priority'), false);
// After a fix the card shows the learner's own new words, the other findings still marked.
const afterFix = buildSegments(essay, applied.text);
assert.equal(afterFix.map((s) => s.text).join(''), applied.text);
assert.equal(afterFix.some((s) => s.kind === 'priority'), false);
assert.equal(afterFix.some((s) => s.kind === 'other'), true);
// Words that appear nowhere (or twice) mark nothing: a highlight is earned.
const noMatch = mapEssay({ ...detail, issues: [{ id: 'i', priority: 'high', quote: 'not in the text', suggestion: 'x', why: 'y' }] }, null);
assert.equal(buildSegments(noMatch, noMatch.text).some((s) => s.kind === 'priority'), false);
assert.deepEqual(buildSegments(null, ''), []);
assert.deepEqual(buildSegments(null, 'plain words'), [{ kind: 'plain', text: 'plain words' }]);

// --- a finding's popover line: the first sentence of the reason ---
assert.equal(firstSentence('“Weekend” is singular. Readers notice this at once.'), '“Weekend” is singular.');
assert.equal(firstSentence('Sau like dùng V-ing.'), 'Sau like dùng V-ing.');
assert.equal(firstSentence('主语是单数，动词要变化。后面还有一句。'), '主语是单数，动词要变化。', 'a CJK full stop ends a sentence without a space');
assert.equal(firstSentence('No terminator here'), 'No terminator here');
assert.equal(firstSentence(''), '');

// --- "Today 09:12": the words for today/yesterday come from Intl, in the interface language ---
{
  const now = new Date(2026, 8, 29, 15, 0, 0);
  const at = (day, hour, minute) => new Date(2026, 8, day, hour, minute, 0).toISOString();
  assert.match(whenLabel(at(29, 9, 12), 'en', now), /^Today 0?9:12/);
  assert.match(whenLabel(at(28, 21, 40), 'en', now), /^Yesterday /);
  assert.match(whenLabel(at(20, 10, 5), 'en', now), /Sep 20/);
  assert.match(whenLabel(at(29, 9, 12), 'vi', now), /^Hôm nay /);
  assert.match(whenLabel(at(29, 9, 12), 'zh', now), /^今天/);
  assert.equal(whenLabel('', 'en', now), '');
  assert.equal(whenLabel('not a date', 'en', now), '');
}

// --- save state: both are saved (the frame's green); the words say where ---
assert.equal(saveTone('account').key, 'savedAccount');
assert.equal(saveTone('device').key, 'savedDevice');
assert.equal(saveTone('anything-else').key, 'savedDevice');
assert.equal(saveTone('device').color, 'var(--green)');

// --- the same model over a review captured from the running stack (a local evaluator, its own
//     wording: overlapping findings, no demonstrated band) ---
{
  const liveDetail = load('writing_essay_detail_live.json');
  const liveReview = load('writing_essay_review_live.json');
  const live = mapEssay(liveDetail, liveReview);
  assert.equal(live.id, 9);
  assert.equal(live.revisionNo, 2);
  assert.equal(live.level, 'B1');
  assert.equal(live.range, '', 'no demonstrated band: the range line has nothing real to say and is not drawn');
  assert.equal(live.canCompare, true);
  assert.equal(live.priorityIssues.length, 1);
  assert.equal(live.otherIssues.length, 3);
  assert.deepEqual(allIssues(live).map((i) => i.categoryKey), ['cat_article', 'cat_tense', 'cat_tense', 'cat_punctuation']);
  assert.deepEqual(allIssues(live).map((i) => i.kind), ['grammar', 'grammar', 'grammar', 'punctuation']);
  assert.equal(allIssues(live).find((i) => i.kind === 'punctuation').kindKey, 'kindPunctuation');
  const liveSegments = buildSegments(live, live.text);
  assert.equal(liveSegments.map((x) => x.text).join(''), live.text, 'overlapping findings never duplicate or drop a word');
  assert.ok(liveSegments.some((x) => x.kind === 'priority'));
  const liveRows = dimensionRows(live.dimensions, allIssues(live), live.text);
  assert.deepEqual(liveRows.map((r) => r.pct), ['65%', '60%', '65%', '60%']);
  const stillStanding = allIssues(live).filter((i) => i.kind === 'grammar' && live.text.includes(i.fragment)).length;
  assert.ok(stillStanding > 0 && stillStanding < 3, 'one of the three grammar-kind findings is not literally in the draft (the wording differs)');
  assert.deepEqual(liveRows[0].note, { key: 'dimFixes', n: stillStanding }, 'the note counts only findings whose words still stand');
  assert.equal(mapEssay(load('writing_essay_detail_v1_live.json'), null).latestId, 9, 'the first version of the live series opens on its latest');
}

// --- the copy: every category the evaluator can name has its label, the refusal is honest in every
//     language it is read in (the real unit, the real number, no "10") ---
{
  const store = new Map();
  globalThis.window = { localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) } };
  Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US' }, configurable: true });
  globalThis.document = { documentElement: { lang: 'en', dataset: {} } };
  const copy = await import('../static/orena/copy/index.js');
  const { t } = await import('../static/orena/screens/writing/copy.js');
  const said = {
    en: { tooShortWords: 'Write at least 2 words to request a review.', tooShortHan: 'Write at least 2 Hanzi to request a review.' },
    vi: { tooShortWords: 'Viết ít nhất 2 từ để yêu cầu nhận xét.', tooShortHan: 'Viết ít nhất 2 chữ Hán để yêu cầu nhận xét.' },
    zh: { tooShortWords: '至少写 2 个词才能请求点评。', tooShortHan: '至少写 2 个汉字才能请求点评。' },
  };
  // A system note follows the INTERFACE language, whatever the support language is (W-08, D-139 HD-14).
  for (const ui of ['en', 'vi', 'zh']) {
    copy.setLanguages({ ui, support: 'en' });
    for (const [key, sentence] of Object.entries(said[ui])) {
      assert.equal(t.plural(key, 2), sentence, `${ui} ${key}`);
      assert.ok(!/10/.test(t.plural(key, 2)), `${ui} ${key} no longer says ten`);
    }
  }
  copy.setLanguages({ ui: 'en', support: 'en' });
  assert.equal(t.plural('tooShortWords', 1), 'Write at least 1 word to request a review.', 'a minimum of one reads as one');
  // The notice a learner is shown is the one for the unit their language is written in.
  const { key, n } = tooShortNotice('zh');
  assert.equal(t.plural(key, n), said.en.tooShortHan);

  const english = { ui: 'en', support: 'en' };
  for (const locale of [english, { ui: 'vi', support: 'vi' }, { ui: 'zh', support: 'zh' }]) {
    copy.setLanguages(locale);
    for (const id of CATEGORY_IDS) {
      const label = t(`cat_${id}`);
      assert.ok(label && label !== `cat_${id}`, `${locale.ui}: a label for the "${id}" finding category`);
    }
    // The frame's plurals: "1 fix" / "2 fixes"; vi and zh have one form.
    assert.ok(t.plural('dimFixes', 1).includes('1') && t.plural('dimFixes', 2).includes('2'), `${locale.ui} dimFixes`);
    assert.ok(t('estimatedRange', { range: 'B1' }).includes('B1'), `${locale.ui}: the range placeholder survives`);
    assert.ok(t.plural('priorityIssues', 0).includes('0'), `${locale.ui}: zero findings read as 0`);
  }
  copy.setLanguages(english);
  assert.equal(t.plural('dimFixes', 1), '1 fix');
  assert.equal(t.plural('dimFixes', 2), '2 fixes');
  assert.equal(t('whyTab'), 'WHY');
  assert.equal(t('appliedCheck'), 'Applied ✓');
  assert.equal(t('appliedToast'), 'Applied — re-review to update the findings');
}

/* LEX-054/057/060: the intent kept with a draft, the draft set aside by "Start new draft", the one that waits. */
{
  const m = await import('../static/orena/screens/writing/model.js');
  const ex = {
    'expression:free': '', 'expression:free::parked': 'expression:parked:a,expression:parked:b',
    'expression:parked:a': 'old words here', 'expression:parked:a::task': 'Old task',
    'expression:parked:b': '', 'expression:parked:b::task': 'bare task',
    'expression:parked:a::intent': m.intentRecord({ register: 'formal', target: 250, free: false }),
  };
  assert.deepEqual(m.parkedKeys(ex), ['expression:parked:a', 'expression:parked:b']);
  const w = m.waitingDraft(ex, 'en');
  assert.equal(w.key, 'expression:parked:a', 'a draft set aside waits when the current slot holds no words');
  assert.equal(w.title, 'Old task');
  assert.equal(w.n, 3);
  assert.equal(m.waitingDraft({ ...ex, 'expression:free': 'now', 'expression:free::intent': m.intentRecord({ free: true }) }, 'en').free, true, 'the current draft wins and keeps its blank-page flag');
  assert.deepEqual(m.readIntent(ex, 'expression:parked:a'), { register: 'formal', target: 250, level: '', free: false });
  assert.deepEqual(m.readIntent({ 'k::intent': '{bad' }, 'k'), { register: '', target: 0, level: '', free: false }, 'a damaged record reads as no intent');
  assert.equal(m.saveTone('saving').key, 'savingNow');
  assert.equal(m.saveTone('account').key, 'savedAccount');
  assert.equal(m.saveTone('device').key, 'savedDevice');
}

{
  const ex = {
    'expression:parked:a': 'one two', 'expression:parked:a::task': 'First',
    'expression:parked:b': '我去了车站', 'expression:parked:b::intent': JSON.stringify({ free: true }),
    'expression:free::parked': 'expression:parked:a,expression:parked:b',
  };
  const list = (await import('../static/orena/screens/writing/model.js')).earlierDrafts(ex, 'zh');
  assert.deepEqual(list.map((d) => d.key), ['expression:parked:b', 'expression:parked:a']);
  assert.equal(list[0].free, true);
  assert.equal(list[1].title, 'First');
}

console.log('Orena Writing screen model: PASS');
