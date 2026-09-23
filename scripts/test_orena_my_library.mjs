/* Thư viện của tôi: a relationship store, not a second library.

   The room lists what the learner kept over the owners that already hold it,
   and writes only the learner's own relationship to those things - kept,
   marked, filed. These assertions exist to stop the three ways that quietly
   stops being true: a second copy of somebody else's data, a second review
   scheduler, and a number nobody measured.

   Schema and decision: `migrations/versions/20260923_0013_my_library_and_
   entry_identity.py`, D-074, reviewed by independent architecture review. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const room = read('static/orena/ui/collection.js');
const api = read('static/orena/infrastructure/api.js');
const routes = read('writing_coach/library_api.py');
const repository = read('writing_coach/persistence/library_repository.py');

/* --- One read for the page, not one per row ---------------------------- */
assert.match(room, /api\.collection\(\{/, 'the rows come from the typed query over the owners');
assert.match(room, /api\.libraryItems\(\{ kind: 'word', words \}\)/, "and the learner's own state comes in one lookup");
assert.doesNotMatch(
  room,
  /for \([^)]*\) \{[^}]*await api\.libraryItem\(/s,
  'never one request per row',
);
assert.match(api, /libraryItems:\(\{kind='',words=\[\],sources=\[\]\}/, 'the lookup takes the whole page at once');

/* --- The room holds no copy of what an owner owns ---------------------- */
for (const forbidden of ['localStorage', 'indexedDB', 'sessionStorage'])
  assert.doesNotMatch(room, new RegExp(forbidden), `the room keeps no ${forbidden} store of its own`);
assert.doesNotMatch(room, /state\.entries\s*=\s*\[\.\.\.state\.entries\]\s*\.map\([^)]*title:/s, 'and rewrites no owner row');

/* --- Every write carries the version it read --------------------------- */
assert.match(room, /expected_version: item\.version/, 'a change is made against the version it read');
assert.match(routes, /expected_version: int = Field\(ge=1\)/, 'and the route requires one');
assert.match(
  repository,
  /if int\(item\.version\) != int\(expected_version\):\s*\n\s*raise LibraryConflict\("version_conflict"\)/,
  'which the repository checks rather than trusting',
);

/* --- No second scheduler ------------------------------------------------ */
/* Words are scheduled in `saved_words`. The library orders the queue by the
   pin and by that schedule; it never computes an interval of its own. */
assert.doesNotMatch(repository, /next_review_at\s*=/, 'the library writes no review date');
assert.doesNotMatch(room, /next_review_at\s*=|REVIEW_STAGE|interval/i, 'and the room invents none');
assert.match(
  repository,
  /\.order_by\(LibraryItem\.pinned_at\)/,
  'the queue is what was marked, oldest mark first',
);
assert.match(repository, /SavedWord\.next_review_at <= moment/, 'then what the words owner says is due');

/* --- One collection, one kind ------------------------------------------ */
assert.match(room, /state\.collections\.filter\(\(set\) => set\.kind === wanted\)/,
  'the picker offers only sets of the item\'s own kind');
assert.match(repository, /if item\.kind != collection\.kind:/, 'and the repository refuses the rest');

/* --- Nothing a learner sees is invented -------------------------------- */
/* The history is the owner's record. Only saved language has one, so only a
   word shows it - three dashes on a passage would be three measures nobody
   took (Design Contract rule 4). */
assert.match(room, /const isWord = entry\.ref\.domain === 'language';/, 'the history belongs to a word');
assert.match(room, /isWord\s*\n?\s*\?\s*`<div class="my-library-detail__history">/, 'and is drawn only for one');

/* --- No browser dialog -------------------------------------------------- */
/* A prompt or a confirm stops the page and is not something the design
   draws; naming a set happens in a field in the room. */
for (const dialog of ['window.prompt', 'window.confirm', 'window.alert'])
  assert.doesNotMatch(room, new RegExp(dialog.replace('.', '\\.')), `no ${dialog}`);
assert.match(room, /data-library-name-form/, 'a set is named in the room');

/* --- The two kinds without an owner are absent, not faked -------------- */
const kinds = room.slice(room.indexOf('const KINDS = ['), room.indexOf('const ITEM_KIND'));
for (const absent of ['note', 'book'])
  assert.doesNotMatch(kinds, new RegExp(`id: '${absent}'`), `${absent} has no owner, so it is not a chip`);
assert.equal((kinds.match(/\{ id: /g) || []).length, 6, 'six kinds have owners today');

/* --- Marking says so when it cannot be stored -------------------------- */
assert.match(routes, /library_unavailable/, 'a runtime without the tables says so');
assert.match(room, /state\.unavailable = true/, 'and the room stops offering to mark');
assert.match(room, /myLibraryUnavailable/, 'in words the learner can read');

console.log('Thư viện của tôi: one read per page, versioned writes, one scheduler, nothing invented: PASS');
