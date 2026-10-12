/* Gate for the shared vocabulary card (D-178, D-179): the pure mapper
   (static/orena/product/vocabulary-card.js#toVocabularyModel) and the VocabularyCard markup per mode
   (static/orena/kit/vocabulary-card.js), on the two reference entries in docs/vocab/samples as the
   importer stores them, plus the shapes the screens already hold (a catalogue card, a saved item).

   Holds: the mapper is pure content (no learner state in, none out); EN and ZH carry their own
   fields; highlights find the exact span (EN whole word, ZH Hanzi) and the pinyin span only when it can
   be found, never the whole line; review-front shows nothing that answers the card; no image frame
   without an illustration; the two review buttons; every card label exists in en/vi/zh. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const store = new Map();
globalThis.window = { localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) } };
Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US' }, configurable: true });
globalThis.document = { documentElement: { lang: 'en', dataset: {} } };

const { toVocabularyModel, learnerState, highlightParts, highlightExample, frontFields, savePayloadOf } = await import('../static/orena/product/vocabulary-card.js');
const { vocabularyCard, CARD_MODES, posLabel } = await import('../static/orena/kit/vocabulary-card.js');
const { setLanguages } = await import('../static/orena/copy/index.js');
const { REVIEW_BUTTONS, GRADES } = await import('../static/orena/screens/review/model.js');

/* The reference samples as `writing_coach/vocabulary_entry_format.py` stores them (the canonical record): the
   fields below are exactly the adapter's output keys, so the gate reads what a stored entry carries. */
const sample = (name) => JSON.parse(readFileSync(new URL(`../docs/vocab/samples/${name}.json`, import.meta.url), 'utf8'));
function stored(record) {
  const zh = record.lang === 'zh-Hans';
  const language = zh ? 'zh' : 'en';
  const notes = [];
  for (const c of record.collocations || []) notes.push({ type: 'collocation', text: c, language });
  const relation = { family: 'word_family', synonym: 'synonym', antonym: 'antonym', related: 'related', compound: 'related' };
  for (const r of record.related || []) notes.push({ type: relation[r.relation], text: r.word, language, ...(r.pos ? { pos: r.pos } : {}), ...(r.reading ? { reading: r.reading } : {}), ...(r.gloss_vi ? { gloss: { vi: r.gloss_vi } } : {}) });
  for (const m of record.zh?.measure_words || []) notes.push({ type: 'classifier', text: m.mw, reading: m.pinyin, phrase: m.phrase, phrase_reading: m.phrase_pinyin, language });
  if (record.memory_tip_vi) notes.push({ type: 'memory_tip', text: record.memory_tip_vi, language: 'vi' });
  const units = (record.zh?.chars || []).map((c) => ({
    surface: c.hanzi, script: 'han', unit_kind: 'character',
    readings: [{ value: c.pinyin, notation: 'pinyin' }, ...(c.han_viet ? [{ value: c.han_viet, notation: 'han_viet' }] : [])],
    facts: {
      stroke_count: { value: c.strokes },
      radical: { value: { surface: c.radical.char, reading: c.radical.pinyin, name: { vi: c.radical.name_vi }, gloss: { vi: c.radical.meaning_vi } } },
      components: { value: c.components.map((surface) => ({ surface })) },
    },
  }));
  return {
    word: record.headword, term: record.headword, language_code: language, part_of_speech: record.pos[0].code,
    level: record.level.value, framework: record.level.scale,
    pronunciations: Object.entries(record.en?.ipa || {}).map(([region, text]) => ({ text, kind: 'pronunciation', notation: 'ipa', region })),
    readings: zh ? [{ text: record.zh.pinyin, kind: 'reading', notation: 'pinyin' }] : [],
    short_meanings: record.meanings.flatMap((m) => [{ language: 'vi', text: m.vi }, ...(zh && m.en ? [{ language: 'en', text: m.en }] : [])]),
    detailed_definitions: !zh ? record.meanings.filter((m) => m.en).map((m) => ({ language: 'en', text: m.en })) : [],
    examples: record.examples.map((e) => ({
      language, text: e.text, highlight: e.highlight, ...(e.reading ? { reading: e.reading } : {}),
      ...(e.reading_highlight ? { reading_highlight: e.reading_highlight } : {}),
      ...(e.label_vi ? { label: { vi: e.label_vi } } : {}), translation: { vi: e.translation_vi },
      ...(e.explanation_vi ? { explanation: { vi: e.explanation_vi } } : {}),
    })),
    usage_notes: notes,
    orthography: units.length ? { script: 'han', units } : {},
    provenance: { source_id: record.id, level_source: record.level.source, illustration: record.illustration, ...(record.en?.etymology_vi ? { etymology: { vi: record.en.etymology_vi } } : {}) },
  };
}

const EN = stored(sample('en_resilient'));
const ZH = stored(sample('zh_senlin'));
const LEARNER_KEYS = ['saved', 'review_stage', 'due', 'next_review_at', 'stage', 'filled', 'hasSchedule', 'memory', 'context'];

/* --- the mapper is pure content --- */
const en = toVocabularyModel(EN, { supportLanguage: 'vi' });
const zh = toVocabularyModel(ZH, { supportLanguage: 'vi' });
for (const model of [en, zh]) for (const key of LEARNER_KEYS) assert.ok(!(key in model), `the content model carries no learner field (${key})`);
const withState = toVocabularyModel({ ...EN, saved: true, review_stage: 3, next_review_at: '2030-01-01T00:00:00Z', due: true }, { supportLanguage: 'vi' });
assert.deepEqual(withState, en, 'learner fields on the input change nothing in the model');
assert.equal(learnerState(null).saved, false);
assert.equal(learnerState({ review_stage: 9, next_review_at: '' }).filled, 4, 'the decorator clamps the stage');

/* --- English --- */
assert.equal(en.word, 'resilient');
assert.equal(en.script, 'latin');
assert.deepEqual(en.pronunciation.ipa.map((item) => item.region), ['uk', 'us']);
assert.equal(en.pos, 'adjective');
assert.equal(en.level, 'C1');
assert.equal(en.meaning.text, 'kiên cường; có khả năng phục hồi nhanh');
assert.ok(en.definition.startsWith('able to recover'), 'the English definition line is kept under the meaning');
assert.equal(en.examples.length, 2);
assert.deepEqual(en.examples[0].parts.filter((part) => part.hit).map((part) => part.value), ['resilient']);
assert.equal(en.examples[0].label, 'Chỉ người');
assert.ok(en.examples[0].translation.startsWith('Trẻ em'));
assert.deepEqual(en.collocations, ['highly resilient', 'remarkably resilient', 'a resilient economy']);
assert.deepEqual(en.synonyms, ['tough', 'hardy']);
assert.deepEqual(en.antonyms, ['fragile', 'vulnerable']);
assert.deepEqual(en.wordFamily.map((item) => item.word), ['resilience', 'resiliently']);
assert.ok(en.memoryTip.text.startsWith('Latin resilire'));
assert.ok(en.etymology.startsWith('Từ Latin'));
assert.deepEqual(en.units, []);
assert.deepEqual(en.illustration, { kind: 'library', ref: 'sprout-through-crack', alt: 'Mầm cây vươn lên qua khe nứt mặt đất trong gió' }, 'the library drawing of the sample, by its ref (D-17X)');

