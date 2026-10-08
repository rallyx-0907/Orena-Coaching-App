/* Imports: the Platform Admin's rules for bringing content in - books, media, vocabulary, Reading
   sources - and for reading what came of it. No presentation. Shared by the old console
   (admin/imports.js re-exports the pure parts) and the new UI's Admin (screens/admin/imports*.js).

   Each flow is the existing importer, used as it was built: EPUBs through the reading library
   importer, links and files through the media source importer, vocabulary sources through the
   admission-checked vocabulary importer. Books and media go one item per request, so every item
   shows its own progress and one failure never holds up the rest; a vocabulary batch is one request
   because publication is decided for the collection as a whole. */
import { adminApi } from './admin-api.js';

export const HISTORY_PAGE = 20;
export const VOCABULARY_FIELDS = [
  'term', 'short_meaning', 'reading', 'pronunciation', 'part_of_speech', 'example', 'level',
  'detailed_definition', 'usage', 'framework', 'topic', 'meaning_language', 'target_language', 'orthography', 'sense_key',
];
/* The fields a mapping shows first; the rest sit behind "more fields". */
export const PRIMARY_FIELDS = 7;
/* The level scales the media library accepts per learning language (media_library_store.validate_entry);
   any other value is refused there. */
export const MEDIA_LEVELS = {
  en: ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'],
  zh: ['HSK1', 'HSK2', 'HSK3', 'HSK4', 'HSK5', 'HSK6', 'HSK7-9'],
};
/* The ways the schema (`ck_reading_source_type`) lets content arrive. */
export const SOURCE_TYPES = ['direct_url', 'rss', 'feed', 'api', 'manual', 'file'];
export const RIGHTS_STATUSES = ['public_domain', 'licensed', 'creator_authorized', 'internal_curated'];

/* Run `worker` over `items` one at a time. Each item moves queued -> processing -> its outcome, and
   a thrown error is that item's failure, never the queue's. */
export async function runQueue(items, worker, onUpdate = () => {}) {
  for (const item of items) item.state = 'queued';
  onUpdate(items);
  for (const item of items) {
    item.state = 'processing';
    onUpdate(items);
    try {
      Object.assign(item, await worker(item));
    } catch (error) {
      Object.assign(item, { state: 'failed', code: error?.category || 'unknown', message: error?.message || '' });
    }
    onUpdate(items);
  }
  return items;
}

export function bookOutcome(row) {
  if (row?.status === 'ok') return { state: 'published', title: row.title, chapters: row.chapter_count, contentId: row.book_id };
  if (row?.status === 'duplicate') return { state: 'duplicate', title: row.title, contentId: row.book_id };
  return { state: 'failed', code: row?.category || 'unknown', stage: row?.stage || 'parse' };
}

export function mediaOutcome(row) {
  // The server keys an uploaded file by its content: the same bytes again are the item already in
  // the library, not a failure and not a second copy.
  if (row?.status === 'duplicate') return { state: 'duplicate', contentId: row.media_id };
  if (row?.status === 'ok') {
    return { state: 'published', contentId: row.media_id, has_transcript: row.has_transcript ?? null, segment_count: row.segment_count ?? null };
  }
  /* The importer's stable category, so the console says it in the operator's language instead of
     quoting an English sentence back at them. The server's `detail` stays as the fallback. */
  return { state: 'failed', code: row?.category || 'source', stage: 'source', message: row?.detail || '' };
}

/* An accepted import is not a finished lesson. Reconcile with the same content
   record the operator opens, including asynchronous transcript processing. */
export function mediaProcessingOutcome(detail) {
  const record = detail.record || {};
  const processing = record.processing || {};
  const segment_count = detail.transcript?.segment_count;
  const state = ['queued', 'running'].includes(processing.state) ? 'processing'
    : processing.state === 'failed' ? 'failed'
      : ['published', 'review', 'archived', 'unpublished'].includes(record.status) ? record.status : 'unpublished';
  return { state, stage: processing.stage || '', code: processing.reason || '',
    message: processing.detail || '', processing, has_transcript: segment_count > 0, segment_count };
}

export function defaultCollectionTitle(filename) {
  const stem = String(filename || '').replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim();
  return stem ? stem[0].toLocaleUpperCase() + stem.slice(1) : '';
}

