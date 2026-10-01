/* Deleting an import (D-107): the device side of the lifecycle.
   A deleted import leaves the device's lists at once and stays gone: a sync never brings it back, a deletion made on
   another device (the account's content-free tombstones) removes the device's copy, and no room opens it - a link or
   a file through the media resolver, a text through its route. A stub fetch stands in for the network. */
import assert from 'node:assert/strict';
import crypto from 'node:crypto';

const dataset = {};
globalThis.document = { documentElement: { dataset, lang: 'en' } };
globalThis.location = { href: '' };
globalThis.window = { localStorage: null, addEventListener() {}, matchMedia: () => ({ matches: false, addEventListener() {} }) };

const calls = [];
let account = { imports: [], deleted: [] };
let failDeletes = false;
let failList = false;
let failMedia = 0; // a status to answer the media delete with, or 0
globalThis.fetch = async (url, options = {}) => {
  const method = options.method || 'GET';
  if (method !== 'GET') calls.push([method, url]);
  if (failDeletes && method === 'DELETE') return { ok: false, status: 500, headers: { get: () => 'application/json' }, json: async () => ({ detail: { category: 'unavailable' } }) };
  if (failList && method === 'GET' && url.includes('/api/imports')) return { ok: false, status: 500, headers: { get: () => 'application/json' }, json: async () => ({ detail: { category: 'unavailable' } }) };
  if (failMedia && method === 'DELETE' && url.includes('/api/media/my/')) return { ok: false, status: failMedia, headers: { get: () => 'application/json' }, json: async () => ({ detail: { category: 'media_index_unavailable' } }) };
  const body = url.includes('/api/account-backbone') ? { state: 'active' }
    : url.includes('/api/imports') ? (method === 'DELETE' ? {} : account)
    : {};
  return { ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => body };
};
const store = () => {
  const data = {};
  return { getItem: (key) => data[key] ?? null, setItem: (key, value) => { data[key] = String(value); }, removeItem: (key) => { delete data[key]; } };
};

const { learnerMemory, setPlaceSink } = await import('../static/orena/product/memory.js');
const { isImportRemoved, isRemovedContent, importMemberId, setRemovedImports, activateRemovedScope } = await import('../static/orena/product/import-removed.js');
const { openMedia } = await import('../static/orena/product/media-source.js');
const records = await import('../static/orena/product/account-records.js');
const shell = await import('../static/orena/shell/context.js');
const { deleteOwnImport } = await import('../static/orena/product/import-delete.js');

setPlaceSink({ enter() {}, clear() {}, removeImport: (id) => records.removeImport(id), recordsFor: (id) => records.recordsFor(id) });
const ref = (form, reference) => crypto.createHash('sha256').update(`orena.import-ref:${form}:${reference}`).digest('hex');
const LINK = 'url:https://example.test/v';
const FILE = 'upload:upload-abc';
const TEXT = 'text:11111111-1111-4111-8111-111111111111';

/* 1. The membership id a route names. */
assert.equal(importMemberId(TEXT), TEXT);
assert.equal(importMemberId(`upload:${LINK}`), LINK);
assert.equal(importMemberId(`upload:${FILE}`), FILE);
assert.equal(importMemberId('media:en-daily-pen'), '', 'a curated lesson is not an import');
assert.equal(importMemberId('article:x'), '');

/* 2. The same hash the server keeps in a tombstone. */
assert.equal(await records.importRef(LINK), ref('url', 'https://example.test/v'));
assert.equal(await records.importRef(FILE), ref('upload', 'upload-abc'));
assert.equal(await records.importRef(TEXT), '', 'a text is matched by its own id, not a reference');

