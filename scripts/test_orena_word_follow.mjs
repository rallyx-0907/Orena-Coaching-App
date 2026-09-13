// Word-level Follow may only sharpen what segment Follow already shows. Every
// assertion here is about refusing to guess: an asset without usable word
// timing must fall back to the segment rather than highlight an approximation.
import assert from 'node:assert/strict';
import {
  wordSpans,
  activeWordIndex,
  linePieces,
} from '../static/orena/capabilities/word-timeline.js';

const english = {
  original_text: 'Anna, do you have a pen?',
  words: [
    { text: 'Anna', start_ms: 500, end_ms: 900 },
    { text: 'do', start_ms: 950, end_ms: 1100 },
    { text: 'you', start_ms: 1100, end_ms: 1250 },
    { text: 'have', start_ms: 1250, end_ms: 1500 },
    { text: 'a', start_ms: 1500, end_ms: 1560 },
    { text: 'pen', start_ms: 1600, end_ms: 2000 },
  ],
};

const spans = wordSpans(english);
assert.equal(spans.length, 6);
assert.deepEqual(
  spans.map((s) => english.original_text.slice(s.start, s.end)),
  ['Anna', 'do', 'you', 'have', 'a', 'pen'],
  'spans must address the canonical line, not a re-rendering of it',
);

// Position, not proximity: a pause belongs to no word.
assert.equal(activeWordIndex(spans, 700), 0);
assert.equal(activeWordIndex(spans, 1300), 3);
assert.equal(activeWordIndex(spans, 1580), -1, 'the gap between words is a gap');
assert.equal(activeWordIndex(spans, 100), -1, 'before the first word');
assert.equal(activeWordIndex(spans, 9000), -1, 'after the last word');
assert.equal(activeWordIndex(spans, Number.NaN), -1);

// Reassembling the pieces must give back the line exactly, punctuation and all.
const pieces = linePieces(english);
assert.equal(pieces.map((p) => p.text).join(''), english.original_text);
assert.ok(
  pieces.some((p) => p.text === ', ' && p.index === -1),
  'text between timed words stays untimed rather than joining a neighbour',
);

// Chinese has no spaces; the same mapping has to hold.
const chinese = {
  original_text: '这是什么？',
  words: [
    { text: '这', start_ms: 0, end_ms: 300 },
    { text: '是', start_ms: 300, end_ms: 600 },
    { text: '什么', start_ms: 600, end_ms: 1200 },
  ],
};
const zhSpans = wordSpans(chinese);
assert.equal(zhSpans.length, 3);
assert.equal(chinese.original_text.slice(zhSpans[2].start, zhSpans[2].end), '什么');
assert.equal(activeWordIndex(zhSpans, 800), 2);
assert.equal(linePieces(chinese).map((p) => p.text).join(''), chinese.original_text);

// Every way the timing can fail to describe the line degrades to the segment.
assert.equal(wordSpans({ original_text: 'A line', words: [] }), null, 'no timing');
assert.equal(wordSpans({ original_text: 'A line' }), null, 'no words field');
assert.equal(
  wordSpans({
    original_text: 'Anna, do you have a pen?',
    words: [{ text: 'Owen', start_ms: 0, end_ms: 100 }],
  }),
  null,
  'timing for text this line does not contain',
);
assert.equal(
  wordSpans({
    original_text: 'Owen: hello there',
    words: [
      { text: 'hello', start_ms: 0, end_ms: 100 },
      { text: 'Owen', start_ms: 100, end_ms: 200 },
    ],
  }),
  null,
  'words out of order against the line',
);
assert.equal(
  wordSpans({
    original_text: 'one two',
    words: [
      { text: 'one', start_ms: 500, end_ms: 900 },
      { text: 'two', start_ms: 100, end_ms: 300 },
    ],
  }),
  null,
  'timings that run backwards',
);
assert.equal(
  wordSpans({
    original_text: 'one two',
    words: [{ text: 'one', start_ms: 900, end_ms: 500 }],
  }),
  null,
  'a word that ends before it starts',
);
assert.equal(
  wordSpans({
    original_text: 'one two',
    words: [{ text: 'one', start_ms: null, end_ms: 500 }],
  }),
  null,
  'a word with no start',
);
assert.equal(linePieces({ original_text: 'A line', words: [] }), null);

console.log(
  'Word-level Follow: canonical-line mapping, gaps, EN/ZH, and truthful fallback when timing does not fit PASS',
);
