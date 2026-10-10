/* Media import minutes (D-16S), the client's part: a link and a file are sent with the device timezone (the learner's
   month follows it) and no idempotency key (the server answers a repeated source with the import the learner already
   has), and the plan's refusal is told apart from every other failure of an import. */
import assert from 'node:assert/strict';

const store = new Map();
globalThis.window = { localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) } };
Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US' }, configurable: true });
globalThis.document = { documentElement: { lang: 'en', dataset: {} } };

const { api } = await import('../static/orena/infrastructure/api.js');
const { isQuotaExhausted } = await import('../static/orena/screens/plan/quota-notice.js');

const seen = [];
globalThis.fetch = async (url, options) => (seen.push({ url, options }), new Response('{"media_id":"upload-1"}', { status: 200, headers: { 'content-type': 'application/json' } }));

await api.prepareMedia({ source_url: 'https://youtu.be/abcdefghijk', target_language: 'vi' });
await api.mediaUpload(new File(['x'], 'lecture.mp3', { type: 'audio/mpeg' }), 'en');

assert.equal(seen[0].url, '/api/media-learning/source');
assert.equal(seen[0].options.headers['Content-Type'], 'application/json');
assert.ok(seen[0].options.headers['X-Orena-Timezone'], 'the learner\'s zone decides when the month ends');
assert.ok(!('Idempotency-Key' in seen[0].options.headers), 'the same source is deduplicated by the server, not by a key');

assert.equal(seen[1].url, '/api/media-learning/upload');
assert.ok(seen[1].options.headers['X-Orena-Timezone']);
assert.ok(!Object.keys(seen[1].options.headers).some((name) => name.toLowerCase() === 'content-type'), 'the form is left to the browser');
assert.ok(seen[1].options.body instanceof FormData);

const refusal = Object.assign(new Error('x'), { status: 429, category: 'quota_exhausted', context: { feature: 'media.import', used: 890, limit: 900, scale: 60 } });
assert.equal(isQuotaExhausted(refusal), true);
assert.equal(isQuotaExhausted(Object.assign(new Error('x'), { status: 429, category: 'rate_limited' })), false, 'another 429 is not the plan');
assert.equal(isQuotaExhausted(Object.assign(new Error('x'), { status: 503, category: 'quota_unavailable' })), false, 'an unreadable limit is a failure to retry, not a refusal');

/* The plan's other refusals are said in the sheet, in each language, not as the generic error. */
const copy = await import('../static/orena/copy/index.js');
const { t } = await import('../static/orena/screens/import/copy.js');
const { importErrorKey } = await import('../static/orena/screens/import/model.js');
for (const category of ['quota_unavailable', 'media_duration_unavailable', 'feature_not_in_plan']) {
  assert.equal(importErrorKey(category), `error_${category}`);
  const said = ['en', 'vi', 'zh'].map((ui) => { copy.setLanguages({ ui: 'en', support: ui }); return t(`error_${category}`); });
  assert.equal(new Set(said).size, 3, `${category}: three languages`);
  for (const text of said) assert.notEqual(text, t('error_generic'));
}
copy.setLanguages({ ui: 'en', support: 'en' });

console.log('test_media_import_quota.mjs: import requests carry the timezone, the plan refusal is told apart: PASS');
