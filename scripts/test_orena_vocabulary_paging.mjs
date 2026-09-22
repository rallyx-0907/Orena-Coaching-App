/* No screen may read a learner's whole vocabulary.
 *
 * Listing every saved word cost three minutes for a learner with sixteen
 * hundred of them, and Vocabulary, Tiến độ, Hồ sơ and Home all waited on that
 * one list. The fix was not only to make the query fast: a screen that shows a
 * count must ask for the count, a screen that shows a queue must ask for the
 * queue, and the library itself must arrive a page at a time.
 *
 * These assertions pin that, because it is the kind of thing a later hand
 * undoes by accident - one convenient `await api.libraryVocabulary()` and the
 * whole library is back in the browser.
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(`../static/orena/${path}`, import.meta.url), 'utf8');

const api = read('infrastructure/api.js');
const rooms = {
  'ui/profile.js': read('ui/profile.js'),
  'ui/progress.js': read('ui/progress.js'),
  'ui/world.js': read('ui/world.js'),
  'ui/expression.js': read('ui/expression.js'),
  'ui/collection.js': read('ui/collection.js'),
  'ui/search.js': read('ui/search.js'),
  'ui/library.js': read('ui/library.js'),
};

/* --- The client offers both shapes, and the page one takes parameters --- */

assert.match(api, /libraryVocabulary:\(params=\{\}\)=>/, 'the page takes parameters');
for (const key of ['limit', 'cursor', 'query', 'status', 'order', 'focus'])
  assert.ok(api.includes(`params.${key}`), `the client passes ${key} to the server`);
assert.match(api, /libraryVocabularySummary:\(\)=>/, 'and there is a counts-only contract');
assert.match(api, /\/api\/library\/vocabulary\/summary/, 'which is its own endpoint');

/* --- Nobody asks for everything ---------------------------------------- */

for (const [name, source] of Object.entries(rooms)) {
  assert.doesNotMatch(
    source,
    /api\.libraryVocabulary\(\s*\)/,
    `${name} must not read the learner's whole vocabulary`,
  );
  for (const call of source.match(/libraryVocabulary\(\{[^}]*\}/g) || []) {
    assert.ok(
      /limit:|focus:/.test(call),
      `${name} asks for a bounded page: ${call.slice(0, 60)}`,
    );
  }
}

/* --- The summary screens use the summary -------------------------------- */

for (const name of ['ui/profile.js', 'ui/progress.js', 'ui/world.js'])
  assert.match(rooms[name], /libraryVocabularySummary\(\)/, `${name} reads the counts, not the words`);

/* Tiến độ shows three recent words, so it asks for three. */
assert.match(rooms['ui/progress.js'], /const RECENT_WORDS = 3;/, 'the recent panel names its size');
assert.match(
  rooms['ui/progress.js'],
  /libraryVocabulary\(\{ limit: RECENT_WORDS, order: 'recent' \}\)/,
  'and asks for exactly that many',
);

/* --- Counting, searching and filtering happen in the database ----------- */

assert.doesNotMatch(
  rooms['ui/progress.js'],
  /items\.filter\(/,
  'Tiến độ does not count words in the browser',
);
assert.doesNotMatch(
  rooms['ui/world.js'],
  /\.filter\(\(item\) => item\.due\)/,
  'Home does not count what is due in the browser',
);
assert.match(rooms['ui/search.js'], /libraryVocabulary\(\{ query: wanted/, 'search is a query');
assert.match(rooms['ui/collection.js'], /query: state\.query\.trim\(\)/, 'so is the saved panel\'s search');
assert.match(rooms['ui/expression.js'], /cursor: append \? savedData\.next_cursor/, 'and the room pages with the cursor');

/* --- The rank is read from the server, never recomputed ----------------- */

const rank = read('product/rank.js');
assert.doesNotMatch(rank, /RANK_THRESHOLDS|tierOf|masteredCount/, 'the browser holds no thresholds');
assert.match(rank, /rank_total/, 'it reads the rank the server sends');

console.log('test_orena_vocabulary_paging.mjs: no screen reads the whole vocabulary');
