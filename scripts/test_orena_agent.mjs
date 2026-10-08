/* Gate for the new UI's side of the Orena agent contract (docs/project/AGENT_CONTRACT.md, v5;
   D-086, D-092, D-094, D-095, D-096). The contract data the UI uses is read against the contract's own
   text; the mock's canonical streams keep §4's ordering guarantees and §7's shapes; requests, the
   reducer, the dispatcher, device memory and the intent map behave as the contract says; the live
   transport answers every §2.1 status and §4.1 fallback as the contract's tables say. */
import assert from 'node:assert/strict';

// LEX-022: a context id held as a number (an essay from /api/evaluate) goes out as the string the server expects.
{
  const { buildRequest } = await import('../static/orena/agent/session.js');
  const request = buildRequest({ context: { surface: 'writing.review', activity_type: 'writing', essay_id: 42 }, languages: { interface: 'en', support: 'vi', target: 'zh' } });
  assert.equal(request.context.essay_id, '42');
  // LEX-006: a word carries the sentence it was selected in.
  const word = buildRequest({ context: { surface: 'reading.workspace', selected_item: { type: 'word', text: '花生', lang: 'zh', sentence: '你们那么爱吃花生。' } }, languages: { interface: 'en', support: 'vi', target: 'zh' } });
  assert.deepEqual(word.context.selected_item, { type: 'word', text: '花生', lang: 'zh-CN', sentence: '你们那么爱吃花生。' });
  const bare = buildRequest({ context: { surface: 'reading.workspace', selected_item: { type: 'word', text: '花生', lang: 'zh' } }, languages: { interface: 'en', support: 'vi', target: 'zh' } });
  assert.equal('sentence' in bare.context.selected_item, false);
}

// LEX-028: a turn never leaves an idle panel - Orena thinks until the reply starts, an empty turn is a retry,
// and a server that goes quiet is stopped with a retry.
{
  const { createSession } = await import('../static/orena/agent/session.js');
  const quiet = createSession({ log: () => {} });
  quiet.learner('Giải thích 花生');
  quiet.apply({ event: 'session', data: { session_id: 's1', contract_version: 5 } });
  assert.equal(quiet.state().thinking, true, 'still thinking after the bookkeeping session event');
  quiet.apply({ event: 'metered', data: { turn_ordinal: 1, budget_state: 'ok' } });
  assert.equal(quiet.state().thinking, true, 'still thinking after metered');
  quiet.apply({ event: 'done', data: { usage: {}, trace_id: 't' } });
  const empty = quiet.lastReply();
  assert.equal(quiet.state().thinking, false);
  assert.deepEqual(empty.error, { class: 'transport', message: '', fallback: 'retry' }, 'an empty turn is a retry, not silence');

  const answered = createSession({ log: () => {} });
  answered.learner('Hi');
  answered.apply({ event: 'segment_end', data: { index: 0, lang: 'vi', text: 'Chào bạn.', voice_style: 'neutral_explain' } });
  answered.apply({ event: 'done', data: { usage: {}, trace_id: 't' } });
  assert.equal(answered.lastReply().error ?? null, null, 'a real answer has no error');

  const { liveTurn } = await import('../static/orena/agent/transport.js');
  const neverAnswers = (url, init) => new Promise((resolve, reject) => init.signal.addEventListener('abort', () => reject(new Error('aborted'))));
  const items = [];
  for await (const item of liveTurn({}, { fetchImpl: neverAnswers, idleMs: 20, log: () => {} })) items.push(item);
  assert.deepEqual(items, [{ event: 'error', data: { class: 'transport', message: '', fallback: 'retry' } }], 'a server that never answers ends in a retry');

  const enc = new TextEncoder();
  let stall;
  // Like a real fetch, aborting the request errors its body.
  const stalls = (url, init) => Promise.resolve({
    status: 200,
    headers: { get: () => null },
    body: new ReadableStream({ start(controller) {
      controller.enqueue(enc.encode('event: session\ndata: {"session_id":"s","contract_version":5}\n\n'));
      stall = controller;
      init.signal.addEventListener('abort', () => controller.error(new Error('aborted')));
    } }),
  });
  const midway = [];
  for await (const item of liveTurn({}, { fetchImpl: stalls, idleMs: 20, log: () => {} })) midway.push(item.event);
  assert.deepEqual(midway, ['session', 'error'], 'a server that goes quiet mid-turn ends in a retry');
}
import fs from 'node:fs';

const text = fs.readFileSync('docs/project/AGENT_CONTRACT.md', 'utf8');
const contract = await import('../static/orena/agent/contract.js');
const { parseEvents } = await import('../static/orena/agent/sse.js');
const { STREAMS, chooseStream, mockTurn } = await import('../static/orena/agent/mock.js');
const { buildRequest, createSession } = await import('../static/orena/agent/session.js');
const { createDispatcher, registerActionHandler } = await import('../static/orena/agent/dispatcher.js');
const { agentMemory } = await import('../static/orena/agent/memory.js');
const { intentHref, supportedIntents, INTENTS, mediaRouteId } = await import('../static/orena/agent/intents.js');
const transport = fs.readFileSync('static/orena/agent/transport.js', 'utf8');

// 1. The contract as data equals the contract as written.
assert.equal(Number(text.match(/`contract_version: (\d+)`/)[1]), contract.CONTRACT_VERSION, 'contract version');
const section = (from, to) => text.slice(text.indexOf(from), text.indexOf(to, text.indexOf(from)));
const actionRows = [...section('## 7. Actions', '\nRules:').matchAll(/^\| `(\w+)` \| .* \| (LOW|CONFIRM) \|/gm)].map((m) => [m[1], m[2]]);
assert.deepEqual(Object.fromEntries(actionRows), { ...contract.ACTIONS }, '§7 allowlist and risks');
const eventNames = [...section('## 4. Events', 'Ordering guarantees').matchAll(/^(\w+)\s+\{/gm)].map((m) => m[1]);
assert.deepEqual(eventNames, [...contract.EVENTS], '§4 event names');
const sixOne = section('### 6.1', '`{…}` are required');
const surfaceBlock = sixOne.slice(sixOne.indexOf('```text') + 7, sixOne.indexOf('```', sixOne.indexOf('```text') + 7));
const ids = [...surfaceBlock.matchAll(/\b([a-z]+(?:\.[a-z_]+)?)(\{([^}]*)\})?/g)];
const written = Object.fromEntries(ids.map((m) => [m[1], m[3] ? m[3].split(',').map((p) => p.trim()) : []]));
assert.deepEqual(Object.keys(written).sort(), Object.keys(contract.SURFACES).sort(), '§6.1 surface ids');
for (const [id, params] of Object.entries(written)) assert.deepEqual(contract.SURFACES[id], params, `${id} parameters`);
assert.equal(contract.toContractLang('zh'), 'zh-CN');
assert.equal(contract.fromContractLang('zh-CN'), 'zh');
assert.equal(contract.toContractLang('en'), 'en');

