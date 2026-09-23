/* The word heard where it is said: frames 06 and 07.
 *
 * What this holds is the promise the screen makes: every clip is a real moment
 * in real media. Nothing is generated, nothing is stitched, and a word the
 * catalogue has never said has no clips rather than an invented one.
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(`../static/orena/${path}`, import.meta.url), 'utf8');
const screen = read('ui/word-clips.js');
const room = read('ui/expression.js');
const deep = read('ui/word-deep.js');
const css = read('rooms.css');
const copy = read('ui/copy.js');
const copyVi = read('ui/copy-vi.js');
const clipsPy = readFileSync(new URL('../writing_coach/word_clips.py', import.meta.url), 'utf8');

/* --- Real media, or none ------------------------------------------------ */

assert.match(
  clipsPy,
  /if not text or folded not in text\.casefold\(\):\n\s*continue/,
  "only a segment's own transcript decides that the word is said in it",
);
/* Nothing here speaks: a clip is media that already exists, so this module
   imports no voice and builds no audio. */
assert.doesNotMatch(clipsPy, /^from writing_coach\.word_audio|^import.*kokoro/im, 'no voice is imported');
assert.doesNotMatch(clipsPy, /WordAudioLibrary|synthesize|speak\(/, 'and no audio is made');
assert.match(screen, /if \(!clip\)/, 'a word with no clips gets no player');
assert.match(screen, /c\.vocabularyNoClips/, 'it says so instead');

/* --- Exactly the moment, not the lesson --------------------------------- */

assert.match(room, /sound\.currentTime = \(Number\(clip\.startMs\) \|\| 0\) \/ 1000;/,
  'playing a clip starts where the clip starts');
assert.match(room, /sound\.currentTime \* 1000 >= \(Number\(clip\.endMs\) \|\| 0\)/,
  'and stops where it ends');
assert.match(room, /if \(!clip\?\.url \|\| clip\.kind === 'embed'\) return;/,
  'an embed is not something this screen may seek inside');
assert.match(room, /const stopClip = \(\) => \{/, 'and a second clip cannot start over the first');

/* --- The way in the desktop deep frame draws ---------------------------- */

assert.match(deep, /const clips = Number\(data\.clipCount\) \|\| 0;/, 'the deep screen knows how many there are');
assert.match(deep, /const toClips = clips\n\s*\?/, 'and draws the way in only when there are some');

/* --- What the frame draws ----------------------------------------------- */

assert.match(screen, /function inLine\(text, word, className\)/, 'the word is marked inside the line');
assert.doesNotMatch(screen, /\.replace\([^)]*<span/, 'by splitting the text, not by writing markup into it');
assert.match(screen, /data-clip-play="\$\{index\}"/, 'every other context can be played');
assert.match(screen, /data-clip-open="\$\{esc\(clip\.lessonId\)\}"/, 'and the clip it came from can be opened');

for (const [what, rule] of [
  ['the screen', /\.word-clips__screen \{[^}]*block-size: 196px;[^}]*border-radius: 16px;/s],
  ['its play button', /\.word-clips__play \{[^}]*inline-size: 62px;/s],
  ['the line', /\.word-clips__line \{[^}]*font-size: 19px;/s],
  ["another context's thumbnail", /\.clip-row__art \{[^}]*inline-size: 108px;[^}]*block-size: 62px;[^}]*border-radius: 15px;/s],
  ['the two actions', /\.clip-action \{[^}]*block-size: 44px;[^}]*border-radius: 13px;/s],
])
  assert.match(css, rule, `${what} is the frame’s size`);

for (const key of ['vocabularyClipCount', 'vocabularyOtherContexts', 'vocabularyOpenClip', 'vocabularyNoClips', 'wordDeepClips', 'wordDeepSeeClips']) {
  assert.equal((copy.match(new RegExp(`\\b${key}:`, 'g')) || []).length, 2, `${key} in English and Chinese`);
  assert.ok(copyVi.includes(`${key}:`), `${key} in Vietnamese`);
}

console.log('test_orena_word_clips.mjs: real moments in real media, or none');
