/* Gate for the annotate request policy: a 4xx (the 409 language mismatch) is asked once and then closed for
   that text and language; 5xx/network is retried at most twice with backoff; success is untouched. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const { annotateWithPolicy, annotateRefused, resetAnnotatePolicy, ANNOTATE_BACKOFF_MS } =
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

// 2. Another 4xx is never retried either.
resetAnnotatePolicy();
const s422 = counter(fail(422));
await assert.rejects(run(s422), (e) => e.status === 422);
assert.equal(s422.calls, 1);

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
console.log('annotate policy: ok');
