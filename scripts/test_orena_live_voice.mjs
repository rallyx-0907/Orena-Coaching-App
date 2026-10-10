/* Gate for Orena's live voice client (AGENT_CONTRACT §9 mode A, R28): the session body, the PCM16 codecs and the
   thread a voice turn is written into. The socket itself is exercised in the browser check (a mocked vendor
   socket), not here. */
import assert from 'node:assert/strict';

globalThis.btoa ??= (text) => Buffer.from(text, 'binary').toString('base64');
globalThis.atob ??= (text) => Buffer.from(text, 'base64').toString('binary');

const { utteranceTracker, voiceSessionBody, toBase64, pcm16ToFloat, voiceThread, openVoiceSession, VoiceSessionError } = await import('../static/orena/agent/live-voice.js');
const { createSession } = await import('../static/orena/agent/session.js');

// A turn body without its message, at the contract version.
{
  const body = voiceSessionBody({ contract_version: 5, trigger: 'message', message: 'hi', session_id: 's', client: { ui_version: 'x' }, context: { surface: 'orena.home' }, coach_notes: [] });
  assert.deepEqual(Object.keys(body).sort(), ['client', 'coach_notes', 'context', 'contract_version', 'session_id']);
  assert.equal(body.contract_version, 5);
}

// PCM16 round trip: little-endian, signed.
{
  const samples = new Int16Array([0, 1000, -1000, 32767, -32768]);
  const back = pcm16ToFloat(toBase64(samples.buffer));
  assert.equal(back.length, 5);
  assert.ok(Math.abs(back[1] - 1000 / 32768) < 1e-6);
  assert.ok(Math.abs(back[2] + 1000 / 32768) < 1e-6);
  assert.equal(back[4], -1);
  const long = new Int16Array(100000).fill(7);
  assert.equal(pcm16ToFloat(toBase64(long.buffer)).length, 100000, 'a long frame encodes without a stack overflow');
}

// A voice turn joins the thread when Orena answers: the learner's words, Orena's words, the server's buttons.
{
  const session = createSession({ log: () => {} });
  const notes = [];
  let persisted = 0;
  const thread = voiceThread({ session, memory: { applyUpdate: (u) => notes.push(u) }, persist: () => { persisted += 1; }, lang: () => 'vi' });
  thread.done(); // nothing said: nothing written
  assert.equal(session.state().messages.length, 0);
  thread.events('lưu từ này', [{ event: 'action', data: { id: 'a1', type: 'save_word', label: 'Save' } }, { event: 'memory_update', data: { op: 'upsert' } }]);
  thread.text('lưu từ này', 'Mình đã chuẩn bị');
  thread.text('lưu từ này', 'Mình đã chuẩn bị nút lưu từ.');
  thread.done();
  const [learner, reply] = session.state().messages;
  assert.deepEqual(learner, { role: 'learner', text: 'lưu từ này' });
  assert.equal(reply.segments.length, 1, 'the growing transcript replaces itself, never piles up');
  assert.equal(reply.segments[0].text, 'Mình đã chuẩn bị nút lưu từ.');
  assert.equal(reply.segments[0].lang, 'vi');
  assert.equal(reply.actions[0].type, 'save_word');
  assert.equal(reply.done, true);
  assert.equal(notes.length, 1);
  assert.equal(persisted, 1);
}

// The server's refusals reach the caller with their status and category (the caller falls back to the cascade).
{
  const fail = (status, category) => async () => ({ ok: false, status, headers: { get: () => '7' }, json: async () => ({ detail: { category } }) });
  await assert.rejects(openVoiceSession({}, { fetchImpl: fail(503, 'voice_unavailable') }), (error) => error instanceof VoiceSessionError && error.status === 503 && error.category === 'voice_unavailable');
  await assert.rejects(openVoiceSession({}, { fetchImpl: fail(429, 'rate_limited') }), (error) => error.status === 429 && error.retryAfter === 7);
}

// D-16T (contract v8): voice is charged by duration. The session request carries the quota headers, and a 429
// quota_exhausted carries the server's own figures so the voice screen can tell the learner, not fall back.
{
  const seen = [];
  const exhausted = async (path, init) => {
    seen.push({ path, headers: init.headers });
    return {
      ok: false, status: 429, headers: { get: () => '3600' },
      json: async () => ({ detail: { category: 'quota_exhausted', message: 'm', retryable: false, context: { feature: 'orena.message', used: 20, limit: 20, resets_at: '2026-10-10T17:00:00Z', upgrade: '#/plan/pricing' } } }),
    };
  };
  await assert.rejects(
    openVoiceSession({ x: 1 }, { fetchImpl: exhausted, idempotencyKey: 'k-1' }),
    (error) => error instanceof VoiceSessionError && error.status === 429 && error.category === 'quota_exhausted'
      && error.context.used === 20 && error.context.limit === 20 && error.context.feature === 'orena.message' && error.retryAfter === 3600,
  );
  assert.equal(seen[0].path, '/api/agent/voice/session');
  assert.equal(seen[0].headers['Idempotency-Key'], 'k-1', 'one key per session the learner opens');
  assert.ok(seen[0].headers['X-Orena-Timezone'], "the device's timezone, so the day ends at the learner's midnight");
  assert.equal(seen[0].headers['Content-Type'], 'application/json');
  const { isQuotaExhausted, quotaMessage } = await import('../static/orena/screens/plan/quota-notice.js').catch(() => ({}));
  if (isQuotaExhausted) {
    const error = new VoiceSessionError(429, 'quota_exhausted', 0, { feature: 'orena.message', used: 20, limit: 20 });
    assert.equal(isQuotaExhausted(error), true, 'the voice screen reads it as the plan limit');
    assert.equal(isQuotaExhausted(new VoiceSessionError(429, 'rate_limited')), false, 'a rate limit stays a failed session');
    assert.equal(isQuotaExhausted(new VoiceSessionError(503, 'quota_unavailable')), false, 'an unreadable limit falls back as before');
    assert.ok(quotaMessage(error).includes('20'), 'the sentence carries the server\'s figures');
  }
}

