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
import { librarySection, libraryCoverUrl } from '../static/orena/ui/library.js';

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
// Each chapter link must carry the exact `book:<id>/<chapterId>` locator
// static/orena/ui/encounter.js's `book:` branch parses.
assert.match(detail, /id=book%3Abook-1%2Fchap-1/, 'chapter one locator');
assert.match(detail, /id=book%3Abook-1%2Fchap-2/, 'chapter two locator');
assert.match(detail, /intent=reading/);

console.log('test_orena_shared_reading_library.mjs: all assertions passed');
