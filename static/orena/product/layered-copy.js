/* A copy table read by semantic layer (D-079). Each key comes from the pack of its declared layer:
   interface keys from the interface language, support keys from the support language's pack - or
   English, the documented fallback, when Orena has none for it; never the interface language instead.
   The layer of every key is declared in ./copy-layers.js; there is no default. A key missing from
   the declarations reads in English and is reported once on the console, and the gate
   (scripts/test_orena_copy_layers.mjs) fails on it before it can ship. */
import { guidanceLocale } from './languages.js';

const cache = new WeakMap();
const reported = new Set();
// CLDR plural categories other than `other`, as a key suffix (`x_one`, `x_few`, ...).
const PLURAL_FORM = /_(zero|one|two|few|many)$/;

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
  /* A plural key (`x_one`, `x_other`) may declare its layer once, under its bare name `x`, as
     scripts/test_orena_copy.mjs accepts; without this every such key read as undeclared, in English. */
  const layerOf = (key) => layers[key] || layers[key.replace(/_(zero|one|two|few|many|other)$/, '')];
  for (const key of keys) {
    const layer = layerOf(key);
    const own = layer === 'support' ? guide : layer === 'interface' ? chrome : null;
    /* A plural form other than `_other` is its language's own grammar. It is never borrowed from
       English: Vietnamese and Chinese have no singular, so an English `_one` back-filled here would
       put an English sentence in a vi/zh interface at n === 1. `_other` falls back like any key. */
    if (own && PLURAL_FORM.test(key)) {
      if (own[key] != null) out[key] = own[key];
    } else if (own) out[key] = own[key] ?? base[key];
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
  Object.defineProperty(out, 'langOf', { value: (key) => (layerOf(key) === 'support' ? guideCode : layerOf(key) === 'interface' ? uiCode : 'en') });
  Object.defineProperty(out, 'uiLang', { value: uiCode });
  Object.defineProperty(out, 'guideLang', { value: guideCode });
  byTable.set(id, out);
  return out;
}