/* 3. Deleting here: gone from every list, marked, never opened, and never re-added by a sync. */
{
  calls.length = 0;
  const box = store();
  const memory = learnerMemory(box, 'me', 'en');
  activateRemovedScope(memory.scope);
  memory.value.imports.push({ id: TEXT, title: 'T', text: 'body', language: 'en', origin: 'imported', kind: 'text' });
  memory.addMedia({ id: LINK, title: 'A link', kind: 'video' });
  memory.addMedia({ id: FILE, title: 'A file', kind: 'audio' });
  memory.keep(TEXT);
  assert.equal(typeof (await deleteOwnImport(memory, LINK)), 'boolean', 'a deletion answers whether the account confirmed');
  assert.deepEqual(memory.value.mediaImports.map((item) => item.id), [FILE]);
  assert.equal(isImportRemoved(LINK), true);
  assert.equal(isRemovedContent(`upload:${LINK}`), true);
  assert.equal(isRemovedContent(`upload:${FILE}`), false);
  assert.equal(memory.mergeImports([{ id: LINK, title: 'A link', kind: 'video' }]), false, 'a sync never re-adds a deleted import');
  assert.deepEqual(memory.value.mediaImports.map((item) => item.id), [FILE]);
  assert.equal(learnerMemory(box, 'me', 'en').isRemoved(LINK), true, 'the deletion survives a reload');
  assert.equal(await deleteOwnImport(memory, 'media:en-daily-pen'), false, 'only the learner\'s own imports can be deleted');
  // importing it again later is a new decision
  assert.equal(memory.addMedia({ id: LINK, title: 'A link', kind: 'video' }), true);
  assert.equal(isImportRemoved(LINK), false);
}

/* 4. No room opens a deleted import: the media resolver refuses before it reaches any provider or API. */
{
  setRemovedImports([LINK, FILE]);
  let reached = 0;
  const api = { mediaMy: async () => { reached += 1; return {}; }, listeningLibraryLesson: async () => { reached += 1; return {}; } };
  for (const id of [LINK, FILE, 'upload-abc']) {
    await assert.rejects(() => openMedia(id, { api }), (error) => error.status === 404 && error.category === 'media_not_found', id);
  }
  assert.equal(reached, 0, 'nothing was fetched for a deleted import');
  setRemovedImports([]);
  await openMedia('upload:upload-abc', { api });
  assert.equal(reached, 1, 'a kept file opens');
}

/* 5. Learning of a deletion made elsewhere: the account's tombstones remove this device's copy; a live import is never reported. */
{
  calls.length = 0;
  records.forgetRecordState();
  const memory = learnerMemory(store(), 'me', 'en');
  activateRemovedScope(memory.scope);
  memory.value.imports.push({ id: TEXT, title: 'T', text: 'body', language: 'en', origin: 'imported', kind: 'text' });
  memory.addMedia({ id: LINK, title: 'A link', kind: 'video' });
  memory.addMedia({ id: FILE, title: 'A file', kind: 'audio' });
  account = {
    imports: [{ id: 'upload:55555555-5555-4555-8555-555555555555', form: 'upload', title: 'A file', text: '', url: '', mediaId: 'upload-abc', kind: 'audio', version: 1 }],
    deleted: [
      { id: TEXT, ref: '' },
      { id: 'url:44444444-4444-4444-8444-444444444444', ref: ref('url', 'https://example.test/v') },
      { id: 'upload:66666666-6666-4666-8666-666666666666', ref: ref('upload', 'upload-abc') }, // an older, deleted record of the file that is live again
    ],
  };
  assert.equal(await shell.syncImports(memory, 'en'), true);
  assert.equal(memory.value.imports.length, 0, 'the deleted text left this device');
  assert.deepEqual(memory.value.mediaImports.map((item) => item.id), [FILE], 'the deleted link left; the file the account holds live stayed');
  assert.equal(isImportRemoved(TEXT), true);
  assert.equal(isImportRemoved(LINK), true);
  assert.equal(isImportRemoved(FILE), false, 'an id the account still holds live is never reported deleted');
  assert.deepEqual(calls.filter((call) => call[0] === 'DELETE'), [], 'learning of a deletion sends nothing');
}

/* 6. A deletion this device made that the account has not heard yet is sent again - for the records this device
   deleted, by record id and version. */
