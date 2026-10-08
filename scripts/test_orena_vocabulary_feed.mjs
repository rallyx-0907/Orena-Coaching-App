/* The daily vocabulary feed: a day-seeded view over the same curated catalog
   the vocabulary collections browse - one content set, not a second one.

   The pre-cutover Home rail and its keep payload (ui/world.js) went with the
   retired UI (D-143). The learner UI's Feed screen is gated by
   test_orena_screen_feed.mjs (it checks the `source_kind: 'feed'` save payload
   over the one save path). What stays here is the request contract of the
   shared API client and the Feed screen's use of it. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

// --- API URL construction, target_level only appended when provided ---
const requested = [];
globalThis.fetch = async (url) => {
  requested.push(String(url));
  return { ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => ({ items: [], date: '2026-09-14' }) };
};
const { api } = await import('../static/orena/infrastructure/api.js');
await api.dailyVocabularyFeed('en');
assert.equal(requested.at(-1), '/api/vocabulary/feed?language_code=en');
await api.dailyVocabularyFeed('zh', 'HSK1');
assert.equal(requested.at(-1), '/api/vocabulary/feed?language_code=zh&target_level=HSK1');

/* --- Wiring: the Feed screen reads this contract, and keeps through the one
   save path - no second feed, no second save endpoint. */
const feed = read('static/orena/screens/feed/screen.js');
const model = read('static/orena/screens/feed/model.js');
assert.match(feed, /api\.dailyVocabularyFeed\(language, /, 'the Feed asks for the day’s words');
assert.match(model, /source_kind: 'feed'/, 'and keeps them through the shared save payload');
assert.doesNotMatch(read('static/orena/screens/library/screen.js'), /dailyVocabularyFeed/, 'the Library carries no second feed');

console.log('Daily Vocabulary Feed: one content set, one save path, API contract PASS');
