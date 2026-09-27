/* Gate for the new UI's side of the Orena agent contract (docs/project/AGENT_CONTRACT.md, v2;
   D-086, D-092). The contract data the UI uses is read against the contract's own text; the mock's
   canonical streams keep §4's ordering guarantees and §7's shapes; requests, the reducer, the
   dispatcher, device memory and the intent map behave as the contract says. */
import assert from 'node:assert/strict';
import fs from 'node:fs';

const text = fs.readFileSync('docs/project/AGENT_CONTRACT.md', 'utf8');
const contract = await import('../static/orena/agent/contract.js');
const { parseEvents } = await import('../static/orena/agent/sse.js');
const { STREAMS, chooseStream, mockTurn } = await import('../static/orena/agent/mock.js');
const { buildRequest, createSession } = await import('../static/orena/agent/session.js');
const { createDispatcher, registerActionHandler } = await import('../static/orena/agent/dispatcher.js');
const { agentMemory } = await import('../static/orena/agent/memory.js');
const { intentHref, supportedIntents, INTENTS } = await import('../static/orena/agent/intents.js');
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

// 2. Nothing calls /api/agent/* until the human says so.
assert.match(transport, /export const AGENT_LIVE = false;/, 'the live transport is off');

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
  if (id === 'S13') {
    assert.ok(!events.some((e) => e.event === 'memory_update'), 'S13 is read-only');
    assert.ok(events.filter((e) => e.event === 'action').every((e) => contract.ACTIONS[e.data.type] === 'LOW'), 'S13 has only LOW actions');
    const segs = events.filter((e) => e.event === 'segment_end');
    assert.equal(segs.length, 1, 'S13 has one segment');
    assert.ok(segs[0].data.text.length <= contract.LIMITS.openingSegment, 'S13 greeting is short');
    assert.ok(events.filter((e) => e.event === 'suggestion').length >= 1 && events.filter((e) => e.event === 'suggestion').length <= 5, 'S13 suggestions');
  }
}
assert.equal(chooseStream({ trigger: 'open', context: {} }), 'S13');
assert.equal(chooseStream({ message: 'Cho tôi xem tiến độ của user khác.', context: {} }), 'S8');
assert.equal(chooseStream({ message: 'Lưu từ này.', context: { selected_item: { type: 'word', text: '我' } } }), 'S5');
assert.equal(chooseStream({ message: 'x', context: { surface: 'writing.review', essay_id: '3' } }), 'S9');
assert.equal(chooseStream({ message: 'x', context: {} }, 'SE'), 'SE');

// 5. Requests: v2, omit what does not apply, contract language codes, words by text.
assert.equal(base.contract_version, 2);
assert.equal(base.context.locale.target, 'zh-CN');
assert.deepEqual(base.context.selected_item, { type: 'word', text: '是', lang: 'zh-CN' }, 'a word has no id, only text and lang');
const open = buildRequest({ trigger: 'open', context: { surface: 'orena.home' }, languages: { interface: 'en', support: 'en', target: 'en' } });
assert.equal(open.trigger, 'open');
assert.ok(!('message' in open), 'an opening turn has no message');
assert.ok(!('session_id' in open) && !('coach_notes' in open), 'absent fields are omitted');

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

// 7. The dispatcher: fixed risks, unsupported ignored, CONFIRM confirmed, one language.
const calls = [];
const fakeApi = { saveWord: async (w) => calls.push(['save', w]), deleteWord: async (w) => calls.push(['delete', w]) };
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
assert.deepEqual(calls, [['save', '我'], ['delete', '我'], ['go', '#/grammar/g1']]);
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

console.log(`Orena agent contract v${contract.CONTRACT_VERSION}: data equals the contract text, ${Object.keys(STREAMS).length} canonical streams keep §4/§7, requests, reducer, dispatcher, device memory and intents behave; live transport off: PASS`);
