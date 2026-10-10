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

// D-16T: the conversation is a chain of short tokens. The client renews before the held token dies, brings the next
// socket up beside the old one, hands over when its setup completes, and ends only when no further token comes.
{
  const timers = [];
  const realSetTimeout = globalThis.setTimeout;
  const realClearTimeout = globalThis.clearTimeout;
  globalThis.setTimeout = (fn, ms) => { const timer = { fn, ms, live: true }; timers.push(timer); return timer; };
  globalThis.clearTimeout = (timer) => { if (timer && typeof timer === 'object') timer.live = false; };
  globalThis.document ??= { addEventListener() {}, removeEventListener() {} };
  globalThis.window ??= { addEventListener() {}, removeEventListener() {} };
  const { connectLiveVoice } = await import('../static/orena/agent/live-voice.js');
  const sockets = [];
  function FakeSocket(url) {
    this.url = url; this.readyState = 1; this.sent = []; this.closed = false;
    this.send = (text) => this.sent.push(JSON.parse(text));
    this.close = () => { this.closed = true; };
    sockets.push(this);
  }
  const posts = [];
  let extendAnswer = null;
  const fetchImpl = async (path, init) => {
    const body = JSON.parse(init.body);
    posts.push({ path, body, headers: init.headers });
    if (path === '/api/agent/voice/extend') {
      if (extendAnswer instanceof Error) throw extendAnswer;
      return extendAnswer.error
        ? { ok: false, status: extendAnswer.status, headers: { get: () => '' }, json: async () => ({ detail: extendAnswer.error }) }
        : { ok: true, json: async () => extendAnswer };
    }
    return { ok: true, json: async () => ({}) };
  };
  const live = (timer) => timer.live;
  const near = (timer, ms) => Math.abs(timer.ms - ms) < 2000; // a timer is set for what is left of a token's life
  const next = (ms) => timers.filter(live).find((timer) => near(timer, ms));
  const settle = () => new Promise((resolve) => realSetTimeout(resolve, 0));
  const closedReasons = [];
  const limits = [];
  try {
    const session = { voice_session_id: 'vs-1', chunk: 0, max_seconds: 120, renew_in: 108, connect: { url: 'wss://x', ephemeral_token: 't0', setup: { setup: { model: 'm' } } } };
    const link = connectLiveVoice(session, {
      audio: { input: {}, output: {} }, mediaDevices: {}, fetchImpl, WebSocketCtor: FakeSocket,
      onClosed: (reason) => closedReasons.push(reason), onLimit: (error) => limits.push(error),
    });
    assert.equal(sockets.length, 1);
    assert.ok(sockets[0].url.endsWith('access_token=t0'));
    assert.ok(next(120000), 'the held token ends the session at its own max_seconds');
    assert.ok(next(108000), 'the next chunk is asked for renew_in seconds after the token was minted');

    // renewal: the answer's socket opens beside the old one, but the old one carries the conversation until it is up
    extendAnswer = { chunk: 1, max_seconds: 120, renew_in: 108, connect: { url: 'wss://x', ephemeral_token: 't1', setup: { setup: { model: 'm' } } } };
    sockets[0].onmessage({ data: JSON.stringify({ sessionResumptionUpdate: { newHandle: 'h-1', resumable: true } }) });
    await settle();
    next(108000).fn();
    await settle();
    const asked = posts.find((p) => p.path === '/api/agent/voice/extend');
    assert.deepEqual(asked.body, { voice_session_id: 'vs-1', chunk: 1, resumption: 'h-1' }, 'the chunk wanted and the vendor handle to resume');
    assert.ok(asked.headers['X-Orena-Timezone'], "the day is the learner's");
    assert.equal(sockets.length, 2);
    assert.ok(sockets[1].url.endsWith('access_token=t1'));
    assert.equal(sockets[0].closed, false, 'the old socket stays until the new one is up');
    sockets[1].onopen();
    assert.deepEqual(sockets[1].sent[0], { setup: { model: 'm' } }, 'the new socket sends the locked setup first');
    sockets[1].onmessage({ data: JSON.stringify({ serverContent: { outputTranscription: { text: 'ignored while pending' } } }) });
    await settle();
    sockets[1].onmessage({ data: JSON.stringify({ setupComplete: {} }) });
    await settle();
    assert.equal(sockets[0].closed, true, 'handed over: the old socket is closed');
    sockets[0].onclose();
    assert.deepEqual(closedReasons, [], 'the retired socket closing does not end the session');
    assert.equal(timers.filter(live).filter((timer) => near(timer, 120000)).length, 1, 'one cap timer, for the new token');
    assert.ok(posts.every((p) => p.path !== '/api/agent/voice/end'), 'nothing was ended');

    // no message left: the held token plays out and the learner is told once
    extendAnswer = { status: 429, error: { category: 'quota_exhausted', message: 'm', retryable: false, context: { feature: 'orena.message', used: 20, limit: 20 } } };
    next(108000).fn();
    await settle();
    assert.equal(limits.length, 1);
    assert.equal(limits[0].status, 429);
    assert.equal(limits[0].category, 'quota_exhausted');
    assert.deepEqual(closedReasons, [], 'a refused renewal does not cut the conversation short');
    assert.equal(sockets.length, 2, 'no further socket');
    assert.ok(next(120000), 'the session ends when the token it holds dies');

    // the token held dies: the session ends, in the way it ends at the learner's tap, and tells the server
    next(120000).fn();
    await settle();
    assert.deepEqual(closedReasons, ['cap']);
    assert.ok(posts.some((p) => p.path === '/api/agent/voice/end'), 'ending tells the server, which mints nothing more');
    link.end('learner');
  } finally {
    globalThis.setTimeout = realSetTimeout;
    globalThis.clearTimeout = realClearTimeout;
  }
}

