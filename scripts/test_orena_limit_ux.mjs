/* Gate for the limit UX gaps (PRE-403 G1-G9): what a learner is told, and how a retry behaves, when a limit or a brake answers.
   Pure parts and the Orena transport are driven; no DOM, no network. */
import assert from 'node:assert/strict';

globalThis.document ??= { addEventListener() {}, removeEventListener() {}, documentElement: { lang: 'en', dataset: {} } };
globalThis.window ??= { addEventListener() {}, removeEventListener() {}, location: { hash: '' } };

const copy = await import('../static/orena/copy/index.js');
const { retryOnce, isTransientRequestError } = await import('../static/orena/infrastructure/retry.js');
const { nextIdempotencyKey } = await import('../static/orena/infrastructure/quota-headers.js');
const { failureOf } = await import('../static/orena/capabilities/speaking-take.js');
const notice = await import('../static/orena/screens/plan/quota-notice.js');
const { retryPlan } = await import('../static/orena/screens/discussion/model.js');
const { liveTurn, MAX_RATE_WAITS } = await import('../static/orena/agent/transport.js');
const { createSession } = await import('../static/orena/agent/session.js');
const { errorText, thinkingText } = await import('../static/orena/screens/orena/model.js');

const err = (status, category, extra = {}) => Object.assign(new Error('x'), { status, ...(category ? { category } : {}), ...extra });
const inHours = (h) => new Date(Date.now() + h * 3600 * 1000).toISOString();
copy.setLanguages({ ui: 'en', support: 'en' });

// G3: retryOnce never re-hits a 429 at once (it would spend the same window twice); other transient failures still retry once.
{
  let calls = 0;
  await assert.rejects(retryOnce(async () => { calls += 1; throw err(429, 'rate_limited', { retryAfterMs: 5000 }); }), (e) => e.status === 429);
  assert.equal(calls, 1, 'a 429 is not retried');
  assert.equal(isTransientRequestError(err(429)), true, 'still transient for the annotate policy, which backs off by Retry-After');
  calls = 0;
  const ok = await retryOnce(async () => { calls += 1; if (calls === 1) throw err(503); return 'ok'; });
  assert.deepEqual([ok, calls], ['ok', 2], 'a 503 still retries once');
}

// G3: a 429 `rate_limited` is told with the seconds from Retry-After (api.js puts them on `retryAfterMs`), in every language.
{
  const limited = err(429, 'rate_limited', { retryAfterMs: 7000 });
  assert.equal(notice.isRateLimited(limited), true);
  assert.equal(notice.pausedLineOf(limited), 'Too many requests. Try again in 7 s.');
  assert.equal(notice.pausedLineOf(err(429, 'rate_limited')), 'Too many requests. Try again in a moment.', 'no Retry-After: no number promised');
  copy.setLanguages({ ui: 'vi', support: 'vi' });
  assert.equal(notice.pausedLineOf(limited), 'Quá nhiều yêu cầu. Thử lại sau 7 giây.');
  copy.setLanguages({ ui: 'zh', support: 'zh' });
  assert.equal(notice.pausedLineOf(limited), '请求过于频繁，请 7 秒后重试。');
  copy.setLanguages({ ui: 'en', support: 'en' });
  assert.equal(notice.isRateLimited(err(429, 'quota_exhausted')), false, 'the plan limit is not the brake');
  assert.equal(notice.isRateLimited(err(429, 'daily_ai_limit')), false);
  assert.equal(notice.isRateLimited(err(503, 'rate_limited')), false);
}

// G8: 503 quota_unavailable has its own line (the existing unavailable pattern), in every language.
{
  const down = err(503, 'quota_unavailable');
  assert.equal(notice.pausedLineOf(down), 'Usage limits can’t be checked right now. Please try again in a moment.');
  copy.setLanguages({ ui: 'vi', support: 'vi' });
  assert.ok(notice.pausedLineOf(down).startsWith('Hiện chưa kiểm tra được hạn mức'));
  copy.setLanguages({ ui: 'zh', support: 'zh' });
  assert.equal(notice.pausedLineOf(down), '暂时无法检查使用额度，请稍后重试。');
  copy.setLanguages({ ui: 'en', support: 'en' });
  assert.equal(notice.pausedLineOf(err(503, 'provider_unavailable')), '', 'another 503 is the room\'s own failure line');
}

