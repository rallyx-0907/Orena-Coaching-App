/* The learner language contract, enforced against the learner UI's registered copy.

   Orena has three language layers and none is inferred from another (D-079): the interface language
   owns the chrome, the support language owns what explains, the learning language owns the material.
   Which layer a surface reads is locked by test_orena_language_layers.mjs and test_orena_copy_layers.mjs;
   every key carrying en/vi/zh is test_orena_copy.mjs. This gate checks that owning a key is also
   having translated it: a pack that answers with the English sentence has not answered, so a learner
   with Vietnamese or Chinese settings never reads English words in the middle of their language.

   Platform Admin is not a learner surface (the `admin` namespace) and is deliberately not held to this. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

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
const { registeredCopy, LOCALES } = await import('../static/orena/copy/index.js');
const tables = registeredCopy();

/* Words that are genuinely the same in every language: a product or framework name, a file type, a
   unit. Anything else the English words repeated in a vi/zh pack is an untranslated string. */
const SAME_IN_EVERY_LANGUAGE = new Set(['Orena', 'Orena Intelligence', 'Premium', 'Plus', 'Pro', 'API', 'Runtime', 'Video', 'Media', 'Aa', 'Pinyin', 'S', 'M', 'L', 'XP', 'CEFR A1–C2']);
const hasWords = (text) => !/^https?:/.test(String(text)) && String(text).replace(/\{\w+\}/g, '').match(/\p{L}{2,}/u) !== null;

let checked = 0;
for (const [namespace, { packs }] of tables) {
  if (namespace === 'admin') continue;
  for (const locale of ['vi', 'zh']) {
    assert.ok(LOCALES.includes(locale), `${locale} is a shipped locale`);
    const echoed = Object.keys(packs.en).filter((key) => {
      const text = packs.en[key];
      return hasWords(text) && !SAME_IN_EVERY_LANGUAGE.has(String(text).replace(/\{\w+\}/g, '').trim()) && packs[locale][key] === text;
    });
    assert.deepEqual(echoed, [], `${namespace}: the ${locale} pack repeats the English words for: ${echoed.join(', ')}`);
    checked += Object.keys(packs.en).length;
  }
}
assert.ok(checked > 1000, `the learner UI's real copy was swept (${checked} strings)`);

console.log(`Learner language: ${tables.size} tables, no English words repeated in vi/zh packs: PASS`);
