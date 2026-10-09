/* The Speaking take lifecycle (capabilities/speaking-take.js): states, refusals before upload,
   whose failure it is, retry without re-recording, and no stale answer over a newer one. */
import assert from 'node:assert/strict';
import { createSpeakingTake, TAKE, MIN_TAKE_MS, failureOf } from '../static/orena/capabilities/speaking-take.js';

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

function fakeRecorder({ startOk = true, error = '' } = {}) {
  const calls = { start: 0, stop: 0, cleanup: 0, discard: 0 };
  return {
    calls,
    start: async () => (calls.start++, startOk),
    stop: async () => (calls.stop++, { blob: { size: 4000 }, url: 'blob:recorder' }),
    cleanup: () => calls.cleanup++,
    discard: () => calls.discard++,
    snapshot: () => ({ error }),
  };
}
const urls = { made: 0, revoked: [], createObjectURL() { return `blob:take-${++this.made}`; }, revokeObjectURL(url) { this.revoked.push(url); } };
const measured = (line) => ({ score_kind: 'measured', reference_text: line, recognized_text: line, pron_score: 80, accuracy_score: 80, words: [] });

function harness({ api, recorder = fakeRecorder(), keep = null } = {}) {
  let clock = 0;
  const seen = [];
  const take = createSpeakingTake({ api, recorder, language: 'en', now: () => clock, urls, keep, onChange: (state) => seen.push(state) });
  return { take, recorder, seen, advance: (ms) => (clock += ms), last: () => seen.at(-1) };
}

// Idle → recording → processing → result; the assessment is kept, the audio is not.
{
  const sent = [];
  const kept = [];
  const api = {
    assessPronunciation: async (blob, language, line) => (sent.push({ blob, language, line }), measured(line)),
    evaluateSpeaking: async (payload) => ({ evaluated: payload.transcript_text }),
    saveSpeakingAttempt: async (payload) => kept.push(payload),
  };
  const h = harness({ api, keep: { assetId: 'asset-1', segmentId: 'asset-1:000' } });
  assert.equal(await h.take.start(), true);
  assert.equal(h.last().phase, TAKE.RECORDING);
  h.advance(1500);
  await h.take.stop('Two cats slept.');
  await tick();
  assert.deepEqual(h.seen.map((s) => s.phase), [TAKE.RECORDING, TAKE.PROCESSING, TAKE.RESULT, TAKE.RESULT]);
  assert.equal(sent.length, 1);
  assert.equal(sent[0].line, 'Two cats slept.');
  assert.equal(h.last().kept, true);
  assert.equal(kept[0].segment_id, 'asset-1:000');
  assert.ok(!('blob' in kept[0]) && !JSON.stringify(kept[0]).includes('blob:'), 'no audio in the kept record');
  assert.match(h.take.takeUrl, /^blob:take-/, 'the take can be heard again from this tab only');
}

// A take that is too short is refused before anything is uploaded.
{
  let sent = 0;
  const h = harness({ api: { assessPronunciation: async () => (sent++, measured('x')) } });
  await h.take.start();
  h.advance(MIN_TAKE_MS - 1);
  await h.take.stop('Hello.');
  assert.equal(sent, 0);
  assert.deepEqual(h.last().error, { kind: 'too_short', retry: false });
}

// A microphone that cannot start is the learner's device, said as such.
{
  const h = harness({ api: {}, recorder: fakeRecorder({ startOk: false, error: 'microphone_unavailable' }) });
  assert.equal(await h.take.start(), false);
  assert.deepEqual(h.last().error, { kind: 'microphone', retry: false });
  const u = harness({ api: {}, recorder: fakeRecorder({ startOk: false, error: 'recording_unsupported' }) });
  await u.take.start();
  assert.equal(u.last().error.kind, 'unsupported');
}

// A service failure is retried with the same take; no second recording.
{
  let calls = 0;
  const api = {
    assessPronunciation: async (blob, language, line) => {
      calls++;
      if (calls === 1) throw Object.assign(new Error('timeout'), { status: 504, category: 'pronunciation_timeout' });
      return measured(line);
    },
  };
  const h = harness({ api });
  await h.take.start();
  h.advance(2000);
  await h.take.stop('Hello there.');
  assert.deepEqual(h.last().error, { kind: 'service', retry: true });
  await h.take.retry();
  assert.equal(h.last().phase, TAKE.RESULT);
  assert.equal(h.recorder.calls.start, 1, 'retry never records again');
}

