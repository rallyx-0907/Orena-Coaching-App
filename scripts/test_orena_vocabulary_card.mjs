import assert from 'node:assert/strict';
import { renderVocabularyCard } from '../static/orena/ui/vocabulary-card.js';

const copy = {
  meaning: 'Meaning',
  pronunciation: 'Pronunciation',
  sourceContext: 'Original context',
  strokeCount: 'strokes',
};

const english = renderVocabularyCard(copy, {
  identity: { language: 'en', normalized: 'take off' },
  headword: 'take off',
  pronunciation: '/teɪk ɒf/',
  meanings: [{ language: 'en', text: 'to leave the ground' }],
  source_encounters: [{ kind: 'reading', fragment: 'The plane will take off.' }],
});
assert.match(english, /class="vocabulary-card"/);
assert.match(english, /take off/);
assert.match(english, /to leave the ground/);
assert.match(english, /The plane will take off\./);
assert.match(english, /lang="en"/);

const chinese = renderVocabularyCard(copy, {
  identity: { language: 'zh', normalized: '学习' },
  headword: '学习',
  meanings: [{ language: 'en', text: 'to study' }],
  orthography: {
    script: 'han',
    characters: [{ character: '学', stroke_count: 8, stroke_paths: ['M0 0'] }],
  },
});
assert.match(chinese, /lang="zh"/);
assert.match(chinese, /data-orthography-script="han"/);
assert.match(chinese, /学/);
assert.match(chinese, /8 strokes/);

assert.throws(
  () => renderVocabularyCard(copy, { headword: '', meanings: [] }),
  /headword/,
);

console.log('Orena Vocabulary Card renderer EN/ZH: PASS');
