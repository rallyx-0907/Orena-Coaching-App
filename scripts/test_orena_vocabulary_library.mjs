/* The curated vocabulary collections (TOEIC, HSK, ...), distinct from what the
   learner has saved and is reviewing. They render through the one shared card
   renderer and the one shared save path - never a second card shape, never a
   second save endpoint.

   Under D-064 they live where the approved design draws them: the Vocabulary
   home lists the learner's collections, "browse" opens the full catalogue, and
   a collection opens on the approved detail. The retired Discover-side library
   section is gone with the composition it belonged to. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { copy } from '../static/orena/ui/copy.js';
import {
  mapVocabularySupportTranslation,
  vocabularyKeepPayload,
} from '../static/orena/ui/world.js';
import { renderVocabularyCollectionCard } from '../static/orena/ui/vocabulary-experience.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

const cardEN = {
  identity: { language: 'en', normalized: 'take off' },
  headword: 'take off',
  pronunciation: '/teɪk ɒf/',
  part_of_speech: 'phrasal verb',
  meanings: [
    { language: 'en', text: 'to leave the ground' },
    { language: 'vi', text: 'cất cánh' },
  ],
  level: 'B1',
  framework: 'toeic',
};

/* --- The support meaning is read from the card, never invented ----------- */
assert.equal(mapVocabularySupportTranslation(cardEN, 'vi'), 'cất cánh');
assert.equal(
  mapVocabularySupportTranslation(cardEN, 'zh'),
  'cất cánh',
  'an unavailable support language falls back to the recorded one rather than to nothing',
);
assert.equal(mapVocabularySupportTranslation({ meanings: [] }, 'vi'), '');

/* --- One save payload, whichever surface keeps the word ------------------ */
const payload = vocabularyKeepPayload(cardEN, 'collection', 'vi');
assert.equal(payload.source_kind, 'collection');
assert.equal(payload.word, 'take off');
assert.equal(payload.translation_vi, 'cất cánh');

/* --- A collection card states real progress, from the collection itself -- */
const card = renderVocabularyCollectionCard(copy.en, {
  id: 'toeic-core', title: 'TOEIC Core', framework: 'toeic', level: 'B1', item_count: 150,
  progress: { learned_count: 87, learning_count: 40, due_count: 12, mastered_count: 47 },
});
assert.match(card, /87 \/ 150/, 'a collection says how far through it the learner is');
assert.match(card, /data-open-collection="toeic-core"/, 'and opens on itself');

/* --- Wiring: the library room owns the collections (D-067) --------------- */
const expression = read('static/orena/ui/expression.js');
const world = read('static/orena/ui/world.js');
assert.match(expression, /api\.vocabularyLibraryCollections\(language\)/, 'the library reads the catalogue');
assert.match(expression, /class="vocab-packs"/, 'and draws every collection it holds');
assert.match(expression, /data-vocabulary-collection="/, 'each one opening on itself');
assert.match(expression, /class="vocab-collection-page"/, 'a collection opens on the approved detail');
assert.match(expression, /collectionError/, 'a failed read is stated, not left blank');
assert.match(expression, /vocabularyLibraryEmpty/, 'and so is a language with no collections yet');
assert.doesNotMatch(world, /vocabularyLibrarySection/, 'the retired library section is gone');

for (const key of ['vocabularyLibraryTitle', 'vocabularyLibraryEmpty', 'vocabularyWordCount'])
  for (const ui of ['en', 'zh']) assert.ok(copy[ui][key], `${ui}.${key} is missing`);

console.log('Vocabulary collections: one card, one save path, real progress, approved home, EN/ZH PASS');