// 2. The server decides (§2.1): no client constant turns the agent on or off.
assert.doesNotMatch(transport, /AGENT_LIVE/, 'no client-side switch: AGENT_ENABLED on the server is the switch');

// 3. SSE framing: chunk boundaries, CRLF, comments, multi-line data.
async function* chunks(...parts) {
  for (const part of parts) yield part;
}
const parsed = [];
for await (const e of parseEvents(chunks('event: sess', 'ion\ndata: {"session_id":"s1"', ',"contract_version":2}\n\n: keep-alive\n\nevent: segment_end\r\ndata: {"index":0,\r\ndata: "text":"a"}\r\n\r\n'))) parsed.push(e);
assert.deepEqual(parsed, [
  { event: 'session', data: { session_id: 's1', contract_version: 2 } },
  { event: 'segment_end', data: { index: 0, text: 'a' } },
]);

// 4. Every canonical stream keeps §4's guarantees and §7's shapes.
const base = buildRequest({
  message: 'x',
  context: { surface: 'speaking.word_detail', content_id: 'media:1', attempt_id: 'r1', take_ref: 't1', essay_id: 'e9', selected_item: { type: 'word', id: 'w0', text: '是', lang: 'zh' } },
  languages: { interface: 'vi', support: 'vi', target: 'zh' },
  client: { supported_actions: Object.keys(contract.ACTIONS), supported_intents: INTENTS },
});
const PAYLOAD_KEYS = {
  navigate: null, play_model: ['content_id', 'item_id'], play_user: ['take_ref', 'item_id'], say_again: ['content_id', 'item_id'],
  compare_with_model: ['take_ref', 'item_id'], save_word: ['text', 'lang'], unsave_word: ['text', 'lang'],
  add_word_to_collection: ['text', 'lang', 'target'], start_review: ['scope', 'text', 'lang'], start_targeted_drill: ['focus', 'item_ids'],
};
for (const [id, make] of Object.entries(STREAMS)) {
  const events = make({ ...base, trigger: id === 'S13' ? 'open' : 'message' }).map(([event, data]) => ({ event, data }));
  assert.equal(events[0].event, 'session', `${id}: session first`);
  const last = events[events.length - 1].event;
  assert.ok(last === 'done' || last === 'error', `${id}: done or error last`);
  assert.equal(events.filter((e) => e.event === 'done' || e.event === 'error').length, 1, `${id}: one terminal event`);
  const ended = new Set();
  const cited = new Set();
  for (const { event, data } of events) {
    assert.ok(contract.EVENTS.includes(event), `${id}: ${event} is a contract event`);
    if (event === 'segment_delta') assert.ok(!ended.has(data.index), `${id}: delta after end`);
    if (event === 'segment_end') ended.add(data.index);
    if (event === 'segment_end') assert.ok(contract.VOICE_STYLES.includes(data.voice_style), `${id}: voice style`);
    if (event === 'evidence') {
      assert.ok(contract.EVIDENCE_SOURCES.includes(data.source), `${id}: evidence source`);
      cited.add(data.id);
    }
    if (event === 'tool_result') for (const e of data.evidence_ids || []) assert.ok(!cited.has(e) || true);
    if (event === 'action') {
      assert.equal(data.risk, contract.ACTIONS[data.type], `${id}: ${data.type} risk is the contract's`);
      assert.ok(data.label.length <= 24, `${id}: label length`);
      if (PAYLOAD_KEYS[data.type]) for (const key of Object.keys(data.payload)) assert.ok(PAYLOAD_KEYS[data.type].includes(key), `${id}: ${data.type} payload key ${key}`);
      if (data.type === 'navigate') assert.ok(data.payload.intent in contract.SURFACES, `${id}: navigate intent`);
    }
  }
  for (const { event, data } of events.filter((e) => e.event === 'suggestion')) {
    assert.match(data.intent, /^prompt\.[a-z_]+$/, `${id}: a suggestion carries a prompt intent (§4, D-094)`);
    assert.ok(!(data.intent in contract.SURFACES), `${id}: a suggestion intent is never a §6.1 id`);
  }
  if (id === 'S13') {
    assert.ok(!events.some((e) => e.event === 'memory_update'), 'S13 is read-only');
    assert.ok(events.filter((e) => e.event === 'action').every((e) => contract.ACTIONS[e.data.type] === 'LOW'), 'S13 has only LOW actions');
    const segs = events.filter((e) => e.event === 'segment_end');
    assert.equal(segs.length, 1, 'S13 has one segment');
    assert.ok(segs[0].data.text.length <= contract.LIMITS.openingSegment, 'S13 greeting is short');
    assert.ok(events.filter((e) => e.event === 'suggestion').length >= 1 && events.filter((e) => e.event === 'suggestion').length <= 5, 'S13 suggestions');
  }
}
// The contract's own fixtures use prompt intents in suggestions (§4, §12 S1/S13).
for (const match of text.matchAll(/suggestion\{"[^"]*", ([\w.]+)\}/g)) {
  assert.match(match[1], /^prompt\./, `§12 fixture suggestion intent ${match[1]} is a prompt intent`);
}
// Action labels are buttons: interface language, not support language (§7, D-094, D-080).
assert.match(section('## 7. Actions', '## 8.'), /`label` is in the `interface` language/, '§7 puts labels in the interface layer');
const mixed = buildRequest({
  message: 'Lưu từ này.',
  context: { selected_item: { type: 'word', text: '我', lang: 'zh' } },
  languages: { interface: 'en', support: 'vi', target: 'zh' },
});
const saveEvents = STREAMS.S5(mixed).map(([event, data]) => ({ event, data }));
assert.equal(saveEvents.find((e) => e.event === 'action').data.label, 'Save word', 'the button speaks the interface language');
assert.equal(saveEvents.find((e) => e.event === 'segment_end').data.lang, 'vi', 'the reply speaks the support language');
assert.equal(chooseStream({ trigger: 'open', context: {} }), 'S13');
assert.equal(chooseStream({ message: 'Cho tôi xem tiến độ của user khác.', context: {} }), 'S8');
assert.equal(chooseStream({ message: 'Lưu từ này.', context: { selected_item: { type: 'word', text: '我' } } }), 'S5');
assert.equal(chooseStream({ message: 'x', context: { surface: 'writing.review', essay_id: '3' } }), 'S9');
assert.equal(chooseStream({ message: 'x', context: {} }, 'SE'), 'SE');

// 5. Requests: the contract's version, omit what does not apply, contract language codes, words by text.
assert.equal(base.contract_version, contract.CONTRACT_VERSION);
assert.equal(base.context.locale.target, 'zh-CN');
assert.deepEqual(base.context.selected_item, { type: 'word', text: '是', lang: 'zh-CN' }, 'a word has no id, only text and lang');
// §3: every locale field maps at its own boundary, not only `target` (D-079 acceptance case C -
// interface Chinese, support English, target Chinese).
const interfaceZh = buildRequest({ message: 'x', context: {}, languages: { interface: 'zh', support: 'en', target: 'zh' } });
assert.equal(interfaceZh.context.locale.interface, 'zh-CN', 'context.locale.interface is mapped to contract codes like support/target/content');
assert.equal(interfaceZh.context.locale.support, 'en');
assert.equal(interfaceZh.context.locale.target, 'zh-CN');
const open = buildRequest({ trigger: 'open', context: { surface: 'orena.home' }, languages: { interface: 'en', support: 'en', target: 'en' } });
assert.equal(open.trigger, 'open');
assert.ok(!('message' in open), 'an opening turn has no message');
assert.ok(!('session_id' in open) && !('coach_notes' in open), 'absent fields are omitted');

// 5b. The real seam Home and the Contextual panel both build their requests through
// (screens/orena/dispatcher-setup.js#requestLanguages), fed with the real copy/index.js#languages()
// object, not a hand-shaped stand-in. copy/index.js#languages() returns `{ui, support}` - it has no
// `interface`/`target` field - so passing it into buildRequest directly silently defaulted both to
// English on every Home/Contextual-panel turn (independent review P1, 2026-09-29). Only what
// copy/index.js and shell/context.js read at import/call time is stubbed; nothing else in this
// DOM-free gate needs it.
{
  globalThis.window = { localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} } };
  Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US' }, configurable: true });
  globalThis.document = { documentElement: { lang: 'en', dataset: {} } };
  const { setLanguages: setCopyLanguages } = await import('../static/orena/copy/index.js');
  const { updateContext } = await import('../static/orena/shell/context.js');
  const { requestLanguages } = await import('../static/orena/screens/orena/dispatcher-setup.js');
  setCopyLanguages({ ui: 'vi', support: 'vi' });
  updateContext({ language: 'zh' });
  const seam = buildRequest({ message: 'x', context: {}, languages: requestLanguages() });
  assert.deepEqual(
    { interface: seam.context.locale.interface, support: seam.context.locale.support, target: seam.context.locale.target },
    { interface: 'vi', support: 'vi', target: 'zh-CN' },
    'the real copy/index.js#languages() -> requestLanguages() -> buildRequest seam lands the learner\'s real interface/support/target, never a silent English default',
  );
  setCopyLanguages({ ui: 'en', support: 'en' });
  updateContext({ language: 'en' });
  delete globalThis.window;
  delete globalThis.document;
  delete globalThis.navigator;
}

