/* The daily vocabulary feed: a day-seeded view over the same curated catalog
   the vocabulary collections browse - one content set, not a second one.

   Its home is Home: the approved design draws "words worth remembering" there
   (Screens part 1 section 01), and D-064 retired the second copy that used to
   sit in the Vocabulary room. "Keep" still reuses the one save path with
   source_kind='feed'. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { copy } from '../static/orena/ui/copy.js';
import { vocabularyKeepPayload } from '../static/orena/ui/world.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

const cardZH = {
  identity: { language: 'zh', normalized: '休息' },
  headword: '休息',
  pronunciation: 'xiūxi',
  meanings: [
    { language: 'zh', text: 'to rest' },
    { language: 'vi', text: 'nghỉ ngơi' },
  ],
  examples: [],
  collocations: [],
  related: [],
  learner_traps: [],
  level: 'HSK1',
  framework: 'hsk',
};

// --- The one save payload shape, tagged for the feed specifically ---
const payload = vocabularyKeepPayload(cardZH, 'feed', 'vi');
assert.equal(payload.source_kind, 'feed');
assert.equal(payload.word, '休息');
assert.equal(payload.translation_vi, 'nghỉ ngơi');

// --- API URL construction, target_level only appended when provided ---
let requested = [];
globalThis.fetch = async (url) => {
  requested.push(String(url));
  return { ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => ({ items: [], date: '2026-09-14' }) };
};
const { api } = await import('../static/orena/infrastructure/api.js');
await api.dailyVocabularyFeed('en');
assert.equal(requested.at(-1), '/api/vocabulary/feed?language_code=en');
await api.dailyVocabularyFeed('zh', 'HSK1');
assert.equal(requested.at(-1), '/api/vocabulary/feed?language_code=zh&target_level=HSK1');

/* --- Wiring: Home reads this contract, and keeps through the one save path.
   The Vocabulary room carries no second feed surface (D-064). */
const world = read('static/orena/ui/world.js');
const discovery = read('static/orena/ui/discovery.js');
const expression = read('static/orena/ui/expression.js');
assert.match(world, /api\.dailyVocabularyFeed\(language\)/, 'Home asks for the day’s words');
assert.match(world, /vocabularyKeepPayload\(card, 'feed', ctx\.support\)/, 'and keeps them through the shared payload');
assert.match(world, /data-discover-vocabulary-save/, 'the keep action is bound on Home');
assert.match(discovery, /data-today-words/, 'the words are the approved Home block');
assert.match(discovery, /data-discover-vocabulary-save="\$\{index\}"/, 'each card offers exactly one keep, indexed');
assert.doesNotMatch(expression, /dailyVocabularyFeed/, 'the Vocabulary room does not carry a second feed');
assert.doesNotMatch(world, /vocabularyFeedSection|discoveryVocabularySection/, 'the retired feed sections are gone');

/* A kept word is marked kept where it stands, rather than reloading the list. */
assert.match(world, /card\.saved = true/, 'keeping updates the card in place');

for (const key of ['vocabularySave', 'vocabularySaved', 'vocabularyStudy'])
  for (const ui of ['en', 'zh']) assert.ok(copy[ui][key], `${ui}.${key} is missing`);

console.log('Daily Vocabulary Feed: one content set, one save path, kept on Home, EN/ZH PASS');
