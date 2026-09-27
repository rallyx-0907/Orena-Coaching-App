/* Gate for the new learner UI's words (D-079, Design Contract rules 9, 26 and 50).

   Every copy table the new UI registers (copy/*.js and screens/<name>/copy.js) declares a language
   layer for every key, and its English, Vietnamese and Chinese packs each carry every key, with the
   same {placeholders}: a supported locale never silently shows English. Interface keys follow the
   interface language and support keys the support language, never each other. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

// The copy modules resolve the interface language at import: give them a browser to ask.
const store = new Map();
globalThis.window = { localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) } };
Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US' }, configurable: true });
globalThis.document = { documentElement: { lang: 'en', dataset: {} } };

const modules = [
  ...fs.readdirSync('static/orena/copy').filter((f) => f.endsWith('.js') && f !== 'index.js').map((f) => path.join('static/orena/copy', f)),
  ...(fs.existsSync('static/orena/screens')
    ? fs.readdirSync('static/orena/screens').map((d) => path.join('static/orena/screens', d, 'copy.js')).filter((f) => fs.existsSync(f))
    : []),
  ...(fs.existsSync('static/orena/agent') ? fs.readdirSync('static/orena/agent').filter((f) => f === 'copy.js').map((f) => path.join('static/orena/agent', f)) : []),
];
for (const file of modules) await import(pathToFileURL(path.resolve(file)).href);

const copy = await import('../static/orena/copy/index.js');
const tables = copy.registeredCopy();
assert.ok(tables.size >= 1, 'copy tables registered');

const placeholders = (text) => [...String(text).matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort().join(',');
let keys = 0;
for (const [namespace, { layers, packs }] of tables) {
  const declared = Object.keys(layers).sort();
  for (const [key, layer] of Object.entries(layers)) assert.ok(['interface', 'support'].includes(layer), `${namespace}.${key}: layer is interface or support`);
  for (const locale of copy.LOCALES) {
    const pack = packs[locale];
    assert.ok(pack, `${namespace}: a ${locale} pack`);
    const base = Object.keys(pack).map((k) => k.replace(/_(one|other)$/, '')).filter((k, i, a) => a.indexOf(k) === i);
    for (const key of Object.keys(pack)) {
      const bare = key.replace(/_(one|other)$/, '');
      assert.ok(layers[key] || layers[bare], `${namespace}.${key} (${locale}) has a declared layer`);
      assert.equal(typeof pack[key], 'string', `${namespace}.${key} (${locale}) is text`);
      assert.ok(pack[key].trim().length > 0, `${namespace}.${key} (${locale}) is not empty`);
    }
    for (const key of declared) {
      const present = key in pack || `${key}_other` in pack;
      assert.ok(present, `${namespace}.${key} is missing from the ${locale} pack`);
      const text = pack[key] ?? pack[`${key}_other`];
      const english = packs.en[key] ?? packs.en[`${key}_other`];
      assert.equal(placeholders(text), placeholders(english), `${namespace}.${key} (${locale}) keeps the placeholders of English`);
    }
    assert.ok(base.length >= declared.length - 0, `${namespace} (${locale}) covers its keys`);
  }
  keys += declared.length;
}

// Layers are honoured: an interface key follows the interface language, a support key the support language.
const probe = copy.defineCopy('gate-probe', {
  layers: { chrome: 'interface', guide: 'support' },
  en: { chrome: 'Back', guide: 'Stress the second syllable.' },
  vi: { chrome: 'Quay lại', guide: 'Nhấn âm tiết thứ hai.' },
  zh: { chrome: '返回', guide: '重读第二个音节。' },
});
copy.setLanguages({ ui: 'zh', support: 'vi' });
assert.equal(probe('chrome'), '返回', 'chrome speaks the interface language');
assert.equal(probe('guide'), 'Nhấn âm tiết thứ hai.', 'guidance speaks the support language');
assert.equal(probe.lang('guide'), 'vi');
copy.setLanguages({ ui: 'vi', support: 'ko' });
assert.equal(probe('guide'), 'Stress the second syllable.', 'a support language with no pack reads English guidance, never the interface language');

console.log(`Orena copy: ${tables.size} tables, ${keys} keys, each in en/vi/zh with its layer and placeholders: PASS`);
