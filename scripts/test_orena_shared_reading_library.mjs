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
//     affordance so it never strands the learner in the detail view.
//     The way back is a LINK to the reading library, not a history step: the
//     reader navigates forward to this page, so a history step landed back in
//     the reader and the two bounced off each other with no way out (fixed
//     2026-09-22). Pinning the destination is what keeps that from returning. ---
const bookLoading = librarySection(c, { open: { id: 'book-1', book: null, error: false } });
assert.match(bookLoading, /class="icon-button book-back"/);
assert.match(bookLoading, /href="#\/practice\?intent=reading"/);
assert.doesNotMatch(bookLoading, /data-close-book/);
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

/* A measurement the app does not have still says so rather than inventing a
   number: an unread book draws the unmeasured track (D-066 rule 4). */
assert.match(detail, /class="progress-bar" data-unavailable/, 'an unread book shows the unmeasured track');
assert.match(detail, new RegExp(r.bookNotStarted));

/* What changed on 2026-09-23, and why this file no longer pins four dashes.
   D-060 kept a component for every backend gap, showing an honest blank. The
   canonical Book detail frames (03 and 04) draw no statistic tiles and no
   "similar level" shelf at all, and D-067 makes the design the authority for
   what a surface draws - a rule written before 2026-09-21 is void where it
   disagrees with it. So the tiles and the shelf were deleted rather than left
   apologising for themselves, and this asserts they stay deleted. */
assert.ok(!detail.includes('book-stat'), 'no statistic tile the frames do not draw');
assert.doesNotMatch(detail, /<strong>—<\/strong>/, 'and no tile left showing a dash');
/* The one thing in that column the frames do draw stays. */
assert.match(detail, new RegExp(r.bookWordsFrom), 'the words the learner saved from this book');
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
/* The words this book taught are drawn as the words themselves, which is what
   frame 03 draws ("BẠN ĐÃ LƯU TỪ ĐÂY" and the words), rather than as a tally
   in a tile the frames do not draw. */
assert.match(resumed, /class="book-words"/, 'the words this book taught are listed');

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
