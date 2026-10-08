/* The progressive dictation hint, and the motion rule.

   Reconstructing a line is work: what the learner has earned by typing comes back to them,
   and a hint never hands over the answer. These hold the parts that are checkable without a
   browser. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  dictationHint,
  earnedCharacters,
  wordProgress,
  MAX_HINT_LEVEL,
} from '../static/orena/capabilities/dictation-hints.js';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const LINE = 'I went to the shop yesterday.';
const hint = (answer, level = 1, expected = LINE, source_language = 'en') =>
  dictationHint({ expected, answer, source_language, level });
const shown = (h) => h.slots.map((s) => s.text).join('');

/* A learner's own correct characters come back to them wherever they are in
   the word, not only in an unbroken run from the start. Seeing what they
   already got right is what lets them reason about the rest, and it reveals
   nothing: they wrote it. */
const earned = (word, attempt) => earnedCharacters(word, attempt).map(Number).join('');
assert.equal(earned('yesterday', 'yesterda'), '111111110');
// The learner typed 'bnag': the b, n and g are theirs; the misplaced a is not.
assert.equal(earned('bang', 'bnag'), '1011', 'a transposition credits only what landed');
assert.equal(earned('shop', 'SHO'), '1110', 'dictation is not a spelling-case test');
assert.equal(earned('shop', 'xyz'), '0000');
assert.equal(earned('shop', ''), '0000');
// A word typed in full is the learner's own work, so all of it stands. What is
// never handed over is a character they did not produce - see the hint gate.
assert.equal(earned('shop', 'shop'), '1111');

const partial = hint('I went to the shop yesterda');
assert.ok(shown(partial).includes('yesterda*'), 'the earned characters stand, the rest do not');
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
assert.ok(/\*{4}/.test(shown(blank)), 'a longer word looks longer');
assert.ok(!shown(blank).includes('shop'), 'nothing is given away at level one');

// The deeper level offers an opening character and no more.
const deeper = hint('', MAX_HINT_LEVEL);
assert.ok(shown(deeper).includes('s***'), 'the deeper hint opens a word');
assert.ok(!shown(deeper).includes('shop'), 'even the deepest hint is not the answer');
assert.equal(hint(LINE).complete, true, 'a finished line has nothing left to find');

/* Chinese counts natural character units rather than being forced through an
   English word-length model. */
const zh = hint('我昨天', 1, '我昨天去了商店。', 'zh');
assert.equal(zh.total, 7, 'every character is its own unit');
assert.equal(zh.anchors, 3);
assert.ok(shown(zh).startsWith('我昨天*'), 'characters already produced stand');
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

/* Motion says something or it is noise, and it is off for anyone who asked. The learner kit's
   base stylesheet owns this for every screen. */
const base = read('static/orena/kit/base.css');
const reduced = base.slice(base.indexOf('@media (prefers-reduced-motion: reduce)'));
assert.ok(base.includes('@media (prefers-reduced-motion: reduce)'), 'the platform preference is honoured');
assert.match(reduced, /animation-duration: 0\.001ms !important;[\s\S]*?transition-duration: 0\.001ms !important;/,
  'reduced motion removes animation and transition for every element');
assert.match(base, /\[tabindex="-1"\]:focus-visible \{ outline: none; \}/,
  'a region focused programmatically does not wear a keyboard focus ring');
assert.match(base, /:focus-visible \{/, 'a keyboard focus ring exists');

console.log('Progressive dictation hints in EN/ZH and the kit reduced-motion rule: PASS');
