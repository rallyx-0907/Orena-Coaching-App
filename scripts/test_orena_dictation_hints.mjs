// A hint has to help a learner continue without becoming the answer. These
// assertions are mostly about what a hint refuses to say.
import assert from 'node:assert/strict';
import {
  dictationHint,
  hintTokens,
  confirmedWords,
  MAX_HINT_LEVEL,
} from '../static/orena/capabilities/dictation-hints.js';

const expected = 'Anna, do you have a pen?';
const text = (hint) => hint.slots.map((s) => s.text).join('');

// Structure survives: punctuation and spacing are never something to guess.
const blank = dictationHint({ expected, source_language: 'en', level: 1 });
assert.equal(text(blank), '****, ** *** **** * ***?');
assert.equal(blank.remaining, 6);
assert.equal(blank.anchors, 0);
assert.equal(blank.total, 6);

// A slot shows how long the word is, and at the deepest level its first
// character - never more, so the last character is always the learner's.
const deep = dictationHint({ expected, source_language: 'en', level: MAX_HINT_LEVEL });
// "a" is one character, so offering its first would be offering the word. It
// stays masked; the deepest hint still never completes anything by itself.
assert.equal(text(deep), 'A***, d* y** h*** * p**?');
assert.ok(!text(deep).includes('pen'), 'the deepest hint still is not the answer');
assert.equal(deep.level, MAX_HINT_LEVEL);
assert.equal(
  dictationHint({ expected, source_language: 'en', level: 9 }).level,
  MAX_HINT_LEVEL,
  'the hint ladder has a top',
);
assert.equal(dictationHint({ expected, source_language: 'en', level: 0 }).level, 1);

// Words the learner has already produced become anchors to read back from.
const partial = dictationHint({
  expected,
  answer: 'Anna do you',
  source_language: 'en',
  level: 1,
});
assert.equal(text(partial), 'Anna, do you **** * ***?');
assert.equal(partial.anchors, 3);
assert.equal(partial.remaining, 3);
assert.deepEqual(
  partial.slots.filter((s) => s.kind === 'anchor').map((s) => s.text),
  ['Anna', 'do', 'you'],
);

// Case and punctuation the learner did not reproduce still count as correct,
// exactly as the comparison they are shown already counts them.
assert.equal(
  dictationHint({
    expected,
    answer: 'anna DO you',
    source_language: 'en',
    level: 1,
  }).anchors,
  3,
);

// A wrong word is not an anchor, and does not shift the ones after it.
const wrong = dictationHint({
  expected,
  answer: 'Anna do we have',
  source_language: 'en',
  level: 1,
});
assert.deepEqual(
  wrong.slots.filter((s) => s.kind === 'anchor').map((s) => s.text),
  ['Anna', 'do', 'have'],
  'a substitution anchors what was right and leaves the rest open',
);
assert.equal(
  text(wrong),
  'Anna, do *** have * ***?',
  'a wrong word does not shift the words after it out of alignment',
);

// Getting everything right leaves nothing to hint at.
const done = dictationHint({
  expected,
  answer: 'Anna, do you have a pen?',
  source_language: 'en',
  level: 2,
});
assert.equal(done.remaining, 0);
assert.equal(done.complete, true);
assert.equal(text(done), expected);

// Chinese: one slot per character, no invented spacing.
const zhExpected = '你有笔吗？';
const zhBlank = dictationHint({ expected: zhExpected, source_language: 'zh', level: 1 });
assert.equal(text(zhBlank), '****？');
assert.equal(zhBlank.total, 4, 'each Hanzi is its own unit');
const zhPartial = dictationHint({
  expected: zhExpected,
  answer: '你有',
  source_language: 'zh',
  level: 1,
});
assert.equal(text(zhPartial), '你有**？');
assert.equal(zhPartial.anchors, 2);
// At the deepest level a single-character word cannot be half-shown, so it
// stays hidden rather than being handed over.
const zhDeep = dictationHint({ expected: zhExpected, source_language: 'zh', level: 2 });
assert.equal(text(zhDeep), '****？');

