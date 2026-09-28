/* Gate for the UI's §6.2 surface names and purposes (AGENT_CONTRACT.md, D-096): regenerates
   static/orena/copy/surfaces.json from the copy layer (scripts/build_orena_surfaces.mjs) and fails
   the build on any difference with the committed file, on a §6.1 id - read from the contract text
   itself, not from contract.js, so a text/code drift is caught by test_orena_agent.mjs and not
   silently agreed with here - missing a name in en, vi or zh-CN, or on a purpose over 90
   characters. */
import assert from 'node:assert/strict';
import fs from 'node:fs';

// The copy modules resolve the interface language at import: give them a browser to ask (see
// scripts/test_orena_copy.mjs, the same stub).
const store = new Map();
globalThis.window = { localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) } };
Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US' }, configurable: true });
globalThis.document = { documentElement: { lang: 'en', dataset: {} } };

const { surfacesDocument, surfacesJSON } = await import('./build_orena_surfaces.mjs');
const doc = surfacesDocument();

const committed = fs.readFileSync('static/orena/copy/surfaces.json', 'utf8');
assert.equal(
  surfacesJSON(),
  committed,
  'static/orena/copy/surfaces.json is stale - run `node scripts/build_orena_surfaces.mjs` and commit the file it writes',
);
assert.ok(!committed.includes('\r\n'), 'static/orena/copy/surfaces.json uses LF line endings');
assert.equal(committed.slice(-1), '\n', 'static/orena/copy/surfaces.json ends with a trailing newline');
assert.equal(doc.contract_version, 5, 'surfaces.json carries the contract version');

// Every §6.1 id, and only a §6.1 id - read from the contract text itself (docs/project/AGENT_CONTRACT.md
// §6.1), the same block scripts/test_orena_agent.mjs reads.
const text = fs.readFileSync('docs/project/AGENT_CONTRACT.md', 'utf8');
const section = (from, to) => text.slice(text.indexOf(from), text.indexOf(to, text.indexOf(from)));
const sixOne = section('### 6.1', '`{…}` are required');
const surfaceBlock = sixOne.slice(sixOne.indexOf('```text') + 7, sixOne.indexOf('```', sixOne.indexOf('```text') + 7));
const ids = [...new Set([...surfaceBlock.matchAll(/\b([a-z]+(?:\.[a-z_]+)?)(\{([^}]*)\})?/g)].map((m) => m[1]))];
assert.deepEqual(Object.keys(doc.surfaces).sort(), ids.sort(), 'every §6.1 id is published, and only §6.1 ids');

const LANGS = ['en', 'vi', 'zh-CN'];
for (const [id, entry] of Object.entries(doc.surfaces)) {
  assert.ok(entry.name, `${id}: has a name`);
  for (const lang of LANGS) {
    assert.equal(typeof entry.name[lang], 'string', `${id}: name.${lang} is text`);
    assert.ok(entry.name[lang].trim().length > 0, `${id}: name.${lang} is not empty`);
  }
  if ('purpose' in entry) {
    for (const lang of LANGS) {
      if (entry.purpose[lang] == null) continue;
      assert.equal(typeof entry.purpose[lang], 'string', `${id}: purpose.${lang} is text`);
      assert.ok(entry.purpose[lang].length <= 90, `${id}: purpose.${lang} is at most 90 characters`);
    }
  }
}

console.log(`Orena surfaces: ${Object.keys(doc.surfaces).length} §6.1 ids published with a name in en/vi/zh-CN, generated file matches the committed one: PASS`);
