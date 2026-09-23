/* The Reading library (canonical frames 01-02), and one promise about it.
 *
 * "Nhập văn bản" must bring the learner's own text in. It used to open the
 * passage generator - a button labelled "import text" that asked which topic
 * and level to *invent* something about. A control whose label and behaviour
 * disagree is worse than a missing one, because the learner cannot tell.
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const at = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const world = at('static/orena/ui/world.js');
const browse = at('static/orena/ui/library-browse.js');
const app = at('static/orena/app.js');
const reference = at('static/orena/ui/reference.js');

/* --- The button does what it says --------------------------------------- */

assert.match(world, /onImport: ctx\.import,/, "the library's import is the learner's own import");
assert.doesNotMatch(
  world,
  /onImport: intent === 'reading' \? \(\) => openReadingRequest/,
  'never the passage generator behind an "import text" label',
);
/* `ctx.import` is the one that takes a title and a body. */
assert.match(app, /import: \(\) => importContent\(\),/, 'and that import is the text sheet');
assert.match(app, /ctx\.memory\.add\(\{\s*title: data\.get\("title"\),\s*text: data\.get\("text"\),/s,
  'which keeps the learner’s own text');

/* Asking for a generated passage is a real thing and keeps its own door, so
   this fix removed no capability. */
assert.match(world, /\[data-read\]/, 'the generator still has a way in');
assert.match(world, /openReadingRequest\(ctx\)/, 'and is still wired to it');

/* --- The header the frame draws ----------------------------------------- */

assert.match(browse, /class="lib-search"/, 'a search');
assert.match(browse, /class="lib-import"/, 'and one import control');
for (const language of ['Import text', 'Nhập văn bản', '导入文本'])
  assert.ok(reference.includes(language), `the label is written in each interface language (${language})`);

/* --- What a card carries ------------------------------------------------- */

/* The frame draws a title, the author under it, and a mono meta line; a book
   the learner is part-way through carries a bar on its cover. All four come
   from data the card already has - none of it is invented here. */
assert.match(browse, /class="lib-title"/, 'the title');
assert.match(browse, /entry\.sub \? `<span class="lib-sub">/, 'the author, when there is one');
assert.match(browse, /class="lib-meta"/, 'the mono meta line');
assert.match(browse, /entry\.percent != null \? ' data-progress' : ''/, 'and progress only when it is known');
assert.match(browse, /sub: book\.author \|\| '',/, "a book's author comes from the library read");


/* --- Book detail (frames 03-04) ----------------------------------------- */

const library = at('static/orena/ui/library.js');
const css = at('static/orena/rooms.css');
const readingApi = at('writing_coach/reading_library_api.py');

/* The duration is derived in the learner's answer, from a count that was
   already stored, at the pace the product already chose. It is not a column
   and it is not a second convention. */
assert.match(readingApi, /def reading_seconds\(word_count: object, learning_language: str\) -> int:/,
  'the learner answer derives a duration');
assert.match(readingApi, /reading_processing\.(EN_WORDS_PER_MINUTE|ZH_CHARS_PER_MINUTE)/,
  "at the product's own pace, read rather than redefined");
assert.doesNotMatch(readingApi, /reading_time_seconds.*=.*\b(180|260)\b/, 'the pace is never inlined here');
assert.match(readingApi, /response = _with_reading_time\(book\)/, 'and the learner read carries it');

/* The admin import path is untouched by the projection. */
const projection = readingApi.slice(
  readingApi.indexOf('def reading_seconds'),
  readingApi.indexOf('@router.get("/books")'),
);
for (const owned of ['asset_store', 'create_book', 'UploadFile', '_admin_guard'])
  assert.ok(!projection.includes(owned), `the projection must not reach into ${owned}`);

/* What the frames draw, and only that. */
assert.match(library, /class="book-hero__meta ds-data"/, 'one meta line');
assert.match(library, /class="book-section-count ds-data"/, 'how many chapters are read');
assert.match(library, /r\.bookChapterMinutes/, 'a duration on every chapter row');
assert.match(library, /const seconds = Number\(chapter\.reading_time_seconds \|\| 0\);/,
  'taken from the server, not computed twice in the browser');
assert.match(library, /const words = !seconds/, 'a row with no count says nothing');
/* What is left of the chapter in progress is pinned by test_orena_reader_place.mjs. */

/* Deleted, because the source draws neither (rule 44). */
assert.ok(!library.includes('bookStat('), 'the statistic tiles are gone');
for (const retired of ['bookStatWordsSaved', 'bookStatTime', 'bookStatQuiz', 'bookStatAudio', 'bookNotMeasured', 'bookAudioGap', 'bookSimilar', 'bookSimilarGap'])
  assert.ok(!at('static/orena/ui/reference.js').includes(`${retired}:`), `${retired} went with them`);
/* Kept, because frame 03 does draw it. */
assert.match(library, /r\.bookWordsFrom/, 'the words the learner saved from this book stay');

for (const [what, rule] of [
  ['the cover', /\.book-hero__cover \{\n  inline-size: 106px;\n  block-size: 144px;/],
  ['the title', /\.book-hero__title \{[^}]*font-size: 21px;\n  line-height: 1\.2;/s],
  ['the byline', /\.book-hero__byline \{ margin: 0; font-size: 14\.5px;/],
  ['a chapter row', /\.book-chapter \{[^}]*padding: 13px 15px;\n  border-radius: 14px;/s],
  ['its number', /\.book-chapter__n \{ flex: none; inline-size: 20px; font-size: 13px;/],
  ['the desktop lift', /@media \(min-width: 1000px\) \{\n  \.book-hero__title \{ font-size: 38px;/],
])
  assert.match(css, rule, `${what} is the frame\u2019s size`);

console.log('test_orena_reading_library.mjs: book detail is its frames, and the duration is derived');
