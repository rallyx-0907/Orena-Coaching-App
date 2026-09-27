/* Gate for the copy engine both learner UIs read through (product/layered-copy.js, D-079) and the
   new UI's placeholders and plural path (copy/index.js).

   A placeholder takes any given value, 0 included: "{n} due" once read literally at zero. A plural
   form is chosen by the plural rules of the language the key renders in (Intl.PluralRules), never
   by which forms a resolved table happens to hold. English has `_one`; Vietnamese and Chinese have
   no singular and read `_other` at every n. The layered table never back-fills a vi/zh `_one` from
   English - that back-fill is what put "1 result" in a Chinese interface. And the new UI chooses a
   plural form in one place only: no module outside copy/index.js picks `_one` itself. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

// copy/index.js resolves the interface language at import: give it a browser to ask.
const store = new Map();
globalThis.window = { localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) } };
Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US' }, configurable: true });
globalThis.document = { documentElement: { lang: 'en', dataset: {} } };

const { layeredCopy } = await import('../static/orena/product/layered-copy.js');
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

// 1. The layered table: a vi/zh pack without `_one` gets none; `_other` and plain keys fall back.
const packs = {
  en: { result_one: '{n} result', result_other: '{n} results', note_one: '{n} note', note_other: '{n} notes', only_en: 'English only' },
  vi: { result_other: '{n} kết quả', note_other: '{n} ghi chú' },
  zh: { result_other: '{n} 个结果', note_other: '{n} 条笔记' },
};
const layers = { result: 'interface', note: 'support', only_en: 'interface' };
for (const ui of ['vi', 'zh']) {
  const table = layeredCopy(packs, layers, ui, ui);
  assert.equal(table.result_one, undefined, `${ui}: no English singular back-filled into an interface plural`);
  assert.equal(table.note_one, undefined, `${ui}: no English singular back-filled into a support plural`);
  assert.equal(table.result_other, packs[ui].result_other, `${ui}: the language's own plural`);
  assert.equal(table.only_en, 'English only', `${ui}: a missing plain key still falls back to English`);
  assert.equal(table.langOf('result_other'), ui, `${ui}: a plural key declared under its bare name has its layer`);
}
const english = layeredCopy(packs, layers, 'en', 'en');
assert.equal(english.result_one, '{n} result', 'English keeps its singular');
// A support language Orena has no pack for reads English, the documented fallback - singular included.
const fallback = layeredCopy(packs, layers, 'vi', 'fr');
assert.equal(fallback.note_one, '{n} note', 'support fallback to English keeps English grammar');
assert.equal(fallback.result_one, undefined, 'the vi interface layer still has no singular');

// 2. copy/index.js plural(): vi and zh at n = 0, 1, 2; English at n = 0, 1, 2.
const t = copy.defineCopy('test.copy-engine', {
  layers: { result: 'interface', note: 'support' },
  en: { result_one: '{n} result', result_other: '{n} results', note_one: '{n} note', note_other: '{n} notes' },
  vi: { result_other: '{n} kết quả', note_other: '{n} ghi chú' },
  zh: { result_other: '{n} 个结果', note_other: '{n} 条笔记' },
});
const expect = {
  en: ['0 results', '1 result', '2 results'],
  vi: ['0 kết quả', '1 kết quả', '2 kết quả'],
  zh: ['0 个结果', '1 个结果', '2 个结果'],
};
for (const [ui, forms] of Object.entries(expect)) {
  copy.setLanguages({ ui, support: ui });
  forms.forEach((form, n) => assert.equal(t.plural('result', n), form, `${ui} interface, n=${n}`));
  forms.forEach((form, n) => assert.equal(t.plural('note', n), { en: ['0 notes', '1 note', '2 notes'], vi: ['0 ghi chú', '1 ghi chú', '2 ghi chú'], zh: ['0 条笔记', '1 条笔记', '2 条笔记'] }[ui][n], `${ui} support, n=${n}`));
}
// The layers stay independent: an English interface with Vietnamese support.
copy.setLanguages({ ui: 'en', support: 'vi' });
assert.equal(t.plural('result', 1), '1 result', 'interface key follows the English interface');
assert.equal(t.plural('note', 1), '1 ghi chú', 'support key follows Vietnamese support, not English grammar');
copy.setLanguages({ ui: 'zh', support: 'en' });
assert.equal(t.plural('result', 1), '1 个结果', 'interface key follows the Chinese interface');
assert.equal(t.plural('note', 1), '1 note', 'support key follows English support');
copy.setLanguages({ ui: 'en', support: 'en' });

// 3. One plural path: no new-UI module outside copy/index.js picks a plural form itself - no
//    `x_one` read by name, no `'one' : 'other'` suffix chosen by hand, no `n === 1 ? 'xOne' :
//    'xOther'` pair of keys. (Copy tables declare their keys as object properties, which this does
//    not match; comments are not code.)
const PICKS = [
  /(['"`])[\w.]*_(?:zero|one|two|few|many)\1(?!\s*:)/g,
  /\?\s*(['"`])_?one\1\s*:\s*(['"`])_?other\2/g,
  /===\s*1\s*\?\s*(['"`])[\w.]*One\1\s*:\s*(['"`])[\w.]*Other\2/g,
];
const code = (source) => source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`\\])\/\/.*$/gm, '$1');
const NEW_UI = ['main.js', 'shell', 'kit', 'screens', 'agent', 'copy'].map((p) => path.join('static/orena', p)).filter((p) => fs.existsSync(p));
const files = [];
const walk = (p) => {
  if (fs.statSync(p).isDirectory()) for (const name of fs.readdirSync(p)) walk(path.join(p, name));
  else if (p.endsWith('.js')) files.push(p);
};
NEW_UI.forEach(walk);
const own = path.join('static/orena/copy/index.js');
const offenders = [];
for (const file of files) {
  if (path.normalize(file) === path.normalize(own)) continue;
  const source = code(fs.readFileSync(file, 'utf8'));
  const found = PICKS.flatMap((pattern) => [...source.matchAll(pattern)].map((m) => m[0]));
  if (found.length) offenders.push(`${file}: ${found.join(', ')}`);
}
assert.deepEqual(offenders, [], 'plural forms are chosen only by copy/index.js (use t.plural)');

console.log(`Orena copy engine: a 0 fills its placeholder, plural forms follow each language's rules (en/vi/zh at n=0,1,2, both layers), no English singular back-filled, ${files.length} new-UI modules use the one plural path: PASS`);
