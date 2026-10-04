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
const { CONTENT_BASE, grammarCatalog, grammarPoint, contractText, levelCode, targetOfId } = source;

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
const served = {
  [`${CONTENT_BASE}/catalog.en.json`]: catalogEn,
  [`${CONTENT_BASE}/catalog.zh.json`]: catalogZh,
  [`${CONTENT_BASE}/points/en.present_perfect_experience.json`]: pointPP,
  [`${CONTENT_BASE}/points/en.plural_nouns.json`]: pointPlural,
  [`${CONTENT_BASE}/points/zh.guo_experience.json`]: pointGuo,
  [`${CONTENT_BASE}/points/zh.ba_sentence.json`]: pointBa,
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
  assert.deepEqual(empty.calls, [`${CONTENT_BASE}/catalog.en.json`]);
  assert.deepEqual(await grammarPoint('en.present_perfect_experience', empty), { point: null }, 'a point that is not there is "not found"');

  const failing = { fetchJson: async () => { throw Object.assign(new Error('boom'), { status: 500 }); } };
  await assert.rejects(grammarCatalog('en', failing), /boom/, 'any other failure is a load error for the router, never an empty catalogue');

  const withDraft = stubFetch({ [`${CONTENT_BASE}/catalog.en.json`]: [...catalogEn, { ...catalogEn[0], id: 'en.draft', status: 'draft_ai' }] });
  const rows = await grammarCatalog('en', withDraft);
  assert.deepEqual(rows.map((row) => row.id), ['en.plural_nouns', 'en.present_perfect_experience'], 'only approved rows, sorted by level.rank, function, sequence (§9)');

  const zhRows = await grammarCatalog('zh', stubFetch(served));
  assert.deepEqual(zhRows.map((row) => row.id), ['zh.guo_experience', 'zh.ba_sentence'], 'HSK 2 before HSK 3');

  const found = await grammarPoint('zh.ba_sentence', stubFetch(served));
  assert.equal(found.point.id, 'zh.ba_sentence');
  const draft = stubFetch({ [`${CONTENT_BASE}/points/en.present_perfect_experience.json`]: { ...pointPP, status: 'flagged' } });
  assert.deepEqual(await grammarPoint('en.present_perfect_experience', draft), { point: null }, 'a point that is not approved never reaches the screen (§0)');

  assert.deepEqual(await grammarPoint('test-r5-present-perfect', { targetLang: 'en', ...stubFetch(served) }), { point: null, redirect: 'en.present_perfect_experience' }, 'an old R5 id resolves through `aliases` to the new id (§9 rule 1)');
  assert.deepEqual(await grammarPoint('a1-unknown-r5-id', { targetLang: 'en', ...stubFetch(served) }), { point: null }, 'an R5 id with no replacement is not found, never guessed');
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

// --- Grammar Library (frame 44): native_title on the card, the support-language gloss under it -
{
  const t = (key, params) => (key === 'levelHeading' ? `${params.code} · ${params.name}` : key);
  const groups = library.buildLibraryGroups(catalogEn, 'vi', t);
  assert.deepEqual(groups.map((group) => group.heading), ['A1 · cefrA1', 'A2 · cefrA2'], 'one group per level, in level.rank order');
  const pp = groups[1].items[0];
  assert.equal(pp.title, 'Present perfect', 'the card title is header.native_title (§1), never header.title');
  assert.notEqual(pp.title, catalogEn[0].header.title.vi);
  assert.equal(pp.note, 'Hiện tại hoàn thành (trải nghiệm)', 'the line under it is header.title in the support language');
  assert.equal(pp.lang, 'en');
  assert.equal(pp.tile, 'A2');
  assert.equal(groups[1].topics, 1, 'topics counts the group\'s `function` values');
  assert.equal(library.buildLibraryGroups(catalogEn, 'zh', t)[1].items[0].note, 'Present perfect (experience)', 'a zh-support learner reads the en gloss, never the vi one');
  assert.deepEqual(library.buildLibraryGroups([], 'en', t), [], 'no content is no groups');
  assert.deepEqual(library.buildLibraryGroups(undefined, 'en', t), []);

  const zh = library.buildLibraryGroups(catalogZh, 'vi', t);
  assert.deepEqual(zh.map((group) => group.heading), ['HSK 2 · hskBand1', 'HSK 3 · hskBand1'], 'a Chinese library groups by HSK 3.0 level');
  assert.equal(zh[0].items[0].title, '过');
  assert.deepEqual(zh[0].items[0].titlePinyin, ['guo'], 'native_title_pinyin travels with the Chinese title');
  assert.equal(zh[0].items[0].lang, 'zh');
  assert.equal(zh[1].items[0].tile, 'HSK3');

  const src = fs.readFileSync('static/orena/screens/grammar/screen.js', 'utf8');
  assert.match(src, /listRow\(\{[^}]*titleLineHeight:\s*20\b/, 'frame 44 draws the card title at line-height 20px');
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
    const stub = stubFetch({ [`${CONTENT_BASE}/points/${point.id}.json`]: point });
    assert.deepEqual(await grammarPoint(point.id, { targetLang: view.header.lang, ...stub }), { point: null });
    for (const key of ['provenance', 'review', 'flags']) assert.equal(Object.hasOwn(point, key), false);
    const fn = functions.find((entry) => entry.id === point.function);
    assert.ok(fn, point.function);
    for (const locale of ['vi', 'en', 'zh-Hans']) assert.ok(fn.title[locale]);
  }
  for (const lang of ['en', 'zh']) {
    const stub = stubFetch({ [`${CONTENT_BASE}/catalog.${lang}.json`]: index.points });
    assert.deepEqual(await grammarCatalog(lang, stub), [], 'draft corpus stays outside admitted learning');
  }
}

console.log('Orena Grammar surface (Library + Concept) on the grammar content contract, seam, fixtures test-only: PASS');
