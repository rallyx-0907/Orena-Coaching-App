/* The Library (D-066): the Canonical UI Baseline's library surface, the one Reading
   and Listening share (static/orena/ui/library-browse.js).

   The contract held here: one row of single-choice type chips offered only for
   types some item really has; a card shows a progress bar and "time left" only from
   a place the learner really reached (device memory); a curated item that carries no
   type is shown with none rather than a guessed one; a hostile title never reaches
   the page as markup; the labels exist in every interface language for every type
   the catalogue can name (writing_coach/listening_catalog.py CONTENT_TYPES). */
import assert from 'node:assert/strict';
import { copy } from '../static/orena/ui/copy.js';
import { referenceCopy } from '../static/orena/ui/reference.js';
import { renderLibraryBrowse } from '../static/orena/ui/library-browse.js';

/* A DOM just large enough for the parts the library touches. */
function makeEl() {
  const els = {};
  return {
    innerHTML: '',
    value: '',
    hidden: false,
    querySelector(selector) {
      return (els[selector] ??= makeEl());
    },
    querySelectorAll() {
      return [];
    },
    addEventListener() {},
  };
}
const root = () => makeEl();
const at = (host, selector) => host.querySelector(selector);
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

const c = copy.vi;
const r = referenceCopy.vi;
const ctxOf = (memory, api = {}) => ({
  api: { libraryBooks: async () => ({ items: [] }), vocabularyLibraryCollections: async () => ({ items: [] }), ...api },
  c,
  ui: 'vi',
  language: 'en',
  alive: () => true,
  memory: { value: { continuation: memory } },
});

/* The catalogue's types, as tests/test_listening_catalog.py fixes them. */
const CATALOGUE_TYPES = ['video', 'interview', 'podcast', 'speech', 'culture', 'dialogue', 'story', 'situation'];
for (const locale of ['en', 'zh', 'vi']) {
  for (const type of [...CATALOGUE_TYPES, 'imported', 'generated', 'book']) {
    assert.ok(referenceCopy[locale][`libraryKind_${type}`], `${locale} names the type "${type}"`);
  }
  for (const key of ['libraryAll', 'libraryImportListening', 'libraryImportReading', 'libraryLeft', 'libraryMinutes']) {
    assert.ok(referenceCopy[locale][key], `${locale} has ${key}`);
  }
}

/* Listening. */
const media = [
  { id: 'media:dialogue', title: 'Ordering food', level: 'A2', duration_ms: 120000, kind: 'audio', origin: 'curated', content_type: 'dialogue', language: 'en' },
  { id: 'media:clip', title: 'The cosmic calendar', level: 'B2', duration_ms: 46000, kind: 'video', origin: 'curated', content_type: 'video', language: 'en' },
  { id: 'media:plain', title: 'Untyped lesson', level: 'B1', duration_ms: 60000, kind: 'audio', origin: 'curated', language: 'en' },
  { id: 'media:mine', title: '<img src=x onerror=alert(1)>', duration_ms: 30000, kind: 'audio', origin: 'imported', language: 'en' },
];
const host = root();
renderLibraryBrowse(host, ctxOf([{ id: 'media:dialogue', place: { index: 5, total: 10 } }]), { readable: [], media }, {
  only: ['audio', 'video'],
  onImport: () => {},
});
const shell = host.innerHTML;
assert.match(shell, new RegExp(`<h1>${r.listening}</h1>`), "the bar names the room in the learner's interface language");
assert.match(shell, new RegExp(r.libraryImportListening), 'the bar offers the import');
assert.match(shell, /role="radiogroup"/, 'the type chips are a single-choice group');

const chips = at(host, '[data-lib-chips]').innerHTML;
const labels = [...chips.matchAll(/data-lib-type="[^"]*">([^<]+)</g)].map((m) => m[1]);
assert.deepEqual(labels, [r.libraryAll, r.libraryKind_dialogue, r.libraryKind_video, r.libraryKind_imported], 'only real types, in the fixed order');
assert.match(chips, /aria-checked="true" data-lib-type="">/, 'All is chosen first');

const grid = at(host, '[data-lib-results]').innerHTML;
assert.match(grid, /aria-valuenow="50"/, 'the bar is the place the learner reached');
assert.match(grid, /còn 1 phút/, 'time left comes from the place and the length');
assert.equal((grid.match(/class="lib-bar"/g) || []).length, 1, 'no place, no bar');
assert.match(grid, />00:46</, 'the length is on the cover, minutes padded as the design draws it');
assert.match(grid, /lib-badge--icon/, 'a video is marked as one');
assert.doesNotMatch(grid, /<img src=x/, 'a hostile title is escaped');
assert.match(grid, /&lt;img src=x/);
const plain = grid.split('<a class="lib-card"').find((card) => card.includes('Untyped lesson'));
assert.doesNotMatch(plain, /Hội thoại|Video ngắn/, 'an item with no type is given none');
assert.match(plain, /B1/, 'and keeps what it does carry');

/* The search narrows the grid. */
at(host, '[data-lib-query]').value = 'cosmic';
at(host, '[data-lib-query]').oninput();
const narrowed = at(host, '[data-lib-results]').innerHTML;
assert.match(narrowed, /The cosmic calendar/);
assert.doesNotMatch(narrowed, /Ordering food/);
at(host, '[data-lib-query]').value = 'zzzz';
at(host, '[data-lib-query]').oninput();
assert.doesNotMatch(at(host, '[data-lib-results]').innerHTML, /state-panel|lib-card/, 'nothing found is an empty grid: the design draws no empty state');

/* Reading: provenance is a badge, said once; time is localised; books load and fail visibly. */
const reading = root();
renderLibraryBrowse(
  reading,
  ctxOf([{ id: 'book:b1/ch2', place: { index: 2, total: 4 } }], { libraryBooks: async () => ({ items: [{ id: 'b1', title: 'A Book', author: 'An Author', chapter_count: 4 }] }) }),
  { readable: [{ id: 'generated:1', title: 'Made', origin: 'generated', level: 'B1', time: '3 min' }], media: [] },
  { only: ['books'], onImport: () => {} },
);
assert.doesNotMatch(at(reading, '[data-lib-results]').innerHTML, /skeleton|placeholder/, 'loading is not drawn in the design, so no placeholder is drawn for it');
await tick();
const shelf = at(reading, '[data-lib-results]').innerHTML;
assert.match(shelf, /A Book/);
assert.match(shelf, /aria-valuenow="50"/, 'a book shows the chapter place from device memory');
assert.match(shelf, /3 phút/, 'the authored "3 min" is shown in the interface language');
assert.equal((shelf.match(/Tạo riêng/g) || []).length, 1, 'provenance is said once');
assert.match(shelf, /An Author/);
assert.match(reading.innerHTML, new RegExp(`<h1>${r.reading}</h1>`));

const failing = root();
renderLibraryBrowse(failing, ctxOf([], { libraryBooks: async () => { throw new Error('down'); } }), { readable: [], media: [] }, { only: ['books'] });
await tick();
assert.match(at(failing, '[data-lib-results]').innerHTML, /role="alert"/, 'a failed read is an error with a retry, not an empty shelf');
assert.match(at(failing, '[data-lib-results]').innerHTML, /data-books-retry/);

console.log('library ok');
