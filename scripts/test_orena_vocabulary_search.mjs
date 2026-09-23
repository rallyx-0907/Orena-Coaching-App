/* The room's own search: the learner's words and the catalogue's.
 *
 * Frames 20 and 21. Two things matter most here and are easy to lose: that
 * neither half is searched in the browser, and that this search does not touch
 * the shared top bar, which searches the whole app.
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { FILTERS, vocabularySearchHtml } from '../static/orena/ui/vocabulary-search.js';

const read = (path) => readFileSync(new URL(`../static/orena/${path}`, import.meta.url), 'utf8');
const screen = read('ui/vocabulary-search.js');
const room = read('ui/expression.js');
const api = read('infrastructure/api.js');
const css = read('rooms.css');
const appPy = readFileSync(new URL('../app.py', import.meta.url), 'utf8');

/* --- Both halves are the server's --------------------------------------- */

assert.match(room, /api\.libraryVocabulary\(\{ query: wanted, limit: SEARCH_LIMIT \}\)/,
  "the learner's words are searched where they live");
assert.match(room, /api\.vocabularyCatalogueSearch\(wanted, language, SEARCH_LIMIT\)/,
  'and the catalogue where it lives');
/* The screen draws what it was given. The only place it looks at the query is
   to pick it out inside a word it has already been handed - never to decide
   whether a word belongs in the list. */
assert.doesNotMatch(screen, /\.filter\([^)]*query|\.includes\(query|indexOf\(query\)/,
  'no row is chosen in the browser');
assert.match(screen, /function matched\(word, query\)/, 'the query is used to mark a match, not to find one');
assert.match(api, /\/api\/vocabulary\/catalogue\/search\?q=/, 'the catalogue search is its own read');
assert.match(appPy, /limit: int = Query\(default=20, ge=1, le=50\)/,
  'which names its own bound, so no query can ask for the catalogue whole');

/* --- The room's search, not the app's ----------------------------------- */

assert.doesNotMatch(screen, /topbar|data-search-global/, 'the shared top bar is left alone');
assert.match(room, /view === 'search' \? vocabularySearchHtml/, 'this search is a view of this room');

/* --- What the frame draws ----------------------------------------------- */

assert.deepEqual(FILTERS, ['all', 'saved', 'dictionary'], 'three chips, in the frame’s order');

const c = {
  vocabularySearch: 'Search', vocabularyFilterAll: 'All', vocabularySearchSaved: 'Saved',
  vocabularySearchDictionary: 'Dictionary', vocabularySearchClear: 'Clear', cancel: 'Cancel',
  vocabularyNoMatches: 'Nothing', vocabularySave: 'Save', vocabularySaved: 'Saved',
  vocabularyDueState: 'due',
};
const drawn = vocabularySearchHtml(c, {
  query: 'gle',
  filter: 'all',
  saved: [{ word: 'glede', definition: 'joy', due: true }],
  catalogue: [{ word: 'glemme', short_meanings: [{ text: 'forget' }], part_of_speech: 'verb' }],
  savedTotal: 2,
  language: 'no',
});
assert.match(drawn, /<b>gle<\/b>de/, 'what was typed is picked out where it stands');
assert.match(drawn, /data-search-keep="glemme"/, 'a catalogue word offers the one thing worth offering');
assert.doesNotMatch(drawn, /data-search-keep="glede"/, 'a word already kept is not offered again');
assert.match(drawn, /Dictionary · NO/, 'the dictionary says which language it is');

/* A word the learner has kept shows as kept, not as a second row to keep. */
const both = vocabularySearchHtml(c, {
  query: 'gle',
  filter: 'all',
  saved: [{ word: 'glemme', definition: 'forget' }],
  catalogue: [{ word: 'glemme', short_meanings: [{ text: 'forget' }] }],
  language: 'no',
});
assert.match(both, /vocab-search__kept/, 'the catalogue row says it is already kept');

/* Nothing typed draws no list at all - not an empty one. */
const idle = vocabularySearchHtml(c, { query: '', filter: 'all', language: 'no' });
assert.doesNotMatch(idle, /vocab-search__label/, 'before anything is typed there is nothing to label');
assert.doesNotMatch(idle, /Nothing/, 'and nothing is not "no matches"');

/* --- Measured ------------------------------------------------------------ */

for (const [what, rule] of [
  ['the field', /\.vocab-search__field \{[^}]*block-size: 46px;[^}]*border-radius: 14px;/s],
  ['a chip', /\.vocab-search__chip \{\n  padding: 8px 14px;/],
  ['a result', /\.vocab-search__word \{[^}]*font-size: 18px;/s],
  ['its note', /\.vocab-search__note \{ font-size: 12\.5px;/],
  ['the keep button', /\.vocab-search__keep \{[^}]*inline-size: 44px;[^}]*border-radius: 13px;/s],
  ["the room's head", /\.vocab-library__search \{\n  inline-size: 42px;/],
])
  assert.match(css, rule, `${what} is the frame’s size`);

console.log('test_orena_vocabulary_search.mjs: both halves searched where they live');
