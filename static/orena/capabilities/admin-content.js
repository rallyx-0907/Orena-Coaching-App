/* Content: the Platform Admin's rules for the three catalogues that exist - books, media (curated
   lessons and shared imports) and vocabulary collections - read from /api/admin/console/content,
   which keeps each item's own identity. No presentation. Shared by the old console
   (admin/content.js keeps its own drawer) and the new UI's Admin (screens/admin/content*.js).

   Actions appear only where a backend contract exists, and only the ones that apply from where the
   item is (`record.actions`). Nothing here deletes: taking an item back is a state - its bytes, its
   transcript, its provenance and its audit trail all survive it - so a decision can be undone. */
import { adminApi } from './admin-api.js';
import { learnerAddress } from './admin-reading.js';

export const PAGE_SIZE = 25;
export const KINDS = ['book', 'media', 'vocabulary'];
export const RIGHTS = ['public_domain', 'licensed', 'creator_authorized', 'internal_curated'];
export const COMPLETENESS = ['complete', 'partial', 'unknown'];

/* Which state each lifecycle intent asks the server for. */
export const MEDIA_STATES = { unpublish: 'unpublished', archive: 'archived', republish: 'published', restore: 'published' };
/* A collection's flow, as the human settled it. Restore goes to `unpublished` and never to
   `published`: coming back from archived returns it to the shelf, and putting it in front of
   learners again is a separate decision. */
export const COLLECTION_STATES = { publish: 'published', unpublish: 'unpublished', archive: 'archived', restore: 'unpublished' };

/* The lifecycle, in the order an operator reads it: the quiet ways off the shelf first, then the
   one that puts something in front of learners. Vocabulary publishes through its own attested
   form, so its footer never offers `publish`. */
const ORDER = ['unpublish', 'archive', 'reprocess', 'restore', 'republish', 'publish'];

export function lifecycleIntents(record) {
  const offered = new Set(record?.actions || []);
  return ORDER.filter((intent) => offered.has(intent) && !(record.kind === 'vocabulary' && intent === 'publish'));
}

/* Run one lifecycle intent. `archive` means two different things to two catalogues, so the kind
   decides, not the word: a book has its own archive route, media moves between states. */
export async function applyLifecycle(api = adminApi, kind, id, intent) {
  if (intent === 'archive' && kind === 'book') return api.archiveBook(id);
  if (intent === 'restore' && kind === 'book') return api.restoreBook(id);
  if (kind === 'vocabulary' && COLLECTION_STATES[intent]) return api.setCollectionStatus(id, COLLECTION_STATES[intent]);
  if (kind === 'media' && MEDIA_STATES[intent]) return api.setMediaStatus(id, MEDIA_STATES[intent]);
  if (intent === 'reprocess') return api.reprocessMedia(id);
  throw new Error(`Unknown lifecycle intent: ${kind} ${intent}`);
}

/* The vocabulary publish admission, as the server treats it (POST .../publish): rights and
   completeness are decision support - they warn, and the audit records them beside the decision -
   while the attestation is the one thing it refuses to go without. The checks are shown so the
   operator sees what they are about to publish over. */
export function publishChecks({ rights = '', completeness = '', attested = false } = {}) {
  const rightsOk = RIGHTS.includes(rights);
  return [
    { id: 'rights', pass: rightsOk, level: rights && rights !== 'unknown' && !rightsOk ? 'strong' : 'warning' },
    { id: 'completeness', pass: completeness === 'complete', level: 'warning' },
    { id: 'attested', pass: Boolean(attested), level: 'required' },
  ];
}

export function canPublish({ attested = false } = {}) {
  return Boolean(attested);
}

export async function publishCollection(api = adminApi, id, { rights, completeness, attested }) {
  return api.publishCollection(id, { rights_status: rights, completeness, attested: Boolean(attested) });
}

export async function loadContent(api = adminApi, { kind = '', q = '', language = '', status = '', sort = 'updated', offset = 0 } = {}) {
  return api.content({ kind, q, language, status, sort, limit: PAGE_SIZE, offset });
}

/* The counts on Content home: the three catalogues the content endpoint owns, and Reading's own
   (it keeps its own lifecycle and endpoint, so the number comes from there). */
export async function contentCounts(api = adminApi) {
  const [shared, reading] = await Promise.allSettled([api.content({ limit: 1, offset: 0 }), api.readingOperations()]);
  const counts = shared.status === 'fulfilled' ? { ...(shared.value.counts || {}) } : {};
  const statusCounts = shared.status === 'fulfilled' ? { ...(shared.value.status_counts || {}) } : {};
  if (reading.status === 'fulfilled') {
    const articles = reading.value.articles || {};
    counts.reading = Object.values(articles).reduce((total, value) => total + Number(value || 0), 0);
    counts.reading_review = Number(articles.needs_review || 0) + Number(articles.ready || 0) + Number(articles.draft || 0);
    counts.reading_published = Number(articles.published || 0);
  }
  return { counts, statusCounts, readingAvailable: reading.status === 'fulfilled' };
}

/* Where a learner opens a record in the new UI (the server builds the old UI's address, which is of
   no use here): books at their first chapter, media as a lesson. Vocabulary has no learner page of
   its own in the new UI - it is reached through My Library. */
export function learnerLink(record, detail) {
  if (record.status !== 'published') return '';
  if (record.kind === 'book') {
    const first = (detail?.book?.chapters || [])[0];
    return first ? learnerAddress('book', record.id, first.id) : '';
  }
  if (record.kind === 'media') return learnerAddress('media', record.id);
  return '';
}

/* The mono tile letters and the kind a record is filed under in the design. */
export const KIND_TILE = { book: 'B', media: 'V', vocabulary: 'W', reading: 'R' };