/* Support-language content shows only in the support language; the meaning falls back, tagged. */
const enForEnglish = toVocabularyModel(EN, { supportLanguage: 'en' });
assert.equal(enForEnglish.examples[0].translation, '', 'a Vietnamese translation is not shown to an English-support learner');
assert.equal(enForEnglish.memoryTip, null);
assert.equal(enForEnglish.meaning.language, 'vi', 'a meaning in another language says which');

/* --- Chinese --- */
assert.equal(zh.script, 'hanzi');
assert.equal(zh.pronunciation.pinyin, 'sēnlín');
assert.deepEqual(zh.units.map((unit) => [unit.hanzi, unit.pinyin, unit.hanViet]), [['森', 'sēn', 'SÂM'], ['林', 'lín', 'LÂM']]);
assert.equal(zh.hanViet, 'SÂM LÂM');
assert.equal(zh.units[0].radical.surface, '木');
assert.equal(zh.units[0].radical.name, 'Mộc');
assert.deepEqual(zh.units[0].components, ['木', '木', '木']);
assert.equal(zh.units[0].strokes, 12);
assert.deepEqual(zh.classifiers, [{ mw: '片', reading: 'piàn', phrase: '一片森林', phraseReading: 'yí piàn sēnlín' }]);
assert.deepEqual(zh.related.map((item) => [item.word, item.gloss]), [['树林', 'rừng cây'], ['森林火灾', 'cháy rừng']]);
assert.deepEqual(zh.examples[0].parts.filter((part) => part.hit).map((part) => part.value), ['森林'], 'the exact Hanzi span');
assert.deepEqual(zh.examples[0].readingParts.filter((part) => part.hit).map((part) => part.value), ['sēnlín'], 'the matching pinyin span');
assert.ok(zh.examples[0].readingParts.some((part) => !part.hit), 'never the whole pinyin line');
assert.equal(zh.definition, '');

/* Pinyin is lit only when its span can be found - never guessed, never the whole line. */
const noReadingHighlight = toVocabularyModel({ ...ZH, examples: [{ ...ZH.examples[0], reading_highlight: undefined }] }, { supportLanguage: 'vi' });
assert.deepEqual(noReadingHighlight.examples[0].readingParts, [{ value: ZH.examples[0].reading, hit: false }]);
const wrongReading = toVocabularyModel({ ...ZH, examples: [{ ...ZH.examples[0], reading_highlight: { match: 'shùlín' } }] }, { supportLanguage: 'vi' });
assert.ok(wrongReading.examples[0].readingParts.every((part) => !part.hit));

/* --- highlight rules --- */
assert.deepEqual(highlightParts('A category of cats.', { match: 'cat' }), [{ value: 'A category of cats.', hit: false }], 'Latin is matched as a whole word');
assert.deepEqual(highlightParts('a cat, a cat', { match: 'cat', occurrence: 2 }).filter((p) => p.hit).length, 1);
assert.equal(highlightParts('a cat, a cat', { match: 'cat', occurrence: 2 })[0].value, 'a cat, a ', 'the second occurrence');
assert.deepEqual(highlightParts('我们应该保护森林。', { match: '森林', latin: false }).map((p) => p.hit), [false, true, false]);
assert.deepEqual(highlightExample('Keep a buffer before it breaks.', 'buffer').map((p) => p.hit), [false, true, false]);
assert.deepEqual(highlightExample('', 'buffer'), []);

/* --- other input shapes: a catalogue card and a saved item --- */
const catalogueCard = {
  identity: { language: 'en', normalized: 'buffer' }, headword: 'buffer', pronunciation: '/ˈbʌfər/', part_of_speech: 'noun',
  meanings: [{ language: 'vi', text: 'vùng đệm' }], short_meanings: [{ language: 'vi', text: 'vùng đệm' }],
  examples: [{ language: 'en', text: 'Keep a buffer before the deadline.' }], collocations: [{ type: 'collocation', text: 'time buffer' }],
  usage_notes: ['Countable in this sense.'], saved: true, review_stage: 2,
};
const fromCard = toVocabularyModel(catalogueCard, { supportLanguage: 'vi' });
assert.equal(fromCard.pronunciation.text, '/ˈbʌfər/');
assert.deepEqual(fromCard.collocations, ['time buffer']);
assert.deepEqual(fromCard.usage, ['Countable in this sense.']);
assert.deepEqual(fromCard.commonMistakes, [], 'free usage text is never a common mistake');
const fromItem = toVocabularyModel({ word: 'health', phonetic: '/helθ/', definition: '', support_translations: { vi: 'sức khoẻ' }, examples: [{ language: 'en', text: 'Health matters.' }] }, { supportLanguage: 'vi' });
assert.equal(fromItem.meaning.text, 'sức khoẻ');
assert.deepEqual(fromItem.examples[0].parts.filter((p) => p.hit).map((p) => p.value), ['Health']);
assert.equal(savePayloadOf(fromCard, 'feed').source_kind, 'feed');
assert.equal(savePayloadOf(fromCard).definition, 'vùng đệm');