const LINK_RECORD = '44444444-4444-4444-8444-444444444444';
const linkItem = (record, version, sequence = 10) => ({ id: `url:${record}`, form: 'url', title: 'A link', text: '', url: 'https://example.test/v', mediaId: '', kind: 'video', version, sequence });
{
  calls.length = 0;
  records.forgetRecordState();
  const memory = learnerMemory(store(), 'me', 'en');
  activateRemovedScope(memory.scope);
  account = { highWater: 10, imports: [linkItem(LINK_RECORD, 3)], deleted: [] };
  await shell.syncImports(memory, 'en'); // the device learns the record and its version
  assert.deepEqual(memory.value.mediaImports.map((item) => item.id), [LINK]);
  failDeletes = true; // offline: the delete cannot reach the account
  await deleteOwnImport(memory, LINK);
  failDeletes = false;
  assert.deepEqual(memory.debtFor(LINK).owed, [LINK_RECORD], 'the device remembers exactly which record it deleted');
  assert.equal(memory.debtFor(LINK).mark, 10, 'and the list position it had then');
  calls.length = 0;
  await shell.syncImports(memory, 'en');
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.deepEqual(memory.value.mediaImports, [], 'the account still holding it does not bring it back');
  const resent = calls.filter((call) => call[0] === 'DELETE').map((call) => call[1]);
  assert.equal(resent.length, 1, 'the unfinished deletion is sent again');
  assert.ok(resent[0].startsWith(`/api/imports/${LINK_RECORD}?`) && resent[0].endsWith('expectedVersion=3'), 'for that record, at that version');
  account = { highWater: 12, imports: [], deleted: [{ id: `url:${LINK_RECORD}`, ref: ref('url', 'https://example.test/v') }] };
  await shell.syncImports(memory, 'en');
  assert.equal(memory.debtFor(LINK), null, 'once the account no longer holds the record, nothing is owed');
}

/* 7. Another device kept the same link again after this one deleted it: a new record. This device must neither delete
   it nor hide it for ever. */
{
  calls.length = 0;
  records.forgetRecordState();
  const memory = learnerMemory(store(), 'me', 'en');
  activateRemovedScope(memory.scope);
  account = { highWater: 10, imports: [linkItem(LINK_RECORD, 3)], deleted: [] };
  await shell.syncImports(memory, 'en');
  failDeletes = true;
  await deleteOwnImport(memory, LINK);
  failDeletes = false;
  const REIMPORT = '77777777-7777-4777-8777-777777777777';
  account = { highWater: 20, imports: [linkItem(LINK_RECORD, 3, 10), linkItem(REIMPORT, 1, 20)], deleted: [] };
  calls.length = 0;
  await shell.syncImports(memory, 'en');
  await new Promise((resolve) => setTimeout(resolve, 20));
  const sent = calls.filter((call) => call[0] === 'DELETE').map((call) => call[1]);
  assert.equal(sent.length, 1);
  assert.ok(sent[0].includes(LINK_RECORD) && !sent[0].includes(REIMPORT), 'only the record this device deleted is deleted again');
  assert.equal(memory.isRemoved(LINK), false, 'the later re-import clears the removed marker of the device');
  assert.deepEqual(memory.value.mediaImports.map((item) => item.id), [LINK], 'and the re-import is listed here');
}

/* 8. An upload that never reached the account is still deleted from the server's store. */
{
  calls.length = 0;
  records.forgetRecordState();
  const memory = learnerMemory(store(), 'me', 'en');
  activateRemovedScope(memory.scope);
  await deleteOwnImport(memory, 'upload:upload-lonely');
  assert.deepEqual(calls.filter((call) => call[0] === 'DELETE').map((call) => call[1]), ['/api/media/my/upload-lonely']);
}

/* 9. Removed sets are per owner and language: building the memory of another language does not replace the room's. */
{
  const en = learnerMemory(store(), 'me', 'en');
  activateRemovedScope(en.scope);
  en.applyDeletions([LINK]);
  const zh = learnerMemory(store(), 'me', 'zh');
  assert.equal(isImportRemoved(LINK), true, 'constructing the zh memory did not clear the set of the en room');
  activateRemovedScope(zh.scope);
  assert.equal(isImportRemoved(LINK), false, 'the zh room has its own');
  activateRemovedScope(en.scope);
}


/* 10. A delete BEFORE the first list read of this session (offline at load, a failed first sync) is not lost: what the
   device had read in an earlier session (its list position) says which live records are the ones it deleted. */
