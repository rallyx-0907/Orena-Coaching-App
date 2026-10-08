/* Thư viện của tôi: a relationship store, not a second library.

   The library lists what the learner kept over the owners that already hold
   it, and writes only the learner's own relationship to those things - kept,
   marked, filed. These assertions stop the quiet ways that stops being true:
   a second review scheduler, an unversioned write, a set that mixes kinds.

   The pre-cutover room (ui/collection.js) went with the retired UI (D-143);
   the learner UI's Collection screen is gated by
   test_orena_screen_collection.mjs and test_orena_collection_actions.mjs.
   What stays here is the server contract, which is unchanged and still
   serves any client.

   Schema and decision: `migrations/versions/20260923_0013_my_library_and_
   entry_identity.py`, D-074, reviewed by independent architecture review. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const api = read('static/orena/infrastructure/api.js');
const routes = read('writing_coach/library_api.py');
const repository = read('writing_coach/persistence/library_repository.py');

/* --- One read for the page, not one per row ---------------------------- */
assert.match(api, /libraryItems:\(\{kind='',words=\[\],sources=\[\]\}/, 'the lookup takes the whole page at once');

/* --- Every write carries the version it read --------------------------- */
assert.match(routes, /expected_version: int = Field\(ge=1\)/, 'the route requires a version');
assert.match(
  repository,
  /if int\(item\.version\) != int\(expected_version\):\s*\n\s*raise LibraryConflict\("version_conflict"\)/,
  'which the repository checks rather than trusting',
);

/* --- No second scheduler ------------------------------------------------ */
/* Words are scheduled in `saved_words`. The library orders the queue by the
   pin and by that schedule; it never computes an interval of its own. */
assert.doesNotMatch(repository, /next_review_at\s*=/, 'the library writes no review date');
assert.match(
  repository,
  /\.order_by\(LibraryItem\.pinned_at\)/,
  'the queue is what was marked, oldest mark first',
);
assert.match(repository, /SavedWord\.next_review_at <= moment/, 'then what the words owner says is due');

/* --- One collection, one kind ------------------------------------------ */
assert.match(repository, /if item\.kind != collection\.kind:/, 'the repository refuses a set of another kind');

/* --- Marking says so when it cannot be stored -------------------------- */
assert.match(routes, /library_unavailable/, 'a runtime without the tables says so');

console.log('Thư viện của tôi: versioned writes, one scheduler, one kind per set: PASS');
