/* Gate for the Grammar surface on Grammar Lab content (D-100): the data seam
   product/grammar-source.js, screens/grammar/model.js (Grammar Library, frame 44) and
   screens/grammar-concept/model.js (Grammar Concept, frame 47), mapped from the grammar content
   contract (docs/project/GRAMMAR_CONTENT_CONTRACT.md, schema v0.4).

   The data here is scripts/fixtures/grammar/ - TEST-ONLY, built from the contract's own JSON and
   in-text examples, never learner content and never shipped (asserted below). No DOM, no fetch:
   the seam's reader takes an injected fetchJson.

   The last block keeps the R5 capability check (capabilities/grammar-pedagogy.js) this gate has
   always carried: R5 modules and their gates stay until their readers are replaced (D-100 point 5). */
import assert from 'node:assert/strict';
import fs from 'node:fs';

const fixture = (name) => JSON.parse(fs.readFileSync(new URL(`./fixtures/grammar/${name}`, import.meta.url), 'utf8'));
const catalogEn = fixture('catalog.en.json');
const catalogZh = fixture('catalog.zh.json');
const pointPP = fixture('points/en.present_perfect_experience.json');
const pointPlural = fixture('points/en.plural_nouns.json');
const pointGuo = fixture('points/zh.guo_experience.json');
const pointBa = fixture('points/zh.ba_sentence.json');

// The copy tables register through copy/index.js, which reads the device at import time.
{
  const store = new Map();
  globalThis.window = { localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) } };
  Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US' }, configurable: true });
  globalThis.document = { documentElement: { lang: 'en', dataset: {} } };
}

const source = await import('../static/orena/product/grammar-source.js');
const library = await import('../static/orena/screens/grammar/model.js');
const concept = await import('../static/orena/screens/grammar-concept/model.js');
const { CATALOG_URL, PROGRESS_URL, pointUrl, grammarCatalog, grammarPoint, grammarProgress, recordGrammarCompletion, contractText, levelCode, targetOfId } = source;

// The canonical contract uses zh-Hans in authored content, while profile/UI
// language remains zh. It must never render Chinese as English or lose its gloss.
assert.equal(contractText({ vi: 'Trải nghiệm', en: 'Experience', 'zh-Hans': '经历' }, 'zh'), '经历');
assert.equal(contractText({ vi: 'Trải nghiệm', en: 'Experience', 'zh-Hans': '经历' }, 'zh-Hans'), '经历');
assert.equal(concept.headerOf({ target_lang: 'zh-Hans', header: { native_title: '过' } }).lang, 'zh');
assert.equal(concept.mistakeOf({ common_mistakes: [
  { wrong: 'first', right: 'first fixed', l1: ['vi'] },
  { wrong: 'second', right: 'second fixed', l1: ['en', 'zh-Hans'] },
] }, 'en', 'en').wrong, 'second', 'canonical l1 arrays select the learner-specific mistake');

const notFound = () => Object.assign(new Error('Request failed (404)'), { status: 404 });
function stubFetch(files) {
  const calls = [];
  const fetchJson = async (url) => {
    calls.push(url);
    if (url in files) return structuredClone(files[url]);
    throw notFound();
  };
  return { fetchJson, calls };
}
// The Grammar Store's learner API shapes (writing_coach/grammar_api.py): the catalogue of the session's
// language, one point with its published version, an old R5 id answered by the server's R5 map.
const catalogBody = (language, points) => ({ language, catalog_revision: 'r1', functions: [], levels: [], points });
const pointBody = (point) => ({ point, version: 1, content_hash: 'h' });
const servedEn = {
  [CATALOG_URL]: catalogBody('en', catalogEn),
  [pointUrl('en.present_perfect_experience')]: pointBody(pointPP),
  [pointUrl('en.plural_nouns')]: pointBody(pointPlural),
  [pointUrl('test-r5-present-perfect')]: { language: 'en', point: null, redirect: 'en.present_perfect_experience' },
};
const servedZh = {
  [CATALOG_URL]: catalogBody('zh', catalogZh),
  [pointUrl('zh.guo_experience')]: pointBody(pointGuo),
  [pointUrl('zh.ba_sentence')]: pointBody(pointBa),
};

