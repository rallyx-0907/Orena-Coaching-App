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
assert.deepEqual(en.illustration, { kind: 'library', ref: 'sprout-through-crack', alt: 'Mầm cây vươn lên qua khe nứt mặt đất trong gió' }, 'the library drawing of the sample, by its ref (D-180)');

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
  'c-vcard__top-end', 'c-vcard__actions', 'data-play', 'data-save',
  'c-vcard__word', '>resilient<', 'data-region="uk"', '<b>Anh</b>', '/rɪˈzɪliənt/', 'data-region="us"', '<b>Mỹ</b>', '/rɪˈzɪljənt/',
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
  'c-vcard__top-end', 'c-vcard__actions', 'data-play', 'data-save',
  '<ruby>森<rt>sēn</rt></ruby><ruby>林<rt>lín</rt></ruby>', 'Hán Việt', 'SÂM LÂM',
  'data-art="ink-pine-trees"',
  'c-vcard__lead', 'data-section="sectionMeaning"', 'rừng, rừng rậm', 'forest',
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
// A saved note says nothing about its own language (PR 4, :8021): 森林 saved with the Vietnamese meaning, then read
// with English support, labelled "rừng, rừng rậm" Chinese. Only Han text is known to be Chinese; any other note is
// shown without a language tag rather than with a guessed one.
const savedForest = toVocabularyModel({ word: '森林', definition: 'rừng, rừng rậm', short_meanings: [{ language: 'en', text: 'forest' }] }, { supportLanguage: 'en' });
assert.equal(savedForest.meaning.text, 'forest');
assert.equal(savedForest.definition, 'rừng, rừng rậm');
assert.equal(savedForest.definitionLanguage, '', 'a Latin-script note is not claimed to be Chinese');
const savedEnglishNote = toVocabularyModel({ word: 'resilient', definition: 'kiên cường', short_meanings: [{ language: 'en', text: 'able to recover' }] }, { supportLanguage: 'en' });
assert.equal(savedEnglishNote.definitionLanguage, '', 'nor English, for an English word');
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
assert.doesNotMatch(cardCss, /overflow-wrap: anywhere|word-break: break-all/, 'nothing lets a word break mid-word');
// No fixed card size: only the kit-sized controls and the svg's own width are plain px.
const sized = [...cardCss.replace(/\/\*[\s\S]*?\*\//g, '').matchAll(/([^{}]+)\{([^}]*)\}/g)]
  .filter(([, , body]) => /(^|\s|;)(width|height|min-width|min-height):\s*\d+px/.test(body))
  .map(([, selector]) => selector.trim());
assert.deepEqual(sized, ['.c-vcard__turn.o-btn', '.c-vcard__disc', '.c-vcard__art svg'], `only fixed-size controls: ${sized.join(', ')}`);
assert.doesNotMatch(cardCss.replace(/\/\*[\s\S]*?\*\//g, ''), /\.c-vcard(--[\w-]+)? \{[^}]*(^|[\s;])height:\s*\d+px/, 'no fixed card height');
// THE SCALE (the human, 2026-10-12): every content size is the design's 520px artboard value scaled by the card's
// width, s = min(1, width / 520), with readability floors only (body 13, labels 11, pinyin/IPA 12). Evaluated here.
const cssRulesAll = [...cardCss.replace(/\/\*[\s\S]*?\*\//g, '').matchAll(/([^{}]+)\{([^}]*)\}/g)].map(([, sel, body]) => [sel.trim(), body]);
const isButton = (sel) => /\.c-vcard__(turn|disc)|o-btn/.test(sel);
for (const [sel, body] of cssRulesAll) {
  if (isButton(sel)) continue;
  for (const [, value] of body.matchAll(/font-size:\s*([^;]+);/g)) {
    assert.ok(!/^\d+(\.\d+)?px$/.test(value.trim()), `${sel}: content font-size ${value} is a fixed px, not the width scale`);
  }
}
function sizeOf(selector, prop, { width, height = 1080, len = 1, em = 16, ks = 1, kt = 1, ka = 1 }) {
  const rule = cssRulesAll.find(([sel]) => sel === selector);
  assert.ok(rule, `${selector} is styled`);
  let expr = (rule[1].match(new RegExp(`(?:^|[;\\s])${prop}:\\s*([^;]+);`)) || [])[1];
  assert.ok(expr, `${selector} sets ${prop}`);
  expr = expr.replace(/var\(--len, 1\)/g, String(len)).replace(/var\(--vc-ks, 1\)/g, String(ks)).replace(/var\(--vc-kt, 1\)/g, String(kt)).replace(/var\(--vc-ka, 1\)/g, String(ka))
    .replace(/(\d+(?:\.\d+)?)px/g, '$1').replace(/(\d+(?:\.\d+)?)cqi/g, `($1*${width}/100)`)
    .replace(/(\d+(?:\.\d+)?)dvh/g, `($1*${height}/100)`).replace(/(\d+(?:\.\d+)?)em/g, `($1*${em})`)
    .replace(/\bcalc\(/g, '(').replace(/\bmin\(/g, 'Math.min(').replace(/\bmax\(/g, 'Math.max(').replace(/\bclamp\(/g, 'clampFn(');
  return Function('clampFn', `return ${expr};`)((a, b, c) => Math.min(Math.max(a, b), c));
}
const at520 = { width: 520, height: 1080 };
const at328 = { width: 328, height: 740 };
const sizes = (at) => ({
  headwordEn: sizeOf('.c-vcard__word', 'font-size', { ...at, len: 9 }),
  headwordZh: sizeOf('.c-vcard__word--han', 'font-size', { ...at, len: 2 }),
  meaning: sizeOf('.c-vcard__meaning-text', 'font-size', at),
  definition: sizeOf('.c-vcard__definition', 'font-size', at),
  body: sizeOf('.c-vcard__lines,\n.c-vcard__note', 'font-size', at),
  exampleEn: sizeOf('.c-vcard__example-text', 'font-size', at),
  exampleZh: sizeOf('.c-vcard--han .c-vcard__example-text', 'font-size', at),
  label: sizeOf('.c-vcard__label', 'font-size', at),
  level: sizeOf('.c-vcard__level', 'font-size', at),
  chip: sizeOf('.c-vcard__chip', 'font-size', at),
  ipa: sizeOf('.c-vcard__ipa', 'font-size', at),
  regionLabel: sizeOf('.c-vcard__ipa b', 'font-size', at),
  artEn: sizeOf('.c-vcard__art', 'height', at),
  artZh: sizeOf('.c-vcard--han .c-vcard__art', 'height', at),
  radical: sizeOf('.c-vcard__radical-glyph', 'width', at),
  pad: sizeOf('.c-vcard', '--vc-pad-x', at),
});
const desk = sizes(at520);
// s = 1 at a 520px card: the design's own values.
assert.deepEqual(
  Object.fromEntries(Object.entries(desk).map(([k, v]) => [k, Math.round(v * 100) / 100])),
  { headwordEn: 60, headwordZh: 104, meaning: 22, definition: 15, body: 15, exampleEn: 19, exampleZh: 24, label: 12, level: 13, chip: 13, ipa: 17, regionLabel: 12, artEn: 220, artZh: 190, radical: 56, pad: 40 },
  'at a 520px card everything is the design value (s = 1)',
);
const phoneSizes = sizes(at328);
const s328 = 328 / 520;
assert.ok(Math.abs(phoneSizes.headwordEn - 60 * s328) < 0.1, `EN headword scales: ${phoneSizes.headwordEn}`);
assert.ok(Math.abs(phoneSizes.headwordZh - 104 * s328) < 0.1, `ZH headword scales: ${phoneSizes.headwordZh}`);
assert.ok(Math.abs(phoneSizes.artEn - 220 * s328) < 0.1, `EN illustration scales: ${phoneSizes.artEn}`);
assert.ok(Math.abs(phoneSizes.artZh - 190 * s328) < 0.1, `ZH illustration scales: ${phoneSizes.artZh}`);
assert.ok(Math.abs(phoneSizes.radical - 56 * s328) < 0.1 && Math.abs(phoneSizes.pad - 40 * s328) < 0.1);
for (const key of ['meaning', 'definition', 'body', 'exampleEn', 'exampleZh']) assert.ok(phoneSizes[key] >= 13, `${key} keeps 13px: ${phoneSizes[key]}`);
for (const key of ['label', 'level', 'chip']) assert.ok(phoneSizes[key] >= 11, `${key} keeps 11px: ${phoneSizes[key]}`);
for (const key of ['ipa', 'regionLabel']) assert.ok(phoneSizes[key] >= 12, `${key} keeps 12px: ${phoneSizes[key]}`);
assert.ok(phoneSizes.meaning < 22 && phoneSizes.body < 15 && phoneSizes.label < 12, 'no old larger mobile sizes');
console.log(`  at a 328px card: ${Object.entries(phoneSizes).map(([k, v]) => `${k} ${v.toFixed(1)}`).join(', ')}`);
// The card is its own size container (cqi = the card's width): no container inside it but the recall face.
assert.match(cardCss, /\.c-vcard \{[^}]*container-type: inline-size/);
assert.doesNotMatch(cardCss.match(/\.c-vcard__body \{[^}]*\}/)[0], /container-type/);
// Word Detail's card is never taller than the visible column below it; Review's and the feed's fill their slot.
assert.match(cardCss, /\.c-vcard--detail \{[^}]*max-height: var\(--vcard-fit, calc\(100dvh - 180px\)\)/, 'the detail card has a max-height tied to the viewport');
assert.match(cardCss, /\.c-vcard--feed,\s*\.c-vcard--review-back \{[^}]*max-height: 100%/);
// All content stays on a phone: no rule drops the illustration (or anything) on a short card.
assert.doesNotMatch(cardCss, /data-fit/, 'no short-card rule drops content');
// A face is head, body, foot - and NOTHING in it scrolls (the human, 2026-10-12, D-180): no scroll region in the
// markup, no overflow auto/scroll on the card, a face or its body.
for (const face of ['front', 'back']) {
  const markup = faceOf(enCard, face);
  const bodyAt = markup.indexOf('<div class="c-vcard__body">');
  assert.ok(bodyAt > -1, `${face}: has a body`);
  assert.ok(markup.indexOf('c-vcard__head') > -1 && markup.indexOf('c-vcard__head') < bodyAt, `${face}: the head is before the body, outside it`);
  assert.ok(markup.indexOf('c-vcard__foot') > bodyAt, `${face}: the foot is after the body`);
  assert.doesNotMatch(markup, /data-scroll-region/, `${face}: no scroll region in a face`);
}
{
  const noComments = cardCss.replace(/\/\*[\s\S]*?\*\//g, '');
  for (const [, selector, body] of noComments.matchAll(/([^{}]+)\{([^}]*)\}/g)) {
    assert.doesNotMatch(body, /overflow(-[xy])?:\s*(auto|scroll)/, `${selector.trim()}: nothing on the card scrolls`);
  }
  for (const css of ['review/review.css', 'feed/feed.css', 'word/word.css']) {
    const screenCss = readFileSync(new URL(`../static/orena/screens/${css}`, import.meta.url), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
    for (const [, selector, body] of screenCss.matchAll(/([^{}]+)\{([^}]*)\}/g)) {
      if (/c-vcard/.test(selector)) assert.doesNotMatch(body, /overflow(-[xy])?:\s*(auto|scroll)/, `${css} ${selector.trim()}: a card face never scrolls`);
    }
  }
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
assert.equal(phone.dataset.fit, 'short', 'recorded as short (information only; nothing is dropped)');
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
assert.equal(underBar.dataset.fit, 'short', 'recorded as short; the face is contained, nothing is dropped');
const hiddenBar = fakeCard({ top: 126, columnBottom: 740 });
fitVocabularyCards({ querySelectorAll: () => [hiddenBar], ownerDocument: { querySelectorAll: () => [rect(0, 0)] } }, { viewport: true });
assert.equal(hiddenBar.props.get('--vcard-fit'), '598px', 'a bar that is not displayed (desktop, focus routes) changes nothing');
// CONTAIN (the human, 2026-10-12): s = min(widthScale, heightScale). The CSS gives the width scale; the fit gives the
// height scale in three phases - spacing first with the illustration held at >= 60% of its width-scaled height, then
// the type with the illustration in proportion, then spacing alone - never under the hard floors.
const { containStep, containCard, CONTAIN_SPACE_MIN, CONTAIN_ART_MIN, CONTAIN_TYPE_MIN, CONTAIN_SPACE_FLOOR } = await import('../static/orena/kit/vocabulary-card.js');
const near = (a, b, eps = 1e-6) => Math.abs(a - b) < eps;
assert.deepEqual(containStep(500, 480), { ks: 1, kt: 1, ka: 1, done: true }, 'a face that fits is left at the width scale');
{
  const first = containStep(400, 500);
  assert.ok(first.kt === 1 && first.ks < 0.81 && first.ks > 0.79, `phase 1: spacing moves first, by the ratio (${first.ks})`);
  assert.equal(first.ka, first.ks, 'the illustration follows spacing ...');
  const deep = containStep(100, 500, { ks: 0.7, kt: 1, ka: 0.7 });
  assert.equal(deep.ks, CONTAIN_SPACE_MIN, 'spacing stops at its minimum');
  assert.equal(deep.ka, CONTAIN_ART_MIN, '... but stays at >= 60% of its width-scaled height while only spacing moves');
  const typeNext = containStep(400, 500, { ks: CONTAIN_SPACE_MIN, kt: 1, ka: CONTAIN_ART_MIN });
  assert.ok(typeNext.ks === CONTAIN_SPACE_MIN && typeNext.kt < 0.81 && typeNext.kt > 0.79, 'phase 2: then the type');
  assert.ok(near(typeNext.ka, CONTAIN_ART_MIN * typeNext.kt), 'with the illustration in proportion');
  const typeMin = containStep(100, 500, { ks: CONTAIN_SPACE_MIN, kt: 0.9, ka: 0.54 });
  assert.equal(typeMin.kt, CONTAIN_TYPE_MIN, 'the type stops at its minimum');
  const last = containStep(400, 500, { ks: CONTAIN_SPACE_MIN, kt: CONTAIN_TYPE_MIN, ka: CONTAIN_ART_MIN * CONTAIN_TYPE_MIN });
  assert.ok(last.ks < CONTAIN_SPACE_MIN && last.kt === CONTAIN_TYPE_MIN, 'phase 3: spacing alone again');
  const end = { ks: CONTAIN_SPACE_FLOOR, kt: CONTAIN_TYPE_MIN, ka: CONTAIN_ART_MIN * CONTAIN_TYPE_MIN };
  assert.equal(containStep(100, 500, end).done, true, 'and the steps end');
  assert.equal(containStep(500, 499.5).done, false, 'a face within a pixel of its box is fitted, not left a hair over');
}
// At the type minimum every floor is the hard floor: body / meaning / example 11px, labels and tags 9.5px, pinyin and
// IPA 10px - and no lower, however narrow or short the card.
for (const at of [{ width: 328, height: 740, kt: CONTAIN_TYPE_MIN, ks: CONTAIN_SPACE_FLOOR, ka: 0.33 }, { width: 200, height: 400, kt: 0.2, ks: 0.2, ka: 0.1 }]) {
  const small = sizes(at);
  for (const key of ['meaning', 'definition', 'body', 'exampleEn', 'exampleZh']) assert.ok(small[key] >= 11 - 1e-9, `${key} >= 11px: ${small[key]}`);
  for (const key of ['label', 'level', 'chip']) assert.ok(small[key] >= 9.5 - 1e-9, `${key} >= 9.5px: ${small[key]}`);
  for (const key of ['ipa', 'regionLabel']) assert.ok(small[key] >= 10 - 1e-9, `${key} >= 10px: ${small[key]}`);
  assert.ok(small.artEn > 0 && small.artZh > 0, 'the illustration stays, smaller');
}
{
  const tight = sizes({ width: 328, height: 740, kt: CONTAIN_TYPE_MIN, ks: CONTAIN_SPACE_MIN, ka: CONTAIN_ART_MIN });
  assert.equal(tight.body, 11, 'body reaches exactly its hard floor');
  assert.equal(tight.label, 9.5, 'labels reach exactly theirs');
  assert.equal(tight.ipa, 10, 'IPA reaches exactly its');
  assert.ok(near(tight.artEn, phoneSizes.artEn * CONTAIN_ART_MIN, 0.01) && near(tight.artZh, phoneSizes.artZh * CONTAIN_ART_MIN, 0.01), 'the illustration is on its own knob, held at 60% through phase 1');
}
// THE RADICAL BOX (lead's 360x740 check: at s 0.8 it fell to ~16px and its glyph ran over the text). A square, beside
// its text block: it follows spacing to a 32px floor (or its width-scaled size, if smaller), and its glyph is sized from
// the box, so the glyph never leaves it.
for (const width of [328, 520, 260]) {
  for (const ks of [1, CONTAIN_SPACE_MIN, CONTAIN_SPACE_FLOOR, 0.1]) {
    const at = { width, height: 740, ks, kt: CONTAIN_TYPE_MIN, ka: 0.3 };
    const box = sizeOf('.c-vcard__radical-glyph', 'width', at);
    assert.equal(box, sizeOf('.c-vcard__radical-glyph', 'height', at), 'square');
    assert.ok(box >= Math.min(32, width * 0.10769) - 1e-9, `radical box >= its floor at ${width}px, ks ${ks}: ${box}`);
    assert.ok(sizeOf('.c-vcard__radical-glyph', 'font-size', at) <= box * 0.65, 'the glyph fits inside its box');
  }
}
assert.equal(Math.round(sizeOf('.c-vcard__radical-glyph', 'width', { width: 520, height: 1080 })), 56, 'the design\'s 56px at s = 1');
assert.match(cardCss, /\.c-vcard__radical-glyph \{[^}]*flex: none;[^}]*box-sizing: border-box;[^}]*aspect-ratio: 1/, 'the box never shrinks out of square');
assert.match(cardCss, /\.c-vcard__radical > \.c-vcard__lines \{[^}]*flex: 1 1 auto;[^}]*min-width: 0/, 'its text takes the rest of the row, beside the box');
// The buttons are not scaled: their rules never read the knobs.
for (const [sel, body] of cssRulesAll) if (isButton(sel)) assert.doesNotMatch(body, /--vc-k[sta]/, `${sel}: a button keeps its size`);

/* THE SAMPLES IN THE BOX. A block-layout model of a face (the gate has no browser): it reads the face's markup and
   this stylesheet's own values (font-size, line-height, gap, padding, heights, flex rows) at the knobs, estimates
   line breaks from the text (a Han glyph 1em, other letters 0.55em, plus slack for word breaks), and returns head,
   body and foot heights. Conservative, not exact: the browser check stays the human's and the lead's. Both full
   samples - EN with its two examples, collocations and memory tip; ZH with its two examples - must fit a 328 x 474
   card on both faces (Word Detail at 360 x 740), the loop ending with fits = yes and the foot below the body's last
   line. */
const VOID = new Set(['img', 'br', 'input', 'path', 'circle', 'rect', 'line', 'polyline', 'polygon', 'ellipse', 'use']);
const INLINE = new Set(['span', 'b', 'i', 'em', 'strong', 'mark', 'a', 'ruby', 'rt', 'rp', 'small', 'sup', 'sub', 'abbr', 'bdi', 'q']);
function parseMarkup(markup) {
  const root = { tag: 'root', cls: [], attrs: '', children: [] };
  const stack = [root];
  for (const [, close, tag, attrs, text] of String(markup).matchAll(/<(\/?)([a-zA-Z][\w-]*)([^>]*)>|([^<]+)/g)) {
    const top = stack[stack.length - 1];
    if (text !== undefined) {
      if (top.tag !== 'svg' && !stack.some((n) => n.tag === 'svg')) top.children.push({ text: text.replace(/&[a-z#0-9]+;/g, 'x') });
      continue;
    }
    const name = tag.toLowerCase();
    if (close) {
      const at = stack.map((n) => n.tag).lastIndexOf(name);
      if (at > 0) stack.length = at;
      continue;
    }
    const node = { tag: name, cls: ((attrs.match(/class="([^"]*)"/) || [])[1] || '').split(/\s+/).filter(Boolean), attrs, children: [] };
    top.children.push(node);
    if (!VOID.has(name) && !/\/$/.test(attrs.trim())) stack.push(node);
  }
  return root;
}
// Simple selectors only (matches() skips :is(), attributes, *, + and ~): enough for the layout values.
const ruleList = cssRulesAll.flatMap(([sel, body]) => sel.split(',').map((one) => [one.trim(), body]));
function compoundMatches(compound, node) {
  if (!node || !node.tag) return false;
  for (const part of compound.match(/(^[a-z][\w-]*)|\.[\w-]+/gi) || []) {
    if (part.startsWith('.')) { if (!node.cls.includes(part.slice(1))) return false; }
    else if (part.toLowerCase() !== node.tag) return false;
  }
  return true;
}
function matches(selector, node, ancestors) {
  const parts = selector.replace(/>/g, ' ').split(/\s+/).filter(Boolean);
  if (parts.some((p) => /[:\[*+~]/.test(p))) return false;
  if (!compoundMatches(parts[parts.length - 1], node)) return false;
  let i = ancestors.length - 1;
  for (let k = parts.length - 2; k >= 0; k -= 1) {
    while (i >= 0 && !compoundMatches(parts[k], ancestors[i])) i -= 1;
    if (i < 0) return false;
    i -= 1;
  }
  return true;
}
function declarations(node, ancestors) {
  const out = {};
  for (const [sel, body] of ruleList) {
    if (!matches(sel, node, ancestors)) continue;
    for (const [, prop, value] of body.matchAll(/(?:^|[;\s])([\w-]+):\s*([^;]+);/g)) out[prop] = value.trim();
  }
  if (node.attrs && /style="[^"]*--len:\s*(\d+)/.test(node.attrs)) out['--len'] = node.attrs.match(/--len:\s*(\d+)/)[1];
  return out;
}
function evalCss(expr, at, vars, em) {
  let e = String(expr);
  for (let guard = 0; guard < 6 && /var\(--/.test(e); guard += 1) {
    e = e.replace(/var\(--([\w-]+)(?:,\s*([^()]+))?\)/g, (m, name, fallback) => {
      if (name === 'vc-ks') return String(at.ks ?? 1);
      if (name === 'vc-kt') return String(at.kt ?? 1);
      if (name === 'vc-ka') return String(at.ka ?? 1);
      if (vars[name] !== undefined) return `(${vars[name]})`;
      return fallback !== undefined ? fallback : '0';
    });
  }
  e = e.replace(/(\d+(?:\.\d+)?)px/g, '$1').replace(/(\d+(?:\.\d+)?)cqi/g, `($1*${at.width}/100)`)
    .replace(/(\d+(?:\.\d+)?)dvh/g, `($1*${at.height}/100)`).replace(/(\d+(?:\.\d+)?)em\b/g, `($1*${em})`)
    .replace(/\bcalc\(/g, '(').replace(/\bmin\(/g, 'Math.min(').replace(/\bmax\(/g, 'Math.max(').replace(/\bclamp\(/g, 'clampFn(');
  try {
    const value = Function('clampFn', `return ${e};`)((a, b, c) => Math.min(Math.max(a, b), c));
    return Number.isFinite(value) ? value : null;
  } catch { return null; }
}
const firstLength = (value) => String(value).trim().split(/\s+(?![^(]*\))/);
function textOf(node) {
  if (node.text !== undefined) return node.text;
  if (node.tag === 'rt' || node.tag === 'svg') return '';
  return node.children.map(textOf).join('');
}
function textWidth(text, fs) {
  let w = 0;
  for (const ch of text.replace(/\s+/g, ' ').trim()) w += /[㐀-鿿豈-﫿　-〿＀-￯]/.test(ch) ? fs : fs * 0.55;
  return w;
}
const isBlock = (node, decl) => node.tag && !INLINE.has(node.tag) && node.tag !== 'button' || (decl && /flex|block|grid/.test(decl.display || ''));
function layout(node, ancestors, ctx, width, inherited) {
  if (node.text !== undefined) return 0;
  if (/\bhidden\b/.test(node.attrs || '') && node.tag !== 'root') return 0;
  const decl = declarations(node, ancestors);
  if ((decl.display || '') === 'none') return 0;
  const vars = { ...inherited.vars };
  for (const [k, v] of Object.entries(decl)) if (k.startsWith('--')) vars[k.slice(2)] = v;
  const fs = decl['font-size'] ? (evalCss(decl['font-size'], ctx.at, { ...vars, len: vars.len || '1' }, inherited.fs) ?? inherited.fs) : inherited.fs;
  const lhRaw = decl['line-height'];
  const lh = lhRaw ? (/px/.test(lhRaw) ? evalCss(lhRaw, ctx.at, vars, fs) / fs : Number(lhRaw) || inherited.lh) : inherited.lh;
  const self = { vars, fs, lh };
  const side = (prop) => {
    const v = decl[prop];
    if (!v) return [0, 0, 0, 0];
    const parts = firstLength(v).map((p) => evalCss(p, ctx.at, vars, fs) ?? 0);
    const [t, r = t, b = t, l = r] = parts;
    return [t, r, b, l];
  };
  const [pt, pr, pb, pl] = side('padding');
  const extraTop = (decl['padding-top'] ? evalCss(decl['padding-top'], ctx.at, vars, fs) : 0) + (decl['margin-top'] ? evalCss(decl['margin-top'], ctx.at, vars, fs) ?? 0 : 0);
  const extraBottom = decl['padding-bottom'] ? evalCss(decl['padding-bottom'], ctx.at, vars, fs) ?? 0 : 0;
  const pad = pt + pb + extraTop + extraBottom;
  const inner = Math.max(40, width - pr - pl);
  if (node.tag === 'button') return Math.max(44, evalCss(decl['min-height'] || decl.height || '44px', ctx.at, vars, fs) ?? 44);
  if (decl.height && node.tag !== 'root') {
    const h = evalCss(decl.height, ctx.at, vars, fs);
    if (h !== null) return h + extraTop;
  }
  const kids = node.children.filter((c) => c.text === undefined ? true : c.text.trim());
  const blockKids = kids.filter((c) => c.text === undefined && isBlock(c, declarations(c, [...ancestors, node])));
  const gapValue = decl.gap ? evalCss(firstLength(decl.gap)[0], ctx.at, vars, fs) ?? 0 : 0;
  const display = decl.display || '';
  if (!blockKids.length) {
    // A text leaf: its lines, and a ruby line over it when it carries one.
    const text = textOf(node);
    if (!text.trim() && !kids.some((c) => c.tag === 'button' || c.tag === 'img')) return pad;
    const lines = Math.max(1, Math.ceil((textWidth(text, fs) * 1.1) / inner));
    const ruby = JSON.stringify(node).includes('"tag":"rt"') ? Math.max(10, 12 * (ctx.at.kt ?? 1), 0.21 * fs) * 1.3 : 0;
    const buttons = kids.filter((c) => c.tag === 'button').length ? 44 : 0;
    return pad + Math.max(lines * fs * lh + ruby, buttons);
  }
  const childAncestors = [...ancestors, node];
  const row = /flex/.test(display) && !/column/.test(decl['flex-direction'] || '');
  if (row) {
    // A flex row: side by side; when it wraps, greedy rows by the children's own text widths.
    const items = kids.map((c) => {
      const h = layout(c, childAncestors, ctx, c.cls.includes('c-vcard__lines') ? inner - (ctx.radicalBox || 0) - gapValue : inner, self);
      const w = c.tag === 'button' ? 44 : c.cls.includes('c-vcard__radical-glyph') ? h : Math.min(inner, textWidth(textOf(c), fs) + 8);
      return { h, w, fill: c.cls.includes('c-vcard__lines') };
    });
    if (!/wrap/.test(decl['flex-wrap'] || '')) return pad + Math.max(0, ...items.map((i) => i.h));
    let total = 0; let lineW = 0; let lineH = 0;
    for (const item of items) {
      if (lineW && lineW + gapValue + item.w > inner) { total += lineH + gapValue; lineW = 0; lineH = 0; }
      lineW += (lineW ? gapValue : 0) + item.w;
      lineH = Math.max(lineH, item.h);
    }
    return pad + total + lineH;
  }
  let sum = 0;
  let inlineRun = '';
  const flush = () => {
    if (inlineRun.trim()) sum += Math.ceil((textWidth(inlineRun, fs) * 1.1) / inner) * fs * lh;
    inlineRun = '';
  };
  const heights = [];
  for (const c of kids) {
    if (blockKids.includes(c)) {
      flush();
      if (c.cls.includes('c-vcard__radical-glyph')) ctx.radicalBox = evalCss(declarations(c, childAncestors).width, ctx.at, vars, fs);
      heights.push(layout(c, childAncestors, ctx, inner, self));
    } else inlineRun += c.text !== undefined ? c.text : textOf(c);
  }
  flush();
  const gaps = /flex|grid/.test(display) ? gapValue * Math.max(0, heights.filter((h) => h > 0).length - 1) : 0;
  return pad + sum + heights.reduce((a, b) => a + b, 0) + gaps;
}
function faceModel(cardMarkup, face) {
  const tree = parseMarkup(cardMarkup);
  const card = tree.children.find((n) => n.cls?.includes('c-vcard'));
  const faceNode = card.children.find((n) => n.cls?.includes(`c-vcard__face--${face}`));
  return { card, faceNode };
}
function modelHeights(cardMarkup, face, at) {
  const { card, faceNode } = faceModel(cardMarkup, face);
  const cardDecl = declarations(card, []);
  const vars = {};
  for (const [k, v] of Object.entries(cardDecl)) if (k.startsWith('--')) vars[k.slice(2)] = v;
  const base = { vars, fs: 16, lh: 1.4 };
  const han = card.cls.includes('c-vcard--han');
  const cardPad = han ? (evalCss(cardDecl.padding, at, vars, 16) ?? 0) : 0;
  const ctx = { at };
  const width = at.width - 2 - 2 * cardPad - (han ? 3 : 0);
  const part = (name) => faceNode.children.find((n) => n.cls?.includes(`c-vcard__${name}`));
  const h = (node) => (node ? layout(node, [card, faceNode], ctx, width, base) : 0);
  return { head: h(part('head')), body: h(part('body')), foot: h(part('foot')), boxLoss: 2 + 2 * cardPad + (han ? 3 : 0) };
}
function modelCard(cardMarkup, face, { width = 328, height = 474, viewportHeight = 740 } = {}) {
  const props = new Map();
  const knobs = () => ({ width, height: viewportHeight, ks: Number(props.get('--vc-ks') ?? 1), kt: Number(props.get('--vc-kt') ?? 1), ka: Number(props.get('--vc-ka') ?? 1) });
  const measure = () => modelHeights(cardMarkup, face, knobs());
  const faceStub = {
    hidden: false,
    get clientHeight() { return height - measure().boxLoss; },
    querySelector: (q) => {
      const name = q.match(/c-vcard__(\w+)/)[1];
      return { getBoundingClientRect: () => ({ height: measure()[name] }), get scrollHeight() { return measure()[name]; } };
    },
  };
  return { props, dataset: {}, style: { setProperty: (name, value) => props.set(name, String(value)) }, querySelectorAll: () => [faceStub], measure, knobs };
}
const fullEn = String(vocabularyCard(en, { mode: 'detail', learner: learnerState(null) }));
const fullZh = String(vocabularyCard(zh, { mode: 'detail', learner: learnerState(null) }));
assert.ok(EN.examples.length >= 2 && EN.usage_notes.some((n) => n.type === 'collocation') && EN.usage_notes.some((n) => n.type === 'memory_tip'), 'the full EN sample: two examples, collocations, memory tip');
assert.ok(ZH.examples.length >= 2, 'the full ZH sample: two examples');
const fitReport = [];
for (const [name, markup] of [['EN', fullEn], ['ZH', fullZh]]) {
  for (const face of ['front', 'back']) {
    const card = modelCard(markup, face);
    const natural = card.measure();
    const result = containCard(card);
    const final = card.measure();
    assert.equal(card.dataset.vcardFits, 'yes', `${name} ${face}: the full sample fits 328 x 474 (need ${result.need.toFixed(1)} / ${result.available.toFixed(1)}, ks ${result.ks.toFixed(2)} kt ${result.kt.toFixed(2)} ka ${result.ka.toFixed(2)})`);
    // The foot sits below the body's last line: head + body content + foot inside the face.
    assert.ok(final.head + final.body + final.foot <= result.available + 0.5, `${name} ${face}: the foot does not cover the body`);
    const knobs = card.knobs();
    if (knobs.ks < 1) assert.ok(knobs.ka >= CONTAIN_ART_MIN * knobs.kt - 1e-3, `${name} ${face}: the illustration kept its share (${JSON.stringify(knobs)})`);
    fitReport.push(`${name} ${face} natural ${(natural.head + natural.body + natural.foot).toFixed(0)} -> ${result.need.toFixed(0)}/${result.available.toFixed(0)} s ${result.s.toFixed(3)}`);
  }
}
console.log(`  model fit at 328 x 474: ${fitReport.join('; ')}`);
// The loop on a face whose need jumps (a line re-wraps) still lands inside its box.
{
  const props = new Map();
  const k = (n) => Number(props.get(n) ?? 1);
  const need = () => 380 * (0.35 * k('--vc-ks') + 0.15 * k('--vc-ka') + 0.5 * k('--vc-kt')) + (k('--vc-kt') > 0.9 ? 24 : 0) + 64;
  const face = { hidden: false, clientHeight: 420, querySelector: (q) => (q.includes('body') ? { scrollHeight: need() } : { getBoundingClientRect: () => ({ height: 0 }) }) };
  const jumpy = { props, dataset: {}, style: { setProperty: (n, v) => props.set(n, String(v)) }, querySelectorAll: () => [face] };
  containCard(jumpy);
  assert.equal(jumpy.dataset.vcardFits, 'yes', 'a re-wrapping face still fits');
}
// Review's revealed card (review-back, the learner's mastery footer in its foot) fills a face TALLER than its content:
// its body is stretched, so its scrollHeight is the slot. The fit reads the content (the body's children), not the
// stretch: a card that fits is left at s = 1 with fits = yes (lead's check of e9e5f3d1: s 0.933, fits no, all visible).
{
  const props = new Map();
  const k = (n) => Number(props.get(n) ?? 1);
  const available = 560;
  const head = 0;
  const foot = () => 64; // the mastery line and the turn action (not scaled)
  const contentHeight = () => 300 * (0.4 * k('--vc-ks') + 0.6 * k('--vc-kt'));
  const bodyTop = 0;
  const body = {
    ownerDocument: { defaultView: { getComputedStyle: () => ({ paddingTop: '12', paddingBottom: '8', marginBottom: '0' }) } },
    getBoundingClientRect: () => ({ top: bodyTop, height: available - foot() }),
    get scrollHeight() { return available - foot(); }, // stretched: the slot, not the content
    get children() { return [{ getBoundingClientRect: () => ({ bottom: bodyTop + 12 + contentHeight(), height: contentHeight(), width: 300 }) }]; },
  };
  const parts = { head: { getBoundingClientRect: () => ({ height: head }) }, foot: { getBoundingClientRect: () => ({ height: foot() }) }, body };
  const face = { hidden: false, clientHeight: available, querySelector: (q) => parts[q.match(/c-vcard__(\w+)/)[1]] };
  const reviewBack = { props, dataset: {}, style: { setProperty: (n, v) => props.set(n, String(v)) }, querySelectorAll: () => [face] };
  const result = containCard(reviewBack);
  assert.equal(result.s, 1, `a stretched review-back card that fits is not shrunk (need ${result.need})`);
  assert.equal(reviewBack.props.get('--vc-ks'), '1.0000');
  assert.equal(reviewBack.dataset.vcardFits, 'yes');
  assert.match(String(vocabularyCard(en, { mode: 'review-back', learner: learnerState({ review_stage: 2, next_review_at: '' }), slots: { footer: { stage: 'Mới', due: 'Hôm nay' } } })), /<div class="c-vcard__foot">\s*<div class="c-vcard__mastery">/, 'the review-back card carries the mastery footer, in its foot (counted once, with the foot)');
}
// It re-fits on resize (every screen) and on turn (the other face fits on its own).
const kitSrc = readFileSync(new URL('../static/orena/kit/vocabulary-card.js', import.meta.url), 'utf8');
assert.match(kitSrc.slice(kitSrc.indexOf('export function bindVocabularyCards')), /containCard\(card\)/, 'turning a card fits the face it shows');
for (const screen of ['review', 'feed']) {
  const src = readFileSync(new URL(`../static/orena/screens/${screen}/screen.js`, import.meta.url), 'utf8');
  assert.match(src, /window\.addEventListener\('resize', onResize\)/, `${screen} fits again on resize`);
  assert.match(src, /window\.removeEventListener\('resize', onResize\)/, `${screen} lets go of resize`);
}
// Word Detail on a phone arrives with the shell chrome collapsed (D-181 option 1): the fit then has no bar to stop
// above and the column's whole height, less its bottom inset (here 20px).
{
  const doc = { documentElement: { dataset: { chrome: 'hidden' } }, querySelectorAll: () => [rect(650), rect(616, 58)], defaultView: { getComputedStyle: () => ({ paddingBottom: '20px', transform: 'none' }) } };
  const column = { getBoundingClientRect: () => ({ bottom: 740 }), scrollTop: 0, ownerDocument: doc };
  const props = new Map();
  const collapsedCard = { dataset: {}, style: { setProperty: (n, v) => props.set(n, v) }, closest: () => column, getBoundingClientRect: () => ({ top: 76 }), parentElement: null };
  fitVocabularyCards({ querySelectorAll: () => [collapsedCard], ownerDocument: doc }, { viewport: true });
  assert.equal(props.get('--vcard-fit'), '628px', 'collapsed: 740 - 20 inset - 76 top - 16 gap, no bar');
  doc.documentElement.dataset.chrome = 'shown';
  fitVocabularyCards({ querySelectorAll: () => [collapsedCard], ownerDocument: doc }, { viewport: true });
  assert.equal(props.get('--vcard-fit'), '524px', 'chrome back: the fit stops above the bar and its orb again (616 - 76 - 16)');
}
{
  const src = readFileSync(new URL('../static/orena/screens/word/screen.js', import.meta.url), 'utf8');
  assert.match(src, /addEventListener\('orena:chrome', onResize\)/, 'Word Detail fits again when the chrome comes or goes');
  assert.match(src, /removeEventListener\('orena:chrome', onResize\)/);
}
// The card keeps the design's portrait board on a wide screen (the human, 2026-10-12, option 1): never wider than the
// 520px artboard (canvas.json) - the width at which s = 1 - centred in its column; Review's session (header, face,
// grades) takes the same width so the grades follow the card.
{
  const boards = Object.values(JSON.parse(readFileSync(new URL('../docs/design/vocab-card/canvas.json', import.meta.url), 'utf8')).boards);
  const boardWidth = boards[0].w;
  assert.ok(boards.every((b) => b.w === boardWidth), 'one board width');
  const cardRule = cardCss.match(/\.c-vcard \{[^}]*\}/)[0];
  const cap = Number((cardRule.match(/max-inline-size: (\d+)px/) || [])[1]);
  assert.ok(cap >= 520 && cap <= 560, `the card has a max inline size of about the board: ${cap}`);
  assert.equal(cap, boardWidth, 'the cap is the artboard: wider than it only stretches the composition');
  assert.match(cardRule, /margin-inline: auto/, 'the card is centred in its column (Word Detail)');
  assert.equal(Math.round(sizeOf('.c-vcard__word', 'font-size', { width: cap, height: 1080, len: 9 })), 60, 's = 1 at the cap');
  const reviewCss = readFileSync(new URL('../static/orena/screens/review/review.css', import.meta.url), 'utf8');
  assert.ok(reviewCss.includes(`.s-review-root:has(.c-vcard) {
  max-width: ${cap}px;`), 'Review: the session around a card takes its width');
  assert.match(reviewCss, /\.s-review-grades \{[^}]*grid-template-columns: repeat\(2, minmax\(0, 1fr\)\)/, 'the grades span that width');
  const wordCss = readFileSync(new URL('../static/orena/screens/word/word.css', import.meta.url), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
  assert.doesNotMatch(wordCss, /\.c-vcard[^{]*\{[^}]*(max-width|max-inline-size|margin)/, 'Word Detail does not override the cap or the centring');
}
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
// The card's CONTENT colours are its scoped tokens only; its BUTTONS keep the app's kit design and tokens (the human,
// 2026-10-12, D-180: the flashcard skin is the content only).
const cssRules = [...cardCss.replace(/\/\*[\s\S]*?\*\//g, '').matchAll(/([^{}]+)\{([^}]*)\}/g)].map(([, selector, body]) => [selector.trim(), body]);
const isButtonRule = (selector) => /\.c-vcard__(turn|disc)|o-btn/.test(selector);
for (const [selector, body] of cssRules) {
  // A colour property (border-radius is a size: it reads the fit's spacing knob, not a colour).
  for (const [, prop, value] of body.matchAll(/(color|background|border(?:-(?!radius)\w+)?|outline|fill|stroke):\s*([^;]+);/g)) {
    for (const used of value.matchAll(/var\(--([\w-]+)/g)) {
      if (isButtonRule(selector)) assert.ok(!used[1].startsWith('vcard-'), `${selector}: a button uses the app's tokens, not ${used[1]}`);
      else assert.ok(used[1].startsWith('vcard-'), `${selector} ${prop}: ${value} uses an app token on the card's content`);
    }
  }
}
// The Hanzi row wraps instead of overlapping (lead's 360x740 check): Hán Việt goes under the Hanzi.
assert.match(cardCss, /\.c-vcard__hanrow \{[^}]*flex-wrap: wrap/, 'the Hanzi row wraps');
assert.match(cardCss, /\.c-vcard__hanrow \.c-vcard__word \{[^}]*min-width: min-content/, 'the Hanzi never shrinks under its glyphs');
assert.doesNotMatch(cardCss, /position:\s*absolute/, 'nothing on the card is absolutely positioned over another block');
assert.ok(faceOf(vocabularyCard(toVocabularyModel({ word: '森林火灾', language_code: 'zh' }, { supportLanguage: 'vi' }), { mode: 'detail' }), 'front').includes('style="--len:4"'), 'a four-character word fits by its own length');
assert.doesNotMatch(cardCss, /@media/, 'no width media query (rule 49 recomposes by the pairs\' own columns)');
// Each face: a body that never scrolls (the fit contains it), a foot that keeps the turn action in view.
assert.match(cardCss, /\.c-vcard__body \{[^}]*min-height: 0;/, 'the body shares the face height');
assert.doesNotMatch(cardCss.match(/\.c-vcard__body \{[^}]*\}/)[0], /overflow/, 'the face body does not scroll');
assert.match(cardCss, /\.c-vcard__foot \{[^}]*flex: none/, 'the turn action never shrinks out of view');
assert.ok(enCard.includes('<div class="c-vcard__body">'));
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

/* --- D-180: the header as drawn, and nothing of the app's palette inside the card --- */
for (const card of [enCard, zhCard]) {
  // The human, 2026-10-13: play and Save sit top right, on the part of speech's row, smaller, so the illustration
  // takes the room the old action row had.
  const front = faceOf(card, 'front');
  const head = front.slice(front.indexOf('<div class="c-vcard__top">'), front.indexOf('c-vcard__body'));
  // The human, 2026-10-13: the part of speech beside the level, on the left; the discs alone on the right.
  const tags = head.slice(head.indexOf('c-vcard__tags'), head.indexOf('c-vcard__top-end'));
  assert.ok(tags.indexOf('c-vcard__level') < tags.indexOf('c-vcard__pos') && tags.includes('c-vcard__pos'), 'part of speech beside the level, in the left group');
  const end = head.slice(head.indexOf('c-vcard__top-end'));
  assert.ok(!end.includes('c-vcard__pos') && end.indexOf('data-play') < end.indexOf('data-save'), 'only play and Save on the right');
  assert.match(cardCss, /\.c-vcard__top \{[^}]*flex-wrap: nowrap/, 'the discs stay on the first line; the left group wraps in its own column');
  assert.equal((front.match(/data-play/g) || []).length, 1, 'one play disc on the face');
  assert.ok(!front.slice(front.indexOf('c-vcard__body')).includes('c-vcard__actions'), 'no action row left in the body');
}
// Chinese: Meaning and Radical side by side (two columns), not stacked.
const lead = zhFront.slice(zhFront.indexOf('c-vcard__lead'));
assert.ok(lead.indexOf('sectionMeaning') < lead.indexOf('sectionRadical') && lead.indexOf('sectionRadical') < lead.indexOf('sectionMeasureWord'), 'Meaning and Radical share the lead grid');
// The human, 2026-10-13: Radical lines up with Related words below it - the lead uses the pair's own columns and
// column gap, so a long meaning wraps inside its column and never moves the radical.
const ruleBody = (selector) => (cssRules.find(([sel]) => sel === selector) || [])[1] || '';
const declOf = (selector, prop) => (ruleBody(selector).match(new RegExp(`(?:^|[;\\s])${prop}:\\s*([^;]+);`)) || [])[1];
assert.equal(declOf('.c-vcard__lead', 'display'), 'grid');
assert.equal(declOf('.c-vcard__lead', 'grid-template-columns'), declOf('.c-vcard__pair', 'grid-template-columns'), 'the same columns as the pair below');
assert.equal(declOf('.c-vcard__lead', 'column-gap'), declOf('.c-vcard__pair', 'column-gap'), 'and the same gap between them');
assert.ok(!cardCss.includes('c-vcard__lead--two') && !zhFront.includes('c-vcard__lead--two'), 'no content-sized meaning column');
const kitCardSrc = readFileSync(new URL('../static/orena/kit/vocabulary-card.js', import.meta.url), 'utf8');
assert.doesNotMatch(kitCardSrc.replace(/\/\*[\s\S]*?\*\//g, ''), /o-tag/, 'no kit tag on the content');
const contentCss = cssRules.filter(([selector]) => !isButtonRule(selector)).map(([selector, body]) => `${selector}{${body}}`).join('');
assert.doesNotMatch(contentCss, /--accent|accent-fill|accent-soft|accent-ink/, 'no app accent on the card content');
for (const card of [enCard, zhCard, String(vocabularyCard(zh, { mode: 'review-back', learner: learnerState({ review_stage: 1, next_review_at: '' }) }))]) {
  assert.doesNotMatch(card, /o-tag|var\(--accent|accent-fill|accent-soft|accent-ink/, 'the rendered content carries no kit tag or app accent');
  // The buttons are the app's kit buttons.
  assert.ok(card.includes('class="o-btn o-btn--primary c-vcard__turn" data-vcard-turn="back"'), 'See examples is the kit primary button');
  assert.ok(card.includes('class="o-btn o-btn--secondary c-vcard__turn" data-vcard-turn="front"'), 'Front is the kit secondary button');
}
assert.doesNotMatch(String(vocabularyCard(en, { mode: 'review-front' })), /o-tag|var\(--accent/);
const tagged2 = String(vocabularyCard(pineAlone, { mode: 'detail', slots: { meaningLabel: () => 'Tiếng Anh' } }));
assert.ok(tagged2.includes('<span class="c-vcard__lang">Tiếng Anh</span>'), 'the meaning language tag is drawn by the card');
// The discs are drawn 34px (the human, 2026-10-13: smaller, top right) and still take a 44px touch target.
assert.match(cardCss, /\.c-vcard__disc \{[^}]*box-sizing: border-box;[^}]*width: 44px;[^}]*height: 44px;[^}]*padding: 5px;[^}]*margin: -5px;[^}]*background-clip: content-box/, 'a 44px target, drawn and laid out at 34px');
// A `background` shorthand after it would reset the clip and paint the whole 44px: the discs set only the colour.
for (const [selector, body] of cssRules.filter(([selector]) => /\.c-vcard__disc/.test(selector))) {
  assert.doesNotMatch(body, /(^|[;\s])background:/, `${selector} sets background-color, never the shorthand`);
}
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
