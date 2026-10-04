/* The one data seam of the two Grammar screens (Grammar Library, frame 44; Grammar Concept,
   frame 47) on Grammar Lab content (D-100), in the shape of docs/project/GRAMMAR_CONTENT_CONTRACT.md
   (schema v0.4).

   There is no grammar API yet: `/api/grammar/v1/*` waits for its own architecture review (D-100
   point 4) and no route is added here. Until then the content is read as static JSON under
   CONTENT_BASE, which is empty - so today every read answers "no content" (an empty catalogue, a
   point that is not found) and the screens draw the design's own empty state. When Grammar Lab's
   sample points arrive (PR B) they are placed at these paths, or this module's two readers are
   pointed at the API once it exists; neither screen changes.

     CONTENT_BASE/catalog.<target_lang>.json   the catalogue projection (contract §9): an array
                                               of rows {id, header:{native_title, native_title_
                                               pinyin?, title, sub}, level, function, sequence,
                                               point_type, error_tags, aliases}
     CONTENT_BASE/points/<id>.json             one point (contract §0-§8)

   A missing file (404) is "no content", never an error; any other failure is a load error the
   router draws as the design's Load error frame.

   Feeding rule (contract §0): only `approved` points reach the UI. This module is the feeder until
   the API exists, so it applies that rule here; the screens never filter. */
import { request } from '../infrastructure/api.js';
import { guidanceLocale } from './languages.js';

export const CONTENT_BASE = '/orena-assets/content/grammar';

const TARGETS = Object.freeze(['en', 'zh']);

async function readJson(url, fetchJson) {
  try {
    return await fetchJson(url);
  } catch (error) {
    if (error?.status === 404) return null;
    throw error;
  }
}

const defaultFetch = (url) => request(url);

/* The target language of a point id, `<lang>.<slug>` (contract §0). An R5 id has no such prefix. */
export function targetOfId(id) {
  const head = String(id || '').split('.')[0];
  return String(id || '').includes('.') && TARGETS.includes(head) ? head : '';
}

function approved(entry) {
  return entry && typeof entry === 'object' && (entry.status == null || entry.status === 'approved');
}

/* Contract §9: sorted by level.rank, function, sequence. The feeder already sorts; sorting again is
   deterministic and costs nothing. */
export function sortCatalog(rows) {
  return [...rows].sort(
    (a, b) =>
      (Number(a?.level?.rank) || 0) - (Number(b?.level?.rank) || 0) ||
      String(a?.function || '').localeCompare(String(b?.function || '')) ||
      (Number(a?.sequence) || 0) - (Number(b?.sequence) || 0),
  );
}

export async function grammarCatalog(targetLang, { fetchJson = defaultFetch } = {}) {
  const lang = TARGETS.includes(targetLang) ? targetLang : 'en';
  const rows = await readJson(`${CONTENT_BASE}/catalog.${lang}.json`, fetchJson);
  if (!Array.isArray(rows)) return [];
  return sortCatalog(rows.filter((row) => approved(row) && row.id && (row.header?.native_title || row.native_title)));
}

/* One point, by its id. An old R5 id (deep links, Writing's grammar_links, Search, Today) resolves
   through the catalogue's `aliases` (contract §9 rule 1): the answer is then `{ redirect: newId }`
   and the caller replaces the address. Nothing found is `{ point: null }`. */
export async function grammarPoint(id, { targetLang = 'en', fetchJson = defaultFetch } = {}) {
  const key = String(id || '').trim();
  if (!key) return { point: null };
  if (targetOfId(key)) {
    const point = await readJson(`${CONTENT_BASE}/points/${encodeURIComponent(key)}.json`, fetchJson);
    if (approved(point) && point.id === key && point.header?.native_title) return { point };
    return { point: null };
  }
  const catalog = await grammarCatalog(targetLang, { fetchJson });
  const owner = catalog.find((row) => Array.isArray(row.aliases) && row.aliases.includes(key));
  return owner ? { point: null, redirect: owner.id } : { point: null };
}

/* A contract locale map (`{vi, en, zh?}`) in the learner's support language (the copy layer's
   support language, D-079). `vi` and `en` are required and `zh` comes later (contract, "Locale"):
   a missing key falls back to `en`, never silently to `vi`, and a missing `en` is an empty string
   rather than another language. A plain string is target-language material and is returned as
   is. */
export function contractText(value, support = 'en') {
  if (value == null) return '';
  if (typeof value === 'string') return value;
  if (typeof value !== 'object') return '';
  // GCC authored locale maps use zh-Hans; the learner profile uses zh.
  // Resolve that contract key locally, retaining EN fallback for absent glosses.
  const target = String(support || '').toLowerCase();
  const code = (target === 'zh' || target === 'zh-hans') && Object.hasOwn(value, 'zh-Hans')
    ? 'zh-Hans' : guidanceLocale(support, Object.keys(value));
  const text = value[code] ?? value.en;
  return typeof text === 'string' ? text : '';
}

/* A level `{framework, value, rank}` (contract §0: `cefr` A1-C2 for en, `hsk3` 1-9 for zh). */
export function levelCode(level) {
  const value = String(level?.value ?? '').trim();
  if (!value) return '';
  return level?.framework === 'hsk3' ? `HSK ${value}` : value;
}
