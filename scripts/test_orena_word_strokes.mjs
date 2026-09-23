/* Nét chữ (frame 05), on the capability Orena already had.
 *
 * The point of these assertions is the audit they encode: this screen adds no
 * stroke source. It reads `/api/chinese/stroke-order`, which has served the
 * vendored pack since 2026-08-26, and it judges tracing against that data's
 * own medians. If a later hand reaches for a second dataset, these fail.
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { STEPS, glyphSvg, stepsFor } from '../static/orena/ui/word-strokes.js';
import { tracedStroke, strokeTraced, heading } from '../static/orena/product/stroke-trace.js';

const read = (path) => readFileSync(new URL(`../static/orena/${path}`, import.meta.url), 'utf8');
const screen = read('ui/word-strokes.js');
const room = read('ui/expression.js');
const api = read('infrastructure/api.js');
const css = read('rooms.css');
const copy = read('ui/copy.js');
const copyVi = read('ui/copy-vi.js');

/* --- One stroke source, the one that was already here -------------------- */

assert.match(api, /chineseStrokeOrder:\(word\)=>request\(`\/api\/chinese\/stroke-order/,
  'the client Orena already had');
assert.match(room, /api\.chineseStrokeOrder\(wanted\)/, 'and the screen reads it');
assert.doesNotMatch(screen, /fetch\(|import\(/, 'the screen fetches nothing of its own');
for (const source of ['hanziwriter', 'cdn.jsdelivr', 'unpkg', 'graphics.txt', 'dictionary.txt'])
  assert.ok(!screen.includes(source) && !room.includes(source), `no second stroke source (${source})`);

/* --- The strip is the character being built ----------------------------- */

assert.equal(STEPS, 5, 'the frame draws five steps');
assert.deepEqual(stepsFor(13), [3, 5, 8, 10, 13], 'spread across the character, ending on the whole of it');
assert.deepEqual(stepsFor(3), [1, 2, 3], 'a short character shows one step per stroke');
assert.deepEqual(stepsFor(0), [], 'and no strokes is no strip');
assert.equal(stepsFor(13).at(-1), 13, 'the last step is always the finished character');

const drawn = glyphSvg({ stroke_paths: ['M0 0', 'M1 1', 'M2 2'] }, { upto: 2 });
assert.equal((drawn.match(/stroke-glyph__on/g) || []).length, 2, 'what is written so far is solid');
assert.equal((drawn.match(/stroke-glyph__off/g) || []).length, 1, 'and the rest is faint, as the frame dims it');
assert.match(drawn, /transform="scale\(1, -1\) translate\(0, -900\)"/,
  "the pack's glyph box runs upward, so it is flipped once, here");

/* --- Tracing judges direction and order, not neatness ------------------- */

const median = [[100, 800], [500, 800], [900, 800]];
assert.equal(tracedStroke(median, median).ok, true, 'the stroke itself is the stroke');
assert.equal(tracedStroke([...median].reverse(), median).ok, false, 'drawn backwards is wrong');
assert.equal(
  tracedStroke(median.map(([x, y], i) => [x + (i % 2 ? 30 : -30), y + 25]), median).ok,
  true,
  'a wobbly line is still the right stroke - the frame penalises direction and order, not handwriting',
);
assert.equal(tracedStroke([[100, 100], [900, 100]], median).reason, 'wrong-start',
  'a stroke started somewhere else is not this one');
assert.equal(tracedStroke([[100, 800]], median).reason, 'too-short', 'a tap is not a stroke');
assert.deepEqual(heading([[0, 0], [10, 0]]), [1, 0]);

/* Out of order is a different mistake from a scribble, and is told apart. */
const medians = [median, [[100, 400], [900, 400]]];
assert.equal(strokeTraced(medians[1], medians), 1, 'the stroke they actually drew is found');
assert.equal(strokeTraced([[0, 0], [5, 5]], medians), -1, 'a scribble matches nothing');
assert.match(room, /strokeState\.wrongReason = other >= 0 \? 'order' : judged\.reason;/,
  'and the two are recorded differently');

/* --- What the frame draws ----------------------------------------------- */

assert.match(screen, /if \(!surface\) return '';/, 'a part with no character is not a card');
assert.match(screen, /const partsBlock = parts\.length/, 'and no parts at all is no section');
assert.match(room, /const strokeParts = \(word\) => \{/, 'the parts come from the entry, not from the glyph');
assert.match(room, /deepData\?\.orthography\?\.parts\?\.\[character\]/,
  'through the orthography contract that already exists');

/* And what it draws is decomposition, labelled as such. The architecture
   requires verified etymology, modern structural decomposition and a learner
   mnemonic to be told apart; this is the second, and says so. */
const parts = readFileSync(
  new URL('../writing_coach/languages/chinese/character_parts.py', import.meta.url),
  'utf8',
);
assert.match(parts, /structural-decomposition/, 'the claim says what kind of claim it is');
assert.doesNotMatch(parts, /"etymology"/, 'and never claims etymology');
/* The safety net that makes curated content checkable: a declared radical is
   measured against the verified pack, so a wrong one fails a test. */
assert.match(parts, /tests\/test_character_parts\.py/, 'and names the test that checks it');

for (const [what, rule] of [
  ['a part card', /\.stroke-part \{[^}]*padding: 14px 8px;[^}]*border-radius: 14px;/s],
  ['its character', /\.stroke-part__glyph \{[^}]*font-size: 30px;/s],
  ['a step', /\.stroke-step \{\n  inline-size: 56px;[^}]*border-radius: 10px;/s],
  ['the square', /\.stroke-square \{[^}]*block-size: 190px;[^}]*border-radius: 15px;/s],
  ['the watch row', /\.stroke-watch \{[^}]*padding: 14px 15px;[^}]*border-radius: 15px;/s],
  ['a foot action', /\.stroke-action \{[^}]*block-size: 50px;[^}]*border-radius: 15px;/s],
  ["frame 26's column", /\.word-strokes__body, \.word-strokes__foot \{ max-inline-size: 640px; \}/],
])
  assert.match(css, rule, `${what} is the frame’s size`);

/* Shaking is motion, and motion is a preference. */
assert.match(css, /@media \(prefers-reduced-motion: reduce\) \{\n  \.stroke-square\[data-wrong='true'\]/,
  'a learner who asked for less motion gets the warning without the shake');

for (const key of ['strokesTitle', 'strokesCount', 'strokesParts', 'strokesOrder', 'strokesWatch', 'strokesTrace', 'strokesFree', 'strokesUnavailable']) {
  assert.equal((copy.match(new RegExp(`\\b${key}:`, 'g')) || []).length, 2, `${key} in English and Chinese`);
  assert.ok(copyVi.includes(`${key}:`), `${key} in Vietnamese`);
}

console.log('test_orena_word_strokes.mjs: frame 05 on the stroke capability that was already here');
