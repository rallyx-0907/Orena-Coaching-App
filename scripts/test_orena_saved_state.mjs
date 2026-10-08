/* Saved is the `kept` relationship, nothing else (D4 I4, implementation review P1-1): a row that only holds where
   the learner was, or a mark, is not a bookmark, and the bookmark toggle never targets it. */
import assert from 'node:assert/strict';

globalThis.location = { href: '' };
let items = [];
globalThis.fetch = async () => ({ ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => ({ items }) });
const { loadSaved } = await import('../static/orena/screens/reader/source.js');
const memory = { value: { kept: [] } };
const doc = { id: 'reading:14', isBook: false };

items = [{ id: 'place-row', relationship: 'started' }];
assert.deepEqual(await loadSaved('article', doc, memory), { saved: false, itemId: '' }, 'opened is not saved');
items = [{ id: 'place-row', relationship: 'started' }, { id: 'bookmark', relationship: 'kept' }];
assert.deepEqual(await loadSaved('article', doc, memory), { saved: true, itemId: 'bookmark' }, 'the toggle targets the bookmark, never the place row');
items = [];
assert.deepEqual(await loadSaved('article', doc, memory), { saved: false, itemId: '' });
console.log('Saved state: only the kept relationship is a bookmark, and the toggle targets it: PASS');