// G4: pronunciation scoring recognises the $5 ceiling (body or header) and never offers Retry.
{
  const resets = inHours(5);
  const body = failureOf(err(429, 'daily_ai_limit', { context: { resets_at: resets } }));
  assert.deepEqual([body.kind, body.retry], ['paused', false]);
  const header = failureOf(err(503, '', { aiPaused: resets }));
  assert.deepEqual([header.kind, header.retry], ['paused', false], 'the pause header on any answer');
  assert.equal(notice.pausedLineOf(body.error), notice.pausedMessage(resets), 'the existing AI-paused sentence, with the time');
  assert.ok(notice.pausedLineOf(body.error).startsWith("Orena's AI is paused for today."));
  assert.equal(failureOf(err(429, 'rate_limited')).retry, false);
  assert.equal(failureOf(err(503, 'pronunciation_unconfigured')).kind, 'unavailable', 'a fault is still a fault');
  assert.equal(failureOf(err(500)).kind, 'service');
}

// G5: speech-to-text refusals read as their own line, not as a provider problem.
{
  const resets = inHours(3);
  assert.equal(notice.transcribeRefusalLine(err(429, 'daily_ai_limit', { context: { resets_at: resets } })), notice.pausedMessage(resets));
  const asr = notice.transcribeRefusalLine(err(429, 'speech_asr_daily_limit', { context: { resets_at: resets } }));
  assert.ok(asr.startsWith('You have reached the limit of your plan for now.') && asr.includes('Resets at'), asr);
  assert.equal(notice.transcribeRefusalLine(err(429, 'speech_asr_daily_limit')), 'You have reached the limit of your plan for now.', 'no time, nothing promised');
  assert.equal(notice.transcribeRefusalLine(err(500)), '', 'any other failure keeps the room\'s provider sheet');
  assert.equal(notice.transcribeRefusalLine(new TypeError('network')), '');
  assert.equal(notice.isAsrDailyLimit(err(429, 'speech_asr_daily_limit')), true);
}

// G1: the quota line carries the reset time from `resets_at`, in the learner's local time and language.
{
  const soon = inHours(4);
  const time = new Intl.DateTimeFormat('en', { hour: 'numeric', minute: '2-digit' }).format(new Date(soon));
  const limit = { feature: 'orena.message', used: 20, limit: 20, resets_at: soon };
  assert.equal(notice.quotaMessage({ context: limit }), `You have used 20 of 20 Orena messages today. Resets at ${time}.`);
  assert.equal(notice.quotaMessage({ context: { ...limit, resets_at: inHours(-2) } }), 'You have used 20 of 20 Orena messages today.', 'a past time is never promised');
  assert.equal(notice.quotaMessage({ context: { ...limit, resets_at: undefined } }), 'You have used 20 of 20 Orena messages today.');
  const month = notice.quotaMessage({ context: { feature: 'writing.review', used: 2, limit: 2, resets_at: inHours(24 * 20) } });
  assert.ok(/^You have used 2 of 2 writing reviews this month\. Resets [A-Z][a-z]{2} \d{1,2}\.$/.test(month), month);
  copy.setLanguages({ ui: 'vi', support: 'vi' });
  const vi = notice.quotaMessage({ context: limit });
  assert.ok(vi.startsWith('Bạn đã dùng 20/20 tin nhắn Orena trong hôm nay. Đặt lại lúc '), vi);
  copy.setLanguages({ ui: 'zh', support: 'zh' });
  const zh = notice.quotaMessage({ context: limit });
  assert.ok(zh.startsWith('今天的 Orena 消息已用 20/20 条。') && zh.endsWith('重置。'), zh);
  assert.ok(!/\{|\}/.test(vi + zh), 'no unfilled slot');
  copy.setLanguages({ ui: 'en', support: 'en' });
}