// Speaker labels are part of the line a learner sees and types.
const labelled = dictationHint({
  expected: '王明：这是什么？',
  answer: '王明',
  source_language: 'zh',
  level: 1,
});
assert.equal(text(labelled), '王明：****？');

assert.deepEqual(
  hintTokens('a, b', 'en').map((t) => t.text),
  ['a', ', ', 'b'],
);
assert.deepEqual(confirmedWords({ expected: 'a b', answer: '', source_language: 'en' }), [
  false,
  false,
]);

/* --- The line takes shape from what the learner types ---

   The mask is not a fixed row of blanks waiting for a whole word: every
   character the learner supplies correctly appears the moment they supply it,
   and every position still unfound stays marked. What makes this work is that
   the alignment happens at two levels - words first, then characters inside a
   matched word - so an insertion or a deletion early in the line does not
   shift every anchor after it. A naive index-by-index comparison fails every
   case below. */
const mask = (expected, answer, source_language = 'en') =>
  text(dictationHint({ expected, answer, source_language, level: 1 }));

const STARS = 'Under the stars tonight';
assert.equal(mask(STARS, ''), '***** *** ***** *******', 'the shape is there before anything is typed');
assert.equal(mask(STARS, 'Undar the stors tonighx'), 'Und*r the st*rs tonigh*');
assert.equal(mask(STARS, STARS), STARS, 'a finished line is simply the line');

for (const [name, expected, answer, want] of [
  // A repeated letter is not an excuse to credit the wrong position.
  ['repeated letters', 'little bottle kettle', 'littel bottle kettle', 'litt*e bottle kettle'],
  // The same word twice: both instances stand on their own.
  ['repeated words', 'the cat and the dog', 'the cat and the dog', 'the cat and the dog'],
  ['one of a repeated pair wrong', 'the cat and the dog', 'the cat and teh dog', 'the cat and t*e dog'],
  // Characters missing, and characters too many: neither shifts the rest.
  ['missing characters', 'tomorrow morning', 'tomorow moring', 'tomor*ow mor*ing'],
  ['extra characters', 'tomorrow morning', 'tommorrow moorning', 'tomorrow morning'],
  // A contraction is one word whose apostrophe still has to be earned.
  ['contraction', "I don't think it's", 'I dont think its', "I don*t think it*s"],
  // Punctuation is structure, not something to guess.
  ['punctuation', 'Wait, is that yours?', 'Wait is that yours', 'Wait, is that yours?'],
  // An edit in the middle leaves the words on both sides where they were.
  ['edit in the middle', 'one two three four five', 'one two thre four five', 'one two thre* four five'],
]) assert.equal(mask(expected, answer), want, name);

/* Transposed whole words are the honest limit of this: the aligner takes the
   conservative reading and credits one placement rather than inventing two.
   Under-crediting is the safe direction - it never shows a character the
   learner has not actually produced. */
assert.equal(mask('from the form', 'form the from'), '**** *** form');

/* Chinese counts characters, because that is what a learner produces. There is
   no word length to reveal and none is invented. */
assert.equal(mask('我昨天去了商店。', '', 'zh'), '*******。');
assert.equal(mask('我昨天去了商店。', '我昨天去商店', 'zh'), '我昨天去*商店。');
assert.equal(
  mask('我昨天去了商店。', '我昨天去了商城', 'zh'),
  '我昨天去了商*。',
  'a wrong character is the only one still marked',
);

/* Nothing is ever handed over that the learner did not type. */
for (const answer of ['', 'U', 'Under', 'Under the', 'Undar the stors'])
  for (const [index, mark] of [...mask(STARS, answer)].entries())
    if (mark !== '*' && mark !== ' ')
      assert.ok(
        answer.toLowerCase().includes(STARS[index].toLowerCase()),
        `"${answer}" was shown a character it never produced: ${STARS[index]}`,
      );

console.log(
  'Dictation hints: structure, earned characters, EN/ZH slot shapes, and a ladder that never reaches the answer PASS',
);