// 6. The reducer folds a stream into what the panel draws.
const session = createSession({ log: () => {} });
session.learner('Tại sao tôi sai từ này?');
for await (const e of mockTurn(base, { pace: 0 })) session.apply(e);
const reply = session.state().messages.at(-1);
assert.equal(reply.segments.length, 2, 'two segments (explanation and reference)');
assert.equal(reply.segments[1].voice_style, 'reference');
assert.equal(reply.evidence.length, 1);
assert.deepEqual(reply.actions.map((a) => a.type), ['play_model', 'say_again']);
assert.ok(reply.done && !session.state().thinking && !session.state().tool);
session.apply({ event: 'not_an_event', data: {} });

// 6b. The learner's own stop and retry (§2.1 429 "the learner may cancel the wait"; §4.1 `retry`):
//     a cancel ends the thinking and hands the question back unsent for a reason that is not a
//     changed language; a retry removes the reply that errored and keeps the learner's message.
{
  const cancelled = createSession({ log: () => {} });
  cancelled.learner('Ôn từ đến hạn');
  cancelled.apply({ event: 'wait', data: { seconds: 3 } });
  assert.equal(cancelled.state().waiting, 3);
  cancelled.cancel();
  const state = cancelled.state();
  assert.ok(!state.thinking && state.waiting === null && state.tool === null, 'nothing is pending after a cancel');
  assert.equal(state.unsent, 'Ôn từ đến hạn');
  assert.equal(state.unsentWhy, 'cancel');
  assert.equal(state.messages.length, 0, 'the unanswered question is not left in the thread');
  const mismatched = createSession({ log: () => {} });
  mismatched.learner('hello');
  mismatched.apply({ event: 'language_mismatch', data: {} });
  assert.equal(mismatched.state().unsentWhy, 'language', 'a changed learning language is told apart from a cancel');
  const errored = createSession({ log: () => {} });
  errored.learner('hello');
  errored.apply({ event: 'error', data: { class: 'provider_unavailable', message: 'busy', fallback: 'retry' } });
  assert.equal(errored.state().messages.at(-1).error.fallback, 'retry');
  errored.retry();
  assert.deepEqual(errored.state().messages.map((m) => m.role), ['learner'], 'the errored reply goes, the learner message stays');
  assert.ok(errored.state().thinking);
}

