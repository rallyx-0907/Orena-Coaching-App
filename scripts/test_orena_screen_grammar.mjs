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
  const { t: libraryT } = await import('../static/orena/screens/grammar/copy.js');
  const copy = await import('../static/orena/copy/index.js');
  const table = copy.registeredCopy().get('grammar');
  assert.equal(levelCode({ framework: 'cefr', value: 'B1', rank: 3 }), 'B1');
  assert.equal(levelCode({ framework: 'hsk3', value: 3, rank: 3 }), 'HSK 3');
  assert.equal(levelCode({}), '');
  assert.equal(library.levelTile({ framework: 'hsk3', value: 7, rank: 7 }), 'HSK7', 'the 44px tile holds the short code');
  for (let n = 1; n <= 9; n += 1) {
    const key = library.levelNameKey({ framework: 'hsk3', value: n });
    assert.equal(key, n <= 3 ? 'hskBand1' : n <= 6 ? 'hskBand2' : 'hskBand3', `HSK ${n} is in its HSK 3.0 band`);
    for (const locale of ['en', 'vi', 'zh']) assert.ok(table.packs[locale][key], `${key} is written in ${locale}`);
  }
  assert.equal(library.levelNameKey({ framework: 'hsk3', value: 10 }), '', 'HSK 3.0 stops at 9');
  for (const code of ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']) {
    const key = library.levelNameKey({ framework: 'cefr', value: code });
    assert.ok(key, `${code} has a name`);
    for (const locale of ['en', 'vi', 'zh']) assert.ok(table.packs[locale][key], `${key} is written in ${locale}`);
  }
  assert.equal(library.levelHeading({ framework: 'hsk3', value: 3 }, libraryT), 'HSK 3 · Elementary');
  assert.equal(library.levelHeading({ framework: 'cefr', value: 'B2' }, libraryT), 'B2 · Upper-intermediate');
  assert.equal(library.levelHeading({ framework: 'cefr', value: 'X9' }, libraryT), 'X9', 'an unknown level shows its code, never a guessed name');
}

