/* Every learner copy string is read by its semantic layer (D-079). For every table the learner UI
   registers (copy/*.js, screens/<name>/copy.js, agent/copy.js) this gate fails when:
   - the layered copy a screen reads returns any key from the wrong language's pack (swept over
     every key of every table, for the human's cases A, B and C);
   - a support language Orena has no pack for reads its guidance in anything but English;
   That every key declares a layer and carries en/vi/zh is scripts/test_orena_copy.mjs. */
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
  ...fs.readdirSync('static/orena/screens').map((d) => path.join('static/orena/screens', d, 'copy.js')).filter((f) => fs.existsSync(f)),
  ...(fs.existsSync('static/orena/agent/copy.js') ? ['static/orena/agent/copy.js'] : []),
];
for (const file of modules) await import(pathToFileURL(path.resolve(file)).href);
const { layeredCopy } = await import('../static/orena/product/layered-copy.js');
const { registeredCopy } = await import('../static/orena/copy/index.js');

const tables = registeredCopy();
assert.ok(tables.size > 10, 'the learner UI registers its copy tables');

for (const [table, { packs, layers }] of tables) {
  const keys = new Set(Object.values(packs).flatMap((pack) => Object.keys(pack)));
  const layerOf = (key) => layers[key] || layers[key.replace(/_(zero|one|two|few|many|other)$/, '')];
  // The copy a screen reads: every key from the pack of its layer, for A, B and C.
  for (const [ui, support] of [['en', 'vi'], ['vi', 'vi'], ['zh', 'en']]) {
    const read = layeredCopy(packs, layers, ui, support);
    for (const key of keys) {
      const layer = layerOf(key);
      assert.ok(layer === 'interface' || layer === 'support', `${table}.${key} has a declared language layer`);
      const from = layer === 'support' ? support : ui;
      const own = packs[from]?.[key];
      if (/_(zero|one|two|few|many)$/.test(key)) {
        // A plural form other than _other is the language's own grammar, never borrowed from English.
        assert.equal(read[key], own, `${table}.${key} (${layer}) for ui ${ui} / support ${support}`);
      } else assert.equal(read[key], own ?? packs.en[key], `${table}.${key} (${layer}) for ui ${ui} / support ${support}`);
    }
    // A support language Orena has no pack for: guidance in English, never in the interface language.
    const ja = layeredCopy(packs, layers, ui, 'ja');
    for (const key of keys)
      if (layerOf(key) === 'support' && !/_(zero|one|two|few|many)$/.test(key)) assert.equal(ja[key], packs.en[key] ?? ja[key], `${table}.${key} for support ja`);
  }
}

console.log(`Copy layers: ${tables.size} learner tables read from the right language for A/B/C: PASS`);
