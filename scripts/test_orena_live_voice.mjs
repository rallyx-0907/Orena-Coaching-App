/* Gate for Orena's live voice client (AGENT_CONTRACT §9 mode A, R28): the session body, the PCM16 codecs and the
   thread a voice turn is written into. The socket itself is exercised in the browser check (a mocked vendor
   socket), not here. */
import assert from 'node:assert/strict';

globalThis.btoa ??= (text) => Buffer.from(text, 'binary').toString('base64');
globalThis.atob ??= (text) => Buffer.from(text, 'base64').toString('binary');

const { voiceSessionBody, toBase64, pcm16ToFloat, voiceThread, openVoiceSession, VoiceSessionError } = await import('../static/orena/agent/live-voice.js');
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

console.log('Orena live voice (§9 mode A): session body, PCM16 codecs, thread writing, server refusals: PASS');