// --- Grammar Library (frame 44, composed 2026-10-08): level filter, continue, topics, all by topic ----------------
{
  const t = (key, params) => (key === 'levelHeading' ? `${params.code} · ${params.name}` : key);
  // The card: native_title, the support-language gloss under it.
  const one = library.buildLibrary({ rows: catalogEn, support: 'vi', t });
  assert.deepEqual(one.levels.map((level) => level.key), ['A1', 'A2'], 'one level per corpus level, in level.rank order');
  assert.equal(one.level.key, 'A1', 'with no declared level the first level is shown');
  const a2 = library.buildLibrary({ rows: catalogEn, support: 'vi', current: 'A2', t });
  assert.equal(a2.level.key, 'A2', 'the learner\'s declared level is the one shown');
  assert.ok(a2.levels.find((level) => level.key === 'A2').current);
  const pp = a2.continue[0];
  assert.equal(pp.title, 'Present perfect', 'the card title is header.native_title (§1), never header.title');
  assert.notEqual(pp.title, catalogEn[0].header.title.vi);
  assert.equal(pp.note, 'Hiện tại hoàn thành (trải nghiệm)', 'the line under it is header.title in the support language');
  assert.equal(pp.lang, 'en');
  assert.equal(library.buildLibrary({ rows: catalogEn, support: 'zh', current: 'A2', t }).continue[0].note, 'Present perfect (experience)', 'a zh-support learner reads the en gloss, never the vi one');
  assert.equal(library.buildLibrary({ rows: [], t }).level, null, 'no content is no level');
  assert.equal(library.buildLibrary({ t }).level, null);

  const zh = library.buildLibrary({ rows: catalogZh, support: 'vi', t });
  assert.deepEqual(zh.levels.map((level) => level.heading), ['HSK 2 · hskBand1', 'HSK 3 · hskBand1'], 'a Chinese library offers HSK 3.0 levels');
  assert.equal(zh.continue[0].title, '过');
  assert.deepEqual(zh.continue[0].titlePinyin, ['guo'], 'native_title_pinyin travels with the Chinese title');
  assert.equal(zh.continue[0].lang, 'zh');

  // A synthetic level of five points over three topics (test-only rows).
  const lv = { framework: 'cefr', value: 'B1', rank: 3 };
  const row = (id, fn, seq) => ({ id: `en.${id}`, level: lv, function: fn, sequence: seq, header: { native_title: id, title: { vi: id, en: id } } });
  const rows = [row('a1', 'fn.time', 1), row('a2', 'fn.time', 2), row('a3', 'fn.time', 3), row('b1', 'fn.link', 1), row('c1', '', 1)];
  const functions = [{ id: 'fn.time', title: { vi: 'Thời gian', en: 'Time' } }, { id: 'fn.link', title: { vi: 'Nối ý', en: 'Linking' } }];
  const progress = [{ point_id: 'en.a1', last_quiz: { correct: 2, total: 3 } }, { point_id: 'en.b1' }];
  const view = library.buildLibrary({ rows, functions, progress, current: 'B1', support: 'vi', t });
  assert.deepEqual(view.continue.map((item) => item.id), ['en.c1', 'en.a2', 'en.a3'], 'continue: the not-yet-completed points of the level, in the catalogue order (function, sequence)');
  assert.deepEqual(view.topics.map((topic) => [topic.title, topic.count, topic.done]), [['Thời gian', 3, 1], ['Nối ý', 1, 1], ['otherTopic', 1, 0]], 'topics: the corpus functions by name in the support language, largest first, a point without one under "other"');
  assert.deepEqual(view.sections.map((section) => section.title), ['Thời gian', 'Nối ý', 'otherTopic'], 'all grammar: a section per topic, in the topics\' order');
  assert.equal(view.shown, 5);
  const done = view.sections[0].items[0];
  assert.deepEqual([done.done, done.score], [true, { correct: 2, total: 3 }], 'a completed point carries its last quiz score');
  assert.deepEqual([view.sections[1].items[0].done, view.sections[1].items[0].score], [true, null], 'completed without a quiz: done, no score');
  assert.equal(view.sections[0].items[1].done, false);
  const time = library.buildLibrary({ rows, functions, progress, current: 'B1', topic: 'fn.time', support: 'vi', t });
  assert.deepEqual([time.topic, time.sections.length, time.shown], ['fn.time', 1, 3], 'a chosen topic narrows all grammar to it');
  assert.equal(library.buildLibrary({ rows, functions, current: 'B1', topic: 'fn.nope', t }).topic, '', 'an unknown topic in the address is ignored');
  assert.equal(library.buildLibrary({ rows, functions, current: 'B1', selected: 'C9', t }).level.key, 'B1', 'an unknown level in the address falls back to the learner\'s');
  const all = library.buildLibrary({ rows, functions, progress: rows.map((r) => ({ point_id: r.id })), current: 'B1', t });
  assert.deepEqual([all.continue.length, all.levelComplete], [0, true], 'a completed level has nothing to continue');
  const many = Array.from({ length: 9 }, (_, i) => row(`m${i}`, 'fn.time', i));
  assert.equal(library.buildLibrary({ rows: many, current: 'B1', t }).continue.length, library.CONTINUE_LIMIT, 'continue is capped');

  const src = fs.readFileSync('static/orena/screens/grammar/screen.js', 'utf8');
  assert.match(src, /listRow\(\{[^}]*titleLineHeight:\s*20\b/, 'frame 44 draws the card title at line-height 20px');
  assert.doesNotMatch(src, /s-grammar__tile/, 'cards inside a level carry no repeated level tile');
  const css = fs.readFileSync('static/orena/screens/grammar/grammar.css', 'utf8');
  assert.match(css, /\.s-grammar__chip \{\s*height: 36px;\s*padding: 0 14px;\s*font-size: 13\.5px;/, 'the level chip is the design\'s Discover level chip');
  assert.match(css, /\.s-grammar__shead \{[^}]*padding-bottom: 10px;\s*border-bottom: 1px solid var\(--border\);/, 'sections use the design\'s grouped heading');
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
