/* AGENT_CONTRACT §6.2, D-096: the UI publishes each §6.1 id's name and purpose for the server, once
   - never generated at request time and never duplicated in the intelligence lane. A name is the
   title of the route the id opens, read from the shell's own copy (agent/intents.js maps an id to a
   route; shell/routes.js names each route's title key in `crumb`; copy/shell.js holds the titles). A
   purpose is one interface-layer line, en/vi/zh-CN, at most 90 characters (Design Contract rule 50);
   this table starts empty and gets an id's purpose only once
   docs/design/canonical-ui/IMPLEMENTATION_MAP.md shows that id's screen as reviewable, so a purpose
   never describes a place that is not yet built (§6.2).

   scripts/build_orena_surfaces.mjs calls buildSurfaces() and writes static/orena/copy/surfaces.json;
   scripts/test_orena_surfaces.mjs regenerates the same data and gates the committed file against it. */
import { defineCopy, registeredCopy } from './index.js';
import { SURFACES } from '../agent/contract.js';
import { intentRoute } from '../agent/intents.js';
import { byId } from '../shell/routes.js';
import './shell.js'; // registers the 'shell' table buildSurfaces() reads names from.

/* Purposes: interface layer, ≤ 90 characters, en/vi/zh-CN. Add a §6.1 id's key here only once its
   screen is reviewable end to end (§6.2); the generator never invents one. */
export const surfacesPurpose = defineCopy('surfaces-purpose', {
  layers: {},
  en: {},
  vi: {},
  zh: {},
});

/* Wire locale code (as §6.2's JSON shape names it) → this copy layer's own pack key. */
const WIRE_LOCALES = Object.freeze({ en: 'en', vi: 'vi', 'zh-CN': 'zh' });

/* Every §6.1 id's `{ name, purpose? }`, read from the raw copy packs - never the live language
   state (copy/index.js's `current`), so this is the same regardless of what the UI happens to be
   showing when it runs. Throws if a §6.1 id has no route, or a route's title is missing a
   language - both are a copy or intents.js defect to fix, never a reason to publish a gap. */
export function buildSurfaces() {
  const tables = registeredCopy();
  const shell = tables.get('shell');
  const purpose = tables.get('surfaces-purpose');
  if (!shell) throw new Error('copy/surfaces.js: copy/shell.js has not registered its table');
  const surfaces = {};
  for (const id of Object.keys(SURFACES)) {
    const route = byId(intentRoute(id));
    if (!route) throw new Error(`copy/surfaces.js: §6.1 id "${id}" has no route (agent/intents.js)`);
    const name = {};
    for (const [wire, packKey] of Object.entries(WIRE_LOCALES)) {
      const text = shell.packs[packKey]?.[route.crumb];
      if (!text) throw new Error(`copy/surfaces.js: no ${wire} title for "${id}" (copy/shell.js "${route.crumb}")`);
      name[wire] = text;
    }
    const entry = { name };
    if (purpose) {
      const line = {};
      for (const [wire, packKey] of Object.entries(WIRE_LOCALES)) {
        const text = purpose.packs[packKey]?.[id];
        if (text) line[wire] = text;
      }
      if (Object.keys(line).length) entry.purpose = line;
    }
    surfaces[id] = entry;
  }
  return surfaces;
}
