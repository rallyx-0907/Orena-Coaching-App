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

console.log('test_orena_reading_library.mjs: the import button brings the learner’s own text in');
