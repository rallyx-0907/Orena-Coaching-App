/* The learner's own records kept with the account, while the deployment keeps work there (D4 I5, I6,
   I8-I10, I12; D-104 H-18): conversation turns, notes and highlights, private imports, typed and
   Reading Transfer responses, and where a kept word was met.

   The device is always the cache and the fallback, so nothing here can lose words:
   - the deployment says whether it keeps work (`/api/account-backbone`): only `active` writes anywhere,
     every other answer leaves the device as the only holder and nothing claims a save;
   - every write is best effort and silent on failure (the device already holds the record);
   - nothing is uploaded in bulk (D-104 H-6): a device value is written when the learner next touches
     it, and a device value the server does not hold stays readable;
   - a 409 means another device moved first. Notes and highlights are a set, so the client unions by id
     and writes again once; everything else re-reads and stops rather than overwrite.

   `api` is injected so scripts/test_orena_account_records.mjs can run the whole thing against a stub. */
import { api as realApi } from '../infrastructure/api.js';
import { accountWorkState } from './draft-sync.js';

let apiRef = realApi;
export function useApi(next) {
  apiRef = next || realApi;
}

export async function recordsActive() {
  return (await accountWorkState(apiRef)) === 'active';
}

const operationId = () => `op-${crypto.randomUUID()}`;

/* ------------------------------------------------------------------ notes and highlights ---- */

/* The server bounds (proposal I10): 80 highlights of 400 characters, 120 notes of 600. */
export const ANNOTATION_LIMITS = Object.freeze({ highlights: 80, highlightChars: 400, notes: 120, noteChars: 600 });

const versions = new Map(); // content id -> the annotation version this device last agreed on
const removed = new Map(); // content id -> ids the learner removed in this visit (a union must not bring them back)

export function forgetRecordState() {
  versions.clear();
  removed.clear();
  convoHeads.clear();
  convoQueues.clear();
  importVersions.clear();
  mediaRecords.clear();
}

export function noteRemoved(contentId, id) {
  if (!removed.has(contentId)) removed.set(contentId, new Set());
  removed.get(contentId).add(id);
}

/* The ids this device removed in this visit and has not yet seen the server acknowledge. */
export function removedIds(contentId) {
  return new Set(removed.get(contentId) || []);
}

const byId = (list) => new Map((Array.isArray(list) ? list : []).map((item) => [item.id, item]));

/* A set union by id; the first list wins on a shared id, and ids the learner removed stay removed. */
export function unionById(first, second, gone = new Set()) {
  const merged = byId(first);
  for (const [id, item] of byId(second)) if (!merged.has(id)) merged.set(id, item);
  return [...merged.values()].filter((item) => !gone.has(item.id));
}

const boundHighlights = (list) => list.slice(-ANNOTATION_LIMITS.highlights).map((item) => ({
  id: String(item.id), segment: String(item.segment || '').slice(0, 255),
  sentence: String(item.sentence || '').slice(0, ANNOTATION_LIMITS.highlightChars), at: String(item.at || '').slice(0, 40),
}));
const boundNotes = (list) => list.slice(-ANNOTATION_LIMITS.notes).map((item) => ({
  id: String(item.id), key: String(item.key || '').slice(0, 255), type: ['factual', 'reflection', 'question'].includes(item.type) ? item.type : 'reflection',
  text: String(item.text || '').slice(0, ANNOTATION_LIMITS.noteChars), at: String(item.at || '').slice(0, 40),
}));

/* What the server holds for this text, or null (nothing kept, or the deployment does not keep work). */
export async function pullAnnotations(contentId) {
  if (!contentId || !(await recordsActive())) return null;
  try {
    const { annotation } = await apiRef.annotations(contentId);
    versions.set(contentId, annotation.version);
    return annotation;
  } catch (error) {
    if (error?.status === 404) versions.set(contentId, 0);
    return null;
  }
}

/* Write this device's set for one text against the version this device read. A 409 means another device moved
   first: the server's set is re-read and merged - its items, plus this device's own NEW items - never an item
   the server remembers as removed (its tombstones) nor one this learner just removed, and the write is made
   once more against the fresh version. `onMerged(set)` hands the merged set back so the device's own store is
   brought in line (a removal made elsewhere must leave this device too). */
