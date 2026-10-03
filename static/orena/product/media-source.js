/* One way to open a piece of media by its id, for every room that plays it (Listening, Content
   Detail, Respond). The same three sources the old Encounter opened (ui/encounter.js), so an
   imported item opens through the canonical flow instead of being assumed a curated lesson:

   - `url:<link>`      a saved source reference: read its already prepared personal
                       record (GET /api/media/source), never acquire from a workspace;
   - `upload:<id>`     a file the learner uploaded, Orena's own stored content: resolved by identity
                       (GET /api/media/my/<id>), with no provider and possibly no transcript;
   - anything else     a curated or shared lesson id (GET /api/listening/library/<id>). A bare
                       stored media id (what the upload route answers with as `media_id`) resolves
                       there too, because the library route falls back to the stored entry.

   All three answer the one acquisition payload shape (asset / playback / transcript / translations),
   so the room that renders it does not care which it was. */
import { isRemovedContent, removedImportError } from './import-removed.js';

// Session-only projections of server records, never a learner-data authority.
// Sharing a ready response avoids transport reads, never substitutes for durable artifacts.
const sessions = new Map();
const SESSION_TTL_MS = 5 * 60 * 1000;
const sessionKey = (id, {owner = 'local', language = '', support = ''}) =>
  JSON.stringify([owner, language, support, mediaRef(id).value]);
export function rememberMedia(id, options, payload) {
  if (payload?.transcript?.segments?.length && payload?.asset?.processing_state !== 'processing') {
    sessions.set(sessionKey(id, options), {promise: Promise.resolve(payload), expires: Date.now() + SESSION_TTL_MS});
    while (sessions.size > 24) sessions.delete(sessions.keys().next().value);
  }
}

export function mediaRef(id) {
  const value = String(id || '');
  if (value.startsWith('url:')) return { kind: 'url', value: value.slice(4) };
  if (value.startsWith('upload:')) return { kind: 'upload', value: value.slice(7) };
  return { kind: 'lesson', value };
}

/* Support and learning language select persisted projections, never processing jobs. */
export async function openMedia(id, { api, support = '', language = '', owner = 'local', alive = () => true, onProgress = () => {} } = {}) {
  const ref = mediaRef(id);
  if (!ref.value) throw new Error('No media id');
  // A deleted import is never re-acquired or re-read from a stale route (D-107).
  if (isRemovedContent(id)) throw removedImportError();
  if (ref.kind === 'url') {
    // Old saved URL memberships are references, never new import instructions.
    const payload=await api.mediaSource(ref.value,support);
    if (isRemovedContent(id)) throw removedImportError();
    return payload;
  }
  const options = {owner, language, support};
  const key = sessionKey(id, options);
  const cached = sessions.get(key);
  if (cached && cached.expires > Date.now()) {
    const payload = await cached.promise;
    if (isRemovedContent(id)) throw removedImportError();
    return payload;
  }
  const pending = Promise.resolve().then(() => ref.kind === 'upload'
    ? api.mediaMy(ref.value, support) : api.listeningLibraryLesson(ref.value, support));
  sessions.set(key, {promise: pending, expires: Date.now() + SESSION_TTL_MS});
  try {
    const payload = await pending;
    if (isRemovedContent(id)) throw removedImportError();
    if (!payload?.transcript?.segments?.length || payload?.asset?.processing_state === 'processing') sessions.delete(key);
    else rememberMedia(id, options, payload);
    return payload;
  } catch (error) {
    sessions.delete(key);
    throw error;
  }
}
