/* Where the learner is, kept on the server (product/continue-sync.js; D4 I4, D-104 H-6, H-12).
   A stub fetch stands in for the network only. */
import assert from 'node:assert/strict';

globalThis.location = { href: '' };
const calls = [];
let script = [];
globalThis.fetch = async (url, options = {}) => {
  calls.push({ url, method: options.method || 'GET', body: options.body ? JSON.parse(options.body) : null });
  const next = script.shift() || { status: 200, body: {} };
  return { ok: next.status < 400, status: next.status, headers: { get: () => 'application/json' }, json: async () => next.body };
};
const sync = await import('../static/orena/product/continue-sync.js');
const { learnerMemory, setPlaceSink } = await import('../static/orena/product/memory.js');

/* Only reading, listening and books have a place. */
assert.equal(sync.placeKind({ id: 'media:lesson-1' }), 'listening');
assert.equal(sync.placeKind({ id: 'media:lesson-1', intent: 'dictation' }), 'listening');
assert.equal(sync.placeKind({ id: 'book:b1:c2' }), 'book');
assert.equal(sync.placeKind({ id: 'text:abc' }), 'reading');
assert.equal(sync.placeKind({ id: 'article-42' }), 'reading');
for (const id of ['grammar:present', 'expression:free', 'essay:9', 'conversation:x', 'voice:1']) assert.equal(sync.placeKind({ id }), '', id);
assert.equal(sync.placeKind({ id: 'x'.repeat(256) }), '');

/* The body is readPlace-shaped; a text with no position is not sent, and finished follows 100%. */
assert.deepEqual(sync.placeBody({ id: 'text:abc', title: 'T', segment: 'p1s1', context: 'Book', place: { index: 2, total: 5, within: 40 } }),
  { kind: 'reading', place: { title: 'T', intent: null, segment: 'p1s1', context: 'Book', index: 2, total: 5, within: 40, finished: false } });
assert.equal(sync.placeBody({ id: 'text:abc', title: 'T', place: null }), null);
assert.equal(sync.placeBody({ id: 'text:abc', title: 'T', place: { index: 5, total: 5, within: 100 } }).place.finished, true);
assert.deepEqual(sync.placeBody({ id: 'media:l1', title: 'L', segment: 's3' }).place.index, 1, 'a listening place with only a segment still has one');

/* A visit is written through the sink, once per boundary (the server coalesces the rest). */
calls.length = 0;
const stamp = 1_000_000;
await sync.sendPlace({ id: 'text:abc', title: 'T', place: { index: 2, total: 5, within: 10 } }, stamp);
await sync.sendPlace({ id: 'text:abc', title: 'T', place: { index: 2, total: 5, within: 30 } }, stamp + 5000);
await sync.sendPlace({ id: 'text:abc', title: 'T', place: { index: 3, total: 5, within: 30 } }, stamp + 6000);
await sync.sendPlace({ id: 'text:abc', title: 'T', place: { index: 3, total: 5, within: 31 } }, stamp + 40000);
assert.deepEqual(calls.map((call) => [call.method, call.url, call.body.place.index]), [
  ['PUT', '/api/continue/text%3Aabc', 2], ['PUT', '/api/continue/text%3Aabc', 3], ['PUT', '/api/continue/text%3Aabc', 3],
]);

/* Clearing sends the cleared flag only. */
calls.length = 0;
await sync.clearPlace('text:abc');
assert.deepEqual(calls[0].body, { kind: 'reading', place: { cleared: true } });
await sync.clearPlace('grammar:x');
assert.equal(calls.length, 1, 'a kind without a place sends nothing');

/* Server places come first, newest first; device entries the server lacks stay readable. */
const merged = sync.mergeContinuation(
  [{ content_id: 'text:a', kind: 'reading', place: { title: 'A', index: 4, total: 8, within: 50, segment: 'p3s1', context: '' } }],
  [{ id: 'text:a', title: 'stale', place: { index: 1, total: 8 } }, { id: 'media:old', title: 'Legacy', place: null }],
);
assert.deepEqual(merged.map((entry) => [entry.id, entry.title]), [['text:a', 'A'], ['media:old', 'Legacy']]);
assert.deepEqual(merged[0].place, { index: 4, total: 8, within: 50 });
assert.equal(merged[0].segment, 'p3s1');
assert.equal(sync.mergeContinuation(null, [{ id: 'x' }]).length, 1, 'no server answer leaves the device list');

/* The memory sends a visit through the sink and takes the merged list without echoing it back. */
const store = (() => {
  const data = {};
  return { data, getItem: (key) => data[key] ?? null, setItem: (key, value) => { data[key] = String(value); }, removeItem: (key) => { delete data[key]; } };
})();
const seen = [];
setPlaceSink({ enter: (entry) => seen.push(['enter', entry.id]), clear: (id) => seen.push(['clear', id]) });
const memory = learnerMemory(store, 'owner', 'en');
memory.enter({ id: 'text:z', title: 'Z', place: { index: 1, total: 2 } });
memory.replaceContinuation([{ id: 'text:y', title: 'Y', place: null }]);
memory.remove('text:z');
assert.deepEqual(seen, [['enter', 'text:z'], ['clear', 'text:z']]);
assert.deepEqual(memory.value.continuation.map((entry) => entry.id), ['text:y']);
setPlaceSink(null);

/* The read: a failed request keeps the device list. */
script = [{ status: 500, body: {} }];
assert.equal(await sync.syncContinuation(learnerMemory(store, 'o2', 'en')), false);

console.log('Continue sync: kinds with a place, body, throttle, clear, server-first merge with legacy device entries: PASS');