// G9: "You can still message Orena" only while the message meter has room.
{
  const voice = { feature: 'orena.voice', used: 15, limit: 15, scale: 60 };
  const messages = (used) => ({ features: { 'orena.message': { used, limit: 20, usage_state: 'known' } } });
  assert.ok(notice.quotaMessage({ context: voice }).includes('You can still message Orena'), 'no commerce read: the clause stays');
  assert.ok(notice.quotaMessage({ context: voice }, messages(3)).includes('You can still message Orena'));
  assert.ok(/^You have used all [\d.]+ minutes of voice chat today\.$/.test(notice.quotaMessage({ context: voice }, messages(20))), 'exactly the line without the clause');
  assert.ok(!notice.quotaMessage({ context: voice }, messages(20)).includes('message Orena'), 'messages spent: the clause is dropped');
  assert.equal(notice.messagesSpent({ features: { 'orena.message': { used: 20, limit: 20, usage_state: 'unknown' } } }), false, 'unknown use is never read as spent');
  const dayLimit = notice.voiceDayLimitMessage({ features: { 'orena.voice': { limit: 900, scale: 60 }, 'orena.message': { used: 20, limit: 20, usage_state: 'known' } } });
  assert.ok(!dayLimit.includes('message Orena'), 'the mid-chunk day limit follows the same rule');
  copy.setLanguages({ ui: 'zh', support: 'zh' });
  assert.ok(!notice.quotaMessage({ context: voice }, messages(20)).includes('发消息'));
  copy.setLanguages({ ui: 'vi', support: 'vi' });
  assert.ok(!notice.quotaMessage({ context: voice }, messages(20)).includes('nhắn tin'));
  copy.setLanguages({ ui: 'en', support: 'en' });
}

// G7 rule: an unanswered request keeps its key, an answered refusal mints a new one, `operation_in_progress` keeps it.
{
  const mint = () => 'new';
  assert.equal(nextIdempotencyKey(new TypeError('network'), 'old', mint), 'old');
  assert.equal(nextIdempotencyKey({}, 'old', mint), 'old');
  assert.equal(nextIdempotencyKey({ status: 503 }, 'old', mint), 'new');
  assert.equal(nextIdempotencyKey({ status: 429, category: 'rate_limited' }, 'old', mint), 'new');
  assert.equal(nextIdempotencyKey({ status: 409, category: 'operation_in_progress' }, 'old', mint), 'old');
  // The discussion's plan is the same rule.
  assert.equal(retryPlan({ status: 500 }, 'r1', mint).requestId, 'new');
  assert.equal(retryPlan(new TypeError('x'), 'r1', mint).requestId, 'r1');
  assert.equal(retryPlan({ status: 409, category: 'operation_in_progress' }, 'r1', mint).requestId, 'r1');
}