/* --- the artifact's two-face layout: every section on its face, in the reference's order --- */
const { t } = await import('../static/orena/copy/vocabulary-card.js');
const reviewSrc = readFileSync(new URL('../static/orena/screens/review/screen.js', import.meta.url), 'utf8');
setLanguages({ ui: 'vi', support: 'vi' });
const plain = (markup) => String(markup).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
const faceOf = (markup, face) => {
  const out = String(markup);
  const start = out.indexOf(`c-vcard__face--${face}`);
  assert.ok(start > -1, `the card has a ${face} face`);
  const end = face === 'front' ? out.indexOf('c-vcard__face--back') : out.length;
  return out.slice(start, end);
};
/* Each marker, in order, is found after the previous one. */
function inOrder(markup, markers, what) {
  let at = -1;
  for (const marker of markers) {
    const found = markup.indexOf(marker, at + 1);
    assert.ok(found > at, `${what}: "${marker}" appears, after the one before it`);
    at = found;
  }
}
assert.deepEqual(CARD_MODES, ['detail', 'feed', 'review-front', 'review-back']);
const enCard = String(vocabularyCard(en, { mode: 'detail', learner: learnerState(null) }));
const enFront = faceOf(enCard, 'front');
const enBack = faceOf(enCard, 'back');
// EN front (Main.dc.html): level + source, POS (native · localized), headword, UK/US IPA rows with play,
// Meaning (support meaning, English definition), Word family, Synonyms / antonyms, See examples ->.
inOrder(enFront, [
  'c-vcard__top', 'c-vcard__level">C1<', 'Oxford 5000', 'c-vcard__pos', 'adjective', 'Tính từ',
  'c-vcard__word', '>resilient<', 'data-region="uk"', '<b>Anh</b>', '/rɪˈzɪliənt/', 'data-region="us"', '<b>Mỹ</b>', '/rɪˈzɪljənt/',
  'c-vcard__actions', 'data-play', 'data-save',
  '<figure class="c-vcard__art" role="img" aria-label="Mầm cây vươn lên qua khe nứt mặt đất trong gió" data-art="sprout-through-crack">', '<svg',
  'data-section="sectionMeaning"', '>Nghĩa<', 'kiên cường; có khả năng phục hồi nhanh', 'able to recover quickly',
  'data-section="sectionWordFamily"', '>Họ từ<', 'resilience', '(n)', 'resiliently', '(adv)',
  'data-section="sectionSynAnt"', 'Đồng / trái nghĩa', '≈ tough, hardy', '≠ fragile, vulnerable',
  'data-vcard-turn="back"', 'Xem ví dụ →',
], 'EN front');
for (const absent of ['c-vcard__example', 'Kết hợp thường gặp', 'Mẹo nhớ']) assert.ok(!enFront.includes(absent), `EN front has no ${absent}`);
// EN back: the headword and "Examples & usage", numbered examples (label, sentence with the highlight,
// translation, explanation), Common collocations as chips, Memory tip, <- Front.
inOrder(enBack, [
  'c-vcard__backword', 'resilient', 'Ví dụ &amp; cách dùng',
  '01 · Chỉ người', 'Children are often more <mark class="c-vcard__hit">resilient</mark> than adults expect.', 'Trẻ em thường kiên cường', 'Nói về tinh thần',
  '02 · Chỉ hệ thống, vật', '<mark class="c-vcard__hit">resilient</mark> to power failures.', 'chịu được sự cố mất điện', 'resilient to / against + N',
  'data-section="sectionCollocations"', 'Kết hợp thường gặp', '<span class="c-vcard__chip">highly resilient</span>', 'a resilient economy',
  'data-section="sectionMemoryTip"', 'Mẹo nhớ', 'Latin resilire',
  'data-vcard-turn="front"', '← Mặt trước',
], 'EN back');
assert.ok(enBack.includes('hidden'), 'the card starts on its front; the back is hidden until turned');
assert.ok(!enBack.includes('data-section="sectionMeaning"'), 'the meaning is the front\'s');

const zhCard = String(vocabularyCard(zh, { mode: 'detail', learner: learnerState(null) }));
const zhFront = faceOf(zhCard, 'front');
const zhBack = faceOf(zhCard, 'back');
// ZH front (Chinese.dc.html): HSK tag, POS (名词 · danh từ), the Hanzi with each pinyin over it, Hán Việt,
// Meaning (support + English), Radical (木 once, then each character = parts · strokes), Measure word, Related words.
inOrder(zhFront, [
  'c-vcard__top', 'c-vcard__level">HSK 4<', 'c-vcard__pos', '名词', 'Danh từ',
  '<ruby>森<rt>sēn</rt></ruby><ruby>林<rt>lín</rt></ruby>', 'Hán Việt', 'SÂM LÂM',
  'c-vcard__actions', 'data-play', 'data-save',
  'data-art="ink-pine-trees"',
  'data-section="sectionMeaning"', 'rừng, rừng rậm', 'forest',
  'data-section="sectionRadical"', '>木<', 'mù', 'Mộc', '(cây)', '森 = 木 + 木 + 木', '12 nét', '林 = 木 + 木', '8 nét',
  'data-section="sectionMeasureWord"', 'Lượng từ', '一片森林', 'yí piàn sēnlín',
  'data-section="sectionRelated"', 'Từ liên quan', '树林', 'shùlín', 'rừng cây', '森林火灾', 'cháy rừng',
  'data-vcard-turn="back"',
], 'ZH front');
assert.equal((zhFront.match(/c-vcard__radical-glyph/g) || []).length, 1, 'a radical the characters share is shown once (docs/vocab README)');
assert.ok(!zhFront.includes('CẦN KIỂM TRA'), 'the Chinese card draws no level source (the reference has none)');
// ZH back: the Hanzi and pinyin, numbered examples (label, Hanzi span, pinyin span, translation, note), Memory tip.
inOrder(zhBack, [
  'c-vcard__backword', '森林', 'sēnlín', 'Ví dụ &amp; cách dùng',
  '一 · Nơi chốn', '这片<mark class="c-vcard__hit">森林</mark>里住着很多动物。', 'Zhè piàn <mark class="c-vcard__hit">sēnlín</mark> lǐ', 'Trong khu rừng này', '片 là lượng từ',
  '二 · Làm tân ngữ', '我们应该保护<mark class="c-vcard__hit">森林</mark>。', 'bǎohù <mark class="c-vcard__hit">sēnlín</mark>', 'Chúng ta nên bảo vệ rừng.',
  'data-section="sectionMemoryTip"', '木 một cây',
  'data-vcard-turn="front"',
], 'ZH back');
assert.ok(!zhBack.includes('Zhè piàn sēnlín lǐ zhùzhe hěn duō dòngwù.</mark>'), 'never the whole pinyin line');