/* What stops a vocabulary import from being sent: [{ key, file? }], each key a copy key. */
export function vocabularyProblems({ files = [], previews = [], mappings = {}, metadata = {} }) {
  const problems = [];
  if (!files.length) problems.push({ key: 'validationFiles' });
  if (!String(metadata.title || '').trim()) problems.push({ key: 'validationTitle' });
  for (const preview of previews) {
    if (preview.error) continue;
    if (!mappings[preview.filename]?.term) problems.push({ key: 'validationTerm', file: preview.filename });
  }
  if (metadata.publish && !metadata.attested) problems.push({ key: 'validationAttest' });
  return problems;
}

/* The engine keys a source by slug, and an operator types a name. One is derived from the other
   rather than asked for twice. */
export function slugFor(name) {
  const base = String(name || '')
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 120);
  return base || `source-${Date.now().toString(36)}`;
}

/* The POST /api/admin/reading/sources body for a registered source. The engine insists on creating
   it waiting for review; an operator approves it in Reading -> Sources. */
export function sourceBody({ name, url = '', type = 'direct_url', language = 'en', rights = {}, license = '' }) {
  return {
    slug: slugFor(name),
    name: String(name).trim(),
    source_type: type,
    base_url: String(url).trim(),
    languages: [language],
    automation_allowed: Boolean(rights.automation_allowed),
    can_republish: Boolean(rights.can_republish),
    can_adapt: Boolean(rights.can_adapt),
    attribution_required: rights.attribution_required !== false,
    license_note: license,
  };
}

/* The vocabulary import's metadata, as the endpoint takes it. */
export function vocabularyMetadata(meta) {
  return {
    title: String(meta.title || '').trim(),
    language_code: meta.language,
    meaning_language: meta.meaning_language,
    framework: meta.framework,
    level: meta.level,
    topic: meta.topic,
    collection_id: meta.collection_id,
    rights_status: meta.rights_status,
    completeness: meta.completeness,
    publish: Boolean(meta.publish),
    publication_attested: Boolean(meta.publish && meta.attested),
  };
}

/* ---- the flows: each one is a request, an outcome, and nothing drawn ------------------------ */

export async function importBooks(api = adminApi, items, language, onUpdate) {
  return runQueue(items.filter((item) => item.state === 'to_import'), async (item) => {
    const response = await api.importBook(item.file, language);
    return bookOutcome((response.results || [])[0]);
  }, onUpdate);
}

/* A link's preview: one row per URL, `ready` when the provider answered, `failed` with the reason
   when it did not. Nothing is stored. */
export async function checkMediaUrls(api = adminApi, urls, language) {
  try {
    const response = await api.mediaPreview(urls, language);
    return (response.items || []).map((row) => (row.status === 'ok'
      ? { ...row, name: row.url, state: 'ready', tags: [] }
      : { url: row.url, name: row.url, state: 'failed', code: 'source', stage: 'source', message: row.detail }));
  } catch (error) {
    return urls.map((url) => ({ url, name: url, state: 'failed', code: error?.category || 'unknown', message: error?.message || '' }));
  }
}

export async function importMedia(api = adminApi, items, language, onUpdate, { rightsCleared = false } = {}) {
  const pending = items.filter((item) => item.state === 'ready' || (item.file && item.state === 'to_import'));
  return runQueue(pending, async (item) => {
    if (item.file) {
      const response = await api.importMediaFile(item.file, language, rightsCleared);
      return mediaOutcome((response.items || [])[0]);
    }
    const response = await api.importMediaUrl({
      url: item.url,
      title: item.title || null,
      level: item.level || null,
      topic: item.topic || null,
      tags: item.tags || [],
      // Only a confirmation is sent; an unconfirmed import leaves rights to the source policy and review.
      rights_cleared: rightsCleared ? true : null,
    }, language);
    return mediaOutcome((response.items || [])[0]);
  }, onUpdate);
}

/* Read the files and propose a column mapping for each; the operator confirms it. */
export async function previewVocabulary(api = adminApi, files) {
  const response = await api.vocabularyPreview(files);
  const previews = response.items || [];
  const mappings = {};
  for (const preview of previews) if (!preview.error) mappings[preview.filename] = { ...(preview.detected_mapping || {}) };
  return { previews, mappings, title: defaultCollectionTitle(files[0]?.name) };
}

export async function importVocabulary(api = adminApi, { files, metadata, mappings }) {
  return api.vocabularyImport(files, vocabularyMetadata(metadata), mappings);
}

export async function loadHistory(api = adminApi, { kind = '', status = '', offset = 0 } = {}) {
  return api.history({ kind, status, limit: HISTORY_PAGE, offset });
}

export async function loadJobs(api = adminApi, { status = '', cursor = '', limit = 25 } = {}) {
  return api.readingJobs({ status, cursor, limit });
}
