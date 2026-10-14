/* Gate: a tap on a script written without spaces names the WORD once the tagger has segmented the sentence, not the
   one character under the pointer (the fallback only while there are no tokens). */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const { wordSpanAt, segmentSentence } = await import('../static/orena/screens/reader/model.js');
const text = '中国政府宣布了新的计划。';
const tokens = [
  { start: 0, end: 2 }, { start: 2, end: 4 }, { start: 4, end: 6 }, { start: 6, end: 7 },
  { start: 7, end: 8 }, { start: 8, end: 10 }, { start: 10, end: 11 },
];
assert.deepEqual(wordSpanAt(text, tokens, 3, '府'), { text: '政府', start: 2, end: 4 });
assert.deepEqual(wordSpanAt(text, tokens, 0, '中'), { text: '中国', start: 0, end: 2 });
assert.equal(wordSpanAt(text, tokens, 3, '政'), null, 'a stale offset (the character is not there) is refused');
assert.equal(wordSpanAt(text, null, 3, '府'), null, 'no tokens: nothing to widen to');
assert.equal(wordSpanAt(text, [], 3), null);
assert.equal(wordSpanAt(text, tokens, 99), null);
// The tagged render has a word span for 政府 and the sentence is lossless.
assert.equal(segmentSentence(text, tokens).filter((p) => p.word).map((p) => p.text).slice(0, 2).join('|'), '中国|政府');

const screen = readFileSync(new URL('../static/orena/screens/reader/screen.js', import.meta.url), 'utf8');
assert.match(screen, /wholeWordAt\(seg, word, at\)/, 'the Reader widens an untagged character tap to its word');
const lexical = readFileSync(new URL('../static/orena/screens/reader/lexical.js', import.meta.url), 'utf8');
assert.match(lexical, /onTapWord\(\{ word: text\.slice\(span\.start, span\.end\), unit, at: span\.start \}\)/);
console.log('reader tap word gate: ok');
