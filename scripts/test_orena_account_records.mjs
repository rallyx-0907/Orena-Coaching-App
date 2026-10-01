/* Records kept with the account (product/account-records.js; D4 I5, I6, I8-I10, I12). A stub api stands
   in for the network only: the device stays the cache, only an `active` deployment is written to, a 409
   on notes/highlights is unioned by id once, a removal stays removed, and nothing is uploaded in bulk. */
import assert from 'node:assert/strict';

globalThis.location = { href: '' };
const records = await import('../static/orena/product/account-records.js');
const draftSync = await import('../static/orena/product/draft-sync.js');

const calls = [];
let state = 'active';
let saveAnnotations = async () => ({ version: 1 });
let annotationsGet = async () => {
  const error = new Error('none');
  error.status = 404;
  throw error;
};
const stub = {
  accountBackbone: async () => ({ state }),
  annotations: async (id) => { calls.push(['get', id]); return annotationsGet(id); },
  saveAnnotations: async (id, body) => { calls.push(['put', id, body]); return saveAnnotations(id, body); },
  appendConversationTurn: async (key, body) => { calls.push(['turn', key, body]); return { head: body.expectedHead + 1 }; },
  conversationRecord: async () => ({
    conversation: {
      head: 2, title: 'Coffee', situation: 'At a cafe.', ended: false,
      turns: [
        { ordinal: 1, role: 'learner', id: 't1', text: 'Hi', origin: 'typed', reply_to: null, meaning: '', support: '' },
        { ordinal: 2, role: 'partner', id: 'reply-t1', text: 'Hello!', origin: 'generated', reply_to: 't1', meaning: 'Xin chào', support: 'vi' },
      ],
    },
  }),
  saveImport: async (id, body) => { calls.push(['import', id, body]); return { version: 1 }; },
  imports: async () => ({
    imports: [
      { id: 'text:11111111-1111-4111-8111-111111111111', form: 'text', title: 'Mine', text: 'body', url: '', version: 3 },
      { id: 'url:44444444-4444-4444-8444-444444444444', form: 'url', title: 'v', text: '', url: 'https://x.test/v', mediaId: '', kind: 'video', durationMs: 5000, thumbnailUrl: 'https://x.test/t.jpg', provider: 'x', version: 1 },
      { id: 'upload:55555555-5555-4555-8555-555555555555', form: 'upload', title: 'f', text: '', url: '', mediaId: 'stored-9', kind: 'audio', durationMs: null, thumbnailUrl: '', provider: '', version: 2 },
    ],
  }),
  deleteImport: async (id, op, version) => { calls.push(['delete', id, version]); return {}; },
  saveResponse: async (key, body) => { calls.push(['response', key, body]); return { version: 1 }; },
  attachProvenance: async (word, body) => { calls.push(['provenance', word, body]); return {}; },
};
records.useApi(stub);
const fresh = (next = 'active') => {
  state = next;
  draftSync.forgetAccountWorkState();
  records.forgetRecordState();
  calls.length = 0;
};

/* Nothing is written unless the deployment keeps work with the account. */
for (const off of ['disabled', 'unavailable']) {
  fresh(off);
  assert.equal(await records.pushAnnotations('reading:1', { highlights: [], notes: [] }), false);
  assert.equal(await records.pullAnnotations('reading:1'), null);
  assert.equal(await records.saveResponse({ kind: 'transfer', mode: 'paraphrase', answer: 'x' }), false);
  assert.equal(await records.appendConversationTurn('conversation:a', { id: 't', role: 'learner', text: 'x' }), false);
  assert.deepEqual(await records.pullImports('en'), []);
  assert.equal(await records.attachProvenance({ term: 'harbour', why: 'from_reading' }), false);
  assert.deepEqual(calls, [], `${off}: no request beyond the state question`);
}

/* Set union by id: the first list wins, removed ids stay removed. */
assert.deepEqual(records.unionById([{ id: 'a', v: 1 }], [{ id: 'a', v: 2 }, { id: 'b' }], new Set(['b'])), [{ id: 'a', v: 1 }]);

