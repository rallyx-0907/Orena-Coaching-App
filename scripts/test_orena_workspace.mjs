/* The learning workspace, the progressive hint, and the motion rules.

   Consuming and producing want different shapes. Following a voice is content;
   reconstructing a line is work, and work needs the thing being worked on and
   the thing being worked from visible at once. These hold the parts of that
   which are checkable without a browser. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  dictationHint,
  earnedPrefix,
  wordProgress,
  MAX_HINT_LEVEL,
} from '../static/orena/capabilities/dictation-hints.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const LINE = 'I went to the shop yesterday.';
const hint = (answer, level = 1, expected = LINE, source_language = 'en') =>
  dictationHint({ expected, answer, source_language, level });
const shown = (h) => h.slots.map((s) => s.text).join('');

/* A learner's own correct letters come back to them. Seeing the start they
   already typed is what lets them reason about the rest, and it reveals
   nothing: they wrote it. */
assert.equal(earnedPrefix('yesterday', 'yesterda'), 8);
assert.equal(earnedPrefix('bang', 'bnag'), 1, 'only the letters that actually match');
assert.equal(earnedPrefix('shop', 'SHO'), 3, 'dictation is not a spelling-case test');
assert.equal(earnedPrefix('shop', 'xyz'), 0);
assert.equal(earnedPrefix('shop', ''), 0);
// The whole word is never handed back this way - that would be a reveal.
assert.equal(earnedPrefix('shop', 'shop'), 3, 'the last character is always withheld');
assert.equal(earnedPrefix('去', '去'), 0, 'a one-character unit cannot be partly given');

const partial = hint('I went to the shop yesterda');
assert.ok(shown(partial).includes('yesterda▁'), 'the earned start stands, the rest does not');
assert.ok(!shown(partial).includes('yesterday'), 'the hint never completes the word');
assert.equal(partial.partial, 1);
assert.equal(partial.anchors, 5, 'words already correct are anchors');

/* Four states, distinguishable. A single undifferentiated run of marks tells a
   learner nothing about where they are. */
// One attempt that reaches all four: words got right, a word mistyped, and a
// word not attempted at all.
const kinds = new Set(hint('I wnet to the shop').slots.map((s) => s.kind));
assert.ok(kinds.has('anchor'), 'words the learner has are anchors');
assert.ok(kinds.has('partial'), 'a word in progress is its own state');
assert.ok(kinds.has('slot'), 'an untouched word is unknown');
assert.ok(kinds.has('structure'), 'punctuation and spacing stay as structure');

// Word boundaries and word shape are visible before anything is typed.
const blank = hint('');
assert.equal(blank.anchors, 0);
assert.equal(blank.partial, 0);
assert.ok(shown(blank).includes(' '), 'word boundaries survive');
assert.ok(/▁{4}/.test(shown(blank)), 'a longer word looks longer');
assert.ok(!shown(blank).includes('shop'), 'nothing is given away at level one');

// The deeper level offers an opening character and no more.
const deeper = hint('', MAX_HINT_LEVEL);
assert.ok(shown(deeper).includes('s▁▁▁'), 'the deeper hint opens a word');
assert.ok(!shown(deeper).includes('shop'), 'even the deepest hint is not the answer');
assert.equal(hint(LINE).complete, true, 'a finished line has nothing left to find');

/* Chinese counts natural character units rather than being forced through an
   English word-length model. */
const zh = hint('我昨天', 1, '我昨天去了商店。', 'zh');
assert.equal(zh.total, 7, 'every character is its own unit');
assert.equal(zh.anchors, 3);
assert.ok(shown(zh).startsWith('我昨天▁'), 'characters already produced stand');
assert.ok(shown(zh).endsWith('。'), 'punctuation stays as structure');
// A one-character unit has nothing to partially open, at any level.
assert.equal(
  shown(hint('', MAX_HINT_LEVEL, '我昨天去了商店。', 'zh')),
  shown(hint('', 1, '我昨天去了商店。', 'zh')),
  'offering the first character of a one-character word is the word',
);

// The progress the hint is built from carries what the learner attempted, which
// is what makes partial credit possible at all.
const progress = wordProgress({ expected: LINE, answer: 'I wnet to the shop', source_language: 'en' });
assert.equal(progress[1].found, false);
assert.equal(progress[1].attempt, 'wnet', 'a wrong word keeps what was written');
assert.equal(progress[0].found, true);
assert.equal(progress[0].attempt, '', 'a correct word needs no attempt recorded');

/* The workspace. Media and work side by side while practising, each scrolling
   on its own, and the practice must be a sibling of the media rather than a
   child of it or no layout can place them apart. */
const encounter = read('static/orena/ui/encounter.js');
assert.ok(
  encounter.includes('</section><section class="practice-space" hidden>'),
  'the practice panel is a workspace column, not nested inside the media stage',
);
assert.ok(
  encounter.includes("window.matchMedia('(max-width: 1079px)')"),
  'narrow screens bring the work to the learner instead of asking them to find it',
);
assert.ok(
  encounter.includes("prefers-reduced-motion: reduce"),
  'the scroll respects a learner who asked for less motion',
);

const world = read('static/orena/world.css');
assert.ok(
  world.includes('.media-encounter:has(.practice-space:not([hidden]))'),
  'the encounter re-composes when a practice opens',
);
assert.ok(world.includes('@media (min-width: 1600px)'), 'wide screens get their own composition');
assert.ok(
  /@media \(min-width: 1600px\)[\s\S]{0,900}\.text-encounter/.test(world),
  'reading keeps a comfortable measure instead of stretching with the window',
);
assert.ok(
  /max-width: 800px\)[\s\S]{0,2000}\.seek-line,[\s\S]{0,200}display: none/.test(world),
  'narrow practice hides scrubbing it does not need',
);

/* Motion says something or it is noise, and it is off for anyone who asked. */
const foundation = read('static/orena/foundation.css');
assert.ok(
  foundation.includes('@media (prefers-reduced-motion: no-preference)'),
  'motion is opt-out by the platform preference',
);
assert.ok(foundation.includes('@keyframes orena-settle'), 'one shared arrival motion');
assert.ok(
  !/animation:[^;]*infinite/.test(foundation),
  'nothing loops: ambient movement is decoration, not communication',
);
assert.ok(
  foundation.includes("[tabindex='-1']:focus:not(:focus-visible)"),
  'a region focused for a screen reader does not wear a keyboard focus ring',
);

console.log('Workspace, progressive hints in EN/ZH, responsive composition and motion: PASS');
