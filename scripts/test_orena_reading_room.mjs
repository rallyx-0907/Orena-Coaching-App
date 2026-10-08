/* The reader: reading first, learning tools on demand.

   Pure contracts of the learner UI's Reader (D-143): the text blocks, chapter
   navigation, bounded settings and selection/context limits live in
   static/orena/product/reader-text.js and reader-settings.js, and the request
   shapes in infrastructure/api.js. The pre-cutover reader markup, Quick Sheet
   renderer and shared lexical layer went with the retired UI; their successors
   are screens/reader and screens/quick-sheet, gated by
   test_orena_screen_reader.mjs and test_orena_screen_quick-sheet.mjs. The
   browser behaviour itself is checked in the browser. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  EXPLAIN_LIMITS,
  LOOKUP_LIMITS,
  blocksFrom,
  chapterNeighbours,
  selectionKind,
  sentenceAround,
} from '../static/orena/product/reader-text.js';
import {
  READER_DEFAULTS,
  readerPresentation,
  readerSettings,
} from '../static/orena/product/reader-settings.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

/* --- Content: typed blocks, never flattened strings --------------------- */
{
  // Structured chapters keep their blocks; unknown or empty blocks drop.
  const blocks = blocksFrom({
    blocks: [
      { type: 'break' },
      { type: 'heading', level: 2, text: 'CHAPTER I.\nDown the Rabbit-Hole' },
      { type: 'paragraph', text: '  Alice was beginning to get very tired.  ' },
      { type: 'paragraph', text: '   ' },
      { type: 'script', text: 'nope' },
      { type: 'break' },
      { type: 'break' },
      { type: 'heading', level: 9, text: 'Deep' },
      { type: 'break' },
    ],
  });
  assert.deepEqual(blocks, [
    { type: 'heading', level: 2, text: 'CHAPTER I.\nDown the Rabbit-Hole' },
    { type: 'paragraph', text: 'Alice was beginning to get very tired.' },
    { type: 'break' },
    { type: 'heading', level: 6, text: 'Deep' },
  ]);
  // A source with only paragraphs reads as paragraphs.
  assert.deepEqual(blocksFrom({ paragraphs: ['One.', ' ', 'Two.'] }), [
    { type: 'paragraph', text: 'One.' },
    { type: 'paragraph', text: 'Two.' },
  ]);
}

/* --- Chapter identity and navigation ------------------------------------- */
{
  const chapters = [
    { id: 'a', title: 'CHAPTER I. Down the Rabbit-Hole', position: 0 },
    { id: 'b', title: 'CHAPTER II. The Pool of Tears', position: 1 },
    { id: 'c', title: 'CHAPTER III. A Caucus-Race', position: 2 },
  ];
  assert.deepEqual(chapterNeighbours(chapters, 'b'), {
    index: 1,
    total: 3,
    previous: chapters[0],
    next: chapters[2],
  });
  assert.equal(chapterNeighbours(chapters, 'a').previous, null);
  assert.equal(chapterNeighbours(chapters, 'c').next, null);
  assert.equal(chapterNeighbours(chapters, 'missing'), null);
}

/* --- Reader settings: real and bounded ------------------------------------ */
{
  assert.deepEqual(readerSettings(null), READER_DEFAULTS);
  // D-066: appearance is not a reader setting. There is one theme system, so a
  // stored 'appearance' from an older build is simply dropped.
  assert.deepEqual(
    readerSettings({ size: 99, font: 'comic', spacing: 'relaxed', width: 'wide', appearance: 'sepia' }),
    { ...READER_DEFAULTS, size: 1.4, spacing: 'relaxed', width: 'wide' },
  );
  assert.ok(!('appearance' in READER_DEFAULTS), 'the reader has no appearance of its own');
  assert.equal(readerSettings({ size: 0.1 }).size, 0.85);
  assert.equal(readerPresentation(READER_DEFAULTS).theme, undefined, 'the reader wears no theme of its own');
  const style = readerPresentation({ ...READER_DEFAULTS, size: 1.2, spacing: 'compact', width: 'narrow', font: 'sans' });
  assert.match(style.style, /--reader-scale: 1\.2/);
  assert.match(style.style, /--reader-leading: 1\.55/);
  assert.match(style.style, /--reader-measure: 36rem/);
  assert.match(readerPresentation(READER_DEFAULTS).style, /--reader-measure: 44rem/, 'the default column is about 700px');
  assert.equal(style.font, 'sans');
}

/* --- Selection decides what is offered ------------------------------------ */
{
  assert.equal(selectionKind('', 'en'), null);
  assert.equal(selectionKind('cloak', 'en'), 'word');
  assert.equal(selectionKind('rabbit-hole', 'en'), 'word');
  assert.equal(selectionKind('genial rays', 'en'), 'phrase');
  assert.equal(selectionKind('She took off one garment after another, and at last undressed.', 'en'), 'passage');
  assert.equal(selectionKind('学校', 'zh'), 'word');
  assert.equal(selectionKind('最后一班回家的车', 'zh'), 'phrase');
  assert.equal(selectionKind('林安赶到站台时，车站里的咖啡店已经关门了。', 'zh'), 'passage');
  assert.equal(selectionKind('x'.repeat(EXPLAIN_LIMITS.selection + 1), 'en'), null, 'too much to act on');
}

/* --- Context sent with a selection stays inside what each endpoint accepts - */
{
  const text = 'The wind blew. The traveler held his cloak tighter! Then the sun shone.';
  const start = text.indexOf('cloak');
  assert.equal(sentenceAround(text, start, start + 5), 'The traveler held his cloak tighter!');
  const zh = '北风吹得很猛。旅人把斗篷裹得更紧了！后来太阳出来了。';
  assert.equal(sentenceAround(zh, zh.indexOf('斗篷'), zh.indexOf('斗篷') + 2), '旅人把斗篷裹得更紧了！');
  const huge = `${'word '.repeat(400)}target ${'word '.repeat(400)}`;
  const at = huge.indexOf('target');
  const bounded = sentenceAround(huge, at, at + 6, LOOKUP_LIMITS.context);
  assert.ok(bounded.length <= LOOKUP_LIMITS.context && bounded.includes('target'));
}

/* --- Which learner action reaches which service ---------------------------- */
const api = read('static/orena/infrastructure/api.js');
assert.match(api, /readingLookup:\(payload\)=>request\('\/api\/reading\/lookup'/);
assert.doesNotMatch(api, /contextualGloss/);

// No AI runs while reading: the Reader and the Quick Sheet never ask for a
// contextual gloss, and the Reader does no background work as text scrolls by.
for (const file of ['static/orena/screens/reader/screen.js', 'static/orena/screens/reader/lexical.js', 'static/orena/screens/quick-sheet/sheet.js']) {
  assert.doesNotMatch(read(file), /contextualGloss|contextualDictionary/, `${file}: no AI runs while reading`);
}
assert.doesNotMatch(read('static/orena/screens/reader/screen.js'), /IntersectionObserver/, 'no background work as paragraphs scroll by');
// The Reader's pointer layer only reports what was pointed at; the explanation
// is reached from the Quick Sheet alone.
assert.doesNotMatch(read('static/orena/screens/reader/lexical.js'), /api\.(wordDetail|sentenceSheet|readingLookup)\(/,
  'the pointer layer does not ask for an explanation itself');

console.log('Reader: typed blocks, chapters, bounded settings, selection and context limits, no AI while reading PASS');
