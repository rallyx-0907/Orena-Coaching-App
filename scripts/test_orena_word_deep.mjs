/* One word, opened all the way: the canonical deep frames' contract.
 *
 * What these hold is the part a later hand undoes by accident: that the
 * screen draws only the sections it was given something for, that it invents
 * no section of its own, and that the two phone pages and the desktop layout
 * are one piece of markup rather than three that drift apart.
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(`../static/orena/${path}`, import.meta.url), 'utf8');
const room = read('ui/word-deep.js');
const css = read('rooms.css');
const copy = read('ui/copy.js');
const copyVi = read('ui/copy-vi.js');

/* --- Nothing is drawn over nothing -------------------------------------- */

/* `section()` is the only way a heading reaches the screen, and it returns
   nothing when its body is empty. A heading written any other way would put a
   label over an empty box. */
assert.match(
  room,
  /function section\(name, body\) \{\s*return body \?/,
  'a section exists only when it has something in it',
);
const headings = room.match(/class="ds-label word-deep__label"/g) || [];
assert.equal(headings.length, 1, 'and every heading goes through that one place');

/* --- The eight sections the frames draw, and no ninth -------------------- */

const sections = [
  'wordDeepSenses',
  'wordDeepCombinations',
  'wordDeepContrast',
  'wordDeepMistake',
  'wordDeepMentalModel',
  'wordDeepRelated',
  'wordDeepWhereFrom',
  'wordDeepYourSentences',
];
const named = [...room.matchAll(/section\(c\.(\w+),/g)].map((m) => m[1]);
assert.deepEqual(named, sections, 'the frames’ sections, in the frames’ order');
for (const key of [...sections, 'wordDeepKeep', 'wordDeepUnkeep', 'wordDeepAsk', 'wordDeepScrollOn', 'wordDeepScrollBack', 'wordDeepChecked']) {
  assert.ok(copy.includes(`${key}:`), `${key} is written in English and Chinese`);
  assert.ok(copyVi.includes(`${key}:`), `${key} is written in Vietnamese`);
}
/* Two dictionaries live in copy.js, so every key is in it twice. */
for (const key of sections)
  assert.equal(
    (copy.match(new RegExp(`${key}:`, 'g')) || []).length,
    2,
    `${key} is in both of copy.js’s dictionaries`,
  );

/* --- One markup, two layouts -------------------------------------------- */

/* The phone puts a half away; the desktop shows it again. If the markup ever
   forks by width instead, these two go out of step silently. */
assert.match(room, /word-deep__half--meaning/, 'the dictionary’s half');
assert.match(room, /word-deep__half--yours/, 'and the learner’s half');
assert.doesNotMatch(room, /matchMedia|innerWidth|isDesktop/, 'the module does not measure the window');
assert.match(css, /\.word-deep__half\[hidden\] \{ display: flex; \}/, 'width brings the hidden half back');
assert.match(css, /\.word-deep__foot \{ display: none; \}/, 'and takes the foot away, which that frame draws none of');

/* --- Measured, not eyeballed -------------------------------------------- */

for (const [what, rule] of [
  ['the headword', /font-size: 26px;/],
  ['its reading', /\.word-deep__reading \{ font-size: 14px; color: var\(--accent-ink\); \}/],
  ['a section label', /font-size: 10\.5px;\n  letter-spacing: 0\.13em;/],
  ['a sense row', /\.word-deep__sense \{ display: flex; gap: 12px; padding: 13px 14px; \}/],
  ['its part of speech', /inline-size: 58px;/],
  ['a related row’s term', /\.word-deep__pair--wide \.word-deep__term \{ inline-size: 72px; \}/],
  ['a foot action', /block-size: 50px;/],
])
  assert.match(css, rule, `${what} is the frame’s size`);

/* Colour has one owner: this screen names no colour of its own. */
const from = css.indexOf('.word-deep {');
const block = css.slice(from, css.indexOf('/* ---', from + 10));
assert.doesNotMatch(block, /#[0-9a-fA-F]{3,8}\b/, 'the screen reads tokens, never a literal colour');

/* --- The learner’s own words, never guessed ------------------------- */

assert.match(room, /marked\(row\.text, word\)/, 'the word is marked where it stands in the sentence');
assert.doesNotMatch(room, /\.replace\(.*<mark>/s, 'and by splitting the text, not by writing markup into it');

console.log('test_orena_word_deep.mjs: one word, opened all the way, and nothing invented');