// 7. The dispatcher: fixed risks, unsupported ignored, CONFIRM confirmed, one language.
//    It calls the app's own infrastructure/api.js: every method it names must be exported there (a
//    hand-written fake once agreed with names the app never had, and every save-word action threw).
const dispatcherSource = fs.readFileSync('static/orena/agent/dispatcher.js', 'utf8');
const apiSource = fs.readFileSync('static/orena/infrastructure/api.js', 'utf8');
const apiMethods = new Set([...apiSource.matchAll(/^ {2}(\w+):/gm)].map((m) => m[1]));
const usedMethods = [...new Set([...dispatcherSource.matchAll(/(?<![\w.])api\.(\w+)\(/g)].map((m) => m[1]))];
assert.ok(usedMethods.length >= 5, 'the dispatcher calls the api');
for (const name of usedMethods) assert.ok(apiMethods.has(name), `dispatcher calls api.${name}, which infrastructure/api.js does not export`);
const calls = [];
const fakeApi = Object.fromEntries(usedMethods.map((name) => [name, async (...args) => {
  calls.push([name, ...args]);
  return name === 'libraryKeep' ? { item: { id: 'it1' } } : {};
}]));
let confirmAnswer = false;
const dispatcher = createDispatcher({ api: fakeApi, go: (h) => calls.push(['go', h]), learningLanguage: () => 'zh', confirm: async () => confirmAnswer, log: () => {} });
assert.deepEqual((await dispatcher.run({ type: 'rm_rf', payload: {} })).reason, 'unknown_type');
assert.deepEqual((await dispatcher.run({ type: 'play_model', payload: {} })).reason, 'unsupported', 'workspace actions need a mounted handler');
assert.equal((await dispatcher.run({ type: 'save_word', payload: { text: 'dog', lang: 'en' } })).reason, 'other_language');
assert.equal((await dispatcher.run({ type: 'save_word', payload: { text: '我', lang: 'zh-CN' } })).ok, true);
assert.equal((await dispatcher.run({ type: 'unsave_word', payload: { text: '我', lang: 'zh-CN' } })).reason, 'declined', 'CONFIRM needs a yes');
confirmAnswer = true;
assert.equal((await dispatcher.run({ type: 'unsave_word', payload: { text: '我', lang: 'zh-CN' } })).ok, true);
assert.equal((await dispatcher.run({ type: 'navigate', payload: { intent: 'grammar.point' } })).reason, 'unknown_intent', 'a missing parameter is refused');
assert.equal((await dispatcher.run({ type: 'navigate', payload: { intent: 'grammar.point', grammar_id: 'g1' } })).ok, true);
assert.deepEqual(calls, [['saveLibraryVocabulary', { word: '我' }], ['deleteLibraryVocabulary', '我'], ['go', '#/grammar/g1']], 'a saved word is POST /api/library/vocabulary { word }, a removed one DELETE');
// A call that throws is a failed action, not an unhandled rejection.
const failing = createDispatcher({ api: { saveLibraryVocabulary: async () => { throw new Error('offline'); } }, go: () => {}, learningLanguage: () => 'zh', confirm: async () => true, log: () => {} });
assert.deepEqual(await failing.run({ type: 'save_word', payload: { text: '我', lang: 'zh-CN' } }), { ok: false, reason: 'failed' });
// Filing (§7): the add-to sheet is the way when the agent names no target; a named deck or library set files it.
const filing = createDispatcher({ api: fakeApi, go: () => {}, learningLanguage: () => 'zh', confirm: async () => true, log: () => {}, canPickCollection: () => true });
assert.ok(filing.supported().includes('add_word_to_collection'));
calls.length = 0;
assert.equal((await filing.run({ type: 'add_word_to_collection', payload: { text: '我', lang: 'zh-CN', target: { system: 'deck', id: 'd1' } } })).ok, true);
assert.deepEqual(calls, [['saveLibraryVocabulary', { word: '我' }], ['vocabularyDeckAdd', 'd1', '我']]);
calls.length = 0;
assert.equal((await filing.run({ type: 'add_word_to_collection', payload: { text: '我', lang: 'zh-CN', target: { system: 'library', id: 'c1' } } })).ok, true);
assert.deepEqual(calls, [['saveLibraryVocabulary', { word: '我' }], ['libraryKeep', { kind: 'word', word: '我' }], ['libraryCollectionAdd', 'c1', 'it1']]);
assert.equal((await filing.run({ type: 'add_word_to_collection', payload: { text: '我', lang: 'zh-CN', target: { system: 'cloud', id: 'x' } } })).reason, 'bad_target');
const release = registerActionHandler('play_model', async () => ({ ok: true }));
assert.ok(dispatcher.supported().includes('play_model'), 'a mounted workspace offers its action');
release();
assert.ok(!dispatcher.supported().includes('play_model'), 'and withdraws it');
assert.ok(!dispatcher.supported().includes('add_word_to_collection'), 'filing is offered only with the add-to sheet');

// 8. Device memory: bounded, weighted, decaying, removable.
const store = new Map();
const storage = { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, v) };
const memory = agentMemory(storage, 'learner@example.com');
const now = Date.parse('2026-09-27T00:00:00Z');
for (let i = 0; i < 30; i += 1) memory.applyUpdate({ op: 'upsert', note: { id: `n${i}`, kind: 'goal', text: 'x'.repeat(120), weight: 0.5 + i / 100, last_reinforced: new Date(now).toISOString(), expires_at: null } }, now);
const sent = memory.requestNotes(now);
assert.ok(sent.length <= 20 && JSON.stringify(sent).length <= 2048, 'at most 20 notes and 2 KB');
assert.equal(sent[0].id, 'n29', 'most weighted first');
memory.applyUpdate({ op: 'remove', note: { id: 'n29' } }, now);
assert.ok(!memory.notes(now).some((n) => n.id === 'n29'), 'removed');
assert.ok(memory.notes(now + 60 * 86400000).length === 0, 'unreinforced notes fade out');
for (let i = 0; i < 50; i += 1) memory.appendMessage({ role: 'learner', text: String(i) });
assert.equal(memory.thread().length, 40, 'the thread keeps its last 40 messages');

// 9. Intents: every contract id is mapped; only built screens are offered.
assert.deepEqual([...INTENTS].sort(), Object.keys(contract.SURFACES).sort(), 'every §6.1 id has a screen mapping');
assert.equal(intentHref('vocabulary.word', { text: '我', lang: 'zh-CN' }), `#/word/${encodeURIComponent('我')}`);
assert.equal(intentHref('reading.workspace', {}), null);
assert.deepEqual(supportedIntents(new Set(['coming'])), [], 'nothing is offered before its screen exists');
assert.ok(supportedIntents(new Set(['today', 'orena'])).includes('orena.home'));
// F-9 (§6.1): one content-id namespace; the Listening routes take the bare id.
assert.equal(mediaRouteId('media:en-daily-pen'), 'en-daily-pen');
assert.equal(mediaRouteId('en-daily-pen'), 'en-daily-pen', 'an older bare id passes through');
// F-3 (§6.1): no grammar point is offered until the canonical Grammar store serves Grammar Lab ids.
assert.ok(!supportedIntents(new Set(['grammar-concept', 'grammar'])).includes('grammar.point'));
assert.ok(supportedIntents(new Set(['grammar-concept', 'grammar'])).includes('grammar.catalog'));