// Orena's transport: bounded waits (G2), its own errors (G6, G8), the key travelling with them (G7).
const SSE_OK = 'event: session\ndata: {"session_id":"s1","contract_version":4}\n\nevent: done\ndata: {"usage":{},"trace_id":"t"}\n\n';
const answer = (status, body = null, headers = {}) => new Response(body, { status, headers });
const envelope = (category) => JSON.stringify({ detail: { category, message: 'm', retryable: true, context: {} } });
const JSON_HEAD = { 'Content-Type': 'application/json' };
async function drive(responses, options = {}) {
  const queue = [...responses];
  const heads = [];
  const slept = [];
  const out = [];
  const fetchImpl = async (url, init) => {
    heads.push(init.headers);
    const next = queue.shift();
    if (next instanceof Error) throw next;
    return next;
  };
  const base = { trigger: 'message', message: 'Hi', context: {}, contract_version: 4 };
  for await (const e of liveTurn(base, { signal: new AbortController().signal, fetchImpl, sleep: async (ms) => { slept.push(ms); }, signedOut: () => {}, log: () => {}, ...options })) out.push(e);
  return { out, heads, slept, last: out[out.length - 1] };
}
{
  // G2: three short waits, then the learner is told (never an unbounded loop).
  const limited = () => answer(429, '{"detail":"Too many requests; try again in a moment."}', { 'Retry-After': '2' });
  let run = await drive([limited(), limited(), limited(), limited(), answer(200, SSE_OK)]);
  assert.equal(MAX_RATE_WAITS, 3);
  assert.deepEqual(run.slept, [2000, 2000, 2000], 'bounded: three waits');
  assert.equal(run.heads.length, 4, 'then it stops asking');
  assert.equal(run.last.event, 'error');
  assert.deepEqual([run.last.data.class, run.last.data.fallback, run.last.data.retryAfter], ['rate_limited', 'retry', 2]);
  assert.equal(new Set(run.heads.map((h) => h['Idempotency-Key'])).size, 1, 'the waits resend one key');
  run = await drive([answer(429, '{"detail":"x"}', { 'Retry-After': '600' }), answer(200, SSE_OK)]);
  assert.deepEqual([run.slept, run.heads.length, run.last.data.class], [[], 1, 'rate_limited'], 'a long Retry-After is told at once, not slept through');
  assert.equal(run.last.data.retryAfter, 600);

  // G2: while waiting, the thinking place says it; the error line carries the seconds.
  assert.equal(thinkingText(null, 'Orena is thinking…', 4), 'Too many requests. Try again in 4 s.');
  assert.equal(thinkingText(null, 'Orena is thinking…', null), 'Orena is thinking…');
  assert.equal(errorText({ class: 'rate_limited', message: '', fallback: 'retry', retryAfter: 12 }, 'x'), 'Too many requests. Try again in 12 s.');

  // G6: a second request under the same key is "still working", not "check your connection".
  run = await drive([answer(409, envelope('operation_in_progress'), JSON_HEAD)]);
  assert.deepEqual([run.last.data.class, run.last.data.fallback, run.last.data.category, run.last.data.status], ['operation_in_progress', 'retry', 'operation_in_progress', 409]);
  assert.equal(errorText(run.last.data, 'transport', 'provider', 'still working'), 'still working');
  run = await drive([answer(409, envelope('operation_finished'), JSON_HEAD)]);
  assert.equal(run.last.data.class, 'transport', 'the other 409s keep the generic line');

  // G8: the plan could not be read.
  run = await drive([answer(503, envelope('quota_unavailable'), JSON_HEAD)]);
  assert.deepEqual([run.last.data.class, run.last.data.fallback], ['quota_unavailable', 'retry']);
  assert.equal(errorText(run.last.data, 'transport'), 'Usage limits can’t be checked right now. Please try again in a moment.');

  // G7: the outcome is unknown after a network failure or a dead stream (key reused); known after an answered refusal (new key).
  const session = createSession({ log: () => {} });
  const finish = async (responses, options) => {
    const run2 = await drive(responses, options);
    session.learner('Hi');
    for (const item of run2.out) session.apply(item);
    return run2;
  };
  let first = await finish([new TypeError('network')]);
  const key1 = first.heads[0]['Idempotency-Key'];
  assert.ok(key1);
  assert.equal(first.last.data.status, undefined, 'unanswered: no status');
  assert.equal(session.retryKey(), key1, 'network failure: Retry reuses the key');
  let retried = await drive([answer(200, SSE_OK)], { idempotencyKey: session.retryKey() });
  assert.equal(retried.heads[0]['Idempotency-Key'], key1, 'the retry is sent under the earlier key');

  const dead = new Response(new ReadableStream({ start(c) { c.enqueue(new TextEncoder().encode('event: session\ndata: {"session_id":"s1","contract_version":4}\n\n')); c.close(); } }), { status: 200 });
  first = await finish([dead]);
  assert.equal(first.last.data.class, 'transport');
  assert.equal(session.retryKey(), first.heads[0]['Idempotency-Key'], 'a stream that died after the request was accepted: the key is reused');

  first = await finish([answer(503, envelope('provider_unavailable'), JSON_HEAD)]);
  assert.equal(session.retryKey(), '', 'an answered refusal: a new key (the transport mints it)');
  first = await finish([answer(409, envelope('operation_in_progress'), JSON_HEAD)]);
  assert.equal(session.retryKey(), first.heads[0]['Idempotency-Key'], 'still running: the key is kept');
  first = await finish([answer(429, '{"detail":"x"}', { 'Retry-After': '600' })]);
  assert.equal(session.retryKey(), '', 'rate limited and answered: a new key');
  // A reply with no error has no key to hand back.
  const fresh = createSession({ log: () => {} });
  fresh.learner('Hi');
  assert.equal(fresh.retryKey(), '');
  // The quota refusals carry nothing extra (the reducer keeps their exact shape).
  const q = await drive([answer(429, JSON.stringify({ detail: { category: 'quota_exhausted', context: { feature: 'orena.message', used: 1, limit: 1 } } }), JSON_HEAD)]);
  assert.deepEqual(Object.keys(q.last.data).sort(), ['class', 'fallback', 'message', 'quota']);
}

console.log('limit UX gates passed');