export async function pushAnnotations(contentId, { highlights, notes }, { onMerged } = {}) {
  if (!contentId || !(await recordsActive())) return false;
  let mine = { highlights: boundHighlights(highlights || []), notes: boundNotes(notes || []) };
  for (let attempt = 0; attempt < 2; attempt += 1) {
    if (!versions.has(contentId)) await pullAnnotations(contentId);
    try {
      const saved = await apiRef.saveAnnotations(contentId, { operationId: operationId(), expectedVersion: versions.get(contentId) ?? 0, ...mine });
      versions.set(contentId, saved.version);
      removed.delete(contentId); // the server has the removals now, as tombstones
      return true;
    } catch (error) {
      if (error?.status !== 409 && error?.status !== 422) return false;
      const server = await pullAnnotations(contentId);
      if (!server) return false;
      const gone = new Set([...(removed.get(contentId) || []), ...(server.tombstones || [])]);
      mine = {
        highlights: boundHighlights(unionById(server.highlights, mine.highlights, gone)),
        notes: boundNotes(unionById(server.notes, mine.notes, gone)),
      };
      onMerged?.(mine, server);
    }
  }
  return false;
}

/* ----------------------------------------------------------------------------- conversations ---- */

const convoHeads = new Map(); // conversation key -> turns the server holds, as this device knows
const convoQueues = new Map(); // conversation key -> the promise the next append waits behind

/* Append one turn after the ones before it (a queue per conversation keeps the order). Stops for good
   on anything but success: the device keeps the whole conversation either way. */
export function appendConversationTurn(key, turn, { title = '', situation = '', ended = false } = {}) {
  const previous = convoQueues.get(key) || Promise.resolve(true);
  const next = previous.then(async (healthy) => {
    if (!healthy || !(await recordsActive())) return false;
    const head = convoHeads.get(key) ?? 0;
    try {
      const saved = await apiRef.appendConversationTurn(key, {
        operationId: operationId(), expectedHead: head, id: turn.id, role: turn.role, text: turn.text,
        replyTo: turn.reply_to || null, origin: turn.origin || '', meaning: turn.meaning || '', support: turn.support || '',
        title, situation, ended,
      });
      convoHeads.set(key, saved.head);
      return true;
    } catch {
      return false;
    }
  });
  convoQueues.set(key, next);
  return next;
}

/* A conversation kept with the account, in the shape product/conversation.js restores, or null. */
export async function loadConversation(key, language) {
  if (!key || !(await recordsActive())) return null;
  try {
    const { conversation } = await apiRef.conversationRecord(key);
    convoHeads.set(key, conversation.head);
    return {
      id: key, language, title: conversation.title, situation: conversation.situation, ended: conversation.ended,
      turns: conversation.turns.map((turn) => ({
        id: turn.id, role: turn.role, text: turn.text, origin: turn.origin || (turn.role === 'partner' ? 'generated' : 'typed'),
        reply_to: turn.role === 'partner' ? turn.reply_to : null, meaning: turn.meaning || '', support: turn.support || '',
      })),
    };
  } catch {
    return null;
  }
}

/* --------------------------------------------------------------------------------- imports ---- */

const importVersions = new Map(); // import uuid -> the version the server holds

const importUuid = (id) => String(id || '').replace(/^(text|url|upload):/, '');

/* A media import's membership id is `url:<the link>` or `upload:<the stored media id>`, not a UUID, so its record id
   is minted when it is kept (a removed import is a terminal tombstone: the same link can be kept again later under a
   new record). This device learns which record(s) hold a membership id when it keeps one or reads the account's list;
   two devices that kept the same link both leave a record, and removing the membership removes every one of them. */
const isMedia = (id) => /^(url|upload):/.test(String(id || ''));
const mediaRecords = new Map(); // membership id -> record uuids the account holds for it