// --- The seam: no content today, contract-shaped content when it is served -------------------
{
  assert.equal(fs.existsSync('static/orena/content/grammar'), false, 'no grammar content ships to learners yet: the seam reads nothing and the test-only fixture stays under scripts/');
  for (const screen of ['grammar', 'grammar-concept']) {
    const src = fs.readFileSync(`static/orena/screens/${screen}/screen.js`, 'utf8');
    assert.doesNotMatch(src, /infrastructure\/api\.js|api\.grammar|completeGrammar|grammar-pedagogy|grammar-shelf/, `${screen}: no R5 read or write is left on the rebuilt screen`);
    assert.match(src, /product\/grammar-source\.js/, `${screen}: reads through the one grammar seam`);
  }

  const empty = stubFetch({});
  assert.deepEqual(await grammarCatalog('en', empty), [], 'a catalogue that is not there is an empty catalogue, not an error');
  assert.deepEqual(empty.calls, ['/api/grammar/v1/points'], 'the catalogue is the learner API, never a static file');
  assert.deepEqual(await grammarPoint('en.present_perfect_experience', empty), { point: null }, 'a point that is not there is "not found"');

  const failing = { fetchJson: async () => { throw Object.assign(new Error('boom'), { status: 500 }); } };
  await assert.rejects(grammarCatalog('en', failing), /boom/, 'any other failure is a load error for the router, never an empty catalogue');

  const withDraft = stubFetch({ [CATALOG_URL]: catalogBody('en', [...catalogEn, { ...catalogEn[0], id: 'en.draft', status: 'draft_ai' }]) });
  const rows = await grammarCatalog('en', withDraft);
  assert.deepEqual(rows.map((row) => row.id), ['en.plural_nouns', 'en.present_perfect_experience'], 'only approved rows, sorted by level.rank, function, sequence (§9)');

  const zhRows = await grammarCatalog('zh', stubFetch(servedZh));
  assert.deepEqual(zhRows.map((row) => row.id), ['zh.guo_experience', 'zh.ba_sentence'], 'HSK 2 before HSK 3');
  assert.deepEqual(await grammarCatalog('en', stubFetch(servedZh)), [], 'another language\'s catalogue is never drawn');

  const found = await grammarPoint('zh.ba_sentence', { targetLang: 'zh', ...stubFetch(servedZh) });
  assert.equal(found.point.id, 'zh.ba_sentence');
  assert.equal(found.version, 1, 'the published version comes with the point');
  const draft = stubFetch({ [pointUrl('en.present_perfect_experience')]: pointBody({ ...pointPP, status: 'flagged' }) });
  assert.deepEqual(await grammarPoint('en.present_perfect_experience', draft), { point: null }, 'a point that is not approved never reaches the screen (§0)');
  const other = stubFetch(servedZh);
  assert.deepEqual(await grammarPoint('zh.ba_sentence', { targetLang: 'en', ...other }), { point: null }, 'a point of the other language is not asked for');
  assert.deepEqual(other.calls, []);

  assert.deepEqual(await grammarPoint('test-r5-present-perfect', { targetLang: 'en', ...stubFetch(servedEn) }), { point: null, redirect: 'en.present_perfect_experience' }, 'an old R5 id is resolved by the server to the new id (§9 rule 1)');
  assert.deepEqual(await grammarPoint('a1-unknown-r5-id', { targetLang: 'en', ...stubFetch(servedEn) }), { point: null }, 'an R5 id with no replacement is not found, never guessed');
  assert.deepEqual(await grammarPoint('a1-dropped', { targetLang: 'en', ...stubFetch({ [pointUrl('a1-dropped')]: { language: 'en', point: null, dropped: true } }) }), { point: null }, 'a dropped R5 id is not found');

  // Progress: read as an addition (a failure is no progress), written with the answers in quick_practice order.
  const progress = stubFetch({ [PROGRESS_URL]: { language: 'en', progress: [{ point_id: 'en.plural_nouns', completed_at: 't', last_quiz: { correct: 2, total: 3 }, via: 'point' }] } });
  assert.deepEqual((await grammarProgress(progress)).map((row) => row.point_id), ['en.plural_nouns']);
  assert.deepEqual(await grammarProgress({ fetchJson: async () => { throw Object.assign(new Error('down'), { status: 503 }); } }), []);
  const sent = [];
  await recordGrammarCompletion('en.plural_nouns', [1, null, 0], { send: async (url, body) => sent.push([url, body]) });
  assert.deepEqual(sent, [['/api/grammar/v1/progress/en.plural_nouns', { answers: [1, null, 0] }]], 'the answers are sent, never a score');
  const quiz = concept.quizOf({ quick_practice: [
    { q: 'kept', options: [{ text: 'a' }, { text: 'b' }], answer: 1 },
    { q: '', options: [{ text: 'a' }, { text: 'b' }], answer: 0 },
    { q: 'kept too', options: [{ text: 'a' }, { text: 'b' }], answer: 0 },
  ] });
  assert.deepEqual(quiz.map((question) => question.index), [0, 2], 'a question left out keeps the others at their quick_practice place');
  const conceptSrc = fs.readFileSync('static/orena/screens/grammar-concept/screen.js', 'utf8');
  assert.match(conceptSrc, /recordGrammarCompletion\(view\.id, answers\)/, 'finishing the quiz records completion through the seam');
  assert.equal(targetOfId('zh.ba_sentence'), 'zh');
  assert.equal(targetOfId('a2-present-perfect'), '');
}

