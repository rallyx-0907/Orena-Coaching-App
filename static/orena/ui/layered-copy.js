/* A copy table read by semantic layer (D-079). Each key comes from the pack of its declared layer:
   interface keys from the interface language, support keys from the support language's pack - or
   English, the documented fallback, when Orena has none for it; never the interface language instead.
   The layer of every key is declared in ./copy-layers.js; there is no default. A key missing from
   the declarations reads in English and is reported once on the console, and the gate
   (scripts/test_orena_copy_layers.mjs) fails on it before it can ship. */
import { guidanceLocale } from '../product/languages.js';

const cache = new WeakMap();
const reported = new Set();

export function layeredCopy(packs, layers, ui, support) {
  const codes = Object.keys(packs);
  const uiCode = packs[ui] ? ui : 'en';
  const guideCode = guidanceLocale(support, codes);
  let byTable = cache.get(packs);
  if (!byTable) cache.set(packs, (byTable = new Map()));
  const id = `${uiCode}|${guideCode}`;
  if (byTable.has(id)) return byTable.get(id);

  const base = packs.en;
  const chrome = packs[uiCode];
  const guide = packs[guideCode];
  const keys = new Set(codes.flatMap((code) => Object.keys(packs[code])));
  const out = {};
  const undeclared = [];
  for (const key of keys) {
    const layer = layers[key];
    if (layer === 'support') out[key] = guide[key] ?? base[key];
    else if (layer === 'interface') out[key] = chrome[key] ?? base[key];
    else {
      out[key] = base[key];
      undeclared.push(key);
    }
  }
  if (undeclared.length && !reported.has(packs)) {
    reported.add(packs);
    console.error(`[Orena copy] ${undeclared.length} keys have no declared language layer: ${undeclared.slice(0, 12).join(', ')}`);
  }
  // Which language a key was rendered in, for its element's `lang`.
  Object.defineProperty(out, 'langOf', { value: (key) => (layers[key] === 'support' ? guideCode : layers[key] === 'interface' ? uiCode : 'en') });
  Object.defineProperty(out, 'uiLang', { value: uiCode });
  Object.defineProperty(out, 'guideLang', { value: guideCode });
  byTable.set(id, out);
  return out;
}
