/* Writes static/orena/copy/surfaces.json from the copy layer (AGENT_CONTRACT §6.2, D-096):
   `{ contract_version, surfaces: { <§6.1 id>: { name: {en, vi, "zh-CN"}, purpose?: {...} } } }`,
   contract locale codes, stable key order (the order §6.1 declares the ids), LF, trailing newline.

   Run directly after changing a route's title (shell/routes.js, copy/shell.js) or a purpose
   (copy/surfaces.js), and commit the file it writes:

     node scripts/build_orena_surfaces.mjs

   scripts/test_orena_surfaces.mjs imports `surfacesDocument`/`surfacesJSON` from here to regenerate
   the same data in memory and fails the build when the committed file drifts from it - so importing
   this module never has the side effect of writing the file; only running it directly does. */
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

// copy/index.js resolves the interface language at import; give it a browser to ask. This script
// never reads the live language state (buildSurfaces() reads the raw packs), but every copy module
// still needs these globals to import cleanly under plain Node.
const store = new Map();
globalThis.window = { localStorage: { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) } };
if (!('navigator' in globalThis) || !globalThis.navigator?.languages) {
  Object.defineProperty(globalThis, 'navigator', { value: { languages: ['en-US'], language: 'en-US' }, configurable: true });
}
globalThis.document = globalThis.document || { documentElement: { lang: 'en', dataset: {} } };

const { CONTRACT_VERSION } = await import('../static/orena/agent/contract.js');
const { buildSurfaces } = await import('../static/orena/copy/surfaces.js');

export function surfacesDocument() {
  return { contract_version: CONTRACT_VERSION, surfaces: buildSurfaces() };
}

export function surfacesJSON() {
  return `${JSON.stringify(surfacesDocument(), null, 2)}\n`;
}

const isMain = process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1];
if (isMain) {
  const doc = surfacesDocument();
  writeFileSync('static/orena/copy/surfaces.json', surfacesJSON());
  console.log(`static/orena/copy/surfaces.json written: ${Object.keys(doc.surfaces).length} §6.1 ids, contract_version ${doc.contract_version}.`);
}
