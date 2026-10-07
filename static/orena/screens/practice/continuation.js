/* A read projection, not a scheduler or another learner-state store. A saved
   navigation place proves a visit; only the owning capability's work proves
   something remains unfinished. Unknown evidence never becomes an obligation. */
import { continuationRows } from './model.js';
import { speakingResumeTarget } from '../../product/speaking-resume.js';
import { restoreConversation, MAX_CONVERSATION_TURNS } from '../../product/conversation.js';
import { openMedia } from '../../product/media-source.js';
import { sourceFromLesson } from '../../product/speaking-source.js';
import { loadReadable } from '../reader/source.js';
import { parseContentId } from '../content/model.js';
import { loadConversation } from '../../product/account-records.js';

// Only persisted reads. Read failures, removed content and language mismatches
// cannot silently re-admit a stale media reference or start an import job.
export async function recentMediaFacts(entries, options) {
  return new Map(await Promise.all(entries.filter(item => /^(media|article|book|text):/.test(String(item.id))).map(async item => {
    try {
      if (!item.id.startsWith('media:')) {
        const doc = await loadReadable(parseContentId(item.id), options.memory);
        return [item.id, doc.language === options.language && doc.paragraphs.length ? { readable: true } : null];
      }
      const id = item.id.slice(6);
      const payload = await openMedia(id, options);
      if (payload.asset?.processing_state && payload.asset.processing_state !== 'ready') return [item.id, null];
      const canonicalId = String(payload.catalog?.lesson_id || id);
      const source = sourceFromLesson(canonicalId, payload, item.segment, options.support);
      if (source.language !== options.language || !source.hasModelAudio) return [item.id, null];
      const index = source.lines.findIndex(line => line.lineId === source.line.lineId) + 1;
      return [item.id, { canonicalId, contentKey: payload.catalog?.lesson_id || source.assetId || id,
        segment: source.line.lineId, index, total: source.lines.length }];
    } catch { return [item.id, null]; }
  })));
}

export async function loadPendingRows(memory, language) {
  const value = memory?.value || {};
  const conversations = { ...value.conversations };
  await Promise.all((value.continuation || []).filter(item => item.id?.startsWith('conversation:') && !conversations[item.id]).map(async item => {
    conversations[item.id] = await loadConversation(item.id, language).catch(() => null);
  }));
  const candidates = pendingRows({ ...value, conversations }, language, { limit: Infinity });
  const admitted = await Promise.all(candidates.map(async row => {
    if (row.routeId !== 'reader') return row;
    try {
      const doc = await loadReadable(parseContentId(row.id), memory);
      return doc.language === language && doc.paragraphs.length ? row : null;
    } catch { return null; }
  }));
  return admitted.filter(Boolean).slice(0, 3);
}

export function pendingRows(memory = {}, language, { limit = 3 } = {}) {
  const rows = continuationRows(memory.continuation, { limit: Infinity });
  /* Each opening of a room starts a conversation of its own, so a learner who left the same scenario
     unfinished several times has several records with one title. Continue offers the newest of them once
     (the list is most-recent-first); the others stay reachable from Recently opened (W-03). */
  const conversations = new Set();
  return rows.flatMap(row => {
    if (row.id === 'expression:free' && String(memory.expressions?.[row.id] || '').trim()) {
      return [{ ...row, reason: 'draft', place: null }];
    }
    if (row.routeId === 'conv') {
      const conversation = restoreConversation(memory.conversations?.[row.id], language);
      if (conversation && !conversation.ended && conversation.turns.length < MAX_CONVERSATION_TURNS &&
          conversation.turns.some(turn => turn.role === 'learner')) {
        const same = `${row.title}|${conversation.situation || ''}`;
        if (conversations.has(same)) return [];
        conversations.add(same);
        return [{ ...row, reason: 'conversation', place: null }];
      }
    }
    if (row.routeId === 'reader' && Number.isFinite(row.place?.within) && row.place.within > 0 && row.place.within < 100) {
      return [{ ...row, reason: 'reading', percent: row.place.within }];
    }
    return [];
  }).slice(0, limit);
}

export function recentRows(entries = [], mediaFacts = new Map()) {
  const seen = new Set();
  return continuationRows(entries, { limit: Infinity }).flatMap(row => {
    const fact = mediaFacts.get(row.id);
    if (mediaFacts.has(row.id) && !fact) return [];
    const identity = fact?.canonicalId ? `media:${fact.contentKey || fact.canonicalId}` : row.id;
    const key = `${identity}:${row.routeId}`;
    if (seen.has(key)) return [];
    seen.add(key);
    return [{ ...row, place: null, line: fact?.canonicalId ? { index: fact.index, total: fact.total } : null,
      ...(fact?.canonicalId ? { params: { id: ['compare', 'speak'].includes(row.routeId) ? `media:${fact.canonicalId}` : fact.canonicalId }, query: { segment: fact.segment } } : {}) }];
  });
}

/* The learner's last speaking line, as a route Pronunciation can open at once (D-139 HD-3): the newest
   speaking place device memory holds, admitted only while its media is still readable, ready, in the
   learning language and has its model audio (the same check Recent uses). Nothing admitted, no line:
   the media chooser is then the way in. */
export async function lastSpeakingLine(memory, options) {
  const entries = (memory?.value?.continuation || []).filter((item) => speakingResumeTarget(item)).slice(0, 3);
  if (!entries.length) return null;
  const facts = await recentMediaFacts(entries, { ...options, memory });
  for (const item of entries) {
    const fact = facts.get(item.id);
    if (fact?.canonicalId) return { params: { id: `media:${fact.canonicalId}` }, query: { segment: fact.segment } };
  }
  return null;
}
