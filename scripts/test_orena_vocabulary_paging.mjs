/* No screen may read a learner's whole vocabulary.
 *
 * Listing every saved word cost three minutes for a learner with sixteen
 * hundred of them, and Vocabulary, Progress, Profile and Home all waited on
 * that one list. The fix was not only to make the query fast: a screen that
 * shows a count must ask for the count, a screen that shows a queue must ask
 * for the queue, and the library itself must arrive a page at a time.
 *
 * These assertions pin that across every learner-UI module (D-143: screens,
 * shell, product, kit, agent and the remaining capabilities), because it is
 * the kind of thing a later hand undoes by accident - one convenient
 * `await api.libraryVocabulary()` and the whole library is back in the browser.
 */
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';

const root = new URL('../static/orena/', import.meta.url);
const read = (path) => readFileSync(new URL(path, root), 'utf8');

const walk = (dir) =>
  readdirSync(new URL(dir, root), { withFileTypes: true }).flatMap((entry) =>
    entry.isDirectory() ? walk(`${dir}${entry.name}/`) : entry.name.endsWith('.js') ? [`${dir}${entry.name}`] : []);
const learnerModules = Object.fromEntries(
  ['screens/', 'shell/', 'product/', 'kit/', 'agent/', 'capabilities/'].flatMap(walk).map((path) => [path, read(path)]),
);
learnerModules['main.js'] = read('main.js');
assert.ok(Object.keys(learnerModules).length > 100, 'the learner UI modules were found');

const api = read('infrastructure/api.js');

/* --- The client offers both shapes, and the page one takes parameters --- */

assert.match(api, /libraryVocabulary:\(params=\{\}\)=>/, 'the page takes parameters');
for (const key of ['limit', 'cursor', 'query', 'status', 'order', 'focus'])
  assert.ok(api.includes(`params.${key}`), `the client passes ${key} to the server`);
assert.match(api, /libraryVocabularySummary:\(\)=>/, 'and there is a counts-only contract');
assert.match(api, /\/api\/library\/vocabulary\/summary/, 'which is its own endpoint');

/* --- Nobody asks for everything ---------------------------------------- */

let pageCalls = 0;
for (const [name, source] of Object.entries(learnerModules)) {
  assert.doesNotMatch(
    source,
    /api\.libraryVocabulary\(\s*\)/,
    `${name} must not read the learner's whole vocabulary`,
  );
  for (const call of source.match(/libraryVocabulary\(\{[^}]*\}/g) || []) {
    pageCalls += 1;
    assert.ok(
      /limit:|focus:/.test(call),
      `${name} asks for a bounded page: ${call.slice(0, 60)}`,
    );
  }
}
assert.ok(pageCalls > 0, 'the scan found the paged reads in the screens');

/* --- The summary screens use the summary -------------------------------- */

for (const name of ['screens/profile/screen.js', 'screens/progress/screen.js'])
  assert.match(learnerModules[name], /libraryVocabularySummary\(\)/, `${name} reads the counts, not the words`);

/* Counting happens in the database: the Library asks for the queue itself, by
   status and order, rather than filtering the whole list for what is due. */
assert.match(learnerModules['screens/library/screen.js'], /libraryVocabulary\(\{ status: 'due', order: 'due', limit: 50 \}\)/,
  'what is due is asked for, not counted in the browser');
assert.doesNotMatch(learnerModules['screens/progress/screen.js'], /items\.filter\(/, 'Progress does not count words in the browser');

/* --- The server does not read the listing to answer membership --------- */

/* Four routes used to read every saved word to answer "is this one saved?".
   They ask about the words they are drawing instead. */
const appPy = readFileSync(new URL('../app.py', import.meta.url), 'utf8');
assert.doesNotMatch(
  appPy,
  /list_library_vocabulary\(\)/,
  'no route reads the whole listing',
);
/* A reference is a call too. Two wirings passed the listing function itself
   and the owner called it with no arguments, which after paging is the first
   default page reported as the whole library. Every wiring hands over a
   reader that is given a limit. */
assert.doesNotMatch(
  appPy,
  /library=list_library_vocabulary/,
  'and no wiring hands the listing over unbounded',
);
assert.match(
  appPy,
  /library=lambda limit: list_library_vocabulary\(limit=limit\)/,
  'the wirings pass a reader that takes its bound',
);
for (const helper of ['saved_vocabulary_words', 'saved_vocabulary_state'])
  assert.ok(appPy.includes(helper), `the routes use ${helper}`);

/* --- The rank is read from the server, never recomputed ----------------- */

const rank = read('product/rank.js');
assert.doesNotMatch(rank, /RANK_THRESHOLDS|tierOf|masteredCount/, 'the browser holds no thresholds');
assert.match(rank, /rank_total/, 'it reads the rank the server sends');

console.log('test_orena_vocabulary_paging.mjs: no screen reads the whole vocabulary');
