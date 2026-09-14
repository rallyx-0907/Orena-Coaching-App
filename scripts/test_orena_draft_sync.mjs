/* A Writing draft kept with the account - and never claimed kept there when
   it is not.

   A draft is a snapshot of the words and the task they answer. draft-sync
   decides by versions: the snapshot the device last agreed with the server,
   the version it agreed on, the saves it sent without hearing back, and what
   the server has now. These cases hold the lines it must keep: the task
   always travels with its words; "kept with your account" appears only for a
   snapshot the account is known to hold; a lost answer is recognised as this
   device's own write, never as another device; a version changed elsewhere is
   shown, not merged; and nothing is sent unless the account keeps work. */
import assert from 'node:assert/strict';
import { learnerMemory } from '../static/orena/product/memory.js';
import {
  draftSync,
  forgetAccountWorkState,
  readAgreement,
  snapshotDigest,
} from '../static/orena/product/draft-sync.js';
import { draftStatus, refreshDraftStatus } from '../static/orena/ui/patterns.js';
import { copy } from '../static/orena/ui/copy.js';

const store = () => {
  const data = {};
  return { data, getItem: (k) => data[k] ?? null, setItem: (k, v) => { data[k] = v; } };
};
const fresh = () => learnerMemory(store(), 'learner', 'en');
const fail = (status, context) => Object.assign(new Error(String(status)), { status, context });

/* An in-memory /api/drafts with the server's real rules: expected version,
   receipts by operation id (a retry replays), 409 with the server snapshot. */
function fakeServer({ state = 'active' } = {}) {
  const drafts = {};
  const calls = [];
  const behaviour = { loseNextAnswer: false, refuseNext: 0 };
  const api = {
    accountBackbone: async () => ({ state }),
    draft: async (key) => {
      calls.push(['get', key]);
      const d = drafts[key];
      if (!d) throw fail(404);
      return { draft: { text: d.text, task: d.task, version: d.version } };
    },
    saveDraft: async (key, body) => {
      calls.push(['put', key, { ...body }]);
      if (behaviour.refuseNext > 0) {
        behaviour.refuseNext -= 1;
        throw fail(503);
      }
      const d = drafts[key] || { version: 0, text: '', task: '', ops: {} };
      let answer;
      if (d.ops[body.operationId]) answer = { status: 'replay', version: d.ops[body.operationId] };
      else if (body.expectedVersion !== d.version)
        throw fail(409, { serverVersion: d.version, serverText: d.text, serverTask: d.task });
      else {
        const version = d.version + 1;
        drafts[key] = { version, text: body.text, task: body.task, ops: { ...d.ops, [body.operationId]: version } };
        answer = { status: 'committed', version };
      }
      if (behaviour.loseNextAnswer) {
        behaviour.loseNextAnswer = false;
        throw fail(0); // committed, but the answer never arrived
      }
      return answer;
    },
  };
  // Another device writing directly, as the server would see it.
  const writeElsewhere = (key, text, task) => {
    const d = drafts[key] || { version: 0, ops: {} };
    drafts[key] = { ...d, version: d.version + 1, text, task };
  };
  return { api, drafts, calls, behaviour, writeElsewhere };
}

const immediately = (fn) => fn();
function device(server, memory = fresh()) {
  const seen = { where: [], elsewhere: [] };
  const sync = draftSync({
    api: server.api, memory, id: 'essay:6',
    onWhere: (w) => seen.where.push(w), onElsewhere: (o) => seen.elsewhere.push(o),
    schedule: immediately, cancel: () => {},
  });
  return { sync, seen, memory, last: () => seen.where.at(-1) };
}
const puts = (server) => server.calls.filter((c) => c[0] === 'put');

