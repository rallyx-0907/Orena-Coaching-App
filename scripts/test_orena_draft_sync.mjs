/* A Writing draft kept with the account - and never claimed kept there when
   it is not.

   draft-sync decides by versions: the text the device last agreed with the
   server, the version it agreed on, and what the server has now. These cases
   are the whole table, plus the lines it must hold: nothing is sent unless the
   account keeps work, typed words are never replaced silently, a version
   changed on another device is shown rather than merged, and a retry after a
   lost answer is the same operation. */
import assert from 'node:assert/strict';
import { learnerMemory } from '../static/orena/product/memory.js';
import {
  draftSync,
  forgetAccountWorkState,
  readAgreement,
  textDigest,
} from '../static/orena/product/draft-sync.js';
import { draftStatus, refreshDraftStatus } from '../static/orena/ui/patterns.js';
import { copy } from '../static/orena/ui/copy.js';

const store = () => {
  const data = {};
  return { data, getItem: (k) => data[k] ?? null, setItem: (k, v) => { data[k] = v; } };
};

function fakeServer({ state = 'active', drafts = {} } = {}) {
  const calls = [];
  const fail = (status, context) => Object.assign(new Error(String(status)), { status, context });
  return {
    calls,
    drafts,
    api: {
      accountBackbone: async () => ({ state }),
      draft: async (key) => {
        calls.push(['get', key]);
        if (!drafts[key]) throw fail(404);
        return { draft: { ...drafts[key] } };
      },
      saveDraft: async (key, body) => {
        calls.push(['put', key, body]);
        const current = drafts[key] || { version: 0, text: '', ops: {} };
        current.ops ||= {};
        if (current.ops[body.operationId]) return { status: 'replay', version: current.ops[body.operationId] };
        if (body.expectedVersion !== current.version)
          throw fail(409, { serverVersion: current.version, serverText: current.text, serverTask: '' });
        const version = current.version + 1;
        drafts[key] = { ...current, version, text: body.text, task: body.task, ops: { ...current.ops, [body.operationId]: version } };
        return { status: 'committed', version };
      },
    },
  };
}

const now = (fn) => fn(); // schedule immediately
const make = (server, memory, extra = {}) => {
  const seen = { where: [], elsewhere: [] };
  const sync = draftSync({
    api: server.api, memory, id: 'essay:6',
    onWhere: (w) => seen.where.push(w), onElsewhere: (o) => seen.elsewhere.push(o),
    schedule: now, cancel: () => {}, ...extra,
  });
  return { sync, seen };
};
const fresh = () => learnerMemory(store(), 'learner', 'en');