// No speech is the learner's outcome, not a provider failure, and is not retried as one.
assert.deepEqual(failureOf({ status: 422, category: 'pronunciation_no_speech' }), { kind: 'no_speech', retry: false });
assert.deepEqual(failureOf({ status: 503, category: 'pronunciation_unconfigured' }), { kind: 'unavailable', retry: false });
assert.deepEqual(failureOf({ status: 502, category: 'pronunciation_auth' }), { kind: 'service', retry: true });
assert.deepEqual(failureOf(Object.assign(new Error('x'), { name: 'AbortError' })), { kind: 'aborted', retry: false });

// A late answer never overwrites a newer take; leaving drops every answer.
{
  const pending = [];
  const api = { assessPronunciation: (blob, language, line) => new Promise((resolve) => pending.push(() => resolve(measured(line)))) };
  const h = harness({ api });
  await h.take.start();
  h.advance(1000);
  const first = h.take.stop('first line');
  await tick();
  assert.equal(h.last().phase, TAKE.PROCESSING);
  assert.equal(await h.take.start(), false, 'no second take while one is being assessed');
  pending[0]();
  await first;
  await h.take.start();
  h.advance(1000);
  const second = h.take.stop('second line');
  await tick();
  h.take.dispose();
  pending[1]();
  await second;
  assert.equal(h.last().phase, TAKE.PROCESSING, 'an answer after leaving the room is dropped');
  assert.ok(urls.revoked.length >= 1, 'the take is released when the room goes');
}

// Cancelling a recording keeps the previous result and sends nothing.
{
  let sent = 0;
  const api = { assessPronunciation: async (b, l, line) => (sent++, measured(line)) };
  const h = harness({ api });
  await h.take.start();
  h.advance(1000);
  await h.take.stop('one');
  await h.take.start();
  h.take.cancel();
  assert.equal(sent, 1);
  assert.equal(h.last().phase, TAKE.RESULT);
  assert.ok(h.last().result, 'the earlier result is still there');
}

// Losing the network while grading is neither the learner's nor the provider's: the take is kept
// for this session and graded again when asked (Orena Speaking 09 C).
assert.deepEqual(failureOf(Object.assign(new TypeError('Failed to fetch'))), { kind: 'offline', retry: true });
{
  let online = false;
  const api = { assessPronunciation: async (b, l, line) => { if (!online) throw new TypeError('Failed to fetch'); return measured(line); } };
  const h = harness({ api });
  await h.take.start();
  h.advance(1500);
  await h.take.stop('Hello again.');
  assert.deepEqual(h.last().error, { kind: 'offline', retry: true });
  assert.ok(h.take.takeBlob, 'the recording is still here to grade later');
  online = true;
  await h.take.retry();
  assert.equal(h.last().phase, TAKE.RESULT);
  assert.equal(h.take.takeMs, 1500);
}

