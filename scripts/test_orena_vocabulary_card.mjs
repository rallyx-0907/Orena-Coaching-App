/* Gate for the shared vocabulary card (D-178, D-17W): the pure mapper
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
    provenance: { source_id: record.id, illustration: record.illustration, ...(record.en?.etymology_vi ? { etymology: { vi: record.en.etymology_vi } } : {}) },
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
assert.equal(en.illustration, null, 'a library reference with no asset behind it is no illustration');

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

/* --- markup per mode --- */
const plain = (markup) => String(markup).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
assert.deepEqual(CARD_MODES, ['detail', 'feed', 'review-front', 'review-back']);
for (const model of [en, zh]) {
  const front = String(vocabularyCard(model, { mode: 'review-front' }));
  const frontText = plain(front);
  assert.ok(front.includes('data-play'), 'review-front plays the word');
  assert.ok(!front.includes('data-save'), 'review-front has no save disc');
  assert.ok(!frontText.includes(model.meaning.text), 'review-front never shows the meaning');
  for (const example of model.examples) assert.ok(!frontText.includes(example.translation) || !example.translation, 'no translation on the front');
  assert.ok(!front.includes('c-vcard__example') && !front.includes('c-vcard__grid') && !front.includes('c-vcard__units') && !front.includes('c-vcard__meaning'), 'no answer block on the front');
  assert.deepEqual(Object.keys(frontFields(model)).sort(), ['language', 'level', 'pos', 'pronunciation', 'script', 'word']);

  const back = String(vocabularyCard(model, { mode: 'review-back', learner: learnerState({ review_stage: 2, next_review_at: '' }) }));
  assert.ok(plain(back).includes(model.meaning.text), 'review-back shows the meaning');
  assert.ok(back.includes('c-vcard__example'));
  assert.ok(back.includes('c-vcard__footer'), 'the learner footer when there is a schedule');
  assert.ok(!back.includes('<figure'), 'no illustration, no frame');
  assert.ok(!back.includes('data-grade'), 'the grades are the screen\'s, under the card');

  const detail = String(vocabularyCard(model, { mode: 'detail', learner: learnerState(null) }));
  assert.ok(detail.includes('data-save') && detail.includes('aria-pressed="false"'), 'detail offers Save');
  assert.ok(!detail.includes('c-vcard__footer'), 'no schedule, no footer');
  assert.ok(!detail.includes('data-grade'), 'Word Detail never grades');

  const feed = String(vocabularyCard(model, { mode: 'feed', learner: { saved: true } }));
  assert.ok(feed.includes('aria-pressed="true"'));
  assert.equal((feed.match(/class="c-vcard__example"/g) || []).length, 1, 'the feed shows the first example only');
}
const enDetail = String(vocabularyCard(en, { mode: 'detail' }));
assert.ok(enDetail.includes('<mark class="c-vcard__hit">resilient</mark>'));
assert.ok(enDetail.includes('/rɪˈzɪliənt/') && enDetail.includes('/rɪˈzɪljənt/'), 'both IPA readings');
assert.ok(!enDetail.includes('<ruby>'));
const zhDetail = String(vocabularyCard(zh, { mode: 'detail' }));
assert.ok(zhDetail.includes('<ruby>森<rt>sēn</rt></ruby><ruby>林<rt>lín</rt></ruby>'), 'Hanzi with their pinyin');
assert.ok(zhDetail.includes('<mark class="c-vcard__hit">森林</mark>'));
assert.ok(zhDetail.includes('<mark class="c-vcard__hit">sēnlín</mark>'));
assert.ok(zhDetail.includes('lang="zh"'));
assert.ok(zhDetail.includes('SÂM LÂM'));
const uploaded = toVocabularyModel({ ...EN, illustration: { kind: 'upload', ref: '/assets/x.png', alt_vi: 'x' } }, { supportLanguage: 'vi' });
assert.ok(String(vocabularyCard(uploaded, { mode: 'detail' })).includes('<figure class="c-vcard__art">'), 'an uploaded image is drawn');
assert.ok(!String(vocabularyCard(uploaded, { mode: 'review-front' })).includes('<figure'), 'never on the front');
assert.throws(() => vocabularyCard(en, { mode: 'flip' }));

/* --- the two review buttons --- */
assert.deepEqual(REVIEW_BUTTONS, ['again', 'got_it']);
assert.ok(GRADES.includes('unsure'), 'unsure stays a grade the API accepts');
const reviewSrc = readFileSync(new URL('../static/orena/screens/review/screen.js', import.meta.url), 'utf8');
assert.match(reviewSrc, /mode: 'review-front'/);
assert.match(reviewSrc, /mode: 'review-back'/);
assert.doesNotMatch(reviewSrc, /gradeButton\('unsure'/, 'no Unsure button');
const feedSrc = readFileSync(new URL('../static/orena/screens/feed/screen.js', import.meta.url), 'utf8');
assert.match(feedSrc, /mode: 'feed'/);
assert.doesNotMatch(feedSrc, /reviewLibraryVocabulary|data-grade/, 'the feed never grades');

/* --- every label in three languages, with diacritics --- */
for (const ui of ['en', 'vi', 'zh']) {
  setLanguages({ ui, support: ui });
  const out = String(vocabularyCard(en, { mode: 'detail' }));
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