// --- Locale maps: support language, `en` the fallback, never `vi` (contract "Locale") ---------
{
  assert.equal(contractText({ vi: 'trải nghiệm', en: 'experience' }, 'vi'), 'trải nghiệm');
  assert.equal(contractText({ vi: 'trải nghiệm', en: 'experience' }, 'zh'), 'experience', 'zh is a later batch: a missing zh reads en');
  assert.equal(contractText({ vi: 'trải nghiệm', en: 'experience', zh: '经历' }, 'zh'), '经历');
  assert.equal(contractText({ vi: 'trải nghiệm', en: 'experience' }, 'fr'), 'experience', 'a support language with no key reads en');
  assert.equal(contractText({ vi: 'chỉ có vi' }, 'en'), '', 'never a silent fall back to vi');
  assert.equal(contractText({ vi: 'chỉ có vi' }, 'zh'), '');
  assert.equal(contractText('She has been', 'vi'), 'She has been', 'a plain string is target-language material');
  assert.equal(contractText(null), '');
}

// --- Levels: CEFR A1-C2 and HSK 3.0 1-9 (contract §0) ----------------------------------------
{
  assert.equal(levelCode({ framework: 'cefr', value: 'B1', rank: 3 }), 'B1');
  assert.equal(levelCode({ framework: 'hsk3', value: 3, rank: 3 }), 'HSK 3');
  assert.equal(levelCode({}), '');
  assert.equal(library.levelTile({ framework: 'hsk3', value: 7, rank: 7 }), 'HSK7', 'the level button and hero hold the short code');
}