const TEXT_RECORD = '11111111-1111-4111-8111-111111111111';
const textItem = (sequence) => ({ id: TEXT, form: 'text', title: 'T', text: 'body', url: '', version: 2, sequence });
const fileItem = (record, sequence) => ({ id: `upload:${record}`, form: 'upload', title: 'A file', text: '', url: '', mediaId: 'upload-abc', kind: 'audio', version: 1, sequence });
const textItemFor = (id, sequence) => ({ id, form: 'text', title: 'T', text: 'body', url: '', version: 2, sequence });
const deletesSent = () => calls.filter((call) => call[0] === 'DELETE' && call[1].startsWith('/api/imports/')).map((call) => call[1]);
const sessionStart = (position) => {
  records.forgetRecordState(); // a new page session: no record ids known yet
  const memory = learnerMemory(store(), 'me', 'en');
  activateRemovedScope(memory.scope);
  memory.setImportMark(position); // read in an earlier session
  return memory;
};
{
  // text
  calls.length = 0;
  const memory = sessionStart(10);
  memory.value.imports.push({ id: TEXT, title: 'T', text: 'body', language: 'en', origin: 'imported', kind: 'text' });
  failList = true; // the first list read fails; the learner deletes anyway
  await shell.syncImports(memory, 'en');
  await deleteOwnImport(memory, TEXT);
  assert.deepEqual(memory.debtFor(TEXT).owed, [TEXT_RECORD], 'a text record is owed whether or not its version was known');
  failList = false;
  account = { highWater: 10, imports: [textItem(4)], deleted: [] };
  await shell.syncImports(memory, 'en');
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.equal(memory.isRemoved(TEXT), true, 'the deletion is not reverted');
  assert.equal(memory.value.imports.length, 0);
  assert.equal(deletesSent().length, 1, 'and the account is told');
}
{
  // link: the record ids are unknown at deletion; the account holds the one made before the last read of the device
  calls.length = 0;
  const memory = sessionStart(10);
  memory.addMedia({ id: LINK, title: 'A link', kind: 'video' });
  failList = true;
  await shell.syncImports(memory, 'en');
  await deleteOwnImport(memory, LINK);
  failList = false;
  assert.deepEqual(memory.debtFor(LINK), { owed: [], mark: 10, media: false });
  account = { highWater: 10, imports: [linkItem(LINK_RECORD, 3, 8)], deleted: [] };
  await shell.syncImports(memory, 'en');
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.equal(memory.isRemoved(LINK), true, 'a record at or before the position of the device is the one it deleted: not reinstated');
  assert.equal(deletesSent().length, 1);
  assert.ok(deletesSent()[0].startsWith(`/api/imports/${LINK_RECORD}?`));
  // a record made after that position, by another device, is a re-import
  calls.length = 0;
  const REIMPORT2 = '88888888-8888-4888-8888-888888888888';
  account = { highWater: 25, imports: [linkItem(LINK_RECORD, 3, 8), linkItem(REIMPORT2, 1, 25)], deleted: [] };
  await shell.syncImports(memory, 'en');
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.equal(memory.isRemoved(LINK), false, 'the later record reinstates the import');
  assert.ok(deletesSent().every((url) => !url.includes(REIMPORT2)), 'and is never deleted');
}
{
  // upload, with the stored copy unreachable at first (503) and retried until it is confirmed
  calls.length = 0;
  const memory = sessionStart(10);
  memory.addMedia({ id: FILE, title: 'A file', kind: 'audio' });
  failList = true;
  failMedia = 503;
  await deleteOwnImport(memory, FILE);
  failList = false;
  assert.equal(memory.debtFor(FILE).media, true);
  account = { highWater: 10, imports: [fileItem('55555555-5555-4555-8555-555555555555', 7)], deleted: [] };
  await shell.syncImports(memory, 'en');
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.equal(deletesSent().length, 1, 'the account record is deleted');
  assert.equal(memory.debtFor(FILE).media, true, 'an unconfirmed stored copy stays owed (503 is not gone)');
  failMedia = 0;
  account = { highWater: 11, imports: [], deleted: [{ id: 'upload:55555555-5555-4555-8555-555555555555', ref: ref('upload', 'upload-abc') }] };
  await shell.syncImports(memory, 'en');
  assert.equal(memory.debtFor(FILE), null, 'confirmed: nothing is owed any more');
}
{
  // a failed list read learns, settles and reinstates nothing
  calls.length = 0;
  const memory = sessionStart(10);
  memory.addMedia({ id: LINK, title: 'A link', kind: 'video' });
  failList = true;
  await deleteOwnImport(memory, LINK);
  const before = JSON.stringify(memory.debtFor(LINK));
  assert.equal(await shell.syncImports(memory, 'en'), false);
  assert.equal(JSON.stringify(memory.debtFor(LINK)), before);
  failList = false;
}
/* 11. Reinstating an import keeps an older record unconfirmed delete owed. */
{
  calls.length = 0;
  const memory = sessionStart(10);
  memory.addMedia({ id: LINK, title: 'A link', kind: 'video' });
  failDeletes = true;
  account = { highWater: 10, imports: [linkItem(LINK_RECORD, 3, 8)], deleted: [] };
  await shell.syncImports(memory, 'en');
  await deleteOwnImport(memory, LINK);
  const R2 = '99999999-9999-4999-8999-999999999999';
  account = { highWater: 30, imports: [linkItem(LINK_RECORD, 3, 8), linkItem(R2, 1, 30)], deleted: [] };
  await shell.syncImports(memory, 'en');
  assert.equal(memory.isRemoved(LINK), false);
  assert.deepEqual(memory.debtFor(LINK).owed, [LINK_RECORD], 'the older record is still owed its delete (the send failed)');
  failDeletes = false;
}


