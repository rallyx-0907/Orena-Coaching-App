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
import { librarySection, libraryCoverUrl, readingFromMemory, wordsFromBook } from '../static/orena/ui/library.js';
import { referenceCopy } from '../static/orena/ui/reference.js';

const c = copy.en;
const r = referenceCopy.en;

/* The library that leads here is the approved browse surface
   (static/orena/ui/library-browse.js); this module owns one book. Its own
   states still have to hold: loading, failure and a cover URL. */
assert.match(librarySection(c, { open: { id: 'book-1', book: null, error: false } }), /skeleton/);
assert.match(librarySection(c, { open: { id: 'book-1', book: null, error: true } }), /role="alert"/);
assert.match(
  libraryCoverUrl('book-2'),
  /^\/api\/reading\/library\/books\/book-2\/cover$/,
  'a book with an edition cover is read from its own endpoint',
);

/* Continue reading is built from device memory, never a second progress
   store, and only a book chapter counts. */
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

// --- The book page: loading, error and the happy path, each with a back
//     affordance so it never strands the learner in the detail view ---
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
const hostile = librarySection(c, {
  open: { id: 'book-1', book: { ...book, title: 'A <b>Bold</b> Title' }, error: false },
});
assert.doesNotMatch(hostile, /<b>Bold<\/b>/, 'a hostile title must never render as raw markup');
assert.match(hostile, /&lt;b&gt;Bold&lt;\/b&gt;/, 'the same title must still appear, escaped');
/* The approved book detail (D-059 Phase 5, part 4 section 16): overview first -
   the cover, what the book is, how far in the learner is and the one action
   they came for - then the chapters, then the side column. */
assert.match(detail, /class="book-page"/);
assert.match(detail, /class="book-hero"/);
assert.match(detail, /class="library-cover library-cover--large"/, 'the cover leads the detail');
assert.match(detail, /<a class="primary"/, 'a book offers one way in');
assert.match(detail, new RegExp(c.libraryStartReading), 'an unread book says start');
assert.match(detail, /2 chapters/, 'essential facts are stated once, quietly');
assert.match(detail, /class="book-chapter-list"/, 'the chapters follow as a list');
assert.match(detail, new RegExp(r.bookAbout), 'the side column carries the description');

/* A backend gap keeps its component and shows the honest unavailable state -
   it is never removed from the approved composition and never invented (D-060,
   docs/project/UI_BACKEND_GAPS.md). */
assert.match(detail, /class="progress-bar" data-unavailable/, 'an unread book shows the unmeasured track');
assert.match(detail, new RegExp(r.bookNotStarted));
assert.match(detail, new RegExp(r.bookStatTime), 'time read keeps its tile');
assert.match(detail, new RegExp(r.bookStatQuiz), 'quiz average keeps its tile');
assert.match(detail, new RegExp(r.bookSimilarGap), 'similar level states why it is empty');
assert.equal((detail.match(/<strong>—<\/strong>/g) || []).length, 4,
  'every unmeasured figure reads as a dash, never as a number nobody measured');
assert.doesNotMatch(detail, /HSK|CEFR|B1/, 'a level nobody stored is never printed (GAP-004)');

const resumed = librarySection(c, {
  open: { id: 'book-1', book, error: false, words: ['one', 'two'] },
  reading: { 'book-1': { chapterId: 'chap-2', index: 2, total: 2 } },
});
assert.match(resumed, new RegExp(r.bookContinueChapter.replace('{n}', '2')),
  'a started book offers the chapter the learner is in');
assert.match(resumed, /aria-current="true"/, 'the chapter the learner is in is marked current');
assert.match(resumed, /data-current/, 'and is distinguishable in the contents');
assert.match(resumed, /class="progress-bar"><span style="width:100%"/, 'a started book shows how far through it is');
assert.match(resumed, /data-done/, 'the chapters behind the current one read as read');
assert.match(resumed, /<strong>2<\/strong>/, 'words saved is a real count of what this book taught');

/* Unread only and "show all" are view state - what the learner asked to see,
   never a second copy of what they have read. */
const filtered = librarySection(c, {
  open: { id: 'book-1', book, error: false },
  reading: { 'book-1': { chapterId: 'chap-2', index: 2, total: 2 } },
  view: { unreadOnly: true },
});
assert.doesNotMatch(filtered, /Chapter One/, 'unread only hides what is behind the learner');
assert.match(filtered, /Chapter Two/);

/* The words this book taught come from the learner's own saved vocabulary,
   matched on where each word was kept - never a second store. */
assert.deepEqual(
  wordsFromBook(
    [
      { word: '图书馆', focus_note: 'Chapter One' },
      { word: '图书馆', focus_note: 'Chapter Two' },
      { word: 'elsewhere', focus_note: 'Another Book' },
      { word: '', focus_note: 'Chapter One' },
    ],
    book,
  ),
  ['图书馆'],
);

// Each chapter link must carry the exact `book:<id>/<chapterId>` locator
// static/orena/ui/encounter.js's `book:` branch parses.
assert.match(detail, /id=book%3Abook-1%2Fchap-1/, 'chapter one locator');
assert.match(detail, /id=book%3Abook-1%2Fchap-2/, 'chapter two locator');
assert.match(detail, /intent=reading/);

console.log('test_orena_shared_reading_library.mjs: all assertions passed');