/* A section with no data is left out, heading and all; no illustration means no frame. */
const sparse = String(vocabularyCard(toVocabularyModel({ word: 'copper', short_meanings: [{ language: 'vi', text: 'đồng' }] }, { supportLanguage: 'vi' }), { mode: 'detail' }));
for (const key of ['sectionWordFamily', 'sectionSynAnt', 'sectionCollocations', 'sectionMemoryTip', 'sectionStructure', 'sectionRadical', 'sectionMeasureWord', 'sectionRelated']) {
  assert.ok(!sparse.includes(`data-section="${key}"`), `no empty ${key}`);
}
assert.ok(!sparse.includes('<ol class="c-vcard__examples">'), 'no empty example list');
assert.ok(!faceOf(enCard, 'back').includes('<figure'), 'the drawing is on the front only');
const unknownArt = toVocabularyModel({ ...EN, provenance: { ...EN.provenance, illustration: { kind: 'library', ref: 'no-such-drawing' } } }, { supportLanguage: 'vi' });
assert.ok(!String(vocabularyCard(unknownArt, { mode: 'detail' })).includes('<figure'), 'a ref the art map does not know draws no frame');
const noArt = toVocabularyModel({ ...EN, provenance: { ...EN.provenance, illustration: { kind: 'none' } } }, { supportLanguage: 'vi' });
assert.ok(!String(vocabularyCard(noArt, { mode: 'detail' })).includes('<figure'), 'kind none: no frame');
assert.ok(!String(vocabularyCard(en, { mode: 'review-front' })).includes('<figure'), 'never on the recall face');
const artSource = readFileSync(new URL('../static/orena/kit/vocabulary-art.js', import.meta.url), 'utf8');
assert.match(artSource, /Art Bible/, 'the art map names the Art Bible boundary');
assert.doesNotMatch(artSource.replace(/\/\*[\s\S]*?\*\//g, ''), /#[0-9a-fA-F]{3,8}|rgba?\(/, 'the drawings carry no colour: the card tokens colour them');
const uploaded = toVocabularyModel({ ...EN, illustration: { kind: 'upload', ref: '/assets/x.png', alt_vi: 'x' } }, { supportLanguage: 'vi' });
assert.ok(faceOf(vocabularyCard(uploaded, { mode: 'detail' }), 'front').includes('<figure class="c-vcard__art">'), 'an uploaded image is drawn on the front');

/* Modes. */
for (const model of [en, zh]) {
  const front = String(vocabularyCard(model, { mode: 'review-front' }));
  const frontText = plain(front);
  assert.ok(front.includes('data-play'), 'review-front plays the word');
  assert.ok(!front.includes('data-save') && !front.includes('data-vcard-turn'), 'review-front: no save, no turn');
  assert.ok(!frontText.includes(model.meaning.text), 'review-front never shows the meaning');
  for (const blocked of ['c-vcard__example', 'c-vcard__pair', 'c-vcard__radical', 'c-vcard__meaning', 'data-section']) assert.ok(!front.includes(blocked), `no ${blocked} on the recall face`);
  assert.ok(frontText.includes(model.word) && (frontText.includes(model.pronunciation.text) || frontText.includes(model.pronunciation.pinyin)));
  assert.deepEqual(Object.keys(frontFields(model)).sort(), ['language', 'level', 'pos', 'pronunciation', 'script', 'word']);

  const back = String(vocabularyCard(model, { mode: 'review-back', learner: learnerState({ review_stage: 2, next_review_at: '' }) }));
  assert.ok(faceOf(back, 'front').includes('data-section="sectionMeaning"'), 'review-back opens on the reference front (the meaning)');
  assert.ok(back.includes('data-vcard-turn="back"'), 'and can turn to the examples');
  assert.ok(!back.includes('data-grade'), 'the grades are the screen\'s, outside the card');
  assert.ok(back.includes('c-vcard__mastery'), 'the learner footer when there is a schedule');
  // Review has no bookmark (D-179 point 4): Save and remove belong to Word Detail and the Feed.
  assert.ok(!back.includes('data-save'), 'review-back draws no bookmark');

  const detail = String(vocabularyCard(model, { mode: 'detail', learner: learnerState(null) }));
  assert.ok(detail.includes('data-save aria-pressed="false"'), 'detail offers Save');
  assert.ok(!detail.includes('c-vcard__mastery'), 'no schedule, no footer');
  assert.ok(!detail.includes('data-grade'), 'Word Detail never grades');
  const feed = String(vocabularyCard(model, { mode: 'feed', learner: { saved: true } }));
  assert.ok(feed.includes('aria-pressed="true"'));
  assert.ok((faceOf(feed, 'back').match(/class="c-vcard__example"/g) || []).length <= 2, 'the feed shows at most two examples');
}
assert.throws(() => vocabularyCard(en, { mode: 'flip' }));

/* --- the meaning panel never claims an absence it has not established (lead's :8021 check, D-179) --- */
setLanguages({ ui: 'vi', support: 'vi' });
const tagged = [];
const meaningLabel = (language) => { tagged.push(language); return `[${language}]`; };
// copper: an English word whose only meaning is its own English definition (a collection card before Save).
const copper = toVocabularyModel({ identity: { language: 'en', normalized: 'copper' }, headword: 'copper', pronunciation: '/ˈkɒpə/',
  meanings: [{ language: 'en', text: 'A reddish metal.' }], short_meanings: [{ language: 'en', text: 'A reddish metal.' }],
  examples: [{ language: 'en', text: 'The wire is made of copper.' }] }, { supportLanguage: 'vi' });
assert.equal(copper.meaning, null);
assert.equal(copper.definition, 'A reddish metal.');
assert.equal(copper.definitionLanguage, 'en');
const copperCard = String(vocabularyCard(copper, { mode: 'detail', slots: { meaningLabel } }));
assert.ok(!copperCard.includes('data-no-meaning'), 'an own-language definition is shown, not "no meaning"');
assert.ok(copperCard.includes('A reddish metal.') && tagged.includes('en'), 'labelled with its language');
// 松树: a Chinese word whose only meaning is a Chinese definition.
const pine = toVocabularyModel({ identity: { language: 'zh', normalized: '松树' }, headword: '松树', pronunciation: 'sōngshù',
  meanings: [{ language: 'zh', text: '一种常绿的树。' }] }, { supportLanguage: 'vi' });
assert.equal(pine.definition, '一种常绿的树。');
assert.equal(pine.definitionLanguage, 'zh');
assert.ok(!String(vocabularyCard(pine, { mode: 'detail', slots: { meaningLabel } })).includes('data-no-meaning'));
// A saved item whose only meaning is the definition kept with it stays a meaning, as on main 947f744f.
const savedCopper = toVocabularyModel({ word: 'copper', definition: 'A reddish metal.' }, { supportLanguage: 'vi' });
assert.equal(savedCopper.meaning.text, 'A reddish metal.');
assert.equal(savedCopper.definition, '', 'never the same text twice');
// economy in the feed: the catalogue card's own-language meaning only.
const economy = toVocabularyModel({ identity: { language: 'en', normalized: 'economy' }, headword: 'economy',
  meanings: [{ language: 'en', text: 'the system of trade and industry' }], examples: [] }, { supportLanguage: 'vi' });
assert.ok(!String(vocabularyCard(economy, { mode: 'feed', learner: { saved: false } })).includes('data-no-meaning'));
// Still being looked up: the kit's skeleton bones, not "no meaning"; nothing at all and nothing pending: "no meaning".
const bare = toVocabularyModel({ word: 'zzz' }, { supportLanguage: 'vi' });
const pendingCard = String(vocabularyCard(bare, { mode: 'detail', slots: { meaningPending: true } }));
assert.ok(pendingCard.includes('data-meaning-pending') && pendingCard.includes('o-bone') && !pendingCard.includes('data-no-meaning'));
assert.ok(String(vocabularyCard(bare, { mode: 'detail' })).includes('data-no-meaning'));
// A support-language meaning plus the own-language definition: both, the definition as the second line.
assert.ok(faceOf(vocabularyCard(en, { mode: 'detail' }), 'front').includes('c-vcard__definition'));

/* --- the headword never breaks inside a word; 360x740 composition, structurally --- */
const { headwordRun } = await import('../static/orena/kit/vocabulary-card.js');
assert.equal(headwordRun('opportunity', 'latin'), 11);
assert.equal(headwordRun('a resilient economy', 'latin'), 9, 'a phrase wraps between words: its longest word sets the size');
assert.equal(headwordRun('森林火灾', 'hanzi'), 4);
assert.ok(String(vocabularyCard(toVocabularyModel({ word: 'opportunity' }), { mode: 'feed' })).includes('style="--len:11"'));
const cardCss = readFileSync(new URL('../static/orena/kit/vocabulary-card.css', import.meta.url), 'utf8');
const wordRule = cardCss.match(/\.c-vcard__word \{[^}]*\}/)[0];
assert.match(wordRule, /overflow-wrap: normal/);
assert.match(wordRule, /word-break: keep-all/);
assert.match(wordRule, /font-size: min\(60px, calc\(165cqi \/ var\(--len, 1\)\), 7\.5dvh\)/, 'the reference size (60px) is the ceiling; the type shrinks to the width and to the viewport height');
assert.match(cardCss, /\.c-vcard__word--han \{[^}]*font-size: min\(104px, calc\(78cqi \/ var\(--len, 1\)\), 12dvh\)/);
assert.doesNotMatch(cardCss, /overflow-wrap: anywhere|word-break: break-all/, 'nothing lets a word break mid-word');
// No fixed card size: only controls and glyph tiles are sized.
const sized = [...cardCss.replace(/\/\*[\s\S]*?\*\//g, '').matchAll(/([^{}]+)\{([^}]*)\}/g)]
  .filter(([, , body]) => /(^|\s|;)(width|height|min-width|min-height):\s*\d+px/.test(body))
  .map(([, selector]) => selector.trim());
// Only controls, the svg's own width and the radical tile are sized in plain px; no card or face height is.
assert.deepEqual(sized, ['.c-vcard__turn', '.c-vcard--han .c-vcard__turn', '.c-vcard__disc', '.c-vcard__art svg', '.c-vcard__radical-glyph'], `only fixed-size controls: ${sized.join(', ')}`);
assert.doesNotMatch(cardCss.replace(/\/\*[\s\S]*?\*\//g, ''), /\.c-vcard(--[\w-]+)? \{[^}]*(^|[\s;])height:\s*\d+px/, 'no fixed card height');
// One viewport (rule 49, CLAUDE.md 6b): spacing scales with the card's width AND the viewport's height, the design's
// value the ceiling.
assert.match(cardCss, /--vc-pad-top: min\(clamp\(20px, 6\.9cqi, 36px\), clamp\(12px, 3\.4dvh, 36px\)\)/);
assert.match(cardCss, /--vc-gap: clamp\(10px, 2\.4dvh, 22px\)/);
// Word Detail's card is never taller than the visible column below it; Review's and the feed's fill their slot.
assert.match(cardCss, /\.c-vcard--detail \{[^}]*max-height: var\(--vcard-fit, calc\(100dvh - 180px\)\)/, 'the detail card has a max-height tied to the viewport');
assert.match(cardCss, /\.c-vcard--feed,\s*\.c-vcard--review-back \{[^}]*max-height: 100%/);
// The illustration's height is clamped against the viewport and drops out on a short card.
assert.match(cardCss, /\.c-vcard__art \{[^}]*height: clamp\(72px, calc\(24dvh - 60px\), 180px\)/);
assert.match(cardCss, /\.c-vcard--han \.c-vcard__art \{[^}]*height: clamp\(64px, calc\(20dvh - 48px\), 150px\)/);
assert.match(cardCss, /\.c-vcard\[data-fit='short'\] \.c-vcard__art \{[^}]*display: none/);
// The head and the foot are outside the face body (the only scroll region).
for (const face of ['front', 'back']) {
  const markup = faceOf(enCard, face);
  const bodyAt = markup.indexOf('<div class="c-vcard__body" data-scroll-region>');
  assert.ok(markup.indexOf('c-vcard__head') > -1 && markup.indexOf('c-vcard__head') < bodyAt, `${face}: the head is before the body, outside it`);
  assert.ok(markup.indexOf('c-vcard__foot') > bodyAt, `${face}: the foot is after the body`);
  assert.equal((markup.match(/data-scroll-region/g) || []).length, 1, `${face}: one scroll region, the body`);
}
assert.ok(faceOf(enCard, 'front').indexOf('c-vcard__top') < faceOf(enCard, 'front').indexOf('c-vcard__body'), 'the top row stays in the head');
assert.match(cardCss, /\.c-vcard__head \{[^}]*flex: none/);
// Each screen fits its cards: Word Detail to the viewport (and again on resize), Review and the feed to their slot.
const { fitVocabularyCards, SHORT_CARD_PX } = await import('../static/orena/kit/vocabulary-card.js');
assert.equal(typeof fitVocabularyCards, 'function');
assert.ok(SHORT_CARD_PX > 400);
// The measurement itself: the visible column below the card's top on arrival, less a gap; short below SHORT_CARD_PX.
function fakeCard({ top, columnBottom, scrollTop = 0, slot = 0 }) {
  const props = new Map();
  return {
    dataset: {},
    style: { setProperty: (name, value) => props.set(name, value) },
    props,
    closest: () => (columnBottom ? { getBoundingClientRect: () => ({ bottom: columnBottom }), scrollTop } : null),
    getBoundingClientRect: () => ({ top }),
    parentElement: { getBoundingClientRect: () => ({ height: slot }) },
  };
}
const tall = fakeCard({ top: 120, columnBottom: 1000 });
const phone = fakeCard({ top: 150, columnBottom: 650, scrollTop: 40 });
fitVocabularyCards({ querySelectorAll: () => [tall, phone] }, { viewport: true });
assert.equal(tall.props.get('--vcard-fit'), '864px');
assert.equal(tall.dataset.fit, 'full');
assert.equal(phone.props.get('--vcard-fit'), '444px', 'measured as if the column were at its top');
assert.equal(phone.dataset.fit, 'short', 'a short card drops its illustration first');
// The phone bar floats over the column's bottom (lead's 360x740 check: the column ran to 740, the bar from ~650 and
// its orb higher): the fit stops above the highest of them, so the card and its turn action are never under it.
const underBar = fakeCard({ top: 126, columnBottom: 740 });
const rect = (top, height = 72) => ({ getBoundingClientRect: () => ({ top, height, width: 300 }) });
const phoneRoot = {
  querySelectorAll: () => [underBar],
  ownerDocument: { querySelectorAll: () => [rect(650), rect(616, 58)] },
};
fitVocabularyCards(phoneRoot, { viewport: true });
assert.equal(underBar.props.get('--vcard-fit'), '474px', 'max-height ends above the bar and its orb (616 - 126 - 16)');
assert.equal(underBar.dataset.fit, 'short', 'so the illustration drops and the meaning shows on arrival');
const hiddenBar = fakeCard({ top: 126, columnBottom: 740 });
fitVocabularyCards({ querySelectorAll: () => [hiddenBar], ownerDocument: { querySelectorAll: () => [rect(0, 0)] } }, { viewport: true });
assert.equal(hiddenBar.props.get('--vcard-fit'), '598px', 'a bar that is not displayed (desktop, focus routes) changes nothing');
// Review and the Daily Feed are learning workspaces (focus routes): no phone bar there (rule 47); they fit their slot.
const routesSrc = readFileSync(new URL('../static/orena/shell/routes.js', import.meta.url), 'utf8');
for (const id of ['review', 'feed']) assert.match(routesSrc, new RegExp(`\{ id: '${id}',[^}]*focus: true`), `${id} is a focus route`);
const slotted = fakeCard({ top: 0, slot: 480 });
fitVocabularyCards({ querySelectorAll: () => [slotted] });
assert.equal(slotted.dataset.fit, 'short');
const wordScreenSrc = readFileSync(new URL('../static/orena/screens/word/screen.js', import.meta.url), 'utf8');
assert.match(wordScreenSrc, /fitVocabularyCards\(element, \{ viewport: true \}\)/);
assert.match(wordScreenSrc, /window\.addEventListener\('resize', onResize\)/);
assert.match(wordScreenSrc, /window\.removeEventListener\('resize', onResize\)/);
assert.match(readFileSync(new URL('../static/orena/screens/review/screen.js', import.meta.url), 'utf8'), /fitVocabularyCards\(element\)/);
assert.match(readFileSync(new URL('../static/orena/screens/feed/screen.js', import.meta.url), 'utf8'), /fitVocabularyCards\(element\)/);
// The card's colours are its scoped tokens only (D-17X).
for (const [, prop, value] of cardCss.replace(/\/\*[\s\S]*?\*\//g, '').matchAll(/(color|background|border(?:-\w+)?|outline|fill|stroke):\s*([^;]+);/g)) {
  for (const used of value.matchAll(/var\(--([\w-]+)/g)) assert.ok(used[1].startsWith('vcard-'), `${prop}: ${value} uses an app token inside the card`);
}
// The Hanzi row wraps instead of overlapping (lead's 360x740 check): Hán Việt goes under the Hanzi.
assert.match(cardCss, /\.c-vcard__hanrow \{[^}]*flex-wrap: wrap/, 'the Hanzi row wraps');
assert.match(cardCss, /\.c-vcard__hanrow \.c-vcard__word \{[^}]*min-width: min-content/, 'the Hanzi never shrinks under its glyphs');
assert.doesNotMatch(cardCss, /position:\s*absolute/, 'nothing on the card is absolutely positioned over another block');
assert.ok(faceOf(vocabularyCard(toVocabularyModel({ word: '森林火灾', language_code: 'zh' }, { supportLanguage: 'vi' }), { mode: 'detail' }), 'front').includes('style="--len:4"'), 'a four-character word fits by its own length');
assert.doesNotMatch(cardCss, /@media/, 'no width media query (rule 49 recomposes by the pairs\' own columns)');
// Each face: a body that scrolls inside itself, a foot that keeps the turn action in view.
assert.match(cardCss, /\.c-vcard__body \{[^}]*min-height: 0;[^}]*overflow-y: auto/, 'each face body is its own scroll region');
assert.match(cardCss, /\.c-vcard__foot \{[^}]*flex: none/, 'the turn action never shrinks out of view');
assert.ok(enCard.includes('<div class="c-vcard__body" data-scroll-region>'));
// Review: the card fills its face; the grades are outside the card and never shrink.
assert.match(reviewSrc, /\$\{vocabularyCard\(model, \{ mode: 'review-back'/);
const gradesAt = reviewSrc.indexOf('<div class="s-review-grades">');
assert.ok(gradesAt > reviewSrc.indexOf('backFaceMarkup(model, learner, row)'), 'the grades are drawn after the card stack, outside the card');
const reviewCss = readFileSync(new URL('../static/orena/screens/review/review.css', import.meta.url), 'utf8');
assert.match(reviewCss, /\.s-review-grades \{[^}]*flex: none/, 'the grades never shrink out of view');
assert.match(reviewCss, /\.s-review-face--revealed > \.c-vcard--review-back \{[^}]*min-height: 0/, 'the card fills the revealed face and scrolls inside');
assert.match(reviewCss, /\.s-review-root \{[^}]*overflow: hidden/, 'the workspace does not scroll as a page');
assert.ok(!reviewSrc.slice(reviewSrc.indexOf('function backFaceMarkup'), reviewSrc.indexOf('function hiddenFaceMarkup')).includes('s-review-face__blob'), 'no corner disc on the turned card: no corner is free of text or controls (VC-12)');
assert.doesNotMatch(reviewCss, /\.s-review-face--revealed > \.s-review-face__blob/);
assert.match(cardCss, /\.c-vcard__foot \{[^}]*flex-wrap: wrap/, 'the foot wraps as whole items');
assert.match(cardCss, /\.c-vcard__stage \{[^}]*white-space: nowrap/, 'the stage label never breaks inside a word');
assert.match(cardCss, /\.c-vcard__due \{[^}]*white-space: nowrap/);
assert.match(cardCss, /\.c-vcard__hanviet \{[^}]*align-items: flex-start/, 'the Hán Việt label and value share the start edge');
// Review neither saves nor removes a word (D-179 point 4).
assert.doesNotMatch(reviewSrc, /data-save|deleteLibraryVocabulary|saveLibraryVocabulary/, 'Review has no save or remove action');

/* --- a reading is only ever the word's own kind (:8021 check: "/paɪn triː/" drawn over 松树) --- */
const { isPinyin, isLatinReading } = await import('../static/orena/product/vocabulary-card.js');
assert.ok(isPinyin('sēnlín') && isPinyin('sōng shù') && isPinyin('ni3 hao3') && isPinyin("xī'ān"));
assert.ok(!isPinyin('/paɪn triː/') && !isPinyin('[paɪn]') && !isPinyin('松树'));
assert.ok(isLatinReading('/ˈbʌfər/') && !isLatinReading('sēnlín') && !isLatinReading('森林'));
const ipaLookup = { available: true, headword: '松树', script: 'hanzi', pinyin: '/paɪn triː/', ipa: '/paɪn triː/' };
// With the entry's pinyin: the entry's pinyin, never the lookup's IPA.
const pineEntry = { word: '松树', language_code: 'zh', readings: [{ text: 'sōngshù', kind: 'reading' }], short_meanings: [{ language: 'vi', text: 'cây thông' }] };
const pineModel = toVocabularyModel(pineEntry, { word: '松树', supportLanguage: 'vi', lookup: ipaLookup });
assert.equal(pineModel.pronunciation.pinyin, 'sōngshù');
const pineCard = String(vocabularyCard(pineModel, { mode: 'detail' }));
assert.ok(!pineCard.includes('paɪn') && pineCard.includes('<rt>sōngshù</rt>'), 'the ruby is the entry\'s pinyin');
// No pinyin anywhere but the lookup's IPA: no reading at all, and no ruby.
const pineBare = toVocabularyModel({ word: '松树', language_code: 'zh' }, { word: '松树', supportLanguage: 'vi', lookup: ipaLookup, seed: { pronunciation: '/paɪn triː/' } });
assert.equal(pineBare.pronunciation.pinyin, '');
const bareCard = String(vocabularyCard(pineBare, { mode: 'detail' }));
assert.ok(!bareCard.includes('paɪn') && !bareCard.includes('<rt>'), 'never an English IPA over Hanzi');
assert.ok(!String(vocabularyCard(pineBare, { mode: 'review-front' })).includes('paɪn'));
// Character units: their pinyin, one per character.
assert.ok(String(vocabularyCard(toVocabularyModel(ZH, { supportLanguage: 'vi', lookup: { ...ipaLookup, headword: '森林' } }), { mode: 'detail' })).includes('<ruby>森<rt>sēn</rt></ruby>'));
// A Latin word never shows pinyin (or Hanzi) as its IPA.
const latin = toVocabularyModel({ word: 'forest', language_code: 'en', readings: [{ text: 'sēnlín' }], phonetic: '森林' }, { supportLanguage: 'vi', lookup: { available: true, headword: 'forest', script: 'latin', ipa: 'sēnlín' } });
assert.equal(latin.pronunciation.text, '');
assert.ok(!String(vocabularyCard(latin, { mode: 'detail' })).includes('sēnlín'));
// Word Detail: the lookup runs in the learner's current learning language (the server refuses any other with a
// 409, media_interaction.py#_validated_source_language); the catalogue is read in the word's own language; a
// refused or empty lookup never fails the page.
const { catalogueLanguage } = await import('../static/orena/screens/word/model.js');
assert.equal(catalogueLanguage('松树', 'en'), 'zh');
assert.equal(catalogueLanguage('copper', 'en'), 'en');
assert.equal(catalogueLanguage('copper', 'zh'), 'en');
const wordSrc = readFileSync(new URL('../static/orena/screens/word/screen.js', import.meta.url), 'utf8');
assert.match(wordSrc, /source_language: language,/, 'the lookup uses the learning language of the account');
assert.match(wordSrc, /catalogueSeed\(word, catalogueLanguage\(word, language\)\)/, 'the catalogue is asked in the language of the word');
assert.doesNotMatch(wordSrc, /throw new Error\(`Word Detail/, 'no lookup and no record still draws a card, never a load error');
for (const refused of [null, { available: false, headword: '松树', script: 'hanzi', pinyin: '/paɪn triː/' }]) {
  const degraded = toVocabularyModel(null, { word: '松树', supportLanguage: 'vi', lookup: refused });
  assert.equal(degraded.word, '松树');
  assert.equal(degraded.script, 'hanzi');
  assert.equal(degraded.pronunciation.pinyin, '', 'no reading rather than a wrong one');
  const degradedCard = String(vocabularyCard(degraded, { mode: 'detail', learner: learnerState(null) }));
  assert.ok(degradedCard.includes('>松树<') && !degradedCard.includes('<rt>') && degradedCard.includes('data-save'));
}
// The catalogue's own answer for a direct link (the search's trimmed shape) gives the pinyin and the meaning.
const searched = toVocabularyModel({ word: '松树', normalized_word: '松树', language_code: 'zh', part_of_speech: 'noun', readings: [{ text: 'sōng shù', kind: 'reading' }], short_meanings: [{ language: 'en', text: 'pine tree' }] }, { word: '松树', supportLanguage: 'vi', lookup: { available: true, headword: '松树', script: 'hanzi', pinyin: '/paɪn triː/' } });
assert.equal(searched.pronunciation.pinyin, 'sōng shù');
assert.equal(searched.meaning.text, 'pine tree');

/* --- meaning precedence (:8021 check, 松树): a support-language meaning from the lookup leads another language's --- */
setLanguages({ ui: 'vi', support: 'vi' });
const pineEn = { word: '松树', language_code: 'zh', readings: [{ text: 'sōng shù' }], short_meanings: [{ language: 'en', text: 'pine; pine tree' }] };
const pineLookup = { available: true, headword: '松树', script: 'hanzi', contextMeaning: 'chỉ loài cây thông' };
const pineMeaning = toVocabularyModel(pineEn, { word: '松树', supportLanguage: 'vi', lookup: pineLookup });
assert.deepEqual(pineMeaning.meaning, { text: 'chỉ loài cây thông', language: '' }, 'the lookup\'s Vietnamese meaning leads');
assert.equal(pineMeaning.english, 'pine; pine tree', 'the English meaning is the second line');
const pineFront = faceOf(vocabularyCard(pineMeaning, { mode: 'detail', slots: { meaningLabel: (l) => `[${l}]` } }), 'front');
assert.ok(pineFront.indexOf('chỉ loài cây thông') < pineFront.indexOf('pine; pine tree'));
assert.ok(!pineFront.includes('chỉ loài cây thông[') , 'the support-language meaning carries no language tag');
// Without the lookup, the other language's meaning is the meaning, tagged (step 5).
const pineAlone = toVocabularyModel(pineEn, { word: '松树', supportLanguage: 'vi' });
assert.deepEqual(pineAlone.meaning, { text: 'pine; pine tree', language: 'en' });
// The entry's own support-language sense always leads the lookup (D-124), and a learner's note leads it too.
assert.equal(toVocabularyModel({ ...pineEn, short_meanings: [...pineEn.short_meanings, { language: 'vi', text: 'cây thông' }] }, { supportLanguage: 'vi', lookup: pineLookup }).meaning.text, 'cây thông');
assert.equal(toVocabularyModel({ ...pineEn, definition: 'my note' }, { supportLanguage: 'vi', lookup: pineLookup }).meaning.text, 'my note');
// A seed's support-language sense comes after the lookup, before another language.
assert.equal(toVocabularyModel(pineEn, { supportLanguage: 'vi', seed: { short_meanings: [{ language: 'vi', text: 'thông' }] } }).meaning.text, 'thông');

/* --- D-17X: the header as drawn, and nothing of the app's palette inside the card --- */
for (const card of [enCard, zhCard]) {
  const top = card.slice(card.indexOf('<div class="c-vcard__top">'), card.indexOf('</div>', card.indexOf('c-vcard__pos')) + 6);
  assert.ok(top.indexOf('c-vcard__level') < top.indexOf('c-vcard__pos'), 'level tag on the left, part of speech on the right, one row');
  assert.ok(!top.includes('data-save') && !top.includes('data-play'), 'no disc pushes the part of speech down: the actions sit under the reading');
}
const kitCardSrc = readFileSync(new URL('../static/orena/kit/vocabulary-card.js', import.meta.url), 'utf8');
for (const [name, source] of [['kit/vocabulary-card.js', kitCardSrc.replace(/\/\*[\s\S]*?\*\//g, '')], ['kit/vocabulary-card.css', cardCss.replace(/\/\*[\s\S]*?\*\//g, '')]]) {
  assert.doesNotMatch(source, /o-tag|--accent|accent-fill|accent-soft|accent-ink/, `${name}: no kit tag and no app accent inside the card`);
}
for (const card of [enCard, zhCard, String(vocabularyCard(en, { mode: 'review-front' })), String(vocabularyCard(zh, { mode: 'review-back', learner: learnerState({ review_stage: 1, next_review_at: '' }) }))]) {
  assert.doesNotMatch(card, /o-tag|o-btn--primary|var\(--accent|accent-fill|accent-soft|accent-ink/, 'the rendered card carries no kit tag, primary kit button or app accent');
}
const tagged2 = String(vocabularyCard(pineAlone, { mode: 'detail', slots: { meaningLabel: () => 'Tiếng Anh' } }));
assert.ok(tagged2.includes('<span class="c-vcard__lang">Tiếng Anh</span>'), 'the meaning language tag is drawn by the card');
// Touch targets: the discs are 44px.
assert.match(cardCss, /\.c-vcard__disc \{[^}]*width: 44px;[^}]*height: 44px/);
// ZH (lead's :8021 check: the content computed the app sans, `:lang(vi)` sets it on every Vietnamese element):
// the family is set on EVERY element of the Chinese card, and only by these four rules - no content class re-sets it.
assert.match(cardCss, /--vcard-han: 'Noto Serif SC', 'Source Han Serif SC', 'Songti SC', STSong, SimSun, NSimSun, serif;/);
// Pinyin and Vietnamese need tone letters: a Latin-led stack whose first Windows font carries them (no Georgia).
assert.match(cardCss, /--vcard-latin-serif: 'Noto Serif', Cambria, 'Times New Roman', 'Noto Serif SC'/);
assert.doesNotMatch(cardCss.replace(/\/\*[\s\S]*?\*\//g, ''), /Georgia/, 'no Georgia in any stack');
const familyRules = [...cardCss.replace(/\/\*[\s\S]*?\*\//g, '').matchAll(/([^{}]+)\{([^}]*)\}/g)]
  .filter(([, , body]) => /font-family/.test(body))
  .map(([, selector, body]) => [selector.replace(/\s+/g, ' ').trim(), body.match(/font-family:\s*([^;]+);/)[1].trim()]);
assert.deepEqual(familyRules, [
  ['.c-vcard.c-vcard--han, .c-vcard.c-vcard--han *', 'var(--vcard-latin-serif)'],
  [".c-vcard.c-vcard--han :is([lang='zh'], .c-vcard__word--han, .c-vcard__radical-glyph, .c-vcard__level), .c-vcard.c-vcard--han :is([lang='zh'], .c-vcard__word--han, .c-vcard__radical-glyph, .c-vcard__level) *", 'var(--vcard-han)'],
  [".c-vcard.c-vcard--han :is([lang='zh'], .c-vcard__word--han) :is(rt, rt *)", 'var(--vcard-latin-serif)'],
  [".c-vcard .c-vcard__turn, .c-vcard .c-vcard__disc, .c-vcard.c-vcard--han .c-vcard__turn, .c-vcard.c-vcard--han .c-vcard__disc, .c-vcard.c-vcard--han [class$='-strokes'] .o-btn--secondary", 'var(--font-ui)'],
], 'the only font-family rules on the card');
// The universal rule outranks the app's `:lang(vi)` (0,1,0) by specificity, not by load order.
// Every pinyin carrier on the Chinese card is outside the Hanzi rule: example readings are lang="zh-Latn", the
// headword's pinyin is <rt> (re-set to the Latin stack), measure-word and related readings are plain muted spans.
const zhFrontMarkup = faceOf(zhCard, 'front');
assert.ok(zhFrontMarkup.includes('<rt>sēn</rt>'));
assert.ok(!/<span lang="zh">[^<]*yí piàn/.test(zhFrontMarkup) && zhFrontMarkup.includes('<span class="c-vcard__muted">yí piàn sēnlín</span>'), 'measure-word pinyin is not in a Hanzi span');
assert.ok(zhFrontMarkup.includes('<span class="c-vcard__muted">shùlín</span>'), 'a related reading is not in a Hanzi span');
assert.ok(faceOf(zhCard, 'back').includes('<p class="c-vcard__example-reading" lang="zh-Latn">'));

/* --- the two review buttons --- */
assert.deepEqual(REVIEW_BUTTONS, ['again', 'got_it']);
assert.ok(GRADES.includes('unsure'), 'unsure stays a grade the API accepts');
assert.match(reviewSrc, /mode: 'review-front'/);
assert.match(reviewSrc, /mode: 'review-back'/);
assert.doesNotMatch(reviewSrc, /gradeButton\('unsure'/, 'no Unsure button');
const feedSrc = readFileSync(new URL('../static/orena/screens/feed/screen.js', import.meta.url), 'utf8');
assert.match(feedSrc, /mode: 'feed'/);
assert.doesNotMatch(feedSrc, /reviewLibraryVocabulary|data-grade/, 'the feed never grades');

/* --- every label in three languages, with diacritics --- */
for (const ui of ['en', 'vi', 'zh']) {
  setLanguages({ ui, support: ui });
  const out = plain(vocabularyCard(en, { mode: 'detail' }));
  assert.ok(!/section[A-Z]|pos[A-Z]|missing key/.test(out), `no raw key in ${ui}`);
}
setLanguages({ ui: 'vi', support: 'vi' });
assert.ok(String(vocabularyCard(en, { mode: 'detail' })).includes('Kết hợp thường gặp'));
assert.equal(posLabel('adjective').text, 'Tính từ');
setLanguages({ ui: 'zh', support: 'zh' });
assert.equal(posLabel('noun').text, '名词');
assert.equal(posLabel('noun / verb').text, '名词／动词');
assert.equal(posLabel('weird-code').known, false);

console.log('test_orena_vocabulary_card.mjs: pure mapper, EN/ZH content, highlight spans, review-front hides the answer, no frame without an image, two review buttons, three languages: PASS');
