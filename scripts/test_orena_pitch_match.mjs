/* Gate for product/pitch-match.js: similarity and intonation are measured, or null. */
import assert from 'node:assert/strict';
import { melody, intonation, timingAgreement, similarity, matchOf } from '../static/orena/product/pitch-match.js';

const curve = (fn, { seconds = 2, hop = 0.01, start = 0 } = {}) => Array.from({ length: Math.round(seconds / hop) }, (_, i) => ({ t: start + i * hop, st: fn(i * hop / seconds) }));
const rise = (x) => 6 * Math.sin(Math.PI * x) + 2 * x; // a hill with a lift at the end
const inverted = (x) => -rise(x);

assert.equal(intonation(curve(rise), curve(rise)), 100, 'identical melodies');
assert.ok(intonation(curve(rise), curve(rise, { seconds: 3 })) >= 99, 'the same melody said slower');
assert.ok(intonation(curve((x) => rise(x) + 5), curve(rise)) >= 99, 'a higher voice');
assert.ok(intonation(curve((x) => 3 * rise(x)), curve(rise)) >= 99, 'a wider range keeps its shape');
assert.ok(intonation(curve(inverted), curve(rise)) <= 10, 'the opposite melody is low');
assert.equal(intonation(curve(() => 0.1), curve(rise)), 0, 'a monotone against a melody');
assert.equal(intonation(curve(rise), curve(() => 0.1)), null, 'a flat model has no shape to follow');
assert.equal(intonation([], curve(rise)), null);
assert.equal(intonation(curve(rise), null), null);
assert.equal(intonation(curve(rise, { seconds: 0.2 }), curve(rise)), null, 'too short to compare');
const gappy = curve(rise).map((p, i) => (i > 80 && i < 100 ? { ...p, st: null } : p));
assert.ok(intonation(gappy, curve(rise)) >= 95, 'a pause is bridged, not read as a different shape');
assert.equal(melody(curve(rise)).length, 100);

const words = (offsets) => offsets.map(([offsetMs, durationMs]) => ({ offsetMs, durationMs }));
const pair = (a, b) => a.map((you, i) => ({ you, model: b[i] }));
const base = words([[0, 400], [500, 400], [1000, 600]]);
assert.equal(timingAgreement(pair(base, base)), 100);
assert.equal(timingAgreement(pair(words([[0, 800], [1000, 800], [2000, 1200]]), base)), 100, 'pace alone is not disagreement');
assert.ok(timingAgreement(pair(words([[1200, 400], [600, 400], [0, 400]]), base)) < 50, 'words in the wrong places');
assert.equal(timingAgreement(pair(base.slice(0, 1), base.slice(0, 1))), null, 'one word says nothing about rhythm');
assert.equal(timingAgreement([]), null);
assert.equal(timingAgreement(null), null);

assert.equal(similarity(100, 100), 100);
assert.equal(similarity(100, 0), 60);
assert.equal(similarity(null, 80), null);
assert.equal(similarity(80, null), null);

const model = { contour: curve(rise) };
assert.deepEqual(matchOf({ you: { contour: curve(rise) }, model, pairs: pair(base, base) }), { intonation: 100, timing: 100, similarity: 100 });
assert.deepEqual(matchOf({ you: { contour: curve(rise) }, model }), { intonation: 100, timing: null, similarity: null });
assert.deepEqual(matchOf({ you: null, model, pairs: pair(base, base) }), { intonation: null, timing: 100, similarity: null });
assert.deepEqual(matchOf(), { intonation: null, timing: null, similarity: null });

console.log('Orena pitch match: intonation, timing agreement and similarity are measured or null: PASS');