// The last chunk (or an unmetered session) has no renewal.
{
  const timers = [];
  const realSetTimeout = globalThis.setTimeout;
  globalThis.setTimeout = (fn, ms) => { const timer = { fn, ms }; timers.push(timer); return timer; };
  try {
    const { connectLiveVoice } = await import('../static/orena/agent/live-voice.js');
    const socket = function FakeSocket() { this.readyState = 0; this.close = () => {}; this.send = () => {}; };
    const link = connectLiveVoice(
      { voice_session_id: 'vs-2', chunk: 0, max_seconds: 900, renew_in: null, last: true, connect: { url: 'wss://x', ephemeral_token: 't', setup: {} } },
      { audio: { input: {}, output: {} }, mediaDevices: {}, fetchImpl: async () => ({ ok: true, json: async () => ({}) }), WebSocketCtor: socket },
    );
    assert.deepEqual(timers.map((timer) => timer.ms), [900000], 'one timer: the end of the only token');
    link.end('learner');
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

// D-16T: Orena's push-to-talk marks its transcription (`purpose`), so the server can refuse an exhausted learner before it
// transcribes; the speaking rooms send none.
{
  const seen = [];
  const realFetch = globalThis.fetch;
  globalThis.window ??= { location: { hash: '' }, addEventListener() {}, removeEventListener() {} };
  globalThis.document ??= { addEventListener() {}, removeEventListener() {} };
  globalThis.fetch = async (url, init) => {
    seen.push({ url, init });
    return { ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => ({ text: 'hi' }) };
  };
  try {
    const { api } = await import('../static/orena/infrastructure/api.js');
    const blob = new Blob(['x'], { type: 'audio/webm' });
    await api.transcribeSpeech(blob, '', 'orena-voice', { purpose: 'orena_voice' });
    await api.transcribeSpeech(blob, 'en');
    const [voice, room] = seen;
    assert.equal(voice.url, '/api/speech/transcribe');
    assert.equal(voice.init.body.get('purpose'), 'orena_voice');
    assert.ok(voice.init.headers['X-Orena-Timezone'], "the day the server checks is the learner's");
    assert.equal(room.init.body.get('purpose'), null, 'a speaking room sends no purpose');
    assert.equal(room.init.body.get('language'), 'en');
  } finally {
    globalThis.fetch = realFetch;
  }
}

console.log('Orena live voice (§9 mode A): session body, PCM16 codecs, thread writing, server refusals: PASS');
