/* Vocabulary Library: a browsable curated catalog (TOEIC, HSK, ...), distinct
   from My Language's own saved/review state. It renders through the one
   shared Vocabulary Card renderer and the one shared save path - never a
   second card shape, never a second save endpoint, never a duplicate save
   affordance on a word already kept.
   docs/superpowers/plans/2026-09-14-vocabulary-experience.md Task E. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { copy } from '../static/orena/ui/copy.js';
import {
  groupVocabularyCollectionsByFramework,
  mapVocabularySupportTranslation,
  vocabularyKeepPayload,
  vocabularyLibraryCardAfterSlot,
  vocabularyLibrarySection,
} from '../static/orena/ui/world.js';

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
  examples: [],
  collocations: [],
  related: [],
  learner_traps: [],
  level: 'A2',
  framework: 'cefr-internal',
};

// --- Shared support-translation mapping, with its documented fallback ---
assert.equal(mapVocabularySupportTranslation(cardEN, 'vi'), 'cất cánh');
assert.equal(
  mapVocabularySupportTranslation(cardEN, 'zh'),
  'cất cánh',
  'no zh translation on this entry falls back to vi',
);
assert.equal(
  mapVocabularySupportTranslation({ ...cardEN, meanings: [cardEN.meanings[0]] }, 'zh'),
  '',
  'no support translation at all yields no invented text',
);

// --- One save payload shape; only source_kind tells "keep" actions apart ---
const payload = vocabularyKeepPayload(cardEN, 'collection', 'vi');
assert.equal(payload.source_kind, 'collection');
assert.equal(payload.word, 'take off');
assert.equal(payload.definition, 'to leave the ground');
assert.equal(payload.translation_vi, 'cất cánh');

// --- Collections group by framework, in first-seen order ---
const collections = [
  { id: 'toeic-600-essential', framework: 'toeic', level: 'A2', title: '600 TOEIC Essential', item_count: 35 },
  { id: 'common-3000', framework: 'cefr-internal', level: 'A1', title: '3000 Common Words', item_count: 35 },
  { id: 'toeic-extra', framework: 'toeic', level: 'B1', title: 'TOEIC Extra', item_count: 10 },
];
const grouped = groupVocabularyCollectionsByFramework(collections);
assert.deepEqual(grouped.map((g) => g.framework), ['toeic', 'cefr-internal']);
assert.equal(grouped[0].collections.length, 2, 'both TOEIC collections share one group');
assert.equal(grouped[1].collections.length, 1);

// --- A saved catalog card never offers a duplicate save affordance ---
const kept = vocabularyLibraryCardAfterSlot(copy.en, { ...cardEN, saved: true }, 0);
assert.doesNotMatch(kept, /data-library-keep/, 'a saved card has no save button');
assert.match(kept, new RegExp(copy.en.vocabularyAlreadyKept));
const unsaved = vocabularyLibraryCardAfterSlot(copy.en, { ...cardEN, saved: false }, 0);
assert.match(unsaved, /data-library-keep="0"/);

for (const ui of ['en', 'zh']) {
  const c = copy[ui];

  // Loading is truthful: no invented content while nothing has loaded.
  assert.match(vocabularyLibrarySection(c, {}), new RegExp(c.vocabularyLibraryLoading));

  // A fetch failure is a notice with a retry, not a silent empty list.
  const errored = vocabularyLibrarySection(c, { error: true });
  assert.match(errored, new RegExp(c.unavailable));
  assert.match(errored, /data-library-retry/);

  // No curated collections for this language is stated, not hidden.
  assert.match(
    vocabularyLibrarySection(c, { collections: [] }),
    new RegExp(c.vocabularyLibraryEmpty),
  );

  // The list groups by framework and links each collection by id.
  const list = vocabularyLibrarySection(c, { collections });
  assert.match(list, new RegExp(c.vocabularyFramework_toeic));
  assert.match(list, new RegExp(c.vocabularyFramework_cefrinternal));
  assert.match(list, /data-open-collection="toeic-600-essential"/);
  assert.match(list, /data-open-collection="common-3000"/);

  // Opening a collection is a compact management view over the same card data.
  const detail = vocabularyLibrarySection(c, {
    open: { id: 'common-3000', title: '3000 Common Words', items: [cardEN, { ...cardEN, saved: true }] },
  });
  assert.match(detail, /class="vocabulary-browse-card"/, 'Library uses compact browse cards');
  assert.match(detail, /take off/);
  assert.match(detail, /data-close-collection/);
  assert.match(detail, /data-library-keep="0"/, 'the unsaved row offers a save action');
  assert.match(detail, new RegExp(c.vocabularySaved), 'the saved row shows it is already saved');

  // Opening a collection can itself fail, or still be loading.
  assert.match(
    vocabularyLibrarySection(c, { open: { id: 'common-3000', items: null } }),
    new RegExp(c.vocabularyLibraryLoading),
  );
  const detailError = vocabularyLibrarySection(c, { open: { id: 'common-3000', error: true } });
  assert.match(detailError, new RegExp(c.unavailable));
  assert.match(detailError, /data-library-retry/);
}

for (const key of [
  'vocabularyLibraryTitle',
  'vocabularyLibraryNote',
  'vocabularyLibraryLoading',
  'vocabularyLibraryEmpty',
  'vocabularyLibraryBack',
  'vocabularyWordCount',
  'vocabularyAlreadyKept',
  'vocabularyFramework_toeic',
  'vocabularyFramework_hsk',
  'vocabularyFramework_cefrinternal',
])
  for (const ui of ['en', 'zh']) assert.ok(copy[ui][key], `${ui}.${key} is missing`);

// --- API URL construction, mirroring the existing libraryVocabulary() shape ---
let requested = [];
globalThis.fetch = async (url) => {
  requested.push(String(url));
  return { ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => ({ items: [] }) };
};
const { api } = await import('../static/orena/infrastructure/api.js');
await api.vocabularyLibraryCollections('zh');
assert.equal(requested.at(-1), '/api/vocabulary/library/collections?language_code=zh');
await api.vocabularyLibraryCollection('hsk 1');
assert.equal(requested.at(-1), '/api/vocabulary/library/collections/hsk%201', 'collection id is URL-encoded');

// --- Wiring: the Discover surface actually calls this contract, not a copy ---
const world = read('static/orena/ui/world.js');
assert.match(world, /renderVocabularyBrowseCard/);
assert.match(world, /api\.vocabularyLibraryCollections\(language\)/);
assert.match(world, /api\.vocabularyLibraryCollection\(id\)/);
assert.match(world, /vocabularyKeepPayload\(card, 'collection', support\)/);
assert.match(world, /data-vocabulary-library/);

console.log('Vocabulary Library: catalog grouping, no duplicate save, shared card/save path, EN/ZH PASS');
