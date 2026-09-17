/* Shared Reading Library grid/detail: pure rendering contract for
   static/orena/ui/library.js. Covers loading/error/empty/grid states, the
   inline book-detail state (mirroring vocabularyLibrarySection's own `open`
   pattern), the encounter locator a chapter link must produce, and that a
   hostile title/author never reaches the page as raw markup - paragraphs and
   metadata always go through esc(), the same gate every other reading source
   in this app renders through. Distinct from test_orena_reading_library.mjs,
   which covers the older, separate hand-curated catalog in
   static/orena/content/reading-library.js. */
import assert from 'node:assert/strict';
import { copy } from '../static/orena/ui/copy.js';
import { librarySection, libraryCoverUrl, readingFromMemory } from '../static/orena/ui/library.js';

const c = copy.en;

// --- Loading / error / empty states never render a grid or a detail view ---
assert.match(librarySection(c, {}), /loading/);
assert.match(librarySection(c, { error: true }), /notice/);
assert.match(librarySection(c, { error: true }), /data-library-grid-retry/);
assert.match(librarySection(c, { items: [] }), /empty/);
assert.doesNotMatch(librarySection(c, { items: [] }), /library-grid"/);

// --- Grid renders one card per book, cover-first, title escaped ---
const items = [
  { id: 'book-1', title: 'A <b>Bold</b> Title', author: 'Author One', learning_language: 'en', cover_asset_key: null },
  { id: 'book-2', title: 'Second Book', author: '', learning_language: 'en', cover_asset_key: 'books/book-2/cover.jpg' },
];
const grid = librarySection(c, { items });
assert.match(grid, /class="library-grid"/);
assert.equal((grid.match(/data-open-book="/g) || []).length, 2);
assert.doesNotMatch(grid, /<b>Bold<\/b>/, 'a hostile title must never render as raw markup');
assert.match(grid, /&lt;b&gt;Bold&lt;\/b&gt;/, 'the same title must still appear, escaped');
assert.match(grid, new RegExp(libraryCoverUrl('book-2').replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
/* D-057: a book with no edition cover wears a designed one drawn from its own
   identity, never a single letter on a tinted square. */
assert.match(grid, /class="content-cover" data-cover-motif="/,
  'a book without an edition cover gets a designed cover');
assert.doesNotMatch(grid, /library-cover-fallback/, 'the single-letter placeholder is retired');
assert.equal(librarySection(c, { items }), grid, 'the same shelf always draws the same covers');

/* Continue reading is a real shelf built from device memory, and it appears
   only when there is real progress to show. */
const reading = readingFromMemory({
  value: {
    continuation: [
      { id: 'book:book-1/chap-2', title: 'Chapter Two', place: { index: 2, total: 4 } },
      { id: 'story:unrelated', title: 'Not a book' },
    ],
  },
});
assert.deepEqual(Object.keys(reading), ['book-1'], 'only book chapters become reading progress');
assert.equal(reading['book-1'].index, 2);
const started = librarySection(c, { items, reading });
assert.match(started, /data-content-rail="library-continue"/, 'a started book gets a Continue reading shelf');
assert.match(started, /class="library-progress"/, 'progress reads on the card');
assert.match(started, /width:50%/, 'progress is computed from the real place');
assert.doesNotMatch(grid, /data-content-rail="library-continue"/,
  'with nothing started, no Continue shelf is invented');
assert.doesNotMatch(grid, /class="library-progress"/, 'no progress bar without progress');

/* A small library is one wall of covers; shelves appear only once the library
   is bigger than a shelf, so a shelf is never the whole library restated. */
const many = Array.from({ length: 10 }, (_, index) => ({
  id: `many-${index}`, title: `Book ${index}`, author: 'Author', learning_language: 'en',
  cover_asset_key: null, word_count: index < 4 ? 400 : 40000, chapter_count: 3,
}));
assert.match(librarySection(c, { items: many }), /data-content-rail="library-short"/,
  'a large library earns a short-reads shelf from real word counts');
assert.doesNotMatch(librarySection(c, { items: many.slice(0, 4) }), /data-content-rail="library-short"/,
  'a small library is not split into shelves that repeat it');


// --- Load-more only appears with a next_cursor ---
assert.doesNotMatch(librarySection(c, { items }), /data-library-more/);
assert.match(librarySection(c, { items, nextCursor: 'abc' }), /data-library-more/);
assert.match(
  librarySection(c, { items, nextCursor: 'abc', loadingMore: true }),
  /data-library-more[^>]*disabled/,
);

// --- Inline book detail: loading, error and the happy path, each with a
//     back affordance so it never strands the learner in the detail view ---
assert.match(librarySection(c, { open: { id: 'book-1', book: null, error: false } }), /data-close-book/);
assert.match(librarySection(c, { open: { id: 'book-1', book: null, error: true } }), /data-book-retry/);

const book = {
  id: 'book-1',
  title: 'Detail Title',
  author: 'Detail Author',
  description: 'A description.',
  learning_language: 'en',
  cover_asset_key: null,
  chapters: [
    { id: 'chap-1', title: 'Chapter One' },
    { id: 'chap-2', title: 'Chapter Two' },
  ],
};
const detail = librarySection(c, { open: { id: 'book-1', book, error: false } });
assert.match(detail, /Detail Title/);
assert.match(detail, /Detail Author/);
/* A book, not a folder of chapters: the cover leads, and the one action the
   learner came for is a primary action beside it rather than an entry
   somewhere in a numbered list. */
assert.match(detail, /class="library-detail"/);
assert.match(detail, /class="library-cover library-cover--large"/, 'the cover leads the detail');
assert.match(detail, /<a class="primary"/, 'a book offers one way in');
assert.match(detail, new RegExp(c.libraryStartReading), 'an unread book says start');
assert.match(detail, /2 chapters/, 'essential facts are stated once, quietly');
assert.doesNotMatch(detail, /class="library-progress"/, 'an unread book shows no progress');

const resumed = librarySection(c, {
  open: { id: 'book-1', book, error: false },
  reading: { 'book-1': { chapterId: 'chap-2', index: 2, total: 2 } },
});
assert.match(resumed, new RegExp(c.resume), 'a started book offers the way back in');
assert.match(resumed, /aria-current="true"/, 'the chapter the learner is in is marked current');
assert.match(resumed, /data-current/, 'and is distinguishable in the contents');
assert.match(resumed, /class="library-progress"/, 'a started book shows how far through it is');

// Each chapter link must carry the exact `book:<id>/<chapterId>` locator
// static/orena/ui/encounter.js's `book:` branch parses.
assert.match(detail, /id=book%3Abook-1%2Fchap-1/, 'chapter one locator');
assert.match(detail, /id=book%3Abook-1%2Fchap-2/, 'chapter two locator');
assert.match(detail, /intent=reading/);

console.log('test_orena_shared_reading_library.mjs: all assertions passed');