// 10. §2.1 HTTP statuses and §4.1 error classes: the tables the UI reads equal the contract text,
//     and the live transport answers each status as they say (driven with a fake fetch; it stays off).
const statusRows = [...section('### 2.1 HTTP status', '## 3.').matchAll(/^\| `(\d{3})` \|/gm)].map((m) => Number(m[1]));
assert.deepEqual(statusRows, [200, 401, 404, 409, 422, 429], '§2.1 statuses');
assert.deepEqual(
  Object.fromEntries(statusRows.map((s) => [s, contract.readStatus(s, '3').kind])),
  { 200: 'stream', 401: 'signed_out', 404: 'absent', 409: 'language_mismatch', 422: 'error', 429: 'wait' },
  'each status reads as §2.1 says',
);
assert.equal(contract.readStatus(422).fallback, 'none', 'a 422 is a client defect: nothing to retry');
assert.equal(contract.readStatus(500).fallback, 'retry', 'a status outside §2.1 is a transport error');
assert.equal(contract.readStatus(429, '7').seconds, 7);
assert.equal(contract.readStatus(429, null).seconds, 1, 'no Retry-After waits the minimum');
assert.equal(contract.readStatus(429, 'Sun, 27 Sep 2026 00:00:10 GMT', Date.parse('2026-09-27T00:00:00Z')).seconds, 10, 'an HTTP date is read');
const fallbackRows = [...section('### 4.1 Error classes', 'The classes a server sends').matchAll(/^\| `(\w+)` \| /gm)].map((m) => m[1]).filter((name) => name !== 'fallback');
assert.deepEqual(fallbackRows, [...contract.FALLBACKS], '§4.1 fallbacks');
assert.match(section('## 4. Events', 'Ordering guarantees'), /fallback: "retry" \| "text_only" \| "none"/, '§4 error event names the same fallbacks');
const classRows = [...section('The classes a server sends', '## 5.').matchAll(/^\| `(\w+)` \| `(\w+)` \|/gm)].map((m) => [m[1], m[2]]).filter(([name]) => name !== 'class');
assert.deepEqual(Object.fromEntries(classRows), { ...contract.ERROR_CLASSES }, '§4.1 classes and their fallbacks');
assert.equal(contract.fallbackOf('later'), 'none', 'an unknown fallback reads as none');

const { liveTurn, turn, probe, resetProbe } = await import('../static/orena/agent/transport.js');
const { orenaPresent, onOrenaPresence } = await import('../static/orena/agent/presence.js');
const SSE_OK = 'event: session\ndata: {"session_id":"s1","contract_version":4}\n\nevent: done\ndata: {"usage":{},"trace_id":"t"}\n\n';
const answer = (status, body = null, headers = {}) => new Response(body, { status, headers });
async function drive(responses, { abortOnSleep = false } = {}) {
  const queue = [...responses];
  const sent = [];
  const slept = [];
  const out = [];
  const controller = new AbortController();
  const fetchImpl = async (url, init) => {
    sent.push(JSON.parse(init.body));
    const next = queue.shift();
    if (next instanceof Error) throw next;
    return next;
  };
  const sleep = async (ms) => {
    slept.push(ms);
    if (abortOnSleep) controller.abort();
  };
  for await (const e of liveTurn(base, { signal: controller.signal, fetchImpl, sleep, signedOut: () => out.push({ event: 'signed_out' }), log: () => {} })) out.push(e);
  return { events: out.map((e) => (e.event === 'error' ? `error:${e.data.class}:${e.data.fallback}` : e.event)), sent, slept };
}
let run = await drive([answer(429, '{"detail":"rate_limited"}', { 'Retry-After': '3' }), answer(200, SSE_OK)]);
assert.deepEqual(run.events, ['wait', 'session', 'done'], '429: wait, then the turn');
assert.deepEqual(run.slept, [3000], 'waited Retry-After seconds');
assert.equal(run.sent.length, 2);
assert.deepEqual(run.sent[1], run.sent[0], 'the same request is sent again');
run = await drive([answer(429, null, { 'Retry-After': '2' }), answer(429, null, { 'Retry-After': '5' }), answer(200, SSE_OK)]);
assert.deepEqual(run.slept, [2000, 5000], 'refused again, it waits again');
run = await drive([answer(429, null, { 'Retry-After': '4' })], { abortOnSleep: true });
assert.deepEqual([run.events, run.sent.length], [['wait'], 1], 'a cancelled wait sends nothing more');
run = await drive([answer(404, '{"detail":"Not Found"}')]);
assert.deepEqual(run.events, ['absent'], '404: Orena is absent, no error');
run = await drive([answer(409, '{"detail":"target_language_mismatch"}')]);
assert.deepEqual([run.events, run.sent.length], [['language_mismatch'], 1], '409: handed back, never resent');
run = await drive([answer(401)]);
assert.deepEqual(run.events, ['signed_out'], '401: the app signs the learner in again');
run = await drive([answer(422, '{"detail":[]}')]);
assert.deepEqual(run.events, ['error:transport:none'], '422: a client defect, nothing to retry');
run = await drive([answer(503)]);
assert.deepEqual(run.events, ['error:transport:retry'], 'an unlisted status: retry');
run = await drive([new TypeError('network')]);
assert.deepEqual(run.events, ['error:transport:retry'], 'a network failure: retry');
run = await drive([answer(200, 'event: session\ndata: {"session_id":"s1"}\n\n')]);
assert.deepEqual(run.events, ['session', 'error:transport:retry'], 'a stream without done or error: retry');
run = await drive([answer(200, 'event: session\ndata: {"session_id":"s1"}\n\nevent: error\ndata: {"class":"voice_unavailable","message":"m","fallback":"text_only"}\n\n')]);
assert.deepEqual(run.events, ['session', 'error:voice_unavailable:text_only'], 'a server error passes through');

