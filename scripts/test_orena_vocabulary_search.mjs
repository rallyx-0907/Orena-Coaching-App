/* The vocabulary search's server contract: the learner's words and the catalogue's.
 *
 * Neither half is searched in the browser, and the catalogue search names its own bound.
 * (The learner UI's search screen is test_orena_screen_search.mjs.)
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(`../static/orena/${path}`, import.meta.url), 'utf8');
const api = read('infrastructure/api.js');
const appPy = readFileSync(new URL('../app.py', import.meta.url), 'utf8');

assert.match(api, /libraryVocabulary:/, "the learner's words are searched where they live");
assert.match(api, /\/api\/vocabulary\/catalogue\/search\?q=/, 'the catalogue search is its own read');
assert.match(appPy, /limit: int = Query\(default=20, ge=1, le=50\)/,
  'which names its own bound, so no query can ask for the catalogue whole');

console.log('test_orena_vocabulary_search.mjs: both halves searched where they live');