/* 12. D-108.1 - Undo, never a confirmation: the import is hidden at once, nothing is sent or erased until the window
   ends, Undo restores it exactly, and a reload mid-window still deletes (Undo is no longer offered). */
const { deleteWithUndo, flushPendingDelete, pendingImportIds, onImportsChanged } = await import('../static/orena/product/import-undo.js');
const UNDO_TEXT = { id: 'text:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', title: 'A', text: 'one', language: 'en', origin: 'imported', kind: 'text' };
const UNDO_TEXT_B = { id: 'text:bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', title: 'B', text: 'two', language: 'en', origin: 'imported', kind: 'text' };
{
  calls.length = 0;
  records.forgetRecordState();
  const memory = sessionStart(10);
  memory.value.imports.push(UNDO_TEXT, UNDO_TEXT_B);
  memory.value.kept.push('text:zzz', UNDO_TEXT.id);
  memory.value.continuation.push({ id: UNDO_TEXT.id, title: 'A', place: { index: 1, total: 2 } });
  memory.value.expressions[UNDO_TEXT.id] = 'my words';
  const toasts = [];
  const timers = [];
  const realSetTimeout = globalThis.setTimeout;
  globalThis.setTimeout = (fn, ms) => { timers.push([fn, ms]); return timers.length; };
  const toast = (text, options) => toasts.push([text, options]);
  let notified = 0;
  const stop = onImportsChanged(() => { notified += 1; });
  assert.equal(deleteWithUndo(memory, UNDO_TEXT.id, { toast, text: 'Deleted from Orena', undoLabel: 'Undo' }), true);
  globalThis.setTimeout = realSetTimeout;
  assert.equal(timers.at(-1)[1], 4000, 'the window is the toast that offers an action');
  assert.equal(toasts.length, 1);
  assert.equal(typeof toasts[0][1].undo, 'function', 'the toast carries the Undo action');
  assert.deepEqual(pendingImportIds(), [UNDO_TEXT.id]);
  // hidden everywhere at once, unopenable, and nothing sent
  assert.deepEqual(memory.value.imports.map((item) => item.id), [UNDO_TEXT_B.id]);
  assert.equal(memory.value.kept.includes(UNDO_TEXT.id), false);
  assert.equal(memory.value.continuation.length, 0);
  assert.equal(isImportRemoved(UNDO_TEXT.id), true);
  assert.deepEqual(calls.filter((call) => call[0] === 'DELETE'), []);
  // a sync inside the window does not bring it back or commit it
  account = { highWater: 10, imports: [textItemFor(UNDO_TEXT.id, 4)], deleted: [] };
  await shell.syncImports(memory, 'en');
  assert.equal(memory.isStaged(UNDO_TEXT.id), true, 'still inside its window after a sync');
  assert.deepEqual(memory.value.imports.map((item) => item.id), [UNDO_TEXT_B.id]);
  assert.deepEqual(calls.filter((call) => call[0] === 'DELETE'), []);
  // Undo restores it exactly
  toasts[0][1].undo();
  assert.deepEqual(memory.value.imports.map((item) => item.id), [UNDO_TEXT.id, UNDO_TEXT_B.id], 'same place in its list');
  assert.deepEqual(memory.value.kept, ['text:zzz', UNDO_TEXT.id], 'same kept mark');
  assert.equal(memory.value.continuation[0].id, UNDO_TEXT.id, 'same saved place');
  assert.equal(memory.value.expressions[UNDO_TEXT.id], 'my words');
  assert.equal(isImportRemoved(UNDO_TEXT.id), false);
  assert.equal(memory.isStaged(UNDO_TEXT.id), false);
  assert.deepEqual(pendingImportIds(), []);
  assert.ok(notified >= 2, 'rooms are told so they repaint');
  assert.deepEqual(calls.filter((call) => call[0] === 'DELETE'), [], 'Undo needs no server revival: nothing was ever sent');
  // the window ends: the deletion is committed
  globalThis.setTimeout = (fn) => { timers.push([fn, 0]); return 0; };
  deleteWithUndo(memory, UNDO_TEXT.id, { toast, text: 'Deleted from Orena', undoLabel: 'Undo' });
  globalThis.setTimeout = realSetTimeout;
  await flushPendingDelete();
  assert.equal(memory.isStaged(UNDO_TEXT.id), false);
  assert.equal(memory.debtFor(UNDO_TEXT.id).owed.length, 1, 'now it is a real deletion owed to the account');
  stop();
}
{
  // a reload mid-window: the staged deletion is still committed (and Undo is not offered)
  calls.length = 0;
  records.forgetRecordState();
  const box = store();
  const first = learnerMemory(box, 'me', 'en');
  activateRemovedScope(first.scope);
  first.setImportMark(10);
  first.value.imports.push(UNDO_TEXT);
  assert.equal(first.stageRemoval(UNDO_TEXT.id), true);
  const reloaded = learnerMemory(box, 'me', 'en');
  activateRemovedScope(reloaded.scope);
  assert.equal(reloaded.isStaged(UNDO_TEXT.id), true);
  assert.equal(reloaded.value.imports.length, 0, 'still hidden after the reload');
  account = { highWater: 10, imports: [textItemFor(UNDO_TEXT.id, 4)], deleted: [] };
  await shell.syncImports(reloaded, 'en');
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.equal(reloaded.isStaged(UNDO_TEXT.id), false);
  assert.equal(deletesSent().length, 1, 'the deletion went to the account');
  assert.equal(reloaded.value.imports.length, 0);
}

