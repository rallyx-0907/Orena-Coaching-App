/* Switching the learning language brings every language-scoped thing over before anything is painted
   (shell/context.js adoptLearningLanguage; runtime acceptance item 4): the new language's profile and its version,
   its stored review settings on top of the device copy, its places and imports. Nothing is written to the server
   by the switch, and the device defaults never overwrite a stored value. A stub fetch stands in for the network. */
import assert from 'node:assert/strict';

const dataset = {};
globalThis.document = { documentElement: { dataset, lang: 'en' } };
globalThis.location = { href: '' };
globalThis.window = { localStorage: null, addEventListener() {}, matchMedia: () => ({ matches: false, addEventListener() {} }) };
const writes = [];
const profiles = {
  zh: { exists: true, language: 'zh', version: 'zh-v1', declared_level: 'HSK3', pinyin: 'on', support_language: 'vi', review_modes: { cloze: false }, review_new_per_day: 7, review_limit_per_day: null },
  en: { exists: true, language: 'en', version: 'en-v9', declared_level: 'B2', pinyin: 'auto', support_language: 'vi', review_modes: null, review_new_per_day: null, review_limit_per_day: null },
};
let active = 'zh';
globalThis.fetch = async (url, options = {}) => {
  if ((options.method || 'GET') !== 'GET') writes.push(`${options.method} ${url}`);
  const body = url.includes('/api/learner-profile') ? profiles[active]
    : url.includes('/api/continue') ? { items: [{ content_id: 'media:zh-1', kind: 'listening', place: { title: 'ZH', index: 1, total: 2 } }] }
    : url.includes('/api/account-backbone') ? { state: 'active' }
    : url.includes('/api/imports') ? { imports: [] }
    : url.includes('/api/library/vocabulary/summary') ? { summary: { due: 4 } }
    : {};
  return { ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => body };
};
const storage = (() => {
  const data = {};
  return { getItem: (key) => data[key] ?? null, setItem: (key, value) => { data[key] = String(value); }, removeItem: (key) => { delete data[key]; } };
})();

const shell = await import('../static/orena/shell/context.js');
const { readReviewSettings } = await import('../static/orena/product/recall-modes.js');
shell.updateContext({ language: 'en', profile: profiles.en, owner: 'me', level: 'B2' });

await shell.adoptLearningLanguage('zh', storage);
const now = shell.context();
assert.equal(now.language, 'zh');
assert.equal(now.profile.version, 'zh-v1', 'the profile (and so the version a write is made against) is the new language\'s');
assert.equal(now.level, 'HSK3');
assert.equal(now.memory.value.reviewSettings.modes.cloze, false, 'the stored zh mode shows, not the device default');
assert.equal(now.memory.value.reviewSettings.modes.typing, true, 'a mode the server does not hold keeps the device value');
assert.equal(now.memory.value.reviewSettings.newPerDay, 7);
assert.deepEqual(now.memory.value.continuation.map((entry) => entry.id), ['media:zh-1']);
assert.equal(dataset.tl, 'zh');
assert.deepEqual(writes, [], 'adopting a language writes nothing - device defaults never overwrite the server');

active = 'en';
await shell.adoptLearningLanguage('en', storage);
assert.equal(shell.context().profile.version, 'en-v9');
assert.equal(readReviewSettings(shell.context().memory.value.reviewSettings).modes.cloze, true, 'the other language\'s stored cloze=false did not leak across');
assert.deepEqual(writes, []);

console.log('Language switch: the new language\'s profile, version and stored review settings are in place before the repaint; nothing is written: PASS');