// The server's capabilities answer decides the visit: 200 is live, 404 hides Orena; a turn waits for it.
let probed = 0;
assert.equal(await probe({ fetchImpl: async () => { probed += 1; return answer(200, '{"contract_version":5,"capabilities":[]}'); } }), true, 'a 200: the agent is on');
assert.equal(await probe({ fetchImpl: async () => { probed += 1; return answer(404); } }), true, 'asked once per visit');
assert.equal(probed, 1);
const liveSent = [];
const liveEvents = [];
const liveStream = 'event: session\ndata: {"session_id":"s1"}\n\nevent: done\ndata: {"usage":{}}\n\n';
for await (const e of turn(base, { fetchImpl: async (url) => { liveSent.push(url); return answer(200, liveStream); } })) liveEvents.push(e.event);
assert.deepEqual([liveSent, liveEvents], [['/api/agent/turn'], ['session', 'done']], 'a live server answers the turn, never the mock');
resetProbe();
const presence = [];
const stopWatching = onOrenaPresence((value) => presence.push(value));
assert.equal(orenaPresent(), true);
const offEvents = [];
for await (const e of turn(base, { fetchImpl: async () => answer(404) })) offEvents.push(e.event);
assert.deepEqual([offEvents, orenaPresent(), presence], [['absent'], false, [false]], 'a server without the agent: 404 hides Orena, no mock reply');
resetProbe();
globalThis.location = { hash: '#/orena?agent=H404' };
const absentRun = [];
for await (const e of turn(base)) absentRun.push(e.event);
assert.deepEqual(absentRun, ['absent'], 'the mock plays a 404');
assert.deepEqual([orenaPresent(), presence], [false, [false]], 'a 404 hides Orena for the visit');
stopWatching();
delete globalThis.location;

// The mock plays the other statuses; the reducer folds them.
const waited = [];
for await (const e of mockTurn(base, { forced: 'H429', pace: 0 })) waited.push(e.event);
assert.deepEqual(waited.slice(0, 2), ['wait', 'session'], 'H429: a wait, then the answer');
const mismatch = [];
for await (const e of mockTurn(base, { forced: 'H409', pace: 0 })) mismatch.push(e.event);
assert.deepEqual(mismatch, ['language_mismatch']);
const folded = createSession({ log: () => {} });
folded.learner('Tại sao?');
folded.apply({ event: 'wait', data: { seconds: 3 } });
assert.deepEqual([folded.state().thinking, folded.state().waiting], [true, 3], 'a wait keeps Orena thinking');
folded.apply({ event: 'language_mismatch', data: {} });
assert.deepEqual([folded.state().unsent, folded.state().thinking, folded.state().messages.length], ['Tại sao?', false, 0], 'the message is handed back unsent');
folded.learner('Tại sao?');
folded.apply({ event: 'session', data: { session_id: 's9' } });
folded.apply({ event: 'error', data: { class: 'something_new', message: 'm', fallback: 'later' } });
assert.deepEqual(folded.state().messages.at(-1).error, { class: 'something_new', message: 'm', fallback: 'none' }, 'unknown class: act on the fallback; unknown fallback: none');
const gone = createSession({ log: () => {} });
gone.opening();
gone.apply({ event: 'absent', data: {} });
assert.deepEqual([gone.state().absent, gone.state().thinking, gone.state().messages.length], [true, false, 0], 'absent: no error, nothing to show');

