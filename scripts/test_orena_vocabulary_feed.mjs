/* Daily Vocabulary Feed: a filtered, day-seeded view over the same curated
   catalog Vocabulary Library browses - a second Discover section, not a
   second content set. "Keep" reuses the existing save path with
   source_kind='feed' and removes the kept word from the local list
   optimistically; empty and error states say what actually happened.
   docs/superpowers/plans/2026-09-14-vocabulary-experience.md Task E. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { copy } from '../static/orena/ui/copy.js';
import {
  discoveryVocabularySection,
  vocabularyFeedCardAfterSlot,
  vocabularyFeedSection,
  vocabularyKeepPayload,
} from '../static/orena/ui/world.js';

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

// --- The one save payload shape, tagged for Feed specifically ---
const payload = vocabularyKeepPayload(cardZH, 'feed', 'vi');
assert.equal(payload.source_kind, 'feed');
assert.equal(payload.word, '休息');
assert.equal(payload.translation_vi, 'nghỉ ngơi');

// --- Each Feed card offers exactly one keep action, indexed for optimistic removal ---
assert.match(vocabularyFeedCardAfterSlot(copy.en, 2), /data-feed-keep="2"/);

for (const ui of ['en', 'zh']) {
  const c = copy[ui];

  const discovery = discoveryVocabularySection(c);
  assert.doesNotMatch(discovery, /data-vocabulary-library/, `${ui} Discovery does not mount the Vocabulary Library`);
  assert.match(discovery, /data-vocabulary-feed/, `${ui} Discovery keeps the Daily Feed mount`);

  // Loading is truthful: no candidates claimed before any arrive.
  assert.match(vocabularyFeedSection(c, {}), new RegExp(c.vocabularyFeedLoading));

  // A fetch failure is a stated notice with retry, never a silent blank.
  const errored = vocabularyFeedSection(c, { error: true });
  assert.match(errored, new RegExp(c.unavailable));
  assert.match(errored, /data-feed-retry/);

  // No candidates left today is said plainly, not shown as a spinner or blank.
  const empty = vocabularyFeedSection(c, { items: [] });
  assert.match(empty, new RegExp(c.vocabularyFeedEmpty));
  assert.doesNotMatch(empty, /data-feed-retry/, 'an empty feed is not treated as an error');

  // A real feed is a compact discovery surface and offers save.
  const withItems = vocabularyFeedSection(c, { items: [cardZH] });
  assert.match(withItems, /class="vocabulary-browse-card vocabulary-feed-slide"/, 'Feed uses compact discovery cards');
  assert.match(withItems, /休息/);
  assert.match(withItems, /data-feed-keep="0"/);
  assert.match(withItems, /data-vocabulary-feed-carousel/);
  assert.match(withItems, /data-vocabulary-feed-track/);
  assert.match(withItems, /vocabulary-feed-carousel--discovery/);
  assert.doesNotMatch(withItems, /vocabulary-feed-preview--grid/);
}

for (const key of ['vocabularyFeedTitle', 'vocabularyFeedPrevious', 'vocabularyFeedNext', 'vocabularyFeedNote', 'vocabularyFeedLoading', 'vocabularyFeedEmpty'])
  for (const ui of ['en', 'zh']) assert.ok(copy[ui][key], `${ui}.${key} is missing`);

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

// --- Wiring: the Discover surface actually calls this contract, not a copy ---
const world = read('static/orena/ui/world.js');
assert.match(world, /api\.dailyVocabularyFeed\(language\)/);
assert.match(world, /vocabularyKeepPayload\(card, 'feed', support\)/);
assert.match(
  world,
  /items = items\.filter\(\(_, i\) => i !== index\)/,
  'a kept Feed word is removed from the local list, not reloaded from the server',
);
assert.match(world, /data-vocabulary-feed/);
assert.match(world, /renderVocabularyFeedCarousel/);
assert.match(world, /bindVocabularyFeedCarousel/);

console.log('Daily Vocabulary Feed: shared card/save path, source_kind feed, truthful empty/error states, EN/ZH PASS');
