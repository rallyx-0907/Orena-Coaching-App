/* The one data seam of the two Grammar screens (Grammar Library, frame 44; Grammar Concept,
   frame 47) on Grammar Lab content (D-100), in the shape of docs/project/GRAMMAR_CONTENT_CONTRACT.md
   (schema v0.4), read from the Grammar Store's learner API (`writing_coach/grammar_api.py`,
   GRAMMAR_CONTENT_STORE rev 3):

     GET  /api/grammar/v1/points               the published catalogue of the session's learning
                                               language: `{language, catalog_revision, functions,
                                               levels, points}`; each row is the contract §9
                                               projection {id, header, level, function, sequence,
                                               point_type, error_tags, aliases, content_hash}
     GET  /api/grammar/v1/points/<id>          one published point `{point, version, content_hash}`;
                                               an old R5 id answers `{point: null, redirect}` (or
                                               `dropped` / `unavailable`), resolved by the server's R5 map
     GET  /api/grammar/v1/progress             the learner's completed points `{progress: [...]}`
     PUT  /api/grammar/v1/progress/<id>        completion, with the quiz answers the server grades

   The learning language is the session's, as for every learner API: `targetLang` only guards against
   drawing another language's catalogue. A 404 is "no content" (an empty catalogue, a point that is not
   found), never an error; any other failure is a load error the router draws as the design's Load error.

   Feeding rule (contract §0): only `approved` points reach the UI. The store serves only published
   versions of approved points; the seam keeps the check so nothing else can reach the screens. */
import { request } from '../infrastructure/api.js';
import { guidanceLocale } from './languages.js';

export const GRAMMAR_API = '/api/grammar/v1';
export const CATALOG_URL = `${GRAMMAR_API}/points`;
export const PROGRESS_URL = `${GRAMMAR_API}/progress`;
export const pointUrl = (id) => `${GRAMMAR_API}/points/${encodeURIComponent(id)}`;

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
  const body = await readJson(CATALOG_URL, fetchJson);
  const rows = Array.isArray(body?.points) ? body.points : [];
  if (body?.language && body.language !== lang) return [];
  return sortCatalog(rows.filter((row) => approved(row) && row.id && (row.header?.native_title || row.native_title)));
}

/* One point, by its id. An old R5 id (deep links, Writing's grammar_links, Search, Today) is resolved
   by the server's R5 map (contract §9 rule 1): the answer is then `{ redirect: newId }` and the caller
   replaces the address. A dropped or not-yet-published R5 id, and anything else not found, is
   `{ point: null }`. `version` is the published version the learner reads. */
export async function grammarPoint(id, { targetLang = 'en', fetchJson = defaultFetch } = {}) {
  const key = String(id || '').trim();
  if (!key) return { point: null };
  const owner = targetOfId(key);
  if (owner && owner !== targetLang) return { point: null };
  const body = await readJson(pointUrl(key), fetchJson);
  if (!body) return { point: null };
  const redirect = typeof body.redirect === 'string' && targetOfId(body.redirect) ? body.redirect : '';
  if (redirect) return { point: null, redirect };
  const point = body.point;
  if (approved(point) && point.header?.native_title && (!owner || point.id === key)) return { point, version: body.version ?? null };
  return { point: null };
}

/* The learner's completed grammar points: `[{point_id, completed_at, last_quiz, via}]`. A failure reads as
   no progress, never as a load error: progress is an addition to a screen, not its content. */
export async function grammarProgress({ fetchJson = defaultFetch } = {}) {
  try {
    const body = await readJson(PROGRESS_URL, fetchJson);
    return Array.isArray(body?.progress) ? body.progress : [];
  } catch {
    return [];
  }
}

const defaultSend = (url, body) =>
  request(url, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

/* Completion of a point, with the quiz answers in `quick_practice` order (`null` for a question the screen
   did not ask). The server grades them from the published key; the client's own score is never sent. */
export function recordGrammarCompletion(id, answers, { send = defaultSend } = {}) {
  return send(`${PROGRESS_URL}/${encodeURIComponent(String(id || ''))}`, { answers: Array.isArray(answers) ? answers : null });
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