/* The body that keeps a media import: the reference the Listening room opens and the display fields of its card. */
function mediaBody(item) {
  const upload = String(item.id).startsWith('upload:');
  const reference = String(item.id).replace(/^(url|upload):/, '');
  return {
    form: upload ? 'upload' : 'url',
    title: String(item.title || reference).slice(0, 240),
    text: '',
    url: upload ? '' : reference,
    mediaId: upload ? reference : '',
    kind: String(item.kind || '').slice(0, 40),
    durationMs: Number.isFinite(item.duration_ms) ? Math.max(0, Math.round(item.duration_ms)) : null,
    thumbnailUrl: String(item.thumbnail_url || '').slice(0, 600),
    provider: String(item.provider || '').slice(0, 40),
  };
}

/* A text or media import the learner just made goes to the account; a text keeps the id the device already made. */
export async function pushImport(item, { fresh = false } = {}) {
  if (!item?.id || !(await recordsActive())) return false;
  const media = isMedia(item.id);
  // What this page remembered of an earlier record for the same link (kept, since deleted - here or elsewhere) says
  // nothing about a NEW import of it.
  if (media && fresh) mediaRecords.delete(item.id);
  if (media && mediaRecords.get(item.id)?.size) return true; // already kept; opening it again is not a second import
  const ident = media ? crypto.randomUUID() : importUuid(item.id);
  try {
    const body = media ? mediaBody(item) : {
      form: item.kind === 'url' ? 'url' : 'text',
      title: String(item.title || '').slice(0, 240), text: item.kind === 'url' ? '' : String(item.text || ''), url: item.kind === 'url' ? String(item.url || '') : '',
    };
    const saved = await apiRef.saveImport(ident, { operationId: operationId(), expectedVersion: 0, ...body });
    importVersions.set(ident, saved.version);
    if (media) mediaRecords.set(item.id, new Set([ident]));
    return true;
  } catch {
    return false;
  }
}

/* The content-free reference a tombstone keeps for a media import (the server's `import_ref`): the same hash of
   the form and the link or stored media id. Lets a device tell which of ITS imports was deleted elsewhere. */
export async function importRef(memoryId) {
  const subtle = globalThis.crypto?.subtle;
  const match = /^(url|upload):(.+)$/.exec(String(memoryId || ''));
  if (!subtle || !match) return '';
  const digest = new Uint8Array(await subtle.digest('SHA-256', new TextEncoder().encode(`orena.import-ref:${match[1]}:${match[2]}`)));
  return [...digest].map((byte) => byte.toString(16).padStart(2, '0')).join('');
}

/* The learner's imports the account holds, as the device's own shapes (so a new device opens and lists them): a text
   as an import, a pasted link or an uploaded file as a media membership - and which of this device's imports the
   account says were deleted (`deletedIds`, membership ids; `localMediaIds` are the device's own link and file ids,
   matched by their reference). An id the account still holds live is never reported deleted. */
/* Every page of the account's imports and tombstones - never silently limited: it pages until the server says there
   is no next page for either list. */
async function readAllImports() {
  const imports = [];
  const deleted = [];
  let highWater = 0;
  let cursor = null;
  let deletedCursor = null;
  let include = 'both';
  for (let page = 0; page < 400; page += 1) {
    const body = await apiRef.imports({ cursor, deletedCursor, include });
    imports.push(...(body.imports || []));
    deleted.push(...(body.deleted || []));
    highWater = Math.max(highWater, Number(body.highWater) || 0);
    cursor = body.nextCursor ?? null;
    deletedCursor = body.nextDeletedCursor ?? null;
    if (cursor == null && deletedCursor == null) return { imports, deleted, highWater };
    include = cursor != null && deletedCursor != null ? 'both' : cursor != null ? 'imports' : 'deleted';
  }
  throw new Error('The import listing did not end.');
}

