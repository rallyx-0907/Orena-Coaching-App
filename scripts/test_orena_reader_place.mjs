/* The reader workspace as its frames draw it (canonical frames 05-06), and the
 * one fact it now keeps: how far into the chapter the learner has read.
 *
 * The rail always measured it and threw it away, so Book detail could say
 * which chapter the learner was in and never how far into it. That number is
 * what the frames write - "34% · còn 9 phút" at the foot of the wide frame,
 * "còn 9 phút" in both bars - and what frame 04 draws on the chapter in
 * progress.
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const at = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const reader = at('static/orena/ui/reader.js');
const encounter = at('static/orena/ui/encounter.js');
const memory = at('static/orena/product/memory.js');
const library = at('static/orena/ui/library.js');
const room = at('static/orena/ui/reading-room.js');
const css = at('static/orena/reader.css');
const reference = at('static/orena/ui/reference.js');

/* --- The measurement is kept, forward, and whole ------------------------- */

assert.match(memory, /const within = Number\(place\?\.within\);/, 'a place may say how far into itself');
assert.match(memory, /Math\.max\(0, Math\.min\(100, Math\.round\(within\)\)\)/, 'clamped and whole, like everything else kept there');
assert.match(memory, /if \(!Number\.isFinite\(within\)\) return \{ index, total \};/,
  'and absent stays absent - not measured is not nought');

assert.match(reader, /onPlace = null/, 'the reader can hand the measurement out');
assert.match(reader, /if \(onPlace && percent > furthest\) \{/, 'only forward: rereading a paragraph is not un-reading the chapter');
assert.match(encounter, /onPlace: chapterIndex >= 0 \? \(within\) => remember\(within\) : null,/,
  'and a chapter of a book is what keeps it');
assert.match(encounter, /const placeOf = \(within\) =>/, 'the place carries it');

/* --- What the frames write ---------------------------------------------- */

/* "chương 3 · còn 9 phút" in the bar; "34% · còn 9 phút" at the foot. */
assert.match(reader, /const readerSeconds = Number\(item\?\.reading_time_seconds \|\| 0\);/,
  'the duration comes from the server answer, not a second count in the browser');
assert.match(reader, /r\.readerMinutesLeft/, 'the bar says what is left');
assert.match(reader, /percentLabel\.textContent = \[progressLabel\(c, percent\), leftLabel\]/,
  'the foot says how far in and what is left');
for (const language of ['{n} min left', 'còn {n} phút', '还剩 {n} 分钟'])
  assert.ok(reference.includes(language), `written in each interface language (${language})`);

/* The bar names the chapter alone, as the frame writes it. */
assert.match(room, /export const chapterLabel = \(c, index\) =>/, 'the chapter, not the chapter and the count');
assert.match(room, /String\(c\.readerChapter \|\| ''\)\.replace\('\{n\}', String\(index \+ 1\)\)/, 'as "chương 3"');
assert.ok(!at('static/orena/ui/copy.js').includes('readerChapterOf'), 'the long form went with it');

/* The hairline is the frame's 3px. */
assert.match(css, /\.reader-rail \{[^}]*block-size: 3px;/s, 'the rail is 3px');

/* --- The phone bar is the phone frame's ---------------------------------- */

/* Five tiles, icon over a 10px label, the way on to the next chapter last and
   in the accent; the two the narrow frame leaves out are not drawn there. */
assert.match(reader, /reader-action--phone/, 'the phone carries the next chapter in the bar');
assert.match(reader, /supplied\.get\('discuss'\) && \{ \.\.\.supplied\.get\('discuss'\), wide: true \}/,
  'discussion belongs to the wide frame');
assert.match(reader, /\{ name: 'later'.*wide: true \}/, 'and so does reading it later');
assert.match(css, /@media \(max-width: 900px\) \{[^@]*\.reader-action \{\n    flex: 1;\n    flex-direction: column;/s,
  'the tiles are a row of equal columns');
assert.match(css, /\.reader-action--wide \{\n    display: none;\n  \}/, 'the other two are not drawn there');
assert.match(css, /block-size: 48px;\n    padding: 0 4px;\n    border-radius: 14px;\n    font-size: 10px;/,
  'at the size the frame draws them');
for (const short of ['readerSaveShort', 'readerCheckShort', 'readerRespondShort'])
  assert.match(reference, new RegExp(`${short}:`), `${short} is the shorter label the phone frame writes`);

/* Deleted, because neither frame draws one (rule 44). */
assert.ok(!reader.includes('reader-dock'), 'the phone chapter dock is gone, not restyled');
assert.ok(!reader.includes('stepLink'), 'and its steps with it');

/* --- Book detail spends the measurement ---------------------------------- */

assert.match(library, /within: Number\.isFinite\(Number\(item\?\.place\?\.within\)\) \? Number\(item\.place\.within\) : null,/,
  'the book reads it back');
assert.match(library, /const remaining = within != null \? Math\.round\(\(seconds \* \(100 - within\)\) \/ 100\) : 0;/,
  'the chapter in progress says what is left of it');
assert.match(library, /fill\(r\.bookTimeLeft, \{ n: minutes\(remaining\) \}\)/, 'in the frame’s words');
assert.match(library, /if \(chapter\.id === currentId && Number\.isFinite\(progress\?\.within\)\)/,
  'and the book’s remainder counts only the part still unread');

console.log('test_orena_reader_place.mjs: the reader keeps its place, and both frames say what is left');
