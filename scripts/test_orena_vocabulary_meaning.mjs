import assert from 'node:assert/strict';
import { localizedMeaning, meaningLanguageLabel, vocabularyMeaning } from '../static/orena/product/vocabulary-meaning.js';
import { wordRow } from '../static/orena/screens/collection/model.js';
import { reviewCard } from '../static/orena/screens/review/model.js';
import { languageRows } from '../static/orena/screens/library/model.js';

/* D-124: one sense, a localization per support language; no language is special-cased except the
   learner record's older Vietnamese copy, which is only the Vietnamese localization. */
const sense = {
  language_code: 'zh',
  short_meanings: [
    { language: 'zh', text: '松科植物' },
    { language: 'en', text: 'pine; pine tree', origin: 'dictionary' },
    { language: 'fr', text: 'pin' },
  ],
  support_translations: { vi: 'cây thông' },
};

for (const [language, text] of [['en', 'pine; pine tree'], ['fr', 'pin'], ['vi', 'cây thông']]) {
  assert.deepEqual(localizedMeaning(sense, language), { text, language, source: 'localization' });
}
// A support language with no localization: the learner's note first, then another language, tagged.
assert.equal(localizedMeaning(sense, 'ja'), null);
assert.deepEqual(vocabularyMeaning({ ...sense, definition: 'my note' }, 'ja'), { text: 'my note', language: '', source: 'note' });
assert.deepEqual(vocabularyMeaning(sense, 'ja'), { text: 'pine; pine tree', language: 'en', source: 'other_language' });
// The sense's own-language definition is not a localization.
assert.equal(vocabularyMeaning({ language_code: 'zh', short_meanings: [{ language: 'zh', text: '松科植物' }] }, 'vi'), null);
// The older saved copy is Vietnamese only, and the sense's own localization wins over it.
assert.deepEqual(localizedMeaning({ translation_vi: 'khoảng đệm' }, 'vi'), { text: 'khoảng đệm', language: 'vi', source: 'saved' });
assert.equal(localizedMeaning({ translation_vi: 'khoảng đệm' }, 'en'), null);
assert.equal(localizedMeaning({ ...sense, translation_vi: 'old copy' }, 'vi').text, 'cây thông');
// Adding a support language is data: a new localization row is found with no code change.
assert.equal(localizedMeaning({ short_meanings: [{ language: 'th', text: 'ต้นสน' }] }, 'th').text, 'ต้นสน');
assert.equal(localizedMeaning(null, 'vi'), null);
assert.equal(localizedMeaning(sense, ''), null);

// The label (D-124): a meaning in another language names that language in the interface language;
// a meaning in the support language carries no label.
assert.equal(meaningLanguageLabel('en', 'vi', 'vi'), 'Tiếng Anh');
assert.equal(meaningLanguageLabel('en', 'vi', 'en'), 'English');
assert.equal(meaningLanguageLabel('en', 'vi', 'zh'), '英语');
assert.equal(meaningLanguageLabel('vi', 'vi', 'en'), '');
assert.equal(meaningLanguageLabel('', 'vi', 'en'), '');
const englishOnly = { identity: { language: 'zh', normalized: '松树' }, headword: '松树', meanings: [{ language: 'en', text: 'pine' }] };
assert.equal(wordRow(englishOnly, 'vi').meaningLanguage, 'en');
assert.equal(wordRow({ ...englishOnly, meanings: [{ language: 'vi', text: 'cây thông' }] }, 'vi').meaningLanguage, 'vi');
const saved = { word: '松树', language_code: 'zh', definition: '', short_meanings: [{ language: 'en', text: 'pine' }] };
assert.equal(reviewCard('松树', saved, 'vi').meaningLanguage, 'en');
assert.equal(languageRows([saved], 'vi')[0].subLanguage, 'en');
assert.equal(languageRows([{ ...saved, short_meanings: [{ language: 'vi', text: 'cây thông' }] }], 'vi')[0].subLanguage, '');

// LEX-070: a Han-script note under a non-Chinese support language says which language it is in.
assert.deepEqual(vocabularyMeaning({ definition: '一种常绿的树。' }, 'vi'), { text: '一种常绿的树。', language: 'zh', source: 'note' });
assert.equal(vocabularyMeaning({ definition: '一种常绿的树。' }, 'zh').language, '');

console.log('Vocabulary meaning: one sense, localized per support language, no fixed language: PASS');