// The plan's pronunciation minutes (D-16Z). The server charges a take's seconds once per idempotency key: one key
// per take, kept when the answer was lost or the server says it already has the take, new when the server answered
// that it charged nothing - so a retry of the same take is never charged twice and never blocked by a failure.
const refusal = Object.assign(new Error('You have used 5 of 5'), {
  status: 429, category: 'quota_exhausted', context: { feature: 'pronunciation.audio', used: 300, limit: 300, scale: 60 },
});
assert.deepEqual(failureOf(refusal), { kind: 'quota', retry: false, error: refusal }, 'the limit is the server\'s refusal, not a service failure');
assert.equal(failureOf(Object.assign(new Error('x'), { status: 429, category: 'rate_limited' })).kind, 'service', 'another 429 is not the plan');
{
  /* A server that answers only what the real one can: a key it has seen is `operation_in_progress` while its first
     request runs and `operation_finished` for ever after - whatever that first request's outcome (the quota core
     records a settled-0 failure too), so only a NEW key can be assessed again. `lose` makes the answer to a first
     request vanish on the way back (the server still finishes it); `hang` leaves it running; `fail` makes the first
     request an answered service failure. */
  const server = (plan) => {
    const seen = new Map(); // key -> 'in_progress' | 'finished'
    const sent = [];
    return {
      sent,
      finish: (key) => seen.set(key, 'finished'),
      api: {
        assessPronunciation: async (blob, language, line, mode, filename, options) => {
          const key = options?.idempotencyKey;
          sent.push(key);
          if (seen.get(key) === 'in_progress') throw Object.assign(new Error('busy'), { status: 409, category: 'operation_in_progress' });
          if (seen.get(key) === 'finished') throw Object.assign(new Error('done'), { status: 409, category: 'operation_finished' });
          const how = plan.shift();
          seen.set(key, how === 'hang' ? 'in_progress' : 'finished');
          if (how === 'lose' || how === 'hang') throw new TypeError('Failed to fetch');
          if (how === 'fail') throw Object.assign(new Error('timeout'), { status: 504, category: 'pronunciation_timeout' });
          return measured(line);
        },
      },
    };
  };
  const record = async (h, line) => {
    await h.take.start();
    h.advance(1500);
    await h.take.stop(line);
  };

  // The answer was lost but the server finished: the resend is `operation_finished` - terminal, not a retry loop.
  {
    const s = server(['lose', 'ok']);
    const h = harness({ api: s.api });
    await record(h, 'Hello again.');
    assert.deepEqual(h.last().error, { kind: 'offline', retry: true });
    await h.take.retry();
    assert.equal(s.sent[0], s.sent[1], 'no answer: the same key, so a processed take is never charged twice');
    assert.deepEqual(h.last().error, { kind: 'already_assessed', retry: false });
    const before = s.sent.length;
    await h.take.retry();
    assert.equal(s.sent.length, before, 'nothing is resent: the answer could only ever be the same');
    assert.equal(h.last().phase, TAKE.ERROR);
    await record(h, 'Hello again.'); // the learner records again: a new take, a new key, a new assessment
    assert.equal(h.last().phase, TAKE.RESULT);
    assert.notEqual(s.sent[2], s.sent[0], 'a new take is a new key');
  }
  // The first request is still running when the resend arrives: that is worth retrying, with the same key.
  {
    const s = server(['hang']);
    const h = harness({ api: s.api });
    await record(h, 'Hello again.');
    await h.take.retry();
    assert.deepEqual(h.last().error, { kind: 'service', retry: true }, 'in progress: try again shortly');
    assert.equal(s.sent[0], s.sent[1]);
    s.finish(s.sent[0]);
    await h.take.retry();
    assert.deepEqual(h.last().error, { kind: 'already_assessed', retry: false });
  }
  // The server answered a failure (it charged nothing and closed that key): the same take goes again under a NEW key.
  {
    const s = server(['fail', 'ok']);
    const h = harness({ api: s.api });
    await record(h, 'Hello again.');
    assert.deepEqual(h.last().error, { kind: 'service', retry: true });
    await h.take.retry();
    assert.equal(h.last().phase, TAKE.RESULT);
    assert.notEqual(s.sent[0], s.sent[1], 'an answered failure closed the key: a new key');
    assert.ok(s.sent.every((key) => typeof key === 'string' && key.length >= 8), 'every send carries a key');
  }
  assert.deepEqual(failureOf(Object.assign(new Error('x'), { status: 409, category: 'operation_conflict' })), { kind: 'already_assessed', retry: false });
}

// The request itself: the take's key and the device timezone ride as headers, and the form is left to the browser
// (a JSON content type would break the multipart boundary).
{
  const { api } = await import('../static/orena/infrastructure/api.js');
  const seen = [];
  globalThis.fetch = async (url, options) => (seen.push({ url, options }), new Response('{"score_kind":"measured"}', { status: 200, headers: { 'content-type': 'application/json' } }));
  await api.assessPronunciation(new Blob(['x']), 'en', 'Hello.', 'scripted', 'recording.webm', { idempotencyKey: 'take-key-1' });
  await api.assessPronunciation(new Blob(['x']), 'en', 'Hello.');
  assert.equal(seen[0].url, '/api/speech/pronunciation');
  assert.equal(seen[0].options.headers['Idempotency-Key'], 'take-key-1');
  assert.ok(seen[0].options.headers['X-Orena-Timezone'], 'the learner\'s zone decides when the month ends');
  assert.ok(!Object.keys(seen[0].options.headers).some((name) => name.toLowerCase() === 'content-type'));
  assert.ok(seen[0].options.body instanceof FormData);
  assert.ok(!('Idempotency-Key' in seen[1].options.headers), 'no key unless the take supplies one');
}

console.log('Speaking take lifecycle: PASS');