async function run() {
  // 1. The account does not keep work: nothing is asked for or sent, and the
  //    room keeps saying "on this device".
  for (const state of ['disabled', 'unavailable']) {
    forgetAccountWorkState();
    const server = fakeServer({ state });
    const memory = fresh();
    memory.write('essay:6', 'hello');
    const { sync, seen } = make(server, memory);
    assert.equal(await sync.open('hello'), null);
    sync.edit('hello there');
    assert.deepEqual(server.calls, [], `${state}: nothing sent`);
    assert.deepEqual(seen.where, ['device']);
    assert.equal(sync.active, false);
  }

  // 2. Nothing on the server yet: a draft already in the box is sent, and the
  //    device remembers what it agreed on.
  forgetAccountWorkState();
  let server = fakeServer();
  let memory = fresh();
  let { sync, seen } = make(server, memory);
  assert.equal(await sync.open('Dear Anna,'), null);
  assert.equal(server.drafts['essay:6'].text, 'Dear Anna,');
  assert.deepEqual(readAgreement(memory, 'essay:6'), { version: 1, digest: textDigest('Dear Anna,') });
  assert.ok(seen.where.includes('account'));

  // 3. Typing moves it on, one version per save.
  sync.edit('Dear Anna, thank you');
  await sync.flush();
  assert.equal(server.drafts['essay:6'].version, 2);

  // 4. Another device (same memory store would be another browser - a fresh
  //    one here) opens the piece with an empty box: the account's copy is the
  //    draft.
  const phone = fresh();
  ({ sync, seen } = make(server, phone));
  assert.equal(await sync.open(''), 'Dear Anna, thank you');
  assert.equal(readAgreement(phone, 'essay:6').version, 2);

  // 5. This device did not touch the text since it last agreed, the server
  //    moved on elsewhere: the server's text is the draft, nothing sent.
  server.drafts['essay:6'] = { ...server.drafts['essay:6'], version: 3, text: 'Dear Anna, thanks!' };
  const before = server.calls.length;
  ({ sync, seen } = make(server, phone));
  assert.equal(await sync.open('Dear Anna, thank you'), 'Dear Anna, thanks!');
  assert.equal(server.calls.filter((c) => c[0] === 'put').length, server.calls.slice(0, before).filter((c) => c[0] === 'put').length);

  // 6. Both moved: the other version is shown, not merged, not sent over.
  phone.write('essay:6', 'Dear Anna, thanks! See you');
  server.drafts['essay:6'] = { ...server.drafts['essay:6'], version: 4, text: 'Dear Anna, thanks! Bye' };
  ({ sync, seen } = make(server, phone));
  assert.equal(await sync.open('Dear Anna, thanks! See you'), null, 'the box is not replaced');
  assert.deepEqual(seen.elsewhere, [{ version: 4, text: 'Dear Anna, thanks! Bye' }]);
  sync.edit('Dear Anna, thanks! See you soon');
  await sync.flush();
  assert.equal(server.drafts['essay:6'].version, 4, 'nothing is sent while the learner has not chosen');

  // 6a. Keeping this one makes it the next version.
  await sync.keepHere('Dear Anna, thanks! See you soon');
  assert.equal(server.drafts['essay:6'].version, 5);
  assert.equal(server.drafts['essay:6'].text, 'Dear Anna, thanks! See you soon');

  // 6b. Or using that version takes it as the draft, and future edits follow.
  server.drafts['essay:6'] = { ...server.drafts['essay:6'], version: 6, text: 'From the laptop' };
  phone.write('essay:6', 'From the phone');
  ({ sync, seen } = make(server, phone));
  await sync.open('From the phone');
  assert.equal(sync.useElsewhere(), 'From the laptop');
  sync.edit('From the laptop, edited');
  await sync.flush();
  assert.equal(server.drafts['essay:6'].version, 7);

  // 7. A conflict discovered while typing is shown the same way.
  server.drafts['essay:6'] = { ...server.drafts['essay:6'], version: 8, text: 'Moved elsewhere' };
  sync.edit('Still typing here');
  await sync.flush();
  assert.deepEqual(seen.elsewhere.at(-1), { version: 8, text: 'Moved elsewhere' });

  // 8. A lost answer: the retry is the same operation and replays.
  forgetAccountWorkState();
  server = fakeServer();
  memory = fresh();
  const flaky = { ...server.api, lost: true };
  flaky.saveDraft = async (key, body) => {
    const answer = await server.api.saveDraft(key, body);
    if (flaky.lost) {
      flaky.lost = false;
      throw Object.assign(new Error('network'), { status: 0 });
    }
    return answer;
  };
  ({ sync, seen } = make({ api: flaky }, memory));
  await sync.open('');
  sync.edit('one');
  await sync.flush();
  assert.equal(seen.where.at(-1), 'device', 'an unanswered save says "on this device"');
  sync.edit('one');
  await sync.flush();
  const puts = server.calls.filter((c) => c[0] === 'put');
  assert.equal(puts.length, 2);
  assert.equal(puts[0][2].operationId, puts[1][2].operationId, 'same words, same version, same operation');
  assert.equal(server.drafts['essay:6'].version, 1, 'replayed, not written twice');
  assert.equal(seen.where.at(-1), 'account');

  // 9. The status says where, in both interface languages, and only the
  //    account says "account".
  for (const ui of ['en', 'zh']) {
    const ctx = { c: copy[ui], memory: fresh() };
    const html = draftStatus(ctx);
    assert.match(html, /data-where="device"/);
    assert.ok(html.includes(copy[ui].draftSaved));
    const node = { dataset: { state: 'saved', where: 'device' }, innerHTML: '' };
    refreshDraftStatus(node, ctx, 'account');
    assert.equal(node.dataset.where, 'account');
    assert.ok(node.innerHTML.includes(copy[ui].draftKeptAccount));
    refreshDraftStatus(node, ctx, 'device');
    assert.ok(node.innerHTML.includes(copy[ui].draftSaved));
    for (const key of ['draftKeptAccount', 'draftElsewhere', 'draftUseElsewhere', 'draftKeepHere'])
      assert.ok(copy[ui][key], `${ui}.${key}`);
  }
  console.log('draft sync: 9 groups passed');
}

run().catch((error) => {
  console.error(error);
  process.exit(1);
});
