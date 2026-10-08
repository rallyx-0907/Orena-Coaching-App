/* A removal holds across devices (product/account-records.js + screens/reader/annotations-sync.js; D4 I10).
   The account remembers removed ids (tombstones). An older device that still holds a removed item loses it when it
   opens the text, and when it writes it is refused, re-reads, and never re-adds a tombstoned item. A stub api stands
   in for the network only; the device stores are the real ones. */
import assert from 'node:assert/strict';

globalThis.location = { href: '' };
const records = await import('../static/orena/product/account-records.js');
const draftSync = await import('../static/orena/product/draft-sync.js');
const sync = await import('../static/orena/screens/reader/annotations-sync.js');
const { loadHighlights, toggleHighlight } = await import('../static/orena/screens/reader/highlights.js');
const { addNote, notesForContent } = await import('../static/orena/screens/quick-sheet/model.js');

const store = () => {
  const data = {};
  return { getItem: (key) => data[key] ?? null, setItem: (key, value) => { data[key] = String(value); }, removeItem: (key) => { delete data[key]; } };
};
const H = (id) => ({ id, segment: `p${id}`, sentence: `Sentence ${id}.`, at: '' });

let serverState;
let puts;
let failPutWith = null;
const stub = {
  accountBackbone: async () => ({ state: 'active' }),
  annotations: async () => {
    if (!serverState) { const error = new Error('none'); error.status = 404; throw error; }
    return { annotation: structuredClone(serverState) };
  },
  saveAnnotations: async (id, body) => {
    puts.push(body);
    if (failPutWith) { const error = new Error('refused'); error.status = failPutWith; failPutWith = null; throw error; }
    return { version: (serverState?.version || 0) + 1 };
  },
};
records.useApi(stub);
const reset = () => { draftSync.forgetAccountWorkState(); records.forgetRecordState(); puts = []; failPutWith = null; };
const CONTENT = 'article:x1';

/* 1. An older device that still holds what another device removed loses it when the text opens. */
{
  reset();
  const storage = store();
  toggleHighlight(storage, 'me', CONTENT, { segment: 'p0', sentence: 'Sentence old.' });
  const stale = loadHighlights(storage, 'me', CONTENT)[0];
  const note = addNote(storage, 'me', `k:${CONTENT}`, { type: 'question', text: 'old note', content: CONTENT });
  serverState = { version: 10, cleared: false, highlights: [H('kept')], notes: [], tombstones: [stale.id, note.id] };
  assert.equal(await sync.pullIntoDevice(storage, 'me', CONTENT), true);
  assert.deepEqual(loadHighlights(storage, 'me', CONTENT).map((item) => item.id), ['kept'], 'the removed highlight left this device, the account\'s arrived');
  assert.deepEqual(notesForContent(storage, 'me', CONTENT), [], 'the removed note left this device');
}

/* 2. A stale write is refused, re-read and merged: the account's items + this device's NEW ones, never a tombstone. */
{
  reset();
  const merged = [];
  serverState = { version: 10, cleared: false, highlights: [H('server')], notes: [], tombstones: ['removed-elsewhere'] };
  failPutWith = 409;
  const ok = await records.pushAnnotations(CONTENT, { highlights: [H('removed-elsewhere'), H('mine-new')], notes: [] }, { onMerged: (set) => merged.push(set) });
  assert.equal(ok, true);
  assert.equal(puts.length, 2);
  assert.deepEqual(puts[1].highlights.map((item) => item.id).sort(), ['mine-new', 'server'], 'a tombstoned item is never re-added');
  assert.equal(puts[1].expectedVersion, 10, 'the retry is against the version just read');
  assert.deepEqual(merged[0].highlights.map((item) => item.id).sort(), ['mine-new', 'server'], 'the device is told the merge');
}

/* 3. A refusal for bringing back a tombstoned id (422) is handled like a conflict. */
{
  reset();
  serverState = { version: 3, cleared: false, highlights: [], notes: [], tombstones: ['gone'] };
  failPutWith = 422;
  assert.equal(await records.pushAnnotations(CONTENT, { highlights: [H('gone'), H('new')], notes: [] }), true);
  assert.deepEqual(puts[1].highlights.map((item) => item.id), ['new']);
}

/* 4. The device store follows the merge, so the next pull or push starts from the same set. */
{
  reset();
  const storage = store();
  toggleHighlight(storage, 'me', CONTENT, { segment: 'p0', sentence: 'Sentence stale.' });
  const stale = loadHighlights(storage, 'me', CONTENT)[0];
  serverState = { version: 4, cleared: false, highlights: [H('server')], notes: [], tombstones: [stale.id] };
  failPutWith = 409;
  sync.scheduleAnnotationPush(storage, 'me', CONTENT, { delay: 0 });
  await new Promise((resolve) => setTimeout(resolve, 30));
  assert.deepEqual(loadHighlights(storage, 'me', CONTENT).map((item) => item.id), ['server'], 'the stale item is gone from the device after the merge');
}

/* 5. The quick-tap race: an item removed in this visit, not yet written, is not brought back by a pull. */
{
  reset();
  const storage = store();
  toggleHighlight(storage, 'me', CONTENT, { segment: 'p0', sentence: 'Sentence tap.' });
  const tapped = loadHighlights(storage, 'me', CONTENT)[0];
  serverState = { version: 6, cleared: false, highlights: [tapped, H('other')], notes: [], tombstones: [] };
  toggleHighlight(storage, 'me', CONTENT, { segment: 'p0', sentence: 'Sentence tap.' }); // the learner taps it off
  sync.noteRemoved(CONTENT, tapped.id);
  await sync.pullIntoDevice(storage, 'me', CONTENT); // a sentence sheet opens inside the debounce
  assert.deepEqual(loadHighlights(storage, 'me', CONTENT).map((item) => item.id), ['other'], 'the removal survived the pull');
}

/* 6. Nothing is touched while the deployment does not keep work with the account. */
{
  reset();
  records.useApi({ ...stub, accountBackbone: async () => ({ state: 'disabled' }) });
  const storage = store();
  toggleHighlight(storage, 'me', CONTENT, { segment: 'p0', sentence: 'Sentence local.' });
  serverState = { version: 2, cleared: false, highlights: [], notes: [], tombstones: [loadHighlights(storage, 'me', CONTENT)[0].id] };
  assert.equal(await sync.pullIntoDevice(storage, 'me', CONTENT), false);
  assert.equal(loadHighlights(storage, 'me', CONTENT).length, 1, 'the device keeps its copy');
  records.useApi(stub);
}

console.log('Annotation removals: tombstones drop stale items, a stale write is re-read and merged without re-adding, the device follows, the quick-tap race holds: PASS');