/* A stale write is unioned with the server's set once and written again; a removal is not brought back. */
fresh();
const H = (id) => ({ id, segment: `p${id}`, sentence: `Sentence ${id}.`, at: '' });
let putCount = 0;
saveAnnotations = async () => {
  putCount += 1;
  if (putCount === 1) {
    const error = new Error('conflict');
    error.status = 409;
    throw error;
  }
  return { version: 3 };
};
annotationsGet = async () => ({ annotation: { highlights: [H('server'), H('gone')], notes: [], cleared: false, version: 2 } });
records.noteRemoved('reading:1', 'gone');
assert.equal(await records.pushAnnotations('reading:1', { highlights: [H('mine')], notes: [] }), true);
const puts = calls.filter((call) => call[0] === 'put');
assert.equal(puts.length, 2);
assert.deepEqual(puts[1][2].highlights.map((item) => item.id).sort(), ['mine', 'server'], 'the union, minus what this learner removed');
assert.equal(puts[1][2].expectedVersion, 2, 'the retry carries the server version it just read');
saveAnnotations = async () => {
  const error = new Error('conflict');
  error.status = 409;
  throw error;
};
fresh();
assert.equal(await records.pushAnnotations('reading:2', { highlights: [H('a')], notes: [] }), false, 'a second conflict is given up on, quietly');

/* Bounds follow the server's. */
fresh();
saveAnnotations = async () => ({ version: 1 });
await records.pushAnnotations('reading:3', {
  highlights: Array.from({ length: 90 }, (_, n) => ({ ...H(String(n)), sentence: 'x'.repeat(500) })),
  notes: Array.from({ length: 130 }, (_, n) => ({ id: `n${n}`, key: 'k', type: 'essay', text: 'y'.repeat(700), at: '' })),
});
const bounded = calls.find((call) => call[0] === 'put')[2];
assert.equal(bounded.highlights.length, 80);
assert.ok(bounded.highlights.every((item) => item.sentence.length === 400));
assert.equal(bounded.notes.length, 120);
assert.ok(bounded.notes.every((item) => item.text.length === 600 && item.type === 'reflection'), 'an unknown note type becomes a reflection, never an invalid write');

/* Conversation turns are appended in order, each at the head the last one returned. */
fresh();
const first = records.appendConversationTurn('conversation:a', { id: 't1', role: 'learner', text: 'Hi' }, { title: 'Coffee', situation: 'At a cafe.' });
const second = records.appendConversationTurn('conversation:a', { id: 'reply-t1', role: 'partner', text: 'Hello', reply_to: 't1' });
assert.deepEqual(await Promise.all([first, second]), [true, true]);
assert.deepEqual(
  calls.filter((call) => call[0] === 'turn').map((call) => [call[2].expectedHead, call[2].id, call[2].replyTo]),
  [[0, 't1', null], [1, 'reply-t1', 't1']],
);
const restored = await records.loadConversation('conversation:a', 'en');
assert.equal(restored.turns.length, 2);
assert.equal(restored.turns[1].reply_to, 't1');
assert.equal(restored.turns[0].reply_to, null);
assert.equal(restored.turns[1].meaning, 'Xin chào');

/* Imports: a new text goes to the account under the id the device made; the account's come back. */
fresh();
assert.equal(await records.pushImport({ id: 'text:22222222-2222-4222-8222-222222222222', title: 'T', text: 'Body', kind: 'text' }), true);
assert.equal(calls[0][1], '22222222-2222-4222-8222-222222222222');
const pulled = await records.pullImports('en');
/* Named contract change: a url import is now a media membership the account keeps (it used to be ignored here). */
assert.deepEqual(pulled.map((item) => item.id), ['text:11111111-1111-4111-8111-111111111111', 'url:https://x.test/v', 'upload:stored-9'], 'texts as imports, links and files as media memberships in the own id scheme of the device');
assert.deepEqual(pulled[1], { id: 'url:https://x.test/v', title: 'v', kind: 'video', language: 'en', origin: 'imported', duration_ms: 5000, thumbnail_url: 'https://x.test/t.jpg', provider: 'x' });
assert.equal(pulled[2].duration_ms, undefined);
assert.equal(await records.removeImport('text:11111111-1111-4111-8111-111111111111'), true);
assert.equal(calls.at(-1)[2], 3, 'the delete carries the version the account holds');
assert.equal(await records.removeImport('text:33333333-3333-4333-8333-333333333333'), false, 'an import the account never held is not deleted there');

