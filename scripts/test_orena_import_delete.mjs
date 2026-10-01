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
globalThis.fetch = async (url, options = {}) => {
  const method = options.method || 'GET';
  if (method !== 'GET') calls.push([method, url]);
  if (failDeletes && method === 'DELETE') return { ok: false, status: 500, headers: { get: () => 'application/json' }, json: async () => ({ detail: { category: 'unavailable' } }) };
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
const linkItem = (record, version) => ({ id: `url:${record}`, form: 'url', title: 'A link', text: '', url: 'https://example.test/v', mediaId: '', kind: 'video', version });
{
  calls.length = 0;
  records.forgetRecordState();
  const memory = learnerMemory(store(), 'me', 'en');
  activateRemovedScope(memory.scope);
  account = { imports: [linkItem(LINK_RECORD, 3)], deleted: [] };
  await shell.syncImports(memory, 'en'); // the device learns the record and its version
  assert.deepEqual(memory.value.mediaImports.map((item) => item.id), [LINK]);
  failDeletes = true; // offline: the delete cannot reach the account
  await deleteOwnImport(memory, LINK);
  failDeletes = false;
  assert.deepEqual(memory.owedRecords(LINK), [LINK_RECORD], 'the device remembers exactly which record it deleted');
  calls.length = 0;
  await shell.syncImports(memory, 'en');
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.deepEqual(memory.value.mediaImports, [], 'the account still holding it does not bring it back');
  const resent = calls.filter((call) => call[0] === 'DELETE').map((call) => call[1]);
  assert.equal(resent.length, 1, 'the unfinished deletion is sent again');
  assert.ok(resent[0].startsWith(`/api/imports/${LINK_RECORD}?`) && resent[0].endsWith('expectedVersion=3'), 'for that record, at that version');
  account = { imports: [], deleted: [{ id: `url:${LINK_RECORD}`, ref: ref('url', 'https://example.test/v') }] };
  await shell.syncImports(memory, 'en');
  assert.deepEqual(memory.owedRecords(LINK), [], 'once the account no longer holds the record, nothing is owed');
}

/* 7. Another device kept the same link again after this one deleted it: a new record. This device must neither delete
   it nor hide it for ever. */
{
  calls.length = 0;
  records.forgetRecordState();
  const memory = learnerMemory(store(), 'me', 'en');
  activateRemovedScope(memory.scope);
  account = { imports: [linkItem(LINK_RECORD, 3)], deleted: [] };
  await shell.syncImports(memory, 'en');
  failDeletes = true;
  await deleteOwnImport(memory, LINK);
  failDeletes = false;
  const REIMPORT = '77777777-7777-4777-8777-777777777777';
  account = { imports: [linkItem(LINK_RECORD, 3), linkItem(REIMPORT, 1)], deleted: [] };
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

console.log('Import deletion: gone from the device at once, never re-added, learned from the account, never opened, retried: PASS');