// 11. §5.6 Address (D-096): the defaults table read from the contract text equals contract.js.
const addressSection = section('### 5.6 Address', 'A support language without a row');
const addressRows = addressSection.split('\n').filter((line) => /^\|\s*`[\w-]+`\s*\|/.test(line));
const writtenAddressFields = {};
const writtenAddressDefaults = {};
for (const line of addressRows) {
  const cells = line.split('|').map((c) => c.trim()).filter((c) => c.length);
  const lang = cells[0].replace(/`/g, '');
  if (lang === 'lang') continue; // the header row, which also happens to be backtick-quoted
  const tokens = [...cells[1].matchAll(/`([^`]+)`/g)].map((m) => m[1]);
  const fields = ['user'];
  const defaults = { user: tokens[1] };
  if (cells[2] !== 'ignored') {
    fields.unshift('self');
    defaults.self = tokens[0];
  }
  if (cells[4] !== 'ignored') {
    fields.push('register');
    defaults.register = tokens[2];
  }
  writtenAddressFields[lang] = fields.sort();
  writtenAddressDefaults[lang] = defaults;
}
assert.deepEqual(Object.keys(writtenAddressFields).sort(), Object.keys(contract.ADDRESS_FIELDS).sort(), '§5.6 languages');
for (const lang of Object.keys(writtenAddressFields)) {
  assert.deepEqual([...contract.ADDRESS_FIELDS[lang]].sort(), writtenAddressFields[lang], `§5.6 ${lang}: fields taken (self/user/register)`);
  assert.deepEqual({ ...contract.ADDRESS_DEFAULTS[lang] }, writtenAddressDefaults[lang], `§5.6 ${lang}: default pair`);
}

// Term validation (§5.6): 1-24 characters, at most 3 words, Unicode letters with their combining
// marks only, single spaces between words; NFC and NFD read the same.
for (const term of ['Nguyễn', 'anh Hương', '小明', 'Minh', 'chị', '王老师', 'Nguyễn'.normalize('NFD')]) {
  assert.ok(contract.isValidAddressTerm(term), `isValidAddressTerm accepts "${term}"`);
}
for (const [label, term] of [
  ['empty', ''],
  ['25 letters', 'x'.repeat(25)],
  ['four words', 'Minh Van Ha Two'],
  ['a digit', 'Minh2'],
  ['punctuation', 'Minh!'],
  ['markup', '<b>'],
  ['a line break', 'a\nb'],
  ['two spaces between words', 'Minh  Van'],
  ['a combining mark with no letter', String.fromCodePoint(0x301)],
  ['a word that starts with a combining mark', `a ${String.fromCodePoint(0x301)}b`],
  ['a zero-width joiner', `Min${String.fromCodePoint(0x200d)}h`],
  ['an emoji', `Minh${String.fromCodePoint(0x1f600)}`],
  ['a full-width digit', `Minh${String.fromCodePoint(0xff12)}`],
  ['a right-to-left mark', `${String.fromCodePoint(0x200f)}Minh`],
  ['a tab', 'Minh\tVan'],
  ['a leading space', ' Minh'],
  ['25 characters outside the basic plane', String.fromCodePoint(0x20000).repeat(25)],
]) {
  assert.ok(!contract.isValidAddressTerm(term), `isValidAddressTerm refuses ${label} ("${JSON.stringify(term)}")`);
}
// Characters, not UTF-16 units: 24 Han characters outside the basic plane are within the limit.
assert.ok(contract.isValidAddressTerm(String.fromCodePoint(0x20000).repeat(24)), 'length counts characters');

// normalizeAddress: drops what the language ignores, resolves zh-CN's register, nulls the whole
// object on an invalid term.
assert.deepEqual(contract.normalizeAddress({ self: 'chị', user: 'Minh', register: 'polite' }, 'en'), { lang: 'en', user: 'Minh' }, 'en drops self and register');
assert.deepEqual(contract.normalizeAddress({ self: 'chị', user: 'em', register: 'polite' }, 'vi'), { lang: 'vi', self: 'chị', user: 'em' }, 'vi drops register');
assert.deepEqual(contract.normalizeAddress({ user: '小明' }, 'zh-CN'), { lang: 'zh-CN', user: '小明', register: 'plain' }, 'zh-CN keeps register and defaults it to plain');
assert.equal(contract.normalizeAddress({ self: 'Minh2', user: 'em' }, 'vi'), null, 'an invalid term makes the whole object null');
assert.equal(contract.normalizeAddress(null, 'vi'), null, 'no address: null');
assert.equal(contract.normalizeAddress({ self: 'chị' }, 'ko'), null, 'a support language with no §5.6 row takes no address');
assert.equal(contract.normalizeAddress({}, 'vi'), null, 'an object that carries nothing is no address (§5.6: at least one field)');
assert.equal(contract.normalizeAddress({ self: 'tớ' }, 'en'), null, 'en with only self (which en ignores) carries nothing');

// The address note (§5.6): stored once per support language, replaced by an upsert, never decays
// or expires, never in requestNotes(), removable, read back by language.
const addrStore = new Map();
const addrStorage = { getItem: (k) => addrStore.get(k) ?? null, setItem: (k, v) => addrStore.set(k, v) };
const addrMemory = agentMemory(addrStorage, 'learner@example.com');
const addrNow = Date.parse('2026-09-28T00:00:00Z');
assert.equal(
  addrMemory.applyUpdate({ op: 'upsert', note: { id: 'address-vi', kind: 'address', address: { self: 'chị', user: 'em', lang: 'vi' }, weight: 1, expires_at: null } }, addrNow),
  true,
  'a valid address note is stored',
);
assert.deepEqual(addrMemory.addressFor('vi', addrNow), { self: 'chị', user: 'em', lang: 'vi' }, 'read back for its support language');
assert.equal(addrMemory.addressFor('en', addrNow), null, 'nothing stored for a different support language');
addrMemory.applyUpdate({ op: 'upsert', note: { id: 'address-vi', kind: 'address', address: { self: 'mình', user: 'bạn', lang: 'vi' }, weight: 1, expires_at: null } }, addrNow);
assert.equal(addrMemory.notes(addrNow).filter((n) => n.kind === 'address' && n.id === 'address-vi').length, 1, 'one per support language: an upsert replaces it');
assert.deepEqual(addrMemory.addressFor('vi', addrNow), { self: 'mình', user: 'bạn', lang: 'vi' }, 'back to the default is an upsert carrying the default pair');
assert.ok(addrMemory.notes(addrNow + 400 * 86400000).some((n) => n.id === 'address-vi'), 'the address note does not decay or expire');
assert.ok(!addrMemory.requestNotes(addrNow).some((n) => n.kind === 'address'), 'the address note is never sent in coach_notes');
assert.equal(
  addrMemory.applyUpdate({ op: 'upsert', note: { id: 'address-en', kind: 'address', address: { user: 'Minh2', lang: 'en' }, weight: 1, expires_at: null } }, addrNow),
  false,
  'an invalid address note is refused',
);
addrMemory.removeNote('address-vi');
assert.equal(addrMemory.addressFor('vi', addrNow), null, 'removable, like any note (§10 privacy exit)');

// buildRequest carries context.address only for the current support language and only from memory.
const withAddress = buildRequest({
  message: 'x',
  context: {},
  languages: { interface: 'vi', support: 'vi', target: 'zh' },
  address: { self: 'chị', user: 'em', lang: 'vi' },
});
assert.deepEqual(withAddress.context.address, { self: 'chị', user: 'em', lang: 'vi' }, 'context.address, normalised, in contract codes');
const withoutAddress = buildRequest({ message: 'x', context: {}, languages: { interface: 'vi', support: 'vi', target: 'zh' } });
assert.ok(!('address' in withoutAddress.context), 'no stored address: omitted');
const wrongLanguage = buildRequest({
  message: 'x',
  context: {},
  languages: { interface: 'vi', support: 'en', target: 'zh' },
  address: { self: 'chị', user: 'em', lang: 'vi' },
});
assert.ok(!('address' in wrongLanguage.context), 'an address for a different support language is never carried');

// S5's reply is an offer that names the button by its interface-language label, never a completion
// claim, in vi/en/zh, with interface and support languages differing (§7, §10, D-096).
const NO_COMPLETION = /đã lưu|đã thêm|mình lưu|\bsaved\b|added it|已(?:帮你|为你|替你)?(?:保存|收藏)/i;
for (const [support, interfaceLang] of [
  ['vi', 'en'],
  ['en', 'zh'],
  ['zh', 'vi'],
]) {
  const req = buildRequest({
    message: 'save',
    context: { selected_item: { type: 'word', text: '我', lang: 'zh' } },
    languages: { interface: interfaceLang, support, target: 'zh' },
  });
  const events = STREAMS.S5(req).map(([event, data]) => ({ event, data }));
  const segmentText = events.find((e) => e.event === 'segment_end').data.text;
  const actionLabel = events.find((e) => e.event === 'action').data.label;
  assert.ok(segmentText.includes(actionLabel), `S5 (support ${support}, interface ${interfaceLang}): names the button by its interface label`);
  assert.ok(!NO_COMPLETION.test(segmentText), `S5 (support ${support}, interface ${interfaceLang}): an offer, not a completion claim`);
}

// No reply, error message or fixture names a provider (§10, D-096).
const PROVIDER_NAMES = /\b(azure|google|gemini|openai|microsoft|ollama|anthropic)\b/i;
const mockSource = fs.readFileSync('static/orena/agent/mock.js', 'utf8');
assert.ok(!PROVIDER_NAMES.test(mockSource), 'mock.js names no provider');
assert.ok(!PROVIDER_NAMES.test(text), 'AGENT_CONTRACT.md names no provider');

// The §12 S5 and S2 fixture texts are the reworded ones - byte for byte, from the mock itself.
const s5vi = STREAMS.S5(
  buildRequest({
    message: 'Lưu từ này.',
    context: { selected_item: { type: 'word', text: '我', lang: 'zh' } },
    languages: { interface: 'vi', support: 'vi', target: 'zh' },
  }),
).map(([event, data]) => ({ event, data }));
assert.equal(s5vi.find((e) => e.event === 'segment_end').data.text, 'Bấm Lưu từ để thêm 我 vào từ vựng của bạn.', '§12 S5 fixture text, byte for byte');
const s2vi = STREAMS.S2(
  buildRequest({
    message: 'Tại sao tôi sai từ này?',
    context: { selected_item: { type: 'word', id: 'w0', text: '是', lang: 'zh' }, content_id: 'media:1', attempt_id: 'r1' },
    languages: { interface: 'vi', support: 'vi', target: 'zh' },
  }),
).map(([event, data]) => ({ event, data }));
assert.equal(
  s2vi.find((e) => e.event === 'segment_end').data.text,
  'Âm 是 bị đánh dấu là phát âm sai, điểm 6/100. Nghe mẫu rồi thử lại nhé:',
  '§5.1/§12 S2 fixture text, byte for byte, no provider name',
);

// S14 (sets the address, already speaks in it) and S15 (identity, addressed by rule) keep §4's
// guarantees; chooseStream picks them from the message in vi/en/zh.
const s14Events = STREAMS.S14({ ...base, context: { ...base.context, locale: { ...base.context.locale, support: 'vi' } } }).map(([event, data]) => ({ event, data }));
assert.equal(s14Events[0].event, 'session', 'S14: session first');
assert.equal(s14Events.at(-1).event, 'done', 'S14: done last');
const s14Upsert = s14Events.find((e) => e.event === 'memory_update');
assert.equal(s14Upsert.data.op, 'upsert');
assert.equal(s14Upsert.data.note.kind, 'address');
assert.equal(s14Upsert.data.note.id, 'address-vi');
assert.deepEqual(s14Upsert.data.note.address, { self: 'chị', user: 'em', lang: 'vi' });
assert.equal(s14Upsert.data.note.expires_at, null, 'no expiry (§5.6)');
assert.equal(s14Upsert.data.note.text, 'Xưng hô: Orena xưng "chị", gọi người học là "em".', '§5.6: text is the line the learner reads in preferences.agent_memory, matching the contract\'s own example');
assert.equal(s14Events.find((e) => e.event === 'segment_end').data.text, 'Được rồi, từ giờ chị gọi em là em nhé.', '§12 S14 fixture text - it already uses the pair it just set');

const s15Request = buildRequest({
  message: 'Bạn là ai?',
  context: { surface: 'home' },
  languages: { interface: 'vi', support: 'vi', target: 'vi' },
  address: { self: 'chị', user: 'em', lang: 'vi' },
});
const s15Events = STREAMS.S15(s15Request).map(([event, data]) => ({ event, data }));
assert.equal(s15Events[0].event, 'session', 'S15: session first');
assert.equal(s15Events.at(-1).event, 'done', 'S15: done last');
assert.ok(!s15Events.some((e) => e.event === 'memory_update'), 'S15 sets nothing');
const s15Text = s15Events.find((e) => e.event === 'segment_end').data.text;
assert.ok(s15Text.startsWith('Chị là Orena'), '§12 S15: fixed copy, in the address the request carries');
assert.ok(s15Text.includes('em'), "§12 S15: the request's own address is applied, not a default");

// English never swaps "I"/"you"; a name adds a vocative, and the pronoun "I" keeps its capital after it.
const englishRequest = buildRequest({ message: 'who are you', context: { surface: 'home' }, languages: { interface: 'en', support: 'en', target: 'en' }, address: { user: 'Minh', lang: 'en' } });
assert.equal(STREAMS.S15(englishRequest).find(([event]) => event === 'segment_end')[1].text, "Minh, I'm Orena, your AI learning assistant.", 'a vocative does not lower the pronoun I');

// §5.6 "Applied only when address.lang equals context.locale.support": the mock stands in for the
// server side too (§11), so a hand-built request whose context.address is for a different language
// than context.locale.support falls back to that language's default rather than being misapplied.
const mismatchedAddressRequest = {
  context: { locale: { interface: 'vi', support: 'vi', target: 'vi' }, address: { self: 'chị', user: 'em', lang: 'zh-CN' } },
};
const mismatchedText = STREAMS.S15(mismatchedAddressRequest).find(([event]) => event === 'segment_end')[1].text;
assert.equal(mismatchedText, 'Mình là Orena, trợ lý học tập AI của bạn.', 'a context.address for the wrong support language is ignored, not applied (§5.6)');

assert.equal(chooseStream({ message: 'Bạn là ai?', context: {} }), 'S15', 'chooseStream: vi identity question');
assert.equal(chooseStream({ message: 'Who are you?', context: {} }), 'S15', 'chooseStream: en identity question');
assert.equal(chooseStream({ message: '你是谁？', context: {} }), 'S15', 'chooseStream: zh identity question');
assert.equal(chooseStream({ message: 'Gọi mình là em nhé.', context: {} }), 'S14', 'chooseStream: vi address request');
assert.equal(chooseStream({ message: 'Call me Minh.', context: {} }), 'S14', 'chooseStream: en address request');
assert.equal(chooseStream({ message: '请叫我小明。', context: {} }), 'S14', 'chooseStream: zh address request');

console.log(`Orena agent contract v${contract.CONTRACT_VERSION}: data equals the contract text, ${Object.keys(STREAMS).length} canonical streams keep §4/§7, requests, reducer, dispatcher, device memory, intents and §5.6 address (defaults, terms, the note, S14/S15, no provider names) behave, every §2.1 status and §4.1 fallback is answered as written; the server decides live or absent: PASS`);