/* 13. D-108.2 - the notes and highlights written on a deleted text leave this device when the deletion is real. */
{
  const dropped = [];
  setPlaceSink({ enter() {}, clear() {}, removeImport: (id) => records.removeImport(id), recordsFor: (id) => records.recordsFor(id), dropLocal: (id) => dropped.push(id) });
  const memory = sessionStart(10);
  memory.value.imports.push(UNDO_TEXT);
  assert.equal(memory.stageRemoval(UNDO_TEXT.id), true);
  assert.deepEqual(dropped, [], 'inside the Undo window nothing is dropped');
  await memory.commitRemoval(UNDO_TEXT.id);
  assert.deepEqual(dropped, [UNDO_TEXT.id]);
  memory.applyDeletions([UNDO_TEXT_B.id]);
  assert.deepEqual(dropped, [UNDO_TEXT.id, UNDO_TEXT_B.id], 'and a deletion learned from the account drops them too');
  setPlaceSink({ enter() {}, clear() {}, removeImport: (id) => records.removeImport(id), recordsFor: (id) => records.recordsFor(id) });
  // the shell hook empties the device stores of notes and highlights for that text
  const box = store();
  const hl = await import('../static/orena/screens/reader/highlights.js');
  const qs = await import('../static/orena/screens/quick-sheet/model.js');
  hl.toggleHighlight(box, 'me', UNDO_TEXT.id, { segment: 'p0', sentence: 'One.' });
  qs.addNote(box, 'me', `k:${UNDO_TEXT.id}`, { type: 'question', text: 'q', content: UNDO_TEXT.id });
  assert.equal(hl.loadHighlights(box, 'me', UNDO_TEXT.id).length, 1);
  await shell.dropLocalAnnotations(box, 'me', UNDO_TEXT.id);
  assert.equal(hl.loadHighlights(box, 'me', UNDO_TEXT.id).length, 0);
  assert.equal(qs.notesForContent(box, 'me', UNDO_TEXT.id).length, 0);
  await shell.dropLocalAnnotations(box, 'me', 'article:other'); // anything but a text import is untouched
}