export async function pullImportState(language, localMediaIds = []) {
  if (!(await recordsActive())) return { ok: false, items: [], deletedIds: [], records: {}, sequences: {}, highWater: 0 };
  try {
    const { imports, deleted, highWater } = await readAllImports();
    const out = [];
    const records = {}; // membership id -> the live account record ids behind it
    const sequences = {}; // record id -> its change sequence
    for (const item of imports) {
      importVersions.set(importUuid(item.id), item.version);
      sequences[importUuid(item.id)] = Number.isFinite(item.sequence) ? item.sequence : Infinity;
      if (item.form === 'text') {
        out.push({ id: item.id, title: item.title, text: item.text, language, origin: 'imported', kind: 'text' });
        records[item.id] = [importUuid(item.id)];
      } else if (item.form === 'url' || item.form === 'upload') {
        const reference = item.form === 'upload' ? item.mediaId : item.url;
        if (!reference) continue;
        const memoryId = `${item.form}:${reference}`;
        mediaRecords.set(memoryId, (mediaRecords.get(memoryId) || new Set()).add(importUuid(item.id)));
        (records[memoryId] ||= []).push(importUuid(item.id));
        if (out.some((entry) => entry.id === memoryId)) continue;
        out.push({
          id: memoryId, title: item.title, kind: item.kind || '', language, origin: 'imported',
          duration_ms: Number.isFinite(item.durationMs) ? item.durationMs : undefined,
          ...(item.thumbnailUrl ? { thumbnail_url: item.thumbnailUrl } : {}), ...(item.provider ? { provider: item.provider } : {}),
        });
      }
    }
    const live = new Set(out.map((entry) => entry.id));
    const refs = new Set(deleted.map((entry) => entry.ref).filter(Boolean));
    const deletedIds = deleted.filter((entry) => String(entry.id).startsWith('text:') && !live.has(entry.id)).map((entry) => entry.id);
    for (const id of localMediaIds) {
      if (live.has(id) || !refs.size) continue;
      if (refs.has(await importRef(id))) deletedIds.push(id);
    }
    return { ok: true, items: out, deletedIds, records, sequences, highWater };
  } catch {
    return { ok: false, items: [], deletedIds: [], records: {}, sequences: {}, highWater: 0 };
  }
}

export async function pullImports(language) {
  return (await pullImportState(language)).items;
}

/* Confirm the stored copy of an uploaded file is gone (or was never this learner's): true on success or a 404, false
   when it could not be reached or the library could not be trusted (503) - the caller tries again at the next sync. */
export async function settleMedia(id) {
  if (!String(id).startsWith('upload:')) return true;
  try {
    await apiRef.deleteMyMedia(String(id).slice(7));
    return true;
  } catch (error) {
    return error?.status === 404;
  }
}

/* The account record ids this device holds for a membership id right now (what a deletion here may delete). */
export function recordsFor(id) {
  const idents = isMedia(id) ? [...(mediaRecords.get(id) || [])] : [importUuid(id)];
  return idents.filter((ident) => importVersions.has(ident));
}

/* Delete an import from the account. `uuids` limits it to those record ids (the resend of an earlier deletion: only
   records this device deleted, never a record another device made since). An uploaded file this device holds no
   account record for - it never synced - is still deleted from the server's store (owner-scoped, idempotent). */
export async function removeImport(id, { uuids = null } = {}) {
  const held = recordsFor(id).filter((ident) => !uuids || uuids.includes(ident));
  if (!uuids && String(id).startsWith('upload:') && !held.length) {
    try {
      await apiRef.deleteMyMedia(String(id).slice(7));
    } catch {
      /* not ours, already gone, or unreachable: nothing further to do from here */
    }
  }
  if (!held.length || !(await recordsActive())) return false;
  let removed = false;
  for (const ident of held) {
    try {
      await apiRef.deleteImport(ident, operationId(), importVersions.get(ident));
      importVersions.delete(ident);
      mediaRecords.get(id)?.delete(ident);
      removed = true;
    } catch {
      /* a record that could not be removed stays; the next sync sends it again */
    }
  }
  if (isMedia(id) && !mediaRecords.get(id)?.size) mediaRecords.delete(id);
  return removed;
}

/* ---------------------------------------------------------------------------- responses ---- */

/* A bounded, valid-JSON summary of a coaching result: the strengths and fixes it named, never more
   than the server keeps. Empty rather than a truncated fragment. */
