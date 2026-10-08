/* The one fact the reader keeps about a place: how far into the chapter the learner has read.
 *
 * Device memory (product/memory.js) stores it beside the chapter index, so Book detail and the
 * Reader can say how far in the learner was and what is left. It is clamped and whole, and an
 * unmeasured place stays unmeasured - not measured is not nought. (The Reader screen itself is
 * test_orena_screen_reader.mjs.)
 */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { learnerMemory } from '../static/orena/product/memory.js';

const memorySource = readFileSync(new URL('../static/orena/product/memory.js', import.meta.url), 'utf8');
assert.match(memorySource, /const within = Number\(place\?\.within\);/, 'a place may say how far into itself');
assert.match(memorySource, /Math\.max\(0, Math\.min\(100, Math\.round\(within\)\)\)/, 'clamped and whole, like everything else kept there');
assert.match(memorySource, /if \(!Number\.isFinite\(within\)\) return \{ index, total \};/, 'and absent stays absent');

const data = {};
const storage = { getItem: (k) => data[k] ?? null, setItem: (k, v) => { data[k] = String(v); } };
const memory = learnerMemory(storage, 'owner', 'en');
memory.enter({ id: 'book:alice/ch-4', title: 'Chapter IV', intent: 'reading', place: { index: 4, total: 14, within: 33.6 } });
assert.equal(memory.value.continuation[0].place.within, 34, 'kept whole');
memory.enter({ id: 'book:alice/ch-5', title: 'Chapter V', intent: 'reading', place: { index: 5, total: 14, within: 140 } });
assert.equal(memory.value.continuation[0].place.within, 100, 'clamped to the whole chapter');
memory.enter({ id: 'book:alice/ch-6', title: 'Chapter VI', intent: 'reading', place: { index: 6, total: 14 } });
assert.equal(memory.value.continuation[0].place.within, undefined, 'not measured is not nought');
assert.equal(learnerMemory(storage, 'owner', 'en').value.continuation[0].place.index, 6, 'and it survives a reload');

console.log('test_orena_reader_place.mjs: the reader keeps its place within the chapter, whole and clamped');