/* 14. D-108.6 - the listing pages; the client reads every page of both lists. */
{
  const live = Array.from({ length: 7 }, (_, n) => ({ id: `url:${String(n).padStart(8, '0')}-0000-4000-8000-000000000000`, form: 'url', title: `L${n}`, text: '', url: `https://example.test/${n}`, mediaId: '', kind: 'video', version: 1, sequence: 100 - n }));
  const gone = Array.from({ length: 3 }, (_, n) => ({ id: `text:${String(n).padStart(8, '0')}-1111-4111-8111-111111111111`, ref: '', seq: 50 - n }));
  const asked = [];
  const realFetch = globalThis.fetch;
  globalThis.fetch = async (url, options = {}) => {
    if ((options.method || 'GET') === 'GET' && url.startsWith('/api/imports?')) {
      const q = new URL(url, 'http://x').searchParams;
      asked.push(url);
      const include = q.get('include');
      const after = (list, cursor, key) => (cursor == null ? list : list.filter((row) => key(row) < Number(cursor)));
      const pageOf = (list, size, key) => ({ rows: list.slice(0, size), next: list.length > size ? key(list[size - 1]) : null });
      const a = include === 'deleted' ? { rows: [], next: null } : pageOf(after(live, q.get('cursor'), (r) => r.sequence), 3, (r) => r.sequence);
      const b = include === 'imports' ? { rows: [], next: null } : pageOf(after(gone, q.get('deletedCursor'), (r) => r.seq), 2, (r) => r.seq);
      const body = { highWater: 100, imports: a.rows, nextCursor: a.next, deleted: b.rows.map(({ id, ref: r }) => ({ id, ref: r })), nextDeletedCursor: b.next };
      return { ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => body };
    }
    return realFetch(url, options);
  };
  records.forgetRecordState();
  const state = await records.pullImportState('en', []);
  globalThis.fetch = realFetch;
  assert.equal(state.ok, true);
  assert.equal(state.items.length, 7, 'every import arrives although a page holds three');
  assert.equal(new Set(state.items.map((item) => item.id)).size, 7);
  assert.deepEqual(state.deletedIds.sort(), gone.map((row) => row.id).sort(), 'and every tombstone, although a page holds two');
  assert.ok(asked.length >= 3, 'it paged');
  assert.ok(asked.slice(1).some((url) => url.includes('include=imports') || url.includes('include=deleted')), 'a finished list is no longer asked for');
}


/* 15. QA round 3, P2: a link deleted and imported again in the SAME session is kept again - as a new record - whatever this
   page remembered about the earlier one. */