export function compactCoaching(result) {
  if (!result || typeof result !== 'object') return '';
  const clip = (value, size) => String(value || '').slice(0, size);
  const pick = (list) => (Array.isArray(list) ? list.slice(0, 6).map((item) => ({
    quote: clip(item?.quote || item?.fragment, 200), why: clip(item?.why || item?.explanation, 300), instead: clip(item?.instead || item?.suggestion, 200),
  })) : []);
  const summary = { strengths: pick(result.strengths || result.carried), fixes: pick(result.fixes || result.landed || result.errors) };
  const text = JSON.stringify(summary);
  return text.length <= 4000 && (summary.strengths.length || summary.fixes.length) ? text : '';
}

/* One take of a typed or transcribed answer and the coaching that came back. Learner work, not
   evidence (D-104 H-3): it is never scored and never read as understanding. */
export async function saveResponse({ kind, source, mode, answer, coaching, sentenceRef = '' }) {
  const text = String(answer || '').trim();
  if (!text || !(await recordsActive())) return false;
  const key = `${kind}:${source?.id || 'open'}:${crypto.randomUUID()}`;
  try {
    await apiRef.saveResponse(key, {
      operationId: operationId(), expectedVersion: 0, mode, answer: text.slice(0, 4000), coaching: compactCoaching(coaching),
      sentenceRef: String(sentenceRef).slice(0, 255), sourceKind: source?.kind || '', sourceId: source?.id ? String(source.id).slice(0, 200) : '',
    });
    return true;
  } catch {
    return false;
  }
}

/* --------------------------------------------------------------------------- provenance ---- */

const PROVENANCE_REASONS = ['looked_up', 'from_reading', 'from_listening', 'from_writing', 'from_speaking', 'from_grammar'];

/* Where a kept word was met. The word is saved on the server first (its own route); a word the server
   does not hold answers 404 here and the device keeps the route back, as before. */
export async function attachProvenance(entry) {
  const word = String(entry?.term || '').trim();
  if (!word || !PROVENANCE_REASONS.includes(entry?.why) || !(await recordsActive())) return false;
  /* An id longer than the record's 200 characters is never cut (a cut id opens something else): the
     occurrence is kept with its sentence and no source. */
  const origin = String(entry.origin || '').length <= 200 ? String(entry.origin || '') : '';
  try {
    await apiRef.attachProvenance(word, {
      operationId: operationId(), reason: entry.why, focus: String(entry.context || '').slice(0, 1200),
      sourceKind: origin ? String(entry.kind || String(entry.why).replace(/^from_/, '') || 'origin').slice(0, 40) : '',
      sourceId: origin,
      // Where inside the source (a Listening transcript segment); the record's own locator field.
      sourceRevision: origin && entry.locator ? String(entry.locator).slice(0, 120) : '',
    });
    return true;
  } catch {
    return false;
  }
}

const REASON_OF_SOURCE = Object.freeze({
  reading: 'from_reading', listening: 'from_listening', writing: 'from_writing', speaking: 'from_speaking', grammar: 'from_grammar',
});

/* A word was just kept from somewhere (the /next word or sentence sheet): record WHERE - which content, which
   sentence - so a new device can still take the learner back to it. The word is already saved (its own route);
   a word the account does not hold answers 404 and the keep stands without provenance. `source` is the sheet's
   own `{kind, content_id}`; the sentence is the context the word was met in. */
export function keepProvenance({ term, source, sentence }) {
  const kind = String(source?.kind || '');
  const id = String(source?.content_id || '');
  return attachProvenance({
    term,
    why: REASON_OF_SOURCE[kind] || 'looked_up',
    // Listening names its media by lesson id, `url:<link>` or `upload:`/stored id: filed as `media:<id>`,
    // the content id the rest of the app (Today, Content Detail, Continue) already uses for it. Reading's
    // ids already carry their kind.
    origin: kind === 'listening' && id && !id.startsWith('media:') ? `media:${id}` : id,
    kind,
    context: sentence || '',
    locator: kind === 'listening' && source?.segment != null ? String(source.segment) : '',
  });
}
