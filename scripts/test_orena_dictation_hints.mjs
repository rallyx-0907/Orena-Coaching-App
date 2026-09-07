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
assert.equal(text(blank), '▁▁▁▁, ▁▁ ▁▁▁ ▁▁▁▁ ▁ ▁▁▁?');
assert.equal(blank.remaining, 6);
assert.equal(blank.anchors, 0);
assert.equal(blank.total, 6);

// A slot shows how long the word is, and at the deepest level its first
// character - never more, so the last character is always the learner's.
const deep = dictationHint({ expected, source_language: 'en', level: MAX_HINT_LEVEL });
// "a" is one character, so offering its first would be offering the word. It
// stays masked; the deepest hint still never completes anything by itself.
assert.equal(text(deep), 'A▁▁▁, d▁ y▁▁ h▁▁▁ ▁ p▁▁?');
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
assert.equal(text(partial), 'Anna, do you ▁▁▁▁ ▁ ▁▁▁?');
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
assert.equal(text(zhBlank), '▁▁▁▁？');
assert.equal(zhBlank.total, 4, 'each Hanzi is its own unit');
const zhPartial = dictationHint({
  expected: zhExpected,
  answer: '你有',
  source_language: 'zh',
  level: 1,
});
assert.equal(text(zhPartial), '你有▁▁？');
assert.equal(zhPartial.anchors, 2);
// At the deepest level a single-character word cannot be half-shown, so it
// stays hidden rather than being handed over.
const zhDeep = dictationHint({ expected: zhExpected, source_language: 'zh', level: 2 });
assert.equal(text(zhDeep), '▁▁▁▁？');

// Speaker labels are part of the line a learner sees and types.
const labelled = dictationHint({
  expected: '王明：这是什么？',
  answer: '王明',
  source_language: 'zh',
  level: 1,
});
assert.equal(text(labelled), '王明：▁▁▁▁？');

assert.deepEqual(
  hintTokens('a, b', 'en').map((t) => t.text),
  ['a', ', ', 'b'],
);
assert.deepEqual(confirmedWords({ expected: 'a b', answer: '', source_language: 'en' }), [
  false,
  false,
]);

console.log(
  'Dictation hints: structure, earned anchors, EN/ZH slot shapes, and a ladder that never reaches the answer PASS',
);