async function run() {
  // 1. The account does not keep work: nothing asked for, nothing sent, and
  //    the room keeps saying "on this device".
  for (const state of ['disabled', 'unavailable']) {
    forgetAccountWorkState();
    const server = fakeServer({ state });
    const d = device(server);
    assert.equal(await d.sync.open({ text: 'hello', task: 'a letter' }), null);
    d.sync.edit({ text: 'hello there', task: 'a letter' });
    assert.deepEqual(server.calls, [], `${state}: nothing sent`);
    assert.deepEqual(d.seen.where, ['device']);
  }

  // 2. Empty server and an empty room: nothing is sent and nothing claims the
  //    account - a 404 is not an acknowledged save.
  forgetAccountWorkState();
  let server = fakeServer();
  let d = device(server);
  assert.equal(await d.sync.open({ text: '', task: '' }), null);
  assert.equal(puts(server).length, 0);
  assert.ok(!d.seen.where.includes('account'), 'no account claim for an empty 404');

  // 3. A failed first save never says "account"; the next save that is
  //    acknowledged does.
  server = fakeServer();
  server.behaviour.refuseNext = 1;
  d = device(server);
  d.memory.write('essay:6', 'Dear Anna,');
  await d.sync.open({ text: 'Dear Anna,', task: 'a letter' });
  await d.sync.flush();
  assert.ok(!d.seen.where.includes('account'), 'a refused first PUT is not an account save');
  assert.equal(d.last(), 'device');
  d.sync.edit({ text: 'Dear Anna, hi', task: 'a letter' });
  assert.equal(d.last(), 'device', 'pending until acknowledged');
  await d.sync.flush();
  assert.equal(d.last(), 'account');
  assert.deepEqual(
    { text: server.drafts['essay:6'].text, task: server.drafts['essay:6'].task },
    { text: 'Dear Anna, hi', task: 'a letter' },
  );

  // 4. The task follows its words to another device.
  const phone = device(server);
  assert.deepEqual(await phone.sync.open({ text: '', task: '' }), { text: 'Dear Anna, hi', task: 'a letter' });
  assert.equal(phone.last(), 'account', 'a read that shows the server holds it may say account');
  assert.equal(readAgreement(phone.memory, 'essay:6').digest, snapshotDigest({ text: 'Dear Anna, hi', task: 'a letter' }));
  // Changing only the task is a change of the draft, and it is sent whole.
  phone.sync.edit({ text: 'Dear Anna, hi', task: 'a complaint' });
  await phone.sync.flush();
  assert.equal(server.drafts['essay:6'].task, 'a complaint');
  assert.equal(server.drafts['essay:6'].text, 'Dear Anna, hi');

  // 5. A device that agreed on the old pair and did not change it takes the
  //    new pair - never the new words under its old task.
  const laptop = device(server, d.memory);
  assert.deepEqual(await laptop.sync.open({ text: 'Dear Anna, hi', task: 'a letter' }), {
    text: 'Dear Anna, hi', task: 'a complaint',
  });

  // 6. Both moved: the other pair is shown whole, not merged, not sent over.
  server.writeElsewhere('essay:6', 'Written on the phone', 'a thank-you note');
  const laptop2 = device(server, laptop.memory);
  assert.equal(await laptop2.sync.open({ text: 'Laptop words', task: 'a complaint' }), null);
  const shown = laptop2.seen.elsewhere.at(-1);
  assert.deepEqual({ text: shown.text, task: shown.task }, { text: 'Written on the phone', task: 'a thank-you note' });
  assert.notEqual(laptop2.last(), 'account');
  const before = puts(server).length;
  laptop2.sync.edit({ text: 'Laptop words, more', task: 'a complaint' });
  await laptop2.sync.flush();
  assert.equal(puts(server).length, before, 'nothing sent while the learner has not chosen');

  // 6a. "Use that version" takes the pair: words and task.
  assert.deepEqual(laptop2.sync.useElsewhere(), { text: 'Written on the phone', task: 'a thank-you note' });
  laptop2.sync.edit({ text: 'Written on the phone, edited', task: 'a thank-you note' });
  await laptop2.sync.flush();
  assert.deepEqual(
    { text: server.drafts['essay:6'].text, task: server.drafts['essay:6'].task },
    { text: 'Written on the phone, edited', task: 'a thank-you note' },
  );

  // 6b. "Keep this one" sends this device's pair as the next version.
  server.writeElsewhere('essay:6', 'Other device again', 'a poem');
  const laptop3 = device(server, laptop2.memory);
  await laptop3.sync.open({ text: 'Mine', task: 'my own task' });
  assert.equal(laptop3.seen.elsewhere.length, 1);
  const version = server.drafts['essay:6'].version;
  await laptop3.sync.keepHere({ text: 'Mine', task: 'my own task' });
  await laptop3.sync.flush();
  assert.equal(server.drafts['essay:6'].version, version + 1);
  assert.deepEqual(
    { text: server.drafts['essay:6'].text, task: server.drafts['essay:6'].task },
    { text: 'Mine', task: 'my own task' },
  );
  assert.equal(laptop3.last(), 'account');

  // 7. A lost answer, same words: the retry is the same operation and replays.
  forgetAccountWorkState();
  server = fakeServer();
  d = device(server);
  await d.sync.open({ text: '', task: '' });
  server.behaviour.loseNextAnswer = true;
  d.sync.edit({ text: 'one', task: '' });
  await d.sync.flush();
  assert.equal(d.last(), 'device', 'an unanswered save says "on this device"');
  d.sync.edit({ text: 'one', task: '' });
  await d.sync.flush();
  const [p1, p2] = puts(server).map((c) => c[2]);
  assert.equal(p1.operationId, p2.operationId, 'same snapshot, same version, same operation');
  assert.equal(server.drafts['essay:6'].version, 1, 'replayed, not written twice');
  assert.equal(d.last(), 'account');

  // 8. A lost answer while typing further (review P2): A commits, its answer
  //    is lost, the learner has moved on to B. A is this device's own
  //    predecessor - not another device - and B lands on top of it.
  forgetAccountWorkState();
  server = fakeServer();
  d = device(server);
  await d.sync.open({ text: '', task: '' });
  server.behaviour.loseNextAnswer = true;
  d.sync.edit({ text: 'A', task: 't' });
  await d.sync.flush();
  assert.equal(server.drafts['essay:6'].text, 'A');
  d.sync.edit({ text: 'A and B', task: 't' });
  await d.sync.flush();
  assert.deepEqual(d.seen.elsewhere, [], 'no false cross-device conflict');
  assert.equal(server.drafts['essay:6'].version, 2);
  assert.deepEqual(
    { text: server.drafts['essay:6'].text, task: server.drafts['essay:6'].task },
    { text: 'A and B', task: 't' },
    'B is never lost',
  );
  assert.equal(d.last(), 'account');
  const ops = puts(server).map((c) => c[2].operationId);
  assert.equal(new Set(ops).size, ops.length, 'A was written once; B is its own operation');

  // 8a. The same, across a reload: the unanswered save is remembered on the
  //     device, so reopening recognises it and sends what was typed after.
  forgetAccountWorkState();
  server = fakeServer();
  d = device(server);
  await d.sync.open({ text: '', task: '' });
  server.behaviour.loseNextAnswer = true;
  d.sync.edit({ text: 'A', task: 't' });
  await d.sync.flush();
  d.memory.write('essay:6', 'A then B');
  const reopened = device(server, d.memory);
  assert.equal(await reopened.sync.open({ text: 'A then B', task: 't' }), null);
  await reopened.sync.flush();
  assert.deepEqual(reopened.seen.elsewhere, []);
  assert.equal(server.drafts['essay:6'].text, 'A then B');
  assert.equal(server.drafts['essay:6'].version, 2);

  // 8b. But a save from another device after ours is still shown as such.
  forgetAccountWorkState();
  server = fakeServer();
  d = device(server);
  await d.sync.open({ text: '', task: '' });
  server.behaviour.loseNextAnswer = true;
  d.sync.edit({ text: 'A', task: '' });
  await d.sync.flush();
  server.writeElsewhere('essay:6', 'Phone', '');
  d.sync.edit({ text: 'A and B', task: '' });
  await d.sync.flush();
  assert.equal(d.seen.elsewhere.at(-1)?.text, 'Phone');
  assert.equal(server.drafts['essay:6'].text, 'Phone', 'the other device is not overwritten');

  // 9. The status says where, in both interface languages.
  for (const ui of ['en', 'zh']) {
    const ctx = { c: copy[ui], memory: fresh() };
    const html = draftStatus(ctx);
    assert.match(html, /data-where="device"/);
    assert.ok(html.includes(copy[ui].draftSaved));
    const node = { dataset: { state: 'saved', where: 'device' }, innerHTML: '' };
    refreshDraftStatus(node, ctx, 'account');
    assert.ok(node.innerHTML.includes(copy[ui].draftKeptAccount));
    refreshDraftStatus(node, ctx, 'device');
    assert.ok(node.innerHTML.includes(copy[ui].draftSaved));
    for (const key of ['draftKeptAccount', 'draftElsewhere', 'draftUseElsewhere', 'draftKeepHere', 'writingTask'])
      assert.ok(copy[ui][key], `${ui}.${key}`);
  }
  console.log('draft sync: 13 cases passed');
}

run().catch((error) => {
  console.error(error);
  process.exit(1);
});
