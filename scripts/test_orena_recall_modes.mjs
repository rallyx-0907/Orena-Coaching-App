/* How a card asks its question: the four canonical review modes.
 *
 * What these hold is that a mode is offered only when the card has what it
 * needs, that a typed answer is judged the way the frame says it is judged,
 * and that a chooser's options do not move between paints.
 */
import assert from 'node:assert/strict';
import {
  ALWAYS_ON,
  CHOICES,
  NOT_HERE,
  TYPING_TRIES,
  answersIn,
  checkTyped,
  choicesFor,
  clozeFor,
  defaultReviewSettings,
  fold,
  hintFor,
  modesFor,
  readReviewSettings,
  taskFor,
} from '../static/orena/product/recall-modes.js';

/* --- Folding: what two spellings must share ----------------------------- */

assert.equal(fold('bạn bè'), 'ban be', 'the marks come off');
assert.equal(fold('  Happy,   glad! '), 'happy glad', 'so do case, punctuation and doubled spaces');
assert.notEqual(fold('ban'), fold('bank'), 'but never a letter');

/* --- A typed answer ----------------------------------------------------- */

assert.deepEqual(checkTyped('bạn bè', 'bạn bè · friend'), { ok: true, exact: true, foldedOnly: false });
assert.deepEqual(checkTyped('ban be', 'bạn bè · friend'), { ok: true, exact: false, foldedOnly: true },
  'typed without the marks is still remembered - the frame says so');
assert.deepEqual(checkTyped('friend', 'bạn bè · friend'), { ok: true, exact: true, foldedOnly: false },
  'any of the answers written in the meaning is the answer');
assert.equal(checkTyped('cao', 'vui · happy, glad').ok, false, 'and a wrong one is wrong');
assert.equal(checkTyped('   ', 'vui').ok, false, 'nothing typed is not an answer');
assert.deepEqual(answersIn('vui · happy, glad'), ['vui', 'happy', 'glad']);

/* The hint gives away how the answer starts and how long it is, never more. */
assert.deepEqual(hintFor('vui vẻ · happy'), { starts: 'v', pieces: 2 });
assert.equal(TYPING_TRIES, 2, 'the frame offers one more try after the first');

/* --- A chooser only when there is something to choose between ----------- */

const pool = [
  { word: '喜欢', definition: 'thích · to like' },
  { word: '想', definition: 'muốn · to want' },
  { word: '懂', definition: 'hiểu · to understand' },
  { word: '高兴', definition: 'vui · happy' },
];
const card = pool[3];
const options = choicesFor(card, pool);
assert.equal(options.length, CHOICES, 'four options, as the frame draws');
assert.ok(options.includes('vui · happy'), 'one of them is the answer');
assert.equal(new Set(options).size, CHOICES, 'and no two are the same');
assert.deepEqual(options, choicesFor(card, pool), 'the same card offers the same order twice');
assert.deepEqual(
  choicesFor(card, [pool[0]]),
  [],
  'a card with too few neighbours is not made into a chooser',
);

/* --- A cloze only when the sentence really holds the word --------------- */

assert.deepEqual(
  clozeFor({ word: 'drikker', source_fragment: 'Hun drikker kaffe hver morgen.' }),
  { segments: ['Hun ', ' kaffe hver morgen.'], answer: 'drikker' },
);
assert.equal(
  clozeFor({ word: 'drikker', source_fragment: 'Hun spiser brød.' }),
  null,
  'a sentence that does not contain the word is no cloze',
);
assert.deepEqual(
  clozeFor({ word: 'hei', source_fragment: 'hei, og hei igjen' }).segments.length,
  3,
  'every occurrence is taken out, not only the first',
);

/* --- Which task a card is set ------------------------------------------- */

assert.deepEqual(
  modesFor({ word: '高兴', definition: 'vui' }, { hasAudio: false, pool }),
  [ALWAYS_ON, 'typing'],
  'no recording, no listening task - and none is synthesised to make one',
);
assert.ok(
  modesFor({ word: '高兴', definition: 'vui · happy' }, { hasAudio: true, pool }).includes('listen_choose'),
  'with a recording and neighbours, hearing and choosing is offered',
);
assert.ok(
  modesFor({ word: '高兴', definition: 'vui' }, { hasAudio: true, pool }).includes('dictation'),
  'and hearing and typing back needs only the recording',
);
assert.equal(
  taskFor({ word: '高兴', definition: 'vui' }, { modes: {} }, { hasAudio: true, pool }),
  ALWAYS_ON,
  'every mode turned off leaves the flashcard, which is always on',
);
assert.equal(
  taskFor({ word: '高兴', definition: 'vui' }, defaultReviewSettings(), { hasAudio: false, pool }),
  'typing',
  'and the one mode a card can be asked in is the one it is asked in',
);

/* --- The settings the sheet writes -------------------------------------- */

const settings = readReviewSettings({ newPerDay: 9000, limitPerDay: -3, modes: { typing: false, speak: true } });
assert.equal(settings.newPerDay, 50, 'a number read back from the device is clamped, not believed');
assert.equal(settings.limitPerDay, 20);
assert.equal(settings.modes.typing, false, 'a mode turned off stays off');
assert.equal(settings.modes[NOT_HERE], false, 'and speaking is not turned on here, whatever was stored');
assert.deepEqual(readReviewSettings(null), defaultReviewSettings(), 'nothing stored is the default');

console.log('test_orena_recall_modes.mjs: a card is only asked what it can answer');
