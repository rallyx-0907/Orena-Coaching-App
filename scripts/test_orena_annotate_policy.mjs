/* Gate for the annotate request policy: a 4xx (the 409 language mismatch) is asked once and then closed for
   that text and language; 5xx/network is retried at most twice with backoff; success is untouched. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const { annotateAll, annotateAllowed, annotateWithPolicy, annotateRefused, resetAnnotatePolicy, ANNOTATE_BACKOFF_MS, BREAKER_LIMIT } =
  await import('../static/orena/infrastructure/annotate-policy.js');

const fail = (status) => Object.assign(new Error('x'), status === undefined ? { name: 'TypeError' } : { status });
const counter = (...outcomes) => {
  const send = async () => {
    send.calls += 1;
    const next = outcomes[Math.min(send.calls - 1, outcomes.length - 1)];
    if (next instanceof Error) throw next;
    return next;
  };
  send.calls = 0;
  return send;
};
const sleeps = [];
const sleep = async (ms) => void sleeps.push(ms);
const payload = { text: 'a', source_language: 'zh' };
const run = (send, scope = 'art', p = payload) => annotateWithPolicy(send, p, { scope, sleep });

// 1. Repeated 409 for one article: exactly one request, every later paragraph is skipped without a request.
resetAnnotatePolicy();
const s409 = counter(fail(409));
for (let i = 0; i < 86; i += 1) await assert.rejects(run(s409), (e) => e.status === 409);
assert.equal(s409.calls, 1, 'one request for 86 paragraphs');
assert.equal(annotateRefused('art', 'zh'), true);
assert.equal(annotateRefused('art', 'en'), false, 'other language not closed');
assert.equal(annotateRefused('other', 'zh'), false, 'other text not closed');
assert.equal(sleeps.length, 0, 'no backoff for a 4xx');

// 2. A payload error (400/413/422) fails once, is never retried, and does not close the pair.
for (const code of [400, 413, 422]) {
  resetAnnotatePolicy();
  const s4 = counter(fail(code));
  await assert.rejects(run(s4), (e) => e.status === code);
  assert.equal(s4.calls, 1);
  assert.equal(annotateRefused('art', 'zh'), false, `${code} leaves the pair open`);
}
// 401 and 403 close the pair, once, without a retry.
for (const code of [401, 403]) {
  resetAnnotatePolicy();
  const s4 = counter(fail(code));
  await assert.rejects(run(s4));
  await assert.rejects(run(s4));
  assert.equal(s4.calls, 1);
  assert.equal(annotateRefused('art', 'zh'), true);
}
// 408/425/429 retry with backoff; Retry-After wins when longer.
for (const code of [408, 425, 429]) {
  resetAnnotatePolicy();
  const s4 = counter(fail(code), { ok: 1 });
  assert.deepEqual(await run(s4), { ok: 1 });
  assert.equal(s4.calls, 2);
  assert.deepEqual(sleeps.splice(0), [ANNOTATE_BACKOFF_MS[0]]);
}
resetAnnotatePolicy();
await run(counter(Object.assign(fail(429), { retryAfterMs: 3000 }), { ok: 1 }));
assert.deepEqual(sleeps.splice(0), [3000]);

// 2b. Concurrent workers: after the first 409 lands, no more than the worker count was ever sent.
resetAnnotatePolicy();
let sent = 0;
const slow409 = async () => { sent += 1; await new Promise((r) => setImmediate(r)); throw fail(409); };
let nextPara = 0;
const workers = Array.from({ length: 6 }, async () => {
  while (nextPara < 86 && !annotateRefused('art', 'zh')) {
    nextPara += 1;
    await run(slow409).catch(() => {});
  }
});
await Promise.all(workers);
assert.ok(sent <= 6, `at most 6 in flight, sent ${sent}`);

// 2c. Circuit breaker: consecutive failed calls close the pair.
resetAnnotatePolicy();
const dead = counter(fail(503));
for (let i = 0; i < 10; i += 1) await run(dead).catch(() => {});
assert.equal(dead.calls, 3 * BREAKER_LIMIT);
assert.equal(annotateRefused('art', 'zh'), true);
sleeps.length = 0;

// 3. 503 forever: 3 requests, two backoffs.
resetAnnotatePolicy();
const s503 = counter(fail(503));
await assert.rejects(run(s503), (e) => e.status === 503);
assert.equal(s503.calls, 3);
assert.deepEqual(sleeps.splice(0), [...ANNOTATE_BACKOFF_MS]);
assert.equal(annotateRefused('art', 'zh'), false, 'a 5xx does not close the pair');

// 4. Network failure then success.
const sNet = counter(fail(undefined), { annotations: [1] });
assert.deepEqual(await run(sNet), { annotations: [1] });
assert.equal(sNet.calls, 2);
sleeps.length = 0;

// 5. Success path: one request, value untouched.
const ok = counter({ annotations: [] });
assert.deepEqual(await run(ok), { annotations: [] });
assert.equal(ok.calls, 1);

// 6. Both callers go through the policy and nothing calls the raw endpoint.
for (const f of ['reader', 'listening']) {
  const src = readFileSync(new URL(`../static/orena/screens/${f}/screen.js`, import.meta.url), 'utf8');
  assert.ok(src.includes('annotateWithPolicy(api.annotateMediaText'), `${f} uses the policy`);
  assert.ok(!/await api\.annotateMediaText/.test(src), `${f} has no raw call`);
}

// 7. Preflight: a text in another language than the one being learned sends nothing; the first request
//    goes alone, a 4xx on it is the only request; on success the rest run in parallel.
assert.equal(annotateAllowed('zh', 'en'), false);
assert.equal(annotateAllowed('ZH', 'zh'), true);
assert.equal(annotateAllowed('', ''), false);
const paragraphs = Array.from({ length: 86 }, (_, i) => i);
const make = (outcome) => {
  const stats = { sent: 0, inFlight: 0, peak: 0 };
  const ask = async () => {
    try {
      await annotateWithPolicy(async () => {
        stats.sent += 1; stats.inFlight += 1; stats.peak = Math.max(stats.peak, stats.inFlight);
        await new Promise((r) => setImmediate(r));
        stats.inFlight -= 1;
        if (outcome) throw fail(outcome);
        return { annotations: [] };
      }, { text: 'a', source_language: 'zh' }, { scope: 'art', sleep });
      return true;
    } catch { return false; }
  };
  return { stats, ask };
};
resetAnnotatePolicy();
let m = make(0);
await annotateAll(paragraphs, m.ask, { scope: 'art', language: 'zh', learning: 'en' });
assert.equal(m.stats.sent, 0, 'language mismatch: zero requests');
resetAnnotatePolicy();
m = make(409);
await annotateAll(paragraphs, m.ask, { scope: 'art', language: 'zh', learning: 'zh' });
assert.equal(m.stats.sent, 1, 'first 409: exactly one request');
resetAnnotatePolicy();
m = make(0);
await annotateAll(paragraphs, m.ask, { scope: 'art', language: 'zh', learning: 'zh' });
assert.equal(m.stats.sent, 86);
assert.ok(m.stats.peak > 1 && m.stats.peak <= 6, `parallel after the first, peak ${m.stats.peak}`);
resetAnnotatePolicy();
m = make(422);
await annotateAll(paragraphs, m.ask, { scope: 'art', language: 'zh', learning: 'zh' });
assert.equal(m.stats.sent, 3, 'a text rejected by the tagger costs three requests, not one per paragraph');
assert.equal(m.stats.peak, 1, 'no success yet: still one at a time');
resetAnnotatePolicy();
let n422 = 0;
await annotateAll(paragraphs, async (i) => (n422 += 1, i === 1), { scope: 'art', language: 'zh', learning: 'zh' });
assert.equal(n422, 86, 'one paragraph failing then one succeeding: the rest still run');
assert.equal(annotateAllowed('zh-Hans', 'zh'), true);
assert.equal(annotateAllowed('zh-CN', 'ZH'), true);
assert.equal(annotateAllowed('en-US', 'en'), true);
assert.equal(annotateAllowed('en', 'zh-Hans'), false);
for (const f of ['reader', 'listening']) {
  const src = readFileSync(new URL(`../static/orena/screens/${f}/screen.js`, import.meta.url), 'utf8');
  assert.ok(src.includes(f === 'reader' ? 'annotateAll(' : 'taggerAllowed('), `${f} preflights the language`);
}
console.log('annotate policy: ok');
