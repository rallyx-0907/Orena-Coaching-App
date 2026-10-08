/* The Reading library's server projection, and the one promise it keeps.
 *
 * The pre-cutover library, book-detail markup and its CSS went with the
 * retired UI (D-143); the learner UI reads the same endpoints through
 * screens/library, screens/content, screens/discover and screens/reader (gated
 * by test_orena_screen_library.mjs, test_orena_screen_content.mjs,
 * test_orena_screen_discover.mjs and test_orena_screen_reader.mjs). The learner
 * UI still takes a book's and chapter's `reading_time_seconds` from the
 * server, so the derivation below remains a live contract.
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const at = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
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

/* The learner UI takes the duration from the server, never computing it twice
   in the browser. */
assert.match(at('static/orena/screens/reader/source.js'), /article\?\.reading_time_seconds/,
  'the reader takes the duration from the server read');
assert.match(at('static/orena/screens/content/model.js'), /reading_time_seconds/,
  'and so does the content screen');

console.log('test_orena_reading_library.mjs: the reading duration is derived server-side and read by the learner UI');
