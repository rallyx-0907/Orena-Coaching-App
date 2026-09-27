/* Gate for the new UI's copy engine (copy/index.js): a placeholder takes any given value, 0
   included - "{n} due" once read literally at zero - and one without a value stays visible. */
import assert from 'node:assert/strict';

// copy/index.js resolves the interface language at import: give it a browser to ask.
const store = new Map();
globalThis.window = { localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) } };
Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US' }, configurable: true });
globalThis.document = { documentElement: { lang: 'en', dataset: {} } };

const copy = await import('../static/orena/copy/index.js');

// 0. Placeholders: every given value fills its placeholder, 0 included; one with no value stays visible.
const fill = copy.defineCopy('test.copy-engine.fill', {
  layers: { count: 'interface' },
  en: { count: '{n} words · {m} left' },
  vi: { count: '{n} từ · còn {m}' },
  zh: { count: '{n} 个词 · 剩 {m}' },
});
assert.equal(fill('count', { n: 0, m: 0 }), '0 words · 0 left', 'a 0 value fills its placeholder');
assert.equal(fill('count', { n: 3 }), '3 words · {m} left', 'a placeholder without a value stays visible');
assert.equal(fill('count', { n: null, m: undefined }), '{n} words · {m} left', 'null and undefined are not values');

console.log('Orena copy engine: a 0 fills its placeholder, a missing value stays visible: PASS');