/* A media import (pasted link / uploaded file) goes to the account under a record id minted when it is kept. */
fresh();
const linkItem = { id: 'url:https://x.test/v', title: 'v', kind: 'video', duration_ms: 5000.4, thumbnail_url: 'https://x.test/t.jpg', provider: 'x' };
assert.equal(await records.pushImport(linkItem), true);
const [, linkUuid, linkBody] = calls[0];
assert.match(linkUuid, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
assert.deepEqual(linkBody, { operationId: linkBody.operationId, expectedVersion: 0, form: 'url', title: 'v', text: '', url: 'https://x.test/v', mediaId: '', kind: 'video', durationMs: 5000, thumbnailUrl: 'https://x.test/t.jpg', provider: 'x' });
assert.equal(await records.pushImport(linkItem), true);
assert.equal(calls.length, 1, 'opening an import again is not a second import');
assert.equal(await records.pushImport({ id: 'upload:stored-9', title: 'f', kind: 'audio' }), true);
assert.equal(calls[1][2].form, 'upload');
assert.equal(calls[1][2].mediaId, 'stored-9');
assert.equal(calls[1][2].durationMs, null);
assert.equal(await records.removeImport('upload:stored-9'), true, 'a media import is removed from the account by the record this device kept');
assert.equal(calls.at(-1)[1], calls[1][1]);
assert.equal(await records.pushImport({ id: 'upload:stored-9', title: 'f', kind: 'audio' }), true);
assert.notEqual(calls.at(-1)[1], calls[1][1], 'a removed membership can be kept again - under a new record, not the terminal one');
/* Two devices that kept the same link leave two records; removing the membership removes both. */
fresh();
await records.pullImports('en');
assert.equal(await records.removeImport('url:https://x.test/v'), true);
assert.deepEqual(calls.filter((call) => call[0] === 'delete').map((call) => call[1]), ['44444444-4444-4444-8444-444444444444']);
fresh('disabled');
assert.equal(await records.pushImport(linkItem), false);
assert.deepEqual(calls, [], 'nothing is sent while the deployment does not keep records');

/* A response is learner work with a bounded summary, never a score. */
fresh();
const coaching = { strengths: [{ quote: 'a', why: 'clear' }], fixes: [{ quote: 'b', instead: 'c', why: 'tense' }] };
assert.equal(await records.saveResponse({ kind: 'transfer', source: { kind: 'text', id: 'reading:14' }, mode: 'paraphrase', answer: '  My words. ', coaching, sentenceRef: '3' }), true);
const [, key, body] = calls[0];
assert.match(key, /^transfer:reading:14:[0-9a-f-]{36}$/);
assert.equal(body.answer, 'My words.');
assert.equal(body.expectedVersion, 0);
assert.equal(JSON.parse(body.coaching).fixes[0].instead, 'c');
assert.equal('score' in body, false);
assert.equal(records.compactCoaching({}), '');
assert.equal(records.compactCoaching({ strengths: [{ quote: 'x'.repeat(5000) }] }).length <= 4000, true);
assert.equal(await records.saveResponse({ kind: 'react', mode: 'react', answer: '   ' }), false, 'nothing to keep');

/* Where a kept word was met. */
fresh();
assert.equal(await records.attachProvenance({ term: 'harbour', why: 'from_reading', origin: 'reading:14', context: 'the harbour lights' }), true);
assert.deepEqual([calls[0][1], calls[0][2].reason, calls[0][2].sourceKind, calls[0][2].sourceId], ['harbour', 'from_reading', 'reading', 'reading:14']);
assert.equal(await records.attachProvenance({ term: 'harbour', why: 'because' }), false);

/* Keeping a word from a sheet records where it was met: the content, the kind and the sentence. */
fresh();
assert.equal(await records.keepProvenance({ term: 'boards', source: { kind: 'reading', content_id: 'article:734b' }, sentence: 'Workers replaced the boards.' }), true);
assert.deepEqual([calls[0][1], calls[0][2].reason, calls[0][2].sourceKind, calls[0][2].sourceId, calls[0][2].focus],
  ['boards', 'from_reading', 'reading', 'article:734b', 'Workers replaced the boards.']);
fresh();
await records.keepProvenance({ term: 'lantern', source: { kind: 'dictionary' }, sentence: 'x' });
assert.equal(calls[0][2].reason, 'looked_up', 'a source with no provenance reason is a look-up');
assert.equal(calls[0][2].sourceKind, '', 'and with no content there is no source to name');
fresh('disabled');
assert.equal(await records.keepProvenance({ term: 'boards', source: { kind: 'reading', content_id: 'a' }, sentence: 's' }), false);
assert.deepEqual(calls, [], 'nothing is sent while the deployment does not keep work with the account');

console.log('Account records client: inactive deployments write nothing, notes union once, removals stay removed, bounds, ordered turns, imports, responses, provenance: PASS');