// --- Grammar Library (design export 2026-10-08: hero, levels, continue, categories, category panel, all topics) ------
{
  const t = (key) => key;
  // The card: native_title, its reading, the support-language gloss (header.sub, else header.title).
  const one = library.buildLibrary({ rows: catalogEn, support: 'vi', t });
  assert.deepEqual(one.levels.map((level) => [level.key, level.count]), [['A1', 1], ['A2', 1]], 'one level per corpus level, in level.rank order, with its count');
  assert.equal(one.level.key, 'A1', 'with no declared level the first level is shown');
  const a2 = library.buildLibrary({ rows: catalogEn, support: 'vi', current: 'A2', t });
  assert.equal(a2.level.key, 'A2', "the learner's declared level is the one shown");
  const pp = a2.continue[0];
  const ppRow = catalogEn.find((row) => row.id === pp.id);
  assert.equal(pp.title, 'Present perfect', 'the title is header.native_title (§1), never header.title');
  assert.equal(pp.lang, 'en');
  assert.equal(pp.reading, '', 'an English point has no reading');
  assert.equal(pp.mean, ppRow.header.sub?.vi || ppRow.header.title.vi, 'the meaning line is header.sub (else header.title) in the support language');
  assert.equal(library.buildLibrary({ rows: [], t }).level, null, 'no content is no level');
  assert.equal(library.buildLibrary({ t }).level, null);
  const zh = library.buildLibrary({ rows: catalogZh, support: 'vi', t });
  assert.deepEqual(zh.levels.map((level) => level.key), ['HSK2', 'HSK3'], 'a Chinese library offers HSK 3.0 levels');
  assert.equal(zh.continue[0].title, '过');
  assert.equal(zh.continue[0].reading, 'guo', 'native_title_pinyin is the reading line');
  assert.equal(zh.continue[0].lang, 'zh');

  // A synthetic level: five points over three functions (test-only rows).
  const lv = { framework: 'cefr', value: 'B1', rank: 3 };
  const row = (id, fn, seq, sub) => ({ id: `en.${id}`, level: lv, function: fn, sequence: seq, header: { native_title: id, title: { vi: `t ${id}`, en: `t ${id}` }, sub: sub ? { vi: sub, en: sub } : undefined } });
  const rows = [row('a1', 'fn.time', 1, 'past'), row('a2', 'fn.time', 2), row('a3', 'fn.time', 3), row('b1', 'fn.link', 1), row('c1', '', 1)];
  const functions = [{ id: 'fn.link', title: { vi: 'Nối ý', en: 'Linking' } }, { id: 'fn.time', title: { vi: 'Thời gian', en: 'Time' } }];
  const progress = [{ point_id: 'en.a1', last_quiz: { correct: 2, total: 3 } }, { point_id: 'en.b1' }];
  const base = { rows, functions, progress, current: 'B1', support: 'vi', t };
  const view = library.buildLibrary(base);
  assert.deepEqual(view.stats, { total: 5, learned: 2, notStarted: 3 }, 'the hero counts learned (completed) and not started; no "learning" state is invented');
  assert.deepEqual(view.continue.map((item) => item.id), ['en.c1', 'en.a2', 'en.a3'], 'continue: the next not-yet-learned points of the level in catalogue order, at most three');
  assert.deepEqual(view.categories.map((c) => [c.name, c.count, c.examples.join(',')]), [['Nối ý', 1, 'b1'], ['Thời gian', 3, 'a1,a2,a3'], ['otherTopic', 1, 'c1']], "categories: the level's functions, in the catalogue's functions order, with counts and examples");
  assert.deepEqual(view.categories.map((c) => c.hue), ['var(--gcat-1)', 'var(--gcat-2)', 'var(--gcat-3)'], "a function takes the design hue of its place in the catalogue's list");
  assert.equal(library.buildLibrary({ ...base, rows: rows.filter((r) => r.function === 'fn.time') }).categories[0].hue, 'var(--gcat-2)', 'so a function keeps its hue at every level');
  assert.equal(view.panel.id, 'fn.link', 'the open category defaults to the first');
  const learned = view.all.find((item) => item.id === 'en.a1');
  assert.deepEqual([learned.learned, learned.score, learned.mean, learned.tag], [true, { correct: 2, total: 3 }, 'past', 'Thời gian']);
  assert.equal(view.all.find((item) => item.id === 'en.a2').mean, 't a2', 'no header.sub: the title gloss');
  const time = library.buildLibrary({ ...base, state: { cat: 'fn.time', all: 'fn.time' } });
  assert.deepEqual([time.panel.id, time.panelItems.length, time.allCat, time.all.length], ['fn.time', 3, 'fn.time', 3], 'a chosen category opens in the panel; an "all" chip narrows all topics');
  assert.deepEqual(library.buildLibrary({ ...base, state: { st: 'L' } }).all.map((i) => i.id).sort(), ['en.a1', 'en.b1'], 'status filter: learned');
  assert.equal(library.buildLibrary({ ...base, state: { st: 'N' } }).all.length, 3, 'status filter: not started');
  assert.deepEqual(library.buildLibrary({ ...base, state: { q: 'PAST' } }).all.map((i) => i.id), ['en.a1'], 'search reads title, reading and glosses, case-insensitively');
  assert.deepEqual(library.buildLibrary({ ...base, state: { sort: 'st' } }).all.map((i) => i.learned), [false, false, false, true, true], 'sort by status: not started first');
  assert.deepEqual(library.buildLibrary({ ...base, state: { sort: 'az' } }).all.map((i) => i.id), ['en.a1', 'en.a2', 'en.a3', 'en.b1', 'en.c1'], 'sort A-Z');
  const none = library.buildLibrary({ ...base, state: { q: 'zzz' } });
  assert.deepEqual([none.all.length, none.panelItems.length, none.filtering], [0, 0, true], 'filters that match nothing empty the panel and the list');
  assert.equal(library.buildLibrary({ ...base, state: { cat: 'fn.nope', all: 'fn.nope', level: 'C9' } }).allCat, 'all', 'unknown address values fall back');
  const all = library.buildLibrary({ ...base, progress: rows.map((r) => ({ point_id: r.id })) });
  assert.equal(all.continue.length, 0, 'a learned level has nothing to continue');

  const src = fs.readFileSync('static/orena/screens/grammar/screen.js', 'utf8');
  assert.doesNotMatch(src, /bookmark/i, 'no bookmark is drawn: nothing stores it (G-14)');
  const css = fs.readFileSync('static/orena/screens/grammar/grammar.css', 'utf8');
  assert.match(css, /\.s-gl \{\s*max-width: 1180px;/, 'the frame is 1180px wide');
  assert.match(css, /\.s-gl__level \{[^}]*min-width: 96px;\s*height: 48px;/, "the level button is the frame's 48px tab");
  assert.match(css, /\.s-gl__topicTitle \{\s*font-family: 'Noto Serif SC'[^}]*font-size: 21px;/, 'the topic title is Noto Serif SC 21');
}

// --- Grammar Concept (frame 47): an English timeline point ------------------------------------
{
  const view = concept.conceptView(pointPP, { support: 'vi', native: 'vi' });
  assert.equal(view.header.title, 'Present perfect', 'the title is native_title (§1)');
  assert.equal(view.header.level, 'A2');
  assert.equal(view.header.sub, 'trải nghiệm', '"Grammar · {level} · {sub}" takes header.sub in the support language');
  assert.equal(view.header.summary, 'Nói đã từng làm gì, không nêu thời điểm.');
  assert.deepEqual(view.pattern.map((cell) => cell.text), ['S', 'have/has', 'V3', '(for/since …)'], 'formula cells in order, the optional one in parentheses as the design draws "(now)"');
  assert.deepEqual(view.pattern.map((cell) => cell.bucket), ['k', 'a', 'b', 'm'], 'subject neutral, aux accent, verb green, time amber');
  assert.ok(view.pattern.every((cell) => !cell.text.includes(' + ')), 'the UI draws the joiner; no cell carries one');

  assert.equal(view.illustration.kind, 'timeline');
  assert.equal(view.illustration.caption, 'shapeUnspecifiedPast', 'the timeline is generated from `shape` alone');
  assert.deepEqual(view.illustration.marks.map((mark) => mark.key), ['markSomeTime']);

  const parts = view.examples[0].parts;
  assert.equal(parts.map((part) => part.text).join(''), 'I have lived here since 2020.', 'the parts rebuild the sentence exactly');
  assert.deepEqual(parts.filter((part) => part.bucket).map((part) => [part.text, part.bucket]), [['I', 'k'], ['have', 'a'], ['lived', 'b'], ['since 2020', 'm']], 'each span takes its cell\'s colour, so a formula cell and its words match');

  assert.deepEqual(view.mistake, { wrong: 'She has went to Japan twice.', wrongPinyin: null, right: 'She has been to Japan twice.', rightPinyin: null, reason: 'Trải nghiệm, không nêu thời điểm → has + V3.' });
  assert.equal(view.quiz.length, 1);
  assert.equal(view.quiz[0].answer, 0, 'answer is an index (§7), compared by index');
  assert.deepEqual(view.quiz[0].options.map((option) => option.text), ['has been', 'was', 'has went']);
  assert.deepEqual(view.tryIt, { prompt: 'Viết một câu về nơi bạn đã từng đến.', placeholder: 'I have been to …', sample: 'I have been to Da Nang twice.', samplePinyin: null });

  const en = concept.conceptView(pointPP, { support: 'en' });
  assert.equal(en.header.sub, 'experience');
  const zhSupport = concept.conceptView(pointPP, { support: 'zh' });
  assert.equal(zhSupport.header.summary, 'Say what you have done, without saying when.', 'no zh key yet: en, never vi');

  const bad = concept.exampleParts({ text: 'abcdef', spans: [{ start: 1, end: 3, role: 'verb' }, { start: 2, end: 4, role: 'aux' }, { start: 4, end: 99, role: 'time' }] });
  assert.deepEqual(bad.map((part) => [part.text, part.bucket]), [['a', null], ['bc', 'b'], ['def', null]], 'an overlapping or out-of-range span is ignored, never drawn wrong');
  assert.equal(concept.timelineOf('not_a_shape'), null, 'a shape this build cannot draw is no illustration');
  for (const shape of ['point_past', 'ongoing_now', 'unspecified_past', 'habit', 'future_condition', 'future_plan', 'past_ongoing']) {
    assert.ok(concept.timelineOf(shape), `the closed shape set is drawn: ${shape}`);
  }
}

// --- An English morphology point, a two-option question, no try-it block ----------------------
{
  const view = concept.conceptView(pointPlural, { support: 'en' });
  assert.equal(view.illustration.kind, 'morphology');
  assert.deepEqual(view.illustration.rows, [{ base: 'book', basePinyin: null, affix: '-s', result: 'books', resultPinyin: null, note: '' }]);
  assert.equal(view.quiz[0].options.length, 2, 'two options when there is one real error (§7)');
  assert.deepEqual(view.examples, []);
  assert.equal(view.mistake, null);
  assert.equal(view.tryIt, null, 'no personal_production block, no card (§7b)');
}

// --- Chinese: pinyin per character, word order boxes, the l1 choice of the mistake ------------
{
  const guo = concept.conceptView(pointGuo, { support: 'vi', native: 'vi' });
  assert.equal(guo.header.lang, 'zh');
  assert.equal(guo.header.level, 'HSK 2');
  assert.deepEqual(guo.header.titlePinyin, ['guo']);
  const parts = guo.examples[0].parts;
  assert.deepEqual(parts.map((part) => [part.text, part.pinyin]), [['他', ['tā']], ['吃', ['chī']], ['过', ['guo']], ['越南菜', ['yuè', 'nán', 'cài']], ['。', ['']]], 'pinyin is cut with the same character positions as the spans');
  assert.equal(guo.quiz[0].qPinyin.length, Array.from(guo.quiz[0].q).length);
  assert.deepEqual(guo.quiz[0].options.map((option) => option.pinyin), [['méi'], ['bù']]);
  assert.deepEqual(guo.tryIt.samplePinyin, ['wǒ', 'chī', 'guo', 'yuè', 'nán', 'cài', '']);

  const ba = concept.conceptView(pointBa, { support: 'en', native: 'en' });
  assert.equal(ba.illustration.kind, 'word_order');
  assert.deepEqual(ba.illustration.boxes.map((box) => [box.text, box.label]), [['主语', 'subject'], ['把', 'the marker 把'], ['宾语', 'object'], ['动词', 'verb'], ['补语', 'complement']], 'word order draws the formula cells as boxes in order, labelled');
  assert.equal(ba.mistake.wrong, '我把书看。', 'the entry whose l1 is the learner\'s native language');
  assert.equal(concept.conceptView(pointBa, { support: 'vi', native: 'vi' }).mistake.wrong, '我看完了把书。');
  assert.equal(concept.conceptView(pointBa, { support: 'en', native: 'fr' }).mistake.wrong, '我把书看。', 'no l1 match: the first entry');
  assert.deepEqual(ba.quiz, [], 'no quick_practice, no quiz card');
  assert.equal(ba.tryIt, null);
  assert.equal(concept.roleBucket('classifier'), 'a');
  assert.equal(concept.roleBucket('nonsense'), 'k');
}

// --- Grammar Concept renders the corpus fields the API returns, in learning order --------------
// The ZH point below is shaped like a real `/api/grammar/v1/points/zh.le_completion` body (pinyin
// arrays, vi/en gloss maps, variants.negative/question, compare[] with `with`), cut down.
{
  const gloss = (vi, en) => ({ vi, en });
  const cell = (text, role, label, pinyin) => ({ text, role, label, pinyin });
  const pointLe = {
    id: 'zh.le_completion', target_lang: 'zh', level: { framework: 'hsk3', value: '2', rank: 2 },
    header: { native_title: '了', native_title_pinyin: ['le'], sub: gloss('hoàn thành', 'completion'), summary: gloss('了 báo hiệu việc đã xong.', '了 marks a finished action.') },
    when_to_use: [gloss('Khi việc đã xong.', 'When the action is finished.'), gloss('Khi có kết quả cụ thể.', 'When there is a concrete result.')],
    pattern: {
      formula: [cell('主语', 'subject', gloss('chủ ngữ', 'subject'), ['zhǔ', 'yǔ']), cell('动词', 'verb', gloss('động từ', 'verb'), ['dòng', 'cí']), cell('了', 'particle', gloss('trợ từ', 'particle'), ['le'])],
      variants: {
        negative: [cell('主语', 'subject', gloss('chủ ngữ', 'subject'), ['zhǔ', 'yǔ']), cell('没有', 'aux', gloss('phủ định', 'negation'), ['méi', 'yǒu']), cell('动词', 'verb', gloss('động từ', 'verb'), ['dòng', 'cí'])],
        question: [cell('主语', 'subject', gloss('chủ ngữ', 'subject'), ['zhǔ', 'yǔ']), cell('动词', 'verb', gloss('động từ', 'verb'), ['dòng', 'cí']), cell('了', 'particle', gloss('trợ từ', 'particle'), ['le']), cell('吗', 'particle', gloss('nghi vấn', 'question'), ['ma'])],
      },
      illustration: { kind: 'none' },
    },
    examples: [
      { text: '我买了书。', form: 'affirmative', spans: [{ start: 0, end: 1, role: 'subject' }, { start: 1, end: 2, role: 'verb' }, { start: 2, end: 3, role: 'particle' }], pinyin: ['wǒ', 'mǎi', 'le', 'shū', ''], translation: gloss('Tôi đã mua sách.', 'I bought a book.'), annotation: gloss('Việc đã xong.', 'The action is done.') },
      { text: '我没买书。', form: 'negative', spans: [], pinyin: ['wǒ', 'méi', 'mǎi', 'shū', ''], translation: gloss('Tôi chưa mua sách.', 'I did not buy a book.'), annotation: { vi: '', en: '' } },
    ],
    compare: [{ with: 'zh.guo_experience', this_meaning: gloss('了: đã xong.', '了: finished.'), this_example: '我买了书。', this_example_pinyin: ['wǒ', 'mǎi', 'le', 'shū', ''], other_meaning: gloss('过: từng.', '过: ever.'), other_example: '我去过北京。', other_example_pinyin: ['wǒ', 'qù', 'guo', 'běi', 'jīng', ''] }],
    common_mistakes: [
      { wrong: '我买书了了。', right: '我买了书。', reason: gloss('Một 了 là đủ.', 'One 了 is enough.'), l1: ['vi'], wrong_pinyin: null, right_pinyin: null },
      { wrong: '我昨天没买了书。', right: '我昨天没买书。', reason: gloss('Phủ định bỏ 了.', 'Drop 了 after 没.'), l1: ['en'] },
      { wrong: '', right: 'x', reason: gloss('bỏ', 'skip') },
    ],
    quick_practice: [{ q: '我买___书。', options: [{ text: '了', pinyin: ['le'] }, { text: '过', pinyin: ['guo'] }], answer: 0, explain: gloss('Việc đã xong dùng 了.', 'A finished action uses 了.') }],
    personal_production: { prompt: gloss('Viết một câu có 了.', 'Write a sentence with 了.'), placeholder: '我买了……', sample: { text: '我吃了饭。', pinyin: ['wǒ', 'chī', 'le', 'fàn', ''] } },
  };
  const ORDER = ['overview', 'pattern', 'examples', 'mistakes', 'compare', 'quiz', 'tryIt'];
  assert.deepEqual([...concept.SECTION_ORDER], ORDER, 'learning order: summary + when to use, pattern + variants, examples, mistakes, compare, quick practice, try it');

  const vi = concept.conceptView(pointLe, { support: 'vi', native: 'vi' });
  assert.deepEqual(concept.sectionsOf(vi), ORDER, 'a full point draws every section, in order');
  assert.deepEqual(vi.whenToUse, ['Khi việc đã xong.', 'Khi có kết quả cụ thể.']);
  assert.deepEqual(vi.variants.map((variant) => variant.form), ['negative', 'question'], 'only the forms the point declares');
  assert.deepEqual(vi.variants[1].cells.map((c) => c.text), ['主语', '动词', '了', '吗']);
  assert.equal(vi.examples[0].translation, 'Tôi đã mua sách.', 'translation in the support language');
  assert.equal(vi.examples[0].annotation, 'Việc đã xong.');
  assert.equal(vi.examples[1].annotation, '', 'an empty annotation is no line');
  assert.deepEqual(vi.mistakes.map((m) => m.wrong), ['我买书了了。'], 'the mistakes aimed at the learner\'s L1; one without wrong/right is dropped');
  assert.equal(vi.mistakes[0].reason, 'Một 了 là đủ.');
  assert.equal(vi.compare[0].withId, 'zh.guo_experience');
  assert.equal(vi.compare[0].thisMeaning, '了: đã xong.');
  assert.equal(vi.compare[0].otherExample, '我去过北京。');
  assert.deepEqual(vi.compare[0].otherExamplePinyin, ['wǒ', 'qù', 'guo', 'běi', 'jīng', '']);
  assert.equal(vi.quiz[0].explain, 'Việc đã xong dùng 了.', 'quick_practice explain in the support language');
  assert.equal(vi.tryIt.prompt, 'Viết một câu có 了.');

  const en = concept.conceptView(pointLe, { support: 'en', native: 'fr' });
  assert.deepEqual(en.mistakes.map((m) => m.wrong), ['我买书了了。', '我昨天没买了书。'], 'no mistake names the L1: all of them');
  assert.equal(en.examples[0].translation, 'I bought a book.');
  assert.equal(en.whenToUse[0], 'When the action is finished.');

  // The same on an English point shaped like the API (the contract's own fixture).
  const pp = concept.conceptView(pointPP, { support: 'en', native: 'en' });
  assert.deepEqual(concept.sectionsOf(pp), ORDER.filter((key) => key !== 'compare' || pp.compare.length), 'the EN point draws the sections it has data for');
  assert.ok(pp.examples.every((example) => example.translation), 'every EN example carries its translation');
  assert.ok(pp.variants.length > 0 && pp.compare.length > 0, 'EN fixture: variants and compare are rendered (the fixture has no when_to_use, so that section is omitted)');
  assert.ok(!concept.sectionsOf(pp).includes('overview') || pp.header.summary, 'overview needs a summary or a when_to_use line');

  // Sections with no data disappear: no heading, no placeholder.
  const bare = concept.conceptView({ id: 'x', target_lang: 'en', header: { native_title: 'X', summary: { en: 'Only a summary.' } } }, { support: 'en' });
  assert.deepEqual(concept.sectionsOf(bare), ['overview']);
  assert.deepEqual([bare.whenToUse, bare.variants, bare.examples, bare.mistakes, bare.compare, bare.quiz], [[], [], [], [], [], []]);
  assert.deepEqual(concept.sectionsOf(concept.conceptView({ id: 'y', header: { native_title: 'Y' }, pattern: { formula: [], variants: { negative: [] } }, compare: [{ with: 'a' }], when_to_use: [{}, ''] })), [], 'empty arrays and entries with no content draw nothing');
  assert.deepEqual(concept.sectionsOf(concept.conceptView({ id: 'z', header: { native_title: 'Z' }, when_to_use: [{ en: 'Only when to use.' }] })), ['overview']);
  assert.deepEqual(concept.sectionsOf(concept.conceptView({ ...pointLe, compare: [], pattern: { formula: pointLe.pattern.formula }, when_to_use: [] })), ['overview', 'pattern', 'examples', 'mistakes', 'quiz', 'tryIt'], 'no variants, no compare, no when_to_use: the rest keeps its order');

  // The screen reads these in this order and uses only kit tokens.
  const screenSrc = fs.readFileSync('static/orena/screens/grammar-concept/screen.js', 'utf8');
  assert.match(screenSrc, /sectionsOf\(view\)/, 'the screen draws what sectionsOf lists');
  const cssSrc = fs.readFileSync('static/orena/screens/grammar-concept/grammar-concept.css', 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
  assert.doesNotMatch(cssSrc, /#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(/, 'no colour literal in the Grammar Concept styles');
}

// --- Try it yourself never concludes the pattern was used (D-100 point 3) ----------------------
{
  const src = fs.readFileSync('static/orena/screens/grammar-concept/screen.js', 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
  const copySrc = fs.readFileSync('static/orena/screens/grammar-concept/copy.js', 'utf8');
  assert.doesNotMatch(copySrc, /evidence|pattern is right|you used|đã dùng đúng|用对/i, 'no copy claims the pattern was used or recorded');
  assert.doesNotMatch(src, /tryOk|evidence|--green-soft|s-gc__tryResult--/, 'the try-it result has no verdict state and writes nothing');
  assert.match(src, /tryIt\.sample/, 'after a submission the screen shows the contract sample');
}

// --- R5 capability (kept, D-100 point 5): a pattern-stage timeline block's own event text reaches
//     the archetype classifier (capabilities/grammar-pedagogy.js reads payload.events alongside
//     payload.parts/segments). Real block captured from GET /api/library/grammar/
//     a2-present-perfect-vs-past-simple, wrapped in a neutral id/title/kind. ----------------------
{
  const { classifyArchetype } = await import('../static/orena/capabilities/grammar-pedagogy.js');
  const realLesson = JSON.parse(fs.readFileSync(new URL('./fixtures/api/grammar_concept_library_grammar_lesson_timeline.json', import.meta.url)));
  const timelineBlock = realLesson.learning_model.blocks.find((block) => block.id === 'a2-time-view');
  assert.equal(timelineBlock?.type, 'timeline');
  assert.equal(timelineBlock?.stage, 'pattern');
  assert.equal(classifyArchetype({ id: 'x', title: 'x', kind: '', learning_model: { blocks: [timelineBlock] } }), 'temporal_aspect');
}

// Upstream PR68 corpus is draft-only, never a lesson catalogue. Exercise real
// model shapes without promoting these incomplete locale maps to approved.
{
  const base = 'tests/fixtures/grammar_content_samples/';
  const index = JSON.parse(fs.readFileSync(`${base}index.json`, 'utf8'));
  assert.equal(index.sample, true);
  assert.equal(index.approved, false);
  assert.equal(index.points.length, 13);
  const points = index.points.map((row) => JSON.parse(fs.readFileSync(`${base}${row.file}`, 'utf8')));
  assert.equal(points.filter((point) => point.target_lang === 'en').length, 10);
  assert.equal(points.filter((point) => point.target_lang === 'zh-Hans').length, 3);
  const functions = JSON.parse(fs.readFileSync(`${base}functions.json`, 'utf8'));
  for (const point of points) {
    assert.equal(point.status, 'draft_ai');
    assert.equal(point.schema_version, '0.4');
    assert.equal(point.id, index.points.find((row) => row.id === point.id).id);
    const view = concept.conceptView(point, { support: 'vi', native: 'vi' });
    assert.equal(view.header.title, point.header.native_title);
    assert.equal(view.header.lang, point.target_lang === 'zh-Hans' ? 'zh' : 'en');
    assert.ok(view.pattern.length && view.examples.length && view.quiz.length, point.id);
    assert.equal(view.quiz.length, point.quick_practice.length, `${point.id}: no question silently discarded`);
    for (const question of view.quiz) assert.ok(question.options.length >= 2);
    const stub = stubFetch({ [pointUrl(point.id)]: pointBody(point) });
    assert.deepEqual(await grammarPoint(point.id, { targetLang: view.header.lang, ...stub }), { point: null });
    for (const key of ['provenance', 'review', 'flags']) assert.equal(Object.hasOwn(point, key), false);
    const fn = functions.find((entry) => entry.id === point.function);
    assert.ok(fn, point.function);
    for (const locale of ['vi', 'en', 'zh-Hans']) assert.ok(fn.title[locale]);
  }
  for (const lang of ['en', 'zh']) {
    const stub = stubFetch({ [CATALOG_URL]: catalogBody(lang, index.points) });
    assert.deepEqual(await grammarCatalog(lang, stub), [], 'draft corpus stays outside admitted learning');
  }
}

console.log('Orena Grammar surface (Library + Concept) on the Grammar Store learner API: catalogue, point, R5 redirect, progress; fixtures test-only: PASS');

/* An example whose annotation repeats its translation word for word shows the line once (6 older EN points). */
{
  const { examplesOf } = await import('../static/orena/screens/grammar-concept/model.js');
  const same = { vi: 'Every morning cho biết đây là thói quen.', en: 'Every morning marks a habit.' };
  const [row] = examplesOf({ examples: [{ text: 'I drink coffee every morning.', translation: same, annotation: same }] }, 'vi');
  assert.equal(row.translation, same.vi);
  assert.equal(row.annotation, '', 'the repeated line is not drawn twice');
  console.log('Grammar Concept: a repeated example note is drawn once: PASS');
}