// D-16T: the session ends by itself at `max_seconds` (the seconds the learner's remaining messages buy).
{
  const calls = [];
  const realSetTimeout = globalThis.setTimeout;
  globalThis.setTimeout = (fn, ms, ...rest) => { calls.push(ms); return realSetTimeout(() => {}, 0); };
  globalThis.document ??= { addEventListener() {}, removeEventListener() {} };
  globalThis.window ??= { addEventListener() {}, removeEventListener() {} };
  const { connectLiveVoice } = await import('../static/orena/agent/live-voice.js');
  try {
    const socket = function FakeSocket() { this.readyState = 0; this.close = () => {}; this.send = () => {}; };
    const link = connectLiveVoice(
      { voice_session_id: 'vs-1', connect: { url: 'wss://x', ephemeral_token: 't', setup: {} }, max_seconds: 120 },
      { audio: { input: {}, output: {} }, mediaDevices: {}, fetchImpl: async () => ({ ok: true, json: async () => ({}) }), WebSocketCtor: socket },
    );
    assert.ok(calls.includes(120 * 1000), 'the cap timer is the session\'s own max_seconds, not a fixed 900');
    link.end('cap');
  } finally {
    globalThis.setTimeout = realSetTimeout;
  }
}

// R29: the learner's voice rides in the session body; with none chosen, no field (the server's default).
{
  const { chosenVoice, chooseVoice } = await import('../static/orena/agent/live-voice.js');
  const store = new Map();
  const storage = { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, v) };
  assert.equal(chosenVoice(storage), '');
  chooseVoice('m-calm', storage);
  assert.equal(chosenVoice(storage), 'm-calm');
  assert.equal(voiceSessionBody({ trigger: 'message' }, { voice: 'm-calm' }).voice, 'm-calm');
  assert.equal('voice' in voiceSessionBody({ trigger: 'message' }), false);
}

// R30: the view a running conversation is told - the route's surface and ids, then a selection on top of it.
{
  const { setRouteView, setViewSelection, viewContext, onViewContext } = await import('../static/orena/shell/view-context.js');
  const seen = [];
  const stop = onViewContext((view) => seen.push(view));
  setRouteView({ intent: 'listening.workspace' }, { id: 'youtube-x' });
  assert.deepEqual(viewContext(), { surface: 'listening.workspace', content_id: 'media:youtube-x' });
  setViewSelection({ type: 'sentence', id: 's1', text: 'It tests.' });
  assert.equal(viewContext().selected_item.id, 's1');
  setRouteView({ intent: 'progress' }, {});
  assert.deepEqual(viewContext(), { surface: 'progress' }, 'a new route starts clean');
  setRouteView({ intent: 'writing.review' }, { id: '42' });
  assert.equal(viewContext().essay_id, '42');
  stop();
  assert.equal(seen.length, 4);
}

// Each utterance has its own identity, never its words: the same words twice are two; a tool call joins the open
// utterance; a closed utterance is never reopened - a tool call that arrives before the next utterance's transcript
// belongs to the next one.
{
  const t = utteranceTracker();
  assert.equal(t.forCall(), 'u1');
  assert.equal(t.forCall(), 'u1', 'a second call in the same utterance');
  assert.equal(t.close({ heard: 'yes', said: 'Right.' }), 'u1');
  assert.equal(t.forCall(), 'u2', 'the first call of the next utterance, before its transcript');
  assert.equal(t.open(), 'u2', 'its transcript then joins it');
  assert.equal(t.close({ heard: 'yes', said: 'Again.' }), 'u2', 'the same words are another utterance');
  assert.equal(t.close({ heard: '', said: 'Welcome.' }), null, 'a turn with no learner in it has no boundary');
  assert.deepEqual(t.transcript(), [
    { role: 'user', text: 'yes', utterance: 'u1' }, { role: 'assistant', text: 'Right.', utterance: 'u1' },
    { role: 'user', text: 'yes', utterance: 'u2' }, { role: 'assistant', text: 'Again.', utterance: 'u2' },
    { role: 'assistant', text: 'Welcome.' },
  ]);
}

console.log('Orena live voice (§9 mode A): session body, PCM16 codecs, thread writing, server refusals: PASS');
