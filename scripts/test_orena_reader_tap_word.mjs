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
assert.match(screen, /mine !== tapSeq/, 'latest tap wins');
assert.ok(screen.includes('Script=Han}/u.test(word)'), 'only a Han character waits for the tagger');
console.log('reader tap word gate: ok');

// Listening: the transcript draws one Han character per column; a tap widens to the tagged word (same helper, no second segmenter).
const shared = await import('../static/orena/product/word-span.js');
assert.equal(shared.wordSpanAt, wordSpanAt, 'the Reader and Listening share one wordSpanAt');
const { createLineTagger, widenHanTap, hanTokens } = await import('../static/orena/screens/listening/model.js');
const line = '他是神龙大侠。';
const lineTokens = hanTokens(line, null);
const shen = lineTokens[2];
const tagged = [{ start: 0, end: 1 }, { start: 1, end: 2 }, { start: 2, end: 4 }, { start: 4, end: 6 }];
let calls = 0;
const tagger = createLineTagger({ allowed: () => true, request: async () => { calls += 1; return tagged; } });
assert.equal(await widenHanTap({ text: line, token: shen, word: '神', tags: () => tagger('s1', line) }), '神龙', 'a tap on 神 names 神龙');
assert.equal(await widenHanTap({ text: line, token: lineTokens[3], word: '龙', tags: () => tagger('s1', line) }), '神龙');
assert.equal(calls, 1, 'one tagger request per line');
assert.equal(await widenHanTap({ text: line, token: shen, word: '龙', tags: () => tagger('s1', line) }), '龙', 'a stale character is refused');
assert.equal(await widenHanTap({ text: 'ok', token: { core: 'ok', start: 0 }, word: 'ok', tags: () => assert.fail('no request for Latin') }), 'ok');
// A tagger that does not answer in time leaves the character.
assert.equal(await widenHanTap({ text: line, token: shen, word: '神', tags: () => new Promise(() => {}), waitMs: 10 }), '神');
// A tagger that fails is forgotten, so the next tap asks again.
let attempts = 0;
const flaky = createLineTagger({ allowed: () => true, request: async () => { attempts += 1; if (attempts === 1) throw new Error('down'); return tagged; } });
assert.equal(await widenHanTap({ text: line, token: shen, word: '神', tags: () => flaky('s1', line) }), '神');
assert.equal(await widenHanTap({ text: line, token: shen, word: '神', tags: () => flaky('s1', line) }), '神龙');
// Language mismatch: no request at all.
let sent = 0;
const closed = createLineTagger({ allowed: () => false, request: async () => { sent += 1; return tagged; } });
assert.equal(await widenHanTap({ text: line, token: shen, word: '神', tags: () => closed('s1', line) }), '神');
assert.equal(sent, 0, 'zero requests when the text is not the learning language');
// A tap that is superseded (any later tap) opens nothing: the screen counts every click in the rows.
const listening = readFileSync(new URL('../static/orena/screens/listening/screen.js', import.meta.url), 'utf8');
assert.match(listening, /rowsEl\.addEventListener\('click', \(event\) => \{\s*tapSeq \+= 1;/, 'every tap supersedes a pending word tap');
assert.match(listening, /mine !== tapSeq/);
console.log('listening tap word gate: ok');