setPlaceSink({ enter() {}, clear() {}, addImport: (item, options) => records.pushImport(item, options), removeImport: (id) => records.removeImport(id), recordsFor: (id) => records.recordsFor(id) });
const putsSent = () => calls.filter((call) => call[0] === 'PUT' && call[1].startsWith('/api/imports/'));
{
  // (a) the page still remembers a record for it (read before the deletion, or deleted elsewhere): the account is told
  calls.length = 0;
  records.forgetRecordState();
  const memory = sessionStart(10);
  account = { highWater: 10, imports: [linkItem(LINK_RECORD, 3, 8)], deleted: [] };
  await shell.syncImports(memory, 'en'); // the page learns record LINK_RECORD for LINK
  assert.deepEqual(memory.value.mediaImports.map((item) => item.id), [LINK]);
  account = { highWater: 12, imports: [], deleted: [{ id: `url:${LINK_RECORD}`, ref: ref('url', 'https://example.test/v') }] };
  await shell.syncImports(memory, 'en'); // deleted elsewhere: it leaves this device
  assert.deepEqual(memory.value.mediaImports, []);
  memory.addMedia({ id: LINK, title: 'A link', kind: 'video' }); // imported again, same session
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.equal(putsSent().length, 1, 'the new import is sent, not skipped as already kept');
  assert.deepEqual(memory.value.mediaImports.map((item) => item.id), [LINK]);
}
{
  // (b) deleted here and imported again at once, before the delete has even finished
  calls.length = 0;
  records.forgetRecordState();
  const memory = sessionStart(10);
  account = { highWater: 10, imports: [linkItem(LINK_RECORD, 3, 8)], deleted: [] };
  await shell.syncImports(memory, 'en');
  const deleting = deleteOwnImport(memory, LINK);
  memory.addMedia({ id: LINK, title: 'A link', kind: 'video' });
  await deleting;
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.equal(putsSent().length, 1, 'the second import is sent');
  assert.equal(memory.isRemoved(LINK), false);
  assert.deepEqual(memory.value.mediaImports.map((item) => item.id), [LINK]);
}
{
  // (c) opening an import that is already listed does not send it again
  calls.length = 0;
  records.forgetRecordState();
  const memory = sessionStart(10);
  memory.addMedia({ id: LINK, title: 'A link', kind: 'video' });
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.equal(putsSent().length, 1);
  memory.addMedia({ id: LINK, title: 'A link', kind: 'video' });
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.equal(putsSent().length, 1, 'a second open of the same import is not a second import');
}

/* 16. QA round 3, P2 (intermittent): offline at load, delete, reconnect, RELOAD - the deletion is not lost, for a text
   and for a link. */
{
  for (const [kind, id, item, live] of [
    ['text', TEXT, { id: TEXT, title: 'T', text: 'body', language: 'en', origin: 'imported', kind: 'text' }, textItemFor(TEXT, 4)],
    ['link', LINK, null, linkItem(LINK_RECORD, 3, 8)],
  ]) {
    calls.length = 0;
    records.forgetRecordState();
    const box = store();
    const first = learnerMemory(box, 'me', 'en');
    activateRemovedScope(first.scope);
    first.setImportMark(10); // an earlier session read the account
    if (item) first.value.imports.push(item);
    else first.addMedia({ id, title: 'A link', kind: 'video' });
    failList = true; // offline at load
    await shell.syncImports(first, 'en');
    failDeletes = true;
    await deleteOwnImport(first, id);
    failDeletes = false;
    // back online, but the page is reloaded before anything is resent: a new page, the same device storage
    calls.length = 0;
    records.forgetRecordState();
    failList = false;
    const reloaded = learnerMemory(box, 'me', 'en');
    activateRemovedScope(reloaded.scope);
    assert.equal(reloaded.isRemoved(id), true, `${kind}: still deleted after the reload`);
    assert.ok(reloaded.debtFor(id), `${kind}: the unconfirmed deletion survived the reload`);
    account = { highWater: 10, imports: [live], deleted: [] };
    await shell.syncImports(reloaded, 'en');
    await new Promise((resolve) => setTimeout(resolve, 20));
    assert.equal(reloaded.isRemoved(id), true, `${kind}: not reinstated`);
    assert.equal(deletesSent().length, 1, `${kind}: the account is told after the reload`);
    assert.equal((reloaded.value.imports.length + reloaded.value.mediaImports.length), 0, `${kind}: not listed again`);
  }
}

console.log('Import deletion: gone from the device at once, never re-added, learned from the account, never opened, retried: PASS');
